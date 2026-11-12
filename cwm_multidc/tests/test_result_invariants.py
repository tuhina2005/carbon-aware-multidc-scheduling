"""Invariants of the saved experiment outputs (skipped when a summary CSV is absent).

Ours is the minimum over every evaluated (DC, T_net) CWM point, and B1, B3, B4, B5, A1 and A2 each
pick one of those same points, so Ours can never be worse than them, under either metric or any
eps.  B2 (HEFT) and C1 (extra CWM seeds) lie outside Ours' search space and may beat it: B2 because
CWM minimises brown kWh, not CI-weighted carbon; C1 because of best-of-N solver noise.
"""

import unittest

import pandas as pd

from cwm_multidc.experiments import MD_DIR, RESULTS

IN_SEARCH_SPACE = ("B1", "B3", "B4", "B5", "A1", "A2")
KEYS = ["experiment", "ci_date", "dag", "start_hour", "data_size_gb", "alpha", "units_per_hour",
        "bandwidth_gbps", "metric", "eps_kwh_per_gb"]


class SummaryInvariantTest(unittest.TestCase):
    def check(self, path):
        if not path.exists():
            self.skipTest(f"{path.name} not generated")
        s = pd.read_csv(path)
        s = s[s.experiment != "forecast"]  # forecast rows realise choices made on other (noisy) CI
        keys = [k for k in KEYS if k in s]
        s = s.assign(**{k: s[k].fillna(-1) for k in keys})
        piv = s.pivot_table(index=keys, columns="method", values="total_gco2", aggfunc="first")
        self.assertFalse(piv.index.duplicated().any())
        for m in IN_SEARCH_SPACE:
            if m not in piv:
                continue
            both = piv[["Ours", m]].dropna()
            worse = both[both.Ours > both[m] * (1 + 1e-9) + 1e-9]
            self.assertTrue(worse.empty, f"{path.name}: Ours worse than {m} in {len(worse)} rows, e.g.\n"
                                         f"{worse.head(3)}")

    def test_grid(self):
        self.check(RESULTS / "grid_summary.csv")

    def test_headline(self):
        self.check(RESULTS / "headline_summary.csv")

    def test_sensitivity(self):
        self.check(RESULTS / "sensitivity_summary.csv")

    def test_multidate(self):
        self.check(RESULTS / MD_DIR / "multidate_summary.csv")


if __name__ == "__main__":
    unittest.main()
