# The test loop

**What it is.** Nine stations run in order against a project's real run directories. Each asks
one question, answers it from evidence on disk, and either passes or blocks. The loop stops at
the first block and names the one thing to do next. `python tests/loop_stations.py --runs <dir>`.

**What it is for.** The suite proves a function returns. It cannot prove the chain works on runs
somebody actually made, in the state they are actually in. Every figure defect this tool has ever
had was found by opening an image while the suite was green.

## The nine stations

| # | Station | The question it asks | Answered from |
|---|---|---|---|
| 1 | `exists` | Did anything actually run, and what died? | instance directories on disk |
| 2 | `landscape` | Does the reuse layer see what is reusable? | licence records across runs |
| 3 | `licence` | Is reuse GRADED, or waved through? | refused / retrospective / provisional / full |
| 4 | `adopt` | Was an adopted product really shared, or copied? | `st_nlink` on the product files |
| 5 | `merge` | Does a run record what it took from elsewhere? | the run's own merge record |
| 6 | `report` | Did the documents assemble? | rendered reports |
| 6b | `drawing` | What can a MACHINE see wrong in the panels? | the per-figure audit in `report.json` |
| 7 | `eye` | Are the pictures right? | a recorded look per figure, bound to its sha256 |
| 8 | `paper` | Can a result be WRITTEN from these figures, and survive review? | claims, citations and verdicts |
| 9 | `outputs` | Did the run produce every deliverable? | the five required files |

### Station 8, in full, because it is the one that decides whether any of this was worth doing

The first seven stations ask whether the machinery worked. **Station 8 asks whether the output is
worth having**, and it is the only station that can fail on a run where everything ran perfectly.

It works like this. `paper --brief` prints what the run holds ready to write from: the design, the
arms, the populations that cannot carry a comparison, the upstream constraint that binds any
claim, and every panel a reader meets first with the caption it carries. You write a result
section from that — and each sentence you would put in a paper is registered as a **claim** with
`--claim`, citing the figures it was read off with `--cites`. A claim citing nothing is refused.
Then the claim is put to review with `--round`, and the verdict is one of three: `standing`,
`narrowed`, or `withdrawn`.

Three properties make it a test rather than a writing exercise:

- **A claim is bound to the sha256 of every figure it cites.** Redraw a cited figure and the
  claim goes stale, because the sentence was read off a picture that no longer exists.
- **`withdrawn` is the verdict that teaches.** A loop where nothing is ever withdrawn has not
  been pushed on, and the station says so on its own output line rather than leaving it to be
  noticed.
- **Missing figures surface here and nowhere else.** Nothing in stations 1 to 7 can tell you a
  panel that should exist does not. It becomes visible when somebody tries to write the sentence
  that needs it and finds nothing to cite.

The station's output is `PAPER.md` and `report/paper.html` inside the run — the section, the
claims, their verdicts, and every cited figure inline — so the writing travels with the figures
it was read off and carries the same run key.

## The stations, in order

Reuse first, because everything downstream is built on results the tool decided were fit to
build on. Manuscript last, because it is the only station that asks whether any of it supported
a claim.

| # | station | asks | evidence it must leave behind |
|---|---|---|---|
| 1 | **exists** | what do these runs already hold? | `status` per run: every instance in one of five states |
| 2 | **landscape** | which results could a new run reuse? | candidates named, with the run each came from |
| 3 | **licence** | is any of it fit to build on? | a grade per instance, from the criteria, on disk |
| 4 | **adopt** | does reuse actually reuse? | `ADOPTED` lines, and **the shared inode measured** |
| 5 | **merge** | did the adopted result reach the object? | the merged object's columns, per adopted instance |
| 6 | **report** | is the page readable? | `standard` on the rendered HTML, per criterion |
| 6b | **drawing** | what can a machine see wrong? | an audit recorded on every panel as it was written |
| 7 | **eye** | are the pictures right? | a review ledger entry per figure in the scan set |
| 8 | **paper** | does any of it support a claim? | claims, verdicts, and a rendered section in the run |

**A station is BLOCKED, not skipped, when its evidence is absent.** Skipping is how a chain gets
reported working on the strength of the stations that happened to be easy.

---

## What counts as evidence

Three kinds, and an assertion is none of them:

- **A file the station wrote**, that a later reader can open — a ledger, a licence, a card.
- **A measurement of the filesystem or the object**, not of the tool's own report of itself.
  Station 4 is the example: the tool says `ADOPTED … by hardlink`, and the station believes it
  only after comparing inode numbers. *A tool's account of its own behaviour is a claim.*
- **A recorded look**, with a note that says what was seen. Bound to the image's digest, so a
  redraw destroys it.

---

## Station 6b: spend the eye only on what a machine cannot see

The eye station is by far the slowest, and the first eleven defects it found included **three
that a measurement can make**: text printed over text, a label clipped by its own canvas, and a
size channel with no key. Every one of them also shipped, because nothing looked at the figure
between drawing it and writing it.

Those are now measured by `emit_figure` at the moment the figure is complete and the artists are
still live, and recorded on the panel. Station 6b reads them. It **reports and never refuses**: a
panel it catches is usually still worth shipping, and a gate that blocks a run over a label two
pixels out is a gate somebody removes.

**This is what makes the loop converge.** Each defect class that moves from the eye to a
measurement makes every future round cheaper, permanently. The eye is then spent on the kinds
that have no mechanical form — a scale that hides its own finding, a rank rule that returns a
boundary, absence drawn as a measured zero, a claim the picture does not support.

## The eye scan, and its coverage rule

Nothing mechanises looking, and the defects that matter are only found by it — a chord drawn as
a starburst, labels driven off the axes, an absent population drawn at the origin. Every one of
those passed a green suite.

**But "look at every figure" is not a rule anybody follows twice.** A run of a few hundred
figures is a few dozen *kinds* repeated over units, and a drawing defect lives in the kind. So:

> **Scan every distinct figure KIND once, plus every panel on the page a reader meets first.**
> Kind is the id with its unit suffix removed. Where a kind is drawn per unit, scan the instance
> from the LARGEST unit and the SMALLEST — the two that break layouts.

That is a stated, repeatable rule with stated coverage, and the driver prints the worklist. A
scan that covers three quarters of the kinds is a scan that says so.

---

## The round

1. Run the driver. It names the first blocked station.
2. Clear that station — run the command, do the looking, write the claim.
3. **Every finding becomes a change in this repository, or it did not happen.** A defect seen and
   not fixed is a defect found twice.
4. Commit, push, and if the finding changed what a run produces, make a new run rather than
   editing one: a run key names the commit that produced what is in the directory.
5. Start the next round from station 1, because a change upstream invalidates what is downstream
   — that is what the digests are for.

**A round that finds nothing is a result**, and it is the only evidence that a previous round's
fix worked. Record it as a round.

### Scan the whole set BEFORE fixing anything — the loop converges only if you do

Every fix that changes a rendering makes a new run, and the eye ledger is bound to each image's
digest, so **a new run resets the whole scan set to unreviewed.** Fix as you go and the station
never fills: the counter went 0 → 3 → 5 → 8 → 0 across five rounds while eight real defects were
being found and fixed, because each fix rebuilt the figures the previous looks were recorded
against.

That is the ledger behaving correctly — a look at a picture that no longer exists is not evidence
about the picture that does. But it means the loop has a shape:

> **Scan the complete set on ONE build, collecting every finding and fixing nothing. Then fix
> them all in one commit, rebuild, and re-scan to verify.**

Two builds per round instead of one per defect. The station passes when a complete scan produces
no fix, which is also the only definition of "the figures are right" this loop has.

---

## What this loop does not do

- **It does not prove the science.** Every station is about whether the tool did what it says.
- **It tests the elements a project's runs exercise.** A project that runs one plugin over one
  design leaves the rest untested, and the driver prints which commands were never reached.
- **It cannot see a missing station.** The list above is what is known to matter; a chain has as
  many failure modes as it has links, and this is the eight somebody thought of.

## An intermittent defect is cleared by a BUILD, not by a run

Station 6b reads what a machine can see in the panels. It was written to clear when the newest
run is clean, which is wrong, and the loop found out how:

> The same commit drew the same panels from the same data twice. One run reported five text
> collisions across two panel kinds; the next reported none, on 140 panels. Neither run adopted
> anything — both drew afresh, from identical inputs. So the placement is not deterministic
> across runs, and which of the two a station happens to read decides whether it passes.

A station that clears on whichever run was clean signs off a build that still ships the defect
to whoever runs it next. **So the station clears a commit, not a run:** it reads every run of
the same tool version and holds open while any of them shows an issue. A build that genuinely
fixed the defect is clean in all of its runs; a build that did not is caught by the run where
the defect appeared.

Two consequences worth stating plainly, because both are easy to get backwards:

- **A single clean run is not evidence of a fix.** It is evidence that this run was clean. To
  claim a fix, either show the defect gone in every run of that build, or show why it cannot
  occur.
- **Do not chase an intermittent defect by reconstructing the panel.** Three attempts to
  reproduce those collisions from the panels' own coordinates all came back clean, which cost
  more than the fix did. Where a defect is measured by the tool, extend the tool's measurement
  until it says where and when — a defect report a person has to re-derive is half a mechanism.

## THE GOAL OF THE LOOP IS STATION 7 COMPLETE. NOTHING ELSE IS THE GOAL.

**The loop has now been abandoned short of its goal twice, and both times it looked like
progress.** This section exists because a round that clears every machine check reads like an
achievement and is not one.

The stations divide into two halves that are not comparable:

- **Stations 1 to 6b are the cheap half.** They are mechanical, they run in seconds, and they go
  green long before the tool is any good. A build can pass every one of them and still ship
  panels whose labels name no point, whose axes hide the result, and whose blank cells mean two
  different things.
- **Station 7 is the loop.** Every figure defect this tool has ever had was found by opening the
  image while the suite was green. A round that clears the machine checks and looks at six
  panels of eighty-four has tested almost nothing.

So:

1. **The goal is station 7 at N of N, then station 8.** Not "station 7 started", not "the
   blocking mechanical defects cleared". The scan is complete or the round is not finished.
2. **A partial scan is never reported as progress.** "6 of 84 looked at" is an unfinished
   round, and describing what those six found does not change that. The loop prints the count on
   every blocked round for this reason.
3. **Running out of things that are easy to fix is not a reason to stop.** It is the point at
   which the loop starts doing what it exists for.
4. **Only two things legitimately interrupt a scan**: a defect that makes the remaining panels
   not worth looking at, and the end of the set. Neither is "I have enough to report".

The convergence rule still applies inside the scan: look at the complete set on ONE build
fixing nothing, then fix everything in one commit, rebuild, and re-scan. Fixing mid-scan
invalidates the reviews already recorded, because a review is bound to its image's sha256.

## Where this loop is weak

Every entry below is a failure that happened, not a risk that might. Four are fixed; the rest are
open and named, because a known weakness is worth more than a clean-looking list.

### FIXED — the audit could see only a third of the text on a panel

It collected `ax.texts` and `fig.texts` — annotations and explicit `text()` calls — and nothing
else. **Tick labels, axis titles, axis labels and legend entries were invisible to it.** An eye
scan of 84 panels found five text collisions the audit had passed, and all five were of exactly
that kind. A check that covers a third of a panel and reports silence is worse than no check,
because the silence is read as a result.

Two things had to change together. The collection now takes every text on the figure; and
**decorations are held to a different tolerance from annotations**, because they are different
kinds of object. An annotation may overlap another slightly at a corner and stay readable, which
is what the 20%-of-the-smaller-box rule is for. Two tick labels sit on a shared baseline, so any
overlap at all is glyphs touching: `0.00.20.40.60.81.0` was passed at 12% overlap and is the least
readable thing in the run it came from. Decorations also do *not* join the off-canvas check — they
live in the margin by design and `bbox_inches="tight"` grows the canvas to hold them; adding them
to it reported eight failures on a three-bar test figure.

### FIXED — nothing measured how often the loop condemns a correct panel

The audit had been wrong in both directions — it reported 14 correctly keyed panels as unkeyed,
and it passed five collisions — and neither error rate was measured. `tests/test_audit_control.py`
is a negative control with **both halves**: five panels built to be sound that it must be silent
on, and four broken in one named way each that it must catch. Both halves are load-bearing.
With only the broken half, a check can be made to catch everything by lowering a threshold, which
is how a gate becomes noise; with only the sound half it can be made to catch nothing, which is
how a gate becomes decoration.

### FIXED — the driver that judges every round was itself unjudged

`loop_stations.py` named a station defined further down the file and raised `NameError` at import,
so it reported **nothing at all** — which looks like the loop was not run rather than like the
loop failed. It shipped because the gate runs `tests/test_*.py` and the driver is not one, and
because the check run against it was `ast.parse`, which parses without executing and cannot see an
undefined name. `tests/test_loop_driver.py` now imports it and asserts every named station is
callable.

### FIXED — a clean run was mistaken for a clean build

The same commit drew the same panels from the same data twice, producing five collisions once and
none the next, neither run adopting anything. Station 6b now clears a **commit**, not a run.

### OPEN — a host change resets the entire eye scan

A review is bound to its image's sha256, which is right: a redrawn panel has not been looked at.
But a change in the *host* redraws every panel of every plugin, so one line in `figure.py` costs
all 84 recorded looks. Measured across five rounds, the eye station went 0 → 3 → 5 → 8 → 0 while
real defects were being found. The convergence rule — scan the whole set on one build, fix in one
commit, rebuild, re-scan — is a discipline working around this, not a solution. **What would fix
it:** carry the *findings* forward across a redraw, so a re-scan starts from what was last seen on
that kind rather than from nothing.

### OPEN — no claim has ever been withdrawn

Twelve claims, two narrowed, none withdrawn. Station 8 prints this on its own line, which is
better than hiding it, but printing a weakness is not testing for one. **What would fix it:** a
station that requires at least one claim to have survived a deliberate falsification attempt,
scoring the pressure applied rather than counting the rounds.

### OPEN — the loop does not ask whether a figure is COMPREHENSIBLE

A correct claim read off an unreadable panel passes every station. Legibility is checked
mechanically only for collisions and clipping; nothing asks whether the encoding can be decoded.

### OPEN — stations 1 to 6 have never failed

They are structural guards against regression, and they were green on every round of this loop
while real defects existed. Six green rows read as progress and are not. **They should be
reported as a block, not as six items**, so the eye goes to 6b onward.

### OPEN — one design shape, one assay

The loop has been run against a 2×2 with one library per animal, on single-nucleus mouse heart.
One factor, three factors, no design at all, time-course and nested designs are all untested, as
is any assay but this one.
