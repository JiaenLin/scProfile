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
        out.append((f"{fid}__{slug}", p, caption, label))

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
        # MARKERS FIRST, ARROWS ON TOP, AND THE HEAD STOPPING SHORT OF THE MARKER. The first
        # version drew each arrow and then painted its destination marker over the arrowhead,
        # so DIRECTION - the entire content of the panel - was legible only from the legend.
        for k, p in enumerate(pops):
            ax.plot([o_lo[k]], [i_lo[k]], "o", ms=3.4, color=cmap[p], mec="white", mew=.5,
                    zorder=2)
            ax.plot([o_hi[k]], [i_hi[k]], "o", ms=5.6, color=cmap[p], mec=F.INK, mew=.5,
                    zorder=2)
        for k, p in enumerate(pops):
            ax.annotate("", xy=(o_hi[k], i_hi[k]), xytext=(o_lo[k], i_lo[k]),
                        arrowprops=dict(arrowstyle="-|>,head_width=.22,head_length=.42",
                                        lw=0.9, color=cmap[p], shrinkA=2, shrinkB=5,
                                        alpha=.95), zorder=3)
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
        # OUTSIDE THE DATA. `loc="lower right"` put the key on top of the longest arrow in the
        # panel - the one population whose role moved furthest, which is the thing a reader
        # came for.
        ax.legend(handles=[_ml.Line2D([], [], marker="o", ls="", ms=3.4, color=F.INK,
                                      label=f"{lo_lv}  (tail)"),
                           _ml.Line2D([], [], marker="o", ls="", ms=5.6, color=F.INK,
                                      label=f"{hi_lv}  (arrowhead)")],
                  fontsize=5.5, frameon=False, loc="upper left",
                  bbox_to_anchor=(0.0, -0.235), ncol=2, handletextpad=0.4,
                  columnspacing=1.4)
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

class _Shim:
    """The tiny surface `network_panels` expects, for a caller that has no plugin context.

    The single-network kinds are written against the plugin-side emit point so a plugin can call
    them directly. The host draws the same kinds for pooled arms and has no such context, and
    duplicating the drawing code host-side is how two renderings of one kind drift apart. One
    shim, one implementation.
    """

    def __init__(self, out_dir, prefix, slug, collect, label="", members=()):
        from . import figure as _F
        self.figure = _F
        self._out, self._prefix, self._slug = out_dir, prefix, slug
        self._collect, self._label = collect, label
        #: THE SAME STAMP THE PLUGIN-SIDE EMIT POINT APPLIES. A host-drawn arm panel is exactly
        #: the kind of picture that gets lifted into a slide, and it has no unit written on it
        #: anywhere unless it is put there. Cell counts are not reachable from an edge list, so
        #: the stamp says what it knows: the arm, and how many samples were pooled into it.
        self._members = tuple(str(m) for m in (members or ()))

    def plot(self):
        import matplotlib.pyplot as plt
        return plt

    def emit_figure(self, fid, fig, caption="", source=None):
        from pathlib import Path
        import matplotlib.pyplot as plt
        d = Path(self._out)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{self._prefix}_{fid}__{self._slug}.png"
        if self._label:
            n = len(self._members)
            what = (f"design arm — {n} samples pooled" if n > 1
                    else "design arm — 1 sample" if n == 1 else "design arm")
            try:
                fig.text(0.0, -0.006, f"{self._label}   ·   {what}", ha="left", va="top",
                         fontsize=5.2, color="#5A5A5A", transform=fig.transFigure)
            except Exception:                                             # noqa: BLE001
                pass
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        self._collect.append((f"{fid}__{self._slug}", path, caption, self._label))


def arms_in(design, pairs):
    """{label: filter} - every distinct arm any contrast compares, each appearing once.

    A marginal contrast's two arms and a conditional contrast's two arms are all arms worth a
    network of their own, and several contrasts share one - drawing an arm once per contrast
    would render the same pooled network four times and invite a reader to compare two
    renderings of identical data.
    """
    out = {}
    for label, fac, lo, hi, lo_f, hi_f in pairs:
        for filt in (lo_f, hi_f):
            key = ", ".join(f"{k} = {v}" for k, v in sorted(filt.items()))
            out.setdefault(key, filt)
    return out


def draw_arm_networks(per_unit_edges, design, arms, out_dir, prefix, *, min_edges=1,
                     group_col=None, member_col=None):
    """The single-network kinds for each arm, pooled. Returns [(fid, path, caption)].

    GROUP LEVEL BY CONSTRUCTION: an arm's cells are pooled before anything is drawn, so no panel
    here needs any single unit to support an inference by itself.

    THE LIST IS `panels.host_kinds()`, NOT A LIST WRITTEN HERE. A registry that nothing consults
    is a specification of intent, and this function was the place a kind could be registered and
    then not drawn - which is how five of thirteen kinds came to be all a plugin inherited from
    its declaration. The registry now names an owner per kind and a test asserts the host draws
    every kind it owns, so the two cannot part company again.
    """
    from . import network_panels as NP

    # ONE POPULATION SET ACROSS EVERY ARM, computed before anything is drawn. Taking each arm's
    # own populations gave the two arms of one contrast DIFFERENT AXES - measured on a real
    # cohort, one arm carried a population the other did not - so two matrices laid out
    # identically, side by side, were indexed differently and a reader comparing cell to cell
    # was comparing different pairs. The union makes an arm's missing population VISIBLE as an
    # empty row rather than as a silently shorter axis, and `network_panels.unconnected` already
    # names a population with no link, which is exactly what one of these now is.
    #
    # THE COLOUR SCALE IS STILL PER ARM, deliberately (panels.R5). A shared axis is a statement
    # about WHICH populations exist; a shared scale would be a statement that two arms' strengths
    # are on one ruler, which for a per-object normalisation they are not.
    pooled = {}
    for label, filt in sorted(arms.items()):
        e = pool(per_unit_edges, _members(design, filt))
        if e is not None and len(e) >= min_edges:
            pooled[label] = e
    pops = sorted({str(x) for e in pooled.values()
                   for x in set(e["source"].astype(str)) | set(e["target"].astype(str))})

    made = []
    for label, e in sorted(pooled.items()):
        slug = "".join(ch if ch.isalnum() else "_" for ch in label).strip("_")
        got = []
        shim = _Shim(out_dir, prefix, slug, got, label=label,
                     members=_members(design, arms[label]))
        NP.circle(shim, e, pops, title=label)
        NP.chord(shim, e, pops, title=label)
        NP.matrix(shim, e, pops, title=label)
        NP.role_scatter(shim, e, pops, title=label)
        # DECLARED OR NOT DRAWN. Each of these returns False rather than raising when the
        # declaration names no grouping column, so a plugin that declares less gets fewer
        # panels and never a broken one.
        NP.flow_rank(shim, e, pops, group_col, title=label)
        NP.role_heatmap(shim, e, pops, group_col, title=label)
        NP.contribution(shim, e, pops, group_col, member_col, title=label)
        made += got
    return made

