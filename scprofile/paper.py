"""The paper test: can someone write the result from these figures, and does it survive review?

WHERE THIS SITS. It is the step AFTER the figures exist and have been looked at, and BEFORE a
run is promoted or its results are reused:

    run  ->  report  ->  standard  ->  review  ->  PAPER  ->  licence / promote
             draw it     measure      look at     write it    build on it
                         the page     the images  and defend

Each earlier step answers a narrower question. `standard` asks whether the page is readable.
`review` asks whether anybody opened the images. Neither asks the question a reader will:
**does this figure set support the thing you want to say?**

WHY A LEDGER AND NOT A CHECKLIST. A checklist is satisfied by reading it. What is recorded here
is a CLAIM - one sentence somebody would put in a paper - and the figures it was read off. A
claim is then reviewed, and the review has three honest outcomes, one of which is that the claim
was wrong. The value is entirely in the third: a claim that dies took a wrong figure with it, or
named a figure that does not exist.

THE ONE PROPERTY THAT MAKES IT A GATE. A claim is bound to the sha256 of every figure it cites.
REDRAW ONE OF THOSE FIGURES AND THE CLAIM IS STALE - not old, stale, and it has to be defended
again. That is the same mechanism as the figure review ledger, for the same reason: a statement
made about a picture cannot outlive the picture.

WHAT THIS IS NOT, AND IT IS NARROW ON PURPOSE FOR NOW. See `NARROW` at the bottom of this file
and `docs/PAPER_TEST.md`. The gaps are NAMED rather than implied, because a test whose limits
are not written down gets used as though it had none.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

#: Where the ledger lives, relative to a run directory. Beside the run, so it travels with the
#: run key and cannot be confused with claims made about some other render.
#: ONE MANUSCRIPT PER PLUGIN, NEVER ONE FOR THE RUN. A profiling run mounts several methods and
#: they answer different questions on different evidence; a single section covering all of them
#: reads as a survey of the tooling rather than as a result, and its figure panel is a gallery.
#: A reader wants the cell-cell communication result, or the differential expression result - not
#: both interleaved. `paper` therefore takes a plugin and writes that plugin's own section, its
#: own claims ledger and its own rendered page, each carrying the plugin in its name.
#:
#: The un-suffixed names are kept as the COHORT-level section, for a run with one plugin or for a
#: synthesis somebody writes deliberately, and are never produced by accident.
LEDGER = "PAPER_CLAIMS.jsonl"


def _report_dir(out, plugin=""):
    """Where this section's rendered page goes."""
    from . import kernels as _K
    return _K.plugin_report(out, plugin) if plugin else _K.run_report(out)


def _root(out, plugin=""):
    """Where this section's files live: the plugin's own directory, or the run root.

    See `kernels.plugin_out`. A cohort-level synthesis (no plugin) stays at the run root, which
    is the only thing there that is about the run rather than about one method.
    """
    from . import kernels as _K
    return _K.plugin_out(out, plugin) if plugin else Path(out)


def ledger_name(plugin=""):
    """`PAPER_CLAIMS.jsonl`, or `PAPER_CLAIMS.<plugin>.jsonl` for one plugin's claims."""
    return LEDGER if not plugin else f"PAPER_CLAIMS.{plugin}.jsonl"


def draft_name(plugin=""):
    """`PAPER.md`, or `PAPER.<plugin>.md`."""
    return DRAFT if not plugin else f"PAPER.{plugin}.md"


def page_name(plugin=""):
    """`report/paper.html`, or `report/<plugin>_paper.html`.

    THE PLUGIN COMES FIRST, because that is the convention `report.py` already uses for every
    other per-plugin page it writes - `cellchat.html`, `cellchat_by_arm.html`,
    `cellchat_by_sample.html`. A page called `paper_cellchat.html` would sort away from its three
    siblings in a directory listing and read as a different kind of thing, which it is not.
    Matching an existing convention is worth more than a name chosen fresh.
    """
    return "paper.html" if not plugin else f"{plugin}_paper.html"

#: A claim shorter than this is a label, not a claim. "Diet matters" asserts nothing checkable.
MIN_CLAIM_WORDS = 8

#: And a review that does not say what was examined is not a review.
MIN_WHY_WORDS = 5

#: The three honest outcomes of putting a claim to a reviewer, and the fourth state a claim can
#: be in before anyone has.
STANDING, NARROWED, WITHDRAWN = "standing", "narrowed", "withdrawn"
UNREVIEWED, STALE = "unreviewed", "stale"
VERDICTS = (STANDING, NARROWED, WITHDRAWN)


class Refused(Exception):
    """A claim or a verdict that cannot have come from the work. Raised, never returned."""


def _digest(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
    except OSError:
        return ""
    return h.hexdigest()


def read_ledger(out, plugin=""):
    """[record] in order. Append-only: later records about one claim supersede earlier ones."""
    p = _root(out, plugin) / ledger_name(plugin)
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:                                                 # noqa: BLE001
            continue
    return rows


def _append(out, rec):
    _root(out, plugin).mkdir(parents=True, exist_ok=True)
    with open(_root(out, plugin) / ledger_name(plugin), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def claim(out, text, cites, *, author="", plugin=""):
    """Record one claim and the figures it was read off. Returns the record.

    `cites` are paths relative to the run directory. A claim citing NOTHING is refused: the
    whole point is to bind a sentence to the pictures it came from, and a claim with no figures
    is an opinion the figure set cannot be held responsible for.
    """
    root = Path(out)
    words = " ".join(str(text or "").split())
    if len(words.split()) < MIN_CLAIM_WORDS:
        raise Refused(f"a claim of {len(words.split())} word(s) asserts nothing checkable. Write "
                      f"the sentence you would put in a paper, in at least {MIN_CLAIM_WORDS} "
                      f"words - what is higher than what, in which arm, and by how much.")
    cites = [str(c).strip() for c in (cites or []) if str(c).strip()]
    if not cites:
        raise Refused("a claim must cite at least one figure. A sentence with no figure behind "
                      "it is not a test of the figure set.")
    missing = [c for c in cites if not (root / c).is_file()]
    if missing:
        raise Refused(f"no such figure in this run: {', '.join(missing)}")
    cid = hashlib.sha256(words.lower().encode()).hexdigest()[:12]
    return _append(out, {"kind": "claim", "id": cid, "text": words,
                         "cites": {c: _digest(root / c) for c in cites},
                         "author": str(author or ""),
                         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})


def review(out, cid, verdict, why, *, reviewer="", replaces=""):
    """Record what a review round did to one claim.

    THE VERDICT THAT MATTERS IS `withdrawn`. A loop that only ever confirms is a loop nobody
    learned from, and the count of withdrawn claims is printed by `summarise` for that reason.
    """
    if verdict not in VERDICTS:
        raise Refused(f"verdict must be one of {', '.join(VERDICTS)}; got {verdict!r}")
    text = " ".join(str(why or "").split())
    if len(text.split()) < MIN_WHY_WORDS:
        raise Refused(f"a verdict of {len(text.split())} word(s) does not say what was examined. "
                      f"Say what the reviewer put to it and what happened, in at least "
                      f"{MIN_WHY_WORDS} words.")
    known = {r["id"] for r in read_ledger(out, plugin) if r.get("kind") == "claim"}
    if cid not in known:
        raise Refused(f"no claim {cid!r} in this run. Record the claim before reviewing it.")
    return _append(out, {"kind": "review", "id": cid, "verdict": verdict, "why": text,
                         "reviewer": str(reviewer or ""), "replaces": str(replaces or ""),
                         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})


def status(out, plugin=""):
    """[(id, state, rounds, text)] for every claim, newest verdict winning.

    A claim whose cited figures have changed is STALE whatever its last verdict was: the review
    was of a picture that no longer exists.
    """
    root = Path(out)
    claims, rounds = {}, {}
    for r in read_ledger(out, plugin):
        if r.get("kind") == "claim":
            claims[r["id"]] = r
        elif r.get("kind") == "review":
            rounds.setdefault(r["id"], []).append(r)
    rows = []
    for cid, c in claims.items():
        rs = rounds.get(cid) or []
        moved = [f for f, sha in (c.get("cites") or {}).items()
                 if sha and _digest(root / f) != sha]
        if moved:
            state = STALE
        elif not rs:
            state = UNREVIEWED
        else:
            state = rs[-1]["verdict"]
        rows.append((cid, state, len(rs), c.get("text", "")))
    return sorted(rows, key=lambda r: (r[1], r[0]))


def outstanding(out, plugin=""):
    """Claims that have not been defended: never reviewed, or cited a figure that has changed."""
    return [(cid, st) for cid, st, _n, _t in status(out, plugin)
            if st in (UNREVIEWED, STALE)]


def summarise(out, plugin=""):
    """One line per claim plus a tally. Printed by `scprofile paper` and by `check --out`."""
    rows = status(out)
    if not rows:
        return ("NO CLAIMS RECORDED. The paper test has not been run on this figure set: nobody "
                "has written down what it is supposed to show, so nothing has been able to "
                "fail. `scprofile paper --claim ... --cites ...`")
    tally = {}
    for _c, st, _n, _t in rows:
        tally[st] = tally.get(st, 0) + 1
    lines = [f"  {cid}  {st:<11} {n} round(s)  {txt[:74]}" for cid, st, n, txt in rows]
    order = (WITHDRAWN, NARROWED, STANDING, UNREVIEWED, STALE)
    lines.append("  " + " · ".join(f"{tally[k]} {k}" for k in order if k in tally))
    if not tally.get(WITHDRAWN) and not tally.get(NARROWED) and tally.get(STANDING):
        lines.append("  EVERY CLAIM SURVIVED UNCHANGED. That is possible and it is also what a "
                     "loop looks like when nobody pushed on it - the value of this test is in "
                     "the claims it kills.")
    return "\n".join(lines)


#: The authored result section, in the run directory. SOURCE, not a rendering.
DRAFT = "PAPER.md"


def brief(out):
    """Everything needed to WRITE the section, read out of the run. Returns text.

    THE STEP THAT MAKES THIS AN AGENTIC PROCESS RATHER THAN A FILING CONVENTION. An agent asked
    to "write the result" has to go and find the figures, guess which are the main ones, and
    open the object for the design - three chances to write about something the run does not
    contain. The brief hands over exactly what the run holds: the panels on the page a reader
    meets first, each with the caption the panel itself carries, the design, and the constraint
    the upstream object placed on the whole run.

    THE CAPTION REST IS INCLUDED AND IT IS THE POINT. That is where a panel states what it does
    NOT establish - the confound audit, the shared-scale warning, the elements taken off the
    magnitude scale - and it is precisely the material a first draft omits and a reviewer then
    finds.
    """
    import json as _json

    root = Path(out)
    try:
        pay = _json.loads((root / "report.json").read_text(encoding="utf-8"))
    except Exception:                                                     # noqa: BLE001
        return ("No report.json in this run, so there is nothing to write from. "
                "Run `scprofile report --out <RUNDIR>` first.")

    L = [f"# Writing brief — {root.name}", ""]
    d = pay.get("describe") or {}
    L += [f"Object: {d.get('n_obs', '?'):,} observations x {d.get('n_vars', '?'):,} features."
          if isinstance(d.get("n_obs"), int) else "Object: size not recorded.",
          f"Assay: {d.get('assay') or '(not declared)'}   Organism: "
          f"{d.get('organism') or '(not declared)'}", ""]

    des = pay.get("design") or {}
    ax = pay.get("unit_axis") or {}
    if des:
        facs = sorted({f for r in des.values() for f in (r or {})})
        L += [f"Design: {len(des)} sample(s) over {', '.join(facs)}."]
        arms = sorted(u for u, k in ax.items() if k == "group")
        if arms:
            mem = pay.get("unit_members") or {}
            L += ["Arms (the unit of inference): "
                  + "; ".join(f"{a} n={len(mem.get(a) or [])}" for a in arms)]
        L += [""]

    con = pay.get("constraint_on_use")
    if con:
        L += ["CONSTRAINT CARRIED BY THE UPSTREAM OBJECT - it binds anything written here:",
              "  " + " ".join(str(con).split())[:600], ""]

    lab = pay.get("label_by_unit") or {}
    tot = pay.get("label_total") or {}
    if lab and tot:
        thin = [l for l in tot if any(l not in (lab.get(u) or {}) for u in lab)]
        L += [f"Populations: {len(tot)} in the object; {len(thin)} are absent from at least one "
              f"unit and cannot carry a between-unit comparison"
              + (f" ({', '.join(sorted(thin)[:8])}{'...' if len(thin) > 8 else ''})"
                 if thin else ""), ""]

    for k in sorted(pay.get("kernels") or {}):
        pl = (pay["kernels"] or {}).get(k) or {}
        figs = pl.get("figures") or []
        cohort = [f for f in figs if not f.get("unit")]
        L += [f"## {k}", ""]
        if pl.get("cannot_show"):
            L += ["What this method cannot show, from its own declaration:"]
            L += [f"  - {' '.join(str(c).split())}" for c in pl["cannot_show"]]
            L += [""]
        # THE PANELS ON THE PAGE, WHICHEVER LAYER DREW THEM. The plugin's payload holds only
        # what the plugin emitted; the design panel, the census, the between-arm comparisons and
        # the interaction are drawn by the HOST at render time. Reading only the payload
        # reported "no cohort-level panel" for a page carrying nine of them - the nine a reader
        # meets first, and the ones every claim in the section is read off.
        try:
            placed = _json.loads((root / "report" / "panels.json")
                                 .read_text(encoding="utf-8")).get(k, {}).get("cohort") or []
        except Exception:                                                 # noqa: BLE001
            placed = []
        cohort = list(placed) + list(cohort)
        L += [f"Panels on the page a reader meets first ({len(cohort)}):" if cohort
              else "No cohort-level panel on this page; every panel is per unit. Say so, and "
                   "read the claims off the per-arm page instead.", ""]
        for f in cohort:
            cap = f.get("caption")
            lead, rest = (cap if isinstance(cap, (list, tuple)) and len(cap) == 2
                          else (cap or "", ""))
            L += [f"  {f.get('path')}",
                  f"     SHOWS : {' '.join(str(lead).split())}"]
            if rest:
                L += [f"     LIMITS: {' '.join(str(rest).split())}"]
            L += [""]
    L += ["---", "Write the Results section you would submit. Then record each claim against the",
          "figures you read it off, put it to a reviewer, and record what happened:", "",
          "  scprofile paper --out <RUNDIR> --claim '...' --cites <fig>,<fig>",
          "  scprofile paper --out <RUNDIR> --round <id> --verdict standing|narrowed|withdrawn"
          " --why '...'",
          "  scprofile paper --out <RUNDIR> --write section.md",
          "  scprofile paper --out <RUNDIR> --render", ""]
    return "\n".join(L)


def next_step(out):
    """(headline, command) - what to do next, always with something runnable.

    A STATUS THAT DOES NOT SAY WHAT TO DO NEXT IS A REPORT SOMEBODY HAS TO INTERPRET. Every
    other gate in this tool names its own remedy; this one drives a loop, so it names the step.
    """
    rows = status(out, plugin)
    have_draft = bool(read_draft(out, plugin))
    if not rows:
        return ("Nothing has been written from these figures yet. Start by reading the brief.",
                "scprofile paper --out {out} --brief")
    todo = [c for c, st, _n, _t in rows if st == UNREVIEWED]
    if todo:
        return (f"{len(todo)} claim(s) have never been put to a reviewer. Review them, and "
                f"record what the review DID - `withdrawn` is the verdict that teaches.",
                "scprofile paper --out {out} --round " + todo[0]
                + " --verdict standing|narrowed|withdrawn --why '...'")
    stale = [c for c, st, _n, _t in rows if st == STALE]
    if stale:
        return (f"{len(stale)} claim(s) cite a figure that has been REDRAWN since the claim was "
                f"made. The section describes pictures that no longer exist; defend them again.",
                "scprofile paper --out {out} --round " + stale[0]
                + " --verdict standing|narrowed|withdrawn --why '...'")
    if not have_draft:
        return ("Every claim is defended and no section has been written. The ledger holds the "
                "sentences and not the document they came from.",
                "scprofile paper --out {out} --write section.md")
    if not (_report_dir(out, plugin) / page_name(plugin)).is_file():
        return ("The section is written and every claim defended. Render it into the run.",
                "scprofile paper --out {out} --render")
    withdrawn = [c for c, st, _n, _t in rows if st == WITHDRAWN]
    if not withdrawn:
        return ("Every claim survived unchanged, which is also what a loop looks like when "
                "nobody pushed. Consider another round against a different standard.",
                "scprofile paper --out {out} --brief")
    return ("The loop has run: claims written, reviewed, and the section rendered into the run.",
            "")


def write_draft(out, text, *, author="", plugin=""):
    """Store the authored result section IN THE RUN, and return where it went.

    WHY THIS IS A RUN OUTPUT AND NOT A SCRATCH FILE. The rule this tool applies to figures - a
    figure a run does not regenerate is a draft - was not being applied to the writing. A
    written result kept in a scratchpad has no run key, cannot be traced to the figures it was
    read off, and disappears with the session that produced it. It is a draft by the tool's own
    definition, and the ledger without it holds four sentences and four verdicts but not the
    section they came from: not the numbers, not the caveats, not why those figures and not
    others.

    The prose is AUTHORED - this tool cannot write the science and does not try. What it does is
    keep it beside the run that produced the figures, bind it to them through the claims, and
    render it with those figures inline so the document and the pictures cannot drift apart.
    """
    root = Path(out)
    body = str(text or "").rstrip() + "\n"
    if len(body.split()) < MIN_CLAIM_WORDS * 4:
        raise Refused(f"a result section of {len(body.split())} words is a note, not a section. "
                      f"Write what you would submit.")
    _root(out, plugin).mkdir(parents=True, exist_ok=True)
    (_root(out, plugin) / draft_name(plugin)).write_text(body, encoding="utf-8")
    _append(out, {"kind": "draft", "words": len(body.split()), "author": str(author or ""),
                  "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    return _root(out, plugin) / draft_name(plugin)


def read_draft(out, plugin=""):
    """The authored section, or "" when none has been written."""
    p = _root(out, plugin) / draft_name(plugin)
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def render(out, *, run_key="", title="Result section", plugin=""):
    """Write `report/paper.html`: the authored section, the claims, and every figure they cite.

    ASSEMBLED FROM THE RUN, so it cannot describe figures that are not there. Every claim's
    state is printed beside it and a stale claim is called out at the top, which is the whole
    reason the claims carry digests: a document written from pictures that have since been
    redrawn is the failure this project calls rule six, and here it is structural rather than
    remembered.
    """
    root = Path(out)
    body = read_draft(out, plugin)
    rows = status(out)
    if not body and not rows:
        return None
    from .report import _page, _e                                     # noqa: PLC0415

    stale = [c for c, st, _n, _t in rows if st in (STALE, UNREVIEWED)]
    out_html = [f"<h1>{_e(title)}</h1>"]
    if run_key:
        out_html.append(f'<p class="sub">Written from run <code>{_e(run_key)}</code>. '
                        f'Every figure cited below is in that run.</p>')
    if stale:
        out_html.append(
            '<div class="bad"><b>NOT CURRENT.</b> ' + str(len(stale)) +
            ' claim(s) in this section are undefended, or cite a figure that has been redrawn '
            'since the claim was made. A section written from pictures that no longer exist '
            'reads exactly like one that is right.</div>')
    if body:
        out_html.append(_md(body))
    else:
        out_html.append('<div class="warn">No result section has been written for this run. '
                        'The claims below exist without the document they came from.</div>')

    if rows:
        out_html.append("<h2>The claims, and what review did to them</h2>")
        out_html.append('<div class="wrap"><table><tr><th>claim</th><th>state</th>'
                        '<th>rounds</th><th>cites</th></tr>')
        cites = {r["id"]: r.get("cites") or {} for r in read_ledger(out, plugin)
                 if r.get("kind") == "claim"}
        for cid, st, n, txt in rows:
            names = ", ".join(Path(f).name for f in sorted(cites.get(cid, {})))
            out_html.append(f"<tr><td>{_e(txt)}</td><td><b>{_e(st)}</b></td>"
                            f"<td>{n}</td><td class='sub'>{_e(names)}</td></tr>")
        out_html.append("</table></div>")
        seen, figs = set(), []
        for cid, _st, _n, _t in rows:
            for f in sorted(cites.get(cid, {})):
                if f not in seen and (root / f).is_file():
                    seen.add(f)
                    figs.append(f)
        if figs:
            out_html.append("<h2>The figures this section is read off</h2>")
            for f in figs:
                rel = Path(f)
                try:
                    href = str(rel.relative_to("report")) if str(rel).startswith("report/") \
                        else "../" + str(rel)
                except Exception:                                     # noqa: BLE001
                    href = "../" + str(rel)
                out_html.append(f'<figure><img src="{_e(href)}" alt="{_e(rel.name)}">'
                                f'<figcaption class="sub">{_e(rel.name)}</figcaption></figure>')

    out_html.append("<h2>What this test does not cover</h2><div class='warn'><ul>"
                    + "".join(f"<li>{_e(x)}</li>" for x in NARROW) + "</ul></div>")
    d = _report_dir(out, plugin)
    d.mkdir(parents=True, exist_ok=True)
    path = d / page_name(plugin)
    path.write_text(_page(f"{title} — scProfile", "".join(out_html)), encoding="utf-8")
    return path


def _md(text):
    """The smallest markdown the section needs: headings, tables, bold, code, paragraphs.

    NOT A MARKDOWN LIBRARY. The host depends on numpy and pandas and nothing else, and a
    dependency added so a document can have italics is a dependency every plugin environment
    then has to resolve around.
    """
    import html as _h
    import re as _re

    out, rows = [], []

    def _flush_table():
        if not rows:
            return
        head, body = rows[0], [r for r in rows[1:] if not set(r) <= set("-: |")]
        out.append('<div class="wrap"><table><tr>'
                   + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr>"
                   + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                             for r in body) + "</table></div>")
        rows.clear()

    def _inline(t):
        t = _h.escape(str(t).strip())
        t = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = _re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        return t

    para = []
    for line in str(text).splitlines():
        st = line.strip()
        if st.startswith("|") and st.endswith("|"):
            if para:
                out.append("<p>" + _inline(" ".join(para)) + "</p>")
                para = []
            rows.append([c.strip() for c in st.strip("|").split("|")])
            continue
        _flush_table()
        if not st:
            if para:
                out.append("<p>" + _inline(" ".join(para)) + "</p>")
                para = []
            continue
        if st.startswith("#"):
            if para:
                out.append("<p>" + _inline(" ".join(para)) + "</p>")
                para = []
            lvl = min(len(st) - len(st.lstrip("#")), 4)
            out.append(f"<h{lvl}>{_inline(st.lstrip('#'))}</h{lvl}>")
            continue
        if st.startswith(("- ", "* ")):
            if para:
                out.append("<p>" + _inline(" ".join(para)) + "</p>")
                para = []
            out.append(f"<ul><li>{_inline(st[2:])}</li></ul>")
            continue
        if st.startswith(">"):
            out.append(f'<div class="warn">{_inline(st.lstrip("> "))}</div>')
            continue
        para.append(st)
    _flush_table()
    if para:
        out.append("<p>" + _inline(" ".join(para)) + "</p>")
    return "".join(out)


#: WHAT THIS TEST DOES NOT YET COVER. Named, because a test whose limits are unwritten gets used
#: as though it had none. Each line is a concrete gap, not a disclaimer.
NARROW = (
    "only the RESULTS section - a paper is also methods, discussion and a figure legend, and "
    "none of those is exercised here",
    "only claims that CITE A FIGURE - a claim resting on a table, or on a number in the text, "
    "is invisible to this ledger",
    "the REVIEWER is unspecified - this records that a round happened and what it decided, not "
    "who is competent to hold it, and a project with no reviewer has no test",
    "MISSING figures are found only INDIRECTLY - a gap surfaces when somebody tries to write "
    "the claim that needs it, so the test sees only as far as the writer's imagination",
    "it does not ask whether a figure is COMPREHENSIBLE - a correct claim read off an "
    "unreadable panel passes",
    "no NEGATIVE CONTROL - the loop has never been run against a figure set known to be sound, "
    "so how often it kills a TRUE claim is unmeasured",
    "ROUNDS are counted, not scored - nothing here says when enough review has happened",
    "run against ONE design shape and ONE method so far - one factor, three factors, no design "
    "at all, and time-course or nested designs are untested",
)
