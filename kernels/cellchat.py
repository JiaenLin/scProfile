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

So three of the five panels here are diagnostics and they come first. The two results — who
signals to whom, and through which ligand–receptor pairs — are worth reading only underneath
them.

IT RUNS PER UNIT. An inference pooled over a cohort describes the average of its conditions and
may describe none of them; the host fans it out and this file sees one unit. Every panel is
therefore a statement about that unit alone.
"""

PLUGIN = {
    "api": 1,
    "version": "0.2.0",
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
            "About 60% of CellChatDB is SECRETED signaling (Jin et al., Nat Commun 2021). On "
            "nuclei those transcripts are the ones least well captured, so the classes of "
            "interaction are not equally affected by the assay - the coverage table is broken "
            "down by CellChat's own annotation class for that reason.",
        ],
    },

    "inject": {"required": ["lognorm", "label", "organism"], "optional": ["sample"]},
    "provides": ["communication"],
    "produces": ["tables/ccc_edges.csv"],
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
        "packages": {"anndata": ">=0.10,<0.12", "pandas": ">=2.0,<3", "scipy": ">=1.10",
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
    "report": {
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
#: every one. It is a property of the page, not of any dataset: one ordered pair per column at
#: 6 pt runs off a 174 mm figure somewhere around here, and the count of pairs grows as the SQUARE
#: of the populations - nine of them is eighty-one columns. It was a bare `15` inside the drawing
#: function, which is a cap on what the reader is shown that nothing in `config`, nothing in the
#: caption and nothing in the source table could see.
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

cc <- createCellChat(object = X, meta = meta, group.by = "label")
cc@DB <- get(db_name)
cc <- subsetData(cc)
cc <- identifyOverExpressedGenes(cc)
cc <- identifyOverExpressedInteractions(cc)
cc <- computeCommunProb(cc, type = mean_type, trim = trim,
                        population.size = pop_size, nboot = nboot, seed.use = 1L)
cc <- filterCommunication(cc, min.cells = min_cells)
df <- subsetCommunication(cc, thresh = thresh)
write.csv(df, out, row.names = FALSE)
cat("edges:", nrow(df), "\n")
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
    # The last stage is the RESULT and the ones above it are the database narrowing down to it;
    # one colour for all four would make the funnel read as four measurements of one thing.
    colours = (["#0072B2"] * (len(rows) - 1) + ["#009E73"]) if len(rows) > 1 else ["#0072B2"]
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.6, 0.34 * len(rows) + 0.9)))
    ax.barh(y, vals, height=0.68, color=colours)
    for yi, v in zip(y, vals):
        ax.text(v, yi, f"  {v:,} ({100 * v / max(1, n0):.0f}%)", va="center", fontsize=6,
                color=F.INK)
    ax.set_yticks(y)
    ax.set_yticklabels([l for l, _ in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.32 if max(vals) else 1)
    ax.set_xlabel("interactions")
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
                   "of populations that carries it. Per-class counts are in the source table."),
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

    panels = [("n_cells", "cells", "#0072B2"),
              ("n_significant_edges", "significant interactions (sent + received)", "#009E73")]
    if above_floor is not None:
        panels.insert(1, ("frac_present_db_genes_above_floor",
                          "fraction of the database genes\nPRESENT here above the averaging floor",
                          "#E69F00"))
    # `constrained`, because the shared y axis carries population names and the right-hand
    # panels carry their own x labels; without it the two collide the moment a name is long.
    fig, axs = plt.subplots(1, len(panels),
                            figsize=(F.DOUBLE, max(1.7, 0.22 * len(src) + 1.0)),
                            sharey=True, squeeze=False, layout="constrained")
    y = np.arange(len(src))
    for ax, (col, xlabel, colour) in zip(axs[0], panels):
        ax.barh(y, src[col].to_numpy(), height=0.7, color=colour)
        ax.set_xlabel(xlabel)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        if col == "n_cells":
            ax.axvline(float(min_cells), color=F.INK, ls="--", lw=0.6)
        if col == "frac_present_db_genes_above_floor":
            ax.set_xlim(0, 1)
    axs[0][0].set_yticks(y)
    axs[0][0].set_yticklabels(src.index)
    axs[0][0].invert_yaxis()

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
    middle = ("what fraction of the database genes PRESENT IN THIS OBJECT clear the averaging "
              "floor in it - which is not a fraction of the database, and F1 is the panel that "
              "says how much of the database is present at all - " if above_floor is not None
              else "")
    ctx.emit_figure(
        "F2_population_power", fig,
        caption=("Per population, sorted by size: how many cells it has, " + middle
                 + "and how many significant interactions came back. "
                 + (floor_why + ". " if above_floor is not None else "")
                 + "The dashed line is min.cells, below which CellChat drops a population's "
                   "edges after scoring. A population low on the left cannot be read as quiet on "
                   "the right - it was never able to speak." + rho
                 + f" Sender and receiver counts are separated in the source table. The "
                   f"{n_sentinel_cells:,} cells carrying an annotator sentinel are not a "
                   f"population, were not handed to CellChat, and are not drawn here."),
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
    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.62))
    if len(vals) <= 30:
        # THE VALUES ARE DISCRETE, so they are drawn discrete. A histogram of five attainable
        # values with twenty bins invents a distribution the test cannot produce.
        w = (1.0 / max(nboot, 1)) * 0.6
        ax.bar(vals, counts, width=w, color="#0072B2")
    else:
        ax.hist(pv, bins=30, color="#0072B2")
    floor = 1.0 / max(nboot, 1)
    ax.axvline(floor, color=F.INK, ls="--", lw=0.6)
    ax.set_xlabel("permutation p-value")
    ax.set_ylabel("edges")
    ax.set_xlim(-floor, max(float(thresh), float(vals.max())) + floor)
    ctx.emit_figure(
        "F3_permutation", fig,
        caption=(f"The p-values behind the edges that survived. The test permutes the group "
                 f"labels {nboot:,} times, so a p-value can only be a multiple of "
                 f"{floor:g} - the dashed line - and every bar here is at or below the "
                 f"{thresh:g} threshold the table was filtered at. A bar at zero is not a small "
                 f"probability: it is an upper bound, meaning no permutation of the labels "
                 f"reached the observed value in {nboot:,} draws. More permutations would "
                 f"separate those edges; nothing else will."),
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

    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.95), layout="constrained")
    im = ax.imshow(counts.to_numpy(), cmap="viridis", aspect="auto",
                   vmin=0, vmax=max(1, int(counts.to_numpy().max())))
    ax.set_xticks(np.arange(n))
    ax.set_yticks(np.arange(n))
    # SHORTENED TO THE SHORTEST UNAMBIGUOUS TAIL. These categories are PAIRS of
    # annotation paths, sixty characters before a real name is reached, and rotated
    # ninety degrees they took three quarters of the figure height - squeezing the
    # data into a strip. The full path stays in the source table.
    _short = F.short_labels(names)
    ax.set_xticklabels([_short[n] for n in names], rotation=90)
    ax.set_yticklabels([_short[n] for n in names])
    ax.set_xlabel("receiver")
    ax.set_ylabel("sender")
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label("significant interactions")
    ctx.emit_figure(
        "F4_network", fig,
        caption=("Inferred communication from each sender population (rows) to each receiver "
                 "(columns), counted as significant ligand-receptor interactions. Every "
                 "population is drawn whether or not it participates, so a silent row is visible "
                 "rather than missing - and a silent row is the case the diagnostics above "
                 "exist to explain. The diagonal is signalling within a population, which is "
                 "inferred exactly as the off-diagonal is and is no more direct. Summed "
                 "communication probability for every pair is in the source table."),
        source=src)


def _fig_dotplot(ctx, edges, top_n, nboot, thresh):
    """CellChat's bubble plot: pairs against sender-receiver, colour probability, size evidence."""
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

    rows = list(e.groupby("interaction")["prob"].max().nlargest(int(top_n)).index)
    sub = e[e["interaction"].isin(rows)]
    # HOW MANY PAIRS THERE WERE, BEFORE THE CAP, so the caption can say what the figure dropped.
    # The cap is a page constraint and it is named; it was a bare literal here.
    n_pairs_all = int(sub["pair"].nunique())
    cols = list(sub["pair"].value_counts().head(_DOT_PAIRS).index)
    sub = sub[sub["pair"].isin(cols)]
    if not len(sub):
        return False
    # Rows ordered by their strongest edge, columns by how much they carry: a dotplot whose axes
    # are in database order is a dotplot nobody can read down.
    rows = list(sub.groupby("interaction")["prob"].max().sort_values(ascending=False).index)
    cols = list(sub.groupby("pair")["prob"].max().sort_values(ascending=False).index)
    ri = {r: i for i, r in enumerate(rows)}
    ci = {c: i for i, c in enumerate(cols)}

    floor = 1.0 / max(int(nboot), 1)
    p_col = "pval" in sub.columns
    pv = (pd.to_numeric(sub["pval"], errors="coerce").to_numpy(dtype=float) if p_col
          else np.full(len(sub), np.nan))
    finite = np.isfinite(pv)
    # A COLUMN THAT IS PRESENT AND UNREADABLE IS NOT AN EVIDENCE DIMENSION. `has_p` used to be
    # `"pval" in sub.columns` alone, so a column R wrote as NA throughout drew every dot at the
    # maximum size under a caption saying no permutation had beaten any of them.
    has_p = bool(finite.any())
    sig = smax = None
    if has_p:
        # A p-value of 0 is not zero probability, it is < 1/nboot; clipped to half the floor so
        # it takes the largest size the scale has rather than an infinite one.
        #
        # AND A p-VALUE THAT IS NOT THERE IS THE WEAKEST POINT ON THE PANEL, NOT THE STRONGEST.
        # Non-finite entries were replaced by `floor` - the SMALLEST attainable p-value - so an
        # edge whose p-value could not be read drew at 87% of the largest area on the figure, in
        # the direction of more evidence rather than less. The table was filtered at `thresh`, so
        # `thresh` is what a surviving edge is known to be no worse than, and it is the honest
        # stand-in.
        weakest = max(float(thresh), floor)
        sig = -np.log10(np.clip(np.where(finite, pv, weakest), floor / 2.0, None))
        smax = float(sig.max()) if float(sig.max()) > 0 else 1.0
        size = 5.0 + 30.0 * (sig / smax)
        size_says = (f"DOT SIZE IS EVIDENCE, not strength: it is -log10 of the permutation "
                     f"p-value, so the largest dots are edges no permutation of the labels beat "
                     f"in {nboot:,} draws and the smallest sit just under the {thresh:g} "
                     f"threshold - and because the test is quantised at {floor:g}, only a few "
                     f"sizes are attainable. The key beside the panel is that scale, which is "
                     f"normalised WITHIN this figure: a dot area is not comparable with another "
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
        size = 14.0
        size_says = ("Dot size is constant: the returned table carried no readable permutation "
                     "p-value" + (" in its `pval` column" if p_col else " column") + ", so there "
                     "is no evidence dimension to draw.")

    F, plt = ctx.figure, ctx.plot()
    fig, ax = plt.subplots(figsize=(F.DOUBLE, max(2.0, 0.20 * len(rows) + 1.4)),
                           layout="constrained")
    pts = ax.scatter([ci[c] for c in sub["pair"]], [ri[r] for r in sub["interaction"]],
                     c=sub["prob"].to_numpy(), s=size, cmap="viridis", linewidths=0)
    F.rasterize_points(ax)
    ax.set_xticks(np.arange(len(cols)))
    # SHORTENED TO THE SHORTEST UNAMBIGUOUS TAIL. These categories are PAIRS of
    # annotation paths, sixty characters before a real name is reached, and rotated
    # ninety degrees they took three quarters of the figure height - squeezing the
    # data into a strip. The full path stays in the source table.
    _short = F.short_labels(cols)
    ax.set_xticklabels([_short[c] for c in cols], rotation=90)
    ax.set_yticks(np.arange(len(rows)))
    ax.set_yticklabels(rows)
    ax.set_xlim(-0.6, len(cols) - 0.4)
    ax.set_ylim(len(rows) - 0.4, -0.6)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    # HORIZONTAL, so the right-hand margin is free for the size key. A colourbar and a legend both
    # anchored right is two things in one place under `constrained`.
    cb = fig.colorbar(pts, ax=ax, orientation="horizontal", location="top", fraction=0.05, pad=0.04)
    cb.outline.set_visible(False)
    cb.set_label("communication probability")
    if smax is not None:
        # A SIZE SCALE WITH NO KEY IS NOT A SCALE. `smax` is fitted to this figure, so the same
        # area means a different p-value in the next run, and without these markers a reader can
        # compare dots inside one panel and nothing else. `s` is an area and Line2D's `ms` is a
        # diameter, hence the square root - and the keys are drawn at the size they appear on the
        # panel, magnified by nothing, because a size key that is not to scale is not a key.
        import matplotlib.lines as ml
        keys = sorted({float(sig.min()), float(np.median(sig)), float(sig.max())})
        handles = [ml.Line2D([], [], marker="o", ls="", color=F.INK,
                             ms=float(np.sqrt(5.0 + 30.0 * (k / smax))),
                             label=f"p = {10 ** (-k):.3g}") for k in keys]
        # `ax.legend`, not `fig.legend`: the anchor is then in AXES coordinates and the key lands
        # beside the panel. Through `figure.legend_outside` it goes to `fig.legend`, whose
        # bbox_to_anchor is read in FIGURE coordinates, so 1.02 is past the right edge of the
        # whole figure and `bbox_inches="tight"` grows the page to reach it.
        ax.legend(handles, [h.get_label() for h in handles], loc="center left",
                  bbox_to_anchor=(1.02, 0.5), title="permutation p", labelspacing=1.1,
                  handletextpad=0.6, borderaxespad=0, frameon=False,
                  fontsize=6, title_fontsize=6)

    src = sub[["interaction", "pair", "source", "target", "prob"]
              + (["pval"] if p_col else [])
              + ([c for c in ("pathway_name", "annotation") if c in sub.columns])]
    dropped = (f" - {n_pairs_all - len(cols):,} further pair(s) carrying one of these "
               f"interactions are NOT drawn" if n_pairs_all > len(cols) else "")
    ctx.emit_figure(
        "F5_dotplot", fig,
        caption=(f"The {len(rows)} strongest ligand-receptor interactions against the "
                 f"{len(cols)} sender -> receiver pairs that carry them{dropped}. The whole set "
                 f"is in tables/ccc_edges.csv. Colour is CellChat's communication probability, on "
                 f"its own scale and not comparable with another method's. " + size_says
                 + " An empty cell is an interaction that was not significant for that pair, "
                   "which the panels above may already explain."),
        source=src.set_index("interaction"))
    return True


# ---------------------------------------------------------------------------------------- run

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
            "Single-NUCLEUS data. Around 60% of CellChatDB is secreted signalling (Jin et al., "
            "Nat Commun 2021), and secreted ligand transcripts are among those least well "
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
