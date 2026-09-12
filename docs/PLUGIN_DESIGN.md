# The plugin design, and what it borrows

A plugin is written once and lives against a moving world. Two very different people have to be
able to trust it: the **builder**, which must make it runnable on a machine nobody has seen, and
the **maintainer**, who must change it years later without knowing what else depends on it.

This is what the shape has to earn.

---

## Borrowed from Cordis, and what was left behind

scProfile's host is inspired by [Cordis](https://github.com/cordiverse/cordis), the framework
behind DeepSeek Harness, whose organising claim is *everything is a plugin*. Four of its ideas
carry over almost unchanged, and the rest deliberately do not.

> The primary Cordis documentation was not reachable when this was written, so what follows is
> the model as understood from its published API surface, not a quotation of its docs. Where this
> design departs, it says so.

**Taken: injection.** A Cordis plugin declares `inject: ['database']` and the framework only
activates it when that service exists — the plugin never checks. scProfile does the same with
**capabilities**: a plugin declares what it must be given, and the host does not call it
otherwise. A plugin that begins `if not ctx.organism: refuse(...)` is doing the host's job, and
doing it once per plugin means doing it differently once per plugin.

**Taken: required versus optional.** Cordis separates injections that gate activation from ones
that are merely used if present. That distinction is the difference between *this plugin cannot
run* and *this plugin will do less*, and both belong in the declaration rather than in an `if`.

**Taken: capabilities, not names.** A Cordis plugin injects `database`, not `sqlite-plugin`.
scProfile plugins `provide` and `inject` **capabilities** — `ordering`, `communication`,
`activity` — so a plugin that needs an ordering does not care which plugin produced it, and a
better one can replace it without every consumer being edited.

**Taken: effects and disposal.** In Cordis everything a plugin registers is tied to its scope and
is undone when the scope closes. Here that is `ctx.effect()`: a dask client, a temp directory, an
R session, released whether the plugin returns, refuses or raises.

**Left behind: the event bus, reactive config, nested loading.** Those serve a long-lived
service host. This host runs batch analyses in subprocesses that exit. Importing that machinery
would be borrowing the shape of a solution to a problem this tool does not have.

---

## The declaration

```python
PLUGIN = {
    "api": 1,                      # the contract this plugin was written against
    "summary": "...",
    "inject": {
        "required": ["counts", "label"],     # the host will not call run() without these
        "optional": ["design", "embedding"], # used if present; the plugin does less without
    },
    "provides": ["activity"],                # capabilities, so consumers need not name plugins
    "config": {                              # typed, defaulted, validated BEFORE run()
        "min_cells": {"type": "int", "default": 10, "min": 1,
                      "help": "populations smaller than this are not scored"},
    },
    "requires": {...},                       # what the BUILDER resolves into environments

    # what the ALLOCATOR schedules on
    "cost": "high", "cores": 8,
    "memory_gb_base": 11.4,                  # paid once, whatever the cell count
    "memory_gb_per_100k": 19.8,              # and this much again per 100k cells
    "gpus": 0,

    # SCOPE: is this meaningful per unit, over the cohort, or both?
    "per_unit": "sample",
    "also_cohort": {"why": "..."},           # only when the output vocabulary is INFERRED

    "references": {...}, "upstream": {...}, "cannot_show": [...],
}
```

**`api` is the compatibility mechanism.** A host that understands api 1 and meets a plugin
declaring api 2 refuses it by name rather than calling it and failing somewhere inside. Without
it, the only way to discover a contract change is a crash in a stranger's run.

**`inject` replaces prerequisite checking inside plugins.** The host resolves each capability
against the object and the design, and either calls `run()` with everything present or reports
precisely which capability was missing — to the *planner*, which turns it into a verdict a user
can act on.

> **One function answers that question, for both.** `declare.available()` is asked by the
> entrypoint before `run()` and by the planner before a queue slot is spent, so the plan and the
> run cannot disagree about what a plugin will be given. It was implemented at run time only:
> the entrypoint refused correctly, the planner did not know `inject` existed, and a plugin
> requiring an organism was planned `RUN` against an object that had none — discovered an hour
> later, in a queue.

**`config` is validated before anything runs.** A bad `--params` should fail in the second the
plan is drawn, not an hour into a queue.

### What the builder and planner may not work out for themselves

A plugin is written **once** and ships prebuilt. The builder and the planner run again on every
new machine and every new project — so anything they have to discover is a guess made later, on
somebody else's machine, about a method they did not write. Four fields exist for that reason,
and each was added after the host had been caught guessing.

**`memory_gb_base` + `memory_gb_per_100k`.** Memory is a fixed cost plus a per-cell one:

```
peak_gb  ≈  memory_gb_base  +  memory_gb_per_100k × n_cells / 100_000
```

The interpreter, the imports and the object are paid once whatever `n` is. Declaring a pure rate
makes a 15 GB measurement on a 10,000-cell instance read as 150 GB per 100k. **Measure both, do
not estimate them:** every run fits them from its own instances and prints them ready to paste,
and a per-unit plugin produces one point per unit for nothing. A plugin declaring neither is
scheduled on a conservative assumption *and the run says it is guessing*, every time.

**`gpus`.** Nothing ships declaring one; the point is that the next method needing a GPU does not
require a scheduler change.

**`references` carry a `tier`.** The declaration used to assume a downloadable file — `url`,
`sha256`, `size` — so a database shipped inside a package or fetched at run time could not be
declared at all. One plugin of nine declared references while four consulted them.

| tier | meaning | what the host can do |
|---|---|---|
| `fetch` | downloadable, checksummed | get it, verify it, refuse without it |
| `bundled` | ships in a package, pinned by that version | name it in the report; nothing else |
| `runtime` | fetched by the tool **while it runs** | warn that the compute node needs network |

The last one is why this matters on a cluster: a batch node with no outbound route fails *inside*
the run, after the queue slot is spent, and the plugin is the only party that knew it would reach
the network. **A reference you do not declare is one the plan cannot warn about and the report
cannot name.**

**`per_unit` and `also_cohort`.** `per_unit` says a pooled answer would describe the average of
the conditions and may describe none of them. `also_cohort` says something narrower and rarer:
this method **infers its own output vocabulary**, so two per-unit results are not comparable with
*each other* and one shared fit is needed to compare them.

A method drawing from a fixed reference resource does not need it — every unit's table is indexed
by the same entries. A method that discovers its vocabulary from the data does: measured across
ten samples, two of them shared 17% of their inferred features, and stacking those columns into
one array would place values that are not the same quantity in the same column.

---

### `report` — what the page should contain

The reporter is the third consumer of a plugin's own words, after the builder and the planner, and
it reads them the same way. Without this block a page is the outputs the plugin declared plus
whatever figures it happened to emit, in emission order, with nothing on it saying what a panel is
for or that one is missing.

```python
"report": {
    "figures": [
        {"id": "confidence",
         "shows": "diagnostic",
         "question": "do neighbouring cells agree on the direction?",
         "source": "figures/confidence.csv",
         "required": True},
        {"id": "phase_portraits",
         "shows": "diagnostic",
         "question": "do the driver genes obey the kinetics the model assumes?",
         "source": "figures/phase_portraits.csv",
         "required": False,
         "when_absent": "no gene passed the dynamical fit, so the field below rests on the "
                        "steady-state approximation alone"},
    ],
    "reads_with": ["pseudotime"],
}
```

| field | is |
|---|---|
| `id` | the name `emit_figure` is called with. The join between the declaration and the panel |
| `shows` | `diagnostic`, `result` or `comparison`. The only vocabulary the reporter understands |
| `question` | printed above the panel, so a reader knows what it is for before deciding whether it answers them |
| `source` | the table the panel must be drawable from |
| `required` | default `True`. A required panel that is absent is a defect; an optional one is a property of the data |
| `when_absent` | the sentence printed in an optional panel's place |
| `reads_with` | plugins that answer the same question from different evidence |

**Diagnostics come first, and that is the point rather than a style.** A result under a failed
check is a number, not an answer, so the reporter orders every page `diagnostic` → `result` →
`comparison` and a reader meets the checks before the headline.

**The reporter knows this vocabulary and no figure.** It positions a panel by `shows`, captions it
by `question` and links it by `source`. It holds no list of ids, no idea what any panel draws, and
gains nothing when a plugin arrives with panels nobody has seen — a reporter that knew the ids
would be wrong about every plugin it had not been told about.

**A declared panel that was not drawn is stated, never left as a gap.** A gap on a page reads as a
figure nobody thought was needed, which is the one reading that is never true: the plugin declared
it. `figure_drift` reports the same mismatch to the maintainer, in both directions — declared and
not drawn, drawn and not declared — the way `produces` already is.

**The block is optional.** A plugin without one still runs and still reports; `declare.check`
returns a WARN, not an ERROR. A format that refuses a plugin for not having it yet is a format
nobody adopts.

## What the host guarantees

Everything below happens for every plugin, in `_entry.py`, and none of it is a plugin's business:

- keys resolved, so **no plugin ever writes a column name**;
- `ctx.populations()`: the grouping a per-population result must use, sentinels already out of it
  and the caveat attached — because two of the first two plugins that grouped by the raw label
  column reported an annotator's refusal as a cell type;
- the object subset to this plugin's unit;
- annotator sentinels kept as cells and counted;
- cells with NaN in a computed embedding excluded and reported;
- the **allocated** core share, never the machine's;
- required capabilities present, or `run()` is not called;
- config defaulted and type-checked;
- effects disposed, on every exit path;
- outputs written and `out.json` sealed.

Every wrapper bug in this project's history lived somewhere in that list.

And a few things the host will *do for* a plugin that asks, so that no plugin writes them twice:

| `ctx.populations()` | the grouping, the mask, `.names` and `.dropped` — five plugins destructured the old two-tuple wrongly |
| `ctx.layers()` | the layer names the object actually has; `list(adata.layers)` yields anndata's `None` alias for X |
| `ctx.source_layers()` | fetch a layer the object does not carry from the ALIGNER OUTPUT beside it, following the upstream chain the host harvested |
| `ctx.plot()`, `ctx.figure` | matplotlib with the journal conventions applied, so a plugin never imports a host module to draw |
| `ctx.fixture()` | the synthetic object a selftest needs, built once rather than hand-rolled per plugin |
| `ctx.effect()` | acquire and release, on every exit path including a raise |

**The environment's own `bin` is on `PATH`**, so a plugin whose method is in another language
reaches its interpreter by name. And **the core share is set as `OMP_NUM_THREADS` and its five
siblings**, because numpy's BLAS sizes its pool at import, before any plugin code runs — that is
the one thread pool a plugin cannot honour for itself.

---

## Why this is robust for the builder

The builder needs to answer *can this run here* without executing analysis. It reads the
declaration — never imports the plugin — so a plugin pinned to numpy 1.23 is still listable by a
host on numpy 2. `env` says what to build, `references` what to fetch, `selftest` how to prove it,
`api` whether to attempt any of it at all.

## Why this is robust for the maintainer

Everything about one plugin is in one file, so there is no second file to keep in step. The
declaration is *checked* rather than trusted: `validate` reports a drift between what the plugin
says and what it does. And the contract is not copied into the plugin, so a fix to the host's
handling of sentinels or NaN rows reaches every plugin — including ones the maintainer never
looked at.

## `report.unit_network` — the one declaration that buys figures

A plugin that writes a per-unit table of relationships between populations declares where it is
and what its columns mean, and the HOST then draws the panels. **No host code names a method**;
what a plugin declares is exactly what it gets.

```python
"unit_network": {"table": "tables/edges.csv", "source": "source", "target": "target",
                 "weight": "score", "weight_scale": "per_object",
                 "group": "pathway", "member": "interaction"}
```

| declared | what it earns |
|---|---|
| `table`, `source`, `target`, `weight` (required) | the sender-by-receiver matrix, the ring, the chord and the role scatter per arm; the difference matrix and the role shift per contrast; the interaction where the design supports one |
| `+ group` | the flow ranking and the group-by-population role heatmap per arm; the paired flow comparison per contrast |
| `+ group` and `member` | the decomposition of one group into its members |

`weight_scale` is `per_object` (the default) or `absolute`, and it decides what a comparison
between two units is allowed to claim. Where a method computes its weight over the elements
present — the usual case — two units' values are on two scales, and every between-arm panel is
drawn on each arm's own SHARE with both totals printed. **The host cannot tell which it is from
the numbers.** Declaring it wrongly does not fail; it produces a comparison that looks right.

An unrecognised key here is an **ERROR**, not a warning: a misspelt column name removes panels
in silence, and a plugin that has lost three looks exactly like one that declared less.

## `report.figures` — the figure plan

Every figure a plugin draws in R is an entry of `report.figures`, and the entry carries the call
(harness ADR-0016): the generated companion `kernels/<plugin>.draw.R` draws from it, and the
plugin's embedded R calls `.draw("<id>")` where a hand-written site used to stand. Adjusting a
figure is editing its entry; `scprofile scaffold <plugin> --force` regenerates the companion, and
a companion edited by hand reads as drifted. Together with the design table the plan determines
the figure count before any compute is scheduled: `scprofile plan` prints it, `capacity
--promised` holds the finished run against it, and the maker's `sch dev convert plan` prints the
plan as a table with what each entry lacks and which need reaches it.

```python
"report": {
    "figures": [
        {"id": "native_heatmap_count", "kind": "matrix", "drawn_by": "tool",
         "fn": "netVisual_heatmap", "axis": "unit", "position": "contrast", "at_most": 1,
         "args": 'cc, measure = "count", color.use = .gcol',
         "legend": "Interactions counted between every ordered pair of {ngrp} populations."},
        {"id": "nativecmp_chord_cell", "kind": "chord", "drawn_by": "tool",
         "fn": "netVisual_chord_cell", "axis": "contrast", "position": "contrast",
         "items": "shared", "at_most": 8, "file": 'paste0("chord_cell__", p)',
         "args": "merged, signaling = p", "legend": "The {p} pathway, both arms."},
        {"id": "nativecmp_interaction", "kind": "interaction", "drawn_by": "plugin",
         "axis": "cohort", "position": "conclusion", "at_most": 3,
         "file": 'paste0("interaction_", ms, "__", safe)',
         "expr": "{ ComplexHeatmap::draw(...) }",
         "legend": "Does the {fac} response depend on {stratum}? ..."},
    ],
    "skips": {"netVisual_embedding": {"skip": "not_applicable", "evidence": "..."}},
    "provides_evidence": {"who_changed": ["native:netVisual_heatmap",
                                          "plan:nativecmp_interaction", "host:diff_matrix"]},
},
```

- **`drawn_by`** is `tool` — the wrapped tool's own function `fn`, called with `args` — or
  `plugin` — this plugin's own R over the tool's numbers, in `expr`. The two are different claims
  about provenance, and the accounting of the tool's exports is built on the distinction.
- **`axis`** (`unit`, `contrast`, `cohort`) is what the family multiplies over; **`position`**
  (`overview`, `contrast`, `conclusion`, `appendix`) is where a result places it, and `appendix`
  means drawn and cited by no sentence.
- **`at_most`** is the ceiling **in files, per occurrence of the axis**. A per-item family names
  the R vector it iterates in `items` and the expression naming each file in `file`; `when`
  guards the draw; `device`, `w`, `h` and `res` are the device's.
- **`legend`** is a template whose `{...}` placeholders are R expressions evaluated where the
  draw is called — the numbers exist there and nowhere else. **`kind`** names a registered panel
  kind and binds the exit standard's rules to the caption.
- **`profile: True`** on a unit-axis entry puts it on the profile page; **`generated: False`**
  marks a file the tool writes as a side effect of a call, a promise kept by any figure format.
- **`report.skips`** is every export of the tool the plan does not call, with a reason from the
  closed vocabulary and its evidence. **`provides_evidence`** routes each need a comparison has to
  the panels that answer it: `native:<fn>`, `plan:<id>` for the plugin's own panel, or
  `host:<kind>`; a panel the plugin draws itself that no route reaches is drawn on every run and
  placed in no document, and the maker's plan table names it.

### The older form, which the eight held-out plugins still carry

Three declarations decide **which** figures a run draws, **how many** of each, and which of them
a result is written from; the same readers apply them until the last such plugin is on the plan,
and `sch dev convert plan --migrate` prints the paste-ready entries built from them.

```python
"report": {
    "figure_position": {"native_": "appendix", "nativecmp_diffInteraction": "contrast"},
    "figure_axis":     {"native_": "unit", "nativecmp_": "contrast"},
},
"native_plots": {
    "netVisual_chord_cell": {"at_most": 8,
                             "use": "figures/nativecmp_chord_cell__<pathway>.png"},
    "netVisual_aggregate":  {"at_most": {"native_aggregate_circle": 1,
                                         "nativecmp_aggregate_circle": 6},
                             "use": "figures/native_aggregate_circle__<pathway>.png per unit, "
                                    "and figures/nativecmp_aggregate_circle__<pathway>.png"},
}
```

**`figure_position`** maps a figure-id prefix to where a result places the family: `overview`,
`contrast`, `conclusion`, or `appendix`. Longest prefix wins, so a broad rule and its exception
sit beside each other. `appendix` means the family is drawn and no result is written from it: the
panels are produced, placed on the pages and reviewable, but they are not numbered, no sentence
can cite them, the writing step does not wait on them, and no vector copy is written for them.

**`figure_axis`** maps a prefix to what the family multiplies over: `unit`, `contrast` or
`cohort`. Without it a ceiling is a number with no units and no count can be computed.

**`at_most`** is the ceiling **in files, per occurrence of the axis** — not the number of items a
loop iterates. A family drawing six pathways once per arm writes twelve files per contrast. It may
be a single number, or a mapping from family to number when one entry names several: an upstream
function that draws one panel per unit and six per contrast needs two.

### The ceiling governs, it does not describe

The host resolves these declarations and hands them to the drawing side, which refuses past the
ceiling before computing the panel. Where the wrapped tool draws into its own graphics device the
host cannot intervene, and `capacity --promised` reports a family that exceeded its ceiling as a
failure of the run.

A ceiling written twice — once in the declaration and once as a literal in the drawing code — is
two numbers kept in step by hand. The declaration is the only place the number belongs.

### Accounting runs in both directions

`capacity --promised` asks two questions of every run and refuses on either:

- **declared and never drawn** — an entry of the plan (on the older form, a plot named in
  `native_plots`) that produced no file anywhere in the run. The reader was promised a panel and
  did not get one.
- **drawn and declared by nothing** — output the run produced that no declaration accounts for.
  A wrapped tool that writes a diagnostic into the working directory is doing something ordinary;
  the point is that nothing else in the run can tell it from output someone asked for. Declare it,
  with `at_most` and a position, and the accounting is complete.

Host-drawn panels are not a plugin's output and are recognised from `panels.IMPLEMENTED`. A host
panel missing from that registry is charged to the plugin.

