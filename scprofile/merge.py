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
        if arr.shape[0] != adata.n_obs:
            raise MergeError(
                f"{payload['kernel']} obsm[{key!r}] has {arr.shape[0]:,} rows for "
                f"{adata.n_obs:,} cells. An array carries no barcodes, so it can only be merged "
                f"when it covers every cell in order - and this one does not. The kernel must "
                f"return every cell, or return a CSV keyed on barcode instead."
                + (f"\n  This plugin ran per unit ({payload['unit']!r}), so its array covers one "
                   f"unit's cells by construction. Return it keyed on barcode, or declare it "
                   f"under `objects` as a side-car."
                   if payload.get("unit") else ""))
        pend_arr.append(("obsm", key, arr))

    for key, rel in (payload.get("layers") or {}).items():
        arr = _read_array(out / rel)
        if arr.shape != adata.shape:
            raise MergeError(
                f"{payload['kernel']} layers[{key!r}] is {arr.shape} for an object of "
                f"{adata.shape}")
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

    # An array output that cannot cross units is an ABSENCE and has to survive as one. Logging it
    # to stdout left the report free to go on printing "merged into the object by barcode" from
    # the plugin's DECLARATION, so `uns` and the HTML both asserted a key the object did not have
    # and the only trace was one line of a finished run's console. Note the asymmetry it fixes:
    # `merge_one` REFUSES a mismatched array loudly; this path was discarding one silently.
    for _out_dir, payload in results:
        for slot in ("obsm", "layers"):
            for key in sorted(payload.get(slot) or {}):
                why = (f"{slot}[{key!r}] was returned per unit and an array carries no barcodes, "
                       f"so it cannot be concatenated across units. It is NOT in the merged "
                       f"object; each unit's copy stays in its own run directory.")
                log(f"    NOT MERGED: unit {payload.get('unit')!r} {why}")
                payload.setdefault("absent", []).append(
                    {"what": f"{slot}[{key}]", "why": why})
                d = merged.setdefault("dropped", [])
                if f"{slot}[{key}]" not in d:      # one key, however many units returned it
                    d.append(f"{slot}[{key}]")
    return merged


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
        units, figs, tabs, cav, absent = [], [], [], [], []
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
            absent += [{"what": tag + str(a.get("what", "?")), "why": a.get("why", "")}
                       for a in (pl.get("absent") or [])]
            units.append({"unit": u, "status": pl.get("status", ""),
                          "headline": pl.get("headline", ""),
                          "caveats": list(pl.get("caveats") or []),
                          "absent": list(pl.get("absent") or []),
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
                "absent": [f"{a.get('what', '?')}: {a.get('why', '')}"
                           for a in (p.get("absent") or [])],
                "cannot_show": list(kernel_specs.get(name, [])),
            } for name, p in sorted((folded or {}).items())
        },
    })
