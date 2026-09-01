"""The cache stamp's recipe covers what makes the object, and not the whole script.

TWO WAYS TO GET THIS WRONG AND THEY ARE NOT SYMMETRIC.

Hashing nothing - which is where this started - let a fitted object survive a CellChat upgrade
and every edit to the inference beneath it, reported as a cache hit on a run that looked normal
throughout. That is a correctness failure and it is silent.

Hashing the WHOLE script fixed that and cost something else: a figure title, a legend or a colour
invalidated eighteen fitted objects and bought a two-and-a-half hour re-inference, for an edit
the object has never heard of. That is not a correctness failure, it is a workflow that stops
being used - and a cache nobody can afford to keep warm is a cache that gets turned off.

So the recipe is the span between two markers, and this checks the span exists, is ordered, and
actually contains the calls that determine the saved object. It is checked here because the
consequence of getting it wrong appears only as an object that should have been rebuilt and was
not - which looks exactly like an object that was correctly reused.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SRC = (ROOT / "kernels" / "cellchat.py").read_text(encoding="utf-8")
FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


a = SRC.find("# --- RECIPE START ---")
b = SRC.find("# --- RECIPE END ---")
check(a > 0, "no RECIPE START marker; the stamp cannot name what makes the object")
check(b > a, "no RECIPE END marker after the start")

if a > 0 and b > a:
    span = SRC[a:b]
    # THE CALLS THAT DECIDE THE OBJECT MUST BE INSIDE IT. A marker pair that drifts off the
    # inference still hashes something and still produces a stamp - it just stops tracking the
    # thing it is for, which is the failure this file exists to make loud.
    for fn in ("createCellChat", "computeCommunProb", "computeCommunProbPathway",
               "aggregateNet", "netAnalysis_computeCentrality", "identifyOverExpressedGenes"):
        check(fn in span, f"{fn} is outside the recipe span, so editing it would not "
                          f"invalidate a single cached object")
    # ...and the drawing must be OUTSIDE it, or nothing was narrowed.
    for fn in ("netVisual_", "ggplot2::", "ComplexHeatmap::"):
        check(fn not in span,
              f"{fn} is inside the recipe span, so a drawing change still invalidates every "
              f"fitted object - the span was not narrowed, only moved")

check("digest_chr" in SRC, "no way to hash a span of the script")
check(re.search(r"is\.na\(\.a\) \|\| is\.na\(\.b\)", SRC) is not None,
      "no fallback when the markers are absent; a renamed marker would silently hash nothing")
check("packageVersion(\"CellChat\")" in SRC,
      "the stamp no longer carries the package version, so an upgrade would be invisible again")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - the recipe is the inference span, the drawing is outside it, and a missing marker "
      "falls back to the whole file")
