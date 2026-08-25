"""Regulatory activity per cell, scored against a curated prior rather than a network inferred here.

ONE FILE. Dropping it into a kernels directory is the whole installation: the host reads PLUGIN
for the manifest, builds the environment from PLUGIN["env"], and runs it through the shared
entrypoint, which applies the contract before this file sees anything.
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
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
    "inject": {"required": ["lognorm", "organism"],
               "optional": ["label"]},
    # A CAPABILITY, not a plugin name. Anything needing per-cell activity injects `activity` and
    # does not care that decoupler produced it.
    "provides": ["activity"],
    "produces": ["obsm[X_tf_activity]", "tables/activity_by_label.csv"],

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
        },
    },

    # WHAT THE WRAPPED TOOL'S OWN DOCUMENTATION SAYS, and which of its defaults are wrong for
    # this contract. In the directory shape this was a separate UPSTREAM.md that had to be kept
    # in step with the wrapper; here it is in the file it describes, which is the only place it
    # cannot drift from.
    "upstream": {
        "docs": "https://decoupler-py.readthedocs.io",
        "read": "2026-08-22",
        "defaults_changed": [
            "use_raw=False. The default follows .raw when it exists, and an object that has been "
            "through QC and annotation usually has a .raw holding PRE-FILTER counts - so the "
            "default scores a different matrix from the one the user is looking at, without "
            "erroring.",
            "verbose=False, because progress output is not a result.",
        ],
        "not_used": [
            "run_mlm and run_wsum: ULM is used alone here. decoupler's own consensus over several "
            "methods is a better answer and needs all of them run, which is a change to this "
            "plugin's declaration, not a flag.",
            "get_progeny: pathway activity is a second prior and would be a second plugin.",
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
        ],
    },

    "cannot_show": [
        "THE PRIOR DECIDES THE ANSWER. An activity score is a statement about the prior's gene "
        "set for that regulator, not a measurement of a protein.",
        "Scores are relative WITHIN this dataset and are not comparable with another dataset's.",
        "The prior is published per organism. On the wrong species it does not error - it "
        "returns a small, plausible table.",
        "THE PRIOR IS FETCHED WHEN THE RUN HAPPENS and is not pinned. Two runs against the same "
        "object, weeks apart, can score against different versions of it; the edge and regulator "
        "counts in the caveats are the only record of which one this was.",
    ],
}


def run(ctx):
    import decoupler as dc

    # NO PREREQUISITE CHECKING. `lognorm` and `organism` are declared as required injections, so
    # the host did not call this without them - and it reported precisely which was missing to
    # the planner, which is where a user can act on it.
    net = dc.get_collectri(organism=ctx.organism, split_complexes=False)
    ctx.log(f"prior: {len(net):,} edges, {net['source'].nunique():,} regulators "
            f"for {ctx.organism}")
    ctx.caveat(f"Scored against a CollecTRI prior of {len(net):,} edges over "
               f"{net['source'].nunique():,} regulators, fetched for {ctx.organism} when this run "
               f"happened. The prior is not pinned and is not a file this host can checksum, so "
               f"those two counts are the only record of which version produced this result.")
    if len(net) < ctx.config["min_edges"]:
        return ctx.refuse("activity scores",
                          f"the prior has {len(net):,} edges, below the declared minimum of "
                          f"{ctx.config['min_edges']:,}. A truncated prior returns a smaller "
                          f"answer rather than an error.")

    ctx.adata.X = ctx.X
    dc.run_ulm(mat=ctx.adata, net=net, source="source", target="target", weight="weight",
               min_n=ctx.config["min_targets"],
               use_raw=False, verbose=False)
    acts = ctx.adata.obsm["ulm_estimate"]
    ctx.emit_obsm("X_tf_activity", acts.values)

    # A SENTINEL IS NOT A POPULATION. `UNRESOLVED` is the annotator declining to call a cell
    # type; a mean activity computed for it lands in the table beside the real populations and
    # reads as a cell type with that activity. Measured on a real cohort: PBS 677295 delivered
    # `activity_by_label.csv` with an `UNRESOLVED` row over 2,139 cells, and the host's own check
    # reported it as a declaration defect. `ctx.populations()` is the host's answer to the
    # question, so every plugin gives the same one and the caveat cannot be forgotten.
    mask, groups = ctx.populations()
    if groups is not None and len(groups):
        ctx.emit_table("activity_by_label", acts[mask].groupby(groups).mean())
    else:
        ctx.emit_table("activity_by_label", acts.mean().to_frame("mean_activity"))
        ctx.caveat("No label column was named, so activity is summarised over all cells together "
                   "rather than per population.")

    ctx.headline = f"{acts.shape[1]:,} regulators scored per cell"


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

    dc.run_ulm(mat=A, net=net, source="source", target="target", weight="weight",
               use_raw=False, verbose=False)
    assert "ulm_estimate" in A.obsm, "run_ulm no longer writes obsm['ulm_estimate']"
    acts = A.obsm["ulm_estimate"]
    assert acts.shape[0] == A.n_obs, f"{acts.shape[0]} rows for {A.n_obs} cells"
    assert acts.shape[1] > 0, "no regulator was scored on data built from the prior's own targets"
    assert np.isfinite(np.asarray(acts.values, dtype=float)).all(), "non-finite activity scores"
    ctx.log(f"  scored {acts.shape[1]:,} regulators over {acts.shape[0]:,} cells")
