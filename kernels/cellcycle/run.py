#!/usr/bin/env python3
"""cellcycle — score S and G2M phase per cell.

WHY THIS IS THE FIRST KERNEL AND A PREREQUISITE OF PSEUDOTIME

A trajectory that is secretly a cell-cycle axis is the commonest false positive in this class of
analysis: cells order beautifully, the pseudotime correlates with real genes, and what has been
recovered is proliferation. The check costs seconds and it is the reason this kernel exists at the
front rather than as an optional extra.

It also demonstrates the contract with nothing else in the way: read `in.json`, do the work, write
declared outputs and `out.json`. No import of the host, no assumption about the dataset.
"""
from __future__ import annotations

import sys
from pathlib import Path

# The kernel imports the CONTRACT and nothing else from the host. manifest.py is stdlib-only for
# exactly this reason: a kernel in a pinned environment must be able to read it.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scprofile import manifest                                            # noqa: E402

VERSION = "0.1.0"

#: Tirosh et al. regulon, the de-facto standard. HUMAN symbols; title-cased for mouse below.
#: Not tissue-specific and not curated for any particular dataset - which is stated in
#: kernel.yml's `cannot_show`, because a reader deserves to know the panel is generic.
S_GENES = """MCM5 PCNA TYMS FEN1 MCM2 MCM4 RRM1 UNG GINS2 MCM6 CDCA7 DTL PRIM1 UHRF1 CENPU
HELLS RFC2 RPA2 NASP RAD51AP1 GMNN WDR76 SLBP CCNE2 UBR7 POLD3 MSH2 ATAD2 RAD51 RRM2 CDC45 CDC6
EXO1 TIPIN DSCC1 BLM CASP8AP2 USP1 CLSPN POLA1 CHAF1B BRIP1 E2F8""".split()

G2M_GENES = """HMGB2 CDK1 NUSAP1 UBE2C BIRC5 TPX2 TOP2A NDC80 CKS2 NUF2 CKS1B MKI67 TMPO
CENPF TACC3 FAM64A SMC4 CCNB2 CKAP2L CKAP2 AURKB BUB1 KIF11 ANP32E TUBB4B GTSE1 KIF20B HJURP
CDCA3 HN1 CDC20 TTK CDC25C KIF2C RANGAP1 NCAPD2 DLGAP5 CDCA2 CDCA8 ECT2 KIF23 HMMR AURKA PSRC1
ANLN LBR CKAP5 CENPE CTCF NEK2 G2E3 GAS2L3 CBX5 CENPA""".split()


def _match(genes, var_names, organism):
    """The panel genes present in THIS object, matched by casing rather than by assumption.

    An object may be indexed by human symbols, mouse symbols, or something else entirely. Trying
    both casings and reporting how many matched is the difference between a low score that means
    "not cycling" and one that means "the panel did not match your gene names".
    """
    have = {str(v): str(v) for v in var_names}
    upper = {str(v).upper(): str(v) for v in var_names}
    out = []
    for g in genes:
        if g in have:
            out.append(have[g])
        elif g.capitalize() in have:
            out.append(have[g.capitalize()])
        elif g.upper() in upper:
            out.append(upper[g.upper()])
    return out


def main(argv):
    import numpy as np
    import pandas as pd
    import scanpy as sc

    inp = manifest.read_input(argv[1] if len(argv) > 1 else manifest.os.environ["SCPROFILE_IN"])
    out = Path(inp["out_dir"])
    A = sc.read_h5ad(inp["h5ad"])
    organism = (inp.get("organism") or "").lower()
    assay = (inp.get("assay") or "").lower()

    s = _match(S_GENES, A.var_names, organism)
    g2m = _match(G2M_GENES, A.var_names, organism)
    print(f"panel matched: S {len(s)}/{len(S_GENES)}, G2M {len(g2m)}/{len(G2M_GENES)}")

    absent, caveats = [], []
    # A panel that barely matches produces a score that is arithmetically fine and means nothing.
    # Refusing here is better than returning a column somebody will colour a UMAP by.
    if len(s) < 10 or len(g2m) < 10:
        manifest.write_output(
            out, kernel="cellcycle", version=VERSION, status="refused",
            headline=f"panel matched only S {len(s)}, G2M {len(g2m)} genes",
            absent=[{"what": "phase", "why":
                     f"only {len(s)}/{len(S_GENES)} S and {len(g2m)}/{len(G2M_GENES)} G2M panel "
                     f"genes are in this object. That is a gene-NAMING mismatch, not a biological "
                     f"result - check whether var_names are symbols for the right organism."}],
            caveats=["Nothing was scored."])
        print("REFUSED: panel does not match this object's gene names")
        return 0

    if A.X is None:
        raise SystemExit("cellcycle: the object has no X to score")
    sc.tl.score_genes_cell_cycle(A, s_genes=s, g2m_genes=g2m)

    ph = A.obs["phase"].astype(str)
    counts = ph.value_counts()
    cycling_fraction = float((ph != "G1").mean())
    print("phase:", dict(counts))

    # ---------------------------------------------------------------- figures
    # A trajectory that is secretly a cell-cycle axis is what this kernel exists to catch, and
    # that is a claim someone will have to make in print. So it ships the two panels that support
    # it, to the same standard as every other kernel: vector, captioned, with their source data.
    figs = []
    try:
        from scprofile import figure
        plt = figure.use()
        fdir, sdir = out / "figures", out / "figures" / "source_data"
        sdir.mkdir(parents=True, exist_ok=True)
        lab_key = inp["keys"].get("label")
        labs = A.obs[lab_key].astype(str) if lab_key and lab_key in A.obs else None

        # F1: where the cycling cells are, per population.
        if labs is not None:
            ct = pd.crosstab(labs, A.obs["phase"].astype(str))
            for c in ("G1", "S", "G2M"):
                if c not in ct:
                    ct[c] = 0
            ct = ct[["G1", "S", "G2M"]]
            frac = ct.div(ct.sum(axis=1), axis=0).sort_values("G1")
            srcf = sdir / "F1_phase_by_population.csv"
            ct.assign(n_cells=ct.sum(axis=1)).to_csv(srcf)
            fig, ax = plt.subplots(figsize=(figure.SINGLE, max(1.6, 0.20 * len(frac) + 0.9)))
            left = np.zeros(len(frac))
            for c, col in zip(["G1", "S", "G2M"], ["#D9D9D9", "#0072B2", "#D55E00"]):
                ax.barh(np.arange(len(frac)), frac[c], left=left, color=col, label=c, height=.72)
                left += frac[c].values
            ax.set_yticks(np.arange(len(frac))), ax.set_yticklabels(frac.index)
            ax.invert_yaxis(), ax.set_xlim(0, 1), ax.set_xlabel("fraction of cells")
            ax.spines["left"].set_visible(False), ax.tick_params(axis="y", length=0)
            figure.legend_outside(fig, ax)
            figs.append(figure.save(
                fig, fdir, "F1_phase_by_population",
                caption=("Scored cell-cycle phase per population. Phase is SCORED from a gene "
                         "panel, not measured: a cell called G2M is one whose G2M panel genes are "
                         "relatively high. Use this to check whether a trajectory follows the "
                         "cycling fraction - if it does, the trajectory may be a cell-cycle axis."),
                source=srcf, log=print))

        # F2: the scores themselves, which is where a weak panel shows up as a blob at the origin.
        srcs = sdir / "F2_scores.csv"
        dd = {"barcode": A.obs_names.astype(str), "S_score": A.obs["S_score"].values,
              "G2M_score": A.obs["G2M_score"].values, "phase": A.obs["phase"].astype(str).values}
        if labs is not None:
            dd["label"] = labs.values
        pd.DataFrame(dd).to_csv(srcs, index=False)
        fig, ax = plt.subplots(figsize=(figure.SINGLE, figure.SINGLE * 0.9))
        for phase_name, col in (("G1", "#D9D9D9"), ("S", "#0072B2"), ("G2M", "#D55E00")):
            m = A.obs["phase"].astype(str).values == phase_name
            if m.any():
                ax.scatter(A.obs["S_score"].values[m], A.obs["G2M_score"].values[m], s=2, c=col,
                           label=phase_name, linewidths=0, rasterized=True)
        ax.axhline(0, color=figure.INK, lw=.5), ax.axvline(0, color=figure.INK, lw=.5)
        ax.set_xlabel("S score"), ax.set_ylabel("G2M score")
        figure.legend_outside(fig, ax)
        figs.append(figure.save(
            fig, fdir, "F2_scores",
            caption=("S against G2M score, one point per cell; the phase call is which score is "
                     "higher, and positive. A cloud sitting at the origin means the panel found "
                     "little to score - on single nuclei that is expected, because cell-cycle "
                     "transcripts are partly cytoplasmic, and is as consistent with the assay as "
                     "with a resting population."),
            source=srcs, log=print))
    except Exception as e:                                                # noqa: BLE001
        print(f"  figures not drawn: {e}")

    (out / "obs").mkdir(parents=True, exist_ok=True)
    written = {}
    for col in ("phase", "S_score", "G2M_score"):
        f = out / "obs" / f"{col}.csv"
        pd.DataFrame({"barcode": A.obs_names.astype(str), col: A.obs[col].values}).to_csv(
            f, index=False)
        written[col] = str(f)

    caveats.append(
        f"Scored from {len(s)} S and {len(g2m)} G2M panel genes present in this object, out of "
        f"{len(S_GENES)} and {len(G2M_GENES)} declared.")
    if assay == "nucleus":
        caveats.append(
            "This is single-NUCLEUS data. Cell-cycle transcripts are partly cytoplasmic, so "
            "scores are compressed relative to whole cells and a low score is as consistent with "
            "the assay as with a resting population.")
    elif not assay:
        caveats.append(
            "The assay was not declared or detected. If these are nuclei the scores are "
            "compressed; pass --assay nucleus so this is stated rather than left open.")
    frac = cycling_fraction
    caveats.append(
        f"{100 * frac:.1f}% of cells score S or G2M. Read that as 'these genes are relatively "
        f"high', not as a proliferation rate.")

    manifest.write_output(
        out, kernel="cellcycle", version=VERSION, status="ok",
        headline=f"{100 * frac:.1f}% of cells score S or G2M "
                 f"(G1 {int(counts.get('G1', 0)):,}, S {int(counts.get('S', 0)):,}, "
                 f"G2M {int(counts.get('G2M', 0)):,})",
        obs=written, figures=figs, absent=absent, caveats=caveats)
    print("wrote out.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
