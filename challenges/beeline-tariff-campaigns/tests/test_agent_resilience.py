"""Decision failures must preserve completed pilots and a legal final plan."""

import unittest
from unittest.mock import patch

import pandas as pd

import agent
from campaign_planner import Belief, fallback_campaigns
from candidate_research import Cell, Hypothesis, build_hypotheses
from mock_environment import make_mock_env
from scoring_core import apply_filters


class AgentResilienceTests(unittest.TestCase):
    def assert_legal(self, env, campaigns):
        self.assertGreaterEqual(len(campaigns), 1)
        self.assertLessEqual(len(campaigns), 10)
        contacts, cost = 0, 0.0
        for campaign in campaigns:
            audience = apply_filters(env.customer_profile, pd.Series(campaign))
            self.assertGreater(len(audience), 0)
            self.assertLessEqual(len(audience), 5000)
            contacts += len(audience)
            cost += len(audience) * env.channels[campaign["channel"]]["cost_per_contact"]
        self.assertLessEqual(contacts, env.remaining_contacts)
        self.assertLessEqual(cost, env.remaining_budget)

    def test_selection_failure_preserves_completed_pilots(self):
        env, _ = make_mock_env(seed=42)
        select = agent.next_pilot

        def fail_after_three(*args, **kwargs):
            if len(env.pilot_history) >= 3:
                raise RuntimeError("Injected selection failure")
            return select(*args, **kwargs)

        with patch.object(agent, "next_pilot", side_effect=fail_after_three):
            campaigns = agent.Agent().act(env)
        self.assertEqual(len(env.pilot_history), 3)
        self.assert_legal(env, campaigns)

    def test_missing_feedback_preserves_completed_pilots(self):
        env, _ = make_mock_env(seed=42)
        run_pilot = env.run_pilot

        def malformed_result(*args, **kwargs):
            result = run_pilot(*args, **kwargs)
            if len(env.pilot_history) == 4:
                result = dict(result)
                result.pop("observed_lift_ratio")
            return result

        env.run_pilot = malformed_result
        campaigns = agent.Agent().act(env)
        self.assertGreaterEqual(len(env.pilot_history), 4)
        self.assert_legal(env, campaigns)

    def test_planner_failure_returns_legal_fallback(self):
        env, _ = make_mock_env(seed=42)
        with patch.object(agent, "plan_campaigns", side_effect=RuntimeError("Injected planner failure")):
            campaigns = agent.Agent().act(env)
        self.assertGreater(len(env.pilot_history), 0)
        self.assert_legal(env, campaigns)

    def test_all_negative_fallback_minimizes_estimated_loss(self):
        profile = pd.DataFrame({
            "ID_NUMBER": [1, 2, 3], "current_tariff": ["a"] * 3,
            "arpu_segment": ["HIGH"] * 3, "data_segment": ["LITE", "HEAVY", "HEAVY"],
            "call_segment": ["LOW"] * 3, "predicted_arpu": [100., 1000., 1000.],
        })
        belief = Belief(Hypothesis(Cell("a", "HIGH", 3, 2100.), "b", -.3, .15))
        channels = {"push": {"cost_per_contact": 0, "conversion_multiplier": .5}}
        campaigns = fallback_campaigns([belief], channels, 10, profile=profile)
        self.assertEqual(len(campaigns), 1)
        audience = apply_filters(profile, pd.Series(campaigns[0]))
        self.assertEqual(audience["ID_NUMBER"].tolist(), [1])

    def test_no_history_uses_nearest_prices_not_tariff_names(self):
        profile = pd.DataFrame({"ID_NUMBER": [1], "current_tariff": ["tariff_1"],
                                "arpu_segment": ["MID"], "predicted_arpu": [2000.]})
        tariffs = pd.DataFrame({"tariff_plan_code": ["tariff_1", "tariff_2", "tariff_9", "tariff_10"],
                                "price_tariff": [1000., 1200., 5000., 1300.]})
        hypotheses = build_hypotheses(profile, tariffs, per_cell=2)
        self.assertEqual([h.target_tariff for h in hypotheses], ["tariff_2", "tariff_10"])


if __name__ == "__main__":
    unittest.main()
