"""Checks candidate generation: tariff groups, scoring and the shortlist."""

import unittest
from pathlib import Path

import pandas as pd

from candidate_research import TARGETS_PER_CELL, TOP_CANDIDATES, build_hypotheses, tariff_groups

ROOT = Path(__file__).resolve().parents[1]


class CandidateResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = pd.read_csv(ROOT / "customer_profile.csv")
        cls.tariffs = pd.read_csv(ROOT / "data" / "dict_tariff.csv")
        cls.shortlist = build_hypotheses(cls.profile, cls.tariffs, ROOT / "data" / "change_tariff.csv")

    def test_identical_tariffs_share_a_group(self):
        groups = tariff_groups(self.tariffs)
        self.assertEqual(groups["tariff_5"], ("tariff_5", "tariff_6", "tariff_7", "tariff_8"))
        self.assertEqual(groups["tariff_9"], ("tariff_9",))  # same price as tariff_16, other bundle

    def test_shortlist_is_ranked_by_score_and_bounded(self):
        self.assertTrue(15 <= len(self.shortlist) <= TOP_CANDIDATES <= 30)
        scores = [h.score for h in self.shortlist]
        self.assertEqual(scores, sorted(scores, reverse=True))
        per_cell = pd.Series([h.cell.key for h in self.shortlist]).value_counts()
        self.assertLessEqual(per_cell.max(), TARGETS_PER_CELL)

    def test_score_is_effect_times_audience_times_mean_arpu(self):
        for h in self.shortlist:
            expected = h.prior_mean * min(h.cell.size, 5000) * h.cell.arpu_sum / h.cell.size
            self.assertAlmostEqual(h.score, expected, places=6)
            self.assertNotIn(h.target_tariff, h.cell.current_tariffs)

    def test_filters_select_exactly_the_cell(self):
        for h in self.shortlist:
            filters = h.cell.filters()
            members = filters["filter_current_tariff"].split(";")
            audience = self.profile[
                self.profile["current_tariff"].isin(members)
                & (self.profile["arpu_segment"] == filters["filter_arpu_segment"])
            ]
            self.assertEqual(len(audience), h.cell.size)

    def test_without_history_still_returns_candidates(self):
        shortlist = build_hypotheses(self.profile, self.tariffs, None)
        self.assertEqual(len(shortlist), TOP_CANDIDATES)
        self.assertTrue(all(h.prior_mean == 0.0 for h in shortlist))


if __name__ == "__main__":
    unittest.main()
