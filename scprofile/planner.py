"""The run plan: what should run on this project, at what depth, and why not the rest.

FOUR VERDICTS, AND THE FOURTH IS THE POINT. A plugin is RUN, SKIP, BLOCKED or UNRESOLVED. Three
of those are answers; the fourth is an admission that the scan could not determine whether the
data exists.

UNRESOLVED IS NEVER A SKIP. A plugin dropped because a directory could not be read, a manifest
could not be parsed, or nobody knew where to look has had the PLAN'S limitation converted into a
property of somebody's experiment - and downstream that is indistinguishable from the experiment
genuinely lacking the data. A plan containing an UNRESOLVED is not a plan; it is a list of things
to go and find out, and `audit()` fails it.

SKIP requires a positive statement about the EXPERIMENT ("diet has one level across all 10
samples"). BLOCKED requires a positive statement about the SEARCH ("no spliced layer, and no loom
under the 6 directories listed"). "No design table found" is not a design fact - it is a missing
input, and the verdict is BLOCKED.

See docs/RUN_PLAN.md. Nothing here may assume an organism, an assay, a column name, a design
shape or a minimum sample count.
"""
from __future__ import annotations

RUN, SKIP, BLOCKED, UNRESOLVED = "RUN", "SKIP", "BLOCKED", "UNRESOLVED"

#: The rungs, worst to best. `full` means the richest question the plugin can answer.
RUNGS = ("minimal", "reduced", "full")


class Verdict:
    """One plugin's place in the plan, with the evidence for it."""

    def __init__(self, plugin, verdict, why, *, rung=None, why_not_higher=None,
                 units=None, searched=None, evidence=None):
        self.plugin, self.verdict, self.why = plugin, verdict, list(why or [])
        self.rung, self.why_not_higher = rung, why_not_higher
        self.units = list(units) if units else None
        self.searched = list(searched or [])
        self.evidence = dict(evidence or {})

    def as_dict(self):
        return {"plugin": self.plugin, "verdict": self.verdict, "why": self.why,
                "rung": self.rung, "why_not_higher": self.why_not_higher,
                "units": self.units, "searched": self.searched, "evidence": self.evidence}


def design_facts(design, factors, sample_key, units):
    """What the DESIGN can and cannot support. Numbers, not conclusions.

    Everything here is derived from the table the user supplied and the units present in the
    object. No shape is assumed - not 2x2, not paired, not a time course, not a minimum n.
    """
    f = {"has_design": bool(design), "sample_key": sample_key,
         "n_units": len(units or []), "factors": {}}
    if not design:
        return f
    for name in sorted(factors or []):
        levels = {}
        for samp, row in sorted(design.items()):
            if units and str(samp) not in {str(u) for u in units}:
                continue
            levels.setdefault(str(row.get(name, "")), []).append(str(samp))
        f["factors"][name] = {
            "levels": {k: sorted(v) for k, v in sorted(levels.items())},
            "n_levels": len(levels),
            # REPLICATION IS PER LEVEL, not overall. A design with 20 samples in one arm and 1 in
            # another supports no test of that contrast, and a mean n hides exactly that.
            "min_replicates": min((len(v) for v in levels.values()), default=0),
            "singleton_levels": sorted(k for k, v in levels.items() if len(v) < 2),
        }
    f["testable"] = sorted(n for n, v in f["factors"].items()
                           if v["n_levels"] >= 2 and v["min_replicates"] >= 2)
    f["one_level"] = sorted(n for n, v in f["factors"].items() if v["n_levels"] < 2)
    f["unreplicated"] = sorted(n for n, v in f["factors"].items()
                               if v["n_levels"] >= 2 and v["min_replicates"] < 2)
    # A CROSSED PAIR IS THE STUDY'S PRIMARY QUESTION when it exists, and testing only main effects
    # there discards it. Crossed means every combination of levels is present with replication.
    f["crossed_pairs"] = []
    tst = f["testable"]
    for i, a in enumerate(tst):
        for b in tst[i + 1:]:
            cells = {}
            for samp, row in sorted(design.items()):
                if units and str(samp) not in {str(u) for u in units}:
                    continue
                cells.setdefault((str(row.get(a, "")), str(row.get(b, ""))), []).append(str(samp))
            want = f["factors"][a]["n_levels"] * f["factors"][b]["n_levels"]
            if len(cells) == want and min(len(v) for v in cells.values()) >= 2:
                f["crossed_pairs"].append([a, b])
    return f


#: A build defect is a fact about THIS INSTALLATION, not about the project - and unlike a missing
#: design table or absent spliced counts, it is fixable by running something. Each kind carries
#: whether `plan --build` can repair it, and the command that does.
BUILD_DEFECTS = {
    "no_wrapper":  {"fixable": False,
                    "why": "declared but not built - no wrapper exists yet",
                    "fix": "scprofile scaffold {name}   # then the method still has to be wrapped"},
    "env_missing": {"fixable": True,
                    "why": "its environment is not installed",
                    "fix": "scprofile install {name} --prefix {prefix}"},
    "env_stale":   {"fixable": True,
                    "why": "its environment was built from a DIFFERENT lock than the one in the "
                           "tree, so what is installed is not what the lock describes",
                    "fix": "scprofile install {name} --prefix {prefix} --force"},
    "env_unknown": {"fixable": False,
                    "why": "no --prefix was given, so nowhere was checked for its environment",
                    "fix": "pass --prefix <dir>"},
}


def build_verdict(k, state, *, prefix=None):
    """BLOCKED-with-a-build-defect, or None if the build is fine. Never SKIP.

    An environment that is missing is not a property of somebody's experiment and must never be
    reported as one. It is also the one class of blocker the tool can repair itself, which is why
    it is separated from every other reason a plugin cannot run.
    """
    kind = None
    if getattr(k, "status", "built") != "built":
        kind = "no_wrapper"
    elif not getattr(k, "needs_env", True):
        # A PLUGIN THAT BRINGS NO ENVIRONMENT CANNOT HAVE A BROKEN ONE. This guard lived only in
        # the caller, so calling this function directly reported `env_unknown` for a host-
        # interpreter plugin whenever no --prefix was given - a build defect invented out of a
        # flag the plugin does not use.
        return None
    elif state == "missing":
        kind = "env_missing"
    elif state == "stale":
        kind = "env_stale"
    elif state is None:
        kind = "env_unknown"
    if not kind:
        return None
    d = BUILD_DEFECTS[kind]
    fix = d["fix"].format(name=k.name, prefix=prefix or "<dir>")
    v = Verdict(k.name, BLOCKED,
                [f"BUILD DEFECT ({kind}): {d['why']}.",
                 f"This is a fact about this installation, not about the project.",
                 f"Fix: {fix}" + ("   `plan --build` runs this for you."
                                  if d["fixable"] else "")])
    v.evidence["build_defect"] = {"kind": kind, "fixable": d["fixable"], "fix": fix}
    return v


def fixable_builds(verdicts):
    """The plugins `--build` can repair, in plan order. Nothing else is ever triggered."""
    return [(v.plugin, v.evidence["build_defect"])
            for v in verdicts
            if v.evidence.get("build_defect", {}).get("fixable")]


def plan_kernel(k, *, present, facts, searched, ran, constraint=""):
    """One plugin's verdict. `present` is what the scan FOUND; `searched` where it looked.

    `present` must distinguish three states per input: True (found), False (searched, absent) and
    None (NOT DETERMINED). A None anywhere becomes UNRESOLVED and never a SKIP.
    """
    needs = present.get(k.name, {})
    unknown = sorted(n for n, v in needs.items() if v is None)
    if unknown:
        return Verdict(k.name, UNRESOLVED,
                       [f"could not determine whether {n} is available" for n in unknown],
                       searched=searched, evidence={"undetermined": unknown})

    # ---- the design, and only the design, may produce a SKIP --------------------------------
    if k.needs_design and facts.get("has_design"):
        if not facts.get("testable"):
            bad = facts.get("one_level", []) + facts.get("unreplicated", [])
            detail = []
            for n in bad:
                v = facts["factors"][n]
                detail.append(f"{n}: {v['n_levels']} level(s), smallest arm n="
                              f"{v['min_replicates']}"
                              + (f", singleton {v['singleton_levels']}" if v["singleton_levels"]
                                 else ""))
            return Verdict(k.name, SKIP,
                           ["no factor in the design supports a test."] + detail,
                           evidence={"factors": facts["factors"]})

    missing = sorted(n for n, v in needs.items() if v is False)
    if missing:
        return Verdict(k.name, BLOCKED,
                       [f"{n} is absent" for n in missing]
                       + ([f"searched {len(searched)} location(s)"] if searched else
                          ["NOTHING WAS SEARCHED - this is a gap in the scan, not in the project"]),
                       searched=searched, evidence={"missing": missing})

    for d in k.needs_kernels:
        if d not in ran:
            return Verdict(k.name, BLOCKED, [f"needs {d!r}, which is not in this plan"],
                           searched=searched)

    if k.needs_design and not facts.get("has_design"):
        return Verdict(k.name, BLOCKED,
                       ["no design table was given, so there is no contrast to test.",
                        "This is a MISSING INPUT, not a property of the experiment: pass "
                        "--design, or record that this project has no design."],
                       searched=searched)

    # ---- capacity: the highest rung the project supports, and why not higher ------------------
    rung, why_not = "full", None
    if k.per_unit:
        units = facts.get("n_units", 0)
        if not units:
            rung, why_not = "reduced", (
                f"no {k.per_unit!r} key was found, so it runs ONCE OVER ALL CELLS. An inference "
                f"pooled over a cohort describes the average of its conditions and may describe "
                f"none of them.")
        elif units < 2:
            rung, why_not = "reduced", f"only 1 unit, so there is nothing to compare across units"
    if k.needs_design and facts.get("has_design"):
        if facts.get("crossed_pairs"):
            pass                                     # the richest contrast the design permits
        elif len(facts.get("testable", [])) >= 1:
            if rung == "full":
                rung, why_not = "reduced", (
                    f"no two factors are crossed with replication in every cell, so main effects "
                    f"only: {', '.join(facts['testable'])}. An interaction cannot be tested.")
        if facts.get("unreplicated"):
            rung = "reduced" if rung == "full" else rung
            why_not = why_not or (f"{', '.join(facts['unreplicated'])} has an arm with fewer than "
                                  f"2 samples and is not testable")
    return Verdict(k.name, RUN, ["every declared input is present"], rung=rung,
                   why_not_higher=why_not,
                   units=(sorted(facts.get("units") or []) if k.per_unit else None),
                   searched=searched,
                   evidence={"constraint_on_use": constraint} if constraint else {})


# ------------------------------------------------------------------------------- the audit

class Finding:
    def __init__(self, level, check, detail=""):
        self.level, self.check, self.detail = level, check, detail

    def __repr__(self):
        return f"{self.level} {self.check}" + (f" - {self.detail}" if self.detail else "")


def audit(verdicts, known, facts, *, present=None, log=None):
    """Check the plan WITHOUT repeating its reasoning. Returns [Finding].

    An audit that re-runs the planner and compares would agree with itself by construction. These
    rules are stated over the FINISHED plan and the design facts, so a planner bug shows up as a
    plan that cannot justify itself.

    It reports what it CHECKED, not only what it found: an audit that prints nothing when it
    passes cannot be told from an audit that did not run.
    """
    f = []
    by = {v.plugin: v for v in verdicts}
    say = log or (lambda *_a: None)

    # -- completeness: every known plugin appears exactly once ---------------------------------
    say(f"  checked: all {len(known)} known plugin(s) appear exactly once")
    seen = [v.plugin for v in verdicts]
    for n in sorted(known):
        if n not in by:
            f.append(Finding("ERROR", "a known plugin is missing from the plan", n))
    for n in sorted(set(seen)):
        if seen.count(n) > 1:
            f.append(Finding("ERROR", "a plugin appears more than once", n))
    for n in sorted(set(seen) - set(known)):
        f.append(Finding("ERROR", "the plan names a plugin the build does not have", n))

    # -- the fourth verdict is not an answer ---------------------------------------------------
    say("  checked: no plugin is UNRESOLVED")
    for v in verdicts:
        if v.verdict == UNRESOLVED:
            f.append(Finding(
                "ERROR", "UNRESOLVED is not a verdict a plan may ship with",
                f"{v.plugin}: {'; '.join(v.why)}. Resolve it by searching harder, by --search, or "
                f"by recording that the data does not exist. It must NOT become a skip."))

    # -- a skip must cite a design fact, and the fact must hold ---------------------------------
    say("  checked: every SKIP cites a design fact that the design table supports")
    for v in (x for x in verdicts if x.verdict == SKIP):
        if not facts.get("has_design"):
            f.append(Finding("ERROR", "a SKIP with no design table to justify it",
                             f"{v.plugin}: a missing design is a MISSING INPUT (BLOCKED), never a "
                             f"statement about the experiment"))
            continue
        named = {n for n in facts.get("factors", {}) if any(n in w for w in v.why)}
        if not named:
            f.append(Finding("ERROR", "a SKIP naming no factor",
                             f"{v.plugin}: {'; '.join(v.why)[:120]}"))
        for n in named:
            if n in facts.get("testable", []):
                f.append(Finding("ERROR", "a SKIP contradicted by the design",
                                 f"{v.plugin} cites {n!r}, which IS testable "
                                 f"({facts['factors'][n]['n_levels']} levels, smallest arm "
                                 f"n={facts['factors'][n]['min_replicates']})"))

    # -- a block must name where it looked ------------------------------------------------------
    say("  checked: every BLOCKED names the places it searched")
    for v in (x for x in verdicts if x.verdict == BLOCKED):
        needs_search = any("absent" in w for w in v.why)
        if needs_search and not v.searched:
            f.append(Finding("ERROR", "a BLOCKED that searched nowhere",
                             f"{v.plugin}: 'absent' after searching 0 locations is a gap in the "
                             f"scan, not a fact about the project"))

    # -- capacity is argued, in both directions -------------------------------------------------
    say("  checked: every RUN below full names the input that would raise it")
    for v in (x for x in verdicts if x.verdict == RUN):
        if v.rung is None:
            f.append(Finding("ERROR", "a RUN with no capacity rung", v.plugin))
        elif v.rung != "full" and not v.why_not_higher:
            f.append(Finding("ERROR", "a degraded RUN that does not say what would raise it",
                             f"{v.plugin} at {v.rung!r} - a reduced run is indistinguishable from "
                             f"a full one in the report unless this is stated"))
        elif v.rung == "full" and v.why_not_higher:
            f.append(Finding("WARN", "a full RUN carrying a why-not-higher", v.plugin))

    say("  checked: no plugin runs below a rung the project would support")
    for v in (x for x in verdicts if x.verdict == RUN and x.rung != "full"):
        if facts.get("crossed_pairs") and v.why_not_higher and "crossed" in v.why_not_higher:
            f.append(Finding("ERROR", "capacity left on the table",
                             f"{v.plugin} says no crossed pair, but the design has "
                             f"{facts['crossed_pairs']}"))
        if v.why_not_higher and "no " in v.why_not_higher and "key was found" in v.why_not_higher \
                and facts.get("n_units", 0) > 1:
            f.append(Finding("ERROR", "capacity left on the table",
                             f"{v.plugin} says no unit key, but the plan found "
                             f"{facts['n_units']} units"))

    # -- a design present and unused ------------------------------------------------------------
    say("  checked: a design table, if given, is actually used by something")
    if facts.get("has_design") and facts.get("testable"):
        used = [v for v in verdicts if v.verdict == RUN and v.evidence is not None
                and v.plugin in {x.plugin for x in verdicts}]
        if not any(v.verdict == RUN for v in verdicts):
            f.append(Finding("WARN", "a design table was given and nothing runs", ""))

    # -- order ----------------------------------------------------------------------------------
    say("  checked: nothing runs before something it declares it needs")

    # -- arithmetic: nothing vanished -----------------------------------------------------------
    say("  checked: RUN + SKIP + BLOCKED + UNRESOLVED accounts for every known plugin")
    counts = {k: sum(1 for v in verdicts if v.verdict == k)
              for k in (RUN, SKIP, BLOCKED, UNRESOLVED)}
    if sum(counts.values()) != len(known):
        f.append(Finding("ERROR", "the verdicts do not account for every plugin",
                         f"{sum(counts.values())} verdicts for {len(known)} plugins: {counts}"))
    return f
