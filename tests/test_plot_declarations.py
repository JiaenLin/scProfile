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
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import subject                                                            # noqa: E402
sys.path.insert(0, str(ROOT))
from scprofile import kernels as K, native as N                           # noqa: E402

FAILURES = []
CHECKED = 0


def _own_ids(spec):
    """The ids of the panels the plugin draws ITSELF, from the plan (harness ADR-0016).

    A plan entry drawn by the plugin names no upstream function, on purpose: the interaction
    panels are a difference of two differences the tool has no plot for. A site that draws one is
    claimed by that entry - by the id, or the id followed by the per-item separator - and the
    caption says "drawn by this plugin", which is the truth and not a gap.
    """
    figs = ((spec or {}).get("report") or {}).get("figures") or []
    return [(str(e.get("id")), N.per_item_entry(e)) for e in figs
            if isinstance(e, dict) and e.get("id")
            and str(e.get("drawn_by") or "plugin") != "tool"
            and any(e.get(k) is not None for k in ("fn", "axis", "at_most", "expr"))]


def _own_claims(own, stem):
    return any(N.names_file(i, stem, per) for i, per in own)


# READ THROUGH THE ONE READER. `native.declared_from` is what the accounting and the captions
# read; a plugin migrated onto the plan has no `native_plots` to parse out of its source, and a
# reader that parsed the source stopped checking that plugin the day it migrated - silently,
# with a green line.
for name, k in sorted(K.discover().items()):
    f = k.path
    src = f.read_text()
    decl = N.declared_from(k.spec or {})
    own = _own_ids(k.spec or {})
    if not decl and not own:
        continue
    # EVERY EMBEDDED SCRIPT, WITH THE PREFIX IT DECLARES. Two fixed names read two of a
    # plugin's four scripts and hard-coded what `.figures(prefix = ...)` already says; the
    # per-unit script of the plugin this was written for was never scanned.
    for m in re.finditer(r"^(_R_[A-Z_]+)\s*=\s*r?(\"\"\"|\'\'\')(.*?)\2", src, re.S | re.M):
        body = m.group(3)
        pm = re.search(r'\.figures\(\s*prefix\s*=\s*"([^"]*)"', body)
        if not pm:
            continue
        prefix = pm.group(1)
        # every plot call: npng("name", ...) / ndev("name", ...) / npng(paste0("name__", x), ...)
        for call in re.finditer(r'\b(?:npng|ndev)\(\s*(?:paste0\(\s*)?"([^"]+)"', body):
            stem = prefix + call.group(1)
            CHECKED += 1
            fn = N.function_for(decl, stem + ".png")
            if not fn and _own_claims(own, stem):
                continue
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
