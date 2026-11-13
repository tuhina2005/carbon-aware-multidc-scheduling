"""W2 contention: diurnal DC queues, queue-delayed compute start, queue-aware baseline B7."""

import unittest

from cwm_multidc.cwm_runner import DAG_DIR, DEFAULT_CLUSTER, DEPLOY_DIR, CWMRunner, ResultCache
from cwm_multidc.data_loader import CITimeSeries, QueueSpec, build_topology, diurnal_queue, series_utc_start
from cwm_multidc.experiments import CT_RHOS, CT_WEIGHTS, ct_queues
from cwm_multidc.optimizer import Problem, evaluate, solve

HAVE_BIN = (DEPLOY_DIR / "solve_cwm").exists() and (DAG_DIR / "atacseq200.dot").exists()
DCS = (("DC_Frankfurt", "DE"), ("DC_Oslo", "NO"), ("DC_Paris", "FR"))


def topo(queues=None, start_hour=6):
    return build_topology(24, DEFAULT_CLUSTER, dcs=DCS, start_hour=start_hour, queues=queues)


class QueueModelTest(unittest.TestCase):
    def test_local_business_hours_follow_dst(self):
        jan = CITimeSeries("FR", (100.0,) * 24, "2024-01-17 00:00:00")  # CET = UTC+1
        jul = CITimeSeries("FR", (100.0,) * 24, "2024-07-17 00:00:00")  # CEST = UTC+2
        q = QueueSpec(2.0, 0.5)
        self.assertEqual([i for i, v in enumerate(diurnal_queue(jan, q)) if v == 2.0], list(range(8, 17)))
        self.assertEqual([i for i, v in enumerate(diurnal_queue(jul, q)) if v == 2.0], list(range(7, 16)))
        cal = CITimeSeries("US-CAL", (100.0,) * 24, "2024-01-17 00:00:00")  # PST = UTC-8
        self.assertEqual(diurnal_queue(cal, q)[17], 2.0)
        self.assertEqual(diurnal_queue(cal, q)[3], 0.5)

    def test_window_suffix_parsed(self):
        s = CITimeSeries("DE", (1.0,), "2024-01-01 00:00:00+2568h")
        self.assertEqual(series_utc_start(s).isoformat(), "2024-04-17T00:00:00+00:00")

    def test_topology_queue_lookup(self):
        t = topo({"DC_Paris": QueueSpec(3.0, 1.0)})
        self.assertIsNone(t.dc("DC_Oslo").queue_hours)
        self.assertTrue(t.contended)
        q = t.dc("DC_Paris").queue_hours
        self.assertEqual(t.queue_wait_s("DC_Paris", 2.5 * 3600), q[2] * 3600)
        self.assertEqual(t.queue_wait_s("DC_Oslo", 0.0), 0.0)
        self.assertFalse(topo({"DC_Paris": QueueSpec(0.0, 0.0)}).contended)

    def test_rho_zero_is_baseline(self):
        self.assertEqual(ct_queues(0.0), {})
        q = ct_queues(2.0)
        self.assertEqual(q["DC_Paris"].peak_h, 2.0 * CT_WEIGHTS["DC_Paris"] * 2.0)
        self.assertIn(0.0, CT_RHOS)


@unittest.skipUnless(HAVE_BIN, "solve_cwm not built")
class SolveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = CWMRunner(cache=ResultCache(None))
        cls.dag = DAG_DIR / "atacseq200.dot"

    def test_queue_delays_start_and_shrinks_deadline(self):
        base = Problem(self.dag, topo(), 100.0, alpha=2.0)
        q = Problem(self.dag, topo({"DC_Paris": QueueSpec(1.0, 1.0)}), 100.0, alpha=2.0)
        a = evaluate(base, self.runner, "DC_Paris", 0.0, 336)
        b = evaluate(q, self.runner, "DC_Paris", 0.0, 336)
        self.assertEqual(a.queue_wait_s, 0.0)
        self.assertEqual(a.t_start_units, a.t_arrival_units)
        self.assertEqual(b.queue_wait_s, 3600.0)
        self.assertEqual(b.t_start_units - b.t_arrival_units, 30)  # 1 h = 30 units
        self.assertEqual(b.d_prime_units, a.d_prime_units - 30)

    def test_queue_longer_than_slack_is_infeasible(self):
        p = Problem(self.dag, topo({"DC_Paris": QueueSpec(8.0, 8.0)}), 100.0, alpha=2.0)
        e = evaluate(p, self.runner, "DC_Paris", 0.0, 336)
        self.assertFalse(e.ok)
        self.assertIn("queue", e.message)

    def test_b7_equals_b3_without_queues_and_avoids_blocked_dc(self):
        s = solve(Problem(self.dag, topo(), 100.0, alpha=2.0), self.runner).summary("location")
        self.assertEqual(s["B7"].dc, s["B3"].dc)
        green = s["B3"].dc
        r = solve(Problem(self.dag, topo({green: QueueSpec(8.0, 8.0)}), 100.0, alpha=2.0), self.runner)
        s = r.summary("location")
        self.assertIsNone(s["B3"])  # CI-only placement misses the deadline
        self.assertIsNotNone(s["B7"])
        self.assertNotEqual(s["B7"].dc, green)
        self.assertLessEqual(s["Ours"].total_gco2, s["B7"].total_gco2 + 1e-9)


if __name__ == "__main__":
    unittest.main()
