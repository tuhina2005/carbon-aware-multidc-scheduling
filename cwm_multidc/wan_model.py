"""WAN transfer and carbon emissions model for CWM multi-data-centre scheduling.

This module models:
1. Wide-Area Network (WAN) transfer latency and arrival time when transferring an input
   dataset from a source data centre to a destination data centre.
2. Network energy consumption based on data volume and energy intensity.
3. Network carbon emissions based on endpoint-average or time-varying carbon intensity.
4. Transparent separation of network metrics from CWM's single-cluster excess-brown-energy
   metric, preventing dimensionally incompatible additions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class WANConfig:
    """Configuration parameters for WAN data transfer and energy/carbon estimation.

    Parameters:
        bandwidth_gbps: Nominal network bandwidth between data centres in Gigabits per second
            (Gbps, 10^9 bits/second). Must be positive.
        energy_intensity_kwh_per_gb: Network energy intensity coefficient in kilowatt-hours
            per Gigabyte (kWh/GB). Default is 0.02 kWh/GB (72 kJ/GB).
            NOTE: This is a configurable research hypothesis/synthetic parameter derived from
            networking literature surveys (e.g. Aslan et al. 2018), not an empirical measurement
            of any specific physical WAN.
        throughput_efficiency: Effective throughput utilization factor in (0.0, 1.0] accounting
            for TCP/IP framing, congestion control, and transport overhead. Default is 0.95.
        unit_convention: Data size unit convention:
            - 'decimal' (default): 1 GB = 10^9 bytes = 8 * 10^9 bits.
            - 'binary': 1 GiB = 2^30 bytes = 8 * 2^30 bits.
        integer_arrival_policy: Policy for discretizing arrival times into integer timestamps
            for CWM solver compatibility:
            - 'ceil' (default): Round up to next integer timestamp. Conservative; ensures CWM
              never schedules compute before transfer has physically completed.
            - 'round': Round to nearest integer timestamp.
            - 'floor': Round down to previous integer timestamp (not recommended for strict precedence).
    """

    bandwidth_gbps: float = 1.0
    energy_intensity_kwh_per_gb: float = 0.02
    throughput_efficiency: float = 0.95
    unit_convention: str = "decimal"
    integer_arrival_policy: str = "ceil"

    def __post_init__(self) -> None:
        if self.bandwidth_gbps <= 0:
            raise ValueError(f"bandwidth_gbps must be positive, got {self.bandwidth_gbps}")
        if self.energy_intensity_kwh_per_gb < 0:
            raise ValueError(
                f"energy_intensity_kwh_per_gb cannot be negative, got {self.energy_intensity_kwh_per_gb}"
            )
        if not (0.0 < self.throughput_efficiency <= 1.0):
            raise ValueError(
                f"throughput_efficiency must be in (0.0, 1.0], got {self.throughput_efficiency}"
            )
        if self.unit_convention not in ("decimal", "binary"):
            raise ValueError(
                f"unit_convention must be 'decimal' or 'binary', got '{self.unit_convention}'"
            )
        if self.integer_arrival_policy not in ("ceil", "round", "floor"):
            raise ValueError(
                f"integer_arrival_policy must be 'ceil', 'round', or 'floor', got '{self.integer_arrival_policy}'"
            )


@dataclass(frozen=True)
class WANTransferResult:
    """Result of a WAN data transfer calculation.

    All units are explicit and SI-consistent.
    """

    source_dc: str
    dest_dc: str
    is_same_dc: bool
    data_size_gb: float
    effective_bandwidth_gbps: float
    transfer_duration_seconds: float
    transfer_start_seconds: float
    arrival_time_seconds: float
    effective_arrival_time_int: int
    network_energy_kwh: float
    network_energy_joules: float
    network_emissions_gco2: float
    avg_carbon_intensity_gco2_per_kwh: float


@dataclass(frozen=True)
class SchedulingObjectiveResult:
    """Composite scheduling objective separating physical components.

    In CWM, the solver returns a raw integer metric: excess brown energy integrated over the
    schedule in power-units * time-units (e.g. Watt-seconds or kW-seconds above budget).
    It is NOT in grams of CO2.

    This class maintains strict dimensional integrity between network and compute metrics.
    """

    network_energy_kwh: float
    network_emissions_gco2: float
    cwm_excess_brown_energy: int
    cwm_energy_unit: str = "Watt x CWM time unit above green budget"
    compute_emissions_gco2: float | None = None
    compute_emissions_note: str = ""
    total_emissions_gco2: float | None = None


def calculate_transfer_duration(
    data_size_gb: float,
    bandwidth_gbps: float,
    throughput_efficiency: float = 1.0,
    unit_convention: str = "decimal",
) -> float:
    """Calculate the physical duration of a WAN data transfer in seconds.

    Formula:
        Duration = DataBits / EffectiveThroughputBitsPerSecond

    Args:
        data_size_gb: Dataset volume in Gigabytes (or GiB if binary convention).
        bandwidth_gbps: Nominal link bandwidth in Gbps (10^9 bits/second).
        throughput_efficiency: Protocol and framing efficiency factor in (0.0, 1.0].
        unit_convention: 'decimal' (1 GB = 10^9 bytes) or 'binary' (1 GiB = 2^30 bytes).

    Returns:
        Transfer duration in seconds as a floating-point number.

    Raises:
        ValueError: If data_size_gb < 0, bandwidth_gbps <= 0, or efficiency not in (0, 1].
    """
    if data_size_gb < 0:
        raise ValueError(f"data_size_gb cannot be negative, got {data_size_gb}")
    if data_size_gb == 0:
        return 0.0

    if bandwidth_gbps <= 0:
        raise ValueError(f"bandwidth_gbps must be positive, got {bandwidth_gbps}")
    if not (0.0 < throughput_efficiency <= 1.0):
        raise ValueError(
            f"throughput_efficiency must be in (0.0, 1.0], got {throughput_efficiency}"
        )

    if unit_convention == "decimal":
        # 1 GB = 10^9 bytes = 8 * 10^9 bits
        total_bits = data_size_gb * 8.0 * 1e9
    elif unit_convention == "binary":
        # 1 GiB = 2^30 bytes = 8 * 2^30 bits
        total_bits = data_size_gb * 8.0 * (1024**3)
    else:
        raise ValueError(f"Unknown unit_convention: '{unit_convention}'")

    effective_throughput_bps = bandwidth_gbps * 1e9 * throughput_efficiency
    return total_bits / effective_throughput_bps


def calculate_arrival_time(
    transfer_start: float,
    duration: float,
    integer_policy: str = "ceil",
) -> tuple[float, int]:
    """Calculate the continuous arrival time and the effective integer arrival timestamp.

    Args:
        transfer_start: Non-negative timestamp when data transfer begins (seconds).
        duration: Non-negative duration of the transfer (seconds).
        integer_policy: 'ceil' (default), 'round', or 'floor'.

    Returns:
        A tuple of (arrival_time_continuous, arrival_time_integer).

    Raises:
        ValueError: If transfer_start < 0 or duration < 0.
    """
    if transfer_start < 0:
        raise ValueError(f"transfer_start cannot be negative, got {transfer_start}")
    if duration < 0:
        raise ValueError(f"duration cannot be negative, got {duration}")

    t_arr_cont = transfer_start + duration

    if integer_policy == "ceil":
        t_arr_int = math.ceil(t_arr_cont)
    elif integer_policy == "round":
        t_arr_int = round(t_arr_cont)
    elif integer_policy == "floor":
        t_arr_int = math.floor(t_arr_cont)
    else:
        raise ValueError(f"Unknown integer_policy: '{integer_policy}'")

    return t_arr_cont, t_arr_int


def calculate_network_energy(
    data_size_gb: float,
    energy_intensity_kwh_per_gb: float = 0.02,
) -> tuple[float, float]:
    """Calculate network energy consumed by data transfer.

    Args:
        data_size_gb: Transferred volume in Gigabytes.
        energy_intensity_kwh_per_gb: Energy coefficient (kWh/GB). Default: 0.02.

    Returns:
        Tuple of (energy_kwh, energy_joules).
        1 kWh = 3.6 * 10^6 Joules.
    """
    if data_size_gb < 0:
        raise ValueError(f"data_size_gb cannot be negative, got {data_size_gb}")
    if energy_intensity_kwh_per_gb < 0:
        raise ValueError(
            f"energy_intensity_kwh_per_gb cannot be negative, got {energy_intensity_kwh_per_gb}"
        )

    energy_kwh = data_size_gb * energy_intensity_kwh_per_gb
    energy_joules = energy_kwh * 3.6e6
    return energy_kwh, energy_joules


def calculate_network_emissions(
    network_energy_kwh: float,
    carbon_intensity_gco2_per_kwh: float,
) -> float:
    """Calculate network carbon emissions in grams of CO2 (gCO2).

    Formula:
        Emissions (gCO2) = Energy (kWh) * CarbonIntensity (gCO2/kWh)

    Args:
        network_energy_kwh: Total energy in kWh.
        carbon_intensity_gco2_per_kwh: Average carbon intensity in gCO2/kWh.

    Returns:
        Emissions in gCO2.
    """
    if network_energy_kwh < 0:
        raise ValueError(f"network_energy_kwh cannot be negative, got {network_energy_kwh}")
    if carbon_intensity_gco2_per_kwh < 0:
        raise ValueError(
            f"carbon_intensity_gco2_per_kwh cannot be negative, got {carbon_intensity_gco2_per_kwh}"
        )

    return network_energy_kwh * carbon_intensity_gco2_per_kwh


def integrate_piecewise_carbon_intensity(
    start_time: float,
    end_time: float,
    intervals: Sequence[float | int],
    carbon_intensities: Sequence[float],
) -> float:
    """Compute the time-weighted average carbon intensity across a piecewise constant profile.

    Args:
        start_time: Window start timestamp (seconds).
        end_time: Window end timestamp (seconds). Must be >= start_time.
        intervals: Array of interval boundaries [t_0, t_1, ..., t_M] with intervals[0] <= start_time.
        carbon_intensities: Array of carbon intensities for each interval [CI_0, ..., CI_{M-1}].

    Returns:
        Time-weighted average carbon intensity in gCO2/kWh across [start_time, end_time].
        If start_time == end_time, returns the instantaneous carbon intensity at start_time.
    """
    if start_time < 0:
        raise ValueError(f"start_time cannot be negative, got {start_time}")
    if end_time < start_time:
        raise ValueError(f"end_time ({end_time}) must be >= start_time ({start_time})")
    if len(intervals) != len(carbon_intensities) + 1:
        raise ValueError(
            f"len(intervals) ({len(intervals)}) must equal len(carbon_intensities) + 1 ({len(carbon_intensities) + 1})"
        )

    # The window must lie inside the profile: uncovered time has no defined CI and
    # silently treating it as CI = 0 would underestimate emissions.
    if start_time < intervals[0] or end_time > intervals[-1]:
        raise ValueError(
            f"window [{start_time}, {end_time}] is not covered by CI profile "
            f"[{intervals[0]}, {intervals[-1]}]"
        )

    # Zero-duration case: instantaneous CI at start_time, using the same
    # left-closed [b_j, e_j) interval convention as CWM.
    if start_time == end_time:
        for i in range(len(carbon_intensities)):
            if intervals[i] <= start_time < intervals[i + 1]:
                return float(carbon_intensities[i])
        # start_time == intervals[-1]: right end of the profile
        return float(carbon_intensities[-1])

    total_duration = end_time - start_time
    total_ci_time = 0.0

    for i, ci in enumerate(carbon_intensities):
        int_start = intervals[i]
        int_end = intervals[i + 1]

        # Overlap between [start_time, end_time] and [int_start, int_end]
        overlap_start = max(start_time, int_start)
        overlap_end = min(end_time, int_end)

        if overlap_end > overlap_start:
            overlap_duration = overlap_end - overlap_start
            total_ci_time += overlap_duration * ci

    return total_ci_time / total_duration


def evaluate_wan_transfer(
    source_dc: str,
    dest_dc: str,
    data_size_gb: float,
    transfer_start: float = 0.0,
    config: WANConfig | None = None,
    source_ci_gco2_per_kwh: float | None = None,
    dest_ci_gco2_per_kwh: float | None = None,
    time_varying_ci_profile: Mapping[str, Any] | None = None,
) -> WANTransferResult:
    """Evaluate WAN transfer duration, energy, and emissions for moving data from source to dest.

    If source_dc == dest_dc, no network transfer occurs:
        - transfer_duration = 0.0
        - network_energy = 0.0
        - network_emissions = 0.0
        - effective_arrival_time = ceil(transfer_start)

    Args:
        source_dc: Identifier of the source data centre where workflow data originates.
        dest_dc: Identifier of the candidate execution data centre.
        data_size_gb: Dataset volume in Gigabytes.
        transfer_start: Transfer launch timestamp (seconds from workflow submission).
        config: WANConfig options. If None, default WANConfig() is used.
        source_ci_gco2_per_kwh: Constant carbon intensity at source DC (gCO2/kWh).
        dest_ci_gco2_per_kwh: Constant carbon intensity at dest DC (gCO2/kWh).
        time_varying_ci_profile: Optional dict with 'intervals' and 'ci' lists for time-varying WAN CI.

    Returns:
        A WANTransferResult containing SI-consistent metrics.
    """
    if config is None:
        config = WANConfig()

    if not isinstance(source_dc, str) or not source_dc.strip():
        raise ValueError("source_dc must be a non-empty string")
    if not isinstance(dest_dc, str) or not dest_dc.strip():
        raise ValueError("dest_dc must be a non-empty string")

    is_same_dc = source_dc.strip().lower() == dest_dc.strip().lower()

    if is_same_dc or data_size_gb == 0:
        # Same-DC transfer: data is already local, no WAN latency or emissions incurred
        duration = 0.0
        t_arr_cont, t_arr_int = calculate_arrival_time(
            transfer_start, duration, integer_policy=config.integer_arrival_policy
        )
        return WANTransferResult(
            source_dc=source_dc,
            dest_dc=dest_dc,
            is_same_dc=is_same_dc,
            data_size_gb=data_size_gb,
            effective_bandwidth_gbps=config.bandwidth_gbps * config.throughput_efficiency,
            transfer_duration_seconds=0.0,
            transfer_start_seconds=transfer_start,
            arrival_time_seconds=t_arr_cont,
            effective_arrival_time_int=t_arr_int,
            network_energy_kwh=0.0,
            network_energy_joules=0.0,
            network_emissions_gco2=0.0,
            avg_carbon_intensity_gco2_per_kwh=0.0,
        )

    # Inter-DC transfer across WAN
    duration = calculate_transfer_duration(
        data_size_gb=data_size_gb,
        bandwidth_gbps=config.bandwidth_gbps,
        throughput_efficiency=config.throughput_efficiency,
        unit_convention=config.unit_convention,
    )

    t_arr_cont, t_arr_int = calculate_arrival_time(
        transfer_start=transfer_start,
        duration=duration,
        integer_policy=config.integer_arrival_policy,
    )

    energy_kwh, energy_joules = calculate_network_energy(
        data_size_gb=data_size_gb,
        energy_intensity_kwh_per_gb=config.energy_intensity_kwh_per_gb,
    )

    # Determine average carbon intensity across the WAN link
    if time_varying_ci_profile is not None:
        avg_ci = integrate_piecewise_carbon_intensity(
            start_time=transfer_start,
            end_time=t_arr_cont,
            intervals=time_varying_ci_profile["intervals"],
            carbon_intensities=time_varying_ci_profile["ci"],
        )
    elif source_ci_gco2_per_kwh is not None and dest_ci_gco2_per_kwh is not None:
        # Endpoint average: (CI_source + CI_dest) / 2
        avg_ci = (source_ci_gco2_per_kwh + dest_ci_gco2_per_kwh) / 2.0
    elif dest_ci_gco2_per_kwh is not None:
        avg_ci = dest_ci_gco2_per_kwh
    elif source_ci_gco2_per_kwh is not None:
        avg_ci = source_ci_gco2_per_kwh
    else:
        raise ValueError(
            "Inter-DC transfer requires carbon intensity: pass time_varying_ci_profile "
            "or source/dest constant CI (refusing to silently report 0 gCO2)"
        )

    emissions_gco2 = calculate_network_emissions(energy_kwh, avg_ci)

    return WANTransferResult(
        source_dc=source_dc,
        dest_dc=dest_dc,
        is_same_dc=False,
        data_size_gb=data_size_gb,
        effective_bandwidth_gbps=config.bandwidth_gbps * config.throughput_efficiency,
        transfer_duration_seconds=duration,
        transfer_start_seconds=transfer_start,
        arrival_time_seconds=t_arr_cont,
        effective_arrival_time_int=t_arr_int,
        network_energy_kwh=energy_kwh,
        network_energy_joules=energy_joules,
        network_emissions_gco2=emissions_gco2,
        avg_carbon_intensity_gco2_per_kwh=avg_ci,
    )


def combine_objectives(
    wan_result: WANTransferResult,
    cwm_excess_brown_energy: int,
    dest_avg_ci_gco2_per_kwh: float | None = None,
    power_to_kw_factor: float | None = None,
    time_to_hours_factor: float | None = None,
) -> SchedulingObjectiveResult:
    """Structure the multi-DC scheduling objective with explicit dimensional separation.

    Warning on Incompatible Quantities:
        The raw integer returned by CWM (`cwm_excess_brown_energy`) is in (power units * time units),
        e.g., Watt-seconds above the green power budget. It is NOT grams of CO2.
        Adding raw `cwm_excess_brown_energy` directly to `network_emissions_gco2` is dimensionally
        invalid.

    If calibration factors (`dest_avg_ci_gco2_per_kwh`, `power_to_kw_factor`, `time_to_hours_factor`)
    are provided, a defensible physical compute emissions estimate is calculated:
        Compute_kWh = cwm_excess_brown_energy * power_to_kw_factor * time_to_hours_factor
        Compute_gCO2 = Compute_kWh * dest_avg_ci_gco2_per_kwh
        Total_gCO2 = network_emissions_gco2 + Compute_gCO2

    Otherwise, `compute_emissions_gco2` and `total_emissions_gco2` remain `None`, preventing
    incompatible additions.
    """
    if cwm_excess_brown_energy < 0:
        raise ValueError(
            f"cwm_excess_brown_energy cannot be negative, got {cwm_excess_brown_energy}"
        )

    # Check if a defensible physical conversion is possible
    if (
        dest_avg_ci_gco2_per_kwh is not None
        and power_to_kw_factor is not None
        and time_to_hours_factor is not None
    ):
        if dest_avg_ci_gco2_per_kwh < 0:
            raise ValueError("dest_avg_ci_gco2_per_kwh cannot be negative")
        if power_to_kw_factor <= 0 or time_to_hours_factor <= 0:
            raise ValueError("conversion factors must be positive")

        compute_energy_kwh = (
            cwm_excess_brown_energy * power_to_kw_factor * time_to_hours_factor
        )
        compute_emissions_gco2 = compute_energy_kwh * dest_avg_ci_gco2_per_kwh
        total_emissions_gco2 = (
            wan_result.network_emissions_gco2 + compute_emissions_gco2
        )
        note = (
            f"Converted using power factor {power_to_kw_factor} kW/unit, "
            f"time factor {time_to_hours_factor} h/unit, "
            f"and dest CI {dest_avg_ci_gco2_per_kwh} gCO2/kWh."
        )
    else:
        compute_emissions_gco2 = None
        total_emissions_gco2 = None
        note = (
            "Physical compute emissions not computed: conversion factors from CWM raw excess "
            "brown energy (Watt x CWM time unit) to kWh/gCO2 were not fully specified. Quantities kept separate."
        )

    return SchedulingObjectiveResult(
        network_energy_kwh=wan_result.network_energy_kwh,
        network_emissions_gco2=wan_result.network_emissions_gco2,
        cwm_excess_brown_energy=cwm_excess_brown_energy,
        cwm_energy_unit="Watt x CWM time unit above green power budget",
        compute_emissions_gco2=compute_emissions_gco2,
        compute_emissions_note=note,
        total_emissions_gco2=total_emissions_gco2,
    )
