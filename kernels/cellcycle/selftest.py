#!/usr/bin/env python3
"""Prove the cell-cycle CALL is well-formed against the installed scanpy, before a run is spent.

This plugin declares `needs_env: false` and runs in the host interpreter, and the contract used to
ask for a selftest only of plugins that bring their own environment. So nothing ever exercised
this call before a real cohort did — and the first cohort that did died three seconds in on

    score_genes() got multiple values for keyword argument 'ctrl_size'

because `score_genes_cell_cycle` computes `ctrl_size = min(len(s_genes), len(g2m_genes))` itself
and then forwards `**kwargs`. Nothing about the signature says so; six lines of its source do.

THE ENVIRONMENT IS NOT THE ONLY THING A SELFTEST PROVES. It proves the call is well-formed against
the version actually installed, which is exactly what moves underneath a wrapper — a keyword that
becomes positional, a default that becomes computed, an argument that is removed. A host
interpreter changes underneath a wrapper just as readily as a pinned one; it simply changes for
different reasons.

It asserts SHAPES, COLUMNS and FINITENESS, never a biological answer. The data is synthetic and
there is no correct phase to check against; a selftest asserting one would be testing its fixture.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main():
    print("cellcycle selftest")

    import numpy as np
    print(f"  numpy       {np.__version__}")
    import pandas as pd
    print(f"  pandas      {pd.__version__}")
    import anndata as ad
    print(f"  anndata     {ad.__version__}")
    import scanpy as sc
    print(f"  scanpy      {sc.__version__}")

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run as K
    print(f"  kernel      {K.VERSION}")

    s_all, g_all = K.S_GENES.split(), K.G2M_GENES.split()
    rng = np.random.default_rng(0)
    n = 300
    # The panels plus filler, so binning has something to bin against. Genes are given a spread of
    # means because score_genes bins on expression and a flat matrix collapses every bin.
    genes = s_all + g_all + [f"FILLER{i}" for i in range(400)]
    X = rng.poisson(rng.uniform(0.2, 8.0, size=len(genes)), size=(n, len(genes))).astype("float32")
    A = ad.AnnData(X, obs=pd.DataFrame(index=[f"c{i}" for i in range(n)]),
                   var=pd.DataFrame(index=genes))
    sc.pp.normalize_total(A, target_sum=1e4)
    sc.pp.log1p(A)
    A.layers["lognorm"] = A.X.copy()

    for layer in (None, "lognorm"):
        # EXACTLY the call run.py makes, both ways it can make it. A selftest that calls the
        # function differently from the kernel proves something about the selftest.
        sc.tl.score_genes_cell_cycle(A, s_genes=s_all, g2m_genes=g_all,
                                     use_raw=False, layer=layer,
                                     n_bins=K.N_BINS, random_state=K.SEED)
        for col in ("S_score", "G2M_score", "phase"):
            assert col in A.obs, f"layer={layer}: scanpy did not write obs[{col!r}]"
        for col in ("S_score", "G2M_score"):
            v = np.asarray(A.obs[col], dtype=float)
            assert v.shape == (n,), f"{col} is {v.shape}, expected ({n},)"
            assert np.isfinite(v).all(), f"{col} contains non-finite values"
        ph = set(A.obs["phase"].astype(str))
        assert ph <= {"G1", "S", "G2M"}, f"unexpected phase labels {ph}"
        print(f"  scored from {'layers[lognorm]' if layer else 'X'}: "
              f"{dict(A.obs['phase'].astype(str).value_counts())}")

    # The panel is HUMAN symbols and a mouse object is indexed by mouse ones. `_match` is what
    # bridges them, and if it ever stops matching the kernel scores on a handful of genes and
    # returns a low score rather than refusing - which reads as "not cycling" and is not.
    mouse_names = [g.capitalize() for g in genes]
    got = K._match(s_all, mouse_names, "mouse")
    assert len(got) == len(s_all), (
        f"_match found {len(got)} of {len(s_all)} S genes against title-cased names")
    assert "Mcm5" in got, f"expected the mouse casing, got e.g. {got[:3]}"
    print(f"  _match: {len(got)}/{len(s_all)} S genes across casings, e.g. {got[:3]}")

    print("cellcycle selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
