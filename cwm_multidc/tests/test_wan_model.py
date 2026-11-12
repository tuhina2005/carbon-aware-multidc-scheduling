"""Automated unit tests for cwm_multidc.wan_model."""

import math
import unittest
from cwm_multidc.wan_model import (
    WANConfig,
    WANTransferResult,
    SchedulingObjectiveResult,
    calculate_transfer_duration,
    calculate_arrival_time,
    calculate_network_energy,
    calculate_network_emissions,
    integrate_piecewise_carbon_intensity,
    evaluate_wan_transfer,
    combine_objectives,
)


class TestWANModel(unittest.TestCase):
    """Test suite covering the WAN transfer and emissions model."""

    # --------------------------------------------------------------------------
    # 1. Transfer duration with known values and units
    # --------------------------------------------------------------------------
    def test_01_transfer_duration_known_values(self):
        """Test transfer duration using hand-calculated values (1 TB at 1 Gbps).

        Synthetic Parameters:
            - Data size: 1000 GB (1 TB in decimal SI convention: 1000 * 8 * 10^9 bits).
            - Bandwidth: 1.0 Gbps (10^9 bits/second).
            - Throughput efficiency: 1.0 (ideal 100% throughput).
            - Rate: 1.0 * 10^9 / (8 * 10^9) = 0.125 GB/s (125 MB/s).
            - Expected duration: 1000 / 0.125 = 8000.0 seconds (~2.22 hours).
        """
        duration = calculate_transfer_duration(
            data_size_gb=1000.0,
            bandwidth_gbps=1.0,
            throughput_efficiency=1.0,
            unit_convention="decimal",
        )
        self.assertAlmostEqual(duration, 8000.0, places=4)

        # Test with 95% efficiency
        # Rate: 0.125 * 0.95 = 0.11875 GB/s
        # Expected duration: 1000 / 0.11875 = 8421.0526... seconds
        duration_eff = calculate_transfer_duration(
            data_size_gb=1000.0,
            bandwidth_gbps=1.0,
            throughput_efficiency=0.95,
            unit_convention="decimal",
        )
        self.assertAlmostEqual(duration_eff, 1000.0 / 0.11875, places=4)

        # Test binary GiB convention:
        # 1024 GiB at 1 Gbps, 1.0 efficiency:
        # Total bits = 1024 * 8 * 1024^3 = 8,796,093,022,208 bits
        # Rate = 10^9 bits/s
        # Expected duration = 8796.0930... seconds
        duration_bin = calculate_transfer_duration(
            data_size_gb=1024.0,
            bandwidth_gbps=1.0,
            throughput_efficiency=1.0,
            unit_convention="binary",
        )
        self.assertAlmostEqual(duration_bin, (1024.0 * 8 * (1024**3)) / 1e9, places=4)

    # --------------------------------------------------------------------------
    # 2. Arrival-time calculation
    # --------------------------------------------------------------------------
    def test_02_arrival_time_calculation(self):
        """Test continuous and discrete arrival times under start-time offsets."""
        # Transfer start at t=500.0s, duration 1200.0s -> arrival 1700.0s
        t_cont, t_int = calculate_arrival_time(transfer_start=500.0, duration=1200.0)
        self.assertEqual(t_cont, 1700.0)
        self.assertEqual(t_int, 1700)

        # Non-zero float arrival
        t_cont2, t_int2 = calculate_arrival_time(transfer_start=15.2, duration=30.3, integer_policy="ceil")
        self.assertAlmostEqual(t_cont2, 45.5, places=4)
        self.assertEqual(t_int2, 46)

    # --------------------------------------------------------------------------
    # 3. Invalid bandwidth and dataset size
    # --------------------------------------------------------------------------
    def test_03_invalid_bandwidth_and_data_size(self):
        """Ensure negative or zero bandwidth, negative data size, or bad efficiency raise errors."""
        # Negative data size
        with self.assertRaises(ValueError):
            calculate_transfer_duration(data_size_gb=-10.0, bandwidth_gbps=1.0)

        # Zero bandwidth
        with self.assertRaises(ValueError):
            calculate_transfer_duration(data_size_gb=100.0, bandwidth_gbps=0.0)

        # Negative bandwidth
        with self.assertRaises(ValueError):
            calculate_transfer_duration(data_size_gb=100.0, bandwidth_gbps=-2.5)

        # Invalid efficiency (0.0 or > 1.0)
        with self.assertRaises(ValueError):
            calculate_transfer_duration(data_size_gb=100.0, bandwidth_gbps=1.0, throughput_efficiency=0.0)
        with self.assertRaises(ValueError):
            calculate_transfer_duration(data_size_gb=100.0, bandwidth_gbps=1.0, throughput_efficiency=1.05)

        # Invalid arrival time inputs
        with self.assertRaises(ValueError):
            calculate_arrival_time(transfer_start=-5.0, duration=10.0)
        with self.assertRaises(ValueError):
            calculate_arrival_time(transfer_start=5.0, duration=-1.0)

    # --------------------------------------------------------------------------
    # 4. Same-DC transfer (no WAN transfer required)
    # --------------------------------------------------------------------------
    def test_04_same_dc_transfer(self):
        """When destination DC equals source DC, data is already local."""
        cfg = WANConfig(bandwidth_gbps=1.0, energy_intensity_kwh_per_gb=0.02)
        res = evaluate_wan_transfer(
            source_dc="DC_Frankfurt",
            dest_dc="DC_Frankfurt",
            data_size_gb=5000.0,  # 5 TB
            transfer_start=200.0,
            config=cfg,
            source_ci_gco2_per_kwh=400.0,
            dest_ci_gco2_per_kwh=400.0,
        )

        self.assertTrue(res.is_same_dc)
        self.assertEqual(res.transfer_duration_seconds, 0.0)
        self.assertEqual(res.network_energy_kwh, 0.0)
        self.assertEqual(res.network_energy_joules, 0.0)
        self.assertEqual(res.network_emissions_gco2, 0.0)
        self.assertEqual(res.arrival_time_seconds, 200.0)
        self.assertEqual(res.effective_arrival_time_int, 200)

    # --------------------------------------------------------------------------
    # 5. Network energy calculation
    # --------------------------------------------------------------------------
    def test_05_network_energy_calculation(self):
        """Test network energy formula: Energy = Data * Intensity."""
        # 1000 GB with energy intensity 0.02 kWh/GB (synthetic literature hypothesis)
        # Expected: 20.0 kWh = 20.0 * 3.6e6 J = 72,000,000 Joules (72 MJ)
        kwh, joules = calculate_network_energy(data_size_gb=1000.0, energy_intensity_kwh_per_gb=0.02)
        self.assertAlmostEqual(kwh, 20.0, places=4)
        self.assertAlmostEqual(joules, 72.0e6, places=1)

        # Zero data size
        kwh_zero, joules_zero = calculate_network_energy(data_size_gb=0.0)
        self.assertEqual(kwh_zero, 0.0)
        self.assertEqual(joules_zero, 0.0)

        # Negative data size raises ValueError
        with self.assertRaises(ValueError):
            calculate_network_energy(data_size_gb=-5.0)

    # --------------------------------------------------------------------------
    # 6. Piecewise-constant carbon-intensity integration
    # --------------------------------------------------------------------------
    def test_06_piecewise_carbon_intensity_integration(self):
        """Test time-weighted carbon intensity across multiple hourly intervals."""
        # Synthetic Intervals: [0, 200, 400, 600]
        # Carbon intensities: [100.0, 200.0, 300.0] gCO2/kWh
        # Transfer window: [100, 500] (duration 400s)
        # Overlap with interval 0 [0, 200): [100, 200) -> 100s * 100 = 10000
        # Overlap with interval 1 [200, 400): [200, 400) -> 200s * 200 = 40000
        # Overlap with interval 2 [400, 600): [400, 500) -> 100s * 300 = 30000
        # Total CI-time = 80000; Average CI = 80000 / 400 = 200.0 gCO2/kWh
        intervals = [0, 200, 400, 600]
        ci_values = [100.0, 200.0, 300.0]

        avg_ci = integrate_piecewise_carbon_intensity(
            start_time=100.0,
            end_time=500.0,
            intervals=intervals,
            carbon_intensities=ci_values,
        )
        self.assertAlmostEqual(avg_ci, 200.0, places=4)

        # Test full evaluate_wan_transfer with time_varying_ci_profile
        cfg = WANConfig(bandwidth_gbps=8.0, energy_intensity_kwh_per_gb=0.01, throughput_efficiency=1.0)
        # Data size: 400s * (8.0 Gbps / 8) = 400 GB
        res = evaluate_wan_transfer(
            source_dc="DC_A",
            dest_dc="DC_B",
            data_size_gb=400.0,
            transfer_start=100.0,
            config=cfg,
            time_varying_ci_profile={"intervals": intervals, "ci": ci_values},
        )
        self.assertAlmostEqual(res.transfer_duration_seconds, 400.0, places=4)
        self.assertAlmostEqual(res.avg_carbon_intensity_gco2_per_kwh, 200.0, places=4)
        # Energy: 400 GB * 0.01 kWh/GB = 4.0 kWh
        self.assertAlmostEqual(res.network_energy_kwh, 4.0, places=4)
        # Emissions: 4.0 kWh * 200.0 gCO2/kWh = 800.0 gCO2
        self.assertAlmostEqual(res.network_emissions_gco2, 800.0, places=4)

    # --------------------------------------------------------------------------
    # 7. Zero duration and boundary conditions
    # --------------------------------------------------------------------------
    def test_07_zero_duration_and_boundaries(self):
        """Zero data size results in zero duration and zero emissions."""
        cfg = WANConfig()
        dur = calculate_transfer_duration(data_size_gb=0.0, bandwidth_gbps=1.0)
        self.assertEqual(dur, 0.0)

        # Instantaneous CI check when start == end
        intervals = [0, 100, 200]
        ci_values = [50.0, 80.0]
        ci_inst = integrate_piecewise_carbon_intensity(
            start_time=50.0, end_time=50.0, intervals=intervals, carbon_intensities=ci_values
        )
        self.assertEqual(ci_inst, 50.0)

        # End time before start time raises ValueError
        with self.assertRaises(ValueError):
            integrate_piecewise_carbon_intensity(
                start_time=150.0, end_time=100.0, intervals=intervals, carbon_intensities=ci_values
            )

    # --------------------------------------------------------------------------
    # 8. Fractional transfer duration and integer-arrival policy
    # --------------------------------------------------------------------------
    def test_08_fractional_duration_policies(self):
        """Test ceil, round, and floor policies on fractional durations.

        Transfer: 100 GB over 3 Gbps (rate = 0.375 GB/s)
        Duration: 100 / 0.375 = 266.666666... s
        Start: 10.0 s -> Continuous arrival: 276.666666... s
        """
        dur = calculate_transfer_duration(data_size_gb=100.0, bandwidth_gbps=3.0, throughput_efficiency=1.0)
        self.assertAlmostEqual(dur, 266.6666666666667, places=5)

        # Ceil policy: 276.666... -> 277
        _, arr_ceil = calculate_arrival_time(transfer_start=10.0, duration=dur, integer_policy="ceil")
        self.assertEqual(arr_ceil, 277)

        # Floor policy: 276.666... -> 276
        _, arr_floor = calculate_arrival_time(transfer_start=10.0, duration=dur, integer_policy="floor")
        self.assertEqual(arr_floor, 276)

        # Round policy: 276.666... -> 277
        _, arr_round = calculate_arrival_time(transfer_start=10.0, duration=dur, integer_policy="round")
        self.assertEqual(arr_round, 277)

    # --------------------------------------------------------------------------
    # 9. Objective component separation and unit correctness
    # --------------------------------------------------------------------------
    def test_09_objective_component_separation(self):
        """Ensure CWM raw excess brown energy is strictly separated from network gCO2 emissions.

        Do NOT add raw Watt-seconds directly to grams of CO2.
        """
        cfg = WANConfig(bandwidth_gbps=1.0, energy_intensity_kwh_per_gb=0.02)
        wan_res = evaluate_wan_transfer(
            source_dc="DC1",
            dest_dc="DC2",
            data_size_gb=1000.0,
            transfer_start=0.0,
            config=cfg,
            source_ci_gco2_per_kwh=400.0,
            dest_ci_gco2_per_kwh=200.0,
        )
        # Network energy = 20 kWh, CI = 300 gCO2/kWh -> Network emissions = 6000 gCO2
        self.assertAlmostEqual(wan_res.network_emissions_gco2, 6000.0, places=2)

        # Raw CWM cost returned from C++ binary: 355000 (Watt-seconds)
        raw_cwm_cost = 355000

        # Case A: Conversion factors omitted / uncalibrated
        # Quantities MUST remain separate; compute_emissions and total_emissions must be None
        obj_separated = combine_objectives(wan_result=wan_res, cwm_excess_brown_energy=raw_cwm_cost)
        self.assertEqual(obj_separated.cwm_excess_brown_energy, 355000)
        self.assertEqual(obj_separated.network_emissions_gco2, 6000.0)
        self.assertIsNone(obj_separated.compute_emissions_gco2)
        self.assertIsNone(obj_separated.total_emissions_gco2)
        self.assertIn("not computed", obj_separated.compute_emissions_note)

        # Case B: Physical conversion calibrated
        # 1 Watt-second = 1 / 3,600,000 kWh
        # Power factor = 1e-3 kW/W, Time factor = 1/3600 h/s -> factor = 1 / 3.6e6
        # Compute energy = 355000 / 3.6e6 = 0.0986111... kWh
        # Dest CI = 200.0 gCO2/kWh
        # Compute emissions = 0.0986111... * 200 = 19.7222... gCO2
        # Total emissions = 6000.0 + 19.7222... = 6019.7222... gCO2
        obj_calibrated = combine_objectives(
            wan_result=wan_res,
            cwm_excess_brown_energy=raw_cwm_cost,
            dest_avg_ci_gco2_per_kwh=200.0,
            power_to_kw_factor=0.001,
            time_to_hours_factor=1.0 / 3600.0,
        )
        expected_compute_emissions = (355000.0 / 3.6e6) * 200.0
        self.assertIsNotNone(obj_calibrated.compute_emissions_gco2)
        self.assertAlmostEqual(obj_calibrated.compute_emissions_gco2, expected_compute_emissions, places=3)
        self.assertAlmostEqual(
            obj_calibrated.total_emissions_gco2, 6000.0 + expected_compute_emissions, places=3
        )

    # --------------------------------------------------------------------------
    # 10. Invalid and missing configuration
    # --------------------------------------------------------------------------
    def test_10_invalid_and_missing_configuration(self):
        """Test configuration invariants and validation."""
        # Non-positive bandwidth
        with self.assertRaises(ValueError):
            WANConfig(bandwidth_gbps=0.0)

        # Negative energy intensity
        with self.assertRaises(ValueError):
            WANConfig(energy_intensity_kwh_per_gb=-0.01)

        # Invalid efficiency
        with self.assertRaises(ValueError):
            WANConfig(throughput_efficiency=0.0)

        # Invalid unit convention
        with self.assertRaises(ValueError):
            WANConfig(unit_convention="terabytes")

        # Invalid arrival policy
        with self.assertRaises(ValueError):
            WANConfig(integer_arrival_policy="nearest_decade")

        # Empty data centre names
        with self.assertRaises(ValueError):
            evaluate_wan_transfer(source_dc="", dest_dc="DC2", data_size_gb=100.0)
        with self.assertRaises(ValueError):
            evaluate_wan_transfer(source_dc="DC1", dest_dc="   ", data_size_gb=100.0)


if __name__ == "__main__":
    unittest.main()
