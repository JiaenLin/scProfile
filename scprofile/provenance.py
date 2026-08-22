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


def ancestry_roots(path, up=4):
    """Directories near the object, walking up from it.

    The recorded chain is only as long as the tools that wrote it. Each records its IMMEDIATE
    input, so a chain breaks wherever a step builds a fresh object — and a joint embedding two
    stages down then points at the stage above it and no further, with the aligner's output
    sitting four levels away and unreferenced.

    Walking up from the object and looking at siblings is the generic recovery: it assumes only
    that a project keeps its stages near each other, which is what a project is.
    """
    import os
    out, d = [], os.path.dirname(os.path.abspath(str(path)))
    for _ in range(up):
        if not d or d == os.path.dirname(d):
            break
        out.append(d)
        try:
            for e in os.scandir(d):
                if e.is_dir(follow_symlinks=False) and not e.name.startswith("."):
                    out.append(e.path)
        except OSError:
            pass
        d = os.path.dirname(d)
    seen, uniq = set(), []
    for r in out:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq


#: The shapes the single-cell profile knows an aligner writes velocity counts in. Recognised by
#: CONTENT — a filename convention is a guess about somebody else's pipeline.
_SOURCE_SHAPES = (
    ("mtx triplet", ("spliced.mtx", "unspliced.mtx", "barcodes.tsv")),
    ("mtx triplet (gz)", ("spliced.mtx.gz", "unspliced.mtx.gz", "barcodes.tsv.gz")),
)

#: A velocyto `.loom` is a FILE, not a directory shape, so it needs its own test. The README has
#: always said the kernel looks for one; this function - which the PLAN uses - did not, so the
#: plan could report "no source found" for data the kernel would have picked up.
_SOURCE_FILES = (("velocyto loom", ".loom"),)

#: Directories that are never an aligner's DELIVERED output and are enormous. STARsolo writes
#: `<sample>__STARtmp` trees with thousands of entries; walking them exhausts any visit budget
#: before the real output two levels away is reached. Pruning is not a shortcut here - it is what
#: makes the budget mean anything.
_PRUNE = ("__STARtmp", "_STARtmp", "STARtmp", ".git", ".snakemake", "__pycache__",
          ".nextflow", "work", ".cache", "site-packages")


def _cache_path(roots, wanted):
    """One cache file per (roots, wanted), in the user's cache dir. Not in the project."""
    import hashlib
    import os
    import tempfile
    key = hashlib.sha256(repr((sorted(map(str, roots)), sorted(wanted))).encode()).hexdigest()[:16]
    base = (os.environ.get("XDG_CACHE_HOME")
            or os.path.join(os.path.expanduser("~"), ".cache"))
    d = os.path.join(base, "scprofile")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = tempfile.gettempdir()
    return os.path.join(d, f"layers_{key}.json")


def find_layer_sources(roots, wanted=("spliced", "unspliced"), max_depth=14, cap=400_000,
                       cache_seconds=3600):
    """Cached, because the PLANNER RUNS EVERY TIME and this walk is the expensive part.

    Measured on a real project: 42,891 directories to depth 14. That is seconds on a warm local
    filesystem and much worse on a cold network one, and `plan` is a command people are meant to
    run freely - a plan that is expensive stops being consulted, and a plan nobody consults is a
    run that finds out at the end.

    The cache is keyed on the roots and what was wanted, lives in the user's cache directory and
    NOT in the project, and is invalidated by age. It stores only paths, so a stale entry costs a
    wrong suggestion rather than a wrong result - and the paths are re-checked for existence when
    they are read back, because a cached directory that has since been deleted must not be
    reported as a source.
    """
    """Where the missing layers actually are. Returns [(kind, path), ...].

    `plan` uses this to turn "this plugin will refuse" into "pass --search <this>". Reporting a
    gap without the path is the difference between a plan and an excuse.

    AND A SEARCH THAT GAVE UP MUST NOT LOOK LIKE ONE THAT FINISHED. This returned the same empty
    list whether it had walked the whole tree or run out of budget, and the caller turned that
    into "the data is absent" - a fact about the SCAN reported as a fact about the project, which
    is the one failure this tool's plan is written to avoid.

    `find_layer_sources.exhausted` is True when the visit cap or the depth limit stopped the walk
    before it was done. The plan reads it and answers UNRESOLVED rather than BLOCKED.

    The defaults were measured against real aligner output, not chosen. STARsolo delivers
    `<sample>_Solo.out/Velocyto/filtered/` at depth 9 below a project root, so the old
    `max_depth=8` could not reach it, and its `__STARtmp` siblings exhausted the old 8,000-visit
    cap long before that. Depth 14 with the temp trees pruned reaches it with budget to spare.
    """
    import json
    import os
    import time

    cp = _cache_path(roots, wanted)
    if cache_seconds and os.path.exists(cp):
        try:
            age = time.time() - os.path.getmtime(cp)
            if age < cache_seconds:
                d = json.loads(open(cp, encoding="utf-8").read())
                # RE-CHECK EXISTENCE. A cached path that has since been deleted is not a source,
                # and reporting one would send a run at a directory that is not there.
                hits = [(k, pth) for k, pth in d.get("found", []) if os.path.exists(pth)]
                find_layer_sources.visited = d.get("visited", 0)
                find_layer_sources.deepest = d.get("deepest", 0)
                find_layer_sources.exhausted = bool(d.get("exhausted"))
                find_layer_sources.cached = True
                return hits
        except (OSError, ValueError):
            pass
    find_layer_sources.cached = False

    found, visited, exhausted, deepest = [], 0, False, 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        stack = [(root, 0)]
        while stack:
            if visited >= cap:
                exhausted = True
                break
            d, depth = stack.pop()
            visited += 1
            deepest = max(deepest, depth)
            try:
                names = {e.name: e for e in os.scandir(d)}
            except OSError:
                # A directory that could not be READ is not a directory known to be empty.
                exhausted = True
                continue
            for kind, need in _SOURCE_SHAPES:
                if all(n in names for n in need):
                    found.append((kind, d))
                    break
            else:
                for kind, suffix in _SOURCE_FILES:
                    hit = sorted(n for n in names if n.endswith(suffix))
                    if hit:
                        found.append((kind, os.path.join(d, hit[0])))
                        break
            for e in names.values():
                if not e.is_dir(follow_symlinks=False) or e.name.startswith("."):
                    continue
                if any(pat in e.name for pat in _PRUNE):
                    continue
                if depth >= max_depth:
                    exhausted = True          # there was more tree and we stopped looking
                    continue
                stack.append((e.path, depth + 1))
        if exhausted and visited >= cap:
            break
    find_layer_sources.visited = visited
    find_layer_sources.deepest = deepest
    find_layer_sources.exhausted = exhausted
    try:
        with open(cp, "w", encoding="utf-8") as fh:
            json.dump({"found": [[k, str(v)] for k, v in found], "visited": visited,
                       "deepest": deepest, "exhausted": exhausted}, fh)
    except OSError:
        pass
    return found


find_layer_sources.visited = 0
find_layer_sources.deepest = 0
find_layer_sources.exhausted = False
find_layer_sources.cached = False


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
