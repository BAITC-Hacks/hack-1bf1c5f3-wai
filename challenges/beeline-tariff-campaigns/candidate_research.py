"""Candidate discovery from participant data.

This module is the data lead's work area. Historical changes provide a weak
ranking prior; only pilots can reveal effects for the evaluation audience.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Candidate:
    current_tariff: str
    arpu_segment: str
    data_segment: str
    target_tariff: str
    audience_size: int
    baseline_arpu: float
    prior_ratio: Optional[float]
    prior_count: int

    @property
    def segment_key(self) -> Tuple[str, str, str]:
        return self.current_tariff, self.arpu_segment, self.data_segment

    def filters(self) -> dict:
        return {
            "filter_current_tariff": self.current_tariff,
            "filter_arpu_segment": self.arpu_segment,
            "filter_data_segment": self.data_segment,
        }


def _historical_priors(path: Optional[Path]) -> Dict[Tuple[str, str, str], Tuple[float, int]]:
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
        labels=["LOW", "MID", "HIGH"],
    )
    history["ratio"] = (
        (history["AVG_ARPU_NEXT_3M"] - history["AVG_ARPU_PREV_3M"])
        / history["AVG_ARPU_PREV_3M"]
    ).clip(-1, 3)
    grouped = history.groupby(
        ["tariff_plan_code_from", "tariff_plan_code_to", "arpu_segment"],
        observed=True,
    )["ratio"].agg(["mean", "count"])
    return {
        (str(source), str(target), str(segment)): (float(row["mean"]), int(row["count"]))
        for (source, target, segment), row in grouped.iterrows()
    }


def build_candidates(
    profile: pd.DataFrame,
    tariffs: pd.DataFrame,
    history_path: Optional[Path] = None,
    limit: int = 12,
) -> List[Candidate]:
    """Return distinct, valid cells with one tariff hypothesis per cell.

    This first-pass ranking is intentionally conservative and deterministic.
    The data lead can improve the prior without changing the agent interface.
    """
    prices = {
        str(row.tariff_plan_code): float(row.price_tariff)
        for row in tariffs[["tariff_plan_code", "price_tariff"]].itertuples(index=False)
    }
    if not prices:
        return []

    priors = _historical_priors(history_path)
    cells = (
        profile.dropna(subset=["current_tariff", "arpu_segment", "data_segment"])
        .groupby(["current_tariff", "arpu_segment", "data_segment"], observed=True)
        .agg(audience_size=("ID_NUMBER", "size"), baseline_arpu=("predicted_arpu", "sum"))
        .reset_index()
    )

    candidates = []
    for cell in cells.itertuples(index=False):
        current = str(cell.current_tariff)
        segment = str(cell.arpu_segment)
        data_segment = str(cell.data_segment)
        size = int(cell.audience_size)
        if current not in prices or segment not in {"LOW", "MID", "HIGH"}:
            continue
        if data_segment not in {"NON_USER", "LITE", "HEAVY"} or not 20 <= size <= 5000:
            continue

        alternatives = [target for target, price in prices.items() if price > prices[current]]
        if not alternatives:
            continue

        def rank(target: str) -> Tuple[float, float]:
            prior, count = priors.get((current, target, segment), (0.0, 0))
            evidence = max(-0.3, min(0.3, prior)) * count / (count + 50)
            price_distance = abs(prices[target] - prices[current])
            return evidence, -price_distance

        target = max(alternatives, key=rank)
        prior_ratio, prior_count = priors.get((current, target, segment), (None, 0))
        candidates.append(
            Candidate(
                current_tariff=current,
                arpu_segment=segment,
                data_segment=data_segment,
                target_tariff=target,
                audience_size=size,
                baseline_arpu=float(cell.baseline_arpu),
                prior_ratio=prior_ratio,
                prior_count=prior_count,
            )
        )
    def priority(candidate: Candidate) -> Tuple[float, float]:
        if candidate.prior_ratio is None:
            return 0.0, candidate.baseline_arpu
        reliability = candidate.prior_count / (candidate.prior_count + 50)
        weak_ratio = max(0.0, min(0.3, candidate.prior_ratio)) * reliability
        return weak_ratio * candidate.baseline_arpu, candidate.baseline_arpu

    return sorted(candidates, key=priority, reverse=True)[:limit]
