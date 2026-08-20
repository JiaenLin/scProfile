# Upstream: scVelo

**What the tool's own documentation and installed signatures say.** Read before changing `run.py`.
Where this file and the installed package disagree, **the package is right**; `selftest.py`
asserts the signature the plugin depends on.

- Docs: <https://scvelo.readthedocs.io/> · Paper: Bergen et al., *Nat Biotechnol* 2020
- Licence: BSD-3-Clause · Version wrapped: **0.3.4** (pinned in `lock.yml`)

---

## The API change that broke the first run, and how it was caught

`scv.pp.filter_and_normalize` in **0.3.4** is:

```python
filter_and_normalize(data, min_counts=None, min_counts_u=None, min_cells=None,
                     min_cells_u=None, min_shared_counts=None, min_shared_cells=None,
                     retain_genes=None, layers_normalize=None, copy=False, **kwargs)
```

**There is no `n_top_genes`.** Earlier versions had it; 0.3.x removed gene selection and the log
transform from this function in favour of scanpy. `**kwargs` is forwarded to `normalize_per_cell`,
which rejects the argument — so passing it raises inside a function whose name gives no hint why.

It failed on the first cluster run, in eight seconds, because `selftest.py` runs the **whole path**
on a synthetic fixture rather than importing the package. An import-only check would have passed
and the failure would have arrived an hour into a real cohort.

The plugin therefore does gene selection with `sc.pp.highly_variable_genes` explicitly, and says
so in its caveats rather than implying scvelo chose the genes.

## Signatures the plugin depends on

```python
scv.tl.velocity(data, vkey='velocity', mode='stochastic', ...)
scv.tl.velocity_graph(data, vkey='velocity', xkey='Ms', n_jobs=None, ...)
scv.tl.velocity_confidence(data, vkey='velocity', copy=False)
scv.tl.velocity_pseudotime(adata, vkey='velocity', root_key=None, n_dcs=10,
                           use_velocity_graph=True, ...)
scv.tl.recover_dynamics(data, var_names='velocity_genes', n_top_genes=None, max_iter=10, ...)
scv.tl.latent_time(data, vkey='velocity', min_likelihood=0.1, min_confidence=0.75, ...)
```

## Defaults, and the ones the plugin changes

| default | plugin | why |
|---|---|---|
| `mode='stochastic'` | kept | what the published single-nucleus work used. `dynamical` is minutes-to-hours and is offered, not assumed |
| `n_jobs=None` (serial) | **scheduler's core count** | `velocity_graph` is the cost of the run and is parallel. Leaving it serial is under-use |
| `arrow_size` (plotting) | **0.7 / scaled** | it is in POINTS and does not scale with the figure, so a panel built for an 85 mm column gets arrowheads meant for a screen |
| `basis` | **an integrated embedding if present** | arrows drawn on a different manifold from the annotation cannot be read against it |

## What is not used yet, and is therefore under-use

| | |
|---|---|
| `mode='dynamical'` | per-gene kinetic rates and `latent_time`. Exposed as a parameter, not the default, on cost |
| `scv.tl.differential_kinetic_test` | whether a gene's kinetics **differ between populations** — closer to a designed experiment's question than one field is |
| `scv.tl.velocity_clusters` | clustering on velocity rather than expression |
| `scv.tl.paga` velocity mode | used for the transitions table; the directed graph itself is not drawn |

## What the tool's own literature says it cannot establish

Carried into `cannot_show`:

- velocity is a **direction**, not a rate; arrow length is not speed and is not comparable between
  datasets;
- **quantification decides the answer** — how intronic reads were counted, and whether the
  reference included introns, changes library size, cell-type assignment and therefore velocity;
- snRNA intronic reads carry a **gene-length bias** in both exonic and intronic counts;
- unspliced mRNA is **read as** a transitional state and need not be — a stable population can hold
  an unspliced reservoir;
- the single-nucleus validation is **directional** (r 0.94–0.99 nucleus vs cell on matched
  populations, *Sci Rep* 2024); that work projected vectors and measured cell speed and did **not**
  derive a pseudotime from them, so `velocity_pseudotime` rests on more.
