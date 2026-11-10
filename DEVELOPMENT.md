> **Every change to this tool follows [the development contract](docs/DEVELOPMENT_CONTRACT.md):** it lands in this repository as mechanism or plugin content, it does not reduce what the tool delivers, and it is the smallest change that fixes the defect.

# Development guideline

*The gate is `.claude/hooks/dev_guideline.py`, run by git from the committed `setup/githooks`: **a push to `main`** is refused while any suite or `scprofile check` is red, or while it carries figure code and `check --deep` is red, and a commit made on `main` itself meets the same gate. A commit or push on any other branch meets none, so work in progress can be checkpointed while it is red; a change is judged when it is accepted, at `main`. A git hook fires in this repository whatever session, editor or terminal made the change — the split was paid for: a session rooted in the plugin maker's repository edited this one through the maker and met no gate at all, because the only trigger was keyed to the session's root directory. **Install the gate once per clone:* `git config core.hooksPath setup/githooks` *— `scprofile check` prints a warning until you do. The same file is a Claude Code `PreToolUse` hook for the session, and there it only reminds. The TEST LOOP below is how the tool is exercised against real runs; `docs/TEST_LOOP.md` is its design, and `docs/ANATOMY_OF_A_RUN.md` is every layer of one run as the code does it. What no hook can enforce is whether anyone LOOKED at a figure — `scprofile review` records that, and the reminder is printed whenever the gate passes figure code.*

**Deliverables live in the repository or in the run they came from.**
Code, tests, docs, skills, examples and the scripts used to look at a panel are committed here; a
run's outputs live in that run's directory. A scratch directory is a fine place to work and to
measure, and a poor place to keep anything: what is left there has no commit and no history.
Four manuscript drafts and every harness used to render a panel were once kept in one, so the one
reusable thing — a way to redraw a panel from a finished run — was rebuilt from memory each time.

Two consequences:
- **A script you will need twice belongs in `tests/`.** A one-line measurement from a shell is
  fine; `tests/preview_panels.py` exists because redrawing a panel kept being rebuilt instead.
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
reported working on the strength of the stations that happened to be easy. The reuse stations
(landscape, licence, adopt, merge) are `n/a` on runs that reused nothing - every first run of a
new cohort - and `n/a` does not block; one licence, `reused` or ADOPTED.json and they are asked.

`python tests/loop_stations.py --runs <dir>` names the first blocked station and the one thing to
do next. Four rules, each paid for:

- **Evidence, not assertion.** A file the station wrote; a MEASUREMENT of the filesystem rather
  than of the tool's report of itself — `ADOPTED … by hardlink` is a claim and `st_nlink` is a
  fact; or a recorded look bound to the image's digest.
- **Every bug found becomes a change with a failing test; a finding that is not a bug is
  answered (`review --answer`) or recorded.**
- **The gate is `python tests/run_all.py`, and nothing else.** It runs one subprocess per suite
  and the exit code decides, which is what `setup/dev_cycle.pbs` step 0 has always done. An
  ad-hoc runner that IMPORTS the suites instead reported green for a whole session: several
  suites call `sys.exit()` at module scope, `SystemExit` inherits from `BaseException` so it
  escaped the runner's `except`, and the runner terminated WITH CODE 0 - hiding every file
  sorted after it and two genuine failures. **Verify a gate by making it fail**: drop a test that
  asserts False and confirm non-zero, which is one command and would have caught this on day one.
  **And the gate runs under an interpreter that has the array stack** (harness ADR-0026, the
  open items): the hook's own interpreter had none, the CLI half of the status contract printed
  SKIP and exited 0, and a change that broke that contract was committed green. `run_all.py`
  runs the suites under `<repo>/.venv/bin/python` (or `$SCPROFILE_TEST_PYTHON`) when the running
  interpreter lacks anndata and that one has it, prints which, and counts every SKIP the suites
  printed in its summary - a green with skips says so. Make the `.venv` once per clone
  (`python3 -m venv .venv && .venv/bin/pip install anndata numpy pandas scipy h5py matplotlib
  PyYAML`; it is gitignored, and the portability scan skips what `.gitignore` names).
- **A wrapper uses the wrapped tool's own plots.** List them from the package, use them, and
  account for every one you do not - from the closed vocabulary in `scprofile/native.py`, which
  rejects "reimplemented", "not considered" and "dependency missing" by name. A reimplementation
  is legitimate only as `superseded_by_design`, naming the panel that replaces it AND the defect
  in the upstream encoding it corrects. A wrapper that has not done the accounting declares
  `wraps.plots_unreviewed` saying so, in its own file; `validate` refuses one that says neither.
  See `docs/FIGURE_STANDARD.md` §6.
- **Fix the mechanism that exists; do not add one beside it.** Every rule in
  `docs/FIGURE_STANDARD.md` names the function that enforces it, and each was a change to
  something already there - the contrast population set, the sentinel mask, the paper writer, the
  panel registry. A second mechanism doing the first one's job is how a codebase acquires two
  answers to one question, and the loop then reports on whichever it happens to read.
- **The loop's own weaknesses are written down, in `docs/TEST_LOOP.md`, and they are part of it.**
  Four are fixed and named with the failure that exposed them; four are open. A loop that
  presents itself as sound is the same defect as a gate that fires on correct behaviour — both
  ask to be believed rather than checked. Read that section before trusting a green run.
- **The eye scan and the written section are the evidence for the report's goal (harness
  GOALS A5.1); report coverage as N of M.** Stations 1 to 6b run in seconds and go green
  while a picture can still be wrong, so the loop prints the eye's count on every blocked run.
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
