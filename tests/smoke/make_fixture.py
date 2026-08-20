#!/usr/bin/env python3
"""Build the synthetic object the smoke test runs against. Entirely generated; no real data.

It carries what a profiling run needs and nothing more: raw counts, spliced and unspliced layers,
a lognorm layer, a cell-type column with two annotator SENTINELS in it, several samples, an
embedding, and an upstream constraint on use in `uns`. Every value is drawn from a seeded
generator, so nothing here can be mistaken for a result.

The sentinels and the multiple samples are not decoration. They are the two features that make the
run exercise its own hard paths - a sentinel is not a cell type and must be handled as such, and a
sample column is what turns a `per_unit` plugin into more than one instance.

    python tests/smoke/make_fixture.py --out fixture.h5ad
"""
from __future__ import annotations

import argparse
from pathlib import Path

SEED = 0
N_CELLS, N_GENES, N_SAMPLES = 1200, 400, 4
TYPES = ["Alpha", "Beta", "Gamma"]
SENTINELS = ["EXCLUDED", "UNRESOLVED"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cells", type=int, default=N_CELLS)
    ap.add_argument("--genes", type=int, default=N_GENES)
    ap.add_argument("--samples", type=int, default=N_SAMPLES)
    a = ap.parse_args()

    import anndata as ad
    import numpy as np
    import pandas as pd
    import scipy.sparse as sp

    rng = np.random.default_rng(SEED)
    n, g = a.cells, a.genes

    # Title-case symbols, so organism detection has something real to detect.
    genes = ([x.capitalize() for x in
              ("ACTB GAPDH MALAT1 MCM5 PCNA TYMS FEN1 MCM2 MCM4 RRM1 UNG GINS2 MCM6 CDCA7 DTL "
               "PRIM1 UHRF1 HELLS RFC2 RPA2 NASP GMNN SLBP CCNE2 UBR7 POLD3 MSH2 ATAD2 RAD51 "
               "RRM2 CDC45 CDC6 EXO1 TIPIN DSCC1 BLM USP1 CLSPN POLA1 CHAF1B BRIP1 E2F8 HMGB2 "
               "CDK1 NUSAP1 UBE2C BIRC5 TPX2 TOP2A NDC80 CKS2 NUF2 CKS1B MKI67 TMPO CENPF "
               "TACC3 SMC4 CCNB2 CKAP2 AURKB BUB1 KIF11 ANP32E TUBB4B GTSE1 KIF20B HJURP "
               "CDCA3 CDC20 TTK CDC25C KIF2C RANGAP1 NCAPD2 DLGAP5 CDCA2 CDCA8 ECT2 KIF23 "
               "HMMR AURKA PSRC1 ANLN LBR CKAP5 CENPE CTCF NEK2 G2E3 CBX5 CENPA").split()])
    genes = (genes + [f"Gene{i:04d}" for i in range(g)])[:g]

    means = rng.uniform(0.2, 8.0, size=g)
    counts = rng.poisson(means, size=(n, g)).astype("float32")
    # Unspliced as a fraction of counts, so an assay probe has something to measure.
    unspliced = rng.binomial(counts.astype(int), 0.34).astype("float32")
    spliced = counts - unspliced

    labels = rng.choice(TYPES, size=n, p=[0.46, 0.29, 0.25]).astype(object)
    hit = rng.choice(n, size=int(n * 0.053), replace=False)
    labels[hit] = rng.choice(SENTINELS, size=len(hit), p=[0.6, 0.4])
    samples = np.array([f"S{1 + i % a.samples}" for i in range(n)])
    rng.shuffle(samples)

    A = ad.AnnData(
        sp.csr_matrix(counts),
        obs=pd.DataFrame({"cell_type": pd.Categorical(labels),
                          "sample": pd.Categorical(samples),
                          "group": pd.Categorical(np.where(
                              pd.Series(samples).isin(["S1", "S2"]), "ctrl", "treat"))},
                         index=[f"cell{i:05d}" for i in range(n)]),
        var=pd.DataFrame(index=pd.Index(genes, name=None)))
    A.layers["counts"] = A.X.copy()
    A.layers["spliced"] = sp.csr_matrix(spliced)
    A.layers["unspliced"] = sp.csr_matrix(unspliced)

    import scanpy as sc
    B = A.copy()
    sc.pp.normalize_total(B, target_sum=1e4)
    sc.pp.log1p(B)
    A.layers["lognorm"] = B.X.copy()
    A.obsm["X_scanvi"] = rng.normal(size=(n, 10)).astype("float32")
    A.obsm["X_umap"] = rng.normal(size=(n, 2)).astype("float32")

    # An upstream constraint, so the host has one to carry into the report. Any integration tool
    # that writes one uses this shape; the text is a plausible one, not a real result.
    A.uns["scintegrate"] = {
        "constraint_on_use": ("This embedding may carry visualisation, clustering and cell-type "
                             "identification. It must NOT carry a composition or abundance claim "
                             "across any factor nested in the batch key."),
        "batch_key": "sample"}

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    A.write_h5ad(out)
    print(f"wrote {out}")
    print(f"  {A.n_obs:,} cells x {A.n_vars:,} genes")
    # `sorted(A.layers)` raised `'<' not supported between 'str' and 'NoneType'` here, which means
    # iterating this anndata's layers yields a None key. The host already carries the same guard
    # in two places - `{k for k in A.layers if k is not None}` - with no comment saying why, so it
    # is a known behaviour that nobody wrote down. Measured and named rather than worked around
    # silently, because a mapping that yields a key its own __getitem__ cannot take is worth
    # knowing about before a plugin declares `layers[...]`.
    lk = list(A.layers)
    if any(k is None for k in lk):
        print(f"  NOTE: A.layers yields a None key on anndata {ad.__version__}; "
              f"raw keys {lk!r}. The host filters it; so does this.")
    print(f"  layers  {sorted(k for k in lk if k is not None)}")
    print(f"  obs     {list(A.obs.columns)}")
    print(f"  obsm    {sorted(A.obsm)}")
    print(f"  labels  {dict(A.obs['cell_type'].value_counts())}")
    print(f"  samples {dict(A.obs['sample'].value_counts())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
