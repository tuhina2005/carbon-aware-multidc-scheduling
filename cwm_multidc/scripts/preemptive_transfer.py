"""Post-hoc analysis: what if the WAN transfer may pause and resume (preemptive transfer)?

Lemma (verified exhaustively in tests): with piecewise-constant hourly path CI, a transfer needing tau
seconds that must finish by its arrival time A is cheapest when it uses the cleanest available hours of
[0, A] first (fractional-knapsack exchange argument), and that is never worse than any contiguous
transfer finishing by A.  Compute carbon depends only on the arrival unit (the profile is shifted to
it), not on how the bytes were spread out, so every saved evaluation (DC, arrival unit) can be re-priced
with the preemptive network carbon WITHOUT new solver runs:

    Ours-P = min over evaluated (d, a) of  NetCarbon_pre(d, A = a*kappa) + CompCarbon(d, a).

Because the contiguous schedule of each evaluation is feasible for the same arrival, Ours-P <= Ours.

    python -m cwm_multidc.scripts.preemptive_transfer [--study multidate|substitution|sources|grid]
"""

from __future__ import annotations

import argparse
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from ..data_loader import DEFAULT_DCS, load_electricitymaps_csv
from ..experiments import CIConfig, DEFAULT_CI_START, MD_DIR, RESULTS, SRC_DIRNAME, SUB_DIR

CI_DIR = Path(__file__).resolve().parents[1] / "data" / "public_ci"
REGION = dict(DEFAULT_DCS)
UNIT_S = 120.0  # kappa (default time scale of every study analysed here)
EPS_BASE = 0.02  # eps at which net_gco2 is stored in the evals files


@lru_cache(maxsize=None)
def _series(region: str) -> np.ndarray:
    return np.asarray(load_electricitymaps_csv(CI_DIR / f"{region}.csv", region).values)


@lru_cache(maxsize=None)
def _offset(date: str) -> int:
    return CIConfig(CI_DIR, date).offset


def path_ci(date: str, start_hour: int, src: str, dst: str, hours: int) -> np.ndarray:
    """Endpoint-average WAN CI on the experiment clock (hour 0 = submission)."""
    h0 = _offset(date) + int(start_hour)
    a, b = _series(REGION[src])[h0:h0 + hours], _series(REGION[dst])[h0:h0 + hours]
    return (a + b) / 2.0


def contiguous_avg(c: np.ndarray, t0: float, tau: float) -> float:
    s, t = 0.0, t0
    while t < t0 + tau - 1e-9:
        h = int(t // 3600)
        nxt = min(3600.0 * (h + 1), t0 + tau)
        s += (nxt - t) * c[h]
        t = nxt
    return s / tau


def preemptive_avg(c: np.ndarray, arrival_s: float, tau: float) -> float:
    """Average CI seen by a transfer of tau seconds using the cleanest time in [0, arrival_s]."""
    caps = np.clip(arrival_s - 3600.0 * np.arange(len(c)), 0.0, 3600.0)
    left, cost = tau, 0.0
    for h in np.argsort(c, kind="stable"):
        x = min(caps[h], left)
        cost += x * c[h]
        left -= x
        if left <= 1e-9:
            break
    if left > 1e-6:
        raise ValueError("transfer does not fit before its arrival time")
    return cost / tau


def reprice(ev: pd.DataFrame, src: str = "DC_Frankfurt") -> pd.DataFrame:
    """Add net_pre_gco2 (preemptive, same arrival unit) to grid CWM evaluations."""
    e = ev[(ev.role == "grid") & (ev.scheduler == "cwm") & (ev.status == "ok")].copy()
    # evals store the realised D/M (e.g. 1.5015 after rounding D up to whole units); summaries the
    # nominal alpha.  Two decimals recover the nominal value for every alpha used (1.2 ... 2.5).
    e["alpha"] = e.alpha.round(2)
    if "source_dc" in e:
        e["src"] = e.source_dc.fillna(src)
    else:
        e["src"] = src
    if "ci_date" not in e:
        e["ci_date"] = DEFAULT_CI_START
    net_pre, check = [], []
    for r in e.itertuples():
        if r.dc == r.src or r.tau_s <= 0:
            net_pre.append(r.net_gco2)
            check.append(0.0)
            continue
        hours = int(np.ceil((r.t_arrival_units * UNIT_S) / 3600.0)) + 1
        c = path_ci(r.ci_date, r.start_hour, r.src, r.dc, hours)
        per_ci = r.net_gco2 / contiguous_avg(c, r.t_net_s, r.tau_s)  # = eps * Delta (kWh)
        check.append(abs(per_ci - EPS_BASE * r.data_size_gb) / (EPS_BASE * r.data_size_gb))
        net_pre.append(per_ci * preemptive_avg(c, r.t_arrival_units * UNIT_S, r.tau_s))
    e["net_pre_gco2"] = net_pre
    e["recon_rel_err"] = check
    return e


def compare(summary: pd.DataFrame, evals: pd.DataFrame, keys: list[str], metric: str, eps: float) -> pd.DataFrame:
    """Per problem: Ours (contiguous), Ours-P (preemptive) and B3 under `metric` and `eps`."""
    comp = "comp_loc_gco2" if metric == "location" else "comp_gco2"
    scale = eps / EPS_BASE
    e = evals.assign(tot_c=evals.net_gco2 * scale + evals[comp], tot_p=evals.net_pre_gco2 * scale + evals[comp])
    ours_p = e.groupby(keys).tot_p.min().rename("OursP")
    s = summary[(summary.metric == metric) & np.isclose(summary.eps_kwh_per_gb, eps)]
    piv = s.pivot_table(index=keys, columns="method", values="total_gco2", aggfunc="first")[["Ours", "B3"]]
    return piv.join(ours_p, how="inner")


STUDIES = {"multidate": (MD_DIR, "multidate", ["ci_date", "dag", "start_hour", "data_size_gb", "alpha"]),
           "substitution": (SUB_DIR, "substitution", ["ci_date", "dag", "start_hour", "data_size_gb", "alpha"]),
           "sources": (SRC_DIRNAME, "sources", ["source_dc", "ci_date", "dag", "start_hour", "data_size_gb", "alpha"]),
           "grid": ("", "grid", ["dag", "start_hour", "data_size_gb", "alpha"])}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--study", default="multidate", choices=list(STUDIES))
    args = ap.parse_args(argv)
    sub, tag, keys = STUDIES[args.study]
    d = RESULTS / sub if sub else RESULTS
    ev = reprice(pd.read_csv(d / f"{tag}_evals.csv"))
    print(f"{args.study}: {len(ev)} evaluations re-priced; CI reconstruction max relative error "
          f"{ev.recon_rel_err.max():.2e}")
    summ = pd.read_csv(d / f"{tag}_summary.csv")
    for metric in ("location", "brown"):
        for eps in (0.02, 0.001):
            t = compare(summ, ev, keys, metric, eps)
            g = lambda a, b: 100 * (1 - t[a] / t[b]).where(t[b] > 0)  # noqa: E731
            print(f"  {metric:8s} eps={eps:<6g} n={len(t):3d} | Ours vs B3 {g('Ours', 'B3').mean():5.2f} % | "
                  f"Ours-P vs B3 {g('OursP', 'B3').mean():5.2f} % (share>=5 % {(g('OursP', 'B3') >= 5).mean():.2f}) | "
                  f"Ours-P vs Ours {g('OursP', 'Ours').mean():5.2f} % (max {g('OursP', 'Ours').max():5.2f}) | "
                  f"never worse: {bool((t.OursP <= t.Ours + 1e-6).all())}")


if __name__ == "__main__":
    main()
