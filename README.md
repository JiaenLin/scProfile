# scProfile

Profile an annotated single-cell or single-nucleus dataset: cell cycle, RNA velocity, pseudotime,
regulons, pathway and TF activity, cell–cell communication, differential abundance.

Takes the output of [scQC](https://github.com/JiaenLin/scQC) →
[scAnno](https://github.com/JiaenLin/scAnno) → [scIntegrate](https://github.com/JiaenLin/scIntegrate),
or any `.h5ad` with counts, a label column and a sample column.

```bash
pip install -e '.[run]'

scprofile doctor                                     # what you have, what you need
scprofile install scenic --prefix ~/envs             # build a kernel's environment
scprofile fetch   scenic --to ~/references           # get its reference data
scprofile run --h5ad cohort.h5ad --out results/ --all
```

## Kernels

Each method is a kernel with its own environment. Install the ones you want; the rest appear in
the report as not run.

| kernel | gives you | needs |
|---|---|---|
| `cellcycle` | phase, S and G2M scores | — |
| `velocity` | direction of transcriptional change | spliced/unspliced layers |
| `pseudotime` | ordering along a trajectory | an embedding, `cellcycle` |
| `scenic` | regulon activity per cell, inferred from your data | counts, cisTarget databases |
| `decoupler` | TF and pathway activity from curated priors | — |
| `liana` | cell–cell communication, consensus over several methods | — |
| `cellchat` | cell–cell communication, CellChat's own scoring | R, CellChatDB |
| `abundance` | whether a cell type shifts across your design | a design table |

Run `scenic` with `decoupler` to compare a network inferred from your data against curated priors.
Run `liana` with `cellchat` to compare two communication methods. Both pairs write separate
outputs, so you can hold them side by side.

## Getting started

**See what you have.**

```bash
scprofile doctor
```

```
  ok    cellcycle  host       runs in the host interpreter
        when: cell-cycle phase per cell, and the check that a trajectory is not a cell-cycle axis
  MISS  velocity   missing    nothing at ~/envs/scprofile-velocity
        fix: scprofile install velocity --prefix ~/envs
        when: your object carries spliced and unspliced layers and you want direction of change
        needs: layers spliced, unspliced
```

**Run it.** Keys, organism and assay are detected and printed:

```
what this object is, and how each was decided:
  label          cell_type              detected: the first of ['cell_type', ...] present
  sample         sample                 detected
  counts_layer   counts                 detected
  organism       mouse                  6/6 probe genes are Title Case
  assay          nucleus                unspliced is 71% of counts, the nuclear pattern
  constraint     uns['scintegrate']     read from the object
```

Override any of them: `--label-key`, `--organism`, `--assay`, and so on.

**Read `report/index.html`.** One page per kernel, plus an index listing every kernel — including
the ones that did not run, and why.

## Output

```
results/
  objects/cohort_profiled.h5ad   cell-level results, merged by barcode
  tables/*.csv                   edge-level results, prefixed by kernel
  report/index.html              start here
  report/<kernel>.html           one per kernel
  report.json                    every number, machine-readable
  README.md                      written by inspecting the directory
```

Velocity layers, pseudotime and regulon scores go into the object. Cell–cell communication is edge
data — cell type × cell type × ligand–receptor — and goes to CSV beside it.

`uns['scprofile']` records which kernels ran, at which versions, against which references, and the
caveats each one declared.

## Adding a kernel

A kernel is a directory:

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
override shipped ones, and `doctor` says when that happens.

## Behaviour worth knowing

- Results merge **by barcode**, never by position. A kernel returning a different cell order is
  merged correctly or refused with the counts.
- A kernel is held to what it declares. Output not listed under `produces` is flagged.
- Prerequisites are checked before anything runs, and every refusal names the fix.
- Guards can refuse a dataset where a kernel's output would not mean what its report says.
  `--allow <kernel>` overrides; overrides are logged to `guard_overrides.jsonl`.
- A missing reference stops a kernel rather than producing a smaller result.
- Nothing is assumed about your data — no column name, organism, assay, design or cell type.
  scIntegrate is optional.

`DESIGN.md` has the full contract and the reasoning.

## Requirements

Python 3.10+. The host needs numpy and pandas; `[run]` adds anndata and scanpy. Kernel
environments are built with conda/mamba, or point scProfile at ones you already have using
`SCPROFILE_<KERNEL>_PYTHON`.
