#!/usr/bin/env python3
"""Write a small synthetic dataset that exercises the whole path, then throw it away.

WHY A FIXTURE AND NOT A REAL DATASET

Most real objects cannot test this tool: the majority carry no spliced/unspliced counts, so the
kernel that most needs proving is the one that refuses on them. And a test that depends on
somebody's data is a test that runs on one machine.

So this builds an object with the SHAPE a real one has after scQC -> scAnno -> scIntegrate, and
with the awkward parts deliberately present rather than smoothed away:

  X                lognormalised, NOT counts - which is what an integrated object delivers, and
                   the thing that makes a second log transform possible
  layers[counts]   the raw counts, where the pipeline actually keeps them
  spliced/unspliced integer counts with unspliced LEADING spliced along a latent axis
  obs[cell_type]   labels, including the annotator sentinels EXCLUDED and UNRESOLVED
  obs[sample]      several samples, so a batch key exists
  obsm[X_scanvi]   an integrated embedding, so the arrows have somewhere to land

    python make_fixture.py /path/to/fixture.h5ad
"""
from __future__ import annotations

import sys
from pathlib import Path


#: Real MOUSE symbols - the casing probes the host uses to detect organism, and enough of the
#: Tirosh cell-cycle panel that `cellcycle` takes its scoring path rather than only its refusal
#: path. A fixture that only ever provokes refusals proves the refusals and nothing else.
_REAL = """Actb Gapdh Malat1 Rpl13a Ptprc Eef1a1 Epcam Pecam1 Col1a1 Myh11 Alb
Mcm5 Pcna Tyms Fen1 Mcm2 Mcm4 Rrm1 Ung Gins2 Mcm6 Cdca7 Dtl Prim1 Uhrf1 Hells Rfc2 Rpa2 Nasp
Gmnn Wdr76 Slbp Ccne2 Ubr7 Pold3 Msh2 Atad2 Rad51 Rrm2 Cdc45 Cdc6 Exo1 Tipin Dscc1 Blm Usp1
Clspn Pola1 Chaf1b Brip1 E2f8
Hmgb2 Cdk1 Nusap1 Ube2c Birc5 Tpx2 Top2a Ndc80 Cks2 Nuf2 Cks1b Mki67 Tmpo Cenpf Tacc3 Smc4 Ccnb2
Ckap2l Ckap2 Aurkb Bub1 Kif11 Anp32e Tubb4b Gtse1 Kif20b Hjurp Cdca3 Cdc20 Ttk Cdc25c Kif2c
Rangap1 Ncapd2 Dlgap5 Cdca2 Cdca8 Ect2 Kif23 Hmmr Aurka Psrc1 Anln Lbr Ckap5 Cenpe Ctcf Nek2
G2e3 Gas2l3 Cbx5 Cenpa""".split()


def _gene_names(g):
    """Real symbols first, then filler. Deterministic, and unique."""
    names = list(dict.fromkeys(_REAL))[:g]
    names += [f"Gm{10000 + j}" for j in range(g - len(names))]
    return names


def build(n=1200, g=400, seed=0):
    import anndata as ad
    import numpy as np
    import pandas as pd
    import scipy.sparse as sp

    rng = np.random.default_rng(seed)

    # Three populations, one of which sits on a progression: unspliced leads spliced along t.
    lab = rng.choice(["Alpha", "Beta", "Gamma"], size=n, p=[0.5, 0.3, 0.2])
    t = np.where(lab == "Alpha", rng.uniform(0, 1, n), rng.uniform(0.4, 0.6, n))

    base = rng.uniform(0.3, 3.5, g)
    prog = np.outer(t, rng.normal(0, 1.4, g))
    spliced = rng.poisson(np.clip(np.exp(base + prog), 0.05, 400)).astype("float32")
    unspliced = rng.poisson(np.clip(np.exp(base + prog + 0.4), 0.05, 400) * 0.35).astype("float32")
    counts = spliced + unspliced

    # The sentinels an annotator leaves behind. They are cells; they are not cell types.
    lab = lab.astype(object)
    lab[rng.choice(n, 40, replace=False)] = "EXCLUDED"
    lab[rng.choice(n, 25, replace=False)] = "UNRESOLVED"

    A = ad.AnnData(X=sp.csr_matrix(counts))
    A.layers["counts"] = sp.csr_matrix(counts)
    A.layers["spliced"] = sp.csr_matrix(spliced)
    A.layers["unspliced"] = sp.csr_matrix(unspliced)
    A.obs_names = [f"CELL{i:05d}" for i in range(n)]
    A.var_names = _gene_names(g)
    A.obs["cell_type"] = pd.Categorical(lab)
    A.obs["sample"] = pd.Categorical(rng.choice([f"S{i}" for i in range(1, 5)], size=n))
    A.obs["group"] = pd.Categorical(np.where(
        A.obs["sample"].isin(["S1", "S2"]), "control", "treated"))

    # X lognormalised, counts kept in the layer. This is the arrangement that makes a second log
    # transform possible, and the kernel is expected to notice it.
    import scanpy as sc
    sc.pp.normalize_total(A, target_sum=1e4)
    sc.pp.log1p(A)

    B = A.copy()
    sc.pp.highly_variable_genes(B, n_top_genes=min(200, B.n_vars))
    sc.pp.pca(B, n_comps=20)
    A.obsm["X_scanvi"] = B.obsm["X_pca"][:, :10].copy()
    sc.pp.neighbors(B, n_pcs=20)
    sc.tl.umap(B, min_dist=0.2)
    A.obsm["X_umap"] = B.obsm["X_umap"].copy()

    A.uns["scintegrate"] = {
        "default_embedding": "X_scanvi",
        "constraint_on_use": "SYNTHETIC FIXTURE. No number here describes anything real.",
    }
    return A


def main(argv):
    out = Path(argv[1] if len(argv) > 1 else "fixture.h5ad")
    A = build()
    out.parent.mkdir(parents=True, exist_ok=True)
    A.write_h5ad(out)
    print(f"wrote {out}")
    print(f"  {A.n_obs:,} cells x {A.n_vars:,} genes")
    print(f"  layers  {manifest.layer_names(A)}")
    print(f"  obs     {list(A.obs.columns)}")
    print(f"  obsm    {list(A.obsm)}")
    print(f"  labels  {dict(A.obs['cell_type'].value_counts())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
