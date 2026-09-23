"""Independent synthetic distribution shifts, using only public evaluation APIs.

The effect tables are generated from participant history plus independent
random shifts, frozen on first use, and never passed to Agent. They are testing
scenarios, not estimates of hidden judging effects. --current compares the
working agent with the Git baseline on the same effects and pilot seeds.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import Agent
from benchmark_agents import historical_agent
from environment import make_environment
from scoring_core import CHANNELS, apply_filters, score_campaigns


SCENARIOS = ("history_shift", "weak_history", "sign_reversal")
MODELS_PATH = ROOT / "experiments" / "robustness_shift_models.csv"


def freeze_models(profile, tariffs):
    if MODELS_PATH.exists():
        return pd.read_csv(MODELS_PATH)
    history = pd.read_csv(ROOT / "data" / "change_tariff.csv").drop_duplicates()
    history = history[history.AVG_ARPU_PREV_3M >= 100].copy()
    history["arpu_segment"] = pd.cut(history.AVG_ARPU_PREV_3M,
                                    [-np.inf, 1000, 5000, np.inf], labels=["LOW", "MID", "HIGH"])
    history["ratio"] = (history.AVG_ARPU_NEXT_3M / history.AVG_ARPU_PREV_3M - 1).clip(-1, 3)
    grouped = history.groupby(["tariff_plan_code_from", "tariff_plan_code_to", "arpu_segment"],
                              observed=True)["ratio"].agg(["mean", "count"])
    totals = grouped.groupby(level=[0, 2], observed=True)["count"].transform("sum")
    historical = (grouped["mean"] * grouped["count"] / totals).to_dict()
    known = profile.dropna(subset=["current_tariff", "arpu_segment"])
    cells = sorted(set(zip(known.current_tariff, known.arpu_segment)))
    rows = []
    settings = {"history_shift": (0.5, 0.015, 0.1),
                "weak_history": (0.1, 0.015, 0.14),
                "sign_reversal": (-0.5, 0.025, 0.12)}
    for index, scenario in enumerate(SCENARIOS):
        rng = np.random.default_rng(20260923 + index)
        strength, intercept, scale = settings[scenario]
        for current, segment in cells:
            for target in sorted(tariffs.tariff_plan_code):
                prior = historical.get((current, target, segment), 0.0)
                effect = float(np.clip(strength * prior + rng.normal(intercept, scale), -0.45, 0.6))
                if current == target:
                    effect = 0.0
                rows.append({"scenario": scenario, "tariff_plan_code_from": current,
                             "tariff_plan_code_to": target, "arpu_segment": segment,
                             "arpu_change_pct": 2 * effect, "conversion_rate": 0.5})
    models = pd.DataFrame(rows)
    models.to_csv(MODELS_PATH, index=False)
    return models


def missing_effect(*args):
    raise AssertionError("Frozen synthetic models must cover every transition")


def evaluate(cls, profile, tariffs, model, seed):
    env, evaluator_state = make_environment(profile, model, tariffs, CHANNELS,
                                            100000, 15000, missing_effect, seed=seed)
    started = time.perf_counter()
    campaigns = cls().act(env)
    seconds = time.perf_counter() - started
    sizes = [len(apply_filters(profile, pd.Series(c))) for c in campaigns]
    cost = sum(n * CHANNELS[c["channel"]]["cost_per_contact"] for n, c in zip(sizes, campaigns))
    legal = (1 <= len(campaigns) <= 10 and max(sizes, default=0) <= 5000
             and sum(sizes) <= env.remaining_contacts and cost <= env.remaining_budget)
    pilots = evaluator_state.executed_pilot_campaigns()
    strategy = pd.DataFrame(pilots + campaigns)
    result = score_campaigns(strategy, profile, model, tariffs,
                             profile.predicted_arpu.sum(), missing_effect)
    return {"net": result["net_arpu_gain"], "cost": result["total_cost"],
            "contacts": result["total_contacts"], "pilots": len(pilots),
            "final_campaigns": len(campaigns), "limits_ok": legal, "seconds": seconds}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", action="store_true")
    parser.add_argument("--baseline-ref", default="0655b5c")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--start-seed", type=int, default=500)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "experiments" / "robustness_shift_results.json")
    args = parser.parse_args()
    baseline, commit = historical_agent(args.baseline_ref)
    agents = [("baseline", baseline)] + ([("current", Agent)] if args.current else [])
    profile = pd.read_csv(ROOT / "customer_profile.csv")
    tariffs = pd.read_csv(ROOT / "data" / "dict_tariff.csv")
    models = freeze_models(profile, tariffs)
    rows = []
    for scenario in SCENARIOS:
        model = models.loc[models.scenario == scenario].drop(columns="scenario")
        for seed in range(args.start_seed, args.start_seed + args.runs):
            for label, cls in agents:
                row = {"scenario": scenario, "seed": seed, "agent": label,
                       **evaluate(cls, profile, tariffs, model, seed)}
                rows.append(row)
                print(f"{scenario} seed={seed} {label}: {row['net']:,.0f}; legal={row['limits_ok']}", flush=True)
    summary = []
    for scenario in SCENARIOS:
        for label, _ in agents:
            subset = [r for r in rows if r["scenario"] == scenario and r["agent"] == label]
            summary.append({"scenario": scenario, "agent": label,
                            "mean": float(np.mean([r["net"] for r in subset])),
                            "min": min(r["net"] for r in subset),
                            "positive": sum(r["net"] > 0 for r in subset),
                            "all_legal": all(r["limits_ok"] for r in subset)})
    report = {"scope": "Three frozen synthetic effect tables; five pilot-noise seeds each by default. Not hidden judge performance.",
              "baseline_commit": commit,
              "models_sha256": hashlib.sha256(MODELS_PATH.read_bytes()).hexdigest(),
              "current_sources_sha256": {n: hashlib.sha256((ROOT / (n + ".py")).read_bytes()).hexdigest()
                                         for n in ("agent", "candidate_research", "campaign_planner")},
              "summary": summary, "runs": rows}
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
