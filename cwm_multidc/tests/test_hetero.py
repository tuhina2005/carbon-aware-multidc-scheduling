"""Per-DC hardware (processor mix + PUE) and the efficiency-aware baseline B6."""

import unittest

from cwm_multidc.cwm_runner import DAG_DIR, DEFAULT_CLUSTER, DEPLOY_DIR, CWMRunner, ResultCache
from cwm_multidc.data_loader import HardwareTier, build_topology, perturb_ci, with_ci
from cwm_multidc.experiments import HW_DIR, HW_SCENARIOS, HW_TIERS, hw_tiers
from cwm_multidc.optimizer import Problem, evaluate, heft_reference, runner_for, solve

HAVE_BIN = (DEPLOY_DIR / "solve_cwm").exists() and (DAG_DIR / "atacseq200.dot").exists()
DCS = (("DC_Frankfurt", "DE"), ("DC_Oslo", "NO"), ("DC_Paris", "FR"))


def topo(hardware=None):
    return build_topology(24, DEFAULT_CLUSTER, dcs=DCS, start_hour=6, hardware=hardware)


class TopologyTest(unittest.TestCase):
    def test_default_is_homogeneous(self):
        t = topo()
        self.assertFalse(t.heterogeneous)
        self.assertTrue(all(d.pue == 1.0 and d.cluster_json is None for d in t.dcs))

    def test_tiers_set_cluster_and_pue(self):
        t = topo({"DC_Oslo": HW_TIERS["legacy"], "DC_Paris": HW_TIERS["standard"]})
        oslo, paris, fra = t.dc("DC_Oslo"), t.dc("DC_Paris"), t.dc("DC_Frankfurt")
        self.assertTrue(oslo.cluster_json.endswith("legacy.json"))
        self.assertEqual((oslo.hardware, oslo.pue), ("legacy", 2.0))
        self.assertIsNone(paris.cluster_json)  # standard = the shared cluster
        self.assertEqual((paris.hardware, paris.pue), ("standard", 1.55))
        self.assertEqual(fra.pue, 1.0)  # not named -> baseline
        self.assertNotEqual(t.cluster_of("DC_Oslo"), t.cluster_of("DC_Paris"))

    def test_with_ci_keeps_hardware(self):
        t = topo({"DC_Oslo": HW_TIERS["legacy"]})
        f = with_ci(t, lambda s: perturb_ci(s, 0.1, 0))
        self.assertEqual((f.dc("DC_Oslo").pue, f.dc("DC_Oslo").cluster_json),
                         (t.dc("DC_Oslo").pue, t.dc("DC_Oslo").cluster_json))

    def test_scenarios_cover_every_dc(self):
        for scen in HW_SCENARIOS:
            tiers = hw_tiers(scen)
            self.assertEqual(len(tiers), 6)
            self.assertTrue(set(HW_SCENARIOS[scen].values()) <= set(HW_TIERS))
        self.assertTrue((HW_DIR / "efficient.json").exists() and (HW_DIR / "legacy.json").exists())


@unittest.skipUnless(HAVE_BIN, "solve_cwm not built")
class SolveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = CWMRunner(cache=ResultCache(None))

    def test_runner_and_heft_per_dc(self):
        p = Problem(DAG_DIR / "atacseq200.dot", topo({"DC_Oslo": HW_TIERS["legacy"]}), 100.0, alpha=2.0)
        self.assertIs(runner_for(p, self.runner, "DC_Paris"), self.runner)
        self.assertTrue(str(runner_for(p, self.runner, "DC_Oslo").cluster_json).endswith("legacy.json"))
        m_ref, m = heft_reference(p, self.runner)
        self.assertEqual(m_ref, m["DC_Frankfurt"])
        self.assertGreater(m["DC_Oslo"], m["DC_Paris"])  # legacy hardware is slower

    def test_pue_scales_compute_exactly(self):
        dag = DAG_DIR / "atacseq200.dot"
        base = Problem(dag, topo(), 100.0, alpha=2.0)
        pue = Problem(dag, topo({"DC_Paris": HardwareTier("x", None, 1.5)}), 100.0, alpha=2.0)
        a = evaluate(base, self.runner, "DC_Paris", 0.0, 336)
        b = evaluate(pue, self.runner, "DC_Paris", 0.0, 336)
        self.assertAlmostEqual(b.comp_loc_gco2, 1.5 * a.comp_loc_gco2, places=6)
        self.assertAlmostEqual(b.comp_gco2, 1.5 * a.comp_gco2, places=6)
        self.assertAlmostEqual(b.net_gco2, a.net_gco2, places=9)  # network unaffected

    def test_b6_ranks_by_pue_times_ci(self):
        dag = DAG_DIR / "atacseq200.dot"
        same = solve(Problem(dag, topo(), 100.0, alpha=2.0), self.runner).summary("location")
        self.assertEqual(same["B6"].dc, same["B3"].dc)  # equal PUEs -> B6 == B3
        # make B3's choice 5x less efficient: B6 must move away from it
        green = same["B3"].dc
        r = solve(Problem(dag, topo({green: HardwareTier("bad", None, 5.0)}), 100.0, alpha=2.0), self.runner)
        s = r.summary("location")
        self.assertEqual(s["B3"].dc, green)
        self.assertNotEqual(s["B6"].dc, green)
        self.assertLessEqual(s["Ours"].total_gco2, s["B6"].total_gco2 + 1e-9)


if __name__ == "__main__":
    unittest.main()
