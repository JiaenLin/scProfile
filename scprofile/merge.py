"""Assembling kernel results into one object. BY BARCODE, never by position.

THE ONE RULE THIS MODULE EXISTS TO ENFORCE

A kernel runs in its own process on its own copy of the data. Nothing guarantees it returns the
cells in the order it received them - a subset, a sort, a filter inside a dependency, and the order
is different. Merging by position then assigns one cell's pseudotime to another, silently, and
every figure downstream looks entirely reasonable.

So every cell-level result is joined on the barcode, and a result whose barcodes do not match is
REFUSED with the counts, not aligned by guesswork.

Edge-level results - cell-cell communication, regulon target lists, abundance tests - are not
cell-level at all and are never merged into the object. They are copied beside it as tables,
because forcing an edge list into `uns` makes it readable by this tool and nothing else.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np


class MergeError(Exception):
    """A result cannot be joined to the object without inventing an alignment."""


def _read_obs_column(path):
    """A kernel's obs column: a two-column CSV of barcode,value. No index guessing."""
    import pandas as pd
    df = pd.read_csv(path)
    if df.shape[1] < 2:
        raise MergeError(f"{path} needs at least two columns (barcode, value); it has "
                         f"{list(df.columns)}")
    return df.set_index(df.columns[0])[df.columns[1]]


def _read_array(path):
    p = Path(path)
    if p.suffix == ".npy":
        return np.load(p, allow_pickle=False)
    if p.suffix == ".npz":
        z = np.load(p, allow_pickle=False)
        return z[z.files[0]]
    raise MergeError(f"{p} is not .npy or .npz; the contract accepts those for arrays")


def merge_one(adata, out_dir, payload, *, log=print):
    """Merge one kernel's declared cell-level outputs. Returns what was merged and what was not."""
    out = Path(out_dir)
    merged = {"obs": [], "obsm": [], "layers": [], "tables": []}
    bc = adata.obs_names.astype(str)

    for col, rel in (payload.get("obs") or {}).items():
        s = _read_obs_column(out / rel)
        s.index = s.index.astype(str)
        shared = bc.intersection(s.index)
        if len(shared) == 0:
            raise MergeError(
                f"{payload['kernel']} obs[{col!r}]: NONE of its {len(s):,} barcodes match the "
                f"object's {len(bc):,}. These are not the same cells. First few from each:\n"
                f"  kernel: {list(s.index[:3])}\n  object: {list(bc[:3])}")
        if len(shared) < len(bc):
            log(f"    obs[{col}]: {len(shared):,} of {len(bc):,} cells covered; the rest are NaN")
        adata.obs[col] = s.reindex(bc).values           # REINDEX: by barcode, never by position
        merged["obs"].append(col)

    for key, rel in (payload.get("obsm") or {}).items():
        arr = _read_array(out / rel)
        if arr.shape[0] != adata.n_obs:
            raise MergeError(
                f"{payload['kernel']} obsm[{key!r}] has {arr.shape[0]:,} rows for "
                f"{adata.n_obs:,} cells. An array carries no barcodes, so it can only be merged "
                f"when it covers every cell in order - and this one does not. The kernel must "
                f"return every cell, or return a CSV keyed on barcode instead.")
        adata.obsm[key] = arr
        merged["obsm"].append(key)

    for key, rel in (payload.get("layers") or {}).items():
        arr = _read_array(out / rel)
        if arr.shape != adata.shape:
            raise MergeError(
                f"{payload['kernel']} layers[{key!r}] is {arr.shape} for an object of "
                f"{adata.shape}")
        adata.layers[key] = arr
        merged["layers"].append(key)

    return merged


def copy_tables(out_dir, payload, dest, *, log=print):
    """Edge-level and gene-level results, copied beside the object under a kernel-prefixed name.

    Prefixed because two kernels legitimately produce the same thing - `liana` and `cellchat` both
    write `ccc_edges.csv`, and that is the point of running both. Unprefixed, the second would
    overwrite the first and the comparison would silently become one method.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    made = []
    for rel in (payload.get("tables") or []):
        src = Path(out_dir) / rel
        name = Path(rel).name
        tgt = dest / (name if name.startswith(payload["kernel"]) else
                      f"{payload['kernel']}_{name}")
        shutil.copy2(src, tgt)
        made.append(tgt.name)
    return made


def link_objects(out_dir, payload, dest, *, log=print):
    """Side-car objects, HARDLINKED beside the merged object rather than copied.

    A kernel ships its own `.h5ad` when its result does not fit the merged one - velocity's fitted
    layers are on a selected gene set, not the full one. Those files are large, so they are
    hardlinked; a copy would double the run's footprint for a file that is byte-identical to one
    already on disk. Falls back to a copy across filesystems.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    made = []
    for key, rel in (payload.get("objects") or {}).items():
        src = Path(out_dir) / rel
        name = Path(rel).name
        tgt = dest / (name if name.startswith(payload["kernel"]) else
                      f"{payload['kernel']}_{name}")
        if tgt.exists():
            tgt.unlink()
        try:
            os.link(src, tgt)
        except OSError:
            shutil.copy2(src, tgt)
        made.append(tgt.name)
        log(f"  object {key} -> objects/{tgt.name}")
    return made


def provenance(payloads, describe, kernel_specs):
    """`uns['scprofile']`: what ran, against what, and every caveat. PROVENANCE ONLY, no results.

    Results live in obs/obsm/layers and in the tables. A uns that also carries results is a uns
    that disagrees with them the first time one is regenerated.
    """
    return {
        "contract": "1.0",
        "input": dict(describe),
        "kernels": {
            p["kernel"]: {
                "version": p.get("version", ""),
                "status": p.get("status", ""),
                "headline": p.get("headline", ""),
                "produced_obs": sorted((p.get("obs") or {}).keys()),
                "produced_obsm": sorted((p.get("obsm") or {}).keys()),
                "produced_layers": sorted((p.get("layers") or {}).keys()),
                "tables": list(p.get("tables") or []),
                "caveats": list(p.get("caveats") or []),
                "absent": [f"{a.get('what', '?')}: {a.get('why', '')}"
                           for a in (p.get("absent") or [])],
                "cannot_show": list(kernel_specs.get(p["kernel"], [])),
            } for p in payloads
        },
    }
