"""A panel the plugin draws itself, on its plan, is routable to the need it answers.

The migration to the figure plan (harness ADR-0016) wrote the plugin's own R panels honestly, as
`drawn_by: plugin`, and `native.function_for` stopped claiming them for the tool functions they
had been filed under in `native_plots`. Every `native:` route then resolved past them: on the
first reproduction eleven cohort-level interaction panels were drawn, described, and placed in no
document - the panel page showed "no plate" for three needs the run had answered, and the paper
numbered eleven figures fewer (PBS 710973, R6).

A route may now name the entry itself: `plan:<id>`. The plate is the file that entry claims,
matched through `native.entry_for` - the id-based inversion `function_for` already applies - and
both documents look it up the way they look up a native plate: labelled by contrast, or filed
under no contrast and answering every one of them.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import compose as C                                        # noqa: E402
from scprofile import declare as D                                        # noqa: E402
from scprofile import native as N                                         # noqa: E402
from scprofile import paper as PA                                         # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


PLAN = [
    {"id": "nativecmp_diff", "drawn_by": "tool", "fn": "fnA", "axis": "contrast",
     "position": "contrast", "args": "m", "legend": "Diff.", "kind": "diff_matrix",
     "items": 'c("count", "weight")', "file": 'paste0("diff_", .item)'},
    # THE PLUGIN'S OWN FAMILY SHARING ITS HEAD WITH THE TOOL'S: `nativecmp_diff_` is where both
    # begin, and only the longest id tells them apart (cellchat's compareInteractions_per1k).
    {"id": "nativecmp_diff_per1k", "drawn_by": "plugin", "axis": "contrast",
     "position": "contrast", "expr": "{ draw(P) }", "legend": "Per thousand.", "kind": "bars",
     "file": 'paste0("diff_per1k_", .item)'},
    {"id": "nativecmp_interaction", "drawn_by": "plugin", "axis": "cohort",
     "position": "conclusion", "at_most": 3, "file": 'paste0("interaction_", ms, "__", safe)',
     "expr": "{ draw(M) }", "legend": "Interaction.", "kind": "interaction"},
    {"id": "nativecmp_interaction_flow", "drawn_by": "plugin", "axis": "cohort",
     "position": "conclusion", "at_most": 2, "file": 'paste0("interaction_flow__", safe)',
     "expr": "{ draw(F) }", "legend": "Flow.", "kind": "interaction"},
]
ROUTES = {"who_changed": ["native:fnA", "plan:nativecmp_interaction"],
          "what_carries_it": ["plan:nativecmp_interaction_flow"]}
SPEC = {"report": {"figures": PLAN, "provides_evidence": ROUTES}}

print("entry_for: which entry of the plan claims a file")
check(N.entry_for(SPEC, "kernels/kk/compare/f1/figures/nativecmp_diff.png") == "nativecmp_diff",
      "a single-file entry is its id exactly")
check(N.entry_for(SPEC, "x/nativecmp_interaction_count__a_by_b.png") == "nativecmp_interaction",
      "a per-item entry claims the files that begin with its id")
check(N.entry_for(SPEC, "x/nativecmp_interaction_flow__a_by_b.png")
      == "nativecmp_interaction_flow",
      "the LONGEST id wins, so a sibling family's files are not swallowed by a shorter id")
check(N.entry_for(SPEC, "x/nobody.png") == "", "a file no entry names belongs to no entry")
check(N.entry_for({}, "x/nativecmp_diff.png") == "", "no plan, no entry")

print("who_drew: the entry that claims the file says who drew it")
DECL = N.declared_from(SPEC)
check(N.who_drew(SPEC, DECL, "x/nativecmp_diff_count.png") == ("fnA", "nativecmp_diff"),
      "a file of the tool's family is credited to the tool's function")
check(N.who_drew(SPEC, DECL, "x/nativecmp_diff_per1k_count.png") == ("", "nativecmp_diff_per1k"),
      "a file of the plugin's own family under the same head is the plugin's, not the tool's "
      f"(function_for alone says {N.function_for(DECL, 'x/nativecmp_diff_per1k_count.png')!r})")
check(N.who_drew({"native_plots": {"fnZ": {"use": "figures/ncmp_z.png"}}}, {"fnZ": {"use":
      "figures/ncmp_z.png"}}, "x/ncmp_z.png") == ("fnZ", ""),
      "a plugin on the older form is still read from native_plots")

DESIGN = {"s1": {"f1": "lo", "f2": "x"}, "s2": {"f1": "lo", "f2": "y"},
          "s3": {"f1": "hi", "f2": "x"}, "s4": {"f1": "hi", "f2": "y"}}
DIFF = "kernels/kk/compare/f1/figures/nativecmp_diff_count.png"
IX = "kernels/kk/compare/_across_arms/figures/nativecmp_interaction_count__f1_by_f2.png"
FLOW = "kernels/kk/compare/_across_arms/figures/nativecmp_interaction_flow__f1_by_f2.png"

with tempfile.TemporaryDirectory() as td:
    out = Path(td)
    (out / "report").mkdir()
    for rel in (DIFF, IX, FLOW):
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(b"\x89PNG")
    (out / "report.json").write_text(json.dumps(
        {"design": DESIGN, "kernels": {"kk": {"kernel": "kk", "spec": SPEC}}}))
    # a finding per contrast, so the paper has a section to number figures from
    (out / "kernels" / "kk" / "tables").mkdir(parents=True)
    rows = ["contrast,element,from,to,total_from,total_to,raw_from,raw_to,raw_delta,"
            "scales_agree,from_source,to_source"]
    for lab, (a, b) in (("f1", ("lo", "hi")), ("f2", ("x", "y"))):
        rows.append(f"{lab},ALPHA,{a},{b},10,20,1,2,1,True,unit '{a}',unit '{b}'")
    (out / "kernels" / "kk" / "tables" / "kk_two_scale.csv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8")
    (out / "report" / "panels.json").write_text(json.dumps({"kk": {
        "cohort": [], "contrast": [], "arm": [],
        "native": [
            {"id": "a", "label": "f1", "path": DIFF, "caption": ["diff shown", "diff limits"]},
            {"id": "b", "label": "", "path": IX, "caption": ["ix shown", "ix limits"]},
            {"id": "c", "label": "", "path": FLOW, "caption": ["flow shown", "flow limits"]}]}}))

    print("the paper's index: a plan route finds its plate beside the native ones")
    by, routes, host = C._native_index(out, "kk", SPEC)
    check(C._figs_for(by, routes, "f1", ("who_changed",), host, scope="contrast") == [DIFF],
          "the contrast scope holds only the plate drawn for this contrast")
    check(C._figs_for(by, routes, "f1", ("who_changed",), host, scope="cohort") == [IX],
          "the cohort scope holds the plugin's own cohort plate, through its plan route")
    check(C._figs_for(by, routes, "", ("what_carries_it",), host, scope="cohort") == [FLOW],
          "the flow family's plate is the flow entry's, not the shorter id's")
    check(C._figs_for(by, routes, "f1", ("who_changed",), host) == [DIFF, IX],
          "a citation gets both, native first")
    idx = C.figure_index(out, "kk", SPEC, DESIGN)
    numbered = {str(p) for p in (idx or {})}
    check(all(p in numbered for p in (DIFF, IX, FLOW)),
          f"the paper numbers every routed plate; it numbered {sorted(numbered)}")

    print("the panel page: a plan route places its plate and leaves no gap")
    f = PA.panel(out, plugin="kk", run_key="RUNKEY")
    h = Path(f).read_text() if f else ""
    check(bool(f), "panel() produced nothing")
    check(IX.rsplit("/", 1)[-1] in h and FLOW.rsplit("/", 1)[-1] in h,
          "the plan routes did not place their plates")
    check("no plate" not in h, "a need the plan answered reads as a gap")
    check("nativecmp_interaction (drawn by the plugin" in h,
          "the plate does not say it is the plugin's own, on the plan")

print("the validator: a plan route must name an entry of the plan")
BASE = {"api": 1, "state_version": 1, "summary": "x", "cannot_show": ["y"]}
bad = [m for lvl, m in D.check({**BASE, "report": {"figures": PLAN, "provides_evidence": {
    "who_changed": ["plan:nowhere"]}}}) if lvl == "ERROR"]
check(any("plan:nowhere" in m and "report.figures" in m for m in bad),
      f"a route to an entry the plan does not carry is not refused: {bad}")
good = [m for lvl, m in D.check({**BASE, "report": {"figures": PLAN,
                                                     "provides_evidence": ROUTES}})
        if lvl == "ERROR" and "plan:" in m]
check(not good, f"a route to an entry on the plan is refused: {good}")

if FAILURES:
    print("FAIL")
    for x in FAILURES:
        print("  -", x)
    raise SystemExit(1)
print("ok: a panel the plugin draws itself is routed by `plan:<id>`, found by the entry that "
      "claims its file, placed by both documents, and refused when the plan has no such entry")
