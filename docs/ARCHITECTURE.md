# What scProfile is made of

scProfile is a **design-aware agentic research discovery workflow for single-cell data**: it takes
an annotated object and a design, and returns figures and a written result section in which every
claim is bound to a figure.

It is built in two halves that meet at the plugin runner. They are one workflow rather than two
tools because **the design table is the only place the experiment is described, and every stage is derived
from it** — the units a
method is fitted to, the comparisons that exist, the evidence each needs, the figure that answers
it, and the sections of the result.

**Part one — the platform harness.** Takes an annotated single-cell object and a design table,
resolves what can run, builds the environments, runs plugins, merges their outputs. Plugins are
plug-and-run: one file each, declared, no host change needed to add one.

**Part two — the agentic figure harness.** Takes the outputs of part one and produces figures and
a written result section. It decides what figures a design needs, prefers the wrapped tool's own
plots, checks what was drawn, records what a person saw, and binds every written claim to the
figures it was read off.

The boundary is the plugin runner. Everything before it is about getting a method to run
correctly. Everything after it is about turning the output into something a reader can check.

---

# Part one: the platform harness

## `declare.py` — the plugin contract

Defines what a plugin declaration may contain and validates it. A plugin is a `PLUGIN` dict and a
`run(ctx)` function in one file. `REPORT_KEYS` lists the keys the report block accepts; a key not
listed is rejected, and `report_get()` is the only way the host reads one, so the checker and the
reader cannot drift apart.

## `kernels.py` — finding plugins and where their output goes

Discovers plugin files, reads their declarations statically, and builds the command that launches
each. Also defines the output layout: `plugin_out()`, `plugin_report()`, `run_report()`. One
plugin, one directory, with its own figures, tables, report pages, manuscript and review ledger.

## `resolve.py` and the installer — environments

Resolves each plugin's declared requirements into an environment. Plugins with compatible
requirements share one. An environment is stamped with the lock it was built from; a stamp that
does not match the current lock means the environment is stale, not usable.

## `planner.py` — what would run, and what a result should contain

`plan()` reads the object and reports what each plugin needs, what it would produce, and what
blocks it. Runs nothing.

`result_spec()` takes a design table and a plugin declaration and returns the sections a result
should have — one per question the design supports, each with the panels that answer it. It reads
no run directory, so a result can be specified before any compute is scheduled.

`delivered()` matches a specification against the figures a run produced and names what is
missing.

## `design_panel.py` — the questions a design supports

`comparisons()` enumerates every question a factorial design can be asked, from the design table
alone:

- **marginal** — factor F pooled over everything else
- **simple** — factor F within one level of another factor, one per level
- **interaction** — whether the F response depends on G

A 2×2 gives 2 marginal, 4 simple, 1 interaction. Three factors give 3, 12, 3. A design cell with
no samples is reported as a gap, not offered as an interaction. A factor that splits the samples
identically to another is named as unanswerable-as-asked.

## `runner.py` — running a plugin

Launches a plugin with its own interpreter, in its own environment, with that environment's `bin`
on `PATH` so the plugin can reach binaries by name. Records what it ran, its memory and its exit.

## `_entry.py` — the shared entry point

Every plugin is launched through this, whatever its shape. It reads the input manifest, builds the
context, calls the plugin, and writes `out.json`. Phases:

- `run(ctx)` — one unit
- `compare(ctx)` — one pair of units, for a plugin that can compare its own results
- `selftest` — prove the environment works
- `guard` — refuse an object the method should not be run on

## `plugin.py` — what a plugin is given

`Context` for `run(ctx)`: the data, the labels, the design, the output directory, and helpers for
emitting figures and tables. `CompareContext` for `compare(ctx)`: two finished units and where to
write.

## `merge.py` — assembling the outputs

Merges per-unit results into one object and one payload, by barcode, with coverage stated. A cell
a plugin never saw is `NaN`, not a substituted value.

## Reuse: `landscape.py`, `licence.py`, `resume.py`

Finds earlier runs whose inputs match, grades what may be reused, and adopts products by hardlink.
The reuse key covers the plugin version, the inputs, the parameters and the host modules that
affect output. Adoption shares an inode; the check is `st_nlink`, not the tool's own claim.

---

# Part two: the agentic figure harness

## `evidence.py` — what a comparison needs, asked of the biology

`NEEDS` lists what a reader needs in order to believe a difference between two groups of cells —
which populations changed, what carries the difference, whether it is sending or receiving,
whether it is abundance or per-cell signal, whether absence is absence or reduction, and so on.
The registry names no method, no plugin and no drawing.

`FOR_QUESTION` maps question kinds to needs. `resolve()` decides how each need is met: the wrapped
tool's own function first, a host panel second, unresolved third. Unresolved is an answer — it
says the dataset cannot answer that part.

A plugin declares what it can supply in `report.provides_evidence`. Nothing outside the plugin
asserts it.

## `units.py` — what one run of a plugin is computed over

A unit is a set of cells the plugin is fitted to. There are two axes and both are produced:

- **group** — cells pooled by design arm. This is the axis the design was built to compare.
- **sample** — one unit per sample. An addition, never a gate: no group panel is withheld
  because an arm holds few samples.

The group axis carries two kinds of unit:

- **crossing** — one per combination of the biological factors (`old_ctl`, `old_trt`, …). These
  are the two sides of every simple effect.
- **marginal** — one per level of each factor, pooled over the others (`old`, `ctl`, …). These
  are the two sides of every marginal effect. Without them a marginal comparison has a question
  and no object, and any tool whose differential takes two fitted objects has nothing to take.

A factor is biological if it varies, is not the sample column, and is not named as technical by
the caller. `membership()` returns the samples behind every group unit and is the only place
that mapping is computed.

## `inputs.derive_design` — the design when no table is passed

A design table is preferred and always wins, because it can carry factors the object has never
heard of. When none is passed, the factors are read out of the object: **a factor is a column
constant within every sample.** Columns that vary within a sample, that are continuous, that
have one level, or that have one level per sample are refused, each for that stated reason. A
derived design is reported as derived, with its columns named.

## `native.py` — the wrapped tool's own plots

A plugin that wraps a tool inherits that tool's figures. Every one is either used or accounted
for. The reasons are a closed set:

- `not_applicable` — with evidence of what is absent
- `superseded_by_design` — naming the replacing panel and the defect in the upstream encoding
- `duplicate_of` — naming the function actually called

`reimplemented`, `not_considered`, `dependency_missing`, `too_slow` and `not_useful` are rejected
by name, each with the remedy. `OWES_ACCOUNTING` lists wrappers that still owe an accounting; it
may shrink and never grow.

`function_for(declared, filename)` inverts the declaration: given a file, it names the upstream
function that drew it. Two things use it. A panel's caption says which function drew it, so a
reader can check the panel against the tool's own documentation. And
`tests/test_plot_declarations.py` walks every plot call in a plugin's embedded script and
requires a declared function to claim each one — so the accounting and the code cannot drift, and
a function cannot be marked used while drawing nothing.

**The practice this enforces: list every plot function the wrapped tool exports, use all of them,
and account for each exception from the closed set above.** A skip is a claim about the data or
about a duplicate, never about effort or convenience.

## `panels.py` — the panel registry

Every panel kind, what it establishes, what it does **not** establish, its owner (host or plugin),
and the numbered rules it must obey. `SERVES` maps question kinds to panel kinds. `IMPLEMENTED`
records where each kind is drawn, so the registry and the drawing code cannot drift.

## `figure.py` — drawing, and what a machine can see

Publication conventions: column widths, colourblind-safe palette, live vector text. `audit(fig)`
inspects a figure before it is saved and reports text over text, text off the canvas, and a size
channel with no key. It reads every text on the panel — annotations, tick labels, titles, axis
labels, legends — and holds rotated decorations to matplotlib's own layout.

`spread_labels()` separates labels; `resolve_overlaps()` re-solves them after the host has
finished changing the canvas.

## `compare_panel.py` and `network_panels.py` — the host's panels

Contrast panels per arm pair, the interaction panel, and per-arm network panels. The population
set of a contrast is the **intersection** across its arms, decided before any matrix is built; a
population absent from one arm is removed and named, not drawn and masked.

`write_two_scale()` writes every contrast's change per element on both scales — raw and share of
the arm's own total — with the arm totals and whether the two agree in sign.

## The compare phase — the tool's own differentials

A plugin may declare `compare(ctx)`. The host runs it once per contrast, in the plugin's own
environment, handing over the two units' output directories and nothing else. The plugin decides
what its upstream can do with two fitted objects.

Two rules the host enforces around it:

- **The panels are placed.** They go on the arms page in their own section, above the host's own
  encodings, and are recorded in `panels.json` under `native` so the writing brief lists them.
  A figure that is drawn and not placed cannot be cited and is not delivered.
- **The two objects must be aligned before they are merged.** A differential that subtracts two
  per-arm matrices does so by position; two arms fitted separately need not carry the same
  groups. Where they do not, the subtraction either errors or silently compares one group against
  a different one. The plugin aligns using the wrapped tool's own function and asserts the two
  agree afterwards; `tests/test_native_plots.py` checks the alignment is a call and not a
  comment.

## `report.py` — the documents

Builds the index and each plugin's pages. Invokes a plugin's `compare(ctx)` once per arm pair
where a single unit pools each side of the contrast.

## `standard.py` — the exit standard

Ten criteria a rendered page must meet: panel count, caption length, arms named, prose present,
caveats present, nothing hidden, no repeats, identifiers resolved, no contradictions, an overview.
Applied by whatever writes the report, to what it wrote.

## `review.py` — what a person actually saw

A note per figure, bound to that image's sha256. Redraw the figure and the review is gone, not
old. A note must say something: empty, too short, or identical to another figure's note is
refused.

## `paper.py` — the result section as a page

`claim()` records a sentence with the figures it was read off; a claim citing nothing is refused.
`review()` records a verdict — standing, narrowed or withdrawn. `render()` writes the section, the
claims and every cited figure into one page, numbering the figures from `compose.figure_index` so
"Figure 3" in a sentence and the plate printed under Figure 3 are one object. `panel()` builds the
figure panel: one plate per piece of evidence each comparison needs.

One manuscript per plugin: `PAPER.<plugin>.md`, `PAPER_CLAIMS.<plugin>.jsonl`,
`report/<plugin>_paper.html`.

## `tests/loop_stations.py` — the test loop

Nine stations run in order against real runs: exists, landscape, licence, adopt, merge, report,
drawing, eye, paper, outputs. The loop stops at the first blocked station and names the one thing
to do next. The goal is the eye scan complete and the manuscript written; the earlier stations go
green long before the output is worth having.

# Part three: the agentic layer

The first two parts end with a run: numbers, figures, and documents that describe them. The
result — what the numbers mean — is not in them, and cannot be. This part is the interface
between the run and whoever writes that.

## `compose.py` — the section the tool can support

Builds a result section from the run's own tables, and nothing else. It walks the design's
comparisons in reading order, states each contrast's ratio on both scales, names the elements
that carry it, and cites the figures by the numbers `figure_index` assigns.

Three things in it decide the shape of the document:

**`figure_index`** numbers every figure once, in four passes — the design-wide panels a plugin
marks `overview`, then the reference group's profile, then each contrast's own panels in the
design's order, then the design-wide panels marked `conclusion`. A panel drawn across the whole
design belongs to no single contrast, so without this it was collected by whichever contrast was
read first, and the document opened with its own conclusion.

**`reference_unit`** is the arm sitting at the control level of every biological factor, named
with `units.group_label` — the same function that names a crossed arm everywhere else. It is the
pooled arm, not a sample inside it, because that is what every contrast is measured against.

**`_limitations`** ranks the run's own recorded caveats — a confound the design cannot separate
first, then a quantity with no test, then a measurement that is not comparable — deduplicates
what a plugin emitted once per unit, and caps the result.

The section it produces is marked as composed, and it is a fallback. It exists so a run nobody
writes up still has a truthful account of itself.

## `brief.py` — what an agent writes from

`WRITING_BRIEF.md`, one per plugin, written on every run. The contrasts in reading order with
their reference arms and both scales; every figure with the number the paper gives it and whether
it has been looked at; how many caveats the run recorded; and the template this plugin declares.
Every entry names the file it came from, and nothing in it is a sentence to reuse.

## `review.py` — what has actually been looked at

A review is bound to a figure's sha256, so redrawing a figure destroys its review rather than
leaving a stale one. A note under four words, or copied from another figure, is refused.

Looks carry between runs by reading the ledgers of sibling run directories — a sibling being a
directory that carries a `report.json`. Nothing is written outside the run being reviewed. This
matters because a run that reuses its fitted objects redraws nothing, and without the carry every
unchanged figure would need looking at again on every run.

## `agenda.py` — the cycle, and the agent's place in it

The whole cycle as an ordered list with the state of each step read off the run's artifacts:
run, read the brief, look at the figures, write, carry it in, defend the claims. State is derived
and never stored — a task is done when the thing proving it exists — so nothing here can report a
result as written after the composer has replaced it.

**Execution mode** changes one step and nothing else. Under `pbs` the compute runs detached on
another machine and cannot call back, so the agenda says to submit it, watch it, and collect its
output the moment `SEALED.txt` appears — which is what keeps submit, watch and collect one run
instead of three errands. Under `local` it runs in front of you. The mode is detected and always
stated, so a wrong guess is visible rather than silently shaping the instructions.

The agenda answers before a run exists, which is the point: an agent asking what the work is gets
the shape of all of it, including that the compute is detached, before it submits anything.

## The writing skill and the plugin's template

`.claude/skills/result-section/SKILL.md` is general and applies to every plugin: the document's
architecture, headings that name the comparison rather than the finding, the rule for which scale
a claim is made on when two disagree, the limitations cap, and the requirement to open the
figures before writing about them.

Each plugin **declares** the template it writes with, in `report.writing_template`. The template
carries what is specific to the method: what it infers, what a result of that kind supports and
does not, the levels a comparison is walked through, and the sentence patterns. The host never
maps a plugin name to a template — that is the one place where adding a second method quietly
stops working.

The two combine into one manuscript. Neither is complete alone: the skill without a template
knows no method, and the template without the skill has no document to fit into.

## Why the tool does not write

It used to. Headings were built from format strings, the limitations paragraph was ranked and
joined, a sentence was emitted whenever two scales diverged past a threshold. All of it
traceable, reproducible, and not writing — it cannot decide what matters, synthesise across
levels, or narrow to a focus, which is the one thing the guidance asks for.

So the tool measures and the agent writes, and `docs/AGENT_CONTRACT.md` states which half is
whose. The division is not a style preference: a tool that writes produces prose that reads
correctly and says nothing, and an agent that writes without the tool produces numbers with no
file behind them.
