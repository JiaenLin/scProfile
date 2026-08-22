"""Whether a population's share shifts across the design.

COMPOSITION IS RELATIVE BY CONSTRUCTION and that governs everything here. Shares must sum to one,
so one population rising makes every other fall arithmetically, and a test that ignores this
reports every population as changed when one did. scCODA handles it by testing against a
reference population and reporting credible inclusion rather than a p-value.

The reference is therefore the single most consequential setting in this plugin, and it is
declared config with an automatic choice that is NAMED in the result — never silently picked.
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "summary": "whether a population's share shifts across the design",
    "when_to_use": "you have a design table and want to know whether composition changed",
    "wraps": {"tool": "pertpy", "homepage": "https://pertpy.readthedocs.io",
              "license": "MIT",
              "cite": "Büttner et al., 2024 (pertpy); "
                      "Büttner et al., Nat Commun 2021 (scCODA)"},
    "upstream": {
        "docs": "https://pertpy.readthedocs.io/en/latest/usage/usage.html#composition",
        "read": "2026-08-22",
        "defaults_changed": [
            "reference_cell_type is chosen explicitly rather than left to 'automatic'. It is the "
            "most consequential setting in the method - every effect is relative to it - and a "
            "silent choice produces a full result whose meaning nobody can state.",
            "fdr is passed through from config rather than left at the library default, because "
            "the credible-inclusion threshold is what turns the posterior into a claim.",
        ],
        "not_used": [
            "tascCODA, which uses a hierarchy over cell types. It is a better answer where a "
            "hierarchy exists and needs one declared; that is a different plugin, not a flag.",
            "Milo. It tests neighbourhoods rather than labelled populations and answers a "
            "different question; it belongs beside this, not inside it.",
        ],
        "gotchas": [
            "scCODA is Bayesian: it returns credible inclusion, not a p-value, and reading its "
            "output as significance is a category error the result text guards against.",
            "With few samples per arm the posterior is dominated by the prior. The sample counts "
            "are reported beside the result for that reason.",
        ],
    },

    "inject": {"required": ["label", "sample", "design"], "optional": ["contrast"]},
    "provides": [],
    "produces": ["tables/abundance_by_population.csv", "tables/abundance_counts.csv"],

    "config": {
        "reference": {"type": "str", "default": "auto",
                      "help": "the population every effect is relative to. 'auto' picks the one "
                              "with the most stable share across samples and NAMES it in the "
                              "result; any population name pins it"},
        "fdr": {"type": "float", "default": 0.05, "min": 0.0, "max": 1.0,
                "help": "the credible-inclusion threshold scCODA uses to call an effect"},
        "min_samples_per_level": {"type": "int", "default": 2, "min": 2,
                                  "help": "a factor needs this many samples in every level, or "
                                          "the posterior is the prior"},
    },

    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {"pertpy": ">=0.9,<2", "pandas": ">=2.0,<3", "numpy": ">=1.24,<3"},
    },

    "cost": "medium", "cores": 4,

    "cannot_show": [
        "COMPOSITION IS RELATIVE BY CONSTRUCTION. One population rising makes every other fall, "
        "and which one actually moved is not recoverable from shares alone - that is what the "
        "reference population is for, and it is named in the result.",
        "Absolute cell numbers are not measured. A share is not a count of cells in a tissue: "
        "dissociation and QC both change what reaches the object, and neither is uniform across "
        "cell types.",
        "A shift measured after a batch correction cannot be separated from what the correction "
        "removed.",
        "scCODA returns CREDIBLE INCLUSION, not a p-value. Reading it as significance is a "
        "category error.",
    ],
}


def _counts_frame(ctx, pd, np):
    """A samples x populations count matrix, sentinels excluded and named."""
    samp = ctx.obs("sample").astype(str).to_numpy()
    pops, dropped = ctx.populations()
    lab = ctx.obs("label").astype(str).to_numpy()
    real = np.asarray(ctx.real_cells())
    tab = (pd.crosstab(pd.Series(samp[real], name="sample"),
                       pd.Series(lab[real], name="population")))
    return tab.loc[:, [p for p in tab.columns if p in set(pops)]], dropped


def run(ctx):
    import numpy as np
    import pandas as pd
    import pertpy as pt

    design = ctx.design_table()
    terms = list((ctx.params.get("contrast") or {}).get("terms")
                 or ctx.testable_factors(min_replicates=ctx.config["min_samples_per_level"]))
    if not terms:
        return ctx.refuse("compositional test",
                          f"no factor has two levels with at least "
                          f"{ctx.config['min_samples_per_level']} samples in each. With fewer, "
                          f"the posterior is the prior.")

    tab, dropped = _counts_frame(ctx, pd, np)
    if dropped:
        ctx.caveat(f"{len(dropped)} annotator sentinel(s) excluded from the composition: "
                   f"{', '.join(dropped)}. A sentinel is a refusal to call a cell type; counting "
                   f"it as a population would make every share depend on how often the annotator "
                   f"declined.")
    if tab.shape[1] < 2:
        return ctx.refuse("compositional test",
                          f"only {tab.shape[1]} population(s) remain. A compositional test needs "
                          f"at least two, because it measures shares of a whole.")

    for t in terms:
        tab[t] = [str(design.get(s, {}).get(t, "")) for s in tab.index]
    ctx.emit_table("abundance_counts", tab)

    pops = [c for c in tab.columns if c not in terms]
    # THE REFERENCE IS THE MOST CONSEQUENTIAL SETTING and is never silently chosen. 'auto' takes
    # the population whose share varies least across samples, which is the closest thing to "did
    # not move" the data offers - and the choice is stated in the headline either way.
    ref = ctx.config["reference"]
    if ref == "auto":
        share = tab[pops].div(tab[pops].sum(axis=1), axis=0)
        ref = str(share.std().idxmin())
        why = "chosen automatically: its share varies least across samples"
    elif ref not in pops:
        return ctx.refuse("compositional test",
                          f"reference population {ref!r} is not present. Available: "
                          f"{', '.join(pops)}")
    else:
        why = "given in config"
    ctx.log(f"reference population: {ref} ({why})")

    import anndata as ad
    out = []
    sccoda = pt.tl.Sccoda()
    for term in terms:
        adata = ad.AnnData(tab[pops].to_numpy().astype(float),
                           obs=pd.DataFrame({term: tab[term].to_numpy()},
                                            index=tab.index.astype(str)),
                           var=pd.DataFrame(index=pd.Index(pops, name="population")))
        mdata = sccoda.load(adata, type="cell_level" if False else "sample_level",
                            covariate_obs=[term]) if hasattr(sccoda, "load") else adata
        model = sccoda.prepare(mdata if hasattr(sccoda, "prepare") else adata,
                               formula=term, reference_cell_type=ref)
        sccoda.run_nuts(model, num_samples=1000, num_warmup=500, rng_key=0)
        res = sccoda.credible_effects(model, est_fdr=ctx.config["fdr"])
        df = res.reset_index() if hasattr(res, "reset_index") else pd.DataFrame(res)
        df["term"], df["reference"] = term, ref
        out.append(df)
        ctx.log(f"  {term}: {int(np.asarray(res).sum())} credible effect(s)")

    res = pd.concat(out, ignore_index=True)
    ctx.emit_table("abundance_by_population", res)
    n = int(res.select_dtypes("bool").to_numpy().sum()) if not res.empty else 0
    sizes = {t: dict(tab[t].value_counts()) for t in terms}
    ctx.headline = (f"{n} credible compositional effect(s) at fdr {ctx.config['fdr']} over "
                    f"{len(pops)} population(s), relative to {ref}")
    ctx.caveat(f"Every effect is RELATIVE TO {ref!r} ({why}). A different reference gives a "
               f"different set of moved populations from the same data, and neither is more "
               f"correct - that is what compositional means.")
    ctx.caveat(f"Sample counts per level: {sizes}. With few samples per arm the posterior is "
               f"dominated by the prior.")


def selftest(ctx):
    """Prove the call works AND that a planted compositional shift is recovered.

    A test asserting only that a table came back would pass on a model that had learned nothing.
    The fixture moves one population's share hard between arms and requires scCODA to call it.
    """
    import numpy as np
    import pandas as pd
    import pertpy as pt
    import anndata as ad

    rng = np.random.default_rng(0)
    pops = [f"pop{i}" for i in range(4)]
    rows, cond = [], []
    for i in range(10):
        treat = i >= 5
        base = np.array([300.0, 300.0, 300.0, 300.0])
        if treat:
            base[0] *= 3.0                      # the planted shift
        rows.append(rng.poisson(base))
        cond.append("treat" if treat else "ctrl")
    tab = pd.DataFrame(np.vstack(rows), columns=pops,
                       index=[f"s{i}" for i in range(10)]).astype(float)

    adata = ad.AnnData(tab.to_numpy(),
                       obs=pd.DataFrame({"cond": cond}, index=tab.index),
                       var=pd.DataFrame(index=pd.Index(pops, name="population")))
    sccoda = pt.tl.Sccoda()
    model = sccoda.prepare(adata, formula="cond", reference_cell_type="pop3")
    sccoda.run_nuts(model, num_samples=500, num_warmup=250, rng_key=0)
    res = sccoda.credible_effects(model, est_fdr=0.05)
    arr = np.asarray(res)
    assert arr.size >= len(pops), f"credible_effects returned {arr.shape}, expected one per population"
    ctx.log(f"  scCODA ran; {int(arr.sum())} credible effect(s) on a fixture with one planted")
    assert int(arr.sum()) >= 1, (
        "scCODA found NO credible effect on a fixture where one population's share was tripled "
        "between arms. The model ran and learned nothing - on real data it would return a full "
        "table of no-change, which is indistinguishable from a real negative.")
