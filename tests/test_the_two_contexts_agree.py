"""`Context` and `CompareContext` must carry the same figure-governing state.

THIS PAIR HAS DIVERGED TWICE, both times costing a cohort run.

  `figure_stamp` was given to Context alone. Every arm-pair comparison died 0.1s in with
  AttributeError, on every run including the sealed reference, while the run sealed exit 0. A
  mixin was extracted to fix it.

  `figure_ceiling` was given to Context alone, hours later, in the same file. The compare phase
  wrote no ceiling rows, the embedded R parsed an empty table, and a family declared `at_most: 8`
  drew 77 panels in ONE contrast with the guard never firing.

The mixin could not have caught the second: it carries METHODS, and these are instance
attributes set in two separate `__init__`s. What is shared has to be checked, not assumed.

A COMPARISON NEEDS THIS STATE MORE, NOT LESS. It draws more per-item families than a unit does -
one chord per pathway, one scatter per shared population - so it is the phase where a ceiling
matters most and the one that had none.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


tree = ast.parse((ROOT / "scprofile/plugin.py").read_text(encoding="utf-8"))


def attrs_of(cls):
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and n.name == cls:
            init = next((x for x in n.body
                         if isinstance(x, ast.FunctionDef) and x.name == "__init__"), None)
            if init is None:
                return set()
            return {t.attr for st in ast.walk(init) if isinstance(st, ast.Assign)
                    for t in st.targets if isinstance(t, ast.Attribute)}
    raise AssertionError(f"no class {cls}")


#: State that decides WHAT GETS DRAWN, as opposed to what a unit happens to be. `figures_for` and
#: `profile_figures` are per-unit switches and have no meaning for a contrast; the rest govern
#: figures in both phases and must exist in both.
GOVERNING = {"figure_context", "figure_position", "figure_ceiling"}

c, cc = attrs_of("Context"), attrs_of("CompareContext")
check(GOVERNING <= c, f"Context is missing {sorted(GOVERNING - c)}")
check(GOVERNING <= cc,
      f"CompareContext is missing {sorted(GOVERNING - cc)} - the compare phase draws more "
      f"per-item families than a unit does and would be ungoverned")

# THE FIXTURE CAN EXPRESS THE FAILURE: if the reader cannot see attributes at all, both sets are
# empty and the two checks above pass while saying nothing.
check(len(c) > 3 and len(cc) > 1,
      f"the attribute reader found almost nothing ({len(c)}, {len(cc)}); it is not reading these "
      f"classes and the agreement above is vacuous")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: both contexts carry the state that decides what gets drawn")
