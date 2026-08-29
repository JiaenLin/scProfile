"""What a run says about ITS OWN output, so a later run can decide whether to trust it.

REUSE WITHOUT TRUST IS WORSE THAN RECOMPUTING. The landscape can tell that an earlier result was
computed from the same inputs by the same code - that is a statement about provenance and says
nothing about whether the result is any good. A unit that ran to completion and produced a table
of nonsense has exactly the same key as one that produced a good one, and reusing it propagates
the error into every run that follows, with a provenance trail that makes it look verified.

So every run publishes a CARD: for the run and for each instance, what happened and whether it
is safe to build on. A later run reads the card rather than inferring from file existence.

FIVE VERDICTS, AND THE MIDDLE THREE ARE THE POINT.

    ok        completed, nothing objected. Reusable.
    empty     ran and produced nothing. THAT IS A RESULT and it is reusable - re-running
              costs the same and answers the same.
    suspect   completed, and something in the run objected to it: the plugin contradicted its
              own output, or a diagnosis was raised against the METHOD rather than the
              environment. NOT reusable without a person looking.
    failed    did not complete. Not reusable, and the next run must do it.
    unknown   the card predates this field, or the run wrote none. Treated as NOT reusable,
              because "no information" and "fine" must never be the same answer.

`unknown` defaulting to not-reusable is deliberate and is the only safe default: a map that
treats silence as approval is a map that launders every result it has no information about.
"""

from __future__ import annotations

import json
from pathlib import Path

CARD = "RUN_CARD.json"

OK, EMPTY, SUSPECT, FAILED, UNKNOWN = "ok", "empty", "suspect", "failed", "unknown"

#: Verdicts a later run may build on without a person intervening.
TRUSTED = (OK, EMPTY)


def _instance_verdict(unit_payload, diagnoses, unit_state):
    """(verdict, reasons) for one instance, from what the run recorded about it."""
    from . import resume

    reasons = []
    if unit_state == resume.DIED:
        return FAILED, ["the kernel started and did not return"]
    if str(unit_payload.get("status", "")).lower() in ("failed", "error"):
        return FAILED, [f"status {unit_payload.get('status')!r}"]
    # A PLUGIN THAT REFUTED ITS OWN OUTPUT IS THE STRONGEST SIGNAL THERE IS, and it is one the
    # plugin volunteered - nothing infers it.
    con = unit_payload.get("contradictions") or []
    if con:
        reasons += [f"the plugin contradicted its own result: {str(c)[:110]}" for c in con[:2]]
    # A METHOD-LAYER DIAGNOSIS is about the answer. An environment- or host-layer one is about
    # the machinery around it and does not make the numbers wrong.
    for d in diagnoses or []:
        if str(d.get("layer", "")).lower() == "method":
            reasons.append(f"method diagnosis: {str(d.get('why', ''))[:110]}")
    if reasons:
        return SUSPECT, reasons
    if unit_state == resume.EMPTY:
        return EMPTY, ["ran and produced nothing, which is a result"]
    return OK, []


def build(out, payload):
    """The card for a finished run, from the payload it already holds."""
    from . import resume

    out = Path(out)
    diagnoses = payload.get("diagnoses") or []
    instances = []
    for name, p in sorted((payload.get("kernels") or {}).items()):
        units = p.get("units") or [None]
        for u in units:
            uid = (u or {}).get("unit") if isinstance(u, dict) else None
            up = u if isinstance(u, dict) else p
            st, why, n = resume.state(resume.unit_dir(out, name, uid))
            verdict, reasons = _instance_verdict(up, diagnoses, st)
            instances.append({"plugin": name, "unit": uid, "verdict": verdict,
                              "reasons": reasons, "artifacts": n, "state": st})
    worst = FAILED if any(i["verdict"] == FAILED for i in instances) else (
        SUSPECT if any(i["verdict"] == SUSPECT for i in instances) else OK)
    return {"card": 1, "run": out.name, "verdict": worst if instances else UNKNOWN,
            "instances": instances,
            # WHAT THE RUN COULD NOT CHECK ABOUT ITSELF. A card that only lists what went right
            # is the thing this exists to replace.
            "not_self_checked": [
                "whether any figure was LOOKED AT - see `scprofile review`",
                "whether the numbers are correct; only whether anything objected to them",
            ]}


def write(out, payload):
    """Write the card beside the run. Returns it."""
    card = build(out, payload)
    (Path(out) / CARD).write_text(json.dumps(card, indent=1), encoding="utf-8")
    return card


def read(rundir):
    """The card a run published, or None."""
    f = Path(rundir) / CARD
    try:
        c = json.loads(f.read_text(encoding="utf-8"))
        return c if isinstance(c, dict) else None
    except (OSError, ValueError):
        return None


def verdict_for(rundir, plugin, unit=None):
    """(verdict, reasons) this run published for one instance. UNKNOWN when it published none."""
    c = read(rundir)
    if not c:
        return UNKNOWN, ["this run published no card, so nothing is known about its output"]
    for i in c.get("instances") or []:
        if i.get("plugin") == plugin and i.get("unit") == unit:
            return i.get("verdict", UNKNOWN), list(i.get("reasons") or [])
    return UNKNOWN, ["the card does not mention this instance"]
