"""The writing skill carries a template per method family, and the templates carry what they must.

WHY THIS IS CHECKED AT ALL. A skill is prose, and prose rots silently: a template can lose the
section that made it useful, or a new one can be added that names a study rather than a method,
and nothing objects until a section is written from it.

THE ONE RULE THAT MATTERS MOST is the last: a template must describe a METHOD FAMILY and never a
study. Templates travel between projects; studies do not, and a template carrying somebody's
cohort is how a tool acquires a dataset it was never given.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude" / "skills" / "result-section"
TPL = SKILL / "templates"

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


check(SKILL.is_file() or (SKILL / "SKILL.md").is_file(), "the result-section skill is missing")
skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")

check(TPL.is_dir(), "there is no templates/ directory, so every method family gets the same "
                    "paragraph")
check("templates/" in skill,
      "SKILL.md does not point at the templates, so a writer never finds them")

tpls = sorted(p for p in TPL.glob("*.md") if p.name != "README.md")
check(bool(tpls), "no method-family template exists")
check((TPL / "README.md").is_file(),
      "templates/README.md is missing, so nobody knows what a new template must contain")

#: WHAT EVERY TEMPLATE MUST ANSWER. Each earns its place: without the first a reader misreads
#: every finding; without the third an author does not know where the boundary is; without the
#: fifth the caveats scatter across the section instead of being stated once.
REQUIRED = ("What the method infers",
            "supports",
            "does NOT support",
            "order to write in",
            "Caveats",
            "Sentence patterns")
for t in tpls:
    body = t.read_text(encoding="utf-8")
    for r in REQUIRED:
        check(r.lower() in body.lower(),
              f"{t.name} has no section on {r!r} — a template missing it is a style guide, not a "
              f"template")
    # A CAVEAT WITHOUT A SOURCE IS AN OPINION. Every template's caveats are taken from published
    # practice, so each must be traceable to the paper that attached it to its own result.
    check(len(re.findall(r"doi:\S+", body)) >= 3,
          f"{t.name} carries fewer than three citations - its caveats cannot be checked, and a "
          f"caution nobody can trace is one an author is entitled to ignore")
    # AND IT MUST BE ABOUT A METHOD, NOT A STUDY. Project and cohort vocabulary is guarded
    # across the whole tree by `test_portability`, templates included - repeating the pattern
    # here would mean writing the project's own name into a file, which is the leak. What is
    # checked here is the possessive framing a template must not use, whatever the study is.
    for bad in ("our cohort", "this study's", "in our data"):
        check(bad.lower() not in body.lower(),
              f"{t.name} is written as though it belonged to one study - a template is about a "
              f"method family and travels between projects")

# INTERPRETATION IS PERMITTED AND MUST BE LEGIBLE. Both halves are checked: a template that
# offers no interpretive pattern leaves the section reading as measurement, and one that offers
# them without marking them produces a hypothesis in the grammar of a result.
for t in tpls:
    body = t.read_text(encoding="utf-8")
    check("marked as one" in body or "as interpretation" in body,
          f"{t.name} offers no pattern for stating an interpretation as an interpretation")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print(f"ok - {len(tpls)} template(s), each with its sections, its citations, and no study in it")
