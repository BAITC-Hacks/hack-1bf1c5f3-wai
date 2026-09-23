"""Judge entry point for the Beeline tariff campaign agent.

The baseline keeps the three-person work areas separate: candidate research,
pilot orchestration here, and resource-aware final campaign selection.
"""

from pathlib import Path

from candidate_research import build_candidates
from campaign_planner import PilotEvidence, select_campaigns


class Agent:
    def act(self, env) -> list[dict]:
        history_path = Path(__file__).resolve().parent / "data" / "change_tariff.csv"
        try:
            candidates = build_candidates(env.customer_profile, env.tariffs, history_path)
        except (OSError, KeyError, TypeError, ValueError):
            candidates = build_candidates(env.customer_profile, env.tariffs)

        observations = []
        for candidate in candidates[:3]:
            if env.pilots_left <= 0 or env.remaining_contacts < 10:
                break
            if "sms" not in env.channels:
                break

            cost_per_contact = float(env.channels["sms"]["cost_per_contact"])
            affordable = int(env.remaining_budget // cost_per_contact) if cost_per_contact else 200
            n_customers = min(100, candidate.audience_size, env.remaining_contacts, affordable)
            if n_customers < 10:
                break

            try:
                result = env.run_pilot(
                    target_tariff=candidate.target_tariff,
                    channel="sms",
                    n_customers=n_customers,
                    **candidate.filters(),
                )
            except (RuntimeError, ValueError, TypeError):
                continue

            observations.append(
                PilotEvidence(
                    candidate=candidate,
                    observed_lift_ratio=float(result["observed_lift_ratio"]),
                    n_customers=int(result["n_customers"]),
                    cost=float(result["cost"]),
                )
            )

        return select_campaigns(candidates, observations, env)
