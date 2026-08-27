"""When something downstream fails, work out WHICH LAYER is wrong and send it there.

THE LOOP THIS COMPLETES

    declare  ->  build  ->  plan  ->  run  ->  report
       ^           ^         ^          |         |
       |           |         +----------+         |   plan already triggers the builder
       |           +--------------------+         |   a run that fails on the ENVIRONMENT
       |                                          |    rebuilds it and retries, once
       +------------------------------------------+   output that contradicts the DECLARATION
                                                       is a defect for the maintainer, reported
                                                       as one - and so is a cost that contradicts
                                                       the declared memory model

A failure in a run has a cause in exactly one layer, and the layers have completely different
remedies. Reporting them all as "plugin X failed" makes the user read a traceback and guess.

    ENVIRONMENT   the pins do not resolve here, or resolved to something that no longer works.
                  REPAIRABLE AUTOMATICALLY: rebuild and try once more.
    DECLARATION   the plugin's own description of itself is not true of what it did. Nothing to
                  rebuild - a maintainer must change the declaration or the method.
    METHOD        the call itself failed on this data. Often not a defect at all: an analysis
                  that cannot be done on this object is a result.
    HOST          the contract was applied wrongly. Not the plugin's fault and not the user's.

WHY A RETRY IS ALWAYS REPORTED, NEVER SWALLOWED

If a plugin fails and then succeeds after a rebuild, the environment had DRIFTED - and that is a
finding about this installation that somebody needs, not a hiccup to hide. A loop that silently
retries until something works converts a real defect into an intermittent one, which is the
hardest kind to ever fix.
"""
from __future__ import annotations

import re

ENVIRONMENT, DECLARATION, METHOD, HOST = "environment", "declaration", "method", "host"

#: Signatures, most specific first. Each maps a failure to the LAYER that owns it, and says what
#: to do - never a guess, and never a traceback handed back to the user.
SIGNATURES = (
    # FIRST, because it is the one failure that is NOBODY'S plugin and NOBODY'S environment, and
    # the default classification sends the reader to exactly the wrong place. Measured on PBS
    # 683096: six instances refused because the tool directory moved mid-run, and every one was
    # reported as `[method] ... the plugin is the place to start`. The plugin was untouched; a
    # `git pull` was not.
    (r"THE TOOL CHANGED WHILE THIS RUN WAS IN PROGRESS", HOST, False,
     "the tool's own code changed while this run was in progress, so instances launched before "
     "that point ran different code from the ones after it. NOT a fault in the plugin, its "
     "environment or its declaration - do not debug any of them. The run refused rather than "
     "producing a result nobody could attribute to a version. Let a run finish, or kill it, "
     "before updating the checkout it is reading; the job template's snapshot removes the race "
     "entirely and this fires only when it is switched off."),
    (r"ModuleNotFoundError|No module named", ENVIRONMENT, True,
     "a package the plugin imports is not in its environment. Either the requirement does not "
     "name it or the environment was not built from the current requirement - and those have "
     "different remedies. CHECK THE DECLARATION FIRST: if the missing module is not named by "
     "this plugin's `requires`, a rebuild cannot add it, and what you are looking at is a "
     "dependency the wrapped tool needs and its own metadata does not declare. Three of those "
     "in one cycle: filelock behind pertpy, omnipath imported lazily inside decoupler's "
     "get_collectri, and forty-four R packages behind CellChat."),
    (r"ImportError|cannot import name|undefined symbol|GLIBC", ENVIRONMENT, True,
     "a package is present but not importable here - usually a binary built against something "
     "this machine does not have, or two pins that disagree."),
    (r"version .* is required|incompatible|but you have", ENVIRONMENT, True,
     "two pinned packages disagree about a third. The lock resolved once and does not now."),
    (r"got multiple values for keyword|unexpected keyword argument|takes no keyword", DECLARATION,
     False,
     "the wrapped tool's signature moved. The plugin calls it the way an older version wanted, "
     "and its selftest should have caught this before a run."),
    (r"has no attribute", DECLARATION, False,
     "the wrapped tool's API moved. The plugin uses a name that no longer exists there."),
    (r"out\.json|contract|manifest", HOST, False,
     "the output manifest could not be read or written. That is the contract, which is this "
     "host's code and not the plugin's."),
    (r"Singular matrix|LinAlgError|rank[- ]deficient|not full rank", METHOD, False,
     "the model matrix is not full rank: two or more terms are collinear on this design, so "
     "their coefficients are not identifiable and the fit inverted a singular matrix. Not a "
     "defect in the data or the tool - it is a property of the design table. A plugin that fits "
     "a model should check the rank first and say which terms are aliased, because "
     "`LinAlgError: Singular matrix` is a true statement about linear algebra and tells a user "
     "nothing about their experiment."),
    (r"MemoryError|Killed|OOM|out of memory", METHOD, False,
     "it ran out of memory. Not a defect: give it more, or fewer cells."),
    (r"timed out|TimeoutExpired", METHOD, False,
     "it exceeded the per-instance timeout. Raise --timeout, or the work is larger than the "
     "budget allowed."),
)


class Diagnosis:
    def __init__(self, layer, why, *, repairable=False, action="", evidence=""):
        self.layer, self.why = layer, why
        self.repairable, self.action, self.evidence = repairable, action, evidence

    def as_dict(self):
        return {"layer": self.layer, "why": self.why, "repairable": self.repairable,
                "action": self.action, "evidence": self.evidence[:400]}

    def __repr__(self):
        return f"<{self.layer}{' repairable' if self.repairable else ''}: {self.why[:60]}>"


def diagnose(name, error, *, prefix=None):
    """Which layer owns this failure, and what to do about it."""
    text = str(error)
    for pat, layer, repairable, why in SIGNATURES:
        if re.search(pat, text, re.I):
            action = ""
            if repairable:
                action = (f"scprofile install {name}"
                          + (f" --prefix {prefix}" if prefix else "")
                          + " --force")
            return Diagnosis(layer, why, repairable=repairable, action=action, evidence=text)
    # NO SIGNATURE MATCHED, and that is reported as such rather than guessed at. A wrong layer
    # sends somebody to the wrong file, which costs more than saying "I do not know".
    return Diagnosis(METHOD,
                     "no known failure signature matched, so the layer is not established. The "
                     "error is below; the plugin is the place to start.",
                     evidence=text)


def declaration_drift(kernel, payload):
    """What the plugin DID, against what it SAID it would. Every mismatch is an upstream defect.

    This is the `run -> declare` edge, and it is the cheapest one in the whole loop: the run has
    already happened and the declaration is right there. A plugin whose `produces` no longer
    matches what it emits has drifted, and the next person to read the declaration will believe
    it.
    """
    import fnmatch
    out = []
    raw = [str(x).strip() for x in (kernel.spec.get("produces") or [])]
    if not raw:
        return out

    # A `?` SUFFIX MARKS AN OUTPUT ONLY SOME RUNS PRODUCE, and a GLOB matches a name chosen at run
    # time. Neither was understood here, and both were already understood by `undeclared()` in
    # kernels.py - two functions asking the same question of the same declaration and disagreeing
    # about the answer. Measured on the one shipped plugin that uses either: `obsm[velocity_*]`
    # was reported TWICE on a correct run, once as a promise broken and once as an output
    # undeclared, and `obs[latent_time]` as a broken promise on every run not in dynamical mode.
    # A check that fires on correct behaviour is a check a maintainer learns to scroll past.
    #
    # THE GLOB IS ON THE NAME, NOT ON `slot[name]`, and that is not a detail: in fnmatch `[phase]`
    # is a CHARACTER CLASS, so matching the whole string makes `obs[phase]` match `obsp` and not
    # itself. `undeclared()` splits first for the same reason.
    def _split(item):
        t = item.rstrip("?").strip()
        if "[" in t and t.endswith("]"):
            slot, _, rest = t.partition("[")
            return slot.strip(), rest[:-1].strip()
        return "tables", t.split("/")[-1]

    declared = [_split(x) for x in raw]
    optional = {_split(x) for x in raw if x.endswith("?")}
    got = set()
    for slot in ("obs", "obsm", "layers", "objects"):
        for key in (payload.get(slot) or {}):
            got.add((slot, str(key)))
    for rel in (payload.get("tables") or []):
        got.add(("tables", str(rel).split("/")[-1]))

    def _shown(slot, name):
        return f"{slot}/{name}" if slot == "tables" else f"{slot}[{name}]"

    for slot, pat in sorted(set(declared)):
        if payload.get("status") in ("refused", "partial"):
            continue          # a refusal is allowed to produce nothing; it said why
        if (slot, pat) in optional:
            continue
        if any(g_slot == slot and fnmatch.fnmatchcase(g_name, pat) for g_slot, g_name in got):
            continue
        out.append(Diagnosis(
            DECLARATION,
            f"declares {_shown(slot, pat)!r} in `produces` and did not emit it. Either the method "
            f"stopped producing it or the declaration is stale; both mislead the next reader.",
            action=f"fix `produces` in the plugin, or the method"))
    for slot, name in sorted(got):
        if any(d_slot == slot and fnmatch.fnmatchcase(name, d_pat)
               for d_slot, d_pat in declared):
            continue
        out.append(Diagnosis(
            DECLARATION,
            f"emitted {_shown(slot, name)!r}, which it does not declare in `produces`. An "
            f"undeclared output is one no `cannot_show` covers and no documentation mentions.",
            action=f"add {_shown(slot, name)!r} to `produces`, with its limits"))
    return out


def figure_drift(kernel, payload):
    """What the plugin DREW, against what its `report` block said it would.

    The same edge as `declaration_drift` and for the same reason - the run has already happened
    and the declaration is right there - applied to the half of the contract that had no check at
    all. Seven of the nine shipped plugins emitted no figure and every gate passed, because
    nothing anywhere compared a page against what it was supposed to contain.

    A plugin that declares no block is not drifting; it has said nothing to drift from. That is a
    WARN at declaration time and is not repeated per run.
    """
    from .declare import report_figures

    out = []
    declared = report_figures(kernel.spec)
    if not declared:
        return out
    # REFUSED ONLY, and the difference from `declaration_drift` above is not an oversight. A
    # refusal produced nothing by design and said why. A PARTIAL run produced results, wrote a
    # page and drew figures - and `partial` is the ordinary status of a method that fitted on a
    # subset or scored below its own threshold, which is most real runs. Exempting it meant the
    # first real run of this check was silent on a plugin whose nine panels had all lost their
    # ids. A panel that genuinely cannot be drawn on some data is what `required: False` and
    # `when_absent` are for; the status is the wrong place to say it.
    if payload.get("status") == "refused":
        return out

    drew = {str(f.get("id") or "") for f in (payload.get("figures") or []) if isinstance(f, dict)}
    for d in declared:
        fid = str(d.get("id") or "")
        if fid in drew or not d.get("required", True):
            continue
        out.append(Diagnosis(
            DECLARATION,
            f"declares figure {fid!r} in `report.figures` as required and did not emit it. The "
            f"page states it as NOT PRODUCED, which tells a reader the run is incomplete; if the "
            f"panel is not always drawable, mark it optional and say when.",
            action=f"emit {fid!r}, or set required=False with a `when_absent` reason"))
    for fid in sorted(drew - {str(d.get("id") or "") for d in declared}):
        if not fid:
            continue
        out.append(Diagnosis(
            DECLARATION,
            f"emitted figure {fid!r}, which its `report` block does not declare. The page shows "
            f"it under 'drawn, and not declared', with nothing saying what it is for.",
            action=f"add {fid!r} to `report.figures` with its question, its source and whether it "
                   f"is a diagnostic or the result"))
    return out


def metric_drift(kernel, payload):
    """What the plugin MEASURED per unit, against what `report.unit_metrics` said it would.

    The twin of `figure_drift`, on the half of the page a per-unit plugin cannot draw for
    itself. A declared metric that never arrives leaves the across-unit comparison short a
    column with nothing saying so, and an undeclared one arrives with no question attached -
    a number on a shared axis whose meaning a reader has to guess.

    A refusal produced nothing by design; a PARTIAL run produced results and a page, and is
    held to the declaration for the same reason it is for figures.
    """
    out = []
    declared = [d for d in ((kernel.report_spec or {}).get("unit_metrics") or [])
                if isinstance(d, dict)]
    if payload.get("status") == "refused":
        return out
    ids = {str(d.get("id") or "") for d in declared} - {""}
    got = set()
    for u in (payload.get("units") or [{}]):
        got |= {str(k) for k in (u.get("metrics") or {})}
    if not (payload.get("units") or []):
        got |= {str(k) for k in (payload.get("metrics") or {})}
    # THE UNDECLARED DIRECTION IS CHECKED EVEN WHEN NOTHING IS DECLARED. Returning early on an
    # empty declaration meant a plugin that is not per-unit could record metrics that nothing
    # renders and nothing reports - which is how two of them were added to a plugin whose page
    # has no across-unit section, and passed every check.
    for mid in sorted(ids - got):
        out.append(Diagnosis(
            DECLARATION,
            f"declares unit metric {mid!r} and recorded it for no unit, so the across-unit "
            f"comparison is missing the column it promised and the page does not say why.",
            action=f"call ctx.metric({mid!r}, value) on every unit, or remove it from "
                   f"`report.unit_metrics`"))
    for mid in sorted(got - ids):
        out.append(Diagnosis(
            DECLARATION,
            f"recorded unit metric {mid!r}, which `report.unit_metrics` does not declare, so it "
            f"reaches a shared axis with no question attached.",
            action=f"add {mid!r} to `report.unit_metrics` with the question it answers"))
    return out


def sentinel_as_population(out_dir, payload, sentinels):
    """Did this plugin report an annotator's refusal as though it were a cell type?

    The contract says a sentinel stays in the object and leaves the STATISTICS - never a
    population, never a denominator. Until now that was ASSERTED, in a caveat the host printed
    and had no way to make true, and the first plugin supplied from outside this repository
    shipped a `separation_by_label.csv` whose worst-scoring population was `UNRESOLVED`.

    A rule the host states and does not check is a rule that holds until somebody writes a
    plugin. So it is checked, on the one thing the host can actually read: the FIRST COLUMN of
    each emitted table, which is where a per-group result puts its group. Stdlib `csv`, first
    column only, first hit per table - the table is not scanned for content, it is checked for
    one specific mistake.

    Not fatal. Reported as a DECLARATION defect, the layer whose remedy is "a maintainer changes
    the plugin or its method".
    """
    import csv
    from pathlib import Path

    sent = {str(s) for s in (sentinels or ()) if s}
    if not sent:
        return []
    out = []
    for rel in (payload.get("tables") or []):
        f = Path(out_dir) / str(rel)
        if not f.exists():
            continue
        try:
            with open(f, newline="", encoding="utf-8", errors="replace") as fh:
                rows = csv.reader(fh)
                next(rows, None)                 # the header names the column, not a group
                hit = next((r[0] for r in rows if r and r[0] in sent), None)
        except OSError:
            continue
        if hit:
            out.append(Diagnosis(
                DECLARATION,
                f"reported the annotator sentinel {hit!r} as a group in {f.name}. A sentinel is "
                f"the annotator declining to call a cell type; scored beside real populations it "
                f"reads as a cell type that did badly. Mask with `ctx.real_cells()` and say how "
                f"many cells were set aside.",
                action=f"exclude sentinels from the grouping in {payload.get('kernel')}",
                evidence=str(f)))
    return out


# Properties that are legitimately falsy across a shipped set and are NOT dead branches. Every
# entry needs its reason written here, because an unexplained exemption is how a check gets
# emptied one line at a time until it passes by containing nothing.
PREDICATE_EXEMPT = {
    # These three are falsy across the shipped set BY DESIGN, not by omission, and each reason is
    # written out because an unexplained exemption is indistinguishable from the defect.
    "needs_obs": "a requirement is declared as a ROLE in `inject`, and the host resolves the role "
                 "to a column name at run time. A key list cannot be written at declaration "
                 "time without hard-coding one project's column names into a tool.",
    "needs_obsm": "the same: `embedding` and `layout` are roles, resolved to obsm keys by the "
                  "host. Ask `needs_representation`, which is derived from the roles.",
    "needs_kernels": "A PLUGIN MUST NEVER NAME ANOTHER PLUGIN - it names a capability, and "
                     "`producer_edges` resolves which installed plugin provides it. Naming a "
                     "peer would bake one site's toolbox into a portable declaration.",
}


def unprovidable_capabilities(kernels):
    """A derived capability no installed plugin provides can never be satisfied. Reported.

    `pseudotime` declared that it can use a `velocity` field and the velocity plugin declared
    `provides: []`, so the capability existed in the vocabulary, was asked for by name, and had
    no producer anywhere - the request resolved to nothing on every run and the optional input
    was simply never delivered. An unprovidable capability reads, at the asking end, exactly like
    one the user chose not to run.
    """
    from .declare import CAPABILITIES
    ks = list(kernels.values()) if isinstance(kernels, dict) else list(kernels)
    provided = {c for k in ks for c in (k.spec.get("provides") or [])}
    wanted = {c for k in ks for c in k.needs_capabilities}
    out = []
    for cap in sorted(wanted - provided):
        if CAPABILITIES.get(cap, {}).get("resolve") != "derived":
            continue
        who = sorted(k.name for k in ks if cap in k.needs_capabilities)
        out.append((cap, f"asked for by {', '.join(who)} and provided by no installed plugin, so "
                         f"it can never be delivered and its absence looks like a choice"))
    return out


def dead_predicates(kernels):
    """A kernel property falsy for EVERY installed plugin is a dead branch, and is reported.

    Not a style check, and not a lint. FIVE decisions - the refusal to run without a design, two
    design-defect reports, a plan entry, and the planner's whole choice of contrast - were
    guarded by `needs_design`; a sixth, the one that applies the upstream constraint, was guarded
    by `needs_obsm`. No shipped plugin set either. Every one of those conditions read False on
    every plugin of every run, so each took its silent branch permanently: no plugin ever
    refused, no contrast was ever planned, and the constraint check exempted the very plugin
    whose headline the constraint forbids.

    None of it was visible at a call site. `if k.needs_design:` taking its False branch looks
    exactly the same whether the flag is unset or the condition is genuinely not met, and the
    difference only becomes visible across the whole installed set at once - which is here.

    The property list is INTROSPECTED, not enumerated, so a property added tomorrow is covered
    without anyone remembering to add it.
    """
    from .kernels import Kernel
    ks = list(kernels.values()) if isinstance(kernels, dict) else list(kernels)
    if not ks:
        return []
    out = []
    for attr in sorted(n for n, v in vars(Kernel).items()
                       if isinstance(v, property) and not n.startswith("_")):
        if attr in PREDICATE_EXEMPT:
            continue
        vals = []
        for k in ks:
            try:
                vals.append(getattr(k, attr))
            except Exception:                                             # noqa: BLE001
                vals = None
                break
        if vals is None:
            continue
        if not any(bool(v) for v in vals):
            out.append((attr, f"falsy for all {len(ks)} installed plugins. Any decision guarded "
                              f"by it has only ever taken its False branch, and that is "
                              f"indistinguishable at the call site from a condition that was "
                              f"checked and not met. Either a plugin should be declaring it, or "
                              f"the decisions reading it are dead and should say so."))
    return out


def report(diagnoses, log=print):
    """Print the loop's findings grouped by the layer that owns them, and what each needs."""
    if not diagnoses:
        return
    by = {}
    for d in diagnoses:
        by.setdefault(d.layer, []).append(d)
    log("\nWHAT THESE FAILURES SAY ABOUT THE TOOLING")
    for layer in (ENVIRONMENT, DECLARATION, METHOD, HOST):
        for d in by.get(layer, []):
            log(f"  [{layer}] {d.why}")
            if d.action:
                log(f"      fix: {d.action}")
    if by.get(DECLARATION):
        log("  A declaration defect is for whoever maintains the plugin: "
            "docs/MAINTAINING_PLUGINS.md")
    if by.get(HOST):
        log("  A host defect is a bug in scProfile itself, not in the plugin or the data.")


#: How much of an under-declaration is noise, and how much is a job that dies. A declaration is
#: what the allocator requests; the measurement is what one run of one instance cost. Below this
#: the difference is not evidence of anything, and firing on it would train a maintainer to
#: scroll past the message that matters.
MEMORY_DRIFT_RATIO = 1.25


def memory_drift(kernel, payload):
    """What the instance COST, against what the plugin said it would. A `run -> declare` edge.

    THE FAILURE THIS EXISTS FOR IS SILENT AT EVERY POINT BEFORE THE END. A plugin declares a
    memory model, the allocator requests it, the scheduler grants it, the run proceeds for
    hours, and the kernel is killed with a signal at the largest step. Nothing before that
    moment is distinguishable from a healthy run, and the log ends without an exception,
    because SIGKILL leaves no traceback to diagnose.

    Measured: an instance reported a 14.4 GB peak, its declaration was sized from that, and the
    scheduler billed the job 42.7 GB - a 3.0x under-report, and a dead run at a 48 GB request.

    SO IT TAKES THE LARGER OF THE MEASUREMENTS AND SAYS WHICH IT TOOK. A process cannot measure
    its own peak reliably: `RUSAGE_SELF` excludes children entirely, `RUSAGE_CHILDREN` returns
    the largest single REAPED child rather than the sum of concurrent ones, and the cgroup
    counter is exact but covers the whole job. Every one of them is an estimate with a known
    direction of error, and the only safe rule when two measurements of one cost disagree is to
    believe the larger and name it: an over-request costs queue time, an under-request costs the
    run and every hour already spent on it.

    Reported, never repaired. A number the host corrects on the fly is a number the declaration
    still gets wrong on the next machine.
    """
    m = (payload or {}).get("measured") or {}
    n = m.get("n_cells")
    if not isinstance(m, dict) or not n:
        return []
    peak, source = peak_measurement(m)
    if peak is None:
        return []
    ex = getattr(kernel, "executor", None) or {}
    base = ex.get("memory_gb_base")
    rate = ex.get("memory_gb_per_100k")
    if base is None and rate is None:
        # NOT SILENCE. A plugin that declares no memory model is one the allocator is guessing
        # for, and the measurement in hand is the only evidence anyone will ever have of what
        # it costs. Reported as a declaration to WRITE, not as one that is wrong.
        return [Diagnosis(
            DECLARATION,
            f"declares no memory model, so the allocator sizes it by a default. This instance "
            f"cost {peak:.1f} GB over {n:,} cells ({source}).",
            action=f"declare memory_gb_base and memory_gb_per_100k in {kernel.name}",
            evidence=repr(m))]
    declared = float(base or 0.0) + float(rate or 0.0) * (float(n) / 100_000.0)
    if declared <= 0 or peak <= declared * MEMORY_DRIFT_RATIO:
        return []
    return [Diagnosis(
        DECLARATION,
        f"cost {peak:.1f} GB over {n:,} cells ({source}) against a declared {declared:.1f} GB - "
        f"{peak / declared:.1f}x. The allocator requests the declared figure, so the next run "
        f"of this size is sized to be killed, and a kill at the largest step leaves no "
        f"traceback to diagnose.",
        action=f"raise memory_gb_base / memory_gb_per_100k in {kernel.name}",
        evidence=repr(m))]


def peak_measurement(measured):
    """(peak_gb, which measurement it came from) - THE LARGER, NAMED.

    `peak_rss_gb` is a floor: the parent plus the largest single reaped child, so concurrent
    workers are undercounted and by a factor nobody can bound from inside the process.
    `cgroup_peak_gb` is what the scheduler bills, and is exact for the JOB - which over-attributes
    when several instances share one job, and is exact when one does.

    Both errors are known and they point opposite ways, so there is no combination that is right
    in general. Taking the larger is wrong only in the direction that costs queue time.
    """
    m = measured or {}
    rss = m.get("peak_rss_gb")
    cg = m.get("cgroup_peak_gb")
    vals = [(float(v), k) for k, v in (("the process's own floor", rss),
                                       ("the scheduler's counter for the job", cg))
            if isinstance(v, (int, float))]
    if not vals:
        return (None, "")
    peak, source = max(vals)
    return (peak, source)
