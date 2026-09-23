"""Checks the empirical-Bayes transition prior on small synthetic histories."""

import unittest

import numpy as np
import pandas as pd

from transition_prior import MIN_EFFECT_SD, MIN_SUPPORT, estimate_transitions

TARIFFS = pd.DataFrame({
    "tariff_plan_code": ["t1", "t2", "t3", "t4"],
    "price_tariff": [1000.0, 2000.0, 3000.0, 4000.0],
})


def _events(pairs):
    rows = []
    rng = np.random.default_rng(0)
    for source, target, n, mean in pairs:
        for value in rng.normal(mean, 0.3, n):
            rows.append({"from": source, "to": target, "segment": "MID", "ratio": value})
    return pd.DataFrame(rows)


class TransitionPriorTests(unittest.TestCase):
    def setUp(self):
        self.events = _events([
            ("t1", "t2", 200, 0.10), ("t1", "t3", 200, 0.60), ("t2", "t3", 150, 0.45),
            ("t3", "t2", 150, -0.20), ("t2", "t4", 3, 2.00), ("t4", "t2", 80, -0.30),
        ])
        self.estimates = estimate_transitions(self.events, TARIFFS).set_index(["from", "to", "segment"])

    def test_covers_every_ordered_pair_including_unseen(self):
        self.assertEqual(len(self.estimates), 4 * 3)
        unseen = self.estimates.loc[("t3", "t4", "MID")]
        self.assertEqual(unseen["support"], 0)
        self.assertTrue(np.isfinite(unseen["change_mean"]))

    def test_well_supported_pair_stays_close_to_its_own_mean(self):
        row = self.estimates.loc[("t1", "t3", "MID")]
        self.assertGreater(row["shrink_weight"], 0.5)
        self.assertLess(abs(row["change_mean"] - row["raw_mean"]), abs(row["tariff_mean"] - row["raw_mean"]))

    def test_sparse_pair_falls_back_to_tariff_mean(self):
        row = self.estimates.loc[("t2", "t4", "MID")]
        self.assertLess(row["support"], MIN_SUPPORT)
        self.assertEqual(row["shrink_weight"], 0.0)
        self.assertAlmostEqual(row["change_mean"], row["tariff_mean"])

    def test_effect_prior_is_inflated_and_floored(self):
        self.assertTrue((self.estimates["effect_sd"] >= MIN_EFFECT_SD).all())
        self.assertTrue(((self.estimates["conversion"] > 0) & (self.estimates["conversion"] < 1)).all())

    def test_empty_history_returns_empty_frame(self):
        empty = pd.DataFrame(columns=["from", "to", "segment", "ratio"])
        self.assertTrue(estimate_transitions(empty, TARIFFS).empty)


if __name__ == "__main__":
    unittest.main()
