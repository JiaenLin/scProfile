"""The run plan, over project shapes this project does not have.

Every case below is a different experiment. If any of them produces a plan that reads plausible
and is wrong, the planner has learned one cohort. The shapes are deliberately awkward: one sample,
no design, a factor with a singleton arm, three crossed factors, a unit key with 40 units, and a
scan that could not finish.

Run: python tests/test_planner.py
"""
import sys
from html import escape as _e_html
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import planner as P                                              # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


class K:
    """A plugin, as the planner sees one.

    `injects_optional` carries `contrast` because a real design-testing plugin declares it: the
    planner now refuses to record a decision the plugin has not said it can be given, after a
    version that recorded one anyway printed a contrast the run then refused outright. A stub
    that omits it is not a simpler plugin, it is a plugin that cannot receive a contrast.
    """
    def __init__(self, name, needs_design=False, per_unit=None, needs_kernels=(),
                 injects_optional=("contrast",)):
        self.name, self.needs_design = name, needs_design
        self.per_unit, self.needs_kernels = per_unit, list(needs_kernels)
        self.injects_required = ["design"] if needs_design else []
        self.injects_optional = list(injects_optional)


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
# A SINGLETON ARM IS A CAVEAT, NOT A SKIP. ctrl has two samples, so a contrast can be phrased;
# that the treat arm has one is something to tell the reader, not a reason to withhold the run.
# This test asserted a SKIP until 2026-08-22, which is the behaviour that told a user with a real
# slightly-imbalanced experiment that their data could not be analysed.
ck("an imbalanced design RUNS", v.verdict == P.RUN, v.verdict)
ck("and the singleton arm is a caveat", any("singleton arm" in c for c in v.caveats),
   "; ".join(v.caveats))
ck("naming which arm", any("treat" in c for c in v.caveats), "; ".join(v.caveats))

print("\nonly a design that cannot phrase the question at all is skipped")
for label, rows in (("every arm n=1", {"a": {"g": "x"}, "b": {"g": "y"}, "c": {"g": "z"}}),
                    ("one level", {f"s{i}": {"g": "only"} for i in range(8)})):
    ff = P.design_facts(design(rows), ["g"], "sample", list(rows))
    vv = P.plan_kernel(K("de", needs_design=True), present={"de": {"counts": True}}, facts=ff,
                       searched=["obj"], ran=set())
    ck(f"{label} -> SKIP", vv.verdict == P.SKIP, vv.verdict)
    ck(f"{label} explains that a caveat could not save it",
       any("carried as a caveat" in w for w in vv.why), "; ".join(vv.why))

print("\nconfounding is a caveat and the run proceeds")
dc = {f"s{i}": {"age": ("old" if i < 4 else "young"),
                "chem": ("V2" if i < 4 else "V3"),
                "diet": ("hf" if i % 2 else "chow")} for i in range(8)}
fc = P.design_facts(design(dc), ["age", "chem", "diet"], "sample", list(dc))
cf = P.confounding(fc)
ck("a complete confound is found", any(c["agreement"] == 1.0 for c in cf), str(cf)[:120])
ck("and it names both factors",
   any("age" in c["note"] and "chem" in c["note"] for c in cf))
vv = P.plan_kernel(K("de", needs_design=True), present={"de": {"counts": True}}, facts=fc,
                   searched=["obj"], ran=set())
ck("the plugin still RUNS", vv.verdict == P.RUN, vv.verdict)
ck("with the confound as a caveat", any("confounded" in c for c in vv.caveats),
   "; ".join(vv.caveats))
ck("telling the reader to attribute carefully",
   any("attribute" in c.lower() for c in vv.caveats), "; ".join(vv.caveats))

print("\nsettings are prescribed at maximum capacity")
st = P.settings_for(K("de", needs_design=True),
                    keys={"label": "cell_type", "sample": "sample", "counts_layer": "counts"},
                    facts=f, references=None, cores=8)
ck("an interaction is chosen when the design is crossed",
   st["contrast"]["kind"] == "interaction", str(st.get("contrast")))
ck("with a formula a user can read", ":" in st["contrast"]["formula"], str(st["contrast"]))
ck("the sample key is carried for a design-aware plugin", st.get("sample") == "sample")
# ONLY WHAT IT CONSUMES. K declares nothing in needs_*, so nothing but the sample key (needed to
# join the design) should appear - listing every detected key against every plugin claimed that a
# plugin would run on inputs it never reads.
ck("a key the plugin does not declare is NOT listed", "embedding" not in st, str(sorted(st)))
class KN:
    name, needs_design, per_unit, needs_kernels = "n", False, None, []
    needs_obs, needs_obsm, needs_layers, sees = ["{label}"], [], ["{lognorm}"], None
stn = P.settings_for(KN(), keys={"label": "ct", "batch": "b", "embedding": "X_p",
                                 "lognorm_layer": "lognorm", "sample": "s"},
                     facts={}, references=None, cores=None)
ck("a declared obs key is listed", stn.get("label") == "ct")
ck("a declared layer is listed", stn.get("lognorm_layer") == "lognorm")
ck("an undeclared embedding is not", "embedding" not in stn, str(sorted(stn)))
ck("an undeclared batch is not", "batch" not in stn, str(sorted(stn)))
ck("and neither is sample, for a plugin that is not per-unit or design-aware",
   "sample" not in stn, str(sorted(stn)))
st2 = P.settings_for(K("liana", per_unit="sample"), keys={"label": "ct"},
                     facts={"units": ["a", "b", "c"]}, references=None, cores=None)
ck("a per-unit plugin is told its units", st2["per_unit"]["n"] == 3, str(st2["per_unit"]))
st3 = P.settings_for(K("liana", per_unit="sample"), keys={}, facts={"units": []},
                     references=None, cores=None)
ck("and pooling is named when there are none", "POOLED" in st3["per_unit"]["mode"])

print("\nthe order of runs honours needs_kernels")
class KO:
    def __init__(self, name, needs):
        self.name, self.needs_kernels = name, needs
        self.spec, self.needs_capabilities = {}, []
avail = {"a": KO("a", []), "b": KO("b", ["a"]), "c": KO("c", ["b"]), "d": KO("d", [])}
w = P.order_of_runs(["a", "b", "c", "d"], avail)
ck("dependents come after what they need", w == [["a", "d"], ["b"], ["c"]], str(w))
ck("independents share a wave", "d" in w[0])
cyc = {"x": KO("x", ["y"]), "y": KO("y", ["x"])}
ck("a cycle is reported, not looped on", bool(P.order_of_runs(["x", "y"], cyc)))

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

print("\nreadiness is a SECOND AXIS and never blocks the project verdict")
class KB2:
    def __init__(self, name, status="built", needs_env=True):
        self.name, self.status, self.needs_env = name, status, needs_env
        self.needs_design, self.per_unit, self.needs_kernels = False, None, []
_k = KB2("liana", status="planned")
_v = P.plan_kernel(_k, present={"liana": {"lognorm": True}},
                   facts=P.design_facts(None, [], "sample", ["a", "b", "c"]),
                   searched=["/x"], ran={"liana"})
_v.readiness = P.build_state(_k, "host", prefix="/env")
ck("an unbuilt plugin still gets its PROJECT verdict", _v.verdict == P.RUN, _v.verdict)
ck("and it is not BLOCKED by the build", _v.verdict != P.BLOCKED)
ck("readiness records the wrapper is missing", _v.readiness["kind"] == "no_wrapper")
ck("with the command that fixes it", "scaffold" in _v.readiness["fix"])
_rdy, _pend = P.ready_count([_v])
ck("it counts as pending, not as unrunnable", len(_pend) == 1 and len(_rdy) == 0)

print("\na build defect is a fact about the installation, never about the project")
class KB:
    def __init__(self, name, status="built", needs_env=True):
        self.name, self.status, self.needs_env = name, status, needs_env
        self.needs_design, self.per_unit, self.needs_kernels = False, None, []
for state, kind, fixable in (("missing", "env_missing", True),
                             ("stale", "env_stale", True),
                             (None, "env_unknown", False)):
    d = P.build_state(KB("x"), state, prefix="/env")
    ck(f"{state!r} names the defect kind", d["kind"] == kind, str(d))
    ck(f"{state!r} fixable={fixable}", d["fixable"] is fixable)
    ck(f"{state!r} carries a fix", bool(d["fix"]))
d = P.build_state(KB("x", status="planned"), "installed", prefix="/env")
ck("no wrapper is not fixable by building", not d["fixable"])
ck("and it points at scaffold", "scaffold" in d["fix"])
for good in ("installed", "host", "override"):
    ck(f"{good!r} is not a defect", P.build_state(KB("x"), good, prefix="/e") is None)
ck("a host-interpreter plugin with no prefix is fine",
   P.build_state(KB("x", needs_env=False), None, prefix=None) is None)

print("\nonly build defects are offered for repair")
def _rv(name, state, status="built"):
    v = P.Verdict(name, P.RUN, ["ok"], rung="full")
    v.readiness = P.build_state(KB(name, status=status), state, prefix="/e")
    return v
vs = [_rv("a", "missing"), _rv("b", "stale"), _rv("c", "host", status="planned"),
      P.Verdict("d", P.BLOCKED, ["no design table was given"]),
      P.Verdict("e", P.RUN, ["ok"], rung="full")]
fx = [n for n, _d in P.fixable_builds(vs)]
ck("the two environment defects are offered", fx == ["a", "b"], str(fx))
ck("a missing wrapper is NOT auto-built", "c" not in fx)
ck("a missing design table is NOT installed away", "d" not in fx)
ck("a healthy plugin is left alone", "e" not in fx)

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

print("\nthe report answers the user's questions, in the user's order")
import tempfile as _tf                                                          # noqa: E402
from scprofile import plan_report as PR                                         # noqa: E402
# A FRESH design, not `d` - which an earlier section rebinds. A test that silently reads a name
# some other block redefined is testing whatever ran last.
_rd = {f"s{i}": {"age": a, "diet": t2} for i, (a, t2) in enumerate(
    [(a, t2) for a in ("young", "old") for t2 in ("chow", "hf") for _ in range(3)])}
_plan = {
    "version": "0.1.0", "h5ad": "/x/o.h5ad",
    "describe": {"n_obs": 100713, "n_vars": 34290},
    "facts": P.design_facts(_rd, ["age", "diet"], "sample", list(_rd)),
    "waves": [["cellcycle", "liana"], ["pseudotime"]],
    "roots": ["/a", "/b"], "search_incomplete": False,
    "constraint_on_use": "must not carry a composition claim across batch",
    "constraint_source": "uns['scintegrate']",
    "verdicts": [
        dict(P.Verdict("cellcycle", P.RUN, ["ok"], rung="full").as_dict(),
             settings={"label": "cell_type", "cores": 1}),
        dict(P.Verdict("liana", P.RUN, ["ok"], rung="reduced").as_dict(),
             settings={"per_unit": {"key": "sample", "n": 10, "mode": "per unit",
                                    "units": []}},
             readiness={"kind": "no_wrapper", "fixable": False,
                        "why": "declared but not built", "fix": "scprofile scaffold liana"},
             caveats=["'age' and 'chemistry' are COMPLETELY confounded"],
             why_not_higher="only 1 unit"),
        dict(P.Verdict("pseudotime", P.RUN, ["ok"], rung="full").as_dict(), settings={}),
        dict(P.Verdict("de", P.SKIP, ["no factor can express a contrast at all"]).as_dict()),
        dict(P.Verdict("velocity", P.BLOCKED, ["layers[spliced] is absent"],
                       searched=["/a", "/b", "/c"]).as_dict()),
    ],
    "audited": True,
    "audit_checks": ["checked: all 9 known plugin(s) appear exactly once",
                     "checked: no plugin is UNRESOLVED"],
    "audit": [],
}
with _tf.TemporaryDirectory() as _d:
    # THE REGISTRY IS PASSED, as the real caller passes it: the "what you get" column is read
    # from each plugin's own declaration now, not from a table in the host that knew only the
    # nine plugins it was written beside.
    from scprofile.kernels import discover as _disc
    _reg = _disc(str(Path(__file__).resolve().parents[1] / "kernels"))
    f = PR.write(_d, _plan, kernels=_reg)
    html = Path(f).read_text()
    ck("it says nothing has run, first", "Nothing here has run yet" in html)
    ck("that warning precedes the plugin list",
       html.index("Nothing here has run") < html.index("What you can run"))
    ck("'what you can run' comes before 'what will not run'",
       html.index("What you can run") < html.index("What will not run"))
    ck("'what you get' precedes the settings",
       html.index("What you get out of it") < html.index("in what order, with what settings"))
    # ON A PLUGIN THAT WILL ACTUALLY RUN. The first version asserted velocity's text, and
    # velocity is BLOCKED in this fixture - the table covers what you GET, so a blocked plugin is
    # correctly absent from it. The test was wrong, not the page.
    # ASSERTED AGAINST THE DECLARATION, not against prose that used to live in the host. If a
    # plugin rewords its own summary this follows it, which is the point.
    _cc = _reg["cellcycle"].spec
    ck("each running plugin says what it yields, in its own declared words",
       _e_html(_cc["summary"][:40]) in html, _cc["summary"][:60])
    ck("and what it cannot tell you, from its own cannot_show",
       _e_html(_cc["cannot_show"][0][:40]) in html, _cc["cannot_show"][0][:60])
    ck("a blocked plugin is NOT in the what-you-get table",
       _e_html(_reg["velocity"].spec["summary"][:40]) not in html)
    # and with no registry the column is EMPTY rather than filled from a stale list
    _bare = Path(PR.write(_d, _plan, filename="bare.html")).read_text()
    ck("with no registry the yield column is empty, not wrong",
       _e_html(_cc["summary"][:40]) not in _bare)
    ck("the design table is shown with arm sizes", "smallest arm" in html)
    ck("the crossed pair is named", "interaction is estimable" in html)
    ck("waves are rendered", "Wave 1" in html and "Wave 2" in html)
    ck("settings are shown per plugin", "cell_type" in html)
    ck("a confound appears as a caveat, not a refusal",
       "Carry this with the result" in html and "confounded" in html)
    ck("an unbuilt plugin is not presented as a data problem",
       "not your data" in html or "not about this installation" in html
       or "not your\ndata" in html or "about this installation, not your" in html)
    ck("a SKIP explains a caveat could not save it", "carried as a caveat instead" in html)
    ck("a BLOCKED says how many places were searched", "3 location(s)" in html)
    ck("the upstream constraint is reproduced", "composition claim across batch" in html)
    # A PASSING AUDIT MUST BE VISIBLE. Keyed on findings alone, a clean audit rendered nothing
    # and was indistinguishable from an audit that never ran.
    ck("a PASSING audit is still shown", "Was this plan checked" in html)
    ck("it says every check passed", "Every check passed" in html)
    ck("and lists what was checked", "appear exactly once" in html)
    _noaudit = dict(_plan); _noaudit["audited"] = False
    with _tf.TemporaryDirectory() as _d2:
        h2 = Path(PR.write(_d2, _noaudit)).read_text()
        ck("an UNAUDITED plan says so plainly", "was not audited" in h2)
    ck("it is a standalone page", "<style>" in html and "<title>" in html)
    ck("no external resource is referenced", "http://" not in html and "src=" not in html)

print("\nthe builder adapts to the machine, and the planner is cheap on repeat")
from scprofile import runner as _R, provenance as _PV                           # noqa: E402
_m = _R.machine()
ck("the machine is probed, not assumed", set(_m) == {"managers", "pythons", "route", "why"})
ck("a route is chosen", _m["route"] in ("micromamba", "mamba", "conda", "venv", "host"))
ck("and it says WHY, in terms of what is present", len(_m["why"]) > 40)

_root = [str(Path(__file__).resolve().parents[1])]
_PV.find_layer_sources(_root, cache_seconds=0)          # cold, cache bypassed
ck("a cold scan reports it was not cached", _PV.find_layer_sources.cached is False)
_PV.find_layer_sources(_root)                            # writes the cache
_a = _PV.find_layer_sources(_root)
ck("a repeated scan is served from cache", _PV.find_layer_sources.cached is True)
ck("and returns the same paths", _PV.find_layer_sources(_root) == _a)
ck("the cache lives outside the project",
   "scProfile" not in _PV._cache_path(_root, ("spliced",))
   or ".cache" in _PV._cache_path(_root, ("spliced",)))

print("\na plugin carries its own proof")
import importlib.util as _iu                                                    # noqa: E402
_pp = Path(__file__).resolve().parents[1] / "kernels" / "decoupler.py"
_spec = _iu.spec_from_file_location("dcp", _pp)
_mod = _iu.module_from_spec(_spec); _spec.loader.exec_module(_mod)
# `needs` became `inject` when capabilities replaced free-text prerequisites: a plugin now says
# what it must be GIVEN, and the host resolves it rather than the plugin checking.
# `env` became `requires` when environment resolution moved to the builder: a plugin states what
# it NEEDS, and the builder decides how few environments satisfy every plugin's needs together.
ck("it declares everything the builder needs",
   {"api", "requires", "inject", "produces", "cannot_show", "upstream"} <= set(_mod.PLUGIN),
   str(sorted(set(_mod.PLUGIN))))
ck("and its requirement is constraints, not a private lock",
   "packages" in _mod.PLUGIN["requires"] and "python" in _mod.PLUGIN["requires"])
ck("it has a run(ctx)", callable(getattr(_mod, "run", None)))
ck("it has a selftest(ctx) in the same file", callable(getattr(_mod, "selftest", None)))
ck("its requirement constrains the interpreter",
   bool(_mod.PLUGIN["requires"].get("python")))
ck("its upstream record names defaults it changed",
   bool(_mod.PLUGIN["upstream"].get("defaults_changed")))
# THE RULE APPLIES TO run(), NOT TO selftest(). `run` is handed a stranger's object and may
# name nothing about it. `selftest` BUILDS ITS OWN DATA, so it must name a species to fetch a
# prior and may use the host fixture's own layer names - those are its inputs, not a user's.
import inspect as _in2                                                          # noqa: E402
_runsrc = _in2.getsource(_mod.run)
# WHAT IS WRONG IS INDEXING WITH A LITERAL, not the presence of a word. `ctx.keys.get("lognorm")`
# is a ROLE and is exactly right; `adata.layers["lognorm"]` is a column name and is not. The first
# version of this check matched bare strings and failed on the correct line.
import re as _re2                                                               # noqa: E402
# obs, layers and var are the USER'S vocabulary and a plugin must reach them through ctx.
# obsm is excluded deliberately: a plugin legitimately reads back the key the WRAPPED LIBRARY just
# wrote - `ctx.adata.obsm["ulm_estimate"]` is decoupler's own API surface, not a name the user
# chose - and failing that would push plugins into guessing where a library put its result.
_bad = _re2.findall(r"\.(obs|layers|var)\[\s*['\"][A-Za-z_]", _runsrc)
ck("run() indexes no user-owned namespace by a literal name", not _bad, str(_bad))
ck("and hard-codes no organism",
   not _re2.search(r"organism\s*=\s*['\"](human|mouse)", _runsrc))
# EVERY host route to a column is by ROLE. `ctx.populations()` is the strongest of them - it
# resolves the label role AND applies the sentinel rule - and listing only the two older ones made
# a plugin fail this check for using the better one.
ck("run() reads keys by ROLE instead",
   any(x in _runsrc for x in ('ctx.keys.get(', 'ctx.obs(', 'ctx.populations(')))
ck("and takes the organism from the host", "ctx.organism" in _runsrc)
ck("selftest is allowed its own fixture's names",
   "human" in _in2.getsource(_mod.selftest))

print("\nthe audit is stated over the plan that was ASKED FOR")
# `plan --kernel a,b --audit` reported an ERROR for every plugin the user had deliberately left
# out - "a known plugin is missing from the plan" - because the completeness rule was stated over
# every plugin on disk rather than over the plan drawn. An audit that cannot be run clean on a
# legitimate invocation is an audit people learn to silence with a flag.
_v = [P.Verdict("a", P.RUN, ["ok"], rung="full")]
_found = P.audit(_v, ["a"], {"has_design": False})
ck("a restricted plan audits clean", not [x for x in _found if x.level == "ERROR"],
   str(_found))
_found = P.audit(_v, ["a", "b"], {"has_design": False})
ck("and a plugin genuinely dropped from its own plan is still an ERROR",
   any(x.level == "ERROR" and "b" in (x.detail or "") for x in _found), str(_found))
import inspect as _in3                                                          # noqa: E402
from scprofile import cli as _cli                                               # noqa: E402
ck("the caller audits the plan it drew",
   "PL.audit(verdicts, sorted(want)" in _in3.getsource(_cli._plan),
   "the audit's `known` must be the set the verdicts were built from")

print("\na reference that has not been downloaded is READINESS, not a blocked verdict")
# It was reported BLOCKED - the same word as "your data has no spliced counts" - which tells a
# new user their dataset cannot support the method when one command fixes it. An organism the
# plugin has NO reference for stays BLOCKED, because there is nothing to download and that IS a
# fact about the project.
import types as _t                                                             # noqa: E402
_k = _t.SimpleNamespace(name="scenic", status="built", needs_env=True)
_miss = P.build_state(_k, "ok", prefix="/e", refs="missing", refdir="/r", organism="mouse")
ck("a missing reference is a readiness defect", _miss and _miss["kind"] == "refs_missing", str(_miss))
ck("and it is fixable", _miss["fixable"] is True)
ck("and the fix is the command that fixes it",
   "fetch scenic" in _miss["fix"] and "/r" in _miss["fix"] and "mouse" in _miss["fix"],
   _miss["fix"])
ck("present references are not a defect",
   P.build_state(_k, "ok", prefix="/e", refs="present") is None)
ck("with no --references it is UNKNOWN and not auto-fixable",
   P.build_state(_k, "ok", prefix="/e", refs="unknown")["kind"] == "refs_unknown")
ck("an unknown reference state is not silently repaired",
   P.build_state(_k, "ok", prefix="/e", refs="unknown")["fixable"] is False)
ck("a missing ENVIRONMENT still takes precedence over a missing reference",
   P.build_state(_k, "missing", prefix="/e", refs="missing")["kind"] == "env_missing")
import inspect as _insp                                                        # noqa: E402
ck("and --build knows how to fetch, not only install",
   "refs.fetch(" in _insp.getsource(_cli._plan), "plan --build cannot fetch")

print("\na reference with no organism is still a reference the plan must see")
# `reference_organisms()` is EMPTY for a plugin whose references carry no organism - a prior
# fetched per-organism at run time. Gating the reference check on that set skipped the whole
# check, so a plugin's freshly declared references were invisible to the plan that was supposed
# to report them. Measured on PBS 682089.
from scprofile import kernels as _K                                            # noqa: E402
_ks = _K.discover(str(Path(__file__).resolve().parents[1] / "kernels"))
_orgless = [n for n, k in _ks.items() if k.references() and not k.reference_organisms()]
ck("at least one shipped plugin declares organism-less references",
   bool(_orgless), "nothing exercises this path")
ck("and the plan gates on `references()`, not on `reference_organisms()`",
   "if k.references():" in _insp.getsource(_cli._plan),
   "the gate still skips organism-less references")
for _n in _orgless:
    ck(f"{_n}'s references survive organism filtering",
       len(_ks[_n].references("mouse")) == len(_ks[_n].references()),
       f"{len(_ks[_n].references('mouse'))} of {len(_ks[_n].references())} survive")

print("\n" + ("the report holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
