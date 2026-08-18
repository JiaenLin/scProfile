"""Reference data: declared by a kernel, fetched on request, never bundled.

A kernel that runs against a PARTIAL database returns fewer regulons, fewer ligand-receptor pairs,
fewer of whatever it counts - and an under-populated result looks exactly like a real one. So a
missing reference is a REFUSAL by name, not a warning.

Compute nodes frequently have no outbound network. When a download is impossible, the URL, the
checksum and the destination are printed for a human to place by hand; the run then proceeds
identically, because verification is by checksum rather than by whether this tool did the fetching.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def _sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def status(kernel, dest, organism=None):
    """{name: (state, path, detail)} where state is present / MISSING / CORRUPT."""
    out = {}
    for name, spec in kernel.references(organism).items():
        fn = spec.get("filename") or Path(str(spec.get("url", name))).name
        p = Path(dest).expanduser() / kernel.name / fn
        if not p.exists():
            out[name] = ("MISSING", str(p), f"{spec.get('size', '?')} from {spec.get('url', '?')}")
            continue
        want = str(spec.get("sha256") or "")
        if want:
            got = _sha256(p)
            if got != want:
                out[name] = ("CORRUPT", str(p),
                             f"sha256 {got[:12]}... expected {want[:12]}...")
                continue
        out[name] = ("present", str(p), "checksum verified" if want else "no checksum declared")
    return out


def resolve(kernel, dest, organism=None):
    """{name: path} for a run, or raise with EVERY missing reference and how to get them."""
    st = status(kernel, dest, organism)
    bad = {k: v for k, v in st.items() if v[0] != "present"}
    if bad:
        lines = [f"  {k}: {v[0]} at {v[1]}\n      {v[2]}" for k, v in bad.items()]
        raise FileNotFoundError(
            f"{kernel.name} cannot run: {len(bad)} reference(s) unusable.\n"
            + "\n".join(lines)
            + f"\n  Fix: scprofile fetch {kernel.name} --to {dest}\n"
              f"  Running without them would return a smaller result that looks like a real one.")
    return {k: v[1] for k, v in st.items()}


def fetch(kernel, dest, organism=None, log=print):
    """Download what is missing and verify it. Prints the manual route when there is no network."""
    import urllib.error
    import urllib.request
    st = status(kernel, dest, organism)
    todo = {k: v for k, v in st.items() if v[0] != "present"}
    if not todo:
        log(f"  {kernel.name}: all {len(st)} reference(s) present and verified")
        return st
    for name, (state, path, _detail) in todo.items():
        spec = kernel.references(organism)[name]
        url = spec.get("url")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        log(f"  {name}: {state} -> fetching {spec.get('size', '')} from {url}")
        try:
            urllib.request.urlretrieve(url, p)
        except (urllib.error.URLError, OSError) as e:
            log(f"    COULD NOT DOWNLOAD ({type(e).__name__}). Place it by hand:")
            log(f"      url    : {url}")
            log(f"      sha256 : {spec.get('sha256', '(none declared)')}")
            log(f"      save to: {p}")
            continue
        want = str(spec.get("sha256") or "")
        if want and _sha256(p) != want:
            p.unlink(missing_ok=True)
            log(f"    CHECKSUM MISMATCH - deleted. The download was corrupt or the URL moved.")
        else:
            log(f"    ok -> {p}")
    return status(kernel, dest, organism)
