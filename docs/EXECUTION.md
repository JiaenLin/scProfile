# Execution plan

How plugins are scheduled: what runs at the same time, what must wait, and how the design is
carried into every one of them.

Two things are being optimised at once and they are not in tension. **Speed** comes from running
independent work concurrently. **Correctness** comes from running each plugin over the unit the
experiment was designed around, rather than over a pooled cohort. The second turns out to be the
larger source of parallelism.

---

## 1. Three axes of parallelism

```
    across plugins        independent nodes of the dependency graph
        x
    across design units   the same plugin over each sample, or each arm
        x
    within a plugin       n_jobs / threads
```

They multiply, and multiplying them without a budget is how a node ends up with 200 threads on 24
cores and runs slower than serial. §4 is the budget.

### The graph is wide and shallow

Derived from each plugin's `needs` and `needs_kernels`, not hand-written:

```
  wave 1   cellcycle   velocity   liana   decoupler   scenic   abundance   de   cellchat
  wave 2   pseudotime                       (needs cellcycle)
  wave 3   tensor_cell2cell                 (needs liana, per-sample)
```

Almost everything is independent. The scheduler's job is therefore not sequencing — it is deciding
what to start first and how much of the machine to give each.

---

## 2. Longest pole first

Within a wave, start by **declared cost, descending**. A `trivial` plugin that finishes in seconds
must never sit in front of a `high` one that runs for hours; the wave's wall-clock is its slowest
member, and starting that member last adds its whole duration to the total.

```yaml
executor:
  cost: high            # trivial | low | medium | high
  cores: 8              # what one instance can actually use
  memory_gb_per_100k: 12
```

`cost` orders. `cores` and `memory_gb_per_100k` are what the budget divides. A plugin that declares
nothing is assumed `medium` and one core — the pessimistic reading, so an undeclared plugin is
under-served rather than allowed to swamp the node.

---

## 3. The design is not an afterthought

**Every plugin receives the design table**, whether or not it tests across it. A plugin that
ignores the design produces a cohort-level number that hides the thing the experiment is about.

Three distinct relationships, and each is declared:

| declaration | means | example |
|---|---|---|
| `needs_design: true` | it **tests** across the design; without one it refuses | `abundance`, `de` |
| `design_aware: true` | it does not test, but **reports per arm** | `velocity` confidence per arm; `cellcycle` phase per arm |
| `per_unit: sample` | it is **run once per unit**, and the results compared | `liana`, `scenic` |

`per_unit` is the important one and it is where most of the speed is.

### Why `per_unit` is a correctness requirement before it is a speed one

Running a communication inference over a pooled cohort produces one contact map. That answers *what
talks to what in this tissue* — which is rarely the question a designed experiment was built to
ask. The question is *how communication differs between conditions*, and that needs one result per
sample, compared afterwards.

The same argument applies to regulon inference. Pooling arms and inferring one network gives a
network for the average of two conditions, which may describe neither.

So `per_unit: sample` plugins fan out over samples — embarrassingly parallel, N× the throughput,
and the only form of the result a downstream comparison can consume. A cohort-level run remains
available as `--pooled` and says in its caveats that it cannot answer a between-condition question.

### The design table

Keyed on `{sample}`, exactly as the integration step consumes it. A sample present in the object
with no row is refused **by name**. Nothing is derived by pattern-matching a sample name — that
bakes one project's naming into a tool every other project has to work around.

---

## 4. The core budget: parallelism without oversubscription

The scheduler holds a **budget** — the cores it was given, from `NCPUS`, `PBS_NCPUS`,
`SLURM_CPUS_PER_TASK` or the machine — and divides it among concurrently running instances. Each
instance is told its share in `in.json`:

```json
{"resources": {"cores": 6, "memory_gb": 32}}
```

**A plugin MUST use that number and not the machine's.** `os.cpu_count()` inside a plugin is a bug:
it reports the node, not the share, and four plugins each reading it will each start 24 threads.

Concurrency is then `min(budget / smallest_declared_cores, ready_plugins)`, floored at 1. A plugin
declaring more cores than the whole budget runs alone, at the budget, rather than being refused.

---

## 5. Executors

The same graph, three backends. Where compute happens is not part of what the analysis is.

| executor | wave 1 becomes | dependencies |
|---|---|---|
| `local` | a process pool sized by the budget | in-process barrier between waves |
| `pbs` | **one job per plugin instance**, submitted at once | `-W depend=afterok:<jobid>` |
| `slurm` | same shape | `--dependency=afterok` |

On a scheduler this is the real win: wave 1 of eight plugins over ten samples is up to eighty
independent jobs, limited by the queue rather than by one node. The harness's dependency edges
become the scheduler's, and nothing waits on a barrier that the graph does not require.

**A wave is not a barrier unless the graph says so.** `pseudotime` waits on `cellcycle` and on
nothing else — it must not wait on `scenic`. The implementation walks the DAG, not the wave index.

---

## 6. Failure isolation

One plugin failing must not take the wave with it.

- a failed instance is recorded, its dependents are marked unrunnable **by name**, and everything
  else continues;
- a **per-unit** plugin that fails on one unit reports that unit as absent and keeps the rest —
  three of ten samples failing is a result about those three, not a dead run;
- the report names every plugin that did not run and why, because a plugin missing from a report
  looks identical to one that found nothing.

---

## 7. Consuming the upstream properly

Each of the three upstream tools leaves something specific behind, and reading it wrong is silent.

### From the QC step

`uns['scqc']` declares **what the flag means**, with a digest of the exact set. A plugin reads the
declaration — it never infers meaning from a column name, which would be the plugin deciding what
is technical on the QC step's behalf. If the digest does not check out, refuse.

### From the annotation step

Several **label columns**, not one: a fine level, a coarse one, and forced variants in which
uncertain calls were pushed to a leaf. They disagree exactly where the annotation was least
certain.

- `{label}` is what a plugin tests on by default;
- a plugin producing a ranking or a comparison should offer the others, because a result that
  moves between label columns was partly about the labels;
- **sentinels are not cell types.** Never a population, a denominator or a legend entry — and never
  dropped, because they are cells.

### From the integration step

Two things, and both are load-bearing.

**`uns['scintegrate']['constraint_on_use']`** states what the chosen embedding may and may not
carry. A plugin whose output would breach it must refuse and name the embedding to use instead.
This is not advisory: where a biological factor is confounded with a batch factor, a correction on
batch removes the contrast, and a test run afterwards returns clean p-values for something the
embedding no longer contains.

**Withheld cells carry `NaN` in every computed embedding.** A plugin using an embedding MUST handle
them explicitly — exclude them and say how many, or refuse. Passing NaN into a neighbour graph
either raises or, worse, silently yields a graph those cells are absent from without anything
recording it.

The **uncorrected** embedding is always present and is what a compositional or abundance claim
across the design must use.

---

## 8. What this plan is judged on

| | |
|---|---|
| speed | wall-clock of a full profile against the sum of its parts run serially |
| no oversubscription | threads started never exceed the budget, measured, not assumed |
| correctness | a `per_unit` plugin produces one result per unit, comparable across arms |
| isolation | a deliberately failed plugin leaves every independent one intact |
| upstream | a constrained embedding is refused; a bad flag digest is refused; NaN rows are handled |

The last row is the one worth failing on. A schedule that is fast and reads its inputs wrongly is
worse than a slow one, because the speed is visible and the wrongness is not.
