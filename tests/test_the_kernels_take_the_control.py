"""The kernels contrast against the CONTROL the host resolved, not the level that sorts first.

THE DEFECT. The host has resolved a control per factor since alphabetical order put a two-factor
study's treated levels in the baseline (tests/test_control_is_the_reference.py) - but only for its
own panels. The DE kernel contrasted `sorted(levels)[-1]` against `[0]`, and abundance let scCODA's
formula take the alphabetical level as baseline. So on any study whose control sorts LAST - WT
after Mut, untreated after treated - every fold change in the DE table ran the other way round
from every comparison panel on the same page, and the correctly-labelled `contrast` column made
the table read right. Found by a second cohort (single-cell-harness ADR-0027, P1/P2), and by the
harness fixture's shape b, whose control is `untreated`.

THE FIX IS ONE CHANNEL. The plan's contrast decision now carries `controls` (and their basis),
resolved by the host's own `control_for` with `--control` first; the kernels read it.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import planner as PL                                          # noqa: E402

FAILURES = []


def check(c, m):
    print(("  ok   " if c else "  FAIL ") + m)
    if not c:
        FAILURES.append(m)


class K:
    name, needs_design, injects_required, injects_optional = "k", True, [], ["contrast"]


DESIGN = {"A1": {"genotype": "Mut"}, "A2": {"genotype": "Mut"},
          "B1": {"genotype": "WT"}, "B2": {"genotype": "WT"}}

print("the plan's contrast decision carries each term's control")
facts = PL.design_facts(DESIGN, ["genotype"], "sample", list(DESIGN))
con = PL.decisions_for(K(), facts).get("contrast") or {}
check(con.get("controls") == {"genotype": "WT"},
      f"WT, which sorts LAST, is the control by the host's vocabulary: {con.get('controls')}")
check("recommend" in (con.get("control_basis") or {}).get("genotype", ""),
      "and the basis says it was recommended, not declared")
facts = PL.design_facts(DESIGN, ["genotype"], "sample", list(DESIGN), controls={"genotype": "Mut"})
con = PL.decisions_for(K(), facts).get("contrast") or {}
check(con.get("controls") == {"genotype": "Mut"} and con["control_basis"]["genotype"] == "declared",
      "a declared control wins, and says so")


class NoContrast(K):
    injects_optional = []


check("contrast" not in PL.decisions_for(NoContrast(), facts),
      "a kernel that cannot receive a contrast is not handed one")

print("\nthe DE kernel orders each term with the control first")
spec = importlib.util.spec_from_file_location("de_kernel", ROOT / "kernels" / "de.py")
de = importlib.util.module_from_spec(spec)
spec.loader.exec_module(de)
o = de._reference_order(["Mut", "WT"], "WT")
check((o["numerator"], o["reference"], o["levels"]) == ("Mut", "WT", ["WT", "Mut"]),
      f"Mut vs WT, WT first in the fit: {o}")
o = de._reference_order(["treated", "untreated"], "untreated")
check((o["numerator"], o["reference"]) == ("treated", "untreated"), "treated vs untreated")
o = de._reference_order(["Mut", "WT"], None)
check((o["numerator"], o["reference"]) == ("WT", "Mut") and o["basis"].startswith("sort order"),
      "with no control the old order stands, and the basis SAYS it was sort order")
o = de._reference_order(["a", "b", "ctl"], "ctl")
check((o["reference"], o["numerator"], o["middle"]) == ("ctl", "b", ["a"]),
      "three levels: the control is the reference and the levels not taken are named")
src = (ROOT / "kernels" / "de.py").read_text(encoding="utf-8")
check("contrast=[term, levels[-1], levels[0]]" not in src,
      "no contrast is taken in sort order any more")
check("_reference_order(" in (ROOT / "kernels" / "de.py").read_text(encoding="utf-8").split("def _reference_order", 1)[1],
      "the fit uses the helper")
ab = (ROOT / "kernels" / "abundance.py").read_text(encoding="utf-8")
check('pd.Categorical(col.to_numpy(), categories=cats)' in ab and '[T.{ctl}]' in ab,
      "abundance builds the term with the control first, and checks the tool took it")

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED")
    raise SystemExit(1)
print("the kernels take the control")
