"""Regression tests for defects found in the Phase 1 audit."""

import unittest

from cwm_multidc.profile_shifting import shift_profile, truncate_profile
from cwm_multidc.wan_model import evaluate_wan_transfer, integrate_piecewise_carbon_intensity


class TestAuditFixes(unittest.TestCase):
    def test_ci_window_past_profile_end_raises(self):
        # Previously returned 50.0 (uncovered half counted as CI = 0).
        with self.assertRaises(ValueError):
            integrate_piecewise_carbon_intensity(0, 200, [0, 100], [100.0])

    def test_ci_window_before_profile_start_raises(self):
        with self.assertRaises(ValueError):
            integrate_piecewise_carbon_intensity(5, 20, [10, 100], [100.0])

    def test_ci_instant_on_boundary_uses_left_closed_interval(self):
        # [0,100) -> 10, [100,200) -> 999: t = 100 belongs to the second interval.
        self.assertEqual(integrate_piecewise_carbon_intensity(100, 100, [0, 100, 200], [10.0, 999.0]), 999.0)
        self.assertEqual(integrate_piecewise_carbon_intensity(200, 200, [0, 100, 200], [10.0, 999.0]), 999.0)

    def test_cross_dc_without_ci_raises(self):
        with self.assertRaises(ValueError):
            evaluate_wan_transfer("A", "B", 1000.0)

    def test_zero_data_cross_dc_not_flagged_same_dc(self):
        r = evaluate_wan_transfer("A", "B", 0.0)
        self.assertFalse(r.is_same_dc)
        self.assertEqual(r.network_emissions_gco2, 0.0)

    def test_truncate_profile(self):
        p = {"horizon": 90, "number_of_intervals": 3, "intervals": [0, 30, 60, 90], "budgets": [1, 2, 3]}
        self.assertEqual(truncate_profile(p, 45)["intervals"], [0, 30, 45])
        self.assertEqual(truncate_profile(p, 45)["budgets"], [1, 2])
        # exactly on a boundary: interval [30,60) is dropped entirely
        self.assertEqual(truncate_profile(p, 30), {"horizon": 30, "number_of_intervals": 1, "intervals": [0, 30], "budgets": [1]})
        self.assertEqual(truncate_profile(p, 90), p)
        self.assertEqual(truncate_profile(p, 1)["intervals"], [0, 1])
        with self.assertRaises(ValueError):
            truncate_profile(p, 91)

    def test_truncate_fractional_boundaries(self):
        # regression: bisect_right(intervals, H - 1) dropped [9.5, 10) when cutting at 9.7
        p = {"horizon": 10.0, "number_of_intervals": 2, "intervals": [0, 9.5, 10.0], "budgets": [1, 2]}
        t = truncate_profile(p, 9)
        self.assertEqual(t["intervals"], [0, 9])
        p2 = {"horizon": 12.0, "number_of_intervals": 2, "intervals": [0, 9.5, 12.0], "budgets": [1, 2]}
        self.assertEqual(truncate_profile(p2, 10)["intervals"], [0, 9.5, 10])
        self.assertEqual(truncate_profile(p2, 10)["budgets"], [1, 2])

    def test_shift_then_truncate(self):
        p = {"horizon": 90, "number_of_intervals": 3, "intervals": [0, 30, 60, 90], "budgets": [1, 2, 3]}
        s = truncate_profile(shift_profile(p, 40), 35)
        self.assertEqual(s["intervals"], [0, 20, 35])
        self.assertEqual(s["budgets"], [2, 3])


if __name__ == "__main__":
    unittest.main()
