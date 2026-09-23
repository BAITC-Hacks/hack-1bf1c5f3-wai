"""Check interaction of consistent planner caution and confidence-aware pilots."""
import sys
import json
from pathlib import Path
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.pilot_compare import PilotAgent
from campaign_planner import Belief
from candidate_research import build_hypotheses
from experiments.planner_shadow import plan_campaigns
from local_eval import evaluate_agent

class Joint(PilotAgent):
    channel_pairs = False
    def act(self, env):
        beliefs = [Belief(h) for h in build_hypotheses(env.customer_profile, env.tariffs, Path('data/change_tariff.csv'))]
        self._explore(env, beliefs)
        plan = plan_campaigns(beliefs, env.customer_profile, env.channels,
            env.remaining_budget, env.remaining_contacts, caution_push=True, search=False)
        if self.channel_pairs:
            from experiments.planner_channel_pairs import improve_channels
            plan = improve_channels(plan, beliefs, env.customer_profile, env.channels, env.remaining_budget)
        return plan

class Pairs(Joint):
    channel_pairs = True

if __name__ == '__main__':
    start, stop = map(int, sys.argv[1:3])
    pairs = '--pairs' in sys.argv
    records = []
    for seed in range(start, stop):
        row = {'seed': seed}
        modes = [('joint',Joint),('pairs',Pairs)] if pairs else [('confirm_only', PilotAgent), ('joint', Joint)]
        for name, cls in modes:
            t = time.monotonic()
            r = evaluate_agent(cls('confirm_winners'), seed=seed, verbose=False)
            row[name] = {key: r[key] for key in ['net_arpu_gain', 'total_contacts', 'total_cost', 'n_pilots']}
            row[name]['seconds'] = time.monotonic() - t
        records.append(row)
        print(json.dumps(row), flush=True)
    suffix = '_pairs' if pairs else ''
    Path(f'experiments/planner_joint{suffix}_{start}_{stop}.json').write_text(json.dumps(records, indent=2))
