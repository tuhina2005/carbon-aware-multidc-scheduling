"""Automated unit tests for cwm_multidc.profile_shifting."""

import copy
import json
import os
import unittest
from cwm_multidc.profile_shifting import shift_profile, validate_profile


class TestProfileShifting(unittest.TestCase):
    """Test suite covering all operational cases and invariants for profile shifting."""

    def setUp(self):
        """Set up small synthetic profiles with hand-calculated expected outputs."""
        # Synthetic Uniform Profile: 3 intervals of duration 30, horizon 90
        # Interval 0: [0, 30), budget 100
        # Interval 1: [30, 60), budget 250
        # Interval 2: [60, 90), budget 50
        self.uniform_profile = {
            "horizon": 90,
            "number_of_intervals": 3,
            "intervals": [0, 30, 60, 90],
            "budgets": [100, 250, 50],
        }

        # Synthetic Nonuniform Profile: intervals of duration 15, 40, 5, 40 (horizon 100)
        # Interval 0: [0, 15), budget 500
        # Interval 1: [15, 55), budget 1200
        # Interval 2: [55, 60), budget 800
        # Interval 3: [60, 100), budget 300
        self.nonuniform_profile = {
            "horizon": 100,
            "number_of_intervals": 4,
            "intervals": [0, 15, 55, 60, 100],
            "budgets": [500, 1200, 800, 300],
        }

    # --------------------------------------------------------------------------
    # 1. Arrival at time zero
    # --------------------------------------------------------------------------
    def test_01_arrival_at_zero(self):
        """Arrival at t=0 leaves timeline, horizon, and budgets identical."""
        shifted = shift_profile(self.uniform_profile, arrival_time=0)
        self.assertEqual(shifted["horizon"], 90)
        self.assertEqual(shifted["number_of_intervals"], 3)
        self.assertEqual(shifted["intervals"], [0, 30, 60, 90])
        self.assertEqual(shifted["budgets"], [100, 250, 50])

    # --------------------------------------------------------------------------
    # 2. Arrival inside the first interval
    # --------------------------------------------------------------------------
    def test_02_arrival_inside_first_interval(self):
        """Arrival at t=10 cuts the first interval from [0, 30) to [0, 20) with same budget."""
        shifted = shift_profile(self.uniform_profile, arrival_time=10)
        # Expected:
        # Relative interval 0: [0, 20), budget 100 (remainder of [10, 30))
        # Relative interval 1: [20, 50), budget 250 (original [30, 60))
        # Relative interval 2: [50, 80), budget 50 (original [60, 90))
        # Horizon: 90 - 10 = 80
        self.assertEqual(shifted["horizon"], 80)
        self.assertEqual(shifted["number_of_intervals"], 3)
        self.assertEqual(shifted["intervals"], [0, 20, 50, 80])
        self.assertEqual(shifted["budgets"], [100, 250, 50])

    # --------------------------------------------------------------------------
    # 3. Arrival inside a later interval
    # --------------------------------------------------------------------------
    def test_03_arrival_inside_later_interval(self):
        """Arrival at t=45 cuts interval 1 from [30, 60) to [0, 15) and drops interval 0."""
        shifted = shift_profile(self.uniform_profile, arrival_time=45)
        # Interval 0 [0, 30) is entirely in past.
        # Active interval 1 [30, 60) remainder is [45, 60) -> relative [0, 15), budget 250
        # Active interval 2 [60, 90) -> relative [15, 45), budget 50
        # Horizon: 90 - 45 = 45
        self.assertEqual(shifted["horizon"], 45)
        self.assertEqual(shifted["number_of_intervals"], 2)
        self.assertEqual(shifted["intervals"], [0, 15, 45])
        self.assertEqual(shifted["budgets"], [250, 50])

    # --------------------------------------------------------------------------
    # 4. Arrival exactly on an interval boundary
    # --------------------------------------------------------------------------
    def test_04_arrival_on_interval_boundary(self):
        """Arrival exactly at t=30 drops interval 0; relative t=0 starts interval 1."""
        shifted = shift_profile(self.uniform_profile, arrival_time=30)
        # Active interval 1 [30, 60) -> relative [0, 30), budget 250
        # Active interval 2 [60, 90) -> relative [30, 60), budget 50
        # Horizon: 90 - 30 = 60
        self.assertEqual(shifted["horizon"], 60)
        self.assertEqual(shifted["number_of_intervals"], 2)
        self.assertEqual(shifted["intervals"], [0, 30, 60])
        self.assertEqual(shifted["budgets"], [250, 50])

    # --------------------------------------------------------------------------
    # 5. Arrival close to the horizon end
    # --------------------------------------------------------------------------
    def test_05_arrival_close_to_horizon_end(self):
        """Arrival at t=85 leaves only the tail 5 time units of the final interval."""
        shifted = shift_profile(self.uniform_profile, arrival_time=85)
        # Only remainder of interval 2 [85, 90) remains -> relative [0, 5), budget 50
        self.assertEqual(shifted["horizon"], 5)
        self.assertEqual(shifted["number_of_intervals"], 1)
        self.assertEqual(shifted["intervals"], [0, 5])
        self.assertEqual(shifted["budgets"], [50])

    # --------------------------------------------------------------------------
    # 6. Arrival at or beyond the horizon
    # --------------------------------------------------------------------------
    def test_06_arrival_at_or_beyond_horizon(self):
        """Arrival at horizon (t=90) or beyond (t=100) must raise ValueError."""
        with self.assertRaises(ValueError) as ctx1:
            shift_profile(self.uniform_profile, arrival_time=90)
        self.assertIn("insufficient horizon", str(ctx1.exception))

        with self.assertRaises(ValueError) as ctx2:
            shift_profile(self.uniform_profile, arrival_time=120)
        self.assertIn("insufficient horizon", str(ctx2.exception))

    # --------------------------------------------------------------------------
    # 7. Nonuniform intervals
    # --------------------------------------------------------------------------
    def test_07_nonuniform_intervals(self):
        """Shift correctly preserves varying durations in nonuniform profiles."""
        # Nonuniform: [0, 15, 55, 60, 100], budgets: [500, 1200, 800, 300]
        # Arrival at t=25: inside interval 1 [15, 55)
        # Remainder of interval 1: [25, 55) -> duration 30, relative [0, 30), budget 1200
        # Interval 2: [55, 60) -> duration 5, relative [30, 35), budget 800
        # Interval 3: [60, 100) -> duration 40, relative [35, 75), budget 300
        # Horizon: 100 - 25 = 75
        shifted = shift_profile(self.nonuniform_profile, arrival_time=25)
        self.assertEqual(shifted["horizon"], 75)
        self.assertEqual(shifted["number_of_intervals"], 3)
        self.assertEqual(shifted["intervals"], [0, 30, 35, 75])
        self.assertEqual(shifted["budgets"], [1200, 800, 300])

    # --------------------------------------------------------------------------
    # 8. Input profile remains unchanged (immutability)
    # --------------------------------------------------------------------------
    def test_08_input_profile_unmodified(self):
        """Shifting must not mutate the input dictionary or its nested lists."""
        orig_copy = copy.deepcopy(self.uniform_profile)
        _ = shift_profile(self.uniform_profile, arrival_time=40)
        self.assertEqual(self.uniform_profile, orig_copy)

    # --------------------------------------------------------------------------
    # 9. Output schema is validated and accepted by validate_profile
    # --------------------------------------------------------------------------
    def test_09_output_schema_validity(self):
        """Every generated shifted profile strictly satisfies CWM profile invariants."""
        for arrival in [0, 5, 15, 30, 55, 59, 99]:
            shifted = shift_profile(self.nonuniform_profile, arrival_time=arrival)
            validate_profile(shifted)
            self.assertEqual(shifted["intervals"][0], 0)
            self.assertEqual(shifted["intervals"][-1], shifted["horizon"])
            self.assertEqual(len(shifted["intervals"]), shifted["number_of_intervals"] + 1)
            self.assertEqual(len(shifted["budgets"]), shifted["number_of_intervals"])

    # --------------------------------------------------------------------------
    # 10. Invalid input and insufficient-horizon behavior
    # --------------------------------------------------------------------------
    def test_10_invalid_inputs_and_insufficient_horizon(self):
        """Test negative arrival time, invalid types, and required_deadline guard."""
        # Negative arrival time
        with self.assertRaises(ValueError):
            shift_profile(self.uniform_profile, arrival_time=-1)

        # Insufficient horizon for required deadline
        # Horizon is 90, arrival is 50 -> remaining horizon is 40. Required deadline is 50.
        with self.assertRaises(ValueError) as ctx:
            shift_profile(self.uniform_profile, arrival_time=50, required_deadline=50)
        self.assertIn("Remaining horizon (40) is less than required deadline (50)", str(ctx.exception))

        # Sufficient horizon for required deadline (40 >= 30) succeeds
        shifted = shift_profile(self.uniform_profile, arrival_time=50, required_deadline=30)
        self.assertEqual(shifted["horizon"], 40)

        # Malformed profile (missing key)
        bad_profile = {"horizon": 50, "intervals": [0, 50], "budgets": [100]}
        with self.assertRaises(ValueError):
            shift_profile(bad_profile, arrival_time=10)

    # --------------------------------------------------------------------------
    # 11. Discretization of floating-point arrival times
    # --------------------------------------------------------------------------
    def test_11_fractional_arrival_times(self):
        """Test discretization policies ('ceil', 'round', 'exact') for float WAN delays."""
        # Arrival at t=12.2: ceil -> 13
        shifted_ceil = shift_profile(self.uniform_profile, arrival_time=12.2, discretize="ceil")
        self.assertEqual(shifted_ceil["intervals"], [0, 17, 47, 77])
        self.assertEqual(shifted_ceil["horizon"], 77)

        # Arrival at t=12.2: round -> 12
        shifted_round = shift_profile(self.uniform_profile, arrival_time=12.2, discretize="round")
        self.assertEqual(shifted_round["intervals"], [0, 18, 48, 78])
        self.assertEqual(shifted_round["horizon"], 78)

        # Arrival at t=12.2 with discretize='exact' must raise ValueError
        with self.assertRaises(ValueError):
            shift_profile(self.uniform_profile, arrival_time=12.2, discretize="exact")

        # Exact float 12.0 works under discretize='exact'
        shifted_exact = shift_profile(self.uniform_profile, arrival_time=12.0, discretize="exact")
        self.assertEqual(shifted_exact["horizon"], 78)

    # --------------------------------------------------------------------------
    # 12. Integration with solve_cwm C++ executable
    # --------------------------------------------------------------------------
    def test_12_cwm_binary_integration(self):
        """Verify that a shifted profile generated from real dataset is accepted by solve_cwm."""
        import subprocess, tempfile

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        solve_cwm_bin = os.path.join(repo_root, "code_cwm", "code", "deploy", "solve_cwm")
        dag_path = os.path.join(repo_root, "code_cwm", "experiments", "reproduce", "instances", "DAGs", "atacseq.dot")
        cluster_path = os.path.join(repo_root, "code_cwm", "experiments", "reproduce", "instances", "cluster_processors.json")
        profile_path = os.path.join(repo_root, "code_cwm", "experiments", "reproduce", "instances", "Profiles", "small", "DE24s.json")

        if not (os.path.exists(solve_cwm_bin) and os.path.exists(dag_path) and os.path.exists(profile_path)):
            self.skipTest("CWM binary or test instances not found; skipping binary integration test.")

        with open(profile_path) as f:
            real_profile = json.load(f)

        # Shift real profile by arrival_time = 1200
        shifted = shift_profile(real_profile, arrival_time=1200, required_deadline=3000)
        validate_profile(shifted)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(shifted, tmp)
            tmp_path = tmp.name

        try:
            cmd = [solve_cwm_bin, dag_path, cluster_path, "small", tmp_path, "3000", "42"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"solve_cwm failed with stderr: {res.stderr}")
            parts = res.stdout.strip().split(",")
            self.assertEqual(len(parts), 3, f"Unexpected stdout format: {res.stdout}")
            elapsed_ms, makespan, carbon = int(parts[0]), int(parts[1]), int(parts[2])
            self.assertGreaterEqual(elapsed_ms, 0)
            self.assertGreater(makespan, 0)
            self.assertLessEqual(makespan, 3000)
            self.assertGreaterEqual(carbon, 0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()

