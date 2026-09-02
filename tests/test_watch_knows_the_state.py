"""A run directory says what state it is in, and the seal-lags-the-queue rule is encoded.

Every check here is a wrong answer that was actually given, by a hand-rolled watcher, in one day:
two runs that had sealed reported as vanished, a CPU-time figure read as wall-clock, and a fresh
loop each time so each could be wrong in its own new way.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scprofile import watch as WT                                               # noqa: E402

FAILURES = []


def ck(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def mk(td, **files):
    r = Path(td) / "run"
    r.mkdir(exist_ok=True)
    for n, body in files.items():
        (r / n).write_text(body, encoding="utf-8")
    return r


RUNNING_BODY = ("phase    : run\njob      : 12345.head\nnode     : c1\n"
                "started  : 2026-09-02T09:00:00Z\nlive log : /somewhere/live.log\n")

print("the markers are read in the safe order")
with tempfile.TemporaryDirectory() as td:
    ck("a directory that does not exist is absent",
       WT.state(Path(td) / "nope")["state"] == WT.ABSENT)

    r = mk(td, **{WT.MARK_SEALED: "phase: run\njob: 12345.head\nfinished : 2026-09-02T09:20:00Z\n"})
    ck("a sealed run is sealed", WT.state(r)["state"] == WT.SEALED)
    # A JOB THAT WROTE BOTH DID NOT FINISH CLEANLY, so failure wins however tempting the seal is.
    (r / WT.MARK_FAILED).write_text("phase: run\nexit     : 99\n", encoding="utf-8")
    ck("failure beats a seal written beside it", WT.state(r)["state"] == WT.FAILED)
    ck("and the reason names the exit", "99" in WT.state(r)["why"], WT.state(r)["why"])

print("\nthe run records its own job id, so nothing has to be passed in")
with tempfile.TemporaryDirectory() as td:
    r = mk(td, **{WT.MARK_RUNNING: RUNNING_BODY})
    ck("the job id comes off the running marker", WT.job_id(r) == "12345.head", WT.job_id(r))
    ck("and the live log with it", WT.state(r)["live_log"] == "/somewhere/live.log")
    ck("and when it started", WT.state(r)["since"] == "2026-09-02T09:00:00Z")
    r2 = mk(Path(td).__class__(tempfile.mkdtemp()), **{WT.MARK_SEALED: "job      : none\n"})
    ck("a job id of 'none' is not a job id", WT.job_id(r2) == "", WT.job_id(r2))

print("\nTHE ONE THAT WAS GOT WRONG TWICE: a seal lags the queue")
with tempfile.TemporaryDirectory() as td:
    r = mk(td, **{WT.MARK_RUNNING: RUNNING_BODY})
    # The job is not in any queue (id 12345.head does not exist here) and no marker is on disk.
    # A hand-rolled watcher called this FAILURE. It is the window between the two, and the honest
    # answer is that the state is not yet known.
    st = WT.state(r)
    ck("job gone and no marker is UNKNOWN, not failed", st["state"] == WT.UNKNOWN, st["state"])
    ck("and it is never reported as failed", st["state"] != WT.FAILED)
    ck("and the reason says the seal lags the queue",
       "lags the queue" in st["why"].lower(), st["why"])
    ck("and says how long the grace has left", "s" in st["why"] and "not failure" in st["why"])
    # PAST THE GRACE PERIOD THE ANSWER CHANGES, and says what it probably means - a trap that
    # never ran, which is a kill from outside rather than a run that reported its own failure.
    old = time.time() - (WT.SEAL_GRACE_S + 60)
    os.utime(r / WT.MARK_RUNNING, (old, old))
    st2 = WT.state(r)
    ck("past the grace it is still not called failed", st2["state"] == WT.UNKNOWN, st2["state"])
    ck("but it says the trap never ran", "trap never ran" in st2["why"], st2["why"])
    ck("and points at the live log", "live log" in st2["why"].lower(), st2["why"])
    ck("the grace is generous enough to matter", WT.SEAL_GRACE_S >= 60)

print("\nwall-clock and CPU time are named, never taken positionally")
src = Path(WT.__file__).read_text(encoding="utf-8")
# THE DOT IS ESCAPED IN THE SOURCE because it is inside a regex, so the check looks for the
# pattern as written rather than for a literal that is not there. A check that fails on correct
# code is a check that gets deleted.
ck("walltime is matched by name", r"resources_used\.walltime" in src)
ck("cput is matched by name and kept separate",
   r"resources_used\.cput" in src and '"cpu"' in src)
ck("the describe line labels which is which",
   "wall " in src and "cpu " in src)

print("\nnothing here is specific to one scheduler, one project or one method")
for word in ("SAMBO", "cellchat", "/data/", "jiaen"):
    ck(f"the module never says {word!r}", word not in src)
ck("it asks whichever scheduler is on PATH", "qstat" in src and "scontrol" in src)
ck("and answers nothing rather than guessing when neither is",
   "return {}" in src)

if FAILURES:
    print("\nFAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("\nok - one answer, from the run's own markers, with the lag rule encoded")
