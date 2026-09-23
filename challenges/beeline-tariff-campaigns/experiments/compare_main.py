"""Compare a frozen main agent with this branch using the official public APIs.

Run from the challenge directory: python experiments/compare_main.py
Only participant modules are downloaded. Organizer files remain unchanged.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types

import pandas as pd

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from local_eval import evaluate_agent
from scoring_core import CHANNELS, apply_filters
from robustness_shift import evaluate as evaluate_shift, SCENARIOS, MODELS_PATH

MODULES = ("transition_prior", "candidate_research", "campaign_planner", "agent")


def git(*args):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT
    )


@contextmanager
def load_agent(directory):
    saved = {name: sys.modules.get(name) for name in MODULES}
    try:
        for name in MODULES:
            path = directory / f"{name}.py"
            sys.modules.pop(name, None)
            if not path.exists():
                continue
            module = types.ModuleType(name)
            # Both versions resolve participant history from the challenge directory.
            module.__file__ = str(HERE / path.name)
            sys.modules[name] = module
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
        yield sys.modules["agent"].Agent
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class RecordedAgent:
    def __init__(self, cls):
        self.agent = cls()
        self.campaigns = []
        self.pilots = []
        self.limits_ok = False
        self.error = None

    def act(self, env):
        try:
            self.campaigns = self.agent.act(env)
        except Exception as exc:
            self.error = repr(exc)
            raise
        self.pilots = env.pilot_history
        sizes = [len(apply_filters(env.customer_profile, pd.Series(c))) for c in self.campaigns]
        cost = sum(n * env.channels[c["channel"]]["cost_per_contact"] for n, c in zip(sizes, self.campaigns))
        self.limits_ok = (1 <= len(sizes) <= 10 and max(sizes, default=0) <= 5000
                          and sum(sizes) <= env.remaining_contacts
                          and cost <= env.remaining_budget and len(self.pilots) <= 20)
        return self.campaigns


def summarize(rows):
    result = {}
    for scenario in sorted({r["scenario"] for r in rows}):
        block = [r for r in rows if r["scenario"] == scenario]
        stats = {}
        for label in ("current", "main"):
            selected = [r for r in block if r["agent"] == label]
            stats[label] = {key: {"median": statistics.median(r[key] for r in selected),
                                 "mean": statistics.mean(r[key] for r in selected),
                                 "min": min(r[key] for r in selected),
                                 "max": max(r[key] for r in selected)}
                            for key in ("net", "cost", "contacts", "seconds")}
            stats[label]["all_legal"] = all(r["limits_ok"] for r in selected)
        current = {r["seed"]: r["net"] for r in block if r["agent"] == "current"}
        differences = [r["net"] - current[r["seed"]] for r in block if r["agent"] == "main"]
        stats["paired"] = {"main_wins": sum(d > 0 for d in differences), "runs": len(differences),
                           "mean_main_minus_current": statistics.mean(differences),
                           "median_main_minus_current": statistics.median(differences)}
        result[scenario] = stats
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="origin/main")
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--shift-runs", type=int, default=5)
    args = parser.parse_args()
    commit = git("rev-parse", args.ref).decode().strip()
    snapshot = HERE / "experiments" / "main_snapshot"
    snapshot.mkdir(exist_ok=True)
    for name in MODULES:
        source = git("show", f"{commit}:challenges/beeline-tariff-campaigns/{name}.py")
        (snapshot / f"{name}.py").write_bytes(source)
    report = {"main_commit": commit, "current_commit": git("rev-parse", "HEAD").decode().strip(),
              "scope": "Synthetic local challenge; paired noise seeds, not hidden judge results.",
              "hashes": {}, "runs": [], "seed42_traces": {}}
    output = HERE / "experiments" / "main_comparison_results.json"
    profile = pd.read_csv(HERE / "customer_profile.csv")
    tariffs = pd.read_csv(HERE / "data" / "dict_tariff.csv")
    models = pd.read_csv(MODELS_PATH)
    report["models_sha256"] = hashlib.sha256(MODELS_PATH.read_bytes()).hexdigest()
    for label, directory in (("current", HERE), ("main", snapshot)):
        report["hashes"][label] = {n: hashlib.sha256((directory / f"{n}.py").read_bytes()).hexdigest()
                                   for n in MODULES if (directory / f"{n}.py").exists()}
        with load_agent(directory) as cls:
            for seed in list(range(args.runs)) + [42]:
                agent = RecordedAgent(cls)
                start = time.perf_counter()
                result = evaluate_agent(agent, seed=seed, verbose=False)
                row = {"scenario": "official_mock" if seed != 42 else "official_seed42",
                       "seed": seed, "agent": label, "net": result["net_arpu_gain"],
                       "cost": result["total_cost"], "contacts": result["total_contacts"],
                       "pilots": result["n_pilots"], "final_campaigns": len(agent.campaigns),
                       "limits_ok": agent.limits_ok, "error": agent.error,
                       "seconds": time.perf_counter() - start}
                report["runs"].append(row)
                if seed == 42:
                    report["seed42_traces"][label] = {"campaigns": agent.campaigns, "pilots": agent.pilots}
                print(f"mock {label} seed={seed}: {row['net']:,.0f}; legal={row['limits_ok']}", flush=True)
            for scenario in SCENARIOS:
                model = models.loc[models.scenario == scenario].drop(columns="scenario")
                for seed in range(500, 500 + args.shift_runs):
                    row = {"scenario": scenario, "seed": seed, "agent": label,
                           **evaluate_shift(cls, profile, tariffs, model, seed)}
                    report["runs"].append(row)
                    print(f"{scenario} {label} seed={seed}: {row['net']:,.0f}; legal={row['limits_ok']}", flush=True)
        output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    report["summary"] = summarize(report["runs"])
    report["official_first10"] = summarize([r for r in report["runs"] if r["scenario"] == "official_mock" and r["seed"] < 10])
    output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
