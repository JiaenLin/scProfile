"""Regulon activity per cell, from a network inferred from this dataset rather than a prior.

CO-EXPRESSION WITH A MOTIF IS NOT REGULATION. Nothing here observes a perturbation, so no edge
is causal. And the whole method rests on a lookup: GRNBoost2 proposes modules, and cisTarget
PRUNES them against motif rankings. Without the rankings nothing is pruned, every co-expression
module survives, and the regulons returned are raw correlation wearing a regulon's name — a full
result file, and wrong. That is why the reference data is a required capability.
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "summary": "regulon activity per cell, from a network inferred from your own data",
    "when_to_use": "you want a gene regulatory network from this dataset rather than a prior",
    "wraps": {"tool": "pyscenic", "homepage": "https://pyscenic.readthedocs.io",
              "license": "GPL-3.0",
              "cite": "Aibar et al., Nat Methods 2017 (SCENIC); "
                      "Van de Sande et al., Nat Protoc 2020 (pySCENIC)"},
    "upstream": {
        "docs": "https://pyscenic.readthedocs.io",
        "read": "2026-08-22",
        "defaults_changed": [
            "grnboost2 is given an explicit seed and a local client. Its default spins up a "
            "dask cluster sized to the machine, which on a shared node is the os.cpu_count() "
            "mistake wearing a scheduler.",
            "The TF list is passed explicitly from the declared reference. Left out, GRNBoost2 "
            "treats every gene as a candidate regulator and the run takes hours longer to "
            "produce a worse network.",
        ],
        "not_used": [
            "The AUCell binarisation step. A threshold per regulon is a decision about what "
            "counts as 'on' and belongs to whoever reads the matrix.",
            "Multi-runs and the consensus regulon set: the right answer for a published network "
            "and a different, much more expensive plugin.",
        ],
        "gotchas": [
            "GRNBoost2 returns an EMPTY adjacency table rather than failing when arboreto and "
            "the installed dask disagree about the scheduler. Empty is checked for explicitly, "
            "because downstream it reads as 'no regulons found'.",
            "The cisTarget rankings are organism-specific and this plugin refuses an organism it "
            "has no rankings for rather than pruning against the wrong species.",
            "AUC IS A WITHIN-EXPERIMENT QUANTITY. The SCENIC protocol states that AUC values may "
            "only be used to compare a regulon's activity across cells of the SAME experiment "
            "(Van de Sande et al., Nat Protoc 2020), and the regulon set is itself inferred per "
            "fit - so two per-sample fits do not even share a vocabulary. This plugin therefore "
            "runs per sample AND once over the cohort, and each result says which it is.",
            "There is no upstream guidance on the multi-sample case. The SCENIC maintainers' "
            "thread on comparing AUC across sequencing runs is still unanswered "
            "(aertslab/SCENIC discussion #317), and the single-cell best-practices GRN chapter "
            "demonstrates on ONE donor, explicitly 'due to batch integration considerations' "
            "(sc-best-practices.org). Absence of guidance is why the two scopes are declared "
            "here rather than left to whoever runs it.",
            "A COHORT FIT LEARNS THE BATCH. GRNBoost2 has no notion of design: pooled across "
            "samples it will happily encode co-expression driven by batch or chemistry as "
            "regulation. Where the object carries an upstream constraint on use, the cohort fit "
            "reproduces it verbatim rather than refusing - the vocabulary is still correct for "
            "every comparison the constraint does not name.",
        ],
    },

    "inject": {"required": ["counts", "organism"], "optional": ["label", "sample"]},
    "provides": ["activity"],
    # `?` on both: the cell-level block comes from the COHORT fit and the per-cell table from a
    # PER-SAMPLE fit, so each run makes one of them and never both.
    "produces": ["obsm[X_regulon_auc]?", "tables/regulon_auc.csv?", "tables/regulon_targets.csv",
                 # cohort fit only - the aggregate a between-condition test should read
                 "tables/regulon_activity_by_sample.csv?"],
    "per_unit": "sample",
    # AND ONCE OVER THE WHOLE COHORT, because a regulon set is INFERRED, not fixed. Each fit
    # discovers its own vocabulary, so two units' AUC columns are not the same quantity and a
    # between-condition comparison built from them compares different things. Measured on ten
    # a ten-sample cohort: 37 to 111 regulons per sample, and two samples shared 17% of
    # their transcription factors (Jaccard 0.17).
    #
    # The per-sample fits are KEPT and are not redundant - they are the only independent check on
    # the pooled one, and a regulon recovered in most samples separately is far stronger evidence
    # than one from a single pooled fit that nothing corroborates.
    "also_cohort": {
        "why": "regulon membership is inferred per fit, so per-sample AUC columns are not the "
               "same quantity. One cohort fit yields ONE regulon vocabulary, which is what a "
               "between-condition comparison of regulon activity requires.",
    },

    # REFERENCE DATA, WITH ITS DIGESTS. Recovered from the directory shape rather than
    # re-derived: the vendor publishes no checksums, so each of these came from a completed
    # download (PBS 676356 mouse, 676454 human), was confirmed by `sha256sum` as a second
    # implementation, and was checked for content - Arrow magic at BOTH ends, and 93% of each TF
    # list present as columns of its own ranking. A digest is only ever as good as the download
    # it came from, and re-deriving these would have thrown that away.
    #
    # Source: resources.aertslab.org, the SCENIC authors' own distribution. The cisTarget
    # databases are distributed for research use; the motif collection derives from JASPAR,
    # HOCOMOCO, SwissRegulon and others.
    "references": {
        "mm10_rankings_10kb": {
            "organism": "mouse", "role": "rankings",
            "url": "https://resources.aertslab.org/cistarget/databases/mus_musculus/mm10/"
                   "refseq_r80/mc_v10_clust/gene_based/"
                   "mm10_10kbp_up_10kbp_down_full_tx_v10_clust.genes_vs_motifs.rankings.feather",
            "sha256": "8fc014f1879355a5e94b155f8b55511e3b47842cceed9d3e17235f60afb85ebc",
            "size": 237172098},
        "mm10_motif2tf": {
            "organism": "mouse", "role": "motif2tf",
            "url": "https://resources.aertslab.org/cistarget/motif2tf/"
                   "motifs-v10nr_clust-nr.mgi-m0.001-o0.0.tbl",
            "sha256": "5b64aad9df9804d50c50484c92d5192bdd5d2056cb105bdd343c0af2f94cce83",
            "size": 113107706},
        "mm_tfs": {
            "organism": "mouse", "role": "tfs",
            "url": "https://resources.aertslab.org/cistarget/tf_lists/allTFs_mm.txt",
            "sha256": "17a95e142147fb7dc063d7b9e84262746b0b64f622793b3cc5df0eddf2f1194c",
            "size": 11726},
        "hg38_rankings_10kb": {
            "organism": "human", "role": "rankings",
            "url": "https://resources.aertslab.org/cistarget/databases/homo_sapiens/hg38/"
                   "refseq_r80/mc_v10_clust/gene_based/"
                   "hg38_10kbp_up_10kbp_down_full_tx_v10_clust.genes_vs_motifs.rankings.feather",
            "sha256": "9c4026a3a8e25fe07cf96749644e2ca028b787410829b30b9932574dc6e78bdb",
            "size": 311298530},
        "hg38_motif2tf": {
            "organism": "human", "role": "motif2tf",
            "url": "https://resources.aertslab.org/cistarget/motif2tf/"
                   "motifs-v10nr_clust-nr.hgnc-m0.001-o0.0.tbl",
            "sha256": "81eb754118e27e854974301b1400fcf519489f8be5249239671fb288cb501c31",
            "size": 98718421},
        # allTFs_hs.txt is a 404: the vendor names this file after the ASSEMBLY, not the species,
        # and nothing would have caught it except fetching it.
        "hs_tfs": {
            "organism": "human", "role": "tfs",
            "url": "https://resources.aertslab.org/cistarget/tf_lists/allTFs_hg38.txt",
            "sha256": "3953034f84112c60d3d8ef15b0e0c8ac5fce0b40d2c7c0824c2945c70cee2523",
            "size": 11690},
    },

    "config": {
        "min_genes_per_regulon": {"type": "int", "default": 10, "min": 1,
                                  "help": "regulons with fewer targets are dropped; a regulon of "
                                          "three genes is a correlation, not a module"},
        "seed": {"type": "int", "default": 0,
                 "help": "GRNBoost2 is stochastic; this is what makes a run reproducible"},
        "cohort_max_cells": {"type": "int", "default": 25000, "min": 0,
                             "help": "the COHORT fit infers its network from at most this many "
                                     "cells, balanced across samples. GRNBoost2 holds the matrix "
                                     "dense and thrashes above ~50k; the estimate stabilises far "
                                     "below that. 0 fits on all cells. Per-sample fits ignore "
                                     "this - they are already small"},
        "min_cells_per_gene": {"type": "int", "default": 3, "min": 0,
                               "help": "a gene detected in fewer cells than this is not offered "
                                       "as a TARGET. It is never removed from the object, never "
                                       "removed as a REGULATOR, and 0 disables the filter. A gene "
                                       "seen in two cells cannot support a regression across "
                                       "thousands, and every one of them costs a full fit"},
    },

    "requires": {
        # EXACT PINS, DELIBERATELY. Stated once here rather than defended nine times: every
        # other plugin in this tree should prefer ranges, and this one must not.
        "exact_pins_why":
            "pySCENIC 0.12.1 is built on dask's distributed scheduler and the releases it was "
            "written against predate the pandas 2 copy-on-write changes. Resolved loose, "
            "arboreto's scatter path shifts underneath it and GRNBoost2 returns an EMPTY "
            "adjacency table rather than failing - a network with no edges, which reads "
            "downstream as 'no regulons found'. This is an older, self-consistent island and it "
            "cannot share an environment with anything modern.",
        "python": ">=3.10,<3.11",
        "packages": {"pyscenic": "==0.12.1", "numpy": "==1.23.5", "pandas": "==1.5.3",
                     "dask": "==2023.5.0", "distributed": "==2023.5.0",
                     "pyarrow": "==11.0.0", "setuptools": "==75.8.2",
                     "arboreto": "==0.1.6", "ctxcore": "==0.2.0",
                     # THE CONTRACT NEEDS IT. `_entry.py` reads the object with
                     # `anndata.read_h5ad` before this plugin sees anything, so an environment
                     # without anndata cannot run ANY plugin - and this one did not have it.
                     # Measured on PBS 677677: every one of ten units reported
                     # `NOT RUN scenic[...]  scenic's interpreter cannot read this object even
                     # re-encoded`, whose cause was `ModuleNotFoundError: No module named
                     # 'anndata'`. A RANGE, not a pin: this is the contract's dependency, not
                     # pySCENIC's, and nothing here calls it.
                     "anndata": ">=0.9,<0.11"},
    },

    "cost": "high", "cores": 16,
    # DERIVED FROM THE MATRIX THIS METHOD HOLDS, then rounded UP. GRNBoost2 keeps the expression
    # frame DENSE: 100k cells x ~28k retained genes x 4 bytes is ~11 GB, and dask's task graph,
    # its scatter copies and the garbage it generates carry that to roughly 3-4x in practice.
    # 40 is that arithmetic rounded up, not a measurement, and it is deliberately generous - PBS
    # 680454 showed what the other direction costs: six hours at 85% of CPU in garbage
    # collection, eight lines of progress, nothing kept.
    # TWO TERMS. The 40 declared before was a pure rate, which charges a 13k-cell per-sample fit
    # for a baseline it pays anyway and charges the cohort fit as though it did not. The dense
    # frame is the per-cell half; the interpreter, dask's scheduler and the loaded rankings are
    # the fixed half. Still rounded up - see `UNDECLARED_GB_BASE` on why the two directions are
    # not symmetric.
    "memory_gb_base": 8, "memory_gb_per_100k": 32,

    "cannot_show": [
        "CO-EXPRESSION WITH A MOTIF IS NOT REGULATION. Nothing here observes a perturbation, so "
        "no edge is causal.",
        "Benchmarks recover very different numbers of TFs from the same data, so a single GRN "
        "result should not be reported alone.",
        "A network inferred from pooled conditions describes the average of them and may describe "
        "neither, which is why this runs per sample.",
        "An absent regulon is not evidence of an inactive TF: it may simply not have had enough "
        "expressed targets in this unit.",
    ],
}


def run(ctx):
    import numpy as np
    import pandas as pd
    from arboreto.algo import grnboost2
    from pyscenic.utils import modules_from_adjacencies
    from pyscenic.prune import prune2df, df2regulons
    from pyscenic.aucell import aucell
    from ctxcore.rnkdb import FeatherRankingDatabase

    # BY ROLE, not by name. The mouse and human entries are different files with different
    # names; the plugin asks for "the rankings" and the host hands over the ones for this
    # organism, so this code does not name a species anywhere.
    rank_path = ctx.reference_for_role("rankings")
    tf_path = ctx.reference_for_role("tfs")
    m2t_path = ctx.reference_for_role("motif2tf")
    if not (rank_path and tf_path and m2t_path):
        return ctx.refuse(
            "regulon activity",
            "the cisTarget references are not available. Without them nothing is pruned, every "
            "co-expression module survives, and the regulons are raw correlation wearing a "
            "regulon's name - a full result file, and wrong.")

    counts = ctx.counts()
    genes = np.asarray(ctx.adata.var_names).astype(str)
    obs_names = np.asarray(ctx.adata.obs_names).astype(str)
    tfs = [l.strip() for l in open(tf_path, encoding="utf-8") if l.strip()]
    present = [t for t in tfs if t in set(genes)]

    # THE COHORT FIT SUBSAMPLES, AND IT HAS TO. GRNBoost2 holds the expression matrix DENSE and
    # ships it through a dask graph: 98,627 cells x 27,812 genes is an 11 GB frame, and measured
    # on PBS 680454 the fit spent SIX HOURS at 85% of CPU time in garbage collection, producing
    # eight lines of progress. It does not fail - it thrashes, which is worse, because a job that
    # is 3% productive looks exactly like a job that is merely slow.
    #
    # A regulatory relationship is estimated from co-expression ACROSS cells and the estimate
    # stabilises long before 100k of them; the per-sample fits recovered 37-111 regulons from
    # 13,824 cells apiece in about 52 minutes. The cap is therefore a tractability choice with a
    # statistical justification, not a shortcut, and `cohort_max_cells: 0` disables it.
    #
    # BALANCED BY SAMPLE, not proportional. The cohort fit exists to produce ONE vocabulary that
    # every condition is scored against; sampling proportionally would let whichever animal
    # yielded most nuclei write more of that vocabulary than the others. Every sample contributes
    # the same number of cells, and the ones with fewer contribute all they have.
    cap = int(ctx.config["cohort_max_cells"])
    fit_rows = None                       # None = fit on every cell, which is the per-unit case
    if PLUGIN.get("per_unit") and ctx.unit is None and cap and counts.shape[0] > cap:
        rng = np.random.default_rng(ctx.config["seed"])
        if "sample" in ctx.keys:
            samp = ctx.obs("sample").astype(str).to_numpy()
            groups = sorted(set(samp))
            per = max(1, cap // len(groups))
            pick = []
            for g in groups:
                idx = np.flatnonzero(samp == g)
                pick.append(idx if len(idx) <= per
                            else rng.choice(idx, size=per, replace=False))
            take = np.sort(np.concatenate(pick))
            how = f"balanced across {len(groups)} sample(s), up to {per:,} cells each"
        else:
            take = np.sort(rng.choice(counts.shape[0], size=cap, replace=False))
            how = "at random; no sample key was available to balance across"
        fit_rows = take
        ctx.log(f"  cohort fit subsampled {counts.shape[0]:,} -> {len(take):,} cells ({how})")
        ctx.caveat(
            f"THE COHORT NETWORK WAS INFERRED FROM A SUBSAMPLE: {len(take):,} of "
            f"{counts.shape[0]:,} cells, {how}, seed {ctx.config['seed']}. No cell was removed "
            f"from the object and AUC IS SCORED FOR EVERY CELL - only the network INFERENCE saw "
            f"the subsample. A regulon absent here may be one the subsample had too few cells to "
            f"support. Set cohort_max_cells to 0 to fit on all cells.")

    # TARGETS ONLY, AND REGULATORS ARE NEVER DROPPED. A gene detected in a handful of cells cannot
    # support a boosted regression over thousands of them, and GRNBoost2 fits EVERY column as a
    # target - so an undetected gene costs a full fit to return noise. Restricting targets is
    # standard SCENIC practice; doing it silently would not be, so the count is logged, the gene
    # stays in the object, and `min_cells_per_gene: 0` turns it off.
    #
    # A TF is exempt whatever its detection rate: it is a REGRESSOR, dropping it removes an
    # explanation rather than a cost, and nothing downstream could recover the regulon it would
    # have carried.
    # DETECTION IS COUNTED ON THE CELLS THAT WILL BE FIT. Counting it on cells the regression
    # never sees would offer targets the fit has no evidence for.
    fit_counts = counts if fit_rows is None else counts[fit_rows, :]
    fit_names = obs_names if fit_rows is None else obs_names[fit_rows]
    detected = np.asarray((fit_counts > 0).sum(axis=0)).ravel()
    floor = int(ctx.config["min_cells_per_gene"])
    keep = detected >= floor if floor else np.ones(len(genes), bool)
    keep |= np.isin(genes, list(present))
    dropped = int((~keep).sum())

    sub = fit_counts[:, keep]
    kept_genes = genes[keep]
    # float32 HALVES the graph dask ships to its workers. GRNBoost2 splits on ordering, and no
    # split in a boosted tree over UMI counts turns on the 8th decimal place.
    dense = np.asarray(sub.todense() if hasattr(sub, "todense") else sub, dtype=np.float32)
    ex = pd.DataFrame(dense, index=pd.Index(fit_names, name="cell"), columns=kept_genes)
    ctx.log(f"{ex.shape[0]:,} cells x {ex.shape[1]:,} genes; "
            f"{len(present):,} of {len(tfs):,} declared TFs present")
    if dropped:
        ctx.log(f"  {dropped:,} gene(s) not offered as targets: detected in fewer than {floor} "
                f"cell(s) here. They remain in the object and every TF was kept regardless.")
        ctx.caveat(f"{dropped:,} of {len(genes):,} genes were not offered to GRNBoost2 as TARGETS "
                   f"(detected in fewer than {floor} cells in this unit). No regulon can name one "
                   f"of them as a target here. They were NOT removed from the object and were NOT "
                   f"removed as regulators; set min_cells_per_gene to 0 to offer all of them.")
    if len(present) < 10:
        return ctx.refuse("regulon activity",
                          f"only {len(present)} of {len(tfs):,} transcription factors from the "
                          f"{ctx.organism} list are in this object. That is a gene-NAMING "
                          f"mismatch, not a biological result.")

    # THE ALLOCATED SHARE, NOT THE MACHINE'S. `client_or_address="local"` makes arboreto build a
    # LocalCluster sized from `multiprocessing.cpu_count()` - the NODE - so this plugin, which
    # runs once per sample, starts the node's worth of workers per sample. Ten instances on one
    # node is ten times the machine in dask workers, and the symptom is a wave slower than running
    # the same work serially. `ctx.effect` releases the client on every exit path including a
    # raise, which is the case a `finally` written in a hurry gets wrong.
    from distributed import Client, LocalCluster
    client = ctx.effect(
        lambda: Client(LocalCluster(n_workers=max(1, int(ctx.cores)), threads_per_worker=1,
                                    processes=False)),
        lambda c: c.close())
    adj = grnboost2(expression_data=ex, tf_names=present, verbose=False,
                    seed=ctx.config["seed"], client_or_address=client)
    # EMPTY IS THE FAILURE THAT DOES NOT RAISE. When arboreto and dask disagree about the
    # scheduler, GRNBoost2 returns no edges and downstream reads that as "no regulons found".
    if adj.shape[0] == 0:
        return ctx.refuse("regulon activity",
                          "GRNBoost2 returned NO EDGES. That is the signature of arboreto and "
                          "the installed dask disagreeing about the scheduler, not of a dataset "
                          "with no co-expression.")
    ctx.log(f"  {adj.shape[0]:,} adjacencies, {adj['TF'].nunique():,} regulators")

    modules = list(modules_from_adjacencies(adj, ex))
    db = FeatherRankingDatabase(fname=str(rank_path), name="rankings")
    pruned = prune2df([db], modules, str(m2t_path), num_workers=ctx.cores)
    regulons = [r for r in df2regulons(pruned)
                if len(r.genes) >= ctx.config["min_genes_per_regulon"]]
    if not regulons:
        return ctx.refuse("regulon activity",
                          f"no regulon survived pruning with at least "
                          f"{ctx.config['min_genes_per_regulon']} targets")
    ctx.log(f"  {len(regulons)} regulon(s) after motif pruning")

    # SCORED FOR EVERY CELL, INCLUDING THE ONES THE FIT NEVER SAW. `X_regulon_auc` is an obsm
    # block and must have one row per cell of the object; scoring only the fit subsample would
    # emit a 25k-row array for a 98k-row object, and the caveat above promises otherwise.
    #
    # CHUNKED, because building one dense frame over every cell is the 11 GB allocation that made
    # the fit thrash in the first place - and doing it here would move the failure rather than
    # fix it. AUCell ranks genes WITHIN each cell independently, so a chunk boundary cannot
    # change a cell's score: this is exact, not an approximation.
    if fit_rows is None:
        auc = aucell(ex, regulons, num_workers=ctx.cores, seed=ctx.config["seed"])
    else:
        parts, step = [], 20_000
        for start in range(0, counts.shape[0], step):
            stop = min(start + step, counts.shape[0])
            blk = counts[start:stop, :][:, keep]
            blk = np.asarray(blk.todense() if hasattr(blk, "todense") else blk, dtype=np.float32)
            parts.append(aucell(
                pd.DataFrame(blk, index=pd.Index(obs_names[start:stop], name="cell"),
                             columns=kept_genes),
                regulons, num_workers=ctx.cores, seed=ctx.config["seed"]))
            del blk
        auc = pd.concat(parts)
        ctx.log(f"  AUC scored for all {auc.shape[0]:,} cells in "
                f"{len(parts)} chunk(s), from a network fitted on {ex.shape[0]:,}")
    if auc.shape[0] != ctx.adata.n_obs:
        return ctx.refuse("regulon activity",
                          f"AUC has {auc.shape[0]:,} rows for an object of {ctx.adata.n_obs:,} "
                          f"cells. An obsm block must have one row per cell; emitting this would "
                          f"misalign every regulon score with the wrong cell.")
    # ONLY THE COHORT FIT CONTRIBUTES THE CELL-LEVEL BLOCK, and the reason is the same one this
    # plugin runs twice for. `obsm` is one array over the whole object: the per-sample fits each
    # discovered their own regulon set, so stacking their AUC columns into one block would place
    # values that are not the same quantity in the same column - the exact misuse every
    # per-sample caveat here warns against.
    #
    # The merger caught it rather than doing it: with a cohort fit present the two scopes claim
    # the same cells and it refused the lot ("the units are not disjoint"), and without one the
    # per-sample widths disagreed. Both refusals were right, and neither is fixable by the
    # merger - the plugin has to stop asking.
    #
    # A per-sample fit keeps its AUC as a table in its own directory, where it is per-sample and
    # reads as such.
    if ctx.unit is None:
        ctx.emit_obsm("X_regulon_auc", auc.to_numpy())
    else:
        ctx.emit_table("regulon_auc", auc)

    # THE UNIT OF REPLICATION IS THE SAMPLE, NOT THE CELL, and the cohort fit is where that gets
    # got wrong. Its AUC columns ARE comparable between cells - that is the whole point of fitting
    # once - and the obvious next step is a per-cell test across conditions with n in the tens of
    # thousands. Cells from one animal are not independent replicates of that animal's condition,
    # so such a test reports the cell count, not the effect: the field's answer for exactly this
    # structure is a mixed model with the individual as a random effect, or pseudobulk first
    # (Fleck/Nagy et al. meta-analyses of AD and SCZ snRNA-seq, Nat Commun 2025).
    #
    # So the cohort fit also ships the AGGREGATE a between-condition test should consume, which
    # makes the correct comparison the easy one to reach for. `de` already treats the sample as
    # the replicate; there is no reason regulon activity should not.
    if PLUGIN.get("per_unit") and ctx.unit is None and "sample" in ctx.keys:
        samp = ctx.obs("sample").astype(str).to_numpy()
        # LENGTHS MUST MATCH EXACTLY. This truncated the longer of the two and carried on, which
        # pairs cells with the wrong samples from the first mismatched row onward and produces a
        # full, plausible table. There is no correct behaviour on a mismatch except to stop.
        if len(samp) != auc.shape[0]:
            return ctx.refuse(
                "regulon activity",
                f"{len(samp):,} sample labels for {auc.shape[0]:,} scored cells. Aggregating "
                f"these would pair cells with the wrong samples and return a full table.")
        # groupby on an ALIGNED SERIES, not set_axis: `set_axis` semantics and its `copy`
        # keyword have moved across pandas versions, and this plugin is pinned to an older,
        # self-consistent island where that matters.
        by = auc.groupby(pd.Series(samp, index=auc.index, name="sample")).mean()
        ctx.emit_table("regulon_activity_by_sample", by)
        ctx.caveat(
            f"tables/regulon_activity_by_sample.csv is the MEAN AUC per regulon per sample, and "
            f"it is what a between-condition test should read. n = {by.shape[0]} samples, not "
            f"{auc.shape[0]:,} cells: cells from one animal are not independent replicates of "
            f"that animal's condition, and a per-cell test across conditions reports the cell "
            f"count rather than the effect.")
    ctx.emit_table("regulon_targets", pd.DataFrame(
        [{"regulon": r.name, "n_targets": len(r.genes),
          "targets": ";".join(sorted(r.genes))} for r in regulons]).set_index("regulon"))

    # THE HEADLINE MUST NOT REPORT THE FIT SIZE AS THE RESULT SIZE. `ex` is the subsample for a
    # cohort fit, so this read "over 25,000 cells" for a result covering 98,627 of them.
    if ex.shape[0] != auc.shape[0]:
        ctx.headline = (f"{len(regulons)} regulon(s), inferred from {ex.shape[0]:,} cells and "
                        f"scored on {auc.shape[0]:,}")
    else:
        ctx.headline = (f"{len(regulons)} regulon(s) over {auc.shape[0]:,} cells, "
                        f"inferred from this {'unit' if ctx.unit else 'dataset'}")
    ctx.caveat("The network was inferred from THIS data, so it is not comparable with one "
               "inferred from another dataset, and an absent regulon is not evidence of an "
               "inactive TF.")

    # THE TWO SCOPES ANSWER DIFFERENT QUESTIONS AND EACH SAYS WHICH IT IS. A reader who mistakes
    # one for the other draws a between-condition conclusion from columns that are not the same
    # quantity - the failure this plugin runs twice to prevent.
    if PLUGIN.get("per_unit") and ctx.unit is None:
        ctx.caveat(
            "THIS IS THE COHORT FIT: one regulon vocabulary over every cell, which is what makes "
            "activity comparable BETWEEN cells and conditions. The per-sample fits beside it are "
            "not interchangeable with it - each discovered its own regulon set, so their AUC "
            "columns are not the same quantity.")
        # A GRN POOLED ACROSS SAMPLES LEARNS WHATEVER CO-VARIES, INCLUDING THE BATCH. When the
        # upstream tool has recorded that a factor never varies within a batch, co-expression
        # driven by the batch is indistinguishable from co-expression driven by that factor, and
        # a regulon-activity difference across it cannot be attributed to biology. Reported, not
        # refused: the fit is still the right vocabulary for every comparison the constraint does
        # not name.
        if ctx.constraint:
            ctx.caveat(
                "An upstream CONSTRAINT ON USE applies to this object and it applies to this fit "
                "in particular. A cohort GRN learns whatever co-varies across the pooled cells, "
                "so where a design factor never varies within a batch, co-expression driven by "
                "the batch enters the regulons themselves and a difference in regulon activity "
                "across that factor cannot be separated from it. The constraint, verbatim: "
                + ctx.constraint.strip()[:600])
    elif PLUGIN.get("per_unit"):
        ctx.caveat(
            "THIS IS A PER-SAMPLE FIT and its regulon set was discovered from this sample alone. "
            "Do NOT compare these AUC values with another sample's - use the cohort fit for that. "
            "What these are good for is REPRODUCIBILITY: a regulon recovered independently in "
            "many samples is far stronger evidence than one appearing in a single pooled fit.")
    ctx.caveat(f"Pruned against the {ctx.organism} cisTarget rankings. Motif enrichment is what "
               f"makes a module a regulon; without it these would be raw co-expression.")


def selftest(ctx):
    """Prove GRNBoost2 runs and RECOVERS A PLANTED REGULATOR — the empty table is the failure.

    The cisTarget steps are not tested here: they need ~400 MB of rankings, which is a fetch and
    not a selftest. What is proved is the half that needs no reference data, and the report says
    which half that is.
    """
    import numpy as np
    import pandas as pd
    from arboreto.algo import grnboost2
    from pyscenic.utils import modules_from_adjacencies                # noqa: F401
    from pyscenic.prune import prune2df                                # noqa: F401
    from pyscenic.aucell import aucell                                 # noqa: F401

    rng = np.random.default_rng(0)
    n, g = 120, 40
    genes = [f"Gene{i:02d}" for i in range(g)]
    drive = rng.normal(5.0, 2.0, size=n)
    X = rng.normal(5.0, 1.0, size=(n, g))
    X[:, 0] = drive                                    # the planted regulator
    for j in range(1, 9):
        X[:, j] = drive * (1.0 + 0.05 * j) + rng.normal(0, 0.3, size=n)
    ex = pd.DataFrame(np.clip(X, 0, None), index=[f"c{i}" for i in range(n)], columns=genes)

    adj = grnboost2(expression_data=ex, tf_names=genes, verbose=False, seed=0,
                    client_or_address="local")
    assert adj.shape[0] > 0, (
        "GRNBoost2 returned NO EDGES on data with a planted regulator. This is the failure this "
        "selftest exists for: arboreto and the installed dask disagree about the scheduler and "
        "the inference comes back empty instead of raising.")
    for col in ("TF", "target", "importance"):
        assert col in adj.columns, f"the adjacency table has no {col!r}; the schema moved"
    imp = adj["importance"].to_numpy(dtype=float)
    assert np.isfinite(imp).all() and (imp > 0).any(), "importances are not finite and positive"
    assert genes[0] in set(adj["TF"].astype(str)), (
        f"the planted regulator {genes[0]!r} is not among the regulators recovered - the "
        f"inference ran but did not find an edge built into the fixture.")
    ctx.log(f"  {adj.shape[0]:,} edges; planted regulator recovered")
    ctx.log("  NOT tested here: the cisTarget prune and AUCell steps, which need the motif "
            "rankings from references.")
