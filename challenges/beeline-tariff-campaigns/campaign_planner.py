"""Bayesian beliefs and resource-aware campaign planning.

Every (cell, target) hypothesis keeps a normal belief about its base lift ratio
(the effect at channel multiplier 1.0). A pilot over a channel observes
`base * multiplier` plus noise with std 0.804/sqrt(n) (documented by the
organizers), so one pilot updates the belief for every channel at once. Which
pilots to run is decided in pilot_policy.py.

Robustness: every go/no-go decision uses the posterior probability that a
campaign pays for itself, not a point estimate, and robust_plan() keeps a
conservative push-only plan ready for contradictory pilots.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from math import erf, isfinite, sqrt
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from candidate_research import Hypothesis

PER_CUSTOMER_NOISE_SD = 0.804
MAX_CAMPAIGNS = 10
MAX_CUSTOMERS_PER_CAMPAIGN = 5000
# Decisions by posterior probability. A free push needs P(effect > 0); a paid
# channel needs P(effect covers its contact cost) — a lucky pilot must not
# trigger an expensive campaign.
MIN_PROB_FREE = 0.60
MIN_PROB_PAID = 0.90
# Paid campaigns are valued on a lower posterior bound (mean - VALUE_CAUTION * sd).
VALUE_CAUTION = 0.5
# Conservative fallback: push only, on cells almost surely positive.
FALLBACK_MIN_PROB = 0.95
# Plans are compared at a pessimistic posterior quantile (10%).
PESSIMISTIC_Z = 1.2816
# Robustness guards for contradictory evidence (see Belief).
CONFLICT_Z = 3.0
CONFLICT_PRIOR_INFLATION = 9.0
# When at least this share of piloted candidates contradicts the prior or its
# own repeat pilots, the evidence as a whole cannot be trusted and only the
# conservative plan is used. Normal and history-shifted runs stay below 0.11;
# deliberately contradictory pilots reach 0.85.
CONFLICT_SHARE = 0.5
# Population-level calibration of the history prior against the pilots: the
# scale of "pilot = scale * prior" has a N(1, CALIBRATION_SCALE_SD^2) prior, so
# weak evidence keeps the history as it is. (An intercept, and never letting
# the fit narrow a prior, both did worse in stress_eval.py.)
CALIBRATION_SCALE_SD = 0.5
MIN_CALIBRATION_POINTS = 4
MIN_PRIOR_SD = 0.05
DATA_SEGMENTS = ("NON_USER", "LITE", "HEAVY")
CALL_SEGMENTS = ("LOW", "MEDIUM", "HIGH")


def normal_cdf(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


@dataclass
class Belief:
    """Normal-normal belief with two robustness guards.

    The prior starts as the history-based hypothesis prior and may be
    re-centred by calibrate_priors() once pilots show how the history maps to
    this audience.

    * Prior-data conflict: when the pooled pilots sit more than CONFLICT_Z
      standard errors from the prior, the prior clearly does not describe
      this audience, so the prior variance is widened and pilots dominate.
    * Contradicting pilots: when two pilots on the same candidate disagree by
      more than CONFLICT_Z, the documented noise understates reality; the
      observation variance is scaled by the measured overdispersion.
    """

    hypothesis: Hypothesis
    observations: List[Tuple[float, float]] = field(default_factory=list)  # (base effect, variance)
    pilotable: bool = True
    prior_mean: float = field(init=False)
    prior_sd: float = field(init=False)

    def __post_init__(self):
        self.prior_mean = self.hypothesis.prior_mean
        self.prior_sd = self.hypothesis.prior_sd

    @property
    def pilots(self) -> int:
        return len(self.observations)

    def _pooled(self) -> Tuple[float, float]:
        weights = [1.0 / v for _, v in self.observations]
        total = sum(weights)
        return sum(w * y for w, (y, _) in zip(weights, self.observations)) / total, 1.0 / total

    def _conflicts_with(self, mean: float, sd: float) -> bool:
        if not self.observations:
            return False
        pooled, variance = self._pooled()
        return abs(pooled - mean) > CONFLICT_Z * sqrt(variance + sd ** 2)

    @property
    def prior_conflict(self) -> bool:
        """The pilots contradict the current (possibly calibrated) prior."""
        return self._conflicts_with(self.prior_mean, self.prior_sd)

    @property
    def history_conflict(self) -> bool:
        """The pilots contradict what the history predicted for this candidate."""
        return self._conflicts_with(self.hypothesis.prior_mean, self.hypothesis.prior_sd)

    @property
    def contradicted(self) -> bool:
        obs = self.observations
        return any(
            abs(yi - yj) > CONFLICT_Z * sqrt(vi + vj)
            for i, (yi, vi) in enumerate(obs) for yj, vj in obs[i + 1:]
        )

    def _variances(self) -> List[float]:
        variances = [v for _, v in self.observations]
        if self.contradicted:
            pooled, _ = self._pooled()
            q = sum((y - pooled) ** 2 / v for y, v in self.observations)
            dispersion = max(1.0, q / (len(self.observations) - 1))
            variances = [v * dispersion for v in variances]
        return variances

    @property
    def precision(self) -> float:
        prior_var = self.prior_sd ** 2 * (CONFLICT_PRIOR_INFLATION if self.prior_conflict else 1.0)
        return 1.0 / prior_var + sum(1.0 / v for v in self._variances())

    @property
    def mean(self) -> float:
        prior_var = self.prior_sd ** 2 * (CONFLICT_PRIOR_INFLATION if self.prior_conflict else 1.0)
        weighted = self.prior_mean / prior_var + sum(
            y / v for (y, _), v in zip(self.observations, self._variances()))
        return weighted / self.precision

    @property
    def sd(self) -> float:
        return sqrt(1.0 / self.precision)

    def prob_above(self, threshold: float) -> float:
        """Posterior probability that the base effect exceeds `threshold`."""
        return normal_cdf((self.mean - threshold) / self.sd)

    @property
    def prob_positive(self) -> float:
        return self.prob_above(0.0)

    def observation_precision(self, multiplier: float, n_customers: int) -> float:
        return multiplier ** 2 * n_customers / PER_CUSTOMER_NOISE_SD ** 2

    def update(self, observed_ratio: float, multiplier: float, n_customers: int) -> None:
        if not isfinite(observed_ratio) or n_customers <= 0 or multiplier <= 0:
            return
        variance = 1.0 / self.observation_precision(multiplier, n_customers)
        self.observations.append((observed_ratio / multiplier, variance))


@dataclass(frozen=True)
class Calibration:
    scale: float
    scale_sd: float
    residual_sd: float
    points: int


def calibrate_priors(beliefs: Sequence[Belief]) -> Optional[Calibration]:
    """Check the history prior against the pilots across candidates and re-centre it.

    Fits pilot = scale * history_prior + residual over the piloted candidates,
    with a N(1, CALIBRATION_SCALE_SD^2) prior on the scale. Every candidate's
    prior, piloted or not, then becomes
    N(scale * history_prior, residual^2 + history_prior^2 * var(scale)).
    If the history overstates effects or points the wrong way, the unpiloted
    candidates are corrected before planning.
    """
    data = [(b.hypothesis.prior_mean,) + b._pooled() for b in beliefs if b.observations]
    if len(data) < MIN_CALIBRATION_POINTS:
        return None
    m, y, v = (np.array(column, dtype=float) for column in zip(*data))
    residual_var = float(np.mean([b.hypothesis.prior_sd ** 2 for b in beliefs if b.observations]))
    scale_precision = scale = 0.0
    for _ in range(10):
        weights = 1.0 / (residual_var + v)
        scale_precision = 1.0 / CALIBRATION_SCALE_SD ** 2 + float((weights * m * m).sum())
        scale = (1.0 / CALIBRATION_SCALE_SD ** 2 + float((weights * m * y).sum())) / scale_precision
        residual_var = max(0.0, float(np.mean((y - scale * m) ** 2 - v)))
    scale_var = 1.0 / scale_precision
    for belief in beliefs:
        history_mean = belief.hypothesis.prior_mean
        belief.prior_mean = scale * history_mean
        belief.prior_sd = max(sqrt(residual_var + history_mean ** 2 * scale_var), MIN_PRIOR_SD)
    return Calibration(scale, sqrt(scale_var), sqrt(residual_var), len(data))


@dataclass
class _Proposal:
    net: float
    campaign: dict
    parts: List[Tuple[np.ndarray, float, "Belief", float]]  # (rows, lift ratio, belief, multiplier)
    contacts: int
    cost: float


def plan_campaigns(
    beliefs: Sequence[Belief],
    profile: pd.DataFrame,
    channels: dict,
    budget: float,
    contacts: int,
    max_campaigns: int = MAX_CAMPAIGNS,
    min_prob_free: float = MIN_PROB_FREE,
    min_prob_paid: float = MIN_PROB_PAID,
) -> List[dict]:
    return _plan(beliefs, profile, channels, budget, contacts, max_campaigns,
                 min_prob_free, min_prob_paid)[0]


def _plan(beliefs, profile, channels, budget, contacts, max_campaigns, min_prob_free, min_prob_paid):
    """Greedily add the campaign with the largest incremental expected net gain.

    Gains are computed per customer against the best campaign already covering
    them (the scorer counts each customer once, at their best campaign), and
    every campaign is sized to fit the remaining contacts and budget exactly.
    A cell or sub-segment only takes a channel when the posterior probability
    that it pays for itself clears min_prob_free (push) or min_prob_paid.
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
        estimate = belief.mean - (VALUE_CAUTION * belief.sd if cost > 0 else 0.0)
        return estimate * multiplier

    def confident(belief: Belief, cost: float, multiplier: float, rows: np.ndarray) -> bool:
        """P(the effect on these customers covers the contact cost) is high enough."""
        if cost <= 0:
            return belief.prob_positive >= min_prob_free
        if belief.contradicted:  # never spend money on contradictory evidence
            return False
        value_base = multiplier * arpu[rows].sum()
        if value_base <= 0:
            return False
        return belief.prob_above(cost * len(rows) / value_base) >= min_prob_paid

    def gain(rows: np.ndarray, ratio: float) -> float:
        new = ratio * arpu[rows]
        old = current[rows]
        return float(np.where(np.isnan(old), new, np.maximum(new - old, 0.0)).sum())

    campaigns: List[dict] = []
    chosen: List[Tuple[np.ndarray, Belief, float]] = []
    spent = 0.0
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
                            if not confident(belief, cost, multiplier, rows):
                                continue
                            ratio = lift_ratio(belief, cost, multiplier)
                            net = gain(rows, ratio) - cost * len(rows)
                            if net > 0:
                                options.append((net / len(rows), net, key, rows, ratio, belief))
                    used_contacts, used_cost, total, parts, tariffs = 0, 0.0, 0.0, [], []
                    for _, net, key, rows, ratio, belief in sorted(options, key=lambda o: o[0], reverse=True):
                        n = len(rows)
                        if (used_contacts + n > min(contacts, MAX_CUSTOMERS_PER_CAMPAIGN)
                                or used_cost + cost * n > budget):
                            continue
                        used_contacts += n
                        used_cost += cost * n
                        total += net
                        parts.append((rows, ratio, belief, multiplier))
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
                        if not confident(belief, cost, multiplier, rows):
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
                            best = _Proposal(net, campaign, [(rows, ratio, belief, multiplier)], n, cost * n)

        if best is None or best.net <= 0:
            break
        for rows, ratio, belief, multiplier in best.parts:
            chosen.append((rows, belief, multiplier))
            new = ratio * arpu[rows]
            old = current[rows]
            current[rows] = np.where(np.isnan(old), new, np.maximum(old, new))
        contacts -= best.contacts
        budget -= best.cost
        spent += best.cost
        campaign = best.campaign
        campaigns.append({
            "campaign_name": (f"c{len(campaigns) + 1}_{campaign['filter_arpu_segment']}_"
                              f"{campaign['target_tariff']}_{campaign['channel']}"),
            **campaign,
        })
    return campaigns, _PlanValue(arpu, chosen, spent)


@dataclass
class _PlanValue:
    """Posterior distribution of a plan's net value.

    Each customer is attributed to the part with the best expected lift (the
    scorer keeps one campaign per customer); a candidate's total exposure then
    moves together with its effect, while different candidates are independent.
    """

    arpu: np.ndarray
    parts: List[Tuple[np.ndarray, Belief, float]]
    cost: float

    def quantile(self, z: float) -> float:
        """Plan value at `mean - z * sd` of its posterior distribution."""
        best = np.full(len(self.arpu), -np.inf)
        owner = np.full(len(self.arpu), -1)
        for k, (rows, belief, multiplier) in enumerate(self.parts):
            lift = belief.mean * multiplier * self.arpu[rows]
            better = lift > best[rows]
            best[rows[better]] = lift[better]
            owner[rows[better]] = k
        exposure: Dict[int, Tuple[Belief, float]] = {}
        for k, (rows, belief, multiplier) in enumerate(self.parts):
            share = multiplier * self.arpu[rows][owner[rows] == k].sum()
            previous = exposure.get(id(belief), (belief, 0.0))[1]
            exposure[id(belief)] = (belief, previous + share)
        mean = sum(b.mean * e for b, e in exposure.values()) - self.cost
        sd = sqrt(sum((b.sd * e) ** 2 for b, e in exposure.values()))
        return mean - z * sd


def robust_plan(
    beliefs: Sequence[Belief],
    profile: pd.DataFrame,
    channels: dict,
    budget: float,
    contacts: int,
) -> Tuple[List[dict], str]:
    """Main plan, or the conservative push-only plan when the evidence is shaky.

    The conservative plan is used when the pilots are broadly contradictory
    (CONFLICT_SHARE of piloted candidates contradict the history or each other),
    or when it is worth more than the main plan at the pessimistic posterior
    quantile of the whole plan.
    """
    free = {name: spec for name, spec in channels.items() if float(spec["cost_per_contact"]) <= 0}
    safe, safe_value = [], None
    if free:
        safe, safe_value = _plan(beliefs, profile, free, budget, contacts, MAX_CAMPAIGNS,
                                 FALLBACK_MIN_PROB, 1.0)

    piloted = [b for b in beliefs if b.pilots]
    flagged = [b for b in piloted if b.contradicted or b.history_conflict]
    if safe and piloted and len(flagged) >= CONFLICT_SHARE * len(piloted):
        return safe, f"conservative: {len(flagged)}/{len(piloted)} piloted candidates have contradictory evidence"

    main, main_value = _plan(beliefs, profile, channels, budget, contacts, MAX_CAMPAIGNS,
                             MIN_PROB_FREE, MIN_PROB_PAID)
    if safe and (not main or safe_value.quantile(PESSIMISTIC_Z) > main_value.quantile(PESSIMISTIC_Z)):
        return safe, "conservative: worth more than the main plan at the pessimistic quantile"
    return main, "main"


def fallback_campaigns(beliefs: Sequence[Belief], channels: dict, contacts: int) -> List[dict]:
    """Last resort: free push on the cell most likely to be positive that fits."""
    channel = "push" if "push" in channels else min(channels, key=lambda c: channels[c]["cost_per_contact"])
    if channels[channel]["cost_per_contact"] > 0:
        return []
    for belief in sorted(beliefs, key=lambda b: b.prob_positive, reverse=True):
        cell = belief.hypothesis.cell
        if belief.prob_positive >= 0.5 and 0 < cell.size <= min(contacts, MAX_CUSTOMERS_PER_CAMPAIGN):
            return [{
                "campaign_name": f"fallback_{cell.name}_{belief.hypothesis.target_tariff}",
                **cell.filters(),
                "target_tariff": belief.hypothesis.target_tariff,
                "channel": channel,
            }]
    return []
