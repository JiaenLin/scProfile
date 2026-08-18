#!/usr/bin/env python3
"""Prove this environment can actually fit a velocity, before a real run is spent on it.

WHY A FIT AND NOT A SET OF IMPORTS

Importing scvelo proves that scvelo is on the path. It does not prove that `scv.tl.velocity` can
run, and the failures worth catching here are all downstream of the import: a numpy that removed
an alias, a pandas that dropped a method, a numba that will not compile the kernels, a
scikit-learn whose neighbour API moved. Every one of those imports cleanly and dies inside the
first real call.

So this builds a small synthetic dataset with a known spliced/unspliced relationship and runs the
complete path the kernel runs - moments, velocity, graph, confidence, pseudotime, embedding. It
takes a few seconds and it is the difference between finding out now and finding out after an
hour of moments on a real cohort.

It asserts SHAPES and FINITENESS, never a biological answer. The data is synthetic; there is no
correct velocity to check against, and a selftest that asserted one would be testing the fixture.
"""
from __future__ import annotations

import sys


def main():
    print("velocity selftest")

    import numpy as np
    print(f"  numpy       {np.__version__}")
    import scipy
    print(f"  scipy       {scipy.__version__}")
    import pandas as pd
    print(f"  pandas      {pd.__version__}")
    import numba
    print(f"  numba       {numba.__version__}")
    import sklearn
    print(f"  scikit-learn {sklearn.__version__}")
    import anndata as ad
    print(f"  anndata     {ad.__version__}")
    import scanpy as sc
    print(f"  scanpy      {sc.__version__}")
    import scvelo as scv
    print(f"  scvelo      {scv.__version__}")

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

    # The 0.3.x sequence. filter_and_normalize no longer selects genes or takes a log - it is
    # filter_genes + normalize_per_cell - and passing n_top_genes to it raises inside
    # normalize_per_cell. This selftest exists to catch exactly that class of drift.
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
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    if bad:
        print(f"\nFAILED: {', '.join(bad)}", file=sys.stderr)
        return 1
    print("\nenvironment is usable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
