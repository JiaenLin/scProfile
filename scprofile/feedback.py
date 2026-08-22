"""When something downstream fails, work out WHICH LAYER is wrong and send it there.

THE LOOP THIS COMPLETES

    declare  ->  build  ->  plan  ->  run
       ^           ^         ^          |
       |           |         +----------+   plan already triggers the builder
       |           +--------------------+   a run that fails on the ENVIRONMENT rebuilds it
       +--------------------------------+   a run whose output contradicts the DECLARATION
                                            is a defect for the maintainer, reported as one

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
