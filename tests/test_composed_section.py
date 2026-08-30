"""The composed section must name what actually moved, not print a certainty, and not go stale.

Three defects, all found by reading the composed output of a real run:

  1. LEADING MEANT THE MOST NEGATIVE, NOT THE LARGEST. Sorted by the signed delta, the section
     named five small movers as leading a contrast while the largest changes in it went
     unmentioned. Every number was correct and the sentence was wrong.
  2. A P-VALUE OF EXACTLY ZERO PRINTED AS `0.0e+00`. A test returning 0 has not measured a
     vanishing probability; it has run out of resolution. Printing it as a number states a
     certainty the test did not produce.
  3. A COMPOSED SECTION SURVIVED A REBUILD. An authored section must never be overwritten, but a
     composed one must be rebuilt when the tool changes - otherwise a rebuild keeps prose written
     by older code beside figures drawn by newer, which reads correctly and is not.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import compose as C                                        # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


# 1. leading is by magnitude
src = (ROOT / "scprofile" / "compose.py").read_text()
check("key=lambda kv: -abs(kv[1])" in src,
      "elements are not ranked by the size of their change, so `leading` names the wrong ones")

# 2. zero is not printed as a number
check(C._p(0.0).startswith("p reported as 0"),
      f"a p-value of zero renders as {C._p(0.0)!r}, which states a certainty the test did not "
      f"produce")
check(C._p(0.03) == "p = 0.03", f"an ordinary p-value renders as {C._p(0.03)!r}")
check("e-" in C._p(1e-12), f"a small p-value renders as {C._p(1e-12)!r}")

# 3. composed vs authored
check(bool(getattr(C, "COMPOSED_MARK", "")), "there is no marker distinguishing composed prose")
pap = (ROOT / "scprofile" / "paper.py").read_text()
check("COMPOSED_MARK" in pap,
      "paper.py cannot tell a composed section from an authored one, so it either overwrites an "
      "author's work or keeps stale composed prose forever")
check("startswith(_C.COMPOSED_MARK)" in pap,
      "the composed/authored distinction is not actually applied when deciding to rebuild")

# 4. THE SECTION MUST LEAD WITH FINDINGS, NOT WITH THE DESIGN'S QUESTIONS. A section whose
#    headings are questions reads as a questionnaire; one whose headings are answers reads as a
#    result, and a reader who reads only the headings knows what was found.
sec = src[src.index("def section("):src.index("def claims(")]
if "## {head}" not in sec or "head = (f\"{d['against']} carries" not in sec:
    FAILURES.append("the section's headings are not generated from the measurement, so they "
                    "cannot be findings and can drift from the text beneath them")
if "the largest difference in" not in sec:
    FAILURES.append("the section does not open with the shape of the result, so a reader must "
                    "assemble it from the subsections")
if "| comparison | reference |" not in sec:
    FAILURES.append("the section carries no summary table across comparisons")
# and the interaction must be arithmetic, explicitly not a test
if "difference of two differences" not in sec:
    FAILURES.append("the interaction is reported without saying the method provides no test "
                    "for it")

# 5. THE SUMMARY TABLE MUST SURVIVE THE RENDERER. Two defects, both visible in the first table
#    a reader of the paper meets, and both invisible to every check that existed:
#      - a contrast conditioned on a second factor is named `age | diet = chow`, and the pipe is
#        the column separator, so those rows carried six cells against a five-column header;
#      - the `|---|---|` separator was compared as a set of CELLS against a set of CHARACTERS,
#        which never matches, so a row of `---` was rendered as data under every header.
from scprofile.paper import _md as _MD                                    # noqa: E402

_t = _MD("| comparison | reference |\n|---|---|\n| age \\| diet = chow | young |")
check(_t.count("<tr>") == 2,
      f"the rendered table has {_t.count('<tr>')} row(s) for a header and one row of data - "
      f"the markdown separator is being rendered as data")
check("<td>age | diet = chow</td>" in _t,
      "a contrast label containing a pipe is split across two cells, so the row has more cells "
      "than the header has columns")
check("_cell(" in src,
      "the composer does not escape a pipe inside a table cell, so any contrast conditioned on "
      "a second factor breaks the row it is on")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ok: leading is by size of change, a zero p-value is described rather than printed, and a "
      "composed section is rebuilt while an authored one is not")
