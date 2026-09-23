"""Coverage, adaptation and recovery checks for the borrowed history model."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

# Frozen research snapshots use the original flat module import names.
# Keep those helpers in experiments while preserving the snapshot source.
sys.path.append(str(Path(__file__).resolve().parents[1] / "experiments"))

from experiments.integration_rank_snapshot import candidate_research as research
from agent import Agent
from experiments.robustness_public_contract import PublicStub


class HistoricalCandidateTests(unittest.TestCase):
    def setUp(self):
        self.profile = pd.DataFrame({
            "ID_NUMBER": [1, 2], "current_tariff": ["a", "a"],
            "arpu_segment": ["MID", "HIGH"], "predicted_arpu": [2000., 8000.],
        })
        self.tariffs = pd.DataFrame({
            "tariff_plan_code": ["a", "b", "c"], "price_tariff": [1000., 2000., 3000.],
        })

    def test_unseen_target_can_rank_first_without_excluding_other_cells(self):
        estimates = pd.DataFrame({
            "from": ["a", "a"], "to": ["b", "c"], "segment": ["MID", "MID"],
            "effect_mean": [.1, .3],
        })
        with patch.object(research, "estimate_transitions", return_value=estimates):
            candidates = research.build_hypotheses(self.profile, self.tariffs, per_cell=1)
        self.assertEqual([(h.cell.arpu_segment, h.target_tariff) for h in candidates],
                         [("HIGH", "b"), ("MID", "c")])
        self.assertTrue(all(h.prior_sd == .15 for h in candidates))
        self.assertEqual(candidates[1].prior_mean, 0.0)  # extrapolation is not evidence

    def test_ranking_does_not_replace_supported_historical_mean(self):
        estimates = pd.DataFrame({
            "from": ["a", "a"], "to": ["b", "c"], "segment": ["MID", "MID"],
            "effect_mean": [.1, .9],
        })
        historical = {("a", "b", "MID"): (.2, 20), ("a", "c", "MID"): (.1, 10)}
        with patch.object(research, "estimate_transitions", return_value=estimates), \
                patch.object(research, "_historical_priors", return_value=historical):
            candidates = research.build_hypotheses(self.profile, self.tariffs, per_cell=1)
        mid = next(h for h in candidates if h.cell.arpu_segment == "MID")
        self.assertEqual(mid.target_tariff, "c")
        self.assertAlmostEqual(mid.prior_mean, .1 * 10 / 15)

    def test_numerical_failure_and_nonfinite_output_preserve_baseline(self):
        expected = research._baseline_hypotheses(self.profile, self.tariffs)
        with patch.object(research, "estimate_transitions", side_effect=np.linalg.LinAlgError("injected")):
            self.assertEqual(research.build_hypotheses(self.profile, self.tariffs), expected)
        bad = pd.DataFrame({"from": ["a"], "to": ["c"], "segment": ["MID"], "effect_mean": [np.nan]})
        with patch.object(research, "estimate_transitions", return_value=bad):
            self.assertEqual(research.build_hypotheses(self.profile, self.tariffs), expected)

    def test_real_candidate_pool_covers_all_cells_without_global_cutoff(self):
        env = PublicStub()
        history = Path(__file__).resolve().parents[1] / "data/change_tariff.csv"
        candidates = research.build_hypotheses(env.customer_profile, env.tariffs, history)
        expected = {c.key for c in research.build_cells(env.customer_profile)}
        self.assertEqual({h.cell.key for h in candidates}, expected)
        self.assertGreater(len(candidates), 30)
        self.assertEqual(len(candidates), 3 * len(expected))
        self.assertTrue(all(h.target_tariff != h.cell.current_tariff for h in candidates))

    def test_final_plan_still_responds_to_pilots(self):
        positive = PublicStub(response=.3)
        negative = PublicStub(response=-.3)
        with patch("agent.build_hypotheses", research.build_hypotheses):
            first = Agent().act(positive)
            second = Agent().act(negative)
        self.assertGreater(len(positive.pilot_history), 0)
        self.assertGreater(len(negative.pilot_history), 0)
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
