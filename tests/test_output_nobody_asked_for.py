"""A run's output must be accounted for in BOTH directions: promised-and-not-drawn, and
drawn-and-promised-by-nobody.

`native.undrawn` has asked the first since a plugin's three declared plots turned out to draw
nothing on a full run. The second was asked by nothing, and a cohort of 1187 figures carried 24
`estimationNumCluster*.pdf` written by the NMF rank estimation inside an upstream function - not
by any call the plugin makes, named by no declaration, linked from no page, cited by no sentence.
Nothing in the tool could tell them from output somebody had asked for.

THE HOST'S OWN PANELS ARE NOT THE PLUGIN'S LITTER, and the first version of this check reported
84 of them as unaccounted for. They are filed beside the plugin's as `<plugin>_<fid>` and the
check has to be TOLD what the host draws; it cannot be left to guess from the name.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scprofile.native as N                                              # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


# Invented names: a host that passed by recognising a real cellchat panel would fail here.
DECL = {"fnA": {"use": "figures/thing_count.png and thing_weight.png"},
        "fnB": {"use": "figures/perthing__<item>.png"},
        "fnC": {"skip": "not_applicable"}}
FILES = ["u1/figures/thing_count.png", "u1/figures/thing_weight.png",
         "u1/figures/perthing__alpha.png", "u2/figures/perthing__beta.png",
         "u1/figures/ownplate.png",
         "u1/figures/hostpanel_X1_something__u1.png",
         "u1/figures/sideeffect_estimate.pdf", "u2/figures/sideeffect_estimate.pdf"]

got = dict(N.undeclared(DECL, FILES, ids=["ownplate", "hostpanel_X1_something"]))
check(got == {"sideeffect_estimate": 2},
      "the backwards question got the wrong answer: %r" % (got,))

# THE FIXTURE CAN EXPRESS THE FAILURE. Without the ids, the accounted-for files must show up -
# otherwise the assertion above passes for a check that reports nothing at all.
blind = dict(N.undeclared(DECL, FILES, ids=()))
check("ownplate" in blind and "hostpanel_X1_something" in blind,
      "with nothing declared as accounted for, the check still found only the litter - it is "
      "not looking at the other files at all: %r" % (blind,))

# A PLACEHOLDER FAMILY IS ONE PROMISE, however many files it becomes.
check("perthing" not in got, "a declared <item> family was reported as unasked-for output")

# A SKIPPED ENTRY PROMISES NOTHING and must not make unrelated output look accounted for.
check(N.undeclared({"fnC": {"skip": "not_applicable"}}, ["a/x.png"], ids=()) == [("x", 1)],
      "a skip ruling was read as accounting for a file")

# COUNTED PER FAMILY, not per file: 24 rows of the same name is a list nobody reads.
many = dict(N.undeclared({}, [f"u{i}/figures/litter__u{i}.pdf" for i in range(24)], ids=()))
check(many == {"litter": 24}, "litter was not collapsed to one row with its count: %r" % (many,))


# A PROMISE IS KEPT BY A FILE OF ANY FIGURE FORMAT. The rank-estimation plate is written as a
# PDF by the tool itself; declared on the plan its promise reads `figures/<id>.png`, and a check
# that swept only the PNGs reported it never drawn on a run that holds twenty-four of them
# (ADR-0016 step 4e, first reproduction).
import io as _io
import tempfile as _tf
from contextlib import redirect_stdout as _rs
from scprofile import cli as _CLI, kernels as _K
_cc = _K.discover().get("cellchat")
if _cc is not None:
    with _tf.TemporaryDirectory() as _td:
        _run = Path(_td) / "20260101T000000Z__scprofile-abc__s"
        _fig = _run / "kernels" / "cellchat" / "U1" / "figures"
        _fig.mkdir(parents=True)
        (_fig / "estimationNumCluster__functional.pdf").write_bytes(b"%PDF-1.4\n")
        _buf = _io.StringIO()
        with _rs(_buf):
            _CLI._promised(_run)
        _txt = _buf.getvalue()
        _gap_block = _txt.split("DECLARED AND NEVER DRAWN", 1)[-1]
        check("netClustering" not in _gap_block,
              "a promise kept by a PDF is reported as never drawn - the sweep read the PNGs alone")
        check("DECLARED AND NEVER DRAWN" in _txt,
              "the other promises of a one-file run must still read as never drawn, or this "
              "proves nothing")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: output nobody asked for is reported, and the host's own panels are not it")
