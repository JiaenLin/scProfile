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

Methods run in waves, several at a time. Each gets a share of the allocation — cores and memory —
sized from what it declared and from how many cells it will actually touch.

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

Every panel is written as a raster preview and a vector PDF with live text, at journal column
width, with a caption and the table it was drawn from. Points are rasterised and axes are not, so
a 100,000-cell embedding stays a few hundred kilobytes without turning its labels into paths.
Colours are colourblind-safe and stable across panels.

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

[docs/REFERENCES.md](docs/REFERENCES.md) lists every reference, its publisher, its terms, and
which of them scProfile can verify.

## Reading the results

Every method states what its result cannot tell you, and that statement appears in the report
under the result itself. Composition is relative, and every effect is named against its reference
population. Velocity is a direction, not a rate. Co-expression with a motif is not regulation.

Guards refuse datasets where a method's output would not mean what its report says. `--allow
<method>` overrides, and every override is written to `guard_overrides.jsonl`.

When an upstream tool has recorded a constraint on the object — a factor that is not identifiable
because it never varies within a batch, say — scProfile reads it and reproduces it, and a method
whose claim it forbids refuses rather than returning a number.

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
    "cores": 4, "memory_gb_per_100k": 8,
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

**Users:** [Run plan](docs/RUN_PLAN.md) · [Reference data](docs/REFERENCES.md)
**Maintainers:** [Plugin design](docs/PLUGIN_DESIGN.md) ·
[Maintaining plugins](docs/MAINTAINING_PLUGINS.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Execution](docs/EXECUTION.md) · [Design](DESIGN.md) · [Roadmap](ROADMAP.md)

## Licence

MIT. Each wrapped tool keeps its own licence; `scprofile doctor` lists them.
