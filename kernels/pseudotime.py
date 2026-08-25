"""Ordering along a trajectory, with fate probabilities toward each terminal state.

AN ORDERING IS NOT A TIME. CellRank returns a position along a manifold, and the manifold is
whatever the embedding says it is. Which KERNEL produced the ordering decides the answer — a
velocity kernel and a connectivity kernel can order the same cells in opposite directions — so
the kernel used is recorded in the result rather than left to be inferred.

WHAT THE PAGE HAS TO SHOW, AND WHY IT IS MOSTLY DIAGNOSTIC

Every number this plugin emits is downstream of two decisions that CellRank makes quietly and
that no reader can see from a fate map: HOW MANY macrostates the Markov chain was coarse-grained
into, and WHICH of those were then called terminal. Both are answerable from the estimator's own
objects — the Schur spectrum for the first, the diagonal of the coarse-grained transition matrix
for the second — and neither appears anywhere in a fate probability. So four of this plugin's six
panels are diagnostics, and they are declared first, because a fate map drawn under a spectrum
with no eigengap is a picture of a decision rather than a measurement.
"""

PLUGIN = {
    "api": 1,
    "version": "0.2.0",
    "summary": "ordering along a trajectory, oriented by velocity where it exists",
    "when_to_use": "you have a continuum you believe is a progression and want cells ordered "
                   "along it",
    "wraps": {"tool": "cellrank", "homepage": "https://cellrank.readthedocs.io",
              "license": "BSD-3-Clause",
              "cite": "Lange et al., Nat Methods 2022 (CellRank); "
                      "Weiler et al., Nat Methods 2024 (CellRank 2)"},
    "upstream": {
        "docs": "https://cellrank.readthedocs.io",
        # Read against the CellRank 2 sources themselves, not only the rendered docs: the API page
        # for `predict_terminal_states` on readthedocs/latest gives `method='top_n'`, and
        # `estimators/terminal_states/_gpcca.py` gives `TermStatesMethod.STABILITY`. The parameter
        # that decides which macrostates become terminal was documented two different ways, so the
        # source is what this plugin was written against and what the defaults below quote.
        "read": "2026-08-25",
        "defaults_changed": [
            "The kernel is CHOSEN, not defaulted: a VelocityKernel where a velocity field exists, "
            "a ConnectivityKernel otherwise, and the choice is in the result. Two kernels can "
            "order the same cells in opposite directions.",
            "n_states is config rather than automatic. GPCCA's automatic choice is a heuristic "
            "over the eigengap and silently decides how many terminal states the biology has.",
            "terminal_state_method and stability_threshold are DECLARED, not inherited. "
            "`predict_terminal_states()` defaults to method='stability' with "
            "stability_threshold=0.96 - the same 0.96 the CellRank paper states - and that one "
            "number decides which macrostates the fate probabilities are probabilities OF. Taken "
            "silently, the report could not say what had selected them.",
            "n_cells_per_state is declared at CellRank's own 30. It is the size of the anchor set "
            "that DEFINES each macrostate and each terminal state, so it is the denominator "
            "behind every fate probability; on a large cohort 30 cells is a very small anchor and "
            "a reader should be able to see the number rather than assume it.",
            "The velocity kernel is offered when the layers CellRank actually reads are present - "
            "its own `xkey='Ms'` and `vkey='velocity'` - rather than when a velocity GRAPH is in "
            "`uns`. Those are different objects: the graph is scVelo's, and an object carrying it "
            "without the moments layer sent VelocityKernel to a KeyError.",
        ],
        "not_used": [
            "CytoTRACEKernel and PseudotimeKernel-from-a-prior: both need an input this plugin is "
            "not given, and inventing one would fabricate the ordering it is meant to measure.",
            "Driver-gene ranking: it is a second question and belongs in its own plugin.",
            "`Lineage.priming_degree()`. It is CellRank's own commitment score and it is MIN-MAX "
            "NORMALISED to [0, 1] over the cells present, so a dataset in which every cell is "
            "evenly split still returns a score spanning the full range. This plugin reports the "
            "raw Shannon entropy of the fate probabilities in bits instead, against the log2(k) "
            "ceiling that means no fate information at all - an absolute scale a reader can judge "
            "without knowing anything about the rest of the dataset.",
            "model='stochastic' and model='monte_carlo' on the VelocityKernel. Propagating "
            "velocity uncertainty does make fate probabilities more robust (CellRank, Nat Methods "
            "2022), but both are deprecated in CellRank 2 and removed in 3.0, so wiring a "
            "parameter here that disappears at the next major version would be a config key with "
            "a shelf life.",
        ],
        "gotchas": [
            "Without petsc4py/slepc4py, GPCCA falls back to a DENSE eigensolver. It is correct "
            "and on a cohort of any size not finishable - a fallback that is right and takes a "
            "week is not a fallback, so the selftest reports which route it got.",
            "Fate probabilities sum to one by construction, so a cell with no clear fate is "
            "reported as evenly split rather than as unknown.",
            "SILENT: the requested number of macrostates can be INCREMENTED. `_validate_n_states` "
            "raises n_states by one, on a log line only, when the requested number would split a "
            "block of complex conjugate eigenvalues - and `compute_schur` does the same to "
            "n_components. Ask for 3 and the result can legitimately be 4 terminal states, with "
            "nothing in the object saying so. This plugin compares requested against realised and "
            "says so where they differ.",
            "SILENT: genes whose velocity is NaN are DROPPED FROM THE FIT with no message. "
            "VelocityKernel._read_from_adata computes `np.isnan(np.sum(vdata, axis=0))` and "
            "subsets both matrices to the survivors, and separately takes `var['velocity_genes']` "
            "as its gene subset when that column exists. So the number of genes actually behind "
            "the transition matrix is decided by a var column and a NaN test the caller never "
            "sees; this plugin counts both and reports them.",
            "SILENT: a DISCONNECTED neighbour graph makes the chain reducible, and GPCCA then "
            "returns the graph's components as macrostates. The fate probabilities are real "
            "numbers that mean 'which component is this cell in', and they draw exactly like a "
            "fate map. CellRank warns about reducibility only when the coarse-grained stationary "
            "distribution fails; this plugin counts components before the fit.",
            "One macrostate is a legal outcome and a vacuous one. `predict_terminal_states` logs "
            "'Found only one macrostate, making it the singular terminal state', after which "
            "every cell's fate probability is 1.0 and any ordering derived from them is constant. "
            "This plugin refuses the ordering rather than emitting a constant column that "
            "satisfies the `ordering` capability.",
            "method='stability' RAISES when no macrostate reaches the threshold. That is the "
            "right behaviour and it is not a bug in the data: it means this chain has no state "
            "stable enough to absorb into. Caught here and reported as a refusal, with the "
            "spectrum and stability panels already drawn so a reader can see why.",
        ],
    },

    # `embedding` IS THE REPRESENTATION and is required: the kernels are built on a neighbour
    # graph and `sc.pp.neighbors(use_rep=...)` needs a space where distances mean something.
    # `layout` is optional and is only for drawing - two columns, and never the first two of the
    # representation, whose axes carry no ordering.
    "inject": {"required": ["embedding"], "optional": ["velocity", "label", "layout"]},
    "provides": ["ordering"],
    "produces": ["obs[pseudotime]", "obsm[fate_probabilities]",
                 "tables/terminal_states.csv",
                 "tables/macrostate_transitions.csv"],

    "config": {
        "n_states": {"type": "int", "default": 3, "min": 2, "max": 20,
                     "help": "how many macrostates GPCCA looks for. This decides how many "
                             "terminal states the result claims, so it is declared, not guessed"},
        "n_neighbors": {"type": "int", "default": 15, "min": 2,
                        "help": "neighbours for the transition matrix, if one must be built"},
        "velocity_weight": {"type": "float", "default": 0.8, "min": 0.0, "max": 1.0,
                            "help": "weight on the velocity kernel when a velocity field exists; "
                                    "the remainder goes to connectivity"},
        # CELLRANK'S OWN DEFAULTS, DECLARED RATHER THAN INHERITED - the same move decoupler's
        # `min_n` needed. `predict_terminal_states()` was being called bare, so the single number
        # that decides which macrostates the fate probabilities are probabilities OF never
        # appeared anywhere a reader could see it.
        "terminal_state_method": {"type": "str", "default": "stability",
                                  "help": "how macrostates become terminal states. CellRank's own "
                                          "default is 'stability'; 'top_n' takes the n_states "
                                          "most stable, 'eigengap' and 'eigengap_coarse' let a "
                                          "heuristic decide the count. An unrecognised value is "
                                          "refused by CellRank itself, which names the four"},
        "stability_threshold": {"type": "float", "default": 0.96, "min": 0.0, "max": 1.0,
                                "help": "a macrostate is terminal when its self-transition "
                                        "probability - the diagonal of the coarse-grained matrix "
                                        "- reaches this. CellRank's own default and the CellRank "
                                        "paper's stated criterion are both 0.96. Only used when "
                                        "terminal_state_method is 'stability'"},
        "n_cells_per_state": {"type": "int", "default": 30, "min": 1,
                              "help": "cells anchoring each macrostate and each terminal state. "
                                      "CellRank's own default is 30; it is the set the fate "
                                      "probabilities are absorbed INTO, so it is a denominator "
                                      "and not a display setting"},
    },

    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {"cellrank": ">=2.0,<3", "scanpy": ">=1.10,<1.11",
                     "anndata": ">=0.10,<0.12", "numpy": ">=1.24,<2", "pandas": ">=2.0,<3"},
        # {name: match-spec}, VERBATIM. conda's `=3.20` means 3.20.* where pip's `==3.20`
        # means a version that does not exist, so these are never translated.
        "conda": {"petsc4py": "3.20", "slepc4py": "3.20"},
    },

    "cost": "high", "cores": 8,

    # Measured, not estimated: fitted from this plugin's own instances in one run on a 10-sample mouse single-nucleus cohort (~99k cells). ONE dataset on ONE machine - a starting point that is right for scheduling, not a universal constant. Every run re-fits and prints its own.
    # Fitted from one instance; the split is indeterminate.
    "memory_gb_per_100k": 7.3,

    # ---- the page -----------------------------------------------------------------------------
    #
    # DIAGNOSTICS FIRST, AND HERE THEY ARE MOST OF THE PAGE. The two results below are both
    # pictures of the same fate probabilities; the four above them are the only place a reader can
    # see the decisions those probabilities rest on. Read in order they answer: does the data
    # support this many states, are the states stable, are they made of anything recognisable, and
    # does any individual cell actually have a fate.
    "report": {
        "figures": [
            # BOTH OPTIONAL, AND BOTH USED TO BE `required: True` WHILE THE CODE BELOW HAD A
            # BRANCH THAT DOES NOT DRAW THEM. A panel a plugin declines to draw, writes a caveat
            # about, and still declares required is reported by `figure_drift` as a defect and
            # rendered as NOT PRODUCED - which tells a reader the run is incomplete when the run
            # handled it. `required` is about whether an absence is a defect or a property of the
            # data, and an estimator with no spectrum is the second thing.
            {"id": "F1_spectrum", "shows": "diagnostic", "required": False,
             "question": "does the data support the number of states this run asked for?",
             "source": "figures/F1_spectrum.csv",
             "when_absent": "the estimator came back with no eigendecomposition, so there is NO "
                            "evidence on this page about whether the data supports the number of "
                            "states that was asked for. Read every count below as a parameter of "
                            "the run rather than as a reading of the data."},
            {"id": "F2_macrostate_stability", "shows": "diagnostic", "required": False,
             "question": "are the states called terminal actually stable, or did a threshold "
                         "decide?",
             "source": "tables/macrostate_transitions.csv",
             "when_absent": "GPCCA returned no coarse-grained transition matrix, so the stability "
                            "of each state - the one measurement behind the terminal-state call - "
                            "is not on this page and cannot be checked. The terminal states named "
                            "in the tables are then a parameter with no evidence beside them."},
            # OPTIONAL, AND THE ABSENCE IS THE FINDING. A macrostate's NAME is the dominant
            # annotation among its anchor cells; with no annotation there is no name and no
            # composition, and the states come back as GPCCA's own indices.
            {"id": "F3_macrostate_composition", "shows": "diagnostic", "required": False,
             "question": "what are these states made of - one population, or several?",
             "source": "figures/F3_macrostate_composition.csv",
             # TWO CAUSES, BOTH NAMED. The sentence used to give only the first, so a run whose
             # estimator assigned no cell to a macrostate printed "the object carries no
             # cell-type annotation" on an object that carried one. An absence sentence that
             # names one of two possible reasons is wrong half the time it is read; the caveats
             # say which of the two happened.
             "when_absent": "either the object carries no cell-type annotation - so the "
                            "macrostates have no names beyond GPCCA's own indices and there is "
                            "nothing to compose them from - or no cell was assigned to a "
                            "macrostate. The caveats say which. Every state in the tables below "
                            "is then a number, and which cells it holds can only be read off the "
                            "fate map."},
            {"id": "F4_fate_certainty", "shows": "diagnostic", "required": True,
             "question": "does any cell actually have a fate, or are the probabilities evenly "
                         "split?",
             "source": "figures/F4_fate_certainty.csv"},
            {"id": "F5_fate_map", "shows": "result", "required": False,
             "question": "where on the map does each fate come from?",
             "source": "figures/F5_fate_map.csv",
             "when_absent": "the object carries no two-column layout, and the representation the "
                            "chain was built on must not be drawn on - its axes carry no "
                            "ordering, so its first two columns are two arbitrary coordinates. "
                            "The fate probabilities themselves are unaffected and are in "
                            "`obsm[fate_probabilities]`; computing a UMAP or similar on that "
                            "representation makes this panel drawable."},
            {"id": "F6_ordering_by_population", "shows": "result", "required": False,
             "question": "which populations sit early on this ordering and which sit late?",
             "source": "figures/F6_ordering_by_population.csv",
             "when_absent": "either the object carries no cell-type annotation, or no population "
                            "was left with a cell once annotator sentinels were set aside - so "
                            "the ordering cannot be summarised per population. The caveats say "
                            "which. The per-cell ordering is unaffected and is in "
                            "`obs[pseudotime]`."},
        ],
        # THE PAIRING, and the reciprocal of the one velocity already declares. Velocity measures
        # direction from the chemistry and this measures it from the shape of the manifold, so the
        # two answer the same question from different evidence and DISAGREEMENT between them is
        # informative rather than an error.
        #
        # There is deliberately no `comparison` panel. Drawing the join would mean reading the
        # other plugin's output column by name, and `provides`/`inject` exist precisely so that a
        # plugin needing an ordering does not name the plugin that made one. The reporter can say
        # the halves belong together; neither plugin can draw it alone.
        "reads_with": ["velocity"],
    },

    "cannot_show": [
        "AN ORDERING IS NOT A TIME. It is a position along a manifold, and it says nothing about "
        "how long anything took.",
        "WHICH KERNEL PRODUCED IT DECIDES THE ANSWER. A velocity kernel and a connectivity kernel "
        "can order the same cells in opposite directions; the kernel used is in the result. The "
        "CellRank 2 authors put it as: the proposed kernels lead to different results if the "
        "underlying assumptions are violated or not sufficiently satisfied (Weiler et al., Nat "
        "Methods 2024).",
        "The ordering is only as good as the embedding it runs on. A constrained embedding "
        "constrains the trajectory.",
        "Fate probabilities sum to one, so a cell with no clear fate reads as evenly split "
        "rather than as unknown.",
        "A CONNECTIVITY KERNEL HAS NO DIRECTION. Its transition matrix is symmetric before "
        "density normalisation, so the chain is reversible: what comes back is a set of "
        "metastable regions of the graph and the probability of drifting into each. Calling one "
        "end of that an origin is the reader's assumption, never this plugin's measurement.",
        "THE NUMBER OF TERMINAL STATES IS A PARAMETER, NOT A RESULT. It follows from n_states and "
        "from the stability threshold, both of which are declared in this plugin's config; the "
        "spectrum panel is the only evidence on the page about whether the data supports the "
        "number that was asked for.",
        "A MACROSTATE'S NAME IS NOT ITS CONTENT. Names come from the dominant annotation among "
        "the handful of anchor cells CellRank assigns to each state, so a state named after a "
        "population may be mostly that population or barely a plurality of it. The composition "
        "panel is what distinguishes those two, and the name alone cannot.",
        "Fate probabilities are ABSORPTION probabilities on a graph, not lineage relationships. "
        "Two cells with the same fate probability are equally likely to reach that state under a "
        "random walk on this manifold; nothing here observes a cell becoming anything.",
    ],
}


# ------------------------------------------------------------------------------- drawing helpers

def _clean(ax, key=None):
    """Strip the frame from an embedding panel and name the axis by the layout's own key.

    THE KEY IS PRINTED WHOLE, deliberately. Splitting `umap_something` into an algorithm and what
    it was run on requires knowing which half is which, and a wrong guess invents an algorithm
    that does not exist. The layout key is what the object actually calls this space, so it can be
    looked up; a name derived from it cannot.

    A publication panel names its axes even where the values are meaningless - an unlabelled
    embedding is the commonest reason a reviewer asks what they are looking at.
    """
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    if key:
        ax.set_xlabel(f"{key} 1", loc="left")
        ax.set_ylabel(f"{key} 2", loc="bottom")


def _colours_for(ctx, labels):
    """A colour per population, stable across every panel, with collisions SAID rather than shown.

    Sentinels never arrive here - this plugin fits on `ctx.real_cells()` only - but the palette
    still runs out, and past its end two populations share a hue with a legend showing each twice
    and nothing admitting it.
    """
    F = ctx.figure
    names = sorted(set(map(str, labels)))
    cols = F.palette(names)
    clash = getattr(F, "palette_collisions", None)
    for _colour, labs in (clash(names) if clash else []):
        ctx.caveat(f"{len(labs)} populations share one colour in the panels below "
                   f"({', '.join(labs)}). There are more populations than the palette has hues "
                   f"that stay separable; read those from the tables rather than from the map.")
    return cols


# ------------------------------------------------------------------------------------- the panels
#
# Four diagnostics and two results. Each is guarded: a panel that cannot be drawn on some data
# says so through `when_absent` above and a caveat here, and never through a gap on the page.

def _fig_spectrum(ctx, eig, n_requested):
    """The Schur spectrum, with the eigengap and the requested number of states marked.

    CellRank's own first diagnostic, and the one thing on the page that speaks to whether
    `n_states` was a reading of the data or an imposition on it.
    """
    import numpy as np
    import pandas as pd
    # `np.asarray(None)` IS NOT NONE. It is a 0-d object array whose `.size` is 1, so an
    # eigendecomposition dict that carries `eigengap` and no `D` - or a `D` of None - walked
    # straight past the guard below and crashed in `np.abs(np.imag(D))` three lines later, on the
    # one panel whose whole purpose is to be drawn when something is off. The None test has to
    # happen before the array is built.
    D = eig.get("D") if isinstance(eig, dict) else None
    D = np.asarray(D) if D is not None else None
    if D is None or not D.size:
        ctx.log("    F1_spectrum not drawn: the estimator carries no eigendecomposition")
        ctx.caveat("The Schur decomposition left no eigenvalues, so the spectrum panel could not "
                   "be drawn and there is NO evidence on this page about whether the data "
                   "supports the number of states that was asked for. Read every count below as "
                   "a parameter of the run.")
        return
    F, plt = ctx.figure, ctx.plot()
    rank = np.arange(1, D.size + 1)
    # `re_part` and `im_part`, not `re`/`im`: `re` is a standard-library module name and a local
    # that shadows one is a trap for whoever adds an import to this function later.
    re_part, im_part = np.real(D), np.imag(D)
    is_complex = np.abs(im_part) > 1e-12
    # `eigengap` is an INDEX into D; CellRank's own suggestion is that index plus one. ABSENT IS
    # NOT ZERO: `eig.get("eigengap", 0)` returns None where the key exists carrying None, and
    # defaulting a missing one to 0 draws a line at "1 state" that the estimator never suggested.
    gap = eig.get("eigengap")
    suggested = int(gap) + 1 if gap is not None else None

    df = pd.DataFrame({"rank": rank, "eigenvalue_real": re_part, "eigenvalue_imag": im_part,
                       "complex_pair": is_complex}).set_index("rank")

    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.74))
    ax.axhline(1.0, color=F.GREY, lw=0.6, zorder=0)
    ax.scatter(rank[~is_complex], re_part[~is_complex], s=14, color="#0072B2", linewidths=0,
               label="real", zorder=3)
    if is_complex.any():
        ax.scatter(rank[is_complex], re_part[is_complex], s=14, color="#E69F00", linewidths=0,
                   label="complex pair", zorder=3)
    F.rasterize_points(ax)
    # THE TWO NUMBERS GO IN THE LEGEND, not in an annotation on the data. Which line is which is
    # the entire content of this panel, and a label placed at an axis limit moves when the data
    # does.
    if suggested is not None:
        ax.axvline(suggested + 0.5, color=F.INK, ls="--", lw=0.7,
                   label=f"eigengap suggests {suggested}")
    ax.axvline(n_requested + 0.5, color="#CC79A7", ls=":", lw=0.9,
               label=f"this run asked for {n_requested}")
    ax.set_xlabel("rank")
    ax.set_ylabel("eigenvalue (real part)")
    F.legend_outside(fig, ax)
    gap_says = ("The dashed line is CellRank's own eigengap suggestion; the dotted line is the "
                "number this run asked for. Where they differ, every count below is the dotted "
                "line's, not the data's. " if suggested is not None else
                "The estimator reported NO eigengap, so the only line drawn is the number this "
                "run asked for and there is nothing on this panel to compare it against. ")
    ctx.emit_figure(
        "F1_spectrum", fig,
        caption=("Real part of the leading eigenvalues of the transition matrix. Eigenvalues near "
                 "1 correspond to slowly-decaying, metastable structure, and a GAP in the "
                 "spectrum is the evidence for a particular number of such structures. "
                 + gap_says +
                 "Points marked as a complex pair cannot be split between states - "
                 "asking for a number that would split one silently raises it by one."),
        source=df)


def _fig_stability(ctx, coarse_T, source, terminal, threshold, method):
    """The coarse-grained transition matrix, and its diagonal against the terminal threshold.

    The diagonal IS the stability index: the probability that a macrostate transitions to itself.
    CellRank calls a macrostate terminal at 0.96, and the paper states that number outright, so
    the panel draws the line and lets a reader see how near the call was.

    `source` is the PATH of the table this plugin already emitted, not the frame. Handing
    `emit_figure` a frame would write the same matrix a second time under the figure's own name,
    and the declaration - which points a reader at `tables/macrostate_transitions.csv` - would
    then name a file this panel had not been drawn from.
    """
    import numpy as np
    import pandas as pd
    if coarse_T is None or not len(coarse_T):
        ctx.log("    F2_macrostate_stability not drawn: no coarse-grained matrix")
        ctx.caveat("GPCCA returned no coarse-grained transition matrix, so the stability of each "
                   "state - the one measurement behind the terminal-state call - is not on this "
                   "page and cannot be checked.")
        return
    F, plt = ctx.figure, ctx.plot()
    names = [str(x) for x in coarse_T.index]
    M = np.asarray(coarse_T, dtype=float)
    stab = pd.Series(np.diag(M), index=names).sort_values()
    term = {str(t) for t in (terminal or [])}

    fig, axs = plt.subplots(1, 2, figsize=(F.DOUBLE, max(1.9, 0.24 * len(names) + 1.2)),
                            squeeze=False, layout="constrained")
    ax = axs[0][0]
    im = ax.imshow(M, cmap="RdYlBu_r", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(names)))
    ax.set_xticklabels(names, rotation=90)
    ax.set_yticks(np.arange(len(names)))
    ax.set_yticklabels(names)
    ax.set_xlabel("to")
    ax.set_ylabel("from")
    ax.set_title("coarse-grained transitions", loc="left")
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    cb.outline.set_visible(False)

    ax2 = axs[0][1]
    y = np.arange(len(stab))
    ax2.barh(y, stab.values, height=0.72,
             color=["#0072B2" if n in term else F.GREY for n in stab.index])
    ax2.set_yticks(y)
    ax2.set_yticklabels(stab.index)
    ax2.set_xlim(0, 1)
    ax2.set_xlabel("stability (self-transition probability)")
    # THIS PANEL IS ALSO DRAWN ON THE REFUSAL PATH, where `terminal` is empty - and "terminal in
    # blue" over a chart with no blue bar in it reads as a rendering fault rather than as the
    # result it is. A title has to be true of the figure under it.
    ax2.set_title("terminal in blue" if term else "no state was called terminal", loc="left")
    if method == "stability":
        ax2.axvline(float(threshold), color=F.INK, ls="--", lw=0.7)
    ax2.spines["left"].set_visible(False)
    ax2.tick_params(axis="y", length=0)

    if term:
        thr = (f"The dashed line is the {threshold} threshold that selected them. "
               if method == "stability" else
               f"Terminal states were selected by method={method!r}, so the threshold is not what "
               f"decided them and no line is drawn. ")
    else:
        # NOTHING WAS SELECTED, so a caption saying a threshold "selected them" describes a
        # selection that did not happen. This is the panel the refusal points a reader at.
        thr = (f"NO macrostate was called terminal here: the dashed line is the {threshold} "
               f"threshold and no bar reaches it. "
               if method == "stability" else
               f"NO macrostate was called terminal here, under method={method!r}. ")
    ctx.emit_figure(
        "F2_macrostate_stability", fig,
        caption=("Left: transition probabilities between macrostates, the whole Markov chain "
                 "coarse-grained onto the states GPCCA found. Right: the diagonal of that matrix, "
                 "which is each state's probability of transitioning to itself and is what "
                 "CellRank means by stability. A terminal state is one a random walk does not "
                 "leave. " + thr
                 + ("A state just under the line and a state just over it are nearly the same "
                    "measurement, and only one of them is in the result." if term else
                    "Nothing downstream of this panel exists: with no state to absorb into there "
                    "are no fate probabilities and no ordering.")),
        source=source)


def _fig_composition(ctx, macrostates, groups, colours):
    """What each macrostate is made of, in populations - because its NAME is only its plurality."""
    import numpy as np
    import pandas as pd
    if groups is None:
        return                      # run() writes the caveat; F3's `when_absent` is that sentence
    if macrostates is None:
        # A SECOND WAY TO BE ABSENT, WHICH USED TO RETURN IN SILENCE. The page then printed F3's
        # `when_absent` - "the object carries no cell-type annotation" - on an object that plainly
        # carried one, which is worse than a gap because it reads as a finding.
        ctx.log("    F3_macrostate_composition not drawn: the estimator returned no macrostate "
                "assignment")
        ctx.caveat("The estimator returned no macrostate assignment, so what the states are made "
                   "of is not on this page. Their names in the tables are still the dominant "
                   "annotation among their anchor cells, and there is nothing here to check that "
                   "against.")
        return
    assign = np.asarray(pd.Series(macrostates).astype(str))
    lab = np.asarray(groups, dtype=object).astype(str)
    keep = ~pd.isna(pd.Series(macrostates)).values
    if not keep.any():
        ctx.log("    F3_macrostate_composition not drawn: no cell was assigned to a macrostate")
        ctx.caveat("No cell was assigned to a macrostate, so what the states are made of is not "
                   "on this page. Their names in the tables are still the dominant annotation "
                   "among their anchor cells, and there is nothing here to check that against.")
        return
    tab = pd.crosstab(pd.Series(assign[keep], name="macrostate"),
                      pd.Series(lab[keep], name="population"))
    frac = tab.div(tab.sum(axis=1), axis=0)
    # Most mixed first: a state that is 40% its own name is the one worth looking at.
    frac = frac.loc[frac.max(axis=1).sort_values().index]

    F, plt = ctx.figure, ctx.plot()
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.7, 0.24 * len(frac) + 1.0)))
    y = np.arange(len(frac))
    left = np.zeros(len(frac))
    for pop in frac.columns:
        v = frac[pop].values
        ax.barh(y, v, left=left, height=0.72, color=(colours or {}).get(str(pop), F.GREY),
                label=str(pop))
        left = left + v
    ax.set_yticks(y)
    ax.set_yticklabels(frac.index)
    # WITHOUT THIS, ROW 0 IS AT THE BOTTOM. `frac` is sorted ascending on its largest fraction, so
    # the most mixed state is row 0 - and matplotlib's y axis grows upward, which put it at the
    # foot of a panel whose caption says "most mixed at the top". The sort, the comment above it
    # and the caption all agreed with each other and disagreed with the picture.
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("fraction of the state's anchor cells")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    F.legend_outside(fig, ax, ncol=1 if len(frac.columns) <= 14 else 2)
    ctx.emit_figure(
        "F3_macrostate_composition", fig,
        caption=("Population composition of the cells anchoring each macrostate, most mixed at "
                 "the top. A macrostate is NAMED after whichever population is commonest among "
                 "these cells, and nothing in that name says whether it was a majority or a bare "
                 "plurality - a state that is 40% of its own namesake carries that name exactly "
                 "as confidently as one that is 98%. Counts are of anchor cells only, not of the "
                 "whole population."),
        source=tab)


def _fig_certainty(ctx, barcodes, fate, names, groups, colours):
    """How much fate information any individual cell carries, against the ceiling of none at all.

    Entropy in BITS, not CellRank's normalised priming degree: the normalised score is min-max
    scaled over the cells present, so it spans [0, 1] whether or not the fate probabilities carry
    anything. log2(k) is the entropy of an even split and is an absolute ceiling.
    """
    import numpy as np
    import pandas as pd
    k = fate.shape[1]
    ceiling = float(np.log2(k)) if k > 1 else 0.0
    safe = np.where(fate > 0, fate, 1.0)
    ent = -(np.where(fate > 0, fate, 0.0) * np.log2(safe)).sum(axis=1)
    top = fate.max(axis=1)
    d = {"barcode": np.asarray(barcodes, dtype=object).astype(str),
         "fate_entropy_bits": ent, "max_fate_probability": top}
    if groups is not None:
        d["label"] = np.asarray(groups, dtype=object).astype(str)
    src = pd.DataFrame(d).set_index("barcode")

    F, plt = ctx.figure, ctx.plot()
    ncol = 1 if groups is None else 2
    fig, axs = plt.subplots(1, ncol, figsize=(F.DOUBLE if ncol == 2 else F.SINGLE,
                                              F.SINGLE * 0.85), squeeze=False,
                            layout="constrained")
    ax = axs[0][0]
    ax.hist(ent, bins=60, color="#0072B2", linewidth=0)
    if ceiling > 0:
        ax.axvline(ceiling, color=F.INK, ls="--", lw=0.7)
    ax.set_xlabel("fate entropy (bits)")
    ax.set_ylabel("cells")
    # `names` WAS ACCEPTED AND NEVER READ. The log2(k) ceiling this panel draws is only
    # interpretable if a reader knows WHICH k states an even split is even across, and they are
    # right here in the argument list.
    shown = ", ".join(str(n) for n in (names or [])[:4])
    if names is not None and len(names) > 4:
        shown += f", +{len(names) - 4} more"
    ax.set_title(f"{k} terminal state(s)" + (f": {shown}" if shown else ""), loc="left")

    if groups is not None:
        g = np.asarray(groups, dtype=object).astype(str)
        order = sorted(set(g.tolist()))
        ax2 = axs[0][1]
        bp = ax2.boxplot([ent[g == l] for l in order], vert=False, widths=0.62,
                         patch_artist=True, showfliers=False,
                         medianprops=dict(color=F.INK, lw=0.8))
        for patch, l in zip(bp["boxes"], order):
            patch.set_facecolor((colours or {}).get(l, F.GREY))
            patch.set_edgecolor(F.INK)
            patch.set_linewidth(0.5)
        ax2.set_yticklabels(order)
        ax2.invert_yaxis()
        ax2.set_xlabel("fate entropy (bits)")
        if ceiling > 0:
            ax2.axvline(ceiling, color=F.INK, ls="--", lw=0.7)
        ax2.set_title("per population", loc="left")
    ctx.emit_figure(
        "F4_fate_certainty", fig,
        caption=(f"Shannon entropy of each cell's fate probabilities, in bits. Zero means the "
                 f"cell is committed to one terminal state; the dashed line at log2(k) = "
                 f"{ceiling:.2f} is an EVEN SPLIT across all {k} of them, which is the value a "
                 f"cell gets when the method has no information about it. Because the "
                 f"probabilities are constrained to sum to one, that case is reported as a "
                 f"confident-looking row of numbers rather than as missing, and this panel is the "
                 f"only place on the page it is visible. A distribution piled against the line is "
                 f"a fate map that will still draw."),
        source=src)


def _fig_fate_map(ctx, barcodes, xy, key, fate, names, order):
    """Each fate on the layout, and the ordering beside them."""
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()
    show = list(range(min(fate.shape[1], 6)))
    d = {"barcode": np.asarray(barcodes, dtype=object).astype(str),
         "x": xy[:, 0], "y": xy[:, 1], "ordering": order}
    for j, nm in enumerate(names):
        d[f"fate_{nm}"] = fate[:, j]
    src = pd.DataFrame(d).set_index("barcode")

    n_panels = len(show) + 1
    ncol = min(3, n_panels)
    nrow = (n_panels + ncol - 1) // ncol
    fig, axs = plt.subplots(nrow, ncol, figsize=(F.DOUBLE, 1.85 * nrow), squeeze=False,
                            layout="constrained")
    flat = axs.ravel()
    for i, j in enumerate(show):
        ax = flat[i]
        v = fate[:, j]
        o = np.argsort(v)
        pts = ax.scatter(xy[o, 0], xy[o, 1], c=v[o], s=1.5, cmap="viridis", vmin=0, vmax=1,
                         linewidths=0, rasterized=True)
        _clean(ax, key)
        ax.set_title(str(names[j]), loc="left")
        cb = fig.colorbar(pts, ax=ax, fraction=0.045, pad=0.02)
        cb.outline.set_visible(False)
    ax = flat[len(show)]
    o = np.argsort(order)
    pts = ax.scatter(xy[o, 0], xy[o, 1], c=order[o], s=1.5, cmap="magma", linewidths=0,
                     rasterized=True)
    _clean(ax, key)
    ax.set_title("ordering", loc="left")
    cb = fig.colorbar(pts, ax=ax, fraction=0.045, pad=0.02)
    cb.outline.set_visible(False)
    for ax in flat[n_panels:]:
        ax.set_visible(False)

    more = ("" if len(show) == fate.shape[1] else
            f" {fate.shape[1] - len(show)} further terminal state(s) are in the source table and "
            f"not drawn.")
    ctx.emit_figure(
        "F5_fate_map", fig,
        caption=(f"Probability of reaching each terminal state, one panel per state, on the "
                 f"object's own two-column layout. The last panel is the ordering: one minus each "
                 f"cell's largest fate probability, so a committed cell is low and an uncommitted "
                 f"one is high. It is an ORDER along this manifold and not elapsed time, and its "
                 f"direction is a property of the kernel that produced it.{more} Read beside the "
                 f"entropy panel: a cell can be mid-scale on every fate here simply because the "
                 f"probabilities had to sum to one."),
        source=src)


def _fig_ordering_by_population(ctx, order, groups, colours):
    """The ordering per population - the form of the result most readers will quote."""
    import numpy as np
    import pandas as pd
    g = np.asarray(groups, dtype=object).astype(str)
    rows = []
    for l in sorted(set(g.tolist())):
        v = order[g == l]
        if not v.size:
            continue
        rows.append({"population": l, "n_cells": int(v.size),
                     "ordering_q25": float(np.percentile(v, 25)),
                     "ordering_median": float(np.median(v)),
                     "ordering_q75": float(np.percentile(v, 75))})
    if not rows:
        # SILENT UNTIL NOW, and F6's `when_absent` would have blamed a missing annotation for it.
        ctx.log("    F6_ordering_by_population not drawn: no population had a cell with an "
                "ordering")
        ctx.caveat("No population was left with a cell once annotator sentinels were set aside, "
                   "so the ordering could not be summarised per population. The per-cell "
                   "ordering is unaffected and is in `obs[pseudotime]`.")
        return
    df = pd.DataFrame(rows).sort_values("ordering_median").set_index("population")

    F, plt = ctx.figure, ctx.plot()
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.7, 0.22 * len(df) + 0.9)))
    y = np.arange(len(df))
    bp = ax.boxplot([order[g == l] for l in df.index], vert=False, widths=0.62,
                    patch_artist=True, showfliers=False,
                    medianprops=dict(color=F.INK, lw=0.8))
    for patch, l in zip(bp["boxes"], df.index):
        patch.set_facecolor((colours or {}).get(str(l), F.GREY))
        patch.set_edgecolor(F.INK)
        patch.set_linewidth(0.5)
    ax.set_yticks(y + 1)
    ax.set_yticklabels(df.index)
    ax.invert_yaxis()
    ax.set_xlabel("ordering (1 - largest fate probability)")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ctx.emit_figure(
        "F6_ordering_by_population", fig,
        # THE AXIS IS INVERTED, SO THE TOP IS THE LOWEST MEDIAN. This said "a population at the
        # bottom is near a terminal state", which is the opposite of what the panel draws: `df` is
        # sorted ascending on the median and `invert_yaxis()` puts the smallest at the top, so the
        # bottom row is the LEAST committed population. A caption that reverses a figure's reading
        # is worse than none - the figure cannot correct it, and a reader has no reason to doubt.
        caption=("The ordering within each population, lowest median first - and the axis is "
                 "inverted, so the lowest sits at the TOP. Low means committed to one terminal "
                 "state and high means uncommitted between several, so this reads as a commitment "
                 "axis rather than as a clock; the population at the top is the one nearest a "
                 "terminal state on this manifold, which does not make it older. Populations, not "
                 "clusters: annotator sentinels are excluded from the grouping and the count is "
                 "in the caveats. Boxes are quartiles, whiskers 1.5 IQR, outliers not drawn."),
        source=df)


# ---------------------------------------------------------------------------------------- the run

def run(ctx):
    import numpy as np
    import pandas as pd
    import cellrank as cr
    import scanpy as sc

    real = np.asarray(ctx.real_cells())
    A = ctx.adata[real].copy()
    p = ctx.populations()
    groups = p.groups                       # aligned to A: p.mask IS real_cells()
    colours = _colours_for(ctx, groups) if groups is not None else {}

    # SET ASIDE FROM THE FIT, NOT ONLY FROM THE GROUPING - and the host's own sentinel caveat says
    # the opposite ("they stay in the object and in any per-cell result; only the grouping excludes
    # them"), because for most plugins that is true. It is not true here: the chain is built on the
    # subset, so a sentinel has no fate probability and no ordering to keep. Said in this plugin's
    # own words, with the count, beside the host's.
    n_aside = int((~real).sum())
    if n_aside:
        ctx.caveat(
            f"{n_aside:,} cells carrying an annotator sentinel were set aside BEFORE the "
            f"transition matrix was built, not merely out of the grouping: the neighbour graph, "
            f"the macrostates and every fate probability are computed on the remaining "
            f"{int(real.sum()):,}. Those cells keep their row in the object and are NaN - not "
            f"zero - in `obs[pseudotime]` and `obsm[fate_probabilities]`, so nothing here orders "
            f"a cell the annotator declined to type. A sentinel rate that differs across the "
            f"design makes this a differential exclusion; it is not measured here.")

    emb = ctx.keys["embedding"]
    # BUILT HERE, ALWAYS, ON THE DECLARED REPRESENTATION. This was `if "neighbors" not in A.uns`,
    # which is wrong twice over. `A` is `ctx.adata[real]`, so an inherited graph has been SLICED:
    # every edge to a set-aside cell is gone and the survivors hold fewer neighbours than they
    # were built with, which is not the kNN graph of these cells and can be disconnected for a
    # purely technical reason - which the component count below would then report as though it
    # were a property of the data. And on any object that already carried a graph, `embedding` -
    # a REQUIRED capability, declared because the chain has to be built where distances mean
    # something - decided nothing at all, and nothing on the page said which space the ordering
    # had actually come from.
    inherited = "neighbors" in A.uns
    sc.pp.neighbors(A, n_neighbors=ctx.config["n_neighbors"], use_rep=emb)
    ctx.log(f"neighbour graph: n_neighbors={ctx.config['n_neighbors']} on {emb}"
            + ("; an existing graph on this object was NOT reused - it had been sliced with the "
               "cells set aside" if inherited else ""))

    # A REDUCIBLE CHAIN RETURNS ITS COMPONENTS AS MACROSTATES, and they draw like a fate map. This
    # is counted before the fit because afterwards it is indistinguishable from biology.
    try:
        from scipy.sparse.csgraph import connected_components
        ncomp, _ = connected_components(A.obsp["connectivities"], directed=False)
        if ncomp > 1:
            ctx.caveat(
                f"The neighbour graph has {ncomp} disconnected components. A Markov chain on a "
                f"disconnected graph is reducible: a random walk cannot cross between components, "
                f"so GPCCA can return the components themselves as macrostates and every fate "
                f"probability then answers 'which component is this cell in'. That result looks "
                f"identical to a trajectory. Check the composition panel before reading any fate.")
        ctx.log(f"neighbour graph: {ncomp} connected component(s)")
    except Exception as e:                                                    # noqa: BLE001
        ctx.log(f"  could not count graph components ({type(e).__name__}: {e})")

    # THE LAYERS CELLRANK ACTUALLY READS, which are its own `xkey`/`vkey` defaults - not scVelo's
    # velocity GRAPH in `uns`. An object with the graph and no moments layer sent VelocityKernel
    # to a KeyError, which is a crash whose cause names neither.
    has_velocity = "velocity" in A.layers and "Ms" in A.layers
    if has_velocity:
        w = ctx.config["velocity_weight"]
        vk = cr.kernels.VelocityKernel(A)
        vk.compute_transition_matrix()
        _report_velocity_genes(ctx, A, vk)
        kern = (w * vk + (1 - w) * cr.kernels.ConnectivityKernel(A).compute_transition_matrix())
        which = f"VelocityKernel({w}) + ConnectivityKernel({1 - w:.2g})"
    else:
        kern = cr.kernels.ConnectivityKernel(A).compute_transition_matrix()
        which = "ConnectivityKernel"
        ctx.caveat("No velocity field was on this object, so the ordering comes from CONNECTIVITY "
                   "alone. A connectivity kernel has no direction of its own: the ordering is a "
                   "position along the manifold and its sign is arbitrary.")
    ctx.log(f"transition matrix from {which}")

    n_req = int(ctx.config["n_states"])
    n_anchor = int(ctx.config["n_cells_per_state"])
    est = cr.estimators.GPCCA(kern)
    est.compute_schur(n_components=max(n_req + 3, 6))

    # THE SPECTRUM IS DRAWN BEFORE THE MACROSTATES, so that a run which cannot get past
    # `predict_terminal_states` still leaves a reader the evidence for why. A refusal with no
    # diagnostics on the page is a refusal nobody can act on.
    _fig_spectrum(ctx, est.eigendecomposition or {}, n_req)

    est.compute_macrostates(n_states=n_req, n_cells=n_anchor,
                            cluster_key=ctx.keys.get("label"))
    got = [str(x) for x in est.macrostates.cat.categories]
    if len(got) != n_req:
        ctx.caveat(f"{n_req} macrostates were requested and {len(got)} were computed. CellRank "
                   f"raises the count by one, on a log line only, when the requested number would "
                   f"split a block of complex conjugate eigenvalues - so this is expected "
                   f"behaviour and not an error, but every count below is {len(got)}'s and not "
                   f"{n_req}'s.")

    coarse = est.coarse_T
    coarse_path = None
    if coarse is not None and len(coarse):
        coarse_path = ctx.emit_table("macrostate_transitions", coarse)

    method = str(ctx.config["terminal_state_method"])
    thr = float(ctx.config["stability_threshold"])
    kw = {"method": method, "n_cells": n_anchor}
    if method == "stability":
        kw["stability_threshold"] = thr
    elif method == "top_n":
        kw["n_states"] = n_req
    try:
        est.predict_terminal_states(**kw)
    except ValueError as e:
        # NOT A CRASH AND NOT A BUG IN THE DATA. With method='stability' CellRank refuses when no
        # macrostate reaches the threshold, which is the statement that this chain has no state
        # stable enough to absorb into. It is a result, so it is recorded as one.
        _fig_stability(ctx, coarse, coarse_path, [], thr, method)
        ctx.refuse("terminal states",
                   f"no macrostate met the terminal criterion (method={method!r}"
                   + (f", stability_threshold={thr}" if method == "stability" else "")
                   + f"): {e}. This chain has no region a random walk does not leave, so there is "
                     f"nothing for fate probabilities to be probabilities of. The spectrum and "
                     f"stability panels show why. Lower stability_threshold, or set "
                     f"terminal_state_method to 'top_n', only if a terminal state is something "
                     f"this data is expected to contain.")
        ctx.headline = f"no terminal state at {method!r} over {A.n_obs:,} cells, from {which}"
        return

    terminal = [str(t) for t in est.terminal_states.cat.categories]
    _fig_stability(ctx, coarse, coarse_path, terminal, thr, method)
    _fig_composition(ctx, est.macrostates, groups, colours)

    est.compute_fate_probabilities()
    fate = np.asarray(est.fate_probabilities)
    names = [str(x) for x in est.fate_probabilities.names] \
        if hasattr(est.fate_probabilities, "names") else \
        [f"state{i}" for i in range(fate.shape[1])]

    if fate.shape[1] < 2:
        # ONE TERMINAL STATE MAKES THE ORDERING A CONSTANT. Emitting it would satisfy the
        # `ordering` capability with a column of zeros, and everything downstream would read it as
        # an ordering. The refusal is the honest form of the same fact.
        _fig_certainty(ctx, A.obs_names, fate, names, groups, colours)
        only = names[0] if names else "<unnamed>"
        ctx.refuse("ordering",
                   f"only one terminal state ({only!r}) survived, so every cell's fate "
                   f"probability is 1.0 by construction and any ordering derived from them is "
                   f"the same number for every cell. The fate probabilities are still emitted; "
                   f"the ordering is not, because a constant column satisfies the `ordering` "
                   f"capability without carrying one.")
        wide = np.full((ctx.adata.n_obs, fate.shape[1]), np.nan, dtype="float32")
        wide[real] = fate
        ctx.emit_obsm("fate_probabilities", wide)
        ctx.headline = f"one terminal state over {A.n_obs:,} cells, from {which}"
        return

    # A pseudotime from the fate structure: how far a cell is from its most likely terminal
    # state, which is an ORDER and is not a duration.
    order = 1.0 - fate.max(axis=1)
    full = np.full(ctx.adata.n_obs, np.nan, dtype="float32")
    full[real] = order
    ctx.emit_obs("pseudotime", full)
    # PADDED TO THE OBJECT THIS PLUGIN WAS GIVEN. `emit_obsm` requires one row per cell of
    # ctx.adata, and this ran on the subset with sentinels excluded - so the excluded rows are
    # NaN, which is "not measured", rather than 0, which is a fate probability.
    wide = np.full((ctx.adata.n_obs, fate.shape[1]), np.nan, dtype="float32")
    wide[real] = fate
    ctx.emit_obsm("fate_probabilities", wide)

    stability = {}
    if coarse is not None and len(coarse):
        stability = dict(zip((str(x) for x in coarse.index),
                             (float(v) for v in np.diag(np.asarray(coarse, dtype=float)))))
    ctx.emit_table("terminal_states", pd.DataFrame(
        {"terminal_state": names,
         "stability_index": [stability.get(n, float("nan")) for n in names],
         "mean_fate_probability": fate.mean(axis=0),
         "cells_most_likely": [int((fate.argmax(axis=1) == i).sum())
                               for i in range(fate.shape[1])]}).set_index("terminal_state"))

    _fig_certainty(ctx, A.obs_names, fate, names, groups, colours)

    lay = ctx.layout()
    lay_key, lay_short = ctx.layout_key()
    if lay is None:
        ctx.caveat("No two-column layout is on this object, so the fate map was not drawn. The "
                   "representation the chain was built on must NOT be substituted: its axes carry "
                   "no ordering, so its first two columns are two arbitrary coordinates and the "
                   "picture cannot announce itself as wrong. Compute a UMAP or similar on that "
                   "representation and this panel becomes drawable.")
    else:
        _fig_fate_map(ctx, A.obs_names, np.asarray(lay)[real][:, :2],
                      lay_short or lay_key, fate, names, order)

    if groups is None:
        ctx.caveat("No cell-type annotation is on this object, so the ordering could not be "
                   "summarised per population and the macrostates have no names beyond GPCCA's "
                   "own indices. The per-cell ordering is unaffected.")
    else:
        _fig_ordering_by_population(ctx, order, groups, colours)

    ctx.headline = (f"{fate.shape[1]} terminal state(s) over {A.n_obs:,} cells, "
                    f"from {which}")
    ctx.caveat(f"The ordering came from {which}, on a {ctx.config['n_neighbors']}-neighbour graph "
               f"built here on `{emb}`. Which kernel produced it decides the answer - a different "
               f"kernel can order the same cells in the opposite direction - and so does the "
               f"representation: a constrained embedding constrains the trajectory.")
    ctx.caveat(f"Terminal states were selected by method={method!r}"
               + (f" at stability_threshold={thr}" if method == "stability" else "")
               + f", from {len(got)} macrostate(s) each anchored by {n_anchor} cells. Those are "
                 f"parameters of this run, not properties of the data: the number of terminal "
                 f"states follows from them.")
    ctx.caveat("Fate probabilities sum to one by construction, so a cell with no clear fate is "
               "reported as evenly split rather than as unknown. The entropy panel is where that "
               "case is visible.")


def _report_velocity_genes(ctx, A, vk):
    """How many genes are actually behind the velocity half of the transition matrix.

    TWO FILTERS, NEITHER OF WHICH ANNOUNCES ITSELF. CellRank takes `var['{vkey}_genes']` as its
    gene subset when that column exists, and then drops every remaining gene whose velocity column
    contains a NaN - `np.isnan(np.sum(vdata, axis=0))`, with no log line. So the width of the fit
    is decided by a var column and a NaN test that the caller never sees.
    """
    import numpy as np
    try:
        col = np.asarray(A.layers["velocity"].sum(axis=0)).ravel()
        sub = None
        if "velocity_genes" in A.var:
            sub = np.asarray(A.var["velocity_genes"]).astype(bool)
        offered = int(sub.sum()) if sub is not None else int(A.n_vars)
        fitted = int(np.isfinite(col[sub] if sub is not None else col).sum())
        scale = (getattr(vk, "params", {}) or {}).get("softmax_scale")
        ctx.log(f"velocity kernel: {fitted:,} of {offered:,} offered gene(s) carried a finite "
                f"velocity" + (f"; softmax_scale={scale}" if scale is not None else ""))
        if fitted < offered:
            ctx.caveat(
                f"The velocity kernel was fitted on {fitted:,} of the {offered:,} genes offered "
                f"to it: CellRank drops any gene whose velocity is NaN, silently. "
                + ("The offered set is `var['velocity_genes']`, chosen upstream, not all "
                   f"{A.n_vars:,} genes in the object. " if sub is not None else "")
                + "A transition matrix built from a small surviving fraction is a direction "
                  "measured on those genes and not on the transcriptome.")
    except Exception as e:                                                    # noqa: BLE001
        ctx.log(f"  could not count velocity genes ({type(e).__name__}: {e})")


def selftest(ctx):
    """Prove the whole path, and REPORT WHICH SOLVER was used.

    The solver matters more than the shapes here: without petsc/slepc, GPCCA is correct and
    unusably slow, and a selftest that passed silently on the dense route would certify an
    environment that cannot finish a real cohort.

    It also proves the two objects the report's diagnostics are drawn from - the
    eigendecomposition and the coarse-grained matrix - and BOTH branches of the terminal-state
    call, because the branch this plugin turns into a refusal is the one no fixture reaches by
    accident.
    """
    import numpy as np
    import cellrank as cr
    import scanpy as sc

    try:
        import petsc4py, slepc4py                                     # noqa: F401
        route = "sparse (petsc4py/slepc4py present)"
    except ImportError:
        route = "DENSE - petsc4py/slepc4py absent"
    ctx.log(f"  GPCCA solver: {route}")

    rng = np.random.default_rng(0)
    n, g = 240, 60
    t = np.sort(rng.uniform(0, 1, size=n))                 # a planted progression
    X = np.exp(1.0 + 2.0 * np.outer(t, rng.uniform(0.2, 1.0, size=g)))
    A = ctx.fixture(n_cells=n, n_genes=g)
    A.X = X.astype("float32")
    A.obs["t"] = t
    sc.pp.pca(A, n_comps=10)
    sc.pp.neighbors(A, n_neighbors=15)

    kern = cr.kernels.ConnectivityKernel(A).compute_transition_matrix()
    assert kern.transition_matrix.shape == (n, n), \
        f"transition matrix is {kern.transition_matrix.shape}, expected ({n}, {n})"

    est = cr.estimators.GPCCA(kern)
    est.compute_schur(n_components=6)

    # F1 IS DRAWN FROM THESE TWO KEYS. `compute_schur` is what populates them, and a version that
    # stopped doing so would leave the panel silently undrawn rather than fail.
    eig = est.eigendecomposition
    assert eig is not None and "D" in eig and "eigengap" in eig, \
        f"compute_schur left no eigendecomposition with D/eigengap: {None if eig is None else sorted(eig)}"
    assert np.asarray(eig["D"]).size >= 2, "fewer than two eigenvalues came back"
    ctx.log(f"  spectrum: {np.asarray(eig['D']).size} eigenvalue(s), "
            f"eigengap suggests {int(eig['eigengap']) + 1} state(s)")

    est.compute_macrostates(n_states=3, n_cells=10, cluster_key=None)
    coarse = est.coarse_T
    assert coarse is not None, "no coarse-grained transition matrix - F2 has no source"
    assert coarse.shape[0] == coarse.shape[1], f"coarse_T is not square: {coarse.shape}"
    diag = np.diag(np.asarray(coarse, dtype=float))
    assert np.isfinite(diag).all(), "non-finite stability on the diagonal of coarse_T"
    ctx.log(f"  coarse_T {coarse.shape}, stability {diag.min():.3f}-{diag.max():.3f}")

    # BOTH BRANCHES. The declared default refuses when nothing is stable enough, and that refusal
    # is a path run() handles rather than a crash - so it is exercised here on purpose.
    try:
        est.predict_terminal_states(method="stability", n_cells=10, stability_threshold=0.96)
        route_t = "stability"
    except ValueError as e:
        assert "stability" in str(e), f"unexpected refusal from predict_terminal_states: {e}"
        ctx.log("  no macrostate reached stability 0.96 on the fixture - this is the branch "
                "run() turns into a refusal, and it raised as designed")
        est.predict_terminal_states(method="top_n", n_cells=10, n_states=2)
        route_t = "top_n (the fixture had no state at 0.96)"
    ctx.log(f"  terminal states via {route_t}")

    est.compute_fate_probabilities()
    fate = np.asarray(est.fate_probabilities)
    assert fate.shape[0] == n, f"fate probabilities cover {fate.shape[0]} of {n} cells"
    assert np.isfinite(fate).all(), "non-finite fate probabilities"
    assert np.allclose(fate.sum(axis=1), 1.0, atol=1e-3), \
        "fate probabilities do not sum to 1 - the estimator's contract changed"

    # F4's own arithmetic, on the numbers that reach it: entropy in bits, bounded by log2(k).
    k = fate.shape[1]
    safe = np.where(fate > 0, fate, 1.0)
    ent = -(np.where(fate > 0, fate, 0.0) * np.log2(safe)).sum(axis=1)
    assert np.isfinite(ent).all(), "non-finite fate entropy"
    assert ent.max() <= np.log2(k) + 1e-6, \
        f"entropy {ent.max():.4f} exceeds the log2({k}) ceiling the panel draws"
    ctx.log(f"  {k} macrostates over {n} cells, probabilities sum to 1, "
            f"entropy 0-{ent.max():.2f} of log2({k})={np.log2(k):.2f} bits")
    if route.startswith("DENSE"):
        ctx.log("  WARNING: the dense route is correct and does not finish on a real cohort.")
