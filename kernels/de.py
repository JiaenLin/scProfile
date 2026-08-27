"""Which genes change, per cell type, across the design - tested on pseudobulk.

THE UNIT OF REPLICATION IS THE SAMPLE, NOT THE CELL, and that decision is the whole plugin.
A per-cell test treats thousands of cells from one animal as thousands of independent
observations and inflates significance by roughly the number of cells per animal. So counts are
summed per (sample, population) first, and the test runs over samples.

WHAT THE PAGE HAS TO SHOW, AND WHY FOUR OF ITS SIX PANELS ARE CHECKS

A differential-expression table is the most quotable output this tool produces and the easiest to
quote wrongly, because every one of its failure modes returns a full, plausible, correctly-shaped
table. Three of them were found by reading PyDESeq2's own documentation rather than the code:

  * `padj` is NaN for THREE different documented reasons and the table does not say which. Two of
    them mean *this gene was never tested*; only one means *this gene has a weak signal*.
  * `refit_cooks=True` does nothing at all below `min_replicates` samples in a level - which is
    most pseudobulk designs - and the outlier gene is then DROPPED from the answer rather than
    rescued from the outlier.
  * independent filtering makes the set of genes that have a `padj` at all depend on `alpha`, so
    two runs differing only in the threshold do not have the same denominator.

None of that is visible in the result. So the page leads with the checks: is there a replicate
here at all, did the count model find a mean-variance trend, are the p-values calibrated, and
which genes left the answer before it was computed. The result comes after them.
"""

PLUGIN = {
    "api": 1,
    "version": "0.2.0",
    "summary": "which genes change, per cell type, across the design",
    "when_to_use": "you have a design table with replicates and want differential expression",
    "wraps": {"tool": "pydeseq2", "homepage": "https://pydeseq2.readthedocs.io",
              "license": "MIT",
              "cite": "Muzellec et al., Bioinformatics 2023 (PyDESeq2); "
                      "Love et al., Genome Biol 2014 (DESeq2)"},
    "upstream": {
        "docs": "https://pydeseq2.readthedocs.io",
        "read": "2026-08-25",
        "defaults_changed": [
            "refit_cooks=True is kept, but the sample sizes here are small and Cook's filtering "
            "is what keeps one outlier animal from carrying a gene. It is named because it "
            "silently changes results.",
            "min_replicates IS NOW PASSED, at PyDESeq2's own default of 7. It was inherited "
            "implicitly, and it is the switch that decides whether `refit_cooks` does anything: "
            "a level with fewer than min_replicates samples is not refitted at all. Passing it "
            "explicitly is what lets the run say, from the data in front of it, that the refit "
            "never happened - see gotchas.",
            "cooks_filter and independent_filter ARE NOW PASSED, both at PyDESeq2's own default "
            "of True. They decide which genes come back with a p-value and which come back with "
            "an adjusted one; taken silently, the report could not state either, and a gene the "
            "filters removed is indistinguishable in the table from a gene that was tested and "
            "found flat.",
            "fit_type IS NOW PASSED, at PyDESeq2's own default of 'parametric', by whichever "
            "name this installed version accepts - see gotchas. It selects the dispersion-mean "
            "model the whole test rests on, and F2_dispersion is drawn so a reader can see "
            "whether that model fitted anything.",
            "A design formula is BUILT FROM THE DESIGN TABLE, never assumed. The plan chooses "
            "the richest contrast the design supports and passes it in params.",
        ],
        "not_used": [
            "LFC shrinkage (lfc_shrink): it changes the ranking and is a presentation choice, "
            "so it belongs to whoever reads the table, not to this plugin. The consequence is "
            "drawn rather than hidden - F5_ma shows the low-count fan that shrinkage exists to "
            "remove, and its caption says not to rank on those fold changes.",
            "Per-cell testing. It is offered by other tools and is never defaulted to here.",
            "size_factors_fit_type='poscounts'. PyDESeq2's default is 'ratio', the median of "
            "ratios, which is estimated only from genes with a non-zero count in EVERY "
            "pseudobulk sample. 'poscounts' is what its documentation offers for sparse data. "
            "Switching would change every normalised count and therefore every result, so it is "
            "not done silently; F1_replicates shows the library sizes the ratio was taken over.",
            "lfc_null / alt_hypothesis - testing against a fold change other than zero. A real "
            "and better-powered question on well-replicated designs, and a different question "
            "from the one this plugin is asked.",
        ],
        "gotchas": [
            "PyDESeq2 requires integer counts and will happily run on log-normalised values, "
            "returning a full table that means nothing. The counts capability is required for "
            "exactly that reason.",
            "A population present in only one arm produces coefficients with no contrast. Those "
            "populations are skipped and named.",
            "A NaN IN `padj` HAS THREE DIFFERENT CAUSES AND THE TABLE DOES NOT SAY WHICH. "
            "DESeq2's own documentation lists them: baseMean is zero, so every column is NA; the "
            "gene has a Cook's-distance outlier, so pvalue AND padj are NA; or independent "
            "filtering removed it for a low mean count, so only padj is NA. The first two mean "
            "the gene was NOT TESTED. Counting `padj < alpha` silently files all three under "
            "'not significant', which is the one reading that is wrong for two of them. "
            "F4_untested separates them and the counts are in its source table.",
            "`refit_cooks=True` IS A NO-OP ON MOST PSEUDOBULK DESIGNS. PyDESeq2 refits an "
            "outlier count only where a level has at least `min_replicates` samples, and that "
            "default is 7 - more replicates than most single-cell designs have per arm. Below "
            "it nothing is refitted, `cooks_filter` sets the gene's p-value and adjusted p-value "
            "to NaN instead, and the gene leaves the answer while its row stays in the table. "
            "The parameter reads as protection and behaves, at these sample sizes, as removal.",
            "INDEPENDENT FILTERING MAKES THE TESTED GENE SET DEPEND ON `alpha`. It chooses the "
            "mean-count threshold that maximises discoveries AT THE ALPHA IT WAS GIVEN, so two "
            "runs differing only in alpha do not have the same denominator - the number of genes "
            "carrying a padj at all changes, not merely the number below the line.",
            "THE DISPERSION ATTRIBUTES MOVED BETWEEN SUPPORTED VERSIONS: PyDESeq2 0.4.x keeps "
            "them in `dds.varm`, 0.5.x in `dds.var`. Code reading one finds nothing on the "
            "other, and 'nothing' is not an error - the dispersion diagnostic would simply stop "
            "being drawn, on a run that otherwise looks complete. `_var_array` reads both and "
            "F2_dispersion is declared optional with the reason.",
            "`fit_type` IS CALLED `trend_fit_type` IN 0.4.x. Same setting, different keyword, "
            "and passing the wrong one is a TypeError at construction rather than a silent "
            "default - but only if it is passed at all. It is resolved from the constructor "
            "signature.",
            "THE `design=` KEYWORD IS A FORMULA STRING ONLY FROM 0.5. 0.4.x takes "
            "`design_factors`, a list of column names, and cannot express the interaction term "
            "this plugin builds. The requirement said `>=0.4` while the code had always passed a "
            "formula, so the declared floor was a version the plugin could not run on; it is now "
            "`>=0.5`.",
        ],
    },

    "inject": {"required": ["counts", "label", "sample", "design"],
               "optional": ["contrast"]},
    "provides": [],
    "produces": ["tables/de_by_population.csv"],

    # WHAT WAS SHOWN TO IT, so the plan can tell a user which of their own columns and layers this
    # plugin will touch. An under-declared plugin looks like one that reads nothing.
    "sees": ["layers[{counts}]", "obs[{label}]", "obs[{sample}]", "var_names"],

    "config": {
        "min_cells": {"type": "int", "default": 10, "min": 1,
                      "help": "a (sample, population) cell with fewer cells than this is not "
                              "summed into a pseudobulk sample - it is noise wearing a "
                              "sample's name"},
        "min_samples_per_level": {"type": "int", "default": 2, "min": 2,
                                  "help": "a population needs this many samples in every level "
                                          "of the contrast, or there is no within-group variance"},
        "min_counts": {"type": "int", "default": 10, "min": 0,
                       "help": "genes below this total across pseudobulk samples are dropped "
                               "before testing, which is a power decision and not a filter on "
                               "biology"},
        "alpha": {"type": "float", "default": 0.05, "min": 0.0, "max": 1.0,
                  "help": "the adjusted-p threshold reported as significant; the full table is "
                          "written regardless. It also sets the independent-filtering threshold, "
                          "so it changes which genes carry an adjusted p-value at all"},
        # THE FOUR BELOW ARE PyDESeq2'S OWN DEFAULTS, DECLARED RATHER THAN INHERITED - the same
        # move that was made for decoupler's `min_n`. Each changes what the result MEANS, and
        # each was being taken silently, so the report could not state any of them.
        "min_replicates": {"type": "int", "default": 7, "min": 2,
                           "help": "a level with at least this many samples has its Cook's "
                                   "outlier counts REFITTED; below it nothing is refitted and "
                                   "the outlier gene is dropped from the answer instead. "
                                   "PyDESeq2's own default is 7, which most single-cell designs "
                                   "do not reach - the run says so when they do not"},
        "cooks_filter": {"type": "bool", "default": True,
                         "help": "set pvalue and padj to NaN for a gene with an extreme count in "
                                 "one sample. PyDESeq2's own default is True. Turning it off "
                                 "returns those genes to the table with a p-value that one "
                                 "sample may be carrying"},
        "independent_filter": {"type": "bool", "default": True,
                               "help": "withhold an adjusted p-value from low-mean genes to "
                                       "raise power at the given alpha. PyDESeq2's own default "
                                       "is True. It is why a gene can have a pvalue and no padj"},
        "fit_type": {"type": "str", "default": "parametric",
                     "help": "how dispersion is fitted against the mean: `parametric` fits a "
                             "gamma-family curve, `mean` uses one number for every gene. "
                             "PyDESeq2's own default is parametric; `mean` is what to fall back "
                             "to when F2_dispersion shows the curve did not fit"},
    },

    # pydeseq2 was measured as ADDITIVE to a modern scanpy stack, so this shares whatever
    # environment the builder resolves for that stack rather than asking for one of its own.
    "requires": {
        "python": ">=3.10,<3.13",
        # THE FLOOR IS 0.5 AND WAS `>=0.4`, which this plugin could never have run on: `design=`
        # takes a formula string only from 0.5, and 0.4.x's `design_factors` list cannot express
        # the interaction term built below. A floor a plugin cannot run at is not a lower bound,
        # it is a build that resolves cleanly and dies at the first call on somebody's machine.
        "packages": {"pydeseq2": ">=0.5,<0.6", "pandas": ">=2.0,<3", "numpy": ">=1.24,<3",
                     # THE CONTRACT'S, NOT THIS METHOD'S. `_entry.py` reads the object with
                     # `anndata.read_h5ad` before run() is called; this plugin never touches it
                     # directly. It worked only because it shares an environment with plugins
                     # that name it.
                     "anndata": ">=0.10,<0.12",
                     # NEEDED SINCE THIS PLUGIN DREW ANYTHING. It was absent while the plugin
                     # emitted no figure, and an undeclared draw dependency is an environment
                     # that builds and a run that dies in the figure step, after the fit is paid.
                     "matplotlib": ">=3.7,<4"},
    },

    "cost": "medium", "cores": 4,

    # Measured, not estimated: fitted from this plugin's own instances in one run on a 10-sample mouse single-nucleus cohort (~99k cells). ONE dataset on ONE machine - a starting point that is right for scheduling, not a universal constant. Every run re-fits and prints its own.
    # Fitted from one instance; the split is indeterminate.
    "memory_gb_per_100k": 7.3,

    # WHAT ITS PAGE SHOULD CONTAIN. Four checks, then two answers, and the order is the argument:
    # every panel above the line decides whether the two below it mean anything, and each of them
    # exists because the corresponding failure returns a full table rather than an error.
    #
    # `shows` is the whole of the reporter's knowledge. It knows no id here and never will.
    "report": {
        "figures": [
            {"id": "F1_replicates", "shows": "diagnostic", "required": True,
             "question": "how many cells and how many counts went into each pseudobulk sample, "
                         "and is that balanced across the levels being compared?",
             "source": "figures/F1_replicates.csv"},
            # OPTIONAL BECAUSE THE ATTRIBUTE MOVED, not because the fit can fail. PyDESeq2 keeps
            # dispersions in `varm` on 0.4.x and in `var` on 0.5.x, and a reader has to be told
            # which of those happened rather than shown a gap.
            {"id": "F2_dispersion", "shows": "diagnostic", "required": False,
             "question": "did the count model find a mean-variance trend, or shrink every gene "
                         "onto a flat line?",
             "source": "figures/F2_dispersion.csv",
             "when_absent": "this build of PyDESeq2 exposed no per-gene dispersion array of the "
                            "fitted length under either the `var` or the `varm` name, so the "
                            "model's own fit cannot be shown. Read every p-value below as "
                            "resting on a dispersion estimate nobody has looked at."},
            {"id": "F3_pvalue_calibration", "shows": "diagnostic", "required": True,
             "question": "are these p-values calibrated, or is the model misspecified?",
             "source": "figures/F3_pvalue_calibration.csv"},
            {"id": "F4_untested", "shows": "diagnostic", "required": True,
             "question": "which genes are absent from the answer, and for which of the "
                         "different reasons?",
             "source": "figures/F4_untested.csv"},
            {"id": "F5_ma", "shows": "result", "required": True,
             "question": "which genes change, at what expression level, and how far can a fold "
                         "change be trusted when no shrinkage was applied?",
             "source": "tables/de_by_population.csv"},
            {"id": "F6_hits_by_population", "shows": "result", "required": True,
             "question": "which populations respond to the contrast, in which direction, and "
                         "which were never tested at all?",
             "source": "figures/F6_hits_by_population.csv"},
        ],
        # THE PAIRING, AND IT IS NOT DECORATIVE. A population whose SHARE moved across the design
        # contributes a different number of cells per arm to its own pseudobulk samples, which
        # F1_replicates shows as an imbalance and this test cannot correct for. Expression and
        # composition are two readouts of one contrast and each is the other's confound; neither
        # plugin can say so from its own evidence.
        "reads_with": ["abundance"],
    },

    "cannot_show": [
        "A gene absent from the object was not tested, and its absence is not evidence of no "
        "change.",
        "PSEUDOBULK CANNOT SEE A CHANGE CONFINED TO A SUBPOPULATION of a labelled type; it "
        "averages it away. A negative result here is a statement about the population as "
        "labelled.",
        "A coefficient in a confounded design is not interpretable in isolation, whatever its "
        "p-value. Where the plan found a confound it is reproduced in the caveats.",
        "Per-cell testing treats cells from one animal as independent and inflates significance "
        "by roughly the number of cells per animal. It is not offered here.",
        "A NaN ADJUSTED P-VALUE IS NOT A NULL RESULT. It means the gene had no counts at all, or "
        "carried a Cook's-distance outlier, or was withheld by independent filtering - and only "
        "the last of those is anything like 'too weak to call'. The other two are genes that "
        "were never tested. F4_untested gives the split.",
        "THE FOLD CHANGES ARE UNSHRUNKEN. No `lfc_shrink` was applied, so at low mean expression "
        "log2FoldChange is dominated by sampling noise and can be arbitrarily large. Rank on the "
        "test statistic or the adjusted p-value; a top-by-fold-change list from this table is a "
        "list of low-count genes.",
        "ONE CONTRAST PER FACTOR IS REPORTED, AND NO INTERACTION COEFFICIENT IS. A factor with "
        "more than two levels is fitted whole and then compared on its first and last levels "
        "only, so a population reported as not responding was compared on one of that factor's "
        "contrasts; the pair taken is named in the result's `contrast` column. Where the plan "
        "asks for an interaction it is added to the design - which makes every main effect "
        "conditional on the other factor's reference level - but the interaction term itself is "
        "not contrasted, so no gene here is evidence for or against one.",
        "The p-value histogram checks CALIBRATION, not correctness. A uniform-plus-spike shape "
        "is consistent with a well-specified model; it is not evidence that the right covariates "
        "are in it, and no shape here can detect a confounder that is absent from the design "
        "table altogether.",
        "The dispersion panel shows that a trend was FITTED, not that it is right. A curve can "
        "be fitted through dispersions that no gene obeys, and the fit reports no error when it "
        "is.",
    ],
}

#: The dispersion-mean models PyDESeq2 offers. Checked here because an unrecognised string would
#: reach the constructor and raise from inside a library, or - worse, on a version that swallows
#: unknown keywords - fit a model nobody chose.
FIT_TYPES = ("parametric", "mean")

#: The two names one setting has carried across the versions this plugin supports. The
#: constructor signature decides which of them this build understands.
FIT_TYPE_KEYWORDS = ("fit_type", "trend_fit_type")

#: Per-gene arrays the dispersion panel needs, in the order it draws them. Each is looked for in
#: `dds.var` and then in `dds.varm`, because PyDESeq2 moved them between 0.4 and 0.5.
DISPERSION_KEYS = ("genewise_dispersions", "fitted_dispersions", "dispersions")

#: How many small panels a grid figure draws before it stops and NAMES the rest. Past this the
#: panels are smaller than their own axis labels, and a grid nobody can read is worse than a grid
#: with a stated omission in its caption.
PANEL_CAP = 9

#: Populations the dispersion grid draws. Fewer than PANEL_CAP because each of these panels is a
#: scatter of every gene and needs the room.
DISPERSION_PANEL_CAP = 6

#: Genes drawn per population in the dispersion panel, sampled deterministically. The panel is a
#: check on a distribution, not a per-gene lookup, and its source table is exactly the points
#: drawn - so a reader opens the numbers behind the picture rather than a different subset.
DISPERSION_GENES = 4000

#: Rows a horizontal-bar figure DRAWS before it stops, while its source table keeps every row -
#: the shape `velocity._fig_transitions` already uses. Height here scales with the row count, and
#: a population-per-row panel on a finely-clustered object is otherwise a figure a metre tall at
#: 7 pt: still readable, and no longer a journal figure, which is the only kind this tool makes.
BAR_ROWS = 30

#: Bins for the p-value histogram. Twenty is the conventional resolution: enough to see a spike
#: at zero separately from the body, coarse enough that twenty thousand genes do not draw as
#: noise.
PVALUE_BINS = 20

#: Why a gene has or has not a usable adjusted p-value, in the order F4 stacks them. The first is
#: the answer; the rest are genes that left the answer, and DESeq2's own documentation is what
#: distinguishes them.
UNTESTED_REASONS = ("tested", "independent filtering", "Cook's outlier", "no counts",
                    "below min_counts")


def _identifiable(ctx, obs, terms):
    """The terms that can be estimated together, and the ones that cannot, with the reason.

    THE RANK TEST IS THE HOST'S, and the fact that this plugin had its own is what let the
    interaction be added to the formula without one. The check existed, correctly, and was
    applied to every main effect - and then a term was appended after it, by a different line,
    which is not a mistake about interactions but about a check living somewhere a later
    contributor does not have to go through.

    `ctx.drop_inestimable` is the one place that decides, for any plugin fitting any model.
    """
    return ctx.drop_inestimable(obs, terms)


def _fit_type_kwargs(cls, want):
    """`({keyword: want}, keyword)` for whichever name this PyDESeq2 calls the setting.

    ONE SETTING, TWO NAMES ACROSS THE SUPPORTED RANGE - `trend_fit_type` in 0.4.x, `fit_type` in
    0.5.x. Guessing wrong is a TypeError from inside a constructor; not passing it at all is
    worse, because then the dispersion model is whatever the installed version happens to default
    to and the report cannot name it. The signature is the only party that knows.
    """
    import inspect
    try:
        params = inspect.signature(cls.__init__).parameters
    except (TypeError, ValueError):                                       # pragma: no cover
        return {}, ""
    for name in FIT_TYPE_KEYWORDS:
        if name in params:
            return {name: want}, name
    return {}, ""


def _var_array(dds, name, np):
    """A per-gene array from a fitted DeseqDataSet, wherever this version keeps it.

    `dds.var` on 0.5.x, `dds.varm` on 0.4.x. Returns None when neither carries it, or when the
    length does not match the gene axis - and None is handled by refusing the panel with a
    reason, never by drawing a blank one.
    """
    for holder in ("var", "varm"):
        d = getattr(dds, holder, None)
        if d is None:
            continue
        try:
            if name not in d:
                continue
            arr = np.asarray(d[name], dtype=float).ravel()
        except Exception:                                                 # noqa: BLE001
            continue
        if arr.size == dds.n_vars:
            return arr
    return None


def _pseudobulk(ctx, np, pd):
    """Sum counts per (sample, population). Returns (matrix, obs, units) or (None, None, units).

    `units` carries EVERY (sample, population) that had a cell in it, including the ones too
    small to be summed, with the reason marked. A pseudobulk sample that was dropped and a
    pseudobulk sample that never existed are indistinguishable in a matrix, and only one of them
    is a statement about the data.
    """
    counts = ctx.counts()
    samp = ctx.obs("sample").astype(str).to_numpy()
    lab = ctx.obs("label").astype(str).to_numpy()
    real = np.asarray(ctx.real_cells())

    # SAID, NOT ASSUMED. A sentinel is the annotator declining to call a cell type, so it is not
    # a population and never a pseudobulk sample - but the number of cells that leaves has to be
    # on the page, because a population absent from the result and a population absent from the
    # annotation read the same way afterwards.
    set_aside = int((~real).sum())
    if set_aside:
        ctx.caveat(
            f"{set_aside:,} cell(s) carry an annotator sentinel and were not summed into any "
            f"pseudobulk sample. A sentinel is the annotator declining to call a cell type, so "
            f"it is not a population and cannot be a unit of replication; the cells stay in the "
            f"object and only the grouping excludes them.")

    keys = {}
    for i, (s, l) in enumerate(zip(samp, lab)):
        if not real[i]:
            continue
        keys.setdefault((s, l), []).append(i)

    rows, meta, units, small = [], [], [], 0
    for (s, l), idx in sorted(keys.items()):
        vec = np.asarray(counts[idx].sum(axis=0)).ravel()
        used = len(idx) >= ctx.config["min_cells"]
        units.append({"population": l, "sample": s, "n_cells": len(idx),
                      "total_counts": float(vec.sum()), "used": bool(used)})
        if not used:
            small += 1
            continue
        rows.append(vec)
        meta.append({"sample": s, "population": l, "n_cells": len(idx),
                     "total_counts": float(vec.sum())})
    if small:
        ctx.caveat(f"{small} (sample, population) combination(s) had fewer than "
                   f"{ctx.config['min_cells']} cells and were not summed into a pseudobulk "
                   f"sample. A handful of cells carrying a sample's name is noise, not a "
                   f"replicate. They are in figures/F1_replicates.csv with used=False.")
    unit_df = pd.DataFrame(units) if units else pd.DataFrame(
        columns=["population", "sample", "n_cells", "total_counts", "used"])
    if not rows:
        return None, None, unit_df
    return np.vstack(rows), pd.DataFrame(meta), unit_df


# ------------------------------------------------------------------------------------ figures
#
# NO BASIS ANYWHERE IN THIS FILE, and that is the shape of the method rather than a limitation.
# Nothing here is drawn on a cell embedding: the unit of this plugin is the pseudobulk sample,
# and every panel is a property of those samples, of the model fitted to them, or of the genes it
# returned. `ctx.layout()` is never called because there is nothing per-cell to place.
#
#   replicates   cells and library size per pseudobulk sample. The panel that decides whether
#                anything below it is a test rather than a comparison of two animals.
#   dispersion   the mean-variance trend the negative binomial rests on. DESeq2's own first
#                diagnostic, and the one that says whether the model fitted at all.
#   calibration  p-value histograms. The omnibus check: uniform under the null, and any other
#                shape is the model saying it is misspecified.
#   untested     what left the answer, and by which of the documented routes.
#   ma           the result, drawn so the unshrunken low-count fan is visible rather than implied.
#   hits         which populations responded, and which were never tested - two things that look
#                identical in a table of results.


def _grid(ctx, n, panel_h=1.5, ncol=3):
    """A constrained grid of at most `ncol` columns, and the flat axis list to fill.

    `layout="constrained"` because these grids carry a title and two axis labels in every panel:
    without it a row-two title lands on row-one's x-axis label, which is how a grid of panels
    becomes a grid of overlapping text.
    """
    F, plt = ctx.figure, ctx.plot()
    ncol = max(1, min(ncol, n))
    nrow = (n + ncol - 1) // ncol
    fig, axs = plt.subplots(nrow, ncol,
                            figsize=(F.SINGLE if ncol == 1 else F.DOUBLE, panel_h * nrow),
                            squeeze=False, layout="constrained")
    flat = list(axs.ravel())
    for ax in flat[n:]:
        ax.set_visible(False)
    return fig, flat[:n]


def _capped(items, cap=PANEL_CAP):
    """`(drawn, omitted)` - what fits in a grid, and what the caption then has to name."""
    return list(items[:cap]), list(items[cap:])


def _fig_replicates(ctx, units, term):
    """Cells and counts per pseudobulk sample, by the level being compared."""
    import numpy as np
    if not len(units):
        return
    F, plt = ctx.figure, ctx.plot()
    d = units.sort_values(["population", "sample"]).reset_index(drop=True)
    pops = sorted(d["population"].astype(str).unique())
    ypos = {p: i for i, p in enumerate(pops)}
    levels = sorted({str(x) for x in d["level"] if str(x)})
    cols = F.palette(levels) if levels else {}
    for _colour, labs in (F.palette_collisions(levels) if levels else []):
        ctx.caveat(f"{len(labs)} levels of {term} share one colour in F1_replicates "
                   f"({', '.join(labs)}); read those points from figures/F1_replicates.csv "
                   f"rather than from the panel.")

    # A DETERMINISTIC JITTER, not a random one. Several samples of one population sit on the same
    # row and would draw as one point; a seeded offset separates them and redraws identically.
    rng = np.random.default_rng(0)
    y = (np.array([ypos[str(p)] for p in d["population"]], dtype=float)
         + (rng.random(len(d)) - 0.5) * 0.55)
    fig, axs = plt.subplots(1, 2, figsize=(F.DOUBLE, max(1.9, 0.30 * len(pops) + 1.1)),
                            squeeze=False, sharey=True, layout="constrained")
    used = np.asarray(d["used"], dtype=bool)
    face = [cols.get(str(l), F.GREY) if u else F.GREY for l, u in zip(d["level"], used)]
    for ax, col, xlab in (
            (axs[0][0], "n_cells", "log10(cells in the pseudobulk sample + 1)"),
            (axs[0][1], "total_counts", "log10(counts in the pseudobulk sample + 1)")):
        v = np.log10(np.asarray(d[col], dtype=float) + 1.0)
        ax.scatter(v, y, s=11, c=face, linewidths=0.3, edgecolors=F.INK, rasterized=True)
        F.rasterize_points(ax)
        ax.set_xlabel(xlab)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axs[0][0].axvline(np.log10(float(ctx.config["min_cells"]) + 1.0), color=F.INK, ls="--", lw=0.6)
    axs[0][0].set_yticks(list(range(len(pops))))
    axs[0][0].set_yticklabels(pops)
    axs[0][0].invert_yaxis()
    axs[0][0].set_title("cells", loc="left")
    axs[0][1].set_title("library size", loc="left")

    import matplotlib.lines as ml
    h = [ml.Line2D([], [], marker="o", ls="", ms=3, color=cols[l], label=f"{term} = {l}")
         for l in levels]
    h.append(ml.Line2D([], [], marker="o", ls="", ms=3, color=F.GREY,
                       label=f"below min_cells ({ctx.config['min_cells']}), not summed"))
    F.legend_outside(fig, axs[0][1], h, [x.get_label() for x in h])
    n_drop = int((~used).sum())
    ctx.emit_figure(
        "F1_replicates", fig,
        caption=(f"One point per (sample, population): the cells summed into that pseudobulk "
                 f"sample, and the counts they carried. {len(d)} combination(s) across "
                 f"{len(pops)} population(s); {n_drop} fell below min_cells="
                 f"{ctx.config['min_cells']} and were not summed (grey, dashed line). Colour is "
                 f"the level of {term}. A population whose points separate by colour on EITHER "
                 f"axis has cell number or sequencing depth confounded with the factor being "
                 f"tested, and its fold changes are not a clean readout of expression. Both axes "
                 f"are log10 of the value plus one. Cells carrying an annotator sentinel are in "
                 f"no row here: a sentinel is not a population, and the count set aside is in "
                 f"the caveats."),
        source=d.set_index("population"))


def _fig_dispersion(ctx, disp, drawn, omitted):
    """Genewise, fitted and final dispersion against mean expression, per population."""
    import numpy as np
    if not len(disp) or not drawn:
        return
    F, _plt = ctx.figure, ctx.plot()
    fig, axes = _grid(ctx, len(drawn), panel_h=1.6)
    for ax, pop in zip(axes, drawn):
        s = disp[disp["population"] == pop]
        x = np.log10(np.asarray(s["baseMean"], dtype=float) + 1.0)
        for key, colour in (("dispersion_genewise", F.GREY), ("dispersion_final", "#0072B2")):
            v = np.asarray(s[key], dtype=float)
            ok = np.isfinite(v) & (v > 0) & np.isfinite(x)
            ax.scatter(x[ok], np.log10(v[ok]), s=2, c=colour, linewidths=0, rasterized=True)
        v = np.asarray(s["dispersion_fitted"], dtype=float)
        ok = np.isfinite(v) & (v > 0) & np.isfinite(x)
        order = np.argsort(x[ok])
        ax.plot(x[ok][order], np.log10(v[ok][order]), color="#D55E00", lw=0.9)
        F.rasterize_points(ax)
        ax.set_title(str(pop), loc="left")
        ax.set_xlabel("log10(baseMean + 1)")
        ax.set_ylabel("log10(dispersion)")
    import matplotlib.lines as ml
    h = [ml.Line2D([], [], marker="o", ls="", ms=3, color=F.GREY, label="genewise (MLE)"),
         ml.Line2D([], [], color="#D55E00", lw=1.0, label="fitted trend"),
         ml.Line2D([], [], marker="o", ls="", ms=3, color="#0072B2", label="final (shrunk)")]
    F.legend_outside(fig, axes[0], h, [x.get_label() for x in h])
    ctx.emit_figure(
        "F2_dispersion", fig,
        caption=(f"Per-gene dispersion against mean expression, for {len(drawn)} population(s)"
                 + (f" of {len(drawn) + len(omitted)}; not drawn: "
                    f"{', '.join(map(str, omitted))}" if omitted else "")
                 + f". Grey is each gene's own maximum-likelihood estimate, the line is the "
                 f"mean-dispersion trend the model fitted, and blue is the final estimate after "
                 f"shrinkage towards that line - blue is what every p-value below rests on. The "
                 f"expected shape is grey scattered around a falling trend with blue pulled onto "
                 f"it. Blue lying exactly on the line everywhere means shrinkage dominated and "
                 f"the genes contributed almost nothing; a flat trend means no mean-variance "
                 f"relationship was found, and `fit_type` is then the parameter to reconsider. "
                 f"Up to {DISPERSION_GENES:,} genes per population, sampled deterministically; "
                 f"the points drawn are exactly the rows of the source table."),
        source=disp.set_index("population"))


def _fig_pvalues(ctx, hist, drawn, omitted):
    """P-value histograms - the omnibus check that the test is calibrated."""
    import numpy as np
    if not len(hist) or not drawn:
        return
    F, _plt = ctx.figure, ctx.plot()
    fig, axes = _grid(ctx, len(drawn), panel_h=1.45)
    width = 1.0 / PVALUE_BINS
    for ax, (pop, term) in zip(axes, drawn):
        s = hist[(hist["population"] == pop) & (hist["term"] == term)]
        centres = np.asarray(s["bin_left"], dtype=float) + width / 2.0
        counts = np.asarray(s["n_genes"], dtype=float)
        ax.bar(centres, counts, width=width * 0.92, color="#0072B2", linewidth=0)
        expected = float(s["expected_if_uniform"].iloc[0]) if len(s) else 0.0
        ax.axhline(expected, color=F.INK, ls="--", lw=0.6)
        ax.set_title(f"{pop}\n{term}", loc="left")
        ax.set_xlim(0, 1)
        ax.set_xlabel("raw p-value")
        ax.set_ylabel("genes")
    ctx.emit_figure(
        "F3_pvalue_calibration", fig,
        caption=(f"Raw p-values in {PVALUE_BINS} equal bins, per population and term"
                 + (f" ({len(drawn)} of {len(drawn) + len(omitted)} shown; not drawn: "
                    f"{', '.join(f'{p} / {t}' for p, t in omitted)})" if omitted else "")
                 + ". The dashed line is what a bin would hold if every gene were null. Flat with "
                 "a spike in the leftmost bin is the shape a well-specified test produces when "
                 "something really changed; flat with no spike means nothing was detected, which "
                 "is a result. A slope rising towards 1, or a hump in the middle, means the "
                 "p-values are NOT uniform under the null - a covariate is missing from the "
                 "model, or the dispersions are mis-estimated - and the adjusted p-values cannot "
                 "then be read as a false-discovery rate. Genes with no p-value at all are "
                 "excluded here and counted in F4_untested."),
        source=hist.set_index("population"))


def _fig_untested(ctx, acct):
    """Where every gene went: into the answer, or out by one of the documented routes."""
    import numpy as np
    if not len(acct):
        return
    F, plt = ctx.figure, ctx.plot()
    # WORST FIRST, and the rest still in the source table. `genes_in_object` is the same for
    # every row, so ordering on `tested` ascending is ordering on the number of genes that LEFT
    # the answer descending - which is the question this panel was declared to answer.
    full = acct.reset_index(drop=True)
    d = full.sort_values("tested", ascending=True).head(BAR_ROWS).reset_index(drop=True)
    hidden = len(full) - len(d)
    rows = [f"{p} / {t}" for p, t in zip(d["population"], d["term"])]
    cols = F.palette(list(UNTESTED_REASONS))
    fig, ax = plt.subplots(figsize=(F.DOUBLE, max(1.7, 0.22 * len(d) + 1.0)),
                           layout="constrained")
    y = np.arange(len(d))
    left = np.zeros(len(d), dtype=float)
    for reason in UNTESTED_REASONS:
        v = np.asarray(d[reason], dtype=float)
        ax.barh(y, v, left=left, height=0.72, color=cols[reason], label=reason)
        left = left + v
    ax.set_yticks(y)
    ax.set_yticklabels(rows)
    ax.invert_yaxis()
    ax.set_xlabel("genes in the object")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    F.legend_outside(fig, ax)
    gone = int(sum(int(full[r].sum()) for r in UNTESTED_REASONS if r != "tested"))
    ctx.emit_figure(
        "F4_untested", fig,
        caption=(f"Every gene in the object, per population and term, by whether it reached the "
                 f"answer"
                 + (f". The {len(d)} combinations that lost the most genes are drawn; the "
                    f"accounting for all {len(full)} is in the source table"
                    if hidden else "")
                 + f". {gone:,} gene-tests did not reach it. `below min_counts` never entered "
                 f"the fit - a power decision made here, at min_counts="
                 f"{ctx.config['min_counts']}. `no "
                 f"counts` had a mean of zero, so DESeq2 returns NA in every column. `Cook's "
                 f"outlier` had an extreme count in one sample and had its p-value AND its "
                 f"adjusted p-value set to NaN. `independent filtering` was withheld an adjusted "
                 f"p-value only, to raise power at alpha={ctx.config['alpha']}. THE FIRST THREE "
                 f"WERE NOT TESTED: counting `padj < alpha` files all of them under 'not "
                 f"significant', which is wrong for every one. Only the `tested` band supports a "
                 f"negative result."),
        source=full.set_index("population"))


def _fig_ma(ctx, res, table_path, drawn, omitted):
    """Fold change against mean expression - the result, with its low-count fan left visible."""
    import numpy as np
    if not drawn:
        return
    F, _plt = ctx.figure, ctx.plot()
    alpha = float(ctx.config["alpha"])
    fig, axes = _grid(ctx, len(drawn), panel_h=1.55)
    n_sig = 0
    for ax, (pop, term) in zip(axes, drawn):
        s = res[(res["population"] == pop) & (res["term"] == term)]
        x = np.log10(np.asarray(s["baseMean"], dtype=float) + 1.0)
        lfc = np.asarray(s["log2FoldChange"], dtype=float)
        padj = np.asarray(s["padj"], dtype=float)
        sig = np.isfinite(padj) & (padj < alpha)
        ok = np.isfinite(x) & np.isfinite(lfc)
        ax.scatter(x[ok & ~sig], lfc[ok & ~sig], s=2, c=F.GREY, linewidths=0, rasterized=True)
        ax.scatter(x[ok & sig], lfc[ok & sig], s=3, c="#D55E00", linewidths=0, rasterized=True)
        n_sig += int((ok & sig).sum())
        ax.axhline(0.0, color=F.INK, lw=0.6)
        F.rasterize_points(ax)
        contrast = str(s["contrast"].iloc[0]) if len(s) else ""
        ax.set_title(f"{pop}\n{term}: {contrast}", loc="left")
        ax.set_xlabel("log10(baseMean + 1)")
        ax.set_ylabel("log2 fold change")

    # ONE SCALE ACROSS THE GRID. Every panel scaled itself, so a fold change of 2 was a different
    # height in each - and the only reason to draw nine panels together is to compare them. On
    # the report this was found in, the y-axes ran -10..5, -5..5 and -2.5..2.5 side by side, and
    # the panel with the LARGEST effects looked flattest.
    #
    # The limits are the union of what the panels hold, symmetric about zero on the fold-change
    # axis so up and down are the same distance, and no point is clipped out of view.
    _lo = min((float(np.nanmin(a.get_ylim())) for a in axes[:len(drawn)]), default=-1.0)
    _hi = max((float(np.nanmax(a.get_ylim())) for a in axes[:len(drawn)]), default=1.0)
    _r = max(abs(_lo), abs(_hi)) or 1.0
    _xhi = max((float(a.get_xlim()[1]) for a in axes[:len(drawn)]), default=1.0)
    for _a in axes[:len(drawn)]:
        _a.set_ylim(-_r, _r)
        _a.set_xlim(0.0, _xhi)
    ctx.emit_figure(
        "F5_ma", fig,
        caption=(f"One point per gene: mean normalised expression against log2 fold change, "
                 f"ONE SCALE ACROSS EVERY PANEL so the heights are comparable, with genes at "
                 f"padj < {alpha} in orange ({n_sig:,} across the panels shown)"
                 + (f". {len(drawn)} of {len(drawn) + len(omitted)} population-term combinations "
                    f"are drawn; not shown: "
                    f"{', '.join(f'{p} / {t}' for p, t in omitted)}" if omitted else "")
                 + ". THE FOLD CHANGES ARE UNSHRUNKEN. The widening fan at the left is not "
                 "biology - it is what a ratio does when both of its numbers are small - and it "
                 "is exactly what `lfc_shrink` exists to remove. Rank on the adjusted p-value; a "
                 "list of the largest fold changes from this table is a list of the "
                 "lowest-expressed genes. Numbers: tables/de_by_population.csv."),
        source=table_path)




def _interaction_estimable(ctx, obs, a, b):
    """Is `a:b` estimable here? THE SAME RANK TEST EVERY MAIN EFFECT ALREADY GETS.

    `_identifiable` asks it of each main effect, in the same dummy coding, and the interaction
    was appended to the formula without being asked at all. A population missing one cell of the
    a-by-b table then produced precisely the error that function exists to prevent -
    `numpy.linalg.LinAlgError: Singular matrix`, raised inside PyDESeq2's IRLS, after the fit had
    been paid for, and killing the whole plugin rather than the one population.

    It was invisible for as long as the plan's contrast never reached the run: with main effects
    only, nothing ever added an interaction column. The first cohort to be handed the decision
    the planner had been making all along was the first to hit it.

    THE RANK TEST ITSELF NOW LIVES IN THE HOST, because it is a fact about a DESIGN and not
    about differential expression. Asking `ctx.estimable` means the next plugin to fit a model
    gets the same answer without reimplementing it - and without repeating the omission above,
    which was not a mistake about interactions but about applying a check to every term.
    """
    return ctx.estimable(obs, [a, b, f"{a}:{b}"])


def _bh_across_families(res, alpha):
    """Benjamini-Hochberg over the RAW p-values of every family at once. A second number only.

    Applied to `pvalue`, never to `padj`: correcting an already-corrected column twice is not a
    joint correction, it is a smaller number with no interpretation at all. Genes that were not
    tested carry NaN and are excluded from m rather than counted as failures to reject - a NaN
    here means the gene was never a test, and inflating m with non-tests would make the joint
    figure conservative for a reason that has nothing to do with the design.
    """
    import numpy as np

    p = np.asarray(res["pvalue"], dtype=float)
    p = p[np.isfinite(p)]
    m = p.size
    if not m:
        return 0
    p.sort()
    thresh = alpha * np.arange(1, m + 1) / m
    below = np.nonzero(p <= thresh)[0]
    return int(below[-1] + 1) if below.size else 0


def _fig_hits(ctx, hits):
    """Which populations responded, and which were never tested - drawn on one axis."""
    import numpy as np
    if not len(hits):
        return
    F, plt = ctx.figure, ctx.plot()
    # NEVER-TESTED ROWS SORT FIRST and so can never be the ones a cap drops. They are the reason
    # this panel exists: a population that was tested and found flat and a population that was
    # never tested draw as the same empty row, and dropping the second to make room for a tested
    # one with two hits would delete the only place that distinction is visible.
    full = hits.reset_index(drop=True)
    full = full.assign(_rank=[(1 if t else 0, -(u + w))
                              for t, u, w in zip(full["tested"], full["n_up"], full["n_down"])])
    d = (full.sort_values("_rank").head(BAR_ROWS)
         .drop(columns="_rank").reset_index(drop=True))
    full = full.drop(columns="_rank")
    hidden = len(full) - len(d)
    rows = [f"{p} / {t}" if t else f"{p}" for p, t in zip(d["population"], d["term"])]
    fig, ax = plt.subplots(figsize=(F.DOUBLE, max(1.7, 0.22 * len(d) + 1.0)),
                           layout="constrained")
    y = np.arange(len(d))
    tested = np.asarray(d["tested"], dtype=bool)
    up = np.where(tested, np.asarray(d["n_up"], dtype=float), 0.0)
    down = np.where(tested, np.asarray(d["n_down"], dtype=float), 0.0)
    ax.barh(y, up, height=0.72, color="#D55E00", label="up in the second level")
    ax.barh(y, -down, height=0.72, color="#0072B2", label="down in the second level")
    ax.axvline(0.0, color=F.INK, lw=0.6)
    # A POPULATION THAT WAS NEVER TESTED IS MARKED, not left at zero. Zero hits and no test draw
    # as the same empty row, and they are opposite statements about the data.
    for i in np.where(~tested)[0]:
        ax.text(0.0, y[i], "  not tested", va="center", ha="left", color=F.GREY, fontsize=6)
    ax.set_yticks(y)
    ax.set_yticklabels(rows)
    ax.invert_yaxis()
    ax.set_xlabel(f"genes at padj < {ctx.config['alpha']}")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    F.legend_outside(fig, ax)
    n_untested = int((~np.asarray(full["tested"], dtype=bool)).sum())
    ctx.emit_figure(
        "F6_hits_by_population", fig,
        # IT SAYS WHAT IT COMPARES. Each term here IS a contrast between arms of the design -
        # that is what a term is - and the caption described the drawing without ever saying so,
        # which left the only figure on the page that compares the design looking like a summary
        # of counts.
        caption=(f"Genes changing across the design, per population and term, at "
                 f"padj < {ctx.config['alpha']} - one row per arm comparison, split by "
                 f"direction. The second level of each contrast is the numerator, and the "
                 f"contrast is named in the source table. "
                 + (f"The {len(d)} rows with the most genes are drawn, never-tested rows first; "
                    f"all {len(full)} are in the source table. " if hidden else "")
                 + (f"{n_untested} row(s) are marked NOT TESTED: no fit was run for them, so an "
                    f"empty row there is an absence of evidence and not evidence of absence. "
                    if n_untested else
                    "Every population shown was tested, so an empty row is a test that found "
                    "nothing. ")
                 + "A bar height is a count of genes at a threshold and is not an effect size: a "
                 "population with more pseudobulk samples has more power and shows more genes at "
                 "the same underlying change. Read it beside F1_replicates."),
        source=full.set_index("population"))


# ---------------------------------------------------------------------------------------- run

def run(ctx):
    import numpy as np
    import pandas as pd
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats

    C = ctx.config
    if C["fit_type"] not in FIT_TYPES:
        return ctx.refuse("differential expression",
                          f"fit_type={C['fit_type']!r} is not one of {', '.join(FIT_TYPES)}. The "
                          f"dispersion-mean model is what every p-value rests on, and an "
                          f"unrecognised name either raises from inside a constructor or leaves "
                          f"a model nobody chose.")
    # THE JOURNAL CONVENTIONS, APPLIED BEFORE ANYTHING IS FITTED. Not for the settings' sake: it
    # is the cheapest possible check that this environment can draw at all, and the alternative
    # is discovering a broken matplotlib backend after every population has been fitted.
    ctx.plot()

    design = ctx.design_table()
    if not design:
        return ctx.refuse("differential expression",
                          "the design table could not be read, so there is no contrast")

    terms = list((ctx.params.get("contrast") or {}).get("terms")
                 or ctx.testable_factors() or [])
    if not terms:
        return ctx.refuse("differential expression",
                          "no factor in the design has two levels with replication in each. A "
                          "test over singletons returns a p-value and no evidence.")

    mat, obs, units = _pseudobulk(ctx, np, pd)

    # F1 IS DRAWN BEFORE THE FIRST REFUSAL CAN HAPPEN, deliberately. If nothing has enough
    # replication to be tested, the replicate panel is the whole explanation of why - and a
    # refusal with no figure leaves the reader to take that explanation on trust.
    if len(units):
        units = units.copy()
        units["level"] = [str(design.get(s, {}).get(terms[0], ""))
                          for s in units["sample"].astype(str)]
        _fig_replicates(ctx, units, terms[0])

    if mat is None:
        return ctx.refuse("differential expression",
                          "no (sample, population) combination had enough cells to form a "
                          "pseudobulk sample")

    for t in terms:
        obs[t] = [str(design.get(s, {}).get(t, "")) for s in obs["sample"]]
    fit_kw, fit_kw_name = _fit_type_kwargs(DeseqDataSet, C["fit_type"])
    ctx.log(f"pseudobulk: {mat.shape[0]} sample-population rows x {mat.shape[1]:,} genes, "
            f"terms {', '.join(terms)}")
    ctx.log(f"dispersion model {C['fit_type']}"
            + (f", passed as `{fit_kw_name}`" if fit_kw_name else
               " - NOT PASSED, this build accepts neither keyword")
            + f"; min_replicates={C['min_replicates']}, cooks_filter={C['cooks_filter']}, "
              f"independent_filter={C['independent_filter']}")

    genes = np.asarray(ctx.adata.var_names).astype(str)
    n_genes_all = int(len(genes))
    out, skipped, dropped_terms = [], [], {}
    disp_frames, hist_rows, acct_rows, hit_rows = [], [], [], []
    no_disp, thin_refit, no_genes = [], [], []
    formulas, interacted, multi_level = {}, {}, {}
    not_interacted = {}          # the plan asked for an interaction this population cannot fit
    rng = np.random.default_rng(0)

    # A POPULATION THAT REACHED NO PSEUDOBULK SAMPLE AT ALL IS STILL A POPULATION, and it is the
    # one the loop below can never see: every unit of it fell under min_cells, so it is absent
    # from `obs` and no `hit_rows` entry was ever written for it. F6_hits_by_population is the
    # panel declared to answer WHICH POPULATIONS WERE NEVER TESTED, and it was silent about
    # exactly the populations that were most thoroughly not tested - while F1_replicates drew
    # them as grey points, so a reader could see the population exist and then fail to find it
    # on the results panel. Absent from a results table and tested-and-flat read identically.
    fitted_pops = {str(p) for p in obs["population"]}
    dropped_pops = (sorted({str(p) for p in units["population"]} - fitted_pops)
                    if len(units) else [])
    for p in dropped_pops:
        sel = units["population"].astype(str) == p
        hit_rows.append({"population": p, "term": "", "contrast": "",
                         "n_up": 0, "n_down": 0, "n_tested": 0, "tested": False,
                         "why_not": f"no (sample, population) unit reached "
                                    f"min_cells={C['min_cells']}"})
        ctx.absent.append({"what": f"differential expression for {p}",
                           "why": f"no sample reached min_cells={C['min_cells']} "
                                  f"({int(units.loc[sel, 'n_cells'].sum()):,} cells across "
                                  f"{int(sel.sum())} sample(s))"})
    if dropped_pops:
        ctx.caveat(
            f"{len(dropped_pops)} population(s) formed no pseudobulk sample at all, because "
            f"every (sample, population) unit of them fell below min_cells={C['min_cells']}: "
            + ", ".join(dropped_pops[:8])
            + (", and others" if len(dropped_pops) > 8 else "")
            + ". They are grey points in F1_replicates and rows marked NOT TESTED in "
              "F6_hits_by_population; the full list is in figures/F6_hits_by_population.csv.")

    for pop in sorted(set(obs["population"])):
        m = obs["population"].to_numpy() == pop
        sub_obs = obs[m].reset_index(drop=True)
        # EVERY LEVEL NEEDS REPLICATION, not just the population overall. A population with six
        # samples in one arm and one in the other supports no test of that contrast, and a mean
        # n hides exactly that.
        thin = [t for t in terms
                if sub_obs[t].value_counts().min() < C["min_samples_per_level"]
                or sub_obs[t].nunique() < 2]
        if thin:
            skipped.append((pop, int(m.sum()), thin))
            hit_rows.append({"population": pop, "term": "", "contrast": "",
                             "n_up": 0, "n_down": 0, "n_tested": 0, "tested": False,
                             "why_not": f"{', '.join(thin)} has a level with too few samples"})
            continue

        # IDENTIFIABLE FIRST. Otherwise the fit raises `Singular matrix` from inside numpy,
        # which is a true statement about linear algebra and tells the user nothing.
        use, aliased = _identifiable(ctx, sub_obs, terms)
        if not use:
            why = [t for t, _w in aliased]
            skipped.append((pop, int(m.sum()), why))
            hit_rows.append({"population": pop, "term": "", "contrast": "",
                             "n_up": 0, "n_down": 0, "n_tested": 0, "tested": False,
                             "why_not": f"every term is aliased: {', '.join(why)}"})
            continue
        if aliased:
            dropped_terms.setdefault(pop, aliased)

        sub = mat[m]
        keep = sub.sum(axis=0) >= C["min_counts"]
        # A POPULATION CAN LOSE EVERY GENE. Where its pseudobulk samples are shallow, nothing
        # reaches min_counts, and an empty matrix reaches PyDESeq2 as a shape error from inside
        # the fit - which names neither the population nor the threshold that emptied it.
        if not int(keep.sum()):
            no_genes.append((pop, int(m.sum())))
            hit_rows.append({"population": pop, "term": "", "contrast": "",
                             "n_up": 0, "n_down": 0, "n_tested": 0, "tested": False,
                             "why_not": f"no gene reached min_counts={C['min_counts']}"})
            continue
        kept_genes = genes[keep]
        counts_df = pd.DataFrame(np.rint(sub[:, keep]).astype(int),
                                 index=[f"s{i}" for i in range(int(m.sum()))],
                                 columns=kept_genes)
        sub_obs.index = counts_df.index

        # EVERY TERM IN `use` IS CONTRASTED BELOW, SO EVERY TERM HAS TO BE IN THE MODEL. The
        # interaction branch REPLACED the formula with `~ use[0] + use[1] + use[0]:use[1]`, which
        # silently dropped every term past the second and then asked PyDESeq2, in the loop below,
        # for a contrast on a variable its design matrix had never heard of. On three estimable
        # factors that is a KeyError from inside the library, raised per population after the fit
        # has already been paid for; on two it looked correct, which is why it shipped. The
        # interaction is now ADDED to the formula, never substituted for it.
        formula = "~ " + " + ".join(use)
        if len(use) >= 2 and (ctx.params.get("contrast") or {}).get("kind") == "interaction":
            # ASKED, NOT ASSUMED. See `_interaction_estimable`: the main effects are rank-tested
            # and the interaction was not, so a population with an empty cell of the a-by-b
            # table took down the entire plugin instead of dropping one term.
            if _interaction_estimable(ctx, sub_obs, use[0], use[1]):
                formula += f" + {use[0]}:{use[1]}"
                interacted[pop] = (use[0], use[1])
            else:
                not_interacted[pop] = (use[0], use[1])
        formulas.setdefault(formula, []).append(pop)
        dds = DeseqDataSet(counts=counts_df, metadata=sub_obs, design=formula,
                           refit_cooks=True, min_replicates=int(C["min_replicates"]),
                           n_cpus=ctx.cores, quiet=True, **fit_kw)
        dds.deseq2()

        # DID THE REFIT EVER HAPPEN HERE? `refit_cooks=True` reads as protection and is inert
        # below min_replicates samples in a level, at which point a Cook's outlier is dropped
        # from the answer rather than replaced. Measured per population, because the answer
        # differs per population as soon as the design is unbalanced.
        widest = max(int(sub_obs[t].value_counts().max()) for t in use)
        if widest < int(C["min_replicates"]):
            thin_refit.append((pop, widest))

        first_res = None
        for term in use:
            levels = sorted(sub_obs[term].unique())
            # ONE CONTRAST PER TERM, WHATEVER ITS NUMBER OF LEVELS. A three-level factor is
            # fitted whole - its middle levels move every coefficient - and then only its first
            # and last are compared, which is a defensible default and an indefensible silence:
            # `contrast` in the result table names the pair taken, and nothing named the pairs
            # NOT taken. Recorded here so the caveat can name them.
            if len(levels) > 2:
                multi_level[(pop, term)] = (str(levels[-1]), str(levels[0]),
                                            [str(x) for x in levels[1:-1]])
            st = DeseqStats(dds, contrast=[term, levels[-1], levels[0]],
                            alpha=C["alpha"],
                            cooks_filter=bool(C["cooks_filter"]),
                            independent_filter=bool(C["independent_filter"]),
                            quiet=True)
            st.summary()
            r = st.results_df.copy()
            r["population"], r["term"] = pop, term
            r["contrast"] = f"{levels[-1]} vs {levels[0]}"
            r["gene"] = r.index
            out.append(r)
            if first_res is None:
                first_res = r

            # WHERE EVERY GENE WENT. DESeq2's own documentation names the three routes out:
            # baseMean zero -> NA in every column; a Cook's-distance outlier -> pvalue AND padj
            # NA; independent filtering -> padj only.
            #
            # EACH STATE IS CONDITIONED ON THE ONES BEFORE IT, so the four PARTITION the genes
            # whatever the library returns. Written as four independent tests they overlapped:
            # a row with baseMean 0 and a finite padj counted as `no counts` AND as `tested`, and
            # a stacked bar of overlapping categories sums past its own total while looking
            # exactly like one that does not. DESeq2 should never emit that row - but a total
            # that is only correct while an upstream invariant holds is a total that reports a
            # library's change of behaviour as a change in the data.
            base = np.asarray(r["baseMean"], dtype=float)
            pv = np.asarray(r["pvalue"], dtype=float)
            pa = np.asarray(r["padj"], dtype=float)
            zero = ~np.isfinite(base) | (base <= 0)
            cooks_na = ~zero & ~np.isfinite(pv)
            indep_na = ~zero & np.isfinite(pv) & ~np.isfinite(pa)
            tested = ~zero & np.isfinite(pv) & np.isfinite(pa)
            acct_rows.append({
                "population": pop, "term": term,
                "tested": int(tested.sum()),
                "independent filtering": int(indep_na.sum()),
                "Cook's outlier": int(cooks_na.sum()),
                "no counts": int(zero.sum()),
                "below min_counts": int(n_genes_all - len(r)),
                "genes_in_object": n_genes_all,
            })

            # P-VALUE CALIBRATION, binned HERE rather than in the figure, so the panel and its
            # source table are the same numbers rather than two computations of them.
            finite = pv[np.isfinite(pv)]
            counted, edges = np.histogram(finite, bins=PVALUE_BINS, range=(0.0, 1.0))
            for lo, hi, n_in in zip(edges[:-1], edges[1:], counted):
                hist_rows.append({"population": pop, "term": term,
                                  "bin_left": float(lo), "bin_right": float(hi),
                                  "n_genes": int(n_in), "n_with_pvalue": int(finite.size),
                                  "expected_if_uniform": float(finite.size) / PVALUE_BINS})

            lfc = np.asarray(r["log2FoldChange"], dtype=float)
            sig = tested & (pa < C["alpha"])
            hit_rows.append({
                "population": pop, "term": term, "contrast": f"{levels[-1]} vs {levels[0]}",
                "n_up": int((sig & (lfc > 0)).sum()), "n_down": int((sig & (lfc < 0)).sum()),
                "n_tested": int(tested.sum()), "tested": True, "why_not": ""})


        # THE INTERACTION, CONTRASTED. It was added to the formula and never tested: the loop
        # above iterates the MAIN EFFECTS, so `age:diet` entered the design, changed every
        # coefficient in it, and produced no row of its own. The study's primary readout was in
        # the model and absent from the output, and the caveat said it had been added - which
        # was true, and read as though it had been tested.
        #
        # PyDESeq2 takes a contrast VECTOR the length of the design matrix, so the column is
        # selected by name from the matrix the fit actually built rather than by reconstructing
        # what formulaic would have called it.
        if pop in interacted:
            a_, b_ = interacted[pop]
            dm = dds.obsm.get("design_matrix")
            cols = list(dm.columns) if dm is not None else []
            hits = [c for c in cols if ":" in c and a_ in c and b_ in c]
            if len(hits) == 1:
                vec = np.zeros(len(cols), dtype=float)
                vec[cols.index(hits[0])] = 1.0
                sti = DeseqStats(dds, contrast=vec, alpha=C["alpha"],
                                 cooks_filter=bool(C["cooks_filter"]),
                                 independent_filter=bool(C["independent_filter"]),
                                 quiet=True)
                sti.summary()
                ri = sti.results_df.copy()
                ri["population"], ri["term"] = pop, f"{a_}:{b_}"
                ri["contrast"] = hits[0]
                ri["gene"] = ri.index
                out.append(ri)
                # AND INTO THE ACCOUNTING, or the term is in the table and in no figure. The
                # hits panel is built from `hit_rows`, so appending only to `out` put the
                # interaction in `de_by_population.csv` and left every panel showing the main
                # effects - the same shape of absence this whole change exists to end.
                _pa = np.asarray(ri["padj"], dtype=float)
                _lf = np.asarray(ri["log2FoldChange"], dtype=float)
                _te = np.isfinite(_pa)
                _sg = _te & (_pa < C["alpha"])
                hit_rows.append({
                    "population": pop, "term": f"{a_}:{b_}", "contrast": hits[0],
                    "n_up": int((_sg & (_lf > 0)).sum()),
                    "n_down": int((_sg & (_lf < 0)).sum()),
                    "n_tested": int(_te.sum()), "tested": True, "why_not": ""})
            else:
                # MORE THAN ONE COLUMN IS NOT ONE CONTRAST. A factor with three or more levels
                # spreads its interaction over several columns, and testing them together is an
                # F-test this does not do. Named rather than silently skipped.
                not_interacted.setdefault(pop, (a_, b_))
                interacted.pop(pop, None)

        # THE DISPERSION ARRAYS, wherever this version keeps them. See `_var_array`: they moved
        # between 0.4 and 0.5, and a missing one has to become a NAMED absence rather than a
        # panel that quietly stops being drawn.
        arrays = {k: _var_array(dds, k, np) for k in DISPERSION_KEYS}
        n_k = len(kept_genes)
        # BY POSITION, NOT BY GENE NAME. `results_df` is indexed by gene and var_names are not
        # guaranteed unique on a real object - `reindex` on a duplicated label raises, and it
        # would raise here, in the diagnostic, on a run whose fit had already succeeded. The
        # results rows are in the order of the columns they were built from, so position is both
        # correct and duplicate-safe; the lengths are asserted rather than assumed.
        bm = (np.asarray(first_res["baseMean"], dtype=float) if first_res is not None else None)
        if (first_res is None or bm is None or bm.size != n_k
                or any(v is None or v.size != n_k for v in arrays.values())):
            no_disp.append(pop)
        else:
            take = (np.arange(n_k) if n_k <= DISPERSION_GENES
                    else np.sort(rng.choice(n_k, size=DISPERSION_GENES, replace=False)))
            disp_frames.append(pd.DataFrame({
                "population": pop,
                "gene": kept_genes[take],
                "baseMean": bm[take],
                "dispersion_genewise": arrays["genewise_dispersions"][take],
                "dispersion_fitted": arrays["fitted_dispersions"][take],
                "dispersion_final": arrays["dispersions"][take],
            }))
        ctx.log(f"  {pop}: {int(m.sum())} pseudobulk samples, {int(keep.sum()):,} genes tested")

    if dropped_terms:
        ctx.caveat(
            "TERMS DROPPED FROM THE MODEL because they are not separately estimable from the "
            "ones kept: "
            + "; ".join(f"{p}: " + ", ".join(f"{t} ({w})" for t, w in a)
                        for p, a in sorted(dropped_terms.items()))
            + ". A term aliased with one already in the model adds no column the model does not "
              "have, and its coefficient would not have been interpretable in isolation. This is "
              "a property of the DESIGN, not of the data: name the terms you want with "
              "--params '{\"contrast\": {\"terms\": [...]}}' if this is not the split you "
              "meant.")
    if skipped:
        ctx.caveat("Not tested, because a level of the contrast had fewer than "
                   f"{C['min_samples_per_level']} samples: "
                   + "; ".join(f"{p} (n={n}, {', '.join(t)})" for p, n, t in skipped)
                   + ". They are drawn in F6_hits_by_population marked NOT TESTED, so an empty "
                     "row there cannot be read as a population that was tested and found flat.")
        for p, n, t in skipped:
            ctx.absent.append({"what": f"differential expression for {p}",
                               "why": f"{', '.join(t)} has a level with too few samples (n={n})"})
    if no_genes:
        ctx.caveat(
            f"Not tested, because no gene reached min_counts={C['min_counts']} summed across its "
            f"pseudobulk samples: "
            + "; ".join(f"{p} (n={n} samples)" for p, n in no_genes)
            + ". That is a statement about sequencing depth in those populations, not about "
              "their biology, and min_counts is set here rather than by the method.")
        for p, n in no_genes:
            ctx.absent.append({"what": f"differential expression for {p}",
                               "why": f"no gene reached min_counts={C['min_counts']} (n={n} "
                                      f"pseudobulk samples)"})
    if not out:
        # The one panel that needs no result is already on the page, and this one still can be:
        # a page whose every row says NOT TESTED is the clearest possible statement of what
        # happened, and it is unavailable to a reader who is given a refusal alone.
        _fig_hits(ctx, pd.DataFrame(hit_rows))
        # THE REFUSAL NAMES THE CAUSE IT MEASURED, not the first one anybody thought of. This
        # said "no population had replication in every level of any factor" whatever had
        # happened - so a run emptied by min_counts, or by min_cells, or by an unestimable
        # design, was reported to the user as a replication problem it did not have, and the
        # parameter that actually emptied it was never named.
        why = []
        if dropped_pops:
            why.append(f"{len(dropped_pops)} formed no pseudobulk sample at "
                       f"min_cells={C['min_cells']}")
        if skipped:
            why.append(f"{len(skipped)} had no term with replication in every level, or none "
                       f"estimable from the design")
        if no_genes:
            why.append(f"{len(no_genes)} had no gene reaching min_counts={C['min_counts']}")
        return ctx.refuse(
            "differential expression",
            ("no population could be fitted: " + "; ".join(why)) if why else
            "no population had replication in every level of any factor")

    res = pd.concat(out, ignore_index=True).sort_values(["population", "term", "padj"])
    table_path = ctx.emit_table("de_by_population", res.set_index("gene"))

    # ------------------------------------------------------------------------------ figures
    ctx.log("figures:")
    acct = pd.DataFrame(acct_rows)
    hist = pd.DataFrame(hist_rows)
    hits = pd.DataFrame(hit_rows)

    # WHICH PANELS A GRID CAN HOLD, decided on the number of tested genes rather than on name
    # order: the combinations a reader most needs to see are the ones with the most evidence in
    # them, and the ones that do not fit are NAMED in the caption rather than dropped.
    ranked = acct.sort_values("tested", ascending=False)
    order_pt = list(zip(ranked["population"].tolist(), ranked["term"].tolist()))
    drawn_pt, omitted_pt = _capped(order_pt)

    if disp_frames:
        disp = pd.concat(disp_frames, ignore_index=True)
        have = set(disp["population"].tolist())
        seen, order_p = set(), []
        for p in ranked["population"].tolist():
            if p in have and p not in seen:
                seen.add(p)
                order_p.append(p)
        drawn_p, omitted_p = _capped(order_p, cap=DISPERSION_PANEL_CAP)
        _fig_dispersion(ctx, disp[disp["population"].isin(drawn_p)], drawn_p, omitted_p)
    if no_disp:
        ctx.caveat(
            f"No dispersion panel for {len(no_disp)} population(s) "
            f"({', '.join(map(str, no_disp))}): this build of PyDESeq2 exposed no per-gene "
            f"dispersion array of the fitted length under either the `var` or the `varm` name. "
            f"The fit ran; what cannot be shown is the mean-variance trend it rests on.")

    _fig_pvalues(ctx, hist, drawn_pt, omitted_pt)
    _fig_untested(ctx, acct)
    _fig_ma(ctx, res, table_path, drawn_pt, omitted_pt)
    _fig_hits(ctx, hits)

    # ------------------------------------------------------------------------------ caveats
    sig = int((res["padj"] < C["alpha"]).sum())
    n_tested = int(acct["tested"].sum())
    n_no_padj = int(acct["independent filtering"].sum() + acct["Cook's outlier"].sum()
                    + acct["no counts"].sum())
    # TERMS, NOT A FORMULA. This read `formula ~ a + b`, which is a model this run may never
    # have fitted: the design is built PER POPULATION, an aliased term is dropped from some
    # populations and not others, and an interaction appears in the formula and in no term name.
    # A headline that prints a formula nobody fitted is wrong in the one place every reader looks.
    # THE CORRECTION SCOPE, BESIDE THE COUNT THAT AGGREGATES OVER IT.
    #
    # PyDESeq2 corrects WITHIN each population's own fit, and this count sums across all of
    # them - so it is a total over as many independent families as there are populations, and
    # neither the headline nor any caveat said so. "Apply multiple-testing correction jointly
    # across the whole comparison family, not separately per cell type, when the cell types are
    # tested in one design" is the standard the number will be read against.
    #
    # The per-population correction is KEPT, because it is what independent filtering and the
    # dispersion prior are computed under and re-deriving them jointly would be a different
    # analysis. What changes is that the joint number is computed and shown next to it, so a
    # reader is never left to assume the two are the same.
    n_families = int(res.groupby(["population", "term"]).ngroups)
    sig_joint = _bh_across_families(res, C["alpha"])
    ctx.headline = (f"{sig:,} gene-population-term results below padj {C['alpha']} "
                    f"across {res['population'].nunique()} population(s), "
                    f"terms {', '.join(sorted(set(res['term'])))}; "
                    f"{sig_joint:,} under one correction over all {n_families} families")
    ctx.caveat(
        f"TWO CORRECTIONS, AND THE HEADLINE CARRIES BOTH. The model is fitted per population, "
        f"so the `padj` column is corrected WITHIN each of the {n_families} population-term "
        f"families separately - and the count that sums across them, {sig:,}, is a total over "
        f"that many independent corrections rather than one. Correcting the raw p-values once "
        f"over all families together gives {sig_joint:,}. The per-family `padj` is kept in the "
        f"table because independent filtering and the dispersion prior are computed under it; "
        f"the joint number is here because a count reported across families is read as though "
        f"it came from one.")
    if formulas:
        ctx.caveat(
            "THE MODEL IS FITTED PER POPULATION and its formula is not necessarily the same for "
            "all of them, because a term aliased in one population can be estimable in another. "
            "Fitted here: "
            + "; ".join(f"`{f}` for {len(ps)} population(s)"
                        for f, ps in sorted(formulas.items()))
            + ". The headline names the terms tested, not one model.")
    if multi_level:
        items = sorted(multi_level.items())
        ctx.caveat(
            f"ONE CONTRAST PER FACTOR, AND {len(items)} population-term combination(s) have a "
            f"factor with MORE THAN TWO LEVELS: "
            + "; ".join(f"{p} / {t}: {hi} vs {lo}, never contrasted {', '.join(mid)}"
                        for (p, t), (hi, lo, mid) in items[:6])
            + (", and others" if len(items) > 6 else "")
            + ". The factor is fitted whole, so every level moves the coefficients, but only its "
              "first and last levels are compared. A population reported here as not responding "
              "was compared on ONE of that factor's contrasts, not on all of them; the pair "
              "taken is the `contrast` column of tables/de_by_population.csv.")
    if not_interacted:
        pairs_ni = sorted(set(not_interacted.values()))
        ctx.caveat(
            f"THE PLAN ASKED FOR AN INTERACTION THAT {len(not_interacted)} POPULATION(S) CANNOT "
            f"FIT, and those populations were fitted on main effects instead: "
            + "; ".join(
                f"{a}:{b} in "
                + ", ".join(sorted(q for q, v in not_interacted.items() if v == (a, b)))
                for a, b in pairs_ni)
            + ". The term is dropped where the design matrix would not be full rank - a cell of "
              "the two factors' table has no sample in that population - so the model there "
              "estimates the same main effects and no interaction. A population reported here "
              "as not responding to the interaction was NOT TESTED for one; the formula "
              "actually fitted per population is in the caveat above.")
    if interacted:
        pairs = sorted({v for v in interacted.values()})
        ctx.caveat(
            "AN INTERACTION IS IN THE MODEL AND IS NOT TESTED HERE. "
            + ", ".join(f"`{a}:{b}`" for a, b in pairs)
            + f" was added to the design for {len(interacted)} population(s) because the plan "
              f"asked for it. Two consequences, and neither is visible in the table: the "
              f"coefficient reported for each of its two main effects is CONDITIONAL - the "
              f"effect at the reference level of the other factor, not a marginal effect "
              f"averaged over it - so the same column name carries different numbers than it "
              f"would without the interaction; and the interaction coefficient itself is not "
              f"contrasted, so no gene here is reported as responding to it.")
    ctx.caveat("The unit of replication is the SAMPLE. Counts were summed per (sample, "
               "population) before testing, so no p-value here is inflated by cell count.")
    ctx.caveat(
        f"{n_tested:,} gene-tests carry an adjusted p-value and {n_no_padj:,} do not. A missing "
        f"padj is NOT a null result: DESeq2 withholds one when the gene has no counts at all, "
        f"when it carries a Cook's-distance outlier - in which case the raw p-value is withheld "
        f"too - and when independent filtering removed it for a low mean count. Only the last is "
        f"anything like 'too weak to call'. The split per population is in "
        f"figures/F4_untested.csv.")
    if thin_refit:
        ctx.caveat(
            f"`refit_cooks` DID NOTHING for {len(thin_refit)} population(s) - "
            + ", ".join(f"{p} (widest level: {w} samples)" for p, w in thin_refit[:8])
            + (", and others" if len(thin_refit) > 8 else "")
            + f". PyDESeq2 refits an outlier count only where a level reaches min_replicates="
              f"{C['min_replicates']} samples. Below that nothing is replaced, and "
            + ("`cooks_filter` removes the gene's p-value and adjusted p-value instead - so a "
               "single extreme sample takes the gene out of the answer rather than being "
               "corrected for."
               if C["cooks_filter"] else
               "`cooks_filter` is off, so those genes keep a p-value that one extreme sample may "
               "be carrying."))
    ctx.caveat(
        f"Dispersion was fitted with fit_type={C['fit_type']!r}"
        + (f", passed explicitly as `{fit_kw_name}`." if fit_kw_name else
           " - which this build accepts under NEITHER `fit_type` nor `trend_fit_type`, so the "
           "installed default was used and this run cannot state which model that was.")
        + " Independent filtering is "
        + (f"ON, so which genes carry an adjusted p-value at all depends on alpha={C['alpha']}: "
           f"changing alpha changes the denominator, not only the line."
           if C["independent_filter"] else
           "OFF, so every gene with a p-value carries an adjusted one, and power at the same "
           "alpha is lower than PyDESeq2's default would give."))
    ctx.caveat(
        "Fold changes are UNSHRUNKEN - no lfc_shrink was applied - so log2FoldChange at low "
        "baseMean is dominated by sampling noise. F5_ma draws that fan rather than hiding it; "
        "rank on padj, not on fold change.")
    if ctx.constraint:
        ctx.caveat(f"The object carries an upstream constraint on use, and it applies to this "
                   f"result as much as to any other: {ctx.constraint}")


def selftest(ctx):
    """Prove the call works: the API, the schema, and that a planted effect is recovered.

    A test that only asserted the table has rows would pass on a broken model. The fixture plants
    a real fold-change in a known set of genes and requires them back, because that is what would
    break silently if PyDESeq2's contrast argument or results schema moved.
    """
    import numpy as np
    import pandas as pd
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats

    rng = np.random.default_rng(0)
    n_s, n_g = 8, 200
    base = rng.integers(50, 500, size=n_g)
    cond = np.array(["ctrl"] * 4 + ["treat"] * 4)
    up = np.arange(20)                                  # the planted effect
    mat = np.vstack([rng.poisson(base * (1 + 3.0 * np.isin(np.arange(n_g), up) * (c == "treat")))
                     for c in cond])
    counts = pd.DataFrame(mat.astype(int), index=[f"s{i}" for i in range(n_s)],
                          columns=[f"g{j}" for j in range(n_g)])
    meta = pd.DataFrame({"cond": cond}, index=counts.index)

    # THE KEYWORD IS RESOLVED, NOT ASSUMED, and the selftest is where that has to be proved:
    # `fit_type` is `trend_fit_type` on the older half of the supported range, and a wrong guess
    # is a TypeError inside a constructor on somebody else's machine.
    fit_kw, fit_kw_name = _fit_type_kwargs(DeseqDataSet, "parametric")
    ctx.log(f"  dispersion keyword: {fit_kw_name or 'NEITHER NAME ACCEPTED'}")
    assert fit_kw_name, ("this PyDESeq2 accepts neither `fit_type` nor `trend_fit_type`. The "
                         "dispersion model would be whatever it defaults to, and no run could "
                         "state which one it used.")

    dds = DeseqDataSet(counts=counts, metadata=meta, design="~ cond",
                       min_replicates=7, quiet=True, **fit_kw)
    dds.deseq2()
    st = DeseqStats(dds, contrast=["cond", "treat", "ctrl"],
                    cooks_filter=True, independent_filter=True, quiet=True)
    st.summary()
    r = st.results_df
    for col in ("baseMean", "log2FoldChange", "pvalue", "padj"):
        assert col in r.columns, f"results_df has no {col!r}; PyDESeq2's schema moved"
    assert len(r) == n_g, f"{len(r)} rows for {n_g} genes"

    hits = set(r[r["padj"] < 0.05].index)
    planted = {f"g{j}" for j in up}
    found = len(hits & planted)
    assert found >= 15, (
        f"only {found} of 20 planted genes were recovered. The model ran and did not find an "
        f"effect built into the fixture - either the contrast argument changed meaning or the "
        f"fit is wrong, and both would return a full, plausible, empty table on real data.")
    assert (r.loc[sorted(planted), "log2FoldChange"] > 0).mean() > 0.9, \
        "the planted genes came back with the wrong SIGN - the contrast is inverted"
    ctx.log(f"  recovered {found}/20 planted genes, correct sign")

    # THE ARRAYS THE DISPERSION PANEL IS DRAWN FROM. They live in `dds.varm` on 0.4.x and in
    # `dds.var` on 0.5.x, and a reader of one finds nothing on the other - which is not an error,
    # it is a diagnostic that stops being drawn on a run that otherwise looks complete.
    missing = [k for k in DISPERSION_KEYS if _var_array(dds, k, np) is None]
    ctx.log(f"  dispersion arrays found: {len(DISPERSION_KEYS) - len(missing)}"
            f"/{len(DISPERSION_KEYS)}"
            + (f"  (absent: {', '.join(missing)})" if missing else ""))
    assert not missing, (
        f"no per-gene {', '.join(missing)} under either `var` or `varm`. F2_dispersion would be "
        f"reported absent on every run in this environment.")

    # The figure path is part of this plugin and part of the environment: matplotlib has a
    # backend, and nothing in the fit above exercises it.
    plt = ctx.plot()
    F = ctx.figure
    fig, axs = plt.subplots(1, 2, figsize=(F.DOUBLE, 1.6), squeeze=False, layout="constrained")
    axs[0][0].scatter([0.0, 1.0], [0.0, 1.0], s=2, c=F.GREY, linewidths=0, rasterized=True)
    axs[0][1].barh([0, 1], [1.0, 2.0], height=0.72, color="#0072B2")
    F.rasterize_points(axs[0][0])
    plt.close(fig)
    ctx.log("  ok   the figure path imports and draws")
