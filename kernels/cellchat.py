"""Cell–cell communication with CellChat's own database and scoring — a second, independent map.

THE FORMAT DID NOT NEED A SECOND SHAPE FOR R.

CellChat is an R package, and this is a Python plugin like every other. It writes what R needs,
runs `Rscript`, and reads back what R wrote. The bridge lives HERE, inside the one plugin that
needs it, rather than in the host — because a host that grows a second plugin format for every
language grows a second plugin format for every language, and the contract (`ctx` in, `emit_*`
out) is the same either way.

What that costs is honest and small: two file round-trips and an `Rscript` on PATH. What it buys
is that the host, the planner, the resolver, the feedback loop and the report treat this exactly
like any other plugin.

WHAT THE PAGE HAS TO CONTAIN, AND WHY IT IS MOSTLY CHECKS

This method cannot fail loudly. Every one of its failure modes returns a small, plausible,
well-formed edge table:

  the database did not match      symbols from another annotation, or an object already reduced
                                  to highly-variable genes, leave most interactions with a gene
                                  that is simply absent. Nothing errors; fewer edges come back.
  the population was too small    `filterCommunication(min.cells)` drops its edges AFTER scoring,
                                  and CellChat's own averaging returns zero for a gene expressed
                                  in too few of a population's cells — 25% of them under the
                                  default `triMean`. A quiet population and an unsampled one are
                                  the same picture.
  the p-value hit its floor       the test is a permutation of the group labels, `nboot` of them.
                                  A p-value can only be a multiple of 1/nboot, so at the default
                                  100 the whole table lies in five values and `0` means "not
                                  beaten in 100 draws", not "vanishingly unlikely".

So the diagnostics come first and the results are worth reading only underneath them: of the
ten panels, three are diagnostics (F1-F3) and seven are results (F4-F10). *This paragraph said
"three of the five panels" until 2026-08-29, having been written when there were five.*

THE RETURN CONTRACT — what one row of `ccc_edges.csv` is, and what each column can carry

Every panel is drawn from this table, so this is the material all of them are made of. Read off
the delivered file, not from the vignette.

| field | what one element is | units and scale | theoretical range | relative or absolute | depends on | degenerate value |
|---|---|---|---|---|---|---|
| `source`, `target` | an ordered population pair | label, categorical | the labels PRESENT IN THIS UNIT | relative — a population with no cells here is not a row and not an axis entry | the annotation upstream | absent entirely; never a zero row |
| `prob` | that pair, for that L-R pair | communication probability | (0, 1], not calibrated | **RELATIVE** — law of mass action over the cells present, with `population.size` | `type`, `trim`, `population.size` | none; an unscored pair is an absent ROW |
| `pval` | the same | permutation p | multiples of 1/`nboot`, filtered at `thresh` | absolute given nboot | `nboot`, `seed.use` | `0` means "not beaten in nboot draws", NOT "vanishingly small" |
| `ligand`, `receptor` | one gene or complex | symbol | the database's own vocabulary | absolute | the database version | a complex is `A_B`, not two rows |
| `interaction_name` | one L-R pair | identifier | database | absolute | database version | — |
| `pathway_name` | the group an L-R pair belongs to | identifier | database | absolute | database version | — |
| `annotation` | the pair's transport class | one of four categories | `Secreted Signaling`, `ECM-Receptor`, `Cell-Cell Contact`, `Non-protein Signaling` | absolute | database version | — |
| `evidence` | literature support | free text carrying accessions (`KEGG: …`, `PMID:…`) | — | absolute | database version | empty string |

**`prob` IS RELATIVE AND THAT IS THE SINGLE MOST CONSEQUENTIAL ROW.** It is computed over the
cells present in the object being scored, so two units' `prob` columns are on two scales. Every
panel drawn from it compares WITHIN a unit and rank-orders across units, and no panel may put
two units' probabilities on one axis. Measured on one unit: 0.000308 to 0.2316, median 0.0115.

**`pval` HAS FIVE VALUES.** At `nboot = 100` and `thresh = 0.05` the delivered column is exactly
{0, 0.01, 0.02, 0.03, 0.04}. It cannot rank and it cannot be corrected as though continuous.

**THE ASSAY COST IS VISIBLE IN `annotation` AND NO PANEL DRAWS IT.** CellChatDB is roughly 60%
secreted signalling; on one nucleus unit the RETURNED edges were 59% ECM-Receptor, 21% cell-cell
contact and **17% secreted**. The caveat this plugin states in prose is measurable in its own
output table, and a class-composition panel would show it rather than assert it.

IT RUNS PER UNIT. An inference pooled over a cohort describes the average of its conditions and
may describe none of them; the host fans it out and this file sees one unit. Every panel is
therefore a statement about that unit alone.
"""

PLUGIN = {
    "api": 1,
    "version": "0.10.1",
    "summary": "cell-cell communication, CellChat's own database and scoring",
    "when_to_use": "you want a second communication method to hold beside the first",
    "wraps": {"tool": "CellChat", "homepage": "https://github.com/jinworks/CellChat",
              "license": "GPL-3.0",
              "cite": "Jin et al., Nat Commun 2021 (CellChat); "
                      "Jin et al., Nat Protoc 2024 (CellChat v2 protocol)"},
    "upstream": {
        "docs": "https://github.com/jinworks/CellChat",
        "read": "2026-08-25",
        "defaults_changed": [
            "identifyOverExpressedGenes(do.fast = FALSE). The default is TRUE and HARD-REQUIRES "
            "`presto`, a Suggests-only package not on CRAN - it stops rather than falling back. "
            "presto is in the requirement for that reason; do.fast is left at its default so the "
            "path everyone else uses is the path tested.",
            "computeCommunProb(type = 'triMean') is CellChat's own default and is kept, but it "
            "is named because it is a strong choice: triMean returns zero for a population where "
            "fewer than 25% of cells express the gene, which is a filter wearing a statistic.",
            # EVERY ARGUMENT BELOW IS PASSED AT ITS OWN DEFAULT. Nothing about the answer changes
            # on the day this was written - what changes is that each is now in `config`, in the
            # plan, in the caveats and in the R command line, instead of being inherited from a
            # function signature nobody in this project had read. Their documented defaults are
            # the ones a reader would least expect if they had not looked.
            "type, trim, population.size, nboot and thresh are now PASSED EXPLICITLY, each at "
            "CellChat's own default. They were inherited, and four of the five change what the "
            "result means: `type` decides the averaging rule and its detection floor (CellChat's "
            "own vignette: 'the number of inferred ligand-receptor pairs clearly depends on the "
            "method for calculating the average gene expression per cell group'); "
            "`population.size = FALSE` is correct for SORTED cells and the documentation says to "
            "set TRUE for unsorted transcriptomes; `nboot = 100` is the p-value's RESOLUTION as "
            "well as its power; `thresh = 0.05` means subsetCommunication has already filtered "
            "the table before this plugin ever sees it.",
            "seed.use = 1L is passed explicitly. It is CellChat's default and the run is a "
            "permutation test: a seed that is implicit is a seed nobody recorded.",
        ],
        "not_used": [
            "netAnalysis_signalingRole and the pattern-learning functions: they are a second "
            "question over the same edges and belong beside this, not inside it.",
            "The spatial mode - this object carries no coordinates. distance.use, "
            "interaction.length, scale.distance and k.min are its arguments and are left alone.",
            "projectData / raw.use = FALSE, which smooths expression over a protein-protein "
            "interaction network before scoring. CellChat offers it for shallow libraries and "
            "says it 'will only introduce very weak communications'; it also makes an edge a "
            "statement about the PPI network as much as about the data, so it is not taken "
            "silently.",
        ],
        "gotchas": [
            "CellChatDB is bundled IN the package, so its version is pinned by the package "
            "version and nothing else records which database produced a result. It is written "
            "into the caveats here for that reason.",
            "A population with very few cells produces unstable probabilities; CellChat's own "
            "min.cells is exposed as config rather than left at its default.",
            # WHAT FAILS SILENTLY, found by reading the documentation rather than the code.
            "`trim` IS IGNORED UNDER THE DEFAULT. computeCommunProb reads it only for "
            "type='truncatedMean' and type='thresholdedMean'; under type='triMean' it is inert. "
            "This plugin passed trim and nothing else for its first version, so a user turning "
            "the one exposed knob got the identical answer back and no warning - the plugin's "
            "own documentation of the knob was the only evidence it did anything.",
            "MOST OF THE DATABASE CAN BE MISSING WITHOUT ANY ERROR. subsetData keeps whatever "
            "signaling genes it finds in the matrix and scores on those, so an object already "
            "reduced to highly-variable genes, or carrying symbols from a different annotation, "
            "returns a smaller table of the same shape. F1_database_coverage is measured "
            "BEFORE the scoring for that reason, and the run says so rather than discovering it "
            "an hour later.",
            "identifyOverExpressedGenes(thresh.p = 0.05, only.pos = TRUE) means a population "
            "whose signaling genes are not over-expressed RELATIVE TO THE OTHERS contributes "
            "nothing. On an object where one population dominates, absence of an edge is partly "
            "a statement about the other populations.",
            "subsetCommunication FILTERS at thresh = 0.05 before returning. The edge table is "
            "not the inferred network, it is the significant part of it, and the unfiltered part "
            "is not written anywhere.",
            "The p-value is a permutation of the group labels, nboot of them, so it is "
            "QUANTISED: only multiples of 1/nboot exist, and at the default of 100 every "
            "surviving edge sits in {0, 0.01, 0.02, 0.03, 0.04}. A reported 0 is an upper bound "
            "set by nboot.",
            "THE ASSAY DOES NOT AFFECT THE INTERACTION CLASSES EQUALLY, and the size of that "
            "is measured on this run rather than quoted: the coverage table is broken down by "
            "CellChat's own annotation class for exactly this reason, and F1 draws it. Measured "
            "on one snRNA sample of a real cohort, SECRETED signalling fell from 37.9% of the "
            "database to 16.6% of the surviving edges while ECM-RECEPTOR rose from 12.9% to "
            "59.1% - a 2.3x depletion against a 4.6x enrichment. Read any pathway-level total "
            "with that in front of it.",
            "The 37.9%/12.9% above are MEASURED from the shipped CellChatDB v2 (mouse: 3,379 "
            "interactions, 1,280 secreted, 435 ECM), not taken from the documentation. This "
            "caveat previously read 'about 60% of CellChatDB is secreted (Jin et al., Nat "
            "Commun 2021)', which is v1's composition of a 2,021-interaction database quoted "
            "beside a pinned v2. CellChat's own v2 vignette is no better: its stated ~17% ECM "
            "and ~13% cell-cell contact are transposed with respect to the data it ships.",
        ],
    },

    # `layout` is OPTIONAL and is only ever DRAWN ON. A communication edge is a claim about
    # two POPULATIONS; drawing the ligand and the receptor on the shared manifold is the only
    # panel on the page that can narrow one, because a ligand confined to one lobe of a sender
    # cluster does not support an arrow drawn from the whole cluster. Absent, the page says so.
    "inject": {"required": ["lognorm", "label", "organism"],
               "optional": ["sample", "layout"]},
    "provides": ["communication"],
    # THE TOOL'S OWN QUANTITIES ARE OUTPUTS, so the report and the figures read CellChat's
    # numbers rather than a second implementation of them. Marked optional because each is
    # written by its own guarded block: one failing quantity costs its table, not the instance,
    # and an instance that produced edges but no centrality is still worth keeping.
    # THE SAVED OBJECT IS AN OUTPUT, so the reuse layer can carry it between runs. Without this
    # the object is written and then invisible to `adopt`: every new run directory starts empty,
    # the guard finds no object, and the inference is paid again - which is the exact cost this
    # was built to remove. Declaring it is what makes the saving worth anything across runs.
    "produces": ["tables/ccc_edges.csv",
                 "[optional] objects/cellchat.rds",
                 "[optional] objects/cellchat.inference.txt",
                 "[optional] tables/cellchat_pathway_prob.csv",
                 "[optional] tables/cellchat_centrality.csv",
                 "[optional] tables/cellchat_rank_net.csv",
                 "[optional] tables/cellchat_net_embedding.csv"],
    "per_unit": "sample",

    "config": {
        "min_cells": {"type": "int", "default": 10, "min": 1,
                      "help": "CellChat's filterCommunication(min.cells): a population smaller "
                              "than this has its edges dropped AFTER scoring. Below it the "
                              "probabilities are unstable"},
        "type": {"type": "str", "default": "triMean",
                 "help": "CellChat's computeCommunProb(type): how a gene is averaged over a "
                         "population. triMean | truncatedMean | thresholdedMean. triMean is the "
                         "tool's own default and produces fewer, stronger interactions; it "
                         "returns ZERO unless 25% of the population's cells express the gene. "
                         "The other two use `trim` as that floor instead"},
        "trim": {"type": "float", "default": 0.1, "min": 0.0, "max": 0.25,
                 "help": "the fraction trimmed from each end before the mean. IGNORED under the "
                         "default type=triMean - CellChat reads it only for truncatedMean and "
                         "thresholdedMean, where it is also the detection floor"},
        "population_size": {"type": "bool", "default": False,
                            "help": "CellChat's population.size. Its own default is FALSE, which "
                                    "is what its documentation prescribes for SORTED cells; it "
                                    "says to set TRUE for unsorted transcriptomes, where "
                                    "abundant populations send collectively stronger signals. "
                                    "It changes the strengths more than the pathways"},
        "nboot": {"type": "int", "default": 100, "min": 1,
                  "help": "label permutations behind every p-value, and therefore its "
                          "RESOLUTION: a p-value can only be a multiple of 1/nboot, so at the "
                          "default an edge reported at 0 means only that 100 permutations did "
                          "not beat it"},
        "thresh": {"type": "float", "default": 0.05, "min": 0.0, "max": 1.0,
                   "help": "CellChat's subsetCommunication(thresh): the edge table is FILTERED "
                           "at this p-value before it is written, which the default does "
                           "silently"},
        "min_coverage": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0,
                         "help": "below this fraction of the database's interactions having "
                                 "every gene present in the object, the run reports `partial`. A "
                                 "gene-subset object or a different symbol set returns a small "
                                 "plausible table rather than failing"},
        "dotplot_n": {"type": "int", "default": 20, "min": 1,
                      "help": "ligand-receptor pairs drawn in the dotplot. The full table is the "
                              "honest artifact; this is for the figure"},
    },

    # DECLARED SO THE TOOL CAN SEE IT. These are R data objects INSIDE the CellChat package,
    # pinned by the commit in `requires.r` - which was chosen for the software, so the database
    # is pinned as a side effect. Nothing here downloads them and nothing can verify them; the
    # point of declaring them is that a plan, a report and `doctor` can name what decided the
    # answer instead of the tool believing this plugin consults nothing.
    "references": {
        "cellchatdb_human": {"tier": "bundled", "organism": "human", "role": "interactions",
                             "package": "CellChat", "cite": "Jin et al., Nat Commun 2021",
                             "source": "https://github.com/jinworks/CellChat",
                             "note": "CellChatDB.human ships inside the CellChat package and is "
                                     "pinned by its commit, not by anything this tool records"},
        "cellchatdb_mouse": {"tier": "bundled", "organism": "mouse", "role": "interactions",
                             "package": "CellChat", "cite": "Jin et al., Nat Commun 2021",
                             "source": "https://github.com/jinworks/CellChat",
                             "note": "CellChatDB.mouse ships inside the CellChat package and is "
                                     "pinned by its commit, not by anything this tool records"},
    },

    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {"anndata": ">=0.12,<0.13", "pandas": ">=2.0,<3", "scipy": ">=1.10",
                     "matplotlib": ">=3.7,<4"},
        "language": "r",
        "r": ["NMF==0.28",
              "immunogenomics/presto@7eb75c4c0a0cf8fc49c705f0975bb3650c51e114",
              "jinworks/CellChat@75253cd0c9e68410e6e721a6d3a0419a1d7e358f"],
        # EVERY DIRECT DEPENDENCY OF EVERY `r:` ENTRY, BY NAME. `remotes` is called with
        # `dependencies = FALSE` on purpose - so that nothing in this environment is chosen at
        # install time - which means a dependency this list forgets is a package `R CMD INSTALL`
        # refuses to build against. It named the first five itself:
        #
        #   ERROR: dependencies 'registry', 'rngtools', 'cluster', 'stringr', 'digest',
        #   'gridBase', 'foreach', 'doParallel', 'reshape2', 'Biobase', 'codetools',
        #   'BiocManager' are not available for package 'NMF'
        #
        # That is the mechanism working - a forgotten dependency surfaces by name, as a line to
        # add here, rather than as an unpinned install nobody recorded. Version is left open for
        # the same reason it is for the other four: `r-base=4.3` is the pin that decides what
        # every `r-*` package resolves against, and inventing versions for forty of them from
        # memory would be a worse claim than none.
        "conda": {
            "r-base": "4.3", "r-matrix": "", "r-ggplot2": "", "r-igraph": "", "r-remotes": "",
            # NMF
            "r-registry": "", "r-rngtools": "", "r-cluster": "", "r-stringr": "", "r-digest": "",
            "r-gridbase": "", "r-foreach": "", "r-doparallel": "", "r-reshape2": "",
            "r-codetools": "", "r-biocmanager": "", "bioconductor-biobase": "",
            # presto
            "r-rcpp": "", "r-data.table": "", "r-dplyr": "", "r-tidyr": "", "r-purrr": "",
            "r-rcpparmadillo": "",
            # CellChat
            "r-future": "", "r-future.apply": "", "r-pbapply": "", "r-irlba": "",
            "r-ggalluvial": "", "r-svglite": "", "r-ggrepel": "", "r-circlize": "",
            "r-cowplot": "", "r-rspectra": "", "r-reticulate": "", "r-sna": "", "r-fnn": "",
            "r-shape": "", "r-patchwork": "", "r-plyr": "", "r-ggpubr": "", "r-ggnetwork": "",
            "r-plotly": "", "r-shiny": "", "r-bslib": "", "r-collapse": "", "r-rcppeigen": "",
            "bioconductor-complexheatmap": "", "bioconductor-biocgenerics": "",
            "bioconductor-biocneighbors": "",
        },
        "channels": ["conda-forge", "bioconda"],
    },

    "cost": "medium", "cores": 4,

    # Measured, not estimated: fitted from this plugin's own instances in one run on a 10-sample mouse single-nucleus cohort (~99k cells). ONE dataset on ONE machine - a starting point that is right for scheduling, not a universal constant. Every run re-fits and prints its own.
    # Fitted from ten per-sample instances.
    "memory_gb_base": 3.1, "memory_gb_per_100k": 5.7,

    # WHAT ITS PAGE SHOULD CONTAIN. Three checks then two answers, and the order is the whole
    # point: every failure this method has returns a well-formed edge table, so the edge table on
    # its own cannot say whether it is one.
    #
    # `shows` is the whole of the reporter's knowledge. It knows no id here and never will.
    # EVERY PLOT CELLCHAT SHIPS, ACCOUNTED FOR. Measured from this plugin's own environment,
    # CellChat 2.2.0.9001: 119 exported functions, 32 plotting or plot-supporting, 29 after the
    # three pure helpers. `scprofile.native` holds the vocabulary; the accounting is checked, and
    # "reimplemented", "not considered" and "dependency missing" are rejected BY NAME.
    #
    # THE HONEST STATE OF THIS PLUGIN TODAY: one is used, and only for its numbers. Twenty-eight
    # are owed. They are listed as `owed` - which is NOT a valid skip reason and will fail the
    # check - because writing a false reason to make a gate green is worse than a red gate.
    "native_plots": {
        # USED - CellChat draws these itself, into the instance's figures/ directory.
        "netAnalysis_computeCentrality": {"use": "tables/cellchat_centrality.csv (numbers only; its plot is not drawn)"},
        "netVisual_circle": {"use": "figures/native_circle_count.png and native_circle_weight.png"},
        "netVisual_heatmap": {"use": "figures/native_heatmap_count.png and native_heatmap_weight.png"},
        "netAnalysis_signalingRole_scatter": {"use": "figures/native_signalingRole_scatter.png"},
        "netAnalysis_signalingRole_heatmap": {"use": "figures/native_signalingRole_heatmap_out.png and _in.png"},
        "netVisual_bubble": {"use": "figures/native_bubble.png"},
        "showDatabaseCategory": {"use": "figures/native_database_category.png"},
        "netVisual_aggregate": {"use": "figures/native_aggregate_circle__<pathway>.png"},
        "netVisual_chord_gene": {"use": "figures/native_chord_gene__<pathway>.png"},
        "netAnalysis_contribution": {"use": "figures/native_contribution__<pathway>.png"},
        "netAnalysis_signalingRole_network": {"use": "figures/native_signalingRole_network__<pathway>.png"},

        # GENUINELY IMPOSSIBLE ON THIS DATA, with the evidence the vocabulary demands.
        "netVisual_spatial": {
            "skip": "not_applicable",
            "evidence": "single-nucleus dissociated data; the object carries no spatial "
                        "coordinates and CellChat's spatial mode was never initialised"},
        "netVisual_chord_cell_internal": {
            "skip": "duplicate_of", "same_as": "netVisual_chord_cell"},

        # OWED. `owed` is NOT a valid reason and `validate` reports every one of these,
        # deliberately: writing a false reason to make a gate green is worse than a red
        # gate. Four of them are pointed straight at a design comparison and are the next
        # to be wired - netVisual_diffInteraction, netAnalysis_diff_signalingRole_scatter,
        # netAnalysis_signalingChanges_scatter and netVisual_chord_cell all need TWO
        # merged objects (mergeCellChat), which this plugin runs one unit at a time and
        # does not yet assemble.
        "netVisual": {"skip": "owed"},
        "netVisual_barplot": {"skip": "owed"},
        "netVisual_individual": {"skip": "owed"},
        "netVisual_hierarchy1": {"skip": "owed"},
        "netVisual_hierarchy2": {"skip": "owed"},
        "netVisual_chord_cell": {"skip": "owed"},
        "netVisual_diffInteraction": {"use": "figures/nativecmp_diffInteraction_{count,weight}.png, per arm pair"},
        "netVisual_embedding": {"skip": "owed"},
        "netVisual_embeddingZoomIn": {"skip": "owed"},
        "netVisual_embeddingPairwise": {"skip": "owed"},
        "netVisual_embeddingPairwiseZoomIn": {"skip": "owed"},
        "netAnalysis_dot": {"skip": "owed"},
        "netAnalysis_river": {"skip": "owed"},
        "netAnalysis_diff_signalingRole_scatter": {"use": "figures/nativecmp_diff_signalingRole.png, per arm pair"},
        "netAnalysis_signalingChanges_scatter": {"use": "figures/nativecmp_signalingChanges__<population>.png"},
        "plotGeneExpression": {"skip": "owed"},
        "StackedVlnPlot": {"skip": "owed"},
    },

    "report": {
        # WHAT THIS PLUGIN CAN SUPPLY, PER PIECE OF EVIDENCE A COMPARISON NEEDS. The needs come
        # from `evidence.NEEDS` and are about the biology, not about CellChat; this is CellChat's
        # own answer to each, best route first.
        #
        # NATIVE IS FIRST ON PRINCIPLE. The wrapped tool's function is the statistic and the
        # encoding its authors chose; a reimplementation is a second implementation to keep in
        # step, and when the two disagree nothing on the page says which was read. Measured in
        # this plugin's own environment, CellChat 2.2.0.9001: 19 of 20 functions named here
        # resolve; only `netVisual_river` does not, and no need routes to it.
        #
        # `abundance_or_intensity` is deliberately ABSENT. CellChat cannot separate them - its
        # probability rises with the number of cells expressing a ligand, so a population that
        # doubles in abundance signals more with no per-cell change. Declaring a route would
        # claim an answer the method does not have; leaving it unrouted makes the gap appear in
        # every specification that asks for it, which is what a paper has to state.
        "provides_evidence": {
            "who_changed": ["native:netVisual_diffInteraction", "host:diff_matrix"],
            "what_carries_it": ["native:rankNet", "host:flow_compare"],
            "direction": ["native:netAnalysis_signalingRole_scatter", "host:role_shift"],
            "presence_or_magnitude": ["host:unit_presence"],
            "specificity": ["native:netVisual_bubble", "host:matrix"],
            "consistency": ["host:unit_presence"],
            "what_was_excluded": ["host:unit_presence"],
        },

        # WHICH OF THIS PLUGIN'S PER-UNIT TABLES CARRIES A NETWORK, so the host can compare
        # ARMS without knowing anything about CellChat. The host pools the units belonging to
        # each arm and draws every contrast the design supports; declaring these columns is the
        # whole interface, and a plugin that emits no network omits this and gets no panels.
        # IT LIVES IN `report` BECAUSE THE REPORTER IS ITS CONSUMER - `report_spec` is what
        # reaches report.json, and a key outside that block is invisible to the reporter no
        # matter how correct it looks in the declaration. Put at the top level first, where it
        # read fine and did nothing.
        "unit_network": {"table": "tables/ccc_edges.csv", "source": "source",
                         "target": "target", "weight": "prob", "group": "pathway_name",
                         # `member` is what a group DECOMPOSES INTO, and declaring it is what
                         # earns the contribution panel. The column is already in this table.
                         "member": "interaction_name"},
        # WHAT MAKES THE UNITS COMPARABLE. Every figure on this page describes ONE unit; these
        # are the numbers the host puts on a shared axis, so a reader sees whether the units
        # agree before reading any single unit's panel as a finding.
        "unit_metrics": [
            {"id": "significant_edges", "question": "how many edges survived the permutation test in this unit?"},
            {"id": "populations", "question": "how many populations did this unit contribute? Edge count scales with the number of ordered pairs, which is quadratic in this."},
        ],
        "figures": [
            # OPTIONAL, and its absence is the loudest thing on the page. Drawing it needs
            # CellChat's database read out interaction by interaction; if that could not be done
            # the run has no way to tell a quiet dataset from a database that never matched it.
            {"id": "F1_database_coverage", "shows": "diagnostic", "required": False,
             "question": "did CellChat's database match the genes in this object at all?",
             "source": "figures/F1_database_coverage.csv",
             "when_absent": "the database could not be read out gene by gene, so how much of it "
                            "was testable here is UNKNOWN. Every failure of this method returns "
                            "a smaller table rather than an error, so without this panel a low "
                            "interaction count below cannot be told apart from a database that "
                            "did not match these gene symbols."},
            {"id": "F2_population_power", "shows": "diagnostic", "required": True,
             "question": "could each population have produced an interaction at all - is what is "
                         "below biology or detection power?",
             "source": "figures/F2_population_power.csv"},
            {"id": "F3_permutation", "shows": "diagnostic", "required": False,
             "question": "how much evidence is behind each edge, given the test is a permutation "
                         "and there were only nboot of them?",
             "source": "figures/F3_permutation.csv",
             "when_absent": "no p-value could be read from the returned table - it is empty, it "
                            "carries no `pval` column, or that column held no number - so "
                            "nothing below has been placed against the permutation floor and any "
                            "ranking rests on the communication probability alone. The run's "
                            "caveats say which of the three it was."},
            {"id": "F4_network", "shows": "result", "required": True,
             "question": "which populations are inferred to signal to which?",
             "source": "figures/F4_network.csv"},
            {"id": "F6_signaling_roles", "shows": "result", "required": False,
             "question": "which populations are net senders and which are net receivers?",
             "source": "figures/F6_signaling_roles.csv",
             "when_absent": "no population carried any outgoing or incoming probability, so "
                            "there is no plane to place them on. That is the same negative "
                            "result F4_network reports, not a drawing failure."},
            {"id": "F7_pathway_roles", "shows": "result", "required": False,
             "question": "for each pathway, which populations send it and which receive it?",
             "source": "figures/F7_pathway_roles.csv",
             "when_absent": "fewer than two pathways carried a non-zero network, so a "
                            "pathway-by-population panel would be a single row. The edge list "
                            "still carries whatever was returned."},
            {"id": "F8_pathway_rank", "shows": "result", "required": False,
             "question": "which pathways carry the most inferred signal in this unit?",
             "source": "figures/F8_pathway_rank.csv",
             "when_absent": "the returned table carries no `pathway_name` column, or every "
                            "pathway summed to zero probability, so there is nothing to rank."},
            {"id": "F9_patterns", "shows": "result", "required": False,
             "question": "do groups of populations use groups of pathways together?",
             "source": "figures/F9_patterns.csv",
             "when_absent": "the population-by-pathway matrix was smaller than 3x3 after "
                            "dropping silent populations, which is below the size a rank-2 "
                            "factorisation can be checked at. Nothing was fitted rather than "
                            "fitting something unverifiable."},
            {"id": "F10_pathway_similarity", "shows": "result", "required": False,
             "question": "which pathways act between the same populations as each other?",
             "source": "figures/F10_pathway_similarity.csv",
             "when_absent": "fewer than four pathways, or fewer than three surviving the "
                            "shared-nearest-neighbour mask - too few points for a placement to "
                            "mean anything."},
            {"id": "F5_dotplot", "shows": "result", "required": False,
             "question": "which ligand-receptor pairs carry the inferred signal, and between "
                         "which populations?",
             "source": "figures/F5_dotplot.csv",
             "when_absent": "there is no pair to draw: either no interaction survived scoring and "
                            "the p-value threshold, or the returned table lacks a column the "
                            "panel needs (source, target, prob, interaction_name) or a readable "
                            "communication probability. Read the first case as a negative result "
                            "of the inference - checked against the panels above - and not as a "
                            "figure that failed; the run's caveats say which case this was."},
        ],
        # THE PAIRING. Both answer the same question from a different database and a different
        # score, and the published comparison of the two families (Dimitrov et al., Nat Commun
        # 2022) found that method and resource each strongly change the predictions. Declared so
        # the reporter can name the missing half as an absence; neither plugin can draw the
        # comparison alone, because neither can read the other's table.
        "reads_with": ["liana"],
    },

    "cannot_show": [
        "NO INTERACTION IS OBSERVED, for the same reason as any expression-only method: this is "
        "co-expression of a ligand and a receptor in two populations.",
        "ITS DATABASE IS ITS OWN. Agreement with another method is evidence; disagreement is a "
        "finding about the databases as much as about the cells.",
        "Scores are not comparable with another method's - they are on different scales, and "
        "only the ranking can be compared.",
        "triMean returns zero for a population where fewer than a quarter of cells express the "
        "gene, so an absent interaction can be a sparsity threshold rather than a biological "
        "absence.",
        "THE NUMBER OF INFERRED PAIRS IS A PROPERTY OF THE AVERAGING RULE. CellChat's own "
        "vignette states that it 'clearly depends on the method for calculating the average gene "
        "expression per cell group', so a count of interactions is not a quantity to compare "
        "across runs that used different `type` or `trim`.",
        "THE P-VALUE IS QUANTISED BY nboot. It is a permutation of the group labels and can only "
        "take multiples of 1/nboot; a reported 0 means no permutation beat the observation in "
        "nboot draws, which is an upper bound and not a measured probability.",
        "An edge count is not comparable BETWEEN POPULATIONS without reading the diagnostics: a "
        "population's cell count sets how much it can clear the averaging floor, and "
        "population.size decides whether abundance is modelled at all.",
        "Around 60% of the database is SECRETED signaling, whose transcripts are the least well "
        "captured on nuclei. An absent secreted interaction is as consistent with the "
        "preparation as with the biology, and the two classes cannot be compared to each other.",
        "The result describes ONE UNIT. It is not a cohort statement, and a difference between "
        "two units' tables has not been tested for one.",
    ],
}

#: CellChat ships one database per species. An organism it has none for is refused rather than
#: silently scored against the human one.
_DB = {"human": "CellChatDB.human", "mouse": "CellChatDB.mouse"}

#: The averaging rules `computeCommunProb` accepts, and the FRACTION OF A POPULATION'S CELLS a
#: gene must be detected in for that rule to return anything but zero. triMean approximates a 25%
#: truncated mean, so it is zero unless a quarter of the group expresses the gene; the other two
#: use `trim` as the floor. Anything not here is passed through and CellChat decides.
_MEAN_TYPES = {"triMean": 0.25, "truncatedMean": None, "thresholdedMean": None}

#: Sender -> receiver pairs the dotplot DRAWS before it stops, while `tables/ccc_edges.csv` keeps
#: every one. It is a property of the page, not of any dataset: the count of pairs grows as the
#: SQUARE of the populations - nine of them is eighty-one - and one pair per ROW at 6 pt is about
#: 5 mm of page each. It was a bare `15` inside the drawing function, which is a cap on what the
#: reader is shown that nothing in `config`, nothing in the caption and nothing in the source
#: table could see.
#:
#: *A pair was a COLUMN until the panel was transposed, and the reason it had to be is the reason
#: this constant is small: a pair of annotation paths is the longest label on the page, and as a
#: rotated column label fifteen of them took half the height of the figure.*
_DOT_PAIRS = 15

#: STEP ONE, AND IT IS CHEAP. Reads the database and writes it out interaction by interaction,
#: with every complex expanded into its subunits, so the coverage of this object can be measured
#: BEFORE the scoring is paid for. It touches no expression data.
_R_DB = r'''
suppressMessages(library(CellChat))
args <- commandArgs(trailingOnly = TRUE)
db_name <- args[1]; out <- args[2]

db <- get(db_name)
inter <- db$interaction
cplx <- db$complex

# A LIGAND MAY BE A COMPLEX, NOT A GENE. CellChatDB names a complex in the ligand or receptor
# column and holds its subunits in db$complex; taking the column at face value asks whether a
# gene called e.g. "IL12 complex" is in var_names, which it never is - and every multi-subunit
# interaction is then counted as absent.
expand <- function(nm) {
  if (!is.null(cplx) && nm %in% rownames(cplx)) {
    s <- as.character(unlist(cplx[nm, ], use.names = FALSE))
    s <- s[!is.na(s) & nzchar(s)]
    if (length(s)) return(s)
  }
  nm
}
join <- function(v) vapply(as.character(v),
                           function(n) paste(expand(n), collapse = ";"),
                           character(1), USE.NAMES = FALSE)

nm <- if ("interaction_name" %in% colnames(inter)) as.character(inter$interaction_name) else rownames(inter)
pw <- if ("pathway_name" %in% colnames(inter)) as.character(inter$pathway_name) else ""
an <- if ("annotation" %in% colnames(inter)) as.character(inter$annotation) else ""

d <- data.frame(interaction_name = nm, pathway_name = pw, annotation = an,
                ligand_genes = join(inter$ligand),
                receptor_genes = join(inter$receptor),
                stringsAsFactors = FALSE)
write.csv(d, out, row.names = FALSE)
cat("database:", nrow(d), "interactions,",
    length(unique(unlist(strsplit(paste(d$ligand_genes, d$receptor_genes, sep = ";"), ";")))),
    "genes\n")
'''

#: STEP TWO: the scoring. Every argument that changes the meaning of the answer is passed on the
#: command line rather than inherited from a signature, so the run's own log records it.
_R_RUN = r'''
suppressMessages({library(CellChat); library(Matrix)})
args <- commandArgs(trailingOnly = TRUE)
mtx <- args[1]; meta_f <- args[2]; db_name <- args[3]
min_cells <- as.integer(args[4]); trim <- as.numeric(args[5]); out <- args[6]
mean_type <- args[7]; pop_size <- as.logical(args[8]); nboot <- as.integer(args[9])
thresh <- as.numeric(args[10])

X <- as(Matrix::readMM(mtx), "CsparseMatrix")
meta <- read.csv(meta_f, row.names = 1, stringsAsFactors = FALSE)
rownames(X) <- read.csv(paste0(mtx, ".genes"), header = FALSE)[[1]]
colnames(X) <- rownames(meta)

# ---------------------------------------------------------------------------------------------
# THE INFERENCE IS EXPENSIVE AND WAS THROWN AWAY EVERY TIME. This script computed the CellChat
# object, wrote a table out of it and exited, so the object itself never survived - and every
# change to a FIGURE cost a full re-inference: measured at 2 minutes 41 seconds and a 7.5 GB peak
# per unit, on an expression matrix of 173 MB written to disk to feed it, times fourteen units.
# Roughly forty minutes of compute discarded to redraw a plot.
#
# So the object is saved, and reused when the INFERENCE inputs are unchanged. The guard is a
# digest of the things that actually determine the object - the expression matrix, the metadata,
# the database and every inference parameter - and NOT of the plotting code, which is the whole
# point: changing a plot must not invalidate an inference.
objdir <- file.path(dirname(dirname(out)), "objects")
dir.create(objdir, showWarnings = FALSE, recursive = TRUE)
rds <- file.path(objdir, "cellchat.rds")
stampf <- file.path(objdir, "cellchat.inference.txt")
stamp <- paste(tools::md5sum(mtx), tools::md5sum(meta_f), db_name, mean_type, trim,
               pop_size, nboot, thresh, min_cells, sep = "|")

cc <- NULL
if (file.exists(rds) && file.exists(stampf) &&
    identical(trimws(readLines(stampf, warn = FALSE))[1], unname(stamp))) {
  cc <- tryCatch({ v <- readRDS(rds); cat("reusing the saved CellChat object; inference skipped\n"); v },
                 error = function(e) { cat("saved object unreadable:", conditionMessage(e), "\n"); NULL })
}

if (is.null(cc)) {
cc <- createCellChat(object = X, meta = meta, group.by = "label")
cc@DB <- get(db_name)
cc <- subsetData(cc)
cc <- identifyOverExpressedGenes(cc)
cc <- identifyOverExpressedInteractions(cc)
cc <- computeCommunProb(cc, type = mean_type, trim = trim,
                        population.size = pop_size, nboot = nboot, seed.use = 1L)
cc <- filterCommunication(cc, min.cells = min_cells)
}

df <- subsetCommunication(cc, thresh = thresh)
write.csv(df, out, row.names = FALSE)
cat("edges:", nrow(df), "\n")

# ---------------------------------------------------------------------------------------------
# CELLCHAT'S OWN DOWNSTREAM QUANTITIES, WRITTEN OUT RATHER THAN RECOMPUTED DOWNSTREAM.
#
# Everything past this point used to be re-derived in Python from the edge table above:
# pathway-level probability, centrality, ranked information flow, network similarity. Each was a
# faithful transcription and each was still a SECOND implementation of a statistic the wrapped
# tool already computes - which is the one thing a wrapper must not do, because when the two
# disagree there is nothing on the page that says which was read.
#
# Measured before this was written: 19 of 20 CellChat functions named by those transcriptions
# resolve in this very environment, CellChat 2.2.0.9001. Nothing was unavailable; nobody had
# asked.
#
# Each block is wrapped so that one failing quantity costs its own table and not the instance:
# a plugin that dies after computing the edges would throw away the expensive part.
`%||%` <- function(a, b) if (is.null(a)) b else a
side <- function(name) file.path(dirname(out), paste0("cellchat_", name, ".csv"))
try_write <- function(name, expr) {
  ok <- tryCatch({ v <- expr; write.csv(v, side(name), row.names = TRUE); TRUE },
                 error = function(e) { cat("native", name, "FAILED:", conditionMessage(e), "\n")
                                       FALSE })
  if (ok) cat("native", name, "written\n")
}

cc <- computeCommunProbPathway(cc)
cc <- aggregateNet(cc)
cc <- netAnalysis_computeCentrality(cc, slot.name = "netP")

# SAVED HERE, NOT EARLIER. The first version wrote the object straight after inference, before
# the pathway probabilities, the aggregate network and the centrality were added to it. A reused
# object was therefore missing all three, and CellChat's own comparison functions refused it:
# "Please run `netAnalysis_computeCentrality` to compute the network centrality scores for each
# dataset seperately". An object is worth reusing only in the state the next step needs.
writeLines(unname(stamp), stampf)
saveRDS(cc, rds)
cat("saved the CellChat object for reuse:", rds, "\n")

# ---------------------------------------------------------------------------------------------
# CELLCHAT'S OWN PLOTS, DRAWN BY CELLCHAT. Until now this script wrote no figure at all - every
# panel was a Python reimplementation - and of the 29 plotting functions CellChat exports exactly
# one was called, for its numbers. The instruction is to use the tool's own plot; a
# reimplementation is legitimate only where it corrects a NAMED defect in the upstream encoding,
# and is declared as such in `native_plots`.
#
# Each is guarded: one failing plot costs its own file, not the instance. Each writes into the
# instance's `figures/` directory beside the host-drawn panels, with a `native_` prefix so a
# reader can tell at a glance which encoding they are looking at.
figdir <- file.path(dirname(dirname(out)), "figures")
dir.create(figdir, showWarnings = FALSE, recursive = TRUE)
npng <- function(name, expr, w = 1800, h = 1500, res = 200) {
  path <- file.path(figdir, paste0("native_", name, ".png"))
  ok <- tryCatch({
    grDevices::png(path, width = w, height = h, res = res)
    on.exit(grDevices::dev.off(), add = TRUE)
    print(expr)
    TRUE
  }, error = function(e) { cat("native plot", name, "FAILED:", conditionMessage(e), "\n"); FALSE })
  if (ok && file.exists(path)) cat("native plot", name, "written\n")
  else if (file.exists(path)) unlink(path)
}

groups <- levels(cc@idents)
ngrp <- length(groups)

npng("circle_count", {
  netVisual_circle(cc@net$count, vertex.weight = as.numeric(table(cc@idents)),
                   weight.scale = TRUE, label.edge = FALSE,
                   title.name = "interactions")
})
npng("circle_weight", {
  netVisual_circle(cc@net$weight, vertex.weight = as.numeric(table(cc@idents)),
                   weight.scale = TRUE, label.edge = FALSE,
                   title.name = "interaction strength")
})
npng("heatmap_count", netVisual_heatmap(cc, measure = "count", color.heatmap = "Blues"))
npng("heatmap_weight", netVisual_heatmap(cc, measure = "weight", color.heatmap = "Blues"))
npng("signalingRole_scatter", netAnalysis_signalingRole_scatter(cc))
npng("signalingRole_heatmap_out",
     netAnalysis_signalingRole_heatmap(cc, pattern = "outgoing", width = 10, height = 12))
npng("signalingRole_heatmap_in",
     netAnalysis_signalingRole_heatmap(cc, pattern = "incoming", width = 10, height = 12))
npng("bubble", netVisual_bubble(cc, sources.use = seq_len(ngrp), targets.use = seq_len(ngrp),
                                remove.isolate = TRUE), w = 2600, h = 2000)
npng("database_category", showDatabaseCategory(cc@DB))

# per-pathway, on the strongest pathway this unit has - `netVisual_aggregate` and
# `netAnalysis_contribution` are pathway-scoped, so they need one named
pw <- tryCatch({
  s <- sort(sapply(dimnames(cc@netP$prob)[[3]], function(k) sum(cc@netP$prob[, , k])),
            decreasing = TRUE)
  names(s)[1]
}, error = function(e) NA_character_)
if (!is.na(pw)) {
  cat("native pathway-scoped plots use:", pw, "\n")
  npng(paste0("aggregate_circle__", pw), netVisual_aggregate(cc, signaling = pw, layout = "circle"))
  npng(paste0("chord_gene__", pw),
       netVisual_chord_gene(cc, signaling = pw, lab.cex = 0.6, legend.pos.y = 30))
  npng(paste0("contribution__", pw), netAnalysis_contribution(cc, signaling = pw))
  npng(paste0("signalingRole_network__", pw),
       netAnalysis_signalingRole_network(cc, signaling = pw, width = 12, height = 4,
                                         font.size = 10))
}

# pathway x (sender, receiver) probability, CellChat's own computeCommunProbPathway
try_write("pathway_prob", {
  P <- cc@netP$prob
  d <- do.call(rbind, lapply(seq_len(dim(P)[3]), function(k) {
    m <- P[, , k]
    data.frame(pathway = dimnames(P)[[3]][k],
               source = rep(rownames(m), times = ncol(m)),
               target = rep(colnames(m), each = nrow(m)),
               prob = as.vector(m))
  }))
  d[d$prob > 0, ]
})

# centrality per pathway and population, CellChat's own netAnalysis_computeCentrality
# NOT EVERY MEASURE IS A NAMED VECTOR OF THE SAME LENGTH. The first version assumed it was and
# died on "arguments imply differing number of rows: 1, 0, 8" - a centrality slot can hold an
# empty measure, and one empty entry took the whole table with it. Each measure is now built
# alone and the empty ones are dropped, so a pathway missing one measure still contributes the
# rest.
try_write("centrality", {
  cen <- cc@netP$centr
  rows <- list()
  for (pw in names(cen)) {
    m <- cen[[pw]]
    for (meas in names(m)) {
      v <- m[[meas]]
      if (is.null(v) || length(v) == 0L || is.null(names(v))) next
      rows[[length(rows) + 1L]] <- data.frame(
        pathway = pw, measure = meas, population = names(v),
        value = as.numeric(v), stringsAsFactors = FALSE)
    }
  }
  if (length(rows) == 0L) stop("no centrality measure had a named value")
  do.call(rbind, rows)
})

# ranked information flow, CellChat's own rankNet (return.data, nothing drawn)
try_write("rank_net", {
  r <- rankNet(cc, mode = "single", stacked = FALSE, do.stat = FALSE, return.data = TRUE)
  as.data.frame(r$signaling.contribution %||% r)
})

# network similarity and its embedding, CellChat's own computeNetSimilarity + netEmbedding
# THE EMBEDDING IS TRIED THROUGH THE PYTHON UMAP THIS ENVIRONMENT ALREADY HAS, not through an
# R package it does not. `netEmbedding(umap.method = "uwot")` failed with "there is no package
# called uwot", and adding one would re-resolve an environment shared by seven plugins - which
# this project has already paid for once, turning one blocked plugin into seven. `umap-learn` is
# the reticulate route to the umap the host stack ships. If that is unavailable too the block
# fails alone and F10 remains the declared reimplementation it already is.
try_write("net_embedding", {
  cc2 <- computeNetSimilarity(cc, type = "functional")
  cc2 <- netEmbedding(cc2, type = "functional", umap.method = "umap-learn")
  e <- cc2@netP$similarity$functional$dr[["single"]]
  data.frame(pathway = rownames(e), dim1 = e[, 1], dim2 = e[, 2])
})
'''


# ------------------------------------------------------------------------------------ helpers

def _genes(cell):
    """The gene symbols in one `a;b;c` field of the database dump. `[]` for an empty field."""
    s = "" if cell is None else str(cell)
    if not s or s.lower() == "nan":
        return []
    return [g for g in (p.strip() for p in s.split(";")) if g and g.lower() != "na"]


def _nnz_per_gene(m):
    """Cells with a STRICTLY POSITIVE value, per column of a CSR matrix.

    Not `getnnz(axis=0)`, which counts STORED entries. A matrix that has been through a tool
    leaving explicit zeros in its sparsity pattern reports those genes as detected in every cell
    that stores one, and both numbers built on this - which genes exist at all, and what fraction
    of a population clears CellChat's averaging floor - are then overstatements with nothing on
    the page able to reveal them. Counted off the data array, so nothing the size of the matrix is
    allocated to find out.
    """
    import numpy as np
    return np.bincount(m.indices[m.data > 0], minlength=m.shape[1])


def _wrap_tick(s, limit=18):
    """A long tick label folded onto two lines at its own separator. Unchanged when short.

    An interaction name is `LIGAND_RECEPTOR` or `LIGAND_SUBUNIT_SUBUNIT`, and rotated ninety
    degrees a thirty-character one is over a centimetre of page per column - which under
    `constrained` comes out of the DATA area, not out of the margin. Folded at the separator
    nearest its middle it costs width, which a double-column figure has, instead of height,
    which it does not.

    NOTHING IS TRUNCATED. A tick label that no longer names exactly one thing is worse than a
    tall one, and an ellipsis on a gene symbol is a label a reader cannot look up.
    """
    s = str(s)
    if len(s) <= limit:
        return s
    mid = len(s) / 2.0
    for sep in ("_", "-", ":", " ", "."):
        at = [i for i, ch in enumerate(s) if ch == sep]
        if at:
            i = min(at, key=lambda k: abs(k - mid))
            if 0 < i < len(s) - 1:
                return s[:i] + "\n" + s[i + 1:]
    return s


def _read_db(path, log):
    """CellChat's database, one row per interaction, or None when R could not write it.

    None is a legitimate answer and is treated as one everywhere below: the coverage panel is
    declared optional precisely so that its absence can be reported as the fact it is.
    """
    import pandas as pd
    try:
        if not path.exists():
            return None
        d = pd.read_csv(path)
    except Exception as e:                                                # noqa: BLE001
        log(f"  database dump not readable ({type(e).__name__}: {e})")
        return None
    need = {"interaction_name", "ligand_genes", "receptor_genes"}
    if not need <= set(d.columns) or not len(d):
        log(f"  database dump has columns {sorted(d.columns)}; expected {sorted(need)}")
        return None
    return d


def _floor_for(mean_type, trim):
    """The fraction of a population's cells a gene must be detected in to survive the averaging.

    Returns (floor, why). This is not a threshold this plugin applies - it is a property of
    CellChat's own aggregation, and the only way to see it is to compute it.
    """
    known = _MEAN_TYPES.get(mean_type, "unknown")
    if known == 0.25:
        return 0.25, (f"type={mean_type} approximates a 25% truncated mean, so a gene detected "
                      f"in fewer than 25% of a population's cells averages to zero there")
    if mean_type == "truncatedMean":
        return float(trim), (f"type={mean_type} trims {100 * float(trim):.0f}% from each end "
                             f"before averaging, so a gene detected in fewer than "
                             f"{100 * float(trim):.0f}% of a population's cells averages to zero "
                             f"there")
    if mean_type in _MEAN_TYPES:
        return float(trim), (f"type={mean_type} zeroes a gene detected in fewer than "
                             f"{100 * float(trim):.0f}% of a population's cells before "
                             f"averaging, so it contributes nothing there")
    return float(trim), (f"type={mean_type} is not one this plugin knows the floor of; {trim} is "
                         f"assumed from `trim` and may not be what CellChat applied")


# ------------------------------------------------------------------------------------ figures
#
#   coverage     how much of the database was testable on this object at all. First, because
#                every other number on the page is conditional on it.
#   power        per population: cells, how much of the database clears the averaging floor, and
#                how many edges came back. The three together say whether an edge count is a
#                statement about signalling or about sampling.
#   permutation  where the p-values sit against the resolution nboot allows.
#   network      population to population, the answer in counts.
#   dotplot      the ligand-receptor pairs behind it. CellChat's own bubble plot.
#
# Every one of them is drawn at a journal column width by `scprofile.figure`, and none of them
# uses colour as the only channel for a category.

# ---------------------------------------------------------------- derived from the edge list
#
# EVERYTHING BELOW IS RECOMPUTED FROM `tables/ccc_edges.csv`, IN PYTHON, AND NEEDS NO SECOND R
# CALL. Read against the CellChat source (v2.2.0.9001) rather than its tutorials, because the
# tutorials describe the object and the object is not what crosses the R/Python boundary here.
#
#   aggregateNet             count  = apply(prob > 0, c(1,2), sum) after prob[pval >= thresh] <- 0
#                            weight = apply(prob,     c(1,2), sum) after the same masking
#   computeCommunProbPathway plain sum of the significant LR probabilities within each pathway
#   centrality outdeg/indeg  igraph::strength(G, "out"/"in") = weighted row / column sums
#
# The edge list is already p-value filtered and carries `pathway_name`, so each of those is a
# groupby away. What it does NOT carry is the non-significant probabilities, and nothing here
# needs them: every CellChat function above masks them to zero first.


def _pops_and_matrices(df, pops=None):
    """(populations, count, weight) - `aggregateNet`, recomputed.

    `count` is the number of significant L-R pairs for an ordered cell pair; `weight` is their
    summed communication probability. Self-signalling is KEPT on the diagonal, as CellChat keeps
    it everywhere except its spatial plot.
    """
    import numpy as np

    pops = list(pops) if pops is not None else sorted(set(df["source"]) | set(df["target"]))
    ix = {p: i for i, p in enumerate(pops)}
    k = len(pops)
    count = np.zeros((k, k), dtype=float)
    weight = np.zeros((k, k), dtype=float)
    for s, t, pr in zip(df["source"], df["target"], df["prob"]):
        if s in ix and t in ix:
            count[ix[s], ix[t]] += 1.0
            weight[ix[s], ix[t]] += float(pr)
    return pops, count, weight


def _pathway_array(df, pops, pathways=None):
    """(pathways, K x K x P) - `computeCommunProbPathway`, recomputed.

    Pathways are ordered by DESCENDING total probability, which is what CellChat does and what
    every downstream index assumes - `netP$pathways` is a ranking, not the database order.
    """
    import numpy as np

    ix = {p: i for i, p in enumerate(pops)}
    have = [p for p in df["pathway_name"].dropna().unique()]
    paths = list(pathways) if pathways is not None else sorted(have)
    pix = {p: i for i, p in enumerate(paths)}
    arr = np.zeros((len(pops), len(pops), len(paths)), dtype=float)
    for s, t, pr, pw in zip(df["source"], df["target"], df["prob"], df["pathway_name"]):
        if s in ix and t in ix and pw in pix:
            arr[ix[s], ix[t], pix[pw]] += float(pr)
    order = np.argsort(arr.sum(axis=(0, 1)))[::-1]
    return [paths[i] for i in order], arr[:, :, order]


def _information_centrality(net):
    """Stephenson-Zelen information centrality, rescaled to sum 1 - CellChat's "Influencer".

    `sna::infocent(net, diag=TRUE, rescale=TRUE, cmode="lower")`. Implemented rather than
    approximated: C = (D - A + J)^-1 with A the symmetrised weights, D its degree diagonal and
    J all-ones; then I_i = 1 / (C_ii + mean_j C_jj - 2 * mean_j C_ij). CellChat wraps this in a
    `tryCatch` that returns zeros on failure, so a zero row there is indistinguishable from a
    measured zero; here a failure is reported as an absence instead.
    """
    import numpy as np

    a = (np.asarray(net, dtype=float) + np.asarray(net, dtype=float).T) / 2.0
    n = a.shape[0]
    if n < 2 or not np.isfinite(a).all() or a.sum() <= 0:
        return None
    d = np.diag(a.sum(axis=1))
    try:
        c = np.linalg.inv(d - a + np.ones((n, n)))
    except np.linalg.LinAlgError:
        return None
    diag = np.diag(c)
    t = diag.sum()
    r = c.sum(axis=1)
    denom = diag + (t - 2.0 * r) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        info = np.where(denom > 0, 1.0 / denom, 0.0)
    tot = info.sum()
    return info / tot if tot > 0 else None


def _flow_betweenness(net):
    """Max-flow betweenness - CellChat's "Mediator", via `sna::flowbet`.

    The total maximum flow that passes THROUGH each node, summed over all other ordered pairs:
    for every (s, t) the max-flow value is computed with the node present and with it deleted,
    and the difference is credited to it. Returns None where it cannot be computed, so the row
    can be named as absent rather than drawn as zero.
    """
    import numpy as np

    a = np.asarray(net, dtype=float)
    n = a.shape[0]
    if n < 3 or a.sum() <= 0:
        return None
    try:
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import maximum_flow
    except Exception:                                                     # noqa: BLE001
        return None
    # maximum_flow needs integer capacities; scale so the smallest positive edge is ~1.
    pos = a[a > 0]
    scale = 1e6 / pos.max() if pos.size else 1.0
    cap = np.rint(a * scale).astype(np.int64)
    np.fill_diagonal(cap, 0)

    def _flow(mat, s, t):
        try:
            return int(maximum_flow(csr_matrix(mat), s, t).flow_value)
        except Exception:                                                 # noqa: BLE001
            return 0

    out = np.zeros(n, dtype=float)
    for v in range(n):
        drop = cap.copy()
        drop[v, :] = 0
        drop[:, v] = 0
        tot = 0
        for s in range(n):
            for t in range(n):
                if s == t or s == v or t == v:
                    continue
                tot += max(0, _flow(cap, s, t) - _flow(drop, s, t))
        out[v] = tot / scale
    return out


def _centrality(arr, pathways):
    """{pathway: {measure: vector}} - `netAnalysis_computeCentrality`, recomputed.

    Four measures, named as CellChat names them on its own panels:
      Sender     outdeg  = weighted OUT-degree = row sum of the pathway matrix
      Receiver   indeg   = weighted IN-degree  = column sum
      Mediator   flowbet = max-flow betweenness
      Influencer info    = Stephenson-Zelen information centrality, rescaled to sum 1
    Self-signalling is on the diagonal and igraph's `strength` counts it in BOTH directions, so
    it is counted here in both too.
    """
    import numpy as np

    out = {}
    for i, pw in enumerate(pathways):
        net = arr[:, :, i]
        if net.sum() <= 0:
            continue
        out[pw] = {"outdeg": net.sum(axis=1), "indeg": net.sum(axis=0),
                   "flowbet": _flow_betweenness(net), "info": _information_centrality(net)}
    return out


def _nmf_lee(v, k, *, seed=0, iters=800):
    """Lee-Seung multiplicative-update NMF with an NNDSVD start - CellChat's exact setup.

    `NMF::nmf(data, rank = k, method = 'lee', seed = 'nndsvd')`. Written out in numpy rather
    than taken from scikit-learn, because scikit-learn is NOT in this plugin's declared
    `requires`: it is present in the built environments only as somebody else's transitive
    dependency, and a plugin that works because of a package it never declared is a plugin that
    breaks on the next machine. numpy arrives with pandas, scipy and anndata, all of which ARE
    declared.

    NNDSVD makes the fit deterministic, which is why CellChat needs no seed argument here.
    """
    import numpy as np

    v = np.asarray(v, dtype=float)
    v[v < 0] = 0.0
    m, n = v.shape
    # --- NNDSVD initialisation (Boutsidis & Gallopoulos 2008), as `seed='nndsvd'`
    u, sig, vt = np.linalg.svd(v, full_matrices=False)
    w = np.zeros((m, k))
    h = np.zeros((k, n))
    w[:, 0] = np.sqrt(sig[0]) * np.abs(u[:, 0])
    h[0, :] = np.sqrt(sig[0]) * np.abs(vt[0, :])
    for j in range(1, min(k, len(sig))):
        x, y = u[:, j], vt[j, :]
        xp, xn = np.maximum(x, 0), np.maximum(-x, 0)
        yp, yn = np.maximum(y, 0), np.maximum(-y, 0)
        xpn, xnn = np.linalg.norm(xp), np.linalg.norm(xn)
        ypn, ynn = np.linalg.norm(yp), np.linalg.norm(yn)
        if xpn * ypn >= xnn * ynn:
            u_, v_, s_ = xp / (xpn or 1), yp / (ypn or 1), xpn * ypn
        else:
            u_, v_, s_ = xn / (xnn or 1), yn / (ynn or 1), xnn * ynn
        w[:, j] = np.sqrt(sig[j] * s_) * u_
        h[j, :] = np.sqrt(sig[j] * s_) * v_
    eps = np.finfo(float).eps
    w[w < eps] = eps
    h[h < eps] = eps
    if seed:
        # RANDOM RESTARTS MUST ACTUALLY RESTART. NNDSVD is deterministic, so perturbing it
        # slightly left every run in the same basin and the consensus was perfect at every rank:
        # measured, cophenetic = 1.000 for k = 3..7, which makes the rank criterion decorative -
        # it would have picked the first of six identical maxima and reported a chosen k.
        # `NMF::nmfEstimateRank` reseeds randomly for exactly this reason, so the stability runs
        # do too; the final fit keeps NNDSVD and stays reproducible.
        rng = np.random.RandomState(seed)
        scale = float(np.sqrt(v.mean() / k)) if v.mean() > 0 else 1.0
        w = rng.rand(m, k) * scale
        h = rng.rand(k, n) * scale
    # --- Lee & Seung multiplicative updates, Frobenius objective
    for _ in range(iters):
        h *= (w.T @ v) / ((w.T @ w @ h) + eps)
        w *= (v @ h.T) / ((w @ h @ h.T) + eps)
    return w, h


def _patterns(arr, pathways, pops, direction="outgoing", k=None, k_range=range(2, 8)):
    """(W_rows, H_cols, k, cophenetic curve) - `identifyCommunicationPatterns`, recomputed.

    The input is K x P, max-normalised PER PATHWAY exactly as CellChat does
    (`sweep(data, 2L, apply(data, 2, max), '/')`), with all-zero cell groups dropped - which
    silently shortens W, so the surviving rows are returned beside it.

    `k` is chosen by the criterion CellChat's `selectK` plots rather than hard-coded: the
    cophenetic correlation of the consensus over restarts. Returned WITH the curve, because a
    decomposition whose rank was picked silently is a decomposition nobody can check.
    """
    import numpy as np

    m = arr.sum(axis=1 if direction == "outgoing" else 0)     # K x P
    keep = m.sum(axis=1) > 0
    m = m[keep]
    rows = [p for p, kp in zip(pops, keep) if kp]
    col_max = m.max(axis=0)
    m = np.divide(m, col_max, out=np.zeros_like(m), where=col_max > 0)
    if m.shape[0] < 3 or m.shape[1] < 3:
        return None, None, None, None

    def _coph(kk, n_run=20):
        from scipy.cluster.hierarchy import cophenet, linkage
        from scipy.spatial.distance import squareform
        con = np.zeros((m.shape[0], m.shape[0]))
        for seed in range(n_run):
            w, _h = _nmf_lee(m, kk, seed=seed, iters=200)
            lab = w.argmax(axis=1)
            con += (lab[:, None] == lab[None, :]).astype(float)
        con /= n_run
        d = 1.0 - con
        np.fill_diagonal(d, 0.0)
        try:
            cond = squareform(d, checks=False)
            z = linkage(cond, "average")
            return float(np.corrcoef(cophenet(z), cond)[0, 1])
        except Exception:                                                 # noqa: BLE001
            return float("nan")

    curve = {}
    if k is None:
        for kk in k_range:
            if kk < m.shape[0]:
                curve[kk] = _coph(kk)
        good = [(kk, v) for kk, v in curve.items() if v == v]
        k = max(good, key=lambda t: t[1])[0] if good else 2
        # A RULE THAT ALWAYS RETURNS THE BOUNDARY IS NOT A SELECTION. Taking the maximum of the
        # cophenetic curve picks the smallest k offered whenever the curve is MONOTONE
        # DECREASING over the range tried - which it was on a real unit, where every k from 2 to
        # 7 declined and the panel reported "rank chosen: k = 2" as though a criterion had
        # discriminated. It had not: it had hit the left edge.
        #
        # The choice is unchanged, because the maximum is still the right rule where the curve
        # has an interior peak. What changes is that the panel now SAYS which of the two
        # happened, and that is the difference between a selection and an artefact of the range.
        _ks = sorted(curve)
        _vals = [curve[kk] for kk in _ks if curve[kk] == curve[kk]]
        _monotone = len(_vals) > 2 and all(b <= a + 1e-12 for a, b in zip(_vals, _vals[1:]))
        _at_edge = bool(good) and k == min(kk for kk, _v in good)
        curve["_boundary"] = 1.0 if (_monotone and _at_edge) else 0.0
    w, h = _nmf_lee(m, k, seed=0)
    w = np.divide(w, w.sum(axis=1, keepdims=True),
                  out=np.zeros_like(w), where=w.sum(axis=1, keepdims=True) > 0)   # rows sum 1
    h = np.divide(h, h.sum(axis=0, keepdims=True),
                  out=np.zeros_like(h), where=h.sum(axis=0, keepdims=True) > 0)   # cols sum 1
    return (w, rows), (h, list(pathways)), k, curve


def _snn(mat, k, prune=1.0 / 15.0):
    """CellChat's `buildSNN`, over the ROWS of a similarity matrix.

    Euclidean kNN on the rows, shared-neighbour count `s`, Jaccard `s / (2k - s)`, then every
    entry below `prune.SNN` set to zero. Separated from `_similarity` because it is the step
    that actually isolates a pathway, and a reader checking that claim should be able to find
    it on its own.
    """
    import numpy as np

    n = mat.shape[0]
    d = np.sqrt(((mat[:, None, :] - mat[None, :, :]) ** 2).sum(-1))
    knn = np.zeros((n, n))
    for i in range(n):
        knn[i, np.argsort(d[i], kind="stable")[:k]] = 1.0
    shared = knn @ knn.T
    snn = shared / (2.0 * k - shared)
    snn[snn < prune] = 0.0
    return snn


def _similarity(arr, pathways):
    """(similarity, kept, dropped) - `computeNetSimilarity(type="functional")`, recomputed.

    Jaccard over the BINARISED sender-receiver adjacency of each pathway, which is what CellChat
    computes and is worth stating plainly: it discards magnitude entirely. Two pathways are
    "functionally similar" when they use the same cell pairs, however strongly.

    CellChat then multiplies by a shared-nearest-neighbour mask, and `netEmbedding` refuses to
    place any pathway whose MASKED off-diagonal similarities are all zero - with no message.
    Those are the most distinctive pathways in the object. They are returned as `dropped` so a
    page can name them instead of quietly embedding 65 points and captioning it 68.

    THE MASK IS THE WHOLE POINT, and this function did not apply it. Until it did, `dropped` was
    computed from the raw Jaccard graph - which is dense, so nothing is ever isolated and the
    list came back empty on every real object. A returned list that is structurally always
    empty is worse than no list: the page prints "none dropped" and the reader believes it.
    Measured on one real cohort, the mask drops three of sixty-eight where the raw graph
    dropped none.
    """
    import numpy as np

    g = (arr > 0).astype(float)
    n = g.shape[2]
    sim = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            inter = float((g[:, :, i] * g[:, :, j]).sum())
            union = float((g[:, :, i] + g[:, :, j] - g[:, :, i] * g[:, :, j]).sum())
            sim[i, j] = sim[j, i] = inter / union if union > 0 else 0.0
    if n < 3:
        return sim, list(pathways), []
    # CellChat documents `k = ceiling(sqrt(P)) + 1`. The clamp to [1, n-1] is OURS: k neighbours
    # cannot exceed the points available, and an unclamped k silently returns a saturated graph
    # in which nothing can be isolated - the same failure this function already had once.
    k = max(1, min(n - 1, int(np.ceil(np.sqrt(n))) + 1))
    masked = sim * _snn(sim, k)
    off = masked.sum(1) - np.diag(masked)
    keep = [i for i in range(n) if off[i] > 1e-12]
    dropped = [pathways[i] for i in range(n) if off[i] <= 1e-12]
    return masked[np.ix_(keep, keep)], [pathways[i] for i in keep], dropped


def _fig_coverage(ctx, db, var_names, detected, edges, thresh):
    """The funnel from CellChat's database to the returned table. True when it was drawn.

    False when the database could not be read; the caller reports the panel as absent rather than
    quoting a coverage it does not have.
    """
    import numpy as np
    import pandas as pd
    if db is None:
        return False
    F, plt = ctx.figure, ctx.plot()

    present, seen = set(map(str, var_names)), set(map(str, detected))
    allg = [_genes(l) + _genes(r)
            for l, r in zip(db["ligand_genes"], db["receptor_genes"])]
    in_object = pd.Series([bool(g) and all(x in present for x in g) for g in allg])
    in_data = pd.Series([bool(g) and all(x in seen for x in g) for g in allg])

    stages = [("in CellChatDB", pd.Series([True] * len(db))),
              ("every gene present in the object", in_object),
              ("every gene detected in >=1 cell", in_data)]
    returned_stage = False
    if edges is not None and "interaction_name" in getattr(edges, "columns", []):
        ret = db["interaction_name"].astype(str).isin(
            set(edges["interaction_name"].astype(str)))
        # A ZERO OVERLAP WITH A NON-EMPTY TABLE IS A NAME MISMATCH, not a result, and drawing it
        # as the last bar of a funnel would report the run as having returned nothing.
        if bool(ret.any()) or not len(edges):
            stages.append((f"returned at p < {thresh:g}", ret))
            returned_stage = True
        else:
            ctx.log("  the edge table's interaction names do not match the database dump's; "
                    "the returned stage is left off the coverage panel")

    n0 = len(db)
    classes = ([str(c) for c in sorted(set(db["annotation"].astype(str)))
                if c and c.lower() != "nan"] if "annotation" in db.columns else [])
    rows = []
    for label, m in stages:
        row = {"n_interactions": int(m.sum()), "fraction_of_database": float(m.mean())}
        for c in classes:
            row[f"n_{c}"] = int((m & (db["annotation"].astype(str) == c)).sum())
        rows.append((label, row))
    src = pd.DataFrame([r for _, r in rows],
                       index=pd.Index([l for l, _ in rows], name="stage"))

    y = np.arange(len(rows))
    vals = [r["n_interactions"] for _, r in rows]
    # TWO PANELS, BECAUSE ONE CHANNEL CANNOT CARRY BOTH CLAIMS. The counts panel shows the
    # attrition - the whole database narrowing to what came back - and on a real arm the last
    # bar was 3% of the first, which makes the CLASS COMPOSITION INSIDE IT unreadable. That
    # composition is the point: this plugin's caveats state that the classes are not equally
    # measurable here and quote the shift, and the panel that was supposed to show it drew it
    # in a sliver two pixels wide. Found by opening the image on a real cohort.
    #
    # So the right panel normalises every stage to 100%. The counts say how much survived; the
    # shares say WHAT survived, and the second is invisible in the first by construction.
    stacked = bool(classes) and len(classes) <= len(F.CATEGORY_COLOURS)
    if stacked:
        fig, axes = plt.subplots(1, 2, figsize=(F.DOUBLE, max(1.9, 0.42 * len(rows) + 1.15)),
                                 layout="constrained", sharey=True,
                                 gridspec_kw={"width_ratios": [1.55, 1.0]})
        ax, ax2 = axes
    else:
        fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.9, 0.42 * len(rows) + 1.15)),
                               layout="constrained")
        ax2 = None
    # THE WHOLE DATABASE BEHIND EVERY BAR. A funnel is a set of fractions of ONE thing, and
    # without the ghost the narrowing - which is the entire content of the panel - has to be
    # reconstructed by reading four bar lengths against a tick axis.
    ax.barh(y, [n0] * len(rows), height=0.72, color=F.GREY, zorder=1)
    # SPLIT BY CellChat's OWN ANNOTATION CLASS, because the classes are NOT equally measurable
    # here and this plugin's caveats say so: around 60% of the database is secreted signalling,
    # whose transcripts are the ones a nuclear preparation retains least. A single bar reports a
    # coverage that could be carried entirely by the contact classes and look identical. The
    # per-class counts were already computed for the source table and drawn nowhere.
    if stacked:
        left = np.zeros(len(rows))
        left2 = np.zeros(len(rows))
        _tot = np.array([max(1.0, float(r["n_interactions"])) for _, r in rows])
        for i, c in enumerate(classes):
            seg = np.array([float(r[f"n_{c}"]) for _, r in rows])
            ax.barh(y, seg, left=left, height=0.72, color=F.CATEGORY_COLOURS[i], zorder=2,
                    label=c)
            left += seg
            share = 100.0 * seg / _tot
            ax2.barh(y, share, left=left2, height=0.72, color=F.CATEGORY_COLOURS[i], zorder=2)
            # THE NUMBER, ON THE SEGMENT, WHERE IT FITS. A share panel a reader has to measure
            # against a tick axis gives back a fifth of the precision the number already has.
            for yi, sh, lf in zip(y, share, left2):
                if sh >= 9.0:
                    ax2.text(lf + sh / 2.0, yi, f"{sh:.0f}", va="center", ha="center",
                             fontsize=5.4, color="white", zorder=3)
            left2 += share
        fig.legend(loc="outside lower center", ncol=min(3, len(classes)), fontsize=5.5,
                   handlelength=1.0, handleheight=0.9, columnspacing=1.2, handletextpad=0.4,
                   frameon=False)
    else:
        ax.barh(y, vals, height=0.72, color="#0072B2", zorder=2)
    # THE LABEL GOES INSIDE ONCE THE BAR IS LONG. It sat to the right of the bar unconditionally,
    # which is why the axis had to run to 1.32x the largest value - a third of the panel width
    # spent on nothing, and the first bar's label off the end of the data anyway.
    for yi, v in zip(y, vals):
        inside = v > 0.72 * n0
        ax.text(v - 0.012 * n0 if inside else v + 0.012 * n0, yi,
                f"{v:,} ({100 * v / max(1, n0):.0f}%)", va="center",
                ha="right" if inside else "left", fontsize=6,
                color="white" if inside and stacked else F.INK, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([l for l, _ in rows])
    if returned_stage:
        # THE LAST BAR IS THE RESULT AND THE ONES ABOVE IT ARE THE DATABASE NARROWING TO IT. It
        # used to be said with a second bar colour, applied to `rows[-1]` WHETHER OR NOT the
        # returned stage was drawn - so on exactly the runs where the join failed, the "result"
        # colour was painted onto a diagnostic stage and the panel claimed a result it had just
        # declined to compute.
        ax.get_yticklabels()[-1].set_fontweight("bold")
        ax.axhline(len(rows) - 1.5, color=F.INK, lw=0.5, ls=":", zorder=4)
    ax.invert_yaxis()
    ax.set_xlim(0, n0)
    ax.set_xlabel("interactions")
    if ax2 is not None:
        ax2.set_xlim(0, 100)
        ax2.set_xlabel("% of that stage")
        ax2.set_xticks([0, 25, 50, 75, 100])
        ax2.tick_params(labelsize=6)
        if returned_stage:
            ax2.axhline(len(rows) - 1.5, color=F.INK, lw=0.5, ls=":", zorder=4)
    # FOUR OR FIVE TICKS, NOT NINE. Every bar carries its own count and its own percentage, so
    # the axis is a rough scale and a dense one is only ink.
    from matplotlib.ticker import MaxNLocator
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    # THE CAPTION DESCRIBES THE BARS THAT ARE THERE. The last stage is dropped whenever the edge
    # table's interaction names do not join to the dump's - which is precisely the failure this
    # panel exists to expose - and a caption naming a gap after a bar nobody can see is how a
    # reader comes to believe they read a funnel that was never drawn.
    tail = ("; the gap after it is the averaging rule, the over-expression filter and the "
            "permutation test together. " if returned_stage else
            ". THE RETURNED STAGE IS NOT DRAWN: the edge table's interaction names did not join "
            "to the database dump's, so how many of these interactions came back cannot be "
            "counted here - read that from tables/ccc_edges.csv instead. ")
    ctx.emit_figure(
        "F1_database_coverage", fig,
        caption=("How much of CellChat's own database could be tested on this object, stage by "
                 "stage. A complex is counted only when EVERY subunit is present. The second bar "
                 "is the one to read first: none of this method's failures raises an error, and "
                 "an object carrying a different symbol set, or already reduced to "
                 "highly-variable genes, collapses there and still returns a well-formed table. "
                 "The gap between the second and third bars is sequencing depth" + tail
                 + "Every bar counts DISTINCT interactions, so the last one is not the number of "
                   "edges in tables/ccc_edges.csv - one interaction returns once per ordered pair "
                   "of populations that carries it. The grey behind each bar is the whole "
                   "database, so a bar is read as a fraction of it rather than against the axis."
                 + (" Each bar is split by CellChat's own annotation class: the classes are not "
                    "equally measurable in every preparation - around 60% of the database is "
                    "secreted signalling - so a coverage figure carried by one class is a "
                    "different result from the same figure spread across all of them. Exact "
                    "per-class counts are in the source table." if stacked
                    else " Per-class counts are in the source table.")),
        source=src)
    return True


def _fig_population_power(ctx, names, n_cells, sent, received, above_floor, min_cells, floor_why,
                          n_sentinel_cells=0):
    """Cells, detectable database, and edges - per population, side by side.

    The pairing is the panel. An edge count alone cannot say whether a quiet population is quiet
    or merely small, and these three columns are the only things that can.

    `n_sentinel_cells` is said on the panel rather than only in a caveat: this is the figure a
    reader counts populations off, and a per-population figure that does not say what it set
    aside reads as the whole object.
    """
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()

    # SENT AND RECEIVED SEPARATELY, then their sum. A population that only listens and one that
    # only speaks are different findings, and a single total cannot tell them apart - nor can it
    # be read at all for a self-loop, which is one edge appearing in both columns.
    d = {"n_cells": [int(n_cells.get(p, 0)) for p in names],
         "edges_as_sender": [int(sent.get(p, 0)) for p in names],
         "edges_as_receiver": [int(received.get(p, 0)) for p in names]}
    d["n_significant_edges"] = [a + b for a, b in
                                zip(d["edges_as_sender"], d["edges_as_receiver"])]
    # PRESENT OR ABSENT, NEVER PRESENT AND EMPTY. When the database dump failed there is no
    # detectable-fraction to report, and a column of blanks would read as a measured zero.
    #
    # AND THE NAME CARRIES ITS DENOMINATOR. It was `frac_db_genes_above_floor`, measured over the
    # database genes PRESENT IN THIS OBJECT and labelled as though it were over the database: on
    # an object matching a third of CellChatDB a population read 0.9 while two thirds of the
    # database was never testable at all, and F1 is the only panel that said so.
    if above_floor is not None:
        d["frac_present_db_genes_above_floor"] = [float(above_floor[p]) for p in names]
    src = pd.DataFrame(d, index=pd.Index(names, name="population"))
    src = src.sort_values("n_cells", ascending=False)

    # `constrained`, because the shared y axis carries population names and the right-hand
    # panels carry their own x labels; without it the two collide the moment a name is long.
    n_panels = 3 if above_floor is not None else 2
    fig, axs = plt.subplots(1, n_panels,
                            figsize=(F.DOUBLE, max(2.0, 0.26 * len(src) + 1.35)),
                            sharey=True, squeeze=False, layout="constrained")
    axs = list(axs[0])
    y = np.arange(len(src))
    below = src["n_cells"].to_numpy() < float(min_cells)
    # A BAR IS NOT ALLOWED TO BECOME A SLAB. `0.72` of a row is right at ten populations and
    # absurd at two, where the panel has a minimum height and the rows divide it between them.
    bh = min(0.72, 0.12 * len(src) + 0.26)

    # (a) CELLS, ON A LOG AXIS, and that is the whole panel working or not working. Population
    # sizes inside one object routinely span three orders of magnitude, and on a linear axis
    # every population anywhere near min.cells - which is the entire subject of this panel - is
    # a sliver indistinguishable from the axis line. The populations the reader most needs to
    # see were the ones the scale erased.
    ax = axs[0]
    cells = np.maximum(src["n_cells"].to_numpy(dtype=float), 0.0)
    ax.barh(y, cells, height=bh, color=np.where(below, "#D55E00", "#0072B2"))
    ax.set_xscale("log")
    ax.set_xlim(0.7, max(2.0, float(cells.max())) * 2.2)
    ax.axvline(float(min_cells), color=F.INK, ls="--", lw=0.6, zorder=3)
    # ANCHORED TO THE AXES, NOT TO A ROW NUMBER. At `-0.9` in data coordinates this label sat
    # just above the top bar on a twelve-population panel and a long way off the top of the
    # figure on a two-population one, because a data unit is a row and rows are not a fixed size.
    ax.text(float(min_cells), 1.005, f" min.cells = {min_cells:,}",
            transform=ax.get_xaxis_transform(), fontsize=5.5, color=F.INK, ha="left", va="bottom")
    ax.set_xlabel("cells  (log scale)")
    # A LOG AXIS DRAWS NINE MINOR TICKS PER DECADE BY DEFAULT, which over four decades is a comb
    # of forty tick marks under a panel of twelve bars.
    ax.tick_params(axis="x", which="minor", length=0)
    # NAMED ON THE FIGURE, NOT ONLY IN THE CAPTION. These populations have no edges in the result
    # for a reason that is technical, and this is the only figure that can say so.
    import matplotlib.patches as mpatch
    keys = ([mpatch.Patch(color="#D55E00", label="below min.cells: edges dropped after scoring")]
            if below.any() else [])

    # (b) THE AVERAGING FLOOR, when the database could be read out.
    if above_floor is not None:
        ax = axs[1]
        ax.barh(y, src["frac_present_db_genes_above_floor"].to_numpy(), height=bh,
                color="#E69F00")
        ax.set_xlim(0, 1)
        ax.set_xlabel("fraction of the database genes\nPRESENT here above the averaging floor")

    # (c) SENT AND RECEIVED, SIDE BY SIDE IN THE BAR. The docstring above says a population that
    # only listens and one that only speaks are different findings - and the panel then drew
    # their SUM, so the one thing it named as the distinction was the one thing it hid. The
    # stacked total is unchanged, so nothing that was readable here has been dropped.
    ax = axs[-1]
    s_arr = src["edges_as_sender"].to_numpy(dtype=float)
    r_arr = src["edges_as_receiver"].to_numpy(dtype=float)
    ax.barh(y, s_arr, height=bh, color="#009E73")
    ax.barh(y, r_arr, left=s_arr, height=bh, color="#56B4E9")
    ax.set_xlabel("significant interactions\n(sent + received)")
    # ONE KEY, BELOW THE WHOLE FIGURE, FOR BOTH PANELS THAT NEED ONE. Inside the axes there is
    # no corner that is reliably free: populations are sorted by cells and not by edges, so the
    # longest bar can be any row, and on a two-population panel every corner has a bar in it -
    # which is where a key pinned to one landed on top of the data.
    keys += [mpatch.Patch(color="#009E73", label="interactions sent"),
             mpatch.Patch(color="#56B4E9", label="interactions received")]
    fig.legend(handles=keys, loc="outside lower center", ncol=min(3, len(keys)), fontsize=5.5,
               handlelength=1.0, handleheight=0.9, columnspacing=1.4, handletextpad=0.4,
               frameon=False)

    for i, ax in enumerate(axs):
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        # PANEL LETTERS. Three panels a caption refers to in order are three panels a reader has
        # to be able to point at.
        ax.set_title("abc"[i], loc="left", fontweight="bold", fontsize=8, pad=3)
    # SHORTENED TO THE SHORTEST UNAMBIGUOUS TAIL, as F4 and F5 already do. These are annotation
    # PATHS, and at full length they took a third of a double-column figure's width for text that
    # repeats the same prefix down every row. The full path stays in the source table.
    _short = F.short_labels(list(src.index))
    axs[0].set_yticks(y)
    axs[0].set_yticklabels([_short[p] for p in src.index])
    axs[0].invert_yaxis()

    rho = ""
    if len(src) >= 4:
        try:
            from scipy.stats import spearmanr
            r = spearmanr(src["n_cells"].to_numpy(),
                          src["n_significant_edges"].to_numpy()).statistic
            if r == r:                                              # not NaN
                rho = (f" Across the {len(src)} populations here, cell count and interaction "
                       f"count rank-correlate at rho = {r:+.2f}.")
        except Exception:                                                 # noqa: BLE001
            rho = ""
    # THE CAPTION DESCRIBES THE PANELS THAT ARE THERE. The middle one exists only when the
    # database could be read out, and a caption naming three panels over two is how a reader
    # comes to believe they saw a check that was never drawn.
    middle = ("(b) what fraction of the database genes PRESENT IN THIS OBJECT clear the "
              "averaging floor in it - which is not a fraction of the database, and F1 is the "
              "panel that says how much of the database is present at all - and "
              if above_floor is not None else "")
    # THE PANELS CARRY LETTERS, SO THE CAPTION USES THEM - and the last letter depends on whether
    # the middle panel exists at all.
    last = "c" if above_floor is not None else "b"
    ctx.emit_figure(
        "F2_population_power", fig,
        caption=("Per population, sorted by size: (a) how many cells it has, on a LOG axis - "
                 "population sizes span orders of magnitude and the ones near min.cells are the "
                 "subject of this panel; " + middle
                 + f"({last}) how many significant interactions came back, split into those it "
                   f"sent and those it received. "
                 + (floor_why + ". " if above_floor is not None else "")
                 + "The dashed line in (a) is min.cells, below which CellChat drops a "
                   "population's edges after scoring; populations below it are drawn in a second "
                   f"colour and their absence from the result is technical. A population low in "
                   f"(a) cannot be read as quiet in ({last}) - it was never able to speak. A "
                   f"self-loop is one edge and is counted in both halves of a ({last}) bar." + rho
                 + f" Population names are shortened to their shortest unambiguous tail; the full "
                   f"paths are in the source table. The {n_sentinel_cells:,} cells carrying an "
                   f"annotator sentinel are not a population, were not handed to CellChat, and "
                   f"are not drawn here."),
        source=src)


def _fig_permutation(ctx, edges, nboot, thresh):
    """Where the p-values sit against the resolution the permutation test allows."""
    import numpy as np
    import pandas as pd
    if edges is None or "pval" not in getattr(edges, "columns", []) or not len(edges):
        return False
    # COERCED, NOT CAST. `np.asarray(..., dtype=float)` raises on a column R wrote as text - and
    # a panel that raises takes the whole run's results with it, for a diagnostic.
    pv = pd.to_numeric(edges["pval"], errors="coerce").to_numpy(dtype=float)
    pv = pv[np.isfinite(pv)]
    if not len(pv):
        return False
    F, plt = ctx.figure, ctx.plot()

    vals, counts = np.unique(pv, return_counts=True)
    src = pd.DataFrame({"n_edges": counts},
                       index=pd.Index(vals, name="pval")).sort_index()
    floor = 1.0 / max(nboot, 1)
    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.74), layout="constrained")
    # A p-VALUE OF ZERO IS CENSORED, NOT SMALL, AND IT IS USUALLY THE TALLEST BAR HERE. In one
    # hue with the rest it reads as the left tail of a distribution, which is precisely the
    # reading the caption then has to argue the reader out of - and the figure is looked at
    # before the caption is read, if the caption is read at all. Its own colour says it first.
    MEASURED, CENSORED = "#0072B2", "#D55E00"
    if len(vals) <= 30:
        # THE VALUES ARE DISCRETE, so they are drawn discrete. A histogram of five attainable
        # values with twenty bins invents a distribution the test cannot produce.
        w = floor * 0.62
        ax.bar(vals, counts, width=w, zorder=2,
               color=[CENSORED if v <= 0 else MEASURED for v in vals])
        # THE COUNT ON ITS OWN BAR. A handful of bars have room for their own numbers, and a
        # reader who has to measure a bar against a tick in order to quote it will quote it wrong.
        for v, c in zip(vals, counts):
            ax.text(v, c, f"{c:,}", ha="center", va="bottom", fontsize=5.5, color=F.INK)
    else:
        ax.hist(pv, bins=30, color=MEASURED, zorder=2)
    # BOTH REFERENCE LINES, AND BOTH NAMED ON THE PANEL. There was one dashed line and nothing
    # on the figure saying what it marked. The threshold matters as much as the resolution does:
    # it is why nothing is drawn to its right, which otherwise reads as an absence of edges
    # rather than as the filter that removed them before this plugin saw the table.
    for x, lab in ((floor, f"1/nboot = {floor:g}\nresolution"),
                   (float(thresh), f"thresh = {thresh:g}\ntable filtered here")):
        ax.axvline(x, color=F.INK, ls="--", lw=0.6, zorder=1)
        # THE THRESHOLD LABEL READS INWARD. It marks the right-hand end of the axis, so anchored
        # left it hangs off the page and only `bbox_inches="tight"` was keeping it on.
        right = x >= float(thresh)
        ax.text(x, 1.01, (lab + " ") if right else (" " + lab),
                transform=ax.get_xaxis_transform(), ha="right" if right else "left",
                va="bottom", fontsize=5, color=F.INK, linespacing=1.2)
    ax.set_xlabel("permutation p-value")
    ax.set_ylabel("edges")
    ax.set_xlim(-1.2 * floor, max(float(thresh), float(vals.max())) + 0.7 * floor)
    ax.margins(y=0.14)
    # TICKS ON THE VALUES THE TEST CAN ACTUALLY RETURN. The automatic locator put -0.01 and 0.06
    # on the axis of a quantity that is a probability and is bounded by the threshold.
    if len(vals) <= 8:
        ax.set_xticks(sorted(set(vals.tolist() + [float(thresh)])))
    if float(vals.min()) <= 0:
        # THE SECOND HUE NEEDS A KEY ON THE PANEL. A colour that means something and is explained
        # only in the caption is a colour most readers will read as decoration.
        import matplotlib.patches as mpatch
        ax.legend(handles=[mpatch.Patch(color=CENSORED,
                                        label=f"p = 0, i.e. p < {floor:g}: censored by nboot"),
                           mpatch.Patch(color=MEASURED, label="resolved by the permutations")],
                  loc="upper right", bbox_to_anchor=(1.0, 0.94), fontsize=5.5,
                  handlelength=1.0, handleheight=0.9, borderaxespad=0.15, labelspacing=0.35,
                  frameon=False)
    ctx.emit_figure(
        "F3_permutation", fig,
        caption=(f"The p-values behind the edges that survived. The test permutes the group "
                 f"labels {nboot:,} times, so a p-value can only be a multiple of "
                 f"{floor:g} - the left dashed line - and every bar here is at or below the "
                 f"{thresh:g} threshold the table was filtered at, which is the right one. The "
                 f"bar at zero is drawn in a second colour because it is not a small probability: "
                 f"it is an upper bound, meaning no permutation of the labels reached the observed "
                 f"value in {nboot:,} draws. More permutations would separate those edges; nothing "
                 f"else will."),
        source=src)
    return True


def _fig_network(ctx, edges, names):
    """Population to population: the answer, in counts, with the silent pairs left visible."""
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()

    n = len(names)
    counts = pd.DataFrame(0, index=names, columns=names, dtype=int)
    prob = pd.DataFrame(0.0, index=names, columns=names, dtype=float)
    if edges is not None and len(edges) and {"source", "target"} <= set(edges.columns):
        pv = (pd.to_numeric(edges["prob"], errors="coerce").fillna(0.0).to_numpy()
              if "prob" in edges.columns else [0.0] * len(edges))
        for src_p, tgt_p, p in zip(edges["source"].astype(str), edges["target"].astype(str), pv):
            if src_p in counts.index and tgt_p in counts.columns:
                counts.at[src_p, tgt_p] += 1
                prob.at[src_p, tgt_p] += float(p)
    # BUILT LONG DIRECTLY, not by `stack()`. Every ordered pair gets a row whether or not it
    # carries an edge, which is the same reason the heatmap draws every population: a pair that
    # is absent from the table and a pair that scored zero read identically otherwise.
    src = pd.DataFrame([{"source": a, "target": b,
                         "n_significant_edges": int(counts.at[a, b]),
                         "summed_probability": float(prob.at[a, b])}
                        for a in names for b in names]).set_index(["source", "target"])

    # ROWS AND COLUMNS IN THE SAME ORDER, BY TOTAL ACTIVITY. Alphabetical order over annotation
    # PATHS is arbitrary once the paths are shortened for the axis - the reader sees a sequence
    # with no rule - and it scatters whatever block structure the matrix has. One order for both
    # axes is not optional: it is what makes the diagonal mean "within a population".
    M0 = counts.to_numpy()
    order = list(np.argsort(-(M0.sum(axis=1) + M0.sum(axis=0)), kind="stable"))
    disp = [names[i] for i in order]
    M = counts.loc[disp, disp].to_numpy()

    # SHORTENED TO THE SHORTEST UNAMBIGUOUS TAIL. These categories are annotation paths, sixty
    # characters before a real name is reached, and rotated ninety degrees they took three
    # quarters of the figure height - squeezing the data into a strip. The full path stays in
    # the source table.
    _short = F.short_labels(disp)
    # ADAPTIVE, SO A CELL STAYS BIG ENOUGH TO SEE, AND THE LABELS GET THEIR OWN ROOM. Fixed at
    # the single-column width, twelve populations gave 4 mm cells and twenty would have given
    # 2 mm - and because `constrained` fits the tick labels FIRST, a long annotation path was
    # taken out of the matrix rather than out of the page. Measured off the labels that will
    # actually be drawn: at 6 pt a character is about 0.042 in, and at 45 degrees it contributes
    # 0.7 of that to the height.
    _lab = max((len(v) for v in _short.values()), default=8)
    band = 0.35 + 0.030 * _lab
    side = min(F.DOUBLE - band, max(F.SINGLE, 0.19 * n + 0.9))
    fig, ax = plt.subplots(figsize=(side + band, side + band), layout="constrained")
    # ZERO IS NOT THE BOTTOM OF THE COLOUR RAMP, IT IS OFF IT. The caption promises that a silent
    # row is visible rather than missing, and under viridis from vmin=0 a silent pair was dark
    # purple - the same reading as one, two or three interactions at print size. The one thing
    # the panel was built to show was the one thing its colour scale could not say.
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("#F0F0F0")
    im = ax.imshow(np.ma.masked_where(M == 0, M), cmap=cmap, aspect="equal",
                   vmin=1, vmax=max(1, int(M.max())))
    ax.set_xticks(np.arange(n))
    ax.set_yticks(np.arange(n))
    ax.set_xticklabels([_short[p] for p in disp], rotation=45, ha="right",
                       rotation_mode="anchor")
    ax.set_yticklabels([_short[p] for p in disp])
    ax.set_xlabel("receiver")
    ax.set_ylabel("sender")
    ax.tick_params(length=0)
    # CELL BOUNDARIES. A twelve by twelve block of flat colour has no landmarks, and tracing a
    # cell back to its row and its column is the only operation a reader performs on it.
    ax.set_xticks(np.arange(n + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(n + 1) - 0.5, minor=True)
    ax.grid(which="minor", color="white", lw=0.5)
    ax.tick_params(which="minor", length=0)
    # THE DIAGONAL IS A DIFFERENT CLAIM AND THE CAPTION ALREADY SAYS SO. Outlined, it can be
    # found; unmarked, the reader has to count cells in from both axes to locate it.
    # DRAWN TWICE, LIGHT UNDER DARK. A single dark outline vanishes on the dark end of viridis -
    # which is where a quiet diagonal cell sits, and a quiet diagonal is a thing a reader looks
    # for - and a single light one vanishes at the bright end.
    for i in range(n):
        ax.add_patch(plt.Rectangle((i - 0.5, i - 0.5), 1, 1, fill=False, ec="white", lw=1.3,
                                   zorder=4))
        ax.add_patch(plt.Rectangle((i - 0.5, i - 0.5), 1, 1, fill=False, ec=F.INK, lw=0.5,
                                   zorder=5))
    # THE NUMBERS THEMSELVES, while they still fit. A count is an exact quantity and a colour is
    # not; above this many populations the digits collide and colour is all there is.
    if n <= 14:
        fs = 5.0 if n <= 10 else 4.2
        for i in range(n):
            for j in range(n):
                v = int(M[i, j])
                if not v:
                    continue
                ax.text(j, i, f"{v:,}", ha="center", va="center", fontsize=fs,
                        color="white" if v < 0.6 * max(1, M.max()) else "#101010", zorder=6)
    for sp in ax.spines.values():
        sp.set_visible(False)
    # NO COLOURBAR WHEN NOTHING IS ON IT. On a unit where no pair returned a significant
    # interaction the whole matrix is grey, and the bar still drew - reading 0.92, 0.96, 1.00 on
    # a count of interactions, a scale with no cell on it and no attainable value on it either.
    # A scale a reader can read is a scale a reader will use.
    any_edge = int(M.max()) > 0
    if any_edge:
        cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
        cb.outline.set_visible(False)
        cb.set_label("significant interactions")
        # AN INTEGER QUANTITY GETS INTEGER TICKS. A colourbar reading 0.0, 2.5, 5.0 on a count
        # of interactions offers the reader a value the quantity cannot take.
        from matplotlib.ticker import MaxNLocator
        if int(M.max()) <= 1:
            cb.set_ticks([1])
        else:
            cb.ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
    import matplotlib.patches as mpatch
    fig.legend(handles=[mpatch.Patch(facecolor="#F0F0F0", edgecolor="#C8C8C8", lw=0.5,
                                     label="no significant interaction")],
               loc="outside lower left", fontsize=5.5, handlelength=1.0, handleheight=0.9,
               frameon=False)
    ctx.emit_figure(
        "F4_network", fig,
        caption=("Inferred communication from each sender population (rows) to each receiver "
                 "(columns), counted as significant ligand-receptor interactions. Rows and "
                 "columns are in the SAME order, sorted by total activity, so the diagonal is "
                 "signalling within a population - which is inferred exactly as the off-diagonal "
                 "is, and is no more direct; it is outlined for that reason. Every population is "
                 "drawn whether or not it participates, and a pair with no significant "
                 "interaction is left off the colour scale in flat grey rather than given the "
                 "bottom of it - so a silent row is visible rather than missing, and a silent row "
                 "is the case the diagnostics above exist to explain. Names are shortened to "
                 "their shortest unambiguous tail. Summed communication probability for every "
                 "pair, and the full paths, are in the source table."
                 + ("" if any_edge else
                    " NO PAIR IN THIS UNIT RETURNED A SIGNIFICANT INTERACTION, so every cell is "
                    "grey and there is no colour scale to draw. That is a result of the "
                    "inference and not a figure that failed; the diagnostics above say which of "
                    "its causes applies here.")),
        source=src)


def _fig_dotplot(ctx, edges, top_n, nboot, thresh):
    """CellChat's bubble plot: sender -> receiver pairs against ligand-receptor interactions.

    Colour is the communication probability; dot size RANKS the permutation p-value. Pairs are on
    the y axis because a pair of annotation paths is the longest label this page has, and a
    horizontal label costs margin width rather than figure height.
    """
    import numpy as np
    import pandas as pd
    if edges is None or not len(edges):
        return False
    need = {"source", "target", "prob"}
    if not need <= set(edges.columns):
        return False
    name_col = "interaction_name" if "interaction_name" in edges.columns else None
    if name_col is None:
        return False

    e = edges.copy()
    e["pair"] = e["source"].astype(str) + " -> " + e["target"].astype(str)
    e["interaction"] = e[name_col].astype(str)
    e["prob"] = pd.to_numeric(e["prob"], errors="coerce")
    e = e[np.isfinite(e["prob"])]
    if not len(e):
        return False

    keep_i = list(e.groupby("interaction")["prob"].max().nlargest(int(top_n)).index)
    sub = e[e["interaction"].isin(keep_i)]
    # HOW MANY PAIRS THERE WERE, BEFORE THE CAP, so the caption can say what the figure dropped.
    # The cap is a page constraint and it is named; it was a bare literal here.
    n_pairs_all = int(sub["pair"].nunique())
    keep_p = list(sub["pair"].value_counts().head(_DOT_PAIRS).index)
    sub = sub[sub["pair"].isin(keep_p)]
    if not len(sub):
        return False
    # Both axes ordered by their strongest edge: a dotplot whose axes are in database order is a
    # dotplot nobody can read down.
    pairs = list(sub.groupby("pair")["prob"].max().sort_values(ascending=False).index)
    inter = list(sub.groupby("interaction")["prob"].max().sort_values(ascending=False).index)
    yi = {p: i for i, p in enumerate(pairs)}
    xi = {t: i for i, t in enumerate(inter)}

    floor = 1.0 / max(int(nboot), 1)
    p_col = "pval" in sub.columns
    pv = (pd.to_numeric(sub["pval"], errors="coerce").to_numpy(dtype=float) if p_col
          else np.full(len(sub), np.nan))
    finite = np.isfinite(pv)
    # A COLUMN THAT IS PRESENT AND UNREADABLE IS NOT AN EVIDENCE DIMENSION. `has_p` used to be
    # `"pval" in sub.columns` alone, so a column R wrote as NA throughout drew every dot at the
    # maximum size under a caption saying no permutation had beaten any of them.
    has_p = bool(finite.any())
    levels = None
    if has_p:
        # A p-VALUE THAT IS NOT THERE IS THE WEAKEST POINT ON THE PANEL, NOT THE STRONGEST.
        # Non-finite entries were once replaced by `floor` - the SMALLEST attainable p-value - so
        # an edge whose p-value could not be read drew at 87% of the largest area on the figure,
        # in the direction of more evidence rather than less. The table was filtered at `thresh`,
        # so `thresh` is what a surviving edge is known to be no worse than, and it is the honest
        # stand-in.
        weakest = max(float(thresh), floor)
        pfill = np.round(np.where(finite, pv, weakest), 12)
        # ORDINAL AND WIDELY SPACED, BECAUSE THE UNDERLYING QUANTITY IS ORDINAL AND NARROW. Size
        # was -log10(p) rescaled onto its own range, and over the values this test can produce -
        # at nboot = 100 the whole table lies in {0, .01, .02, .03, .04} - that spans -log10 from
        # 1.4 to 2.3. As an AREA that is a 25% difference in diameter, which no eye reads off a
        # scatter: the panel carried an evidence dimension nobody could see, and its own key drew
        # three markers that were indistinguishable from each other. Ranking the attainable
        # values and spreading them over the full usable area range makes the dimension legible.
        # It is a rank, and the caption says so rather than implying a continuous scale.
        levels = sorted(set(pfill.tolist()))
        rank = {v: i for i, v in enumerate(sorted(levels, reverse=True))}
        span = max(1, len(levels) - 1)
        size = np.array([13.0 + 62.0 * (rank[v] / span) for v in pfill])

        def _plab(v):
            # `p = 0.005` USED TO APPEAR IN THE KEY, and this test cannot produce it. It came out
            # of clipping p = 0 to half the floor so the marker would have a finite size, and then
            # printing the clipped value back as though it were the measurement.
            return (f"p = 0  (< {floor:g})" if v <= 0 else f"p = {v:g}")

        size_says = (f"DOT SIZE IS EVIDENCE, not strength: it ranks the permutation p-value, "
                     f"largest for the edges no permutation of the labels beat in {nboot:,} draws "
                     f"and smallest for those sitting just under the {thresh:g} threshold. The "
                     f"test is quantised at {floor:g}, so only {len(levels)} size(s) exist here "
                     f"and the key beside the panel names each one; the steps are equal in area "
                     f"and NOT proportional to p, and a dot area is not comparable with another "
                     f"run's.")
        n_missing = int((~finite).sum())
        if n_missing:
            size_says += (f" {n_missing:,} of the {len(sub):,} points carried no readable "
                          f"p-value and are drawn at the size of an edge with p = {weakest:g}, "
                          f"the weakest a surviving edge can be, which is a statement about the "
                          f"table rather than about those edges.")
    else:
        # SIZE MEANS NOTHING HERE, SO IT IS CONSTANT AND THE CAPTION SAYS SO. A size scale
        # carrying no variable is a scale a reader will read anyway.
        size = 22.0
        size_says = ("Dot size is constant: the returned table carried no readable permutation "
                     "p-value" + (" in its `pval` column" if p_col else " column") + ", so there "
                     "is no evidence dimension to draw.")

    F, plt = ctx.figure, ctx.plot()
    # PAIRS ON THE Y AXIS, INTERACTIONS ON THE X. A sender -> receiver category is a PAIR of
    # annotation paths and is the longest label anywhere on this page; rotated ninety degrees
    # under the panel, those labels took HALF the height of the whole figure - the data was drawn
    # in a strip and then shrunk again to fit the column. On y they read horizontally and cost
    # margin WIDTH, which a double-column figure has and height it does not, and the ranking then
    # runs top to bottom, which is the order a reader wants them in anyway.
    # THE FIGURE GROWS FOR THE LABELS; THE DATA AREA DOES NOT SHRINK FOR THEM. `constrained`
    # fits tick labels first, so a fixed height meant a long interaction name was paid for out
    # of the panel - which is how the old orientation ended up drawing its dots in a strip. The
    # band is measured off the labels that will actually be drawn, after folding.
    _xlab = [_wrap_tick(t) for t in inter]
    _long = max((len(ln) for t in _xlab for ln in t.split("\n")), default=8)
    band = 0.30 + 0.045 * _long
    fig, ax = plt.subplots(figsize=(F.DOUBLE, max(2.4, 0.21 * len(pairs) + 1.15 + band)),
                           layout="constrained")
    # A SPARSE GRID NEEDS RULES. Most cells of this panel are empty by construction, and without
    # them tracing a dot back to its row and its column is guesswork over several centimetres.
    ax.set_axisbelow(True)
    ax.grid(True, color="#EDEDED", lw=0.4)
    # A LINEAR SCALE WITH ONE LARGE OUTLIER MAKES EVERY OTHER VALUE THE SAME COLOUR. Measured
    # by opening this panel: a single self-signalling pair sat at 0.28 while the other ~200 dots
    # were under 0.06, so the ramp spent four fifths of its range on one mark and the channel
    # could not be decoded anywhere else. The colour is the METHOD's probability and is not
    # touched; what changes is the range the ramp is spread over.
    #
    # CLIPPED AT A PERCENTILE, AND THE CLIP IS PRINTED. Anything above it is drawn at the top
    # colour and the colourbar says how many marks that is, so a reader knows the top of the
    # ramp means "at least this" rather than "this". `decoupler` in this repository already
    # solves the same problem the same way and prints its own percentile for the same reason.
    _c = sub["prob"].to_numpy()
    _hi = float(np.percentile(_c, 98)) if _c.size else 1.0
    _over = int((_c > _hi).sum())
    if not (_hi > 0):
        _hi = float(_c.max()) if _c.size else 1.0
    pts = ax.scatter([xi[t] for t in sub["interaction"]], [yi[p] for p in sub["pair"]],
                     c=_c, s=size, cmap="viridis", linewidths=0,
                     vmin=float(_c.min()) if _c.size else 0.0, vmax=_hi)
    # RASTERISED ONLY WHEN IT BUYS SOMETHING. The convention exists for scatters of 100,000
    # points; a few hundred dots stay vector, so the circles print crisp and stay editable.
    if len(sub) > 5000:
        F.rasterize_points(ax)
    ax.set_yticks(np.arange(len(pairs)))
    # SHORTENED TO THE SHORTEST UNAMBIGUOUS TAIL. These categories are PAIRS of
    # annotation paths, sixty characters before a real name is reached. The full path
    # stays in the source table.
    _short = F.short_labels(pairs)
    ax.set_yticklabels([_short[p] for p in pairs])
    ax.set_xticks(np.arange(len(inter)))
    ax.set_xticklabels(_xlab, rotation=90, linespacing=0.95)
    ax.set_xlabel("ligand-receptor interaction")
    ax.set_ylabel("sender -> receiver")
    ax.set_ylim(len(pairs) - 0.4, -0.6)
    ax.set_xlim(-0.6, len(inter) - 0.4)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    # HORIZONTAL, so the right-hand margin is free for the size key. A colourbar and a legend both
    # anchored right is two things in one place under `constrained`. `aspect` is set because the
    # default of 20 shrank it to half the panel width, leaving it floating over the middle of the
    # figure with no edge aligned to anything.
    cb = fig.colorbar(pts, ax=ax, orientation="horizontal", location="top", fraction=0.035,
                      pad=0.02, aspect=45)
    cb.outline.set_visible(False)
    cb.set_label("communication probability"
                 + (f"   (clipped at the 98th percentile, {_hi:.3g}; {_over} mark"
                    f"{'s' if _over != 1 else ''} above it drawn at the top colour)"
                    if _over else ""))
    if levels is not None:
        # A SIZE SCALE WITH NO KEY IS NOT A SCALE, and this key is now every attainable value
        # rather than three quantiles of a continuous one. `s` is an area and Line2D's `ms` is a
        # diameter, hence the square root - and the keys are drawn at the size they appear on the
        # panel, magnified by nothing, because a size key that is not to scale is not a key.
        import matplotlib.lines as ml
        span = max(1, len(levels) - 1)
        rank = {v: i for i, v in enumerate(sorted(levels, reverse=True))}
        shown = sorted(levels)[:6]
        handles = [ml.Line2D([], [], marker="o", ls="", color=F.INK,
                             ms=float(np.sqrt(13.0 + 62.0 * (rank[v] / span))),
                             label=_plab(v)) for v in shown]
        # `ax.legend`, not `fig.legend`: the anchor is then in AXES coordinates and the key lands
        # beside the panel. Through `figure.legend_outside` it goes to `fig.legend`, whose
        # bbox_to_anchor is read in FIGURE coordinates, so 1.02 is past the right edge of the
        # whole figure and `bbox_inches="tight"` grows the page to reach it.
        ax.legend(handles, [h.get_label() for h in handles], loc="center left",
                  bbox_to_anchor=(1.02, 0.5), title="permutation p", labelspacing=1.0,
                  handletextpad=0.6, borderaxespad=0, frameon=False,
                  fontsize=6, title_fontsize=6)

    src = sub[["interaction", "pair", "source", "target", "prob"]
              + (["pval"] if p_col else [])
              + ([c for c in ("pathway_name", "annotation") if c in sub.columns])]
    dropped = (f" - {n_pairs_all - len(pairs):,} further pair(s) carrying one of these "
               f"interactions are NOT drawn" if n_pairs_all > len(pairs) else "")
    ctx.emit_figure(
        "F5_dotplot", fig,
        caption=(f"The {len(inter)} strongest ligand-receptor interactions (columns) against the "
                 f"{len(pairs)} sender -> receiver pairs that carry them (rows), both ordered by "
                 f"their strongest edge{dropped}. The whole set is in tables/ccc_edges.csv. "
                 f"Colour is CellChat's communication probability, on its own scale and not "
                 f"comparable with another method's. " + size_says
                 + " Population names are shortened to their shortest unambiguous tail; the full "
                   "paths are in the source table. An empty cell is an interaction that was not "
                   "significant for that pair, which the panels above may already explain."),
        source=src.set_index("interaction"))
    return True


# ---------------------------------------------------------------------------------------- run

# ---------------------------------------------------------------------------------------------
# THE PANELS THE CENTRALITY / PATTERN / SIMILARITY HELPERS WERE WRITTEN FOR.
#
# Those helpers were added, verified against CellChat's own definitions, and then called by
# NOTHING - `_pops_and_matrices`, `_pathway_array`, `_centrality`, `_patterns` and `_similarity`
# each appeared exactly once in this file, at their own `def`. The commit that added them says
# "No figure drawn yet" and no commit since drew one. So the plugin computed five figures'
# worth of quantities in principle and shipped five figures that use none of them.
#
# DEAD CODE IS NOT A HALF-FINISHED FEATURE, it is a claim in the repository that something is
# supported. Everything below is the other half, and it adds no dependency: every quantity comes
# from the edge list this plugin already writes.
# ---------------------------------------------------------------------------------------------


def _edges_to_arrays(edges, names):
    """(pops, count, weight, pathways, K x K x P) or None - the shared front half of F6-F10.

    Computed ONCE and handed to each panel. Five panels each rebuilding the pathway array is
    five chances for them to disagree about which pathways exist and in what order, and the
    order is not cosmetic: `_pathway_array` ranks by descending total probability and every
    "top N" below indexes into that ranking.
    """
    import pandas as pd

    if edges is None or not len(edges):
        return None
    need = {"source", "target", "prob"}
    if not need <= set(edges.columns):
        return None
    df = edges.copy()
    df["source"] = df["source"].astype(str)
    df["target"] = df["target"].astype(str)
    df["prob"] = pd.to_numeric(df["prob"], errors="coerce").fillna(0.0)
    pops, count, weight = _pops_and_matrices(df, names)
    if "pathway_name" not in df.columns:
        return pops, count, weight, [], None
    paths, arr = _pathway_array(df, pops)
    return pops, count, weight, paths, arr


def _fig_signaling_roles(ctx, pre, names):
    """F6 - `netAnalysis_signalingRole_scatter`: who sends, who receives, on one plane."""
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()

    if pre is None:
        return False
    pops, count, weight, _paths, _arr = pre
    out_s, in_s = weight.sum(axis=1), weight.sum(axis=0)
    if float(out_s.sum() + in_s.sum()) <= 0:
        return False
    n_edge = count.sum(axis=1) + count.sum(axis=0)

    # A MAP KEYED BY LABEL, exactly like `palette` - iterating it yields the ORIGINAL labels,
    # which is how the first version of this panel printed full hierarchical paths over its own
    # y-axis. Indexed in `pops` order, never iterated.
    _sm = F.short_labels(pops)
    short = [_sm[p] for p in pops]
    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.85), layout="constrained")
    # AREA PROPORTIONAL TO COUNT, NOT RADIUS. A radius-encoded marker overstates a large value
    # by squaring it, and this is the one panel where marker size carries a number.
    smax = float(n_edge.max()) or 1.0
    size = 18.0 + 150.0 * (n_edge / smax)
    # `palette` returns a DICT keyed by label, not a list. Indexing it back in `pops` order is
    # what keeps a point's colour tied to its own population rather than to its position.
    _cmap = F.palette(list(pops))
    ax.scatter(out_s, in_s, s=size, c=[_cmap[p] for p in pops], alpha=0.85,
               edgecolor=F.INK, linewidth=0.4, zorder=3)
    # AND THE SIZE IS KEYED. The comment above says area carries a number; nothing on the panel
    # said WHICH number, so the reader met a tenfold spread of marker areas with no way to read
    # one. Found by opening it, in the same pass that found the identical defect on the
    # similarity panel - two panels, one omission, and the note about area being proportional
    # sat directly above the line that failed to key it.
    #
    # DRAWN AT THE SMALLEST VALUE ACTUALLY PLOTTED AS WELL AS THE LARGEST, because the map is
    # affine - `18 + 150 * n/nmax` - so area is not proportional at the small end and a key
    # showing only large values would confirm a mapping that does not hold there.
    if float(n_edge.max()) > 0:
        import matplotlib.lines as _ml
        _lo_e, _hi_e = float(n_edge.min()), float(n_edge.max())
        ax.legend(handles=[_ml.Line2D([], [], marker="o", ls="", color="#B0B0B0",
                                      markeredgecolor=F.INK, markeredgewidth=0.4,
                                      markersize=((18.0 + 150.0 * (v / smax)) ** 0.5) * 0.72,
                                      label=f"{v:.0f}")
                           for v in ({_lo_e, _hi_e} if _hi_e > _lo_e else {_hi_e})],
                  title="significant edges", fontsize=5, title_fontsize=5.5, frameon=False,
                  loc="upper left", bbox_to_anchor=(1.0, 1.0), labelspacing=1.1,
                  handletextpad=0.9, borderpad=0.2)
    # THE DIAGONAL IS THE CLAIM. A population above it receives more than it sends; below,
    # the reverse. Without it a reader compares two axes by eye and gets it wrong.
    #
    # THE RANGE IS TAKEN FROM THE DATA, NOT FROM ZERO. The diagonal only needs the two axes to
    # share a scale; it does not need the origin. Anchoring at zero put every population into
    # the top-right eighth of the first version of this panel - drawn, checked, and wrong - and
    # the differences the panel exists to show were smaller than the marker. A shared padded
    # range keeps the 45 degrees meaningful and spends the panel on the data. Zero is included
    # only when the data already comes near it, so a genuinely near-zero population is not
    # magnified into looking distant from the rest.
    lo_d = float(min(out_s.min(), in_s.min()))
    hi_d = float(max(out_s.max(), in_s.max()))
    span = (hi_d - lo_d) or (hi_d or 1.0)
    lo = 0.0 if lo_d <= 0.25 * span else lo_d - 0.12 * span
    hi = hi_d + 0.12 * span
    ax.plot([lo, hi], [lo, hi], color=F.GREY, lw=0.8, ls="--", zorder=1)
    # ON THE FIGURE, NOT ON THE AXES, AND THIS IS THE SECOND ATTEMPT. At the top-left of the
    # plotting area the note was overprinted by a high-receiving population's own label. Moved
    # to a GUESSED offset below the axes, it printed straight through the x-axis title instead -
    # one collision traded for another, because an offset in axes coordinates knows nothing
    # about the tick labels and the axis title that live outside them.
    #
    # Figure coordinates, beside the provenance stamp, where `bbox_inches="tight"` GROWS the
    # canvas to hold it rather than laying it over something. The stamp has worked that way on
    # every panel since it was added; this is the same mechanism, and the lesson is that a text
    # block anchored below a plot needs a measurement or a place outside the layout, never a
    # number that looked right once.
    fig.text(0.0, -0.055, "above the line: receives more than it sends",
             transform=fig.transFigure, fontsize=5.0, color="#8A8A8A", ha="left", va="top")
    # AND ONLY THE STRONGEST ARE NAMED. With every population labelled, the drawing audit found
    # two pairs of names printed over each other - horizontal neighbours at equal height, which
    # the radial declutter cannot separate because it moves labels vertically by design. Eight
    # is the same answer the similarity panel and the host role scatter already use, and every
    # position stays in the source table.
    _rank6 = sorted(range(len(pops)), key=lambda i: -(out_s[i] + in_s[i]))
    _named6 = {pops[i] for i in _rank6[:8]}
    # LABELS PUSHED OUTWARD FROM THE CENTRE. Every label offset by the same (2.5, 2.5) collided
    # wherever points cluster, which on this panel is exactly where the populations of interest
    # are. Offsetting along each point's own direction from the centroid separates a cluster
    # radially, which is the one direction that is always free.
    cx, cy = float(np.mean(out_s)), float(np.mean(in_s))
    _texts = []
    for x, y, lab, _pop in zip(out_s, in_s, short, pops):
        if _pop not in _named6:
            continue
        dx, dy = float(x) - cx, float(y) - cy
        norm = (dx * dx + dy * dy) ** 0.5 or 1.0
        ox, oy = 7.0 * dx / norm, 7.0 * dy / norm
        # OUTWARD FROM THE CENTRE, UNLESS OUTWARD LEAVES THE PANEL. A population near the left
        # edge is pushed further left by the radial rule and its name lands on the y-axis title
        # or off the figure entirely - which is what a thirteen-population arm did to four
        # labels that a nine-population sample never exposed. Near an edge the anchor flips
        # INWARD: slightly worse placement, still readable, still attached to its own point.
        _near_left = (float(x) - lo) < 0.18 * (hi - lo)
        _near_right = (hi - float(x)) < 0.18 * (hi - lo)
        if _near_left:
            ox, ha = abs(ox) + 2.0, "left"
        elif _near_right:
            ox, ha = -abs(ox) - 2.0, "right"
        else:
            ox, ha = ox + (2.0 if ox >= 0 else -2.0), ("left" if ox >= 0 else "right")
        _texts.append(ax.annotate(lab, (x, y), fontsize=5.5, xytext=(ox, oy),
                                  textcoords="offset points", color=F.INK, ha=ha,
                                  va="bottom" if oy >= 0 else "top"))
    F.spread_labels(ax, _texts)
    # ROOM FOR THE LABELS THEMSELVES. Population names here are hierarchical and long, and an
    # outward-offset label on the rightmost point runs past the axes without this.
    # PADDED ON BOTH SIDES. An outward-offset label on the LEFTMOST point runs off the axis
    # just as one on the rightmost does, and the leftmost population is the quiet one - the
    # case a reader is least able to reconstruct from memory.
    pad = 0.10 * (hi - lo)
    ax.set_xlim(lo - pad * 0.6, hi + pad)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("outgoing strength  (summed probability sent)")
    ax.set_ylabel("incoming strength  (summed probability received)")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    src = pd.DataFrame({"population": list(pops),
                        "outgoing_strength": out_s, "incoming_strength": in_s,
                        "significant_edges_sent": count.sum(axis=1).astype(int),
                        "significant_edges_received": count.sum(axis=0).astype(int)}
                       ).set_index("population")
    ctx.emit_figure(
        "F6_signaling_roles", fig,
        caption=("Each population placed by how much inferred signal it SENDS (x) against how "
                 "much it RECEIVES (y), both as summed communication probability over every "
                 "pathway; marker area is its total number of significant interactions. The "
                 "dashed line is equality, so distance from it is the asymmetry of a "
                 "population's role rather than its activity. Both axes are CellChat's own "
                 "probability scale and are comparable only within this unit. Self-signalling "
                 "sits on the diagonal of the underlying matrix and is counted in BOTH sums, as "
                 "CellChat counts it. This is a description of the inferred network, not a "
                 "test: no interval is drawn because nothing here has been tested."),
        source=src)
    return True


def _fig_pathway_rank(ctx, pre, top_n=20):
    """F8 - `rankNet`: total information flow per pathway, ranked, within one unit."""
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()

    if pre is None:
        return False
    _pops, _c, _w, paths, arr = pre
    if arr is None or not len(paths):
        return False
    flow = arr.sum(axis=(0, 1))
    if float(flow.sum()) <= 0:
        return False
    keep = min(int(top_n), len(paths))
    lab = list(paths[:keep])[::-1]
    val = list(flow[:keep])[::-1]

    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.6, 0.135 * keep + 0.55)),
                           layout="constrained")
    ax.barh(range(len(lab)), val, color=F.OKABE_ITO[0], height=0.72)
    ax.set_yticks(range(len(lab)))
    ax.set_yticklabels(lab, fontsize=6)
    ax.set_xlabel("information flow  (summed communication probability)")
    ax.margins(y=0.01)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)

    src = pd.DataFrame({"pathway": list(paths), "information_flow": flow,
                        "rank": np.arange(1, len(paths) + 1)}).set_index("pathway")
    ctx.emit_figure(
        "F8_pathway_rank", fig,
        caption=(f"Signalling pathways ranked by total information flow - the communication "
                 f"probability summed over every ordered population pair - within this unit. "
                 f"{'All ' + str(len(paths)) if keep == len(paths) else 'The top ' + str(keep) + ' of ' + str(len(paths))} "
                 f"pathways are drawn; every pathway and its rank is in the source table. "
                 f"THIS IS A RANKING WITHIN ONE UNIT AND NOT A COMPARISON BETWEEN UNITS: the "
                 f"probability scale depends on the populations present and on depth, so a "
                 f"pathway's bar here cannot be read against the same pathway's bar elsewhere. "
                 f"Rank can be compared; height cannot."),
        source=src)
    return True


def _fig_pathway_roles(ctx, pre, top_n=18):
    """F7 - `netAnalysis_signalingRole_heatmap`: pathway x population, sending and receiving."""
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()

    if pre is None:
        return False
    pops, _c, _w, paths, arr = pre
    if arr is None or len(paths) < 2:
        return False
    cen = _centrality(arr, paths)
    if not cen:
        return False
    shown = [p for p in paths if p in cen][:int(top_n)]
    if len(shown) < 2:
        return False
    _sm = F.short_labels(pops)
    short = [_sm[p] for p in pops]

    panels = (("outdeg", "Sender  (outgoing)"), ("indeg", "Receiver  (incoming)"))
    fig, axes = plt.subplots(1, 2, figsize=(F.DOUBLE, max(1.9, 0.17 * len(shown) + 1.0)),
                             layout="constrained", sharey=True)
    rows = []
    for ax, (key, title) in zip(np.atleast_1d(axes), panels):
        M = np.array([cen[p][key] for p in shown], dtype=float)
        # ROW-NORMALISED, AND SAID SO ON THE AXIS. CellChat scales each pathway to its own max
        # so that a weak pathway's pattern is visible beside a strong one. It means colour is
        # NOT comparable between rows, which is exactly the misreading the label prevents.
        rmax = M.max(axis=1, keepdims=True)
        Mn = np.divide(M, rmax, out=np.zeros_like(M), where=rmax > 0)
        # ABSENCE IS NOT A LOW SCORE (`panels.R2`). A population that does not appear in a
        # pathway's network at all has centrality exactly 0, and so does one that appears and is
        # peripheral - the same pale cell for "never in it" and "in it, weakly". Found by
        # opening the panel: three populations were pale across almost the whole sender side,
        # which reads as "these barely signal" and means "these are not in these pathways".
        #
        # Off the ramp and crossed, the way the sender-by-receiver matrix already marks a pair
        # with no edge. The colour scale then starts at the smallest score that was actually
        # measured, so the ramp is spent on the range that exists.
        _absent = M <= 0
        _shown = np.where(_absent, np.nan, Mn)
        _cm = plt.get_cmap("magma_r").copy()
        _cm.set_bad("white")
        im = ax.imshow(_shown, aspect="auto", cmap=_cm, vmin=0, vmax=1)
        _ys, _xs = np.nonzero(_absent)
        ax.scatter(_xs, _ys, marker="x", s=9, linewidths=0.45, color="#B0B0B0", zorder=3)
        ax.set_xticks(range(len(pops)))
        ax.set_xticklabels(short, rotation=45, ha="right", fontsize=5.5)
        ax.set_yticks(range(len(shown)))
        ax.set_yticklabels(shown, fontsize=5.5)
        ax.set_title(title, fontsize=7)
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        for i, p in enumerate(shown):
            for j, pop in enumerate(pops):
                rows.append({"pathway": p, "population": pop, "measure": key,
                             "centrality": float(M[i, j]),
                             "row_normalised": float(Mn[i, j])})
    cb = fig.colorbar(im, ax=list(np.atleast_1d(axes)), fraction=0.03, pad=0.015)
    cb.outline.set_visible(False)
    cb.set_label("centrality, scaled to each pathway's own maximum", fontsize=6)

    ctx.emit_figure(
        "F7_pathway_roles", fig,
        caption=(f"White crossed cells are populations NOT IN that pathway's network at all, "
                 f"which is a different thing from being in it and peripheral - both used to be "
                 f"the same pale colour. "
                 f"Which populations send and which receive, PER PATHWAY. Left is weighted "
                 f"out-degree and right weighted in-degree, the two measures CellChat labels "
                 f"Sender and Receiver. EACH ROW IS SCALED TO ITS OWN MAXIMUM, so colour shows "
                 f"where a pathway acts and never how strong it is - a faint row and a bright "
                 f"row can carry the same total, and the ranking in F8_pathway_rank is where "
                 f"magnitude is read. The {len(shown)} highest-flow of {len(paths)} pathways "
                 f"are drawn; unscaled values for every pathway and population are in the "
                 f"source table."),
        source=pd.DataFrame(rows).set_index(["pathway", "population", "measure"]))
    return True


def _fig_patterns(ctx, pre, direction="outgoing"):
    """F9 - `identifyCommunicationPatterns`: the latent patterns, with the rank shown."""
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()

    if pre is None:
        return False
    pops, _c, _w, paths, arr = pre
    if arr is None or len(paths) < 3:
        return False
    (w, rows), (h, cols), k, curve = _patterns(arr, paths, pops, direction=direction)
    if w is None:
        return False

    fig = plt.figure(figsize=(F.DOUBLE, 2.6), layout="constrained")
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 2.2, 0.9])
    ax0, ax1, ax2 = (fig.add_subplot(gs[0, i]) for i in range(3))

    ax0.imshow(w, aspect="auto", cmap="magma_r", vmin=0)
    ax0.set_xticks(range(k))
    ax0.set_xticklabels([f"P{i + 1}" for i in range(k)], fontsize=6)
    ax0.set_yticks(range(len(rows)))
    _rm = F.short_labels(rows)
    ax0.set_yticklabels([_rm[r] for r in rows], fontsize=5.5)
    ax0.set_title("populations x pattern", fontsize=7)

    ncol = h.shape[1]
    im = ax1.imshow(h, aspect="auto", cmap="magma_r", vmin=0)
    ax1.set_yticks(range(k))
    ax1.set_yticklabels([f"P{i + 1}" for i in range(k)], fontsize=6)
    step = max(1, ncol // 40)
    ax1.set_xticks(range(0, ncol, step))
    ax1.set_xticklabels([cols[i] for i in range(0, ncol, step)], rotation=90, fontsize=4.5)
    ax1.set_title("pattern x pathway", fontsize=7)

    # THE RANK, SHOWN. `k` is chosen by cophenetic correlation over restarts, and a decomposition
    # whose rank was picked silently is a decomposition nobody can check. The chosen k is marked
    # on the curve it was chosen from.
    _boundary = bool(curve.pop("_boundary", 0.0)) if curve else False
    if curve:
        ks = sorted(curve)
        ax2.plot(ks, [curve[i] for i in ks], marker="o", ms=3, lw=1,
                 color=F.OKABE_ITO[0])
        ax2.axvline(k, color=F.OKABE_ITO[3], lw=1, ls="--")
        ax2.set_xlabel("k")
        ax2.set_ylabel("cophenetic correlation", fontsize=6)
        # SAY WHICH OF THE TWO HAPPENED. Where the curve declines over the whole range tried,
        # taking its maximum returns the SMALLEST k offered for any data - the title then reads
        # like a criterion that discriminated, and no criterion did. Found by opening the panel
        # on a real unit, where every k from 2 to 7 declined.
        ax2.set_title(f"rank chosen: k = {k}" if not _boundary
                      else f"k = {k}: the LOWEST TRIED", fontsize=7)
        if _boundary:
            ax2.text(0.5, -0.30, "the curve declines throughout, so the maximum is the left\n"
                                 "edge of the range — a boundary, not a selection",
                     transform=ax2.transAxes, ha="center", va="top", fontsize=5.2,
                     color="#B25E00")
    else:
        ax2.set_axis_off()
        ax2.text(0.5, 0.5, f"k = {k}\n(no curve)", ha="center", va="center", fontsize=6)
    for ax in (ax0, ax1):
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
    for sp in ("top", "right"):
        ax2.spines[sp].set_visible(False)
    cb = fig.colorbar(im, ax=[ax1], fraction=0.02, pad=0.01)
    cb.outline.set_visible(False)
    cb.set_label("loading", fontsize=6)

    src = pd.concat([
        pd.DataFrame(w, index=pd.Index(rows, name="row"),
                     columns=[f"P{i + 1}" for i in range(k)]).stack()
          .rename("loading").reset_index().assign(side="population"),
        pd.DataFrame(h.T, index=pd.Index(cols, name="row"),
                     columns=[f"P{i + 1}" for i in range(k)]).stack()
          .rename("loading").reset_index().assign(side="pathway"),
    ]).rename(columns={"level_1": "pattern"}).set_index(["side", "row", "pattern"])
    ctx.emit_figure(
        "F9_patterns", fig,
        caption=(f"Latent {direction} communication patterns: a non-negative factorisation of "
                 f"the population-by-pathway matrix into {k} patterns, each a set of populations "
                 f"(left) that use a set of pathways (right) together. The input is scaled to "
                 f"each pathway's own maximum before factorising, as CellChat does, so a pattern "
                 f"groups pathways by WHERE they act and not by how strong they are. The rank "
                 f"was not chosen by hand: the right panel is the cophenetic correlation of the "
                 f"consensus over restarts and the dashed line is the k taken from it. A pattern "
                 f"is a summary of this unit's own matrix - it is not a cell state, and the "
                 f"numbering carries no order."),
        source=src)
    return True


def _fig_similarity(ctx, pre):
    """F10 - `computeNetSimilarity` + an embedding: which pathways use the same cell pairs."""
    import numpy as np
    import pandas as pd
    F, plt = ctx.figure, ctx.plot()

    if pre is None:
        return False
    _pops, _c, _w, paths, arr = pre
    if arr is None or len(paths) < 4:
        return False
    sim, kept, dropped = _similarity(arr, paths)
    if sim is None or len(kept) < 3:
        return False

    # CLASSICAL MDS, AND NAMED AS SUCH ON THE PAGE. CellChat embeds with UMAP; umap-learn is not
    # in this plugin's declared packages and adding a dependency to place a few dozen points
    # would be the wrong trade. Classical scaling is deterministic, needs nothing beyond numpy,
    # and - unlike UMAP - its axes carry a meaning that can be stated. What must NOT happen is
    # calling it UMAP, so the caption says which it is and the axis labels say MDS.
    d = 1.0 - np.asarray(sim, dtype=float)
    np.fill_diagonal(d, 0.0)
    n = d.shape[0]
    j = np.eye(n) - np.ones((n, n)) / n
    b = -0.5 * j @ (d ** 2) @ j
    vals, vecs = np.linalg.eigh(b)
    order = np.argsort(vals)[::-1][:2]
    xy = vecs[:, order] * np.sqrt(np.clip(vals[order], 0, None))
    flow = arr.sum(axis=(0, 1))
    fmap = {p: float(f) for p, f in zip(paths, flow)}
    size = np.array([fmap.get(p, 0.0) for p in kept], dtype=float)
    size = 16.0 + 130.0 * (size / (size.max() or 1.0))

    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.9), layout="constrained")
    ax.scatter(xy[:, 0], xy[:, 1], s=size, color=F.OKABE_ITO[2], alpha=0.8,
               edgecolor=F.INK, linewidth=0.35, zorder=3)
    # A SIZE CHANNEL WITH NO KEY IS DECORATION THAT LOOKS LIKE EVIDENCE. Dot area varied about
    # tenfold across this panel and nothing on it said what area meant - found by opening the
    # figure, and it is the single most common defect in the catalogue this project keeps.
    #
    # THE MAP IS AFFINE AND THE KEY SAYS SO. `16 + 130 * f/fmax` has an intercept, so area is
    # NOT proportional to flow: at the small end the floor dominates. The key is drawn at the
    # SMALLEST value actually plotted as well as the largest, which is what makes the floor
    # self-evident rather than a footnote nobody reads.
    _raw = np.array([fmap.get(p, 0.0) for p in kept], dtype=float)
    if _raw.size and _raw.max() > 0:
        import matplotlib.lines as _ml
        _lo, _hi = float(_raw[_raw > 0].min()), float(_raw.max())
        _keys = [(_lo, 16.0 + 130.0 * (_lo / _hi)), (_hi, 146.0)]
        ax.legend(handles=[_ml.Line2D([], [], marker="o", ls="", color=F.OKABE_ITO[2],
                                      markeredgecolor=F.INK, markeredgewidth=0.35,
                                      markersize=(sz ** 0.5) * 0.72,
                                      label=f"{v:.3g}") for v, sz in _keys],
                  title="total flow", fontsize=5, title_fontsize=5.5, frameon=False,
                  loc="upper left", bbox_to_anchor=(1.0, 1.0), labelspacing=1.1,
                  handletextpad=0.9, borderpad=0.2)
    # LABELS PUSHED OUTWARD FROM THE CENTRE, for the reason F6 does it: this panel's whole
    # message is that pathways CLUSTER, so the labels collide exactly where the reader is
    # looking. Radial offset is the one direction that stays free inside a cluster.
    # ONLY THE HIGHEST-FLOW PATHWAYS ARE LABELLED, and the caption says how many. Radial offset
    # alone was tried and looked at: it separates a round cluster and does nothing for the
    # near-collinear chains this similarity produces, so twenty-four labels overprinted each
    # other and ran off the axes. A panel that labels everything illegibly names nothing. Every
    # pathway keeps its coordinates in the source table, so nothing is lost but the clutter.
    # EIGHT, NOT TWELVE. The drawing audit named three collisions here - 'CDH5' over 'ESAM',
    # 'APP' over 'CypA', 'COLLAGEN' over 'CypA' - and all three are horizontal neighbours at
    # equal height, which the declutter cannot fix because it separates vertically by design.
    # Fewer labels is the honest fix: every position stays in the source table.
    _n_lab = 8
    _rank = {p: i for i, p in enumerate(paths)}
    _label = {k for k in sorted(kept, key=lambda q: _rank.get(q, 10 ** 6))[:_n_lab]}
    cx, cy = float(xy[:, 0].mean()), float(xy[:, 1].mean())
    _texts = []
    for (x, y), lab in zip(xy, kept):
        if lab not in _label:
            continue
        dx, dy = float(x) - cx, float(y) - cy
        norm = (dx * dx + dy * dy) ** 0.5 or 1.0
        ox, oy = 7.5 * dx / norm, 7.5 * dy / norm
        _texts.append(ax.annotate(lab, (x, y), fontsize=5.0,
                                  xytext=(ox + (1.5 if ox >= 0 else -1.5), oy),
                                  textcoords="offset points", color=F.INK,
                                  ha="left" if ox >= 0 else "right",
                                  va="bottom" if oy >= 0 else "top"))
    # THE CLUSTER IS THE RESULT, so its labels are the ones that must be readable. Radial
    # offset alone puts every member of a tight clump on the same side; this separates them.
    F.spread_labels(ax, _texts)
    # EQUAL ASPECT, BECAUSE THE DISTANCES ARE THE POINT. An MDS panel drawn on unequal axes
    # shows distances that are not the distances it computed, which is the one thing this
    # plot must not do.
    ax.set_aspect("equal", adjustable="datalim")
    # ROOM FOR THE LABEL, NOT JUST FOR THE POINT. `margins` reserves space around the DATA, and
    # a label is drawn in display space outside it - so the leftmost pathway's name started
    # before the axis and was clipped by it. Found by opening the panel. The declutter is left
    # alone: it separates vertically and cannot fix a name that is simply wider than the margin.
    ax.margins(0.30)
    ax.set_xlabel("MDS 1")
    ax.set_ylabel("MDS 2")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    src = pd.DataFrame({"pathway": list(kept), "mds1": xy[:, 0], "mds2": xy[:, 1],
                        "information_flow": [fmap.get(p, 0.0) for p in kept]}
                       ).set_index("pathway")
    ctx.emit_figure(
        "F10_pathway_similarity", fig,
        caption=("Pathways placed by functional similarity - the Jaccard overlap of the ordered "
                 "population pairs each one uses, so two pathways are close when they act "
                 "BETWEEN THE SAME POPULATIONS, however strongly. Magnitude is discarded by that "
                 "definition and is shown only as marker area. The placement is CLASSICAL "
                 "MULTIDIMENSIONAL SCALING, not the UMAP CellChat uses: it is deterministic and "
                 "needs no extra dependency, and distances are approximated rather than "
                 "preserved, so read neighbourhoods and not gaps. The "
                 f"{min(_n_lab, len(kept))} highest-flow of {len(kept)} placed pathways are "
                 "LABELLED and the rest are drawn unlabelled - every one keeps its coordinates "
                 "in the source table."
                 + (f" {len(dropped)} pathway(s) could not be placed and are NAMED rather than "
                    f"dropped silently - {', '.join(dropped[:8])}"
                    + (" ..." if len(dropped) > 8 else "")
                    + ". Those share no nearest neighbour after the shared-nearest-neighbour "
                      "mask, which makes them the most distinctive pathways here, not the least "
                      "important." if dropped else "")),
        source=src)
    return True


def run(ctx):
    import subprocess
    import numpy as np
    import pandas as pd
    from scipy import io as sio
    from scipy import sparse

    C = ctx.config
    db = _DB.get(ctx.organism)
    if not db:
        return ctx.refuse("cell-cell communication",
                          f"CellChat ships no database for {ctx.organism!r}. Known: "
                          f"{', '.join(sorted(_DB))}. Scoring against another species' database "
                          f"returns a small plausible table rather than failing.")

    # `ctx.populations()` unpacks as (mask, groups); `.names` and `.dropped` are what this wants.
    # Read as (populations, dropped) this made `len(pops)` the CELL COUNT - so the refusal below
    # could never fire and the headline claimed a hundred thousand populations - and `if dropped:`
    # asked the truth value of a numpy array, which raises.
    pop = ctx.populations()
    if len(pop.names) < 2:
        return ctx.refuse("cell-cell communication",
                          f"only {len(pop.names)} population(s); communication needs two to be "
                          f"between.")
    # HOW MANY CELLS, NOT HOW MANY LABELS. `len(pop.dropped)` is the number of distinct sentinel
    # VALUES - two, usually - and "2 annotator sentinel(s) excluded" reads as two cells.
    n_sentinel_cells = int((~np.asarray(pop.mask)).sum())
    if pop.dropped:
        ctx.caveat(f"{n_sentinel_cells:,} cell(s) carrying {len(pop.dropped)} annotator sentinel "
                   f"label(s) ({', '.join(pop.dropped)}) were excluded as senders and as "
                   f"receivers, and were not handed to CellChat at all. A sentinel is the "
                   f"annotator declining to call a cell type, and an interaction attributed to "
                   f"one names nothing.")

    # THE CONVENTIONS BEFORE ANYTHING IS SPENT. Not for the settings' sake: it is the cheapest
    # possible check that this environment can draw at all, and the alternative is discovering a
    # broken backend after the scoring has run.
    ctx.plot()

    real = np.asarray(ctx.real_cells())
    A = ctx.adata[real]
    X = ctx.X[real] if ctx.X.shape[0] == ctx.adata.n_obs else A.X
    # ONE csr, USED THREE TIMES. It is written out for R, asked which genes are detected, and
    # asked how much of each population expresses them; building it once is the difference
    # between one copy of the matrix and three.
    Xc = sparse.csr_matrix(X)
    var_names = np.asarray(A.var_names).astype(str)
    rscript = ctx.params.get("rscript") or "Rscript"

    # ---------------------------------------------------------- what the database can reach
    #
    # BEFORE ANYTHING IS WRITTEN OR SCORED, because this is the failure that costs an hour and
    # then reads like a result. It touches no expression data and takes seconds.
    db_script = ctx.out / "cellchat_db.R"
    db_script.write_text(_R_DB, encoding="utf-8")
    db_csv = ctx.out / "cellchat_db.csv"
    p0 = subprocess.run([rscript, str(db_script), db, str(db_csv)],
                        capture_output=True, text=True)
    for line in (p0.stdout or "").splitlines()[-4:]:
        ctx.log(f"  R: {line}")
    if p0.returncode != 0:
        ctx.log("  the database could not be read out; coverage will not be reported "
                + " | ".join((p0.stderr or "").strip().splitlines()[-3:]))
    db_frame = _read_db(db_csv, ctx.log)

    coverage, testable = None, None
    if db_frame is not None:
        present = set(var_names)
        allg = [_genes(l) + _genes(r)
                for l, r in zip(db_frame["ligand_genes"], db_frame["receptor_genes"])]
        testable = [bool(g) and all(x in present for x in g) for g in allg]
        coverage = float(np.mean(testable)) if len(testable) else 0.0
        ctx.log(f"database {db}: {len(db_frame):,} interactions, "
                f"{int(np.sum(testable)):,} ({100 * coverage:.1f}%) with every gene present in "
                f"this object's {len(var_names):,} genes")
        if coverage <= 0:
            return ctx.refuse(
                "cell-cell communication",
                f"not one of {db}'s {len(db_frame):,} interactions has all of its genes in this "
                f"object. Nothing is scoreable, and CellChat would return an empty or "
                f"near-empty table rather than saying so.\n"
                f"  This is what a different gene annotation looks like - the object carries "
                f"{len(var_names):,} genes, e.g. {', '.join(map(str, var_names[:4]))}.\n"
                f"  Fix: run this on an object whose var_names are the symbols {db} uses, and "
                f"one that has not been reduced to a selected gene set.")
        if coverage < float(C["min_coverage"]):
            ctx.log(f"  coverage is below min_coverage={C['min_coverage']}; the run will be "
                    f"reported as partial")

    # ---------------------------------------------------------- the scoring
    mtx = ctx.out / "cellchat_expr.mtx"
    # GENES x CELLS: CellChat's convention, and transposing in the wrong place is the classic way
    # to get a full, plausible, meaningless result out of it.
    sio.mmwrite(str(mtx), Xc.T.tocoo())
    pd.Series(var_names).to_csv(str(mtx) + ".genes", index=False, header=False)
    meta = ctx.out / "cellchat_meta.csv"
    pd.DataFrame({"label": A.obs[ctx.keys["label"]].astype(str).to_numpy()},
                 index=A.obs_names.astype(str)).to_csv(meta)

    script = ctx.out / "cellchat.R"
    script.write_text(_R_RUN, encoding="utf-8")
    edges_f = ctx.out / "tables" / "ccc_edges.csv"
    argv = [rscript, str(script), str(mtx), str(meta), db,
            str(C["min_cells"]), str(C["trim"]), str(edges_f),
            str(C["type"]), "TRUE" if C["population_size"] else "FALSE",
            str(C["nboot"]), str(C["thresh"])]
    ctx.log(f"handing {A.n_obs:,} cells x {A.n_vars:,} genes to {db} via {rscript}")
    ctx.log(f"  type={C['type']} trim={C['trim']} population.size={C['population_size']} "
            f"nboot={C['nboot']} thresh={C['thresh']} min.cells={C['min_cells']}")
    proc = subprocess.run(argv, capture_output=True, text=True)
    for line in (proc.stdout or "").splitlines()[-8:]:
        ctx.log(f"  R: {line}")
    if proc.returncode != 0 or not edges_f.exists():
        tail = (proc.stderr or "").strip().splitlines()[-6:]
        return ctx.refuse("cell-cell communication",
                          "CellChat did not produce an edge table. R said: "
                          + " | ".join(tail))

    try:
        df = pd.read_csv(edges_f)
    except pd.errors.EmptyDataError:
        # R EXITED 0 AND WROTE NOTHING, which is this method's characteristic shape of failure:
        # it does not raise. Unhandled, this was a traceback out of `read_csv` rather than a
        # refusal the host could record beside every other result.
        return ctx.refuse("cell-cell communication",
                          f"CellChat wrote {edges_f.name} with no header at all, so not even the "
                          f"columns of the edge table are known. R exited 0.")
    # INDEXED BY NAME, NOT BY POSITION, and on the same column liana's `ccc_edges.csv` uses - the
    # two are declared `reads_with` each other and are meant to be opened side by side.
    # `df.set_index(df.columns[0])` indexed on whatever column CellChat happened to write first.
    ctx.emit_table("ccc_edges", df.set_index("source" if "source" in df.columns
                                             else df.columns[0]))
    ctx.log(f"{len(df):,} significant edges returned at p < {C['thresh']}")

    # ---------------------------------------------------------- what the figures are drawn from
    groups = np.asarray(pop.groups) if pop.groups is not None else None
    names = sorted(pop.names)
    n_cells = {p: int((groups == p).sum()) for p in names} if groups is not None else {}
    sent = {p: 0 for p in names}
    received = {p: 0 for p in names}
    if {"source", "target"} <= set(df.columns):
        for col, into in (("source", sent), ("target", received)):
            for p, k in df[col].astype(str).value_counts().items():
                if p in into:
                    into[p] = int(k)
    edge_counts = {p: sent[p] + received[p] for p in names}

    detected = var_names[_nnz_per_gene(Xc) > 0]
    floor, floor_why = _floor_for(str(C["type"]), float(C["trim"]))
    above_floor = None
    if db_frame is not None and groups is not None:
        gset = {g for l, r in zip(db_frame["ligand_genes"], db_frame["receptor_genes"])
                for g in _genes(l) + _genes(r)}
        idx = {g: i for i, g in enumerate(var_names)}
        cols = [idx[g] for g in sorted(gset) if g in idx]
        if cols:
            sub = Xc[:, cols]
            above_floor = {}
            for p in names:
                rows_i = np.where(groups == p)[0]
                if not len(rows_i):
                    above_floor[p] = 0.0
                    continue
                nz = _nnz_per_gene(sub[rows_i]) / float(len(rows_i))
                above_floor[p] = float(np.mean(nz >= floor))

    ctx.log("figures:")
    drew_coverage = _fig_coverage(ctx, db_frame, var_names, detected, df, float(C["thresh"]))
    _fig_population_power(ctx, names, n_cells, sent, received, above_floor,
                          int(C["min_cells"]), floor_why, n_sentinel_cells)
    drew_perm = _fig_permutation(ctx, df, int(C["nboot"]), float(C["thresh"]))
    _fig_network(ctx, df, names)
    drew_dot = _fig_dotplot(ctx, df, int(C["dotplot_n"]), int(C["nboot"]), float(C["thresh"]))
    # THE PATHWAY-LEVEL PANELS. `_edges_to_arrays` is computed once and shared: five panels each
    # rebuilding the pathway array is five chances to disagree about which pathways exist and in
    # what order, and that order is a ranking every "top N" below indexes into.
    _pre = _edges_to_arrays(df, names)
    drew_roles = _fig_signaling_roles(ctx, _pre, names)
    drew_rank = _fig_pathway_rank(ctx, _pre)
    drew_proles = _fig_pathway_roles(ctx, _pre)
    drew_pat = _fig_patterns(ctx, _pre)
    drew_sim = _fig_similarity(ctx, _pre)

    # ---------------------------------------------------------- caveats, from this run's numbers
    # EDGES AND INTERACTIONS ARE TWO NUMBERS AND THE HEADLINE HAD ONE WORD FOR BOTH. A row of this
    # table is one interaction between one ORDERED PAIR of populations, so `len(df)` counts
    # triples, while F1's last bar counts DISTINCT interactions - and the headline calling the
    # first "interactions" disagreed with the figure printed under it.
    #
    # `df.iloc[0]` is gone with it. subsetCommunication returns rows in the database's order, so
    # the first one is not the strongest, the most significant or the most anything; quoting it in
    # a headline puts an arbitrary sender -> receiver pair where a reader looks for the finding.
    n_inter = (int(df["interaction_name"].astype(str).nunique())
               if "interaction_name" in df.columns else None)
    # ON A SHARED AXIS WITH THE OTHER UNITS. Declared in `report.unit_metrics`; the host
    # draws the comparison, so this is the whole of what this plugin owes for one.
    ctx.metric("significant_edges", len(df))
    ctx.metric("populations", len(names))
    ctx.headline = (f"{len(df):,} significant edges"
                    + (f" over {n_inter:,} ligand-receptor interaction(s)"
                       if n_inter is not None else "")
                    + f" and {len(names)} populations, {db}"
                    + (f"; {100 * coverage:.0f}% of the database testable here"
                       if coverage is not None else "; database coverage unmeasured"))

    ctx.caveat(f"Database: {db}, bundled in the pinned CellChat package. Its version is fixed by "
               f"the package version and by nothing else, so two runs on different CellChat "
               f"versions are two databases.")
    if coverage is not None:
        ctx.caveat(
            f"{int(np.sum(testable)):,} of {len(db_frame):,} database interactions "
            f"({100 * coverage:.1f}%) have every one of their genes present in this object; the "
            f"rest could not be tested at all. See F1_database_coverage.")
        if coverage < float(C["min_coverage"]):
            ctx.status = "partial"
            ctx.caveat(
                f"COVERAGE IS BELOW {C['min_coverage']}. Most of the database was not testable "
                f"here, and this method does not fail when that happens - it returns a smaller "
                f"table of exactly the same shape. Read the edge table as a sample of the "
                f"database that happened to be measurable, not as the interactions that exist.")
    else:
        ctx.caveat(
            "The database could not be read out interaction by interaction, so how much of it "
            "was testable on this object is UNKNOWN and F1_database_coverage is absent. A low "
            "interaction count below cannot be distinguished from a database that did not match "
            "these gene symbols.")
    ctx.caveat(
        f"Averaging: type={C['type']}"
        + (f", trim={C['trim']}" if str(C["type"]) != "triMean"
           else " (trim is not read under triMean)")
        + f". {floor_why}, whatever the biology. CellChat's own vignette states that the number "
          f"of inferred pairs depends on this choice, so an interaction count is not comparable "
          f"across runs that set it differently.")
    ctx.caveat(
        f"population.size={C['population_size']}. CellChat's default is FALSE, which its "
        f"documentation prescribes for SORTED cells; for an unsorted preparation it says to set "
        f"TRUE, on the grounds that abundant populations send collectively stronger signals. "
        f"Whether this dataset is sorted is not something this plugin can read.")
    # THE STATED REASON IS THE ACTUAL REASON. `_fig_permutation` declines for three different
    # causes and this said "no p-value column" for all of them - so a run that returned no edge at
    # all was told its table had no `pval`, which is a false sentence on the page about the one
    # thing the reader cannot check for themselves.
    if drew_perm:
        perm_says = ", and F3_permutation shows where they sit."
    elif not len(df):
        perm_says = ("; no edge survived, so there is no p-value to place and F3_permutation is "
                     "absent.")
    elif "pval" not in df.columns:
        perm_says = ("; the returned table carries no `pval` column, so F3_permutation is absent "
                     "and nothing below has been placed against the permutation floor.")
    else:
        perm_says = ("; the returned table's `pval` column held no readable number, so "
                     "F3_permutation is absent.")
    ctx.caveat(
        f"Every edge was tested by permuting the group labels {C['nboot']:,} times and the table "
        f"was filtered at p < {C['thresh']}. A p-value can only be a multiple of "
        f"{1.0 / max(int(C['nboot']), 1):g}, so a reported 0 is an upper bound rather than a "
        f"measured probability" + perm_says)
    small = sorted(p for p in names if n_cells.get(p, 0) < int(C["min_cells"]))
    if small:
        ctx.caveat(
            f"{len(small)} population(s) have fewer than min.cells={C['min_cells']} cells and "
            f"their edges were dropped after scoring: "
            + ", ".join(f"{p} ({n_cells.get(p, 0):,})" for p in small[:8])
            + ("..." if len(small) > 8 else "")
            + ". They are absent from the result and that absence is technical.")
    silent = sorted(p for p in names
                    if edge_counts.get(p, 0) == 0 and n_cells.get(p, 0) >= int(C["min_cells"]))
    if silent:
        ctx.caveat(
            f"{len(silent)} population(s) large enough to be scored returned NO significant "
            f"interaction: " + ", ".join(silent[:8]) + ("..." if len(silent) > 8 else "")
            + ". Read that against F2_population_power before calling it biology - CellChat also "
              "requires a population's signalling genes to be over-expressed relative to the "
              "others, so silence is partly a statement about the rest of the object.")
    if not drew_dot:
        want = {"source", "target", "prob", "interaction_name"}
        missing = sorted(want - set(df.columns))
        if not len(df):
            dot_why = "no interaction survived scoring and the p-value threshold"
        elif missing:
            dot_why = (f"the returned table carries no {', '.join(missing)} column, so there is "
                       f"nothing to place on one of the panel's axes")
        else:
            dot_why = "no row carried a readable communication probability"
        ctx.caveat(f"No ligand-receptor pair could be drawn: {dot_why}, so F5_dotplot is absent. "
                   f"Read that against the panels above rather than as a figure that failed.")
    if not drew_coverage:
        ctx.log("  F1_database_coverage not drawn")
    ctx.caveat("Scores are CellChat's own scale and are not comparable with another method's; "
               "only the ranking can be compared.")
    if ctx.assay == "nucleus":
        ctx.caveat(
            "Single-NUCLEUS data. Secreted signalling is 37.9% of the pinned CellChatDB v2 "
            "(measured: 1,280 of 3,379 mouse interactions; the v1 figure of ~60% belongs to a "
            "different, smaller database), and secreted ligand transcripts are among those "
            "least well "
            "retained when the cytoplasm is lost, so the interaction classes are not equally "
            "represented here and an absent secreted interaction is as consistent with the "
            "preparation as with the biology. How large that cost is on this tissue is not "
            "something this run measured: F1_database_coverage counts what is PRESENT in the "
            "object, not what the preparation removed.")
    elif ctx.assay == "cell":
        ctx.caveat(
            "Whole cells. Dissociation itself changes ligand and receptor expression, and no "
            "spatial information constrains which of these populations could have been in "
            "contact.")
    if ctx.unit:
        ctx.caveat(f"This result describes the unit {ctx.unit!r} alone. Nothing here is a "
                   f"comparison between units, and a difference between two units' tables has "
                   f"not been tested for.")


# ----------------------------------------------------------------------------------- selftest

#: The R that lists what CellChat actually exports, so the accounting is checked against the
#: package rather than against memory. This inventory was first taken by hand, over SSH, and the
#: numbers went into a declaration - which is the same defect as quoting a hand-computed figure
#: in a manuscript: nobody else can reproduce it and nothing notices when it drifts.
_R_INVENTORY = r"""
suppressMessages(library(CellChat))
ex <- sort(getNamespaceExports("CellChat"))
plotting <- grep("^(netVisual|netAnalysis|plot|show|StackedVln)", ex, value = TRUE)
cat(paste(plotting, collapse = "\n"), "\n")
"""


def plot_inventory():
    """The plotting functions CellChat exports here, measured. [] when R cannot be reached.

    MEASURED, NOT DECLARED. `native_plots` is this plugin's account of what it does with each of
    them, and an account is only worth anything against a real list - if CellChat adds a function
    or renames one, the accounting must go stale loudly rather than quietly stay complete.
    """
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as fh:
        fh.write(_R_INVENTORY)
        path = fh.name
    try:
        p = subprocess.run(["Rscript", path], capture_output=True, text=True, timeout=600)
    except Exception:                                                     # noqa: BLE001
        return []
    if p.returncode != 0:
        return []
    # NO UNDERSCORE FILTER. An earlier version kept only names containing "_", which silently
    # dropped netVisual, StackedVlnPlot, plotGeneExpression and showDatabaseCategory - and the
    # accounting then reported four DECLARED functions as ones CellChat does not export, when the
    # package exports all four and the filter had hidden them. A check with a filter in it is a
    # check on the filter too.
    return [l.strip() for l in p.stdout.splitlines() if l.strip()]


def check_plot_accounting():
    """Compare the DECLARED accounting against the package. Returns a list of problems.

    Run from `selftest`, where R is present. On a machine without R the inventory comes back
    empty and this says so rather than passing.
    """
    inv = plot_inventory()
    if not inv:
        return ["could not read CellChat's exports; the plot accounting is unverified here"]
    declared = PLUGIN.get("native_plots") or {}
    missing = [f for f in inv if f not in declared]
    stale = [f for f in declared if f not in inv]
    out = []
    if missing:
        out.append(f"{len(missing)} exported plot(s) absent from native_plots: "
                   f"{', '.join(sorted(missing)[:8])}")
    if stale:
        out.append(f"{len(stale)} declared plot(s) CellChat does not export: "
                   f"{', '.join(sorted(stale)[:8])}")
    return out


def selftest(ctx):
    """Prove R, CellChat, its database and the bridge — not just that the package imports.

    The R side is the part that breaks: a Suggests-only package a default code path requires, a
    database object renamed, a function moved. Running the real pipeline on a tiny fixture is the
    only thing that sees any of it.

    IT ALSO RUNS THE DATABASE DUMP, because the diagnostics are now built on that file's SHAPE.
    `db$interaction$ligand`, `db$complex` and the `annotation` column are three assumptions about
    somebody else's data object, and a version that renames any of them would leave the coverage
    panel silently absent on every run - which is exactly the failure that panel exists to catch.
    """
    import subprocess
    import shutil
    import tempfile
    from pathlib import Path

    rscript = shutil.which("Rscript")
    assert rscript, "no Rscript on PATH - this plugin's environment did not provide R"
    probe = r'''
suppressMessages(library(CellChat))
cat("CellChat", as.character(packageVersion("CellChat")), "\n")
cat("presto", as.character(packageVersion("presto")), "\n")
for (n in c("CellChatDB.human", "CellChatDB.mouse")) {
  db <- get(n); cat(n, nrow(db$interaction), "interactions\n") }
d <- CellChatDB.mouse$interaction
stopifnot(nrow(d) > 1000)
for (col in c("ligand", "receptor", "pathway_name", "annotation")) {
  stopifnot(col %in% colnames(d)) }
cat("interaction columns OK\n")
stopifnot(!is.null(CellChatDB.mouse$complex), nrow(CellChatDB.mouse$complex) > 0)
cat("complex table", nrow(CellChatDB.mouse$complex), "rows\n")
cat("OK\n")
'''
    p = subprocess.run([rscript, "-e", probe], capture_output=True, text=True, timeout=900)
    for line in (p.stdout or "").splitlines():
        ctx.log(f"  R: {line}")
    assert p.returncode == 0 and "OK" in (p.stdout or ""), (
        "the CellChat probe failed. R said: "
        + " | ".join((p.stderr or "").strip().splitlines()[-6:]))
    # presto is the one that bites: `identifyOverExpressedGenes` defaults to do.fast = TRUE and
    # STOPS without it rather than falling back, and it is Suggests-only and not on CRAN.
    assert "presto" in (p.stdout or ""), (
        "presto is not installed. CellChat's default overexpression path hard-requires it and "
        "stops rather than falling back, so the environment is not usable.")

    # The database dump, end to end, on the real database - not a fixture. It is the input to
    # every coverage number this plugin reports, and it is parsed by Python, so both halves are
    # exercised here or neither is.
    import pandas as pd
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        s = td / "db.R"
        s.write_text(_R_DB, encoding="utf-8")
        out = td / "db.csv"
        q = subprocess.run([rscript, str(s), "CellChatDB.mouse", str(out)],
                           capture_output=True, text=True, timeout=900)
        for line in (q.stdout or "").splitlines():
            ctx.log(f"  R: {line}")
        assert q.returncode == 0 and out.exists(), (
            "the database dump failed, so the coverage diagnostic would be absent on every run. "
            "R said: " + " | ".join((q.stderr or "").strip().splitlines()[-6:]))
        d = pd.read_csv(out)
        for col in ("interaction_name", "pathway_name", "annotation",
                    "ligand_genes", "receptor_genes"):
            assert col in d.columns, f"the dump has no {col!r} column; its writer and its reader "\
                                     f"disagree"
        assert len(d) > 1000, f"the dump holds {len(d)} interactions, which is not a database"
        genes = {g for l, r in zip(d["ligand_genes"], d["receptor_genes"])
                 for g in _genes(l) + _genes(r)}
        assert len(genes) > 500, (
            f"only {len(genes)} gene symbols came out of the dump. Every coverage number is "
            f"computed against this set, so a truncated one reports a real object as "
            f"uncoverable.")
        # A COMPLEX MUST HAVE BEEN EXPANDED. If it was not, every multi-subunit interaction is
        # tested for a gene that is a complex NAME and can never be in var_names - which reports
        # a matched database as unmatched, and does it silently.
        assert any(";" in str(x) for x in d["ligand_genes"]) or \
               any(";" in str(x) for x in d["receptor_genes"]), (
            "no interaction expanded into subunits, so db$complex was not read. Multi-subunit "
            "interactions would be counted as absent on every object.")
        ctx.log(f"  database dump: {len(d):,} interactions, {len(genes):,} gene symbols, "
                f"annotation classes {sorted(set(d['annotation'].astype(str)))[:4]}")

    # The figure path is part of this plugin and part of the environment: matplotlib has a
    # backend, and none of it is exercised by the R bridge.
    plt = ctx.plot()
    fig, ax = plt.subplots(figsize=(ctx.figure.SINGLE, ctx.figure.SINGLE))
    ax.imshow([[0, 1], [1, 0]], cmap="viridis")
    plt.close(fig)
    ctx.log("  ok   the drawing path imports and draws")


#: STEP THREE: the COMPARISON. CellChat ships four differential figures and every one of them
#: needs two objects merged; a per-unit plugin had nowhere to call them from, so none was called
#: and every comparison panel in the section was a reimplementation. This runs once per arm pair,
#: on the objects the two units already saved, so it costs no inference at all.
_R_COMPARE = r"""
suppressMessages({library(CellChat); library(patchwork)})
args <- commandArgs(trailingOnly = TRUE)
rds_a <- args[1]; rds_b <- args[2]; name_a <- args[3]; name_b <- args[4]; figdir <- args[5]
dir.create(figdir, showWarnings = FALSE, recursive = TRUE)

a <- readRDS(rds_a); b <- readRDS(rds_b)
# The merged object is what every differential function here takes. Order matters: CellChat's
# differentials are computed as the SECOND relative to the FIRST, so the names are recorded on
# every figure this writes rather than left to the reader.
m <- mergeCellChat(list(a, b), add.names = c(name_a, name_b))
cat("merged:", name_a, "and", name_b, "\n")

npng <- function(nm, expr, w = 2000, h = 1600, res = 200) {
  path <- file.path(figdir, paste0("nativecmp_", nm, ".png"))
  ok <- tryCatch({
    grDevices::png(path, width = w, height = h, res = res)
    on.exit(grDevices::dev.off(), add = TRUE)
    print(expr); TRUE
  }, error = function(e) { cat("native compare", nm, "FAILED:", conditionMessage(e), "\n"); FALSE })
  if (ok) cat("native compare", nm, "written\n") else if (file.exists(path)) unlink(path)
}

# 1. the differential interaction network - CellChat's own answer to "which pairs changed"
npng("diffInteraction_count", netVisual_diffInteraction(m, weight.scale = TRUE, measure = "count"))
npng("diffInteraction_weight", netVisual_diffInteraction(m, weight.scale = TRUE, measure = "weight"))

# 2. the differential heatmap, same question in a form that reads pair by pair
npng("diff_heatmap_count", netVisual_heatmap(m, measure = "count"))
npng("diff_heatmap_weight", netVisual_heatmap(m, measure = "weight"))

# 3. ranked information flow with BOTH arms on one axis, CellChat's own comparison mode
npng("rankNet_stacked", rankNet(m, mode = "comparison", stacked = TRUE, do.stat = FALSE),
     w = 1600, h = 2000)
npng("rankNet_unstacked", rankNet(m, mode = "comparison", stacked = FALSE, do.stat = FALSE),
     w = 1600, h = 2000)

# 4. how each population's signalling ROLE moves between the two arms
npng("diff_signalingRole", {
  gg <- tryCatch(netAnalysis_diff_signalingRole_scatter(m), error = function(e) NULL)
  if (is.null(gg)) stop("netAnalysis_diff_signalingRole_scatter returned nothing")
  gg
})

# 5. per-population signalling changes - the one figure that names WHICH signals moved for a
#    given population, which is the question a reader asks immediately after seeing the network
groups <- intersect(levels(a@idents), levels(b@idents))
for (g in head(groups, 4)) {
  safe <- gsub("[^A-Za-z0-9]+", "_", g)
  npng(paste0("signalingChanges__", safe),
       netAnalysis_signalingChanges_scatter(m, idents.use = g))
}
"""


def compare(ctx):
    """CellChat's own differential figures for one pair of arms.

    Runs on the two units' SAVED objects, so it costs no inference. Every figure here is
    CellChat's, drawn by CellChat; none is a reimplementation.
    """
    import subprocess
    import tempfile

    names = ctx.names
    if len(names) != 2:
        ctx.log(f"compare needs exactly two units, got {names}")
        return
    rds = [ctx.dir_of(n) / "objects" / "cellchat.rds" for n in names]
    missing = [str(p) for p in rds if not p.is_file()]
    if missing:
        # A SAVED OBJECT IS THE INPUT. Without it there is nothing to compare and re-running the
        # inference here would hide that the unit never wrote one.
        ctx.log(f"no saved CellChat object for {ctx.pair}: {missing}")
        return
    with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as fh:
        fh.write(_R_COMPARE)
        script = fh.name
    cmd = ["Rscript", script, str(rds[0]), str(rds[1]), names[0], names[1],
           str(ctx.figures())]
    p = subprocess.run(cmd, capture_output=True, text=True)
    for line in (p.stdout + p.stderr).splitlines():
        if line.strip():
            ctx.log(f"  R: {line.rstrip()}")
    if p.returncode != 0:
        ctx.log(f"compare FAILED for {ctx.pair} (exit {p.returncode})")
