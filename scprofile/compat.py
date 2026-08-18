"""Making one interpreter's `.h5ad` readable by another's.

THE HAZARD AT THE CENTRE OF THE PLUGIN DESIGN

A kernel runs in a pinned environment precisely so it can hold versions the host does not. The
cost of that is a version skew in the ONE thing they must both understand: the object.

It is not hypothetical and it is not rare. On pandas >= 3 a string column cannot be held as
`object` - the new `str` dtype is the default and pandas coerces back to it - and anndata >= 0.11
writes that dtype as a NULLABLE STRING: a group of `values` + `mask` rather than a dataset. The
file is valid AnnData and round-trips through its own writer perfectly. An older anndata raises:

    IORegistryError: No read method registered for IOSpec(encoding_type='nullable-string-array')
    Error raised while reading key '_index' of <class 'h5py._hl.group.Group'> from /obs

So a user on a current stack, having installed everything correctly, watches a kernel die on the
first line - with a message about an IO registry, which points nowhere near pandas.

THE HOST'S JOB, NOT THE KERNEL'S

The host is the only party that can see both sides, so it probes the kernel's own interpreter
BEFORE launching it, and if the object cannot be read there it writes one compatibility copy in
the classic encoding and points every kernel at that instead. Written once and reused, from the
object already in memory, so it costs one write rather than a read and a write.

The classic encoding is the COMPATIBLE direction: string datasets are what every reader expects,
so the copy is readable by more things, not fewer.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

#: Reads obs and var - which is where the failure is - without touching X.
_PROBE = (
    "import sys, anndata as ad\n"
    "A = ad.read_h5ad(sys.argv[1], backed='r')\n"
    "_ = list(A.obs_names[:1]), list(A.var_names[:1]), list(A.obs.columns)\n"
    "print('READABLE', ad.__version__)\n"
)


class classic_string_encoding:
    """Write string columns as HDF5 string DATASETS, not as nullable-string groups.

    Scoped rather than set once at import, because it is a global on the anndata module and this
    library has no business changing how objects written elsewhere in the caller's process are
    stored. Restored even if the write raises.

    Duplicated from its sibling tools rather than imported from one, deliberately: this package
    must write a readable file without any of them present, and a guarantee about the output
    cannot be held in a dependency the output does not otherwise need.
    """

    def __init__(self):
        self._prev = None
        self._had = False

    def __enter__(self):
        try:
            import anndata as ad
            self._prev = ad.settings.allow_write_nullable_strings
            ad.settings.allow_write_nullable_strings = False
            self._had = True
        except Exception:                                                  # noqa: BLE001
            self._had = False        # older anndata has no such setting and does not need one
        return self

    def __exit__(self, *exc):
        if self._had:
            import anndata as ad
            ad.settings.allow_write_nullable_strings = self._prev
        return False


def can_read(python_exe, h5ad, timeout=300):
    """Can THAT interpreter read this object? Returns (ok, detail).

    Asked of the interpreter itself rather than inferred from version numbers, because the
    question is what its anndata's IO registry actually has a reader for - and that is a fact
    about an install, not about a version string.
    """
    try:
        r = subprocess.run([str(python_exe), "-c", _PROBE, str(h5ad)],
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"could not probe {python_exe}: {e}"
    if r.returncode == 0:
        return True, (r.stdout or "").strip()
    tail = [ln for ln in (r.stderr or "").strip().splitlines() if ln.strip()]
    return False, tail[-1] if tail else f"exited {r.returncode}"


def write_compatible(adata, path, *, log=print):
    """One copy in the classic string encoding, from the object already in memory."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    log(f"  writing a compatibility copy in the classic string encoding -> {p.name}")
    with classic_string_encoding():
        adata.write_h5ad(p)
    log(f"  {p.stat().st_size / 1e9:.2f} GB")
    return p


def readable_input(adata, h5ad, python_exe, workdir, *, cache, log=print):
    """The path to hand a kernel running under `python_exe`, converting once if it must.

    `cache` is a dict owned by the caller so the conversion happens at most once per run no matter
    how many kernels need it, and the probe at most once per distinct interpreter.
    """
    exe = str(python_exe)
    if exe in cache.get("probed", {}):
        return cache["probed"][exe]
    cache.setdefault("probed", {})

    ok, detail = can_read(exe, h5ad)
    if ok:
        cache["probed"][exe] = Path(h5ad)
        return Path(h5ad)

    log(f"  this kernel's interpreter cannot read the object as written:")
    log(f"    {detail}")
    conv = cache.get("converted")
    if conv is None:
        conv = write_compatible(adata, Path(workdir) / "input_classic_strings.h5ad", log=log)
        cache["converted"] = conv
    ok2, detail2 = can_read(exe, conv)
    if not ok2:
        log(f"  the compatibility copy did not help either: {detail2}")
        cache["probed"][exe] = None
        return None
    log(f"  the compatibility copy is readable there; using it")
    cache["probed"][exe] = conv
    return conv
