"""Smoke test: the stress runner builds every scenario and scores the agent."""

import os
import unittest
from pathlib import Path

import numpy as np

import stress_eval
from agent import Agent

ROOT = Path(__file__).resolve().parents[1]


class StressEvalTests(unittest.TestCase):
    def test_one_world_of_the_hostile_and_noisy_scenarios(self):
        cwd = os.getcwd()
        os.chdir(ROOT)  # the runner reads data relative to the challenge folder
        try:
            runs = stress_eval.run_stress(Agent, ["hostile", "noisy_pilots"], worlds=1, seeds=1)
        finally:
            os.chdir(cwd)
        self.assertEqual(list(runs["scenario"]), ["hostile", "noisy_pilots"])
        self.assertTrue(np.isfinite(runs["net"]).all())
        self.assertTrue((runs["pilots"] == 20).all())
        self.assertFalse(runs["crashed"].any())

    def test_every_scenario_changes_the_effects_or_the_pilots(self):
        import pandas as pd
        from mock_environment import _mock_impact_model
        base = _mock_impact_model(pd.read_csv(ROOT / "data" / "change_tariff.csv"))
        for name, (transform, noisy, hide_history) in stress_eval.SCENARIOS.items():
            model = transform(base, np.random.default_rng(0))
            changed = not np.allclose(model["arpu_change_pct"], base["arpu_change_pct"])
            self.assertTrue(changed or noisy or hide_history, name)


if __name__ == "__main__":
    unittest.main()
