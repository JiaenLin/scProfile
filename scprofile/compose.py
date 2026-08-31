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

#: THE FIRST LINE OF A COMPOSED SECTION. An authored section must never be
#: overwritten; a composed one must be REBUILT when the tool changes, or a rebuild
#: keeps a section written by older code beside figures drawn by newer. The marker
#: is how those two cases are told apart, and it is visible to a reader as well.
COMPOSED_MARK = "<!-- composed by scprofile; edit and pass back with --section -->"


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
            # THE DENOMINATOR EACH SIDE'S FIT USED, carried from the table rather than
            # recomputed, so a ratio in this text and a bar in a panel are the same arithmetic.
            "cells_from": _f(r.get("cells_from"), 0.0) or None,
            "cells_to": _f(r.get("cells_to"), 0.0) or None,
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
        # LEADING MEANS THE LARGEST CHANGE, in either direction. Sorted by the SIGNED delta this
        # returned the most negative - the elements highest in the reference arm - so the section
        # named five small movers as leading the difference while the largest changes in the
        # contrast went unmentioned. Sorted by magnitude it names what actually moved.
        el = sorted(c["elements"], key=lambda kv: -abs(kv[1]))
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
            # THE SAME RATIO ON A PER-OBSERVATION SCALE. A SECOND SCALE, NOT A CORRECTION: the
            # dependence of a total on the observations behind it is not linear, so dividing puts
            # the arithmetic on the page instead of removing it. Absent where the run did not
            # record a size, and then simply not written.
            "cells_reference": c["cells_from"], "cells_against": c["cells_to"],
            "ratio_per_cell": ((tt / c["cells_to"]) / (tf / c["cells_from"]))
            if (tf and tt and c["cells_from"] and c["cells_to"]) else None,
        }
    return out


def _n(x, digits=2):
    return f"{x:,.{digits}f}" if isinstance(x, float) else f"{x:,}"


def _p(v):
    """Render a p-value, and never print an exact zero as though it were a measurement.

    A test that returns 0 has not measured a vanishing probability; it has run out of resolution
    - a permutation p of 0 means the statistic was not beaten in any draw, and an underflowed
    analytic p means the same thing about the arithmetic. Printing `0.0e+00` states a certainty
    the test did not produce.
    """
    if v is None:
        return ""
    if v <= 0:
        return "p reported as 0, at the limit of what the test resolves"
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


#: WHICH EVIDENCE BACKS WHICH SENTENCE, in the order the section writes them.
#:
#: IT LIVES HERE ONCE BECAUSE THE PROSE AND THE FIGURE NUMBERS MUST AGREE. A citation that names
#: a different plate from the one printed under that number is worse than no citation at all: it
#: reads as a check a reader can make, and fails silently when they make it. Two copies of this
#: list - one for the writing, one for the numbering - is exactly how the two come apart, which
#: is the same disconnection between the panel and the paper, one level down.
#:
#: The keys are sentences; the values are needs from `evidence.NEEDS`, which are questions about
#: a comparison and know nothing about any tool. A plugin routes each need to its own function.
SENTENCE_EVIDENCE = (
    ("ratio", ("how_much_total", "who_changed", "what_carries_it")),
    ("tested", ("what_carries_it", "specificity")),
    ("presence", ("presence_or_magnitude", "what_carries_it")),
    ("direction", ("direction",)),
)


def _native_index(run, plugin, spec):
    """({(contrast, function): [path]}, {need: [route]}) - what this run actually drew.

    ONLY FILES THAT EXIST enter the index. Everything downstream - the numbering, the citations,
    the figures printed under them - is built from it, so filtering here is what guarantees the
    prose cannot cite a number that has no picture under it, without any consumer having to
    check separately and get it right.
    """
    routes = ((spec or {}).get("report") or {}).get("provides_evidence") or {}
    declared = (spec or {}).get("native_plots") or {}
    try:
        placed = json.loads((Path(run) / "report" / "panels.json")
                            .read_text(encoding="utf-8")).get(plugin) or {}
        native = placed.get("native") or []
    except (OSError, ValueError):
        native = []
    from . import native as _NAT

    by = {}
    for x in native:
        rel = str(x.get("path") or "")
        if not rel or not (Path(run) / rel).is_file():
            continue
        fn = _NAT.function_for(declared, rel)
        if fn:
            by.setdefault((str(x.get("label") or ""), fn), []).append(rel)
    # HOST PANELS RESOLVE THE SAME WAY THEY DO IN THE PANEL. A `host:` route was simply skipped
    # here, so a need the host answers - the census, the difference matrix, the per-unit totals -
    # produced a plate the panel placed and the paper never carried. That is the panel and the
    # paper resolving the same declaration differently, which is the disconnection between the
    # two documents this project has already fixed once at the level above.
    host = [x for grp in ("contrast", "arm", "cohort") for x in (placed.get(grp) or [])
            if str(x.get("path") or "") and (Path(run) / str(x.get("path"))).is_file()]
    return by, dict(routes), host


def _stems():
    """{panel kind: the id stem its figures carry} - the same inversion the panel uses."""
    from . import panels as _PN

    out = {}
    for kind, where in (_PN.IMPLEMENTED or {}).items():
        stem = str(where).split("\u2014")[-1].strip().split(",")[0].strip()
        if stem:
            out[kind] = stem
    return out


def _figs_for(by, routes, label, needs, host=()):
    """The plates this contrast drew for these needs, in route order, each once.

    NATIVE FIRST, HOST AS THE FALLBACK WITHIN A NEED - the same rule `paper.panel` applies, so
    the two documents choose the same plate for the same need rather than each choosing its own.
    """
    stems = _stems() if host else {}
    out = []
    for need in needs:
        got = []
        for r in (routes.get(need) or []):
            r = str(r)
            if r.startswith("native:"):
                fn = r.split(":", 1)[1]
                # AN UNLABELLED NATIVE PANEL ANSWERS EVERY CONTRAST. A figure drawn over all of
                # the design's arms at once is filed under none of them, so keying strictly on
                # the contrast name made it invisible to both documents - the same rule the
                # `host:` branch below already applies, and `paper.panel` now applies too.
                got += (by.get((label, fn)) or []) + (by.get(("", fn)) or [])
            elif r.startswith("host:") and not got:
                stem = stems.get(r.split(":", 1)[1])
                if not stem:
                    continue
                hits = [str(f.get("path")) for f in host
                        if str(f.get("id") or "").startswith(stem)
                        and (not f.get("label") or str(f.get("label")) == label)]
                if hits:
                    got.append(hits[0])
        out += got
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _controls(run):
    """{factor: control level} the run recorded, or `{}`.

    THE ORDER OF THE SECTION DEPENDS ON THEM. `comparisons()` puts the control stratum first,
    and without the declaration it falls back to alphabetical - which on a real study put the
    perturbed stratum ahead of the untreated one. The run already writes what was declared.
    """
    try:
        return dict(json.loads((Path(run) / "report.json")
                               .read_text(encoding="utf-8")).get("controls") or {})
    except (OSError, ValueError):
        return {}


def _order(f, design, controls=None):
    """The contrasts in the DESIGN's reading order, falling back to alphabetical.

    One definition, because the section, the claims and the figure numbers all walk it and a
    figure numbered in one order and printed in another is unreadable.
    """
    from .design_panel import comparisons as _cmps

    cmps = _cmps(design or {}, controls=controls) if design else []
    return [c.get("label") for c in cmps if c.get("label") in f] or sorted(f)


def figure_index(run, plugin, spec=None, design=None):
    """{figure path: number} - a stable figure number, in the order the section cites it.

    A PAPER NUMBERS ITS FIGURES AND THE TEXT POINTS AT THEM. Without this the composed section
    named measurements in prose while the figures sat underneath it in a block captioned with
    their FILENAMES, and nothing on the page said which picture any sentence was read off. A
    reader could not check a single number against a single plate.

    The number is a position in this run's own reading order - design order, and within a
    contrast the order the sentences are written - so it is stable across rebuilds of the same
    run and means nothing outside it. Numbers are contiguous because the index is built only
    from plates that exist.
    """
    f = findings(run, plugin, spec)
    if not f:
        return {}
    by, routes, host = _native_index(run, plugin, spec)
    idx, n = {}, 0
    for label in _order(f, design, _controls(run)):
        for _key, needs in SENTENCE_EVIDENCE:
            for path in _figs_for(by, routes, label, needs, host):
                if path not in idx:
                    n += 1
                    idx[path] = n
    return idx


def cite(idx, paths):
    """" (Figure 3, 4)" for these plates, or "" - the citation as it appears in a sentence."""
    ns = sorted({idx[p] for p in paths if p in idx})
    if not ns:
        return ""
    return (" (Figure " if len(ns) == 1 else " (Figures ") + ", ".join(str(i) for i in ns) + ")"


#: A population is NAMED as accounting for a contrast on its own when its share of the two arms
#: differs by at least this factor. Written here, before the run that tests it, so the threshold
#: is a decision and not a description of whichever elements it happened to catch.
#:
#: 3.0 is the same factor this project's own removal rule uses for "differential across the
#: design", chosen for consistency rather than tuned: a share that trebles between two arms is a
#: composition difference large enough to produce a difference in a sum of pairs by itself.
COMPOSITION_FOLD = 3.0

#: And a population is NAMED as thin when its arm holds fewer than this many observations of it.
#: 200 is twenty times the smallest floor a wrapped method here applies before it declines to
#: score a population at all; below it a per-population quantity is being read off very few
#: observations whatever the method says.
COMPOSITION_THIN = 200


def _composition(run, plugin, spec, units):
    """{unit: {element: n}} from the per-element size table the plugin NAMES, or {}.

    THE COMPOSITION IS WHY TWO TOTALS DIFFER MORE OFTEN THAN ANY PER-CELL CHANGE IS. A network
    total is a sum over ordered pairs of populations, so two arms holding different proportions
    of the same populations differ in the sum before anything a cell does differs. It was in no
    file the run wrote, so no reader could check it, and every difference read as behaviour.
    """
    net = ((spec or {}).get("report") or {}).get("unit_network") or {}
    rel, ecol, scol = (str(net.get("size_table") or ""),
                       str(net.get("size_table_element") or ""),
                       str(net.get("size_table_size") or ""))
    if not (rel and ecol and scol):
        return {}
    out = {}
    for u in units:
        got = {}
        for r in _rows(Path(run) / "kernels" / plugin / str(u) / rel):
            try:
                got[str(r.get(ecol))] = float(r.get(scol) or 0)
            except (TypeError, ValueError):
                continue
        if got:
            out[str(u)] = got
    return out


def _settings(run, plugin, units):
    """{parameter: value} this run resolved, or {} - read from a finished unit's own manifest.

    STATED ONCE, AT THE TOP. They are a property of the RUN, not of any comparison, and printing
    them under each contrast puts a constant where a finding belongs - the same failure as the
    aliasing line printed four times and the alignment sentence on a panel with no populations.
    """
    for u in units:
        try:
            cfg = json.loads((Path(run) / "kernels" / plugin / str(u) / "out.json")
                             .read_text(encoding="utf-8")).get("config") or {}
        except (OSError, ValueError):
            continue
        if cfg:
            return dict(cfg)
    return {}


def section(run, plugin, spec=None, design=None, run_key=""):
    """The result section, as Markdown, composed from this run's tables.

    IT LEADS WITH FINDINGS, NOT WITH APPARATUS. A section whose headings are the design's
    questions reads as a questionnaire; one whose headings are its answers reads as a result, and
    a reader who reads only the headings knows what was found. The heading is generated from the
    measurement, so it cannot disagree with the paragraph under it.

    Nothing here knows any biology. It says which contrast is largest, which elements moved most,
    what the method's own test said, and where every number came from. Saying what the movement
    MEANS is an author's job, and an authored section replaces this one.
    """
    from .design_panel import comparisons as _cmps

    f = findings(run, plugin, spec)
    if not f:
        return ""
    W = _weight_name(spec)
    ctl = _controls(run)
    cmps = _cmps(design or {}, controls=ctl) if design else []
    order = _order(f, design, ctl)
    # THE FIGURES, NUMBERED, so the sentences can point at them. Built from the same routes the
    # panel places by, so a number in this text and the plate printed under it are the same
    # object by construction rather than by anyone keeping two lists in step.
    by, routes, host = _native_index(run, plugin, spec)
    idx = figure_index(run, plugin, spec, design)

    def _c(label, *needs):
        return cite(idx, _figs_for(by, routes, label, needs, host))

    kind = {c.get("label"): str(c.get("kind", "")) for c in cmps}
    quest = {c.get("label"): str(c.get("question", "")) for c in cmps}
    alias = {}
    for c in cmps:
        for a in (c.get("aliased_with") or []):
            alias.setdefault(str(c.get("factor")), set()).add(str(a))

    ranked = [l for l in order if f[l]["ratio"]]
    by_size = sorted(ranked, key=lambda l: -f[l]["ratio"])
    L = [COMPOSED_MARK, "", "# What this run measured across the design", ""]

    # THE SUMMARY FIRST. A reader should not have to assemble the shape of the result from six
    # subsections; the run knows which contrast is largest and can say so.
    def _cell(x):
        # A CONTRAST LABEL CONTAINS A PIPE - `age | diet = chow` is how a simple effect is named
        # in this design and in every other - and a pipe is the column separator. Unescaped, the
        # four conditional rows carried six cells against a five-column header, so the table a
        # reader meets first rendered with its contrast names split in half. Escaped the standard
        # way; `_md` unescapes when it splits.
        return str(x).replace("|", "\\|")

    if ranked:
        big, small = f[by_size[0]], f[by_size[-1]]
        L += [f"Across {len(order)} comparison(s) the design supports, the largest difference in "
              f"total {W} is **{by_size[0]}** at **{_n(big['ratio'])}x**, and the smallest is "
              f"**{by_size[-1]}** at **{_n(small['ratio'])}x**. Every difference below is measured "
              f"against that contrast's reference arm, and every number is read from a table in "
              f"run `{run_key or Path(run).name}`.", ""]
        _has_pc = any(f[l].get("ratio_per_cell") for l in ranked)
        L += [f"| comparison | reference | {W} |"
              + (" per observation |" if _has_pc else "")
              + " elements differing | leading element |",
              "|---|---|---|" + ("---|" if _has_pc else "") + "---|---|"]
        for l in ranked:
            d = f[l]
            lead = d["leading"][0][0] if d["leading"] else "—"
            sig = f"{d['n_significant']} of {d['n_tested']}" if d["n_tested"] else "not tested"
            L += [f"| {_cell(l)} | {_cell(d['reference'])} | {_n(d['ratio'])}x |"
                  + ((f" {_n(d['ratio_per_cell'])}x |" if d.get("ratio_per_cell") else " — |")
                     if _has_pc else "")
                  + f" {sig} | {_cell(lead)} |"]
        L += [""]
    # THE COMPOSITION AND THE SETTINGS, ONCE. Both are properties of the RUN, so they go here and
    # not under each comparison. A constant printed under every finding is the failure this
    # section has already had twice - the aliasing line four times, the alignment sentence on a
    # panel with no populations - and it buries the sentence that actually describes the result.
    _arms = []
    for lab in order:
        for k in ("reference", "against"):
            v = str(f[lab].get(k) or "")
            if v and v not in _arms:
                _arms.append(v)
    comp = _composition(run, plugin, spec, _arms)
    if comp:
        pops = sorted({p for c in comp.values() for p in c})
        cols = [a for a in _arms if a in comp]
        L += ["### What each arm is made of", "",
              "A network total is a sum over ordered pairs of populations, so two arms holding "
              "different proportions of the same populations differ in that sum before anything "
              "a cell does differs. Every comparison below is read against this table.", "",
              "| population | " + " | ".join(_cell(c) for c in cols) + " |",
              "|---" * (len(cols) + 1) + "|"]
        tot = {c: sum(comp[c].values()) or 1.0 for c in cols}
        for pop in pops:
            L += ["| " + _cell(pop) + " | " + " | ".join(
                f"{100.0 * comp[c].get(pop, 0.0) / tot[c]:.2f}% "
                f"({int(comp[c].get(pop, 0.0)):,})" for c in cols) + " |"]
        L += ["| **total cells** | " + " | ".join(f"**{int(tot[c]):,}**" for c in cols) + " |", ""]
    # WHAT THIS RUN DECLINED TO COMPARE, ONCE. Every comparison here restricts itself to the
    # elements its arms share, and an element dropped for that reason is invisible in the result:
    # a panel drawn on nine populations and one drawn on eleven look identical. Named rather than
    # described, because a category cannot be argued with and a list can.
    try:
        from . import removals as _RM
        _rrows = _RM.read(run, plugin)
        _n_rm, _rm_names, _rm_diff = _RM.summarise(
            _rrows, design,
            json.loads((Path(run) / "report.json").read_text(encoding="utf-8"))
            .get("unit_members") or {})
    except Exception:                                                     # noqa: BLE001
        _n_rm, _rm_names, _rm_diff = 0, [], []
    if _n_rm:
        L += ["### What was not compared", "",
              f"{_n_rm} element(s) could not enter every comparison, because a difference cannot "
              f"be computed for something one side does not have: "
              + ", ".join(f"**{x}**" for x in _rm_names)
              + ". Each is present in its own arm's panels and absent only from the comparisons; "
                "the run records where each was found and where it was not.", ""]
        if _rm_diff:
            # RULE-ONE'S THIRD QUESTION, ANSWERED BY THE RUN. An element absent from every arm at
            # one level of a factor has had a technical property turned into an apparent
            # biological one, and that is not a judgement the person making the removal can make.
            #
            # GROUPED BY ELEMENT, because one element aligns with several factors whenever those
            # factors are aliased - and listing every pair separately produced eleven clauses in
            # one sentence, ending in a singular "its" after a list. The fact is about the
            # element; the factors it lines up with are its predicate.
            _byel = {}
            for _e, _f2, _lv in _rm_diff:
                _byel.setdefault(_e, []).append((_f2, _lv))
            L += ["Some of those absences line up with the design rather than falling across it. "
                  "Where they do, the absence must not be read as that arm having none of the "
                  "element: it is a property of which arms could be compared.", ""]
            for _e, _fl in sorted(_byel.items()):
                L += [f"- **{_e}** is absent from every arm with "
                      + ", ".join(f"`{f2} = {lv}`" for f2, lv in sorted(set(_fl))) + "."]
            L += [""]
            if any(len(set(v)) > 1 for v in _byel.values()):
                L += ["An element lining up with more than one factor at once is what aliasing "
                      "looks like from here: those factors do not vary independently in this "
                      "design, so which of them the absence belongs to cannot be told apart.", ""]
    _cfg = _settings(run, plugin, _arms)
    if _cfg:
        L += ["*Every unit was fitted with the same settings: "
              + ", ".join(f"`{k} = {v}`" for k, v in sorted(_cfg.items())) + ".*", ""]
    if alias:
        L += ["; ".join(f"In this design **{k}** varies together with {', '.join(sorted(v))} "
                        f"across all samples, so a difference along {k} is a difference along "
                        f"both" for k, v in sorted(alias.items())) + ".", ""]

    for lab in order:
        d = f[lab]
        # THE HEADING IS THE FINDING, generated from the measurement so the two cannot diverge.
        if d["ratio"]:
            head = (f"{d['against']} carries {_n(d['ratio'])}x the {W} of {d['reference']}"
                    + (f", in {lab}" if kind.get(lab) not in ("marginal", "") else ""))
        else:
            head = lab
        L += [f"## {head}", ""]
        if quest.get(lab):
            L += [f"*{quest[lab]}*", ""]
        if d["ratio"]:
            L += [f"Total {W} is {_n(d['total_against'])} in **{d['against']}** against "
                  f"{_n(d['total_reference'])} in the reference arm **{d['reference']}**, over "
                  f"{d['n_elements']} elements"
                  + _c(lab, "how_much_total", "who_changed") + "."]
            if d.get("ratio_per_cell"):
                # THE ARMS ARE NOT THE SAME SIZE AND THE READER IS TOLD SO HERE. Per contrast,
                # because the sizes are - unlike the inference settings, which are a property of
                # the run and are stated once at the top rather than under every comparison.
                L += [f"The two arms were fitted on {_n(d['cells_against'], 0)} and "
                      f"{_n(d['cells_reference'], 0)} cells, so on a per-cell scale the same "
                      f"comparison is **{_n(d['ratio_per_cell'])}x**."]
        if d["n_tested"]:
            L += [f"**{d['n_significant']} of {d['n_tested']}** elements differ significantly "
                  f"between the arms by the method's own between-arm test"
                  + _c(lab, "what_carries_it") + "."]
        if d["leading"]:
            L += [f"The largest changes are {_lead_phrase(d['leading'])}"
                  + _c(lab, "specificity") + "."]
        if d["only_against"]:
            L += [f"**{len(d['only_against'])}** element(s) are detected in "
                  f"**{d['against']}** and not in {d['reference']}"
                  + (f" — {', '.join(d['only_against'])}"
                     if len(d["only_against"]) <= 12 else "")
                  + (f"; **{len(d['only_reference'])}** the other way" if d["only_reference"]
                     else ", and none the other way")
                  + _c(lab, "presence_or_magnitude") + "."]
        elif d["only_reference"]:
            L += [f"**{len(d['only_reference'])}** element(s) are detected in {d['reference']} "
                  f"and not in {d['against']}, and none the other way"
                  + _c(lab, "presence_or_magnitude") + "."]
        # AND THE POPULATIONS THAT COULD ACCOUNT FOR THIS CONTRAST BY THEMSELVES. Named per
        # contrast because they differ per contrast; the thresholds are declared above this
        # function, before the run that tests them, rather than chosen from what they caught.
        if comp:
            ra, rb = str(d["reference"]), str(d["against"])
            ca, cb = comp.get(ra) or {}, comp.get(rb) or {}
            ta, tb = sum(ca.values()) or 1.0, sum(cb.values()) or 1.0
            flagged = []
            for pop in sorted(set(ca) | set(cb)):
                sa, sb = ca.get(pop, 0.0) / ta, cb.get(pop, 0.0) / tb
                if not (sa and sb):
                    continue
                fold = max(sa / sb, sb / sa)
                thin = min(ca.get(pop, 0.0), cb.get(pop, 0.0)) < COMPOSITION_THIN
                if fold >= COMPOSITION_FOLD or thin:
                    flagged.append((pop, fold, int(min(ca.get(pop, 0), cb.get(pop, 0)))))
            if flagged:
                L += ["*Read with care in this contrast: "
                      + "; ".join(f"**{p}** differs {_n(fl)}x in share between the arms "
                                  f"(as few as {mn:,} cells in one of them)"
                                  for p, fl, mn in flagged)
                      + ". A difference in how much of a population an arm holds produces a "
                        "difference in a sum over its pairs without anything per-cell changing.*"]
        _dir = _c(lab, "direction")
        if _dir:
            L += [f"Sending and receiving are shown separately: each population's outgoing and "
                  f"incoming {W} in **{d['against']}** against the reference arm "
                  f"**{d['reference']}**, over the same set of elements in both arms{_dir}."]
        if d["disagree"]:
            L += [f"{d['disagree']} of {d['n_elements']} elements move in opposite directions on "
                  f"the raw and share scales, because the arms differ in total {W}; both scales "
                  f"are in the table below."]
        L += ["", f"*Source: `{d['source_table']}`"
                  + (f"; significance from `{d['source_stats']}` in this contrast's directory"
                     if d["source_stats"] else "")
                  + f". Reference arm is {d['from_source'] or 'the run'}.*", ""]

    # THE INTERACTION, where the design supports one: a difference of two differences, computed
    # from the simple effects the run already measured. Reported as arithmetic and NOT as a test,
    # because the method provides none for it.
    simple = [c for c in cmps if str(c.get("kind")) == "simple" and c.get("label") in f]
    byfac = {}
    for c in simple:
        byfac.setdefault(str(c.get("factor")), []).append(c.get("label"))
    inter = [(fac, ls) for fac, ls in byfac.items() if len(ls) == 2]
    if inter:
        L += ["## Whether one factor's effect depends on the other", ""]
        for fac, ls in sorted(inter):
            a, b = f[ls[0]], f[ls[1]]
            if not (a["ratio"] and b["ratio"]):
                continue
            la, lb = math.log2(a["ratio"]), math.log2(b["ratio"])
            L += [f"The effect of **{fac}** is {_n(a['ratio'])}x in `{ls[0]}` and "
                  f"{_n(b['ratio'])}x in `{ls[1]}` — log2 {la:+.2f} against {lb:+.2f}, a "
                  f"difference of {la - lb:+.2f}."]
        L += ["", "*This is arithmetic on the simple effects above. The method provides no test "
                  "for a difference of two differences, so no significance is attached to it and "
                  "none should be read into it.*", ""]

    L += ["## How this section was produced", "",
          "Every number above was read from a table in this run, by the tool, so the text and "
          "the figures beside it cannot disagree and the section exists for every run. It is the "
          "measured skeleton of a result. **The reading of it — what the changes mean, and what "
          "they suggest — belongs in an authored version**, written against "
          "`.claude/skills/result-section`, which may state findings and hypotheses in the "
          "field's own language; pass it back with `--section` and it replaces this and is never "
          "overwritten.", ""]
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
    f = findings(run, plugin, spec)
    if not f:
        return []
    W = _weight_name(spec)
    by, routes, host = _native_index(run, plugin, spec)

    def figs_for(label, needs):
        return _figs_for(by, routes, label, needs, host)

    made = []
    for label in _order(f, design, _controls(run)):
        d = f[label]
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
