"""Cell–cell communication: a ranked ligand–receptor table, per unit.

NO INTERACTION IS OBSERVED. These are co-expression of a ligand and a receptor in two
populations, with no spatial information — on dissociated tissue the two cells may never have
touched. That is the first thing in `cannot_show` and the first thing the result says.

It runs PER UNIT because an inference pooled over a cohort describes the average of its
conditions and may describe none of them. The host fans it out; this file sees one unit.
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "summary": "cell-cell communication, consensus over several scoring methods",
    "when_to_use": "you want a ligand-receptor map and, with a design, how it differs between "
                   "conditions",
    "wraps": {"tool": "liana", "homepage": "https://liana-py.readthedocs.io",
              "license": "GPL-3.0",
              "cite": "Dimitrov et al., Nat Commun 2022 (LIANA); "
                      "Türei et al., Mol Syst Biol 2021 (OmniPath)"},
    "upstream": {
        "docs": "https://liana-py.readthedocs.io",
        "read": "2026-08-22",
        "defaults_changed": [
            "resource_name is chosen BY ORGANISM. The default is `consensus`, which is HUMAN, "
            "and a human resource on non-human symbols does not error - it returns a small, "
            "plausible table. That is the failure this plugin exists to avoid.",
            "use_raw=False. The default follows .raw, which on an annotated object usually holds "
            "pre-filter counts - a different matrix from the one the user is looking at.",
            "expr_prop is exposed as config rather than left at the library default, because it "
            "decides how many interactions survive and is the knob people actually turn.",
        ],
        "not_used": [
            "The single-method calls (cellphonedb, natmi, ...). rank_aggregate runs them and "
            "aggregates, which is the point of the tool; using one alone is a different claim.",
            "liana's spatial functions - this object carries no spatial information.",
        ],
        "gotchas": [
            "rank_aggregate REFUSES when more than 98% of the resource's genes are missing from "
            "var_names. That check is correct and is the signature of a resource for the wrong "
            "organism; it is reported as a refusal rather than caught and hidden.",
            "Ligand and receptor transcripts are partly cytoplasmic, so a single-nucleus "
            "preparation reports fewer of them and a low interaction count is as consistent with "
            "the assay as with the biology.",
        ],
    },

    "inject": {"required": ["lognorm", "label", "organism"], "optional": ["sample"]},
    "provides": ["communication"],
    "produces": ["tables/ccc_edges.csv"],
    "per_unit": "sample",

    "config": {
        "expr_prop": {"type": "float", "default": 0.1, "min": 0.0, "max": 1.0,
                      "help": "a gene must be expressed in this proportion of a population to "
                              "count; it decides how many interactions survive"},
        "top_n": {"type": "int", "default": 0, "min": 0,
                  "help": "keep only this many top-ranked interactions, 0 for all. The full "
                          "table is the honest artifact; this is for a figure"},
    },

    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {"liana": ">=1.3,<2", "scanpy": ">=1.10,<1.11",
                     "anndata": ">=0.10,<0.12", "numpy": ">=1.24,<2", "pandas": ">=2.0,<3"},
    },

    "cost": "medium", "cores": 8,

    "cannot_show": [
        "NO INTERACTION IS OBSERVED. These are co-expression of a ligand and a receptor in two "
        "populations, with no spatial information - on dissociated tissue the cells may never "
        "have touched.",
        "A rank is WITHIN this dataset. It is not a strength comparable to another dataset's.",
        "The resource decides the answer. On the wrong organism it does not error; it returns a "
        "small plausible table.",
        "Ligand and receptor transcripts are partly cytoplasmic, so a single-nucleus preparation "
        "reports fewer of them and a low count is as consistent with the assay as with biology.",
    ],
}

#: Resource per organism. Anything not here is refused rather than defaulted to the human one.
_RESOURCE = {"human": "consensus", "mouse": "mouseconsensus"}


def run(ctx):
    import liana as li

    res_name = _RESOURCE.get(ctx.organism)
    if not res_name:
        return ctx.refuse(
            "cell-cell communication",
            f"no ligand-receptor resource is declared for {ctx.organism!r}. The default resource "
            f"is human and would return a small plausible table on other symbols rather than "
            f"failing. Known: {', '.join(sorted(_RESOURCE))}.")

    # `ctx.populations()` unpacks as (mask, groups); `.names` and `.dropped` are what this wants.
    # It read the two-tuple as (populations, dropped), so `len(pops)` was the CELL COUNT - the
    # refusal below could never fire and the headline would have claimed 100,713 populations -
    # and `if dropped:` asked the truth value of a numpy array, which raises. Fourth plugin to
    # misread it, which is a statement about the affordance and not about four authors.
    pop = ctx.populations()
    if len(pop.names) < 2:
        return ctx.refuse("cell-cell communication",
                          f"only {len(pop.names)} population(s) here; communication needs at "
                          f"least two to be between.")
    if pop.dropped:
        ctx.caveat(f"{len(pop.dropped)} annotator sentinel(s) excluded as senders and receivers: "
                   f"{', '.join(pop.dropped)}. A sentinel is a refusal to call a cell type, and "
                   f"an interaction attributed to one names nothing.")

    lab = ctx.keys["label"]
    A = ctx.adata[ctx.real_cells()].copy()
    A.X = ctx.X if ctx.X.shape[0] == A.n_obs else A.X
    ctx.log(f"{A.n_obs:,} cells, {len(pop.names)} populations, resource {res_name}")

    li.mt.rank_aggregate(A, groupby=lab, resource_name=res_name,
                         expr_prop=ctx.config["expr_prop"],
                         use_raw=False, verbose=False, seed=0, n_perms=100)
    edges = A.uns["liana_res"].copy()
    if ctx.config["top_n"]:
        edges = edges.nsmallest(ctx.config["top_n"], "magnitude_rank")
    ctx.emit_table("ccc_edges", edges.set_index("source"))

    top = edges.nsmallest(3, "magnitude_rank")
    ctx.headline = (f"{len(edges):,} interactions over {len(pop.names)} populations"
                    + (f"; strongest {top.iloc[0]['source']} -> {top.iloc[0]['target']} "
                       f"({top.iloc[0]['ligand_complex']}:{top.iloc[0]['receptor_complex']})"
                       if len(top) else ""))
    ctx.caveat(f"Resource {res_name!r} for {ctx.organism}. The resource decides the answer, and "
               f"the wrong one returns a small plausible table rather than an error.")
    if ctx.assay == "nucleus":
        ctx.caveat("Single-nucleus: ligand and receptor transcripts are partly cytoplasmic, so a "
                   "low interaction count is as consistent with the assay as with the biology.")


def selftest(ctx):
    """Prove the resource loads OFFLINE and that scoring recovers a planted pair.

    Offline matters as much as the schema: a compute node may have no outbound route, and a
    resource that needs the network is a plugin that cannot run in a batch job at all.
    """
    import liana as li
    import numpy as np

    for organism, name in sorted(_RESOURCE.items()):
        r = li.resource.select_resource(name)
        assert len(r) > 1000, f"{name} looks truncated: {len(r)} interactions"
        for col in ("ligand", "receptor"):
            assert col in r.columns, f"{name} has no {col!r} column; its schema moved"
        ctx.log(f"  {name} ({organism}): {len(r):,} interactions, loaded offline")

    res = li.resource.select_resource(_RESOURCE["mouse"])
    # THE FIXTURE IS BUILT FROM THE RESOURCE. liana refuses when >98% of the resource is absent
    # from var_names - correctly, since that is the signature of the wrong organism - so a
    # fixture of arbitrary gene names tests the refusal and not the scoring.
    genes = sorted({g for g in list(res["ligand"]) + list(res["receptor"])
                    if isinstance(g, str) and "_" not in g})[:600]
    pair = res.iloc[0]
    A = ctx.fixture(n_cells=200, genes=genes, labels=("Alpha", "Beta"))
    A.X = A.layers["lognorm"]
    lig, rec = str(pair["ligand"]), str(pair["receptor"])
    if lig in genes and rec in genes:
        gi = {g: i for i, g in enumerate(genes)}
        m = np.asarray(A.X.todense() if hasattr(A.X, "todense") else A.X)
        m[A.obs["label"] == "Alpha", gi[lig]] += 20
        m[A.obs["label"] == "Beta", gi[rec]] += 20
        A.X = m

    li.mt.rank_aggregate(A, groupby="label", resource_name=_RESOURCE["mouse"],
                         expr_prop=0.1, use_raw=False, verbose=False, seed=0, n_perms=10)
    out = A.uns["liana_res"]
    for col in ("source", "target", "ligand_complex", "receptor_complex", "magnitude_rank"):
        assert col in out.columns, f"liana_res has no {col!r}; the schema moved"
    assert len(out) > 0, "rank_aggregate returned no rows on a fixture built from its own resource"
    assert np.isfinite(out["magnitude_rank"].to_numpy(dtype=float)).all(), \
        "magnitude_rank contains non-finite values"
    ctx.log(f"  rank_aggregate: {len(out):,} rows x {out.shape[1]} columns")
