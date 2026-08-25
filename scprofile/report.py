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
from datetime import datetime, timezone
from pathlib import Path

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
    return (f'<figure><img src="{_e(rel)}" alt="{_e(f.get("id") or f["path"])}">'
            f'<figcaption><b>{head}</b> {_e(f.get("caption") or "")}'
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
            q = f'<h3>{_e(d.get("question") or d.get("id"))}</h3>'
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
    return ('<div class="bad"><b>The upstream constraint binds this page.</b> Its numbers cross '
            + _e(", ".join(binds))
            + ', and a claim across ' + ("that factor" if len(binds) == 1 else "those factors")
            + ' is what the object\'s own constraint on use forbids. Read it before the results, '
              'not after them:<blockquote>'
            + "".join(f"<p>{_e(line.strip())}</p>"
                      for line in str(constraint).splitlines() if line.strip())
            + "</blockquote></div>")


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


def _across_units(units, declared):
    """THE UNITS ON ONE AXIS. Drawn by the host, once, for every per-unit plugin.

    A per-unit plugin runs separately on each unit and its page is that many single-unit
    reports in sequence. Every panel on it is true, and the one question a cohort study asks -
    do the units agree? - is answered nowhere, because the numbers never share an axis.
    Measured on a ten-animal cohort: one plugin's per-unit interaction count ran from 8,194 to
    38,895, a 4.7-fold range across ten animals of one tissue, and a reader taking the strongest
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
        blocks.append(f'<figure><figcaption><b>{_e(k)}</b>'
                      + (f' — {_e(q)}' if q else "")
                      + f' Each dot is one unit; hover for its name. '
                        f'{n} unit(s), {_num(vals[0])} to {_num(vals[-1])}.</figcaption>'
                      + _svg_strip(vals, labs) + "</figure>")
    if not rows:
        return ('<h2>Across units</h2><div class="bad">This plugin ran once per unit and '
                'recorded no comparable number, so its units cannot be put on one axis. Every '
                'panel below describes a single unit, and whether the units agree is not '
                'answered anywhere on this page.</div>')
    return ("<h2>Across units</h2><p class='sub'>Every panel further down describes ONE unit. "
            "This is the only place the units are compared, and the spread here is the context "
            "for reading any single-unit panel as a finding.</p>"
            + "".join(blocks)
            + "<div class='wrap'><table><tr><th>metric</th><th>min</th><th>median</th>"
              "<th>max</th><th>range</th><th>extremes</th></tr>"
            + "".join(rows) + "</table></div>")


def write_kernel(out_dir, name, payload, cannot_show, summary="", merged=None,
                 spec=None, constraint="", binds=()):
    """One kernel's own page. Ends in its own limits, not a shared block."""
    p = payload or {}
    caveats = p.get("caveats") or []
    absent = p.get("absent") or []
    body = [f"<h1>{_e(name)}</h1>",
            f'<p class="sub">{_e(summary)}</p>',
            f'<p class="lede">status <b>{_e(p.get("status", "?"))}</b> · '
            f'{_e(p.get("headline", ""))}</p>',
            _constraint_block(constraint, binds)]
    if caveats:
        body.append('<div class="warn"><b>Read these with the numbers, not after them</b><ul>'
                    + "".join(f"<li>{_e(c)}</li>" for c in caveats) + "</ul></div>")
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
    body.append(_figure_section(p.get("figures") or [], spec))
    if p.get("per_unit") and units:
        # Nine of ten unit payloads used to be discarded by a dict comprehension keyed on the
        # plugin name, and the survivor was rendered under that name as though it described the
        # cohort. Every unit gets a row, including the ones that produced nothing.
        body.append(
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
                f"<td class='sub'>{_e('; '.join(u.get('caveats') or []) or '—')}</td></tr>"
                for u in units) + "</table></div>")
    body.append(_limits(cannot_show))
    body.append('<p class="sub"><a href="index.html">&larr; back to the index</a></p>')
    d = Path(out_dir) / "report"
    d.mkdir(parents=True, exist_ok=True)
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
                     constraint=con, binds=cb.get(name) or [])
    return write_index(out_dir, payload)
