"""Single-network panels, drawn for ONE arm or ONE unit.

Seven kinds: the ring and the chord, which draw the network itself; the sender-by-receiver
matrix and the role scatter, which are the same numbers without a cut; and - where the
declaration names a grouping column - the flow ranking, the group-by-population role heatmap and
the decomposition of one group into its members.

The first two go wrong the same way every time: both must draw a SUBSET of edges to be readable
at all, and a subset is a removal. `panels.R3` is therefore not advice here, it is the contract -
state the fraction of strength kept, and NAME what is left with no link. The matrix and the
scatter exist partly to answer that: they show every pair and every population, uncut.

EVERYTHING HERE IS AN AGGREGATION OF THE DECLARED EDGE LIST, AND THAT IS THE BOUNDARY. Summing,
ranking and cross-tabulating rearrange what a plugin computed; they do not compute anything. The
kinds that would - a latent decomposition of the group-by-population matrix, a similarity
embedding over groups - are NOT here and must not be, because the reporter may not produce a
number that first exists at render time. They belong to the plugin, which has the method's own
machinery, and `panels.OWNER` records that rather than listing them as things the host has not
got round to.

Nothing in this module knows what produced the numbers. It takes an edge list with source,
target and weight, and a population order, which is all a network is.
"""

from __future__ import annotations

import math

from . import figure as F


def aggregate(edges, pops):
    """(count, weight) K x K over a FIXED population order. The one place this is computed."""
    import numpy as np

    ix = {p: i for i, p in enumerate(pops)}
    c = np.zeros((len(pops), len(pops)))
    w = np.zeros((len(pops), len(pops)))
    if edges is None or not len(edges):
        return c, w
    for s, t, p in zip(edges["source"].astype(str), edges["target"].astype(str),
                       edges["prob"]):
        if s in ix and t in ix:
            c[ix[s], ix[t]] += 1.0
            w[ix[s], ix[t]] += float(p)
    return c, w


def strength_cut(w, keep=0.90, protect_top=True):
    """(mask, kept_fraction, weakest_drawn) - the strongest edges making `keep` of total weight.

    CUT BY CUMULATIVE STRENGTH, NOT BY COUNT. A count cut ("top 50 edges") removes a different
    amount of the network on every unit, so two panels drawn the same way are not comparable.

    `protect_top` keeps each population's strongest link IN and OUT whatever its rank, so a
    population never disappears merely for being weak - which is the difference between a panel
    that is thinned and a panel that has quietly lost a third of its rows.
    """
    import numpy as np

    flat = [(w[i, j], i, j) for i in range(w.shape[0]) for j in range(w.shape[1]) if w[i, j] > 0]
    if not flat:
        return np.zeros_like(w, dtype=bool), 0.0, 0.0
    flat.sort(reverse=True)
    total = sum(v for v, _i, _j in flat)
    mask = np.zeros_like(w, dtype=bool)
    run = 0.0
    weakest = flat[0][0]
    for v, i, j in flat:
        if run / total >= keep:
            break
        mask[i, j] = True
        weakest = v
        run += v
    if protect_top:
        for i in range(w.shape[0]):
            if w[i].max() > 0:
                mask[i, int(np.argmax(w[i]))] = True
            if w[:, i].max() > 0:
                mask[int(np.argmax(w[:, i])), i] = True
    kept = float(w[mask].sum() / total) if total > 0 else 0.0
    return mask, kept, float(weakest)


def unconnected(mask, pops):
    """Populations with no drawn link in either direction - the names R3 requires."""
    import numpy as np

    out = []
    for i, p in enumerate(pops):
        if not (mask[i].any() or mask[:, i].any()):
            out.append(p)
    return out


def _side(x, tol=0.28):
    """Horizontal anchor for a label at ring position x: outward, never back over its mark."""
    if x > tol:
        return "left"
    if x < -tol:
        return "right"
    return "center"


def _ring(n, r=1.0, start=90.0):
    """Positions on a circle, clockwise from the top - a stable order across panels."""
    return [(r * math.cos(math.radians(start - 360.0 * k / n)),
             r * math.sin(math.radians(start - 360.0 * k / n))) for k in range(n)]


def circle(ctx, edges, pops, *, fid="N1_circle", keep=0.90, title=None, note=""):
    """The aggregate network as a ring. Returns True if drawn.

    Node AREA - never radius - encodes the count, with a legend carrying real values: a radius
    encoding overstates a large value by squaring it, and this is a panel whose marker size
    carries a number.
    """
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, Circle as MCircle

    c, w = aggregate(edges, pops)
    if w.sum() <= 0:
        return False
    mask, kept, weakest = strength_cut(w, keep=keep)
    silent = unconnected(mask, pops)
    deg = c.sum(1) + c.sum(0)
    pos = _ring(len(pops))
    cmap = F.palette(list(pops))
    short = F.short_labels(list(pops))

    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 1.10), layout="constrained")
    ax.set_aspect("equal")
    ax.axis("off")
    wmax = float(w[mask].max()) or 1.0

    for i in range(len(pops)):
        for j in range(len(pops)):
            if not mask[i, j]:
                continue
            lw = 0.25 + 2.6 * (w[i, j] / wmax)
            col = cmap[pops[i]]
            if i == j:
                # SELF-LOOP = AUTOCRINE, and it is inferred exactly as an off-diagonal edge is.
                x, y = pos[i]
                ax.add_patch(MCircle((x * 1.13, y * 1.13), 0.085, fill=False, ec=col,
                                     lw=lw, alpha=.85, zorder=2))
                continue
            ax.add_patch(FancyArrowPatch(pos[i], pos[j], connectionstyle="arc3,rad=0.18",
                                         arrowstyle="-|>", mutation_scale=6.5,
                                         lw=lw, color=col, alpha=.75, zorder=2,
                                         shrinkA=7, shrinkB=8))
    dmax = float(deg.max()) or 1.0
    _nlabels = []
    for k, p in enumerate(pops):
        # A RADIUS FLOOR, DISCLOSED. Without it the smallest population is a dot nobody can
        # click on; with it the smallest are drawn slightly larger than proportional, and the
        # caption says so rather than letting the reader infer area is exact everywhere.
        rr = 0.055 + 0.105 * math.sqrt(deg[k] / dmax)
        x, y = pos[k]
        ax.add_patch(MCircle((x, y), rr, color=cmap[p], zorder=3))
        ax.text(x, y, str(k + 1), ha="center", va="center", fontsize=4.6,
                color="white", zorder=4, weight="bold")
        # ANCHORED BY SIDE. A centred label on a node at the left or right of the ring runs
        # back over its own disc: "Lymphatic endothelial" sat on top of the node it named.
        _nlabels.append(ax.annotate(f"{k + 1} {short[p]}", (x * 1.22, y * 1.22),
                                    xytext=(0, 0), textcoords="offset points", fontsize=4.6,
                                    ha=_side(x), va="center", color=F.INK, zorder=4))
    # NOT DECLUTTERED. A ring PLACES its labels by construction - one per node, evenly spaced,
    # anchored outward by side - so the only collision it had was a long name running back over
    # its own disc, which `_side` fixes. Adding a vertical declutter on top made it worse, not
    # better: see `figure.spread_labels`, which is now bounded for the same reason.
    # THE TWO LEGENDS, WITH REAL VALUES ON THEM. Both channels here carry a number, and an
    # encoding a reader cannot invert is decoration. Without these the panel says "area is
    # interactions, width is strength" and offers no way to turn either back into a quantity.
    def _nice(v):
        if v <= 0:
            return 0.0
        e = 10.0 ** math.floor(math.log10(v))
        return float(max(1.0, round(v / e)) * e) if v >= 1 else round(v, 4)

    lg_y = -1.52
    ax.text(-1.55, lg_y + 0.20, "node area = interactions (in + out)", fontsize=4.4,
            color=F.INK, ha="left")
    xs = -1.44
    for frac in (0.15, 0.5, 1.0):
        val = _nice(dmax * frac)
        rr = 0.055 + 0.105 * math.sqrt(max(val, 0.0) / dmax)
        ax.add_patch(MCircle((xs, lg_y), rr, facecolor="#C8C8C8", ec="none", zorder=3))
        ax.text(xs, lg_y - rr - 0.055, f"{val:,.0f}", fontsize=4.0, ha="center", color=F.INK)
        xs += rr + 0.20
    ax.text(0.42, lg_y + 0.20, "edge width = summed strength", fontsize=4.4,
            color=F.INK, ha="left")
    ys = lg_y + 0.10
    for frac in (0.15, 0.5, 1.0):
        val = wmax * frac
        ax.plot([0.48, 0.86], [ys, ys], lw=0.25 + 2.6 * frac, color="#7A7A7A",
                solid_capstyle="butt", zorder=3)
        ax.text(0.92, ys, f"{val:.3g}", fontsize=4.0, va="center", color=F.INK)
        ys -= 0.115
    ax.set_xlim(-1.62, 1.62)
    ax.set_ylim(-1.86, 1.62)
    if title:
        ax.set_title(title, fontsize=8)

    n_drawn, n_all = int(mask.sum()), int((w > 0).sum())
    cap = (f"Inferred network as a ring: edge colour is the SENDER, the arrowhead the receiver, "
           f"a loop is signalling within a population. Node area is total interactions, edge "
           f"width summed strength.",
           f"{n_drawn} of {n_all} edges are drawn - the strongest {kept * 100:.0f}% of total "
           f"strength, weakest drawn {weakest:.4g}. "
           + (f"Left with no drawn link, and NAMED rather than dropped in silence: "
              f"{', '.join(short[p] for p in silent)}. " if silent else
              "Every population keeps at least one drawn link. ")
           + f"Each population's strongest link in and out is kept whatever its rank, so nothing "
             f"vanishes merely for being weak. Node radius has a floor, so the smallest "
             f"populations are drawn slightly larger than proportional. Every node carries its "
             f"number, so no reading depends on hue. Widths are on the method's own scale and "
             f"compare within this panel only.{note}")
    ctx.emit_figure(fid, fig, caption=cap)
    return True


def chord(ctx, edges, pops, *, fid="N2_chord", keep=0.75, title=None, note=""):
    """The aggregate network as a chord diagram. Returns True if drawn.

    THE KIND MOST LIKELY TO LIE BY OMISSION. A population whose links all fall under the cut is
    not drawn faintly, it is ABSENT - on one real cohort five of thirteen vanished with nothing
    on the figure to say so. The names go in the caption, every time.
    """
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.patches import Wedge, PathPatch
    from matplotlib.path import Path

    c, w = aggregate(edges, pops)
    if w.sum() <= 0:
        return False
    mask, kept, weakest = strength_cut(w, keep=keep)
    silent = unconnected(mask, pops)
    drawn = [i for i in range(len(pops)) if mask[i].any() or mask[:, i].any()]
    if len(drawn) < 2:
        return False
    cmap = F.palette(list(pops))
    short = F.short_labels(list(pops))

    tot = {i: float(w[i][mask[i]].sum() + w[:, i][mask[:, i]].sum()) for i in drawn}
    grand = sum(tot.values()) or 1.0
    gap = 2.0
    span = 360.0 - gap * len(drawn)
    start, arcs = 90.0, {}
    for i in drawn:
        ext = span * tot[i] / grand
        arcs[i] = (start - ext, start)
        start -= ext + gap

    # ONE TICK VALUE FOR THE WHOLE RING, rounded to something a reader can hold in mind.
    _raw = grand / 12.0
    _e = 10.0 ** math.floor(math.log10(_raw)) if _raw > 0 else 1.0
    _tick_val = max(1.0, round(_raw / _e)) * _e
    _tick_deg = span * _tick_val / grand

    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 1.06), layout="constrained")
    ax.set_aspect("equal")
    ax.axis("off")
    R, RW = 1.0, 0.075
    cursor = {i: arcs[i][1] for i in drawn}
    _labels = []
    for i in drawn:
        a0, a1 = arcs[i]
        ax.add_patch(Wedge((0, 0), R, a0, a1, width=RW, facecolor=cmap[pops[i]], lw=0))
        mid = math.radians((a0 + a1) / 2.0)
        mx, my = math.cos(mid), math.sin(mid)
        _labels.append(ax.annotate(short[pops[i]], (1.10 * mx, 1.10 * my),
                                   xytext=(0, 0), textcoords="offset points", ha=_side(mx),
                                   va="bottom" if my >= 0 else "top", fontsize=4.8,
                                   color=F.INK))
        # TICKS WORTH A STATED AMOUNT, so arc length inverts to a quantity instead of being
        # read as a share of a circle whose total nobody knows.
        step = grand / span
        k, deg_at = 0, a1
        while deg_at > a0 + 1e-9:
            if k % 2 == 0:
                ax.plot([R * math.cos(math.radians(deg_at)),
                         (R + .022) * math.cos(math.radians(deg_at))],
                        [R * math.sin(math.radians(deg_at)),
                         (R + .022) * math.sin(math.radians(deg_at))],
                        lw=.4, color=F.INK, zorder=4)
            deg_at -= _tick_deg
            k += 1

    def _arc_pt(deg, r=R - RW):
        return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)))

    def _arc(d0, d1, step=1.2):
        """Points along the circumference from d0 to d1 - the flat end of a ribbon."""
        n = max(2, int(abs(d1 - d0) / step) + 1)
        return [_arc_pt(d0 + (d1 - d0) * k / (n - 1.0)) for k in range(1, n)]

    for i in drawn:
        for j in drawn:
            if not mask[i, j]:
                continue
            ext = span * w[i, j] / grand
            a_lo, a_hi = cursor[i] - ext, cursor[i]
            cursor[i] -= ext
            b_lo, b_hi = cursor[j] - ext, cursor[j]
            cursor[j] -= ext
            # A RIBBON'S ENDS ARE ARCS AND ITS SIDES ARE THE CURVES THROUGH THE CENTRE.
            # The first version had this exactly inverted - it curved each END through (0,0)
            # and joined the two with a straight line - which draws a lens pinched at the
            # middle, not a ribbon. On a dense network the result was a starburst of spikes,
            # and it looked like a property of the data rather than of the path.
            verts = [_arc_pt(a_lo)]
            codes = [Path.MOVETO]
            for v in _arc(a_lo, a_hi):
                verts.append(v)
                codes.append(Path.LINETO)
            verts += [(0.0, 0.0), _arc_pt(b_lo)]
            codes += [Path.CURVE3, Path.CURVE3]
            for v in _arc(b_lo, b_hi):
                verts.append(v)
                codes.append(Path.LINETO)
            verts += [(0.0, 0.0), _arc_pt(a_lo)]
            codes += [Path.CURVE3, Path.CURVE3]
            ax.add_patch(PathPatch(Path(verts, codes), facecolor=cmap[pops[i]], lw=0,
                                   alpha=.55, zorder=1))
    # TWO ADJACENT SLIVERS SHARE A LABEL POSITION. Arcs sized by strength put the smallest
    # populations side by side at one point on the ring, and their names overprinted into an
    # unreadable stack - the case a label is most needed for, since a sliver cannot be
    # identified any other way.
    F.spread_labels(ax, _labels)
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.35, 1.35)
    if title:
        ax.set_title(title, fontsize=8)

    n_drawn, n_all = int(mask.sum()), int((w > 0).sum())
    cap = (f"Inferred network as a chord diagram. Arc length is a population's total strength "
           f"in plus out - one tick is {_tick_val:.3g} - and a ribbon takes the SENDER's colour, "
           f"its width that pair's strength.",
           f"{n_drawn} of {n_all} ordered pairs are drawn - the strongest {kept * 100:.0f}% of "
           f"total strength. "
           + (f"NOT DRAWN AT ALL, and named here because the figure cannot say it: "
              f"{', '.join(short[p] for p in silent)}. A population with no surviving link is "
              f"absent from a chord, not faint in it. " if silent else
              "Every population survives the cut and appears. ")
           + f"Each population's strongest link in and out is kept whatever its rank. Widths are "
             f"on the method's own scale and compare within this panel only.{note}")
    ctx.emit_figure(fid, fig, caption=cap)
    return True


# --------------------------------------------------------------------------------------------
# THE UNCUT VIEWS. The ring and the chord above are readable because they remove edges; these
# two remove none, which is what makes them the panels a reader checks a cut against.
# --------------------------------------------------------------------------------------------

def matrix(ctx, edges, pops, *, fid="N3_matrix", title=None, note=""):
    """Sender by receiver, every ordered pair, nothing cut. Returns True if drawn."""
    import numpy as np
    import matplotlib.pyplot as plt

    c, w = aggregate(edges, pops)
    if w.sum() <= 0:
        return False
    short = F.short_labels(list(pops))
    lab = [short[p] for p in pops]

    # R2: A ZERO CELL HAS TWO CAUSES AND THIS PANEL CANNOT TELL THEM APART. An edge list holds
    # what was returned, not what was attempted, so a pair that was scored and came back empty
    # is written into the same cell as a pair that never cleared a minimum-cells floor. The
    # panel marks every zero as one thing and the caption says which two things that is.
    #
    # AND A ZERO MUST NOT LOOK LIKE A WEAK EDGE, which the first version of this panel got
    # wrong: zeros took the bottom of the colour ramp, a faint grey x on pale cream, and were
    # indistinguishable from the weakest real pairs at a glance. Found by opening the image on a
    # real arm. Zeros are now OUT of the ramp entirely - white, crossed - and the ramp starts at
    # the smallest strength that was actually inferred, so every coloured cell is an edge.
    zero = (w <= 0)
    shown = np.where(zero, np.nan, w)
    lo = float(w[~zero].min()) if (~zero).any() else 0.0
    cmap = plt.get_cmap("magma_r").copy()
    cmap.set_bad("white")

    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.94), layout="constrained")
    im = ax.imshow(shown, cmap=cmap, vmin=lo, vmax=float(w.max()))
    ax.set_xticks(range(len(pops)), lab, rotation=90, fontsize=6)
    ax.set_yticks(range(len(pops)), lab, fontsize=6)
    ax.set_xlabel("receiver", fontsize=7)
    ax.set_ylabel("sender", fontsize=7)
    ys, xs = np.nonzero(zero)
    ax.scatter(xs, ys, marker="x", s=14, linewidths=0.7, color="#9A9A9A", zorder=3)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.ax.tick_params(labelsize=6)
    cb.set_label("summed strength", fontsize=6)
    if title:
        ax.set_title(title, fontsize=8)

    n_zero, n_all = int(zero.sum()), int(w.size)
    cap = (f"Every ordered population pair, uncut: row signals to column, colour is that pair's "
           f"summed strength on the method's own scale. White and crossed is NO edge, and the "
           f"colour scale starts at the weakest edge there is.",
           f"{n_all - n_zero} of {n_all} ordered pairs carry inferred signal. The {n_zero} "
           f"crossed cells are pairs with NO edge in this unit, and this panel CANNOT SAY WHICH "
           f"KIND of absence each is: a pair that was scored and returned nothing is a result, a "
           f"pair whose populations never cleared the method's minimum-cells floor is a "
           f"threshold, and an edge list records only what came back. A population absent from "
           f"the method's output entirely has no row and no column here at all. Strength is "
           f"per-object and comparable within this panel only.{note}")
    ctx.emit_figure(fid, fig, caption=cap)
    return True


def role_scatter(ctx, edges, pops, *, fid="N4_role", title=None, note=""):
    """Outgoing against incoming strength, one point per population. Returns True if drawn."""
    import matplotlib.pyplot as plt

    _c, w = aggregate(edges, pops)
    if w.sum() <= 0:
        return False
    out_s, in_s = w.sum(1), w.sum(0)
    cmap = F.palette(list(pops))
    short = F.short_labels(list(pops))

    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.92), layout="constrained")
    hi = float(max(out_s.max(), in_s.max())) or 1.0
    # THE DIAGONAL IS THE ONLY REFERENCE LINE THAT MEANS ANYTHING HERE. Net sender and net
    # receiver is a statement about which side of y = x a population falls, and without the line
    # drawn a reader compares two axes by eye and gets it wrong for anything near the middle.
    ax.plot([0, hi], [0, hi], color=F.GREY, lw=0.6, zorder=0)
    texts = []
    for i, p in enumerate(pops):
        ax.scatter(out_s[i], in_s[i], s=26, color=cmap[p], edgecolor="white", lw=0.4, zorder=2)
        texts.append(ax.annotate(short[p], (out_s[i], in_s[i]), fontsize=5.5,
                                 xytext=(3, 3), textcoords="offset points"))
    F.spread_labels(ax, texts)
    ax.set_xlabel("outgoing strength", fontsize=7)
    ax.set_ylabel("incoming strength", fontsize=7)
    ax.tick_params(labelsize=6)
    if title:
        ax.set_title(title, fontsize=8)

    n_send = int((out_s > in_s).sum())
    cap = (f"Each population's total outgoing strength against its total incoming strength. "
           f"The line is parity; above it a population receives more than it sends.",
           f"{n_send} of {len(pops)} populations sit below the line and are net senders here. "
           f"These are TWO SUMS OVER THE SAME EDGE LIST AND NOT A TEST: no interval is drawn "
           f"because none was computed, and a population close to the line is not thereby "
           f"balanced - it is unresolved. Both axes are on the method's own per-object scale, so "
           f"positions compare within this panel and rank-order across panels, nothing more."
           f"{note}")
    ctx.emit_figure(fid, fig, caption=cap)
    return True


# --------------------------------------------------------------------------------------------
# THE GROUPED VIEWS. Drawn only when the declaration names a grouping column, and NOT drawn
# silently when it does not - `panels.R2` applies to a panel's own absence as much as to a cell.
# --------------------------------------------------------------------------------------------

def flow_rank(ctx, edges, pops, group_col, *, fid="N5_flow", top=18, title=None, note=""):
    """Groups ranked by total strength within this unit. Returns True if drawn."""
    import matplotlib.pyplot as plt

    if not group_col or group_col not in getattr(edges, "columns", ()):
        return False
    tot = edges.groupby(group_col)["prob"].sum().sort_values(ascending=False)
    tot = tot[tot > 0]
    if not len(tot):
        return False
    shown, hidden = tot.head(top), tot.iloc[top:]

    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 1.05), layout="constrained")
    ys = range(len(shown))
    ax.barh(list(ys), list(shown.values), color=F.OKABE_ITO[0], height=0.72)
    ax.set_yticks(list(ys), [str(i) for i in shown.index], fontsize=6)
    ax.invert_yaxis()
    ax.set_xlabel("summed strength", fontsize=7)
    ax.tick_params(axis="x", labelsize=6)
    if title:
        ax.set_title(title, fontsize=8)

    kept = float(shown.sum() / tot.sum())
    cap = (f"{group_col.replace('_', ' ')}s in this unit, ranked by the strength summed over "
           f"every edge they carry.",
           f"{len(shown)} of {len(tot)} drawn, holding {kept * 100:.0f}% of total strength"
           + (f"; the {len(hidden)} not drawn are the weakest and are named in the source table. "
              if len(hidden) else ". ")
           + f"A BAR'S LENGTH IS NOT COMPARABLE TO THE SAME BAR IN ANOTHER UNIT - the scale is "
             f"per-object, so only the RANKING carries across panels. Nothing here is tested: "
             f"these are sums, with no interval and no significance marking.{note}")
    ctx.emit_figure(fid, fig, caption=cap)
    return True


def role_heatmap(ctx, edges, pops, group_col, *, fid="N6_role_heatmap", top=18, title=None,
                 note=""):
    """Group by population, as sender and as receiver, side by side. Returns True if drawn."""
    import numpy as np
    import matplotlib.pyplot as plt

    if not group_col or group_col not in getattr(edges, "columns", ()):
        return False
    tot = edges.groupby(group_col)["prob"].sum().sort_values(ascending=False)
    groups = [g for g in tot.index if tot[g] > 0][:top]
    if not groups or not pops:
        return False
    gi = {g: i for i, g in enumerate(groups)}
    pi = {p: i for i, p in enumerate(pops)}
    send = np.zeros((len(groups), len(pops)))
    recv = np.zeros((len(groups), len(pops)))
    for g, s, t, v in zip(edges[group_col].astype(str), edges["source"].astype(str),
                          edges["target"].astype(str), edges["prob"]):
        if g in gi:
            if s in pi:
                send[gi[g], pi[s]] += float(v)
            if t in pi:
                recv[gi[g], pi[t]] += float(v)

    # R1: ONE SCALE ACROSS THE GRID. Each row is divided by its own maximum ACROSS BOTH panels,
    # not per panel - scaling sender and receiver separately would make every group look equally
    # balanced, which is the one thing this figure is for.
    both = np.concatenate([send, recv], axis=1)
    rmax = both.max(axis=1, keepdims=True)
    rmax[rmax == 0] = 1.0
    short = F.short_labels(list(pops))
    lab = [short[p] for p in pops]

    fig, axes = plt.subplots(1, 2, figsize=(F.DOUBLE, F.SINGLE * 1.02), layout="constrained",
                             sharey=True)
    for ax, M, what in ((axes[0], send / rmax, "as sender"), (axes[1], recv / rmax, "as receiver")):
        im = ax.imshow(M, cmap="magma_r", vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_xticks(range(len(pops)), lab, rotation=90, fontsize=6)
        ax.set_title(what, fontsize=7)
    axes[0].set_yticks(range(len(groups)), [str(g) for g in groups], fontsize=6)
    cb = fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02)
    cb.ax.tick_params(labelsize=6)
    cb.set_label("share of the row's own maximum", fontsize=6)
    if title:
        fig.suptitle(title, fontsize=8)

    cap = (f"Where each {group_col.replace('_', ' ')} acts: its strength across populations as a "
           f"sender, and as a receiver. {len(groups)} of {len(tot)} drawn, the strongest by "
           f"total.",
           f"EVERY ROW IS SCALED TO ITS OWN MAXIMUM ACROSS BOTH PANELS, so a row says where a "
           f"group acts and NOT how strong it is - a group carrying a hundredth of another's "
           f"strength fills its row identically. Read strength off the flow ranking instead. "
           f"Scaling the two panels separately would have made every group look balanced between "
           f"sending and receiving, which is what this figure exists to distinguish.{note}")
    ctx.emit_figure(fid, fig, caption=cap)
    return True


def contribution(ctx, edges, pops, group_col, member_col, *, fid="N7_contribution", top=14,
                 title=None, note=""):
    """The strongest group, decomposed into the members inside it. Returns True if drawn."""
    import matplotlib.pyplot as plt

    cols = getattr(edges, "columns", ())
    if not group_col or not member_col or group_col not in cols or member_col not in cols:
        return False
    tot = edges.groupby(group_col)["prob"].sum().sort_values(ascending=False)
    tot = tot[tot > 0]
    if not len(tot):
        return False
    # ONE GROUP, AND WHICH ONE IS A CHOICE THAT MUST BE STATED. The strongest by total flow is
    # the defensible default and it is still a choice: a reader who does not know which group
    # this is, or that it was picked rather than given, will read it as the group that matters.
    #
    # AND IT MUST BE A GROUP THAT CAN BE DECOMPOSED. Taking the strongest unconditionally drew,
    # on a real arm, a single bar at 1.00 labelled `PECAM1_PECAM1` - a group whose one member is
    # itself. That is not a decomposition; it is a tautology that reads as a finding, and no
    # check could see it because a figure was written and the suite was green. The strongest
    # group with MORE THAN ONE member is chosen instead, its rank among all groups is stated,
    # and where no group has two members nothing is drawn - an absence the reporter names.
    g, rank, mem = None, 0, None
    for i, cand in enumerate(tot.index, start=1):
        sub = edges[edges[group_col].astype(str) == str(cand)]
        m = sub.groupby(member_col)["prob"].sum().sort_values(ascending=False)
        m = m[m > 0]
        if len(m) > 1:
            g, rank, mem = cand, i, m
            break
    if g is None:
        return False
    shown, hidden = mem.head(top), mem.iloc[top:]

    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.95), layout="constrained")
    ys = range(len(shown))
    ax.barh(list(ys), list(shown.values / mem.sum()), color=F.OKABE_ITO[2], height=0.72)
    ax.set_yticks(list(ys), [str(i) for i in shown.index], fontsize=6)
    ax.invert_yaxis()
    ax.set_xlabel(f"share of {g}'s total strength", fontsize=7)
    ax.tick_params(axis="x", labelsize=6)
    # THE GROUP'S NAME BELONGS IN THE TITLE. With an arm label passed in, the first version put
    # only the arm there and the group survived solely in an axis label - so a panel lifted out
    # of the page said which arm it described and not what it decomposed.
    ax.set_title(f"{title} — {g}" if title else str(g), fontsize=8)

    # R4: THE DENOMINATOR IS THIS GROUP'S TOTAL IN THIS UNIT, not the group's total anywhere
    # else, and a share therefore cannot be compared between units without saying so.
    cap = (f"The strongest {group_col.replace('_', ' ')} in this unit - {g} - split into the "
           f"{member_col.replace('_', ' ')}s that make it up.",
           f"{len(shown)} of {len(mem)} drawn"
           + (f", holding {shown.sum() / mem.sum() * 100:.0f}% of the group's strength; the "
              f"{len(hidden)} not drawn are the weakest. " if len(hidden) else ". ")
           + f"THE GROUP WAS CHOSEN, not given: {g} is rank {rank} of {len(tot)} by flow in THIS "
             f"unit and the highest-flow group that HAS more than one member"
           + (f" — the {rank - 1} above it decompose into themselves and say nothing. "
              if rank > 1 else ". ")
           + f"A panel in another unit may decompose a different group, and the two are then "
             f"not a comparison. The denominator is {g}'s own total here, so a share is within-unit "
             f"and within-group. A member absent from this panel was not necessarily tested and "
             f"found empty - an edge list holds what was returned.{note}")
    ctx.emit_figure(fid, fig, caption=cap)
    return True
