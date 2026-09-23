"""Checks the robustness layer: probability-based decisions and the conservative plan."""

import unittest

import pandas as pd

from agent import Agent
from campaign_planner import (
    FALLBACK_MIN_PROB,
    MIN_PROB_PAID,
    Belief,
    calibrate_priors,
    plan_campaigns,
    robust_plan,
)
from candidate_research import Cell, Hypothesis
from mock_environment import make_mock_env
from scoring_core import CHANNELS, apply_filters


def _profile():
    rows = []
    for i in range(900):
        rows.append({
            "ID_NUMBER": i,
            "current_tariff": ["tariff_1", "tariff_2", "tariff_3"][i % 3],
            "arpu_segment": "MID",
            "data_segment": ["NON_USER", "LITE", "HEAVY"][(i // 3) % 3],
            "call_segment": ["LOW", "MEDIUM", "HIGH"][(i // 9) % 3],
            "predicted_arpu": 3000.0 + 10 * (i % 40),
        })
    return pd.DataFrame(rows)


def _belief(profile, tariff, mean, sd, target="tariff_8"):
    audience = profile[profile["current_tariff"] == tariff]
    cell = Cell((tariff,), "MID", len(audience), float(audience["predicted_arpu"].sum()))
    return Belief(Hypothesis(cell, target, mean, sd))


class BeliefGuardTests(unittest.TestCase):
    def setUp(self):
        self.profile = _profile()

    def test_prior_conflict_lets_pilots_dominate(self):
        guarded = _belief(self.profile, "tariff_1", 0.40, 0.05)
        for _ in range(2):
            guarded.update(observed_ratio=-0.10, multiplier=0.65, n_customers=200)
        self.assertTrue(guarded.prior_conflict)
        # without the guard the posterior would stay near the (wrong) prior
        pilot_only = -0.10 / 0.65
        plain_precision = 1 / 0.05 ** 2 + 2 * 0.65 ** 2 * 200 / 0.804 ** 2
        plain_mean = (0.40 / 0.05 ** 2 + 2 * 0.65 ** 2 * 200 / 0.804 ** 2 * pilot_only) / plain_precision
        self.assertLess(abs(guarded.mean - pilot_only), abs(plain_mean - pilot_only))

    def test_contradicting_pilots_widen_the_posterior(self):
        consistent = _belief(self.profile, "tariff_1", 0.0, 0.15)
        contradicting = _belief(self.profile, "tariff_1", 0.0, 0.15)
        for ratio in (0.10, 0.12):
            consistent.update(ratio, 0.65, 200)
        for ratio in (0.60, -0.40):
            contradicting.update(ratio, 0.65, 200)
        self.assertFalse(consistent.contradicted)
        self.assertTrue(contradicting.contradicted)
        self.assertGreater(contradicting.sd, consistent.sd)

    def test_normal_pilots_do_not_trip_the_guards(self):
        belief = _belief(self.profile, "tariff_1", 0.20, 0.15)
        for ratio in (0.12, 0.15, 0.10):
            belief.update(ratio, 0.65, 200)
        self.assertFalse(belief.prior_conflict)
        self.assertFalse(belief.contradicted)


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        profile = _profile()
        self.beliefs = [_belief(profile, "tariff_1", 0.10 + 0.05 * k, 0.15, target=f"tariff_{8 + k}")
                        for k in range(6)]
        self.unpiloted = _belief(profile, "tariff_2", 0.30, 0.15)

    def test_history_pointing_the_wrong_way_pulls_unpiloted_priors_down(self):
        for belief in self.beliefs:
            belief.update(-0.6 * belief.hypothesis.prior_mean * 0.65, 0.65, 200)
        calibration = calibrate_priors(self.beliefs + [self.unpiloted])
        self.assertLess(calibration.scale, 0)
        self.assertLess(self.unpiloted.prior_mean, 0)
        self.assertLess(self.unpiloted.prob_positive, 0.5)

    def test_history_that_holds_is_left_alone(self):
        for belief in self.beliefs:
            belief.update(belief.hypothesis.prior_mean * 0.65, 0.65, 200)
        calibration = calibrate_priors(self.beliefs + [self.unpiloted])
        self.assertAlmostEqual(calibration.scale, 1.0, delta=0.15)
        self.assertAlmostEqual(self.unpiloted.prior_mean, 0.30, delta=0.05)

    def test_too_few_pilots_change_nothing(self):
        self.beliefs[0].update(-0.5, 0.65, 200)
        self.assertIsNone(calibrate_priors(self.beliefs + [self.unpiloted]))
        self.assertEqual(self.unpiloted.prior_mean, 0.30)


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.profile = _profile()

    def _channels(self, campaigns):
        return {c["channel"] for c in campaigns}

    def test_paid_channel_requires_probability_of_paying_off(self):
        # expected value of a call is positive, but it is far from certain
        risky = _belief(self.profile, "tariff_1", 0.30, 0.25)
        audience = apply_filters(self.profile, pd.Series(risky.hypothesis.cell.filters()))
        break_even = 160 * len(audience) / (1.20 * audience["predicted_arpu"].sum())
        self.assertGreater(risky.mean, break_even)
        self.assertLess(risky.prob_above(break_even), MIN_PROB_PAID)
        campaigns = plan_campaigns([risky], self.profile, CHANNELS, 100_000, 15_000)
        self.assertNotIn("call", self._channels(campaigns))

    def test_contradictory_pilots_switch_to_conservative_push_plan(self):
        beliefs = [_belief(self.profile, t, 0.2, 0.15) for t in ("tariff_1", "tariff_2", "tariff_3")]
        for belief in beliefs[:2]:
            for ratio in (0.90, -0.50):  # pilots that cannot both be right
                belief.update(ratio, 0.65, 200)
        for ratio in (0.30, 0.32):
            beliefs[2].update(ratio, 0.65, 200)
        campaigns, reason = robust_plan(beliefs, self.profile, CHANNELS, 100_000, 15_000)
        self.assertTrue(reason.startswith("conservative"), reason)
        self.assertEqual(self._channels(campaigns), {"push"})
        chosen = {c["filter_current_tariff"] for c in campaigns}
        self.assertEqual(chosen, {"tariff_3"})  # only the cell that is surely positive
        self.assertGreaterEqual(beliefs[2].prob_positive, FALLBACK_MIN_PROB)

    def test_clean_evidence_keeps_the_main_plan(self):
        beliefs = [_belief(self.profile, t, 0.3, 0.05) for t in ("tariff_1", "tariff_2")]
        campaigns, reason = robust_plan(beliefs, self.profile, CHANNELS, 100_000, 15_000)
        self.assertEqual(reason, "main")
        self.assertTrue(campaigns)


class _ContradictingPilots:
    """Mock environment whose pilots alternate between wild highs and lows."""

    def __init__(self, env):
        self._env = env
        self._flip = 1

    def __getattr__(self, name):
        return getattr(self._env, name)

    def run_pilot(self, *args, **kwargs):
        result = dict(self._env.run_pilot(*args, **kwargs))
        self._flip = -self._flip
        result["observed_lift_ratio"] = result["observed_lift_ratio"] + self._flip * 0.8
        return result


class AgentRobustnessTests(unittest.TestCase):
    def test_agent_falls_back_to_push_when_pilots_contradict(self):
        env, _ = make_mock_env(seed=3)
        agent = Agent()
        campaigns = agent.act(_ContradictingPilots(env))
        self.assertEqual(len(env.pilot_history), 20)
        self.assertTrue(agent.decision.startswith("conservative"), agent.decision)
        self.assertTrue(campaigns)
        self.assertEqual({c["channel"] for c in campaigns}, {"push"})


if __name__ == "__main__":
    unittest.main()
