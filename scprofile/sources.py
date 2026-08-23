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
from .provenance import PRUNE, WALK_CAP, WALK_DEPTH   # noqa: F401  (re-exported)

#: 10x-style barcodes are ACGT runs. Pulling the longest one out of a name absorbs sample
#: prefixes, `-1` suffixes and velocyto's trailing `x` in a single rule. A name with no such run
#: falls back to itself, so non-10x data still matches when the strings agree exactly.
_CORE = re.compile(r"[ACGTN]{8,}")

#: Directories never worth descending into, and HOW FAR TO GO - both taken from `provenance`,
#: which is where the PLANNER'S copy of this walk lives.
#:
#: THE PLAN AND THE RUN MUST REACH THE SAME DISTANCE, and they did not. The planner walked to
#: depth 14 with 400,000 visits and pruned `<sample>__STARtmp` by substring; this walked to depth
#: 3 with 4,000 visits and an exact-name skip list that `S1__STARtmp` does not match. Measured
#: on real aligner output: STARsolo delivers `<sample>_Solo.out/Velocyto/filtered/` at depth 9
#: below a project root, so `plan` could say "your spliced counts are here, pass --search <root>"
#: and the run, given exactly that root, could not reach them - and would refuse with a list of
#: everywhere it had looked, none of which was deep enough. A plan that promises what the run
#: cannot deliver is worse than a plan that promises nothing.
_SKIP = {"logs", "figures", "reports", "report", "tmp"}
MAX_DEPTH = WALK_DEPTH
MAX_DIRS = WALK_CAP
MIN_MATCH = 0.5


def _pruned(name):
    """Substring, not name. The directory is `<sample>__STARtmp`, and an exact-name skip list
    walks straight into it - which is what exhausts a visit budget before the real output two
    levels away is reached."""
    return name in _SKIP or any(pat in name for pat in PRUNE)

#: The layer pair this was written for, and the only one any shipped plugin asks for today. It is
#: a DEFAULT and not a definition: every function below takes `names`, so a plugin needing some
#: other aligner-written pair gets the same search rather than a copy of it. The names are the
#: host's own capability vocabulary (`declare.CAPABILITIES`), never a project's column.
DEFAULT_LAYERS = ("spliced", "unspliced")


def core(name):
    m = _CORE.findall(str(name).upper())
    return max(m, key=len) if m else str(name)


class Source:
    """One place the wanted layers were found, and what is known about it before opening it.

    `size` is the bytes that would have to be read, taken from the directory entry rather than by
    opening anything. It is what lets `attach` try the cheapest source first, which matters
    because an aligner writes the SAME counts twice: STARsolo delivers `Velocyto/filtered/` beside
    `Velocyto/raw/`, and the raw triplet is every droplet rather than every cell - 1.1 GB against
    242 MB per matrix on a real run, for the identical cells once the barcodes are matched.
    """

    def __init__(self, kind, path, sample=None, why="", size=0):
        self.kind, self.path, self.sample, self.why = kind, Path(path), sample, why
        self.size = int(size or 0)

    def __repr__(self):
        return f"<{self.kind} {self.path}{' sample=' + self.sample if self.sample else ''}>"


def _size(entry):
    """Bytes, from the directory entry. Never opens the file."""
    try:
        return entry.stat().st_size if entry is not None else 0
    except OSError:
        return 0


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
    looked, exhausted = [], False
    for root in search_paths:
        r = Path(root)
        if not r.is_dir():
            continue
        looked.append(str(r))
        stack = [(r, 0)]
        while stack:
            if visited >= MAX_DIRS:
                # A SEARCH THAT GAVE UP MUST NOT LOOK LIKE ONE THAT FINISHED. Returning the same
                # empty list either way turns a fact about the SCAN into a fact about the project.
                exhausted = True
                break
            d, depth = stack.pop()
            rd = str(d.resolve())
            if rd in seen_dirs:
                continue
            seen_dirs.add(rd)
            visited += 1
            try:
                entries = list(os.scandir(d))
            except OSError:
                # A directory that could not be READ is not a directory known to be empty.
                exhausted = True
                continue
            entry_names = {e.name for e in entries}
            # An mtx triplet: spliced/unspliced matrices beside a barcode list. This is what
            # STARsolo's Velocyto output and several other quantifiers write.
            by_name = {e.name: e for e in entries}
            mtx = [[n for n in entry_names if re.match(rf"^{re.escape(w)}\.mtx(\.gz)?$", n)]
                   for w in names]
            bc = [n for n in entry_names if re.match(r"^barcodes\.tsv(\.gz)?$", n)]
            if all(mtx) and bc:
                found.append(Source("mtx", d, _sample_from(d, sample_hints),
                                    " + ".join(f"{w}.mtx" for w in names) + " + barcodes.tsv",
                                    size=sum(_size(by_name.get(m[0])) for m in mtx)))
            for e in entries:
                if e.is_file():
                    if e.name.endswith(".loom"):
                        found.append(Source("loom", e.path, _sample_from(e.path, sample_hints),
                                            "a .loom, which velocyto writes", size=_size(e)))
                    elif e.name.endswith(".h5ad") and "velocity" not in e.name:
                        found.append(Source("h5ad", e.path, _sample_from(e.path, sample_hints),
                                            "an .h5ad - checked for the wanted layers",
                                            size=_size(e)))
                elif e.is_dir(follow_symlinks=False) and not _pruned(e.name) \
                        and not e.name.startswith("."):
                    if depth >= max_depth:
                        exhausted = True      # there was more tree and we stopped looking
                        continue
                    stack.append((Path(e.path), depth + 1))
    find.looked = looked
    find.visited = visited
    find.exhausted = exhausted
    return found


find.looked = []
find.visited = 0
find.exhausted = False


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

        def _read_list(f, col=0):
            import gzip
            op = gzip.open if str(f).endswith(".gz") else open
            with op(f, "rt") as fh:
                out = []
                for ln in fh:
                    if not ln.strip():
                        continue
                    parts = ln.rstrip("\n").split("\t")
                    out.append((parts[col] if col < len(parts) else parts[0]).strip())
                return out

        fb, fg = _p("barcodes.tsv"), _p("features.tsv", "genes.tsv")
        fm = [_p(f"{w}.mtx") for w in names]
        if not all([fb, fg] + fm):
            return None
        bcs = _read_list(fb)
        # EVERY COLUMN OF features.tsv IS A CANDIDATE GENE NAME, and which one the object uses is
        # the object's business. The 10x/STARsolo convention is `<gene id>\t<symbol>\t<type>`;
        # this read column 0 while the object is indexed by SYMBOLS, so on a real cohort it
        # matched 466 of 34,290 genes, `filter_and_normalize` then dropped 34,286 for want of
        # shared counts, and velocity refused because "only 4 genes survived selection" - a
        # refusal about the DATA whose cause was a column index. Both columns are returned;
        # `attach` takes whichever overlaps the object more and says which, and by how much.
        genes = [_read_list(fg, c) for c in (0, 1)]
        mats = [scipy.io.mmread(str(f)).tocsr() for f in fm]
        # mtx from these quantifiers is genes x cells; orient by which axis matches the lists.
        # `len(genes)` IS NOT THE GENE COUNT any more - `genes` is one list per field of
        # features.tsv - and using it here compared 34,290 against 2, refused every source as
        # "matches neither N barcodes nor 2 genes", and turned a fix into a total failure to
        # source anything. Measured on PBS 677757, on the run that was meant to prove the fix.
        n_genes = len(genes[0])
        if mats[0].shape[0] == n_genes and mats[0].shape[1] == len(bcs):
            mats = [m.T.tocsr() for m in mats]
        if mats[0].shape[0] != len(bcs):
            log(f"    {d}: {mats[0].shape} matches neither {len(bcs)} barcodes nor "
                f"{n_genes} genes")
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
    # COO PIECES, ASSEMBLED ONCE. This built a `lil_matrix((n_obs, n_vars))` per layer and
    # assigned each source into it with `D[np.ix_(dst_rows, dst_cols)] = M[...]`. That is correct
    # and it does not survive a real object: a LIL is a Python list per row, so a hundred thousand
    # cells by thirty-four thousand genes at ~150 million nonzeros per layer is tens of GB of
    # interpreter objects, filled one source at a time through scipy's Python-level fancy-index
    # assignment, and then converted. Nothing had ever run it - velocity refused for want of
    # counts in every previous cycle - so the cost was unmeasured rather than accepted.
    #
    # Row, column and value arrays per source, concatenated once at the end, is the same result
    # in numpy: int32 indices (n_obs and n_vars are both far below 2^31) and float32 values.
    pieces = [[] for _ in names]
    filled = np.zeros(n, dtype=bool)
    var_pos = {str(v).upper(): i for i, v in enumerate(A.var_names)}
    obs_core = np.array([core(b) for b in A.obs_names])
    samples = (A.obs[sample_key].astype(str).values
               if sample_key and sample_key in A.obs else None)
    notes, used, skipped = [], 0, 0

    # CHEAPEST FIRST, AND STOP WHEN EVERY CELL IS COVERED. An aligner writes the same counts
    # twice - STARsolo's `Velocyto/raw/` is every droplet and `Velocyto/filtered/` is every cell,
    # and once the barcodes are matched they give the identical answer for the cells in this
    # object. On a real ten-sample project that is 22 GB of MatrixMarket text read, parsed and
    # discarded for nothing, and it is the difference between this step taking minutes and taking
    # an afternoon. Ordering by the size on the directory entry needs no pipeline's vocabulary and
    # no filename convention: the smaller source that covers the same cells IS the cheaper correct
    # answer. Ties break on the path so a run is reproducible.
    for src in sorted(sources, key=lambda s: (s.size, str(s.path))):
        # Restrict to this source's sample when it names one. The same core barcode legitimately
        # recurs across samples, and matching globally would give one animal's unspliced counts
        # to another's cell - which produces a full matrix and a wrong answer.
        if src.sample is not None and samples is not None:
            scope = np.where(samples == src.sample)[0]
            scope_why = f"within sample {src.sample}"
        else:
            scope = np.arange(n)
            scope_why = "across all cells (the source names no sample)"

        # DECIDED BEFORE OPENING IT. The scope comes from the source's PATH, so a source whose
        # cells are already covered is skipped without being read - which is the whole saving,
        # because an aligner writes `Velocyto/raw/` (every droplet, 1.1 GB per matrix) beside
        # `Velocyto/filtered/` (every cell, 242 MB), the small one is tried first, and the large
        # one adds nothing once its sample is complete. Scoped rather than global, so a sample
        # the small copy did NOT cover still gets the large one tried.
        if len(scope) == 0 or filled[scope].all():
            skipped += 1
            continue
        loaded = load(src, log=log, names=names)
        if loaded is None:
            continue
        bcs, genes, mats = loaded

        want = {}
        for j, b in enumerate(bcs):
            want.setdefault(core(b), j)
        matched = [(i, want[obs_core[i]]) for i in scope if obs_core[i] in want]
        rate = len(matched) / max(1, len(scope))
        log(f"    {src.kind}  {src.path.name}: {len(matched):,}/{len(scope):,} barcodes matched "
            f"({100 * rate:.1f}%) {scope_why}")
        if rate < min_match:
            notes.append(f"{src.path.name} matched only {100 * rate:.1f}% and was NOT used")
            continue
        # A CELL IS FILLED ONCE, BY THE FIRST SOURCE THAT COVERS IT - which, given the ordering
        # above, is the cheapest. The old code overwrote, so the winner was whichever source came
        # last in an unspecified order; taking the first makes it deterministic AND means the
        # concatenated pieces below hold no duplicate (row, column), which would otherwise be
        # summed rather than replaced.
        rows = [(i, j) for i, j in matched if not filled[i]]
        if not rows:
            notes.append(f"{src.path.name}: every cell it matched was already covered")
            continue

        # WHICHEVER COLUMN THE OBJECT SPEAKS. A source may offer gene ids and symbols; the
        # object uses one of them, and choosing the wrong one produces a full, valid, nearly-empty
        # matrix rather than an error.
        options = genes if genes and isinstance(genes[0], list) else [genes]
        best, best_keep = 0, []
        for ci, col in enumerate(options):
            gcols = [var_pos.get(str(gn).upper()) for gn in col]
            hit = [(k, c) for k, c in enumerate(gcols) if c is not None]
            if len(hit) > len(best_keep):
                best, best_keep = ci, hit
        keep = best_keep
        if not keep:
            notes.append(f"{src.path.name}: no gene name overlapped the object")
            log(f"      no gene name overlapped the object - not used")
            continue
        if len(options) > 1:
            log(f"      gene names: field {best} of {len(options)} overlaps most "
                f"({len(keep):,} of {len(options[best]):,})")
        src_cols = np.array([k for k, _ in keep])
        dst_cols = np.array([c for _, c in keep], dtype="int32")
        src_rows = np.array([j for _, j in rows])
        dst_rows = np.array([i for i, _ in rows], dtype="int32")
        for bucket, M in zip(pieces, mats):
            sub = M[np.ix_(src_rows, src_cols)].tocoo()
            bucket.append((dst_rows[sub.row], dst_cols[sub.col],
                           np.asarray(sub.data, dtype="float32")))
        filled[dst_rows] = True
        used += 1
        notes.append(f"{src.path.name}: {len(rows):,} cells, {len(keep):,} genes")

    if not used:
        return False, "; ".join(notes) if notes else "no source carried usable counts"

    if skipped:
        log(f"  {skipped} further candidate(s) not opened: every cell was already covered")
        notes.append(f"{skipped} further candidate(s) were not opened - every cell was already "
                     f"covered by a smaller source")
    cov = float(filled.mean())
    log(f"  attached from {used} source(s): {filled.sum():,}/{n:,} cells "
        f"({100 * cov:.1f}%) have {'/'.join(names)} counts")
    for w, bucket in zip(names, pieces):
        if bucket:
            r = np.concatenate([x[0] for x in bucket])
            c = np.concatenate([x[1] for x in bucket])
            v = np.concatenate([x[2] for x in bucket])
        else:
            r = c = np.zeros(0, dtype="int32")
            v = np.zeros(0, dtype="float32")
        A.layers[w] = sp.coo_matrix((v, (r, c)), shape=(n, g), dtype="float32").tocsr()
    return True, (f"{used} source(s), {filled.sum():,}/{n:,} cells ({100 * cov:.1f}%) covered. "
                  + "; ".join(notes))
