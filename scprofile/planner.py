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

#: HOW BADLY A DESIGN HAS TO FAIL BEFORE A PLUGIN IS DROPPED.
#:
#: A plan's default answer is RUN. Skipping is reserved for a design that CANNOT express the
#: question at all, and everything short of that runs with a caveat attached. The line is drawn
#: here because the alternative was measured and it was useless: a planner that skips on every
#: imperfection tells a user with a real, slightly-imbalanced experiment that their data cannot be
#: analysed, which is both wrong and the opposite of what they installed the tool for.
#:
#: TRULY UNSUPPORTED - skip, because no analysis exists:
#:   - the factor has ONE level. There is no contrast; the question cannot be phrased.
#:   - every arm has n=1. A differential test over singletons has no within-group variance to
#:     estimate, so the number it returns is not an estimate of anything.
#:
#: A CAVEAT, NOT A SKIP - run, and say so in the result:
#:   - one arm of several is a singleton while others are replicated.
#:   - two factors are confounded, wholly or partly. The effect is real and its ATTRIBUTION is
#:     ambiguous, which is a statement to carry with the result, not a reason to withhold it.
#:   - the groups are unbalanced.
#:   - an upstream constraint limits what the embedding may support.
MIN_LEVELS_FOR_A_CONTRAST = 2
MIN_REPLICATES_SOMEWHERE = 2

#: The rungs, worst to best. `full` means the richest question the plugin can answer.
RUNGS = ("minimal", "reduced", "full")


class Verdict:
    """One plugin's place in the plan, with the evidence for it."""

    def __init__(self, plugin, verdict, why, *, rung=None, why_not_higher=None,
                 units=None, searched=None, evidence=None, readiness=None):
        self.plugin, self.verdict, self.why = plugin, verdict, list(why or [])
        #: What stands between this installation and running it. None means ready. This is NOT
        #: the verdict: a plugin can be RUN (full) on the project and still need its wrapper.
        self.readiness = readiness
        self.rung, self.why_not_higher = rung, why_not_higher
        self.units = list(units) if units else None
        self.searched = list(searched or [])
        self.evidence = dict(evidence or {})
        #: Things true of this run that a reader must be told, and that are NOT reasons to
        #: withhold it: an imbalance, a confound, a constraint from upstream.
        self.caveats = []
        #: The concrete settings this plugin should run with, from `settings_for`.
        self.settings = {}

    def as_dict(self):
        return {"plugin": self.plugin, "verdict": self.verdict, "why": self.why,
                "readiness": self.readiness, "caveats": self.caveats,
                "settings": self.settings,
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
    # A REFERENCE THAT HAS NOT BEEN DOWNLOADED IS A FACT ABOUT THIS INSTALLATION. It was reported
    # as BLOCKED - the same word as "your data does not contain spliced counts" - which tells a
    # new user their dataset cannot support the method when the truth is that one command fixes
    # it. That is exactly the conflation the readiness axis exists to prevent, one field over.
    #
    # An organism the plugin has NO reference for stays BLOCKED, and correctly: there is nothing
    # to download, and that IS a fact about the project.
    "refs_missing": {"fixable": True,
                     "why": "its reference data has not been downloaded here",
                     "fix": "scprofile fetch {name} --to {refdir} --organism {organism}"},
    "refs_unknown": {"fixable": False,
                     "why": "no --references was given, so nowhere was checked for them",
                     "fix": "pass --references <dir>"},
}


def build_state(k, state, *, prefix=None, refs=None, refdir=None, organism=None):
    """The plugin's READINESS in this installation, or None if it is ready. NEVER A VERDICT.

    READINESS IS A SECOND AXIS, NOT A BLOCKER, and collapsing it into the verdict was a design
    error with a real cost: a plan run on a healthy project reported seven of nine plugins BLOCKED
    because their wrappers had not been written here, in the same column and the same word as
    "your data is missing". A user installing this tool and running the planner would conclude
    their dataset could not be analysed, when every one of those plugins would run on it.

    So a plugin now gets BOTH: what it would do ON THIS PROJECT (the verdict, from data and
    design alone) and what stands between here and running it (this). The plan leads with the
    first, because that is the question the user asked, and reports the second as work to be done
    - most of it by `--build`.
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
    # THE ENVIRONMENT FIRST, then references. Both can be missing at once and readiness is one
    # answer; the environment is the prerequisite for running at all, and `--build` re-derives the
    # plan after repairing, so the second pass reports what the first one fixed its way past.
    if not kind and refs == "missing":
        kind = "refs_missing"
    elif not kind and refs == "unknown":
        kind = "refs_unknown"
    if not kind:
        return None
    d = BUILD_DEFECTS[kind]
    return {"kind": kind, "fixable": d["fixable"], "why": d["why"],
            "fix": d["fix"].format(name=k.name, prefix=prefix or "<dir>",
                                   refdir=refdir or "<dir>", organism=organism or "<organism>")}


def fixable_builds(verdicts):
    """The plugins `--build` can repair, in plan order. Nothing else is ever triggered."""
    return [(v.plugin, v.readiness) for v in verdicts
            if (v.readiness or {}).get("fixable")]


def ready_count(verdicts):
    """(ready, needing work) - the headline a user actually wants from a plan."""
    ready = [v for v in verdicts if not v.readiness]
    return ready, [v for v in verdicts if v.readiness]


def confounding(facts):
    """Factor pairs that partition the samples the same way, wholly or partly.

    A CAVEAT, NEVER A SKIP. Two factors that split the cohort identically cannot have their
    effects told apart - but the effect is still real and still worth estimating; what is
    ambiguous is which name to put on it. That belongs in the result, beside the number, not in a
    decision to withhold the number.

    Returns [{"pair": [a, b], "agreement": 0..1, "note": str}], strongest first.
    """
    out, fs = [], facts.get("factors", {})
    names = sorted(fs)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            amap = {s: lv for lv, ss in fs[a]["levels"].items() for s in ss}
            bmap = {s: lv for lv, ss in fs[b]["levels"].items() for s in ss}
            shared = sorted(set(amap) & set(bmap))
            if len(shared) < 2:
                continue
            # How well does knowing a's level determine b's? Perfect determination in either
            # direction is complete confounding.
            pairs = {}
            for s in shared:
                pairs.setdefault(amap[s], set()).add(bmap[s])
            agree = sum(1 for lv, bs in pairs.items() if len(bs) == 1) / max(len(pairs), 1)
            if agree >= 0.999:
                out.append({"pair": [a, b], "agreement": 1.0,
                            "note": f"{a!r} and {b!r} are COMPLETELY confounded: every level of "
                                    f"{a!r} has exactly one level of {b!r}. Any effect estimated "
                                    f"for one is equally an effect of the other. Run it; attribute "
                                    f"it carefully."})
            elif agree >= 0.5:
                out.append({"pair": [a, b], "agreement": round(agree, 3),
                            "note": f"{a!r} and {b!r} are PARTLY confounded ({agree:.0%} of "
                                    f"{a!r}'s levels map to a single {b!r} level). The contrast is "
                                    f"estimable; its attribution is weakened."})
    return sorted(out, key=lambda d: -d["agreement"])


def settings_for(k, *, keys, facts, references=None, cores=None):
    """The SETTINGS this plugin should run with, at the highest capacity the project supports.

    A plan that says "run liana" and not "over these 10 samples, on this layer, with this label
    column" has not planned anything - the user still has to work out every flag, and a plugin run
    with a default it should not have used produces a result nobody can tell from a correct one.

    Everything here is DERIVED from the object and the design. No default is invented for a key
    that was not detected; a key that is absent is absent, and the plugin's own guard decides.
    """
    # ONLY WHAT THIS PLUGIN CONSUMES. Listing every detected key against every plugin said that
    # `cellcycle` would run on `X_scanvi` and `batch`, which it never reads - a settings block
    # that names an input the plugin ignores is not documentation, it is a claim about behaviour
    # that is false, and the reader has no way to tell the used from the padding.
    declared = " ".join(sum((list(getattr(k, attr, None) or [])
                             for attr in ("needs_obs", "needs_obsm", "needs_layers", "sees")),
                            []))
    s = {}
    for role, tokens in (("label", ("{label}", "label")),
                         ("sample", ("{sample}", "sample")),
                         ("batch", ("{batch}", "batch")),
                         ("compartment", ("{compartment}", "compartment")),
                         ("embedding", ("{embedding}", "embedding")),
                         ("counts_layer", ("{counts}", "counts")),
                         ("lognorm_layer", ("{lognorm}", "lognorm"))):
        if not keys.get(role):
            continue
        used = any(tok in declared for tok in tokens)
        # A per-unit plugin uses the unit key whether or not it names it in `needs`, and a
        # design-aware one uses the sample key to join the design table.
        if role == "sample" and (k.per_unit or getattr(k, "needs_design", False)):
            used = True
        if used:
            s[role] = keys[role]
    if k.per_unit:
        units = sorted(facts.get("units") or [])
        s["per_unit"] = {"key": k.per_unit, "n": len(units),
                         "units": units,
                         "mode": "per unit" if units else "POOLED (no unit key found)"}
    s.update(decisions_for(k, facts))
    if getattr(k, "reference_organisms", lambda: set())():
        s["references"] = {"organism": (keys.get("organism") or None),
                           "declared_for": sorted(k.reference_organisms()),
                           "dir": references}
    if cores:
        want = int((getattr(k, "executor", None) or {}).get("cores", 1) or 1)
        s["cores"] = min(int(cores), want)
    return s


def decisions_for(kernel, facts):
    """The decisions the PLAN makes for a kernel, as the dict the RUN is handed verbatim.

    ONE function, called by the planner to record and render and by the runner to inject,
    because THE PLAN AND THE RUN MUST AGREE BY CONSTRUCTION - the same rule `available()` states
    for capabilities, applied to decisions. A decision that exists only in the plan is a
    decision the analysis did not make.

    It was: `contrast` was computed here, rendered into the plan HTML and into the plan's text
    output, and then passed to nothing at all. The run built its parameters from the command
    line alone, so a study whose interaction the plan had identified, justified and PRINTED was
    tested for main effects, and the report said so plainly without anything registering that
    the two documents disagreed. A reader had the plan's formula on one page and the run's terms
    on another and no reason to compare them.

    Returns a plain dict so a new decision is added by returning one more key, and the runner
    delivers it without being changed.

    A DECISION THE PLUGIN CANNOT RECEIVE IS NOT A DECISION. Every key returned here must be a
    capability the kernel declares in `inject`, because that is the channel it arrives by - and
    the first version of this checked nothing, so the plan printed a contrast, the run delivered
    it, and both plugins refused the whole run with "no such parameter ['contrast']" three
    hours into a queue. Deciding something for a plugin that has not said it can be given it is
    a decision made about a plugin rather than for one.
    """
    d = {}
    if not (getattr(kernel, "needs_design", False) and facts.get("has_design")):
        return d
    # MAXIMUM CAPACITY: the richest contrast the design permits, not the safest one.
    pairs = facts.get("crossed_pairs") or []
    if pairs:
        x, y = pairs[0]
        d["contrast"] = {"kind": "interaction", "terms": [x, y],
                         "formula": f"~ {x} + {y} + {x}:{y}",
                         "why": f"{x} and {y} are crossed with replication in every cell, so "
                                f"the interaction is estimable - and it is usually the "
                                f"question the study was designed to ask."}
        if len(pairs) > 1:
            d["contrast"]["other_crossed_pairs"] = pairs[1:]
    elif facts.get("testable"):
        d["contrast"] = {"kind": "main effects", "terms": list(facts["testable"]),
                         "formula": "~ " + " + ".join(facts["testable"]),
                         "why": "no two factors are crossed with replication in every cell"}
    takes = (set(getattr(kernel, "injects_required", []) or [])
             | set(getattr(kernel, "injects_optional", []) or []))
    return {k: v for k, v in d.items() if k in takes}


def order_of_runs(names, available):
    """Waves honouring the capability graph, so a plan says WHEN as well as what.

    A plugin that reads another's output has to run after it, and a plan that lists both without
    saying so leaves the user to discover the ordering from a failure. Plugins in one wave are
    independent BY THE GRAPH - not merely convenient to group.
    """
    from .kernels import producer_edges
    # DECLARED EDGES PLUS CAPABILITY EDGES. `needs_kernels` is empty for every shipped plugin and
    # should be - a plugin names a capability, not a peer - so honouring it alone gave the
    # scheduler nothing to order and made every run a single wave.
    edges = producer_edges({n: available[n] for n in names if available.get(n)})
    remaining, done, waves, guard = sorted(names), set(), [], 0
    while remaining:
        guard += 1
        if guard > len(names) + 2:
            waves.append(list(remaining))          # a cycle: report it rather than looping
            break
        ready = [n for n in remaining
                 if all(d in done or d not in names
                        for d in (list(getattr(available.get(n), "needs_kernels", []) or [])
                                  + edges.get(n, [])))]
        if not ready:
            waves.append(list(remaining))
            break
        waves.append(ready)
        done.update(ready)
        remaining = [n for n in remaining if n not in done]
    return waves


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

    # ---- a SKIP only where NO ANALYSIS EXISTS ------------------------------------------------
    # Not "this is imperfect". Not "this is confounded". Not "one arm is small". Those are
    # caveats and the run proceeds. A skip means the design cannot phrase the question at all.
    caveats = []
    if k.needs_design and facts.get("has_design"):
        fs = facts["factors"]
        usable = [n for n, v in fs.items()
                  if v["n_levels"] >= MIN_LEVELS_FOR_A_CONTRAST
                  and max((len(s) for s in v["levels"].values()), default=0)
                  >= MIN_REPLICATES_SOMEWHERE]
        if not usable:
            detail = [f"{n}: {v['n_levels']} level(s), largest arm n="
                      f"{max((len(s) for s in v['levels'].values()), default=0)}"
                      for n, v in sorted(fs.items())]
            return Verdict(k.name, SKIP,
                           ["no factor can express a contrast at all - every one has a single "
                            "level, or no level with two samples in it.",
                            "This is the only kind of design problem that stops a run. An "
                            "imbalance or a confound would be carried as a caveat instead."]
                           + detail,
                           evidence={"factors": fs})
        # Everything below runs. It is recorded, not withheld.
        for n in sorted(facts.get("unreplicated", [])):
            v = fs[n]
            caveats.append(f"{n!r} has a singleton arm ({', '.join(v['singleton_levels'])}); "
                           f"that arm contributes no within-group variance.")
        for c in confounding(facts):
            caveats.append(c["note"])
        if not facts.get("crossed_pairs") and len(facts.get("testable", [])) > 1:
            caveats.append("no two factors are crossed with replication in every cell, so main "
                           "effects only - an interaction is not estimable here.")
    if constraint:
        caveats.append("An upstream constraint on use applies to this object and is reproduced "
                       "in the report; a claim it forbids must be refused by the plugin, not by "
                       "this plan.")

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
    v = Verdict(k.name, RUN, ["every declared input is present"], rung=rung,
                why_not_higher=why_not,
                units=(sorted(facts.get("units") or []) if k.per_unit else None),
                searched=searched,
                evidence={"constraint_on_use": constraint} if constraint else {})
    v.caveats = caveats
    return v


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
