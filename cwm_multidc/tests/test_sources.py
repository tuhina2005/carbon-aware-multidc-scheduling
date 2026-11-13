"""W3: the data's source DC is a parameter (local run, network path and B1 all follow it)."""

import unittest

from cwm_multidc.cwm_runner import DAG_DIR, DEFAULT_CLUSTER, DEPLOY_DIR, CWMRunner, ResultCache
from cwm_multidc.data_loader import build_topology
from cwm_multidc.experiments import SRC_SOURCES
from cwm_multidc.optimizer import Problem, solve, transfer_duration_s

HAVE_BIN = (DEPLOY_DIR / "solve_cwm").exists() and (DAG_DIR / "atacseq200.dot").exists()
DCS = (("DC_Frankfurt", "DE"), ("DC_Paris", "FR"), ("DC_California", "US-CAL"))


class SourceTest(unittest.TestCase):
    def test_sources_cover_the_three_swing_regimes(self):
        self.assertEqual(SRC_SOURCES, ("DC_Frankfurt", "DC_Warsaw", "DC_California"))

    def test_source_has_no_transfer_and_paths_start_there(self):
        t = build_topology(24, DEFAULT_CLUSTER, dcs=DCS, start_hour=6, source="DC_California")
        p = Problem(DAG_DIR / "atacseq200.dot", t, 100.0, alpha=2.0)
        self.assertEqual(transfer_duration_s(p, "DC_California"), 0.0)
        self.assertGreater(transfer_duration_s(p, "DC_Frankfurt"), 0.0)
        wan = t.wan_ci("DC_Paris")["ci"]  # endpoint average of California and Paris
        cal, par = t.dc("DC_California").ci.values, t.dc("DC_Paris").ci.values
        self.assertAlmostEqual(wan[3], (cal[3] + par[3]) / 2)

    @unittest.skipUnless(HAVE_BIN, "solve_cwm not built")
    def test_b1_runs_at_the_source(self):
        t = build_topology(24, DEFAULT_CLUSTER, dcs=DCS, start_hour=6, source="DC_California")
        s = solve(Problem(DAG_DIR / "atacseq200.dot", t, 100.0, alpha=2.0),
                  CWMRunner(cache=ResultCache(None))).summary("location")
        self.assertEqual(s["B1"].dc, "DC_California")
        self.assertEqual(s["B1"].net_gco2, 0.0)


if __name__ == "__main__":
    unittest.main()
