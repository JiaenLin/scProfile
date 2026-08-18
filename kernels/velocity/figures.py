#!/usr/bin/env python3
"""The figure set a velocity paper actually contains.

Not "some plots of the result" - the panels a reader and a reviewer will look for, each written
as a raster preview and a vector PDF with live text, at journal column width, with a caption and
the table it was drawn from. What a figure is FOR is stated in its caption, and what it cannot
establish stays in the kernel's `cannot_show`.

  proportions     spliced vs unspliced per population. The first panel in most velocity papers,
                  and the one that decides whether the rest is worth reading: a population whose
                  unspliced fraction is near zero has no kinetic signal, whatever the arrows do.
  stream          the field on the embedding, coloured by population. The headline panel.
  grid            the same field as discrete arrows. Preferred by many journals over the stream,
                  because a stream line interpolates and an arrow does not.
  confidence      per cell, and per population as a distribution. The panel that says whether to
                  believe the headline one.
  phase           per-gene phase portraits with the steady-state fit. The evidence that the model
                  fitted anything - a reviewer asking "show me the genes" is asking for this.
  transitions     directed population-to-population flow. The quantitative form of the stream.
  pseudotime      the ordering, with its own caveat in the caption.
  drivers         the genes carrying the field, ranked.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scprofile import figure                                              # noqa: E402


def _clean(ax):
    ax.set_xticks([]), ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def proportions(A, labels, out, sources_dir, plt, log=print):
    """Spliced/unspliced balance per population - the panel that licenses the rest."""
    import numpy as np
    import pandas as pd
    if labels is None:
        return None
    rows = []
    for lab in sorted(set(labels)):
        m = np.asarray(labels) == lab
        s = float(A.layers["spliced"][m].sum())
        u = float(A.layers["unspliced"][m].sum())
        if s + u <= 0:
            continue
        rows.append({"label": lab, "n_cells": int(m.sum()),
                     "spliced_fraction": s / (s + u), "unspliced_fraction": u / (s + u),
                     "spliced_counts": s, "unspliced_counts": u})
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("unspliced_fraction", ascending=False)
    src = Path(sources_dir) / "F1_proportions.csv"
    df.to_csv(src, index=False)

    fig, ax = plt.subplots(figsize=(figure.SINGLE, max(1.6, 0.20 * len(df) + 0.9)))
    y = np.arange(len(df))
    ax.barh(y, df["spliced_fraction"], color="#0072B2", label="spliced", height=0.72)
    ax.barh(y, df["unspliced_fraction"], left=df["spliced_fraction"], color="#E69F00",
            label="unspliced", height=0.72)
    ax.set_yticks(y), ax.set_yticklabels(df["label"])
    ax.invert_yaxis()
    ax.set_xlim(0, 1), ax.set_xlabel("fraction of counts")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    figure.legend_outside(fig, ax)
    return figure.save(
        fig, out, "F1_proportions",
        caption=("Spliced and unspliced fraction of counts in each population. The unspliced "
                 "fraction is the material velocity is inferred from: a population near zero has "
                 "no kinetic signal to fit, whatever arrows are drawn over it. Fractions are of "
                 "counts, not of cells."),
        source=src, log=log)


def stream_and_grid(A, basis, label_key, out, sources_dir, plt, scv, colours, log=print):
    """The headline field, as a stream and as discrete arrows."""
    import numpy as np
    import pandas as pd
    xy = np.asarray(A.obsm[f"X_{basis}"])[:, :2]
    v = np.asarray(A.obsm[f"velocity_{basis}"])[:, :2]
    src = Path(sources_dir) / "F2_field.csv"
    d = {"barcode": A.obs_names.astype(str), "x": xy[:, 0], "y": xy[:, 1],
         "vx": v[:, 0], "vy": v[:, 1]}
    if label_key and label_key in A.obs:
        d["label"] = A.obs[label_key].astype(str).values
    pd.DataFrame(d).to_csv(src, index=False)

    made = []
    for kind, fn, cap in (
        ("F2_stream", scv.pl.velocity_embedding_stream,
         "RNA velocity on the {b} embedding, as a stream. Lines follow the field and are "
         "INTERPOLATED between cells; arrow length is a direction, never a rate in real time, and "
         "lengths are not comparable between datasets."),
        ("F3_grid", scv.pl.velocity_embedding_grid,
         "The same field as discrete arrows on a grid. Each arrow averages the cells in its cell "
         "and does not interpolate between them, so an empty region stays empty - which is why "
         "this panel and the stream can disagree, and why both are shown."),
    ):
        try:
            fig, ax = plt.subplots(figsize=(figure.SINGLE, figure.SINGLE * 0.92))
            fn(A, basis=basis, color=label_key, ax=ax, show=False, legend_loc="none",
               palette=[colours[l] for l in sorted(colours)] if colours else None,
               size=12, alpha=0.75, arrow_color=figure.INK, linewidth=0.5, dpi=400,
               title="", frameon=False)
            figure.rasterize_points(ax)
            _clean(ax)
            if colours:
                import matplotlib.lines as ml
                h = [ml.Line2D([], [], marker="o", ls="", ms=3, color=c, label=l)
                     for l, c in sorted(colours.items())]
                figure.legend_outside(fig, ax, h, [x.get_label() for x in h],
                                      ncol=1 if len(h) <= 14 else 2)
            made.append(figure.save(fig, out, kind, caption=cap.format(b=basis), source=src,
                                    log=log))
        except Exception as e:                                            # noqa: BLE001
            log(f"    {kind} not drawn: {e}")
    return made


def confidence(A, labels, basis, out, sources_dir, plt, scv, colours, log=print):
    """Where the field is trustworthy, on the map and as a distribution per population."""
    import numpy as np
    import pandas as pd
    conf = np.asarray(A.obs["velocity_confidence"], dtype=float)
    length = np.asarray(A.obs["velocity_length"], dtype=float)
    src = Path(sources_dir) / "F4_confidence.csv"
    d = {"barcode": A.obs_names.astype(str), "velocity_confidence": conf,
         "velocity_length": length}
    if labels is not None:
        d["label"] = labels
    pd.DataFrame(d).to_csv(src, index=False)

    xy = np.asarray(A.obsm[f"X_{basis}"])[:, :2]
    ncol = 1 if labels is None else 2
    fig, axs = plt.subplots(1, ncol, figsize=(figure.DOUBLE if ncol == 2 else figure.SINGLE,
                                              figure.SINGLE * 0.9), squeeze=False)
    ax = axs[0][0]
    o = np.argsort(conf)
    sc = ax.scatter(xy[o, 0], xy[o, 1], c=conf[o], s=2, cmap="RdYlBu_r", vmin=0, vmax=1,
                    linewidths=0, rasterized=True)
    _clean(ax)
    ax.set_title("velocity confidence", loc="left")
    cb = fig.colorbar(sc, ax=ax, fraction=0.04, pad=0.02)
    cb.outline.set_visible(False)

    if labels is not None:
        ax2 = axs[0][1]
        order = sorted(set(labels))
        data = [conf[np.asarray(labels) == l] for l in order]
        bp = ax2.boxplot(data, vert=False, widths=0.62, patch_artist=True, showfliers=False,
                         medianprops=dict(color=figure.INK, lw=0.8))
        for patch, l in zip(bp["boxes"], order):
            patch.set_facecolor((colours or {}).get(l, figure.GREY))
            patch.set_edgecolor(figure.INK), patch.set_linewidth(0.5)
        ax2.set_yticklabels(order)
        ax2.set_xlabel("velocity confidence")
        ax2.set_xlim(0, 1)
        ax2.axvline(0.5, color=figure.INK, ls="--", lw=0.6)
        ax2.invert_yaxis()
        ax2.set_title("per population", loc="left")
    return figure.save(
        fig, out, "F4_confidence",
        caption=("Velocity confidence: the agreement between a cell's own velocity vector and "
                 "those of its neighbours. Low values mean the arrows in that region disagree "
                 "with each other, so the field there is unresolved rather than pointing "
                 "somewhere. Read the headline panel only where this one is high; the dashed "
                 "line marks 0.5."),
        source=src, log=log)


def phase_portraits(A, genes, label_key, out, sources_dir, plt, scv, colours, log=print):
    """Per-gene unspliced against spliced - the evidence the model fitted anything."""
    import pandas as pd
    genes = [g for g in genes if g in A.var_names][:6]
    if not genes:
        return None
    src = Path(sources_dir) / "F5_phase.csv"
    rows = {"barcode": A.obs_names.astype(str)}
    if label_key and label_key in A.obs:
        rows["label"] = A.obs[label_key].astype(str).values
    for g in genes:
        j = list(A.var_names).index(g)
        for lay, nm in (("Ms", "spliced_moment"), ("Mu", "unspliced_moment")):
            if lay in A.layers:
                col = A.layers[lay][:, j]
                rows[f"{g}_{nm}"] = (col.toarray().ravel() if hasattr(col, "toarray")
                                     else col.ravel())
    pd.DataFrame(rows).to_csv(src, index=False)
    try:
        ncol = 3
        nrow = (len(genes) + ncol - 1) // ncol
        fig, axs = plt.subplots(nrow, ncol, figsize=(figure.DOUBLE, 1.55 * nrow), squeeze=False)
        for ax, g in zip(axs.ravel(), genes):
            scv.pl.scatter(A, x="Ms", y="Mu", color=label_key, basis=g, ax=ax, show=False,
                           legend_loc="none", size=8, alpha=0.6, frameon=True,
                           title=g, fontsize=7, dpi=400,
                           palette=[colours[l] for l in sorted(colours)] if colours else None)
            figure.rasterize_points(ax)
            ax.set_xlabel("spliced (Ms)"), ax.set_ylabel("unspliced (Mu)")
        for ax in axs.ravel()[len(genes):]:
            ax.set_visible(False)
        return figure.save(
            fig, out, "F5_phase_portraits",
            caption=("Phase portraits for the highest-scoring velocity genes: unspliced against "
                     "spliced abundance, one point per cell. A gene above the steady-state "
                     "relation is being induced and one below is being repressed; that residual, "
                     "summed over genes, IS the velocity vector. A cloud with no structure means "
                     "the gene contributed nothing, whatever its rank."),
            source=src, log=log)
    except Exception as e:                                                # noqa: BLE001
        log(f"    F5_phase_portraits not drawn: {e}")
        return None


def transitions(rows, out, sources_dir, plt, colours, log=print):
    """Directed population-to-population flow - the stream, in numbers."""
    import numpy as np
    import pandas as pd
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("confidence", ascending=False).head(20)
    src = Path(sources_dir) / "F6_transitions.csv"
    pd.DataFrame(rows).to_csv(src, index=False)
    fig, ax = plt.subplots(figsize=(figure.SINGLE, max(1.6, 0.20 * len(df) + 0.8)))
    y = np.arange(len(df))
    ax.barh(y, df["confidence"], height=0.72,
            color=[(colours or {}).get(f, "#0072B2") for f in df["from"]])
    ax.set_yticks(y)
    ax.set_yticklabels([f"{a} → {b}" for a, b in zip(df["from"], df["to"])])
    ax.invert_yaxis()
    ax.set_xlabel("transition confidence")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    return figure.save(
        fig, out, "F6_transitions",
        caption=("Directed transitions between populations, from the velocity graph, strongest "
                 "first. Bars are coloured by the population the transition leaves. This is the "
                 "quantitative form of the stream panel: a direction visible there and absent "
                 "here is a direction within a population, not between them."),
        source=src, log=log)


def pseudotime(A, basis, out, sources_dir, plt, log=print):
    import numpy as np
    import pandas as pd
    pt = np.asarray(A.obs["velocity_pseudotime"], dtype=float)
    src = Path(sources_dir) / "F7_pseudotime.csv"
    pd.DataFrame({"barcode": A.obs_names.astype(str), "velocity_pseudotime": pt}).to_csv(
        src, index=False)
    xy = np.asarray(A.obsm[f"X_{basis}"])[:, :2]
    fig, ax = plt.subplots(figsize=(figure.SINGLE, figure.SINGLE * 0.9))
    sc = ax.scatter(xy[:, 0], xy[:, 1], c=pt, s=2, cmap="viridis", linewidths=0, rasterized=True)
    _clean(ax)
    cb = fig.colorbar(sc, ax=ax, fraction=0.04, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label("velocity pseudotime")
    return figure.save(
        fig, out, "F7_pseudotime",
        caption=("Velocity pseudotime: a diffusion ordering computed on the velocity graph, with "
                 "the root inferred from where the arrows point rather than chosen by hand. It is "
                 "an ORDER, not elapsed time, and it rests on more assumptions than the arrows "
                 "do - the published single-nucleus validation of velocity is directional and "
                 "did not extend to a pseudotime derived from it."),
        source=src, log=log)


def drivers(var_df, cols, out, sources_dir, plt, log=print):
    import numpy as np
    if not cols or var_df is None or not len(var_df):
        return None
    key = cols[0]
    d = var_df[[c for c in cols]].dropna(subset=[key]).sort_values(key, ascending=False).head(25)
    if not len(d):
        return None
    src = Path(sources_dir) / "F8_drivers.csv"
    d.to_csv(src)
    fig, ax = plt.subplots(figsize=(figure.SINGLE, max(1.6, 0.19 * len(d) + 0.8)))
    y = np.arange(len(d))
    ax.barh(y, d[key], height=0.72, color="#009E73")
    ax.set_yticks(y), ax.set_yticklabels(d.index)
    ax.invert_yaxis()
    ax.set_xlabel(key)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    return figure.save(
        fig, out, "F8_drivers",
        caption=(f"The genes carrying the field, ranked by {key}. These are the genes whose "
                 f"unspliced/spliced residual contributes most to the velocity vectors; a high "
                 f"rank means a gene drove the result, not that it is biologically important. "
                 f"Check them in the phase portraits before naming any of them in text."),
        source=src, log=log)
