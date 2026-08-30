# What scProfile is made of

scProfile is two harnesses joined at the plugin runner.

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

## `native.py` — the wrapped tool's own plots

A plugin that wraps a tool inherits that tool's figures. Every one is either used or accounted
for. The reasons are a closed set:

- `not_applicable` — with evidence of what is absent
- `superseded_by_design` — naming the replacing panel and the defect in the upstream encoding
- `duplicate_of` — naming the function actually called

`reimplemented`, `not_considered`, `dependency_missing`, `too_slow` and `not_useful` are rejected
by name, each with the remedy. `OWES_ACCOUNTING` lists wrappers that still owe an accounting; it
may shrink and never grow.

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

## `paper.py` — the result section

`brief()` prints what to write from: the design's questions first, then the panels, then what the
run delivered against the specification. `claim()` records a sentence with the figures it was read
off; a claim citing nothing is refused. `review()` records a verdict — standing, narrowed or
withdrawn. `render()` writes the section, the claims and every cited figure into one page.

One manuscript per plugin: `PAPER.<plugin>.md`, `PAPER_CLAIMS.<plugin>.jsonl`,
`report/<plugin>_paper.html`.

## `tests/loop_stations.py` — the test loop

Nine stations run in order against real runs: exists, landscape, licence, adopt, merge, report,
drawing, eye, paper, outputs. The loop stops at the first blocked station and names the one thing
to do next. The goal is the eye scan complete and the manuscript written; the earlier stations go
green long before the output is worth having.
