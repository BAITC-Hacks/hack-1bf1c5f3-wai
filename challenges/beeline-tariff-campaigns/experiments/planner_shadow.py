"""Explore budget opportunity costs using public posterior beliefs only."""
import numpy as np
from experiments.planner_shadow_base import plan_campaigns as greedy, CAUTION


def expected_utility(campaigns, beliefs, profile, channels, caution_push=False):
    arpu = profile.predicted_arpu.fillna(0).to_numpy(float)
    current = np.zeros(len(profile))
    lookup = {(b.hypothesis.cell.key, b.hypothesis.target_tariff): b for b in beliefs}
    spent = 0.0
    for campaign in campaigns:
        spec = channels[campaign['channel']]
        cost = float(spec['cost_per_contact'])
        multiplier = float(spec['conversion_multiplier'])
        mask = np.ones(len(profile), dtype=bool)
        for name in ('arpu_segment', 'data_segment', 'call_segment', 'current_tariff'):
            value = campaign.get('filter_' + name)
            if value is not None:
                mask &= profile[name].astype(str).isin(value.split(';')).to_numpy()
        spent += int(mask.sum()) * cost
        for key, rows in profile[mask].groupby(['current_tariff', 'arpu_segment']).groups.items():
            belief = lookup.get((key, campaign['target_tariff']))
            if belief is not None:
                ratio = (belief.mean - (CAUTION * belief.sd if cost or caution_push else 0)) * multiplier
                rows = np.asarray(rows)
                current[rows] = np.maximum(current[rows], ratio * arpu[rows])
    return current.sum() - spent


def plan_campaigns(beliefs, profile, channels, budget, contacts, max_campaigns=10, caution_push=False, search=True):
    """Compare feasible portfolios at several prices for scarce budget.

    Shadow prices are chosen from posterior channel upgrade returns, so no
    scoring-model effects or evaluation outcomes enter candidate construction.
    """
    profile = profile.reset_index(drop=True)
    upgrades = []
    specs = sorted(channels.values(), key=lambda s: s['cost_per_contact'])
    for belief in beliefs:
        cell = belief.hypothesis.cell
        if cell.size <= 0:
            continue
        value = max(0, belief.mean - CAUTION * belief.sd) * cell.arpu_sum / cell.size
        for low, high in zip(specs, specs[1:]):
            delta_cost = high['cost_per_contact'] - low['cost_per_contact']
            if delta_cost > 0:
                upgrades.append(max(0, value * (high['conversion_multiplier'] - low['conversion_multiplier']) / delta_cost - 1))
    shadows = [0.0]
    if upgrades and search:
        shadows += list(np.quantile(upgrades, [0.5, 0.75, 0.9, 0.97]))
    best, best_score = [], -np.inf
    for shadow in sorted(set(shadows)):
        plan = greedy(beliefs, profile, channels, budget, contacts, max_campaigns, shadow=float(shadow), caution_push=caution_push)
        score = expected_utility(plan, beliefs, profile, channels, caution_push=caution_push)
        if score > best_score:
            best, best_score = plan, score
    return best
