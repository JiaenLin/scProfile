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


def resolve(kernel, dest, organism=None):
    """{name: path} for a run, or raise with EVERY missing reference and how to get them.

    Verifies by checksum: this is the call a run depends on, and a truncated database returns a
    smaller answer rather than an error.
    """
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
    if dry_run:
        for k, v in pf["missing"].items():
            log(f"    would fetch {k}: {v[2]}")
        return status(kernel, dest, organism)

    refs = kernel.references(organism)
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
        want = str(spec.get("sha256") or "")
        if want:
            got = _sha256(part)
            if got != want:
                part.unlink(missing_ok=True)
                log(f"    CHECKSUM MISMATCH — deleted. Got {got[:12]}…, expected {want[:12]}…")
                continue
        part.rename(p)                              # only now is it a real file
        log(f"    ok -> {p} ({_human(p.stat().st_size)})")
    return status(kernel, dest, organism)
