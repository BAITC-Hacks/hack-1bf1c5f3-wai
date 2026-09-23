"""Adaptive pilot policy: successive halving in two rounds.

Round 1 — medium pilots (ROUND1_SIZE customers) on the ROUND1_CANDIDATES
          best-scoring shortlisted candidates, so each gets a first look.
Cut     — after every update, drop clear outsiders: candidates whose
          posterior P(effect > 0) is below 1 - SIGN_CONFIDENCE, or that are
          that likely to lose to another target in the same cell.
Round 2 — every remaining pilot goes to a finalist whose sign is still unclear
          (the one with the largest knowledge gradient), sized 150-200 so the
          pilot can settle the sign. A candidate gets at most
          MAX_PILOTS_PER_CANDIDATE pilots; when no finalist is left, unpiloted
          shortlisted candidates with an unclear sign are next.

Beliefs are normal-normal with the empirical-Bayes prior from candidate
research, re-calibrated against the pilots after round 1 and after every
later pilot (calibrate_priors). Pilots use sms or push only, never a call: an sms pilot on 200
customers costs 800 units, a call pilot 32,000 (a third of the budget).
Beliefs are kept at channel multiplier 1.0, so the result extrapolates to
every other channel through its known multiplier.
"""

from collections import defaultdict
from math import exp, pi, sqrt
from typing import Dict, List, Optional, Sequence, Tuple

from campaign_planner import PER_CUSTOMER_NOISE_SD, Belief, calibrate_priors, normal_cdf

PILOT_CHANNELS = ("sms", "push")
ROUND1_CANDIDATES = 8
ROUND1_SIZE = 60
ROUND2_MIN_SIZE = 150
MAX_PILOT_CUSTOMERS = 200
MIN_PILOT_CUSTOMERS = 10
SIGN_CONFIDENCE = 0.95  # the sign counts as settled beyond this posterior probability
SIGN_Z = 1.645  # the matching one-sided normal quantile
# An effect near zero never settles its sign; cap it so it cannot absorb round 2.
MAX_PILOTS_PER_CANDIDATE = 3


def _normal_pdf(z: float) -> float:
    return exp(-0.5 * z * z) / sqrt(2 * pi)


def prob_positive(belief: Belief) -> float:
    return belief.prob_positive


def sign_unclear(belief: Belief) -> bool:
    return 1 - SIGN_CONFIDENCE < belief.prob_positive < SIGN_CONFIDENCE


def _by_cell(beliefs: Sequence[Belief]) -> Dict[tuple, List[Belief]]:
    groups: Dict[tuple, List[Belief]] = defaultdict(list)
    for belief in beliefs:
        groups[belief.hypothesis.cell.key].append(belief)
    return groups


def cut_outsiders(beliefs: Sequence[Belief]) -> List[Belief]:
    """Stop piloting clear losers; returns the newly cut beliefs."""
    cut = []
    for cell_beliefs in _by_cell(beliefs).values():
        for belief in cell_beliefs:
            if not belief.pilotable:
                continue
            loses_to_rival = any(
                normal_cdf((o.mean - belief.mean) / sqrt(o.sd ** 2 + belief.sd ** 2)) > SIGN_CONFIDENCE
                for o in cell_beliefs if o is not belief
            )
            if belief.prob_positive < 1 - SIGN_CONFIDENCE or loses_to_rival:
                belief.pilotable = False
                cut.append(belief)
    return cut


def round2_size(belief: Belief, multiplier: float) -> int:
    """Customers needed for the pilot alone to settle the sign, within 150-200."""
    signal = max(abs(belief.mean) * multiplier, 1e-9)
    needed = (SIGN_Z * PER_CUSTOMER_NOISE_SD / signal) ** 2
    size = int(min(max(needed, ROUND2_MIN_SIZE), MAX_PILOT_CUSTOMERS))
    return min(size, belief.hypothesis.cell.size)


def knowledge_gradient(belief: Belief, cell_beliefs: Sequence[Belief], multiplier: float, n: int) -> float:
    """Expected improvement of the cell decision ("best target or nothing")."""
    alternative = max([0.0] + [o.mean for o in cell_beliefs if o is not belief])
    posterior_var = 1.0 / (belief.precision + belief.observation_precision(multiplier, n))
    sigma = sqrt(max(belief.sd ** 2 - posterior_var, 0.0))
    if sigma <= 0:
        return 0.0
    z = -abs(belief.mean - alternative) / sigma
    return sigma * (z * normal_cdf(z) + _normal_pdf(z)) * belief.hypothesis.cell.arpu_sum


def choose_finalist(beliefs: Sequence[Belief], multiplier: float) -> Optional[Tuple[Belief, int]]:
    """Round-2 pick: an unclear-sign finalist, widening the pool only if none is left."""
    live = [
        b for b in beliefs
        if b.pilotable and b.pilots < MAX_PILOTS_PER_CANDIDATE
        and b.hypothesis.cell.size >= MIN_PILOT_CUSTOMERS
    ]
    pools = (
        [b for b in live if b.pilots > 0 and sign_unclear(b)],  # round-1 survivors
        [b for b in live if sign_unclear(b)],                   # unpiloted shortlist
        live,                                                   # sharpen the rest
    )
    cells = _by_cell(beliefs)
    for pool in pools:
        best, best_score = None, 0.0
        for belief in pool:
            n = round2_size(belief, multiplier)
            score = knowledge_gradient(belief, cells[belief.hypothesis.cell.key], multiplier, n)
            if best is None or score > best_score:
                best, best_score = (belief, n), score
        if best is not None:
            return best
    return None


def _pilot_channel(env, n: int) -> Optional[str]:
    for channel in PILOT_CHANNELS:
        if channel not in env.channels:
            continue
        cost = float(env.channels[channel]["cost_per_contact"])
        if cost * n <= env.remaining_budget:
            return channel
    return None


def _run(env, belief: Belief, n: int) -> bool:
    n = min(n, belief.hypothesis.cell.size, env.remaining_contacts)
    channel = _pilot_channel(env, n)
    if channel is None or n < MIN_PILOT_CUSTOMERS:
        return False
    try:
        result = env.run_pilot(
            target_tariff=belief.hypothesis.target_tariff,
            channel=channel,
            n_customers=n,
            **belief.hypothesis.cell.filters(),
        )
    except (RuntimeError, ValueError, TypeError):
        return False
    belief.update(
        float(result["observed_lift_ratio"]),
        float(env.channels[channel]["conversion_multiplier"]),
        int(result["n_customers"]),
    )
    return True


def run_pilots(env, beliefs: Sequence[Belief]) -> None:
    """Spend every available pilot; `beliefs` must be ordered by candidate score."""
    round1 = [b for b in beliefs if b.hypothesis.cell.size >= MIN_PILOT_CUSTOMERS][:ROUND1_CANDIDATES]
    for belief in round1:
        if env.pilots_left <= 0 or env.remaining_contacts < MIN_PILOT_CUSTOMERS:
            return
        if not _run(env, belief, ROUND1_SIZE):
            belief.pilotable = False
    calibrate_priors(beliefs)
    cut_outsiders(beliefs)

    while env.pilots_left > 0 and env.remaining_contacts >= MIN_PILOT_CUSTOMERS:
        channel = _pilot_channel(env, MAX_PILOT_CUSTOMERS) or next(
            (c for c in PILOT_CHANNELS if c in env.channels), None)
        if channel is None:
            return
        choice = choose_finalist(beliefs, float(env.channels[channel]["conversion_multiplier"]))
        if choice is None:
            return
        belief, n = choice
        if not _run(env, belief, n):
            belief.pilotable = False  # a failed pilot does not consume the limit
            continue
        calibrate_priors(beliefs)
        cut_outsiders(beliefs)
