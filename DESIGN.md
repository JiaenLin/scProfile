# scProfile — design

**Status: agreed 2026-08-18, not yet built.** This document is the contract. Where the code and
this file disagree, one of them is a bug.

scProfile profiles an annotated, optionally integrated single-cell or single-nucleus dataset.
It is a **host for kernels**, not an analysis: the host knows about manifests, environments,
provenance and reports, and knows nothing about velocity, regulons or ligand–receptor pairs.

---

## 0. What it must run on

**Any dataset processed by scQC → scAnno → scIntegrate.** Not this cohort. That forbids, concretely:

| forbidden | because |
|---|---|
| assuming any obs column name | scAnno's `--label-obs` lets the user name them. `cell_type` is a convention, not a guarantee |
| assuming an organism | every reference is organism-keyed; mouse and human at minimum |
| assuming cells rather than nuclei | it changes the **caveats**, not the code. Velocity on nuclei is not velocity on cells |
| assuming a design shape | 2×2, paired, time-course and single-group must all work — or no design at all |
| naming a cell type anywhere in the source | a tool that mentions `Cardiomyocyte` is a tool for one tissue |
| requiring scIntegrate | a dataset may stop after scAnno. Integration output is **read if present, named if absent** |
| requiring spliced/unspliced | most datasets do not have them. The velocity kernel refuses by name; nothing else notices |

**The minimum input** is one `.h5ad` with: raw counts in a layer, a label column, a sample column.
Everything else — an embedding, a batch key, a design table, `uns['scintegrate']` — is optional and
its absence is reported rather than assumed away.

---

## 1. Kernels

Seven, each independently installable, each with its own environment.

| kernel | what it produces | needs |
|---|---|---|
| `cellcycle` | `obs[phase, S_score, G2M_score]` | nothing beyond the object |
| `velocity` | `layers[velocity, Ms, Mu]`, `obs[velocity_confidence]` | **spliced/unspliced layers** |
| `pseudotime` | `obs[pseudotime]`, `uns[paga]` | an embedding, and `cellcycle` |
| `scenic` | `obsm[X_regulon_auc]`, `tables/regulon_targets.csv` | counts, cisTarget refs |
| `decoupler` | `obsm[X_tf_activity, X_pathway_activity]` | lognorm; prior nets |
| `liana` | `tables/ccc_edges.csv` | lognorm, labels |
| `cellchat` | `tables/ccc_edges.csv` (its own scoring) | **R**, CellChatDB |
| `abundance` | `tables/abundance_tests.csv` | a design, and the constraint |

**Two are deliberate cross-checks rather than additions.** `decoupler` applies *curated prior*
regulons where `scenic` *infers* a GRN from the data; `liana` is a consensus over several
ligand–receptor methods where `cellchat` is one. Agreement between a pair is evidence; disagreement
is a finding. Neither pair is a duplicate.

`cellcycle` is a **prerequisite of `pseudotime`**, not a sibling. A trajectory that is secretly a
cell-cycle axis is the commonest false positive in this class of analysis, and the check costs
seconds. `--no-cellcycle-check` exists and says in its own help what accepting it means.

---

## 2. The plugin model

**One environment per kernel, called as a subprocess across a file contract.** The host's own
dependencies are **numpy and pandas** and nothing else.

This is not fastidiousness. pySCENIC has historically pinned old numpy; CellChat is R. They cannot
share an interpreter with each other, and need not.

```
kernels/<name>/
  kernel.yml       what it needs, what it produces, what it cannot show
  lock.yml         the environment, captured from a working install
  references.yml   URL + sha256 + size, organism-keyed
  run.py | run.R   the entry point. Reads in.json, writes out.json
  selftest.py      proves the env works before a run is spent on it
```

### Installing

```bash
scprofile install scenic --prefix ~/envs      # builds from lock.yml, then runs selftest
scprofile doctor                              # which kernels are installed, missing, or STALE
```

A kernel whose lock has changed since its env was built is **stale**, and that is a third state —
neither present nor absent. Sites with existing environments override via config; `doctor` says
which route each kernel is using, so it is never ambiguous.

### The contract

**JSON in, JSON out.** The host never guesses what a kernel wrote.

```jsonc
// in.json — written by the host
{ "h5ad": "...", "out_dir": "...",
  "keys":   { "label": "cell_type", "batch": "sample", "sample": "sample",
              "counts_layer": "counts", "embedding": "X_scanvi" },
  "organism": "mouse", "assay": "nucleus",
  "design":  "design.csv",
  "references": { "rankings": "/path/verified.feather" },
  "params": { } }

// out.json — written by the kernel
{ "kernel": "scenic", "version": "...", "status": "ok",
  "obs":     { "…": "obs.csv column" },
  "obsm":    { "X_regulon_auc": "obsm/X_regulon_auc.npy" },
  "layers":  { },
  "tables":  ["tables/regulon_targets.csv"],
  "figures": ["figures/…png"],
  "absent":  [ {"what": "kbet", "why": "…"} ],
  "caveats": ["inferred on nuclei; unspliced fraction is assay-driven"] }
```

The host **validates `out.json` against a schema** and merges only what is declared. A kernel that
produces nothing declares nothing, and that is visible; a kernel that dies leaves no `out.json` at
all, which is a different and equally visible state.

**Cell-level results are joined by BARCODE, never by position.** A kernel that returns a different
cell order — or a subset — is merged correctly or refused, not silently misaligned.

### References

Declared, fetched on request, **never bundled**.

```bash
scprofile fetch scenic --to ~/references
```

Each entry carries a URL, a sha256 and a size. A kernel **refuses by name** when a reference is
missing rather than running against a partial database and returning fewer regulons — an under-
populated result looks exactly like a real one. Compute nodes often have no network, so `fetch`
prints the URL, checksum and destination when it cannot download, for a human to place by hand.

### Ordering

Each kernel **declares its prerequisites** and the host checks them **before spending anything**:

```
REFUSE: pseudotime needs obs['phase'], which is absent.
        Run `--kernel cellcycle` first, or pass --no-cellcycle-check and accept
        that a cell-cycle axis will not be detected.
```

No automatic DAG execution. Asking for one kernel must never silently spend an hour on another.

---

## 3. Output

**One h5ad for cell-level results, sidecar tables for everything else.**

```
results/NN_profile/
  objects/cohort_profiled.h5ad     cell-level: layers, obs, obsm
  tables/*.csv                     edge-level and gene-level
  figures/*.png
  report/index.html                START HERE
  report/<kernel>.html             one per kernel
  report.json                      every number, machine-readable
  README.md                        written by inspecting the directory
```

Cell-cell communication is **edge data** — cell type × cell type × ligand–receptor. It does not fit
`obs` or `obsm`, and forcing it into `uns` makes it readable by this tool and nothing else. It goes
to CSV. Likewise regulon → target gene lists, and abundance test results.

`uns['scprofile']` carries **provenance only**: which kernels ran, at which versions, against which
references, with which parameters, and every caveat each one declared. Not results.

---

## 4. Report

**One document per kernel, plus an index.**

The index carries, for every kernel: whether it ran, its headline number, and **what it cannot
show**. A kernel that was not run is a named absence on the index with the reason — not installed,
prerequisite unmet, reference missing — never a gap.

Every kernel document ends with its own limits, because they differ and a shared block encourages
skipping. Velocity's are not SCENIC's.

---

## 5. What this design refuses to do

- **It will not run a kernel whose environment it cannot verify.** A selftest passes before a run
  is spent.
- **It will not merge by position.** Barcodes or a refusal.
- **It will not present a p-value for a contrast that is not identifiable.** The `abundance` kernel
  reads `uns['scintegrate']['constraint_on_use']`; where the tested factor is nested in the batch
  key it refuses or caveats in the loudest terms the report has. milo and scCODA will happily return
  small p-values for a confounded design, and they read as biology.
- **It will not describe a nucleus as a cell.** The assay is detected or declared and changes what
  every kernel says about its own result.
- **It will not treat an annotator sentinel as a cell type.** Same rule as upstream: `EXCLUDED` and
  `UNRESOLVED` are statements about the annotation.
