"""Development/held-out comparisons on frozen new worlds and official mock.

Run from challenge directory. Agent receives public env only, never effect tables.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

from compare_main import HERE, MODULES, git, load_agent, RecordedAgent, evaluate_agent
from robustness_shift import evaluate as evaluate_shift
from borrow_prior import configure

BASELINE_COMMIT = "e822ad18e2bfd8f93fc59e077997cefa9cbe1be0"
BASELINE = HERE / "experiments/integration_baseline"
MODELS = HERE / "experiments/integration_effect_worlds.csv"
FAMILIES = {"strong_history": (1., .02), "moderate_shift": (.5, .08),
            "independent": (0., .12), "reversed": (-.5, .10)}


def prepare(round_number=1):
    BASELINE.mkdir(exist_ok=True)
    for name in ("candidate_research", "campaign_planner", "agent"):
        path = BASELINE / f"{name}.py"
        source = git("show", f"{BASELINE_COMMIT}:challenges/beeline-tariff-campaigns/{name}.py")
        if path.exists():
            assert path.read_bytes() == source, "Baseline snapshot changed"
        else:
            path.write_bytes(source)
    if MODELS.exists():
        return
    profile = pd.read_csv(HERE / "customer_profile.csv")
    tariffs = pd.read_csv(HERE / "data/dict_tariff.csv")
    with load_agent(BASELINE):
        historical = sys.modules["candidate_research"]._historical_priors(HERE / "data/change_tariff.csv")
    known = profile.dropna(subset=["current_tariff", "arpu_segment"])
    cells = sorted(set(zip(known.current_tariff, known.arpu_segment)))
    cells = [(t, s) for t, s in cells if s in ("LOW", "MID", "HIGH")]
    targets = sorted(tariffs.tariff_plan_code.astype(str))
    rows = []
    for family_index, (family, (strength, scale)) in enumerate(FAMILIES.items()):
        for world in range(4):
            # Round two reuses development worlds, but reserves entirely new
            # validation worlds after the first hybrid failed validation.
            if round_number == 2 and world > 0:
                world += 3
            rng = np.random.default_rng(95000 + 100 * family_index + world)
            destination = {t: rng.normal(0, scale * .4) for t in targets}
            for current, segment in cells:
                cell_shift = rng.normal(.015, scale * .2)
                for target in targets:
                    history_effect = historical.get((current, target, segment), (0., 0))[0]
                    effect = np.clip(strength * history_effect + destination[target] + cell_shift
                                     + rng.normal(0, scale * .8), -.45, .6)
                    if target == current:
                        effect = 0.
                    rows.append({"family": family, "world": world,
                                 "split": "development" if world == 0 else "validation",
                                 "tariff_plan_code_from": current, "tariff_plan_code_to": target,
                                 "arpu_segment": segment, "arpu_change_pct": 2 * effect,
                                 "conversion_rate": .5})
    pd.DataFrame(rows).to_csv(MODELS, index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("prepare", "development", "validation"), default="development")
    parser.add_argument("--candidate", default="eb_fixed", choices=(
        "eb_fixed", "eb_uncertain", "eb_union", "eb_rank", "eb_sparse", "integrated", "rejected", "rank_rejected"))
    parser.add_argument("--round", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    global MODELS
    if args.round == 2:
        MODELS = HERE / "experiments/integration_effect_worlds_round2.csv"
    prepare(args.round)
    if args.stage == "prepare":
        print(hashlib.sha256(MODELS.read_bytes()).hexdigest())
        return
    models = pd.read_csv(MODELS)
    profile = pd.read_csv(HERE / "customer_profile.csv")
    tariffs = pd.read_csv(HERE / "data/dict_tariff.csv")
    labels = (["baseline", "main", "eb_fixed", "eb_uncertain", "eb_union"]
              if args.stage == "development" else ["baseline", "main", args.candidate])
    if args.round == 2 and args.stage == "development":
        labels = ["baseline", "eb_rank", "eb_sparse"]
    seeds = range(10) if args.stage == "development" else range(100, 130)
    noise_seeds = (700, 701) if args.stage == "development" else (1700, 1701)
    if args.round == 2 and args.stage == "validation":
        seeds, noise_seeds = range(200, 230), (2700, 2701)
    selected = models.loc[models.split == args.stage]
    report = {"stage": args.stage, "baseline_commit": BASELINE_COMMIT,
              "models_sha256": hashlib.sha256(MODELS.read_bytes()).hexdigest(),
              "scope": "Artificial effect families, not estimates of judging effects.",
              "runs": [], "hashes": {}}
    suffix = "" if args.round == 1 else "_round2"
    output = HERE / "experiments" / f"integration_{args.stage}{suffix}.json"
    for label in labels:
        directory = HERE / "experiments/main_snapshot" if label == "main" else BASELINE
        if label == "integrated":
            directory = HERE
        elif label == "rejected":
            directory = HERE / "experiments/integration_rejected"
        elif label == "rank_rejected":
            directory = HERE / "experiments/integration_rank_snapshot"
        report["hashes"][label] = {n: hashlib.sha256((directory / f"{n}.py").read_bytes()).hexdigest()
                                    for n in MODULES if (directory / f"{n}.py").exists()}
        with load_agent(directory) as cls:
            if label.startswith("eb_"):
                configure(label)
            for seed in seeds:
                wrapper = RecordedAgent(cls)
                start = time.perf_counter()
                result = evaluate_agent(wrapper, seed=seed, verbose=False)
                report["runs"].append({"agent": label, "family": "official_mock", "world": None,
                                       "seed": seed, "net": result["net_arpu_gain"],
                                       "limits_ok": wrapper.limits_ok, "seconds": time.perf_counter() - start})
            values = [r["net"] for r in report["runs"] if r["agent"] == label]
            print(f"{label} mock mean={np.mean(values):,.0f} median={np.median(values):,.0f}", flush=True)
            for (family, world), frame in selected.groupby(["family", "world"], sort=True):
                model = frame.drop(columns=["family", "world", "split"])
                for seed in noise_seeds:
                    report["runs"].append({"agent": label, "family": family, "world": int(world),
                                           "seed": seed, **evaluate_shift(cls, profile, tariffs, model, seed)})
                print(f"{label} {family} world={world}: " + ", ".join(f"{r['net']:,.0f}" for r in report["runs"][-2:]), flush=True)
        report["summary"] = pd.DataFrame(report["runs"]).groupby(["agent", "family"]).agg(
            mean=("net", "mean"), median=("net", "median"), minimum=("net", "min"),
            runs=("net", "size"), all_legal=("limits_ok", "all")).reset_index().to_dict("records")
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
