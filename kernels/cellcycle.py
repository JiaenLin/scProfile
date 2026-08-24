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
"""

PLUGIN = {
    "api": 1,
    "version": "0.2.0",
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
    "provides": [],
    "produces": ["obs[phase]", "obs[S_score]", "obs[G2M_score]"],

    # WHAT WAS SHOWN TO IT - the honest list, which the plan reports so a user can see which of
    # their own columns and layers each plugin will touch. An under-declared plugin looks like one
    # that reads nothing at all.
    "sees": ["X", "layers[{lognorm}]", "var_names"],

    "config": {
        "min_panel_genes": {"type": "int", "default": 10, "min": 1,
                            "help": "refuse below this many matched genes in either panel - a "
                                    "score computed from a handful of genes is arithmetically "
                                    "fine and reads as 'not cycling' when it means 'the panel "
                                    "did not match your gene names'"},
    },

    "per_unit": None,
    "cost": "trivial", "cores": 1,
    # Measured, not estimated: fitted from this plugin's own instances in one run on a 10-sample mouse single-nucleus cohort (~99k cells). ONE dataset on ONE machine - a starting point that is right for scheduling, not a universal constant. Every run re-fits and prints its own.
    # Fitted from one instance; the split is indeterminate.
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
        "read": "2026-08-22",
        "defaults_changed": [
            "use_raw=False, and the values are ASSIGNED rather than named with `layer=`. "
            "scanpy's default `use_raw=None` means USE .raw IF PRESENT - so the same plugin, on "
            "two objects differing only in whether an upstream step left a .raw behind, scores "
            "DIFFERENT values, and nothing in the output says which was used. An object whose "
            ".raw holds counts rather than log-normalised values gets a score computed on counts.",
            "n_bins=25 and random_state=0 are scanpy's own defaults, kept and RECORDED. Changing "
            "either changes every score, so they belong in the caveats rather than in the code "
            "alone.",
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
        ],
        "gotchas": [
            "ctrl_size CANNOT BE PASSED to score_genes_cell_cycle. It computes it itself as "
            "min(len(s_genes), len(g2m_genes)) and then forwards **kwargs, so passing the keyword "
            "raises `got multiple values for keyword argument`. Nothing in the signature says so; "
            "six lines of its source do. This reached a live cohort, from a plugin that shipped no "
            "selftest because it declared it needed no environment - and the environment is not "
            "the only thing a selftest proves.",
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
        ],
    },

    "cannot_show": [
        "Phase is SCORED from a gene set, not measured. A cell scored G2M is one whose G2M genes "
        "are relatively high, which is not the same as a cell in G2M.",
        "The gene sets are the standard human ones, title-cased for mouse. They are not "
        "tissue-specific and were not curated for this dataset.",
        "On single nuclei the signal is weaker - cell-cycle transcripts are partly cytoplasmic - "
        "so a low score is as consistent with the assay as with a resting population.",
        "A cycling population is not a proliferating one. Scoring says which genes are high, not "
        "how many cells divided.",
    ],
}

#: scanpy's own defaults, named rather than inherited. `ctrl_size` is deliberately NOT here: see
#: upstream.gotchas.
N_BINS, SEED = 25, 0

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


def run(ctx):
    import numpy as np
    import pandas as pd
    import scanpy as sc

    A = ctx.adata
    s = _match(S_GENES, A.var_names)
    g2m = _match(G2M_GENES, A.var_names)
    ctx.log(f"panel matched: S {len(s)}/{len(S_GENES)}, G2M {len(g2m)}/{len(G2M_GENES)}")

    # A panel that barely matches produces a score that is arithmetically fine and means nothing.
    # Refusing is better than returning a column somebody will colour a UMAP by.
    floor = ctx.config["min_panel_genes"]
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
    # ctrl_size is NOT passable here; see upstream.gotchas. The control set is sized by the
    # PANELS that matched this object, not by score_genes' own default of 50.
    ctrl = min(len(s), len(g2m))
    sc.tl.score_genes_cell_cycle(A, s_genes=s, g2m_genes=g2m, use_raw=False,
                                 n_bins=N_BINS, random_state=SEED)

    ph = A.obs["phase"].astype(str)
    counts = ph.value_counts()
    cycling_fraction = float((ph != "G1").mean())
    ctx.log(f"phase: {dict(counts)}")

    # ---------------------------------------------------------------- figures
    # A trajectory that is secretly a cell-cycle axis is what this plugin exists to catch, and
    # that is a claim somebody will have to make in print. So it ships the two panels that support
    # it, to the same standard as everything else: vector, captioned, with their source data.
    try:
        plt, F = ctx.plot(), ctx.figure
        # A SENTINEL IS NOT A POPULATION. The directory-shaped version of this plugin grouped by
        # the raw label column, so an annotator's refusal to call a cell type appeared in the
        # per-population panel as a population with a cycling fraction. `ctx.populations()` is the
        # host's one answer to that question and attaches the caveat itself.
        mask, groups = ctx.populations()
        if groups is not None and len(groups):
            ct = pd.crosstab(pd.Series(groups, name="label"),
                             pd.Series(np.asarray(ph)[mask], name="phase"))
            for c in ("G1", "S", "G2M"):
                if c not in ct:
                    ct[c] = 0
            ct = ct[["G1", "S", "G2M"]]
            frac = ct.div(ct.sum(axis=1), axis=0).sort_values("G1")
            fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.6, 0.20 * len(frac) + 0.9)))
            left = np.zeros(len(frac))
            for c, col in zip(["G1", "S", "G2M"], ["#D9D9D9", "#0072B2", "#D55E00"]):
                ax.barh(np.arange(len(frac)), frac[c], left=left, color=col, label=c, height=.72)
                left += frac[c].values
            ax.set_yticks(np.arange(len(frac)))
            ax.set_yticklabels(frac.index)
            ax.invert_yaxis()
            ax.set_xlim(0, 1)
            ax.set_xlabel("fraction of cells")
            ax.spines["left"].set_visible(False)
            ax.tick_params(axis="y", length=0)
            F.legend_outside(fig, ax)
            ctx.emit_figure(
                "F1_phase_by_population", fig,
                caption=("Scored cell-cycle phase per population. Phase is SCORED from a gene "
                         "panel, not measured: a cell called G2M is one whose G2M panel genes are "
                         "relatively high. Use this to check whether a trajectory follows the "
                         "cycling fraction - if it does, the trajectory may be a cell-cycle "
                         "axis. Annotator sentinels are not shown as populations."),
                source=ct.assign(n_cells=ct.sum(axis=1)))

        # F2: the scores themselves, which is where a weak panel shows as a blob at the origin.
        dd = {"barcode": A.obs_names.astype(str), "S_score": A.obs["S_score"].values,
              "G2M_score": A.obs["G2M_score"].values, "phase": np.asarray(ph)}
        lab = ctx.obs("label")
        if lab is not None:
            dd["label"] = lab.astype(str).values
        fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.9))
        for phase_name, col in (("G1", "#D9D9D9"), ("S", "#0072B2"), ("G2M", "#D55E00")):
            m = np.asarray(ph) == phase_name
            if m.any():
                ax.scatter(A.obs["S_score"].values[m], A.obs["G2M_score"].values[m], s=2, c=col,
                           label=phase_name, linewidths=0, rasterized=True)
        ax.axhline(0, color=F.INK, lw=.5)
        ax.axvline(0, color=F.INK, lw=.5)
        ax.set_xlabel("S score")
        ax.set_ylabel("G2M score")
        F.legend_outside(fig, ax)
        ctx.emit_figure(
            "F2_scores", fig,
            caption=("S against G2M score, one point per cell; the phase call is which score is "
                     "higher, and positive. A cloud sitting at the origin means the panel found "
                     "little to score - on single nuclei that is expected, because cell-cycle "
                     "transcripts are partly cytoplasmic, and is as consistent with the assay as "
                     "with a resting population."),
            source=pd.DataFrame(dd).set_index("barcode"))
    except Exception as e:                                                # noqa: BLE001
        ctx.log(f"  figures not drawn: {e}")

    for col in ("phase", "S_score", "G2M_score"):
        ctx.emit_obs(col, A.obs[col].values)

    ctx.caveat(
        f"Scored from {scored_from} with use_raw=False, stated explicitly: scanpy's default would "
        f"have used .raw where present, so an object that had one would have been scored on "
        f"different values with nothing in the output saying so. Those values were assigned to X "
        f"before scoring, because the pinned scanpy's `score_genes` has no `layer` argument.")
    ctx.caveat(
        f"The score is the panel mean minus the mean of a control set drawn from matched "
        f"expression bins (ctrl_size={ctrl}, sized by the matched panels because scanpy computes "
        f"it and forbids the keyword; n_bins={N_BINS}, random_state={SEED}). That subtraction is "
        f"what makes zero a meaningful reference; a naive panel mean is dominated by how abundant "
        f"its genes happen to be.")
    ctx.caveat(
        f"Scored from {len(s)} S and {len(g2m)} G2M panel genes present in this object, out of "
        f"{len(S_GENES)} and {len(G2M_GENES)} declared.")
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
        f"relatively high', not as a proliferation rate.")

    ctx.headline = (f"{100 * cycling_fraction:.1f}% of cells score S or G2M "
                    f"(G1 {int(counts.get('G1', 0)):,}, S {int(counts.get('S', 0)):,}, "
                    f"G2M {int(counts.get('G2M', 0)):,})")


def selftest(ctx):
    """Prove the CALL is well-formed against the installed scanpy, before a run is spent.

    Not an import check. The first cohort this plugin ever met died three seconds in on

        score_genes() got multiple values for keyword argument 'ctrl_size'

    because `score_genes_cell_cycle` computes `ctrl_size = min(len(s_genes), len(g2m_genes))`
    itself and then forwards `**kwargs`. Nothing about the signature says so; six lines of its
    source do, and only running the real call finds it.

    It asserts SHAPES, COLUMNS and FINITENESS, never a biological answer: the fixture is synthetic
    and a selftest asserting a phase would be testing its own fixture.
    """
    import numpy as np
    import scanpy as sc

    ctx.log(f"  scanpy      {sc.__version__}")

    n = 300
    # The panels plus filler, so binning has something to bin against. `ctx.fixture` gives the
    # genes a spread of means because score_genes bins on expression and a flat matrix collapses
    # every bin.
    genes = list(S_GENES) + list(G2M_GENES) + [f"FILLER{i}" for i in range(400)]
    A = ctx.fixture(n_cells=n, genes=genes)

    counts_X = A.X.copy()
    for source in ("X", "lognorm"):
        # EXACTLY the call `run` makes, both ways it can make it - INCLUDING the assignment,
        # because `layer=` is what the pinned scanpy refuses and a selftest that called the
        # function differently from the plugin would have proved something about the selftest.
        A.X = counts_X if source == "X" else A.layers["lognorm"]
        sc.tl.score_genes_cell_cycle(A, s_genes=list(S_GENES), g2m_genes=list(G2M_GENES),
                                     use_raw=False,
                                     n_bins=N_BINS, random_state=SEED)
        for col in ("S_score", "G2M_score", "phase"):
            assert col in A.obs, f"{source}: scanpy did not write obs[{col!r}]"
        for col in ("S_score", "G2M_score"):
            v = np.asarray(A.obs[col], dtype=float)
            assert v.shape == (n,), f"{col} is {v.shape}, expected ({n},)"
            assert np.isfinite(v).all(), f"{col} contains non-finite values"
        ph = set(A.obs["phase"].astype(str))
        assert ph <= {"G1", "S", "G2M"}, f"unexpected phase labels {ph}"
        ctx.log(f"  scored from {'layers[lognorm]' if source == 'lognorm' else 'X'}: "
                f"{dict(A.obs['phase'].astype(str).value_counts())}")

    # The panel is HUMAN symbols and a mouse object is indexed by mouse ones. `_match` is what
    # bridges them, and if it ever stops matching, the plugin scores on a handful of genes and
    # returns a low score rather than refusing - which reads as "not cycling" and is not.
    mouse_names = [g.capitalize() for g in genes]
    got = _match(list(S_GENES), mouse_names)
    assert len(got) == len(S_GENES), (
        f"_match found {len(got)} of {len(S_GENES)} S genes against title-cased names")
    assert "Mcm5" in got, f"expected the mouse casing, got e.g. {got[:3]}"
    ctx.log(f"  _match: {len(got)}/{len(S_GENES)} S genes across casings, e.g. {got[:3]}")
