"""The agent's side of a run, as an ordered list of tasks with state read off the run itself.

WHY THIS EXISTS. scProfile is run by an agent, and half the work is the agent's: looking at the
figures, writing the result, defending the claims. That half had a command for each step and no
interface over them - so it depended on the agent remembering the order, and the record shows
what that produces. In this project's whole history: 120 figure looks, and `run --section` used
ZERO times. The steps existed and the phase never ran.

A PBS JOB CANNOT WAIT FOR AN AGENT. The job fits, draws, and seals, unattended, and the agent
works between jobs. So the handoff has to be an artifact the job leaves behind: what remains to
be done, in order, with the command for each and the state of each read off the run. That is
this module.

STATE IS DERIVED AND NEVER STORED. A task is done when the ARTIFACT that proves it exists - a
brief on disk, no outstanding figures, a section that is authored rather than composed, claims in
the ledger. A stored status file would be a fifth artifact to keep in step with four others, and
this project has already paid for reports that described a state the run had moved past. Nothing
here can say "written" about a section the composer has since regenerated.

THE HOST OWNS THE PHASES; THE PLUGIN OWNS THEIR CONTENT. Read, look, write, carry in, defend is
the same sequence whatever the method is. What the brief holds and which template applies are
declared by the plugin, so a new method gets this interface without the host learning anything
about it.
"""
from __future__ import annotations

import json
from pathlib import Path

#: A task is one of these. `blocked` means an earlier task has to happen first - stated so an
#: agent does not start work whose input is not there yet.
DONE, PENDING, BLOCKED = "done", "pending", "blocked"

NAME = "AGENDA.md"


def _authored(run, plugin):
    """(exists, authored) for the plugin's section. Composed is not authored."""
    from . import compose as C
    from . import paper as P

    p = P._root(run, plugin) / P.draft_name(plugin)
    if not p.is_file():
        return False, False
    head = p.read_text(encoding="utf-8").strip()
    return True, bool(head) and not head.startswith(C.COMPOSED_MARK)


def tasks(run, plugin, spec=None):
    """[{id, title, state, why, do}] - the agent's remaining work on this run, in order."""
    from . import brief as B
    from . import review as R

    run = Path(run)
    pay = B._payload(run)
    spec = spec if spec is not None else ((pay.get("kernels") or {}).get(plugin) or {}).get("spec")

    brief = run / "kernels" / plugin / B.NAME
    try:
        out = R.outstanding(run, plugin) or []
    except Exception:                                                     # noqa: BLE001
        out = []
    exists, authored = _authored(run, plugin)
    claims = list((run / "kernels" / plugin).glob("PAPER_CLAIMS*.jsonl"))
    tmpl = B.template_of(spec)

    t = [{"id": "brief", "title": "Read the writing brief",
          "state": DONE if brief.is_file() else PENDING,
          "why": "the evidence this result is written from, with every number's file named",
          "do": f"scprofile write --out {run} --plugin {plugin}"},
         {"id": "look", "title": f"Open the figures ({len(out)} outstanding)",
          "state": DONE if not out else PENDING,
          "why": "every figure defect found in this project was found by opening the image "
                 "while the suite was green; a table shows none of them",
          "do": f'scprofile review --out {run} --plugin {plugin} --figure <path> --note "..."'},
         {"id": "write", "title": "Write the result",
          "state": DONE if authored else (BLOCKED if out else PENDING),
          "why": f"against {B.SKILL}/SKILL.md"
                 + (f" and the template this plugin declares, "
                    f"{B.SKILL}/templates/{tmpl}.md" if tmpl
                    else ", which names no template for this plugin"),
          "do": "write it, then carry it in with the next task"},
         {"id": "carry", "title": "Carry the written result into a run",
          "state": DONE if authored else BLOCKED,
          "why": "a section outside a run has no run key and its citations resolve to nothing; "
                 "one run produces all of its output, so it enters on a run and is not patched "
                 "into this one",
          "do": "scprofile run ... --section <file>"},
         {"id": "defend", "title": "Record the claims and what review did to them",
          "state": DONE if claims else (PENDING if authored else BLOCKED),
          "why": "a claim is bound to the figures it cites, so a redraw makes it stale and the "
                 "ledger refuses a citation the run does not contain",
          "do": f'scprofile paper --out {run} --plugin {plugin} --claim "..." --cites <figs>'}]
    return t


def outstanding(run, plugin, spec=None):
    """The tasks that are not done."""
    return [x for x in tasks(run, plugin, spec) if x["state"] != DONE]


def write_agenda(run, plugin, spec=None):
    """Write `kernels/<plugin>/AGENDA.md`. Returns its path.

    EMITTED BY THE RUN, so the handoff does not depend on anyone asking. A PBS job seals and
    leaves this behind; the agent picks it up without having to know what step it is on.
    """
    t = tasks(run, plugin, spec)
    left = [x for x in t if x["state"] != DONE]
    L = [f"# Agenda - {plugin}", "",
         f"Run `{Path(run).name}`. The tool has done its half: it measured, drew, and wrote what "
         f"it can support. **The rest is the agent's**, and this is what remains.", "",
         f"**{len(t) - len(left)} of {len(t)} done.**", ""]
    for i, x in enumerate(t, 1):
        mark = {DONE: "x", PENDING: " ", BLOCKED: "-"}[x["state"]]
        L += [f"{i}. [{mark}] **{x['title']}** — {x['state']}",
              f"       {x['why']}",
              f"       `{x['do']}`", ""]
    if left:
        L += ["*A blocked task is waiting on an earlier one, not on the tool.*", ""]
    else:
        L += ["*Nothing outstanding. The result is written, carried into a run, and defended.*",
              ""]
    d = Path(run) / "kernels" / plugin
    d.mkdir(parents=True, exist_ok=True)
    p = d / NAME
    p.write_text("\n".join(L), encoding="utf-8")
    return p
