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

#: HOW THE COMPUTE HALF EXECUTES, which changes what the agent has to do about it and nothing
#: else. `pbs` is a scheduler: the work runs detached on another machine and cannot call back.
#: `local` is a subprocess: it finishes before the next line.
PBS, LOCAL = "pbs", "local"


def mode(explicit=""):
    """Which execution mode this machine is in. Detected, and overridable.

    Detection is a convenience and never a claim: an agent that knows better passes `--mode`,
    and the protocol says which mode it is describing so a wrong guess is visible rather than
    silently shaping the instructions.
    """
    if str(explicit or "").strip() in (PBS, LOCAL):
        return str(explicit).strip()
    import os
    import shutil
    if any(k.startswith("PBS_") for k in os.environ) or shutil.which("qstat"):
        return PBS
    return LOCAL


def execution_task(run, how=PBS):
    """Task zero: the compute half, and what the agent does about it in this mode.

    THE AGENT IS TOLD BEFORE THE RUN, NOT AFTER. On a scheduler the job runs detached and cannot
    call anyone, so an agent that does not know to watch it discovers the output whenever it next
    happens to look - and the cycle stretches to however long that is. Watching it and picking the
    output up the moment it seals is what keeps submit-watch-collect ONE run rather than three
    disconnected errands.
    """
    run = Path(run)
    sealed = (run / "SEALED.txt").is_file()
    started = (run / "report.json").is_file()
    if how == PBS:
        why = ("the compute runs DETACHED on another machine and cannot call you back. Submit "
               "it, then watch it - it is still one run, and the output is picked up the moment "
               "it seals rather than whenever you next think to look. Never run it on a login "
               "node.")
        do = ("submit as a batch job, then poll its state (`qstat -f <jobid>`) and follow the "
              "live log the job prints. It has finished when SEALED.txt appears in the run "
              "directory; the job writes AGENDA.md as its last act, so pick that up immediately.")
    else:
        why = "the compute runs in front of you and finishes before the next step begins"
        do = "scprofile run --h5ad <object> --out <run> ..."
    return {"id": "run", "title": "Run the pipeline",
            "state": DONE if sealed else (PENDING if not started else PENDING),
            "why": why, "do": do}


def _authored(run, plugin):
    """(exists, authored) for the plugin's section. Composed is not authored."""
    from . import compose as C
    from . import paper as P

    p = P._root(run, plugin) / P.draft_name(plugin)
    if not p.is_file():
        return False, False
    head = p.read_text(encoding="utf-8").strip()
    return True, bool(head) and not head.startswith(C.COMPOSED_MARK)


def tasks(run, plugin, spec=None, how=None):
    """[{id, title, state, why, do}] - the whole cycle, in order, with the state of each.

    THE COMPUTE STEP IS IN THE LIST. It is the tool's to perform and the AGENT'S to start and to
    watch, and leaving it out made the agenda a thing you read after a run instead of the shape
    of the whole cycle - which is the difference between an agent that waits for the job and one
    that discovers it finished some time ago.
    """
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

    how = mode(how)
    started = (run / "report.json").is_file()
    t = [execution_task(run, how),
         {"id": "brief", "title": "Read the writing brief",
          "state": DONE if brief.is_file() else (PENDING if started else BLOCKED),
          "why": "the evidence this result is written from, with every number's file named",
          "do": f"scprofile write --out {run} --plugin {plugin}"},
         {"id": "look", "title": f"Open the figures ({len(out)} outstanding)",
          "state": DONE if (started and not out) else (PENDING if started else BLOCKED),
          "why": "every figure defect found in this project was found by opening the image "
                 "while the suite was green; a table shows none of them",
          "do": f'scprofile review --out {run} --plugin {plugin} --figure <path> --note "..."'},
         {"id": "write", "title": "Write the result",
          # AN EMPTY OUTSTANDING LIST IS NOT A FINISHED ONE. Before the run there are no
          # figures at all, so "nothing outstanding" was read as "all looked at" and writing
          # showed as available on a run that did not exist yet - which is precisely the order
          # this list exists to enforce.
          "state": (DONE if authored
                    else PENDING if (started and not out)
                    else BLOCKED),
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


def outstanding(run, plugin, spec=None, how=None):
    """The tasks that are not done."""
    return [x for x in tasks(run, plugin, spec, how) if x["state"] != DONE]


def write_agenda(run, plugin, spec=None, how=None):
    """Write `kernels/<plugin>/AGENDA.md`. Returns its path.

    EMITTED BY THE RUN, so the handoff does not depend on anyone asking. A PBS job seals and
    leaves this behind; the agent picks it up without having to know what step it is on.
    """
    how = mode(how)
    t = tasks(run, plugin, spec, how)
    left = [x for x in t if x["state"] != DONE]
    L = [f"# Agenda - {plugin}", "",
         f"Run `{Path(run).name}`, execution mode **{how}**"
         + (" — the compute runs detached on another machine, so it is submitted and WATCHED, "
            "and its output picked up the moment it seals. That is one run, not three errands."
            if how == PBS else " — the compute runs in front of you."), "",
         "The tool does the measuring, drawing and refusing. **The rest is the agent's.**", "",
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
