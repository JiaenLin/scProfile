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
    # THE RULE IS ABOUT THE METRIC LOOP, so the span checked ends where the loop does. The
    # ligand-receptor panel below it reads `net$prob` as the [pop x pop x pair] ARRAY and sums
    # two of its dimensions; `.armmat` returns a 2-D matrix and cannot serve it. Checking the
    # whole script flagged that as a bypass - a guard firing on the one thing it was not written
    # about, which is how a guard gets switched off. The end marker is a comment in the script,
    # so moving the loop moves the boundary with it.
    _end = SRC.find("# ---- LIGAND-RECEPTOR LEVEL", body_end)
    _stop = _end if _end > body_end else len(SRC)
    # THE METRIC LOOP ITSELF, and nothing else. The accessor's own body sits above `body_end`
    # and is excluded by starting there; the ligand-receptor panel below the marker reads
    # `net$prob` as the [pop x pop x pair] ARRAY and sums two dimensions, which `.armmat` - a
    # 2-D matrix - cannot serve, so it ends the span rather than being flagged as a bypass.
    outside = SRC[body_end:_stop]
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
