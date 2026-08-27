"""RNA velocity - the DIRECTION of transcriptional change, from spliced and unspliced counts.

WHAT THIS PLUGIN IS FOR, AND WHERE IT STOPS

Every other measurement in a single-cell dataset describes where a cell IS. Velocity is the only
one that says where it is GOING, and it does so from a fact of the chemistry: unspliced pre-mRNA
is transcribed before it is spliced, so a gene being switched on carries an unspliced excess and a
gene being switched off carries an unspliced deficit. Fit that per gene, and the residual points
along the cell's trajectory.

It stops at DIRECTION. Arrow length is not a rate in hours, and two datasets' arrows are not
comparable. Every one of those limits is in `cannot_show` and is printed under this plugin's own
results, so a reader meets them beside the figure rather than in a methods section they will not
open.

WHAT IT HANDS TO PSEUDOTIME, WHICH IS THE POINT OF RUNNING IT FIRST

A pseudotime built from expression alone is an AXIS WITHOUT AN ORIENTATION. Diffusion pseudotime
measures distance along the neighbour graph from a root cell, and the root is a decision - usually
an analyst pointing at the cluster they believe is the start. Velocity makes that decision from
the data: the arrows say which end is upstream. So this plugin ships its fitted object, velocity
graph included, as a side-car; `pseudotime` reads it and runs perfectly well without it on the
many datasets that have no unspliced counts, reporting an unoriented axis and saying so.

`velocity_pseudotime` is written here as well, because it is nearly free once the graph exists and
because users expect it. Read it as the weaker of the two claims: the single-nucleus validation in
the literature is DIRECTIONAL - nucleus and cell velocities correlate r 0.94-0.99 on matched
populations - and that study projected vectors and measured cell speed. It did not derive a
pseudotime from them.

NOTHING IS REMOVED FROM THE DATASET HERE

Velocity is fitted on a selected gene set, because the model needs genes with enough unspliced
signal to fit. That selection is INTERNAL: the merged object keeps every gene and every cell, the
counts printed below name exactly what the fit saw, and the fitted layers ship as their own file
rather than being padded back onto the full gene list - a zero in a `velocity` layer would assert
no change, when the truth is not fitted.

CONVERTED FROM FIVE FILES TO ONE, 2026-08-22, and two things moved rather than being rewritten.
The search for spliced/unspliced counts beside the object is now `scprofile/sources.py` and is
reached through `ctx.source_layers()`: it was never about velocity - any plugin needing something
the ALIGNER produced is in the same position, and the host is the only party holding the upstream
chain. The guard is now `guard(g)` in this file, which is a shape the host had to grow: a one-file
plugin had no way to declare one, so converting a guarded plugin would silently have deleted its
guard.
"""

PLUGIN = {
    "api": 1,
    "version": "0.2.0",
    "summary": "RNA velocity from spliced/unspliced counts - the DIRECTION of transcriptional "
               "change",
    "when_to_use": "your object carries spliced and unspliced layers, or the aligner output is "
                   "still beside it, and you want direction of change rather than position",
    "wraps": {"tool": "scvelo", "version": "0.3.4", "homepage": "https://scvelo.readthedocs.io",
              "license": "BSD-3-Clause", "cite": "Bergen et al., Nat Biotechnol 2020"},

    # NOT AN `inject`. The one prerequisite most datasets fail cannot be repaired later - spliced
    # and unspliced counts come from the ALIGNER - but they are very often still on disk beside
    # the object, so requiring them as a capability would refuse before looking. `needs` records
    # what it wants, `can_source_layers` tells the host not to block on it, and `ctx.source_layers`
    # goes and looks. It refuses with a list of everywhere it looked, which is strictly more
    # useful than "layers absent".
    "needs": {"layers": ["spliced", "unspliced"]},
    "can_source_layers": True,
    # `layout` AND `embedding` ARE BOTH NAMED, because this plugin uses both and they are not
    # the same object: the fit and the neighbour graph run on the representation, the arrows are
    # drawn on the layout. Declaring only one is how it came to draw on the other.
    "inject": {"required": [],
               "optional": ["counts", "label", "sample", "embedding", "layout"]},
    # IT PROVIDES THE CAPABILITY IT PRODUCES. This said `[]` while the plugin wrote a fitted
    # velocity field into obsm, so `pseudotime`, which declares `velocity` as an input it can
    # use, could never be given one: the host resolves a derived capability to whoever DECLARES
    # it, not to whoever happens to write a matching key.
    "provides": ["velocity"],
    "produces": ["obs[velocity_confidence]",
                 "obs[velocity_length]",
                 "obs[velocity_pseudotime]",
                 # `?` - PRODUCED ONLY IN `dynamical` MODE. Without the mark the declaration is a
                 # promise this plugin breaks on every default run, and drift reported on every
                 # run is drift nobody reads.
                 "obs[latent_time]?",
                 "obsm[velocity_*]",
                 "objects[velocity_h5ad]",
                 "tables/velocity_by_label.csv",
                 "tables/velocity_transitions.csv",
                 "tables/velocity_genes.csv"],

    # WHAT WAS SHOWN TO IT. The plan reports this so a user can see which of their own layers and
    # columns each plugin will touch; an under-declared plugin looks like one that reads nothing.
    "sees": ["layers[spliced]", "layers[unspliced]", "layers[{counts}]",
             "obsm[{embedding}]", "obs[{label}]"],

    # TYPED, DEFAULTED AND RANGE-CHECKED BY THE HOST before run() is called. These were a private
    # DEFAULTS dict read out of raw `--params`, so `--params '{"n_top_gene": 3000}'` was silently
    # dropped and `--params '{"n_pcs": "thirty"}'` failed an hour in. A bad parameter should fail
    # in the second the plan is drawn.
    "config": {
        "mode": {"type": "str", "default": "stochastic",
                 "help": "stochastic | deterministic | dynamical. `dynamical` also fits kinetic "
                         "rates and writes obs[latent_time]; it is the slow one, minutes to "
                         "hours, and it is what you want to read per-gene kinetics"},
        "n_top_genes": {"type": "int", "default": 2000, "min": 50,
                        "help": "genes carried into the fit"},
        "min_shared_counts": {"type": "int", "default": 20, "min": 0,
                              "help": "minimum spliced+unspliced counts for a gene to be fitted"},
        "n_pcs": {"type": "int", "default": 30, "min": 2,
                  "help": "principal components the moment/neighbour step works on"},
        "n_neighbors": {"type": "int", "default": 30, "min": 2,
                        "help": "neighbours for the moments and, if one must be computed, the "
                                "embedding"},
        "basis": {"type": "str", "default": "",
                  "help": "obsm key to draw arrows on, without the X_ prefix. Empty means the "
                          "host's detected embedding, then the first of umap, scanvi, scvi, "
                          "harmony, tsne, pca present - so an integrated embedding wins and the "
                          "arrows land on the manifold the rest of the report uses"},
        "min_dist": {"type": "float", "default": 0.2, "min": 0.0,
                     "help": "only used if no embedding exists and one has to be computed here"},
        "n_jobs": {"type": "int", "default": 0, "min": 0,
                   "help": "workers for the graph step. 0 means the core share the host "
                           "allocated, which is what it should almost always be"},
        "min_confidence": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0,
                           "help": "below this MEDIAN confidence the run reports `partial` and "
                                   "says the field is unresolved rather than presenting it as a "
                                   "direction"},
        "spliced_source": {"type": "str", "default": "",
                           "help": "a directory to search FIRST for spliced/unspliced counts, "
                                   "ahead of the leads the upstream chain recorded"},
        "min_barcode_match": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0,
                              "help": "a source matching fewer than this fraction of a sample's "
                                      "barcodes is not used - a partial match fills some cells "
                                      "and leaves the rest at zero, which fits perfectly well "
                                      "and means nothing"},
    },

    "per_unit": None,
    "cost": "high", "cores": 8,
    # Measured, not estimated: fitted from this plugin's own instance in one run on a 10-sample
    # mouse single-nucleus cohort (~99k cells). ONE dataset on ONE machine - a starting point
    # that is right for scheduling, not a universal constant. Every run re-fits and prints its
    # own. One instance, so the split between baseline and per-cell is indeterminate and the
    # whole peak is attributed to the RATE: that over-charges a smaller dataset, where the error
    # is bounded, rather than under-requesting a larger one, which is what kills a job.
    "memory_gb_per_100k": 14.6,
    "design_aware": True,

    # WHAT IT NEEDS, NOT WHAT TO BUILD. These are exact, and `exact_pins_why` says so once rather
    # than the validator saying it sixteen times: they are the stack scvelo 0.3.4 was released
    # alongside, and its own lower bounds resolve today to a stack released long after its last
    # commit.
    "requires": {
        "python": "==3.11",
        "channels": ["conda-forge"],
        "exact_pins_why":
            "scvelo 0.3.4 declares `pandas!=1.4.0,>=1.1.1`, `numpy>=1.17`, `scanpy>=1.5`. Those "
            "lower bounds are honest about what it was written against and say NOTHING about "
            "what it still works with: resolved today they pull pandas 3, numpy 2.5 and scanpy "
            "1.12 - a stack released long after scvelo's last commit. An upper bound nobody wrote "
            "is not an upper bound that does not exist. In this project a neighbouring tool "
            "resolved that way, called a pandas function removed in 2.0, and the metric came back "
            "ABSENT rather than failing - a silent hole in a benchmark table. `selftest` runs a "
            "complete velocity fit against these versions before any real run is spent.",
        "packages": {
            "numpy": "==1.26.4",
            "scipy": "==1.13.1",
            "pandas": "==2.2.3",
            "numba": "==0.60.0",
            "llvmlite": "==0.43.0",
            "scikit-learn": "==1.5.2",
            "matplotlib": "==3.9.2",
            "h5py": "==3.12.1",
            "anndata": "==0.10.9",
            "scanpy": "==1.10.4",
            "umap-learn": "==0.5.7",
            "pynndescent": "==0.5.13",
            "igraph": "==0.11.8",
            "leidenalg": "==0.10.2",
            "loompy": "==3.0.7",
            "scvelo": "==0.3.4",
        },
    },

    "upstream": {
        "docs": "https://scvelo.readthedocs.io",
        "read": "2026-08-22",
        "defaults_changed": [
            "GENE SELECTION AND THE LOG ARE DONE HERE, EXPLICITLY. scvelo 0.3 removed both from "
            "`filter_and_normalize` - it is `filter_genes` + `normalize_per_cell` and nothing "
            "else, though its own docstring still says 'Filtering, normalization and log "
            "transform'. Passing `n_top_genes` reaches `normalize_per_cell` through **kwargs and "
            "raises inside a function whose name gives no hint why. It failed on the first "
            "cluster run in eight seconds because the selftest runs the whole path rather than "
            "importing the package.",
            "n_jobs is the host's ALLOCATED core share rather than scvelo's serial default. "
            "`velocity_graph` is the cost of the run and is parallel; leaving it serial is "
            "under-use, and reading the machine's core count is how four plugins start four times "
            "the node's worth of threads.",
            "arrow_size in the plots is 0.7 rather than scvelo's default. It is in POINTS and "
            "does not scale with the figure, so a panel built for an 85 mm column comes out with "
            "arrowheads meant for a screen.",
            "basis is the LAYOUT DERIVED FROM the integrated representation where one exists - "
            "`X_umap_<name>` beside `X_<name>` - rather than whatever is first in obsm. Arrows "
            "drawn on a different manifold from the annotation cannot be read against it, and "
            "arrows drawn on the representation ITSELF cannot be read at all: that space is 30 "
            "to 50 columns wide, its axes carry no ordering, and its first two are a ball.",
        ],
        "not_used": [
            "mode='dynamical' as the default: it fits per-gene kinetic rates and `latent_time` "
            "and costs minutes to hours. It is offered as config rather than assumed.",
            "scv.tl.differential_kinetic_test - whether a gene's kinetics DIFFER between "
            "populations. Closer to a designed experiment's question than one field is, and it is "
            "a second plugin rather than a flag.",
            "scv.tl.velocity_clusters - clustering on velocity rather than on expression.",
        ],
        "gotchas": [
            "The spliced/unspliced layers are NOT ambient-corrected and cannot be: correction is "
            "applied to total counts and does not decompose into spliced and unspliced parts.",
            "`filter_and_normalize` selects GENES, not cells. That is asserted here rather than "
            "trusted, because every obs column written below is aligned to the object's names.",
            "A velocity matrix that is entirely NaN is what a broken numba backend produces, and "
            "it travels all the way to a stream plot with no arrows and no error message. The "
            "selftest checks for it by name.",
        ],
    },

    # WHAT ITS PAGE SHOULD CONTAIN, declared so the reporter can lay it out, caption it, and say
    # which panel is MISSING. Retrofitted to nine panels this plugin already drew: before this
    # block existed the page was those nine in emission order, with nothing on it saying that the
    # first four are checks on whether the field means anything and the rest are the field.
    #
    # `shows` is the whole of the reporter's knowledge. It knows no id here and never will.
    "report": {
        "figures": [
            {"id": "F1_proportions", "shows": "diagnostic", "required": True,
             "question": "is there enough unspliced signal for the model to fit?",
             "source": "figures/F1_proportions.csv"},
            {"id": "F4_confidence", "shows": "diagnostic", "required": True,
             "question": "do neighbouring cells agree on the direction?",
             "source": "figures/F4_confidence.csv"},
            {"id": "F9_by_population", "shows": "diagnostic", "required": True,
             "question": "where is the field trustworthy, population by population?",
             "source": "figures/F9_by_population.csv"},
            # OPTIONAL, AND THE REASON IS THE FINDING. Only a small subset of genes obeys the
            # kinetics these models assume, and where none does the field rests on nothing - so
            # the absence of this panel says more than the panel would.
            {"id": "F5_phase_portraits", "shows": "diagnostic", "required": False,
             "question": "do the driver genes actually obey the kinetics the model assumes?",
             "source": "figures/F5_phase_portraits.csv",
             "when_absent": "no gene passed the dynamical fit, so there is no phase portrait to "
                            "draw. Read the field below as resting on the steady-state "
                            "approximation alone."},
            {"id": "F8_drivers", "shows": "diagnostic", "required": False,
             "question": "which genes carry the field?",
             "source": "figures/F8_drivers.csv",
             "when_absent": "the fit produced no ranking column, so the genes driving the field "
                            "cannot be named - only that some do."},
            {"id": "F2_stream", "shows": "result", "required": True,
             "question": "which way is the field pointing?",
             "source": "figures/F2_stream.csv"},
            {"id": "F3_grid", "shows": "result", "required": True,
             "question": "does the field hold without interpolation between cells?",
             "source": "figures/F3_grid.csv"},
            {"id": "F6_transitions", "shows": "result", "required": True,
             "question": "which populations flow into which?",
             "source": "figures/F6_transitions.csv"},
            {"id": "F7_pseudotime", "shows": "result", "required": True,
             "question": "what ordering does the field imply?",
             "source": "figures/F7_pseudotime.csv"},
        ],
        # THE PAIRING. Velocity and a pseudotime built without it answer the same question from
        # different evidence, and a published comparison exists precisely because velocity can be
        # wrong where the ordering is right (CellRank 2, Nat Methods 2024). Declared here so the
        # reporter can name the missing half as an absence rather than leave the page silent;
        # neither plugin can draw the comparison alone.
        "reads_with": ["pseudotime"],
    },

    "cannot_show": [
        "Velocity is a DIRECTION, not a rate of change in real time. Arrow length is not speed in "
        "hours, and two datasets' arrow lengths are not comparable.",
        "THE MODEL'S OWN ASSUMPTIONS CAN BE VIOLATED WITHOUT ANY ERROR. scVelo's authors state "
        "that errors arise where a common splicing rate across genes, or the observation of full "
        "splicing dynamics with steady-state mRNA levels, does not hold (Bergen et al., Nat "
        "Biotechnol 2020). Neither is testable from the counts, so a violated assumption presents "
        "as a confident field rather than as a failure.",
        "UNSPLICED ABUNDANCE IS PARTLY A PROPERTY OF THE GENE, NOT THE CELL. It varies with the "
        "amount of relevant intronic sequence per gene, and intronic reads are only a noisy "
        "approximation of nascent transcription (Bergen et al., Mol Syst Biol 2021, citing Erhard "
        "et al. 2019). Genes with little intronic sequence are underrepresented in the fit "
        "regardless of how they are transcribed; metabolic labelling, not deeper sequencing, is "
        "what resolves this.",
        "The validated single-nucleus use is DIRECTIONAL. Nucleus and cell velocities correlate "
        "0.94-0.99 on matched microglia (Sci Rep 2024), but that study projected vectors and "
        "measured cell speed - it did not derive a pseudotime from them. `velocity_pseudotime` "
        "rests on more assumptions than the arrows do.",
        "Quantification choices change the answer. How intronic reads were counted, and whether "
        "the reference included intronic regions, alter library size, cell-type assignment and "
        "therefore velocity - so a velocity result is a property of the alignment as much as of "
        "the biology.",
        "snRNA intronic reads carry a GENE LENGTH BIAS, in both exonic and intronic counts. A "
        "long gene contributes more unspliced signal for reasons that are not kinetic.",
        "Unspliced counts are noisy, especially for 3-prime tagging chemistries. Nuclei have "
        "proportionally more intronic signal than cells, which helps - but the per-gene counts "
        "are still small.",
        "Unspliced mRNA is READ AS a transitional state, and need not be. A stable population can "
        "hold an unspliced reservoir for rapid transcription-independent expression, and looks "
        "identical here.",
        "These counts are NOT ambient-corrected. Correction is applied to total counts and cannot "
        "be decomposed into spliced and unspliced parts. Published snRNA velocity does not "
        "correct either, and the effect is contained to this plugin's own outputs - nothing else "
        "in the object reads these layers.",
        "The arrows are drawn as a PROJECTION into two dimensions. The fit happens in gene space, "
        "and a 2-D layout that tore the manifold can make a coherent field look incoherent, or "
        "the reverse. Read the field beside velocity_confidence, never alone.",
    ],
}

#: Embeddings to project arrows onto, best first. An integrated embedding is preferred because
#: that is the manifold the annotation and the report already use - drawing velocity on a
#: different one gives two pictures of the same cells that cannot be laid side by side.
BASIS_PREFERENCE = ("umap", "scanvi", "scvi", "harmony", "umap_integrated", "tsne", "pca")

#: The modes scvelo's own `velocity` accepts. Checked here because an unrecognised string is
#: passed straight through and produces a plausible field from a model nobody chose.
MODES = ("stochastic", "deterministic", "dynamical")


# ---------------------------------------------------------------------------------- the guard

def guard(g):
    """Is this dataset one where velocity would MEAN what the report says?

    Runs in the HOST, before the environment is resolved and before anything is spent. NOT a
    prerequisite check - the host's `unmet()` covers those, and no amount of willingness makes a
    missing layer runnable. This is about INTERPRETABILITY: the run would succeed, produce
    numbers, and those numbers would not support the sentence a reader will write under them.

    The escape is `--allow velocity`, and every use of it is appended to `guard_overrides.jsonl`
    with its reason.
    """
    if not g.assay:
        g.deny(
            "The assay is not declared or detected, and velocity says different things about\n"
            "nuclei and whole cells. On nuclei the unspliced fraction is high BY CONSTRUCTION,\n"
            "so every caveat this plugin writes depends on knowing which you have.\n"
            "  Fix: pass --assay nucleus or --assay cell. It changes no computation.")
        return
    if g.assay == "nucleus":
        g.note("single-NUCLEUS velocity: validated directionally against matched cells "
               "(r 0.94-0.99, Sci Rep 2024), but the pseudotime output rests on more than the "
               "arrows do")
    if not g.organism:
        g.note("organism unknown; nothing here depends on it, but the report will say so")


# ------------------------------------------------------------------------------------ helpers

def _pick_basis(ctx, declared):
    """The 2-D space the arrows are drawn in, and a sentence saying how it was chosen.

    Returns (basis, why) or (None, why) when one has to be computed, and raises ValueError when
    the user named one that is not there - which the caller turns into a refusal, because naming a
    missing embedding is a fact about the request and a run should say so rather than pick another.
    """
    A = ctx.adata
    have = {k[2:] if k.startswith("X_") else k: k for k in A.obsm}

    def _two(key):
        """Is this obsm entry actually two columns? A basis that is not is not a picture."""
        m = A.obsm.get(have.get(key, key))
        return getattr(m, "ndim", 0) == 2 and m.shape[1] == 2

    if declared:
        d = declared[2:] if declared.startswith("X_") else declared
        if d not in have:
            raise ValueError(
                f"basis={declared!r} was asked for and obsm has {sorted(A.obsm)}. Name one of "
                f"those, or leave it empty and one will be chosen.")
        if not _two(d):
            raise ValueError(
                f"basis={declared!r} has {A.obsm[have[d]].shape[1]} columns. Arrows are drawn on "
                f"two axes; the first two columns of a wider space are two coordinates of it, "
                f"not a picture of it.")
        return d, "declared in --params"

    # THE LAYOUT, NOT THE REPRESENTATION. This read `ctx.keys['embedding']` and checked its width
    # nowhere, so on an integrated object every panel was drawn on the first two columns of a
    # 30-dimensional scANVI latent - labelled SCANVI 1 and SCANVI 2, two arbitrary coordinates of
    # a space with no variance ordering, which draw as a featureless ball whatever structure the
    # data has. The object carried `X_umap_scanvi` throughout. scvelo's own default basis is
    # `umap` and its documented preference is umap, tsne, pca: a 30-column latent was never
    # expected here by the tool either.
    named = ctx.keys.get("layout")
    if named:
        d = named[2:] if named.startswith("X_") else named
        if d in have and _two(d):
            return d, f"the layout the host resolved ({named})"

    for cand in BASIS_PREFERENCE:
        if cand in have and _two(cand):
            return cand, f"first of {list(BASIS_PREFERENCE)} present in obsm, at two columns"

    wide = sorted(f"{k} ({A.obsm[v].shape[1]}c)" for k, v in have.items()
                  if getattr(A.obsm[v], "ndim", 0) == 2 and A.obsm[v].shape[1] != 2)
    return None, ("no two-column embedding in obsm; one will be computed here"
                  + (f". Present but wider, and therefore not a layout: {', '.join(wide[:6])}"
                     if wide else ""))


def _short(F, labels):
    """Hierarchical population names cut to their shortest UNAMBIGUOUS tail, in order.

    THE AXIS, NEVER THE SOURCE TABLE. An annotation label is a PATH, and on a real cohort the
    paths run to fifty or more characters - as a PAIR, on the transitions panel, to a hundred.
    Drawn in full they take more of a panel than the data does, measured on a twelve-population
    fixture: the transitions panel saved at 169 mm and the proportions panel at 143 mm, both
    declared at the 85 mm single column, the excess entirely tick text. The full path stays in the
    CSV emitted beside every panel, so nothing is lost by shortening the axis.
    """
    m = F.short_labels([str(l) for l in labels])
    return [m[str(l)] for l in labels]


def _by_size(counts):
    """The one order every per-population panel uses: most cells first, ties by name.

    THREE PANELS SORTED THREE WAYS is what this replaces - the proportions panel by unspliced
    fraction, the confidence boxes alphabetically, the per-population pair by cell count. Same
    populations, same page, three vertical orders, so a reader comparing a population across the
    diagnostics had to find it again in each one. Which order is chosen matters far less than that
    one is.
    """
    return [l for l, _ in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))]


def _point_size(n):
    """Marker area for a scatter of n cells at journal column width.

    A SIZE THAT WAS RIGHT FOR THE FIXTURE. `s=2` was typed against a few thousand cells; at a
    hundred thousand on an 85 mm panel the same 2 covers the manifold in a solid mat and every
    structure inside it, which is exactly the size of dataset this plugin is costed for.
    """
    return float(min(8.0, max(0.5, 5000.0 / max(int(n), 1) ** 0.7)))


def _draw_order(n, seed=0):
    """A fixed random permutation to scatter in.

    DRAWING ORDER IS AN ARGUMENT. Points drawn last are the points a reader sees: sorting the
    confidence map by confidence put every high value on top of every low one, and the field came
    out uniformly confident whatever the data said. In a categorical map the same thing happens by
    accident, because the object's row order is usually the order the populations were
    concatenated in. A permutation is the only order that asserts nothing.
    """
    import numpy as np
    return np.random.default_rng(seed).permutation(int(n))


def _fraction_axis(ax):
    """0 to 1 at quarters, on every axis of this page that carries a fraction.

    FIVE AXES ON THIS PAGE CARRY A PROPORTION and every one of them was left to matplotlib, which
    fits the axis to the data - so a median confidence of 0.75 and an unspliced fraction of 0.35
    drew bars of the same length in the two halves of ONE figure whose entire question is how the
    two compare. A fraction has a known range; there is no reason to discover it per panel, and
    every reason not to.
    """
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "0.25", "0.5", "0.75", "1"])


def _bar_grid(ax, axis="x"):
    """Faint rules behind the bars, so a length can be read without opening the CSV."""
    ax.set_axisbelow(True)
    ax.grid(axis=axis, color="#E8E8E8", lw=0.5, zorder=0)


def _annotate_n(ax, ys, counts, x=1.02):
    """The cell count each row was computed from, in the right margin.

    A MEDIAN OVER 47 CELLS AND A MEDIAN OVER 37,000 DRAW THE SAME BAR. On a real annotation the
    populations differ by three orders of magnitude, and a per-population panel that does not
    carry n invites the reader to weigh them equally - which is the one thing the figure knows to
    be wrong and the reader cannot see.
    """
    for yy, c in zip(ys, counts):
        ax.text(x, yy, f"{int(c):,}", transform=ax.get_yaxis_transform(),
                ha="left", va="center", fontsize=5.5, color="#666666", clip_on=False)
    ax.text(x, 1.0, "n", transform=ax.transAxes, ha="left", va="bottom",
            fontsize=5.5, color="#666666", clip_on=False)


def _fit_width(fig, target):
    """Shrink the canvas until what is SAVED is `target` inches wide, legend and margins in.

    A FIGURE IS MADE AT THE WIDTH IT WILL BE PRINTED AT - that is the whole reason the shared
    conventions carry `SINGLE` and `DOUBLE` - and `bbox_inches="tight"` quietly breaks the promise
    the moment anything is drawn outside the axes. A legend anchored past the right edge is not
    seen by constrained layout, so the tight bounding box grows to include it and the file comes
    out wider than it was declared to be: the phase grid saved at 213 mm for a 174 mm column, and
    a figure scaled back down at submission has 7 pt labels at 5.7 pt.

    Measured rather than guessed, because the width of a legend depends on the labels in it - and
    those are somebody else's annotation. Three passes, because moving the edge moves the legend
    with it; it converges in two on everything drawn here.
    """
    pad = 0.04                                   # savefig.pad_inches, both sides
    for _ in range(3):
        fig.canvas.draw()
        try:
            got = fig.get_tightbbox(fig.canvas.get_renderer()).width + pad
        except Exception:                                                 # noqa: BLE001
            return
        w, h = fig.get_size_inches()
        # IT SHRINKS AND NEVER GROWS. Symmetric, it also widened a figure whose content was
        # NARROWER than its canvas - which is every grid holding an empty cell - and each pass
        # widened the canvas without widening the content, so a one-gene phase grid walked from
        # 174 mm to 409 mm in three passes. The declared width is the intent; overflow is the
        # defect, and only overflow is corrected here.
        if got <= target + 0.02:
            return
        fig.set_size_inches(max(1.6, w - (got - target)), h)


def _clean(ax, F, basis=None):
    """An embedding panel: no ticks, no frame, TRUE ASPECT, and a corner axis indicator.

    `set_aspect("equal")` IS THE PUBLICATION FIX HERE AND IT WAS MISSING. A UMAP drawn into a
    box of a different shape from its data is a UMAP with a scale factor in one axis: distances
    are the entire content of an embedding, and every panel of this page drew them stretched by
    whatever ratio the figure happened to have.

    A publication panel names its axes even when the values are meaningless. An unlabelled
    embedding is the commonest reason a reviewer asks what they are looking at - and a corner
    indicator says it in the space a pair of full-length axis labels wanted, which on a square
    map is the difference between a legible panel and a cramped one.

    THE ALGORITHM, THEN WHAT IT WAS RUN ON. Uppercasing the whole obsm key gave `UMAP_SCANVI 1`,
    which reads as an algorithm nobody has heard of. A layout derived from a representation is a
    UMAP OF that representation, and saying it that way is both shorter and true. The splitter
    lives in `figure.py`, because four plugins spelling their own axis label is four labels that
    drift apart.
    """
    import matplotlib.patheffects as pe
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    # `datalim`, NOT `box`. Both hold the aspect and neither distorts anything; the difference is
    # which one gives way. `box` shrinks the axes inside the cell the layout gave it and leaves a
    # margin the colourbar then attaches to the far side of - a small map, a floating bar, and a
    # band of white between them. `datalim` keeps the cell and widens the limits instead, so the
    # panel is as large as the figure can make it.
    ax.set_aspect("equal", adjustable="datalim")
    if not basis:
        return
    halo = [pe.withStroke(linewidth=1.8, foreground="white")]
    kw = dict(xycoords="axes fraction", textcoords="axes fraction",
              arrowprops=dict(arrowstyle="-|>,head_width=0.14,head_length=0.3", lw=0.7,
                              color=F.INK, shrinkA=0, shrinkB=0,
                              path_effects=[pe.withStroke(linewidth=2.0, foreground="white")]))
    ax.annotate("", xy=(0.175, 0.02), xytext=(0.02, 0.02), **kw)
    ax.annotate("", xy=(0.02, 0.175), xytext=(0.02, 0.02), **kw)
    ax.text(0.19, 0.02, F.basis_label(basis, 1), transform=ax.transAxes, ha="left",
            va="center", fontsize=5.5, color=F.INK, path_effects=halo)
    ax.text(0.02, 0.19, F.basis_label(basis, 2), transform=ax.transAxes, ha="left",
            va="bottom", rotation=90, fontsize=5.5, color=F.INK, path_effects=halo)


def _colours_for(ctx, labels):
    """A colour per population, with annotator sentinels forced to GREY.

    A sentinel is not a cell type - it is the annotator saying it declined to call one. Giving it
    a hue of its own puts it in the legend beside the real populations as though it were one, and
    a reader has no way to tell from the figure that it is not.
    """
    F = ctx.figure
    sent = {str(s) for s in ctx.sentinels}
    every = sorted(set(map(str, labels)))
    real = [l for l in every if l not in sent]
    cols = F.palette(real)
    for l in every:
        if l in sent:
            cols[l] = F.GREY
    # A HUE CARRYING TWO POPULATIONS IS SAID, because it cannot be seen. The palette used to
    # cycle at eight and this cohort has fourteen cell types, so five pairs shared a colour and
    # the legend showed each hue twice with nothing anywhere admitting it. The palette is longer
    # now; past its end the only honest thing is to name the pairs.
    clash = getattr(F, "palette_collisions", None)
    for colour, labs in (clash(real) if clash else []):
        ctx.caveat(f"{len(labs)} populations share one colour in every figure below "
                   f"({', '.join(labs)}). There are more populations than the palette has hues "
                   f"that stay separable; read those points from the per-population panels "
                   f"rather than from the map.")
    return cols


def _scatter_cells(ax, xy, labels, colours, F, alpha=1.0):
    """The cell layer under a field panel: one dot per cell, coloured by population.

    Rasterised, because a hundred thousand vector dots is a 40 MB PDF that opens in nothing, and
    permuted, because the object's row order is the order the samples were concatenated in.
    """
    import numpy as np
    from matplotlib.colors import to_rgba_array
    o = _draw_order(len(xy))
    if labels is not None and colours:
        cvec = to_rgba_array([colours.get(str(l), F.GREY) for l in labels])[o]
    else:
        cvec = F.GREY
    ax.scatter(xy[o, 0], xy[o, 1], c=cvec, s=_point_size(len(xy)), linewidths=0,
               alpha=alpha, rasterized=True, zorder=1)


def _place_labels(ax, F, xy, labels, colours, sentinels):
    """Population names ON the map, at each population's median position.

    A LEGEND OF FOURTEEN ENTRIES BESIDE AN 85 mm MAP LEAVES 45 mm OF MAP. It also asks the reader
    to carry a swatch across the gap and match it against a dot two thirds of a millimetre across,
    which for the pairs of hues that survive a colour-vision check is not reliably possible. A
    name written where the population is needs neither. The median, not the mean, so a population
    with a satellite lobe is still labelled inside itself.

    Returns the names it drew, which is empty only when the annotation is nothing but sentinels -
    the one case where the caller falls back to a legend, because there is no population to write
    anywhere.
    """
    import numpy as np
    import matplotlib.patheffects as pe
    sent = {str(s) for s in sentinels}
    labs = np.asarray([str(l) for l in labels])
    real = [l for l in sorted(set(labs)) if l not in sent]
    if not real:
        return []
    pos = {l: (float(np.median(xy[labs == l, 0])), float(np.median(xy[labs == l, 1])))
           for l in real}
    short = dict(zip(real, _short(F, real)))
    # Nudge apart in y only, in data units, so a name never sits on another name. Ten passes is
    # enough for the crowding a real annotation produces and cannot oscillate the way a free
    # repulsion can.
    span = float(np.ptp(xy[:, 1])) or 1.0
    gap = 0.045 * span
    for _ in range(25):
        order = sorted(real, key=lambda l: pos[l][1])
        moved = False
        for a, b in zip(order, order[1:]):
            dy = pos[b][1] - pos[a][1]
            dx = abs(pos[b][0] - pos[a][0])
            if dy < gap and dx < 0.14 * (float(np.ptp(xy[:, 0])) or 1.0):
                pos[a] = (pos[a][0], pos[a][1] - (gap - dy) / 2)
                pos[b] = (pos[b][0], pos[b][1] + (gap - dy) / 2)
                moved = True
        if not moved:
            break
    for l in real:
        # A PLATE, NOT A STROKE. A white outline round the glyphs is enough over a scatter and
        # not over a stream line, and the stream is drawn in ink at up to a point wide: the
        # letters and the field ended up the same colour in the same place. A semi-opaque plate
        # hides a little of the map and makes the name readable on all of it.
        ax.text(pos[l][0], pos[l][1], short[l], ha="center", va="center", fontsize=5.5,
                color=F.INK, zorder=5, clip_on=False,
                path_effects=[pe.withStroke(linewidth=1.6, foreground="white")],
                bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.66))
    return real


def _velocity_on_grid(xy, v, n=50, smooth=0.55, k=None):
    """The projected field averaged onto a regular grid, with the local cell mass beside it.

    ONE GRID FOR BOTH FIELD PANELS. The stream and the arrow panel are declared as the same field
    drawn two ways - "which is why this panel and the stream can disagree, and why both are
    shown" - and that sentence is only true if the disagreement is the drawing. Computed twice at
    two densities by two calls with two autoscalings, a difference between the panels could as
    easily have been the two computations, and no reader could tell which.

    Gaussian-weighted mean of the k nearest cells at each node, kernel width set from the node
    spacing - the same estimator the wrapped tool uses for its own grid, kept here so both panels
    can share one call and one scale. `mass` is the summed kernel weight and is what decides where
    there are enough cells to draw an arrow at all: an empty region must stay empty, or the panel
    interpolates across a gap and asserts a flow through cells that are not there.
    """
    import numpy as np
    from scipy.spatial import cKDTree
    ok = np.isfinite(xy).all(1) & np.isfinite(v).all(1)
    xy, v = np.asarray(xy)[ok], np.asarray(v)[ok]
    grs = []
    for d in range(2):
        lo, hi = float(xy[:, d].min()), float(xy[:, d].max())
        pad = 0.02 * (hi - lo or 1.0)
        grs.append(np.linspace(lo - pad, hi + pad, int(n)))
    X, Y = np.meshgrid(grs[0], grs[1])
    P = np.column_stack([X.ravel(), Y.ravel()])
    kk = int(k or min(max(len(xy) // 50, 30), 500))
    kk = max(1, min(kk, len(xy)))
    dist, idx = cKDTree(xy).query(P, k=kk, workers=-1)
    if dist.ndim == 1:
        dist, idx = dist[:, None], idx[:, None]
    scale = float(np.mean([g[1] - g[0] for g in grs])) * smooth
    w = np.exp(-0.5 * (dist / scale) ** 2)
    mass = w.sum(1)
    V = (v[idx] * w[:, :, None]).sum(1) / np.maximum(mass, 1e-12)[:, None]
    sh = X.shape
    return (grs[0], grs[1], V[:, 0].reshape(sh), V[:, 1].reshape(sh), mass.reshape(sh))


# ------------------------------------------------------------------------------------ figures
#
# The set a velocity paper actually contains - not "some plots of the result". Each is written as
# a raster preview and a vector PDF with live text, at journal column width, with a caption saying
# what it is FOR and the table it was drawn from beside it.
#
#   proportions   spliced vs unspliced per population. The first panel in most velocity papers,
#                 and the one that decides whether the rest is worth reading.
#   stream/grid   the field on the embedding. The headline panels.
#   confidence    per cell and per population - whether to believe the headline one.
#   phase         per-gene phase portraits. The evidence that the model fitted anything.
#   transitions   directed population-to-population flow: the stream, in numbers.
#   pseudotime    the ordering, with its own caveat in the caption.
#   drivers       the genes carrying the field, ranked.

def _fig_proportions(ctx, mask, groups):
    """Spliced/unspliced balance per population - the panel that licenses the rest."""
    import numpy as np
    import pandas as pd
    if groups is None or not len(groups):
        return
    A = ctx.adata
    rows = []
    for lab in sorted(set(groups)):
        m = np.zeros(A.n_obs, dtype=bool)
        m[np.where(mask)[0][np.asarray(groups) == lab]] = True
        s = float(A.layers["spliced"][m].sum())
        u = float(A.layers["unspliced"][m].sum())
        if s + u <= 0:
            continue
        rows.append({"label": lab, "n_cells": int(m.sum()),
                     "spliced_fraction": s / (s + u), "unspliced_fraction": u / (s + u),
                     "spliced_counts": s, "unspliced_counts": u})
    if not rows:
        return
    F, plt = ctx.figure, ctx.plot()
    df = pd.DataFrame(rows).set_index("label")
    df = df.loc[_by_size(df["n_cells"].to_dict())]
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.7, 0.19 * len(df) + 1.0)),
                           layout="constrained")
    y = np.arange(len(df))
    _bar_grid(ax)
    ax.barh(y, df["spliced_fraction"], color=F.CATEGORY_COLOURS[0], label="spliced", height=0.74,
            zorder=2)
    ax.barh(y, df["unspliced_fraction"], left=df["spliced_fraction"],
            color=F.CATEGORY_COLOURS[1], label="unspliced", height=0.74, zorder=2)
    # THE NUMBER THE PANEL IS ABOUT, WRITTEN ON THE BAR. Stacked to one, every bar is the same
    # length and the only thing that varies is an internal boundary - which is a position a reader
    # has to estimate against a gridline. The unspliced fraction is what the caption asks them to
    # judge, so it is printed where they are judging it.
    for yy, sf, uf in zip(y, df["spliced_fraction"], df["unspliced_fraction"]):
        ax.text(min(sf + uf / 2, 0.96), yy, f"{100 * uf:.0f}%", ha="center", va="center",
                fontsize=5.5, color=F.INK, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(_short(F, df.index))
    ax.invert_yaxis()
    _fraction_axis(ax)
    ax.set_xlabel("fraction of spliced + unspliced counts")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    _annotate_n(ax, y, df["n_cells"])
    # NOT `legend_outside`, AND THE REASON IS THE COLUMN BESIDE IT. The shared placement is the
    # right-hand margin, which is where this panel writes n - two things in one margin, drawn on
    # top of each other. A two-key legend is one line of text, so it goes above the axes, which is
    # outside the data exactly as the convention requires and costs no width at all.
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.005), ncol=2, frameon=False,
              handlelength=1.1, handletextpad=0.4, columnspacing=1.4, markerscale=1)
    _fit_width(fig, F.SINGLE)
    ctx.emit_figure(
        "F1_proportions", fig,
        caption=("Spliced and unspliced fraction of counts in each population, most cells first; "
                 "the unspliced percentage is printed on each bar and n is the cells it was "
                 "summed over. The unspliced fraction is the material velocity is inferred from: "
                 "a population near zero has no kinetic signal to fit, whatever arrows are drawn "
                 "over it. Fractions are of counts, not of cells. Annotator sentinels are not "
                 "shown as populations. Axis names are shortened to their shortest unambiguous "
                 "tail; the full labels are in the table beside this panel."),
        source=df)


def _fig_field(ctx, basis, label_key, colours):
    """The headline field, as a stream and as discrete arrows - one grid, one scale, one frame."""
    import numpy as np
    import pandas as pd
    A = ctx.adata
    F, plt = ctx.figure, ctx.plot()
    xy = np.asarray(A.obsm[f"X_{basis}"])[:, :2]
    v = np.asarray(A.obsm[f"velocity_{basis}"])[:, :2]
    labels = A.obs[label_key].astype(str).values if (label_key and label_key in A.obs) else None
    d = {"barcode": A.obs_names.astype(str), "x": xy[:, 0], "y": xy[:, 1],
         "vx": v[:, 0], "vy": v[:, 1]}
    if labels is not None:
        d["label"] = labels
    src = pd.DataFrame(d).set_index("barcode")

    gx, gy, U, V, mass = _velocity_on_grid(xy, v, n=50)
    # WHERE THERE ARE TOO FEW CELLS TO AVERAGE, NOTHING IS DRAWN. The threshold is a percentile of
    # the node mass rather than an absolute, because the mass scale depends on the kernel width,
    # which depends on the layout's own units - an absolute cut-off would mean something different
    # on every dataset.
    thin = mass < np.percentile(mass, 60)
    speed = np.sqrt(U ** 2 + V ** 2)
    lo, hi = float(np.nanmin(xy[:, 0])), float(np.nanmax(xy[:, 0]))
    lo2, hi2 = float(np.nanmin(xy[:, 1])), float(np.nanmax(xy[:, 1]))
    padx, pady = 0.04 * (hi - lo or 1), 0.04 * (hi2 - lo2 or 1)

    for kind, cap in (
        ("F2_stream",
         "RNA velocity on the {b} embedding, as a stream. Lines follow the field and are "
         "INTERPOLATED between cells; line width is the local speed of the projected field. "
         "Arrow length is a direction, never a rate in real time, and lengths are not comparable "
         "between datasets. Populations are named where they sit rather than in a legend; the "
         "names are shortened to their shortest unambiguous tail and given in full in the table "
         "beside this panel."),
        ("F3_grid",
         "The same field as discrete arrows on a grid - the same grid, the same kernel and the "
         "same axes as the stream panel, so any difference between the two is the drawing and "
         "not the computation. Each arrow averages the cells around its node and does not "
         "interpolate between them, so a region with too few cells stays empty - which is why "
         "this panel and the stream can disagree, and why both are shown. Arrow length is scaled "
         "to the node spacing and is a direction, not a rate."),
    ):
        try:
            fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE), layout="constrained")
            _scatter_cells(ax, xy, labels, colours, F, alpha=0.85)
            if kind == "F2_stream":
                Um, Vm = U.copy(), V.copy()
                Um[thin] = np.nan
                Vm[thin] = np.nan
                lw = 0.25 + 0.85 * (speed / (np.nanmax(speed) or 1.0))
                ax.streamplot(gx, gy, Um, Vm, color=F.INK, linewidth=lw, density=1.3,
                              arrowsize=0.55, arrowstyle="-|>", zorder=4,
                              broken_streamlines=True)
            else:
                step = 3                      # 17 x 17 arrows on an 85 mm panel
                sl = (slice(None, None, step), slice(None, None, step))
                Xg, Yg = np.meshgrid(gx, gy)
                keep = ~thin[sl]
                spacing = float(gx[1] - gx[0]) * step
                # LENGTH IS SET BY THE NODE SPACING, not by the raw vector magnitude, and off the
                # 90th percentile rather than the median: projected speed is heavy-tailed, so a
                # median scaling drew the fastest tenth of the nodes three spacings long, across
                # their neighbours, and the panel became a hairball exactly where the field is
                # strongest. At the 90th only that tenth reaches a full spacing.
                fast = float(np.nanpercentile(speed[sl][keep], 90)) if keep.any() else 0.0
                q = (fast / spacing) if fast > 0 else 1.0
                ax.quiver(Xg[sl][keep], Yg[sl][keep], U[sl][keep], V[sl][keep],
                          angles="xy", scale_units="xy", scale=q, width=0.0042,
                          headwidth=4.2, headlength=4.6, headaxislength=4.0,
                          color=F.INK, zorder=4)
            ax.set_xlim(lo - padx, hi + padx)
            ax.set_ylim(lo2 - pady, hi2 + pady)
            named = _place_labels(ax, F, xy, labels, colours, ctx.sentinels) \
                if (labels is not None and colours) else []
            _clean(ax, F, basis)
            if labels is not None and colours and not named:
                import matplotlib.lines as ml
                h = [ml.Line2D([], [], marker="o", ls="", ms=2.5, color=c,
                               label=(f"{l} (not a cell type)" if c == F.GREY else l))
                     for l, c in sorted(colours.items())]
                F.legend_outside(fig, ax, h, _short(F, [x.get_label() for x in h]),
                                 ncol=1 if len(h) <= 14 else 2)
            _fit_width(fig, F.SINGLE)
            ctx.emit_figure(kind, fig, caption=cap.format(b=basis), source=src)
        except Exception as e:                                            # noqa: BLE001
            ctx.log(f"    {kind} not drawn: {e}")


def _fig_confidence(ctx, basis, mask, groups, colours):
    """Where the field is trustworthy, on the map and as a distribution per population."""
    import numpy as np
    import pandas as pd
    A = ctx.adata
    F, plt = ctx.figure, ctx.plot()
    conf = np.asarray(A.obs["velocity_confidence"], dtype=float)
    length = np.asarray(A.obs["velocity_length"], dtype=float)
    d = {"barcode": A.obs_names.astype(str), "velocity_confidence": conf,
         "velocity_length": length}
    if groups is not None:
        lab = np.full(A.n_obs, "", dtype=object)
        lab[np.asarray(mask)] = groups
        d["label"] = lab
    src = pd.DataFrame(d).set_index("barcode")

    xy = np.asarray(A.obsm[f"X_{basis}"])[:, :2]
    has_groups = groups is not None and len(groups)
    order = []
    if has_groups:
        gi = np.asarray(groups)
        counts = {l: int((gi == l).sum()) for l in set(gi)}
        order = _by_size(counts)
    # THE MAP IS SQUARE AND THE BOXES ARE AS TALL AS THEY HAVE ROWS. One figsize for both put a
    # square map and a fourteen-row box panel in boxes of the same shape, so whichever needed
    # more height starved the other; `width_ratios` keeps the map square at 85 mm-equivalent and
    # gives the rest to the distributions.
    h = max(F.SINGLE * 0.92, 0.215 * len(order) + 1.0) if has_groups else F.SINGLE * 0.92
    fig, axs = plt.subplots(1, 2 if has_groups else 1,
                            figsize=(F.DOUBLE if has_groups else F.SINGLE, h),
                            squeeze=False, layout="constrained",
                            gridspec_kw={"width_ratios": [1.0, 1.15]} if has_groups else None)
    ax = axs[0][0]
    o = _draw_order(len(xy))
    pts = ax.scatter(xy[o, 0], xy[o, 1], c=conf[o], s=_point_size(len(xy)), cmap="RdYlBu_r",
                     vmin=0, vmax=1, linewidths=0, rasterized=True)
    _clean(ax, F, basis)
    ax.set_title("per cell, on the layout", loc="left")
    cb = fig.colorbar(pts, ax=ax, fraction=0.045, pad=0.02, shrink=0.82,
                      ticks=[0, 0.25, 0.5, 0.75, 1])
    cb.set_label("velocity confidence")
    cb.outline.set_visible(False)

    if has_groups:
        ax2 = axs[0][1]
        sub = conf[np.asarray(mask)]
        data = [sub[gi == l] for l in order]
        y = np.arange(1, len(order) + 1)
        _bar_grid(ax2)
        bp = ax2.boxplot(data, vert=False, widths=0.66, patch_artist=True, showfliers=False,
                         medianprops=dict(color=F.INK, lw=0.9),
                         whiskerprops=dict(lw=0.6), capprops=dict(lw=0.6), zorder=2)
        for patch, l in zip(bp["boxes"], order):
            patch.set_facecolor((colours or {}).get(l, F.GREY))
            patch.set_edgecolor(F.INK)
            patch.set_linewidth(0.5)
        ax2.set_yticks(y)
        ax2.set_yticklabels(_short(F, order))
        ax2.set_xlabel("velocity confidence")
        _fraction_axis(ax2)
        # THE LINE NEEDS NO LABEL HERE: 0.5 is one of the axis's own ticks, and the note that used
        # to name it was drawn above the axes, straight through the panel title.
        ax2.axvline(0.5, color=F.INK, ls="--", lw=0.6, zorder=3)
        ax2.invert_yaxis()
        ax2.spines["left"].set_visible(False)
        ax2.tick_params(axis="y", length=0)
        ax2.set_title("per population, most cells first", loc="left")
        _annotate_n(ax2, y, [len(x) for x in data])
    _fit_width(fig, F.DOUBLE if has_groups else F.SINGLE)
    ctx.emit_figure(
        "F4_confidence", fig,
        caption=("Velocity confidence: the agreement between a cell's own velocity vector and "
                 "those of its neighbours. Low values mean the arrows in that region disagree "
                 "with each other, so the field there is unresolved rather than pointing "
                 "somewhere. Read the headline panel only where this one is high; the dashed "
                 "line marks 0.5. Both panels run 0 to 1. Cells are drawn in a fixed random "
                 "order, so no value is systematically painted over another, and n is the cells "
                 "in each box - a box over tens of cells and one over tens of thousands are the "
                 "same width."),
        source=src)


def _fig_phase(ctx, genes, label_key, colours):
    """Per-gene unspliced against spliced - the evidence the model fitted anything."""
    import numpy as np
    import pandas as pd
    A = ctx.adata
    genes = [g for g in genes if g in A.var_names][:6]
    if not genes:
        return
    F, plt = ctx.figure, ctx.plot()
    labels = A.obs[label_key].astype(str).values if (label_key and label_key in A.obs) else None
    rows = {"barcode": A.obs_names.astype(str)}
    if labels is not None:
        rows["label"] = labels
    cols = {}
    for g in genes:
        j = list(A.var_names).index(g)
        for lay, nm in (("Ms", "spliced_moment"), ("Mu", "unspliced_moment")):
            if lay in A.layers:
                col = A.layers[lay][:, j]
                col = (col.toarray().ravel() if hasattr(col, "toarray")
                       else np.asarray(col).ravel())
                rows[f"{g}_{nm}"] = col
                cols[(g, lay)] = col
    src = pd.DataFrame(rows).set_index("barcode")
    if not cols:
        ctx.log("    F5_phase_portraits not drawn: no Ms/Mu moments on the object")
        return
    try:
        # NO EMPTY COLUMN, AND THE WIDTH FOLLOWS THE COUNT. Three columns were fixed, so a fit
        # that ranked one gene drew it in the left third of a 174 mm figure beside two blank
        # cells - and a blank cell is a panel a reader looks for.
        ncol = min(3, len(genes))
        nrow = (len(genes) + ncol - 1) // ncol
        wide = max(F.SINGLE, F.DOUBLE * ncol / 3)
        # constrained_layout, because a title in row 2 lands on row 1's x-axis label otherwise -
        # which is how a grid of panels turns into a grid of overlapping text.
        fig, axs = plt.subplots(nrow, ncol, figsize=(wide, 1.95 * nrow), squeeze=False,
                                layout="constrained")
        o = _draw_order(A.n_obs)
        s = _point_size(A.n_obs)
        for i, (ax, g) in enumerate(zip(axs.ravel(), genes)):
            ms, mu = cols.get((g, "Ms")), cols.get((g, "Mu"))
            if ms is None or mu is None:
                ax.set_visible(False)
                continue
            from matplotlib.colors import to_rgba_array
            c = (to_rgba_array([colours.get(str(l), F.GREY) for l in labels])[o]
                 if (labels is not None and colours) else F.CATEGORY_COLOURS[0])
            ax.scatter(ms[o], mu[o], c=c, s=s, linewidths=0, alpha=0.8, rasterized=True)
            # THE STEADY-STATE LINE, WHICH THE CAPTION'S WHOLE CLAIM RESTS ON. "A gene above the
            # steady-state relation is being induced" is unreadable without the relation drawn:
            # the fitted ratio is in var, so it is drawn from the fit rather than eyeballed.
            gcol = next((c_ for c_ in ("velocity_gamma", "fit_gamma") if c_ in A.var), None)
            gam = float(A.var.loc[g, gcol]) if gcol else float("nan")
            if np.isfinite(gam):
                off = (float(A.var.loc[g, "velocity_offset"])
                       if "velocity_offset" in A.var else 0.0)
                xs = np.array([0.0, float(np.nanmax(ms))])
                ax.plot(xs, gam * xs + off, ls="--", lw=0.7, color=F.INK, zorder=3,
                        label="steady state" if i == 0 else None)
            ax.set_title(g, loc="left")
            ax.margins(x=0.02, y=0.04)
            if i % ncol == 0:
                ax.set_ylabel("unspliced (Mu)")
            if i // ncol == nrow - 1 or i + ncol >= len(genes):
                ax.set_xlabel("spliced (Ms)")
            ax.tick_params(labelsize=5.5)
        for ax in axs.ravel()[len(genes):]:
            ax.set_visible(False)
        if labels is not None and colours:
            import matplotlib.lines as ml
            h = [ml.Line2D([], [], marker="o", ls="", ms=2.5, color=c,
                           label=(f"{l} (not a cell type)" if c == F.GREY else l))
                 for l, c in sorted(colours.items())]
            h.append(ml.Line2D([], [], ls="--", lw=0.7, color=F.INK, label="steady state"))
            F.legend_outside(fig, axs[0][ncol - 1], h,
                             _short(F, [x.get_label() for x in h[:-1]]) + ["steady state"],
                             ncol=1)
        _fit_width(fig, wide)
        ctx.emit_figure(
            "F5_phase_portraits", fig,
            caption=("Phase portraits for the highest-scoring velocity genes: unspliced against "
                     "spliced abundance, one point per cell, drawn in a fixed random order. The "
                     "dashed line is the fitted steady-state relation for that gene. A gene above "
                     "it is being induced and one below is being repressed; that residual, summed "
                     "over genes, IS the velocity vector. A cloud with no structure means the "
                     "gene contributed nothing, whatever its rank. Each panel is scaled to its "
                     "own gene - abundances are not comparable between panels."),
            source=src)
    except Exception as e:                                                # noqa: BLE001
        ctx.log(f"    F5_phase_portraits not drawn: {e}")


def _fig_transitions(ctx, rows, colours):
    """Directed population-to-population flow - the stream, in numbers."""
    import numpy as np
    import pandas as pd
    if not rows:
        return
    F, plt = ctx.figure, ctx.plot()
    full = pd.DataFrame(rows).set_index("from")
    top = 20
    df = pd.DataFrame(rows).sort_values("confidence", ascending=False).head(top)
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.7, 0.185 * len(df) + 0.95)),
                           layout="constrained")
    y = np.arange(len(df))
    _bar_grid(ax)
    ax.barh(y, df["confidence"], height=0.74, zorder=2,
            color=[(colours or {}).get(f, F.CATEGORY_COLOURS[0]) for f in df["from"]])
    ax.set_yticks(y)
    ax.set_yticklabels(_short(F, [f"{a} -> {b}" for a, b in zip(df["from"], df["to"])]))
    ax.invert_yaxis()
    _fraction_axis(ax)
    ax.set_xlabel("transition confidence")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    _fit_width(fig, F.SINGLE)
    ctx.emit_figure(
        "F6_transitions", fig,
        caption=(f"Directed transitions between populations, from the velocity graph, strongest "
                 f"first - the {len(df)} strongest of {len(full)} that survived, all of them in "
                 f"the table beside this panel. Bars are coloured by the population the "
                 f"transition leaves and the axis runs the full 0 to 1 of the confidence. This "
                 f"is the quantitative form of the stream panel: a direction visible there and "
                 f"absent here is a direction within a population, not between them. Both halves "
                 f"of each pair are shortened to their shortest unambiguous tail."),
        source=full)


def _fig_pseudotime(ctx, basis):
    import numpy as np
    import pandas as pd
    A = ctx.adata
    F, plt = ctx.figure, ctx.plot()
    pt = np.asarray(A.obs["velocity_pseudotime"], dtype=float)
    src = pd.DataFrame({"barcode": A.obs_names.astype(str),
                        "velocity_pseudotime": pt}).set_index("barcode")
    xy = np.asarray(A.obsm[f"X_{basis}"])[:, :2]
    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.98), layout="constrained")
    o = _draw_order(len(xy))
    pts = ax.scatter(xy[o, 0], xy[o, 1], c=pt[o], s=_point_size(len(xy)), cmap="viridis",
                     vmin=0, vmax=1, linewidths=0, rasterized=True)
    _clean(ax, F, basis)
    cb = fig.colorbar(pts, ax=ax, fraction=0.045, pad=0.02, shrink=0.82,
                      ticks=[0, 0.25, 0.5, 0.75, 1])
    cb.outline.set_visible(False)
    cb.set_label("velocity pseudotime (rank, 0 to 1)")
    _fit_width(fig, F.SINGLE)
    ctx.emit_figure(
        "F7_pseudotime", fig,
        caption=("Velocity pseudotime: a diffusion ordering computed on the velocity graph, with "
                 "the root inferred from where the arrows point rather than chosen by hand. It is "
                 "an ORDER, not elapsed time - the scale is 0 to 1 by construction and the "
                 "distance between two values means nothing - and it rests on more assumptions "
                 "than the arrows do: the published single-nucleus validation of velocity is "
                 "directional and did not extend to a pseudotime derived from it. Cells are drawn "
                 "in a fixed random order."),
        source=src)


def _fig_drivers(ctx, var_df, cols):
    import numpy as np
    if not cols or var_df is None or not len(var_df):
        return
    F, plt = ctx.figure, ctx.plot()
    key = cols[0]
    d = var_df[list(cols)].dropna(subset=[key]).sort_values(key, ascending=False).head(25)
    if not len(d):
        return
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.7, 0.14 * len(d) + 0.95)),
                           layout="constrained")
    y = np.arange(len(d))
    val = np.asarray(d[key], dtype=float)
    # A DOT, NOT A BAR, AND THE REASON IS THE DATA. The twenty-five top-ranked genes of a real fit
    # differ in the third decimal: as bars from zero, five sixths of every bar is identical ink
    # and the ranking the panel exists to show is invisible. A bar has to start at zero to be
    # honest; a dot carries no such claim, so the axis can be the range the scores actually
    # occupy.
    lo, hi = float(np.nanmin(val)), float(np.nanmax(val))
    pad = 0.08 * (hi - lo) if hi > lo else max(abs(hi), 1.0) * 0.1
    left = lo - pad
    _bar_grid(ax)
    # A LEADER ACROSS THE WHOLE PANEL, NOT A STEM FROM THE LEFT EDGE. A stem drawn from the axis
    # minimum reads as a bar from a baseline, and this axis has no baseline - the left edge is
    # wherever the 25th score happened to fall. A dotted rule spanning the panel is a guide from
    # the gene's name to its dot and cannot be read as a length.
    ax.hlines(y, left, hi + pad, color="#E0E0E0", lw=0.5, ls=(0, (1, 2)), zorder=1)
    ax.scatter(val, y, s=13, color=F.CATEGORY_COLOURS[2], zorder=3, linewidths=0)
    ax.set_yticks(y)
    ax.set_yticklabels(d.index)
    ax.invert_yaxis()
    ax.set_xlim(left, hi + pad)
    ax.set_xlabel(str(key).replace("_", " "))
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    _fit_width(fig, F.SINGLE)
    ctx.emit_figure(
        "F8_drivers", fig,
        caption=(f"The genes carrying the field, ranked by `{key}`, highest first. These are the "
                 f"genes whose unspliced/spliced residual contributes most to the velocity "
                 f"vectors; a high rank means a gene drove the result, not that it is "
                 f"biologically important. THE AXIS DOES NOT START AT ZERO - it spans the range "
                 f"the top 25 scores occupy, because a ranked score is a position and not a "
                 f"quantity of anything; read the order, not the length. Check them in the phase "
                 f"portraits before naming any of them in text."),
        source=d)


def _fig_by_population(ctx, by_label, min_confidence):
    """The per-population diagnostic pair: is there a direction, and was there signal for one?"""
    import numpy as np
    if not len(by_label) or by_label["velocity_confidence_median"].isna().all():
        return
    F, plt = ctx.figure, ctx.plot()
    d = by_label
    fig, axs = plt.subplots(1, 2, figsize=(F.DOUBLE, max(1.7, 0.20 * len(d) + 1.0)),
                            sharey=True, sharex=True, layout="constrained")
    y = np.arange(len(d))
    for ax_ in axs:
        _bar_grid(ax_)
    axs[0].barh(y, d["velocity_confidence_median"], color=F.CATEGORY_COLOURS[0], height=0.74,
                zorder=2)
    axs[0].axvline(float(min_confidence), color=F.INK, ls="--", lw=0.6, zorder=3)
    # NAMED, AND INSIDE THE AXES. min_confidence is a run parameter and can be anything, so unlike
    # the 0.5 on the confidence panel it is not readable off a tick - and drawn above the axes it
    # would sit wherever a title goes.
    axs[0].text(float(min_confidence), 0.99, f"min_confidence {float(min_confidence):g}",
                transform=axs[0].get_xaxis_transform(), ha="center", va="top",
                fontsize=5.5, color=F.INK, zorder=4,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))
    axs[0].set_xlabel("velocity confidence (median)")
    axs[1].barh(y, d["unspliced_fraction"], color=F.CATEGORY_COLOURS[1], height=0.74, zorder=2)
    axs[1].set_xlabel("unspliced fraction of fitted counts")
    # BOTH PANELS ARE FRACTIONS AND BOTH RUN 0 TO 1. Left to themselves they auto-scaled to their
    # own maxima - confidence to 0.75, the unspliced fraction to 0.35 - and the right-hand bars
    # came out nearly as long as the left-hand ones at half the value. The pairing IS the panel's
    # question, and two axes with different rulers cannot be paired by eye.
    _fraction_axis(axs[0])
    axs[0].set_yticks(y)
    axs[0].set_yticklabels(_short(F, d.index))
    axs[0].invert_yaxis()
    for ax_ in axs:
        ax_.spines["left"].set_visible(False)
        ax_.tick_params(axis="y", length=0)
    if "n_cells" in d:
        _annotate_n(axs[1], y, d["n_cells"])
    _fit_width(fig, F.DOUBLE)
    ctx.emit_figure(
        "F9_by_population", fig,
        caption=("Per population, most cells first, side by side: how much the arrows agree with "
                 "their neighbours, and how much unspliced signal there was to build them from. "
                 "BOTH AXES ARE FRACTIONS AND BOTH RUN 0 TO 1, so the two halves can be read "
                 "against each other; n is the cells behind each row. The pairing is the point - "
                 "a population low on both has no velocity to read, and a population low on the "
                 "left but high on the right has signal the model could not resolve into a "
                 "direction. The dashed line is the run's min_confidence. Annotator sentinels are "
                 "not shown as populations."),
        source=d)


# ---------------------------------------------------------------------------------------- run

def run(ctx):
    import numpy as np
    import pandas as pd
    import scanpy as sc
    import scvelo as scv

    C = ctx.config
    if C["mode"] not in MODES:
        return ctx.refuse("velocity", f"mode={C['mode']!r} is not one of {', '.join(MODES)}. An "
                                      f"unrecognised mode is passed straight through and produces "
                                      f"a plausible field from a model nobody chose.")
    n_jobs = int(C["n_jobs"]) or ctx.cores
    # THE JOURNAL CONVENTIONS, APPLIED BEFORE ANYTHING IS FITTED. Not for the settings' sake - it
    # is the cheapest possible check that this environment can draw at all, and the alternative is
    # discovering a broken matplotlib backend after an hour of moments on a real cohort.
    ctx.plot()
    A = ctx.adata
    n0, g0 = A.n_obs, A.n_vars
    ctx.log(f"scvelo {scv.__version__}, mode {C['mode']}, {n_jobs} worker(s)")
    ctx.log(f"{n0:,} cells x {g0:,} genes")

    # ------------------------------------------------------------ is there anything to fit
    #
    # An object that has been through QC, annotation and integration has almost certainly lost its
    # spliced/unspliced layers - they come from the aligner and nothing downstream carries them.
    # But the aligner's output is usually still on disk, and the upstream tools recorded where
    # their own inputs were. So before refusing, LOOK - through the host, which is the party
    # holding that chain.
    have = set(ctx.layers())
    sourced_note = ""
    if not {"spliced", "unspliced"} <= have:
        ctx.log(f"spliced/unspliced are not on the object (layers: {sorted(have) or 'none'})")
        ok, sourced_note = ctx.source_layers(
            ("spliced", "unspliced"),
            extra_roots=[C["spliced_source"]] if C["spliced_source"] else (),
            min_match=C["min_barcode_match"])
        if not ok:
            ctx.caveat("Nothing was fitted.")
            return ctx.refuse(
                "velocity",
                "Spliced/unspliced counts come from the ALIGNER. They cannot be derived from a "
                "counts matrix, and the only route is to re-quantify from FASTQ or BAM in an "
                "intron-aware mode.\n"
                f"  Present layers: {sorted(have) or 'none'}.\n"
                f"  Searched {len(ctx.searched)} lead(s) taken from the upstream chain"
                + (", AND THE WALK DID NOT FINISH - it hit its depth or visit limit, so this is "
                   "a fact about the search and not about your project" if ctx.search_exhausted
                   else "")
                + ":\n    " + "\n    ".join(ctx.searched[:8] or ["(none recorded)"])
                + (f"\n  Candidates opened but not usable: {sourced_note}" if sourced_note else "")
                + "\n  Fix: --search <dir> to point at the aligner output, or "
                  "--params '{\"spliced_source\": \"<dir>\"}'.")
        have = set(ctx.layers())
        ctx.log(f"sourced from beside the object: {sourced_note}")

    s_tot = float(A.layers["spliced"].sum())
    u_tot = float(A.layers["unspliced"].sum())
    u_frac = u_tot / (s_tot + u_tot) if (s_tot + u_tot) else 0.0
    ctx.log(f"unspliced is {100 * u_frac:.1f}% of spliced+unspliced counts")
    if u_tot <= 0:
        ctx.caveat("Nothing was fitted.")
        return ctx.refuse(
            "velocity",
            "layers['unspliced'] sums to zero. The layer exists but carries no counts, which "
            "usually means the quantification wrote the slot without an intron-aware reference. "
            "There is no signal to fit.")

    # ------------------------------------------------------------ start from COUNTS
    # The model is fitted on spliced/unspliced abundances, and X is used only for the HVG
    # selection and the PCA the neighbour graph is built on. An upstream tool typically delivers
    # lognormalised X with the counts kept in a layer - log1p applied to that would be a SECOND
    # log, which produces a perfectly plausible embedding and no error anywhere.
    counts_layer = ctx.keys.get("counts")
    if counts_layer and counts_layer in have:
        A.X = A.layers[counts_layer].copy()
        x_src = f"layers[{counts_layer!r}], as named by the host"
    else:
        xmax = float(A.X.max())
        if xmax < 30:
            ctx.caveat("Nothing was fitted.")
            return ctx.refuse(
                "velocity",
                f"X has maximum {xmax:.2f}, which is the range of log1p data rather than of "
                f"counts, and no counts layer was named. Preprocessing it again would apply a "
                f"second log transform - which produces a plausible embedding and reports no "
                f"error.\n  Fix: --counts-layer <name>. Layers present: {sorted(have)}.")
        x_src = f"X as delivered (max {xmax:.0f}, count-like)"
    ctx.log(f"counts from {x_src}")

    # ------------------------------------------------------------ the fit
    # scvelo 0.3 REMOVED gene selection and the log transform from filter_and_normalize; see
    # upstream.defaults_changed. Both are done here, explicitly, where they can be counted.
    scv.pp.filter_and_normalize(A, min_shared_counts=int(C["min_shared_counts"]))
    sc.pp.log1p(A)
    n_top = min(int(C["n_top_genes"]), A.n_vars)
    sc.pp.highly_variable_genes(A, n_top_genes=n_top, subset=True)
    g1 = A.n_vars
    # filter_and_normalize selects genes, not cells - this asserts that rather than trusting it.
    # Every obs column written below is aligned to the object's own names.
    if A.n_obs != n0:
        raise RuntimeError(
            f"gene selection changed the CELL count, {n0:,} -> {A.n_obs:,}. Gene selection must "
            f"not drop cells.")
    ctx.log(f"fitted on {g1:,} of {g0:,} genes "
            f"(min_shared_counts={C['min_shared_counts']}, n_top_genes={n_top})")
    if g1 < 50:
        ctx.caveat("Nothing was fitted.")
        return ctx.refuse(
            "velocity",
            f"only {g1} of {g0} genes had at least {C['min_shared_counts']} shared "
            f"spliced+unspliced counts. A velocity fitted on that many genes is noise. Lower "
            f"min_shared_counts if the libraries are shallow, but a fit this thin is usually "
            f"telling you the unspliced quantification is sparse.")

    scv.pp.moments(A, n_pcs=int(C["n_pcs"]), n_neighbors=int(C["n_neighbors"]))
    if C["mode"] == "dynamical":
        ctx.log("fitting the dynamical model - this is the slow mode, minutes to hours")
        scv.tl.recover_dynamics(A, n_jobs=n_jobs)
    scv.tl.velocity(A, mode=C["mode"])
    scv.tl.velocity_graph(A, n_jobs=n_jobs)
    scv.tl.velocity_confidence(A)
    scv.tl.velocity_pseudotime(A)
    if C["mode"] == "dynamical":
        scv.tl.latent_time(A)

    conf = np.asarray(A.obs["velocity_confidence"], dtype=float)
    length = np.asarray(A.obs["velocity_length"], dtype=float)
    med_conf = float(np.nanmedian(conf))
    ctx.log(f"velocity_confidence: median {med_conf:.3f}, "
            f"{100 * float(np.mean(conf < 0.3)):.1f}% of cells below 0.3")

    # ------------------------------------------------------------ where to draw the arrows
    try:
        basis, why_basis = _pick_basis(ctx, C["basis"])
    except ValueError as e:
        ctx.caveat("Nothing was fitted onto an embedding.")
        return ctx.refuse("velocity arrows", str(e))
    if basis is None:
        ctx.log(f"computing a UMAP for the arrows (min_dist={C['min_dist']})")
        sc.pp.neighbors(A, n_neighbors=int(C["n_neighbors"]), n_pcs=int(C["n_pcs"]))
        sc.tl.umap(A, min_dist=float(C["min_dist"]))
        basis, why_basis = "umap", f"computed here at min_dist={C['min_dist']}"
    ctx.log(f"basis: X_{basis}  ({why_basis})")
    scv.tl.velocity_embedding(A, basis=basis)

    # ------------------------------------------------------------ per label, sentinels aside
    #
    # A SENTINEL IS NOT A POPULATION. The five-file version of this plugin put every sentinel in
    # this table with an `is_sentinel` column and sorted them last, which is a per-population
    # median velocity confidence computed for the annotator's refusal to call a cell type - and in
    # a results table that reads exactly like a cell type whose field could not be resolved.
    # `ctx.populations()` is the host's one answer and attaches the caveat itself.
    label_key = ctx.keys.get("label")
    mask, groups = ctx.populations()
    rows = []
    if groups is not None and len(groups):
        idx = np.where(np.asarray(mask))[0]
        for lab in sorted(set(groups)):
            sel = idx[np.asarray(groups) == lab]
            m = np.zeros(A.n_obs, dtype=bool)
            m[sel] = True
            su = float(A.layers["Mu"][m].sum()) if "Mu" in A.layers else float("nan")
            ss = float(A.layers["Ms"][m].sum()) if "Ms" in A.layers else float("nan")
            rows.append({
                "label": lab,
                "n_cells": int(m.sum()),
                "velocity_confidence_median": float(np.nanmedian(conf[m])),
                "velocity_length_median": float(np.nanmedian(length[m])),
                "velocity_pseudotime_median":
                    float(np.nanmedian(A.obs["velocity_pseudotime"].values[m])),
                "unspliced_fraction": (su / (ss + su)) if (ss + su) > 0 else float("nan"),
            })
        rows.sort(key=lambda r: -r["n_cells"])
    by_label = pd.DataFrame(rows)
    if len(by_label):
        by_label = by_label.set_index("label")
    ctx.emit_table("velocity_by_label", by_label)

    # ------------------------------------------------------------ directed label transitions
    # Not "these cells move" but "this population moves TOWARD that one". It is also the honest
    # place to see that a direction is ABSENT - a symmetric transition matrix means the arrows
    # carry no between-label signal.
    trans_note, trows = "", []
    if label_key and label_key in A.obs and A.obs[label_key].astype(str).nunique() > 1:
        try:
            lab_series = A.obs[label_key].astype(str)
            scv.tl.paga(A, groups=label_key)
            tr = A.uns["paga"]["transitions_confidence"]
            tr = np.asarray(tr.todense()) if hasattr(tr, "todense") else np.asarray(tr)
            cats = list(pd.Categorical(lab_series).categories)
            sent = {str(x) for x in ctx.sentinels}
            trows = [{"from": cats[i], "to": cats[j], "confidence": float(tr[i, j])}
                     for i in range(len(cats)) for j in range(len(cats))
                     if i != j and float(tr[i, j]) > 0
                     and cats[i] not in sent and cats[j] not in sent]
            trows.sort(key=lambda r: -r["confidence"])
            trans_note = (f"{len(trows)} directed label transition(s); strongest "
                          + ", ".join(f"{r['from']} -> {r['to']} ({r['confidence']:.2f})"
                                      for r in trows[:3])) if trows else \
                "no directed transition between labels survived - the arrows carry within-label " \
                "structure but no between-label direction"
            ctx.log(f"transitions: {trans_note}")
        except Exception as e:                                            # noqa: BLE001
            ctx.log(f"  PAGA transitions not computed: {e}")
    # ALWAYS EMITTED, even empty. A table with a header and no rows says "no transition survived";
    # a table that is absent says the plugin declares an output it did not write, and drift
    # reported on an ordinary run is drift nobody reads.
    ctx.emit_table("velocity_transitions",
                   pd.DataFrame(trows).set_index("from") if trows
                   else pd.DataFrame(columns=["to", "confidence"],
                                     index=pd.Index([], name="from")))

    # ------------------------------------------------------------ driver genes
    if "fit_likelihood" in A.var:
        gv = A.var.sort_values("fit_likelihood", ascending=False)
        cols = [c for c in ("fit_likelihood", "fit_alpha", "fit_beta", "fit_gamma",
                            "velocity_score") if c in gv]
    else:
        if label_key and label_key in A.obs:
            try:
                scv.tl.rank_velocity_genes(A, groupby=label_key, min_corr=0.3)
            except Exception as e:                                        # noqa: BLE001
                ctx.log(f"  rank_velocity_genes skipped: {e}")
        gv = (A.var.sort_values("velocity_score", ascending=False)
              if "velocity_score" in A.var else A.var)
        cols = [c for c in ("velocity_score", "velocity_gamma", "velocity_r2") if c in gv]
    ctx.emit_table("velocity_genes", gv[cols].head(500))
    # The genes the phase portraits are drawn for: the highest-ranked by whichever score this mode
    # produced. Named here so the figure and the table cannot disagree about them.
    top_genes = list(gv.index[:6]) if cols else []

    # ------------------------------------------------------------ figures
    colours = _colours_for(ctx, A.obs[label_key].astype(str).values) \
        if label_key and label_key in A.obs else {}
    ctx.log("figures:")
    _fig_proportions(ctx, mask, groups)
    _fig_field(ctx, basis, label_key if (label_key and label_key in A.obs) else None,
               colours)
    _fig_confidence(ctx, basis, mask, groups, colours)
    _fig_phase(ctx, top_genes,
               label_key if (label_key and label_key in A.obs) else None, colours)
    _fig_transitions(ctx, trows, colours)
    _fig_pseudotime(ctx, basis)
    _fig_drivers(ctx, gv, cols)
    _fig_by_population(ctx, by_label, C["min_confidence"])

    # ------------------------------------------------------------ what the host merges
    for col in ["velocity_confidence", "velocity_length", "velocity_pseudotime"] + \
            (["latent_time"] if "latent_time" in A.obs else []):
        ctx.emit_obs(col, np.asarray(A.obs[col]))
    # The barcodes go with the array; `emit_obsm` writes them. The five-file version wrote
    # `obsm/barcodes.txt`, one file for the directory under a name nothing in the host has ever
    # looked for - so the barcodes existed and the merge went on aligning by POSITION anyway.
    ctx.emit_obsm(f"velocity_{basis}", np.asarray(A.obsm[f"velocity_{basis}"], dtype="float32"))

    # The fitted object, with its selected genes, its Ms/Mu/velocity layers and its velocity
    # graph. This is what `pseudotime` reads to orient itself, and what a user opens to plot a
    # phase portrait for a gene they care about.
    (ctx.out / "objects").mkdir(parents=True, exist_ok=True)
    f_obj = ctx.out / "objects" / "velocity.h5ad"
    A.write_h5ad(f_obj, compression="gzip")
    ctx.emit_object("velocity_h5ad", f_obj)
    ctx.log(f"wrote {f_obj.name}  ({A.n_obs:,} x {A.n_vars:,}, velocity graph included)")

    # ------------------------------------------------------------ caveats, from the data
    if sourced_note:
        ctx.caveat(
            "Spliced/unspliced counts were NOT on the input object. They were found beside it by "
            "following the provenance the upstream tools recorded, and attached BY BARCODE: "
            + sourced_note + ". Cells that matched no source carry zeros in those layers, which "
            "the fit treats as no signal - check the coverage above before reading the field.")
    if med_conf < float(C["min_confidence"]):
        ctx.status = "partial"
        ctx.caveat(
            f"MEDIAN velocity_confidence is {med_conf:.3f}, below {C['min_confidence']}. Each "
            f"cell's arrow largely disagrees with its neighbours', so the field should be read as "
            f"unresolved rather than as a direction. Do not draw a trajectory from it.")
    ctx.caveat(
        f"Fitted on {g1:,} of {g0:,} genes, selected inside this plugin from {x_src} "
        f"(min_shared_counts={C['min_shared_counts']}, n_top_genes={n_top}). No gene or cell was "
        f"removed from the merged object; the fitted layers ship as objects/velocity.h5ad rather "
        f"than being padded onto the full gene list, because a zero in a velocity layer would "
        f"assert no change where the truth is not fitted.")
    ctx.caveat(
        f"Mode {C['mode']}. Arrows are a DIRECTION: length is not a rate in real time, and "
        f"lengths from two datasets are not comparable.")
    ctx.caveat(
        f"Arrows are drawn on X_{basis} ({why_basis}), a TWO-column layout. The neighbours and "
        f"the fit use the representation, which is a different and wider space; a velocity "
        f"embedding is the projection of the fitted field onto this layout, so a projection can "
        f"make a coherent field look incoherent where the layout tore the manifold.")
    if ctx.assay == "nucleus":
        ctx.caveat(
            f"Single-NUCLEUS data, unspliced {100 * u_frac:.1f}% of counts. The high intronic "
            f"fraction is expected and helps the fit. Validated use is DIRECTIONAL - nucleus and "
            f"cell velocities correlate r 0.94-0.99 on matched populations (Sci Rep 2024) - and "
            f"that comparison did not cover a pseudotime derived from the arrows.")
    elif ctx.assay == "cell":
        ctx.caveat(
            f"Whole cells, unspliced {100 * u_frac:.1f}% of counts. For 3-prime tagging "
            f"chemistries the unspliced counts are sparse and the per-gene fits are noisy.")
    if ctx.sentinels and label_key and label_key in A.obs:
        n_sent = int(A.obs[label_key].astype(str).isin(set(ctx.sentinels)).sum())
        if n_sent:
            names = ", ".join(sorted(ctx.sentinels))
            ctx.caveat(
                f"{n_sent:,} cells carry an annotator sentinel ({names}). They were fitted like "
                f"any other cell - nothing was dropped, and they keep their per-cell "
                f"velocity_confidence, velocity_length and velocity_pseudotime - but they are not "
                f"a population, so they are absent from the per-population table, from the "
                f"population figures, and from the directed transitions.")
    if trans_note:
        ctx.caveat("Directed transitions between labels are in tables/velocity_transitions.csv. "
                   + trans_note + ".")

    ctx.headline = (f"velocity fitted on {g1:,} genes ({C['mode']}); median confidence "
                    f"{med_conf:.2f}; unspliced {100 * u_frac:.1f}% of counts")


# ----------------------------------------------------------------------------------- selftest

def selftest(ctx):
    """Prove this environment can actually FIT a velocity, before a real run is spent on it.

    WHY A FIT AND NOT A SET OF IMPORTS. Importing scvelo proves that scvelo is on the path. It
    does not prove that `scv.tl.velocity` can run, and the failures worth catching are all
    downstream of the import: a numpy that removed an alias, a pandas that dropped a method, a
    numba that will not compile the kernels, a scikit-learn whose neighbour API moved. Every one
    of those imports cleanly and dies inside the first real call - and one of them, `n_top_genes`
    reaching `normalize_per_cell` through **kwargs, is exactly how the first cluster run died.

    So this builds a small synthetic dataset with a known spliced/unspliced relationship and runs
    the complete path the plugin runs - moments, velocity, graph, confidence, pseudotime,
    embedding. It asserts SHAPES and FINITENESS, never a biological answer: the data is synthetic,
    there is no correct velocity to check against, and a selftest that asserted one would be
    testing its fixture.
    """
    import numpy as np
    import pandas as pd
    import anndata as ad
    import scanpy as sc
    import scvelo as scv

    for mod in (np, pd, sc, scv):
        ctx.log(f"  {mod.__name__:<11} {mod.__version__}")

    rng = np.random.default_rng(0)
    n, g = 600, 300

    # A synthetic ordering: cells sit on a latent axis, spliced counts follow it, and unspliced
    # counts LEAD it. That is the structure velocity is supposed to detect, so a run that produces
    # a degenerate graph on this fixture is telling us the environment is broken rather than that
    # the biology is quiet.
    t = np.linspace(0, 1, n)
    base = rng.uniform(0.5, 4.0, g)
    prog = np.outer(t, rng.normal(0, 1.5, g))
    s = rng.poisson(np.clip(np.exp(base + prog), 0.05, 300)).astype("float32")
    u = rng.poisson(np.clip(np.exp(base + prog + 0.35), 0.05, 300) * 0.4).astype("float32")

    A = ad.AnnData(X=s.copy())
    A.layers["spliced"] = s
    A.layers["unspliced"] = u
    A.obs_names = [f"cell{i}" for i in range(n)]
    A.var_names = [f"Gene{j}" for j in range(g)]
    A.obs["label"] = pd.Categorical(np.where(t < 0.5, "early", "late"))

    # THE 0.3.x SEQUENCE, and the reason this selftest exists. `filter_and_normalize` no longer
    # selects genes or takes a log, and passing n_top_genes to it raises inside
    # normalize_per_cell.
    scv.pp.filter_and_normalize(A, min_shared_counts=5)
    sc.pp.log1p(A)
    sc.pp.highly_variable_genes(A, n_top_genes=min(200, A.n_vars), subset=True)
    scv.pp.moments(A, n_pcs=15, n_neighbors=15)
    scv.tl.velocity(A, mode="stochastic")
    scv.tl.velocity_graph(A, n_jobs=1)
    scv.tl.velocity_confidence(A)
    scv.tl.velocity_pseudotime(A)

    sc.pp.neighbors(A, n_neighbors=15, n_pcs=15)
    sc.tl.umap(A)
    scv.tl.velocity_embedding(A, basis="umap")

    checks = [
        ("velocity layer", A.layers["velocity"].shape[0] == A.n_obs),
        ("velocity graph", A.uns["velocity_graph"].shape == (A.n_obs, A.n_obs)),
        ("confidence finite", np.isfinite(A.obs["velocity_confidence"].values).all()),
        ("pseudotime finite", np.isfinite(A.obs["velocity_pseudotime"].values).all()),
        ("embedding shape", A.obsm["velocity_umap"].shape == (A.n_obs, 2)),
        # A velocity matrix that is entirely NaN is what a broken numba backend produces, and it
        # travels all the way to a stream plot with no arrows and no error message.
        ("velocity not all-NaN", bool(np.isfinite(np.asarray(A.layers["velocity"])).any())),
        # Ms/Mu are moments of the NORMALISED, UNLOGGED spliced and unspliced layers. If a future
        # version starts logging them the fit silently changes meaning, so pin the shape here.
        ("Ms present", "Ms" in A.layers and A.layers["Ms"].shape == A.shape),
        ("Mu present", "Mu" in A.layers and A.layers["Mu"].shape == A.shape),
    ]
    bad = [name for name, ok in checks if not ok]
    for name, ok in checks:
        ctx.log(f"  {'ok  ' if ok else 'FAIL'} {name}")
    assert not bad, f"the environment cannot fit a velocity: {', '.join(bad)}"

    # THE FIGURE PATH IS PART OF THIS PLUGIN AND PART OF THE ENVIRONMENT, and it is this
    # plugin's own now rather than the wrapped tool's: the field panels are drawn from
    # `obsm[velocity_<basis>]` with matplotlib, so what has to be exercised here is
    # `_velocity_on_grid`, the stream and the quiver - none of which the fit above touches. It
    # used to call `scv.pl.velocity_embedding_grid`, which proved the tool's plotting imports and
    # nothing about the code that actually draws.
    plt = ctx.plot()
    F = ctx.figure
    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE))
    gx, gy, U, V, mass = _velocity_on_grid(A.obsm["X_umap"][:, :2],
                                           A.obsm["velocity_umap"][:, :2], n=24)
    assert U.shape == (24, 24) and np.isfinite(mass).all(), "the grid estimator returned nothing"
    thin = mass < np.percentile(mass, 60)
    Um, Vm = U.copy(), V.copy()
    Um[thin], Vm[thin] = np.nan, np.nan
    ax.streamplot(gx, gy, Um, Vm, color=F.INK, linewidth=0.4, density=1.0, arrowsize=0.55)
    Xg, Yg = np.meshgrid(gx, gy)
    ax.quiver(Xg[~thin], Yg[~thin], U[~thin], V[~thin], angles="xy", scale_units="xy",
              color=F.INK)
    _clean(ax, F, "umap")
    plt.close(fig)
    ctx.log("  ok   the grid estimator, the stream and the arrows draw")
    ctx.log(f"  fitted {A.n_obs:,} cells on {A.n_vars:,} genes")
