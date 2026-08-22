"""Ordering along a trajectory, with fate probabilities toward each terminal state.

AN ORDERING IS NOT A TIME. CellRank returns a position along a manifold, and the manifold is
whatever the embedding says it is. Which KERNEL produced the ordering decides the answer — a
velocity kernel and a connectivity kernel can order the same cells in opposite directions — so
the kernel used is recorded in the result rather than left to be inferred.
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "summary": "ordering along a trajectory, oriented by velocity where it exists",
    "when_to_use": "you have a continuum you believe is a progression and want cells ordered "
                   "along it",
    "wraps": {"tool": "cellrank", "homepage": "https://cellrank.readthedocs.io",
              "license": "BSD-3-Clause",
              "cite": "Lange et al., Nat Methods 2022 (CellRank); "
                      "Weiler et al., Nat Methods 2024 (CellRank 2)"},
    "upstream": {
        "docs": "https://cellrank.readthedocs.io",
        "read": "2026-08-22",
        "defaults_changed": [
            "The kernel is CHOSEN, not defaulted: a VelocityKernel where a velocity field exists, "
            "a ConnectivityKernel otherwise, and the choice is in the result. Two kernels can "
            "order the same cells in opposite directions.",
            "n_states is config rather than automatic. GPCCA's automatic choice is a heuristic "
            "over the eigengap and silently decides how many terminal states the biology has.",
        ],
        "not_used": [
            "CytoTRACEKernel and PseudotimeKernel-from-a-prior: both need an input this plugin is "
            "not given, and inventing one would fabricate the ordering it is meant to measure.",
            "Driver-gene ranking: it is a second question and belongs in its own plugin.",
        ],
        "gotchas": [
            "Without petsc4py/slepc4py, GPCCA falls back to a DENSE eigensolver. It is correct "
            "and on a cohort of any size not finishable - a fallback that is right and takes a "
            "week is not a fallback, so the selftest reports which route it got.",
            "Fate probabilities sum to one by construction, so a cell with no clear fate is "
            "reported as evenly split rather than as unknown.",
        ],
    },

    "inject": {"required": ["embedding"], "optional": ["velocity", "label"]},
    "provides": ["ordering"],
    "produces": ["obs[pseudotime]", "obsm[fate_probabilities]",
                 "tables/terminal_states.csv"],

    "config": {
        "n_states": {"type": "int", "default": 3, "min": 2, "max": 20,
                     "help": "how many macrostates GPCCA looks for. This decides how many "
                             "terminal states the result claims, so it is declared, not guessed"},
        "n_neighbors": {"type": "int", "default": 15, "min": 2,
                        "help": "neighbours for the transition matrix, if one must be built"},
        "velocity_weight": {"type": "float", "default": 0.8, "min": 0.0, "max": 1.0,
                            "help": "weight on the velocity kernel when a velocity field exists; "
                                    "the remainder goes to connectivity"},
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

    "cannot_show": [
        "AN ORDERING IS NOT A TIME. It is a position along a manifold, and it says nothing about "
        "how long anything took.",
        "WHICH KERNEL PRODUCED IT DECIDES THE ANSWER. A velocity kernel and a connectivity kernel "
        "can order the same cells in opposite directions; the kernel used is in the result.",
        "The ordering is only as good as the embedding it runs on. A constrained embedding "
        "constrains the trajectory.",
        "Fate probabilities sum to one, so a cell with no clear fate reads as evenly split "
        "rather than as unknown.",
    ],
}


def run(ctx):
    import numpy as np
    import cellrank as cr
    import scanpy as sc

    A = ctx.adata[ctx.real_cells()].copy()
    emb = ctx.keys["embedding"]
    if "neighbors" not in A.uns:
        sc.pp.neighbors(A, n_neighbors=ctx.config["n_neighbors"], use_rep=emb)
        ctx.log(f"built a neighbour graph on {emb}")

    has_velocity = "velocity" in A.layers and "velocity_graph" in A.uns
    if has_velocity:
        w = ctx.config["velocity_weight"]
        kern = (w * cr.kernels.VelocityKernel(A).compute_transition_matrix()
                + (1 - w) * cr.kernels.ConnectivityKernel(A).compute_transition_matrix())
        which = f"VelocityKernel({w}) + ConnectivityKernel({1 - w:.2g})"
    else:
        kern = cr.kernels.ConnectivityKernel(A).compute_transition_matrix()
        which = "ConnectivityKernel"
        ctx.caveat("No velocity field was on this object, so the ordering comes from CONNECTIVITY "
                   "alone. A connectivity kernel has no direction of its own: the ordering is a "
                   "position along the manifold and its sign is arbitrary.")
    ctx.log(f"transition matrix from {which}")

    est = cr.estimators.GPCCA(kern)
    est.compute_schur(n_components=max(ctx.config["n_states"] + 3, 6))
    est.compute_macrostates(n_states=ctx.config["n_states"],
                            cluster_key=ctx.keys.get("label"))
    est.predict_terminal_states()
    est.compute_fate_probabilities()

    fate = np.asarray(est.fate_probabilities)
    names = [str(x) for x in est.fate_probabilities.names] \
        if hasattr(est.fate_probabilities, "names") else \
        [f"state{i}" for i in range(fate.shape[1])]

    # A pseudotime from the fate structure: how far a cell is from its most likely terminal
    # state, which is an ORDER and is not a duration.
    order = 1.0 - fate.max(axis=1)
    full = np.full(ctx.adata.n_obs, np.nan, dtype="float32")
    full[np.asarray(ctx.real_cells())] = order
    ctx.emit_obs("pseudotime", full)
    # PADDED TO THE OBJECT THIS PLUGIN WAS GIVEN. `emit_obsm` requires one row per cell of
    # ctx.adata, and this ran on the subset with sentinels excluded - so the excluded rows are
    # NaN, which is "not measured", rather than 0, which is a fate probability.
    wide = np.full((ctx.adata.n_obs, fate.shape[1]), np.nan, dtype="float32")
    wide[np.asarray(ctx.real_cells())] = fate
    ctx.emit_obsm("fate_probabilities", wide)

    import pandas as pd
    ctx.emit_table("terminal_states", pd.DataFrame(
        {"terminal_state": names,
         "mean_fate_probability": fate.mean(axis=0),
         "cells_most_likely": [int((fate.argmax(axis=1) == i).sum())
                               for i in range(fate.shape[1])]}).set_index("terminal_state"))

    ctx.headline = (f"{fate.shape[1]} terminal state(s) over {A.n_obs:,} cells, "
                    f"from {which}")
    ctx.caveat(f"The ordering came from {which}. Which kernel produced it decides the answer - "
               f"a different kernel can order the same cells in the opposite direction.")
    ctx.caveat("Fate probabilities sum to one by construction, so a cell with no clear fate is "
               "reported as evenly split rather than as unknown.")


def selftest(ctx):
    """Prove the whole path, and REPORT WHICH SOLVER was used.

    The solver matters more than the shapes here: without petsc/slepc, GPCCA is correct and
    unusably slow, and a selftest that passed silently on the dense route would certify an
    environment that cannot finish a real cohort.
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
    est.compute_macrostates(n_states=3, cluster_key=None)
    est.predict_terminal_states()
    est.compute_fate_probabilities()
    fate = np.asarray(est.fate_probabilities)
    assert fate.shape[0] == n, f"fate probabilities cover {fate.shape[0]} of {n} cells"
    assert np.isfinite(fate).all(), "non-finite fate probabilities"
    assert np.allclose(fate.sum(axis=1), 1.0, atol=1e-3), \
        "fate probabilities do not sum to 1 - the estimator's contract changed"
    ctx.log(f"  {fate.shape[1]} macrostates over {n} cells, probabilities sum to 1")
    if route.startswith("DENSE"):
        ctx.log("  WARNING: the dense route is correct and does not finish on a real cohort.")
