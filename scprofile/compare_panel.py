"""Comparison panels BETWEEN units, for every contrast the design supports.

WHAT THIS EXISTS TO FIX. A per-unit plugin drew every figure it had about ONE unit, and the
cohort page carried a single summary strip. On a factorial design that is the wrong way round:
the comparison between arms is the question, and it had no picture at all. A page of "here is
unit 3", once per unit, and nothing showing one arm against another.

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


def contrast_confounds(design, lo_members, hi_members, exclude=()):
    """{factor: state} for the samples ONE contrast actually compares.

    ALIASING IS A PROPERTY OF THE CONTRAST, NOT ONLY OF THE FACTOR PAIR. Two factors can be
    perfectly crossed over the whole design and still be aliased inside one conditional
    contrast, because conditioning throws away the samples that crossed them. Measured on a real
    two-factor study: a treatment factor and a technical factor were balanced over the whole
    cohort, yet one of the conditional contrasts compared one technical level against the other
    with NO OVERLAP at all - every sample on one side from one level, every sample on the other
    side from the other. A reader told only that the design is "crossed" would take that
    contrast at face value, and the crossing is a property of the cohort rather than of the
    comparison being drawn.

    Three states, and the middle one is the one people forget:
      aliased   the two sides share no level of this factor, so it cannot be separated at all
      partial   they overlap but are not balanced, so it is separable only in part
      balanced  both levels appear on both sides
    """
    out = {}
    facs = {f for m in list(lo_members) + list(hi_members)
            for f in (design.get(m) or {})} - set(exclude)
    for f in sorted(facs):
        lo = {str((design.get(m) or {}).get(f)) for m in lo_members}
        hi = {str((design.get(m) or {}).get(f)) for m in hi_members}
        if len(lo) == 1 and len(hi) == 1 and lo == hi:
            continue                      # held constant: not a confound, it is the condition
        out[f] = ("aliased" if lo.isdisjoint(hi)
                  else "balanced" if lo == hi else "partial")
    return out


def confound_sentence(conf, factor):
    """The one-line statement a contrast panel carries about what it cannot separate."""
    bad = sorted(f for f, st in conf.items() if st == "aliased" and f != factor)
    part = sorted(f for f, st in conf.items() if st == "partial" and f != factor)
    if not bad and not part:
        return (f"Every other factor in the design is balanced across this contrast, so it is "
                f"separable from all of them.")
    out = ""
    if bad:
        out += (f"ALIASED WITH {', '.join(bad).upper()}: the two sides share no level of "
                f"{'it' if len(bad) == 1 else 'them'}, so nothing in these data separates a "
                f"{factor} effect from "
                f"{'a ' + bad[0] + ' effect' if len(bad) == 1 else 'effects of ' + ', '.join(bad)}"
                f". Any statement naming {factor} here is equally a statement about "
                f"{', '.join(bad)}. ")
    if part:
        out += (f"Partly confounded with {', '.join(part)}: the sides overlap but are not "
                f"balanced, so separation is incomplete. ")
    return out


def draw_contrast(per_unit_edges, design, spec, out_dir, prefix, *, weight="prob",
                  group_col=None, min_edges=1, weight_scale="per_object"):
    """Every panel for ONE contrast. Returns [(figure_id, path, caption)].

    WHERE THE WEIGHT IS NORMALISED WITHIN EACH UNIT, EVERY WEIGHT-DERIVED PANEL IS DRAWN ON
    SHARES. Measured on a real cohort: two arms of one contrast had total inferred strength of
    23.4 and 7.8 - a factor of THREE - so a raw difference between them is mostly the difference
    in totals, and the largest "effect" on the page was the smaller arm being smaller. On the
    same pathway the raw comparison said the effect of one factor DISAPPEARED under the other
    (-4.15 against +0.16) while the share comparison said it REVERSED (-8.6 pp against +8.7 pp).
    Same numbers, opposite conclusions, and the difference is entirely the denominator.

    Counts are left as counts - a count of significant interactions is not a normalised weight -
    and every panel says which of the two it is drawing.
    """
    import numpy as np
    import matplotlib.pyplot as plt
    from pathlib import Path

    label, fac, lo_lv, hi_lv, lo_f, hi_f = spec
    lo_m, hi_m = _members(design, lo_f), _members(design, hi_f)
    e_lo, e_hi = pool(per_unit_edges, lo_m), pool(per_unit_edges, hi_m)
    if e_lo is None or e_hi is None or len(e_lo) < min_edges or len(e_hi) < min_edges:
        return []
    _seen_lo = set(e_lo["source"].astype(str)) | set(e_lo["target"].astype(str))
    _seen_hi = set(e_hi["source"].astype(str)) | set(e_hi["target"].astype(str))
    pops = sorted(_seen_lo | _seen_hi)
    c_lo, w_lo = matrices(e_lo, pops, weight)
    c_hi, w_hi = matrices(e_hi, pops, weight)
    rel = str(weight_scale or "per_object") != "absolute"
    _tot_lo, _tot_hi = float(w_lo.sum()) or 1.0, float(w_hi.sum()) or 1.0
    if rel:
        w_lo, w_hi = 100.0 * w_lo / _tot_lo, 100.0 * w_hi / _tot_hi
    _wunit = "% of the arm's own total" if rel else "summed probability"
    _wnote = (f"  THE WEIGHT IS NORMALISED WITHIN EACH UNIT, so the two arms' raw totals "
              f"({_tot_lo:.4g} and {_tot_hi:.4g}, {_tot_hi / _tot_lo:.2f}x) are not comparable "
              f"and every weight here is that arm's OWN SHARE. A raw difference would be mostly "
              f"the difference in totals." if rel else
              f"  The weight is on an absolute scale, so the two arms' values compare directly.")
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
    # WHAT THIS PARTICULAR CONTRAST CANNOT SEPARATE, on every panel it produces.
    _conf = contrast_confounds(design, lo_m, hi_m)
    _csent = confound_sentence(_conf, str(fac))

    # ---- 1. differential interactions, sender x receiver -------------------------------------
    # A DIFFERENCE OF PRESENCE IS NOT A DIFFERENCE OF MAGNITUDE, AND IT DOMINATED THE PANEL.
    # `pops` is the UNION of both arms, so a population with cells in one arm and none in the
    # other contributed its entire count as a "change" - the largest number on the figure, in
    # the strongest colour, for a population that was never scored on one side. Measured on a
    # real cohort: the four heaviest columns of the diet panel were populations missing from one
    # arm outright, and the panel read as a large, specific, directional effect.
    #
    # They are NOT dropped - a dropped row is invisible and a reader cannot tell it was ever
    # there. They are taken off the colour scale, hatched, and named, the way `panels.R2` asks.
    only_lo = {p for p in pops if p in _seen_lo and p not in _seen_hi}
    only_hi = {p for p in pops if p in _seen_hi and p not in _seen_lo}
    one_arm = sorted(only_lo | only_hi)
    _ix = {p: i for i, p in enumerate(pops)}
    unscored = np.zeros((len(pops), len(pops)), dtype=bool)
    for p in one_arm:
        unscored[_ix[p], :] = True
        unscored[:, _ix[p]] = True

    for what, A, B, unit in (("count", c_lo, c_hi, "significant interactions"),
                             ("strength", w_lo, w_hi, _wunit)):
        D = B - A
        if not np.any(D):
            continue
        fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.92), layout="constrained")
        Dm = np.where(unscored, np.nan, D)
        m = float(np.nanmax(np.abs(Dm))) if np.isfinite(Dm).any() else 0.0
        m = m or 1.0
        cmap = plt.get_cmap("RdBu_r").copy()
        cmap.set_bad("#F2F2F2")
        im = ax.imshow(Dm, cmap=cmap, vmin=-m, vmax=m)
        if unscored.any():
            ax.imshow(np.where(unscored, 1.0, np.nan), cmap="gray", vmin=0, vmax=1,
                      alpha=0.0)
            for i in range(len(pops)):
                for j in range(len(pops)):
                    if unscored[i, j]:
                        ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, fill=False,
                                                   hatch="////", lw=0.0,
                                                   edgecolor="#B0B0B0", zorder=2))
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
              (f"Change in {unit} from {lo_lv} to {hi_lv}, per sender-receiver pair, cells "
               f"pooled within each arm. {arm_n}."
               + (f" Hatched cells are NOT a difference." if one_arm else ""),
               _csent
               + (f"HATCHED AND OFF THE SCALE: every pair involving "
                f"{', '.join(short[_ix[p]] for p in one_arm)}, which "
                f"{'has' if len(one_arm) == 1 else 'have'} cells in only one of these two arms. "
                f"A difference there is a difference of PRESENCE, not of magnitude, and drawn on "
                f"this scale it would be the largest number on the panel for a population that "
                f"was never scored on one side. " if one_arm else "Every population has cells in "
                "both arms, so no pair is a comparison of presence. ")
               + f"Cells are pooled within each arm before inference, so this is a group-level "
                 f"comparison and needs no single sample to support one. Blue is lower in "
                 f"{hi_lv}, red higher, on a symmetric scale so both directions read at the same "
                 f"weight. Nothing here is a test: no interval is drawn because none was "
                 f"computed."
               + (_wnote if what == "strength" else
                  "  This panel counts EDGES, not weight, so no normalisation applies to it — "
                  "though a count still rises with an arm's total power.")))

    # ---- 2. information flow per group (rankNet, paired) -------------------------------------
    if group_col and group_col in e_lo.columns and group_col in e_hi.columns:
        fl = e_lo.groupby(group_col)[weight].sum()
        fh = e_hi.groupby(group_col)[weight].sum()
        if rel:
            fl, fh = 100.0 * fl / (fl.sum() or 1.0), 100.0 * fh / (fh.sum() or 1.0)
        # THE SAME RULE AS THE MATRIX ABOVE. A group scored in one arm and not the other is a
        # difference of presence; drawn as a paired bar with one bar at zero it reads as the
        # largest change on the panel. Kept, marked, and named - not dropped.
        _both = set(fl.index) & set(fh.index)
        keys = sorted(set(fl.index) | set(fh.index),
                      key=lambda k: -(float(fl.get(k, 0)) + float(fh.get(k, 0))))[:22]
        _one = [k for k in keys if k not in _both]
        if keys:
            a = np.array([float(fl.get(k, 0.0)) for k in keys])
            b = np.array([float(fh.get(k, 0.0)) for k in keys])
            y = np.arange(len(keys))[::-1]
            fig, ax = plt.subplots(figsize=(F.SINGLE, max(1.7, 0.15 * len(keys) + 0.6)),
                                   layout="constrained")
            ax.barh(y + 0.19, a, height=0.36, color=F.OKABE_ITO[0], label=str(lo_lv))
            ax.barh(y - 0.19, b, height=0.36, color=F.OKABE_ITO[1], label=str(hi_lv))
            for yi, k in zip(y, keys):
                if k in _one:
                    ax.axhspan(yi - 0.42, yi + 0.42, color="#B0B0B0", alpha=0.22, zorder=0)
            ax.set_yticks(y)
            ax.set_yticklabels([f"{k} †" if k in _one else k for k in keys], fontsize=5)
            ax.set_xlabel("information flow  (" + _wunit + ")")
            ax.legend(fontsize=5.5, frameon=False, loc="lower right")
            ax.tick_params(axis="y", length=0)
            for sp in ("top", "right", "left"):
                ax.spines[sp].set_visible(False)
            _save(fig, "C3_flow",
                  (f"Information flow per {group_col.replace('_', ' ')} in each arm, ranked by "
                   f"their combined total. {arm_n}."
                   + (" † is scored in one arm only." if _one else ""),
                   _csent
                   + (f"MARKED †, ON A SHADED ROW, AND NOT A MAGNITUDE: "
                    f"{', '.join(str(k) for k in _one)} — scored in one of these arms and not "
                    f"the other, so the empty bar is an absence and not a zero. " if _one else "")
                   + _wnote.strip() + " "
                   + f"Arms are pooled groups, not averages of samples. THE TWO ARMS DO NOT "
                     f"NECESSARILY CONTAIN THE SAME POPULATIONS — the earlier claim that they do "
                     f"was untrue whenever a population is missing from one — so a bar's HEIGHT "
                     f"carries the arm's total composition as well as the pathway, and the "
                     f"reliable comparison is the RANK. Bars are on the method's own probability "
                     f"scale and not comparable with any other figure."))

    # ---- 3. signalling role shift ------------------------------------------------------------
    o_lo, i_lo = w_lo.sum(1), w_lo.sum(0)
    o_hi, i_hi = w_hi.sum(1), w_hi.sum(0)
    if float(o_lo.sum() + o_hi.sum()) > 0:
        fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.92), layout="constrained")
        cmap = F.palette(list(pops))
        # MARKERS FIRST, ARROWS ON TOP, AND THE HEAD STOPPING SHORT OF THE MARKER. The first
        # version drew each arrow and then painted its destination marker over the arrowhead,
        # so DIRECTION - the entire content of the panel - was legible only from the legend.
        # AN ARROW FROM THE ORIGIN IS NOT A ROLE SHIFT. A population absent from one arm sits at
        # (0, 0) there, so the panel drew the longest arrow on the figure - from nowhere to its
        # full position - for a population that was never scored on one side. Same defect as the
        # difference matrix, in the one encoding where it looks most like a finding: a long
        # arrow reads as a large, directional change.
        for k, p in enumerate(pops):
            _one = p in one_arm
            ax.plot([o_lo[k]], [i_lo[k]], "o", ms=3.4,
                    color="none" if _one else cmap[p],
                    mec="#B0B0B0" if _one else "white", mew=.6, zorder=2)
            ax.plot([o_hi[k]], [i_hi[k]], "o", ms=5.6,
                    color="none" if _one else cmap[p],
                    mec="#B0B0B0" if _one else F.INK, mew=.6, zorder=2)
        for k, p in enumerate(pops):
            if p in one_arm:
                continue                # no arrow: there is no pair of positions to join
            ax.annotate("", xy=(o_hi[k], i_hi[k]), xytext=(o_lo[k], i_lo[k]),
                        arrowprops=dict(arrowstyle="-|>,head_width=.22,head_length=.42",
                                        lw=0.9, color=cmap[p], shrinkA=2, shrinkB=5,
                                        alpha=.95), zorder=3)
        # ALREADY ON SHARES where the weight is per-object: o_lo/i_lo are read off w_lo, which
        # was normalised above, so an arrow is a change in the population's SHARE of its arm.
        _live = [k for k, p in enumerate(pops) if p not in one_arm]
        lim = (float(max(max(o_lo[_live], default=0), max(o_hi[_live], default=0),
                         max(i_lo[_live], default=0), max(i_hi[_live], default=0)))
               * 1.12) or 1.0
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
               f"{arm_n}."
               + (" Hollow rings have no arrow." if one_arm else ""),
               _csent
               + (f"NO ARROW IS DRAWN for {', '.join(short[_ix[p]] for p in one_arm)}: absent from "
                f"one of these arms, so one end of the arrow would be the origin and its length "
                f"would be a presence, not a shift. Hollow rings mark where they sit in the arm "
                f"that has them. " if one_arm else "")
               + _wnote.strip() + " "
               + (f"Axes are therefore each population's SHARE of its arm, and an arrow is a "
                  f"change in the BALANCE between populations rather than in the arm's total. "
                  if rel else "")
               + f"The small marker is {lo_lv}, the arrowhead {hi_lv}. Above the dashed line a "
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
                     group_col=None, member_col=None, weight_scale="per_object"):
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

    # THE GRID MAXIMUM, COMPUTED BEFORE ANY PANEL IS DRAWN (panels.R1). Each arm was scaled to
    # its own maximum, so four arms of a factorial design drawn side by side all showed their
    # widest edge at full width whatever it was worth - the defect this project has measured at
    # 3.2x on a nine-panel grid and the one a design comparison is most damaged by.
    #
    # AND WHAT A SHARED SCALE DOES NOT LICENCE IS DECLARED, NOT ASSUMED (panels.R5). Where the
    # weight is normalised within each object - which is the usual case for a communication
    # probability - widths compare within a panel and RANK-ORDER across panels, nothing more.
    # The host cannot know which it is, so `unit_network.weight_scale` says: `per_object` (the
    # conservative default) or `absolute`.
    from . import network_panels as _NP
    scale, per_object = {}, str(weight_scale or "per_object") != "absolute"
    for e in pooled.values():
        _c, _w = _NP.aggregate(e, pops)
        if _w.sum() <= 0:
            continue
        scale["pair"] = max(scale.get("pair", 0.0), float(_w.max()))
        _m, _k, _x = _NP.strength_cut(_w, keep=0.90)
        scale["edge"] = max(scale.get("edge", 0.0),
                            float(_w[_m].max()) if _m.any() else float(_w.max()))
        scale["role"] = max(scale.get("role", 0.0),
                            float(max(_w.sum(1).max(), _w.sum(0).max())))
        if group_col and group_col in getattr(e, "columns", ()):
            scale["flow"] = max(scale.get("flow", 0.0),
                                float(e.groupby(group_col)["prob"].sum().max()))
    _scale_note = (
        "  ONE SCALE ACROSS EVERY ARM, so a width here is the same number as a width on any "
        "other arm's panel." + (
            "  The weight is normalised WITHIN each unit, so that comparison is a RANK ordering "
            "and not a magnitude." if per_object else
            "  The weight is on an absolute scale, so magnitudes compare directly."))

    made = []
    for label, e in sorted(pooled.items()):
        slug = "".join(ch if ch.isalnum() else "_" for ch in label).strip("_")
        got = []
        shim = _Shim(out_dir, prefix, slug, got, label=label,
                     members=_members(design, arms[label]))
        NP.circle(shim, e, pops, title=label, scale=scale, note=_scale_note)
        NP.chord(shim, e, pops, title=label)
        NP.matrix(shim, e, pops, title=label, scale=scale, note=_scale_note)
        NP.role_scatter(shim, e, pops, title=label, scale=scale, note=_scale_note)
        # DECLARED OR NOT DRAWN. Each of these returns False rather than raising when the
        # declaration names no grouping column, so a plugin that declares less gets fewer
        # panels and never a broken one.
        NP.flow_rank(shim, e, pops, group_col, title=label, scale=scale, note=_scale_note)
        NP.role_heatmap(shim, e, pops, group_col, title=label)
        NP.contribution(shim, e, pops, group_col, member_col, title=label)
        made += got
    return made



def interaction_specs(design, factors=None, technical=None):
    """[(fA, fB, lo_a, hi_a, lo_b, hi_b)] - every pair of crossed two-level factors.

    A FACTORIAL DESIGN'S HEADLINE IS THE INTERACTION AND NOTHING DREW IT. Six two-arm contrasts
    were drawn for a 2x2 - each factor marginally and each held at every level of the other - and
    a reader was left to compare two of them in their head. "Does the diet effect depend on age"
    is not the difference of two panels a page apart; it is one panel, and the marginal effect
    can be flat while both simple effects are large and opposite, which is the case a design like
    this most often exists to find.

    Only factors with EXACTLY TWO levels and all four cells populated qualify. A cell with no
    samples makes the interaction undefined rather than small, and drawing it would put a
    difference of presence on a magnitude axis.
    """
    from . import units as _U
    facs = factors or _U.biological_factors(
        design, technical=technical or _U.DEFAULT_TECHNICAL)
    lv = {}
    for row in design.values():
        for f, v in (row or {}).items():
            if f in facs:
                lv.setdefault(str(f), set()).add(str(v))
    two = sorted(f for f, s in lv.items() if len(s) == 2)
    out = []
    for i, fa in enumerate(two):
        for fb in two[i + 1:]:
            la, lb = sorted(lv[fa]), sorted(lv[fb])
            cells = {(a, b): _members(design, {fa: a, fb: b}) for a in la for b in lb}
            if all(cells[k] for k in cells):
                out.append((fa, fb, la[0], la[1], lb[0], lb[1]))
    return out


def draw_interaction(per_unit_edges, design, spec, out_dir, prefix, *, weight="prob",
                     group_col=None, min_edges=1, weight_scale="per_object"):
    """Does the effect of one factor depend on the level of the other? Returns [(fid, path, cap)].

    The effect of factor A within each level of factor B, one against the other. A point on the
    identity line responds to A the same way in both; a point off it is an interaction. The
    quadrants are the readable part: opposite sides of the diagonal means the direction itself
    flips, which a marginal contrast averages to nothing.
    """
    import numpy as np
    import matplotlib.pyplot as plt
    from pathlib import Path
    from . import figure as _F

    fa, fb, a0, a1, b0, b1 = spec
    cell = {}
    for a in (a0, a1):
        for b in (b0, b1):
            e = pool(per_unit_edges, _members(design, {fa: a, fb: b}))
            if e is None or len(e) < min_edges:
                return []
            cell[(a, b)] = e

    # THE ELEMENT IS THE COARSEST NAMEABLE ONE THE DECLARATION SUPPORTS. A named group is what a
    # reader can act on; an ordered population pair is what every declaration has.
    rel = str(weight_scale or "per_object") != "absolute"

    def _totals(e):
        if group_col and group_col in getattr(e, "columns", ()):
            t = e.groupby(group_col)[weight].sum()
        else:
            t = (e.assign(_k=e["source"].astype(str) + " → " + e["target"].astype(str))
                  .groupby("_k")[weight].sum())
        # SHARES WHERE THE WEIGHT IS PER-OBJECT, AND THIS PANEL IS WHERE IT DECIDED THE ANSWER.
        # On a real cohort the raw version put one pathway at -4.15 within one level and +0.16
        # within the other - an effect that DISAPPEARS - while the same pathway on shares was
        # -8.6 pp against +8.7 pp, an effect that REVERSES. The four arms' totals spanned 7.8 to
        # 30.4, so the raw version was largely reporting which arm was smallest.
        return (100.0 * t / (t.sum() or 1.0)).to_dict() if rel else t.to_dict()

    what = (group_col or "pathway").replace("_", " ") if group_col else "population pair"
    tot = {k: _totals(v) for k, v in cell.items()}
    # PRESENT IN ALL FOUR CELLS, or the point is a difference of presence on a magnitude axis.
    # What that costs is printed rather than absorbed.
    keys = set(tot[(a0, b0)])
    for k in tot:
        keys &= set(tot[k])
    seen = set().union(*[set(v) for v in tot.values()])
    keys = sorted(keys)
    if len(keys) < 3:
        return []

    dx = np.array([tot[(a1, b0)].get(k, 0.0) - tot[(a0, b0)].get(k, 0.0) for k in keys])
    dy = np.array([tot[(a1, b1)].get(k, 0.0) - tot[(a0, b1)].get(k, 0.0) for k in keys])
    off = np.abs(dy - dx)
    order = np.argsort(-off)

    # A SHARE IS COMPOSITIONAL, AND A LINEAR DIFFERENCE OF SHARES RANKS BY WHAT IS ABUNDANT.
    # This panel names the elements furthest from the line, so the ranking IS the claim - and on
    # a real cohort the ranking was not stable. Ranked by percentage points, the largest
    # interaction was a component holding 14-24% of every arm; ranked by log-ratio, that
    # component was mid-table and the largest was one holding under 3%, whose swing is small in
    # points and eight-fold in ratio. Both are correct arithmetic on the same numbers.
    #
    # Neither scale is safe alone: the linear one is dominated by abundant components and the
    # log one by near-zero components. So BOTH are computed and their top ranks compared, and
    # where they disagree the panel says so and declines to present its own ordering as the
    # finding. This is a disagreement to disclose, not to resolve by picking a favourite.
    _agree, _alt = None, []
    with np.errstate(divide="ignore", invalid="ignore"):
        _lg = {}
        for k in tot:
            v = np.array([max(tot[k].get(q, 0.0), 0.0) for q in keys], dtype=float)
            pos = v[v > 0]
            floor = float(pos.min()) / 2.0 if len(pos) else 1.0
            l = np.log2(np.where(v > 0, v, floor))
            _lg[k] = l - l.mean()                       # centred log-ratio
        lx = _lg[(a1, b0)] - _lg[(a0, b0)]
        ly = _lg[(a1, b1)] - _lg[(a0, b1)]
        loff = np.abs(ly - lx)
    _n_top = min(5, len(keys))
    _lin_top = [keys[i] for i in order[:_n_top]]
    _log_top = [keys[i] for i in np.argsort(-loff)[:_n_top]]
    _agree = len(set(_lin_top) & set(_log_top))
    _alt = [k for k in _log_top if k not in _lin_top]

    # AN INTERACTION IS THE DIFFERENCE OF TWO CONTRASTS, so it inherits what each of them
    # cannot separate — and it acquires one more: if the two strata sit in different batches, an
    # ADDITIVE batch effect cancels but a batch-BY-factor interaction does not, and the two are
    # indistinguishable. Audited on the samples this panel actually compares.
    _c0 = contrast_confounds(design, _members(design, {fa: a0, fb: b0}),
                             _members(design, {fa: a1, fb: b0}))
    _c1 = contrast_confounds(design, _members(design, {fa: a0, fb: b1}),
                             _members(design, {fa: a1, fb: b1}))
    _bad = sorted({f for c in (_c0, _c1) for f, st in c.items()
                   if st == "aliased" and f not in (fa, fb)})
    _strata = contrast_confounds(design, _members(design, {fb: b0}),
                                 _members(design, {fb: b1}))
    _sbad = sorted(f for f, st in _strata.items() if st == "aliased" and f not in (fa, fb))
    _isent = ""
    if _bad:
        _isent += (f"ALIASED WITH {', '.join(_bad).upper()} INSIDE AT LEAST ONE STRATUM, so the "
                   f"{fa} effect on that axis is equally a {', '.join(_bad)} effect. ")
    if _sbad:
        _isent += (f"AND THE TWO STRATA DIFFER IN {', '.join(_sbad).upper()}: an ADDITIVE effect "
                   f"of {', '.join(_sbad)} cancels in an interaction, but an interaction between "
                   f"{', '.join(_sbad)} and {fa} does not, and this design cannot tell it from "
                   f"the {fa}-by-{fb} interaction. ")
    if not _isent:
        _isent = (f"Every other design factor is balanced within both strata and between them, "
                  f"so this interaction is separable from all of them. ")

    lim = float(max(np.abs(dx).max(), np.abs(dy).max())) or 1.0
    fig, ax = plt.subplots(figsize=(_F.SINGLE, _F.SINGLE * 1.02), layout="constrained")
    # SYMMETRIC AND CENTRED ON ZERO IN BOTH DIRECTIONS. A signed quantity drawn on a data-derived
    # box puts "no change" somewhere off-centre and invites reading a quadrant boundary that is
    # not there.
    ax.axhline(0, color=_F.GREY, lw=0.6, zorder=0)
    ax.axvline(0, color=_F.GREY, lw=0.6, zorder=0)
    ax.plot([-lim, lim], [-lim, lim], color=_F.GREY, lw=0.7, ls="--", zorder=0)
    # A REVERSAL NEEDS TWO REAL EFFECTS, NOT TWO SIGNS. Marking every sign disagreement made an
    # element at (+0.05, -0.02) - noise on both axes - carry the same mark as one that genuinely
    # flips, so the panel claimed a reversal it could not support. Found by opening it: two of
    # the marked points sat on the origin.
    #
    # THE FLOOR IS DECLARED HERE, ABOVE THE RENDER THAT USES IT: an effect counts only if it
    # reaches a twentieth of the axis on BOTH sides. It is a readability threshold, not a test,
    # and the panel prints it so a reader sees what was and was not called a reversal.
    FLIP_FLOOR = 0.05
    _big = (np.abs(dx) >= FLIP_FLOOR * lim) & (np.abs(dy) >= FLIP_FLOOR * lim)
    _rev = _big & ((dx > 0) != (dy > 0))
    flips = int(_rev.sum())
    col = ["#D55E00" if r else "#0072B2" for r in _rev]
    ax.scatter(dx, dy, s=22, c=col, edgecolor="white", lw=0.35, zorder=2)
    texts = []
    for i in order[:8]:
        texts.append(ax.annotate(str(keys[i])[:22], (dx[i], dy[i]), fontsize=5.4,
                                 xytext=(3, 3), textcoords="offset points"))
    _F.spread_labels(ax, texts)
    ax.set_xlim(-1.08 * lim, 1.08 * lim)
    ax.set_ylim(-1.08 * lim, 1.08 * lim)
    ax.set_aspect("equal")
    # SHORT ENOUGH TO FIT THE COLUMN. The first version wrote the factor, both levels and the
    # unit into each axis label; at 85 mm the y-label was clipped at the top of the panel and
    # the x-label ran off the right edge, so the one thing a reader needs to know - which
    # stratum each axis is - was the part that did not render.
    _u = "Δ share, pp" if rel else "Δ weight"
    ax.set_xlabel(f"{_u}   ({a0}→{a1})   |   {fb} = {b0}", fontsize=7)
    ax.set_ylabel(f"{_u}   ({a0}→{a1})   |   {fb} = {b1}", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title(f"{fa} × {fb}", fontsize=8)
    fig.text(0.0, -0.006,
             f"{fa} x {fb} interaction   ·   4 arms, cells pooled within each",
             ha="left", va="top", fontsize=5.2, color="#5A5A5A", transform=fig.transFigure)

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    slug = f"{fa}__x__{fb}"
    path = Path(out_dir) / f"{prefix}_C5_interaction__{slug}.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    # THE LEAD IS BUDGETED. The visible caption is capped at 45 words and the host spends about
    # eight of them, so a lead written as three explanatory sentences fails the page it is on.
    cap = (f"Does {fa} act differently under each {fb}? One point per {what}, drawn by arm: its "
           f"{a0}→{a1} change within {fb} = {b0} against the same within {fb} = {b1}. Off the "
           f"dashed line, the response differs.",
           _isent
           + (f"THE RANKING IS NOT STABLE ACROSS SCALES and the labels are therefore NOT a "
              f"finding: ranked by log-ratio — the scale a compositional readout requires — the "
              f"largest interactions include {', '.join(map(str, _alt))}, which do not appear in "
              f"the top {_n_top} here. A linear difference of shares ranks by what is ABUNDANT; "
              f"a log-ratio ranks by what changes most in RATIO, and a small component can lead "
              f"one and not the other. Only the {_agree} element(s) leading BOTH should be read "
              f"as ordered. " if rel and _alt else
              f"The top {_n_top} are the same ranked by log-ratio, so the ordering is not an "
              f"artefact of the linear share scale. " if rel else "")
           + f"{len(keys)} of {len(seen)} {what}s are present in all four arms and drawn — the "
           f"rest are absent from at least one arm, where a difference would be a difference of "
           f"PRESENCE and not of magnitude. {flips} REVERSE DIRECTION — marked apart, and "
           f"counted only where the effect reaches {FLIP_FLOOR:.0%} of the axis on both sides, "
           f"so a sign disagreement between two near-zero values is not called a reversal. A "
           f"reversal is the case a marginal contrast averages to nothing. NOTHING HERE IS "
           f"TESTED: these are differences of sums, with no "
           f"interval and no significance marking, and the eight furthest from the line are "
           f"labelled by distance, not by evidence."
           + ("  THE WEIGHT IS NORMALISED WITHIN EACH UNIT, so both axes are each element's "
              "SHARE OF ITS ARM in percentage points, not a raw sum: the four arms' totals are "
              "not comparable and a raw difference between them would mostly report which arm "
              "is smallest." if rel else ""))
    return [(f"C5_interaction__{slug}", path, cap, f"{fa} × {fb}")]
