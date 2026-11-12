"""Power-profile shifting module for CWM multi-data-centre scheduling.

In single-cluster CWM, workflow execution is assumed to begin at relative time t = 0.
When an input dataset is transferred across a WAN to a destination data centre, computation
cannot begin until the transfer completes at absolute arrival time T_arrival.

This module shifts the destination data centre's green power-budget profile leftward by
T_arrival so that CWM can execute natively starting from relative time t' = 0 (which
corresponds to absolute time T_arrival), preserving exact budget values across all
remaining intervals.
"""

from __future__ import annotations

import copy
import math
from bisect import bisect_left, bisect_right
from typing import Any, Mapping


def validate_profile(profile: Mapping[str, Any]) -> None:
    """Validate that a profile dictionary conforms to CWM's expected schema and semantics.

    Args:
        profile: Dictionary containing horizon, number_of_intervals, intervals, and budgets.

    Raises:
        TypeError: If fields have incorrect types.
        ValueError: If fields violate structural or numerical invariants.
    """
    if not isinstance(profile, Mapping):
        raise TypeError(f"Profile must be a mapping/dict, got {type(profile).__name__}")

    required_keys = ("horizon", "number_of_intervals", "intervals", "budgets")
    for k in required_keys:
        if k not in profile:
            raise ValueError(f"Profile missing required key: '{k}'")

    horizon = profile["horizon"]
    num_intervals = profile["number_of_intervals"]
    intervals = profile["intervals"]
    budgets = profile["budgets"]

    if not isinstance(horizon, (int, float)) or horizon <= 0:
        raise ValueError(f"'horizon' must be a positive number, got {horizon}")

    if not isinstance(num_intervals, int) or num_intervals <= 0:
        raise ValueError(f"'number_of_intervals' must be a positive integer, got {num_intervals}")

    if not isinstance(intervals, list):
        raise TypeError(f"'intervals' must be a list, got {type(intervals).__name__}")

    if not isinstance(budgets, list):
        raise TypeError(f"'budgets' must be a list, got {type(budgets).__name__}")

    if len(intervals) != num_intervals + 1:
        raise ValueError(
            f"Length of 'intervals' ({len(intervals)}) must equal 'number_of_intervals' + 1 ({num_intervals + 1})"
        )

    if len(budgets) != num_intervals:
        raise ValueError(
            f"Length of 'budgets' ({len(budgets)}) must equal 'number_of_intervals' ({num_intervals})"
        )

    if intervals[0] != 0:
        raise ValueError(f"First interval boundary must be 0, got {intervals[0]}")

    if intervals[-1] != horizon:
        raise ValueError(
            f"Last interval boundary ({intervals[-1]}) must match horizon ({horizon})"
        )

    for i in range(len(intervals) - 1):
        if intervals[i] >= intervals[i + 1]:
            raise ValueError(
                f"Interval boundaries must be strictly increasing: intervals[{i}]={intervals[i]} >= intervals[{i+1}]={intervals[i+1]}"
            )

    for i, b in enumerate(budgets):
        if not isinstance(b, (int, float)):
            raise TypeError(f"Budget at index {i} must be numeric, got {type(b).__name__}")
        if b < 0:
            raise ValueError(f"Budget at index {i} cannot be negative, got {b}")


def shift_profile(
    profile: Mapping[str, Any],
    arrival_time: int | float,
    required_deadline: int | float | None = None,
    discretize: str = "ceil",
) -> dict[str, Any]:
    """Shift a power-budget profile leftward by arrival_time.

    The returned profile begins at relative time t' = 0, which corresponds to absolute
    arrival time T_arrival. Any portion of the profile before arrival_time is discarded.
    The active interval covering arrival_time has its start truncated to arrival_time,
    and all subsequent interval boundaries are shifted by arrival_time.

    Args:
        profile: The original data centre power profile dict. Remains unmodified.
        arrival_time: Non-negative timestamp when workflow computation starts.
        required_deadline: Optional positive deadline (in relative time units). If the
            remaining profile horizon is strictly less than required_deadline, an error
            is raised instead of returning an insufficient profile.
        discretize: Policy for handling floating-point arrival times:
            - 'ceil' (default): Round arrival time up to the next integer. This represents
              the safest scheduling assumption (never underestimates WAN transfer duration)
              and guarantees all interval boundaries are integers as required by CWM C++.
            - 'round': Round arrival time to the nearest integer.
            - 'exact': Require arrival_time to already be an exact integer.

    Returns:
        A new profile dictionary conforming to CWM's schema, with timeline starting at 0.

    Raises:
        ValueError: If arrival_time is negative, exceeds horizon, or remaining horizon is
            insufficient for required_deadline.
        TypeError: If input profile is malformed or types are invalid.
    """
    validate_profile(profile)

    if not isinstance(arrival_time, (int, float)):
        raise TypeError(f"arrival_time must be numeric, got {type(arrival_time).__name__}")

    if arrival_time < 0:
        raise ValueError(f"arrival_time cannot be negative, got {arrival_time}")

    # Handle floating-point arrival times according to discretization policy
    if isinstance(arrival_time, float):
        if arrival_time.is_integer():
            T_arr = int(arrival_time)
        elif discretize == "ceil":
            T_arr = math.ceil(arrival_time)
        elif discretize == "round":
            T_arr = round(arrival_time)
        elif discretize == "exact":
            raise ValueError(
                f"arrival_time {arrival_time} is fractional, but discretize='exact' requires integer timestamps"
            )
        else:
            raise ValueError(f"Unknown discretization policy: '{discretize}'. Use 'ceil', 'round', or 'exact'")
    else:
        T_arr = arrival_time

    horizon = profile["horizon"]
    intervals: list[int] = profile["intervals"]
    budgets: list[float] = profile["budgets"]

    if T_arr >= horizon:
        raise ValueError(
            f"arrival_time ({T_arr}) meets or exceeds profile horizon ({horizon}); insufficient horizon remaining"
        )

    remaining_horizon = horizon - T_arr

    if required_deadline is not None:
        if required_deadline <= 0:
            raise ValueError(f"required_deadline must be positive, got {required_deadline}")
        if remaining_horizon < required_deadline:
            raise ValueError(
                f"Remaining horizon ({remaining_horizon}) is less than required deadline ({required_deadline})"
            )

    # Edge case: arrival_time == 0 requires no shifting
    if T_arr == 0:
        return copy.deepcopy(dict(profile))

    # Find interval index j* such that intervals[j*] <= T_arr < intervals[j*+1]
    # bisect_right returns insertion point i such that intervals[i-1] <= T_arr < intervals[i]
    j_star = bisect_right(intervals, T_arr) - 1

    # Shifted interval boundaries:
    # Relative time 0 corresponds to absolute time T_arr.
    # The active interval j* ends at absolute time intervals[j*+1], which is
    # intervals[j*+1] - T_arr in relative time.
    # All subsequent original boundaries are shifted by T_arr.
    shifted_intervals = [0] + [t - T_arr for t in intervals[j_star + 1 :]]
    shifted_budgets = copy.deepcopy(budgets[j_star:])
    num_shifted_intervals = len(shifted_budgets)

    shifted_profile = {
        "horizon": remaining_horizon,
        "number_of_intervals": num_shifted_intervals,
        "intervals": shifted_intervals,
        "budgets": shifted_budgets,
    }

    validate_profile(shifted_profile)
    return shifted_profile


def truncate_profile(profile: Mapping[str, Any], horizon: int) -> dict[str, Any]:
    """Truncate a profile so that it ends exactly at ``horizon`` (spec Sec. 3.7, step 4).

    CWM integrates max(0, P(t) - G(t)) over *every* interval of the profile, including
    idle power after the makespan.  Leaving the profile longer than the effective
    deadline D' would therefore make the reported cost depend on how much horizon
    happens to remain after T_arrival.  Truncating to D' fixes the integration window
    to [0, D').

    Args:
        profile: A valid CWM profile (starting at 0).
        horizon: New positive integer horizon, <= profile['horizon'].

    Returns:
        New profile whose last interval is cut at ``horizon``.
    """
    validate_profile(profile)
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon <= 0:
        raise ValueError(f"horizon must be a positive integer, got {horizon!r}")
    if horizon > profile["horizon"]:
        raise ValueError(
            f"cannot extend profile: requested horizon {horizon} > {profile['horizon']}"
        )
    intervals = profile["intervals"]
    # number of intervals that start strictly before the new horizon (bisect_left counts
    # boundaries < horizon; correct for integer AND fractional boundaries)
    n = bisect_left(intervals, horizon)
    n = max(1, min(n, len(profile["budgets"])))
    new_intervals = list(intervals[:n]) + [horizon]
    out = {
        "horizon": horizon,
        "number_of_intervals": n,
        "intervals": new_intervals,
        "budgets": copy.deepcopy(list(profile["budgets"][:n])),
    }
    validate_profile(out)
    return out
