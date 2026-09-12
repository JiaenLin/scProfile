"""The unit's manifest records every panel the plan's companion drew, marked unmeasured.

Harness ADR-0016 step 4f. A panel drawn in R reached the run through nothing: the companion
wrote `captions.tsv`, the reporter globbed the file off disk, and the manifest - the tool's own
account of what a unit produced - never heard of it. Three readers of the manifest were wrong
because of it, on every unit of every run: the feedback diagnosed each of the plan's entries as
"declared and did not emit" (1,728 lines in one driver log), station 6b could only say "765
drawn and NOT measured" without saying which of them anything had recorded, and a page could
not tell a panel the companion drew from one nobody drew.

The record is read from what the companion wrote - the caption file is the companion's account,
and this copies it into the host's - and carries `measured: False`, because the drawing audit
runs where the host writes a panel and this panel was written elsewhere. The page renders such
a record through the native path that already carries its provenance and context; the manifest
half never renders it a second time.
"""
import ast
import inspect
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import manifest as M                                       # noqa: E402
from scprofile import plugin as P                                         # noqa: E402
from scprofile import report as R                                         # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


print("the record is read from the companion's caption file")
with tempfile.TemporaryDirectory() as td:
    out = Path(td)
    (out / "figures").mkdir()
    (out / "figures" / "native_ring.png").write_bytes(b"\x89PNG")
    (out / "figures" / "native_gone.png").write_bytes(b"\x89PNG")
    (out / "figures" / "captions.tsv").write_text(
        "file\tcaption\tdrawn_by\n"
        "native_ring.png\tA ring of 12 populations.\ttool\n"
        "native_lost.png\tA caption for a file that was never written.\tplugin\n",
        encoding="utf-8")
    ctx = P.Context(None, keys={}, out=str(out), cores=1, log=lambda *a, **k: None)
    ctx._figures.append({"id": "host_one", "path": str(out / "figures" / "host_one.png"),
                         "caption": "host", "audit": []})
    n = ctx._record_r_panels()
    recs = {f["id"]: f for f in ctx._figures}
    check(n == 1 and "native_ring" in recs, f"recorded {n}: {sorted(recs)}")
    r = recs.get("native_ring") or {}
    check(r.get("measured") is False, "a companion-drawn panel is not marked unmeasured")
    check(r.get("drawn_by") == "tool" and r.get("caption") == "A ring of 12 populations.",
          f"the record does not carry the companion's own words: {r}")
    check(str(r.get("path", "")).endswith("figures/native_ring.png"), f"path {r.get('path')!r}")
    check("native_lost" not in recs, "a caption with no file behind it became a record")
    check("native_gone" not in recs, "a file with no caption became a record (the reporter says "
                                     "NO LEGEND WAS WRITTEN for it; the manifest may not invent one)")
    check(recs["host_one"].get("measured") is None, "a host-emitted record was touched")
    n2 = ctx._record_r_panels()
    check(n2 == 0 and sum(1 for f in ctx._figures if f["id"] == "native_ring") == 1,
          "recording twice recorded the panel twice")

print("the serialiser carries what the record says")
src = inspect.getsource(P.FigureContextReader._record_r_panels)
written = set()
for node in ast.walk(ast.parse(src.lstrip())):
    if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "append" and node.args:
        if isinstance(node.args[0], ast.Dict):
            written |= {k.value for k in node.args[0].keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)}
probe = {k: "x" for k in written}
probe.update({"path": "figures/F.png", "measured": False})
carried = set(M._figure(probe, rel=lambda x: str(x)))
lost = sorted(written - carried - {"vector", "source"})
check(bool(written) and not lost, f"dropped between the plugin and the run: {lost or written}")
e = M._figure({"id": "F", "path": "figures/F.png", "caption": "c", "drawn_by": "plugin",
               "measured": False}, rel=lambda x: str(x))
check(e.get("measured") is False and e.get("drawn_by") == "plugin", str(e))
old = M._figure({"id": "F", "path": "figures/F.png"}, rel=lambda x: str(x))
check("measured" not in old and "drawn_by" not in old,
      "a record that said nothing about measurement now says something")

print("the page renders a companion-drawn record through the native path only")
figs = [{"id": "host_one", "path": "kernels/k/U/figures/host_one.png", "unit": "U"},
        {"id": "native_ring", "path": "kernels/k/U/figures/native_ring.png", "unit": "U",
         "measured": False, "drawn_by": "tool"}]
kept = [f["id"] for f in R.manifest_figures_to_render(figs)]
check(kept == ["host_one"], f"the manifest half would render {kept}")

if FAILURES:
    print("FAIL")
    for x in FAILURES:
        print("  -", x)
    raise SystemExit(1)
print("ok: the manifest records every panel the companion drew, marked unmeasured, carried by "
      "the serialiser, and rendered once")
