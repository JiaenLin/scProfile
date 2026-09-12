"""Which curated gene sets describe a population's own markers - ranked cell-population-vs-rest,
tested against a curated library with gseapy's preranked GSEA (`gseapy.prerank`).

WHY PRERANK AND NOT gseapy's TWO-PHENOTYPE MODE

gseapy also ships `gsea()` / `GSEA`, the classic two-phenotype permutation test - but that
compares SAMPLES carrying a phenotype label, and needs replicate samples in each phenotype. This
plugin is handed cells and a label column, not phenotype-labelled samples, so the matching entry
point is prerank: rank every gene once per population (this population's cells against the rest
of the object's real cells) and test the ranked list against a gene-set library. See
`upstream.not_used` for the tool's other entry points and why each is not this one.

WHAT THE PAGE HAS TO SHOW BEFORE THE ANSWER IS WORTH READING

  THE RANKING IS A DESCRIPTION OF THIS OBJECT, NOT A DESIGN CONTRAST. Signal-to-noise ranks a
      population against the REST OF THE SAME COHORT's cells; it is not a comparison across a
      design's arms; `de` is design-aware, and this is not the same claim.
  A GENE SET ABSENT FROM THE CONFIGURED LIBRARY CANNOT BE FOUND, however real the underlying
      biology - and a wrong-organism or wrong-symbol library returns a SMALL, PLAUSIBLE table
      rather than an error. F1 reports, per population, how many of the resolved library's terms
      actually survived contact with this object's own detected genes.
  TWO ENRICHED TERMS CAN SHARE MOST OF THEIR GENES. A curated library carries near-duplicate
      terms from different sources; a shared leading edge is one signal, not two findings.
  THE STRONGEST HIT CAN STILL LOOK LIKE NOISE. NES and FDR are numbers; whether the running
      enrichment curve is a clean concentrated peak or a ragged spread across the whole ranking
      is a shape a number does not carry, which is why F2 draws it before F3 restates it as a
      score.

None of that is visible in a results table alone, which is why the diagnostics are declared ahead
of the answer in `report` and the reporter puts them there.
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "state_version": 1,
    "summary": "which curated gene sets describe a population's own markers, ranked "
              "population-vs-rest and tested with gseapy's preranked GSEA",
    "when_to_use": "you have cell-type or cluster labels and want to describe a population in "
                  "the vocabulary of a curated gene-set library (hallmarks, pathways, GO terms) "
                  "rather than by its top individual marker genes",
    "wraps": {"tool": "gseapy", "homepage": "https://github.com/zqfang/GSEApy",
              "license": "BSD-3-Clause",
              "cite": "Fang Z. GSEApy: a comprehensive package for performing gene set "
                      "enrichment analysis in Python. Bioinformatics, 2023; original method: "
                      "Subramanian et al., PNAS 2005 (GSEA)"},

    # ACCOUNTED AGAINST gseapy's OWN SOURCE, not only against what this family's extractor found.
    # `sch dev convert inventory` (the python_package extractor: a name-prefix list, or a
    # signature carrying ax/axes/fig/figure) surfaces only 3 of these 6 - barplot, dotplot and
    # heatmap all take `ax=`. gseaplot, gseaplot2 and enrichment_map build their own figure
    # internally and take no ax/axes/fig/figure parameter, and none of the three names begins
    # with a prefix the extractor's short list recognises ("gseaplot".startswith("plot") is
    # False), so the extractor cannot see them at all - confirmed by reading gseapy/plot.py's
    # signatures directly, not by trusting the tool's own report. `Prerank.plot()` (a METHOD on
    # the class prerank() returns) is invisible to it for a different reason: the extractor
    # inspects the `gseapy` package's own namespace and has no way to look at a method reachable
    # only from an instance a call returns.
    "native_plots": {
        "barplot": {"skip": "duplicate_of", "same_as": "dotplot"},
        "dotplot": {"use": "figures/F3_top_pathways_by_population.png - the per-population dot "
                          "plot of top enriched terms, coloured by NES"},
        "heatmap": {"use": "figures/F4_leading_edge_expression.png - the strongest hit's "
                          "leading-edge genes, z-scored per gene across populations"},
        "gseaplot": {"skip": "duplicate_of", "same_as": "gseaplot2",
                    "evidence": "gseaplot2 called with a single term produces the same "
                               "running-enrichment-score panel gseaplot does (both build on "
                               "GSEAPlot/TracePlot); this plugin always calls gseaplot2, with "
                               "the top few hits, so the single-term function is not called"},
        "gseaplot2": {"use": "figures/F2_leading_edge_curves.png - the running-enrichment-score "
                            "trace for the strongest 1-3 hits, overlaid"},
        "enrichment_map": {"use": "tables/enrichment_map_nodes.csv, "
                                 "tables/enrichment_map_edges.csv (numbers only; gseapy's own "
                                 "function returns these two node/edge DataFrames rather than a "
                                 "rendered figure - drawing the network layout is a separate "
                                 "capability this plugin does not implement)"},
    },

    "upstream": {
        "docs": "https://gseapy.readthedocs.io/en/latest/; "
               "https://github.com/zqfang/GSEApy (read against the installed 1.3.1 source, not "
               "only the rendered docs - three of the gotchas below are only in the source)",
        "read": "2026-09-12",
        "defaults_changed": [
            "min_size=15, max_size=500, permutation_num=1000, weight=1.0, method='permutation', "
            "seed=123 are gseapy's OWN defaults for prerank, PASSED EXPLICITLY here as `config` "
            "rather than inherited, so a run can say what they were and a user can change them.",
            "threads is NOT gseapy's default (4 in the free function, 1 in the Prerank class): "
            "this plugin always passes ctx.cores, the host's allocated share, never a fixed "
            "number and never os.cpu_count().",
            "outdir=None and no_plot=True throughout. gseapy's own prerank can write its own "
            "files and draw its own (unreviewed) figures to `outdir`; this plugin never lets it "
            "touch disk on its own; ctx.emit_figure/ctx.emit_table are the only places a panel "
            "or a table is written, which is the same reasoning plugin.py gives for gating "
            "every figure through one method.",
            "gene_sets IS RESOLVED BY THIS PLUGIN BEFORE prerank IS CALLED, via gseapy's own "
            "get_library(name, organism, min_size, max_size, gene_list=<this object's detected "
            "genes>) - one call per configured library, merged. prerank accepts a bare Enrichr "
            "library NAME and would resolve it internally with the same call, but resolving it "
            "here first is what makes F1's coverage numbers computable at all: once gene_sets is "
            "a name string, nothing downstream can say how many of a term's members this object "
            "actually has without fetching the library independently anyway.",
            "dotplot's own `cutoff` (default 0.05) and `wrap_width` (default None) are passed "
            "explicitly rather than left at gseapy's defaults - see the comment at the call "
            "site in _fig_top_pathways for why (found via `sch dev convert defaults`, which "
            "lists every default this file was inheriting silently before this was written).",
        ],
        "not_used": [
            "gseapy.gsea() / gseapy.GSEA - the two-phenotype, permutation-of-SAMPLES mode. It "
            "needs replicate samples per phenotype; this plugin has cells and populations, not "
            "phenotype-labelled samples. See the module docstring.",
            "gseapy.enrichr() / gseapy.Enrichr - over-representation analysis on a fixed gene "
            "LIST (e.g. markers past a p-value cutoff), rather than the whole ranked list "
            "prerank uses. A threshold thrown away is information thrown away; prerank needs no "
            "cutoff to defend.",
            "gseapy.Msigdb - a second way to fetch gene sets, from an MSigDB release rather than "
            "Enrichr. Not used: mixing two gene-set fetch mechanisms is two different provenance "
            "stories for the same kind of input, and Enrichr is what gseapy's own `organism=` "
            "parameter is documented against.",
            "gseapy.ssgsea / gseapy.gsva / gseapy.SingleSampleGSEA - single-sample scoring "
            "against a fixed gene set, producing a per-SAMPLE (not per-population) score. A "
            "genuinely different capability, closer to `decoupler`'s per-cell activity than to "
            "this plugin's per-population test.",
            "Prerank.plot() / GSEAbase.plot() - the result object's own convenience method. It "
            "delegates to the same GSEAPlot/TracePlot classes as the free functions gseaplot / "
            "gseaplot2 this plugin calls directly (verified by reading gseapy/base.py); calling "
            "the free function keeps this plugin from holding a live Prerank instance open past "
            "one population's loop iteration.",
            "gseapy.plot.ringplot - not exported from the `gseapy` package itself (only from "
            "`gseapy.plot`), and 1.3.1's own implementation is a no-op: it emits a "
            "DeprecationWarning ('ringplot is deprecated; use dotplot instead') and returns None "
            "without drawing anything. Not in native_plots for either reason.",
            "prerank's own `sample_size` and `eps` keywords - left at gseapy's defaults (101, "
            "1e-50) rather than exposed as config, because both are read only by the "
            "'multilevel' method this plugin does not default to (config `method` is "
            "'permutation'). A user who sets method='multilevel' inherits both silently; that "
            "combination is untested by this plugin's own selftest.",
        ],
        "gotchas": [
            "dotplot AND barplot RAISE `ValueError: Can not detetermine colormap. All values in "
            "<column> are 0s` when EVERY value of the chosen `column` is exactly 0 - measured "
            "directly against 1.3.1, not read from documentation. A small permutation_num or a "
            "strongly separated ranking commonly floors FDR q-val (and NOM p-val) at 0.0 for "
            "every term, which is not a rare edge case - it is what a clean set of hits looks "
            "like. This plugin colours by NES (continuous) for exactly this reason and still "
            "wraps every native call in try/except, because a pathological table can raise for "
            "reasons DotPlot.process does not document.",
            "get_library(name, organism, gene_list=...) can return an EMPTY dict WITH NO ERROR "
            "when every term fails the overlap filter. Read directly in gseapy/parser.py: its "
            "own 'nothing survived' guard is `if filsets_num == len(genesets_dict): raise ...`, "
            "comparing the REMOVED count to the REMAINING count - true only when exactly half "
            "were removed, not when all were. When ALL terms are filtered out (total == removed, "
            "remaining == 0) the condition is `total == 0`, which is false for any non-trivial "
            "library, so the guard does not fire and an empty dict is returned silently. This "
            "plugin refuses explicitly when its own resolution comes back empty rather than "
            "trusting gseapy to have raised.",
            "get_library's `gene_list` filter REPLACES a surviving term's member list with ONLY "
            "the overlapping genes and discards the term's original size - so this plugin can "
            "report the ABSOLUTE overlap count per term and cannot report a coverage PERCENTAGE "
            "without a second, unfiltered fetch of the same library. F1 reports counts.",
            "gseaplot's and gseaplot2's `ofname` is documented as 'output file name. If None, "
            "don't save figure', and Prerank.plot() calls `g.savefig()` UNCONDITIONALLY in its "
            "own source (gseapy/base.py) - yet none of the three raises or writes a file when "
            "ofname is None; verified by calling GSEAPlot.savefig() with ofname=None directly "
            "rather than trusting either docstring.",
            "`organism=` on prerank/get_library is documented to select the Enrichr "
            "SERVER/catalog (human, mouse, yeast, fly, fish, worm) for a library NAME; it 'does "
            "not affect custom gene sets (gmt or dict)' - so a locally supplied .gmt path "
            "silently ignores ctx.organism, and a wrong-species .gmt is not caught by this "
            "plugin.",
            "`Tag %` and `Gene %` in res2d are POSITIONS, not coverage: gseapy's own docstring "
            "defines them as 'percent of gene set/gene list BEFORE the running enrichment peak', "
            "i.e. where the peak falls along each axis - not what fraction of a term's members "
            "this object's genes actually contain. This plugin does not use either column as a "
            "coverage measure (an earlier draft of this file did, incorrectly, before this "
            "docstring was read against the installed source).",
            "permutation_num sets the finest achievable nominal p-value (1/permutation_num), and "
            "FDR is derived from it - at the tool's own default of 1000 the floor is 0.001; this "
            "plugin's own due-diligence probe measured 100 producing floors of 0.01 that make "
            "most terms in a small test read as equally 'significant'.",
        ],
    },

    # CAPABILITIES, NEVER COLUMN NAMES. `organism` is required for the same reason decoupler
    # requires it: the gene-set library is published/served per species and a mismatch returns a
    # small plausible table rather than failing.
    "inject": {"required": ["lognorm", "label", "organism"], "optional": []},
    "provides": [],
    "produces": ["tables/enrichment_by_population.csv", "tables/ranking_coverage.csv",
                "tables/leading_edge_top_hits.csv", "tables/leading_edge_expression.csv",
                "tables/enrichment_map_nodes.csv", "tables/enrichment_map_edges.csv"],
    "sees": ["layers[{lognorm}]", "obs[{label}]", "var_names"],

    "config": {
        "gene_sets": {"type": "list", "default": ["MSigDB_Hallmark_2020"],
                     "help": "one or more Enrichr library names (see gseapy.get_library_name) "
                             "or .gmt file paths. Resolved and merged before ranking; a term "
                             "name repeated across libraries keeps the later library's members. "
                             "A library name is fetched over the network WHEN THE RUN HAPPENS "
                             "and is not pinned by this plugin"},
        # gseapy's OWN defaults for `prerank`, declared rather than inherited - see
        # upstream.defaults_changed.
        "min_size": {"type": "int", "default": 15, "min": 1,
                    "help": "gene sets with fewer than this many members present in this "
                            "object's detected genes are dropped before testing. gseapy's own "
                            "default is 15"},
        "max_size": {"type": "int", "default": 500, "min": 1,
                    "help": "gene sets with more than this many members present are dropped "
                            "before testing. gseapy's own default is 500"},
        "permutation_num": {"type": "int", "default": 1000, "min": 100,
                            "help": "gene-set permutations used to estimate each p-value. "
                                    "gseapy's own default is 1000; it also sets the finest "
                                    "achievable nominal p-value, 1/permutation_num"},
        "weight": {"type": "float", "default": 1.0, "min": 0.0, "max": 2.0,
                  "help": "the exponent (p) in gseapy's weighted running-sum statistic. "
                          "gseapy's own default is 1.0; 0 reduces to an unweighted "
                          "Kolmogorov-Smirnov-like statistic"},
        "method": {"type": "str", "default": "permutation",
                  "help": "gseapy's own p-value procedure: 'permutation' (classic gene-set "
                          "permutation) or 'multilevel' (fgsea's adaptive multilevel sampling, "
                          "which can resolve p-values below 1/permutation_num). gseapy's own "
                          "default is 'permutation'"},
        "seed": {"type": "int", "default": 123, "min": 0,
                "help": "random seed for the permutation null. gseapy's own default is 123"},
        # PLUGIN-OWNED, NOT gseapy's. gseapy's prerank knows nothing about "populations"; this
        # guard exists because a signal-to-noise ranking over a handful of cells is mostly its
        # own sampling noise, the same reasoning de.py's min_cells and decoupler's min_targets
        # apply to their own per-group thresholds.
        "min_cells_per_population": {"type": "int", "default": 10, "min": 2,
                                     "help": "a population with fewer real cells than this is "
                                             "not ranked - a signal-to-noise ranking over that "
                                             "few cells is mostly its own sampling noise. This "
                                             "is this plugin's own guard, not gseapy's"},
        "top_terms": {"type": "int", "default": 20, "min": 1,
                     "help": "terms drawn in the per-population dot plot and offered to "
                             "gseapy's own enrichment_map, ranked by |NES| across every "
                             "population. Nothing is dropped from the tables - every scored "
                             "term is in tables/enrichment_by_population.csv"},
    },

    "cost": "medium", "cores": 4,

    # THE LIBRARY, WHEN NAMED AS AN ENRICHR STRING, IS FETCHED OVER THE NETWORK AT RUN TIME - the
    # same tier and the same reasoning as decoupler's CollecTRI/Progeny. Nothing pins a version;
    # the term/edge counts this plugin logs and caveats are the only record of which one answered.
    "references": {
        "gene_set_library": {"tier": "runtime", "role": "gene_sets",
                             "source": "Enrichr (maayanlab.cloud), via gseapy.get_library",
                             "cite": "Chen EY et al., BMC Bioinformatics 2013; "
                                     "Kuleshov MV et al., Nucleic Acids Res 2016; "
                                     "Xie Z et al., Curr Protoc 2021 (Enrichr)",
                             "note": "resolved once per configured library name in `gene_sets`, "
                                    "before ranking. Needs outbound HTTPS from the compute node; "
                                    "a .gmt path in `gene_sets` instead reads a local file and "
                                    "needs no network"},
    },

    "requires": {
        "python": ">=3.9,<3.13",
        "packages": {
            # MEASURED AGAINST 1.3.1 SPECIFICALLY, not a wider range gseapy's own metadata would
            # allow: several gotchas above (the all-zero-colormap crash site, ofname=None
            # behaviour, the get_library empty-dict silence) were confirmed by reading 1.3.1's
            # installed source and are not asserted of any other version.
            "gseapy": ">=1.3,<1.4",
            "numpy": ">=1.24,<3",
            "pandas": ">=2.0,<3",
            # USED DIRECTLY (scipy.sparse.issparse), not only pulled in by gseapy. gseapy's own
            # metadata requires scipy with no version constraint at all.
            "scipy": ">=1.10,<2",
            # THE CONTRACT'S, NOT THIS METHOD'S: `_entry.py` reads the object with
            # `anndata.read_h5ad` before run() is called.
            "anndata": ">=0.12,<0.13",
            # ctx.plot() and every ctx.emit_figure call import this inside the plugin's own
            # interpreter; gseapy's own dotplot/barplot/heatmap/gseaplot/gseaplot2 need it too.
            "matplotlib": ">=3.6,<4",
        },
    },

    "report": {
        "figures": [
            {"id": "F1_ranking_coverage", "shows": "diagnostic", "required": True,
             "drawn_by": "plugin",
             "question": "how many of the configured library's terms actually survived contact "
                         "with this object's own detected genes, per population?",
             "source": "tables/ranking_coverage.csv"},
            {"id": "F2_leading_edge_curves", "shows": "diagnostic", "required": False,
             "drawn_by": "tool",
             "question": "do the strongest hits look like a real, concentrated enrichment or a "
                         "diffuse, noisy one?",
             "source": "tables/leading_edge_top_hits.csv",
             "when_absent": "no population's strongest hit could be matched back to a result "
                            "gseapy still held in memory - it is drawn from the SAME run's "
                            "Prerank objects and is not recomputed from the tables. The numeric "
                            "result is unaffected; only this shape check is missing."},
            {"id": "F3_top_pathways_by_population", "shows": "result", "required": True,
             "drawn_by": "tool",
             "question": "which gene sets are enriched in which populations, and in which "
                         "direction?",
             "source": "tables/enrichment_by_population.csv"},
            {"id": "F4_leading_edge_expression", "shows": "result", "required": False,
             "drawn_by": "tool",
             "question": "which of the strongest hit's leading-edge genes actually carry an "
                         "expression difference across populations, rather than riding along in "
                         "the ranking?",
             "source": "tables/leading_edge_expression.csv",
             "when_absent": "the strongest hit's leading-edge genes (gseapy's own Lead_genes "
                            "column) did not resolve against this object's detected genes."},
        ],
        # THE PAIRING. decoupler scores per-cell activity against a curated PRIOR NETWORK; this
        # scores per-population marker rank against a curated gene-set LIBRARY. Different
        # evidence for a similar question - "what pathway/regulatory vocabulary is active here" -
        # and a reader comparing the two should be told the other exists.
        "reads_with": ["decoupler"],

        # WHAT EACH FAMILY MULTIPLIES OVER, AND WHERE IT PLACES. Read by `scprofile.planner`
        # (`figure_families`/`figure_plan`) BEFORE a job runs, to say how many files a run will
        # write - and its own default when a family is UNDECLARED here is axis="unit",
        # position="contrast" (planner.py, `_match(..., "unit")` / `_match(..., "contrast")`),
        # which is WRONG for this plugin: nothing here runs per unit or draws an arm-pair
        # comparison. `sch dev convert placement` demands this of every kernel with declared
        # figures, though most of this family's own plain-Python kernels (decoupler, de,
        # pseudotime, cellcycle) have never filled it in and so carry that wrong default
        # silently - see the report for this conversion.
        "figure_axis": {
            # ALL FOUR ARE DRAWN ONCE PER RUN, over the whole object - never per sample/unit
            # (this kernel declares no `per_unit`) and never per arm-pair (it does not implement
            # CompareContext or read a design at all).
            "F1_ranking_coverage": "cohort",
            "F2_leading_edge_curves": "cohort",
            "F3_top_pathways_by_population": "cohort",
            "F4_leading_edge_expression": "cohort",
        },
        "figure_position": {
            # NOT "appendix": these are the numbered, citable diagnostic and result panels this
            # kernel's whole page is built from, not supplementary plates. NOT "overview" or
            # "contrast": scprofile/compose.py's own `figure_index` normalises any cohort-axis
            # panel that is not "overview" to "conclusion" for numbering purposes (read directly
            # - a cohort-scoped panel declared "contrast" would match neither of the composer's
            # two cohort-scope passes and be re-normalised anyway), so "conclusion" states
            # in the declaration what would otherwise happen by a fallback a reader of this file
            # cannot see.
            "F1_ranking_coverage": "conclusion",
            "F2_leading_edge_curves": "conclusion",
            "F3_top_pathways_by_population": "conclusion",
            "F4_leading_edge_expression": "conclusion",
        },
    },

    "cannot_show": [
        "A SHIFT IN ONE POPULATION CAN SURFACE AS ENRICHMENT IN A DIFFERENT ONE. 'Rest' is every "
        "OTHER real population pooled together, so a real change confined to population A moves "
        "the 'rest' average for every OTHER population's own contrast too - measured directly in "
        "this plugin's own selftest-style probe: boosting only one of three populations on a "
        "planted gene set produced that population's expected POSITIVE NES, and a LARGER-|NES|, "
        "genuinely NEGATIVE result for a different, untouched population, purely from how 'rest' "
        "is composed. A population's own hit list is not evidence about that population alone.",
        "THIS RANKS MARKERS OF ONE POPULATION AGAINST THE REST OF THE SAME OBJECT'S CELLS, NOT "
        "AGAINST A DESIGN. An enriched pathway here describes what makes a population distinct "
        "within this cohort; it is not a comparison across conditions. Read `de` alongside it "
        "for a design-aware answer.",
        "CELLS ARE NOT REPLICATES. The signal-to-noise ranking is computed over cells of one "
        "population against the rest; a population assembled disproportionately from one animal "
        "or one sample carries that animal's expression into the ranking, uncorrected.",
        "A GENE SET ABSENT FROM THE CONFIGURED LIBRARY CANNOT BE FOUND, however real the "
        "underlying biology. `gene_sets` decides the entire vocabulary this method can report "
        "on; a negative result is a statement about this library, not about the pathway space.",
        "TWO ENRICHED TERMS SHARING MOST OF THEIR GENES ARE NOT TWO INDEPENDENT FINDINGS. "
        "Curated libraries carry near-duplicate terms; a shared leading edge is one signal "
        "counted twice, and this plugin does not de-duplicate terms by gene overlap.",
        "COMPETITIVE GENE-SET TESTING ON A PRERANKED LIST ASSUMES GENES BEHAVE INDEPENDENTLY "
        "UNDER PERMUTATION. Co-expressed, co-regulated genes violate that assumption in the "
        "direction that makes a p-value look smaller than it is; the permutation FDR here does "
        "not correct for gene-gene correlation.",
        "NES IS COMPARABLE ACROSS TERMS WITHIN ONE POPULATION'S OWN RANKING AND IS NOT "
        "GUARANTEED COMPARABLE ACROSS POPULATIONS. The signal-to-noise ranking's scale depends "
        "on how separated a population is from the rest, which differs population to "
        "population; a larger NES in population A than population B is not, by itself, evidence "
        "that the pathway matters more in A.",
        "THE GENE-SET LIBRARY, WHEN NAMED AS AN ENRICHR STRING, IS FETCHED OVER THE NETWORK AT "
        "RUN TIME AND IS NOT PINNED. Two runs against the same object, weeks apart, can resolve "
        "the same-named library differently; nothing in the result records which version "
        "answered beyond the term count this plugin logs.",
        "A CELL CARRYING AN ANNOTATOR SENTINEL CONTRIBUTES TO NO POPULATION'S RANKING. They "
        "stay in the object; they are excluded from both sides of every population's contrast.",
        "min_size/max_size/permutation_num ARE DECLARED CONFIG, NOT FIXED FACTS. Changing them "
        "changes which terms can be tested at all and how fine a p-value can get - the same way "
        "de.py's alpha changes its own denominator - so two runs with different settings are not "
        "reporting on the same tested set even when scored from the same object.",
    ],
}


def _mean_std(X):
    """(mean, std) per column, ddof=1, for a dense array OR a scipy.sparse matrix.

    WRITTEN ONCE SO IT WORKS ON EITHER, rather than densifying first: a cohort's lognorm layer is
    usually sparse, and `np.asarray(X.todense())` on the full gene axis for one population's
    cells is exactly the peak-memory spike decoupler's own `batch_size` exists to avoid one level
    over. `E[X^2] - E[X]^2` reads a sparse matrix's own `.multiply` rather than densifying it.
    """
    import numpy as np
    import scipy.sparse as sp
    n = X.shape[0]
    mean = np.asarray(X.mean(axis=0)).ravel()
    if sp.issparse(X):
        mean_sq = np.asarray(X.multiply(X).mean(axis=0)).ravel()
    else:
        mean_sq = np.asarray(np.asarray(X) ** 2).mean(axis=0).ravel()
    var_pop = np.clip(mean_sq - mean ** 2, 0.0, None)
    var_unbiased = var_pop * n / max(n - 1, 1)
    return mean, np.sqrt(var_unbiased)


def _signal_to_noise(mean_in, std_in, mean_out, std_out):
    """The classic Broad GSEA / gseapy signal-to-noise ranking metric, per gene.

    REPLICATES gseapy's OWN FORMULA (`gseapy.algorithm.ranking_metric_tensor`, method
    'signal_to_noise') rather than importing it: that function permutes a SAMPLE-level class
    label for the two-phenotype permutation mode this plugin does not use (see the module
    docstring), and is not part of gseapy's public, exported surface. The correction - floor
    each std at 0.2*|mean|, and at 0.2 if still zero - is copied from its source so a
    population's own ranking uses the same convention gseapy's two-phenotype mode does.
    """
    import numpy as np
    si = np.maximum(std_in, 0.2 * np.abs(mean_in))
    si = np.where(si == 0, 0.2, si)
    so = np.maximum(std_out, 0.2 * np.abs(mean_out))
    so = np.where(so == 0, 0.2, so)
    return (mean_in - mean_out) / (si + so)


def _resolve_gene_sets(ctx, names, gene_universe):
    """{term: [overlapping genes]} merged over every configured library, and the problems.

    RESOLVED HERE, ONCE, BEFORE ANY POPULATION IS RANKED - rather than handing prerank the bare
    name and letting it fetch internally once per population. Both reach the same network call
    with the same arguments, but resolving first is what lets F1 say how many of a term's own
    members this object actually has: `get_library`'s own `gene_list` filter REPLACES a term's
    member list with only the overlap and prerank's internal resolution never surfaces that
    count anywhere this plugin could read it back.

    IMPORTS gseapy ONLY IF THERE IS SOMETHING TO RESOLVE. `names` is empty whenever `run()` is
    called with no `gene_sets` configured, which is a legitimate (if useless) declaration this
    function must not fail on just because it reached for a package it did not end up needing -
    the same reasoning `plugin.py` gives for keeping every third-party import inside a function
    rather than at module scope, one level further in.
    """
    resolved, problems = {}, []
    if not names:
        return resolved, problems
    import gseapy as gp
    for nm in names:
        try:
            d = gp.get_library(name=str(nm), organism=ctx.organism,
                               min_size=int(ctx.config["min_size"]),
                               max_size=int(ctx.config["max_size"]),
                               gene_list=list(gene_universe))
        except Exception as e:                                            # noqa: BLE001
            problems.append(f"{nm}: {type(e).__name__}: {e}")
            continue
        if not d:
            problems.append(f"{nm}: resolved to zero terms after filtering to this object's "
                            f"{len(gene_universe):,} detected genes at "
                            f"min_size={ctx.config['min_size']}/max_size="
                            f"{ctx.config['max_size']}")
            continue
        collide = sorted(set(d) & set(resolved))
        if collide:
            ctx.log(f"  {len(collide)} term name(s) appear in more than one configured "
                    f"library; the later one wins (e.g. {collide[:3]})")
        resolved.update(d)
    return resolved, problems


def _fig_coverage(ctx, coverage, n_available, source_path):
    """F1 - how much of the resolved library actually had something to say about THIS object.

    PLUGIN-drawn: this is a count this plugin computed itself (see `_resolve_gene_sets`), not a
    number gseapy reports anywhere in `res2d`.
    """
    plt = ctx.plot()
    F = ctx.figure
    pops = list(coverage.index)
    fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.6, 0.30 * len(pops) + 0.9)),
                           layout="constrained")
    y = list(range(len(pops)))
    vals = coverage["n_terms_scored"].to_numpy(dtype=float)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#ECECEC", lw=0.4)
    ax.barh(y, vals, height=0.62, color="#0072B2", zorder=2)
    ax.axvline(n_available, color=F.INK, ls=":", lw=0.7)
    ax.text(n_available, -0.7, f"{n_available} resolved", ha="center", va="bottom", fontsize=5.5,
           color=F.INK)
    ax.set_yticks(y)
    ax.set_yticklabels(pops)
    ax.invert_yaxis()
    ax.set_xlabel("gene sets scored for this population")
    ax.set_title("library coverage per population", loc="left", fontsize=8)
    ctx.emit_figure(
        "F1_ranking_coverage", fig,
        caption=(f"For each ranked population, how many of the {n_available} gene sets this "
                 f"plugin resolved from the configured `gene_sets` library actually passed "
                 f"min_size/max_size against that population's own ranked genes (the dotted "
                 f"line marks {n_available}, the resolved total). A population well short of "
                 f"the line lost terms at ranking time - usually because fewer of its own genes "
                 f"were detected - not because those terms are absent from the library. "
                 f"Populations too small to rank (below min_cells_per_population) are not "
                 f"shown here; they are named in the caveats."),
        source=source_path)


def _fig_leading_edge(ctx, top_rows, kept, source_path):
    """F2 - gseapy's own running-enrichment-score trace. TOOL-drawn, unmodified upstream figure."""
    import gseapy as gp
    plt = ctx.plot()
    F = ctx.figure
    palette = ["#0072B2", "#D55E00", "#009E73", "#CC79A7"]
    terms, hits, ress, colours, labels, rank_metric = [], [], [], [], [], None
    for i, (_, row) in enumerate(top_rows.iterrows()):
        pop_name, term = row["population"], row["Term"]
        pre = kept.get(pop_name)
        r = pre.results.get(term) if pre is not None else None
        if not r:
            continue
        terms.append(f"{term} [{pop_name}]")
        hits.append(r["hits"])
        ress.append(r["RES"])
        colours.append(palette[i % len(palette)])
        labels.append((term, pop_name, float(row["NES"]), float(row["FDR q-val"])))
        if rank_metric is None:
            rank_metric = pre.ranking
    if not terms:
        return
    axes = gp.gseaplot2(terms=terms, hits=hits, RESs=ress, rank_metric=rank_metric,
                        colors=colours, ofname=None,
                        figsize=(F.DOUBLE, F.DOUBLE * 0.62))
    if not axes:
        return
    fig = axes[0].figure
    cap_terms = "; ".join(f"{t} in {p} (NES {n:+.2f}, FDR {q:.3g})" for t, p, n, q in labels)
    ctx.emit_figure(
        "F2_leading_edge_curves", fig,
        caption=(f"gseapy's own running-enrichment-score trace (gseaplot2), unmodified, for the "
                 f"{len(terms)} strongest hit(s) by |NES| anywhere in this run: {cap_terms}. A "
                 f"clean single peak with its hit ticks concentrated under it is what a "
                 f"believable enrichment looks like; a curve that wanders, or hit ticks spread "
                 f"across the whole ranking, is a term whose NES and FDR should not be trusted "
                 f"on shape alone. The rank metric traced along the bottom is the first-listed "
                 f"population's own signal-to-noise ranking; each curve above it is still that "
                 f"population's own result even where the traces are overlaid on one axis."),
        source=source_path)


def _fig_top_pathways(ctx, combined, top_terms, source_path):
    """F3 - gseapy's own dot plot, faceted by population. TOOL-drawn, unmodified upstream figure."""
    import gseapy as gp
    plt = ctx.plot()
    F = ctx.figure
    fig_df = combined[combined["Term"].isin(top_terms)].copy()
    if fig_df.empty:
        return
    n_terms, n_pops = fig_df["Term"].nunique(), fig_df["population"].nunique()
    # cutoff=1.0 IS A NO-OP FOR column="NES" - gseapy's own DotPlot.process() sets its whole
    # `thresh` mask to True for NES/ES/"Combined Score"/"Odds Ratio" columns (plot.py, read
    # directly) - but passed explicitly rather than left at gseapy's own default of 0.05, which
    # WOULD matter for a p-value-shaped column and would silently drop rows if a future version
    # ever stopped special-casing NES. wrap_width keeps a long MSigDB-style term name from
    # overlapping the next tick label, which gseapy's own default (no wrapping) does not.
    ax = gp.dotplot(fig_df, column="NES", x="population", title="", ofname=None,
                    top_term=max(len(top_terms), 1), size=4, cutoff=1.0, wrap_width=28,
                    figsize=(F.DOUBLE, max(2.4, 0.24 * n_terms + 1.1)))
    if ax is None:
        return
    fig = ax.figure
    ax.set_title(f"top {n_terms} pathway(s) by |NES|, across {n_pops} population(s)",
                loc="left", fontsize=8)
    ctx.emit_figure(
        "F3_top_pathways_by_population", fig,
        caption=(f"gseapy's own dotplot, unmodified: the {n_terms} gene set(s) with the "
                 f"largest |NES| anywhere in this run, one column per population that ranked "
                 f"them, dot size the fraction of the ranked list before the running-score peak "
                 f"('Gene %', gseapy's own definition - a position, not a coverage fraction) "
                 f"and colour the normalised enrichment score (NES). A missing dot in a "
                 f"population's column means that term did not pass min_size/max_size for that "
                 f"population's own ranking, not zero enrichment. The source table holds every "
                 f"population and every term this run scored, not only what is drawn here."),
        source=source_path)


def _fig_leading_edge_expression(ctx, expr_df, top_pop, top_term, source_path):
    """F4 - gseapy's own heatmap, of the strongest hit's leading-edge genes. TOOL-drawn."""
    import gseapy as gp
    plt = ctx.plot()
    F = ctx.figure
    n_genes, n_pops = expr_df.shape[1], expr_df.shape[0]
    ax = gp.heatmap(expr_df.T, z_score=0, title="", ofname=None,
                    figsize=(max(F.SINGLE, 0.20 * n_pops + 1.2), max(1.8, 0.16 * n_genes + 1.0)))
    if ax is None:
        return
    fig = ax.figure
    ctx.emit_figure(
        "F4_leading_edge_expression", fig,
        caption=(f"gseapy's own heatmap, unmodified, of the {n_genes} leading-edge gene(s) of "
                 f"the single strongest hit ({top_term!r} in population {top_pop!r}): each "
                 f"gene's mean log-normalised expression per population, Z-SCORED PER GENE "
                 f"(across populations, gseapy's own z_score=0) so a highly expressed gene does "
                 f"not visually dominate a lowly expressed one - the raw means are in the source "
                 f"table. A leading-edge gene that reads flat here is contributing to the "
                 f"RANKING through its relative position among all genes, not through a "
                 f"difference a reader can see on this panel alone."),
        source=source_path)


def run(ctx):
    """Rank each population's markers against the rest of the object, and test the ranking
    against a curated gene-set library with gseapy's preranked GSEA. Everything the contract
    requires (lognorm, label, organism) has already been checked by the host."""
    import numpy as np
    import pandas as pd
    import scipy.sparse as sp
    import gseapy as gp

    ctx.plot()  # cheapest possible proof the drawing environment works, before anything runs

    p = ctx.populations()
    if p.groups is None:
        return ctx.refuse("pathway enrichment by population",
                          "no label column was named, so there are no populations to rank "
                          "markers for or against.")
    if len(p.names) < 2:
        return ctx.refuse(
            "pathway enrichment by population",
            f"{len(p.names)} population(s) with a real label ({', '.join(p.names) or 'none'}). "
            f"Ranking a population's markers needs a REST to rank against; with fewer than two "
            f"populations there is none.")
    if p.dropped:
        ctx.caveat(f"{len(p.dropped)} label value(s) carry an annotator sentinel and are "
                   f"excluded from every population's contrast: {', '.join(p.dropped)}. They "
                   f"stay in the object.")

    X = ctx.X
    genes = np.asarray(ctx.adata.var_names.astype(str))
    totals = np.asarray(X.sum(axis=0)).ravel() if sp.issparse(X) else np.asarray(X).sum(axis=0)
    detected = totals > 0
    n_detected = int(detected.sum())
    ctx.log(f"{n_detected:,} of {len(genes):,} genes are detected somewhere in this object and "
            f"are the ranking's gene universe")
    if n_detected < int(ctx.config["min_size"]):
        return ctx.refuse(
            "pathway enrichment by population",
            f"only {n_detected:,} genes are detected anywhere in this object, below the "
            f"declared min_size={ctx.config['min_size']}. No gene set could pass the size "
            f"filter.")
    ctx.caveat(f"Ranked over the {n_detected:,} of {len(genes):,} genes detected anywhere in "
              f"this object; a gene never detected in any cell was left out of the ranking "
              f"rather than ranked at an uninformative tied value.")
    Xd = X.tocsc()[:, detected] if sp.issparse(X) else X[:, detected]
    genes_d = genes[detected]

    gene_sets_cfg = list(ctx.config["gene_sets"])
    resolved, problems = _resolve_gene_sets(ctx, gene_sets_cfg, genes_d)
    for msg in problems:
        ctx.log(f"  gene set library not resolved: {msg}")
    if not resolved:
        return ctx.refuse(
            "pathway enrichment by population",
            f"none of the configured gene-set librar{'y' if len(gene_sets_cfg) == 1 else 'ies'} "
            f"{gene_sets_cfg} resolved to any usable term against this object's "
            f"{n_detected:,} detected genes." + (" " + "; ".join(problems) if problems else "") +
            " Note: gseapy's own get_library can return an empty result with no error when "
            "every term fails the overlap filter - this is not necessarily a network failure.")
    ctx.caveat(
        f"Scored against {len(resolved):,} gene set(s) resolved from "
        f"{', '.join(str(g) for g in gene_sets_cfg)}. A pathway absent from this library cannot "
        f"be found here however real the underlying biology. Any library named as an Enrichr "
        f"library (not a local .gmt path) is fetched over the network WHEN THIS RUN HAPPENS and "
        f"is not pinned by this plugin - two runs weeks apart may consult different versions of "
        f"the same-named library.")

    rows, coverage_rows, kept = [], [], {}
    for name in p.names:
        local = np.asarray(p.groups) == name
        n_cells = int(local.sum())
        if n_cells < int(ctx.config["min_cells_per_population"]):
            ctx.log(f"  {name}: {n_cells:,} cell(s), below "
                    f"min_cells_per_population={ctx.config['min_cells_per_population']} - not "
                    f"ranked")
            ctx.caveat(f"Population {name!r} has only {n_cells:,} cell(s), below "
                      f"min_cells_per_population={ctx.config['min_cells_per_population']}, and "
                      f"was not ranked: a signal-to-noise ranking over that few cells is mostly "
                      f"its own sampling noise.")
            continue
        full_mask = np.zeros(Xd.shape[0], dtype=bool)
        full_mask[p.mask] = local
        rest_mask = p.mask & ~full_mask

        mean_in, std_in = _mean_std(Xd[full_mask])
        mean_out, std_out = _mean_std(Xd[rest_mask])
        s2n = _signal_to_noise(mean_in, std_in, mean_out, std_out)
        rnk = pd.Series(s2n, index=genes_d)
        finite = np.isfinite(rnk.to_numpy())
        if not finite.all():
            ctx.log(f"  {name}: {int((~finite).sum())} gene(s) produced a non-finite "
                    f"signal-to-noise value and were dropped from the ranking")
            rnk = rnk[finite]
        rnk = rnk.sort_values(ascending=False)

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pre = gp.prerank(rnk=rnk, gene_sets=dict(resolved), organism=ctx.organism,
                             outdir=None, min_size=int(ctx.config["min_size"]),
                             max_size=int(ctx.config["max_size"]),
                             permutation_num=int(ctx.config["permutation_num"]),
                             weight=float(ctx.config["weight"]), method=str(ctx.config["method"]),
                             seed=int(ctx.config["seed"]), threads=ctx.cores, verbose=False,
                             ascending=False, no_plot=True)
        res = pre.res2d.copy()
        coverage_rows.append({"population": name, "n_cells": n_cells,
                             "n_genes_ranked": len(rnk), "n_terms_scored": len(res)})
        if res.empty:
            ctx.log(f"  {name}: {n_cells:,} cells ranked, no gene set passed min_size/max_size "
                    f"against {len(rnk):,} ranked genes")
            continue
        res.insert(0, "population", name)
        res.insert(1, "n_cells", n_cells)
        rows.append(res)
        kept[name] = pre

    coverage = pd.DataFrame(coverage_rows).set_index("population") if coverage_rows else \
        pd.DataFrame(columns=["n_cells", "n_genes_ranked", "n_terms_scored"])
    coverage_path = ctx.emit_table("ranking_coverage", coverage)

    if not rows:
        ctx.caveat("No population produced a scored result; see the log and "
                  "tables/ranking_coverage.csv for which populations were ranked and what they "
                  "found.")
        return ctx.refuse("pathway enrichment by population",
                          "every ranked population scored zero gene sets - see "
                          "tables/ranking_coverage.csv.")

    combined = pd.concat(rows, ignore_index=True)
    combined_path = ctx.emit_table("enrichment_by_population", combined)
    ctx.caveat(f"{len(kept):,} of {len(p.names):,} population(s) were ranked and scored; the "
              f"rest are named above with the reason they were not.")

    # ---------------------------------------------------------------- figures
    ctx.log("figures:")
    try:
        _fig_coverage(ctx, coverage, len(resolved), coverage_path)
    except Exception as e:                                                # noqa: BLE001
        ctx.log(f"    F1_ranking_coverage not drawn: {e}")

    order = combined.reindex(combined["NES"].abs().sort_values(ascending=False).index)
    top_rows_for_curve = order.head(min(3, len(order)))
    leading_edge_frames = []
    for _, row in top_rows_for_curve.iterrows():
        pre = kept.get(row["population"])
        r = pre.results.get(row["Term"]) if pre is not None else None
        if not r:
            continue
        curve = pd.DataFrame({"rank_position": np.arange(len(r["RES"])), "running_es": r["RES"]})
        curve.insert(0, "population", row["population"])
        curve.insert(1, "term", row["Term"])
        leading_edge_frames.append(curve)
    if leading_edge_frames:
        led_path = ctx.emit_table("leading_edge_top_hits", pd.concat(leading_edge_frames,
                                                                     ignore_index=True))
        try:
            _fig_leading_edge(ctx, top_rows_for_curve, kept, led_path)
        except Exception as e:                                            # noqa: BLE001
            ctx.log(f"    F2_leading_edge_curves not drawn: {e}")
            ctx.caveat("The leading-edge running-enrichment curve for the strongest hit(s) was "
                      "not drawn; the numbers behind it are still in "
                      "tables/leading_edge_top_hits.csv.")
    else:
        ctx.log("    F2_leading_edge_curves not drawn: no hit's result could be recovered from "
                "this run's own Prerank object(s)")
        ctx.caveat("The leading-edge running-enrichment curve could not be drawn for any hit in "
                  "this run.")

    top_terms = list(order.head(int(ctx.config["top_terms"]))["Term"].unique())
    try:
        _fig_top_pathways(ctx, combined, top_terms, combined_path)
    except Exception as e:                                                # noqa: BLE001
        ctx.log(f"    F3_top_pathways_by_population not drawn: {e}")
        ctx.caveat("The per-population dot plot of top pathways was not drawn; the full table "
                  "is still in tables/enrichment_by_population.csv.")

    top1 = order.iloc[0]
    top_pop, top_term = top1["population"], top1["Term"]
    lead_genes = [g for g in str(top1.get("Lead_genes", "")).split(";") if g]
    lead_genes = [g for g in lead_genes if g in set(genes_d)]
    if lead_genes:
        gi = {g: i for i, g in enumerate(genes_d)}
        cols = [gi[g] for g in lead_genes]
        expr_rows = {}
        for name in kept:
            local = np.asarray(p.groups) == name
            full_mask = np.zeros(Xd.shape[0], dtype=bool)
            full_mask[p.mask] = local
            sub = Xd[full_mask][:, cols]
            expr_rows[name] = (np.asarray(sub.mean(axis=0)).ravel() if sp.issparse(sub)
                              else np.asarray(sub).mean(axis=0))
        expr_df = pd.DataFrame(expr_rows, index=lead_genes).T
        expr_df.index.name = "population"
        expr_path = ctx.emit_table("leading_edge_expression", expr_df)
        try:
            _fig_leading_edge_expression(ctx, expr_df, top_pop, top_term, expr_path)
        except Exception as e:                                            # noqa: BLE001
            ctx.log(f"    F4_leading_edge_expression not drawn: {e}")
            ctx.caveat("The leading-edge expression heatmap for the strongest hit was not "
                      "drawn; the numbers are still in tables/leading_edge_expression.csv.")
    else:
        ctx.log("    F4_leading_edge_expression not drawn: the strongest hit's leading-edge "
                "genes were not resolvable among this object's detected genes")
        ctx.caveat("The leading-edge expression panel for the strongest hit was not drawn: its "
                  "Lead_genes could not be resolved against this object's detected genes.")

    # enrichment_map: NUMBERS ONLY (see native_plots) - gseapy's own function returns node/edge
    # tables, not a rendered figure; drawing the network is a different capability this plugin
    # does not implement.
    try:
        top_pop_res = combined[combined["population"] == top_pop]
        nodes, edges = gp.enrichment_map(top_pop_res, column="FDR q-val", cutoff=1.0,
                                         top_term=int(ctx.config["top_terms"]))
        ctx.emit_table("enrichment_map_nodes", nodes)
        ctx.emit_table("enrichment_map_edges", edges)
    except Exception as e:                                               # noqa: BLE001
        ctx.log(f"  enrichment_map tables not written: {e}")
        ctx.caveat("gseapy's own enrichment_map node/edge tables were not produced for the "
                  "strongest population's results.")

    ctx.headline = (f"{len(kept):,} of {len(p.names):,} population(s) ranked against "
                    f"{len(resolved):,} gene set(s); strongest hit {top_term!r} in "
                    f"{top_pop!r}, NES {float(top1['NES']):+.2f}")


def selftest(ctx):
    """Prove the call works against the versions installed here, and that a REAL signal survives
    the whole path: plant a mean shift in a known set of genes for half a synthetic cohort, rank
    it, and require gseapy's prerank to name that gene set as the strongest hit.

    Not an import check. gseapy 1.x's res2d columns, prerank's own keyword names, and
    dotplot/gseaplot/heatmap's return shapes with ofname=None have all moved between versions or
    are undocumented (see upstream.gotchas) - none of that is caught by an import succeeding.

    DOES NOT CALL ctx.fixture(): that builds its lognorm layer with scanpy, which this plugin
    does not otherwise need (its own computation is numpy/scipy only) - see the PR/report for
    why this plugin does not carry scanpy as a dependency just to exercise this test.
    """
    import numpy as np
    import pandas as pd
    import gseapy as gp

    rng = np.random.default_rng(0)
    n_cells, n_genes = 160, 120
    genes = np.array([f"Gene{i:04d}" for i in range(n_genes)])
    labels = np.array(["Planted", "Other"])[np.arange(n_cells) % 2]
    lognorm = rng.poisson(rng.uniform(0.2, 6.0, size=n_genes), size=(n_cells, n_genes)).astype(
        float)
    planted_genes = list(genes[:15])
    boost = labels == "Planted"
    lognorm[np.ix_(boost, np.arange(15))] += 4.0

    mask_in = labels == "Planted"
    mean_in, std_in = _mean_std(lognorm[mask_in])
    mean_out, std_out = _mean_std(lognorm[~mask_in])
    s2n = _signal_to_noise(mean_in, std_in, mean_out, std_out)
    rnk = pd.Series(s2n, index=genes).sort_values(ascending=False)
    assert np.isfinite(rnk.to_numpy()).all(), "signal-to-noise produced non-finite value(s)"
    ctx.log(f"  ranked {len(rnk):,} genes; top 5: {list(rnk.index[:5])}")
    assert set(planted_genes) & set(rnk.index[:15]), (
        "none of the 15 genes this test boosted for the 'Planted' cells landed in the top 15 of "
        "their own ranking - the signal-to-noise metric did not recover a signal this test "
        "planted")

    gene_sets = {"PLANTED": planted_genes, "RANDOM_A": list(genes[40:55]),
                "RANDOM_B": list(genes[70:85])}
    pre = gp.prerank(rnk=rnk, gene_sets=gene_sets, organism="human", outdir=None,
                     min_size=1, max_size=1000, permutation_num=100, weight=1.0,
                     method="permutation", seed=0, threads=max(1, ctx.cores), verbose=False,
                     ascending=False, no_plot=True)
    res = pre.res2d
    for col in ("Term", "NES", "NOM p-val", "FDR q-val", "Gene %", "Lead_genes"):
        assert col in res.columns, f"prerank's res2d no longer carries {col!r}; its schema moved"
    assert "PLANTED" in set(res["Term"]), "the planted gene set was dropped by prerank entirely"
    row = res.set_index("Term").loc["PLANTED"]
    assert float(row["NES"]) > 0, (
        f"the planted gene set's own NES is {row['NES']!r}, not positive - a gene set boosted "
        f"to the top of the ranking should read as enriched in the positive direction")
    best = res.sort_values("NES", ascending=False).iloc[0]["Term"]
    assert best == "PLANTED", (
        f"the strongest hit by NES is {best!r}, not the planted gene set - prerank ran without "
        f"error but did not recover a signal this test planted")
    ctx.log(f"  PLANTED gene set recovered as the strongest hit: NES={float(row['NES']):+.2f}, "
            f"FDR q-val={row['FDR q-val']}")

    # `_resolve_gene_sets` WITH NOTHING CONFIGURED must be a clean no-op, not an error - proved
    # here because `run()` treats an empty `resolved` as a refusal, and a helper that raised
    # instead on zero inputs would turn "nothing configured" into a crash rather than a refusal.
    resolved, problems = _resolve_gene_sets(ctx, [], genes)
    assert resolved == {} and problems == [], "resolving zero configured libraries must be a no-op"

    # the native plotting surface this plugin actually calls, proved against this fixture's own
    # tiny result rather than assumed from a docstring - two of the three calls below raised on
    # an all-zero-FDR result before `column="NES"` was chosen (see upstream.gotchas).
    plt = ctx.plot()
    ax = gp.dotplot(res, column="NES", title="selftest", ofname=None, size=3)
    assert ax is not None, "dotplot returned None with ofname=None"
    plt.close(ax.figure)
    r = pre.results["PLANTED"]
    axes = gp.gseaplot(term="PLANTED", hits=r["hits"], nes=r["nes"], pval=r["pval"], fdr=r["fdr"],
                       RES=r["RES"], rank_metric=pre.ranking, ofname=None)
    assert axes, "gseaplot returned nothing with ofname=None"
    plt.close(axes[0].figure)
    hm = gp.heatmap(pd.DataFrame({"Planted": [1.0, 2.0], "Other": [0.5, 0.3]},
                                 index=["g1", "g2"]), z_score=0, title="selftest", ofname=None)
    assert hm is not None, "heatmap returned None with ofname=None"
    plt.close(hm.figure)
    ctx.log("  ok   dotplot, gseaplot and heatmap all import and draw")
