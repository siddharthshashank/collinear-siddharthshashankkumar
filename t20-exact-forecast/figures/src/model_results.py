"""Model results: every completed run as a multiple of the reference's regret, grouped by model.

Numbers from jobs/*/verifier/details.json (runs) and build.log (tiers).
    python model_results.py  ->  model_results.svg, model_results.png
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

RUNS = {
    "Claude Opus 4.7\nClaude Code":  [(1.533, 1.492, False), (1.573, 1.537, False), (1.396, 1.376, False), (1.364, 1.345, False), (1.703, 1.661, False)],
    "GPT-5.5\nCodex":                [(1.575, 1.613, False), (1.545, 1.543, False), (1.109, 1.117, False), (1.362, 1.341, True), (1.409, 1.398, False)],
    "Claude Fable 5.1\nClaude Code": [(1.027, 1.015, False), (1.104, 1.093, False), (1.008, 0.989, False)],
    "GPT-6-astra\nCodex":            [(1.054, 1.047, False), (1.072, 1.061, False)],
}
TALLY = ["0 of 5", "0 of 5", "2 of 3", "2 of 2"]
COLORS = ["#d0641c", "#1f6fb0", "#7a3e9d", "#0f8b8d"]
TIERS = [("last season only", 1.50), ("no shrinkage", 1.58), ("coin flip", 1.89)]
BAR, INK, MUTED, GRID, RED = 1.10, "#1d2933", "#5b6167", "#e7eaed", "#b23a3a"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "axes.edgecolor": "#9aa0a6", "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})
fig, ax = plt.subplots(figsize=(11, 7.2))
fig.subplots_adjust(left=0.09, right=0.8, top=0.86, bottom=0.19)

# the pass zone and the reference lines
ax.axhspan(0.85, BAR, color="#eef6ef", zorder=0)
ax.text(-0.48, 0.905, "pass zone", fontsize=10.5, color="#3b7a48", va="bottom", ha="left")
ax.axhline(1.0, color="#b0b6bc", lw=1.0, zorder=1)
ax.axhline(BAR, color=RED, lw=1.7, ls="--", zorder=1)
for name, y in TIERS:
    ax.axhline(y, color="#c9ced3", lw=1.0, ls=":", zorder=1)
    ax.text(3.6, y, f"{name}   {y:.2f}", va="center", ha="left", fontsize=10.5, color=MUTED)
ax.text(3.6, BAR, "pass bar   1.10", va="center", ha="left", fontsize=11, color=RED, fontweight="bold")
ax.text(3.6, 1.0, "reference   1.00", va="center", ha="left", fontsize=10.5, color=MUTED)

# the runs
for gi, ((label, runs), color) in enumerate(zip(RUNS.items(), COLORS)):
    runs = sorted(runs, key=lambda r: r[0]); n = len(runs)
    xs = gi + np.linspace(-0.28, 0.28, n) if n > 1 else np.array([gi])
    for x, (allw, held, cut) in zip(xs, runs):
        ax.plot([x, x], [held, allw], color=color, lw=1.4, alpha=0.6, zorder=2)
        ax.scatter([x], [held], s=48, facecolor="white", edgecolor=color, lw=1.6, zorder=3)
        ax.scatter([x], [allw], s=84, color=color, zorder=4, marker="D" if cut else "o")
        if allw == 1.109: ax.annotate("1.109", (x, allw), (x + 0.1, 1.175), fontsize=10, color=color, arrowprops=dict(arrowstyle="-", color=color, lw=0.9))
        if allw == 1.104: ax.annotate("1.104, passed the\nheld-out rule", (x, allw), (x - 0.72, 1.2), fontsize=10, color=color, arrowprops=dict(arrowstyle="-", color=color, lw=0.9))

ax.set_yscale("log"); ax.set_ylim(0.88, 2.05)
ax.set_yticks([0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0]); ax.set_yticklabels(["0.9", "1.0", "1.1", "1.2", "1.4", "1.6", "1.8", "2.0"])
ax.set_xlim(-0.55, 3.55)
ax.set_xticks(range(4)); ax.set_xticklabels([f"{k}\npassed {t}" for k, t in zip(RUNS.keys(), TALLY)], fontsize=12)
for lab, color in zip(ax.get_xticklabels(), COLORS): lab.set_color(color)
ax.tick_params(axis="x", length=0, pad=14)
ax.set_ylabel("Total regret, as a multiple of the reference's (log scale)", fontsize=12)
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
for sp in ("top", "right"): ax.spines[sp].set_visible(False)

# legend
handles = [Line2D([], [], marker="o", color=INK, ls="", ms=8, label="all eight worlds"),
           Line2D([], [], marker="o", color=INK, markerfacecolor="white", ls="", ms=7, markeredgewidth=1.6, label="the seven held-out worlds"),
           Line2D([], [], marker="D", color=INK, ls="", ms=7, label="session cut short by a usage limit"),
           Line2D([], [], color=RED, ls="--", lw=1.7, label="pass bar, committed before any run"),
           Line2D([], [], color="#c9ced3", ls=":", lw=1.2, label="careless tiers of the ladder")]
ax.legend(handles=handles, loc="upper right", fontsize=10.5, frameon=True, framealpha=1, edgecolor="#d5dadf", borderpad=0.9, labelspacing=0.6)

fig.text(0.09, 0.945, "Every completed run, by model", fontsize=17, fontweight="bold", color=INK, ha="left")
fig.text(0.09, 0.915, "The rule is 1.10 times the reference on all eight worlds, and again on the seven held out.", fontsize=10.5, color=MUTED, ha="left")
fig.text(0.09, 0.888, "Two careless tiers, team ratings (3.23) and raw head-to-head (4.00), sit above the top of the axis.", fontsize=10.5, color=MUTED, ha="left")
fig.text(0.09, 0.03, "Sources: jobs/*/verifier/details.json for the runs; build.log for the reference and the tiers. Values in RUN_REPORT.md.", fontsize=9.5, color=MUTED, ha="left")
fig.savefig("model_results.svg"); fig.savefig("model_results.png", dpi=200)
print("written model_results.svg and .png")
