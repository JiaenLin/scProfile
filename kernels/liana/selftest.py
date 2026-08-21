#!/usr/bin/env python3
"""Prove this environment can actually SCORE an interaction, before a real run is spent on it.

Importing liana proves liana is on the path. It does not prove `rank_aggregate` can run, and the
failures worth catching are all downstream of the import: a pandas groupby whose semantics moved,
a decoupler API rename, a resource file that no longer parses, an omnipath call that needs the
network on a compute node that has none.

So this builds a small synthetic object with a KNOWN ligand-receptor pair expressed in two known
populations and runs the complete path the kernel runs. It asserts SHAPES and COLUMNS, never a
biological answer - the data is synthetic and there is no correct interaction to find.

It also checks the two things this plugin's `cannot_show` warns about, because a selftest that
does not exercise the failure the documentation names is proving the easy half:

  - the default resource is HUMAN, and a human resource on mouse symbols returns a SMALL PLAUSIBLE
    TABLE rather than an error. The mouse resource is loaded here and its size compared.
  - the resource must load without network access, or this plugin cannot run in a batch job.
"""
from __future__ import annotations

import sys


def main():
    print("liana selftest")

    import numpy as np
    print(f"  numpy       {np.__version__}")
    import pandas as pd
    print(f"  pandas      {pd.__version__}")
    import anndata as ad
    print(f"  anndata     {ad.__version__}")
    import scanpy as sc
    print(f"  scanpy      {sc.__version__}")
    import liana as li
    print(f"  liana       {li.__version__}")

    # ---- the resource, offline ---------------------------------------------------------------
    # A compute node may have no outbound network. If the resource cannot load here, the plugin
    # cannot run in a batch job at all, and that is better known now than at hour three.
    res_h = li.resource.select_resource("consensus")
    res_m = li.resource.select_resource("mouseconsensus")
    print(f"  resource consensus (human):     {len(res_h):,} interactions")
    print(f"  resource mouseconsensus:        {len(res_m):,} interactions")
    assert len(res_h) > 1000, "the human consensus resource looks truncated"
    assert len(res_m) > 1000, "the mouse consensus resource looks truncated"
    hcase = res_h["ligand"].astype(str).str.isupper().mean()
    mcase = res_m["ligand"].astype(str).str.isupper().mean()
    print(f"  casing: human {hcase:.0%} upper, mouse {mcase:.0%} upper "
          f"- this is what makes a human resource on mouse symbols return almost nothing")
    assert hcase > 0.8 and mcase < 0.5, "the two resources are not in the casings expected"

    # ---- a real scoring run ------------------------------------------------------------------
    # THE FIXTURE MUST COVER THE RESOURCE. liana refuses when more than 98% of the resource's
    # genes are absent from var_names - correctly, because that is the signature of a resource
    # for the wrong organism, which is the failure this plugin's own cannot_show warns about. A
    # 62-gene fixture triggers exactly that refusal (PBS 676307), so the object is built FROM the
    # resource: every gene it names, plus the planted pair made strong.
    pair = res_m.iloc[0]
    lig, rec = str(pair["ligand"]), str(pair["receptor"])
    genes = sorted(set(res_m["ligand"].astype(str)) | set(res_m["receptor"].astype(str)))
    genes = [g for g in genes if "_" not in g]          # complexes are written A_B; skip them
    genes = list(dict.fromkeys([lig, rec] + genes))
    print(f"  fixture covers {len(genes):,} of the resource's genes")
    rng = np.random.default_rng(0)
    n = 200
    labels = np.array(["Alpha"] * (n // 2) + ["Beta"] * (n - n // 2))
    X = rng.poisson(1.0, size=(n, len(genes))).astype("float32")
    # The ligand high in Alpha, the receptor high in Beta, so there is something to find.
    X[labels == "Alpha", genes.index(lig)] += 40
    X[labels == "Beta", genes.index(rec)] += 40

    A = ad.AnnData(X, obs=pd.DataFrame({"cell_type": pd.Categorical(labels)},
                                       index=[f"c{i}" for i in range(n)]),
                   var=pd.DataFrame(index=genes))
    sc.pp.normalize_total(A, target_sum=1e4)
    sc.pp.log1p(A)

    li.mt.rank_aggregate(A, groupby="cell_type", resource_name="mouseconsensus",
                         expr_prop=0.1, use_raw=False, verbose=False, seed=0)
    res = A.uns["liana_res"]
    print(f"  rank_aggregate -> {res.shape[0]:,} rows x {res.shape[1]} columns")
    for col in ("source", "target", "ligand_complex", "receptor_complex",
                "magnitude_rank", "specificity_rank"):
        assert col in res.columns, f"liana_res has no {col!r}; the schema moved"
    assert res.shape[0] > 0, "rank_aggregate returned no rows on data built to contain a pair"
    assert np.isfinite(res["magnitude_rank"].to_numpy(dtype=float)).all(), \
        "magnitude_rank contains non-finite values"
    top = res.sort_values("magnitude_rank").iloc[0]
    print(f"  strongest: {top['source']} -> {top['target']}  "
          f"{top['ligand_complex']}:{top['receptor_complex']}  rank {top['magnitude_rank']:.3g}")

    print("environment is usable")
    print("liana selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
