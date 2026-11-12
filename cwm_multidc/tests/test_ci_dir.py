"""--ci-dir wiring: directory scan, date offsets, provenance labels, portal-export import.

The CSVs here are throwaway fixtures written to a temp dir (constant / ramp values); they
exercise parsing only and are never placed in cwm_multidc/data/.
"""

import calendar
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from cwm_multidc.cwm_runner import DEFAULT_CLUSTER
from cwm_multidc.data_loader import EM_ZONES, build_topology, hours_from_series_start, scan_ci_dir
from cwm_multidc.experiments import CIConfig, main as exp_main
from cwm_multidc.plots import SYNTHETIC_NOTE, _ci_note, _source
from cwm_multidc.scripts import fetch_ci_data

COL = "Carbon Intensity gCO₂eq/kWh (LCA)"


def write_fixture(path: Path, zone: str, start: dt.datetime, hours: int, base: float) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"Datetime (UTC),Zone Id,{COL}\n")
        for h in range(hours):
            f.write(f"{(start + dt.timedelta(hours=h)):%Y-%m-%d %H:%M:%S},{zone},{base + h % 24}\n")


class CIDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.start = dt.datetime(2024, 1, 1)
        for i, region in enumerate(EM_ZONES):
            write_fixture(self.dir / f"{region}.csv", EM_ZONES[region], self.start, 24 * 120, 100.0 * (i + 1))

    def tearDown(self):
        self.tmp.cleanup()

    def test_scan_requires_every_region(self):
        self.assertEqual(set(scan_ci_dir(self.dir)), set(EM_ZONES))
        (self.dir / "PL.csv").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "PL"):
            scan_ci_dir(self.dir)

    def test_offset_from_date(self):
        self.assertEqual(hours_from_series_start(self.dir / "DE.csv", "2024-04-17"), 107 * 24)
        self.assertEqual(hours_from_series_start(self.dir / "DE.csv", "2024-01-01T05:00Z"), 5)
        with self.assertRaises(ValueError):
            hours_from_series_start(self.dir / "DE.csv", "2023-12-31")

    def test_config_places_start_hour_on_date(self):
        ci = CIConfig(self.dir, "2024-03-01")
        self.assertEqual(ci.offset, 60 * 24)
        self.assertEqual(ci.label, f"hourly CI CSVs from {self.dir.name}/ (no MANIFEST.json)@2024-03-01")
        self.assertEqual(len(ci.dcs), 6)
        topo = build_topology(24, DEFAULT_CLUSTER, ci_csv=ci.ci_csv, start_hour=ci.offset + 6)
        self.assertFalse(topo.synthetic)
        de = next(d for d in topo.dcs if d.region == "DE")
        self.assertEqual(de.ci.values[0], 100.0 + 6)  # fixture value = base + hour-of-day

    def test_synthetic_fallback(self):
        ci = CIConfig(None)
        self.assertIsNone(ci.ci_csv)
        self.assertEqual((ci.offset, ci.label), (0, "synthetic"))

    def test_manifest_selects_dcs_and_label(self):
        (self.dir / "MANIFEST.json").write_text(json.dumps(
            {"label": "Energy-Charts/ENTSO-E + CAISO 2024", "regions": {r: {} for r in EM_ZONES if r != "IN"}}))
        (self.dir / "IN.csv").unlink()
        ci = CIConfig(self.dir)
        self.assertNotIn("IN", {r for _, r in ci.dcs})
        self.assertEqual(ci.label, "Energy-Charts/ENTSO-E + CAISO 2024@2024-04-17")
        (self.dir / "PL.csv").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "PL"):
            CIConfig(self.dir)

    def test_cli_flags_parse(self):
        with self.assertRaisesRegex(FileNotFoundError, "does not exist"):
            exp_main(["grid", "--ci-dir", str(self.dir / "nope")])

    def test_plot_labels(self):
        lab = "Electricity Maps 2024 (life-cycle)@2024-04-17"
        real = pd.DataFrame({"synthetic_ci": [False, False], "ci_source": [lab] * 2})
        self.assertEqual(_source(real), lab)
        self.assertEqual(_ci_note(_source(real)), "Carbon intensity: Electricity Maps 2024 (life-cycle) "
                                                  "historical hourly data, window starting 2024-04-17 UTC.")
        mixed = real.assign(synthetic_ci=[False, True])
        self.assertEqual(_ci_note(_source(mixed)), SYNTHETIC_NOTE)
        legacy = pd.DataFrame({"synthetic_ci": [True]})
        self.assertEqual(_ci_note(_source(legacy)), SYNTHETIC_NOTE)


class ImportTest(unittest.TestCase):
    def test_import_validates_and_renames(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as out:
            hours = (366 if calendar.isleap(2024) else 365) * 24
            for region, zone in EM_ZONES.items():
                write_fixture(Path(src) / f"{zone}_2024_hourly.csv", zone, dt.datetime(2024, 1, 1), hours, 50.0)
            fetch_ci_data.main(["import", src, "--out", out])
            self.assertEqual(scan_ci_dir(out).keys(), EM_ZONES.keys())
            man = json.loads((Path(out) / "MANIFEST.json").read_text())
            self.assertEqual(man["regions"]["NO"]["zone"], "NO-NO1")
            self.assertEqual(man["regions"]["IN"]["rows"], hours)

    def test_import_rejects_partial_year(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as out:
            for zone in EM_ZONES.values():
                write_fixture(Path(src) / f"{zone}_2024_hourly.csv", zone, dt.datetime(2024, 1, 1), 100, 50.0)
            with self.assertRaises(SystemExit) as cm:
                fetch_ci_data.main(["import", src, "--out", out])
            self.assertIn("expected 8784", str(cm.exception))


if __name__ == "__main__":
    unittest.main()


class GapFillTest(unittest.TestCase):
    def test_short_gaps_interpolated_long_gaps_rejected(self):
        from cwm_multidc.scripts.fetch_public_ci import MAX_GAP_HOURS, _fill_short_gaps

        hours = [dt.datetime(2024, 1, 1) + dt.timedelta(hours=i) for i in range(40)]
        ci = [10.0, None, None, 40.0] + [40.0] * 36
        self.assertEqual(_fill_short_gaps(ci, "X", hours[:len(ci)]), {1, 2})
        self.assertEqual(ci[:4], [10.0, 20.0, 30.0, 40.0])
        long = [1.0] + [None] * (MAX_GAP_HOURS + 1) + [1.0]
        with self.assertRaisesRegex(ValueError, "consecutive hours missing"):
            _fill_short_gaps(long, "X", hours[:len(long)])
