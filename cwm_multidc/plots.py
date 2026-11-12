"""Figures and tables for the Deadline Tension experiments (reads results/*.csv)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

from .optimizer import BASELINE_NAMES  # noqa: E402

# Reference categorical palette (dataviz skill, light mode), fixed order, never cycled.
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
TEXT, TEXT2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

METHODS = ["Ours", "B1", "B2", "B3", "B4", "B5"]
METHOD_COLOR = dict(zip(METHODS, SLOTS))  # colour follows the method, never its rank
METHOD_MARK = {"Ours": "o", "B1": "s", "B2": "v", "B3": "D", "B4": "^", "B5": "P"}
DCS = ["DC_Frankfurt", "DC_Oslo", "DC_Paris", "DC_Warsaw", "DC_California", "DC_Mumbai"]
DC_COLOR = dict(zip(DCS, SLOTS))
DC_SHORT = {"DC_Frankfurt": "FRA", "DC_Oslo": "OSL", "DC_Paris": "PAR", "DC_Warsaw": "WAW",
            "DC_California": "CAL", "DC_Mumbai": "BOM"}
DC_MARK = {"DC_Frankfurt": "s", "DC_Oslo": "o", "DC_Paris": "D", "DC_Warsaw": "^",
           "DC_California": "v", "DC_Mumbai": "P"}


def _style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": TEXT2, "xtick.color": TEXT2, "ytick.color": TEXT2,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
        "axes.spines.right": False, "font.size": 9, "axes.titlesize": 10, "axes.titlecolor": TEXT,
        "legend.frameon": False, "lines.linewidth": 2, "lines.markersize": 6,
    })


SYNTHETIC_NOTE = "Synthetic carbon-intensity data (development only; not empirical results)."


def _source(df: pd.DataFrame) -> str:
    """CI provenance of a results frame: 'synthetic' if any row used synthetic CI."""
    if df.synthetic_ci.astype(str).str.lower().eq("true").any() or "ci_source" not in df:
        return "synthetic"
    labels = sorted(set(df.ci_source.dropna().astype(str)))
    return "synthetic" if not labels or "synthetic" in labels else ",".join(labels)


def _ci_note(source: str) -> str:
    """Footer text from ci_source labels of the form '<description>@<start date>'."""
    if source == "synthetic":
        return SYNTHETIC_NOTE
    parts = [lab.rsplit("@", 1) for lab in source.split(",")]
    texts = sorted({p[0] for p in parts})
    dates = sorted({p[1] for p in parts if len(p) == 2})
    return (f"Carbon intensity: {'; '.join(texts)} historical hourly data, "
            f"window starting {', '.join(dates)} UTC.")


def _footer(fig, source: str):
    import textwrap
    width = max(60, int(fig.get_figwidth() * 17))  # ~17 chars per inch at 7 pt
    fig.text(0.01, 0.005, textwrap.fill(_ci_note(source), width), color=TEXT2, fontsize=7,
             ha="left", va="bottom")


def _label(m):
    return f"{m}: {BASELINE_NAMES[m]}" if m != "Ours" else "Ours: Joint Spatiotemporal"


# --------------------------------------------------------------------------- figures
def fig_pareto(evals: pd.DataFrame, summ: pd.DataFrame, out: Path, size=1000.0, alpha=2.0, dags=None):
    dags = [d for d in (dags or sorted(evals.dag.unique())) if d in set(evals.dag)]
    fig, axes = plt.subplots(1, len(dags), figsize=(6.0 * len(dags), 4.8), squeeze=False)
    for ax, dag in zip(axes[0], dags):
        e = evals[(evals.dag == dag) & (evals.data_size_gb == size) & np.isclose(evals.alpha, alpha, atol=0.02)
                  & (evals.scheduler == "cwm") & (evals.status == "ok")
                  & ((evals.role == "grid") if "role" in evals else True)]
        if e.empty:
            ax.set_visible(False)
            continue
        e = e.assign(net=e.net_gco2 / 1e3, comp=e.comp_gco2 / 1e3)
        for dc in DCS:
            d = e[e.dc == dc].sort_values("t_net_s")
            if d.empty:
                continue
            ax.plot(d.net, d.comp, "-", color=DC_COLOR[dc], lw=1, alpha=0.6)
            ax.scatter(d.net, d.comp, s=22, color=DC_COLOR[dc], marker=DC_MARK[dc],
                       edgecolor=SURFACE, linewidth=1, zorder=3, label=DC_SHORT[dc])
        # Pareto front (non-dominated points)
        pts = e.sort_values(["net", "comp"])[["net", "comp"]].to_numpy()
        front, best = [], np.inf
        for x, y in pts:
            if y < best:
                front.append((x, y))
                best = y
        if front:
            fx, fy = zip(*front)
            ax.step(fx, fy, where="post", color=TEXT2, lw=1, ls=":", label="Pareto front")
        s = summ[(summ.dag == dag) & (summ.data_size_gb == size) & np.isclose(summ.alpha, alpha, atol=0.02)]
        # zoom on the region spanned by the compared methods (far, dominated points clipped)
        ref = s[s.method.isin(["Ours", "B3", "B4", "B5"])].dropna(subset=["total_gco2"])
        span = 1.6 * max(ref.net_gco2.max(), ref.comp_gco2.max()) / 1e3 if len(ref) else e.net.max()
        xmax, ymax = span, span
        n_out = int(((e.net > xmax) | (e.comp > ymax)).sum())
        if n_out:
            ax.text(0.99, 0.02, f"{n_out} dominated points outside view", transform=ax.transAxes,
                    ha="right", va="bottom", fontsize=7, color=TEXT2)
        tot_min = (e.net + e.comp).min()
        for t in (tot_min, ref.total_gco2.max() / 1e3 if len(ref) else tot_min):
            ax.plot([0, t], [t, 0], color=TEXT2, lw=0.8, ls="--", zorder=0, alpha=0.5)
        for m in ("Ours", "B3", "B4", "B5"):
            r = s[s.method == m]
            if r.empty or pd.isna(r.total_gco2.iloc[0]):
                continue
            x, y = r.net_gco2.iloc[0] / 1e3, r.comp_gco2.iloc[0] / 1e3
            ax.scatter([x], [y], s=120, facecolor="none", edgecolor=TEXT, linewidth=1.5, zorder=4)
            same = [mm for mm in ("Ours", "B3", "B4", "B5") if mm != m and not s[s.method == mm].empty
                    and np.isclose(s[s.method == mm].total_gco2.iloc[0], r.total_gco2.iloc[0])]
            if any(METHODS.index(mm) < METHODS.index(m) for mm in same):
                continue  # label drawn once for coincident methods
            ax.annotate("=".join([m] + same), (x, y), xytext=(7, 7), textcoords="offset points",
                        color=TEXT, fontsize=8)
        ax.set_xlim(0, xmax)
        ax.set_ylim(0, ymax)
        ax.set_xlabel("Network carbon (kgCO$_2$)")
        ax.set_ylabel("Compute carbon (kgCO$_2$)")
        ax.set_title(f"{dag}: Δ = {size / 1000:g} TB, D = {alpha}·M\none point per (DC, T$_{{net}}$); dashed = iso-total")
        ax.legend(fontsize=7, ncol=2, loc="upper right")
    _footer(fig, _source(evals))
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out / "fig_pareto.png", dpi=180)
    plt.close(fig)


def _method_lines(ax, s: pd.DataFrame, x: str, logx=False):
    for m in METHODS:
        d = s[s.method == m].sort_values(x)
        if d.empty:
            continue
        ours = m == "Ours"
        ax.plot(d[x], d.total_gco2 / 1e3, marker=METHOD_MARK[m], color=METHOD_COLOR[m],
                lw=5 if ours else 1.3, ls="-" if ours else (0, (4, 2)), ms=9 if ours else 5,
                markeredgecolor=SURFACE, alpha=0.55 if ours else 1.0, label=_label(m),
                zorder=2 if ours else 3)
    if logx:
        ax.set_xscale("log")
    ax.set_ylabel("Total carbon (kgCO$_2$)")
    ax.set_ylim(bottom=0)


def _choice_strip(ax, s: pd.DataFrame, x: str, logx=False):
    o = s[s.method == "Ours"].sort_values(x)
    ax.plot(o[x], o.t_net_h, color=METHOD_COLOR["Ours"], marker="o", ms=5, markeredgecolor=SURFACE)
    for _, r in o.iterrows():
        if pd.notna(r.dc):
            ax.annotate(DC_SHORT.get(r.dc, r.dc), (r[x], r.t_net_h), xytext=(0, 6),
                        textcoords="offset points", ha="center", fontsize=7, color=TEXT2)
    if logx:
        ax.set_xscale("log")
    ax.set_ylabel("Ours: T$_{net}$ (h)")
    ax.set_ylim(bottom=-0.2, top=max(1.0, o.t_net_h.max() * 1.35 if len(o) else 1.0))


def fig_sweep(summ: pd.DataFrame, out: Path, kind: str):
    dags = sorted(summ.dag.unique())
    fig, axes = plt.subplots(2, len(dags), figsize=(max(9.0, 5.2 * len(dags)), 5.8), squeeze=False,
                             gridspec_kw={"height_ratios": [3, 1.3]}, sharex="col")
    for j, dag in enumerate(dags):
        if kind == "deadline":
            s = summ[(summ.dag == dag) & (summ.data_size_gb == 1000.0)]
            x, logx, title = "alpha", False, f"{dag}: deadline sweep (Δ = 1 TB)"
        else:
            s = summ[(summ.dag == dag) & np.isclose(summ.alpha, 2.0)]
            x, logx, title = "data_size_gb", True, f"{dag}: data-volume sweep (D = 2.0·M)"
        _method_lines(axes[0][j], s, x, logx)
        axes[0][j].set_title(title)
        _choice_strip(axes[1][j], s, x, logx)
        axes[1][j].set_xlabel("Deadline factor α (D = α·M$_{HEFT}$)" if kind == "deadline" else "Input data Δ (GB)")
    h, l = axes[0][0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=3, fontsize=8, bbox_to_anchor=(0.5, 1.0))
    _footer(fig, _source(summ))
    fig.tight_layout(rect=(0, 0.03, 1, 0.9))
    fig.savefig(out / f"fig_{'deadline' if kind == 'deadline' else 'datasize'}.png", dpi=180)
    plt.close(fig)


def fig_heatmap(summ: pd.DataFrame, out: Path):
    dags = sorted(summ.dag.unique())
    fig, axes = plt.subplots(1, len(dags), figsize=(5.4 * len(dags), 4.2), squeeze=False)
    for ax, dag in zip(axes[0], dags):
        s = summ[summ.dag == dag]
        sizes = sorted(s.data_size_gb.unique())
        alphas = sorted(s.alpha.unique())
        o = s[s.method == "Ours"].set_index(["data_size_gb", "alpha"])
        b3 = s[s.method == "B3"].set_index(["data_size_gb", "alpha"])
        idx = np.full((len(sizes), len(alphas)), np.nan)
        for i, sz in enumerate(sizes):
            for k, a in enumerate(alphas):
                if (sz, a) in o.index and pd.notna(o.loc[(sz, a), "dc"]):
                    dc = o.loc[(sz, a), "dc"]
                    idx[i, k] = DCS.index(dc)
                    tn = o.loc[(sz, a), "t_net_h"]
                    txt = DC_SHORT[dc] + (f"\n+{tn:.1f}h" if tn > 1e-9 else "")
                    if (sz, a) in b3.index and pd.notna(b3.loc[(sz, a), "total_gco2"]):
                        ot, bt = o.loc[(sz, a), "total_gco2"], b3.loc[(sz, a), "total_gco2"]
                        txt += "\n=B3" if np.isclose(ot, bt) else f"\n{(1 - ot / bt) * 100:+.0f}%"
                    else:
                        txt += "\n(B3 n/a)"
                    ax.text(k, i, txt, ha="center", va="center", fontsize=6.5,
                            color="#ffffff" if dc in ("DC_Frankfurt", "DC_California", "DC_Mumbai") else TEXT)
        ax.imshow(idx, cmap=ListedColormap(SLOTS[:len(DCS)]), vmin=-0.5, vmax=len(DCS) - 0.5,
                  aspect="auto", origin="lower")
        ax.set_xticks(range(len(alphas)), [f"{a:g}" for a in alphas])
        ax.set_yticks(range(len(sizes)), [f"{sz / 1000:g} TB" if sz >= 1000 else f"{sz:g} GB" for sz in sizes])
        ax.set_xlabel("Deadline factor α")
        ax.set_ylabel("Input data Δ")
        ax.grid(False)
        ax.set_title(f"{dag}: DC chosen by Ours (+T$_{{net}}$ wait, gain vs B3)")
    _footer(fig, _source(summ))
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out / "fig_heatmap.png", dpi=180)
    plt.close(fig)


# ---------------------------------------------------------------- new figures
ABL = ["B3", "A1", "A2", "C1", "B1"]
ABL_COLOR = {"B3": SLOTS[3], "A1": SLOTS[6], "A2": SLOTS[4], "C1": SLOTS[7], "B1": SLOTS[1]}


def _gain(piv, m):
    both = piv[["Ours", m]].dropna() if m in piv else pd.DataFrame(columns=["Ours", m])
    both = both[both[m] > 0]
    return 1 - both["Ours"] / both[m]


def fig_ablation(hs: pd.DataFrame, out: Path):
    """Per-problem gain of Ours over B3, the ablations and the equal-budget control."""
    keys = ["dag", "start_hour", "alpha"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 6.2), sharey=True)
    for ax, metric in zip(axes, ("brown", "location")):
        d = hs[(hs.metric == metric) & np.isclose(hs.eps_kwh_per_gb, 0.02)]
        piv = d.pivot_table(index=keys, columns="method", values="total_gco2", aggfunc="first")
        labels = [f"{a} · {b}h · α={c:g}" for a, b, c in piv.index]
        y = np.arange(len(piv))
        for k, m in enumerate(ABL):
            if m not in piv:
                continue
            g = (1 - piv["Ours"] / piv[m]).where(piv[m] > 0) * 100
            ax.scatter(g, y + (k - 2) * 0.13, s=26, color=ABL_COLOR[m], edgecolor=SURFACE, linewidth=1,
                       label=f"vs {m}: {BASELINE_NAMES[m]}", zorder=3)
        ax.axvline(0, color=TEXT2, lw=0.8)
        ax.axvline(5, color=TEXT2, lw=0.8, ls=":")
        ax.set_yticks(y, labels, fontsize=7)
        ax.set_xlabel("Gain of Ours (% of baseline total carbon)")
        ax.set_title(f"{metric} compute metric (dotted: 5% target)")
        ax.set_xscale("symlog", linthresh=10)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=3, fontsize=7.5, bbox_to_anchor=(0.5, 1.0))
    _footer(fig, _source(hs))
    fig.tight_layout(rect=(0, 0.03, 1, 0.88))
    fig.savefig(out / "fig_ablation.png", dpi=180)
    plt.close(fig)


def fig_sensitivity(ss: pd.DataFrame, gs: pd.DataFrame | None, out: Path):
    """kappa, bandwidth, eps_net (post hoc) and forecast error: Ours vs B3 vs B1 (brown metric)."""
    show = ["Ours", "B3", "B1"]
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.9))
    base = ss[(ss.metric == "brown") & np.isclose(ss.eps_kwh_per_gb, 0.02)]

    def lines(ax, d, x, xlabel, logx=False):
        for m in show:
            q = d[d.method == m].groupby(x).total_gco2.agg(["mean", "min", "max"]).reset_index()
            if q.empty:
                continue
            ax.plot(q[x], q["mean"] / 1e3, marker=METHOD_MARK[m], color=METHOD_COLOR[m], ms=6,
                    markeredgecolor=SURFACE, lw=2.4 if m == "Ours" else 1.4, label=_label(m))
            if (q["max"] > q["min"]).any():
                ax.fill_between(q[x], q["min"] / 1e3, q["max"] / 1e3, color=METHOD_COLOR[m], alpha=0.12, lw=0)
        ax.set_xlabel(xlabel)
        if logx:
            ax.set_xscale("log")
        ax.set_ylim(bottom=0)

    k = base[base.experiment == "kappa"].assign(kappa_s=lambda t: 3600 / t.units_per_hour)
    lines(axes[0], k, "kappa_s", "κ (seconds per CWM unit)")
    axes[0].set_ylabel("Total carbon (kgCO$_2$)")
    axes[0].set_title("Time scale κ")
    bw = pd.concat([base[base.experiment == "bandwidth"], k[np.isclose(k.units_per_hour, 30)]])
    lines(axes[1], bw, "bandwidth_gbps", "WAN bandwidth (Gbps)", logx=True)
    axes[1].set_title("Bandwidth")
    if gs is not None:
        e = gs[(gs.metric == "brown") & (gs.dag == "eager1000") & (gs.data_size_gb == 1000.0)
               & np.isclose(gs.alpha, 2.0)]
        lines(axes[2], e, "eps_kwh_per_gb", "ε$_{net}$ (kWh/GB)", logx=True)
    axes[2].set_title("Network energy intensity (post hoc)")
    fc = base[base.experiment == "forecast"]
    oracle = k[np.isclose(k.units_per_hour, 30)].assign(forecast_sigma=0.0)
    lines(axes[3], pd.concat([oracle, fc]), "forecast_sigma", "CI forecast error σ")
    axes[3].set_title("Decisions on noisy forecasts\n(realised carbon; band = seed range)")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=3, fontsize=8, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle(f"eager1000, Δ = 1 TB, D = 2.0·M", y=0.9, fontsize=9, color=TEXT2)
    _footer(fig, _source(ss))
    fig.tight_layout(rect=(0, 0.03, 1, 0.84))
    fig.savefig(out / "fig_sensitivity.png", dpi=180)
    plt.close(fig)


def fig_attenuation(out: Path):
    """Prop. 3: empirical maximum saving from delaying a transfer vs the sinc prediction."""
    from .cwm_runner import DEFAULT_CLUSTER
    from .data_loader import build_topology
    from .wan_model import integrate_piecewise_carbon_intensity as integ

    src = out / "ci_source.json"
    info = json.loads(src.read_text()) if src.exists() else {"label": "synthetic", "files": {}}
    if info["files"]:
        topo = build_topology(24 * 8, DEFAULT_CLUSTER, dcs=[tuple(d) for d in info["dcs"]], ci_csv=info["files"],
                              start_hour=info["offset_hours"] + 6)
    else:
        topo = build_topology(24 * 8, DEFAULT_CLUSTER, start_hour=6)
    taus = np.array([0.25, 0.5, 1, 2, 3, 4, 6, 8, 10, 12, 16, 20, 24, 30, 36])
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for k, dc in enumerate(["DC_Oslo", "DC_California", "DC_Paris"]):
        w = topo.wan_ci(dc)
        ci = np.array(w["ci"])
        n = (len(ci) // 24) * 24
        spec = np.fft.rfft(ci[:n] - ci[:n].mean())
        a1 = 2 * np.abs(spec[n // 24]) / n  # amplitude of the 24 h harmonic
        cbar = ci.mean()
        emp = []
        for tau_h in taus:
            tau = tau_h * 3600
            T = np.arange(0, (24 * 8 - 37) * 3600, 900.0)
            v = np.array([integ(t, t + tau, w["intervals"], w["ci"]) for t in T])
            # windowed peak-to-trough within each day, averaged over days
            per_day = [(v[i:i + 96].max() - v[i:i + 96].min()) / cbar for i in range(0, len(v) - 96, 96)]
            emp.append(np.mean(per_day))
        x = np.linspace(0.05, 36, 400)
        theo = 2 * a1 / cbar * np.abs(np.sinc(x / 24))  # np.sinc(x) = sin(pi x)/(pi x)
        c = [SLOTS[1], SLOTS[0], SLOTS[2]][k]
        ax.plot(x, theo * 100, color=c, lw=1.2, ls=(0, (4, 2)))
        ax.plot(taus, np.array(emp) * 100, marker="o", color=c, ms=5, markeredgecolor=SURFACE,
                label=f"Frankfurt→{dc[3:]}")
    ax.set_xlabel("Transfer duration τ (h)")
    ax.set_ylabel("Max saving from delaying (% of mean)")
    ax.set_title("Prop. 3 check: saving from delaying a transfer vs its duration")
    ax.text(0.99, 0.97, "solid: measured (daily peak-to-trough of window-mean WAN CI)\n"
            "dashed: 24 h harmonic only, 2A₁/c̄·|sinc(πτ/24 h)|\n"
            "gap above dashed = non-periodic (weather) variability", transform=ax.transAxes,
            ha="right", va="top", fontsize=7, color=TEXT2)
    ax.axvline(24, color=TEXT2, lw=0.8, ls=":")
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=8, loc="center right")
    _footer(fig, "synthetic" if topo.synthetic else info["label"])
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out / "fig_attenuation.png", dpi=180)
    plt.close(fig)


# ---------------------------------------------------------------------------- tables
TABLE_METHODS = ["B1", "B2", "B3", "B4", "B5", "A1", "A2", "C1"]


def gains_table(summ: pd.DataFrame) -> pd.DataFrame:
    keys = ["dag", "start_hour", "data_size_gb", "alpha"]
    piv = summ.pivot_table(index=keys, columns="method", values="total_gco2", aggfunc="first")
    rows = []
    for m in TABLE_METHODS:
        if m not in piv or piv[m].isna().all():
            continue
        g = _gain(piv, m)
        rows.append({"vs": f"{m}: {BASELINE_NAMES[m]}", "n": len(g),
                     "mean_gain_%": 100 * g.mean() if len(g) else np.nan,
                     "median_gain_%": 100 * g.median() if len(g) else np.nan,
                     "max_gain_%": 100 * g.max() if len(g) else np.nan,
                     "share_gain>=5%": (g >= 0.05).mean() if len(g) else np.nan,
                     "n_infeasible": int(piv[m].isna().sum())})
    return pd.DataFrame(rows)


def headline_md(summ: pd.DataFrame, out: Path, name: str):
    keys = ["dag", "start_hour", "data_size_gb", "alpha"]
    lines = [f"# {name}", ""]
    src = _source(summ)
    lines += [("> **Synthetic carbon-intensity data**: development results, not empirical findings."
               if src == "synthetic" else f"> {_ci_note(src)}"), ""]
    for metric in ("brown", "location"):
        d = summ[(summ.metric == metric) & np.isclose(summ.eps_kwh_per_gb, 0.02)]
        if d.empty:
            continue
        lines += [f"## {metric} metric, ε = 0.02 kWh/GB: gain = 1 − Ours/other (total gCO₂)", "",
                  gains_table(d).round(3).to_markdown(index=False), ""]
        o = d[d.method == "Ours"].copy()
        o = o[o.total_gco2 > 0]
        gap = (1 - o.separable_bound_gco2 / o.total_gco2).clip(lower=0)
        nm = o.nonmono_drops.sum() / max(1, o.nonmono_steps.sum())
        lines += [f"- Ours vs separable bound: median gap {100 * gap.median():.1f}% (max {100 * gap.max():.1f}%)",
                  f"- CWM non-monotonicity (Prop. 1 violations): {100 * nm:.1f}% of consecutive arrival steps", ""]
    d = summ[(summ.metric == "brown") & np.isclose(summ.eps_kwh_per_gb, 0.02)]
    per = d.pivot_table(index=keys, columns="method", values="total_gco2", aggfunc="first") / 1e3
    per = per[[m for m in METHODS + ["A1", "A2", "C1"] if m in per]]
    ours = d[d.method == "Ours"].set_index(keys)
    per["Ours DC"] = ours.dc.map(DC_SHORT)
    per["Ours T_net (h)"] = ours.t_net_h.round(2)
    lines += ["## Per problem, brown metric (total kgCO₂)", "", per.round(2).to_markdown(), ""]
    eps = summ[(summ.metric == "brown") & (summ.method.isin(["Ours", "B3"]))]
    if eps.eps_kwh_per_gb.nunique() > 1:
        lines += ["## ε_net sweep (brown metric, post hoc): gain of Ours over B3", ""]
        rows = []
        for e, g in eps.groupby("eps_kwh_per_gb"):
            piv = g.pivot_table(index=keys, columns="method", values="total_gco2", aggfunc="first")
            gg = _gain(piv, "B3")
            rows.append({"eps_kwh_per_gb": e, "n": len(gg), "mean_gain_%": 100 * gg.mean(),
                         "share_gain>=5%": (gg >= 0.05).mean()})
        lines += [pd.DataFrame(rows).round(3).to_markdown(index=False), ""]
    (out / f"{name}.md").write_text("\n".join(lines))


def make_all(results: Path):
    _style()
    results = Path(results)
    gs = None
    if (results / "grid_summary.csv").exists():
        gs_all = pd.read_csv(results / "grid_summary.csv")
        gs = gs_all
        main = gs_all[(gs_all.metric == "brown") & np.isclose(gs_all.eps_kwh_per_gb, 0.02)]
        ge = pd.read_csv(results / "grid_evals.csv")
        fig_pareto(ge, main, results, dags=["eager1000"] if "eager1000" in set(ge.dag) else None)
        fig_sweep(main, results, "deadline")
        fig_sweep(main, results, "datasize")
        fig_heatmap(main, results)
        headline_md(gs_all, results, "grid_gains")
    if (results / "headline_summary.csv").exists():
        hs = pd.read_csv(results / "headline_summary.csv")
        headline_md(hs, results, "headline")
        fig_ablation(hs, results)
    if (results / "sensitivity_summary.csv").exists():
        fig_sensitivity(pd.read_csv(results / "sensitivity_summary.csv"), gs, results)
    fig_attenuation(results)
    print(f"figures/tables written to {results}")
