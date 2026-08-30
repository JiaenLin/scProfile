"""The declared controls must be in report.json, because every rebuild reads that file.

They were set on the payload AFTER report.json was written. So the run itself used the declared
reference, and the file every later command reads carried no controls at all - `scprofile report`
on the same run fell back to alphabetical order and drew every contrast against the opposite
reference. One run, two directions, depending on which command last touched it, and both
rendered without complaint.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []
src = (ROOT / "scprofile" / "cli.py").read_text()

i_set = src.find('payload["controls"] = _controls_from(a)')
i_json = src.find('(out / "report.json").write_text')
if i_set < 0:
    FAILURES.append("the declared controls are never recorded on the payload")
elif i_json < 0:
    FAILURES.append("report.json is never written")
elif i_set > i_json:
    FAILURES.append("the controls are set AFTER report.json is written, so every rebuild reads a "
                    "file with no controls and reverses the direction of every contrast")

# and the reader must actually use them
rep = (ROOT / "scprofile" / "report.py").read_text()
if 'controls=(payload_all or {}).get("controls")' not in rep:
    FAILURES.append("the reporter does not read the controls out of the payload")
if "arm_pairs(design, controls=controls)" not in rep:
    FAILURES.append("the contrasts are built without the controls")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ok: the controls are recorded before report.json and read back by the reporter")
