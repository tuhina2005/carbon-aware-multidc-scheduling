"""Tests for cwm_multidc.data_loader."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from cwm_multidc.cwm_runner import DEFAULT_CLUSTER
from cwm_multidc.data_loader import (
    BudgetMapping,
    CITimeSeries,
    ClusterPower,
    TimeScale,
    build_topology,
    ci_to_profiles,
    load_electricitymaps_csv,
    synthetic_ci,
    wan_ci_profile_seconds,
)
from cwm_multidc.profile_shifting import shift_profile, truncate_profile, validate_profile


class TestTimeScale(unittest.TestCase):
    def test_conversions(self):
        ts = TimeScale(30)
        self.assertEqual(ts.seconds_per_unit, 120.0)
        self.assertEqual(ts.seconds_to_units_ceil(0), 0)
        self.assertEqual(ts.seconds_to_units_ceil(120.0), 1)
        self.assertEqual(ts.seconds_to_units_ceil(120.0001), 2)
        self.assertEqual(ts.seconds_to_units_ceil(3600.0 + 1e-10), 30)  # float noise absorbed
        # 1 TB at 0.95 Gbps = 8421.05 s -> 70.18 units -> 71
        self.assertEqual(ts.seconds_to_units_ceil(8e12 / 0.95e9), 71)
        # 1 kW for 1 hour = 1000 W x 30 units = 1 kWh
        self.assertAlmostEqual(ts.watt_units_to_kwh(1000 * 30), 1.0)
        with self.assertRaises(ValueError):
            TimeScale(0)
        with self.assertRaises(ValueError):
            ts.seconds_to_units_ceil(-1)


class TestBudgets(unittest.TestCase):
    def setUp(self):
        self.cl = ClusterPower.from_cluster_json(DEFAULT_CLUSTER, "small")

    def test_cluster_power_matches_cwm_base_power(self):
        # values verified in the Phase 1 audit against config.cpp setBasePower()
        self.assertEqual((self.cl.p_idle, self.cl.p_dyn), (16854, 30108 + 28069))

    def test_budget_monotone_and_floored_at_idle(self):
        m = BudgetMapping()
        bs = [m.budget(ci, self.cl) for ci in (0, 50, 200, 400, 799, 800, 1500)]
        self.assertTrue(all(a >= b for a, b in zip(bs, bs[1:])))
        self.assertEqual(bs[-1], self.cl.p_idle)
        self.assertEqual(bs[-2], self.cl.p_idle)
        self.assertEqual(bs[0], int(self.cl.p_idle + 0.2 * self.cl.p_dyn))
        self.assertTrue(all(isinstance(b, int) for b in bs))

    def test_profiles_aligned_and_valid(self):
        ci = CITimeSeries("X", (100.0, 300.0, 50.0))
        p, c = ci_to_profiles(ci, self.cl, TimeScale(30))
        self.assertEqual(p["intervals"], [0, 30, 60, 90])
        self.assertEqual(p["intervals"], c["intervals"])
        self.assertEqual(c["budgets"], [100.0, 300.0, 50.0])
        validate_profile(p)
        # shifting both identically keeps CI aligned with budgets
        sp, sc = shift_profile(p, 45), shift_profile(c, 45)
        self.assertEqual(sp["intervals"], sc["intervals"])
        self.assertEqual(sc["budgets"], [300.0, 50.0])
        # shifted intervals [0, 15, 45]: relative 20 = absolute 65, inside the third hour
        self.assertEqual(truncate_profile(sc, 20)["budgets"], [300.0, 50.0])
        self.assertEqual(truncate_profile(sc, 15)["budgets"], [300.0])


class TestCIData(unittest.TestCase):
    def test_synthetic_deterministic_and_calibrated(self):
        a = synthetic_ci("DE", 24 * 14, seed=3)
        b = synthetic_ci("DE", 24 * 14, seed=3)
        c = synthetic_ci("DE", 24 * 14, seed=4)
        self.assertEqual(a.values, b.values)
        self.assertNotEqual(a.values, c.values)
        self.assertAlmostEqual(np.mean(a.values), 350.0, delta=0.5)
        self.assertTrue(a.synthetic)
        # solar dip: German midday (UTC 10-12) cleaner than night (UTC 0-2) on average
        v = np.array(a.values).reshape(-1, 24)
        self.assertLess(v[:, 10:13].mean(), v[:, 0:3].mean())
        with self.assertRaises(ValueError):
            synthetic_ci("Atlantis", 24)

    def test_mean_fractional_hours(self):
        s = CITimeSeries("X", (100.0, 200.0, 400.0))
        self.assertAlmostEqual(s.mean(1.5), (100 + 0.5 * 200) / 1.5)
        self.assertAlmostEqual(s.mean(), 700 / 3)

    def test_csv_loader(self):
        with tempfile.TemporaryDirectory() as d:
            good = Path(d) / "de.csv"
            good.write_text(
                "Datetime (UTC),Zone Id,Carbon Intensity gCO₂eq/kWh (direct)\n"
                "2024-01-01 00:00:00,DE,300.5\n2024-01-01 01:00:00,DE,310\n2024-01-01 02:00:00,DE,290\n"
            )
            s = load_electricitymaps_csv(good)
            self.assertEqual(s.values, (300.5, 310.0, 290.0))
            self.assertEqual(s.region, "DE")
            self.assertFalse(s.synthetic)
            self.assertEqual(s.window(1, 2).values, (310.0, 290.0))

            gap = Path(d) / "gap.csv"
            gap.write_text("Datetime (UTC),Carbon Intensity gCO₂eq/kWh (direct)\n"
                           "2024-01-01 00:00:00,300\n2024-01-01 02:00:00,310\n")
            with self.assertRaises(ValueError):
                load_electricitymaps_csv(gap)
            blank = Path(d) / "blank.csv"
            blank.write_text("Datetime (UTC),Carbon Intensity gCO₂eq/kWh (direct)\n"
                             "2024-01-01 00:00:00,\n")
            with self.assertRaises(ValueError):
                load_electricitymaps_csv(blank)

    def test_wan_ci_endpoint_average(self):
        w = wan_ci_profile_seconds(CITimeSeries("A", (100.0, 200.0)), CITimeSeries("B", (0.0, 400.0)))
        self.assertEqual(w, {"intervals": [0.0, 3600.0, 7200.0], "ci": [50.0, 300.0]})


class TestTopology(unittest.TestCase):
    def test_build_and_validate(self):
        t = build_topology(48, DEFAULT_CLUSTER)
        self.assertEqual(t.hours, 48)
        self.assertEqual(t.source_dc.region, "DE")
        self.assertTrue(t.synthetic)
        p, _ = t.profiles("DC_Oslo")
        self.assertEqual(p["horizon"], 48 * 30)
        # cleaner grid -> larger budget on average
        self.assertGreater(np.mean(t.profiles("DC_Oslo")[0]["budgets"]),
                           np.mean(t.profiles("DC_Warsaw")[0]["budgets"]))
        with self.assertRaises(ValueError):
            build_topology(48, DEFAULT_CLUSTER, source="DC_Nowhere")


if __name__ == "__main__":
    unittest.main()
