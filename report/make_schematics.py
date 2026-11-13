"""Schematic figures for the report (not data plots): deadline timeline and system architecture."""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "figures"
INK, INK2, GRID, BG = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
NET, QUEUE, COMP, WAIT = "#2a78d6", "#eda100", "#1baf7a", "#d9d8d3"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "figure.facecolor": BG,
                     "axes.facecolor": BG, "savefig.facecolor": BG})


def timeline():
    fig, ax = plt.subplots(figsize=(9, 2.6))
    bars = [(0, 2.0, WAIT, "wait\n(T$_{net}$)"), (2.0, 2.4, NET, "WAN transfer\nτ = Δ / B$_{eff}$"),
            (4.4, 1.0, QUEUE, "queue\nq$_d$"), (5.4, 6.6, COMP, "CWM schedules the DAG in D′ = D − start")]
    for x, w, c, label in bars:
        ax.add_patch(FancyBboxPatch((x, 0.35), w, 0.5, boxstyle="round,pad=0.0,rounding_size=0.06",
                                    facecolor=c, edgecolor=BG, linewidth=2))
        ax.text(x + w / 2, 0.6, label, ha="center", va="center", fontsize=8,
                color="#ffffff" if c in (NET, COMP) else INK)
    for x, lab in ((0, "0"), (2.0, "T$_{net}$"), (4.4, "T$_{arr}$"), (5.4, "start"), (12.0, "D")):
        ax.plot([x, x], [0.2, 1.0], color=INK2, lw=0.8, ls=":")
        ax.text(x, 0.08, lab, ha="center", va="top", fontsize=9, color=INK)
    ax.annotate("", xy=(12.0, 1.12), xytext=(0, 1.12),
                arrowprops=dict(arrowstyle="<->", color=INK2, lw=1))
    ax.text(6.0, 1.2, "global deadline D (shared by waiting, transfer, queue and compute)", ha="center",
            va="bottom", fontsize=8.5, color=INK2)
    ax.set_xlim(-0.3, 12.4)
    ax.set_ylim(-0.25, 1.45)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "fig_timeline.png", dpi=200)
    plt.close(fig)


def architecture():
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    boxes = {
        "ci": (0.2, 3.0, "Hourly CI 2024\nEnergy-Charts + CAISO\n(fetch_public_ci.py)"),
        "dag": (0.2, 1.6, "WfCommons DAGs\n+ cluster / hardware tiers"),
        "topo": (2.9, 2.3, "Topology builder\nper-DC CI, PUE, queues\n(data_loader.py)"),
        "cand": (5.6, 3.0, "Candidate generator\n(DC, T$_{net}$) breakpoints\n(Prop. 2 / Cor. 2a)"),
        "eval": (5.6, 1.6, "Evaluate candidate\nnetwork carbon (exact)\nshift + truncate profile"),
        "cwm": (8.3, 1.6, "solve_cwm (C++)\nCWM heuristic,\nper-interval energy"),
        "sel": (8.3, 3.0, "Select Ours, B1–B7,\nA1/A2, C1, rule R1/R3\n(both metrics, ε sweep)"),
        "out": (5.6, 0.2, "Cached results → tables & figures\n(results/, invariant tests)"),
    }
    w, h = 2.3, 1.0
    for key, (x, y, label) in boxes.items():
        face = {"cwm": COMP, "sel": NET}.get(key, "#ffffff")
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    facecolor=face, edgecolor=INK2, linewidth=1))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=7.6,
                color="#ffffff" if face != "#ffffff" else INK)

    def arrow(a, b, ra=(1, 0.5), rb=(0, 0.5)):
        (xa, ya, _), (xb, yb, _) = boxes[a], boxes[b]
        ax.add_patch(FancyArrowPatch((xa + ra[0] * w, ya + ra[1] * h), (xb + rb[0] * w, yb + rb[1] * h),
                                     arrowstyle="-|>", mutation_scale=10, color=INK2, lw=1))
    arrow("ci", "topo")
    arrow("dag", "topo")
    arrow("topo", "cand")
    arrow("cand", "eval", (0.5, 0), (0.5, 1))
    arrow("eval", "cwm")
    arrow("cwm", "sel", (0.5, 1), (0.5, 0))
    arrow("eval", "out", (0.5, 0), (0.5, 1))
    ax.set_xlim(0, 10.8)
    ax.set_ylim(0, 4.2)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "fig_architecture.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    timeline()
    architecture()
