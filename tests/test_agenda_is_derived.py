"""The agent's remaining work is read off the run, never stored, and ordered so nothing is guessed.

scProfile is run by an agent and half the work is the agent's. That half had a command per step
and no interface over them, so it depended on remembering the sequence - and across this
project's whole history `run --section` had been used zero times while 120 figure looks were
recorded. The steps existed; the phase never ran.

TWO PROPERTIES ARE CHECKED, because they are what make it usable from a batch job:

  * STATE IS DERIVED. A task is done when the artifact proving it exists. Storing status would
    be a fifth file to keep in step with four others, and it would go on reporting "written"
    about a section the composer had since regenerated - which is the staleness this project
    treats as worse than being wrong, because it reads correctly.
  * A TASK WHOSE INPUT IS ABSENT IS BLOCKED, not pending. An agent that starts writing before
    looking produces a result about figures nobody opened, which is the failure the whole
    arrangement exists to prevent.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import agenda as AG                                        # noqa: E402
from scprofile import compose as C                                       # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


def _state(run, plugin="p"):
    return {t["id"]: t["state"] for t in AG.tasks(run, plugin, how=AG.LOCAL)}


with tempfile.TemporaryDirectory() as td:
    run = Path(td) / "runX"
    (run / "kernels" / "p" / "figures").mkdir(parents=True)
    (run / "report.json").write_text('{"kernels": {"p": {}}}', encoding="utf-8")
    (run / "kernels" / "p" / "figures" / "a.png").write_bytes(b"PNG-A")

    # BEFORE ANYTHING HAS RUN, every step after the run is blocked - including writing, which
    # an empty outstanding list once made look available on a run that did not exist.
    nothing = Path(td) / "not-yet"
    pre = {t["id"]: t["state"] for t in AG.tasks(nothing, "p", how=AG.PBS)}
    check(pre["run"] == AG.PENDING, "the run itself is not the first task: %r" % pre)
    check(pre["write"] == AG.BLOCKED,
          "writing shows as available before anything has run, because an empty figure list "
          "read as a finished one: %r" % pre)
    check(all(pre[k] == AG.BLOCKED for k in ("brief", "look", "carry", "defend")),
          "a step whose input cannot exist yet is not blocked: %r" % pre)

    # AND THE MODE CHANGES WHAT THE COMPUTE STEP TELLS THE AGENT TO DO, and nothing else.
    pbs = AG.execution_task(nothing, AG.PBS)
    loc = AG.execution_task(nothing, AG.LOCAL)
    check("watch" in pbs["why"].lower() and "detached" in pbs["why"].lower(),
          "pbs mode does not tell the agent the job runs detached and must be watched")
    check("watch" not in loc["why"].lower(),
          "local mode tells the agent to watch a job that finishes in front of it")

    # AND THE LOOK STEP CARRIES THE MECHANICS OF CROSSING THE MACHINE BOUNDARY, in pbs mode only.
    # "Open the figures" is not an instruction an agent on another machine can follow, and an
    # agenda whose step cannot be followed is where a hand-rolled workaround comes from.
    _look = {t["id"]: t for t in AG.tasks(run, "p", how=AG.PBS)}["look"]
    _look_l = {t["id"]: t for t in AG.tasks(run, "p", how=AG.LOCAL)}["look"]
    _how = " ".join(_look.get("how") or [])
    check("FIGURES.txt" in _how,
          "the pbs look step does not name the transfer list, so the agent has to parse the "
          "brief's markdown to find the images: %r" % (_how[:120],))
    check("--files-from" in _how or "-T " in _how,
          "the pbs look step names no way to move the set in one operation: %r" % (_how[:120],))
    check(not any("rsync" in h for h in (_look_l.get("how") or [])),
          "local mode is told to transfer files that are already in front of it")

    # AND IT SAYS TO FAN THE STEP OUT - but only when there is enough of it to be worth splitting.
    # An instruction to parallelise four figures is an instruction ignored along with the ones
    # that matter, so the floor is part of the mechanism and is tested in both directions.
    import scprofile.review as _RV
    _small = " ".join(AG._fanout(run, "p", 3))
    _big = " ".join(AG._fanout(run, "p", 200))
    check(not _small, "the agenda tells an agent to split three figures across agents: %r"
          % (_small[:100],))
    check("--shards" in _big and "PARALLELISES" in _big.upper(),
          "a 200-figure look step does not tell the agent it can be split: %r" % (_big[:160],))
    check("do not divide the list yourself" in _big.lower(),
          "the agent is told to parallelise without being told the tool cuts the shards, which "
          "is how one figure gets two reviews and another none")
    check(_RV.SHARD_FLOOR > 1, "the shard floor is not a floor")

    # THE FAILURE PATH IS PART OF THE CYCLE. A run that regressed or lost a unit still seals and
    # still reports five of six tasks done, so an agenda that does not read its own records walks
    # an agent past the problem into the writing.
    import json as _json
    ids = [x["id"] for x in AG.tasks(run, "p", how=AG.PBS)]
    check("account" in ids, "the agenda has no step for what the run reports against itself")
    check(ids.index("account") < ids.index("write"),
          "accounting for the run comes after writing it up: %r" % (ids,))
    clean = {t["id"]: t for t in AG.tasks(run, "p", how=AG.PBS)}["account"]
    check(clean["state"] == AG.DONE,
          "a run with nothing against it still shows an outstanding accounting step")
    (run / "CAPACITY.json").write_text(
        _json.dumps({"regressions": ["figures: 10 -> 7"]}), encoding="utf-8")
    (run / "RUN_CARD.json").write_text(_json.dumps({"instances": [
        {"unit": "u2", "state": "empty", "verdict": "suspect"},
        {"unit": "u3", "state": "done", "verdict": "suspect"}]}), encoding="utf-8")
    _rj = _json.loads((run / "report.json").read_text(encoding="utf-8"))
    _rj["units"] = ["u1", "u2", "u3"]
    (run / "report.json").write_text(_json.dumps(_rj), encoding="utf-8")
    hz = AG.health(run)
    kinds = " ".join(h["what"] for h in hz)
    # THE UNIT THAT BROKE CAN BE MISSING FROM THE CARD, and then the card names a different unit
    # as the failure. The fixture schedules u1/u2/u3 and records only u2/u3, so u1 is the one that
    # left no record - which is the unit an agent must read first.
    check(any("NO record" in h["what"] and "u1" in h["detail"] for h in hz),
          "a scheduled unit with no instance in the card is not named: %r" % (kinds,))
    check("regression" in kinds, "a capacity regression is not surfaced: %r" % (kinds,))
    check("did not produce" in kinds, "the unit that actually failed is not named: %r" % (kinds,))
    # THE ONE THAT WAS MISREAD: 3 suspect, 1 actually failed. Reporting 3 broken units is wrong.
    _susp = [h for h in hz if "non-ok verdict" in h["what"]]
    check(_susp and "only 1 of them actually failed" in _susp[0]["why"],
          "the agenda does not separate the units that failed from the ones downgraded by them")
    dirty = {t["id"]: t for t in AG.tasks(run, "p", how=AG.PBS)}["account"]
    check(dirty["state"] == AG.PENDING, "findings against the run leave the step done")
    check(dirty["state"] != AG.BLOCKED and
          {t["id"]: t for t in AG.tasks(run, "p", how=AG.PBS)}["brief"]["state"] != AG.BLOCKED,
          "an intended removal halts the whole cycle, which is how a step gets switched off")
    _run_task = AG.execution_task(run, AG.PBS)
    check("lags the queue" in _run_task["why"].lower(),
          "the watch recipe does not say the seal lags the queue, which twice made a sealed run "
          "read as a failure")
    (run / "CAPACITY.json").unlink()
    (run / "RUN_CARD.json").unlink()

    st = _state(run)
    # THE COMPUTE STEP IS DONE ONCE THE RUN WROTE ITS OWN RECORD, NOT ONLY ONCE THE JOB SEALED.
    # The agenda is emitted while the report renders, which is BEFORE the batch script's trap
    # writes SEALED.txt - so a state read only off SEALED.txt reported "Run the pipeline -
    # pending" on every agenda the tool ever delivered, including on runs that sealed cleanly
    # seconds later. There is no SEALED.txt in this fixture, which is exactly that moment.
    check(not (run / "SEALED.txt").exists(), "fixture is not the pre-seal moment it tests")
    check(st["run"] == AG.DONE,
          "a run that has written report.json is reported as not yet run: %r" % st)
    check("report.json" in AG.execution_task(run, AG.PBS)["why"],
          "the compute step does not say WHICH fact it read, so a partial run and a sealed one "
          "are indistinguishable in the agenda")
    (run / "SEALED.txt").write_text("phase: run\n", encoding="utf-8")
    check("sealed" in AG.execution_task(run, AG.PBS)["why"].lower(),
          "a sealed run is not reported as sealed")
    (run / "SEALED.txt").unlink()
    check(st["brief"] == AG.PENDING, "a run with no brief does not ask for one: %r" % st)
    check(st["look"] == AG.PENDING, "an unreviewed figure is not outstanding: %r" % st)
    check(st["write"] == AG.BLOCKED,
          "writing is offered before the figures have been looked at, which is how a result "
          "gets written about panels nobody opened: %r" % st)
    check(st["carry"] == AG.BLOCKED and st["defend"] == AG.BLOCKED,
          "a task whose input does not exist is not blocked: %r" % st)

    # A COMPOSED SECTION IS NOT A WRITTEN ONE. This is the distinction the whole phase turns on.
    d = run / "kernels" / "p"
    (d / "PAPER.p.md").write_text(C.COMPOSED_MARK + "\nskeleton\n", encoding="utf-8")
    check(_state(run)["write"] != AG.DONE,
          "a code-composed section counts as written, so the agent's step reports itself done")

    (d / "PAPER.p.md").write_text("# A real section\n\nWritten by an agent.\n", encoding="utf-8")
    st2 = _state(run)
    check(st2["write"] == AG.DONE and st2["carry"] == AG.DONE,
          "an authored section is not recognised: %r" % st2)
    check(st2["defend"] == AG.PENDING,
          "with a result written, defending it is not yet asked for: %r" % st2)

    # DERIVED, NOT STORED: regenerating the composed skeleton must take the task back.
    (d / "PAPER.p.md").write_text(C.COMPOSED_MARK + "\nskeleton again\n", encoding="utf-8")
    check(_state(run)["write"] != AG.DONE,
          "the agenda kept reporting the result as written after the composer replaced it - "
          "which is exactly what a stored status would do")

    p = AG.write_agenda(run, "p")
    check(p.is_file() and "Agenda" in p.read_text(encoding="utf-8"),
          "no agenda was written for the job to leave behind")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - state is derived from artifacts, blocked tasks are blocked, composed is not written")
