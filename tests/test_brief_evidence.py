"""The writing brief must see what the plugin DECLARES, not only what it produced.

WHAT THIS COST: the brief printed "NOT AVAILABLE - this dataset cannot answer this part" against
every evidence need of every comparison, for a plugin that supplies most of them. The run's
report.json recorded outputs and not the declaration, so `provides_evidence` was invisible the
moment the run ended. A section written from that brief would have reported the whole design as
unanswerable.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import evidence as E, kernels as K                         # noqa: E402
from scprofile.paper import _plugin_spec_of                               # noqa: E402

FAILURES = []
def _spec(k):
    """`discover` returns FileKernel objects; the declaration is on `.spec`."""
    return getattr(k, "spec", None) or (k if isinstance(k, dict) else {}) or {}


specs = {n: _spec(k) for n, k in (K.discover() or {}).items()}
wrappers = {n: s for n, s in specs.items()
            if ((s.get("report") or {}).get("provides_evidence"))}

if not wrappers:
    print("FAIL")
    print("  - no plugin declares provides_evidence; this check proved nothing")
    raise SystemExit(1)

for name, spec in sorted(wrappers.items()):
    declared = E.routes(spec) if hasattr(E, "routes") else \
        ((spec.get("report") or {}).get("provides_evidence") or {})
    # A RUN PAYLOAD WITH NO DECLARATION must still resolve, through the fallback.
    pay = {"kernels": {name: {"kernel": name, "figures": [], "tables": []}}}
    got = _plugin_spec_of(pay, name)
    seen = (got.get("report") or {}).get("provides_evidence") or {}
    if not seen:
        FAILURES.append(f"{name}: a payload without a declaration resolved to no evidence "
                        f"routes; the brief would say NOT AVAILABLE for every need")
    elif set(seen) != set(declared):
        FAILURES.append(f"{name}: resolved {len(seen)} route(s), the plugin declares "
                        f"{len(declared)}")
    # AND a payload that CARRIES one must use it rather than the source on disk.
    pay2 = {"kernels": {name: {"kernel": name,
                               "spec": {"report": {"provides_evidence": {"x": ["y"]}}}}}}
    got2 = _plugin_spec_of(pay2, name)
    if ((got2.get("report") or {}).get("provides_evidence") or {}) != {"x": ["y"]}:
        FAILURES.append(f"{name}: a recorded declaration was ignored in favour of the source")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print(f"ok: {len(wrappers)} plugin(s) declare evidence routes, and the brief resolves them "
      f"both from a recorded declaration and from discovery")
