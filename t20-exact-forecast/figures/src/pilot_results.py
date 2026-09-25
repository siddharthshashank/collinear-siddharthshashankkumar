"""Plate 7: the ten pilot runs against the tiers and the bar, world by world, and the one-constant ablations.

Every number is from the job records (details.json), build.log (the tiers) and ablations.log.
    python pilot_results.py   ->  pilot_results.svg, pilot_results.png
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm

WORLDS = ["visible", "heldout_a", "heldout_b", "heldout_c", "heldout_d", "heldout_e", "heldout_f", "heldout_g"]
LABELS = ["visible", "held-out a", "held-out b", "held-out c", "held-out d", "held-out e", "held-out f", "held-out g"]
# per-world regret as a multiple of the reference's, from each run's details.json; order: visible, a..g
RUNS = [
    ("Run 1: Opus 4.7", "opus", [1.864, 1.348, 1.161, 2.701, 1.723, 1.584, 1.179, 1.244], 1.533, 1.492, False),
    ("Run 2: GPT-5.5", "gpt", [1.279, 1.531, 1.735, 2.553, 2.122, 1.263, 1.211, 1.501], 1.575, 1.613, False),
    ("Run 3: Opus 4.7", "opus", [1.862, 1.364, 1.298, 2.166, 2.148, 1.785, 1.135, 1.452], 1.573, 1.537, False),
    ("Run 4: GPT-5.5", "gpt", [1.561, 1.346, 1.869, 2.290, 2.427, 1.246, 1.031, 1.485], 1.545, 1.543, False),
    ("Run 5: Opus 4.7", "opus", [1.550, 1.176, 1.071, 2.098, 1.785, 1.633, 1.153, 1.186], 1.396, 1.376, False),
    ("Run 6: GPT-5.5", "gpt", [1.045, 1.045, 1.034, 1.417, 1.470, 0.975, 1.225, 0.827], 1.109, 1.117, False),
    ("Run 7: Opus 4.7", "opus", [1.518, 1.215, 1.003, 1.962, 1.706, 1.594, 1.120, 1.183], 1.364, 1.345, False),
    ("Run 8: GPT-5.5", "gpt", [1.523, 1.102, 1.092, 2.057, 1.969, 1.460, 1.233, 1.010], 1.362, 1.341, True),
    ("Run 9: Opus 4.7", "opus", [2.038, 1.214, 1.367, 2.803, 2.391, 1.869, 1.465, 1.366], 1.703, 1.661, False),
    ("Run 10: GPT-5.5", "gpt", [1.496, 1.308, 1.101, 2.121, 1.728, 1.437, 1.277, 1.132], 1.409, 1.398, False),
    ("F1: Fable 5.1", "fable", [1.121, 0.959, 0.960, 1.041, 1.133, 0.900, 1.044, 1.140], 1.027, 1.015, False),
    ("F2: Fable 5.1", "fable", [1.191, 1.054, 1.017, 1.050, 1.230, 1.101, 1.105, 1.147], 1.104, 1.093, False),
    ("F3: Fable 5.1", "fable", [1.157, 0.941, 0.905, 0.985, 1.053, 0.959, 1.008, 1.117], 1.008, 0.989, False),
    ("A1: GPT-6-astra", "astra", [1.109, 1.056, 0.861, 1.174, 0.943, 1.055, 1.076, 1.103], 1.054, 1.047, False),
    ("A2: GPT-6-astra", "astra", [1.165, 1.034, 0.901, 1.134, 1.127, 1.053, 1.089, 1.104], 1.072, 1.061, False),
]
# per-world regret of the reference and the tiers, from build.log; order: visible, a..g
REF = [0.0087, 0.0167, 0.0075, 0.0074, 0.0061, 0.0095, 0.0132, 0.0090]
TIERS = {
    "Tier: raw head-to-head": [0.0478, 0.0544, 0.0305, 0.0424, 0.0401, 0.0304, 0.0389, 0.0283],
    "Tier: team ratings": [0.0393, 0.0156, 0.0515, 0.0175, 0.0362, 0.0192, 0.0275, 0.0452],
    "Starter / coin flip": [0.0208, 0.0138, 0.0228, 0.0093, 0.0117, 0.0185, 0.0235, 0.0270],
    "Tier: no shrinkage": [0.0120, 0.0196, 0.0110, 0.0178, 0.0123, 0.0201, 0.0185, 0.0124],
    "Tier: last season only": [0.0096, 0.0199, 0.0157, 0.0127, 0.0134, 0.0081, 0.0186, 0.0193],
}
# ablations on held-out c: (label, colour key, as submitted, after, the change)
ABL = [
    ("Trial 1, Opus 4.7", "opus", 2.70, 1.36, "the single ridge of 1.0 raised to 25"),
    ("Trial 2, GPT-5.5", "gpt", 2.55, 1.57, "every prior sd x 0.33"),
    ("Trial 3, Opus 4.7", "opus", 2.17, 1.64, "every ridge x 12"),
    ("Trial 4, GPT-5.5", "gpt", 2.29, 1.60, "every ridge x 12"),
    ("Trial 5, Opus 4.7", "opus", 2.10, 1.27, "quality ridges 4 to 44 and 31, the true values"),
    ("Trial 6, GPT-5.5\nhedge removed", "gpt", 1.42, 1.67, "output logit scale 0.90 to 1.0"),
    ("Trial 6, GPT-5.5\nhedge deepened", "gpt", 1.42, 1.13, "output logit scale 0.90 to 0.75"),
    ("Trial 6, GPT-5.5\npriors halved, hedge kept", "gpt", 1.42, 0.91, "every prior sd x 0.5"),
]
COL = {"opus": "#d0641c", "gpt": "#1f6fb0", "fable": "#7a3e9d", "astra": "#0f8b8d", "tier": "#7a7f85", "oracle": "#178a5a", "bar": "#b23a3a"}
INK = "#1d2933"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": "#8a9096", "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})

def draw_a(fig, ax):
    rows = []
    for name, kind, per, tot, held, cut in RUNS:
        rows.append((name, kind, tot, held, cut))
    for name, per in TIERS.items():
        rows.append((name, "tier", sum(per) / sum(REF), sum(per[1:]) / sum(REF[1:]), False))
    rows.append(("Oracle (reference)", "oracle", 1.0, 1.0, False))
    rows.sort(key=lambda r: -r[2])
    y = np.arange(len(rows))
    for yi, (name, kind, tot, held, cut) in zip(y, rows):
        c = COL[kind]
        ax.plot([held, tot], [yi, yi], color=c, lw=1.2, alpha=0.6, zorder=2)
        ax.scatter([tot], [yi], s=54, color=c, zorder=3, marker="D" if cut else "o")
        ax.scatter([held], [yi], s=54, facecolor="white", edgecolor=c, lw=1.6, zorder=3, marker="D" if cut else "o")
        if kind != "tier":
            ax.text(max(tot, held) * 1.05, yi, f"{tot:.3f} / {held:.3f}", va="center", fontsize=9, color=INK)
    ax.axvline(1.10, color=COL["bar"], lw=1.4, ls="--", zorder=1)
    ax.axvline(1.0, color="#b8bec4", lw=0.8, zorder=1)
    ax.text(1.115, -0.55, "pass bar x1.10", color=COL["bar"], fontsize=9.5, ha="left", va="bottom")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=9.5)
    for lab, (name, kind, *_ ) in zip(ax.get_yticklabels(), rows):
        lab.set_color(COL[kind] if kind != "tier" else "#5b6167")
    ax.set_xscale("log")
    ax.set_xticks([1.0, 1.5, 2, 3, 4]); ax.set_xticklabels(["1.0", "1.5", "2", "3", "4"])
    ax.set_xlim(0.95, 5.2); ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_xlabel("Summed regret as a multiple of the reference's summed regret (log scale)")
    ax.set_title("(a) Every completed run and the tiers, pooled over the graded worlds", fontsize=12, color=INK, loc="left", pad=10)
    ax.scatter([], [], color=INK, s=54, label="all 8 worlds"); ax.scatter([], [], facecolor="white", edgecolor=INK, lw=1.6, s=54, label="7 held-out worlds")
    ax.scatter([], [], color=COL["gpt"], s=54, marker="D", label="run 8: session cut short by a usage limit")
    ax.scatter([], [], color=COL["fable"], s=54, label="Claude Fable 5.1"); ax.scatter([], [], color=COL["astra"], s=54, label="GPT-6-astra")
    ax.legend(loc="upper right", fontsize=9, frameon=False)
    ax.grid(axis="x", color="#e6e9ec", lw=0.8); ax.set_axisbelow(True)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)

def draw_b(fig, ax):
    mat = np.array([per for _, _, per, *_ in RUNS] + [[c / r for c, r in zip(TIERS["Starter / coin flip"], REF)]])
    names = [n for n, *_ in RUNS] + ["Starter (0.5)"]
    cmap = LinearSegmentedColormap.from_list("rb", ["#2f6fb2", "#f6f3ee", "#c62828"])
    im = ax.imshow(mat, cmap=cmap, norm=LogNorm(vmin=0.8, vmax=3.0), aspect="auto")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8.6, color="white" if (v > 2.1 or v < 0.9) else INK, fontweight="bold" if v <= 1.10 else "normal")
    ax.set_xticks(range(len(LABELS))); ax.set_xticklabels(LABELS, rotation=35, ha="right", fontsize=9.5)
    ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontsize=9.5)
    for lab, (n, kind, *_ ) in zip(ax.get_yticklabels(), RUNS + [("", "tier")]):
        lab.set_color(COL[kind] if kind != "tier" else "#5b6167")
    ax.set_title("(b) Regret on each world as a multiple of the reference's", fontsize=12, color=INK, loc="left", pad=10)
    cb = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.045, pad=0.2, ticks=[0.8, 1.0, 1.25, 1.5, 2, 3]); cb.ax.set_xticklabels(["0.8", "1.0", "1.25", "1.5", "2", "3"]); cb.outline.set_visible(False); cb.set_label("regret as a multiple of the reference's", fontsize=9.5)
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.tick_params(length=0)

def draw_c(fig, ax):
    y = np.arange(len(ABL))[::-1]
    for yi, (name, kind, before, after, change) in zip(y, ABL):
        c = COL[kind]
        ax.annotate("", xy=(after, yi), xytext=(before, yi), arrowprops=dict(arrowstyle="-|>", color=c, lw=1.8, shrinkA=6, shrinkB=2), zorder=3)
        ax.scatter([before], [yi], s=60, facecolor="white", edgecolor=c, lw=1.6, zorder=4)
        ax.scatter([after], [yi], s=60, color=c, zorder=4)
        ax.text(0.82, yi - 0.36, change, fontsize=8.4, color="#5b6167", va="center", ha="left")
    ax.axvline(1.10, color=COL["bar"], lw=1.4, ls="--", zorder=1)
    ax.axvline(1.0, color="#b8bec4", lw=0.8, zorder=1)
    ax.axvline(1.26, color="#9aa0a6", lw=0.9, ls=":", zorder=1)
    ax.text(1.27, -0.95, "coin flip on this world", fontsize=8.5, color="#5b6167", ha="left", va="center")
    ax.text(1.08, -0.95, "bar", fontsize=8.5, color=COL["bar"], ha="right", va="center")
    ax.set_yticks(y); ax.set_yticklabels([a[0] for a in ABL], fontsize=9.5)
    for lab, (n, kind, *_ ) in zip(ax.get_yticklabels(), ABL): lab.set_color(COL[kind])
    ax.set_xlim(0.78, 2.98); ax.set_ylim(-1.4, len(ABL) - 0.2)
    ax.set_xlabel("Regret on held-out c as a multiple of the reference's")
    ax.scatter([], [], facecolor="white", edgecolor=INK, lw=1.6, s=60, label="as submitted"); ax.scatter([], [], color=INK, s=60, label="after the one change")
    ax.legend(loc="upper right", fontsize=9, frameon=False)
    ax.set_title("(c) One constant changed per program", fontsize=12, color=INK, loc="left", pad=10)
    ax.grid(axis="x", color="#e6e9ec", lw=0.8); ax.set_axisbelow(True)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)


# the combined plate
fig = plt.figure(figsize=(21, 10.2))
gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.2, 0.95], wspace=0.55, left=0.1, right=0.985, top=0.92, bottom=0.17)
draw_a(fig, fig.add_subplot(gs[0])); draw_b(fig, fig.add_subplot(gs[1])); draw_c(fig, fig.add_subplot(gs[2]))
fig.text(0.1, 0.05, "Sources: jobs/*/verifier/details.json for the runs, build.log for the tiers and the reference, ablations.log for panel (c). "
         "Pooled ratios are sums of world-mean regrets; every world has 24 fixtures. The bar is 1.10 on all eight worlds and again on the seven held out.",
         fontsize=9, color="#5b6167")
fig.savefig("pilot_results.svg"); fig.savefig("pilot_results.png", dpi=134)
print("written pilot_results.svg and .png")

# each panel on its own, for the paper
for tag, draw, size, margins in [("a", draw_a, (8.2, 8.6), dict(left=0.24, right=0.97, top=0.93, bottom=0.09)),
                                  ("b", draw_b, (8.2, 9.0), dict(left=0.17, right=0.98, top=0.93, bottom=0.17)),
                                  ("c", draw_c, (8.2, 6.8), dict(left=0.27, right=0.97, top=0.92, bottom=0.12))]:
    f = plt.figure(figsize=size); f.subplots_adjust(**margins)
    draw(f, f.add_subplot(111))
    f.savefig(f"pilot_{tag}.pdf"); print("panel", tag, "saved")
