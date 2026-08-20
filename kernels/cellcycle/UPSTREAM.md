# Upstream: scanpy `score_genes_cell_cycle`, and the Tirosh regulon

**What the tool's own documentation and installed signatures say.**

- Docs: <https://scanpy.readthedocs.io/> · Licence: BSD-3-Clause
- Gene sets: Tirosh et al., *Science* 2016 — the de-facto standard S and G2M regulons
- Method: Tirosh et al., *Nature* 2016 (`AddModuleScore` / `score_genes`)

---

## Signatures, measured from the install

```python
sc.tl.score_genes_cell_cycle(adata, *, s_genes, g2m_genes, copy=False, **kwargs)

sc.tl.score_genes(adata, gene_list, *, ctrl_as_ref=True, ctrl_size=50, gene_pool=None,
                  n_bins=25, score_name='score', random_state=0, copy=False,
                  use_raw=None, layer=None)
```

`score_genes_cell_cycle` forwards `**kwargs` to `score_genes`. Everything below therefore applies.

## `use_raw=None` means USE `.raw` IF PRESENT

This is the same class of defect as LIANA's human-by-default resource: it does not error, it
scores different numbers.

`use_raw=None` resolves to `.raw` when the object has one and `.X` when it does not. So the same
plugin, on two objects that differ only in whether an upstream step left `.raw` behind, scores
**different values** — and nothing in the output says which was used. An object whose `.raw` holds
counts rather than log-normalised values gets a score computed on counts.

**The plugin must pass `use_raw=False` and name the layer**, and state in its caveats which values
were scored.

## What the score actually is

`score_genes` is **not** the mean expression of the panel. It is the mean of the panel **minus the
mean of a control set drawn from matched expression bins** — `ctrl_size=50` genes per bin,
`n_bins=25`.

That subtraction is the whole method. A naive panel mean is dominated by how abundant its genes
happen to be, so a ribosomal signature scores high in every cell and means nothing. The control
set is what makes **zero** a meaningful reference, and it is why `ctrl_size` and `n_bins` are
parameters worth exposing rather than constants worth hiding.

## Defaults, and what the plugin does

| default | plugin | why |
|---|---|---|
| `use_raw=None` | **`False`, layer named** | see above — the silent one |
| `ctrl_size=50`, `n_bins=25` | kept, **recorded** | scanpy's own defaults; changing them changes every score |
| `random_state=0` | kept | the control set is sampled |
| human gene symbols | **matched by casing, and the match count reported** | the panel is human; the plugin tries exact, title-case and upper-case, and REFUSES below 10 matched genes per set — a low score from an unmatched panel looks exactly like a resting population |

## What is not used yet

`gene_pool` — restricting the control universe. Relevant where a gene class should not be eligible
as a control, and unused because no such case has been argued here.

## What it cannot establish

- Phase is **scored from a gene set, not measured.** A cell called G2M is one whose G2M genes are
  relatively high.
- The panels are the standard **human** ones, title-cased for mouse. Not tissue-specific and not
  curated for any dataset.
- On single nuclei the signal is weaker — cell-cycle transcripts are partly cytoplasmic — so a low
  score is as consistent with the assay as with a resting population.
- A cycling population is not a proliferating one. Scoring says which genes are high, not how many
  cells divided.
