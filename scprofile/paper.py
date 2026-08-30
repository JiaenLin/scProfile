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
import os as _os
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
    """`<run>/report` - BESIDE the plugin's other pages, whichever plugin it is about.

    THE PAGE MUST LAND WHERE ITS SIBLINGS ARE. `page_name` says the file is called
    `<plugin>_paper.html` so it sorts beside `<plugin>.html`, `<plugin>_by_arm.html` and
    `<plugin>_by_sample.html` - and this returned `<run>/kernels/<plugin>/report`, where none of
    those three is. The reason given for the NAME was defeated by the DIRECTORY, the run index
    could not link the section, and a reader following the report would never meet it.

    The section's SOURCES - its draft and its claims ledger - do stay in the plugin's own
    directory, which is `_root`. Source beside the method, rendered page beside the other pages.
    """
    from . import kernels as _K
    return _K.run_report(out)


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


def _append(out, rec, plugin=""):
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
                         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, plugin)


def review(out, cid, verdict, why, *, reviewer="", replaces="", plugin=""):
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
                         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, plugin)


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
    rows = status(out, plugin)
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


def _plugin_spec_of(pay, plugin=""):
    """The declaration of the plugin being written about, out of report.json."""
    ks = (pay.get("kernels") or {})
    got = {}
    if plugin and plugin in ks:
        got = ks[plugin].get("spec") or ks[plugin] or {}
    elif len(ks) == 1:
        only = next(iter(ks.values()))
        got = only.get("spec") or only or {}
    # A RUN WRITTEN BEFORE THE DECLARATION WAS RECORDED still has to be writable from. Falling
    # back to discovery keeps older runs usable; it is second because the recorded copy is the
    # one that actually ran, and the source on disk may have moved since.
    if not (got.get("report") or {}).get("provides_evidence"):
        try:
            from . import kernels as _K
            live = (_K.discover() or {}).get(plugin or (next(iter(ks), "") if ks else ""))
            live = getattr(live, "spec", None) or (live if isinstance(live, dict) else None)
            if live:
                return dict(live)
        except Exception:                                                 # noqa: BLE001
            pass
    return got


def brief(out, plugin=""):
    """Everything needed to WRITE the section, read out of the run. Returns text.

    IT OPENS WITH THE DESIGN'S OWN QUESTIONS, NOT WITH THE PANELS. A writer handed a directory of
    figures writes about the figures; a writer handed the questions the design supports writes
    about the experiment and then goes looking for the figure that answers each. The order of
    those two decides whether a section is a survey of the tooling or a result - and the first
    section written from this brief was a survey, because the brief led with panels.

    The specification comes from `planner.result_spec` and needs no run at all; what the run adds
    is which of the specified panels actually exist.

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

        # THE DESIGN'S OWN QUESTIONS, BEFORE ANY PANEL IS MENTIONED. `planner.result_spec` needs
        # only the design table and the plugin's declaration, so this section of the brief is
        # identical whether or not anything has run - and a writer meets the experiment before
        # meeting the output. The first section written from this brief was a survey of the
        # tooling because the brief led with panels.
        try:
            from .planner import (result_spec as _rs, spec_text as _st,
                                  delivered as _dl, gap_text as _gt)
            _spec = _rs(des, _plugin_spec_of(pay, plugin))
            L += [_st(_spec), ""]
            # AND WHAT THIS RUN ACTUALLY HAS, against that specification. A missing panel is a
            # gap to report in the section, not a section to quietly leave out.
            _figs = [f.get("file") or f.get("id") or ""
                     for k in (pay.get("kernels") or {}).values()
                     for f in (k.get("figures") or [])]
            L += [_gt(_dl(_spec, _figs)), ""]
            # THE SAME LABELS THE PANEL USES, so a section and a panel section are one thing
            # seen twice. The panel is built from `design_panel.comparisons` and the written
            # section was built from whatever headings its author chose, so the two agreed on
            # nothing but the run they came from and a reader had to re-derive the mapping.
            from .compare_panel import control_basis as _cb
            from .design_panel import comparisons as _cm

            _ctrl = _cb(des, controls=pay.get("controls"))
            if _ctrl:
                L += ["THE REFERENCE OF EACH CONTRAST - everything is measured against these:"]
                L += [f"  {f}: against {lv!r}   ({why})" for f, (lv, why) in sorted(_ctrl.items())]
                L += [""]
            L += ["USE THESE HEADINGS, VERBATIM, IN THIS ORDER. They are the panel's section "
                  "names, so a reader moving between the two documents lands in the same place:"]
            for _c in _cm(des):
                L += [f"  {_c.get('kind', '').upper():12s} {_c.get('label', '')}"
                      f"   -- {_c.get('question', '')}"]
            L += ["", "A question with no panel is a gap to report, not a section to skip.", ""]
        except Exception as _e:                                           # noqa: BLE001
            L += [f"(the design's questions could not be enumerated: {_e})", ""]

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
            _pj = _json.loads((root / "report" / "panels.json")
                              .read_text(encoding="utf-8")).get(k, {})
            placed = _pj.get("cohort") or []
            native = _pj.get("native") or []
        except Exception:                                                 # noqa: BLE001
            placed, native = [], []
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

        # THE WRAPPED TOOL'S OWN COMPARISON PANELS, GROUPED BY CONTRAST. These are what a
        # subsection about a contrast is written off: the method's own function, its own
        # statistic, its own encoding. They live on the arms page rather than the first page,
        # and a brief that read only the first page listed none of them - so the section written
        # from it described the host's panels and never mentioned the tool's answer.
        if native:
            byc = {}
            for f_ in native:
                byc.setdefault(str(f_.get("label") or ""), []).append(f_)
            L += [f"### The tool's own comparison panels ({len(native)} over {len(byc)} "
                  f"contrast(s)) — CITE THESE FOR ANY CLAIM ABOUT A CONTRAST", ""]
            for lab in sorted(byc):
                L += [f"  CONTRAST {lab}"]
                for f_ in byc[lab]:
                    cap = f_.get("caption")
                    lead, rest = (cap if isinstance(cap, (list, tuple)) and len(cap) == 2
                                  else (cap or "", ""))
                    L += [f"    {f_.get('path')}",
                          f"       SHOWS : {' '.join(str(lead).split())}"]
                    if rest:
                        L += [f"       LIMITS: {' '.join(str(rest).split())}"]
                L += [""]
        else:
            L += ["The tool drew no comparison panel of its own in this run. Say so, and say "
                  "which contrasts were left to the host's encodings.", ""]
    L += ["---", "Write the Results section you would submit. Then record each claim against the",
          "figures you read it off, put it to a reviewer, and record what happened:", "",
          "  scprofile paper --out <RUNDIR> --claim '...' --cites <fig>,<fig>",
          "  scprofile paper --out <RUNDIR> --round <id> --verdict standing|narrowed|withdrawn"
          " --why '...'",
          "  scprofile paper --out <RUNDIR> --write section.md",
          "  scprofile paper --out <RUNDIR> --render", ""]
    return "\n".join(L)


def next_step(out, plugin=""):
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
                  "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, plugin)
    return _root(out, plugin) / draft_name(plugin)


def read_draft(out, plugin=""):
    """The authored section, or "" when none has been written."""
    p = _root(out, plugin) / draft_name(plugin)
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _captions(out, plugin=""):
    """{figure path: the caption it was drawn with} - read from the run's own `panels.json`.

    The reporter records what it put on each page, caption included. Reading it here is what
    lets the paper print a real legend instead of a filename, and it works for any plugin
    because the reporter wrote it for all of them.
    """
    import json as _json

    try:
        pj = _json.loads((Path(out) / "report" / "panels.json")
                         .read_text(encoding="utf-8")).get(plugin) or {}
    except (OSError, ValueError):
        return {}
    caps = {}
    for group in ("cohort", "native", "contrast", "arm"):
        for f in (pj.get(group) or []):
            cap = f.get("caption")
            if isinstance(cap, (list, tuple)):
                cap = " ".join(str(x) for x in cap if x)
            caps[str(f.get("path") or "")] = " ".join(str(cap or "").split())
    return caps


def _figure_index(out, plugin=""):
    """{figure path: number} for this run, or `{}` - the numbering the composed prose cites."""
    import json as _json

    try:
        pay = _json.loads((Path(out) / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    from . import compose as _C

    try:
        return _C.figure_index(out, plugin, _plugin_spec_of(pay, plugin), pay.get("design") or {})
    except Exception:                                                     # noqa: BLE001
        return {}


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
    rows = status(out, plugin)
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
        # THE FIGURES, NUMBERED, WITH THE LEGEND THEY WERE DRAWN WITH.
        #
        # They were printed in an unordered block captioned with their FILENAMES - the whole of
        # the legend a reader of the paper got. Nothing said what a panel showed, what its
        # colours meant, or which sentence it belonged to, so no number in the text could be
        # checked against any picture. A paper numbers its figures and its text points at them.
        #
        # The order and the numbers come from `compose.figure_index`, the same index the prose
        # cites through, so "Figure 3" in a sentence and the plate printed under Figure 3 are one
        # object by construction. Any figure a claim cites that the index does not carry is
        # printed after them rather than dropped.
        idx = _figure_index(out, plugin)
        caps = _captions(out, plugin)
        seen, figs = set(), []
        for f in sorted(idx, key=lambda x: idx[x]):
            if (root / f).is_file():
                seen.add(f)
                figs.append(f)
        for cid, _st, _n, _t in rows:
            for f in sorted(cites.get(cid, {})):
                if f not in seen and (root / f).is_file():
                    seen.add(f)
                    figs.append(f)
        if figs:
            out_html.append("<h2>Figures</h2>")
            for i, f in enumerate(figs, 1):
                # RELATIVE TO WHERE THE PAGE ACTUALLY IS, computed rather than assumed. The
                # href was hard-coded as "../" + path, which was right while every page sat in
                # `<run>/report/`. A plugin's page now sits in `<run>/kernels/<plugin>/report/`,
                # three levels down, and every `<img>` pointed at nothing - the section rendered
                # with its claims, its verdicts and NO FIGURES, which is the one thing a figure
                # panel has to have.
                rel = Path(f)
                href = _os.path.relpath(root / rel, _report_dir(out, plugin))
                n = idx.get(f, i)
                # THE LEGEND IS PRINTED WHOLE. `report.CAPTION_LEAD_WORDS` splits a caption into
                # a lead and a disclosure, which is right for a page of a hundred panels and
                # wrong for a paper: a figure legend that stops at 32 words is not a legend. No
                # cap and no disclosure here - what the figure was drawn with is what is printed.
                leg = caps.get(f, "")
                out_html.append(
                    f'<figure><img src="{_e(href)}" alt="Figure {n}">'
                    f'<figcaption><b>Figure {n}.</b> {_e(leg) if leg else ""}'
                    f'<span class="sub"> Source: <code>{_e(str(rel))}</code>.</span>'
                    f'</figcaption></figure>')

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


def ensure_section(out, *, plugin="", spec=None, design=None, run_key=""):
    """Compose a section from this run's tables if none has been authored. Returns the path.

    EVERY RUN SHIPS A SECTION. The panel was made a mechanism and the writing was not, so a fresh
    checkout and a fresh run produced figures and no document - and the numbers in the documents
    that did exist had been read off tables by a person and typed, which is the failure this
    project names elsewhere applied to the manuscript itself.

    An AUTHORED section always wins and is never overwritten: this only fills the gap. What the
    run guarantees is that a section exists, that every number in it is traceable to a table in
    the same run, and that it cannot silently disagree with the panel beside it.
    """
    from . import compose as _C

    existing = _root(out, plugin) / draft_name(plugin)
    if existing.is_file():
        head = existing.read_text(encoding="utf-8").strip()
        # AN AUTHORED SECTION IS NEVER OVERWRITTEN. A COMPOSED ONE IS REBUILT: otherwise a
        # rebuild keeps a section written by older code beside figures drawn by newer, which is
        # the staleness this project treats as worse than being wrong, because it reads correctly.
        if head and not head.startswith(_C.COMPOSED_MARK):
            return None
    text = _C.section(out, plugin, spec=spec, design=design, run_key=run_key)
    if not text.strip():
        return None
    _root(out, plugin).mkdir(parents=True, exist_ok=True)
    existing.write_text(text, encoding="utf-8")
    # AND THE CLAIMS, BOUND TO FIGURES. A section renders with the figures its CLAIMS cite, so
    # composing prose alone produced a document with no pictures beside the panel that has them
    # all. Each composed claim cites the plates the panel places for that contrast, chosen by the
    # plugin's own declared routes, so the two documents show the same figures by construction.
    if not read_ledger(out, plugin):
        for sentence, cites in _C.claims(out, plugin, spec=spec, design=design):
            try:
                claim(out, sentence, cites, author="composed", plugin=plugin)
            except Refused:
                continue
    return existing


def panel_name(plugin=""):
    """`report/panel.html`, or `report/<plugin>_panel.html`. Beside the section, as a sibling."""
    return "panel.html" if not plugin else f"{plugin}_panel.html"



def _re_strip_placeholders(html_text):
    """Remove any ALSO placeholder that was never filled, so none reaches the page."""
    import re as _re
    return _re.sub(r"<!--ALSO:[^>]*-->", "", html_text)

def panel(out, *, run_key="", plugin=""):
    """Write `report/<plugin>_panel.html`: ONE PLATE PER EVIDENCE NEED, PER COMPARISON.

    THE FIGURE PANEL IS A DELIVERABLE AND IT WAS NOT BEING PRODUCED. The run writes an arms page
    carrying every between-arm figure it drew - on this cohort, 426 of them - which is an
    appendix, not a panel. A panel is the subset a reader is asked to look at, and until now the
    only way to get one was to pick figures by hand into a document with no run key. That is a
    draft by this project's own rule, whatever it looks like.

    So the selection is DERIVED, not curated. For every comparison the design supports, and every
    piece of evidence that comparison needs, the plugin's `provides_evidence` names the route -
    `native:<function>` or `host:<panel kind>` - and the plate is the figure in THAT contrast
    which that function drew, matched through `native.function_for`, the same inversion the
    captions use. A need with no route is printed as a gap rather than skipped.

    Nothing here is specific to a method or a project: a three-factor design gives more
    comparisons and therefore more plates, from the same code.
    """
    import json as _json

    root = Path(out)
    try:
        pay = _json.loads((root / "report.json").read_text(encoding="utf-8"))
    except Exception:                                                     # noqa: BLE001
        return None
    des = pay.get("design") or {}
    if not des:
        return None
    from . import native as _NAT
    from .design_panel import comparisons as _cmps
    from .evidence import NEEDS as _NEEDS
    from .report import _e, _page                                         # noqa: PLC0415

    spec = _plugin_spec_of(pay, plugin)
    routes = ((spec.get("report") or {}).get("provides_evidence") or {})
    declared = (spec.get("native_plots") or {})
    try:
        placed = _json.loads((root / "report" / "panels.json").read_text(encoding="utf-8"))
        native = (placed.get(plugin) or {}).get("native") or []
    except Exception:                                                     # noqa: BLE001
        native = []
    # index the run's native panels by (contrast label, the function that drew them)
    by = {}
    for f in native:
        fn = _NAT.function_for(declared, str(f.get("path") or ""))
        if fn:
            by.setdefault((str(f.get("label") or ""), fn), []).append(f)
    # HOST PANELS RESOLVE THROUGH THE PANEL REGISTRY. `panels.IMPLEMENTED` records where each
    # kind is drawn, ending in the id stem the figure carries; matching on that stem is how a
    # `host:` route finds its plate. Without this every need served by a host panel read as a
    # gap on a page that had the figure in it.
    from . import panels as _PN

    host = list((placed.get(plugin) or {}).get("contrast") or []) + \
        list((placed.get(plugin) or {}).get("arm") or []) + \
        list((placed.get(plugin) or {}).get("cohort") or [])
    stems = {}
    for kind, where in (_PN.IMPLEMENTED or {}).items():
        stem = str(where).split("\u2014")[-1].strip().split(",")[0].strip()
        if stem:
            stems[kind] = stem

    cmps = _cmps(des)
    # A FIGURE IS PLACED ONCE. Several evidence needs can route to the same panel - the presence
    # map answers three of them - and the panel emitted it for every need of every comparison:
    # one figure, twenty-one times, which reads as though absence were the finding. Once is
    # enough for the reader; the needs it also answers are named beside it instead.
    placed_at, also = {}, {}
    H = [f"<h1>Figure panel &mdash; {_e(plugin or 'this run')}</h1>"]
    if run_key:
        H.append(f'<p class="sub">Every plate below is in run <code>{_e(run_key)}</code>. '
                 f'The selection is derived: one plate per piece of evidence each comparison '
                 f'needs, chosen by the route the plugin declares for that need, not by hand. '
                 f'The full set of between-arm figures is on the arms page.</p>')
    n_plate, n_gap = 0, 0
    # ALIASING IS STATED ONCE. It was printed at the head of every comparison it affects - four
    # times on this design - which put a design fact where the finding should be and read as
    # though the comparison had been withheld. It has not been: the contrast is drawn and the
    # result stands; the aliasing is a fact about attribution and belongs in one line.
    _alias = {}
    for c in cmps:
        for a_ in (c.get("aliased_with") or []):
            _alias.setdefault(str(c.get("factor") or ""), set()).add(str(a_))
    if _alias:
        H.append('<p class="sub">' + "; ".join(
            f"<b>{_e(f)}</b> varies together with {_e(', '.join(sorted(v)))} across every "
            f"sample, so a difference along {_e(f)} is a difference along both"
            for f, v in sorted(_alias.items())) + ".</p>")

    for c in cmps:
        label = c.get("label") or c.get("question") or ""
        H.append(f'<h2>{_e(str(c.get("kind", "")).upper())} &mdash; {_e(label)}</h2>')
        H.append(f'<p class="sub">{_e(str(c.get("question") or ""))}</p>')
        for need, route in sorted(routes.items()):
            # EVERY ROUTE THAT RESOLVES, NOT ONLY THE FIRST. Two of the tool's own functions
            # answer "which populations differ" - the differential network and the differential
            # heatmap - and stopping at the first match meant the heatmap was drawn on every run
            # and placed in none. They read differently: one shows the shape of the change, the
            # other lets a reader find a pair.
            found = []
            for r in (route or []):
                r = str(r)
                if r.startswith("native:"):
                    fn = r.split(":", 1)[1]
                    for h in (by.get((label, fn)) or []):
                        found.append((fn, h))
                elif r.startswith("host:"):
                    kind = r.split(":", 1)[1]
                    stem = stems.get(kind)
                    if not stem:
                        continue
                    # a between-arm panel must be THIS contrast's; a cohort panel has no label
                    hits = [f for f in host
                            if str(f.get("id") or "").startswith(stem)
                            and (not f.get("label") or str(f.get("label")) == label)]
                    if hits and not found:
                        found.append((f"{kind} (drawn by scProfile)", hits[0]))
            # `NEEDS` maps a need to (question, why). It is a tuple, not a mapping - the
            # first version called .get on it and raised on the first plate.
            meta = _NEEDS.get(need) or ()
            title = str(meta[0]) if meta else str(need)
            why = str(meta[1]) if len(meta) > 1 else ""
            if not found:
                n_gap += 1
                H.append(f'<div class="bad"><b>{_e(title)}</b> &mdash; no plate. '
                         f'The route declared for this need drew nothing in this contrast.'
                         + (f' <span class="sub">{_e(why)}</span>' if why else "")
                         + '</div>')
                continue
            for fn, f in found:
                key = str(f.get("path") or "")
                if key in placed_at:
                    also.setdefault(placed_at[key], []).append(title)
                    continue
                placed_at[key] = (label, title)
                n_plate += 1
                cap = f.get("caption")
                lead, rest = (cap if isinstance(cap, (list, tuple)) and len(cap) == 2
                              else (cap or "", ""))
                rel = "../" + str(f.get("path") or "")
                # THE CONTRAST IS NAMED ON THE PLATE. Lifted out of the page a figure carried
                # only the tool's own generic title, so nothing on it said which two arms it
                # compared or in which direction.
                H.append(f'<figure><figcaption class="lead"><b>{_e(title)}</b> '
                         f'&mdash; <code>{_e(fn)}</code> '
                         f'&middot; <b>{_e(label)}</b></figcaption>'
                         f'<img src="{_e(rel)}" alt="{_e(title)} — {_e(label)}">'
                         f'<figcaption>{_e(str(lead))}'
                         + f"<!--ALSO:{label}|{title}-->"
                         + (f' <span class="sub">{_e(str(rest))}</span>' if rest else "")
                         + '</figcaption></figure>')

    page = "".join(H)
    for (lab, ttl), extra in also.items():
        line = (" It also answers: " + "; ".join(sorted(set(extra))) + ".") if extra else ""
        page = page.replace(f"<!--ALSO:{lab}|{ttl}-->", _e(line) if line else "")
    page = _re_strip_placeholders(page)
    H = [page]
    H.insert(1, f'<p class="sub"><b>{n_plate}</b> plate(s) over <b>{len(cmps)}</b> comparison(s)'
                + (f', and <b>{n_gap}</b> need(s) with no plate' if n_gap else '') + '.</p>')
    H.append(f'<p class="sub"><a href="{_e(page_name(plugin))}">the written section</a> '
             f'&middot; <a href="index.html">the run index</a></p>')
    d = _report_dir(out, plugin)
    d.mkdir(parents=True, exist_ok=True)
    f = d / panel_name(plugin)
    f.write_text(_page(f"{plugin} figure panel — scProfile", "".join(H)), encoding="utf-8")
    return f
