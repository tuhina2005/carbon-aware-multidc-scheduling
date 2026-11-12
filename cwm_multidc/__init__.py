"""CWM Multi-Data-Centre Extension Package."""

from .profile_shifting import shift_profile, truncate_profile, validate_profile
from .wan_model import (
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

__all__ = [
    "shift_profile",
    "truncate_profile",
    "validate_profile",
    "WANConfig",
    "WANTransferResult",
    "SchedulingObjectiveResult",
    "calculate_transfer_duration",
    "calculate_arrival_time",
    "calculate_network_energy",
    "calculate_network_emissions",
    "integrate_piecewise_carbon_intensity",
    "evaluate_wan_transfer",
    "combine_objectives",
]
