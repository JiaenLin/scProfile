"""`--force` must not remove an environment it has no way to rebuild.

MEASURED, ON A REAL CLUSTER. A repair job omitted `module load anaconda3`, so `install --force`
removed a from-source R environment and THEN discovered there was no conda-family manager on
PATH. It printed an accurate and detailed account of what it would have needed. The environment
was gone. A half-built environment had become no environment at all, and the job that was meant
to fix it is what finished it off.

The check is the same one the build makes; it is asked earlier. It fires only when the lock
actually needs a manager - a lock whose conda section is empty builds as a venv and must not be
refused for the absence of a tool it will never call.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scprofile.runner as R                                              # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


body = __import__("inspect").getsource(R)

# THE ORDER IS THE WHOLE PROPERTY, so it is asserted on the source: the refusal has to be
# upstream of the rmtree, and a test that only called the function on a machine WITH conda would
# pass whatever the order was.
i_refuse = body.find("this lock needs conda")
i_rm = body.find("shutil.rmtree(p)")
check(i_refuse != -1, "the precondition refusal is gone")
check(i_rm != -1, "the removal is gone; this test is checking nothing")
check(i_refuse != -1 and i_rm != -1 and i_refuse < i_rm,
      "the environment is removed before anything checks that it can be rebuilt")

# AND IT IS CONDITIONAL. Refusing whenever a manager is absent would break every venv-only lock
# on every machine without conda - the case the builder explicitly adapts to.
window = body[i_refuse - 700:i_refuse] if i_refuse > 700 else body[:i_refuse]
check('spec["conda"]' in window,
      "the refusal does not depend on the lock actually needing conda packages, so a venv-only "
      "lock would be refused for the absence of a manager it never calls")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: --force checks it can rebuild before it removes")
