"""Model results: every completed run as a multiple of the reference's regret, grouped by model.

Numbers from jobs/*/verifier/details.json (runs) and build.log (tiers).
    python model_results.py  ->  model_results.svg, model_results.png
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = {
    "Claude Opus 4.7\n(Claude Code)":  [(1.533, 1.492, False), (1.573, 1.537, False), (1.396, 1.376, False), (1.364, 1.345, False), (1.703, 1.661, False)],
    "GPT-5.5\n(Codex)":                [(1.575, 1.613, False), (1.545, 1.543, False), (1.109, 1.117, False), (1.362, 1.341, True), (1.409, 1.398, False)],
    "Claude Fable 5.1\n(Claude Code)": [(1.027, 1.015, False), (1.104, 1.093, False), (1.008, 0.989, False)],
    "GPT-6-astra\n(Codex)":            [(1.054, 1.047, False), (1.072, 1.061, False)],
}
TALLY = ["0 of 5 passed", "0 of 5 passed", "2 of 3 passed", "2 of 2 passed"]
COLORS = ["#d0641c", "#1f6fb0", "#7a3e9d", "#0f8b8d"]
TIERS = [("last season only", 1.50), ("no shrinkage", 1.58), ("coin flip", 1.89)]   # team ratings 3.23 and head-to-head 4.00 are above the axis
BAR, INK, MUTED, GRID = 1.10, "#1d2933", "#5b6167", "#e7eaed"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "axes.edgecolor": "#9aa0a6", "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})
fig, ax = plt.subplots(figsize=(11, 7.6))
fig.subplots_adjust(left=0.09, right=0.80, top=0.84, bottom=0.2)

# reference lines
ax.axhline(1.0, color="#b8bec4", lw=1.0, zorder=1)
ax.text(3.6, 1.0, "reference  1.00", va="center", ha="left", fontsize=11, color=MUTED)
ax.axhline(BAR, color="#b23a3a", lw=1.6, ls="--", zorder=1)
ax.text(3.6, BAR, "pass bar  1.10", va="center", ha="left", fontsize=11.5, color="#b23a3a", fontweight="bold")
for name, y in TIERS:
    ax.axhline(y, color="#c9ced3", lw=1.0, ls=":", zorder=1)
    ax.text(3.6, y, f"{name}  {y:.2f}", va="center", ha="left", fontsize=10.5, color=MUTED)

# runs
for gi, ((label, runs), color) in enumerate(zip(RUNS.items(), COLORS)):
    n = len(runs)
    runs = sorted(runs, key=lambda r: r[0])
    xs = gi + np.linspace(-0.28, 0.28, n) if n > 1 else np.array([gi])
    for k, (x, (allw, held, cut)) in enumerate(zip(xs, runs)):
        ax.plot([x, x], [held, allw], color=color, lw=1.4, alpha=0.55, zorder=2)
        ax.scatter([x], [held], s=46, facecolor="white", edgecolor=color, lw=1.6, zorder=3)
        ax.scatter([x], [allw], s=78, color=color, zorder=4, marker="D" if cut else "o")
        if allw == 1.109: ax.annotate("near miss, 1.109", (x, allw), (x + 0.12, 1.19), fontsize=10, color=color, arrowprops=dict(arrowstyle="-", color=color, lw=0.9))
        if allw == 1.104: ax.annotate("1.104: missed by 0.4 points,\npassed on the held-out seven", (x, allw), (x - 0.62, 1.245), fontsize=10, color=color, arrowprops=dict(arrowstyle="-", color=color, lw=0.9))
    ax.text(gi, 0.905, TALLY[gi], ha="center", va="top", fontsize=11.5, color=color, fontweight="bold")

ax.set_yscale("log")
ax.set_ylim(0.88, 2.05)
ax.set_yticks([0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0]); ax.set_yticklabels(["0.9", "1.0", "1.1", "1.2", "1.4", "1.6", "1.8", "2.0"])
ax.set_xlim(-0.55, 3.55)
ax.set_xticks(range(4)); ax.set_xticklabels(list(RUNS.keys()), fontsize=12)
ax.tick_params(axis="x", length=0, pad=30)
ax.set_ylabel("Total regret, as a multiple of the reference's (log scale)", fontsize=12)
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
for sp in ("top", "right"): ax.spines[sp].set_visible(False)

fig.text(0.09, 0.955, "Every completed run, by model", fontsize=17, fontweight="bold", color=INK, ha="left")
fig.text(0.09, 0.92, "Filled: all eight worlds. Hollow: the seven held-out worlds. Diamond: the session cut short by a usage limit.", fontsize=10.5, color=MUTED, ha="left")
fig.text(0.09, 0.89, "Two careless tiers, team ratings (3.23) and raw head-to-head (4.00), sit above the top of the axis.", fontsize=10.5, color=MUTED, ha="left")
fig.text(0.09, 0.055, "The rule is 1.10 on all eight worlds and again on the held-out seven. The values are in RUN_REPORT.md.", fontsize=9.5, color=MUTED, ha="left")
fig.text(0.09, 0.028, "Sources: jobs/*/verifier/details.json for the runs; build.log for the reference and the tiers.", fontsize=9.5, color=MUTED, ha="left")
fig.savefig("model_results.svg"); fig.savefig("model_results.png", dpi=200)
print("written model_results.svg and .png")
