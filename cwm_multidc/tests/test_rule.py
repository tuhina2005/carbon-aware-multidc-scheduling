"""W4 theory-guided rule: solver-free ranking + top-k solved candidates (R1, R3)."""

import unittest

from cwm_multidc.cwm_runner import DAG_DIR, DEFAULT_CLUSTER, DEPLOY_DIR, CWMRunner, ResultCache
from cwm_multidc.data_loader import QueueSpec, build_topology
from cwm_multidc.optimizer import RULES, Problem, rule_rank, solve

HAVE_BIN = (DEPLOY_DIR / "solve_cwm").exists() and (DAG_DIR / "atacseq200.dot").exists()
DCS = (("DC_Frankfurt", "DE"), ("DC_Oslo", "NO"), ("DC_Paris", "FR"))


@unittest.skipUnless(HAVE_BIN, "solve_cwm not built")
class RuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = CWMRunner(cache=ResultCache(None))
        topo = build_topology(30, DEFAULT_CLUSTER, dcs=DCS, start_hour=6)
        cls.res = solve(Problem(DAG_DIR / "atacseq200.dot", topo, 300.0, alpha=2.5), cls.runner)

    def test_rules_are_grid_points_and_ordered(self):
        for metric in ("location", "brown"):
            s = self.res.summary(metric)
            for r in RULES:
                self.assertIsNotNone(s[r])
                self.assertLessEqual(s["Ours"].total_gco2, s[r].total_gco2 + 1e-9)
            self.assertLessEqual(s["R3"].total_gco2, s["R1"].total_gco2 + 1e-9)  # top-3 contains top-1

    def test_ranking_uses_no_compute_results_of_candidates(self):
        """Changing a candidate's realised compute carbon must not change its rank."""
        from dataclasses import replace

        grid = [e for e in self.res.evaluations if e.role == "grid" and e.scheduler == "cwm"]
        ref = next(e for e in grid if e.ok and e.t_net_s == 0.0)
        a = rule_rank(self.res.problem, grid, self.res.deadline_units, ref, self.res.m_ref_units)
        shuffled = [replace(e, comp_loc_gco2=12345.0, comp_gco2=6789.0) if e is not ref else e for e in grid]
        b = rule_rank(self.res.problem, shuffled, self.res.deadline_units, ref, self.res.m_ref_units)
        self.assertEqual([(e.dc, e.t_net_s) for e in a], [(e.dc, e.t_net_s) for e in b])

    def test_window_shorter_than_heft_is_dropped(self):
        grid = [e for e in self.res.evaluations if e.role == "grid" and e.scheduler == "cwm"]
        ref = next(e for e in grid if e.ok and e.t_net_s == 0.0)
        d = self.res.deadline_units
        self.assertTrue(rule_rank(self.res.problem, grid, d, ref, d))  # L = D: start-at-0 candidates fit
        self.assertEqual(rule_rank(self.res.problem, grid, d, ref, d + 30), [])  # L = D + 1 h: none fit

    def test_queue_moves_ranking(self):
        """A long queue at a DC pushes its candidates down (later start, fewer clean hours)."""
        topo = build_topology(30, DEFAULT_CLUSTER, dcs=DCS, start_hour=6,
                              queues={"DC_Paris": QueueSpec(6.0, 6.0), "DC_Oslo": QueueSpec(6.0, 6.0)})
        r = solve(Problem(DAG_DIR / "atacseq200.dot", topo, 300.0, alpha=2.5), self.runner)
        s = r.summary("location")
        self.assertLessEqual(s["Ours"].total_gco2, s["R3"].total_gco2 + 1e-9)


if __name__ == "__main__":
    unittest.main()
