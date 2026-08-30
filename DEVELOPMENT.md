# Development guideline

*Enforced by `.claude/hooks/dev_guideline.py`, which DENIES rather than reminds: tool code written outside the package, scProfile material written to a scratchpad, ad-hoc scProfile code run from a shell heredoc, a commit while any suite or `scprofile check` is red, and figure code committed while `check --deep` is red. The TEST LOOP below is how the tool is exercised against real runs; `docs/TEST_LOOP.md` is its design. What it cannot enforce is whether anyone LOOKED at a figure — `scprofile review` records that, and the count is printed on every figure-code commit.*

**THE REPOSITORY IS THE ONLY HOME.**
Every scProfile artefact — code, tests, docs, skills, examples, the scripts you use to look at a
panel — lives here and nowhere else. A run's outputs live in that run's directory. **There is no
third place**, and a scratchpad is not one: work put there has no commit, no history, and is gone
with the session that made it.

This was broken while the rule above it was being enforced. Four manuscript drafts and every
harness used to render a panel and look at it were written to a scratchpad, so the one thing that
could be reused — a way to redraw a panel from a finished run — had to be rebuilt from memory
each time and was never committed. *A figure in a scratchpad is a draft. So is everything else.*

Two consequences, both enforced:
- **Use the CLI, or commit the script.** Ad-hoc scProfile code in a shell heredoc is a script
  nobody can run twice. `tests/preview_panels.py` exists because that need is real and kept
  being met in the wrong place.
- **A written result belongs to its run.** `scprofile paper --write` puts it there, with a run
  key, bound to the figures it was read off.

**Ship it in the tool, or it does not exist.**
A figure, check or fix a run does not regenerate is a draft. Scratchpads decide what to build,
never deliver it. Wire it or delete it — nothing that nothing calls.

**Look at the real output.**
A green suite proves a file was written, not that it is right. Open every figure. Verify on real
data; a convenient fixture hides the bug it was built to catch.

**THE LOOP IS HOW THIS TOOL IS TESTED, and it is not optional.**
The suite proves a function returns. It cannot prove the chain works on runs somebody actually
made, in the state they are actually in. So a project's real runs go through every element in
order — `exists · landscape · licence · adopt · merge · report · drawing · eye · paper` — and a
station that has produced no evidence is **BLOCKED, never skipped**. Skipping is how a chain gets
reported working on the strength of the stations that happened to be easy.

`python tests/loop_stations.py --runs <dir>` names the first blocked station and the one thing to
do next. Four rules, each paid for:

- **Evidence, not assertion.** A file the station wrote; a MEASUREMENT of the filesystem rather
  than of the tool's report of itself — `ADOPTED … by hardlink` is a claim and `st_nlink` is a
  fact; or a recorded look bound to the image's digest.
- **Scan the whole set before fixing anything.** Every fix that changes a rendering makes a new
  run, and the review ledger binds to digests, so a new run resets the scan set. Fixing as you go,
  the eye station went 0 → 3 → 5 → 8 → 0 across five rounds while real defects were being found.
  Collect on one build, fix in one commit, rebuild, re-scan.
- **Every finding becomes a change in this repository, or it did not happen.** A defect seen and
  not fixed is a defect found twice.
- **The gate is `python tests/run_all.py`, and nothing else.** It runs one subprocess per suite
  and the exit code decides, which is what `setup/dev_cycle.pbs` step 0 has always done. An
  ad-hoc runner that IMPORTS the suites instead reported green for a whole session: several
  suites call `sys.exit()` at module scope, `SystemExit` inherits from `BaseException` so it
  escaped the runner's `except`, and the runner terminated WITH CODE 0 - hiding every file
  sorted after it and two genuine failures. **Verify a gate by making it fail**: drop a test that
  asserts False and confirm non-zero, which is one command and would have caught this on day one.
- **A wrapper uses the wrapped tool's own plots.** List them from the package, use them, and
  account for every one you do not - from the closed vocabulary in `scprofile/native.py`, which
  rejects "reimplemented", "not considered" and "dependency missing" by name. A reimplementation
  is legitimate only as `superseded_by_design`, naming the panel that replaces it AND the defect
  in the upstream encoding it corrects. `native.OWES_ACCOUNTING` is a ratchet over the wrappers
  that still owe one: it may shrink, never grow. See `docs/FIGURE_STANDARD.md` §6.
- **Fix the mechanism that exists; do not add one beside it.** Every rule in
  `docs/FIGURE_STANDARD.md` names the function that enforces it, and each was a change to
  something already there - the contrast population set, the sentinel mask, the paper writer, the
  panel registry. A second mechanism doing the first one's job is how a codebase acquires two
  answers to one question, and the loop then reports on whichever it happens to read.
- **The loop's own weaknesses are written down, in `docs/TEST_LOOP.md`, and they are part of it.**
  Four are fixed and named with the failure that exposed them; four are open. A loop that
  presents itself as sound is the same defect as a gate that fires on correct behaviour — both
  ask to be believed rather than checked. Read that section before trusting a green run.
- **THE GOAL IS THE EYE SCAN COMPLETE AND THE MANUSCRIPT WRITTEN. NOTHING ELSE IS THE GOAL.**
  A round ends when station 7 is at N of N and station 8 has produced the draft and its figure
  panel — not when the mechanical stations go green. Stations 1 to 6b are the cheap half: they
  run in seconds and pass while the pictures are still wrong and while no manuscript exists.
  A partial scan is an unfinished round and **must not be reported as progress**, however much
  the panels it did cover turned up; and a run with no `PAPER.md` and no `report/paper.html` has
  not produced its deliverables, whatever else it wrote. The loop prints the distance to the goal
  as a count on every blocked round, and names every required output that is missing, because
  both have been abandoned short of the goal while being described as going well.
- **Move what you can from the eye to a measurement.** The eye is the slowest station and the only
  irreplaceable one. Three of the first eleven defects were mechanical — text over text, a label
  off the canvas, an unkeyed size channel — and are now measured by `emit_figure` on every panel
  of every run. **Each class that moves makes every future round cheaper, permanently.**

**A round that finds nothing is a result** — the only evidence a previous fix worked. The loop
ends when a complete scan produces no fix, and that is the only definition of "the figures are
right" this tool has.

**Use the wrapped tool's own statistics.**
Never invent an effect size, interval or p-value beside them. A descriptive panel is fine and
must say it is descriptive.

**The group is the unit; the sample is confidence.**
Single-cell inference is over pooled cells. Never gate a result on sample count; state `n`.

**Nothing in the host names a project or a method.**
Factors, levels, tissues, plugin names — none belong in host code or docs.

**A preview must match the action.**
`plan` and `run`, dry-run and `--grant`: one decision function, two callers.

**Every check must be able to fail.**
Break it deliberately and watch it go red before trusting it green.
