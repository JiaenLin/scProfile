# scProfile

**Profile an annotated single-cell or single-nucleus dataset: cell cycle, RNA velocity,
pseudotime, regulons, pathway and TF activity, cell–cell communication, differential abundance.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Each method is a **kernel** with its own pinned environment. Install the ones you want; the rest
appear in the report as not run, with the reason.

Takes the output of [scQC](https://github.com/JiaenLin/scQC) →
[scAnno](https://github.com/JiaenLin/scAnno) →
[scIntegrate](https://github.com/JiaenLin/scIntegrate), or any `.h5ad` with counts, a label column
and a sample column.

📖 **[Design](DESIGN.md)** · **[Roadmap](ROADMAP.md)**

---

## Install

```bash
pip install -e '.[run]'

scprofile doctor                             # what you have, what you need
scprofile install velocity --prefix ~/envs   # build a kernel's environment
scprofile fetch   scenic   --to ~/references # get its reference data
```

The host needs numpy and pandas; `[run]` adds anndata and scanpy. Kernel environments are built
with conda/mamba, or point scProfile at ones you already have with
`SCPROFILE_<KERNEL>_PYTHON`.

Installing a kernel builds its environment from a pinned lock and then runs the kernel's own
selftest against it — a real computation, not a set of imports — so a broken environment is found
before a run is spent on it.

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

```
kernels/<name>/
  kernel.yml       what it needs, what it produces, what it cannot show
  lock.yml         its environment
  references.yml   reference data, with checksums
  run.py | run.R   entry point: reads in.json, writes out.json
  guard.py         optional: refuse datasets where the result would mislead
  selftest.py      proves the environment works
```

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
