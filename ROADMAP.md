# Kernel roadmap

What scProfile should be able to call, in what order, and what has been looked at and declined.

scProfile is a harness, not an analysis. Its job is to know how to call a tool correctly, on data
that tool can actually answer for, and to say plainly what the answer does not establish. That
makes the interesting question **not** "which tools are popular" but **which questions can be
answered from a counts matrix, a label column and a sample column** — because that is what arrives
from scQC → scAnno → scIntegrate, and most of the field's best tools need something more.

---

## The admission gate

No kernel is added without written answers to all six. They are the entries in `kernel.yml`.

1. **What question does it answer** that no shipped kernel answers?
2. **What does it need** beyond counts + labels + samples? Anything extra is a gate most datasets
   fail, and the kernel must refuse cleanly rather than produce a number.
3. **Can it be installed reproducibly** — a lock that pins, and a selftest that runs the real
   thing? An R tool needs a working bridge before its kernel is worth writing.
4. **What can its output NOT show?** If this list is short, it has not been thought about.
5. **Is there evidence it works**, on data like the target, from someone other than its authors?
6. **What breaks silently** if the input is wrong? This decides whether it needs a `guard.py`.

Two rules that fall out of the gate and are worth stating separately:

- **A tool that needs a modality we do not have is not "future work" — it is a refusal with a
  fix.** Velocity already works this way, and it is the model: search for the data, report where
  you looked, refuse with the remedy named.
- **Where two methods answer the same question differently, ship both.** `scenic` against
  `decoupler`, `liana` against `cellchat`. Agreement is evidence; disagreement is a finding. This
  is the single most useful thing a harness can do that a single tool cannot.

---

## Tier 0 — shipped

| kernel | answers | needs |
|---|---|---|
| `cellcycle` | phase per cell; the check that a trajectory is not a cell-cycle axis | — |
| `velocity` | direction of transcriptional change | spliced/unspliced (searched for, not assumed) |

---

## Tier 1 — next, and in this order

The order is a dependency order, not a preference. Each unlocks the ones under it.

### 1. `pseudotime`
**Answers** ordering along a trajectory, and — with `velocity` — its orientation.
**Needs** an embedding and `cellcycle`. Runs without velocity on any dataset.
**Build on** scanpy DPT + [CellRank 2](https://www.nature.com/articles/s41592-024-02303-9), which
is the right abstraction: it builds a transition matrix from velocity, *or* a pseudotime, *or*
similarity, *or* real time, and returns fate probabilities. It has a 2026 Nature Protocols paper
and is scverse-native.
**Cannot show** that a trajectory is a real transition rather than a similarity gradient. A
continuum of states and a continuum of *cells moving through* states look identical here.
**Guard** refuse, or caveat hard, when the ordering correlates with the cell-cycle score — the
commonest false positive in this class, and the reason `cellcycle` ships first.

### 2. `abundance`
**Answers** does a population's *share* shift across the design.
**Needs** a design table. **Build on** [pertpy](https://www.nature.com/articles/s41592-025-02909-7)
(Nat Methods 2026), which now carries scCODA 2.0, tascCODA 2.0 and Milo in one scverse-native
package — one dependency instead of three, one of them R.
**Ship two by construction**: scCODA (per-label, compositional, handles the sum-to-one constraint)
and Milo (per-neighbourhood, catches shifts inside a label that per-label testing cannot see).
**Cannot show** direction of causation, or absolute cell numbers — composition is relative by
construction, so one population rising makes every other fall.
**Guard, and this one is mandatory**: it must read `uns['scintegrate']['constraint_on_use']` and
refuse when the tested factor is nested in, or aliased with, the batch key. A compositional test
on a confounded factor returns clean p-values for a contrast that is not identifiable.

### 3. `de`
**Answers** which genes change, per cell type, across the design.
**Needs** a design table and replicates. **Build on** pseudobulk + pyDESeq2, with per-cell methods
as an explicit alternative rather than a default.
**Cannot show** anything useful without biological replicates: per-cell tests treat cells as
independent samples, which inflates significance by roughly the number of cells per animal. The
guard should refuse a design with one sample per group outright.

### 4. `scenic` and 5. `decoupler` — deliberately a pair
**Answer** regulon / TF / pathway activity per cell.
`scenic` **infers** a network from the data (pySCENIC; needs cisTarget databases, a large
download, and it is the heaviest environment on this list).
`decoupler` **applies curated priors** — CollecTRI, PROGENy, MSigDB — and is cheap, pure Python,
and needs no reference download.
**Run them together.** They disagree in an informative way: a regulon that both find is well
supported; one only SCENIC finds may be dataset-specific or may be an artefact of co-expression.
GRN benchmarking is an unsettled field — methods recover very different numbers of TFs on the same
data — so a single GRN result should never be reported alone.
**Cannot show** causality. Co-expression with a motif is not regulation, and neither tool observes
a perturbation.

### 6. `liana` and 7. `cellchat` — also a pair
**Answer** which cell types may be signalling to which, through which ligand–receptor pairs.
`liana` is Python and computes a **consensus** across several scoring methods;
`cellchat` is R with its own curated database and scoring.
Benchmarks rank the underlying methods inconsistently — CellPhoneDB leads some and sits mid-table
in others, CellChat the reverse — which is the argument for a consensus and for running two.
**`cellchat` is also the R-bridge pilot.** It is worth doing for that reason alone: SCENIC+,
Nichenet, tradeSeq, miloR and hdWGCNA all sit behind the same bridge.
**Cannot show** that any interaction occurs. These are co-expression of a ligand and a receptor in
two populations, with **no spatial information** — the cells may never touch. On dissociated
tissue that caveat is the whole story, and it belongs beside every edge.

---

## Tier 2 — worth having, once Tier 1 is real

| kernel | answers | needs | note |
|---|---|---|---|
| `programs` | gene programs / co-expression modules that cut across cell types | — | cNMF, or Hotspot. Finds activity programs a discrete label cannot express — the strongest tier-2 candidate because it needs nothing extra |
| `hdwgcna` | co-expression modules with a hub-gene structure | R | very widely used in the tissue literature; behind the R bridge |
| `signatures` | scoring published gene sets per cell | a gene set | thin wrapper, but the right place to enforce "a score is not a measurement" |
| `stemness` | differentiation potential without a root cell | — | CytoTRACE 2. A useful independent check on a pseudotime's direction |
| `tradeseq` | genes changing *along* a trajectory | `pseudotime`, R | the natural consumer of tier-1 #1 |
| `nichenet` | ligand → downstream *target* response, not just LR pairs | R, priors | answers the question CCC methods cannot: did the receiver respond |
| `cellchat_multi` | how communication differs across conditions | `cellchat` + design | usually the actual biological question |
| `tensor_cell2cell` | context-aware CCC across many samples via tensor decomposition | `liana` | designed for exactly a multi-sample design |
| `augur` | which cell type responds *most* to the perturbation | design | prioritisation, a good complement to `de` |
| `dialogue` | multicellular programs — coordinated states across cell types | many samples | answers a question nothing else here does |

---

## Tier 3 — needs a modality this pipeline does not produce

These are **refusals with a fix**, not omissions. Each should eventually exist as a declared kernel
that refuses cleanly and names what would be required, exactly as `velocity` does when the
unspliced layer is missing.

| kernel | needs | why it is still worth declaring |
|---|---|---|
| `scenic_plus` | paired scATAC (multiome) | the honest upgrade path from `scenic` |
| `celloracle` | ATAC or a base GRN | in-silico TF knockout — the only perturbation-flavoured tool that runs on unperturbed data |
| `spatial` (squidpy) | coordinates | makes CCC claims testable instead of suggestive |
| `cnv` (inferCNV / numbat) | a normal reference | tumour work only |
| `tcr` / `bcr` (scirpy) | VDJ libraries | immunology only |
| `multiome` (MOFA+, MultiVI) | a second modality | |
| `perturbation` (CPA, scGen) | a perturbation design | pertpy covers this if the design ever exists |
| `metabolic` (Compass, scFEA) | — | listed low: expensive, and validation on nuclei is thin |
| `splicing` (BRIE2, MARVEL) | reads or a BAM | relevant to snRNA specifically, given intronic content |

---

## Evaluated and declined, for now

Recording these matters as much as the roadmap. A name that keeps coming up and has already been
assessed should not be re-argued from scratch.

**Foundation models — scGPT, Geneformer, UCE — for zero-shot embedding or annotation.**
Declined on evidence, not on principle.
[Genome Biology 2025](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-025-03574-x)
evaluated both zero-shot and found they are outperformed by highly variable genes with scVI or
Harmony on cell-type separation and batch integration, with Geneformer consistently lowest across
integration metrics, sometimes performing worse on datasets inside its own pretraining set.
scIntegrate already ships scVI and Harmony and benchmarks them. Adding a slower method that scores
below what is already there, on the same metrics, is not an upgrade.
**Revisit when** there is independent evidence of a *fine-tuned* model beating scVI on a task this
pipeline actually performs. The kernel design is not the obstacle — a `foundation` kernel would
slot in unchanged.

**Monocle3 / Slingshot** as separate trajectory kernels. CellRank 2 spans the same ground, is
Python, and is scverse-native. Adding a second and third trajectory tool multiplies environments
without adding a question.

**Seurat as an integration or clustering kernel.** scIntegrate owns integration. A kernel that
re-does an earlier stage's job inside a later stage is how a pipeline stops being reproducible from
two command lines.

**WGCNA (the original).** Superseded by hdWGCNA for single-cell, which is already listed.

---

## What has to be built before Tier 1 finishes

Three pieces of harness, each blocking several kernels:

1. **The R bridge.** `cellchat` is the pilot; `tradeseq`, `nichenet`, `hdwgcna`, `miloR` and
   `scenic_plus` follow. The contract already allows `run.R` and `manifest.py` is stdlib-only so an
   R shim can read it — what is missing is a lock that builds R reproducibly and a selftest that
   proves it.
2. **A design table contract.** `abundance`, `de`, `augur` and `cellchat_multi` all need one, and
   all need the same guard against a factor confounded with batch. Write it once.
3. **Reference data handling at scale.** `fetch` exists; cisTarget databases are the first
   reference big enough to test whether it is real.

---

## How this list will go wrong

Stated in advance so it can be checked later.

- **Tier 2 will grow faster than Tier 1 finishes.** The gate is there to slow that down. A kernel
  that runs but whose `cannot_show` was never written is worse than no kernel, because its output
  looks exactly as authoritative as one that was thought about.
- **The pairs will drift into single defaults.** If `scenic` is slow to install, people will run
  `decoupler` alone and report it as regulon activity. The report must name the missing half of a
  pair as an absence, not leave it silent.
- **The refusals are the product.** Most datasets reaching this tool will not have spliced counts,
  ATAC, spatial coordinates or a design table. A harness whose most common output is a clear,
  correct refusal naming the fix is doing its job — and that is the part most likely to be quietly
  removed as "unhelpful".
