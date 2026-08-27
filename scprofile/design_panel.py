"""THE DESIGN, DRAWN — the one figure a multi-factor study exists to produce.

WHY THIS IS A MODULE AND NOT A FEW MORE LINES OF SVG. The per-arm view was hand-rolled inline
SVG strips, one `<figure>` per (measure, factor) pair, capped at three because a page's whole
budget is twelve figures. On a study with three per-cell measures and four design factors that
showed three of twelve comparisons; two factors appeared on no page at all, and the panels that
were drawn were cell-level quartile bars in which a difference between arms is invisible - the
full range of 50,000 cells is the full range of the scale, whatever the medians do.

Two figures replace it, and they answer different questions:

  THE DATA      one point per SAMPLE, arms side by side, every measure against every factor,
                shared scale down each row. n is the number of samples, which is the number
                that licences a claim - a per-cell view puts n in the tens of thousands and is
                pseudoreplication (Squair et al., Nat Commun 2021).

  THE EFFECT    every comparison on one axis, as a standardised difference with an interval,
                sorted by magnitude. Direction and size at a glance, and the ones whose interval
                spans zero are visibly the ones with nothing in them.

Neither is a test. Both are descriptions, and the interval is a description of spread, not a
p-value: with five samples an arm it is wide on purpose, and a reader who can see that it is
wide is better served than one shown a number that hides it.

NOTHING HERE KNOWS A PROJECT. Factors, levels, measures and samples all arrive as arguments.
"""
from __future__ import annotations

#: Colour-blind safe, and the same order every run so a level keeps its colour across figures.
ARM_COLOURS = ("#4C78A8", "#F58518", "#54A24B", "#B279A2", "#E45756", "#72B7B2")
#: Above this many arms a strip stops being readable and the measure is tabulated instead.
MAX_ARMS = 6


def _median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def effects(per_sample, design, factors=None):
    """[(measure, factor, g, lo, hi, from_level, to_level, n_from, n_to)] for every 2-level pair.

    Hedges' g - the standardised difference - because the measures have different units and a
    figure that puts them on one axis has to. The interval is the normal approximation on g's
    standard error; with a handful of samples an arm it is WIDE, and that is the point.
    """
    import math
    out = []
    factors = list(factors or sorted({f for r in design.values() for f in r}))
    measures = sorted({m for v in per_sample.values() for m in v})
    for m in measures:
        for f in factors:
            groups = {}
            for sample, vals in per_sample.items():
                lvl = (design.get(sample) or {}).get(f)
                if lvl is None or m not in vals:
                    continue
                groups.setdefault(str(lvl), []).append(float(vals[m]))
            levels = sorted(groups)
            if len(levels) != 2:
                continue
            a, b = groups[levels[0]], groups[levels[1]]
            if len(a) < 2 or len(b) < 2:
                continue
            ma, mb = sum(a) / len(a), sum(b) / len(b)
            va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
            vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
            sp = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
            if sp <= 0:
                continue
            d = (mb - ma) / sp
            # Hedges' correction: g is biased upward at these sample sizes and the correction
            # is the difference between a defensible number and an optimistic one.
            j = 1.0 - 3.0 / (4.0 * (len(a) + len(b)) - 9.0)
            g = d * j
            se = math.sqrt((len(a) + len(b)) / (len(a) * len(b))
                           + g * g / (2.0 * (len(a) + len(b) - 2)))
            out.append((m, f, g, g - 1.96 * se, g + 1.96 * se,
                        levels[0], levels[1], len(a), len(b)))
    out.sort(key=lambda r: -abs(r[2]))
    return out


def aliased(design, factors=None):
    """{factor: [factors that split the samples identically]}.

    Two factors with the same partition are ONE comparison drawn twice, and which of them a
    difference belongs to is exactly what the data cannot say. Naming them is the honest form;
    drawing both is two pieces of apparent evidence for one split.
    """
    factors = list(factors or sorted({f for r in design.values() for f in r}))
    sig = {}
    for f in factors:
        groups = {}
        for s, r in design.items():
            groups.setdefault(str((r or {}).get(f)), set()).add(s)
        sig[f] = frozenset(frozenset(v) for v in groups.values())
    out = {}
    for f in factors:
        out[f] = sorted(o for o in factors if o != f and sig[o] == sig[f])
    return out


#: Technical factors sort AFTER biological ones - a fixed, meaningful panel order beats one that
#: moves between figures (Wilke, Fundamentals of Data Visualization, ch. 21). Matched on the
#: factor NAME only as a hint; nothing here requires a project to use these words.
TECHNICAL_HINTS = ("batch", "chemistry", "lane", "run", "kit", "flowcell", "library", "protocol")


def _order(factors, alias):
    """Biological factors first, technical last, aliased duplicates folded into the one kept."""
    keep, seen = [], set()
    for f in sorted(factors, key=lambda x: (any(h in x.lower() for h in TECHNICAL_HINTS), x)):
        if f in seen:
            continue
        keep.append(f)
        seen.add(f)
        seen.update(alias.get(f) or [])
    return keep


def draw(per_sample, design, path, *, cells=None, width=None):
    """The design panel: sample-level points per arm, and every effect on one axis.

    A SUPERPLOT (Lord et al., J Cell Biol 2020) without the decorative half: one marker per
    SAMPLE, because the sample is what licences a claim, with n stated IN the panel - which is
    the single element that stops a reader taking n as the cell count.

    Rows are measures and share a y-axis, because the units are the same across factors and a
    reader compares along a row. Columns are factors, biological before technical, in a fixed
    order so the grid does not move between reports. The last column is the effect: every
    comparison on one standardised axis with an interval, which is the estimation-plot
    convention (Ho et al., Nat Methods 2019) and says what a p-value would hide at n=10.

    Returns the number of comparisons drawn, or 0 if there was nothing to draw.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # THE SHARED CONSTANTS, NOT A NUMBER OF MY OWN. This declared 7.0 inches - 177.8 mm against
    # a 174 mm double column - and saved at 200 dpi while the convention is 400. A module that
    # sets its own width and its own resolution is a second copy of the page geometry, and the
    # whole point of `figure.py` is that there is one.
    from . import figure as F
    width = float(width or F.DOUBLE)
    alias = aliased(design)
    factors = _order({f for r in design.values() for f in r}, alias)
    measures = sorted({m for v in per_sample.values() for m in v})
    if not factors or not measures:
        return 0
    eff = effects(per_sample, design, factors)
    ncol = len(factors) + (1 if eff else 0)
    fig, axes = plt.subplots(len(measures), ncol, squeeze=False,
                             figsize=(width, 1.95 * len(measures) + 0.85))
    for i, m in enumerate(measures):
        row_vals = [v[m] for v in per_sample.values() if m in v]
        lo, hi = (min(row_vals), max(row_vals)) if row_vals else (0, 1)
        pad = (hi - lo) * 0.12 or 1.0
        for j, f in enumerate(factors):
            ax = axes[i][j]
            groups = {}
            for s, vals in per_sample.items():
                lv = (design.get(s) or {}).get(f)
                if lv is not None and m in vals:
                    groups.setdefault(str(lv), []).append(float(vals[m]))
            levels = sorted(groups)[:MAX_ARMS]
            for k, lv in enumerate(levels):
                ys = groups[lv]
                # SPREAD THE TIES, not every point equally. Integer-valued measures put five
                # samples on one y and a fixed comb still stacked them; offsetting by rank
                # WITHIN a tied group separates exactly the points that would overlap.
                order = sorted(range(len(ys)), key=lambda t: ys[t])
                tie, xs = {}, [0.0] * len(ys)
                for t in order:
                    c = tie.get(ys[t], 0)
                    tie[ys[t]] = c + 1
                    xs[t] = k + ((c % 2) * 2 - 1) * (0.055 * ((c + 1) // 2))
                ax.plot(xs, ys, "o", ms=5.5, color=ARM_COLOURS[k % len(ARM_COLOURS)],
                        mec="white", mew=.7, alpha=.95, zorder=3, clip_on=False)
                ax.plot([k - .26, k + .26], [_median(ys)] * 2, color="#222", lw=1.7, zorder=4)
            ax.set_xticks(range(len(levels)))
            ax.set_xticklabels(levels, fontsize=6.5)
            ax.set_xlim(-.55, len(levels) - .45)
            ax.set_ylim(lo - pad, hi + pad)
            ax.tick_params(labelsize=6)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            # n IN THE PANEL. Every source on pseudoreplication converges on this: without it a
            # reader takes n from the cell count printed elsewhere on the page.
            ax.text(.02, .97, "n = " + " vs ".join(str(len(groups[l])) for l in levels),
                    transform=ax.transAxes, fontsize=5.6, va="top", color="#555")
            if i == 0:
                ttl = f + ("*" if alias.get(f) else "")
                ax.set_title(ttl, fontsize=8, weight="bold", pad=4)
            if j == 0:
                ax.set_ylabel(m, fontsize=7.5)
            else:
                ax.set_yticklabels([])
        if eff:
            ax = axes[i][len(factors)]
            # THE SAME ORDER AS THE COLUMNS. Sorting each row by its own effect size put the
            # factors in a different order in every row, so a reader scanning down the column
            # was re-reading the labels each time instead of comparing.
            _by = {r[1]: r for r in eff if r[0] == m}
            rows = [_by[f] for f in factors if f in _by]
            for y, r in enumerate(rows):
                solid = (r[3] > 0) or (r[4] < 0)
                col = "#B4442E" if solid else "#9AA0A6"
                ax.plot([r[3], r[4]], [y, y], color=col, lw=1.5, zorder=2)
                ax.plot([r[2]], [y], "o", ms=6, color=col, mec="white", mew=.7, zorder=3)
            ax.axvline(0, color="#333", lw=.9, ls="--", zorder=1)
            ax.set_yticks(range(len(rows)))
            ax.set_yticklabels([r[1] for r in rows], fontsize=6.5)
            # TOP-TO-BOTTOM MATCHES LEFT-TO-RIGHT. matplotlib puts index 0 at the bottom, so
            # the effect column listed the factors in the reverse of the column order and a
            # reader crossing from the panels to the summary re-read the labels.
            ax.set_ylim(max(len(rows) - .4, .6), -.6)
            ax.tick_params(labelsize=6)
            for sp in ("top", "right", "left"):
                ax.spines[sp].set_visible(False)
            if i == 0:
                ax.set_title("effect", fontsize=8, weight="bold", pad=4)
            if i == len(measures) - 1:
                ax.set_xlabel("std. difference (95% CI)", fontsize=6.5)
            # ONE SCALE DOWN THE COLUMN. Rows that scale themselves cannot be compared, and
            # comparison is the only reason the column exists.
            _all = [v for r in eff for v in (r[3], r[4])]
            if _all:
                _m = max(abs(min(_all)), abs(max(_all))) * 1.08 or 1.0
                ax.set_xlim(-_m, _m)
    # NO SUPTITLE. It wrapped and truncated at this width, and a figure that carries its own
    # explanation in raster text cannot be re-worded without redrawing it. The page states it
    # in the figcaption, where it is selectable, translatable and part of the prose budget.
    fig.tight_layout()
    try:
        F.fit_column(fig, target=width)
    except Exception:                                                     # noqa: BLE001
        pass
    _dpi = matplotlib.rcParams.get("savefig.dpi")
    fig.savefig(path, dpi=_dpi if isinstance(_dpi, (int, float)) else 400)
    plt.close(fig)
    return len(eff)
