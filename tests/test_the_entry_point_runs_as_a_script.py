"""`_entry.py` is EXECUTED, not imported, so it may not use a relative import.

The host copies this file into the plugin's own environment and runs it with the plugin's
interpreter. It has no parent package there, so `from . import x` raises "attempted relative
import with no known parent package" - and the driver reads a plugin that exits 1 during import
as a broken ENVIRONMENT and answers by force-rebuilding it from source. One added line cost a
unit, a misdiagnosis and a from-source R rebuild before it was read.

Every other import in the file is absolute for this reason. Nothing said so.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


SCRIPTS = ["scprofile/_entry.py"]

for rel in SCRIPTS:
    src = (ROOT / rel).read_text(encoding="utf-8")
    tree = ast.parse(src)
    rel_imports = [(n.lineno, n.module or "", n.level)
                   for n in ast.walk(tree)
                   if isinstance(n, ast.ImportFrom) and (n.level or 0) > 0]
    check(not rel_imports,
          f"{rel} uses a relative import at line(s) "
          f"{[l for l, _m, _lv in rel_imports]}: it is run as a script and has no parent package")

# THE FIXTURE CAN EXPRESS THE FAILURE. Without this, the assertion above passes for a checker
# that never finds an ImportFrom at all.
probe = ast.parse("from . import thing\nfrom scprofile import other\n")
found = [n for n in ast.walk(probe) if isinstance(n, ast.ImportFrom) and (n.level or 0) > 0]
check(len(found) == 1, "the check cannot see a relative import even when one is put in front of it")

# AND IT MUST NOT FIRE ON THE ABSOLUTE ONES THE FILE ACTUALLY USES.
absolute = [n for n in ast.walk(probe) if isinstance(n, ast.ImportFrom) and not (n.level or 0)]
check(len(absolute) == 1, "an absolute import was counted as relative")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: the entry point uses no relative import")
