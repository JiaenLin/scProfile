"""Adjacent string literals do not concatenate in R, and this file is half Python.

Python joins `"a" "b"` into `"ab"`. R does not: inside a `paste0(...)` a missing comma between
two literals is a syntax error, and Rscript parses the whole file before running any of it - so
it halts the script.

WHAT IT COST. The cohort script drew its overview bars, entered the framing loop and stopped, so
the run produced a plausible partial output - four design-wide figures where there should have
been sixteen, and every interaction panel missing - while every other page rendered normally.
One line said `compare across arms FAILED`, and nothing else in the run looked wrong.

The two languages live in one file here, which is precisely the condition for carrying a habit
across the boundary. A Python author writing an R string will do this again; a parse of the R
would catch it, but there is no R on the machine where these files are edited, so the check is
textual and runs anywhere.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []


def blocks(src):
    """{name: body} for every embedded R script - the same extraction the argv guard uses."""
    out = {}
    q3 = chr(34) * 3
    pat = r'(_R_[A-Z_]+)\s*=\s*r?(' + q3 + "|'''" + r')(.*?)\2'
    for m in re.finditer(pat, src, re.S):
        out[m.group(1)] = m.group(3)
    return out


checked = 0
for f in sorted((ROOT / "kernels").glob("*.py")):
    for name, body in blocks(f.read_text(encoding="utf-8")).items():
        checked += 1
        lines = body.splitlines()
        for i in range(len(lines) - 1):
            a, b = lines[i].rstrip(), lines[i + 1].strip()
            # A line ending in a closing quote followed by one opening with a quote. In R the
            # only way that is legal is if the first line's quote closes an argument that the
            # separator was forgotten after - which is the defect.
            if a.endswith('"') and b.startswith('"') and not a.endswith('\\"'):
                FAILURES.append(
                    f"{f.name} / {name}: line {i + 1} ends a string literal and line {i + 2} "
                    f"begins another with no comma between them - R does not concatenate "
                    f"adjacent literals and will not parse the script\n"
                    f"      {a[-58:]}\n      {b[:58]}")

if not checked:
    print("FAIL")
    print("  - no embedded R script was found; this proved nothing")
    raise SystemExit(1)
if FAILURES:
    print("FAIL")
    for x in FAILURES[:6]:
        print("  -", x)
    raise SystemExit(1)
print(f"ok - {checked} embedded script(s), no adjacent string literals in any of them")
