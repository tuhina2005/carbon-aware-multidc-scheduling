"""Put real Electricity Maps hourly carbon-intensity data in place for the multi-DC topology.

Output: ``<out>/<REGION>.csv`` for every topology region (DE, NO, FR, PL, US-CAL, IN), which
``experiments.py --ci-dir <out>`` reads, plus ``MANIFEST.json`` (zone, rows, mean, sha256).

Two ways to get the data (Electricity Maps publishes no anonymous download):

1. ``import`` (free account): sign in at https://app.electricitymaps.com/datasets, download the
   *hourly* 2024 CSV for each zone below, then

       python -m cwm_multidc.scripts.fetch_ci_data import ~/Downloads

   Files are matched by zone id in the file name (e.g. ``NO-NO1_2024_hourly.csv``).

2. ``api`` (API token with historical access, in ``ELECTRICITYMAPS_API_KEY``):

       python -m cwm_multidc.scripts.fetch_ci_data api --year 2024

Zones (see ``data_loader.EM_ZONES``): DE->DE, NO->NO-NO1 (Oslo), FR->FR, PL->PL,
US-CAL->US-CAL-CISO, IN->IN-WE (Mumbai).

Every file is validated with ``load_electricitymaps_csv`` (consecutive UTC hours, no blank
values) and must cover the whole year.  Nothing is interpolated or invented: a gap is an error.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..data_loader import EM_ZONES, load_electricitymaps_csv

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "electricitymaps"
API_URL = "https://api.electricitymaps.com/v3/carbon-intensity/past-range"
CI_COLUMN = "Carbon Intensity gCO₂eq/kWh (LCA)"
API_CHUNK_DAYS = 7


def _validate(path: Path, region: str, year: int) -> dict:
    series = load_electricitymaps_csv(path, region)  # raises on gaps / blanks / non-hourly steps
    expected = (366 if calendar.isleap(year) else 365) * 24
    if len(series.values) != expected:
        raise ValueError(f"{path}: {len(series.values)} hourly rows, expected {expected} for {year}")
    first = dt.datetime.fromisoformat(series.start_utc.replace("Z", "+00:00")).replace(tzinfo=None)
    if first != dt.datetime(year, 1, 1):
        raise ValueError(f"{path}: first timestamp {series.start_utc}, expected {year}-01-01 00:00 UTC")
    return {"rows": len(series.values), "first_utc": series.start_utc,
            "mean_gco2_per_kwh": round(sum(series.values) / len(series.values), 2),
            "min": min(series.values), "max": max(series.values)}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(out: Path, entries: dict, how: str, year: int) -> None:
    manifest = {"source": "Electricity Maps", "year": year, "how": how,
                "retrieved_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "regions": entries}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def _find_export(src: Path, zone: str, year: int) -> Path:
    hits = [p for p in src.rglob("*.csv")
            if p.name.upper().startswith(f"{zone.upper()}_{year}") and "HOURLY" in p.name.upper()]
    if not hits:
        raise FileNotFoundError(f"no hourly {year} export for zone {zone} under {src} "
                                f"(expected a file like {zone}_{year}_hourly.csv)")
    if len(hits) > 1:
        raise ValueError(f"several candidate files for zone {zone}: {[str(h) for h in hits]}")
    return hits[0]


def cmd_import(args) -> None:
    src, out = Path(args.src).expanduser(), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    entries, errors = {}, []
    for region, zone in EM_ZONES.items():
        try:
            f = _find_export(src, zone, args.year)
            dst = out / f"{region}.csv"
            shutil.copyfile(f, dst)
            entries[region] = {"zone": zone, "file": dst.name, "original": f.name,
                               **_validate(dst, region, args.year), "sha256": _sha256(dst)}
            print(f"{region:7s} <- {f.name}: {entries[region]['rows']} h, "
                  f"mean {entries[region]['mean_gco2_per_kwh']} gCO2/kWh")
        except (OSError, ValueError) as e:
            errors.append(f"{region}: {e}")
    if errors:
        sys.exit("import failed:\n  " + "\n  ".join(errors))
    _write_manifest(out, entries, "portal export import", args.year)


def _api_get(zone: str, start: dt.datetime, end: dt.datetime, key: str) -> list[dict]:
    q = urllib.parse.urlencode({"zone": zone, "start": start.strftime("%Y-%m-%dT%H:%MZ"),
                                "end": end.strftime("%Y-%m-%dT%H:%MZ"), "emissionFactorType": "lifecycle"})
    req = urllib.request.Request(f"{API_URL}?{q}", headers={"auth-token": key})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["data"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(2 ** attempt * 5)
                continue
            raise RuntimeError(f"{zone} {start:%Y-%m-%d}: HTTP {e.code} {e.read()[:200]!r}") from e
    raise AssertionError("unreachable")


def cmd_api(args) -> None:
    key = os.environ.get("ELECTRICITYMAPS_API_KEY")
    if not key:
        sys.exit("set ELECTRICITYMAPS_API_KEY to an Electricity Maps API token with historical access")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    y0, y1 = dt.datetime(args.year, 1, 1), dt.datetime(args.year + 1, 1, 1)
    entries = {}
    for region, zone in EM_ZONES.items():
        by_hour: dict[dt.datetime, float] = {}
        t = y0
        while t < y1:
            t2 = min(t + dt.timedelta(days=API_CHUNK_DAYS), y1)
            for rec in _api_get(zone, t, t2, key):
                ts = dt.datetime.fromisoformat(rec["datetime"].replace("Z", "+00:00")).replace(tzinfo=None)
                if y0 <= ts < y1 and rec.get("carbonIntensity") is not None:
                    by_hour[ts] = float(rec["carbonIntensity"])
            t = t2
        dst = out / f"{region}.csv"
        with open(dst, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Datetime (UTC)", "Zone Id", CI_COLUMN])
            h = y0
            while h < y1:  # a missing hour is written blank, so validation below fails loudly
                v = by_hour.get(h)
                w.writerow([h.strftime("%Y-%m-%d %H:%M:%S"), zone, "" if v is None else v])
                h += dt.timedelta(hours=1)
        entries[region] = {"zone": zone, "file": dst.name, **_validate(dst, region, args.year),
                           "sha256": _sha256(dst)}
        print(f"{region:7s} <- API {zone}: mean {entries[region]['mean_gco2_per_kwh']} gCO2/kWh")
    _write_manifest(out, entries, "API v3 carbon-intensity/past-range (lifecycle)", args.year)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import", help="validate and rename Electricity Maps portal CSV exports")
    imp.add_argument("src", help="directory holding the downloaded <ZONE>_<YEAR>_hourly.csv files")
    imp.set_defaults(fn=cmd_import)
    api = sub.add_parser("api", help="download through the Electricity Maps API (needs a token)")
    api.set_defaults(fn=cmd_api)
    for p in (imp, api):
        p.add_argument("--year", type=int, default=2024)
        p.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
