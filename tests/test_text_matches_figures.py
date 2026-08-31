"""The numbers a section quotes are computed over the populations its figures are drawn over.

THE DEFECT, FOUND BY REVIEWING A REAL RUN'S ARITHMETIC. A wrapped tool that draws a differential
restricts both arms to the elements they SHARE, because an element only one arm has contributes
its whole value as a difference rather than a change. The host's two-scale table did not restrict,
so every ratio the written section quoted was computed over the UNION while every panel beside it
was drawn over the INTERSECTION.

Measured on a real cohort, one contrast read 1.31x in the text and 1.02x - no effect at all - on
the populations a reader could see, because two populations present in one arm only carried a
fifth of that arm's total. Both numbers were correct; they were answers to different questions,
and only one of them had a picture.

Nothing is hidden by the restriction: the elements it drops are exactly those reported as present
in one arm and not the other, which is a result and is stated as one.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                                       # noqa: E402
from scprofile import compare_panel as CP                                 # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


# two arms, two samples each; ONLY the treated arm has population "X", and it carries a lot
def edges(rows):
    return pd.DataFrame(rows, columns=["source", "target", "prob", "group"])


SHARED = [("A", "B", 1.0, "p1"), ("B", "A", 1.0, "p1")]
per = {
    "s1": edges(SHARED), "s2": edges(SHARED),
    "s3": edges(SHARED + [("X", "A", 50.0, "p9"), ("A", "X", 50.0, "p9")]),
    "s4": edges(SHARED + [("X", "A", 50.0, "p9"), ("A", "X", 50.0, "p9")]),
    "ctl": edges(SHARED + SHARED),
    "trt": edges(SHARED + SHARED + [("X", "A", 100.0, "p9"), ("A", "X", 100.0, "p9")]),
}
design = {"s1": {"g": "ctl"}, "s2": {"g": "ctl"}, "s3": {"g": "trt"}, "s4": {"g": "trt"}}
# the pooled units the host would find, one per side
per["ctl"] = edges(SHARED + SHARED)
pairs = [("g", "g", "ctl", "trt", {"g": "ctl"}, {"g": "trt"})]

rows = CP.two_scale_table(per, design, pairs, group_col="group", weight="prob")
check(bool(rows), "the two-scale table produced no rows for a contrast it should support")
if rows:
    tot_from = rows[0]["total_from"]
    tot_to = rows[0]["total_to"]
    els = {r["element"] for r in rows}
    check("p9" not in els,
          "an element carried only by the population that ONE arm has is in the table, so the "
          "text is computed over the union while the figures are drawn over the intersection")
    check(abs(tot_to - tot_from) < 1e-6,
          f"the totals differ ({tot_from} against {tot_to}) although the two arms are identical "
          f"on the populations they share - the arm-specific population is being counted as a "
          f"change when it is a presence")
    check("populations_compared" in rows[0],
          "the row does not say how many populations it was computed over, so a reader cannot "
          "check that the number and the panel are about the same set")
    check(rows[0].get("populations_only_one_arm") == 1,
          f"the row does not record the population present in one arm only "
          f"(got {rows[0].get('populations_only_one_arm')!r})")

# 5. THE UNIT, NOT THE LEVEL. `from`/`to` are factor LEVELS - two contrasts can both read
#    "young against aged" and mean different objects - so a consumer resolving a side by that
#    name reads the MARGINAL unit for every conditional contrast. Found in a real run: the
#    composition table listed four marginal arms while telling the reader every comparison is
#    read against it, and the per-contrast composition caveat used the wrong pair every time.
if rows:
    check("unit_from" in rows[0] and "unit_to" in rows[0],
          "the row does not record WHICH UNIT each side came from, so a consumer can only "
          "resolve a side by its level name - which is the same object for several contrasts")
    check(rows[0].get("unit_from") == "ctl" and rows[0].get("unit_to") == "trt",
          f"the recorded units are wrong: {rows[0].get('unit_from')!r} / "
          f"{rows[0].get('unit_to')!r}")

# 6. NO INVENTED DENOMINATOR, AND NO COMPARISON BETWEEN DISJOINT ARMS.
empty = {"ctl": edges(SHARED), "trt": edges([("A", "B", 0.0, "p1")]),
         "s1": edges(SHARED), "s3": edges(SHARED)}
zero_rows = CP.two_scale_table(
    {"ctl": edges(SHARED), "trt": edges([]), "s1": edges(SHARED), "s3": edges([])},
    design, pairs, group_col="group", weight="prob")
check(not zero_rows,
      "an arm with no signal at all still produced a row; the total was replaced with 1.0 and "
      "the section quoted it as a measurement")

disjoint = {"ctl": edges([("A", "B", 1.0, "p1")]), "trt": edges([("X", "Y", 8.0, "p9")]),
            "s1": edges([("A", "B", 1.0, "p1")]), "s3": edges([("X", "Y", 8.0, "p9")])}
dj = CP.two_scale_table(disjoint, design, pairs, group_col="group", weight="prob")
check(not dj,
      "two arms sharing NO population produced a ratio anyway - the restriction was skipped "
      "precisely when there was nothing to compare")

src = (ROOT / "scprofile" / "compare_panel.py").read_text()
check("_shared" in src and "isin(_shared)" in src,
      "the restriction is not applied in compare_panel, so the table and the figures can diverge "
      "again the next time one of them changes")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - the quoted numbers and the drawn panels cover the same populations")
