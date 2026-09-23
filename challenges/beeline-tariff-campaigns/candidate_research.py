"""Candidate discovery from participant data.

The scoring code looks up a transition effect by (current_tariff, arpu_segment),
so data/call segment filters only shrink the audience, they never change the
per-customer effect. A *cell* is therefore a group of current tariffs x ARPU
segment, where a group joins tariffs with identical specifications (same price
and bundles). Every cell x target tariff is scored as

    expected effect x available audience x mean predicted_arpu

using the empirical-Bayes prior from transition_prior.py, and only the top
candidates are kept for piloting and planning.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from transition_prior import ARPU_SEGMENTS, estimate_transitions, load_history

# Prior width used only when there is no history for a transition.
PRIOR_SD = 0.15
TOP_CANDIDATES = 30  # the brief asks for the top 15-30; shorter lists were fragile when effects shift
TARGETS_PER_CELL = 3  # keeps the shortlist from collapsing onto one cell
MAX_CUSTOMERS_PER_CAMPAIGN = 5000


@dataclass(frozen=True)
class Cell:
    current_tariffs: Tuple[str, ...]
    arpu_segment: str
    size: int
    arpu_sum: float

    @property
    def key(self) -> Tuple[Tuple[str, ...], str]:
        return self.current_tariffs, self.arpu_segment

    @property
    def name(self) -> str:
        return "+".join(self.current_tariffs)

    def filters(self) -> dict:
        return {
            "filter_current_tariff": ";".join(self.current_tariffs),
            "filter_arpu_segment": self.arpu_segment,
        }


@dataclass(frozen=True)
class Hypothesis:
    cell: Cell
    target_tariff: str
    prior_mean: float
    prior_sd: float
    score: float = 0.0


def tariff_groups(tariffs: pd.DataFrame) -> Dict[str, Tuple[str, ...]]:
    """Map each tariff to the group of tariffs with identical specifications."""
    specs = [c for c in tariffs.columns if c not in ("tariff_plan_code", "description")]
    groups = {}
    for _, group in tariffs.groupby(specs, dropna=False):
        members = tuple(sorted(group["tariff_plan_code"].astype(str)))
        for code in members:
            groups[code] = members
    return groups


def build_cells(profile: pd.DataFrame, groups: Dict[str, Tuple[str, ...]]) -> List[Tuple[Cell, pd.DataFrame]]:
    """Return group cells with the per-tariff audience inside each of them."""
    per_tariff = (
        profile.dropna(subset=["current_tariff", "arpu_segment"])
        .assign(
            current_tariff=lambda df: df["current_tariff"].astype(str),
            arpu_segment=lambda df: df["arpu_segment"].astype(str),
            predicted_arpu=lambda df: df["predicted_arpu"].fillna(0.0),
        )
        .groupby(["current_tariff", "arpu_segment"], observed=True)
        .agg(size=("ID_NUMBER", "size"), arpu_sum=("predicted_arpu", "sum"))
        .reset_index()
    )
    per_tariff = per_tariff[per_tariff["arpu_segment"].isin(ARPU_SEGMENTS)]
    per_tariff["group"] = per_tariff["current_tariff"].map(lambda t: groups.get(t, (t,)))
    cells = []
    for (group, segment), members in per_tariff.groupby(["group", "arpu_segment"]):
        present = tuple(sorted(members["current_tariff"]))
        cell = Cell(present, segment, int(members["size"].sum()), float(members["arpu_sum"].sum()))
        cells.append((cell, members))
    return cells


def build_hypotheses(
    profile: pd.DataFrame,
    tariffs: pd.DataFrame,
    history_path: Optional[Path] = None,
    top_n: int = TOP_CANDIDATES,
    per_cell: int = TARGETS_PER_CELL,
) -> List[Hypothesis]:
    """Score every cell x target tariff and return the top `top_n` candidates."""
    prices = {
        str(row.tariff_plan_code): float(row.price_tariff)
        for row in tariffs[["tariff_plan_code", "price_tariff"]].itertuples(index=False)
    }
    if not prices:
        return []

    estimates = estimate_transitions(load_history(history_path), tariffs)
    priors = {}
    if not estimates.empty:
        priors = {
            (row.segment, row[0], row[1]): (float(row.effect_mean), float(row.effect_sd))
            for row in estimates[["from", "to", "segment", "effect_mean", "effect_sd"]].itertuples(index=False)
        }

    scored = []
    for cell, members in build_cells(profile, tariff_groups(tariffs)):
        weights = members["arpu_sum"].to_numpy(dtype=float)
        if weights.sum() <= 0:
            weights = members["size"].to_numpy(dtype=float)
        weights = weights / weights.sum()
        mean_arpu = cell.arpu_sum / cell.size
        available = min(cell.size, MAX_CUSTOMERS_PER_CAMPAIGN)
        cheapest = min(prices.get(t, 0.0) for t in cell.current_tariffs)
        for target in prices:
            if target in cell.current_tariffs:
                continue
            member = [priors.get((cell.arpu_segment, t, target), (0.0, PRIOR_SD)) for t in members["current_tariff"]]
            means = pd.Series([m for m, _ in member]).to_numpy()
            sds = pd.Series([s for _, s in member]).to_numpy()
            mean = float((weights * means).sum())
            # mixture variance: members' own uncertainty plus their spread
            sd = float(((weights * (sds ** 2 + (means - mean) ** 2)).sum()) ** 0.5)
            score = mean * available * mean_arpu
            # without history every score is 0: prefer big cells, then the nearest pricier tariff
            gap = prices[target] - cheapest
            tie_break = (cell.arpu_sum, gap > 0, -abs(gap))
            scored.append(((score,) + tie_break, Hypothesis(cell, target, mean, sd, score)))

    shortlist, per_cell_count = [], {}
    for _, hypothesis in sorted(scored, key=lambda item: item[0], reverse=True):
        key = hypothesis.cell.key
        if per_cell_count.get(key, 0) >= per_cell:
            continue
        per_cell_count[key] = per_cell_count.get(key, 0) + 1
        shortlist.append(hypothesis)
        if len(shortlist) >= top_n:
            break
    return shortlist
