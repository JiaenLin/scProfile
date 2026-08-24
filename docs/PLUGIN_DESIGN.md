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
