# Template — cell–cell communication

For a plugin that infers ligand–receptor signalling between populations and compares it between
arms. CellChat is the worked case; the shape holds for any method that scores population pairs
from co-expression.

> **Grounded in published practice.** The structure, the claims and every caveat below were taken
> from method and results text in the literature, retrieved through the digital-mentors corpora,
> and each is cited by DOI. Where a paper is cited for a caveat, that paper attached the caveat
> to its own result — these are not cautions invented here.

## What the method infers

**Co-expression of a ligand and its receptor in two populations, scored and permuted.** It does
not observe communication; it scores the *possibility* of it from expression. Say this once, in
the first sentence that reports a network, and the rest of the section can speak plainly.

The benchmarking literature states the goal as inferring "which cell types are communicating
within a tissue to mediate tissue function" (doi:10.21203/rs.3.rs-4181617/v1), and the assumptions
common to all such algorithms begin with "the co-occurrence of ligand" and receptor expression
(doi:10.1101/2021.07.11.451750). A section that reports inferred edges as observed signalling has
skipped the only sentence that distinguishes them.

## What a result of this kind supports

- **Which population pairs carry inferred signal, and how much**, within one arm.
- **Which programmes carry it** — the pathway or ligand–receptor level, which is the axis that
  connects a result to known biology.
- **Whether a population acts as a sender, a receiver, or both**, and how that changes.
- **The direction and size of a difference between two arms**, with the method's own test.
- **Which elements are present in one arm and not the other** — a presence, which is a result.

## What it does NOT support, and why

- **That the communication occurred.** Inference is from co-expression; there is no measurement of
  a signal being sent or received.
- **Abundance against per-cell intensity.** A population that is more abundant contributes more to
  a total with no per-cell change, and the method does not separate the two. Say so rather than
  implying either.
- **Causality or ordering.** A differential network says two arms differ, not that one signal
  drove another.
- **That an absent element was tested.** Elements below a minimum-cell floor are dropped before
  scoring; absence there is a threshold, not a biological zero.

## The order to write in

1. **What was inferred, and separately in what.** Networks are fitted per arm and then compared.
2. **What was excluded and why** — populations below the cell floor, and populations one arm has
   and the other does not. Published practice is explicit about this: one snRNA study states
   "Cell types or subtypes with less than 10 nuclei in either disease group were excluded"
   (doi:10.1016/j.celrep.2023.112086). Name what went, do not describe the category.
3. **How much network each arm carries**, before any difference. A ratio between two arms is
   uninterpretable without the totals it is a ratio of.
4. **The comparison, per contrast, in the design's order** — conditional effects before marginal
   ones, since a marginal effect averages over strata.
5. **Which programmes carry the difference**, with the method's own between-arm test named.
6. **A focus.** Published sections narrow: the same study "compared the signaling networks in
   [one condition] to the signaling networks in [the other], focused on endothelial subtypes"
   (doi:10.1016/j.celrep.2023.112086). A section that reports every pathway equally reports none.
7. **The caveats**, once each, where they belong.

## Caveats to attach, with citations

**Nuclear transcriptome.** Where the assay is single-nucleus: "The snRNA-seq does not reflect the
total mRNA present in a cell, as it excludes RNA outside of the nucleus. In addition, snRNA-seq is
designed to detect poly-adenylated transcripts and therefore does not fully explore the presence
of RNA molecules that are processed by alternative mechanisms" (doi:10.26508/lsa.202101048). A
ligand–receptor method reads exactly the transcripts this excludes, so the caveat is not generic —
it bears directly on what was scored. Attach it once, in limitations.

**Dissociation changes what is measured.** Tissue that is "difficult to dissociate without
damaging constituent cells or inducing acute ischemia" thereby influences "cellular mRNA
composition" (doi:10.26508/lsa.202101048). Where recovery differs between arms, the composition
difference that follows is technical before it is biological.

**The cell is not the replicate.** Pooling cells within an arm and inferring from the pool treats
cells as replicates. The standing guidance is to "aggregate to the donor level or use random
effects for donor and experiment", because otherwise "p-values reflect cell count rather than
biological replication"; treating nuclei as independent replicates "inflates significance by
orders of magnitude" (Ellinor corpus; see also doi:10.1038/s41576-023-00586-w). Communication
methods pool by construction, so state it and show the per-sample spread beside the arm.

**Composition confounds the comparison.** Shifts in cell-type proportion "are known confounders
... often addressed through the use of covariates when the cell type proportions are known"
(doi:10.1101/2025.09.07.674751), and proportions themselves are hard to measure, with "significantly
different results based on species, location within the [tissue], method of study"
(doi:10.1080/15592294.2025.2524411). Report the composition of each arm once, near the top.

**Excluding a population is not neutral.** "If cell types with expected proportion changes are
excluded from the study, their effects may be misattributed to other, highly correlated cell
types" (doi:10.17615/m0ws-an52). Where a comparison is restricted to populations both arms share,
say which were dropped and that their signal is not redistributed but absent.

**Where proportions are analysed directly**, the compositional constraint is real: transformations
such as centred log-ratio "convert proportions to an unconstrained space while preserving their
relationships" (doi:10.17615/m0ws-an52).

## Sentence patterns

Filled from the run's own tables. Never copy the prose; copy the shape.

**The framing sentence, once.**
> Ligand–receptor signalling was inferred separately within each arm from co-expression of
> {DATABASE}'s ligand–receptor pairs, and compared between arms. An edge is an inferred
> possibility of signalling, not an observation of it.

**Totals before differences.**
> {ARM_A} carries a total interaction strength of {T_A} over {N_A} populations, against {T_B} in
> {ARM_B}; the two networks were fitted on {C_A} and {C_B} cells respectively.

**A contrast, with the method's own test.**
> {AGAINST} carries {RATIO}x the interaction strength of {REFERENCE} ({T1} against {T2}), and
> {N_SIG} of {N_TESTED} programmes differ between the arms by {TEST_NAME}.

**What carries it.**
> The difference is led by {ELEMENTS}, each higher in {ARM} ({P_VALUES}).

**Presence, stated as presence.**
> {ELEMENTS} are detected in {ARM_A} and not in {ARM_B}. This is a difference in presence, not in
> magnitude: the element was not weaker in {ARM_B}, it was absent.

**An interpretation, marked as one.**
> {OBSERVATION}. This is consistent with {MECHANISM}, though the present data do not test it.

**A hypothesis, marked as one.**
> One explanation for {OBSERVATION} is {HYPOTHESIS}; it predicts {CONSEQUENCE}, which {ASSAY}
> would test.

**A sensitivity result, which strengthens rather than hedges.**
> The difference holds on a per-cell scale ({RATIO_PER_CELL}x) and in {STRATUM}, where {ARM} was
> fitted on fewer cells than {OTHER} — so it is not a consequence of arm size.
