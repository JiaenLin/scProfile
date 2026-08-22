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
        ],
    },

    "inject": {"required": ["counts", "organism"], "optional": ["label", "sample"]},
    "provides": ["activity"],
    "produces": ["obsm[X_regulon_auc]", "tables/regulon_targets.csv"],
    "per_unit": "sample",

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
    tfs = [l.strip() for l in open(tf_path, encoding="utf-8") if l.strip()]
    present = [t for t in tfs if t in set(genes)]

    # TARGETS ONLY, AND REGULATORS ARE NEVER DROPPED. A gene detected in a handful of cells cannot
    # support a boosted regression over thousands of them, and GRNBoost2 fits EVERY column as a
    # target - so an undetected gene costs a full fit to return noise. Restricting targets is
    # standard SCENIC practice; doing it silently would not be, so the count is logged, the gene
    # stays in the object, and `min_cells_per_gene: 0` turns it off.
    #
    # A TF is exempt whatever its detection rate: it is a REGRESSOR, dropping it removes an
    # explanation rather than a cost, and nothing downstream could recover the regulon it would
    # have carried.
    detected = np.asarray((counts > 0).sum(axis=0)).ravel()
    floor = int(ctx.config["min_cells_per_gene"])
    keep = detected >= floor if floor else np.ones(len(genes), bool)
    keep |= np.isin(genes, list(present))
    dropped = int((~keep).sum())

    sub = counts[:, keep]
    kept_genes = genes[keep]
    # float32 HALVES the graph dask ships to its workers. GRNBoost2 splits on ordering, and no
    # split in a boosted tree over UMI counts turns on the 8th decimal place.
    dense = np.asarray(sub.todense() if hasattr(sub, "todense") else sub, dtype=np.float32)
    ex = pd.DataFrame(dense, index=ctx.adata.obs_names.astype(str), columns=kept_genes)
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

    auc = aucell(ex, regulons, num_workers=ctx.cores, seed=ctx.config["seed"])
    ctx.emit_obsm("X_regulon_auc", auc.to_numpy())
    ctx.emit_table("regulon_targets", pd.DataFrame(
        [{"regulon": r.name, "n_targets": len(r.genes),
          "targets": ";".join(sorted(r.genes))} for r in regulons]).set_index("regulon"))

    ctx.headline = (f"{len(regulons)} regulon(s) over {ex.shape[0]:,} cells, "
                    f"inferred from this {'unit' if ctx.unit else 'dataset'}")
    ctx.caveat("The network was inferred from THIS data, so it is not comparable with one "
               "inferred from another dataset, and an absent regulon is not evidence of an "
               "inactive TF.")
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
