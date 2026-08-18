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
        if k.summary:
            print(f"        {k.summary}")
    print("")
    print("A kernel that is MISSING is not a failure - it is a kernel you have not installed.")
    print("Its absence is named in the report rather than leaving a gap.")
    return 0 if worst == 0 else 0        # never fatal: doctor reports, it does not gate


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

def _run(a):
    from . import inputs, manifest, merge, refs, report, runner
    from .kernels import discover, order, unmet

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

    have_obs = set(A.obs.columns)
    have_obsm = set(A.obsm)
    have_layers = {k for k in A.layers if k is not None}
    ran, payloads, skipped = [], [], []

    for name in order(want, ks):
        k = ks[name]
        print(f"\n=== {name} ===")
        probs = unmet(k, obs=have_obs, obsm=have_obsm, layers=have_layers, ran=ran,
                      has_design=bool(a.design))
        if probs and not a.force:
            print(f"  NOT RUN - {len(probs)} prerequisite(s) unmet:")
            for p in probs:
                print(f"    {p}")
            skipped.append({"kernel": name, "why": probs})
            continue
        try:
            r = refs.resolve(k, a.references, organism[0]) if k.references(organism[0]) else {}
        except FileNotFoundError as e:
            print(f"  NOT RUN - {e}")
            skipped.append({"kernel": name, "why": [str(e)]})
            continue

        kout = out / "kernels" / name
        kout.mkdir(parents=True, exist_ok=True)
        manifest.write_input(
            kout / "in.json", h5ad=a.h5ad, out_dir=kout,
            keys={r_: v[0] for r_, v in keys.items() if v[0]},
            organism=organism[0], assay=assay[0], design=a.design, references=r,
            params=json.loads(a.params) if a.params else {})
        try:
            payload = runner.run(k, inp=kout / "in.json", out_dir=kout, prefix=a.prefix)
        except Exception as e:                                            # noqa: BLE001
            print(f"  FAILED: {e}")
            skipped.append({"kernel": name, "why": [str(e)]})
            continue
        print(f"  status {payload['status']}   {payload.get('headline', '')}")
        for c in payload.get("caveats", []):
            print(f"  caveat: {c}")
        try:
            got = merge.merge_one(A, kout, payload)
        except merge.MergeError as e:
            print(f"  MERGE REFUSED: {e}")
            skipped.append({"kernel": name, "why": [str(e)]})
            continue
        tabs = merge.copy_tables(kout, payload, out / "tables")
        for slot, v in got.items():
            if v:
                print(f"  merged {slot}: {', '.join(v)}")
        if tabs:
            print(f"  tables: {', '.join(tabs)}")
        have_obs |= set(got["obs"])
        have_obsm |= set(got["obsm"])
        have_layers |= set(got["layers"])
        ran.append(name)
        payloads.append(payload)

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
               "kernels": {p["kernel"]: p for p in payloads},
               "cannot_show": {n: ks[n].cannot_show for n in sorted(ks)},
               "summaries": {n: ks[n].summary for n in sorted(ks)},
               "object": str(op)}
    (out / "report.json").write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    print(f"      {out}/report.json")
    print(f"      {report.write_all(out, payload)}")
    return 0


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
    r.add_argument("--object-name", default="cohort_profiled.h5ad")
    r.add_argument("--force", action="store_true",
                   help="run a kernel whose prerequisites are unmet. It will probably refuse "
                        "itself, and its result would not mean what the report says it means")
    r.set_defaults(fn=_run)

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
