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
        "SEARCH": {"plan", "run"}, "DES": {"plan", "run"},
        "SECTION": {"run"}, "NOCACHE": {"run"}}

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

# CONTROL is expanded into an array rather than a ${VAR:+...} because --control repeats, so it
# is checked separately: the array must be built and it must reach `run`.
_run = " ".join(inv.get("run") or [])
if "${CTRL[@]}" not in _run and "$CTRL" not in _run:
    FAILURES.append("CONTROL is never expanded into the run invocation, so a declared control "
                    "does not reach the tool and the direction falls back to a recommendation")
# PARAMS must be built AND reach `run`, or a run meant to test another setting repeats the first
_run2 = " ".join(inv.get("run") or [])
if "PARAMJSON" not in _run2:
    FAILURES.append("PARAMS is never passed to `run`, so a config override is accepted on the "
                    "qsub line and silently ignored")
if "PARAMS" not in (src[:src.index("set -")] if "set -" in src else src):
    FAILURES.append("PARAMS is consumed but not documented in the header")

if "CTRL+=(--control" not in src:
    FAILURES.append("the job does not build the --control array")
# `-v` SPLITS ITS OWN VALUE ON COMMAS. A comma-separated list is torn apart by PBS before the
# script sees it: measured, a two-factor declaration arrived with only its first entry and the
# second factor fell back silently to alphabetical order.
if "IFS=','" in src:
    FAILURES.append("a multi-value variable is split on commas, which `-v` has already used as "
                    "its own separator - the second entry never arrives")
if "CONTROL" not in (src[:src.index("set -")] if "set -" in src else src):
    FAILURES.append("CONTROL is consumed but not documented in the header")

# EVERY variable the file consumes is documented in its own header, or a user cannot know it
# exists. The header is the only place a qsub line is described.
header = src[:src.index("set -")] if "set -" in src else src[:4000]
#: Names the script DERIVES for itself rather than accepting from the caller. They need no
#: header entry because nobody can pass them; documenting the input that produces them is the
#: thing that helps a reader.
DERIVED = {"PARAMJSON"}

for var in sorted({m.group(1) for m in re.finditer(r"\$\{(\w+):\+", flat)} - DERIVED):
    if var not in header:
        FAILURES.append(f"${var} is consumed but not documented in the header")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print(f"ok: {len(WANT)} job variable(s) reach exactly the invocations they are for, "
      f"and every optional variable is documented")
