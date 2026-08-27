"""The one entrypoint every plugin is run through. Shipped with the host; never generated.

A plugin runs in its OWN interpreter - often its own pinned environment, sometimes another
language's - so the host cannot import it and call it directly. That is why plugins were wrappers
with a `main()`: each had to re-implement the protocol, and each re-implemented it slightly
differently.

This file is that wrapper, written ONCE. The plugin's interpreter runs THIS, with the plugin
module on its path; it reads `in.json`, applies the whole contract, imports the plugin, calls
`run(ctx)`, and writes `out.json`. Nothing is generated and nothing is copied between plugins, so
a fix to the contract is a fix for every plugin including ones this project did not write.

    <plugin's python> <this file, by path> <plugin module path> <in.json>
    <plugin's python> <this file, by path> --selftest <plugin module path>
    <HOST's python>    <this file, by path> --guard    <plugin module path>   < payload on stdin

BY PATH, NOT AS `-m`. The interpreter is the PLUGIN'S, in the plugin's own pinned environment,
where the host is not installed and must not have to be - `-m scprofile._entry` would not resolve
there. This file puts the host on its own `sys.path` as its first act, and everything it imports
from the host is stdlib-only, so it loads in any environment a plugin can be built in.

WHO CONSTRUCTS THAT COMMAND: the KERNEL, through `FileKernel.argv`. The runner asks a kernel how
it is launched and knows nothing about shapes. The runner used to build the command itself, which
is right for the directory shape and silently wrong for this one: a one-file plugin handed
straight to an interpreter defines two names, exits 0 and writes nothing, and exit 0 with no
`out.json` is the single failure the host cannot tell from a plugin that finished with no
results.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import declare, manifest                                   # noqa: E402
from scprofile.plugin import Context, Guard                               # noqa: E402


def _has(ctx, cap, inp):
    """Is this capability actually available? The host answers; the plugin never asks.

    The ANSWER lives in `declare.available`, so the planner and the run cannot disagree about
    what a plugin will be given; this only reads the object into the shape it wants.
    """
    A = ctx.adata
    return declare.available(
        cap, keys=ctx.keys,
        obs=(A.obs.columns if A is not None else ()),
        layers=(A.layers.keys() if A is not None else ()),
        obsm=(A.obsm.keys() if A is not None else ()),
        var=(getattr(A, "var", None).columns if A is not None and getattr(A, "var", None)
             is not None else ()),
        has_design=bool(inp.get("design")), organism=ctx.organism,
        derived=list(inp.get("upstream") or {}) + list(inp.get("provided") or []))


def load(path):
    """Import a plugin from a file path, without it needing to be installed anywhere."""
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"scprofile_plugin_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "run"):
        raise SystemExit(f"{path.name} declares no run(ctx). A plugin is a PLUGIN dict and a "
                         f"run(ctx) function; see scprofile/plugin.py.")
    return mod


def selftest(plugin_path, log=print):
    """Run a plugin's own `selftest(ctx)`, in the plugin's own interpreter.

    THIS IS THE QUALITY CHECK THE BUILDER RUNS on every new machine. It proves the call is
    well-formed against the versions actually installed there - which is what moves underneath a
    wrapper, and what an import check cannot see: an API that moved, a scheduler handshake that
    silently returns nothing, a keyword the function now forbids.

    A plugin with no `selftest` is reported as unproven rather than as passing.
    """
    mod = load(plugin_path)
    fn = getattr(mod, "selftest", None)
    if fn is None:
        log(f"  {Path(plugin_path).stem}: NO SELFTEST. Nothing has proved this plugin's call is "
            f"well-formed against the versions installed here; only a real run will.")
        return None
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ctx = Context(None, keys={}, out=d, cores=1, log=log)
        fn(ctx)
    log(f"  {Path(plugin_path).stem}: selftest passed")
    return True


def guard(plugin_path, payload, log=print):
    """Ask a one-file plugin's `guard(g)`. Exit 0 allows and prints notes; non-zero denies.

    THE SAME PROTOCOL A `guard.py` USED, because `guard_verdict` reads an exit code and a stream
    and must not learn about shapes. What changed is only where the function lives: a one-file
    plugin has no neighbouring file for the host to execute, so it had NO GUARD AT ALL and nothing
    said so - converting a guarded plugin to this shape silently deleted the check.

    This runs in the HOST's interpreter, before the plugin's environment is resolved. If the
    module cannot be imported here that is reported as a denial, not waved through: a guard that
    was never consulted has not allowed anything, and running as though it had is the one outcome
    a gate must never produce.
    """
    import json
    d = json.loads(payload or "{}")
    g = Guard(d.get("describe"), d.get("constraint"), d.get("params"))
    try:
        mod = load(plugin_path)
    except Exception as e:                                                # noqa: BLE001
        log(f"{Path(plugin_path).stem} ships a guard and could not be imported by the host "
            f"interpreter ({type(e).__name__}: {e}).\n"
            f"  A guard runs before the environment is resolved, so its module scope must import "
            f"nothing the host does not have - keep third-party imports inside the functions.\n"
            f"  Nothing has been checked, so nothing is allowed.")
        return 2
    fn = getattr(mod, "guard", None)
    if fn is None:
        return 0
    fn(g)
    if g.denials:
        log("\n".join(g.denials))
        return 1
    log(" | ".join(g.notes) if g.notes else "")
    return 0


def main(argv):
    if argv[1] == "--selftest":
        return 0 if selftest(argv[2]) is not False else 1
    if argv[1] == "--guard":
        return guard(argv[2], sys.stdin.read())
    plugin_path = argv[1]
    inp = manifest.read_input(argv[2] if len(argv) > 2 else os.environ["SCPROFILE_IN"])
    out = Path(inp["out_dir"])
    log = print

    import numpy as np
    # ANNDATA, NOT SCANPY. This read the object with `scanpy.read_h5ad`, which is the same
    # function one package further away - and it made SCANPY an undeclared requirement of the
    # CONTRACT, imposed on every plugin's environment by the entrypoint rather than by anything a
    # plugin asked for. The contract should need as little of a plugin's environment as it can:
    # what it does here is read an h5ad, and anndata is what reads an h5ad.
    import anndata as ad

    A = ad.read_h5ad(inp["h5ad"])
    keys = dict(inp.get("keys") or {})
    unit = inp.get("unit")
    sentinels = set(inp.get("sentinels") or ())
    cores = int((inp.get("resources") or {}).get("cores", 1))
    log(f"{A.n_obs:,} cells x {A.n_vars:,} genes"
        + (f", unit {unit!r}" if unit else "") + f", {cores} core(s)")

    pre_caveats = []

    # ---- THE CONTRACT, applied once for every plugin that will ever exist --------------------
    #
    # A per-unit plugin sees ONE unit's cells. Doing this here rather than in each plugin is what
    # stops one of them forgetting and reporting a cohort-wide number under a unit's name.
    ukey = keys.get("sample")
    if unit is not None and ukey and ukey in A.obs:
        A = A[A.obs[ukey].astype(str) == str(unit)].copy()
        log(f"  subset to {unit!r}: {A.n_obs:,} cells")
        if A.n_obs == 0:
            manifest.write_output(out, kernel=Path(plugin_path).stem, status="refused",
                                  headline=f"no cells in unit {unit!r}",
                                  absent=[{"what": "everything",
                                           "why": f"unit {unit!r} has no cells here"}])
            return 0

    # A sentinel is an annotator declining to call a cell type. They are CELLS: never a
    # population, never a denominator, never dropped.
    #
    # THE CAVEAT SAYS WHAT IS TRUE, NOT WHAT WOULD BE NICE. It used to end "and are not treated as
    # a population", which the host has no way to make true: only the plugin knows what it groups
    # by. In the first run that ever reached a third-party plugin, that sentence was printed
    # beside a results table whose worst-scoring population was `UNRESOLVED` - the annotator's
    # refusal to call a cell type, reported as a cell type that scored badly. The host offers
    # `ctx.real_cells()` and CHECKS the emitted tables afterwards; it does not promise.
    lab = keys.get("label")
    if lab and lab in A.obs:
        from scprofile import inputs
        _real, found = inputs.sentinel_mask(A.obs[lab], sentinels)
        n = int((~_real).sum())
        if n:
            pre_caveats.append(
                f"{n:,} cells carry an annotator sentinel "
                f"({', '.join(f'{s} {c:,}' for s, c in sorted(found.items()))}). They are KEPT - "
                f"they are cells, not a population, and nothing here drops them. If one of those "
                f"names appears in this plugin's results as though it were a cell type, that is a "
                f"defect in the plugin and not a finding about the data.")
            log(f"  {n:,} sentinel-labelled cells kept")

    # A NaN row in a computed embedding is a cell an upstream step withheld. In a neighbour graph
    # it either raises or silently yields a graph that cell is absent from.
    emb = keys.get("embedding")
    if emb and emb in A.obsm:
        bad = np.isnan(np.asarray(A.obsm[emb])[:, 0])
        nb = int(bad.sum())
        if nb:
            A = A[~bad].copy()
            pre_caveats.append(f"{nb:,} cells carry NaN in obsm[{emb!r}] - withheld upstream - "
                               f"and are EXCLUDED here.")
            log(f"  excluded {nb:,} cells with NaN in {emb}")

    mod = load(plugin_path)
    spec = getattr(mod, "PLUGIN", {}) or {}

    # THE CONTRACT VERSION, checked before anything else. A host that meets a plugin written
    # against a contract it does not implement refuses it BY NAME, rather than calling it and
    # failing somewhere inside where the cause is a traceback in a stranger's run.
    api = spec.get("api", declare.API)
    if api != declare.API:
        manifest.write_output(out, kernel=Path(plugin_path).stem, status="refused",
                              headline=f"plugin declares api {api}, host implements "
                                       f"{declare.API}",
                              absent=[{"what": "everything",
                                       "why": f"contract mismatch: this plugin was written "
                                              f"against api {api}."}])
        return 0

    # CONFIG: defaulted, typed and range-checked HERE, so a plugin never validates its own
    # parameters and a bad --params fails before the work rather than inside it.
    try:
        config = declare.resolve_config(spec, inp.get("params"), Path(plugin_path).stem)
    except declare.DeclarationError as e:
        manifest.write_output(out, kernel=Path(plugin_path).stem, status="refused",
                              headline="parameter refused",
                              absent=[{"what": "everything", "why": str(e)}])
        return 0

    ctx = Context(A, keys=keys, out=out, cores=cores, unit=unit,
                  organism=inp.get("organism"), assay=inp.get("assay"),
                  references=inp.get("references"),
                  # BY ROLE, NOT BY NAME. `Context` accepted these from the beginning and nothing
                  # ever passed them, so `ctx.reference_for_role(...)` returned None for every
                  # role of every plugin - and scenic, the only plugin that asks, refused on all
                  # ten units of a real cohort with "the cisTarget references are not available"
                  # while `in.json` listed all three of them, verified, by absolute path.
                  reference_specs=inp.get("reference_specs"), params=inp.get("params"),
                  design=inp.get("design"), sentinels=sentinels, config=config,
                  # The SAME field `Guard` reads. A plugin may be refused by the constraint and
                  # may also need to REPRODUCE it - the cohort-scope fits do - and only Guard
                  # could see it.
                  constraint=inp.get("constraint") or "",
                  # The upstream chain, so a plugin needing a file that is NOT in the object can
                  # ask the host to go and find it (`ctx.source_layers`). Harvested from `uns`,
                  # which is dropped from this copy of the object on purpose.
                  provenance=inp.get("provenance"), log=log)
    ctx.caveats.extend(pre_caveats)

    # REQUIRED CAPABILITIES. The host either satisfies them or does not call run() - a plugin
    # that opens with `if not ctx.organism: refuse(...)` is doing the host's job, and doing it
    # once per plugin means doing it differently once per plugin.
    missing = [c for c in ((spec.get("inject") or {}).get("required") or [])
               if not _has(ctx, c, inp)]
    if missing:
        ctx.status = "refused"
        ctx.headline = f"missing required capability: {', '.join(missing)}"
        for c in missing:
            ctx.absent.append({"what": c,
                               "why": declare.CAPABILITIES.get(c, {}).get("why", "not available")})
        log(f"  NOT CALLED: {ctx.headline}")
    else:
        try:
            mod.run(ctx)
        finally:
            # ON EVERY EXIT PATH, including a raise. A plugin that raised did not reach the
            # `finally` somebody wrote inside it in a hurry.
            ctx._dispose(log=log)

    # WHAT IT ACTUALLY COST, measured by the process that paid it. The allocator schedules on
    # memory and eight of nine plugins declare no rate, so it assumes one - and an assumption
    # nothing ever checks is how the core budget stayed wrong for every run. Every plugin now
    # reports its own peak RSS beside the cell count it processed, which is exactly the number
    # `memory_gb_per_100k` wants, so the declaration can be filled in from measurement rather
    # than from somebody's estimate. This is the run -> declare edge doing its job.
    peak_gb = None
    try:
        import resource
        # CHILDREN TOO. RUSAGE_SELF is the calling process ALONE, and the libraries these
        # plugins wrap parallelise with SUBPROCESSES - joblib, loky, pynndescent - so the memory
        # that actually decides whether a job survives is invisible to it. Measured on a real
        # cohort: a plugin reported a 14.4 GB peak in three separate runs, its declaration was
        # fitted to that number, the host scheduled on the declaration, and the plugin was
        # SIGKILLed at 48 GB while computing neighbours. Its own measurement was wrong by more
        # than threefold, in the direction that gets a run killed and keeps nothing.
        #
        # RUSAGE_CHILDREN is the maximum of any single REAPED child, not the sum of concurrent
        # ones, so this is still a floor - but a floor that includes the workers beats a ceiling
        # that pretends they do not exist.
        _self = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        _kids = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        raw = float(_self) + float(_kids)
        # ru_maxrss is KILOBYTES on Linux and BYTES on macOS/BSD. Getting this wrong reports a
        # 1024x error in whichever direction, and both directions look plausible.
        peak_gb = raw / (1024.0**2 if sys.platform != "darwin" else 1024.0**3)
    except (ImportError, OSError, ValueError):
        pass
    if peak_gb:
        n = int(getattr(ctx, "n_obs", 0) or getattr(getattr(ctx, "adata", None), "n_obs", 0) or 0)
        # THE RAW PAIR, AND NOT A RATE. `peak / n * 100_000` reads as "GB per 100k cells" and is
        # not one: memory is a BASELINE plus a per-cell term - interpreter, imports and the
        # object are paid once, whatever n is - and dividing by n attributes all of that fixed
        # cost to the per-cell slope. On instances of 10-25k cells it produced 157 GB/100k for a
        # plugin whose real per-cell demand is a fraction of that, which is wrong in the
        # dangerous direction for the small instances and the safe one for the large.
        #
        # ONE MEASUREMENT CANNOT SEPARATE THE TWO. Two at different sizes can, and a per-unit
        # plugin produces one per unit for free - so the host fits them afterwards
        # (`kernels.fit_memory_model`) and this reports only what it actually observed.
        # AND THE KERNEL'S OWN COUNTER, WHERE THERE IS ONE. Measured against PBS's accounting
        # on a real job: the process tree reported 14.374 GB and `resources_used.mem` was
        # 42.7 GB - THREE TIMES more - because RUSAGE_CHILDREN is the largest single reaped
        # child, not the sum of eight concurrent workers. Adding children narrows that gap and
        # does not close it, and a floor presented as a peak is what got this plugin killed by
        # its own declaration.
        #
        # The cgroup counter is what the scheduler itself bills. It covers the whole JOB, so it
        # is only attributable to one plugin when one instance runs at a time - which is exactly
        # the one-plugin-one-job shape these are verified in. Recorded ALONGSIDE, never instead:
        # the model keeps using the attributable floor, and the discrepancy becomes visible
        # instead of silent.
        cg = None
        for _c in ("/sys/fs/cgroup/memory.peak",
                   "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"):
            try:
                cg = int(Path(_c).read_text().strip()) / (1024.0 ** 3)
                break
            except (OSError, ValueError):
                continue
        ctx.measured = {"peak_rss_gb": round(peak_gb, 3), "n_cells": n,
                        **({"cgroup_peak_gb": round(cg, 3)} if cg else {}),
                        # NAMED, because it is a floor and not a peak: RUSAGE_CHILDREN is the
                        # largest single reaped child, so concurrent workers are undercounted.
                        "rss_covers": "parent + largest reaped child (a floor, not the peak); "
                                      "cgroup_peak_gb, where present, is what the scheduler "
                                      "bills for the WHOLE job"}
        log(f"  peak memory {peak_gb:.2f} GB over {n:,} cells")

    manifest.write_output(
        out, kernel=Path(plugin_path).stem,
        version=str((getattr(mod, "PLUGIN", {}) or {}).get("version", "0.1.0")),
        # THE REFUTATIONS FIRST, COMPOSED HERE SO ORDER CANNOT MATTER. `ctx.contradiction`
        # prefixed the headline directly, and both plugins that call it assign `ctx.headline`
        # on the next line - so the refutation was written and immediately overwritten, and two
        # runs came back with the unqualified claim and no sign anything had been attempted.
        status=ctx.status,
        headline=" ".join(list(getattr(ctx, "_contradictions", []) or []) + [ctx.headline or ""]
                          ).strip(),
        obs=ctx._obs, obsm=ctx._obsm, layers=ctx._layers,
        tables=ctx._tables, figures=ctx._figures, objects=ctx._objects,
        absent=ctx.absent, caveats=ctx.caveats,
        metrics=getattr(ctx, "_metrics", None),
        # AND AS A FIELD OF THEIR OWN, so the reporter can put them where the claim is and the
        # exit standard can check that it did. Composed into the headline above as well: two
        # consumers, one recorded fact, neither reading the other's copy.
        contradictions=list(getattr(ctx, "_contradictions", []) or []),
        measured=getattr(ctx, "measured", None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
