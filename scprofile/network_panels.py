"""Single-network panels: the ring and the chord, drawn for ONE arm or ONE unit.

These are the two shapes every network method publishes and the two that go wrong the same way
every time: both must draw a SUBSET of edges to be readable at all, and a subset is a removal.
`panels.R3` is therefore not advice here, it is the contract - state the fraction of strength
kept, and NAME what is left with no link.

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
    for k, p in enumerate(pops):
        # A RADIUS FLOOR, DISCLOSED. Without it the smallest population is a dot nobody can
        # click on; with it the smallest are drawn slightly larger than proportional, and the
        # caption says so rather than letting the reader infer area is exact everywhere.
        rr = 0.055 + 0.105 * math.sqrt(deg[k] / dmax)
        x, y = pos[k]
        ax.add_patch(MCircle((x, y), rr, color=cmap[p], zorder=3))
        ax.text(x, y, str(k + 1), ha="center", va="center", fontsize=4.6,
                color="white", zorder=4, weight="bold")
        ax.annotate(f"{k + 1} {short[p]}", (x * 1.30, y * 1.30), fontsize=4.6,
                    ha="center", va="center", color=F.INK, zorder=4)
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
    for i in drawn:
        a0, a1 = arcs[i]
        ax.add_patch(Wedge((0, 0), R, a0, a1, width=RW, facecolor=cmap[pops[i]], lw=0))
        mid = math.radians((a0 + a1) / 2.0)
        ax.annotate(short[pops[i]], (1.13 * math.cos(mid), 1.13 * math.sin(mid)),
                    ha="center", va="center", fontsize=4.8, color=F.INK)
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

    def _pt(deg, r=R - RW):
        return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)))

    for i in drawn:
        for j in drawn:
            if not mask[i, j]:
                continue
            ext = span * w[i, j] / grand
            a_lo, a_hi = cursor[i] - ext, cursor[i]
            cursor[i] -= ext
            b_lo, b_hi = cursor[j] - ext, cursor[j]
            cursor[j] -= ext
            p0, p1, p2, p3 = _pt(a_hi), _pt(a_lo), _pt(b_hi), _pt(b_lo)
            path = Path([p0, (0, 0), p1, p2, (0, 0), p3, p0],
                        [Path.MOVETO, Path.CURVE3, Path.CURVE3,
                         Path.LINETO, Path.CURVE3, Path.CURVE3, Path.CLOSEPOLY])
            ax.add_patch(PathPatch(path, facecolor=cmap[pops[i]], lw=0, alpha=.55, zorder=1))
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
