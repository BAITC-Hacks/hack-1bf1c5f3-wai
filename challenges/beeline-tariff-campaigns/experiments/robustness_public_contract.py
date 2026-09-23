"""Public-interface fault and feedback checks; no mock effects or internals.

Run from the challenge directory with .venv/Scripts/python.exe -X utf8
experiments/robustness_public_contract.py. Synthetic feedback in these checks
is deliberately controlled, and is not a prediction of judging performance.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agent
from candidate_research import Cell, Hypothesis, build_cells, build_hypotheses
from campaign_planner import Belief, fallback_campaigns
from scoring_core import apply_filters


CHANNELS = {
    "push": {"cost_per_contact": 0, "conversion_multiplier": 0.5},
    "sms": {"cost_per_contact": 4, "conversion_multiplier": 0.65},
    "digital_ads": {"cost_per_contact": 22, "conversion_multiplier": 0.85},
    "call": {"cost_per_contact": 160, "conversion_multiplier": 1.2},
}


class PublicStub:
    """Implements documented attributes and pilots with controlled responses."""

    def __init__(self, response=0.2, missing_feedback_at=None):
        self.customer_profile = pd.read_csv(ROOT / "customer_profile.csv")
        self.tariffs = pd.read_csv(ROOT / "data" / "dict_tariff.csv")
        self.channels = CHANNELS
        self.remaining_budget = 100000.0
        self.remaining_contacts = 15000
        self.pilots_left = 20
        self.pilot_history = []
        self.response = response
        self.missing_feedback_at = missing_feedback_at

    def run_pilot(self, target_tariff, channel, n_customers=100, **filters):
        audience = apply_filters(self.customer_profile, pd.Series(filters))
        n = min(int(n_customers), len(audience), self.remaining_contacts)
        cost = self.channels[channel]["cost_per_contact"] * n
        if not 10 <= n <= 200 or cost > self.remaining_budget or self.pilots_left <= 0:
            raise ValueError("Pilot exceeds public limits")
        self.remaining_budget -= cost
        self.remaining_contacts -= n
        self.pilots_left -= 1
        result = {
            "target_tariff": target_tariff, "channel": channel,
            "n_customers": n, "cost": cost,
            "observed_lift_ratio": self.response,
        }
        self.pilot_history.append(result.copy())
        if len(self.pilot_history) == self.missing_feedback_at:
            del result["observed_lift_ratio"]
        return result


def outcome(env):
    try:
        campaigns = agent.Agent().act(env)
        contacts = 0
        spend = 0.0
        max_size = 0
        for campaign in campaigns:
            n = len(apply_filters(env.customer_profile, pd.Series(campaign)))
            contacts += n
            max_size = max(max_size, n)
            spend += n * env.channels[campaign["channel"]]["cost_per_contact"]
        return {
            "pilots": len(env.pilot_history), "final_campaigns": len(campaigns),
            "limits_ok": bool(1 <= len(campaigns) <= 10 and max_size <= 5000
                              and contacts <= env.remaining_contacts
                              and spend <= env.remaining_budget),
            "plan": campaigns,
        }
    except Exception as exc:
        return {"pilots": len(env.pilot_history), "error": type(exc).__name__}


def main():
    report = {}
    positive = outcome(PublicStub(response=0.3))
    negative = outcome(PublicStub(response=-0.3))
    report["feedback_sensitivity"] = {
        "different_plans": positive.get("plan") != negative.get("plan"),
        "positive": positive, "negative": negative,
    }
    report["missing_feedback_after_four_completed_pilots"] = outcome(
        PublicStub(missing_feedback_at=4)
    )
    env = PublicStub()
    original = agent.next_pilot

    def failing_selection(*args, **kwargs):
        if len(env.pilot_history) >= 3:
            raise RuntimeError("Injected decision-path failure")
        return original(*args, **kwargs)

    with patch.object(agent, "next_pilot", failing_selection):
        report["selection_failure_after_three_completed_pilots"] = outcome(env)
    with patch.object(agent, "plan_campaigns", side_effect=RuntimeError("Injected planner failure")):
        report["planner_failure"] = outcome(PublicStub())

    fallback_profile = pd.DataFrame({
        "ID_NUMBER": range(6), "current_tariff": ["tariff_1"] * 6,
        "arpu_segment": ["HIGH"] * 6,
        "data_segment": ["LITE"] + ["HEAVY"] * 5,
        "call_segment": ["LOW"] + ["HIGH"] * 5,
        "predicted_arpu": [50.0] + [1000.0] * 5,
    })
    cell = Cell("tariff_1", "HIGH", 6, 5050.0)
    negative_beliefs = [Belief(Hypothesis(cell, target, mean, 0.15))
                        for target, mean in [("tariff_2", -0.3), ("tariff_3", -0.05)]]
    fallback = fallback_campaigns(negative_beliefs, CHANNELS, 15000,
                                  profile=fallback_profile, budget=0.0)
    selected = (apply_filters(fallback_profile, pd.Series(fallback[0]))
                if fallback else fallback_profile.iloc[:0])
    report["all_negative_minimal_loss_fallback"] = {
        "plan": fallback,
        "least_loss_audience": selected.ID_NUMBER.tolist() == [0],
        "best_available_target": bool(fallback and fallback[0]["target_tariff"] == "tariff_3"),
        "free_channel": bool(fallback and fallback[0]["channel"] == "push"),
    }

    env = PublicStub()
    cells = build_cells(env.customer_profile)
    hypotheses = build_hypotheses(env.customer_profile, env.tariffs, ROOT / "data" / "change_tariff.csv")
    report["candidate_coverage"] = {
        "cells": len(cells), "hypotheses": len(hypotheses),
        "possible_nonidentity_transitions": len(cells) * (len(env.tariffs) - 1),
        "cells_without_candidates": [c.key for c in cells if not any(h.cell.key == c.key for h in hypotheses)],
    }
    no_history = build_hypotheses(env.customer_profile, env.tariffs)
    prices = env.tariffs.set_index("tariff_plan_code")["price_tariff"].to_dict()
    inconsistencies = []
    for cell in cells:
        current = prices.get(cell.current_tariff)
        if current is None:
            continue
        nearest = [t for _, t in sorted((p-current, t) for t, p in prices.items() if p > current)[:3]]
        chosen = [h.target_tariff for h in no_history if h.cell.key == cell.key]
        if set(nearest) != set(chosen):
            inconsistencies.append({"cell": cell.key, "nearest": nearest, "chosen": chosen})
    report["no_history_nearest_price_mismatches"] = inconsistencies
    destination = ROOT / "experiments" / "robustness_public_contract_results.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    compact = {k: v for k, v in report.items() if k not in ("feedback_sensitivity", "no_history_nearest_price_mismatches")}
    compact["different_plans_for_opposite_feedback"] = report["feedback_sensitivity"]["different_plans"]
    compact["no_history_nearest_price_mismatches"] = len(inconsistencies)
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
