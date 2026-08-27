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
        import numpy as np
        return np.load(p, allow_pickle=False)
    if p.suffix == ".npz":
        import numpy as np
        z = np.load(p, allow_pickle=False)
        return z[z.files[0]]
    raise MergeError(f"{p} is not .npy or .npz; the contract accepts those for arrays")


def _array_columns(path):
    """The names of an array's columns, written beside it by `ctx.emit_obsm`.

    Without them a 674-column activity matrix reaches the object as a bare ndarray and every
    figure the host could draw from it would be labelled by position. Absent for an array whose
    columns have no names - a two-column layout has none to give - and that is not an error.
    """
    f = Path(str(path) + "").with_suffix("").with_suffix(".columns.txt")
    g = Path(str(path).replace(".npy", ".columns.txt"))
    for cand in (g, f):
        try:
            if cand.exists():
                return [x for x in cand.read_text(encoding="utf-8").splitlines() if x]
        except OSError:
            pass
    return None


def _array_barcodes(path):
    """The barcodes an emitted array's rows belong to, or None if it carries none.

    Written by `ctx.emit_obsm` beside the `.npy`. Its absence is not an error - a plugin built
    before this, or one that writes its own array, has none - and the caller then falls back on
    the positional rule.
    """
    q = Path(path)
    stem = q.name[:-len(q.suffix)] if q.suffix else q.name
    side = q.parent / f"{stem}.barcodes.txt"
    if not side.exists():
        return None
    idx = [ln.strip() for ln in side.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return idx or None


def _align_rows(arr, idx, bc, *, what, log=print):
    """Put an array's rows where its barcodes say they go, NaN where it has nothing to say.

    The obs path has always done this - `reindex(bc)` - and the array path could not, because
    nothing recorded which cells the rows were. Now something does.
    """
    import numpy as np
    if len(idx) != arr.shape[0]:
        raise MergeError(
            f"{what}: {arr.shape[0]:,} rows and {len(idx):,} barcodes beside it. The array and "
            f"its index disagree, so nothing here can say which cell a row belongs to.")
    a = arr if arr.ndim > 1 else arr.reshape(-1, 1)
    pos = {b: i for i, b in enumerate(idx)}
    take = np.fromiter((pos.get(b, -1) for b in bc), dtype=np.int64, count=len(bc))
    hit = take >= 0
    if not hit.any():
        raise MergeError(
            f"{what}: NONE of its {len(idx):,} barcodes match the object's {len(bc):,}. These "
            f"are not the same cells. First few from each:\n"
            f"  kernel: {idx[:3]}\n  object: {list(bc[:3])}")
    out = np.full((len(bc), a.shape[1]), np.nan, dtype="float32")
    out[hit] = a[take[hit]]
    n = int(hit.sum())
    if n < len(bc):
        log(f"    {what}: {n:,} of {len(bc):,} cells covered; the rest are NaN")
    return out


def _require_unique_barcodes(adata):
    """Every merge here is `reindex(obs_names)`, which needs the object's barcodes to be unique.

    pandas raises `cannot reindex on an axis with duplicate labels` from deep inside the merge,
    with a traceback naming neither the object nor the plugin - and by then several subprocesses
    have finished and their results are about to be thrown away with the exception. Say it here,
    where the cause is nameable and nothing has run yet.
    """
    if adata.obs_names.is_unique:
        return
    seen, dup = set(), []
    for b in adata.obs_names.astype(str):       # plain python: a refusal must not need a stack
        (dup.append(b) if b in seen else seen.add(b))
    dup = sorted(set(dup))
    raise MergeError(
        f"the object's barcodes are not unique: {len(dup):,} value(s) repeat, e.g. "
        f"{list(dup[:3])}. Every result here is merged BY BARCODE, so a repeated barcode has no "
        f"single cell to merge onto. Make obs_names unique upstream - "
        f"`adata.obs_names_make_unique()` if the duplicates are genuinely different cells, or "
        f"fix the concatenation that produced them if they are not.")


def merge_one(adata, out_dir, payload, *, log=print):
    """Merge one kernel's declared cell-level outputs. Returns what was merged and what was not.

    ALL-OR-NOTHING. Everything is read and checked BEFORE anything is assigned, because this
    function can refuse and its caller treats a refusal as "the plugin did not run".

    It used to assign the obs columns in its first loop and raise from its second. `cli._run`
    caught the MergeError, printed MERGE REFUSED, put the plugin in `skipped` and continued - so
    the delivered object carried that plugin's obs column, mostly NaN, while `report.json`,
    `uns['scprofile']`, the report page and the README all said the plugin had not run. A column
    in an object that no document admits to is worse than a missing one: nothing about it looks
    wrong, and there is nothing to check it against.
    """
    out = Path(out_dir)
    _require_unique_barcodes(adata)
    merged = {"obs": [], "obsm": [], "layers": [], "tables": []}
    bc = adata.obs_names.astype(str)
    pend_obs, pend_arr = [], []

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
        pend_obs.append((col, s))

    for key, rel in (payload.get("obsm") or {}).items():
        arr = _read_array(out / rel)
        idx = _array_barcodes(out / rel)
        _cols = _array_columns(out / rel)
        if _cols:
            merged.setdefault("obsm_columns", {})[key] = _cols
        if idx is not None:
            # BY BARCODE, like every obs column. The host excludes cells with NaN in a computed
            # embedding from every plugin, so a plugin handed 98,627 of 100,713 cells returned
            # 98,627 rows and this refused it for not covering 100,713 - refused a plugin for
            # returning exactly the cells the host gave it.
            pend_arr.append(("obsm", key,
                             _align_rows(arr, idx, bc,
                                         what=f"{payload['kernel']} obsm[{key!r}]", log=log)))
            continue
        if arr.shape[0] != adata.n_obs:
            raise MergeError(
                f"{payload['kernel']} obsm[{key!r}] has {arr.shape[0]:,} rows for "
                f"{adata.n_obs:,} cells, and carries no barcodes beside it. Without them it can "
                f"only be merged when it covers every cell in order - and this one does not. "
                f"Emit it with `ctx.emit_obsm`, which writes the barcodes, or return a CSV keyed "
                f"on barcode instead."
                + (f"\n  This plugin ran per unit ({payload['unit']!r}), so its array covers one "
                   f"unit's cells by construction."
                   if payload.get("unit") else ""))
        pend_arr.append(("obsm", key, arr))

    for key, rel in (payload.get("layers") or {}).items():
        arr = _read_array(out / rel)
        idx = _array_barcodes(out / rel)
        if arr.ndim != 2 or arr.shape[1] != adata.n_vars:
            raise MergeError(
                f"{payload['kernel']} layers[{key!r}] is {arr.shape} for an object of "
                f"{adata.shape}. The gene axis has to match exactly - nothing beside the array "
                f"names its columns, and the host never subsets genes, so a different width is a "
                f"different object.")
        if idx is not None:
            # ROWS BY BARCODE, exactly as for obsm. A plugin handed fewer cells than the object -
            # which the host itself does, whenever a computed embedding has NaN rows - returns
            # fewer rows, and a shape check alone refuses it for that.
            pend_arr.append(("layers", key,
                             _align_rows(arr, idx, bc,
                                         what=f"{payload['kernel']} layers[{key!r}]", log=log)))
            continue
        if arr.shape != adata.shape:
            raise MergeError(
                f"{payload['kernel']} layers[{key!r}] is {arr.shape} for an object of "
                f"{adata.shape}, and carries no barcodes beside it. Emit it with "
                f"`ctx.emit_layer`, which writes them.")
        pend_arr.append(("layers", key, arr))

    # Nothing above touched `adata`. Past this line nothing can raise.
    for col, s in pend_obs:
        adata.obs[col] = s.reindex(bc).values           # REINDEX: by barcode, never by position
        merged["obs"].append(col)
    for slot, key, arr in pend_arr:
        getattr(adata, slot)[key] = arr
        merged[slot].append(key)

    return merged


def merge_many(adata, results, *, log=print):
    """Merge one plugin's results from SEVERAL units — one run per sample, say — as one column.

    A per-unit plugin returns a result covering only its own unit's cells. Merging each in turn
    with `merge_one` would let the last unit's NaNs overwrite every earlier unit's values, and the
    object would carry the final sample's result under a name implying the cohort's.

    So the pieces are concatenated FIRST and assigned once. Overlap between units is an error, not
    a merge: two units claiming the same cell means the units were not disjoint, and quietly
    taking one of them would hide that.
    """
    import pandas as pd
    # PER-UNIT IS A PROPERTY OF THE RESULT, NOT A COUNT OF THEM. This tested `len(results) == 1`,
    # so a per-unit plugin down to its last surviving unit was routed into merge_one - whose obsm
    # check requires an array covering EVERY cell, which a single unit's never does. Nine of ten
    # units failing therefore turned the tenth's valid result into a refusal of the whole plugin,
    # and the more units failed the more likely it became.
    if len(results) == 1 and not results[0][1].get("unit"):
        return merge_one(adata, results[0][0], results[0][1], log=log)

    _require_unique_barcodes(adata)
    merged = {"obs": [], "obsm": [], "layers": [], "tables": []}
    bc = adata.obs_names.astype(str)
    cols = {}
    for out_dir, payload in results:
        for col, rel in (payload.get("obs") or {}).items():
            s = _read_obs_column(Path(out_dir) / rel)
            s.index = s.index.astype(str)
            cols.setdefault(col, []).append((payload.get("unit"), s))

    for col, pieces in cols.items():
        idx = pd.Index([])
        for unit, s in pieces:
            dup = idx.intersection(s.index)
            if len(dup):
                raise MergeError(
                    f"obs[{col!r}]: unit {unit!r} claims {len(dup):,} cell(s) another unit "
                    f"already returned, e.g. {list(dup[:3])}. The units are not disjoint, and "
                    f"taking one of them would hide that.")
            idx = idx.append(s.index)
        full = pd.concat([s for _u, s in pieces])
        shared = bc.intersection(full.index)
        if len(shared) == 0:
            raise MergeError(
                f"obs[{col!r}]: none of {len(full):,} barcodes from {len(pieces)} unit(s) match "
                f"the object's {len(bc):,}. These are not the same cells.\n"
                f"  units: {list(full.index[:3])}\n  object: {list(bc[:3])}")
        if len(shared) < len(bc):
            log(f"    obs[{col}]: {len(shared):,} of {len(bc):,} cells covered across "
                f"{len(pieces)} unit(s); the rest are NaN")
        adata.obs[col] = full.reindex(bc).values
        merged["obs"].append(col)

    # AN ARRAY THAT CARRIES ITS BARCODES CAN CROSS UNITS. `ctx.emit_obsm` writes them, so a
    # per-unit plugin's arrays concatenate exactly as its obs columns do - the same disjointness
    # check, the same NaN for cells no unit covered. The sentence this replaced said an array
    # "carries no barcodes" as though that were a property of arrays; it was a property of what
    # the host had chosen to write down.
    import numpy as np
    pieces = {}
    for out_dir, payload in results:
        for key, rel in (payload.get("obsm") or {}).items():
            arr = _read_array(Path(out_dir) / rel)
            idx = _array_barcodes(Path(out_dir) / rel)
            pieces.setdefault(key, []).append((payload, arr, idx))
    for key, parts in sorted(pieces.items()):
        if any(idx is None for _p, _a, idx in parts):
            for payload, _a, idx in parts:
                if idx is not None:
                    continue
                _record_absent(merged, payload, "obsm", key, log,
                               "was returned per unit with no barcodes beside it, so nothing "
                               "here can say which cell a row belongs to. Emit it with "
                               "`ctx.emit_obsm`, which writes them.")
            continue
        seen, rows, index = set(), [], []
        clash = None
        for payload, arr, idx in parts:
            dup = seen.intersection(idx)
            if dup:
                clash = (payload.get("unit"), sorted(dup)[:3], len(dup))
                break
            seen.update(idx)
            rows.append(arr if arr.ndim > 1 else arr.reshape(-1, 1))
            index.extend(idx)
        if clash:
            raise MergeError(
                f"obsm[{key!r}]: unit {clash[0]!r} claims {clash[2]:,} cell(s) another unit "
                f"already returned, e.g. {clash[1]}. The units are not disjoint, and taking one "
                f"of them would hide that.")
        widths = {r.shape[1] for r in rows}
        if len(widths) > 1:
            _record_absent(merged, parts[0][0], "obsm", key, log,
                           f"came back with different widths across units ({sorted(widths)}), so "
                           f"the columns are not the same quantity and stacking them would "
                           f"invent one.")
            continue
        full = np.vstack(rows)
        adata.obsm[key] = _align_rows(full, index, bc, what=f"obsm[{key!r}]", log=log)
        merged["obsm"].append(key)

    # A LAYER STILL DOES NOT CROSS UNITS, and the reason is memory rather than alignment: the
    # barcodes would align it, but the result would be a DENSE cohort-wide matrix - cells by
    # genes, float32 - that no single unit's result implies and that this host will not allocate
    # on a plugin's behalf. A per-unit plugin whose result is per gene should emit a table, or a
    # side-car object under `objects`.
    for _out_dir, payload in results:
        for key in sorted(payload.get("layers") or {}):
            _record_absent(merged, payload, "layers", key, log,
                           "was returned per unit. Concatenating a per-unit layer means "
                           "allocating a dense cells-by-genes matrix for the whole cohort, which "
                           "no one unit's result implies; emit a table or a side-car object "
                           "instead.")
    return merged


def _record_absent(merged, payload, slot, key, log, why):
    """An output that did not reach the object is an ABSENCE and has to survive as one.

    Logging it to stdout left the report free to go on printing "merged into the object by
    barcode" from the plugin's DECLARATION, so `uns` and the HTML both asserted a key the object
    did not have and the only trace was one line of a finished run's console.
    """
    text = (f"{slot}[{key!r}] {why} It is NOT in the merged object; each unit's copy stays in "
            f"its own run directory.")
    log(f"    NOT MERGED: unit {payload.get('unit')!r} {text}")
    payload.setdefault("absent", []).append({"what": f"{slot}[{key}]", "why": text})
    d = merged.setdefault("dropped", [])
    if f"{slot}[{key}]" not in d:                  # one key, however many units returned it
        d.append(f"{slot}[{key}]")


def delivered_name(payload, rel):
    """The filename a per-instance artifact is DELIVERED under, beside the merged object.

    Two rules, and they have to be in ONE place. Kernel-prefixed, because `liana` and `cellchat`
    both write `ccc_edges.csv` and running both is the point. Unit-suffixed, because otherwise
    every unit of a per-unit plugin writes the SAME name and only the last survives - which then
    looks exactly like a cohort-level result.

    This function exists because the two rules were written twice and only one copy got the second
    rule. `copy_tables` had the unit suffix and a comment naming the hazard; `link_objects`, on the
    identical path 25 lines below, did not - so a per-unit plugin's side-car objects overwrote each
    other and delivered one sample's file under a cohort-looking name.
    """
    name = Path(rel).name
    stem = name if name.startswith(payload["kernel"]) else f"{payload['kernel']}_{name}"
    if payload.get("unit"):
        st = Path(stem)
        stem = f"{st.stem}__{payload['unit']}{st.suffix}"
    return stem


def _check_collisions(payload, rels, slot):
    """Refuse before delivering anything if two declared paths resolve to one delivered name."""
    seen = {}
    for rel in rels:
        name = delivered_name(payload, rel)
        if name in seen and seen[name] != rel:
            raise MergeError(
                f"{payload['kernel']}: {slot} {seen[name]!r} and {rel!r} both deliver as "
                f"{name!r}. Only the basename is kept beside the object, so one would silently "
                f"replace the other. Give them different FILENAMES rather than different "
                f"directories.")
        seen[name] = rel


def copy_tables(out_dir, payload, dest, *, log=print):
    """Edge-level and gene-level results, copied beside the object under a kernel-prefixed name.

    Prefixed because two kernels legitimately produce the same thing - `liana` and `cellchat` both
    write `ccc_edges.csv`, and that is the point of running both. Unprefixed, the second would
    overwrite the first and the comparison would silently become one method.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    # COLLISIONS FIRST, BEFORE ANY COPY. `delivered_name` takes the BASENAME, so one plugin
    # declaring `a/edges.csv` and `b/edges.csv` - a real shape, the same table computed two ways -
    # resolves both to one file and the second copy silently replaces the first. Checked up front
    # rather than mid-loop, so a refusal leaves nothing half-delivered.
    _check_collisions(payload, payload.get("tables") or [], "tables")
    made = []
    for rel in (payload.get("tables") or []):
        tgt = dest / delivered_name(payload, rel)
        shutil.copy2(Path(out_dir) / rel, tgt)
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
    _check_collisions(payload, list((payload.get("objects") or {}).values()), "objects")
    made = []
    for key, rel in (payload.get("objects") or {}).items():
        src = Path(out_dir) / rel
        tgt = dest / delivered_name(payload, rel)
        if tgt.exists():
            tgt.unlink()
        try:
            os.link(src, tgt)
        except OSError:
            shutil.copy2(src, tgt)
        made.append(tgt.name)
        log(f"  object {key} -> objects/{tgt.name}")
    return made


def fold_payloads(payloads, failed=None):
    """One entry per PLUGIN from a list with one entry per INSTANCE. Keyed by name, keeps units.

    The wave rewrite made a per-unit plugin produce N payloads, all carrying the same
    `payload["kernel"]`. Both consumers still built `{p["kernel"]: p for p in payloads}` - so nine
    of ten units were dropped by a dict comprehension, and the survivor was rendered under the
    bare plugin name as though it described the cohort. Nothing counted the loss and nothing could
    recover it from `report.json`.

    Folding also NORMALISES every path to be relative to the RUN directory rather than to the
    instance directory. A run-level document whose paths are relative to somewhere else is a
    document whose links do not resolve, and that is exactly how it failed: the report rendered
    `../kernels/<name>/<fig>` for a file at `../kernels/<name>/<unit>/<fig>`.
    """
    by = {}
    for pl in payloads:
        by.setdefault(pl["kernel"], []).append(pl)

    out = {}
    for name, group in by.items():
        multi = len(group) > 1 or any(g.get("unit") for g in group)
        units, figs, tabs, cav, absent, contra = [], [], [], [], [], []
        slots = {"obs": {}, "obsm": {}, "layers": {}, "objects": {}}
        for pl in sorted(group, key=lambda g: str(g.get("unit") or "")):
            u = pl.get("unit")
            base = pl.get("dir") or f"kernels/{name}"
            tag = f"[{u}] " if (multi and u) else ""
            for slot in slots:
                for k, rel in (pl.get(slot) or {}).items():
                    slots[slot].setdefault(k, []).append(f"{base}/{rel}")
            for rel in (pl.get("tables") or []):
                tabs.append("tables/" + delivered_name(pl, rel))
            for f in (pl.get("figures") or []):
                f = dict(f) if isinstance(f, dict) else {"path": f, "caption": ""}
                for fld in ("path", "vector", "source"):
                    if f.get(fld):
                        f[fld] = f"{base}/{f[fld]}"
                f["unit"] = u
                if tag:
                    f["caption"] = tag + (f.get("caption") or "")
                figs.append(f)
            cav += [tag + c for c in (pl.get("caveats") or [])]
            # UNTAGGED. A contradiction is looked for VERBATIM on the rendered page, so a
            # per-unit prefix would make every one of them unfindable - the fold would break
            # the check by making the sentence true of a unit rather than of the result.
            contra += [c for c in (pl.get("contradictions") or []) if c not in contra]
            absent += [{"what": tag + str(a.get("what", "?")), "why": a.get("why", "")}
                       for a in (pl.get("absent") or [])]
            units.append({"unit": u, "status": pl.get("status", ""),
                          "headline": pl.get("headline", ""),
                          "caveats": list(pl.get("caveats") or []),
                          "contradictions": list(pl.get("contradictions") or []),
                          "absent": list(pl.get("absent") or []),
                          "metrics": dict(pl.get("metrics") or {}),
                          "dir": base, "n_figures": len(pl.get("figures") or [])})

        # UNITS THAT FAILED HAVE NO PAYLOAD, so folding only what came back described a plugin
        # that ran on seven samples of ten as plainly "ok" - in report.json, in the report page and
        # in uns['scprofile'], while the merged column held NaN for the other three. A status
        # computed from the survivors is a status computed from the good news.
        gone = sorted({str(u) for u in (failed or {}).get(name, []) if u is not None})
        sts = {u["status"] for u in units}
        status = (group[0].get("status", "") if len(sts) == 1
                  else "partial" if sts & {"ok", "partial"} else sorted(sts)[0])
        if gone or (failed or {}).get(name):
            status = "partial"
        head = (group[0].get("headline", "") if not multi else
                f"{len(units)} unit(s): " + " · ".join(
                    f"{u['unit']} {u['headline']}" for u in units[:3])
                + (" …" if len(units) > 3 else ""))
        if gone:
            head += f" — {len(gone)} unit(s) FAILED and are not in this: {', '.join(gone)}"
            cav.insert(0, f"Ran on {len(units)} of {len(units) + len(gone)} unit(s). "
                          f"{', '.join(gone)} failed, and every cell of those units is NaN in "
                          f"this plugin's merged column.")
            absent.insert(0, {"what": f"{len(gone)} unit(s)",
                              "why": f"{', '.join(gone)} failed; their cells carry no result."})
        out[name] = {"kernel": name, "version": group[0].get("version", ""),
                     "status": status, "headline": head,
                     "obs": slots["obs"], "obsm": slots["obsm"],
                     "layers": slots["layers"], "objects": slots["objects"],
                     "tables": tabs, "figures": figs, "caveats": cav, "absent": absent,
                     "contradictions": contra,
                     "units": units, "failed_units": gone, "per_unit": multi}
    return out


def _uns_safe(node, where="uns['scprofile']"):
    """Refuse anything `uns` cannot hold, HERE, where the offending key is nameable.

    This exists because a one-line addition to `provenance` put `[None]` into `uns` - the unit
    list of a plugin that has no units - and h5py cannot write None inside a list. The whole run
    then died at `write_h5ad`, AFTER every subprocess had finished and before `report.json`,
    `report/` or the README were written: a total loss, from a provenance field, at the last step.

    So the constraint is checked rather than hoped for. A dict destined for `uns` may hold only
    strings, numbers, booleans and lists of those - no None anywhere, at any depth.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            if not isinstance(k, str):
                raise MergeError(f"{where}: key {k!r} is not a string; uns keys must be")
            _uns_safe(v, f"{where}[{k!r}]")
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            if v is None:
                raise MergeError(
                    f"{where}[{i}] is None. h5py cannot write None inside a list, and the failure "
                    f"lands at write_h5ad - after every plugin has finished and before anything "
                    f"is reported. Use a string, or leave the entry out.")
            _uns_safe(v, f"{where}[{i}]")
    elif node is None:
        raise MergeError(f"{where} is None; use \"\" or omit the key")
    elif not isinstance(node, (str, int, float, bool)):
        raise MergeError(f"{where} is {type(node).__name__}, which uns cannot hold")
    return node


def _plain(node):
    """Coerce a foreign dict into something `uns` can hold. None becomes "".

    `describe` is assembled elsewhere and a missing key there legitimately reads as None - the
    object has no compartment column, say. That is not a defect to refuse; it is a fact to record.
    So it is NORMALISED on the way in, while the fields provenance builds itself are CHECKED by
    `_uns_safe` and refused. Coercing everything would hide our own bugs; refusing everything
    would turn someone else's honest absence into a failed run.
    """
    if isinstance(node, dict):
        return {str(k): _plain(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [_plain(v) for v in node]
    if node is None:
        return ""
    if isinstance(node, (str, int, float, bool)):
        return node
    return str(node)


def provenance(folded, describe, kernel_specs, merged=None):
    """`uns['scprofile']`: what ran, against what, and every caveat. PROVENANCE ONLY, no results.

    Results live in obs/obsm/layers and in the tables. A uns that also carries results is a uns
    that disagrees with them the first time one is regenerated.
    """
    return _uns_safe({
        "contract": "1.0",
        "input": _plain(dict(describe)),
        # `produced_*` is read from WHAT THE MERGE RETURNED, not from what the plugin declared.
        # Written from the declaration, it asserted `obsm[X_regulon_auc]` was in the object for a
        # per-unit plugin whose arrays merge_many had just refused to concatenate.
        "kernels": {
            name: {
                "version": p.get("version", ""),
                "status": p.get("status", ""),
                "headline": p.get("headline", ""),
                # STRINGS, and no None. A plugin with no units yielded [None] here and killed
                # the h5ad write for every run in the tree.
                "units": [str(u["unit"]) for u in (p.get("units") or [])
                          if u.get("unit") is not None],
                "failed_units": list(p.get("failed_units") or []),
                "produced_obs": sorted((merged or {}).get(name, {}).get("obs", [])),
                "produced_obsm": sorted((merged or {}).get(name, {}).get("obsm", [])),
                "produced_layers": sorted((merged or {}).get(name, {}).get("layers", [])),
                "not_merged": sorted((merged or {}).get(name, {}).get("dropped", [])),
                "tables": list(p.get("tables") or []),
                "caveats": list(p.get("caveats") or []),
                "contradictions": list(p.get("contradictions") or []),
                "absent": [f"{a.get('what', '?')}: {a.get('why', '')}"
                           for a in (p.get("absent") or [])],
                "cannot_show": list(kernel_specs.get(name, [])),
            } for name, p in sorted((folded or {}).items())
        },
    })
