# scProfile

**Profile an annotated single-cell or single-nucleus dataset: cell cycle, RNA velocity,
pseudotime, regulons, pathway and TF activity, cell–cell communication, differential abundance.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Each method is a **plugin** that declares what it NEEDS; the builder resolves every plugin's
needs together and builds as few environments as satisfy them all, sharing where it can prove that
is safe and isolating where it cannot — and saying which, and why. Install the ones you want; the
rest appear in the report as not run, with the reason.

Takes the output of [scQC](https://github.com/JiaenLin/scQC) →
[scAnno](https://github.com/JiaenLin/scAnno) →
[scIntegrate](https://github.com/JiaenLin/scIntegrate), or any `.h5ad` with counts, a label column
and a sample column.

**This README is for people running an analysis.** You install scProfile, point it at an object,
and run `plan` and `run`. You never open a plugin, never edit one and never write a wrapper — if
you find yourself doing that, it is a bug in this tool, not a step you were meant to take.

Writing or updating a plugin is a **maintainer** job:
**[docs/MAINTAINING_PLUGINS.md](docs/MAINTAINING_PLUGINS.md)**.

📖 For users: **[Run plan](docs/RUN_PLAN.md)** · **[Reference data](docs/REFERENCES.md)**
📖 For developers: **[Plugin design](docs/PLUGIN_DESIGN.md)** · **[Architecture](docs/ARCHITECTURE.md)** · **[Maintaining plugins](docs/MAINTAINING_PLUGINS.md)** · **[Execution](docs/EXECUTION.md)** · **[Design](DESIGN.md)** · **[Roadmap](ROADMAP.md)**

---

## Install

```bash
pip install -e '.[run]'

scprofile doctor                              # what you have, what you need
scprofile plan   --h5ad c.h5ad --all          # what WOULD run, and what stops it
scprofile validate                            # static checks on plugins and references
scprofile scaffold abundance                  # a declared plugin's build skeleton
scprofile install velocity --prefix ~/envs    # build a plugin's environment
scprofile fetch   scenic --to ~/refs --dry-run  # how much, and does it fit
scprofile run    --h5ad c.h5ad --out r/ --all
```

**`plan` first.** It reads the object, resolves every prerequisite, searches for inputs that are
not in the object but may be beside it, and ends with the command that closes each gap. It runs
nothing, and every refusal a real run would produce arrives in seconds.

A gap is only ever one of four things, and **only the last is a reason to skip a plugin**: an
input that is elsewhere on disk (find it), a missing environment (install it), a missing
implementation (build it), or a design that cannot support the test — which is a finding about the
experiment and belongs in the report whether or not the plugin runs.

The host needs numpy and pandas; `[run]` adds anndata and scanpy. Kernel environments are built
with conda/mamba, or point scProfile at ones you already have with
`SCPROFILE_<KERNEL>_PYTHON`.

Installing a kernel builds **the environment it resolves to** — which several plugins may share —
and then runs the selftest of every plugin in it. A real computation, not a set of imports, so a
broken environment is found before a run is spent on it; and every plugin, not only the one you
asked for, because an environment shared by four and proved by one is an environment the other
three meet for the first time inside a run.

```
scprofile install decoupler --prefix ~/envs --dry-run   # which environment, shared with whom
  environment scprofile-env-3cd799b82e
      shared by: decoupler, liana, pseudotime, velocity
```

## Run

```bash
scprofile run --h5ad cohort.h5ad --out results/ --prefix ~/envs --all
```

Keys, organism and assay are detected and printed:

```
what this object is, and how each was decided:
  label          cell_type              detected: the first of ['cell_type', ...] present
  sample         sample                 detected
  counts_layer   counts                 detected
  organism       mouse                  6/6 probe genes are Title Case
  assay          nucleus                unspliced is 71% of counts, the nuclear pattern
  constraint     uns['scintegrate']     read from the object
```

Override any of them: `--label-key`, `--organism`, `--assay`, `--counts-layer`, and so on.
Then read `report/index.html`.

## Kernels

| kernel | gives you | needs |
|---|---|---|
| `cellcycle` | phase, S and G2M scores | — |
| `velocity` | direction of transcriptional change | spliced/unspliced layers |
| `pseudotime` | ordering along a trajectory | an embedding, `cellcycle` |
| `scenic` | regulon activity inferred from your data | counts, cisTarget databases |
| `decoupler` | TF and pathway activity from curated priors | — |
| `liana` | cell–cell communication, consensus over several methods | — |
| `cellchat` | cell–cell communication, CellChat's own scoring | R, CellChatDB |
| `abundance` | whether a cell type shifts across your design | a design table |

Built today: `cellcycle`, `velocity`. The rest are declared with their prerequisites and appear in
`doctor`; [`ROADMAP.md`](ROADMAP.md) is the order they arrive in and what was evaluated and
declined.

Run `scenic` with `decoupler` to compare a network inferred from your data against curated priors.
Run `liana` with `cellchat` to compare two communication methods. Both pairs write separate
outputs, so results can be held side by side.

## Finding inputs that are not in the object

Spliced and unspliced counts come from the aligner and are absent from almost every object that
has been through QC and annotation — while the aligner output is usually still on disk.

The host harvests the upstream chain recorded in `uns` — tool records recognised by shape, and any
string that resolves to a directory — and passes the leads to the kernel, which searches them for a
velocyto `.loom`, an mtx triplet beside a barcode list, or an `.h5ad` carrying both layers.
Matching is on the barcode core, within each sample, with the match rate printed for every source
tried; a source below threshold is refused rather than partially applied. `--search` adds
directories for data that moved.

A kernel that finds nothing refuses with the list of every directory it looked in.

## Reference data

Some kernels consult data that did not come from your object — a motif ranking, a
ligand–receptor database, a regulatory prior. Those decide answers as much as the algorithm does.

```
scprofile fetch scenic --to <dir> --organism mouse --dry-run   # size, and whether it fits
scprofile fetch scenic --to <dir> --organism mouse             # resumable, verified
scprofile validate scenic --references <dir> --deep            # hashes what is on disk
```

`fetch` reports the total and checks free space before downloading anything, resumes a killed
download from its `.part`, takes one writer per directory, and prints the `sha256` of any file
whose vendor publishes none so it can be declared. A kernel whose references are unusable
**refuses to run**: a missing motif database does not fail, it returns a smaller answer that looks
like a real one.

## Planning a run

```
scprofile plan --h5ad object.h5ad --design design.csv --all --audit
```

`plan` runs nothing. It gives every plugin one of four verdicts — **RUN** (with the capacity rung
it will run at, and why not a higher one), **SKIP** (the *design* cannot support it, citing the
factor and its arm sizes), **BLOCKED** (the *data* is absent, naming every place it looked), or
**UNRESOLVED** (the scan could not determine — which is a defect in the plan, never a skip).

`--audit` then checks the plan by rules that do not repeat its reasoning: that every plugin is
accounted for exactly once, that no verdict is UNRESOLVED, that every SKIP cites a design fact the
design table actually supports, that every BLOCKED searched somewhere, and that no plugin was left
at a lower rung than the project would support.

**[`docs/RUN_PLAN.md`](docs/RUN_PLAN.md) is the guideline** the plan follows, and the reasoning
behind the four verdicts.

**[`docs/REFERENCES.md`](docs/REFERENCES.md) is the register** — every reference every kernel
uses, who published it, under what terms, and which of them this tool can actually verify. Not all
of them can be: a database bundled inside a package version is pinned by that version and by
nothing else.

## Output

```
results/
  objects/cohort_profiled.h5ad   cell-level results, merged by barcode
  objects/<kernel>_*.h5ad        side-car objects a kernel ships whole
  tables/*.csv                   edge- and gene-level results, prefixed by kernel
  report/index.html              start here
  report/<kernel>.html           one per kernel
  report.json                    every number, machine-readable
  README.md                      written by inspecting the directory
```

Cell-level results merge into the object by barcode. Cell–cell communication is edge data — cell
type × cell type × ligand–receptor — and goes to CSV beside it. A kernel whose result does not fit
the merged object ships its own file: velocity is fitted on a selected gene set, so padding its
layers back onto the full gene list would assert zero velocity where the truth is *not fitted*.

`uns['scprofile']` records which kernels ran, at which versions, against which references, and the
caveats each declared.

## Figures

Every panel is written as a raster preview and a vector PDF with live text, at journal column
width, with a caption and the table it was drawn from. Points are rasterised and axes are not, so
a 100,000-cell embedding stays a few hundred kilobytes without turning its labels into paths.
Colours are colourblind-safe and stable across panels.

## Adding a kernel

A plugin is ONE FILE — `kernels/<name>.py` holding a `PLUGIN` dict and a `run(ctx)`. Dropping it
in is the whole installation; the host reads the declaration without importing it, resolves the
environment, and runs it through the shared entrypoint.

```python
PLUGIN = {
    "api": 1, "summary": "...", "cannot_show": [...],
    "inject": {"required": ["lognorm", "label"], "optional": ["design"]},
    "produces": ["obs[my_score]"],
    "requires": {"python": ">=3.10,<3.13", "packages": {"mytool": ">=1.2,<1.3"}},
}
def run(ctx): ...
def selftest(ctx): ...
def guard(g): ...        # optional: refuse datasets where the result would mislead
```

`produces` may name an output only some runs make - `"obs[latent_time]?"` - and may glob a name
chosen at run time - `"obsm[velocity_*]"`. Both are held to: the `?` says the ABSENCE is not
drift, and the glob still refuses a name that does not match it.

The older directory shape still loads, and is what a plugin in another language uses:

```
kernels/<name>/
  kernel.yml       what it needs, what it produces, what it cannot show
  lock.yml         a fully-pinned environment - read as the strictest possible requirement
  references.yml   reference data, with checksums
  run.py | run.R   entry point: reads in.json, writes out.json
  guard.py         optional: refuse datasets where the result would mislead
  selftest.py      proves the environment works
```

Every plugin shipped here is one file. The directory shape is kept because a plugin written in
another language needs it, and because nothing that worked should stop working - but it is not
the shape to write a new plugin in.

Kernels talk to the host through JSON — write your results, declare them in `out.json`, and the
host merges and reports them. Any language.

Point `$SCPROFILE_KERNELS` at your own directory to add kernels without forking. Site kernels
override shipped ones, and `doctor` reports when that happens.

## Behaviour

- Results merge **by barcode**, never by position. A kernel returning a different cell order is
  merged correctly or refused with the counts.
- A kernel is held to what it declares. Output not listed under `produces` is flagged; patterns
  are allowed for outputs named after a runtime choice.
- Prerequisites are checked before anything runs, and every refusal names the fix.
- Guards refuse datasets where a kernel's output would not mean what its report says. `--allow
  <kernel>` overrides, and every override is logged to `guard_overrides.jsonl`.
- A missing reference stops a kernel rather than producing a smaller result.
- The host asks each kernel's own interpreter whether it can read the object before launching it,
  and writes one compatibility copy if not — a kernel pinned to an older anndata cannot read the
  encodings a current one writes.
- Nothing is assumed about your data: no column name, organism, assay, design or cell type.
  scIntegrate is optional.

## Requirements

Python 3.10+. Kernel environments are built with conda, mamba or micromamba.

## License

MIT — see [LICENSE](LICENSE).
