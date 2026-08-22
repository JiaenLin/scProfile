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

**And the host sets the thread-pool variables to the same number**, because there is one thread
pool a plugin cannot control: the BLAS behind numpy sizes itself from `OMP_NUM_THREADS` when numpy
is imported, before any plugin code runs, and inherits whatever the job script exported for its own
sake. `manifest.env_for_kernel` therefore sets `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
`MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS` and `BLIS_NUM_THREADS` from the
share in the manifest it was just handed — one statement of the number, so the two cannot disagree.
*Without it an eight-instance wave on a sixteen-core allocation ran 128 BLAS threads on 16 cores,
with every instance correctly told `cores: 1`.*

Concurrency is then `min(budget / smallest_declared_cores, ready_plugins)`, floored at 1. A plugin
declaring more cores than the whole budget runs alone, at the budget, rather than being refused.

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
| correctness | a `per_unit` plugin produces one result per unit, comparable across arms |
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
