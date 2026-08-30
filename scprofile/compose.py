"""Compose the result section FROM THE RUN, so every run ships one.

THE HOST DOES NOT KNOW WHAT THE QUANTITY IS CALLED. The first version of this
module said "total interaction strength" and "cell-cell communication" - one
wrapped tool's vocabulary, written into the host, where it would have appeared in
the composed section of every plugin including ones that measure something else
entirely. A plugin names its own quantity through `unit_network.weight_name`;
without one the host says "weight", which is true of any of them.

THE PANEL WAS MADE A MECHANISM AND THE WRITING WAS NOT. Figures and the panel are produced by
the run; the section was authored by hand, which means a fresh checkout and a fresh run produce
no section at all, and the numbers in one came from a person reading tables and typing. That is
the failure this project names elsewhere - a scratch probe decides what to compute, never what to
write down - applied to the document itself.

So the section is COMPOSED from the run's own tables. Every sentence here is a template filled
from a measured value, and every value names the file it came from. Nothing is inferred, nothing
is rounded into a claim, and where a quantity is absent the sentence is not written rather than
softened.

WHAT THIS IS NOT. It is not a replacement for an author. It states what was measured, in the
design's own order, with the tool's own statistics - the part that must be reproducible. An
author who wants to say what it MEANS edits the result and passes it back with `--section`, and
that authored version wins. What the run guarantees is that a section exists, that its numbers
are traceable, and that it cannot silently disagree with the panel beside it.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


def _rows(path):
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except (OSError, ValueError):
        return []


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _two_scale(run, plugin):
    """{contrast: {...}} from the host's own two-scale table. General: the host wrote it."""
    p = Path(run) / "kernels" / plugin / "tables" / f"{plugin}_two_scale.csv"
    out = {}
    for r in _rows(p):
        c = out.setdefault(r["contrast"], {
            "from": r.get("from"), "to": r.get("to"),
            "total_from": _f(r.get("total_from")), "total_to": _f(r.get("total_to")),
            "from_source": r.get("from_source", ""), "to_source": r.get("to_source", ""),
            "elements": [], "only_from": [], "only_to": [], "disagree": 0, "n": 0})
        c["n"] += 1
        c["elements"].append((r["element"], _f(r.get("raw_delta"))))
        if _f(r.get("raw_to")) == 0:
            c["only_from"].append(r["element"])
        if _f(r.get("raw_from")) == 0:
            c["only_to"].append(r["element"])
        if str(r.get("scales_agree")) == "False":
            c["disagree"] += 1
    return out, p


def _significance(run, plugin, spec):
    """{contrast: {element: p}} from the table the PLUGIN declares carries its own test.

    The host does not know what test a wrapped tool runs or where it puts it, and must not
    guess. A plugin that ships a between-arm statistic names the file and the columns; one that
    ships none is simply reported without significance rather than with a substitute.
    """
    decl = ((spec or {}).get("report") or {}).get("comparison_stats") or {}
    rel, name_col, p_col = decl.get("table"), decl.get("element"), decl.get("pvalue")
    if not (rel and name_col and p_col):
        return {}, None
    out = {}
    base = Path(run) / "kernels" / plugin / "compare"
    if not base.is_dir():
        return {}, None
    for d in sorted(base.iterdir()):
        f = d / rel
        if not f.is_file():
            continue
        best = {}
        for r in _rows(f):
            n, pv = r.get(name_col), _f(r.get(p_col), 1.0)
            if n is not None:
                best[n] = min(best.get(n, 1.0), pv)
        out[d.name] = best
    return out, rel


def findings(run, plugin, spec=None):
    """Every measured fact the section states, per contrast. No prose, no interpretation."""
    ts, ts_path = _two_scale(run, plugin)
    sig, sig_rel = _significance(run, plugin, spec)
    out = {}
    for label, c in ts.items():
        el = sorted(c["elements"], key=lambda kv: kv[1])
        p = sig.get(label) or {}
        lead = [(n, p.get(n)) for n, _d in el if p.get(n, 1.0) < 0.05][:5] if p else \
               [(n, None) for n, _d in el[:5]]
        tf, tt = c["total_from"], c["total_to"]
        out[label] = {
            "reference": c["from"], "against": c["to"],
            "total_reference": tf, "total_against": tt,
            "ratio": (tt / tf) if tf else None,
            "log2": math.log2(tt / tf) if tf and tt else None,
            "n_elements": c["n"], "n_significant": sum(1 for v in p.values() if v < 0.05),
            "n_tested": len(p),
            "leading": lead,
            "only_reference": sorted(c["only_from"]), "only_against": sorted(c["only_to"]),
            "disagree": c["disagree"],
            "source_table": str(ts_path.relative_to(Path(run))) if ts_path.is_file() else "",
            "source_stats": sig_rel or "",
            "from_source": c["from_source"], "to_source": c["to_source"],
        }
    return out


def _n(x, digits=2):
    return f"{x:,.{digits}f}" if isinstance(x, float) else f"{x:,}"


def _p(v):
    if v is None:
        return ""
    return f"p = {v:.3g}" if v >= 1e-4 else f"p = {v:.1e}"


def _lead_phrase(lead):
    return ", ".join(f"**{n}**" + (f" ({_p(v)})" if v is not None else "") for n, v in lead)


def _weight_name(spec):
    """What the plugin calls the quantity it measures. `weight` when it does not say.

    A HOST THAT NAMES THE QUANTITY IS A HOST THAT KNOWS ONE TOOL. This is the plugin's word,
    read from its own declaration, so the same composer serves a plugin measuring something with
    no relation to the one it was written beside.
    """
    n = ((spec or {}).get("report") or {}).get("unit_network") or {}
    return str(n.get("weight_name") or "weight")


def section(run, plugin, spec=None, design=None, run_key=""):
    """The result section, as Markdown, composed from this run's tables.

    ONE SUBSECTION PER COMPARISON THE DESIGN SUPPORTS, in the design's own order and under the
    panel's own labels, so the two documents cannot disagree about what was compared.
    """
    from .design_panel import comparisons as _cmps

    f = findings(run, plugin, spec)
    if not f:
        return ""
    cmps = _cmps(design or {}) if design else []
    order = [c.get("label") for c in cmps if c.get("label") in f] or sorted(f)
    kind = {c.get("label"): str(c.get("kind", "")) for c in cmps}
    quest = {c.get("label"): str(c.get("question", "")) for c in cmps}
    alias = {}
    for c in cmps:
        for a in (c.get("aliased_with") or []):
            alias.setdefault(str(c.get("factor")), set()).add(str(a))

    W = _weight_name(spec)
    L = [f"# What this run measured across the design",
         "",
         f"Composed from run `{run_key or Path(run).name}`. Every number below is read from a "
         f"table in that run and the table is named where it is used; every difference is "
         f"measured against the contrast's reference arm.",
         ""]
    if alias:
        L += ["; ".join(f"In this design **{k}** varies together with "
                        f"{', '.join(sorted(v))} across all samples, so a difference along "
                        f"{k} is a difference along both" for k, v in sorted(alias.items()))
              + ".", ""]

    for lab in order:
        d = f[lab]
        L += [f"## {quest.get(lab) or lab}", ""]
        if d["ratio"]:
            L += [f"Measured against **{d['reference']}**, the **{d['against']}** arm carries "
                  f"**{_n(d['ratio'])}x** the total {W} "
                  f"({_n(d['total_against'])} against {_n(d['total_reference'])}), over "
                  f"{d['n_elements']} elements."]
        if d["n_tested"]:
            L += [f"**{d['n_significant']} of {d['n_tested']}** differ significantly between the "
                  f"arms by the method's own between-arm test."]
        if d["leading"]:
            L += [f"Leading the difference: {_lead_phrase(d['leading'])}."]
        if d["only_against"]:
            L += [f"**{len(d['only_against'])}** element(s) are detected in "
                  f"**{d['against']}** and not in {d['reference']}"
                  + (f" — {', '.join(d['only_against'])}"
                     if len(d["only_against"]) <= 12 else "")
                  + (f"; **{len(d['only_reference'])}** the other way" if d["only_reference"]
                     else ", and none the other way") + "."]
        elif d["only_reference"]:
            L += [f"**{len(d['only_reference'])}** element(s) are detected in "
                  f"{d['reference']} and not in {d['against']}, and none the other way."]
        if d["disagree"]:
            L += [f"{d['disagree']} of {d['n_elements']} elements move in opposite directions on "
                  f"the raw and share scales, because the two arms differ in total strength; "
                  f"both are in `{d['source_table']}`."]
        L += ["", f"*Source: `{d['source_table']}`"
                  + (f", significance from `{d['source_stats']}` per contrast" if d["source_stats"]
                     else "")
                  + f". Reference arm from {d['from_source'] or 'the run'}.*", ""]

    L += ["## How this section was produced", "",
          "It is composed by the tool from this run's own tables, so it exists for every run and "
          "its numbers cannot drift from the figures beside it. It states what was measured, in "
          "the design's order, under the same labels the figure panel uses. It does not "
          "interpret: an author who wants to say what the measurements mean edits this and "
          "passes it back with `--section`, and that version replaces this one.", ""]
    return "\n".join(L)


def claims(run, plugin, spec=None, design=None):
    """[(sentence, [figure paths])] - the composed findings, each bound to its figures.

    THE SECTION MUST CARRY THE SAME FIGURES AS THE PANEL. A section is rendered with the figures
    its CLAIMS cite, so prose alone renders a document with no pictures - which is what composing
    only text produced. The claims are made here, from the same measured facts as the sentences,
    and cite the same plates the panel places for that contrast, chosen by the plugin's own
    declared routes.

    Every sentence is a statement of what was measured. None interprets, and none is written
    where the measurement behind it is missing.
    """
    import json as _json

    f = findings(run, plugin, spec)
    if not f:
        return []
    W = _weight_name(spec)
    routes = ((spec or {}).get("report") or {}).get("provides_evidence") or {}
    declared = (spec or {}).get("native_plots") or {}
    try:
        placed = _json.loads((Path(run) / "report" / "panels.json")
                             .read_text(encoding="utf-8")).get(plugin) or {}
        native = placed.get("native") or []
    except Exception:                                                     # noqa: BLE001
        native = []
    from . import native as _NAT

    by = {}
    for x in native:
        fn = _NAT.function_for(declared, str(x.get("path") or ""))
        if fn:
            by.setdefault((str(x.get("label") or ""), fn), []).append(str(x.get("path")))

    def figs_for(label, needs):
        out = []
        for need in needs:
            for r in (routes.get(need) or []):
                r = str(r)
                if r.startswith("native:"):
                    out += by.get((label, r.split(":", 1)[1])) or []
        seen, uniq = set(), []
        for x in out:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return uniq

    made = []
    for label, d in sorted(f.items()):
        if d["ratio"]:
            cites = figs_for(label, ("who_changed", "what_carries_it"))
            if cites:
                made.append((
                    f"In the contrast {label}, the {d['against']} arm carries "
                    f"{_n(d['ratio'])} times the total {W} of the reference arm "
                    f"{d['reference']}, {_n(d['total_against'])} against "
                    f"{_n(d['total_reference'])}, over {d['n_elements']} elements.", cites))
        if d["n_tested"] and d["leading"]:
            cites = figs_for(label, ("what_carries_it", "specificity"))
            if cites:
                names = ", ".join(n for n, _v in d["leading"])
                made.append((
                    f"In the contrast {label}, {d['n_significant']} of {d['n_tested']} elements "
                    f"differ significantly between the arms by the method's own between-arm "
                    f"test, led by {names}.", cites))
        if d["only_against"] or d["only_reference"]:
            cites = figs_for(label, ("presence_or_magnitude", "what_carries_it"))
            if cites:
                made.append((
                    f"In the contrast {label}, {len(d['only_against'])} element(s) are detected "
                    f"in {d['against']} and not in {d['reference']}, and "
                    f"{len(d['only_reference'])} the other way.", cites))
        if d["n_tested"]:
            cites = figs_for(label, ("direction",))
            if cites:
                made.append((
                    f"In the contrast {label}, each population's outgoing and incoming {W} is "
                    f"measured against the reference arm "
                    f"{d['reference']}.", cites))
    return made
