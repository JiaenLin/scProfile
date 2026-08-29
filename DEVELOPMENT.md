# Development guideline

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
