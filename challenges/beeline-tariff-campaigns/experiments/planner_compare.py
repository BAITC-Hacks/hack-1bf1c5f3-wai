"""Paired official-evaluator comparison, with the baseline pilot policy fixed."""
import argparse
import json
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'pilot_snapshot'))
import agent
agent.__file__ = str(Path(__file__).resolve().parents[1] / 'agent.py')
from agent import Agent as Baseline
from candidate_research import build_hypotheses
from campaign_planner import Belief
from local_eval import evaluate_agent
from experiments.planner_shadow import plan_campaigns


class Variant(Baseline):
    caution_push = False
    search = True
    def act(self, env):
        beliefs = [Belief(h) for h in build_hypotheses(env.customer_profile, env.tariffs, Path('data/change_tariff.csv'))]
        self._explore(env, beliefs)
        return plan_campaigns(beliefs, env.customer_profile, env.channels, env.remaining_budget, env.remaining_contacts, caution_push=self.caution_push, search=self.search)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--stop', type=int, default=10)
    parser.add_argument('--caution-push', action='store_true')
    parser.add_argument('--no-search', action='store_true')
    args = parser.parse_args()
    Variant.caution_push = args.caution_push
    Variant.search = not args.no_search
    records = []
    for seed in range(args.start, args.stop):
        row = {'seed': seed}
        for label, cls in [('baseline', Baseline), ('shadow', Variant)]:
            start = time.monotonic()
            result = evaluate_agent(cls(), seed=seed, verbose=False)
            row[label] = {key: result[key] for key in ['net_arpu_gain', 'total_cost', 'total_contacts', 'unique_customers_targeted', 'n_pilots']}
            row[label]['seconds'] = time.monotonic() - start
        print(json.dumps(row), flush=True)
        records.append(row)
    suffix = '_consistent' if args.caution_push else ''
    suffix += '_nosearch' if args.no_search else ''
    Path(f'experiments/planner_comparison{suffix}_{args.start}_{args.stop}.json').write_text(json.dumps(records, indent=2))
