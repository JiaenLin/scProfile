"""Whether a population's share shifts across the design.

COMPOSITION IS RELATIVE BY CONSTRUCTION and that governs everything here. Shares must sum to one,
so one population rising makes every other fall arithmetically, and a test that ignores this
reports every population as changed when one did. scCODA handles it by testing against a
reference population and reporting credible inclusion rather than a p-value.

The reference is therefore the single most consequential setting in this plugin, and it is
declared config with an automatic choice that is NAMED in the result — never silently picked.

THE PAGE IS MOSTLY DIAGNOSTICS, AND THAT IS THE METHOD'S SHAPE RATHER THAN CAUTION

Four of this plugin's five panels are checks, because four separate things decide what its one
answer means and not one of them is visible in the answer:

  the replicates   a share is measured per sample, and the model is fitted on as many rows as
                   there are samples. Where one library carries an arm, the shift is that
                   library's, and only the per-sample points show it.
  the reference    "credible changes detected by scCODA have to be interpreted in relation to the
                   reference cell type" (Buttner, Ostner et al., Nat Commun 2021). If the
                   population every effect is measured against moved, every effect is wrong, and
                   nothing in the output says so.
  the sampler      pertpy WARNS on an acceptance rate outside 0.6-0.95 - "Results might be
                   incorrect!" - through a logger. A logger warning in a batch run is invisible:
                   the run finishes, the table is full, and the page says nothing.
  the threshold    the answer is a posterior inclusion probability cut at a threshold derived
                   from the requested FDR, and when NO threshold reaches that FDR the tool cuts
                   at 1.0 and reports every effect as not credible - which reads exactly like a
                   real negative. scCODA's own tutorial says to raise the FDR "up to 0.2 if no
                   effects are found at a more conservative level", and a reader can only act on
                   that advice if they can see where the inclusion probabilities actually sat.

NOTHING IS REMOVED FROM THE DATASET HERE. Annotator sentinels leave the GROUPING, because a
sentinel is the annotator declining to call a cell type and counting it as a population would make
every share depend on how often they declined; they stay in the object and are named in a caveat.
"""

PLUGIN = {
    "api": 1,
    "version": "0.2.0",
    "summary": "whether a population's share shifts across the design",
    "when_to_use": "you have a design table and want to know whether composition changed",
    "wraps": {"tool": "pertpy", "homepage": "https://pertpy.readthedocs.io",
              "license": "MIT",
              "cite": "Büttner et al., 2024 (pertpy); "
                      "Büttner et al., Nat Commun 2021 (scCODA)"},
    "upstream": {
        "docs": "https://pertpy.readthedocs.io/en/latest/usage/usage.html#composition",
        "read": "2026-08-25",
        "defaults_changed": [
            "reference_cell_type is chosen explicitly rather than left to 'automatic'. It is the "
            "most consequential setting in the method - every effect is relative to it - and a "
            "silent choice produces a full result whose meaning nobody can state.",
            "THE AUTOMATIC CHOICE NOW MIRRORS THE TOOL'S OWN RULE, which it did not. This plugin "
            "picked the population with the smallest standard deviation of share; "
            "`_base_coda._prepare` picks the smallest DISPERSION - variance over mean of relative "
            "abundance - among populations whose fraction of zero entries is below "
            "`automatic_reference_absence_threshold`. Those are different rules and they pick "
            "different populations: a rare population that is nearly constant wins on standard "
            "deviation and would be REFUSED by scCODA for its zeros. The rule is applied here, "
            "rather than by passing 'automatic', so the choice can be named and drawn before the "
            "fit instead of appearing in a logger line inside it.",
            "num_samples and num_warmup are passed explicitly AT THE TOOL'S OWN DEFAULTS, 10000 "
            "and 1000. They were hard-coded here at 1000 and 500 - a tenth of the chain the tool "
            "asks for - and the inclusion probability the whole answer is read off is a share OF "
            "THE DRAWS, so a shorter chain resolves it more coarsely and moves which effects are "
            "called. A sampling parameter that changes the answer is config, not a literal.",
            "set_fdr() is called BEFORE the effects are read back. `credible_effects(est_fdr=x)` "
            "recomputes the decision at x and does NOT store it, so the booleans came back at the "
            "requested FDR while the stored effect table, and the inclusion-probability threshold "
            "in uns, stayed at the library default of 0.05. At the default they agree and nothing "
            "shows; at any other `fdr` the page would have carried two answers.",
            "fdr is passed through from config rather than left at the library default, because "
            "the credible-inclusion threshold is what turns the posterior into a claim.",
        ],
        "not_used": [
            "tascCODA, which uses a hierarchy over cell types. It is a better answer where a "
            "hierarchy exists and needs one declared; that is a different plugin, not a flag.",
            "Milo. It tests neighbourhoods rather than labelled populations and answers a "
            "different question; it belongs beside this, not inside it.",
            "THE AUTHORS' REFERENCE SWEEP, and this is the one omission a reader should weigh. "
            "scCODA's own documentation validates the reference by 'sequentially running scCODA "
            "and selecting each cell type as the reference once', then taking the populations "
            "credible in more than half of those runs. It is the only real check that the answer "
            "does not depend on the reference - and it costs one MCMC fit per population per "
            "term, which is a different plugin's worth of compute rather than a flag on this one. "
            "F2_reference reports what can be checked without refitting: whether the chosen "
            "reference is the stable population the model assumes it is.",
            "run_hmc, and the numpyro kernel arguments generally. `run_nuts(*args, **kwargs)` "
            "passes them to the NUTS KERNEL, not to MCMC, so `num_chains` cannot be reached "
            "through it - which is why the convergence panel splits the one chain rather than "
            "comparing several.",
        ],
        "gotchas": [
            "scCODA is Bayesian: it returns credible inclusion, not a p-value, and reading its "
            "output as significance is a category error the result text guards against.",
            "With few samples per arm the posterior leans on the prior. The sample counts are "
            "reported beside the result for that reason - though this is the regime scCODA was "
            "built for, and its authors report it comparing favourably to other models "
            "'particularly when only a low number of experimental replicates are available' "
            "(Nat Commun 2021).",
            "THE ACCEPTANCE-RATE WARNING GOES TO A LOGGER AND NOWHERE ELSE. `__run_mcmc` warns "
            "'Results might be incorrect!' when the mean acceptance rate is below 0.6 or above "
            "0.95 and then returns a complete, ordinary-looking result. In a batch run that line "
            "is on stderr in a job file nobody opens. The rate is read back out of "
            "uns['scCODA_params']['mcmc'] and drawn.",
            "STANDARD CONVERGENCE DIAGNOSTICS MISREAD THIS MODEL. 'Due to the spike-and-slab "
            "priors, the beta parameters have many values at 0, which looks like a convergence "
            "issue, but is actually not' (scCODA docs), and the reference population's effect is "
            "constant at 0 for the whole chain - a KDE of it raises. So the check here is on the "
            "quantity the answer is actually read off: the inclusion probability, computed on the "
            "first half of the chain against the second.",
            "ZERO COUNTS ARE SILENTLY PSEUDOCOUNTED. `_prepare` replaces every zero with 0.5 and "
            "says so at INFO level. A population absent from a sample is therefore fitted as "
            "half a cell, and the sample totals the model uses include those halves.",
            "THE SIGN OF `log2-fold change` CAN DISAGREE WITH THE SIGN OF THE EFFECT PARAMETER, "
            "and pertpy's own docstring says so: the fold change is COMPOSITIONAL - expected "
            "counts are renormalised to the same total before the ratio - so a population with a "
            "zero effect can carry a non-zero fold change driven entirely by other populations. "
            "The reference population is the clearest case: its effect is fixed at 0 by "
            "construction and its fold change is not. Both columns are drawn, side by side.",
            "WHEN NO THRESHOLD REACHES THE REQUESTED FDR THE TOOL CUTS AT 1.0. `opt_thresh` walks "
            "the inclusion probabilities downwards and returns 1.0 when none satisfies the "
            "target, so every effect is set to zero and the result is a full table of no-change. "
            "That is indistinguishable from a real negative unless the threshold is shown.",
        ],
    },

    "inject": {"required": ["label", "sample", "design"], "optional": ["contrast"]},
    "provides": [],
    "produces": ["tables/abundance_by_population.csv", "tables/abundance_counts.csv"],

    "config": {
        "reference": {"type": "str", "default": "auto",
                      "help": "the population every effect is relative to. 'auto' applies "
                              "scCODA's own rule - the lowest dispersion (variance/mean of "
                              "share) among populations present in enough samples - and NAMES "
                              "the choice in the result; any population name pins it"},
        "reference_absence_threshold": {"type": "float", "default": 0.05, "min": 0.0, "max": 1.0,
                                        "help": "a population missing from more than this "
                                                "fraction of samples cannot be the automatic "
                                                "reference. scCODA's own default; with fewer "
                                                "than 20 samples it means 'present in every "
                                                "one'"},
        "fdr": {"type": "float", "default": 0.05, "min": 0.0, "max": 1.0,
                "help": "the credible-inclusion threshold scCODA uses to call an effect. Its own "
                        "tutorial recommends raising this as far as 0.2 if nothing is found at a "
                        "conservative level; pertpy's paper used 0.1"},
        "num_samples": {"type": "int", "default": 10000, "min": 100,
                        "help": "MCMC draws kept after warmup. The tool's own default. The "
                                "inclusion probability is a share OF these, so a shorter chain "
                                "resolves the decision more coarsely"},
        "num_warmup": {"type": "int", "default": 1000, "min": 50,
                       "help": "MCMC warmup draws, discarded. The tool's own default"},
        "seed": {"type": "int", "default": 0, "min": 0,
                 "help": "rng_key for the sampler. The tool's own remedy for a poor acceptance "
                         "rate is to re-run with a different one, which needs this to be reachable"},
        "min_samples_per_level": {"type": "int", "default": 2, "min": 2,
                                  "help": "a factor needs this many samples in every level, or "
                                          "the posterior is the prior"},
    },

    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {
            "pertpy": ">=0.9,<2", "pandas": ">=2.0,<3", "numpy": ">=1.24,<3",
            # PINNED BECAUSE THE TOOL THIS WRAPS DOES NOT PIN IT. pertpy 1.0.5 declares a bare
            # `Requires-Dist: mudata` with no constraint at all, and calls
            # `mudata.set_options(pull_on_update=False)` at import. mudata 0.4 removed
            # `set_options` in favour of `settings`, so `import pertpy` raises AttributeError
            # against any 0.4 - measured, on mudata 0.4.1: `hasattr(mudata, "set_options")` is
            # False and the public surface carries `settings` in its place.
            #
            # Nothing about that is visible until an environment is resolved fresh AFTER the new
            # mudata is published, which is why this passed and then stopped passing with no
            # change on our side. AN UNPINNED TRANSITIVE DEPENDENCY IS A DECISION TO LET SOMEONE
            # ELSE'S RELEASE SCHEDULE DECIDE WHETHER THIS PLUGIN IMPORTS. Naming a ceiling the
            # upstream forgot is one of the things a plugin declaration is FOR.
            #
            # Ceiling only, deliberately: 0.4 is measured to break it and no floor has been
            # measured, so inventing one would be asserting something nobody checked.
            "mudata": "<0.4",
            # THE CONTRACT'S, NOT THIS METHOD'S. `_entry.py` reads the object with
            # `anndata.read_h5ad` before run() is called. This plugin happens to work today
            # because it SHARES an environment with plugins that do name anndata - which is
            # accidental: isolate it for any reason and it stops being able to start.
            "anndata": ">=0.12,<0.13",
            # THE SAME GAP, ONE SLOT OVER, AND IT OPENED THE DAY THIS PLUGIN LEARNED TO DRAW.
            # `ctx.plot()` imports matplotlib; a plugin that emits figures and does not name it
            # is relying on a neighbour in a shared environment to have asked for it. The figure
            # conventions module is written to need matplotlib and nothing else, so this is the
            # whole of the drawing requirement.
            "matplotlib": ">=3.6,<4",
            # PERTPY IMPORTS THIS AND DOES NOT DECLARE IT. `pertpy/data/_dataloader.py` does
            # `from filelock import FileLock` at module scope, and `pertpy/__init__.py` imports
            # `data`, so `import pertpy` raises ModuleNotFoundError in an environment resolved
            # from pertpy's own metadata. Measured on PBS 677555. A dependency a wrapped tool
            # forgot is still a dependency this plugin needs, and naming it here is the only
            # place it can be said.
            "filelock": ">=3",
        },
    },

    "cost": "medium", "cores": 4,

    # Measured, not estimated: fitted from this plugin's own instances in one run on a 10-sample mouse single-nucleus cohort (~99k cells). ONE dataset on ONE machine - a starting point that is right for scheduling, not a universal constant. Every run re-fits and prints its own.
    # Fitted from one instance; the split is indeterminate.
    "memory_gb_per_100k": 7.2,

    # WHAT ITS PAGE SHOULD CONTAIN. The order below is the order a reader has to meet them in, and
    # the reporter enforces it by `shows`: the four checks decide whether the fifth panel is an
    # answer or a number. Nothing here is per-cell and nothing is drawn on an embedding - a
    # composition is a table of shares per sample, and the only honest picture of one is the
    # samples themselves.
    "report": {
        "figures": [
            {"id": "F1_shares", "shows": "diagnostic", "required": True,
             "question": "do the replicates within a group agree, or is one sample carrying the "
                         "shift?",
             "source": "figures/F1_shares.csv"},
            {"id": "F2_reference", "shows": "diagnostic", "required": True,
             "question": "is the population every effect is measured against actually a stable "
                         "one, and did it hold still across the design?",
             "source": "figures/F2_reference.csv"},
            {"id": "F3_sampling", "shows": "diagnostic", "required": False,
             "question": "did the sampler settle on the quantity the answer is read off?",
             "source": "figures/F3_sampling.csv",
             # BOTH HALVES HAVE TO GO MISSING. The panel draws two checks that come out of two
             # different keys - the posterior draws and the acceptance rate - and a version that
             # moves one still writes the other, so it is absent only when the chain was not
             # described at all. It used to be absent whenever the DRAWS were missing, which
             # threw away the only drawing of pertpy's acceptance-rate warning for an unrelated
             # reason - and this sentence then told a reader that warning had been looked at.
             "when_absent": "the tool recorded neither the posterior draws nor the mean "
                            "acceptance rate where this plugin reads them, so no check could be "
                            "made on the chain at all - not its convergence, and not the one "
                            "warning pertpy itself raises. The effects below were produced by a "
                            "chain nobody has looked at."},
            {"id": "F4_credibility", "shows": "diagnostic", "required": False,
             "question": "how close was each call to the threshold that decided it?",
             "source": "tables/abundance_by_population.csv",
             # TWO ABSENCES, AND THEY DO DIFFERENT THINGS TO THE PAGE. This said the same absence
             # took the effect sizes out of the result panel below, which is true of one of them
             # and false of the other - and a `when_absent` that overstates what is missing is
             # the same failure as a gap one step further on: the reader is told a panel they can
             # see in front of them is gone.
             "when_absent": "the inclusion probabilities could not be read back, so the "
                            "threshold cut through them cannot be shown and nothing says how "
                            "close any call came to it. Two different absences produce this. An "
                            "effect table with no inclusion-probability column: the result panel "
                            "below is still drawn, from the effect sizes. Or no effect table at "
                            "all: the result panel is absent with it, and the run reports "
                            "`partial` and says in its caveats that nothing was tested either "
                            "way."},
            {"id": "F5_effects", "shows": "result", "required": True,
             "question": "which populations shifted, in which direction, and by how much?",
             "source": "tables/abundance_by_population.csv"},
        ],
    },

    "cannot_show": [
        "COMPOSITION IS RELATIVE BY CONSTRUCTION. One population rising makes every other fall, "
        "and which one actually moved is not recoverable from shares alone - that is what the "
        "reference population is for, and it is named in the result.",
        "A POPULATION WITH NO CREDIBLE EFFECT IS NOT A POPULATION THAT DID NOT MOVE. scCODA's own "
        "tutorial: because the data is compositional, cell types for which no credible change was "
        "detected can still change in abundance, as soon as a credible effect is detected on "
        "another cell type.",
        "THE MODEL ASSUMES FEW POPULATIONS MOVE. The spike-and-slab prior estimates effects 'in a "
        "parsimonious fashion', which 'implicitly assumes that only few cell types change upon "
        "perturbation' (Büttner, Ostner et al. 2020). Where a perturbation moves most of the "
        "tissue at once, that assumption is wrong and the model will still return a short list.",
        "A POPULATION LEFT OUT DOES NOT LEAVE A HOLE - ITS EFFECT MOVES. Where a cell type with a "
        "real proportion change is absent from the analysis, its effect is misattributed to other, "
        "highly correlated types rather than simply lost (Rau et al., post-MI cardiac remodeling, "
        "2026). That applies directly to the annotator sentinels excluded here, and to any cell "
        "type an upstream step withheld: the remaining shares are not the shares that would have "
        "been measured with them present.",
        "Absolute cell numbers are not measured. A share is not a count of cells in a tissue: "
        "dissociation and QC both change what reaches the object, and neither is uniform across "
        "cell types.",
        "A shift measured after a batch correction cannot be separated from what the correction "
        "removed.",
        "scCODA returns CREDIBLE INCLUSION, not a p-value. Reading it as significance is a "
        "category error.",
    ],
}

#: pertpy's own acceptance-rate warning band, from `_base_coda.__run_mcmc`. Outside it the tool
#: prints "Results might be incorrect!" to a logger and returns a complete result anyway. The
#: numbers are the tool's, not a threshold chosen here, which is why they are not config: a band
#: a user can widen is a band that stops meaning what the tool meant by it.
ACCEPT_LOW, ACCEPT_HIGH = 0.6, 0.95

#: The magnitude below which pertpy counts a `beta` draw as switched OFF by the spike-and-slab
#: prior, from `__complete_beta_df`. Copied so the split-half inclusion probability drawn in
#: F3_sampling is the SAME quantity the tool thresholds, not a near neighbour of it.
SPIKE_ZERO = 1e-3

#: Okabe-Ito hues used for the quantities that are not categories - one for a credible effect, one
#: for the fold change. `figure.palette` is for labels; a bar that means "credible" is not a label.
CREDIBLE = "#0072B2"
FOLD = "#E69F00"

#: Okabe-Ito vermillion, for a number the WRAPPED TOOL itself warns about - currently only an
#: acceptance rate outside its own band. It marks nothing this plugin decides: a warning colour a
#: reader meets on a value nobody warned about teaches them to ignore it on the value somebody did.
WARN = "#D55E00"

#: The band behind the reference population's row. Lighter than `figure.GREY`, which is a MARK on
#: these panels ("not measured"), because a background that reads as a mark puts a third meaning on
#: a hue already carrying two.
REF_BAND = "#F0F0F0"

#: The tallest a figure may be. A journal page is 11 inches with margins, and a panel taller than
#: that is not a figure - it is a figure the reader will be handed at 60% scale, with 4 pt labels.
#: Every panel here grows with the number of populations, so without a stop one annotation makes
#: five unusable figures at once.
PAGE_HEIGHT = 9.4

#: EVERY EFFECT ON THIS PAGE IS RELATIVE TO ONE POPULATION, so which row that is has to be findable
#: without reading a caption. It is marked three ways - named in capitals in the axis label, bolded,
#: and given the row band above - because a reader who misses it misreads every other row.
REF_TAG = "  (REFERENCE)"


# ------------------------------------------------------------------------------------ helpers

def _num(pd, np, col):
    """A float array from a column that may be pandas' NULLABLE dtype.

    `summary_prepare` ends with `convert_dtypes(dtype_backend="numpy_nullable")`, so every column
    of the effect table comes back as Float64 carrying `pd.NA`. `.to_numpy()` on one of those
    yields an OBJECT array: matplotlib cannot plot it, `!= 0` returns another masked array, and
    the failure lands at draw time - an hour after the fit, on the one machine that had the newer
    pandas.
    """
    return pd.to_numeric(col, errors="coerce").to_numpy(dtype=float, na_value=np.nan)


def _flags(np, col, n):
    """A plain boolean array from a `credible` column, whatever dtype it arrived in.

    `d.reindex(order)` on an effect table that is short of a population turns a bool column into
    OBJECT dtype with `nan` in the gaps, and `.fillna(False)` on one of those is deprecated in
    pandas 2.2 and CHANGES BEHAVIOUR in 3 - so the ordinary case the reindex was written to
    survive is the one that prints a FutureWarning today and returns a different array on the
    next pandas this plugin's own `requires` will resolve to.

    Nothing is being filled in, which is why this is not a fillna. A value that is not a boolean
    is a population the tool returned no row for: it was not called credible because it was never
    tested, and False is the only reading of that a colour can carry.
    """
    if col is None:
        return np.zeros(int(n), dtype=bool)
    return np.array([v is True or v == 1 for v in col.to_numpy(dtype=object)], dtype=bool)


def _coda(model):
    """The sample-level AnnData, whether `prepare` handed back a MuData or an AnnData.

    Everything this plugin reads back - the inclusion-probability threshold, the acceptance rate,
    the posterior draws - lives in `uns["scCODA_params"]` on that object, and pertpy's own entry
    points take either shape. One accessor, so no figure has to know which it got.
    """
    return model["coda"] if hasattr(model, "mod") else model


def _counts_frame(ctx, pd, np):
    """A samples x populations count matrix, sentinels excluded and NAMED.

    `ctx.populations()` unpacks as `(mask, groups)`; `.names` and `.dropped` are what this wants.
    This read the two-tuple as `(populations, dropped)`: `set(pops)` became `{True, False}`, every
    population was filtered out of the crosstab as "not a population", and the next line asked the
    truth value of a numpy array - so the plugin would have died before reaching scCODA at all.

    Third of four plugins to misread the same two-tuple, which is why it now carries `.names` and
    `.dropped` as well.
    """
    pop = ctx.populations()
    mask = np.asarray(pop.mask)
    samp = ctx.obs("sample").astype(str).to_numpy()
    tab = pd.crosstab(pd.Series(samp[mask], name="sample"),
                      pd.Series(np.asarray(pop.groups), name="population"))
    return tab, pop.dropped


def _reference_frame(tab, pops, share, np, pd, absence_threshold):
    """Per population: how variable its share is, and how often it is missing entirely.

    Both columns are scCODA's own criteria for a reference, computed the way `_base_coda._prepare`
    computes them - dispersion is variance over mean of RELATIVE abundance, at ddof=0 as numpy
    does it, and eligibility is the fraction of samples with a zero COUNT. Recomputing them here
    rather than reading the tool's choice back is what lets the choice be drawn, and named, before
    an hour of sampling is spent on it.
    """
    n = len(tab.index)
    absent = (tab[pops] == 0).sum(axis=0).astype(float) / max(n, 1)
    mean = share.mean(axis=0)
    disp = share.var(axis=0, ddof=0) / mean.replace(0, np.nan)
    out = pd.DataFrame({"mean_share": mean, "dispersion": disp,
                        "fraction_of_samples_absent": absent,
                        "eligible_as_reference": absent < float(absence_threshold)})
    out.index.name = "population"
    return out.sort_values("dispersion")


def _pick_reference(ctx, refframe, pops, absence_threshold):
    """The population every effect will be measured against, and a sentence saying how it was got.

    Returns `(name, why)` or `(None, why)`, the second of which the caller turns into a refusal.
    Passing a NAME rather than "automatic" is deliberate: the tool's automatic path announces its
    choice in a logger line from inside the fit, and by then the run is already spending.
    """
    want = str(ctx.config["reference"])
    if want != "auto":
        if want not in pops:
            return None, (f"reference population {want!r} is not present. Available: "
                          f"{', '.join(map(str, pops))}")
        return want, "given in config"
    ok = refframe[refframe["eligible_as_reference"]]
    if not len(ok):
        best = refframe["fraction_of_samples_absent"].min()
        return None, (
            f"no population is present in enough samples to be an automatic reference: the least "
            f"absent is missing from {100 * float(best):.0f}% of samples and the threshold is "
            f"{100 * float(absence_threshold):.0f}%. Every effect must be measured against "
            f"something that is actually there in every arm.\n"
            f"  Fix: name one with --params '{{\"reference\": \"<population>\"}}', or raise "
            f"reference_absence_threshold and accept that the reference is pseudocounted where it "
            f"is missing.")
    name = str(ok["dispersion"].idxmin())
    return name, ("chosen by scCODA's own rule: lowest dispersion (variance/mean of share) among "
                  "the populations present in enough samples")


def _read_fit(ctx, sccoda, model, term, ref, credible, np, pd):
    """Everything one fitted term produced, in plain frames and floats.

    Read out of `uns["scCODA_params"]` rather than off the model object, because the model
    instance is reused across terms and pertpy's own `make_arviz` had to be changed for the same
    reason (their issue #812). Every lookup is a `.get`: a key this version does not write must
    cost the plugin one absent PANEL, declared as such, not a traceback over the whole run.
    """
    A = _coda(model)
    par = dict(A.uns.get("scCODA_params") or {})
    mcmc = dict(par.get("mcmc") or {})
    covs = [str(c) for c in (par.get("covariate_names") or [])]
    fit = {"term": term, "reference": ref, "covariates": covs,
           "threshold": float("nan"), "accept": float("nan"),
           "num_chains": int(mcmc.get("num_chains") or 1),
           "n_draws": int(mcmc.get("num_samples") or 0),
           "n_warmup": int(mcmc.get("num_warmup") or 0),
           "effects": None, "halves": None, "mismatch": 0}
    try:
        fit["threshold"] = float(np.asarray(par["threshold_prob"]).ravel()[0])
    except Exception:                                                     # noqa: BLE001
        ctx.log("  no inclusion-probability threshold recorded by the tool")
    try:
        fit["accept"] = float(np.asarray(mcmc["acceptance_rate"]).ravel()[0])
    except Exception:                                                     # noqa: BLE001
        ctx.log("  no acceptance rate recorded by the tool")

    # ---- the effects, as the tool's own table -------------------------------------------
    eff = None
    try:
        eff = sccoda.get_effect_df(model)
    except Exception as e:                                                # noqa: BLE001
        ctx.log(f"  effect table not readable: {e}")
    if eff is not None and len(eff):
        d = eff.reset_index()
        d.columns = [str(c) for c in d.columns]
        d = d.rename(columns={"Covariate": "covariate", "Cell Type": "population"})
        out = pd.DataFrame({"term": term,
                            "covariate": d["covariate"].astype(str),
                            "population": d["population"].astype(str),
                            "reference": ref})
        # ONLY THE COLUMNS THE TOOL ACTUALLY GAVE. An optional field is present-or-absent; a
        # column of NA under a name a reader recognises is worse than no column, because it types
        # as a number and reads as a measurement that came back empty.
        for new, old in (("effect", "Final Parameter"),
                         ("inclusion_probability", "Inclusion probability"),
                         ("log2_fold_change", "log2-fold change"),
                         ("expected_cells", "Expected Sample"),
                         ("sd", "SD")):
            if old in d:
                out[new] = _num(pd, np, d[old])
        hdi = [c for c in d.columns if c.startswith(("HDI", "ETI"))][:2]
        if len(hdi) == 2:
            out["hdi_low"] = _num(pd, np, d[hdi[0]])
            out["hdi_high"] = _num(pd, np, d[hdi[1]])
            out["hdi_columns"] = f"{hdi[0]} to {hdi[1]}"
        out["inclusion_threshold"] = fit["threshold"]
        # TWO ROUTES TO THE SAME BOOLEAN, AND THEY ARE COMPARED. `credible_effects` is the tool's
        # answer; `Final Parameter != 0` is how the tool computes it. They can only disagree if
        # the two halves are at different FDR levels - which is exactly what happens when
        # `set_fdr` was never called and `credible_effects(est_fdr=...)` recomputed without
        # storing. A disagreement is reported rather than silently resolved.
        own = (out["effect"].to_numpy() != 0) if "effect" in out else None
        cred = np.asarray(credible).astype(bool).ravel() if credible is not None else None
        if cred is not None and len(cred) == len(out):
            out["credible"] = cred
            if own is not None:
                fit["mismatch"] = int((cred != own).sum())
        elif own is not None:
            out["credible"] = own
        fit["effects"] = out

    # ---- did the chain settle on the inclusion probability -------------------------------
    # NOT R-hat AND NOT A TRACE. "Due to the spike-and-slab priors, the beta parameters have many
    # values at 0, which looks like a convergence issue, but is actually not" (scCODA docs), and
    # the reference's effect is constant at 0 for the whole chain. So the check is on the derived
    # quantity the decision is actually made on: the share of draws in which the effect was not
    # switched off, computed on the first half of the chain against the second.
    beta = (mcmc.get("samples") or {}).get("beta")
    names = [str(x) for x in A.var.index]
    try:
        b = np.asarray(beta, dtype=float)
    except Exception:                                                     # noqa: BLE001
        b = None
    if b is not None and b.ndim == 3 and b.shape[0] >= 4 \
            and b.shape[1] == len(covs) and b.shape[2] == len(names):
        h = b.shape[0] // 2
        i1 = (np.abs(b[:h]) > SPIKE_ZERO).mean(axis=0)
        i2 = (np.abs(b[h:]) > SPIKE_ZERO).mean(axis=0)
        rows = [{"term": term, "covariate": covs[j], "population": names[k],
                 "inclusion_first_half": float(i1[j, k]),
                 "inclusion_second_half": float(i2[j, k]),
                 "difference": float(abs(i1[j, k] - i2[j, k]))}
                for j in range(len(covs)) for k in range(len(names))]
        fit["halves"] = pd.DataFrame(rows)
    else:
        ctx.log("  posterior draws for `beta` not found in the shape this plugin reads; the "
                "chain cannot be split")
    return fit


def _contrasts(fits):
    """(fit, covariate) for every column the design matrix produced, in fitted order.

    A two-level factor gives one; a three-level factor gives two, both against the level patsy
    took as base. The panels are drawn per CONTRAST rather than per term for that reason - a
    figure with one panel per term silently shows the first contrast of a three-level factor and
    calls it the factor.
    """
    return [(f, c) for f in fits for c in (f["covariates"] or [f["term"]])]


# ------------------------------------------------------------------------------------ figures
#
# No basis, and there is nothing to be sorry about in that: a composition is a table of shares per
# sample, the model is fitted on that table, and the honest picture of it is the samples. Nothing
# below reads an embedding or a layout.

def _strip(ax, np, xs, ys, colour, s=13):
    """One row of per-sample points. Used by the shares panel and by the reference panel.

    A HAIRLINE WHITE EDGE, WHICH IS NOT DECORATION. These are replicate points and the reader's
    question is how many there are and whether one sits apart; drawn as flat discs at s=7 two
    samples with near-equal shares were one dot, so a panel whose whole purpose is to show the
    replicates was under-reporting them. The edge separates touching points and costs nothing -
    the collection is rasterised.
    """
    ax.scatter(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float), s=s, color=colour,
               edgecolors="white", linewidths=0.35, zorder=3)


def _population_axis(ax, np, F, order, ref):
    """The shared y axis of this page: one row per population, the reference NAMED and bolded.

    Every panel below the shares one is drawn in the same row order, so the axis is built once
    here rather than four times - a result panel and its credibility panel that disagree about
    which row is which is a figure that cannot be read across, and that is a whole-page property
    rather than a per-panel one.

    NAMES ARE CUT TO THE SHORTEST UNAMBIGUOUS TAIL, `figure.short_labels`, because a population
    name is often an annotation PATH and the full path took a third of the panel width away from
    the data. Cutting stops as soon as two names would collide, so a shortened label still names
    exactly one population; the full path stays in the source table under every figure.
    """
    short = F.short_labels([str(p) for p in order])
    ax.set_yticks(np.arange(len(order)))
    ax.set_yticklabels([short[str(p)] + (REF_TAG if p == ref else "") for p in order])
    for lab, p in zip(ax.get_yticklabels(), order):
        if p == ref:
            lab.set_fontweight("bold")
    return short


def _reference_row(ax, order, ref):
    """The band behind the reference row, drawn in the panel body rather than only in the label."""
    if ref in list(order):
        i = list(order).index(ref)
        ax.axhspan(i - 0.5, i + 0.5, color=REF_BAND, lw=0, zorder=0)


def _rows(ax, F, n, lo=0.0, hi=1.0):
    """The per-row guide line every panel here is read along.

    It carries more than tidiness: an effect of exactly zero and an inclusion probability of
    exactly zero both draw NOTHING, and without a line those rows are a label with blank space
    beside them - which reads as a population the run forgot rather than one the model fixed.
    """
    for i in range(int(n)):
        ax.hlines(i, lo, hi, colors=F.GREY, lw=0.4, zorder=1)


def _bare(ax, F, keep_x=False):
    """Strip an axis of the furniture a categorical row-plot does not use."""
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    if not keep_x:
        ax.spines["bottom"].set_visible(False)
        ax.set_xticks([])


def _ratio(a, b):
    """`b / a` as text, or a dash where it cannot be formed. Never a bare `inf` on a figure."""
    try:
        a, b = float(a), float(b)
    except Exception:                                                     # noqa: BLE001
        return "-"
    if not (a > 0) or not (b >= 0):
        return "-"
    r = b / a
    return f"{r:.2f}x" if r < 10 else f"{r:.0f}x"


def _height(ctx, want, rows, name):
    """`want` inches, capped at a page - and the cap is SAID when it bites.

    A cap applied silently hands the reader a panel whose labels have merged into a grey band and
    no reason to distrust it, which is the one failure mode a figure cannot signal for itself.
    `rows` is the number of DRAWN rows, not of panels: the sentence a reader needs is how much
    height each row got, and on a stacked panel that is not the same as height per panel.
    """
    want, rows = float(want), max(int(rows), 1)
    if want <= PAGE_HEIGHT:
        return want
    ctx.caveat(
        f"{name} draws {rows} rows and wanted {want:.1f} inches; it was capped at {PAGE_HEIGHT} "
        f"so it still fits a page, which leaves {PAGE_HEIGHT / rows:.2f} inches per row. Rows may "
        f"be too close to read at print size - the numbers behind every mark are in the table "
        f"named as this figure's source.")
    return PAGE_HEIGHT


def _flat_column(axs, np, F, values, note):
    """Give a column of axes a readable scale when everything in it is exactly zero.

    A COLUMN OF ZEROS AUTOSCALES TO A LIE. Where no effect is called, every fold change the tool
    returns is exactly 0, and matplotlib answers a range of zero with a default of about +/-0.05 -
    so the panel arrives with tick labels at two decimal places and no bars, which reads as a
    scale someone chose and a set of very small changes, rather than as a column of exact zeros.
    """
    v = np.asarray(values, dtype=float)
    if v.size and np.isfinite(v).any() and float(np.nanmax(np.abs(v))) > 0:
        return
    for ax in axs:
        ax.set_xlim(-1, 1)
    axs[0].text(0.5, 0.5, note, transform=axs[0].transAxes, ha="center", va="center",
                fontsize=6, color=F.INK)


def _call_key(F, ml, ref_short, fdr_note="credible"):
    """The three-way encoding shared by the credibility panel and the result panel.

    FILLED, HOLLOW, GREY - a shape difference and not only a hue difference, so the distinction
    survives greyscale printing and every form of colour-vision deficiency. It has to: the
    difference between "called" and "measured and not called" is the entire result.
    """
    return [
        ml.Line2D([], [], marker="o", ls="", ms=3.2, color=CREDIBLE, label=fdr_note),
        ml.Line2D([], [], marker="o", ls="", ms=3.2, mfc="none", mec=F.INK, mew=0.7,
                  color="none", label="measured, not called"),
        ml.Line2D([], [], marker="s", ls="", ms=3.2, mfc=F.GREY, mec=F.INK, mew=0.4,
                  color="none", label=f"{ref_short}: not measured"),
    ]


def _fig_shares(ctx, tab, pops, terms, share, order, ref):
    """The data the model is fitted on, one point per sample - the panel that licenses the rest."""
    import numpy as np
    import pandas as pd
    import matplotlib.lines as ml
    F, plt = ctx.figure, ctx.plot()

    # THE LEVEL MEANS ARE COMPUTED ONCE AND DRAWN, and they are computed here rather than by eye
    # from the points because a reader cannot average five dots on a logarithmic axis. Ten
    # replicate points answer "does one sample carry it"; they do not answer "by how much", and
    # this panel is asked both.
    lvs = {t: sorted({str(x) for x in tab[t]}) for t in terms}
    means = {t: {l: share.loc[[s for s in tab.index if str(tab.loc[s, t]) == l]].mean(axis=0)
                 for l in lvs[t]} for t in terms}

    rows = []
    totals = tab[pops].sum(axis=1)
    for s in tab.index:
        for p in pops:
            r = {"sample": str(s), "population": str(p), "count": float(tab.loc[s, p]),
                 "share": float(share.loc[s, p]), "cells_in_sample": float(totals.loc[s])}
            for t in terms:
                r[t] = str(tab.loc[s, t])
            # EVERY NUMBER THAT IS DRAWN IS IN THE SOURCE TABLE. The level means and the ratio
            # between them are marks on the panel now, so a reader must be able to open them
            # rather than re-derive them from the per-sample column.
            for t in terms:
                for l in lvs[t]:
                    r[f"mean_share[{t}={l}]"] = float(means[t][l][p])
                ms = [float(means[t][l][p]) for l in lvs[t]]
                a, b = (ms[0], ms[1]) if len(ms) == 2 else (min(ms), max(ms))
                r[f"ratio_of_level_means[{t}]"] = (b / a) if a > 0 else np.nan
            rows.append(r)
    src = pd.DataFrame(rows).set_index("sample")

    levels = sorted({str(tab.loc[s, t]) for t in terms for s in tab.index})
    cols = F.palette(levels)
    clash = getattr(F, "palette_collisions", None)
    for _colour, labs in (clash(levels) if clash else []):
        ctx.caveat(f"Design levels {', '.join(labs)} share one colour in the composition figure; "
                   f"there are more levels than the palette has separable hues. Read those from "
                   f"tables/abundance_counts.csv rather than from the panel.")

    n = len(terms)
    # A NARROW TEXT COLUMN BESIDE EACH TERM. The ratio was tried as an annotation inside the
    # panel and there is nowhere inside a panel to put it: the axis runs to a share of 1 and a
    # population can sit anywhere on it, so any x that is empty in one dataset is on top of the
    # data in the next. A column of its own cannot collide with anything.
    fig, axs = plt.subplots(1, 2 * n, squeeze=False, sharey=True, layout="constrained",
                            gridspec_kw={"width_ratios": [1.0, 0.30] * n},
                            figsize=(F.SINGLE if n == 1 else F.DOUBLE,
                                     _height(ctx, max(2.2, 0.30 * len(order) + 1.2),
                                             len(order), "F1_shares")))
    for k, t in enumerate(terms):
        ax, strip = axs[0][2 * k], axs[0][2 * k + 1]
        lv = lvs[t]
        _reference_row(ax, order, ref)
        _reference_row(strip, order, ref)
        _rows(ax, F, len(order))
        step = 0.62 / max(len(lv), 1)
        for i, p in enumerate(order):
            ys = [i + (j - (len(lv) - 1) / 2.0) * step for j in range(len(lv))]
            ms = [float(means[t][l][p]) for l in lv]
            # THE SHIFT, AS ONE MARK. Drawn under the points and over the guide line, so the eye
            # reads the segment first and the replicates second - which is the order the two
            # questions come in. On a logarithmic axis its length IS the log ratio.
            ax.plot(ms, ys, color=F.INK, lw=1.1, alpha=0.55, zorder=2, solid_capstyle="round")
            for j, l in enumerate(lv):
                sel = [s for s in tab.index if str(tab.loc[s, t]) == l]
                if sel:
                    _strip(ax, np, share.loc[sel, p].to_numpy(), np.full(len(sel), ys[j]), cols[l])
            # A TICK ACROSS THE ROW, NOT A MARKER ON IT. Drawn as a diamond the mean sat on top of
            # the replicates it summarises and hid them - in the panel whose first question is how
            # many replicates there are and whether one sits apart. A perpendicular tick occupies
            # the row rather than the point, and is dark rather than level-coloured so it reads as
            # a different KIND of thing from the dots.
            # Short enough that two adjacent levels' ticks cannot touch: at half a level's
            # spacing they abutted into one continuous bar with a kink in it, which is a single
            # mark where there are two means and a shift between them.
            ax.vlines(ms, [y - 0.10 for y in ys], [y + 0.10 for y in ys],
                      colors=F.INK, lw=1.4, zorder=6)
        F.rasterize_points(ax)
        # LINEAR BELOW 1%, LOGARITHMIC ABOVE. On a linear axis every rare population sits on the
        # spine and a doubling of a 0.5% population is invisible beside a 40% one - which is the
        # comparison this panel exists to make. symlog is defined at zero, and a zero share is
        # exactly the value a reader must be able to see.
        ax.set_xscale("symlog", linthresh=0.01)
        # A HAIR PAST ZERO ON THE LEFT. A population absent from a sample is drawn at exactly 0
        # and, with the limit AT zero, half that marker is behind the spine - so the one value a
        # reader most needs to see on a share axis was the one drawn as a half-disc.
        ax.set_xlim(-0.0016, 1)
        # PER CENT, NOT POWERS OF TEN. A composition is read as a percentage by everyone who
        # reads one, and `10^-2` on a share axis is a translation the reader should not be asked
        # to make. The dotted line is where the scale stops being logarithmic - unmarked, the
        # spacing below it looks like a decade and is not.
        ax.set_xticks([0.0, 0.01, 0.1, 1.0])
        ax.set_xticklabels(["0", "1%", "10%", "100%"])
        ax.axvline(0.01, color=F.GREY, lw=0.5, ls=":", zorder=0)
        ax.set_xlabel("share of cells in the sample")
        ax.set_title(str(t), loc="left")
        _bare(ax, F, keep_x=True)

        # ---- the ratio column ------------------------------------------------------------
        head = (f"{lv[1]}\n/ {lv[0]}" if len(lv) == 2 else "widest ratio\nof level means")
        strip.set_xlim(0, 1)
        for i, p in enumerate(order):
            ms = [float(means[t][l][p]) for l in lv]
            a, b = (ms[0], ms[1]) if len(ms) == 2 else (min(ms), max(ms))
            txt = _ratio(a, b)
            heavy = txt != "-" and abs(np.log2(max(b, 1e-12) / max(a, 1e-12))) >= 1.0
            strip.text(0.5, i, txt, ha="center", va="center", fontsize=6,
                       color=F.INK, fontweight="bold" if heavy else "normal")
        strip.set_xlabel(head, fontsize=5.5)
        _bare(strip, F)

    _population_axis(axs[0][0], np, F, order, ref)
    # SET, NOT INVERTED. `invert_yaxis` toggles, and on a shared axis any panel that had already
    # set a descending limit flipped the whole figure back - which put the largest population at
    # the bottom and every panel of the page in a different order from this one.
    axs[0][0].set_ylim(len(order) - 0.5, -0.5)
    # EACH LEVEL NAMED WITH ITS OWN FACTOR, ALONG THE BOTTOM. Two things at once. A flat list of
    # every level in the study reads as one set of categories and with two factors on one figure
    # it is two, so a reader matching a hue to the wrong factor's key reads the wrong panel -
    # hence `factor = level` rather than a bare level name. And the key is below the axes rather
    # than in the right margin because `figure.fit_column` charges a margin key to the figure's
    # WIDTH, taking it from the panels; below, it is charged to height, of which a row plot has
    # as much as it needs.
    if n > 1:
        h = [ml.Line2D([], [], marker="o", ls="", ms=2.5, color=cols[l], label=f"{t} = {l}")
             for t in terms for l in lvs[t]]
    else:
        h = [ml.Line2D([], [], marker="o", ls="", ms=2.5, color=cols[l], label=l) for l in levels]
    h.append(ml.Line2D([], [], marker="|", ls="", ms=5, mew=1.4, color=F.INK,
                       label="level mean"))
    fig.legend(h, [x.get_label() for x in h], loc="outside lower center",
               ncol=min(len(h), 5 if n > 1 else 6), frameon=False, handletextpad=0.4,
               columnspacing=1.6, markerscale=1.6)
    two = all(len(lvs[t]) == 2 for t in terms)
    ctx.emit_figure(
        "F1_shares", fig,
        caption=("Every sample's share of every population, one point per sample, split by design "
                 "level. This is the whole of the data the model is fitted on: the fit has as many "
                 "rows as there are points in one column here, so a level whose points do not "
                 "separate from the other level's has no shift for the model to find, and a level "
                 "carried by one outlying sample has one that belongs to that library. The "
                 "TICK is that level's mean share and the segment joining the ticks is the "
                 "shift; on a logarithmic axis its length is the log ratio, and the column beside "
                 "each panel gives that ratio as a number"
                 + (", larger level over smaller where a factor has more than two levels"
                    if not two else "")
                 + " (bold at two-fold or more). Those means are DESCRIPTIVE - the model's own "
                 "estimate of the same shift is F5, it is measured relative to the reference "
                 "population, and the two are not required to agree. The x axis is linear below "
                 "1% and logarithmic above, so a rare population's change is visible beside a "
                 "common one's; the dotted line is where the scale changes. Population names are "
                 "cut to their shortest unambiguous tail and given in full in the source table. "
                 "Annotator sentinels are not shown as populations."),
        source=src)

def _fig_reference(ctx, refframe, tab, terms, share, ref, why):
    """The reference, on the tool's own criterion and against the design it must not follow."""
    import numpy as np
    import matplotlib.lines as ml
    from matplotlib.ticker import PercentFormatter
    F, plt = ctx.figure, ctx.plot()

    d = refframe.copy()
    d["is_reference"] = [p == ref for p in d.index]
    # The per-level means go in the SOURCE for every population, not only the reference: the right
    # panel draws one population's points, and a reader asking the same question of another
    # population should not have to re-derive it.
    for t in terms:
        for l in sorted({str(x) for x in tab[t]}):
            sel = [s for s in tab.index if str(tab.loc[s, t]) == l]
            d[f"mean_share[{t}={l}]"] = [float(share.loc[sel, p].mean()) if sel else np.nan
                                         for p in d.index]

    levels = sorted({str(tab.loc[s, t]) for t in terms for s in tab.index})
    cols = F.palette(levels)
    pairs = [(t, l) for t in terms for l in sorted({str(x) for x in tab[t]})]
    nrow = max(len(d), len(pairs))
    short = F.short_labels([str(p) for p in d.index] + [str(ref)])
    fig, axs = plt.subplots(1, 2, squeeze=False, layout="constrained",
                            figsize=(F.DOUBLE, _height(ctx, max(2.2, 0.26 * nrow + 1.3), nrow,
                                                       "F2_reference")))

    ax = axs[0][0]
    y = np.arange(len(d))
    # A LOGARITHMIC AXIS, AND POINTS RATHER THAN BARS. Drawn as bars on a linear axis this panel
    # was unreadable in both directions at once: dispersion runs over orders of magnitude, so the
    # single ineligible population squashed every candidate into one indistinguishable sliver -
    # in the panel whose whole job is to show WHY one of them was chosen - and the tick labels
    # were six-decimal numbers running into each other. A bar cannot start at zero on a log axis;
    # a point has no such problem.
    disp = d["dispersion"].to_numpy(dtype=float)
    good = np.isfinite(disp) & (disp > 0)
    lo = float(disp[good].min()) / 3.0 if good.any() else 1e-6
    hi = float(disp[good].max()) * 3.0 if good.any() else 1.0
    _reference_row(ax, list(d.index), ref)
    for i in y:
        ax.hlines(i, lo, hi, colors=F.GREY, lw=0.4, zorder=1)
    x = np.where(good, disp, lo)
    elig = d["eligible_as_reference"].to_numpy(dtype=bool)
    isref = d["is_reference"].to_numpy(dtype=bool)
    # THREE STATES, AND HOLLOW IS ONE OF THEM. An ineligible candidate was drawn in `figure.GREY`,
    # which at 15% ink on white is the colour this page uses for "not measured" and reads at a
    # glance as a value that failed to arrive. It is the opposite: it was measured, and REFUSED.
    # A hollow marker says refused; only a hue said it before, and faintly.
    ax.scatter(x[~elig], y[~elig], s=20, facecolors="none", edgecolors=F.INK, linewidths=0.8,
               zorder=3)
    ax.scatter(x[elig & ~isref], y[elig & ~isref], s=16, color=F.INK, linewidths=0, zorder=3)
    ax.scatter(x[isref], y[isref], s=44, marker="D", color=CREDIBLE, edgecolors="white",
               linewidths=0.8, zorder=5)
    F.rasterize_points(ax)
    ax.set_xscale("log")
    ax.set_xlim(lo, hi)
    if not good.all():
        # A POINT PARKED ON THE AXIS FLOOR IS NOT A MEASUREMENT, and a log axis drops
        # non-positive values without saying so. Named here rather than left to look like the
        # most stable population in the dataset - which is exactly how it would read.
        ctx.caveat(
            "Population(s) " + ", ".join(str(p) for p, ok in zip(d.index, good) if not ok)
            + " have no dispersion to place on the reference panel's logarithmic axis - their "
              "share did not vary at all across samples, or their mean is zero. They are drawn at "
              "the left edge, which is a position rather than a value.")
    ax.set_yticks(y)
    # THE ABSENCE IS GIVEN AS A NUMBER. "too often absent" is the verdict, not the evidence, and
    # the reader's next question - how much of the threshold did it miss by - was answerable only
    # from a table that is not on the page.
    ax.set_yticklabels([
        short[str(p)] + (REF_TAG if p == ref else
                         ("" if e else f"  (absent from {100 * float(a):.0f}% of samples)"))
        for p, e, a in zip(d.index, d["eligible_as_reference"],
                           d["fraction_of_samples_absent"])])
    for lab, p in zip(ax.get_yticklabels(), d.index):
        if p == ref:
            lab.set_fontweight("bold")
    ax.set_ylim(len(d) - 0.5, -0.5)
    ax.set_xlabel("dispersion of share across samples (variance / mean)")
    ax.set_title("what the reference was chosen on", loc="left")
    _bare(ax, F, keep_x=True)

    ax2 = axs[0][1]
    # THE COHORT MEAN, AS THE LINE THE ARMS ARE READ AGAINST. Without it the arm means are two
    # points in space and the eye supplies its own baseline - usually the axis, which is zero and
    # is not the comparison anyone is making. Labelled ON the line rather than in a key: a margin
    # legend is charged to this panel's WIDTH by `figure.fit_column`, and two marks did not
    # justify a fifth of it.
    cohort = float(share[ref].mean())
    ax2.axvline(cohort, color=F.INK, lw=0.6, ls="--", zorder=2)
    ax2.text(cohort, -0.62, "cohort mean", ha="center", va="center", fontsize=5.5, color=F.INK)
    for i, (t, l) in enumerate(pairs):
        sel = [s for s in tab.index if str(tab.loc[s, t]) == l]
        ax2.hlines(i, 0, 1, colors=F.GREY, lw=0.4, zorder=1)
        if sel:
            m = float(share.loc[sel, ref].mean())
            _strip(ax2, np, share.loc[sel, ref].to_numpy(), np.full(len(sel), i), cols[l])
            ax2.vlines(m, i - 0.16, i + 0.16, colors=F.INK, lw=1.4, zorder=6)
    # ONE RATIO PER FACTOR, WHICH IS THE ANSWER THIS PANEL WAS ASKED FOR. "Did the reference move"
    # is a question about a NUMBER, and a reader cannot take the ratio of two clouds of dots by
    # eye on an axis that starts at zero - which it must, because a share is a proportion and a
    # zoomed axis makes a one-per-cent wobble look like a shift.
    seps, at = [], 0
    for t in terms:
        lv = sorted({str(x) for x in tab[t]})
        ms = [float(share.loc[[s for s in tab.index if str(tab.loc[s, t]) == l], ref].mean())
              for l in lv]
        a, b = (ms[0], ms[1]) if len(ms) == 2 else (min(ms), max(ms))
        d[f"reference_ratio_of_level_means[{t}]"] = (b / a) if a > 0 else np.nan
        # THE NUMBER SAYS WHAT IT IS THE RATIO OF. Unlabelled it was a bold figure floating
        # between two rows, and a reader who guesses which way round it goes gets the direction of
        # every effect on the page backwards.
        head = f"{lv[1]} / {lv[0]}" if len(lv) == 2 else "widest / narrowest"
        ax2.text(0.985, at + (len(lv) - 1) / 2.0, f"{head}\n{_ratio(a, b)}",
                 transform=ax2.get_yaxis_transform(), ha="right", va="center",
                 fontsize=6, color=F.INK, linespacing=1.5)
        at += len(lv)
        seps.append(at - 0.5)
    for s_ in seps[:-1]:
        ax2.axhline(s_, color=F.GREY, lw=0.6, zorder=0)
    F.rasterize_points(ax2)
    ax2.set_yticks(np.arange(len(pairs)))
    ax2.set_yticklabels([f"{t} = {l}" for t, l in pairs])
    # HALF A SLOT OF MARGIN, EXPLICITLY. Matplotlib's default 5% margin on a handful of rows puts
    # the first and last of them on the frame; these panels have as few as two.
    ax2.set_ylim(len(pairs) - 0.5, -1.0)
    ax2.set_xlim(0, max(0.01, float(share[ref].max()) * 1.45))
    # PER CENT, AS ON THE SHARES PANEL. The same quantity written two ways on one page - `0.020`
    # here and `1%` there - is a translation the reader has to make between two panels that are
    # meant to be read against each other.
    ax2.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=1))
    ax2.set_xlabel(f"share of {short[str(ref)]} in the sample")
    ax2.set_title("did the reference itself move", loc="left")
    _bare(ax2, F, keep_x=True)

    # THREE MARKS, ALONG THE BOTTOM, AND ONLY THE LEFT PANEL'S. A key in the right margin is
    # charged to the figure's WIDTH - `figure.fit_column` shrinks the whole canvas back to the
    # declared column afterwards - and a nine-entry key measured a FIFTH of this figure, taken
    # from the right panel's data. The right panel's two marks are named where they are drawn:
    # the dashed line carries its own label, and the level-mean tick is the one this page's
    # first figure teaches.
    key = [ml.Line2D([], [], marker="D", ls="", ms=3.4, color=CREDIBLE, label="the reference"),
           ml.Line2D([], [], marker="o", ls="", ms=3.0, color=F.INK, label="eligible candidate"),
           ml.Line2D([], [], marker="o", ls="", ms=3.0, mfc="none", mec=F.INK, mew=0.8,
                     color="none", label="refused: too often absent")]
    fig.legend(key, [k.get_label() for k in key], loc="outside lower center", ncol=3,
               frameon=False, handletextpad=0.4, columnspacing=1.6, markerscale=1.6)

    ctx.emit_figure(
        "F2_reference", fig,
        caption=(f"The reference population, which is {ref} ({why}). LEFT: the criterion it was "
                 f"chosen on - dispersion of each population's share across samples, lowest "
                 f"first; a hollow marker is a population that was measured and REFUSED as a "
                 f"candidate for being absent from too many samples, and its axis label gives the "
                 f"fraction it was refused on. RIGHT: the assumption itself. Every effect in this "
                 f"plugin's result is a change RELATIVE TO this population, so if its own share "
                 f"differs between the levels drawn here, the effects carry that difference with "
                 f"the opposite sign and nothing else in the output will say so. The bold number "
                 f"in each factor's block is the ratio of that factor's level means, and the axis "
                 f"deliberately starts at zero: a share is a proportion, and an axis zoomed onto "
                 f"the data would make any wobble look like a shift. The tick across each row is "
                 f"that level's mean, as on the shares figure, and the key below names the marks "
                 f"of the left panel. "
                 f"The per-sample values on the "
                 f"right are the {ref} rows of figures/F1_shares.csv. Population names are cut to "
                 f"their shortest unambiguous tail; the source table gives them in full."),
        source=d)

def _fig_sampling(ctx, fits):
    """Whether the chain settled, checked on the quantity the answer is read off."""
    import numpy as np
    import pandas as pd
    have = [f for f in fits if f["halves"] is not None]
    rated = [f for f in fits if np.isfinite(f["accept"])]
    # TWO CHECKS, TWO KEYS, AND THEY GO MISSING SEPARATELY. `samples['beta']` and
    # `acceptance_rate` are different entries of uns['scCODA_params']; a version that moves one
    # still writes the other. This returned on the DRAWS alone, so a tool that recorded a bad
    # acceptance rate and no draws drew nothing - and the acceptance rate is the whole reason this
    # panel exists, because pertpy raises it through a logger and nowhere else. Either half is
    # enough to draw; the caption and `when_absent` say which one is here.
    if not have and not rated:
        return
    F, plt = ctx.figure, ctx.plot()
    if have:
        src = pd.concat([f["halves"] for f in have], ignore_index=True)
    else:
        # ONLY THE COLUMNS THERE ARE. An `inclusion_first_half` column of NA would type as a
        # number and read as a check that came back empty, when the truth is that it was never
        # made - the same rule the effect table above is built under.
        src = pd.DataFrame({"term": [f["term"] for f in fits]})
    rate = {f["term"]: f["accept"] for f in fits}
    src["acceptance_rate"] = [rate.get(t, float("nan")) for t in src["term"]]
    src["draws"] = [next((f["n_draws"] for f in fits if f["term"] == t), 0) for t in src["term"]]
    src["chains"] = [next((f["num_chains"] for f in fits if f["term"] == t), 1) for t in src["term"]]

    # WHETHER THE CALL FLIPPED, NOT ONLY WHETHER THE NUMBER MOVED. An inclusion probability that
    # wandered from 0.11 to 0.19 changed nothing; one that crossed the threshold changed the
    # answer for that population, and only the second is a reason to re-run. Computed per row so
    # it is in the source table as well as on the panel.
    flip = np.zeros(len(src), dtype=bool)
    if have and "inclusion_first_half" in src.columns:
        thr = {f["term"]: f["threshold"] for f in fits}
        t1 = src["inclusion_first_half"].to_numpy(dtype=float)
        t2 = src["inclusion_second_half"].to_numpy(dtype=float)
        cut = np.array([thr.get(t, np.nan) for t in src["term"]], dtype=float)
        flip = np.isfinite(cut) & ((t1 >= cut) != (t2 >= cut))
    src["call_changed_between_halves"] = flip

    terms = [f["term"] for f in fits]
    cols = F.palette(terms)
    # SQUARE, BECAUSE THE CLAIM IS ABOUT A DIAGONAL. On a wider-than-tall axis the y=x line is not
    # at 45 degrees, and "how far off the diagonal" - the only thing this panel is read for - is
    # then a judgement the reader makes against a line whose slope the aspect ratio chose.
    fig, axs = plt.subplots(1, 2, figsize=(F.DOUBLE, max(2.9, 0.24 * len(terms) + 2.6)),
                            squeeze=False, layout="constrained",
                            gridspec_kw={"width_ratios": [1.0, 0.85]})
    ax = axs[0][0]
    ax.plot([0, 1], [0, 1], color=F.GREY, lw=0.6, zorder=1)
    for f in have:
        h = f["halves"]
        a = h["inclusion_first_half"].to_numpy(dtype=float)
        b = h["inclusion_second_half"].to_numpy(dtype=float)
        moved = (np.isfinite(f["threshold"])
                 & ((a >= f["threshold"]) != (b >= f["threshold"]))) if np.isfinite(
                     f["threshold"]) else np.zeros(len(a), dtype=bool)
        ax.scatter(a, b, s=11, color=cols[f["term"]], linewidths=0, alpha=0.85, zorder=3)
        # A RING ROUND EVERY POPULATION WHOSE CALL CHANGED. These are the only points on the panel
        # that cost anything, and undecorated they are indistinguishable from the dozen ordinary
        # ones near the same place on the diagonal.
        if moved.any():
            ax.scatter(a[moved], b[moved], s=52, facecolors="none", edgecolors=WARN,
                       linewidths=1.0, zorder=4)
        if np.isfinite(f["threshold"]):
            for line in (ax.axvline, ax.axhline):
                line(f["threshold"], color=cols[f["term"]], ls="--", lw=0.5, zorder=2)
    F.rasterize_points(ax)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("inclusion probability, first half of chain")
    ax.set_ylabel("inclusion probability, second half")
    ax.set_title("did the decision stop moving", loc="left")
    if have:
        # THE SUMMARY IN WORDS, IN THE CORNER THE DATA CANNOT REACH. The dashed lines are one per
        # term and a fourth dashed line labelled in the margin is not a legend anybody reads; the
        # count is what a reader wants and it is one number per term.
        lines = []
        for f in have:
            h = f["halves"]
            a = h["inclusion_first_half"].to_numpy(dtype=float)
            b = h["inclusion_second_half"].to_numpy(dtype=float)
            nm = int(((a >= f["threshold"]) != (b >= f["threshold"])).sum()) \
                if np.isfinite(f["threshold"]) else -1
            thr = f"cut {f['threshold']:.3f}" if np.isfinite(f["threshold"]) else "no cut recorded"
            got = f"{nm} of {len(a)} calls changed" if nm >= 0 else "cannot say: no cut recorded"
            lines.append((cols[f["term"]], f"{f['term']}  -  {thr}  -  {got}"))
        for j, (c, txt) in enumerate(lines):
            ax.text(0.97, 0.03 + 0.055 * (len(lines) - 1 - j), txt, transform=ax.transAxes,
                    ha="right", va="bottom", fontsize=5.5, color=c)
    else:
        # AN EMPTY PANEL SAYS WHY IT IS EMPTY. An axis with a diagonal and no points reads as a
        # check that was made and found nothing, which is the opposite of what happened.
        ax.text(0.5, 0.5, "the posterior draws were not\nrecorded: no chain to split",
                transform=ax.transAxes, ha="center", va="center", color=F.INK, fontsize=6)

    # NO LEGEND ON EITHER PANEL, and not by omission: the right panel's y-ticks are the terms and
    # its points carry the same hue as the left panel's, so the tick labels ARE the key. A legend
    # here would have had to sit on the data - the interesting points are the ones off the
    # diagonal, which is exactly where a corner legend goes.
    ax2 = axs[0][1]
    y = np.arange(len(fits))
    ax2.axvspan(ACCEPT_LOW, ACCEPT_HIGH, color=F.GREY, alpha=0.55, lw=0, zorder=0)
    # A POINT ON A GUIDE LINE, NOT A BAR AND NOT A STEM FROM ZERO. There are as many rows here as
    # there are terms - usually two - and two bars in a panel sized for a square scatter beside it
    # are two slabs. A stem is no better: it encodes the rate as a LENGTH FROM ZERO, and an
    # acceptance rate is not a magnitude, it is a position inside a band. The point carries the
    # value; a rate that was never recorded draws none - leaving its label and, in words, why.
    for i, f in enumerate(fits):
        a = f["accept"]
        ax2.hlines(i, 0, 1, colors=F.GREY, lw=0.4, zorder=1)
        if not np.isfinite(a):
            ax2.text(0.5, i, "not recorded by this version of the tool", ha="center", va="center",
                     fontsize=5.5, color=F.INK)
            continue
        out = not (ACCEPT_LOW <= a <= ACCEPT_HIGH)
        ax2.scatter([a], [i], s=30, color=cols[f["term"]], zorder=4,
                    edgecolors=WARN if out else "white", linewidths=1.1 if out else 0.6)
        # THE NUMBER, BECAUSE THE DECISION IS MADE ON THE NUMBER. pertpy's band is 0.6-0.95 and a
        # point drawn at 0.58 sits against the edge of the shading; whether it is inside is not a
        # thing to read off a position, and it is the one judgement this panel exists for.
        ax2.text(min(a + 0.02, 0.99), i - 0.10, f"{a:.3f}" + ("  outside the band" if out else ""),
                 ha="left" if a < 0.6 else "right", va="bottom", fontsize=6,
                 color=WARN if out else F.INK, fontweight="bold" if out else "normal")
    F.rasterize_points(ax2)
    ax2.set_yticks(y)
    ax2.set_yticklabels(terms)
    ax2.set_ylim(len(fits) - 0.5, -0.5)
    ax2.set_xlim(0, 1)
    ax2.set_xlabel("mean acceptance rate")
    ax2.set_title(f"the tool's own band, {ACCEPT_LOW}-{ACCEPT_HIGH}", loc="left")
    _bare(ax2, F, keep_x=True)

    # THE CAPTION FOLLOWS WHAT WAS DRAWN. The left panel is empty when the tool stored no draws,
    # and a caption describing points nobody can see is the figure lying about itself.
    left = ("LEFT: the posterior inclusion probability of every effect, computed on the first "
            "half of the chain against the second - a point off the diagonal is an effect the "
            "chain had not finished deciding, and a point RINGED IN VERMILLION is one whose CALL "
            "changed between the halves, which is the only kind of movement that changes the "
            "answer. The count of those is given per term in the corner, with the threshold each "
            "was counted against. Standard convergence statistics "
            "misread this model, because the spike-and-slab prior fixes many draws at exactly "
            "zero and the reference's effect is zero for the whole chain, so the check is made "
            "on the derived quantity the answer is actually read off."
            if have else
            "LEFT: EMPTY, and said so on the panel. This version of the tool did not store the "
            "posterior draws where this plugin reads them, so the chain could not be split and "
            "no convergence check was made on it at all.")
    ctx.emit_figure(
        "F3_sampling", fig,
        caption=("Whether the sampler settled. " + left + " RIGHT: the mean acceptance rate "
                 "against the band pertpy warns outside of - it warns through a logger, which in "
                 "a batch run nobody sees. The rate is printed as a number beside each point "
                 "because the judgement is whether it falls inside a band, which is not a thing "
                 "to read off a position against the edge of a shaded region; a rate outside the "
                 "band is ringed and named. A term whose rate the tool did not record has its "
                 "label and, in words, the reason. One hue per term, named on the "
                 "right-hand axis."),
        source=src)

def _fig_credibility(ctx, fits, order, ref, src_path):
    """How close each call was to the threshold that decided it."""
    import numpy as np
    import matplotlib.lines as ml
    contrasts = [(f, c) for f, c in _contrasts(fits)
                 if f["effects"] is not None
                 and "inclusion_probability" in f["effects"].columns]
    if not contrasts:
        return
    F, plt = ctx.figure, ctx.plot()
    n = len(contrasts)
    fig, axs = plt.subplots(1, n, squeeze=False, sharey=True, layout="constrained",
                            figsize=(F.SINGLE if n == 1 else F.DOUBLE,
                                     _height(ctx, max(2.2, 0.26 * len(order) + 1.4),
                                             len(order), "F4_credibility")))
    y = np.arange(len(order))
    ref_i = list(order).index(ref) if ref in list(order) else None
    for k, (f, cov) in enumerate(contrasts):
        ax = axs[0][k]
        d = f["effects"]
        d = d[d["covariate"] == cov].set_index("population").reindex(order)
        inc = d["inclusion_probability"].to_numpy(dtype=float)
        cred = _flags(np, d["credible"] if "credible" in d.columns else None, len(order))
        _reference_row(ax, order, ref)
        # The guide line matters more here than anywhere else: the reference's inclusion
        # probability is exactly zero, so its marker has no position to be at, and without a line
        # its row would be a label with nothing beside it - which reads as a population the run
        # forgot rather than one the model never tested.
        _rows(ax, F, len(order))
        # A STEM AND A POINT, NOT A FILLED BAR. Twelve full-height bars, most of them the INK that
        # means "measured and not called", put the panel's whole weight on the populations that
        # are not the result - and at print size two solid bars of similar length are harder to
        # tell apart than two points against a common line. The stem keeps the length, which is
        # what "how close to the threshold" is read off.
        for i in y:
            if ref_i is not None and i == ref_i:
                continue
            if np.isfinite(inc[i]):
                ax.hlines(i, 0, inc[i], colors=CREDIBLE if cred[i] else F.INK, lw=1.2, zorder=2)
        sel = np.array([np.isfinite(v) for v in inc])
        if ref_i is not None:
            sel[ref_i] = False
        hit = sel & cred
        miss = sel & ~cred
        ax.scatter(inc[hit], y[hit], s=20, color=CREDIBLE, zorder=4, edgecolors="white",
                   linewidths=0.5)
        # HOLLOW, NOT MERELY A DIFFERENT COLOUR. "called" against "measured and not called" is the
        # entire result of this plugin, and a distinction carried by hue alone is one that a
        # greyscale print and a colour-blind reader both lose.
        ax.scatter(inc[miss], y[miss], s=20, facecolors="none", edgecolors=F.INK, linewidths=0.8,
                   zorder=4)
        if ref_i is not None:
            # THE BLANK ROW, EXPLAINED WHERE IT IS BLANK. The reference has no inclusion
            # probability because its effect is fixed at zero and never sampled; a row with
            # nothing on it says "the run lost this population", which is a different sentence.
            ax.text(0.02, ref_i, "not tested: fixed at 0 by construction",
                    fontsize=5.5, va="center", ha="left", color=F.INK, style="italic", zorder=5)
        if np.isfinite(f["threshold"]):
            ax.axvline(f["threshold"], color=F.INK, ls="--", lw=0.6, zorder=3)
            # THE CUT, AS A NUMBER, ON THE PANEL. It is derived from the requested FDR and it
            # DIFFERS BETWEEN TERMS, so two panels side by side can carry two different decision
            # rules; a dashed line in each with the value only in the caption invites the reader
            # to compare them as though they were one.
            ax.text(f["threshold"], -0.88, f"cut {f['threshold']:.3f}", fontsize=5.5,
                    ha="center", va="center", color=F.INK)
        F.rasterize_points(ax)
        ax.set_xlim(0, 1)
        ax.set_xlabel("posterior inclusion probability")
        ax.set_title(str(cov), loc="left")
        _bare(ax, F, keep_x=True)
    _population_axis(axs[0][0], np, F, order, ref)
    # A ROW OF BLANK RESERVED AT THE TOP, INSIDE THE AXES. The cut is labelled with its value and
    # the label has to go somewhere that is neither on a stem nor on the panel title - at SINGLE
    # column width it landed on the title, which is where a two-panel figure puts the name of the
    # contrast, so the one number that decided every call was printed through the one word saying
    # what it decided.
    axs[0][0].set_ylim(len(order) - 0.5, -1.4)
    key = _call_key(F, ml, F.short_labels([str(p) for p in order])[str(ref)]
                    if ref in list(order) else str(ref))
    # ALONG THE BOTTOM, NOT DOWN THE RIGHT. This panel is as wide as its population names are
    # long, and a key in the right margin takes that width from the data; three entries in a row
    # under the axes cost height, of which a row-plot already has as much as it needs.
    fig.legend(key, [k.get_label() for k in key], loc="outside lower center", ncol=3,
               frameon=False, handletextpad=0.4, columnspacing=1.6, markerscale=1.6)
    thr = ", ".join(f"{f['term']} {f['threshold']:.3f}" for f in fits
                    if np.isfinite(f["threshold"]))
    ctx.emit_figure(
        "F4_credibility", fig,
        caption=(f"The share of posterior draws in which each effect was NOT switched off by the "
                 f"spike-and-slab prior, against the dashed threshold that turned it into a call "
                 f"({thr or 'threshold not recorded'}), which is marked and numbered on each "
                 f"panel because it can differ between terms. The threshold is derived from the "
                 f"requested FDR, not chosen: the tool walks the inclusion probabilities "
                 f"downwards and takes the first cut whose implied FDR is below the target - and "
                 f"when none is, it cuts at 1.0 and reports everything as not credible, which "
                 f"reads exactly like a real negative. A point just short of the line is an "
                 f"effect a slightly larger FDR would call; scCODA's own tutorial recommends "
                 f"raising it as far as 0.2 when nothing is found. Filled is called, hollow is "
                 f"measured and not called, and the reference row carries neither because its "
                 f"effect is fixed at zero by construction rather than measured at all."),
        source=src_path)

def _fig_effects(ctx, fits, order, ref, src_path):
    """The answer: the model's own effect, and the compositional fold change beside it."""
    import numpy as np
    import matplotlib.lines as ml
    contrasts = [(f, c) for f, c in _contrasts(fits) if f["effects"] is not None]
    if not contrasts:
        return
    F, plt = ctx.figure, ctx.plot()
    n = len(contrasts)
    per = max(1.6, 0.24 * len(order) + 1.0)
    tall = _height(ctx, per * n, len(order) * n, f"F5_effects, {n} contrast(s)")
    # SHARED X WITHIN EACH COLUMN, WHICH IS THE WHOLE POINT OF DRAWING THEM IN A GRID. Left to
    # themselves the rows autoscaled independently: one contrast's axis ran to 2.0 and the next
    # to 1.0, so an effect drawn HALF AS FAR from zero was the LARGER of the two, and the figure
    # invited exactly the comparison it made wrong. Shared y as well, so the row order is one row
    # order and a reader can read straight across.
    fig, axs = plt.subplots(n, 2, figsize=(F.DOUBLE, tall), squeeze=False,
                            sharex="col", sharey=True, layout="constrained")
    y = np.arange(len(order))
    short = F.short_labels([str(p) for p in order])
    sref = short[str(ref)] if ref in list(order) else str(ref)
    seen_eff, seen_lfc = [], []
    for r, (f, cov) in enumerate(contrasts):
        d = f["effects"]
        d = d[d["covariate"] == cov].set_index("population").reindex(order)
        cred = _flags(np, d["credible"] if "credible" in d.columns else None, len(order))
        isref = np.array([p == ref for p in order], dtype=bool)

        ax = axs[r][0]
        _reference_row(ax, order, ref)
        _reference_row(axs[r][1], order, ref)
        eff = d["effect"].to_numpy(dtype=float) if "effect" in d.columns else np.full(len(order),
                                                                                     np.nan)
        if "hdi_low" in d.columns:
            # AS A SEGMENT, NOT AS AN ERROR BAR. `errorbar` demands non-negative xerr, and the
            # interval here is the HDI of the SELECTED draws while the point is the mean of the
            # non-zero ones or an exact zero - so the point can sit outside its own interval and
            # matplotlib would raise at draw time. hlines has no such constraint and shows the
            # same two numbers.
            ax.hlines(y, d["hdi_low"].to_numpy(dtype=float), d["hdi_high"].to_numpy(dtype=float),
                      colors=[F.GREY if p else (CREDIBLE if c else F.INK)
                              for p, c in zip(isref, cred)], lw=1.1, zorder=2)
        # FILLED, HOLLOW, GREY - the same three marks as the credibility panel and in the same
        # meanings. A hollow point is one the model measured and did NOT call, and its position at
        # exactly zero is the tool's doing rather than an estimate: `Final Parameter` is set to
        # zero for every effect the spike-and-slab switched off, which is why a hollow point can
        # sit outside its own credible interval. Filled and hollow differ in SHAPE, so the
        # distinction survives a greyscale print.
        ax.scatter(eff[cred & ~isref], y[cred & ~isref], s=18, color=CREDIBLE, zorder=4,
                   edgecolors="white", linewidths=0.5)
        ax.scatter(eff[~cred & ~isref], y[~cred & ~isref], s=18, facecolors="none",
                   edgecolors=F.INK, linewidths=0.8, zorder=4)
        ax.scatter(eff[isref], y[isref], s=20, marker="s", facecolors=F.GREY, edgecolors=F.INK,
                   linewidths=0.4, zorder=4)
        seen_eff.append(eff)
        if "hdi_low" in d.columns:
            seen_eff.append(d["hdi_low"].to_numpy(dtype=float))
            seen_eff.append(d["hdi_high"].to_numpy(dtype=float))
        F.rasterize_points(ax)
        ax.axvline(0, color=F.INK, lw=0.6, zorder=3)
        ax.set_title(str(cov), loc="left")
        _bare(ax, F, keep_x=True)

        ax2 = axs[r][1]
        lfc = (d["log2_fold_change"].to_numpy(dtype=float) if "log2_fold_change" in d.columns
               else np.full(len(order), np.nan))
        # THE SAME THREE MEANINGS AS THE LEFT PANEL, because it is the same row. The fold change
        # was drawn credible-or-grey while the effect beside it was drawn credible-or-black, so a
        # population that was measured and not called was black on one side of the figure and
        # grey on the other - and grey is the tool's mark for a value that was never measured.
        # The reference keeps an INK edge: its fold change is the one number on this panel a
        # reader is most likely to be surprised by, and at 15% ink on white it was invisible.
        ax2.barh(y, lfc, height=0.68, zorder=2,
                 color=[F.GREY if p else (FOLD if c else "none")
                        for p, c in zip(isref, cred)],
                 edgecolor=[F.INK if (p or not c) else "none"
                            for p, c in zip(isref, cred)], linewidth=0.6)
        seen_lfc.append(lfc)
        ax2.axvline(0, color=F.INK, lw=0.6, zorder=3)
        ax2.set_title("compositional fold change", loc="left")
        _bare(ax2, F, keep_x=True)
        _population_axis(ax, np, F, order, ref)
        if r == n - 1:
            # THE AXIS LABELS ONLY UNDER THE BOTTOM ROW, because the columns share their scale
            # and matplotlib prints the tick labels there only. A label repeated under a row whose
            # ticks are hidden names an axis the reader cannot see.
            ax.set_xlabel(f"effect on log-abundance, relative to {sref}")
            ax2.set_xlabel("log2 fold change in expected share")
    axs[0][0].set_ylim(len(order) - 0.5, -0.5)
    _flat_column([axs[r][0] for r in range(n)], np, F, np.concatenate(seen_eff) if seen_eff else [],
                 "every effect is exactly zero:\nnothing was called at this threshold")
    _flat_column([axs[r][1] for r in range(n)], np, F, np.concatenate(seen_lfc) if seen_lfc else [],
                 "every fold change is exactly zero:\nno effect was switched on")
    key = _call_key(F, ml, sref)
    fig.legend(key, [k.get_label() for k in key], loc="outside lower center", ncol=3,
               frameon=False, handletextpad=0.4, columnspacing=1.6, markerscale=1.6)
    ctx.emit_figure(
        "F5_effects", fig,
        caption=(f"The result, twice, because the two halves can disagree and the disagreement is "
                 f"the method. LEFT: the model's own effect parameter with its credible interval, "
                 f"measured RELATIVE TO {ref} and FILLED where the effect was called credible. A "
                 f"HOLLOW point was measured and not called, and it sits at exactly zero because "
                 f"the tool sets it there rather than because the posterior mean was zero - which "
                 f"is why a hollow point can lie outside its own interval - the interval is "
                 f"over the draws in which the effect was switched ON, so for a population that "
                 f"was not called it describes the minority of draws in which it was. RIGHT: the "
                 f"same effect "
                 f"as a fold change in expected share - which is COMPOSITIONAL, renormalised to a "
                 f"constant total, so a population with an effect of exactly zero can still carry "
                 f"a fold change driven entirely by other populations moving. The reference is "
                 f"the clearest case: its effect is fixed at zero by construction and its fold "
                 f"change is not, and it is drawn grey with an outline for that reason. Each "
                 f"column shares one x scale across every contrast, so a bar twice as long is "
                 f"twice the change. A population with no credible effect has not been shown to "
                 f"hold still."),
        source=src_path)

# ---------------------------------------------------------------------------------------- run

def run(ctx):
    import numpy as np
    import pandas as pd
    import pertpy as pt
    import anndata as ad

    C = ctx.config
    # THE JOURNAL CONVENTIONS, APPLIED BEFORE ANYTHING IS FITTED - and the cheapest possible check
    # that this environment can draw at all. The alternative is discovering a missing matplotlib
    # after every chain in the run has been sampled.
    ctx.plot()

    design = ctx.design_table()
    terms = list((ctx.params.get("contrast") or {}).get("terms")
                 or ctx.testable_factors(min_replicates=C["min_samples_per_level"]))
    if not terms:
        return ctx.refuse("compositional test",
                          f"no factor has two levels with at least "
                          f"{C['min_samples_per_level']} samples in each. With fewer, "
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

    # THE POPULATIONS ARE NAMED BEFORE THE DESIGN COLUMNS ARE ADDED. They are added to the same
    # frame, and a population whose name equals a factor's would have its counts overwritten by
    # that factor's levels - silently, and the fit would run on the survivors.
    pops = [str(c) for c in tab.columns]
    clash = sorted(set(map(str, terms)) & set(pops))
    if clash:
        return ctx.refuse(
            "compositional test",
            f"population(s) {', '.join(clash)} have the same name as a design factor. The counts "
            f"and the design share one table here, so one would overwrite the other. Rename "
            f"either, or name the factors to test with --params '{{\"contrast\": {{\"terms\": "
            f"[...]}}}}'.")
    for t in terms:
        tab[t] = [str(design.get(s, {}).get(t, "")) for s in tab.index]
    ctx.emit_table("abundance_counts", tab)

    share = tab[pops].div(tab[pops].sum(axis=1), axis=0)
    order = [str(p) for p in share.mean(axis=0).sort_values(ascending=False).index]
    refframe = _reference_frame(tab, pops, share, np, pd, C["reference_absence_threshold"])
    ref, why = _pick_reference(ctx, refframe, pops, C["reference_absence_threshold"])
    if ref is None:
        return ctx.refuse("compositional test", why)
    ctx.log(f"{len(pops)} population(s), {len(tab.index)} sample(s), {len(terms)} term(s)")
    ctx.log(f"reference population: {ref} ({why})")
    n_absent = float(refframe.loc[ref, "fraction_of_samples_absent"])
    if n_absent > 0:
        ctx.caveat(f"The reference population {ref!r} is absent from "
                   f"{100 * n_absent:.0f}% of samples. scCODA replaces a zero count with a "
                   f"pseudocount of 0.5, so in those samples every effect is measured against "
                   f"half a cell.")

    # ------------------------------------------------------------------------------ the fits
    fits = []
    sccoda = pt.tl.Sccoda()
    for term in terms:
        adata = ad.AnnData(tab[pops].to_numpy().astype(float),
                           obs=pd.DataFrame({term: tab[term].to_numpy()},
                                            index=tab.index.astype(str)),
                           var=pd.DataFrame(index=pd.Index(pops, name="population")))
        mdata = (sccoda.load(adata, type="sample_level", covariate_obs=[term])
                 if hasattr(sccoda, "load") else adata)
        model = sccoda.prepare(mdata, formula=term, reference_cell_type=ref)
        sccoda.run_nuts(model, num_samples=int(C["num_samples"]),
                        num_warmup=int(C["num_warmup"]), rng_key=int(C["seed"]))
        # THE FDR IS SET BEFORE ANYTHING IS READ BACK. `credible_effects(est_fdr=x)` recomputes
        # the decision at x and does not store it, so the stored effect table and the threshold in
        # uns would stay at the library's 0.05 while the booleans came back at x. `set_fdr`
        # recomputes and stores, and then every number on the page is at one FDR.
        if hasattr(sccoda, "set_fdr"):
            sccoda.set_fdr(model, est_fdr=float(C["fdr"]))
            cred = sccoda.credible_effects(model)
        else:
            cred = sccoda.credible_effects(model, est_fdr=float(C["fdr"]))
        fit = _read_fit(ctx, sccoda, model, term, ref, cred, np, pd)
        fits.append(fit)
        n_this = int(np.asarray(cred).astype(bool).sum())
        ctx.log(f"  {term}: {n_this} credible effect(s), threshold {fit['threshold']:.3f}, "
                f"acceptance {fit['accept']:.3f}")

    # ------------------------------------------------------------------------- what came back
    parts = [f["effects"] for f in fits if f["effects"] is not None]
    if parts:
        res = pd.concat(parts, ignore_index=True).set_index("population")
    else:
        # A TABLE WITH A HEADER AND NO ROWS SAYS "the tool returned no effect table"; an ABSENT
        # table says this plugin declares an output it did not write, on every ordinary run.
        res = pd.DataFrame(columns=["term", "covariate", "credible"],
                           index=pd.Index([], name="population"))
        # PARTIAL, AND THE HEADLINE SAYS SO BELOW. Left at `ok` this run reported "0 credible
        # compositional effect(s)" over a full population list, from a chain that sampled
        # perfectly well and an effect table nobody could open - which is a NEGATIVE RESULT that
        # was never measured. It is the same reading `cannot_show` warns about for the FDR
        # threshold cutting at 1.0, arriving by a different route, and a caveat under a confident
        # headline does not undo a confident headline.
        ctx.status = "partial"
        ctx.caveat("The fitted effect table could not be read back from the tool, so this result "
                   "carries no effect sizes, no credible intervals and no inclusion "
                   "probabilities - only what ran. NO POPULATION WAS TESTED EITHER WAY: this is "
                   "not a result of no change, and the empty table is not a list of populations "
                   "that held still. The result panel and the credibility panel are both absent "
                   "for the same reason.")
    res_path = ctx.emit_table("abundance_by_population", res)

    # ------------------------------------------------------------------------------- figures
    ctx.log("figures:")
    _fig_shares(ctx, tab, pops, terms, share, order, ref)
    _fig_reference(ctx, refframe, tab, terms, share, ref, why)
    _fig_sampling(ctx, fits)
    _fig_credibility(ctx, fits, order, ref, res_path)
    _fig_effects(ctx, fits, order, ref, res_path)

    # -------------------------------------------------------------------- caveats, from the data
    n_cred = int(_flags(np, res["credible"] if "credible" in res.columns else None,
                        len(res)).sum())
    # `int(v)`, NOT the numpy scalar. Under numpy 2 `repr(np.int64(5))` is "np.int64(5)", so
    # `dict(value_counts())` interpolated into a caveat reads
    # "{'aged': np.int64(5), 'young': np.int64(5)}" - a sentence about the study design with the
    # host language's type names in it, printed to the person deciding whether to believe the
    # result. Measured on numpy 2.0.2.
    sizes = {t: {str(k): int(v) for k, v in tab[t].value_counts().items()} for t in terms}
    # A RATE THAT WAS NEVER RECORDED IS NOT A RATE OUTSIDE THE BAND. `nan` fails every comparison,
    # so without the finiteness test an older tool that does not store the acceptance rate would
    # flip every run to `partial` and quote "nan" at the reader as though the sampler had
    # misbehaved. The two cases are opposite statements and are reported separately.
    silent = [f for f in fits if not np.isfinite(f["accept"])]
    bad = [f for f in fits if np.isfinite(f["accept"])
           and not (ACCEPT_LOW <= f["accept"] <= ACCEPT_HIGH)]
    if silent:
        ctx.caveat("The sampler's acceptance rate was not recorded by this version of the tool "
                   "for " + ", ".join(f["term"] for f in silent)
                   + ", so the one check pertpy itself makes on the chain could not be made here.")
    if bad:
        ctx.status = "partial"
        ctx.caveat(
            "The sampler's mean acceptance rate is outside the band pertpy itself warns on "
            f"({ACCEPT_LOW}-{ACCEPT_HIGH}) for: "
            + ", ".join(f"{f['term']} at {f['accept']:.3f}" for f in bad)
            + ". The tool's own words are 'Results might be incorrect!'. It says so through a "
              "logger and returns a complete result anyway. Re-run with a different seed "
              "(--params '{\"seed\": 1}') before reading the effects for those terms.")
    moved = [f for f in fits if f["mismatch"]]
    if moved:
        ctx.caveat(
            "The tool's credible-effect booleans disagree with its own effect table for "
            + ", ".join(f"{f['term']} ({f['mismatch']} of {len(f['effects'])})" for f in moved)
            + ". That happens when the two are computed at different FDR levels, which means "
              "`set_fdr` did not take effect in this version of the tool. Read the booleans as "
              f"the answer at fdr={C['fdr']} and the effect columns as possibly at the library "
              f"default.")
    unresolved = [f for f in fits if f["halves"] is None]
    if unresolved:
        ctx.caveat("The posterior draws were not readable for "
                   + ", ".join(f["term"] for f in unresolved)
                   + ", so the chain could not be split and no convergence check was made on "
                     "those terms.")
    ctx.caveat(f"Every effect is RELATIVE TO {ref!r} ({why}). A different reference gives a "
               f"different set of moved populations from the same data, and neither is more "
               f"correct - that is what compositional means. The only real check of it is the "
               f"authors' own reference sweep, one fit per population per term, which this "
               f"plugin does not run; F2_reference shows what can be checked without refitting.")
    ctx.caveat(f"Sample counts per level: {sizes}. The model is fitted on "
               f"{len(tab.index)} rows - one per sample, not one per cell - and with few samples "
               f"per arm the posterior leans on the prior.")
    ctx.caveat(f"Chain: {C['num_samples']:,} draws after {C['num_warmup']:,} warmup, seed "
               f"{C['seed']}, at fdr {C['fdr']}. The inclusion probability every call is made on "
               f"is a share OF those draws, so the chain length is part of the answer.")
    # A COUNT OF ZERO AND A COUNT THAT WAS NEVER MADE ARE DIFFERENT SENTENCES. `n_cred` is 0 in
    # both cases and only one of them is a finding, so the headline branches on whether an effect
    # table came back rather than on the number it produced.
    ctx.headline = (
        (f"{n_cred} credible compositional effect(s) at fdr {C['fdr']} over "
         f"{len(pops)} population(s), relative to {ref}")
        if parts else
        (f"{len(terms)} term(s) sampled over {len(pops)} population(s) relative to {ref}; the "
         f"tool returned NO effect table, so nothing was called either way"))


# ----------------------------------------------------------------------------------- selftest

def selftest(ctx):
    """Prove the call works, that a planted shift is recovered, AND that the page can be drawn.

    A test asserting only that a table came back would pass on a model that had learned nothing.
    The fixture moves one population's share hard between arms and requires scCODA to call it.

    IT ALSO ASSERTS THE KEYS THE FIGURES READ. Four of the five panels are drawn from places the
    tool's public API does not return - the inclusion-probability threshold, the acceptance rate
    and the posterior draws all live in `uns["scCODA_params"]` - and a rename there costs a panel
    that is declared optional, which means the page would say "not produced" and the run would
    look ordinary. An import test cannot see that; this can.
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
    if hasattr(sccoda, "set_fdr"):
        sccoda.set_fdr(model, est_fdr=0.05)
    res = sccoda.credible_effects(model)
    arr = np.asarray(res)
    assert arr.size >= len(pops), f"credible_effects returned {arr.shape}, expected one per population"
    ctx.log(f"  scCODA ran; {int(arr.sum())} credible effect(s) on a fixture with one planted")
    assert int(arr.sum()) >= 1, (
        "scCODA found NO credible effect on a fixture where one population's share was tripled "
        "between arms. The model ran and learned nothing - on real data it would return a full "
        "table of no-change, which is indistinguishable from a real negative.")

    # ---- everything the panels read, by name --------------------------------------------
    A = _coda(model)
    par = dict(A.uns.get("scCODA_params") or {})
    mcmc = dict(par.get("mcmc") or {})
    eff = sccoda.get_effect_df(model)
    beta = np.asarray((mcmc.get("samples") or {}).get("beta"))
    checks = [
        ("effect table has the effect", "Final Parameter" in eff.columns),
        ("effect table has the inclusion probability", "Inclusion probability" in eff.columns),
        ("effect table has the fold change", "log2-fold change" in eff.columns),
        ("effect table has a credible interval",
         len([c for c in map(str, eff.columns) if c.startswith(("HDI", "ETI"))]) >= 2),
        ("effect table is one row per covariate and population", len(eff) >= len(pops)),
        ("the inclusion threshold is recorded", "threshold_prob" in par),
        ("the acceptance rate is recorded", "acceptance_rate" in mcmc),
        ("the reference is recorded as given", par.get("reference_cell_type") == "pop3"),
        # The shape the convergence panel splits: draws x covariates x populations.
        ("posterior draws for beta are (draws, covariates, populations)",
         beta.ndim == 3 and beta.shape[2] == len(pops)),
    ]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        ctx.log(f"  {'ok  ' if ok else 'FAIL'} {n}")
    assert not bad, ("the tool no longer reports what this plugin's panels are drawn from: "
                     + ", ".join(bad))

    # A nullable dtype in the effect table is the reason `_num` exists; assert it survives the
    # conversion rather than trusting that this pandas returns float64.
    v = _num(pd, np, eff["Final Parameter"])
    assert v.dtype == np.dtype("float64") and len(v) == len(eff), \
        f"the effect column did not convert to plain floats: {v.dtype}"

    # THE FIGURE PATH IS PART OF THIS PLUGIN AND PART OF THE ENVIRONMENT, and it is newly part of
    # this one: matplotlib is declared here for the first time in this version. The fit does not
    # exercise it, and a plugin whose five panels fail on a missing backend fails after the
    # sampling is spent.
    plt = ctx.plot()
    fig, ax = plt.subplots(figsize=(ctx.figure.SINGLE, 1.4))
    ax.barh([0, 1], [0.4, 0.9], color=[CREDIBLE, ctx.figure.GREY])
    ax.set_xscale("symlog", linthresh=0.01)
    plt.close(fig)
    ctx.log("  ok   the figure path imports and draws")
