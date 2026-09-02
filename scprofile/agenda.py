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

EVERY TASK ON THIS LIST IS THE AGENT'S, AND NONE OF THEM WAITS FOR A PERSON. There is no human
step inside scProfile: the agent submits the job, watches it, opens every figure, writes the
result and carries it back in. A task marked `blocked` is waiting on an EARLIER TASK, never on
someone else - and the agenda says so, because a list with an implied human step is a list with
a step nobody performs. Human review happens outside this tool, on the artifacts a run leaves.
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
    # TWO SEPARATE FACTS, AND THIS TASK USED TO READ ONLY THE LATER ONE.
    #
    # `report.json` is the RUN'S own record, written when the kernels have finished. `SEALED.txt`
    # is the JOB'S marker, written by the batch script's trap on a clean exit. The agenda is
    # emitted while the report renders - which is BEFORE the trap fires - so a task whose state
    # was `DONE if sealed` reported "Run the pipeline - pending" on every agenda the tool has
    # ever delivered, including on runs that went on to seal cleanly seconds later. The one
    # artifact whose whole purpose is to say what is left said the finished part was not done.
    #
    # They are not merged. A run that wrote `report.json` and never sealed is a partial run, and
    # calling that sealed is the error the batch script's own comment warns about: a false SEALED
    # tells everything downstream that a partial run is complete. So the compute is DONE once the
    # run has written its own record, and the note says which of the two facts is in evidence.
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
    if sealed:
        why = "the job sealed: SEALED.txt is in the run directory"
    elif started:
        why = ("the run wrote its own record (report.json). SEALED.txt is the JOB's marker and "
               "is written AFTER this file, so its absence here is not evidence of failure - "
               "read the run directory for it before promoting anything")
    return {"id": "run", "title": "Run the pipeline",
            "state": DONE if (sealed or started) else PENDING,
            "why": why, "do": do}


#: One agent's share of the looking. Not a limit on how many agents may run - a size at which a
#: single agent's notes are still specific, since a note copied across panels is refused and a
#: reviewer who has just seen sixty figures writes exactly that.
FIGURES_PER_AGENT = 25


def _fanout(run, plugin, n_outstanding):
    """The lines that tell an agent to SPLIT the looking, when there is enough of it to split.

    LOOKING IS THE ONLY STEP IN THIS CYCLE THAT PARALLELISES WITHOUT ARGUMENT. The panels are
    independent, nothing is computed, and the record is append-only - so a step that takes one
    agent an hour takes four agents a quarter of it, with the same ledger at the end. It is also
    the step that gets skipped, and the two facts are the same fact: a task nobody can finish in
    one sitting is a task that gets a glance and a summary instead.

    THE TOOL PROVIDES THE SPLIT. An agent dividing the list itself is how one figure gets two
    reviews and another gets none, which the ledger then reports as outstanding for ever.
    `review --shards N` cuts the OUTSTANDING set into disjoint groups with each unit's figures
    kept together, and `--shard K` prints one group - the argument to hand a sub-agent.

    SAID ONLY WHEN IT PAYS. Below the floor the split costs more than it saves, and an
    instruction to parallelise four figures is an instruction that gets ignored along with the
    ones that matter.
    """
    from . import review as R
    if n_outstanding < R.SHARD_FLOOR:
        return []
    k = max(2, -(-int(n_outstanding) // FIGURES_PER_AGENT))
    return [f"THIS STEP PARALLELISES. {n_outstanding} figures is roughly {k} agents' work at "
            f"~{FIGURES_PER_AGENT} each. Do not divide the list yourself - ask the tool for "
            f"disjoint shards, one per agent:",
            f"    scprofile review --out {run} --plugin {plugin} --shards {k}          "
            f"# all of them, to dispatch",
            f"    scprofile review --out {run} --plugin {plugin} --shards {k} --shard 1 "
            f"# one agent's list",
            "each agent opens its own shard and records its own looks; the ledger is append-only "
            "and locked per write, so they may record at the same time. A note is refused if it "
            "repeats another figure's, so the shards must not overlap - which is why the tool "
            "cuts them and not you."]


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
          # UNDER A SCHEDULER THE IMAGES ARE NOT WHERE THE AGENT IS, and saying "open the
          # figures" to an agent that cannot reach them is an instruction it cannot follow. It
          # then writes a throwaway parser over the brief's markdown to get the paths - the
          # in-house script this tool exists to make unnecessary - or, worse, writes about the
          # panels without opening them, which is the exact failure the ledger was built for.
          #
          # So the mechanics are part of the task, and they are generic: the run writes the set
          # as a transfer list, and any tool that reads a file of paths takes it as it stands.
          # The host does not know the agent's hostname or where it keeps files, and must not
          # guess - it names the list, the run root and the direction, and leaves the two
          # endpoints to the agent, which is the only party that knows them.
          "how": ([f"the figures are on the cluster filesystem; whatever you open images with "
                   f"usually is not. Bring the whole set across in ONE transfer using the list "
                   f"this run writes - {run}/kernels/{plugin}/{B.FIGURE_LIST}, one "
                   f"run-relative path per line, in the order the paper numbers them:",
                   f"    rsync -a --files-from=<the list> <host>:{run}/ <a local directory>/",
                   f"    # no rsync: tar -C {run} -T {run}/kernels/{plugin}/"
                   f"{B.FIGURE_LIST} -czf figures.tgz   (then fetch and unpack that)",
                   "open every one from the local copy - then record each look AGAINST THE RUN "
                   "DIRECTORY, not the copy, because the ledger lives with the run and is bound "
                   "to the image the run holds."] if how == PBS else []) + _fanout(run, plugin,
                                                                                   len(out)),
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
         "The tool does the measuring, drawing and refusing. **Everything else on this list is the agent's, and none of it waits for anyone.**", "",
         f"**{len(t) - len(left)} of {len(t)} done.**", ""]
    for i, x in enumerate(t, 1):
        mark = {DONE: "x", PENDING: " ", BLOCKED: "-"}[x["state"]]
        L += [f"{i}. [{mark}] **{x['title']}** — {x['state']}",
              f"       {x['why']}"]
        # HOW, WHERE THE MODE CHANGES THE MECHANICS. Printed between the reason and the command
        # because it is neither: it is what has to be true before the command can be typed.
        for line in x.get("how") or []:
            L.append(f"       {line}")
        L += [f"       `{x['do']}`", ""]
    if left:
        L += ["*A blocked task is waiting on an earlier task \u2014 not on the tool, and not on a person.*", ""]
    else:
        L += ["*Nothing outstanding. The result is written, carried into a run, and defended.*",
              ""]
    d = Path(run) / "kernels" / plugin
    d.mkdir(parents=True, exist_ok=True)
    p = d / NAME
    p.write_text("\n".join(L), encoding="utf-8")
    return p
