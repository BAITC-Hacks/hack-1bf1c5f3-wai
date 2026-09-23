"""Controlled participant-only variants; no production agent changes.

Run after compare_main.py, from the challenge directory.
"""

from dataclasses import replace
import json
from pathlib import Path
import sys
import time
import types

import pandas as pd

from compare_main import HERE, load_agent, RecordedAgent, evaluate_agent
from robustness_shift import SCENARIOS, MODELS_PATH, evaluate as evaluate_shift


def configure(variant):
    research = sys.modules["candidate_research"]
    entry = sys.modules["agent"]
    if variant == "singleton_groups":
        research.tariff_groups = lambda tariffs: {str(t): (str(t),) for t in tariffs.tariff_plan_code}
    elif variant == "wide_shortlist":
        original = research.build_hypotheses
        entry.build_hypotheses = lambda *a, **kw: original(*a, **kw, top_n=189)
    elif variant == "fixed_prior_sd":
        original = research.build_hypotheses
        entry.build_hypotheses = lambda *a, **kw: [replace(h, prior_sd=.15) for h in original(*a, **kw)]
    elif variant == "current_decision_policy":
        # Current selector works with grouped keys too. Load it against main's
        # Hypothesis type, then transplant only the selection function.
        policy = types.ModuleType("comparison_policy")
        sys.modules[policy.__name__] = policy
        exec(compile((HERE / "campaign_planner.py").read_bytes(), "current_policy", "exec"), policy.__dict__)
        entry.next_pilot = policy.next_pilot
        planner = sys.modules["campaign_planner"]
        source = (HERE / "experiments/main_snapshot/campaign_planner.py").read_text(encoding="utf-8")
        old = "estimate = belief.mean - (CAUTION * belief.sd if cost > 0 else 0.0)"
        assert source.count(old) == 1
        exec(compile(source.replace(old, "estimate = belief.mean - CAUTION * belief.sd"),
                     "main_cautious_planner", "exec"), planner.__dict__)
        entry.plan_campaigns = planner.plan_campaigns
        entry.Belief = planner.Belief


def main():
    profile = pd.read_csv(HERE / "customer_profile.csv")
    tariffs = pd.read_csv(HERE / "data/dict_tariff.csv")
    models = pd.read_csv(MODELS_PATH)
    rows = []
    output = HERE / "experiments/main_ablation_results.json"
    for variant in ("current_decision_policy", "singleton_groups", "wide_shortlist", "fixed_prior_sd"):
        with load_agent(HERE / "experiments/main_snapshot") as cls:
            configure(variant)
            for seed in range(10):
                wrapper = RecordedAgent(cls)
                start = time.perf_counter()
                result = evaluate_agent(wrapper, seed=seed, verbose=False)
                rows.append({"variant": variant, "scenario": "official_mock", "seed": seed,
                             "net": result["net_arpu_gain"], "limits_ok": wrapper.limits_ok,
                             "seconds": time.perf_counter() - start})
            print(f"{variant} mock median: {pd.Series([r['net'] for r in rows if r['variant'] == variant]).median():,.0f}", flush=True)
            for scenario in SCENARIOS:
                model = models.loc[models.scenario == scenario].drop(columns="scenario")
                for seed in range(500, 505):
                    rows.append({"variant": variant, "scenario": scenario, "seed": seed,
                                 **evaluate_shift(cls, profile, tariffs, model, seed)})
                selected = [r["net"] for r in rows if r["variant"] == variant and r["scenario"] == scenario]
                print(f"{variant} {scenario} mean: {pd.Series(selected).mean():,.0f}", flush=True)
        summary = pd.DataFrame(rows).groupby(["variant", "scenario"]).agg(
            median=("net", "median"), mean=("net", "mean"), minimum=("net", "min"),
            all_legal=("limits_ok", "all")).reset_index().to_dict("records")
        output.write_text(json.dumps({"scope": "Exploratory one-factor changes to frozen main; synthetic scenarios only.",
                                      "summary": summary, "runs": rows}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
