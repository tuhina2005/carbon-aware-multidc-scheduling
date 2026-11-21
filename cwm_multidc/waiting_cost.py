"""Holding emissions: carbon spent while a job waits before its compute starts.

The base model charges network and compute energy only, so waiting to send the data is free.  In
reality something is held while the job waits: at least its input data on storage, at most reserved
servers.  This module charges a constant *holding power* P (W) from submission until compute starts,
at the carbon intensity of the grid where the job is held:

    Hold = P x [ int_{0}^{T_arr} CI_src(t) dt  +  int_{T_arr}^{T_arr + q} CI_d(t) dt ]

i.e. at the source grid until the data has arrived (waiting + transfer), then at the destination
grid while queued.  Every strategy pays it the same way: B3 pays for its transfer and its queue, Ours
additionally for any time it chooses to wait.

Holding carbon is linear in P and needs no solver calls, so every selection (Ours, baselines, rules)
is re-derived from the saved evaluations for each P.  P = 0 reproduces the saved summaries exactly
(checked by ``tests/test_waiting_cost.py``).

    python -m cwm_multidc.waiting_cost            # all three studies -> results/waiting/
"""

from __future__ import annotations

import argparse
import math
from dataclasses import fields, replace
from pathlib import Path

import numpy as np
import pandas as pd

from .cwm_runner import DAG_DIR, DEFAULT_CLUSTER, CWMRunner
from .data_loader import SECONDS_PER_HOUR, TimeScale, Topology, build_topology
from .experiments import (ALPHAS, EPS_DEFAULT, HEADLINE_ALPHAS, MD_DIR, RESULTS, SUB_DIR, SUB_REGIONS, CIConfig,
                          ct_queues)
from .optimizer import Evaluation, Problem, select

CI_DIR = RESULTS.parent / "data" / "public_ci"
OUT_DIR = RESULTS / "waiting"

# Holding power levels (W).  Realistic storage: about 1-20 W per TB held (disks up to whole storage
# servers with overhead), i.e. 0.1-20 W for the 100 GB-1 TB inputs used here.  The upper levels reach
# the cluster's idle power (16.9 kW), the unrealistic worst case of servers reserved while waiting.
POWER_W = (0.0, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0, 10000.0, 16854.0)
STORAGE_W_PER_TB = (1.0, 5.0, 20.0)

STUDIES = {
    # tag: (summary/evals folder, file prefix, comparison baselines)
    "multidate": (MD_DIR, "multidate", ("B3", "A1")),
    "substitution": (SUB_DIR, "substitution", ("B3", "A1")),
    "contention": ("contention", "contention", ("B3", "B7", "A1")),
}
METHODS = ("Ours", "B1", "B3", "B7", "A1", "R3")
KEYS = ["ci_date", "start_hour", "dag", "data_size_gb", "alpha", "contention_rho"]


# --------------------------------------------------------------------------- carbon
def _integral(values, t0: float, t1: float) -> float:
    """int_{t0}^{t1} CI dt in gCO2/kWh x h, for an hourly series starting at t = 0 (seconds)."""
    if t1 <= t0:
        return 0.0
    h0, h1 = t0 / SECONDS_PER_HOUR, t1 / SECONDS_PER_HOUR
    tot = 0.0
    for i in range(int(math.floor(h0)), int(math.ceil(h1))):
        lo, hi = max(h0, i), min(h1, i + 1)
        if hi > lo:
            tot += (hi - lo) * values[i]
    return tot


def holding_gco2_per_w(e: Evaluation, topo: Topology) -> float:
    """Holding carbon (g) per watt of holding power for one evaluated candidate."""
    t_arr = 0.0 if e.dc == topo.source else e.t_arrival_s
    src = _integral(topo.source_dc.ci.values, 0.0, t_arr)
    dst = _integral(topo.dc(e.dc).ci.values, t_arr, t_arr + (e.queue_wait_s or 0.0))
    return (src + dst) / 1000.0  # W x h x g/kWh / 1000 = g


def with_holding(e: Evaluation, grams: float) -> Evaluation:
    """Copy of ``e`` with holding carbon added to both compute metrics (so totals include it)."""
    if not e.ok or grams == 0:
        return e
    return replace(e, comp_gco2=e.comp_gco2 + grams, comp_loc_gco2=e.comp_loc_gco2 + grams,
                   total_gco2=e.total_gco2 + grams)


# ------------------------------------------------------------------------ re-loading
_EVAL_FIELDS = {f.name for f in fields(Evaluation)}


def _eval_from_row(r: dict) -> Evaluation:
    kw = {}
    for k in _EVAL_FIELDS:
        v = r.get(k)
        if isinstance(v, float) and math.isnan(v):
            v = None
        kw[k] = v
    kw["seeds"] = tuple(int(s) for s in str(r.get("seeds") or "").split())
    kw["message"] = kw["message"] or ""
    for k in ("t_arrival_units", "d_prime_units", "t_start_units"):
        if kw[k] is not None:
            kw[k] = int(kw[k])
    kw["queue_wait_s"] = kw["queue_wait_s"] or 0.0
    return Evaluation(**kw)


_HEFT: dict[str, int] = {}


def _topology(tag: str, dag: str, date: str, start: int, rho: float) -> Topology:
    """The topology the study used for this problem (mirrors experiments.Runner.topology)."""
    ci = CIConfig(CI_DIR, date)
    if tag == "substitution":
        ci.dcs = tuple(d for d in ci.dcs if d[1] in SUB_REGIONS)
    if dag not in _HEFT:
        _HEFT[dag] = CWMRunner().heft_makespan(DAG_DIR / f"{dag}.dot")
    ts = TimeScale()
    hours = int(math.ceil(max(ALPHAS + HEADLINE_ALPHAS) * _HEFT[dag] / ts.units_per_hour)) + 2
    queues = ct_queues(rho, ci.dcs) if rho else None
    return build_topology(hours, DEFAULT_CLUSTER, dcs=ci.dcs, ci_csv=ci.ci_csv, start_hour=ci.offset + start,
                          timescale=ts, queues=queues)


def load_problems(tag: str):
    """Yield (key, problem, evals, d_units, m_ref, green) for every problem of a study."""
    folder, prefix, _ = STUDIES[tag]
    ev = pd.read_csv(RESULTS / folder / f"{prefix}_evals.csv")
    sm = pd.read_csv(RESULTS / folder / f"{prefix}_summary.csv")
    for df in (ev, sm):
        if "contention_rho" not in df:
            df["contention_rho"] = 0.0
        df["contention_rho"] = df["contention_rho"].fillna(0.0)
    # evals carry the effective alpha (D / M, e.g. 1.5015); summaries the nominal one (1.5): take the nominal
    nominal = sm[["ci_date", "start_hour", "dag", "data_size_gb", "contention_rho", "deadline_units", "alpha"]] \
        .drop_duplicates()
    ev = ev.drop(columns="alpha").merge(nominal, on=["ci_date", "start_hour", "dag", "data_size_gb",
                                                     "contention_rho", "deadline_units"], how="left",
                                        validate="many_to_one")
    if ev.alpha.isna().any():
        raise ValueError(f"{tag}: evaluations without a matching summary problem")
    green =(sm[sm.method == "Ours"].drop_duplicates(KEYS).set_index(KEYS)["greenest_dc"])
    for key, g in ev.groupby(KEYS, sort=True):
        date, start, dag, size, alpha, rho = key
        topo = _topology(tag, dag, date, int(start), float(rho))
        prob = Problem(DAG_DIR / f"{dag}.dot", topo, float(size), alpha=float(alpha))
        evals = [_eval_from_row(r) for r in g.to_dict("records")]
        gd = green.get(key)
        yield key, prob, evals, int(g.deadline_units.iloc[0]), int(g.m_ref_units.iloc[0]), \
            (None if isinstance(gd, float) else gd)


# ---------------------------------------------------------------------------- sweep
def sweep(tag: str, powers=POWER_W, metric: str = "location") -> pd.DataFrame:
    """One row per problem x holding power x method: total carbon (g) and the chosen point."""
    rows = []
    for key, prob, evals, d_units, m_ref, green in load_problems(tag):
        per_w = [holding_gco2_per_w(e, prob.topology) if e.ok else 0.0 for e in evals]
        for p in powers:
            ev = [with_holding(e, p * w) for e, w in zip(evals, per_w)]
            sel = select(prob, ev, d_units, green, metric, 1.0, m_ref=m_ref)
            for m in METHODS:
                e = sel.get(m)
                rows.append(dict(zip(KEYS, key), power_w=p, method=m,
                                 total_gco2=None if e is None else e.total_gco2,
                                 dc=None if e is None else e.dc,
                                 t_net_h=None if e is None else e.t_net_s / 3600,
                                 queue_h=None if e is None else (e.queue_wait_s or 0.0) / 3600))
    return pd.DataFrame(rows)


def gains(df: pd.DataFrame, versus: tuple[str, ...]) -> pd.DataFrame:
    """Mean / share >= 5 % gain of Ours over each baseline, per holding power (and rho if present)."""
    by = ["power_w"] + (["contention_rho"] if df.contention_rho.nunique() > 1 else [])
    piv = df.pivot_table(index=KEYS + ["power_w"], columns="method", values="total_gco2", aggfunc="first")
    ours = df[df.method == "Ours"]
    waits = (ours.t_net_h > 0).groupby([ours[c] for c in by]).mean()
    out = []
    for grp, p in piv.reset_index().groupby(by):
        grp = grp if isinstance(grp, tuple) else (grp,)
        row = dict(zip(by, grp), n=len(p), ours_waits_pct=100 * float(waits.loc[grp if len(grp) > 1 else grp[0]]))
        for b in versus:
            ok = p[b].notna() & (p[b] > 0)
            g = 1 - p.loc[ok, "Ours"] / p.loc[ok, b]
            row[f"gain_vs_{b}_pct"] = 100 * g.mean()
            row[f"share5_vs_{b}_pct"] = 100 * (g >= 0.05).mean()
            row[f"{b}_infeasible"] = int((~p[b].notna()).sum())
        out.append(row)
    return pd.DataFrame(out)


def break_even(g: pd.DataFrame, col: str) -> float | None:
    """Smallest holding power (W, log-linear interpolation) at which the mean gain drops to <= 0.1 %."""
    g = g.sort_values("power_w")
    xs, ys = g.power_w.to_numpy(), g[col].to_numpy()
    for i in range(1, len(xs)):
        if ys[i] <= 0.1 < ys[i - 1]:
            x0, x1 = max(xs[i - 1], 1e-3), xs[i]
            f = (ys[i - 1] - 0.1) / (ys[i - 1] - ys[i])
            return float(np.exp(np.log(x0) + f * (np.log(x1) - np.log(x0))))
    return None if ys[-1] > 0.1 else float(xs[0])


STORAGE_BAND_W = (0.1, 20.0)  # 1-20 W/TB x 0.1-1 TB: the realistic holding power for these jobs
LABELS = {"multidate": "Seasonal study (all 5 DCs)", "substitution": "H6: swinging grids only",
          "contention": "W2: queues, ρ = 2"}


def _curves(tag: str, g: pd.DataFrame) -> pd.DataFrame:
    return g[g.contention_rho == 2.0] if tag == "contention" and "contention_rho" in g else g


def figure(results: dict[str, pd.DataFrame]) -> None:
    from . import plots

    plots._style()
    plt = plots.plt
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.6), sharey=False)
    panels = (("gain_vs_B3_pct", "Gain of Ours over B3 (greenest DC + CWM), %"),
              ("gain_vs_A1_pct", "Value of waiting: gain of Ours over A1 (no wait), %"))
    for ax, (col, title) in zip(axes, panels):
        ax.axvspan(*STORAGE_BAND_W, color=plots.GRID, alpha=0.6, lw=0)
        for i, (tag, g) in enumerate(results.items()):
            c = _curves(tag, g).sort_values("power_w")
            ax.plot(c.power_w, c[col], marker="o", ms=3.5, color=plots.SLOTS[i], label=LABELS[tag])
            if tag == "contention" and col == "gain_vs_B3_pct":
                ax.plot(c.power_w, c.gain_vs_B7_pct, marker="o", ms=3.5, ls="--", color=plots.SLOTS[i],
                        label="W2: Ours over B7 (queue-aware), ρ = 2")
        ax.set_xscale("symlog", linthresh=1.0)
        ax.set_xlim(0, 2e4)
        ax.set_ylim(bottom=0)
        ax.set_xlabel("Holding power while waiting / queued (W)")
        ax.set_title(title, loc="left")
        ax.text(1.2, ax.get_ylim()[1] * 0.02, "realistic storage", va="bottom", color=plots.TEXT2, fontsize=7.5)
    axes[0].legend(fontsize=7.5, loc="upper left", bbox_to_anchor=(0.0, 0.88))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    plots._footer(fig, "Energy-Charts/ENTSO-E + CAISO 2024 (production-based life-cycle CI)@2024-01-17 to 2024-10-16")
    fig.savefig(OUT_DIR / "fig_holding.png", dpi=180)
    plt.close(fig)


def markdown(results: dict[str, pd.DataFrame]) -> None:
    lines = ["# Holding emissions: does waiting still pay when waiting has a cost?", "",
             "Holding power P (W) is charged from submission until compute starts: at the source grid's CI until the "
             "data has arrived, then at the destination grid's CI while queued (`cwm_multidc/waiting_cost.py`). "
             "Every method pays it; every selection is re-derived from the saved evaluations (no new solver calls). "
             "Location metric, ε = 0.02 kWh/GB. Realistic storage for these 0.1–1 TB inputs is about "
             f"{STORAGE_BAND_W[0]:g}–{STORAGE_BAND_W[1]:g} W; the top level is the whole cluster's idle power.", ""]
    for tag, g in results.items():
        lines += [f"## {LABELS[tag] if tag != 'contention' else 'W2: queues'}", ""]
        cols = [c for c in g.columns if c.startswith(("gain_", "share5_", "ours_waits", "B3_inf"))]
        keep = ["power_w"] + (["contention_rho"] if "contention_rho" in g else []) + cols
        lines += [g[keep].round(2).to_markdown(index=False), ""]
        grps = [("", g)] if "contention_rho" not in g else [(f" at ρ = {r:g}", x) for r, x in g.groupby("contention_rho")]
        for lab, x in grps:
            be = break_even(x, "gain_vs_A1_pct")
            lines.append(f"- Break-even holding power for the value of waiting{lab}: "
                         + (f"**{be:,.0f} W**" if be else "not reached within the swept range (≤ 16.9 kW)"))
        lines.append("")
    lines += ["Ours can never lose to B3, A1 or B7: they are points of its search space, re-selected under the same "
              "holding cost. At high holding power Ours stops waiting (A1 gain → 0) but keeps beating B3, because "
              "it then prefers destinations whose transfer is short or none.", ""]
    (OUT_DIR / "holding.md").write_text("\n".join(lines))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--studies", default=",".join(STUDIES))
    ap.add_argument("--from-csv", action="store_true", help="re-draw figure/table from saved CSVs only")
    args = ap.parse_args(argv)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for tag in args.studies.split(","):
        if args.from_csv:
            results[tag] = pd.read_csv(OUT_DIR / f"{tag}_holding_gains.csv")
            continue
        df = sweep(tag)
        df.to_csv(OUT_DIR / f"{tag}_holding.csv", index=False)
        g = gains(df, STUDIES[tag][2])
        g.to_csv(OUT_DIR / f"{tag}_holding_gains.csv", index=False)
        results[tag] = g
        print(f"== {tag}\n{g.round(2).to_string(index=False)}", flush=True)
    markdown(results)
    figure(results)


if __name__ == "__main__":
    main()
