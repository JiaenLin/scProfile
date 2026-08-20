"""scprofile — profile an annotated single-cell or single-nucleus dataset.

    scprofile doctor  [--prefix DIR]
    scprofile install <kernel> --prefix DIR [--force]
    scprofile fetch   <kernel> --to DIR
    scprofile run --h5ad IN.h5ad --out DIR --kernel a,b,c  [--all]
    scprofile report  --out DIR

EASY TO RUN IS A DESIGN CONSTRAINT, NOT A NICETY. Keys, organism and assay are DETECTED and the
evidence for each is printed; a wrong guess is one flag away. Every refusal carries the command
that fixes it. Nothing is assumed about the dataset - not a column name, not an organism, not an
assay, not a design.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REFUSE = 2


def _kernels():
    from .kernels import discover
    return discover()


# ------------------------------------------------------------------------------------- doctor

def _doctor(a):
    from . import refs, runner
    from .kernels import discover
    ks = discover()
    print(f"scprofile {_v()}   python {sys.version.split()[0]}")
    print(f"kernels found: {len(ks)}\n")
    width = max((len(n) for n in ks), default=8)
    worst = 0
    for name, k in sorted(ks.items()):
        state, detail, fix = runner.env_state(k, a.prefix)
        mark = {"installed": "ok  ", "host": "ok  ", "override": "ok  ",
                "missing": "MISS", "stale": "STALE"}[state]
        print(f"  {mark}  {name:<{width}}  {state:<9} {detail}")
        if fix:
            print(f"        fix: {fix}")
            worst = max(worst, 1)
        r = k.references(a.organism)
        if r:
            st = refs.status(k, a.references, a.organism) if a.references else {}
            if not a.references:
                print(f"        needs {len(r)} reference(s); pass --references DIR to check them")
            else:
                bad = [n for n, v in st.items() if v[0] != "present"]
                print(f"        references: {len(st) - len(bad)}/{len(st)} present"
                      + (f"   fix: scprofile fetch {name} --to {a.references}" if bad else ""))
        if k.when_to_use:
            print(f"        when: {k.when_to_use}")
        need = []
        if k.needs_layers:
            need.append("layers " + ", ".join(k.needs_layers))
        if k.needs_obs:
            need.append("obs " + ", ".join(k.needs_obs))
        if k.needs_kernels:
            need.append("after " + ", ".join(k.needs_kernels))
        if k.needs_design:
            need.append("a --design")
        if need:
            print(f"        needs: {'; '.join(need)}")
    for name, lost, won in getattr(discover, "shadowed", []):
        print(f"\n  NOTE  {name} is SHADOWED: {won} overrides {lost}")
        print("        A site kernel overriding a shipped one is legitimate; doing it without")
        print("        saying so would mean a run used code from a directory nobody mentioned.")
    print("")
    print("A kernel that is MISSING is not a failure - it is a kernel you have not installed.")
    print("Its absence is named in the report rather than leaving a gap.")
    print("Point `run --h5ad` at an object to see which kernels are RELEVANT to it.")
    return 0


def _v():
    from . import __version__
    return __version__


# --------------------------------------------------------------------------------- install

def _install(a):
    from . import runner
    ks = _kernels()
    for name in _split(a.kernel):
        if name not in ks:
            print(f"scprofile: no kernel {name!r}. Known: {', '.join(sorted(ks))}",
                  file=sys.stderr)
            return REFUSE
        print(f"{name}:")
        try:
            p = runner.install(ks[name], a.prefix, force=a.force)
            print(f"  installed at {p}")
        except Exception as e:                                            # noqa: BLE001
            print(f"  FAILED: {e}", file=sys.stderr)
            return 1
    return 0


def _fetch(a):
    from . import refs
    ks = _kernels()
    for name in _split(a.kernel):
        if name not in ks:
            print(f"scprofile: no kernel {name!r}", file=sys.stderr)
            return REFUSE
        print(f"{name}:")
        refs.fetch(ks[name], a.to, a.organism)
    return 0


def _split(s):
    return [x.strip() for x in str(s).split(",") if x.strip()]


# -------------------------------------------------------------------------------------- run

def _default_cores():
    """The cores this process was ALLOCATED, preferring the scheduler over the machine.

    A shared node reports every core it has, not the share this job was given, and taking the
    machine's count is how a wave ends up slower than running the same work serially.
    """
    for var in ("NCPUS", "PBS_NCPUS", "SLURM_CPUS_PER_TASK"):
        v = os.environ.get(var)
        if v and v.isdigit() and int(v) > 0:
            return int(v)
    import multiprocessing
    return max(1, min(8, multiprocessing.cpu_count()))


def _run(a):
    from . import compat, inputs, manifest, merge, provenance, refs, report, runner
    from .kernels import (discover, guard_verdict, log_escape, schedule,
                          undeclared, unmet)

    try:
        import anndata as ad
    except ImportError:
        print("scprofile: run needs anndata.  pip install -e '.[run]'", file=sys.stderr)
        return REFUSE

    ks = discover()
    want = sorted(ks) if a.all else _split(a.kernel or "")
    if not want:
        print("scprofile: name kernels with --kernel a,b or use --all", file=sys.stderr)
        return REFUSE
    bad = [n for n in want if n not in ks]
    if bad:
        print(f"scprofile: unknown kernel(s) {bad}. Known: {', '.join(sorted(ks))}",
              file=sys.stderr)
        return REFUSE

    # ---- F9: a plugin is validated BEFORE it is run ------------------------------------------
    # `validate` is cheap and static. Running a plugin whose UPSTREAM.md is still a template, or
    # whose run.py is still a scaffold, produces a result nobody can interpret and a report that
    # presents it as though somebody could.
    if not getattr(a, "no_validate", False):
        from . import validate as V
        errs = 0
        for n in [x for x in want if ks[x].status == "built"]:
            f = V.validate_plugin(ks[n])
            bad = [x for x in f if x.level == "ERROR"]
            if bad:
                errs += len(bad)
                print(f"scprofile: {n} fails validation:", file=sys.stderr)
                for x in bad:
                    print(f"    {x.check}" + (f" — {x.detail}" if x.detail else ""),
                          file=sys.stderr)
        if errs:
            print(f"scprofile: REFUSE - {errs} validation error(s). Fix them, or --no-validate "
                  f"to run anyway (which is recorded in the report).", file=sys.stderr)
            return REFUSE

    out = Path(a.out)
    print(f"reading {a.h5ad}")
    A = ad.read_h5ad(a.h5ad)
    print(f"  {A.n_obs:,} cells x {A.n_vars:,} genes")

    try:
        keys = inputs.detect_keys(
            A.obs.columns, layers=[k for k in A.layers if k is not None], obsm=list(A.obsm),
            overrides={"label": a.label_key, "sample": a.sample_key, "batch": a.batch_key,
                       "counts_layer": a.counts_layer, "compartment": a.compartment_key})
    except inputs.Refuse as e:
        print(f"scprofile: REFUSE - {e}", file=sys.stderr)
        return REFUSE
    organism = inputs.detect_organism(list(A.var_names), a.organism)
    assay = inputs.detect_assay(A, a.assay)
    constraint, csrc = inputs.read_constraint(A)

    print("\nwhat this object is, and how each was decided:")
    for role, (name, why) in keys.items():
        print(f"  {role:<14} {str(name or '(none)'):<26} {why}")
    print(f"  {'organism':<14} {str(organism[0] or '(unknown)'):<26} {organism[1]}")
    print(f"  {'assay':<14} {str(assay[0] or '(unknown)'):<26} {assay[1]}")
    print(f"  {'constraint':<14} {(csrc or 'ABSENT'):<26} "
          + ("read from the object" if csrc else
             "no upstream constraint on use - kernels that need one will say so"))

    if not keys["label"][0]:
        print("\nscprofile: REFUSE - no label column found and none given.\n"
              f"  Fix: --label-key <one of> {list(A.obs.columns)[:12]}", file=sys.stderr)
        return REFUSE

    prov = provenance.harvest(A, extra_roots=_split(a.search or ""))
    provenance.describe(prov, log=print)

    _km = {r_: v[0] for r_, v in keys.items() if v[0]}
    _km.setdefault('lognorm', 'lognorm' if 'lognorm' in A.layers else None)
    _km.setdefault('counts', _km.get('counts_layer'))
    _km = {k2: v2 for k2, v2 in _km.items() if v2}
    have_obs = set(A.obs.columns)
    have_obsm = set(A.obsm)
    have_layers = {k for k in A.layers if k is not None}
    allowed = set(_split(a.allow or ""))
    ran, payloads, skipped = [], [], []
    #: {kernel: out_dir} for kernels that have already finished, handed to each later kernel so it
    #: can read a predecessor's result directly. This is what makes `needs_kernels` mean something
    #: beyond ordering.
    upstream = {}
    #: Probe results per interpreter, and at most one compatibility copy of the object. A kernel's
    #: pinned anndata may have no reader for the encoding a current one writes; see compat.py.
    readable = {}

    # ---- units, the second axis of parallelism -----------------------------------------------
    #
    # A per_unit plugin is run once per design unit and the results compared. That is a
    # CORRECTNESS declaration before it is a speed one: an inference pooled over a cohort
    # describes the average of its conditions and may describe neither.
    sample_key = keys["sample"][0]
    units = (sorted(set(A.obs[sample_key].astype(str))) if sample_key else None)
    budget = int(getattr(a, "cores", 0) or _default_cores())
    waves = schedule(want, ks, budget_cores=budget, units=units)
    n_inst = sum(len(w) for w in waves)
    print(f"\nplan: {n_inst} instance(s) in {len(waves)} wave(s), {budget} core(s)"
          + (f", {len(units)} unit(s)" if units else ""))
    for i, wave in enumerate(waves, 1):
        print(f"  wave {i}: " + ", ".join(
            f"{x['plugin']}" + (f"[{x['unit']}]" if x["unit"] else "") + f"({x['cores']}c)"
            for x in wave))
    if a.timeout:
        print(f"  per-instance timeout {a.timeout}s")
    else:
        print("  NO per-instance timeout. A plugin that hangs will block the whole run; "
              "--timeout bounds it.")

    results = {}          # plugin -> [(out_dir, payload)]
    timings = {}

    def _prepare(inst):
        """Everything before the subprocess: guards, references, the readable copy, in.json."""
        name, unit, cores = inst["plugin"], inst["unit"], inst["cores"]
        k = ks[name]
        allow, why, escape = guard_verdict(
            k, describe=inputs.describe(A, keys, organism, assay, csrc),
            constraint=constraint, params={})
        if not allow and k.name not in allowed:
            return None, [f"guard refused: {why}", f"override with {escape} (it is logged)"]
        if not allow:
            log_escape(out / "guard_overrides.jsonl", k.name, str(why))
        try:
            r = refs.resolve(k, a.references, organism[0]) if k.references(organism[0]) else {}
        except FileNotFoundError as e:
            return None, [str(e)]
        kout = out / "kernels" / name / (str(unit) if unit else "")
        kout.mkdir(parents=True, exist_ok=True)
        exe, _src = runner.interpreter(k, a.prefix)
        k_h5ad = a.h5ad
        if exe:
            k_h5ad = compat.readable_input(A, a.h5ad, exe, out, cache=readable)
            if k_h5ad is None:
                return None, [f"{name}'s interpreter cannot read this object even re-encoded"]
        manifest.write_input(
            kout / "in.json", h5ad=k_h5ad, out_dir=kout,
            keys={r_: v[0] for r_, v in keys.items() if v[0]},
            organism=organism[0], assay=assay[0], design=a.design, references=r,
            params=json.loads(a.params) if a.params else {},
            upstream=dict(upstream), sentinels=inputs.DEFAULT_SENTINELS,
            provenance=prov, resources={"cores": cores}, unit=unit)
        return kout, None

    for wi, wave in enumerate(waves, 1):
        # Prerequisites are re-checked at the START OF EACH WAVE, not once up front: a plugin may
        # become runnable because an earlier wave produced what it needed, and the graph only
        # orders — it does not know what a plugin actually wrote.
        live = []
        for inst in wave:
            name = inst["plugin"]
            k = ks[name]
            if k.status != "built":
                if name not in {s["kernel"] for s in skipped}:
                    skipped.append({"kernel": name, "why": [
                        f"declared but not built. `scprofile scaffold {name}` writes the "
                        f"skeleton; the method still has to be wrapped."]})
                continue
            probs = unmet(k, obs=have_obs, obsm=have_obsm, layers=have_layers, ran=ran,
                          has_design=bool(a.design), keys=_km)
            if probs and not a.force:
                if name not in {s["kernel"] for s in skipped}:
                    skipped.append({"kernel": name, "why": probs})
                continue
            live.append(inst)
        if not live:
            continue

        print(f"\n=== wave {wi} ===", flush=True)
        prepared = []
        for inst in live:
            kout, why = _prepare(inst)
            if kout is None:
                lbl = inst["plugin"] + (f"[{inst['unit']}]" if inst["unit"] else "")
                print(f"  NOT RUN {lbl}")
                for w in why:
                    print(f"      {w}")
                skipped.append({"kernel": inst["plugin"], "why": why})
                continue
            prepared.append((inst, kout))

        # Instances in a wave are independent by construction, so they run CONCURRENTLY. The
        # plugins are subprocesses, so threads are the right shape - each blocks on its child and
        # holds no lock. The merge afterwards is sequential because AnnData is not thread-safe.
        import concurrent.futures as cf
        import time as _time

        def _go(item):
            inst, kout = item
            lbl = inst["plugin"] + (f"[{inst['unit']}]" if inst["unit"] else "")
            t0 = _time.perf_counter()
            try:
                pl = runner.run(ks[inst["plugin"]], inp=kout / "in.json", out_dir=kout,
                                prefix=a.prefix, log=lambda *_a, **_k: None,
                                timeout=a.timeout)
                pl["unit"] = inst["unit"]
                return inst, kout, pl, _time.perf_counter() - t0, None
            except Exception as e:                                        # noqa: BLE001
                return inst, kout, None, _time.perf_counter() - t0, f"{lbl}: {e}"

        with cf.ThreadPoolExecutor(max_workers=max(1, len(prepared))) as ex:
            done = list(ex.map(_go, prepared))

        for inst, kout, pl, secs, err in done:
            name = inst["plugin"]
            lbl = name + (f"[{inst['unit']}]" if inst["unit"] else "")
            timings.setdefault(name, []).append(round(secs, 1))
            if err:
                # One instance failing must not take the wave. A per-unit plugin failing on one
                # unit reports that unit as absent and keeps the rest.
                print(f"  FAILED {lbl}  ({secs:.0f}s)")
                print(f"      {err}")
                skipped.append({"kernel": name, "why": [err]})
                continue
            print(f"  {lbl:<28} {pl['status']:<8} {secs:>6.0f}s  {pl.get('headline', '')}")
            extra = undeclared(ks[name], pl)
            if extra:
                print(f"      UNDECLARED OUTPUT: {', '.join(extra)} - no `cannot_show` covers "
                      f"them and no documentation mentions them")
                pl.setdefault("caveats", []).append(
                    "Wrote " + ", ".join(extra) + " without declaring them in kernel.yml.")
            for c in pl.get("caveats", []):
                print(f"      caveat: {c}")
            if pl.get("status") in ("ok", "partial"):
                upstream[name] = kout
            results.setdefault(name, []).append((kout, pl))

        # ---- merge, sequentially, once per plugin --------------------------------------------
        for name in sorted({i["plugin"] for i, _k in prepared}):
            got_list = results.get(name)
            if not got_list:
                continue
            if name in ran:
                continue
            try:
                got = merge.merge_many(A, got_list)
            except merge.MergeError as e:
                print(f"  MERGE REFUSED {name}: {e}")
                skipped.append({"kernel": name, "why": [str(e)]})
                continue
            for kout, pl in got_list:
                merge.copy_tables(kout, pl, out / "tables")
                merge.link_objects(kout, pl, out / "objects")
            for slot, v in got.items():
                if v:
                    print(f"  merged {slot}: {', '.join(v)}")
            have_obs |= set(got["obs"])
            have_obsm |= set(got["obsm"])
            have_layers |= set(got["layers"])
            ran.append(name)
            payloads.extend(pl for _k, pl in got_list)

    describe = inputs.describe(A, keys, organism, assay, csrc)
    A.uns["scprofile"] = merge.provenance(
        payloads, describe, {n: ks[n].cannot_show for n in ran})
    (out / "objects").mkdir(parents=True, exist_ok=True)
    op = out / "objects" / a.object_name
    from .emit import write_h5ad
    write_h5ad(A, op)
    print(f"\nwrote {op}  ({op.stat().st_size / 1e9:.2f} GB)")

    payload = {"version": _v(), "input": str(a.h5ad), "describe": describe,
               "constraint_on_use": constraint, "constraint_source": csrc,
               "ran": ran, "skipped": skipped,
               "status": {n: ks[n].status for n in sorted(ks)},
               "schedule": [[{kk: vv for kk, vv in i.items()} for i in w] for w in waves],
               "seconds": timings, "cores": budget, "units": units,
               "timeout": a.timeout,
               "kernels": {p["kernel"]: p for p in payloads},
               "cannot_show": {n: ks[n].cannot_show for n in sorted(ks)},
               "summaries": {n: ks[n].summary for n in sorted(ks)},
               "object": str(op)}
    (out / "report.json").write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    _write_readme(out, payload)
    print(f"      {out}/report.json")
    print(f"      {report.write_all(out, payload)}")
    return 0


def _validate(a):
    """Static checks on plugins and their references. Runs nothing."""
    from . import validate as V
    from .kernels import discover
    ks = discover()
    names = _split(a.name or "") or sorted(ks)
    bad = [n for n in names if n not in ks]
    if bad:
        print(f"scprofile: unknown plugin(s) {bad}", file=sys.stderr)
        return REFUSE

    print("plugins")
    errs = 0
    for n in names:
        k = ks[n]
        f = V.validate_plugin(k) + V.validate_references(
            k, dest=a.references, organism=a.organism, deep=a.deep)
        errs += V.report(k, f)
    print()
    if errs:
        print(f"{errs} error(s). Each is a defect that would produce a plausible wrong answer "
              f"rather than a failure.")
        return REFUSE
    print("no errors. Warnings are worth reading: none of them stops a run, and each is "
          "something a reader of the result would want to know.")
    return 0


def _scaffold(a):
    """Write a declared plugin's build skeleton. The judgement is still yours."""
    from . import scaffold as SC
    from .kernels import discover
    ks = discover()
    names = _split(a.name or "")
    bad = [n for n in names if n not in ks]
    if bad:
        print(f"scprofile: unknown plugin(s) {bad}. Declare a kernel.yml first — the manifest "
              f"comes before the implementation so a plugin can be judged against a real dataset "
              f"with `scprofile plan` before anyone writes it.", file=sys.stderr)
        return REFUSE
    for n in names:
        SC.scaffold(ks[n], force=a.force)
    return 0


def _plan(a):
    """What WOULD run, and what stops it. Reads the object; runs nothing.

    Exists because the useful answer before a long run is not "it failed" but "here is what is
    missing and here is the command that fixes it". Every refusal a real run would produce is
    produced here in seconds, and the schedule is printed so the shape of the work is visible
    before any of it is spent.
    """
    from . import compat, inputs, provenance, runner
    from .kernels import discover, guard_verdict, schedule, unmet

    try:
        import anndata as ad
    except ImportError:
        print("scprofile: plan needs anndata.  pip install -e '.[run]'", file=sys.stderr)
        return REFUSE

    ks = discover()
    want = sorted(ks) if a.all else _split(a.kernel or "")
    if not want:
        want = sorted(ks)
    bad = [n for n in want if n not in ks]
    if bad:
        print(f"scprofile: unknown plugin(s) {bad}. Known: {', '.join(sorted(ks))}",
              file=sys.stderr)
        return REFUSE

    print(f"reading {a.h5ad}")
    A = ad.read_h5ad(a.h5ad, backed="r")
    print(f"  {A.n_obs:,} cells x {A.n_vars:,} genes\n")

    try:
        keys = inputs.detect_keys(
            A.obs.columns, layers=[k for k in A.layers if k is not None], obsm=list(A.obsm),
            overrides={"label": a.label_key, "sample": a.sample_key, "batch": a.batch_key,
                       "counts_layer": a.counts_layer, "compartment": a.compartment_key})
    except inputs.Refuse as e:
        print(f"scprofile: REFUSE - {e}", file=sys.stderr)
        return REFUSE
    organism = inputs.detect_organism(list(A.var_names), a.organism)
    assay = inputs.detect_assay(A, a.assay)
    constraint, csrc = inputs.read_constraint(A)

    print("what this object is, and how each was decided:")
    for role, (name, why) in keys.items():
        print(f"  {role:<14} {str(name or '(none)'):<30} {why}")
    print(f"  {'organism':<14} {str(organism[0] or '(unknown)'):<30} {organism[1]}")
    print(f"  {'assay':<14} {str(assay[0] or '(unknown)'):<30} {assay[1]}")
    print(f"  {'constraint':<14} {(csrc or 'ABSENT'):<30} "
          + ("read from the object" if csrc else "no upstream constraint recorded"))

    # ---- what the upstream stages left, and whether it is usable -----------------------------
    print("\nupstream prerequisites")
    import numpy as np
    ok_all = True

    labels = [c for c in A.obs.columns
              if A.obs[c].dtype.name in ("category", "object", "string")
              and 1 < A.obs[c].astype(str).nunique() <= 200]
    print(f"  label columns available     {len(labels)}: {', '.join(labels[:6])}"
          + (" ..." if len(labels) > 6 else ""))

    sent = [s for s in inputs.DEFAULT_SENTINELS
            if keys["label"][0] and s in set(A.obs[keys["label"][0]].astype(str))]
    print(f"  annotator sentinels         {', '.join(sent) if sent else 'none present'}")

    cl = keys.get("counts_layer", (None,))[0]
    if cl:
        sub = A.layers[cl][:2000] if A.n_obs > 2000 else A.layers[cl][:]
        d = np.asarray(sub.data if hasattr(sub, "data") and not isinstance(
            sub.data, memoryview) else sub).ravel()
        integral = bool(d.size) and bool(np.all(d == np.rint(d)))
        print(f"  counts layer                layers[{cl!r}] "
              + ("integral - usable by count models" if integral
                 else "NOT INTEGRAL - a count model handed this returns a plausible embedding"))
        ok_all &= integral
    else:
        print("  counts layer                ABSENT - count models cannot run")
        ok_all = False

    nan_emb = []
    for k in A.obsm:
        arr = A.obsm[k]
        if getattr(arr, "ndim", 0) == 2 and arr.shape[1] >= 2:
            n = int(np.isnan(np.asarray(arr[:, 0])).sum())
            if n:
                nan_emb.append((k, n))
    if nan_emb:
        print(f"  embeddings with NaN rows    " + ", ".join(f"{k} ({n:,})" for k, n in nan_emb))
        print(f"      cells withheld upstream. A plugin using one MUST exclude them and say how "
              f"many, or refuse - a NaN row in a neighbour graph either raises or silently")
        print(f"      yields a graph those cells are absent from.")

    if constraint:
        print(f"  constraint on use           PRESENT")
        for line in str(constraint).strip().splitlines()[:4]:
            if line.strip():
                print(f"      {line.strip()[:100]}")
        print("      a plugin whose claim this forbids must refuse and name the alternative")
    design_levels = {}
    if a.design:
        try:
            samples_in_obj = (sorted(set(A.obs[keys["sample"][0]].astype(str)))
                              if keys["sample"][0] else [])
            tab, key, factors = inputs.read_design(a.design, samples_in_obj)
            print(f"  design table                {a.design} - key {key!r}, "
                  f"factors {', '.join(factors)}")
            if keys["sample"][0]:
                samples = sorted(set(A.obs[keys["sample"][0]].astype(str)))
                missing = [s for s in samples if s not in tab]
                print(f"      {len(samples)} samples in the object, "
                      + (f"{len(missing)} with NO ROW: {missing[:5]}" if missing
                         else "every one has a row"))
                ok_all &= not missing
                import collections
                for f in factors:
                    cnt = collections.Counter(tab[s][f] for s in samples if s in tab)
                    design_levels[f] = dict(cnt)
                    small = {k: v for k, v in cnt.items() if v < 3}
                    print(f"      {f:<12} " + ", ".join(f"{k}={v}" for k, v in sorted(cnt.items()))
                          + ("   <- BELOW 3 PER GROUP: compositional and pseudobulk tests refuse"
                             if small else ""))
        except Exception as e:                                            # noqa: BLE001
            print(f"  design table                REFUSED - {e}")
            ok_all = False
    else:
        print("  design table                NOT GIVEN - any plugin testing across a design "
              "will refuse")

    # ---- per plugin ---------------------------------------------------------------------------
    print("\nplugins")
    _km = {r_: v[0] for r_, v in keys.items() if v[0]}
    _km.setdefault('lognorm', 'lognorm' if 'lognorm' in A.layers else None)
    _km.setdefault('counts', _km.get('counts_layer'))
    _km.setdefault('embedding', next((e for e in ('X_scanvi', 'X_umap', 'X_pca')
                                      if e in A.obsm), None))
    _km = {k2: v2 for k2, v2 in _km.items() if v2}
    have_obs, have_obsm = set(A.obs.columns), set(A.obsm)
    have_layers = {k for k in A.layers if k is not None}
    import os
    prov = provenance.harvest(A)
    runnable, planned, todo = [], [], []
    for name in sorted(want):
        k = ks[name]
        if k.status != "built":
            planned.append((name, k))
            continue
        probs = unmet(k, obs=have_obs, obsm=have_obsm, layers=have_layers,
                      ran=set(want), has_design=bool(a.design), keys=_km)
        state, why, fix = runner.env_state(k, a.prefix)
        env_ok = state in ("installed", "override", "host")
        if probs:
            print(f"  NOT RUNNABLE  {name}")
            for pr in probs:
                print(f"      {pr}")
        elif not env_ok:
            print(f"  NO ENVIRONMENT {name}   {why}")
            todo.append(("env", name, fix or f"scprofile install {name} --prefix <dir>"))
        else:
            runnable.append(name)
            e = k.executor
            unit = f", per {k.per_unit}" if k.per_unit else ""
            print(f"  runnable      {name}   cost {e['cost']}, {e['cores']} core(s){unit}")
            # `runnable` here means the prerequisite check did not block it. A plugin that
            # declares can_source_layers is NOT blocked on a missing layer - it goes and looks -
            # so reporting it as plainly runnable overstates the case. Say what it will look for
            # and what happens if it does not find it.
            from .kernels import resolve_keys
            miss = [c for c in resolve_keys(k.needs_layers, _km) if c not in have_layers]
            if miss and k.can_source_layers:
                roots = (list((prov or {}).get("search_paths") or [])
                         + provenance.ancestry_roots(a.h5ad))
                hits = provenance.find_layer_sources(roots, tuple(miss))
                if hits:
                    common = os.path.commonpath([h[1] for h in hits]) if len(hits) > 1 \
                        else hits[0][1]
                    print(f"      layers {', '.join(miss)} are NOT on this object, but "
                          f"{len(hits)} source(s) were FOUND:")
                    for kind, d in hits[:3]:
                        print(f"        {kind}  {d}")
                    if len(hits) > 3:
                        print(f"        ... and {len(hits) - 3} more")
                    todo.append(("data", name, f"--search {common}"))
                else:
                    print(f"      layers {', '.join(miss)} are not on this object and no source "
                          f"was found under {len(roots)} lead(s).")
                    todo.append(("data", name,
                                 f"# regenerate {', '.join(miss)} from the aligner, or "
                                 f"--search <dir>"))
            if k.needs_design and not a.design:
                print(f"      needs a design table")

    if planned:
        print("\ndeclared, not built — what each WOULD need on this object")
        for name, k in planned:
            probs = unmet(k, obs=have_obs, obsm=have_obsm, layers=have_layers,
                          ran={n for n, _ in planned} | set(runnable),
                          has_design=bool(a.design), keys=_km)
            mark = "ready when built" if not probs else "would refuse"
            wraps = k.spec.get("plans_to_wrap") or "-"
            unit = f", per {k.per_unit}" if k.per_unit else ""
            print(f"  {mark:<16} {name:<12} wraps {wraps}{unit}")
            for pr in probs:
                print(f"      {pr}")
            if not probs:
                todo.append(("build", name,
                             f"scprofile scaffold {name}   # manifest exists; lock, selftest, "
                             f"run.py and UPSTREAM.md do not"))

    # ---- design defects: the ONLY legitimate reason to skip a plugin ------------------------
    #
    # Everything else that stops a plugin - a missing environment, an unbuilt implementation, an
    # input that exists elsewhere on disk - is WORK, and listing it beside a genuine limit of the
    # experiment makes the two look alike. A design defect is a finding about the study; a missing
    # build is a finding about us. Only the first is a reason not to run something.
    defects = []
    if design_levels:
        for name in sorted(want):
            k = ks[name]
            if not (k.needs_design or k.design_aware):
                continue
            for f, counts in design_levels.items():
                small = {lv: n for lv, n in counts.items() if n < 3}
                if small and k.needs_design:
                    defects.append((name, f"factor {f!r} has {', '.join(f'{lv}=n{n}' for lv, n in sorted(small.items()))}"
                                          f" — below 3 replicates, so an effect is estimable but"
                                          f" weakly powered, and an interaction across two such"
                                          f" levels is the weakest term in the model"))
    if constraint and "must NOT" in str(constraint):
        for name in sorted(want):
            k = ks[name]
            if k.needs_design and k.needs_obsm:
                defects.append((name, "the upstream constraint forbids a claim across the tested "
                                      "factor on the chosen embedding; it must use the "
                                      "uncorrected one and say so"))
    if defects:
        print("\ndesign limits — the only legitimate reason to skip a plugin")
        for name, why in defects:
            print(f"  {name:<12} {why}")
        print("  These are findings about the EXPERIMENT. They belong in the report whether or "
              "not the plugin runs.")

    # ---- what to do about it ------------------------------------------------------------------
    #
    # A gap reported without the command that closes it is an excuse. Everything above that
    # stopped something is repeated here as an action, in the order it has to happen.
    if todo:
        print(f"\nto make this runnable — {len(todo)} gap(s), all FIXABLE")
        order = {"data": 0, "env": 1, "build": 2}
        for kind, name, cmd in sorted(todo, key=lambda x: (order.get(x[0], 9), x[1])):
            print(f"  [{kind:<5}] {name:<12} {cmd}")
        print("\n  `scprofile plan --fix` runs the env and reference steps. A [build] step needs "
              "a person: scaffold writes the skeleton from the manifest, and the method still has "
              "to be wrapped correctly.")
        print("  NONE of these is a reason to skip a plugin. A missing build is a finding about "
              "the tooling, not about the data.")

    # ---- the schedule -------------------------------------------------------------------------
    if runnable:
        units = (sorted(set(A.obs[keys["sample"][0]].astype(str)))
                 if keys["sample"][0] else None)
        print(f"\nschedule ({a.cores} cores"
              + (f", {len(units)} units" if units else "") + ")")
        for i, wave in enumerate(schedule(runnable, ks, budget_cores=a.cores, units=units), 1):
            print(f"  wave {i}: " + ", ".join(
                f"{x['plugin']}" + (f"[{x['unit']}]" if x['unit'] else "")
                + f"({x['cores']}c)" for x in wave))
    else:
        print("\nnothing is runnable on this object as it stands.")
    print("\nnothing was run.")
    return 0 if runnable and ok_all else REFUSE


def _write_readme(out, payload):
    """The six-question README, written by INSPECTING the directory.

    By inspecting it, not from what the run intended: a README describing files that were not
    written is the failure this project has hit in three other places, and it reads exactly like a
    correct one.
    """
    out = Path(out)
    d = payload.get("describe") or {}
    ran, skipped = payload.get("ran") or [], payload.get("skipped") or []
    files = sorted(q for q in out.rglob("*") if q.is_file())
    by_dir = {}
    for q in files:
        by_dir.setdefault(str(q.parent.relative_to(out)) or ".", []).append(q.name)

    L = [f"# scProfile output", "",
         f"- **{len(ran)}** plugin(s) ran, **{len(skipped)}** did not",
         f"- {len(files)} files, {sum(q.stat().st_size for q in files) / 1e9:.2f} GB", ""]

    L += ["## 1. What is this, and where did it come from?", "",
          f"Produced by scProfile {payload.get('version', '?')} from `{payload.get('input')}`.",
          f"Plugins that ran: {', '.join(ran) or 'none'}.", ""]
    if payload.get("constraint_on_use"):
        L += ["The input carried a **constraint on use**, reproduced in the report. It applies to "
              "everything here.", ""]

    L += ["## 2. What is the layout?", ""]
    for k in sorted(by_dir):
        L.append(f"- `{k}/` — {len(by_dir[k])} file(s): "
                 + ", ".join(sorted(by_dir[k])[:6])
                 + (" …" if len(by_dir[k]) > 6 else ""))
    L.append("")

    L += ["## 3. What does each file contain?", "",
          "| file | is |", "|---|---|"]
    for k, v in sorted((payload.get("kernels") or {}).items()):
        L.append(f"| `report/{k}.html` | {k}: {v.get('headline', '')} |")
    L += ["| `objects/*.h5ad` | the input object with every merged cell-level result |",
          "| `tables/*.csv` | edge- and gene-level results, prefixed by plugin |",
          "| `report.json` | every number in the report, machine-readable |", ""]

    L += ["## 4. What processing has already been applied?", "",
          "Nothing here re-processes the input. Each plugin adds its own result; the object's "
          "X, layers and existing obs are the input's.", ""]
    for k, v in sorted((payload.get("kernels") or {}).items()):
        for c in (v.get("caveats") or [])[:2]:
            L.append(f"- **{k}**: {c}")
    L.append("")

    L += ["## 5. Which file is the intended input for the next step?", "",
          f"`objects/{Path(str(payload.get('object', ''))).name}` — it carries every merged "
          f"result. The per-plugin directories under `kernels/` are the raw run output and are "
          f"kept for provenance, not for reading.", ""]

    L += ["## 6. What is missing, or cannot be done with this output?", ""]
    if skipped:
        L.append("**Did not run:**", )
        for s in skipped:
            L.append(f"- `{s['kernel']}` — {'; '.join(str(w) for w in (s.get('why') or []))[:300]}")
        L.append("")
    L += ["Every plugin's own limits are on its report page and in "
          "`report.json` under `cannot_show`. They are not repeated here, because a limit "
          "restated away from the number it qualifies is a limit that goes stale.", ""]
    (out / "README.md").write_text("\n".join(L), encoding="utf-8")
    return out / "README.md"


def _report(a):
    from . import report
    p = Path(a.out) / "report.json"
    if not p.exists():
        print(f"scprofile: no {p}. Run `scprofile run` first.", file=sys.stderr)
        return REFUSE
    print(f"wrote {report.write_all(Path(a.out), json.loads(p.read_text()))}")
    return 0


# ------------------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="scprofile", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"scprofile {_v()}")
    sub = ap.add_subparsers(dest="cmd", metavar="COMMAND")

    d = sub.add_parser("doctor", help="what is installed, what is missing, and the exact fix")
    d.add_argument("--prefix", default=None, help="where kernel environments live")
    d.add_argument("--references", default=None, help="where reference data lives")
    d.add_argument("--organism", default=None)
    d.set_defaults(fn=_doctor)

    i = sub.add_parser("install", help="build a kernel's environment from its lock")
    i.add_argument("kernel")
    i.add_argument("--prefix", required=True)
    i.add_argument("--force", action="store_true", help="rebuild an existing environment")
    i.set_defaults(fn=_install)

    f = sub.add_parser("fetch", help="download and verify a kernel's declared references")
    f.add_argument("kernel")
    f.add_argument("--to", required=True)
    f.add_argument("--organism", default=None)
    f.add_argument("--dry-run", action="store_true",
                   help="report what would be downloaded, how much, and whether it fits. "
                        "Reference databases are gigabytes; filling a filesystem halfway through "
                        "is a worse failure than refusing at the start")
    f.set_defaults(fn=_fetch)

    r = sub.add_parser("run", help="run kernels, merge results, write the report")
    r.add_argument("--h5ad", required=True, type=Path)
    r.add_argument("--out", required=True, type=Path)
    r.add_argument("--kernel", default=None, help="comma separated")
    r.add_argument("--all", action="store_true", help="every kernel, in prerequisite order")
    r.add_argument("--prefix", default=None, help="where kernel environments live")
    r.add_argument("--references", default=None, help="where reference data lives")
    r.add_argument("--label-key", default=None)
    r.add_argument("--compartment-key", default=None)
    r.add_argument("--sample-key", default=None)
    r.add_argument("--batch-key", default=None)
    r.add_argument("--counts-layer", default=None)
    r.add_argument("--embedding", default=None)
    r.add_argument("--organism", default=None, choices=[None, "mouse", "human"])
    r.add_argument("--assay", default=None, choices=[None, "cell", "nucleus"],
                   help="does not change what is computed; changes what each kernel may claim")
    r.add_argument("--design", default=None, type=Path,
                   help="CSV keyed on the sample column, carrying the experimental factors")
    r.add_argument("--params", default=None, help="JSON passed through to every kernel")
    r.add_argument("--cores", type=int, default=None, metavar="N",
                   help="core budget divided across concurrently running plugins. Defaults to "
                        "the scheduler's allocation, never the machine's core count")
    r.add_argument("--timeout", type=int, default=None, metavar="SECONDS",
                   help="per-instance limit. Without one, a plugin that hangs blocks the whole "
                        "run and under a scheduler the walltime kills every plugin rather than "
                        "the one at fault")
    r.add_argument("--no-validate", action="store_true",
                   help="run without the static checks. Recorded in the report")
    r.add_argument("--search", default=None, metavar="DIRS",
                   help="extra directories a kernel may look in for files that are NOT in the "
                        "object - spliced/unspliced counts, most often. Comma-separated. The "
                        "upstream chain recorded in uns is searched automatically; this is for "
                        "data that moved, or a pipeline that recorded nothing")
    r.add_argument("--object-name", default="cohort_profiled.h5ad")
    r.add_argument("--allow", default=None, metavar="KERNELS",
                   help="run these kernels even though their own guard refused. Comma separated. "
                        "Every override is written to guard_overrides.jsonl with its reason - a "
                        "gate with no escape gets switched off, and one whose escapes are all "
                        "recorded does not")
    r.add_argument("--force", action="store_true",
                   help="run a kernel whose prerequisites are unmet. It will probably refuse "
                        "itself, and its result would not mean what the report says it means")
    r.set_defaults(fn=_run)

    pl = sub.add_parser("plan", help="what WOULD run, and what stops it. Runs nothing")
    pl.add_argument("--h5ad", required=True)
    pl.add_argument("--kernel", default=None)
    pl.add_argument("--all", action="store_true")
    pl.add_argument("--prefix", default=None)
    pl.add_argument("--design", default=None)
    pl.add_argument("--cores", type=int, default=8)
    for f in ("label-key", "sample-key", "batch-key", "counts-layer", "compartment-key",
              "organism", "assay"):
        pl.add_argument(f"--{f}", default=None)
    pl.set_defaults(fn=_plan)

    va = sub.add_parser("validate", help="static checks on plugins and their references")
    va.add_argument("name", nargs="?", default=None,
                    help="plugin name(s), comma-separated. Default: all")
    va.add_argument("--references", default=None, metavar="DIR",
                    help="also check the reference files on disk under this directory")
    va.add_argument("--deep", action="store_true",
                    help="verify reference checksums. Hashes gigabytes; this is what a run does "
                         "before trusting them")
    va.add_argument("--organism", default=None)
    va.set_defaults(fn=_validate)

    sc_ = sub.add_parser("scaffold", help="write a declared plugin's build skeleton")
    sc_.add_argument("name", help="plugin name(s), comma-separated")
    sc_.add_argument("--force", action="store_true", help="overwrite existing skeleton files")
    sc_.set_defaults(fn=_scaffold)

    p = sub.add_parser("report", help="rebuild the documents from report.json")
    p.add_argument("--out", required=True, type=Path)
    p.set_defaults(fn=_report)

    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
