# kernel: enrichment

> Written BEFORE the code. If a line here changes while the code is being written, that is a
> finding about the design, not an edit to tidy away - say what changed and why in the PR.

**Process note, honestly recorded rather than hidden**: this file was scaffolded before the
mechanism (`sch dev new` writes it first) but its PROSE was filled in after `run()` was written,
not before - this conversion went inventory/account -> mechanism -> declaration -> this file,
not spec-first. Two lines below changed as a direct result of writing the code rather than
predicting it: "Gene %"/"Tag %" were first believed to be coverage fractions and are positions
(caught by reading gseapy/base.py's own docstring); the strongest hit across populations turned
out to sometimes be a population this plugin never boosted, in its own selftest-shaped probe (see
`cannot_show` in kernels/enrichment.py) - a real property of "rest = every other population
pooled", not a bug.

## The question it answers
Which curated gene sets (pathways, hallmarks, GO terms, ...) describe what makes one population's
own cells distinct from the rest of this same object's cells?

## What it SEES
`lognorm` (the expression this plugin ranks on), `label` (the populations it ranks
population-vs-rest), `organism` (which Enrichr catalogue/server a library name resolves against).
It is NOT design-aware: it is never shown a design table, a sample column or a contrast, and its
ranking is a description of the cohort's own populations against each other, not of an experimental
arm against another.

## What it CANNOT SHOW
See `PLUGIN["cannot_show"]` in kernels/enrichment.py for the full, current list - it is proved
against the code rather than duplicated here as prose that can drift from it. The two most easily
missed: a population's own hit list is not evidence about that population ALONE (a shift confined
to population A can surface as a significant result in population B, because "rest" pools every
other population - demonstrated, not hypothesised, in this plugin's own due-diligence probe); and
`Gene %`/`Tag %` in gseapy's own result table are POSITIONS along the ranked list, not a coverage
fraction of a gene set's membership - this plugin computes its own coverage number (F1) rather
than reading either column as one.

## What would make it wrong
- The population-vs-rest mask including a population's own cells on the "rest" side, or including
  an annotator-sentinel cell on either side (both are structural bugs this plugin's own smoke
  test checks by construction, not something a reader of a results table could see).
- A gene-set library resolved for the wrong organism returning a small, plausible-looking table
  silently (gseapy does not raise for this) - the reason `organism` is a required injection and
  F1 exists at all.
- A `permutation_num` too small for the number of populations x gene sets tested, producing p/FDR
  values that floor at `1/permutation_num` and read as "equally significant" when they are really
  "equally coarse" (see `upstream.gotchas`).

## state_version
1 - the numbers are: per (population, gene set) NES / NOM p-val / FDR q-val / leading-edge genes
from gseapy's `prerank`, run once per real population (>= min_cells_per_population) against that
population's own signal-to-noise ranking (this population's cells vs every other real
population's cells, on the detected-gene universe) and a gene-set library resolved once via
gseapy's `get_library`. Bump this if the ranking metric, the rest-definition, the gene-detection
filter, or the resolution process changes in a way that would change the numbers for the same
input object and the same config.

## How it is proved
- [x] `sch dev check --point kernel --name enrichment` - contract (0 failing, 8 warnings),
      declaration blocked on the unmeasured `memory_gb_per_100k` (no run exists yet - see the
      conversion report), fixture shapes/leak/baseline blocked on this host's own missing
      anndata/word-list, not on this plugin
- [ ] a pre-declared reproduction against a reference run - none exists yet; this plugin has
      never been run
- [x] `tests/test_kernel_enrichment.py` - the claim below, which a generic contract check cannot
      see: the ranking math itself recovers a real, planted difference and does not leak a
      population's own cells into its "rest"
