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


#: Paul Tol's qualitative schemes, appended to Okabe-Ito for the categories Okabe-Ito runs out
#: on. Both sets are designed for colour-vision deficiency; together they give twelve hues that
#: stay separable, which is about where hue stops working as an identifier at all.
#: https://personal.sron.nl/~pault/ - "muted" and "light", minus the ones too near an Okabe-Ito.
TOL_EXTRA = ["#332288", "#88CCEE", "#44AA99", "#117733", "#999933", "#DDCC77",
             "#661100", "#AA4499", "#882255"]

#: Every hue this tool will use for a category, in order.
CATEGORY_COLOURS = OKABE_ITO[:7] + [c for c in TOL_EXTRA if c not in OKABE_ITO]

#: Above this many categories, no palette separates them and a legend stops being readable.
#: Not a style rule: at sixteen the eye cannot match a swatch to a dot.
PALETTE_LIMIT = len(CATEGORY_COLOURS)


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
    written = {}
    for ext in formats:
        f = d / f"{name}.{ext}"
        fig.savefig(f, format=ext)
        written[ext] = f
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
