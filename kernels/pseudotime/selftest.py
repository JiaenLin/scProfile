#!/usr/bin/env python3
"""Prove this environment can actually COMPUTE FATE PROBABILITIES, before a run is spent on it.

CellRank 2 is a framework over kernels of its own, and which one is used decides the answer. The
failures worth catching are downstream of the import: a scvelo whose moments API moved, a
petsc/slepc pair that will not solve, a GPCCA decomposition that needs a solver the build did not
get. Every one of those imports cleanly and dies inside the first real call - or worse, falls back
to a dense eigensolver and takes hours.

So this runs the complete path on a small synthetic object with a KNOWN progression: a latent
ordering along which unspliced leads spliced. It asserts SHAPES and FINITENESS, never a biological
answer - the ordering is the fixture, not a result.
"""
from __future__ import annotations

import sys


def main():
    print("pseudotime selftest")

    import numpy as np
    print(f"  numpy       {np.__version__}")
    import pandas as pd
    print(f"  pandas      {pd.__version__}")
    import scipy.sparse as sp
    import anndata as ad
    print(f"  anndata     {ad.__version__}")
    import scanpy as sc
    print(f"  scanpy      {sc.__version__}")
    import scvelo as scv
    print(f"  scvelo      {scv.__version__}")
    import cellrank as cr
    print(f"  cellrank    {cr.__version__}")
    try:
        import petsc4py, slepc4py                                          # noqa: F401
        print("  petsc4py/slepc4py present - GPCCA uses the sparse solver")
    except ImportError:
        print("  WARNING: no petsc4py/slepc4py. GPCCA falls back to a DENSE eigensolver, which")
        print("  is correct and much slower; on a real cohort that is hours, not minutes.")

    rng = np.random.default_rng(0)
    n, g = 300, 50
    t = np.sort(rng.uniform(0, 1, size=n))              # the planted progression
    base = np.exp(1.0 + 2.0 * np.outer(t, rng.uniform(0.2, 1.0, size=g)))
    spliced = rng.poisson(base).astype("float32")
    unspliced = rng.poisson(base * 1.4).astype("float32")   # unspliced LEADS spliced

    A = ad.AnnData(sp.csr_matrix(spliced + unspliced),
                   obs=pd.DataFrame({"t": t}, index=[f"c{i}" for i in range(n)]),
                   var=pd.DataFrame(index=[f"Gene{i:02d}" for i in range(g)]))
    A.layers["spliced"] = sp.csr_matrix(spliced)
    A.layers["unspliced"] = sp.csr_matrix(unspliced)

    scv.pp.filter_and_normalize(A, min_shared_counts=0, log=True)
    sc.pp.pca(A, n_comps=10)
    sc.pp.neighbors(A, n_neighbors=15)
    scv.pp.moments(A, n_pcs=10, n_neighbors=15)
    scv.tl.velocity(A, mode="stochastic")
    scv.tl.velocity_graph(A, n_jobs=1)

    vk = cr.kernels.VelocityKernel(A).compute_transition_matrix()
    ck = cr.kernels.ConnectivityKernel(A).compute_transition_matrix()
    comb = 0.8 * vk + 0.2 * ck
    print(f"  transition matrix {comb.transition_matrix.shape}")
    assert comb.transition_matrix.shape == (n, n), "the transition matrix is the wrong shape"

    est = cr.estimators.GPCCA(comb)
    est.compute_schur(n_components=6)
    est.compute_macrostates(n_states=3, cluster_key=None)
    print(f"  macrostates: {list(est.macrostates.cat.categories)}")
    est.predict_terminal_states()
    est.compute_fate_probabilities()
    fp = np.asarray(est.fate_probabilities)
    print(f"  fate probabilities {fp.shape}")
    assert fp.shape[0] == n, f"fate probabilities cover {fp.shape[0]} of {n} cells"
    assert np.isfinite(fp).all(), "fate probabilities contain non-finite values"
    assert np.allclose(fp.sum(axis=1), 1.0, atol=1e-3), "fate probabilities do not sum to 1"

    ptk = cr.kernels.PseudotimeKernel(A, time_key="t")
    ptk.compute_transition_matrix()
    print("  PseudotimeKernel also builds, so a run with no velocity has a route")

    print("environment is usable")
    print("pseudotime selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
