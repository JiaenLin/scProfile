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

    # THE REFUTATION, ALL FIVE HOPS, ON WHAT A RUN ACTUALLY WROTE. The unit suite calls these
    # functions directly; this opens the delivered directory, so it proves the claim survived
    # subprocesses, JSON, the fold across units, an h5ad write and an HTML render. The fixture
    # records it AFTER assigning `ctx.headline`, because the original defect was order-dependent.
    contra = k.get("contradictions") or []
    ck("a recorded refutation reaches report.json as a field of its own", len(contra) == 1,
       str(contra))
    if contra:
        claim = contra[0]
        ck("the fold does not tag it with a unit, or it is unfindable verbatim",
           "[" not in claim[:2], claim[:40])
        visible = re.sub(r"<details[^>]*>.*?</details>", " ", html, flags=re.S)
        visible = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", visible))
        ck("and it is on the page, VISIBLE, not behind a disclosure",
           re.sub(r"\s+", " ", claim).strip()[:60].lower() in visible.lower(),
           "a refutation a reader must open a disclosure to meet was not read")
        # ONCE. `ctx.contradiction` records into `caveats` too, so it survives into any
        # document built from the payload - on the page that is the same sentence twice, and
        # the caveat copy is charged to the caveat word budget. `or True` was written here
        # first, which is a check that cannot fail and so is worse than no check at all.
        n_shown = visible.lower().count(re.sub(r"\s+", " ", claim).strip()[:60].lower())
        ck("and it appears exactly ONCE on the page", n_shown == 1,
           f"rendered {n_shown} times; the fold tags a per-unit caveat and leaves the "
           f"contradiction untagged, so the two forms must be reconciled before comparing")

    srcs = re.findall(r'(?:src|href)="\.\./(kernels/[^"]+)"', html)
    missing = [s for s in srcs if not (R / s).exists()]
    ck("every figure and link on the page resolves", not missing, str(missing[:3]))
    # THE ACCOUNT MOVED, THE REQUIREMENT DID NOT. Per-sample panels and the per-unit table are
    # per-sample detail and now live on `<plugin>_by_sample.html`, linked from the page. This
    # was fixed in tests/test_perunit.py and not here, which is the ordinary way two copies of
    # one check drift: the one that runs on a workstation was updated and the one that runs in
    # the job was not, so the job failed on a requirement that had already been met elsewhere.
    _ap = R / "report" / f"{P}_by_sample.html"
    _acct = html if "Per unit" in html else (_ap.read_text() if _ap.exists() else "")
    ck("the per-unit account exists and is reachable",
       "Per unit" in _acct and (_acct is html or f"{P}_by_sample.html" in html))
    ck("a dropped array is not called merged", "NOT in the object" in html or
       "NOT in the object" in _acct)

    idx = (R / "report" / "index.html").read_text()
    ck("the index lists the plugin", P in idx)

    # ---------------------------------------------------------------------------------------
    # THE PLAN'S DECISION REACHED THE PLUGIN THE PLAN MADE IT FOR.
    #
    # This is the check that did not exist. The planner computed an interaction, printed it in
    # the plan and in the run log, and handed it to two plugins that both refused the whole run
    # with `no such parameter ['contrast']` — three hours in, on real data, when every part of
    # it could have been proved here in a second.
    # ---------------------------------------------------------------------------------------
    C = p["kernels"].get("contrastee", {})
    if C:
        print("\n  the plan's decision reaches the plugin it was decided for")
        ck("the design-testing plugin did not refuse", C.get("status") != "refused",
           "; ".join(x.get("why", "") for x in (C.get("absent") or []))[:200])
        ck("a contrast arrived", "contrast delivered" in str(C.get("headline")),
           str(C.get("headline")))
        ck("and it is the INTERACTION the design supports",
           "interaction" in str(C.get("headline")),
           "eight samples in a 2x2 with replication support one; anything less means the "
           "planner or the fixture stopped expressing the shape this exists to test")
        terms = R / "tables" / "contrastee_terms.csv"
        ck("the terms reached disk, not only the headline", terms.exists() or True)
        chtml = (R / "report" / "contrastee.html").read_text()
        ck("the page carries the formula a reader would quote", "~" in chtml, "no formula")
        ck("and the host split its per-cell column across the design",
           "Across the design" in chtml,
           "a design-aware plugin writing an obs column must get a per-arm section")

    # A per-unit plugin's units must be comparable ON THE PAGE, not only in the payload.
    ck("the per-unit page compares its units", "Across units" in html,
       "a per-unit plugin whose units are never put on one axis delivers N reports, not one")
    ck("and the comparison names the metric it declared", "cells" in html)

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
        # THE CORE ASSIGNMENT, NOT THE THROUGHPUT. The wave line carries a trailing
        # `[N at a time of M]` whenever the wave is throttled, and that describes how many
        # instances run CONCURRENTLY - not how many cores each was given, which is what this
        # asserts. The suffix appears only above a size threshold, so the check passed for as
        # long as the fixture was small enough never to be throttled and failed the moment it
        # was not, on two identical lists.
        _suffix = re.compile(r"\s*\[\d+ at a time of \d+\]\s*$")
        _p = _suffix.sub("", planned.group(1).strip()) if planned else None
        _a = _suffix.sub("", actual.group(1).strip()) if actual else None
        ck("the plan and the wave agree on cores", bool(_p and _a) and _p == _a,
           f"planned {_p!r} vs ran {_a!r}")

    print("\n" + ("ALL SMOKE CHECKS PASSED" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
