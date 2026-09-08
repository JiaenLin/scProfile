"""Every panel the plugin's own code draws must be claimed by a declared upstream function.

THE ACCOUNTING AND THE CODE DRIFT SILENTLY. `native_plots` says which upstream functions are
used and names the file each writes; the R (or Python) the plugin runs is what actually draws
them. Nothing connected the two, so a function could be marked used while drawing nothing, and a
panel could appear on the page with no declared origin - which is how two comparison panels came
to have no function named against them at all, and a caption could not say what drew them.

This walks the plot calls in each plugin's embedded script, and asks `native.function_for` -
the same inversion the report uses to caption a panel - to name a declared function for each.
An unclaimed panel fails. It is deliberately the same code path as the captions, so a caption
that would read "(drawn by an undeclared function)" fails here first.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import subject                                                            # noqa: E402
sys.path.insert(0, str(ROOT))
from scprofile import native as N                                         # noqa: E402

FAILURES = []
CHECKED = 0


def _declaration(src):
    m = re.search(r'"native_plots":\s*\{', src)
    if not m:
        return None
    i = src.index("{", m.start())
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                break
    try:
        return ast.literal_eval(src[i:j + 1])
    except Exception:                                                     # noqa: BLE001
        return None


for f in sorted((ROOT / "kernels").glob("*.py")):
    src = f.read_text()
    decl = _declaration(src)
    if not decl:
        continue
    for var, prefix in (("_R_RUN", "native_"), ("_R_COMPARE", "nativecmp_")):
        m = re.search(var + r'\s*=\s*r?"""(.*?)"""', src, re.S)
        if not m:
            continue
        body = m.group(1)
        # every plot call: npng("name", ...) / ndev("name", ...) / npng(paste0("name__", x), ...)
        for call in re.finditer(r'\b(?:npng|ndev)\(\s*(?:paste0\(\s*)?"([^"]+)"', body):
            stem = prefix + call.group(1)
            CHECKED += 1
            fn = N.function_for(decl, stem + ".png")
            if not fn:
                FAILURES.append(f"{f.name}: {stem}.png is drawn but no declared function "
                                f"claims it - a caption cannot say what drew it")
            elif "skip" in (decl.get(fn) or {}):
                FAILURES.append(f"{f.name}: {stem}.png is drawn by {fn}, which is declared "
                                f"SKIPPED - the accounting says it is unused and it is used")

# NOTHING FOUND IS TWO FINDINGS, and this asserted the worse one. It printed FAIL and exited 1
# when a single plugin was removed, reporting a repository with none of this in it as a fault in
# the checking. `subject.nothing_found` asks a second, cruder question - is the marker in any
# kernel's raw text - and only the two answers together are decisive.
if not CHECKED:
    _kind, _why = subject.nothing_found('npng(', 'draws a panel from an embedded R script')
    if _kind == "broken":
        print("FAIL")
        print("  - " + _why)
        raise SystemExit(1)
    print("skipped - " + _why)
    raise SystemExit(0)
if FAILURES:
    print("FAIL")
    for x in FAILURES:
        print("  -", x)
    raise SystemExit(1)
print(f"ok: {CHECKED} drawn panel(s), every one claimed by a declared upstream function")
