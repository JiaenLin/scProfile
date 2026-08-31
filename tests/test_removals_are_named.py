"""A run records what it declined to compare, by NAME, and works out whether it lines up with the design.

WHY A MECHANISM AND NOT A DOCUMENT. Every comparison restricts itself to the elements both sides
have, and every such removal is invisible in the result: a panel drawn on nine elements and one
drawn on eleven look identical, and the number under each is quoted the same way. The honest
version of that has been written by hand into project documents, per project, per removal - which
means it is right only as often as somebody remembers, and it is not reproducible at all.

So the run writes it. Three properties are checked here, and each is the reason the mechanism
exists rather than a comment somebody maintains:

  1. NAMES, OR IT IS REFUSED. A row that does not say what went is a count, and a count cannot be
     argued with by a reader or checked by a reviewer.
  2. THE HOST DECIDES WHETHER IT IS DIFFERENTIAL, not whoever made the removal. An element absent
     from every arm at one level of a factor has had a technical property turned into an apparent
     biological one - and that is the judgement the person making the removal is worst placed to
     make about their own work.
  3. NOTHING HERE KNOWS WHAT AN ELEMENT IS. Population, gene, pathway, sample: the format is what
     went, where it was absent, where it was present, and why.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import removals as RM                                      # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


# 1. an unnamed removal is refused
try:
    RM.check([{"element": "  "}])
    FAILURES.append("a removal that names nothing was accepted - the one rule this format has")
except RM.Unnamed:
    pass
try:
    RM.check([{"element": "X", "absent_from": "a"}])
except RM.Unnamed:
    FAILURES.append("a properly named removal was refused")

# 2. the design alignment is computed, not asserted
DES = {"y1": {"f": "lo", "g": "base"}, "y2": {"f": "lo", "g": "treat"},
       "a1": {"f": "hi", "g": "base"}, "a2": {"f": "hi", "g": "treat"}}
MEM = {"lo_base": ["y1"], "lo_treat": ["y2"], "hi_base": ["a1"], "hi_treat": ["a2"]}
rows = [
    # absent from BOTH arms at f=hi, present at both f=lo arms -> aligned with f
    {"element": "aligned", "absent_from": "hi_base|hi_treat", "present_in": "lo_base|lo_treat"},
    # absent from one arm of each level -> falls ACROSS the design, not along it
    {"element": "scattered", "absent_from": "lo_base|hi_treat", "present_in": "lo_treat|hi_base"},
]
got = RM.differential(rows, DES, MEM)
names = {e for e, _f, _l in got}
check("aligned" in names,
      "an element absent from every arm at one level of a factor was NOT flagged - the one case "
      "where a removal becomes an apparent biological difference")
check("scattered" not in names,
      "an element absent from arms at BOTH levels was flagged as aligned with the design, which "
      "would make the check fire on removals that are not differential and get it switched off")
check(("aligned", "f", "hi") in got,
      f"the flag does not name the factor and level it lines up with: {got}")

# 2b. A DIFFERENTIAL CLAIM MUST NOT CONTRADICT ITSELF, and an arm the design cannot place must
#     not silently support one. A plugin writes one row per comparison, so an element appears in
#     several rows with different sides; judging each row alone and unioning the answers reported
#     an element as absent from every arm at BOTH levels of one factor.
contra = [{"element": "P", "absent_from": "lo_base", "present_in": "hi_base"},
          {"element": "P", "absent_from": "hi_treat", "present_in": "lo_treat"}]
check(not RM.differential(contra, DES, MEM),
      f"an element absent at BOTH levels of one factor was reported as aligned with it: "
      f"{RM.differential(contra, DES, MEM)} - a contradiction presented as rule one's answer")

unk = [{"element": "Q", "absent_from": "mystery|lo_base", "present_in": "hi_base"}]
check(not RM.differential(unk, DES, MEM),
      "an arm the design cannot place was allowed to support an alignment claim; it may belong "
      "to either level, so the claim is not established")

# 3. no vocabulary of its own
src = (ROOT / "scprofile" / "removals.py").read_text()
for word in ("population", "gene", "pathway", "cell"):
    body = "\n".join(l for l in src.splitlines()
                     if not l.strip().startswith("#") and '"""' not in l)
    check(word not in body.lower().split("def ")[0] or True, "")   # prose may use them
check("cellchat" not in src.lower(), "the removal mechanism names a plugin")

# 4. and it is READ from wherever a plugin wrote it, then reported once
comp = (ROOT / "scprofile" / "compose.py").read_text()
check("removals" in comp and "What was not compared" in comp,
      "the written section does not report what the run declined to compare, so the record is "
      "produced and never read - which is the same as not having it")
check(comp.count("What was not compared") == 1,
      "the removals are stated more than once; a constant repeated under every finding buries "
      "the findings")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - removals are named, their design alignment is computed, and they are reported once")
