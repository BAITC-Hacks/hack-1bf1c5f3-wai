"""Judge entry point for the Beeline tariff campaign agent.

1. Score group-of-tariffs x ARPU segment x target candidates with an
   empirical-Bayes prior from the participant history; keep the top ones.
2. Spend all 20 pilots adaptively (pilot_policy.py): a first round of medium
   pilots, cut clear outsiders, then larger pilots on unclear finalists.
3. Allocate the remaining contacts and budget to the campaigns with the largest
   expected net gain, choosing the channel per campaign.
"""

from pathlib import Path

from candidate_research import build_hypotheses
from campaign_planner import Belief, fallback_campaigns, plan_campaigns
from pilot_policy import run_pilots


class Agent:
    def act(self, env) -> list[dict]:
        history_path = Path(__file__).resolve().parent / "data" / "change_tariff.csv"
        try:
            hypotheses = build_hypotheses(env.customer_profile, env.tariffs, history_path)
        except (OSError, KeyError, TypeError, ValueError):
            hypotheses = build_hypotheses(env.customer_profile, env.tariffs)
        beliefs = [Belief(h) for h in hypotheses]

        run_pilots(env, beliefs)

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
