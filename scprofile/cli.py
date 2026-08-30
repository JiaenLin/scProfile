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


def _default_memory_gb():
    """The memory this process was ALLOCATED, preferring the scheduler over the machine.

    Same rule as `_default_cores` and for the same reason: a shared node reports every byte it
    has, and sizing a wave from that is how a job gets killed for exceeding a request it never
    knew about. PBS states the request in `PBS_VMEM`/`PBS_MEM` (bytes, or a suffixed string);
    the cgroup limit is the next most truthful source, and the machine's RAM is the last resort.
    """
    for var in ("PBS_VMEM", "PBS_MEM", "SLURM_MEM_PER_NODE"):
        v = (os.environ.get(var) or "").strip().lower()
        if not v:
            continue
        mult = {"k": 1 / 1024**2, "m": 1 / 1024, "g": 1.0, "t": 1024.0}
        try:
            if v[-2:] in ("kb", "mb", "gb", "tb"):
                return float(v[:-2]) * mult[v[-2]]
            if v[-1] in mult:
                return float(v[:-1]) * mult[v[-1]]
            n = float(v)
        except (ValueError, KeyError):
            continue
        # SLURM_MEM_PER_NODE is MB; a bare PBS value is bytes.
        return n / 1024.0 if var.startswith("SLURM") else n / 1024.0**3
    for f in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = open(f, encoding="utf-8").read().strip()
            if raw.isdigit() and int(raw) < (1 << 60):
                return int(raw) / 1024.0**3
        except OSError:
            pass
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024.0**3
    except (ValueError, OSError, AttributeError):
        return None


def _run(a):
    from . import compat, inputs, manifest, merge, provenance, refs, report, runner
    from .kernels import (UNDECLARED_GB_PER_100K, ResourcePool, _budget, concurrency,
                          fingerprint_drift, fit_memory_model, tool_fingerprint,
                          demand, discover, guard_verdict, log_escape, schedule,
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
            # THE DECLARATION *AND* ITS REFERENCES. Only `validate_plugin` was called here, so
            # every reference check lived in a maintainer command that no pipeline runs - which
            # is why a checker demanding a url from a bundled database went unnoticed through
            # eighteen runs. Static: no `dest`, so nothing is hashed and nothing is fetched.
            f = V.validate_plugin(ks[n]) + V.validate_references(
                ks[n], organism=getattr(a, "organism", None))
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
    try:
        A = ad.read_h5ad(a.h5ad)
    except Exception as exc:                      # noqa: BLE001 - re-raised unless explained
        said = compat.explain_read_failure(exc, a.h5ad)
        if said is None:
            raise
        print("scprofile: " + said, file=sys.stderr)
        return REFUSE
    print(f"  {A.n_obs:,} cells x {A.n_vars:,} genes")

    try:
        keys = inputs.detect_keys(
            A.obs.columns, layers=manifest.layer_names(A),
            # WIDTHS, NOT JUST NAMES. Handed a bare list of obsm keys the host could not tell a
            # 30-dimensional latent from a 2-dimensional layout, and chose the latent as the
            # thing to draw on - on an object that also carried the UMAP of that same latent.
            obsm={str(k): int(v.shape[1]) if getattr(v, "ndim", 0) == 2 else None
                  for k, v in A.obsm.items()},
            overrides={"label": a.label_key, "sample": a.sample_key, "batch": a.batch_key,
                       "counts_layer": a.counts_layer, "compartment": a.compartment_key,
                       "lognorm_layer": getattr(a, "lognorm_layer", None),
                       "embedding": getattr(a, "embedding", None),
                       "layout": getattr(a, "layout", None)})
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
    if assay[0] and str(assay[0]).lower() not in ("cell", "nucleus"):
        # SAID, NOT REFUSED. The value is carried through to every plugin; what the user needs to
        # know is that the caveats keyed on it will not fire.
        print(f"      {assay[0]!r} is not an assay this tool reasons about (cell, nucleus), so "
              f"assay-specific caveats will NOT be applied. It is carried through as declared.")
    if not assay[0]:
        # NAME THEM. "it changes what each kernel is allowed to claim" is true, and it is also
        # skippable - a cost with nothing named on it cannot be weighed, so a reader in a hurry
        # moves past it. I moved past it, and the run that followed would have shipped a cellchat
        # report with NO single-nucleus caveat on a single-nucleus study. Naming the plugins that
        # will fall silent makes it a decision instead of a note: a report that is silent because
        # nothing was known reads exactly like one that earned its silence.
        _dep = inputs.assay_dependent([ks[n] for n in want if n in ks])
        if _dep:
            print(f"      {len(_dep)} of the {len(want)} plugin(s) here branch on it and will "
                  f"emit NO assay caveat: {', '.join(_dep)}")
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
    # REUSE IS RECORDED, NOT SILENT. A run that reused nine of ten instances and one that
    # computed all ten produce the same directory; only this list distinguishes them, and the
    # report prints it.
    reused = []
    from . import resume as _resume

    def _collect_existing(name_, unit_, why_):
        """Fold an instance that is ALREADY on disk into this run's payload.

        AN INSTANCE THAT IS NOT RECOMPUTED IS STILL PART OF THE RUN. Skipping the computation
        and skipping the COLLECTION are different things, and doing both produced a run whose
        report.json held `ran: 0, kernels: []` while fourteen complete instances sat in its
        directory: 140 figures on disk and one page rendered. Reuse that loses the result is
        not reuse.
        """
        d = _resume.unit_dir(out, name_, unit_)
        try:
            pl_ = json.loads((d / "out.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        pl_.setdefault("kernel", name_)
        pl_.setdefault("unit", unit_)
        # THE PAYLOAD MUST SAY WHERE IT LIVES. `fold_payloads` falls back to `kernels/<plugin>`
        # when `dir` is absent - the PLUGIN directory, not the instance's - so every reused unit
        # pointed one level too high and the reporter found no per-unit table under it: the arm
        # panels silently vanished from a run whose figures were all present on disk.
        try:
            pl_["dir"] = str(d.relative_to(out))
        except ValueError:
            pl_["dir"] = str(d)
        # THE SAME MERGE A COMPUTED INSTANCE GETS. An adopted instance that skipped this would
        # reach the report but not the object: its obs columns and arrays would be missing from
        # the merged h5ad while its figures sat in the run directory.
        try:
            got_ = merge.merge_many(A, [(d, pl_)])
            for _slot, _names in (got_ or {}).items():
                if _names:
                    print(f"  merged {_slot}: {', '.join(_names)}")
            merge.copy_tables(d, pl_, out / "tables")
            merge.link_objects(d, pl_, out / "objects")
        except Exception as _e:                                              # noqa: BLE001
            print(f"  WARNING merging a reused instance failed: {_e}")
            return False
        payloads.append(pl_)
        if name_ not in ran:
            ran.append(name_)
        reused.append({"kernel": name_, "unit": unit_, **why_})
        return True

    from . import landscape as _LS, licence as _LCN

    # READ ONCE, NOT PER INSTANCE. Scanning every earlier run for each of fourteen instances
    # would re-walk the same directories fourteen times.
    _have_earlier = (_LS.scan(a.reuse_from, plugins=set(want))
                     if getattr(a, "reuse_from", None) else [])
    if _have_earlier:
        print(f"  reuse: {len(_have_earlier)} instance(s) found under {a.reuse_from}")
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
    samples = sorted(set(A.obs[sample_key].astype(str))) if sample_key else []
    # THE UNIT AXIS IS RESOLVED FROM THE DESIGN, GROUP FIRST. Single-cell inference is made over
    # a GROUP of cells; pooling an arm is the analysis, not a fallback from it. The sample axis
    # is run as well where the design supports it, and reports whether the members of an arm
    # agree - it is confidence, never a precondition.
    #
    # `--unit-by` selects the axis; the default runs the group axis and the sample axis both.
    from . import units as _UN

    # THE DESIGN IS READ HERE, AGAINST THE SAMPLES. It is read again further down against the
    # final unit list; that is cheap and keeps the later call unchanged. Reading it there only
    # would be circular - the unit axis needs the design, and that call needs the units.
    _axis_design = {}
    if getattr(a, "design", None):
        try:
            _axis_design, _adk, _adf = inputs.read_design(a.design, samples)
        except Exception as _e:                                              # noqa: BLE001
            print(f"  units: design not readable for axis resolution ({_e}); sample axis only")
    _plan_axes, _why_axes = _UN.resolve(_axis_design or {}, sample_key=sample_key,
                                        samples=samples,
                                        prefer=getattr(a, "unit_by", "both") or "both")
    unit_members = {}
    # WHICH AXIS EACH UNIT CAME FROM, CARRIED RATHER THAN INFERRED LATER. The reporter has to
    # tell an arm from an animal - a group unit's panels are the design result and an animal's
    # are the consistency check - and it was inferring it from whether the label happened to be
    # a key of the design table. That works until a project names an arm after a sample, and it
    # is a guess about something the resolver already knows for certain.
    unit_axis = {}
    for _ax in _plan_axes:
        for _u, _mem in _ax["units"].items():
            unit_members.setdefault(str(_u), list(_mem))
            unit_axis.setdefault(str(_u), _ax["kind"])
    units = sorted(unit_members) or (samples or None)
    for _w in _why_axes:
        print(f"  units: {_w}")
    # HOW BIG EACH UNIT ACTUALLY IS. Memory is charged per instance against the cells that
    # instance touches, and units are not equal - assuming n_obs/len(units) would under-charge
    # the largest, which is the one that decides whether the wave fits. A group unit is charged
    # the sum of its members.
    _per_sample = (A.obs[sample_key].astype(str).value_counts().to_dict() if sample_key else {})
    unit_cells = {u: sum(_per_sample.get(m, 0) for m in mem)
                  for u, mem in unit_members.items()} or _per_sample

    # WHICH POPULATIONS EACH UNIT EVEN CONTAINS, recorded once, here, where the object is open.
    # A per-unit method sees only the labels present in its own slice, so a population with no
    # cells in one arm is simply not in that arm's result - and every panel then draws the axis
    # it happens to have, with nothing anywhere saying the study has more. Measured on a real
    # cohort: a plugin reported 8 to 12 populations across 14 units against 15 labels in the
    # object, and no page named a single one of the missing.
    #
    # The host is the only layer that can say this. A plugin sees one unit by construction and
    # cannot know what it is missing; the reporter cannot open the object. So it is taken here
    # and carried, per label and per unit, as counts rather than as a presence flag - "absent"
    # and "two cells" are different facts and a boolean throws the second away.
    # `keys[role]` IS (name, why), NOT a name. The first version of this took `keys.get("label")`
    # whole, so the census silently produced nothing: a two-element list is not a column, the
    # `in A.obs` test was False, and the panel that depends on it was simply never drawn - on a
    # run that otherwise passed everything. `sample_key` two hundred lines up already does the
    # right thing and reads `keys["sample"][0]`.
    label_key = (keys.get("label") or (None,))[0]
    label_by_unit, label_total = {}, {}
    if label_key and label_key in A.obs and sample_key and sample_key in A.obs:
        _lab = A.obs[label_key].astype(str)
        _smp = A.obs[sample_key].astype(str)
        label_total = _lab.value_counts().to_dict()
        _by_sample = {}
        for (sm, lb), n in _lab.groupby(_smp).value_counts().items():
            _by_sample.setdefault(str(sm), {})[str(lb)] = int(n)
        for _u, _mem in (unit_members or {s: [s] for s in (samples or [])}).items():
            acc = {}
            for m in _mem:
                for lb, n in (_by_sample.get(str(m)) or {}).items():
                    acc[lb] = acc.get(lb, 0) + int(n)
            label_by_unit[str(_u)] = acc
    # WHAT THE CODE LOOKED LIKE WHEN THIS RUN STARTED. Re-checked before every instance.
    _tool_root = Path(__file__).resolve().parent.parent
    _tool_at_start = tool_fingerprint(_tool_root)

    # THE PLAN'S DECISIONS, COMPUTED HERE BY THE PLAN'S OWN FUNCTION - not read back from a plan
    # file. A run may be launched without one, and a decision recovered from a stale file would
    # be a decision about a different object. Same function, same inputs, same answer is the only
    # construction under which the plan and the run cannot disagree; anything else is two pieces
    # of code that happen to match today.
    from . import planner as _PL
    _run_facts = {"has_design": False}
    # BOUND BEFORE THE BRANCH. `_dtab` was set only inside `if a.design:` and read
    # unconditionally when the payload was assembled, so any run WITHOUT a design died at the
    # last step with an UnboundLocalError - after every plugin had finished. A run with no
    # design is the ordinary case for a cohort that has none, and it is what the smoke test
    # exercises.
    _dtab = None
    if a.design:
        try:
            # SAMPLES, NOT UNITS. A design table has one row per SAMPLE; a unit may now be
            # a design arm, and passing the unit list made four arm labels look like
            # samples missing from the table - "design table unreadable" on a table that
            # was perfectly readable.
            _dtab, _dkey, _dfactors = inputs.read_design(a.design, samples or [])
            _run_facts = _PL.design_facts(_dtab, _dfactors, sample_key, units or [])
        except Exception as e:
            print(f"  WARNING: design table unreadable, so the plan's decisions cannot be made "
                  f"or delivered: {e}")
    _decisions_said = set()

    def _params_for(name):
        """`--params` over the plan's decisions, and the run SAYS which it used.

        A decision delivered silently is one nobody can audit, and one overridden silently is
        worse: the plan's page still shows the formula that did not run.
        """
        user = json.loads(a.params) if a.params else {}
        dec = _PL.decisions_for(ks[name], _run_facts)
        out = dict(dec)
        out.update(user)
        if dec and name not in _decisions_said:
            _decisions_said.add(name)
            for key, val in sorted(dec.items()):
                shown = val.get("formula") if isinstance(val, dict) else val
                if key in user:
                    print(f"  {name}: --params {key} OVERRIDES the plan's {shown}")
                else:
                    print(f"  {name}: {key} {shown}  (decided from the design, by the planner)")
        return out

    budget = int(getattr(a, "cores", 0) or _default_cores())
    mem_budget = getattr(a, "memory_gb", None) or _default_memory_gb()
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

    def _write_in(inst, kout, ctx, need=None):
        """The in.json, written only once the core share AND the memory share are final."""
        name, unit, cores = inst["plugin"], inst["unit"], inst["cores"]
        mem_gb = (need or {}).get("memory_gb")
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
            params=_params_for(name),
            upstream=flat, upstream_units={k_: v_ for k_, v_ in per.items() if v_},
            sentinels=sentinels,
            # BOTH DIMENSIONS THE HOST SCHEDULES ON. `cores` alone was passed for as long as
            # this existed, and the plugin that partitions its allocation was left to infer the
            # other half from the machine.
            provenance=prov,
            resources={"cores": cores, **({"memory_gb": round(float(mem_gb), 2)}
                                          if mem_gb else {})},
            unit=unit, unit_members=unit_members.get(str(unit)),
            constraint=constraint)
        return kout

    for wi, wave in enumerate(waves, 1):
        # Prerequisites are re-checked at the START OF EACH WAVE, not once up front: a plugin may
        # become runnable because an earlier wave produced what it needed, and the graph only
        # orders — it does not know what a plugin actually wrote.
        live = []
        for inst in wave:
            name = inst["plugin"]
            k = ks[name]
            # ALREADY DONE, AND STILL VALID. Checked per wave, with the version the plugin
            # would run now, so a unit produced by older code is NOT reused - a resume that
            # cannot see a version change is a resume that keeps exactly the units a code
            # change invalidated. `--force-all` additionally discards `empty`, which is a
            # RESULT and is kept by default.
            if getattr(a, "resume", False):
                st, why, _n = _resume.state(
                    _resume.unit_dir(out, name, inst.get("unit")),
                    want_version=(k.spec or {}).get("version"))
                reuse = st in ((_resume.DONE,) if getattr(a, "force_all", False)
                               else _resume.FINISHED)
                if reuse:
                    lbl = name + (f"[{inst['unit']}]" if inst.get("unit") else "")
                    if _collect_existing(name, inst.get("unit"), {"state": st}):
                        print(f"  REUSED  {lbl}  ({st}: {why})")
                        continue
                    print(f"  not reused {lbl}: its out.json could not be read back")
            # ADOPT A LICENSED RESULT FROM AN EARLIER RUN INSTEAD OF RECOMPUTING IT.
            # `--resume` above reuses what THIS directory already holds; this reaches into
            # earlier runs, which is the ordinary case - a new run key means last week's work
            # sits one directory away and is otherwise recomputed from nothing.
            #
            # Nothing is adopted without a LICENCE that still verifies: the products are
            # re-hashed before the hardlink, so an adopted file cannot differ from the licensed
            # one. `--reuse-min-grade` is the policy and defaults to `provisional`; a
            # `retrospective` licence - a run that published no card - must be asked for.
            if getattr(a, "reuse_from", None):
                _w = _LS.wanted(name, inst.get("unit"),
                                version=(k.spec or {}).get("version"), h5ad=a.h5ad,
                                params=_params_for(name), keys=_km)
                _st, _src, _why = _LS.match(_w, _have_earlier)
                lbl = name + (f"[{inst['unit']}]" if inst.get("unit") else "")
                if _st == _LS.REUSABLE:
                    _lic = _LCN.read(_src["run_dir"], name, inst.get("unit"))
                    # A CANDIDATE THE LANDSCAPE ACCEPTS BUT NOBODY HAS LICENSED IS LICENSED NOW.
                    # `match` can approve on the run card alone; `adopt` requires a licence,
                    # because the licence is what carries the product hashes that make a
                    # hardlink safe. Without this the two disagreed and every adoption was
                    # refused with "grade None" after the landscape had said REUSE - fourteen
                    # instances recomputed at 9m21s against 1m56s.
                    #
                    # Granting here invents no evidence: integrity, completeness and provenance
                    # are computed from what is on disk, and the card the landscape just
                    # accepted IS the self-report. A grant that fails still refuses.
                    if _lic is None:
                        _k2 = ks.get(name)
                        _figs2 = ((_k2.spec or {}).get("report") or {}).get("figures") or []
                        _lic = _LCN.grant(
                            _src["run_dir"], name, inst.get("unit"),
                            declared=list((_k2.spec or {}).get("produces") or []),
                            required_figures=[f.get("id") for f in _figs2
                                              if isinstance(f, dict) and f.get("required")],
                            declared_version=(_k2.spec or {}).get("version"),
                            granter="adopted-on-demand")
                    n_f, how, bad = _LCN.adopt(_lic, out,
                                               min_grade=getattr(a, "reuse_min_grade",
                                                                 _LCN.PROVISIONAL))
                    if n_f and _collect_existing(
                            name, inst.get("unit"),
                            {"state": "adopted", "from": _src["run"],
                             "grade": _lic.get("grade"), "how": how}):
                        print(f"  ADOPTED {lbl}  {n_f} file(s) by {how} from {_src['run']}")
                        continue
                    if n_f:
                        print(f"  not adopted {lbl}: its out.json could not be read back")
                    print(f"  not adopted {lbl}: {'; '.join(bad) or 'refused'}")
                elif _src is not None:
                    print(f"  not adopted {lbl}: {'; '.join(_why[:1])}")
            if k.status != "built":
                if name not in {s["kernel"] for s in skipped}:
                    skipped.append({"kernel": name, "why": [
                        f"declared but not built. `scprofile scaffold {name}` writes the "
                        f"skeleton; the method still has to be wrapped."]})
                continue
            probs = unmet(k, obs=have_obs, obsm=have_obsm, layers=have_layers, available=ks, ran=ran,
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
        # PER-INSTANCE MEMORY IS COMPUTED FROM THE CELLS THAT INSTANCE TOUCHES, not from the
        # cohort. A per-unit instance sees its unit; charging it for the whole object would
        # serialise a wave that fits comfortably.
        #
        # COMPUTED HERE, BEFORE `in.json`, because the plugin needs it too. It used to be
        # computed after the manifests were written and used only to bound the wave - so the
        # host worked out what each instance may use, admitted it on that basis, and then told
        # the instance its core share and nothing about its memory. A plugin that partitions
        # its allocation could only guess, and one of them did: it sized a worker pool from
        # `ctx.cores` with no memory limit, dask divided the machine's memory by that count,
        # and the workers spent 86% of their CPU in garbage collection while 124 GB of the
        # job's own allocation sat unused.
        need = {}
        for inst, _k, _c in staged:
            u = inst.get("unit")
            n_cells = int(unit_cells.get(u, A.n_obs)) if u else A.n_obs
            need[(inst["plugin"], u)] = demand(inst, ks[inst["plugin"]], n_cells)
        prepared = [(inst, _write_in(inst, kout, ctx,
                                     need[(inst["plugin"], inst.get("unit"))]))
                    for inst, kout, ctx in staged]

        # Instances in a wave are independent by construction, so they run CONCURRENTLY. The
        # plugins are subprocesses, so threads are the right shape - each blocks on its child and
        # holds no lock. The merge afterwards is sequential because AnnData is not thread-safe.
        import concurrent.futures as cf
        import time as _time

        def _go(item):
            inst, kout = item
            lbl = inst["plugin"] + (f"[{inst['unit']}]" if inst["unit"] else "")
            t0 = _time.perf_counter()
            # THE CODE IS READ AT THIS LAUNCH, not at the start of the run. If the tool directory
            # moved underneath us - a `git pull` while a three-hour run is spawning instances -
            # everything after that point runs different code from everything before it, and the
            # run reports one commit for both. Refusing here turns a silent, unattributable
            # mixture into a loud failure naming the files that moved.
            _ch, _add, _rm = fingerprint_drift(_tool_at_start, tool_fingerprint(_tool_root))
            if _ch or _rm:
                _what = ", ".join((_ch + _rm)[:4]) + (" ..." if len(_ch + _rm) > 4 else "")
                return inst, kout, None, _time.perf_counter() - t0, (
                    f"{lbl}: THE TOOL CHANGED WHILE THIS RUN WAS IN PROGRESS ({_what}). "
                    f"Instances launched before this point ran different code, and a run that "
                    f"used two versions would report one. Refusing rather than producing a "
                    f"result nobody can attribute. Let the run finish or kill it before "
                    f"updating {_tool_root}.")
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

        # ADMISSION IS BY CORES, NOT BY COUNT. `at_once` is a headline for the plan; the pool is
        # what actually schedules, because a wave mixing a 16-core fit with 1-core instances has
        # no single correct thread count. Each instance takes the cores it was allocated and
        # releases them when its subprocess exits, so the allocation stays full without ever
        # being oversubscribed - the two failures a fixed pool has to choose between.
        pool = ResourcePool(budget, memory_gb=mem_budget)

        assumed = sorted({i["plugin"] for i, _k in prepared
                          if need[(i["plugin"], i.get("unit"))]["memory_assumed"]})
        if assumed and mem_budget:
            # SAID OUT LOUD, EVERY TIME. An assumed figure that is never printed is
            # indistinguishable from a measured one, and the whole point of the field is that
            # the plugin should state it.
            print(f"  memory not declared by {', '.join(assumed)}; assuming "
                  f"{UNDECLARED_GB_PER_100K:g} GB per 100k cells for scheduling. "
                  f"Declare `memory_gb_per_100k` to replace the guess.", flush=True)

        def _gated(item):
            inst, _kout = item
            d = need[(inst["plugin"], inst.get("unit"))]
            g = pool.acquire(d)
            try:
                return _go(item)
            finally:
                pool.release(g)

        # Threads block on permits before they spawn anything, so one per instance is cheap and
        # the pool decides what is resident. Sizing THIS to `at_once` would re-impose the count
        # limit the permits exist to replace.
        with cf.ThreadPoolExecutor(max_workers=max(1, len(prepared))) as ex:
            done = list(ex.map(_gated, prepared))

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
            for dd in (FB.declaration_drift(ks[name], pl) + FB.figure_drift(ks[name], pl)
                       + FB.metric_drift(ks[name], pl)
                       + FB.memory_drift(ks[name], pl, concurrent=len(staged))):
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

    # WHAT EACH PLUGIN ACTUALLY COST, fitted rather than divided. Every instance reported its
    # peak RSS and the cells it processed; a per-unit plugin gives several points at different
    # sizes, which is exactly what separates the fixed baseline from the per-cell slope. One
    # point cannot, and the fit says so instead of inventing a rate from it.
    memory_model = {}
    _by_plugin, _basis = {}, {}
    for _pl in payloads:                       # the RAW per-instance list; `folded` drops measured
        _m = _pl.get("measured")
        if not isinstance(_m, dict) or not _m.get("n_cells"):
            continue
        # THE LARGER OF THE MEASUREMENTS, by the same rule the drift diagnosis uses. Reading
        # `peak_rss_gb` here and the larger figure there would have the model and the warning
        # disagree about what one instance cost, and a maintainer would have to work out which
        # to believe. `peak_measurement` is the one place that decides.
        _peak, _src = FB.peak_measurement(_m)
        if _peak:
            _by_plugin.setdefault(_pl["kernel"], []).append((_m["n_cells"], _peak))
            _basis.setdefault(_pl["kernel"], set()).add(_src)
    # A JOB-WIDE COUNTER IS NOT A SET OF POINTS ON A PER-INSTANCE CURVE. Every instance that
    # shared one job reports the SAME figure, so a fit over them is a horizontal line through
    # one value repeated - which is exactly what "45.0 GB fixed + 0.0 GB/100k" was, from ten
    # instances spanning 7,374 to 11,985 cells. The fit was not weak; it was measuring nothing,
    # and it printed as a pair of numbers to copy into a declaration.
    #
    # DETECTED FROM THE DATA RATHER THAN PLUMBED THROUGH. Identical peaks at differing sizes is
    # the signature itself - it is the tell that found this - and reading it here means the
    # check cannot fall out of step with however the host happens to schedule waves.
    _unattributable = {}
    for _n in list(_by_plugin):
        _pts = _by_plugin[_n]
        if (len(_pts) > 1 and len({round(_gb, 6) for _sz, _gb in _pts}) == 1
                and len({_sz for _sz, _gb in _pts}) > 1
                and _basis.get(_n) == {"the scheduler's counter for the job"}):
            _unattributable[_n] = len(_pts)
            del _by_plugin[_n]
    for _n, _pts in sorted(_by_plugin.items()):
        _b, _r = fit_memory_model(_pts)
        # BOTH None means no usable measurement. A None BASELINE alone means the split was
        # indeterminate and the whole peak went to the rate - which is a result, and the one
        # belonging to the plugins that produced a single instance. This skipped on the baseline
        # alone and so dropped exactly those from the report: least data, most in need of it.
        if _b is None and _r is None:
            continue
        memory_model[_n] = {"base_gb": _b, "gb_per_100k": _r, "points": len(_pts),
                            # WHICH MEASUREMENT THIS WAS FITTED ON. The floor undercounts
                            # concurrent workers by a factor nothing inside the process can
                            # bound, so a model fitted only on floors is a model to add
                            # headroom to, and the report has to say which it is.
                            "basis": sorted(_basis.get(_n, ())),
                            "declared_per_100k": ks[_n].executor.get("memory_gb_per_100k")
                            if _n in ks else None,
                            "declared_base_gb": ks[_n].executor.get("memory_gb_base")
                            if _n in ks else None}
    for _n, _cnt in sorted(_unattributable.items()):
        print(f"\n  memory for {_n} was NOT fitted: all {_cnt} instances reported the same "
              f"figure at differing sizes, which is the scheduler's counter for the WHOLE JOB "
              f"rather than each instance's own cost. A model fitted on it would be a "
              f"horizontal line through one number. Run one instance in a job to measure this "
              f"plugin's own demand.")
    if memory_model:
        _floor_only = all(_m.get("basis") == ["the process's own floor"]
                          for _m in memory_model.values())
        print("\n  measured memory, fitted as baseline + per-cell (declare these):"
              + ("\n  FITTED ON THE PROCESS'S OWN FLOOR, which excludes concurrent children: "
                 "declare above it, not at it." if _floor_only else ""))
        for _n, _m in sorted(memory_model.items()):
            if _m["base_gb"] is None:
                # one point, or all at one size: the split is unknown and the whole peak is
                # charged to the rate, which is the direction that over-charges rather than
                # under-requests. Said, so nobody reads it as a measured baseline of zero.
                print(f"    {_n:<12} {_m['gb_per_100k']:>6.1f} GB/100k, no baseline separated "
                      f"({_m['points']} instance(s) at one size)")
            else:
                _rate = (f"{_m['gb_per_100k']:.1f} GB/100k" if _m["gb_per_100k"] is not None
                         else "per-cell term indeterminate")
                print(f"    {_n:<12} {_m['base_gb']:>6.1f} GB fixed + {_rate}")

    # ACROSS THE DESIGN, FOR EVERY PLUGIN THAT WROTE A PER-CELL COLUMN. Computed by the host
    # because the host is the only party holding the design, the object and every plugin's
    # output at once - and because a per-arm view every plugin implements for itself is a
    # convention, which is the form of this defect that has already cost three fixes.
    # Description only: quantiles and compositions, no test. See inputs.by_arm.
    _by_arm = {}
    if _run_facts.get("has_design") and sample_key:
        try:
            _dt, _dk, _df = inputs.read_design(a.design, samples or [])
            for _n, _slots in sorted(merged_slots.items()):
                _cols = list((_slots or {}).get("obs") or [])
                # AND ITS ARRAYS. A plugin whose per-cell output is a matrix has no obs column,
                # and skipping it here is what kept the design off the pages of the two plugins
                # that deliver activity per cell. `obsm_columns` is written by the merge from
                # the names `ctx.emit_obsm` puts beside the array.
                _obsm = {k: v for k, v in ((_slots or {}).get("obsm_columns") or {}).items()}
                if not _cols and not _obsm:
                    continue
                _got = inputs.by_arm(A, _cols, _dt, sample_key, _df, obsm=_obsm)
                if _got:
                    _by_arm[_n] = _got
        except Exception as e:                                            # noqa: BLE001
            print(f"  per-arm summaries not computed: {type(e).__name__}: {e}")
    if _by_arm:
        print(f"  across the design: {', '.join(sorted(_by_arm))}")

    # ONE PLUGIN'S NUMBER AGAINST ANOTHER'S. A diagnostic is useless on the page of the plugin
    # that computed it: one plugin exists partly to check that a trajectory is not a cell-cycle
    # axis, and the trajectory is on a different page. Only the host holds both columns.
    _conc = {}
    try:
        _conc = inputs.concordance(A, {n: list((sl or {}).get("obs") or [])
                                       for n, sl in merged_slots.items()})
    except Exception as e:                                                # noqa: BLE001
        print(f"  cross-plugin concordance not computed: {type(e).__name__}: {e}")
    if _conc:
        _pairs = {(r["a"]["column"], r["b"]["column"]) for v in _conc.values() for r in v}
        print(f"  cross-plugin concordance: {len(_pairs)} pair(s) over "
              f"{len(_conc)} plugin(s)")

    # WHICH PLUGINS THE CONSTRAINT BINDS, AND ON WHICH FACTORS - decided by the host, the only
    # party holding the constraint, every plugin's contrast and every plugin's per-arm section
    # at once, and written here so the reporter never re-derives it against a different design.
    # Measured on the run that motivated it: the constraint reached the README and the index and
    # NONE of the nine plugin pages, including the one whose headline it forbids outright.
    #
    # A PAGE IS BOUND BY THE FACTORS IT ACTUALLY SHOWS, which is a union of two things and was
    # briefly only one. Widening the SET of bound plugins to include everything with a per-arm
    # section, while still computing the factors as an intersection with the plugin's CONTRAST
    # TERMS, gave every one of them an empty list: a plugin that does not test the design has no
    # terms to intersect. Four pages went on showing results across age and diet with no
    # constraint on them, and the binding looked as though it had been considered.
    _forbidden = set(inputs.constraint_binds(constraint,
                                             sorted((_run_facts.get("factors") or {}))))
    _binds = {}
    for _n in sorted(ks):
        # THE ALIASES COUNT AS SHOWN. A collapsed factor is not an absent one: if a page draws
        # `age` and the design aliases `age` with a reagent version, the page is drawing that
        # reagent split too, and a constraint naming the reagent must bind it. Collapsing the
        # panel and then not binding what the panel shows would have been a quieter version of
        # the bug the collapse was added to fix.
        _shown = set()
        for _cols in (_by_arm.get(_n) or {}).values():
            for _f, _d in _cols.items():
                _shown.add(_f)
                _shown.update(_d.get("aliased_with") or [])
        _terms = set((_PL.decisions_for(ks[_n], _run_facts).get("contrast") or {})
                     .get("terms") or [])
        _hit = sorted(_forbidden & (_shown | _terms))
        if _hit:
            _binds[_n] = _hit
    if _binds:
        print(f"  the constraint binds: "
              + "; ".join(f"{n} on {', '.join(v)}" for n, v in sorted(_binds.items())))

    payload = {"version": _v(), "input": str(a.h5ad), "describe": describe,
               "by_arm": _by_arm, "concordance": _conc,
               # WHICH ARM EACH SAMPLE IS IN. The reporter had the per-unit numbers and the arm
               # NAMES and no way to join them, so a per-unit plugin's units could be put on one
               # axis and not grouped by the design - which is the only comparison the study
               # exists to make. It is the design table, carried verbatim.
               "design": {str(k): {str(f): str(v) for f, v in (r or {}).items()}
                          for k, r in (_dtab or {}).items()},
               "memory_model": memory_model,
               "constraint_on_use": constraint, "constraint_source": csrc,
               "constraint_binds": _binds,
               "ran": ran, "skipped": skipped,
               "status": {n: ks[n].status for n in sorted(ks)},
               "schedule": [[{kk: vv for kk, vv in i.items()} for i in w] for w in waves],
               "seconds": timings, "cores": budget, "units": units,
               # {unit: "group"|"sample"} - see the note where it is built.
               "unit_axis": unit_axis, "unit_members": unit_members,
               "label_key": label_key, "label_total": label_total,
               "label_by_unit": label_by_unit, "sentinels": list(sentinels or ()),
               "timeout": a.timeout,
               "kernels": folded,
               "merged": merged_slots,
               "partial": sorted({s["kernel"] for s in skipped} & set(ran)),
               # WHAT THIS RUN LEARNED ABOUT THE TOOLING, kept apart from what it learned about
               # the data. A defect in a plugin is not a property of somebody's cells.
               "diagnoses": [d.as_dict() for d in diagnoses],
               "repaired": sorted(repaired),
               "cannot_show": {n: ks[n].cannot_show for n in sorted(ks)},
               # WHAT EACH PLUGIN SAID ITS REPORT SHOULD CONTAIN, carried into the payload rather
               # than read from the plugin at render time. `scprofile report` rebuilds the
               # documents from this file alone, months later and possibly on another machine:
               # a reporter that went back to the declaration would render a page describing
               # whatever the plugin says TODAY over numbers from the run that happened then.
               # WHAT WAS NOT RECOMPUTED, AND WHERE IT CAME FROM. A run that adopted fourteen
               # instances and one that computed them leave the same directory; only this
               # distinguishes them, and a reader of the report is entitled to know which they
               # are looking at.
               "reused": reused,
               "report_spec": {n: ks[n].report_spec for n in sorted(ks)},
               # THE CLAIM, carried beside the output that would make it true, so the page can
               # say "declares it reports per arm and produced nothing to split" rather than
               # rendering an empty section that reads like a plugin nobody asked.
               "design_aware": {n: bool(ks[n].design_aware) for n in sorted(ks)},
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
    # THE RUN SAYS WHAT IT THINKS OF ITS OWN OUTPUT, for whatever run comes next. Provenance
    # alone cannot tell a good result from a bad one - a unit that completed and produced
    # nonsense has the same inputs and the same code as one that did not - so reuse keyed on
    # provenance alone launders every error forward with a trail that makes it look verified.
    from . import runcard as _RC
    _card = _RC.write(out, payload)
    print(f"      {out / _RC.CARD}  (this run's own verdict: {_card['verdict']})")
    print(f"      {out}/report.json")
    # THE README IS WRITTEN LAST, and it has to be. It describes the directory BY INSPECTING IT,
    # which is the whole reason it can be trusted - and it was called two lines above
    # `report.write_all`, the only thing that creates `report/`. So every run shipped a README
    # whose layout section omitted the run's primary deliverable while section 3 of the same file
    # linked the reader into it, with a file count short by 1 + 1 + n_kernels. Inspecting too
    # early is the same failure as describing what was intended; it just fails the other way.
    idx = report.write_all(out, payload, prefix=getattr(a, 'prefix', None))
    print(f"      {idx}")
    _judge(out)
    _write_readme(out, payload)
    return 0


def _judge(out):
    """Measure the report that was just written, and SAY SO. Never refuse it.

    A MODULE SOMEBODY HAS TO THINK TO CALL IS THE SAME AS NOT HAVING ONE, and the report that
    fails the standard is exactly the report nobody thinks to check. Both harnesses invoked
    `scprofile standard` and the tool itself did not, so a run delivered a report and said
    nothing about whether it was readable - which is the one question a reader cannot answer
    for themselves without opening every page.

    IT NEVER REFUSES AND NEVER REWRITES. A report that fails the standard is still the record
    of what the run did, and withholding it would destroy the evidence to protect the reader
    from it. The verdict is printed beside the path, at the moment the path is printed.
    """
    from . import standard as ST
    d = Path(out) / "report"
    if not d.is_dir():
        return
    try:
        _judge_inner(ST, d, out)
    except Exception as e:                                                # noqa: BLE001
        # THIS RUNS AFTER EVERY PLUGIN HAS FINISHED, and a measurement that kills the run it is
        # measuring destroys hours of completed work to report on its readability. The same
        # shape as the unbound name that killed a design-less run at the last step, and the
        # same remedy: the verdict is worth having and is worth nothing at that price.
        print(f"      the exit standard could not be applied: {type(e).__name__}: {e}")


def _judge_inner(ST, d, out):
    if not ST.summarise_selfcheck(ST.selfcheck()):
        print("      the exit standard could not be applied: the ruler above is broken")
        return
    res = ST.check_report(d)
    if not res:
        return
    bad = [(page, cid, det) for page, cs in sorted(res.items()) for cid, ok, det in cs if not ok]
    if not bad:
        print(f"      exit standard MET on {len(res)} page(s)")
        return
    print(f"      exit standard NOT met: {len(bad)} criteri{'on' if len(bad) == 1 else 'a'} "
          f"across {len({p for p, _c, _d in bad})} of {len(res)} page(s). "
          f"The report is written and is still the record of this run.")
    for page, cid, det in bad[:8]:
        print(f"        {page:<14} {cid:<14} {det}")
    if len(bad) > 8:
        print(f"        ... and {len(bad) - 8} more; `scprofile standard --out {out}` for all")


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
        # THE UPSTREAM'S OWN PLOTS, ACCOUNTED FOR. A plugin that wraps a tool inherits its
        # figures; `scprofile.native` holds the closed vocabulary of reasons one may go unused,
        # and rejects "reimplemented", "not considered" and "dependency missing" by name. This
        # prints the accounting and counts anything unaccounted as an error, because an
        # unexplained gap between what a tool draws and what a wrapper uses is exactly the
        # difference between wrapping a method and re-inventing a worse one.
        _np = (k.spec or {}).get("native_plots") or {}
        if _np:
            from . import native as _NAT
            _u, _sk, _pr = _NAT.account(sorted(_np), _np)
            print(f"  upstream plots: {len(_u)} used, {len(_sk)} validly skipped, "
                  f"{len(_pr)} unaccounted")
            for _fn, _why in _pr[:6]:
                print(f"    {_fn}: {_why[:150]}")
            if len(_pr) > 6:
                print(f"    ... and {len(_pr) - 6} more")
            errs += len(_pr)
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

    # --new WRITES A PLUGIN THAT DOES NOT EXIST YET. `scaffold` otherwise takes an ALREADY
    # DECLARED plugin and writes its build skeleton, so a maintainer starting from nothing had a
    # documented one-file template and no command that emitted it.
    if getattr(a, "new", False):
        from .onefile import render

        out_dir = Path(getattr(a, "dir", None) or "kernels")
        out_dir.mkdir(parents=True, exist_ok=True)
        for n in _split(a.name):
            f = out_dir / f"{n}.py"
            if f.exists() and not a.force:
                print(f"scprofile: {f} exists; pass --force to overwrite", file=sys.stderr)
                return REFUSE
            f.write_text(render(n), encoding="utf-8")
            print(f"wrote {f}")
        print("Next: fill in run(), then `scprofile validate <name>`.")
        return 0

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

    # RESOLVED ONCE, HERE, exactly as `run` does it - `--cores` now defaults to None in both, so
    # the plan and the run answer the same question about the same machine.
    a.cores = int(getattr(a, "cores", 0) or _default_cores())
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
    try:
        A = ad.read_h5ad(a.h5ad, backed="r")
    except Exception as exc:                      # noqa: BLE001 - re-raised unless explained
        said = compat.explain_read_failure(exc, a.h5ad)
        if said is None:
            raise
        print("scprofile: " + said, file=sys.stderr)
        return REFUSE
    print(f"  {A.n_obs:,} cells x {A.n_vars:,} genes\n")

    try:
        keys = inputs.detect_keys(
            A.obs.columns, layers=manifest.layer_names(A),
            # WIDTHS, NOT JUST NAMES. Handed a bare list of obsm keys the host could not tell a
            # 30-dimensional latent from a 2-dimensional layout, and chose the latent as the
            # thing to draw on - on an object that also carried the UMAP of that same latent.
            obsm={str(k): int(v.shape[1]) if getattr(v, "ndim", 0) == 2 else None
                  for k, v in A.obsm.items()},
            overrides={"label": a.label_key, "sample": a.sample_key, "batch": a.batch_key,
                       "counts_layer": a.counts_layer, "compartment": a.compartment_key,
                       "lognorm_layer": getattr(a, "lognorm_layer", None),
                       "embedding": getattr(a, "embedding", None),
                       "layout": getattr(a, "layout", None)})
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
    if assay[0] and str(assay[0]).lower() not in ("cell", "nucleus"):
        # THE PLAN SAYS IT TOO. This warning existed only on the run path, so the document a
        # person reads BEFORE committing a job was the one that did not mention it.
        print(f"      {assay[0]!r} is not an assay this tool reasons about (cell, nucleus), so "
              f"assay-specific caveats will NOT be applied. It is carried through as declared.")
    if not assay[0]:
        # NAME THEM. "it changes what each kernel is allowed to claim" is true, and it is also
        # skippable - a cost with nothing named on it cannot be weighed, so a reader in a hurry
        # moves past it. I moved past it, and the run that followed would have shipped a cellchat
        # report with NO single-nucleus caveat on a single-nucleus study. Naming the plugins that
        # will fall silent makes it a decision instead of a note: a report that is silent because
        # nothing was known reads exactly like one that earned its silence.
        _dep = inputs.assay_dependent([ks[n] for n in want if n in ks])
        if _dep:
            print(f"      {len(_dep)} of the {len(want)} plugin(s) here branch on it and will "
                  f"emit NO assay caveat: {', '.join(_dep)}")
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

    # THE TWO OBSM ROLES, SIDE BY SIDE AND WITH THEIR WIDTHS. A reader cannot otherwise tell that
    # the thing being computed on and the thing being drawn on are different objects - and neither
    # could the tool: it planned a plugin as runnable while handing it a 30-column latent to draw
    # arrows on, and nothing in the plan said what would be drawn on what.
    _emb = keys.get("embedding", (None,))[0]
    _lay = keys.get("layout", (None,))[0]

    def _w(k):
        m = A.obsm.get(k) if k else None
        return m.shape[1] if getattr(m, "ndim", 0) == 2 else None

    print(f"  representation              "
          + (f"obsm[{_emb!r}], {_w(_emb)} columns - neighbours and graphs are computed on this"
             if _emb else "NONE - a plugin needing a neighbour graph will say so"))
    if _lay:
        print(f"  layout to draw on           obsm[{_lay!r}], {_w(_lay)} columns - "
              f"{keys['layout'][1]}")
    else:
        # NOT AN ERROR, AND NOT SILENT. A plugin that draws refuses and names the remedy; one
        # that does not is unaffected. What must not happen is the run finding out.
        print("  layout to draw on           NONE - no two-column entry in obsm. Any plugin that "
              "draws will refuse or compute its own; the remedy is "
              "`sc.pp.neighbors(adata, use_rep=<representation>)` then `sc.tl.umap(adata)`")
    _wide = sorted(f"{k} ({v.shape[1]}c)" for k, v in A.obsm.items()
                   if getattr(v, "ndim", 0) == 2 and v.shape[1] != 2)
    if _wide and not _lay:
        print(f"      wider entries present, and NOT layouts: {', '.join(_wide[:6])}"
              + (" ..." if len(_wide) > 6 else ""))

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
        probs = unmet(k, obs=have_obs, obsm=have_obsm, layers=have_layers, available=ks,
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
            unit = (f", per {k.per_unit}" if k.per_unit else "") + (
                " + one cohort fit" if k.per_unit and k.also_cohort else "")
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
            probs = unmet(k, obs=have_obs, obsm=have_obsm, layers=have_layers, available=ks,
                          ran={n for n, _ in planned} | set(runnable),
                          has_design=bool(a.design), keys=_km,
                          organism=organism[0], var=set(A.var.columns), derived=_provided)
            mark = "ready when built" if not probs else "would refuse"
            wraps = k.spec.get("plans_to_wrap") or "-"
            unit = (f", per {k.per_unit}" if k.per_unit else "") + (
                " + one cohort fit" if k.per_unit and k.also_cohort else "")
            print(f"  {mark:<16} {name:<12} wraps {wraps}{unit}")
            for pr in probs:
                print(f"      {pr}")
            if not probs:
                todo.append(("build", name,
                             f"scprofile scaffold {name}   # manifest exists; lock, selftest, "
                             f"run.py and UPSTREAM.md do not"))

    # THE DESIGN FACTS, COMPUTED BEFORE ANYTHING JUDGES THE DESIGN. They used to be derived a
    # hundred lines below the section that reports design defects, so the defect section could
    # only ever ask about a plugin's declared properties - never about what the plugin would
    # actually test. A verdict on a study needs the study's own numbers in scope first.
    from . import planner as PL
    from . import units as _UNP

    samples = (sorted(set(A.obs[keys["sample"][0]].astype(str)))
               if keys["sample"][0] else [])
    dtab, dfactors = None, []
    if a.design:
        try:
            dtab, _dkey, dfactors = inputs.read_design(a.design, samples)
        except Exception:                                                 # noqa: BLE001
            dtab, dfactors = None, []          # already reported above, as a refusal
    # THE PLAN SCHEDULES WHAT THE RUN WILL RUN. `plan` resolved units as samples while `run`
    # resolved them from the design, so a plan promised ten instances and the run did fourteen.
    # A preview that disagrees with the action is the defect this project has already fixed
    # once, in the licence.
    _pax, _pwhy = _UNP.resolve(dtab or {}, sample_key=keys["sample"][0], samples=samples,
                               prefer=getattr(a, "unit_by", "both") or "both")
    _pmem = {}
    for _ax in _pax:
        for _u, _m in _ax["units"].items():
            _pmem.setdefault(str(_u), list(_m))
    units = sorted(_pmem) or samples

    facts = PL.design_facts(dtab, dfactors, keys["sample"][0], units)
    facts["units"] = units

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
    # WHICH FACTORS THE CONSTRAINT ACTUALLY NAMES, against what each plugin actually tests.
    # This asked `k.needs_design and k.needs_obsm` - two properties no plugin set - so it was
    # false for every plugin of every run, and the plugin whose headline the constraint forbids
    # outright was exempted along with all the others. A claim is bounded because of the FACTOR
    # it crosses, not because of the container the factor arrived in.
    bound = inputs.constraint_binds(constraint, sorted(design_levels))
    if bound:
        for name in sorted(want):
            k = ks[name]
            if not (k.needs_design or k.needs_representation):
                continue
            terms = (PL.decisions_for(k, facts).get("contrast") or {}).get("terms") or []
            hit = sorted(set(terms) & set(bound))
            if hit:
                defects.append((name, f"the upstream constraint forbids a claim across "
                                      f"{', '.join(hit)}, and this plugin's contrast tests "
                                      f"{', '.join(terms)}. Use the uncorrected representation "
                                      f"and say so, or a test that models the factor rather than "
                                      f"removing it - and either way the page must carry the "
                                      f"constraint beside the number"))
            elif k.needs_representation:
                defects.append((name, f"the upstream constraint forbids a claim across "
                                      f"{', '.join(bound)} on the corrected representation, and "
                                      f"this plugin reads one"))
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
    from .kernels import resolve_keys as _rk

    roots = sorted(set(list((prov or {}).get("search_paths") or [])
                       + provenance.ancestry_roots(a.h5ad)
                       + _split(getattr(a, "search", "") or "")))
    present = {}
    #: {plugin: "present"|"missing"|"unknown"} - filled while the prerequisites are checked and
    #: read when readiness is computed, so a fetchable reference reports as work to do rather
    #: than as a property of the data.
    _refs_state = {}
    #: {plugin: [reference names]} fetched over the network AT RUN TIME
    _runtime_refs = {}

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
        # THE GATE IS "DOES IT DECLARE ANY REFERENCE", not "does it declare an organism-specific
        # one". `reference_organisms()` is empty for a plugin whose references carry no organism -
        # a prior fetched per-organism at run time, say - so gating on it skipped the check
        # entirely and the plan reported nothing about references the plugin had just declared.
        # Measured on PBS 682089: decoupler's two runtime priors were invisible.
        if k.references():
            org = organism[0]
            if k.reference_organisms() and org \
                    and str(org).lower() not in k.reference_organisms():
                need["reference data"] = False        # a species it cannot serve: BLOCKED
            elif not a.references:
                need["reference data"] = None         # NOT DETERMINED - nowhere was checked
                _refs_state[k.name] = "unknown"
            else:
                try:
                    st = refs.status(k, a.references, org)
                    # BUNDLED AND RUNTIME COUNT AS SATISFIED. Nothing here can download them, so
                    # treating them as missing would report a gap no command closes and send
                    # `--build` after a file that does not exist.
                    ok = bool(st) and all(v[0] in ("present", "bundled", "runtime")
                                          for v in st.values())
                    # DECLARED FOR THIS ORGANISM BUT NOT ON DISK IS NOT A BLOCKED VERDICT. The
                    # plugin can serve this species; the files have simply not been downloaded
                    # here, which is readiness and is repaired by `--build`. Reporting it as
                    # BLOCKED told a new user their data could not support the method.
                    need["reference data"] = True if not ok else ok
                    _refs_state[k.name] = "present" if ok else "missing"
                    # A RUNTIME FETCH IS A DEPENDENCY ON THE NETWORK AT RUN TIME, and a batch
                    # node routinely has no outbound route. Said in the plan, it costs nothing;
                    # discovered in the run, it costs the queue slot.
                    net = sorted(n for n, v in st.items() if v[0] == "runtime")
                    if net:
                        _runtime_refs[k.name] = net
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
            v.readiness = PL.build_state(
                k, _build_state(k), prefix=a.prefix,
                refs=_refs_state.get(k.name), refdir=a.references,
                organism=organism[0])
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
    if _runtime_refs:
        print("\n  NEEDS THE NETWORK WHEN IT RUNS - not now, and not on this machine unless this")
        print("  is where the job runs. A compute node with no outbound route fails at run time:")
        for _n, _r in sorted(_runtime_refs.items()):
            print(f"    {_n:<12} fetches {', '.join(_r)} on first use")

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
                if d["kind"] == "refs_missing":
                    # THE DIRECTORY THE USER ALREADY NAMED. `--build` downloads only into the
                    # `--references` directory they passed, never a location this tool picks:
                    # reference sets run to hundreds of megabytes and where they land is the
                    # user's decision, not a default worth guessing.
                    if not a.references:
                        raise RuntimeError(
                            "no --references directory given, so there is nowhere to download "
                            "to. Pass --references <dir>.")
                    refs.fetch(ks[name], a.references, organism[0], log=print)
                else:
                    runner.install(ks[name], a.prefix,
                                   force=(d["kind"] == "env_stale"), log=print)
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
        print(f"\nwrote {plan_report.write(outp, payload, kernels=ks)}")
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


def _check(a):
    """One line per element: GREEN if it is wired and working, RED if it is not.

    A check exists to give an answer, not a report to interpret. Every line is a claim that is
    either true of this installation or is not, and the exit code is red if any is red.
    """
    import ast as _ast
    from . import panels as _P

    root = Path(__file__).resolve().parent
    rows = []

    def row(name, ok, detail=""):
        rows.append((name, bool(ok), detail))

    # --- every module reachable, counting the subprocess launch -------------------------------
    mods = {f.stem: f for f in root.glob("*.py") if not f.stem.startswith("__")}
    g = {}
    for m, f in mods.items():
        deps = set()
        for n in _ast.walk(_ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, _ast.ImportFrom) and n.module:
                b = n.module.split(".")[-1]
                if b in mods:
                    deps.add(b)
            if isinstance(n, _ast.ImportFrom) and n.level and not n.module:
                deps |= {x.name for x in n.names if x.name in mods}
            if isinstance(n, _ast.Import):
                deps |= {x.name.split(".")[-1] for x in n.names
                         if x.name.split(".")[-1] in mods}
        g[m] = deps
    g["kernels"] = g.get("kernels", set()) | {"_entry"}
    seen, stack = {"cli"}, ["cli"]
    while stack:
        for nxt in g.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    unreached = sorted(set(mods) - seen - {"panels"})
    row("every module reachable from the CLI", not unreached, ", ".join(unreached))

    src = (root / "cli.py").read_text(encoding="utf-8")
    ent = (root / "_entry.py").read_text(encoding="utf-8")
    rep = (root / "report.py").read_text(encoding="utf-8")
    man = (root / "manifest.py").read_text(encoding="utf-8")

    row("group-level inference: the unit axis is resolved from the design",
        "_UN.resolve(" in src, "run still resolves units as samples")
    row("group-level inference: a unit carries its members",
        '"unit_members"' in man and "unit_members=" in src, "in.json has no unit_members")
    row("the landscape and the adopter cannot disagree",
        'granter="adopted-on-demand"' in src,
        "match can approve on the card while adopt requires a licence")
    row("a reused instance records WHERE IT LIVES, so its figures are found",
        'pl_["dir"] = str(d.relative_to(out))' in src,
        "fold_payloads falls back to the plugin dir and the per-unit table is not found")
    row("a run records what it reused", '"reused": reused,' in src)
    row("run can ADOPT a licensed earlier result instead of recomputing",
        '"--reuse-from"' in src and "_LCN.adopt(" in src,
        "landscape reports reuse but run recomputes everything")
    row("plan and run resolve the SAME unit axis",
        src.count("_UN.resolve(") + src.count("_UNP.resolve(") >= 2,
        "plan schedules a different set of instances than run creates")
    # THE PATTERN IS ASSEMBLED, NOT WRITTEN. A check that greps its own file for a literal
    # finds the literal in its own line and reports a defect that is only its own text. Built
    # from parts, it appears nowhere in the source it scans.
    _bad_call = "read_design(a." + "design, units"
    row("the design table is read against SAMPLES, not units",
        _bad_call not in src,
        "a group unit label is not a sample and will look like a missing row")
    row("group-level inference: a plugin subsets by membership",
        "col.isin(want)" in ent, "_entry subsets by equality on the sample key")
    row("group-level comparison: between-arm panels are drawn",
        "_arm_content" in rep and "draw_arm_networks" in rep)
    row("figures: the reporter reads unit_network", "unit_network" in rep)
    row("run publishes its own verdict", "_RC.write(out, payload)" in src)
    row("resume is honoured by run", "_resume.state(" in src)
    row("the exit standard is run by the writer of the report", "standard" in rep)
    for c in ("status", "landscape", "licence", "review", "paper", "check", "scaffold"):
        row(f"command `{c}` is registered", f'add_parser("{c}"' in src)
    row("panel registry agrees with what is drawn",
        set(_P.IMPLEMENTED) <= set(_P.BY_ID)
        and set(_P.IMPLEMENTED) | set(_P.gaps()) | set(_P.plugin_kinds()) == set(_P.BY_ID),
        "registry and IMPLEMENTED disagree")
    # THE DEBT, AS ITS OWN LINE. A kind the host OWNS and does not draw is a panel every plugin
    # declaring a network should be getting and is not; a kind the plugin owns is a decision.
    # Counting them together published five-of-thirteen as though eight were unfinished.
    row(f"the host draws every panel kind it owns ({len(_P.host_kinds())})",
        not _P.gaps(), f"owed and not drawn: {', '.join(_P.gaps())}")

    # --- the plugins this installation actually ships -----------------------------------------
    # NOT A SOURCE GREP AND NOT A FIXTURE. Every row above asks whether the host's code is
    # present; this one asks whether the plugins on the kernel path pass the host's own
    # validator. Nothing did - not `check`, not `check --deep`, not a suite - and twelve errors
    # across three of the nine shipped plugins stood green for as long as they existed.
    from . import validate as _V
    from .kernels import discover as _disc
    try:
        _ks = _disc()
    except Exception as e:                                                  # pragma: no cover
        _ks, _why = {}, str(e)
        row("every shipped plugin validates", False, f"discovery failed: {_why}")
    else:
        _bad = {}
        for _n, _k in sorted(_ks.items()):
            _e = [x.check for x in _V.validate_plugin(_k) + _V.validate_references(_k)
                  if x.level == "ERROR"]
            if _e:
                _bad[_n] = _e
        row(f"every shipped plugin validates ({len(_ks)} found)", not _bad,
            "; ".join(f"{n}: {len(v)} error(s) — {v[0]}" for n, v in _bad.items()))

    # --- what a run directory actually produced, if one was named -----------------------------
    if a.out:
        from . import resume as _RS, review as _RV, runcard as _RC2
        out = Path(a.out)
        # `resume.survey`, NOT `resume.status`, WHICH DOES NOT EXIST. This whole branch raised
        # AttributeError on every invocation of `check --out` and nothing noticed, because the
        # branch is optional and no suite ever passed the flag. A check that cannot run is worse
        # than a missing one: `check` was reported green all this time by never reaching here.
        rows_ = _RS.survey(out, _RS.discover(out))
        row("run: every instance finished",
            bool(rows_) and all(st in _RS.FINISHED for _p, _u, st, _w, _n in rows_),
            f"{len(_RS.outstanding(rows_))} outstanding"
            if rows_ else "no instances in this directory")
        row("run: a card was published", _RC2.read(out) is not None, "no RUN_CARD.json")
        todo = _RV.outstanding(out)
        row("run: every figure has been looked at", not todo,
            f"{len(todo)} not looked at")
        from . import paper as _PA
        _pc = _PA.status(out)
        _pt = _PA.outstanding(out)
        row("run: the figure set has been tested by writing the result from it",
            bool(_pc) and not _pt,
            "no claims recorded — nobody has written down what these figures are supposed to "
            "show, so nothing has been able to fail" if not _pc
            else f"{len(_pt)} claim(s) undefended or stale")
        # A HOST BLOCK THAT PRODUCES NOTHING LOOKS EXACTLY LIKE ONE THAT WAS NOT NEEDED. The
        # population census reached the payload as an empty dict for a whole run - `keys[role]`
        # is (name, why) and was read whole - so the panel depending on it was never drawn, on a
        # run that passed every other check. An empty census with a label key present is a
        # defect; an empty one with no label key is a fact about the object.
        import json as _json
        try:
            _pay = _json.loads((out / "report.json").read_text(encoding="utf-8"))
        except Exception:                                                 # noqa: BLE001
            _pay = {}
        _lk = _pay.get("label_key")
        row("run: the population census was recorded",
            not _lk or bool(_pay.get("label_by_unit")),
            f"label key {_lk!r} but label_by_unit is empty — the presence panel cannot draw")

    # BEHAVIOURAL CHECKS, not source greps. Everything above proves code is PRESENT; these
    # build a real run directory and put the same question to the tool that a run puts.
    if getattr(a, "deep", False):
        from . import selfcheck as _SC

        for title, _exp, _got, ok_, detail in _SC.reuse_ablation():
            row(f"reuse: {title}", ok_, detail)
        ok_hl, why_hl = _SC.adoption_is_a_hardlink()
        row("adoption shares the inode rather than copying", ok_hl, why_hl)

    width = max(len(n) for n, _o, _d in rows)
    red = 0
    for name, ok, detail in rows:
        mark = "GREEN" if ok else "RED  "
        red += 0 if ok else 1
        print(f"  {mark}  {name:<{width}}" + (f"   {detail}" if detail and not ok else ""))
    print(f"\n  {len(rows) - red} green, {red} red")
    return 0 if red == 0 else REFUSE

def _licence(a):
    """Evaluate what a run produced and, with --grant, licence it for adoption by a later run."""
    from . import licence as LC, resume
    from .kernels import discover

    out = Path(a.out)
    if not out.is_dir():
        print(f"scprofile: no such run directory: {out}", file=sys.stderr)
        return REFUSE
    ks = discover()
    want = _split(a.kernel or "") or None
    found = [(p, u) for p, u in resume.discover(out) if not want or p in want]
    if not found:
        print(f"{out}\n  nothing here to licence.")
        return 0
    print(f"{out}")
    tally = {}
    for plugin, unit in found:
        k = ks.get(plugin)
        declared = list((k.spec or {}).get("produces") or []) if k else []
        _figs = ((k.spec or {}).get("report") or {}).get("figures") or [] if k else []
        required = [f.get("id") for f in _figs if isinstance(f, dict) and f.get("required")]
        cur_ver = (k.spec or {}).get("version") if k else None
        # ONE DECISION FUNCTION FOR BOTH PATHS. `--grant` differs from the dry run only in
        # whether the result is written down; a preview computed by a shortened check is a
        # preview that can disagree with the action, and this one did.
        fn = LC.grant if a.grant else LC.decide
        lic = fn(out, plugin, unit, declared=declared, required_figures=required,
                 declared_version=cur_ver, retrospective=a.retrospective,
                 granter=a.granter)
        g = lic["grade"]
        tally[g] = tally.get(g, 0) + 1
        lbl = f"{plugin}[{unit}]" if unit else plugin
        print(f"  {g:<14s} {lbl}")
        for r in (lic.get("refused_because") or [])[:3]:
            print(f"                 {r}")
        for r in (lic.get("not_evidenced") or [])[:3]:
            print(f"                 not evidenced: {r}")
    print("\n  " + ", ".join(f"{n} {g}" for g, n in sorted(tally.items())))
    if not a.grant:
        print("  (nothing written - pass --grant)")
    if tally.get(LC.REFUSED) and not a.retrospective:
        print("\n  A run made before the run card exists has NO self-report, and that cannot be\n"
              "  reconstructed by reading its output afterwards. `--retrospective` grants a\n"
              "  licence that says so explicitly, rather than one that implies evidence nobody\n"
              "  has. It is a deliberate act and it is recorded as one.")
    return 0

def _landscape(a):
    """The checklist: for every instance a new run would need, is it already computed?

    Answers three questions a person actually has - what exists, what changed, and what has
    never been run - and names the run each reusable result came from.
    """
    from . import landscape as LS
    from .kernels import discover

    root = Path(a.root)
    if not root.is_dir():
        print(f"scprofile: no such directory: {root}", file=sys.stderr)
        return REFUSE
    plugins = _split(a.kernel or "") or None
    have = LS.scan(root, plugins=plugins)
    if a.json:
        print(json.dumps(have, indent=1, default=str))
        return 0
    if not have:
        print(f"{root}\n  no earlier run holds anything here.")
        return 0

    runs = sorted({h["run"] for h in have}, reverse=True)
    print(f"{root}")
    print(f"  {len(have)} instance(s) across {len(runs)} run(s), newest first")
    print()
    for r in runs:
        rows = [h for h in have if h["run"] == r]
        vers = sorted({str(h.get("version")) for h in rows})
        figs = sum(len(h["figures"]) for h in rows)
        done = sum(1 for h in rows if h["state"] == "done")
        print(f"  {r}")
        print(f"      {len(rows)} instance(s), {done} done, {figs} figure(s), "
              f"plugin version(s) {', '.join(vers)}")

    # WHAT A NEW RUN WOULD ACTUALLY HAVE TO DO. Without --h5ad this is an inventory; with it,
    # it is a plan, because the input is half of what decides whether anything can be reused.
    if not a.h5ad:
        print("\n  Pass --h5ad to turn this inventory into a plan: reuse is decided by the "
              "INPUT as much as by the code, and without it nothing here can be called "
              "reusable.")
        return 0
    ks = discover()
    want_names = plugins or sorted({h["plugin"] for h in have})
    units = sorted({h.get("unit") for h in have if h.get("unit")})
    print(f"\n  against {a.h5ad}")
    n_reuse = n_change = n_absent = 0
    for name in want_names:
        k = ks.get(name)
        ver = (k.spec or {}).get("version") if k else None
        for u in (units or [None]):
            src = next((h for h in have
                        if h["plugin"] == name and h.get("unit") == u), None)
            w = LS.wanted(name, u, version=ver, h5ad=a.h5ad,
                          params=(src or {}).get("params"), keys=(src or {}).get("keys"))
            st, got, why = LS.match(w, have)
            lbl = f"{name}[{u}]" if u else name
            if st == LS.REUSABLE:
                n_reuse += 1
                print(f"    REUSE   {lbl:<28s} from {got['run']}  "
                      f"({got['artifacts']} artifact(s), {len(got['figures'])} figure(s))")
            elif st == LS.CHANGED:
                n_change += 1
                print(f"    RUN     {lbl:<28s} newest copy in {got['run']} cannot be used")
                for d in why[:3]:
                    print(f"                {d}")
            else:
                n_absent += 1
                print(f"    RUN     {lbl:<28s} never run here")
    print(f"\n  {n_reuse} reusable, {n_change + n_absent} to compute")
    if have:
        chk, unchk = LS.verified_fields(have[0])
        print(f"\n  VERIFIED against the filesystem just now: {', '.join(chk) or 'nothing'}.")
        print(f"  Taken on trust from what the run wrote: {', '.join(unchk)}.")
        print("  A run records the input's PATH and no digest of its contents, so an object "
              "rebuilt at the same path with the same size and mtime would not be detected. "
              "Reuse on that basis, or re-run.")
    return 0

def _paper(a):
    """The paper test: write the result from the figures, then defend it.

    THE STEP AFTER LOOKING AND BEFORE PROMOTING. `standard` asks whether the page is readable;
    `review` asks whether anybody opened the images; neither asks the question a reader will,
    which is whether the figure set supports the thing you want to SAY. A claim is bound to the
    figures it was read off, so redrawing one of them makes the claim stale and it has to be
    defended again.
    """
    from . import paper as PA

    out = Path(a.out)
    if not out.is_dir():
        print(f"scprofile: no such run directory: {out}", file=sys.stderr)
        return REFUSE

    if a.claim:
        try:
            rec = PA.claim(out, a.claim, _split(a.cites or ""), author=a.author, plugin=a.plugin)
        except PA.Refused as e:
            print(f"scprofile: REFUSED - {e}", file=sys.stderr)
            return REFUSE
        print(f"claim {rec['id']} recorded, citing {len(rec['cites'])} figure(s).")
        print("  Now put it to a reviewer and record what happened:")
        print(f"    scprofile paper --out {out} --round {rec['id']} "
              f"--verdict standing|narrowed|withdrawn --why '...'")
        return 0

    if a.brief:
        print(PA.brief(out, a.plugin))
        return 0

    if a.write:
        src = Path(a.write)
        if not src.is_file():
            print(f"scprofile: no such file: {src}", file=sys.stderr)
            return REFUSE
        try:
            dst = PA.write_draft(out, src.read_text(encoding="utf-8"), author=a.author,
                              plugin=a.plugin)
        except PA.Refused as e:
            print(f"scprofile: REFUSED - {e}", file=sys.stderr)
            return REFUSE
        print(f"the result section is now part of this run: {dst}")
        print(f"    scprofile paper --out {out} --render")
        return 0

    if a.render:
        path = PA.render(out, plugin=a.plugin, run_key=out.name)
        if path is None:
            print("scprofile: nothing to render - no section and no claims.", file=sys.stderr)
            return REFUSE
        print(f"wrote {path}")
        return 0

    if a.round:
        if not (a.verdict and a.why):
            print("scprofile: --round needs --verdict and --why", file=sys.stderr)
            return REFUSE
        try:
            rec = PA.review(out, a.round, a.verdict, a.why, reviewer=a.reviewer,
                            plugin=a.plugin)
        except PA.Refused as e:
            print(f"scprofile: REFUSED - {e}", file=sys.stderr)
            return REFUSE
        print(f"round recorded: {rec['id']} -> {rec['verdict']}")
        return 0

    print(f"{out}")
    print(PA.summarise(out, a.plugin))
    todo = PA.outstanding(out, a.plugin)
    if todo:
        print(f"\n  {len(todo)} claim(s) not defended:")
        for cid, st in todo:
            print(f"    {cid}  {st}")
    # ALWAYS SAY WHAT TO DO NEXT. A status nobody can act on is a report to interpret, and this
    # command drives a loop rather than describing a state.
    head, cmd = PA.next_step(out, a.plugin)
    print(f"\n  NEXT: {head}")
    if cmd:
        print(f"    {cmd.format(out=out)}")

    print("\n  WHAT THIS TEST DOES NOT COVER (docs/PAPER_TEST.md):")
    for line in PA.NARROW:
        print(f"    - {line}")
    if a.strict and todo:
        return REFUSE
    return 0


def _review(a):
    """The figure-review ledger: record a look, or report what has not been looked at.

    A GATE, NOT A REMINDER, when `--strict` is passed. Every figure defect found in this
    codebase was found by opening the image while the suite was green, so a report that a
    figure exists is not evidence about the figure.
    """
    from . import review as RV

    out = Path(a.out)
    if not out.is_dir():
        print(f"scprofile: no such run directory: {out}", file=sys.stderr)
        return REFUSE
    if a.figure or a.note:
        if not (a.figure and a.note):
            print("scprofile: --figure and --note go together", file=sys.stderr)
            return REFUSE
        try:
            rec = RV.record(out, a.figure, a.note, reviewer=a.reviewer, plugin=a.plugin)
        except RV.Refused as e:
            print(f"scprofile: REFUSED - {e}", file=sys.stderr)
            return REFUSE
        print(f"recorded: {rec['figure']}  ({rec['sha256'][:12]})")
        return 0

    rows = RV.status(out, a.plugin)
    counts = RV.summarise(out, a.plugin)
    if not rows:
        print(f"{out}\n  no figures here yet.")
        return 0
    print(f"{out}")
    print("  " + ", ".join(f"{n} {k}" for k, n in sorted(counts.items())))
    todo = [(r, st, w) for r, st, w in rows if st != RV.REVIEWED]
    if todo:
        # NAMES, NOT JUST A COUNT. A number is ignorable; a list of filenames is a task.
        print(f"\n  {len(todo)} figure(s) have not been looked at, or were redrawn since:")
        for r, st, w in todo:
            print(f"    {st:10s} {r}")
            if st == RV.STALE:
                print(f"               {w}")
        print("\n  Open each one. Then record what you saw:")
        print(f"    scprofile review --out {out} --figure <path> --note \"...\"")
    else:
        print("\n  every figure has been looked at, and none has been redrawn since.")
    if a.strict and todo:
        return REFUSE
    return 0

def _status(a):
    """What is already on disk, and what a `--resume` would still run.

    POINTED AT A DIRECTORY ALONE, never needing the plan that made it. The case where this
    matters most is the one where the plan cannot be rebuilt - the object moved, the tool
    changed underneath, a job was killed halfway - and the question is precisely what survived.
    """
    from . import resume

    out = Path(a.out)
    if not out.is_dir():
        print(f"scprofile: no such run directory: {out}", file=sys.stderr)
        return REFUSE
    # THE VERSIONS THAT WOULD RUN NOW, so a unit produced by older code is reported STALE
    # rather than counted as finished. A status that cannot see a version change is a status
    # that recommends keeping exactly the units a code change invalidated.
    try:
        from .kernels import discover as _disc
        versions = {n: (k.spec or {}).get("version") for n, k in _disc().items()}
    except Exception:
        versions = {}
    rows = resume.survey(out, resume.discover(out), versions=versions)
    if a.json:
        print(json.dumps([{"plugin": p, "unit": u, "state": st, "why": w, "artifacts": n}
                          for p, u, st, w, n in rows], indent=1))
        return 0
    if not rows:
        print(f"{out}\n  nothing has been staged here - no kernels/ directory, or it is empty.")
        return 0
    counts = resume.summarise(rows)
    print(f"{out}")
    print(f"  {len(rows)} instance(s): "
          + ", ".join(f"{n} {k}" for k, n in sorted(counts.items())))
    print()
    for p, u, st, why, n in rows:
        lbl = f"{p}[{u}]" if u else p
        mark = "  " if st in resume.FINISHED else "->"
        print(f"  {mark} {st:7s} {lbl:<28s} {why}")
    todo = resume.outstanding(rows)
    print()
    if todo:
        print(f"  {len(todo)} instance(s) would be re-run by `run --resume`: "
              + ", ".join(f"{p}[{u}]" if u else str(p) for p, u in todo))
    else:
        print("  nothing outstanding. `run --resume` would recompute nothing.")
    # SAID EVERY TIME, because it is the one classification a reader will second-guess.
    if counts.get(resume.EMPTY):
        print(f"  {counts[resume.EMPTY]} instance(s) are `empty` and are NOT outstanding: they "
              f"ran and returned nothing, which is a result. Re-running costs the same and "
              f"answers the same. Use --force-all if you mean to discard that.")
    return 0

def _standard(a):
    """Measure the RENDERED report against the exit standard. Non-zero when it is not met.

    On the report that was actually written, in the directory a run actually produced - the
    same reason `report` rebuilds from report.json rather than from the installed plugins. A
    standard measured on a fixture proves the checker runs and nothing about the report anyone
    opens, which is why this takes a directory rather than a payload.
    """
    from . import standard as ST
    # THE RULER IS MEASURED BEFORE IT MEASURES. Five of these criteria have at some point
    # reported the defect they were written for as absent, and a broken ruler's verdict is
    # not a weaker verdict - it is the wrong one, delivered with the same confidence. Each
    # criterion carries a page it must reject; this costs milliseconds and runs every time,
    # because the report nobody checks is the one that fails.
    if not ST.summarise_selfcheck(ST.selfcheck()):
        print("\nTHE STANDARD ITSELF IS BROKEN - no report was judged. Fix the criteria above; "
              "a verdict from a ruler that cannot fail is worse than no verdict.")
        return 2
    d = Path(a.out)
    d = d if d.name == "report" else d / "report"
    if not d.is_dir():
        print(f"no rendered report at {d}. Run `scprofile report --out <run dir>` first.")
        return 2
    res = ST.check_report(d)
    if not res:
        print(f"no plugin pages under {d}")
        return 2
    ok = ST.summarise(res)
    n = sum(1 for v in res.values() for _c, o, _dd in v if not o)
    print(f"\n{'EXIT STANDARD MET' if ok else f'{n} failing criteria across {len(res)} page(s)'}")
    return 0 if ok else 1


def _report(a):
    from . import report
    p = Path(a.out) / "report.json"
    if not p.exists():
        print(f"scprofile: no {p}. Run `scprofile run` first.", file=sys.stderr)
        return REFUSE
    print(f"wrote {report.write_all(Path(a.out), json.loads(p.read_text()))}")
    _judge(Path(a.out))
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
    r.add_argument("--reuse-from", type=Path,
                   help="a directory of earlier run directories. A licensed instance whose "
                        "reuse key matches is HARDLINKED into this run instead of recomputed.")
    r.add_argument("--reuse-min-grade",
                   choices=("full", "provisional", "retrospective"), default="provisional",
                   help="the weakest licence grade this run will adopt")
    r.add_argument("--unit-by", choices=("group", "sample", "both"), default="both",
                   help="which unit axis to run. `group` runs one instance per design arm over "
                        "its pooled cells; `sample` runs one per sample; `both` (default) runs "
                        "the group axis and the sample axis.")
    r.add_argument("--resume", action="store_true",
                   help="reuse instances this --out already holds and run only what is "
                        "outstanding. `status --out` says in advance what that would be.")
    r.add_argument("--force-all", action="store_true",
                   help="with --resume, redo even instances that ran and returned nothing")
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
    r.add_argument("--layout", default=None, metavar="OBSM_KEY",
                   help="obsm key to DRAW on: a two-column embedding. Detected otherwise, "
                        "preferring the layout derived from the representation (`X_umap_<name>` "
                        "beside `X_<name>`). This is not the same key as --embedding, which is "
                        "what neighbours are computed on and is usually 30-50 columns wide")
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
    # NO `choices` HERE EITHER, and for the reason written above `--organism`: argparse refusing
    # the flag stops a user DECLARING what they have, before the tool has a chance to reason
    # about it. The same defect, one flag over - `--organism` was opened up and this was left.
    #
    # `cell` and `nucleus` are what the tool REASONS about, not what is valid to say. Anything
    # else is accepted and reported as unrecognised, so a user knows the assay-specific caveats
    # will not fire rather than finding a plugin silently skipped them.
    r.add_argument("--assay", default=None, metavar="NAME",
                   help="does not change what is computed; changes what each kernel may claim. "
                        "'cell' and 'nucleus' are reasoned about; anything else is taken as "
                        "declared and reported as unrecognised")
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
    # THE SAME DEFAULT AS `run`, AND IT HAS TO BE. A hard-coded 8 made `plan` describe a machine
    # nobody was using: on PBS 679143 the plan printed `scenic[S1](8c)` and the run, given the
    # allocation, did `scenic[S1](16c)`. The plan is the document a person reads BEFORE
    # committing a job, so a plan that understates the budget understates every share in it - and
    # two documents of one run disagreeing is how the last core-allocation bug was found.
    pl.add_argument("--cores", type=int, default=None, metavar="N",
                    help="core budget divided across concurrently running plugins. Defaults to "
                         "the scheduler's allocation, never the machine's core count")
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
    pl.add_argument("--unit-by", choices=("group", "sample", "both"), default="both",
                     help="which unit axis to plan. Must match what `run` will use, or the plan "
                          "promises a different set of instances than the run creates.")
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
    sc_.add_argument("--new", action="store_true",
                     help="write a NEW one-file plugin from the template, instead of a declared "
                          "plugin's build skeleton")
    sc_.add_argument("--dir", type=Path, default=Path("kernels"),
                     help="where --new writes the file")
    sc_.set_defaults(fn=_scaffold)

    p = sub.add_parser("report", help="[you] rebuild the documents from report.json")
    p.add_argument("--out", required=True, type=Path)
    p.set_defaults(fn=_report)

    ck_ = sub.add_parser("check",
                         help="[you] one green/red line per element of scProfile")
    ck_.add_argument("--out", type=Path, help="a run directory, to check what it produced")
    ck_.add_argument("--deep", action="store_true",
                     help="also BUILD real situations and assert the tool responds correctly - "
                          "the reuse ablation and the adoption hardlink")
    ck_.set_defaults(fn=_check)

    lc = sub.add_parser("licence",
                        help="[you] evaluate a run's results and licence them for reuse")
    lc.add_argument("--out", required=True, type=Path, help="the run to licence")
    lc.add_argument("--kernel", help="plugins, comma separated. Default: all it holds")
    lc.add_argument("--grant", action="store_true", help="write licences, not just report")
    lc.add_argument("--retrospective", action="store_true",
                    help="licence a run that predates the run card. Its own verdict CANNOT be "
                         "recovered; the licence records that gap rather than hiding it.")
    lc.add_argument("--granter", default="", help="who granted it")
    lc.set_defaults(fn=_licence)

    ls_ = sub.add_parser("landscape",
                         help="[you] what EARLIER runs already hold, and what a new run must "
                              "actually compute")
    ls_.add_argument("--root", required=True, type=Path,
                     help="a directory of run directories")
    ls_.add_argument("--h5ad", type=Path, help="the input a new run would use")
    ls_.add_argument("--kernel", help="plugins to consider, comma separated")
    ls_.add_argument("--json", action="store_true", help="machine-readable")
    ls_.set_defaults(fn=_landscape)

    rv = sub.add_parser("review",
                        help="[you] which figures have been LOOKED AT, and which have not")
    rv.add_argument("--out", required=True, type=Path, help="a run directory")
    rv.add_argument("--plugin", default="",
                    help="record against THIS PLUGIN'S ledger, kernels/<plugin>/"
                         "FIGURE_REVIEW.jsonl. Figure paths stay relative to the run root")
    rv.add_argument("--figure", help="record a look at this figure (path relative to --out)")
    rv.add_argument("--note", help="what you saw. Refused if empty, too short, or copied "
                                   "from another figure's note")
    rv.add_argument("--reviewer", default="", help="who looked")
    rv.add_argument("--strict", action="store_true",
                    help="exit non-zero while any figure is unreviewed or has been redrawn "
                         "since it was reviewed. For a gate, a CI step, or a job script.")
    rv.set_defaults(fn=_review)

    pa = sub.add_parser("paper",
                        help="[you] write the result from these figures, then defend it")
    pa.add_argument("--out", required=True, type=Path, help="a run directory")
    pa.add_argument("--claim", help="one sentence you would put in a paper, read off the "
                                    "figures. Refused if it is too short to be checkable")
    pa.add_argument("--cites", help="the figures it was read off, comma-separated, relative to "
                                    "--out. A claim citing nothing is refused")
    pa.add_argument("--round", help="record a review round against this claim id")
    pa.add_argument("--verdict", choices=("standing", "narrowed", "withdrawn"),
                    help="what the round did to the claim. `withdrawn` is the one that teaches")
    pa.add_argument("--why", help="what the reviewer put to it, and what happened")
    pa.add_argument("--plugin", default="",
                    help="write THIS PLUGIN'S section, claims and page - PAPER.<plugin>.md, "
                         "PAPER_CLAIMS.<plugin>.jsonl and report/<plugin>_paper.html. A run "
                         "mounts several methods answering different questions on different "
                         "evidence, and one section covering all of them reads as a survey of "
                         "the tooling rather than as a result. Omit only for a deliberate "
                         "cohort-level synthesis")
    pa.add_argument("--author", default="", help="who wrote the claim")
    pa.add_argument("--reviewer", default="", help="who reviewed it")
    pa.add_argument("--brief", action="store_true",
                    help="what this run holds, ready to write from: the panels a reader meets "
                         "first with the caption each carries, the design, the arms, the "
                         "populations that cannot carry a comparison, and the upstream "
                         "constraint. Read this before writing anything")
    pa.add_argument("--write", metavar="FILE",
                    help="take an authored result section INTO the run as PAPER.md, so it has a "
                         "run key and travels with the figures it was read off")
    pa.add_argument("--render", action="store_true",
                    help="write report/paper.html: the section, the claims and their verdicts, "
                         "and every figure they cite, inline")
    pa.add_argument("--strict", action="store_true",
                    help="exit non-zero while any claim is undefended or has gone stale")
    pa.set_defaults(fn=_paper)

    sv = sub.add_parser("status",
                        help="[you] what does this run directory already hold, and what is left?")
    sv.add_argument("--out", required=True, type=Path, help="a run directory")
    sv.add_argument("--json", action="store_true", help="machine-readable, for a job script")
    sv.set_defaults(fn=_status)

    st_ = sub.add_parser("standard",
                         help="[you] does the rendered report meet the exit standard?")
    st_.add_argument("--out", required=True, type=Path,
                     help="a run directory, or the report/ inside one")
    st_.set_defaults(fn=_standard)

    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
