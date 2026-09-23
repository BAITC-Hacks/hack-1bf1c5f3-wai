"""Bounded channel reassignment on already selected campaign audiences."""
import numpy as np
from campaign_planner import CAUTION

def improve_channels(campaigns, beliefs, profile, channels, budget):
    if not campaigns:
        return campaigns
    profile = profile.reset_index(drop=True)
    arpu = profile.predicted_arpu.fillna(0).to_numpy(float)
    channel_names = list(channels)
    specs = [channels[name] for name in channel_names]
    n_campaigns, n_channels = len(campaigns), len(specs)
    values = np.zeros((n_campaigns, n_channels, len(profile)))
    costs = np.zeros((n_campaigns, n_channels))
    lookup = {(b.hypothesis.cell.key, b.hypothesis.target_tariff): b for b in beliefs}
    for i, campaign in enumerate(campaigns):
        mask = np.ones(len(profile), dtype=bool)
        for key in ('arpu_segment','current_tariff','data_segment','call_segment'):
            value = campaign.get('filter_' + key)
            if value is not None:
                mask &= profile[key].astype(str).isin(value.split(';')).to_numpy()
        ratio = np.zeros(len(profile))
        for key, rows in profile[mask].groupby(['current_tariff','arpu_segment']).groups.items():
            b = lookup.get((key, campaign['target_tariff']))
            if b is not None:
                ratio[np.asarray(rows)] = b.mean - CAUTION * b.sd
        for j, spec in enumerate(specs):
            values[i,j] = ratio * arpu * spec['conversion_multiplier']
            costs[i,j] = mask.sum() * spec['cost_per_contact']
    selected = np.array([channel_names.index(c['channel']) for c in campaigns])
    indices = np.arange(n_campaigns)
    spent = costs[indices,selected].sum()
    score = np.max(values[indices,selected], axis=0).sum() - spent
    for _ in range(2):
        changed = False
        for a in range(n_campaigns):
            for b in range(a, n_campaigns):
                others = indices[(indices != a) & (indices != b)]
                base = np.max(values[others, selected[others]],axis=0) if len(others) else np.zeros(len(profile))
                remaining_spend = spent - costs[a, selected[a]] - (costs[b, selected[b]] if b != a else 0)
                best = None
                for x in range(n_channels):
                    for y in range(n_channels) if b != a else [x]:
                        new_spent = remaining_spend + costs[a,x] + (costs[b,y] if b != a else 0)
                        if new_spent > budget:
                            continue
                        new_score = np.maximum(base, np.maximum(values[a,x], values[b,y])).sum() - new_spent
                        if new_score > score + 1e-6:
                            best = (x,y,new_spent,new_score)
                            score = new_score
                if best:
                    selected[a],selected[b],spent,score = best
                    changed = True
        if not changed:
            break
    return [{**c, 'channel':channel_names[selected[i]], 'campaign_name':f'optimized_{i+1}_{channel_names[selected[i]]}'} for i,c in enumerate(campaigns)]
