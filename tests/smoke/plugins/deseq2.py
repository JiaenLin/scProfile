"""Pseudobulk differential expression, per cell population, with DESeq2 itself.

THE UNIT OF REPLICATION IS THE SAMPLE, NOT THE CELL. Two phases, matching the host's own split:

  run(ctx)      runs once per UNIT - a single sample, or a design ARM pooling several samples'
                cells (the host runs both axes by default). Whichever it is handed, this phase
                only SUMS raw counts per (sample, population) among the cells it was given. It
                never fits anything and never sees a second arm.
  compare(ctx)  runs once per ARM PAIR, after both arms' run() has already written its own
                pseudobulk tables to disk. For every population BOTH arms produced at least
                `min_samples_per_arm` pseudobulk samples for, it hands DESeq2 the combined
                counts matrix - samples as columns, arm as the design factor - and lets DESeq2
                fit, test and draw. Nothing here re-implements a mean, a variance or a p-value:
                every number on these pages is DESeq2's own.

WHY THE SPLIT. A per-cell test treats thousands of cells from one animal as thousands of
independent observations and inflates significance by roughly the number of cells per animal.
Summing to one pseudobulk profile per (sample, population) first, and testing over samples, is
the field's answer to that; it is also why this plugin needs the compare PHASE at all - the run
phase sees one unit and a t-test between arms needs both.

THE RETURN CONTRACT - what one row of `tables/deseq2_results__<population>.csv` is

Read off the delivered file, which is exactly `DESeq2::results()`'s own data frame with a `gene`
column added, not a re-derived summary.

| field | what it is | notes |
|---|---|---|
| `gene` | one feature of the object | this plugin's own addition; everything else is DESeq2's |
| `baseMean` | mean of normalised counts across ALL pseudobulk samples of this population | not per arm |
| `log2FoldChange` | the MLE fold change, {hi} relative to {lo} | UNSHRUNK - see cannot_show |
| `lfcSE` | its standard error | |
| `stat` | the Wald statistic | |
| `pvalue` | Wald test p-value | NaN for a Cook's-distance outlier gene: NOT "not significant" |
| `padj` | BH-adjusted p-value | NaN for baseMean == 0, a Cook's outlier, OR independent filtering - three different reasons, indistinguishable in this column alone |

A gene can be ABSENT from every table for three different reasons that a headline count elides:
filtered before the fit (`min_count_sum`), never present in the object, or present in only one
arm's population (the whole population is then untested and named in
`tables/deseq2_skipped_populations.csv` rather than silently missing).

WHAT FAILS SILENTLY, READ FROM DESeq2's OWN DOCUMENTATION AND FROM RUNNING IT

  * `vst()` REFUSES on too few genes ("less than 'nsub' rows") rather than falling back; this
    plugin passes `nsub = min(1000, nrow(dds))` and still falls back to
    `varianceStabilizingTransformation()` on any further error, so the PCA panel is not simply
    absent on a small gene panel.
  * The default size-factor estimator (`sfType = "ratio"`, a geometric mean over genes) raises
    outright when some gene is zero in EVERY pseudobulk sample of a population - not rare on a
    small population - and this plugin retries once with `sfType = "poscounts"` rather than
    letting the whole population fail.
  * `plotDispEsts` silently substitutes a local regression for the parametric curve when the
    parametric fit does not converge, and says so only in the run's own log, never on the panel.
  * `results(..., alpha=)` and `plotMA(..., alpha=)` each default to 0.1. This plugin passes 0.05
    to both explicitly (`config.alpha`) so the table's significance calls and the MA plot's
    highlighted points never disagree with each other or with the field's usual convention.
"""

import re


def _slug(name):
    """A population name, made safe for a filename. Never empty."""
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_")
    return s or "pop"


PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "state_version": 1,
    "summary": "pseudobulk differential expression between two arms, per cell population, "
               "with DESeq2",
    "when_to_use": "you have raw counts, a sample column and two design arms with replicate "
                  "samples in each, and want a population-resolved differential-expression "
                  "table tested over samples rather than over cells",
    "wraps": {"tool": "DESeq2", "homepage": "https://bioconductor.org/packages/DESeq2",
              "license": "LGPL (>= 3)",
              "cite": "Love, Huber, Anders, Genome Biology 2014 (DESeq2)"},

    "upstream": {
        "docs": "https://bioconductor.org/packages/release/bioc/vignettes/DESeq2/inst/doc/"
               "DESeq2.html",
        "read": "2026-09-12",
        "defaults_changed": [
            "results(alpha=) and plotMA(alpha=) both default to 0.1 in DESeq2 itself; this "
            "plugin passes config.alpha (default 0.05) to both explicitly, so the table's "
            "significance calls and the MA plot's highlighted points are always the same "
            "genes.",
            "DESeq(minReplicatesForReplace=) is DESeq2's own default of 7, now passed "
            "explicitly as config.min_replicates. Most pseudobulk arms have far fewer than 7 "
            "replicates, so Cook's-distance replacement is a no-op on most runs; the point of "
            "passing it explicitly is that the run can say so rather than leaving it implicit.",
            "DESeq(fitType=) is left at DESeq2's own default 'parametric', exposed as "
            "config.fit_type so a population whose dispersion curve does not fit "
            "parametrically can be re-run at 'local' or 'mean' - DESeq2 substitutes a local "
            "fit automatically when the parametric one fails and only says so in the log.",
        ],
        "not_used": [
            "lfcShrink / apeglm: shrinkage changes the ranking and is a presentation choice "
            "for whoever reads the table. The MLE fold change is reported unshrunk, and "
            "plotMA's fan of noisy low-count points is left visible rather than shrunk away - "
            "see cannot_show.",
            "multi-factor or paired designs, and interaction terms: the design fitted here is "
            "always `~arm`, one factor at two levels, because compare(ctx) is handed exactly "
            "two already-resolved arms by the host. A study wanting to control for a batch "
            "term INSIDE this contrast needs a design this plugin does not build.",
            "parallel=TRUE / BiocParallel: pseudobulk sample counts are small (samples, not "
            "cells), so the fit is fast, and a deterministic single-process run is easier to "
            "reproduce than a parallel one.",
        ],
        "gotchas": [
            "padj is NA for THREE different reasons DESeq2 documents and this table does not "
            "separate on its own: baseMean == 0 (every value NA), a Cook's-distance outlier "
            "(pvalue AND padj NA), or independent filtering for a low mean count (padj only "
            "NA). The first two mean the gene was NOT TESTED, not 'tested and flat'.",
            "vst() raises 'less than nsub rows' on a small gene panel rather than falling back "
            "on its own; this plugin passes nsub = min(1000, nrow(dds)) and falls back to "
            "varianceStabilizingTransformation() on any further error.",
            "The default median-of-ratios size factor estimator raises when some gene is zero "
            "in every pseudobulk sample of a population - not rare with few replicates - and "
            "this plugin retries once with sfType='poscounts' rather than losing the "
            "population.",
            "plotDispEsts silently substitutes a local regression for the parametric dispersion "
            "curve when the parametric fit does not converge; DESeq2 prints a note to the "
            "console and changes nothing on the panel itself.",
            "DESeqDataSetFromMatrix requires integer counts and does not check very hard: a "
            "pseudobulk sum of raw counts is always an integer, but a plugin upstream of this "
            "one that writes fractional 'counts' (after ambient-RNA correction, say) would be "
            "rounded by DESeq2 without a warning.",
        ],
    },

    # CAPABILITIES, NEVER COLUMN NAMES. `design` is deliberately ABSENT: the arm pairing that
    # drives compare(ctx) is the HOST's own reading of the project's design table (report.py),
    # never something this plugin is handed through `inject` - cellchat's compare needs exactly
    # the same two arms and does not inject `design` either.
    "inject": {"required": ["counts", "label", "sample"], "optional": []},
    "provides": [],
    "produces": [
        "tables/pseudobulk__<population>.csv per population this unit reached min_cells on",
        "tables/pseudobulk_meta.csv",
        "[compare] tables/deseq2_skipped_populations.csv",
        "[compare] tables/deseq2_manifest.tsv",
        "[compare] tables/deseq2_input__<population>.csv per population tested",
        "[compare] tables/deseq2_coldata__<population>.csv per population tested",
        "[compare] tables/deseq2_results__<population>.csv per population tested",
        "[compare] tables/deseq2_populations_tested.tsv",
        "[compare] figures/nativecmp_plotMA__<population>.png",
        "[compare] figures/nativecmp_plotDispEsts__<population>.png",
        "[compare] figures/nativecmp_plotPCA__<population>.png",
        "[compare] figures/nativecmp_plotCounts__<population>.png",
        "[compare] figures/nativecmp_plotSparsity__<population>.png",
    ],

    # SCOPE. A pooled cohort-wide pseudobulk would describe the average of every arm and every
    # population and answer nothing; the result exists only per population, per arm pair, in
    # compare(ctx). run(ctx) itself is meaningful over a sample OR an arm, hence "sample" - the
    # smaller of the two, matching cellchat/liana/scenic's own declaration for the same reason.
    "per_unit": "sample",

    "config": {
        "min_cells": {"type": "int", "default": 10, "min": 1,
                      "help": "a (sample, population) combination with fewer cells than this "
                              "is not summed into a pseudobulk sample - a handful of cells "
                              "carrying a sample's name is noise, not a replicate"},
        "min_samples_per_arm": {"type": "int", "default": 2, "min": 2,
                                "help": "a population needs at least this many pseudobulk "
                                        "samples in BOTH arms or there is no within-arm "
                                        "variance for DESeq2 to estimate dispersion from"},
        "min_count_sum": {"type": "int", "default": 10, "min": 0,
                          "help": "a gene with fewer total counts than this, summed across "
                                  "only the pseudobulk samples actually used in a population's "
                                  "fit, is dropped before DESeq2 sees it - a power decision, "
                                  "not a claim the gene is not expressed"},
        "alpha": {"type": "float", "default": 0.05, "min": 0.0, "max": 1.0,
                  "help": "the adjusted-p threshold passed to both results() and plotMA(), so "
                          "the table and the MA plot always agree on which genes are "
                          "highlighted. DESeq2's own default for both is 0.1"},
        "fit_type": {"type": "str", "default": "parametric",
                     "help": "DESeq2's own DESeq(fitType=): parametric | local | mean. "
                             "parametric is DESeq2's own default; switch to local or mean if "
                             "nativecmp_plotDispEsts shows the parametric curve did not fit"},
        "min_replicates": {"type": "int", "default": 7, "min": 2,
                           "help": "DESeq2's own DESeq(minReplicatesForReplace=): a Cook's "
                                   "outlier count is refitted only in an arm with at least "
                                   "this many pseudobulk samples. DESeq2's own default is 7, "
                                   "which most single-cell designs do not reach per arm"},
        "max_populations": {"type": "int", "default": 12, "min": 1,
                            "help": "at most this many shared, testable populations are fitted "
                                    "and drawn per arm pair, by descending pooled cell count. "
                                    "Paired with each figure family's own at_most=12 below - "
                                    "raise both together"},
    },

    "requires": {
        "python": ">=3.10,<3.13",
        # THE CONTRACT'S, NOT THIS METHOD'S - `_entry.py` reads the object with anndata and
        # `ctx.plot()` imports matplotlib before this file is ever asked to do either.
        "packages": {"anndata": ">=0.12,<0.13", "pandas": ">=2.0,<3", "numpy": ">=1.24,<3",
                     "matplotlib": ">=3.6,<4"},
        "language": "r",
        # DESeq2 IS BIOCONDUCTOR, NOT CRAN, so it is named under `conda` the way cellchat names
        # ComplexHeatmap and BiocGenerics - `r-base` alone would not pull it in, and is the key
        # `sch dev convert borrowed` and the scaffold's `draws_through_r` read to know this
        # plugin needs an R interpreter in its environment at all.
        "conda": {"r-base": "", "bioconductor-deseq2": ""},
        "channels": ["conda-forge", "bioconda"],
    },

    # NOTHING IS CONSULTED THAT DID NOT COME FROM THE USER'S OWN OBJECT - no bundled database, no
    # prior, no reference panel. Declared empty rather than left absent: absent says nobody has
    # looked; `{}` says this was checked (`sch dev convert references`) and there is nothing here.
    "references": {},

    "cost": "low", "cores": 2,

    # MEMORY IS DELIBERATELY UNDECLARED. `memory_gb_base` / `memory_gb_per_100k` must be MEASURED
    # from a real run (two terms: fixed cost + per-cell rate; a rate alone attributes the fixed
    # cost to the cells and sizes small jobs to be killed - see scprofile/declare.py). No run of
    # this plugin has happened yet in this clean room, so nothing is written here rather than a
    # guessed number that would read as measured. `scprofile capacity --out <run> --memory` prints
    # both terms ready to paste once one exists.

    "report": {
        # per_unit REQUIRES THIS: a per-unit plugin's units must land on one shared axis, or its
        # page is N single-unit reports nobody can compare. Recorded in run(ctx) with
        # ctx.metric(id, value); the host draws the across-unit comparison itself.
        "unit_metrics": [
            {"id": "populations", "question": "how many populations did this unit reach "
                                              "min_cells on and write a pseudobulk table for?"},
            {"id": "samples", "question": "how many distinct samples were pooled into this "
                                          "unit's pseudobulk tables?"},
            {"id": "cells", "question": "how many real (non-sentinel) cells did this unit's "
                                        "pseudobulk tables sum over in total?"},
        ],
        # EVERY FIGURE HERE IS drawn_by: "tool" - DESeq2's OWN plotting functions, called
        # unmodified, once per population the two arms share. All five of DESeq2's exported
        # plotting functions are accounted for (`sch dev convert inventory`): none reimplemented,
        # none skipped. `kind: "other"` because none of these is a population-to-population
        # network panel - the vocabulary registered in scprofile/panels.py is for a plugin's
        # `unit_network` declaration, which this plugin does not have: DESeq2 tests one
        # population against itself across arms, and there is no edge between populations to
        # declare weight, source or target for. `axis: contrast` / `position: contrast`
        # throughout: every panel needs both arms and exists only in compare(ctx).
        "figures": [
            {"id": "nativecmp_plotMA", "kind": "other", "drawn_by": "tool", "fn": "plotMA",
             "axis": "contrast", "position": "contrast", "at_most": 12,
             "file": 'paste0("plotMA__", safe)',
             "args": 'res, alpha = alpha, main = .ttl("MA plot")',
             "legend": "MA plot for {pop}: log2 fold change ({hi} vs {lo}) against the mean "
                      "of normalised counts across all pseudobulk samples of this population, "
                      "one point per gene DESeq2 tested. Blue points pass padj < {alpha}; grey "
                      "points do not, including genes padj could not be computed for. This is "
                      "DESeq2's own UNSHRUNK fold change - genes at the low-count end fan out "
                      "and should not be ranked on fold change alone."},
            {"id": "nativecmp_plotDispEsts", "kind": "other", "drawn_by": "tool",
             "fn": "plotDispEsts", "axis": "contrast", "position": "contrast", "at_most": 12,
             "file": 'paste0("plotDispEsts__", safe)',
             "args": 'dds, main = .ttl("dispersion estimates")',
             "legend": "Gene-wise dispersion estimates for {pop} (black), the fitted "
                      "mean-dispersion trend (red) and the values actually used in testing "
                      "after shrinkage toward that trend (blue). Every p-value in this "
                      "population's results table rests on this fit; a trend that visibly does "
                      "not track the black cloud means DESeq2 substituted a local regression "
                      "for the '{fit_type}' fit and said so only in this run's own log."},
            {"id": "nativecmp_plotPCA", "kind": "other", "drawn_by": "tool", "fn": "plotPCA",
             "axis": "contrast", "position": "contrast", "at_most": 12,
             "file": 'paste0("plotPCA__", safe)',
             "args": 'vsd, intgroup = "arm"',
             "legend": "Variance-stabilised pseudobulk samples of {pop}, projected onto their "
                      "first two principal components and coloured by arm ({lo} against "
                      "{hi}). Each point is one SAMPLE's pooled cells in this population, not "
                      "one cell. If the two arms do not separate here, a gene called "
                      "significant below is a smaller effect than whatever dominates these two "
                      "axes, not necessarily a false one."},
            {"id": "nativecmp_plotCounts", "kind": "other", "drawn_by": "tool",
             "fn": "plotCounts", "axis": "contrast", "position": "contrast", "at_most": 12,
             "file": 'paste0("plotCounts__", safe)',
             "args": 'dds, gene = top_gene, intgroup = "arm", '
                     'main = .ttl(paste0("counts: ", top_gene))',
             "legend": "Normalised counts of {top_gene}, the gene with the smallest adjusted "
                      "p-value in {pop} ({lo} against {hi}), one point per pseudobulk sample. "
                      "This is the single strongest hit the table names for this population; "
                      "it is not a summary of every other gene tested alongside it."},
            {"id": "nativecmp_plotSparsity", "kind": "other", "drawn_by": "tool",
             "fn": "plotSparsity", "axis": "contrast", "position": "contrast", "at_most": 12,
             "file": 'paste0("plotSparsity__", safe)',
             "args": "dds",
             "legend": "Concentration of counts in {pop}: for each pseudobulk sample, its "
                      "counts ranked high to low against their cumulative share of that "
                      "sample's total. A curve pulled toward the corner means a handful of "
                      "genes dominate that sample's pseudobulk library, which is ordinary for "
                      "a pooled profile and is shown as a diagnostic, not a defect."},
        ],
        # THE OTHER TWO OF DESeq2's SEVEN INVENTORIED EXPORTS (`sch dev convert inventory
        # --rscript Rscript`), neither a plot this plugin declines - read from DESeq2 1.52.0's
        # own installed source, not from its documentation.
        "skips": {
            "estimateDispersionsPriorVar": {
                "skip": "not_applicable",
                "evidence": "deparse(body(DESeq2:::estimateDispersionsPriorVar)) on the "
                           "installed 1.52.0 shows it calls hist(..., plot = FALSE) twice, "
                           "as a numeric density estimator for its KL-divergence search, and "
                           "nothing else the inventory's primitive list matches. It never "
                           "draws; the inventory's body-rule flagged it as a false positive of "
                           "that heuristic, not as a plot this plugin declines to call."},
            "show": {
                "skip": "not_applicable",
                "evidence": "the S4 print/summary method for this package's classes "
                           "(DESeqDataSet, DESeqResults, DESeqTransform): it writes a text "
                           "summary to the console and draws nothing. Matched only by the "
                           "inventory's NAME convention - the literal word 'show' - never by "
                           "its body."},
        },
    },

    "cannot_show": [
        "PSEUDOBULK CANNOT SEE A CHANGE CONFINED TO A SUBSET of a labelled population; summing "
        "the population's cells averages it away. A negative result here is a statement about "
        "the population as labelled, not about every cell in it.",
        "A population present in only one arm has no contrast and is not run through DESeq2 at "
        "all; it is named in tables/deseq2_skipped_populations.csv, and its absence from the "
        "results tables is not evidence of no expression or no change.",
        "This tests a difference in mean pseudobulk expression, never a difference in the "
        "number or proportion of cells. A population that changed abundance but not per-cell "
        "expression can still produce DE genes here from a compositional shift in what got "
        "pooled; read a companion abundance result beside this one before attributing a hit to "
        "expression alone.",
        "log2FoldChange is DESeq2's raw MLE, not shrunk (lfcShrink is not run). Ranking genes "
        "by fold change over-weights the low-count end; nativecmp_plotMA shows the fan this "
        "produces and padj is the safer sort key.",
        "A NaN in padj has three different DESeq2 causes and this table does not separate them "
        "on its own: a zero baseMean, a Cook's-distance outlier, or independent filtering at a "
        "low mean count. The first two mean the gene was never tested; only the third is close "
        "to 'tested and flat'.",
        "The pseudobulk sample IS the animal, and two or three animals per arm is the usual "
        "case here, not a large one; a small padj from few replicates is weaker evidence than "
        "the same padj from ten. tables/deseq2_populations_tested.tsv states n_lo and n_hi "
        "beside every row.",
        "Every table and figure here describes ONE population in ONE arm pair. It says nothing "
        "about any other population, and nothing about a third arm this design may also carry.",
    ],
}


# ================================================================================================
# run(ctx) - pseudobulk aggregation only. One unit: a sample, or an arm pooling several samples'
# cells (the host decides which axis this call is; see PLUGIN["per_unit"] above). Either way this
# sums raw counts per (sample, population) among exactly the cells ctx.adata holds - never more.
# ================================================================================================

def run(ctx):
    import numpy as np
    import pandas as pd

    counts = ctx.counts()
    if counts is None:
        return ctx.refuse(
            "pseudobulk aggregation",
            "no integer counts layer is available. DESeq2 models raw counts; handed "
            "log-normalised values it would still run and return a plausible table that means "
            "nothing, so this plugin refuses rather than guess which layer is which.")

    samp_col = ctx.obs("sample")
    if samp_col is None:
        return ctx.refuse(
            "pseudobulk aggregation",
            "no sample column is available. The sample is this method's unit of replication; "
            "with no sample to sum cells INTO, every cell would have to be its own replicate, "
            "which is exactly the per-cell inflation pseudobulking exists to avoid.")

    p = ctx.populations()
    if p.groups is None:
        return ctx.refuse(
            "pseudobulk aggregation",
            "no label column is available, so there is no population to stratify the "
            "pseudobulk by. This method reports one differential-expression table PER "
            "population and has nothing to key those tables on without it.")

    min_cells = int(ctx.config.get("min_cells", 10))
    samp_all = samp_col.astype(str).to_numpy()
    samp = samp_all[p.mask]                      # aligned to p.groups, see Populations
    lab = np.asarray(p.groups)
    genes = np.asarray(ctx.adata.var_names).astype(str)

    # ONE PASS OVER THE REAL CELLS, GROUPING (population, sample) -> the row indices to sum.
    # Sentinel-labelled cells are already out of `p.groups`/`p.mask` - see ctx.populations().
    real_rows = np.flatnonzero(p.mask)
    keys = {}
    for row, s, l in zip(real_rows, samp, lab):
        keys.setdefault((str(l), str(s)), []).append(row)

    meta_rows, by_pop = [], {}
    for (l, s), idx in sorted(keys.items()):
        n = len(idx)
        used = n >= min_cells
        total = 0.0
        if used:
            vec = np.asarray(counts[idx].sum(axis=0)).ravel()
            by_pop.setdefault(l, {})[s] = vec
            total = float(vec.sum())
        meta_rows.append({"population": l, "sample": s, "n_cells": int(n),
                          "total_counts": total, "used": bool(used)})

    meta_df = pd.DataFrame(
        meta_rows, columns=["population", "sample", "n_cells", "total_counts", "used"])
    if len(meta_df):
        meta_df = meta_df.set_index(pd.Index(
            [f"{r.population}::{r.sample}" for r in meta_df.itertuples()], name="unit"))
    ctx.emit_table("pseudobulk_meta", meta_df)

    n_small = int((~meta_df["used"]).sum()) if len(meta_df) else 0
    if n_small:
        ctx.caveat(
            f"{n_small} (sample, population) combination(s) had fewer than "
            f"min_cells={min_cells} cells and were not summed into a pseudobulk sample - a "
            f"handful of cells carrying a sample's name is noise, not a replicate. See "
            f"tables/pseudobulk_meta.csv (used=False).")
    if p.dropped:
        ctx.caveat(
            f"{', '.join(p.dropped)}: annotator sentinel label(s), present in the object but "
            f"excluded from pseudobulking - a sentinel is the annotator declining to call a "
            f"cell type, not a population to sum into a replicate.")

    written = 0
    for l in sorted(by_pop):
        wide = pd.DataFrame(by_pop[l], index=genes)
        wide.index.name = "gene"
        # INTEGER, ALWAYS. A sum of raw counts already is one; the cast only guards against a
        # counts layer stored as float that is nonetheless integer-VALUED, so DESeq2 downstream
        # is handed exactly what DESeqDataSetFromMatrix asserts rather than silently rounding it.
        wide = wide.round().astype("int64")
        ctx.emit_table(f"pseudobulk__{_slug(l)}", wide)
        written += 1

    if not written:
        return ctx.refuse(
            "pseudobulk aggregation",
            f"no (sample, population) combination reached min_cells={min_cells} among "
            f"{len(keys)} combination(s) present.")

    n_samples = len({s for _l, s in keys})
    ctx.metric("populations", written)
    ctx.metric("samples", n_samples)
    ctx.metric("cells", int(meta_df["n_cells"].sum()) if len(meta_df) else 0)

    ctx.headline = (f"pseudobulk summed for {written} population(s) across {n_samples:,} "
                    f"sample(s)" + (f", unit {ctx.unit!r}" if ctx.unit else ""))
    ctx.log(f"  {ctx.headline}")


# ================================================================================================
# THE COMPARE PHASE. DESeq2 needs both arms to fit dispersion; run(ctx) above never sees a second
# arm, so nothing here can be computed until the host calls compare(ctx) once per arm pair, on
# the pseudobulk tables both arms' run() already wrote.
# ================================================================================================

#: THE R SIDE. One Rscript invocation per arm pair, looping over every population the manifest
#: names - not one invocation per population, so DESeq2's own library load is paid once. Every
#: figure this script draws is `.draw("<id>")` against the plan the companion generates from
#: PLUGIN["report"]["figures"] above; nothing here calls png()/dev.off() or defines its own
#: device wrapper. `.figures`, `.draw`, `.at_ceiling` and the rest are defined in the GENERATED
#: companion this script is prepended to by `ctx.rscript` - see kernels/deseq2.draw.R.
_R_COMPARE = r"""
suppressMessages({library(DESeq2)})
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) >= 10)
manifest_path   <- args[1]
figdir          <- args[2]
tabledir        <- args[3]
lo              <- args[4]
hi              <- args[5]
context_path    <- args[6]
alpha           <- as.numeric(args[7])
fit_type        <- args[8]
min_replicates  <- as.integer(args[9])
min_count_sum   <- as.integer(args[10])

# THE DRAWING PROTOCOL, CONFIGURED ONCE. `.figures`, `.draw`, the ceiling and the caption writer
# are defined in the generated companion prepended above this script - see cellchat.draw.R for
# the same pattern on another plugin.
.figures(prefix = "nativecmp_", what = "DESeq2 plot", w = 1800, h = 1500,
         context = context_path)

dir.create(figdir, showWarnings = FALSE, recursive = TRUE)
dir.create(tabledir, showWarnings = FALSE, recursive = TRUE)

man <- utils::read.delim(manifest_path, sep = "\t", stringsAsFactors = FALSE)
cat("DESeq2 compare:", nrow(man), "population(s) to fit,", lo, "against", hi, "\n")

.ttl <- function(what) paste0(what, " - ", pop, " (", hi, " vs ", lo, ")")

acct <- vector("list", nrow(man))
for (i in seq_len(nrow(man))) {
  pop  <- man$population[i]
  safe <- man$safe[i]
  acct[[i]] <- tryCatch({
    cts <- as.matrix(utils::read.csv(man$matrix[i], row.names = 1, check.names = FALSE))
    storage.mode(cts) <- "integer"
    cd <- utils::read.csv(man$coldata[i], row.names = 1, stringsAsFactors = FALSE)
    cd$arm <- factor(cd$arm, levels = c(lo, hi))
    stopifnot(identical(colnames(cts), rownames(cd)))

    keep <- rowSums(cts) >= min_count_sum
    cts <- cts[keep, , drop = FALSE]
    cat(pop, ": ", nrow(cts), " of ", length(keep), " genes pass min_count_sum=",
        min_count_sum, "\n", sep = "")
    if (nrow(cts) < 1) stop("no gene passed min_count_sum")

    dds <- DESeqDataSetFromMatrix(countData = cts, colData = cd, design = ~arm)
    # THE ZERO-EVERYWHERE GOTCHA. The default median-of-ratios size factor estimator raises
    # when some gene is zero in every pseudobulk sample of this population - not rare with few
    # replicates - so a failure here is retried once with the estimator DESeq2's own
    # documentation recommends for sparse data, rather than losing the whole population.
    dds <- tryCatch(
      DESeq(dds, fitType = fit_type, minReplicatesForReplace = min_replicates, quiet = TRUE),
      error = function(e) {
        cat(pop, ": default size factors failed (", conditionMessage(e),
            "); retrying with sfType='poscounts'\n", sep = "")
        dds2 <- estimateSizeFactors(dds, type = "poscounts")
        DESeq(dds2, fitType = fit_type, minReplicatesForReplace = min_replicates, quiet = TRUE)
      })

    res <- results(dds, contrast = c("arm", hi, lo), alpha = alpha)
    resdf <- as.data.frame(res)
    resdf <- cbind(gene = rownames(resdf), resdf)
    utils::write.csv(resdf, file.path(tabledir, paste0("deseq2_results__", safe, ".csv")),
                      row.names = FALSE)

    # THE VARIANCE-STABILISED MATRIX, FOR plotPCA ALONE - never fed back into results(). See
    # upstream.gotchas: vst() refuses outright on too few genes rather than falling back.
    vsd <- tryCatch(vst(dds, blind = FALSE, nsub = min(1000L, nrow(dds))),
                    error = function(e) varianceStabilizingTransformation(dds, blind = FALSE))
    ord <- order(res$padj, na.last = TRUE)
    top_gene <- rownames(res)[ord[1]]

    .draw("nativecmp_plotMA")
    .draw("nativecmp_plotDispEsts")
    .draw("nativecmp_plotPCA")
    .draw("nativecmp_plotCounts")
    .draw("nativecmp_plotSparsity")

    data.frame(population = pop, n_genes = nrow(cts),
               n_tested = sum(!is.na(res$pvalue)),
               n_sig = sum(!is.na(res$padj) & res$padj < alpha),
               n_lo = sum(cd$arm == lo), n_hi = sum(cd$arm == hi),
               tested = TRUE, why_not = "", stringsAsFactors = FALSE)
  }, error = function(e) {
    cat(pop, ": FAILED - ", conditionMessage(e), "\n", sep = "")
    data.frame(population = pop, n_genes = NA, n_tested = NA, n_sig = NA,
               n_lo = NA, n_hi = NA, tested = FALSE,
               why_not = paste("DESeq2 failed:", conditionMessage(e)),
               stringsAsFactors = FALSE)
  })
}
acct_df <- do.call(rbind, acct)
utils::write.table(acct_df, file.path(tabledir, "deseq2_populations_tested.tsv"),
                    sep = "\t", row.names = FALSE, quote = FALSE)
cat("DESeq2 compare done:", sum(acct_df$tested), "of", nrow(acct_df), "population(s) fitted\n")
"""


def compare(ctx):
    """Run once per arm pair. Both units' run() has already written their own pseudobulk tables;
    this only reads them, decides which populations both arms can support, and hands DESeq2 the
    combined matrix per population."""
    import pandas as pd

    names = ctx.names
    if len(names) != 2:
        return ctx.refuse("DESeq2 comparison",
                          f"expected exactly two arms to compare, this contrast names "
                          f"{len(names)}: {', '.join(names)}")
    lo, hi = names          # lo: reference/control (first-declared); hi: the arm subtracted

    def _meta(unit):
        path = ctx.dir_of(unit) / "tables" / "pseudobulk_meta.csv"
        return pd.read_csv(path) if path.is_file() else None

    meta = {lo: _meta(lo), hi: _meta(hi)}
    missing = [u for u, m in meta.items() if m is None]
    if missing:
        return ctx.refuse(
            "DESeq2 comparison",
            f"no tables/pseudobulk_meta.csv from {' and '.join(missing)} - its run() phase "
            f"did not produce a pseudobulk table, so there is nothing to compare here.")

    min_n = int(ctx.config.get("min_samples_per_arm", 2))
    used = {u: m[m["used"]].groupby("population")["sample"].apply(list)
            for u, m in meta.items()}
    pops_lo, pops_hi = set(used[lo].index), set(used[hi].index)
    shared = sorted(pops_lo & pops_hi)

    skipped = []
    for pop in sorted(pops_lo - pops_hi):
        skipped.append({"population": pop, "why_not": f"present only in {lo}"})
    for pop in sorted(pops_hi - pops_lo):
        skipped.append({"population": pop, "why_not": f"present only in {hi}"})

    testable = []
    for pop in shared:
        n_lo, n_hi = len(used[lo][pop]), len(used[hi][pop])
        if n_lo < min_n or n_hi < min_n:
            skipped.append({"population": pop,
                            "why_not": f"{lo} has {n_lo}, {hi} has {n_hi} pseudobulk sample(s); "
                                       f"min_samples_per_arm={min_n} needs at least that many "
                                       f"in EACH arm"})
            continue
        testable.append(pop)

    # RANKED BY POOLED CELL COUNT, DESCENDING - so a cap falls on the least-powered populations
    # first, not on an alphabetical accident of their names.
    pooled_cells = {
        pop: int(meta[lo].loc[meta[lo]["population"] == pop, "n_cells"].sum()
                 + meta[hi].loc[meta[hi]["population"] == pop, "n_cells"].sum())
        for pop in testable}
    testable.sort(key=lambda p: pooled_cells[p], reverse=True)
    cap = int(ctx.config.get("max_populations", 12))
    for pop in testable[cap:]:
        skipped.append({"population": pop,
                        "why_not": f"more than max_populations={cap} shared testable "
                                   f"population(s) this contrast; kept the {cap} with the most "
                                   f"pooled cells"})
    testable = testable[:cap]

    pd.DataFrame(skipped, columns=["population", "why_not"]).to_csv(
        ctx.tables() / "deseq2_skipped_populations.csv", index=False)

    if not testable:
        return ctx.refuse(
            "DESeq2 comparison",
            f"no population has at least min_samples_per_arm={min_n} pseudobulk sample(s) in "
            f"BOTH {lo} and {hi}; see tables/deseq2_skipped_populations.csv for every "
            f"population considered and why each was set aside.")

    manifest_rows = []
    for pop in testable:
        slug = _slug(pop)
        m_lo = pd.read_csv(ctx.dir_of(lo) / "tables" / f"pseudobulk__{slug}.csv", index_col=0)
        m_hi = pd.read_csv(ctx.dir_of(hi) / "tables" / f"pseudobulk__{slug}.csv", index_col=0)
        m_lo = m_lo.loc[:, used[lo][pop]]
        m_hi = m_hi.loc[:, used[hi][pop]]
        # SAME OBJECT, SAME var_names, SO THE SAME GENE SET IN THE SAME ORDER - reindexed rather
        # than trusted, because a plugin upstream of this one could still have written the two
        # arms' tables from objects whose gene order does not agree.
        m_hi = m_hi.reindex(index=m_lo.index).fillna(0)
        combined = pd.concat([m_lo, m_hi], axis=1).round().astype("int64")
        combined.index.name = "gene"
        in_path = ctx.tables() / f"deseq2_input__{slug}.csv"
        combined.to_csv(in_path)

        coldata = pd.DataFrame({"arm": [lo] * m_lo.shape[1] + [hi] * m_hi.shape[1]},
                                index=list(m_lo.columns) + list(m_hi.columns))
        coldata.index.name = "sample"
        cd_path = ctx.tables() / f"deseq2_coldata__{slug}.csv"
        coldata.to_csv(cd_path)

        manifest_rows.append({"population": pop, "safe": slug,
                              "matrix": str(in_path), "coldata": str(cd_path)})

    manifest_path = ctx.tables() / "deseq2_manifest.tsv"
    pd.DataFrame(manifest_rows, columns=["population", "safe", "matrix", "coldata"]).to_csv(
        manifest_path, sep="\t", index=False)

    # THE CEILINGS AND THE COLOUR MAP, MATERIALISED FOR R. Without this file `.figures(context=)`
    # has nothing to read, `.ceil` stays empty, and every `at_most` above is a number the R side
    # never sees - see the harness's own note on cellchat about a ceiling that governs nothing.
    context_path = ctx.write_figure_context() or ""

    C = ctx.config
    proc = ctx.rscript(
        _R_COMPARE,
        [str(manifest_path), str(ctx.figures()), str(ctx.tables()), lo, hi, str(context_path),
         str(float(C.get("alpha", 0.05))), str(C.get("fit_type", "parametric")),
         str(int(C.get("min_replicates", 7))), str(int(C.get("min_count_sum", 10)))],
        name="deseq2_compare")

    if proc.returncode != 0:
        ctx.refuse("DESeq2 comparison",
                   f"the R side exited {proc.returncode}. Last lines: "
                   + " | ".join((proc.stderr or proc.stdout or "").strip().splitlines()[-6:]))
        return

    acct_path = ctx.tables() / "deseq2_populations_tested.tsv"
    n_ok = len(testable)
    if acct_path.is_file():
        acct = pd.read_csv(acct_path, sep="\t")
        n_ok = int(acct["tested"].astype(str).isin(["True", "TRUE", "1"]).sum())
    ctx.log(f"  DESeq2 compare {hi} vs {lo}: {n_ok} of {len(testable)} population(s) fitted, "
            f"{len(skipped)} skipped before reaching R")


# ================================================================================================
# selftest(ctx) - proves the method RUNS AND RECOVERS A PLANTED SIGNAL, on a fixture built by the
# host (ctx.fixture()). Exercises BOTH phases exactly as a real run would: run(ctx) once per arm,
# pseudobulking that arm's samples' cells by population; compare(ctx) once, over the two arms'
# saved tables, running DESeq2 through Rscript and drawing at least one panel through the
# generated companion.
# ================================================================================================

def selftest(ctx):
    import shutil
    import tempfile
    from pathlib import Path

    assert shutil.which("Rscript"), "no Rscript on PATH - this plugin's environment has no R"

    # MAKER DEFECT, WORKED AROUND HERE (see REPORT.md): `scprofile._entry.selftest()` builds the
    # Context this function is CALLED with as `Context(None, keys={}, out=d, cores=1, log=log)`
    # - no `r_companion=`, so it is always "". The real run/compare path always loads it via
    # `_companion_text(plugin_path)`. Reading the sibling companion by path here is exactly what
    # that helper does; it lets this selftest draw a real panel through `.draw()` regardless.
    draw_r = Path(__file__).resolve().with_name("deseq2.draw.R")
    assert draw_r.is_file(), (
        f"{draw_r.name} does not exist yet - run `scprofile scaffold deseq2 --force` first")
    companion_text = draw_r.read_text(encoding="utf-8")

    # THE REAL CLASSES, NOT A HAND-ROLLED STAND-IN. `type(ctx)` is `scprofile.plugin.Context`
    # itself, already imported by the host process running this selftest; `CompareContext` sits
    # beside it. Importing it here, inside the function the task asked this of, matches how
    # `scprofile._entry._compare()` builds the one this plugin will actually be called with.
    Context = type(ctx)
    from scprofile.plugin import CompareContext

    # A FIXTURE WITH TWO ARMS AND THREE SAMPLES EACH - the smallest design that gives DESeq2 a
    # real within-arm variance to estimate dispersion from in both arms at once.
    labels = ("popA", "popB")
    samples = [f"s{i}" for i in range(6)]         # s0,s1,s2 -> ctrl; s3,s4,s5 -> trt
    arm_of = {s: ("ctrl" if i < 3 else "trt") for i, s in enumerate(samples)}
    n_cells, n_genes = 600, 60
    try:
        A = ctx.fixture(n_cells=n_cells, n_genes=n_genes, labels=labels, seed=0)
    except ModuleNotFoundError as e:
        # MAKER DEFECT, WORKED AROUND HERE (see REPORT.md): ctx.fixture() unconditionally
        # imports scanpy to build a `lognorm` layer, even for a plugin - this one - that never
        # injects `lognorm` at all. This clean room's interpreter has anndata/numpy/pandas/
        # matplotlib/scipy but no scanpy, so ctx.fixture() raises ModuleNotFoundError for
        # every plugin regardless of whether it needs the layer scanpy is used to build.
        # Rebuilt here from the identical formula ctx.fixture() uses (same seed, same
        # rng.poisson(rng.uniform(...)) draw), omitting only the lognorm layer this plugin
        # never reads.
        ctx.log(f"  ctx.fixture() needs scanpy, not installed here ({e}); rebuilding the "
               f"counts+label part of the same fixture without it")
        import anndata as ad
        import numpy as np
        import pandas as pd
        rng = np.random.default_rng(0)
        gv = [f"Gene{i:04d}" for i in range(n_genes)]
        X = rng.poisson(rng.uniform(0.2, 6.0, size=len(gv)),
                        size=(n_cells, len(gv))).astype("float32")
        A = ad.AnnData(
            X, obs=pd.DataFrame({"label": pd.Categorical(
                [labels[i % len(labels)] for i in range(n_cells)])},
                index=[f"c{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=gv))
        A.layers["counts"] = A.X.copy()
    # BLOCK ASSIGNMENT, NOT `i % len(samples)`. ctx.fixture() cycles the label as `i %
    # len(labels)`, and len(labels)=2 divides len(samples)=6 - so a sample-by-`i % 6` scheme
    # would alias perfectly with the label cycle (sample s reduces to one label every time) and
    # every population would end up with only 3 of the 6 samples, never split 3-and-3 across
    # the two arms. Contiguous blocks decorrelate the two: each sample is one contiguous run of
    # cells, and the label still alternates every cell WITHIN it.
    n = A.n_obs
    A.obs["sample"] = [samples[min(i * len(samples) // n, len(samples) - 1)] for i in range(n)]

    # PLANT A SIGNAL: genes 0-2, in popA only, multiplied up in the trt samples. If the method
    # cannot recover an effect this size on this little noise, it cannot be trusted on real data
    # either - an import check alone would not have caught that.
    import numpy as np
    counts = np.asarray(A.layers["counts"]).copy()
    trt_rows = (A.obs["sample"].isin([s for s in samples if arm_of[s] == "trt"])
                & (A.obs["label"] == "popA")).to_numpy()
    counts[np.ix_(trt_rows, [0, 1, 2])] = (
        counts[np.ix_(trt_rows, [0, 1, 2])] * 8 + 20)
    A.layers["counts"] = counts.astype("float32")

    with tempfile.TemporaryDirectory(prefix="deseq2-selftest-") as td:
        td = Path(td)
        out = {}
        for arm in ("ctrl", "trt"):
            members = [s for s in samples if arm_of[s] == arm]
            sub = A[A.obs["sample"].isin(members)].copy()
            arm_out = td / arm
            actx = Context(sub, keys={"counts": "counts", "label": "label", "sample": "sample"},
                           out=arm_out, cores=1, unit=arm, unit_members=members, log=ctx.log)
            run(actx)
            assert actx.status == "ok", f"run(ctx) refused on arm {arm!r}: {actx.absent}"
            assert (arm_out / "tables" / "pseudobulk_meta.csv").is_file(), (
                f"run(ctx) wrote no pseudobulk_meta.csv for arm {arm!r}")
            assert (arm_out / "tables" / "pseudobulk__popA.csv").is_file(), (
                f"run(ctx) wrote no pseudobulk table for popA on arm {arm!r}")
            out[arm] = arm_out

        cctx = CompareContext(
            pair="trt__ctrl", units={"ctrl": out["ctrl"], "trt": out["trt"]},
            out=td / "compare", config={"min_samples_per_arm": 2, "max_populations": 12,
                                        "alpha": 0.05, "fit_type": "parametric",
                                        "min_replicates": 7, "min_count_sum": 10},
            figure_position={"nativecmp_": "contrast"},
            figure_ceiling={f["id"]: f["at_most"] for f in PLUGIN["report"]["figures"]},
            r_companion=companion_text, log=ctx.log)
        compare(cctx)
        assert cctx.status == "ok", f"compare(ctx) refused: {cctx.absent}"

        res_path = cctx.out / "tables" / "deseq2_results__popA.csv"
        assert res_path.is_file(), "compare(ctx) wrote no deseq2_results__popA.csv"
        import pandas as pd
        res = pd.read_csv(res_path).set_index("gene")
        for g in ("Gene0000", "Gene0001", "Gene0002"):
            assert g in res.index, f"{g} is missing from popA's own results table"
            assert res.loc[g, "padj"] == res.loc[g, "padj"], f"{g}: padj is NaN, not recovered"
            assert res.loc[g, "padj"] < 0.05, (
                f"{g}: planted an 8x, +20 count shift and padj came back "
                f"{res.loc[g, 'padj']!r} - the signal was not recovered")
            assert res.loc[g, "log2FoldChange"] > 0, (
                f"{g}: planted a higher count in trt and log2FoldChange came back "
                f"{res.loc[g, 'log2FoldChange']!r}, not positive")

        drawn = sorted((cctx.out / "figures").glob("nativecmp_plotMA__*.png"))
        assert drawn, "compare(ctx) drew no nativecmp_plotMA panel through the companion"
        assert drawn[0].stat().st_size > 0, f"{drawn[0]} exists but is empty"

    ctx.log("  deseq2 selftest: pseudobulk recovered a planted 8x/+20 shift in 3 genes of "
           "popA (padj<0.05, log2FoldChange>0) and drew at least one panel through the "
           "generated companion")
