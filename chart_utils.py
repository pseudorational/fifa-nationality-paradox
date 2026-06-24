"""
Shared matplotlib PNG renderer for the WC 2026 bipartite flow charts.
Called by wc2026_migration_html.py and wc2026_citizenship_html.py.

Output sized for LinkedIn / Substack: ~1920 px wide at 120 DPI.
"""


def make_png(flows_df, src_col, rep_col, src_colors, out,
             title, right_hdr, left_sub, min_players=2):
    """
    Draw a bipartite bubble-flow chart and save it as a PNG.

    Parameters
    ----------
    flows_df    : DataFrame with columns [src_col, rep_col, 'n']
    src_col     : column name for the source country (right side)
    rep_col     : column name for the representing country (left side)
    src_colors  : {country: hex_color} for the right-side bubbles / curves
    out         : output file path, e.g. "wc2026_migration.png"
    title       : retained for call-site compatibility; not rendered in chart
    right_hdr   : right column header, e.g. "BORN IN" or "CITIZENSHIP"
    left_sub    : subtitle under each left bubble, e.g. "foreign-born"
    min_players : threshold used in the footer note
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.path import Path as MPath
        from matplotlib.patches import PathPatch
    except ImportError:
        print("matplotlib not installed — skipping PNG")
        return

    BG   = "#0d1117"
    BLUE = "#3b82f6"
    GOLD = "#f59e0b"
    DIM  = "#94a3b8"

    st = flows_df.groupby(src_col)["n"].sum().sort_values(ascending=False)
    rt = flows_df.groupby(rep_col)["n"].sum().sort_values(ascending=False)
    lc = rt.index.tolist()
    rc = st.index.tolist()

    n_rows = max(len(lc), len(rc))
    fig_h  = max(11, n_rows * 0.60 + 1.5)
    fig, ax = plt.subplots(figsize=(16, fig_h))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.06, 1.01)
    ax.axis("off")

    def yp(names, top=0.95, bot=0.04):
        n = len(names)
        if n < 2:
            return {names[0]: (top + bot) / 2}
        s = (top - bot) / (n - 1)
        return {c: top - i * s for i, c in enumerate(names)}

    ly, ry = yp(lc), yp(rc)
    LX, RX = 0.30, 0.70
    MAX_N  = flows_df["n"].max()
    MIN_LW, MAX_LW = 1.5, 14.0

    for _, row in flows_df.iterrows():
        s, r, n = row[src_col], row[rep_col], row["n"]
        if s not in ry or r not in ly:
            continue
        lp = (LX, ly[r])
        rp = (RX, ry[s])
        lw  = MIN_LW + (MAX_LW - MIN_LW) * (n / MAX_N) ** 0.55
        alp = 0.20 + 0.60 * (n / MAX_N)
        verts = [rp, (0.5, rp[1]), (0.5, lp[1]), lp]
        codes = [MPath.MOVETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4]
        ax.add_patch(PathPatch(
            MPath(verts, codes),
            facecolor="none",
            edgecolor=src_colors.get(s, "#888"),
            linewidth=lw, alpha=alp, zorder=2,
        ))

    def bsz(v, mx):
        return 90 + 860 * (v / mx) ** 0.65

    for c in lc:
        y  = ly[c]
        sz = bsz(rt[c], rt.max())
        ax.scatter(LX, y, s=sz, color=BLUE, alpha=0.92,
                   linewidths=1.2, edgecolors="#93c5fd", zorder=5)
        ax.text(LX - 0.022, y + 0.008, c,
                ha="right", va="center", fontsize=24,
                color="white", fontweight="bold")
        ax.text(LX - 0.022, y - 0.016, f"{int(rt[c])} {left_sub}",
                ha="right", va="center", fontsize=8, color=DIM)

    for c in rc:
        y   = ry[c]
        sz  = bsz(st[c], st.max())
        col = src_colors.get(c, "#888")
        ax.scatter(RX, y, s=sz, color=col, alpha=0.92,
                   linewidths=1.2, edgecolors="white", zorder=5)
        ax.text(RX + 0.022, y + 0.008, c,
                ha="left", va="center", fontsize=24,
                color="white", fontweight="bold")
        ax.text(RX + 0.022, y - 0.016, f"{int(st[c])} players",
                ha="left", va="center", fontsize=8, color=DIM)

    for x_, lbl_, col_ in [(LX, "REPRESENTING", BLUE), (RX, right_hdr, GOLD)]:
        ax.text(x_, 0.980, lbl_, ha="center", fontsize=13,
                color=col_, fontweight="bold")
        ax.plot([x_ - 0.12, x_ + 0.12], [0.970, 0.970],
                color=col_, linewidth=1.5, alpha=0.5)

    ax.axvline(0.5, color="#1e293b", linewidth=1.2,
               linestyle="--", alpha=0.8, zorder=1)

    ax.text(0.5, -0.044,
            f"Source: Wikipedia + Wikidata  ·  flows ≥ {min_players} players shown",
            ha="center", fontsize=8, color="#64748b")

    plt.tight_layout(pad=0.3)
    plt.savefig(out, dpi=120, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"Saved: {out}")
