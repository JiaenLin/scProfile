"""The written section and the figure panel must be built from the same enumeration.

They were not. The panel's sections come from `design_panel.comparisons`; the written section's
headings came from whatever its author chose. So the two agreed on nothing except the run they
came from - different structure, different figures, no cross-reference - and a reader moving
between them had to re-derive the mapping themselves.

The brief is where that is fixed, because it is what the writer is handed: it now gives the
panel's own labels, verbatim and in order, and the reference level of every contrast.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []
src = (ROOT / "scprofile" / "paper.py").read_text()

i = src.index("def brief(")
j = src.find("\ndef ", i + 1)
blk = src[i:j if j > 0 else len(src)]
assert len(blk) > 500, "brief block extraction failed; the checks below would prove nothing"

if "comparisons as _cm" not in blk and "_cmps(" not in blk:
    FAILURES.append("the brief does not enumerate the design's comparisons, so the section it "
                    "produces cannot share structure with the panel")
if "USE THESE HEADINGS" not in blk:
    FAILURES.append("the brief does not hand the writer the panel's section names, so the two "
                    "documents will disagree on structure")
if "control_basis" not in blk:
    FAILURES.append("the brief does not state the reference level of each contrast, so a "
                    "section can describe a difference in the wrong direction")

# and the panel must use the same function, or 'the same' is not true
pi = src.index("def panel(out")
pj = src.find("\ndef ", pi + 1)
pblk = src[pi:pj if pj > 0 else len(src)]
# MATCHED ON THE CALL, NOT ON ITS EXACT ARGUMENTS. The literal was `_cmps(des)`, so adding the
# declared controls - which is what puts the contrasts in reading order - read as the panel no
# longer building from `comparisons` at all. A guard that fires when its subject gains an
# argument is testing the spelling, not the property.
if "_cmps(des" not in pblk:
    FAILURES.append("the panel does not build from design_panel.comparisons")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ok: the brief and the panel are built from one enumeration, and the brief states the "
      "reference of every contrast")
