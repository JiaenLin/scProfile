"""The reference described first is the ARM at every control level, not a sample inside it.

A difference is unreadable until the thing it is a difference FROM has been described, and every
contrast in the document is measured against a POOLED ARM - one fit on all of that arm's cells.

The first version scanned the design, which is keyed by SAMPLE, and returned the first animal
whose row sat at every control level. It resolved, it found that animal's panels, and it would
have put a single replicate in the manuscript as "the control" - a profile no comparison is
actually read against. Nothing failed: the unit existed, its figures existed, and the section
would have rendered.

So the check is on WHICH unit comes back, not on whether one does. The arm name is built with
`units.group_label`, the same function that names a crossed arm everywhere else in the host, so
this cannot drift from the units a run produces.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile.compose import reference_unit                              # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


# Two factors, two levels each, two replicates per cell. Deliberately not this project's names.
DESIGN = {}
for a in ("lo", "hi"):
    for b in ("ctl", "trt"):
        for r in (1, 2):
            DESIGN[f"{a}{b}{r}"] = {"dose": a, "drug": b, "batch": "B1"}
CTL = {"dose": "lo", "drug": "ctl"}
ARMS = {"lo_ctl", "hi_ctl", "lo_trt", "hi_trt"} | set(DESIGN)

got = reference_unit(DESIGN, CTL, ARMS)
check(got == "lo_ctl",
      "the reference is %r, which is a sample, not the pooled arm every contrast is measured "
      "against" % (got,))

# THE FALLBACK IS FOR A DESIGN WITH NO POOLED ARM, and must not fire while one exists.
only_samples = set(DESIGN)
got2 = reference_unit(DESIGN, CTL, only_samples)
check(got2 in {"loctl1", "loctl2"},
      "with no crossed arm in the run the reference should fall back to a sample at the control "
      "levels, got %r" % (got2,))

check(reference_unit(DESIGN, {}, ARMS) == "",
      "with no declared control there is no reference and none should be invented")

# A factor with no declared control cannot yield a reference arm - the arm would be a guess.
check(reference_unit(DESIGN, {"dose": "lo"}, ARMS) in {"", "loctl1", "loctl2"},
      "a partial control declaration produced a crossed-arm name, which asserts a level nobody "
      "declared")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - the reference is the pooled arm, with a sample fallback only where no arm exists")
