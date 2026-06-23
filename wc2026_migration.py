"""
FIFA World Cup 2026 — Player Migration Visual Story
Bipartite bubble chart: BORN IN (right) --arrow--> REPRESENTING (left)
Arrow thickness = number of players making that cross-border journey.

Run: python wc2026_migration.py
Output: wc2026_migration.png
"""
import sys, os
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.path import Path
from matplotlib.patches import PathPatch, FancyArrowPatch
import matplotlib.patheffects as pe

OUTPUT_PNG = "wc2026_migration.png"
MIN_PLAYERS = 2     # hide flows with fewer than this many players
BG          = "#0d1117"
BLUE        = "#3b82f6"
GOLD        = "#f59e0b"
MUTED       = "#64748b"
TEXT_DIM    = "#94a3b8"

# ── Birth-country color palette (qualitative) ─────────────────────────────────
PALETTE = [
    "#60a5fa",  # France         — soft blue
    "#f472b6",  # United Kingdom — pink
    "#34d399",  # Netherlands    — green
    "#fb923c",  # Germany        — orange
    "#a78bfa",  # Spain          — purple
    "#facc15",  # Belgium        — yellow
    "#4ade80",  # Sweden         — lime
    "#f87171",  # United States  — red
    "#2dd4bf",  # Portugal       — cyan
    "#c084fc",  # DRC            — lavender
    "#e879f9",  # Argentina      — magenta
    "#fde68a",  # Bosnia & Herz  — pale yellow
    "#86efac",  # Australia      — pale green
    "#93c5fd",  # Canada         — pale blue
    "#d8b4fe",  # Denmark        — pale purple
    "#fca5a5",  # Croatia        — pale red
    "#6ee7b7",  # Brazil         — mint
    "#a5f3fc",  # Switzerland    — ice blue
    "#fcd34d",  # Ghana          — amber
    "#f9a8d4",  # Austria        — blush
]

# ─────────────────────────────────────────────────────────────────────────────
# 1. Load & filter
# ─────────────────────────────────────────────────────────────────────────────
df = pd.read_csv("wc2026_players.csv")
complete = df[df["data_complete"] == True].copy()
complete = complete[
    complete["birth_country"].notna() &
    (complete["birth_country"].str.strip() != "")
]

cross = complete[complete["birth_country"] != complete["representing"]].copy()

print(f"Players with complete data : {len(complete)}")
print(f"Born outside represented nation : {len(cross)}  "
      f"({100*len(cross)/len(complete):.0f}%)")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Compute flows
# ─────────────────────────────────────────────────────────────────────────────
all_flows = (
    cross
    .groupby(["birth_country", "representing"])
    .size()
    .reset_index(name="n")
    .sort_values("n", ascending=False)
)

flows = all_flows[all_flows["n"] >= MIN_PLAYERS].copy()

birth_totals = flows.groupby("birth_country")["n"].sum().sort_values(ascending=False)
team_totals  = flows.groupby("representing")["n"].sum().sort_values(ascending=False)

print(f"\nFlows shown (≥{MIN_PLAYERS} players): {len(flows)}  "
      f"covering {flows['n'].sum()} players")
print(f"\nTop birth countries:  "
      + ", ".join(f"{c} ({n})" for c, n in birth_totals.head(6).items()))
print(f"Top receiving teams:  "
      + ", ".join(f"{c} ({n})" for c, n in team_totals.head(6).items()))

# ─────────────────────────────────────────────────────────────────────────────
# 3. Layout — y positions for each column
# ─────────────────────────────────────────────────────────────────────────────
left_countries  = team_totals.index.tolist()   # receiving, largest at top
right_countries = birth_totals.index.tolist()  # exporting, largest at top

def make_ypos(names, top=0.93, bottom=0.05):
    n = len(names)
    if n == 1:
        return {names[0]: (top + bottom) / 2}
    step = (top - bottom) / (n - 1)
    return {name: top - i * step for i, name in enumerate(names)}

left_y  = make_ypos(left_countries)
right_y = make_ypos(right_countries)

LEFT_X  = 0.30
RIGHT_X = 0.70

birth_color = {c: PALETTE[i % len(PALETTE)]
               for i, c in enumerate(right_countries)}

# ─────────────────────────────────────────────────────────────────────────────
# 4. Figure setup
# ─────────────────────────────────────────────────────────────────────────────
n_rows   = max(len(left_countries), len(right_countries))
fig_h    = max(16, n_rows * 0.58 + 3)
fig, ax  = plt.subplots(figsize=(22, fig_h))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 1)
ax.set_ylim(-0.07, 1.10)
ax.axis("off")

# ─────────────────────────────────────────────────────────────────────────────
# 5. Draw flows (cubic bezier curves)
# ─────────────────────────────────────────────────────────────────────────────
max_n  = flows["n"].max()
MIN_LW = 1.5
MAX_LW = 16.0

for _, row in flows.iterrows():
    b     = row["birth_country"]
    r     = row["representing"]
    n     = row["n"]
    lp    = (LEFT_X,  left_y[r])
    rp    = (RIGHT_X, right_y[b])
    lw    = MIN_LW + (MAX_LW - MIN_LW) * (n / max_n) ** 0.55
    alpha = 0.22 + 0.58 * (n / max_n)
    color = birth_color[b]

    # Cubic Bezier: control points bow toward the center x
    cx    = 0.5
    verts = [rp, (cx, rp[1]), (cx, lp[1]), lp]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4]
    ax.add_patch(PathPatch(
        Path(verts, codes),
        facecolor="none", edgecolor=color,
        linewidth=lw, alpha=alpha, zorder=2,
    ))

# ─────────────────────────────────────────────────────────────────────────────
# 6. Draw bubbles & labels
# ─────────────────────────────────────────────────────────────────────────────
MAX_BUBBLE = 1100

def bubble_size(val, max_val, base=130):
    return base + MAX_BUBBLE * (val / max_val) ** 0.65

# Left — receiving countries (blue)
for country in left_countries:
    y  = left_y[country]
    sz = bubble_size(team_totals[country], team_totals.max())
    ax.scatter(LEFT_X, y, s=sz, color=BLUE, alpha=0.95,
               linewidths=1.5, edgecolors="#93c5fd", zorder=5)
    n_val = int(team_totals[country])
    ax.text(LEFT_X - 0.022, y + 0.007, country,
            ha="right", va="center",
            fontsize=8.5, color="white", fontweight="bold")
    ax.text(LEFT_X - 0.022, y - 0.012, f"{n_val} foreign-born",
            ha="right", va="center",
            fontsize=6.5, color=TEXT_DIM)

# Right — birth countries (colored)
for country in right_countries:
    y   = right_y[country]
    sz  = bubble_size(birth_totals[country], birth_totals.max())
    col = birth_color[country]
    ax.scatter(RIGHT_X, y, s=sz, color=col, alpha=0.95,
               linewidths=1.5, edgecolors="white", zorder=5)
    n_val = int(birth_totals[country])
    ax.text(RIGHT_X + 0.022, y + 0.007, country,
            ha="left", va="center",
            fontsize=8.5, color="white", fontweight="bold")
    ax.text(RIGHT_X + 0.022, y - 0.012, f"{n_val} players",
            ha="left", va="center",
            fontsize=6.5, color=TEXT_DIM)

# ─────────────────────────────────────────────────────────────────────────────
# 7. Column headers
# ─────────────────────────────────────────────────────────────────────────────
for x, label, color in [
    (LEFT_X,  "REPRESENTING",  BLUE),
    (RIGHT_X, "BORN IN",       GOLD),
]:
    ax.text(x, 0.99, label,
            ha="center", va="center", fontsize=13,
            color=color, fontweight="bold")
    ax.plot([x - 0.12, x + 0.12], [0.978, 0.978],
            color=color, linewidth=1.5, alpha=0.5, zorder=3)

# Divider
ax.axvline(0.5, color="#1e293b", linewidth=1.2,
           linestyle="--", alpha=0.8, zorder=1)

# ─────────────────────────────────────────────────────────────────────────────
# 8. Arrow-thickness legend  (bottom-center)
# ─────────────────────────────────────────────────────────────────────────────
legend_y = -0.04
legend_xs = [0.38, 0.44, 0.50]
for x_leg, n_leg in zip(legend_xs, [1, 5, 19]):
    lw_leg = MIN_LW + (MAX_LW - MIN_LW) * (n_leg / max_n) ** 0.55
    ax.plot([x_leg - 0.03, x_leg + 0.03], [legend_y, legend_y],
            color="white", linewidth=lw_leg, alpha=0.55,
            solid_capstyle="round")
    ax.text(x_leg, legend_y - 0.017,
            f"{n_leg} player{'s' if n_leg > 1 else ''}",
            ha="center", va="top", fontsize=6.5, color=TEXT_DIM)
ax.text(0.44, legend_y + 0.018, "Arrow thickness",
        ha="center", va="bottom", fontsize=7, color=TEXT_DIM)

# ─────────────────────────────────────────────────────────────────────────────
# 9. Headline stats (top-center)
# ─────────────────────────────────────────────────────────────────────────────
ax.text(0.5, 1.065,
        "FIFA World Cup 2026 — Crossing Borders",
        ha="center", va="center", fontsize=17, color="white",
        fontweight="bold")
ax.text(0.5, 1.040,
        "Players who were born in a different country from the one they represent",
        ha="center", va="center", fontsize=10, color=TEXT_DIM)

stat_items = [
    (f"{len(cross)}", "cross-border players"),
    (f"{len(left_countries)}", "receiving nations"),
    (f"{len(right_countries)}", "source nations"),
]
for i, (val, label) in enumerate(stat_items):
    cx = 0.35 + i * 0.15
    ax.text(cx, 1.012, val, ha="center", va="center",
            fontsize=14, color=GOLD, fontweight="bold")
    ax.text(cx, 0.997, label, ha="center", va="center",
            fontsize=7, color=TEXT_DIM)

# ─────────────────────────────────────────────────────────────────────────────
# 10. Callout annotations for top-3 flows
# ─────────────────────────────────────────────────────────────────────────────
top3 = all_flows.head(3)
for _, row in top3.iterrows():
    b = row["birth_country"]
    r = row["representing"]
    n = row["n"]
    if b not in right_y or r not in left_y:
        continue
    mid_y = (right_y[b] + left_y[r]) / 2
    ax.text(0.5, mid_y,
            f"{n}",
            ha="center", va="center",
            fontsize=8, color="white", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#1e293b",
                      edgecolor=birth_color.get(b, "white"), linewidth=1,
                      alpha=0.85),
            zorder=10)

# Footer
ax.text(0.5, -0.065,
        f"Source: Wikipedia 2026 FIFA World Cup squads + Wikidata  •  "
        f"Only flows of ≥{MIN_PLAYERS} players shown  •  "
        f"Data complete for {len(complete)} of {len(df)} squad members",
        ha="center", va="center", fontsize=6.5, color=MUTED)

# ─────────────────────────────────────────────────────────────────────────────
# 11. Save
# ─────────────────────────────────────────────────────────────────────────────
plt.tight_layout(pad=0.3)
plt.savefig(OUTPUT_PNG, dpi=160, bbox_inches="tight", facecolor=BG)
print(f"\nSaved: {OUTPUT_PNG}")
plt.show()
