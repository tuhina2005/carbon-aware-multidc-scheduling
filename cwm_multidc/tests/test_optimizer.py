"""Tests for cwm_multidc.optimizer: grid construction, carbon arithmetic, baselines, E2E."""

import math
import unittest
from pathlib import Path

import numpy as np

from cwm_multidc.cwm_runner import DAG_DIR, DEFAULT_CLUSTER, DEPLOY_DIR, STATUS_OK, CWMResult, CWMRunner, ResultCache
from cwm_multidc.data_loader import (
    CITimeSeries,
    ClusterPower,
    DataCentre,
    TimeScale,
    Topology,
    build_topology,
)
from cwm_multidc.data_loader import perturb_ci, with_ci
from cwm_multidc.optimizer import (
    Evaluation,
    Problem,
    SearchResult,
    _network,
    evaluate,
    solve,
    t_net_candidates,
    transfer_duration_s,
)

HAVE_BIN = (DEPLOY_DIR / "solve_cwm").exists() and (DAG_DIR / "atacseq200.dot").exists()
CL = ClusterPower("small", 16854, 58177)


class FakeRunner:
    """Deterministic stand-in for CWMRunner: a constant ``excess_per_unit`` W of brown
    power over the whole of D', so E_j = excess_per_unit x (interval length in units).
    With 120 s/unit, 1000 W over a full 30-unit interval is exactly 1 kWh."""

    def __init__(self, m_ref=60, excess_per_unit=1000):
        self.m_ref = m_ref
        self.excess_per_unit = excess_per_unit  # W of brown power, constant
        self.calls = []

    def heft_makespan(self, dag):
        return self.m_ref

    def solve(self, dag, profile, deadline, seed=42, scheduler="cwm"):
        self.calls.append((profile["intervals"][:3], deadline, seed, scheduler))
        iv = profile["intervals"]
        per = tuple(self.excess_per_unit * (b - a) for a, b in zip(iv, iv[1:]))
        # total energy = idle + work; work = 2 x excess so the two metrics differ
        energy = tuple(CL.p_idle * (b - a) + 2 * x for x, a, b in zip(per, iv, iv[1:]))
        return CWMResult(STATUS_OK, scheduler, deadline, 1, deadline, sum(per), per, "", energy)


def _topo(ci_by_dc, bw=1.0, source="S"):
    dcs = tuple(DataCentre(n, n, CITimeSeries(n, tuple(map(float, v))), bw) for n, v in ci_by_dc.items())
    return Topology(source, dcs, CL, TimeScale(30))


class TestCandidates(unittest.TestCase):
    def setUp(self):
        self.topo = _topo({"S": [100] * 24, "G": [10] * 24})

    def test_source_only_tnet_zero(self):
        p = Problem(Path("x.dot"), self.topo, 1000.0)
        self.assertEqual(t_net_candidates(p, "S", 60, 90), [0.0])
        self.assertEqual(t_net_candidates(p, "S", 60, 59), [])

    def test_breakpoints_and_feasibility(self):
        p = Problem(Path("x.dot"), self.topo, 1000.0)  # tau = 8421.05 s
        tau = transfer_duration_s(p, "G")
        self.assertAlmostEqual(tau, 8e12 / 0.95e9)
        m, d = 60, 60 + 300  # slack 300 units = 10 h
        c = t_net_candidates(p, "G", m, d)
        ts = self.topo.timescale
        self.assertEqual(c[0], 0.0)
        for h in range(1, 7):
            self.assertIn(h * 3600.0, c)
        for k in range(3, 10):
            if 0 <= k * 3600 - tau <= c[-1]:
                self.assertTrue(any(abs(x - (k * 3600 - tau)) < 1e-6 for x in c))
        for x in c:
            self.assertLessEqual(ts.seconds_to_units_ceil(x + tau), d - m)
        # latest candidate leaves exactly the HEFT makespan (within one unit)
        self.assertGreaterEqual(d - ts.seconds_to_units_ceil(c[-1] + tau), m)
        self.assertLess(ts.units_to_seconds(d - m) - (c[-1] + tau), 120.0 + 1e-6)

    def test_transfer_too_long_infeasible(self):
        p = Problem(Path("x.dot"), self.topo, 10_000.0)  # tau ~ 23.4 h
        self.assertEqual(t_net_candidates(p, "G", 60, 60 + 300), [])

    def test_uniform_grid(self):
        p = Problem(Path("x.dot"), self.topo, 100.0, grid="uniform", grid_step_s=900)
        c = t_net_candidates(p, "G", 60, 120)
        self.assertEqual(c[:3], [0.0, 900.0, 1800.0])
        self.assertTrue(all(abs((b - a) - 900) < 1e-9 for a, b in zip(c, c[1:])))

    def test_breakpoint_grid_finds_network_optimum(self):
        """NetCarbon is piecewise linear in T_net; the breakpoint grid must contain its
        minimiser.  Compare against a 30 s brute-force scan on a random CI profile."""
        rng = np.random.default_rng(7)
        topo = _topo({"S": rng.uniform(100, 600, 30), "G": rng.uniform(5, 300, 30)})
        p = Problem(Path("x.dot"), topo, 1500.0)
        m, d = 30, 30 + 600
        cands = t_net_candidates(p, "G", m, d)
        best_grid = min(_network(p, "G", t).network_emissions_gco2 for t in cands)
        fine = np.arange(0.0, cands[-1], 30.0)
        best_fine = min(_network(p, "G", float(t)).network_emissions_gco2 for t in fine)
        self.assertLessEqual(best_grid, best_fine + 1e-6)


class TestEvaluateArithmetic(unittest.TestCase):
    def test_carbon_units_and_alignment(self):
        # CI of G: hour h -> 10*(h+1);  1000 W brown for every unit of D'
        topo = _topo({"S": [400] * 24, "G": [10.0 * (h + 1) for h in range(24)]})
        p = Problem(Path("x.dot"), topo, 1000.0)
        fr = FakeRunner(m_ref=60)
        e = evaluate(p, fr, "G", 0.0, 240)
        # arrival: 8421.05 s -> 71 units (2 h 11 units); D' = 169 units
        self.assertEqual(e.t_arrival_units, 71)
        self.assertEqual(e.d_prime_units, 169)
        # brown energy = 1 kW x 169 units x 120 s = 1 kW x 5.6333 h
        self.assertAlmostEqual(e.comp_brown_kwh, 169 * 120 / 3600)
        # intervals after shift: [71,90) h2, [90,120) h3, ..., [210,240) h7
        hours = [(19, 30), (30, 40), (30, 50), (30, 60), (30, 70), (30, 80)]
        expected = sum(units * 120 / 3600 * ci for units, ci in hours)
        self.assertAlmostEqual(e.comp_gco2, expected)
        # network: 20 kWh x mean((400 + CI_G)/2) over [0, 8421 s)
        tau = 8e12 / 0.95e9
        mean_ci = (3600 * 205 + 3600 * 210 + (tau - 7200) * 215) / tau
        self.assertAlmostEqual(e.net_kwh, 20.0)
        self.assertAlmostEqual(e.net_gco2, 20.0 * mean_ci, places=6)
        self.assertAlmostEqual(e.total_gco2, e.net_gco2 + e.comp_gco2)

    def test_location_metric(self):
        topo = _topo({"S": [400] * 24, "G": [10] * 24})
        e = evaluate(Problem(Path("x.dot"), topo, 1000.0), FakeRunner(), "S", 0.0, 120)
        # dynamic energy = 2 x excess -> location carbon = 2 x brown carbon at constant CI
        self.assertAlmostEqual(e.comp_dyn_kwh, 2 * e.comp_brown_kwh)
        self.assertAlmostEqual(e.comp_loc_gco2, 2 * e.comp_gco2)
        self.assertAlmostEqual(e.total_loc_gco2, e.net_gco2 + e.comp_loc_gco2)

    def test_under_metric_and_eps_scaling(self):
        e = Evaluation("G", 0.0, "cwm", STATUS_OK, 1.0, 1.0, 1, 10, 20.0, 1000.0,
                       comp_gco2=50.0, total_gco2=1050.0, comp_loc_gco2=80.0)
        u = e.under("location", 0.25)
        self.assertEqual((u.net_gco2, u.net_kwh, u.comp_gco2, u.total_gco2), (250.0, 5.0, 80.0, 330.0))
        self.assertEqual(e.under().total_gco2, 1050.0)
        with self.assertRaises(ValueError):
            e.under("market")

    def test_source_has_no_network_and_full_deadline(self):
        topo = _topo({"S": [400] * 24, "G": [10] * 24})
        e = evaluate(Problem(Path("x.dot"), topo, 1000.0), FakeRunner(), "S", 0.0, 120)
        self.assertEqual((e.net_gco2, e.t_arrival_units, e.d_prime_units), (0.0, 0, 120))
        self.assertAlmostEqual(e.comp_gco2, 120 * 120 / 3600 * 400)

    def test_seeds_averaged(self):
        topo = _topo({"S": [400] * 24, "G": [10] * 24})
        fr = FakeRunner()
        evaluate(Problem(Path("x.dot"), topo, 1000.0, seeds=(1, 2, 3)), fr, "S", 0.0, 120)
        self.assertEqual([c[2] for c in fr.calls], [1, 2, 3])


class TestBaselines(unittest.TestCase):
    def test_semantics_with_fake_runner(self):
        topo = _topo({"S": [400] * 24, "G": [10] * 24, "B": [800] * 24, "M": [200] * 24})
        p = Problem(Path("x.dot"), topo, 200.0, alpha=4.0)
        r = solve(p, FakeRunner(m_ref=60), workers=2)
        s = r.summary()
        self.assertEqual(r.greenest_dc, "G")
        self.assertEqual((s["B1"].dc, s["B1"].t_net_s), ("S", 0.0))
        self.assertEqual((s["B2"].dc, s["B2"].scheduler), ("G", "heft"))
        self.assertEqual((s["B3"].dc, s["B3"].t_net_s, s["B3"].scheduler), ("G", 0.0, "cwm"))
        self.assertEqual(s["B4"].dc, "G")
        self.assertEqual(s["B4"].net_gco2, min(e.net_gco2 for e in r.evaluations if e.dc == "G"))
        self.assertEqual(s["B5"].t_net_s, 0.0)
        for b in ("B1", "B3", "B4", "B5", "A1", "A2"):
            self.assertLessEqual(s["Ours"].total_gco2, s[b].total_gco2 + 1e-9, b)
        self.assertIsNone(s["C1"])  # control not requested

    def test_ablations_control_and_bound(self):
        topo = _topo({"S": [400] * 24, "G": [10] * 24, "B": [800] * 24, "M": [200] * 24})
        fr = FakeRunner(m_ref=60)
        p = Problem(Path("x.dot"), topo, 200.0, alpha=4.0, seeds=(1, 2), equal_budget_control=True)
        r = solve(p, fr, workers=2)
        s = r.summary()
        grid = [e for e in r.evaluations if e.role == "grid" and e.scheduler == "cwm"]
        ctrl = [e for e in r.evaluations if e.role == "control"]
        # equal budget: K grid points x 2 seeds == (K-1 control groups + B3) x 2 seeds
        self.assertEqual(len(ctrl) + 1, len(grid))
        self.assertTrue(all(len(e.seeds) == 2 and e.dc == "G" and e.t_net_s == 0.0 for e in ctrl))
        self.assertEqual(len({e.seeds for e in ctrl} | {(1, 2)}), len(grid))  # disjoint seed groups
        self.assertLessEqual(s["C1"].total_gco2, s["B3"].total_gco2 + 1e-9)
        # control points never enter the search space of Ours
        self.assertEqual(s["Ours"].role, "grid")
        self.assertEqual(s["A1"].t_net_s, 0.0)
        self.assertEqual(s["A2"].dc, "G")
        self.assertLessEqual(r.separable_bound(), s["Ours"].total_gco2 + 1e-9)
        # re-derivation under another metric / eps is consistent with direct computation
        loc = r.summary("location", 0.5)
        expect = min(e.net_gco2 * 0.5 + e.comp_loc_gco2 for e in grid if e.ok)
        self.assertAlmostEqual(loc["Ours"].total_gco2, expect)

    def test_nonmonotone_count(self):
        def ev(t_arr, comp):
            return Evaluation("G", float(t_arr), "cwm", STATUS_OK, 0.0, 0.0, t_arr, 100 - t_arr, 0.0, 0.0,
                              comp_gco2=comp, total_gco2=comp, comp_loc_gco2=comp)
        r = SearchResult(None, 10, 100, [ev(0, 5.0), ev(10, 7.0), ev(20, 6.0), ev(30, 9.0)], None)
        self.assertEqual(r.nonmonotone_fraction(), (1, 3))


class TestForecast(unittest.TestCase):
    def test_perturb_ci(self):
        s = CITimeSeries("DE", tuple(float(x) for x in range(100, 400)))
        self.assertIs(perturb_ci(s, 0.0), s)
        f = perturb_ci(s, 0.25, seed=3)
        self.assertEqual(f.values, perturb_ci(s, 0.25, seed=3).values)
        ratio = np.log(np.array(f.values) / np.array(s.values))
        self.assertAlmostEqual(ratio.std(), 0.25, delta=0.08)
        self.assertTrue(all(v > 0 for v in f.values))
        topo = _topo({"S": [400] * 24, "G": [10] * 24})
        t2 = with_ci(topo, lambda x: perturb_ci(x, 0.1, 1))
        self.assertEqual([d.name for d in t2.dcs], ["S", "G"])
        self.assertNotEqual(t2.dc("G").ci.values, topo.dc("G").ci.values)


@unittest.skipUnless(HAVE_BIN, "solve_cwm binary not available")
class TestEndToEnd(unittest.TestCase):
    """Real solve_cwm on a real WfCommons DAG, three DCs."""

    @classmethod
    def setUpClass(cls):
        dcs = (("DC_Frankfurt", "DE"), ("DC_Oslo", "NO"), ("DC_Warsaw", "PL"))
        cls.topo = build_topology(24, DEFAULT_CLUSTER, dcs=dcs, start_hour=6)
        cls.problem = Problem(DAG_DIR / "atacseq200.dot", cls.topo, 1000.0, alpha=2.0)
        # solve_cwm is not run-to-run deterministic for a fixed seed (inherited from the CWM
        # baseline: ~10 % of runs return a different schedule), so the direct call below shares
        # this in-memory cache: a hit proves Ours passed byte-identical inputs to the solver.
        cls.cache = ResultCache(None)
        cls.result = solve(cls.problem, CWMRunner(cache=cls.cache))

    def test_invariants(self):
        r = self.result
        self.assertEqual(r.m_ref_units, 168)
        self.assertEqual(r.deadline_units, 336)
        self.assertTrue(r.best is not None and r.best.ok)
        for e in r.evaluations:
            if e.ok:
                self.assertLessEqual(e.makespan_units, e.d_prime_units)
                self.assertEqual(e.t_arrival_units + e.d_prime_units, r.deadline_units)
                self.assertGreaterEqual(e.d_prime_units, r.m_ref_units)
                self.assertGreaterEqual(e.comp_gco2, 0.0)
                self.assertAlmostEqual(e.total_gco2, e.net_gco2 + e.comp_gco2)
        s = r.summary()
        for b in ("B1", "B3", "B4", "B5", "A1", "A2"):
            if s[b] is not None:
                self.assertLessEqual(s["Ours"].total_gco2, s[b].total_gco2 + 1e-9)
        for e in r.evaluations:
            if e.ok:  # marginal location-based carbon is defined and non-negative
                self.assertGreaterEqual(e.comp_loc_gco2, 0.0)
                self.assertGreaterEqual(e.comp_dyn_kwh, 0.0)

    def test_source_matches_direct_solver_call(self):
        """Ours' bookkeeping for the source DC equals a hand-made solve_cwm call."""
        power, ci = self.topo.profiles("DC_Frankfurt")
        from cwm_multidc.profile_shifting import truncate_profile

        n_before = len(self.cache._mem)
        direct = CWMRunner(cache=self.cache).solve(DAG_DIR / "atacseq200.dot", truncate_profile(power, 336), 336,
                                                   seed=42)
        self.assertEqual(len(self.cache._mem), n_before, "direct call missed the cache: inputs differ")
        e = next(x for x in self.result.evaluations if x.dc == "DC_Frankfurt" and x.scheduler == "cwm")
        self.assertEqual(e.cwm_raw_watt_units, direct.carbon_cost)
        ts = self.topo.timescale
        exp = sum(ts.watt_units_to_kwh(w) * c for w, c in zip(direct.per_interval, ci["budgets"]))
        self.assertAlmostEqual(e.comp_gco2, exp)


if __name__ == "__main__":
    unittest.main()
