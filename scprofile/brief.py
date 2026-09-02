"""The writing brief: everything an agent needs to write a result, gathered from the run.

WHY THIS EXISTS. The section used to be ASSEMBLED BY CODE - headings built from f-strings, a
limitations paragraph ranked and joined, a sentence emitted when two scales diverged past a
threshold. That is deterministic and traceable and it is not writing. It cannot decide what
matters, synthesise across levels, or narrow to a focus, which is the one thing the writing
template asks for: a section that reports every element equally reports none.

scProfile is run BY AN AGENT. So the writing is the agent's, and the tool's job is to hand it
the evidence in one place - not to imitate the writing badly.

WHAT THIS IS NOT. It is not a draft, and nothing in it is a sentence to be pasted. Every entry
is a measurement with the file it came from, so a claim can be traced back and a number cannot
enter the manuscript from a conversation.

THE ORDER OF THE PHASE, which the brief states to whoever reads it:

    1. read the brief;
    2. OPEN THE FIGURES it names, and record what was seen (`scprofile review`);
    3. write, against the skill and the plugin's declared template;
    4. carry it back in with `run --section`, where the claims are checked.

Step 2 is not advice. A figure is where a defect lives that no table shows - an encoding that
contradicts its legend, a panel whose ranking hides the thing it was drawn for - and every one
of those found in this project was found by opening the image. The review ledger binds a look to
the image's sha256, so a redraw destroys the record and the figure returns to the outstanding
list; the brief lists what is outstanding and `--strict` is what a gate reads.
"""
from __future__ import annotations

import json
from pathlib import Path

NAME = "WRITING_BRIEF.md"

#: THE FIGURE SET AS A TRANSFER LIST, one run-relative path per line, in the order the paper
#: numbers them.
#:
#: The brief NAMES every figure, which is enough for a reader and not enough for an agent whose
#: image viewer is on a different machine from the run - the normal case under a scheduler. That
#: agent has to get the set in front of itself before it can look at anything, and with only a
#: markdown list to work from it writes a throwaway parser, which is the in-house script this
#: tool exists to make unnecessary. One path per line is what every transfer tool already
#: accepts: `rsync --files-from`, `tar -T`, `xargs cp`.
FIGURE_LIST = "FIGURES.txt"

#: Where the agent-facing instructions live. Named in the brief rather than remembered, so an
#: agent that has never seen this project can find them from the run alone.
SKILL = ".claude/skills/result-section"


def _payload(run):
    try:
        return json.loads((Path(run) / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def template_of(spec):
    """The template this plugin writes with, or "" - DECLARED, never inferred from the name.

    A plugin ships the template that suits its method, the same way it ships its panels. The
    host must not map a plugin name to a template: that is the one place where adding a second
    method quietly stops working.
    """
    return str(((spec or {}).get("report") or {}).get("writing_template") or "")


def write_brief(run, plugin, spec=None, design=None):
    """Write `kernels/<plugin>/WRITING_BRIEF.md`. Returns its path, or None.

    Built from the same readers the composer uses, so the brief and any composed fallback cannot
    disagree about what the run measured.
    """
    from . import compose as C
    from . import review as R

    run = Path(run)
    pay = _payload(run)
    spec = spec if spec is not None else ((pay.get("kernels") or {}).get(plugin) or {}).get("spec")
    design = design if design is not None else (pay.get("design") or {})
    f = C.findings(run, plugin, spec)
    if not f:
        return None

    idx = C.figure_index(run, plugin, spec, design)
    ctl = C._controls(run)
    order = C._order(f, design, ctl)
    tmpl = template_of(spec)
    subject = str(((spec or {}).get("report") or {}).get("subject") or "features")

    L = [f"# Writing brief - {plugin}", "",
         f"Run `{run.name}`. Everything below was measured by this run and names the file it "
         f"came from. **Nothing here is a sentence to reuse**: it is the evidence the result is "
         f"written from.", "",
         "## What to do, in order", "",
         f"1. Read this brief.",
         f"2. **Open every figure listed under _Figures to look at_** and record what you saw:",
         f"   `scprofile review --out {run} --plugin {plugin} --figure <path> --note \"...\"`",
         f"   A note is refused if it is too short, or copied from another figure. The record is "
         f"bound to the image, so a figure redrawn since it was looked at comes back onto the "
         f"list.",
         f"   The same set is written as a transfer list, one run-relative path per line, at "
         f"`kernels/{plugin}/{FIGURE_LIST}` - so the images can be brought to whatever opens "
         f"them in ONE operation instead of parsed out of this document. "
         f"`scprofile agenda --out {run}` prints the command for the mode this run is in.",
         f"3. Write the result against `{SKILL}/SKILL.md`"
         + (f" and the template it names for this method, `{SKILL}/templates/{tmpl}.md`."
            if tmpl else ", which names no template for this plugin - say so rather than "
                          "borrowing another method's."),
         f"4. Carry it back into the run: `scprofile run --section <file>`. A section outside the "
         f"run has no run key and its citations resolve to nothing.", "",
         f"**You are writing about {subject}.** The reference level of every factor is "
         + (", ".join(f"`{k} = {v}`" for k, v in sorted(ctl.items())) if ctl
            else "not declared, so direction cannot be assumed") + ".", ""]

    # THE DESIGN THE RUN RESOLVED, FIRST, AND AS BIOLOGY RATHER THAN AS BOOKKEEPING.
    #
    # The brief handed over contrasts, figures and caveats - every input to the writing was the
    # run describing itself - so the section that came back described the run. It reported that a
    # matrix programme rose from 1.0 to 17.2 without saying what a rise in that programme IS, and
    # it discussed the factors as labels on a contrast table rather than as the interventions the
    # experiment performed. A brief whose whole vocabulary is internal produces a result whose
    # whole vocabulary is internal.
    #
    # So the design is stated first, in the factors' own names: what was varied, from what to
    # what, how the arms are made, and what QUESTION each contrast asks. None of it is specific to
    # a study - it is read from the design table, and the question templates use whatever the
    # factors happen to be called.
    _facs = {}
    for _row in (design or {}).values():
        for _k, _v in (_row or {}).items():
            _facs.setdefault(str(_k), set()).add(str(_v))
    _facs = {k: sorted(v) for k, v in _facs.items() if len(v) > 1}
    if _facs:
        _arms = len(set(tuple(sorted((str(k), str(v)) for k, v in (r or {}).items()
                                     if str(k) in _facs))
                        for r in (design or {}).values()))
        L += ["## The design this run resolved", "",
              f"**{len(_facs)} factor(s), crossed into {_arms} arm(s) over "
              f"{len(design or {})} sample(s).**", ""]
        for _k in sorted(_facs):
            _lv = _facs[_k]
            _ref = str(ctl.get(_k) or "")
            _oth = [x for x in _lv if x != _ref] or _lv
            L.append(f"- **`{_k}`**: {', '.join('`%s`' % x for x in _lv)}"
                     + (f" — reference `{_ref}`, so every `{_k}` contrast asks what changes when "
                        f"`{_k}` goes from `{_ref}` to `{_oth[0]}`." if _ref else "."))
        L += ["", "**The questions the crossing supports, in the order they are worth asking:**",
              "",
              "1. *What does each factor do on its own, inside one level of the other?* Those are "
              "the simple effects, and there is one per level - they are separate results, not "
              "repeats of each other.",
              "2. *Does one factor's effect DEPEND on the other?* That is the interaction, the "
              "deepest question a crossed design answers, and the reason the experiment was "
              "crossed rather than run as two separate ones.",
              "3. *What does each factor do on average?* The marginals. They are averages over "
              "strata that may behave differently, so they are read AFTER the simple effects.",
              "",
              "**Write about the factors as the interventions they are, not as labels on a "
              "table.** The reader wants to know what happened to the system when each was "
              "applied, in the language of the field - what a change in these elements MEANS "
              "biologically, which processes they belong to, and what the pattern across the arms "
              "says about the system. A section that only reports which quantity moved has "
              "described the measurement and not the result.", ""]

    L += ["## The contrasts, in reading order", "",
          "| contrast | reference | against | ratio | per observation | elements differing |",
          "|---|---|---|---|---|---|"]
    def _cell(x):
        # A CONTRAST LABEL CAN CONTAIN A PIPE - a simple effect is named `<factor> | <other>
        # table. Unescaped, one label became three cells and every value after it shifted left.
        # The composer had this bug and it was fixed there; writing a second table by hand
        # reproduced it, which is what a second implementation of one thing is for.
        return str(x).replace("|", "\\|")

    def _num(x):
        # THREE SIGNIFICANT FIGURES, not sixteen. `3.221313010331362` is not more precise than
        # `3.22`, it is only harder to read, and a brief that is hard to read is skimmed.
        try:
            return f"{float(x):.3g}"
        except (TypeError, ValueError):
            return "—"

    for lab in order:
        d = f[lab]
        L.append(f"| {_cell(lab)} | {_cell(d.get('unit_reference') or d['reference'])} "
                 f"| {_cell(d.get('unit_against') or d['against'])} "
                 f"| {_num(d['ratio'])} | {_num(d.get('ratio_per_cell'))} "
                 f"| {d['n_significant']} of {d['n_tested']} |")
    L += ["", "*Read against both scales. Where a total and a per-observation figure disagree "
              "in size, say which one the claim is made on - the skill states the rule.*", ""]

    _con = str(pay.get("constraint_on_use") or "").strip()
    _binds = pay.get("constraint_binds") or {}
    _alias = {}
    try:
        from .design_panel import aliased as _aliased
        _alias = {k: v for k, v in (_aliased(design) or {}).items() if v}
    except Exception:                                                     # noqa: BLE001
        _alias = {}
    if _con or _alias:
        # AFTER THE DESIGN AND THE CONTRASTS, AND SHORT. The first version of this block opened
        # the brief, and the section that came back led with caveats and never said the biology -
        # which is the failure the writing guidance already names. What a design cannot separate
        # is a sentence the result carries where the contrast is stated and a paragraph at the
        # end; it is not the frame the argument is built in.
        L += ["## What the design cannot separate", "",
              "One line each, said where the contrast is stated and again in the limitations "
              "paragraph. **Not the frame of the argument** - a result that leads with its "
              "caveats has not reported anything.", ""]
        for _fac, mates in sorted(_alias.items()):
            L.append(f"- `{_fac}` is aliased with {', '.join('`%s`' % m for m in mates)}: they "
                     f"split the samples identically, so a difference along one is equally a "
                     f"difference along the others and this data cannot say which.")
        if _con:
            _who = ", ".join(f"`{k}` on {', '.join(v)}" for k, v in sorted(_binds.items()))
            L += [f"- The object carries an upstream constraint on use"
                  + (f", binding {_who}" if _who else "") + ": " + _con.split(".")[0].strip()
                  + ". A headline it forbids stays forbidden however strong the number is."]
        L += [""]

    L += ["## Figures to look at", "",
          "Numbered as the paper numbers them. **Open each one before writing about it.**", ""]
    # THE PAIRS ARE (path, state), NOT PATHS. Stringifying them produced "('a.png', 'unreviewed')"
    # and compared it against a path, so nothing ever matched and the brief marked NOTHING as
    # outstanding on a run where not one figure had been looked at. The list is the whole point
    # of this section; silently empty, it reads as "all reviewed" and the step gets skipped.
    #
    # AND THE FAILURE IS LOUD. This was wrapped in `except Exception: pass`, which is why the
    # defect above could not announce itself: a gate that cannot report its own breakage is a
    # gate that is off without anyone deciding to switch it off.
    outstanding = set()
    try:
        outstanding = {str(r) for r, _st in (R.outstanding(run, plugin) or [])}
    except Exception as _e:                                               # noqa: BLE001
        L.append(f"> **The review ledger could not be read ({_e}), so nothing below is marked "
                 f"as outstanding. Treat every figure as unreviewed.**")
        L.append("")
    ordered = [path for path, _n in sorted(idx.items(), key=lambda kv: kv[1])]
    for path, n in sorted(idx.items(), key=lambda kv: kv[1]):
        mark = " **(not yet looked at)**" if path in outstanding else ""
        L.append(f"- Figure {n}: `{path}`{mark}")
    L += [""]

    cav = ((pay.get("kernels") or {}).get(plugin) or {}).get("caveats") or []
    if cav:
        L += ["## What the run recorded against itself", "",
              f"{len(cav)} caveat(s), many repeated per unit. **The limitations paragraph is "
              f"yours to write from these** - ranked by what would change a conclusion, under "
              f"200 words. They are in `report.json` under `kernels.{plugin}.caveats`.", ""]

    L += ["## What this brief does not contain", "", 
          "An interpretation. The tool measured; the reading is yours, and the skill says what "
          "may be stated as a finding, what may be stated as a hypothesis, and what may not be "
          "stated at all.", ""]

    d = run / "kernels" / plugin
    d.mkdir(parents=True, exist_ok=True)
    (d / FIGURE_LIST).write_text("\n".join(ordered) + "\n", encoding="utf-8")
    p = d / NAME
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return p
