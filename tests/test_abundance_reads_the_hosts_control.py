"""abundance's fit takes the host's control as its base, and its plan terms meet its own floor.

autodev W055 (harness ROUTE R32, GAP-039 by its second route): on the dev fixture's shape b, whose
control sorts last, the formula library's alphabetical base reversed every effect of abundance
(the shapes' effect columns summed +3.462 and -3.413). The answer recorded in
kernels/abundance.design.json names the run's control (`ctx.levels`) as patsy's Treatment
reference. This suite evaluates the plugin's OWN expressions - the fit call's `formula` and the
`terms` statement, read from the shipped file - against a stand-in host whose control sorts
last, and hands the formula to patsy, the library pertpy 1.0.4 builds its design with. It fails
on the file before the answer: `formula=term` puts the level that sorts first at the base, and
the plan's terms reach the fit whatever `min_samples_per_level` says.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" - {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


SRC = (ROOT / "kernels" / "abundance.py").read_text(encoding="utf-8")
RUN = next(n for n in ast.parse(SRC).body if isinstance(n, ast.FunctionDef) and n.name == "run")
calls = [n for n in ast.walk(RUN) if isinstance(n, ast.Call) and getattr(n.func, "attr", "")
         == "prepare"]
ck("run() has one fit call, `prepare(...)`", len(calls) == 1, len(calls))
formula = next((k.value for k in calls[0].keywords if k.arg == "formula"), None) if calls else None
terms = next((n.value for n in ast.walk(RUN) if isinstance(n, ast.Assign)
              and [getattr(t, "id", "") for t in n.targets] == ["terms"]), None)


class Host:
    """The two things the plugin asks here: the plan's contrast, and a term's levels in the order
    the plan decided - the control first, though it sorts last."""

    def __init__(self, contrast, testable):
        self.params, self._testable = {"contrast": contrast}, testable

    def levels(self, term, present=None):
        pres = sorted({str(x) for x in present}) if present is not None else ["untreated", "treated"]
        return ["untreated"] + [x for x in pres if x != "untreated"]

    def testable_factors(self, min_levels=2, min_replicates=2):
        return [t for t, n in self._testable.items() if n >= min_replicates]


print("1. the fit's base level is the host's control, not the level that sorts first")
try:
    import pandas as pd
    import patsy
except ImportError as e:                                            # pragma: no cover
    print(f"  skip (no patsy here: {e})")
    pd = patsy = None
if formula is not None and pd is not None:
    tab = pd.DataFrame({"arm": ["treated", "untreated", "treated", "untreated"]},
                       index=["s1", "s2", "s3", "s4"])
    f = eval(compile(ast.Expression(formula), "abundance.py", "eval"),
             {}, {"term": "arm", "tab": tab, "ctx": Host({}, {"arm": 2})})
    cols = patsy.dmatrix(f, tab).design_info.column_names
    ck("the formula the plugin hands pertpy is patsy's", isinstance(f, str), repr(f))
    ck("its design column is the treated level against the control ('untreated' sorts last)",
       len(cols) == 2 and cols[1].endswith("[T.treated]"), cols)

print("\n2. the plan's terms are held to the plugin's own min_samples_per_level")
if terms is not None:
    def terms_for(contrast, testable, floor):
        return eval(compile(ast.Expression(terms), "abundance.py", "eval"),
                    {"ctx": Host(contrast, testable),
                     "C": {"min_samples_per_level": floor}})
    plan = {"kind": "main effects", "terms": ["arm", "site"]}
    ck("at the floor the plan used, every term the plan named is fitted",
       list(terms_for(plan, {"arm": 3, "site": 3}, 2)) == ["arm", "site"])
    ck("a term whose levels miss the plugin's own floor is not fitted",
       list(terms_for(plan, {"arm": 4, "site": 3}, 4)) == ["arm"],
       terms_for(plan, {"arm": 4, "site": 3}, 4))
    ck("with no plan, the testable factors at that floor",
       list(terms_for({}, {"arm": 4, "site": 3}, 4)) == ["arm"])

print("\n3. a term the floor drops, and an interaction asked for, are named in the model's caveat")
cav = next((n.args[0] for n in ast.walk(RUN) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", "") == "caveat" and n.args
            and "Sample counts per level" in ast.unparse(n.args[0])), None)
ck("(the model's caveat is in run())", cav is not None)
if cav is not None and pd is not None:
    def said(contrast, terms_fitted):
        return eval(compile(ast.Expression(cav), "abundance.py", "eval"),
                    {"sizes": {}, "tab": pd.DataFrame(index=["s1", "s2"]), "C": {
                        "min_samples_per_level": 3}, "terms": terms_fitted,
                     "ctx": Host(contrast, {})})
    one = said({"kind": "main effects", "terms": ["arm", "site"]}, ["arm"])
    ck("a factor the plan named and the floor dropped is NOT TESTED, by name and by the floor",
       "Factor 'site', named by the plan, is NOT TESTED" in one and "fewer than 3 samples" in one,
       one)
    two = said({"kind": "interaction", "terms": ["arm", "site"]}, ["arm", "site"])
    ck("an interaction the plan asked for is NOT FITTED, by name and with the reason",
       "THE INTERACTION OF 'arm' AND 'site' IS NOT FITTED" in two
       and "one factor at a time" in two, two)
    ck("and nothing of the kind is said where neither happened",
       "NOT" not in said({"kind": "main effects", "terms": ["arm"]}, ["arm"]))

print()
if FAIL:
    print(f"{len(FAIL)} FAILED: {FAIL}")
    sys.exit(1)
print("abundance's fit reads its base level from the host, and its terms meet its own floor")
