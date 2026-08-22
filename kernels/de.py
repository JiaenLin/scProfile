"""Which genes change, per cell type, across the design — tested on pseudobulk.

THE UNIT OF REPLICATION IS THE SAMPLE, NOT THE CELL, and that decision is the whole plugin.
A per-cell test treats thousands of cells from one animal as thousands of independent
observations and inflates significance by roughly the number of cells per animal. So counts are
summed per (sample, population) first, and the test runs over samples.
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "summary": "which genes change, per cell type, across the design",
    "when_to_use": "you have a design table with replicates and want differential expression",
    "wraps": {"tool": "pydeseq2", "homepage": "https://pydeseq2.readthedocs.io",
              "license": "MIT",
              "cite": "Muzellec et al., Bioinformatics 2023 (PyDESeq2); "
                      "Love et al., Genome Biol 2014 (DESeq2)"},
    "upstream": {
        "docs": "https://pydeseq2.readthedocs.io",
        "read": "2026-08-22",
        "defaults_changed": [
            "refit_cooks=True is kept, but the sample sizes here are small and Cook's filtering "
            "is what keeps one outlier animal from carrying a gene. It is named because it "
            "silently changes results.",
            "A design formula is BUILT FROM THE DESIGN TABLE, never assumed. The plan chooses "
            "the richest contrast the design supports and passes it in params.",
        ],
        "not_used": [
            "LFC shrinkage (lfc_shrink): it changes the ranking and is a presentation choice, "
            "so it belongs to whoever reads the table, not to this plugin.",
            "Per-cell testing. It is offered by other tools and is never defaulted to here.",
        ],
        "gotchas": [
            "PyDESeq2 requires integer counts and will happily run on log-normalised values, "
            "returning a full table that means nothing. The counts capability is required for "
            "exactly that reason.",
            "A population present in only one arm produces coefficients with no contrast. Those "
            "populations are skipped and named.",
        ],
    },

    "inject": {"required": ["counts", "label", "sample", "design"],
               "optional": ["contrast"]},
    "provides": [],
    "produces": ["tables/de_by_population.csv"],

    "config": {
        "min_cells": {"type": "int", "default": 10, "min": 1,
                      "help": "a (sample, population) cell with fewer cells than this is not "
                              "summed into a pseudobulk sample - it is noise wearing a "
                              "sample's name"},
        "min_samples_per_level": {"type": "int", "default": 2, "min": 2,
                                  "help": "a population needs this many samples in every level "
                                          "of the contrast, or there is no within-group variance"},
        "min_counts": {"type": "int", "default": 10, "min": 0,
                       "help": "genes below this total across pseudobulk samples are dropped "
                               "before testing, which is a power decision and not a filter on "
                               "biology"},
        "alpha": {"type": "float", "default": 0.05, "min": 0.0, "max": 1.0,
                  "help": "the adjusted-p threshold reported as significant; the full table is "
                          "written regardless"},
    },

    # pydeseq2 was measured as ADDITIVE to a modern scanpy stack, so this shares whatever
    # environment the builder resolves for that stack rather than asking for one of its own.
    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {"pydeseq2": ">=0.4,<0.6", "pandas": ">=2.0,<3", "numpy": ">=1.24,<3"},
    },

    "cost": "medium", "cores": 4,

    "cannot_show": [
        "A gene absent from the object was not tested, and its absence is not evidence of no "
        "change.",
        "PSEUDOBULK CANNOT SEE A CHANGE CONFINED TO A SUBPOPULATION of a labelled type; it "
        "averages it away. A negative result here is a statement about the population as "
        "labelled.",
        "A coefficient in a confounded design is not interpretable in isolation, whatever its "
        "p-value. Where the plan found a confound it is reproduced in the caveats.",
        "Per-cell testing treats cells from one animal as independent and inflates significance "
        "by roughly the number of cells per animal. It is not offered here.",
    ],
}


def _pseudobulk(ctx, np, pd):
    """Sum counts per (sample, population). Returns (matrix, obs) or refuses."""
    counts = ctx.counts()
    samp = ctx.obs("sample").astype(str).to_numpy()
    lab = ctx.obs("label").astype(str).to_numpy()
    real = np.asarray(ctx.real_cells())

    keys, rows, meta = {}, [], []
    for i, (s, l) in enumerate(zip(samp, lab)):
        if not real[i]:
            continue
        keys.setdefault((s, l), []).append(i)

    small = 0
    for (s, l), idx in sorted(keys.items()):
        if len(idx) < ctx.config["min_cells"]:
            small += 1
            continue
        sub = counts[idx]
        rows.append(np.asarray(sub.sum(axis=0)).ravel())
        meta.append({"sample": s, "population": l, "n_cells": len(idx)})
    if small:
        ctx.caveat(f"{small} (sample, population) combination(s) had fewer than "
                   f"{ctx.config['min_cells']} cells and were not summed into a pseudobulk "
                   f"sample. A handful of cells carrying a sample's name is noise, not a "
                   f"replicate.")
    if not rows:
        return None, None
    return np.vstack(rows), pd.DataFrame(meta)


def run(ctx):
    import numpy as np
    import pandas as pd
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats

    design = ctx.design_table()
    if not design:
        return ctx.refuse("differential expression",
                          "the design table could not be read, so there is no contrast")

    terms = list((ctx.params.get("contrast") or {}).get("terms")
                 or ctx.testable_factors() or [])
    if not terms:
        return ctx.refuse("differential expression",
                          "no factor in the design has two levels with replication in each. A "
                          "test over singletons returns a p-value and no evidence.")

    mat, obs = _pseudobulk(ctx, np, pd)
    if mat is None:
        return ctx.refuse("differential expression",
                          "no (sample, population) combination had enough cells to form a "
                          "pseudobulk sample")

    for t in terms:
        obs[t] = [str(design.get(s, {}).get(t, "")) for s in obs["sample"]]
    ctx.log(f"pseudobulk: {mat.shape[0]} sample-population rows x {mat.shape[1]:,} genes, "
            f"terms {', '.join(terms)}")

    genes = np.asarray(ctx.adata.var_names).astype(str)
    out, skipped = [], []
    for pop in sorted(set(obs["population"])):
        m = obs["population"].to_numpy() == pop
        sub_obs = obs[m].reset_index(drop=True)
        # EVERY LEVEL NEEDS REPLICATION, not just the population overall. A population with six
        # samples in one arm and one in the other supports no test of that contrast, and a mean
        # n hides exactly that.
        thin = [t for t in terms
                if sub_obs[t].value_counts().min() < ctx.config["min_samples_per_level"]
                or sub_obs[t].nunique() < 2]
        if thin:
            skipped.append((pop, int(m.sum()), thin))
            continue

        sub = mat[m]
        keep = sub.sum(axis=0) >= ctx.config["min_counts"]
        counts_df = pd.DataFrame(np.rint(sub[:, keep]).astype(int),
                                 index=[f"s{i}" for i in range(int(m.sum()))],
                                 columns=genes[keep])
        sub_obs.index = counts_df.index

        formula = "~ " + " + ".join(terms)
        if len(terms) >= 2 and (ctx.params.get("contrast") or {}).get("kind") == "interaction":
            formula = f"~ {terms[0]} + {terms[1]} + {terms[0]}:{terms[1]}"
        dds = DeseqDataSet(counts=counts_df, metadata=sub_obs, design=formula,
                           refit_cooks=True, n_cpus=ctx.cores, quiet=True)
        dds.deseq2()
        for term in terms:
            levels = sorted(sub_obs[term].unique())
            st = DeseqStats(dds, contrast=[term, levels[-1], levels[0]],
                            alpha=ctx.config["alpha"], quiet=True)
            st.summary()
            r = st.results_df.copy()
            r["population"], r["term"] = pop, term
            r["contrast"] = f"{levels[-1]} vs {levels[0]}"
            r["gene"] = r.index
            out.append(r)
        ctx.log(f"  {pop}: {int(m.sum())} pseudobulk samples, {int(keep.sum()):,} genes tested")

    if skipped:
        ctx.caveat("Not tested, because a level of the contrast had fewer than "
                   f"{ctx.config['min_samples_per_level']} samples: "
                   + "; ".join(f"{p} (n={n}, {', '.join(t)})" for p, n, t in skipped) + ".")
        for p, n, t in skipped:
            ctx.absent.append({"what": f"differential expression for {p}",
                               "why": f"{', '.join(t)} has a level with too few samples (n={n})"})
    if not out:
        return ctx.refuse("differential expression",
                          "no population had replication in every level of any factor")

    res = pd.concat(out, ignore_index=True).sort_values(["population", "term", "padj"])
    ctx.emit_table("de_by_population", res.set_index("gene"))
    sig = int((res["padj"] < ctx.config["alpha"]).sum())
    ctx.headline = (f"{sig:,} gene-population-term results below padj {ctx.config['alpha']} "
                    f"across {res['population'].nunique()} population(s), "
                    f"formula ~ {' + '.join(terms)}")
    ctx.caveat("The unit of replication is the SAMPLE. Counts were summed per (sample, "
               "population) before testing, so no p-value here is inflated by cell count.")


def selftest(ctx):
    """Prove the call works: the API, the schema, and that a planted effect is recovered.

    A test that only asserted the table has rows would pass on a broken model. The fixture plants
    a real fold-change in a known set of genes and requires them back, because that is what would
    break silently if PyDESeq2's contrast argument or results schema moved.
    """
    import numpy as np
    import pandas as pd
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats

    rng = np.random.default_rng(0)
    n_s, n_g = 8, 200
    base = rng.integers(50, 500, size=n_g)
    cond = np.array(["ctrl"] * 4 + ["treat"] * 4)
    up = np.arange(20)                                  # the planted effect
    mat = np.vstack([rng.poisson(base * (1 + 3.0 * np.isin(np.arange(n_g), up) * (c == "treat")))
                     for c in cond])
    counts = pd.DataFrame(mat.astype(int), index=[f"s{i}" for i in range(n_s)],
                          columns=[f"g{j}" for j in range(n_g)])
    meta = pd.DataFrame({"cond": cond}, index=counts.index)

    dds = DeseqDataSet(counts=counts, metadata=meta, design="~ cond", quiet=True)
    dds.deseq2()
    st = DeseqStats(dds, contrast=["cond", "treat", "ctrl"], quiet=True)
    st.summary()
    r = st.results_df
    for col in ("log2FoldChange", "pvalue", "padj", "baseMean"):
        assert col in r.columns, f"results_df has no {col!r}; PyDESeq2's schema moved"
    assert len(r) == n_g, f"{len(r)} rows for {n_g} genes"

    hits = set(r[r["padj"] < 0.05].index)
    planted = {f"g{j}" for j in up}
    found = len(hits & planted)
    assert found >= 15, (
        f"only {found} of 20 planted genes were recovered. The model ran and did not find an "
        f"effect built into the fixture - either the contrast argument changed meaning or the "
        f"fit is wrong, and both would return a full, plausible, empty table on real data.")
    assert (r.loc[sorted(planted), "log2FoldChange"] > 0).mean() > 0.9, \
        "the planted genes came back with the wrong SIGN - the contrast is inverted"
    ctx.log(f"  recovered {found}/20 planted genes, correct sign")
