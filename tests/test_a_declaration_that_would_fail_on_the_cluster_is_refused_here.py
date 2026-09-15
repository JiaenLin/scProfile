"""Three declarations the validator passed and the cluster would have refused or wasted
(harness ADR-0026, step 4 - the kill pass): a config parameter with no default fails every
instance at start; a writing template that does not exist fails the writer after the run; an
`args` on an entry with `generated: False` has no generated site and does nothing at all.

Found by editing the plugin at random through the maker and reading what the maker said:
build 9 of 9 on all three. Everything here is invented; a check that passed by recognising a
real method's names would fail. Run: python tests/test_a_declaration_that_would_fail_on_the_cluster_is_refused_here.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import declare as D                                              # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def base():
    return {"name": "demo", "api": 1, "version": "1.0.0", "state_version": 1,
            "summary": "s", "when_to_use": "w", "provides": ["x"],
            "requires": {"python": ">=3.10"},
            "config": {"nboot": {"type": "int", "default": 100, "help": "permutations"}},
            "report": {"figures": [
                {"id": "native_a", "kind": "circle", "drawn_by": "tool", "fn": "drawA",
                 "axis": "unit", "position": "contrast", "legend": "a"}]}}


def errors(spec, word):
    return [m for lvl, m in D.check(spec, "demo") if lvl == "ERROR" and word in m]


def warns(spec, word):
    return [m for lvl, m in D.check(spec, "demo") if lvl == "WARN" and word in m]


print("a config parameter with no default is an error, not a warning")
spec = base()
del spec["config"]["nboot"]["default"]
ck("refused, by the parameter's name", errors(spec, "nboot") and any(
    "default" in m for m in errors(spec, "nboot")), str(D.check(spec, "demo"))[:300])
spec["config"]["nboot"]["required"] = True
ck("unless the parameter is declared required, which a run must then be given",
   not errors(spec, "nboot"), str(errors(spec, "nboot")))

print("\na writing template is a file, or the declaration is refused")
spec = base()
spec["report"]["writing_template"] = "no-such-template"
ck("a template that does not exist is refused, by name",
   errors(spec, "no-such-template"), str(D.check(spec, "demo"))[:300])
spec["report"]["writing_template"] = "cell-cell-communication"
ck("one that exists passes", not errors(spec, "writing_template"), str(errors(spec, "writing")))

print("\n`args` on an entry with no generated site does nothing, and the validator says so")
spec = base()
spec["report"]["figures"][0]["generated"] = False
spec["report"]["figures"][0]["args"] = "x, y = 1"
ck("warned, by the entry's id and the key",
   warns(spec, "native_a") and any("args" in m for m in warns(spec, "native_a")),
   str(D.check(spec, "demo"))[:300])

print("\na ceiling above one on an entry the companion draws once is refused")
# THE PLAN COUNTED FILES THE COMPANION CANNOT DRAW (harness ADR-0026, K-m): `at_most: 2` on a
# single-file entry - no `items`, no `file` rule - made the plan count twelve plates a run of
# six contrasts holds six of, and the layout read the axis as over budget on nothing.
spec = base()
spec["report"]["figures"][0]["at_most"] = 2
found = [m for lvl, m in D.check(spec, "demo") if lvl == "ERROR" and "at_most" in m and "native_a" in m]
ck("refused, naming the entry and what a ceiling needs", found and "items" in found[0], str(D.check(spec, "demo"))[:300])
spec["report"]["figures"][0]["items"] = 'c("in", "out")'
ck("with items to count over, the ceiling stands", not [m for lvl, m in D.check(spec, "demo") if lvl == "ERROR" and "at_most" in m and "native_a" in m])
spec = base()
spec["report"]["figures"][0]["at_most"] = 2
spec["report"]["figures"][0]["generated"] = False
ck("a side-effect entry's ceiling is accounting and stands", not [m for lvl, m in D.check(spec, "demo") if lvl == "ERROR" and "at_most" in m and "native_a" in m])

print("\nan argument the wrapped function has not got is refused against the recorded signatures")
import json
import tempfile
SIGS = {"tool": "faketool", "functions": {
    "drawA": "function (x, color = NULL, width = 10)",
    "drawB": "function (x, ...)",
    "drawC": "function (m, measure = c(\"count\", \"weight\"), title.name = NULL)"}}


def with_record(spec):
    with tempfile.TemporaryDirectory() as td:
        rec = Path(td) / "demo.signatures.json"
        rec.write_text(json.dumps(SIGS))
        return D.check(spec, "demo", signatures=rec)


spec = base()
spec["report"]["figures"][0]["args"] = "x, colour = 1"
found = [m for lvl, m in with_record(spec) if lvl == "ERROR" and "colour" in m]
ck("a misspelt argument is refused, naming the function's own parameters",
   found and "color" in found[0] and "width" in found[0], str(with_record(spec))[:300])
spec["report"]["figures"][0]["args"] = "x, color = 1, width = 12"
ck("the function's own parameters pass", not [m for lvl, m in with_record(spec) if lvl == "ERROR" and "drawA" in m])
spec["report"]["figures"][0]["fn"] = "drawB"
spec["report"]["figures"][0]["args"] = "x, anything = 1"
ck("a function taking `...` accepts any name; the check says it cannot refuse there",
   not [m for lvl, m in with_record(spec) if lvl == "ERROR" and "anything" in m])
spec["report"]["figures"][0]["fn"] = "drawC"
del spec["report"]["figures"][0]["args"]
spec["report"]["figures"][0]["expr"] = 'ComplexHeatmap::draw( drawC(m, measure = "weight", colour.heatmap = "RdBu", title.name = paste("a", b)))'
found = [m for lvl, m in with_record(spec) if lvl == "ERROR" and "colour.heatmap" in m]
ck("a named argument inside an expr's call is checked too, nested calls left alone", bool(found), str(with_record(spec))[:300])
spec["report"]["figures"][0]["fn"] = "drawZ"
spec["report"]["figures"][0]["expr"] = "drawZ(m, q = 1)"
found = [m for lvl, m in with_record(spec) if "drawZ" in m and "record" in m]
ck("a function the record does not carry is a warning to re-record, not an error",
   found and all(lvl != "ERROR" for lvl, m in with_record(spec) if "drawZ" in m), str(with_record(spec))[:300])
ck("without a record nothing is said", not [m for lvl, m in D.check(spec, "demo") if "signature" in m.lower()])

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\nwhat would fail on the cluster is refused here")
