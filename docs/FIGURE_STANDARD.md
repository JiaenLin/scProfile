# The figure standard

**A figure set is finished when someone can write the paper from it and the paper survives
review.** Not when the suite is green, not when the panels are pretty, not when the exit
standard passes. Those are necessary and none of them is the test.

This document is the test, and the rules the test produced. Nothing here names a project, a
method, a tissue or a factor: every rule below was found on real data and every one of them is
about a shape, not a subject.

---

## The test: write the paper

**It is a command, not a habit:** `scprofile paper`. How to run it, and — importantly — the eight
things it does not yet cover, are in [`PAPER_TEST.md`](PAPER_TEST.md). The rest of this section is
why it works.


Take the figure set. Write the Results section a scientist would submit — the claims, the
numbers, the figure callouts, the limitations. Then have it reviewed against how papers are
actually judged, and revise. Repeat until the section stops changing.

**Every round removes something, and what it removes is a missing figure or a wrong one.**
That is the whole mechanism: a claim you cannot write down is a figure that does not exist, and
a claim that dies under review is a figure that was misleading you.

Four things make it work:

1. **Write the claim, not a description of the panel.** "Figure 3 shows the comparison" tests
   nothing. "X is higher in A than in B, and the difference reverses in C" is a claim, and a
   claim can be wrong.
2. **Check every number against its own denominator before writing it.** Most of what dies,
   dies here.
3. **Review against real standards, not your own.** How does the field judge this kind of
   claim? What would a specialist demand? Grounded review — real papers, real practice — beats
   imagined review, because imagined reviewers only know what you know.
4. **Run it more than once.** One round finds the obvious. The rounds after it find the ones
   that survived because you believed them.

**Do not tune the test to one dramatic failure.** The point is not to find the worst panel; it
is to find every claim the figure set cannot support, including the boring ones. A round that
returns "this is fine" for most panels and one real problem is a normal round.

### What one full pass looked like

Four rounds on one figure set, and what each removed:

| round | the claim going in | what came out |
|---|---|---|
| 1 | a factor changes total signalling | it was the groups' totals, four-fold apart |
| 2 | a switch between two pathway families | half of it was a self-interacting pair behaving as an abundance readout |
| 3 | one named pathway leads the effect | the ranking was not stable across scales; the "control" led the other scale |
| 4 | — | the effect survives; the identity of what carries it does not |

The section ended weaker and true. Three of the four rounds produced a code change, and those
changes are the rules below.

---

## The rules

Each was paid for by a real defect on real data. They are in `scprofile/panels.py` as
`RULES`, so a panel kind can declare which bind it and a test can check.

### R1 — One scale across a grid, never per panel

A grid whose panels each use their own maximum makes the widest mark in every panel look
identical whatever it is worth. Compute the maximum over the whole grid and **print it**, so a
width converts back to a number.

*Measured: one panel's widest edge 0.0120 against another's 0.0384 — a factor of 3.2 — both
drawn at full width.*

### R2 — Absence is not zero, and it is not one thing

An element with nothing has two causes that look identical and mean opposite things: it was
measured and returned nothing (a result), or it never cleared a threshold (a threshold). Mark
them differently and say which is which, or say the panel cannot tell them apart.

### R3 — A cut must name what it removed

Any panel that draws a subset to stay readable is performing a removal. State the fraction of
the total kept and **name what is left out**. Keep each element's strongest link whatever its
rank, so nothing vanishes for being weak.

### R4 — A denominator that is not what it looks like must be declared

Averaging over N while a quantity was measurable in fewer than N divides by N anyway.

### R5 — A per-object scale is not comparable across objects

Where each unit is normalised within itself, marks compare within a panel and rank-order across
panels. Nothing more.

### R6 — No panel is gated on the sample axis

Draw the group comparison first, from members pooled, whatever the group sizes. Add the
per-member view where the design supports it. State n; never withhold.

### R7 — A compositional readout is checked on a second scale

Where values are shares of a total, a **linear** difference ranks by what is abundant and a
**log-ratio** ranks by what changes most in ratio. Both are correct arithmetic on the same
numbers and they routinely disagree. A panel that **names elements** is claiming an ordering, so
compute both, compare the top ranks, and where they disagree say so on the panel and decline to
present your ordering as the finding.

*Measured: the element leading the linear ranking was mid-table on the log ranking — and the
element leading the log ranking had been used as a control, on the grounds that it did not move.*

### R8 — A difference of presence is not a difference of magnitude

In a comparison between two sets, an element present in one and absent from the other
contributes its whole value as a "change", in whatever encoding looks most like a finding: the
extreme of a colour scale, an empty bar beside a full one, an arrow from the origin. It also
sets the limits and compresses every real difference. Mark those elements, take them **off** the
magnitude scale, and name them. Do not drop them — a dropped row is invisible.

*Measured: with those elements off the scale, a colour range fell from ±150 to ±50 and a
pair-specific pattern appeared that had read as a uniform shift.*

### R9 — A contrast states what it cannot separate

Aliasing is a property of the **comparison**, not only of the factor pair. Two factors can be
perfectly crossed over a whole cohort and still be aliased inside one conditional contrast,
because conditioning discards the samples that crossed them. Audit the samples the panel
actually compares; report aliased, partly confounded, or balanced, on the panel.

*Measured: a design correctly reported as crossed contained a conditional contrast whose two
sides shared no level of a technical factor at all.*

### R10 — A panel names on its face what it was drawn from

A caption does not travel with an image into a slide, a grant or a referee's PDF. Unit, what
kind of unit, and n go **on** the figure. A pooled group and a single member render identically
otherwise, and a reader supplies the cohort the picture never claimed.

### R11 — Where the weight is normalised within a unit, compare shares and print the totals

Many methods return a quantity computed over the elements present, so two units' values sit on
two scales and a raw difference reports mostly which unit is smaller. Whether a weight is
per-object or absolute **is not knowable from the numbers** — it is declared, and the
conservative reading is the default.

*Measured: four groups whose totals spanned a factor of four. The raw comparison found no
reversals in the whole design; the share comparison found five.*

---

## Choosing which figures are main and which are supplementary

The test decides this too, and the rule is short: **a main figure is one the Results section
cites for a claim.** Everything else is supplementary, however good it looks.

Three corollaries that come up every time:

- **The panel showing what the analysis was GIVEN belongs in the main figure**, before any
  result. Every per-unit panel draws the axis its own unit happens to have, and a reader who
  meets a result before meeting that has already taken a missing element for a silent one.
- **The interaction, where the design supports one, outranks the main effects.** A marginal
  effect can be flat while both halves are large and opposite. Lead with the question, not its
  summary.
- **A panel that answers the same question twice in different units is one main panel**, and the
  other variant is supplementary. Prefer covering distinct questions over covering one question
  thoroughly.

---

## What this standard does not do

- It does not make a result true. It removes claims the figures cannot support; what remains is
  still an inference from one assay.
- It does not replace looking at every image. Three of the defects above were found by opening a
  PNG and none by any check.
- It does not scale down. A small figure set needs the test as much as a large one — a set of
  five panels can support a wrong paper just as easily.
- **It cannot tell you whether the biology is right.** The best outcome of a full pass is a
  section that is honest and modest, and the next step after that is usually an orthogonal
  measurement rather than another figure.

## Five rules for a comparison panel

Each names the mechanism that already enforces it. None of them is a new subsystem: where a rule
needed code, it changed an existing function.

### 1. A cell that cannot hold a comparison is not drawn where comparisons are read

The population set of a contrast is the **intersection** across its arms, decided in
`compare_panel.contrast_populations()` before any matrix is built, and the edges are filtered to
it. What is removed is returned BY NAME with the arm that lacked it, and the caption states it.

This replaced masking in the plot. The union was drawn first with absent rows and columns hatched
— honest, and still wrong: on a real cohort it put two full rows and two full columns of hatch
through the middle of a 13×13 matrix, 48 of 169 cells, breaking every real block in half. Removal
belongs at source; the *fact* of removal belongs in the caption. Locked by
`tests/test_contrast_populations.py`, which also asserts no `hatch=` survives in the contrast code.

### 2. The label column and the sentinels are a run decision, and sentinels are already held out

`EXCLUDED` and `UNRESOLVED` are `manifest.DEFAULT_SENTINELS`; `ctx.live_mask()` keeps them out of
every grouping, so no plugin has to remember. Which label column to profile is `--label`, and a
forced or resolved column is the one to pass when the unresolved fraction carries no information.
Nothing new is needed for this — the mechanism exists and the decision is at the invocation.

### 3. Use the wrapped tool's own plot and its own statistic

Step zero of the `plugin-figures` skill, and it is a rule about *where the effort goes*, not about
quality: resolve what the tool would draw, establish whether it is reachable, and then choose
NATIVE, deliberate reimplementation, or transcription under constraint. A reimplementation is
legitimate and must be declared as a departure with the defect it corrects named. The statistic is
never invented: `upstream.defaults_changed` and `cannot_show` are where that is recorded.

### 4. One manuscript per plugin, never one per run

A run mounts several methods answering different questions on different evidence; one section
covering all of them reads as a survey of the tooling, and its figure panel is a gallery.
`paper --plugin <name>` writes `PAPER.<name>.md`, `PAPER_CLAIMS.<name>.jsonl` and
`report/<name>_paper.html` — the last matching the `<plugin>_by_arm.html` convention `report.py`
already uses, so the four pages of one plugin sort together.

### 5. The panel kinds and their rules are declared, not re-derived

`scprofile/panels.py` is the registry: every kind, what it establishes, what it does NOT, its
owner (host or plugin), and the numbered rules R1–R11. A new panel is a registry entry, and the
loop checks drawing against that registry rather than against a list somebody keeps in their head.

## 6. List the tool's own plots, and use them

**A wrapper inherits the figures of the tool it wraps.** Every one is either used, or accounted
for with a reason the mechanism accepts — otherwise the wrapper is re-inventing a worse version
of something that already ships, and nobody finds out because nobody counted.

The practice, in order:

1. **List them.** Not from memory — from the package, in the plugin's own environment. CellChat
   exports 30 plotting functions; the hand-taken list was wrong in two ways at once, and the
   check that reads `getNamespaceExports` found both.
2. **Use them.** This is the default and it needs no justification. `{"use": "<where it lands>"}`.
3. **Account for the rest**, from a closed vocabulary in `scprofile/native.py`:
   `not_applicable` with evidence, `superseded_by_design` naming the replacing panel *and* the
   defect it corrects, or `duplicate_of` naming the function actually called.

**Three answers are rejected by name**, because they are the ones that get given:
`reimplemented` (the instruction is to use the tool's plot), `not_considered` (an omission
wearing the clothes of a reason), and `dependency_missing` (a package one install away is not a
design decision). Each rejection carries the remedy.

**What this was worth, measured.** Asked how many of CellChat's 30 plotting functions the plugin
used, the answer was **one** — and only for its numbers; the R script contained no `ggsave`,
`png()` or `pdf()` call at all. After the accounting it is **14**, and four of those answer a
design comparison directly. The gap was never a decision; it was never counted.

**It is a ratchet.** `native.OWES_ACCOUNTING` names the wrappers that still owe one. The list may
shrink and never grow: a new wrapper arriving without an accounting fails the suite, while the
named debt stays visible. Without that, this section is advice, and advice is followed until
somebody is in a hurry.
