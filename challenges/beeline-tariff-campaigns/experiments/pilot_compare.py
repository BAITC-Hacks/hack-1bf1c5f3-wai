"""Pilot policy experiment using frozen baseline planning and official scoring.

Run from challenge directory: .venv/Scripts/python.exe -X utf8 experiments/pilot_compare.py
Only development seeds select a policy; holdout is evaluated separately.
"""
from pathlib import Path
import sys
import json
from collections import defaultdict
from math import sqrt
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent / "pilot_snapshot"))
import agent
agent.__file__ = str(ROOT / "agent.py")
from campaign_planner import _normal_cdf, _normal_pdf, next_pilot
import campaign_planner
from local_eval import evaluate_agent


class PilotAgent(agent.Agent):
    def __init__(self, mode):
        self.mode = mode
        self.samples = []

    def _explore(self, env, beliefs):
        while env.pilots_left > 0:
            if self.mode == "fixed100":
                choice = next_pilot(beliefs, 0.65)
                if choice is None:
                    break
                choice = (choice, "sms", min(100, choice.hypothesis.cell.size))
            elif self.mode in ("confirm_winners", "confirm_uniform"):
                choice = self.confirm_choice(beliefs)
            else:
                choice = self.choose(env, beliefs)
                if choice is None:
                    break
            belief, channel, n = choice
            spec = env.channels[channel]
            n = min(n, env.remaining_contacts)
            if spec["cost_per_contact"]:
                n = min(n, int(env.remaining_budget // spec["cost_per_contact"]))
            if n < 10:
                break
            try:
                result = env.run_pilot(target_tariff=belief.hypothesis.target_tariff,
                    channel=channel, n_customers=n, **belief.hypothesis.cell.filters())
            except (RuntimeError, ValueError, TypeError):
                belief.pilotable = False
                continue
            belief.update(float(result["observed_lift_ratio"]),
                float(spec["conversion_multiplier"]), int(result["n_customers"]))
            self.samples.append((channel, n))

    @staticmethod
    def confirm_choice(beliefs):
        cells = defaultdict(list)
        for belief in beliefs:
            cells[belief.hypothesis.cell.key].append(belief)
        best, best_value = None, -float("inf")
        for group in cells.values():
            cell = group[0].hypothesis.cell
            n = min(200, cell.size)
            if n < 10:
                continue
            for belief in group:
                if not belief.pilotable:
                    continue
                alternative = max([0.] + [b.mean - .5 * b.sd for b in group if b is not belief])
                variance = 1 / (belief.precision + belief.observation_precision(.65, n))
                sigma = sqrt(max(belief.sd ** 2 - variance, 0))
                updated_mean = belief.mean - .5 * sqrt(variance)
                z = (updated_mean - alternative) / sigma
                expected_best = alternative + sigma * (z * _normal_cdf(z) + _normal_pdf(z))
                current_best = max(alternative, belief.mean - .5 * belief.sd)
                value = (expected_best - current_best) * cell.arpu_sum
                if value > best_value:
                    best_value, best = value, (belief, "sms", n)
        return best

    def choose(self, env, beliefs):
        cells = defaultdict(list)
        for belief in beliefs:
            cells[belief.hypothesis.cell.key].append(belief)
        # The last affordable contact estimates what a pilot displaces.
        opportunities = sorted([
            (max(0, max(b.mean for b in group)) * .65 * group[0].hypothesis.cell.arpu_sum
             / group[0].hypothesis.cell.size - 4, group[0].hypothesis.cell.size)
            for group in cells.values()], reverse=True)
        used = 0
        contact_shadow = 0
        for value, size in opportunities:
            used += size
            contact_shadow = max(0, value)
            if used >= env.remaining_contacts:
                break
        # Marginal channel upgrade value per budget unit, estimated from beliefs.
        upgrades = sorted([
            (max(0, max(b.mean for b in group)) * .20 * group[0].hypothesis.cell.arpu_sum
             / group[0].hypothesis.cell.size / 18 - 1, 18 * group[0].hypothesis.cell.size)
            for group in cells.values()], reverse=True)
        used_budget = 0
        budget_shadow = 0
        discretionary = max(0, env.remaining_budget - env.remaining_contacts * 4)
        for value, spend in upgrades:
            used_budget += spend
            budget_shadow = max(0, value)
            if used_budget >= discretionary:
                break
        best, best_value = None, float("-inf")
        channel_names = ("sms",) if self.mode == "adaptive_sms" else ("push", "sms", "digital_ads")
        for group in cells.values():
            cell = group[0].hypothesis.cell
            for belief in group:
                if not belief.pilotable:
                    continue
                alternative = max([0.] + [other.mean for other in group if other is not belief])
                for channel in channel_names:
                    spec = env.channels[channel]
                    multiplier = spec["conversion_multiplier"]
                    cost = spec["cost_per_contact"]
                    for n in sorted({min(n, cell.size) for n in (25, 50, 100, 150, 200)}):
                        if n < 10 or n > env.remaining_contacts or n * cost > env.remaining_budget:
                            continue
                        posterior_var = 1 / (belief.precision + belief.observation_precision(multiplier, n))
                        sigma = sqrt(max(belief.sd ** 2 - posterior_var, 0))
                        if sigma <= 0:
                            continue
                        z = -abs(belief.mean - alternative) / sigma
                        knowledge = sigma * (z * _normal_cdf(z) + _normal_pdf(z)) * cell.arpu_sum * .65
                        utility = knowledge - n * (contact_shadow + cost * (1 + budget_shadow))
                        if utility > best_value:
                            best_value, best = utility, (belief, channel, n)
        return best


if __name__ == "__main__":
    modes = sys.argv[1].split(",") if len(sys.argv) > 1 else ["baseline", "fixed100", "adaptive_sms", "adaptive_channels"]
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    stop = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    rows = []
    for seed in range(start, stop):
        for mode in modes:
            # Private frozen planner instance; no production source changes.
            if mode == "confirm_uniform":
                source = (ROOT / "experiments" / "pilot_snapshot" / "campaign_planner.py").read_text(encoding="utf-8")
                source = source.replace("(CAUTION * belief.sd if cost > 0 else 0.0)", "(CAUTION * belief.sd)")
                exec(compile(source, campaign_planner.__file__, "exec"), campaign_planner.__dict__)
                agent.plan_campaigns = campaign_planner.plan_campaigns
            else:
                source = (ROOT / "experiments" / "pilot_snapshot" / "campaign_planner.py").read_text(encoding="utf-8")
                exec(compile(source, campaign_planner.__file__, "exec"), campaign_planner.__dict__)
                agent.plan_campaigns = campaign_planner.plan_campaigns
            policy = agent.Agent() if mode == "baseline" else PilotAgent(mode)
            began = time.perf_counter()
            result = evaluate_agent(policy, seed=seed, verbose=False)
            row = {"mode": mode, "seed": seed, "net": result["net_arpu_gain"],
                "seconds": time.perf_counter() - began, "pilots": result["n_pilots"],
                "samples": getattr(policy, "samples", [])}
            rows.append(row)
            print(json.dumps(row), flush=True)
    path = ROOT / "experiments" / f"pilot_results_{start}_{stop}_{'_'.join(modes)}.json"
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for mode in modes:
        values = [r["net"] for r in rows if r["mode"] == mode]
        print(mode, "mean", sum(values) / len(values), "min", min(values), flush=True)
