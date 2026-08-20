#!/usr/bin/env python3
"""Finding spliced/unspliced counts that are NOT in the object, and attaching them safely.

WHY THIS EXISTS

Spliced and unspliced counts come from the aligner. They are not in a counts matrix and cannot be
derived from one, so an object that went counts -> QC -> annotation -> integration has lost the
route to velocity even though the files are usually still sitting on disk beside it. Telling a
user to go and rebuild an object by hand is exactly the friction this tool exists to remove.

So: the host harvests the upstream chain from `uns` and passes the directory leads in `in.json`
(see scprofile/provenance.py). This module searches them for anything an aligner writes velocity
counts into, and attaches what it finds BY BARCODE.

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


def find(search_paths, sample_hints=(), *, log=print, max_depth=MAX_DEPTH):
    """Every velocity-counts source under the given leads. Reports where it looked."""
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
            names = {e.name for e in entries}
            # An mtx triplet: spliced/unspliced matrices beside a barcode list. This is what
            # STARsolo's Velocyto output and several other quantifiers write.
            sp = [n for n in names if re.match(r"^spliced\.mtx(\.gz)?$", n)]
            up = [n for n in names if re.match(r"^unspliced\.mtx(\.gz)?$", n)]
            bc = [n for n in names if re.match(r"^barcodes\.tsv(\.gz)?$", n)]
            if sp and up and bc:
                found.append(Source("mtx", d, _sample_from(d, sample_hints),
                                    "spliced.mtx + unspliced.mtx + barcodes.tsv"))
            for e in entries:
                if e.is_file():
                    if e.name.endswith(".loom"):
                        found.append(Source("loom", e.path, _sample_from(e.path, sample_hints),
                                            "a .loom, which velocyto writes"))
                    elif e.name.endswith(".h5ad") and "velocity" not in e.name:
                        found.append(Source("h5ad", e.path, _sample_from(e.path, sample_hints),
                                            "an .h5ad - checked for spliced/unspliced layers"))
                elif e.is_dir(follow_symlinks=False) and depth < max_depth \
                        and e.name not in _SKIP and not e.name.startswith("."):
                    stack.append((Path(e.path), depth + 1))
    find.looked = looked
    find.visited = visited
    return found


find.looked = []
find.visited = 0


def load(source, log=print):
    """(barcodes, genes, spliced, unspliced) from one source, or None if it carries neither."""
    import numpy as np
    import scipy.sparse as sp

    if source.kind == "loom":
        import anndata as ad
        A = ad.read_loom(str(source.path), sparse=True, validate=False)
        have = set(manifest.layer_names(A))
        if not {"spliced", "unspliced"} <= have:
            return None
        return (list(map(str, A.obs_names)), list(map(str, A.var_names)),
                sp.csr_matrix(A.layers["spliced"]), sp.csr_matrix(A.layers["unspliced"]))

    if source.kind == "h5ad":
        import h5py
        try:
            with h5py.File(source.path, "r") as f:
                if "layers" not in f or not {"spliced", "unspliced"} <= set(f["layers"].keys()):
                    return None
        except OSError:
            return None
        import anndata as ad
        A = ad.read_h5ad(source.path)
        return (list(map(str, A.obs_names)), list(map(str, A.var_names)),
                sp.csr_matrix(A.layers["spliced"]), sp.csr_matrix(A.layers["unspliced"]))

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
        fs, fu = _p("spliced.mtx"), _p("unspliced.mtx")
        if not all((fb, fg, fs, fu)):
            return None
        bcs, genes = _read_list(fb), _read_list(fg)
        S, U = scipy.io.mmread(str(fs)).tocsr(), scipy.io.mmread(str(fu)).tocsr()
        # mtx from these quantifiers is genes x cells; orient by which axis matches the lists.
        if S.shape[0] == len(genes) and S.shape[1] == len(bcs):
            S, U = S.T.tocsr(), U.T.tocsr()
        if S.shape[0] != len(bcs):
            log(f"    {d}: {S.shape} matches neither {len(bcs)} barcodes nor {len(genes)} genes")
            return None
        return bcs, genes, S, U

    return None


def attach(A, sources, *, sample_key=None, min_match=MIN_MATCH, log=print):
    """Fill `A.layers['spliced'/'unspliced']` from the sources. Returns (ok, note).

    Matching is on the barcode core, within a sample when the source names one, and the rate is
    printed for every source tried - including the ones that matched nothing, because a source
    that matched nothing is the thing a user most needs to see.
    """
    import numpy as np
    import scipy.sparse as sp

    n, g = A.n_obs, A.n_vars
    S = sp.lil_matrix((n, g), dtype="float32")
    U = sp.lil_matrix((n, g), dtype="float32")
    filled = np.zeros(n, dtype=bool)
    var_pos = {str(v).upper(): i for i, v in enumerate(A.var_names)}
    obs_core = np.array([core(b) for b in A.obs_names])
    samples = (A.obs[sample_key].astype(str).values
               if sample_key and sample_key in A.obs else None)
    notes, used = [], 0

    for src in sources:
        loaded = load(src, log=log)
        if loaded is None:
            continue
        bcs, genes, s_mat, u_mat = loaded

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
        S[np.ix_(dst_rows, dst_cols)] = s_mat[np.ix_(src_rows, src_cols)]
        U[np.ix_(dst_rows, dst_cols)] = u_mat[np.ix_(src_rows, src_cols)]
        filled[dst_rows] = True
        used += 1
        notes.append(f"{src.path.name}: {len(rows):,} cells, {len(keep):,} genes")

    if not used:
        return False, "; ".join(notes) if notes else "no source carried usable counts"

    cov = float(filled.mean())
    log(f"  attached from {used} source(s): {filled.sum():,}/{n:,} cells "
        f"({100 * cov:.1f}%) have spliced/unspliced counts")
    A.layers["spliced"] = sp.csr_matrix(S)
    A.layers["unspliced"] = sp.csr_matrix(U)
    return True, (f"{used} source(s), {filled.sum():,}/{n:,} cells ({100 * cov:.1f}%) covered. "
                  + "; ".join(notes))
