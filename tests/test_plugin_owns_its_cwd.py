"""A plugin must run in a directory it owns, so a wrapped tool cannot write into the project.

Nothing set a working directory, so every plugin inherited the one the job was launched from.
A wrapped tool that writes to the current directory then writes into the PROJECT: measured,
CellChat's netVisual and its cluster-number estimator dropped eight plates and a PDF at the
project root, beside the stage directories, on a run whose output was supposed to be sealed
inside its own run key. Nothing failed and nothing said so - the files were simply there.

This is checked on the source because it is invisible at runtime: a run that litters completes
normally and produces a correct report.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []

#: (file, the call that launches a plugin, what it must be given)
LAUNCHES = [("scprofile/runner.py", "manifest.env_for_kernel"),
            ("scprofile/report.py", '"--compare"')]

for rel, marker in LAUNCHES:
    src = (ROOT / rel).read_text()
    # find the subprocess.run(...) call containing the marker, brackets matched
    idx = src.find(marker)
    if idx < 0:
        FAILURES.append(f"{rel}: could not find the plugin launch at all ({marker})")
        continue
    start = src.rfind("subprocess.run(", 0, idx)
    if start < 0:
        FAILURES.append(f"{rel}: {marker} is not inside a subprocess.run call")
        continue
    depth, end = 0, start
    for j in range(src.index("(", start), len(src)):
        if src[j] == "(":
            depth += 1
        elif src[j] == ")":
            depth -= 1
            if depth == 0:
                end = j
                break
    call = src[start:end + 1]
    if "cwd=" not in call:
        FAILURES.append(f"{rel}: the plugin is launched with no cwd, so it inherits the "
                        f"directory the job was started in and anything the wrapped tool "
                        f"writes to the current directory lands in the project")
    elif not re.search(r"cwd=str\(", call):
        FAILURES.append(f"{rel}: cwd is passed but not as a string; subprocess is strict here")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print(f"ok: {len(LAUNCHES)} plugin launch site(s) run in a directory the instance owns")
