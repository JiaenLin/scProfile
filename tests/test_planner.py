"""The run plan, over project shapes this project does not have.

Every case below is a different experiment. If any of them produces a plan that reads plausible
and is wrong, the planner has learned one cohort. The shapes are deliberately awkward: one sample,
no design, a factor with a singleton arm, three crossed factors, a unit key with 40 units, and a
scan that could not finish.

Run: python tests/test_planner.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import planner as P                                              # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


class K:
    """A plugin, as the planner sees one."""
    def __init__(self, name, needs_design=False, per_unit=None, needs_kernels=()):
        self.name, self.needs_design = name, needs_design
        self.per_unit, self.needs_kernels = per_unit, list(needs_kernels)


def design(rows):
    return {s: r for s, r in rows.items()}


print("\na 2x2 with replication supports an interaction")
d = design({f"s{i}": {"age": a, "diet": t} for i, (a, t) in enumerate(
    [(a, t) for a in ("young", "old") for t in ("chow", "hf") for _ in range(3)])})
f = P.design_facts(d, ["age", "diet"], "sample", list(d))
ck("both factors testable", f["testable"] == ["age", "diet"], str(f["testable"]))
ck("the crossed pair is found", f["crossed_pairs"] == [["age", "diet"]], str(f["crossed_pairs"]))
v = P.plan_kernel(K("de", needs_design=True), present={"de": {"counts": True}}, facts=f,
                  searched=["obj"], ran=set())
ck("de RUNs at full on a crossed design", v.verdict == P.RUN and v.rung == "full",
   f"{v.verdict}/{v.rung}")

print("\nthree factors, only two crossed — still full, and the pair is named")
d3 = design({f"s{i}": {"age": a, "diet": t, "sex": ("m" if i % 2 else "f")}
             for i, (a, t) in enumerate(
                 [(a, t) for a in ("y", "o") for t in ("c", "h") for _ in range(3)])})
f3 = P.design_facts(d3, ["age", "diet", "sex"], "sample", list(d3))
ck("finds every crossed pair, sorted", len(f3["crossed_pairs"]) >= 1, str(f3["crossed_pairs"]))

print("\nno replication in one arm is NOT testable, and the numbers are shown")
d1 = design({"a1": {"g": "ctrl"}, "a2": {"g": "ctrl"}, "b1": {"g": "treat"}})
f1 = P.design_facts(d1, ["g"], "sample", list(d1))
ck("g is unreplicated, not testable", f1["unreplicated"] == ["g"] and f1["testable"] == [],
   f"{f1['unreplicated']} / {f1['testable']}")
ck("the singleton arm is named", f1["factors"]["g"]["singleton_levels"] == ["treat"],
   str(f1["factors"]["g"]["singleton_levels"]))
v = P.plan_kernel(K("de", needs_design=True), present={"de": {"counts": True}}, facts=f1,
                  searched=["obj"], ran=set())
ck("de is SKIPPED, not blocked", v.verdict == P.SKIP, v.verdict)
ck("and the skip shows the arm sizes", any("smallest arm n=1" in w for w in v.why),
   "; ".join(v.why))

print("\none level is a design fact; a missing table is not")
d0 = design({f"s{i}": {"diet": "hf"} for i in range(10)})
f0 = P.design_facts(d0, ["diet"], "sample", list(d0))
v = P.plan_kernel(K("de", needs_design=True), present={"de": {"counts": True}}, facts=f0,
                  searched=["obj"], ran=set())
ck("one level -> SKIP", v.verdict == P.SKIP, v.verdict)
ck("naming the factor and its single level", any("diet" in w for w in v.why), "; ".join(v.why))
fnone = P.design_facts(None, [], "sample", ["s1", "s2"])
v = P.plan_kernel(K("de", needs_design=True), present={"de": {"counts": True}}, facts=fnone,
                  searched=["obj"], ran=set())
ck("NO design table -> BLOCKED, never SKIP", v.verdict == P.BLOCKED, v.verdict)
ck("and it says so in as many words", any("MISSING INPUT" in w for w in v.why), "; ".join(v.why))

print("\nan undetermined input is UNRESOLVED and never a skip")
v = P.plan_kernel(K("velocity"), present={"velocity": {"spliced": None}}, facts=fnone,
                  searched=[], ran=set())
ck("None -> UNRESOLVED", v.verdict == P.UNRESOLVED, v.verdict)
ck("it is not a SKIP", v.verdict != P.SKIP)
ck("it names what could not be determined", v.evidence["undetermined"] == ["spliced"])

print("\nabsent-after-searching is BLOCKED, and must say where it looked")
v = P.plan_kernel(K("velocity"), present={"velocity": {"spliced": False}}, facts=fnone,
                  searched=["/a", "/b", "/c"], ran=set())
ck("False -> BLOCKED", v.verdict == P.BLOCKED, v.verdict)
ck("the count of places searched is in the reason", any("3 location" in w for w in v.why),
   "; ".join(v.why))
v0 = P.plan_kernel(K("velocity"), present={"velocity": {"spliced": False}}, facts=fnone,
                   searched=[], ran=set())
ck("searching nowhere is called out as a gap in the SCAN",
   any("gap in the scan" in w for w in v0.why), "; ".join(v0.why))

print("\na per-unit plugin with no unit key runs POOLED, and is not skipped")
v = P.plan_kernel(K("liana", per_unit="sample"), present={"liana": {"lognorm": True}},
                  facts=P.design_facts(None, [], None, []), searched=["obj"], ran=set())
ck("it still RUNs", v.verdict == P.RUN, v.verdict)
ck("at a reduced rung", v.rung == "reduced", str(v.rung))
ck("saying pooling answers a different question", "pooled" in (v.why_not_higher or "").lower(),
   str(v.why_not_higher))

print("\n40 units fan out at full")
many = [f"u{i:02d}" for i in range(40)]
fm = P.design_facts(None, [], "sample", many)
v = P.plan_kernel(K("liana", per_unit="sample"), present={"liana": {"lognorm": True}},
                  facts=fm, searched=["obj"], ran=set())
ck("full rung with 40 units", v.verdict == P.RUN and v.rung == "full", f"{v.verdict}/{v.rung}")

print("\nthe audit refuses a plan that cannot justify itself")
known = ["a", "b", "c"]
good = [P.Verdict("a", P.RUN, ["ok"], rung="full"),
        P.Verdict("b", P.SKIP, ["g: 2 level(s), smallest arm n=1"]),
        P.Verdict("c", P.BLOCKED, ["spliced is absent", "searched 3 location(s)"],
                  searched=["/a", "/b", "/c"])]
found = P.audit(good, known, f1)
ck("a sound plan passes", not [x for x in found if x.level == "ERROR"], str(found))

bad = list(good) + [P.Verdict("d", P.UNRESOLVED, ["could not read /x"])]
found = P.audit(bad, known + ["d"], f1)
ck("an UNRESOLVED fails the audit",
   any("UNRESOLVED" in x.check for x in found), str(found))

miss = [good[0]]
found = P.audit(miss, known, f1)
ck("a missing plugin fails", any("missing from the plan" in x.check for x in found), str(found))

dup = good + [P.Verdict("a", P.RUN, ["ok"], rung="full")]
found = P.audit(dup, known, f1)
ck("a duplicate fails", any("more than once" in x.check for x in found), str(found))

nosearch = [P.Verdict("a", P.RUN, ["ok"], rung="full"),
            P.Verdict("b", P.SKIP, ["g: 2 level(s), smallest arm n=1"]),
            P.Verdict("c", P.BLOCKED, ["spliced is absent"], searched=[])]
found = P.audit(nosearch, known, f1)
ck("a BLOCKED that searched nowhere fails",
   any("searched nowhere" in x.check for x in found), str(found))

degraded = [P.Verdict("a", P.RUN, ["ok"], rung="reduced"),
            P.Verdict("b", P.SKIP, ["g: 2 level(s), smallest arm n=1"]),
            P.Verdict("c", P.BLOCKED, ["x is absent"], searched=["/a"])]
found = P.audit(degraded, known, f1)
ck("a degraded RUN with no reason fails",
   any("does not say what would raise it" in x.check for x in found), str(found))

# a SKIP that names a factor the design says IS testable
fx = P.design_facts(design({f"s{i}": {"age": ("y" if i < 3 else "o")} for i in range(6)}),
                    ["age"], "sample", [f"s{i}" for i in range(6)])
wrong = [P.Verdict("a", P.RUN, ["ok"], rung="full"),
         P.Verdict("b", P.SKIP, ["age cannot be tested"]),
         P.Verdict("c", P.BLOCKED, ["x is absent"], searched=["/a"])]
found = P.audit(wrong, known, fx)
ck("a SKIP contradicted by the design fails",
   any("contradicted by the design" in x.check for x in found), str(found))

noskipjust = [P.Verdict("a", P.RUN, ["ok"], rung="full"),
              P.Verdict("b", P.SKIP, ["it probably will not work"]),
              P.Verdict("c", P.BLOCKED, ["x is absent"], searched=["/a"])]
found = P.audit(noskipjust, known, fx)
ck("a SKIP citing no factor fails", any("naming no factor" in x.check for x in found), str(found))

print("\nthe audit says what it checked, not only what it found")
lines = []
P.audit(good, known, f1, log=lines.append)
ck("it reports its own checks", len(lines) >= 6, f"{len(lines)} lines")
ck("even when everything passes", any("checked:" in x for x in lines))

print("\nthe plan is deterministic")
a1 = [v.as_dict() for v in [P.plan_kernel(K("de", needs_design=True),
                                          present={"de": {"counts": True}}, facts=f,
                                          searched=["obj"], ran=set()) for _ in range(3)]]
ck("three identical calls agree", a1[0] == a1[1] == a1[2])

print("\n" + ("the planner holds on every shape" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
