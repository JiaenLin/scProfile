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


from .units import membership as _membership          # noqa: E402


def pool(per_unit_edges, members, *, unit_members=None):
    """(edges, source) for one side of a contrast, PREFERRING THE ARM'S OWN FIT.

    THE HOST'S TABLE AND THE TOOL'S FIGURE WERE DESCRIBING DIFFERENT OBJECTS UNDER THE SAME
    WORDS. This concatenated the per-SAMPLE edge lists, so "total interaction strength" in the
    table was a sum over animals, while the tool's comparison figures beside it were drawn from
    the arm's own fit on POOLED cells. Measured on one cohort the two differed by a factor of
    2.5 - 57.5 against 23.3 for the same arm - and both appeared on the same page.

    They are different quantities, not one right and one wrong: a sum over animals weights each
    animal's network equally, and a pooled fit weights each CELL equally. But a reader cannot
    compare a number from one against a figure from the other, so where a unit exists whose
    members are exactly this side, its own edge list is used, and the source is returned so the
    table can say which it was.

    `unit_members` is {unit: set(samples)}, from `units.membership`.
    """
    import pandas as pd

    want = frozenset(str(m) for m in members)
    for u, mem in (unit_members or {}).items():
        if frozenset(str(x) for x in mem) == want and u in per_unit_edges:
            return per_unit_edges[u], f"unit '{u}' (one fit on the pooled cells)"
    frames = [per_unit_edges[u] for u in members if u in per_unit_edges]
    if not frames:
        return None, "no data"
    return (pd.concat(frames, ignore_index=True),
            f"{len(frames)} sample(s) summed (no unit pools this side)")


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


def arm_pairs(design, factors=None, technical=None, controls=None):
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
    from .design_panel import contrast_label as _label, control_for as _control

    out = []
    for f in facs:
        # THE CONTROL IS THE REFERENCE, and the difference is computed against it. This took
        # `sorted(levels[f])`, so the reference was alphabetical. Measured on a real two-factor
        # study, that put the TREATED level of both factors in the baseline position - backwards
        # on both, and invisibly, because a difference computed the wrong way round looks exactly
        # like one computed the right way: same figure, same colours, opposite meaning.
        a, _basis = _control(levels[f], declared=(controls or {}).get(f))
        b = next(x for x in sorted(levels[f]) if x != a)
        out.append((_label(f), f, a, b, {f: a}, {f: b}))
        for h in facs:
            if h == f:
                continue
            for lv in sorted(levels[h]):
                out.append((_label(f, {h: lv}), f, a, b,
                            {f: a, h: lv}, {f: b, h: lv}))
    return out


def control_basis(design, factors=None, technical=None, controls=None):
    """{factor: (control level, why)} - the reference chosen for each factor, and on what basis.

    Returned so a caller can PRINT the recommendation. A direction chosen silently is the defect
    this replaces; a direction chosen by convention and announced is not.
    """
    from .design_panel import control_for as _control
    from .units import DEFAULT_TECHNICAL

    tech = {t.lower() for t in (technical if technical is not None else DEFAULT_TECHNICAL)}
    levels = {}
    for row in design.values():
        for f, v in (row or {}).items():
            levels.setdefault(str(f), set()).add(str(v))
    facs = [f for f in sorted(levels) if len(levels[f]) == 2 and f.lower() not in tech]
    facs = [f for f in (factors or facs) if f in levels and len(levels[f]) == 2]
    return {f: _control(levels[f], declared=(controls or {}).get(f)) for f in facs}


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
    _um = _membership(design)
    e_lo, _ = pool(per_unit_edges, lo_m, unit_members=_um)
    e_hi, _ = pool(per_unit_edges, hi_m, unit_members=_um)
    if e_lo is None or e_hi is None or len(e_lo) < min_edges or len(e_hi) < min_edges:
        return []
    _seen_lo = set(e_lo["source"].astype(str)) | set(e_lo["target"].astype(str))
    _seen_hi = set(e_hi["source"].astype(str)) | set(e_hi["target"].astype(str))
    # THE INTERSECTION, DECIDED HERE, BEFORE ANY MATRIX IS BUILT. See `contrast_populations`.
    # A population with cells in one arm and none in the other cannot hold a difference, so it is
    # removed from the comparison at SOURCE rather than drawn and then masked in the plot.
    pops = sorted(_seen_lo & _seen_hi)
    one_arm = sorted((_seen_lo | _seen_hi) - (_seen_lo & _seen_hi))

    def _drop_short(names):
        """Short labels for populations that are NOT on the axis, so `short` cannot index them."""
        m = F.short_labels(list(names))
        return [m.get(n, n) for n in names]

    if len(pops) < 2:
        return []                # nothing the two arms share: there is no contrast to draw
    e_lo = e_lo[e_lo["source"].astype(str).isin(pops) & e_lo["target"].astype(str).isin(pops)]
    e_hi = e_hi[e_hi["source"].astype(str).isin(pops) & e_hi["target"].astype(str).isin(pops)]
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
        # THE STAMP, HERE TOO. `panels.R10` says a panel names on its face what it was drawn
        # from, and the per-arm panels have done so since the stamp was added - but the CONTRAST
        # panels save through this function rather than through the shim that stamps, so four
        # host kinds shipped with nothing on them. Found by opening one and noticing the foot of
        # the figure was empty where every neighbouring panel had a line.
        try:
            fig.text(0.0, -0.006,
                     f"{label}   ·   {len(lo_m)} vs {len(hi_m)} samples, cells pooled per arm",
                     ha="left", va="top", fontsize=5.2, color="#5A5A5A",
                     transform=fig.transFigure)
        except Exception:                                                 # noqa: BLE001
            pass
        p = Path(out_dir) / f"{prefix}_{fid}__{slug}.png"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        plt.close(fig)
        out.append((f"{fid}__{slug}", p, caption, label))

    arm_n = f"{lo_lv} (n={len(lo_m)}) vs {hi_lv} (n={len(hi_m)})"
    # WHAT THIS PARTICULAR CONTRAST CANNOT SEPARATE, on every panel it produces.
    _conf = contrast_confounds(design, lo_m, hi_m)
    _csent = confound_sentence(_conf, str(fac))

    # ---- 1. differential interactions, sender x receiver -------------------------------------
    # A DIFFERENCE OF PRESENCE IS NOT A DIFFERENCE OF MAGNITUDE, AND IT IS NO LONGER DRAWN AT ALL.
    #
    # This was first fixed by keeping the union and HATCHING the rows and columns that could not
    # hold a difference, so that a reader could see they were absent. That was honest and it was
    # still the wrong panel: on a real cohort it put two full rows and two full columns of hatch
    # through the middle of a 13x13 matrix - 48 of 169 cells, 28% of the figure - carrying no
    # comparison, and breaking every real block in half. A cell that cannot hold a difference
    # should not occupy the space where differences are read.
    #
    # So the removal happens at SOURCE, above: `pops` is the intersection and the edges are
    # filtered to it. What is kept is the FACT of the removal - `one_arm` names every population
    # taken out and the caption says so - because a removal is only cheap when the thing removed
    # is named. That is this project's standing rule and it is the half that must not be lost.

    for what, A, B, unit in (("count", c_lo, c_hi, "significant interactions"),
                             ("strength", w_lo, w_hi, _wunit)):
        D = B - A
        if not np.any(D):
            continue
        fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.92), layout="constrained")
        # NO MASK, BECAUSE THERE IS NOTHING LEFT TO MASK. Every cell on this panel holds a
        # difference between two arms that both contain the pair; the populations that did not
        # are gone from `pops` before the matrix was built.
        m = float(np.nanmax(np.abs(D))) if np.isfinite(D).any() else 0.0
        m = m or 1.0
        cmap = plt.get_cmap("RdBu_r").copy()
        im = ax.imshow(D, cmap=cmap, vmin=-m, vmax=m)
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
               + (f" {len(one_arm)} population(s) removed." if one_arm else ""),
               _csent
               + (f"REMOVED FROM THIS COMPARISON, not masked in it: "
                f"{', '.join(_drop_short(one_arm))}, which "
                f"{'has' if len(one_arm) == 1 else 'have'} cells in only one of these two arms. "
                f"A difference there would be a difference of PRESENCE, not of magnitude, so the "
                f"population is taken out before the matrix is built and every cell drawn here "
                f"holds a real comparison. " if one_arm else "Every population has cells in "
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
        # EVERY POPULATION HERE HAS BOTH ENDS. The hollow ring that used to mark a one-armed
        # population is gone with the population itself - it is removed at source now, so there
        # is no half-drawn state left to encode and no legend entry needed for one.
        for k, p in enumerate(pops):
            ax.plot([o_lo[k]], [i_lo[k]], "o", ms=3.4, color=cmap[p],
                    mec="white", mew=.6, zorder=2)
            ax.plot([o_hi[k]], [i_hi[k]], "o", ms=5.6, color=cmap[p],
                    mec=F.INK, mew=.6, zorder=2)
        for k, p in enumerate(pops):
            ax.annotate("", xy=(o_hi[k], i_hi[k]), xytext=(o_lo[k], i_lo[k]),
                        arrowprops=dict(arrowstyle="-|>,head_width=.22,head_length=.42",
                                        lw=0.9, color=cmap[p], shrinkA=2, shrinkB=5,
                                        alpha=.95), zorder=3)
        # ALREADY ON SHARES where the weight is per-object: o_lo/i_lo are read off w_lo, which
        # was normalised above, so an arrow is a change in the population's SHARE of its arm.
        _live = list(range(len(pops)))
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
               + (f" {len(one_arm)} population(s) removed." if one_arm else ""),
               _csent
               + (f"REMOVED FROM THIS COMPARISON: {', '.join(_drop_short(one_arm))} - absent from "
                f"one of these arms, so one end of the arrow would be the origin and its length "
                f"would be a presence, not a shift. They are taken out before the axes are "
                f"computed, so nothing on this panel is half-drawn. " if one_arm else "")
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


def contrast_populations(pooled):
    """The populations a contrast may be drawn on, and the ones removed from it BY NAME.

    THE SET IS THE INTERSECTION, NOT THE UNION, AND IT IS DECIDED HERE RATHER THAN IN THE PLOT.

    The union was drawn first, with the arms' missing populations hatched so a reader could see
    they were absent. That is honest and it is still the wrong panel: on a real cohort it put two
    fully hatched rows and two fully hatched columns into a 13x13 matrix - 48 of 169 cells, 28% of
    the panel - carrying no comparison at all, and it put them THROUGH the middle of the grid so
    every real block was broken in half. A cell that cannot hold a difference should not be drawn
    where a difference goes.

    The invariant the union existed to protect is kept: this is still ONE population set shared by
    every arm of the contrast, so two matrices side by side are indexed identically and a reader
    comparing cell to cell is comparing the same pair. An intersection is a shared axis too.

    What is NOT lost is the fact of the removal. A population dropped here is returned by name
    with the arms that lacked it, so the caller states it in the caption and the record - which is
    this project's standing rule: removal is cheap only when the thing removed is named.
    """
    per_arm = {}
    for label, e in pooled.items():
        per_arm[label] = (set(e["source"].astype(str)) | set(e["target"].astype(str)))
    if not per_arm:
        return [], {}
    keep = set.intersection(*per_arm.values())
    everywhere = set().union(*per_arm.values())
    dropped = {}
    for p in sorted(everywhere - keep):
        dropped[p] = sorted(label for label, seen in per_arm.items() if p not in seen)
    return sorted(keep), dropped


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
        e, _ = pool(per_unit_edges, _members(design, filt),
                    unit_members=_membership(design))
        if e is not None and len(e) >= min_edges:
            pooled[label] = e
    pops, dropped = contrast_populations(pooled)

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



def _ordered(levels, declared):
    """[baseline, perturbed] - the control level first, by declaration or by recommendation."""
    from .design_panel import control_for as _cf

    ctl = _cf(list(levels), declared=declared)[0]
    rest = [x for x in levels if x != ctl]
    return ([ctl] + rest) if ctl in levels else list(levels)


def interaction_specs(design, factors=None, technical=None, controls=None):
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
            # THE DECLARED CONTROL IS THE BASELINE, NOT THE ALPHABET. `sorted()` put whichever
            # level sorts first in the baseline position, so this panel and the wrapped tool's
            # own interaction panel - which does use the declared control - appeared on the same
            # page as mirror images of one quantity, with their axes swapped and their effect
            # signs flipped. Both were internally honest, which is why nothing errored.
            la = _ordered(sorted(lv[fa]), (controls or {}).get(fa))
            lb = _ordered(sorted(lv[fb]), (controls or {}).get(fb))
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
            e, _ = pool(per_unit_edges, _members(design, {fa: a, fb: b}),
                        unit_members=_membership(design))
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


def _unit_for(um, members):
    """The unit id whose membership is exactly this set of samples, or "".

    A CONTRAST SIDE IS A SET OF SAMPLES; a per-unit quantity is keyed by UNIT. This is the same
    resolution the native compare phase does, and it is here so a side's size can be looked up
    without any consumer re-deriving which unit pooled it.
    """
    want = frozenset(str(x) for x in (members or ()))
    for uid, mem in (um or {}).items():
        if frozenset(str(x) for x in (mem or ())) == want:
            return str(uid)
    return ""


def two_scale_table(per, design, pairs, *, group_col=None, weight="prob", unit_cells=None):
    """Every contrast's change per element, on BOTH scales, with whether the two agree.

    THE NUMBERS A RESULT SECTION QUOTES MUST COME FROM A FILE THE TOOL WROTE. These were computed
    by hand, in an ad-hoc script, and went straight into a manuscript's claims - which is exactly
    the thing this project's evidence rule forbids, because a number nobody can open is a number
    nobody can check.

    WHY BOTH SCALES. Where a method normalises within each object - the usual case for a
    communication probability - an element's SHARE of its arm and its RAW value answer different
    questions, and they can disagree in sign. Measured on a real cohort: five of six leading
    elements reversed direction between the two, because the arm totals differed 3.8-fold and a
    collapsing total makes whatever shrinks least appear to rise. A section that quotes one scale
    without the other is reporting an artefact of the denominator half the time.

    So the table carries both and marks the agreement. Nothing here decides which is right - that
    is the reader's - it only makes the disagreement impossible to miss.

    Returns a list of dicts, one per (contrast, element).
    """
    import pandas as pd

    _um = _membership(design)
    rows = []
    for sp in pairs:
        label, factor, lo_lv, hi_lv = sp[0], sp[1], sp[2], sp[3]
        lo_f, hi_f = (sp[4] if len(sp) > 4 else None), (sp[5] if len(sp) > 5 else None)
        m_lo, m_hi = _members(design, lo_f), _members(design, hi_f)
        e_lo, src_lo = pool(per, m_lo, unit_members=_um)
        e_hi, src_hi = pool(per, m_hi, unit_members=_um)
        # HOW BIG EACH SIDE'S FIT WAS. A total is not comparable between two arms of different
        # size without it, and a reader who is not given it will assume they were comparable.
        # THE UNIT, NOT ONLY THE LEVEL. `from`/`to` are factor LEVELS - two different contrasts
        # both name the SAME two levels - so any consumer resolving a side by level name reads
        # the MARGINAL unit even for a conditional contrast. That is the same mistake the native
        # compare phase documents having already made once, and it reached the composition table
        # a reader is told every comparison is read against.
        u_lo, u_hi = _unit_for(_um, m_lo), _unit_for(_um, m_hi)
        c_lo = (unit_cells or {}).get(u_lo)
        c_hi = (unit_cells or {}).get(u_hi)
        if e_lo is None or e_hi is None:
            continue
        gcol = group_col or "group"
        if gcol not in e_lo.columns or gcol not in e_hi.columns:
            continue
        # THE NUMBERS AND THE FIGURES MUST BE ABOUT THE SAME POPULATIONS.
        #
        # A wrapped tool that draws a differential restricts both arms to the elements they SHARE,
        # because an element only one arm has contributes its whole value as a difference. This
        # table did not, so every ratio a written section quoted was computed over the union while
        # every panel beside it was drawn over the intersection. Measured on a real cohort: one
        # contrast read 1.31x in the text and 1.02x - no effect at all - on the populations the
        # reader could actually see, because two populations present in one arm only carried a
        # fifth of its total.
        #
        # Nothing is hidden by this: the elements dropped here are exactly the ones reported as
        # PRESENT IN ONE ARM AND NOT THE OTHER, which is a result and is stated as one. What is
        # removed is the possibility of reading a presence as a change, in the number as well as
        # in the picture.
        _p_lo = set(e_lo["source"]) | set(e_lo["target"])
        _p_hi = set(e_hi["source"]) | set(e_hi["target"])
        _shared = _p_lo & _p_hi
        if not _shared:
            # NO SHARED ELEMENT IS NOT "NOTHING TO RESTRICT", it is nothing to compare. The guard
            # read `if _shared and ...`, so two arms with no population in common skipped the
            # restriction entirely and produced a ratio between two disjoint networks.
            print(f"  two-scale: {label} shares no population between its arms; "
                  f"no comparison is possible and no row is written")
            continue
        if _p_lo - _shared or _p_hi - _shared:
            e_lo = e_lo[e_lo["source"].isin(_shared) & e_lo["target"].isin(_shared)]
            e_hi = e_hi[e_hi["source"].isin(_shared) & e_hi["target"].isin(_shared)]
            if e_lo.empty or e_hi.empty:
                continue
        a = e_lo.groupby(gcol)[weight].sum()
        b = e_hi.groupby(gcol)[weight].sum()
        tot_a, tot_b = float(a.sum()), float(b.sum())
        if not (tot_a and tot_b):
            # AN ARM WITH NOTHING IN IT IS NOT A CONTRAST. Substituting 1.0 to avoid dividing by
            # zero wrote a fabricated total into the table, and the written section quoted it:
            # "Total is 3.00 against 1.00 in the reference arm". The share scale is undefined
            # here and the ratio is meaningless; the contrast is skipped and said to be skipped.
            print(f"  two-scale: {label} has an arm with no signal at all "
                  f"({lo_lv}={tot_a:g}, {hi_lv}={tot_b:g}); no row written for it")
            continue
        for g in sorted(set(a.index) | set(b.index)):
            ra, rb = float(a.get(g, 0.0)), float(b.get(g, 0.0))
            sa, sb = 100.0 * ra / tot_a, 100.0 * rb / tot_b
            d_raw, d_share = rb - ra, sb - sa
            rows.append({
                "contrast": label, "factor": factor, "from": lo_lv, "to": hi_lv,
                "element": g,
                "raw_from": ra, "raw_to": rb, "raw_delta": d_raw,
                "share_from": sa, "share_to": sb, "share_delta_pp": d_share,
                "total_from": tot_a, "total_to": tot_b,
                # THE DENOMINATOR, ON THE ROW. Carried rather than computed downstream, so the
                # per-observation scale in a written section and the one in a panel are the same
                # arithmetic on the same two numbers.
                "cells_from": c_lo, "cells_to": c_hi,
                "unit_from": u_lo, "unit_to": u_hi,
                # WHICH POPULATIONS THIS ROW WAS COMPUTED OVER, so a reader can see that the
                # number and the panel beside it are about the same set.
                "populations_compared": len(_shared),
                "populations_only_one_arm": len((_p_lo | _p_hi) - _shared),
                # WHICH OBJECT EACH SIDE CAME FROM. A number whose provenance is not on the row
                # cannot be compared against a figure, and this table sits beside figures drawn
                # from the arm's own fit.
                "from_source": src_lo, "to_source": src_hi,
                "scales_agree": bool(d_raw * d_share > 0) if d_raw and d_share else None,
            })
    return rows


def write_two_scale(per, design, pairs, out_path, *, group_col=None, weight="prob",
                    unit_cells=None):
    """Write `two_scale_table` as a CSV. Returns the path, or None when there is nothing to say."""
    import csv
    from pathlib import Path

    rows = two_scale_table(per, design, pairs, group_col=group_col, weight=weight,
                           unit_cells=unit_cells)
    if not rows:
        return None
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return out_path


def decompose_by_member(edges, sizes_arm, sizes_member, *, weight="prob"):
    """Split ONE arm's own fit over the members whose cells it was fitted on.

    THE PROBLEM THIS SOLVES. An arm's network is one fit on its members' pooled cells, and each
    member also has a fit of its own. Those are different fits, so a panel that draws the arm as
    a bar and its members as points is putting two incomparable quantities on one axis - and
    dividing both by cells does not reconcile them. Measured on a real cohort: the same 23,263
    cells gave 30.56 as one pooled fit and 84.28 as three separate fits summed, so every member
    point sat above every bar, in every arm, whatever the biology was.

    THE RULE. For an ordered pair of populations (i, j) the arm's own value is credited to member
    `a` by that member's share of the arm's cells in the two populations involved:

        W_a  =  sum_ij  V(i, j) * [ f_a(i) + f_a(j) ] / 2

    Half for sending, half for receiving. Two properties make it this rule rather than a taste:

      * IT PARTITIONS EXACTLY. Each population's shares sum to one across members, so the members'
        values sum to the arm's - nothing is created and nothing is lost.
      * THE BAR BECOMES THE CELL-WEIGHTED MEAN OF ITS OWN POINTS, because the values sum to the
        arm's total and the cells sum to the arm's cells. Points can then fall on both sides of
        the bar, which is what a reader already expects of them.

    IT IS A DERIVED QUANTITY AND MUST BE LABELLED ONE. The wrapped method reports nothing per
    member from a pooled fit; this is an attribution rule chosen here, applied to the method's own
    matrix. It does not replace the members' independent fits, which stay on the raw panel.

    `edges` is the arm's declared edge table (source, target, and `weight`). `sizes_arm` and
    `sizes_member` are {population: cells} for the arm and for one member. Returns
    `{"count": float, "weight": float}` - that member's share of the arm's edge count and total.
    """
    if edges is None or not len(edges) or not sizes_arm:
        return {"count": 0.0, "weight": 0.0}
    cols = getattr(edges, "columns", ())
    if "source" not in cols or "target" not in cols:
        return {"count": 0.0, "weight": 0.0}

    def _f(p):
        tot = float(sizes_arm.get(p, 0) or 0)
        return (float((sizes_member or {}).get(p, 0) or 0) / tot) if tot > 0 else 0.0

    src = edges["source"].astype(str).map(_f).to_numpy(dtype=float)
    tgt = edges["target"].astype(str).map(_f).to_numpy(dtype=float)
    credit = (src + tgt) / 2.0
    w = (edges[weight].astype(float).to_numpy() if weight in cols
         else __import__("numpy").ones(len(edges), dtype=float))
    return {"count": float(credit.sum()), "weight": float((credit * w).sum())}
