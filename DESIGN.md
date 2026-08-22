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

Seven, each independently installable. **Not each with its own environment** — a plugin declares
what it NEEDS and the builder resolves every plugin's needs together into as few environments as
satisfy them all, sharing where it can prove that is safe and isolating where it cannot. On the
shipped set that is 6 plugins in 3 environments. See `docs/ARCHITECTURE.md` §1a.

| kernel | what it produces | needs |
|---|---|---|
| `cellcycle` | `obs[phase, S_score, G2M_score]` | nothing beyond the object |
| `velocity` | `obs[velocity_confidence, velocity_length, velocity_pseudotime]`, `obsm[velocity_*]`, `objects[velocity_h5ad]` | **spliced/unspliced layers** |
| `pseudotime` | `obs[pseudotime]`, `uns[paga]` | an embedding, and `cellcycle`; **uses `velocity` when present** |
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

### `velocity` and `pseudotime`: independent, and one orients the other

They are separate kernels because they answer separate questions and because **most datasets can
run only one of them.** Spliced/unspliced counts come from the aligner; an object quantified
without them has no route to velocity, and making pseudotime depend on velocity would put a
trajectory out of reach of the majority of data that reaches this tool.

Four things get conflated under "pseudotime", and they are not interchangeable:

| | what it measures | needs unspliced | gives a direction |
|---|---|---|---|
| diffusion pseudotime (DPT) | distance along the expression kNN graph from a root | no | **no** — you choose the root |
| `velocity_pseudotime` | DPT on the **velocity** graph, root inferred from where the arrows point | yes | yes |
| `latent_time` | the dynamical model's gene-shared time — a fitted kinetic parameter, not a graph distance | yes, plus the slow fit | yes |
| CellRank fate probabilities | a Markov chain built from velocity, *or* a pseudotime, *or* similarity, *or* real time | optional | depends on its input |

**The connection is orientation.** An expression-graph pseudotime gives an axis and cannot say
which end is the beginning; that is normally an analyst pointing at the cluster they believe is the
start. Velocity makes the decision from the data instead.

So `velocity` ships its fitted object — velocity graph included — as a side-car, and `pseudotime`
reads it through `in.json`'s `upstream`. Without it, `pseudotime` still runs and reports an
**unoriented** axis, saying so. With it, the two are computed and **compared**: an orientation that
disagrees with the root-cell version is a finding, not a detail to reconcile silently.

`velocity` also writes `velocity_pseudotime` itself, because it is nearly free once the graph
exists. It is the weaker of that kernel's two claims and is labelled as such — the single-nucleus
validation in the literature is *directional* (r 0.94–0.99 against matched cells), and that
comparison did not extend to a pseudotime derived from the arrows.

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
  UPSTREAM.md     what the wrapped tool's own documentation says
  selftest.py      proves the env works before a run is spent on it
```

### Installing

```bash
scprofile install scenic --prefix ~/envs --dry-run   # which environment, shared with whom
scprofile install scenic --prefix ~/envs      # builds THAT environment, then runs the selftest
                                              # of every plugin resolving to it
scprofile doctor                              # which kernels are installed, missing, or STALE
```

The unit of installation is the resolved environment, not the plugin: it is built whole, from the
merged requirement, and proved for every member — an environment shared by four and proved by one
is one the other three meet for the first time inside a run.

A kernel whose requirement has changed since its env was built is **stale**, and that is a third
state — neither present nor absent. Sites with existing environments override via config; `doctor` says
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

### Four patterns taken from the agent harness this was built inside

The harness that runs these tools had already solved several of these problems, and the design was
half-reinventing them. Adopted verbatim:

| harness | here |
|---|---|
| a skill's `description` says **when** to use it, so a router judges relevance without loading it | `when_to_use` in `kernel.yml`; `doctor` reports whether a kernel is RELEVANT to this dataset, not only whether it is installed |
| `allowed-tools` — a skill is **held to** what it declared | `produces` is checked against what the kernel actually wrote. An undeclared output is reported everywhere, because nothing in `cannot_show` covers it and no documentation mentions it |
| a `PreToolUse` hook **denies** an action and names the remedy, and its escape is **logged** | `guard(g)` in a one-file plugin, or `guard.py` in the directory shape — run in the host before anything is spent. `--allow <kernel>` overrides, and every override lands in `guard_overrides.jsonl` with its reason |
| plugin namespacing makes an override visible | a site kernel shadowing a shipped one is legitimate and is why `$SCPROFILE_KERNELS` exists — doing it **silently** is not, so `doctor` prints it |

The escape-hatch rule is the harness's own, and it is the one worth stating twice: **a gate with no
escape gets switched off; a gate whose escapes are all recorded does not.**

A guard is not a prerequisite check. `unmet()` refuses when a required layer is absent — that is
structural, and no willingness makes it runnable. A guard is about **interpretability**: the run
would succeed, produce numbers, and those numbers would not support the sentence a reader writes
under them.

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

---

## UPSTREAM.md — required for any plugin that wraps a tool

A plugin that wraps someone else's tool MUST carry `UPSTREAM.md`: **what that tool's own
documentation says**, with links, recorded so the wrapping can be checked against the source
rather than against the author's memory.

It states, at minimum:

- the **documented signature** with every default, and where results are written;
- **every default that is wrong for this contract, and why** — a default that silently produces a
  plausible wrong answer is the reason this file exists;
- **what the tool drops** at its defaults, so those become named absences instead of empty rows;
- **what the tool can do that the plugin does not use yet**, so under-use is visible and
  deliberate rather than accidental;
- the **licence and citation**.

Where `UPSTREAM.md` and the installed package disagree, **the installed package is right** and the
file is stale. `selftest.py` asserts the signature the plugin actually depends on, so the drift is
caught by a run rather than by a reader.

The clearest case so far: LIANA+ defaults to a **human** ligand-receptor resource. Run against
mouse symbols it does not error — it matches almost nothing, or the few symbols that coincide
between species, and returns a small plausible table. Nothing in the output says the resource was
for the wrong organism.

---

## A design defect is the only legitimate reason to skip a plugin

Four things stop a plugin, and only one of them is a reason not to run it.

| stops it | is | what to do |
|---|---|---|
| the input is not in the object | often **on disk elsewhere** | find it and pass it |
| no environment | **work** | install it |
| no implementation | **work** | build it |
| **the design cannot support the test** | a **finding about the experiment** | report it, whether or not the plugin runs |

The first three are findings about the tooling. Listing them beside the fourth makes the two look
alike, and a reader cannot then tell *this experiment cannot answer that question* from *nobody has
written this yet*. Those are opposite facts and they have opposite remedies.

So `plan` separates them: fixable gaps are printed with the command that closes each, under a
heading that says they are all fixable; design limits are printed separately and marked as
belonging in the report **whether or not the plugin runs**.

The rule this encodes: **a plugin is never skipped for a reason that is work.** If it cannot run
because something is missing, the missing thing gets built. If it cannot run because the
experiment cannot answer the question, that is the result, and it is written down.
