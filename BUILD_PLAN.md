# Build plan — the profiling increment

The next two plugins, in the order a real cohort needs them, and **how each can fail.**

Same shape as the three tools before this one: the tool is built here, tested on a real dataset
elsewhere, and nothing about that dataset enters this repository. Three rules govern the whole
plan and are not negotiable.

**No in-house scripts.** Anything that runs is a plugin in this repository, invoked by its own CLI.
A one-off script written beside a dataset to make an analysis work is a finding about the plugin,
not a solution — the 46 retired scripts behind two earlier stages are what that path looks like at
the end.

**No overfitting.** No column name, organism, assay, design shape or cell type from any particular
dataset. Every plugin is written against the key map and validated on the synthetic fixture
**before** it meets real data.

**No leaking.** No dataset's sample names, counts, cell types or findings in this repository — in
code, comments, docs, tests or example output. `tests/test_contract.py` greps for it; extend the
pattern when a new one becomes conceivable.

---

## Ordering, and why it differs from the roadmap

[`ROADMAP.md`](ROADMAP.md) orders tier 1 as `pseudotime → abundance → de → …`, on the grounds that
`pseudotime` depends on `cellcycle`. That dependency is real but it is not a *precedence*:
`abundance` and `de` depend on neither.

The first real test cohort asks a compositional question and a differential-expression one. So the
increment is:

```
  A  abundance      does a population's share shift across the design
  B  de             which genes change, per cell type, across the design
  C  decoupler      TF and pathway activity from curated priors   (cheap, no reference download)
```

`pseudotime` moves after them. Nothing is lost — it gains a `cellcycle` that has by then been run
on real data rather than a fixture.

---

## Phase A — `abundance`

**Answers** whether a population's *share* shifts across the design.

**Wraps** [pertpy](https://pertpy.readthedocs.io), which carries scCODA 2.0, tascCODA and Milo in
one scverse-native package — one dependency rather than three, one of them R.

**Ships two methods by construction**, because they answer different questions and disagree
informatively:

| | works on | catches |
|---|---|---|
| **scCODA** | per-label counts | a shift in a labelled population, handling the sum-to-one constraint |
| **Milo** | kNN neighbourhoods | a shift *inside* a label that per-label testing cannot see |

### The guard is the point of this plugin

`abundance` is the first plugin whose headline output an upstream constraint can forbid. It **must**
read `uns['<integrator>']['constraint_on_use']` and act on it, and the two methods are affected
differently:

- **scCODA uses no embedding.** It counts cells per label per sample. A constraint on an embedding
  does not reach it.
- **Milo builds neighbourhoods on an embedding.** If that embedding is a corrected one, and the
  constraint says the correction removed the contrast being tested, then Milo is testing a factor
  the embedding no longer carries — and it will return clean, small p-values for it.

So the guard must refuse Milo on a corrected embedding whose constraint names the tested factor,
and say which uncorrected embedding to use instead. `--allow abundance` overrides and is logged.

**A second refusal, structural rather than interpretive:** a design with fewer than three samples
per group. Compositional and pseudobulk tests on n=2 are arithmetic, not evidence. `unmet()`
refuses; there is no threshold to lower.

**`cannot_show`** — at minimum: composition is relative by construction, so one population rising
makes every other fall and the direction of causation is not recoverable; absolute cell numbers are
not measured; and a shift measured after a batch correction cannot be separated from what the
correction removed.

**Evaluation.**

| | pass |
|---|---|
| fixture, planted shift | a shift injected into the synthetic fixture is recovered by both methods |
| fixture, no shift | neither method reports one — the false-positive check, run first |
| guard | Milo refuses on a constrained embedding, and names the uncorrected one |
| guard | refuses n<3 per group, by count and not by option |
| declaration | output matches `produces`; `sees: [design]` declared |
| real cohort | runs, and its refusals are correct rather than convenient |

**Falsifier.** If the guard cannot read a constraint written by an upstream tool, the constraint
was decorative and the whole chain of *record it now, act on it later* has not worked once.

---

## Phase B — `de`

**Answers** which genes change, per cell type, across the design.

**Wraps** pyDESeq2 on pseudobulk. Per-cell tests are offered as an explicit alternative, never a
default.

### Pseudobulk is the default because the alternative inflates

A per-cell test treats cells as independent samples. They are not — cells from one animal are one
animal, and the effective sample size is the number of animals. Testing per cell inflates
significance by roughly the number of cells per animal, which on a real cohort is four orders of
magnitude.

**Refuses** a design with fewer than three samples per group, for the same reason `abundance` does.
Where a design has an interaction term, the plugin fits it and reports **which coefficient absorbs
a confounded factor** rather than reporting all coefficients as equals.

**`cannot_show`** — at minimum: a gene absent from the object was not tested and its absence is
not evidence; pseudobulk cannot see a change confined to a subpopulation of a labelled type; and a
coefficient in a confounded design is not interpretable in isolation.

**Evaluation.**

| | pass |
|---|---|
| fixture, planted DE | genes with an injected effect are recovered; the null is calibrated |
| n<3 | refuses, with the count |
| per-cell alternative | reports both counts when both were run, and names which is which |
| interaction | fits it, and states what each coefficient absorbs |

**Falsifier.** If pseudobulk on the first real cohort produces almost nothing because the design is
too small, that is a result about the design and must be reported as one — not tuned around by
falling back to per-cell testing.

---

## Phase C — `decoupler`

Cheap and worth having early: pure Python, no reference download, curated priors (CollecTRI,
PROGENy, MSigDB). It is also the counterweight to `scenic` later, and having it first means the
pair is not introduced by its expensive half.

---

## Written for the harness, mounted in scProfile

The [single-cell-harness](https://github.com/JiaenLin/single-cell-harness) plugin format is where
these end up. Its fields are declared **now**, in `kernel.yml`, even though scProfile does not yet
read them — they are additive, they cost nothing, and adding them later means revisiting every
plugin:

```yaml
layer: stack          # neither of these produces new numbers from nothing
reversible: true
sees: [design]        # both are given the design table; declared, not omitted
profile: single-cell/1.0
```

`sees` matters most. Both plugins are given the design table, and any comparison that ranks them
against something that was not needs to know.

---

## What stops this plan

- **`abundance`'s guard cannot read the upstream constraint.** Phase A's falsifier. Stop and fix
  the contract rather than shipping a plugin that ignores it.
- **The first real cohort is too small for either test.** Report it as a finding about the design.
  A tool that returns a result on n=2 because returning nothing felt unhelpful is worse than one
  that refuses.
- **A plugin needs a dataset-specific fix.** Then it is overfitted and the fix belongs in the key
  map or the profile, not in the plugin.
- **pertpy cannot be pinned reproducibly.** Measure this first, before writing any plugin code —
  a dry-run resolve against a current stack, exactly as was done for scvelo, where the answer
  turned out to be that it needed its own environment and a hard pin.

---

## Order of work

1. **Measure** pertpy and pyDESeq2 against a current stack. A resolve that changes packages is the
   answer to whether they need their own environments.
2. `abundance`: manifest, lock, selftest, guard, `run.py`.
3. Extend the fixture with a **planted compositional shift** and a **null** — the false-positive
   case first.
4. `sch`-side: nothing. The host already merges tables and renders per-plugin pages.
5. `de`, same shape.
6. Run both on a real cohort. **Its refusals are the result**, if that is what it produces.
7. `decoupler`.

---

## The tool family is additive. Nothing leaves it.

**A plugin is never removed from the plan because it is expensive or blocked.** It is sequenced by
what blocks it, and what blocks it is written down. A tool dropped from a build order with no
reason recorded is indistinguishable, later, from one nobody thought of — and this plan lost three
that way once before this section existed.

Every declared plugin appears below with its blocker and its cost. New tools join by the same
route: a manifest declaring `needs` / `produces` / `cannot_show`, then `UPSTREAM.md`, then the
build. The manifest comes first precisely so a tool can be evaluated against a real dataset with
`scprofile plan` before anyone commits to writing it.

| plugin | blocked on | cost |
|---|---|---|
| `velocity` | nothing — inputs found beside the object | S |
| `de` | nothing — its dependency is already installed | S |
| `liana` | ~~its own environment~~ — built, selftest passes | M |
| `cellchat` | ~~**the R bridge**~~ — built, selftest passes | M |
| `abundance` | its own environment | M |
| `decoupler` | a dependency resolve | S |
| `pseudotime` | ~~its own environment~~ — built, selftest passes; consumes velocity | M |
| `scenic` | ~~**a multi-GB reference fetch**, untested at that scale~~ — built, selftest passes; mouse references fetched and verified | L |

Four of those blockers are cleared. **Every one of the five remaining blockers is now a `run.py`
or `run.R`, not an environment.** That is a different kind of work and it is what `status:
planned` still means for each of them.

### Two of these are infrastructure wearing a plugin's name

**`cellchat` is the R bridge, and the bridge is now built.** The contract already allowed `run.R`
and `manifest.py` is stdlib-only so an R shim can read it; what was missing was a lock that builds
R reproducibly and a selftest that proves it. Both exist.

The lock format had to grow for it, because a conda environment YAML expresses conda packages and
pip packages and nothing else, while CellChat is distributed only from GitHub and needs an NMF
newer than any conda channel carries. `lock.yml` now takes an `r:` section of exact pins — a git
commit or a CRAN version — applied in one process with `dependencies = FALSE` so nothing in the
environment is chosen at install time. See `docs/EXECUTION.md` §9 for what was rejected and why,
and for the three things the format still cannot express.

**What the selftest caught that a dependency reading could not.** `identifyOverExpressedGenes`
defaults to `do.fast = TRUE`, which hard-requires `presto` — a package CellChat lists under
*Suggests*, and which is not on CRAN. It does not fall back; it stops. A lock built from Depends +
Imports + LinkingTo, the disciplined reading of a DESCRIPTION, was not enough, and only running
the real call showed it.

What is still missing for `cellchat` is `run.R`. Building the bridge unlocks every R tool behind
it — `tradeseq`, `nichenet`, `hdWGCNA` — so its cost was amortised across four, not one.

It is also **half of a pair**. Running one communication method alone contradicts the reason the
pair exists: agreement between two is evidence, disagreement is a finding about the databases as
much as about the cells. Shipping `liana` without it is shipping half the argument.

**`scenic` is the reference-fetch test.** `refs.py` exists and has never handled anything at the
scale cisTarget databases arrive in. Doing it last is a sequencing decision about risk, not a
judgement about the method — and it is the other half of the `decoupler` pair, where a network
inferred from the data is checked against curated priors.

### What "sequenced later" must never mean

- absent from the plan
- absent from `scprofile plan` output against a real dataset
- absent from the report, which names every plugin that did not run and why

A plugin that is declared but unbuilt still answers *what would you need from me* — which is worth
having before it is written, and is why the declarations exist ahead of the implementations.
