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
#: 1.2 added `upstream_units`. 1.1 added `upstream`, `sentinels` and the `objects` slot. Only the
#: MAJOR is compared, so a
#: kernel written against 1.0 still runs - it simply does not read the new fields.
# 1.4 adds the optional `contradictions` key: the claims a plugin made AGAINST ITS OWN RESULT.
# They were recorded only into `caveats`, where they are one sentence among ten and nothing
# downstream can tell them apart - so the reporter could not show a refutation where the claim
# is, and the exit standard could not check that it had. A field of its own is what makes the
# absence of one detectable.
# 1.3 adds the optional `metrics` key: one comparable number per instance, so a per-unit
# plugin's units can be put on one axis. A MINOR bump because compatibility is gated on
# the major version and a reader that does not know the key ignores it.
CONTRACT_VERSION = "1.4"

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


def _host_version():
    """Deferred import: `landscape` imports nothing from here, and this keeps it that way."""
    try:
        from .landscape import host_version
        return host_version()
    except Exception:                                                     # noqa: BLE001
        return None


def write_input(path, *, h5ad, out_dir, keys, organism=None, assay=None, design=None,
                references=None, reference_specs=None, params=None, upstream=None,
                upstream_units=None, sentinels=DEFAULT_SENTINELS,
                provenance=None, resources=None, unit=None, unit_members=None,
                unit_axis=None, figures_for=None,
                constraint="", cache_dir=None,
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

    A PER-UNIT UPSTREAM HAS NO SINGLE out_dir, and pretending otherwise is how this went wrong: it
    was written once per instance under the plugin's name, so a ten-unit upstream left ONE
    directory - the last that succeeded, which changes between runs as different units fail - and
    the downstream read one sample as the cohort's result with nothing recording which. So:

      `upstream[name]`        set ONLY when the host can name one correct directory: the upstream
                              ran once, or the reader is per-unit on the same key and gets its own
                              unit's. ABSENT when neither holds - and a consumer indexing a
                              missing key fails loudly, which is the point.
      `upstream_units[name]`  {unit: out_dir} for every unit that succeeded, always. A method that
                              genuinely needs all of them - the cross-sample comparisons this
                              design exists for - reads this.
    """
    payload = {
        "contract": contract,
        # THE HOST CODE THAT DECIDES WHAT THIS INSTANCE WILL CONTAIN. Part of the reuse
        # key: without it a run made after a host change adopts instances from before it,
        # and the change never reaches them. See `landscape.HOST_MODULES`.
        "host_version": _host_version(),
        "h5ad": str(Path(h5ad).resolve()),
        "out_dir": str(Path(out_dir).resolve()),
        "keys": dict(keys or {}),
        "organism": organism,
        "assay": assay,
        "design": str(Path(design).resolve()) if design else None,
        # THE UPSTREAM CONSTRAINT ON USE, verbatim. `_entry.py` has read `d["constraint"]` to
        # build the plugin's Guard since guard mode existed, and NOTHING EVER WROTE IT - so a
        # guard that consults the constraint has been reading None in every run, and a guard that
        # would have refused was silently permissive. Third field in this contract with that
        # shape, after the reference specs and the core budget.
        "constraint": str(constraint or ""),
        # A DIRECTORY THAT SURVIVES THE RUN, for a plugin to keep an expensive intermediate in.
        # The instance directory does not survive: a plugin that saved its fitted object there
        # found an empty directory on every new run, so a change to a PLOT paid for the whole
        # inference again - measured at 2m41s and 7.5 GB per unit, eighteen units, to redraw a
        # figure. The host only says WHERE; what to keep and under what key is the plugin's, and
        # a plugin that needs none ignores it.
        "cache_dir": str(Path(cache_dir).resolve()) if cache_dir else None,
        "references": {k: str(Path(v).resolve()) for k, v in (references or {}).items()},
        # THE DECLARATIONS BEHIND THOSE PATHS, so a plugin can ask for one BY ROLE. Without them
        # `ctx.reference_for_role` has nothing to search and returns None for every role, for
        # every plugin, always - which is not a degraded answer, it is the whole mechanism that
        # keeps a SPECIES out of a plugin failing closed. The mouse and human entries of one
        # reference are different files with different names, so a plugin asking by NAME has to
        # know both and pick, and picking is the one thing no plugin may do.
        "reference_specs": {str(k): {kk: (str(vv) if not isinstance(vv, (int, float, bool))
                                          else vv)
                                     for kk, vv in dict(v).items()}
                            for k, v in (reference_specs or {}).items()
                            if isinstance(v, dict)},
        "params": dict(params or {}),
        "upstream": {k: str(Path(v).resolve()) for k, v in (upstream or {}).items()},
        "upstream_units": {k: {str(u): str(Path(d).resolve()) for u, d in (v or {}).items()}
                           for k, v in (upstream_units or {}).items()},
        "sentinels": list(sentinels or ()),
        # What the upstream tools recorded about where this object came from. Harvested by the
        # host because `uns` is dropped from the kernel copy, and because a kernel needing a file
        # that is not IN the object still needs to be told where to look. Plain JSON, so it
        # crosses every version boundary the object itself cannot.
        "provenance": dict(provenance or {}),
        # THE CORE SHARE, not the machine's. A plugin calling os.cpu_count() reports the node
        # rather than its share, so four concurrent plugins each start the node's worth of
        # threads and the wave runs slower than serial. Plugins are required to use this.
        "resources": dict(resources or {}),
        "unit": unit,
        # THE SAMPLES THIS UNIT COVERS. One for a sample unit, several for a design arm. `_entry`

        # subsets by membership in this list, which is what lets a plugin be invoked once per arm

        # over the arm's pooled cells rather than once per sample.

        "unit_members": list(unit_members) if unit_members else None,
        # WHICH AXIS THIS UNIT CAME FROM, and which axes this run wants figures for. Both are
        # the host's knowledge, not the plugin's: the resolver named the axes and the run was
        # asked which of them to draw.
        "unit_axis": str(unit_axis) if unit_axis else None,
        "figures_for": list(figures_for) if figures_for else None,
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
    d.setdefault("upstream_units", {})
    d.setdefault("reference_specs", {})
    d.setdefault("sentinels", list(DEFAULT_SENTINELS))
    d.setdefault("params", {})
    d.setdefault("provenance", {})
    d.setdefault("resources", {})
    d.setdefault("unit", None)
    return d


# ------------------------------------------------------------------------------ kernel -> host

def layer_names(adata):
    """The layer names an object actually HAS. Not `list(adata.layers)`, and here is why.

    Measured on anndata 0.13.2 (PBS 672521), and the last line settles it:

        bare AnnData, no layers assigned     list(adata.layers) == [None]
        adata.layers[None]                   -> the X matrix itself, (n_obs, n_vars)
        h5py /layers on disk                 exactly the real names. NO None, either from
                                             anndata's own writer or from ours.

    So `None` is anndata's in-memory alias for X - the same `layer=None` that scanpy functions
    take to mean "use X" - and iterating the mapping now yields it. It is not persisted and it is
    not something this project creates.

    That makes it harmless and easy to get wrong twice. `sorted(adata.layers)` raises TypeError
    the moment a real layer exists, and a plugin that iterates layers to decide what it was given
    is told about a layer that is X under another name. The guard was already written EIGHT times
    across five files with no comment in any of them, which is how the ninth copy comes to be the
    one that forgets.

    Lives in manifest.py because that is the only host module a kernel may import.
    """
    return sorted(str(k) for k in getattr(adata, "layers", ()) if k is not None)


def write_output(out_dir, *, kernel, version="", status="ok", obs=None, obsm=None, layers=None,
                 tables=None, figures=None, objects=None, absent=None, caveats=None, headline="",
                 measured=None, metrics=None, contradictions=None, config=None,
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
        # ONE NUMBER PER INSTANCE, comparable across units. See Context.metric.
        "metrics": {str(k): float(v) for k, v in (metrics or {}).items()},
        # WHAT THIS UNIT ACTUALLY RAN WITH, resolved - defaults filled in, overrides applied.
        # It was recorded NOWHERE. A run could not say which parameters produced it, a reader
        # could not tell a default from a choice, and a written section quoting a number had no
        # way to state the settings behind it. Every value here is JSON-safe or dropped.
        "config": {str(k): v for k, v in (config or {}).items()
                   if isinstance(v, (str, int, float, bool)) or v is None},
        "kernel": kernel,
        "version": str(version),
        # WHAT THIS INSTANCE ACTUALLY COST, from the process that paid it: peak RSS,
        # the cells it processed, and the GB-per-100k the allocator wants declared.
        # Absent when the platform could not report it, which is not zero.
        "measured": dict(measured) if measured else None,
        "status": status,
        "headline": str(headline),
        "obs": {str(k): rel(v) for k, v in (obs or {}).items()},
        "obsm": {str(k): rel(v) for k, v in (obsm or {}).items()},
        "layers": {str(k): rel(v) for k, v in (layers or {}).items()},
        "tables": [rel(v) for v in (tables or [])],
        "figures": [_figure(v, rel) for v in (figures or [])],
        "objects": {str(k): rel(v) for k, v in (objects or {}).items()},
        "absent": [dict(a) for a in (absent or [])],
        "caveats": [str(c) for c in (caveats or [])],
        # WHAT THE PLUGIN SAID AGAINST ITS OWN HEADLINE. Kept apart from `caveats` - which it
        # is also recorded in, so no existing reader loses it - because a refutation that
        # cannot be distinguished from a qualification cannot be shown where the claim is, and
        # its absence cannot be noticed by anything.
        "contradictions": [str(c) for c in (contradictions or [])],
    }
    if status not in STATUSES:
        raise ContractError(f"status {status!r} is not one of {STATUSES}")
    (out / "out.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def _figure(v, rel):
    """A figure entry: a bare path, or a mapping with a caption, a vector copy and source data.

    Both forms are accepted because a kernel should be able to declare a figure in one line while
    it is being written, and grow the caption and the source table later. The report renders
    whichever it is given, and says so when a figure arrives with no source data - "the numbers
    behind this figure are not on disk" is a fact a reader is entitled to.

    THE ID IS CARRIED, and it was not. This function builds a fresh mapping from a fixed list of
    keys, written before `report.figures` existed, so every panel arrived at the host with its id
    stripped - the join between what a plugin DECLARED and what it DREW, severed at serialisation
    with nothing at either end to notice. Measured on the first real run: nine panels emitted with
    their ids, nine recorded as `null`, and the drift check that exists to catch exactly that
    reported clean.

    For the bare-path form the id is the file's stem, which is what `emit_figure` names it after
    anyway - so a plugin that declares `{"id": "confidence"}` and writes `confidence.png` joins up
    whichever form it used.
    """
    if isinstance(v, dict):
        e = {"id": str(v.get("id") or Path(str(v["path"])).stem),
             "path": rel(v["path"]), "caption": str(v.get("caption") or "")}
        for k in ("vector", "source"):
            if v.get(k):
                e[k] = rel(v[k])
        # THE DRAWING AUDIT TRAVELS WITH THE FIGURE, and this serialiser is why it did not.
        # SECOND TIME. The paragraph above records the id being stripped here for the same
        # reason: this builds a fresh mapping from a fixed list of keys, so anything
        # `emit_figure` learns about a panel and is not on that list is dropped between the
        # plugin and the run. The audit ran on all 223 panels of a real run, found what it found,
        # and none of it arrived.
        #
        # The whitelist is right - a plugin must not be able to inject arbitrary keys into the
        # payload - so the fix is the entry, not the design. What this needs and does not have is
        # a check that every key `emit_figure` writes is one this function carries; until then,
        # the next key added will be dropped exactly like the last two.
        # ALWAYS WRITTEN, EVEN EMPTY, and that is the whole point. Writing it only when
        # something was found makes "measured and clean" indistinguishable from "never
        # measured" - the absence-is-not-one-thing defect this tool corrects on four panels,
        # committed here in its own metadata. An empty list is a RESULT: every artist was
        # measured and none collided. A missing key is a run made before the audit existed.
        if v.get("audit") is not None:
            e["audit"] = [{"code": str(a.get("code")), "detail": str(a.get("detail"))}
                          for a in v["audit"] if isinstance(a, dict)]
        return e
    return {"id": Path(str(v)).stem, "path": rel(v), "caption": ""}


def figure_paths(payload):
    """Every file a figure entry points at, for validation and for copying."""
    out = []
    for f in (payload.get("figures") or []):
        if isinstance(f, dict):
            out += [f[k] for k in ("path", "vector", "source") if f.get(k)]
        else:
            out.append(f)
    return out


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
    for v in (d.get("tables") or []):
        if not (out / v).exists():
            missing.append(f"tables -> {v}")
    for v in figure_paths(d):
        if not (out / v).exists():
            missing.append(f"figures -> {v}")
    if missing:
        raise ContractError(
            f"{d['kernel']} declared {len(missing)} output(s) that do not exist on disk:\n  "
            + "\n  ".join(missing[:8])
            + "\nA declaration the host cannot verify is worse than no declaration: it would be "
              "merged as a promise.")
    d.setdefault("caveats", [])
    # A 1.3 kernel has none, and absent must read as empty rather than as missing: every
    # consumer below does `.get("contradictions") or []`, and a default here means the older
    # payload and the newer one are the same shape at the point they are used.
    d.setdefault("contradictions", [])
    d.setdefault("absent", [])
    d.setdefault("objects", {})
    return d


def unknown_keys(payload):
    """Keys in a manifest the host does not act on. Reported, never silently accepted."""
    known = {"contract", "kernel", "version", "status", "headline", "absent", "caveats",
             # what the instance cost, measured by the process that paid it
             "measured",
             # one comparable number per instance, so a per-unit plugin's units share an axis
             "metrics",
             # what the plugin said against its own headline, kept apart from `caveats` so the
             # reporter can put it where the claim is and the standard can check that it did
             "contradictions",
             # the RESOLVED parameters this unit ran with - defaults filled in, overrides
             # applied. Without it a run cannot say what produced it and a reader cannot tell a
             # default from a choice.
             "config"}
    return sorted(set(payload) - known - set(OUTPUT_SLOTS))


#: Thread-pool variables, every one read at IMPORT time by the library it controls.
_THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")


def env_for_kernel(inp, cores=None):
    """The environment a kernel entry point is run with. Kept here so host and kernel agree.

    `SCPROFILE_IN` is how a kernel in any language finds its manifest without argument parsing -
    the R bridge reads the same variable.

    THE CORE SHARE IS ALSO AN ENVIRONMENT VARIABLE, and it has to be, which is the part that was
    missing. The contract says a plugin must use its allocated share and never the machine's, and
    a plugin can honour that for the work it schedules itself - `n_jobs`, a dask client, a
    thread pool. It cannot honour it for numpy: the BLAS behind it sizes its pool from
    `OMP_NUM_THREADS` at IMPORT time, before any plugin code runs. So an eight-instance wave on a
    sixteen-core allocation started sixteen BLAS threads per instance, 128 on 16 cores - the exact
    oversubscription the share exists to prevent, arriving through the one door a plugin cannot
    close. Worse, it is inherited: a job script exporting `OMP_NUM_THREADS=$NCPUS` for its own
    sake hands the node's count to every plugin it launches.

    The share is authoritative here. A caller passing None leaves the variables alone.
    """
    e = dict(os.environ)
    e["SCPROFILE_IN"] = str(inp)
    e["SCPROFILE_CONTRACT"] = CONTRACT_VERSION
    if cores:
        for var in _THREAD_VARS:
            e[var] = str(int(cores))
    return e
