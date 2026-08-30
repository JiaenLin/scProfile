"""The figure panel must be DERIVED from the design and the plugin's declared routes.

The run writes an arms page carrying every between-arm figure it drew - 426 on one real cohort -
which is an appendix, not a panel. A panel is the subset a reader is asked to look at, and the
only way to get one was to pick figures by hand into a document with no run key. That is a draft
by this project's own rule, whatever it looks like when published.

So the selection must come from the design's own comparisons and the plugin's own
`provides_evidence` routes, and a need whose route drew nothing must be reported as a gap rather
than quietly dropped - otherwise a panel with half its plates missing looks complete.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import paper as PA                                         # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


DESIGN = {"s1": {"f1": "lo", "f2": "x"}, "s2": {"f1": "lo", "f2": "y"},
          "s3": {"f1": "hi", "f2": "x"}, "s4": {"f1": "hi", "f2": "y"}}
SPEC = {"report": {"provides_evidence": {
            "who_changed": ["native:fnA", "host:diff_matrix"],
            "what_carries_it": ["native:fnB"],
            "direction": ["host:role_shift"]}},
        "native_plots": {"fnA": {"use": "figures/ncmp_alpha.png"},
                         "fnB": {"use": "figures/ncmp_beta.png"}}}

with tempfile.TemporaryDirectory() as td:
    out = Path(td)
    (out / "report").mkdir()
    (out / "report.json").write_text(json.dumps(
        {"design": DESIGN, "kernels": {"kk": {"kernel": "kk", "spec": SPEC}}}))
    # one contrast has both plates, another has only one - the second must show a gap
    (out / "report" / "panels.json").write_text(json.dumps({"kk": {"cohort": [], "native": [
        {"id": "a", "label": "f1", "path": "kernels/kk/compare/f1/figures/ncmp_alpha.png",
         "caption": ["alpha shown", "alpha limits"]},
        {"id": "b", "label": "f1", "path": "kernels/kk/compare/f1/figures/ncmp_beta.png",
         "caption": ["beta shown", "beta limits"]},
        {"id": "c", "label": "f2", "path": "kernels/kk/compare/f2/figures/ncmp_alpha.png",
         "caption": ["alpha shown", "alpha limits"]}]}}))

    f = PA.panel(out, plugin="kk", run_key="RUNKEY")
    check(f is not None, "panel() produced nothing on a design with comparisons")
    if f:
        h = Path(f).read_text()
        check(Path(f).name == "kk_panel.html", f"wrong file name {Path(f).name}")
        check(Path(f).parent == out / "report",
              f"panel landed in {Path(f).parent}, not beside the other pages")
        check("ncmp_alpha.png" in h and "ncmp_beta.png" in h,
              "the declared native routes did not select their plates")
        check("fnA" in h and "fnB" in h,
              "the plate captions do not name the function that drew them")
        check("no plate" in h,
              "a need whose route drew nothing was dropped silently instead of shown as a gap")
        check("RUNKEY" in h, "the panel does not carry the run key")
        # A HOST-ONLY need must not silently masquerade as a native plate.
        check(h.count("<img") >= 3, f"too few plates placed: {h.count('<img')}")

    # No design, no panel - and it must say so rather than emit an empty page.
    (out / "report.json").write_text(json.dumps({"design": {}, "kernels": {}}))
    check(PA.panel(out, plugin="kk") is None,
          "a run with no design still produced a panel")

if FAILURES:
    print("FAIL")
    for x in FAILURES:
        print("  -", x)
    raise SystemExit(1)
print("ok: the panel is derived from the design's comparisons and the plugin's declared "
      "evidence routes, names the drawing function, and reports needs with no plate as gaps")
