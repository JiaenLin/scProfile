"""A look taken on an image counts on any run holding that same image.

A review is bound to a figure's sha256 - redraw it and the review is gone, which is right. But
the ledger lived only INSIDE the run directory, so a run that reused every fitted object and
redrew nothing still reported every figure as never looked at: 672 of them, on every run.

Honouring that means re-reviewing an unchanged figure set every time, which nobody does. A gate
that demands the impossible is a gate that is off, and this one had been off since it was built.

So a second ledger sits BESIDE the run directories, keyed by the image rather than by the path.
The run keeps its own complete account; the carried one is what stops unchanged bytes being
presented as unexamined. Checked on real files with real digests, because the whole mechanism is
about bytes.
"""
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

    # THE RUN'S OWN ACCOUNT IS STILL COMPLETE - the carry is in addition, not instead.
    check("kernels/p/figures/same.png" in R.read_ledger(a, "p"),
          "the look was not recorded in the run it was taken in")
    check(R.carried_path(a) == R.carried_path(b),
          "two runs of one stage resolve different carried ledgers, so nothing is shared")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - a look carries to identical bytes, never to redrawn ones, and the run still records it")
