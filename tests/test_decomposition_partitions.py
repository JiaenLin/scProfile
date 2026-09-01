"""Splitting an arm's fit over its members must partition it exactly.

An arm's network is ONE fit on its members' pooled cells; each member also has a fit of its own.
Those are different fits, so drawing the arm as a bar and the members as points put two
incomparable quantities on one axis - measured, the same 23,263 cells gave 30.56 as one pooled
fit and 84.28 as three separate fits summed, so every point sat above every bar in every arm,
whatever the biology was. Dividing both by cells does not reconcile that; it is not a scale
error.

`decompose_by_member` credits the ARM's own matrix to each member by that member's share of the
arm's cells, half for sending and half for receiving. Two properties are the whole reason it is
that rule and not another, so both are checked here rather than described:

  * IT PARTITIONS EXACTLY - the members' values sum to the arm's, so nothing is created or lost.
  * THE BAR IS THEN THE CELL-WEIGHTED MEAN OF ITS POINTS, which is what lets a point fall on
    either side of it.

Checked on numbers, because a partition that is off by a little is a partition that is wrong and
looks right.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                                        # noqa: E402
from scprofile.compare_panel import decompose_by_member                    # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


EDGES = pd.DataFrame({
    "source": ["A", "A", "B", "B", "C"],
    "target": ["B", "C", "A", "C", "A"],
    "prob":   [0.4, 0.1, 0.2, 0.05, 0.25],
})
# Three members whose per-population cells sum to the arm's, as they must.
MEMB = {"m1": {"A": 50, "B": 10, "C": 40},
        "m2": {"A": 30, "B": 60, "C": 10},
        "m3": {"A": 20, "B": 30, "C": 50}}
ARM = {p: sum(m[p] for m in MEMB.values()) for p in ("A", "B", "C")}

parts = {k: decompose_by_member(EDGES, ARM, v, weight="prob") for k, v in MEMB.items()}

got_w = sum(p["weight"] for p in parts.values())
want_w = float(EDGES["prob"].sum())
check(abs(got_w - want_w) < 1e-9,
      f"the members' weights sum to {got_w!r}, not the arm's {want_w!r} - the split creates or "
      f"destroys signal")

got_c = sum(p["count"] for p in parts.values())
check(abs(got_c - float(len(EDGES))) < 1e-9,
      f"the members' counts sum to {got_c!r}, not the arm's {float(len(EDGES))!r}")

# THE PROPERTY THE PANEL DEPENDS ON. Values sum to the arm's and cells sum to the arm's cells,
# so the arm's per-cell rate is exactly the cell-weighted mean of the members' per-cell rates -
# which is what allows a point to sit below the bar.
cells = {k: sum(v.values()) for k, v in MEMB.items()}
bar = want_w / sum(cells.values())
mean = sum(parts[k]["weight"] for k in MEMB) / sum(cells[k] for k in MEMB)
check(abs(bar - mean) < 1e-12,
      f"the bar {bar!r} is not the cell-weighted mean of its points {mean!r}")

check(any(parts[k]["weight"] / cells[k] < bar for k in MEMB)
      and any(parts[k]["weight"] / cells[k] > bar for k in MEMB),
      "no member falls on either side of the bar, which is the symptom the decomposition exists "
      "to remove")

# A member contributing no cells is credited nothing, and an empty arm is not a division by zero.
check(decompose_by_member(EDGES, ARM, {}, weight="prob")["weight"] == 0.0,
      "a member with no cells was credited part of the arm's fit")
check(decompose_by_member(None, ARM, MEMB["m1"])["weight"] == 0.0,
      "an absent edge table did not decompose to nothing")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - the split is exact and the bar is the cell-weighted mean of its own points")
