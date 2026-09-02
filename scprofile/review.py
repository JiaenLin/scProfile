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


def sibling_runs(out):
    """Other RUN directories beside this one. A run is a directory carrying a `report.json`.

    Being a sibling directory is not enough - the parent of a run is not always a run root, and
    treating it as one carries looks between unrelated runs.
    """
    here = Path(out).resolve()
    try:
        return sorted(d for d in here.parent.iterdir()
                      if d.is_dir() and d != here and (d / RUN_MARKER).is_file())
    except OSError:
        return []


def read_carried(out, plugin=""):
    """{sha256: entry} - looks taken on sibling runs, keyed by the IMAGE they were taken on.

    Read from each run's OWN ledger. A review is bound to a figure's bytes, so an unchanged image
    carries; nothing else does, and nothing is written outside the run being reviewed.
    """
    seen = {}
    for run in sibling_runs(out):
        for rel, rec in read_ledger(run, plugin).items():
            sha = str(rec.get("sha256") or "")
            if sha:
                seen.setdefault(sha, dict(rec, run=run.name))
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
        if isinstance(rec, dict) and rec.get("figure"):
            seen[str(rec["figure"])] = rec
    return seen


class Refused(Exception):
    """A note that does not evidence a look. Raised, never returned - see the module docstring."""


def record(out, figure, note, *, reviewer="", plugin=""):
    """Append one review. REFUSES a note that cannot have come from looking.

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
                                                                time.gmtime())}
    ledger_path(root, plugin).parent.mkdir(parents=True, exist_ok=True)
    _append_line(ledger_path(root, plugin), json.dumps(rec))
    return rec


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
    rows = []
    for rel in figures(out):
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


def outstanding(out, plugin=""):
    """Figures needing a look: never reviewed, or redrawn since."""
    # A CARRIED LOOK IS A LOOK. It was taken on these exact bytes; which run it was taken in is
    # provenance, not a reason to demand it again.
    return [(r, st) for r, st, _w in status(out, plugin) if st not in (REVIEWED, CARRIED_OK)]


#: Below this many outstanding figures, splitting the work costs more than it saves.
SHARD_FLOOR = 12

#: A figure's KIND: what it is a picture of, with the unit or contrast it was drawn for stripped
#: off. `native_circle_weight__Aging1` and `native_circle_weight__young_chow` are one kind drawn
#: twice; a defect in how that kind is drawn is present in both and in every other instance.
#:
#: The stem is cut at the first `__`, which is the separator every figure id here uses between
#: what a panel is and which unit it is of, and then a trailing unit token is dropped.
def kind_of(rel):
    """The figure kind of a run-relative path."""
    stem = Path(rel).stem
    stem = stem.split("__", 1)[0]
    return re.sub(r"_[A-Za-z0-9]*[0-9]$", "", stem)


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
