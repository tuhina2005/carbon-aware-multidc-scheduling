"""Tests for cwm_multidc.cwm_runner (parsing, caching, and real-binary integration)."""

import json
import math
import tempfile
import unittest
from pathlib import Path

from cwm_multidc.cwm_runner import (
    DAG_DIR,
    DEFAULT_CLUSTER,
    DEPLOY_DIR,
    INSTANCES_DIR,
    STATUS_INFEASIBLE,
    STATUS_OK,
    CWMResult,
    CWMRunner,
    CWMRunnerError,
    ResultCache,
    parse_solver_output,
)

HAVE_BIN = (DEPLOY_DIR / "solve_cwm").exists() and (DAG_DIR / "atacseq200.dot").exists()


def _real_profile():
    with open(INSTANCES_DIR / "Profiles" / "small" / "DE24s.json") as f:
        p = json.load(f)
    p["budgets"] = [math.floor(b) for b in p["budgets"]]  # what the C++ parser does
    return p


class TestParsing(unittest.TestCase):
    def test_single_line(self):
        self.assertEqual(parse_solver_output("12,240,999\n", False), (12, 240, 999, None, None))

    def test_per_interval(self):
        self.assertEqual(parse_solver_output("1,5,7\n0,3,4\n9,9,9\n", True, 3),
                         (1, 5, 7, (0, 3, 4), (9, 9, 9)))

    def test_energy_below_excess_rejected(self):
        with self.assertRaises(ValueError):
            parse_solver_output("1,5,7\n0,3,4\n9,2,9\n", True, 3)

    def test_missing_energy_line_rejected(self):
        with self.assertRaises(ValueError):
            parse_solver_output("1,5,7\n0,3,4\n", True, 3)

    def test_inconsistent_sum_rejected(self):
        with self.assertRaises(ValueError):
            parse_solver_output("1,5,8\n0,3,4\n9,9,9\n", True, 3)

    def test_wrong_length_rejected(self):
        with self.assertRaises(ValueError):
            parse_solver_output("1,5,7\n3,4\n9,9\n", True, 3)

    def test_garbage_rejected(self):
        for s in ["", "a,b,c", "1,2", "1,0,5", "1,2,3\nextra"]:
            with self.assertRaises(ValueError, msg=s):
                parse_solver_output(s, False)


class TestCache(unittest.TestCase):
    def test_roundtrip_and_torn_line(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.jsonl"
            c = ResultCache(path)
            r = CWMResult(STATUS_OK, "cwm", 10, 1, 9, 5, (2, 3))
            c.put("k", r)
            c.put("t", CWMResult("timeout", "cwm", 10))  # not persisted
            with open(path, "a") as f:
                f.write('{"key": "broken"')  # torn write
            c2 = ResultCache(path)
            self.assertEqual(c2.get("k"), r)
            self.assertIsNone(c2.get("t"))
            self.assertEqual(len(c2), 1)


@unittest.skipUnless(HAVE_BIN, "solve_cwm binary or DAG instances not available")
class TestRealBinary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = CWMRunner()
        cls.dag = DAG_DIR / "atacseq200.dot"
        cls.profile = _real_profile()

    def test_heft_makespan(self):
        self.assertEqual(self.runner.heft_makespan(self.dag), 168)

    def test_cwm_ok_and_per_interval_consistent(self):
        r = self.runner.solve(self.dag, self.profile, 252, seed=1)
        self.assertEqual(r.status, STATUS_OK, r.message)
        self.assertLessEqual(r.makespan, 252)
        self.assertEqual(len(r.per_interval), self.profile["number_of_intervals"])
        self.assertEqual(sum(r.per_interval), r.carbon_cost)
        # total energy covers at least the idle power over every interval
        iv = self.profile["intervals"]
        for e, a, b in zip(r.per_interval_energy, iv, iv[1:]):
            self.assertGreaterEqual(e, 16854 * (b - a))
        # matches the frozen baseline value for this instance (see Phase 1 audit)
        self.assertEqual(r.carbon_cost, 213553)

    def test_heft_scheduler_matches_reference(self):
        # reference: deploy/main prints HEFT-SL carbon 554437 for seed 42 on DE24s
        r = self.runner.solve(self.dag, self.profile, 5000, seed=42, scheduler="heft")
        self.assertEqual(r.status, STATUS_OK, r.message)
        self.assertEqual((r.makespan, r.carbon_cost), (168, 554437))

    def test_infeasible_deadline(self):
        r = self.runner.solve(self.dag, self.profile, 100, seed=1, scheduler="heft")
        self.assertEqual(r.status, STATUS_INFEASIBLE)

    def test_cache_hit_skips_binary(self):
        with tempfile.TemporaryDirectory() as d:
            runner = CWMRunner(cache=ResultCache(Path(d) / "c.jsonl"))
            a = runner.solve(self.dag, self.profile, 5000, seed=42, scheduler="heft")
            runner.solve_bin = Path("/nonexistent")  # would fail if invoked
            b = runner.solve(self.dag, self.profile, 5000, seed=42, scheduler="heft")
            self.assertEqual(a, b)

    def test_input_validation(self):
        with self.assertRaises(CWMRunnerError):
            self.runner.solve(self.dag, self.profile, 0)
        with self.assertRaises(CWMRunnerError):
            self.runner.solve(self.dag, self.profile, self.profile["horizon"] + 1)
        bad = dict(self.profile, budgets=[b + 0.5 for b in self.profile["budgets"]])
        with self.assertRaises(CWMRunnerError):
            self.runner.solve(self.dag, bad, 252)
        with self.assertRaises(CWMRunnerError):
            self.runner.solve(DAG_DIR / "nope.dot", self.profile, 252)

    def test_configuration_errors(self):
        with self.assertRaises(CWMRunnerError):
            CWMRunner(variant="medium")
        with self.assertRaises(CWMRunnerError):
            CWMRunner(cluster_json=DEFAULT_CLUSTER.with_name("missing.json"))


@unittest.skipUnless(HAVE_BIN, "solve_cwm not built")
class TestDeterminism(unittest.TestCase):
    """Regression test for the out-of-bounds read in mapper.cpp (sweep line past the profile horizon).

    Before the fix, this exact instance (synthetic CI, Frankfurt, atacseq200, D = 336, seed 42)
    returned brown energy 6222 in ~80 % of runs and 5673 otherwise.
    """

    def test_same_input_same_schedule(self):
        from cwm_multidc.data_loader import build_topology
        from cwm_multidc.profile_shifting import truncate_profile

        topo = build_topology(24, DEFAULT_CLUSTER, dcs=(("DC_Frankfurt", "DE"), ("DC_Oslo", "NO"),
                                                        ("DC_Warsaw", "PL")), start_hour=6)
        power, _ = topo.profiles("DC_Frankfurt")
        profile = truncate_profile(power, 336)
        runner = CWMRunner()  # no cache: every call runs the binary
        dag = DAG_DIR / "atacseq200.dot"
        results = {(r.status, r.makespan, r.carbon_cost, tuple(r.per_interval or ())) for r in (runner.solve(dag, profile, 336, seed=42)
                                                                    for _ in range(6))}
        self.assertEqual(len(results), 1, f"solve_cwm gave different results for the same input: {results}")
        self.assertEqual(next(iter(results))[2], 6222)


class TestCacheFailures(unittest.TestCase):
    """Regression: an interrupted run once cached solver crashes (status "error") as if they were real."""

    def test_failures_neither_persisted_nor_reused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cache.jsonl"
            c = ResultCache(path)
            c.put("bad", CWMResult("error", "cwm", 10, message=""))
            c.put("slow", CWMResult("timeout", "cwm", 10))
            c.put("good", CWMResult(STATUS_INFEASIBLE, "cwm", 10))
            self.assertIsNone(c.get("bad"))
            # an old cache file that already contains a failure must not resurrect it
            with open(path, "a") as f:
                f.write(json.dumps({"key": "old", "result": CWMResult("error", "cwm", 10).to_json()}) + "\n")
            reloaded = ResultCache(path)
            self.assertIsNone(reloaded.get("old"))
            self.assertIsNone(reloaded.get("bad"))
            self.assertEqual(reloaded.get("good").status, STATUS_INFEASIBLE)


if __name__ == "__main__":
    unittest.main()
