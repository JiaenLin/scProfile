"""Publication figure conventions, shared by every kernel.

WHAT MAKES A FIGURE PUBLISHABLE, AS OPPOSED TO READABLE

A figure that looks fine in a report is routinely unusable in a manuscript, and always for the
same handful of reasons. Each is a setting, and setting them once here is the difference between
a report you read and a report you can submit from.

  vector, with LIVE TEXT   `pdf.fonttype = 42` embeds TrueType rather than converting glyphs to
                           paths. Type 3 - matplotlib's default - is what makes a figure land in
                           Illustrator with text that cannot be selected, restyled or corrected.
                           Journals reject it, and it is discovered at resubmission.
  points rasterised,       A UMAP of 100,000 cells as vector paths is a 40 MB PDF that crashes
  axes not                 the reader. `rasterized=True` on the scatter alone keeps every label,
                           axis and legend as text while the dots become an embedded image.
  a real size              Figures are made at the column width they will be printed at - 85 mm
                           single, 174 mm double - because a figure scaled down afterwards has
                           7 pt labels at 4 pt.
  a caption                Written where the numbers are, by the code that has them.
  SOURCE DATA              Every panel gets the table it was drawn from. Several journals now
                           require it, and it is the only way a reader can check a figure rather
                           than believe it.

Requires matplotlib, which any kernel that draws already has. It must not need anything else -
kernels live in pinned environments and this module is imported into all of them.
"""
from __future__ import annotations

from pathlib import Path

#: Journal column widths in inches. Most journals want one or the other, exactly.
#: Below this share of the page, the panel is mostly margin and shrinking further
#: buys the declared width with the data area. An over-wide figure scales down
#: proportionately; a collapsed one does not.
#: Never shrink a figure below this fraction of the size it declared, however far it
#: still is from the column. A panel that is mostly tick label cannot reach the target
#: by shrinking, and trying collapses it.
MIN_PAGE_SHARE = 0.7

SINGLE = 85 / 25.4
DOUBLE = 174 / 25.4

#: Okabe-Ito: eight hues distinguishable with any common form of colour vision, and in greyscale.
#: Chosen over matplotlib's default because a figure whose categories are indistinguishable to
#: ~8% of readers is a figure that fails for ~8% of readers.
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7",
             "#56B4E9", "#D55E00", "#F0E442", "#000000"]

GREY = "#D9D9D9"
INK = "#1A1A1A"

RC = {
    "pdf.fonttype": 42,          # live, selectable text in the vector output. Not negotiable.
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 7,
    "axes.labelsize": 7,
    "axes.titlesize": 8,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6,
    "legend.frameon": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "figure.dpi": 150,
    "savefig.dpi": 400,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
}


def use():
    """Apply the conventions. Called once by a kernel before it draws anything."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update(RC)
    return plt


#: Paul Tol's qualitative schemes. https://personal.sron.nl/~pault/ - "muted" and "light".
#: KEPT FOR PROVENANCE, no longer the source of `CATEGORY_COLOURS`; see the block below.
TOL_EXTRA = ["#332288", "#88CCEE", "#44AA99", "#117733", "#999933", "#DDCC77",
             "#661100", "#AA4499", "#882255"]

#: Every hue this tool will use for a category, in order.
#:
#: CHOSEN AT THE OPACITY MARKS ARE DRAWN AT, and against BOTH published dichromacy models. That
#: is the whole reason this list is no longer `OKABE_ITO[:7] + TOL_EXTRA`.
#:
#: Okabe-Ito and Paul Tol are both designed for colour-vision deficiency, and both are designed
#: for a SOLID swatch. Almost nothing in this tool is drawn solid: a chord ribbon goes down at
#: alpha 0.6, a circle-plot edge at 0.88, overplotted points lower still. Alpha compositing over
#: the page contracts the whole gamut toward it - chroma and lightness shrink together - so a
#: pair that clears the bar as a swatch need not clear it as a mark. Concatenating the two
#: published lists also never checked the JOIN between them, and the worst pairs in the old
#: palette were exactly that: one Okabe-Ito hue against one Tol hue.
#:
#: WHAT WAS MEASURED, on the thirteen populations these figures carry, worst pair by CIEDE2000:
#:
#:                            deuteranopia        protanopia        normal
#:                          Machado  Vienot   Machado  Vienot
#:     old, as a swatch       3.53     3.06      6.10    4.47        8.01
#:     old, at ribbon 0.6     1.73     2.39      5.06    3.50        5.34   <- indistinguishable
#:     this list, swatch      9.40    10.27      8.77    9.65       11.17
#:     this list, at 0.6      8.01     7.87      8.15    7.95        8.66
#:
#: DEUTERANOPIA AND PROTANOPIA, in that order, because those are the ones that exist: ~1 in 12
#: men and ~1 in 100, against ~1 in 10,000 for tritanopia. Every colour check on this palette
#: before 2026-08-28 ran tritanopia, which is how a palette with a worst deuteranopic pair of
#: dE00 1.7 at the drawn opacity passed all of them. Tritanopia is still in the objective at half
#: weight so it is not traded away, and it improves rather than degrades: 7.48 / 8.43 as a swatch
#: and 5.88 / 4.57 at 0.6 (Machado / Vienot), against the old palette's 4.78 / 1.91 and
#: 3.30 / 1.43.
#:
#: TWO SIMULATION MODELS, not one. Machado, Oliveira & Fernandes (2009) at severity 1.0 and
#: Vienot, Brettel & Mollon (1999) are both in current use and they disagree - on the palette
#: this file carried for one afternoon they disagreed about one violet-against-indigo pair by a
#: factor of 1.6, one model calling it safe and the other calling it collapsed. There is no way
#: to decide from outside which is right for a given reader, so the palette clears the bar under
#: BOTH rather than under whichever is being run today. `chord.py` measures with Vienot and warns
#: below dE 15 on its own CIE76 scale: the old palette scored 6.9 there and this one scores 16.8.
#:
#: The hues are ordered so that every PREFIX is itself a good palette - `palette()` gives the
#: i-th sorted label the i-th colour, so a five-category figure only ever sees the first five.
CATEGORY_COLOURS = ["#FFA200", "#2E2EAE", "#5D3A2E", "#C5B9F3",
                    "#DCAEA2", "#975100", "#745D80", "#7474FF",
                    "#179751", "#B997AE", "#97D168", "#8B80C5",
                    "#3A8068", "#AE0051", "#C57400", "#5D51A2"]

#: Above this many categories, no palette separates them and a legend stops being readable.
#: Not a style rule: at sixteen the eye cannot match a swatch to a dot.
PALETTE_LIMIT = len(CATEGORY_COLOURS)

#: The lowest opacity at which `CATEGORY_COLOURS` still holds `dE00 >= 7` between every pair -
#: under normal vision, deuteranopia and protanopia, under both simulation models. MEASURED by
#: bisection on the list above, not chosen: 0.566 at sixteen categories, 0.560 at thirteen,
#: 0.387 at eight, 0.179 at four. Rounded up to one figure a drawing routine can hold to.
#:
#: A mark drawn below this carries a colour its reader cannot decode, which for a chord ribbon or
#: a circle-plot edge is the only channel naming the sender. Fade below it deliberately or not at
#: all - and where a figure needs a weaker-looking mark, weaken the WIDTH, which stays legible
#: all the way down. `min_mark_alpha(n)` recomputes the floor for a given number of categories,
#: so it cannot drift away from the palette the way a hand-copied constant would.
MIN_MARK_ALPHA = 0.6


def palette(labels):
    """A stable colour per label: same label, same colour, in every figure of every kernel.

    Keyed on the sorted label list rather than on encounter order, so two figures drawn from
    different subsets of the same data still agree - a legend that means one thing in panel A and
    another in panel B is worse than no legend.

    IT USED TO CYCLE, SILENTLY. `OKABE_ITO[i % 8]` over an annotation with fourteen cell types
    gave five pairs of real populations the same colour, with a legend that showed each hue twice
    and nothing anywhere saying so. A palette that fails for readers with colour-vision deficiency
    was the
    stated reason for choosing Okabe-Ito in the first place; one that repeats itself fails for
    everybody.

    The palette is longer now, and where it still runs out `palette_collisions` names the pairs so
    a caller can say so or label the points directly. It never silently repeats without that being
    answerable.
    """
    labs = sorted(map(str, labels))
    return {l: CATEGORY_COLOURS[i % len(CATEGORY_COLOURS)] for i, l in enumerate(labs)}


def palette_collisions(labels):
    """`[(colour, [labels])]` for every hue carrying more than one label. `[]` when none.

    A figure with collisions must say so, or label its populations on the plot rather than in a
    legend. Two cell types under one swatch is a legend that cannot be used, and the reader has
    no way to discover it.
    """
    p = palette(labels)
    by = {}
    for l, c in p.items():
        by.setdefault(c, []).append(l)
    return sorted((c, sorted(ls)) for c, ls in by.items() if len(ls) > 1)


# --------------------------------------------------------------------- colour-vision deficiency
#
# THE CHECK LIVES WITH THE PALETTE. Every claim in the `CATEGORY_COLOURS` comment above is
# reproducible from this file alone, with no import beyond the standard library, so a reader who
# doubts a number can compute it rather than trust it - and so a test can assert the property
# instead of a person remembering to re-check it after an edit.
#
# TWO MODELS, because the two published ones disagree and neither is the arbiter of the other.
# Machado, Oliveira & Fernandes (2009) at severity 1.0 - the matrices `colorspacious` uses at
# severity 100 - and Vienot, Brettel & Mollon (1999), which is what several other tools and
# `chord.py`'s own check use. A palette measured under one and drawn for readers of the other has
# been checked against a model, not against a reader. Both are applied in LINEAR sRGB; doing it
# on the gamma values is the common shortcut and it flatters whatever is being checked.
#
# Distance is CIEDE2000 in CIE Lab under D65, never a comparison of hex strings: two hexes can
# differ in every digit and land on the same point once a deficiency is applied, which is exactly
# the failure being looked for.

CVD_MATRIX = {
    "deuteranopia": ((0.367322, 0.860646, -0.227968),
                     (0.280085, 0.672501, 0.047413),
                     (-0.011820, 0.042940, 0.968881)),
    "protanopia": ((0.152286, 1.052583, -0.204868),
                   (0.114503, 0.786281, 0.099216),
                   (-0.003882, -0.048116, 1.051998)),
    "tritanopia": ((1.255528, -0.076749, -0.178779),
                   (-0.078411, 0.930809, 0.147602),
                   (0.004733, 0.691367, 0.303900)),
}

#: Vienot, Brettel & Mollon (1999). A projection onto the dichromatic plane, so it is harsher
#: than Machado at severity 1.0 for some hues and gentler for others - the disagreement is the
#: reason both are here.
CVD_MATRIX_VIENOT = {
    "protanopia": ((0.0, 1.05118294, -0.05116099), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "deuteranopia": ((1.0, 0.0, 0.0), (0.9513092, 0.0, 0.04866992), (0.0, 0.0, 1.0)),
    "tritanopia": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (-0.86744736, 1.86727089, 0.0)),
}

#: Both, by name. `separation` takes one; `min_mark_alpha` requires every one of them.
CVD_MODELS = ("machado", "vienot")

#: The order every colour report prints, commonest deficiency first. A check that reports
#: tritanopia and not the other two has checked the rarest case and skipped the ones that exist.
CVD_ORDER = ("deuteranopia", "protanopia", "tritanopia")


def _to_rgb(colour):
    h = str(colour).lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _lab(rgb):
    """sRGB in [0,1] -> CIE Lab under D65."""
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    m = ((0.4124564, 0.3575761, 0.1804375),
         (0.2126729, 0.7151522, 0.0721750),
         (0.0193339, 0.1191920, 0.9503041))
    xyz = [sum(r[i] * lin[i] for i in range(3)) for r in m]
    white = (0.95047, 1.0, 1.08883)
    d = 6 / 29
    f = []
    for v, w in zip(xyz, white):
        t = v / w
        f.append(t ** (1 / 3) if t > d ** 3 else t / (3 * d * d) + 4 / 29)
    return (116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2]))


def cvd_simulate(rgb, kind, model="machado"):
    """An sRGB triple in [0,1] as `kind` sees it under `model`. Applied in LINEAR light."""
    m = CVD_MATRIX if model == "machado" else CVD_MATRIX_VIENOT
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    out = [sum(r[i] * lin[i] for i in range(3)) for r in m[kind]]
    out = [min(1.0, max(0.0, v)) for v in out]
    return tuple(v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055 for v in out)


def delta_e00(lab1, lab2):
    """CIEDE2000. Written out rather than approximated by Euclidean Lab distance, which
    overstates separation in exactly the desaturated region a composited mark lands in."""
    import math
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7))) if Cb > 0 else 0.5
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    else:
        dhp = h2p - h1p - 360 * (1 if h2p > h1p else -1)
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2)
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6))
         - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dTh = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7)) if Cbp > 0 else 0.0
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dTh)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                     + Rt * (dCp / Sc) * (dHp / Sh))


def separation(colours, alpha=1.0, kinds=CVD_ORDER, over=(1.0, 1.0, 1.0),
               model="machado"):
    """`{condition: [(dE00, a, b), ...]}` worst pair first, for colours DRAWN AT `alpha`.

    `alpha` is the point. A palette is validated as a solid swatch and then drawn at 0.6, and
    compositing over the page contracts the whole gamut toward it: the pair that decides whether
    a figure is readable is the worst pair AS DRAWN, which is not in general the worst pair as a
    swatch. Pass the alpha the marks actually carry.

    `colours` may be a list or a {name: colour} mapping; `over` is the background composited
    against, white unless a figure has a tinted panel.
    """
    items = (list(colours.items()) if hasattr(colours, "items")
             else [(c, c) for c in colours])
    out = {}
    for kind in ("normal",) + tuple(kinds):
        labs = []
        for name, col in items:
            rgb = _to_rgb(col)
            rgb = tuple(alpha * c + (1 - alpha) * b for c, b in zip(rgb, over))
            labs.append((name, _lab(rgb if kind == "normal"
                                    else cvd_simulate(rgb, kind, model))))
        out[kind] = sorted((delta_e00(labs[i][1], labs[j][1]), labs[i][0], labs[j][0])
                           for i in range(len(labs)) for j in range(i + 1, len(labs)))
    return out


def min_mark_alpha(n=PALETTE_LIMIT, threshold=7.0, kinds=("deuteranopia", "protanopia"),
                   models=CVD_MODELS):
    """The lowest alpha at which the first `n` category colours all stay `threshold` apart.

    Every model in `models`, and normal vision too - the worst case over all of them, because a
    reader is only served if the pair survives whichever model describes them. Bisected on the
    palette itself, so it cannot drift away from `CATEGORY_COLOURS` the way a hand-copied
    constant would. `MIN_MARK_ALPHA` is this at the full sixteen, rounded up.

    `None` when even a solid mark does not clear `threshold` - the honest answer, and not
    something to paper over with a floor of 1.0.
    """
    cols = CATEGORY_COLOURS[:n]

    def ok(a):
        worst = min(separation(cols, alpha=a, kinds=())["normal"][0][0],
                    *(separation(cols, alpha=a, kinds=kinds, model=m)[k][0][0]
                      for m in models for k in kinds))
        return worst >= threshold

    if not ok(1.0):
        return None
    lo, hi = 0.02, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if ok(mid):
            hi = mid
        else:
            lo = mid
    return hi


#: Layout algorithms whose output an axis can be named after. Anything else is printed whole: a
#: wrong guess about which half of a name is the algorithm is worse than not splitting it.
LAYOUT_ALGORITHMS = ("umap", "tsne", "draw_graph_fa", "draw_graph_fr", "fa2", "phate",
                     "densmap", "diffmap", "pca")


def split_basis(name):
    """`("umap", "scanvi")` from `umap_scanvi`; `(name, "")` for anything unrecognised.

    Longest known algorithm first, never the first underscore: `partition("_")` turns
    `draw_graph_fa` into `("draw", "graph_fa")`, inventing both an algorithm and a provenance out
    of one name.
    """
    n = str(name)
    n = n[2:] if n.startswith("X_") else n
    for known in sorted(LAYOUT_ALGORITHMS, key=len, reverse=True):
        if n == known:
            return known, ""
        if n.startswith(known + "_"):
            return known, n.removeprefix(known + "_")
    return n, ""


def basis_label(name, axis=1):
    """`UMAP 1  (of scanvi)` - the algorithm, then what it was run on.

    HERE RATHER THAN IN EACH PLUGIN, and that is the point. Four plugins drawing on a layout wrote
    four axis labels: three printed the obsm key verbatim (`umap_scanvi 1`) and the fourth carried
    a private splitter, so a correction to one reached none of the others. An axis label is a
    convention of this tool, like the column width and the palette, and a convention implemented
    per plugin is a convention that drifts.

    A layout derived from a representation IS a UMAP of that representation, and saying so is both
    shorter than the raw key and true - where `SCANVI 1`, which this replaced, was neither.
    """
    algo, of = split_basis(name)
    return f"{algo.upper()} {int(axis)}" + (f"  (of {of})" if of and int(axis) == 1 else "")

def short_labels(labels, sep="/", pair=" -> "):
    """`{label: shortened}` - hierarchical names cut to their shortest UNAMBIGUOUS tail.

    Returns a mapping and never a list, so a caller can put the short form on the axis and the
    full form in the source table, and a reader who needs the whole path can open it.

    WHY THIS IS NOT COSMETIC. An annotation like `Endothelial/Lymphatic endothelial` is a path,
    and a communication panel's categories are PAIRS of them - `A/B -> C/D`, sixty characters
    before any real name is reached. Rotated ninety degrees those labels took three quarters of
    the figure height on two shipped panels, squeezing the data into a strip at the top and, on
    one of them, leaving the colourbar drawn straight through the label text.

    SHORTENED ONLY AS FAR AS STAYS UNIQUE, one segment at a time. `Endothelial/Endocardial` and
    `Stromal/Fibroblast` both cut to their last segment; `Stromal/Mural/Pericyte` and
    `Stromal/Mural/Smooth muscle` do too, because those tails already differ. Where two labels
    WOULD collide, both keep another segment - so a shortened label always names exactly one
    thing, which an abbreviation chosen by truncation cannot promise.

    `pair` is applied on both sides of an arrow, because a pair of paths is the ordinary shape of
    a cell-cell communication category and shortening only one half helps by half.
    """
    labs = [str(x) for x in labels]

    def _sides(x):
        return x.split(pair) if pair and pair in x else [x]

    # Every distinct path across every side, shortened together: two sides of one arrow must not
    # disagree about how far a name can be cut.
    paths = sorted({p for x in labs for p in _sides(x)})
    depth = {p: 1 for p in paths}
    for _ in range(12):
        cut = {p: sep.join(p.split(sep)[-depth[p]:]) for p in paths}
        seen = {}
        for p, c in cut.items():
            seen.setdefault(c, []).append(p)
        clash = [ps for ps in seen.values() if len(ps) > 1]
        if not clash:
            break
        for ps in clash:
            for p in ps:
                if depth[p] < len(p.split(sep)):
                    depth[p] += 1
        else:
            if all(depth[p] >= len(p.split(sep)) for ps in clash for p in ps):
                break
    cut = {p: sep.join(p.split(sep)[-depth[p]:]) for p in paths}
    return {x: (pair.join(cut[p] for p in _sides(x)) if pair and pair in x else cut[x])
            for x in labs}

def rasterize_points(ax):
    """Mark scatter collections raster, leaving text and axes vector."""
    for c in ax.collections:
        c.set_rasterized(True)


def fit_column(fig, target=None):
    """Shrink a figure back to the column width it declared. Returns the width in mm.

    A PANEL THAT DECLARES `SINGLE` AND SAVES AT 98 mm IS NOT A SINGLE-COLUMN PANEL. Everything
    drawn outside the axes - a key in the right margin, a long tick label, a colourbar - is
    ADDED to the canvas by `bbox_inches="tight"` rather than fitted into it, and `figsize` only
    ever described the axes. Measured across the shipped set: panels declaring the 85 mm column
    saved at 98 to 118 mm.

    Nothing errors, which is why it survived. A journal scales an over-wide figure down to the
    column, and every font goes down with it: 7 pt type set at 85 mm prints at 6 pt from a
    99 mm file and at 5 pt from a 118 mm one. The figure looks fine in the report and is
    illegible in the manuscript.

    Applied at SAVE time, so a plugin gets it by declaring a width and drawing normally, and no
    plugin needs its own copy. The scale is uniform, so proportions and aspect are preserved.
    """
    import matplotlib.pyplot as plt                                       # noqa: F401
    # CLASSIFY BY WHAT THE PANEL DECLARED, NOT BY WHAT THE LABELS GREW IT TO. This read the
    # CURRENT canvas and split at the midpoint, so a panel that sized itself from its data -
    # `side + label band` - could land either side of the cliff: measured, a 46-character
    # population name gave 85.0 mm and a 47-character one gave 129.7 mm. One character in one
    # name flipped the saved width by 53%, which is worse than being uniformly over-wide,
    # because an over-wide figure at least scales down proportionately every time.
    #
    # `get_size_inches()` at this point is the figsize the panel asked for; snapping it to the
    # NEARER of the two columns is stable under any label.
    w0 = float(fig.get_size_inches()[0])
    want = float(target) if target else (
        SINGLE if abs(w0 - SINGLE) <= abs(w0 - DOUBLE) else DOUBLE)
    # ITERATED, because TEXT DOES NOT SCALE WITH THE FIGURE. Shrinking the canvas shrinks the
    # axes and leaves the key, the tick labels and the colourbar at their point size, so one
    # pass over-corrects the axes and still overshoots the target - measured, 98.2 mm went to
    # 89.7 against a target of 85. Three passes converge; the loop exits as soon as it is
    # inside half a millimetre, and never grows a figure that is already narrow enough.
    # A TOTAL FLOOR, NOT A PER-STEP ONE. The clamp used to sit inside the loop as
    # `k = max(0.55, want/got)`, which bounds one iteration and not the product: six passes at
    # 0.55 is 0.028, and a panel whose margin is a long tick label collapsed from 85 mm to
    # 13.7 mm while its axes stayed a constant share of the shrinking page, so the share test
    # never fired. Measured, and it is the same defect as the thing being fixed - buying the
    # declared width with the data - only faster.
    w0, h0 = fig.get_size_inches()
    prev = None
    for _ in range(10):
        fig.canvas.draw()
        try:
            got = fig.get_tightbbox(fig.canvas.get_renderer()).width
        except Exception:                                                 # noqa: BLE001
            return fig.get_size_inches()[0] * 25.4
        if got <= want + 0.5 / 25.4:
            break
        # NOT CONVERGING. Text does not scale, so a figure that is mostly label reaches a floor
        # where shrinking the canvas no longer shrinks the saved image. Stop there rather than
        # iterate into a collapse.
        # BAIL ONLY WHEN IT STOPS IMPROVING AT ALL. A 2% floor was too strict: a figure whose
        # margin is a fixed-size key converges slowly but genuinely, and the strict test made
        # this give up on the ordinary legend case it was written for.
        if prev is not None and got >= prev - 1e-4:
            fig.set_size_inches(w0, h0)
            break
        prev = got
        w, h = fig.get_size_inches()
        k = want / got
        if w * k < MIN_PAGE_SHARE * w0:
            fig.set_size_inches(w0, h0)    # too wide beats unreadable, and beats collapsed
            break
        fig.set_size_inches(w * k, h * k)
    return got * 25.4


#: How far a written panel may sit from the width it declared before `save`/`emit_figure` say so.
#: Not zero: `fit_column` snaps to the declared figsize and a tight bbox still rounds to whole
#: pixels, which is ~0.06 mm at 400 dpi. One millimetre is under a percent of the single column
#: and well inside what a typesetter absorbs; past it, the scaling a typesetter applies starts
#: taking the fonts with it.
WIDTH_TOLERANCE_MM = 1.0


def written_width_mm(path, dpi=None):
    """The width of a written PNG, in millimetres, read from the FILE. None if unreadable.

    THE ONLY HONEST MEASUREMENT OF WHAT WAS SAVED. `figsize` is what was asked for and
    `bbox_inches="tight"` is free to ignore it - it ADDS everything outside the axes to the
    canvas rather than fitting it in. Reporting `figsize` after such a save is a check that
    cannot fail: it restates the input as though it were the outcome.

    Measured on real panels, a declared 174.00 mm double column wrote at 175.01 mm and every log
    line said the two agreed, because the number in the log came from the figure object.
    """
    import struct

    try:
        raw = Path(path).read_bytes()
        if raw[12:16] != b"IHDR":
            return None
        px = struct.unpack(">II", raw[16:24])[0]
    except Exception:                                                     # noqa: BLE001
        return None
    if not dpi:
        import matplotlib as _mpl
        dpi = _mpl.rcParams.get("savefig.dpi")
        dpi = dpi if isinstance(dpi, (int, float)) else 200
    return px / float(dpi) * 25.4


def check_written_width(path, want_in, *, log=None, dpi=None):
    """Compare a written PNG against the width it declared. Returns (got_mm, ok).

    Warns rather than raises. A panel one millimetre over is still a panel worth having, and a
    hard failure here would be a gate that fires on correct behaviour - which is the kind that
    gets switched off. What it must not do is stay quiet, because nothing downstream can tell an
    over-wide figure from a correct one: both render.
    """
    got = written_width_mm(path, dpi=dpi)
    if got is None or not want_in:
        return got, True
    want = float(want_in) * 25.4
    ok = abs(got - want) <= WIDTH_TOLERANCE_MM
    if not ok and log is not None:
        log(f"      WIDTH {Path(path).name}: saved {got:.2f} mm against a declared "
            f"{want:.2f} mm ({got - want:+.2f}). `bbox_inches` added what `fit_column` had "
            f"fitted; the panel will be rescaled to the column and its type with it.")
    return got, ok


def save(fig, out_dir, name, *, caption="", source=None, formats=("png", "pdf"), log=print):
    """Write one figure in every requested format and return its manifest entry.

    Returns {"path", "vector", "caption", "source"} - the shape `manifest.write_output` accepts
    for a captioned figure. `source` is a path to the table the figure was drawn from; pass it,
    because a figure whose numbers cannot be opened is a figure a reader has to take on trust.
    """
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    # THE DECLARED WIDTH IS ENFORCED HERE, once, for every plugin - see `fit_column`.
    try:
        fit_column(fig)
    except Exception:                                                     # noqa: BLE001
        pass                       # a figure that will not measure is still a figure to write
    want_in = float(fig.get_size_inches()[0])
    written = {}
    for ext in formats:
        f = d / f"{name}.{ext}"
        fig.savefig(f, format=ext)
        written[ext] = f
    # WHAT WAS WRITTEN, NOT WHAT WAS ASKED FOR. See `check_written_width`.
    if "png" in written:
        check_written_width(written["png"], want_in, log=log)
    entry = {"path": str(written.get("png", list(written.values())[0])), "caption": caption}
    if "pdf" in written:
        entry["vector"] = str(written["pdf"])
    if source is not None:
        entry["source"] = str(source)
    log(f"    {name}  " + ", ".join(sorted(written)) + (f"  [{Path(source).name}]" if source
                                                        else "  [NO SOURCE DATA]"))
    import matplotlib.pyplot as plt
    plt.close(fig)
    return entry


def legend_outside(fig, ax, handles=None, labels=None, ncol=1, markerscale=2.5):
    """Legend to the right of the axes, never on top of the data.

    `markerscale` DEFAULTS TO 2.5 because a categorical key stands for dots drawn at s=2 or s=3,
    which are invisible at true size. A SIZE key is the opposite case and must pass 1.0: its
    whole content is how big the marker is, so scaling it says something false about every dot
    it explains - and at 2.5 the three keys of a size legend overlapped into one blob in the
    margin, which is a size key a reader cannot read at all.
    """
    kw = dict(loc="center left", bbox_to_anchor=(1.02, 0.5), ncol=ncol,
              handletextpad=0.4, borderaxespad=0, markerscale=markerscale)
    if handles is not None:
        return fig.legend(handles, labels, **kw)
    return ax.legend(**kw)

def spread_labels(ax, texts, *, iterations=80, pad=1.2, clip=True, max_shift=14.0):
    """Nudge annotation labels apart, in DISPLAY space, until they stop overlapping.

    RADIAL OFFSET IS NOT ENOUGH WHERE IT MATTERS. Offsetting each label away from the centroid
    separates a round cloud and does nothing for a tight cluster: every member is on the same
    side, so every label is pushed the same way and they land on each other. Measured on a real
    pathway-similarity panel, where the twelve highest-flow points sat in one clump and their
    labels overprinted into an unreadable stack - which is the case a label is most needed for,
    because that clump is the result.

    Works on `Annotation`s created with `textcoords="offset points"`: their offset is `xyann`,
    so this adjusts the offset and never the data. Purely vertical separation, deliberately -
    moving a label sideways breaks the left/right alignment that ties it to its own point, and
    a label that has drifted onto a neighbour is worse than one that overlaps slightly.

    Returns the number of iterations used, so a caller can tell "settled" from "gave up".
    """
    if not texts:
        return 0
    fig = ax.figure
    try:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
    except Exception:
        # NO RENDERER, NO DECLUTTER, AND NO CRASH. Some backends cannot measure text before the
        # figure is saved. A slightly overlapping label is a blemish; an exception here loses
        # the whole panel, and the panel is the point.
        return 0
    used = 0
    for used in range(1, iterations + 1):
        try:
            boxes = [t.get_window_extent(r) for t in texts]
        except Exception:
            return used
        moved = False
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                bi, bj = boxes[i], boxes[j]
                if not bi.overlaps(bj):
                    continue
                overlap = min(bi.y1, bj.y1) - max(bi.y0, bj.y0) + pad
                if overlap <= 0:
                    continue
                step = overlap / 2.0
                up, down = (i, j) if bi.y0 >= bj.y0 else (j, i)
                for t, dy in ((texts[up], step), (texts[down], -step)):
                    ox, oy = t.xyann
                    # BOUNDED, BECAUSE AN UNBOUNDED DECLUTTER LOSES THE LABEL. Pushing purely
                    # vertically accumulates wherever several labels share a y-band - which is
                    # every label on a ring - and on a twelve-node ring it drove ten of them
                    # clean off the axes and left one at the bottom of the canvas, nowhere near
                    # its mark. A label that has travelled further than `max_shift` points can
                    # no longer be associated with the thing it names, so overlapping slightly
                    # is the better failure.
                    ny = oy + dy * 72.0 / fig.dpi
                    t.set_position((ox, max(-max_shift, min(max_shift, ny))))
                moved = True
        if not moved:
            break
        try:
            fig.canvas.draw()
        except Exception:
            return used
    if clip:
        # A LABEL PUSHED OUT OF THE AXES IS NOT SAVED, IT IS LOST. Growing the y-range is the
        # one adjustment that keeps every label attached to its own point.
        try:
            ax.margins(y=max(ax.margins()[1], 0.12))
        except Exception:
            pass
    return used


# --------------------------------------------------------------------------------------------
# WHAT A MACHINE CAN SEE IN A FIGURE, so the eye is spent on what it cannot.
#
# Eleven defects were found in one figure set by opening every panel. THREE OF THEM WERE
# MECHANICAL - text printed over text, a label outside the canvas, a size channel with no key -
# and finding those by eye is a waste of the one check that cannot be automated. Every one was
# also found LATE, after the panel had shipped, because nothing looked at the figure between
# drawing it and saving it.
#
# `audit` runs at the moment the figure is complete and about to be written, where the artists
# are still live and their rendered positions are knowable. It REPORTS; it does not refuse.
# A drawing this catches is usually still worth shipping, and a gate that blocks a run over a
# label two pixels out is a gate somebody removes.
# --------------------------------------------------------------------------------------------

#: A text artist smaller than this is a tick label or a footnote, and those legitimately sit
#: close to things. The check is for a LABEL landing on a LABEL, not for tight typesetting.
_AUDIT_MIN_PT = 4.0

#: Two boxes overlapping by less than this fraction of the smaller one are touching, not
#: colliding. Chosen before the first run rather than tuned to its output.
_AUDIT_OVERLAP = 0.20


def audit(fig):
    """[(code, detail)] - what is measurably wrong with this figure. Empty is the good case.

    Three checks, each the mechanical half of a defect found by eye:

      text_overlap   two text artists whose rendered boxes overlap. Found by eye four times in
                     one set: a note through a label, an n through a contrast name, eleven
                     labels through each other, and a title through a point.
      off_canvas     an artist rendered outside the figure. Found by eye twice: a title cut to
                     "observed difference betwe" and a label starting before its own axis.
      size_unkeyed   a scatter drawing more than one marker size, with no legend on the axes.
                     A size channel a reader cannot decode is decoration that looks like
                     evidence, and it shipped on two panels at once.
    """
    out = []
    try:
        fig.canvas.draw()
        rend = fig.canvas.get_renderer()
    except Exception:                                                     # noqa: BLE001
        return out                       # a figure that will not render is not this check's job

    def _bb(a):
        try:
            b = a.get_window_extent(renderer=rend)
            return b if b.width > 0 and b.height > 0 else None
        except Exception:                                                 # noqa: BLE001
            return None

    # ---- text on text -------------------------------------------------------------------
    texts = []
    for ax in fig.get_axes():
        for t in ax.texts:
            if t.get_visible() and str(t.get_text()).strip() \
                    and float(t.get_fontsize() or 0) >= _AUDIT_MIN_PT:
                texts.append((t, _bb(t)))
    for t in fig.texts:
        if t.get_visible() and str(t.get_text()).strip() \
                and float(t.get_fontsize() or 0) >= _AUDIT_MIN_PT:
            texts.append((t, _bb(t)))
    texts = [(t, b) for t, b in texts if b is not None]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i][1], texts[j][1]
            w = min(a.x1, b.x1) - max(a.x0, b.x0)
            h = min(a.y1, b.y1) - max(a.y0, b.y0)
            if w <= 0 or h <= 0:
                continue
            small = min(a.width * a.height, b.width * b.height) or 1.0
            if (w * h) / small >= _AUDIT_OVERLAP:
                out.append(("text_overlap",
                            f"{str(texts[i][0].get_text())[:24]!r} over "
                            f"{str(texts[j][0].get_text())[:24]!r}"))

    # ---- outside the canvas -------------------------------------------------------------
    # `bbox_inches="tight"` GROWS the canvas for anything outside it, so this catches only what
    # is clipped by an artist's own clip box - which is what truncated a title and a label.
    fw, fh = fig.canvas.get_width_height()
    for t, b in texts:
        if not t.get_clip_on():
            continue
        if b.x0 < -1 or b.y0 < -1 or b.x1 > fw + 1 or b.y1 > fh + 1:
            out.append(("off_canvas", f"{str(t.get_text())[:32]!r} is clipped by the canvas"))

    # ---- a size channel with no key -----------------------------------------------------
    for ax in fig.get_axes():
        sized = False
        for c in ax.collections:
            try:
                sizes = c.get_sizes()
            except Exception:                                             # noqa: BLE001
                continue
            if sizes is not None and len(sizes) > 1 and float(max(sizes)) > 0:
                if float(max(sizes)) / (float(min(sizes)) or 1.0) >= 1.5:
                    sized = True
        if sized and ax.get_legend() is None and not any(
                a.get_legend() is not None for a in fig.get_axes()):
            out.append(("size_unkeyed",
                        "a scatter varies marker size and no axes carries a legend"))
            break
    return out
