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
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "summary": "cell-cell communication, CellChat's own database and scoring",
    "when_to_use": "you want a second communication method to hold beside the first",
    "wraps": {"tool": "CellChat", "homepage": "https://github.com/jinworks/CellChat",
              "license": "GPL-3.0",
              "cite": "Jin et al., Nat Commun 2021 (CellChat)"},
    "upstream": {
        "docs": "https://github.com/jinworks/CellChat",
        "read": "2026-08-22",
        "defaults_changed": [
            "identifyOverExpressedGenes(do.fast = FALSE). The default is TRUE and HARD-REQUIRES "
            "`presto`, a Suggests-only package not on CRAN - it stops rather than falling back. "
            "presto is in the requirement for that reason; do.fast is left at its default so the "
            "path everyone else uses is the path tested.",
            "computeCommunProb(type = 'triMean') is CellChat's own default and is kept, but it "
            "is named because it is a strong choice: triMean returns zero for a population where "
            "fewer than 25% of cells express the gene, which is a filter wearing a statistic.",
        ],
        "not_used": [
            "netAnalysis_signalingRole and the pattern-learning functions: they are a second "
            "question over the same edges and belong beside this, not inside it.",
            "The spatial mode - this object carries no coordinates.",
        ],
        "gotchas": [
            "CellChatDB is bundled IN the package, so its version is pinned by the package "
            "version and nothing else records which database produced a result. It is written "
            "into the caveats here for that reason.",
            "A population with very few cells produces unstable probabilities; CellChat's own "
            "min.cells is exposed as config rather than left at its default.",
        ],
    },

    "inject": {"required": ["lognorm", "label", "organism"], "optional": ["sample"]},
    "provides": ["communication"],
    "produces": ["tables/ccc_edges.csv"],
    "per_unit": "sample",

    "config": {
        "min_cells": {"type": "int", "default": 10, "min": 1,
                      "help": "populations smaller than this are dropped by CellChat before "
                              "scoring; below it the probabilities are unstable"},
        "trim": {"type": "float", "default": 0.1, "min": 0.0, "max": 0.5,
                 "help": "trimmed mean fraction for computeCommunProb"},
    },

    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {"anndata": ">=0.10,<0.12", "pandas": ">=2.0,<3", "scipy": ">=1.10"},
        "language": "r",
        "r": ["NMF==0.28",
              "immunogenomics/presto@7eb75c4c0a0cf8fc49c705f0975bb3650c51e114",
              "jinworks/CellChat@75253cd0c9e68410e6e721a6d3a0419a1d7e358f"],
        "conda": {"r-base": "4.3", "r-matrix": "", "r-ggplot2": "", "r-igraph": "",
                  "r-remotes": ""},
        "channels": ["conda-forge", "bioconda"],
    },

    "cost": "medium", "cores": 4,

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
    ],
}

#: CellChat ships one database per species. An organism it has none for is refused rather than
#: silently scored against the human one.
_DB = {"human": "CellChatDB.human", "mouse": "CellChatDB.mouse"}

_R = r'''
suppressMessages({library(CellChat); library(Matrix)})
args <- commandArgs(trailingOnly = TRUE)
mtx <- args[1]; meta_f <- args[2]; db_name <- args[3]
min_cells <- as.integer(args[4]); trim <- as.numeric(args[5]); out <- args[6]

X <- as(Matrix::readMM(mtx), "CsparseMatrix")
meta <- read.csv(meta_f, row.names = 1, stringsAsFactors = FALSE)
rownames(X) <- read.csv(paste0(mtx, ".genes"), header = FALSE)[[1]]
colnames(X) <- rownames(meta)

cc <- createCellChat(object = X, meta = meta, group.by = "label")
cc@DB <- get(db_name)
cc <- subsetData(cc)
cc <- identifyOverExpressedGenes(cc)
cc <- identifyOverExpressedInteractions(cc)
cc <- computeCommunProb(cc, type = "triMean", trim = trim)
cc <- filterCommunication(cc, min.cells = min_cells)
df <- subsetCommunication(cc)
write.csv(df, out, row.names = FALSE)
cat("edges:", nrow(df), "\n")
'''


def run(ctx):
    import subprocess
    import numpy as np
    import pandas as pd
    from scipy import io as sio
    from scipy import sparse

    db = _DB.get(ctx.organism)
    if not db:
        return ctx.refuse("cell-cell communication",
                          f"CellChat ships no database for {ctx.organism!r}. Known: "
                          f"{', '.join(sorted(_DB))}. Scoring against another species' database "
                          f"returns a small plausible table rather than failing.")

    pops, dropped = ctx.populations()
    if len(pops) < 2:
        return ctx.refuse("cell-cell communication",
                          f"only {len(pops)} population(s); communication needs two to be "
                          f"between.")
    if dropped:
        ctx.caveat(f"{len(dropped)} annotator sentinel(s) excluded: {', '.join(dropped)}.")

    real = np.asarray(ctx.real_cells())
    A = ctx.adata[real]
    X = ctx.X[real] if ctx.X.shape[0] == ctx.adata.n_obs else A.X
    mtx = ctx.out / "cellchat_expr.mtx"
    # GENES x CELLS: CellChat's convention, and transposing in the wrong place is the classic way
    # to get a full, plausible, meaningless result out of it.
    sio.mmwrite(str(mtx), sparse.csr_matrix(X).T.tocoo())
    pd.Series(np.asarray(A.var_names).astype(str)).to_csv(
        str(mtx) + ".genes", index=False, header=False)
    meta = ctx.out / "cellchat_meta.csv"
    pd.DataFrame({"label": A.obs[ctx.keys["label"]].astype(str).to_numpy()},
                 index=A.obs_names.astype(str)).to_csv(meta)

    script = ctx.out / "cellchat.R"
    script.write_text(_R, encoding="utf-8")
    edges = ctx.out / "tables" / "ccc_edges.csv"

    rscript = ctx.params.get("rscript") or "Rscript"
    ctx.log(f"handing {A.n_obs:,} cells x {A.n_vars:,} genes to {db} via {rscript}")
    proc = subprocess.run([rscript, str(script), str(mtx), str(meta), db,
                           str(ctx.config["min_cells"]), str(ctx.config["trim"]), str(edges)],
                          capture_output=True, text=True)
    for line in (proc.stdout or "").splitlines()[-8:]:
        ctx.log(f"  R: {line}")
    if proc.returncode != 0 or not edges.exists():
        tail = (proc.stderr or "").strip().splitlines()[-6:]
        return ctx.refuse("cell-cell communication",
                          "CellChat did not produce an edge table. R said: "
                          + " | ".join(tail))

    df = pd.read_csv(edges)
    ctx.emit_table("ccc_edges", df.set_index(df.columns[0]))
    ctx.headline = f"{len(df):,} interactions over {len(pops)} populations, {db}"
    ctx.caveat(f"Database: {db}, bundled in the pinned CellChat package. Its version is fixed by "
               f"the package version and by nothing else, so two runs on different CellChat "
               f"versions are two databases.")
    ctx.caveat("Scores are CellChat's own scale and are not comparable with another method's; "
               "only the ranking can be compared.")


def selftest(ctx):
    """Prove R, CellChat, its database and the bridge — not just that the package imports.

    The R side is the part that breaks: a Suggests-only package a default code path requires, a
    database object renamed, a function moved. Running the real pipeline on a tiny fixture is the
    only thing that sees any of it.
    """
    import subprocess
    import shutil

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
