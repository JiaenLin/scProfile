"""Reference data: declared by a plugin, fetched on request, never bundled.

A plugin that runs against a PARTIAL database returns fewer regulons, fewer ligand-receptor pairs,
fewer of whatever it counts — and an under-populated result looks exactly like a real one. So a
missing reference is a REFUSAL by name, not a warning.

WRITTEN FOR FILES THAT ARE GIGABYTES, BECAUSE THEY ARE

The motif databases a regulon method needs are 1–2 GB each and a set of them is tens. Four things
follow, and none of them matters at kilobyte scale:

  resumable      a 2 GB download that dies at 1.9 GB must not start over. HTTP Range, and a
                 `.part` file that is only renamed once the checksum passes.
  cheap checks   hashing 2 GB on every status() call would make `plan` cost minutes. Size is
                 checked first; the digest is cached in a sidecar keyed on size and mtime, and
                 recomputed only when those change or verification is asked for.
  budget first   the total is reported, and the free space checked, BEFORE anything downloads.
                 Filling a filesystem halfway through is a worse failure than refusing at the
                 start.
  a manual route Compute nodes frequently have no outbound network. When a download is
                 impossible the URL, the checksum and the destination are printed for a human to
                 place by hand; the run then proceeds identically, because verification is by
                 checksum rather than by whether this tool did the fetching.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import socket
from pathlib import Path

CHUNK = 1 << 22          # 4 MiB — large enough that a multi-GB file is not a syscall storm


def _sha256(path, chunk=CHUNK, progress=None):
    h = hashlib.sha256()
    seen, total = 0, os.path.getsize(path)
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
            seen += len(b)
            if progress and total:
                progress(seen, total)
    return h.hexdigest()


def _cached_digest(p):
    """The file's digest, recomputed only when its size or mtime has changed.

    Hashing gigabytes on every `plan` would make the cheap command expensive, and a command that
    is expensive stops being run.
    """
    side = p.with_suffix(p.suffix + ".sha256")
    st = p.stat()
    stamp = f"{st.st_size}:{int(st.st_mtime)}"
    if side.exists():
        try:
            cached_stamp, cached = side.read_text().split()[:2]
            if cached_stamp == stamp:
                return cached
        except (ValueError, OSError):
            pass
    got = _sha256(p)
    try:
        side.write_text(f"{stamp} {got}\n")
    except OSError:
        pass
    return got


def _human(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def _declared_bytes(spec):
    s = spec.get("size")
    if isinstance(s, (int, float)):
        return int(s)
    if isinstance(s, str):
        t = s.strip().upper().replace(" ", "")
        for u, m in (("TB", 1 << 40), ("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10), ("B", 1)):
            if t.endswith(u):
                try:
                    return int(float(t[: -len(u)]) * m)
                except ValueError:
                    return 0
    return 0


def status(kernel, dest, organism=None, verify=False):
    """{name: (state, path, detail)} — present / MISSING / WRONG SIZE / CORRUPT.

    `verify=False` checks existence and declared size only, which is what `plan` needs. Pass
    `verify=True` to hash, which is what a run needs before trusting the file.
    """
    out = {}
    for name, spec in kernel.references(organism).items():
        fn = spec.get("filename") or Path(str(spec.get("url", name))).name
        p = Path(dest).expanduser() / kernel.name / fn
        want_bytes = _declared_bytes(spec)
        if not p.exists():
            out[name] = ("MISSING", str(p),
                         f"{_human(want_bytes) if want_bytes else spec.get('size', '?')} "
                         f"from {spec.get('url', '?')}")
            continue
        got_bytes = p.stat().st_size
        if want_bytes and got_bytes != want_bytes:
            out[name] = ("WRONG SIZE", str(p),
                         f"{_human(got_bytes)} on disk, {_human(want_bytes)} declared — "
                         f"an interrupted download, or the file upstream changed")
            continue
        want = str(spec.get("sha256") or "")
        if want and verify:
            got = _cached_digest(p)
            if got != want:
                out[name] = ("CORRUPT", str(p), f"sha256 {got[:12]}… expected {want[:12]}…")
                continue
            out[name] = ("present", str(p), "checksum verified")
            continue
        out[name] = ("present", str(p),
                     "size matches; checksum not verified this call" if want
                     else "NO CHECKSUM DECLARED — this file cannot be verified")
    return out


def plan_fetch(kernel, dest, organism=None):
    """What a fetch would download, how much, and whether it fits. Downloads nothing."""
    st = status(kernel, dest, organism)
    todo = {k: v for k, v in st.items() if v[0] != "present"}
    refs = kernel.references(organism)
    total = sum(_declared_bytes(refs[k]) for k in todo)
    free = shutil.disk_usage(Path(dest).expanduser().parent
                             if Path(dest).expanduser().exists()
                             else Path.cwd()).free
    return {"missing": todo, "bytes": total, "free": free,
            "fits": (total == 0) or (free > total * 1.1)}


class UnsupportedOrganism(FileNotFoundError):
    """The plugin declares reference data, but none for this organism."""


def require_supported(kernel, organism):
    """Refuse when a plugin needs reference data and has none declared for THIS organism.

    Without this the check was skipped whenever `references(organism)` came back empty, and empty
    had two meanings that could not be told apart: this plugin needs no reference data, and this
    plugin's reference data has not been declared for your species. The second one ran.
    """
    have = kernel.reference_organisms()
    if not have:
        return                                   # genuinely needs none, for any organism
    if organism and str(organism).lower() in have:
        return
    raise UnsupportedOrganism(
        f"{kernel.name} needs reference data and declares none for "
        f"{organism!r}. It has references for: {', '.join(sorted(have))}.\n"
        f"  Running it anyway would not fail - it would return a result computed against no "
        f"reference at all, which is the shape of a real answer and is not one.\n"
        f"  Fix: add entries for {organism!r} to {kernel.path / 'references.yml'} and fetch them, "
        f"or pass --organism for a species it already supports.")


def resolve(kernel, dest, organism=None):
    """{name: path} for a run, or raise with EVERY missing reference and how to get them.

    Verifies by checksum: this is the call a run depends on, and a truncated database returns a
    smaller answer rather than an error.
    """
    require_supported(kernel, organism)
    st = status(kernel, dest, organism, verify=True)
    bad = {k: v for k, v in st.items() if v[0] != "present"}
    if bad:
        lines = [f"  {k}: {v[0]} at {v[1]}\n      {v[2]}" for k, v in bad.items()]
        raise FileNotFoundError(
            f"{kernel.name} cannot run: {len(bad)} reference(s) unusable.\n"
            + "\n".join(lines)
            + f"\n  Fix: scprofile fetch {kernel.name} --to {dest}\n"
              f"  Running without them would return a smaller result that looks like a real one.")
    return {k: v[1] for k, v in st.items()}


class _DirLock:
    """One writer per reference directory. A second fetch REFUSES rather than racing.

    Two fetches of the same reference into the same directory both append to the same `.part`
    through resumable Range requests, and the result is a file that is the wrong length or the
    right length with interleaved bytes. Nothing downstream would catch it: a declared sha256
    would - but the case where this matters most is the FIRST download, when there is no declared
    digest, and the digest computed afterwards would then be a digest of the corruption, printed
    as the value to paste in. A blessed wrong checksum is worse than no checksum.

    Held for the whole fetch, released on the way out, and stale-tolerant: a lock whose owning
    process is gone is taken over, because a job killed mid-download must not block the retry.
    """

    def __init__(self, d, log=print):
        self.path, self.log, self.held = Path(d) / ".scprofile_fetch.lock", log, False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {socket.gethostname()}\n".encode())
            os.close(fd)
            self.held = True
        except FileExistsError:
            who = self.path.read_text(encoding="utf-8", errors="replace").strip()
            pid = who.split()[0] if who else ""
            host = who.split()[1] if len(who.split()) > 1 else ""
            mine = host == socket.gethostname()
            alive = False
            if mine and pid.isdigit():
                try:
                    os.kill(int(pid), 0)
                    alive = True
                except (OSError, ProcessLookupError):
                    alive = False
            if alive:
                raise RuntimeError(
                    f"another fetch is already writing to {self.path.parent} (pid {pid} on "
                    f"{host}). Two writers share one .part file and produce a file that is "
                    f"neither download - wait for it, or fetch to a different --to.")
            self.log(f"  taking over a stale fetch lock from {who or 'an unknown process'}")
            self.path.write_text(f"{os.getpid()} {socket.gethostname()}\n", encoding="utf-8")
            self.held = True
        return self

    def __exit__(self, *_exc):
        if self.held:
            self.path.unlink(missing_ok=True)
        return False


def fetch(kernel, dest, organism=None, log=print, dry_run=False):
    """Download what is missing, resumably, and verify it."""
    import urllib.error
    import urllib.request

    pf = plan_fetch(kernel, dest, organism)
    if not kernel.references(organism):
        # ZERO OF ZERO IS NOT "PRESENT". Every plugin with no references.yml reported
        # "all reference(s) present" - a success message for a question nobody asked, and one that
        # reads identically to a plugin whose references really are all on disk. A check that
        # passes for its own reasons is worse than no check.
        log(f"  {kernel.name}: declares no reference data, so there is nothing to fetch")
        return {}
    if not pf["missing"]:
        log(f"  {kernel.name}: all {len(kernel.references(organism))} reference(s) present")
        return status(kernel, dest, organism)
    log(f"  {kernel.name}: {len(pf['missing'])} missing, {_human(pf['bytes'])} to download, "
        f"{_human(pf['free'])} free")
    if not pf["fits"]:
        log(f"  REFUSING: {_human(pf['bytes'])} will not fit in {_human(pf['free'])} with margin. "
            f"Filling a filesystem halfway through is worse than stopping here.")
        return status(kernel, dest, organism)
    recorded = []
    if dry_run:
        for k, v in pf["missing"].items():
            log(f"    would fetch {k}: {v[2]}")
        return status(kernel, dest, organism)

    refs = kernel.references(organism)
    # ONE WRITER. Everything below appends to `.part` files; a second fetch into the same
    # directory produces a file that is neither download, and on a FIRST fetch - where there is
    # no declared digest to catch it - the digest printed afterwards would be the corruption's.
    with _DirLock(Path(dest) / kernel.name, log=log):
        recorded += _download(refs, pf, log)
    _report_digests(recorded, log)
    return status(kernel, dest, organism)


def _download(refs, pf, log):
    """The download loop itself, so the lock above wraps all of it and nothing else."""
    import urllib.error
    import urllib.request
    recorded = []
    for name, (state, path, _d) in pf["missing"].items():
        spec = refs[name]
        url, p = spec.get("url"), Path(path)
        part = p.with_suffix(p.suffix + ".part")
        p.parent.mkdir(parents=True, exist_ok=True)
        have = part.stat().st_size if part.exists() else 0
        log(f"  {name}: {state}" + (f", resuming from {_human(have)}" if have else ""))
        try:
            req = urllib.request.Request(url)
            if have:
                req.add_header("Range", f"bytes={have}-")
            with urllib.request.urlopen(req, timeout=60) as r, \
                    open(part, "ab" if have else "wb") as fh:
                if have and r.status != 206:      # server ignored Range — start over honestly
                    fh.close()
                    part.unlink(missing_ok=True)
                    log("    server does not support resume; restarting")
                    have = 0
                    fh = open(part, "wb")
                seen = have
                while True:
                    b = r.read(CHUNK)
                    if not b:
                        break
                    fh.write(b)
                    seen += len(b)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            log(f"    COULD NOT DOWNLOAD ({type(e).__name__}: {e}). "
                f"{_human(part.stat().st_size) if part.exists() else '0 B'} kept for a retry.")
            log(f"      url    : {url}")
            log(f"      sha256 : {spec.get('sha256', '(none declared)')}")
            log(f"      save to: {p}")
            continue
        # A SHORT READ IS NOT AN ERROR, and that is the whole problem. When a server closes the
        # connection cleanly part-way through, `read()` returns b"" and this loop exits exactly as
        # it does on a complete file - nothing raises, so the `except` above never sees it. Before
        # this check the truncated `.part` was RENAMED to the real name, which did two bad things
        # at once: it destroyed the resume (the `.part` is what Range picks up from), and on a
        # first fetch, where there is no declared digest, it left a short database sitting under
        # the name of a complete one. That is precisely the failure this module's header warns
        # about - a truncated database returns a smaller answer rather than an error.
        #
        # The size is checked FIRST because it is the check that still works when no digest has
        # been declared, which is the case that matters most.
        want_bytes = _declared_bytes(spec)
        got_bytes = part.stat().st_size if part.exists() else 0
        if want_bytes and got_bytes != want_bytes:
            log(f"    INCOMPLETE — {_human(got_bytes)} of {_human(want_bytes)}. The connection "
                f"ended without an error, which is how a truncated file gets the name of a whole "
                f"one. Kept as .part; run the fetch again and it resumes from here.")
            continue
        want = str(spec.get("sha256") or "")
        got = _sha256(part)
        if want and got != want:
            part.unlink(missing_ok=True)
            log(f"    CHECKSUM MISMATCH — deleted. Got {got[:12]}…, expected {want[:12]}…")
            continue
        if not want_bytes:
            # Neither a size nor a digest was declared, so nothing here can tell a complete
            # download from an interrupted one. Say so at the moment it happens rather than
            # leaving it to be inferred from a `validate` warning later.
            log("    NOTE: this entry declares neither size nor sha256, so completeness was not "
                "checked. Declare `size` from the server's Content-Length as well as the digest "
                "printed below.")
        part.rename(p)                              # only now is it a real file
        log(f"    ok -> {p} ({_human(p.stat().st_size)})")
        if not want:
            # THE FIRST DOWNLOAD IS THE ONLY PLACE A DIGEST CAN COME FROM. A vendor who publishes
            # no checksum leaves the author with nothing to declare, and `validate` refuses an
            # undeclared digest - correctly, because a truncated database returns a smaller answer
            # rather than an error. So the digest is computed here and printed as the exact lines
            # to paste, and the file is left unverified until somebody does.
            #
            # Printed, NOT written back. references.yml is tool source; the machine that downloads
            # is not the machine that authors, and a file edited by whichever host ran a fetch is
            # a file with no single origin.
            recorded.append((name, got, p.stat().st_size))
    return recorded


def _report_digests(recorded, log):
    if recorded:
        log("")
        log("  These files declared NO sha256, so nothing verified them. They are on disk and")
        log("  `validate` will keep refusing this plugin until the digests are declared. Paste")
        log("  into references.yml, at the matching entry, having satisfied yourself the source")
        log("  is the one you meant:")
        for name, got, size in recorded:
            log(f"    {name}:")
            log(f"      sha256: {got}")
            log(f"      size: {size}")
