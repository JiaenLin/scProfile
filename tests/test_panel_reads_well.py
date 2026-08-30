"""The panel must place a figure once, name its contrast, and explain rather than warn.

Four defects found by reading the rendered page, none of which any other check can see:

  1. ONE FIGURE, TWENTY-ONE TIMES. Several evidence needs route to the same panel, and the panel
     emitted it for every need of every comparison - which reads as though that one figure were
     the finding.
  2. A FIGURE ANSWERING A NEED WAS DROPPED because another route answered it first. Two of the
     tool's functions answer "which populations differ"; the second was drawn on every run and
     placed in none.
  3. NOTHING ON A PLATE SAID WHICH CONTRAST IT WAS. Lifted out of the page it carried only the
     wrapped tool's generic title.
  4. THE CAPTIONS WARNED INSTEAD OF EXPLAINING - "what it does not establish" - and a design
     fact was repeated at the head of every comparison it touched.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []
src = (ROOT / "scprofile" / "paper.py").read_text()
rep = (ROOT / "scprofile" / "report.py").read_text()

# from `def panel(` to the next top-level def, whichever that is. The first version sliced to a
# helper defined ABOVE panel, so the slice ran backwards and every check passed on an empty
# string - a check that proves nothing while printing ok.
_i = src.index("def panel(out")
_j = src.find("\ndef ", _i + 1)
blk = src[_i:_j if _j > 0 else len(src)]
assert len(blk) > 500, "panel block extraction failed; the checks below would prove nothing"

# 1. a figure is placed once
if "placed_at" not in blk or "also.setdefault" not in blk:
    FAILURES.append("the panel does not dedupe: one figure can be placed once per need")
# 2. every resolving route is placed, not the first
if re.search(r"got = \(fn, hits\[0\]\)\s*\n\s*break", blk):
    FAILURES.append("the panel stops at the first route, so a second figure answering the same "
                    "need is drawn and never placed")
if "for fn, f in found:" not in blk:
    FAILURES.append("the panel does not place every route that resolved")
# 3. the contrast is named on the plate
fig = re.search(r"<figure><figcaption class=\"lead\">.*?</figcaption>", blk, re.S)
if not fig or "{_e(label)}" not in fig.group(0):
    FAILURES.append("a plate does not name the contrast it belongs to")
# 4. explain, do not warn
for name, text in (("paper.py", blk), ("report.py", rep)):
    if "does not establish" in text:
        FAILURES.append(f"{name}: a caption still frames its content as what it does NOT show")
if blk.count("cannot be answered as asked"):
    FAILURES.append("paper.py: aliasing is still written as a refusal to answer")
if "for c in cmps:\n        for a_ in" not in blk:
    FAILURES.append("aliasing is not collected and stated once for the whole panel")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ok: one figure placed once, every resolving route placed, the contrast named on each "
      "plate, and captions explain rather than warn")
