"""The plan a plugin declares is the same plan before and after it is migrated to carry the call.

Harness ADR-0016, step 2g. `native_plots` prose, a ceiling dict per function and two prefix maps
are being replaced by one entry per figure family in `report.figures`. The migration is a
transcription, and a transcription that changes what a run will draw has changed a figure it
was not asked to. So the plan is fingerprinted BEFORE the migration - files per axis, files per
position, the vector-copy count, and every family stem with its ceiling - and asserted equal
AFTER, with no run needed. The reproduction on the cluster is the second proof; this is the one
that costs nothing.

RECORD DELIBERATELY, NEVER AUTOMATICALLY:  python3 tests/test_the_figure_plan_is_the_same_plan.py --record
A baseline a test writes for itself cannot fail the first time it runs.

RECORDED TWICE, and the second time is written down. The first baseline was read by the prose
reader, which placed a brace family by its STEM: `native_heatmap` for `native_heatmap_{count,
weight}.png` misses the `native_heatmap_` rule by one underscore and fell to the `native_`
default, appendix, while the reporter - matching the file names themselves - placed those 36
files at contrast. The migrated plan says contrast per member, as the run did; the files, the
vector copies and the total were identical at the re-record, and the reason is in the harness's
ADR-0016 status table, step 3.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import kernels as K, planner as PL                          # noqa: E402

BASELINE = ROOT / "tests" / "baselines" / "cellchat_figure_plan.json"
#: The cohort shape the sealed reference was drawn on: 18 units, 6 arm-pair contrasts, 1 cohort.
SHAPE = {"units": 18, "contrasts": 6, "cohort": 1}


def fingerprint(spec):
    plan = PL.figure_plan(spec, **SHAPE)
    by_axis, by_pos = {}, {}
    for r in plan["rows"]:
        by_axis[r["axis"]] = by_axis.get(r["axis"], 0) + r["files"]
        by_pos[r["position"]] = by_pos.get(r["position"], 0) + r["files"]
    # A FAMILY IS COUNTED IN FILES PER OCCURRENCE OF ITS AXIS. A brace family (`native_heat`,
    # ceiling 2) and its two members after migration (`native_heat_count`, `native_heat_weight`,
    # ceiling 1 each) are the same plan; the stems are compared by prefix, the files by sum.
    fams = sorted((r["family"], r["at_most"], r["axis"], r["position"]) for r in plan["rows"])
    return {"files": plan["files"], "vector": plan["vector"], "total": plan["total"],
            "by_axis": dict(sorted(by_axis.items())), "by_position": dict(sorted(by_pos.items())),
            "families": fams}


def main(argv):
    spec = K.discover()["cellchat"].spec
    now = fingerprint(spec)
    if "--record" in argv:
        BASELINE.write_text(json.dumps(now, indent=1), encoding="utf-8")
        print(f"recorded {BASELINE.relative_to(ROOT)}: {now['files']} files, "
              f"{now['vector']} vector, {len(now['families'])} families")
        return 0
    if not BASELINE.is_file():
        print(f"FAIL\n  - no baseline at {BASELINE.relative_to(ROOT)}; record it with --record "
              f"BEFORE migrating the declaration")
        return 1
    ref = json.loads(BASELINE.read_text(encoding="utf-8"))
    bad = []
    for k in ("files", "vector", "total"):
        if ref[k] != now[k]:
            bad.append(f"{k}: baseline {ref[k]}, now {now[k]}")
    for k in ("by_axis", "by_position"):
        if ref[k] != now[k]:
            bad.append(f"{k}: baseline {ref[k]}, now {now[k]}")
    # every family that existed still exists as itself or as a member of itself, and no family
    # exists now that no baseline family covers
    old_stems = [f[0] for f in ref["families"]]
    new_stems = [f[0] for f in now["families"]]
    for st in old_stems:
        if not any(n == st or n.startswith(st + "_") for n in new_stems):
            bad.append(f"family {st!r} is gone")
    for n in new_stems:
        if not any(n == st or n.startswith(st + "_") for st in old_stems):
            bad.append(f"family {n!r} is new - the migration added a figure")
    if bad:
        print("FAIL")
        for b in bad:
            print("  -", b)
        return 1
    print(f"ok: the plan is the same plan - {now['files']} files, {now['vector']} vector copies, "
          f"{len(now['families'])} families over {len(old_stems)} baseline stems")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
