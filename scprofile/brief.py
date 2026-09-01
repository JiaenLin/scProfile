"""The writing brief: everything an agent needs to write a result, gathered from the run.

WHY THIS EXISTS. The section used to be ASSEMBLED BY CODE - headings built from f-strings, a
limitations paragraph ranked and joined, a sentence emitted when two scales diverged past a
threshold. That is deterministic and traceable and it is not writing. It cannot decide what
matters, synthesise across levels, or narrow to a focus, which is the one thing the writing
template asks for: a section that reports every pathway equally reports none.

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
         f"3. Write the result against `{SKILL}/SKILL.md`"
         + (f" and the template it names for this method, `{SKILL}/templates/{tmpl}.md`."
            if tmpl else ", which names no template for this plugin - say so rather than "
                          "borrowing another method's."),
         f"4. Carry it back into the run: `scprofile run --section <file>`. A section outside the "
         f"run has no run key and its citations resolve to nothing.", "",
         f"**You are writing about {subject}.** The reference level of every factor is "
         + (", ".join(f"`{k} = {v}`" for k, v in sorted(ctl.items())) if ctl
            else "not declared, so direction cannot be assumed") + ".", ""]

    L += ["## The contrasts, in reading order", "",
          "| contrast | reference | against | ratio | per observation | elements differing |",
          "|---|---|---|---|---|---|"]
    def _cell(x):
        # A CONTRAST LABEL CONTAINS A PIPE - `age | diet = chow` - and this is a pipe-delimited
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

    L += ["## Figures to look at", "",
          "Numbered as the paper numbers them. **Open each one before writing about it.**", ""]
    outstanding = set()
    try:
        outstanding = {str(x) for x in (R.outstanding(run, plugin) or [])}
    except Exception:                                                     # noqa: BLE001
        pass
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
    p = d / NAME
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return p
