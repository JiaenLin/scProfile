"""The authored section and the derived panel must travel with the run, not follow it.

Before this, both were reachable only through `paper --render` after the run finished. So every
fresh run had figures and no section and no panel, and the newest run in a directory looked
incomplete when the only thing missing was writing. The panel needs no author at all - it is
derived from the design and the plugin's declared routes - and the section, though authored, has
no reason to live outside the run that produced its figures.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []
cli = (ROOT / "scprofile" / "cli.py").read_text()
rep = (ROOT / "scprofile" / "report.py").read_text()

if '"--section"' not in cli:
    FAILURES.append("run has no --section, so a written result cannot be carried into a run")
if "_carry_section(" not in cli or cli.count("_carry_section(") < 2:
    FAILURES.append("--section is declared but the run never acts on it")
if "PA.panel(" not in rep and "_PA.panel(" not in rep:
    FAILURES.append("a run does not write the figure panel, which needs no author")
# AN ABSENCE THAT NEEDS EXPLAINING IS A DEFECT. A run with figures and no section looks broken
# to anyone who opens it, with no way to tell missing from failed from never-intended.
if "No written result section in this run" not in rep:
    FAILURES.append("a run without a written section says nothing about it, so the absence "
                    "reads as a fault rather than a fact")
# claims must NOT be carried: they are bound to figures by digest, and figures are redrawn
m = re.search(r"def _carry_section\(.*?\n(?=\ndef )", cli, re.S)
if m and re.search(r"--claim|_PA\.claim\(", m.group(0)):
    FAILURES.append("the section carry also copies claims; a claim copied across a run is about "
                    "figures that were redrawn since")
# and the except clause must not shadow the module's escape helper
if re.search(r"except Exception as _e:", rep):
    FAILURES.append("report.py binds `_e` in an except clause, which shadows the HTML escape "
                    "helper for the whole function")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ok: the panel is written by the run, the section can be carried into it, and claims are "
      "not copied across redrawn figures")
