"""A LICENCE: the evidence that one earlier result may be adopted into a later run.

WHY A LICENCE AND NOT A FLAG. Adoption is a hardlink - the new run's file IS the old run's file,
byte for byte, and every number downstream of it inherits whatever was wrong with it. A boolean
"reusable" written by whoever felt confident is not enough to justify that. A licence records
the EVIDENCE, names what it could not check, and dies the moment the artifact changes.

FOUR CLASSES OF EVIDENCE, GATHERED SEPARATELY BECAUSE THEY FAIL SEPARATELY.

  integrity     every artifact exists and its sha256 is recorded HERE, in the licence. This is
                what makes the licence self-invalidating: change a byte and it no longer matches.
  completeness  the instance finished, and everything its plugin DECLARED it produces is present.
                A run that returned early leaves a plausible directory; the declaration is the
                only thing that says what should have been in it.
  self_report   the producing run's own verdict, from its RUN_CARD - did the plugin contradict
                itself, was a diagnosis raised against the METHOD.
  provenance    plugin, version, unit, input identity, params, keys - the reuse key. Not quality,
                but without it "the same result" cannot be defined at all.

  inspection    OPTIONAL and recorded separately: whether a person opened the figures
                (`scprofile review`). Never required, never invented.

THREE GRADES, AND THE THIRD IS THE HONEST ONE.

  full          all four classes satisfied AND the figures were inspected.
  provisional   all four satisfied, nobody looked. Adoptable; the licence says nobody looked.
  retrospective GRANTED AFTER THE FACT to a run that predates this mechanism. Integrity,
                completeness and provenance are verified from what is on disk NOW. The
                SELF-REPORT CANNOT BE RECOVERED - the run published no card and no amount of
                reading its output afterwards recreates what it would have said. A retrospective
                licence states that gap rather than papering over it.

  refused       something failed. The reasons are named.

A RETROSPECTIVE LICENCE IS NOT A FULL ONE WITH AN ASTERISK. It is a different claim: "the bytes
are intact and complete and I know where they came from", not "the run that made them reported
nothing wrong". Keeping the two apart is the entire reason this file has grades instead of a
boolean, because the temptation - when eight earlier runs are sitting there and re-running costs
hours - is exactly to blur them.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

LICENCE_DIR = "LICENCES"

FULL, PROVISIONAL, RETROSPECTIVE, REFUSED = ("full", "provisional", "retrospective", "refused")
ADOPTABLE = (FULL, PROVISIONAL, RETROSPECTIVE)

#: Ordered weakest to strongest, so a policy can say "at least this".
GRADE_ORDER = (REFUSED, RETROSPECTIVE, PROVISIONAL, FULL)

# ---------------------------------------------------------------------------------------------
# THE CRITERIA. Stated here, in one place, as data - not spread through the logic that reads
# them. A licence records the version it was granted under, so a licence written before a
# criterion existed is distinguishable from one that passed it, and adding a criterion does not
# silently re-bless everything already on disk.
#
# A GRADE IS DERIVED FROM EVIDENCE ALONE. Nothing a person passes on the command line changes
# what evidence says. What a person decides is which grades they are willing to ADOPT, which is
# a policy applied at adoption time and recorded there - see `adopt(min_grade=...)`.
# ---------------------------------------------------------------------------------------------

#: Bump when a criterion is added, removed, or its measurement changes. Licences carry it.
CRITERIA_VERSION = 1


class Criterion:
    """One thing that is measured, what passing it establishes, and what it does NOT."""

    def __init__(self, cid, requires, measured_by, establishes, does_not_establish, *,
                 required_for_any_licence=False):
        self.id = cid
        self.requires = requires
        self.measured_by = measured_by
        self.establishes = establishes
        self.does_not_establish = does_not_establish
        #: A criterion no licence of any grade may fail. The others differentiate grades.
        self.required = required_for_any_licence


CRITERIA = (
    Criterion(
        "integrity",
        "every file the instance produced exists and hashes cleanly",
        "sha256 of each file, recorded INTO the licence",
        "that the bytes adopted later are the bytes licensed now",
        "that the bytes are correct - only that they have not changed",
        required_for_any_licence=True),
    Criterion(
        "completeness",
        "the instance finished, and everything its plugin DECLARES it produces is present",
        "resume.state() against the unit directory, plus the plugin's `produces` list",
        "that nothing the plugin promised is missing",
        "that what is present is right, nor that the plugin promised everything it should",
        required_for_any_licence=True),
    Criterion(
        "provenance",
        "the reuse key is computable: plugin, version, unit, input identity, params, keys",
        "landscape.unit_record() reading in.json and out.json",
        "that a later run can tell whether it is asking for the same thing",
        "that the INPUT is unchanged - runs record a path and no content digest",
        required_for_any_licence=True),
    Criterion(
        "self_report",
        "the producing run published a card and its verdict for this instance is trusted",
        "runcard.verdict_for()",
        "that the run that computed this did not object to it",
        "that the run would have noticed a problem; it reports what it checked, not what it "
        "did not"),
    Criterion(
        "inspection",
        "every figure the instance produced has a recorded look",
        "review.read_ledger() against the figures on disk",
        "that a person opened each panel and wrote down what they saw",
        "that what they saw was right"),
)

BY_ID = {c.id: c for c in CRITERIA}

#: GRADE FROM EVIDENCE, and nothing else. Read top to bottom; the first matching row wins.
GRADE_RULES = (
    (REFUSED, "any REQUIRED criterion fails"),
    (REFUSED, "self_report is present and NOT trusted - the run that made it objected"),
    (RETROSPECTIVE, "self_report is ABSENT: the run published no card and it cannot be "
                    "reconstructed afterwards"),
    (FULL, "every criterion passes, inspection included"),
    (PROVISIONAL, "required criteria and self_report pass; nobody looked at the figures"),
)



def _artifacts(unit_dir):
    """Every file an instance produced, relative to its directory, with a digest."""
    from . import review

    d = Path(unit_dir)
    out = {}
    for p in sorted(d.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(d))] = review.digest(p)
    return out


def evaluate(rundir, plugin, unit=None, *, declared=None):
    """The evidence, class by class. No judgement here - `grant` decides what it adds up to."""
    from . import landscape, resume, runcard, review

    d = resume.unit_dir(rundir, plugin, unit)
    ev, missing = {}, []

    st, why, n = resume.state(d)
    arts = _artifacts(d) if d.is_dir() else {}
    ev["integrity"] = {"ok": bool(arts) and all(v for v in arts.values()),
                       "n_files": len(arts),
                       "why": "every file hashed" if arts else "no files in this instance"}

    # COMPLETENESS IS AGAINST THE DECLARATION, not against "some files exist". A plugin that
    # declares three tables and wrote one leaves a directory that looks fine.
    want = list(declared or [])
    absent = [w for w in want if not (d / w).exists()]
    ev["completeness"] = {
        "ok": st in resume.FINISHED and not absent,
        "state": st, "declared": want, "absent": absent,
        "why": (why if st not in resume.FINISHED else
                (f"declared but not present: {absent}" if absent else "finished, nothing missing"))}

    v, reasons = runcard.verdict_for(rundir, plugin, unit)
    ev["self_report"] = {"ok": v in runcard.TRUSTED, "verdict": v, "reasons": reasons}
    if v == runcard.UNKNOWN:
        missing.append("the producing run published no card, so its own verdict on this result "
                       "cannot be recovered")

    rec = landscape.unit_record(rundir, plugin, unit)
    ev["provenance"] = {"ok": bool(rec and rec.get("input")),
                        "key": rec.get("key") if rec else None,
                        "version": rec.get("version") if rec else None,
                        "input": rec.get("input") if rec else None,
                        "why": "reuse key computable" if rec else "no in.json to key on"}
    if rec and rec.get("input_size") is None:
        missing.append("the input object is not reachable from here, so its identity could not "
                       "be confirmed - only the path it was recorded under")

    figs = [f for f in arts if f.startswith("figures/")]
    looked = review.read_ledger(rundir)
    seen = [f for f in figs
            if any(k.endswith(f) for k in looked)]
    ev["inspection"] = {"ok": bool(figs) and len(seen) == len(figs),
                        "figures": len(figs), "reviewed": len(seen),
                        "why": f"{len(seen)} of {len(figs)} figure(s) have a recorded look"}
    return ev, missing


def decide(rundir, plugin, unit=None, *, declared=None, granter="", **_ignored):
    """The licence this WOULD be, written nowhere.

    SPLIT FROM `grant` BECAUSE A PREVIEW THAT DISAGREES WITH THE ACTION IS WORSE THAN NEITHER.
    The first version of the CLI ran its own shortened check for the dry run - hard classes only
    - and reported "would grant" for ten instances that `--grant` then refused, because the
    shortened check never looked at the self-report. One decision function, two callers.
    """
    from . import resume, runcard

    ev, missing = evaluate(rundir, plugin, unit, declared=declared)
    hard = [k for k in ("integrity", "completeness", "provenance") if not ev[k]["ok"]]
    if hard:
        return {"licence": 1, "grade": REFUSED, "run": Path(rundir).name,
                "plugin": plugin, "unit": unit,
                "refused_because": [f"{k}: {ev[k]['why']}" for k in hard],
                "evidence": ev}

    self_ok = ev["self_report"]["ok"]
    unknown = ev["self_report"]["verdict"] == runcard.UNKNOWN
    if not self_ok and not unknown:
        # The run said something was wrong with this result. That is not a gap to be waived by
        # a flag; it is the one signal here that came from the thing that computed it.
        return {"licence": 1, "grade": REFUSED, "run": Path(rundir).name,
                "plugin": plugin, "unit": unit,
                "refused_because": [f"the producing run calls this "
                                    f"{ev['self_report']['verdict']!r}"]
                                   + ev["self_report"]["reasons"],
                "evidence": ev}
    # A MISSING SELF-REPORT IS EVIDENCE, NOT A REFUSAL. It grades RETROSPECTIVE - the bytes are
    # intact, complete and keyed, and the run said nothing about itself because it could not.
    # Whether that is good enough to adopt is a POLICY decision and is taken at adoption.

    grade = RETROSPECTIVE if unknown else (FULL if ev["inspection"]["ok"] else PROVISIONAL)
    rule = next(r for g, r in GRADE_RULES if g == grade)
    d = resume.unit_dir(rundir, plugin, unit)
    lic = {
        "licence": 1, "grade": grade, "run": Path(rundir).name, "run_dir": str(rundir),
        "plugin": plugin, "unit": unit, "dir": str(d),
        "criteria_version": CRITERIA_VERSION,
        "graded_by_rule": rule,
        "granted": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "granter": str(granter or ""),
        "key": ev["provenance"]["key"],
        "artifacts": _artifacts(d),
        "evidence": ev,
        # WHAT THIS LICENCE DOES NOT CLAIM. Printed in the licence itself, so it travels with it
        # rather than living in a document nobody opens beside it.
        "not_evidenced": missing + [
            "that the numbers are CORRECT - only that nothing available objected to them",
        ] + ([] if ev["inspection"]["ok"] else
             ["that any figure was looked at"]),
        "void_if": "any artifact's sha256 changes, or the reuse key changes",
    }
    return lic


def grant(rundir, plugin, unit=None, **kw):
    """`decide`, then written to disk. The only difference between them is the write."""
    lic = decide(rundir, plugin, unit, **kw)
    _write(rundir, plugin, unit, lic)
    return lic


def _slug(plugin, unit):
    return f"{plugin}__{unit}" if unit else str(plugin)


def _write(rundir, plugin, unit, lic):
    d = Path(rundir) / LICENCE_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{_slug(plugin, unit)}.json").write_text(json.dumps(lic, indent=1), encoding="utf-8")


def read(rundir, plugin, unit=None):
    f = Path(rundir) / LICENCE_DIR / f"{_slug(plugin, unit)}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def verify(lic, rundir=None):
    """(ok, reasons) - is this licence still true of what is on disk RIGHT NOW?

    THE LICENCE IS NOT THE AUTHORITY; THE BYTES ARE. A licence is a claim about a set of files
    at a moment. Re-checking it before adopting is the whole reason the hashes are in it.
    """
    from . import review

    if not lic or lic.get("grade") not in ADOPTABLE:
        return False, [f"grade {(lic or {}).get('grade')!r} is not adoptable"]
    d = Path(rundir or lic.get("run_dir", "")) / "" if rundir else Path(lic.get("dir", ""))
    base = Path(lic.get("dir", "")) if not rundir else Path(rundir) / Path(lic["dir"]).name
    base = Path(lic.get("dir")) if Path(lic.get("dir", "")).is_dir() else base
    bad = []
    for rel, want in (lic.get("artifacts") or {}).items():
        got = review.digest(base / rel)
        if got is None:
            bad.append(f"missing since the licence was granted: {rel}")
        elif got != want:
            bad.append(f"CHANGED since the licence was granted: {rel}")
    return (not bad), bad


def adopt(lic, dest_run, *, link=True, min_grade=PROVISIONAL):
    """Materialise a licensed instance inside a new run. Returns (n_files, how, reasons).

    HARDLINK BY DEFAULT, and the reason is not disk space. A hardlink is the SAME INODE: the
    adopted file cannot silently differ from the licensed one, because there is only one copy of
    the bytes. A copy can drift; a link cannot. Where a link is impossible - a different
    filesystem - it falls back to a copy and SAYS SO, because a copy is a weaker claim and the
    run should record which it got.
    """
    import shutil

    # POLICY, APPLIED HERE AND RECORDED HERE. The grade came from evidence; what a project is
    # willing to build on is its own decision, and it belongs at the moment of adoption rather
    # than smuggled into how the evidence was read.
    g = (lic or {}).get("grade")
    if GRADE_ORDER.index(g) < GRADE_ORDER.index(min_grade) if g in GRADE_ORDER else True:
        return 0, "refused", [f"grade {g!r} is below the minimum this adoption accepts "
                              f"({min_grade!r})"]
    ok, why = verify(lic)
    if not ok:
        return 0, "refused", why
    src = Path(lic["dir"])
    dst = Path(dest_run) / "kernels" / lic["plugin"] / (lic["unit"] or "")
    dst.mkdir(parents=True, exist_ok=True)
    how, n = "hardlink", 0
    for rel in sorted(lic.get("artifacts") or {}):
        s, t = src / rel, dst / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        if t.exists():
            t.unlink()
        try:
            if link:
                os.link(s, t)
            else:
                raise OSError("copy requested")
        except OSError:
            shutil.copy2(s, t)
            how = "copy"
        n += 1
    (dst / "ADOPTED.json").write_text(json.dumps(
        {"from_run": lic.get("run"), "grade": lic.get("grade"), "how": how,
         "accepted_minimum_grade": min_grade,
         "criteria_version": lic.get("criteria_version"),
         "key": lic.get("key"), "adopted": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "not_evidenced": lic.get("not_evidenced", [])}, indent=1), encoding="utf-8")
    return n, how, []
