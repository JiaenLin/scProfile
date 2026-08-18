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


def palette(labels):
    """A stable colour per label: same label, same colour, in every figure of every kernel.

    Keyed on the sorted label list rather than on encounter order, so two figures drawn from
    different subsets of the same data still agree - a legend that means one thing in panel A and
    another in panel B is worse than no legend.
    """
    labs = sorted(map(str, labels))
    return {l: OKABE_ITO[i % len(OKABE_ITO)] for i, l in enumerate(labs)}


def rasterize_points(ax):
    """Mark scatter collections raster, leaving text and axes vector."""
    for c in ax.collections:
        c.set_rasterized(True)


def save(fig, out_dir, name, *, caption="", source=None, formats=("png", "pdf"), log=print):
    """Write one figure in every requested format and return its manifest entry.

    Returns {"path", "vector", "caption", "source"} - the shape `manifest.write_output` accepts
    for a captioned figure. `source` is a path to the table the figure was drawn from; pass it,
    because a figure whose numbers cannot be opened is a figure a reader has to take on trust.
    """
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
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


def legend_outside(fig, ax, handles=None, labels=None, ncol=1):
    """Legend to the right of the axes, never on top of the data."""
    kw = dict(loc="center left", bbox_to_anchor=(1.02, 0.5), ncol=ncol,
              handletextpad=0.4, borderaxespad=0, markerscale=2.5)
    if handles is not None:
        return fig.legend(handles, labels, **kw)
    return ax.legend(**kw)
