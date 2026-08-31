"""Both cache layers must decline to rewrite what they just read, and both must say so.

The matrix store had this right from the start - on a hit it logs "not rewritten" and leaves the
file alone. The object store, sitting beside it in the same script, re-wrote the `.rds` it had
just loaded from that same path under that same stamp. Measured on eighteen units: 1.02 GB
written back byte-identical every run.

The cost is the smaller half. The mtime is the larger one: a cache HIT moved the object's
timestamp forward, so a cached input came to look NEWER than the artifacts derived from it -
which is the one direction a freshness check cannot tolerate, and it fired on correct behaviour.

Two layers sitting in one file and disagreeing about their own contract is the defect; this
checks they agree, not that either is spelled a particular way.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SRC = (ROOT / "kernels" / "cellchat.py").read_text(encoding="utf-8")
FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


# MATCH THE WORD, NOT THE PHRASE. The matrix store builds its message across a line
# continuation - "MB not " then "rewritten" - so "not rewritten" as one string appears in only
# one of the two layers and this check failed on code that was correct. Comment lines are
# excluded so that DESCRIBING the contract never satisfies it.
_said = [ln for ln in SRC.splitlines()
         if "rewritten" in ln and not ln.lstrip().startswith("#")]
check(len(_said) >= 2,
      "only one cache layer reports declining to rewrite on a hit; the other still writes back "
      "what it just read (found: %r)" % (_said,))

# The object store's write must be REACHABLE ONLY when the object was not loaded. Checking the
# guard exists is not enough - it has to be the thing the write hangs off.
m = re.search(r"\.from_cache <- !is\.null\(cc\)", SRC)
w = re.search(r"saveRDS\(cc, rds_tmp\)", SRC)
check(bool(m), "nothing records whether the CellChat object came from the cache")
check(bool(w), "the object store no longer writes at all, which is a different bug")
if m and w:
    check(m.start() < w.start(),
          "the cache flag is set AFTER the write that depends on it")
    between = SRC[m.start():w.start()]
    check("if (.from_cache)" in between,
          "saveRDS is not guarded by the cache flag, so a hit still rewrites the object")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - both cache layers decline the rewrite on a hit and both say so")
