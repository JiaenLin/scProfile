"""Cell-cycle phase per cell, and the check that a trajectory is not a cell-cycle axis.

WHY THIS RUNS FIRST AND IS A PREREQUISITE OF PSEUDOTIME

A trajectory that is secretly a cell-cycle axis is the commonest false positive in this class of
analysis: cells order beautifully, the pseudotime correlates with real genes, and what has been
recovered is proliferation. The check costs seconds, and it is the reason this plugin sits at the
front rather than being an optional extra.

IT DECLARES A REQUIREMENT, AND THAT IS A CHANGE. The five-file version set `needs_env: false`
and ran in whatever interpreter the host happened to be, on the argument that "a separate
environment for a two-minute scoring step would be friction with nothing behind it". That argument
was true when the builder built one environment per plugin, and it stopped being true when the
resolver started merging requirements: this constraint is the same numpy/pandas/scanpy stack four
other plugins already declare, so it joins their environment and costs nothing at all. What it
buys is that the score no longer depends on an interpreter nobody pinned - and the call it wraps
is precisely one whose behaviour has moved between versions, which is what the selftest below
exists to catch.

WHAT THE PANELS ARE FOR, AND WHY THREE OF THE FIVE ARE CHECKS

This method has no failure mode that looks like a failure. Every cell gets a phase, always: the
rule is `S` by default, `G2M` where the G2M score is the larger, and `G1` ONLY where both scores
are negative - no threshold anywhere, so "cycling" here means "one of two scores came out above
zero". Where that zero sits is not a property of the biology. It is the mean of a CONTROL SET
drawn at random from the genes in this object, matched to the panel by expression bin, and three
separate things move it without raising anything:

  the panel did not match      a human panel against another organism's symbols scores near zero
                               and reads as a resting population (`F3`, and the refusal above it);
  the control draw             a different `random_state` is a different control set and a
                               different zero (`F4` measures how many calls move);
  the cells' own sparsity      a cell with few detected genes has a noisier panel mean, and the
                               binning controls for a gene's ABUNDANCE, not for a cell's depth
                               (`F5`).

So the page is three diagnostics and two results, and the checks come first on purpose: `F3`, `F4`
and `F5` are the three ways above, one panel each, and a reader who meets a cycling fraction
before them cannot tell which of the three they have.

`F2` IS A RESULT, AND WAS DECLARED A DIAGNOSTIC. The scatter of S against G2M is the panel the
gene sets' own paper drew (Tirosh et al., Science 2016, Fig. 3a) with the decision boundary added,
and the boundary was the argument for calling it a check. It is not one: what a reader takes off
that panel is the cycling fraction and the phase of every cell, which is this plugin's answer.
Distance from the boundary only becomes a check when something MEASURES it, and that is `F4` -
which redraws the control set, moves the boundary, and counts the calls that follow it. Labelling
the answer a diagnostic put it above two of the three checks that qualify it, which is the one
ordering the reporter exists to prevent.
"""

PLUGIN = {
    "api": 1,
    "version": "0.3.0",
    "summary": "cell-cycle phase per cell, and the check that a trajectory is not a "
               "cell-cycle axis",
    "when_to_use": "you are about to read a trajectory, or want to know which populations are "
                   "cycling before anything else is interpreted",
    "wraps": {"tool": "scanpy", "homepage": "https://scanpy.readthedocs.io",
              "license": "BSD-3-Clause",
              "cite": "Tirosh et al., Science 2016 (gene sets); "
                      "Wolf et al., Genome Biol 2018 (scanpy)"},

    # NOTHING IS REQUIRED. The panel match is what decides whether this can run, and that is a
    # property of the gene names rather than of a capability the host can resolve - so it is
    # checked in `run` and answered with a refusal that says which names were looked for.
    "inject": {"required": [], "optional": ["lognorm", "label"]},
    # Same omission as velocity's: it writes obs[phase], and `phase` is a declared capability
    # another plugin may ask for. A producer that does not say so is not a producer.
    "provides": ["phase"],
    "produces": ["obs[phase]", "obs[S_score]", "obs[G2M_score]"],

    # WHAT WAS SHOWN TO IT - the honest list, which the plan reports so a user can see which of
    # their own columns and layers each plugin will touch. An under-declared plugin looks like one
    # that reads nothing at all.
    #
    # `obs[{label}]` IS READ AND WAS NOT DECLARED. The planner builds its settings block from
    # `needs_*` and `sees` and from nothing else, so while this list held three entries the plan
    # told a user that cellcycle would touch no label column - and F1 groups every phase call by
    # it, F2 carries it in its source data. `inject.optional` naming the capability is not the
    # same statement: that says the plugin does less without it, not that it reads it.
    "sees": ["X", "layers[{lognorm}]", "var_names", "obs[{label}]"],

    "config": {
        "min_panel_genes": {"type": "int", "default": 10, "min": 1,
                            "help": "refuse below this many matched genes in either panel - a "
                                    "score computed from a handful of genes is arithmetically "
                                    "fine and reads as 'not cycling' when it means 'the panel "
                                    "did not match your gene names'"},
        # SCANPY'S OWN DEFAULTS, DECLARED RATHER THAN INHERITED - the same move `decoupler` made
        # for `min_n`. All three change every score in the object, and until they were config
        # they were module constants: correct, passed explicitly, and invisible to anyone reading
        # the run's own parameters. A number that decides the answer belongs where the report can
        # print it and a user can move it.
        "n_bins": {"type": "int", "default": 25, "min": 2,
                   "help": "expression bins the control set is drawn from. scanpy's own default "
                           "is 25. The score is the panel mean MINUS the control mean, so this "
                           "changes every score in the object"},
        "random_state": {"type": "int", "default": 0, "min": 0,
                         "help": "seed for the random control-gene draw. scanpy's own default is "
                                 "0. The draw sets where zero is, and the phase call is a "
                                 "comparison against zero - so this moves calls, and "
                                 "stability_seeds measures how many"},
        "ctrl_as_ref": {"type": "bool", "default": True,
                        "help": "may the control genes themselves be part of the reference set? "
                                "scanpy's own default is True and its documentation says it "
                                "BECOMES FALSE IN SCANPY 2.0 - passing it explicitly is what "
                                "stops that release changing this plugin's scores silently. On a "
                                "scanpy too old to have the parameter, True is the only "
                                "behaviour and False is refused rather than ignored"},
        "stability_seeds": {"type": "int", "default": 3, "min": 0, "max": 25,
                            "help": "how many EXTRA control draws to re-score with, to measure "
                                    "how much of the phase call is the draw rather than the "
                                    "cells. Each costs one more pass of the scoring step; 0 "
                                    "skips the check and F4 is reported absent"},
    },

    "per_unit": None,
    "cost": "trivial", "cores": 1,
    # Measured, not estimated: fitted from this plugin's own instances in one run on a 10-sample mouse single-nucleus cohort (~99k cells). ONE dataset on ONE machine - a starting point that is right for scheduling, not a universal constant. Every run re-fits and prints its own.
    # Fitted from one instance; the split is indeterminate.
    # The diagnostic panels added since that measurement allocate one chunk of the matrix at a
    # time (see `_detected_per_cell`) rather than a copy of it, so the rate should move little -
    # but it has NOT been re-measured, and the next real run will print its own.
    "memory_gb_per_100k": 7.3,
    "design_aware": True,

    # THE SAME STACK four other plugins already declare, so this joins their resolved environment
    # rather than adding one. Constraints, not pins: scanpy tolerates any patch of 1.10 for this
    # call, and claiming otherwise would force an environment nobody can share.
    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {
            "scanpy": ">=1.10,<1.11",
            "anndata": ">=0.10,<0.12",
            "numpy": ">=1.24,<2",
            "pandas": ">=2.0,<3",
            "matplotlib": ">=3.7",
        },
    },

    "upstream": {
        "docs": "https://scanpy.readthedocs.io",
        "read": "2026-08-25",
        "defaults_changed": [
            "use_raw=False, and the values are ASSIGNED rather than named with `layer=`. "
            "scanpy's default `use_raw=None` means USE .raw IF PRESENT - so the same plugin, on "
            "two objects differing only in whether an upstream step left a .raw behind, scores "
            "DIFFERENT values, and nothing in the output says which was used. An object whose "
            ".raw holds counts rather than log-normalised values gets a score computed on counts.",
            "n_bins=25 and random_state=0 are scanpy's own defaults, kept and now CONFIG rather "
            "than module constants. Changing either changes every score, so they belong where a "
            "run prints them and a user can move them - and `stability_seeds` exists because "
            "random_state is not a formality: it selects the control set the score is measured "
            "against.",
            "ctrl_as_ref is PASSED, at scanpy's own default of True. Its documentation states it "
            "will change to False in scanpy 2.0, which would change every score in this plugin's "
            "output on the day that release lands, with nothing failing. Passed explicitly, the "
            "release moves nothing here. Where the installed scanpy is old enough not to have "
            "the parameter, it is not passed - True is that version's only behaviour - and "
            "asking for False there is REFUSED rather than silently ignored.",
            "The panels are matched by casing - exact, title-case, upper-case - and the match "
            "count is reported. The published panel is HUMAN symbols and a mouse object is "
            "indexed by mouse ones; an unmatched panel produces a low score that looks exactly "
            "like a resting population.",
        ],
        "not_used": [
            "gene_pool, which restricts the control universe. Relevant where a gene class should "
            "not be eligible as a control, and unused because no such case has been argued here.",
            "score_genes with a custom panel: a different gene set is a different plugin's "
            "declaration, not a flag on this one.",
            "Regressing the scores out of the expression matrix, which scanpy's own cell-cycle "
            "how-to demonstrates. It is a REMOVAL, it is not reversible downstream of here, and "
            "the difference between a cycling population and a proliferation artefact is a "
            "judgement about the experiment rather than about the scores.",
        ],
        "gotchas": [
            "ctrl_size CANNOT BE PASSED to score_genes_cell_cycle. It computes it itself as "
            "min(len(s_genes), len(g2m_genes)) and then forwards **kwargs, so passing the keyword "
            "raises `got multiple values for keyword argument`. Nothing in the signature says so; "
            "six lines of its source do. This reached a live cohort, from a plugin that shipped "
            "no selftest because it declared it needed no environment - and the environment is "
            "not the only thing a selftest proves.",
            "The score is NOT the panel mean. It is the panel mean minus the mean of a control "
            "set drawn from matched expression bins, and that subtraction is what makes zero a "
            "meaningful reference - a naive panel mean is dominated by how abundant its genes "
            "happen to be.",
            "`score_genes` IN THE PINNED SCANPY TAKES NO `layer` ARGUMENT. It was added later, "
            "so `layer=` passed through `score_genes_cell_cycle`'s **kwargs raises `got an "
            "unexpected keyword argument`. An earlier version of this record quoted a signature "
            "that HAD it - read from whatever scanpy the host interpreter happened to carry, "
            "which is exactly the reading a plugin with no declared environment can make. The "
            "values are assigned to X instead, which works on every version.",
            "THE PHASE RULE HAS NO THRESHOLD IN IT, and it is three lines of source rather than "
            "anything the docstring says: `phase` starts as S for every cell, becomes G2M where "
            "G2M_score > S_score, and becomes G1 only where BOTH scores are negative. So `G1` is "
            "a residual bucket - resting cells, quiescent cells and every cell whose panel found "
            "nothing, together - and the cycling fraction is the fraction of cells with any "
            "positive score. The gene sets' own paper called a cell cycling at >=2-fold "
            "upregulation with t-test p < 0.01 for one of the programmes (Tirosh et al., Science "
            "2016). Nothing here reproduces that bar, and a cell one thousandth above zero is "
            "reported identically to one far above it.",
            "ZERO IS SET BY A RANDOM DRAW, so the phase call is stochastic in a way nothing in "
            "the output announces. The control set is sampled per expression bin with "
            "`random_state`; a different seed is a different zero and moves the calls nearest it. "
            "F4 re-scores at further seeds and reports how many moved - a run with "
            "stability_seeds=0 cannot say, and says that instead.",
            "SCALED VALUES BREAK THE BINNING SILENTLY. After scaling to zero mean and unit "
            "variance every gene's mean is ~0, so the expression bins the control set is matched "
            "on carry no information and the 'matched' control is an arbitrary draw "
            "(scverse/scanpy#3030, open at the time of reading). The scores are still produced "
            "and still look like scores. This plugin measures the matrix minimum and says so "
            "rather than assuming it was handed log-normalised values.",
            "THE CONTROL SET IS DRAWN FROM THE GENES IN THIS OBJECT. An object subset to highly "
            "variable genes gives the same cells a different score from the same object "
            "unsubset, because the bins and the control universe are different - with no error "
            "and no line in the output. Two datasets' scores are not comparable for the same "
            "reason.",
            "scanpy samples the control genes ONCE PER BIN, not once per gene of the panel "
            "(scverse/scanpy#3845, open, milestoned). The reference implementation this method "
            "comes from draws ~100 control genes for EACH gene of the set, so a panel whose "
            "genes are concentrated in low-expression bins gets a control composition that does "
            "not match it, and the scores shift - the reporter of the issue measured 'almost "
            "completely negative' scores on a mixed list. That bias is in every score below; "
            "what it is not is random, so it does not average out over cells.",
            "ctrl_size is min(matched S, matched G2M), so a POOR gene-name match shrinks the "
            "control set as well as the panel. Both halves of the subtraction get noisier at "
            "once, which is why F3 reports the match and the detection rather than only the "
            "count of names found.",
        ],
    },

    # WHAT ITS PAGE SHOULD CONTAIN. Three diagnostics and two results, listed here in the order
    # the reporter will lay them out, so the declaration reads as the page reads. Each of the
    # three checks is one way this method returns a confident phase for cells it knows nothing
    # about, and a reader who meets a cycling fraction before them cannot tell which they have.
    #
    # `F2_scores` WAS DECLARED `diagnostic` AND IS NOT ONE. It shows every cell's two scores and
    # the phase each was called - the answer, not a check on whether the answer means anything -
    # and `shows` is what decides where the reporter puts it, so the label alone was enough to
    # print the result above two of the three checks that qualify it. The boundary drawn on it is
    # only a check once something measures distance from it, which is F4.
    #
    # `shows` is the whole of the reporter's knowledge. It knows no id here and never will.
    "report": {
        "figures": [
            {"id": "F3_panel_detection", "shows": "diagnostic", "required": True,
             "question": "are the panel genes actually detected in these cells, or is a low "
                         "score an empty panel?",
             "source": "figures/F3_panel_detection.csv"},
            # OPTIONAL, AND THE ABSENCE IS A SETTING RATHER THAN A PROPERTY OF THE DATA - which
            # is worth saying, because it is the one panel here a user can turn off.
            {"id": "F4_seed_stability", "shows": "diagnostic", "required": False,
             "question": "would a different draw of control genes give the same phase call?",
             "source": "figures/F4_seed_stability.csv",
             "when_absent": "stability_seeds was set to 0, so the scoring ran once and nothing "
                            "measured how much of the phase call is the control draw rather than "
                            "the cells. Read every phase count on this page as one realisation "
                            "of a stochastic call."},
            {"id": "F5_score_vs_detection", "shows": "diagnostic", "required": False,
             "question": "does the cycling call track how many genes were detected per cell?",
             "source": "figures/F5_score_vs_detection.csv",
             "when_absent": "the cells could not be binned by detected-gene count: either they "
                            "do not differ in it, or the matrix carries negative values, in "
                            "which case a zero is not an absent gene and counting zeros measures "
                            "nothing. The depth confound is untested here, which is not the same "
                            "as absent."},
            {"id": "F2_scores", "shows": "result", "required": True,
             "question": "what did each cell score, and which phase did that make it?",
             "source": "figures/F2_scores.csv"},
            {"id": "F1_phase_by_population", "shows": "result", "required": False,
             "question": "which populations carry the cycling signal?",
             "source": "figures/F1_phase_by_population.csv",
             "when_absent": "the object carries no cell-type or cluster column, so the phase "
                            "calls cannot be attributed to a population. The cohort-wide "
                            "fractions in the headline and in F2 are all that this data "
                            "supports."},
        ],
        # THE PAIRING, AND IT IS CHECK-AND-CLAIM RATHER THAN TWO CLAIMS. `pseudotime` produces an
        # ordering; the question "is that ordering proliferation?" is answered here, from a gene
        # panel, and there, from where the ordering runs. Neither page answers it alone, and the
        # reporter can name the missing half as an absence rather than leave it silent.
        "reads_with": ["pseudotime"],
    },

    "cannot_show": [
        "Phase is SCORED from a gene set, not measured. A cell scored G2M is one whose G2M genes "
        "are relatively high, which is not the same as a cell in G2M.",
        "THE CALL CONTAINS NO THRESHOLD. G1 is assigned only where both scores are negative, so "
        "it is a residual bucket holding resting cells and cells whose panel found nothing, and "
        "'cycling' means a score came out above zero rather than that a cell passed any test. "
        "The gene sets' own paper required >=2-fold upregulation and t-test p < 0.01 to call a "
        "cell cycling (Tirosh et al., Science 2016); this does not.",
        "ZERO IS NOT A FIXED REFERENCE. It is the mean of a control set drawn at random from the "
        "genes present in THIS object, so the same cells score differently in a differently "
        "filtered object, and scores from two datasets are not comparable.",
        "The gene sets are the standard human ones, title-cased for mouse. They are not "
        "tissue-specific and were not curated for this dataset.",
        "On single nuclei the signal is weaker - cell-cycle transcripts are partly cytoplasmic - "
        "so a low score is as consistent with the assay as with a resting population.",
        "A cycling population is not a proliferating one. Scoring says which genes are high, not "
        "how many cells divided.",
    ],
}

#: scanpy's own defaults. These are the values `config` declares, repeated here as literals
#: because the declaration is read from SOURCE by a host that never imports this file - it must
#: hold literals only, so the two cannot be written once. `run` reads `ctx.config`; the selftest,
#: which is handed no config, reads these. `ctrl_size` is deliberately absent: see
#: upstream.gotchas.
N_BINS, SEED, CTRL_AS_REF = 25, 0, True

#: The three phases scanpy's own rule can produce, in cycle order. Written down because the rule
#: is `S` by default, `G2M` where its score is larger, `G1` only where BOTH are negative - so the
#: set is closed, and a fourth value arriving means the installed scanpy changed the rule.
PHASES = ("G1", "S", "G2M")

#: One colour per phase, fixed across every panel here. G1 is GREY because it is the bucket that
#: also holds "nothing was scored", and a hue would give it the standing of a call.
PHASE_COLOURS = {"G1": "#D9D9D9", "S": "#0072B2", "G2M": "#D55E00"}

#: Tirosh et al. regulon, the de-facto standard. HUMAN symbols; matched across casings below.
S_GENES = """MCM5 PCNA TYMS FEN1 MCM2 MCM4 RRM1 UNG GINS2 MCM6 CDCA7 DTL PRIM1 UHRF1 CENPU
HELLS RFC2 RPA2 NASP RAD51AP1 GMNN WDR76 SLBP CCNE2 UBR7 POLD3 MSH2 ATAD2 RAD51 RRM2 CDC45 CDC6
EXO1 TIPIN DSCC1 BLM CASP8AP2 USP1 CLSPN POLA1 CHAF1B BRIP1 E2F8""".split()

G2M_GENES = """HMGB2 CDK1 NUSAP1 UBE2C BIRC5 TPX2 TOP2A NDC80 CKS2 NUF2 CKS1B MKI67 TMPO
CENPF TACC3 FAM64A SMC4 CCNB2 CKAP2L CKAP2 AURKB BUB1 KIF11 ANP32E TUBB4B GTSE1 KIF20B HJURP
CDCA3 HN1 CDC20 TTK CDC25C KIF2C RANGAP1 NCAPD2 DLGAP5 CDCA2 CDCA8 ECT2 KIF23 HMMR AURKA PSRC1
ANLN LBR CKAP5 CENPE CTCF NEK2 G2E3 GAS2L3 CBX5 CENPA""".split()


def _match(genes, var_names):
    """The panel genes present in THIS object, matched by casing rather than by assumption.

    An object may be indexed by human symbols, mouse symbols, or something else entirely. Trying
    each casing and reporting how many matched is the difference between a low score that means
    "not cycling" and one that means "the panel did not match your gene names".
    """
    have = {str(v): str(v) for v in var_names}
    upper = {str(v).upper(): str(v) for v in var_names}
    out = []
    for g in genes:
        if g in have:
            out.append(have[g])
        elif g.capitalize() in have:
            out.append(have[g.capitalize()])
        elif g.upper() in upper:
            out.append(upper[g.upper()])
    return out


def _accepts(fn, name):
    """Does the INSTALLED function take this keyword? Asked of the signature, never assumed.

    Two of this plugin's three recorded failures are a keyword that was well-formed against one
    version of scanpy and forbidden by another - `ctrl_size`, then `layer` - and both arrived as a
    TypeError seconds into a real cohort. `ctrl_as_ref` is the same shape of risk in the other
    direction: it exists in the scanpy this plugin declares, its default is documented to CHANGE
    in scanpy 2.0, and it does not exist at all in older ones. Asking is three lines and the
    answer is printed, so the run records which behaviour it got.
    """
    import inspect
    try:
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):                                       # a C or wrapped callable
        return False


def _score_once(sc, A, s, g2m, *, n_bins, seed, extra):
    """One complete scoring, returned as arrays rather than left in `obs`.

    `score_genes_cell_cycle` writes `S_score`, `G2M_score` and `phase` into obs and OVERWRITES
    them on every call, so a plugin that re-scores to measure stability would silently ship the
    last seed's answer as its result. Taking copies out is what makes the reference scoring
    survive its own stability check.
    """
    import numpy as np
    sc.tl.score_genes_cell_cycle(A, s_genes=s, g2m_genes=g2m, use_raw=False,
                                 n_bins=int(n_bins), random_state=int(seed), **extra)
    return (np.asarray(A.obs["S_score"], dtype=float).copy(),
            np.asarray(A.obs["G2M_score"], dtype=float).copy(),
            np.asarray(A.obs["phase"].astype(str)).copy())


def _is_sparse(m):
    """Sparse without importing scipy - which this plugin does not declare and must not import."""
    return hasattr(m, "toarray")


def _matrix_min(X):
    """The smallest value in the matrix, cheaply, or 0.0 for an empty one.

    Used for ONE question: are these values scaled? A negative minimum says they are centred, and
    on centred values every gene's mean is ~0, which is what makes the control-gene binning
    meaningless (scverse/scanpy#3030). For a sparse matrix the stored values are the only
    non-zeros, so their minimum answers it without densifying anything.
    """
    import numpy as np
    if X is None:
        return 0.0
    if _is_sparse(X):
        d = getattr(X, "data", None)
        return float(np.min(d)) if d is not None and getattr(d, "size", 0) else 0.0
    a = np.asarray(X)
    return float(np.min(a)) if a.size else 0.0


def _detected_per_cell(X, chunk=5000):
    """Genes with a non-zero value in each cell, computed a block of rows at a time.

    IN CHUNKS BECAUSE THE WHOLE-MATRIX FORM IS THE EXPENSIVE ONE. `(X > 0)` on a dense object of
    any size allocates a boolean copy of it; on a large cohort that is the difference between a
    diagnostic and a killed job. The block size is rows, so the peak is bounded by the gene count
    rather than by the cell count.
    """
    import numpy as np
    n = int(X.shape[0])
    out = np.zeros(n, dtype="int64")
    for a in range(0, n, int(chunk)):
        b = min(a + int(chunk), n)
        out[a:b] = np.asarray((X[a:b] > 0).sum(axis=1)).ravel()
    return out


def _panel_detection(A, s, g2m):
    """Per panel gene: in how many cells it is non-zero, and its mean, on the SCORED values.

    A gene that is in `var_names` and detected in no cell contributes nothing to the panel mean
    and still counts toward `ctrl_size`, because that is `min(len(s), len(g2m))` over the names
    that MATCHED. So the number of names found is not the number of genes doing any work, and
    only this separates them.
    """
    import numpy as np
    import pandas as pd
    rows = []
    for panel, genes in (("S", list(s)), ("G2M", list(g2m))):
        if not genes:
            continue
        sub = A[:, genes].X
        M = sub.toarray() if _is_sparse(sub) else np.asarray(sub)
        M = np.asarray(M, dtype=float)
        det = (M > 0).sum(axis=0)
        mean = M.mean(axis=0)
        for g, d, mu in zip(genes, np.asarray(det).ravel(), np.asarray(mean).ravel()):
            rows.append({"gene": str(g), "panel": panel, "n_cells_detected": int(d),
                         "detection_rate": float(d) / max(1, int(A.n_obs)),
                         "mean_value": float(mu)})
    return pd.DataFrame(rows)


def _stability_table(ref, alt):
    """How the phase calls at the reference seed were re-called at the other seeds.

    Rows are the reference call, columns are what each further control draw made of the same
    cell, and the cells are counted once per seed - so a row sums to n_cells x n_seeds. The
    diagonal is agreement; everything off it is a call that belongs to the draw rather than to
    the cell.
    """
    import numpy as np
    import pandas as pd
    ref = np.asarray(ref)
    rows = []
    for p in PHASES:
        m = ref == p
        row = {"reference_phase": p, "n_cells": int(m.sum()), "n_seeds": len(alt)}
        for q in PHASES:
            row[q] = int(sum(int(((np.asarray(a) == q) & m).sum()) for _sd, a in alt))
        denom = max(1, row["n_cells"] * max(1, len(alt)))
        row["agreement"] = float(row[p]) / denom
        rows.append(row)
    return pd.DataFrame(rows).set_index("reference_phase")


# ------------------------------------------------------------------------------------ figures
#
# Each panel is drawn by its own function and called under its own guard, so a panel that cannot
# be drawn on some object costs that panel and not the four after it. The whole figure block used
# to sit under one `try`, which meant the first failure took the page.
#
# In page order - the three checks, then the two results. The functions are defined in the order
# `run` calls them, which is not the same thing and never has to be: `shows` is what the reporter
# lays a page out by, and emission order is invisible to it.
#
#   CHECKS
#   F3 panel detection   were the panel genes detected at all? The panel that separates "not
#                        cycling" from "nothing to score", and the first one to read.
#   F4 seed stability    how many calls move when the control set is redrawn.
#   F5 vs detection      whether the cycling call tracks per-cell depth rather than biology.
#
#   RESULTS
#   F2 scores            the scatter the gene sets' own paper drew, plus the decision boundary -
#                        every cell's two scores and the phase they made. The answer per cell.
#   F1 by population     the answer per population: which populations carry the signal.


def _fit_column(fig, width, *, pad=0.06, tries=6, grow=True):
    """Size the axes so the WHOLE panel - key, tick labels and all - prints at `width`.

    `figsize=(F.SINGLE, ...)` sizes the AXES, and `emit_figure` saves with `bbox_inches="tight"`,
    so everything outside them is ADDED to the file rather than fitted into it. Measured on this
    plugin's own panels: a three-entry key in the right margin made F1 119 mm wide and F4 105 mm,
    against the 85 mm single column they were all declared at. Nothing fails - the figure is
    simply scaled down when it is placed, and 7 pt labels arrive at 5 pt, which is the one
    publication defect that is invisible in the file and obvious on the page.

    A candidate for the shared module; it stays here until a second plugin has used it.
    """
    try:
        fig.canvas.draw()
        cap, last, best = float(width) * 1.8, None, None
        for _ in range(int(tries)):
            try:
                bb = fig.get_tightbbox()
            except TypeError:                                   # older matplotlib wants a renderer
                bb = fig.get_tightbbox(fig.canvas.get_renderer())
            over = float(bb.width) + float(pad) - float(width)
            w, h = fig.get_size_inches()
            if over <= 0.03 and (best is None or w > best):
                best = w                       # the widest canvas that still fits the column
            if abs(over) <= 0.03 or (over < 0 and not grow):
                return
            new = min(cap, max(1.5, w - over))
            if last is not None and abs(new - last) < 0.01:    # a constraint the width cannot move
                return
            last = new
            fig.set_size_inches(new, h)
            fig.canvas.draw()
        # AN ARTIST THAT DOES NOT SCALE - a long annotation, a wide tick label - can hold the
        # panel over the column however narrow the canvas gets. End on the widest size that was
        # measured to fit rather than on wherever the last iteration happened to stop.
        if best is not None:
            fig.set_size_inches(best, fig.get_size_inches()[1])
    except Exception:                                                     # noqa: BLE001
        return                       # a panel slightly off the column beats a panel not drawn


def _key_above(fig, ax, *, ncol=3):
    """The categorical key as one row ABOVE the panel, where it costs height and not width.

    `F.legend_outside` is the tool's convention and is right for a panel whose data is a cloud;
    for a stacked bar it is not, because the bar already spans the full width and the key in the
    right margin is pure overflow - see `_fit_column` for what that cost in millimetres.
    """
    h, l = ax.get_legend_handles_labels()
    fig.subplots_adjust(top=0.97)          # the key sits above the figure; the margin was white
    return fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=int(ncol),
                      handletextpad=0.4, columnspacing=1.1, borderaxespad=0)


def _pct_axis(ax, axis="x"):
    """Ticks as percentages. A fraction axis labelled 0.0-1.0 is read as a percentage anyway."""
    from matplotlib.ticker import FuncFormatter
    getattr(ax, f"{axis}axis").set_major_formatter(FuncFormatter(lambda v, _p: f"{100 * v:g}"))


def _wilson(k, n, z=1.96):
    """95% interval for a proportion, closed form - scipy is not a dependency of this plugin.

    On the depth panel the bins hold thousands of cells and the interval is hairline thin, which
    is the point: it says the trend there is not sampling noise, and it would widen visibly on a
    cohort where the bins are small.
    """
    import numpy as np
    k, n = np.asarray(k, dtype=float), np.maximum(np.asarray(n, dtype=float), 1.0)
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return np.clip(c - h, 0, 1), np.clip(c + h, 0, 1)


def _free_corner(x, y, top, *, box=(0.66, 0.30)):
    """The corner of an axes the data is not in, as `annotate` keywords: `xy`, `ha`, `va`.

    A number printed on a panel has to sit somewhere, and a fixed corner is right for one shape
    of data and wrong for its mirror image - which on a trend panel is not a rare case but the
    other half of the outcome the panel is drawn to distinguish. Corners are tried in reading
    order and the first one no point falls into wins; where every corner is occupied the last is
    returned, because a legible overlap in a known place beats a search that returns nothing.
    """
    import numpy as np
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    xf = (x - np.nanmin(x)) / max(float(np.nanmax(x) - np.nanmin(x)), 1e-9)
    yf = y / max(float(top), 1e-9)
    bw, bh = box
    corners = ((0.03, 0.03, "left", "bottom"), (0.03, 0.97, "left", "top"),
               (0.97, 0.03, "right", "bottom"), (0.97, 0.97, "right", "top"))
    pick = corners[-1]
    for c in corners:
        cx, cy, ha, va = c
        x0 = cx if ha == "left" else cx - bw
        y0 = cy if va == "bottom" else cy - bh
        hit = ((xf > x0 - .02) & (xf < x0 + bw + .02)
               & (yf > y0 - .02) & (yf < y0 + bh + .02)).any()
        if not hit:
            pick = c
            break
    return dict(xy=(pick[0], pick[1]), ha=pick[2], va=pick[3])


def _fig_panel_detection(ctx, det):
    """Detection rate of every matched panel gene, ranked - the licence for everything below."""
    import numpy as np
    # A REQUIRED PANEL THAT RETURNS SILENTLY IS THE ONE GAP A READER CANNOT EXPLAIN. The reporter
    # will print it NOT PRODUCED - correctly, it is declared required - and the page would say
    # nothing about why. The other three panels here all say; this one returned bare.
    if det is None or not len(det):
        ctx.caveat(
            "F3_panel_detection was not drawn: no per-gene detection could be computed for the "
            "matched panels, so nothing on this page separates a low score from a panel that "
            "found nothing to score. The phase calls below stand, but the licence for reading "
            "them is missing.")
        return
    F, plt = ctx.figure, ctx.plot()
    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.72))
    dead, widest = [], 1
    for panel in ("S", "G2M"):
        d = det[det["panel"] == panel].sort_values("detection_rate", ascending=False)
        if not len(d):
            continue
        y = np.asarray(d["detection_rate"].values, dtype=float)
        x = np.arange(1, len(y) + 1)
        widest = max(widest, len(y))
        ax.plot(x, y, color=PHASE_COLOURS[panel], lw=0.9, marker="o", ms=2.0,
                mec="none", label=f"{panel} panel  ({len(y)} genes matched)")
        # THE DEAD TAIL, MARKED WHERE IT IS rather than only counted in the caption. These genes
        # are in var_names, contribute nothing to the panel mean, and still count toward
        # ctrl_size - so the length of this tail is what separates "not cycling" from "nothing
        # was scored", and it was the one quantity the panel did not show.
        z = y <= 0
        if z.any():
            ax.plot(x[z], y[z], ls="none", marker="o", ms=3.0, mfc="white",
                    mec=PHASE_COLOURS[panel], mew=0.8)
            dead.append(f"{panel} {int(z.sum())}/{len(y)}")
    ax.set_xlabel("panel genes, ranked within their own panel")
    ax.set_ylabel("fraction of cells with a non-zero value")
    ax.set_ylim(0, 1)
    ax.set_xlim(0, widest + 1)
    if dead:
        ax.annotate("hollow = detected in NO cell (" + ", ".join(dead) + ")\n"
                    "these still count toward the control-set size",
                    xy=(0.98, 0.72), xycoords="axes fraction", ha="right", va="top",
                    fontsize=6, color=F.INK, linespacing=1.35)
    ax.legend(loc="upper right", markerscale=2.0, handletextpad=0.5, borderaxespad=0.2)
    _fit_column(fig, F.SINGLE)
    n_zero = int((det["detection_rate"] <= 0).sum())
    ctx.emit_figure(
        "F3_panel_detection", fig,
        caption=(f"Every panel gene that matched this object's gene names, ranked by the "
                 f"fraction of cells it is detected in, on the values that were scored. Each "
                 f"panel is ranked within itself, so a position on the x axis is not the same "
                 f"gene in the two curves. A curve that falls to the floor early means most of "
                 f"the panel contributes nothing, and a score built from the rest is a score over "
                 f"a handful of genes - which is arithmetically fine and reads as a resting "
                 f"population. {n_zero} of {len(det)} matched genes are detected in no cell at "
                 f"all (hollow markers); they still count toward the control-set size, because "
                 f"that is the number of NAMES matched."),
        source=det.set_index("gene"))


def _fig_scores(ctx, S, G2M, phase):
    """S against G2M with the decision boundary - the panel the gene sets' own paper drew."""
    import numpy as np
    import pandas as pd
    A = ctx.adata
    F, plt = ctx.figure, ctx.plot()
    dd = {"barcode": A.obs_names.astype(str), "S_score": S, "G2M_score": G2M,
          "phase": np.asarray(phase)}
    lab = ctx.obs("label")
    if lab is not None:
        dd["label"] = lab.astype(str).values
    ph = np.asarray(phase)
    n_cells = int(ph.size)
    # TALLER THAN THE COLUMN IS WIDE, because the axes below is SQUARE: with equal aspect the
    # box takes the smaller of the two, so a square canvas leaves the panel height-limited and
    # `bbox_inches="tight"` then trims the unused width off the sides - a panel declared at 85 mm
    # that arrives at 75 mm. The extra height is what lets the square grow to the full column.
    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 1.16))
    lo = float(min(np.nanmin(S), np.nanmin(G2M)))
    hi = float(max(np.nanmax(S), np.nanmax(G2M)))
    pad = 0.04 * (hi - lo) if hi > lo else 1.0
    # ONE SQUARE AXIS FOR BOTH SCORES, and it is not cosmetic. The S/G2M boundary is the line
    # y = x, and on an axis whose scales differ that line is not drawn at 45 degrees - so the
    # panel showed points assigned by a rule the picture contradicted. Equal limits and equal
    # aspect are what make "whichever score is larger" readable off the figure.
    ax.set_xlim(lo - pad, hi + pad)
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_aspect("equal", adjustable="box")
    ax.fill_between([lo - pad, 0.0], lo - pad, 0.0, color="#F4F4F4", lw=0, zorder=0)
    for phase_name in PHASES:
        m = ph == phase_name
        if m.any():
            ax.scatter(S[m], G2M[m], s=1.4, c=PHASE_COLOURS[phase_name], label=phase_name,
                       alpha=0.45, linewidths=0, rasterized=True)
    F.rasterize_points(ax)
    # THE RULE, DRAWN, because the distance from these lines IS the confidence of the call and
    # there is no other confidence to report. Below and left of the axes is G1 (shaded); above
    # them the diagonal separates S from G2M. A cell sitting on a line is one control draw from
    # the other answer.
    #
    # THE DIAGONAL IS CLIPPED AT THE ORIGIN, and drawing it into the third quadrant was wrong:
    # both scores are negative there, every cell is G1 whichever is larger, and a boundary drawn
    # across a region it does not divide invents a distinction the rule does not make.
    if hi > 0:
        ax.plot([0, hi + pad], [0, hi + pad], color=F.INK, lw=0.6, ls=":", zorder=2)
    ax.axhline(0, color=F.INK, lw=.5, zorder=2)
    ax.axvline(0, color=F.INK, lw=.5, zorder=2)
    ax.set_xlabel("S score  (panel mean - control mean)")
    ax.set_ylabel("G2M score  (panel mean - control mean)")
    # THE KEY IS THE REGIONS THEMSELVES. A swatch in the margin makes a reader map three colours
    # onto three areas that the axes have already named; the count belongs where the cells are,
    # and it keeps the panel at one column wide.
    frac = {p: float((ph == p).mean()) for p in PHASES}
    cnt = {p: int((ph == p).sum()) for p in PHASES}
    where = {"G1": (0.03, 0.03, "left", "bottom"), "S": (0.97, 0.03, "right", "bottom"),
             "G2M": (0.03, 0.97, "left", "top")}
    for p in PHASES:
        x, y, ha, va = where[p]
        ax.annotate(f"{p}\n{cnt[p]:,}  ({100 * frac[p]:.1f}%)",
                    xy=(x, y), xycoords="axes fraction", ha=ha, va=va, fontsize=6.5,
                    color=(F.INK if p == "G1" else PHASE_COLOURS[p]), linespacing=1.3,
                    bbox=dict(boxstyle="square,pad=0.25", ec="none", alpha=0.72,
                              fc=("#F4F4F4" if p == "G1" else "white")))
    _fit_column(fig, F.SINGLE)
    # THE ASSAY IS READ, NOT ASSUMED. This sentence used to be written for every object: "on
    # single nuclei that is expected, because cell-cycle transcripts are partly cytoplasmic".
    # It is true of nuclei and false of whole cells, and a caption is where a reader is least
    # able to check it - so it is said where the host says the assay is nuclei, offered as a
    # possibility where the assay was never declared, and not said at all on whole cells.
    assay = str(getattr(ctx, "assay", "") or "")
    if assay == "nucleus":
        origin = ("on the single NUCLEI this was run on that is expected, because cell-cycle "
                  "transcripts are partly cytoplasmic, and is as consistent with the assay as "
                  "with a resting population")
    elif not assay:
        origin = ("the assay was not declared, so a compressed cloud cannot be told apart from "
                  "the preparation: on nuclei it is expected, because cell-cycle transcripts are "
                  "partly cytoplasmic, and on whole cells it is not")
    else:
        origin = (f"the assay was declared {assay}, not nucleus, so cytoplasmic loss of "
                  f"cell-cycle transcripts does not explain it")
    ctx.emit_figure(
        "F2_scores", fig,
        caption=(f"S against G2M score, one point per cell ({n_cells:,} cells), with the boundary "
                 f"the phase call is made on; both axes carry the same scale, so the dotted line "
                 f"is the true y = x boundary. The rule has no threshold in it: a cell is G1 only "
                 f"where BOTH scores are negative (the shaded quadrant), and otherwise it is "
                 f"whichever score is larger (either side of the dotted diagonal, which divides "
                 f"nothing where both scores are negative and is not drawn there). So a cell just "
                 f"above a line is reported exactly like one far above it, and a cloud sitting at "
                 f"the origin means the panel found little to score - {origin}. Counts are "
                 f"printed in the region they belong to. Every cell of the object is drawn, "
                 f"annotator "
                 f"sentinels included: this is a per-cell result, and only the per-population "
                 f"panel excludes them."),
        source=pd.DataFrame(dd).set_index("barcode"))


def _fig_stability(ctx, tab, seeds):
    """How much of the phase call is the cell, and how much is the control draw."""
    import numpy as np
    if tab is None or not len(tab) or not seeds:
        return
    d = tab[tab["n_cells"] > 0]
    if not len(d):
        return
    F, plt = ctx.figure, ctx.plot()
    cols = [p for p in PHASES]
    frac = d[cols].div(d[cols].sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.35, 0.36 * len(frac) + 1.0)))
    y = np.arange(len(frac))
    # ONLY THE DISAGREEMENT IS DRAWN, and the full-composition version could not show it. Each
    # row of that bar was its own colour from end to end - a call that moves 1% of the time and
    # one that moves 30% both render as a solid bar, because the quantity the panel exists to
    # report was 1% of the axis. Here the axis is the moved fraction, so the check is legible
    # whether it passes or fails, and the colours say WHICH phase the cells moved to.
    left = np.zeros(len(frac))
    for c in cols:
        v = np.array([0.0 if p == c else float(frac.loc[p, c]) for p in frac.index])
        ax.barh(y, v, left=left, color=PHASE_COLOURS[c], label=f"re-called {c}", height=.68,
                edgecolor="white", linewidth=0.3)
        left += v
    top = float(max(left.max(), 1e-3))
    ax.set_xlim(0, top * 1.34)
    for i, p in enumerate(frac.index):
        ax.annotate(f"{100 * left[i]:.2f}% moved", xy=(left[i] + top * 0.03, y[i]),
                    va="center", ha="left", fontsize=6, color=F.INK)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{p}  (n={int(d.loc[p, 'n_cells']):,})" for p in frac.index])
    ax.set_ylim(len(frac) - 0.5, -0.5)          # one row is one row, not the whole panel
    _pct_axis(ax)
    ax.set_xlabel("% of (cell, seed) pairs re-called as a DIFFERENT phase")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    _key_above(fig, ax, ncol=3)
    _fit_column(fig, F.SINGLE)
    total = int(d["n_cells"].sum()) * len(seeds)
    agree = int(sum(int(d.loc[p, p]) for p in frac.index))
    moved = 1.0 - (agree / total if total else 1.0)
    ctx.emit_figure(
        "F4_seed_stability", fig,
        caption=(f"Each row is the cells called that phase at the reference control draw; the bar "
                 f"is the fraction of those cells that {len(seeds)} further control draw(s) "
                 f"(seeds {', '.join(str(s) for s in seeds)}) called something ELSE, coloured by "
                 f"what they were called instead. The rest of each row - the number in brackets - kept "
                 f"its phase and is not drawn, so that the moved fraction is readable at any "
                 f"size; note the axis maximum. Only the control set changes: the gene panels, "
                 f"the values and the cells are identical, so everything here is a call that "
                 f"belongs to the draw rather than to the cell. {100 * moved:.1f}% of (cell, "
                 f"seed) pairs changed phase. A high figure does not mean the scoring is wrong; "
                 f"it means the cells sit near the boundary in F2, and that the phase COUNTS "
                 f"should not be quoted to more precision than this."),
        source=tab)


def _fig_depth(ctx, detected, phase, S, G2M):
    """Is the cycling call reading biology, or reading how deeply each cell was sequenced?"""
    import numpy as np
    import pandas as pd
    if detected is None:
        ctx.caveat(
            "F5_score_vs_detection was not drawn: the scored values are centred, so a zero is not "
            "an absent gene and counting zeros per cell would measure nothing. Whether the "
            "cycling call tracks per-cell depth is untested here, which is not the same as it "
            "being absent.")
        return
    F, plt = ctx.figure, ctx.plot()
    det = np.asarray(detected, dtype=float)
    q = pd.qcut(pd.Series(det), 10, labels=False, duplicates="drop")
    if int(q.nunique()) < 3:
        ctx.caveat(
            "F5_score_vs_detection was not drawn: these cells fall into fewer than three "
            "distinct bins of detected-gene count, so there is no depth gradient to test the "
            "phase call against. The confound is untested here, which is not the same as absent.")
        return None
    df = pd.DataFrame({"bin": np.asarray(q.values, dtype=float), "detected_genes": det,
                       "S_score": np.asarray(S, dtype=float),
                       "G2M_score": np.asarray(G2M, dtype=float),
                       "cycling": (np.asarray(phase) != "G1").astype(float)})
    g = df.groupby("bin").agg(n_cells=("detected_genes", "size"),
                              detected_genes_median=("detected_genes", "median"),
                              S_score_median=("S_score", "median"),
                              G2M_score_median=("G2M_score", "median"),
                              cycling_fraction=("cycling", "mean"))
    # THE TREND THIS PANEL DRAWS, RETURNED. It is the one number that says whether the phase
    # call tracks the biology or the sequencing depth, and it was drawn and thrown away - so
    # the headline could report 45.5% cycling while this panel, further down the same page,
    # showed the called fraction FALLING as detection rises.
    _x = g["detected_genes_median"].to_numpy(dtype=float)
    _y = g["cycling_fraction"].to_numpy(dtype=float)
    _rho = None
    if _x.size >= 3 and _x.std() > 0 and _y.std() > 0:
        _rx = pd.Series(_x).rank().to_numpy()
        _ry = pd.Series(_y).rank().to_numpy()
        _rho = float(np.corrcoef(_rx, _ry)[0, 1])
    # TWO PANELS ON ONE DEPTH AXIS: the call, and the scores it is made from. The medians were
    # already in this panel's own source table and nothing drew them, so the page could report
    # that the CALL tracks depth without ever showing that the SCORES do - which is the
    # mechanism, and the half a reader needs to believe the first.
    fig, (ax, ax2) = plt.subplots(
        2, 1, sharex=True, figsize=(F.SINGLE, F.SINGLE * 1.02),
        gridspec_kw=dict(height_ratios=[1.55, 1.0], hspace=0.12))
    lo95, hi95 = _wilson(g["cycling_fraction"].values * g["n_cells"].values, g["n_cells"].values)
    ax.fill_between(_x, lo95, hi95, color=F.GREY, lw=0, zorder=1)
    ax.plot(_x, _y, color=F.INK, lw=1.2, marker="o", ms=3.4, zorder=3, clip_on=False)
    cohort = float(df["cycling"].mean())
    ax.axhline(cohort, color=F.INK, lw=0.5, ls="--", zorder=2)
    ax.annotate(f"cohort {100 * cohort:.1f}%", xy=(_x[-1], cohort), xytext=(0, 3),
                textcoords="offset points", ha="right", va="bottom", fontsize=6, color=F.INK)
    ax.set_ylabel("cells called S or G2M (%)")
    # A PERCENTAGE AXIS DOES NOT GO ABOVE 100, and one that spans a tenth of a point turns a
    # hairline interval into a band across the panel. Headroom for the annotation, floored at two
    # points and capped at the only value the quantity can reach.
    top_y = min(1.0, max(0.02, float(np.nanmax(hi95)), cohort) * 1.32)
    ax.set_ylim(0, top_y)
    _pct_axis(ax, "y")
    # THE FINDING, STATED ON THE FIGURE. This is the panel that decides whether the cycling
    # fraction on this page is biology or library depth, and it carried no number at all: a
    # reader had to eyeball a slope and take the direction on trust.
    if _rho is not None:
        drift = 100.0 * (_y[-1] - _y[0])
        # SHORT LINES ON PURPOSE. A caption can run to sixty characters and a label inside an
        # 85 mm panel cannot: text does not shrink with the axes, so a long annotation pushes the
        # panel off the column instead of wrapping. The reasoning is in the caption; what is on
        # the figure is the direction, the coefficient and the two ends of the trend.
        verdict = ("FALLS as depth rises" if _rho <= -0.6 else
                   "RISES with depth" if _rho >= 0.6 else "is not monotone in depth")
        # AND IT GOES IN A CORNER THE DATA IS NOT IN. Fixed at the bottom left it was legible
        # on a falling trend and sat on the first three points of a rising one - and this panel
        # is drawn precisely because either can happen.
        # The cohort line is data too - it spans the whole width, and a corner it runs through
        # is not free.
        corner = _free_corner(np.r_[_x, _x], np.r_[_y, np.full(_x.shape, cohort)], top_y)
        ax.annotate(f"the cycling call {verdict}\n"
                    f"Spearman rho = {_rho:+.2f} over {len(_x)} depth bins\n"
                    f"{100 * _y[0]:.1f}% to {100 * _y[-1]:.1f}% ({drift:+.1f} pts) across them",
                    xycoords="axes fraction", fontsize=6, color=F.INK, linespacing=1.5,
                    **corner)
    for name, col in (("S", "S_score_median"), ("G2M", "G2M_score_median")):
        ax2.plot(_x, g[col].values, color=PHASE_COLOURS[name], lw=1.2, marker="o", ms=3.0,
                 mec="none", label=f"{name} score")
    ax2.axhline(0, color=F.INK, lw=0.5)
    # THE NOTE GOES ON THE SIDE OF THE LINE THE CURVES ARE NOT ON, and inside the panel: where
    # every score is negative the zero line sits against the top spine, and a label placed above
    # it lands in the panel overhead.
    _lo2, _hi2 = ax2.get_ylim()
    _zf = (0.0 - _lo2) / max(_hi2 - _lo2, 1e-9)
    _above = float(np.nanmedian(g["S_score_median"].values[-2:])) < 0
    if _above and _zf > 0.88:                      # the line is against the top spine
        _above = False
    elif not _above and _zf < 0.12:                # and against the bottom one
        _above = True
    ax2.annotate("zero - the phase boundary", xy=(_x[-1], 0), xytext=(0, 2 if _above else -3),
                 textcoords="offset points", ha="right", va=("bottom" if _above else "top"),
                 fontsize=6, color=F.INK)
    ax2.set_ylabel("median score")
    ax2.set_xlabel("genes detected per cell (bin median)")
    ax2.legend(loc="best", markerscale=2.0, handletextpad=0.5, borderaxespad=0.2)
    _fit_column(fig, F.SINGLE)
    # TEN BINS WERE ASKED FOR AND ARE NOT WHAT WAS DRAWN. `duplicates="drop"` collapses quantile
    # edges that tie, so an object whose cells share detected-gene counts gets fewer - the guard
    # above accepts as few as three - and the caption said "ten" whatever came out. It is
    # counted, and the smallest bin is named, because a bin holding two cells has a cycling
    # fraction of 0, 0.5 or 1 whatever the biology.
    n_bins_drawn, smallest = int(len(g)), int(g["n_cells"].min())
    trend = ("" if _rho is None else
             f"Over these bins the fraction called S or G2M has Spearman rho {_rho:+.2f} against "
             f"the bin's median detected-gene count, printed on the panel. ")
    ctx.emit_figure(
        "F5_score_vs_detection", fig,
        caption=(f"TOP: cells in {n_bins_drawn} bins of how many genes were detected in them "
                 f"(ten were asked for; quantile edges that tie are collapsed), against the "
                 f"fraction of each bin called S or G2M, with a 95% interval on each bin "
                 f"(shaded) and the "
                 f"cohort fraction dashed. BOTTOM: the median of the two scores the call is made "
                 f"from, on the same depth axis, against the zero the call compares them to - the "
                 f"mechanism behind whatever the top panel shows. The smallest bin holds "
                 f"{smallest:,} cell(s), and a bin holding few cells moves in steps rather than "
                 f"smoothly. {trend}The control set is matched to the panel on a GENE's abundance "
                 f"and on nothing about the CELL, so a cell with few detected genes has a noisier "
                 f"panel mean and a noisier control mean at once. A line with ANY slope - rising "
                 f"or falling - means part of the cycling call is the library rather than the "
                 f"biology, and any comparison of cycling fractions between groups that differ in "
                 f"depth is reading that first. A flat line is the check passing."),
        source=g)
    return _rho


def _fig_by_population(ctx, phase):
    """Scored phase per population - the result, and the panel the trajectory check is made on."""
    import numpy as np
    import pandas as pd
    # A SENTINEL IS NOT A POPULATION. The directory-shaped version of this plugin grouped by
    # the raw label column, so an annotator's refusal to call a cell type appeared in the
    # per-population panel as a population with a cycling fraction. `ctx.populations()` is the
    # host's one answer to that question and attaches the caveat itself.
    mask, groups = ctx.populations()
    if groups is None or not len(groups):
        ctx.caveat(
            "F1_phase_by_population was not drawn: this object carries no cell-type or cluster "
            "column, so the phase calls cannot be attributed to a population. Nothing was "
            "dropped - every cell keeps its own phase, S_score and G2M_score.")
        return
    F, plt = ctx.figure, ctx.plot()
    ct = pd.crosstab(pd.Series(groups, name="label"),
                     pd.Series(np.asarray(phase)[np.asarray(mask)], name="phase"))
    for c in PHASES:
        if c not in ct:
            ct[c] = 0
    ct = ct[list(PHASES)]
    n_per = ct.sum(axis=1)
    # STABLE, so populations that tie - every one of them, where nothing scored - keep the
    # order they came in rather than a different one on every run.
    frac = ct.div(n_per, axis=0).sort_values("G1", kind="mergesort")
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.6, 0.21 * len(frac) + 0.95)))
    left = np.zeros(len(frac))
    for c in PHASES:
        ax.barh(np.arange(len(frac)), frac[c], left=left, color=PHASE_COLOURS[c], label=c,
                height=.72, edgecolor="white", linewidth=0.3)
        left += frac[c].values
    # THE COHORT'S OWN G1 FRACTION, so a population can be read against the page's headline
    # rather than against the eye. Bars are stacked G1 first, so this line is where a population
    # with exactly the cohort's cycling fraction would break.
    cohort_g1 = float(ct["G1"].sum()) / max(1, int(n_per.sum()))
    ax.axvline(cohort_g1, color=F.INK, lw=0.6, ls="--", zorder=3)
    _right = cohort_g1 > 0.6                      # the label goes on the side with room for it
    ax.annotate(f"cohort {100 * (1 - cohort_g1):.1f}% cycling", xy=(cohort_g1, -0.62),
                xytext=(-3 if _right else 3, 0), textcoords="offset points",
                ha=("right" if _right else "left"), va="bottom", fontsize=6, color=F.INK)
    # NAMES CUT TO THEIR SHORTEST UNAMBIGUOUS TAIL, and the n kept beside them. A hierarchical
    # label is a path, and at full length twelve of them took half the width of a panel declared
    # at one column - while the one number that says whether a population's fraction means
    # anything, how many cells it holds, was not on the figure at all.
    short = F.short_labels(list(frac.index))
    ax.set_yticks(np.arange(len(frac)))
    ax.set_yticklabels([f"{short.get(p, p)}  ({int(n_per[p]):,})" for p in frac.index])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_ylim(len(frac) - 0.5, -0.95)
    _pct_axis(ax)
    ax.set_xlabel("% of cells in the population")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    _key_above(fig, ax, ncol=3)
    _fit_column(fig, F.SINGLE)
    smallest = int(n_per.min())
    ctx.emit_figure(
        "F1_phase_by_population", fig,
        caption=(f"Scored cell-cycle phase per population, ordered by the fraction called S or "
                 f"G2M, with the number of cells in each population in brackets - the smallest "
                 f"here holds {smallest:,}, and a small population's fraction moves in steps "
                 f"rather than smoothly. Names are cut to their shortest unambiguous tail; the "
                 f"full labels are in the source table. The dashed line is the cohort's own "
                 f"cycling fraction. Phase is SCORED from a gene panel, not measured: a cell "
                 f"called G2M is one whose G2M panel genes are relatively high, and G1 is the "
                 f"bucket for cells where neither panel scored above zero. Use this to check "
                 f"whether a trajectory follows the cycling fraction - if it does, the trajectory "
                 f"may be a cell-cycle axis. Read it against F4: a population whose calls move "
                 f"between control draws has a fraction here that moves with them. Annotator "
                 f"sentinels are not shown as populations."),
        source=ct.assign(n_cells=ct.sum(axis=1)))


# ---------------------------------------------------------------------------------------- run

def run(ctx):
    import pandas as pd
    import scanpy as sc

    C = ctx.config
    A = ctx.adata
    # THE JOURNAL CONVENTIONS, APPLIED BEFORE ANYTHING IS SCORED. Not for the settings' sake - it
    # is the cheapest possible check that this environment can draw at all, and the alternative is
    # discovering a broken matplotlib backend after the scoring is done.
    ctx.plot()

    s = _match(S_GENES, A.var_names)
    g2m = _match(G2M_GENES, A.var_names)
    ctx.log(f"panel matched: S {len(s)}/{len(S_GENES)}, G2M {len(g2m)}/{len(G2M_GENES)}")

    # A panel that barely matches produces a score that is arithmetically fine and means nothing.
    # Refusing is better than returning a column somebody will colour a UMAP by.
    floor = C["min_panel_genes"]
    if len(s) < floor or len(g2m) < floor:
        ctx.caveat("Nothing was scored.")
        return ctx.refuse(
            "phase",
            f"only {len(s)}/{len(S_GENES)} S and {len(g2m)}/{len(G2M_GENES)} G2M panel genes are "
            f"in this object, below the declared minimum of {floor}. That is a gene-NAMING "
            f"mismatch, not a biological result - check whether var_names are symbols for the "
            f"right organism.")

    if A.X is None:
        return ctx.refuse("phase", "the object has no X to score")

    # use_raw=None - scanpy's default - means USE .raw IF PRESENT. Named explicitly; see
    # upstream.defaults_changed.
    #
    # AND THE LAYER IS ASSIGNED, NOT PASSED. `score_genes` in the scanpy this plugin declares
    # takes no `layer` argument at all - it was added later - so `layer=` reaches it through
    # `score_genes_cell_cycle`'s **kwargs and raises `got an unexpected keyword argument`. That
    # is the whole reason a plugin running in the host interpreter was moved to a declared
    # environment: the call was well-formed against whatever scanpy the host happened to have and
    # is not against the one this plugin says it needs. `ctx.X` is the host's answer to "the
    # values this plugin should work on" and needs no keyword.
    lognorm = ctx.keys.get("lognorm")
    layer = lognorm if lognorm and lognorm in A.layers else None
    scored_from = f"layers[{layer!r}]" if layer else "X"
    A.X = ctx.X
    ctx.log(f"scoring from {scored_from} (use_raw=False, explicitly)")

    # ctrl_as_ref IS ASKED FOR, not inherited: scanpy documents its default changing to False in
    # 2.0, which would change every score here on the day that release lands. Where the installed
    # scanpy is too old to have it, True is the only behaviour that version has - so it is not
    # passed, and asking for False is refused rather than quietly ignored.
    extra, ctrl_ref_note = {}, ""
    if _accepts(sc.tl.score_genes, "ctrl_as_ref"):
        extra["ctrl_as_ref"] = bool(C["ctrl_as_ref"])
        ctrl_ref_note = f"ctrl_as_ref={bool(C['ctrl_as_ref'])}, passed explicitly"
    elif not C["ctrl_as_ref"]:
        ctx.caveat("Nothing was scored.")
        return ctx.refuse(
            "phase",
            f"ctrl_as_ref=False was asked for and this scanpy ({sc.__version__}) has no such "
            f"parameter on `score_genes` - the behaviour it selects does not exist here, and "
            f"passing the keyword would raise inside a function whose name gives no hint why.\n"
            f"  Fix: leave ctrl_as_ref at True, which is this version's only behaviour, or "
            f"install a scanpy that has the parameter.")
    else:
        ctrl_ref_note = (f"this scanpy ({sc.__version__}) predates `ctrl_as_ref`; the behaviour "
                         f"True selects is its only one")
    ctx.log(f"  {ctrl_ref_note}")

    # ctrl_size is NOT passable here; see upstream.gotchas. The control set is sized by the
    # PANELS that matched this object, not by score_genes' own default of 50.
    ctrl = min(len(s), len(g2m))
    n_bins, seed = int(C["n_bins"]), int(C["random_state"])

    # SCALED VALUES BREAK THE BINNING AND NOTHING SAYS SO. Measured rather than assumed: on
    # centred values every gene's mean is ~0, the expression bins carry no information, and the
    # "matched" control set is an arbitrary draw (scverse/scanpy#3030).
    xmin = _matrix_min(A.X)
    scaled = xmin < 0
    if scaled:
        ctx.log(f"  the scored values reach {xmin:.2f} - they are CENTRED, not log-normalised")

    S_ref, G_ref, ph_ref = _score_once(sc, A, s, g2m, n_bins=n_bins, seed=seed, extra=extra)
    counts = pd.Series(ph_ref).value_counts()
    cycling_fraction = float((ph_ref != "G1").mean())
    ctx.log(f"phase: {dict(counts)}")

    # ---------------------------------------------------------------- is the call the cells'?
    # The same panels, the same values, the same cells - a different random control set. Anything
    # that moves belongs to the draw, and until this was measured the phase counts were quoted as
    # if they were a property of the data.
    alt, stab, moved = [], None, float("nan")
    n_seeds = int(C["stability_seeds"])
    for k in range(1, n_seeds + 1):
        _s, _g, _p = _score_once(sc, A, s, g2m, n_bins=n_bins, seed=seed + k, extra=extra)
        alt.append((seed + k, _p))
        ctx.log(f"  re-scored at random_state={seed + k}: "
                f"{100 * float((_p != ph_ref).mean()):.1f}% of phase calls changed")
    if alt:
        stab = _stability_table(ph_ref, alt)
        total = int(stab["n_cells"].sum()) * len(alt)
        agree = int(sum(int(stab.loc[p, p]) for p in PHASES))
        moved = 1.0 - (agree / total if total else 1.0)

    # THE REFERENCE SCORING IS WHAT SHIPS. `score_genes_cell_cycle` overwrites obs on every call,
    # so after the stability draws the object holds the LAST seed's answer; every consumer below
    # reads these arrays, and obs is put back for anything that reads the object itself.
    A.obs["S_score"] = S_ref
    A.obs["G2M_score"] = G_ref
    A.obs["phase"] = pd.Categorical(ph_ref)

    # ---------------------------------------------------------------- what was there to score
    det = _panel_detection(A, s, g2m)
    n_zero = int((det["detection_rate"] <= 0).sum()) if len(det) else 0
    if len(det):
        ctx.log(f"panel detection: median {100 * float(det['detection_rate'].median()):.1f}% of "
                f"cells per gene, {n_zero} of {len(det)} matched genes detected in none")
    # Counting zeros only means something where a zero means an absent gene. On centred values it
    # does not, so the depth panel is refused rather than drawn on a number that is not detection.
    per_cell = None if scaled else _detected_per_cell(A.X)

    # ---------------------------------------------------------------- figures
    # Each under its own guard: a panel that cannot be drawn on some object costs that panel, not
    # the four after it. The whole block used to sit under one `try`.
    ctx.log("figures:")
    # WHAT A PANEL MEASURED, KEPT. The loop called each figure for its side effect and dropped
    # whatever it returned, so the depth trend - the one number saying whether the phase call
    # tracks detection rather than cycling - was computed, drawn, and discarded before the
    # headline was written.
    _drawn = {}
    for fn, args in ((_fig_panel_detection, (ctx, det)),
                     (_fig_scores, (ctx, S_ref, G_ref, ph_ref)),
                     (_fig_stability, (ctx, stab, [sd for sd, _p in alt])),
                     (_fig_depth, (ctx, per_cell, ph_ref, S_ref, G_ref)),
                     (_fig_by_population, (ctx, ph_ref))):
        try:
            _drawn[fn.__name__] = fn(*args)
        except Exception as e:                                            # noqa: BLE001
            ctx.log(f"  {fn.__name__} not drawn: {type(e).__name__}: {e}")
    _depth_rho = _drawn.get("_fig_depth")

    ctx.emit_obs("phase", ph_ref)
    ctx.emit_obs("S_score", S_ref)
    ctx.emit_obs("G2M_score", G_ref)

    # ---------------------------------------------------------------- caveats, from the data
    ctx.caveat(
        f"Scored from {scored_from} with use_raw=False, stated explicitly: scanpy's default would "
        f"have used .raw where present, so an object that had one would have been scored on "
        f"different values with nothing in the output saying so. Those values were assigned to X "
        f"before scoring, because the pinned scanpy's `score_genes` has no `layer` argument.")
    ctx.caveat(
        f"The score is the panel mean minus the mean of a control set drawn from matched "
        f"expression bins (ctrl_size={ctrl}, sized by the matched panels because scanpy computes "
        f"it and forbids the keyword; n_bins={n_bins}, random_state={seed}, {ctrl_ref_note}). "
        f"That subtraction is what makes zero a meaningful reference; a naive panel mean is "
        f"dominated by how abundant its genes happen to be. The control set is drawn from the "
        f"genes IN THIS OBJECT, so the same cells in a differently filtered object score "
        f"differently, and these scores are not comparable with another dataset's.")
    ctx.caveat(
        f"Scored from {len(s)} S and {len(g2m)} G2M panel genes present in this object, out of "
        f"{len(S_GENES)} and {len(G2M_GENES)} declared"
        + (f"; {n_zero} of those {len(det)} matched genes are detected in NO cell and contribute "
           f"nothing but still count toward the control-set size. See F3." if len(det) else "."))
    if scaled:
        ctx.caveat(
            f"THE SCORED VALUES ARE CENTRED (minimum {xmin:.2f}), not log-normalised. On centred "
            f"values every gene's mean is close to zero, so the expression bins the control set "
            f"is matched on carry no information and the control is an arbitrary draw rather than "
            f"an abundance-matched one (scverse/scanpy#3030, open). The scores below were still "
            f"produced and still look like scores. Pass a log-normalised layer if one exists.")
    if alt:
        ctx.caveat(
            f"{100 * moved:.1f}% of phase calls changed when the control set was redrawn at "
            f"{len(alt)} further seed(s) ({', '.join(str(sd) for sd, _p in alt)}), with the "
            f"panels, values and cells identical. The phase call is a comparison against a zero "
            f"that a random draw sets, so that fraction is the precision of every phase count "
            f"here - see F4.")
    else:
        ctx.caveat(
            "stability_seeds=0, so the scoring ran once and nothing here measures how much of the "
            "phase call is the control draw. The counts below are one realisation of a "
            "stochastic call, not a fixed property of the cells.")
    if ctx.assay == "nucleus":
        ctx.caveat(
            "This is single-NUCLEUS data. Cell-cycle transcripts are partly cytoplasmic, so "
            "scores are compressed relative to whole cells and a low score is as consistent with "
            "the assay as with a resting population.")
    elif not ctx.assay:
        ctx.caveat(
            "The assay was not declared or detected. If these are nuclei the scores are "
            "compressed; pass --assay nucleus so this is stated rather than left open.")
    ctx.caveat(
        f"{100 * cycling_fraction:.1f}% of cells score S or G2M. Read that as 'these genes are "
        f"relatively high', not as a proliferation rate - and note the call carries NO threshold: "
        f"G1 is assigned only where both scores are negative, so this counts every cell with one "
        f"score above zero. The gene sets' own paper called a cell cycling at >=2-fold "
        f"upregulation with t-test p < 0.01 for one of the programmes.")

    # ITS OWN DIAGNOSTIC, AGAINST ITS OWN HEADLINE. If the fraction called cycling FALLS as
    # detection rises, the call is tracking how deeply a cell was sequenced and not how it was
    # cycling - and a headline reporting a proliferation-shaped percentage on top of that is a
    # claim this plugin's own panel refutes. The panel was drawn and the headline never heard
    # of it.
    if _depth_rho is not None and _depth_rho < 0:
        ctx.contradiction(
            f"THE PHASE CALL TRACKS SEQUENCING DEPTH, NOT CYCLING: the fraction called S or "
            f"G2M FALLS as detection rises (Spearman {_depth_rho:+.2f} over the depth bins), "
            f"which is the opposite of what a real proliferating fraction does. Read the "
            f"percentage below as a property of detection.")
    ctx.headline = (f"{100 * cycling_fraction:.1f}% of cells score S or G2M "
                    f"(G1 {int(counts.get('G1', 0)):,}, S {int(counts.get('S', 0)):,}, "
                    f"G2M {int(counts.get('G2M', 0)):,})"
                    + (f"; {100 * moved:.1f}% of calls move on a different control draw"
                       if alt else "; stability of the calls not measured"))


def selftest(ctx):
    """Prove the CALL is well-formed against the installed scanpy, before a run is spent.

    Not an import check. The first cohort this plugin ever met died three seconds in on

        score_genes() got multiple values for keyword argument 'ctrl_size'

    because `score_genes_cell_cycle` computes `ctrl_size = min(len(s_genes), len(g2m_genes))`
    itself and then forwards `**kwargs`. Nothing about the signature says so; six lines of its
    source do, and only running the real call finds it.

    It asserts SHAPES, COLUMNS, FINITENESS and THE PHASE RULE, never a biological answer: the
    fixture is synthetic and a selftest asserting a phase would be testing its own fixture. The
    rule is asserted because it is not documented anywhere the plugin can read at run time, every
    caveat this plugin writes about G1 being a residual bucket depends on it, and a version that
    changed it would change every cycling fraction this plugin has ever reported without failing.
    """
    import numpy as np
    import scanpy as sc

    ctx.log(f"  scanpy      {sc.__version__}")
    # WHICH KEYWORDS THIS INSTALL ACTUALLY TAKES, recorded rather than assumed. `ctrl_as_ref`
    # exists in the declared scanpy and is documented to flip its default in 2.0; `layer` does
    # not exist in it and is the keyword that raised on a live cohort.
    has_ref = _accepts(sc.tl.score_genes, "ctrl_as_ref")
    ctx.log(f"  score_genes accepts ctrl_as_ref={has_ref}, "
            f"layer={_accepts(sc.tl.score_genes, 'layer')}")

    n = 300
    # The panels plus filler, so binning has something to bin against. `ctx.fixture` gives the
    # genes a spread of means because score_genes bins on expression and a flat matrix collapses
    # every bin.
    genes = list(S_GENES) + list(G2M_GENES) + [f"FILLER{i}" for i in range(400)]
    A = ctx.fixture(n_cells=n, genes=genes)

    extra = {"ctrl_as_ref": CTRL_AS_REF} if has_ref else {}
    counts_X = A.X.copy()
    for source in ("X", "lognorm"):
        # EXACTLY the call `run` makes, both ways it can make it - INCLUDING the assignment,
        # because `layer=` is what the pinned scanpy refuses and a selftest that called the
        # function differently from the plugin would have proved something about the selftest.
        A.X = counts_X if source == "X" else A.layers["lognorm"]
        S, G, ph = _score_once(sc, A, list(S_GENES), list(G2M_GENES),
                               n_bins=N_BINS, seed=SEED, extra=extra)
        for col in ("S_score", "G2M_score", "phase"):
            assert col in A.obs, f"{source}: scanpy did not write obs[{col!r}]"
        for name, v in (("S_score", S), ("G2M_score", G)):
            assert v.shape == (n,), f"{name} is {v.shape}, expected ({n},)"
            assert np.isfinite(v).all(), f"{name} contains non-finite values"
        assert set(ph) <= set(PHASES), f"unexpected phase labels {set(ph) - set(PHASES)}"
        # THE RULE ITSELF: G1 only where BOTH scores are negative, and never anywhere else. Every
        # sentence this plugin writes about G1 being a residual bucket rests on it.
        both_neg = (S < 0) & (G < 0)
        assert (ph[both_neg] == "G1").all(), (
            "a cell with two negative scores was not called G1 - the phase rule has changed")
        assert (ph[~both_neg] != "G1").all(), (
            "a cell with a positive score was called G1 - the phase rule has changed")
        ctx.log(f"  scored from {'layers[lognorm]' if source == 'lognorm' else 'X'}: "
                f"{dict(A.obs['phase'].astype(str).value_counts())}")

    # THE STABILITY PATH IS PART OF THE PLUGIN, so it is part of the proof: re-scoring must run
    # and must return a comparable array. What it must NOT do is assert that the calls agree -
    # on a synthetic fixture with no cell-cycle structure they need not, and an assertion there
    # would be testing the fixture.
    _s2, _g2, ph2 = _score_once(sc, A, list(S_GENES), list(G2M_GENES),
                                n_bins=N_BINS, seed=SEED + 1, extra=extra)
    assert ph2.shape == ph.shape, f"a re-score returned {ph2.shape}, expected {ph.shape}"
    tab = _stability_table(ph, [(SEED + 1, ph2)])
    assert set(PHASES) <= set(tab.columns), (
        f"the stability table has columns {list(tab.columns)}, expected one per phase")
    assert int(tab["n_cells"].sum()) == n, (
        f"the stability table covers {int(tab['n_cells'].sum())} cells, expected {n}")
    ctx.log(f"  re-scored at random_state={SEED + 1}: "
            f"{100 * float((ph2 != ph).mean()):.1f}% of calls moved on the fixture")

    # The detection helpers run on both matrix shapes the host can hand over. A dense fixture
    # exercises the chunked path; the sparse branch is the one a real object takes.
    det = _panel_detection(A, _match(S_GENES, A.var_names), _match(G2M_GENES, A.var_names))
    assert len(det) == len(S_GENES) + len(G2M_GENES), (
        f"panel detection covered {len(det)} genes, expected "
        f"{len(S_GENES) + len(G2M_GENES)}")
    assert det["detection_rate"].between(0, 1).all(), "a detection rate outside [0, 1]"
    per_cell = _detected_per_cell(A.X, chunk=64)
    assert per_cell.shape == (n,), f"detection is {per_cell.shape}, expected ({n},)"
    assert int(per_cell.max()) <= A.n_vars, "more genes detected than the object has"
    ctx.log(f"  detection: {len(det)} panel genes, median "
            f"{float(np.median(per_cell)):.0f} genes per cell over {A.n_vars} genes")

    # The panel is HUMAN symbols and a mouse object is indexed by mouse ones. `_match` is what
    # bridges them, and if it ever stops matching, the plugin scores on a handful of genes and
    # returns a low score rather than refusing - which reads as "not cycling" and is not.
    mouse_names = [g.capitalize() for g in genes]
    got = _match(list(S_GENES), mouse_names)
    assert len(got) == len(S_GENES), (
        f"_match found {len(got)} of {len(S_GENES)} S genes against title-cased names")
    assert "Mcm5" in got, f"expected the mouse casing, got e.g. {got[:3]}"
    ctx.log(f"  _match: {len(got)}/{len(S_GENES)} S genes across casings, e.g. {got[:3]}")
