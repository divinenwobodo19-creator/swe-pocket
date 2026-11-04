"""Figure 1 — repository size is three axes, not one.

Small multiples (breadth / coupling / depth), one row per repository, rows
ordered by mean node count. Each dot is one task; the bar tick is the repo mean.
Reads only the released derived tables (no competition data needed).

    python3 scripts/make_figure1.py   ->  paper/fig1_three_axes.png (+ .svg)
"""
import csv
import json
from pathlib import Path
from statistics import mean

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
LARGE_C, COMPACT_C = "#2a78d6", "#eb6834"  # validated pair (all-pairs, light)
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

rows = []
for r in csv.DictReader(open(ROOT / "data/joined_structure_gold.csv")):
    rows.append(dict(repo=r["repo"], stratum="large", nodes=float(r["nodes"]),
                     density=float(r["density"]), depth=float(r["max_depth"])))
for r in json.load(open(ROOT / "data/compact_joined.json")):
    rows.append(dict(repo=r["repo"], stratum="compact", nodes=float(r["nodes"]),
                     density=float(r["density"]), depth=float(r["max_depth"])))

repos = sorted({r["repo"] for r in rows},
               key=lambda p: mean(r["nodes"] for r in rows if r["repo"] == p))
ypos = {p: i for i, p in enumerate(repos)}  # smallest at bottom

panels = [("nodes", "Breadth — nodes (log)", True),
          ("density", "Coupling — edges per node", False),
          ("depth", "Depth — longest call chain (log)", True)]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                     "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK})
fig, axes = plt.subplots(1, 3, figsize=(10, 3.6), sharey=True, facecolor=SURF)

for ax, (key, title, log) in zip(axes, panels):
    ax.set_facecolor(SURF)
    for p in repos:
        pts = [r for r in rows if r["repo"] == p]
        c = LARGE_C if pts[0]["stratum"] == "large" else COMPACT_C
        y = ypos[p]
        jit = [y + ((i % 7) - 3) * 0.035 for i in range(len(pts))]
        ax.scatter([r[key] for r in pts], jit, s=14, color=c, alpha=0.45,
                   linewidths=0, zorder=2)
        m = mean(r[key] for r in pts)
        ax.plot([m, m], [y - 0.32, y + 0.32], color=c, lw=2.5,
                solid_capstyle="round", zorder=3)
        ax.annotate(f"{m:,.0f}" if key != "density" else f"{m:.2f}", (m, y + 0.34),
                    ha="center", va="bottom", fontsize=7.5, color=INK2)
    if log:
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: f"{v:,.0f}"))
    ax.set_title(title, fontsize=9.5, color=INK, loc="left")
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.tick_params(length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)

axes[0].set_yticks(range(len(repos)), repos)
axes[0].set_ylim(-0.6, len(repos) - 0.2)
handles = [plt.Line2D([], [], color=LARGE_C, lw=2.5, label="large (provided)"),
           plt.Line2D([], [], color=COMPACT_C, lw=2.5, label="compact (mined)")]
fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
           bbox_to_anchor=(0.5, -0.02), fontsize=8.5, labelcolor=INK)
fig.tight_layout(rect=(0, 0.06, 1, 1))

out = ROOT / "paper/fig1_three_axes"
fig.savefig(out.with_suffix(".png"), dpi=200, facecolor=SURF)
fig.savefig(out.with_suffix(".svg"), facecolor=SURF)
print("wrote", out.with_suffix(".png"))
