"""Resource-aware conversion of pilot observations to final campaigns.

This module is the planner and QA lead's work area. The current policy is a
runnable baseline; improve channel economics and uncertainty here.
"""

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import List, Sequence

from candidate_research import Candidate


@dataclass(frozen=True)
class PilotEvidence:
    candidate: Candidate
    observed_lift_ratio: float
    n_customers: int
    cost: float


def select_campaigns(
    candidates: Sequence[Candidate],
    observations: Sequence[PilotEvidence],
    env,
) -> List[dict]:
    """Select disjoint cells without relying on the evaluator's silent caps."""
    valid = [item for item in observations if isfinite(item.observed_lift_ratio)]

    def cautious_ratio(item: PilotEvidence) -> float:
        # The supplied environment documents per-customer noise near 0.804.
        # A one-standard-error deduction prevents a weak positive pilot from
        # automatically triggering a large paid campaign.
        return item.observed_lift_ratio - 0.804 / sqrt(max(item.n_customers, 1))

    ranked = sorted(valid, key=cautious_ratio, reverse=True)

    # A failed pilot still leaves a valid, low-cost output path. Under normal
    # operation final choices come from actual pilot observations.
    if not ranked and candidates:
        ranked = [PilotEvidence(candidates[0], 0.0, 0, 0.0)]

    remaining_contacts = max(0, int(env.remaining_contacts))
    remaining_budget = max(0.0, float(env.remaining_budget))
    chosen_cells = set()
    campaigns = []

    for item in ranked:
        candidate = item.candidate
        if candidate.segment_key in chosen_cells:
            continue
        estimate = cautious_ratio(item)
        if campaigns and estimate <= 0:
            continue

        size = candidate.audience_size
        if size <= 0 or size > 5000 or size > remaining_contacts:
            continue

        channel = "sms" if estimate > 0 else "push"
        if channel not in env.channels:
            channel = "push" if "push" in env.channels else next(iter(env.channels), "")
        if not channel:
            break
        cost = size * float(env.channels[channel]["cost_per_contact"])
        if cost > remaining_budget and "push" in env.channels:
            channel = "push"
            cost = size * float(env.channels[channel]["cost_per_contact"])
        if cost > remaining_budget:
            continue

        campaigns.append({
            "campaign_name": f"main_{len(campaigns) + 1}_{candidate.current_tariff}_{candidate.target_tariff}",
            **candidate.filters(),
            "target_tariff": candidate.target_tariff,
            "channel": channel,
        })
        chosen_cells.add(candidate.segment_key)
        remaining_contacts -= size
        remaining_budget -= cost
        if len(campaigns) >= 3:
            break

    return campaigns
