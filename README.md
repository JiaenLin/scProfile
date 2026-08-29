# scProfile

**Profile an annotated single-cell or single-nucleus dataset.** Cell cycle, RNA velocity,
pseudotime, regulons, pathway and TF activity, cell–cell communication, differential abundance
and differential expression — from one object, in one run, into one report.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

```bash
pip install -e '.[run]'

scprofile plan --h5ad cohort.h5ad --design design.csv --all --report plan/
scprofile run  --h5ad cohort.h5ad --design design.csv --all --out results/
open results/report/index.html
```

Works on any `.h5ad` with counts, a cell-type label and a sample column. Pairs directly with
[scQC](https://github.com/JiaenLin/scQC) → [scAnno](https://github.com/JiaenLin/scAnno) →
[scIntegrate](https://github.com/JiaenLin/scIntegrate).

**You never write a wrapper.** Install scProfile, point it at an object, run `plan` then `run`.
Writing or updating a method is a maintainer job — see
[docs/MAINTAINING_PLUGINS.md](docs/MAINTAINING_PLUGINS.md).

---

## What you get

| method | gives you | needs |
|---|---|---|
| `cellcycle` | phase, S and G2M scores per cell | — |
| `velocity` | direction of transcriptional change | spliced/unspliced layers |
| `pseudotime` | ordering along a trajectory, with fate probabilities | an embedding, `cellcycle` |
| `scenic` | regulon activity, from a network inferred from your data | counts, cisTarget databases |
| `decoupler` | TF and pathway activity, from curated priors | — |
| `liana` | cell–cell communication, consensus over several methods | — |
| `cellchat` | cell–cell communication, CellChat's scoring | R, CellChatDB |
| `abundance` | whether a population's share shifts across your design | a design table |
| `de` | which genes change, per cell type, across your design | a design table with replicates |

Run `scenic` with `decoupler` to compare a network inferred from your data against curated
priors. Run `liana` with `cellchat` to compare two communication methods. Both pairs write
separate outputs, so you can hold the results side by side.

## Plan before you run

```bash
scprofile plan --h5ad cohort.h5ad --design design.csv --all --audit --report plan/
```

`plan` reads the object, resolves every prerequisite, searches for inputs that live beside the
object rather than in it, and prints the command that closes each gap. It runs nothing and takes
seconds.

Every method gets one of four verdicts:

- **RUN** — with the capacity it will run at, and what would raise it
- **SKIP** — your design cannot support this test, citing the factor and its arm sizes
- **BLOCKED** — the data is absent; every directory searched is named
- **UNRESOLVED** — the scan could not determine. A defect in the plan, never a skip.

`--audit` checks the plan against rules that do not reuse its reasoning: every method accounted
for exactly once, nothing UNRESOLVED, every SKIP citing a fact the design table supports, every
BLOCKED naming where it looked.

`--report` writes an HTML page — what will run, in what order, with what settings, what each
result lets you say, and what it does not.

## Install methods

```bash
scprofile doctor                                    # what you have, what you need
scprofile install scenic --prefix ~/envs --dry-run  # which environment, shared with whom
scprofile install scenic --prefix ~/envs
```

Each method declares the versions it needs. The builder resolves them together and builds as few
environments as satisfy them all — sharing where that is provably safe, isolating where it is
not, and telling you which and why.

```
scprofile install decoupler --prefix ~/envs --dry-run
  environment scprofile-env-3cd799b82e
      shared by: decoupler, liana, pseudotime, velocity
```

Installing builds the environment and runs the selftest of **every** method in it — a real
computation, not a set of imports. Point at environments you already have with
`SCPROFILE_<METHOD>_PYTHON`.

The host itself needs only numpy and pandas; `[run]` adds anndata and scanpy. Method
environments are built with conda, mamba or micromamba.

## Run

```bash
scprofile run --h5ad cohort.h5ad --out results/ --prefix ~/envs --all
```

Keys, organism and assay are detected and printed, and any can be overridden with `--label-key`,
`--sample-key`, `--counts-layer`, `--organism`, `--assay` and the rest:

```
what this object is, and how each was decided:
  label          cell_type          detected: first of ['cell_type', ...] present
  sample         sample             detected
  counts_layer   counts             detected
  organism       mouse              6/6 probe genes are Title Case
  assay          nucleus            unspliced is 71% of counts, the nuclear pattern
```

Methods run in waves, several at a time. Each gets a share of the allocation — cores, memory and
GPUs — sized from what it declared and from how many cells it will actually touch. Memory is a
fixed cost plus a per-cell one, so a method processing one sample is not charged as though it were
processing the cohort.

Every run measures what each method actually cost and prints the two terms fitted from its own
instances, ready to paste into a declaration. A method that declares no memory is scheduled on a
conservative assumption and the run says so, every time.

The run also **cannot change underneath itself**: it copies the tool into the run directory and
runs from there, so updating your checkout mid-run cannot reach it, and the host refuses any
instance whose code has moved since the run began.

## Output

```
results/
  objects/cohort_profiled.h5ad   cell-level results, merged by barcode
  objects/<method>_*.h5ad        side-car objects a method ships whole
  tables/*.csv                   edge- and gene-level results, prefixed by method
  report/index.html              start here
  report/<method>.html           one page per method
  report.json                    every number, machine-readable
  README.md                      written by inspecting the directory
```

Cell-level results merge into the object by barcode, never by position. Communication results are
edge data — cell type × cell type × ligand–receptor — and go to CSV beside it. A method whose
result does not fit the merged object ships its own file.

`uns['scprofile']` records which methods ran, at which versions, against which references, and
the caveats each declared.

## Figures

A plugin declares its figures in `PLUGIN["report"]["figures"]` and draws them with
`ctx.emit_figure`.

The host draws three things itself, from a plugin's `unit_network` declaration:

- the **design panel** — every contrast the design supports, described;
- the **between-arm comparisons** — for each contrast, drawn from cells pooled within each arm;
- the **per-arm networks** — a ring and a chord for every arm.

```python
"unit_network": {"table": "tables/ccc_edges.csv", "source": "source",
                 "target": "target", "weight": "prob", "group": "pathway_name"}
```

`weight` must be a magnitude, not a rank. `group` is optional. Any plugin that declares this
gets the panels; no host code names a method.

Two rules apply throughout:

- **The group is the unit.** Comparisons are drawn from cells pooled within an arm, whatever the
  arm sizes. The sample axis reports whether the members of a group agree; it never gates a
  panel.
- **Statistics come from the wrapped method.** The host computes none of its own. Where a method
  ships no test, the panel is descriptive and says so.

`scprofile standard` measures the rendered cohort page. `scprofile review` records which figures
have been looked at.

**Panel kinds, the rules each obeys, and the report page layout are in
[docs/REFERENCE.md](docs/REFERENCE.md).**

## Inputs that are not in the object

Spliced and unspliced counts come from the aligner and are missing from almost every object that
has been through QC and annotation — while the aligner output is usually still on disk.

scProfile reads the upstream chain recorded in `uns`, hands those leads to the method, and
searches them for a velocyto `.loom`, an mtx triplet beside a barcode list, or an `.h5ad`
carrying both layers. Matching is on the barcode core, within each sample, with the match rate
printed for every source tried. A source below threshold is refused rather than partly applied.

`--search <dir>` adds directories for data that has moved. A method that finds nothing refuses
and lists every directory it looked in.

## Reference data

Some methods consult data that did not come from your object — a motif ranking, a
ligand–receptor database, a regulatory prior. These decide answers as much as the algorithm does.

```bash
scprofile fetch scenic --to ~/refs --organism mouse --dry-run   # size, and whether it fits
scprofile fetch scenic --to ~/refs --organism mouse             # resumable, verified
scprofile validate scenic --references ~/refs --deep            # hashes what is on disk
```

`fetch` checks free space before downloading, resumes a killed download, and takes one writer per
directory. A method whose references are unusable **refuses to run** — a missing motif database
does not fail loudly, it returns a smaller answer that looks like a real one.

Not every reference is a file you download. A method declares which kind each one is, so the plan
can tell you before you spend a queue slot:

| tier | meaning |
|---|---|
| `fetch` | downloadable and checksummed — scProfile gets it and verifies it |
| `bundled` | ships inside a package, pinned by that version and nothing else |
| `runtime` | fetched by the tool **while it runs** — needs network on the compute node |

That last one matters on a cluster: `plan` names every method that will reach the network mid-run,
so a batch node with no outbound route is a problem you find in the plan rather than an hour in.

[docs/REFERENCES.md](docs/REFERENCES.md) lists every reference, its publisher, its terms, and
which of them scProfile can verify.

## Reusing an earlier run

A run is expensive. scProfile can report what an earlier run already computed, whether it is
still valid, and whether it is fit to build on — and adopt it into a new run by hardlink.

```
scprofile status    --out RUNDIR                # what is left in this run
scprofile landscape --root RUNS --h5ad OBJ      # what earlier runs hold, and what to compute
scprofile licence   --out RUNDIR --grant        # evaluate results and licence them for reuse
scprofile review    --out RUNDIR                # which figures have not been looked at
```

Reuse requires three things to be true at once:

1. **The result exists and is finished** — `status` reads the instance directory.
2. **It is the same thing** — the reuse key covers plugin, version, unit, input identity, params
   and keys. Nothing else.
3. **It is fit to build on** — the producing run's `RUN_CARD.json` verdict.

A licence records the evidence for all three plus, optionally, that the figures were looked at.
Adoption re-verifies every hash and then hardlinks, so an adopted file cannot differ from the
licensed one.

Grades are `refused`, `retrospective`, `provisional` and `full`. The grade comes from evidence;
which grades you accept is set at adoption.

**Definitions of every criterion, grade, verdict and file are in
[docs/REFERENCE.md](docs/REFERENCE.md).**

## Reading the results

Every method states what its result cannot tell you, and that statement appears in the report
under the result itself. Composition is relative, and every effect is named against its reference
population. Velocity is a direction, not a rate. Co-expression with a motif is not regulation.

Guards refuse datasets where a method's output would not mean what its report says. `--allow
<method>` overrides, and every override is written to `guard_overrides.jsonl`.

When an upstream tool has recorded a constraint on the object — a factor that is not identifiable
because it never varies within a batch, say — scProfile reads it and reproduces it, and a method
whose claim it forbids refuses rather than returning a number.

### The report is measured, and it says so

A rendered report is held to a standard measured on the artifact itself — the HTML that was
written and the figures it references, never a fixture. Ten criteria: that a page opens with what
the cohort was, that something on it compares the design, that no panel is the same plot redrawn
per sample, caps on figures and on prose, that an unmapped identifier is named as one, and that a
refutation the method made against its own headline appears where the headline is.

Whatever writes a report measures it, so the verdict arrives with the run rather than when
somebody remembers to ask:

```bash
scprofile standard --out <run dir>     # non-zero when the standard is not met
```

`ok` means the criterion was checked and passed. `exempt` means the page declared, with a reason
printed beside it, that the criterion cannot apply — a cohort with no design table can never draw
a panel comparing arms. `n/a` means it could not be measured at all. None of the three is
reported as either of the others: a column of ticks that includes checks nobody could run stops
meaning anything.

## Adding a method

A plugin is **one file**: `kernels/<name>.py` with a `PLUGIN` dict and a `run(ctx)`. Dropping it
in is the whole installation. The host reads the declaration without importing it, resolves the
environment, and runs it through a shared entrypoint that applies the contract.

```python
PLUGIN = {
    "api": 1,
    "summary": "what it gives you",
    "inject": {"required": ["counts", "label"], "optional": ["sample"]},
    "produces": ["obs[my_score]", "tables/my_result.csv"],
    "requires": {"python": ">=3.10,<3.13", "packages": {"scanpy": ">=1.10,<1.11"}},
    "cores": 4, "memory_gb_base": 4, "memory_gb_per_100k": 8,
    "cannot_show": ["what a reader must not conclude from this"],
}

def run(ctx): ...
def selftest(ctx): ...
def guard(g): ...        # optional: refuse datasets where the result would mislead
```

Methods ask for **capabilities**, not column names, so a plugin never binds itself to one
project's schema. `produces` may mark an output only some runs make — `"obs[latent_time]?"` — and
may glob a name chosen at run time — `"obsm[velocity_*]"`. Both are held to.

Plugins talk to the host through JSON: write your results, declare them in `out.json`, and the
host merges and reports them. Any language. A directory layout is also supported, which is what a
plugin written outside Python uses.

Point `$SCPROFILE_KERNELS` at your own directory to add methods without forking. Site methods
override shipped ones, and `doctor` reports when that happens.

Full contract: [docs/PLUGIN_DESIGN.md](docs/PLUGIN_DESIGN.md) ·
[docs/MAINTAINING_PLUGINS.md](docs/MAINTAINING_PLUGINS.md).

## Requirements

Python 3.10+.

## Documentation

**Users:** you run scProfile and read its reports. You never write a plugin.

| document | what it covers |
|---|---|
| [REFERENCE.md](docs/REFERENCE.md) | **Every element defined once** — concepts, commands, run-directory files, reuse, licences, figures, the exit standard |
| [RUN_PLAN.md](docs/RUN_PLAN.md) | How the plan is built and how to read it |
| [RESUME.md](docs/RESUME.md) | Resuming a run, and reuse across runs |
| [REPORTING.md](docs/REPORTING.md) | How the documents are assembled |
| [REFERENCES.md](docs/REFERENCES.md) | Reference data: declaring, fetching, verifying |

**Maintainers:** you write or repair plugins.

| document | what it covers |
|---|---|
| [PLUGIN_DESIGN.md](docs/PLUGIN_DESIGN.md) | Writing a plugin |
| [MAINTAINING_PLUGINS.md](docs/MAINTAINING_PLUGINS.md) | Keeping a plugin's declaration true |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the host, plugins and environments fit together |
| [EXECUTION.md](docs/EXECUTION.md) | Scheduling, cores, memory and waves |
| [DEVLOG.md](docs/DEVLOG.md) | Development history |
