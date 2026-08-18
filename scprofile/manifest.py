"""The contract between the host and a kernel. JSON in, JSON out, validated both ways.

WHY A SCHEMA RATHER THAN A CONVENTION

A kernel runs in its own interpreter, often its own language. The host cannot import it, cannot
catch its exceptions, and must not guess what it wrote. So the kernel DECLARES its output and the
host validates that declaration against this schema before merging anything.

The three states a kernel can leave behind are then distinguishable, which is the whole point:

    out.json absent          the kernel died. The host says so and keeps the stderr.
    out.json, nothing in it  the kernel ran and found nothing. That is a RESULT.
    out.json with entries    the kernel produced these things, and only these are merged.

A convention-based host - glob the output directory - collapses the first two into "no files",
and those are opposite facts.

STDLIB ONLY. This module is imported by every kernel, in every environment, including the R
bridge's python shim. It may not depend on numpy, pandas, anndata or anything else a kernel might
pin differently.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

#: Bumped when the contract changes shape. A kernel built against an older major refuses rather
#: than being read with the wrong expectations.
#: 1.1 added `upstream`, `sentinels` and the `objects` slot. Only the MAJOR is compared, so a
#: kernel written against 1.0 still runs - it simply does not read the new fields.
CONTRACT_VERSION = "1.1"

#: What a kernel may declare it produced. Anything else in `out.json` is ignored with a warning -
#: silently accepting unknown keys is how two versions of a contract drift into three.
#:
#: `objects` exists because not every result is cell-by-something. Velocity is fitted on a
#: SELECTED gene set, so its `velocity`/`Ms`/`Mu` layers are cells x (a few thousand) genes and
#: cannot be merged into an object with the full gene list - padding the rest with zeros would
#: assert that those genes have zero velocity, which is the opposite of "not fitted". A kernel
#: whose result does not fit the merged object ships it as its own file instead.
OUTPUT_SLOTS = ("obs", "obsm", "layers", "tables", "figures", "objects")

#: Statuses a kernel may report. `partial` exists because "it ran, some of it worked" is real and
#: must not be rounded to either success or failure.
STATUSES = ("ok", "partial", "refused")


class ContractError(Exception):
    """The manifest is not something the host can act on. Always names the offending key."""


# ------------------------------------------------------------------------------ host -> kernel

#: Labels an upstream annotator uses to mean "not a cell type". Passed to every kernel because a
#: kernel cannot import the host's `inputs` module - that module needs pandas, and a kernel lives
#: in a pinned environment that may not have the host's version of anything.
DEFAULT_SENTINELS = ("EXCLUDED", "UNRESOLVED")


def write_input(path, *, h5ad, out_dir, keys, organism=None, assay=None, design=None,
                references=None, params=None, upstream=None, sentinels=DEFAULT_SENTINELS,
                contract=CONTRACT_VERSION):
    """Write `in.json`. Every path is made ABSOLUTE first.

    A kernel runs with its own working directory - a different interpreter, sometimes a different
    container - so a relative path in the manifest is a path resolved against somewhere the host
    did not choose. Absolute or nothing.

    `upstream` is {kernel_name: its out_dir} for kernels that have ALREADY RUN in this invocation.
    It is how one kernel reads another's result without the host merging first, and it is the
    mechanism behind `needs_kernels`. The alternative - merge after every kernel and hand the next
    one a rewritten object - would make each kernel's input depend on the order of everything
    before it, and a re-run of one kernel would no longer reproduce.
    """
    payload = {
        "contract": contract,
        "h5ad": str(Path(h5ad).resolve()),
        "out_dir": str(Path(out_dir).resolve()),
        "keys": dict(keys or {}),
        "organism": organism,
        "assay": assay,
        "design": str(Path(design).resolve()) if design else None,
        "references": {k: str(Path(v).resolve()) for k, v in (references or {}).items()},
        "params": dict(params or {}),
        "upstream": {k: str(Path(v).resolve()) for k, v in (upstream or {}).items()},
        "sentinels": list(sentinels or ()),
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def read_input(path):
    """Read `in.json` inside a kernel. Refuses a contract this kernel was not built for."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    got = str(d.get("contract", ""))
    if got.split(".")[0] != CONTRACT_VERSION.split(".")[0]:
        raise ContractError(
            f"in.json declares contract {got!r}; this kernel understands "
            f"{CONTRACT_VERSION!r}. A kernel reading a contract it does not know would act on "
            f"fields that have changed meaning.")
    for req in ("h5ad", "out_dir", "keys"):
        if not d.get(req):
            raise ContractError(f"in.json has no {req!r}")
    # Defaults for the 1.1 fields, so a kernel may read them unconditionally against a host that
    # has not been updated. Absent and empty mean the same thing for all three.
    d.setdefault("upstream", {})
    d.setdefault("sentinels", list(DEFAULT_SENTINELS))
    d.setdefault("params", {})
    return d


# ------------------------------------------------------------------------------ kernel -> host

def write_output(out_dir, *, kernel, version="", status="ok", obs=None, obsm=None, layers=None,
                 tables=None, figures=None, objects=None, absent=None, caveats=None, headline="",
                 contract=CONTRACT_VERSION):
    """Write `out.json` from inside a kernel. The only supported way for a kernel to report.

    `caveats` is not decoration and is not optional in spirit: it is what the report prints under
    the kernel's own results, and a kernel that declares none is asserting that its output can be
    read without qualification. Very few can.

    Paths are recorded RELATIVE to `out_dir`, so a run directory can be moved or promoted by
    hardlink without every manifest in it becoming a lie.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    def rel(v):
        p = Path(v)
        try:
            return str(p.resolve().relative_to(out.resolve()))
        except ValueError:
            return str(v)

    payload = {
        "contract": contract,
        "kernel": kernel,
        "version": str(version),
        "status": status,
        "headline": str(headline),
        "obs": {str(k): rel(v) for k, v in (obs or {}).items()},
        "obsm": {str(k): rel(v) for k, v in (obsm or {}).items()},
        "layers": {str(k): rel(v) for k, v in (layers or {}).items()},
        "tables": [rel(v) for v in (tables or [])],
        "figures": [rel(v) for v in (figures or [])],
        "objects": {str(k): rel(v) for k, v in (objects or {}).items()},
        "absent": [dict(a) for a in (absent or [])],
        "caveats": [str(c) for c in (caveats or [])],
    }
    if status not in STATUSES:
        raise ContractError(f"status {status!r} is not one of {STATUSES}")
    (out / "out.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def read_output(out_dir):
    """Read and VALIDATE a kernel's `out.json`. Returns the payload, or raises ContractError.

    Every declared path is checked to EXIST. A kernel that names a file it did not write is the
    one failure this contract exists to catch: the host would otherwise merge a promise.
    """
    out = Path(out_dir)
    f = out / "out.json"
    if not f.exists():
        raise ContractError(
            f"{f} was not written. The kernel did not finish - which is a different thing from "
            f"finishing with no results, and is why an empty out.json is a valid answer.")
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContractError(f"{f} is not valid JSON: {e}") from None

    got = str(d.get("contract", ""))
    if got.split(".")[0] != CONTRACT_VERSION.split(".")[0]:
        raise ContractError(f"{f} declares contract {got!r}, host understands {CONTRACT_VERSION!r}")
    if d.get("status") not in STATUSES:
        raise ContractError(f"{f} declares status {d.get('status')!r}, not one of {STATUSES}")
    if not d.get("kernel"):
        raise ContractError(f"{f} does not say which kernel wrote it")

    missing = []
    for slot in ("obs", "obsm", "layers", "objects"):
        for k, v in (d.get(slot) or {}).items():
            if not (out / v).exists():
                missing.append(f"{slot}[{k}] -> {v}")
    for slot in ("tables", "figures"):
        for v in (d.get(slot) or []):
            if not (out / v).exists():
                missing.append(f"{slot} -> {v}")
    if missing:
        raise ContractError(
            f"{d['kernel']} declared {len(missing)} output(s) that do not exist on disk:\n  "
            + "\n  ".join(missing[:8])
            + "\nA declaration the host cannot verify is worse than no declaration: it would be "
              "merged as a promise.")
    d.setdefault("caveats", [])
    d.setdefault("absent", [])
    d.setdefault("objects", {})
    return d


def unknown_keys(payload):
    """Keys in a manifest the host does not act on. Reported, never silently accepted."""
    known = {"contract", "kernel", "version", "status", "headline", "absent", "caveats"}
    return sorted(set(payload) - known - set(OUTPUT_SLOTS))


def env_for_kernel(inp):
    """The environment a kernel entry point is run with. Kept here so host and kernel agree.

    `SCPROFILE_IN` is how a kernel in any language finds its manifest without argument parsing -
    the R bridge reads the same variable.
    """
    e = dict(os.environ)
    e["SCPROFILE_IN"] = str(inp)
    e["SCPROFILE_CONTRACT"] = CONTRACT_VERSION
    return e
