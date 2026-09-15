"""A look taken on an image counts on any run holding that same image.

A review is bound to a figure's sha256 - redraw it and the review is gone, which is right. But
the ledger lived only INSIDE the run directory, so a run that reused every fitted object and
redrew nothing still reported every figure as never looked at: 672 of them, on every run.

Honouring that means re-reviewing an unchanged figure set every time, which nobody does. A gate
that demands the impossible is a gate that is off, and this one had been off since it was built.

So a look is carried by READING the sibling runs' own ledgers, keyed by the image rather than by
the path. Nothing extra is written, and a sibling counts only if it is a run - a directory
carrying a `report.json`.

That last clause is not decoration. The first version wrote a shared ledger at the run's parent,
which is a guess about layout dressed as a fact: for a run in a temp directory it lands in the
system temp directory and carries looks between runs that have nothing to do with each other. A
contract test creating a run under /tmp caught it on the first execution.

Checked on real files with real digests, because the whole mechanism is about bytes.
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tempfile                                                           # noqa: E402
from scprofile import review as R                                         # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


def _mkfig(run, rel, data):
    p = Path(run) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


with tempfile.TemporaryDirectory() as td:
    stage = Path(td) / "04_stage"
    a, b = stage / "runA", stage / "runB"
    for r in (a, b):
        _mkfig(r, "kernels/p/figures/same.png", b"IDENTICAL-BYTES")
        # A SIBLING COUNTS ONLY IF IT IS A RUN. Without this marker neither directory is one,
        # and nothing should carry - which is the isolation an unrelated directory relies on.
        (r / "report.json").write_text("{}", encoding="utf-8")
    _mkfig(b, "kernels/p/figures/redrawn.png", b"NEW-BYTES")
    _mkfig(a, "kernels/p/figures/redrawn.png", b"OLD-BYTES")

    R.record(a, "kernels/p/figures/same.png", "the shared panel reads correctly on run A",
             plugin="p")
    R.record(a, "kernels/p/figures/redrawn.png", "this one will be redrawn before run B",
             plugin="p")

    st = dict((r, s) for r, s, _w in R.status(b, "p"))
    check(st.get("kernels/p/figures/same.png") == R.CARRIED_OK,
          "an identical image is %r on the next run - the look did not survive, so an unchanged "
          "figure set must be re-reviewed every run"
          % (st.get("kernels/p/figures/same.png"),))
    check(st.get("kernels/p/figures/redrawn.png") == R.UNREVIEWED,
          "a REDRAWN figure carried a look across from different bytes: %r"
          % (st.get("kernels/p/figures/redrawn.png"),))

    out = {r for r, _s in R.outstanding(b, "p")}
    check("kernels/p/figures/same.png" not in out,
          "a carried look is still counted as outstanding, so the brief will demand it again")
    check("kernels/p/figures/redrawn.png" in out,
          "a redrawn figure is not outstanding, so a changed image passes as looked at")

    # AND THE LISTING SAYS THE SAME AS THE COUNT (harness ADR-0020, the second rerun): the
    # status counted the carried look as reviewed and the shards left it out, and the listing
    # under it printed the same figure under "have not been looked at ... Open each one" -
    # fifty-six of them on the rerun, every one already looked at on identical bytes.
    import subprocess
    p = subprocess.run([sys.executable, "-m", "scprofile.cli", "review", "--out", str(b),
                        "--plugin", "p"], capture_output=True, text=True, cwd=str(ROOT),
                       env={**os.environ, "PYTHONPATH": str(ROOT)})
    listed = p.stdout.split("Open each one")[0] if "Open each one" in p.stdout else ""
    check("same.png" not in listed,
          "the listing tells the reader to open a figure whose look carried:\n" + p.stdout[:600])

    # THE RUN'S OWN ACCOUNT IS STILL COMPLETE - the carry is in addition, not instead.
    check("kernels/p/figures/same.png" in R.read_ledger(a, "p"),
          "the look was not recorded in the run it was taken in")
    check([d.name for d in R.sibling_runs(b)] == ["runA"],
          "run B does not see run A as a sibling run, so nothing can carry")

    # A RUN'S OWN LEDGER CAN ADOPT WHAT IT RELIES ON (harness ADR-0025, found by the writing
    # seal): the carry is a read-time view across siblings, and a run whose written layer is
    # sealed elsewhere - a replay on another machine, with no sibling beside it - reads every
    # carried look as never taken. `adopt` appends each carried look and stated answer to the
    # run's own ledger, naming the run it came from, so the ledger stands on its own.
    R.answer(a, "kernels/p/figures/same.png",
             "the shared panel is right as the upstream draws it, by its own design", by="x",
             plugin="p")
    got = R.adopt(b, "p")
    check(got.get("looks") == 1 and got.get("answers") == 1,
          f"adopt did not take the sibling's look and answer: {got}")
    own = R.read_ledger(b, "p")
    check("kernels/p/figures/same.png" in own
          and own["kernels/p/figures/same.png"].get("carried_from") == "runA",
          "the adopted look is not in run B's own ledger, named for the run it came from")
    lone2 = Path(td) / "alone" / "runB2"
    _mkfig(lone2, "kernels/p/figures/same.png", b"IDENTICAL-BYTES")
    (lone2 / "report.json").write_text("{}", encoding="utf-8")
    shutil.copy(R.ledger_path(b, "p"), R.ledger_path(lone2, "p"))
    st4 = dict((r, s_) for r, s_, _w in R.status(lone2, "p"))
    check(st4.get("kernels/p/figures/same.png") == R.REVIEWED,
          "the adopted look does not count once the run stands alone: %r"
          % (st4.get("kernels/p/figures/same.png"),))
    check(R.adopt(b, "p") == {"looks": 0, "answers": 0},
          "adopting twice appends the same records again")
    check(not any("kernels/p/figures/redrawn.png" == k for k in own if own[k].get("carried_from")),
          "a look on different bytes was adopted")

    # AND A DIRECTORY THAT IS NOT A RUN CARRIES NOTHING, whatever it holds.
    lone = Path(td) / "elsewhere" / "runC"
    _mkfig(lone, "kernels/p/figures/same.png", b"IDENTICAL-BYTES")
    st3 = dict((r, s_) for r, s_, _w in R.status(lone, "p"))
    check(st3.get("kernels/p/figures/same.png") == R.UNREVIEWED,
          "an unrelated directory inherited a look from a run it has nothing to do with: %r"
          % (st3.get("kernels/p/figures/same.png"),))

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - a look carries to identical bytes, never to redrawn ones, and the run still records it")
