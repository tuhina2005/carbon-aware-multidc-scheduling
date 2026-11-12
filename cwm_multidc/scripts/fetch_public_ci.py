"""Hourly life-cycle carbon intensity from free public generation data (no account needed).

Sources
  DE, FR, PL, NO : Energy-Charts public API (Fraunhofer ISE; ENTSO-E Transparency data,
                   CC BY 4.0), ``/public_power``, 15-min/hourly net generation by fuel.
                   Norway is the national mix (the API has no NO1 bidding-zone series).
  US-CAL         : CAISO "Today's Outlook" daily fuel-source files, 5-min MW by fuel, local
                   Pacific time (converted to UTC, DST-aware).
  IN (Mumbai)    : no free hourly fuel-mix source found -> not produced; the experiments drop
                   DC_Mumbai when this directory is used.

Method (production-based, life-cycle):
  CI_h = sum_f G_{f,h} * EF_f / sum_f G_{f,h}
  G = mean MW of each fuel over the UTC hour, negatives clipped to 0. Storage (pumped hydro,
  batteries), imports/cross-border flows and load series are excluded. EF_f are IPCC AR5 WG3
  Annex III life-cycle medians (the defaults Electricity Maps also uses); oil 650 and
  unknown/other/waste 700 follow Electricity Maps' defaults where IPCC gives no value.
  Differences from Electricity Maps: no flow tracing (imports ignored), so CAISO, which imports
  ~20-30 % of its energy, and small importers are biased towards their domestic mix.

Usage
  python -m cwm_multidc.scripts.fetch_public_ci --year 2024
Writes ``cwm_multidc/data/public_ci/<REGION>.csv`` + ``MANIFEST.json``; raw downloads are
cached under ``raw/`` so re-runs are offline.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

from ..data_loader import load_electricitymaps_csv

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "public_ci"
CI_COLUMN = "Carbon Intensity gCO₂eq/kWh (LCA)"
UA = "cwm-multidc-research/1.0 (python urllib)"

# life-cycle emission factors, gCO2eq/kWh
EF = {"coal": 820, "gas": 490, "oil": 650, "biomass": 230, "nuclear": 12, "hydro": 24,
      "wind": 11, "solar": 45, "geothermal": 38, "unknown": 700}

ENERGY_CHARTS_FUEL = {
    "Nuclear": "nuclear", "Hydro Run-of-River": "hydro", "Hydro water reservoir": "hydro",
    "Biomass": "biomass", "Other renewables": "biomass", "Fossil brown coal / lignite": "coal",
    "Fossil hard coal": "coal", "Fossil coal-derived gas": "coal", "Fossil oil": "oil",
    "Fossil gas": "gas", "Geothermal": "geothermal", "Wind offshore": "wind", "Wind onshore": "wind",
    "Solar": "solar", "Waste": "unknown", "Others": "unknown",
}
ENERGY_CHARTS_SKIP = {"Hydro pumped storage", "Hydro pumped storage consumption", "Cross border electricity trading",
                      "Load", "Residual load", "Renewable share of load", "Renewable share of generation",
                      "Battery storage", "Battery storage consumption", "Load (incl. self-consumption)"}
CAISO_FUEL = {"Solar": "solar", "Wind": "wind", "Geothermal": "geothermal", "Biomass": "biomass",
              "Biogas": "biomass", "Small hydro": "hydro", "Large Hydro": "hydro", "Coal": "coal",
              "Nuclear": "nuclear", "Natural Gas": "gas", "Other": "unknown"}
CAISO_SKIP = {"Time", "Batteries", "Imports"}

REGIONS = {  # region -> (source, code)
    "DE": ("energy-charts", "de"), "FR": ("energy-charts", "fr"), "PL": ("energy-charts", "pl"),
    "NO": ("energy-charts", "no"), "US-CAL": ("caiso", "CISO"),
}


def _get(url: str, cache: Path) -> bytes:
    if cache.exists():
        return cache.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(body)
            time.sleep(0.3)  # be polite to public endpoints
            return body
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 4:
                raise RuntimeError(f"{url}: {e}") from e
            time.sleep(5 * 2 ** attempt)
    raise AssertionError("unreachable")


Hourly = dict[dt.datetime, dict[str, float]]  # UTC hour -> fuel -> mean MW


# UTC hour -> (series name, fuel) -> sample timestamp -> MW.  Keyed by timestamp so that
# samples returned by two overlapping requests are counted once.
Samples = dict[dt.datetime, dict[tuple[str, str], dict[float, float]]]


def _new_samples() -> Samples:
    return defaultdict(lambda: defaultdict(dict))


def _accumulate(samples: Samples) -> Hourly:
    """Hourly mean MW per series, then summed over the series of each fuel."""
    out: Hourly = {}
    for h, series in samples.items():
        fuels: dict[str, float] = defaultdict(float)
        for (_, fuel), vals in series.items():
            fuels[fuel] += sum(vals.values()) / len(vals)
        out[h] = dict(fuels)
    return out


def energy_charts(code: str, year: int, raw: Path) -> tuple[Hourly, list[str]]:
    samples = _new_samples()
    unknown_types: set[str] = set()
    for m in range(1, 13):
        a = dt.datetime(year, m, 1)
        b = dt.datetime(year + (m == 12), m % 12 + 1, 1)
        url = (f"https://api.energy-charts.info/public_power?country={code}"
               f"&start={a:%Y-%m-%dT%H:%MZ}&end={b:%Y-%m-%dT%H:%MZ}")
        d = json.loads(_get(url, raw / "energy-charts" / f"{code}_{year}-{m:02d}.json"))
        ts = d["unix_seconds"]
        for p in d["production_types"]:
            name = p["name"]
            if name in ENERGY_CHARTS_SKIP:
                continue
            fuel = ENERGY_CHARTS_FUEL.get(name)
            if fuel is None:
                unknown_types.add(name)
                fuel = "unknown"
            for t, v in zip(ts, p["data"]):
                if v is None:
                    continue
                h = dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None, minute=0, second=0)
                if h.year == year:
                    samples[h][(name, fuel)][t] = max(0.0, float(v))
    return _accumulate(samples), sorted(unknown_types)


def caiso(year: int, raw: Path) -> tuple[Hourly, list[str]]:
    tz = ZoneInfo("America/Los_Angeles")
    samples = _new_samples()
    unknown_types: set[str] = set()
    day = dt.date(year - 1, 12, 31)  # local days overlapping the UTC year
    while day <= dt.date(year, 12, 31):
        url = f"https://www.caiso.com/outlook/history/{day:%Y%m%d}/fuelsource.csv"
        rows = list(csv.DictReader(_get(url, raw / "caiso" / f"{day:%Y%m%d}.csv").decode("utf-8-sig").splitlines()))
        seen: set[str] = set()
        for r in rows:
            hhmm = r["Time"].strip()
            fold = 1 if hhmm in seen else 0  # repeated 01:xx on the November DST day
            seen.add(hhmm)
            hh, mm = map(int, hhmm.split(":")[:2])
            local = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz, fold=fold)
            u = local.astimezone(dt.timezone.utc).replace(tzinfo=None)
            if u.year != year:
                continue
            h = u.replace(minute=0, second=0)
            for col, val in r.items():
                if col in CAISO_SKIP or col is None or val in (None, ""):
                    continue
                fuel = CAISO_FUEL.get(col.strip())
                if fuel is None:
                    unknown_types.add(col)
                    fuel = "unknown"
                samples[h][(col.strip(), fuel)][u.timestamp()] = max(0.0, float(val))
        day += dt.timedelta(days=1)
    return _accumulate(samples), sorted(unknown_types)


def write_region(region: str, zone: str, hourly: Hourly, year: int, out: Path) -> dict:
    y0 = dt.datetime(year, 1, 1)
    n = (366 if calendar.isleap(year) else 365) * 24
    dst = out / f"{region}.csv"
    energy = defaultdict(float)
    hours = [y0 + dt.timedelta(hours=i) for i in range(n)]
    ci: list[float | None] = []
    gen: list[float | None] = []
    for h in hours:
        g = hourly.get(h, {})
        tot = sum(g.values())
        if tot <= 0:
            ci.append(None)
            gen.append(None)
            continue
        for fu, mw in g.items():
            energy[fu] += mw
        ci.append(sum(mw * EF[fu] for fu, mw in g.items()) / tot)
        gen.append(tot)
    filled = _fill_short_gaps(ci, region, hours)
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Datetime (UTC)", "Zone Id", CI_COLUMN, "Generation MW (excl. storage)", "Interpolated"])
        for i, h in enumerate(hours):
            w.writerow([f"{h:%Y-%m-%d %H:%M:%S}", zone, f"{ci[i]:.2f}",
                        "" if gen[i] is None else f"{gen[i]:.1f}", int(i in filled)])
    series = load_electricitymaps_csv(dst, region)
    if len(series.values) != n:
        raise ValueError(f"{region}: {len(series.values)} rows, expected {n}")
    total_e = sum(energy.values())
    return {"zone": zone, "file": dst.name, "rows": n,
            "mean_gco2_per_kwh": round(sum(series.values) / n, 1),
            "generation_weighted_gco2_per_kwh": round(sum(energy[f] * EF[f] for f in energy) / total_e, 1),
            "min": min(series.values), "max": max(series.values),
            "fuel_share": {f: round(e / total_e, 4) for f, e in sorted(energy.items())},
            "interpolated_hours_utc": [f"{hours[i]:%Y-%m-%d %H:%M}" for i in sorted(filled)],
            "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()}


MAX_GAP_HOURS = 12


def _fill_short_gaps(ci: list[float | None], region: str, hours: list[dt.datetime]) -> set[int]:
    """Linearly interpolate runs of missing hours of length <= MAX_GAP_HOURS (in place).
    Gaps come from the source publishing incomplete days; longer gaps are an error."""
    filled: set[int] = set()
    i, n = 0, len(ci)
    while i < n:
        if ci[i] is not None:
            i += 1
            continue
        j = i
        while j < n and ci[j] is None:
            j += 1
        if j - i > MAX_GAP_HOURS:
            raise ValueError(f"{region}: {j - i} consecutive hours missing from {hours[i]} (max {MAX_GAP_HOURS})")
        left = ci[i - 1] if i > 0 else ci[j]
        right = ci[j] if j < n else left
        if left is None or right is None:
            raise ValueError(f"{region}: no data at all")
        for k in range(i, j):
            ci[k] = left + (right - left) * (k - i + 1) / (j - i + 1)
            filled.add(k)
        i = j
    return filled


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--regions", nargs="*", default=list(REGIONS))
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = out / "raw"
    entries = {}
    for region in args.regions:
        src, code = REGIONS[region]
        hourly, unk = energy_charts(code, args.year, raw) if src == "energy-charts" else caiso(args.year, raw)
        entries[region] = {"source": src, **write_region(region, f"{src}:{code}", hourly, args.year, out),
                           "unmapped_types_as_unknown": unk}
        e = entries[region]
        print(f"{region:7s} {src}:{code}: mean {e['mean_gco2_per_kwh']} gCO2/kWh "
              f"(range {e['min']:.0f}-{e['max']:.0f}); shares {e['fuel_share']}"
              + (f"; unmapped {unk}" if unk else ""), flush=True)
    manifest = {
        "label": f"Energy-Charts/ENTSO-E + CAISO {args.year} (production-based life-cycle CI)",
        "year": args.year,
        "retrieved_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "CI_h = sum_f G_fh EF_f / sum_f G_fh; storage, imports and load excluded",
        "emission_factors_gco2_per_kwh": EF,
        "factor_source": "IPCC AR5 WG3 Annex III life-cycle medians; oil and unknown per Electricity Maps defaults",
        "sources": {"energy-charts": "https://api.energy-charts.info (Fraunhofer ISE, ENTSO-E data, CC BY 4.0)",
                    "caiso": "https://www.caiso.com/outlook/history/<YYYYMMDD>/fuelsource.csv"},
        "not_covered": {"IN": "no free hourly fuel-mix source for the Western Indian grid; DC_Mumbai is dropped"},
        "regions": entries,
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
