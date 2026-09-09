"""One fact, said four ways by five modules that do not know about each other.

THAT TWO FACTORS SPLIT THE SAMPLES IDENTICALLY is a single property of a design, and this
repository states it in four different wordings from five places:

  brief.py         `age` is aliased with `chemistry`: they split the samples identically ...
  compose.py       **age** varies together with chemistry across every sample, so ...      (x2)
  paper.py         <b>age</b> varies together with chemistry across every sample, so ...
  compare_panel.py ALIASED WITH CHEMISTRY: the two sides share no level of it, so ...       (x2)
                   Partly confounded with batch: the sides overlap but are not balanced ...
  planner.py       ALIASED with chemistry - this question cannot ...
                   'age' and 'chemistry' are PARTLY confounded (75% of ...
  report.py        Identical split to `chemistry` - one panel, not two, and which of them ... (x2)

Eleven places. Two of the wordings appear in more than one capitalisation - ALIASED WITH,
ALIASED with, Partly confounded, PARTLY confounded - so even a consumer that knew all five
phrasings and matched them case-sensitively would still miss some.

EACH IS DEFENSIBLE ON ITS OWN. The brief is for whoever writes the section; the composed
sentence is cohort-wide; the compare_panel one is about the samples ONE contrast actually
compares, which can be aliased inside a stratum even when the cohort is crossed - a stronger and
more specific claim. Redundancy across audiences is not the defect.

WHAT IS A DEFECT IS THAT NOTHING CAN ASK THE QUESTION. A reader can be told; a checker cannot
find out. An external check of "does this page warn about the confound" has to know all four
wordings and their capitalisation, and one written against the SAMBO run got it wrong three
times in a row - reporting the four pages that carry the strongest form of the sentence as
silent, twice writing that up as a defect in the tool. A property stated four ways is a property
with no single name, and a fact no consumer can test for is one that can quietly stop being
emitted.

This does not consolidate them - that is a decision about audiences, not a bug fix. It PINS the
set, so a fifth wording, or a change to one of these four, fails here and takes the external
check with it rather than silently making it blind.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


#: The exact substrings a rendered page may carry. Matched case-INSENSITIVELY by any consumer -
#: one of these is emitted in capitals and that is what defeated the external check.
PHRASINGS = ("aliased with", "varies together with", "identical split to",
             "partly confounded")

#: file -> how many places in it emit one. Counted on the source, ignoring comments and
#: docstrings, so a mention in prose about the problem does not inflate the count.
EMITTERS = {
    "scprofile/brief.py": 1,             # `age` is aliased with `chemistry`: they split ...
    "scprofile/compare_panel.py": 3,     # ALIASED WITH ... / Partly confounded with ...
    "scprofile/compose.py": 2,           # **age** varies together with chemistry across ...
    "scprofile/paper.py": 1,             # <b>age</b> varies together with chemistry ...
    "scprofile/planner.py": 2,           # ALIASED with ... / are PARTLY confounded (75% of ...
    "scprofile/report.py": 2,            # Identical split to `chemistry` - one panel, not two
}


def _emitting_lines(path):
    """Lines whose STRING LITERALS contain one of the phrasings.

    PARSED, NOT GREPPED. The first version of this matched a quoted fragment with a regex that
    required a double quote, and `report.py` builds its clause with single quotes - so the two
    places that state it on the by-arm page counted as zero, in a test written to stop exactly
    this kind of blindness. Walking the tree costs nothing and cannot be fooled by a quote
    style, a line break inside a string, or a phrase mentioned in a comment.
    """
    import ast
    text = (ROOT / path).read_text(encoding="utf-8")
    tree = ast.parse(text)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if id(node) in docstrings:
            continue
        low = node.value.lower()
        if any(w in low for w in PHRASINGS):
            out.append((node.lineno, " ".join(node.value.split())[:78]))
    return sorted(set(out))


total = 0
for path, want in sorted(EMITTERS.items()):
    got = _emitting_lines(path)
    total += len(got)
    check(len(got) == want,
          f"{path}: {len(got)} place(s) emit an aliasing statement, pinned at {want}"
          + ("".join(f"\n      {i}: {t}" for i, t in got) if len(got) != want else ""))

check(total == sum(EMITTERS.values()),
      f"{total} emitters across the tree, pinned at {sum(EMITTERS.values())}")

# And nowhere else. A new module that starts saying it must be added above, so the external
# check's list is updated in the same change.
others = []
for f in sorted((ROOT / "scprofile").glob("*.py")):
    rel = f"scprofile/{f.name}"
    if rel in EMITTERS:
        continue
    if _emitting_lines(rel):
        others.append(rel)
check(not others, f"a module outside the pinned set now states the aliasing: {others}")

if fails:
    print("FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"ok - {total} places state the aliasing, in {len(PHRASINGS)} wordings across "
      f"{len(EMITTERS)} modules; the set is pinned so an external check cannot go blind")
