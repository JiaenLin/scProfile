# Upstream: LIANA+

**What the tool's own documentation says, recorded so the wrapping can be checked against it
rather than against memory.** Read before changing `run.py`. Every claim below is sourced; where
this file and the installed package disagree, **the installed package is right** and this file is
stale — `selftest.py` asserts the signature it depends on.

- Docs: <https://liana-py.readthedocs.io/en/latest/>
- API: [`rank_aggregate.__call__`](https://liana-py.readthedocs.io/en/latest/generated/liana.method.rank_aggregate.__call__.html)
- Workflow: [Steady-state LR inference](https://liana-py.readthedocs.io/en/latest/notebooks/basic_usage.html)
- Resources & orthology: [Prior Knowledge](https://liana-py.readthedocs.io/en/latest/notebooks/prior_knowledge.html)
- Paper: Dimitrov et al., *Nat Cell Biol* 2024 — LIANA+
- Licence: GPL-3.0

---

## The signature, as documented

```python
rank_aggregate.__call__(
    groupby,                    # REQUIRED — the cell-identity column
    resource_name='consensus',
    expr_prop=0.1,
    min_cells=5,
    groupby_pairs=None,
    base=e,
    aggregate_method='rra',
    consensus_opts=None,
    return_all_lrs=False,
    key_added='liana_res',
    use_raw=True,
    layer=None,
    de_method='t-test',
    n_perms=1000,
    seed=1337,
    n_jobs=1,
    resource=None, interactions=None,
    mdata_kwargs=None, spatial_key=None, spatial_kwargs=None,
    inplace=True, verbose=False,
)
```

Writes `adata.uns['liana_res']` when `inplace=True`; returns a DataFrame when `inplace=False`.

The consensus aggregates **CellPhoneDB, Connectome, log2FC, NATMI and SingleCellSignalR** by
Robust Rank Aggregation.

---

## The four defaults that are wrong for us, and why

### 1. `resource_name='consensus'` is HUMAN

> *"LIANA uses human gene symbols by default; other species require homology conversion."*

**This is the failure that does not announce itself.** A human resource run against mouse symbols
does not error — it matches almost nothing, or matches the handful of symbols that coincide
between species, and returns a small, plausible table of interactions.

LIANA ships **`'mouseconsensus'`** among its 17 resources (`li.rs.show_resources()`), and for other
species provides `li.rs.get_hcop_orthologs(target_organism=...)` over the HCOP database — 19
species — with `li.rs.translate_resource()` to convert a resource. The docs use
`min_evidence=3` and warn about one-to-many mappings: *"we will be harsher and only keep mappings
that don't map to more than 1 mouse gene."*

**The plugin must therefore pick the resource from the detected organism and refuse when the
organism is unknown.** An unknown organism is exactly the case where the default silently applies
a human resource.

### 2. `use_raw=True` prefers `.raw`

LIANA expects **log1p-transformed** values and looks in `.raw` first. An object whose `.raw` holds
something else — or has none — gets whatever is there, silently.

**The plugin must pass `use_raw=False` and name the layer explicitly**, resolved through the key
map, and state in its caveats which values were used.

### 3. `n_jobs=1`

Permutation testing at `n_perms=1000` is the cost of the run and it is embarrassingly parallel.
Leaving this at 1 is under-use, not caution. **The plugin honours the scheduler's core count.**

### 4. `n_perms=1000` bounds the p-value

The smallest achievable p-value is `1/n_perms`. Tutorials use 100 for speed; that makes 0.01 the
floor and is a different claim. **If it is lowered, the run says so and the report states the
floor.**

---

## What is dropped, and must be reported as a named absence

| default | drops |
|---|---|
| `min_cells=5` | **an entire cell identity** with fewer than 5 cells — it does not appear in the output at all |
| `expr_prop=0.1` | an interaction where either partner is expressed in <10% of cells in the relevant identity |
| `return_all_lrs=False` | everything filtered — only the surviving pairs come back |

A cell type absent from the results because it had 4 cells looks identical to one that had no
interactions. **The plugin records which identities were dropped and why.**

---

## Output columns

| column | is |
|---|---|
| `magnitude_rank` | aggregated rank of interaction **strength** |
| `specificity_rank` | aggregated rank of **cell-type specificity** |
| `lr_means` | mean ligand-receptor expression — the magnitude score |
| `cellphone_pvals` | permutation p-value — the specificity score |
| `ligand_props` / `receptor_props` | proportion of cells expressing each partner |
| `ligand_complex` / `receptor_complex` | the complex, where heteromeric |

**Complexes use the MINIMUM expression across subunits**, which the docs note may differ from the
original implementations.

---

## The full power, and what we are not using yet

LIANA+ is a framework, not one function. Beyond steady-state LR inference it provides:

| | |
|---|---|
| **Tensor-cell2cell** | context factorisation across many samples — communication *patterns*, not one contact map |
| **MOFA+ intercellular** | multi-sample factor analysis over CCC |
| **pyCrossTalkeR** | differential communication networks between conditions |
| **spatial** | bivariate metrics, MISTy, local scores — where coordinates exist |
| **metabolite-mediated** | multi-modal CCC |

**A single contact map over a pooled cohort answers the wrong question for a designed experiment.**
The question is how communication *differs between conditions*, and Tensor-cell2cell is what LIANA
provides for it. The plugin computes per-sample results in the shape those consumers need
(`li.multi.df_to_lr`), so the factorisation is the next increment rather than a rewrite.

---

## What a LIANA result cannot establish

Carried into `cannot_show`:

- **No interaction is observed.** These are co-expression of a ligand and a receptor in two
  populations. There is no spatial information here, and on dissociated tissue the cells may never
  have touched.
- **A rank is within this dataset.** `magnitude_rank` orders interactions here; it is not a
  strength comparable to another dataset's.
- **The resource decides the answer.** Benchmarks rank the underlying methods inconsistently — no
  single resource or method is best across them, which is why the consensus exists and why running
  a second tool is worth more than tuning this one.
- **Nuclei carry less of this signal.** Ligand and receptor transcripts are partly cytoplasmic, so
  a single-nucleus preparation reports fewer of them, and a low interaction count is as consistent
  with the assay as with the biology.
