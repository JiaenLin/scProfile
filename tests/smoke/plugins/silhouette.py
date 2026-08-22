"""Cluster separation: how well-separated the labelled populations are in the embedding.

THIS PLUGIN EXISTS TO TEST THE FORMAT, NOT TO EXTEND THE TOOL.

It is deliberately NOT one of the nine methods scProfile was designed around. It wraps
scikit-learn, needs no environment of its own, produces a per-cell score and a per-population
table, and provides a capability another plugin can inject. If the format only fits the nine
methods it was written beside, it is not a format - it is nine wrappers with a shared directory.

So the question this answers is: can somebody who has never spoken to this project drop a file in
and have the host build it, plan it, run it, merge it and report it, with no change to the host?

The method itself is real and small: the silhouette coefficient of each cell against its own
label in the embedding the host chose. It is a genuine quality measure and a genuinely
misleadable one, which is why its limits are declared as carefully as any other plugin's.
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "summary": "how separated the labelled populations are in the embedding",
    "when_to_use": "you want a number for whether your labels correspond to structure in the "
                   "embedding, rather than only a picture of it",
    "wraps": {"tool": "scikit-learn", "homepage": "https://scikit-learn.org",
              "license": "BSD-3-Clause",
              "cite": "Rousseeuw, J. Comput. Appl. Math. 1987 (silhouettes); "
                      "Pedregosa et al., JMLR 2011 (scikit-learn)"},
    "upstream": {
        "docs": "https://scikit-learn.org/stable/modules/generated/"
                "sklearn.metrics.silhouette_samples.html",
        "read": "2026-08-22",
        "defaults_changed": [
            "metric='euclidean' is kept, but it is only meaningful because the embedding is "
            "already a Euclidean space the upstream tool chose. On a raw count matrix it would "
            "not be, and the plugin would still return numbers.",
        ],
        "not_used": [
            "silhouette_score, which returns the mean alone. The per-cell values are the useful "
            "thing: a mean of 0.1 can be one badly-placed population or every cell mediocre, and "
            "those are different findings.",
        ],
        "gotchas": [
            "silhouette_samples is O(n^2) in memory on a dense pairwise distance. It is "
            "subsampled per label here, and the subsample size is declared config rather than a "
            "constant, so a user can raise it and know they did.",
        ],
    },

    # CAPABILITIES, resolved by the host. This plugin names no column and no obsm key.
    "inject": {"required": ["embedding", "label"], "optional": []},
    "provides": [],
    "produces": ["obs[silhouette]", "tables/separation_by_label.csv"],

    "config": {
        "max_cells": {"type": "int", "default": 20000, "min": 100,
                      "help": "cells sampled before computing distances; the calculation is "
                              "quadratic in memory, so this bounds it rather than the object"},
        "min_cells_per_label": {"type": "int", "default": 10, "min": 2,
                                "help": "populations smaller than this are not scored - a "
                                        "silhouette over three cells is arithmetic, not evidence"},
    },

    # No `env`: it runs in the host's interpreter, because scanpy already brings scikit-learn.
    "cost": "medium", "cores": 4,

    "cannot_show": [
        "A SILHOUETTE IS ABOUT THE EMBEDDING, NOT THE BIOLOGY. Two genuinely distinct cell types "
        "that the embedding placed together score badly, and that is a statement about the "
        "embedding.",
        "It is computed on the embedding the host chose. A different embedding gives different "
        "numbers for the same labels, and the two are not comparable.",
        "Scores from two datasets are not comparable: the coefficient depends on the number of "
        "populations and their relative sizes.",
        "A negative score means a cell sits closer to another label's cells. That is worth "
        "looking at and is not by itself an error in the annotation.",
    ],
}


def run(ctx):
    import numpy as np
    import pandas as pd
    from sklearn.metrics import silhouette_samples

    emb = np.asarray(ctx.embedding())
    lab = ctx.obs("label").astype(str).to_numpy()

    # POPULATIONS TOO SMALL TO SCORE ARE EXCLUDED AND NAMED, never quietly dropped: a label
    # missing from a results table reads as a label that scored nothing.
    counts = pd.Series(lab).value_counts()
    too_small = sorted(counts[counts < ctx.config["min_cells_per_label"]].index)
    keep = ~np.isin(lab, too_small)
    if too_small:
        ctx.caveat(f"{len(too_small)} population(s) have fewer than "
                   f"{ctx.config['min_cells_per_label']} cells and are NOT scored: "
                   f"{', '.join(too_small)}. A silhouette over a handful of cells is arithmetic, "
                   f"not evidence.")
    if keep.sum() < 3 or len(set(lab[keep])) < 2:
        return ctx.refuse("silhouette",
                          "fewer than two populations are large enough to compare. A silhouette "
                          "needs at least two.")

    idx = np.flatnonzero(keep)
    rng = np.random.default_rng(0)
    if idx.size > ctx.config["max_cells"]:
        idx = np.sort(rng.choice(idx, size=ctx.config["max_cells"], replace=False))
        ctx.caveat(f"Computed on a random {idx.size:,}-cell subsample (seed 0) because the "
                   f"distance calculation is quadratic in memory. Raise max_cells to change it.")

    sil = silhouette_samples(emb[idx], lab[idx], metric="euclidean")

    # Every cell gets a value; the ones not scored get NaN rather than a zero, because zero is a
    # meaningful silhouette and "not measured" is not.
    full = np.full(ctx.adata.n_obs, np.nan, dtype="float32")
    full[idx] = sil
    ctx.emit_obs("silhouette", full)

    by = (pd.DataFrame({"label": lab[idx], "silhouette": sil})
          .groupby("label")["silhouette"].agg(["count", "mean", "median", "min", "max"])
          .sort_values("mean"))
    ctx.emit_table("separation_by_label", by)

    worst = by.index[0]
    ctx.headline = (f"median silhouette {float(np.median(sil)):.3f} over {len(by)} population(s); "
                    f"least separated {worst} ({by.loc[worst, 'mean']:.3f})")
    ctx.caveat(f"{int((sil < 0).sum()):,} of {sil.size:,} scored cells have a NEGATIVE "
               f"silhouette - they sit closer to another label's cells than to their own.")


def selftest(ctx):
    """Prove the call works here: the API, the shapes, and the sign convention.

    Uses two deliberately SEPARATED blobs, because a silhouette on random data is near zero and
    would pass an assertion that only checked finiteness - the fixture has to contain the thing
    being measured or the test measures nothing.
    """
    import numpy as np
    from sklearn.metrics import silhouette_samples

    rng = np.random.default_rng(0)
    a = rng.normal(0, 0.3, size=(60, 5))
    b = rng.normal(8, 0.3, size=(60, 5))
    emb = np.vstack([a, b])
    lab = np.array(["A"] * 60 + ["B"] * 60)

    sil = silhouette_samples(emb, lab, metric="euclidean")
    assert sil.shape == (120,), f"silhouette_samples returned {sil.shape}, expected (120,)"
    assert np.isfinite(sil).all(), "non-finite silhouette values"
    # THE SIGN CONVENTION IS THE THING THAT COULD SILENTLY INVERT. Well-separated blobs must
    # score near +1; if a future version flipped it, every result would read backwards and no
    # shape check would notice.
    assert sil.mean() > 0.8, (
        f"two blobs eight standard deviations apart scored {sil.mean():.3f}. Either the metric "
        f"changed or the sign convention did - and a flipped sign would make every result read "
        f"backwards without any shape check noticing.")
    ctx.log(f"  separated blobs score {sil.mean():.3f}; overlapping data would score near 0")
