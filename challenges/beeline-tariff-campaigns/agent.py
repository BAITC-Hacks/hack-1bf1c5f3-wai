"""Judge entry point for the Beeline tariff campaign agent.

1. Build (cell, target) hypotheses with weak priors from the participant history.
2. Spend all 20 pilots, each on the hypothesis with the largest knowledge
   gradient, updating Bayesian beliefs after every observation.
3. Allocate the remaining contacts and budget to the campaigns with the largest
   expected net gain, choosing the channel per campaign.
"""

from pathlib import Path

from candidate_research import build_hypotheses
from campaign_planner import (
    MAX_PILOT_CUSTOMERS,
    MIN_PILOT_CUSTOMERS,
    Belief,
    fallback_campaigns,
    next_pilot,
    plan_campaigns,
)

PILOT_CHANNEL = "sms"


class Agent:
    def act(self, env) -> list[dict]:
        history_path = Path(__file__).resolve().parent / "data" / "change_tariff.csv"
        try:
            hypotheses = build_hypotheses(env.customer_profile, env.tariffs, history_path)
        except (OSError, KeyError, TypeError, ValueError):
            hypotheses = build_hypotheses(env.customer_profile, env.tariffs)
        beliefs = [Belief(h) for h in hypotheses]

        self._explore(env, beliefs)

        try:
            campaigns = plan_campaigns(
                beliefs, env.customer_profile, env.channels,
                budget=float(env.remaining_budget), contacts=int(env.remaining_contacts),
            )
        except Exception:  # never waste completed pilots on a planning bug
            campaigns = []
        if not campaigns:
            campaigns = fallback_campaigns(beliefs, env.channels, int(env.remaining_contacts))
        return campaigns

    @staticmethod
    def _explore(env, beliefs) -> None:
        while env.pilots_left > 0:
            channel = PILOT_CHANNEL if PILOT_CHANNEL in env.channels else "push"
            spec = env.channels[channel]
            cost = float(spec["cost_per_contact"])
            affordable = int(env.remaining_budget // cost) if cost else MAX_PILOT_CUSTOMERS
            if affordable < MIN_PILOT_CUSTOMERS and "push" in env.channels:
                channel, spec, affordable = "push", env.channels["push"], MAX_PILOT_CUSTOMERS

            belief = next_pilot(beliefs, float(spec["conversion_multiplier"]))
            if belief is None:
                return
            cell = belief.hypothesis.cell
            n_customers = min(MAX_PILOT_CUSTOMERS, cell.size, env.remaining_contacts, affordable)
            if n_customers < MIN_PILOT_CUSTOMERS:
                return

            try:
                result = env.run_pilot(
                    target_tariff=belief.hypothesis.target_tariff,
                    channel=channel,
                    n_customers=n_customers,
                    **cell.filters(),
                )
            except (RuntimeError, ValueError, TypeError):
                belief.pilotable = False
                continue

            belief.update(
                float(result["observed_lift_ratio"]),
                float(spec["conversion_multiplier"]),
                int(result["n_customers"]),
            )
