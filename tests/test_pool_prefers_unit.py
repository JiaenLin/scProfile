"""A contrast side must be read off the arm's OWN fit where one exists.

WHAT THIS COST: the host's table summed the per-SAMPLE networks while the tool's comparison
figures beside it were drawn from the arm's fit on POOLED cells. Both were labelled "total
interaction strength". Measured on one cohort they differed by a factor of 2.5 - 57.5 against
23.3 for the same arm - and a reader comparing the table against the figure on the same page
would have been comparing two different quantities.

Neither is wrong: a sum over animals weights each animal equally, a pooled fit weights each cell
equally. What is wrong is not saying which, so the table also records the source of each side.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []
try:
    import pandas as pd
except Exception:                                                         # noqa: BLE001
    print("ok: skipped, pandas is not importable here")
    raise SystemExit(0)

from scprofile.compare_panel import pool, two_scale_table, arm_pairs      # noqa: E402

D = {"s1": {"f1": "lo", "f2": "x"}, "s2": {"f1": "lo", "f2": "y"},
     "s3": {"f1": "hi", "f2": "x"}, "s4": {"f1": "hi", "f2": "y"}}


def _edges(vals):
    return pd.DataFrame({"source": ["A"] * len(vals), "target": ["B"] * len(vals),
                         "group": ["G"] * len(vals), "prob": vals})


# per-sample edges sum to 4.0 on the `lo` side; the arm's own fit says 1.0. They must not be
# interchangeable, and the arm's own fit must win.
per = {"s1": _edges([1.0, 1.0]), "s2": _edges([1.0, 1.0]),
       "s3": _edges([0.5]), "s4": _edges([0.5]),
       "lo": _edges([1.0]), "hi": _edges([0.25]),
       "lo_x": _edges([9.0])}
um = {"lo": {"s1", "s2"}, "hi": {"s3", "s4"}, "lo_x": {"s1"}}

e, src = pool(per, ["s1", "s2"], unit_members=um)
if e is None or abs(float(e["prob"].sum()) - 1.0) > 1e-9:
    FAILURES.append(f"the arm's own fit was not used: got {None if e is None else e['prob'].sum()}")
if "unit 'lo'" not in src:
    FAILURES.append(f"the source does not name the unit: {src!r}")

# with no unit covering the side, summing the members is correct AND must say so
e2, src2 = pool(per, ["s1", "s2"], unit_members={})
if e2 is None or abs(float(e2["prob"].sum()) - 4.0) > 1e-9:
    FAILURES.append("without a unit, the members were not summed")
if "summed" not in src2:
    FAILURES.append(f"a summed side does not say so: {src2!r}")

# and the table carries the provenance of both sides
rows = two_scale_table(per, D, arm_pairs(D), group_col="group")
if not rows:
    FAILURES.append("two_scale_table produced no rows")
else:
    if not all("from_source" in r and "to_source" in r for r in rows):
        FAILURES.append("the table does not record where each side came from")
    # `arm_pairs` sorts the levels, so which side is `from` is its business, not this test's.
    # What matters is that BOTH totals are the units' own fits (1.0 and 0.25) and neither is a
    # sum over members (4.0 and 1.0).
    marg = [r for r in rows if r["contrast"] == "f1"]
    if marg:
        got = {round(float(marg[0]["total_from"]), 9), round(float(marg[0]["total_to"]), 9)}
        if got != {1.0, 0.25}:
            FAILURES.append(f"the marginal contrast did not use the units' own fits: {got}")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ok: a contrast side uses the arm's own fit when one exists, sums members when none "
      "does, and the table records which")
