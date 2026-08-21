#!/usr/bin/env python3
"""Prove this environment can actually INFER A NETWORK, before a cohort is spent on it.

The failure this exists to catch is specific and it does not raise. pySCENIC's GRNBoost2 runs on
dask; when arboreto and the installed dask disagree about the scheduler API, the inference returns
an EMPTY adjacency table rather than an error. Downstream that reads as "no regulons found" - a
result-shaped hole. An import check would pass through it without noticing.

So this runs a real GRNBoost2 over a small matrix built with a KNOWN driver: one transcription
factor whose expression drives a block of targets. It asserts that edges come back at all, that
the planted TF is among the regulators found, and that the importances are finite. It asserts
nothing about biology - the data is synthetic and the planted edge is the fixture, not a result.

It does NOT test the cisTarget steps. Those need the motif rankings, which are ~1 GB and declared
in references.yml; `scprofile fetch scenic` gets them and `validate --deep` verifies them. What is
proved here is the half that needs no reference data, and the report says which half that is.
"""
from __future__ import annotations

import sys


def main():
    print("scenic selftest")

    import numpy as np
    print(f"  numpy       {np.__version__}")
    import pandas as pd
    print(f"  pandas      {pd.__version__}")
    import pyarrow
    print(f"  pyarrow     {pyarrow.__version__}")
    import dask
    print(f"  dask        {dask.__version__}")
    import distributed
    print(f"  distributed {distributed.__version__}")
    import arboreto
    from arboreto.algo import grnboost2
    print(f"  arboreto    {getattr(arboreto, '__version__', 'unknown')}")
    import ctxcore
    print(f"  ctxcore     {getattr(ctxcore, '__version__', 'unknown')}")
    import pyscenic
    print(f"  pyscenic    {pyscenic.__version__}")
    # Imported because the kernel needs them, and because a missing one here is a build failure
    # rather than a runtime one.
    from pyscenic.utils import modules_from_adjacencies                     # noqa: F401
    from pyscenic.prune import prune2df                                     # noqa: F401
    from pyscenic.aucell import aucell                                      # noqa: F401

    rng = np.random.default_rng(0)
    n_cells, n_genes = 120, 40
    genes = [f"Gene{i:02d}" for i in range(n_genes)]
    tf = genes[0]
    targets = genes[1:9]

    # A planted regulator: the TF varies across cells and its targets follow it, everything else
    # is noise. GRNBoost2 should be able to recover THIS, and if it recovers nothing the
    # scheduler handshake is broken.
    drive = rng.normal(5.0, 2.0, size=n_cells)
    X = rng.normal(5.0, 1.0, size=(n_cells, n_genes))
    X[:, 0] = drive
    for j, _g in enumerate(targets, start=1):
        X[:, j] = drive * (1.0 + 0.05 * j) + rng.normal(0, 0.3, size=n_cells)
    X = np.clip(X, 0, None)
    ex = pd.DataFrame(X, index=[f"c{i}" for i in range(n_cells)], columns=genes)

    print("  running GRNBoost2 (single process, seeded)")
    adj = grnboost2(expression_data=ex, tf_names=genes, verbose=False, seed=0,
                    client_or_address="local")
    print(f"  adjacencies -> {adj.shape[0]:,} edges x {adj.shape[1]} columns")

    # THE POINT OF THIS FILE. An empty table here is the silent failure, so it is the first thing
    # asserted and the message says what it means.
    assert adj.shape[0] > 0, (
        "GRNBoost2 returned NO EDGES on data with a planted regulator. This is the failure this "
        "selftest exists for: arboreto and the installed dask disagree about the scheduler and "
        "the inference comes back empty instead of raising. The pins in lock.yml are wrong for "
        "this dask.")
    for col in ("TF", "target", "importance"):
        assert col in adj.columns, f"adjacency table has no {col!r}; the schema moved"
    imp = adj["importance"].to_numpy(dtype=float)
    assert np.isfinite(imp).all(), "importances contain non-finite values"
    assert (imp > 0).any(), "every importance is zero"

    found = set(adj["TF"].astype(str))
    print(f"  regulators found: {len(found)}; planted TF {tf!r} present: {tf in found}")
    top = adj.sort_values("importance", ascending=False).head(3)
    for _i, r in top.iterrows():
        print(f"    {r['TF']} -> {r['target']}  importance {r['importance']:.4g}")
    assert tf in found, (
        f"the planted regulator {tf!r} is not among the regulators recovered. The inference ran "
        f"but did not find an edge built into the fixture.")

    print("  NOT tested here: the cisTarget prune and AUCell steps, which need the motif")
    print("  rankings from references.yml. `scprofile fetch scenic --to <dir>` gets them.")
    print("environment is usable")
    print("scenic selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
