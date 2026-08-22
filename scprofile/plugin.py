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
            "env": {"python": "3.11", "pip": ["mytool==1.2.3"]},   # omit to use the host's
        }

        def run(ctx):
            import mytool
            score = mytool.compute(ctx.X, groups=ctx.obs(ctx.keys["label"]))
            ctx.emit_obs("my_score", score)
            ctx.headline = f"{len(score):,} cells scored"

That is the entire plugin. No manifest to keep in step with a wrapper, no `run.py` to write, no
skeleton to finish, no boilerplate to copy from the plugin next door.

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


class Context:
    """Everything a plugin is given, already correct. Built by the host, never by a plugin.

    The plugin receives this and returns nothing: it calls `emit_*` for what it produced and sets
    `headline`. What reaches the merged object is exactly what it emitted.
    """

    def __init__(self, adata, *, keys, out, cores=1, unit=None, organism=None, assay=None,
                 references=None, params=None, design=None, sentinels=(), log=print):
        self.adata = adata
        #: {role: actual name in THIS object}. `ctx.keys["label"]`, never a literal column.
        self.keys = dict(keys or {})
        self.out = Path(out)
        #: THE ALLOCATED SHARE. `os.cpu_count()` in a plugin starts the node's worth of threads
        #: per plugin, and four concurrent plugins then start four times the node.
        self.cores = int(cores or 1)
        self.unit = unit
        self.organism = (organism or "").lower() or None
        self.assay = (assay or "").lower() or None
        self.references = dict(references or {})
        self.params = dict(params or {})
        self.design = design
        self.sentinels = tuple(sentinels or ())
        self.log = log

        self.headline = ""
        self.status = "ok"
        self._obs, self._obsm, self._layers = {}, {}, {}
        self._tables, self._figures, self._objects = [], [], {}
        self.caveats, self.absent = [], []
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

    def obs(self, role_or_name):
        """A column BY ROLE. `ctx.obs("label")` resolves through the key map; a literal name is
        accepted too, so a plugin can read something only it knows about."""
        name = self.keys.get(role_or_name, role_or_name)
        return self.adata.obs[name] if name in self.adata.obs else None

    def embedding(self):
        emb = self.keys.get("embedding")
        return self.adata.obsm[emb] if emb and emb in self.adata.obsm else None

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

    def emit_obsm(self, name, array):
        import numpy as np
        p = self.out / "arrays" / f"{name}.npy"
        np.save(p, np.asarray(array, dtype="float32"))
        self._obsm[name] = p
        return p

    def emit_layer(self, name, array):
        import numpy as np
        p = self.out / "arrays" / f"layer_{name}.npy"
        np.save(p, np.asarray(array, dtype="float32"))
        self._layers[name] = p
        return p

    def emit_table(self, name, frame):
        """An edge- or gene-level result. Not per cell, so it lands beside the object as CSV."""
        p = self.out / "tables" / (name if name.endswith(".csv") else f"{name}.csv")
        frame.to_csv(p, index=True)
        self._tables.append(p)
        return p

    def emit_figure(self, name, fig, *, caption="", source=None):
        """A panel, written as raster AND vector with its source data, at journal width."""
        png = self.out / "figures" / f"{name}.png"
        pdf = self.out / "figures" / f"{name}.pdf"
        fig.savefig(png, dpi=200, bbox_inches="tight")
        fig.savefig(pdf, bbox_inches="tight")
        src = None
        if source is not None:
            src = self.out / "figures" / f"{name}.csv"
            source.to_csv(src)
        self._figures.append({"path": png, "vector": pdf, "source": src, "caption": caption})
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

    def caveat(self, text):
        """Something true of this result that a reader must be told. Printed with the numbers."""
        self.caveats.append(text)
