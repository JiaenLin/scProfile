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
