"""A result is read in the design's order, and both documents walk the same one.

TWO DEFECTS, ONE CAUSE - the enumeration's order was being taken for the reading order.

  1. MARGINALS CAME FIRST. A marginal effect is an AVERAGE OVER STRATA, so it means something
     only after the strata have been seen. Emitted first, the section opened with the averaged
     answer and showed the effects it averages several screens later - which is precisely the
     order that hides an interaction, because a flat marginal reads as "no effect" until the
     reader reaches the two large opposite simple effects underneath it.
  2. THE SUMMARY TABLE SORTED BY RATIO while the subsections under it were in another order, so
     the first thing a reader meets disagreed with the body about what order the design is read
     in.

And within the simple effects the CONTROL stratum comes first: one factor's effect within the
other's control level is that effect on its own, while the same effect within a perturbed level
is that effect under a second change, and reading the perturbed one first asks the reader to
hold two changes at once. The control is the level DECLARED on the command line - nothing here
knows what a control is called in any field, which is the property the portability check exists
to protect, and which it enforced on the first draft of this very file.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile.design_panel import comparisons                             # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


# a 2x2, named in nobody's vocabulary
DES = {}
for a in ("lo", "hi"):
    for b in ("base", "treat"):
        for i in (1, 2, 3):
            DES[f"{a}_{b}{i}"] = {"A": a, "B": b}
CTRL = {"A": "lo", "B": "base"}

got = comparisons(DES, controls=CTRL)
kinds = [c["kind"] for c in got]
labels = [c.get("label") or "" for c in got]

# 1. simple before marginal before interaction
rank = {"simple": 0, "marginal": 1, "interaction": 2}
seq = [rank[k] for k in kinds]
check(seq == sorted(seq),
      f"the comparisons are not ordered simple -> marginal -> interaction: {kinds}")

# 2. the control stratum leads the simple effects
simple = [l for l, k in zip(labels, kinds) if k == "simple"]
check(simple == ["A | B = base", "B | A = lo", "A | B = treat", "B | A = hi"],
      f"the simple effects are not in control-stratum-first order: {simple}")

# 3. WITHOUT a declaration it must still be simple-before-marginal - the kind ordering is a
#    property of the design, not of anyone having declared a control.
seq2 = [rank[c["kind"]] for c in comparisons(DES)]
check(seq2 == sorted(seq2),
      "without declared controls the kind ordering is lost, but it does not depend on them")

# 4. THE SAME ORDER REACHES BOTH DOCUMENTS. `compose` walks it for the prose and the figure
#    numbers, `paper.panel` for the plates; if either stops passing the controls through, the
#    two documents silently disagree about order again.
comp = (ROOT / "scprofile" / "compose.py").read_text()
pap = (ROOT / "scprofile" / "paper.py").read_text()
check("_controls(run)" in comp,
      "compose does not read the run's declared controls, so its order falls back to "
      "alphabetical while the panel's does not")
check("controls=ctl" in comp or "controls=_controls" in comp,
      "compose does not pass the controls into comparisons()")
check("controls=pay.get(\"controls\")" in pap,
      "the figure panel does not pass the run's declared controls into comparisons()")
check("by_size" in comp,
      "the summary table still sorts by effect size, so it disagrees with the sections beneath "
      "it about the order the design is read in")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - simple before marginal, control stratum first, and both documents walk it")
