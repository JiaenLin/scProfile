"""Regulatory activity per cell, scored against a curated prior rather than a network inferred here.

ONE FILE. Dropping it into a kernels directory is the whole installation: the host reads PLUGIN
for the manifest, builds the environment from PLUGIN["env"], and runs it through the shared
entrypoint, which applies the contract before this file sees anything.
"""

PLUGIN = {
    "version": "0.1.0",
    "summary": "regulatory activity per cell, from a curated prior",
    "when_to_use": "you want transcription-factor or pathway activity without inferring a "
                   "network from your own data",
    "wraps": {"tool": "decoupler", "homepage": "https://github.com/saezlab/decoupler-py",
              "license": "GPL-3.0",
              "cite": "Badia-i-Mompel et al., Bioinformatics Advances 2022"},

    # WHAT IT READS, BY ROLE. Never a column name: `{lognorm}` and `{label}` are resolved against
    # whatever this project happens to call them.
    "needs": {"layers": ["{lognorm}"]},
    "sees": ["{lognorm}", "{label}", "var_names"],
    "produces": ["obsm[X_tf_activity]", "tables/activity_by_label.csv"],
    "per_unit": None,
    "cost": "medium", "cores": 4,

    # The host builds this. Omit `env` entirely and the plugin runs in the host's interpreter.
    "env": {"python": "3.11",
            "pip": ["numpy==1.26.4", "pandas==2.2.3", "scanpy==1.10.4", "anndata==0.10.9",
                    "decoupler==1.8.0"]},

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
        ],
    },

    "cannot_show": [
        "THE PRIOR DECIDES THE ANSWER. An activity score is a statement about the prior's gene "
        "set for that regulator, not a measurement of a protein.",
        "Scores are relative WITHIN this dataset and are not comparable with another dataset's.",
        "The prior is published per organism. On the wrong species it does not error - it "
        "returns a small, plausible table.",
    ],
}


def run(ctx):
    import decoupler as dc

    # THE PRIOR IS CHOSEN BY ORGANISM, from what the host detected or was told. Guessing would
    # return a full table of scores computed against the wrong species - a result-shaped hole,
    # which is the third thing this plugin says it cannot show.
    if not ctx.organism:
        return ctx.refuse("activity scores",
                          "no organism was determined, and the prior is organism-specific. "
                          "Pass --organism.")

    net = dc.get_collectri(organism=ctx.organism, split_complexes=False)
    ctx.log(f"prior: {len(net):,} edges, {net['source'].nunique():,} regulators "
            f"for {ctx.organism}")

    if not ctx.keys.get("lognorm"):
        ctx.caveat("No log-normalised layer was named, so X was used as it stands. An activity "
                   "score computed on counts is not comparable with one computed on "
                   "log-normalised values.")

    ctx.adata.X = ctx.X
    dc.run_ulm(mat=ctx.adata, net=net, source="source", target="target", weight="weight",
               use_raw=False, verbose=False)
    acts = ctx.adata.obsm["ulm_estimate"]
    ctx.emit_obsm("X_tf_activity", acts.values)

    lab = ctx.obs("label")
    if lab is not None:
        ctx.emit_table("activity_by_label", acts.groupby(lab.astype(str).values).mean())
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
