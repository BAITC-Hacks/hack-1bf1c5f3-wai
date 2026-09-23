"""Judge entry point for the Beeline tariff campaign agent.

1. Score group-of-tariffs x ARPU segment x target candidates with an
   empirical-Bayes prior from the participant history; keep the top ones.
2. Spend all 20 pilots adaptively (pilot_policy.py): a first round of medium
   pilots, cut clear outsiders, then larger pilots on unclear finalists.
3. Allocate the remaining contacts and budget to the campaigns with the largest
   expected net gain, choosing the channel per campaign. Go/no-go decisions
   use posterior probabilities; a conservative push-only plan replaces the
   main one when pilots contradict each other or it is safer (robust_plan).
"""

from pathlib import Path

from candidate_research import build_hypotheses
from campaign_planner import Belief, fallback_campaigns, robust_plan
from pilot_policy import run_pilots


class Agent:
    def __init__(self):
        self.decision = ""  # which plan was returned and why, for inspection

    def act(self, env) -> list[dict]:
        history_path = Path(__file__).resolve().parent / "data" / "change_tariff.csv"
        try:
            hypotheses = build_hypotheses(env.customer_profile, env.tariffs, history_path)
        except (OSError, KeyError, TypeError, ValueError):
            hypotheses = build_hypotheses(env.customer_profile, env.tariffs)
        beliefs = [Belief(h) for h in hypotheses]

        run_pilots(env, beliefs)

        try:
            campaigns, self.decision = robust_plan(
                beliefs, env.customer_profile, env.channels,
                budget=float(env.remaining_budget), contacts=int(env.remaining_contacts),
            )
        except Exception as error:  # never waste completed pilots on a planning bug
            campaigns, self.decision = [], f"planning failed: {type(error).__name__}"
        if not campaigns:
            campaigns = fallback_campaigns(beliefs, env.channels, int(env.remaining_contacts))
            self.decision += "; last-resort single push campaign"
        return campaigns
