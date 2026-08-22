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
        # THE ENVIRONMENT BEING FINE IS NOT THE PLUGIN EXISTING, and reading only the environment
        # made `doctor` print `ok  de  host  runs in the host interpreter` for a plugin that is
        # `status: planned` and has no run.py at all. Nothing to run, reported as ready - the
        # plausible wrong answer this tool's own validator banner warns about.
        built = k.status == "built"
        mark = ({"installed": "ok  ", "host": "ok  ", "override": "ok  ",
                 "missing": "MISS", "stale": "STALE"}[state] if built else "TODO")
        state_s = state if built else "planned"
        print(f"  {mark}  {name:<{width}}  {state_s:<9} "
              + (detail if built else
                 "declared, not built - no run.py. `scprofile scaffold " + name
                 + "` writes the skeleton; the method still has to be wrapped."))
        if fix and built:
            print(f"        fix: {fix}")
            worst = max(worst, 1)
        if not built and state in ("installed", "override", "stale"):
            # THE OTHER HALF OF THE SAME DISTINCTION. Reading only the environment reported a
            # plugin with no run.py as ready, which is the comment above. Reading only the status
            # hides the environment completely: three locks were built and proved here, and
            # `doctor` said `TODO ... declared, not built` for all three with no sign that
            # anything exists on disk. Both facts are real and neither substitutes for the other.
            print(f"        environment: {state} - {detail}")
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
    # WHAT THE BUILDER RESOLVED. A shared environment is a decision the user should be able to
    # see and disagree with, and the count is the difference between one 1.5 GB build and four.
    from . import resolve as RS
    groups = RS.group_by_compatibility(list(ks.values()))
    if groups:
        RS.report(groups)
        n_env = len(groups)
        n_mem = sum(len(g.members) for g in groups)
        if n_mem > n_env:
            print(f"  {n_mem - n_env} fewer environment(s) than plugins, because their declared "
                  f"requirements are mutually satisfiable.")

    n_todo = sum(1 for k in ks.values() if k.status != "built")
    if n_todo:
        print(f"{n_todo} kernel(s) are DECLARED BUT NOT BUILT. Their prerequisites are real and "
              f"checkable;\nthe implementation does not exist. That is a different fact from "
              f"MISSING, which means\nthe code is here and its environment is not.")
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
        print(f"{name}:", flush=True)
        try:
            p = runner.install(ks[name], a.prefix, force=a.force,
                               dry_run=bool(getattr(a, "dry_run", False)))
            print(f"  {'would install at' if getattr(a, 'dry_run', False) else 'installed at'} {p}")
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
        print(f"{name}:", flush=True)
        # By KEYWORD. The fourth positional of refs.fetch is `log`, and passing dry_run there
        # silently downloaded - the flag whose entire help text is "filling a filesystem halfway
        # through is a worse failure than refusing at the start" did the thing it exists to avoid.
        refs.fetch(ks[name], a.to, a.organism, dry_run=bool(getattr(a, "dry_run", False)))
    return 0


def _split(s):
    """Comma-separated names, DEDUPLICATED, first occurrence wins.

    Under the old serial loop a repeated `--kernel cellcycle,cellcycle` merely ran the plugin
    twice and the second overwrote the first, harmlessly. Concurrency turned it into two
    subprocesses writing one directory at once - and merge_many then took the multi-unit branch
    and refused the result as "the units are not disjoint" for a run with no units, so a plugin
    the user asked for TWICE produced nothing at all.
    """
    seen, out = set(), []
    for x in str(s).split(","):
        x = x.strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


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
    from .kernels import (_budget, concurrency, discover, guard_verdict, log_escape, schedule,
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
    # UNCONDITIONALLY, AND FIRST. Every later writer - report.json, report/, README.md - assumes
    # this exists, and until this line the only thing that created it was the `objects/` mkdir
    # further down. The moment that mkdir became conditional on something having merged, a run in
    # which every plugin refused died with FileNotFoundError on `report.json` - losing the report
    # for exactly the run whose report matters most. A directory the whole function writes into
    # is the function's own precondition, not a side effect of one of its branches.
    out.mkdir(parents=True, exist_ok=True)
    print(f"reading {a.h5ad}")
    A = ad.read_h5ad(a.h5ad)
    print(f"  {A.n_obs:,} cells x {A.n_vars:,} genes")

    try:
        keys = inputs.detect_keys(
            A.obs.columns, layers=manifest.layer_names(A), obsm=list(A.obsm),
            overrides={"label": a.label_key, "sample": a.sample_key, "batch": a.batch_key,
                       "counts_layer": a.counts_layer, "compartment": a.compartment_key,
                       "lognorm_layer": getattr(a, "lognorm_layer", None),
                       "embedding": getattr(a, "embedding", None)})
    except inputs.Refuse as e:
        print(f"scprofile: REFUSE - {e}", file=sys.stderr)
        return REFUSE
    organism = inputs.detect_organism(list(A.var_names), a.organism)
    assay = inputs.detect_assay(A, a.assay)
    # A DEFAULT, NOT A DEFINITION. `--sentinels` replaces them outright and `--sentinels ""` says
    # this annotation has none - a tool that knows only one annotator's sentinels treats another's
    # as a cell population, which is the same failure as not knowing about sentinels at all.
    sentinels = (tuple(_split(a.sentinels)) if getattr(a, "sentinels", None) is not None
                 else inputs.DEFAULT_SENTINELS)
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

    # THE SAME LEADS THE PLAN SEARCHED. `plan` looks in `prov.search_paths` PLUS the directories
    # around the object (`ancestry_roots`) plus `--search`; this passed only the first and the
    # third, so a plan could report "velocity would find its counts at X" and the run then never
    # looked there. A recorded chain is only as long as the tools that wrote it, and walking up
    # from the object is the generic recovery - a plan that promises what the run cannot deliver
    # is worse than one that promises nothing.
    prov = provenance.harvest(
        A, extra_roots=_split(a.search or "") + provenance.ancestry_roots(a.h5ad))
    provenance.describe(prov, log=print)

    # From DETECTION, not from a literal. `{lognorm}` is a key a plugin names; which layer it
    # resolves to is this object's business, and `--lognorm-layer` says so outright. ONE
    # FUNCTION, because this was written out twice here and omitted at the third place - the one
    # that writes `in.json`, which is the only one a plugin ever sees.
    _km = inputs.capability_keys(keys)
    have_obs = set(A.obs.columns)
    have_obsm = set(A.obsm)
    have_layers = set(manifest.layer_names(A))
    allowed = set(_split(a.allow or ""))
    ran, payloads, skipped = [], [], []
    #: {kernel: out_dir} for kernels that have already finished, handed to each later kernel so it
    #: can read a predecessor's result directly. This is what makes `needs_kernels` mean something
    #: beyond ordering.
    upstream = {}
    #: Derived capabilities this run will have, because a plugin in it provides them. The host
    #: resolves `inject` against these; a plugin never names another plugin.
    _provided = {c for n in want for c in (ks[n].spec.get("provides") or [])}
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
    # `per_unit` is a CORRECTNESS declaration before it is a speed one, so a plugin that declares
    # it and then runs once over everything is not merely slower - it is answering a different
    # question. With no sample key there is no alternative, but silence here would have delivered
    # a pooled number under a per-unit plugin's name with nothing anywhere saying so.
    pooled = [n for n in want if ks[n].per_unit and not units]
    if pooled:
        print(f"  WARNING: {', '.join(pooled)} declare per_unit and no unit key was found in "
              f"this object, so each runs ONCE OVER ALL CELLS. An inference pooled over a cohort "
              f"describes the average of its conditions and may describe none of them.")
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
    merged_slots = {}     # plugin -> what merge ACTUALLY put in the object
    timings = {}
    from . import feedback as FB
    diagnoses = []        # what these failures say about the TOOLING, not about the data
    repaired = set()      # plugins rebuilt mid-run, so a retry is never silent

    def _stage(inst):
        """EVERYTHING THAT CAN REFUSE - guards, references, the readable copy. Writes no in.json.

        Split from the write because `in.json` carries the core share, and the share can only be
        correct once the set of instances that will actually launch is known. Three of the filters
        live here - a guard verdict, a missing reference, an object the plugin's interpreter
        cannot read even re-encoded - and dividing the budget before them handed cores to
        instances that were about to be dropped. docs/EXECUTION.md claimed the division happened
        after all of them; it happened after two of the five.
        """
        name, unit = inst["plugin"], inst["unit"]
        k = ks[name]
        allow, why, escape = guard_verdict(
            k, describe=inputs.describe(A, keys, organism, assay, csrc),
            constraint=constraint, params={})
        if not allow and k.name not in allowed:
            return None, None, [f"guard refused: {why}",
                                f"override with {escape} (it is logged)"]
        if not allow:
            log_escape(out / "guard_overrides.jsonl", k.name, str(why))
        try:
            # `k.reference_organisms()`, NOT `k.references(organism)`. The latter filters by
            # organism, so a plugin with mouse and human references run on any other species
            # returned {} - and the host read that as "needs none" and skipped the check entirely.
            r = refs.resolve(k, a.references, organism[0]) if k.reference_organisms() else {}
        except FileNotFoundError as e:
            return None, None, [str(e)]
        kout = out / "kernels" / name / (str(unit) if unit else "")
        kout.mkdir(parents=True, exist_ok=True)
        exe, _src = runner.interpreter(k, a.prefix)
        k_h5ad = a.h5ad
        if exe:
            k_h5ad = compat.readable_input(A, a.h5ad, exe, out, cache=readable)
            if k_h5ad is None:
                return None, None, [f"{name}'s interpreter cannot read this object even re-encoded"]
        return kout, {"refs": r, "h5ad": k_h5ad}, None

    def _write_in(inst, kout, ctx):
        """The in.json, written only once the core share is final."""
        name, unit, cores = inst["plugin"], inst["unit"], inst["cores"]
        # ONE DIRECTORY ONLY WHEN ONE IS CORRECT. An upstream that ran once has a single output;
        # a per-unit upstream has one per unit, and the only unambiguous choice is THIS instance's
        # own unit. Where neither holds, `upstream[name]` is left out and the consumer meets a
        # missing key rather than a plausible wrong directory - `upstream_units` carries all of
        # them for a method that genuinely needs the set.
        flat, per = {}, {}
        for up_name, by_unit in upstream.items():
            per[up_name] = {u: d for u, d in by_unit.items() if u is not None}
            if list(by_unit) == [None]:
                flat[up_name] = by_unit[None]
            elif unit is not None and unit in by_unit:
                flat[up_name] = by_unit[unit]
        manifest.write_input(
            kout / "in.json", h5ad=ctx["h5ad"], out_dir=kout,
            # THE SAME MAP THE PREREQUISITE CHECK USED. This wrote the raw roles, so the host
            # decided a plugin's `lognorm` was satisfied and then handed it a manifest with no
            # `lognorm` in it - the check and the delivery disagreed, and only the delivery is
            # what the plugin ever sees.
            keys=_km,
            organism=organism[0], assay=assay[0], design=a.design, references=ctx["refs"],
            reference_specs=ks[name].references(organism[0]),
            params=json.loads(a.params) if a.params else {},
            upstream=flat, upstream_units={k_: v_ for k_, v_ in per.items() if v_},
            sentinels=sentinels,
            provenance=prov, resources={"cores": cores}, unit=unit)
        return kout

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
                          has_design=bool(a.design), keys=_km, organism=organism[0],
                          var=set(A.var.columns), derived=_provided)
            if probs and not a.force:
                if name not in {s["kernel"] for s in skipped}:
                    skipped.append({"kernel": name, "why": probs})
                continue
            live.append(inst)
        if not live:
            continue

        # STAGE FIRST, THEN BUDGET, THEN WRITE. `schedule` sizes a wave from every requested
        # plugin; five filters then remove instances, and each takes a share of the cores with it.
        # Measured before this was reordered: `run --all --cores 8` on a 10-sample object built a
        # wave of 35 instances declaring 301 cores, scaled EVERY instance to 1, and ran velocity
        # single-threaded on an 8-core allocation - while `plan --cores 8`, which filters first,
        # printed velocity(7c) for the same command. Two documents of one run disagreeing is how
        # it was found; then a review found the reorder had covered only two of the five filters,
        # while the document it added claimed all of them.
        staged = []
        for inst in live:
            kout, ctx, why = _stage(inst)
            if kout is None:
                lbl = inst["plugin"] + (f"[{inst['unit']}]" if inst["unit"] else "")
                print(f"  NOT RUN {lbl}")
                for w in why:
                    print(f"      {w}")
                skipped.append({"kernel": inst["plugin"], "unit": inst["unit"], "why": why})
                continue
            staged.append((inst, kout, ctx))
        if not staged:
            continue
        _budget([i for i, _k, _c in staged], budget)
        at_once = concurrency([i for i, _k, _c in staged], budget)
        print(f"\n=== wave {wi} === " + ", ".join(
            f"{x['plugin']}" + (f"[{x['unit']}]" if x["unit"] else "") + f"({x['cores']}c)"
            for x, _k, _c in staged)
              + (f"   [{at_once} at a time of {len(staged)}]"
                 if at_once < len(staged) else ""), flush=True)
        prepared = [(inst, _write_in(inst, kout, ctx)) for inst, kout, ctx in staged]

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
                # Run-relative, so a run-level document's links resolve. Without it the report
                # built `../kernels/<name>/<fig>` for a file at `../kernels/<name>/<unit>/<fig>`.
                pl["dir"] = str(kout.relative_to(out))
                return inst, kout, pl, _time.perf_counter() - t0, None
            except Exception as e:                                        # noqa: BLE001
                return inst, kout, None, _time.perf_counter() - t0, f"{lbl}: {e}"

        # AT MOST `at_once`, which is the rule EXECUTION.md §4 has always stated and nothing
        # implemented. Telling 35 instances that they have one core each and then starting all 35
        # is the oversubscription the core share exists to prevent, wearing the other hat.
        with cf.ThreadPoolExecutor(max_workers=at_once) as ex:
            done = list(ex.map(_go, prepared))

        for inst, kout, pl, secs, err in done:
            name = inst["plugin"]
            lbl = name + (f"[{inst['unit']}]" if inst["unit"] else "")
            timings.setdefault(name, []).append(round(secs, 1))
            # ALSO ON THE INSTANCE. `timings` is keyed by plugin, and the report's schedule table
            # has one row per INSTANCE - so it rendered the plugin's whole runtime on every unit's
            # row, reporting 10,000s of compute for 1,000s of work on a ten-unit plugin, and
            # showing that time even on rows for units that never ran.
            inst["seconds"] = round(secs, 1)
            inst["outcome"] = "failed" if err else "ok"
            if err:
                # One instance failing must not take the wave. A per-unit plugin failing on one
                # unit reports that unit as absent and keeps the rest.
                print(f"  FAILED {lbl}  ({secs:.0f}s)")
                print(f"      {err}")
                dg = FB.diagnose(name, err, prefix=a.prefix)
                print(f"      [{dg.layer}] {dg.why}")
                diagnoses.append(dg)

                # THE run -> build EDGE. An environment failure is the one class this can repair
                # itself, and it repairs it ONCE. A loop that retries until something works turns
                # a real defect into an intermittent one, which is the hardest kind to ever fix.
                if dg.repairable and a.prefix and name not in repaired:
                    repaired.add(name)
                    # NAME WHAT IS ACTUALLY BEING REBUILT. An environment resolved as shared is
                    # not "{name}'s environment", and a --force rebuild of it removes and rebuilds
                    # it for every plugin that resolves there. That is correct - a shared
                    # environment is not divisible - and it is not something to discover from the
                    # elapsed time.
                    _g, _gp = runner.env_for(ks[name], a.prefix)
                    _also = [m for m in (_g.members if _g else []) if m != name]
                    print(f"      REPAIRING: rebuilding {name}'s environment and retrying once"
                          + (f"\n      that environment is {_g.name}, SHARED WITH "
                             f"{', '.join(_also)} - all of them are rebuilt and re-proved"
                             if _also else ""))
                    try:
                        runner.install(ks[name], a.prefix, force=True,
                                       log=lambda s: print(f"        {s}"))
                    except Exception as e2:                               # noqa: BLE001
                        print(f"        REBUILD FAILED: {str(e2).splitlines()[0][:140]}")
                        skipped.append({"kernel": name, "unit": inst["unit"],
                                        "why": [err, f"rebuild also failed: {e2}"]})
                        continue
                    inst2, kout2, pl2, secs2, err2 = _go((inst, kout))
                    timings.setdefault(name, []).append(round(secs2, 1))
                    if err2:
                        print(f"      STILL FAILED after rebuild: {err2}")
                        diagnoses.append(FB.Diagnosis(
                            FB.DECLARATION,
                            f"{name} failed, its environment was rebuilt from its lock, and it "
                            f"failed again the same way. The environment is not the cause; the "
                            f"plugin or its lock is.", evidence=str(err2)))
                        skipped.append({"kernel": name, "unit": inst["unit"],
                                        "why": [err, "and again after a clean rebuild"]})
                        continue
                    # IT WORKED AFTER A REBUILD, WHICH IS ITSELF A FINDING. The environment had
                    # drifted from its lock, and somebody needs to know that about this machine.
                    print(f"      RECOVERED after rebuild ({secs2:.0f}s)")
                    diagnoses.append(FB.Diagnosis(
                        FB.ENVIRONMENT,
                        f"{name} failed and then succeeded after its environment was rebuilt "
                        f"from the same lock. The installed environment had DRIFTED - this run "
                        f"is fine, and the next one on this machine will fail the same way "
                        f"until it is rebuilt.",
                        repairable=True,
                        action=f"scprofile install {name} --prefix {a.prefix} --force"))
                    pl, secs, err = pl2, secs2, None
                else:
                    skipped.append({"kernel": name, "unit": inst["unit"], "why": [err]})
                    continue
            print(f"  {lbl:<28} {pl['status']:<8} {secs:>6.0f}s  {pl.get('headline', '')}")
            # THE run -> declare EDGE, the cheapest in the loop: the run has happened and the
            # declaration is right there. A plugin whose `produces` no longer matches what it
            # emits has drifted, and the next person to read the declaration will believe it.
            for dd in FB.declaration_drift(ks[name], pl):
                print(f"      [{dd.layer}] {dd.why}")
                diagnoses.append(dd)
            # AND THE RULE THE HOST STATES BUT CANNOT APPLY. Only the plugin knows what it groups
            # by, so the host cannot keep sentinels out of a plugin's populations - it can only
            # offer `ctx.real_cells()` and then check. A rule stated and never checked holds until
            # somebody writes a plugin.
            for dd in FB.sentinel_as_population(kout, pl, sentinels):
                print(f"      [{dd.layer}] {dd.why}")
                diagnoses.append(dd)

            extra = undeclared(ks[name], pl)
            if extra:
                print(f"      UNDECLARED OUTPUT: {', '.join(extra)} - no `cannot_show` covers "
                      f"them and no documentation mentions them")
                pl.setdefault("caveats", []).append(
                    "Wrote " + ", ".join(extra) + " without declaring them in kernel.yml.")
            for c in pl.get("caveats", []):
                print(f"      caveat: {c}")
            if pl.get("status") in ("ok", "partial"):
                # BY UNIT. `upstream[name] = kout` wrote once per instance under the plugin's
                # name, so a ten-unit upstream left ONE directory - the last that SUCCEEDED, which
                # changes between runs as different units fail - and a downstream plugin read one
                # sample as the cohort's result with nothing recording which.
                upstream.setdefault(name, {})[inst["unit"]] = kout
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
                skipped.append({"kernel": name, "unit": None, "why": [str(e)]})
                continue
            merged_slots[name] = got
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

    FB.report(diagnoses)
    describe = inputs.describe(A, keys, organism, assay, csrc)
    folded = merge.fold_payloads(
        payloads, failed={s["kernel"]: [x["unit"] for x in skipped if x["kernel"] == s["kernel"]]
                          for s in skipped})
    A.uns["scprofile"] = merge.provenance(
        folded, describe, {n: ks[n].cannot_show for n in ran}, merged=merged_slots)
    # NOTHING MERGED, NOTHING TO WRITE. When every plugin refused, failed or was skipped, `A` is
    # still exactly the object that was read, and writing it out is a multi-gigabyte copy of the
    # input under a name that says it was profiled. It is not merely wasteful - it is the one
    # artifact a reader opens to see what the run produced, and it looks identical whether the
    # run produced everything or nothing. The absence is NAMED here and `report.json` carries a
    # null `object`, so a consumer can tell "no object" from "an object I have not looked at".
    #
    # `merged_slots` IS NOT THE TEST, and using it as one was the first version of this. A plugin
    # that ran and refused still gets an entry - {'obs': [], 'obsm': [], 'layers': []} - which is
    # a truthy dict describing nothing. PBS 676944 wrote 3.21 GB on the strength of it: velocity
    # recovered from its environment failure, then refused for want of spliced counts, and the
    # run reported an object it had contributed nothing to. What matters is whether anything
    # LANDED - cell-level data merged into it, or tables and side-car objects written beside it
    # that a reader will want the provenance for.
    op = None
    merged_anything = any(v for got in merged_slots.values() for v in got.values())
    beside_it = any((pl.get("tables") or pl.get("objects")) for pl in payloads)
    if merged_anything or beside_it:
        (out / "objects").mkdir(parents=True, exist_ok=True)
        op = out / "objects" / a.object_name
        from .emit import write_h5ad
        write_h5ad(A, op)
        print(f"\nwrote {op}  ({op.stat().st_size / 1e9:.2f} GB)")
    else:
        why = ("no plugin ran" if not ran else
               "the plugin(s) that ran - " + ", ".join(ran) +
               " - produced nothing to merge and nothing to place beside it")
        print(f"\nNO OBJECT WRITTEN: {why}, so the only object this run could write is a copy "
              f"of\n  {a.h5ad}\nunder a name that says it was profiled. The reports below still "
              f"describe what happened and why.")

    payload = {"version": _v(), "input": str(a.h5ad), "describe": describe,
               "constraint_on_use": constraint, "constraint_source": csrc,
               "ran": ran, "skipped": skipped,
               "status": {n: ks[n].status for n in sorted(ks)},
               "schedule": [[{kk: vv for kk, vv in i.items()} for i in w] for w in waves],
               "seconds": timings, "cores": budget, "units": units,
               "timeout": a.timeout,
               "kernels": folded,
               "merged": merged_slots,
               "partial": sorted({s["kernel"] for s in skipped} & set(ran)),
               # WHAT THIS RUN LEARNED ABOUT THE TOOLING, kept apart from what it learned about
               # the data. A defect in a plugin is not a property of somebody's cells.
               "diagnoses": [d.as_dict() for d in diagnoses],
               "repaired": sorted(repaired),
               "cannot_show": {n: ks[n].cannot_show for n in sorted(ks)},
               "summaries": {n: ks[n].summary for n in sorted(ks)},
               # WHAT THE PLUGINS ACTUALLY READ. When a plugin's pinned anndata cannot read the
               # object as written, the host hands it a compatibility copy instead - the matrices
               # in the classic encoding, uns entries dropped BY NAME, obsp/varm/varp not carried.
               # That file is not `input`, and every result in this run came from it. It is kept
               # for exactly that reason and named here, because 3 GB nobody can identify beside
               # an output directory is debris rather than a record.
               "input_read_by_kernels": (str(readable.get("converted"))
                                         if readable.get("converted") else None),
               "object": str(op) if op else None}
    (out / "report.json").write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    print(f"      {out}/report.json")
    # THE README IS WRITTEN LAST, and it has to be. It describes the directory BY INSPECTING IT,
    # which is the whole reason it can be trusted - and it was called two lines above
    # `report.write_all`, the only thing that creates `report/`. So every run shipped a README
    # whose layout section omitted the run's primary deliverable while section 3 of the same file
    # linked the reader into it, with a file count short by 1 + 1 + n_kernels. Inspecting too
    # early is the same failure as describing what was intended; it just fails the other way.
    idx = report.write_all(out, payload)
    print(f"      {idx}")
    _write_readme(out, payload)
    return 0


def _selftest(a):
    """Run each plugin's selftest with ITS OWN interpreter. Runs no analysis.

    A selftest used to run only at install time, which answers "did this environment work on the
    day it was built". Environments drift, and a plugin declaring `needs_env: false` has no
    install step at all - so its selftest never ran automatically, and a keyword the wrapped
    function forbids reached a real cohort before anything executed the call.

    WHAT THE DEFAULT SET IS, AND WHAT IT USED TO BE

    Every plugin that SHIPS a selftest. It used to be every plugin whose `status` is `built`, and
    those are different sets in the direction that matters: a status is about a plugin's run.py, a
    selftest is about its ENVIRONMENT. Four environments were built and proved at install time,
    and `scprofile selftest` then skipped all four because none of them has a wrapper yet -
    printing `2 passed` and exiting 0, which reads exactly like a clean sweep of everything
    installed. A check that silently narrows its own scope is worse than one that fails.
    """
    from . import runner
    from .kernels import discover
    ks = discover()
    # ASK THE KERNEL, do not guess from its path. A one-file plugin's selftest is a function in
    # the file, not a neighbouring `selftest.py`, and probing for the file put every one-file
    # plugin in the `not considered` list - which reads exactly like a plugin that was checked.
    shipped = [n for n in sorted(ks) if ks[n].has_selftest]
    names = _split(a.name or "") or shipped
    if not a.name:
        absent = [n for n in sorted(ks) if n not in shipped]
        if absent:
            # NAMED, not counted. A plugin missing from a list of results looks identical to one
            # that was checked and found fine.
            print(f"not considered - these ship no selftest: {', '.join(absent)}\n")
    bad = [n for n in names if n not in ks]
    if bad:
        print(f"scprofile: unknown plugin(s) {bad}. Known: {', '.join(sorted(ks))}",
              file=sys.stderr)
        return REFUSE
    ran, missing, failed, blocked = [], [], [], []
    for n in names:
        print(f"{n}:", flush=True)
        try:
            if runner.selftest(ks[n], prefix=a.prefix, log=print, timeout=a.timeout):
                ran.append(n)
            else:
                missing.append(n)
                print("  NO SELFTEST. Nothing has proved this plugin's call is well-formed "
                      "against the version installed; only a real run will.")
        except RuntimeError as e:
            # "no environment" is not the same as "the environment is broken", and collapsing them
            # loses the only one that has a fix.
            (blocked if "no interpreter to run" in str(e) else failed).append(n)
            print(f"  {'COULD NOT RUN' if n in blocked else 'FAILED'}\n{e}", file=sys.stderr)
        except Exception as e:                                            # noqa: BLE001
            failed.append(n)
            print(f"  FAILED\n{e}", file=sys.stderr)

    print(f"\n{len(ran)} passed, {len(failed)} failed, {len(blocked)} could not run, "
          f"{len(missing)} have no selftest")
    for label, group in (("without a selftest", missing), ("could not run", blocked)):
        if group:
            print(f"  {label}: {', '.join(group)}")
    # ANYTHING OTHER THAN "ran and passed" IS NOT SUCCESS. Returning 0 because nothing could run
    # is a check that passes for its own reasons, which is worse than no check at all.
    return 0 if (ran and not failed and not blocked and not missing) else REFUSE


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
    from . import compat, declare, inputs, manifest, provenance, refs, runner
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
            A.obs.columns, layers=manifest.layer_names(A), obsm=list(A.obsm),
            overrides={"label": a.label_key, "sample": a.sample_key, "batch": a.batch_key,
                       "counts_layer": a.counts_layer, "compartment": a.compartment_key,
                       "lognorm_layer": getattr(a, "lognorm_layer", None),
                       "embedding": getattr(a, "embedding", None)})
    except inputs.Refuse as e:
        print(f"scprofile: REFUSE - {e}", file=sys.stderr)
        return REFUSE
    organism = inputs.detect_organism(list(A.var_names), a.organism)
    assay = inputs.detect_assay(A, a.assay)
    # A DEFAULT, NOT A DEFINITION. `--sentinels` replaces them outright and `--sentinels ""` says
    # this annotation has none - a tool that knows only one annotator's sentinels treats another's
    # as a cell population, which is the same failure as not knowing about sentinels at all.
    sentinels = (tuple(_split(a.sentinels)) if getattr(a, "sentinels", None) is not None
                 else inputs.DEFAULT_SENTINELS)
    constraint, csrc = inputs.read_constraint(A)

    describe_p = {"n_obs": int(A.n_obs), "n_vars": int(A.n_vars)}
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

    sent = [s for s in sentinels
            if keys["label"][0] and s in set(A.obs[keys["label"][0]].astype(str))]
    print(f"  annotator sentinels         {', '.join(sent) if sent else 'none present'}"
          + (f"  (looking for {', '.join(sentinels)})" if sentinels and not sent else ""))

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
        # PRINTED WHOLE, AND WRAPPED RATHER THAN CUT. This took the first 4 lines and the first
        # 100 characters of each, silently. On the object that motivated the feature it stopped
        # at "...may carry visualisation, clustering and cell-type identification" and dropped
        # the clause beginning "it must NOT" - the half that says what you may not claim, which
        # is the entire reason an upstream tool writes a constraint at all. The audit two hundred
        # lines below reads the FULL text for "must NOT", so the check and the reader were
        # looking at different documents.
        import textwrap
        print(f"  constraint on use           PRESENT")
        for line in str(constraint).strip().splitlines():
            if not line.strip():
                continue
            for wrapped in textwrap.wrap(line.strip(), width=100) or [""]:
                print(f"      {wrapped}")
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
    # From DETECTION, not from a literal - and from the same function `run` uses, so the plan and
    # the run cannot disagree about what a plugin will be given.
    _km = inputs.capability_keys(keys)
    have_obs, have_obsm = set(A.obs.columns), set(A.obsm)
    have_layers = set(manifest.layer_names(A))
    import os
    prov = provenance.harvest(A)
    runnable, planned, todo = [], [], []
    _provided = {c for n in want for c in (ks[n].spec.get("provides") or [])}
    for name in sorted(want):
        k = ks[name]
        if k.status != "built":
            planned.append((name, k))
            continue
        probs = unmet(k, obs=have_obs, obsm=have_obsm, layers=have_layers,
                      ran=set(want), has_design=bool(a.design), keys=_km,
                      organism=organism[0], var=set(A.var.columns), derived=_provided)
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
                          has_design=bool(a.design), keys=_km,
                          organism=organism[0], var=set(A.var.columns), derived=_provided)
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

    # ---- THE RUN PLAN: one verdict per plugin, and why -----------------------------------------
    # docs/RUN_PLAN.md. The section above reports prerequisites; this one commits to a verdict and
    # has to justify it. The two are separate because a prerequisite list is a set of observations
    # and a plan is a decision, and only the decision can be audited.
    from . import planner as PL
    from .kernels import resolve_keys as _rk

    units = (sorted(set(A.obs[keys["sample"][0]].astype(str)))
             if keys["sample"][0] else [])
    dtab, dfactors = None, []
    if a.design:
        try:
            dtab, _dkey, dfactors = inputs.read_design(a.design, units)
        except Exception:                                                 # noqa: BLE001
            dtab, dfactors = None, []          # already reported above, as a refusal
    facts = PL.design_facts(dtab, dfactors, keys["sample"][0], units)
    facts["units"] = units

    roots = sorted(set(list((prov or {}).get("search_paths") or [])
                       + provenance.ancestry_roots(a.h5ad)
                       + _split(getattr(a, "search", "") or "")))
    present = {}
    for name in sorted(want):
        k, need = ks[name], {}
        # A REQUIRED CAPABILITY IS AN INPUT LIKE ANY OTHER, and until now the plan did not read
        # `inject` at all: the entrypoint refuses without one, and the plan - whose job is to say
        # that before a queue slot is spent - called the plugin RUN.
        for cap in k.injects_required:
            need[f"capability {cap}"] = declare.available(
                cap, keys=_km, obs=have_obs, obsm=have_obsm, layers=have_layers,
                var=set(A.var.columns), has_design=bool(a.design), organism=organism[0],
                derived=_provided)
        for c in _rk(k.needs_obs, _km):
            need[f"obs[{c}]"] = c in have_obs
        for c in _rk(k.needs_obsm, _km):
            need[f"obsm[{c}]"] = c in have_obsm
        # REFERENCE DATA IS AN INPUT LIKE ANY OTHER, and the plan ignored it entirely. A plugin
        # whose motif database has not been fetched was reported runnable and refused at run time
        # - the plan's whole job is to find that out before a queue slot is spent.
        if k.reference_organisms():
            org = organism[0]
            if org and str(org).lower() not in k.reference_organisms():
                need["reference data"] = False        # a species it cannot serve: BLOCKED
            elif not a.references:
                need["reference data"] = None         # NOT DETERMINED - nowhere was checked
            else:
                try:
                    st = refs.status(k, a.references, org)
                    need["reference data"] = bool(st) and all(v[0] == "present"
                                                              for v in st.values())
                except Exception:                                         # noqa: BLE001
                    need["reference data"] = None
        for c in _rk(k.needs_layers, _km):
            if c in have_layers:
                need[f"layers[{c}]"] = True
            elif not k.can_source_layers:
                need[f"layers[{c}]"] = False
            else:
                # THE THREE-STATE ANSWER. A plugin that goes looking has not been answered until
                # the search has actually run: True found, False searched-and-absent, and None
                # NOT DETERMINED - which is UNRESOLVED and must never become a skip.
                try:
                    hits = provenance.find_layer_sources(roots, (c,)) if roots else []
                    if hits:
                        need[f"layers[{c}]"] = True
                    elif not roots or provenance.find_layer_sources.exhausted:
                        # NOT DETERMINED. The walk stopped on a limit or an unreadable directory,
                        # so "found nothing" is a statement about the SEARCH. Reporting it as an
                        # absence is how a plan tells someone their aligner output does not exist
                        # when it is sitting two directories past where the walk gave up.
                        need[f"layers[{c}]"] = None
                    else:
                        need[f"layers[{c}]"] = False
                except Exception:                                         # noqa: BLE001
                    need[f"layers[{c}]"] = None
        present[name] = need

    def _build_state(k):
        """installed / host / override -> ready; missing / stale -> a defect; None -> unchecked."""
        if not k.needs_env:
            return "host"
        if not a.prefix:
            return None                    # nowhere was checked, and that is not "fine"
        st, _why, _fix = runner.env_state(k, a.prefix)
        return st

    def _make_plan():
        # EVERY plugin is planned against the project, INCLUDING the ones this installation
        # cannot run yet. That is the whole point: "on your data this would run at full, and it
        # needs its wrapper built" is useful, and "BLOCKED" is not.
        will = {n for n in sorted(want)}
        out = []
        for n in sorted(want):
            k = ks[n]
            v = PL.plan_kernel(k, present=present, facts=facts, searched=roots,
                               ran=will, constraint=constraint)
            v.readiness = PL.build_state(k, _build_state(k), prefix=a.prefix)
            v.settings = PL.settings_for(
                k, keys={**{r_: kv[0] for r_, kv in keys.items()},
                         "organism": organism[0]},
                facts=facts, references=a.references, cores=a.cores)
            out.append(v)
        return out

    verdicts = _make_plan()

    print("\nRUN PLAN")
    print(f"  {len(units)} unit(s) on {keys['sample'][0]!r}" if units
          else "  no unit key found on this object")
    if facts.get("has_design"):
        for fn, fv in sorted(facts["factors"].items()):
            print(f"  {fn:<12} {fv['n_levels']} level(s), smallest arm n={fv['min_replicates']}: "
                  + ", ".join(f"{k2}={len(v2)}" for k2, v2 in sorted(fv["levels"].items())))
        print(f"  testable: {', '.join(facts['testable']) or 'none'}"
              + (f"   crossed: {facts['crossed_pairs']}" if facts["crossed_pairs"] else ""))
    else:
        print("  no design table given")
    # AN INCOMPLETE WALK THAT FOUND WHAT IT NEEDED IS NOT A WARNING. It matters only for inputs
    # reported ABSENT - those may merely be unfound - and saying "INCOMPLETE" over a plan where
    # every input resolved trains the reader to skip the line that will one day matter.
    _unresolved = [n for n, need in present.items() if any(v is None for v in need.values())]
    print(f"  searched {len(roots)} location(s), {provenance.find_layer_sources.visited:,} "
          f"director(ies), to depth {provenance.find_layer_sources.deepest}"
          + ("  -- the walk did not finish; nothing was reported absent on the strength of it"
             if provenance.find_layer_sources.exhausted and not _unresolved else "")
          + ("  -- INCOMPLETE, and it matters: see UNRESOLVED below"
             if provenance.find_layer_sources.exhausted and _unresolved else ""))

    ready, pending = PL.ready_count(verdicts)
    will_run = [v for v in verdicts if v.verdict == PL.RUN]
    print(f"\n  ON THIS PROJECT: {len(will_run)} of {len(verdicts)} plugin(s) would run.")
    print(f"  IN THIS INSTALLATION: {len(ready)} ready now, {len(pending)} need building first.")
    print("  Those are different questions and this plan answers both separately - a plugin that")
    print("  is not built yet is not a limitation of your data.")
    print()
    # ---- the prescription: what runs, in what order, with what settings ----------------------
    runs = [v for v in verdicts if v.verdict == PL.RUN]
    waves = PL.order_of_runs([v.plugin for v in runs], ks)
    byname = {v.plugin: v for v in verdicts}
    if waves and runs:
        print("  ORDER OF RUNS - a wave waits only on what the graph says it waits on:")
        for i, w in enumerate(waves, 1):
            print(f"    wave {i}: " + ", ".join(w))
    print()
    for i, w in enumerate(waves, 1):
        for name in w:
            v = byname[name]
            head = v.verdict + (f" ({v.rung})" if v.rung else "")
            tag = "" if not v.readiness else f"   [prepare first: {v.readiness['kind']}]"
            print(f"  wave {i}  {head:<14} {v.plugin}{tag}")
            for key, val in sorted(v.settings.items()):
                if isinstance(val, dict):
                    if key == "per_unit":
                        print(f"      {key:<14} {val['mode']}, {val['n']} unit(s) on "
                              f"{val['key']!r}")
                    elif key == "contrast":
                        print(f"      {key:<14} {val['kind']}: {val['formula']}")
                        print(f"                     {val['why']}")
                    elif key == "references":
                        print(f"      {key:<14} {val['organism']}, declared for "
                              f"{', '.join(val['declared_for'])}")
                else:
                    print(f"      {key:<14} {val}")
            if v.why_not_higher:
                print(f"      NOT FULL:      {v.why_not_higher}")
            for c in v.caveats:
                print(f"      CAVEAT:        {c}")
            if v.readiness:
                print(f"      prepare with:  {v.readiness['fix']}")
    for v in sorted(verdicts, key=lambda x: x.plugin):
        if v.verdict == PL.RUN:
            continue
        print(f"  {v.verdict:<20} {v.plugin}")
        for w in v.why:
            print(f"      {w}")

    # ---- --build: repair what the plan found, then plan again ---------------------------------
    fixable = PL.fixable_builds(verdicts)
    pend = [v for v in verdicts if v.readiness]
    if pend and not getattr(a, "build", False):
        print(f"\n  PREPARATION: {len(pend)} plugin(s) are not ready in this installation.")
        print("  None of this is a limitation of your project - every one of them is planned")
        print("  above against your data. Run `scprofile plan ... --build` and this command will")
        print("  do the work it can and tell you precisely what is left:")
        for v in pend:
            mark = "auto" if (v.readiness or {}).get("fixable") else "you"
            print(f"    [{mark:>4}] {v.plugin:<12} {v.readiness['fix']}")
    if fixable and getattr(a, "build", False):
        print(f"\n=== --build: repairing {len(fixable)} build defect(s) ===")
        print("  ONLY build defects trigger this. A missing design table or an absent layer is a")
        print("  fact about the project and is never something this tool installs its way out of.")
        repaired, failed = [], []
        for name, d in fixable:
            print(f"\n  {name}: {d['kind']}")
            print(f"    {d['fix']}")
            try:
                runner.install(ks[name], a.prefix, force=(d["kind"] == "env_stale"), log=print)
                repaired.append(name)
            except Exception as e:                                        # noqa: BLE001
                # TROUBLESHOOT, do not just report. A build failure has a small number of causes
                # and each has a different remedy; printing the traceback and stopping leaves the
                # user to work out which one they hit.
                msg = str(e)
                print(f"    BUILD FAILED: {msg.splitlines()[0][:160]}")
                hints = []
                low = msg.lower()
                if "no micromamba" in low or "conda" in low and "path" in low:
                    hints.append("no conda/mamba on PATH. On a cluster this is usually a module: "
                                 "`module load anaconda3` before running, or build the "
                                 "environment yourself from the lock and point "
                                 f"SCPROFILE_{name.upper()}_PYTHON at its python.")
                if "selftest" in low:
                    hints.append("the environment BUILT and its selftest failed, so the packages "
                                 "resolved but the call they make does not work. That is a lock "
                                 "problem, not a network one - the versions in "
                                 f"kernels/{name}/lock.yml need revisiting.")
                if "no space" in low or "disk" in low:
                    hints.append("out of disk on the prefix. Environments here run to a few GB "
                                 "each; pick a --prefix with room.")
                if "timed out" in low or "temporary failure" in low or "resolve" in low:
                    hints.append("looks like a network failure reaching the package index. "
                                 "Retrying is reasonable; a compute node with no outbound route "
                                 "is not.")
                if "cython" in low or "wheel" in low or "build" in low and "failed" in low:
                    hints.append("a package tried to build from source and could not. If it is "
                                 "available from conda-forge, move it out of the pip section of "
                                 f"kernels/{name}/lock.yml into the conda dependencies.")
                if not hints:
                    hints.append("no known signature matched. The full error is above; the lock "
                                 f"is kernels/{name}/lock.yml.")
                for h in hints:
                    print(f"      -> {h}")
                failed.append((name, e))
        print(f"\n  repaired {len(repaired)}, failed {len(failed)}")
        if repaired:
            # RE-PLAN, do not patch the verdicts. A plan edited after the fact is a plan whose
            # verdicts were not all produced by the same procedure.
            print("\nRUN PLAN, re-derived after the repairs")
            verdicts = _make_plan()
            for v in sorted(verdicts, key=lambda x: (x.verdict != PL.RUN, x.plugin)):
                head = v.verdict + (f" ({v.rung})" if v.rung else "")
                print(f"  {head:<16} {v.plugin}")
        if failed:
            ok_all = False

    audit_found, audit_checks, audited = [], [], False
    if getattr(a, "audit", False):
        audited = True
        print("\nAUDIT OF THIS PLAN")

        def _alog(line):
            audit_checks.append(str(line).strip())
            print(line)
        # AGAINST THE PLAN THAT WAS ASKED FOR, not against every plugin on disk. The completeness
        # rule exists so nothing VANISHES from a plan; stated over `ks` it fired on every plugin
        # the user had deliberately left out, so `plan --kernel a,b --audit` reported eight
        # ERRORs about plugins nobody asked to plan - and an audit that cannot be run clean on a
        # legitimate invocation is an audit people learn to pass a flag to silence.
        # `want` is every plugin when none were named, so the default answer does not change.
        found = audit_found = PL.audit(verdicts, sorted(want), facts, present=present, log=_alog)
        errs = [x for x in found if x.level == "ERROR"]
        for x in found:
            print(f"  {x.level}  {x.check}")
            if x.detail:
                print(f"      {x.detail}")
        print(f"\n  {len(errs)} error(s), {len(found) - len(errs)} warning(s)")
        if errs:
            print("  THIS PLAN IS NOT USABLE. Each error is a claim the plan cannot support.")
            ok_all = False

    # ---- the report --------------------------------------------------------------------------
    if getattr(a, "report", None):
        from . import plan_report
        payload = {
            "version": _v(), "h5ad": str(a.h5ad), "describe": describe_p,
            "facts": facts, "waves": waves, "roots": roots,
            "search_incomplete": bool(provenance.find_layer_sources.exhausted),
            "constraint_on_use": constraint, "constraint_source": csrc,
            "verdicts": [v.as_dict() for v in verdicts],
            # BOTH: what was CHECKED and what was FOUND. A clean audit returns an empty finding
            # list, so a report keyed on findings alone rendered a passing audit and an audit that
            # never ran identically - the exact failure this project's own audit rule names.
            "audited": audited, "audit_checks": audit_checks,
            "audit": [{"level": x.level, "check": x.check, "detail": x.detail}
                      for x in (audit_found or [])],
        }
        import json as _json
        outp = Path(a.report)
        outp.mkdir(parents=True, exist_ok=True)
        (outp / "run_plan.json").write_text(_json.dumps(payload, indent=1, default=str),
                                            encoding="utf-8")
        print(f"\nwrote {plan_report.write(outp, payload)}")
        print(f"      {outp}/run_plan.json")

    # ---- the schedule -------------------------------------------------------------------------
    if runnable:
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
    ran = payload.get("ran") or []
    # `skipped` holds one entry per INSTANCE; `ran` holds one per PLUGIN. Counting one against the
    # other printed "0 plugin(s) ran, 10 did not" for ONE ten-unit plugin, and "1 ran, 1 did not"
    # for a plugin that ran on nine samples of ten and is listed under both headings.
    by_kernel = {}
    for s in (payload.get("skipped") or []):
        by_kernel.setdefault(s["kernel"], []).append(s)
    partial = {k: v for k, v in by_kernel.items() if k in ran}
    did_not = {k: v for k, v in by_kernel.items() if k not in ran}
    (out / "README.md").touch()          # so the enumeration below counts this file too
    files = sorted(q for q in out.rglob("*") if q.is_file())
    by_dir = {}
    for q in files:
        by_dir.setdefault(str(q.parent.relative_to(out)) or ".", []).append(q.name)

    L = [f"# scProfile output", "",
         f"- **{len(ran)}** plugin(s) ran, **{len(did_not)}** did not"
         + (f", **{len(partial)}** ran but not on every unit" if partial else ""),
         f"- {len(files)} files, {sum(q.stat().st_size for q in files) / 1e9:.2f} GB", ""]

    L += ["## 1. What is this, and where did it come from?", "",
          f"Produced by scProfile {payload.get('version', '?')} from `{payload.get('input')}`.",
          f"Plugins that ran: {', '.join(ran) or 'none'}.", ""]
    if payload.get("input_read_by_kernels"):
        # WHAT THE PLUGINS ACTUALLY READ is not always what was passed in, and the README is the
        # document somebody opens. A 3 GB file beside the results that no document admits to is
        # not a record of anything.
        L += [f"The plugins did not read that file directly: their pinned anndata could not, so "
              f"they were given `{Path(payload['input_read_by_kernels']).name}` — the same "
              f"matrices in the classic encoding, with `uns` entries dropped by name and "
              f"obsp/varm/varp not carried. It is kept beside these results because it is what "
              f"the numbers came from.", ""]
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
        # THE FILES THAT ARE THERE, not the ones the flag implies. Asserting per-unit tables from
        # `per_unit` alone described `tables/<k>_*__<unit>.csv` for a per-unit plugin that declares
        # no tables at all - which is the exact failure this function's docstring says it avoids by
        # inspecting the directory, committed inside the function that says it.
        got = sorted(q.name for q in (out / "tables").glob(f"{k}_*")) if (out / "tables").is_dir() \
            else []
        if v.get("per_unit") and got:
            L.append(f"| `tables/{k}_*` | {len(got)} file(s), one per unit: "
                     + ", ".join(got[:4]) + (" …" if len(got) > 4 else "") + " |")
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
    if did_not:
        L.append("**Did not run:**")
        for k, ss in sorted(did_not.items()):
            why = "; ".join(str(w) for s in ss for w in (s.get("why") or []))[:300]
            L.append(f"- `{k}` — {why}")
        L.append("")
    if partial:
        # A plugin in both lists is the case both the README and the index used to render as a
        # plain success. Its merged column holds NaN for every cell of every failed unit, and that
        # is invisible in an object and in a headline alike.
        L.append("**Ran, but not on every unit** — the merged column is NaN for the cells of the "
                 "units named here, and no headline shows that:")
        for k, ss in sorted(partial.items()):
            us = ", ".join(str(s.get("unit")) for s in ss if s.get("unit") is not None) or "?"
            why = "; ".join(str(w) for s in ss for w in (s.get("why") or []))[:200]
            L.append(f"- `{k}` — {len(ss)} unit(s) failed ({us}): {why}")
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
    # LINE-BUFFER OUR OWN OUTPUT. Every long command here interleaves this process's `print` with
    # the UNBUFFERED output of subprocesses it launched - conda, pip, Rscript - on the same
    # descriptor. Redirected to a file or a pipe, which is every batch job, python block-buffers
    # while the children do not, so the log reads in an order the run did not happen in.
    #
    # Measured on PBS 676422: `--force: removing <prefix>` was still sitting in the buffer while
    # conda's solve scrolled past it, so the only evidence that a 3 GB directory had been deleted
    # arrived after the thing that followed it - and the first reading of that log was that the
    # removal had not happened. Four call sites had already been patched with `flush=True` one at
    # a time; this is the general form of the same fix.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass                       # a stdout that cannot be reconfigured is one to leave alone
    # WHO EACH COMMAND IS FOR. A user runs doctor/install/fetch/plan/run and nothing else; the
    # rest are for whoever MAINTAINS a plugin. Marking them is not decoration - a user who cannot
    # tell which commands are theirs assumes all of them are, and starts scaffolding.
    ap = argparse.ArgumentParser(
        prog="scprofile", description=(__doc__ or "") + """

  [you]        commands for running an analysis: doctor, install, fetch, plan, run, report
  [maintainer] commands for whoever maintains a plugin: validate, selftest, scaffold
               see docs/MAINTAINING_PLUGINS.md - a user should never need these
""",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"scprofile {_v()}")
    sub = ap.add_subparsers(dest="cmd", metavar="COMMAND")

    d = sub.add_parser("doctor", help="[you] what is installed, what is missing, and the exact fix")
    d.add_argument("--prefix", default=None, help="where kernel environments live")
    d.add_argument("--references", default=None, help="where reference data lives")
    d.add_argument("--organism", default=None)
    d.set_defaults(fn=_doctor)

    i = sub.add_parser("install", help="[you] build the environment a kernel resolves to")
    i.add_argument("kernel")
    i.add_argument("--prefix", required=True)
    i.add_argument("--force", action="store_true", help="rebuild an existing environment")
    i.add_argument("--dry-run", action="store_true",
                   help="resolve and report what would be built - the environment, who shares "
                        "it, and every package handed to the manager - and build nothing. The "
                        "resolver proves the DECLARED constraints do not contradict each other; "
                        "only a real resolve proves their transitive closure installs")
    i.set_defaults(fn=_install)

    f = sub.add_parser("fetch", help="[you] download and verify a kernel's declared references")
    f.add_argument("kernel")
    f.add_argument("--to", required=True)
    f.add_argument("--organism", default=None)
    f.add_argument("--dry-run", action="store_true",
                   help="report what would be downloaded, how much, and whether it fits. "
                        "Reference databases are gigabytes; filling a filesystem halfway through "
                        "is a worse failure than refusing at the start")
    f.set_defaults(fn=_fetch)

    r = sub.add_parser("run", help="[you] run kernels, merge results, write the report")
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
    r.add_argument("--lognorm-layer", default=None, metavar="LAYER",
                   help="the log-normalised layer. `lognorm` is what this tool family writes; "
                        "Seurat converters write `data` and Bioconductor `logcounts`, and the "
                        "host used to hard-code the first of those")
    r.add_argument("--embedding", default=None, metavar="OBSM_KEY",
                   help="obsm key to use as THE embedding. Detected otherwise, with the evidence "
                        "printed. This flag was declared and never read - the embedding was "
                        "picked inline from a fixed list headed by one integration tool's output")
    r.add_argument("--sentinels", default=None, metavar="A,B",
                   help="labels an annotator uses for 'no call', REPLACING the default "
                        "EXCLUDED,UNRESOLVED. Pass an empty string if this annotation has none")
    # NO `choices`. It was `[None, "mouse", "human"]`, which meant a user of any other species
    # could not even DECLARE their organism - argparse refused the flag before the tool could
    # refuse the analysis. Detection still only distinguishes mouse from human, by symbol casing,
    # and says so; but what a user tells the tool is not the tool's to restrict, and a plugin that
    # cannot serve a species should be the thing that says so, with a reason.
    r.add_argument("--organism", default=None, metavar="NAME",
                   help="the species. Detected from gene-symbol casing when it can be "
                        "(mouse/human only); anything you pass is taken as declared")
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

    pl = sub.add_parser("plan", help="[you] what WOULD run, and what stops it. Runs nothing")
    pl.add_argument("--h5ad", required=True)
    pl.add_argument("--kernel", default=None)
    pl.add_argument("--all", action="store_true")
    pl.add_argument("--prefix", default=None)
    pl.add_argument("--design", default=None)
    pl.add_argument("--cores", type=int, default=8)
    # THE SAME OVERRIDES AS `run`. A plan computed with different keys from the run it predicts
    # is a plan about a different object, and `plan` exists to be believed.
    for f in ("label-key", "sample-key", "batch-key", "counts-layer", "compartment-key",
              "lognorm-layer", "embedding", "sentinels", "organism", "assay"):
        pl.add_argument(f"--{f}", default=None)
    pl.add_argument("--references", default=None, metavar="DIR",
                    help="where reference data lives. WITHOUT IT the plan cannot tell a plugin "
                         "whose references are on disk from one whose are not, and reports both "
                         "as runnable - then the run refuses")
    pl.add_argument("--search", default=None, metavar="DIR,DIR",
                    help="extra directories to search for inputs not on the object")
    pl.add_argument("--report", default=None, metavar="DIR",
                    help="write the plan as an HTML page a person can read before committing a "
                         "cluster to it: what can run, what you get from each result, in what "
                         "order, with what settings, and what you must not conclude")
    pl.add_argument("--build", action="store_true",
                    help="repair the build defects the plan finds - install a missing "
                         "environment, rebuild a stale one - then re-derive the plan. ONLY build "
                         "defects; a missing design table or an absent layer is a fact about the "
                         "project and is never installed away")
    pl.add_argument("--audit", action="store_true",
                    help="check the plan by rules that do not repeat its reasoning: every plugin "
                         "accounted for once, no UNRESOLVED, every SKIP citing a design fact the "
                         "table supports, every BLOCKED naming where it looked, and no plugin "
                         "left below a rung the project would support")
    pl.set_defaults(fn=_plan)

    va = sub.add_parser("validate", help="[maintainer] static checks on plugins and their references")
    va.add_argument("name", nargs="?", default=None,
                    help="plugin name(s), comma-separated. Default: all")
    va.add_argument("--references", default=None, metavar="DIR",
                    help="also check the reference files on disk under this directory")
    va.add_argument("--deep", action="store_true",
                    help="verify reference checksums. Hashes gigabytes; this is what a run does "
                         "before trusting them")
    va.add_argument("--organism", default=None)
    va.set_defaults(fn=_validate)

    se = sub.add_parser("selftest", help="[maintainer] prove each plugin's environment still works")
    se.add_argument("name", nargs="?", default=None,
                    help="plugin name(s), comma-separated. Default: every built plugin")
    se.add_argument("--prefix", default=None, help="where kernel environments live")
    se.add_argument("--timeout", type=int, default=None, metavar="SEC")
    se.set_defaults(fn=_selftest)

    sc_ = sub.add_parser("scaffold", help="[maintainer] write a declared plugin's build skeleton")
    sc_.add_argument("name", help="plugin name(s), comma-separated")
    sc_.add_argument("--force", action="store_true", help="overwrite existing skeleton files")
    sc_.set_defaults(fn=_scaffold)

    p = sub.add_parser("report", help="[you] rebuild the documents from report.json")
    p.add_argument("--out", required=True, type=Path)
    p.set_defaults(fn=_report)

    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
