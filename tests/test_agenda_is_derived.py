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
