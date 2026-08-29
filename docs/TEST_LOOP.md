# The test loop

**A tool is not tested by its own suite. It is tested by putting a project's real runs through
every element in order, and refusing to advance past a station that has produced no evidence.**

The suite proves a function returns. This proves the chain works on runs somebody actually made,
in the state they are actually in — some sealed, some not, some carded, some not — which is the
state a tool meets and a fixture never reproduces.

Run it with `python tests/loop_stations.py --runs <dir> --round N`. It reports each station,
names the evidence missing, and prints the one thing to do next. **It does not do the looking or
the writing** — nothing can — but it will not let the loop advance without them.

---

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
