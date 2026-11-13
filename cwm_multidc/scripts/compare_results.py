"""Compare two results folders (e.g. pre- vs post-solver-fix) problem by problem.

    python -m cwm_multidc.scripts.compare_results OLD_DIR NEW_DIR [--out FILE.md]

For every study present in both folders (grid, headline, sensitivity, multidate) it reports, per
metric at eps = 0.02 kWh/GB: how many problems changed Ours' choice (DC / T_net), the change in
Ours' total carbon, and the gain of Ours over B3 before and after.  Problems are matched on their
full key, so nothing is averaged across different problems.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

STUDIES = {"grid": "grid_summary.csv", "headline": "headline_summary.csv",
           "sensitivity": "sensitivity_summary.csv", "multidate": "multidate/multidate_summary.csv"}
KEYS = ["experiment", "ci_date", "dag", "start_hour", "data_size_gb", "alpha", "units_per_hour",
        "bandwidth_gbps", "forecast_sigma", "forecast_seed"]


def _frame(path: Path, metric: str) -> pd.DataFrame:
    s = pd.read_csv(path)
    s = s[(s.metric == metric) & np.isclose(s.eps_kwh_per_gb, 0.02)]
    keys = [k for k in KEYS if k in s]
    s = s.assign(**{k: s[k].fillna(-1) for k in keys})
    ours = s[s.method == "Ours"].set_index(keys)[["dc", "t_net_h", "total_gco2"]]
    b3 = s[s.method == "B3"].set_index(keys)["total_gco2"].rename("b3")
    return ours.join(b3)


def compare(old: Path, new: Path) -> str:
    lines = [f"# Results comparison", "", f"- old: `{old}`", f"- new: `{new}`", ""]
    rows = []
    for study, rel in STUDIES.items():
        if not ((old / rel).exists() and (new / rel).exists()):
            continue
        for metric in ("location", "brown"):
            a, b = _frame(old / rel, metric), _frame(new / rel, metric)
            both = a.join(b, lsuffix="_old", rsuffix="_new", how="inner")
            if both.empty:
                continue
            changed = (both.dc_old != both.dc_new) | ~np.isclose(both.t_net_h_old, both.t_net_h_new)
            d = (both.total_gco2_new - both.total_gco2_old) / both.total_gco2_old.where(both.total_gco2_old > 0)
            g_old = 1 - both.total_gco2_old / both.b3_old.where(both.b3_old > 0)
            g_new = 1 - both.total_gco2_new / both.b3_new.where(both.b3_new > 0)
            rows.append({"study": study, "metric": metric, "problems": len(both),
                         "only old": len(a) - len(both), "only new": len(b) - len(both),
                         "choice changed": int(changed.sum()),
                         "Ours total changed (>0.1 %)": int((d.abs() > 1e-3).sum()),
                         "median |Δ total| %": 100 * d.abs().median(), "max |Δ total| %": 100 * d.abs().max(),
                         "gain vs B3 old (mean %)": 100 * g_old.mean(), "gain vs B3 new (mean %)": 100 * g_new.mean(),
                         "share ≥ 5 % old": (g_old >= 0.05).mean(), "share ≥ 5 % new": (g_new >= 0.05).mean()})
    lines += [pd.DataFrame(rows).round(3).to_markdown(index=False), ""]
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    text = compare(args.old, args.new)
    if args.out:
        args.out.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
