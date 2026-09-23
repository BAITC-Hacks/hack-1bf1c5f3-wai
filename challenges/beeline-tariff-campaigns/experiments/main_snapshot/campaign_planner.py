"""Bayesian pilot selection and resource-aware campaign planning.

Every (cell, target) hypothesis keeps a normal belief about its base lift ratio
(the effect at channel multiplier 1.0). A pilot over a channel observes
`base * multiplier` plus noise with std 0.804/sqrt(n) (documented by the
organizers), so one pilot updates the belief for every channel at once.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from math import erf, exp, isfinite, pi, sqrt
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from candidate_research import Hypothesis

PER_CUSTOMER_NOISE_SD = 0.804
MAX_PILOT_CUSTOMERS = 200
MIN_PILOT_CUSTOMERS = 10
MAX_CAMPAIGNS = 10
MAX_CUSTOMERS_PER_CAMPAIGN = 5000
# Paid contacts are committed on (mean - CAUTION * sd): a lucky pilot should
# not trigger an expensive call campaign. Free push uses the plain mean.
CAUTION = 0.5
DATA_SEGMENTS = ("NON_USER", "LITE", "HEAVY")
CALL_SEGMENTS = ("LOW", "MEDIUM", "HIGH")


@dataclass
class Belief:
    hypothesis: Hypothesis
    precision: float = field(init=False)
    weighted_sum: float = field(init=False)
    pilots: int = 0
    pilotable: bool = True

    def __post_init__(self):
        self.precision = 1.0 / self.hypothesis.prior_sd ** 2
        self.weighted_sum = self.hypothesis.prior_mean * self.precision

    @property
    def mean(self) -> float:
        return self.weighted_sum / self.precision

    @property
    def sd(self) -> float:
        return sqrt(1.0 / self.precision)

    def observation_precision(self, multiplier: float, n_customers: int) -> float:
        return multiplier ** 2 * n_customers / PER_CUSTOMER_NOISE_SD ** 2

    def update(self, observed_ratio: float, multiplier: float, n_customers: int) -> None:
        if not isfinite(observed_ratio) or n_customers <= 0 or multiplier <= 0:
            return
        obs_precision = self.observation_precision(multiplier, n_customers)
        self.precision += obs_precision
        self.weighted_sum += obs_precision * observed_ratio / multiplier
        self.pilots += 1


def _normal_pdf(z: float) -> float:
    return exp(-0.5 * z * z) / sqrt(2 * pi)


def _normal_cdf(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def next_pilot(beliefs: Sequence[Belief], multiplier: float) -> Optional[Belief]:
    """Pick the hypothesis whose pilot has the largest knowledge gradient.

    The decision per cell is "best target, or nothing". A pilot is worth what
    it is expected to improve that decision, scaled by the cell's ARPU mass.
    """
    by_cell: Dict[tuple, List[Belief]] = defaultdict(list)
    for belief in beliefs:
        by_cell[belief.hypothesis.cell.key].append(belief)

    best, best_score = None, 0.0
    for cell_beliefs in by_cell.values():
        cell = cell_beliefs[0].hypothesis.cell
        n = min(MAX_PILOT_CUSTOMERS, cell.size)
        if n < MIN_PILOT_CUSTOMERS:
            continue
        for belief in cell_beliefs:
            if not belief.pilotable:
                continue
            alternative = max([0.0] + [o.mean for o in cell_beliefs if o is not belief])
            posterior_var = 1.0 / (belief.precision + belief.observation_precision(multiplier, n))
            sigma = sqrt(max(belief.sd ** 2 - posterior_var, 0.0))
            if sigma <= 0:
                continue
            z = -abs(belief.mean - alternative) / sigma
            score = sigma * (z * _normal_cdf(z) + _normal_pdf(z)) * cell.arpu_sum
            if score > best_score:
                best, best_score = belief, score
    return best


@dataclass
class _Proposal:
    net: float
    campaign: dict
    parts: List[Tuple[np.ndarray, float]]  # (profile row positions, lift ratio)
    contacts: int
    cost: float


def plan_campaigns(
    beliefs: Sequence[Belief],
    profile: pd.DataFrame,
    channels: dict,
    budget: float,
    contacts: int,
    max_campaigns: int = MAX_CAMPAIGNS,
) -> List[dict]:
    """Greedily add the campaign with the largest incremental expected net gain.

    Gains are computed per customer against the best campaign already covering
    them (the scorer counts each customer once, at their best campaign), and
    every campaign is sized to fit the remaining contacts and budget exactly.
    Campaigns are either whole cells grouped by (ARPU segment, target, channel)
    or a data/call sub-segment of one cell, which lets the last paid campaigns
    use up the budget without relying on the scorer's silent truncation.
    """
    profile = profile.reset_index(drop=True)
    arpu = profile["predicted_arpu"].fillna(0.0).to_numpy(dtype=float)
    current = np.full(len(profile), np.nan)  # expected lift already secured

    tariff_col = profile["current_tariff"].astype(str).to_numpy()
    segment_col = profile["arpu_segment"].astype(str).to_numpy()
    cell_rows = {}
    for belief in beliefs:
        cell = belief.hypothesis.cell
        if cell.key not in cell_rows:
            mask = np.isin(tariff_col, cell.current_tariffs) & (segment_col == cell.arpu_segment)
            if mask.any():
                cell_rows[cell.key] = np.flatnonzero(mask)
    data = profile["data_segment"].to_numpy()
    calls = profile["call_segment"].to_numpy()
    sub_segments = {}
    for key, rows in cell_rows.items():
        subsets = []
        for d in (None,) + DATA_SEGMENTS:
            for c in (None,) + CALL_SEGMENTS:
                if d is None and c is None:
                    continue
                mask = np.ones(len(rows), dtype=bool)
                if d is not None:
                    mask &= data[rows] == d
                if c is not None:
                    mask &= calls[rows] == c
                if mask.any():
                    subsets.append((d, c, rows[mask]))
        sub_segments[key] = subsets

    by_cell: Dict[tuple, List[Belief]] = defaultdict(list)
    for belief in beliefs:
        if belief.hypothesis.cell.key in cell_rows:
            by_cell[belief.hypothesis.cell.key].append(belief)

    channel_options = [
        (name, float(spec["cost_per_contact"]), float(spec["conversion_multiplier"]))
        for name, spec in channels.items()
    ]

    def lift_ratio(belief: Belief, cost: float, multiplier: float) -> float:
        estimate = belief.mean - (CAUTION * belief.sd if cost > 0 else 0.0)
        return estimate * multiplier

    def gain(rows: np.ndarray, ratio: float) -> float:
        new = ratio * arpu[rows]
        old = current[rows]
        return float(np.where(np.isnan(old), new, np.maximum(new - old, 0.0)).sum())

    campaigns: List[dict] = []
    while len(campaigns) < max_campaigns:
        best: Optional[_Proposal] = None

        # 1) whole cells sharing an ARPU segment, target and channel
        targets_by_segment = defaultdict(set)
        for key, cell_beliefs in by_cell.items():
            for belief in cell_beliefs:
                targets_by_segment[key[1]].add(belief.hypothesis.target_tariff)
        for segment, targets in targets_by_segment.items():
            for target in sorted(targets):
                for name, cost, multiplier in channel_options:
                    options = []
                    for key, cell_beliefs in by_cell.items():
                        if key[1] != segment:
                            continue
                        for belief in cell_beliefs:
                            if belief.hypothesis.target_tariff != target:
                                continue
                            rows = cell_rows[key]
                            ratio = lift_ratio(belief, cost, multiplier)
                            net = gain(rows, ratio) - cost * len(rows)
                            if net > 0:
                                options.append((net / len(rows), net, key, rows, ratio))
                    used_contacts, used_cost, total, parts, tariffs = 0, 0.0, 0.0, [], []
                    for _, net, key, rows, ratio in sorted(options, key=lambda o: o[0], reverse=True):
                        n = len(rows)
                        if (used_contacts + n > min(contacts, MAX_CUSTOMERS_PER_CAMPAIGN)
                                or used_cost + cost * n > budget):
                            continue
                        used_contacts += n
                        used_cost += cost * n
                        total += net
                        parts.append((rows, ratio))
                        tariffs.extend(key[0])
                    if parts and (best is None or total > best.net):
                        best = _Proposal(total, {
                            "filter_arpu_segment": segment,
                            "filter_current_tariff": ";".join(sorted(tariffs)),
                            "target_tariff": target,
                            "channel": name,
                        }, parts, used_contacts, used_cost)

        # 2) a data/call sub-segment of a single cell
        for key, cell_beliefs in by_cell.items():
            for belief in cell_beliefs:
                for name, cost, multiplier in channel_options:
                    ratio = lift_ratio(belief, cost, multiplier)
                    for data_segment, call_segment, rows in sub_segments[key]:
                        n = len(rows)
                        if n > contacts or n > MAX_CUSTOMERS_PER_CAMPAIGN or cost * n > budget:
                            continue
                        net = gain(rows, ratio) - cost * n
                        if best is None or net > best.net:
                            campaign = {
                                "filter_arpu_segment": key[1],
                                "filter_current_tariff": ";".join(key[0]),
                                "target_tariff": belief.hypothesis.target_tariff,
                                "channel": name,
                            }
                            if data_segment is not None:
                                campaign["filter_data_segment"] = data_segment
                            if call_segment is not None:
                                campaign["filter_call_segment"] = call_segment
                            best = _Proposal(net, campaign, [(rows, ratio)], n, cost * n)

        if best is None or best.net <= 0:
            break
        for rows, ratio in best.parts:
            new = ratio * arpu[rows]
            old = current[rows]
            current[rows] = np.where(np.isnan(old), new, np.maximum(old, new))
        contacts -= best.contacts
        budget -= best.cost
        campaign = best.campaign
        campaigns.append({
            "campaign_name": (f"c{len(campaigns) + 1}_{campaign['filter_arpu_segment']}_"
                              f"{campaign['target_tariff']}_{campaign['channel']}"),
            **campaign,
        })
    return campaigns


def fallback_campaigns(beliefs: Sequence[Belief], channels: dict, contacts: int) -> List[dict]:
    """Free push on the most promising cell that still fits the contact limit."""
    channel = "push" if "push" in channels else min(channels, key=lambda c: channels[c]["cost_per_contact"])
    if channels[channel]["cost_per_contact"] > 0:
        return []
    for belief in sorted(beliefs, key=lambda b: b.mean, reverse=True):
        cell = belief.hypothesis.cell
        if belief.mean > 0 and 0 < cell.size <= min(contacts, MAX_CUSTOMERS_PER_CAMPAIGN):
            return [{
                "campaign_name": f"fallback_{cell.name}_{belief.hypothesis.target_tariff}",
                **cell.filters(),
                "target_tariff": belief.hypothesis.target_tariff,
                "channel": channel,
            }]
    return []
