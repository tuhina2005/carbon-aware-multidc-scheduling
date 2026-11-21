"""Carbon vs deadline, and results by workflow type (from saved summaries; no solver calls).

    python -m cwm_multidc.tradeoffs        # -> results/tradeoffs/{tradeoffs.md, fig_deadline_tradeoff.png}

1. Deadline trade-off.  CWM stretches a schedule to fill its window (median makespan = 99.8 % of D'),
   so a job finishes at its deadline whatever the placement; "makespan vs carbon" is therefore the
   deadline D itself.  From the seasonal study (alpha = 1.5 / 2.0 / 2.5): mean carbon per job against
   D in hours, and the carbon saved per extra hour of deadline.
2. Workflow types.  Headline study (4 workflows, 17 Apr 2024): what CWM adds over HEFT (gain vs B2) and
   joint gain over B3.  Seasonal study (2 workflows): joint gain, the value of waiting, and the
   saving split into network and compute carbon.
"""

from __future__ import annotations

import re

import pandas as pd

from .cwm_runner import DAG_DIR
from .experiments import EPS_DEFAULT, MD_DIR, RESULTS

OUT_DIR = RESULTS / "tradeoffs"
UNITS_PER_HOUR = 30
MD_KEYS = ["ci_date", "start_hour", "dag", "data_size_gb", "alpha"]
HL_KEYS = ["dag", "start_hour", "data_size_gb", "alpha"]


def _load(path, metric="location") -> pd.DataFrame:
    s = pd.read_csv(path)
    return s[(s.metric == metric) & ((s.eps_kwh_per_gb - EPS_DEFAULT).abs() < 1e-12)]


def _wide(s: pd.DataFrame, keys, col="total_gco2") -> pd.DataFrame:
    return s.pivot_table(index=keys, columns="method", values=col, aggfunc="first")


def dag_shape(dag: str) -> tuple[int, int]:
    """(tasks, dependencies) of a workflow .dot file."""
    text = (DAG_DIR / f"{dag}.dot").read_text()
    return len(re.findall(r"^\s*\w+\s*\[", text, re.M)), text.count("->")


# --------------------------------------------------------------------------- deadline
def deadline_table(ms: pd.DataFrame) -> pd.DataFrame:
    w = _wide(ms, MD_KEYS)
    meta = ms[ms.method == "Ours"].drop_duplicates(MD_KEYS).set_index(MD_KEYS)
    w["D_h"] = meta.deadline_units / UNITS_PER_HOUR
    t = w.groupby(["dag", "data_size_gb", "alpha"])[["D_h", "B1", "B3", "Ours"]].mean()
    t[["B1", "B3", "Ours"]] /= 1000.0  # kg per job
    return t.reset_index()


def per_hour(t: pd.DataFrame) -> pd.DataFrame:
    """Carbon saved per extra hour of deadline, alpha 1.5 -> 2.5, for each method (g/h)."""
    rows = []
    for (dag, size), g in t.groupby(["dag", "data_size_gb"]):
        g = g.sort_values("alpha")
        dh = g.D_h.iloc[-1] - g.D_h.iloc[0]
        rows.append({"dag": dag, "data_size_gb": size, "extra_hours": dh,
                     **{f"{m}_g_per_h": 1000 * (g[m].iloc[0] - g[m].iloc[-1]) / dh for m in ("B1", "B3", "Ours")}})
    return pd.DataFrame(rows)


def figure(t: pd.DataFrame) -> None:
    from . import plots

    plots._style()
    plt = plots.plt
    dags = sorted(t.dag.unique())
    fig, axes = plt.subplots(1, len(dags), figsize=(4.6 * len(dags), 3.4))
    for ax, dag in zip(axes, dags):
        for m in ("B1", "B3", "Ours"):
            # B1 never transfers, so its carbon does not depend on the data size: draw it once
            for size, ls in (((1000.0, "-"),) if m == "B1" else ((1000.0, "-"), (100.0, ":"))):
                g = t[(t.dag == dag) & (t.data_size_gb == size)].sort_values("D_h")
                lab = "B1 (stay in Frankfurt)" if m == "B1" else f"{m}, {size / 1000:g} TB"
                ax.plot(g.D_h, g[m], ls=ls, marker=plots.METHOD_MARK[m], ms=4, color=plots.METHOD_COLOR[m],
                        label=lab if dag == dags[0] else None)
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}" if str(v)[0] in "25" else ""))
        ax.set_xlabel("Deadline D (hours after submission)")
        ax.set_ylabel("Mean carbon per job (kg CO₂, log)")
        ax.set_title(dag, loc="left")
    fig.legend(fontsize=7.5, ncol=5, loc="upper center")
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    plots._footer(fig, plots._source(MS_CACHE["ms"]))
    fig.savefig(OUT_DIR / "fig_deadline_tradeoff.png", dpi=180)
    plt.close(fig)


MS_CACHE: dict[str, pd.DataFrame] = {}


# -------------------------------------------------------------------------- workflows
def headline_workflows(hs: pd.DataFrame) -> pd.DataFrame:
    w = _wide(hs, HL_KEYS)
    meta = hs[hs.method == "Ours"].drop_duplicates(HL_KEYS).set_index(HL_KEYS)
    df = pd.DataFrame({"M_h": meta.m_ref_units / UNITS_PER_HOUR,
                       "gain_vs_B2_pct": 100 * (1 - w.Ours / w.B2), "gain_vs_B3_pct": 100 * (1 - w.Ours / w.B3),
                       "ours_kg": w.Ours / 1000}).reset_index()
    out = df.groupby("dag").mean(numeric_only=True)[["M_h", "ours_kg", "gain_vs_B2_pct", "gain_vs_B3_pct"]]
    shape = {d: dag_shape(d) for d in out.index}
    out.insert(0, "tasks", [shape[d][0] for d in out.index])
    out.insert(1, "dependencies", [shape[d][1] for d in out.index])
    return out.reset_index()


def seasonal_workflows(ms: pd.DataFrame) -> pd.DataFrame:
    idx = lambda m: ms[ms.method == m].set_index(MD_KEYS)  # noqa: E731
    o, b, a = idx("Ours"), idx("B3"), idx("A1")
    df = pd.DataFrame({"M_h": o.m_ref_units / UNITS_PER_HOUR, "B3_kg": b.total_gco2 / 1000,
                       "net_share_B3_pct": 100 * b.net_gco2 / b.total_gco2,
                       "gain_vs_B3_pct": 100 * (1 - o.total_gco2 / b.total_gco2),
                       "value_of_waiting_pct": 100 * (1 - o.total_gco2 / a.total_gco2),
                       "saved_net_g": b.net_gco2 - o.net_gco2, "saved_comp_g": b.comp_gco2 - o.comp_gco2,
                       "waits_pct": 100 * (o.t_net_h > 0)}).reset_index()
    return df.groupby(["dag", "data_size_gb"]).mean(numeric_only=True).drop(columns=["start_hour", "alpha"]).reset_index()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ms = _load(RESULTS / MD_DIR / "multidate_summary.csv")
    hs = _load(RESULTS / "headline_summary.csv")
    MS_CACHE["ms"] = ms
    t = deadline_table(ms)
    ph = per_hour(t)
    hw, sw = headline_workflows(hs), seasonal_workflows(ms)
    figure(t)
    md = ["# Carbon vs deadline, and results by workflow type", "",
          "Location metric, ε = 0.02 kWh/GB, from the saved summaries (no solver calls). "
          "CWM fills its window (median makespan = 99.8 % of D′), so a job finishes at its deadline D: the "
          "carbon/latency trade-off is carbon against D.", "",
          "## Mean carbon per job against the deadline (seasonal study, 4 dates × 4 start hours)", "",
          t.round(3).to_markdown(index=False), "",
          "## Carbon saved per extra hour of deadline (α 1.5 → 2.5), g CO₂ per hour", "",
          ph.round(1).to_markdown(index=False), "",
          "## By workflow: headline study (17 Apr 2024, 1 TB, start 00/12 UTC, α 1.5/2.0, 3 seeds)", "",
          hw.round(2).to_markdown(index=False), "",
          "## By workflow: seasonal study (gain and where the saving comes from)", "",
          "`saved_net_g` / `saved_comp_g`: mean grams Ours saves over B3 in network / compute carbon "
          "(negative = Ours spends more).", "",
          sw.round(2).to_markdown(index=False), ""]
    (OUT_DIR / "tradeoffs.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
