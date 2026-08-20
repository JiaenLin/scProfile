#!/usr/bin/env python3
"""A fixture plugin, not a method. It makes the PER-UNIT path observable in a real run.

Nine of the ten defects fixed on 2026-08-20 lived on the per-unit path and none of them could
fire, because every `per_unit` plugin in the tree is `status: planned`. A code path that no
delivered run exercises is one whose bugs are found by users. This plugin is the smallest thing
that walks it: one unit at a time, writing every kind of output the contract has — an obs column
covering only its own cells, an array it knows cannot cross units, a table, a figure with a vector
and a source, and a side-car object under a FIXED basename so a collision would be visible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scprofile import manifest                                            # noqa: E402

VERSION = "0.1.0"


def main(argv):
    inp = json.loads(Path(argv[1]).read_text())
    out = Path(inp["out_dir"])
    unit = inp.get("unit")
    cores = (inp.get("resources") or {}).get("cores")

    import anndata as ad
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    A = ad.read_h5ad(inp["h5ad"])
    skey = (inp.get("keys") or {}).get("sample")
    if unit is not None and skey:
        A = A[A.obs[skey].astype(str) == str(unit)].copy()
    print(f"unit {unit!r}: {A.n_obs} cells, {cores} core(s)")

    rng = np.random.default_rng(abs(hash(str(unit))) % (2**31))
    score = pd.Series(rng.normal(size=A.n_obs), index=A.obs_names.astype(str), name="perunit_score")
    (out / "obs").mkdir(parents=True, exist_ok=True)
    sp = out / "obs" / "score.csv"
    score.to_frame().to_csv(sp, index_label="barcode")

    (out / "arrays").mkdir(parents=True, exist_ok=True)
    ap = out / "arrays" / "X_perunit.npy"
    np.save(ap, rng.normal(size=(A.n_obs, 2)).astype("float32"))

    (out / "tables").mkdir(parents=True, exist_ok=True)
    tp = out / "tables" / "perunit_edges.csv"
    pd.DataFrame({"unit": [unit] * 3, "rank": [1, 2, 3],
                  "value": rng.normal(size=3)}).to_csv(tp, index=False)

    (out / "figures").mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(3.35, 2.4), dpi=200)
    ax.hist(score.values, bins=20)
    ax.set_title(f"unit {unit}")
    ax.set_xlabel("score")
    fp = out / "figures" / "F1_score.png"
    vp = out / "figures" / "F1_score.pdf"
    fig.savefig(fp, bbox_inches="tight")
    fig.savefig(vp, bbox_inches="tight")
    plt.close(fig)
    sd = out / "figures" / "F1_score.csv"
    score.to_frame().to_csv(sd, index_label="barcode")

    # A FIXED basename, deliberately. Every unit writes `perunit_side.h5ad`; if the delivered name
    # does not carry the unit, nine of these overwrite each other in objects/.
    op = out / "perunit_side.h5ad"
    ad.AnnData(np.asarray(A.X[:, :5].todense() if hasattr(A.X, "todense") else A.X[:, :5]),
               obs=A.obs[[]].copy()).write_h5ad(op)

    manifest.write_output(
        out, kernel="perunit", version=VERSION, status="ok",
        headline=f"{A.n_obs} cells scored",
        obs={"perunit_score": sp}, obsm={"X_perunit": ap},
        tables=[tp], objects={"side": op},
        figures=[{"path": fp, "vector": vp, "source": sd,
                  "caption": f"Score distribution for unit {unit}."}],
        caveats=[f"Unit {unit} only. Nothing here is comparable across units without a model "
                 f"that says so.",
                 f"Ran on {cores} core(s), as allocated in in.json."])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
