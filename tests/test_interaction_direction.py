"""An interaction is measured against the CONTROL stratum, and the direction is not positional.

THE BUG THIS EXISTS FOR. An interaction is one effect compared with the same effect at baseline:
how much more a factor does where the other factor is perturbed than it does in its control level.
The first version emitted the strata in READING order - control first, which is right for reading -
and then subtracted the second from the first. That is the opposite subtraction.

IT WAS INVISIBLE BECAUSE IT WAS CONSISTENT. Both framings of the same interaction were flipped the
same way, so they still equalled each other, every panel agreed with every other panel, and the
only sign that anything was wrong was a title that read backwards to someone who knew the biology.
A sign error that preserves its own internal consistency is the kind no cross-check finds.

So the direction is a property of the DECLARED control, marked on the row, and never of the order
rows happen to be in - the same rule that already fixes the direction of every contrast.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import units as U                                          # noqa: E402
from scprofile.design_panel import control_for                            # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


# a 2x2 in nobody's vocabulary
DES = {}
for a in ("lo", "hi"):
    for b in ("base", "treat"):
        for i in (1, 2):
            DES[f"{a}_{b}{i}"] = {"A": a, "B": b}
CTRL = {"A": "lo", "B": "base"}
facs = U.biological_factors(DES)

# the rule the host applies, restated here so the test fails if the host stops applying it
roles = {}
for f in facs:
    g = [x for x in facs if x != f][0]
    cg = control_for(sorted({str(r[g]) for r in DES.values()}), declared=CTRL.get(g))[0]
    for gl in sorted({str(r[g]) for r in DES.values()}):
        roles[(f, gl)] = "reference" if gl == cg else "against"

check(roles[("A", "base")] == "reference",
      "the control level of the stratum factor is not the reference, so the interaction is "
      "measured the wrong way round")
check(roles[("A", "treat")] == "against", "the perturbed stratum is not the one differenced")
check(roles[("B", "lo")] == "reference", "the second framing does not use its control stratum")
check(roles[("B", "hi")] == "against", "the second framing's perturbed stratum is misplaced")

# THE HOST MUST MARK IT, and the plugin must carry it
rep = (ROOT / "scprofile" / "report.py").read_text()
check('"stratum_role"' in rep,
      "the host does not mark which stratum is the reference, so a consumer can only guess from "
      "the order - which is how the subtraction came out backwards")
check("_ctrl_g" in rep and "reference\" if _gl == _ctrl_g" in rep,
      "the role is not derived from the DECLARED control")

ck = (ROOT / "kernels" / "cellchat.py").read_text()
check("stratum_role" in ck, "the plugin never receives the role")
check('rows$stratum_role == "against"' in ck and 'rows$stratum_role == "reference"' in ck,
      "the plugin picks its strata by POSITION rather than by the role it was given - the exact "
      "mistake, reintroduced")

# AND THE PANEL MUST SAY WHICH COLOUR MEANS WHAT. A diverging scale with no reading is the
# defect this repository has now fixed on three separate panel classes.
blk = ck[ck.index("interaction_"):]
check("RED: the" in ck and "BLUE: larger in" in ck,
      "the interaction heatmap has no direction key, so nothing on it says what red means")
check("Sources (Sender)" in ck and "Targets (Receiver)" in ck,
      "the interaction heatmap has no axis labels, unlike the tool's own heatmaps beside it")
check("NO interaction" in ck,
      "the panel does not say that white means the same response in both strata, which is the "
      "most misread value on a diverging scale")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - the control stratum is the reference, marked not positional, and the panel says so")
