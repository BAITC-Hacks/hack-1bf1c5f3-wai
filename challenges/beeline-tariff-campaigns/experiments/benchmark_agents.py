"""Paired official evaluations against a participant agent saved in Git.

Run from the challenge directory, for example:
python experiments/benchmark_agents.py --baseline-ref 0655b5c --start-seed 30 --runs 30
This compares pilot noise seeds, not different hidden judging effect models.
"""

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from agent import Agent
from local_eval import evaluate_agent

MODULES = ("candidate_research", "campaign_planner", "agent")


def git(*args):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
        cwd=ROOT, text=True, encoding="utf-8",
    )


def historical_agent(ref):
    """Load only the three participant modules; leave organizer code untouched."""
    commit = git("rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    saved = {name: sys.modules.get(name) for name in MODULES}
    try:
        for name in MODULES:
            source = git("show", f"{commit}:challenges/beeline-tariff-campaigns/{name}.py")
            module = types.ModuleType(name)
            module.__file__ = str(HERE / f"{name}.py")
            sys.modules[name] = module
            exec(compile(source, module.__file__, "exec"), module.__dict__)
        return sys.modules["agent"].Agent, commit
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def summarize(rows):
    summary = {}
    for label in ("baseline", "current"):
        subset = [row for row in rows if row["agent"] == label]
        summary[label] = {"positive_runs": sum(row["net"] > 0 for row in subset)}
        for key in ("net", "cost", "contacts", "pilots", "final_campaigns", "seconds"):
            values = [row[key] for row in subset]
            summary[label][key] = {
                "mean": statistics.mean(values), "median": statistics.median(values),
                "min": min(values), "max": max(values),
            }
    differences = [rows[i + 1]["net"] - rows[i]["net"] for i in range(0, len(rows), 2)]
    summary["paired"] = {
        "wins": sum(value > 0 for value in differences),
        "ties": sum(value == 0 for value in differences),
        "runs": len(differences), "mean_difference": statistics.mean(differences),
        "median_difference": statistics.median(differences),
        "min_difference": min(differences),
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="0655b5c")
    parser.add_argument("--start-seed", type=int, default=0)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    baseline, commit = historical_agent(args.baseline_ref)
    rows = []
    for seed in range(args.start_seed, args.start_seed + args.runs):
        for label, cls in (("baseline", baseline), ("current", Agent)):
            start = time.perf_counter()
            result = evaluate_agent(cls(), seed=seed, verbose=False)
            if result is None:
                raise RuntimeError(f"{label} produced no result on seed {seed}")
            rows.append({
                "seed": seed, "agent": label, "net": result["net_arpu_gain"],
                "cost": result["total_cost"], "contacts": result["total_contacts"],
                "pilots": result["n_pilots"],
                "final_campaigns": result["n_campaigns"] - result["n_pilots"],
                "seconds": time.perf_counter() - start,
            })
        print(f"seed {seed:3}: baseline {rows[-2]['net']:12,.0f}  current {rows[-1]['net']:12,.0f}", flush=True)
    report = {
        "baseline_commit": commit,
        "current_sources_sha256": {
            name: hashlib.sha256((HERE / f"{name}.py").read_bytes()).hexdigest()
            for name in MODULES
        },
        "python": sys.version,
        "scope": "Official mock effects, paired pilot noise seeds; not hidden judging performance.",
        "summary": summarize(rows), "runs": rows,
    }
    print(json.dumps(report["summary"], indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
