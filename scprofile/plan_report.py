"""The run plan as a document a person reads before committing a cluster to it.

WHO THIS IS FOR, AND WHAT THEY ARE DECIDING

Somebody with an object, a design table and a queue allocation, deciding whether to spend it.
They are not debugging this tool. The questions they actually have, in the order they have them:

    1. Can I run this at all, and on what?
    2. What will I GET - what artifacts, what claims can I make from them?
    3. What is going to run, in what order, and how long will it take?
    4. What settings will each thing use, and are they the right ones for MY design?
    5. What is not going to run, and is that my data's fault or something I can fix?
    6. What must I not conclude from this?

So the page answers them in that order. It does NOT open with a status table of nine plugins,
because "what is the state of your installation" is question five and leads with the tool's
problems rather than the user's work.

WHAT IT MUST NEVER DO

Present a plan as a result. Nothing here has run. Every number is about what WOULD happen, and
the page says so at the top, because a plan and a report of a finished run look alike once they
are both HTML in a browser and one of them is a claim about data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .report import CSS, _e

def _yield_for(kernel):
    """What a reader gets, IN THE PLUGIN'S OWN WORDS. Never from a table in the host.

    This was a hard-coded mapping of exactly the nine plugins that existed when it was written,
    and a tenth plugin rendered two empty cells in the report - silently, because a blank table
    cell looks like a plugin with nothing to say rather than a host that was never told about it.

    Both halves already exist as REQUIRED declarations (`declare.check` errors without them), so
    the table was duplicating them and could only be wrong. `cannot_show[0]` is the first limit
    the plugin author chose to lead with, which is exactly the "what it cannot tell you" column.
    """
    if kernel is None:
        return "", ""
    spec = getattr(kernel, "spec", None) or {}
    gives = str(spec.get("summary") or "").strip()
    when = str(spec.get("when_to_use") or "").strip()
    if when and len(gives) < 60:
        joined = gives.rstrip()
        if joined and joined[-1] not in ".!?":
            joined += "."
        gives = f"{joined} Use it when {when[0].lower()}{when[1:]}" if joined else when
    limits = spec.get("cannot_show") or []
    return gives, str(limits[0]).strip() if limits else ""


def _card(title, body, kind=""):
    cls = {"warn": "warn", "bad": "bad", "good": "good"}.get(kind, "card")
    return f'<div class="{cls}"><b>{_e(title)}</b><br>{body}</div>'


def write(out_dir, plan, *, filename="run_plan.html", kernels=None):
    """Render the plan. `plan` is the dict `scprofile plan --report` assembles.

    `kernels` is the registry, so the "what you get" column can be read from each plugin's own
    declaration rather than a table here. Optional, because a plan can be rendered from a saved
    `run_plan.json` with no registry to hand - in which case the column is empty, which is
    honest, rather than filled in from a list that knows only the plugins someone remembered.
    """
    now = datetime.now(timezone.utc)
    d = plan.get("describe") or {}
    facts = plan.get("facts") or {}
    verdicts = plan.get("verdicts") or []
    waves = plan.get("waves") or []
    by = {v["plugin"]: v for v in verdicts}
    runs = [v for v in verdicts if v["verdict"] == "RUN"]
    skips = [v for v in verdicts if v["verdict"] == "SKIP"]
    other = [v for v in verdicts if v["verdict"] not in ("RUN", "SKIP")]
    pending = [v for v in verdicts if v.get("readiness")]

    B = []
    B.append("<h1>Run plan</h1>")
    B.append(f'<p class="sub">{d.get("n_obs", 0):,} cells &times; {d.get("n_vars", 0):,} genes '
             f'&middot; scprofile {_e(plan.get("version", ""))} &middot; '
             f'{now:%Y-%m-%d %H:%M %Z}</p>')

    # NOTHING HAS RUN. Said first, and in the loudest box on the page, because a plan and a
    # finished report are both HTML in a browser and only one of them is a claim about data.
    B.append(_card("Nothing here has run yet.",
                   "This is a plan: what <i>would</i> happen, with these settings, in this order. "
                   "No number on this page is a result. Read it, change what you disagree with, "
                   "then run it.", "warn"))

    # ---- 1. what you can run ------------------------------------------------------------------
    B.append("<h2>What you can run</h2>")
    B.append(f'<p class="lede"><b>{len(runs)} of {len(verdicts)}</b> plugin(s) can run on this '
             f'project. '
             + (f'<b>{len(skips)}</b> cannot, because of the design. ' if skips else "")
             + (f'<b>{len(other)}</b> need something that is not here yet. ' if other else "")
             + (f'<b>{len(pending)}</b> need preparing in this installation first &mdash; which '
                f'is not a limit of your data.' if pending else ""))

    if facts.get("has_design"):
        rows = "".join(
            f"<tr><td><code>{_e(n)}</code></td><td>{v['n_levels']}</td>"
            f"<td>{_e(', '.join(f'{k}={len(s)}' for k, s in sorted(v['levels'].items())))}</td>"
            f"<td>{v['min_replicates']}</td></tr>"
            for n, v in sorted(facts.get("factors", {}).items()))
        B.append("<h3>Your design, as this plan read it</h3>"
                 "<div class='wrap'><table><tr><th>factor</th><th>levels</th><th>samples</th>"
                 f"<th>smallest arm</th></tr>{rows}</table></div>")
        if facts.get("crossed_pairs"):
            B.append(f'<p class="sub">Crossed with replication in every cell: '
                     + ", ".join(f"<code>{_e(a)} &times; {_e(b)}</code>"
                                 for a, b in facts["crossed_pairs"])
                     + " &mdash; so an interaction is estimable, and the plan uses it.</p>")
    else:
        B.append(_card("No design table was given.",
                       "Plugins that test across conditions need one &mdash; a CSV keyed on your "
                       "sample column. Without it they are not skipped, they are waiting: pass "
                       "<code>--design</code> and re-plan.", "warn"))

    # ---- 2. what you get ----------------------------------------------------------------------
    B.append("<h2>What you get out of it</h2>")
    B.append('<p class="lede">What each result lets you say, and what it does not. The second '
             'column is the part that matters when the figure is in a talk.</p>')
    rows = []
    for v in sorted(runs, key=lambda x: x["plugin"]):
        gives, limit = _yield_for((kernels or {}).get(v["plugin"]))
        rows.append(f"<tr><td><code>{_e(v['plugin'])}</code></td><td>{_e(gives)}</td>"
                    f"<td class='sub'>{_e(limit)}</td></tr>")
    B.append("<div class='wrap'><table><tr><th>plugin</th><th>what you get</th>"
             f"<th>what it cannot tell you</th></tr>{''.join(rows)}</table></div>")

    # ---- 3 + 4. order and settings ------------------------------------------------------------
    B.append("<h2>What runs, in what order, with what settings</h2>")
    B.append('<p class="lede">A wave waits only on what the dependency graph says it waits on. '
             'Everything inside one wave is independent and can run at the same time.</p>')
    for i, w in enumerate(waves, 1):
        B.append(f"<h3>Wave {i}</h3>")
        for name in w:
            v = by.get(name)
            if not v:
                continue
            s = v.get("settings") or {}
            bits = []
            for key in ("label", "sample", "batch", "compartment", "embedding",
                        "counts_layer", "lognorm_layer", "cores"):
                if s.get(key):
                    bits.append(f"<tr><td>{_e(key)}</td><td><code>{_e(s[key])}</code></td></tr>")
            if s.get("per_unit"):
                pu = s["per_unit"]
                bits.append(f"<tr><td>runs</td><td>{_e(pu['mode'])} &mdash; {pu['n']} unit(s) on "
                            f"<code>{_e(pu['key'])}</code></td></tr>")
            if s.get("contrast"):
                c = s["contrast"]
                bits.append(f"<tr><td>contrast</td><td><code>{_e(c['formula'])}</code><br>"
                            f"<span class='sub'>{_e(c['why'])}</span></td></tr>")
            if s.get("references"):
                r = s["references"]
                bits.append(f"<tr><td>references</td><td>{_e(r['organism'] or 'not detected')}"
                            f" &mdash; declared for {_e(', '.join(r['declared_for']))}</td></tr>")
            rung = v.get("rung")
            badge = (f'<span class="pill">{_e(rung)}</span>' if rung else "")
            prep = ("" if not v.get("readiness") else
                    f'<span class="pill warn">prepare first</span>')
            B.append(f"<h4><code>{_e(name)}</code> {badge} {prep}</h4>")
            if bits:
                B.append("<div class='wrap'><table>" + "".join(bits) + "</table></div>")
            if v.get("why_not_higher"):
                B.append(_card("Not at full capacity", _e(v["why_not_higher"]), "warn"))
            for c in (v.get("caveats") or []):
                B.append(_card("Carry this with the result", _e(c), "warn"))
            if v.get("readiness"):
                B.append(_card("Not installed here yet",
                               f"{_e(v['readiness']['why'])}.<br>"
                               f"<code>{_e(v['readiness']['fix'])}</code><br>"
                               f"<span class='sub'>This is about this installation, not your "
                               f"data. The plan above is what it will do once it is ready."
                               f"</span>"))

    # ---- 5. what will not run -----------------------------------------------------------------
    if skips or other:
        B.append("<h2>What will not run, and whose problem it is</h2>")
        for v in skips:
            B.append(_card(f"{v['plugin']} &mdash; your design cannot express this",
                           "<br>".join(_e(w) for w in v["why"])
                           + "<br><span class='sub'>This is the only kind of design problem that "
                             "stops a run. An imbalance or a confound would have been carried as "
                             "a caveat instead.</span>", "bad"))
        for v in other:
            B.append(_card(f"{v['plugin']} &mdash; {v['verdict'].lower()}",
                           "<br>".join(_e(w) for w in v["why"])
                           + (f"<br><span class='sub'>Searched {len(v.get('searched') or [])} "
                              f"location(s).</span>" if v.get("searched") else ""),
                           "bad" if v["verdict"] == "BLOCKED" else "warn"))

    # ---- 6. what you must not conclude --------------------------------------------------------
    B.append("<h2>Before you quote any of this</h2>")
    if plan.get("constraint_on_use"):
        B.append(_card("A constraint travelled with this object",
                       _e(plan["constraint_on_use"])
                       + f"<br><span class='sub'>source: "
                         f"{_e(plan.get('constraint_source', ''))}</span>", "warn"))
    else:
        B.append(_card("This object carries no constraint on use",
                       "Nothing upstream recorded what its embedding may and may not support, so "
                       "nothing here has checked whether a contrast you test is identifiable. "
                       "Each plugin says what it cannot show on its own page.", "bad"))
    B.append('<p class="sub">Every plugin ships its own limits and they are printed with its '
             'results, not here &mdash; a limit restated away from the number it qualifies is a '
             'limit that goes stale.</p>')

    # RENDERED WHENEVER THE AUDIT RAN, not whenever it found something. A clean audit returns no
    # findings, so keying this section on findings made a passing audit and an audit that was
    # never run look the same - which is the failure the audit rule itself names.
    if plan.get("audited"):
        found = plan.get("audit") or []
        n_err = sum(1 for x in found if x.get("level") == "ERROR")
        checks = plan.get("audit_checks") or []
        B.append("<h2>Was this plan checked?</h2>")
        body = ("<br>".join(f"{_e(x['level'])} &mdash; {_e(x['check'])}" for x in found)
                if found else
                "Every check passed. This plan can justify each of its own verdicts.")
        if checks:
            body += ("<br><br><span class='sub'>What was checked:<br>"
                     + "<br>".join(_e(c) for c in checks) + "</span>")
        B.append(_card(f"{len(checks) or len(found)} check(s), {n_err} error(s)", body,
                       "bad" if n_err else "good"))
    else:
        B.append("<h2>Was this plan checked?</h2>")
        B.append(_card("No. This plan was not audited.",
                       "Re-run with <code>--audit</code> and the plan will be checked by rules "
                       "that do not repeat its own reasoning &mdash; that every plugin is "
                       "accounted for once, that nothing is left unresolved, that every skip "
                       "cites a design fact the table supports, and that nothing runs below a "
                       "capacity your project would support.", "warn"))

    B.append(f'<p class="sub">Object: <code>{_e(plan.get("h5ad", ""))}</code><br>'
             f'Searched {len(plan.get("roots") or [])} location(s) for inputs not on the object'
             + ("  &mdash; <b>the search did not complete</b>, so anything reported as absent "
                "may only be unfound." if plan.get("search_incomplete") else "") + "</p>")

    dd = Path(out_dir)
    dd.mkdir(parents=True, exist_ok=True)
    f = dd / filename
    f.write_text(
        f'<meta charset="utf-8"><meta name="viewport" content="width=device-width,'
        f'initial-scale=1"><title>Run plan &mdash; scProfile</title><style>{CSS}</style>'
        f'<main>{"".join(B)}</main>', encoding="utf-8")
    return f
