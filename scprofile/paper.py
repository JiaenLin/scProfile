"""The paper test: can someone write the result from these figures, and does it survive review?

WHERE THIS SITS. It is the step AFTER the figures exist and have been looked at, and BEFORE a
run is promoted or its results are reused:

    run  ->  report  ->  standard  ->  review  ->  PAPER  ->  licence / promote
             draw it     measure      look at     write it    build on it
                         the page     the images  and defend

Each earlier step answers a narrower question. `standard` asks whether the page is readable.
`review` asks whether anybody opened the images. Neither asks the question a reader will:
**does this figure set support the thing you want to say?**

WHY A LEDGER AND NOT A CHECKLIST. A checklist is satisfied by reading it. What is recorded here
is a CLAIM - one sentence somebody would put in a paper - and the figures it was read off. A
claim is then reviewed, and the review has three honest outcomes, one of which is that the claim
was wrong. The value is entirely in the third: a claim that dies took a wrong figure with it, or
named a figure that does not exist.

THE ONE PROPERTY THAT MAKES IT A GATE. A claim is bound to the sha256 of every figure it cites.
REDRAW ONE OF THOSE FIGURES AND THE CLAIM IS STALE - not old, stale, and it has to be defended
again. That is the same mechanism as the figure review ledger, for the same reason: a statement
made about a picture cannot outlive the picture.

WHAT THIS IS NOT, AND IT IS NARROW ON PURPOSE FOR NOW. See `NARROW` at the bottom of this file
and `docs/PAPER_TEST.md`. The gaps are NAMED rather than implied, because a test whose limits
are not written down gets used as though it had none.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

#: Where the ledger lives, relative to a run directory. Beside the run, so it travels with the
#: run key and cannot be confused with claims made about some other render.
LEDGER = "PAPER_CLAIMS.jsonl"

#: A claim shorter than this is a label, not a claim. "Diet matters" asserts nothing checkable.
MIN_CLAIM_WORDS = 8

#: And a review that does not say what was examined is not a review.
MIN_WHY_WORDS = 5

#: The three honest outcomes of putting a claim to a reviewer, and the fourth state a claim can
#: be in before anyone has.
STANDING, NARROWED, WITHDRAWN = "standing", "narrowed", "withdrawn"
UNREVIEWED, STALE = "unreviewed", "stale"
VERDICTS = (STANDING, NARROWED, WITHDRAWN)


class Refused(Exception):
    """A claim or a verdict that cannot have come from the work. Raised, never returned."""


def _digest(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
    except OSError:
        return ""
    return h.hexdigest()


def read_ledger(out):
    """[record] in order. Append-only: later records about one claim supersede earlier ones."""
    p = Path(out) / LEDGER
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:                                                 # noqa: BLE001
            continue
    return rows


def _append(out, rec):
    with open(Path(out) / LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def claim(out, text, cites, *, author=""):
    """Record one claim and the figures it was read off. Returns the record.

    `cites` are paths relative to the run directory. A claim citing NOTHING is refused: the
    whole point is to bind a sentence to the pictures it came from, and a claim with no figures
    is an opinion the figure set cannot be held responsible for.
    """
    root = Path(out)
    words = " ".join(str(text or "").split())
    if len(words.split()) < MIN_CLAIM_WORDS:
        raise Refused(f"a claim of {len(words.split())} word(s) asserts nothing checkable. Write "
                      f"the sentence you would put in a paper, in at least {MIN_CLAIM_WORDS} "
                      f"words - what is higher than what, in which arm, and by how much.")
    cites = [str(c).strip() for c in (cites or []) if str(c).strip()]
    if not cites:
        raise Refused("a claim must cite at least one figure. A sentence with no figure behind "
                      "it is not a test of the figure set.")
    missing = [c for c in cites if not (root / c).is_file()]
    if missing:
        raise Refused(f"no such figure in this run: {', '.join(missing)}")
    cid = hashlib.sha256(words.lower().encode()).hexdigest()[:12]
    return _append(out, {"kind": "claim", "id": cid, "text": words,
                         "cites": {c: _digest(root / c) for c in cites},
                         "author": str(author or ""),
                         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})


def review(out, cid, verdict, why, *, reviewer="", replaces=""):
    """Record what a review round did to one claim.

    THE VERDICT THAT MATTERS IS `withdrawn`. A loop that only ever confirms is a loop nobody
    learned from, and the count of withdrawn claims is printed by `summarise` for that reason.
    """
    if verdict not in VERDICTS:
        raise Refused(f"verdict must be one of {', '.join(VERDICTS)}; got {verdict!r}")
    text = " ".join(str(why or "").split())
    if len(text.split()) < MIN_WHY_WORDS:
        raise Refused(f"a verdict of {len(text.split())} word(s) does not say what was examined. "
                      f"Say what the reviewer put to it and what happened, in at least "
                      f"{MIN_WHY_WORDS} words.")
    known = {r["id"] for r in read_ledger(out) if r.get("kind") == "claim"}
    if cid not in known:
        raise Refused(f"no claim {cid!r} in this run. Record the claim before reviewing it.")
    return _append(out, {"kind": "review", "id": cid, "verdict": verdict, "why": text,
                         "reviewer": str(reviewer or ""), "replaces": str(replaces or ""),
                         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})


def status(out):
    """[(id, state, rounds, text)] for every claim, newest verdict winning.

    A claim whose cited figures have changed is STALE whatever its last verdict was: the review
    was of a picture that no longer exists.
    """
    root = Path(out)
    claims, rounds = {}, {}
    for r in read_ledger(out):
        if r.get("kind") == "claim":
            claims[r["id"]] = r
        elif r.get("kind") == "review":
            rounds.setdefault(r["id"], []).append(r)
    rows = []
    for cid, c in claims.items():
        rs = rounds.get(cid) or []
        moved = [f for f, sha in (c.get("cites") or {}).items()
                 if sha and _digest(root / f) != sha]
        if moved:
            state = STALE
        elif not rs:
            state = UNREVIEWED
        else:
            state = rs[-1]["verdict"]
        rows.append((cid, state, len(rs), c.get("text", "")))
    return sorted(rows, key=lambda r: (r[1], r[0]))


def outstanding(out):
    """Claims that have not been defended: never reviewed, or cited a figure that has changed."""
    return [(cid, st) for cid, st, _n, _t in status(out) if st in (UNREVIEWED, STALE)]


def summarise(out):
    """One line per claim plus a tally. Printed by `scprofile paper` and by `check --out`."""
    rows = status(out)
    if not rows:
        return ("NO CLAIMS RECORDED. The paper test has not been run on this figure set: nobody "
                "has written down what it is supposed to show, so nothing has been able to "
                "fail. `scprofile paper --claim ... --cites ...`")
    tally = {}
    for _c, st, _n, _t in rows:
        tally[st] = tally.get(st, 0) + 1
    lines = [f"  {cid}  {st:<11} {n} round(s)  {txt[:74]}" for cid, st, n, txt in rows]
    order = (WITHDRAWN, NARROWED, STANDING, UNREVIEWED, STALE)
    lines.append("  " + " · ".join(f"{tally[k]} {k}" for k in order if k in tally))
    if not tally.get(WITHDRAWN) and not tally.get(NARROWED) and tally.get(STANDING):
        lines.append("  EVERY CLAIM SURVIVED UNCHANGED. That is possible and it is also what a "
                     "loop looks like when nobody pushed on it - the value of this test is in "
                     "the claims it kills.")
    return "\n".join(lines)


#: WHAT THIS TEST DOES NOT YET COVER. Named, because a test whose limits are unwritten gets used
#: as though it had none. Each line is a concrete gap, not a disclaimer.
NARROW = (
    "only the RESULTS section - a paper is also methods, discussion and a figure legend, and "
    "none of those is exercised here",
    "only claims that CITE A FIGURE - a claim resting on a table, or on a number in the text, "
    "is invisible to this ledger",
    "the REVIEWER is unspecified - this records that a round happened and what it decided, not "
    "who is competent to hold it, and a project with no reviewer has no test",
    "MISSING figures are found only INDIRECTLY - a gap surfaces when somebody tries to write "
    "the claim that needs it, so the test sees only as far as the writer's imagination",
    "it does not ask whether a figure is COMPREHENSIBLE - a correct claim read off an "
    "unreadable panel passes",
    "no NEGATIVE CONTROL - the loop has never been run against a figure set known to be sound, "
    "so how often it kills a TRUE claim is unmeasured",
    "ROUNDS are counted, not scored - nothing here says when enough review has happened",
    "run against ONE design shape and ONE method so far - one factor, three factors, no design "
    "at all, and time-course or nested designs are untested",
)
