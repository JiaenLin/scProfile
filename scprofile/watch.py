"""What state is this run in? One answer, from the run's own markers and the scheduler.

WHY THIS EXISTS. Under a scheduler the compute is detached, and an agent watching it has to answer
one question repeatedly: is it still going, did it finish, or did it die. That question was
answered by hand every time, and answered WRONG four times in a single day:

- twice a watcher reported `JOB GONE without SEALED` on runs that had sealed perfectly, because a
  finished job leaves the queue BEFORE its trap's write is visible on a network filesystem;
- once a CPU-time figure was read as wall-clock, making a 20-minute run look like an hour;
- and every check was a fresh shell loop, so each one could be wrong in its own new way.

None of that is hard. It is just unwritten, and unwritten means re-derived, and re-derived means
occasionally wrong in a way nobody notices because the answer is plausible.

THE THREE RULES THIS ENCODES, all of them paid for:

1. **A seal LAGS the queue.** `job absent AND no SEALED.txt` is not failure until the grace
   period has passed. Before that it is UNKNOWN, which is a different answer and the honest one.
2. **FAILED.txt is the negative marker.** The absence of the positive one is not evidence.
3. **Elapsed is wall-clock.** A scheduler reports CPU time too and they differ by the core count,
   so the field is named rather than taken from whichever column came first.

NOTHING HERE IS PROJECT-SPECIFIC. It reads markers this tool's own job script writes and, if a
scheduler command happens to be on PATH, asks it about a job id the run recorded itself.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path

RUNNING, SEALED, FAILED, UNKNOWN, ABSENT = "running", "sealed", "failed", "unknown", "absent"

#: Markers the job script writes. RUNNING is written before any work and left in place, so a run
#: directory says which job owns it while that job is alive - the thing whose absence forced every
#: watcher to be told the job id out of band and then guess.
MARK_RUNNING, MARK_SEALED, MARK_FAILED = "RUNNING.txt", "SEALED.txt", "FAILED.txt"

#: How long after a job leaves the queue to keep answering UNKNOWN rather than FAILED.
#:
#: The trap writes its marker after the scheduler has already dropped the job, and on a network
#: filesystem that write can take a moment more to become visible to another host. Two false
#: failure reports in one day came from a gap of seconds. Generous on purpose: the cost of waiting
#: is a slower answer, and the cost of not waiting is calling a good run dead.
SEAL_GRACE_S = 120.0

#: Scheduler states that mean the work has NOT finished. Anything else - PBS `F`/`C`/`E`, Slurm
#: COMPLETED/FAILED/CANCELLED/TIMEOUT - is a job that has ended, and the run's own markers are
#: then the authority. Listed positively because the set of end states differs between schedulers
#: and a blacklist silently treats an unknown one as still running.
LIVE_STATES = {"R", "Q", "H", "S", "T", "W", "B", "M",
               "RUNNING", "PENDING", "SUSPENDED", "CONFIGURING", "COMPLETING", "RESIZING"}


#: A run with no marker and no reachable scheduler is still observable: something is either
#: writing to it or it is not. Below this many seconds since the newest write, treat it as alive.
#:
#: WHY THIS FALLBACK EXISTS. The first version of this module answered UNKNOWN for any run that
#: carried no RUNNING.txt - which is every run submitted before that marker existed, and every run
#: from a job script this tool did not write. Asked about a live job, it said "either the job has
#: not started or it predates this marker" and the caller went back to the scheduler by hand,
#: which is the thing the module exists to stop. A watcher that only works on runs it started is
#: not a watcher.
#:
#: Generous, because a run inside one long step can be quiet for minutes: the answer distinguishes
#: "being written" from "quiet", and never calls quiet dead.
ACTIVE_S = 300.0

#: How far to look for the newest write. A run directory holds thousands of files and the answer
#: does not need all of them - it needs to know whether ANY of them is recent.
_SCAN_CAP = 4000


def newest_write(run):
    """Seconds since the most recent write anywhere under the run, or None if it cannot be read.

    THE ONE SIGNAL THAT NEEDS NOTHING. No marker, no job id, no scheduler, no log path: a run that
    is progressing is a run whose directory is being written to. It is weaker evidence than a
    marker and it is never reported as more than it is.
    """
    run = Path(run)
    newest, seen = None, 0
    marks = {MARK_RUNNING, MARK_SEALED, MARK_FAILED}
    try:
        for p in run.rglob("*"):
            # THE MARKERS ARE NOT EVIDENCE OF WORK. They are written once, at the boundaries, so
            # counting them makes a run that has done nothing since it started look busy - and,
            # worse, makes the just-started window indistinguishable from the just-finished one,
            # which is the window the grace period exists for. Its own suite caught this: the
            # activity check shadowed the seal-lags-the-queue branch entirely, because a fixture
            # whose only file is RUNNING.txt always looked freshly written.
            if p.name in marks:
                continue
            seen += 1
            if seen > _SCAN_CAP:
                break
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if newest is None or m > newest:
                newest = m
    except OSError:
        return None
    return None if newest is None else max(0.0, time.time() - newest)


def _read(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _field(text, key):
    m = re.search(rf"^{re.escape(key)}\s*:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def job_id(run):
    """The scheduler's id for the job that wrote this run, or "". Recorded by the run itself."""
    run = Path(run)
    for mark in (MARK_RUNNING, MARK_SEALED, MARK_FAILED):
        got = _field(_read(run / mark), "job")
        if got and got.lower() != "none":
            return got
    return ""


def _scheduler(jid):
    """{state, walltime, cput} from whatever scheduler is on PATH. {} when none can answer.

    THE FIELD IS NAMED, NEVER POSITIONAL. A scheduler prints CPU time beside wall-clock and they
    differ by the core count; reading whichever column came first turned a 20-minute run into an
    hour-long one. Asking for the key by name costs nothing and cannot make that mistake.
    """
    if not jid:
        return {}
    if shutil.which("qstat"):
        cmd = ["qstat", "-x", "-f", jid]
    elif shutil.which("scontrol"):
        cmd = ["scontrol", "show", "job", jid]
    else:
        return {}
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return {}
    txt = (out.stdout or "") + (out.stderr or "")
    if out.returncode != 0 and "job_state" not in txt.lower():
        # The job is gone from the scheduler entirely. That is a fact about the QUEUE and not
        # about the run - see SEAL_GRACE_S.
        return {"present": False}
    flat = re.sub(r"\n\t", "", txt)
    st = (re.search(r"job_state\s*=\s*(\w+)", flat) or
          re.search(r"JobState=(\w+)", flat) or [None, ""])[1]
    # A SCHEDULER REMEMBERS A JOB AFTER IT ENDS, AND `present` MUST NOT MEAN `remembered`.
    #
    # `qstat -x` answers for finished jobs too - that is what the flag is for - so any state at
    # all was being read as "still going". Measured live: a job cancelled two minutes earlier
    # reported `job_state=F` and this module said RUNNING, which is the single worst answer it
    # can give, because a caller waiting on it waits for ever.
    #
    # So the STATE decides, not the reply. Only states that mean the work has not finished count
    # as present; everything else falls through to the run's own markers, which is where the
    # truth is once a job has ended.
    if st and st.upper() not in LIVE_STATES:
        return {"present": False, "state": st}
    return {"present": True, "state": st,
            "walltime": (re.search(r"resources_used\.walltime\s*=\s*([\d:]+)", flat) or
                         re.search(r"RunTime=([\d:\-]+)", flat) or [None, ""])[1],
            "cput": (re.search(r"resources_used\.cput\s*=\s*([\d:]+)", flat) or [None, ""])[1]}


def state(run):
    """{state, why, job, elapsed, cpu, live_log, since} - the run's true state, from its markers.

    ORDER MATTERS AND IT IS THE SAFE ORDER. FAILED is checked before SEALED because a job that
    wrote both is a job that did not finish cleanly; SEALED before the scheduler because a sealed
    run is finished whatever the queue thinks; and the queue last, where it can only distinguish
    'still going' from 'gone, and not yet accounted for'.
    """
    run = Path(run)
    if not run.is_dir():
        return {"state": ABSENT, "why": "no such run directory", "job": "",
                "elapsed": "", "cpu": "", "live_log": "", "since": ""}
    fail, seal, live = (_read(run / m) for m in (MARK_FAILED, MARK_SEALED, MARK_RUNNING))
    jid = job_id(run)
    base = {"job": jid, "live_log": _field(live, "live log"), "since": _field(live, "started"),
            "elapsed": "", "cpu": ""}
    if fail:
        return dict(base, state=FAILED,
                    why=f"{MARK_FAILED} is present: {_field(fail, 'exit') or 'no exit recorded'}")
    if seal:
        return dict(base, state=SEALED,
                    why=f"{MARK_SEALED} is present, written {_field(seal, 'finished') or '?'}")
    sch = _scheduler(jid)
    if sch.get("present"):
        return dict(base, state=RUNNING,
                    why=f"the scheduler reports job_state={sch.get('state') or '?'}",
                    elapsed=sch.get("walltime") or "", cpu=sch.get("cput") or "")
    quiet = newest_write(run)
    if not jid:
        # NO ID TO ASK ABOUT, SO ASK THE DIRECTORY. This is the case that made the first version
        # useless: a run from a job script that predates RUNNING.txt is still perfectly
        # observable, because something is either writing to it or it is not.
        if quiet is not None and quiet < ACTIVE_S:
            return dict(base, state=RUNNING,
                        why=f"no job id recorded, but the run directory was written to "
                            f"{int(quiet)}s ago, so something is still producing it",
                        elapsed="")
        return dict(base, state=UNKNOWN,
                    why=(f"no job id recorded and nothing has been written to the run for "
                         f"{int(quiet)}s. It has either finished without a marker or stopped."
                         if quiet is not None else
                         f"no {MARK_RUNNING}, no seal, and the run directory cannot be read"))
    # THE CASE THAT WAS GOT WRONG TWICE. The job is not in the queue and no marker is on disk.
    # That is not failure; it is the window between the two.
    age = 0.0
    try:
        age = time.time() - (run / MARK_RUNNING).stat().st_mtime
    except OSError:
        pass
    # THE DIRECTORY OUTRANKS THE QUEUE FOR LIVENESS. A job can be absent from the scheduler this
    # host can see - a different cluster, a scheduler that ages entries out - while its work is
    # visibly still landing. Being written to is positive evidence; being missing from a queue is
    # not evidence of anything.
    if quiet is not None and quiet < ACTIVE_S:
        return dict(base, state=RUNNING,
                    why=f"the scheduler does not report this job, but the run directory was "
                        f"written to {int(quiet)}s ago, so something is still producing it")
    if age < SEAL_GRACE_S:
        return dict(base, state=UNKNOWN,
                    why=f"the job has left the queue and no marker is visible yet. A seal LAGS "
                        f"the queue; this is not failure for another "
                        f"{max(0, int(SEAL_GRACE_S - age))}s")
    return dict(base, state=UNKNOWN,
                why=f"the job left the queue over {int(age)}s ago and wrote neither "
                    f"{MARK_SEALED} nor {MARK_FAILED}. It was probably killed from outside - by "
                    f"the scheduler on a limit, or by a node failure - so its trap never ran. "
                    f"Read the live log; the run directory holds whatever it had written.")


def describe(run):
    """One line an agent can act on."""
    st = state(run)
    bits = [f"{st['state'].upper()}", st["why"]]
    if st.get("elapsed"):
        bits.append(f"wall {st['elapsed']}" + (f", cpu {st['cpu']}" if st.get("cpu") else ""))
    if st.get("job"):
        bits.append(f"job {st['job']}")
    return "  ·  ".join(b for b in bits if b)


def wait(run, timeout_s=None, poll_s=20.0, log=print):
    """Block until the run is SEALED or FAILED. Returns the final state dict.

    THE LOOP IS HERE SO IT IS WRITTEN ONCE. Every hand-rolled version of it in this project got
    the seal-lags-the-queue rule wrong, because the rule is invisible until it bites and then it
    looks like a broken run rather than a broken watcher.
    """
    t0 = time.time()
    last = ""
    while True:
        st = state(run)
        if st["state"] in (SEALED, FAILED):
            return st
        line = describe(run)
        if line != last:
            log(f"  {line}")
            last = line
        if timeout_s is not None and (time.time() - t0) > timeout_s:
            return st
        time.sleep(max(1.0, float(poll_s)))
