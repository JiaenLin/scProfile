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
     "a package the plugin imports is not in its environment. Either the lock does not name it "
     "or the environment was not built from the current lock."),
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
    out = []
    declared = set(kernel.spec.get("produces") or [])
    if not declared:
        return out
    got = set()
    for slot in ("obs", "obsm", "layers"):
        for key in (payload.get(slot) or {}):
            got.add(f"{slot}[{key}]")
    for rel in (payload.get("tables") or []):
        got.add(f"tables/{str(rel).split('/')[-1]}")

    for d in sorted(declared - got):
        if payload.get("status") in ("refused", "partial"):
            continue          # a refusal is allowed to produce nothing; it said why
        out.append(Diagnosis(
            DECLARATION,
            f"declares {d!r} in `produces` and did not emit it. Either the method stopped "
            f"producing it or the declaration is stale; both mislead the next reader.",
            action=f"fix `produces` in the plugin, or the method"))
    for g in sorted(got - declared):
        out.append(Diagnosis(
            DECLARATION,
            f"emitted {g!r}, which it does not declare in `produces`. An undeclared output is "
            f"one no `cannot_show` covers and no documentation mentions.",
            action=f"add {g!r} to `produces`, with its limits"))
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
