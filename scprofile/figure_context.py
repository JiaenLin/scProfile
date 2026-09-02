"""What every figure must be able to say about itself, computed once by the host.

WHY THIS EXISTS. An audit of 58 figure kinds across one run found three defects in almost every
one of them, and all three are the same defect wearing different clothes: **the panel does not
know what the run knows.**

1. **Colour was not stable across figure families.** One population was blue in every comparison
   panel and red in every per-unit panel of the same run, and a third population was red in the
   comparison set. Anyone reading the two families side by side misidentifies a population, and
   nothing on either panel warns them. The host knows the label set; the plugin was picking
   colours from whatever order its own data happened to arrive in.

2. **No panel named its unit, its size, or the direction of its contrast.** The host's own
   figures already carried `<arm> - <k> samples pooled - n = <cells>`; not one plugin panel
   carried the arm or the n, and on two differential panels the title's arm ordering contradicted
   the sign convention the colours implied. That is not a drawing bug - the plugin was never
   handed the sentence.

3. **Absence was handled four different ways in one run** - keyed grey, an undefined glyph, a
   silent blank, and the outright omission of the arm's top-ranked element with no note. Only the
   panels the host drew got it right, because only the host knew what had been dropped.

So this module computes those three things ONCE, from what the host already has, and puts them in
`in.json` under `figure_context`. A plugin stamps them; the reporter states them in the caption
whatever the plugin did. Neither has to re-derive them, and two panels cannot disagree.

NOTHING HERE IS ABOUT ANY PARTICULAR METHOD. The input is a list of label strings, a unit name and
a contrast; a plugin that measures something else entirely gets the same guarantees from the same
code, which is the test that this belongs in the host.
"""
from __future__ import annotations

import colorsys
import hashlib

#: The palette is generated, not listed, so it does not run out - a fixed list of N breaks at N+1
#: by REPEATING, which is the very defect this module exists to prevent arriving through its fix.
#:
#: THE HUE COMES FROM THE LABEL, NOT FROM ITS POSITION. The first version placed hues along the
#: golden-angle sequence indexed by rank in the sorted label set, and its own suite caught what
#: that means: drop one label and every label after it shifts rank, so every colour after the gap
#: changes. A panel drawn on 9 of 13 populations would have recoloured eight of them - the same
#: cross-panel mismatch, now produced by the mechanism meant to stop it.
#:
#: So the hue is a hash of the label string. A label's colour then depends on the label ALONE:
#: two panels, two plugins, two runs and any subset agree without having to agree on a set.
HUE_STEPS = 3600

#: Two labels can hash to neighbouring hues. Below this separation the later one (by sorted name)
#: is moved to the nearest free slot, which is deterministic and touches only the colliding pair -
#: so set-independence is exact everywhere except inside a collision, and a collision is visible
#: because `colour_map` is a function anyone can call twice.
MIN_HUE_GAP = 6

#: Saturation and lightness are held constant so hue alone carries identity - a panel that also
#: encodes magnitude in colour must use a different channel, and this leaves it free.
SAT, LIGHT = 0.62, 0.55


def colour_map(labels):
    """{label: '#rrggbb'} - deterministic, stable, and the same in every panel of a run.

    KEYED ON THE LABEL, NOT ON ITS POSITION IN SOMEBODY'S DATA FRAME. Two plugins, two figure
    families and two arms holding different subsets of the same populations all resolve one label
    to one colour, which is what makes panels comparable by eye. A label absent from one panel
    simply does not appear; it does not shift every colour after it, which is what an
    order-based palette does and why the families disagreed.

    The map does not depend on which OTHER labels exist, either: a colour is a function of its
    own label. The one exception is a hash collision, where the later of the two by sorted name is
    nudged to the nearest free hue - so a subset that breaks a collision can move one colour, and
    only that one. Everything else is invariant.
    """
    names = sorted({str(x) for x in (labels or []) if str(x).strip()})
    taken, slots = set(), {}
    for name in names:
        h = int(hashlib.sha1(name.encode("utf-8")).hexdigest()[:8], 16) % HUE_STEPS
        # NEAREST FREE SLOT, searched outward, so the shift is the smallest one that separates
        # them and does not cascade down the rest of the set.
        if any(abs(h - t) % HUE_STEPS < MIN_HUE_GAP for t in taken):
            for d in range(1, HUE_STEPS):
                for cand in ((h + d) % HUE_STEPS, (h - d) % HUE_STEPS):
                    if not any(abs(cand - t) % HUE_STEPS < MIN_HUE_GAP for t in taken):
                        h = cand
                        break
                else:
                    continue
                break
        taken.add(h)
        slots[name] = h
    out = {}
    for name, h in slots.items():
        r, g, b = colorsys.hls_to_rgb(h / HUE_STEPS, LIGHT, SAT)
        out[name] = "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
    return out


def stamp(unit=None, unit_kind="", members=(), n_cells=None, contrast=None):
    """One line naming what the panel is OF. Empty string when the host knows nothing.

    THE DIRECTION IS PART OF THE IDENTITY OF A DIFFERENCE. `A vs. B` in a title with `B - A` in
    the data is not a cosmetic mismatch: the audit found two panels where the title's ordering and
    the sign convention disagreed, and no reader could recover which way the difference ran. So a
    contrast is never rendered as `A vs B`; it is rendered as an explicit subtraction against a
    named reference.
    """
    bits = []
    if contrast:
        ref = str(contrast.get("reference") or "").strip()
        agn = str(contrast.get("against") or "").strip()
        lab = str(contrast.get("label") or "").strip()
        if ref and agn:
            bits.append(f"{agn} MINUS {ref}  (reference: {ref})")
        elif lab:
            bits.append(lab)
    elif unit:
        bits.append(str(unit) + (f" · {unit_kind}" if unit_kind else ""))
    mem = [str(m) for m in (members or []) if str(m).strip()]
    if len(mem) > 1:
        bits.append(f"{len(mem)} samples pooled")
    if n_cells:
        try:
            bits.append(f"n = {int(n_cells):,} cells")
        except (TypeError, ValueError):
            pass
    return "  ·  ".join(bits)


def absence(all_labels, drawn_labels):
    """{'absent': [...], 'note': '...'} - what a panel does NOT show, by name.

    A COUNT IS NOT A NAME. "11 of 13 populations" tells a reader something is missing and not what,
    and the audit found one panel that dropped the arm's TOP-RANKED element with no note at all. A
    list of names is checkable; a count is not.

    Silence here is deliberate: with nothing missing the note is empty, so a panel does not carry
    a reassurance nobody needs. A gate that fires when everything is correct gets switched off.
    """
    have = {str(x) for x in (drawn_labels or [])}
    gone = sorted({str(x) for x in (all_labels or [])} - have)
    if not gone:
        return {"absent": [], "note": ""}
    return {"absent": gone,
            "note": ("NOT SHOWN, and not zero: " + ", ".join(gone)
                     + ". These are absent from this panel; the panel says nothing about them.")}


def build(labels=(), unit=None, unit_kind="", members=(), n_cells=None, contrast=None,
          drawn_labels=None):
    """The whole block, as it goes into `in.json` under `figure_context`.

    A plugin reads what it can use and ignores the rest; the reporter reads the same block for the
    caption. One source, so the image and its caption cannot say different things - which they did,
    in a run where the panel named an arm the caption did not.
    """
    labs = sorted({str(x) for x in (labels or []) if str(x).strip()})
    ctx = {"labels": labs,
           "colours": colour_map(labs),
           "stamp": stamp(unit, unit_kind, members, n_cells, contrast),
           "unit": None if unit is None else str(unit),
           "contrast": dict(contrast) if contrast else None}
    if drawn_labels is not None:
        ctx.update(absence(labs, drawn_labels))
    # A DIGEST OF THE MAP, so a panel drawn under a different label set is detectable rather than
    # merely different. Two runs whose colour maps differ are two runs whose figures must not be
    # laid side by side, and this is the one value that says so in a glance.
    ctx["colour_key"] = hashlib.sha1(
        "|".join(f"{k}={v}" for k, v in sorted(ctx["colours"].items())).encode()).hexdigest()[:12]
    return ctx
