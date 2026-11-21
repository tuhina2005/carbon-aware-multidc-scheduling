"""Holding-emissions re-scoring (cwm_multidc.waiting_cost)."""

import math
import unittest

import pandas as pd

from cwm_multidc import waiting_cost as wc
from cwm_multidc.data_loader import CITimeSeries, ClusterPower, DataCentre, Topology
from cwm_multidc.experiments import EPS_DEFAULT, RESULTS
from cwm_multidc.optimizer import Evaluation


def _topo():
    src = CITimeSeries("DE", (100.0, 200.0, 300.0, 400.0))
    dst = CITimeSeries("NO", (10.0, 20.0, 30.0, 40.0))
    return Topology("A", (DataCentre("A", "DE", src), DataCentre("B", "NO", dst)), ClusterPower("small", 1, 1))


def _ev(dc, t_arr_s, queue_s=0.0, total=100.0):
    return Evaluation(dc=dc, t_net_s=0.0, scheduler="cwm", status="ok", tau_s=0.0, t_arrival_s=t_arr_s,
                      t_arrival_units=0, d_prime_units=1, net_kwh=0.0, net_gco2=0.0, comp_gco2=total,
                      comp_loc_gco2=total, total_gco2=total, queue_wait_s=queue_s)


class TestHolding(unittest.TestCase):
    def test_integral_partial_hours(self):
        self.assertAlmostEqual(wc._integral((100.0, 200.0), 1800, 5400), 0.5 * 100 + 0.5 * 200)
        self.assertEqual(wc._integral((100.0,), 10, 10), 0.0)

    def test_source_then_destination(self):
        # held 1.5 h at the source (100, 200 g/kWh), then queued 1 h at the destination (20, 30)
        g = wc.holding_gco2_per_w(_ev("B", 5400, 3600), _topo())
        self.assertAlmostEqual(g, (100 + 0.5 * 200 + 0.5 * 20 + 0.5 * 30) / 1000)

    def test_local_job_pays_only_its_queue(self):
        g = wc.holding_gco2_per_w(_ev("A", 9999, 3600), _topo())  # arrival ignored at the source
        self.assertAlmostEqual(g, 100 / 1000)

    def test_with_holding_adds_to_both_metrics(self):
        e = wc.with_holding(_ev("B", 0), 5.0)
        self.assertEqual((e.comp_gco2, e.comp_loc_gco2, e.total_gco2), (105.0, 105.0, 105.0))
        self.assertAlmostEqual(e.under("location").total_gco2, 105.0)

    def test_break_even_interpolates(self):
        g = pd.DataFrame({"power_w": [0, 10, 100], "x": [2.0, 1.0, -1.0]})
        self.assertTrue(10 < wc.break_even(g, "x") < 100)
        self.assertIsNone(wc.break_even(pd.DataFrame({"power_w": [0, 10], "x": [2.0, 1.0]}), "x"))


@unittest.skipUnless((RESULTS / "multidate" / "multidate_evals.csv").exists()
                     and (wc.CI_DIR / "DE.csv").exists(), "saved results / CI data not present")
class TestZeroPowerReproduces(unittest.TestCase):
    """P = 0 must reproduce the saved summaries exactly (same choice, same total)."""

    def _check(self, tag, n_max=24):
        folder, prefix, _ = wc.STUDIES[tag]
        sm = pd.read_csv(RESULTS / folder / f"{prefix}_summary.csv")
        sm = sm[(sm.metric == "location") & ((sm.eps_kwh_per_gb - EPS_DEFAULT).abs() < 1e-12)]
        if "contention_rho" not in sm:
            sm["contention_rho"] = 0.0
        sm = sm.fillna({"contention_rho": 0.0}).set_index(wc.KEYS + ["method"])
        for i, (key, prob, evals, d, m, green) in enumerate(wc.load_problems(tag)):
            if i >= n_max:
                break
            sel = wc.select(prob, evals, d, green, "location", 1.0, m_ref=m)
            for meth in wc.METHODS:
                saved = sm.loc[key + (meth,), "total_gco2"]
                got = sel[meth].total_gco2 if sel[meth] is not None else float("nan")
                if math.isnan(saved):
                    self.assertTrue(math.isnan(got), (tag, key, meth))
                else:
                    self.assertAlmostEqual(got, saved, places=6, msg=(tag, key, meth))

    def test_multidate(self):
        self._check("multidate")

    def test_contention(self):
        self._check("contention")


if __name__ == "__main__":
    unittest.main()
