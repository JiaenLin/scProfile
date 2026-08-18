"""What the upstream tools recorded about where this object came from.

WHY THE HOST DOES THIS AND NOT THE KERNEL

Some inputs are not in the object. Velocity needs spliced and unspliced counts, which come from
the ALIGNER - they are not in a counts matrix and cannot be derived from one. Requiring a user to
hand-build an object carrying them is exactly the friction this tool exists to remove, when the
upstream pipeline already wrote down where its own inputs were.

The host reads that chain because the kernel cannot. `uns` is the one slot holding arbitrary
python, it is where anndata encodings diverge between versions, and the kernel copy deliberately
drops it (see compat.py). So the chain is harvested here, into plain JSON, and handed over in
`in.json` - which every kernel can read regardless of what its anndata is.

WHAT IS HARVESTED, AND WHY IT IS GENERIC

Not a list of known tools. Any string in `uns` that looks like a filesystem path is a lead, and
tool records are recognised by SHAPE - a mapping carrying `tool` and `version`, or a `schema` of
the form `<something>/provenance@<n>`. An object from a pipeline this file has never heard of
gets the same treatment as one from a pipeline it has.

Nothing here decides anything. It produces leads, the kernel searches them, and every path it
looked at is reported whether or not it found something.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

#: How far into a nested `uns` to look. Provenance lives near the top; a deep walk mostly finds
#: matrices and costs time.
MAX_DEPTH = 4

#: A value long enough to be a path and shaped like one. Windows drive letters included, because
#: an object may have been written elsewhere and read here.
_PATHLIKE = re.compile(r"^(/|[A-Za-z]:[\\/])[^\0\n]{3,}$")


def _text(v):
    """bytes -> str, numpy scalars -> str, everything else -> None."""
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(v, str):
        return v
    if hasattr(v, "item") and getattr(v, "shape", None) == ():
        try:
            return _text(v.item())
        except Exception:                                                  # noqa: BLE001
            return None
    return None


def _walk(node, depth=0):
    """(key, string) for every string-ish leaf in a nested mapping or array."""
    if depth > MAX_DEPTH:
        return
    if hasattr(node, "items"):
        for k, v in node.items():
            s = _text(v)
            if s is not None:
                yield str(k), s
            else:
                yield from _walk(v, depth + 1)
        return
    if isinstance(node, (list, tuple)) or (hasattr(node, "__len__")
                                           and hasattr(node, "__getitem__")
                                           and not isinstance(node, (str, bytes))):
        try:
            items = list(node)[:64]
        except Exception:                                                  # noqa: BLE001
            return
        for v in items:
            s = _text(v)
            if s is not None:
                yield "", s
            else:
                yield from _walk(v, depth + 1)


def _tool_records(uns):
    """Mappings that describe a tool run, recognised by shape rather than by name."""
    out = []
    for key, node in dict(uns or {}).items():
        if not hasattr(node, "items"):
            continue
        flat = {k: _text(v) for k, v in node.items()}
        schema = flat.get("schema") or ""
        tool = flat.get("tool")
        if tool or "/provenance@" in str(schema):
            out.append({k: v for k, v in {
                "slot": str(key),
                "tool": tool or str(schema).split("/")[0],
                "version": flat.get("version"),
                "run_key": flat.get("run_key"),
                "sample": flat.get("sample"),
                "written": flat.get("written"),
            }.items() if v})
    return out


def harvest(adata, *, extra_roots=()):
    """Leads for a kernel that needs something the object does not contain.

    Returns {"tools": [...], "search_paths": [...], "sample_hints": [...], "found_in": {...}} -
    all plain JSON. `search_paths` are DIRECTORIES that exist, deduplicated and ordered
    deepest-first, because the most specific lead is the one most likely to be right.
    """
    uns = getattr(adata, "uns", {}) or {}
    dirs, found_in = {}, {}
    for key, s in _walk(uns):
        if not _PATHLIKE.match(s):
            continue
        p = Path(s)
        d = p if p.is_dir() else p.parent
        try:
            if not d.is_dir():
                continue
        except OSError:
            continue
        r = str(d.resolve())
        if r not in dirs:
            dirs[r] = len(r.split(os.sep))
            found_in[r] = f"uns[{key!r}]" if key else "uns"

    for r in extra_roots:
        d = Path(r)
        if d.is_dir():
            rr = str(d.resolve())
            dirs.setdefault(rr, len(rr.split(os.sep)))
            found_in.setdefault(rr, "given on the command line")

    ordered = sorted(dirs, key=lambda r: -dirs[r])

    hints = []
    for rec in _tool_records(uns):
        if rec.get("sample"):
            hints.append(rec["sample"])
    for key, s in _walk(uns):
        if key in ("sample", "sample_id", "library") and not _PATHLIKE.match(s):
            hints.append(s)

    return {
        "tools": _tool_records(uns),
        "search_paths": ordered,
        "found_in": found_in,
        "sample_hints": sorted(set(hints)),
    }


def describe(prov, log=print):
    """Print the chain, so a user can see what a kernel will be searching before it searches."""
    tools = prov.get("tools") or []
    if tools:
        log("  upstream chain recorded in the object:")
        for t in tools:
            bits = [t.get("tool") or "?"]
            if t.get("version"):
                bits.append(t["version"])
            if t.get("run_key"):
                bits.append(f"run {t['run_key']}")
            if t.get("sample"):
                bits.append(f"sample {t['sample']}")
            log(f"    {' | '.join(bits)}")
    paths = prov.get("search_paths") or []
    if paths:
        log(f"  {len(paths)} directory lead(s) for kernels needing files beside the object:")
        for r in paths[:6]:
            log(f"    {r}   ({prov.get('found_in', {}).get(r, '')})")
        if len(paths) > 6:
            log(f"    ... and {len(paths) - 6} more, all passed to the kernels")
