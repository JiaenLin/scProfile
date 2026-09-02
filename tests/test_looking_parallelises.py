"""Looking at the figures is the step that parallelises, so the tool must cut the work itself.

WHY THIS SUITE EXISTS. Opening every panel is the slowest step in the writing cycle and the one
most often skipped, and those are the same fact: a task nobody can finish in one sitting gets a
glance and a summary instead. It is also the only step that parallelises without argument - the
panels are independent, nothing is computed, and the record is append-only.

Two things have to hold before an agenda may tell an agent to fan it out, and neither is obvious
from reading the code:

1. THE SPLIT IS DISJOINT AND COMPLETE. An agent dividing the list itself is how one figure gets
   two reviews and another gets none - and the second is invisible, because the ledger simply
   goes on reporting it as outstanding.
2. CONCURRENT WRITERS DO NOT CORRUPT THE LEDGER. `open(..., "a")` is atomic on a local
   filesystem; a run under a scheduler lives on a network one, where the client may do its own
   read-modify-write of the offset. Two agents recording at the same instant would then produce
   one interleaved line - a ledger that fails to parse, discovered long after the looks that
   filled it.

WHAT THE SECOND HALF DOES AND DOES NOT PROVE. The forked writers below would very likely pass
with no lock at all, because small O_APPEND writes on a local filesystem do not interleave in
practice - and the filesystem the lock exists for cannot be stood up in a unit test. So it is a
regression guard, and the BEHAVIOUR the lock promises is tested directly beside it: a stale lock
is taken over rather than blocking for ever, and a busy one does not cost a writer its record.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scprofile.review as RV                                                   # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


#: A UNIT DIRECTORY WITH SPACES AND A PIPE IN ITS NAME, because that is what a contrast is
#: called: a simple effect is written `<factor> | <other> = <level>`. Reading the transfer list
#: with `.split()` instead of `.splitlines()` turned 93 paths into 269 tokens, matched none of
#: them, and silently dropped every figure under a contrast directory from the fan-out. The
#: counts were the only symptom.
AWKWARD = "age | diet = chow"


def _fixture(td, per_dir=(7, 5, 4, 3)):
    """A run with several figure directories, the way a plugin writes one per unit."""
    run = Path(td) / "runP"
    made = []
    names = [AWKWARD] + [f"unit{i}" for i in range(1, len(per_dir))]
    for i, n in enumerate(per_dir):
        d = run / "kernels" / "p" / names[i] / "figures"
        d.mkdir(parents=True)
        for j in range(n):
            f = d / f"panel_{j}.png"
            f.write_bytes(b"PNG" + bytes([i, j]))
            made.append(str(f.relative_to(run)))
    (run / "report.json").write_text('{"kernels": {"p": {}}}', encoding="utf-8")
    return run, made


print("the split is disjoint, complete, and keeps a unit's figures together")
with tempfile.TemporaryDirectory() as td:
    run, made = _fixture(td)
    for n in (2, 3, 4):
        groups = RV.shards(run, "p", n)
        flat = [x for g in groups for x in g]
        check(len(groups) == n, f"asked for {n} shards, got {len(groups)}")
        check(sorted(flat) == sorted(made),
              f"the {n}-way split does not cover exactly the outstanding set: "
              f"{sorted(set(flat) ^ set(made))[:3]}")
        check(len(flat) == len(set(flat)),
              f"the {n}-way split repeats a figure, so two agents would review it and the note "
              f"check would refuse the second")
        # SIBLINGS TOGETHER. A differential panel means little without the arm networks beside
        # it, so balancing counts by cutting a unit in half buys an even split and costs the
        # only context that makes a note worth writing.
        home = {}
        for i, g in enumerate(groups):
            for rel in g:
                home.setdefault(str(Path(rel).parent), set()).add(i)
        split = [d for d, where in home.items() if len(where) > 1]
        check(not split, f"the {n}-way split cut these units across shards: {split}")

    # AN EMPTY OUTSTANDING SET STILL RETURNS N GROUPS, so a caller that dispatches per shard
    # dispatches nothing rather than crashing on an index.
    empty = RV.shards(Path(td) / "nothing-here", "p", 3)
    check(len(empty) == 3 and not any(empty),
          "a run with no figures does not return empty shards: %r" % (empty,))

    # AND THE SPLIT IS OVER WHAT IS LEFT, not over everything. A second pass after a partial
    # review must divide only the remainder, or agents re-open panels already recorded.
    RV.record(run, made[0], "the first panel, recorded so the next split has one fewer "
              "to make", plugin="p")
    again = [x for g in RV.shards(run, "p", 2) for x in g]
    check(made[0] not in again,
          "a figure already looked at came back in the split, so the fan-out re-does work")
    check(len(again) == len(made) - 1,
          "the split after one review does not cover the remaining figures: %d of %d"
          % (len(again), len(made) - 1))

    # AND A RESTRICTED SHARD KEEPS THE AWKWARD PATHS. The list is one path per line precisely
    # because paths contain spaces; a reader that splits on whitespace loses exactly the
    # directories a comparison lives in.
    listed = [r for r in made if AWKWARD in r]
    got = [x for g in RV.shards(run, "p", 2, only=listed) for x in g]
    check(sorted(got) == sorted(r for r in listed if r != made[0]),
          "restricting the split to a declared list lost the paths with spaces in them: %r"
          % (sorted(set(got) ^ set(r for r in listed if r != made[0]))[:3],))

print("\ncoverage before volume: every kind is reached before any kind is exhausted")
with tempfile.TemporaryDirectory() as td:
    # ONE KIND DRAWN MANY TIMES, AND A RARE KIND. Reading in path order spends the budget inside
    # the first kind and never reaches the last - which is exactly what happened on a real run:
    # 31 kinds looked at, 50 never opened at all, after 93 looks.
    run = Path(td) / "runK"
    d = run / "kernels" / "p" / "figures"
    d.mkdir(parents=True)
    made = []
    for u in range(20):
        f = d / f"aaa_common_panel__unit{u}.png"
        f.write_bytes(b"PNG-c" + bytes([u]))
        made.append(str(f.relative_to(run)))
    for name in ("zzz_rare_panel__only", "mmm_middle_panel__only"):
        f = d / f"{name}.png"
        f.write_bytes(name.encode())
        made.append(str(f.relative_to(run)))
    (run / "report.json").write_text('{"kernels": {"p": {}}}', encoding="utf-8")

    one = RV.by_kind(run, "p", 1)
    kinds = {RV.kind_of(x) for x in one}
    check(len(one) == 3 and len(kinds) == 3,
          "one-per-kind did not return exactly one of each of the three kinds: %r" % (one,))
    check(any("zzz_rare" in x for x in one),
          "the rare kind was never sampled, which is the whole failure this exists to fix")
    two = RV.by_kind(run, "p", 2)
    # 2 from the kind with twenty instances, and 1 each from the two kinds that have only one -
    # a cap is a maximum, not a quota, and a rare kind must not be padded to reach it.
    check(len(two) == 4, "two-per-kind returned %d, expected 4 (2 + 1 + 1, capped by supply)"
          % len(two))
    check(set(one) <= set(made) and len(set(two)) == len(two),
          "the sample is not drawn from the run, or repeats a figure")
    # AND IT SAMPLES ONLY WHAT IS OUTSTANDING, like every other split here.
    RV.record(run, made[0], "sampled kind check, one common panel recorded before resampling",
              plugin="p")
    check(made[0] not in RV.by_kind(run, "p", 2),
          "a figure already looked at was sampled again")

print("\nconcurrent writers do not corrupt the ledger")
with tempfile.TemporaryDirectory() as td:
    run, made = _fixture(td, per_dir=(8,))
    # FORKED, NOT THREADED. Threads would share the interpreter and prove nothing about a write
    # racing another process's - which is the case an agent fan-out actually creates.
    kids = []
    for i, rel in enumerate(made):
        pid = os.fork()
        if pid == 0:                                                    # pragma: no cover - child
            try:
                RV.record(run, rel, f"child {i} looked at this panel and wrote a distinct note "
                                    f"about what it shows, number {i}", plugin="p")
                os._exit(0)
            except Exception:                                                  # noqa: BLE001
                os._exit(1)
        kids.append(pid)
    bad = 0
    for pid in kids:
        _p, st = os.waitpid(pid, 0)
        bad += 0 if (os.WIFEXITED(st) and os.WEXITSTATUS(st) == 0) else 1
    check(bad == 0, f"{bad} of {len(made)} concurrent writers failed to record")

    led = RV.ledger_path(run, "p")
    lines = [x for x in led.read_text(encoding="utf-8").splitlines() if x.strip()]
    parsed, broken = [], 0
    for x in lines:
        try:
            parsed.append(json.loads(x))
        except ValueError:
            broken += 1
    check(broken == 0, f"{broken} interleaved line(s) in the ledger - concurrent appends are not "
                       f"safe, so the agenda must not tell agents to record at the same time")
    check(len(parsed) == len(made),
          f"{len(parsed)} record(s) survived {len(made)} concurrent writers: a lost append is a "
          f"figure that stays outstanding for ever with nobody able to say why")
    check(len({r["figure"] for r in parsed}) == len(made),
          "two writers recorded the same figure")
    check(not list(led.parent.glob("*.lock")),
          "a lock file was left behind, so the next writer waits out the stale timeout for "
          "nothing")

    # AND THE LOCK ITSELF IS TESTED DIRECTLY, because the fork test above would very likely pass
    # WITHOUT any lock: eight small O_APPEND writes on a local filesystem do not interleave in
    # practice. It is a regression guard, not a proof - the case the lock exists for is a network
    # filesystem, which no unit test here can stand up. What CAN be tested is the behaviour the
    # lock promises, so that is what is checked.
    import time as _t
    lockf = Path(str(led) + ".lock")
    lockf.write_text("999999 nowhere\n", encoding="utf-8")
    os.utime(lockf, (_t.time() - RV.APPEND_STALE_S * 2,) * 2)
    n_before = len(led.read_text(encoding="utf-8").splitlines())
    RV._append_line(led, '{"figure": "stale-lock-probe"}')
    check(len(led.read_text(encoding="utf-8").splitlines()) == n_before + 1,
          "a lock nobody has touched for twice the stale timeout blocked an append, so one "
          "killed agent stops every other agent for ever")
    check(not lockf.exists(), "the taken-over stale lock was not released")

    # A LOCK HELD RIGHT NOW MUST NOT LOSE THE WRITE EITHER. The wait has a deadline, and past it
    # the append proceeds anyway: a look that was actually taken is worth more than the small
    # chance of an interleave, and a writer that silently dropped its record would leave a figure
    # outstanding with nobody able to say why.
    lockf.write_text("1 elsewhere\n", encoding="utf-8")
    RV.APPEND_WAIT_S, _keep = 0.1, RV.APPEND_WAIT_S
    n_before = len(led.read_text(encoding="utf-8").splitlines())
    RV._append_line(led, '{"figure": "busy-lock-probe"}')
    RV.APPEND_WAIT_S = _keep
    check(len(led.read_text(encoding="utf-8").splitlines()) == n_before + 1,
          "an append gave up and lost the record rather than proceeding past the wait deadline")
    lockf.unlink(missing_ok=True)

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("\nok - the work splits cleanly and several agents may record into one ledger")
