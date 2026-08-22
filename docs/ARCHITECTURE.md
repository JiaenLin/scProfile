# Four domains, and what each is allowed to know

scProfile is a plugin host. Its correctness rests on the boundaries between four things, and
every serious defect in its history has been one domain doing another's job.

```
      DECLARE  ──►  BUILD  ──►  PLAN  ──►  RUN
    the plugin     the builder   the planner   the runner
```

| domain | owns | may read | may NOT |
|---|---|---|---|
| **the plugin** | everything about itself | nothing outside its own directory | know a project, a column, an organism |
| **the builder** | making a declared plugin runnable | the plugin's declaration | infer anything the plugin did not declare |
| **the planner** | deciding what runs, how, in what order | the object, the design, the plugin declarations | write results, or refuse for a build reason |
| **the runner** | executing the plan | the plan, the built plugins | decide what should run |

---

## 1. The plugin declares everything about itself

A plugin directory is **self-describing**. The builder does not go looking; it reads.

| file | declares |
|---|---|
| `kernel.yml` | what it needs, produces, sees, cannot show; whether it runs per unit; its cost and cores; what tool it wraps |
| `recipe.py` | **the method call, and only that** |
| `lock.yml` | its environment, pinned |
| `references.yml` | reference data, with URL, organism, digest and size |
| `selftest.py` / `.R` | proof the call is well-formed against the installed versions |
| `UPSTREAM.md` | what the wrapped tool's own documentation says, and which of its defaults are wrong here |

**Nothing in a plugin may name a project's vocabulary** — not a column, a layer, an organism or a
sample. Those arrive at run time through `keys` and `organism`. The compiler refuses a recipe that
hard-codes one, because a plugin that names one project's vocabulary works on one project.

## 2. The builder makes it runnable, and does not discover

`scprofile install <name>` takes a declared plugin all the way:

1. **compiles `run.py`** from `recipe.py` — the contract half is generated identically for every
   plugin: reading `in.json`, resolving keys, subsetting to a unit, keeping annotator sentinels as
   cells, excluding cells with NaN in a computed embedding, honouring the allocated core share,
   writing declared outputs and `out.json`;
2. builds the environment from `lock.yml`;
3. proves it with the plugin's own selftest.

**The builder is mechanical and knows no plugin by name.** If a declaration is incomplete it says
which file is missing — it does not guess, and it does not hand the user a skeleton to finish.

> **This is why `scaffold` no longer writes a `TODO`.** It used to emit a `run.py` whose body was
> `raise SystemExit("this is a SCAFFOLD, implement the method call")`. That is a script handed to
> the user to complete, and a plugin host whose plugins must be hand-written is a directory of
> examples. The wrapper is now compiled; what a plugin author writes is the method call, beside
> the declaration it belongs to.

## 3. The planner decides, and repairs rather than refuses

It reads the object and the design table and gives every plugin a verdict, its settings at the
highest capacity the project supports, and a place in the run order.

**It never refuses for a build reason.** A plugin that is not built still gets its full verdict
against the project — *"on your data this would run at full, over 10 samples, testing the
age×diet interaction"* — and the build gap is listed separately and handed to the builder. A
plugin that is not built is not a limitation of the user's data.

**It skips only what the design cannot express**: a factor with one level, or no level with two
samples. An imbalance, a confound, even a complete confound, all run with a caveat. See
[`RUN_PLAN.md`](RUN_PLAN.md).

## 4. The runner executes

Waves, subprocesses, merge by barcode, one report. It decides nothing.

---

## The boundaries, stated as rules

1. **A plugin never learns about a project.** Keys arrive at run time.
2. **The builder never infers.** Everything it needs is declared; a gap is named, not filled.
3. **The planner never refuses for a build reason.** Readiness is repaired.
4. **The runner never decides.** If it is choosing, the planner did not finish.
5. **No domain writes another's files.** The builder writes into the plugin; the runner writes
   into the run directory; the planner writes nothing but its plan.

Each of these was learned by breaking it. The builder inferring produced a plugin that scored from
a layer nothing declared. The planner refusing for a build reason produced a plan telling a
healthy cohort that seven of nine analyses were impossible. And a wrapper written by hand is how a
forbidden keyword reached a live run.
