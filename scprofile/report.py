"""The documents: one per kernel, plus an index that names what did NOT run.

THE INDEX IS THE POINT. A profiling tool with seven optional kernels can produce a report that
looks complete while three of them never ran, and a reader has no way to see the difference
between "no regulons were found" and "SCENIC was never installed". So the index lists EVERY known
kernel with one of three states - ran, skipped with a reason, not installed - and never omits one.

Each kernel gets its own page ending in its own limits, because they differ. Velocity's caveats
are not SCENIC's, and a shared block at the end of one long document is a block readers skip.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path

# THE SAME PALETTE THE PLUGINS DRAW WITH. Imported, never copied: a second list of the same
# sixteen colours is how a convention drifts, and `figure.py` imports no plotting library at
# module scope, so the reporter takes on no dependency by asking it.
from .figure import CATEGORY_COLOURS

CSS = """
:root{--bg:#fff;--fg:#191919;--mut:#5b5b5b;--line:#e6e4e0;--card:#faf9f7;--warn:#fff8ec;
--warnl:#b06d12;--bad:#fdeeed;--badl:#a8403c;--good:#eef7ee;--goodl:#3f7d43}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#16181c;--fg:#e8e6e3;
--mut:#a3a09b;--line:#2d3138;--card:#1d2025;--warn:#2a2115;--warnl:#e0a44a;--bad:#2a1717;
--badl:#e07b76;--good:#16241a;--goodl:#7fbf85}}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);margin:0;padding:2.5rem 1.5rem 5rem;
font:16px/1.65 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto}
h1{font-size:1.9rem;margin:0 0 .35rem}h2{font-size:1.2rem;margin:2.6rem 0 .8rem;
padding-bottom:.35rem;border-bottom:1px solid var(--line)}
h3{font-size:1rem;margin:1.6rem 0 .5rem}
.sub{color:var(--mut);font-size:.9rem}.lede{font-size:1.03rem}
.warn,.bad,.good{padding:1rem 1.2rem;margin:1.2rem 0;border-radius:0 5px 5px 0;font-size:.93rem}
.warn{background:var(--warn);border-left:3px solid var(--warnl)}
.bad{background:var(--bad);border-left:3px solid var(--badl)}
.good{background:var(--good);border-left:3px solid var(--goodl)}
.wrap{overflow-x:auto;margin:1rem 0}
table{border-collapse:collapse;width:100%;font-size:.87rem;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--line);padding:.45rem .55rem;text-align:left;
vertical-align:top}
th{background:var(--card);font-size:.7rem;text-transform:uppercase;color:var(--mut)}
code{font-family:ui-monospace,Consolas,monospace;font-size:.85em}
a{color:inherit}
figcaption{margin-top:.7rem;font-size:.86rem;line-height:1.5}
.nosrc{color:#b45309;font-weight:600}
figure{margin:1.6rem 0;padding:1rem;background:var(--card);border:1px solid var(--line);
border-radius:8px}img{max-width:100%;height:auto;display:block;border-radius:4px;background:#fff}
ul{margin:.4rem 0 .4rem 1.1rem;padding:0}li{margin:.25rem 0}
.pill.warn{background:#fef3c7;color:#92400e}
.pill{display:inline-block;padding:.1rem .45rem;border-radius:3px;background:var(--card);
border:1px solid var(--line);font-size:.72rem;color:var(--mut)}
"""


def _e(v):
    return html.escape("" if v is None else str(v), quote=True)


def _page(title, body):
    now = datetime.now(timezone.utc).astimezone()
    return (f'<!doctype html><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{_e(title)}</title><style>{CSS}</style><main>{body}"
            f'<p class="sub">generated {now:%Y-%m-%d %H:%M %Z}</p></main>')


def _limits(items):
    if not items:
        return ('<div class="warn"><b>This kernel declared no limits.</b> That is unusual and '
                'worth questioning: almost every method here rests on an assumption a reader '
                'should be told about.</div>')
    return ('<div class="warn"><b>What this cannot show</b><ul>'
            + "".join(f"<li>{_e(x)}</li>" for x in items) + "</ul></div>")


#: What each `shows` group is called on the page, and the sentence under the heading. The
#: reporter's whole knowledge of what a figure is: three groups, no ids, no plugin names.
_GROUPS = (
    ("diagnostic", "Did the method's assumptions hold here?",
     "Read these before the result. They are the checks on whether this method could answer "
     "the question on this data at all; a result under a failed check is a number, not an "
     "answer."),
    ("result", "What it found",
     "The answer the method was run for. Its limits are at the foot of this page."),
    ("comparison", "The same question, answered another way",
     "Drawn against a second method. Agreement is evidence; disagreement is a finding. A panel "
     "missing here usually means the other half of the pair did not run."),
)


#: A caption's first sentences, up to this many words. The rest goes behind a disclosure.
CAPTION_LEAD_WORDS = 32


#: A heading is a heading: this many words, then the rest goes under it.
HEADING_LEAD_WORDS = 14


def _split_caption(text, limit=None):
    """(what a reader sees, what is one click away). Split on a sentence, never mid-clause."""
    limit = CAPTION_LEAD_WORDS if limit is None else int(limit)
    t = " ".join(str(text).split())
    if len(t.split()) <= limit:
        return t, ""
    lead, used = [], 0
    for sent in re.split(r"(?<=[.!?]) ", t):
        if used and used + len(sent.split()) > limit:
            break
        lead.append(sent)
        used += len(sent.split())
    head = " ".join(lead)
    if not head or len(head.split()) > limit:
        # A SINGLE SENTENCE CAN EXCEED THE CAP, and splitting on sentences alone then returns a
        # lead longer than the lead is allowed to be. Break at the last clause boundary that
        # fits; failing that, at the word. The remainder still goes behind the disclosure, so
        # the split is where a reader stops, never where the text ends.
        words = t.split()
        cut = limit
        for i in range(cut, max(4, cut // 2), -1):
            if words[i - 1].endswith((",", ";", ":", "-")):
                cut = i
                break
        head = " ".join(words[:cut]).rstrip(",;:-") + " ..."
        return head, " ".join(words[cut:])
    return head, t[len(head):].strip()


def _panel(f, index, *, note=""):
    """One drawn panel: the image, its caption, its vector and its source data."""
    rel = f"../{f['path']}"
    extra = []
    if f.get("vector"):
        extra.append(f'<a href="../{_e(f["vector"])}">vector (PDF)</a>')
    if f.get("source"):
        extra.append(f'<a href="../{_e(f["source"])}">source data</a>')
    else:
        extra.append('<span class="nosrc">no source data</span>')
    unit = f.get("unit")
    head = f"Figure {index}." + (f" <code>{_e(unit)}</code>" if unit else "")
    # THE CLAIM VISIBLE, THE REST ONE CLICK AWAY. Captions were 65% of every word on the page -
    # 13,172 of 20,545 on the worst - so the figures were surrounded by more text than a reader
    # will read, and the sentence that says what the panel SHOWS was buried in it. Nothing is
    # thrown away: the remainder is still on the page, behind a disclosure.
    lead, rest = _split_caption(f.get("caption") or "")
    return (f'<figure><img src="{_e(rel)}" alt="{_e(f.get("id") or f["path"])}">'
            f'<figcaption><b>{head}</b> {_e(lead)}'
            + (f'<details><summary class="sub">more</summary>{_e(rest)}</details>' if rest else "")
            + (f'<br><span class="sub">{_e(note)}</span>' if note else "")
            + f'<br><span class="sub">{" &middot; ".join(extra)}</span></figcaption></figure>')


def _absent_panel(decl, kind):
    """A declared panel that was not drawn. Never a gap.

    A gap on a page reads as a figure nobody thought was needed, which is the one reading that is
    never true here: the plugin declared it, so somebody thought it was needed and it is not
    there. `required` decides whether that is a property of the data or a defect in the run.
    """
    why = str(decl.get("when_absent") or "").strip()
    if decl.get("required", True):
        body = ("<b>NOT PRODUCED</b> — this plugin declares this panel as required and did not "
                "emit it. The method ran; the panel did not. That is a defect in the plugin, not "
                "a property of these data.")
        cls = "bad"
    else:
        body = "<b>not produced</b> — " + (why or "the plugin gave no reason, which is itself a "
                                                 "gap in its declaration")
        cls = "warn"
    return (f'<div class="{cls}"><p class="sub">{_e(kind)} · '
            f'{_e(decl.get("question") or "")}</p>{body}</div>')


def _figure_section(figs, spec):
    """The figure half of a kernel page, laid out by what each panel is FOR.

    TWO SHAPES, AND THE SECOND IS NOT A FALLBACK TO BE REMOVED. A plugin that declares a `report`
    block gets its panels ordered diagnostic-first, each under the question it answers, with every
    declared panel it did not draw stated in place. A plugin that declares none gets what this
    page has always done - the panels it emitted, in the order it emitted them - because the
    declaration has to be worth adding for a plugin written outside this repository, and a
    reporter that renders nothing without one is a reporter nobody's plugin survives.
    """
    from .declare import figures_in

    declared = figures_in(spec)
    if not declared:
        if not figs:
            return ""
        panels = "".join(_panel(f, i + 1) for i, f in enumerate(figs))
        return ("<h2>Figures</h2><p class='sub'>In the order this plugin emitted them: it "
                "declares no <code>report</code> block, so nothing here can say what a panel is "
                "for, or that one is missing.</p>" + panels)

    # BY ID, AND A LIST PER ID. A per-unit plugin emits the same panel once per unit, and folding
    # them to one would report nine units' work as one figure and silently pick whichever came
    # back first.
    by_id = {}
    for f in figs:
        by_id.setdefault(str(f.get("id") or ""), []).append(f)

    out, n = [], 0
    for kind, title, blurb in _GROUPS:
        here = [d for d in declared if d.get("shows") == kind]
        if not here:
            continue
        body = []
        for d in here:
            got = by_id.get(str(d.get("id") or ""), [])
            # A HEADING IS A HEADING. The whole question went into the <h3>, and the questions
            # are sentences - several hundred words of them on a page, in the largest type on
            # it. The lead names what the panel answers; the rest is still there, under it.
            _q_lead, _q_rest = _split_caption(d.get("question") or d.get("id") or "",
                                              limit=HEADING_LEAD_WORDS)
            q = (f'<h3>{_e(_q_lead)}</h3>'
                 + (f"<details><summary class='sub'>in full</summary>{_e(_q_rest)}</details>"
                    if _q_rest else ""))
            if not got:
                body.append(q + _absent_panel(d, kind))
                continue
            body.append(q)
            for f in got:
                n += 1
                body.append(_panel(f, n))
        out.append(f"<h2>{_e(title)}</h2><p class='sub'>{_e(blurb)}</p>" + "".join(body))

    # EMITTED AND NOT DECLARED. Rendered, always - a panel that was drawn must appear, or the
    # page hides work the run did - but named as undeclared, because an undeclared panel is one
    # no question describes and no `cannot_show` was written against.
    extra = [f for f in figs if str(f.get("id") or "") not in {str(d.get("id")) for d in declared}]
    if extra:
        out.append("<h2>Drawn, and not declared</h2><p class='sub'>These panels were emitted and "
                   "the plugin's <code>report</code> block does not list them, so nothing states "
                   "what they are for.</p>"
                   + "".join(_panel(f, n + i + 1) for i, f in enumerate(extra)))

    if declared:
        out.append("<p class='sub'>Every panel is written as a raster preview and as a vector PDF "
                   "with live text, at journal column width. The source data link opens the table "
                   "the panel was drawn from.</p>")
    return "".join(out)

def _constraint_block(constraint, binds):
    """The upstream prohibition, ON THE PAGE THAT MAKES THE CLAIM IT BOUNDS.

    A constraint on the index bounds the index. Measured on the run that motivated this: the
    constraint reached `README.md` and `index.html` and none of the nine plugin pages - and the
    page it most needed to reach carried, as its headline and with nothing beside it, exactly the
    kind of claim the constraint forbids. Nobody quotes a cover page.

    It is placed ABOVE the numbers rather than under them. A limit printed after a result is read
    after the result has been believed, and the panels below are what a reader screenshots.
    """
    if not (constraint and binds):
        return ""
    # THE PROHIBITION VISIBLE, THE WHOLE TEXT KEPT. Printing the entire constraint on every
    # bound page put ~250 words of it in front of a reader six times over, and the sentence that
    # actually forbids something was inside them. The prohibition is what binds; the rest is
    # context, and it is one click away rather than gone.
    text = str(constraint)
    forbid = [ln.strip() for ln in re.split(r"(?<=[.])\s+", " ".join(text.split()))
              if "must NOT" in ln]
    return ('<div class="bad"><b>The upstream constraint binds this page</b> on '
            + _e(", ".join(binds)) + '. '
            + _e(forbid[0] if forbid else text[:300])
            + '<details><summary class="sub">the constraint in full</summary>'
            + "".join(f"<p>{_e(line.strip())}</p>"
                      for line in text.splitlines() if line.strip())
            + "</details></div>")


def _num(v):
    """A number a reader can read. `:,.4g` renders 38,895 as `3.89e+04`, which is a count.

    Counts are the commonest thing a plugin reports per unit, and scientific notation on a
    count is not a rounding choice - it makes two numbers a reader is meant to compare look
    like different kinds of thing.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f != f or f in (float("inf"), float("-inf")):
        return "-"
    if abs(f) >= 1e12 or (f and abs(f) < 1e-4):
        return f"{f:.4g}"
    if abs(f - round(f)) < 1e-9:
        return f"{round(f):,d}"
    # `.4g` counts SIGNIFICANT digits, so 23543.5 comes out as 2.354e+04 - the same defect one
    # decimal place further on. Above 1, fix the decimals; below it, significant digits are what
    # a reader wants.
    return f"{f:,.2f}" if abs(f) >= 1 else f"{f:.4g}"


def _svg_strip(values, labels, *, width=560, height=96):
    """One axis, one dot per unit, drawn as inline SVG.

    Inline because the reporter has no plotting library and must not acquire one: a comparison
    that only exists when an optional dependency is installed is a comparison that will be
    missing from somebody's report. Everything here is arithmetic and string formatting.
    """
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pad, top = 46, 30
    w = width - 2 * pad
    pts, ticks = [], []
    for v, lab in zip(values, labels):
        x = pad + w * (v - lo) / span
        pts.append(f'<circle cx="{x:.1f}" cy="{top}" r="5" fill="currentColor" '
                   f'fill-opacity="0.55"><title>{_e(lab)}: {_num(v)}</title></circle>')
    for v in (lo, (lo + hi) / 2, hi):
        x = pad + w * (v - lo) / span
        ticks.append(f'<line x1="{x:.1f}" y1="{top + 12}" x2="{x:.1f}" y2="{top + 18}" '
                     f'stroke="currentColor" stroke-opacity="0.4"/>'
                     f'<text x="{x:.1f}" y="{top + 32}" font-size="11" text-anchor="middle" '
                     f'fill="currentColor" fill-opacity="0.7">{_num(v)}</text>')
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
            f'style="max-width:{width}px">'
            f'<line x1="{pad}" y1="{top + 12}" x2="{width - pad}" y2="{top + 12}" '
            f'stroke="currentColor" stroke-opacity="0.25"/>'
            + "".join(ticks) + "".join(pts) + "</svg>")


def _units_by_arm(units, design, declared, *, out_dir=None, name=""):
    """THE PER-UNIT NUMBERS, GROUPED BY ARM. The comparison the study exists to make.

    A per-unit plugin already records one comparable number per unit, and the units already sit
    on one axis. What was missing was the join: the reporter had the numbers and the arm NAMES
    and no way to put a unit in an arm, so three plugins could show ten dots and not say which
    four were aged.

    Median per arm, and the units behind it. NOT a test - two arms of five samples compared by
    eye is a description, and the page says so.
    """
    if not design:
        return ""
    named = {str(d.get("id")): d for d in (declared or []) if isinstance(d, dict)}
    # ALIASED FACTORS ARE ONE COMPARISON, NOT TWO. Two factors that split the samples identically
    # produced two panels with byte-identical numbers and no note - a reader with two panels
    # showing the same difference under two names has, on the page, two pieces of evidence for
    # one. The per-CELL path already collapsed them; this one did not, so the same cohort got
    # the honest treatment on four pages and the duplicated one on three.
    from .design_panel import aliased as _aliased
    _alias = _aliased(design)
    factors, _seen = [], set()
    for f in sorted({f for r in design.values() for f in r}):
        if f in _seen:
            continue
        factors.append(f)
        _seen.add(f)
        _seen.update(_alias.get(f) or [])
    keys = []
    for u in units:
        for k in (u.get("metrics") or {}):
            if k not in keys:
                keys.append(k)
    blocks, rows = [], []
    for k in keys:
        vals = {str(u.get("unit")): float(u["metrics"][k]) for u in units
                if isinstance((u.get("metrics") or {}).get(k), (int, float))}
        if len(vals) < 2:
            continue
        for fac in factors:
            arms = {}
            for unit, v in vals.items():
                lvl = (design.get(unit) or {}).get(fac)
                if lvl:
                    arms.setdefault(str(lvl), []).append(v)
            if len(arms) < 2 or any(len(v) < 2 for v in arms.values()):
                continue
            recs = []
            for lvl in sorted(arms):
                xs = sorted(arms[lvl])
                m = xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs)//2 - 1] + xs[len(xs)//2]) / 2
                recs.append({"level": lvl, "n": len(xs), "median": m,
                             "q1": xs[0], "q3": xs[-1], "min": xs[0], "max": xs[-1]})
            q = (named.get(k) or {}).get("question") or ""
            # DRAWN UP TO THE CAP, TABULATED IN FULL. Two metrics across four factors is eight
            # panels of one shape, and the page budget is twelve for everything. Every pair is
            # still in the table below, so capping the drawing loses no number.
            # EVERY PAIR, NOT THE ALPHABETICALLY FIRST THREE. The cap took whichever factors
            # sorted first and named nothing it dropped, so on this cohort `diet` - the factor
            # with the LARGEST split on two of the three plugins that use this path, 3.0x on
            # one - was the one comparison with no picture, and a second measure got no panel
            # at all. A page budget is a reason to spend one figure on many strips, not a
            # reason to hide the largest effect in the study.
            _ali = _alias.get(fac) or []
            blocks.append(f'<div class="armpair"><p class="sub"><b><code>{_e(k)}</code> by '
                          f'<code>{_e(fac)}</code></b> — per arm, one point per sample. '
                          f'{len(recs)} arms.'
                          + (' Identical split to '
                             + ", ".join("<code>" + _e(x) + "</code>" for x in _ali)
                             + ' — one panel, not two; which of them a difference belongs to '
                               'is not something this data can say.' if _ali else "")
                          + '</p>' + _arm_rows_numeric(recs) + "</div>")
            lo, hi = recs[0], recs[-1]
            rows.append(f"<tr><td><code>{_e(k)}</code></td><td><code>{_e(fac)}</code></td>"
                        f"<td>{_e(lo['level'])} {_num(lo['median'])}</td>"
                        f"<td>{_e(hi['level'])} {_num(hi['median'])}</td>"
                        f"<td class='sub'>{_e(q[:70])}</td></tr>")
    if not rows:
        return ""
    # A REAL FIGURE WHERE ONE CAN BE DRAWN. The strips below carry the numbers, but they are
    # hand-rolled SVG: not exportable as vector art for a manuscript, and a bar of quartiles
    # hides the very difference it is drawn to show. `design_panel` draws one point per SAMPLE
    # with the comparison summarised beside it, which is the idiom this kind of claim is held
    # to (Lord et al., J Cell Biol 2020; Ho et al., Nat Methods 2019). It falls back to the
    # strips when the drawing cannot be made at all: a report that renders beats one that
    # refuses over a figure, and the reporter must never REQUIRE a plotting stack.
    per_sample = {str(u.get("unit")): {k: float(v)
                                       for k, v in (u.get("metrics") or {}).items()
                                       if isinstance(v, (int, float))}
                  for u in units if u.get("unit") is not None}
    if out_dir and per_sample:
        try:
            from . import design_panel
            rel = f"kernels/{name}/figures/{name}_across_design.png"
            dest = Path(out_dir) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            n_cmp = design_panel.draw(per_sample, design, dest)
            if n_cmp:
                dupes = sorted({a for f in _alias for a in (_alias.get(f) or [])})
                return ("<h2>Across the design</h2><figure>"
                        f'<img src="../{rel}" alt="{_e(name)} across the design">'
                        f"<figcaption>Every measure this plugin recorded per sample, against "
                        f"every factor of the design — {n_cmp} comparison(s). One point per "
                        f"SAMPLE, bar is the median; n is in each panel because the sample is "
                        f"the unit of replication, not the cell. Right: each comparison as a "
                        f"standardised difference with a 95% interval, filled where the "
                        f"interval excludes zero."
                        + (" A factor marked * splits the samples identically to "
                           + ", ".join("<code>" + _e(d) + "</code>" for d in dupes)
                           + ", so it is drawn once." if dupes else "")
                        + " A DESCRIPTION, not a test.</figcaption></figure>"
                        + "<div class='wrap'><table><tr><th>metric</th><th>factor</th>"
                          "<th>arm</th><th>arm</th><th></th></tr>"
                        + "".join(rows) + "</table></div>")
        except Exception:                                                 # noqa: BLE001
            pass
    return ("<h2>Across the design</h2><p class='sub'>This plugin's per-unit numbers grouped by "
            "arm. A DESCRIPTION, not a test: n is the number of samples in each arm.</p>"
            + "".join(blocks)
            + "<div class='wrap'><table><tr><th>metric</th><th>factor</th><th>arm</th>"
              "<th>arm</th><th></th></tr>" + "".join(rows) + "</table></div>")


def _across_units(units, declared):
    """THE UNITS ON ONE AXIS. Drawn by the host, once, for every per-unit plugin.

    A per-unit plugin runs separately on each unit and its page is that many single-unit
    reports in sequence. Every panel on it is true, and the one question a cohort study asks -
    do the units agree? - is answered nowhere, because the numbers never share an axis.
    Measured on a real cohort: one plugin's per-unit interaction count ran from 8,194 to
    38,895, a 4.7-fold range across the units of a single tissue, and a reader taking the strongest
    interaction off the first unit's panel had nothing on the page to warn them.

    So the host renders it rather than each plugin: one implementation, no per-plugin drawing
    code to drift, and it appears for a plugin written next year without that plugin doing
    anything but calling `ctx.metric`.

    The spread is DESCRIBED, never judged. A fold-range is a fact about the cohort; whether it
    is too large is a question about the biology and the reader's, not this function's.
    """
    named = {str(d.get("id")): d for d in (declared or []) if isinstance(d, dict)}
    rows, blocks = [], []
    keys = []
    for u in units:
        for k in (u.get("metrics") or {}):
            if k not in keys:
                keys.append(k)
    for k in keys:
        pairs = [(str(u.get("unit")), float(u["metrics"][k])) for u in units
                 if isinstance((u.get("metrics") or {}).get(k), (int, float))]
        if len(pairs) < 2:
            continue
        pairs.sort(key=lambda t: t[1])
        labs = [a for a, _ in pairs]
        vals = [b for _, b in pairs]
        n = len(vals)
        med = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        fold = (vals[-1] / vals[0]) if vals[0] > 0 else float("inf")
        q = (named.get(k) or {}).get("question") or ""
        rows.append(f"<tr><td><code>{_e(k)}</code></td><td>{_num(vals[0])}</td>"
                    f"<td>{_num(med)}</td><td>{_num(vals[-1])}</td>"
                    f"<td>{'-' if fold != fold or fold == float('inf') else f'{fold:,.2f}x'}</td>"
                    f"<td class='sub'>{_e(labs[0])} lowest, {_e(labs[-1])} highest</td></tr>")
        blocks.append(f'<figure><figcaption><b>{_e(k)}</b> — {n} units, '
                      f'{_num(vals[0])} to {_num(vals[-1])}'
                      + (f', {fold:,.2f}x' if fold == fold and fold != float("inf") else "")
                      + '.</figcaption>' + _svg_strip(vals, labs) + "</figure>")
    # A DECLARED METRIC THAT ARRIVED FOR NO UNIT IS NAMED, not omitted. The same rule the
    # figures already follow: an absent panel and a panel nobody wanted look identical on a
    # page, and only one of them means the run is incomplete.
    absent = sorted(set(named) - set(keys))
    gap = ("" if not absent else
           '<div class="bad"><b>Declared and not recorded:</b> '
           + ", ".join(f"<code>{_e(a)}</code>" for a in absent)
           + ". The comparison this plugin said it would make is missing from this page, and "
             "its absence is a fact about the run rather than about the cohort.</div>")
    if not rows:
        return ('<h2>Across units</h2>' + gap + '<div class="bad">This plugin ran once per unit and '
                'recorded no comparable number, so its units cannot be put on one axis. Every '
                'panel below describes a single unit, and whether the units agree is not '
                'answered anywhere on this page.</div>')
    return ("<h2>Across units</h2>" + gap + "<p class='sub'>The only place the units are "
            "compared; every panel below describes one.</p>"
            + "".join(blocks)
            + "<div class='wrap'><table><tr><th>metric</th><th>min</th><th>median</th>"
              "<th>max</th><th>range</th><th>extremes</th></tr>"
            + "".join(rows) + "</table></div>")


BY_ARM_PANEL_CAP = 3


def _arm_rows_numeric(arms, *, width=560, row=22):
    """One row per arm: the min-max span, the interquartile box and the median.

    A box is drawn rather than a mean and an error bar because a mean over cells says almost
    nothing about a distribution that is usually skewed and often bimodal, and because an error
    bar over CELLS is a standard error of the wrong n - the unit of replication is the sample,
    not the cell, and nothing here should imply otherwise. Quantiles claim only what they are.
    """
    lo = min(a["min"] for a in arms)
    hi = max(a["max"] for a in arms)
    span = (hi - lo) or 1.0
    pad, lab = 30, 110
    w = width - pad - lab
    h = row * len(arms) + 26
    def x(v):
        return lab + w * (v - lo) / span
    out = []
    for i, a in enumerate(arms):
        y = 12 + row * i
        out.append(
            f'<text x="0" y="{y + 4}" font-size="11" fill="currentColor">'
            f'{_e(a["level"])} <tspan fill-opacity="0.55">n={a["n"]:,}</tspan></text>'
            f'<line x1="{x(a["min"]):.1f}" y1="{y}" x2="{x(a["max"]):.1f}" y2="{y}" '
            f'stroke="currentColor" stroke-opacity="0.3"/>'
            f'<rect x="{x(a["q1"]):.1f}" y="{y - 5}" width="{max(1.0, x(a["q3"]) - x(a["q1"])):.1f}" '
            f'height="10" fill="currentColor" fill-opacity="0.18"/>'
            f'<line x1="{x(a["median"]):.1f}" y1="{y - 6}" x2="{x(a["median"]):.1f}" y2="{y + 6}" '
            f'stroke="currentColor" stroke-width="2"><title>median {_num(a["median"])}</title>'
            f'</line>')
    out.append(f'<text x="{lab}" y="{h - 4}" font-size="10" fill="currentColor" '
               f'fill-opacity="0.6">{_num(lo)}</text>'
               f'<text x="{width - pad}" y="{h - 4}" font-size="10" text-anchor="end" '
               f'fill="currentColor" fill-opacity="0.6">{_num(hi)}</text>')
    return (f'<svg viewBox="0 0 {width} {h}" width="100%" role="img" '
            f'style="max-width:{width}px">' + "".join(out) + "</svg>")


def _arm_rows_categorical(arms, categories, *, width=560, row=22):
    """One stacked bar per arm: the composition, as shares that sum to one."""
    cats = [c for c in (categories or []) if any(c in (a.get("share") or {}) for a in arms)]
    pad, lab = 30, 110
    w = width - pad - lab
    h = row * len(arms) + 30
    out = []
    for i, a in enumerate(arms):
        y = 12 + row * i
        cx = lab
        out.append(f'<text x="0" y="{y + 8}" font-size="11" fill="currentColor">'
                   f'{_e(a["level"])} <tspan fill-opacity="0.55">n={a["n"]:,}</tspan></text>')
        for j, c in enumerate(cats):
            frac = float((a.get("share") or {}).get(c, 0.0))
            bw = w * frac
            if bw <= 0:
                continue
            out.append(f'<rect x="{cx:.1f}" y="{y}" width="{bw:.1f}" height="12" '
                       f'fill="{CATEGORY_COLOURS[j % len(CATEGORY_COLOURS)]}">'
                       f'<title>{_e(c)}: {frac * 100:.1f}%</title></rect>')
            cx += bw
    key = " ".join(
        f'<tspan fill="{CATEGORY_COLOURS[j % len(CATEGORY_COLOURS)]}">&#9632;</tspan> {_e(c)}'
        for j, c in enumerate(cats))
    out.append(f'<text x="{lab}" y="{h - 6}" font-size="10" fill="currentColor">{key}</text>')
    return (f'<svg viewBox="0 0 {width} {h}" width="100%" role="img" '
            f'style="max-width:{width}px">' + "".join(out) + "</svg>")


def _by_arm_block(by_arm, *, aware):
    """THE DESIGN, ON A PAGE THAT DID NOT TEST IT. Description only.

    Of nine plugins on the cohort that motivated this, the two that test the design reported
    across it and the other seven reported per population and per cell - never once splitting a
    result by the factor the study exists to ask about. Two of the seven DECLARED that they
    report per arm and between them had fourteen panels, none of them about an arm.

    Rendered by the host from the per-cell columns a plugin already writes, so a plugin gets
    this by producing its output and writing no code for it.

    IT IS NOT A TEST AND MUST NOT BE READ AS ONE. The unit of replication in these designs is
    the sample, not the cell; a difference visible here is a difference between groups of cells
    and becomes a claim about the design only through a model that says so - which is what the
    plugins that test the design are for, and what the upstream constraint may forbid outright.
    """
    if not by_arm:
        if aware:
            return ('<h2>Across the design</h2><div class="bad">This plugin declares that it '
                    'reports per arm and produced no per-cell column the host could split by '
                    'one, so its page says nothing about the design it claims to describe.'
                    '</div>')
        return ""
    # EVERY PAIR, IN ONE FIGURE. This drew ONE `<figure>` per (column, factor) pair and capped
    # the count at three, because a page's whole budget is twelve figures - so a plugin with
    # three per-cell columns over a four-factor design showed three of twelve comparisons and
    # named the other nine in a sentence. On the cohort this was written for, that meant ONE
    # column was ever compared and two design factors appeared on no page at all.
    #
    # The cap was the wrong lever. These panels are inline SVG strips a few rows tall, not
    # plots; what cost twelve figures was wrapping each in its own `<figure>`. Collected into a
    # single figure they cost ONE against the budget and NOTHING is dropped - which is the whole
    # reason the study exists, and the one thing a reader was not being shown.
    blocks, omitted = [], []
    for col in sorted(by_arm):
        for fac in sorted(by_arm[col]):
            d = by_arm[col][fac]
            arms = d.get("arms") or []
            if len(arms) < 2:
                omitted.append(f"{col} by {fac} (one arm present)")
                continue
            svg = (_arm_rows_numeric(arms) if d.get("kind") == "numeric"
                   else _arm_rows_categorical(arms, d.get("categories")))
            what = ("median, interquartile box and full range, per arm"
                    if d.get("kind") == "numeric" else "composition, per arm")
            # SHORT, AND THE CAVEAT SAID ONCE. Repeating "this is a description and not a test"
            # under every panel put the same 25 words on the page as many times as there were
            # factors; it belongs to the section, which states it above, not to each figure.
            ali = d.get("aliased_with") or []
            blocks.append(f'<div class="armpair"><p class="sub"><b><code>{_e(col)}</code> by '
                          f'<code>{_e(fac)}</code></b> — {what}, {len(arms)} arms.'
                          + (f' Identical split to '
                             + ", ".join("<code>" + _e(x) + "</code>" for x in ali)
                             + ' — one panel, not two, and which of them a difference belongs '
                               'to is not something this data can say.' if ali else "")
                          + '</p>' + svg + "</div>")
    if not blocks:
        return ""
    return ("<h2>Across the design</h2>"
            "<figure><figcaption>Every per-cell measure this plugin wrote, against every factor "
            f"of the design: {len(blocks)} comparison(s). A DESCRIPTION, not a test — the unit "
            "of replication is the sample, not the cell.</figcaption>"
            + "".join(blocks) + "</figure>"
            + (f"<p class='sub'>Not comparable here: {_e('; '.join(omitted))}.</p>"
               if omitted else ""))


def _concordance_block(name, recs):
    """This plugin's per-cell numbers against every OTHER plugin's, on both their pages.

    A diagnostic is useless on the page of the plugin that computed it. One plugin's summary
    reads "the check that a trajectory is not a cell-cycle axis" and the trajectory is on
    another plugin's page; the check was computed, reported and never applied to the claim it
    exists to bound - the same shape as an upstream constraint that reaches an index and none of
    the pages a reader quotes from.

    It is also the only second opinion a trajectory gets here. Confirming a trajectory with more
    than one method is what the field asks for when the topology is not known in advance
    (Heumos et al., Nat Rev Genet 2023), and two plugins that each order the same cells are two
    methods whether or not they were run for that purpose.

    Rho and n, sorted by strength, NOT thresholded and NOT interpreted. Which correlation
    matters is a question about the biology; that these two columns move together is arithmetic.
    """
    if not recs:
        return ""
    rows = []
    for r in recs:
        a, b = r["a"], r["b"]
        mine, theirs = (a, b) if a["plugin"] == name else (b, a)
        rho = float(r["rho"])
        rows.append(f"<tr><td><code>{_e(mine['column'])}</code></td>"
                    f"<td><code>{_e(theirs['column'])}</code><br>"
                    f"<span class='sub'>from {_e(theirs['plugin'])}</span></td>"
                    f"<td>{rho:+.3f}</td><td>{r['n']:,}</td></tr>")
    return ("<h2>Against the other plugins</h2><p class='sub'>Spearman between this plugin's "
            "per-cell numbers and another's, on the same cells. Not thresholded, not "
            "interpreted.</p>"
            "<div class='wrap'><table><tr><th>this plugin</th><th>against</th>"
            "<th>rho</th><th>cells</th></tr>" + "".join(rows) + "</table></div>")


def _lede(text):
    """The headline's claim, with the rest under it.

    A per-unit plugin's headline is every unit's headline concatenated - sixty words of
    per-sample detail in the first line of the page, before a reader has been told what the
    cohort is. The lead is the claim; the per-unit half is in the appendix and here.
    """
    lead, rest = _split_caption(text or "", limit=CAPTION_LEAD_WORDS)
    return (_e(lead)
            + (f"<details><summary class='sub'>per unit</summary>{_e(rest)}</details>"
               if rest else ""))


def _headline_without(p):
    """The headline with its refutations stripped - THIS PAGE shows them in a block of their own.

    `_entry` composes the delivered headline as `contradictions + headline`, and that must not
    change: it is what protects every consumer that reads `report.json` and has never heard of
    the newer field - the index, the schedule table, anything built from the payload later. A
    reader takes the headline, so the headline carries the refutation.

    On THIS page it is carried twice, once in the composed headline and once in the block below
    it, and saying the same sentence twice in the first two lines is the repetition this whole
    reporting pass exists to remove. The page is the one place both appear, so the page is where
    it is reconciled - not by weakening the payload.
    """
    head = str(p.get("headline") or "")
    for c in (p.get("contradictions") or []):
        head = head.replace(str(c).strip(), "").strip()
    return " ".join(head.split()) or str(p.get("headline") or "")


def _contradiction_block(items):
    """What the plugin said against its own headline, beside the headline, never collapsed.

    Two pages on a real cohort carried a claim their own figures refute - "45.5% of cells score
    S or G2M" in post-mitotic tissue, "3 terminal states" over cells whose fate entropy sits at
    the maximum three states allow. Neither page was dishonest: the evidence against each was
    plotted, correctly, further down.

    It reached the page as one sentence among ten in the caveat list, and before that it was
    prefixed onto the headline - where `_lede` splits at the first clause and folds the rest
    into a disclosure, so a refutation longer than the lead was rendered CLOSED. A mechanism
    that survives only while the sentence is short is not a mechanism.

    So it gets a block of its own: after the claim, before anything else, with no `<details>`
    anywhere inside it. `standard.check_page` looks for exactly this text in exactly the
    visible part of the page.
    """
    got = [str(c).strip() for c in (items or []) if str(c).strip()]
    if not got:
        return ""
    return ('<div class="warn"><b>This result is contradicted by its own diagnostics.</b><ul>'
            + "".join(f"<li>{_e(c)}</li>" for c in got) + "</ul></div>")


def _fold_caveats(caveats):
    """Caveats identical apart from their `[unit]` tag, folded into one line naming the units.

    A per-unit plugin emits its caveats once per unit and the merge tags each with the unit it
    came from, so a ten-sample run put the same sentence on the page ten times - 106 caveats on
    one page, of which a handful were distinct. Every unit is still named; what goes is the
    repetition, not the information.
    """
    import re as _re
    # IDENTICAL APART FROM THEIR NUMBERS COUNTS AS IDENTICAL. Ten units emit the same sentence
    # with their own counts in it - "576 cells carry an annotator sentinel", "412 cells ..." -
    # so folding on exact text left 42 distinct lines from 106, and a thousand words of the same
    # handful of statements. The numbers are not lost: each varying position is rendered as the
    # RANGE across the units it came from.
    _NUM = _re.compile(r"\d[\d,\.]*")
    groups, order, nums = {}, [], {}
    for c in caveats:
        m = _re.match(r"^\[([^\]]+)\]\s*(.*)$", str(c), _re.S)
        unit, body = (m.group(1), m.group(2)) if m else (None, str(c))
        key = _NUM.sub("\u0000", body)
        if key not in groups:
            groups[key] = []
            order.append(key)
            nums[key] = [[] for _ in _NUM.findall(body)]
        for i, v in enumerate(_NUM.findall(body)):
            if i < len(nums[key]):
                nums[key][i].append(v)
        if unit:
            groups[key].append(unit)

    def _fill(key):
        parts = key.split("\u0000")
        vals = nums.get(key) or []
        out_s = parts[0]
        for i, seg in enumerate(parts[1:]):
            got = sorted(set(vals[i])) if i < len(vals) else []
            if len(got) == 1:
                out_s += got[0]
            elif got:
                def _f(x):
                    try:
                        return float(str(x).replace(",", ""))
                    except ValueError:
                        return 0.0
                lo, hi = min(got, key=_f), max(got, key=_f)
                out_s += f"{lo}-{hi}"
            out_s += seg
        return out_s

    groups = {_fill(k): v for k, v in groups.items()}
    order = [_fill(k) for k in order]
    order_units = {u for v in groups.values() for u in v}
    out = []
    for body in order:
        units = groups[body]
        if not units:
            out.append(body)
        elif len(units) == 1:
            out.append(f"[{units[0]}] {body}")
        else:
            # ALL OF THEM IS NOT A LIST. Naming every unit on every folded caveat put ten names
            # on seventeen lines - two hundred words of the same ten strings, on a page whose
            # per-sample appendix already names them all. A SUBSET is still listed, because
            # which units a caveat applies to is the whole of its meaning when it is not all.
            total = len(order_units) if order_units else len(units)
            tag = (f"all {len(units)} units" if len(set(units)) >= total
                   else f"{len(units)} units: {', '.join(units)}")
            out.append(f"{body}  <span class='sub'>({tag})</span>")
    return out


def _overview_block(payload, *, plugin=None, by_arm=None):
    """WHAT WAS COMPARED, before any number. First on every page.

    THE FACTORS COME FROM THE DESIGN TABLE, which is the thing the user supplied. They were read
    from `by_arm` - the host's per-arm summaries - and that is a DOWNSTREAM ARTIFACT: it is built
    only from per-cell columns, so a plugin that writes none contributes nothing to it. Four
    plugins write none.

    The page then said "No design factor was resolved, so nothing on this page is a comparison
    between groups" over a cohort whose design resolved perfectly - ten samples, four factors,
    two levels each - and said it directly above its own per-arm panels. A
    reader is told the study has no groups by the one block whose job is to say what the groups
    are.

    A missing PER-CELL COLUMN and a missing DESIGN are different absences with different
    remedies, and reporting the first as the second sends the reader to the wrong place.
    """
    d = payload.get("describe") or {}
    units = [str(u) for u in (payload.get("units") or [])]
    # {factor: sorted levels}, FROM THE DESIGN ITSELF.
    factors = {}
    for row in (payload.get("design") or {}).values():
        for fac, lvl in (row or {}).items():
            factors.setdefault(str(fac), set()).add(str(lvl))
    n = d.get("n_obs")
    bits = []
    if n:
        bits.append(f"<b>{n:,}</b> cells")
    if units:
        bits.append(f"<b>{len(units)}</b> samples")
    if d.get("organism"):
        bits.append(f"{_e(d['organism'])} {_e(d.get('assay',''))}".strip())
    head = ("<h2>The cohort</h2><p class='lede'>" + " &middot; ".join(bits) + "</p>"
            + (f"<p class='sub'>Samples: {_e(', '.join(units))}</p>" if units else ""))
    if not factors:
        # THE ONLY CASE THAT EARNS THE EXEMPTION. A cohort with no design table can never draw a
        # panel comparing arms, so `arms` would fail on every page of every such run with no
        # remedy anyone could apply. Attached to the design being absent, and to nothing else:
        # attached to `by_arm` being empty, it exempted runs whose design was perfect.
        return head + ('<div class="bad" data-standard-exempt="arms">No design table was '
                       'supplied, so nothing on this page is a comparison between groups.</div>')
    rows = "".join(
        f"<tr><td><code>{_e(f)}</code></td><td>{_e(' / '.join(sorted(v)))}</td>"
        f"<td class='sub'>{len(v)} arms</td></tr>"
        for f, v in sorted(factors.items()))
    out = head + ("<div class='wrap'><table><tr><th>factor</th><th>arms</th><th></th></tr>"
                  + rows + "</table></div>")
    # AND WHAT THIS PLUGIN CONTRIBUTED TO IT. A NAMED ABSENCE about the plugin, never a claim
    # about the cohort: the design is right there in the table above.
    if plugin and not by_arm:
        out += ("<p class='sub'>" + _e(plugin) + " writes no per-cell column, so its own output "
                "is not split by these factors below. Where this page compares arms it does so "
                "through the per-unit measures it declared.</p>")
    return out

def write_kernel(out_dir, name, payload, cannot_show, summary="", merged=None,
                 spec=None, constraint="", binds=(), by_arm=None, aware=False,
                 concordance=(), payload_all=None):
    """One kernel's own page. Ends in its own limits, not a shared block."""
    p = payload or {}
    # ONCE ON THE PAGE, AT THE TOP. `ctx.contradiction` records into `caveats` as well, so that
    # a refutation survives into any document built from the payload by something that has
    # never heard of the newer field. On the page that is the same sentence twice, once in a
    # block that shouts and once ninth in a list - and the list copy is charged to the caveat
    # budget, so saying it properly would cost a page its `caveats` criterion.
    _contra = {str(c).strip() for c in (p.get("contradictions") or [])}
    # THE FOLD TAGS A PER-UNIT CAVEAT WITH ITS UNIT AND LEAVES THE CONTRADICTION UNTAGGED - it
    # has to, because the exit standard looks for the claim VERBATIM on the page. So comparing
    # the two directly matched for a cohort plugin and never for a per-unit one, and the claim
    # rendered twice: once in the block that shouts and once in the folded caveat list. The tag
    # is stripped before comparing, which is the one place these two forms are reconciled.
    caveats = [c for c in (p.get("caveats") or [])
               if re.sub(r"^\[[^\]]+\]\s*", "", str(c)).strip() not in _contra]
    absent = p.get("absent") or []
    body = [f"<h1>{_e(name)}</h1>",
            f'<p class="sub">{_e(summary)}</p>',
            f'<p class="lede">status <b>{_e(p.get("status", "?"))}</b> · '
            + _lede(_headline_without(p)) + '</p>',
            _contradiction_block(p.get("contradictions")),
            _overview_block(payload_all or {}, plugin=name, by_arm=by_arm),
            _constraint_block(constraint, binds)]
    if caveats:
        # THE CLAIM VISIBLE, THE ELABORATION COLLAPSED - the same split the captions get, and
        # for the same reason. These are written claim-first, so the leading sentence is the
        # part a reader must not miss; what follows is why, and it is one click away rather
        # than gone. A caveat nobody reaches the end of is not a caveat that was read.
        folded = _fold_caveats(caveats)
        items = []
        for c in folded:
            tail = ""
            if "</span>" in c:
                c, tail = c.split("<span class='sub'>", 1)
                tail = "<span class='sub'>" + tail
            lead, rest = _split_caption(c)
            items.append("<li>" + _e(lead) + tail
                         + (f"<details><summary class='sub'>why</summary>{_e(rest)}</details>"
                            if rest else "") + "</li>")
        body.append('<div class="warn"><b>Read these with the numbers, not after them</b><ul>'
                    + "".join(items) + "</ul></div>")
    # WHAT THE MERGE RETURNED, not what the plugin declared. Hard-coding "merged into the object
    # by barcode" from the declaration made this table assert a key the object did not have: a
    # per-unit plugin's arrays cannot be concatenated across units, merge_many drops them, and
    # this row went on saying they were merged. A reader then looks for a key nobody wrote.
    got = merged or {}
    rows = []
    for slot in ("obs", "obsm", "layers"):
        declared = sorted((p.get(slot) or {}))
        actually = set(got.get(slot) or [])
        for k in declared:
            rows.append((slot, k, "merged into the object by barcode" if k in actually or not got
                         else "NOT in the object — see what it could not produce, below"))
    for t in (p.get("tables") or []):
        rows.append(("table", Path(t).name, "beside the object, under this name"))
    if rows:
        body.append("<h2>What it produced</h2><div class='wrap'><table>"
                    "<tr><th>where</th><th>name</th><th>note</th></tr>"
                    + "".join(f"<tr><td>{_e(a)}</td><td><code>{_e(b)}</code></td>"
                              f"<td class='sub'>{_e(c)}</td></tr>" for a, b, c in rows)
                    + "</table></div>")
    if absent:
        body.append("<h2>What it could not produce</h2><div class='bad'><ul>"
                    + "".join(f"<li><b>{_e(a.get('what', '?'))}</b> — {_e(a.get('why', ''))}</li>"
                              for a in absent) + "</ul></div>")
    # BEFORE THE PANELS, NOT AFTER THEM. Every panel below describes one unit, and a reader who
    # meets the first unit's panel before meeting the spread has already formed the finding.
    units = p.get("units") or []
    if p.get("per_unit") and units:
        body.append(_across_units(units, (spec or {}).get("unit_metrics")))
        body.append(_units_by_arm(units, (payload_all or {}).get("design") or {},
                                  (spec or {}).get("unit_metrics"),
                                  out_dir=out_dir, name=name))
    body.append(_by_arm_block(by_arm, aware=bool(aware)))
    body.append(_concordance_block(name, concordance))
    # PER-SAMPLE PANELS GO TO AN APPENDIX, AND ARE LINKED. Three plugins here run once per
    # sample, so their pages carried the same five plots ten times over - 140 of 191 figures in
    # the report this was written for. Worse, two of those three INFER PER SAMPLE, so the
    # panels are not comparable with each other even in principle. Nothing is deleted: every
    # panel is still rendered, on its own page, one click away.
    per_unit_extra = ""
    figs_all = p.get("figures") or []
    per_unit_figs = [f for f in figs_all if f.get("unit")]
    cohort_figs = [f for f in figs_all if not f.get("unit")]
    if per_unit_figs and cohort_figs:
        body.append(_figure_section(cohort_figs, spec))
    elif per_unit_figs:
        body.append("<h2>Figures</h2><div class='bad'>Every panel this plugin drew describes "
                    "ONE sample; it has none over the cohort. They are in the "
                    f"<a href=\"{_e(name)}_by_sample.html\">per-sample appendix</a>.</div>")
    else:
        body.append(_figure_section(figs_all, spec))
    if per_unit_figs:
        body.append(f"<p class='sub'><a href=\"{_e(name)}_by_sample.html\">"
                    f"{len(per_unit_figs)} per-sample panels</a> &mdash; the same plots, one set "
                    f"per sample.</p>")
    if p.get("per_unit") and units:
        # Nine of ten unit payloads used to be discarded by a dict comprehension keyed on the
        # plugin name, and the survivor was rendered under that name as though it described the
        # cohort. Every unit gets a row, including the ones that produced nothing.
        per_unit_table = (
            "<h2>Per unit</h2><p class='sub'>This plugin runs once per unit because pooling the "
            "units would answer a different question. Each ran separately; the cell-level results "
            "are one column in the object, assembled from all of them.</p>"
            "<div class='wrap'><table><tr><th>unit</th><th>status</th><th>headline</th>"
            "<th>figures</th><th>caveats</th></tr>"
            + "".join(
                f"<tr><td><code>{_e(u.get('unit'))}</code></td>"
                f"<td>{_e(u.get('status', ''))}</td>"
                f"<td class='sub'>{_e(u.get('headline', ''))}</td>"
                f"<td>{_e(u.get('n_figures', 0))}</td>"
                f"<td class='sub'>{len(u.get('caveats') or [])}</td></tr>"
                for u in units) + "</table></div>")
        # BESIDE THE PANELS IT DESCRIBES. Ten rows of per-sample headlines is per-sample detail,
        # and it was 551 words on the page a reader opens - more than a third of everything
        # visible there - describing figures that are no longer on it.
        if per_unit_figs:
            per_unit_extra = per_unit_table
        else:
            body.append(per_unit_table)
    body.append(_limits(cannot_show))
    body.append('<p class="sub"><a href="index.html">&larr; back to the index</a></p>')
    d = Path(out_dir) / "report"
    d.mkdir(parents=True, exist_ok=True)
    if per_unit_figs:
        ap = ["<h1>" + _e(name) + " &mdash; per sample</h1>",
              "<p class='sub'>The same panels, once per sample. They are here rather than on "
              "the plugin's page because a page carrying one plot ten times hides its own "
              "result &mdash; and where the method is fitted per sample, these are not "
              "comparable with each other. "
              f"<a href='{_e(name)}.html'>&larr; back</a></p>"]
        ap += [per_unit_extra] if per_unit_extra else []
        ap += [_panel(f_, i + 1) for i, f_ in enumerate(per_unit_figs)]
        (d / f"{name}_by_sample.html").write_text(
            _page(f"{name} per sample — scProfile", "".join(ap)), encoding="utf-8")
    f = d / f"{name}.html"
    f.write_text(_page(f"{name} — scProfile", "".join(body)), encoding="utf-8")
    return f


def _schedule_block(payload):
    """What ran, in what order, on how many cores, and how long it took.

    Every other tool in this family records its own run cost. Without it the provenance cannot
    answer how long, on what, or in what order - and a schedule that was printed but not recorded
    is a claim nobody can check afterwards.
    """
    waves = payload.get("schedule") or []
    if not waves:
        return ""
    secs = payload.get("seconds") or {}
    rows = []
    for i, w in enumerate(waves, 1):
        for inst in w:
            n = inst.get("plugin")
            # THIS INSTANCE'S OWN TIME. Reading `seconds[plugin]` put the plugin's whole runtime
            # on every one of its unit rows - ten rows of "1000s over 10 instance(s)" for 1,000s
            # of work - and gave that same time to rows for units that never ran at all.
            if inst.get("seconds") is not None:
                took = f"{inst['seconds']:.0f}s"
                if inst.get("outcome") == "failed":
                    took += " (failed)"
            elif not inst.get("unit") and secs.get(n):
                took = f"{sum(secs[n]):.0f}s"
            else:
                took = "did not run"
            rows.append(f"<tr><td>{i}</td><td><code>{_e(n)}</code></td>"
                        f"<td>{_e(inst.get('unit') or '—')}</td>"
                        f"<td>{_e(inst.get('cores'))}</td><td>{_e(took)}</td></tr>")
    return ("<h2>How this ran</h2><p class='sub'>Instances in one wave are independent and run "
            "concurrently; a wave waits only on what the dependency graph says it waits on. The "
            f"core budget was {_e(payload.get('cores'))}"
            + (f", per-instance timeout {_e(payload.get('timeout'))}s"
               if payload.get("timeout") else ", with NO per-instance timeout")
            + ".</p><div class='wrap'><table><tr><th>wave</th><th>plugin</th><th>unit</th>"
              "<th>cores</th><th>time</th></tr>" + "".join(rows) + "</table></div>")


def write_index(out_dir, payload):
    """The index: EVERY known kernel, with its state and what it cannot show."""
    ran = list(payload.get("ran") or [])
    # ACCUMULATE. Built as a dict comprehension this was last-wins, so a plugin that failed on
    # every one of ten units showed exactly one reason and the `[:3]` slice below could never
    # show more than that one.
    skipped, sk_units = {}, {}
    for s in (payload.get("skipped") or []):
        skipped.setdefault(s["kernel"], []).extend(s.get("why", []))
        if s.get("unit") is not None:
            sk_units.setdefault(s["kernel"], []).append(str(s["unit"]))
    kern = payload.get("kernels") or {}
    known = sorted(set(payload.get("cannot_show") or {}) | set(ran) | set(skipped))
    d = payload.get("describe") or {}

    rows = []
    for n in known:
        if n in ran and n in skipped:
            # THE FOURTH STATE, and the one that was missing. `ran` was tested first, so a plugin
            # that succeeded on seven samples of ten rendered as a plain "ran / ok" carrying one
            # sample's headline - while the merged column held NaN for the other three and the
            # `elif` that would have named them was unreachable. A partial result presented as a
            # whole one is worse than a missing one: nothing about it looks wrong.
            p = kern.get(n, {})
            us = sk_units.get(n) or []
            state = ('<span class="pill warn">ran, ' + _e(len(skipped[n]))
                     + ' unit(s) failed</span> ' + _e(p.get("status", "")))
            head = (_e(p.get("headline", ""))
                    + "<br><span class='sub'>NOT covered: "
                    + (_e(", ".join(us)) if us else "see the page")
                    + " — those cells are NaN in the merged column</span>")
            link = f'<a href="{_e(n)}.html">{_e(n)}</a>'
        elif n in ran:
            p = kern.get(n, {})
            state = f'<span class="pill">ran</span> {_e(p.get("status", ""))}'
            head = _e(p.get("headline", ""))
            link = f'<a href="{_e(n)}.html">{_e(n)}</a>'
        elif n in skipped:
            state = '<span class="pill">not run</span>'
            head = "<br>".join(_e(w) for w in skipped[n][:3])
            link = _e(n)
        elif (payload.get("status") or {}).get(n) == "planned":
            # NOT THE SAME AS "not requested", and the distinction is the one this whole design
            # rests on: `this experiment cannot answer that` and `nobody has written this yet` are
            # opposite facts with opposite remedies, and a reader must not have to guess which.
            state = '<span class="pill warn">declared, not built</span>'
            head = (_e((payload.get("summaries") or {}).get(n, ""))
                    + "<br><span class='sub'>its prerequisites are declared and checkable; "
                      "the implementation does not exist</span>")
            link = _e(n)
        else:
            state = '<span class="pill">not requested</span>'
            head = _e((payload.get("summaries") or {}).get(n, ""))
            link = _e(n)
        rows.append(f"<tr><td>{link}</td><td>{state}</td><td class='sub'>{head}</td></tr>")

    con = payload.get("constraint_on_use") or ""
    con_block = (f'<div class="warn"><b>Constraint on use, carried from upstream</b><br>'
                 f'{_e(con)}<br><br><span class="sub">source: '
                 f'{_e(payload.get("constraint_source"))}</span></div>' if con else
                 '<div class="bad"><b>No upstream constraint on use was found.</b> This object '
                 'carries no record of what its embedding may and may not support, so nothing '
                 'here has checked whether a contrast you test is identifiable. Any kernel that '
                 'needs one says so on its own page.</div>')

    body = [
        "<h1>scProfile</h1>",
        f'<p class="sub">{d.get("n_obs", 0):,} cells × {d.get("n_vars", 0):,} genes · '
        f'scprofile {_e(payload.get("version"))}</p>',
        con_block,
        "<h2>Kernels</h2>",
        '<p class="lede">Every kernel this build knows about is listed, including the ones that '
        'did not run. A report that omitted them would look complete.</p>',
        "<div class='wrap'><table><tr><th>kernel</th><th>state</th>"
        "<th>headline, or why not</th></tr>" + "".join(rows) + "</table></div>",
        "<h2>What this object is, and how each was decided</h2>",
        "<div class='wrap'><table><tr><th>item</th><th>value</th><th>evidence</th></tr>"
        + "".join(f"<tr><td>{_e(k)}</td><td><code>{_e(v)}</code></td>"
                  f"<td class='sub'>{_e((d.get('keys_why') or {}).get(k, ''))}</td></tr>"
                  for k, v in (d.get("keys") or {}).items())
        + f"<tr><td>organism</td><td><code>{_e(d.get('organism'))}</code></td>"
          f"<td class='sub'>{_e(d.get('organism_why'))}</td></tr>"
          f"<tr><td>assay</td><td><code>{_e(d.get('assay'))}</code></td>"
          f"<td class='sub'>{_e(d.get('assay_why'))}</td></tr>"
        + "</table></div>",
        '<p class="sub">A value marked <i>detected</i> was a guess this tool made and printed; '
        'one marked <i>given on the command line</i> was your instruction. They carry different '
        'weight when a result is questioned later.</p>',
        # NO OBJECT IS A RESULT, NOT A BLANK. A run in which nothing merged writes no object, and
        # a report that renders `None` in a <code> block reads as a path somebody mistyped.
        "<h2>The object</h2>" + (
            f"<p><code>{_e(payload.get('object'))}</code></p>" if payload.get("object") else
            '<p class="bad"><b>No object was written.</b> No plugin contributed anything to '
            'merge, so the only object this run could have written is a copy of its input under '
            'a name that says it was profiled. What each plugin did instead is below.</p>'),
        '<p class="sub">Cell-level results are merged into it BY BARCODE. Edge-level results — '
        'cell–cell communication, regulon targets, abundance tests — are CSV beside it, because '
        'they are not per-cell and forcing them into <code>uns</code> makes them readable by this '
        'tool and nothing else.</p>',
    ]
    dd = Path(out_dir) / "report"
    dd.mkdir(parents=True, exist_ok=True)
    f = dd / "index.html"
    body.append(_schedule_block(payload))
    f.write_text(_page("scProfile", "".join(body)), encoding="utf-8")
    return f


def write_all(out_dir, payload):
    """Every kernel page plus the index. Returns the index path."""
    cs = payload.get("cannot_show") or {}
    sm = payload.get("summaries") or {}
    mg = payload.get("merged") or {}
    # FROM THE PAYLOAD, not from the installed plugin. `scprofile report` rebuilds these documents
    # from report.json alone; reading the declaration live would describe what the plugin promises
    # today over numbers it produced some other day.
    rs = payload.get("report_spec") or {}
    # FROM THE PAYLOAD for the same reason as `report_spec`: the host decided which plugins the
    # constraint binds while it held both the constraint and every plugin's contrast, and a
    # reporter re-deriving that months later would be re-deciding it against a different design.
    con = payload.get("constraint_on_use") or ""
    cb = payload.get("constraint_binds") or {}
    for name, p in (payload.get("kernels") or {}).items():
        write_kernel(out_dir, name, p, cs.get(name, []), sm.get(name, ""),
                     merged=mg.get(name), spec=rs.get(name),
                     constraint=con, binds=cb.get(name) or [],
                     by_arm=(payload.get("by_arm") or {}).get(name),
                     aware=bool((payload.get("design_aware") or {}).get(name)),
                     concordance=(payload.get("concordance") or {}).get(name) or [],
                     payload_all=payload)
    return write_index(out_dir, payload)
