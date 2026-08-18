#!/usr/bin/env python3
"""velocity - the DIRECTION of transcriptional change, from spliced and unspliced counts.

WHAT THIS KERNEL IS FOR, AND WHERE IT STOPS

Every other measurement in a single-cell dataset describes where a cell IS. Velocity is the only
one that says where it is GOING, and it does so from a fact of the chemistry: unspliced pre-mRNA
is transcribed before it is spliced, so a gene being switched on carries an unspliced excess and a
gene being switched off carries an unspliced deficit. Fit that per gene, and the residual points
along the cell's trajectory.

It stops at DIRECTION. Arrow length is not a rate in hours, and two datasets' arrows are not
comparable. Every one of the limits is declared in `kernel.yml` under `cannot_show` and printed
under this kernel's own results, so a reader meets them beside the figure rather than in a methods
section they will not open.

WHAT IT HANDS TO PSEUDOTIME, WHICH IS THE POINT OF RUNNING IT FIRST

A pseudotime built from expression alone is an AXIS WITHOUT AN ORIENTATION. Diffusion pseudotime
measures distance along the neighbour graph from a root cell, and the root is a decision - usually
an analyst pointing at the cluster they believe is the start. Velocity makes that decision from
the data: the arrows say which end is upstream.

So this kernel ships its fitted object, velocity graph included, as a side-car. The `pseudotime`
kernel reads it through `in.json`'s `upstream` and uses it to orient, and runs perfectly well
without it on the many datasets that have no unspliced counts - reporting an unoriented axis and
saying so.

`velocity_pseudotime` is written here as well, because it is nearly free once the graph exists and
because users expect it. Read it as the weaker of the two claims this kernel makes: the
single-nucleus validation in the literature is DIRECTIONAL - nucleus and cell velocities correlate
r 0.94-0.99 on matched populations - and that study projected vectors and measured cell speed. It
did not derive a pseudotime from them.

NOTHING IS REMOVED FROM THE DATASET HERE

Velocity is fitted on a selected gene set, because the model needs genes with enough unspliced
signal to fit. That selection is INTERNAL to this kernel: the merged object keeps every gene and
every cell, the counts printed below name exactly what the fit saw, and the fitted layers ship as
their own file rather than being padded back onto the full gene list - a zero in a `velocity`
layer would assert no change, when the truth is not fitted.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scprofile import manifest                                            # noqa: E402

VERSION = "0.1.0"

#: Defaults, all overridable with `--params '{"mode": "dynamical", ...}'`.
DEFAULTS = {
    "mode": "stochastic",        # stochastic | deterministic | dynamical
    "n_top_genes": 2000,
    "min_shared_counts": 20,
    "n_pcs": 30,
    "n_neighbors": 30,
    "basis": None,               # obsm key WITHOUT the X_ prefix; None = pick one
    "min_dist": 0.2,             # only used if a UMAP has to be computed here
    "n_jobs": None,
    "min_confidence": 0.5,       # below this median, the arrows are reported as unreadable
}

#: Embeddings to project arrows onto, best first. An integrated embedding is preferred because
#: that is the manifold the annotation and the report already use - drawing velocity on a
#: different one gives two pictures of the same cells that cannot be laid side by side.
BASIS_PREFERENCE = ("umap", "scanvi", "scvi", "harmony", "umap_integrated", "tsne", "pca")


def _cpus(requested):
    """How many workers to give the graph step, honouring the scheduler over the machine.

    A PBS job that asks for 8 cores and then starts 128 threads is oversubscribing a shared node,
    and the usual symptom is a job that is slower than the serial version.
    """
    if requested:
        return int(requested)
    for var in ("NCPUS", "PBS_NCPUS", "SLURM_CPUS_PER_TASK", "OMP_NUM_THREADS"):
        v = os.environ.get(var)
        if v and v.isdigit() and int(v) > 0:
            return int(v)
    return max(1, min(8, os.cpu_count() or 1))


def _pick_basis(A, declared, keys):
    """The 2-D space the arrows are drawn in, and a sentence saying how it was chosen."""
    have = {k[2:] if k.startswith("X_") else k: k for k in A.obsm}
    if declared:
        d = declared[2:] if declared.startswith("X_") else declared
        if d not in have:
            raise SystemExit(
                f"velocity: --params basis={declared!r} but obsm has {sorted(A.obsm)}.\n"
                f"  Fix: name one of those, or omit it and one will be chosen.")
        return d, f"declared in --params"
    named = keys.get("embedding")
    if named:
        d = named[2:] if named.startswith("X_") else named
        if d in have:
            return d, f"the embedding key the host detected ({named})"
    for cand in BASIS_PREFERENCE:
        if cand in have and A.obsm[have[cand]].shape[1] >= 2:
            return cand, f"first of {list(BASIS_PREFERENCE)} present in obsm"
    return None, "no 2-D embedding in obsm; one will be computed here"


def main(argv):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import scanpy as sc
    import scvelo as scv

    inp = manifest.read_input(argv[1] if len(argv) > 1 else os.environ["SCPROFILE_IN"])
    out = Path(inp["out_dir"])
    (out / "obs").mkdir(parents=True, exist_ok=True)
    (out / "obsm").mkdir(parents=True, exist_ok=True)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    (out / "objects").mkdir(parents=True, exist_ok=True)

    P = dict(DEFAULTS)
    P.update({k: v for k, v in (inp.get("params") or {}).items() if k in DEFAULTS})
    keys = inp["keys"]
    label_key = keys.get("label")
    assay = (inp.get("assay") or "").lower()
    sentinels = set(inp.get("sentinels") or ())
    n_jobs = _cpus(P["n_jobs"])

    print(f"scvelo {scv.__version__}, mode {P['mode']}, {n_jobs} worker(s)")
    A = sc.read_h5ad(inp["h5ad"])
    n0, g0 = A.n_obs, A.n_vars
    print(f"read {n0:,} cells x {g0:,} genes")

    # ---------------------------------------------------------------- is there anything to fit
    have = {k for k in A.layers if k is not None}
    absent = []
    for need in ("spliced", "unspliced"):
        if need not in have:
            absent.append({"what": "velocity", "why":
                           f"layers[{need!r}] is absent. Spliced/unspliced counts come from the "
                           f"ALIGNER - they cannot be derived from a counts matrix, and the only "
                           f"route is to re-quantify from FASTQ or BAM with an intron-aware "
                           f"mode. Present layers: {sorted(have) or 'none'}."})
    if absent:
        manifest.write_output(out, kernel="velocity", version=VERSION, status="refused",
                              headline="no spliced/unspliced layers on this object",
                              absent=absent, caveats=["Nothing was fitted."])
        print("REFUSED: no spliced/unspliced layers")
        return 0

    s_tot = float(A.layers["spliced"].sum())
    u_tot = float(A.layers["unspliced"].sum())
    u_frac = u_tot / (s_tot + u_tot) if (s_tot + u_tot) else 0.0
    print(f"unspliced is {100 * u_frac:.1f}% of spliced+unspliced counts")
    if u_tot <= 0:
        manifest.write_output(
            out, kernel="velocity", version=VERSION, status="refused",
            headline="the unspliced layer is present but empty",
            absent=[{"what": "velocity", "why":
                     "layers['unspliced'] sums to zero. The layer exists but carries no counts, "
                     "which usually means the quantification wrote the slot without an "
                     "intron-aware reference. There is no signal to fit."}],
            caveats=["Nothing was fitted."])
        print("REFUSED: unspliced layer is empty")
        return 0

    # ---------------------------------------------------------------- the fit
    scv.pp.filter_and_normalize(A, min_shared_counts=int(P["min_shared_counts"]),
                                n_top_genes=int(P["n_top_genes"]))
    g1 = A.n_vars
    # The host merges obsm BY POSITION, so a step that dropped cells would misalign every arrow
    # against every barcode and nothing downstream would notice. filter_and_normalize selects
    # genes, not cells - this asserts that rather than trusting it.
    if A.n_obs != n0:
        raise SystemExit(
            f"velocity: gene selection changed the CELL count, {n0:,} -> {A.n_obs:,}. The host "
            f"merges obsm by position and this would silently misalign it. Refusing.")
    print(f"fitted on {g1:,} of {g0:,} genes "
          f"(min_shared_counts={P['min_shared_counts']}, n_top_genes={P['n_top_genes']})")
    if g1 < 50:
        manifest.write_output(
            out, kernel="velocity", version=VERSION, status="refused",
            headline=f"only {g1} genes survived selection",
            absent=[{"what": "velocity", "why":
                     f"only {g1} of {g0} genes had at least {P['min_shared_counts']} shared "
                     f"spliced+unspliced counts. A velocity fitted on that many genes is noise. "
                     f"Lower min_shared_counts if the libraries are shallow, but a fit this thin "
                     f"is usually telling you the unspliced quantification is sparse."}],
            caveats=["Nothing was fitted."])
        print("REFUSED: too few genes survived selection")
        return 0

    scv.pp.moments(A, n_pcs=int(P["n_pcs"]), n_neighbors=int(P["n_neighbors"]))
    if P["mode"] == "dynamical":
        print("fitting the dynamical model - this is the slow mode, minutes to hours")
        scv.tl.recover_dynamics(A, n_jobs=n_jobs)
    scv.tl.velocity(A, mode=P["mode"])
    scv.tl.velocity_graph(A, n_jobs=n_jobs)
    scv.tl.velocity_confidence(A)
    scv.tl.velocity_pseudotime(A)
    if P["mode"] == "dynamical":
        scv.tl.latent_time(A)

    conf = np.asarray(A.obs["velocity_confidence"], dtype=float)
    length = np.asarray(A.obs["velocity_length"], dtype=float)
    med_conf = float(np.nanmedian(conf))
    print(f"velocity_confidence: median {med_conf:.3f}, "
          f"{100 * float(np.mean(conf < 0.3)):.1f}% of cells below 0.3")

    # ---------------------------------------------------------------- where to draw the arrows
    basis, why_basis = _pick_basis(A, P["basis"], keys)
    if basis is None:
        print(f"computing a UMAP for the arrows (min_dist={P['min_dist']})")
        sc.pp.neighbors(A, n_neighbors=int(P["n_neighbors"]), n_pcs=int(P["n_pcs"]))
        sc.tl.umap(A, min_dist=float(P["min_dist"]))
        basis, why_basis = "umap", f"computed here at min_dist={P['min_dist']}"
    print(f"basis: X_{basis}  ({why_basis})")
    scv.tl.velocity_embedding(A, basis=basis)

    # ---------------------------------------------------------------- per label, sentinels aside
    rows, lab_series = [], None
    if label_key and label_key in A.obs:
        lab_series = A.obs[label_key].astype(str)
        for lab, idx in lab_series.groupby(lab_series).groups.items():
            m = lab_series.index.isin(idx)
            su = float(A.layers["Mu"][m].sum()) if "Mu" in A.layers else float("nan")
            ss = float(A.layers["Ms"][m].sum()) if "Ms" in A.layers else float("nan")
            rows.append({
                "label": lab,
                "is_sentinel": lab in sentinels,
                "n_cells": int(m.sum()),
                "velocity_confidence_median": float(np.nanmedian(conf[m])),
                "velocity_length_median": float(np.nanmedian(length[m])),
                "velocity_pseudotime_median":
                    float(np.nanmedian(A.obs["velocity_pseudotime"].values[m])),
                "unspliced_fraction": (su / (ss + su)) if (ss + su) > 0 else float("nan"),
            })
        rows.sort(key=lambda r: (r["is_sentinel"], -r["n_cells"]))
    by_label = pd.DataFrame(rows)
    f_bylabel = out / "tables" / "velocity_by_label.csv"
    by_label.to_csv(f_bylabel, index=False)

    # ---------------------------------------------------------------- directed label transitions
    # This is the table the `pseudotime` kernel and a reader both want: not "these cells move" but
    # "this population moves TOWARD that one". It is also the honest place to see that a direction
    # is absent - a symmetric transition matrix means the arrows carry no between-label signal.
    tables = [f_bylabel]
    trans_note = ""
    if lab_series is not None and lab_series.nunique() > 1:
        try:
            scv.tl.paga(A, groups=label_key)
            tr = A.uns["paga"]["transitions_confidence"]
            tr = np.asarray(tr.todense()) if hasattr(tr, "todense") else np.asarray(tr)
            cats = list(pd.Categorical(lab_series).categories)
            trows = [{"from": cats[i], "to": cats[j], "confidence": float(tr[i, j])}
                     for i in range(len(cats)) for j in range(len(cats))
                     if i != j and float(tr[i, j]) > 0]
            trows.sort(key=lambda r: -r["confidence"])
            f_tr = out / "tables" / "velocity_transitions.csv"
            pd.DataFrame(trows).to_csv(f_tr, index=False)
            tables.append(f_tr)
            trans_note = (f"{len(trows)} directed label transition(s); strongest "
                          + ", ".join(f"{r['from']} -> {r['to']} ({r['confidence']:.2f})"
                                      for r in trows[:3])) if trows else \
                "no directed transition between labels survived - the arrows carry within-label " \
                "structure but no between-label direction"
            print(f"transitions: {trans_note}")
        except Exception as e:                                            # noqa: BLE001
            print(f"  PAGA transitions not computed: {e}")

    # ---------------------------------------------------------------- driver genes
    if "fit_likelihood" in A.var:
        gv = A.var.sort_values("fit_likelihood", ascending=False)
        cols = [c for c in ("fit_likelihood", "fit_alpha", "fit_beta", "fit_gamma",
                            "velocity_score") if c in gv]
    else:
        if lab_series is not None:
            try:
                scv.tl.rank_velocity_genes(A, groupby=label_key, min_corr=0.3)
            except Exception as e:                                        # noqa: BLE001
                print(f"  rank_velocity_genes skipped: {e}")
        gv = (A.var.sort_values("velocity_score", ascending=False)
              if "velocity_score" in A.var else A.var)
        cols = [c for c in ("velocity_score", "velocity_gamma", "velocity_r2") if c in gv]
    f_genes = out / "tables" / "velocity_genes.csv"
    gv[cols].head(500).to_csv(f_genes)
    tables.append(f_genes)

    # ---------------------------------------------------------------- figures
    figs = []
    scv.settings.figdir = str(out / "figures")
    try:
        ax = scv.pl.velocity_embedding_stream(
            A, basis=basis, color=label_key if lab_series is not None else None,
            legend_loc="right margin", dpi=140, show=False,
            title=f"velocity on X_{basis}   —   DIRECTION only; arrow length is not a rate")
        f = out / "figures" / "velocity_stream.png"
        ax.figure.savefig(f, dpi=140, bbox_inches="tight"); plt.close(ax.figure)
        figs.append(f)
    except Exception as e:                                                # noqa: BLE001
        print(f"  stream plot not drawn: {e}")

    try:
        ax = scv.pl.scatter(A, basis=basis, color="velocity_confidence", cmap="coolwarm",
                            show=False, dpi=140,
                            title="velocity_confidence   —   grey-blue means the arrows here "
                                  "disagree with their neighbours")
        f = out / "figures" / "velocity_confidence.png"
        ax.figure.savefig(f, dpi=140, bbox_inches="tight"); plt.close(ax.figure)
        figs.append(f)
    except Exception as e:                                                # noqa: BLE001
        print(f"  confidence plot not drawn: {e}")

    # Confidence beside unspliced fraction, per label. The pairing is the point: a population whose
    # arrows are unconfident AND whose unspliced fraction is low has no velocity to read, and a bar
    # chart says that in one glance where two columns of numbers do not.
    if len(by_label) and not by_label["velocity_confidence_median"].isna().all():
        d = by_label[~by_label["is_sentinel"]] if (~by_label["is_sentinel"]).any() else by_label
        h = max(2.6, 0.34 * len(d) + 1.4)
        fig, axs = plt.subplots(1, 2, figsize=(10.5, h), sharey=True)
        y = np.arange(len(d))
        axs[0].barh(y, d["velocity_confidence_median"], color="#4f81bd")
        axs[0].axvline(float(P["min_confidence"]), color="#1a1a1a", ls="--", lw=1)
        axs[0].set_title(f"velocity_confidence (median)   dashed = {P['min_confidence']}",
                         fontsize=9, loc="left")
        axs[1].barh(y, d["unspliced_fraction"], color="#9bbb59")
        axs[1].set_title("unspliced fraction of the fitted counts", fontsize=9, loc="left")
        axs[0].set_yticks(y); axs[0].set_yticklabels(d["label"], fontsize=8)
        axs[0].invert_yaxis()
        for ax_ in axs:
            ax_.spines[["top", "right"]].set_visible(False)
        fig.suptitle("Per population: is there a direction here, and is there signal to build it "
                     "from?", fontsize=10, x=.01, ha="left")
        f = out / "figures" / "velocity_by_label.png"
        fig.savefig(f, dpi=140, bbox_inches="tight"); plt.close(fig)
        figs.append(f)

    try:
        ax = scv.pl.scatter(A, basis=basis, color="velocity_pseudotime", cmap="gnuplot",
                            show=False, dpi=140,
                            title="velocity_pseudotime   —   ORDER, not elapsed time")
        f = out / "figures" / "velocity_pseudotime.png"
        ax.figure.savefig(f, dpi=140, bbox_inches="tight"); plt.close(ax.figure)
        figs.append(f)
    except Exception as e:                                                # noqa: BLE001
        print(f"  pseudotime plot not drawn: {e}")

    # ---------------------------------------------------------------- what the host merges
    written_obs = {}
    cols = ["velocity_confidence", "velocity_length", "velocity_pseudotime"]
    if "latent_time" in A.obs:
        cols.append("latent_time")
    for col in cols:
        f = out / "obs" / f"{col}.csv"
        pd.DataFrame({"barcode": A.obs_names.astype(str),
                      col: np.asarray(A.obs[col])}).to_csv(f, index=False)
        written_obs[col] = f

    f_emb = out / "obsm" / f"velocity_{basis}.npy"
    np.save(f_emb, np.asarray(A.obsm[f"velocity_{basis}"], dtype="float32"))
    f_bc = out / "obsm" / "barcodes.txt"
    f_bc.write_text("\n".join(map(str, A.obs_names)), encoding="utf-8")

    # The fitted object, with its selected genes, its Ms/Mu/velocity layers and its velocity
    # graph. This is what `pseudotime` reads to orient itself, and what a user opens to plot a
    # phase portrait for a gene they care about.
    f_obj = out / "objects" / "velocity.h5ad"
    A.write_h5ad(f_obj, compression="gzip")
    print(f"wrote {f_obj.name}  ({A.n_obs:,} x {A.n_vars:,}, velocity graph included)")

    # ---------------------------------------------------------------- caveats, from the data
    caveats = [
        f"Fitted on {g1:,} of {g0:,} genes, selected inside this kernel "
        f"(min_shared_counts={P['min_shared_counts']}, n_top_genes={P['n_top_genes']}). No gene "
        f"or cell was removed from the merged object; the fitted layers ship as "
        f"objects/velocity.h5ad rather than being padded onto the full gene list, because a zero "
        f"in a velocity layer would assert no change where the truth is not fitted.",
        f"Mode {P['mode']}. Arrows are a DIRECTION: length is not a rate in real time, and "
        f"lengths from two datasets are not comparable.",
        f"Arrows are drawn on X_{basis} ({why_basis}). A velocity embedding is a projection - "
        f"the fit happens in gene space, and a projection can make a coherent field look "
        f"incoherent if the 2-D layout tore the manifold.",
    ]
    status = "ok"
    if med_conf < float(P["min_confidence"]):
        status = "partial"
        caveats.insert(0,
            f"MEDIAN velocity_confidence is {med_conf:.3f}, below {P['min_confidence']}. Each "
            f"cell's arrow largely disagrees with its neighbours', so the field should be read as "
            f"unresolved rather than as a direction. Do not draw a trajectory from it.")
    if assay == "nucleus":
        caveats.append(
            f"Single-NUCLEUS data, unspliced {100 * u_frac:.1f}% of counts. The high intronic "
            f"fraction is expected and helps the fit. Validated use is DIRECTIONAL - nucleus and "
            f"cell velocities correlate r 0.94-0.99 on matched populations (Sci Rep 2024) - and "
            f"that comparison did not cover a pseudotime derived from the arrows.")
    elif assay == "cell":
        caveats.append(
            f"Whole cells, unspliced {100 * u_frac:.1f}% of counts. For 3-prime tagging "
            f"chemistries the unspliced counts are sparse and the per-gene fits are noisy.")
    if sentinels and lab_series is not None:
        n_sent = int(lab_series.isin(sentinels).sum())
        if n_sent:
            caveats.append(
                f"{n_sent:,} cells carry an annotator sentinel ({', '.join(sorted(sentinels))}). "
                f"They were fitted like any other cell - nothing was dropped - but they are "
                f"excluded from the per-population table's ordering and from the bar figure, "
                f"because a sentinel is not a cell type.")
    if trans_note:
        caveats.append("Directed transitions between labels are in "
                       "tables/velocity_transitions.csv. " + trans_note + ".")

    manifest.write_output(
        out, kernel="velocity", version=VERSION, status=status,
        headline=f"velocity fitted on {g1:,} genes ({P['mode']}); median confidence "
                 f"{med_conf:.2f}; unspliced {100 * u_frac:.1f}% of counts",
        obs=written_obs,
        obsm={f"velocity_{basis}": f_emb},
        objects={"velocity_h5ad": f_obj},
        tables=tables, figures=figs, caveats=caveats)
    print("wrote out.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
