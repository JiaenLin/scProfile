"""Comparison panels BETWEEN units, for every contrast the design supports.

WHAT THIS EXISTS TO FIX. A per-unit plugin drew every figure it had about ONE unit, and the
cohort page carried a single summary strip. On a factorial design that is the wrong way round:
the comparison between arms is the question, and it had no picture at all. Ten pages of "here
is unit 3" and nothing showing one arm against another.

IT IS DRIVEN BY A DECLARATION, NOT BY A PLUGIN NAME. A plugin says which of its per-unit tables
carries a network:

    "unit_network": {"table": "tables/ccc_edges.csv", "source": "source",
                     "target": "target", "weight": "prob", "group": "pathway_name"}

and this draws the same panels for it. Nothing here knows what method produced the numbers,
which is what stops it becoming one plugin's private figure code living in the host.

NO FIGURE IS GATED ON SAMPLE-LEVEL SUPPORT. Arms are pooled from whatever units belong to them,
so a contrast is drawable whenever both its arms have any data at all. Whether the arms have
enough SAMPLES to support an interval is a separate question, answered in the design panel, and
it is not permitted to withhold a picture here.
"""

from __future__ import annotations

from . import figure as F


def pool(per_unit_edges, members):
    """One arm's edge list: the concatenation of its members'. Group level, by construction."""
    import pandas as pd

    frames = [per_unit_edges[u] for u in members if u in per_unit_edges]
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def matrices(edges, pops, weight="prob"):
    """(count, weight) K x K for one arm, over a FIXED population order."""
    import numpy as np

    ix = {p: i for i, p in enumerate(pops)}
    c = np.zeros((len(pops), len(pops)))
    w = np.zeros((len(pops), len(pops)))
    if edges is None or not len(edges):
        return c, w
    for s, t, p in zip(edges["source"].astype(str), edges["target"].astype(str),
                       edges[weight]):
        if s in ix and t in ix:
            c[ix[s], ix[t]] += 1.0
            w[ix[s], ix[t]] += float(p)
    return c, w


def arm_pairs(design, factors=None, technical=None):
    """[(label, factor, from_level, to_level, from_filter, to_filter)] - every contrast.

    The same six a 2x2 supports: each factor marginally, and each factor held at every level of
    every other. A filter is a dict of factor->level that a SAMPLE must match to join that arm.
    """
    from .units import DEFAULT_TECHNICAL

    tech = {t.lower() for t in (technical if technical is not None else DEFAULT_TECHNICAL)}
    levels = {}
    for row in design.values():
        for f, v in (row or {}).items():
            levels.setdefault(str(f), set()).add(str(v))
    facs = [f for f in sorted(levels)
            if len(levels[f]) == 2 and f.lower() not in tech]
    facs = [f for f in (factors or facs) if f in levels and len(levels[f]) == 2]
    out = []
    for f in facs:
        a, b = sorted(levels[f])
        out.append((f, f, a, b, {f: a}, {f: b}))
        for h in facs:
            if h == f:
                continue
            for lv in sorted(levels[h]):
                out.append((f"{f} | {h} = {lv}", f, a, b,
                            {f: a, h: lv}, {f: b, h: lv}))
    return out


def _members(design, filt):
    return [s for s, row in design.items()
            if all(str((row or {}).get(k)) == str(v) for k, v in filt.items())]


def _short(pops):
    m = F.short_labels(list(pops))
    return [m[p] for p in pops]


def draw_contrast(per_unit_edges, design, spec, out_dir, prefix, *, weight="prob",
                  group_col=None, min_edges=1):
    """Every panel for ONE contrast. Returns [(figure_id, path, caption)]."""
    import numpy as np
    import matplotlib.pyplot as plt
    from pathlib import Path

    label, fac, lo_lv, hi_lv, lo_f, hi_f = spec
    lo_m, hi_m = _members(design, lo_f), _members(design, hi_f)
    e_lo, e_hi = pool(per_unit_edges, lo_m), pool(per_unit_edges, hi_m)
    if e_lo is None or e_hi is None or len(e_lo) < min_edges or len(e_hi) < min_edges:
        return []
    pops = sorted(set(e_lo["source"].astype(str)) | set(e_lo["target"].astype(str))
                  | set(e_hi["source"].astype(str)) | set(e_hi["target"].astype(str)))
    c_lo, w_lo = matrices(e_lo, pops, weight)
    c_hi, w_hi = matrices(e_hi, pops, weight)
    short = _short(pops)
    out = []
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    slug = "".join(ch if ch.isalnum() else "_" for ch in label).strip("_")

    def _save(fig, fid, caption):
        p = Path(out_dir) / f"{prefix}_{fid}__{slug}.png"
        fig.savefig(p, dpi=200)
        plt.close(fig)
        out.append((f"{fid}__{slug}", p, caption))

    arm_n = f"{lo_lv} (n={len(lo_m)}) vs {hi_lv} (n={len(hi_m)})"

    # ---- 1. differential interactions, sender x receiver -------------------------------------
    for what, A, B, unit in (("count", c_lo, c_hi, "significant interactions"),
                             ("strength", w_lo, w_hi, "summed probability")):
        D = B - A
        if not np.any(D):
            continue
        fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.92), layout="constrained")
        m = float(np.abs(D).max()) or 1.0
        im = ax.imshow(D, cmap="RdBu_r", vmin=-m, vmax=m)
        ax.set_xticks(range(len(pops)))
        ax.set_xticklabels(short, rotation=45, ha="right", fontsize=5)
        ax.set_yticks(range(len(pops)))
        ax.set_yticklabels(short, fontsize=5)
        ax.set_xlabel("receiver")
        ax.set_ylabel("sender")
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
        cb.outline.set_visible(False)
        cb.set_label(f"{hi_lv} minus {lo_lv}   ({unit})", fontsize=6)
        _save(fig, f"C1_diff_{what}",
              (f"Change in {unit} from {lo_lv} to {hi_lv}, per sender-receiver pair. "
               f"{arm_n}.",
               f"Cells are pooled within each arm before inference, so this is a group-level "
               f"comparison and needs no single sample to support one. Blue is lower in "
               f"{hi_lv}, red higher, on a symmetric scale so both directions read at the same "
               f"weight. Nothing here is a test: no interval is drawn because none was "
               f"computed."))

    # ---- 2. information flow per group (rankNet, paired) -------------------------------------
    if group_col and group_col in e_lo.columns and group_col in e_hi.columns:
        fl = e_lo.groupby(group_col)[weight].sum()
        fh = e_hi.groupby(group_col)[weight].sum()
        keys = sorted(set(fl.index) | set(fh.index),
                      key=lambda k: -(float(fl.get(k, 0)) + float(fh.get(k, 0))))[:22]
        if keys:
            a = np.array([float(fl.get(k, 0.0)) for k in keys])
            b = np.array([float(fh.get(k, 0.0)) for k in keys])
            y = np.arange(len(keys))[::-1]
            fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.7, 0.15 * len(keys) + 0.6)),
                                   layout="constrained")
            ax.barh(y + 0.19, a, height=0.36, color=F.OKABE_ITO[0], label=str(lo_lv))
            ax.barh(y - 0.19, b, height=0.36, color=F.OKABE_ITO[1], label=str(hi_lv))
            ax.set_yticks(y)
            ax.set_yticklabels(keys, fontsize=5)
            ax.set_xlabel("information flow (summed probability)")
            ax.legend(fontsize=5.5, frameon=False, loc="lower right")
            ax.tick_params(axis="y", length=0)
            for sp in ("top", "right", "left"):
                ax.spines[sp].set_visible(False)
            _save(fig, "C3_flow",
                  (f"Information flow per {group_col.replace('_', ' ')} in each arm, ranked by "
                   f"their combined total. {arm_n}.",
                   f"Arms are pooled groups, not averages of samples. Bars are on the method's "
                   f"own probability scale and are comparable between these two arms - inferred "
                   f"from the same database over the same populations - and not against any "
                   f"other figure."))

    # ---- 3. signalling role shift ------------------------------------------------------------
    o_lo, i_lo = w_lo.sum(1), w_lo.sum(0)
    o_hi, i_hi = w_hi.sum(1), w_hi.sum(0)
    if float(o_lo.sum() + o_hi.sum()) > 0:
        fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.92), layout="constrained")
        cmap = F.palette(list(pops))
        for k, p in enumerate(pops):
            ax.annotate("", xy=(o_hi[k], i_hi[k]), xytext=(o_lo[k], i_lo[k]),
                        arrowprops=dict(arrowstyle="-|>", lw=0.9, color=cmap[p],
                                        shrinkA=0, shrinkB=0, alpha=0.9))
            ax.plot([o_lo[k]], [i_lo[k]], "o", ms=3.4, color=cmap[p], mec="white", mew=.5)
            ax.plot([o_hi[k]], [i_hi[k]], "o", ms=6.4, color=cmap[p], mec=F.INK, mew=.5)
        lim = float(max(o_lo.max(), o_hi.max(), i_lo.max(), i_hi.max())) * 1.12 or 1.0
        ax.plot([0, lim], [0, lim], color=F.GREY, lw=.8, ls="--", zorder=0)
        _tx = [ax.annotate(s, (o_hi[k], i_hi[k]), fontsize=5, xytext=(4, 2),
                           textcoords="offset points", color=F.INK)
               for k, s in enumerate(short)]
        F.spread_labels(ax, _tx)
        ax.set_xlim(0, lim)
        ax.set_ylim(0, lim)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("outgoing strength")
        ax.set_ylabel("incoming strength")
        # WHICH END IS WHICH, ON THE FIGURE. The caption says it, and a figure lifted into a
        # slide leaves its caption behind - so the two arms are named in the panel itself. The
        # marker sizes here are the same ones the arrows use.
        import matplotlib.lines as _ml
        ax.legend(handles=[_ml.Line2D([], [], marker="o", ls="", ms=3.4, color=F.INK,
                                      label=f"{lo_lv}  (tail)"),
                           _ml.Line2D([], [], marker="o", ls="", ms=6.4, color=F.INK,
                                      label=f"{hi_lv}  (head)")],
                  fontsize=5.5, frameon=False, loc="lower right", handletextpad=0.4)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        _save(fig, "C4_role_shift",
              (f"How each population's signalling role moves from {lo_lv} to {hi_lv}. "
               f"{arm_n}.",
               f"The small marker is {lo_lv}, the arrowhead {hi_lv}. Above the dashed line a "
               f"population receives more than it sends. Arms are pooled groups. An arrow is "
               f"the difference of two point estimates and carries no interval - its length is "
               f"not evidence of size."))
    return out
