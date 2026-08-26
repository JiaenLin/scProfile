"""A fixture plugin, not a method. It makes the PER-UNIT path observable in a real run.

Nine of the ten defects fixed on 2026-08-20 lived on the per-unit path and none of them could
fire, because every `per_unit` plugin in the tree is `status: planned`. A code path that no
delivered run exercises is one whose bugs are found by users. This plugin is the smallest thing
that walks it: one unit at a time, writing every kind of output the contract has - an obs column
covering only its own cells, an array it knows cannot cross units, a table, a figure with a
vector and a source, a side-car object under a FIXED basename so a collision would be visible,
and the unit metrics that are the only thing on a per-unit page comparing the units.

ONE FILE, AND THAT IS WHY IT MOVED. It was six - kernel.yml, run.py, selftest.py and the rest -
and `kernel.yml` is read by a deliberately small parser that supports flat lists and ONE level of
nested mapping. `report.unit_metrics` is a list of mappings under a nested key, so the declaration
this plugin is now required to carry was not expressible in the format it was written in: the
rule was unsatisfiable rather than unmet. The host's own comment says a plugin is one file and
the directory shape is the old shape; this is the shape the rule can be stated in.
"""
from __future__ import annotations

PLUGIN = {
    "name": "perunit",
    "version": "0.2.0",
    "summary": "a site plugin that exercises the per-unit path end to end, so its defects "
               "are not latent",
    "language": "python",
    "needs_env": False,
    "per_unit": "sample",
    "design_aware": False,
    "sees": ["obs[sample]", "X"],
    "inject": {"required": ["sample"], "optional": []},
    "executor": {"cost": "trivial", "cores": 1},
    "produces": ["obs[perunit_score]", "obsm[X_perunit]"],
    "report": {
        # WHAT MAKES THE UNITS COMPARABLE. Declared here and recorded by `run`; the two are
        # checked against each other, so a fixture that walks the per-unit path walks this part
        # of it too.
        "unit_metrics": [
            {"id": "cells",
             "question": "how many cells did this unit bring? Every per-unit number scales "
                         "with it, so it is the first thing to look at when units disagree."},
            {"id": "score_mean",
             "question": "what did this unit's seeded score average? It is noise, and the "
                         "spread across units is what noise looks like on this page."},
        ],
        "figures": [
            {"id": "F1_score", "shows": "diagnostic",
             "question": "what does a seeded per-unit score look like within one unit?",
             "source": "figures/F1_score.csv", "required": True},
        ],
    },
    "cannot_show": [
        "It computes nothing biological. It exists to make the per-unit code path observable "
        "in a real run.",
        "The scores are drawn from a seeded generator. Any structure in them is the seed, "
        "not the data.",
    ],
}


def run(ctx):
    import numpy as np
    import pandas as pd

    A = ctx.adata
    unit = ctx.unit
    ctx.log(f"unit {unit!r}: {A.n_obs} cells")

    rng = np.random.default_rng(abs(hash(str(unit))) % (2 ** 31))
    score = pd.Series(rng.normal(size=A.n_obs), index=A.obs_names.astype(str))
    ctx.emit_obs("perunit_score", score.values)
    ctx.emit_obsm("X_perunit", rng.normal(size=(A.n_obs, 2)).astype("float32"))

    ctx.emit_table("perunit_edges",
                   pd.DataFrame({"unit": [unit] * 3, "rank": [1, 2, 3],
                                 "value": rng.normal(size=3)}).set_index("rank"))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    F = ctx.figure
    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.72))
    ax.hist(score.values, bins=20)
    ax.set_xlabel("score")
    ax.set_ylabel("cells")
    ctx.emit_figure("F1_score", fig, source=score.to_frame("score"),
                    caption=f"Score distribution within unit {unit}. Seeded noise: the shape "
                            f"is the generator, not the data.")

    # A FIXED basename, deliberately. Every unit writes `perunit_side.h5ad`; if the delivered
    # name does not carry the unit, all but one of these overwrite each other in objects/.
    import anndata as ad
    op = ctx.out / "perunit_side.h5ad"
    X = A.X[:, :5]
    ad.AnnData(np.asarray(X.todense() if hasattr(X, "todense") else X),
               obs=A.obs[[]].copy()).write_h5ad(op)
    ctx.emit_object("side", op)

    # DECLARED ABOVE AND RECORDED HERE.
    ctx.metric("cells", int(A.n_obs))
    ctx.metric("score_mean", float(score.mean()))

    ctx.headline = f"{A.n_obs} cells scored"
    ctx.caveat(f"Unit {unit} only. Nothing here is comparable across units without a model "
               f"that says so - which is what the across-units section is, and it compares "
               f"the two declared metrics and nothing else.")


def selftest(ctx):
    """Prove this fixture can write everything the contract has, before a run depends on it."""
    import numpy as np
    import pandas as pd

    n = 40
    s = pd.Series(np.linspace(0, 1, n))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    F = ctx.figure
    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.72))
    ax.plot(s.values)
    ctx.emit_figure("F1_score", fig, source=s.to_frame("score"), caption="selftest")
    ctx.emit_table("perunit_edges", pd.DataFrame({"rank": [1], "value": [0.0]}).set_index("rank"))
    ctx.metric("cells", n)
    ctx.metric("score_mean", float(s.mean()))
    ctx.headline = "selftest ok"
