"""Candidate discovery from participant data.

The scoring code looks up a transition effect by (current_tariff, arpu_segment),
so a *cell* is exactly that pair: data/call segment filters only shrink the
audience, they never change the per-customer effect. Each cell gets a few
target-tariff hypotheses with a weak prior from the historical changes; pilots
are what reveal the effect for the evaluation audience.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

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


def build_hypotheses(
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

        for mean, target in sorted(options, reverse=True)[:per_cell]:
            hypotheses.append(Hypothesis(cell, target, mean, PRIOR_SD))
    return hypotheses
