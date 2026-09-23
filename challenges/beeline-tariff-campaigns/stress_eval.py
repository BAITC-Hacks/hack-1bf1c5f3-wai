"""
Stress tests: run the agent in worlds whose effects differ from the history.

    python stress_eval.py                          # every scenario, 5 worlds x 2 seeds
    python stress_eval.py --worlds 10 --seeds 3
    python stress_eval.py --scenarios hostile,noisy_pilots

Why. The mock environment builds its effects from data/change_tariff.csv, and
the agent's prior comes from the same file, so local_eval.py flatters the
agent. The judge runs the same environment class on effects that "noticeably
differ". Each scenario below builds such a world from the mock effect model
and scores the agent with scoring_core, exactly like local_eval.py.

What to look for: a positive result in every run (stable sign), a p10 close to
the median (low variance) and small losses in the hostile world, where
little can be earned.

All data is synthetic; these are not Beeline results.
"""

import argparse
import contextlib
from typing import Callable, Dict, List

import numpy as np
import pandas as pd

import candidate_research
from environment import make_environment
from mock_environment import (
    CHANNELS,
    MAX_TOTAL_CONTACTS,
    TOTAL_BUDGET,
    _mock_fallback,
    _mock_impact_model,
)
from scoring_core import MAX_CAMPAIGNS, sanitize_campaigns, score_campaigns

FILTER_COLUMNS = ["filter_arpu_segment", "filter_data_segment", "filter_call_segment",
                  "filter_current_tariff", "explicit_ids"]


def _shifted(model, rng):
    """Every transition is rescaled and shifted; conversion changes too."""
    model = model.copy()
    model["arpu_change_pct"] = (model["arpu_change_pct"] * rng.uniform(-0.3, 1.5, len(model))
                                + rng.normal(0, 0.15, len(model)))
    model["conversion_rate"] = (model["conversion_rate"] * rng.uniform(0.5, 1.5, len(model))).clip(0, 1)
    return model


def _shuffled(model, rng):
    """Effects are reassigned between transitions: the history ranks the wrong pairs."""
    model = model.copy()
    for _, index in model.groupby("arpu_segment", observed=True).groups.items():
        order = rng.permutation(len(index))
        for column in ("arpu_change_pct", "conversion_rate"):
            model.loc[index, column] = model.loc[index, column].to_numpy()[order]
    return model


def _damped(model, rng):
    """Effects are a quarter of the history: thin margins, paid channels rarely pay."""
    model = model.copy()
    model["arpu_change_pct"] = model["arpu_change_pct"] * 0.25
    return model


def _hostile(model, rng):
    """Most transitions lose ARPU: the agent should find the few winners or stay small."""
    model = model.copy()
    model["arpu_change_pct"] = model["arpu_change_pct"] * rng.uniform(-1.2, 0.4, len(model))
    return model


class _NoisyPilots:
    """Pilots twice as noisy as documented (4x variance)."""

    def __init__(self, env, rng):
        self._env, self._rng = env, rng

    def __getattr__(self, name):
        return getattr(self._env, name)

    def run_pilot(self, *args, **kwargs):
        result = dict(self._env.run_pilot(*args, **kwargs))
        extra_sd = 0.804 * np.sqrt(3) / np.sqrt(result["n_customers"])
        result["observed_lift_ratio"] += float(self._rng.normal(0, extra_sd))
        return result


@contextlib.contextmanager
def _without_history():
    original = candidate_research.load_history
    candidate_research.load_history = lambda path: original(None)
    try:
        yield
    finally:
        candidate_research.load_history = original


# name -> (effect model transform, wrap pilots with extra noise, hide the history)
SCENARIOS: Dict[str, tuple] = {
    "shifted": (_shifted, False, False),
    "shuffled": (_shuffled, False, False),
    "damped": (_damped, False, False),
    "hostile": (_hostile, False, False),
    "noisy_pilots": (_shifted, True, False),
    "no_history": (_shifted, False, True),
}


def run_once(agent_factory: Callable, profile, dict_tariff, model, seed, noisy=False, hide_history=False) -> dict:
    env, internals = make_environment(profile, model, dict_tariff, CHANNELS, TOTAL_BUDGET,
                                      MAX_TOTAL_CONTACTS, _mock_fallback, seed=seed)
    agent = agent_factory()
    crashed = False
    target = _NoisyPilots(env, np.random.default_rng(seed + 7)) if noisy else env
    with _without_history() if hide_history else contextlib.nullcontext():
        try:
            final = agent.act(target)
        except Exception:  # the judge still scores the pilots
            final, crashed = [], True
    final = sanitize_campaigns(final, env.tariffs)[:MAX_CAMPAIGNS]
    campaigns = pd.DataFrame(internals.executed_pilot_campaigns() + final)
    for column in FILTER_COLUMNS:
        if column not in campaigns.columns:
            campaigns[column] = None
    result = score_campaigns(campaigns, env.customer_profile, model, env.tariffs,
                             profile["predicted_arpu"].sum(), _mock_fallback)
    return {
        "net": result["net_arpu_gain"],
        "pilots": len(env.pilot_history),
        "conservative": str(getattr(agent, "decision", "")).startswith("conservative"),
        "crashed": crashed,
    }


def run_stress(agent_factory: Callable, scenarios: List[str], worlds: int, seeds: int) -> pd.DataFrame:
    profile = pd.read_csv("customer_profile.csv")
    dict_tariff = pd.read_csv("data/dict_tariff.csv")
    base = _mock_impact_model(pd.read_csv("data/change_tariff.csv"))
    rows = []
    for name in scenarios:
        transform, noisy, hide_history = SCENARIOS[name]
        for world in range(worlds):
            model = transform(base, np.random.default_rng(1000 + world))
            for seed in range(seeds):
                outcome = run_once(agent_factory, profile, dict_tariff, model, seed, noisy, hide_history)
                rows.append({"scenario": name, "world": world, "seed": seed, **outcome})
    return pd.DataFrame(rows)


def summarize(runs: pd.DataFrame) -> pd.DataFrame:
    def within_world_std(group):
        spread = group.groupby("world")["net"].std(ddof=1)
        return float(spread.mean()) if spread.notna().any() else float("nan")

    summary = []
    for name, group in runs.groupby("scenario", sort=False):
        net = group["net"]
        summary.append({
            "scenario": name,
            "runs": len(group),
            "positive": f"{int((net > 0).sum())}/{len(group)}",
            "median": net.median(),
            "p10": net.quantile(0.1),
            "min": net.min(),
            "within_world_std": within_world_std(group),
            "conservative": int(group["conservative"].sum()),
            "crashed": int(group["crashed"].sum()),
        })
    return pd.DataFrame(summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenarios", default=",".join(SCENARIOS), help="comma-separated subset")
    parser.add_argument("--worlds", type=int, default=5, help="effect models per scenario")
    parser.add_argument("--seeds", type=int, default=2, help="pilot-noise seeds per world")
    args = parser.parse_args()

    from agent import Agent

    names = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    unknown = sorted(set(names) - set(SCENARIOS))
    if unknown:
        parser.error(f"unknown scenarios {unknown}; choose from {list(SCENARIOS)}")

    summary = summarize(run_stress(Agent, names, args.worlds, args.seeds))
    money = ["median", "p10", "min", "within_world_std"]
    print(summary.to_string(index=False, formatters={c: "{:,.0f}".format for c in money}))
    unstable = summary[summary["positive"].map(lambda s: s.split("/")[0] != s.split("/")[1])]
    if len(unstable):
        print("\n⚠ Sign is not stable in: " + ", ".join(unstable["scenario"]))


if __name__ == "__main__":
    main()
