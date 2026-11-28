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


def architecture_big():
    """Full-page, self-explanatory architecture: inputs, five stages, which file does what."""
    TEAL, AMBER, SOFT = "#1F6F66", "#C8652A", "#F1F0EB"
    fig, ax = plt.subplots(figsize=(8.5, 12.3))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.15, 14.5)
    ax.axis("off")

    def box(x, y, w, h, title, body, face="#ffffff", edge=INK2, tcol=INK, bcol=INK2, tag=None, lw=1.2,
            tsize=12, bsize=9.4, tag_on_title=True):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    facecolor=face, edgecolor=edge, linewidth=lw))
        ax.text(x + 0.2, y + h - 0.22, title, ha="left", va="top", fontsize=tsize, weight="bold", color=tcol)
        ax.text(x + 0.2, y + h - 0.68, body, ha="left", va="top", fontsize=bsize, color=bcol, linespacing=1.4)
        if tag and tag_on_title:
            ax.text(x + w - 0.2, y + h - 0.26, tag, ha="right", va="top", fontsize=8.6, color=bcol, style="italic")
        elif tag:
            ax.text(x + 0.2, y + 0.14, tag, ha="left", va="bottom", fontsize=8.2, color=bcol, style="italic")

    def down(x, y0, y1, label=None):
        ax.add_patch(FancyArrowPatch((x, y0), (x, y1), arrowstyle="-|>", mutation_scale=18, color=INK2, lw=1.6))
        if label:
            ax.text(x + 0.18, (y0 + y1) / 2, label, fontsize=9.2, color=INK2, va="center", style="italic")

    ax.text(5, 14.35, "How the system works, end to end", ha="center", va="top", fontsize=17, weight="bold",
            color=INK)
    ax.text(5, 13.85, "Read from top to bottom.  Teal border = this project's code;  green = the CWM solver "
            "(reused);  orange = results.", ha="center", va="top", fontsize=8.8, color=INK2)

    ax.text(0.2, 13.4, "INPUTS", fontsize=10, weight="bold", color=TEAL, va="top")
    ins = [("Grid carbon", "Hourly CI for 2024\nGermany, Norway,\nFrance, Poland,\nCalifornia"),
           ("Workflow", "Task graph, e.g.\neager1000\n0.1–10 TB of input\nin Frankfurt"),
           ("Settings", "Deadline D =\nα × makespan\n1 Gbit/s link\nε kWh per GB"),
           ("Optional studies", "Hardware + PUE\nper data centre\nOffice-hour queues\nOther data origins")]
    for k, (t, b) in enumerate(ins):
        box(0.2 + k * 2.45, 10.95, 2.3, 2.05, t, b, tsize=10.5, bsize=8.6)
    ax.plot([1.35, 8.7], [10.7, 10.7], color=INK2, lw=1.4)
    for k in range(4):
        ax.plot([1.35 + k * 2.45] * 2, [10.95, 10.7], color=INK2, lw=1.4)
    down(5, 10.7, 10.35)

    box(0.2, 8.65, 9.6, 1.7, "1   Build the world",
        "Put the five data centres on one shared clock. For each one, record its hourly\n"
        "carbon intensity and a green-power budget derived from it (a cleaner hour gives a\n"
        "bigger budget); in some studies also its hardware and its queue.",
        edge=TEAL, lw=2, tag="data_loader.py")
    down(5, 8.65, 8.3)
    box(0.2, 6.6, 9.6, 1.7, "2   List the candidates",
        "Every data centre × every transfer start time. Only starts on hour boundaries\n"
        "can be best (Property 2), so the list stays small. Drop any candidate that leaves\n"
        "less time than the workflow needs even at full speed.",
        edge=TEAL, lw=2, tag="optimizer.py")
    down(5, 6.6, 6.25, "for each candidate")

    ax.add_patch(FancyBboxPatch((0.2, 2.05), 9.6, 4.2, boxstyle="round,pad=0.02,rounding_size=0.12",
                                facecolor=SOFT, edgecolor=TEAL, linewidth=2))
    ax.text(0.4, 6.03, "3   Score the candidate exactly", fontsize=12, weight="bold", color=INK, va="top")
    ax.text(9.6, 6.03, "Total carbon = ② + ④", fontsize=11, weight="bold", color=TEAL, ha="right", va="top")
    w, h = 4.45, 1.6
    subs = [(0.42, 4.1, "① When does the data arrive?", "start + size ÷ bandwidth\n(+ queue wait, if any)",
             "#ffffff", INK, INK2, "wan_model.py"),
            (5.13, 4.1, "② Network carbon", "ε × size × average carbon\nintensity of both ends", "#ffffff",
             INK, INK2, "wan_model.py"),
            (0.42, 2.42, "③ Cut the green budget", "keep only the hours from\narrival to the deadline (D′)",
             "#ffffff", INK, INK2, "profile_shifting.py"),
            (5.13, 2.42, "④ Run CWM inside that DC", "schedule + energy per hour\n→ compute carbon (× PUE)",
             COMP, "#ffffff", "#ffffff", "solve_cwm (C++) via cwm_runner.py")]
    for x, y, t, b, face, tc, bc, tag in subs:
        box(x, y, w, h, t, b, face=face, tcol=tc, bcol=bc, tag=tag, tsize=10.5, bsize=9, tag_on_title=False)
    ax.add_patch(FancyArrowPatch((4.87, 4.95), (5.13, 4.95), arrowstyle="-|>", mutation_scale=12, color=INK2))
    ax.add_patch(FancyArrowPatch((2.65, 4.1), (2.65, 4.02), arrowstyle="-|>", mutation_scale=14, color=INK2))
    ax.add_patch(FancyArrowPatch((4.87, 3.22), (5.13, 3.22), arrowstyle="-|>", mutation_scale=12, color=INK2))
    ax.text(5, 2.1, "Every CWM run is cached (inputs + solver fingerprint), so long runs can stop and resume.",
            fontsize=8.4, color=INK2, ha="center", va="bottom", style="italic")
    down(5, 2.05, 1.75, "all candidates scored")

    box(0.2, 0.0, 4.6, 1.75, "4   Choose",
        "Ours = the lowest total.\nEvery baseline (Stay-local,\nGreenest-DC, No-wait …) is another\n"
        "rule applied to the same scores.", edge=NET, lw=2, tsize=11.5, bsize=9, tag="optimizer.py")
    box(5.2, 0.0, 4.6, 1.75, "5   Results",
        "Tables and figures for the report.\n129 tests, e.g. Ours is never\nworse than any rule it could pick.",
        face=AMBER, edge=AMBER, tcol="#ffffff", bcol="#ffffff", tsize=11.5, bsize=9, tag="plots.py")
    ax.add_patch(FancyArrowPatch((4.8, 0.88), (5.2, 0.88), arrowstyle="-|>", mutation_scale=16, color=INK2, lw=1.4))
    fig.savefig(OUT / "fig_architecture_big.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    timeline()
    architecture()
    architecture_big()
