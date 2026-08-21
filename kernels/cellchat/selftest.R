#!/usr/bin/env Rscript
# Prove this environment can actually SCORE COMMUNICATION, before a cohort is spent on it.
#
# `library(CellChat)` is not the test. CellChat is a sequence of calls over an S4 object it mutates
# in place, its ligand-receptor scoring is compiled Rcpp, and its permutation step runs through
# `future`. Every one of those can be present, attach cleanly, and then fail - or worse, return an
# empty edge table - inside the first real run:
#
#   * the conda r-base and the compiled CellChat_Rcpp objects disagree about the ABI, which shows
#     up when the compiled function is CALLED, not when the package is attached;
#   * `identifyOverExpressedInteractions` finds nothing, `computeCommunProb` then returns a
#     zero-row table, and downstream reads that as "these cells do not communicate";
#   * `future` picks a parallel plan whose workers cannot see this library.
#
# So this runs the whole path on a synthetic object with a PLANTED interaction: genes taken from
# CellChat's own database, a ligand made high in one group and its receptor high in another. It
# asserts shapes, columns and finiteness, and that the planted edge comes back. It asserts nothing
# about biology - the data is synthetic and the planted pair is the fixture, not a result.
#
# It also measures the database's gene-symbol CASING, for the reason liana's selftest does the
# same: CellChatDB is species-specific, and the human database run against mouse symbols returns a
# small plausible table rather than an error.

suppressPackageStartupMessages(library(CellChat))

cat("cellchat selftest\n")
cat(sprintf("  R            %s.%s\n", R.version$major, R.version$minor))
for (p in c("CellChat", "NMF", "ComplexHeatmap", "BiocNeighbors", "Matrix", "Rcpp",
            "future", "circlize", "sna", "igraph", "ggplot2")) {
  v <- tryCatch(as.character(utils::packageVersion(p)), error = function(e) "ABSENT")
  cat(sprintf("  %-12s %s\n", p, v))
  if (v == "ABSENT") {
    stop(sprintf(paste0("%s is not installed. Every CellChat dependency comes from the pinned ",
                        "conda section of lock.yml - a missing one is a line to add there, not ",
                        "something to install by hand."), p))
  }
}
sha <- utils::packageDescription("CellChat")$RemoteSha
cat(sprintf("  CellChat commit %s\n", if (is.null(sha)) "unrecorded" else substr(sha, 1, 7)))

# ONE process. `future`'s default is sequential, but a site .Rprofile can change it, and a plan
# whose workers cannot see this library fails in a way that reads as a CellChat bug.
future::plan("sequential")
options(future.globals.maxSize = 512 * 1024^2)
set.seed(0)

# ---- the databases, and what tells them apart -----------------------------------------------
db_human <- CellChatDB.human
db_mouse <- CellChatDB.mouse
cat(sprintf("  CellChatDB human: %s interactions, %s genes\n",
            format(nrow(db_human$interaction), big.mark = ","),
            format(nrow(db_human$geneInfo), big.mark = ",")))
cat(sprintf("  CellChatDB mouse: %s interactions, %s genes\n",
            format(nrow(db_mouse$interaction), big.mark = ","),
            format(nrow(db_mouse$geneInfo), big.mark = ",")))
upper_frac <- function(g) {
  g <- g[!is.na(g) & nzchar(g)]
  mean(g == toupper(g))
}
cat(sprintf(paste0("  casing: human %.0f%% upper, mouse %.0f%% upper - this is what makes the ",
                   "wrong database return almost nothing\n"),
            100 * upper_frac(db_human$geneInfo$Symbol),
            100 * upper_frac(db_mouse$geneInfo$Symbol)))
if (nrow(db_human$interaction) < 100 || nrow(db_mouse$interaction) < 100) {
  stop("a CellChatDB with under 100 interactions is not the shipped database")
}

# ---- a fixture built FROM the database, so a real edge exists to find ------------------------
# Single-gene ligands and receptors only: a complex is resolved through CellChatDB$complex and
# would need every subunit planted, which makes the fixture about the fixture. A gene is used on
# one side only, so the plant is unambiguous.
symbols <- db_human$geneInfo$Symbol
symbols <- unique(symbols[!is.na(symbols) & nzchar(symbols)])
simple <- db_human$interaction[db_human$interaction$ligand %in% symbols &
                                 db_human$interaction$receptor %in% symbols, ]
simple <- simple[!(simple$receptor %in% simple$ligand), ]
simple <- simple[!duplicated(simple$ligand) & !duplicated(simple$receptor), ]
if (nrow(simple) < 8) stop("fewer than 8 single-gene interactions in the database; cannot plant")
pairs <- simple[seq_len(8), c("ligand", "receptor", "interaction_name")]
planted <- as.character(pairs$interaction_name[1])
cat(sprintf("  planting %d ligand-receptor pairs from the database; the first is %s\n",
            nrow(pairs), planted))

groups <- c("Alpha", "Beta", "Gamma")
per_group <- 60
n <- length(groups) * per_group
background <- setdiff(symbols, c(pairs$ligand, pairs$receptor))[seq_len(60)]
genes <- unique(c(pairs$ligand, pairs$receptor, background))
labels <- factor(rep(groups, each = per_group), levels = groups)
cells <- sprintf("c%03d", seq_len(n))

# Log-normalised-looking values: background everywhere, the planted ligands high in Alpha and
# their receptors high in Beta. `computeCommunProb`'s triMean scores nothing unless the gene is
# expressed across most of a group, so the plant is group-wide rather than sprinkled.
X <- matrix(rgamma(length(genes) * n, shape = 1.2, rate = 1.5),
            nrow = length(genes), dimnames = list(genes, cells))
X[pairs$ligand, labels == "Alpha"] <- X[pairs$ligand, labels == "Alpha"] + 4
X[pairs$receptor, labels == "Beta"] <- X[pairs$receptor, labels == "Beta"] + 4
X <- Matrix::Matrix(X, sparse = TRUE)

meta <- data.frame(labels = labels, row.names = cells)

# ---- the real calls, in order ----------------------------------------------------------------
cc <- createCellChat(object = X, meta = meta, group.by = "labels")
cc@DB <- db_human
cc <- subsetData(cc)
cc <- identifyOverExpressedGenes(cc)
vf <- unique(unlist(cc@var.features, use.names = FALSE))
vf <- vf[!is.na(vf) & nzchar(vf)]
cat(sprintf("  over-expressed features: %d\n", length(vf)))
if (length(vf) == 0) stop("identifyOverExpressedGenes found nothing on a fixture with a +4 shift")
cc <- identifyOverExpressedInteractions(cc)
cat(sprintf("  candidate interactions after filtering: %d\n", nrow(cc@LR$LRsig)))
if (nrow(cc@LR$LRsig) == 0) stop("identifyOverExpressedInteractions kept no candidate pairs")

cc <- computeCommunProb(cc, type = "triMean")
cc <- filterCommunication(cc, min.cells = 10)
net <- subsetCommunication(cc)

cat(sprintf("  subsetCommunication -> %s rows x %d columns\n",
            format(nrow(net), big.mark = ","), ncol(net)))

# THE POINT OF THIS FILE. Zero rows is the silent failure, so it is checked first and the message
# says what it means.
if (nrow(net) == 0) {
  stop(paste0("computeCommunProb returned NO EDGES on data with a planted ligand-receptor pair. ",
              "That is the failure this selftest exists for: the pipeline runs, reports nothing, ",
              "and a report reads it as 'these cells do not communicate'."))
}
want_cols <- c("source", "target", "ligand", "receptor", "prob", "pval", "interaction_name")
absent <- setdiff(want_cols, names(net))
if (length(absent)) {
  stop(sprintf("the edge table has no %s column(s); the schema moved",
               paste(absent, collapse = ", ")))
}
if (!all(is.finite(net$prob))) stop("communication probabilities contain non-finite values")
if (!any(net$prob > 0))        stop("every communication probability is zero")
if (!all(net$pval >= 0 & net$pval <= 1)) stop("p-values fall outside [0, 1]")

top <- net[order(-net$prob), ][1, ]
cat(sprintf("  strongest: %s -> %s  %s:%s  prob %.3g  p %.3g\n",
            top$source, top$target, top$ligand, top$receptor, top$prob, top$pval))
found <- as.character(net$interaction_name)
cat(sprintf("  planted pair %s recovered: %s\n", planted, planted %in% found))
if (!(planted %in% found)) {
  stop(paste0("the planted ligand-receptor pair is not among the edges recovered. The inference ",
              "ran but did not find an edge built into the fixture."))
}

# The aggregated network is what every CellChat figure is drawn from and it is a separate code
# path from the edge table: a run that produced edges and no aggregate would report empty plots.
cc <- computeCommunProbPathway(cc)
cc <- aggregateNet(cc)
k <- nlevels(labels)
cat(sprintf("  aggregated network: count %dx%d, weight %dx%d\n",
            nrow(cc@net$count), ncol(cc@net$count), nrow(cc@net$weight), ncol(cc@net$weight)))
if (!all(dim(cc@net$count) == c(k, k)) || !all(dim(cc@net$weight) == c(k, k))) {
  stop("the aggregated network is not one cell per pair of groups")
}
if (!all(is.finite(cc@net$weight))) stop("the aggregated weights are not finite")
if (sum(cc@net$count) == 0)         stop("the aggregated network is empty")
cat(sprintf("  signalling pathways with a result: %d\n", length(cc@netP$pathways)))

cat("environment is usable\n")
cat("cellchat selftest OK\n")
