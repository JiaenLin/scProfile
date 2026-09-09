"""A selftest that was KILLED is not a plugin that failed, and the message could not tell you.

MEASURED, ACROSS THREE SUBMISSIONS. The same environment was asked to prove the same seven
members on two nodes: it proved five, then four, then two, with no change to any plugin that
could account for it. Every failure printed "SELFTEST FAILED" followed by the plugin's log - and
that log held three FutureWarnings from an import and nothing else, because the process had been
killed before it could write anything.

So the message arrived with no diagnosis and read as a broken plugin. It is a machine, and the
first thing to look at is the node and its limits - which is exactly what the reader cannot know
from a message that omits the one number that says so. `subprocess` returns a NEGATIVE code for a
signal; -9 is a kill.

This is the third place in one day the same defect was found: the R extractor reported "produced
no answer:" with both streams empty and no status, and a job's checker graded a rebuild it had
watched fail. A failure that cannot say what kind of failure it is costs more than the failure.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


src = (ROOT / "scprofile" / "runner.py").read_text(encoding="utf-8")
block = src[src.index("    out = logf.read_text"):]
block = block[:block.index("# Print it on SUCCESS too")]

check("exit {r.returncode}" in block,
      "the failure message does not carry the exit status")
check("r.returncode < 0" in block,
      "nothing distinguishes a signal from a non-zero exit")
check("SIGKILL" in block,
      "the one signal a batch node actually sends is not named")
check("memory cgroup" in block,
      "a kill does not point the reader at the node's limits")
check("nothing but warnings" in block,
      "a log holding only warnings is not called out as saying nothing")

# the three places, so a fourth is noticed
r_ext = (ROOT.parent / "single-cell-harness" / "sch" / "dev" / "extract" / "r_namespace.py")
if r_ext.is_file():
    rs = r_ext.read_text(encoding="utf-8")
    check("p.returncode" in rs and "both stdout and stderr were empty" in rs,
          "the R extractor stopped reporting its exit status")

if fails:
    print("FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ok - a killed selftest names the signal and points at the node, not at the plugin")
