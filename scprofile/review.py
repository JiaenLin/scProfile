"""Which figures have actually been LOOKED AT, and which have not.

A GREEN TEST SAYS A FILE WAS WRITTEN. IT SAYS NOTHING ABOUT WHETHER THE PICTURE IS RIGHT.
Every figure defect worth finding in this codebase was found by opening the image, and the
suite was green through all of them: a chord whose ribbon geometry was inverted and rendered as
a starburst of spikes; ring labels sitting on top of the nodes they named; arrowheads painted
over by their own destination markers, so direction - the whole content of the panel - was
legible only from the legend; and a decluttering fix, correct in itself, applied where the
geometry did not need it, which drove ten of twelve labels off the axes and passed every test
before and after.

Nothing here can verify that the agent moved its eyes. What it CAN do is make the
unreviewed set impossible to overlook and impossible to keep once it is stale, which is the
same shape as every other gate in this tool: not a reminder, a refusal.

THREE PROPERTIES DO THE WORK.

1. A REVIEW IS BOUND TO THE IMAGE'S CONTENT. The sha256 of the file is recorded with the note.
   Redraw the figure and the review is INVALIDATED - not merely old, gone. This is the property
   that cannot be talked around: a panel cannot be reviewed once and then quietly change.

2. A NOTE MUST SAY SOMETHING. An empty note, a note shorter than a few words, or a note
   IDENTICAL TO ANOTHER FIGURE'S in the same ledger is refused. Copying one line across forty
   panels is the obvious way to defeat this, so it is the one thing checked directly.

3. THE UNREVIEWED SET IS REPORTED AS A COUNT AND AS NAMES. A number is ignorable; a list of
   filenames is a task. Both are printed, always, including when it is zero.

The ledger is append-only and lives beside the run it describes, so it travels with the run key
and cannot be confused with a review of some other render.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

#: Where the ledger lives, relative to a run directory.
LEDGER = "FIGURE_REVIEW.jsonl"

#: LOOKS CARRY BETWEEN RUNS, READ FROM THE RUNS' OWN LEDGERS - no shared file is written.
#:
#: A review is bound to a figure's sha256, so an unchanged image IS the same image and a look at
#: it is still a look. But the ledger lived only inside the run directory, so a run that reused
#: every fitted object and redrew nothing still reported every one of its figures as never looked
#: at - on this cohort, 672 of them, per run. Honouring that means re-reviewing an unchanged
#: figure set on every run, which nobody will do, so the step gets skipped: a gate that demands
#: the impossible is a gate that is off.
#:
#: THE FIRST VERSION WROTE A SHARED LEDGER AT `Path(out).parent`, which is a guess about layout
#: dressed as a fact. For a run under `runs/<tool>/<stage>/<key>` it lands where intended; for a
#: run anywhere else - a temp directory, say - it lands in that directory's parent and carries
#: looks between runs that have nothing to do with each other. A test creating a run under the
#: system temp directory caught it immediately, which is what it is for.
#:
#: So nothing extra is written. A sibling's looks are read from THAT RUN'S OWN ledger, and a
#: sibling counts only if it is a run - a directory carrying a `report.json`. Scope becomes a
#: property of what is on disk rather than of a path this module assumed.
RUN_MARKER = "report.json"


def ledger_path(out, plugin=""):
    """Where the looks are recorded: the plugin's own directory, or the run root.

    ONE LEDGER PER PLUGIN, for the same reason there is one manuscript per plugin - the looks
    belong with the figures they were taken on. The FIGURE PATHS INSIDE stay relative to the RUN
    root so a path means the same thing wherever it is read, and so the loop can union the
    ledgers of several plugins without rewriting anything.
    """
    from pathlib import Path as _P
    from . import kernels as _K
    root = _K.plugin_out(out, plugin) if plugin else _P(out)
    return root / LEDGER


#: The shape of a run key: a UTC stamp, the tool and its commit, then the stage and a slug -
#: `20260913T133001Z__scprofile-b751000__04_profile__written`. A writing run is named like this.
RUN_KEY_RE = re.compile(r"^\d{8}T\d{6}Z__[A-Za-z][\w]*-[0-9a-f]{7,}__")


def sibling_runs(out):
    """Other RUN directories beside this one. A run is a directory carrying a `report.json`.

    Being a sibling directory is not enough - the parent of a run is not always a run root, and
    treating it as one carries looks between unrelated runs.
    """
    here = Path(out).resolve()

    def _stands_for(d):
        """The run `d` is, or the one run a directory NAMED LIKE A RUN that is not one holds - a
        writing run holding its replay (harness ADR-0020, step 4) - or None. Named like a run,
        because a scratch folder holding one run is not a run's stand-in: read as one, it
        carried looks between the unrelated runs of two tests."""
        if (d / RUN_MARKER).is_file():
            return d
        if not RUN_KEY_RE.match(d.name):
            return None
        try:
            kids = [k for k in d.iterdir() if k.is_dir() and (k / RUN_MARKER).is_file()]
        except OSError:
            return None
        return kids[0] if len(kids) == 1 else None

    def _beside(x, parent):
        out_ = []
        try:
            entries = sorted(parent.iterdir())
        except OSError:
            return out_
        for d in entries:
            if not d.is_dir() or d == x or d == here:
                continue
            r = _stands_for(d)
            if r is not None and r != here:
                out_.append(r)
        return out_

    found = _beside(here, here.parent)
    # A WRITING RUN STANDS FOR THE REPLAY IT HOLDS. The seal lays a run's replay under
    # `<writing run>/replay/` beside nothing, so the looks that carry by content hash from the
    # run beside were invisible there (blind 0006, both seals failed W3 on `looked_at`). When
    # the parent is not a run and holds only this one, the parent's siblings are this run's -
    # and no further: a lone run's grandparent is not a run root, and reading it would carry
    # looks between unrelated runs.
    if not found and _stands_for(here.parent) == here and here.parent.parent != here.parent:
        found = _beside(here.parent, here.parent.parent)
    return found


def read_carried(out, plugin=""):
    """{sha256: entry} - looks taken on sibling runs, keyed by the IMAGE they were taken on.

    Read from each run's OWN ledger. A review is bound to a figure's bytes, so an unchanged image
    carries; nothing else does, and nothing is written outside the run being reviewed.
    """
    # THE LATEST LOOK PER IMAGE, WHICHEVER SIBLING TOOK IT (harness ADR-0022): the first
    # sibling's record won before, so an older run's defect look outranked the plain look a
    # later run's looker had settled it with, and eighteen settled figures were sent back.
    seen = {}
    for run in sibling_runs(out):
        for rel, rec in read_ledger(run, plugin).items():
            sha = str(rec.get("sha256") or "")
            if sha and str(rec.get("at") or "") >= str((seen.get(sha) or {}).get("at") or ""):
                seen[sha] = dict(rec, run=run.name)
    return seen

#: A note below this many words is not a look, it is a keystroke.
MIN_NOTE_WORDS = 4

#: Image suffixes a run can produce. Anything else is not a figure.
SUFFIXES = (".png", ".jpg", ".jpeg", ".svg", ".pdf")

REVIEWED, STALE, UNREVIEWED = "reviewed", "stale", "unreviewed"

#: Looked at on an EARLIER run, and the image has not changed since. It counts as reviewed - the
#: review is bound to the bytes, and these are the same bytes - but it is named differently so a
#: reader can tell a look taken here from one carried in.
CARRIED_OK = "reviewed (carried)"
#: A figure the eye marked, the author answered, and a looker has not looked at again.
ANSWERED = "answered - needs a look"

#: The host's own composed panels, by the ids the reporter gives them (harness ADR-0019): the
#: network kinds, the contrast kinds, the presence and totals panels, the design grid. A finding
#: on one of these is the host's debt, fixed in the module named, with nothing to paste.
_HOST_PANELS = {"N": "network_panels", "C": "compare_panel", "P": "network_panels",
                "across_design": "design_panel"}


def digest(path):
    """sha256 of a file's bytes, or None. The identity a review is bound to."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def figures(out):
    """Every figure a run directory holds, as paths relative to it, sorted."""
    root = Path(out)
    if not root.is_dir():
        return []
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.is_file() and p.suffix.lower() in SUFFIXES
                  and "report" not in p.relative_to(root).parts[:1])


def read_ledger(out, plugin=""):
    """{relpath: latest entry}. Append-only on disk; last entry per figure wins."""
    f = ledger_path(out, plugin)
    seen = {}
    if not f.exists():
        return seen
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("figure") and not rec.get("answer"):
            seen[str(rec["figure"])] = rec
    return seen


def read_answers(out, plugin=""):
    """{relpath: latest answer record} - what the author said about a figure that should stay.

    KEPT APART FROM THE LOOKS (harness ADR-0019): an answer is not a look, and the latest look
    per figure must stay the eye's. An answer record carries `answer`, `by`, `sha256`, `at`.
    """
    def _own(run):
        f = ledger_path(run, plugin)
        got = {}
        if not f.exists():
            return got
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("figure") and rec.get("answer"):
                got[str(rec["figure"])] = rec
        return got

    seen = _own(out)
    # AND THE SIBLINGS', BY THE IMAGE'S BYTES (harness ADR-0019, found on the rerun of blind
    # 0006): the looks and the findings carried from the run beside this one by sha256 and not
    # one of the author's 21 answers did, so the answered plates were not outstanding for a fresh
    # look and the worksheet would have asked the same kinds again. An answer is bound to the
    # bytes like a look is: on the same bytes it carries, with the run it was given on named.
    by_sha = {}
    for run in sibling_runs(out):
        for _rel, rec in _own(run).items():
            sha = str(rec.get("sha256") or "")
            if sha:
                by_sha.setdefault(sha, dict(rec, run=run.name))
    if by_sha:
        root = Path(out)
        for rel in figures(out):
            if rel in seen or (plugin and not rel.startswith(f"kernels/{plugin}/")):
                continue
            now = digest(root / rel)
            if now and now in by_sha:
                seen[rel] = dict(by_sha[now], figure=rel)
    return seen


class Refused(Exception):
    """A note that does not evidence a look. Raised, never returned - see the module docstring."""


def record(out, figure, note, *, reviewer="", plugin="", defect=False):
    """Append one review. REFUSES a note that cannot have come from looking.

    `defect=True` marks a look that says THE PANEL MUST CHANGE (harness ADR-0018): the verdict a
    machine can read, so the audit stage counts it, the agenda's write task waits on it and a
    claim cannot cite the plate. Without it a look describes.

    The refusals are deliberately few and mechanical: emptiness, brevity, and being identical
    to another figure's note. A check that tried to judge whether a sentence was INSIGHTFUL
    would be a check nobody could satisfy twice, and would be switched off.
    """
    root = Path(out)
    rel = str(figure)
    path = root / rel
    if not path.is_file():
        raise Refused(f"no such figure in this run: {rel}")
    text = " ".join(str(note or "").split())
    if len(text.split()) < MIN_NOTE_WORDS:
        raise Refused(f"a note of {len(text.split())} word(s) is not a look. Say what the panel "
                      f"shows, or what is wrong with it, in at least {MIN_NOTE_WORDS} words.")
    for other, rec in read_ledger(out).items():
        if other != rel and " ".join(str(rec.get("note", "")).split()).lower() == text.lower():
            raise Refused(f"this note is identical to the one recorded for {other!r}. One line "
                          f"copied across figures is the obvious way to defeat this, so it is "
                          f"the one thing checked directly.")
    rec = {"figure": rel, "sha256": digest(path), "note": text,
           "reviewer": str(reviewer or ""), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                time.gmtime()),
           **({"defect": True} if defect else {})}
    ledger_path(root, plugin).parent.mkdir(parents=True, exist_ok=True)
    _append_line(ledger_path(root, plugin), json.dumps(rec))
    return rec


def declared_text(plugin, rel, plugin_file=None):
    """(entry id, the words) the plugin's OWN declaration carries for the plan entry that claims
    `rel`, read from the plugin's file in this tree - not from the run, which froze the
    declaration when it ran. ("", "") when the file or the entry cannot be found."""
    pf = Path(plugin_file) if plugin_file else _plugin_file(plugin)
    if not pf or not pf.is_file():
        return "", ""
    try:
        from ._entry import load as _load
        from . import declare as _DC
        from . import native as _NAT
        spec = dict(getattr(_load(str(pf)), "PLUGIN", {}) or {})
        fid = str(_NAT.entry_for(spec, Path(rel).name) or "")
        entry = next((e for e in _DC.report_figures(spec) if str(e.get("id") or "") == fid),
                     None)
    except Exception:                                                     # noqa: BLE001
        return "", ""
    if entry is None:
        return fid, ""
    # THE LEGEND, NOT ANYWHERE IN THE ENTRY (found by the cold author of ADR-0022's pass): the
    # page prints the legend under the figure; a sentence in `args` closes nothing a reader sees.
    return fid, " ".join(str(entry.get(k) or "") for k in ("legend", "caption"))


def _norm(text):
    return " ".join(str(text or "").split()).lower()


def answer(out, figure, why, *, by="", plugin="", stated=False, plugin_file=None):
    """Record why a figure the eye marked should stay as it is. Returns the record.

    STATED, AND CLOSED (harness ADR-0022): thirteen of sixteen surviving kinds named the
    upstream's own drawing - a legend it does not draw, labels the plugin cannot reach through
    its plan - and their only exit was a looker's fresh look, which kept finding what is there.
    With `stated=True` the answer is a disclosure: the words must appear in the plan entry that
    captions the figure, in the plugin's own file, and then the finding closes without a fresh
    look, because the check is mechanical - the words are there or they are not. A redraw
    reopens it as it reopens every look.

    THE ANSWER PATH (harness ADR-0019). A colour key that reads min and max by the upstream's
    design, a ribbon with no numeric width in any version of the tool: the loop's rule is that
    every finding becomes a change, and the only way to make one not happen is a later look on
    the same bytes - which the author is not entitled to give. So the author answers, the
    finding stays open, and the review's outstanding list sends the figure back to a LOOKER,
    whose fresh look on the same bytes settles it. Refuses an answer with no reason or no name.
    """
    root = Path(out)
    rel = str(figure)
    path = root / rel
    if not path.is_file():
        raise Refused(f"no such figure in this run: {rel}")
    text = " ".join(str(why or "").split())
    if len(text.split()) < MIN_NOTE_WORDS * 2:
        raise Refused(f"an answer of {len(text.split())} word(s) is not a reason. Say why this "
                      f"panel stays as it is - what the upstream draws by design, where the "
                      f"numbers are - in at least {MIN_NOTE_WORDS * 2} words.")
    who = str(by or "").strip()
    if not who:
        raise Refused("an answer needs a name: --reviewer <who answered>. A looker reads it "
                      "and must know whose it is.")
    rec = {"figure": rel, "sha256": digest(path), "answer": text, "by": who,
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if stated:
        fid, words = declared_text(plugin, rel, plugin_file)
        if _norm(text) not in _norm(words):
            raise Refused(f"the plan entry {fid or '?'!r} that captions {rel} does not state "
                          f"this in its legend. A stated answer closes the finding only when "
                          f"the words are where the page prints them: put this sentence in the "
                          f"entry's legend in the plugin's file, then answer again.")
        rec["stated"] = True
    ledger_path(root, plugin).parent.mkdir(parents=True, exist_ok=True)
    _append_line(ledger_path(root, plugin), json.dumps(rec))
    return rec


def stated_answers(out, plugin=""):
    """{relpath: answer record} - stated answers on the figure's current bytes that no later
    look has re-marked. These CLOSE the finding (see `answer`)."""
    root = Path(out)
    looks = read_ledger(out, plugin)
    out_ = {}
    # EVERY STATED RECORD THIS RUN OR ITS SIBLINGS HOLD, BY ENTRY - not by bytes, which is how
    # answers otherwise carry; the by-entry carry below re-checks each against the declaration.
    by_kind = {}
    for run in [root] + list(sibling_runs(out)):
        f = ledger_path(run, plugin)
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("stated") is True and rec.get("figure"):
                by_kind[kind_of(str(rec["figure"]))] = rec
    for rel, rec in read_answers(out, plugin).items():
        if rec.get("stated") is not True:
            continue
        now = digest(root / rel)
        if now and rec.get("sha256") and now != rec["sha256"]:
            continue
        look = looks.get(rel) or {}
        if look.get("defect") is True and str(look.get("at") or "") > str(rec.get("at") or ""):
            continue                       # the eye marked it again after the disclosure
        out_[rel] = rec
    # AND BY THE ENTRY, TO ANY RENDERING (harness ADR-0022): seventeen plates of one scan set
    # render differently on every run, so a disclosure bound to bytes reopened with nothing
    # changed but the pixels. The disclosure is about the entry's drawing by the upstream's
    # design; it holds for every rendering while the legend carries the words, and that is
    # checked against the declaration in this tree, not the image.
    words_by_kind = {}
    for rel in figures(out):
        if rel in out_ or (plugin and not rel.startswith(f"kernels/{plugin}/")):
            continue
        kind = kind_of(rel)
        rec = by_kind.get(kind)
        if rec is None:
            continue
        # ONE READ OF THE DECLARATION PER KIND: read per figure, the worksheet took two minutes
        # on 945 figures, loading the plugin's file for each.
        if kind not in words_by_kind:
            words_by_kind[kind] = _norm(declared_text(plugin, rel)[1])
        words = words_by_kind[kind]
        if words and _norm(rec.get("answer")) in words:
            out_[rel] = dict(rec, figure=rel, carried_by="entry")
    return out_


def answered(out, plugin=""):
    """{relpath: answer record} - figures whose OPEN defect carries a later answer, same bytes."""
    root = Path(out)
    ans = read_answers(out, plugin)
    if not ans:
        return {}
    looks = read_ledger(out, plugin)
    carried = read_carried(out, plugin)
    open_ = {rel for rel, _n, _w, _r in defects(out, plugin)}
    out_ = {}
    for rel, rec in ans.items():
        if rel not in open_:
            continue                       # settled by a look, or never marked
        now = digest(root / rel)
        if now and rec.get("sha256") and now != rec["sha256"]:
            continue                       # the answer was about other bytes
        # THE LOOK THAT SETTLED IT CARRIES WITH IT (harness ADR-0022): held against this run's
        # own ledger alone, a figure a looker had settled on the run before read "needs a look"
        # again on identical bytes - eighteen of them on one rerun.
        look = looks.get(rel) or (carried.get(now) if now else None) or {}
        if str(look.get("at") or "") > str(rec.get("at") or ""):
            continue                       # a looker marked it again after the answer
        out_[rel] = rec
    return out_


#: How long to wait for another writer's append, and when to treat its lock as abandoned.
APPEND_WAIT_S = 20.0
APPEND_STALE_S = 60.0


def _append_line(path, line):
    """Append one line under an exclusive-create lock, waiting for other writers.

    THE LEDGER HAS MORE THAN ONE WRITER NOW. Looking at figures is the slowest step in the cycle
    and it parallelises perfectly - the figures are independent and the record is append-only -
    so the agenda tells an agent to fan the step out. That makes concurrent appends normal rather
    than exotic, and `open(..., "a")` is not enough for it: O_APPEND atomicity is a guarantee of
    the LOCAL filesystem, and a run under a scheduler lives on a network filesystem where the
    client can do its own read-modify-write of the offset. Two agents recording at the same
    instant would then produce one interleaved line - a ledger that fails to parse, discovered
    long after the looks that filled it.

    A LOCK THAT REFUSES WOULD BE THE WRONG LOCK. `refs._DirLock` refuses a second writer, which
    is right for a download that would corrupt a file and wrong here: the second writer has done
    the work already and only needs its turn. This one waits, and takes over a lock nobody has
    touched for `APPEND_STALE_S` so an agent killed mid-append cannot block the rest for ever.
    """
    import os
    import socket
    lock = Path(str(path) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + APPEND_WAIT_S
    held = False
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {socket.gethostname()}\n".encode())
            os.close(fd)
            held = True
            break
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue
            if age > APPEND_STALE_S:
                # ABANDONED, NOT BUSY. Unlink and go round; whoever wins the next O_EXCL owns it.
                try:
                    lock.unlink()
                except OSError:
                    pass
                continue
            if time.time() > deadline:
                break
            time.sleep(0.05)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    finally:
        if held:
            try:
                lock.unlink()
            except OSError:
                pass


def status(out, plugin=""):
    """[(relpath, state, why)] for every figure, sorted. `state` is one of the three above."""
    led = read_ledger(out, plugin)
    carried = read_carried(out, plugin)
    ans = answered(out, plugin)
    closed = stated_answers(out, plugin)
    rows = []
    for rel in figures(out):
        if rel in closed:
            rows.append((rel, REVIEWED, f"stated by {closed[rel].get('by')}: "
                                        f"{str(closed[rel].get('answer'))[:110]}"))
            continue
        if rel in ans:
            # ANSWERED, NOT SETTLED (harness ADR-0019): the author said why it stays; a looker
            # decides. Outstanding, so the shards carry it to one.
            rows.append((rel, ANSWERED, f"answered by {ans[rel].get('by')}: "
                                        f"{str(ans[rel].get('answer'))[:110]} - a looker's "
                                        f"fresh look on the same image settles it"))
            continue
        rec = led.get(rel)
        if rec is None:
            # NOT IN THIS RUN'S LEDGER, BUT PERHAPS THE SAME IMAGE. A run that reused its fitted
            # objects and redrew nothing produces figures byte-identical to an earlier run's, and
            # a look at those bytes is still a look. Matched on the image, never on the path.
            now = digest(Path(out) / rel)
            prev = carried.get(now) if now else None
            if prev:
                rows.append((rel, CARRIED_OK,
                             f"looked at on run {prev.get('run', '?')} "
                             f"({prev.get('at', 'date unknown')}) and the image is unchanged"))
            else:
                rows.append((rel, UNREVIEWED, "never looked at"))
            continue
        now = digest(Path(out) / rel)
        if now and rec.get("sha256") and now != rec["sha256"]:
            rows.append((rel, STALE,
                         "REDRAWN since it was reviewed - the review describes an image that no "
                         "longer exists"))
            continue
        rows.append((rel, REVIEWED, str(rec.get("note", ""))[:120]))
    return rows


def defects(out, plugin=""):
    """[(relpath, note, reviewer, run)] - looks marked a defect whose image is unchanged.

    THE EYE'S VERDICT, MACHINE-READABLE (harness ADR-0018). Fifty-eight of one run's 139 notes
    named a defect and nothing could count them. The latest look per figure decides: a later
    clean look on the same bytes supersedes a defect; a redraw clears it, as it clears every
    look; a sibling run's look on the same bytes carries. `run` names the sibling when it does.
    """
    root = Path(out)
    led = read_ledger(out, plugin)
    carried = read_carried(out, plugin)
    out_ = []
    for rel in figures(out):
        now = digest(root / rel)
        rec = led.get(rel)
        run_name = ""
        if rec is None:
            rec = carried.get(now) if now else None
            if rec is None:
                continue
            run_name = str(rec.get("run") or "")
        elif now and rec.get("sha256") and now != rec["sha256"]:
            continue                          # stale: the look was of an image that is gone
        if rec.get("defect") is True:
            out_.append((rel, str(rec.get("note", "")), str(rec.get("reviewer", "")), run_name))
    # A STATED ANSWER CLOSES THE FINDING (harness ADR-0022): the declaration carries the words.
    closed = stated_answers(out, plugin)
    if closed:
        out_ = [x for x in out_ if x[0] not in closed]
    return out_


def open_findings(out, plugin=""):
    """{relpath: [finding]} - the machine's residue after repair and the eye's open defects.

    ONE LIST FOR EVERY READER (harness ADR-0018): the audit stage, the agenda's write task, the
    claim ledger and the brief all ask "which figures does this run's own record call wrong",
    and they must agree. A machine finding is `machine: <code>: <where>`; an eye finding is
    `eye (<who>): <the looker's words>`.
    """
    root = Path(out)
    found = {}
    try:
        doc = json.loads((root / RUN_MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    for name, pl in (doc.get("kernels") or {}).items():
        if plugin and name != plugin:
            continue
        for f in (pl.get("figures") or []) if isinstance(pl, dict) else []:
            rel = str(f.get("path") or "")
            for a in (f.get("audit") or []):
                if isinstance(a, dict):
                    found.setdefault(rel, []).append(
                        f"machine: {a.get('code')}: {a.get('detail')}")
    ans = answered(out, plugin)
    for rel, note, who, run_name in defects(out, plugin):
        found.setdefault(rel, []).append(
            f"eye ({who or 'unnamed'}{', on ' + run_name if run_name else ''}): {note}"
            + (f"; answered by {ans[rel].get('by')}: {ans[rel].get('answer')}" if rel in ans
               else ""))
    return found


def _plugin_file(plugin):
    """The plugin's own file in this tree, or None."""
    try:
        from .kernels import discover
        k = discover().get(plugin)
        return Path(k.path) if k is not None and Path(k.path).is_file() else None
    except Exception:                                                     # noqa: BLE001
        return None


def worksheet(out, plugin, plugin_file=None):
    """The audit's worksheet: every open finding, by kind, with an owner and the two answers.

    A FINDING IS NOT YET WORK (harness ADR-0019). Seventy findings on 46 kinds had three owners
    and the ledger named none: the HOST's own composed panels (mechanism - nothing to paste),
    the TOOL's plates drawn with a plan entry's arguments, size and legend (the plan, the
    author's), and the PLUGIN's own drawing (its file, the author's). This groups the open
    findings by kind, names the owner, prints the plan entry as declared or the code site,
    quotes the eye, shows an answer already given, and states the two answers: edit the entry
    or the code and bump the version; or `--answer` why the plate stays, for a looker to settle.
    It ends with the prediction the rerun is submitted with.

    ONE PLAN ENTRY IS ONE KIND, AND THE EYE IS QUOTED WHOLE (found by the cold author of blind
    0006). A per-item entry draws `patterns_incoming` and `patterns_outgoing` from one
    declaration; grouped by the drawn stem it surfaced as two headings, and a reader answering
    "each kind once" fixed the same entry twice. So a finding is grouped under the plan entry
    that claims its file where there is one, and under its drawn kind where there is none (the
    host's panels, a plate not on the plan). And the note was cut at 300 characters, which cut
    the actionable half of a two-clause finding often enough that the author read the ledger
    instead of the sheet: the words are the whole point of the sheet, so they are printed whole.
    """
    import json as _json
    from collections import Counter
    from . import declare as _DC
    from . import native as _NAT
    root = Path(out)
    of = open_findings(out, plugin)
    ans = read_answers(out, plugin)
    try:
        doc = _json.loads((root / RUN_MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    spec = (((doc.get("kernels") or {}).get(plugin) or {}).get("spec")) or {}
    entries = {str(e.get("id") or ""): e for e in _DC.report_figures(spec)}
    pf = Path(plugin_file) if plugin_file else _plugin_file(plugin)
    src = (pf.read_text(encoding="utf-8", errors="replace").splitlines()
           if pf and pf.is_file() else [])

    def sites(fid):
        return [i + 1 for i, l in enumerate(src) if f"'{fid}'" in l or f'"{fid}"' in l]

    by_kind = {}
    for rel, ws in sorted(of.items()):
        claimed = _NAT.entry_for(spec, Path(rel).name)
        by_kind.setdefault(claimed if claimed in entries else kind_of(rel), []).append((rel, ws))
    L = [f"# THE AUDIT'S WORKSHEET - {plugin} on {root.name}: {len(of)} open finding(s) on "
         f"{len(by_kind)} kind(s); answer each kind ONCE, the instances follow", ""]
    owners = Counter()
    for kind in sorted(by_kind):
        items = by_kind[kind]
        base = Path(items[0][0]).name
        stem = base.rsplit(".", 1)[0]
        host_key = ""
        if stem.startswith(f"{plugin}_"):
            tail = stem[len(plugin) + 1:]
            host_key = ("across_design" if tail.startswith("across_design")
                        else tail[:1] if tail[:1] in ("N", "C", "P") and tail[1:2].isdigit()
                        else "")
        fid = _NAT.entry_for(spec, base)
        e = entries.get(fid) or {}
        if host_key:
            owner = "HOST"
            where = (f"the host's own panel (scprofile/{_HOST_PANELS[host_key]}.py): mechanism "
                     f"- nothing to paste, the host fixes it and every plugin gets the fix")
        elif e and str(e.get("drawn_by") or "tool") == "tool":
            owner = "TOOL"
            where = ("the tool's plate; the plan entry is where it is adjusted (arguments, "
                     "size, legend), as declared:\n     "
                     + ", ".join(f"{k}: {str(v)[:60]!r}" for k, v in e.items()
                                 if k in ("id", "fn", "args", "w", "h", "legend", "axis",
                                          "position", "kind")))
        elif e:
            owner = "PLUGIN"
            where = (f"the plugin's own drawing; the plan entry {fid!r} and the code at "
                     + (", ".join(f"{pf.name}:{n}" for n in sites(fid)[:4]) if pf and sites(fid)
                        else "(the plugin's file is not in this tree)"))
        else:
            owner = "PLUGIN"
            where = ("not on the plan: the plugin's own drawing - declare it as an entry, then "
                     "adjust it")
        owners[owner] += 1
        L += [f"## {kind}   [{owner}]   {len(items)} instance(s) carry a finding",
              f"   {where}"]
        for rel, ws in items:
            L.append(f"   - {rel}")
            for w in ws:
                L.append(f"       {w}")
            if rel in ans:
                L.append(f"       answered by {ans[rel].get('by')}: {ans[rel].get('answer')}")
        if owner != "HOST":
            L += ["   ANSWER, one of:",
                  "     edit the entry or the code, bump `version` (the reuse key), run the "
                  "build gates (scprofile validate; the maker's status), then the rerun;",
                  f"     or, if this is the upstream's own drawing and right as it is: scprofile "
                  f"review --out {root} --plugin {plugin} --figure <path> --answer \"why\" "
                  f"--reviewer <you>   - a looker's fresh look then settles it;",
                  f"     or, if this is the upstream's own drawing and the finding is real but "
                  f"not the plugin's to cure: put one sentence saying so in the entry's legend, "
                  f"bump `version`, then scprofile review --out {root} --plugin {plugin} "
                  f"--figure <path> --answer \"that sentence\" --reviewer <you> --stated   - "
                  f"the finding closes when the declaration carries the words"]
        L.append("")
    L += [f"# owners: {', '.join(f'{k} {n}' for k, n in sorted(owners.items())) or 'none'}", "",
          "# PREDICTION for the rerun, to submit the job with: every kind edited redraws and is "
          "looked at again; the looks on unchanged images carry; the answered figures come back "
          "to a looker; `audited` names only what survives a fresh look."]
    return "\n".join(L)


def outstanding(out, plugin=""):
    """Figures needing a look: never reviewed, or redrawn since."""
    # A CARRIED LOOK IS A LOOK. It was taken on these exact bytes; which run it was taken in is
    # provenance, not a reason to demand it again.
    return [(r, st) for r, st, _w in status(out, plugin) if st not in (REVIEWED, CARRIED_OK)]


#: Below this many outstanding figures, splitting the work costs more than it saves.
SHARD_FLOOR = 12

#: A figure's KIND: what it is a picture of, with the unit or contrast it was drawn for stripped
#: off. `<stem>__S1` and `<stem>__arm_a` are one kind drawn
#: twice; a defect in how that kind is drawn is present in both and in every other instance.
#:
#: The stem is cut at the first `__`, which is the separator every figure id here uses between
#: what a panel is and which unit it is of, and then a trailing unit token is dropped.
def kind_of(rel):
    """The figure kind of a run-relative path."""
    stem = Path(rel).stem
    stem = stem.split("__", 1)[0]
    return re.sub(r"_[A-Za-z0-9]*[0-9]$", "", stem)


def _size(path):
    try:
        return Path(path).stat().st_size
    except OSError:
        return -1


def scan_set(out, plugin=""):
    """The figures an agent reads: every figure the paper numbers, plus the largest instance of
    every kind the paper does not show. Run-relative paths, sorted.

    ONE SELECTION (harness ADR-0017). Station 7 asked for every kind's largest and smallest
    instance and printed eight names; the agenda asked for the figures the paper cites;
    `--shards` split a third list; the station and the sampler each had their own definition of
    a kind. An agent that did exactly what one said was told by the other that nothing was
    done. This is the one set every reader counts: what a reader is shown - `FIGURES.txt`,
    written beside the brief - and one look at every other kind drawn, because a defect in how
    a kind is drawn is in every instance of it and one instance establishes it; the largest is
    the one that breaks a layout. `--all-figures` remains the audit of everything drawn.
    """
    root = Path(out)
    raster = (".png", ".jpg", ".jpeg")
    figs = [f for f in figures(out) if f.lower().endswith(raster)]
    if plugin:
        figs = [f for f in figs if f.startswith(f"kernels/{plugin}/")]
    paper = []
    if plugin:
        from .brief import FIGURE_LIST
        lst = root / "kernels" / plugin / FIGURE_LIST
        if lst.is_file():
            paper = [x.strip() for x in lst.read_text(encoding="utf-8").splitlines()
                     if x.strip() and (root / x.strip()).is_file()]
    have = {kind_of(p) for p in paper}
    by = {}
    for f in figs:
        k = kind_of(f)
        if k in have:
            continue
        if k not in by or _size(root / f) > _size(root / by[k]):
            by[k] = f
    return sorted(set(paper) | set(by.values()))


def by_kind(out, plugin="", per_kind=1, only=None):
    """Up to `per_kind` OUTSTANDING figures of every kind. Coverage before volume.

    A RUN DRAWS ONE KIND MANY TIMES. This cohort has 81 kinds across 819 figures: a circle plot
    per unit, a role heatmap per contrast, and so on. A defect in how a kind is drawn - a colour
    bar with no negative half, an absence rendered as a zero, a label over its own node - is in
    every instance of that kind, so opening one finds it and opening the other eighteen finds it
    again. Reading in path order spends the whole budget inside the first few kinds and never
    reaches the rest: here, 31 kinds had been looked at and 50 had never been opened at all.

    So this samples ACROSS kinds first. It is not a substitute for looking at everything - two
    instances cannot show that the nineteenth is fine - and `shards` still splits the whole
    outstanding set when that is what is wanted. It is what to do FIRST, and it is what to do
    when the figures are about to be redrawn: a review dies when its image changes, so a full
    sweep before a fix round is a sweep that gets thrown away.
    """
    left = [r for r, _st in (outstanding(out, plugin) or [])]
    if only is not None:
        want = {str(x).strip() for x in only if str(x).strip()}
        left = [r for r in left if r in want]
    seen, picked = {}, []
    for rel in sorted(left):
        k = kind_of(rel)
        if seen.get(k, 0) >= max(1, int(per_kind)):
            continue
        seen[k] = seen.get(k, 0) + 1
        picked.append(rel)
    return picked


def shards(out, plugin="", n=2, only=None):
    """Split the OUTSTANDING figures into `n` disjoint groups. Returns a list of lists.

    WHY THE TOOL DOES THE SPLITTING. Opening the figures is the slowest step in the cycle and the
    only one that parallelises without argument: the panels are independent, nothing is computed,
    and the record is append-only. An agent that wants to fan the step out across several agents
    otherwise has to invent a split - and an invented split is where the same figure gets two
    reviews and another gets none, which the ledger then reports as outstanding for ever.

    SIBLINGS STAY TOGETHER. Groups are formed by DIRECTORY first, because every plugin writes one
    directory per unit or per contrast, and the figures in one are the ones that have to be read
    against each other: a differential heatmap means little without the two arm networks beside
    it. Balancing figure counts while cutting a contrast in half would produce even shards and
    incoherent ones, and the note an agent can write about half a contrast is worth less than the
    minute the balance saved.

    The split is over what is OUTSTANDING, not over every figure, so a second pass after a partial
    review divides only what is left.
    """
    n = max(1, int(n))
    left = [r for r, _st in (outstanding(out, plugin) or [])]
    # RESTRICTED TO A DECLARED SET, WHEN ONE IS GIVEN. A run holds every figure it drew; the
    # brief's list holds the ones the PAPER is written from, which is a smaller set and the one
    # the writing step actually blocks on. Sharding the whole run would send agents to open
    # appendix panels no sentence will cite, before the panels every sentence will.
    #
    # The caller passes the list rather than the tool guessing it: `only` is any iterable of
    # run-relative paths - `kernels/<plugin>/FIGURES.txt` is the obvious one, and a plugin or a
    # site may have another.
    if only is not None:
        want = {str(x).strip() for x in only if str(x).strip()}
        left = [r for r in left if r in want]
    if not left:
        return [[] for _ in range(n)]
    groups = {}
    for rel in left:
        groups.setdefault(str(Path(rel).parent), []).append(rel)
    # Largest directory first into the emptiest bin: greedy, deterministic, and it keeps the
    # biggest indivisible unit from being the thing that unbalances the last bin.
    bins = [[] for _ in range(n)]
    for _d, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        j = min(range(n), key=lambda i: (len(bins[i]), i))
        bins[j].extend(sorted(members))
    return [sorted(b) for b in bins]


def summarise(out, plugin=""):
    """{state: count}."""
    c = {}
    for _r, st, _w in status(out, plugin):
        c[st] = c.get(st, 0) + 1
    return c
