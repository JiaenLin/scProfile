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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import figures as figs_mod                                                # noqa: E402
import sources                                                            # noqa: E402
from scprofile import figure, manifest                                    # noqa: E402

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
    "spliced_source": None,      # a path to search FIRST for spliced/unspliced counts
    "min_barcode_match": 0.5,    # a source matching fewer of a sample's barcodes is not used
}

#: Embeddings to project arrows onto, best first. An integrated embedding is preferred because
#: that is the manifold the annotation and the report already use - drawing velocity on a
#: different one gives two pictures of the same cells that cannot be laid side by side.
BASIS_PREFERENCE = ("umap", "scanvi", "scvi", "harmony", "umap_integrated", "tsne", "pca")


def _cpus(requested, resources=None):
    """How many workers to give the graph step.

    THE HOST'S ALLOCATION FIRST. `in.json['resources']['cores']` is this plugin's SHARE, divided
    by the scheduler across everything running concurrently. The machine's core count is the
    node's, and four plugins each reading it start four times the node's worth of threads - the
    usual symptom being a wave slower than running the same work serially.

    The environment variables are the fallback for a standalone invocation outside the harness,
    where nobody has allocated a share. The machine count is the last resort and is capped,
    because an uncapped guess on a shared node is the failure this function exists to avoid.
    """
    if requested:
        return int(requested)
    share = (resources or {}).get("cores")
    if share:
        return max(1, int(share))
    for var in ("NCPUS", "PBS_NCPUS", "SLURM_CPUS_PER_TASK", "OMP_NUM_THREADS"):
        v = os.environ.get(var)
        if v and v.isdigit() and int(v) > 0:
            return int(v)
    import multiprocessing
    return max(1, min(8, multiprocessing.cpu_count()))


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
    plt = figure.use()               # journal conventions, applied before anything is drawn
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
    n_jobs = _cpus(P["n_jobs"], inp.get("resources"))

    print(f"scvelo {scv.__version__}, mode {P['mode']}, {n_jobs} worker(s)")
    A = sc.read_h5ad(inp["h5ad"])
    n0, g0 = A.n_obs, A.n_vars
    print(f"read {n0:,} cells x {g0:,} genes")

    # ---------------------------------------------------------------- is there anything to fit
    #
    # An object that has been through QC, annotation and integration has almost certainly lost
    # its spliced/unspliced layers - they come from the aligner and nothing downstream carries
    # them. But the aligner's output is usually still on disk, and the upstream tools recorded
    # where their own inputs were. So before refusing, LOOK: the host passes the chain it
    # harvested from uns, and this searches it.
    have = set(manifest.layer_names(A))
    sourced_note = ""
    if not {"spliced", "unspliced"} <= have:
        print(f"spliced/unspliced are not on the object (layers: {sorted(have) or 'none'})")
        prov = inp.get("provenance") or {}
        roots = []
        if P["spliced_source"]:
            roots.append(str(P["spliced_source"]))
        roots += list(prov.get("search_paths") or [])
        roots.append(str(Path(inp["h5ad"]).parent))
        hints = list(prov.get("sample_hints") or [])
        if keys.get("sample") and keys["sample"] in A.obs:
            hints += [str(x) for x in A.obs[keys["sample"]].astype(str).unique()]
        hints = sorted(set(h for h in hints if h))

        print(f"searching {len(roots)} lead(s) for aligner output"
              + (f", {len(hints)} sample name(s) known" if hints else ""))
        cands = sources.find(roots, hints, log=print)
        print(f"  visited {sources.find.visited} director(ies), found {len(cands)} candidate(s)")
        ok = False
        if cands:
            ok, sourced_note = sources.attach(
                A, cands, sample_key=keys.get("sample"),
                min_match=float(P["min_barcode_match"]), log=print)
        if not ok:
            manifest.write_output(
                out, kernel="velocity", version=VERSION, status="refused",
                headline="no spliced/unspliced counts on the object or beside it",
                absent=[{"what": "velocity", "why":
                         "Spliced/unspliced counts come from the ALIGNER. They cannot be derived "
                         "from a counts matrix, and the only route is to re-quantify from FASTQ "
                         "or BAM in an intron-aware mode.\n"
                         f"  Present layers: {sorted(have) or 'none'}.\n"
                         f"  Searched {sources.find.visited} directories under "
                         f"{len(sources.find.looked)} lead(s) taken from the upstream chain:\n    "
                         + "\n    ".join(sources.find.looked[:8] or ["(none recorded)"])
                         + (f"\n  Candidates opened but not usable: {sourced_note}"
                            if sourced_note else "")
                         + "\n  Fix: --search <dir> to point at the aligner output, or "
                           "--params '{\"spliced_source\": \"<dir>\"}'."}],
                caveats=["Nothing was fitted."])
            print("REFUSED: no spliced/unspliced counts found")
            return 0
        have = set(manifest.layer_names(A))
        print(f"sourced from beside the object: {sourced_note}")

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

    # ---------------------------------------------------------------- start from COUNTS
    # The model is fitted on spliced/unspliced abundances, and X is used only for the HVG
    # selection and the PCA the neighbour graph is built on. An upstream tool typically delivers
    # lognormalised X with the counts kept in a layer - log1p applied to that would be a SECOND
    # log, which produces a perfectly plausible embedding and no error anywhere.
    counts_layer = keys.get("counts_layer")
    if counts_layer and counts_layer in have:
        A.X = A.layers[counts_layer].copy()
        x_src = f"layers[{counts_layer!r}], as named by the host"
    else:
        xmax = float(A.X.max())
        if xmax < 30:
            manifest.write_output(
                out, kernel="velocity", version=VERSION, status="refused",
                headline="X looks log-transformed and no counts layer was named",
                absent=[{"what": "velocity", "why":
                         f"X has maximum {xmax:.2f}, which is the range of log1p data rather than "
                         f"of counts, and no counts layer was named. Preprocessing it again would "
                         f"apply a second log transform - which produces a plausible embedding and "
                         f"reports no error.\n  Fix: --counts-layer <name>. Layers present: "
                         f"{sorted(have)}."}],
                caveats=["Nothing was fitted."])
            print("REFUSED: X looks logged and no counts layer was named")
            return 0
        x_src = f"X as delivered (max {xmax:.0f}, count-like)"
    print(f"counts from {x_src}")

    # ---------------------------------------------------------------- the fit
    # scvelo 0.3 REMOVED gene selection and the log transform from filter_and_normalize - it is
    # now filter_genes + normalize_per_cell and nothing else, though its own docstring still says
    # "Filtering, normalization and log transform". Passing n_top_genes reaches
    # normalize_per_cell through **kwargs and raises. The selection and the log are done here,
    # explicitly, where they can be counted and reported.
    scv.pp.filter_and_normalize(A, min_shared_counts=int(P["min_shared_counts"]))
    sc.pp.log1p(A)
    n_top = min(int(P["n_top_genes"]), A.n_vars)
    sc.pp.highly_variable_genes(A, n_top_genes=n_top, subset=True)
    g1 = A.n_vars
    # filter_and_normalize selects genes, not cells - this asserts that rather than trusting it.
    # The host now merges this array BY BARCODE, so a dropped cell would be reported as coverage
    # rather than misaligned; it is still not something this step is allowed to do silently,
    # because every obs column written below is aligned to the same names.
    if A.n_obs != n0:
        raise SystemExit(
            f"velocity: gene selection changed the CELL count, {n0:,} -> {A.n_obs:,}. Gene "
            f"selection must not drop cells. Refusing.")
    print(f"fitted on {g1:,} of {g0:,} genes "
          f"(min_shared_counts={P['min_shared_counts']}, n_top_genes={n_top})")
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
    trans_note, trows = "", []
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
    # The genes the phase portraits are drawn for: the highest-ranked by whichever score this
    # mode produced. Named here so the figure block and the table cannot disagree about them.
    top_genes = list(gv.index[:6]) if cols else []

    # ---------------------------------------------------------------- figures
    #
    # The set a velocity paper contains, not a sample of the result. Each panel is written as a
    # raster preview and a vector PDF with live text, at journal column width, with a caption
    # saying what it is FOR and the table it was drawn from beside it.
    fdir = out / "figures"
    sdir = out / "figures" / "source_data"
    sdir.mkdir(parents=True, exist_ok=True)
    labels = lab_series.values if lab_series is not None else None
    colours = figs_mod.colours_for(labels, sentinels) if labels is not None else {}
    print("figures:")
    figs = []

    def _add(x):
        if isinstance(x, list):
            figs.extend([y for y in x if y])
        elif x:
            figs.append(x)

    _add(figs_mod.proportions(A, labels, fdir, sdir, plt, log=print))
    _add(figs_mod.stream_and_grid(A, basis, label_key if lab_series is not None else None,
                                  fdir, sdir, plt, scv, colours, log=print))
    _add(figs_mod.confidence(A, labels, basis, fdir, sdir, plt, scv, colours, log=print))
    _add(figs_mod.phase_portraits(A, top_genes, label_key if lab_series is not None else None,
                                  fdir, sdir, plt, scv, colours, log=print))
    _add(figs_mod.transitions(trows, fdir, sdir, plt, colours, log=print))
    _add(figs_mod.pseudotime(A, basis, fdir, sdir, plt, log=print))
    _add(figs_mod.drivers(gv, cols, fdir, sdir, plt, log=print))

    # The per-population diagnostic pair: is there a direction here, and is there signal to build
    # it from? Kept because the pairing is the finding and two columns of numbers hide it.
    if len(by_label) and not by_label["velocity_confidence_median"].isna().all():
        d = by_label[~by_label["is_sentinel"]] if (~by_label["is_sentinel"]).any() else by_label
        fig, axs = plt.subplots(1, 2, figsize=(figure.DOUBLE, max(1.6, 0.20 * len(d) + 0.9)),
                                sharey=True)
        y = np.arange(len(d))
        axs[0].barh(y, d["velocity_confidence_median"], color="#0072B2", height=0.72)
        axs[0].axvline(float(P["min_confidence"]), color=figure.INK, ls="--", lw=0.6)
        axs[0].set_xlabel("velocity confidence (median)")
        axs[1].barh(y, d["unspliced_fraction"], color="#E69F00", height=0.72)
        axs[1].set_xlabel("unspliced fraction of fitted counts")
        axs[0].set_yticks(y), axs[0].set_yticklabels(d["label"])
        axs[0].invert_yaxis()
        for ax_ in axs:
            ax_.spines["left"].set_visible(False)
            ax_.tick_params(axis="y", length=0)
        figs.append(figure.save(
            fig, fdir, "F9_by_population",
            caption=("Per population, side by side: how much the arrows agree with their "
                     "neighbours, and how much unspliced signal there was to build them from. "
                     "The pairing is the point - a population low on both has no velocity to "
                     "read, and a population low on the left but high on the right has signal "
                     "the model could not resolve into a direction. Sentinel labels are excluded "
                     "from this panel."),
            source=f_bylabel, log=print))

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
    # THE HOST'S CONVENTION, not this plugin's. This wrote `obsm/barcodes.txt` - one file for the
    # directory, a name nothing in the host has ever looked for - so the barcodes existed and the
    # merge went on aligning by POSITION anyway. The host reads `<array>.barcodes.txt` beside the
    # array; `ctx.emit_obsm` writes exactly that for one-file plugins.
    f_bc = out / "obsm" / f"velocity_{basis}.barcodes.txt"
    f_bc.write_text("\n".join(map(str, A.obs_names)) + "\n", encoding="utf-8")

    # The fitted object, with its selected genes, its Ms/Mu/velocity layers and its velocity
    # graph. This is what `pseudotime` reads to orient itself, and what a user opens to plot a
    # phase portrait for a gene they care about.
    f_obj = out / "objects" / "velocity.h5ad"
    A.write_h5ad(f_obj, compression="gzip")
    print(f"wrote {f_obj.name}  ({A.n_obs:,} x {A.n_vars:,}, velocity graph included)")

    # ---------------------------------------------------------------- caveats, from the data
    caveats = []
    if sourced_note:
        caveats.append(
            "Spliced/unspliced counts were NOT on the input object. They were found beside it by "
            "following the provenance the upstream tools recorded, and attached BY BARCODE: "
            + sourced_note + ". Cells that matched no source carry zeros in those layers, which "
            "the fit treats as no signal - check the coverage above before reading the field.")
    caveats += [
        f"Fitted on {g1:,} of {g0:,} genes, selected inside this kernel from {x_src} "
        f"(min_shared_counts={P['min_shared_counts']}, n_top_genes={n_top}). No gene "
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
