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

#: Where the agent records what the run's own findings MEAN. Beside the run, because the finding
#: is a property of the run and so is the reading of it.
ACCOUNT = "ACCOUNTING.md"

#: Long enough that "fine" is not an accounting. Same reasoning as a review note: the check cannot
#: judge whether a sentence is true, so it checks the one thing it can - that somebody wrote one.
ACCOUNT_WORDS = 20

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
        do = (f"submit as a batch job, then `scprofile watch --out {run} --wait` - it blocks "
              f"until the run is sealed or failed and reports each change of state. Do NOT "
              f"hand-roll the poll loop: every hand-rolled version of it in this project got the "
              f"seal-lags-the-queue rule wrong. The job writes AGENDA.md as its last act, so "
              f"pick that up the moment it seals.")
        # THE SEAL LAGS THE QUEUE, AND A WATCHER THAT DOES NOT KNOW THAT REPORTS A CLEAN RUN AS
        # A FAILURE. The scheduler drops a finished job from `qstat` before the trap's write to
        # a network filesystem is visible, so `job gone AND no SEALED.txt` is true for a while on
        # a run that sealed perfectly. Three hand-rolled watchers in one session made exactly
        # this call twice, on runs that had sealed. The negative marker is FAILED.txt, not the
        # absence of the positive one.
        why += (" The seal LAGS the queue: a finished job leaves `qstat` before SEALED.txt is "
                "visible on a network filesystem, so 'job gone and no seal' is not a failure "
                "until you have re-checked. FAILED.txt is the marker that means failure.")
    else:
        why = "the compute runs in front of you and finishes before the next step begins"
        do = "scprofile run --h5ad <object> --out <run> ..."
    # APPENDED, NEVER REPLACED. The first version overwrote `why` with the state sentence, which
    # deleted the mode's own guidance - including the warning that the seal lags the queue - on
    # every run that had started, which is every run anyone ever reads this for. Its own suite
    # caught it. State is one more thing the reader needs, not a substitute for the rest.
    if sealed:
        why += " STATE: the job sealed - SEALED.txt is in the run directory."
    elif started:
        why += (" STATE: the run wrote its own record (report.json); SEALED.txt is the JOB's "
                "marker and is written after it.")
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


def health(run):
    """What the run says against ITSELF, read off its own records. [] when it says nothing.

    THE CYCLE HAS A FAILURE PATH AND THE AGENDA DID NOT COVER IT. A run that regresses or loses a
    unit still seals, still writes a report, and still tells an agent that five of six tasks are
    done - so the agent walks past it into the writing. The two records that would have said
    otherwise are already on disk and nothing pointed at them.

    Both findings here carry the same warning, because both were misread in the session that
    produced this function:

    - A REGRESSION IS NOT AUTOMATICALLY A BREAKAGE. Deliberately removing a duplicated figure
      lowers the figure count, and the guard is right to report it: what it cannot know is whether
      the drop was intended. Only the agent knows, and it must say which.
    - ONE FAILED UNIT CAN DOWNGRADE EVERY OTHER UNIT'S VERDICT. A single instance failing produced
      a run-level diagnosis that marked all seventeen instances suspect, and the count of suspect
      units then read as seventeen separate failures. Cause and consequence are not distinguished
      by the number; they are distinguished by reading which unit actually failed.
    """
    import json
    from . import capacity as CAP
    from . import review as RV

    run = Path(run)
    found = []
    # COMPUTED, NOT READ. CAPACITY.json records this run's own counts and nothing else - the
    # comparison against a sibling is made at report time and printed, never stored. The first
    # version of this function read a `regressions` key that has never existed, so it reported
    # nothing on a run whose report had just printed four of them: a check that silently answers
    # "all clear" is worse than no check, because it is believed.
    prev, worse = None, []
    try:
        sibs = [d for d in RV.sibling_runs(run) if d.name < run.name]
        prev = max(sibs, key=lambda d: d.name) if sibs else None
        if prev is not None:
            worse = CAP.regressions(CAP.read(run), CAP.read(prev))
    except Exception:                                                     # noqa: BLE001
        worse = []
    if worse:
        found.append({"what": f"{len(worse)} capacity regression(s) against {prev.name}",
                      "detail": "; ".join(f"{k}: {b} -> {n}" for k, b, n, _v in worse),
                      "why": "the run produced less than its sibling. A DELIBERATE removal looks "
                             "exactly like a breakage here and the guard cannot tell them apart - "
                             "say which each one is before writing anything up."})
    try:
        card = json.loads((run / "RUN_CARD.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        card = {}
    inst = [i for i in (card.get("instances") or []) if isinstance(i, dict)]
    # A UNIT THAT FAILS HARD CAN BE MISSING FROM THE CARD ALTOGETHER, and then the card names some
    # OTHER unit as the failure. Measured: one instance exited on a signal, was absent from the
    # seventeen instances the card recorded, and the only unit the card called empty was a
    # different one that had failed for a different reason on an earlier run. An agent reading the
    # card alone goes to the wrong log. So the scheduled set is compared against the recorded one,
    # and a unit that was scheduled and left no instance is named as exactly that.
    try:
        sched = json.loads((run / "report.json").read_text(encoding="utf-8")).get("units") or []
    except (OSError, ValueError):
        sched = []
    have = {str(i.get("unit")) for i in inst}
    lost = sorted({str(u) for u in sched} - have) if sched else []
    if lost:
        found.append({"what": f"{len(lost)} scheduled unit(s) left NO record in the run card",
                      "detail": ", ".join(lost),
                      "why": "these are the units to read first: a unit that fails hard can be "
                             "absent from the card entirely, so the unit the card calls failed "
                             "may not be the one that broke."})
    outright = [str(i.get("unit")) for i in inst
                if str(i.get("state") or "") in ("empty", "failed")
                or str(i.get("outcome") or "") == "failed"]
    suspect = [str(i.get("unit")) for i in inst if i.get("verdict") not in ("ok", None)]
    if outright:
        found.append({"what": f"{len(outright)} unit(s) did not produce",
                      "detail": ", ".join(sorted(outright)),
                      "why": "these are the units that actually failed. Read their own logs; the "
                             "rest of the run may be sound."})
    if suspect and len(suspect) > len(outright):
        found.append({"what": f"{len(suspect)} unit(s) carry a non-ok verdict",
                      "detail": ", ".join(sorted(suspect)[:6])
                                + (" ..." if len(suspect) > 6 else ""),
                      "why": f"only {len(outright)} of them actually failed. A run-level diagnosis "
                             f"marks every instance, so this number counts consequence as well as "
                             f"cause - do not report it as that many broken units."})
    return found


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
    hz = health(run) if started else []
    # AN ACCOUNTING IS AN ARTIFACT, like every other state here. The step asked an agent to "say
    # which findings were intended" and gave it nowhere to say it, so the answer lived in a
    # session and died with it - and the next agent met the same findings with no record that
    # anyone had ever looked. A task whose result has no home is a task that gets skipped.
    accounted = (run / ACCOUNT).is_file() and len(
        (run / ACCOUNT).read_text(encoding="utf-8", errors="replace").split()) >= ACCOUNT_WORDS
    t = [execution_task(run, how),
         # ACCOUNT FOR THE RUN BEFORE WRITING IT UP. A run that regressed or lost a unit still
         # seals, still reports, and still says five of six tasks are done - so an agenda without
         # this step walks an agent straight past it into the writing. It does NOT block the rest:
         # a deliberate figure removal shows up here as a regression, and a step that halted the
         # cycle on correct behaviour is a step that gets switched off.
         {"id": "account", "title": (f"Account for what the run reports against itself "
                                     f"({len(hz)} finding(s))" if hz else
                                     "Account for what the run reports against itself"),
          "state": (DONE if (started and (not hz or accounted))
                    else PENDING if started else BLOCKED),
          "why": "the run's own records say whether it produced less than its sibling and which "
                 "units failed; both look like breakage and neither necessarily is",
          "how": [f"{h['what']}: {h['detail']}" for h in hz]
                 + ([hz[0]["why"]] if hz else []),
          "do": f"write {run / ACCOUNT} saying which finding was intended and which was not - "
                f"at least {ACCOUNT_WORDS} words, one line per finding. `scprofile capacity "
                f"--out {run}` prints the numbers behind them."},
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
          # THE FIGURE SET MUST BE SETTLED BEFORE THE SECTION IS WRITTEN. A section cites figures
          # by the number the paper gives them, and adding or removing one figure renumbers every
          # figure after it - so a section written against one figure set and carried into a run
          # with another cites the wrong plates while reading perfectly. Fix the figures first,
          # re-run, and write against the set that will ship.
          "do": "write it, then carry it in with the next task. If any figure is still to be "
                "added or removed, do THAT first: the paper numbers figures in order, so changing "
                "the set renumbers the citations of a section already written"},
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
         "**Run this list to the end in one go.** Every task below is unblocked by the one above it and by nothing else, so there is no point in it where the right move is to stop and ask. A cycle that halts after the compute leaves a run with figures nobody opened and a section nobody wrote - which is the state this file exists to get a run out of, not a state to report back from.", "",
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
        L += ["*A blocked task is waiting on an earlier task \u2014 not on the tool, and not on "
              "a person. Do the one above it, then come back; do not stop here.*", "",
              "**If you are about to change how a figure is drawn, do it BEFORE looking at the "
              "figures.** A review is bound to the image, so redrawing destroys it: a sweep taken "
              "before a fix round is a sweep thrown away. Fix, re-run, then look.", ""]
    else:
        L += ["*Nothing outstanding. The result is written, carried into a run, and defended.*",
              ""]
    d = Path(run) / "kernels" / plugin
    d.mkdir(parents=True, exist_ok=True)
    p = d / NAME
    p.write_text("\n".join(L), encoding="utf-8")
    return p
