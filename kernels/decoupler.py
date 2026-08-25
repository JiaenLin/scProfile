"""Regulatory activity per cell, scored against a curated prior rather than a network inferred here.

ONE FILE. Dropping it into a kernels directory is the whole installation: the host reads PLUGIN
for the manifest, builds the environment from PLUGIN["env"], and runs it through the shared
entrypoint, which applies the contract before this file sees anything.

WHAT THE PAGE HAS TO ANSWER BEFORE THE ANSWER IS WORTH READING

ULM's score is a t-value taken from the correlation between one regulator's weight vector - zero
for every gene it does not target - and one cell's expression vector ACROSS ALL GENES, with
`df = n_genes - 2`. Three properties follow from that arithmetic rather than from any biology, and
each is a way this result can be confidently wrong while looking exactly like a right one:

  THE PRIOR HAS TO MATCH THE GENE NAMES. decoupler intersects the prior's targets with the
      matrix's own feature names and drops any regulator left with fewer than `min_targets` of
      them. Gene symbols against Ensembl IDs, or a species the prior barely covers, does not fail
      - it returns a smaller, plausible table. F1 is that intersection, drawn per regulator.
  THE SCALE IS SET BY THE GENE COUNT, not by the regulon. `df = n_genes - 2`, so the same biology
      scored on a 20,000-gene and a 34,000-gene matrix produces different numbers for the same
      cell. Two datasets' scores are not comparable and neither are two runs of this plugin over
      differently filtered genes; the gene count is logged and in the caveats for that reason.
  A CELL'S SCORE IS READ OFF ITS DETECTED GENES. The correlation is estimated over every feature,
      and in a sparsely detected cell most of them are zero on both sides. So activity magnitude
      can track sequencing depth, and a difference between populations can be a difference in
      depth. F2 measures that on THIS data rather than assuming it away.

None of the three is visible in the result table, and none of them errors. That is why the
diagnostics are declared ahead of the answer in `report`, and why the reporter puts them there.

WHAT IT DOES NOT ANSWER ALONE

An activity is a statement about the PRIOR's gene set for a regulator. A network inferred from the
data is a different kind of evidence about the same question, and the two disagree informatively -
so `report.reads_with` names that other plugin, and the reporter marks the missing half of the
pair as an absence rather than leaving the page silent about it.
"""

PLUGIN = {
    "api": 1,
    "version": "0.2.0",
    "summary": "regulatory activity per cell, from a curated prior",
    "when_to_use": "you want transcription-factor or pathway activity without inferring a "
                   "network from your own data",
    "wraps": {"tool": "decoupler", "homepage": "https://github.com/saezlab/decoupler-py",
              "license": "GPL-3.0",
              "cite": "Badia-i-Mompel et al., Bioinformatics Advances 2022"},

    # WHAT IT MUST BE GIVEN, and what it will use if present. The host resolves both and does
    # NOT CALL run() when a required one is missing - so this file contains no prerequisite
    # checking at all. `organism` is required because the prior is published per species and
    # returns a small plausible table for the wrong one rather than failing.
    #
    # `layout` IS NAMED SEPARATELY FROM `embedding` AND THIS PLUGIN USES ONLY THE LAYOUT. The
    # per-cell activity map is drawn on two coordinates made to be looked at; a representation is
    # 30-50 columns whose axes carry no ordering, and its first two draw as a ball whatever the
    # data holds. Declaring only one of the pair is how a plugin comes to draw on the other.
    "inject": {"required": ["lognorm", "organism"],
               "optional": ["label", "layout"]},
    # A CAPABILITY, not a plugin name. Anything needing per-cell activity injects `activity` and
    # does not care that decoupler produced it.
    "provides": ["activity"],
    "produces": ["obsm[X_tf_activity]",
                 "tables/activity_by_label.csv",
                 "tables/regulator_coverage.csv"],

    # WHAT WAS SHOWN TO IT. The plan reports this so a user can see which of their own layers and
    # columns each plugin will touch; an under-declared plugin looks like one that reads nothing.
    "sees": ["layers[{lognorm}]", "obs[{label}]", "obsm[{layout}]"],

    # TYPED, DEFAULTED AND RANGE-CHECKED BY THE HOST before run() is called. The plugin reads
    # ctx.config and never validates it.
    "config": {
        "min_edges": {"type": "int", "default": 1000, "min": 1,
                      "help": "refuse if the prior has fewer edges than this - a truncated "
                              "download returns a smaller answer rather than an error"},
        # DECOUPLER'S OWN DEFAULT, DECLARED RATHER THAN INHERITED. `run_ulm(min_n=5)` drops any
        # source with fewer than five targets present in the matrix, because an activity fitted
        # on three genes is noise with a t-value. It was being taken silently, so the report
        # could not say what the filter had been - and a source scored on 5 targets and one
        # scored on 50 are not the same measurement.
        "min_targets": {"type": "int", "default": 5, "min": 1,
                        "help": "a regulator with fewer than this many of its targets present "
                                "in the matrix is dropped rather than scored. decoupler's own "
                                "default is 5"},
        # THE SAME PATTERN, TWO PARAMETERS OVER. Both were being inherited implicitly, and both
        # change something a reader of the result would want to know.
        "split_complexes": {"type": "bool", "default": False,
                            "help": "split a prior's protein complexes into their subunits "
                                    "before scoring. False - decoupler's own default - keeps a "
                                    "complex as ONE regulator, so the result names the complex "
                                    "and not its members; True renames every such regulator and "
                                    "changes each one's target count. It decides what the rows "
                                    "of the answer ARE, so it is stated rather than assumed"},
        "batch_size": {"type": "int", "default": 10000, "min": 1,
                       "help": "cells scored per batch. decoupler's own default is 10000. It "
                               "does not change the result: each batch is DENSIFIED, so this is "
                               "the peak-memory dial and the reason a large object can die in a "
                               "call that has nothing to allocate of its own"},
        "top_regulators": {"type": "int", "default": 20, "min": 1,
                           "help": "regulators drawn in the per-population panel, ranked by the "
                                   "spread of their mean activity ACROSS populations - "
                                   "decoupler's own `summarize_acts` criterion. Nothing is "
                                   "dropped: every scored regulator is in the tables"},
        "redundancy_above": {"type": "float", "default": 0.7, "min": 0.0, "max": 1.0,
                             "help": "in the overlap panel, regulator pairs whose target-weight "
                                     "vectors correlate above this in absolute value are counted "
                                     "and named. NOT a filter - nothing is removed - it only "
                                     "sets what the caveat counts as a redundant pair"},
    },
    "per_unit": None,
    "cost": "medium", "cores": 4,

    # Measured, not estimated: fitted from this plugin's own instances in one run on a 10-sample mouse single-nucleus cohort (~99k cells). ONE dataset on ONE machine - a starting point that is right for scheduling, not a universal constant. Every run re-fits and prints its own.
    # Fitted from one instance; the split is indeterminate.
    "memory_gb_per_100k": 7.5,
    # WHAT IT NEEDS, NOT WHAT TO BUILD. A plugin cannot know what else is installed, so it must
    # not decide its own environment: three plugins wanting this same stack used to get three
    # 1.5 GB copies of it. The BUILDER resolves these constraints across every plugin and builds
    # as few environments as satisfy them all. Omit `requires` and the plugin runs in the host's.
    #
    # Constraints, not pins, wherever the tool genuinely tolerates a range - a pin is a claim
    # that only THIS version works, and claiming it where it is untrue is what forces an
    # environment nobody can share.
    # FETCHED OVER THE NETWORK WHILE IT RUNS. Nothing pins these, nothing checksums them, and
    # the fetch needs outbound HTTPS FROM A COMPUTE NODE - which is the failure a batch job
    # discovers after its queue slot is spent. Declaring them is what lets `plan` say so first.
    "references": {
        "collectri": {"tier": "runtime", "role": "prior", "source": "OmniPath",
                      "cite": "Muller-Dott et al., Nucleic Acids Res 2023",
                      "note": "TF-target prior, fetched from OmniPath on first use. Needs "
                              "outbound HTTPS at RUN time; nothing here pins the version"},
        "progeny": {"tier": "runtime", "role": "prior", "source": "OmniPath",
                    "cite": "Schubert et al., Nat Commun 2018",
                    "note": "pathway-response prior, fetched from OmniPath on first use. Needs "
                            "outbound HTTPS at RUN time; nothing here pins the version"},
    },

    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {
            "decoupler": ">=1.8,<1.9",   # the API this plugin calls is 1.8's, any patch of it
            "scanpy": ">=1.10,<1.11",
            "anndata": ">=0.10,<0.12",
            "numpy": ">=1.24,<2",        # decoupler 1.8 predates the numpy 2 ABI
            "pandas": ">=2.0,<3",
            # DECOUPLER IMPORTS THIS AND DOES NOT REQUIRE IT. `get_collectri` calls
            # `_omnipath_check_version`, which does `import omnipath` - lazily, inside the
            # function, so nothing about installing decoupler asks for it and nothing about
            # importing decoupler notices. It surfaces on the first call to the one function this
            # plugin exists to make. Measured on PBS 677555:
            # `ModuleNotFoundError: No module named 'omnipath'` from inside `get_collectri`.
            "omnipath": ">=1.0",
            # NEEDED SINCE THIS PLUGIN DREW ANYTHING, and declared for exactly the reason
            # `_spearman` below is hand-written rather than imported from scipy: a plugin that
            # reaches for a package it never declared works until the builder resolves an
            # environment that does not happen to contain it, and then dies in the figure step
            # after the prior has been fetched and every cell scored. matplotlib is present today
            # only because scanpy asks for it - a fact about a neighbour, not a requirement of this
            # file. The floor is 3.6: every panel here uses `subplots(layout="constrained")`,
            # which is the release that added it.
            "matplotlib": ">=3.6,<4",
        },
    },

    # WHAT THE WRAPPED TOOL'S OWN DOCUMENTATION SAYS, and which of its defaults are wrong for
    # this contract. In the directory shape this was a separate UPSTREAM.md that had to be kept
    # in step with the wrapper; here it is in the file it describes, which is the only place it
    # cannot drift from.
    "upstream": {
        "docs": "https://decoupler-py.readthedocs.io",
        # 2026-08-25: read again against the INSTALLED source of the pinned version rather than
        # against the rendered docs, because three of the five gotchas below are in code that the
        # docs do not describe at all - a fallback in an `except Exception`, a return value the
        # documented signature does not mention, and the degrees of freedom the score is scaled by.
        "read": "2026-08-25",
        "defaults_changed": [
            "use_raw=False. The default follows .raw when it exists, and an object that has been "
            "through QC and annotation usually has a .raw holding PRE-FILTER counts - so the "
            "default scores a different matrix from the one the user is looking at, without "
            "erroring.",
            "verbose=False, because progress output is not a result.",
            "min_n, batch_size and split_complexes are PASSED EXPLICITLY at decoupler's own "
            "defaults rather than inherited. None of the three changes value; what changes is "
            "that the run can now say what they were. min_n decides which regulators exist in "
            "the answer, split_complexes decides what a regulator IS - a complex or its subunits "
            "- and batch_size is the size of the dense block the scorer materialises, which is "
            "the whole of this plugin's peak memory and is invisible in every traceback it "
            "causes.",
            "The panels are decoupler's own two, plus three checks it does not draw. Its "
            "single-cell vignette shows a heatmap of mean activity for the most variable "
            "regulators across clusters and a per-cell map of one regulator on the embedding; "
            "both are here, ranked by the spread across populations that `summarize_acts` uses. "
            "The diagnostics ahead of them are not in any tutorial, which is the reason for "
            "declaring them: the tutorials are written on data where the prior already matched.",
        ],
        "not_used": [
            "run_mlm and run_wsum: ULM is used alone here. decoupler's own consensus over several "
            "methods is a better answer and needs all of them run, which is a change to this "
            "plugin's declaration, not a flag.",
            "get_progeny: pathway activity is a second prior and would be a second plugin.",
            "get_pseudobulk + a bulk-style contrast. decoupler's own pseudobulk notebook is "
            "explicit that single cells within a sample are not independent of each other, so a "
            "per-cell test 'is not testing the variation across a population of samples, rather "
            "the variation inside an individual one'. Scoring per cell and TESTING per sample are "
            "two different jobs; this plugin does the first and says so, and the second belongs "
            "with the plugin that already owns designs and contrasts.",
            "decoupler 2.x, where this API is `dc.mt.ulm` and `dc.op.collectri`. The pin here is "
            "1.8 and the call surface below is 1.8's; the rename is recorded so that a future "
            "bump is understood as a rewrite of the calls rather than a version number.",
        ],
        "gotchas": [
            "get_collectri takes `organism` and silently returns a small table for a species it "
            "has little for - it does not raise. The refusal above exists for that.",
            "THE PRIOR IS FETCHED OVER THE NETWORK, at run time, from OmniPath's API. It is not "
            "a file with a URL and a checksum, so it cannot be declared as a reference and "
            "fetched once by the host - which means a run needs a route out of the compute node, "
            "and two runs a month apart score against two different priors. The edge and "
            "regulator counts are logged and in the caveats for that reason: they are the only "
            "record of WHICH prior produced a result.",
            "THE NETWORK FETCH FAILS INTO A DIFFERENT ANSWER, NOT INTO AN ERROR. `get_collectri` "
            "wraps its web query in `except Exception:` and falls back to `_static_fallback`, a "
            "stored snapshot, logging a traceback and RETURNING NORMALLY. So a run with no route "
            "out of the node produces a result scored against an older prior, and nothing in the "
            "returned object distinguishes it from the live one. The edge and regulator counts "
            "this plugin prints are again the only record.",
            "THE SCORE'S SCALE IS THE GENE COUNT. `ulm()` sets `df = n_features - 2`, where "
            "n_features is every gene in the matrix and not the regulon's size, and the t-value "
            "is that df applied to a correlation. Filtering genes therefore rescales every "
            "activity in the object, silently and uniformly, which is why no threshold on these "
            "numbers travels between datasets or even between two gene filters.",
            "run_ulm RETURNS A NEW OBJECT when any cell is empty. Its documented behaviour is to "
            "write `obsm['ulm_estimate']` in place and return None; but `extract` drops cells "
            "whose row is all zeros, and `return_data` then logs 'Provided AnnData contains empty "
            "observations. Returning repaired object.' and hands back a SUBSET copy - leaving the "
            "caller's own object with no result in it at all. Code that ignores the return value "
            "reads back a key that was never written. This plugin takes the returned object when "
            "there is one and pads the missing cells with NaN rather than dropping them.",
            "min_n is applied to the targets that SURVIVE the matrix, and `check_mat` has already "
            "removed every all-zero gene by then. So the regulator list depends on this object's "
            "gene filtering as much as on the prior, and two runs over the same cells with "
            "different QC can score different regulators.",
            "CollecTRI is curated in one species and served for others by ORTHOLOGY. OmniPath "
            "serves mouse and rat; for anything else `get_collectri` calls `translate_net`, "
            "which imports pypath - a heavy package decoupler does not require either, exactly "
            "like omnipath above - and downloads orthology databases at RUN time, documented at "
            "about fifteen minutes on a first call. On such an organism the regulon membership "
            "is a projection, not curated evidence in that species.",
        ],
    },

    # WHAT ITS PAGE SHOULD CONTAIN, declared so the reporter can lay it out, caption it, and say
    # which panel is MISSING. The order below is the order a reader needs and not the order the
    # code draws in: three ways this method can be confidently wrong, and only then its answer.
    #
    # `shows` is the whole of the reporter's knowledge. It knows no id here and never will.
    "report": {
        "figures": [
            {"id": "F1_prior_coverage", "shows": "diagnostic", "required": True,
             "question": "is this prior about the genes in this object at all - and is a "
                         "regulator's score explained by nothing more than how many targets it "
                         "has?",
             "source": "tables/regulator_coverage.csv"},
            {"id": "F2_detection_depth", "shows": "diagnostic", "required": True,
             "question": "does a cell's activity measure its biology, or how many genes were "
                         "detected in it?",
             "source": "figures/F2_detection_depth.csv"},
            # OPTIONAL BECAUSE IT IS A SECOND PASS OVER THE MATRIX and a prior with many
            # thousands of regulators makes the pair table quadratic. Where it cannot be drawn
            # the absence is not neutral, so `when_absent` says what is then unknown.
            {"id": "F3_regulon_overlap", "shows": "diagnostic", "required": False,
             "question": "are two high-scoring regulators two findings, or one regulon counted "
                         "twice?",
             "source": "figures/F3_regulon_overlap.csv",
             # TWO ABSENCES, AND THEY ARE OPPOSITE FINDINGS. The check may not have run, in which
             # case redundancy is UNKNOWN; or it ran and found no correlated pair at all, in which
             # case the regulons are ORTHOGONAL on this matrix - which is the stronger of the two
             # results this panel can produce. A sentence naming only the first states the unknown
             # as fact on every run of the second, so it names both and points at the caveat that
             # says which happened. `run()` writes that caveat in both branches.
             "when_absent": "EITHER the prior's regulons were not compared with each other on "
                            "this data, OR they were compared and no two scored regulators share "
                            "enough targets to correlate at all - opposite findings, and this "
                            "run's caveats say which. Where the check did not run, nothing says "
                            "whether two regulators are near-copies: two hits sharing most of "
                            "their targets score almost identically by construction, so read any "
                            "pair of names below as possibly one measurement until their target "
                            "lists have been compared."},
            {"id": "F4_by_population", "shows": "result", "required": False,
             "question": "which regulators separate the populations, and in which direction?",
             "source": "figures/F4_by_population.csv",
             "when_absent": "no population could be formed - either no label column was named, or "
                            "one was and every cell in it carries an annotator sentinel, which is "
                            "a finding about the annotation rather than a missing argument. This "
                            "run's caveats say which. Nothing is missing from the per-cell "
                            "result; tables/activity_by_label.csv holds the cohort-wide mean "
                            "instead of a per-population one."},
            {"id": "F5_activity_map", "shows": "result", "required": False,
             "question": "where do the strongest regulators sit on the manifold the rest of the "
                         "report uses?",
             "source": "figures/F5_activity_map.csv",
             "when_absent": "the object carries no two-column layout to draw on. The first two "
                            "columns of a wider representation are two arbitrary coordinates of "
                            "it and not a picture of it, so nothing was drawn in its place; "
                            "compute a layout and re-run to get this panel."},
        ],
        # THE PAIRING, and it is documented rather than decorative: one plugin INFERS a network
        # from these cells and this one APPLIES a curated one. A regulator both find is well
        # supported; one only the inferred network finds may be co-expression rather than
        # regulation. Declared here so the reporter can name the missing half as an absence -
        # neither plugin can draw the comparison alone.
        "reads_with": ["scenic"],
    },

    "cannot_show": [
        "THE PRIOR DECIDES THE ANSWER. An activity score is a statement about the prior's gene "
        "set for that regulator, not a measurement of a protein.",
        "Scores are relative WITHIN this dataset and are not comparable with another dataset's.",
        "THE SCALE IS SET BY THE GENE COUNT, NOT THE REGULON. The t-value carries n_genes - 2 "
        "degrees of freedom, so re-running over a differently filtered gene list rescales every "
        "activity in the object. No threshold on these numbers travels between two runs whose "
        "matrices had different genes in them.",
        "A REGULATOR IS NOT SEPARABLE FROM ONE THAT SHARES ITS TARGETS. Two regulons overlapping "
        "in most of their targets produce almost the same score by construction, so 'A is active "
        "and B is not' cannot be read off this result for such a pair however different their "
        "biology is.",
        "The prior is published per organism. On the wrong species it does not error - it "
        "returns a small, plausible table. And on any organism but the curated one the regulons "
        "are an ORTHOLOGY PROJECTION rather than curated evidence in that species.",
        "THE PRIOR IS FETCHED WHEN THE RUN HAPPENS and is not pinned. Two runs against the same "
        "object, weeks apart, can score against different versions of it; the edge and regulator "
        "counts in the caveats are the only record of which one this was. A run with no route "
        "out of the node falls back to a stored snapshot and says so only in a log line.",
        "CELLS ARE NOT REPLICATES. Every score here is per cell, and cells from one sample are "
        "not independent of each other. A difference in activity between two arms of a design is "
        "not established by comparing cells across them - that comparison needs the unit of "
        "replication, which is the sample.",
        "The p-values decoupler returns are one two-sided test per cell per regulator, "
        "uncorrected. On a cohort-sized object that is tens of millions of tests, and the "
        "fraction below 0.05 is reported as a description of the output rather than as evidence.",
    ],
}


# ------------------------------------------------------------------------------------ helpers
#
# Everything below is drawing and arithmetic that run() would otherwise carry inline. It lives
# ABOVE run() deliberately: the maintainer checks slice this file between the run and selftest
# definitions, so a helper parked in that gap is read as part of run's own body.
#
# THEY SLICE ON THE LITERAL TEXT, so this comment may not quote the two headers it is describing.
# It did, and the slice then started HERE - at the first match, which was the comment - leaving a
# two-line window in which the properties being asserted about run() were all trivially false. A
# note explaining a check is inside the thing the check reads.

#: How much of a ranked list each panel can HOLD, as opposed to how much there is. Named here
#: because every one of them is a limit of the figure and none is a property of the data, and a
#: panel that silently shows the first few of something is indistinguishable from one showing all
#: of it. Each caption prints the number it drew and the number there were.
_OVERLAP_BARS = 18      # pairs drawn in F3
_OVERLAP_ROWS = 200     # pairs written to F3's source table, same order as the bars
_MAP_PANELS = 4         # regulators drawn in F5


def _detected(ctx):
    """(genes present, detected genes per cell) - decoupler's own definition of present.

    `check_mat` drops a feature whose column is entirely zero before anything else happens, so
    the genes a regulon is matched against are the DETECTED ones and not the object's var_names.
    Counting them any other way makes the coverage panel disagree with the run it describes.
    """
    import numpy as np
    X = ctx.X
    names = np.asarray(ctx.adata.var_names, dtype=str)
    if hasattr(X, "tocsr"):
        M = X.tocsr()
        per_gene = np.asarray(M.getnnz(axis=0)).ravel()
        per_cell = np.asarray(M.getnnz(axis=1)).ravel()
    else:
        M = np.asarray(X)
        per_gene = np.count_nonzero(M, axis=0)
        per_cell = np.count_nonzero(M, axis=1)
    return names[per_gene > 0], per_cell


def _spearman(a, b):
    """Spearman rho with tied ranks averaged, from numpy and pandas alone.

    Written here rather than imported because scipy is not in this plugin's requirement, and a
    plugin that reaches for an undeclared package works until the builder resolves an environment
    that does not happen to contain it.
    """
    import numpy as np
    import pandas as pd
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if int(ok.sum()) < 3:
        return float("nan")
    ra = pd.Series(a[ok]).rank().to_numpy()
    rb = pd.Series(b[ok]).rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def _size_bins(min_targets):
    """Bins for regulon size, with the drop threshold ON a bin edge by construction.

    A histogram of regulon sizes is unreadable on a linear axis - CollecTRI's regulons run from
    one target to thousands - and a log axis cannot show the regulators with zero targets present,
    which are exactly the ones this panel exists to count. Explicit bins in multiples of the
    threshold solve both, and make the threshold visible as a boundary rather than as a line
    drawn over a shape.
    """
    m = max(1, int(min_targets))
    edges = sorted({0, 1, m, 2 * m, 5 * m, 20 * m})
    labels = []
    for i, lo in enumerate(edges):
        hi = edges[i + 1] if i + 1 < len(edges) else None
        if hi is None:
            labels.append(f"{lo}+")
        elif hi - lo == 1:
            labels.append(str(lo))
        else:
            labels.append(f"{lo}-{hi - 1}")
    return edges, labels


def _clean(ax, F, key=""):
    """No ticks, no box, and the axes NAMED - an unlabelled map is the commonest reason a reader
    asks what they are looking at.

    The layout key is printed WHOLE. A neighbouring plugin learned that splitting it into an
    algorithm and a provenance requires knowing which half is which, and a wrong guess invents
    both; printing the object's own key is shorter and cannot be wrong.
    """
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    if key:
        ax.set_xlabel(f"{key} 1", loc="left")
        ax.set_ylabel(f"{key} 2", loc="bottom")


def _fig_coverage(ctx, cov, min_targets, source_path):
    """F1 - did the prior meet this object's genes, and does regulon size alone set the score?

    Two panels sharing an x quantity on purpose. The left says how many of each regulator's
    targets are actually here and how many regulators that cost; the right says whether the
    survivors' scores are a function of that same number. A prior that matched nothing and a
    ranking that is just regulon size are the two ways this result is about the prior rather than
    about the data, and they are one question.
    """
    import numpy as np
    F, plt = ctx.figure, ctx.plot()
    edges, labels = _size_bins(min_targets)
    v = cov["targets_present"].to_numpy(dtype=float)
    counts, dropped_bins = [], []
    for i, lo in enumerate(edges):
        hi = edges[i + 1] if i + 1 < len(edges) else np.inf
        counts.append(int(((v >= lo) & (v < hi)).sum()))
        dropped_bins.append(lo < min_targets)
    first_scored = int(np.argmin(dropped_bins)) if not all(dropped_bins) else len(edges)

    fig, axs = plt.subplots(1, 2, figsize=(F.DOUBLE, F.SINGLE * 0.72), layout="constrained")
    ax = axs[0]
    x = np.arange(len(counts))
    ax.bar(x, counts, width=0.74,
           color=[F.GREY if d else "#0072B2" for d in dropped_bins])
    if 0 < first_scored < len(edges):
        ax.axvline(first_scored - 0.5, color=F.INK, ls="--", lw=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("targets of that regulator present in this matrix")
    ax.set_ylabel("regulators in the prior")
    ax.set_title("what the prior found here", loc="left")

    ax2 = axs[1]
    sc = cov[cov["scored"]]
    rho = _spearman(sc["targets_present"], sc["mean_abs_activity"])
    ax2.scatter(sc["targets_present"], sc["mean_abs_activity"], s=5, color="#0072B2",
                alpha=0.65, linewidths=0)
    F.rasterize_points(ax2)
    ax2.set_xscale("log")
    ax2.set_xlabel("targets present (log)")
    ax2.set_ylabel("mean |activity| over cells")
    ax2.set_title(f"score against regulon size (Spearman {rho:+.2f})", loc="left")

    n_scored = int(cov["scored"].sum())
    ctx.emit_figure(
        "F1_prior_coverage", fig,
        caption=(f"LEFT: every regulator in the prior, binned by how many of its targets are "
                 f"present in this matrix. Bars left of the dashed line fall below "
                 f"min_targets={min_targets} and were not scored; {n_scored:,} of "
                 f"{len(cov):,} regulators were. A prior whose mass sits in the low bins has not "
                 f"met these gene names - the usual cause is an identifier mismatch or an "
                 f"organism the prior barely covers, and neither of them errors. RIGHT: for the "
                 f"scored regulators, mean |activity| against that same target count. A strong "
                 f"positive relation means the ranking below is largely a ranking of regulon "
                 f"size. Presence is counted against the DETECTED genes, which is what decoupler "
                 f"matches against after dropping all-zero features."),
        source=source_path)


def _fig_depth(ctx, frame, rho):
    """F2 - is the size of a cell's activities a fact about its biology or about its depth?

    The score is a correlation taken over every gene, most of which are zero on both sides in a
    sparsely detected cell. So this relation is expected to be nonzero and the panel is not a
    pass/fail: it is the number a reader needs before reading any difference between populations,
    because populations differ in depth.
    """
    import numpy as np
    F, plt = ctx.figure, ctx.plot()
    x = frame["genes_detected"].to_numpy(dtype=float)
    y = frame["mean_abs_activity"].to_numpy(dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    # A SUBSAMPLE IS DRAWN AND THE WHOLE IS MEASURED. 100,000 overplotted points hide the shape
    # they are meant to show, and rho is computed on every cell either way - the caption says so,
    # because a reader cannot tell a subsampled panel from a complete one by looking.
    idx = np.where(ok)[0]
    shown = idx
    if idx.size > 20000:
        shown = np.random.default_rng(0).choice(idx, 20000, replace=False)

    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.8))
    ax.scatter(x[shown], y[shown], s=1.5, color="#0072B2", alpha=0.35, linewidths=0)
    F.rasterize_points(ax)
    q = np.unique(np.quantile(x[ok], np.linspace(0, 1, 21))) if ok.any() else np.array([])
    if q.size > 2:
        b = np.digitize(x, q[1:-1], right=False)
        cx, cy = [], []
        for i in range(q.size - 1):
            m = ok & (b == i)
            if int(m.sum()) >= 20:
                cx.append(float(np.median(x[m])))
                cy.append(float(np.median(y[m])))
        if len(cx) > 1:
            ax.plot(cx, cy, color=F.INK, lw=1.0)
    ax.set_xlabel("genes detected in the cell")
    ax.set_ylabel("mean |activity| over regulators")
    ax.set_title(f"Spearman {rho:+.2f}", loc="left")
    ctx.emit_figure(
        "F2_detection_depth", fig,
        caption=(f"One point per cell: how many genes were detected in it against how large its "
                 f"activity scores are. The line is the median in twenty depth bins. ULM scores a "
                 f"cell by correlating the regulator's weights with that cell's expression across "
                 f"every gene, so a shallow cell has fewer non-zero entries carrying the same "
                 f"correlation and some relation here is expected. It matters because populations "
                 f"differ in depth: with Spearman {rho:+.2f}, a difference in activity between "
                 f"two populations of different depth cannot be read as biology without checking "
                 f"this first. Points are a random subsample of at most 20,000 cells drawn with a "
                 f"fixed seed; the coefficient and the source table cover every cell."),
        source=frame)


def _fig_overlap(ctx, pairs, n_sources, thr):
    """F3 - how many of these regulators are the same regulon twice?

    From decoupler's own `check_corr`, which correlates the prior's weight vectors after matching
    them to this matrix. Two regulators whose targets overlap score almost identically whatever
    their biology, and a page that lists both as findings has counted one measurement twice.
    """
    import numpy as np
    F, plt = ctx.figure, ctx.plot()
    # SORTED ONCE, AND THE SOURCE TABLE IS THE HEAD OF THE SAME ORDER. The bars were the strongest
    # |corr| in the frame while the source table was `pairs.head(200)` - 200 rows in the order
    # decoupler happened to return them, reaching |corr| 0.006 on a real prior and containing none
    # of the pairs drawn. A reader opening the source data to check the panel could not find a
    # single row of it, which is the one thing source data exists to prevent.
    #
    # `sort_values(key=...)` rather than `reindex(...index)` for a second reason: reindexing on an
    # index that is not unique raises, and nothing about `check_corr`'s return value promises one.
    ordered = pairs.sort_values("corr", key=lambda s: s.abs(), ascending=False)
    top = ordered.head(_OVERLAP_BARS)
    if not len(top):
        return
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.6, 0.19 * len(top) + 0.9)))
    y = np.arange(len(top))
    vals = top["corr"].to_numpy(dtype=float)
    ax.barh(y, vals, height=0.72,
            color=["#D55E00" if v < 0 else "#0072B2" for v in vals])
    ax.set_yticks(y)
    ax.set_yticklabels([f"{a} / {b}" for a, b in zip(top["source1"], top["source2"])])
    ax.invert_yaxis()
    ax.axvline(0, color=F.INK, lw=0.6)
    ax.set_xlim(-1, 1)
    ax.set_xlabel("correlation between the two regulators' target weights")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    n_red = int((pairs["corr"].abs() > thr).sum())
    n_src_rows = min(len(ordered), _OVERLAP_ROWS)
    ctx.emit_figure(
        "F3_regulon_overlap", fig,
        caption=(f"The {len(top)} most overlapping pairs of scored regulators, as decoupler's own "
                 f"check_corr computes them: the correlation between the two regulators' "
                 f"target-weight vectors after matching to this matrix. A pair near +1 shares "
                 f"most of its targets with the same signs and will produce near-identical "
                 f"activities in every cell - not two findings. A pair near -1 shares targets "
                 f"with opposing signs and will be anti-correlated by construction. {n_red:,} "
                 f"pair(s) among the {n_sources:,} scored regulators exceed |{thr}|. The bars are "
                 f"the head of {len(pairs):,} compared pairs ranked by |correlation|; the source "
                 f"table holds the strongest {n_src_rows:,} of them, in that same order, so every "
                 f"bar drawn is in it."),
        source=ordered.head(_OVERLAP_ROWS))


def _fig_by_population(ctx, sub, ranked_by, n_ranked):
    """F4 - the answer: mean activity per population, for the regulators that vary most.

    `ranked_by` is the criterion the caller actually ranked on, printed rather than assumed. The
    caption used to name the spread of the population means unconditionally, which is false in the
    branch run() falls into when there are fewer than two populations to spread across - and a
    caption naming a criterion the code did not use is a figure that cannot be checked.
    """
    import numpy as np
    F, plt = ctx.figure, ctx.plot()
    vals = np.asarray(sub.to_numpy(), dtype=float)
    lim = float(np.nanmax(np.abs(vals))) if np.isfinite(vals).any() else 1.0
    lim = lim if lim > 0 else 1.0
    # `constrained`, because the column labels are regulator names rotated vertical and the row
    # labels are whatever the annotation calls its populations: without it the colourbar is drawn
    # across them.
    fig, ax = plt.subplots(figsize=(F.DOUBLE, max(1.8, 0.20 * len(sub) + 1.6)),
                           layout="constrained")
    im = ax.imshow(vals, aspect="auto", cmap="coolwarm", vmin=-lim, vmax=lim,
                   interpolation="nearest")
    ax.set_xticks(np.arange(sub.shape[1]))
    ax.set_xticklabels(list(sub.columns), rotation=90)
    ax.set_yticks(np.arange(sub.shape[0]))
    ax.set_yticklabels(list(sub.index))
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label("mean activity (t-value)")
    ctx.emit_figure(
        "F4_by_population", fig,
        caption=(f"Mean activity per population for {sub.shape[1]} of the {n_ranked:,} scored "
                 f"regulators the ranking covers, the highest by {ranked_by}. That is a ranking of "
                 f"VARIABILITY and not of importance, and every scored regulator is in the tables "
                 f"whether or not it is drawn here. The rows are every population the annotation "
                 f"names; the "
                 f"colour scale is symmetric about zero because the sign is the whole of the "
                 f"claim: positive is the regulon's targets moving with their weights, negative "
                 f"against them. Read it against F1 and F3 - a regulator scored on few targets, "
                 f"or one that shares its targets with its neighbour in this panel, is not an "
                 f"independent result. Annotator sentinels are not shown as populations."),
        source=sub)


def _fig_map(ctx, xy, acts, names, axis_name, obsm_key, ranked_by):
    """F5 - the strongest regulators drawn per cell on the layout the rest of the report uses.

    Four panels is what this figure HOLDS. The count and the criterion are printed in the caption
    because a page showing four regulators out of several hundred, with nothing saying how they
    were chosen or how many there were, reads as a selection somebody made on the biology.
    """
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()
    ranked = list(names)
    names = ranked[:_MAP_PANELS]
    if not names:
        return
    ncol = 2 if len(names) > 1 else 1
    nrow = (len(names) + ncol - 1) // ncol
    fig, axs = plt.subplots(nrow, ncol, figsize=(F.DOUBLE, 3.1 * nrow), squeeze=False,
                            layout="constrained")
    for ax, name in zip(axs.ravel(), names):
        a = np.asarray(acts[name].to_numpy(), dtype=float)
        fin = np.isfinite(a)
        # Cells with no score are DRAWN, in grey. Dropping them would leave a hole in the
        # manifold that reads as a region with no cells in it.
        if (~fin).any():
            ax.scatter(xy[~fin, 0], xy[~fin, 1], s=1.5, color=F.GREY, linewidths=0)
        lim = float(np.nanpercentile(np.abs(a[fin]), 98)) if fin.any() else 1.0
        lim = lim if lim > 0 else 1.0
        o = np.argsort(np.abs(a[fin]))
        pts = ax.scatter(xy[fin][o, 0], xy[fin][o, 1], c=a[fin][o], s=1.5, cmap="coolwarm",
                         vmin=-lim, vmax=lim, linewidths=0)
        F.rasterize_points(ax)
        _clean(ax, F, axis_name)
        ax.set_title(name, loc="left")
        cb = fig.colorbar(pts, ax=ax, fraction=0.045, pad=0.02)
        cb.outline.set_visible(False)
    for ax in axs.ravel()[len(names):]:
        ax.set_visible(False)
    # THE COORDINATE COLUMNS ARE PREFIXED. A regulator called `x` would otherwise overwrite the
    # x coordinate in the source table and nothing would say so - the prior chooses these names,
    # this plugin does not, and a name it has never seen is exactly what it must survive.
    src = pd.DataFrame({"barcode": list(acts.index.astype(str)),
                        "layout_x": xy[:, 0], "layout_y": xy[:, 1]}).set_index("barcode")
    for name in names:
        src[name] = np.asarray(acts[name].to_numpy(), dtype=float)
    ctx.emit_figure(
        "F5_activity_map", fig,
        caption=(f"Per-cell activity on obsm[{obsm_key}] for {len(names)} of the {len(ranked):,} "
                 f"scored regulators the ranking covers - the highest by {ranked_by}. "
                 f"{len(names)} is how many "
                 f"panels this figure holds and not a statement about the data; every regulator's "
                 f"per-cell score is in obsm[X_tf_activity] whether or not it is drawn. Each "
                 f"panel has its own symmetric scale, clipped at the 98th percentile of "
                 f"|activity| for that regulator, so panels show shape and not relative "
                 f"magnitude. Grey cells carry no score. Every cell is drawn including those an "
                 f"annotator declined to type: the score is per cell and does not depend on the "
                 f"label. The layout is the object's own - this plugin computes none - so a "
                 f"region where the layout tore the manifold looks the same here as everywhere "
                 f"else in the report."),
        source=src)


def run(ctx):
    import warnings

    import numpy as np
    import pandas as pd
    import decoupler as dc

    # THE JOURNAL CONVENTIONS, APPLIED BEFORE ANYTHING IS FETCHED. Not for the settings' sake: it
    # is the cheapest possible check that this environment can draw at all, and the alternative is
    # discovering a broken matplotlib backend after the prior has been downloaded and scored.
    ctx.plot()

    # NO PREREQUISITE CHECKING. `lognorm` and `organism` are declared as required injections, so
    # the host did not call this without them - and it reported precisely which was missing to
    # the planner, which is where a user can act on it.
    net = dc.get_collectri(organism=ctx.organism, split_complexes=ctx.config["split_complexes"])
    ctx.log(f"prior: {len(net):,} edges, {net['source'].nunique():,} regulators "
            f"for {ctx.organism} (split_complexes={ctx.config['split_complexes']})")
    ctx.caveat(f"Scored against a CollecTRI prior of {len(net):,} edges over "
               f"{net['source'].nunique():,} regulators, fetched for {ctx.organism} when this run "
               f"happened, with split_complexes={ctx.config['split_complexes']}. The prior is "
               f"not pinned and is not a file this host can checksum, so those two counts are "
               f"the only record of which version produced this result - including whether the "
               f"fetch reached OmniPath at all, since a failed fetch falls back to a stored "
               f"snapshot and returns normally.")
    ctx.caveat(f"CollecTRI is curated in one species and served for others by ORTHOLOGY "
               f"projection. This run asked for {ctx.organism}; unless that is the curated "
               f"species, each regulon's membership is a mapping of the curated one and not "
               f"evidence collected in {ctx.organism}.")
    if len(net) < ctx.config["min_edges"]:
        return ctx.refuse("activity scores",
                          f"the prior has {len(net):,} edges, below the declared minimum of "
                          f"{ctx.config['min_edges']:,}. A truncated prior returns a smaller "
                          f"answer rather than an error.")

    ctx.adata.X = ctx.X
    genes_present, per_cell_detected = _detected(ctx)
    n_genes = int(len(genes_present))
    ctx.log(f"matrix: {ctx.adata.n_obs:,} cells x {ctx.adata.n_vars:,} genes, "
            f"{n_genes:,} of them detected and therefore matchable")

    # THE INTERSECTION IS MEASURED BEFORE ANYTHING IS SCORED, because the commonest catastrophic
    # case has no other symptom. When no regulator keeps `min_targets` of its targets, decoupler's
    # own filter stops with "No sources with more than min_n targets" - accurate, and it reaches a
    # user as a traceback about a parameter rather than as the finding it is: these gene names and
    # this prior's gene names are not the same vocabulary.
    tgt = net["target"].astype(str)
    grp = pd.DataFrame({"source": net["source"].astype(str),
                        "present": tgt.isin(set(map(str, genes_present)))}).groupby("source")
    cov = pd.DataFrame({"targets_in_prior": grp["present"].size(),
                        "targets_present": grp["present"].sum()})
    cov["coverage"] = cov["targets_present"] / cov["targets_in_prior"].clip(lower=1)
    would_score = int((cov["targets_present"] >= ctx.config["min_targets"]).sum())
    ctx.log(f"prior against this matrix: {would_score:,} of {len(cov):,} regulators keep at "
            f"least min_targets={ctx.config['min_targets']} of their targets")
    if not would_score:
        return ctx.refuse(
            "activity scores",
            f"not one of the prior's {len(cov):,} regulators keeps "
            f"{ctx.config['min_targets']} of its targets among the {n_genes:,} detected genes of "
            f"this object, so there is nothing to score. The prior's targets and this matrix's "
            f"feature names are different vocabularies - gene symbols against Ensembl "
            f"identifiers is the usual cause, and a prior fetched for the wrong organism is the "
            f"next. Neither is visible in a result, which is why this stops here.\n"
            f"  Median regulator overlap: {100 * float(cov['coverage'].median()):.1f}% of its "
            f"prior targets.")

    # THE RETURN VALUE IS NOT IGNORABLE. Documented behaviour is to write obsm in place and return
    # None, but `extract` drops cells whose row is entirely zero and `return_data` then hands back
    # a SUBSET COPY, leaving the caller's object without the result. Reading the key off ctx.adata
    # unconditionally is how a run ends in a missing key on data that is merely sparse.
    returned = dc.run_ulm(mat=ctx.adata, net=net, source="source", target="target",
                          weight="weight", min_n=ctx.config["min_targets"],
                          batch_size=ctx.config["batch_size"], use_raw=False, verbose=False)
    scored = ctx.adata if returned is None else returned
    acts = scored.obsm["ulm_estimate"]
    pvals = scored.obsm["ulm_pvals"] if "ulm_pvals" in scored.obsm else None
    n_cells_scored = int(acts.shape[0])
    n_sources = int(acts.shape[1])

    names = pd.Index(ctx.adata.obs_names.astype(str))
    n_missing = int(len(names)) - n_cells_scored
    if n_missing:
        if int(pd.Index(acts.index.astype(str)).isin(names).sum()) != n_cells_scored:
            return ctx.refuse(
                "activity scores",
                f"the scorer returned {n_cells_scored:,} rows whose names do not all appear "
                f"among this object's {len(names):,} barcodes, so the scores cannot be put back "
                f"beside the cells they belong to. Padding them by position would align the "
                f"wrong cells silently.")
        acts = acts.reindex(names)
        if pvals is not None:
            pvals = pvals.reindex(names)
        ctx.caveat(
            f"{n_missing:,} of {len(names):,} cells have NO value in every column of the "
            f"activity result. Their row of the scored matrix was entirely zero, so decoupler "
            f"set them aside before fitting and returned a repaired object. They are kept here "
            f"as cells and carry NaN rather than a zero, because a zero in this array would "
            f"assert an activity of exactly none where the truth is that nothing was scored.")
    ctx.log(f"scored {n_sources:,} regulators over {n_cells_scored:,} cells"
            + (f"; {n_missing:,} cell(s) were empty and carry NaN" if n_missing else ""))
    ctx.emit_obsm("X_tf_activity", acts.to_numpy())

    # ------------------------------------------------------------ per regulator: what it had
    #
    # float32 AND ONE COPY. `to_numpy()` already hands back the scorer's own float32; asking for
    # float64 here doubles a cells-by-regulators array that is hundreds of megabytes on a cohort,
    # and taking |A| twice doubles it again. The summaries below are diagnostics, not the result.
    A = np.asarray(acts.to_numpy(), dtype="float32")
    absA = np.abs(A)
    # `scored` IS READ OFF THE RESULT, not recomputed from the rule. The count above predicts
    # which regulators survive; this records which ones did. Where the two disagree the prediction
    # is wrong about how decoupler matched the genes, and a caveat says so rather than the table
    # quietly carrying a `scored` column that no column of the result corresponds to.
    cov["scored"] = cov.index.isin(list(acts.columns))
    mismatch = int(((cov["targets_present"] >= ctx.config["min_targets"]) != cov["scored"]).sum())
    if mismatch:
        ctx.caveat(
            f"{mismatch:,} regulator(s) are on the wrong side of the min_targets rule as this "
            f"plugin counts target presence and as decoupler counted it. The `scored` column of "
            f"tables/regulator_coverage.csv is the RESULT and is right; `targets_present` beside "
            f"it is this plugin's count and disagrees for those rows, so read the coverage figure "
            f"for those regulators as approximate.")
    sd = (np.nanstd(A, axis=0, ddof=1) if n_cells_scored > 1 else np.zeros(n_sources))
    per_src = pd.DataFrame(
        {"mean_abs_activity": np.nanmean(absA, axis=0), "sd_activity": sd},
        index=pd.Index(acts.columns.astype(str), name="source"))
    sig = None
    if pvals is not None:
        # A CELL THAT WAS NOT SCORED IS NOT A NON-SIGNIFICANT ONE. Its p is NaN, `NaN < 0.05` is
        # False, and dividing by every cell would quietly report it as a test that came out
        # negative. The denominator is the cells that were actually tested.
        sig = np.asarray(pvals.to_numpy(), dtype="float32") < 0.05
        per_src["frac_cells_p_below_0.05"] = sig.sum(axis=0) / max(1, n_cells_scored)
    cov = cov.join(per_src, how="left")
    cov.index.name = "source"
    cov = cov.sort_values(["scored", "targets_present"], ascending=[False, False])
    cov_path = ctx.emit_table("regulator_coverage", cov)

    n_scored_reg = int(cov["scored"].sum())
    med_cov = float(cov.loc[cov["scored"], "coverage"].median()) if n_scored_reg else float("nan")
    ctx.caveat(
        f"{n_scored_reg:,} of {len(cov):,} regulators in the prior were scored; the rest had "
        f"fewer than min_targets={ctx.config['min_targets']} of their targets among the "
        f"{n_genes:,} detected genes of this matrix. A scored regulator carries a median "
        f"{100 * med_cov:.0f}% of its prior targets, so most of what the prior says about it is "
        f"not represented here. Both numbers are per regulator in "
        f"tables/regulator_coverage.csv.")
    ctx.caveat(
        f"The scores are t-values with {n_genes - 2:,} degrees of freedom - the DETECTED GENE "
        f"COUNT minus two, not the regulon size. That sets their scale: the same cells scored "
        f"over a differently filtered gene list give different numbers, so no threshold on these "
        f"values carries to another object or to another run of this one.")
    if sig is not None:
        frac = float(sig.sum()) / max(1, n_cells_scored * n_sources)
        ctx.caveat(
            f"{100 * frac:.1f}% of the {n_cells_scored * n_sources:,} cell-by-regulator tests "
            f"have an uncorrected two-sided p below 0.05. It is one test per cell per regulator "
            f"and nothing here corrects for their number; the figure describes the output, it is "
            f"not evidence that that many are real.")

    # ------------------------------------------------------------ per cell: depth against score
    # A cell whose whole row is NaN was never scored, and NaN is the right answer for it: it
    # reaches the panel as a point that is not drawn rather than as a cell whose activity is
    # nothing. numpy warns "Mean of empty slice" for each such row, which is a note about the
    # data and not a fault, so it is silenced HERE and said once, in the caveat above.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        cell_mean = np.nanmean(absA, axis=1)
    per_cell = pd.DataFrame(
        {"genes_detected": np.asarray(per_cell_detected, dtype=float),
         "mean_abs_activity": cell_mean},
        index=pd.Index(names, name="barcode"))
    p = ctx.populations()
    if p.groups is not None:
        lab = np.full(len(names), "", dtype=object)
        lab[np.asarray(p.mask)] = p.groups
        per_cell["label"] = lab
    rho_depth = _spearman(per_cell["genes_detected"], per_cell["mean_abs_activity"])
    ctx.caveat(
        f"Spearman {rho_depth:+.2f} between a cell's detected-gene count and the mean size of "
        f"its activities. The score is a correlation over every gene, so some relation is "
        f"expected; it is stated because populations differ in depth, and a difference in "
        f"activity between two of them is not biology until this is accounted for.")

    # ------------------------------------------------------------ per population: the answer
    #
    # A SENTINEL IS NOT A POPULATION. `UNRESOLVED` is the annotator declining to call a cell
    # type; a mean activity computed for it lands in the table beside the real populations and
    # reads as a cell type with that activity. Measured on a real cohort: PBS 677295 delivered
    # `activity_by_label.csv` with an `UNRESOLVED` row over 2,139 cells, and the host's own check
    # reported it as a declaration defect. `ctx.populations()` is the host's answer to the
    # question, so every plugin gives the same one and the caveat cannot be forgotten.
    by_label, no_pop_why = None, ""
    if p.groups is not None and len(p.groups):
        by_label = acts[p.mask].groupby(p.groups).mean()
        # THE INDEX IS NAMED. Grouping by a bare array leaves the index with no name at all, so
        # the CSV ships with an empty first header cell - a column of cell-type names that nothing
        # in the file says is a column of cell-type names, in the one table a reader opens by hand.
        by_label.index.name = "label"
        ctx.emit_table("activity_by_label", by_label)
    else:
        # TWO DIFFERENT ABSENCES, AND ONLY ONE OF THEM IS ABOUT THE ARGUMENTS. `groups is None` is
        # no label column. An EMPTY groups array is a label column in which every cell carries an
        # annotator sentinel - a finding about the annotation, which reads as a forgotten argument
        # if it is reported as one, and sends a user to fix a flag that was never the problem.
        no_pop_why = ("no label column was named" if p.groups is None else
                      f"a label column was named and every one of its {len(names):,} cells "
                      f"carries an annotator sentinel, so there is no population to group by")
        ctx.emit_table("activity_by_label",
                       acts.mean().to_frame("mean_activity").rename_axis("source"))
        ctx.caveat(f"Activity is summarised over all cells together rather than per population: "
                   f"{no_pop_why}.")

    # THE RANKING IS decoupler's OWN: the spread of a regulator's mean across groups, which is
    # what `summarize_acts(min_std=...)` keeps. It ranks by VARIABILITY and says nothing about
    # importance, and the caption says so where a reader will meet it.
    #
    # THE CRITERION TRAVELS WITH THE RANKING, because it is not always that one. With fewer than
    # two populations there is nothing to spread across and the fallback ranks on the spread across
    # CELLS, which is a different quantity; the captions print whichever was used rather than
    # naming summarize_acts on every run.
    if by_label is not None and len(by_label) > 1:
        spread = by_label.std(axis=0, ddof=1)
        ranked_by = ("the spread of its mean across populations - the criterion decoupler's own "
                     "summarize_acts uses")
    else:
        spread = pd.Series(sd, index=acts.columns)
        ranked_by = ("its standard deviation across cells, there being fewer than two populations "
                     "to spread across")
    ranked = list(spread.sort_values(ascending=False).dropna().index)

    # ------------------------------------------------------------ figures
    ctx.log("figures:")
    _fig_coverage(ctx, cov, ctx.config["min_targets"], cov_path)
    _fig_depth(ctx, per_cell, rho_depth)

    # decoupler's own redundancy check, over the prior AS MATCHED to this matrix. Guarded because
    # it is a second pass over the object and a prior with many thousands of regulators makes the
    # pair list quadratic: a failure here must cost the page a panel, never the run its result.
    #
    # THE THREE OUTCOMES ARE DIFFERENT SENTENCES, and one of them is a finding. Not computed, and
    # nothing is known about redundancy; computed and empty, and the regulons are ORTHOGONAL,
    # which the declared `when_absent` would otherwise mis-state as unchecked; computed and full,
    # and the pairs are named.
    pairs = None
    try:
        pairs = dc.check_corr(net, mat=ctx.adata, min_n=ctx.config["min_targets"], use_raw=False)
        pairs = pairs[pairs["source1"].isin(list(acts.columns))
                      & pairs["source2"].isin(list(acts.columns))]
    except Exception as e:                                                # noqa: BLE001
        ctx.log(f"    regulon overlap not computed: {e}")
        ctx.caveat("The prior's regulons were NOT compared with each other, so nothing here says "
                   "whether two of the regulators named below share most of their targets. Read "
                   "any pair as possibly one measurement.")
    if pairs is not None and not len(pairs):
        ctx.caveat("The prior's regulons WERE compared and no two of the scored regulators share "
                   "enough targets to correlate at all. The overlap panel is absent because "
                   "there is nothing in it, not because the check was skipped.")
    elif pairs is not None:
        thr = ctx.config["redundancy_above"]
        n_red = int((pairs["corr"].abs() > thr).sum())
        try:
            _fig_overlap(ctx, pairs, n_sources, thr)
        except Exception as e:                                            # noqa: BLE001
            ctx.log(f"    F3_regulon_overlap not drawn: {e}")
        ctx.caveat(
            f"{n_red:,} pair(s) of the {n_sources:,} scored regulators have target-weight "
            f"vectors correlating above |{thr}| on this matrix. Such a pair scores almost "
            f"identically in every cell whatever its biology, so two names from one pair are one "
            f"measurement and not two findings.")

    # A PANEL THAT CANNOT BE DRAWN IS NOT AN ABSENT OUTPUT. `ctx.absent` is the list of things the
    # run could not produce and renders as a defect; a declared panel that is optional renders
    # with the plugin's own `when_absent` and is a property of the data. Putting these there would
    # say the same thing twice, once in the wrong tone.
    if by_label is not None and len(by_label) and ranked:
        _fig_by_population(ctx, by_label[ranked[:int(ctx.config["top_regulators"])]],
                           ranked_by, len(ranked))
    else:
        ctx.log("    F4_by_population not drawn: "
                + (no_pop_why or "no regulator could be ranked"))

    # THE LAYOUT, NEVER THE REPRESENTATION. `ctx.embedding()` is 30-50 columns whose axes carry no
    # ordering and whose first two draw as a ball whatever the data holds; `ctx.layout()` is the
    # two coordinates made to be looked at, and it returns None rather than a fallback when the
    # object has none. Nothing here is drawn on anything else.
    xy = ctx.layout()
    lay_full, lay_key = ctx.layout_key()
    if xy is None:
        # THE REASON PRINTED IS THE REASON THAT FIRED. This branch also catches an empty ranking,
        # and reporting that as a missing layout sends a reader to compute a UMAP they already have.
        ctx.log("    F5_activity_map not drawn: the object carries no two-column layout")
        ctx.caveat("The object carries no two-column layout, so the per-cell activities were not "
                   "mapped. The first two columns of a wider representation are two arbitrary "
                   "coordinates of it and not a picture of it, so nothing was drawn in its "
                   "place; every score is still in obsm[X_tf_activity].")
    elif not ranked:
        ctx.log("    F5_activity_map not drawn: no regulator could be ranked")
        ctx.caveat("No regulator could be ranked, so none was mapped. Every score is still in "
                   "obsm[X_tf_activity] and in tables/regulator_coverage.csv.")
    else:
        _fig_map(ctx, np.asarray(xy, dtype=float)[:, :2], acts, ranked,
                 lay_key or "layout", lay_full or "layout", ranked_by)
        ctx.caveat(f"The per-cell map is drawn on obsm[{lay_full}], the object's own layout - "
                   f"this plugin computes none. The scores themselves were fitted per cell in "
                   f"gene space and do not depend on it.")

    ctx.headline = (f"{n_sources:,} of {len(cov):,} regulators scored per cell; median "
                    f"{100 * med_cov:.0f}% of each one's prior targets present")


def selftest(ctx):
    """Prove the CALL works against the versions installed on THIS machine.

    Not an import check. The failures worth catching here are all downstream of the import: the
    prior's schema moving, `run_ulm` renaming a keyword, an obsm key that is no longer where the
    result is put. Every one of those imports cleanly and dies inside the first real call.

    Asserts SHAPES and FINITENESS, never a biological answer - the fixture is synthetic and there
    is no correct activity to check against.
    """
    import decoupler as dc
    import numpy as np

    net = dc.get_collectri(organism="human", split_complexes=False)
    assert len(net) > 1000, f"the prior looks truncated: {len(net)} edges"
    for col in ("source", "target", "weight"):
        assert col in net.columns, f"the prior has no {col!r} column; its schema moved"
    ctx.log(f"  prior: {len(net):,} edges, {net['source'].nunique():,} regulators")

    # A fixture whose genes ARE the prior's targets, so there is something to score.
    targets = sorted(set(net["target"].astype(str)))[:400]
    A = ctx.fixture(n_cells=120, genes=targets)
    A.X = A.layers["lognorm"]

    # EVERY KEYWORD THIS PLUGIN PASSES, PASSED HERE. `min_n` decides which regulators exist,
    # `batch_size` decides how the matrix is walked, and both are silently dropped by a signature
    # that renamed them - decoupler 2.x is the version where this whole call surface moved.
    returned = dc.run_ulm(mat=A, net=net, source="source", target="target", weight="weight",
                          min_n=5, batch_size=64, use_raw=False, verbose=False)
    # THE SAME BRANCH run() TAKES. run_ulm returns None and writes in place unless a cell was
    # empty, in which case it returns a repaired COPY and the caller's object holds nothing.
    scored = A if returned is None else returned
    assert "ulm_estimate" in scored.obsm, "run_ulm no longer writes obsm['ulm_estimate']"
    assert "ulm_pvals" in scored.obsm, "run_ulm no longer writes obsm['ulm_pvals']"
    acts = scored.obsm["ulm_estimate"]
    pv = np.asarray(scored.obsm["ulm_pvals"].values, dtype=float)
    assert acts.shape[0] == scored.n_obs, f"{acts.shape[0]} rows for {scored.n_obs} cells"
    assert acts.shape[1] > 0, "no regulator was scored on data built from the prior's own targets"
    assert np.isfinite(np.asarray(acts.values, dtype=float)).all(), "non-finite activity scores"
    assert np.isfinite(pv).all() and pv.min() >= 0 and pv.max() <= 1, "p-values out of [0, 1]"
    ctx.log(f"  scored {acts.shape[1]:,} regulators over {acts.shape[0]:,} cells")

    # The redundancy panel's own call. It is a different entry point with a different signature,
    # and its default `use_raw=True` fails on any object without a .raw - which is every object
    # this plugin is handed.
    pairs = dc.check_corr(net, mat=A, min_n=5, use_raw=False)
    for col in ("source1", "source2", "corr"):
        assert col in pairs.columns, f"check_corr no longer returns {col!r}; its schema moved"
    ctx.log(f"  regulon overlap: {len(pairs):,} correlated pair(s) among the scored regulators")

    # The figure path is part of this plugin and part of the environment: matplotlib has a
    # backend, and none of the above exercises it.
    plt = ctx.plot()
    fig, ax = plt.subplots(figsize=(ctx.figure.SINGLE, ctx.figure.SINGLE))
    ax.scatter([0, 1], [0, 1], s=2)
    ctx.figure.rasterize_points(ax)
    plt.close(fig)
    ctx.log("  ok   the drawing path imports and draws")
