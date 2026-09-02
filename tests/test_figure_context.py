"""Every figure must be able to say what it is of, in colours that mean the same thing everywhere.

An audit of 58 figure kinds in one run found three defects in nearly all of them, and this is the
suite for the host-side answer to all three. Each check below is a defect that was actually
observed, written as the property that would have caught it.
"""
from __future__ import annotations

import inspect
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scprofile import figure_context as FC                                      # noqa: E402
from scprofile import manifest as MF                                            # noqa: E402

FAILURES = []


def ck(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


# GENERIC LABELS ON PURPOSE. This suite tests a HOST module, and the portability guard refuses a
# project's own vocabulary anywhere in the tree - correctly: a host test written against one
# study's cell types is a host test that stops making sense for the next study. The shapes that
# matter are kept - a nested path, a plain name, a name that is a prefix of another.
POPS = ["Compartment/Family/Type one", "Compartment/Type two",
        "Family/Type three", "Type four", "Type", "Type four extended"]

print("one label, one colour, everywhere in the run")
a = FC.colour_map(POPS)
ck("every label gets a colour", set(a) == set(POPS))
ck("no two labels share a colour", len(set(a.values())) == len(a),
   f"{len(a) - len(set(a.values()))} collision(s)")
# THE DEFECT: one population was blue in the comparison figures and red in the per-unit figures of
# the SAME RUN, because each family coloured by position in its own data frame. Discovery order
# must not reach the colour.
b = FC.colour_map(list(reversed(POPS)))
ck("the map does not depend on the order the labels arrived in", a == b)
# AND A SUBSET MUST NOT SHIFT THE REST. A panel drawn on 9 of 13 populations coloured its nine
# from position 0, so every colour after the first gap moved.
sub = FC.colour_map([p for p in POPS if p != "Type four"])
ck("a panel missing one label keeps every other label's colour",
   all(sub[k] == a[k] for k in sub),
   f"{sum(1 for k in sub if sub[k] != a[k])} label(s) changed colour when one was dropped")
ck("colours are hex triples", all(len(v) == 7 and v[0] == "#" for v in a.values()))
# THE PALETTE MUST NOT RUN OUT. A fixed list of N breaks at N+1 by repeating - which is the very
# defect it was added to fix, arriving through the fix.
big = FC.colour_map([f"pop{i}" for i in range(200)])
ck("200 labels get 200 distinct colours", len(set(big.values())) == 200,
   f"only {len(set(big.values()))} distinct")

print("\nthe stamp names the unit, its size, and the DIRECTION of a difference")
s1 = FC.stamp(unit="arm_one", unit_kind="design arm", members=["A", "B", "C"], n_cells=30830)
ck("a unit stamp names the unit", "arm_one" in s1)
ck("and how many samples were pooled", "3 samples pooled" in s1, s1)
ck("and the cell count, grouped", "n = 30,830 cells" in s1, s1)
# THE DEFECT: two differential panels carried a title whose arm ordering was the opposite of the
# sign convention in the data, and no reader could recover which way the difference ran. `A vs B`
# is banned in a stamp; an explicit subtraction is not.
s2 = FC.stamp(contrast={"reference": "arm_ref", "against": "arm_test"})
ck("a contrast is rendered as an explicit subtraction", "MINUS" in s2, s2)
ck("and names its reference", "reference: arm_ref" in s2, s2)
ck("and never as the ambiguous 'vs'", " vs" not in s2.lower(), s2)
ck("nothing known, nothing claimed", FC.stamp() == "")

print("\nabsence is NAMED, never counted, and silent when there is none")
# THE DEFECT: one panel omitted the arm's top-ranked pathway with no note at all; others said
# nothing while dropping four populations. A count is not checkable; a list of names is.
_gone = {"Type four", "Type"}
ab = FC.absence(POPS, [p for p in POPS if p not in _gone])
ck("the missing labels are named", set(ab["absent"]) == _gone)
ck("the note carries the names, not a number",
   "Type four" in ab["note"] and "2 of" not in ab["note"])
ck("and says absence is not zero", "not zero" in ab["note"].lower(), ab["note"])
# A GATE THAT FIRES ON CORRECT BEHAVIOUR GETS SWITCHED OFF: nothing missing, nothing said.
ck("a complete panel carries no note", FC.absence(POPS, POPS)["note"] == "")

print("\nthe block reaches the plugin through in.json, and only when there is something to say")
ctx = FC.build(labels=POPS, unit="arm_one", unit_kind="design arm",
               members=["A", "B", "C"], n_cells=30830, drawn_labels=POPS[:3])
for k in ("labels", "colours", "stamp", "unit", "contrast", "absent", "note", "colour_key"):
    ck(f"figure_context carries {k}", k in ctx)
# TWO RUNS WHOSE MAPS DIFFER MUST NOT BE LAID SIDE BY SIDE, and the digest is what says so.
ck("the colour key changes when the label set does",
   FC.build(labels=POPS)["colour_key"] != FC.build(labels=POPS[:-1])["colour_key"])
ck("and is stable for the same label set",
   FC.build(labels=POPS)["colour_key"] == FC.build(labels=list(reversed(POPS)))["colour_key"])

ck("write_input accepts it", "figure_context" in inspect.signature(MF.write_input).parameters)
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "in.json"
    MF.write_input(p, h5ad=str(Path(td) / "x.h5ad"), out_dir=Path(td), keys={},
                   figure_context=ctx)
    got = json.loads(p.read_text())
    ck("and writes it verbatim", got.get("figure_context", {}).get("colours") == ctx["colours"])
    MF.write_input(p, h5ad=str(Path(td) / "x.h5ad"), out_dir=Path(td), keys={})
    # AN EMPTY STRUCTURE LOOKS LIKE AN ANSWER. A plugin must meet a MISSING key when the host has
    # nothing to say, not a block of blanks it will render as a caption saying nothing.
    ck("and omits the key entirely when there is nothing to say",
       "figure_context" not in json.loads(p.read_text()))

print("\nthe plugin side reads it by ACCESSOR, and a host that says nothing changes nothing")
from scprofile.plugin import Context                                            # noqa: E402
_c = Context(None, keys={}, out=".", figure_context=ctx)
# POSITIONAL AGAINST THE CALLER'S OWN LEVEL ORDER. A plotting function takes a colour vector
# against ITS levels, so the map must come back in the order asked for - handing back sorted keys
# would colour the wrong labels, which is the defect this exists to fix arriving through the fix.
_want = [POPS[2], POPS[0]]
ck("colours come back in the order asked for", list(_c.figure_colours(_want)) == _want,
   str(list(_c.figure_colours(_want))))
ck("the stamp is readable by accessor", _c.figure_stamp() == ctx["stamp"])
ck("the absence note is readable by accessor", _c.figure_absence() == ctx["note"])
# A HOST THAT SAYS NOTHING MUST LEAVE THE PLUGIN EXACTLY AS IT WAS. Empty, never a block of
# blanks: a plugin renders "" as no subtitle, and a structure of empty strings as a blank one.
_n = Context(None, keys={}, out=".")
ck("no context means no colours", _n.figure_colours() == {})
ck("no context means no stamp", _n.figure_stamp() == "")
ck("no context means no absence note", _n.figure_absence() == "")
# AND A PARTIAL MAP IS REFUSED RATHER THAN RECYCLED. A vector shorter than the level set gets
# recycled silently by the plotting layer, colouring populations with each other's colours.
ck("a label with no colour simply does not come back",
   list(_c.figure_colours(["not-a-label", POPS[0]])) == [POPS[0]])

print("\nnothing here knows about any particular method or project")
src = Path(FC.__file__).read_text(encoding="utf-8").lower()
for word in ("cell" + "chat", "cardio" + "myocyte", "path" + "way", "lig" + "and_pair",
             "mou" + "se", "fibro" + "blast"):
    ck(f"the host module never says {word[:4]}...", word not in src)

if FAILURES:
    print("\nFAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("\nok - one colour map, one stamp, named absence, and none of it method-specific")
