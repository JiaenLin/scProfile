"""A contrast's reference must be the CONTROL, and how it was chosen must be reportable.

WHAT THIS COST: nothing chose the direction, so `arm_pairs` used `sorted(levels)` and the
reference was ALPHABETICAL. On a real two-factor study that put the TREATED level of both factors
in the baseline position - backwards on both, and invisibly, because a difference computed the
wrong way round looks exactly like one computed the right way: same figure, same colours,
opposite meaning.

An explicit declaration always wins. Failing that a level whose name conventionally reads as a
control is RECOMMENDED and the basis is returned, so it can be printed rather than applied in
silence. Failing that the first sorted level is used and the basis says exactly that.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile.compare_panel import arm_pairs, control_basis                # noqa: E402
from scprofile.design_panel import control_for                              # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


# the vocabulary is general, not this cohort's
for levels, want in ((["treated", "control"], "control"), (["KO", "WT"], "WT"),
                     (["drug", "vehicle"], "vehicle"), (["d7", "d0"], "d0"),
                     (["stim", "unstimulated"], "unstimulated")):
    got, why = control_for(levels)
    check(got == want, f"{levels}: chose {got!r}, expected {want!r}")
    check("recommend" in why, f"{levels}: no basis given for {got!r}")

# a declaration overrides the vocabulary entirely
got, why = control_for(["treated", "control"], declared="treated")
check(got == "treated" and why == "declared",
      f"a declared control was not honoured: {got!r} ({why})")

# where nothing reads as a control, say so rather than pretending
got, why = control_for(["A", "B"])
check(got == "A" and "sorts first" in why,
      f"an arbitrary reference was not described as arbitrary: {got!r} ({why})")

# AND THE CONTRAST MUST USE IT. This is the half that was broken.
D = {"s1": {"f1": "treated", "f2": "hi"}, "s2": {"f1": "treated", "f2": "lo"},
     "s3": {"f1": "control", "f2": "hi"}, "s4": {"f1": "control", "f2": "lo"}}
for sp in arm_pairs(D):
    if sp[1] == "f1":
        check(sp[2] == "control",
              f"{sp[0]}: reference is {sp[2]!r}, not the control - the difference is inverted")
basis = control_basis(D)
check(basis.get("f1", (None,))[0] == "control", f"control_basis wrong: {basis}")
check(bool(basis.get("f1", (None, ""))[1]), "control_basis returned no basis to print")

# a declared control must reach the contrast, not only the recommendation
for sp in arm_pairs(D, controls={"f1": "treated"}):
    if sp[1] == "f1":
        check(sp[2] == "treated",
              f"{sp[0]}: a declared control did not reach the contrast ({sp[2]!r})")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ok: the control is the reference, a declaration overrides the vocabulary, and an "
      "arbitrary choice is described as arbitrary")
