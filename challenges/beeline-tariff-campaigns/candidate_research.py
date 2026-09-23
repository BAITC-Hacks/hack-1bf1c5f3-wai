"""Candidate discovery from participant data.

The scoring code looks up a transition effect by (current_tariff, arpu_segment),
so a *cell* is exactly that pair: data/call segment filters only shrink the
audience, they never change the per-customer effect. Each cell gets a few
target-tariff hypotheses with an empirical-Bayes prior from the historical
changes (see transition_prior.py); pilots reveal the effect for the evaluation
audience.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from transition_prior import ARPU_SEGMENTS, estimate_transitions, load_history

# Prior width used only when there is no history at all.
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

    estimates = estimate_transitions(load_history(history_path), tariffs)
    priors = {}
    if not estimates.empty:
        for (segment, source), group in estimates.groupby(["segment", "from"]):
            priors[(segment, source)] = group.sort_values("effect_mean", ascending=False)

    hypotheses = []
    for cell in build_cells(profile):
        current, segment = cell.current_tariff, cell.arpu_segment
        ranked = priors.get((segment, current))
        if ranked is not None:
            for row in ranked.head(per_cell).itertuples(index=False):
                hypotheses.append(Hypothesis(cell, row.to, float(row.effect_mean), float(row.effect_sd)))
        elif current in prices:
            # no history at all: nearest pricier tariffs with a neutral prior
            pricier = sorted(
                (price - prices[current], target)
                for target, price in prices.items()
                if price > prices[current]
            )
            for _, target in pricier[:per_cell]:
                hypotheses.append(Hypothesis(cell, target, 0.0, PRIOR_SD))
    return hypotheses
