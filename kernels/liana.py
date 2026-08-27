"""Cell–cell communication: a ranked ligand–receptor table, per unit.

NO INTERACTION IS OBSERVED. These are co-expression of a ligand and a receptor in two
populations, with no spatial information — on dissociated tissue the two cells may never have
touched. That is the first thing in `cannot_show` and the first thing the result says.

It runs PER UNIT because an inference pooled over a cohort describes the average of its
conditions and may describe none of them. The host fans it out; this file sees one unit.

WHAT THE PAGE HAS TO SAY BEFORE THE TABLE MEANS ANYTHING

Three things decide this result and none of them is visible in a ranked table of interactions.

  the RESOURCE reaching the object   Every score is computed over interactions whose genes are
                                     in `var_names`. On an object whose genes were filtered
                                     upstream, most of the resource is simply not there, and the
                                     surviving table is a property of that filter. liana refuses
                                     only past 98% missing; at 60% it returns a full, plausible
                                     answer.
  the POPULATIONS                    Scores are per label. Populations below `min_cells` are
                                     dropped inside liana before anything is scored, and the
                                     number of interactions a population appears in is bounded
                                     by how many cells it has.
  the METHODS DISAGREEING            `rank_aggregate` is a consensus over five scoring methods,
                                     and the benchmark that produced this tool found the overlap
                                     between their top-ranked interactions to be low (Dimitrov
                                     et al., Nat Commun 2022). A consensus over methods that
                                     disagree is still a number.

So the `report` block declares those three as diagnostics, ahead of the two result panels, and
the reporter puts them in that order. A ranked interaction under an unchecked resource coverage
is a name, not a finding.
"""

PLUGIN = {
    "api": 1,
    "version": "0.2.0",
    "summary": "cell-cell communication, consensus over several scoring methods",
    "when_to_use": "you want a ligand-receptor map and, with a design, how it differs between "
                   "conditions",
    "wraps": {"tool": "liana", "homepage": "https://liana-py.readthedocs.io",
              "license": "GPL-3.0",
              "cite": "Dimitrov et al., Nat Commun 2022 (LIANA); "
                      "Türei et al., Mol Syst Biol 2021 (OmniPath)"},
    "upstream": {
        "docs": "https://liana-py.readthedocs.io",
        "read": "2026-08-25",
        "defaults_changed": [
            "resource_name is chosen BY ORGANISM. The default is `consensus`, which is HUMAN, "
            "and a human resource on non-human symbols does not error - it returns a small, "
            "plausible table. That is the failure this plugin exists to avoid.",
            "use_raw=False. The default follows .raw, which on an annotated object usually holds "
            "pre-filter counts - a different matrix from the one the user is looking at.",
            "expr_prop is exposed as config rather than left at the library default, because it "
            "decides how many interactions survive and is the knob people actually turn.",
            "n_perms is 1000 - liana's OWN default - and is passed explicitly. This plugin passed "
            "100, which reads as a speed setting and is a RESOLUTION one: a permutation p-value "
            "cannot be smaller than 1/n_perms, so every specificity p-value bottomed out at 0.01 "
            "and the specificity half of the consensus was flatter than the data.",
            "min_cells is passed explicitly at liana's own default of 5, because it REMOVES "
            "populations rather than parameterising a score: `prep_check_adata` drops every cell "
            "identity with fewer cells than this before anything is scored, and says so only at "
            "verbose=True. The populations it drops are named in the caveats and drawn in "
            "F2_population_support instead of being absent without explanation.",
            "de_method is passed explicitly at liana's default 't-test'. It is the 1-vs-rest test "
            "(scanpy's rank_genes_groups) behind the statistics the specificity scores are built "
            "from, so it decides half of the consensus and was being inherited invisibly.",
            "verbose=True, against liana's default of False. Its own warnings are the ones worth "
            "having - non-normalised input, empty features removed, cell identities excluded, a "
            "var name that collides with the complex separator - and at the default every one of "
            "them is silent.",
            "n_jobs is the host's ALLOCATED core share rather than liana's serial default of 1.",
            "seed is fixed rather than left at liana's 1337, so a re-run of the same unit "
            "reproduces. Permutation p-values move with the seed; the value itself means nothing.",
        ],
        "not_used": [
            "The single-method calls (cellphonedb, natmi, ...). rank_aggregate runs them and "
            "aggregates, which is the point of the tool; using one alone is a different claim.",
            "liana's spatial functions - this object carries no spatial information.",
            "return_all_lrs. It would return every interaction with the WORST surviving score "
            "substituted for the ones that failed expr_prop, which is a filtered result wearing "
            "an unfiltered shape. What was filtered is reported instead, by name, in "
            "F1_resource_coverage.",
            "liana's own plotting (li.pl). It returns plotnine objects, not matplotlib figures, "
            "so it cannot carry this tool's journal conventions or its source data.",
        ],
        "gotchas": [
            "rank_aggregate REFUSES when more than 98% of the resource's genes are missing from "
            "var_names. That check is correct and is the signature of a resource for the wrong "
            "organism; it is reported as a refusal rather than caught and hidden.",
            "Ligand and receptor transcripts are partly cytoplasmic, so a single-nucleus "
            "preparation reports fewer of them and a low interaction count is as consistent with "
            "the assay as with the biology.",
            "IT DOES NOT REFUSE COUNTS. `prep_check_adata` sums the first 100 STORED values of "
            "the matrix and, if that sum is a whole number, prints `Make sure that normalized "
            "counts are passed!` - a warning, and only at verbose=True. Counts scored as though "
            "they were log-normalised return a complete, plausible, differently-ranked table.",
            "The min_cells removal is silent at the default verbosity. A population below it is "
            "not scored, not named, and not distinguishable in the output from a population that "
            "was scored and found to communicate with nothing.",
            "An all-zero gene is REMOVED inside liana; an all-zero cell is only warned about. The "
            "two look the same in the log and are not the same in the result.",
            "A gene symbol containing `_` cannot be told from a two-subunit complex, because `_` "
            "is the complex separator. `check_vars` warns and continues, so such a gene is "
            "quietly unavailable to every interaction that needs it.",
            "Two of the five aggregated methods report the SAME magnitude column - `expr_prod`, "
            "from Connectome and NATMI - so any agreement measured between score columns shows "
            "one 1.00 that is an identity rather than a consensus.",
            "A score's orientation is not in its name. `cellphone_pvals` is low-is-strong and "
            "`expr_prod` is high-is-strong, so a correlation computed over the raw columns "
            "reports disagreement where there is agreement. liana declares the orientation of "
            "every score it produces (`get_method_scores`, and the per-method specs on the "
            "aggregate); this plugin reads it from there rather than assuming it.",
        ],
    },

    "inject": {"required": ["lognorm", "label", "organism"], "optional": ["sample"]},
    "provides": ["communication"],
    "produces": ["tables/ccc_edges.csv"],
    # WHAT WAS SHOWN TO IT, so the plan can say which of a user's own layers and columns this
    # plugin will touch. It reads no embedding and no layout: the panels below are dotplots and
    # matrices, and there is no basis in this result to draw on.
    "sees": ["layers[{lognorm}]", "obs[{label}]"],
    "per_unit": "sample",

    "config": {
        "expr_prop": {"type": "float", "default": 0.1, "min": 0.0, "max": 1.0,
                      "help": "a gene must be expressed in this proportion of a population to "
                              "count; it decides how many interactions survive"},
        "min_cells": {"type": "int", "default": 5, "min": 0,
                      "help": "liana's own default. A population with fewer cells than this is "
                              "EXCLUDED from the inference entirely - not scored badly, absent. "
                              "Which populations that removes is reported"},
        "n_perms": {"type": "int", "default": 1000, "min": 1,
                    "help": "liana's own default. Permutations behind the specificity p-values: "
                            "the smallest p-value obtainable is 1/n_perms, so a low value flattens "
                            "the specificity half of the consensus rather than only speeding it up"},
        "de_method": {"type": "str", "default": "t-test",
                      "help": "liana's own default. The 1-vs-rest test (scanpy's "
                              "rank_genes_groups) behind the statistics the specificity scores "
                              "use; 't-test', 't-test_overestim_var', 'wilcoxon' or 'logreg'"},
        "top_n": {"type": "int", "default": 0, "min": 0,
                  "help": "keep only this many top-ranked interactions, 0 for all. The full "
                          "table is the honest artifact; this is for a figure"},
    },

    # BUNDLED IN THE WHEEL, and constrained by a RANGE in `requires` - so which version of the
    # resource a run used is recorded in the result's caveats and by nothing else. Declared so
    # the tool can say that, rather than reporting a plugin that consults no reference data.
    "references": {
        "consensus": {"tier": "bundled", "organism": "human", "role": "interactions",
                      "package": "liana", "cite": "Dimitrov et al., Nat Commun 2022; "
                                                  "Turei et al., Mol Syst Biol 2021",
                      "source": "https://github.com/saezlab/liana-py",
                      "note": "assembled from OmniPath, ships in the wheel, loads offline - "
                              "which is what lets this plugin run in a batch job"},
        "mouseconsensus": {"tier": "bundled", "organism": "mouse", "role": "interactions",
                           "package": "liana", "cite": "Dimitrov et al., Nat Commun 2022; "
                                                       "Turei et al., Mol Syst Biol 2021",
                           "source": "https://github.com/saezlab/liana-py",
                           "note": "assembled from OmniPath, ships in the wheel, loads offline"},
    },

    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {"matplotlib": ">=3.6,<4", "liana": ">=1.3,<2", "scanpy": ">=1.10,<1.11",
                     "anndata": ">=0.10,<0.12", "numpy": ">=1.24,<2", "pandas": ">=2.0,<3"},
    },

    "cost": "medium", "cores": 8,

    # Measured, not estimated: fitted from this plugin's own instances in one run on a 10-sample mouse single-nucleus cohort (~99k cells). ONE dataset on ONE machine - a starting point that is right for scheduling, not a universal constant. Every run re-fits and prints its own.
    # Fitted from ten per-sample instances.
    "memory_gb_base": 3.1, "memory_gb_per_100k": 5.5,

    # WHAT ITS PAGE SHOULD CONTAIN. Diagnostics first, and here that ordering is the whole point:
    # the three checks below decide whether the ranked table underneath them is about the biology
    # or about the gene filter, the cluster sizes and a disagreement between scoring methods.
    #
    # `shows` is the whole of the reporter's knowledge. It knows no id here and never will.
    "report": {
        # WHAT MAKES THE UNITS COMPARABLE. Every figure on this page describes ONE unit; these
        # are the numbers the host puts on a shared axis, so a reader sees whether the units
        # agree before reading any single unit's panel as a finding.
        "unit_metrics": [
            {"id": "interactions", "question": "how many interactions did this unit yield, and how far apart are the units?"},
            {"id": "populations", "question": "how many populations passed min_cells in this unit? A unit contributing fewer populations can only produce fewer interactions."},
        ],
        "figures": [
            {"id": "F1_resource_coverage", "shows": "diagnostic", "required": True,
             "question": "how much of the ligand-receptor resource could this object ever have "
                         "shown, and what removed the rest?",
             "source": "figures/F1_resource_coverage.csv"},
            {"id": "F2_population_support", "shows": "diagnostic", "required": True,
             "question": "did every population have enough cells to be scored, and does a "
                         "population's interaction count just track how many cells it has?",
             "source": "figures/F2_population_support.csv"},
            # OPTIONAL, AND THE ABSENCE IS THE FINDING. The consensus is only a consensus while
            # there are several scores to agree; with one, the page must say that rather than
            # show a correlation of a column with itself.
            {"id": "F3_method_agreement", "shows": "diagnostic", "required": False,
             "question": "do the scoring methods behind the consensus agree on which "
                         "interactions matter?",
             "source": "figures/F3_method_agreement.csv",
             "when_absent": "fewer than two of the aggregated methods' score columns survived in "
                            "the result with any variation in them, so there was nothing to "
                            "compare. Read the consensus rank below as one method's answer, not "
                            "as agreement between several."},
            {"id": "F4_dotplot", "shows": "result", "required": True,
             "question": "which ligand-receptor pairs are inferred, between which populations, "
                         "and are they strong, specific, or both?",
             "source": "figures/F4_dotplot.csv"},
            {"id": "F5_sender_receiver", "shows": "result", "required": True,
             "question": "which populations are inferred to signal to which, and how one-sided "
                         "is it?",
             "source": "figures/F5_sender_receiver.csv"},
        ],
        # THE PAIRING. A second plugin answers the same question from its own database and its own
        # scoring, and the benchmark behind this tool is precisely that two such answers overlap
        # less than a reader expects. Declared so the reporter can name the missing half as an
        # absence; neither plugin can draw the comparison alone.
        "reads_with": ["cellchat"],
    },

    "cannot_show": [
        "NO INTERACTION IS OBSERVED. These are co-expression of a ligand and a receptor in two "
        "populations, with no spatial information - on dissociated tissue the cells may never "
        "have touched. Co-occurrence standing in for a communication event is the core assumption "
        "of the whole method family, and it is what spatial coordinates are used to constrain "
        "(Fischer et al., Nat Biotechnol 2022).",
        "A rank is WITHIN this dataset. It is not a strength comparable to another dataset's.",
        "The resource decides the answer. On the wrong organism it does not error; it returns a "
        "small plausible table.",
        "THE ANSWER IS A PROPERTY OF THE ANNOTATION. Every score is computed between labels, so "
        "merging or splitting one population changes every interaction it appears in. There is no "
        "reading of this output that is independent of how the cells were grouped.",
        "A p-value here is a PERMUTATION p-value over shuffled cell labels. It says an "
        "interaction is specific to this pair of populations relative to that shuffling - not "
        "that it happens - and its resolution is 1/n_perms.",
        "AN INTERACTION MISSING FROM THE TABLE WAS NOT TESTED AND FOUND WEAK. Interactions below "
        "expr_prop, and interactions whose genes are not in this object, are absent rather than "
        "low-ranked. F1_resource_coverage is the only place their number appears.",
        "Ligand and receptor transcripts are partly cytoplasmic, so a single-nucleus preparation "
        "reports fewer of them and a low count is as consistent with the assay as with biology.",
    ],
}

#: Resource per organism. Anything not here is refused rather than defaulted to the human one.
_RESOURCE = {"human": "consensus", "mouse": "mouseconsensus"}

#: How liana joins the subunits of a protein complex. It is `DefaultValues.complex_sep` in
#: liana's own constants, repeated here because the coverage panel has to split what liana
#: joined - and because a gene symbol that CONTAINS it cannot be told from a complex.
_COMPLEX_SEP = "_"

#: Fixed so that a re-run of the same unit reproduces. liana's own default is 1337; the value
#: means nothing, having one does.
_SEED = 0

#: Rows the dotplot can carry before the interaction labels stop being readable at 6 pt.
_DOT_ROWS = 25

#: The name `_score_columns` files a column the AGGREGATE itself wrote under, as opposed to one
#: of the methods being aggregated. Not a method name: `magnitude_rank` and `specificity_rank`
#: are the consensus, and a panel that correlates them with the columns they were computed from -
#: or with each other - reports arithmetic and calls it agreement.
_CONSENSUS = "consensus"

#: The three fates of an interaction in the resource, in the order they happen. Written once
#: because the figure, the table and the caveats all have to agree about them.
_ABSENT = "genes absent from this object"
_BELOW = "below expr_prop in every population"
_EXPRESSED = "above expr_prop somewhere"


# ------------------------------------------------------------------------------------ helpers

def _subunits(entity):
    """The gene symbols a complex is made of. `"A_B"` is two subunits; `"A"` is one."""
    return [p for p in str(entity).split(_COMPLEX_SEP) if p]


def _detection(X, labels, names):
    """Per population, the fraction of its cells with a non-zero value in each gene.

    This is the quantity `expr_prop` is compared against, computed here rather than read out of
    liana, because it has to be known for interactions liana never returns - the ones the filter
    removed. Non-zero rather than positive, so a matrix carrying negatives is not silently
    counted as undetected.
    """
    import numpy as np
    props = np.zeros((len(names), X.shape[1]), dtype="float32")
    counts = []
    for i, nm in enumerate(names):
        m = np.asarray(labels) == nm
        n = int(m.sum())
        counts.append(n)
        if not n:
            continue
        nz = np.asarray((X[m] != 0).sum(axis=0)).ravel()
        props[i] = nz / float(n)
    return props, counts


def _coverage(resource, var_names, props, expr_prop):
    """One row per interaction in the resource: could this object ever have shown it?

    The three fates are exhaustive and are computed the way liana computes them - a complex needs
    every subunit, and the proportion of a complex IN ONE POPULATION is the MINIMUM over its
    subunits. An interaction is reachable iff its ligand clears expr_prop in some population and
    its receptor clears it in some population, because every ordered pair of populations is
    scored.

    THE ORDER OF THE MIN AND THE MAX IS THE WHOLE CALCULATION, and it was the wrong way round.
    This took the maximum over populations per SUBUNIT and then the minimum over subunits, which
    is an upper bound on the quantity liana thresholds rather than the quantity itself: a
    two-subunit ligand whose two subunits are expressed in two DIFFERENT populations scored 1.00
    and was reported reachable, although no population carries the complex and liana can never
    score it. Measured on a three-gene example, `A_B -> R` with A only in one population and B
    only in the other came back `above expr_prop somewhere`. The minimum over subunits has to be
    taken FIRST, within each population, and the maximum over populations after - which is also
    what the `*_max_proportion` columns have always claimed to hold. It matters twice over
    because F1_resource_coverage's caption reads any gap between its step 3 and its step 4 as
    something liana removed, and this made part of that gap the plugin's own arithmetic.

    `props` is (the populations that will actually be scored) x (genes), in `var_names` order.
    """
    import numpy as np
    import pandas as pd
    idx = {str(g): j for j, g in enumerate(map(str, var_names))}
    P = np.asarray(props, dtype="float64")
    if P.ndim == 1:                          # a single population, handed as a vector
        P = P[None, :]
    rows, seen = [], set()
    for lig, rec in zip(resource["ligand"], resource["receptor"]):
        key = (str(lig), str(rec))
        if key in seen:
            continue
        seen.add(key)
        lsub, rsub = _subunits(lig), _subunits(rec)
        if not lsub or not rsub:
            continue
        missing = [s for s in lsub + rsub if s not in idx]
        if missing:
            lp = rp = float("nan")
            stage = _ABSENT
        else:
            lp = float(P[:, [idx[s] for s in lsub]].min(axis=1).max())
            rp = float(P[:, [idx[s] for s in rsub]].min(axis=1).max())
            stage = _EXPRESSED if min(lp, rp) >= expr_prop else _BELOW
        rows.append({"ligand_complex": key[0], "receptor_complex": key[1],
                     "n_subunits": len(lsub) + len(rsub),
                     "subunits_absent": ";".join(missing),
                     "ligand_max_proportion": lp, "receptor_max_proportion": rp,
                     "stage": stage})
    # THE COLUMNS ARE NAMED even when there are no rows. An empty frame built from an empty list
    # has no columns at all, and every reader below indexes one by name - so a resource that came
    # back empty would fail as a KeyError about `stage` rather than as an empty resource.
    return pd.DataFrame(rows, columns=["ligand_complex", "receptor_complex", "n_subunits",
                                       "subunits_absent", "ligand_max_proportion",
                                       "receptor_max_proportion", "stage"])


def _score_columns(li):
    """`{column: (lower_is_stronger, [methods])}` - liana's own declaration of its scores.

    ASKED, NOT ASSUMED. Every method registers the column it writes and whether that column
    ascends, and the aggregate carries the per-method specs; a plugin hard-coding the orientation
    of `cellphone_pvals` is a plugin that will keep hard-coding it after the schema moves. Two
    routes because both exist in the versions this plugin supports, and an empty dict is a
    legitimate answer that costs one optional panel.

    THE CONSENSUS IS TAGGED, NOT MIXED IN. `magnitude_rank` and `specificity_rank` are what
    rank_aggregate WROTE, not evidence about it, and they are recorded under the single method
    name `_CONSENSUS` so every consumer can tell the result from its inputs. They used to arrive
    looking like two more methods, with two consequences that were both silent: the agreement
    panel could correlate the consensus with itself and call that method agreement, and the
    `if not out` fallback below could never fire, because those two entries had already been put
    in `out` above it.
    """
    out = {}
    ra = getattr(getattr(li, "mt", None), "rank_aggregate", None)
    # THE AGGREGATE'S OWN COLUMNS ARE RESOLVED FIRST, so a per-method spec can never be filed
    # under one of them whichever order liana declares things in.
    aggregate = {}
    for which in ("magnitude", "specificity"):
        col = getattr(ra, which, None)
        if col:
            aggregate[str(col)] = bool(getattr(ra, f"{which}_ascending", True))
    for attr in ("magnitude_specs", "specificity_specs"):
        specs = getattr(ra, attr, None)
        # `specs or {}` ASKS FOR A TRUTH VALUE, which a frame or an array refuses to give - and
        # this runs outside any figure's try, so it would take the whole result with it.
        if not isinstance(specs, dict):
            continue
        for meth, spec in specs.items():
            try:
                col, ascending = spec[0], bool(spec[1])
            except Exception:                                             # noqa: BLE001
                continue
            # A METHOD MAY DECLARE NO SCORE OF ONE KIND - liana's logfc has no magnitude - and
            # `str(None)` made a column literally called "None" that no result ever carries.
            if not col or str(col) in aggregate:
                continue
            out.setdefault(str(col), (ascending, []))[1].append(str(meth))
    if not out:
        getter = getattr(getattr(li, "mt", None), "get_method_scores", None)
        try:
            declared = getter() if callable(getter) else None
        except Exception:                                                 # noqa: BLE001
            declared = None
        for col, ascending in (declared if isinstance(declared, dict) else {}).items():
            if not col or str(col) in aggregate:
                continue
            try:
                out.setdefault(str(col), (bool(ascending), []))
            except Exception:                                             # noqa: BLE001
                continue
    for col, ascending in aggregate.items():
        out.setdefault(col, (ascending, [_CONSENSUS]))
    return out


def _looks_like_counts(X):
    """Are the stored values whole numbers? Then this is not a log-normalised matrix.

    liana asks the same question of the first 100 stored values and answers it with a warning
    that its own default verbosity suppresses. Asked here over more of them, and answered where
    a reader of the result will see it.
    """
    import numpy as np
    # `.nnz` IS THE TEST FOR SPARSENESS, not `.data`. Every numpy array has a `.data` attribute -
    # it is the memoryview of the buffer - so asking for one and finding it does not mean this is
    # a sparse matrix, and treating a dense matrix's buffer as a sparse matrix's stored values
    # walks the whole object instead of a slice of it.
    data = getattr(X, "data", None) if hasattr(X, "nnz") else None
    # BOUNDED BEFORE ANYTHING IS FILTERED. A boolean mask over a real cohort's matrix allocates
    # another matrix; the slice is taken first, so this check costs the same on any object.
    v = np.asarray(data[:200_000]) if data is not None else np.asarray(X[:200]).ravel()
    v = v[v != 0][:5000]
    if not v.size:
        return False
    return bool(np.all(np.isfinite(v)) and np.all(v == np.floor(v)))


def _spearman(frame):
    """Spearman over the columns, as Pearson on ranks - which is what it is.

    `DataFrame.corr(method="spearman")` reaches for scipy, and scipy is not in this plugin's
    declared requirement. Ranking first needs nothing that is not already here.
    """
    return frame.rank().corr()


def _draw(ctx, what, fn, *a):
    """Draw one panel, or say which one could not be drawn and why.

    A panel that raises must not take the result with it - the table and every other panel are
    unaffected - and it must not vanish quietly either. `figure_drift` reports a declared panel
    that was not emitted to the maintainer; this caveat reports it to the reader, who is the one
    looking at the page with a gap in it.
    """
    try:
        return fn(ctx, *a)
    except Exception as e:                                                # noqa: BLE001
        ctx.log(f"    {what} not drawn: {type(e).__name__}: {e}")
        ctx.caveat(f"{what} could not be drawn ({type(e).__name__}: {e}). The page states it as "
                   f"not produced; the numbers behind the other panels are unaffected.")
        return None


# ------------------------------------------------------------------------------------ figures
#
# Five panels: three checks on whether this method could have worked on this object, then the two
# that are the answer. There is no basis to draw on - a communication result lives between
# labels, not on a manifold - so these are dotplots, bars and matrices.

def _fig_coverage(ctx, cov, res_name, expr_prop, min_cells):
    """The funnel from the resource to the result. Every step is a filter, and every filter is
    invisible in the ranked table underneath it."""
    import numpy as np
    F, plt = ctx.figure, ctx.plot()
    steps = [("in the resource", len(cov), "#0072B2"),
             ("genes present here", int((cov["stage"] != _ABSENT).sum()), "#56B4E9"),
             (f"above expr_prop {expr_prop:g}", int((cov["stage"] == _EXPRESSED).sum()),
              "#E69F00"),
             ("scored in the result", int(cov["in_result"].sum()), "#009E73")]
    fig, ax = plt.subplots(figsize=(F.SINGLE, 1.9))
    y = np.arange(len(steps))
    ax.barh(y, [v for _n, v, _c in steps], height=0.68, color=[c for _n, _v, c in steps])
    for yy, (_n, v, _c) in zip(y, steps):
        ax.text(v, yy, f" {v:,}", va="center", ha="left", fontsize=6)
    ax.set_yticks(y)
    ax.set_yticklabels([n for n, _v, _c in steps])
    ax.invert_yaxis()
    ax.set_xlim(0, max([v for _n, v, _c in steps] + [1]) * 1.22)
    ax.set_xlabel("ligand-receptor interactions")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ctx.emit_figure(
        "F1_resource_coverage", fig,
        caption=(f"How much of the {res_name!r} resource this object could ever have shown. Each "
                 f"step removes interactions from every panel below it, and none of those "
                 f"removals is visible in the ranked table. Step 2 is a property of the gene "
                 f"list: on an object whose genes were filtered upstream, most of the resource is "
                 f"not absent from the biology but from var_names. Step 3 is expr_prop "
                 f"({expr_prop:g}), applied as liana applies it - a complex takes the smallest "
                 f"proportion of its subunits, and an interaction is reachable if its ligand "
                 f"clears the threshold in some population and its receptor in some population. "
                 f"Steps 3 and 4 should agree; a gap between them is something liana's own "
                 f"preparation removed as well - an all-zero gene, or a population below "
                 f"min_cells={min_cells}. The source table names every interaction and which step "
                 f"it was lost at."),
        source=cov.set_index("ligand_complex"))


def _fig_population_support(ctx, per_pop, min_cells, colours):
    """Cell number per population beside what it bought - the confound, drawn."""
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()
    d = per_pop.sort_values("n_cells", ascending=False)
    fig, axs = plt.subplots(1, 2, figsize=(F.DOUBLE, max(1.8, 0.20 * len(d) + 1.1)),
                            layout="constrained")
    y = np.arange(len(d))
    axs[0].barh(y, d["n_cells"], height=0.72,
                color=[(colours.get(p, F.GREY) if e else F.GREY)
                       for p, e in zip(d.index, d["entered_inference"])])
    if int(min_cells) > 0:
        axs[0].axvline(float(min_cells), color=F.INK, ls="--", lw=0.6)
    axs[0].set_yticks(y)
    axs[0].set_yticklabels(d.index)
    axs[0].invert_yaxis()
    axs[0].set_xlabel("cells")
    axs[0].set_title(f"population size (dashed: min_cells={min_cells})", loc="left")
    axs[0].spines["left"].set_visible(False)
    axs[0].tick_params(axis="y", length=0)

    ax = axs[1]
    ax.scatter(d["n_cells"], d["interactions_as_sender"], s=14, linewidths=0,
               c=[(colours.get(p, F.GREY) if e else F.GREY)
                  for p, e in zip(d.index, d["entered_inference"])])
    F.rasterize_points(ax)
    ax.set_xlabel("cells in the population")
    ax.set_ylabel("interactions where it is the sender")
    rho, why = float("nan"), "too few populations to correlate"
    if len(d) >= 5:
        r = _spearman(pd.DataFrame({"a": d["n_cells"].astype(float),
                                    "b": d["interactions_as_sender"].astype(float)}))
        rho, why = float(r.iloc[0, 1]), "no variation to correlate"
    ax.set_title("interactions against size"
                 + (f"  (Spearman rho {rho:+.2f})" if np.isfinite(rho) else f"  ({why})"),
                 loc="left")
    if len(d) <= 8:
        for p, xx, yy in zip(d.index, d["n_cells"], d["interactions_as_sender"]):
            ax.annotate(str(p), (xx, yy), fontsize=5, xytext=(2, 2),
                        textcoords="offset points")
    ctx.emit_figure(
        "F2_population_support", fig,
        caption=("Left: how many cells each population brought, against the min_cells threshold "
                 "below which liana drops a population from the inference entirely - a dropped "
                 "population is absent from the result, not ranked low in it, and is drawn grey "
                 "here. Right: the number of interactions a population sends, against its size. A "
                 "strong positive relation means the ranking is partly a picture of the "
                 "annotation's cell numbers; the populations are coloured as on the left. Both "
                 "panels count only real calls - annotator sentinels are not populations. The "
                 "source table adds how many genes were detected in each population, which is the "
                 "other half of the same confound."),
        source=d)


def _fig_method_agreement(ctx, full, scores):
    """Do the METHODS being aggregated agree? Returns True when the panel was drawn."""
    import pandas as pd
    cols, ordered = {}, []
    for col, (ascending, methods) in sorted(scores.items()):
        # THE CONSENSUS IS NOT EVIDENCE ABOUT THE CONSENSUS. `magnitude_rank` and
        # `specificity_rank` are what rank_aggregate wrote FROM the columns beside them here, so
        # a correlation with them is arithmetic wearing the label of method agreement. Keeping
        # them also made this panel's `required: False` a fiction: liana returns those two on
        # every run, so the `< 2` test below passed on them alone, the declared `when_absent`
        # sentence could never be printed, and a page could show a 2x2 matrix of the result
        # against itself under the question "do the scoring methods agree?".
        if list(methods) == [_CONSENSUS] or col not in full.columns:
            continue
        s = pd.to_numeric(full[col], errors="coerce").astype(float)
        if int(s.notna().sum()) < 3 or int(s.nunique(dropna=True)) < 2:
            continue
        # ORIENTED SO THAT HIGHER IS STRONGER, from liana's own declaration. Without it the
        # low-is-strong scores anti-correlate with the high-is-strong ones and the panel reports
        # disagreement between methods that agree.
        cols[col] = (-s if ascending else s)
        ordered.append((col, methods))
    if len(cols) < 2:
        return False
    R = _spearman(pd.DataFrame(cols))
    n = len(R)
    F, plt = ctx.figure, ctx.plot()
    side = max(2.2, 0.36 * n + 1.3)
    fig, ax = plt.subplots(figsize=(min(F.DOUBLE, side + 1.0), side), layout="constrained")
    im = ax.imshow(R.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(n))
    ax.set_xticklabels(R.columns, rotation=90)
    ax.set_yticks(range(n))
    ax.set_yticklabels(R.index)
    for i in range(n):
        for j in range(n):
            v = float(R.values[i, j])
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=5,
                    color="white" if abs(v) > 0.6 else F.INK)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label("Spearman rho")
    named = "; ".join(f"{c} ({', '.join(m)})" if m else c for c, m in ordered)
    ctx.emit_figure(
        "F3_method_agreement", fig,
        caption=(f"Agreement between the scores the consensus is built from, over all "
                 f"{len(full):,} scored interactions. Every column is oriented from liana's own "
                 f"declaration so that higher means stronger, which is why a low-is-strong score "
                 f"like a permutation p-value does not appear as disagreement. Columns: {named}. "
                 f"It is one row per SCORE COLUMN rather than per method: where two methods report "
                 f"the same column they appear once, because a correlation between them would be "
                 f"an identity and not a consensus. For the same reason the consensus's own "
                 f"magnitude_rank and specificity_rank are NOT rows here - they are what these "
                 f"columns were aggregated into, and a result correlated with its own inputs "
                 f"measures the aggregation. The benchmark this tool came from found the "
                 f"overlap between "
                 f"methods' top-ranked interactions low (Dimitrov et al., Nat Commun 2022): "
                 f"where these correlations are weak, the consensus rank is an average over "
                 f"methods that do not agree, and an interaction supported by only one of them is "
                 f"the weaker claim."),
        source=R)
    return True


def _fig_dotplot(ctx, full):
    """The canonical ligand-receptor dotplot: colour is strength, size is specificity."""
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()
    # COERCED, NOT CAST, and ranked over the rows that CAN be ranked. `nsmallest` keeps NaN rows
    # once there are fewer non-NaN rows than asked for, so a non-finite magnitude_rank reached
    # `c=` as a NaN colour and drew an invisible dot - an interaction removed from the panel with
    # nothing anywhere saying so.
    mr = pd.to_numeric(full["magnitude_rank"], errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(mr)
    if not ok.any():
        raise ValueError("every magnitude_rank is non-finite, so no interaction can be ranked")
    ranked = full[ok].copy()
    # THE COERCED VALUES GO BACK INTO THE FRAME, or `nsmallest` sorts the original column and
    # refuses an object dtype outright - which is the whole case the coercion was added for.
    ranked["magnitude_rank"] = mr[ok]
    top = ranked.nsmallest(min(_DOT_ROWS, len(ranked)), "magnitude_rank").copy()
    top["interaction"] = (top["ligand_complex"].astype(str) + " -> "
                          + top["receptor_complex"].astype(str))
    top["pair"] = top["source"].astype(str) + " -> " + top["target"].astype(str)
    ys = list(dict.fromkeys(top["interaction"]))
    xs = sorted(set(top["pair"].tolist()))
    # A RANK HERE IS PROBABILITY-LIKE AND SMALL IS STRONG, so both are inverted to be drawn. The
    # clip is what stops a rank of exactly zero becoming an infinite dot.
    mag = -np.log10(np.clip(top["magnitude_rank"].to_numpy(dtype=float), 1e-12, None))
    # SIZE DEGRADES, IT DOES NOT TAKE THE PANEL WITH IT. `specificity_rank` is asserted by the
    # selftest, so its absence is real schema drift - but F4 is a REQUIRED result panel, and one
    # missing column turning it into a gap on the page is a worse answer than one dimension of it
    # going constant with the caption saying so.
    has_spec = "specificity_rank" in top.columns
    spec = (-np.log10(np.clip(pd.to_numeric(top["specificity_rank"], errors="coerce")
                              .to_numpy(dtype=float), 1e-12, None))
            if has_spec else np.full(len(top), np.nan))
    finite = np.isfinite(spec)
    n_nospec = int((~finite).sum())
    lo, hi = ((float(np.nanmin(spec)), float(np.nanmax(spec))) if finite.any() else (0.0, 0.0))
    if not (np.isfinite(lo) and np.isfinite(hi)):
        # A NaN marker size draws nothing and reports nothing. One constant size and a caption
        # that still says what size means is the honest degradation.
        lo = hi = 0.0
    size = 8.0 + 52.0 * ((spec - lo) / (hi - lo) if hi > lo else np.zeros_like(spec))
    # THE SAME DEGRADATION, ONE ROW AT A TIME. The branch above only caught the case where EVERY
    # specificity was missing; a few missing among many left those dots at size NaN, which draws
    # nothing at all, and the caption below now says how many.
    size = np.where(np.isfinite(size), size, 8.0)
    fig, ax = plt.subplots(figsize=(min(F.DOUBLE, max(3.2, 0.32 * len(xs) + 2.6)),
                                    max(2.0, 0.17 * len(ys) + 1.4)), layout="constrained")
    ax.set_axisbelow(True)
    ax.grid(True, lw=0.3, color=F.GREY)
    pts = ax.scatter([xs.index(p) for p in top["pair"]],
                     [ys.index(i) for i in top["interaction"]],
                     c=mag, s=size, cmap="viridis", linewidths=0)
    F.rasterize_points(ax)
    ax.set_xticks(range(len(xs)))
    # SHORTENED TO THE SHORTEST UNAMBIGUOUS TAIL. These categories are PAIRS of
    # annotation paths, sixty characters before a real name is reached, and rotated
    # ninety degrees they took three quarters of the figure height - squeezing the
    # data into a strip. The full path stays in the source table.
    _short = F.short_labels(list(xs))
    ax.set_xticklabels([_short[x] for x in xs], rotation=90)
    ax.set_yticks(range(len(ys)))
    ax.set_yticklabels(ys)
    ax.set_xlim(-0.6, len(xs) - 0.4)
    ax.set_ylim(len(ys) - 0.4, -0.6)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(pts, ax=ax, orientation="horizontal", location="top", fraction=0.05, pad=0.04)
    cb.outline.set_visible(False)
    cb.set_label("-log10 magnitude_rank  (expression strength)")
    # THE SCATTER'S OWN LEGEND, not a second formula. This built Line2D handles with
    # `ms=sqrt(8 + 52*t)` - markersize in POINTS - to stand for a scatter sized by `s`, which is
    # an AREA in points squared. Two formulas for one mapping, kept in step by hand, and the
    # legend drew three markers that overlapped into a single blob in the margin: a size key a
    # reader cannot read is worse than none, because the panel's size channel then means nothing.
    #
    # `legend_elements` derives the handles FROM the artist, so the key cannot disagree with the
    # dots it explains, whatever the size formula becomes later.
    try:
        handles, labels = pts.legend_elements(prop="sizes", num=3, alpha=0.8)
        _rng = (hi - lo) or 1.0
        labels = [f"{lo + _rng * i / max(1, len(handles) - 1):.1f}"
                  for i in range(len(handles))]
    except Exception:                                                     # noqa: BLE001
        handles, labels = [], []
    if handles:
        # TRUE SIZE. This legend IS the size key; scaling its markers would say something
        # false about every dot it explains.
        F.legend_outside(fig, ax, handles, labels, markerscale=1.0)
    ctx.emit_figure(
        "F4_dotplot", fig,
        caption=(f"The {len(ys)} highest-ranked interactions by magnitude, and the sender -> "
                 f"receiver pairs they were ranked in. Colour is the aggregated MAGNITUDE rank - "
                 f"how strongly the ligand and receptor are expressed - and size is the "
                 f"aggregated SPECIFICITY rank, how much this pair of populations stands out "
                 f"against a shuffled labelling. Both are shown as -log10, so larger and brighter "
                 f"is stronger. They are different claims: a large pale dot is specific to these "
                 f"populations without being strongly expressed, and a small bright dot is "
                 f"strongly expressed everywhere. A BLANK CELL has two causes and they are "
                 f"different: the interaction did not pass expr_prop for that pair, so it was "
                 f"never scored, or it was scored and ranked below this panel's cut. "
                 f"tables/ccc_edges.csv tells the two apart. The legend is the size key; the "
                 f"source table is the {len(top):,} rows drawn."
                 + (" The returned table carries NO specificity_rank column, so every dot is one "
                    "constant size and size means nothing here - only colour is being read."
                    if not has_spec else
                    (f" {n_nospec:,} of them carry no specificity value and are drawn at the "
                     f"smallest size, so their size means ABSENT rather than unspecific."
                     if n_nospec else ""))),
        source=top.set_index("interaction"))


def _fig_sender_receiver(ctx, full, names):
    """Who talks to whom, as counts. The dotplot's population axis, summed."""
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()
    src_lab, tgt_lab = full["source"].astype(str), full["target"].astype(str)
    mat = pd.crosstab(src_lab, tgt_lab)
    # THE AXIS IS THE UNION, not the populations this plugin expected. `reindex` DROPS a label it
    # is not handed, so any population liana scored that this plugin's own min_cells arithmetic
    # had written off would have disappeared from the matrix - silently, under a caption that
    # states a count. The expected populations lead, so an unexpected one is visible at the end.
    axis = list(dict.fromkeys([str(x) for x in names]
                              + sorted(set(src_lab) | set(tgt_lab))))
    mat = mat.reindex(index=axis, columns=axis, fill_value=0)
    mat.index.name, mat.columns.name = "sender", "receiver"
    n = len(axis)
    side = max(2.3, 0.34 * n + 1.3)
    fig, ax = plt.subplots(figsize=(min(F.DOUBLE, side + 1.0), side), layout="constrained")
    im = ax.imshow(mat.values, cmap="viridis", vmin=0)
    ax.set_xticks(range(n))
    # SHORTENED TO THE SHORTEST UNAMBIGUOUS TAIL. These categories are PAIRS of
    # annotation paths, sixty characters before a real name is reached, and rotated
    # ninety degrees they took three quarters of the figure height - squeezing the
    # data into a strip. The full path stays in the source table.
    _short = F.short_labels(list(mat.columns) + list(mat.index))
    ax.set_xticklabels([_short[c] for c in mat.columns], rotation=90)
    ax.set_yticks(range(n))
    ax.set_yticklabels([_short[i] for i in mat.index])
    ax.set_xlabel("receiver")
    ax.set_ylabel("sender")
    if n <= 12:
        big = float(np.nanmax(mat.values)) if mat.values.size else 0.0
        for i in range(n):
            for j in range(n):
                v = int(mat.values[i, j])
                ax.text(j, i, f"{v}", ha="center", va="center", fontsize=5,
                        color="white" if v < 0.6 * big else F.INK)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label("interactions")
    ctx.emit_figure(
        "F5_sender_receiver", fig,
        caption=("How many interactions survived between each ordered pair of populations. This "
                 "is a COUNT, not a strength: a pair with many weak interactions outranks a pair "
                 "with one strong one, and the count is bounded by how many cells and how many "
                 "genes each population brought - read it beside F2_population_support. The "
                 "matrix is directed, so the two triangles are different questions, and the "
                 "diagonal is a population inferred to signal to itself. A row of zeros is a "
                 "population that passed min_cells and sent nothing."),
        source=mat)


# ---------------------------------------------------------------------------------------- run

def run(ctx):
    import numpy as np
    import pandas as pd
    import liana as li

    C = ctx.config
    res_name = _RESOURCE.get(ctx.organism)
    if not res_name:
        return ctx.refuse(
            "cell-cell communication",
            f"no ligand-receptor resource is declared for {ctx.organism!r}. The default resource "
            f"is human and would return a small plausible table on other symbols rather than "
            f"failing. Known: {', '.join(sorted(_RESOURCE))}.")

    # `ctx.populations()` unpacks as (mask, groups); `.names` and `.dropped` are what this wants.
    # It read the two-tuple as (populations, dropped), so `len(pops)` was the CELL COUNT - the
    # refusal below could never fire and the headline would have claimed one population per cell -
    # and `if dropped:` asked the truth value of a numpy array, which raises. Fourth plugin to
    # misread it, which is a statement about the affordance and not about four authors.
    pop = ctx.populations()
    if len(pop.names) < 2:
        return ctx.refuse("cell-cell communication",
                          f"only {len(pop.names)} population(s) here; communication needs at "
                          f"least two to be between.")
    if pop.dropped:
        # THE NUMBER SET ASIDE IS A NUMBER OF CELLS. `len(pop.dropped)` is how many DISTINCT
        # sentinel labels the annotator used - two, on most objects - and reporting it beside the
        # words "excluded as senders and receivers" reads as two cells rather than as thousands.
        n_sentinel = int((~np.asarray(pop.mask)).sum())
        ctx.caveat(f"{n_sentinel:,} cell(s) carrying an annotator sentinel were excluded as "
                   f"senders and receivers before anything was scored: "
                   f"{', '.join(pop.dropped)}. A sentinel is a refusal to call a cell type, and "
                   f"an interaction attributed to one names nothing.")

    # The journal conventions, applied before anything is spent - and the cheapest possible check
    # that this environment can draw at all. The alternative is discovering a broken matplotlib
    # backend after the permutations have run.
    ctx.plot()

    lab = ctx.keys["label"]
    A = ctx.adata[ctx.real_cells()].copy()
    # THE LOG-NORMALISED MATRIX OF THE SUBSET OBJECT. This was `A.X = ctx.X if ctx.X.shape[0] ==
    # A.n_obs else A.X`, and the fallback fired exactly when it mattered: `ctx.X` is the whole
    # object's matrix, so on any object carrying a sentinel the shapes differ and `A.X` was
    # whatever `.X` happened to be - counts, on the objects that keep lognorm in a layer. The
    # layer is already subset here, so there is no shape to reconcile.
    lognorm = ctx.keys.get("lognorm")
    if lognorm and lognorm in A.layers:
        A.X = A.layers[lognorm]
        x_src = f"layers[{lognorm!r}]"
    else:
        x_src = "X as delivered"

    labels = np.asarray(pop.groups)
    names = list(pop.names)
    props, counts = _detection(A.X, labels, names)
    per_pop = pd.DataFrame({"n_cells": counts,
                            "genes_detected": (props > 0).sum(axis=1).astype(int)},
                           index=pd.Index(names, name="population"))
    per_pop["entered_inference"] = per_pop["n_cells"] >= int(C["min_cells"])
    small = list(per_pop.index[~per_pop["entered_inference"]])
    kept = list(per_pop.index[per_pop["entered_inference"]])
    ctx.log(f"{A.n_obs:,} cells, {len(names)} populations, resource {res_name}, {x_src}")
    if len(kept) < 2:
        return ctx.refuse(
            "cell-cell communication",
            f"only {len(kept)} population(s) reach min_cells={C['min_cells']}; liana drops the "
            f"rest before scoring, and communication needs at least two to be between.\n"
            f"  Below the threshold: "
            + ", ".join(f"{p} ({int(per_pop.loc[p, 'n_cells'])})" for p in small[:12])
            + "\n  Fix: --params '{\"min_cells\": <n>}', or group the cells more coarsely.")

    # The reachability of an interaction is decided by the populations that will actually be
    # scored, so the populations liana is about to drop are dropped here too. The whole
    # per-population matrix is handed over, not its column maximum: a complex has to be reduced
    # to its smallest subunit WITHIN a population before the populations are compared, and doing
    # it the other way round reports a complex as reachable when its subunits live in two
    # different populations. See `_coverage`.
    kept_set = set(kept)
    keep_rows = [i for i, nm in enumerate(names) if nm in kept_set]
    scored_props = props[keep_rows]

    resource = li.resource.select_resource(res_name)
    cov = _coverage(resource, A.var_names, scored_props, float(C["expr_prop"]))

    li.mt.rank_aggregate(A, groupby=lab, resource_name=res_name,
                         expr_prop=float(C["expr_prop"]),
                         min_cells=int(C["min_cells"]),
                         de_method=str(C["de_method"]),
                         n_perms=int(C["n_perms"]),
                         n_jobs=ctx.cores,
                         use_raw=False, verbose=True, seed=_SEED)
    full = A.uns["liana_res"].copy()
    ctx.log(f"{len(full):,} scored interactions over {len(kept)} population(s)")

    scored = set(zip(full["ligand_complex"].astype(str), full["receptor_complex"].astype(str)))
    cov["in_result"] = [(l, r) in scored
                        for l, r in zip(cov["ligand_complex"], cov["receptor_complex"])]

    # DRAWN BEFORE THE EMPTINESS CHECK, because an empty result is exactly the case where this
    # panel is the whole answer: it says whether the resource ever reached the object.
    ctx.log("figures:")
    _draw(ctx, "F1_resource_coverage", _fig_coverage, cov, res_name, float(C["expr_prop"]),
          int(C["min_cells"]))

    edges = full.nsmallest(int(C["top_n"]), "magnitude_rank") if C["top_n"] else full
    ctx.emit_table("ccc_edges", edges.set_index("source"))

    n_present = int((cov["stage"] != _ABSENT).sum())
    if not len(full):
        ctx.caveat(f"No interaction was scored. Of {len(cov):,} interactions in {res_name!r}, "
                   f"{n_present:,} had both genes in this object and "
                   f"{int((cov['stage'] == _EXPRESSED).sum()):,} cleared expr_prop "
                   f"{C['expr_prop']:g} in any population.")
        return ctx.refuse(
            "cell-cell communication",
            f"rank_aggregate returned no interaction. This is a result rather than a failure, and "
            f"figures/F1_resource_coverage.csv names the step that removed every one of them.\n"
            f"  {len(cov) - n_present:,} of {len(cov):,} interactions have a gene that is not in "
            f"var_names, which no parameter recovers - the object would have to carry those "
            f"genes.\n"
            f"  Fix, if the loss was at expr_prop instead: --params '{{\"expr_prop\": <lower>}}'.")

    # ------------------------------------------------------------ the remaining panels
    colours = ctx.figure.palette(names)
    clash = getattr(ctx.figure, "palette_collisions", None)
    for _colour, labs in (clash(names) if clash else []):
        ctx.caveat(f"{len(labs)} populations share one colour in the figures below "
                   f"({', '.join(labs)}). There are more populations than the palette has hues "
                   f"that stay separable; read those from the axis labels rather than the "
                   f"colours.")
    per_pop["interactions_as_sender"] = [
        int((full["source"].astype(str) == p).sum()) for p in per_pop.index]
    per_pop["interactions_as_receiver"] = [
        int((full["target"].astype(str) == p).sum()) for p in per_pop.index]
    _draw(ctx, "F2_population_support", _fig_population_support, per_pop, int(C["min_cells"]),
          colours)

    if not _draw(ctx, "F3_method_agreement", _fig_method_agreement, full, _score_columns(li)):
        ctx.caveat(
            "The per-method score columns could not be compared, so nothing here says whether "
            "the methods behind the consensus agree with each other. Read the ranks as one "
            "method's answer rather than as several agreeing.")

    _draw(ctx, "F4_dotplot", _fig_dotplot, full)
    _draw(ctx, "F5_sender_receiver", _fig_sender_receiver, full, kept)

    # ------------------------------------------------------------ caveats, from the data
    top = full.nsmallest(3, "magnitude_rank")
    # ON A SHARED AXIS WITH THE OTHER UNITS. Declared in `report.unit_metrics`; the host
    # draws the comparison, so this is the whole of what this plugin owes for one.
    ctx.metric("interactions", len(full))
    ctx.metric("populations", len(kept))
    ctx.headline = (f"{len(full):,} interactions over {len(kept)} populations"
                    + (f"; strongest {top.iloc[0]['source']} -> {top.iloc[0]['target']} "
                       f"({top.iloc[0]['ligand_complex']}:{top.iloc[0]['receptor_complex']})"
                       if len(top) else ""))
    ctx.caveat(f"Resource {res_name!r} for {ctx.organism}. The resource decides the answer, and "
               f"the wrong one returns a small plausible table rather than an error.")
    frac = n_present / len(cov) if len(cov) else 0.0
    ctx.caveat(
        f"{n_present:,} of {len(cov):,} interactions in {res_name!r} ({100 * frac:.0f}%) have all "
        f"their genes in this object; {len(cov) - n_present:,} do not and could not be scored "
        f"whatever the biology. A further "
        f"{int((cov['stage'] == _BELOW).sum()):,} were present but below expr_prop "
        f"{C['expr_prop']:g} in every population. Interactions removed at either step are ABSENT "
        f"from tables/ccc_edges.csv, not ranked low in it."
        + ("" if frac >= 0.75 else
           " At this coverage the ranked table is as much a property of the gene list this object "
           "carries as of its biology."))
    if small:
        ctx.caveat(
            f"{len(small)} population(s) were EXCLUDED from the inference by min_cells="
            f"{C['min_cells']}, before any score was computed: "
            + ", ".join(f"{p} ({int(per_pop.loc[p, 'n_cells'])} cells)" for p in small)
            + ". They are absent from the result rather than scored and found silent, they stay "
              "in the object, and lowering min_cells is what puts them back.")
    ctx.caveat(
        f"Specificity is a permutation p-value over {C['n_perms']:,} shuffles of the cell labels, "
        f"so it cannot resolve below {1.0 / max(int(C['n_perms']), 1):.2g} and every interaction "
        f"at that floor is tied. Magnitude is not a p-value at all.")
    ctx.caveat(
        f"Scored from {x_src}, with de_method={C['de_method']!r} behind the specificity "
        f"statistics and expr_prop={C['expr_prop']:g}. Every score is computed BETWEEN LABELS, so "
        f"merging or splitting a population changes every interaction it appears in.")
    if _looks_like_counts(A.X):
        ctx.status = "partial"
        ctx.caveat(
            f"THE MATRIX SCORED LOOKS LIKE COUNTS, not log-normalised values: its stored values "
            f"are whole numbers ({x_src}). liana does not refuse this - it checks the first 100 "
            f"stored values and warns - and the magnitude scores are computed directly from the "
            f"matrix, so the ranking below is not the one log-normalised input would give.")
    odd = [str(g) for g in A.var_names if _COMPLEX_SEP in str(g)]
    if odd:
        ctx.caveat(
            f"{len(odd):,} gene symbol(s) in this object contain {_COMPLEX_SEP!r}, which is "
            f"liana's complex separator, so they cannot be told from a two-subunit complex and "
            f"are unavailable to any interaction needing them: "
            + ", ".join(odd[:8]) + ("..." if len(odd) > 8 else ""))
    if C["top_n"]:
        ctx.caveat(f"tables/ccc_edges.csv holds the top {int(C['top_n']):,} interactions by "
                   f"magnitude_rank, not all {len(full):,}. Every figure was computed from all "
                   f"{len(full):,}; F4_dotplot then draws only its own top rows, and says so.")
    if ctx.assay == "nucleus":
        ctx.caveat("Single-nucleus: ligand and receptor transcripts are partly cytoplasmic, so a "
                   "low interaction count is as consistent with the assay as with the biology.")


# ----------------------------------------------------------------------------------- selftest

def selftest(ctx):
    """Prove the resource loads OFFLINE, and that scoring returns the schema the panels read.

    Offline matters as much as the schema: a compute node may have no outbound route, and a
    resource that needs the network is a plugin that cannot run in a batch job at all.

    It says SCHEMA and not "recovers a planted pair", which is what it used to say: a pair is
    planted, but nothing here asserts it comes back, and a docstring claiming a check nobody
    wrote is worse than the missing check - it stops the next reader from writing it.
    """
    import liana as li
    import numpy as np
    import pandas as pd

    for organism, name in sorted(_RESOURCE.items()):
        r = li.resource.select_resource(name)
        assert len(r) > 1000, f"{name} looks truncated: {len(r)} interactions"
        for col in ("ligand", "receptor"):
            assert col in r.columns, f"{name} has no {col!r} column; its schema moved"
        ctx.log(f"  {name} ({organism}): {len(r):,} interactions, loaded offline")

    res = li.resource.select_resource(_RESOURCE["mouse"])
    # THE FIXTURE IS BUILT FROM THE RESOURCE. liana refuses when >98% of the resource is absent
    # from var_names - correctly, since that is the signature of the wrong organism - so a
    # fixture of arbitrary gene names tests the refusal and not the scoring.
    genes = sorted({g for g in list(res["ligand"]) + list(res["receptor"])
                    if isinstance(g, str) and _COMPLEX_SEP not in g})[:600]
    # CHOSEN FROM WHAT THE FIXTURE CARRIES, not `res.iloc[0]` and a hope. The gene list is the
    # alphabetically first 600 of the resource's single-gene entities, so the first row's ligand
    # and receptor are rarely both in it - which meant the planting usually did not happen and
    # nothing said so.
    gs = set(genes)
    pair = next((row for _, row in res.iterrows()
                 if str(row["ligand"]) in gs and str(row["receptor"]) in gs), None)
    A = ctx.fixture(n_cells=200, genes=genes, labels=("Alpha", "Beta"))
    A.X = A.layers["lognorm"]
    if pair is not None:
        lig, rec = str(pair["ligand"]), str(pair["receptor"])
        gi = {g: i for i, g in enumerate(genes)}
        m = np.asarray(A.X.todense() if hasattr(A.X, "todense") else A.X)
        m[A.obs["label"] == "Alpha", gi[lig]] += 20
        m[A.obs["label"] == "Beta", gi[rec]] += 20
        A.X = m
        ctx.log(f"  planted {lig} -> {rec} into Alpha -> Beta")
    else:
        ctx.log("  no interaction of the resource had both its genes in the fixture; scoring is "
                "exercised but nothing is planted")

    li.mt.rank_aggregate(A, groupby="label", resource_name=_RESOURCE["mouse"],
                         expr_prop=0.1, min_cells=5, de_method="t-test",
                         use_raw=False, verbose=False, seed=_SEED, n_perms=10)
    out = A.uns["liana_res"]
    # `specificity_rank` IS IN THIS LIST BECAUSE A PANEL READS IT. F4_dotplot sizes every dot by
    # it and it was not asserted anywhere, so the one schema change that would blank the size
    # dimension of the headline panel was the one this selftest could not see.
    for col in ("source", "target", "ligand_complex", "receptor_complex",
                "magnitude_rank", "specificity_rank"):
        assert col in out.columns, f"liana_res has no {col!r}; the schema moved"
    assert len(out) > 0, "rank_aggregate returned no rows on a fixture built from its own resource"
    assert np.isfinite(out["magnitude_rank"].to_numpy(dtype=float)).all(), \
        "magnitude_rank contains non-finite values"
    ctx.log(f"  rank_aggregate: {len(out):,} rows x {out.shape[1]} columns")

    # THE ORIENTATION OF EVERY SCORE, ASKED OF LIANA. F3_method_agreement is optional and
    # degrades quietly, so nothing at run time would notice it becoming permanently absent - and
    # an optional panel that is always absent is a defect wearing a `when_absent` sentence.
    #
    # PER-METHOD, WHICH IS WHAT THE PANEL COMPARES. This counted every column `_score_columns`
    # returned, and the aggregate's own `magnitude_rank` and `specificity_rank` are always two of
    # them - so the assertion passed on the consensus alone and could never catch the per-method
    # specs disappearing, which is the only thing it was written to catch.
    scores = _score_columns(li)
    per_method = sorted(c for c, (_asc, meths) in scores.items()
                        if list(meths) != [_CONSENSUS] and c in out.columns)
    ctx.log(f"  per-method score columns liana declares and returns: "
            f"{', '.join(per_method) or 'none'}")
    assert len(per_method) >= 2, (
        "liana declares fewer than two PER-METHOD scores among the columns it returned, so "
        "F3_method_agreement could only ever correlate the consensus with itself. Its per-method "
        "specs or get_method_scores have moved.")

    # AND THE COVERAGE ARITHMETIC, where the answer is known by construction. Every gene is given
    # a detection proportion of 1 in the one population, so expr_prop cannot remove anything and
    # the only reason left for an interaction to be unreachable is a subunit missing from
    # var_names - which is exactly what F1_resource_coverage claims to separate. The fixture
    # carries 600 of the resource's single-gene entities, so most interactions ARE absent; what
    # must not happen is that none is reachable, because that is what a broken complex split
    # looks like.
    cov = _coverage(res, list(A.var_names), np.ones((1, A.n_vars), dtype="float32"), 0.1)
    assert len(cov), "the coverage table is empty on a fixture built from the resource"
    assert not len(cov[cov["stage"] == _BELOW]), \
        "an interaction is below expr_prop although every gene is detected in every cell"
    reachable = cov[cov["stage"] == _EXPRESSED]
    assert len(reachable), "no interaction is reachable although every gene is fully detected"
    ctx.log(f"  coverage: {len(reachable):,} of {len(cov):,} interactions reachable when every "
            f"gene the object carries is detected in every cell")

    # THE MIN AND THE MAX IN THE ORDER LIANA APPLIES THEM, on two populations built to disagree.
    # A two-subunit ligand whose subunits are expressed in DIFFERENT populations is not reachable
    # by any pair, and taking the maximum over populations before the minimum over subunits said
    # it was - silently, on the one panel whose whole job is to say what could never have been
    # shown. Nothing else in this file would have noticed.
    split = np.array([[1.0, 0.0, 1.0], [0.0, 1.0, 1.0]], dtype="float32")
    probe = _coverage(pd.DataFrame({"ligand": ["A" + _COMPLEX_SEP + "B"], "receptor": ["R"]}),
                      ["A", "B", "R"], split, 0.1)
    assert list(probe["stage"]) == [_BELOW], (
        "a complex whose subunits are expressed in two different populations is reported "
        f"{list(probe['stage'])} - no single population carries it, so liana can never score it. "
        "The minimum over subunits must be taken within a population before the populations are "
        "compared.")
    ctx.log("  coverage: a complex split across two populations is correctly unreachable")
