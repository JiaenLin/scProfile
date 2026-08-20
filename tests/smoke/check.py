#!/usr/bin/env python3
"""Assert the properties a finished run must have. Reads only the delivered directory.

WHY THIS EXISTS SEPARATELY FROM tests/test_perunit.py

Those tests drive the merge and report functions directly and prove the rules in isolation. This
one opens what a real run actually WROTE and checks that the rules survived the trip through
subprocesses, a compatibility copy, concurrent threads, an h5ad write and an HTML render. Three
defects reached HEAD past a green unit-test suite and were caught here instead:

  - `[None]` in a provenance field, which nothing raises on until write_h5ad;
  - a core budget divided twice, visible only by comparing the printed plan against the printed
    wave in the SAME log;
  - a keyword the wrapped scanpy function forbids, which only a real call rejects.

    python tests/smoke/check.py --out RUNDIR --units 4 --log RUNDIR/smoke.log
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  -- {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="the run directory `scprofile run --out` wrote")
    ap.add_argument("--plugin", default="perunit", help="the per-unit plugin to check")
    ap.add_argument("--units", type=int, default=4)
    ap.add_argument("--expect", default="", help="comma-separated plugins that must appear in `ran`")
    ap.add_argument("--log", default="", help="the run's console log, for the plan-vs-wave check")
    a = ap.parse_args()

    R = Path(a.out)
    p = json.loads((R / "report.json").read_text())
    P = a.plugin

    k = p["kernels"].get(P, {})
    units = [u["unit"] for u in (k.get("units") or [])]
    ck("every unit reaches report.json", len(units) == a.units, f"got {units}")
    ck("the plugin is marked per-unit", k.get("per_unit") is True)
    ck("every unit's figures survive", len(k.get("figures") or []) == a.units,
       str(len(k.get("figures") or [])))

    tabs = sorted((R / "tables").glob(f"{P}*"))
    ck("one table per unit on disk", len(tabs) == a.units, str([t.name for t in tabs]))
    objs = sorted((R / "objects").glob(f"{P}*"))
    ck("one side-car per unit, unit-suffixed", len(objs) == a.units, str([o.name for o in objs]))
    ck("no two delivered names collide", len({o.name for o in objs}) == len(objs))

    html = (R / "report" / f"{P}.html").read_text()
    srcs = re.findall(r'(?:src|href)="\.\./(kernels/[^"]+)"', html)
    missing = [s for s in srcs if not (R / s).exists()]
    ck("every figure and link on the page resolves", not missing, str(missing[:3]))
    ck("the page has a per-unit section", "Per unit" in html)
    ck("a dropped array is not called merged", "NOT in the object" in html)

    idx = (R / "report" / "index.html").read_text()
    ck("the index lists the plugin", P in idx)

    prov = p.get("merged", {}).get(P, {})
    ck("provenance records what merged", bool(prov.get("obs")))
    ck("provenance records what did NOT", bool(prov.get("dropped")))
    ck("a dropped key is listed once, not once per unit",
       len(prov.get("dropped") or []) == len(set(prov.get("dropped") or [])),
       str(prov.get("dropped")))

    md = (R / "README.md").read_text()
    ck("the README sees report/", "report/" in md)
    n = int(md.split("- ")[2].split(" files")[0])
    real = len([q for q in R.rglob("*") if q.is_file()])
    ck("the README file count is right", n == real, f"said {n}, is {real}")

    for name in [x.strip() for x in a.expect.split(",") if x.strip()]:
        ck(f"{name} ran", name in p["ran"], str(p["ran"]))

    sch = [i for w in p["schedule"] for i in w]
    ck("the schedule records every unit",
       sum(1 for i in sch if i["plugin"] == P) == a.units)

    if a.log:
        # THE PLAN AND THE RUN MUST AGREE when nothing was filtered out of the wave. They did not:
        # _budget was applied twice and scaled the already-scaled number, so a printed velocity(2c)
        # ran at 1c. A tool whose plan disagrees with its run is one whose plan is not evidence.
        #
        # Anchored on the plan's own position. A log may hold several runs, and an unanchored
        # search compared one run's plan against another run's wave - an assertion failing on the
        # wrong lines, which is the one way a check can be worse than no check.
        log = Path(a.log).read_text()
        n_inst = len(sch)
        planned = re.search(rf"plan: {n_inst} instance.*?\n  wave 1: ([^\n]+)", log)
        actual = re.search(r"=== wave 1 === ([^\n]+)", log[planned.end():]) if planned else None
        ck("the plan and the wave agree on cores",
           bool(planned and actual) and planned.group(1).strip() == actual.group(1).strip(),
           f"planned {planned and planned.group(1)!r} vs ran {actual and actual.group(1)!r}")

    print("\n" + ("ALL SMOKE CHECKS PASSED" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
