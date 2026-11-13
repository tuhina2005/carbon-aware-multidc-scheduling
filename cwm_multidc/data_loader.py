"""Multi-DC data pipeline: carbon-intensity timeseries -> aligned CWM power-budget profiles.

Design decisions (agreed in Phase 2):

1. **Time scale.**  CWM works in integer *time units*.  We fix ``units_per_hour = 30``
   (one hourly CI sample = one CWM interval of exactly 30 units, i.e. 120 s/unit), which
   matches the mean interval length [10, 50] of the original CWM profiles.  Every
   conversion between seconds and CWM units goes through :class:`TimeScale`.

2. **One absolute clock.**  t = 0 is the submission instant, which is aligned to a UTC
   hour boundary.  All DCs share that clock, so the WAN CI ``(CI_src(t) + CI_dst(t)) / 2``
   is evaluated on simultaneous samples.

3. **Global CI -> budget mapping** (identical for every DC):
       G(t) = P_idle + max(0, 1 - CI(t) / CI_hi) * f * P_dyn
   with P_idle = sum of all idle powers (compute + links), P_dyn = sum of all work
   powers, f = 0.2 (small) / 0.4 (large) as in the CWM paper, and CI_hi = 800 gCO2/kWh.
   Because G >= P_idle, idle power is never charged as brown energy, and a cleaner grid
   always yields a larger budget — budgets are comparable across DCs (unlike the
   per-profile min-max rescaling of the original CWM instances).

4. **Data.**  :func:`load_electricitymaps_csv` reads Electricity Maps hourly exports.
   When no real data is available, :func:`synthetic_ci` produces *synthetic* diurnal
   series calibrated to approximate 2024 annual means.  Synthetic data is for
   development only and every record built from it is tagged ``synthetic=True``.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .profile_shifting import validate_profile

SECONDS_PER_HOUR = 3600.0


# ----------------------------------------------------------------------------- time
@dataclass(frozen=True)
class TimeScale:
    """Mapping between wall-clock seconds and CWM integer time units."""

    units_per_hour: int = 30

    def __post_init__(self) -> None:
        if not isinstance(self.units_per_hour, int) or self.units_per_hour <= 0:
            raise ValueError(f"units_per_hour must be a positive int, got {self.units_per_hour!r}")

    @property
    def seconds_per_unit(self) -> float:
        return SECONDS_PER_HOUR / self.units_per_hour

    def seconds_to_units_ceil(self, seconds: float) -> int:
        """Conservative conversion: data never 'arrives' earlier than physically possible.

        A tiny tolerance absorbs float noise so that e.g. 3600.0000000001 s -> 30 units.
        """
        if seconds < 0:
            raise ValueError(f"seconds must be >= 0, got {seconds}")
        u = seconds / self.seconds_per_unit
        return int(math.ceil(u - 1e-9))

    def units_to_seconds(self, units: float) -> float:
        return units * self.seconds_per_unit

    def units_to_hours(self, units: float) -> float:
        return units / self.units_per_hour

    def watt_units_to_kwh(self, watt_units: float) -> float:
        """CWM excess energy (W x unit) -> kWh."""
        return watt_units * self.seconds_per_unit / 3.6e6


# ------------------------------------------------------------------------ CI data
@dataclass(frozen=True)
class CITimeSeries:
    """Hourly carbon intensity (gCO2/kWh); sample i covers [i h, (i+1) h) after ``start_utc``."""

    region: str
    values: tuple[float, ...]
    start_utc: str = "2024-01-01T00:00:00Z"
    synthetic: bool = False
    source: str = ""

    def __post_init__(self) -> None:
        if len(self.values) == 0:
            raise ValueError("empty CI series")
        if any((not math.isfinite(v)) or v < 0 for v in self.values):
            raise ValueError(f"CI series for {self.region} contains negative/non-finite values")

    def __len__(self) -> int:
        return len(self.values)

    def window(self, start_hour: int, hours: int) -> "CITimeSeries":
        if start_hour < 0 or start_hour + hours > len(self.values):
            raise ValueError(
                f"window [{start_hour}, {start_hour + hours}) outside series of {len(self.values)} h for {self.region}"
            )
        return CITimeSeries(self.region, self.values[start_hour:start_hour + hours],
                            f"{self.start_utc}+{start_hour}h", self.synthetic, self.source)

    def mean(self, hours: float | None = None) -> float:
        """Mean CI over the first ``hours`` hours (fractional last hour weighted)."""
        if hours is None:
            return float(np.mean(self.values))
        if hours <= 0:
            raise ValueError("hours must be positive")
        full = int(math.floor(hours))
        if hours > len(self.values):
            raise ValueError("mean window longer than series")
        tot = sum(self.values[:full])
        frac = hours - full
        if frac > 0:
            tot += frac * self.values[full]
        return tot / hours


_EM_TIME_COLS = ("Datetime (UTC)", "datetime", "Datetime")
_EM_CI_COLS = (
    "Carbon Intensity gCO₂eq/kWh (LCA)",
    "Carbon intensity gCO₂eq/kWh (Life cycle)",
    "Carbon Intensity gCO₂eq/kWh (direct)",
    "Carbon intensity gCO₂eq/kWh (direct)",
    "carbon_intensity",
)


def load_electricitymaps_csv(path: str | Path, region: str | None = None, column: str | None = None) -> CITimeSeries:
    """Load an Electricity Maps hourly CSV export (one row per UTC hour).

    Gaps are not interpolated silently: a missing/blank value raises.  Rows must be
    consecutive hours (checked on the timestamp column when parseable).
    """
    import datetime as _dt

    path = Path(path)
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"{path}: no rows")
    cols = rows[0].keys()
    tcol = next((c for c in _EM_TIME_COLS if c in cols), None)
    ccol = column or next((c for c in _EM_CI_COLS if c in cols), None)
    if ccol is None or ccol not in cols:
        raise ValueError(f"{path}: no carbon-intensity column among {list(cols)}")
    vals: list[float] = []
    prev = None
    for i, r in enumerate(rows):
        raw = (r.get(ccol) or "").strip()
        if raw == "":
            raise ValueError(f"{path}: missing CI value at row {i + 2}")
        vals.append(float(raw))
        if tcol:
            ts = _dt.datetime.fromisoformat(r[tcol].strip().replace("Z", "+00:00"))
            if prev is not None and (ts - prev) != _dt.timedelta(hours=1):
                raise ValueError(f"{path}: non-hourly step between rows {i + 1} and {i + 2}")
            prev = ts
    region = region or (rows[0].get("Zone Id") or rows[0].get("Country") or path.stem)
    start = rows[0][tcol].strip() if tcol else "unknown"
    return CITimeSeries(region, tuple(vals), start, synthetic=False, source=str(path))


# Approximate 2024 annual-mean grid CI (gCO2/kWh, Electricity Maps order of magnitude),
# UTC offset of local solar noon, and diurnal solar-dip depth.  SYNTHETIC calibration.
SYNTHETIC_REGIONS: dict[str, dict[str, float]] = {
    "NO": {"mean": 30.0, "utc_offset": 1, "solar_dip": 0.03, "noise": 0.10},
    "FR": {"mean": 45.0, "utc_offset": 1, "solar_dip": 0.12, "noise": 0.20},
    "DE": {"mean": 350.0, "utc_offset": 1, "solar_dip": 0.35, "noise": 0.18},
    "PL": {"mean": 650.0, "utc_offset": 1, "solar_dip": 0.12, "noise": 0.08},
    "US-CAL": {"mean": 220.0, "utc_offset": -8, "solar_dip": 0.50, "noise": 0.10},
    "IN": {"mean": 650.0, "utc_offset": 5.5, "solar_dip": 0.15, "noise": 0.05},
}


def synthetic_ci(region: str, hours: int, seed: int = 0, start_utc_hour: int = 0) -> CITimeSeries:
    """Synthetic hourly CI: annual mean x (1 - solar dip around local noon) x AR(1) noise.

    The solar term is a clipped cosine that is zero at night and peaks at local noon;
    the series is renormalised to the region's target mean.  Deterministic in ``seed``.
    """
    if region not in SYNTHETIC_REGIONS:
        raise ValueError(f"unknown synthetic region {region!r}; known: {sorted(SYNTHETIC_REGIONS)}")
    if hours <= 0:
        raise ValueError("hours must be positive")
    p = SYNTHETIC_REGIONS[region]
    rng = np.random.default_rng(_stable_seed(region, seed))  # stable across processes
    h = np.arange(hours) + start_utc_hour + 0.5
    local = (h + p["utc_offset"]) % 24.0
    solar = np.clip(np.cos((local - 12.0) / 12.0 * math.pi * 1.6), 0.0, None)  # ~ 7:30-16:30
    shape = 1.0 - p["solar_dip"] * solar
    # AR(1) multi-hour weather noise (wind), phi = 0.9
    eps = rng.normal(0.0, p["noise"] * math.sqrt(1 - 0.81), size=hours)
    ar = np.zeros(hours)
    for i in range(hours):
        ar[i] = (0.9 * ar[i - 1] if i else 0.0) + eps[i]
    series = shape * np.exp(ar)
    series = series / series.mean() * p["mean"]
    return CITimeSeries(region, tuple(float(round(v, 3)) for v in series),
                        f"synthetic+{start_utc_hour}h", synthetic=True, source=f"synthetic_ci(seed={seed})")


def perturb_ci(series: CITimeSeries, sigma: float, seed: int = 0, phi: float = 0.8) -> CITimeSeries:
    """CI *forecast* = actual x exp(e_t), with e_t a zero-mean AR(1) of marginal std ``sigma``.

    Used to evaluate decisions taken on forecasts against realised CI.  sigma = 0 returns
    the series unchanged (oracle forecast).
    """
    if sigma < 0 or not (0 <= phi < 1):
        raise ValueError("sigma must be >= 0 and 0 <= phi < 1")
    if sigma == 0:
        return series
    rng = np.random.default_rng(_stable_seed("forecast:" + series.region, seed))
    n = len(series)
    e = np.empty(n)
    e[0] = rng.normal(0.0, sigma)
    innov = sigma * math.sqrt(1 - phi * phi)
    for i in range(1, n):
        e[i] = phi * e[i - 1] + rng.normal(0.0, innov)
    vals = np.asarray(series.values) * np.exp(e - sigma * sigma / 2)  # mean-preserving
    return CITimeSeries(series.region, tuple(float(v) for v in vals), series.start_utc,
                        series.synthetic, f"{series.source}+forecast(sigma={sigma},seed={seed})")


def with_ci(topo: "Topology", transform) -> "Topology":
    """New topology with every DC's CI series replaced by ``transform(series)``."""
    from dataclasses import replace as _replace

    dcs = tuple(_replace(d, ci=transform(d.ci)) for d in topo.dcs)  # keeps bandwidth and hardware
    return Topology(topo.source, dcs, topo.cluster, topo.timescale, topo.mapping, topo.cluster_json)


def _stable_seed(region: str, seed: int) -> int:
    import zlib

    return (zlib.crc32(region.encode()) ^ (seed * 2654435761)) % (2**32)


# --------------------------------------------------------------------- clusters
@dataclass(frozen=True)
class ClusterPower:
    """Aggregate power figures of a CWM cluster variant (CWM power units, i.e. W)."""

    variant: str
    p_idle: int  # compute idle + link idle (CWM 'basePower')
    p_dyn: int  # all compute work powers + all link work powers

    @classmethod
    def from_cluster_json(cls, path: str | Path, variant: str = "small") -> "ClusterPower":
        with open(path) as f:
            c = json.load(f)
        for cl in c["clusters"]:
            if cl["cluster_id"] == variant:
                n = cl["processors_per_type"]
                idle = sum(p["idle_power"] for p in c["processors"]) * n + sum(cl["communication_idle_powers"])
                work = sum(p["work_power"] for p in c["processors"]) * n + sum(cl["communication_work_powers"])
                return cls(variant, int(idle), int(work))
        raise ValueError(f"cluster variant {variant!r} not in {path}")


@dataclass(frozen=True)
class BudgetMapping:
    """Global, DC-independent CI -> green power budget mapping (see module docstring)."""

    ci_hi: float = 800.0
    green_fraction: float | None = None  # default: 0.2 small / 0.4 large (CWM paper)

    def fraction(self, variant: str) -> float:
        if self.green_fraction is not None:
            return self.green_fraction
        return {"small": 0.2, "large": 0.4}[variant]

    def budget(self, ci: float, cluster: ClusterPower) -> int:
        g = cluster.p_idle + max(0.0, 1.0 - ci / self.ci_hi) * self.fraction(cluster.variant) * cluster.p_dyn
        return int(math.floor(g))


# ---------------------------------------------------------------------- profiles
def ci_to_profiles(
    ci: CITimeSeries,
    cluster: ClusterPower,
    timescale: TimeScale,
    mapping: BudgetMapping = BudgetMapping(),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build an hourly CWM power profile and the matching CI profile (both in CWM units).

    Returns ``(power_profile, ci_profile)``; both have identical ``intervals`` so the
    CI profile can be shifted/truncated with exactly the same functions, which keeps
    per-interval excess energy and per-interval CI aligned by construction.
    """
    u = timescale.units_per_hour
    n = len(ci)
    intervals = [i * u for i in range(n + 1)]
    power = {
        "horizon": n * u,
        "number_of_intervals": n,
        "intervals": intervals,
        "budgets": [mapping.budget(v, cluster) for v in ci.values],
    }
    ci_prof = {
        "horizon": n * u,
        "number_of_intervals": n,
        "intervals": list(intervals),
        "budgets": [float(v) for v in ci.values],  # 'budgets' field reused to carry CI
    }
    validate_profile(power)
    validate_profile(ci_prof)
    return power, ci_prof


def wan_ci_profile_seconds(src: CITimeSeries, dst: CITimeSeries) -> dict[str, list[float]]:
    """Endpoint-average WAN CI ``(CI_src + CI_dst)/2`` on an hourly grid in **seconds**.

    Format matches :func:`cwm_multidc.wan_model.evaluate_wan_transfer`'s
    ``time_varying_ci_profile`` argument.
    """
    n = min(len(src), len(dst))
    return {
        "intervals": [i * SECONDS_PER_HOUR for i in range(n + 1)],
        "ci": [(a + b) / 2.0 for a, b in zip(src.values[:n], dst.values[:n])],
    }


# ------------------------------------------------------------------- topology
@dataclass(frozen=True)
class HardwareTier:
    """A DC's hardware: processor mix (CWM cluster file; None = the shared cluster) and PUE."""

    name: str
    cluster_json: str | Path | None = None
    pue: float = 1.0


@dataclass(frozen=True)
class DataCentre:
    name: str
    region: str
    ci: CITimeSeries
    bandwidth_gbps: float = 1.0  # from the source DC
    # Optional per-DC hardware (a CWM cluster file, variant "small").  None = the topology's shared
    # cluster, which keeps the homogeneous model (and its solver-cache keys) exactly as before.
    cluster_json: str | None = None
    cluster: "ClusterPower | None" = None
    hardware: str = ""  # label, e.g. "efficient" / "standard" / "legacy"
    # Facility power usage effectiveness: grid energy = PUE x IT energy.  1.0 (IT only) is the
    # baseline model.  Applied to compute energy after the solver runs; this is exact when the
    # DC's green budget scales with its facility power (excess and dynamic energy scale by PUE).
    pue: float = 1.0
    # Contention: hours a job waits in this DC's queue if it arrives during hour i of the series
    # (same clock as ``ci``).  None = no queue (the baseline model).
    queue_hours: tuple[float, ...] | None = None

    @property
    def synthetic(self) -> bool:
        return self.ci.synthetic


@dataclass(frozen=True)
class Topology:
    """Candidate DCs on one absolute clock.  ``source`` must be one of ``dcs``."""

    source: str
    dcs: tuple[DataCentre, ...]
    cluster: ClusterPower
    timescale: TimeScale = TimeScale()
    mapping: BudgetMapping = BudgetMapping()
    cluster_json: str = ""
    _profiles: dict = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        names = [d.name for d in self.dcs]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate DC names: {names}")
        if self.source not in names:
            raise ValueError(f"source DC {self.source!r} not among candidates {names}")
        lens = {len(d.ci) for d in self.dcs}
        if len(lens) != 1:
            raise ValueError(f"CI series must have equal length (shared clock), got {sorted(lens)}")

    @property
    def hours(self) -> int:
        return len(self.dcs[0].ci)

    def dc(self, name: str) -> DataCentre:
        for d in self.dcs:
            if d.name == name:
                return d
        raise KeyError(name)

    @property
    def source_dc(self) -> DataCentre:
        return self.dc(self.source)

    def cluster_of(self, name: str) -> "ClusterPower":
        """Power figures of DC ``name``'s hardware (its own cluster, else the shared one)."""
        return self.dc(name).cluster or self.cluster

    def cluster_json_of(self, name: str) -> str:
        return self.dc(name).cluster_json or self.cluster_json

    @property
    def heterogeneous(self) -> bool:
        return any(d.cluster_json for d in self.dcs)

    def profiles(self, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if name not in self._profiles:
            self._profiles[name] = ci_to_profiles(self.dc(name).ci, self.cluster_of(name), self.timescale,
                                                  self.mapping)
        return self._profiles[name]

    def queue_wait_s(self, name: str, t_s: float) -> float:
        """Queue wait (seconds) for a job that becomes ready at DC ``name`` at time ``t_s``."""
        q = self.dc(name).queue_hours
        if not q:
            return 0.0
        i = min(max(int(t_s // SECONDS_PER_HOUR), 0), len(q) - 1)
        return q[i] * SECONDS_PER_HOUR

    @property
    def contended(self) -> bool:
        return any(d.queue_hours and any(d.queue_hours) for d in self.dcs)

    def wan_ci(self, name: str) -> dict[str, list[float]]:
        return wan_ci_profile_seconds(self.source_dc.ci, self.dc(name).ci)

    @property
    def synthetic(self) -> bool:
        return any(d.synthetic for d in self.dcs)


# ------------------------------------------------------------------ contention
REGION_TZ = {"DE": "Europe/Berlin", "NO": "Europe/Oslo", "FR": "Europe/Paris", "PL": "Europe/Warsaw",
             "US-CAL": "America/Los_Angeles", "IN": "Asia/Kolkata"}


@dataclass(frozen=True)
class QueueSpec:
    """Diurnal queue at a DC: ``peak_h`` hours of waiting for jobs arriving in local business hours
    [``busy_from``, ``busy_to``), ``off_h`` otherwise (local time, DST-aware)."""

    peak_h: float
    off_h: float = 0.0
    busy_from: int = 9
    busy_to: int = 18


def series_utc_start(series: "CITimeSeries"):
    """UTC datetime of sample 0 (handles window suffixes such as '2024-01-01 00:00:00+2568h';
    synthetic series start at 2024-01-01 00:00 UTC)."""
    import datetime as _dt

    base, *shifts = series.start_utc.split("+")
    hours = sum(int(s.rstrip("h")) for s in shifts if s.endswith("h"))
    try:
        t0 = _dt.datetime.fromisoformat(base.strip().replace("Z", "+00:00"))
    except ValueError:
        t0 = _dt.datetime(2024, 1, 1)
    if t0.tzinfo is None:
        t0 = t0.replace(tzinfo=_dt.timezone.utc)
    return t0.astimezone(_dt.timezone.utc) + _dt.timedelta(hours=hours)


def diurnal_queue(series: "CITimeSeries", spec: QueueSpec) -> tuple[float, ...]:
    """Hourly queue waits on ``series``' clock for a DC in ``series.region``."""
    import datetime as _dt
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(REGION_TZ[series.region])
    t0 = series_utc_start(series)
    out = []
    for i in range(len(series)):
        h = (t0 + _dt.timedelta(hours=i)).astimezone(tz).hour
        out.append(spec.peak_h if spec.busy_from <= h < spec.busy_to else spec.off_h)
    return tuple(out)


DEFAULT_DCS: tuple[tuple[str, str], ...] = (
    ("DC_Frankfurt", "DE"),
    ("DC_Oslo", "NO"),
    ("DC_Paris", "FR"),
    ("DC_Warsaw", "PL"),
    ("DC_California", "US-CAL"),
    ("DC_Mumbai", "IN"),
)

# Topology region -> Electricity Maps zone holding that DC.  Oslo is bidding zone NO1,
# California is the CAISO balancing area, Mumbai is the Western Indian grid.
EM_ZONES: dict[str, str] = {
    "DE": "DE",
    "NO": "NO-NO1",
    "FR": "FR",
    "PL": "PL",
    "US-CAL": "US-CAL-CISO",
    "IN": "IN-WE",
}


def scan_ci_dir(ci_dir: str | Path, regions: Sequence[str] | None = None) -> dict[str, Path]:
    """Map each topology region to ``<ci_dir>/<REGION>.csv``.  Every region must be present:
    a partial directory would silently mix real and synthetic data, so it raises instead."""
    ci_dir = Path(ci_dir)
    if not ci_dir.is_dir():
        raise FileNotFoundError(f"CI directory {ci_dir} does not exist")
    regions = list(regions) if regions is not None else [r for _, r in DEFAULT_DCS]
    found = {r: ci_dir / f"{r}.csv" for r in regions}
    missing = [r for r, p in found.items() if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"{ci_dir}: missing CI files for {missing} (expected <REGION>.csv)")
    return found


def hours_from_series_start(path: str | Path, start_utc: str) -> int:
    """Whole hours between the first timestamp of an Electricity Maps CSV and ``start_utc``
    (ISO date or datetime, UTC).  Used to place experiment start hours inside a year of data."""
    import datetime as _dt

    with open(path, newline="", encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))
    tcol = next((c for c in _EM_TIME_COLS if c in row), None)
    if tcol is None:
        raise ValueError(f"{path}: no timestamp column among {list(row)}")

    def _utc(s: str) -> _dt.datetime:
        t = _dt.datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        return t.replace(tzinfo=_dt.timezone.utc) if t.tzinfo is None else t.astimezone(_dt.timezone.utc)

    delta = _utc(start_utc) - _utc(row[tcol])
    hours, rem = divmod(delta.total_seconds(), 3600)
    if rem or hours < 0:
        raise ValueError(f"{start_utc} is not a whole hour at/after the start of {path} ({row[tcol]})")
    return int(hours)


def build_topology(
    hours: int,
    cluster_json: str | Path,
    variant: str = "small",
    source: str = "DC_Frankfurt",
    dcs: Sequence[tuple[str, str]] = DEFAULT_DCS,
    ci_csv: Mapping[str, str | Path] | None = None,
    start_hour: int = 0,
    seed: int = 0,
    bandwidth_gbps: float | Mapping[str, float] = 1.0,
    timescale: TimeScale = TimeScale(),
    mapping: BudgetMapping = BudgetMapping(),
    hardware: Mapping[str, HardwareTier] | None = None,
    queues: Mapping[str, QueueSpec] | None = None,
) -> Topology:
    """Assemble a topology.  Regions with a CSV in ``ci_csv`` use real data (window
    ``[start_hour, start_hour + hours)``); all others fall back to :func:`synthetic_ci`.

    ``hardware`` optionally maps a DC name to a :class:`HardwareTier` (own cluster file, same
    variant, and PUE); DCs not in it use ``cluster_json`` with PUE 1.  ``queues`` optionally maps a
    DC name to a :class:`QueueSpec` (diurnal queue wait); DCs not in it have no queue."""
    from dataclasses import replace as _replace

    cluster = ClusterPower.from_cluster_json(cluster_json, variant)
    out = []
    for name, region in dcs:
        if ci_csv and region in ci_csv:
            series = load_electricitymaps_csv(ci_csv[region], region).window(start_hour, hours)
        else:
            series = synthetic_ci(region, hours, seed=seed, start_utc_hour=start_hour)
        bw = bandwidth_gbps[name] if isinstance(bandwidth_gbps, Mapping) else bandwidth_gbps
        hw = (hardware or {}).get(name)
        if hw is None:
            out.append(DataCentre(name, region, series, float(bw)))
        elif hw.cluster_json is not None and Path(hw.cluster_json).resolve() != Path(cluster_json).resolve():
            out.append(DataCentre(name, region, series, float(bw), str(Path(hw.cluster_json).resolve()),
                                  ClusterPower.from_cluster_json(hw.cluster_json, variant), hw.name, float(hw.pue)))
        else:
            out.append(DataCentre(name, region, series, float(bw), hardware=hw.name, pue=float(hw.pue)))
        q = (queues or {}).get(name)
        if q is not None and (q.peak_h > 0 or q.off_h > 0):
            out[-1] = _replace(out[-1], queue_hours=diurnal_queue(series, q))
    return Topology(source, tuple(out), cluster, timescale, mapping, str(cluster_json))
