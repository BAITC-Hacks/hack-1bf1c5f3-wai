"""Checks the public challenge contract without changing organizer code."""

import unittest

import pandas as pd

from agent import Agent
from make_submission import build_submission
from mock_environment import make_mock_env
from scoring_core import apply_filters


class AgentContractTests(unittest.TestCase):
    def test_pilots_and_final_campaigns_fit_resources(self):
        env, _ = make_mock_env(seed=42)
        campaigns = Agent().act(env)

        self.assertGreater(len(env.pilot_history), 0)
        self.assertLessEqual(len(env.pilot_history), 20)
        self.assertGreaterEqual(len(campaigns), 1)
        self.assertLessEqual(len(campaigns), 10)

        known_tariffs = set(env.tariffs["tariff_plan_code"])
        final_contacts = 0
        final_cost = 0.0
        for campaign in campaigns:
            self.assertIn(campaign["target_tariff"], known_tariffs)
            self.assertIn(campaign["channel"], env.channels)
            audience = apply_filters(env.customer_profile, pd.Series(campaign))
            self.assertGreater(len(audience), 0)
            self.assertLessEqual(len(audience), 5000)
            final_contacts += len(audience)
            final_cost += len(audience) * env.channels[campaign["channel"]]["cost_per_contact"]

        self.assertLessEqual(final_contacts, env.remaining_contacts)
        self.assertLessEqual(final_cost, env.remaining_budget)

    def test_submission_is_deterministic_for_seed_42(self):
        first = build_submission(Agent())
        second = build_submission(Agent())
        pd.testing.assert_frame_equal(first, second)


if __name__ == "__main__":
    unittest.main()
