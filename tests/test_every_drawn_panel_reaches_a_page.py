"""A panel a plugin declares must be reachable by some evidence route, or nothing can cite it.

DECLARING A PANEL IS NOT PLACING IT. The paper and the figure panel both index figures by the
NEED each answers, through `provides_evidence`. A panel declared in `native_plots` with no route
pointing at its function is drawn on every run, costs what it costs, and reaches no page - not
the paper, not the panel, not even the brief that tells an agent which figures to open.

It has happened twice here. The comment in the cellchat declaration records the first: a heatmap
"drawn on every run and placed in no paper". The second was the ligand-receptor interaction
panels, added to answer a review comment, drawn correctly, cited by nothing - found only by
reading the brief and noticing the numbers stopped short.

A panel may legitimately have no route: the profile set is placed by its own `profile` mark, not
by a need. So the rule is that every declared function is EITHER routed by a need OR marked
profile - and a function that is neither is named here rather than discovered a round later.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []
CHECKED = 0

for f in sorted((ROOT / "kernels").glob("*.py")):
    src = f.read_text(encoding="utf-8")
    # READ THE LITERAL, DO NOT IMPORT THE MODULE. A plugin imports its own environment's
    # packages at module scope, which the host interpreter running the suite does not have - so
    # importing to read a declaration makes the check pass by skipping, which is the failure
    # mode a guard must not have. `ast.literal_eval` on the declaration itself needs nothing.
    spec = {}
    try:
        tree = ast.parse(src)
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            try:
                d = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                continue
            if isinstance(d, dict) and "native_plots" in d:
                spec = d
                break
    except SyntaxError:
        continue
    declared = (spec or {}).get("native_plots") or {}
    routes = ((spec or {}).get("report") or {}).get("provides_evidence") or {}
    if not declared:
        continue
    CHECKED += 1
    routed = {str(r).split(":", 1)[1] for rs in routes.values() for r in rs
              if str(r).startswith("native:")}
    for fn, d in sorted(declared.items()):
        if not isinstance(d, dict):
            continue
        if fn in routed or d.get("profile"):
            continue
        # AN ESCAPE THAT LEAVES A RECORD. A declaration is also the accounting of what the
        # wrapped tool OFFERS, so a function this plugin does not draw is a fact worth keeping -
        # and it must not read as a panel someone could go looking for. `unplaced` carries the
        # reason, and a reason is required: an escape with no record is the gate switched off.
        why = str(d.get("unplaced") or "").strip()
        if why and len(why.split()) >= 4:
            continue
        if d.get("unplaced"):
            FAILURES.append(f"{f.name}: `{fn}` is marked unplaced with no usable reason")
            continue
        FAILURES.append(
            f"{f.name}: `{fn}` is declared, and no evidence route names it, and it is not "
            f"marked `profile` or `unplaced` - so if it draws anything, nothing can cite it")

if not CHECKED:
    print("FAIL")
    print("  - no plugin declaration was read; this proved nothing")
    raise SystemExit(1)
if FAILURES:
    print("FAIL")
    for x in FAILURES[:8]:
        print("  -", x)
    raise SystemExit(1)
print(f"ok - {CHECKED} declaration(s); every declared panel is routed by a need or marked profile")
