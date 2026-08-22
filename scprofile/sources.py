"""Finding layers that are NOT in the object, in the aligner output beside it, and attaching them.

WHY THIS IS THE HOST'S JOB AND NOT ONE PLUGIN'S

Some inputs come from the ALIGNER and cannot be derived from a counts matrix. Spliced and
unspliced counts are the example this was written for, but nothing below is about velocity: an
object that went counts -> QC -> annotation -> integration has lost every aligner-produced layer
while the files are usually still sitting on disk beside it, and any plugin that needs one is in
exactly the same position. Telling a user to go and rebuild an object by hand is the friction this
tool exists to remove.

So: the host harvests the upstream chain from `uns` and passes the directory leads in `in.json`
(see scprofile/provenance.py). This module searches them for anything an aligner writes those
layers into, and attaches what it finds BY BARCODE. A plugin reaches it through
`ctx.source_layers()` and writes none of it.

IT LIVED IN A PLUGIN UNTIL 2026-08-22, and moving it is a correction rather than a tidy-up. A
plugin may not know a project; the aligner-output shapes below are not one project's vocabulary,
they are a fact about how quantifiers write output - the same fact `provenance.find_layer_sources`
already encoded on the PLANNER'S side of the same question. Two searches for one thing, in two
layers, is how a plan comes to promise what a run cannot deliver.

WHAT IS AND IS NOT ASSUMED

No tool name, no directory layout and no filename pattern from any one pipeline. Sources are
recognised by CONTENT - a loom with spliced/unspliced layers, an mtx triplet beside a barcode
list, an h5ad carrying both layers - and every directory searched is reported whether or not it
yielded anything. A search that finds nothing prints where it looked, which is the difference
between "your data has no velocity counts" and "I did not look where they are".

THE PART THAT GOES WRONG SILENTLY

Barcode matching. An aligner writes `AAACCCAAGAAACACT-1`; a joint object writes
`Sample3_AAACCCAAGAAACACT`; a velocyto loom writes `Sample3:AAACCCAAGAAACACTx`. Matching those
naively produces a 0% overlap and an empty result, or - far worse - a partial overlap that fills
some cells and leaves the rest at zero, which fits perfectly well and means nothing.

So matching is on the barcode CORE, the match rate is always printed, a source is refused below a
threshold, and a joint object is matched WITHIN each sample - because the same core barcode
legitimately recurs across samples of one experiment, and matching globally would assign one
animal's unspliced counts to another's cell.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from . import manifest

#: 10x-style barcodes are ACGT runs. Pulling the longest one out of a name absorbs sample
#: prefixes, `-1` suffixes and velocyto's trailing `x` in a single rule. A name with no such run
#: falls back to itself, so non-10x data still matches when the strings agree exactly.
_CORE = re.compile(r"[ACGTN]{8,}")

#: Directories never worth descending into. Bounded because these leads point into run trees that
#: can hold tens of thousands of files on a networked filesystem.
_SKIP = {".git", "logs", "cache", "__pycache__", "figures", "reports", "report", "tmp"}

MAX_DEPTH = 3
MAX_DIRS = 4000
MIN_MATCH = 0.5

#: The layer pair this was written for, and the only one any shipped plugin asks for today. It is
#: a DEFAULT and not a definition: every function below takes `names`, so a plugin needing some
#: other aligner-written pair gets the same search rather than a copy of it. The names are the
#: host's own capability vocabulary (`declare.CAPABILITIES`), never a project's column.
DEFAULT_LAYERS = ("spliced", "unspliced")


def core(name):
    m = _CORE.findall(str(name).upper())
    return max(m, key=len) if m else str(name)


class Source:
    """One place velocity counts were found, and what is known about it before opening it."""

    def __init__(self, kind, path, sample=None, why=""):
        self.kind, self.path, self.sample, self.why = kind, Path(path), sample, why

    def __repr__(self):
        return f"<{self.kind} {self.path}{' sample=' + self.sample if self.sample else ''}>"


def _sample_from(path, hints):
    """Which sample a source belongs to, if its path names one of the object's samples."""
    s = str(path)
    hit = [h for h in hints if h and re.search(rf"(^|[^A-Za-z0-9]){re.escape(h)}([^A-Za-z0-9]|$)",
                                               s)]
    return max(hit, key=len) if hit else None


def find(search_paths, sample_hints=(), *, log=print, max_depth=MAX_DEPTH,
         names=DEFAULT_LAYERS):
    """Every source of the wanted layers under the given leads. Reports where it looked."""
    found, seen_dirs, visited = [], set(), 0
    looked = []
    for root in search_paths:
        r = Path(root)
        if not r.is_dir():
            continue
        looked.append(str(r))
        stack = [(r, 0)]
        while stack and visited < MAX_DIRS:
            d, depth = stack.pop()
            rd = str(d.resolve())
            if rd in seen_dirs:
                continue
            seen_dirs.add(rd)
            visited += 1
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            entry_names = {e.name for e in entries}
            # An mtx triplet: spliced/unspliced matrices beside a barcode list. This is what
            # STARsolo's Velocyto output and several other quantifiers write.
            mtx = [[n for n in entry_names if re.match(rf"^{re.escape(w)}\.mtx(\.gz)?$", n)]
                   for w in names]
            bc = [n for n in entry_names if re.match(r"^barcodes\.tsv(\.gz)?$", n)]
            if all(mtx) and bc:
                found.append(Source("mtx", d, _sample_from(d, sample_hints),
                                    " + ".join(f"{w}.mtx" for w in names) + " + barcodes.tsv"))
            for e in entries:
                if e.is_file():
                    if e.name.endswith(".loom"):
                        found.append(Source("loom", e.path, _sample_from(e.path, sample_hints),
                                            "a .loom, which velocyto writes"))
                    elif e.name.endswith(".h5ad") and "velocity" not in e.name:
                        found.append(Source("h5ad", e.path, _sample_from(e.path, sample_hints),
                                            "an .h5ad - checked for the wanted layers"))
                elif e.is_dir(follow_symlinks=False) and depth < max_depth \
                        and e.name not in _SKIP and not e.name.startswith("."):
                    stack.append((Path(e.path), depth + 1))
    find.looked = looked
    find.visited = visited
    return found


find.looked = []
find.visited = 0


def load(source, log=print, names=DEFAULT_LAYERS):
    """(barcodes, genes, [matrix per wanted layer]) from one source, or None if it has none."""
    import numpy as np
    import scipy.sparse as sp

    if source.kind == "loom":
        import anndata as ad
        A = ad.read_loom(str(source.path), sparse=True, validate=False)
        have = set(manifest.layer_names(A))
        if not set(names) <= have:
            return None
        return (list(map(str, A.obs_names)), list(map(str, A.var_names)),
                [sp.csr_matrix(A.layers[w]) for w in names])

    if source.kind == "h5ad":
        import h5py
        try:
            with h5py.File(source.path, "r") as f:
                if "layers" not in f or not set(names) <= set(f["layers"].keys()):
                    return None
        except OSError:
            return None
        import anndata as ad
        A = ad.read_h5ad(source.path)
        return (list(map(str, A.obs_names)), list(map(str, A.var_names)),
                [sp.csr_matrix(A.layers[w]) for w in names])

    if source.kind == "mtx":
        import scipy.io
        d = source.path

        def _p(*names):
            for n in names:
                for suffix in ("", ".gz"):
                    f = d / (n + suffix)
                    if f.exists():
                        return f
            return None

        def _read_list(f):
            import gzip
            op = gzip.open if str(f).endswith(".gz") else open
            with op(f, "rt") as fh:
                return [ln.split("\t")[0].strip() for ln in fh if ln.strip()]

        fb, fg = _p("barcodes.tsv"), _p("features.tsv", "genes.tsv")
        fm = [_p(f"{w}.mtx") for w in names]
        if not all([fb, fg] + fm):
            return None
        bcs, genes = _read_list(fb), _read_list(fg)
        mats = [scipy.io.mmread(str(f)).tocsr() for f in fm]
        # mtx from these quantifiers is genes x cells; orient by which axis matches the lists.
        if mats[0].shape[0] == len(genes) and mats[0].shape[1] == len(bcs):
            mats = [m.T.tocsr() for m in mats]
        if mats[0].shape[0] != len(bcs):
            log(f"    {d}: {mats[0].shape} matches neither {len(bcs)} barcodes nor "
                f"{len(genes)} genes")
            return None
        return bcs, genes, mats

    return None


def attach(A, sources, *, sample_key=None, min_match=MIN_MATCH, log=print,
           names=DEFAULT_LAYERS):
    """Fill `A.layers[name]` for each wanted layer from the sources. Returns (ok, note).

    Matching is on the barcode core, within a sample when the source names one, and the rate is
    printed for every source tried - including the ones that matched nothing, because a source
    that matched nothing is the thing a user most needs to see.
    """
    import numpy as np
    import scipy.sparse as sp

    n, g = A.n_obs, A.n_vars
    dest = [sp.lil_matrix((n, g), dtype="float32") for _ in names]
    filled = np.zeros(n, dtype=bool)
    var_pos = {str(v).upper(): i for i, v in enumerate(A.var_names)}
    obs_core = np.array([core(b) for b in A.obs_names])
    samples = (A.obs[sample_key].astype(str).values
               if sample_key and sample_key in A.obs else None)
    notes, used = [], 0

    for src in sources:
        loaded = load(src, log=log, names=names)
        if loaded is None:
            continue
        bcs, genes, mats = loaded

        # Restrict to this source's sample when it names one. The same core barcode legitimately
        # recurs across samples, and matching globally would give one animal's unspliced counts
        # to another's cell - which produces a full matrix and a wrong answer.
        if src.sample is not None and samples is not None:
            scope = np.where(samples == src.sample)[0]
            scope_why = f"within sample {src.sample}"
        else:
            scope = np.arange(n)
            scope_why = "across all cells (the source names no sample)"

        want = {}
        for j, b in enumerate(bcs):
            want.setdefault(core(b), j)
        rows = [(i, want[obs_core[i]]) for i in scope if obs_core[i] in want]
        rate = len(rows) / max(1, len(scope))
        log(f"    {src.kind}  {src.path.name}: {len(rows):,}/{len(scope):,} barcodes matched "
            f"({100 * rate:.1f}%) {scope_why}")
        if rate < min_match:
            notes.append(f"{src.path.name} matched only {100 * rate:.1f}% and was NOT used")
            continue

        gcols = [var_pos.get(str(gn).upper()) for gn in genes]
        keep = [(k, c) for k, c in enumerate(gcols) if c is not None]
        if not keep:
            notes.append(f"{src.path.name}: no gene name overlapped the object")
            log(f"      no gene name overlapped the object - not used")
            continue
        src_cols = np.array([k for k, _ in keep])
        dst_cols = np.array([c for _, c in keep])
        src_rows = np.array([j for _, j in rows])
        dst_rows = np.array([i for i, _ in rows])
        for D, M in zip(dest, mats):
            D[np.ix_(dst_rows, dst_cols)] = M[np.ix_(src_rows, src_cols)]
        filled[dst_rows] = True
        used += 1
        notes.append(f"{src.path.name}: {len(rows):,} cells, {len(keep):,} genes")

    if not used:
        return False, "; ".join(notes) if notes else "no source carried usable counts"

    cov = float(filled.mean())
    log(f"  attached from {used} source(s): {filled.sum():,}/{n:,} cells "
        f"({100 * cov:.1f}%) have {'/'.join(names)} counts")
    for w, D in zip(names, dest):
        A.layers[w] = sp.csr_matrix(D)
    return True, (f"{used} source(s), {filled.sum():,}/{n:,} cells ({100 * cov:.1f}%) covered. "
                  + "; ".join(notes))
