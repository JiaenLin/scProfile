"""Regulon activity per cell, from a network inferred from this dataset rather than a prior.

CO-EXPRESSION WITH A MOTIF IS NOT REGULATION. Nothing here observes a perturbation, so no edge
is causal. And the whole method rests on a lookup: GRNBoost2 proposes modules, and cisTarget
PRUNES them against motif rankings. Without the rankings nothing is pruned, every co-expression
module survives, and the regulons returned are raw correlation wearing a regulon's name — a full
result file, and wrong. That is why the reference data is a required capability.
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "summary": "regulon activity per cell, from a network inferred from your own data",
    "when_to_use": "you want a gene regulatory network from this dataset rather than a prior",
    "wraps": {"tool": "pyscenic", "homepage": "https://pyscenic.readthedocs.io",
              "license": "GPL-3.0",
              "cite": "Aibar et al., Nat Methods 2017 (SCENIC); "
                      "Van de Sande et al., Nat Protoc 2020 (pySCENIC)"},
    "upstream": {
        "docs": "https://pyscenic.readthedocs.io",
        # 2026-08-25: re-read against the PINNED version's own source, `0.12.1`, not `master` -
        # `prune2df`'s default differs between the two trees this plugin could have been told
        # about, and reading the wrong one is how a parameter gets documented at a value nothing
        # ever used. Every number below was taken from the 0.12.1 tag and confirmed a second time
        # against `master`, and where the two disagree that is said rather than resolved.
        "read": "2026-08-25",
        "defaults_changed": [
            "grnboost2 is given an explicit seed and a local client. Its default spins up a "
            "dask cluster sized to the machine, which on a shared node is the os.cpu_count() "
            "mistake wearing a scheduler.",
            "The TF list is passed explicitly from the declared reference. Left out, GRNBoost2 "
            "treats every gene as a candidate regulator and the run takes hours longer to "
            "produce a worse network.",
            "THREE PARAMETERS ARE NOW PASSED EXPLICITLY AT THE TOOL'S OWN DEFAULTS RATHER THAN "
            "INHERITED - auc_threshold (0.05), prune_rank_threshold and keep_only_activating "
            "(True). None of the three changes the number this plugin computed before; what "
            "changes is that the run can now SAY what they were. Each decides what the result "
            "MEANS - which fraction of the ranking the AUC integrates over, how deep into the "
            "motif ranking a target may be recovered from, and whether a repressed target may "
            "belong to a regulon at all - and a result that cannot name them cannot be compared "
            "with any other SCENIC result, including a later run of this same plugin.",
            "prune_rank_threshold defaults to 1500, which is `prune2df`'s own default and what "
            "this plugin was silently taking. It is NOT the 5000 of `pyscenic ctx`; see the "
            "gotcha. Left at 1500 deliberately: raising it would silently change every regulon "
            "count already measured with this plugin, and a default changed underneath old "
            "numbers is worse than one that is merely different from someone else's.",
        ],
        "not_used": [
            "The AUCell binarisation step. A threshold per regulon is a decision about what "
            "counts as 'on' and belongs to whoever reads the matrix.",
            "Multi-runs and the consensus regulon set: the right answer for a published network "
            "and a different, much more expensive plugin.",
            "aucell's `normalize=True`, which rescales each regulon's AUC across cells. It makes "
            "two regulons of very different size look comparable, and they are not - the "
            "rescaling hides the size dependence rather than removing it.",
            "aucell's `noweights=True`, which ignores the importance each target carries out of "
            "GRNBoost2. The weights are the only thing distinguishing a regulon from a gene "
            "list, so they are kept.",
        ],
        "gotchas": [
            "GRNBoost2 returns an EMPTY adjacency table rather than failing when arboreto and "
            "the installed dask disagree about the scheduler. Empty is checked for explicitly, "
            "because downstream it reads as 'no regulons found'.",
            "The cisTarget rankings are organism-specific and this plugin refuses an organism it "
            "has no rankings for rather than pruning against the wrong species.",
            "AUC IS A WITHIN-EXPERIMENT QUANTITY. The SCENIC protocol states that AUC values may "
            "only be used to compare a regulon's activity across cells of the SAME experiment "
            "(Van de Sande et al., Nat Protoc 2020), and the regulon set is itself inferred per "
            "fit - so two per-sample fits do not even share a vocabulary. This plugin therefore "
            "runs per sample AND once over the cohort, and each result says which it is.",
            "There is no upstream guidance on the multi-sample case. The SCENIC maintainers' "
            "thread on comparing AUC across sequencing runs is still unanswered "
            "(aertslab/SCENIC discussion #317), and the single-cell best-practices GRN chapter "
            "demonstrates on ONE donor, explicitly 'due to batch integration considerations' "
            "(sc-best-practices.org). Absence of guidance is why the two scopes are declared "
            "here rather than left to whoever runs it.",
            "A COHORT FIT LEARNS THE BATCH. GRNBoost2 has no notion of design: pooled across "
            "samples it will happily encode co-expression driven by batch or chemistry as "
            "regulation. Where the object carries an upstream constraint on use, the cohort fit "
            "reproduces it verbatim rather than refusing - the vocabulary is still correct for "
            "every comparison the constraint does not name.",
            # ---- found 2026-08-25, reading 0.12.1's own source. All four fail SILENTLY. ----
            "ONE PARAMETER, TWO OFFICIAL DEFAULTS, NO ERROR EITHER WAY. `prune2df`'s python "
            "signature declares rank_threshold=1500; the `pyscenic ctx` command-line default for "
            "the same parameter is 5000. Which one a result was computed at depends only on "
            "whether it came from a notebook or from the documented command-line workflow of the "
            "protocol paper, nothing anywhere records it, and the two are not the same analysis "
            "- 5000 recovers targets from more than three times as deep in the motif ranking. "
            "Verified in the 0.12.1 tag this plugin pins and again on master. Exposed as "
            "`prune_rank_threshold` so a run states which it used.",
            "AUC IS AN AREA UNDER A CURVE THAT STOPS AT auc_threshold x n_genes, AND A SHALLOW "
            "CELL RUNS OUT OF DETECTED GENES BEFORE IT GETS THERE. AUCell ranks every gene "
            "within each cell; genes tied at zero are ordered by a random shuffle of the gene "
            "axis, which is what `seed` controls. So for a cell whose detected-gene count is "
            "below the cut-off, part of the recovery curve is integrated over an arbitrary "
            "order, and its AUC is reading library depth rather than regulon activity. There is "
            "no warning: the number comes back in range and looks like every other cell's. "
            "pySCENIC ships `derive_auc_threshold` for exactly this check and nothing calls it "
            "for you. F1_ranking_depth is that check, and it also asks whether the shortfall is "
            "spread evenly across populations - a depth deficit concentrated in one population "
            "turns a technical property into an apparent biological difference.",
            "REPRESSION IS DISCARDED BY DEFAULT AND THE RESULT DOES NOT SAY SO. "
            "`modules_from_adjacencies` splits each module by the sign of the TF-target "
            "correlation (rho_dichotomize=True, rho_threshold=0.03) and then keeps only the "
            "activating half (keep_only_activating=True; the CLI spells the same choice "
            "`--all_modules no`). A TF that represses its targets therefore returns NO REGULON, "
            "which is indistinguishable in every output from a TF that regulates nothing. "
            "Exposed as `keep_only_activating`.",
            "THE CORRELATION THAT DECIDES ACTIVATING FROM REPRESSING USES THE ZEROS. "
            "`rho_mask_dropouts` defaulted to True up to pySCENIC 0.9.16 and to False after it, "
            "to match the R implementation - so the same data through two versions can sort a "
            "target into opposite halves of the split, with no error and no note in either "
            "result. This plugin takes the current default and names it here.",
            "`modules_from_adjacencies` applies its OWN floor of min_genes=20 to the modules it "
            "builds, before anything is pruned. `min_genes_per_regulon` is applied AFTER "
            "pruning, where a regulon holds only the motif-supported subset and is routinely "
            "smaller, so both are live and they are not the same filter - a module of 20 that "
            "loses 15 targets to pruning is a regulon of 5 and this plugin drops it.",
            "GRNBoost2 DOES NOT MODEL SELF-REGULATION (RegVelo, Cell 2026), so a TF that "
            "autoregulates has that edge missing from every network here. Absent, not zero.",
        ],
    },

    "inject": {"required": ["counts", "organism"],
               # `layout` is OPTIONAL and is only ever drawn on. A regulon's activity read
               # against the manifold the rest of the report uses is the panel a reader asks for
               # first; an object without one still gets every other panel, and the page says
               # which is missing rather than drawing on two arbitrary columns of something
               # wider.
               "optional": ["label", "sample", "layout"]},
    "provides": ["activity"],
    # `?` on both: the cell-level block comes from the COHORT fit and the per-cell table from a
    # PER-SAMPLE fit, so each run makes one of them and never both.
    "produces": ["obsm[X_regulon_auc]?", "tables/regulon_auc.csv?", "tables/regulon_targets.csv",
                 # cohort fit only - the aggregate a between-condition test should read
                 "tables/regulon_activity_by_sample.csv?",
                 # `?` because it needs a label column, which is an OPTIONAL injection
                 "tables/regulon_activity_by_label.csv?"],
    "per_unit": "sample",
    # AND ONCE OVER THE WHOLE COHORT, because a regulon set is INFERRED, not fixed. Each fit
    # discovers its own vocabulary, so two units' AUC columns are not the same quantity and a
    # between-condition comparison built from them compares different things. Measured on ten
    # a ten-sample cohort: 37 to 111 regulons per sample, and two samples shared 17% of
    # their transcription factors (Jaccard 0.17).
    #
    # The per-sample fits are KEPT and are not redundant - they are the only independent check on
    # the pooled one, and a regulon recovered in most samples separately is far stronger evidence
    # than one from a single pooled fit that nothing corroborates.
    "also_cohort": {
        "why": "regulon membership is inferred per fit, so per-sample AUC columns are not the "
               "same quantity. One cohort fit yields ONE regulon vocabulary, which is what a "
               "between-condition comparison of regulon activity requires.",
    },

    # REFERENCE DATA, WITH ITS DIGESTS. Recovered from the directory shape rather than
    # re-derived: the vendor publishes no checksums, so each of these came from a completed
    # download (PBS 676356 mouse, 676454 human), was confirmed by `sha256sum` as a second
    # implementation, and was checked for content - Arrow magic at BOTH ends, and 93% of each TF
    # list present as columns of its own ranking. A digest is only ever as good as the download
    # it came from, and re-deriving these would have thrown that away.
    #
    # Source: resources.aertslab.org, the SCENIC authors' own distribution. The cisTarget
    # databases are distributed for research use; the motif collection derives from JASPAR,
    # HOCOMOCO, SwissRegulon and others.
    "references": {
        "mm10_rankings_10kb": {
            "organism": "mouse", "role": "rankings",
            "url": "https://resources.aertslab.org/cistarget/databases/mus_musculus/mm10/"
                   "refseq_r80/mc_v10_clust/gene_based/"
                   "mm10_10kbp_up_10kbp_down_full_tx_v10_clust.genes_vs_motifs.rankings.feather",
            "sha256": "8fc014f1879355a5e94b155f8b55511e3b47842cceed9d3e17235f60afb85ebc",
            "size": 237172098},
        "mm10_motif2tf": {
            "organism": "mouse", "role": "motif2tf",
            "url": "https://resources.aertslab.org/cistarget/motif2tf/"
                   "motifs-v10nr_clust-nr.mgi-m0.001-o0.0.tbl",
            "sha256": "5b64aad9df9804d50c50484c92d5192bdd5d2056cb105bdd343c0af2f94cce83",
            "size": 113107706},
        "mm_tfs": {
            "organism": "mouse", "role": "tfs",
            "url": "https://resources.aertslab.org/cistarget/tf_lists/allTFs_mm.txt",
            "sha256": "17a95e142147fb7dc063d7b9e84262746b0b64f622793b3cc5df0eddf2f1194c",
            "size": 11726},
        "hg38_rankings_10kb": {
            "organism": "human", "role": "rankings",
            "url": "https://resources.aertslab.org/cistarget/databases/homo_sapiens/hg38/"
                   "refseq_r80/mc_v10_clust/gene_based/"
                   "hg38_10kbp_up_10kbp_down_full_tx_v10_clust.genes_vs_motifs.rankings.feather",
            "sha256": "9c4026a3a8e25fe07cf96749644e2ca028b787410829b30b9932574dc6e78bdb",
            "size": 311298530},
        "hg38_motif2tf": {
            "organism": "human", "role": "motif2tf",
            "url": "https://resources.aertslab.org/cistarget/motif2tf/"
                   "motifs-v10nr_clust-nr.hgnc-m0.001-o0.0.tbl",
            "sha256": "81eb754118e27e854974301b1400fcf519489f8be5249239671fb288cb501c31",
            "size": 98718421},
        # allTFs_hs.txt is a 404: the vendor names this file after the ASSEMBLY, not the species,
        # and nothing would have caught it except fetching it.
        "hs_tfs": {
            "organism": "human", "role": "tfs",
            "url": "https://resources.aertslab.org/cistarget/tf_lists/allTFs_hg38.txt",
            "sha256": "3953034f84112c60d3d8ef15b0e0c8ac5fce0b40d2c7c0824c2945c70cee2523",
            "size": 11690},
    },

    "config": {
        "min_genes_per_regulon": {"type": "int", "default": 10, "min": 1,
                                  "help": "regulons with fewer targets are dropped; a regulon of "
                                          "three genes is a correlation, not a module"},
        "seed": {"type": "int", "default": 0,
                 "help": "GRNBoost2 is stochastic; this is what makes a run reproducible"},
        "cohort_max_cells": {"type": "int", "default": 25000, "min": 0,
                             "help": "the COHORT fit infers its network from at most this many "
                                     "cells, balanced across samples. GRNBoost2 holds the matrix "
                                     "dense and thrashes above ~50k; the estimate stabilises far "
                                     "below that. 0 fits on all cells. Per-sample fits ignore "
                                     "this - they are already small"},
        "min_cells_per_gene": {"type": "int", "default": 3, "min": 0,
                               "help": "a gene detected in fewer cells than this is not offered "
                                       "as a TARGET. It is never removed from the object, never "
                                       "removed as a REGULATOR, and 0 disables the filter. A gene "
                                       "seen in two cells cannot support a regression across "
                                       "thousands, and every one of them costs a full fit"},

        # ---- THREE THAT WERE BEING INHERITED SILENTLY, EACH DECIDING WHAT THE AUC MEANS ----
        # Same move that was made for decoupler's `min_n`: the value is the tool's own, and what
        # changes is that it is now DECLARED, PASSED and REPORTABLE. A parameter taken implicitly
        # cannot appear in the report, so two runs at two different values produce two result
        # files that are indistinguishable on the page.
        "auc_threshold": {"type": "float", "default": 0.05, "min": 0.0, "max": 1.0,
                          "help": "the fraction of each cell's gene ranking the AUC is "
                                  "integrated over. pySCENIC's own default is 0.05, i.e. the "
                                  "top 5%. It must sit BELOW the number of genes a cell has "
                                  "detected or the curve runs on past the detection limit into "
                                  "a randomly-ordered tail - see F1_ranking_depth, which is the "
                                  "panel that checks it"},
        "prune_rank_threshold": {"type": "int", "default": 1500, "min": 1,
                                 "help": "how deep into each motif's gene ranking cisTarget may "
                                         "recover a target from. 1500 is `prune2df`'s own "
                                         "default and what this plugin has been taking; the "
                                         "`pyscenic ctx` command line defaults the SAME "
                                         "parameter to 5000, so a published pySCENIC result is "
                                         "more likely to have used 5000 than 1500. Set 5000 to "
                                         "match the protocol paper's workflow"},
        "keep_only_activating": {"type": "bool", "default": True,
                                 "help": "keep only modules where the TF's expression "
                                         "correlates POSITIVELY with its targets. pySCENIC's own "
                                         "default is True, which means a repressor returns no "
                                         "regulon at all and is indistinguishable from a TF that "
                                         "regulates nothing. False keeps both halves and every "
                                         "regulon name then carries its (+) or (-) direction"},
    },

    "requires": {
        # EXACT PINS, DELIBERATELY. Stated once here rather than defended nine times: every
        # other plugin in this tree should prefer ranges, and this one must not.
        "exact_pins_why":
            "pySCENIC 0.12.1 is built on dask's distributed scheduler and the releases it was "
            "written against predate the pandas 2 copy-on-write changes. Resolved loose, "
            "arboreto's scatter path shifts underneath it and GRNBoost2 returns an EMPTY "
            "adjacency table rather than failing - a network with no edges, which reads "
            "downstream as 'no regulons found'. This is an older, self-consistent island and it "
            "cannot share an environment with anything modern.",
        "python": ">=3.10,<3.11",
        "packages": {"pyscenic": "==0.12.1", "numpy": "==1.23.5", "pandas": "==1.5.3",
                     "dask": "==2023.5.0", "distributed": "==2023.5.0",
                     "pyarrow": "==11.0.0", "setuptools": "==75.8.2",
                     "arboreto": "==0.1.6", "ctxcore": "==0.2.0",
                     # THE CONTRACT NEEDS IT. `_entry.py` reads the object with
                     # `anndata.read_h5ad` before this plugin sees anything, so an environment
                     # without anndata cannot run ANY plugin - and this one did not have it.
                     # Measured on PBS 677677: every one of ten units reported
                     # `NOT RUN scenic[...]  scenic's interpreter cannot read this object even
                     # re-encoded`, whose cause was `ModuleNotFoundError: No module named
                     # 'anndata'`. A RANGE, not a pin: this is the contract's dependency, not
                     # pySCENIC's, and nothing here calls it.
                     "anndata": ">=0.9,<0.11",
                     # THE PANELS NEED IT AND NOTHING DECLARED IT. `ctx.plot()` imports
                     # matplotlib, and this environment did not have it - which was invisible
                     # for as long as this plugin drew nothing. It is pinned like the rest of
                     # this island rather than ranged: 3.7.3 is the last line that builds
                     # against numpy 1.23 and pandas 1.5 without complaint, and matplotlib 3.8
                     # onward wants numpy >= 1.23 with wheels built against a newer ABI than
                     # the one pySCENIC 0.12.1 is standing on.
                     "matplotlib": "==3.7.3"},
    },

    "cost": "high", "cores": 16,
    # Measured, not estimated: fitted from this plugin's own instances in one run on a 10-sample mouse single-nucleus cohort (~99k cells). ONE dataset on ONE machine - a starting point that is right for scheduling, not a universal constant. Every run re-fits and prints its own.
    # Fitted from ten per-sample instances plus the cohort fit.
    "memory_gb_base": 11.4, "memory_gb_per_100k": 19.8,

    # WHAT ITS PAGE SHOULD CONTAIN. Five panels, and the first three are checks rather than
    # results, because every way this method fails on real data fails QUIETLY: the AUC of a
    # shallow cell is in range, a network that was never pruned is a full file of plausible
    # regulons, and two regulons sharing nine tenths of their targets read on a page as two
    # independent findings. None of the three announces itself in the answer.
    #
    # Panels are declared here in the order a reader needs them - can the AUC mean anything, did
    # the reference do any work, are these one finding or several, and only then the answer - and
    # the reporter enforces `diagnostic` before `result` whatever order they are written in.
    "report": {
        # WHAT MAKES THE UNITS COMPARABLE. Every figure on this page describes ONE unit; these
        # are the numbers the host puts on a shared axis, so a reader sees whether the units
        # agree before reading any single unit's panel as a finding.
        "unit_metrics": [
            {"id": "regulons", "question": "how many regulons survived in this unit? The network is inferred per unit, so this is a property of the unit and not only of the biology."},
            {"id": "cells_scored", "question": "how many cells were scored in this unit? Regulon count depends on it."},
        ],
        "figures": [
            {"id": "F1_ranking_depth", "shows": "diagnostic", "required": True,
             "question": "do cells have enough detected genes for the AUC cut-off to mean "
                         "anything, and is the shortfall spread evenly across populations?",
             "source": "figures/F1_ranking_depth.csv"},
            {"id": "F2_pruning_funnel", "shows": "diagnostic", "required": True,
             "question": "how much of the inferred co-expression survived motif pruning - and "
                         "did the reference do any work at all?",
             "source": "figures/F2_pruning_funnel.csv"},
            # OPTIONAL, AND THE ABSENCE IS THE FINDING. One regulon has no pair to overlap with,
            # and a run that returned one regulon is a much bigger caveat than a missing panel.
            {"id": "F3_regulon_overlap", "shows": "diagnostic", "required": False,
             "question": "are these regulons independent measurements, or do they share their "
                         "target genes?",
             "source": "figures/F3_regulon_overlap.csv",
             "when_absent": "fewer than two regulons survived, so there is no pair to overlap. "
                            "Read the single result below as one module, not as a network."},
            {"id": "F4_activity_by_population", "shows": "result", "required": False,
             "question": "which regulons are active in which populations?",
             "source": "figures/F4_activity_by_population.csv",
             "when_absent": "the object carries no cell-type annotation, or only one population "
                            "after the annotator's sentinels were set aside, so activity cannot "
                            "be summarised per population. The per-cell AUC is unaffected and is "
                            "beside this page."},
            {"id": "F5_activity_on_layout", "shows": "result", "required": False,
             "question": "is a regulon's activity coherent on the manifold, or scattered across "
                         "it?",
             "source": "figures/F5_activity_on_layout.csv",
             "when_absent": "the object carries no two-column layout to draw on - or one that "
                            "does not line up with the scored cells, and the run's own caveat "
                            "says which. Nothing was drawn on the first two columns of a wider "
                            "representation instead, whose axes carry no ordering and would show "
                            "a ball whatever structure the activity has."},
        ],
        # THE PAIRING, AND IT IS THE SHARPEST ONE THIS TOOL HAS. `decoupler` answers the same
        # question - per-cell activity for a transcription factor - from a CURATED PRIOR, where
        # this plugin infers the network from the data in front of it. Neither is ground truth
        # and the two disagree in an informative way: a regulon this plugin finds that the prior
        # has no edges for is either novel or an artefact of this dataset, and one the prior
        # scores that this plugin never assembled had too few co-expressed targets HERE. Declared
        # so the reporter can name the missing half as an absence; neither plugin can draw the
        # comparison alone.
        "reads_with": ["decoupler"],
    },

    "cannot_show": [
        "CO-EXPRESSION WITH A MOTIF IS NOT REGULATION. Nothing here observes a perturbation, so "
        "no edge is causal.",
        "Benchmarks recover very different numbers of TFs from the same data, so a single GRN "
        "result should not be reported alone. Both bulk and single-cell GRN methods performed "
        "poorly against known networks in a published comparison, and the recommendation that "
        "followed was to be wary of the inferred relationships rather than to prefer a method "
        "(Luecken & Theis, Mol Syst Biol 2019, citing Chen & Mar 2018).",
        "A network inferred from pooled conditions describes the average of them and may describe "
        "neither, which is why this runs per sample.",
        "An absent regulon is not evidence of an inactive TF: it may simply not have had enough "
        "expressed targets in this unit. With the default `keep_only_activating` it is also what "
        "a REPRESSOR returns, and those two absences are identical in every output here.",
        "AUC IS NOT COMPARABLE BETWEEN REGULONS OF DIFFERENT SIZE. It is an area under a "
        "recovery curve for one gene set within one cell's ranking, so a 200-target regulon and "
        "a 12-target regulon produce numbers on different scales. Compare a regulon with itself "
        "across cells, which is what every panel here does; do not rank two regulons against "
        "each other by their AUC.",
        "AUC IS ALSO A FUNCTION OF HOW MANY GENES A CELL DETECTED, and that is a library "
        "property, not a biological one. F1_ranking_depth is the only thing standing between "
        "that and a conclusion, and it can only report the risk - it cannot correct it.",
    ],
}


# ------------------------------------------------------------------------------------ figures
#
# THE THREE CHECKS COME FIRST BECAUSE ALL THREE FAILURES ARE QUIET. A SCENIC run that has gone
# wrong does not produce an error or an empty file - it produces regulons. So the page opens with
# the AUC's own precondition, then with how much work the motif reference actually did, then with
# whether the regulons it returned are independent of each other; and only after those with the
# activity itself.
#
#   ranking depth   AUCell integrates to a fixed rank. A cell that detected fewer genes than that
#                   rank scores off an arbitrary tail. Depth-driven AUC is in range and silent.
#   pruning funnel  GRNBoost2 proposes, cisTarget disposes. If nothing was disposed of, the
#                   result is co-expression under a regulon's name.
#   overlap         two regulons sharing most of their targets have correlated AUC by
#                   construction and are ONE finding reported twice.
#   by population   the answer: mean activity per regulon per population.
#   on the layout   the same answer against the manifold, where incoherence is visible and a
#                   table cannot show it.

#: How many regulons a heatmap can carry before the row labels stop being readable. Not a style
#: rule - past this the reader cannot match a row to a name, which is the only thing the panel is
#: for. Everything else stays in the full table beside it.
_HEATMAP_ROWS = 30

#: Pairs drawn in the overlap panel, and the same reason rather than a different one: each row
#: label is TWO regulon names, so it stops being matchable to a bar sooner than a heatmap row
#: does. The source table beside it is the full pairwise matrix, so the cut hides nothing.
_OVERLAP_ROWS = 25

#: Regulons drawn on the layout. Four panels at half a double column each is the most that keeps
#: a scatter of a large dataset legible; the rest are in the table.
_LAYOUT_PANELS = 4


def _colours(ctx, names):
    """A colour per population, and the pairs that share a hue NAMED rather than left silent.

    `ctx.populations()` has already taken the annotator's sentinels out, so nothing here needs a
    GREY category - every name arriving is a real call.
    """
    F = ctx.figure
    cols = F.palette(names)
    clash = getattr(F, "palette_collisions", None)
    for _colour, labs in (clash(names) if clash else []):
        ctx.caveat(f"{len(labs)} populations share one colour in the panels below "
                   f"({', '.join(labs)}). There are more populations than the palette has hues "
                   f"that stay separable; read those from the tables rather than from the "
                   f"legend.")
    return cols


def _clean(ax, F, layout_name=None):
    """Ticks and spines off, and the axes NAMED even though their values mean nothing.

    The name is printed whole. A layout key is often `<algorithm>_<what it was run on>` and
    splitting it needs a list of algorithms to split against; guessing which half is which
    invents a provenance, and an unrecognised name printed whole is the honest outcome.
    """
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    if layout_name:
        ax.set_xlabel(F.basis_label(layout_name, 1), loc="left")
        ax.set_ylabel(F.basis_label(layout_name, 2), loc="bottom")


def _fig_ranking_depth(ctx, detected, cutoff, n_universe, pops, colours):
    """THE PANEL THAT LICENSES EVERY AUC ON THE PAGE.

    AUCell ranks every gene within each cell and integrates the recovery curve out to a fixed
    rank - `auc_threshold` x the number of genes it was given. Genes tied at zero are ordered by
    a random shuffle of the gene axis, which is what the seed controls. So a cell that detected
    fewer genes than that rank has part of its curve integrated over an arbitrary order, and its
    AUC moves with library depth rather than with regulon activity. Nothing warns: the number
    comes back between 0 and 1 like every other cell's.

    The right-hand panel is the half that matters for a designed experiment. A depth shortfall
    spread evenly across populations weakens every regulon equally; one concentrated in a single
    population has converted a library property into an apparent biological difference, and no
    downstream test can undo that.
    """
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()
    d = {"barcode": np.asarray(ctx.adata.obs_names).astype(str),
         "genes_detected": np.asarray(detected, dtype=int)}
    if pops.groups is not None:
        lab = np.full(len(detected), "", dtype=object)
        lab[np.asarray(pops.mask)] = pops.groups
        d["label"] = lab
    src = pd.DataFrame(d).set_index("barcode")

    two = pops.groups is not None and len(pops.names) >= 2
    fig, axs = plt.subplots(1, 2 if two else 1,
                            figsize=(F.DOUBLE if two else F.SINGLE, F.SINGLE * 0.72),
                            squeeze=False, layout="constrained")
    ax = axs[0][0]
    ax.hist(np.asarray(detected, dtype=float), bins=60, color="#0072B2")
    ax.axvline(cutoff, color=F.INK, ls="--", lw=0.8)
    ax.set_xlabel("genes detected per cell")
    ax.set_ylabel("cells")
    ax.set_title("the AUC cut-off against the detection limit", loc="left")

    if two:
        ax2 = axs[0][1]
        sub = np.asarray(detected, dtype=float)[np.asarray(pops.mask)]
        gi = np.asarray(pops.groups)
        order = list(pops.names)
        bp = ax2.boxplot([sub[gi == l] for l in order], vert=False, widths=0.62,
                         patch_artist=True, showfliers=False,
                         medianprops=dict(color=F.INK, lw=0.8))
        for patch, l in zip(bp["boxes"], order):
            patch.set_facecolor((colours or {}).get(l, F.GREY))
            patch.set_edgecolor(F.INK)
            patch.set_linewidth(0.5)
        ax2.set_yticklabels(order)
        ax2.set_xlabel("genes detected per cell")
        ax2.axvline(cutoff, color=F.INK, ls="--", lw=0.8)
        ax2.invert_yaxis()
        ax2.set_title("per population", loc="left")

    below = float(np.mean(np.asarray(detected) < cutoff))
    n_aside = int((~np.asarray(pops.mask)).sum())
    # THE CAPTION DESCRIBES THE PANEL THAT WAS DRAWN, NOT THE ONE THIS FUNCTION CAN DRAW. It
    # said "the right panel asks whether that shortfall is even" unconditionally, on a figure
    # that has NO right panel unless the object carries two populations - so on an unannotated
    # object the caption pointed at a panel that is not there, which reads as a figure with half
    # of it missing. The declared question asks about populations either way, so the absence has
    # to be answered here in words.
    second = (f"The right panel asks whether that shortfall is even: a deficit concentrated in "
              f"one population is a technical property wearing a biological one. Annotator "
              f"sentinels are not a population - the {n_aside:,} cell(s) carrying one are in the "
              f"histogram and in no box."
              if two else
              "There is no per-population panel: fewer than two populations remain once the "
              "annotator's sentinels are set aside, so nothing here says whether the shortfall "
              "is even across populations - which is the half that decides whether a depth "
              "deficit can pass as a biological difference.")
    ctx.emit_figure(
        "F1_ranking_depth", fig,
        caption=(f"Genes detected per cell, against the rank the AUC is integrated out to "
                 f"(dashed line, {cutoff:,.0f} = auc_threshold x {n_universe:,} genes offered to "
                 f"AUCell). AUCell ranks all genes within each cell and takes the area under the "
                 f"recovery curve up to that rank; genes tied at zero are ordered by a seeded "
                 f"random shuffle, so for a cell to the LEFT of the line part of the curve is "
                 f"integrated over an arbitrary tail and its AUC tracks library depth rather "
                 f"than regulon activity. Here {100 * below:.1f}% of cells are left of it. "
                 + second),
        source=src)


def _fig_pruning_funnel(ctx, rows):
    """Did the motif reference do any work? The one question the result cannot answer for itself.

    GRNBoost2 proposes modules from co-expression alone; cisTarget prunes them against motif
    rankings, and the pruning is the entire difference between a regulon and a correlation. Both
    ends of this funnel are failures that produce a full, plausible result file: nothing pruned
    means the rankings were not consulted or not discriminating, and almost nothing surviving
    means the ranking database and the gene names are not describing the same organism.

    Counted in TRANSCRIPTION FACTORS at every stage, so the bars are comparable with each other.
    Edges and modules are in the source table, where the units can differ without misleading a
    reader who is looking at a picture.
    """
    import numpy as np
    import pandas as pd
    if not rows:
        return
    F, plt = ctx.figure, ctx.plot()
    df = pd.DataFrame(rows).set_index("stage")
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.5, 0.30 * len(df) + 0.8)))
    y = np.arange(len(df))
    ax.barh(y, df["transcription_factors"], height=0.7, color="#009E73")
    ax.set_yticks(y)
    ax.set_yticklabels(df.index)
    ax.invert_yaxis()
    ax.set_xlabel("transcription factors")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    span = float(df["transcription_factors"].max()) or 1.0
    for yi, v in zip(y, df["transcription_factors"]):
        ax.text(float(v) + 0.01 * span, yi, f"{int(v):,}", va="center", ha="left", fontsize=6,
                color=F.INK)
    ax.set_xlim(0, span * 1.18)
    ctx.emit_figure(
        "F2_pruning_funnel", fig,
        caption=("How many transcription factors survive each stage, from the candidate list to "
                 "the delivered regulons. The step that matters is motif pruning: it is the only "
                 "thing separating a regulon from a co-expression module, so a funnel that "
                 "barely narrows there is reporting correlation under a regulon's name, and one "
                 "that collapses there usually means the ranking database and these gene symbols "
                 "are not describing the same organism. Edge, module and regulon counts are in "
                 "the source table beside this panel."),
        source=df)


def _fig_regulon_overlap(ctx, regulons):
    """Are these independent findings, or one finding counted several times?

    Two regulons sharing most of their target genes have correlated AUC BY CONSTRUCTION - the
    same genes are being ranked for both - so reporting them as two active regulons overstates
    the evidence by exactly the amount they overlap. The Jaccard heatmap is the standard check in
    the SCENIC family's own tooling; what is drawn here is its most actionable slice, the closest
    partner each regulon has, because that is what decides whether a name may be reported alone.
    """
    import numpy as np
    import pandas as pd
    if len(regulons) < 2:
        ctx.caveat(
            "F3_regulon_overlap was not drawn: fewer than two regulons survived, so there is no "
            "pair to overlap. Read the result as one module rather than as a network.")
        return
    names = [str(r.name) for r in regulons]
    sets = [set(map(str, r.genes)) for r in regulons]
    n = len(names)
    J = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            u = len(sets[i] | sets[j])
            v = (len(sets[i] & sets[j]) / u) if u else 0.0
            J[i, j] = J[j, i] = v
    # AND THE DIAGONAL IS FILLED, because the exported matrix is what a reader opens to check
    # this panel and it was shipping a Jaccard of 0.0 for every regulon against ITSELF - a number
    # that is in range, reads like a measurement, and says the opposite of the truth. A comment
    # here claimed the table "keeps its true diagonal"; nothing ever wrote one, since the loop
    # above only fills i < j.
    for i in range(n):
        J[i, i] = 1.0 if sets[i] else 0.0
    full = pd.DataFrame(J, index=pd.Index(names, name="regulon"), columns=names)

    # THE DIAGONAL IS MASKED FOR THE ARGMAX AND NOT FOR THE TABLE. A regulon overlaps itself
    # completely, so `argmax` over an unmasked row returns that regulon every time - and before
    # the diagonal was filled it returned column 0 at a Jaccard of 0.0 wherever a row was empty,
    # which reads on the panel as a real pair.
    off = J.copy()
    np.fill_diagonal(off, -1.0)
    best = np.argmax(off, axis=1)
    top = pd.DataFrame({
        "regulon": names,
        "n_targets": [len(s) for s in sets],
        "closest_regulon": [names[b] for b in best],
        "jaccard": [float(J[i, best[i]]) for i in range(n)],
    }).sort_values("jaccard", ascending=False)
    # A MUTUAL PAIR IS ONE ROW, NOT TWO. Every regulon gets a row here, so where two are each
    # other's closest partner the SAME pair was drawn twice, one bar per direction - and a panel
    # whose whole purpose is to stop a reader counting one finding twice was itself printing it
    # twice. `top` keeps every regulon, because the count below is per regulon; only the bars are
    # de-duplicated.
    pair = top.apply(lambda r: tuple(sorted((r["regulon"], r["closest_regulon"]))), axis=1)
    show = top[~pair.duplicated()].head(_OVERLAP_ROWS)

    F, plt = ctx.figure, ctx.plot()
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.5, 0.19 * len(show) + 0.8)))
    y = np.arange(len(show))
    ax.barh(y, show["jaccard"], height=0.72, color="#CC79A7")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{a} / {b}" for a, b in zip(show["regulon"], show["closest_regulon"])])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Jaccard overlap of target genes")
    ax.axvline(0.5, color=F.INK, ls="--", lw=0.6)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    n_high = int((top["jaccard"] >= 0.5).sum())
    ctx.emit_figure(
        "F3_regulon_overlap", fig,
        caption=(f"For each regulon, its largest target-gene overlap with any other, strongest "
                 f"first: the {len(show)} strongest distinct pair(s) among {n} regulons are drawn, "
                 f"a mutually-closest pair once rather than once per direction. Two regulons that "
                 f"share their targets are scored on nearly the same genes and their AUC is "
                 f"correlated by construction, so they are one finding and not two. {n_high} of "
                 f"{n} regulons sit at or above 0.5 (dashed line) - counted over every regulon, "
                 f"not only the bars shown. The source table is the FULL pairwise matrix, so any "
                 f"pair can be checked, not only the closest."),
        source=full)


def _population_means(auc, pops):
    """Mean AUC per regulon per population, or None when there are fewer than two populations.

    SEPARATE FROM THE PANEL BECAUSE IT IS A PRODUCT, NOT A PICTURE.
    `tables/regulon_activity_by_label.csv` is declared in `produces`, and it was being written
    from inside the figure function - which run() calls inside the same try/except that keeps an
    hours-long fit alive through a drawing bug. So any drawing bug took a DECLARED TABLE with it,
    and the only trace was a log line saying a figure had not been drawn. Every other plugin in
    this tree emits its tables from run(); this one now does too.

    GROUPED BY POSITION, on an ARRAY rather than an index-aligned Series. `pops.mask` and
    `pops.groups` are positional facts about the object's rows and the AUC frame is in that same
    order; handing pandas a Series would make it align by barcode instead, which is correct only
    for as long as the barcodes stay unique, and silently pairs the wrong labels with the wrong
    cells the first time they do not.
    """
    import numpy as np
    if pops.groups is None or len(pops.names) < 2:
        return None
    idx = np.flatnonzero(np.asarray(pops.mask))
    by = auc.iloc[idx].groupby(np.asarray(pops.groups)).mean()
    by.index.name = "population"
    if by.shape[0] < 2 or by.shape[1] < 1:
        return None
    return by


def _fig_activity_by_population(ctx, by, n_aside=0):
    """Mean activity per regulon per population - the answer, with its own scale problem handled.

    ROWS ARE Z-SCORED ACROSS POPULATIONS, and that is not decoration. AUC is an area under a
    recovery curve for one gene set, so a 200-target regulon and a 12-target one produce numbers
    on different scales; a heatmap of raw AUC ranks regulons by size. Standardising each row asks
    the only question a reader can answer from a picture - where is THIS regulon most active -
    and the raw means are in the source table for the comparison the picture cannot support.

    Takes the means already computed and emitted by run(): this function draws, and produces
    nothing a reader would miss if the drawing failed.
    """
    import numpy as np
    M = by.T                                     # regulons x populations
    mu = M.mean(axis=1).to_numpy()[:, None]
    sd = M.std(axis=1).to_numpy()[:, None]
    # A FLAT ROW IS FLAT, AND `sd == 0` DOES NOT DETECT ONE. The standard deviation of three
    # identical AUC values is 1.7e-17, not 0.0, because the values themselves are not exactly
    # representable - so an exact-zero guard never fires, the row is divided by its own rounding
    # error, and a regulon with IDENTICAL activity in every population comes out at z = -0.82
    # everywhere. That is not a cosmetic problem here: rows are ordered by their maximum z, so
    # the flattest regulons in the dataset would have been ranked as the most population-specific
    # ones and drawn at full colour saturation. The tolerance is relative to the row's own level,
    # and the comparison is written `~(sd > tol)` so a NaN row is treated as flat rather than
    # slipping through as neither greater nor smaller.
    flat = ~(sd > np.abs(mu) * 1e-9)
    spread = np.where(flat, 1.0, sd)
    Z = (M.to_numpy() - mu) / spread
    Z[flat.ravel(), :] = 0.0
    order = np.argsort(-np.nanmax(Z, axis=1))[:min(_HEATMAP_ROWS, M.shape[0])]
    Z, rows = Z[order], [M.index[i] for i in order]
    cols = list(M.columns)

    F, plt = ctx.figure, ctx.plot()
    wide = len(cols) > 8
    fig, ax = plt.subplots(figsize=(F.DOUBLE if wide else F.SINGLE,
                                    max(1.8, 0.16 * len(rows) + 1.1)), layout="constrained")
    lim = float(np.nanmax(np.abs(Z))) or 1.0
    im = ax.imshow(Z, aspect="auto", cmap="RdBu_r", vmin=-lim, vmax=lim)
    ax.set_xticks(np.arange(len(cols)))
    # Shortened to the shortest unambiguous tail: these are annotation PATHS, and rotated
    # ninety degrees the full ones take more height than the data. The source table keeps
    # the whole path.
    _short = F.short_labels(list(cols))
    ax.set_xticklabels([_short[c] for c in cols], rotation=90)
    ax.set_yticks(np.arange(len(rows)))
    ax.set_yticklabels(rows)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label("mean AUC, standardised across populations")
    ctx.emit_figure(
        "F4_activity_by_population", fig,
        caption=(f"Mean regulon activity per population, standardised ACROSS POPULATIONS within "
                 f"each row: red is where a regulon is most active relative to its own average, "
                 f"blue where it is least. Rows are not comparable with each other and are not "
                 f"meant to be - AUC scales with the number of targets a regulon has. The "
                 f"{len(rows)} most population-specific of {M.shape[0]} regulons are drawn; the "
                 f"source table holds the raw, unstandardised mean for EVERY regulon, as does "
                 f"tables/regulon_activity_by_label.csv. Annotator sentinels are not a "
                 f"population: the {n_aside:,} cell(s) carrying one are in no column."),
        # THE SOURCE IS THE WHOLE TABLE, BECAUSE THE CAPTION SAYS IT IS. This was
        # `M.iloc[order]` - the drawn rows alone - under a caption promising every regulon, so
        # on any run with more regulons than the panel can carry the source data contradicted
        # the sentence pointing at it, and a reader checking the figure would have found the
        # other regulons missing with nothing saying why.
        source=M)
    return [str(r) for r in rows]


def _fig_activity_on_layout(ctx, auc, picks, ranked_by="most variable across cells"):
    """The same activity against the manifold, where a table cannot show incoherence.

    A regulon whose high-AUC cells sit together on the layout is describing a state; one whose
    high-AUC cells are sprayed evenly over it is describing noise, or depth. Both give the same
    per-population mean, and only the picture separates them.

    THE LAYOUT, NEVER THE REPRESENTATION. `ctx.layout()` returns two columns produced to be
    looked at, or None. There is no fallback to the first two columns of anything wider: a
    variational latent has no variance ordering, so its first two columns draw as a ball whatever
    the activity does, and a panel that cannot announce itself as wrong is worse than a panel
    that is missing.
    """
    import numpy as np
    import pandas as pd
    xy = ctx.layout()
    if xy is None:
        ctx.caveat(
            "F5_activity_on_layout was not drawn: this object carries no two-column layout. "
            "Nothing was drawn on a wider representation instead - its axes carry no ordering "
            "and the panel would show a ball whatever the activity does.")
        return
    xy = np.asarray(xy, dtype=float)[:, :2]
    if xy.shape[0] != auc.shape[0]:
        ctx.caveat(
            f"F5_activity_on_layout was not drawn: the layout has {xy.shape[0]:,} rows and the "
            f"AUC has {auc.shape[0]:,}. Drawing them together would place activity on the wrong "
            f"cells.")
        return
    ok = np.isfinite(xy).all(axis=1)
    if int(ok.sum()) < 10:
        ctx.caveat("F5_activity_on_layout was not drawn: fewer than ten cells have finite layout "
                   "coordinates.")
        return
    picks = [p for p in (picks or list(auc.columns)) if p in auc.columns][:_LAYOUT_PANELS]
    if not picks:
        # SILENCE IS THE ONE THING A MISSING PANEL MAY NOT BE. Every other exit here says why;
        # this one returned without a word, and the page would then print the `when_absent`
        # sentence about a missing layout for an object that has one.
        ctx.caveat(
            "F5_activity_on_layout was not drawn: none of the regulons it was asked to draw is a "
            "column of the AUC matrix, so there was nothing to put on the layout.")
        return
    # THE OBJECT'S OWN KEY, WHOLE. `_clean` promises the name is printed whole, and stripping the
    # `X_` prefix and uppercasing is not that: it turned a layout stored as `X_umap_scanvi` into
    # an axis labelled `UMAP_SCANVI 1`, an algorithm nobody has heard of. Printing the key the
    # object carries cannot be wrong about what it is.
    key, bare = ctx.layout_key()
    name = str(key or bare or "layout")

    F, plt = ctx.figure, ctx.plot()
    ncol = 2 if len(picks) > 1 else 1
    nrow = (len(picks) + ncol - 1) // ncol
    fig, axs = plt.subplots(nrow, ncol,
                            figsize=(F.DOUBLE if ncol == 2 else F.SINGLE, 2.15 * nrow),
                            squeeze=False, layout="constrained")
    for ax, reg in zip(axs.ravel(), picks):
        v = np.asarray(auc[reg], dtype=float)
        o = np.argsort(v[ok])                     # the active cells drawn last, not buried
        pts = ax.scatter(xy[ok][o, 0], xy[ok][o, 1], c=v[ok][o], s=2, cmap="viridis",
                         linewidths=0, rasterized=True)
        F.rasterize_points(ax)
        _clean(ax, F, name)
        ax.set_title(str(reg), loc="left")
        cb = fig.colorbar(pts, ax=ax, fraction=0.045, pad=0.02)
        cb.outline.set_visible(False)
        cb.set_label("AUC")
    for ax in axs.ravel()[len(picks):]:
        ax.set_visible(False)

    # THE COORDINATE COLUMNS ARE PREFIXED. A regulon is named after its transcription factor
    # and this plugin does not choose those names, so a regulon called `x` would have overwritten
    # the x coordinate in the source table with nothing anywhere saying so - the neighbouring
    # plugin that writes the same kind of table records the same lesson.
    src = pd.DataFrame({"barcode": np.asarray(ctx.adata.obs_names).astype(str),
                        "layout_x": xy[:, 0], "layout_y": xy[:, 1],
                        **{str(p): np.asarray(auc[p], dtype=float) for p in picks}}
                       ).set_index("barcode")
    ctx.emit_figure(
        "F5_activity_on_layout", fig,
        caption=(f"Regulon activity on the object's own {name} layout, for the {len(picks)} "
                 f"regulon(s) {ranked_by}. Cells are drawn lowest-AUC first so active "
                 f"cells are not buried. Read coherence, not level: activity concentrated in a "
                 f"region of the manifold is a state, activity sprayed evenly across it is noise "
                 f"or sequencing depth, and the two give the same per-population mean. The "
                 f"colour scale is per panel because AUC is not comparable between regulons of "
                 f"different size. {int((~ok).sum()):,} cell(s) had no finite coordinates and "
                 f"are absent from the panels but present in the source table."),
        source=src)


def run(ctx):
    import numpy as np
    import pandas as pd
    from arboreto.algo import grnboost2
    from pyscenic.utils import modules_from_adjacencies
    from pyscenic.prune import prune2df, df2regulons
    from pyscenic.aucell import aucell
    from ctxcore.rnkdb import FeatherRankingDatabase

    # THE JOURNAL CONVENTIONS, APPLIED BEFORE ANYTHING IS FITTED - and, far more to the point,
    # the cheapest possible proof that this environment can draw at all. The alternative is
    # discovering a matplotlib that is absent or has no usable backend AFTER a GRNBoost2 fit that
    # takes the better part of an hour per unit. This environment did not carry matplotlib until
    # the panels below were written, which nothing could have noticed while the plugin drew
    # nothing.
    ctx.plot()

    # BY ROLE, not by name. The mouse and human entries are different files with different
    # names; the plugin asks for "the rankings" and the host hands over the ones for this
    # organism, so this code does not name a species anywhere.
    rank_path = ctx.reference_for_role("rankings")
    tf_path = ctx.reference_for_role("tfs")
    m2t_path = ctx.reference_for_role("motif2tf")
    if not (rank_path and tf_path and m2t_path):
        return ctx.refuse(
            "regulon activity",
            "the cisTarget references are not available. Without them nothing is pruned, every "
            "co-expression module survives, and the regulons are raw correlation wearing a "
            "regulon's name - a full result file, and wrong.")

    counts = ctx.counts()
    genes = np.asarray(ctx.adata.var_names).astype(str)
    obs_names = np.asarray(ctx.adata.obs_names).astype(str)
    tfs = [l.strip() for l in open(tf_path, encoding="utf-8") if l.strip()]
    present = [t for t in tfs if t in set(genes)]

    # THE COHORT FIT SUBSAMPLES, AND IT HAS TO. GRNBoost2 holds the expression matrix DENSE and
    # ships it through a dask graph: 98,627 cells x 27,812 genes is an 11 GB frame, and measured
    # on PBS 680454 the fit spent SIX HOURS at 85% of CPU time in garbage collection, producing
    # eight lines of progress. It does not fail - it thrashes, which is worse, because a job that
    # is 3% productive looks exactly like a job that is merely slow.
    #
    # A regulatory relationship is estimated from co-expression ACROSS cells and the estimate
    # stabilises long before 100k of them; the per-sample fits recovered 37-111 regulons from
    # 13,824 cells apiece in about 52 minutes. The cap is therefore a tractability choice with a
    # statistical justification, not a shortcut, and `cohort_max_cells: 0` disables it.
    #
    # BALANCED BY SAMPLE, not proportional. The cohort fit exists to produce ONE vocabulary that
    # every condition is scored against; sampling proportionally would let whichever animal
    # yielded most nuclei write more of that vocabulary than the others. Every sample contributes
    # the same number of cells, and the ones with fewer contribute all they have.
    cap = int(ctx.config["cohort_max_cells"])
    fit_rows = None                       # None = fit on every cell, which is the per-unit case
    if PLUGIN.get("per_unit") and ctx.unit is None and cap and counts.shape[0] > cap:
        rng = np.random.default_rng(ctx.config["seed"])
        if "sample" in ctx.keys:
            samp = ctx.obs("sample").astype(str).to_numpy()
            groups = sorted(set(samp))
            per = max(1, cap // len(groups))
            pick = []
            for g in groups:
                idx = np.flatnonzero(samp == g)
                pick.append(idx if len(idx) <= per
                            else rng.choice(idx, size=per, replace=False))
            take = np.sort(np.concatenate(pick))
            how = f"balanced across {len(groups)} sample(s), up to {per:,} cells each"
        else:
            take = np.sort(rng.choice(counts.shape[0], size=cap, replace=False))
            how = "at random; no sample key was available to balance across"
        fit_rows = take
        ctx.log(f"  cohort fit subsampled {counts.shape[0]:,} -> {len(take):,} cells ({how})")
        ctx.caveat(
            f"THE COHORT NETWORK WAS INFERRED FROM A SUBSAMPLE: {len(take):,} of "
            f"{counts.shape[0]:,} cells, {how}, seed {ctx.config['seed']}. No cell was removed "
            f"from the object and AUC IS SCORED FOR EVERY CELL - only the network INFERENCE saw "
            f"the subsample. A regulon absent here may be one the subsample had too few cells to "
            f"support. Set cohort_max_cells to 0 to fit on all cells.")

    # TARGETS ONLY, AND REGULATORS ARE NEVER DROPPED. A gene detected in a handful of cells cannot
    # support a boosted regression over thousands of them, and GRNBoost2 fits EVERY column as a
    # target - so an undetected gene costs a full fit to return noise. Restricting targets is
    # standard SCENIC practice; doing it silently would not be, so the count is logged, the gene
    # stays in the object, and `min_cells_per_gene: 0` turns it off.
    #
    # A TF is exempt whatever its detection rate: it is a REGRESSOR, dropping it removes an
    # explanation rather than a cost, and nothing downstream could recover the regulon it would
    # have carried.
    # DETECTION IS COUNTED ON THE CELLS THAT WILL BE FIT. Counting it on cells the regression
    # never sees would offer targets the fit has no evidence for.
    fit_counts = counts if fit_rows is None else counts[fit_rows, :]
    fit_names = obs_names if fit_rows is None else obs_names[fit_rows]
    detected = np.asarray((fit_counts > 0).sum(axis=0)).ravel()
    floor = int(ctx.config["min_cells_per_gene"])
    keep = detected >= floor if floor else np.ones(len(genes), bool)
    keep |= np.isin(genes, list(present))
    dropped = int((~keep).sum())

    sub = fit_counts[:, keep]
    kept_genes = genes[keep]
    # float32 HALVES the graph dask ships to its workers. GRNBoost2 splits on ordering, and no
    # split in a boosted tree over UMI counts turns on the 8th decimal place.
    dense = np.asarray(sub.todense() if hasattr(sub, "todense") else sub, dtype=np.float32)
    ex = pd.DataFrame(dense, index=pd.Index(fit_names, name="cell"), columns=kept_genes)
    ctx.log(f"{ex.shape[0]:,} cells x {ex.shape[1]:,} genes; "
            f"{len(present):,} of {len(tfs):,} declared TFs present")
    if dropped:
        ctx.log(f"  {dropped:,} gene(s) not offered as targets: detected in fewer than {floor} "
                f"cell(s) here. They remain in the object and every TF was kept regardless.")
        ctx.caveat(f"{dropped:,} of {len(genes):,} genes were not offered to GRNBoost2 as TARGETS "
                   f"(detected in fewer than {floor} cells in this unit). No regulon can name one "
                   f"of them as a target here. They were NOT removed from the object and were NOT "
                   f"removed as regulators; set min_cells_per_gene to 0 to offer all of them.")
    if len(present) < 10:
        return ctx.refuse("regulon activity",
                          f"only {len(present)} of {len(tfs):,} transcription factors from the "
                          f"{ctx.organism} list are in this object. That is a gene-NAMING "
                          f"mismatch, not a biological result.")

    # HOW MANY GENES EACH CELL DETECTED, over the SAME gene universe AUCell will rank - the kept
    # columns, not the object's full var. AUCell integrates the recovery curve out to
    # auc_threshold x this many genes, so a cell whose detected count is below that rank runs off
    # the end of its own data and scores against a randomly-ordered tail. Counted for EVERY cell,
    # including the ones a subsampled fit never saw, because every cell gets an AUC.
    #
    # Chunked over rows for the same reason the AUC scoring is: materialising a boolean over the
    # whole matrix at once is the allocation that made the fit thrash, and moving a failure is
    # not fixing it.
    n_universe = int(keep.sum())
    detected_per_cell = np.zeros(counts.shape[0], dtype=np.int64)
    for _s in range(0, counts.shape[0], 20_000):
        _e = min(_s + 20_000, counts.shape[0])
        detected_per_cell[_s:_e] = np.asarray(
            (counts[_s:_e, :][:, keep] > 0).sum(axis=1)).ravel()
    auc_cut = float(ctx.config["auc_threshold"]) * n_universe
    n_shallow = int((detected_per_cell < auc_cut).sum())
    ctx.log(f"  AUC integrates to rank {auc_cut:,.0f} of {n_universe:,} genes "
            f"(auc_threshold={ctx.config['auc_threshold']}); {n_shallow:,} cell(s) detected "
            f"fewer genes than that")

    # THE ALLOCATED SHARE, NOT THE MACHINE'S. `client_or_address="local"` makes arboreto build a
    # LocalCluster sized from `multiprocessing.cpu_count()` - the NODE - so this plugin, which
    # runs once per sample, starts the node's worth of workers per sample. Ten instances on one
    # node is ten times the machine in dask workers, and the symptom is a wave slower than running
    # the same work serially. `ctx.effect` releases the client on every exit path including a
    # raise, which is the case a `finally` written in a hurry gets wrong.
    from distributed import Client, LocalCluster
    client = ctx.effect(
        lambda: Client(LocalCluster(n_workers=max(1, int(ctx.cores)), threads_per_worker=1,
                                    processes=False)),
        lambda c: c.close())
    adj = grnboost2(expression_data=ex, tf_names=present, verbose=False,
                    seed=ctx.config["seed"], client_or_address=client)
    # EMPTY IS THE FAILURE THAT DOES NOT RAISE. When arboreto and dask disagree about the
    # scheduler, GRNBoost2 returns no edges and downstream reads that as "no regulons found".
    if adj.shape[0] == 0:
        return ctx.refuse("regulon activity",
                          "GRNBoost2 returned NO EDGES. That is the signature of arboreto and "
                          "the installed dask disagreeing about the scheduler, not of a dataset "
                          "with no co-expression.")
    ctx.log(f"  {adj.shape[0]:,} adjacencies, {adj['TF'].nunique():,} regulators")

    # keep_only_activating IS PASSED, NOT INHERITED, and it is the parameter that decides what an
    # ABSENCE in this result means. `modules_from_adjacencies` splits every module by the sign of
    # the TF-target correlation and, at its own default, keeps the activating half alone - so a
    # repressor returns no regulon and is indistinguishable from a TF that regulates nothing.
    # Same value as before; what changes is that the run can now say it.
    modules = list(modules_from_adjacencies(
        adj, ex, keep_only_activating=bool(ctx.config["keep_only_activating"])))
    db = FeatherRankingDatabase(fname=str(rank_path), name="rankings")
    # rank_threshold IS PASSED for the same reason and with a sharper edge: `prune2df`'s own
    # signature defaults it to 1500 and `pyscenic ctx` defaults the SAME parameter to 5000, so
    # until it was passed here a result could not say which of the tool's two official defaults
    # produced it. See the gotcha; the value is unchanged at 1500.
    pruned = prune2df([db], modules, str(m2t_path), num_workers=ctx.cores,
                      rank_threshold=int(ctx.config["prune_rank_threshold"]))
    # NOTHING SURVIVED IS ITS OWN DIAGNOSIS, and it is not the same one as a thin result. An
    # empty enrichment table means the rankings and these gene symbols did not meet, which is a
    # reference problem; saying so here is cheaper than letting df2regulons decide what an empty
    # frame means.
    if len(pruned) == 0:
        return ctx.refuse(
            "regulon activity",
            f"cisTarget found NO motif-enriched module: {len(modules):,} co-expression module(s) "
            f"went in and the enrichment table came back empty. That is usually the ranking "
            f"database and these gene symbols not describing the same organism, or a "
            f"prune_rank_threshold ({ctx.config['prune_rank_threshold']}) too shallow for this "
            f"database, rather than a dataset with no regulation.")
    all_regulons = list(df2regulons(pruned))
    regulons = [r for r in all_regulons
                if len(r.genes) >= ctx.config["min_genes_per_regulon"]]
    if not regulons:
        return ctx.refuse("regulon activity",
                          f"no regulon survived pruning with at least "
                          f"{ctx.config['min_genes_per_regulon']} targets")
    ctx.log(f"  {len(regulons)} regulon(s) after motif pruning")

    # THE FUNNEL, COUNTED IN ONE UNIT SO THE STAGES ARE COMPARABLE. Transcription factors, not
    # edges at one stage and modules at the next: the question the panel answers is how many
    # regulators survive each filter, and a bar chart whose bars are different quantities answers
    # it wrongly while looking right. The other counts ride along in the table.
    def _tf(x):
        return str(getattr(x, "transcription_factor", None) or getattr(x, "name", x))

    funnel = [
        {"stage": "offered as regulators", "transcription_factors": len(present),
         "items": len(present), "unit": "transcription factors in the declared list and present "
                                        "in this object"},
        {"stage": "with a co-expression edge",
         "transcription_factors": int(adj["TF"].nunique()),
         "items": int(adj.shape[0]), "unit": "GRNBoost2 adjacencies"},
        {"stage": "with a co-expression module",
         "transcription_factors": len({_tf(m) for m in modules}),
         "items": len(modules), "unit": "modules offered to cisTarget"},
        {"stage": "motif-enriched", "transcription_factors": len({_tf(r) for r in all_regulons}),
         "items": len(all_regulons), "unit": "regulons out of cisTarget, before the size floor"},
        {"stage": f"kept (>= {ctx.config['min_genes_per_regulon']} targets)",
         "transcription_factors": len({_tf(r) for r in regulons}),
         "items": len(regulons), "unit": "regulons delivered"},
    ]
    kept_frac = (funnel[3]["transcription_factors"] / funnel[2]["transcription_factors"]
                 if funnel[2]["transcription_factors"] else float("nan"))
    ctx.log(f"  motif pruning kept {funnel[3]['transcription_factors']:,} of "
            f"{funnel[2]['transcription_factors']:,} regulators with a module")

    # SCORED FOR EVERY CELL, INCLUDING THE ONES THE FIT NEVER SAW. `X_regulon_auc` is an obsm
    # block and must have one row per cell of the object; scoring only the fit subsample would
    # emit a 25k-row array for a 98k-row object, and the caveat above promises otherwise.
    #
    # CHUNKED, because building one dense frame over every cell is the 11 GB allocation that made
    # the fit thrash in the first place - and doing it here would move the failure rather than
    # fix it. AUCell ranks genes WITHIN each cell independently, so a chunk boundary cannot
    # change a cell's score: this is exact, not an approximation.
    #
    # auc_threshold IS PASSED AT AUCELL'S OWN DEFAULT rather than inherited, and it is the
    # parameter this whole result is an area under. Passing it explicitly is what lets the run,
    # the caveats and F1_ranking_depth all quote the same number - two runs at two different
    # thresholds otherwise produce two AUC matrices that are indistinguishable on the page.
    auc_kw = dict(num_workers=ctx.cores, seed=ctx.config["seed"],
                  auc_threshold=float(ctx.config["auc_threshold"]))
    if fit_rows is None:
        auc = aucell(ex, regulons, **auc_kw)
    else:
        parts, step = [], 20_000
        for start in range(0, counts.shape[0], step):
            stop = min(start + step, counts.shape[0])
            blk = counts[start:stop, :][:, keep]
            blk = np.asarray(blk.todense() if hasattr(blk, "todense") else blk, dtype=np.float32)
            parts.append(aucell(
                pd.DataFrame(blk, index=pd.Index(obs_names[start:stop], name="cell"),
                             columns=kept_genes),
                regulons, **auc_kw))
            del blk
        auc = pd.concat(parts)
        ctx.log(f"  AUC scored for all {auc.shape[0]:,} cells in "
                f"{len(parts)} chunk(s), from a network fitted on {ex.shape[0]:,}")
    if auc.shape[0] != ctx.adata.n_obs:
        return ctx.refuse("regulon activity",
                          f"AUC has {auc.shape[0]:,} rows for an object of {ctx.adata.n_obs:,} "
                          f"cells. An obsm block must have one row per cell; emitting this would "
                          f"misalign every regulon score with the wrong cell.")
    # ONLY THE COHORT FIT CONTRIBUTES THE CELL-LEVEL BLOCK, and the reason is the same one this
    # plugin runs twice for. `obsm` is one array over the whole object: the per-sample fits each
    # discovered their own regulon set, so stacking their AUC columns into one block would place
    # values that are not the same quantity in the same column - the exact misuse every
    # per-sample caveat here warns against.
    #
    # The merger caught it rather than doing it: with a cohort fit present the two scopes claim
    # the same cells and it refused the lot ("the units are not disjoint"), and without one the
    # per-sample widths disagreed. Both refusals were right, and neither is fixable by the
    # merger - the plugin has to stop asking.
    #
    # A per-sample fit keeps its AUC as a table in its own directory, where it is per-sample and
    # reads as such.
    if ctx.unit is None:
        ctx.emit_obsm("X_regulon_auc", auc.to_numpy())
    else:
        ctx.emit_table("regulon_auc", auc)

    # THE UNIT OF REPLICATION IS THE SAMPLE, NOT THE CELL, and the cohort fit is where that gets
    # got wrong. Its AUC columns ARE comparable between cells - that is the whole point of fitting
    # once - and the obvious next step is a per-cell test across conditions with n in the tens of
    # thousands. Cells from one animal are not independent replicates of that animal's condition,
    # so such a test reports the cell count, not the effect: the field's answer for exactly this
    # structure is a mixed model with the individual as a random effect, or pseudobulk first
    # (Fleck/Nagy et al. meta-analyses of AD and SCZ snRNA-seq, Nat Commun 2025).
    #
    # So the cohort fit also ships the AGGREGATE a between-condition test should consume, which
    # makes the correct comparison the easy one to reach for. `de` already treats the sample as
    # the replicate; there is no reason regulon activity should not.
    if PLUGIN.get("per_unit") and ctx.unit is None and "sample" in ctx.keys:
        samp = ctx.obs("sample").astype(str).to_numpy()
        # LENGTHS MUST MATCH EXACTLY. This truncated the longer of the two and carried on, which
        # pairs cells with the wrong samples from the first mismatched row onward and produces a
        # full, plausible table. There is no correct behaviour on a mismatch except to stop.
        if len(samp) != auc.shape[0]:
            return ctx.refuse(
                "regulon activity",
                f"{len(samp):,} sample labels for {auc.shape[0]:,} scored cells. Aggregating "
                f"these would pair cells with the wrong samples and return a full table.")
        # groupby on an ALIGNED SERIES, not set_axis: `set_axis` semantics and its `copy`
        # keyword have moved across pandas versions, and this plugin is pinned to an older,
        # self-consistent island where that matters.
        by = auc.groupby(pd.Series(samp, index=auc.index, name="sample")).mean()
        ctx.emit_table("regulon_activity_by_sample", by)
        ctx.caveat(
            f"tables/regulon_activity_by_sample.csv is the MEAN AUC per regulon per sample, and "
            f"it is what a between-condition test should read. n = {by.shape[0]} samples, not "
            f"{auc.shape[0]:,} cells: cells from one animal are not independent replicates of "
            f"that animal's condition, and a per-cell test across conditions reports the cell "
            f"count rather than the effect.")
    sizes = [len(r.genes) for r in regulons]
    ctx.emit_table("regulon_targets", pd.DataFrame(
        [{"regulon": r.name, "n_targets": len(r.genes),
          "targets": ";".join(sorted(r.genes))} for r in regulons]).set_index("regulon"))

    # ------------------------------------------------------------ figures
    #
    # DIAGNOSTICS FIRST, in the order the `report` block declares them, and each guarded on its
    # own. A panel that cannot be drawn says why through `ctx.caveat` and the page prints the
    # `when_absent` sentence beside the gap; a panel that RAISES is logged and the run keeps its
    # regulons, because losing an hours-long fit to a drawing bug would be the most expensive
    # possible way to be told about a drawing bug.
    pops = ctx.populations()
    colours = _colours(ctx, pops.names) if pops.groups is not None else {}
    ctx.log("figures:")
    for what, fn in (
        ("F1_ranking_depth",
         lambda: _fig_ranking_depth(ctx, detected_per_cell, auc_cut, n_universe, pops, colours)),
        ("F2_pruning_funnel", lambda: _fig_pruning_funnel(ctx, funnel)),
        ("F3_regulon_overlap", lambda: _fig_regulon_overlap(ctx, regulons)),
    ):
        try:
            fn()
        except Exception as e:                                            # noqa: BLE001
            ctx.log(f"    {what} not drawn: {type(e).__name__}: {e}")
    # THE TABLE IS A PRODUCT AND IS EMITTED HERE; THE PANEL ONLY DRAWS IT. Computed and written
    # outside the try/except so that a drawing bug costs a figure and not a declared table - the
    # same lesson as the shallow-cell caveat below, which used to be read back out of a panel's
    # return value and went missing whenever the drawing did.
    n_aside = int((~np.asarray(pops.mask)).sum())
    by_pop = _population_means(auc, pops)
    picks, ranked_by = None, "most variable across cells"
    if by_pop is None:
        ctx.caveat(
            "F4_activity_by_population was not drawn: the object carries no cell-type annotation "
            "with at least two populations once the annotator's sentinels were set aside. The "
            "per-cell AUC is unaffected.")
    else:
        ctx.emit_table("regulon_activity_by_label", by_pop.T)
        try:
            picks = _fig_activity_by_population(ctx, by_pop, n_aside)
            ranked_by = "most population-specific in the panel above"
        except Exception as e:                                            # noqa: BLE001
            ctx.log(f"    F4_activity_by_population not drawn: {type(e).__name__}: {e}")
    try:
        # THE SAME REGULONS THE HEATMAP RANKED, so the two result panels cannot disagree about
        # which regulons this run is pointing at. With no populations there is no specificity to
        # rank by and the most variable across cells is the honest fallback - and the caption
        # SAYS WHICH, because "the most population-specific regulons" printed over a fallback
        # ranking is a claim about an annotation the object does not carry.
        if not picks:
            picks, ranked_by = (list(auc.var().sort_values(ascending=False).index),
                                "most variable across cells")
        _fig_activity_on_layout(ctx, auc, picks, ranked_by)
    except Exception as e:                                                # noqa: BLE001
        ctx.log(f"    F5_activity_on_layout not drawn: {type(e).__name__}: {e}")

    # ------------------------------------------------------------ caveats, from the data
    #
    # THE THREE PARAMETERS THAT DECIDE WHAT THE AUC MEANS, PRINTED WITH THE NUMBERS. They were
    # taken implicitly until 2026-08-25, which meant no result could be compared with any other
    # SCENIC result - including a later run of this same plugin - because nothing recorded them.
    ctx.caveat(
        f"AUC parameters, all at pySCENIC's own defaults and now stated rather than inherited: "
        f"auc_threshold={ctx.config['auc_threshold']} (the AUC is the area under each cell's "
        f"recovery curve out to rank {auc_cut:,.0f} of {n_universe:,} genes), "
        f"prune_rank_threshold={ctx.config['prune_rank_threshold']} (how deep into each motif's "
        f"ranking a target could be recovered from - `pyscenic ctx` defaults the same parameter "
        f"to 5000, so a published pySCENIC result was more likely computed at that), "
        f"keep_only_activating={bool(ctx.config['keep_only_activating'])}.")
    if bool(ctx.config["keep_only_activating"]):
        ctx.caveat(
            "ONLY ACTIVATING MODULES WERE KEPT, which is pySCENIC's default. A TF whose targets "
            "are negatively correlated with it returns no regulon here, so in this result a "
            "repressor and a TF that regulates nothing look identical. Set keep_only_activating "
            "to false to keep both halves; the regulon names then carry their direction.")
    # FROM THE NUMBER, NOT FROM THE FIGURE. This read the fraction back out of the panel's return
    # value, so a caveat about the data would have gone missing whenever the DRAWING failed -
    # which is the one moment a reader most needs to be told in words.
    shallow_frac = n_shallow / float(counts.shape[0] or 1)
    if shallow_frac >= 0.05:
        ctx.status = "partial"
        ctx.caveat(
            f"{100 * shallow_frac:.1f}% of cells detected fewer genes than the rank the AUC is "
            f"integrated to ({auc_cut:,.0f}). For those cells part of the recovery curve runs "
            f"past the detection limit into a randomly-ordered tail, so their AUC moves with "
            f"library depth as well as with regulon activity. See F1_ranking_depth for whether "
            f"the shortfall is spread evenly across populations - if it is not, an apparent "
            f"difference in regulon activity between those populations may be a difference in "
            f"depth. Lowering auc_threshold shortens the curve to what the shallowest cells "
            f"actually measured.")
    if sizes:
        ctx.caveat(
            f"Regulon size spans {min(sizes):,} to {max(sizes):,} target genes (median "
            f"{int(sorted(sizes)[len(sizes) // 2]):,}). AUC is an area under a recovery curve "
            f"for one gene set within one cell's ranking, so it does NOT put two regulons of "
            f"different size on the same scale. Compare a regulon with itself across cells, "
            f"which is what every panel here does; do not rank two regulons against each other "
            f"by their AUC.")
    if funnel[2]["transcription_factors"]:
        ctx.caveat(
            f"Motif pruning kept {funnel[3]['transcription_factors']:,} of "
            f"{funnel[2]['transcription_factors']:,} regulators that had a co-expression module "
            f"({100 * kept_frac:.0f}%). Pruning is the entire difference between a regulon and a "
            f"correlation, so read that fraction before the regulons: near 100% means the "
            f"reference removed almost nothing, and near 0% usually means the ranking database "
            f"and these gene symbols are not describing the same organism. F2_pruning_funnel.")

    # THE HEADLINE MUST NOT REPORT THE FIT SIZE AS THE RESULT SIZE. `ex` is the subsample for a
    # cohort fit, so this read "over 25,000 cells" for a result covering 98,627 of them.
    # ON A SHARED AXIS WITH THE OTHER UNITS. Declared in `report.unit_metrics`; the host
    # draws the comparison, so this is the whole of what this plugin owes for one.
    ctx.metric("regulons", len(regulons))
    ctx.metric("cells_scored", int(auc.shape[0]))
    if ex.shape[0] != auc.shape[0]:
        ctx.headline = (f"{len(regulons)} regulon(s), inferred from {ex.shape[0]:,} cells and "
                        f"scored on {auc.shape[0]:,}")
    else:
        ctx.headline = (f"{len(regulons)} regulon(s) over {auc.shape[0]:,} cells, "
                        f"inferred from this {'unit' if ctx.unit else 'dataset'}")
    ctx.caveat("The network was inferred from THIS data, so it is not comparable with one "
               "inferred from another dataset, and an absent regulon is not evidence of an "
               "inactive TF.")

    # THE TWO SCOPES ANSWER DIFFERENT QUESTIONS AND EACH SAYS WHICH IT IS. A reader who mistakes
    # one for the other draws a between-condition conclusion from columns that are not the same
    # quantity - the failure this plugin runs twice to prevent.
    if PLUGIN.get("per_unit") and ctx.unit is None:
        ctx.caveat(
            "THIS IS THE COHORT FIT: one regulon vocabulary over every cell, which is what makes "
            "activity comparable BETWEEN cells and conditions. The per-sample fits beside it are "
            "not interchangeable with it - each discovered its own regulon set, so their AUC "
            "columns are not the same quantity.")
        # A GRN POOLED ACROSS SAMPLES LEARNS WHATEVER CO-VARIES, INCLUDING THE BATCH. When the
        # upstream tool has recorded that a factor never varies within a batch, co-expression
        # driven by the batch is indistinguishable from co-expression driven by that factor, and
        # a regulon-activity difference across it cannot be attributed to biology. Reported, not
        # refused: the fit is still the right vocabulary for every comparison the constraint does
        # not name.
        if ctx.constraint:
            ctx.caveat(
                "An upstream CONSTRAINT ON USE applies to this object and it applies to this fit "
                "in particular. A cohort GRN learns whatever co-varies across the pooled cells, "
                "so where a design factor never varies within a batch, co-expression driven by "
                "the batch enters the regulons themselves and a difference in regulon activity "
                "across that factor cannot be separated from it. The constraint, verbatim: "
                + ctx.constraint.strip()[:600])
    elif PLUGIN.get("per_unit"):
        ctx.caveat(
            "THIS IS A PER-SAMPLE FIT and its regulon set was discovered from this sample alone. "
            "Do NOT compare these AUC values with another sample's - use the cohort fit for that. "
            "What these are good for is REPRODUCIBILITY: a regulon recovered independently in "
            "many samples is far stronger evidence than one appearing in a single pooled fit.")
    ctx.caveat(f"Pruned against the {ctx.organism} cisTarget rankings. Motif enrichment is what "
               f"makes a module a regulon; without it these would be raw co-expression.")


def selftest(ctx):
    """Prove GRNBoost2 runs and RECOVERS A PLANTED REGULATOR — the empty table is the failure.

    The cisTarget steps are not tested here: they need ~400 MB of rankings, which is a fetch and
    not a selftest. What is proved is the half that needs no reference data, and the report says
    which half that is.
    """
    import numpy as np
    import pandas as pd
    from arboreto.algo import grnboost2
    from pyscenic.utils import modules_from_adjacencies                # noqa: F401
    from pyscenic.prune import prune2df                                # noqa: F401
    from pyscenic.aucell import aucell                                 # noqa: F401

    rng = np.random.default_rng(0)
    n, g = 120, 40
    genes = [f"Gene{i:02d}" for i in range(g)]
    drive = rng.normal(5.0, 2.0, size=n)
    X = rng.normal(5.0, 1.0, size=(n, g))
    X[:, 0] = drive                                    # the planted regulator
    for j in range(1, 9):
        X[:, j] = drive * (1.0 + 0.05 * j) + rng.normal(0, 0.3, size=n)
    ex = pd.DataFrame(np.clip(X, 0, None), index=[f"c{i}" for i in range(n)], columns=genes)

    adj = grnboost2(expression_data=ex, tf_names=genes, verbose=False, seed=0,
                    client_or_address="local")
    assert adj.shape[0] > 0, (
        "GRNBoost2 returned NO EDGES on data with a planted regulator. This is the failure this "
        "selftest exists for: arboreto and the installed dask disagree about the scheduler and "
        "the inference comes back empty instead of raising.")
    for col in ("TF", "target", "importance"):
        assert col in adj.columns, f"the adjacency table has no {col!r}; the schema moved"
    imp = adj["importance"].to_numpy(dtype=float)
    assert np.isfinite(imp).all() and (imp > 0).any(), "importances are not finite and positive"
    assert genes[0] in set(adj["TF"].astype(str)), (
        f"the planted regulator {genes[0]!r} is not among the regulators recovered - the "
        f"inference ran but did not find an edge built into the fixture.")
    ctx.log(f"  {adj.shape[0]:,} edges; planted regulator recovered")
    ctx.log("  NOT tested here: the cisTarget prune and AUCell steps, which need the motif "
            "rankings from references.")
