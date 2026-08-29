# Development guideline

*Enforced by `.claude/hooks/dev_guideline.py`, which DENIES rather than reminds: tool code written outside the package, scProfile material written to a scratchpad, ad-hoc scProfile code run from a shell heredoc, a commit while any suite or `scprofile check` is red, and figure code committed while `check --deep` is red. What it cannot enforce is whether anyone LOOKED at a figure — `scprofile review` records that, and the count is printed on every figure-code commit.*

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
