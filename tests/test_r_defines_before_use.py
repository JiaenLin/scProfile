"""An embedded R script must define a helper BEFORE it calls it. R does not hoist.

WHAT THIS COST: a phase clock was added to measure where a run spends its time, and `mark` was
defined next to the other helpers - far below its first call. Every unit of the run died on
`Error in mark("read the matrix") : could not find function "mark"`, after the host had already
written a 1.4 GB matrix for each of them. Python would have accepted the same arrangement, which
is exactly why this is easy to write and easy to miss.

Only helpers the script defines ITSELF are checked; anything from a library is out of scope.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []
CHECKED = 0

for f in sorted((ROOT / "kernels").glob("*.py")):
    src = f.read_text()
    q3 = chr(34) * 3
    pat = r"(_R_[A-Z_]+)\s*=\s*r?(" + q3 + "|'''" + r")(.*?)\2"
    for m in re.finditer(pat, src, re.S):
        name, body = m.group(1), m.group(3)
        # `fn <- function(` at the start of a line is a definition this script owns
        defs = {d.group(1): d.start()
                for d in re.finditer(r"^([A-Za-z_.][\w.]*)\s*<-\s*function\s*\(", body, re.M)}
        if not defs:
            continue
        CHECKED += 1
        for fn, at in defs.items():
            # the first CALL that is not the definition itself
            first = None
            for c in re.finditer(r"(?<![\w.$])" + re.escape(fn) + r"\s*\(", body):
                if abs(c.start() - at) < 2:
                    continue
                if body[max(0, c.start() - 30):c.start()].rstrip().endswith("<-"):
                    continue
                first = c.start()
                break
            if first is not None and first < at:
                line = body[:first].count("\n") + 1
                dline = body[:at].count("\n") + 1
                FAILURES.append(
                    f"{f.name} / {name}: `{fn}` is called at line {line} and only defined at "
                    f"line {dline}. R does not hoist; this dies at run time.")

if CHECKED == 0:
    print("FAIL")
    print("  - no embedded R script defines a helper; this check proved nothing")
    raise SystemExit(1)
if FAILURES:
    print("FAIL")
    for x in FAILURES:
        print("  -", x)
    raise SystemExit(1)
print(f"ok: {CHECKED} embedded R script(s); every helper is defined before it is called")
