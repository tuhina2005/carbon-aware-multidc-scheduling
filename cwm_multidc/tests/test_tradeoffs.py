"""Deadline trade-off and per-workflow tables (cwm_multidc.tradeoffs)."""

import unittest

import pandas as pd

from cwm_multidc import tradeoffs as tr
from cwm_multidc.experiments import MD_DIR, RESULTS

MS = RESULTS / MD_DIR / "multidate_summary.csv"


class TestPerHour(unittest.TestCase):
    def test_saving_per_extra_hour(self):
        t = pd.DataFrame({"dag": ["x", "x"], "data_size_gb": [1.0, 1.0], "alpha": [1.5, 2.5],
                          "D_h": [10.0, 20.0], "B1": [3.0, 2.0], "B3": [1.0, 1.0], "Ours": [1.0, 0.5]})
        r = tr.per_hour(t).iloc[0]
        self.assertAlmostEqual(r.B1_g_per_h, 100.0)  # 1 kg over 10 h
        self.assertAlmostEqual(r.Ours_g_per_h, 50.0)
        self.assertAlmostEqual(r.B3_g_per_h, 0.0)

    def test_dag_shape_counts_tasks(self):
        tasks, deps = tr.dag_shape("atacseq200")
        self.assertEqual((tasks, deps), (195, 350))


@unittest.skipUnless(MS.exists(), "saved multidate summary not present")
class TestAgainstSummary(unittest.TestCase):
    def test_workflow_gains_average_to_headline(self):
        ms = tr._load(MS)
        sw = tr.seasonal_workflows(ms)
        # equal-sized groups (48 problems each), so the mean of group means is the overall mean (1.76 %)
        self.assertAlmostEqual(sw.gain_vs_B3_pct.mean(), 1.76, places=2)

    def test_ours_never_worse_than_b3_on_average(self):
        t = tr.deadline_table(tr._load(MS))
        self.assertTrue((t.Ours <= t.B3 + 1e-9).all())


if __name__ == "__main__":
    unittest.main()
