"""The one entrypoint every plugin is run through. Shipped with the host; never generated.

A plugin runs in its OWN interpreter - often its own pinned environment, sometimes another
language's - so the host cannot import it and call it directly. That is why plugins were wrappers
with a `main()`: each had to re-implement the protocol, and each re-implemented it slightly
differently.

This file is that wrapper, written ONCE. The plugin's interpreter runs THIS, with the plugin
module on its path; it reads `in.json`, applies the whole contract, imports the plugin, calls
`run(ctx)`, and writes `out.json`. Nothing is generated and nothing is copied between plugins, so
a fix to the contract is a fix for every plugin including ones this project did not write.

    <plugin's python> -m scprofile._entry <plugin module path> <in.json>
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import manifest                                            # noqa: E402
from scprofile.plugin import Context                                      # noqa: E402


def load(path):
    """Import a plugin from a file path, without it needing to be installed anywhere."""
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"scprofile_plugin_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "run"):
        raise SystemExit(f"{path.name} declares no run(ctx). A plugin is a PLUGIN dict and a "
                         f"run(ctx) function; see scprofile/plugin.py.")
    return mod


def main(argv):
    plugin_path = argv[1]
    inp = manifest.read_input(argv[2] if len(argv) > 2 else os.environ["SCPROFILE_IN"])
    out = Path(inp["out_dir"])
    log = print

    import numpy as np
    import scanpy as sc

    A = sc.read_h5ad(inp["h5ad"])
    keys = dict(inp.get("keys") or {})
    unit = inp.get("unit")
    sentinels = set(inp.get("sentinels") or ())
    cores = int((inp.get("resources") or {}).get("cores", 1))
    log(f"{A.n_obs:,} cells x {A.n_vars:,} genes"
        + (f", unit {unit!r}" if unit else "") + f", {cores} core(s)")

    pre_caveats = []

    # ---- THE CONTRACT, applied once for every plugin that will ever exist --------------------
    #
    # A per-unit plugin sees ONE unit's cells. Doing this here rather than in each plugin is what
    # stops one of them forgetting and reporting a cohort-wide number under a unit's name.
    ukey = keys.get("sample")
    if unit is not None and ukey and ukey in A.obs:
        A = A[A.obs[ukey].astype(str) == str(unit)].copy()
        log(f"  subset to {unit!r}: {A.n_obs:,} cells")
        if A.n_obs == 0:
            manifest.write_output(out, kernel=Path(plugin_path).stem, status="refused",
                                  headline=f"no cells in unit {unit!r}",
                                  absent=[{"what": "everything",
                                           "why": f"unit {unit!r} has no cells here"}])
            return 0

    # A sentinel is an annotator declining to call a cell type. They are CELLS: never a
    # population, never a denominator, never dropped.
    lab = keys.get("label")
    if lab and lab in A.obs:
        n = int(A.obs[lab].astype(str).isin(sentinels).sum())
        if n:
            pre_caveats.append(
                f"{n:,} cells carry an annotator sentinel ({', '.join(sorted(sentinels))}). "
                f"They are KEPT - they are cells - and are not treated as a population.")
            log(f"  {n:,} sentinel-labelled cells kept")

    # A NaN row in a computed embedding is a cell an upstream step withheld. In a neighbour graph
    # it either raises or silently yields a graph that cell is absent from.
    emb = keys.get("embedding")
    if emb and emb in A.obsm:
        bad = np.isnan(np.asarray(A.obsm[emb])[:, 0])
        nb = int(bad.sum())
        if nb:
            A = A[~bad].copy()
            pre_caveats.append(f"{nb:,} cells carry NaN in obsm[{emb!r}] - withheld upstream - "
                               f"and are EXCLUDED here.")
            log(f"  excluded {nb:,} cells with NaN in {emb}")

    ctx = Context(A, keys=keys, out=out, cores=cores, unit=unit,
                  organism=inp.get("organism"), assay=inp.get("assay"),
                  references=inp.get("references"), params=inp.get("params"),
                  design=inp.get("design"), sentinels=sentinels, log=log)
    ctx.caveats.extend(pre_caveats)

    mod = load(plugin_path)
    mod.run(ctx)

    manifest.write_output(
        out, kernel=Path(plugin_path).stem,
        version=str((getattr(mod, "PLUGIN", {}) or {}).get("version", "0.1.0")),
        status=ctx.status, headline=ctx.headline,
        obs=ctx._obs, obsm=ctx._obsm, layers=ctx._layers,
        tables=ctx._tables, figures=ctx._figures, objects=ctx._objects,
        absent=ctx.absent, caveats=ctx.caveats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
