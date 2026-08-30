"""Every variable the job accepts must reach the invocation it is for, and be documented.

TWO FAILURES OF THE SAME SHAPE, BOTH SILENT. `LABEL` was accepted on the qsub line and reached
`plan` but not `run`, so a run planned one label column and profiled another with nothing in its
output saying so. `REUSE` was worse: the host had `--reuse-from` from the start and this file
never passed it at all, so every run recomputed every instance and the adopt machinery sat
unreachable behind a flag nobody sent.

Neither is visible at runtime. A job with a dropped flag runs to completion and produces a
report. So the check is on the text of the job script, and it is about WHICH invocation each
flag lands in - counting occurrences is not enough, and a count is what let LABEL through.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOB = ROOT / "setup" / "dev_cycle.pbs"

#: variable -> the scprofile subcommands it MUST reach. A variable for `run` alone that also
#: reached `plan` would be as wrong as the reverse; both are stated.
WANT = {"LABEL": {"plan", "run"}, "REUSE": {"run"}, "REUSE_GRADE": {"run"},
        "SEARCH": {"plan", "run"}, "DES": {"plan", "run"}}

FAILURES = []
src = JOB.read_text()

# Split into invocations: everything from `scprofile.cli <sub>` to the end of that continued
# command. Line continuations mean a command spans lines, so the join happens first.
flat = re.sub(r"\\\n\s*", " ", src)
inv = {}
for m in re.finditer(r"scprofile\.cli\s+(\w+)(.*?)(?:\n|$)", flat):
    inv.setdefault(m.group(1), []).append(m.group(2))

for var, subs in WANT.items():
    for sub in subs:
        bodies = inv.get(sub) or []
        if not bodies:
            FAILURES.append(f"no `{sub}` invocation found at all")
            continue
        if not any(f"${{{var}:+" in b for b in bodies):
            FAILURES.append(f"${var} never reaches `{sub}` "
                            f"(found in: {sorted(k for k, v in inv.items() if any(f'${{{var}:+' in x for x in v))})")
    for sub, bodies in inv.items():
        if sub not in subs and any(f"${{{var}:+" in b for b in bodies):
            FAILURES.append(f"${var} reaches `{sub}`, which is not one of {sorted(subs)}")

# EVERY variable the file consumes is documented in its own header, or a user cannot know it
# exists. The header is the only place a qsub line is described.
header = src[:src.index("set -")] if "set -" in src else src[:4000]
for var in sorted({m.group(1) for m in re.finditer(r"\$\{(\w+):\+", flat)}):
    if var not in header:
        FAILURES.append(f"${var} is consumed but not documented in the header")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print(f"ok: {len(WANT)} job variable(s) reach exactly the invocations they are for, "
      f"and every optional variable is documented")
