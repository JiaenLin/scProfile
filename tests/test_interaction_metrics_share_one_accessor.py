"""Every interaction metric reads its per-arm matrix through ONE accessor.

The interaction is a difference of two differences, so it reads four per-arm matrices. Those
four reads were four separate expressions, and adding a metric meant editing all four in step -
where missing one is silent, because the panel still draws, still has the right shape, and is
simply wrong for that arm.

It matters more now than it did. `count` and `weight` come straight off the merged object;
`prob_all` is `net$prob` summed over the L-R axis BEFORE `aggregateNet` applies its p-value
threshold, which is the whole point of that panel - it is the metric that does not punish a
population for having few cells. A read that bypasses the accessor gets the thresholded matrix
back and quietly reinstates the bias the panel exists to remove.

So: one accessor, and no direct read outside it.
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


d = SRC.find(".armmat <- function")
check(d > 0, "the interaction block has no single per-arm accessor")
if d > 0:
    # The accessor's own body is the ONLY place allowed to touch mi@net directly.
    body_end = SRC.find("for (ms in c(", d)
    check(body_end > d, "the metric loop no longer follows the accessor")
    outside = SRC[:d] + SRC[body_end:]
    stray = re.findall(r"mi@net\[\[", outside)
    check(not stray,
          "%d per-arm matrix read(s) bypass the accessor, so a metric can silently read the "
          "thresholded matrix instead of the one it declares" % len(stray))
    loop = re.search(r'for \(ms in c\(([^)]*)\)\)', SRC[body_end:body_end + 400])
    check(bool(loop) and "prob_all" in loop.group(1),
          "the size-balanced metric is not in the interaction metric loop")
    check(bool(loop) and "count" in loop.group(1) and "weight" in loop.group(1),
          "count or weight was dropped from the interaction loop - the tested readings must "
          "stay beside the balanced one, not be replaced by it")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - one accessor, three metrics, none bypassing it")
