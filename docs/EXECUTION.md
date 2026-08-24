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

```python
"cost": "high",              # trivial | low | medium | high — orders the wave
"cores": 8,                  # what one instance can actually use
"memory_gb_base": 11.4,      # paid once, whatever the cell count
"memory_gb_per_100k": 19.8,  # and this much again per 100k cells
"gpus": 0,
```

`cost` orders. The rest are what the allocator divides, on **every** dimension — not cores alone.

### Memory is two terms

```
peak_gb  ≈  memory_gb_base  +  memory_gb_per_100k × n_cells / 100_000
```

The interpreter, the imports and the object are paid **once**, whatever `n` is; only the working
matrices scale. Modelling memory as a pure rate makes a 15 GB measurement on a 10,000-cell
instance read as 150 GB per 100k, which over-predicts small instances by an order of magnitude and
can under-predict large ones — and under-predicting is the one that kills a job.

**Measure both terms; do not estimate them.** Every run reports each instance's peak RSS and cell
count, fits the two terms per plugin, and prints them ready to paste into a declaration. A
per-unit plugin gives one point per unit for nothing, which is exactly what separates a baseline
from a slope.

**One point cannot separate them**, and the fit says so: it attributes the whole peak to the
**rate** and reports no baseline. That is the direction that fails safe. Attributing it to the
baseline is exact at the size measured and under-predicts every larger one — 7.2 GB seen at 98,627
cells would charge 7.2 GB for 500,000, where the truth is nearer 36. Attributing it to the rate
over-charges the smaller instances instead, where the error is bounded by the baseline and nothing
dies.

A plugin that declares no memory is scheduled on a conservative assumption **and the run says it
is guessing**, every time. `declare` warns, so the gap is visible where it can be fixed.

### Admission is by resources, not by count

`ResourcePool` admits an instance when **every** dimension it needs is free. A cores-only pool is
blind in the dimension that actually ends runs: a job died at 260 GB against a 200 GB request
while each of its ten instances was correctly holding one core. The core budget was satisfied
throughout and could not have prevented it.

Every request is capped at the pool's own totals before it is waited on, so an instance wanting
more than the whole allocation runs alone rather than waiting for permits that can never exist.

### Estimate high

The two failure directions are not symmetric. Over-requesting costs queue time and some idle
capacity — visible, recoverable, measurable afterwards. Under-requesting gets the job **killed**,
usually at the end of its longest step, with no partial result and an error naming the plugin
rather than the request. Memory and walltime take the ceiling; cores take what schedules promptly,
because an over-large core request delays scheduling and cores do not kill a job.

---

## 2a. The tool cannot change under a running run

A run reads its code at **every subprocess launch**, not once at the start. A three-hour run spawns
instances across three hours, so a `git pull` into the tool directory at hour one is picked up by
everything launched after it. The run then uses two versions and reports one, because the banner
records the commit at the beginning and nothing re-checks.

That failure is silent and unattributable: both versions are correct on their own — the *mixture*
is what is wrong — so no test catches it, and the report names a commit that never produced those
results in full.

Two mechanisms, because one of them is a job script somebody else may not use:

| | where | what it does |
|---|---|---|
| **detect** | the host | fingerprints the tool tree at run start and **re-checks before every instance**. A launch whose tool has moved refuses and names the files. |
| **prevent** | the job template | copies the tool into the run directory and runs from there, so a pull cannot reach a live job at all. `SNAPSHOT=0` opts out. |

The snapshot also means the run directory holds exactly the code that produced it. `__pycache__`
is excluded from the fingerprint: a `.pyc` is written by *running* the code, not by changing it,
and counting it would make every run report drift against itself.

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
and the only form of the result a downstream comparison can consume.

### `also_cohort` — when per-unit results are not comparable to each other

**The paragraph above is true of a method with a FIXED output vocabulary and false of one that
INFERS it.** `liana` and `cellchat` score ligand–receptor pairs drawn from a reference resource, so
every unit's table is indexed by the same pairs and the units really can be compared. SCENIC is not
like that: each fit discovers its own regulon set, so two units' AUC columns are **not the same
quantity** and a between-condition comparison built from them compares different things.

Measured on a ten-sample cohort: **37 to 111 regulons per sample, and two samples shared
17% of their transcription factors (Jaccard 0.17)** — with the counts separating almost perfectly by
a design factor that is itself confounded with batch, which is what makes the naive reading
dangerous rather than merely noisy.

A plugin in that position declares `also_cohort` with its reason, and the scheduler emits **one
extra instance with `unit: None` alongside the per-unit ones**. Both are kept because they answer
different questions and check each other:

| scope | question it answers | comparable? |
|---|---|---|
| per unit | what programme operates in *this* sample | within that sample only |
| cohort | one vocabulary over every cell | across cells and conditions |

The per-unit fits are the only **independent** check on the pooled one — a regulon recovered
separately in most samples is far stronger evidence than one appearing in a single pooled fit that
nothing corroborates. And the cohort fit carries the risk the per-unit fits do not: a pooled GRN has
no notion of design and will encode batch-driven co-expression as regulation, so where the object
records a constraint on use, the cohort fit reproduces it verbatim.

There is no upstream guidance to defer to here. The SCENIC maintainers' thread on comparing AUC
across runs is unanswered ([aertslab/SCENIC #317](https://github.com/aertslab/SCENIC/discussions/317)),
and the single-cell best-practices GRN chapter demonstrates on one donor, explicitly *"due to batch
integration considerations"*. The declaration exists because the guidance does not.

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

**And the host sets the thread-pool variables to the same number**, because there is one thread
pool a plugin cannot control: the BLAS behind numpy sizes itself from `OMP_NUM_THREADS` when numpy
is imported, before any plugin code runs, and inherits whatever the job script exported for its own
sake. `manifest.env_for_kernel` therefore sets `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
`MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS` and `BLIS_NUM_THREADS` from the
share in the manifest it was just handed — one statement of the number, so the two cannot disagree.
*Without it an eight-instance wave on a sixteen-core allocation ran 128 BLAS threads on 16 cores,
with every instance correctly told `cores: 1`.*

**Admission is by CORES, not by count.** Every instance is given the cores it DECLARED, capped at
the budget, and `kernels.CorePool` admits it when that many are free. A plugin declaring more cores
than the whole budget runs alone, at the budget, rather than being refused.
`kernels.concurrency()` reports how many that leaves resident — a headline for the plan, computed
the way the pool behaves.

*Until 2026-08-22 the budget was divided PROPORTIONALLY across the whole wave —
`declared x budget / sum(declared)` — and that is a different rule wearing the same word. It
assumed a wave runs all at once, when only the resident subset does, so it charged every instance
for the presence of instances that had not started. On any wave larger than the budget the
arithmetic collapsed to one core each: 37 instances declaring 313 cores against a budget of 12 gave
`scenic` `int(16 x 12 / 313)` = 0, floored to 1. Measured on PBS 677891 — ten GRNBoost2 fits, each
declaring 16 cores, each running on one, still unfinished after 4h23m of a 12h timeout while the
plan printed `scenic[S1](1c)` and nothing printed the 16. **A declaration read and then
discarded is worse than one never read**, because the plan prints its consequence and never prints
the declaration.*

*That sentence was here from the beginning and nothing implemented it until 2026-08-22: the runner
started **every** instance of a wave at once, however many there were. The two are not the same
thing — the budget divides the share each instance is **told** it has, and thirty-five instances
each correctly told `cores: 1` still run thirty-five processes on a node asked for eight. On the
shipped set, ten samples and three `per_unit` plugins, that is 35 subprocesses each opening a 3 GB
object, and the memory failure it causes reads as the plugin's fault. `kernels.concurrency()` is
the rule; the wave is now started through it.*

**The budget is divided over the instances that actually launch, at the start of each wave — not
over the ones that were requested.** A wave is filtered by five things first, in order: the plugin
is declared but not built; its prerequisites are unmet; a guard refuses it; a declared reference is
missing; its interpreter cannot read the object even re-encoded. All five run before the division,
which is why `in.json` — the file carrying the core share — is written after it and not with the
rest of the preparation. *An earlier version of this paragraph claimed all five and the code did
two; a review found the gap. The share is what a plugin is contractually required to use instead
of `os.cpu_count()`, so a wrong one is a real misallocation, not a reporting detail.* Measured:
`run --all --cores 8` on a ten-sample object built a wave of 35 instances declaring 301 cores,
scaled every one of them to 1, and ran the single built plugin single-threaded on an eight-core
allocation — while `plan --cores 8`, which filters first, printed `velocity(7c)` for the same
command. Two documents describing the same run disagreeing is how it was found, and it scales with
how many declared-but-unbuilt plugins the roadmap holds.

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
  looks identical to one that found nothing;
- **a plugin that ran on some units and failed on others is neither "ran" nor "not run", and gets
  its own state.** It appears in both lists, and testing `ran` first rendered seven-of-ten samples
  as a plain success carrying one sample's headline — while the merged column held NaN for the
  other three, which is invisible in an object and in a headline alike. The index says `ran, N
  unit(s) failed` and names the units; the README lists it under *Ran, but not on every unit*.

**A per-unit plugin's ARRAYS cross units too, now that they carry their barcodes.** They used to
be dropped with the sentence "an array carries no barcodes, so it cannot be concatenated across
units" — which was never a property of arrays. `ctx.emit_obsm` writes the barcodes beside the
`.npy`, so the pieces concatenate under the same disjointness check the obs columns already had:
two units claiming one cell is refused, differing widths are refused, and a cell no unit covered
is NaN. A **layer** still does not cross units, and the reason is memory rather than alignment: the
barcodes would align it, but the result would be a dense cells-by-genes matrix for the whole
cohort that no one unit's result implies. Emit a table or a side-car object instead.

Per-unit results are folded for reporting, never collapsed. One plugin gets one page and one
`report.json` entry, and that entry carries **every** unit — status, headline, caveats, figures and
the unit-suffixed table names actually on disk. Keying a per-instance list on the plugin's name
discarded nine of ten units in a dict comprehension and presented the survivor under the cohort's
name; nothing counted the loss and nothing could recover it afterwards.

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
| correctness | a `per_unit` plugin produces one result per unit — comparable across arms when its output vocabulary is fixed, and via its `also_cohort` fit when the vocabulary is inferred |
| isolation | a deliberately failed plugin leaves every independent one intact |
| upstream | a constrained embedding is refused; a bad flag digest is refused; NaN rows are handled |

The last row is the one worth failing on. A schedule that is fast and reads its inputs wrongly is
worse than a slow one, because the speed is visible and the wrongness is not.

---

## 9. Locking a plugin whose method is not packaged

A lock exists so that the same specification builds the same environment on a machine nobody has
seen. `lock.yml` is a conda environment YAML, which expresses conda packages and pip packages —
and, until 2026-08-21, nothing else. That is enough for every python plugin here and it was not
enough for one plugin, which is worth writing down because the gap is not obvious until a method
falls into it.

**CellChat is distributed only from GitHub.** Measured rather than assumed — on PBS 676350
`conda search` over conda-forge and bioconda returned "No match found" for both `r-cellchat` and
`bioconductor-cellchat`. The two personal channels that carry it are
a two-year-old linux-64 build and a macOS-arm64 one; pinning a tool to a personal channel with one
platform and no maintenance is not something another site can reproduce, so neither is a lock.

That left three options and only one of them is honest.

| | |
|---|---|
| pin a personal channel | reproducible on one platform, until the channel is deleted |
| a shell step in the installer | the lock stops being the specification, and nothing validates a shell script |
| **express it in the format** | what was done |

`lock.yml` now takes an `r:` section, whose entries are exact in one of two ways:

```yaml
r:
  - NMF==0.28                                              # a CRAN release, current or archived
  - owner/repo@0123456789abcdef0123456789abcdef01234567    # a git commit
```

applied by `remotes::install_version` and `remotes::install_github`, both with `upgrade = "never"`
and `dependencies = FALSE`. Five rules, and each is the R spelling of something the pip path
already does for the same measured reason:

- **A commit, never a tag or a branch.** A branch moves and a tag can be re-pointed at a different
  commit with no version changing anywhere, so both read as pinned while neither is. The parser
  refuses anything that is not 40 hex characters or an exact version, and so does `validate`.
- **One process, all pins together.** Applied one at a time in separate runs, a later entry can
  re-resolve an earlier one and the environment stops matching the lock its fingerprint claims.
- **`dependencies = FALSE`, and this is the load-bearing one.** Every dependency comes from the
  pinned conda section, so nothing in the environment is chosen at install time. Letting `remotes`
  fetch a missing dependency installs an unpinned package that nothing recorded — and it *works*,
  which is what makes it dangerous. A dependency that was forgotten instead fails to load in the
  selftest, by name, which is a line to add to the lock.
- **CRAN entries before git ones.** The CRAN form exists because a conda channel's ceiling is not
  the package's: conda-forge's `r-nmf` stops at 0.21.0 and CellChat requires `NMF (>= 0.23.0)`, so
  an environment built from conda alone cannot install CellChat at all — `R CMD INSTALL` refuses on
  the version requirement. An entry applied after the git package would be applied after the thing
  it exists to satisfy had already refused.
- **The install is verified by reading the version and `RemoteSha` back out.** Both installers
  report success for a build that produced no loadable package often enough to be worth checking.

An `r:` lock pins `r-base=`, not `python=`. Demanding a python pin from an R lock was the format
asserting an assumption; `r-base` is the line that decides which binaries every `r-*` package
resolves against, exactly as the python minor version decides which wheels are built.

**What the format still cannot express**, so that the next person meets it as a known limit rather
than as a surprise: a package from a non-git source that is not on any channel (a tarball behind a
registration form, a Bioconductor version older than the one the channel carries); a build flag
that has to be set at compile time; and a system library that is not a conda package. All three
would be the same kind of extension, and none of them has come up yet — the point of writing this
down is that the next one should extend the format too, rather than reach for a shell step.
