"""Development-only adapters for borrowing teammate historical estimates."""

import sys

import numpy as np

from transition_prior import estimate_transitions, load_history


def configure(mode):
    research = sys.modules["candidate_research"]
    original = research.build_hypotheses

    def build(profile, tariffs, history_path=None, per_cell=3):
        baseline = original(profile, tariffs, history_path, per_cell=per_cell)
        estimates = estimate_transitions(load_history(history_path), tariffs)
        if estimates.empty:
            return baseline
        priors = {
            (row[0], row[1], row.segment): (float(row.effect_mean), float(row.effect_sd))
            for row in estimates[["from", "to", "segment", "effect_mean", "effect_sd"]].itertuples(index=False)
            if np.isfinite(row.effect_mean) and np.isfinite(row.effect_sd)
        }
        historical = research._historical_priors(history_path)
        if mode == "eb_sparse":
            return [research.Hypothesis(h.cell, h.target_tariff,
                        priors.get((h.cell.current_tariff, h.target_tariff, h.cell.arpu_segment),
                                   (h.prior_mean, .15))[0]
                        if historical.get((h.cell.current_tariff, h.target_tariff, h.cell.arpu_segment), (0., 0))[1] < 5
                        else h.prior_mean, .15) for h in baseline]
        old_by_cell = {}
        for h in baseline:
            old_by_cell.setdefault(h.cell.key, []).append(h)
        codes = list(tariffs.tariff_plan_code.astype(str))
        hypotheses = []
        for cell in research.build_cells(profile):
            old = old_by_cell.get(cell.key, [])
            options = [(priors[(cell.current_tariff, t, cell.arpu_segment)][0], t)
                       for t in codes if t != cell.current_tariff
                       and (cell.current_tariff, t, cell.arpu_segment) in priors]
            if not options:
                hypotheses.extend(old)
                continue
            targets = [t for _, t in sorted(options, key=lambda x: x[0], reverse=True)[:per_cell]]
            if mode == "eb_union":
                targets = list(dict.fromkeys([h.target_tariff for h in old] + targets))
            for target in targets:
                mean, sd = priors.get((cell.current_tariff, target, cell.arpu_segment), (0., .15))
                if mode == "eb_rank":
                    effect, count = historical.get((cell.current_tariff, target, cell.arpu_segment), (0., 0))
                    mean = effect * count / (count + 5)
                hypotheses.append(research.Hypothesis(cell, target, mean,
                    max(.15, sd) if mode == "eb_uncertain" else .15))
        return hypotheses

    sys.modules["agent"].build_hypotheses = build
