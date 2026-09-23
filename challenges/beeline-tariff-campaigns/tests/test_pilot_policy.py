"""Checks the adaptive two-round pilot policy on the mock environment."""

import unittest
from pathlib import Path

from campaign_planner import Belief
from candidate_research import build_hypotheses
from mock_environment import make_mock_env
from pilot_policy import (
    MAX_PILOT_CUSTOMERS,
    MAX_PILOTS_PER_CANDIDATE,
    ROUND1_CANDIDATES,
    ROUND1_SIZE,
    ROUND2_MIN_SIZE,
    cut_outsiders,
    run_pilots,
)

ROOT = Path(__file__).resolve().parents[1]


class PilotPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env, cls.internals = make_mock_env(seed=7)
        hypotheses = build_hypotheses(cls.env.customer_profile, cls.env.tariffs, ROOT / "data" / "change_tariff.csv")
        cls.beliefs = [Belief(h) for h in hypotheses]
        run_pilots(cls.env, cls.beliefs)
        cls.history = cls.env.pilot_history

    def test_uses_every_pilot_and_never_calls(self):
        self.assertEqual(len(self.history), 20)
        self.assertTrue({p["channel"] for p in self.history} <= {"sms", "push"})

    def test_round_one_is_medium_pilots_on_top_candidates(self):
        round1 = self.history[:ROUND1_CANDIDATES]
        self.assertTrue(all(p["n_customers"] <= ROUND1_SIZE for p in round1))
        expected = [b.hypothesis.target_tariff for b in self.beliefs[:ROUND1_CANDIDATES]]
        self.assertEqual([p["target_tariff"] for p in round1], expected)

    def test_round_two_uses_large_pilots_and_caps_repeats(self):
        profile = self.env.customer_profile
        campaigns = self.internals.executed_pilot_campaigns()
        for pilot, campaign in list(zip(self.history, campaigns))[ROUND1_CANDIDATES:]:
            cell_size = int((
                profile["current_tariff"].isin(campaign["filter_current_tariff"].split(";"))
                & (profile["arpu_segment"] == campaign["filter_arpu_segment"])
            ).sum())
            self.assertLessEqual(pilot["n_customers"], MAX_PILOT_CUSTOMERS)
            self.assertGreaterEqual(pilot["n_customers"], min(ROUND2_MIN_SIZE, cell_size))
        self.assertTrue(all(b.pilots <= MAX_PILOTS_PER_CANDIDATE for b in self.beliefs))

    def test_clear_negative_candidate_is_cut(self):
        belief = Belief(self.beliefs[0].hypothesis)
        belief.update(observed_ratio=-0.5, multiplier=0.65, n_customers=200)
        cut_outsiders([belief])
        self.assertFalse(belief.pilotable)


if __name__ == "__main__":
    unittest.main()
