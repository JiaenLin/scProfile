# scProfile

**Comprehensive profiling of an annotated single-cell or single-nucleus dataset — easy to run.**

Takes the output of scQC → scAnno → scIntegrate and profiles it: cell cycle, RNA velocity,
pseudotime, regulons, pathway and TF activity, cell–cell communication, differential abundance.

```bash
scprofile doctor                      # what is installed, what is missing, and the exact fix
scprofile install scenic --prefix ~/envs
scprofile fetch   scenic --to ~/references
scprofile run --h5ad cohort.h5ad --out results/ --all
```

## It is a host for kernels, not an analysis

Each profiling method is a **kernel**: its own directory, its own environment, its own entry point,
behind a JSON contract. The host depends on **numpy and pandas** and knows nothing about velocity,
regulons or ligand–receptor pairs.

That is not fastidiousness. pySCENIC has historically pinned old numpy; CellChat is R. They cannot
share an interpreter with each other and they do not need to.

```
kernels/<name>/
  kernel.yml       what it needs, what it produces, what it CANNOT show
  lock.yml         the environment, captured from a working install
  references.yml   URL + sha256 + size, organism-keyed
  run.py | run.R   the entry point
  selftest.py      proves the env works before a run is spent on it
```

## Easy to run is a design constraint

Keys, organism and assay are **detected**, and the evidence for each is printed:

```
what this object is, and how each was decided:
  label          cell_type                  detected: the first of ['cell_type', ...] present
  sample         sample                     detected: ...
  counts_layer   counts                     detected: ...
  organism       mouse                      6/6 probe genes are Title Case (['ACTB', 'GAPDH'])
  assay          nucleus                    unspliced is 71% of counts, which is the nuclear pattern
  constraint     uns['scintegrate'][...]    read from the object
```

A wrong guess is one flag away. **Every refusal carries the command that fixes it:**

```
REFUSE: pseudotime needs obs['phase'], which is absent.
        Fix: run --kernel cellcycle first.
```

## Three states, kept distinguishable

A kernel runs in another process, often another language. The host cannot import it or catch its
exceptions — so the kernel **declares** what it produced and the host **validates** that
declaration:

| | means |
|---|---|
| no `out.json` | the kernel died |
| `out.json`, nothing in it | it ran and found nothing — **a result** |
| `out.json` with entries | these things exist, and only these are merged |

A host that globbed the output directory would collapse the first two, and those are opposite facts.

## Merged by barcode, never by position

Nothing guarantees a kernel returns cells in the order it received them. Merging by position
assigns one cell's pseudotime to another, silently, and every figure downstream looks reasonable.
So cell-level results are joined on the barcode and a mismatch is **refused with the counts**.

Cell–cell communication is **edge data** — cell type × cell type × ligand–receptor. It is not
per-cell and never enters the object; it goes to CSV beside it, prefixed by kernel, so running
LIANA *and* CellChat gives you two files to compare rather than one overwriting the other.

## Two pairs are cross-checks, not duplicates

`scenic` infers a GRN **from your data**; `decoupler` applies **curated prior** regulons. `liana`
is a consensus over several ligand–receptor methods; `cellchat` is one. Agreement between a pair
is evidence. Disagreement is a finding. Either beats one number.

And `cellcycle` is a **prerequisite of `pseudotime`**, not a sibling: a trajectory that is secretly
a cell-cycle axis is the commonest false positive in this class of analysis, and the check costs
seconds.

## It runs on any dataset from the upstream tools

No obs column name, organism, assay, design shape or cell type is assumed anywhere. scIntegrate
itself is optional — a dataset may stop after annotation, and the integration output is read if
present and **named if absent**.

The minimum input is one `.h5ad` with raw counts in a layer, a label column and a sample column.

See `DESIGN.md` for the full contract.
