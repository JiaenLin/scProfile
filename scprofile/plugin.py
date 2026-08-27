"""The plugin API. A plugin is ONE FILE, and dropping it in is the whole installation.

WHERE THE EFFORT GOES, AND WHY IT IS ASYMMETRIC

A plugin is written ONCE. The builder and the planner run again for every new user, every new
machine, every new project. So a plugin should carry everything it will ever need - its
environment, its references, its limits, its upstream record and ITS OWN PROOF - and the builder
and planner should be light, adaptive and fast on repeat.

That is why `selftest` lives in the plugin file rather than beside it: a plugin that cannot prove
itself on a new machine is a plugin that will be debugged on that machine, one user at a time.

WHAT A PLUGIN IS

    kernels/myplugin.py

        PLUGIN = {
            "summary": "what it is for",
            "needs":   {"layers": ["{lognorm}"], "obs": ["{label}"]},
            "produces": ["obs[my_score]"],
            "cannot_show": ["what a reader must not conclude"],
            # WHAT IT NEEDS, NOT WHAT TO BUILD. The builder resolves every plugin's
            # requirement together and builds as few environments as satisfy them all; a plugin
            # cannot know what else is installed, so it must not decide its own environment.
            # Omit `requires` and the plugin runs in the host's interpreter.
            "requires": {"python": ">=3.10,<3.13", "packages": {"mytool": ">=1.2,<1.3"}},
        }

        def run(ctx):
            import mytool
            score = mytool.compute(ctx.X, groups=ctx.obs(ctx.keys["label"]))
            ctx.emit_obs("my_score", score)
            ctx.headline = f"{len(score):,} cells scored"

        def guard(g):                       # OPTIONAL, and see the Guard class below
            if not g.assay:
                g.deny("this result means different things on nuclei and on whole cells")

That is the entire plugin. No manifest to keep in step with a wrapper, no `run.py` to write, no
skeleton to finish, no boilerplate to copy from the plugin next door.

A SHAPE THAT CANNOT EXPRESS SOMETHING SILENTLY DELETES IT. This shape had no guard for its first
seven plugins, and nothing said so - so converting a guarded plugin to the shape the host prefers
removed its check with no error and no line in the log, and the first dataset that guard existed
to refuse would have been analysed and reported. The same reasoning is why `produces` can mark an
output `"obs[latent_time]?"` when only one mode makes it: a declaration with no way to be right is
a declaration that gets ignored.

KEEP THIRD-PARTY IMPORTS INSIDE FUNCTIONS, as the sketch above does. Module scope is executed by
the HOST's interpreter for anything that must happen before the plugin's environment is resolved -
`guard(g)` is that case - and the host has none of the plugin's pins.

WHY THIS REPLACED SIX FILES

The previous shape asked an author for `kernel.yml`, `run.py`, `lock.yml`, `references.yml`,
`selftest.py` and `UPSTREAM.md` - and `run.py` began life as a generated skeleton whose body was
`raise SystemExit("implement the method call")`. Six files that must agree with each other, one of
them handed over half-written, is an assembly kit. Every one of those files is now either derived
from `PLUGIN` or optional.

THE CONTRACT IS THE HOST'S, NOT THE PLUGIN'S

`ctx` arrives already correct: keys resolved so no column name is ever written down, the object
already subset to this plugin's unit, annotator sentinels kept as cells and counted, cells with
NaN in a computed embedding excluded and reported, the ALLOCATED core share rather than the
machine's. Every wrapper bug this project has had lived in that code, and it is now written once,
here, and shared by every plugin including ones written by someone else.

WHAT A PLUGIN MAY NEVER DO

Name a column, a layer, an organism or a sample. Those arrive through `ctx.keys` and
`ctx.organism`. A plugin that writes `adata.obs["cell_type"]` works on one project; the whole key
mechanism exists so that no plugin ever does.
"""
from __future__ import annotations

from pathlib import Path


class Populations(tuple):
    """What `ctx.populations()` returns: `(mask, groups)`, and the two things people wanted.

    FOUR PLUGINS HAVE NOW GOT THIS WRONG, and two of them the same way - `pops, dropped =
    ctx.populations()` - which is not four mistakes, it is one bad affordance. A function called
    `populations` that returns a boolean mask and a per-cell label array is answering a different
    question from the one its name asks, and the wrong reading is silent: `len(pops)` becomes the
    cell count, `if dropped:` asks the truth value of an array, and one of those raises and the
    other reports 100,713 populations.

    So it still IS `(mask, groups)` - every correct caller is untouched, because this is a tuple -
    and it now also answers what the wrong callers were asking for:

        p = ctx.populations()
        p.mask       boolean over every cell of the object: is this a REAL call?
        p.groups     the labels of those cells, as strings, aligned to p.mask
        p.names      the distinct populations, sorted. What `len(pops)` was reaching for.
        p.dropped    the sentinel labels actually present, sorted. What `dropped` was reaching for.

    `groups` is None when the object carries no label column, and `mask` is then all-True, so a
    plugin can call this unconditionally and branch on `p.groups is None`.
    """

    def __new__(cls, mask, groups, names=(), dropped=()):
        return super().__new__(cls, (mask, groups))

    def __init__(self, mask, groups, names=(), dropped=()):
        super().__init__()
        self.names = list(names)
        self.dropped = list(dropped)

    @property
    def mask(self):
        return self[0]

    @property
    def groups(self):
        return self[1]


class Guard:
    """What a plugin's GUARD is given, and the only two things it may do with it.

    A guard answers one question, before anything is spent: is this dataset one where this
    plugin's output would MEAN what its report says it means? It is NOT a prerequisite check -
    those are structural, the host does them in `unmet()`, and no willingness makes a missing
    layer runnable. A guard is about interpretability: the run would succeed, produce numbers,
    and those numbers would not support the sentence a reader will write under them.

        def guard(g):
            if not g.assay:
                g.deny("velocity says different things about nuclei and whole cells ...")

    Modelled on the agent harness's PreToolUse hook, including the part that matters most: the
    escape is `--allow <plugin>` and every use of it is appended to `guard_overrides.jsonl` with
    its reason. A gate with no escape gets switched off; a gate whose escapes are all recorded
    does not.

    IT RUNS IN THE HOST'S INTERPRETER, before the plugin's environment is resolved - which is the
    whole point, since one thing a guard can say is that building the environment is not worth it.
    So a plugin that ships a guard must be IMPORTABLE BY THE HOST: keep every third-party import
    inside a function, as every plugin here already does.
    """

    def __init__(self, describe=None, constraint="", params=None):
        #: What the host knows about the object: n_obs, n_vars, keys, layers, obsm, organism,
        #: assay and how each was decided. See `inputs.describe`.
        self.describe = dict(describe or {})
        #: The upstream tool's own constraint on use, verbatim, or "" when the object carries
        #: none - and an ABSENT constraint is a finding, not a pass.
        self.constraint = str(constraint or "")
        self.params = dict(params or {})
        self.notes, self.denials = [], []

    @property
    def assay(self):
        return (self.describe.get("assay") or "").lower() or None

    @property
    def organism(self):
        return (self.describe.get("organism") or "").lower() or None

    @property
    def keys(self):
        return dict(self.describe.get("keys") or {})

    def deny(self, reason):
        """Refuse this dataset, and say what would make it runnable. Printed to the user."""
        self.denials.append(str(reason))

    def note(self, text):
        """Allow, with something the reader of the result has to be told."""
        self.notes.append(str(text))


class Context:
    """Everything a plugin is given, already correct. Built by the host, never by a plugin.

    The plugin receives this and returns nothing: it calls `emit_*` for what it produced and sets
    `headline`. What reaches the merged object is exactly what it emitted.
    """

    def __init__(self, adata, *, keys, out, cores=1, unit=None, organism=None, assay=None,
                 references=None, reference_specs=None, params=None, design=None,
                 sentinels=(), provenance=None, constraint="",
                 config=None, log=print):
        self.adata = adata
        #: {role: actual name in THIS object}. `ctx.keys["label"]`, never a literal column.
        self.keys = dict(keys or {})
        self.out = Path(out)
        #: THE ALLOCATED SHARE. `os.cpu_count()` in a plugin starts the node's worth of threads
        #: per plugin, and four concurrent plugins then start four times the node.
        self.cores = int(cores or 1)
        self.unit = unit
        #: The upstream tool's constraint on use, verbatim, or "" when the object carries none.
        #: `Guard` has had this since it existed and `Context` did not, so a plugin that wanted to
        #: REPRODUCE the constraint in its own caveats - rather than merely be refused by it - had
        #: nothing to read. An absent constraint is "", never None: a plugin testing it should not
        #: have to distinguish "no constraint" from "the host forgot to pass one".
        self.constraint = str(constraint or "")
        self.organism = (organism or "").lower() or None
        self.assay = (assay or "").lower() or None
        self.references = dict(references or {})
        #: The declarations behind those paths, so a plugin can ask by role rather than by name.
        self._reference_specs = dict(reference_specs or {})
        self.params = dict(params or {})
        self.design = design
        self.sentinels = tuple(sentinels or ())
        #: What the upstream tools recorded about where this object came from - directory leads
        #: and sample names, harvested by the host from `uns` and handed over as plain JSON.
        #: Read through `source_layers()`; a plugin should not have to parse it.
        self.provenance = dict(provenance or {})
        self.log = log

        #: Typed, defaulted and RANGE-CHECKED before run() was called. A plugin reads
        #: `ctx.config["min_cells"]` and never validates it: a bad --params fails in the second
        #: the plan is drawn, not an hour into a queue.
        self.config = dict(config or {})
        self._effects = []
        self._design_cache, self._design_factors = None, []
        self.headline = ""
        self.status = "ok"
        self._obs, self._obsm, self._layers = {}, {}, {}
        self._tables, self._figures, self._objects = [], [], {}
        self.caveats, self.absent = [], []
        #: ONE NUMBER PER INSTANCE, so a per-unit plugin's units can be put on one axis.
        #: A per-unit plugin delivers N single-sample reports; without a scalar the host can
        #: compare, the page is those N reports stapled together and the cohort statement is
        #: left to the reader's arithmetic. Measured on a ten-animal cohort: one plugin's
        #: interaction count ran 8,194 to 38,895 across the ten, and nothing on its page put
        #: the ten numbers on the same axis.
        self._metrics = {}
        #: Claims this plugin's own diagnostics refute. See `contradiction`.
        self._contradictions = []
        #: So `populations()` says what it set aside ONCE however many tables a plugin writes.
        self._said_populations = False
        #: Every directory `source_layers()` walked, so a refusal can name where it looked -
        #: and whether the walk FINISHED, because a search that gave up and a project that has
        #: nothing return the same empty list, and only one of them is a fact about the data.
        self.searched = []
        self.search_exhausted = False
        for d in ("tables", "figures", "obs", "arrays"):
            (self.out / d).mkdir(parents=True, exist_ok=True)

    # ---- reading -------------------------------------------------------------------------
    @property
    def X(self):
        """The matrix this plugin should work on: its declared lognorm layer, or X."""
        lay = self.keys.get("lognorm")
        if lay and lay in self.adata.layers:
            return self.adata.layers[lay]
        return self.adata.X

    def counts(self):
        """The counts layer, or None. A count model handed non-integers returns a plausible lie."""
        lay = self.keys.get("counts")
        return self.adata.layers[lay] if lay and lay in self.adata.layers else None

    def layers(self):
        """The layer names this object actually HAS. NOT `list(adata.layers)`, and here is why.

        On current anndata a bare object with no layers iterates as `[None]`, and `layers[None]`
        is X under another name. So `sorted(adata.layers)` raises the moment a real layer exists,
        and a plugin deciding what it was given is told about a layer that is not one. The guard
        was written EIGHT times across five files in this project before anybody named it, which
        is how the ninth copy comes to be the one that forgets - so it is answered here, once, for
        every plugin.
        """
        from . import manifest
        return manifest.layer_names(self.adata)

    def obs(self, role_or_name):
        """A column BY ROLE. `ctx.obs("label")` resolves through the key map; a literal name is
        accepted too, so a plugin can read something only it knows about."""
        name = self.keys.get(role_or_name, role_or_name)
        return self.adata.obs[name] if name in self.adata.obs else None

    def embedding(self):
        """The REPRESENTATION to compute on: a neighbour graph, a transition matrix, a kNN.

        Usually 30-50 columns wide. Its axes are not interpretable and it is NOT what to draw on
        - for that call `layout()`, and see the note there for why the difference matters.
        """
        emb = self.keys.get("embedding")
        return self.adata.obsm[emb] if emb and emb in self.adata.obsm else None

    def layout(self):
        """The TWO columns to draw on, or None when the object carries no layout.

        A REPRESENTATION IS NOT A LAYOUT. `embedding()` returns a space where distances mean
        something and the axes do not; this returns two coordinates produced to be looked at. For
        a variational latent the difference is total: its dimensions carry no variance ordering,
        so its first two are two arbitrary coordinates of a roughly isotropic ball and draw as
        one - which is what four panels of a shipped plugin looked like before this existed, on
        an object that carried the UMAP of that same latent all along.

        None means the object has none. Refuse and name what to compute; do not fall back to the
        first two columns of something wider, because that picture cannot announce itself as
        wrong.
        """
        lay = self.keys.get("layout")
        if not lay or lay not in self.adata.obsm:
            return None
        m = self.adata.obsm[lay]
        return m if getattr(m, "ndim", 0) == 2 and m.shape[1] == 2 else None

    def layout_key(self):
        """The NAME of the layout, for a plugin that hands a basis to a tool rather than an array.

        Returned without the `X_` prefix as well as with it, because scanpy and scvelo take
        `basis='umap'` while obsm holds `X_umap`, and every plugin that has needed this has
        written the same two lines of stripping.
        """
        lay = self.keys.get("layout")
        if not lay or lay not in self.adata.obsm:
            return None, None
        return lay, (lay[2:] if lay.startswith("X_") else lay)

    def real_cells(self):
        """A boolean mask: cells whose label is a REAL call, not an annotator's refusal to make one.

        A sentinel - `UNRESOLVED`, `EXCLUDED`, whatever this annotator writes - is a cell the
        annotator declined to type. The rule is that it stays in the object and leaves the
        STATISTICS: never a population, never a denominator, never dropped.

        The host cannot apply that rule for you, because only this plugin knows what it groups
        by; what the host can do is answer the question once, the same way, for every plugin.
        Anything that reports per-label results should mask with this and say how many it set
        aside - a sentinel in a results table reads as a cell type that scored badly, and the
        first plugin supplied from outside this repository put `UNRESOLVED` in its output as the
        least-separated population in the dataset.

        All-True when the object carries no label column or no sentinels are declared, so a
        plugin can call it unconditionally.
        """
        from . import inputs
        lab = self.obs("label")
        if lab is None:
            import numpy as np
            return np.ones(self.adata.n_obs, dtype=bool)
        return inputs.sentinel_mask(lab, self.sentinels)[0]

    def estimable(self, obs, terms):
        """Can this design estimate all of `terms` at once, on these cells?

        THE HOST ANSWERS QUESTIONS ABOUT THE DESIGN; the plugin decides what to do with the
        answer. A model term that the data cannot carry does not fail politely - it raises from
        inside the fitting library, after the fit has been paid for, and takes the whole plugin
        down rather than the one population it was inestimable in.

        Terms are factor names, or interactions written `"a:b"`. A plugin that fits per
        population must ask PER POPULATION: the cohort can be complete while a subset of it is
        not, which is exactly the case that has already cost a run.
        """
        from . import inputs
        return inputs.estimable(obs, terms)

    def drop_inestimable(self, obs, terms):
        """(kept, dropped) in the order given - and DROPPED IS FOR THE REPORT, not the log.

        A term silently missing from a model is a question silently not asked, and "no effect"
        and "never tested" are the same empty row on a figure. Name them.
        """
        from . import inputs
        return inputs.drop_inestimable(obs, terms)

    def populations(self, role="label"):
        """The grouping a per-population result must use, and the caveat that goes with it.

        TWO OF THE FIRST TWO PLUGINS THAT GROUPED BY LABEL GOT THIS WRONG, which is a statement
        about the affordance and not about the two authors. `ctx.obs("label")` hands back the raw
        column; using it correctly means remembering, unprompted, that some of its values are the
        annotator DECLINING to call a cell type - and a mean activity or a silhouette computed
        for `UNRESOLVED` reads in a results table exactly like a cell type that scored badly.

        Returns a `Populations`: it unpacks as `(mask, groups)` - the boolean mask of real
        cells and their labels as strings - and it also carries `.names` and `.dropped`, which is
        what four plugins reached for by destructuring it wrongly. See the class.

            mask, groups = ctx.populations()
            ctx.emit_table("x_by_label", frame[mask].groupby(groups).mean())

            p = ctx.populations()
            if len(p.names) < 2: ...
            if p.dropped: ctx.caveat(f"excluded {', '.join(p.dropped)}")

        `groups` is None when the object carries no such column, and the mask is all-True - so a
        plugin can call this unconditionally and branch on `p.groups is None`.
        """
        import numpy as np
        lab = self.obs(role)
        if lab is None:
            return Populations(np.ones(self.adata.n_obs, dtype=bool), None)
        mask = np.asarray(self.real_cells())
        raw = np.asarray(lab.astype(str))
        n = int((~mask).sum())
        if n and not self._said_populations:
            self._said_populations = True
            self.caveat(
                f"{n:,} cells carry an annotator sentinel and are NOT summarised as a "
                f"population - a sentinel is the annotator declining to call a cell type, and a "
                f"per-population number computed for one reads as a cell type with that value. "
                f"They stay in the object and in any per-cell result; only the grouping excludes "
                f"them.")
        groups = raw[mask]
        return Populations(mask, groups, sorted(set(groups.tolist())),
                           sorted(set(raw[~mask].tolist())))

    def source_layers(self, names=("spliced", "unspliced"), *, extra_roots=(),
                      min_match=0.5):
        """Layers the object does not carry, fetched from the ALIGNER OUTPUT beside it.

        Returns `(ok, note)`. On success the layers are on `ctx.adata` and `note` says how many
        cells each source covered; on failure `ok` is False and `note` says what was opened and
        rejected. Either way `ctx.searched` names every lead that was walked, which is what turns
        a refusal into something a user can act on: "I did not look where they are" and "your data
        does not have them" are opposite statements and read identically without it.

        WHY THE HOST OWNS THIS. Some inputs come from the aligner and cannot be derived from a
        counts matrix - spliced/unspliced counts are the case that forced it, but the shape of the
        problem is general. The host is the only party that has the upstream chain: `uns` is
        dropped from the plugin's copy of the object on purpose, and the leads arrive as plain
        JSON in `in.json`. A plugin doing this for itself would be re-deriving what it was already
        given, once per plugin, differently each time.

        Nothing here is a project's vocabulary. `names` are the host's own capability names, and
        the search recognises sources by CONTENT rather than by any pipeline's filenames.
        """
        from . import sources
        roots = [str(r) for r in extra_roots if r]
        roots += list(self.provenance.get("search_paths") or [])
        hints = list(self.provenance.get("sample_hints") or [])
        samp = self.keys.get("sample")
        if samp and self.adata is not None and samp in self.adata.obs:
            hints += [str(x) for x in self.adata.obs[samp].astype(str).unique()]
        hints = sorted({h for h in hints if h})
        self.log(f"searching {len(roots)} lead(s) for aligner output"
                 + (f", {len(hints)} sample name(s) known" if hints else ""))
        cands = sources.find(roots, hints, log=self.log, names=tuple(names))
        self.searched = list(sources.find.looked)
        self.search_exhausted = bool(sources.find.exhausted)
        self.log(f"  visited {sources.find.visited:,} director(ies), "
                 f"found {len(cands)} candidate(s)"
                 + ("  (the walk hit its limit and did NOT finish)"
                    if self.search_exhausted else ""))
        if not cands:
            return False, ""
        return sources.attach(self.adata, cands, sample_key=samp, min_match=float(min_match),
                              log=self.log, names=tuple(names))

    def design_table(self):
        """{sample: {factor: level}} from the design CSV, or {} if none was given.

        Read by the HOST so every design-aware plugin reads it the same way. Three plugins each
        parsing a CSV is three chances to disagree about whether a sample with no row is an
        error, and it is: a sample present in the object with no row is refused BY NAME upstream,
        never derived from its name.
        """
        if self._design_cache is None:
            self._design_cache = {}
            if self.design:
                try:
                    from . import inputs
                    tab, _key, factors = inputs.read_design(self.design)
                    self._design_cache = dict(tab)
                    self._design_factors = list(factors)
                except Exception as e:                                # noqa: BLE001
                    self.log(f"  design table could not be read: {e}")
        return self._design_cache

    def testable_factors(self, min_levels=2, min_replicates=2):
        """Factors with at least two levels and replication in every level, sorted.

        THE SAME BAR THE PLANNER USES. A plugin that invented its own would disagree with the
        plan the user read - and the plan is what they decided to spend a queue on.
        """
        tab = self.design_table()
        if not tab:
            return []
        samples = set(str(s) for s in (self.obs("sample").astype(str).unique()
                                       if self.obs("sample") is not None else tab))
        out = []
        for f in sorted(self._design_factors or
                        {k for row in tab.values() for k in row}):
            levels = {}
            for s, row in tab.items():
                if str(s) in samples:
                    levels.setdefault(str(row.get(f, "")), []).append(s)
            if len(levels) >= min_levels and min(map(len, levels.values())) >= min_replicates:
                out.append(f)
        return out

    def reference_for_role(self, role):
        """A declared reference BY ROLE, for this organism. `ctx.reference_for_role("rankings")`.

        The mouse and human entries of the same reference are different files with different
        names, so a plugin asking by NAME has to know both and pick - which is a species named in
        a plugin, and the one thing no plugin may do. Asking by role, the host picks.
        """
        for name, path in sorted(self.references.items()):
            spec = (self._reference_specs or {}).get(name, {})
            if spec.get("role") == role:
                return path
        return None

    def reference(self, name):
        """A declared reference file, verified by the host before the plugin was started."""
        return self.references.get(name)

    # ---- emitting ------------------------------------------------------------------------
    def emit_obs(self, name, values):
        """A per-cell result. Written keyed on barcode, so the host merges it by barcode."""
        import pandas as pd
        p = self.out / "obs" / f"{name}.csv"
        pd.Series(list(values), index=self.adata.obs_names.astype(str),
                  name=name).to_frame().to_csv(p, index_label="barcode")
        self._obs[name] = p
        return p

    def emit_obsm(self, name, array, columns=None):
        """A per-cell ARRAY, written with the barcodes its rows belong to and the names of its
        COLUMNS.

        AN ARRAY CARRIES NO COLUMN NAMES EITHER, and that gap costs the same thing one step
        later. A 674-column activity matrix reaches the merged object as a bare ndarray, so the
        host can split it by design arm and can only call the results `X_tf_activity[3]` - which
        is not a regulator, and not a figure anybody can read. The plugin is the party that
        knows the names, right here, exactly as the host was the party that knew the barcodes.

        "AN ARRAY CARRIES NO BARCODES" WAS NOT A FACT, IT WAS A GAP. The host said it three times
        - as the reason a per-cell array must cover every cell in order, and as the reason a
        per-unit one can never be merged at all - and the host is the party that knows the
        barcodes: they are `self.adata.obs_names`, right here.

        What it cost: the host itself EXCLUDES cells with NaN in a computed embedding from every
        plugin, so a plugin handed 98,627 of an object's 100,713 cells returned an array of
        98,627 rows and the merge refused it for not covering 100,713 - refused the plugin for
        returning exactly the cells the host had given it. Nothing about that is specific to one
        plugin or one dataset; it is every plugin that emits an array on an object with a
        withheld cell in it.
        """
        import numpy as np
        arr = np.asarray(array, dtype="float32")
        p = self.out / "arrays" / f"{name}.npy"
        if self.adata is not None:
            if arr.shape[0] != self.adata.n_obs:
                raise ValueError(
                    f"emit_obsm({name!r}): {arr.shape[0]:,} rows for the {self.adata.n_obs:,} "
                    f"cells this plugin was given. An obsm is per cell of the object handed to "
                    f"run(); if this result is not, emit it as a table or a side-car object.")
            (self.out / "arrays" / f"{name}.barcodes.txt").write_text(
                "\n".join(self.adata.obs_names.astype(str)) + "\n", encoding="utf-8")
        cols = list(columns) if columns is not None else getattr(array, "columns", None)
        if cols is not None:
            cols = [str(c) for c in cols]
            if len(cols) != arr.shape[1]:
                raise ValueError(
                    f"emit_obsm({name!r}): {len(cols)} column names for {arr.shape[1]} columns. "
                    f"Names that do not match the array are worse than none: they would label "
                    f"every downstream figure with the wrong thing.")
            (self.out / "arrays" / f"{name}.columns.txt").write_text(
                "\n".join(cols) + "\n", encoding="utf-8")
        np.save(p, arr)
        self._obsm[name] = p
        return p

    def emit_layer(self, name, array):
        """A per-cell, per-gene result, written with the barcodes its ROWS belong to.

        The same gap `emit_obsm` had, one slot over: a plugin handed fewer cells than the object
        returns fewer rows, and a merge that can only check `shape == adata.shape` refuses it.
        The gene axis needs no index because the host never subsets `var` - a plugin sees every
        gene of the object it was given - so the column count is asserted instead.
        """
        import numpy as np
        arr = np.asarray(array, dtype="float32")
        p = self.out / "arrays" / f"layer_{name}.npy"
        if self.adata is not None:
            if arr.shape != (self.adata.n_obs, self.adata.n_vars):
                raise ValueError(
                    f"emit_layer({name!r}): {arr.shape} for the "
                    f"({self.adata.n_obs:,}, {self.adata.n_vars:,}) object this plugin was "
                    f"given. A layer is per cell AND per gene of that object.")
            (self.out / "arrays" / f"layer_{name}.barcodes.txt").write_text(
                "\n".join(self.adata.obs_names.astype(str)) + "\n", encoding="utf-8")
        np.save(p, arr)
        self._layers[name] = p
        return p

    def emit_table(self, name, frame):
        """An edge- or gene-level result. Not per cell, so it lands beside the object as CSV."""
        p = self.out / "tables" / (name if name.endswith(".csv") else f"{name}.csv")
        frame.to_csv(p, index=True)
        self._tables.append(p)
        return p

    @property
    def figure(self):
        """The shared figure conventions: SINGLE, DOUBLE, INK, GREY, palette, legend_outside.

        Reached through `ctx` so a plugin never imports a host module to draw. What lives there is
        the difference between a figure you can read and one you can submit - live text in the
        vector output, points rasterised and axes not, real column widths, a colour-vision-safe
        palette - and it is contract, not method: every panel this tool produces should look like
        the others whichever plugin drew it, including plugins written by somebody else.
        """
        from . import figure
        return figure

    def plot(self):
        """`matplotlib.pyplot`, with the conventions already applied. Call before drawing.

        NOTHING USED THIS UNTIL THE TWO PLUGINS THAT DRAW WERE CONVERTED. Seven one-file plugins
        shipped and not one emitted a figure, so the whole figure half of this contract was
        unexercised - `emit_figure` was overriding the publication DPI with a hard 200 and leaking
        every canvas it was handed, and neither could be noticed by a plugin that never called it.
        """
        return self.figure.use()

    def emit_figure(self, name, fig, *, caption="", source=None, close=True):
        """A panel, written as raster AND vector with its source data, at journal width.

        `source` is either a frame - written beside the panel - or a path to a table already on
        disk, because a plugin whose figure is drawn from a table it emitted should be able to
        point at that table rather than write the same numbers twice.

        THE FIGURE IS CLOSED. matplotlib keeps every unclosed figure alive: a plugin drawing a
        dozen panels holds a dozen canvases of a 100,000-cell scatter in memory and gets a
        RuntimeWarning at twenty, and the plugin that trips it is the one whose report has the
        most panels in it. `close=False` is there for the rare case of drawing on it again.
        """
        png = self.out / "figures" / f"{name}.png"
        pdf = self.out / "figures" / f"{name}.pdf"
        # THE CONVENTION WINS WHERE THERE IS ONE. `figure.use()` sets savefig.dpi to 400 for
        # publication; a hard `dpi=200` here silently overrode it, so a plugin that had asked for
        # the journal settings got half the resolution it asked for. Where nothing has been set,
        # matplotlib leaves the string "figure" and 200 is the honest fallback.
        import matplotlib as _mpl
        dpi = _mpl.rcParams.get("savefig.dpi")
        dpi = dpi if isinstance(dpi, (int, float)) else 200
        fig.savefig(png, dpi=dpi, bbox_inches="tight")
        fig.savefig(pdf, bbox_inches="tight")
        src = None
        if source is not None:
            if hasattr(source, "to_csv"):
                src = self.out / "figures" / f"{name}.csv"
                source.to_csv(src)
            else:
                src = Path(source)
        # THE ID IS THE NAME IT WAS EMITTED UNDER, and that is the whole join between the
        # declaration and the panel. Without it the reporter can count figures and nothing else:
        # it cannot say which declared panel is missing, and a missing panel is the one thing a
        # reader cannot see for themselves.
        self._figures.append({"id": str(name), "path": png, "vector": pdf, "source": src,
                              "caption": caption})
        if close:
            try:
                import matplotlib.pyplot as plt
                plt.close(fig)
            except Exception:                                             # noqa: BLE001
                pass
        return png

    def emit_object(self, name, path):
        """A side-car whose result does not fit the merged object."""
        self._objects[name] = Path(path)
        return path

    def refuse(self, what, why):
        """Stop, and say what is missing. NOT an exception: a refusal is a result, and the host
        records it as one. A plugin that returns an empty answer instead produces a result-shaped
        hole nobody can distinguish from a real negative."""
        self.status = "refused"
        self.absent.append({"what": what, "why": why})
        self.headline = self.headline or f"refused: {what}"

    def fixture(self, n_cells=200, n_genes=300, *, genes=None, labels=("A", "B"), seed=0):
        """A small synthetic AnnData for this plugin's own selftest, built by the HOST.

        Every selftest in this project began by hand-rolling one of these, and each got it subtly
        differently - one too small for the tool's own coverage check, one with no label column,
        one whose X was counts where the tool wanted log values. A fixture is contract, not
        method, so the host builds it and the plugin says only what it needs to be true.
        """
        import anndata as ad
        import numpy as np
        import pandas as pd
        rng = np.random.default_rng(seed)
        gv = list(genes) if genes else [f"Gene{i:04d}" for i in range(n_genes)]
        X = rng.poisson(rng.uniform(0.2, 6.0, size=len(gv)), size=(n_cells, len(gv)))
        A = ad.AnnData(
            X.astype("float32"),
            obs=pd.DataFrame({"label": pd.Categorical(
                [labels[i % len(labels)] for i in range(n_cells)])},
                index=[f"c{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=gv))
        A.layers["counts"] = A.X.copy()
        import scanpy as sc
        B = A.copy()
        sc.pp.normalize_total(B, target_sum=1e4)
        sc.pp.log1p(B)
        A.layers["lognorm"] = B.X.copy()
        return A

    def effect(self, acquire, release=None):
        """Acquire something that must be released, and register the release NOW.

        Borrowed from Cordis, where everything a plugin registers is tied to its scope and undone
        when the scope closes. A dask client, a temp directory, an R session, a memory-mapped
        file: each is released whether the plugin returns, refuses, or raises - which is the case
        a `finally` in a plugin gets wrong, because a plugin that raised did not reach its
        `finally` in the version somebody wrote in a hurry.

            client = ctx.effect(lambda: Client(n_workers=ctx.cores),
                                lambda c: c.close())
        """
        obj = acquire() if callable(acquire) else acquire
        if release is not None:
            self._effects.append((obj, release))
        return obj

    def _dispose(self, log=None):
        """Release every effect, newest first, and never let one failure hide another."""
        for obj, release in reversed(self._effects):
            try:
                release(obj)
            except Exception as e:                                        # noqa: BLE001
                (log or self.log)(f"  effect release failed ({type(e).__name__}: {e}); "
                                  f"continuing so the rest are still released")
        self._effects.clear()

    def caveat(self, text):
        """Something true of this result that a reader must be told. Printed with the numbers."""
        self.caveats.append(text)

    def contradiction(self, claim):
        """This plugin's OWN diagnostic refutes its own headline. Say it in the headline.

        Two pages measured on a real cohort carried a headline their own figures contradict:
        "45.5% of cells score S or G2M" in post-mitotic tissue, on a panel whose genes are
        detected in almost no cell and whose called fraction FALLS as sequencing depth rises;
        and "3 terminal states" over cells whose fate entropy sits at the maximum three states
        allow, which is what a uniform fate probability looks like.

        Neither page was wrong - the evidence against each was plotted, honestly, further down.
        But a reader takes the headline, and a limit that is only reachable by reading every
        panel is a limit most readers will not meet. A refutation belongs where the claim is.

        Recorded as a caveat too, so it survives into `report.json` and any document built from
        it rather than living only in a string.

        ORDER MUST NOT MATTER, and it did. This prefixed `self.headline`, and both plugins that
        call it assign `ctx.headline = ...` on the NEXT line - so the refutation was written and
        immediately overwritten, and two runs came back with the unqualified headline and no
        sign anything had been attempted. A mechanism that works only when called last is a
        trap set for whoever writes the next plugin.

        It records; the entry point composes the headline from what was recorded.
        """
        text = str(claim).strip()
        if not text:
            return
        self._contradictions.append(text)
        self.caveat(text)

    def metric(self, name, value):
        """Record ONE headline number for this instance, comparable across units.

        Declared in `report.unit_metrics` and checked against what is emitted, exactly as
        figures are: a number nobody declared cannot be compared, and a declared number that
        never arrives leaves a gap that reads like a plugin nobody asked for a comparison from.

        The host draws the across-unit comparison itself, once, for every per-unit plugin -
        so this is the whole of what a plugin has to do to get one, and no plugin writes its
        own version of the same picture.
        """
        try:
            v = float(value)
        except (TypeError, ValueError):
            self.log(f"  metric {name!r} is not a number ({value!r}); not recorded")
            return
        if v != v:                                        # NaN compares unequal to itself
            self.log(f"  metric {name!r} is NaN; not recorded")
            return
        self._metrics[str(name)] = v
