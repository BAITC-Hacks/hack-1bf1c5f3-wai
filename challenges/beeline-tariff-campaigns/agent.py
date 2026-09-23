"""Judge entry point for the Beeline tariff campaign agent.

1. Build (cell, target) hypotheses with weak priors from the participant history.
2. Spend up to 20 pilots, using a bounded LLM choice at four checkpoints when
   a key is available and the knowledge-gradient policy otherwise.
3. Allocate the remaining contacts and budget to the campaigns with the largest
   expected net gain, choosing the channel per campaign.
"""

import os
from pathlib import Path

from candidate_research import build_hypotheses
from campaign_planner import (
    MAX_PILOT_CUSTOMERS,
    MIN_PILOT_CUSTOMERS,
    Belief,
    fallback_campaigns,
    plan_campaigns,
    rank_pilots,
)
from llm_selector import select_pilot

PILOT_CHANNEL = "sms"
LLM_CHECKPOINTS = (0, 5, 10, 15)
LLM_SHORTLIST_SIZE = 5


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

    def _explore(self, env, beliefs) -> None:
        pilot_results = []
        llm_enabled = bool(os.getenv("OPENAI_API_KEY"))
        last_llm_checkpoint = None
        while env.pilots_left > 0:
            channel = PILOT_CHANNEL if PILOT_CHANNEL in env.channels else "push"
            spec = env.channels[channel]
            cost = float(spec["cost_per_contact"])
            affordable = int(env.remaining_budget // cost) if cost else MAX_PILOT_CUSTOMERS
            if affordable < MIN_PILOT_CUSTOMERS and "push" in env.channels:
                channel, spec, affordable = "push", env.channels["push"], MAX_PILOT_CUSTOMERS

            ranked = rank_pilots(beliefs, float(spec["conversion_multiplier"]))
            if not ranked:
                return
            belief = ranked[0][0]
            ai_chosen = False
            completed = len(env.pilot_history)
            if (llm_enabled and completed in LLM_CHECKPOINTS
                    and completed != last_llm_checkpoint):
                last_llm_checkpoint = completed
                shortlist = ranked[:LLM_SHORTLIST_SIZE]
                try:
                    suggested = select_pilot(shortlist, pilot_results)
                except Exception:
                    suggested = None
                if suggested is not None and any(suggested is item[0] for item in shortlist):
                    belief = suggested
                    ai_chosen = True
                else:
                    llm_enabled = False
                    print("[AI] API unavailable or invalid choice; using deterministic fallback")
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
            if ai_chosen:
                print(f"[AI] Pilot {completed + 1}: selected "
                      f"{cell.current_tariff}/{cell.arpu_segment} -> "
                      f"{belief.hypothesis.target_tariff}")
            pilot_results.append({
                "current_tariff": cell.current_tariff,
                "arpu_segment": cell.arpu_segment,
                "target_tariff": belief.hypothesis.target_tariff,
                "observed_lift_ratio": float(result["observed_lift_ratio"]),
                "n_customers": int(result["n_customers"]),
            })
