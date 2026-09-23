"""Candidate discovery from participant data.

The scoring code looks up a transition effect by (current_tariff, arpu_segment),
so a *cell* is exactly that pair: data/call segment filters only shrink the
audience, they never change the per-customer effect. Each cell gets a few
target-tariff hypotheses ranked by a hierarchical historical model. We retain
every cell and the original weak priors: pilots reveal the effect for the
evaluation audience, especially for previously unseen transitions.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from transition_prior import estimate_transitions, load_history

ARPU_SEGMENTS = ("LOW", "MID", "HIGH")
# The judged audience "noticeably differs" from the history, so the prior is
# deliberately wide relative to typical effects (0.0-0.45).
PRIOR_SD = 0.15
TARGETS_PER_CELL = 3


@dataclass(frozen=True)
class Cell:
    current_tariff: str
    arpu_segment: str
    size: int
    arpu_sum: float

    @property
    def key(self) -> Tuple[str, str]:
        return self.current_tariff, self.arpu_segment

    def filters(self) -> dict:
        return {
            "filter_current_tariff": self.current_tariff,
            "filter_arpu_segment": self.arpu_segment,
        }


@dataclass(frozen=True)
class Hypothesis:
    cell: Cell
    target_tariff: str
    prior_mean: float
    prior_sd: float


def _historical_priors(path: Optional[Path]) -> Dict[Tuple[str, str, str], Tuple[float, int]]:
    """Map (from, to, arpu_segment) -> (expected lift ratio, observation count).

    The expected ratio is the mean relative ARPU change times the share of
    switchers from that cell who chose this target (a conversion proxy).
    """
    if path is None or not path.is_file():
        return {}

    history = pd.read_csv(path)
    # The supplied history contains exact duplicate events. Remove them before
    # computing transition means so duplicated rows do not overweight a prior.
    history = history.drop_duplicates()
    history = history[history["AVG_ARPU_PREV_3M"] >= 100].copy()
    history["arpu_segment"] = pd.cut(
        history["AVG_ARPU_PREV_3M"],
        bins=[-np.inf, 1000, 5000, np.inf],
        labels=list(ARPU_SEGMENTS),
    )
    history["ratio"] = (
        (history["AVG_ARPU_NEXT_3M"] - history["AVG_ARPU_PREV_3M"])
        / history["AVG_ARPU_PREV_3M"]
    ).clip(-1, 3)
    grouped = history.groupby(
        ["tariff_plan_code_from", "tariff_plan_code_to", "arpu_segment"],
        observed=True,
    )["ratio"].agg(["mean", "count"])
    totals = grouped.groupby(level=[0, 2], observed=True)["count"].transform("sum")
    grouped["effect"] = grouped["mean"] * grouped["count"] / totals
    return {
        (str(source), str(target), str(segment)): (float(row["effect"]), int(row["count"]))
        for (source, target, segment), row in grouped.iterrows()
    }


def build_cells(profile: pd.DataFrame) -> List[Cell]:
    cells = (
        profile.dropna(subset=["current_tariff", "arpu_segment"])
        .assign(predicted_arpu=lambda df: df["predicted_arpu"].fillna(0.0))
        .groupby(["current_tariff", "arpu_segment"], observed=True)
        .agg(size=("ID_NUMBER", "size"), arpu_sum=("predicted_arpu", "sum"))
        .reset_index()
    )
    return [
        Cell(str(row.current_tariff), str(row.arpu_segment), int(row.size), float(row.arpu_sum))
        for row in cells.itertuples(index=False)
        if str(row.arpu_segment) in ARPU_SEGMENTS
    ]


def _baseline_hypotheses(
    profile: pd.DataFrame,
    tariffs: pd.DataFrame,
    history_path: Optional[Path] = None,
    per_cell: int = TARGETS_PER_CELL,
) -> List[Hypothesis]:
    """Return up to `per_cell` target-tariff hypotheses for every audience cell."""
    prices = {
        str(row.tariff_plan_code): float(row.price_tariff)
        for row in tariffs[["tariff_plan_code", "price_tariff"]].itertuples(index=False)
    }
    if not prices:
        return []

    priors = _historical_priors(history_path)
    hypotheses = []
    for cell in build_cells(profile):
        current, segment = cell.current_tariff, cell.arpu_segment
        options = []
        for target in prices:
            if target == current or (current, target, segment) not in priors:
                continue
            effect, count = priors[(current, target, segment)]
            # shrink effects seen on a handful of switchers towards zero
            options.append((effect * count / (count + 5), target))

        if not options and current in prices:
            # no history for this cell: nearest pricier tariffs, neutral prior
            pricier = sorted(
                (price - prices[current], target)
                for target, price in prices.items()
                if price > prices[current]
            )
            options = [(0.0, target) for _, target in pricier]

        # Stable ties preserve the nearest-price order of neutral candidates.
        for mean, target in sorted(options, key=lambda item: item[0], reverse=True)[:per_cell]:
            hypotheses.append(Hypothesis(cell, target, mean, PRIOR_SD))
    return hypotheses


def build_hypotheses(
    profile: pd.DataFrame,
    tariffs: pd.DataFrame,
    history_path: Optional[Path] = None,
    per_cell: int = TARGETS_PER_CELL,
) -> List[Hypothesis]:
    """Rank targets with empirical-Bayes history, keeping every audience cell.

    The model shares evidence across destinations and price gaps to rank
    transitions, including those missing from history. Belief means still use
    the directly observed, count-shrunk historical effect; unseen transitions
    start neutral. All candidates retain SD 0.15. Model extrapolation therefore
    suggests what to investigate without becoming assumed campaign gain.
    Model failures or unsupported cells use the original historical/price
    fallback, so a numerical failure cannot prevent pilots from running.
    """
    if per_cell <= 0:
        return []
    baseline = _baseline_hypotheses(profile, tariffs, history_path, per_cell)
    try:
        estimates = estimate_transitions(load_history(history_path), tariffs)
        if estimates.empty:
            return baseline
        rankings = {
            (str(row[0]), str(row[1]), str(row.segment)): float(row.effect_mean)
            for row in estimates[["from", "to", "segment", "effect_mean"]].itertuples(index=False)
            if np.isfinite(row.effect_mean)
        }
        historical = _historical_priors(history_path)
    except Exception:
        # The richer model is optional; retain the simpler valid hypotheses.
        return baseline

    by_cell = {}
    for hypothesis in baseline:
        by_cell.setdefault(hypothesis.cell.key, []).append(hypothesis)
    targets = list(tariffs["tariff_plan_code"].astype(str))
    hypotheses = []
    for cell in build_cells(profile):
        options = [
            (rankings[(cell.current_tariff, target, cell.arpu_segment)], target)
            for target in targets
            if target != cell.current_tariff
            and (cell.current_tariff, target, cell.arpu_segment) in rankings
        ]
        if not options:
            hypotheses.extend(by_cell.get(cell.key, []))
            continue
        for _, target in sorted(options, key=lambda item: item[0], reverse=True)[:per_cell]:
            effect, count = historical.get((cell.current_tariff, target, cell.arpu_segment), (0.0, 0))
            mean = effect * count / (count + 5)
            hypotheses.append(Hypothesis(cell, target, mean, PRIOR_SD))
    return hypotheses
