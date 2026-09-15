"""A plan the layout trimmed still runs: the companion skips what is gone, the unit's axis reaches
the drawing, the host gates a plugin-drawn panel that is off the plan, and the accounting takes the
layout's reason (harness ADR-0024).

Run: python tests/test_a_trimmed_plan_still_runs.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


print("the accounting takes the layout's reason")
from scprofile import native as N                                              # noqa: E402
ck("over_budget with an axis and a budget is a valid ruling",
   N._check_skip({"skip": "over_budget", "axis": "contrast", "budget": 10}) == "",
   N._check_skip({"skip": "over_budget", "axis": "contrast", "budget": 10}))
ck("over_budget without the budget is not",
   "budget" in N._check_skip({"skip": "over_budget", "axis": "contrast"}))

print("\nthe unit's axis reaches the drawing through the figure context")
from scprofile.plugin import Context                                           # noqa: E402
with tempfile.TemporaryDirectory() as td:
    ctx = Context(None, keys={}, out=Path(td), cores=1, unit="U1", unit_axis="group",
                  log=lambda *a, **k: None)
    fc = ctx.write_figure_context()
    text = Path(fc).read_text(encoding="utf-8") if fc else ""
    ck("the context file carries the unit's axis", "axis\tgroup" in text, repr(text))

print("\nthe host gates a plugin-drawn panel the plan no longer carries")
import matplotlib                                                                # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                                  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    lines = []
    ctx = Context(None, keys={}, out=Path(td), cores=1, unit="U1", unit_axis="sample",
                  figure_position={"F2_presence": "appendix"}, plan_ids=("F2_presence",),
                  log=lines.append)
    fig = plt.figure()
    ck("a panel off the plan is not drawn", ctx.emit_figure("F5_dotplot", fig) is None
       and "F5_dotplot" not in ctx.drawn)
    ck("and the log says why", any("not on the plan" in x for x in lines), str(lines))
    fig = plt.figure()
    ck("a panel on the plan is drawn", ctx.emit_figure("F2_presence", fig) is not None
       and "F2_presence" in ctx.drawn)
    legacy = Context(None, keys={}, out=Path(td), cores=1, unit="U1", unit_axis="sample",
                     figure_position={"F": "appendix"}, log=lines.append)
    fig = plt.figure()
    ck("a plugin with no plan draws as before", legacy.emit_figure("F9_anything", fig) is not None)

print("\nthe host gates a plugin-drawn panel by the entry's axis, and a marginal pool draws nothing")
with tempfile.TemporaryDirectory() as td:
    lines = []
    # A SAMPLE-AXIS PANEL ON A GROUP UNIT: found on the first run under the layout (PBS 711438),
    # where the R companion held its entries to the unit's axis and the host's own emit path
    # did not, so every arm drew the per-sample census and the group axis read 6 against 5.
    ctx = Context(None, keys={}, out=Path(td), cores=1, unit="ARM", unit_axis="group",
                  figure_position={"F2_census": "appendix"}, plan_ids=("F2_census", "F3_roles"),
                  plan_axis={"F2_census": "sample", "F3_roles": "group"}, log=lines.append)
    fig = plt.figure()
    ck("a sample-axis panel is not drawn for a group unit",
       ctx.emit_figure("F2_census", fig) is None and "F2_census" not in ctx.drawn)
    ck("and the log names the axis", any("axis" in x for x in lines), str(lines))
    fig = plt.figure()
    ck("a group-axis panel is drawn for it", ctx.emit_figure("F3_roles", fig) is not None)
    lines = []
    marg = Context(None, keys={}, out=Path(td), cores=1, unit="aged", unit_axis="margin",
                   figure_position={"F3_roles": "contrast"}, plan_ids=("F3_roles",),
                   plan_axis={"F3_roles": "group"}, log=lines.append)
    fig = plt.figure()
    ck("a marginal pool draws nothing from the plan",
       not marg.draw_figures and marg.emit_figure("F3_roles", fig) is None)
    ck("and says why", any("margin" in x for x in lines), str(lines))

print("\nthe resolver names the marginal pools, and the run files them under their own axis")
from scprofile import units as U                                                # noqa: E402
_design = {"S1": {"dose": "low", "time": "early"}, "S2": {"dose": "low", "time": "late"},
           "S3": {"dose": "high", "time": "early"}, "S4": {"dose": "high", "time": "late"}}
_plan, _why = U.resolve(_design)
_grp = next((a for a in _plan if a["kind"] == "group"), {})
ck("the group axis lists its marginal pools apart from the arms",
   sorted(_grp.get("margins") or []) == ["early", "high", "late", "low"], str(_grp.get("margins")))
ck("and the arms are not among them", "low_early" in _grp.get("units", {})
   and "low_early" not in (_grp.get("margins") or []))
ck("the axis of a unit is `margin` for a pool and `group` for an arm",
   U.axis_of(_plan) .get("low") == "margin" and U.axis_of(_plan).get("low_early") == "group"
   and U.axis_of(_plan).get("S1") == "sample", str(U.axis_of(_plan)))

print("\nthe companion skips an entry the layout dropped, and one not for this unit's axis")
from scprofile import scaffold as SC                                             # noqa: E402
SPEC = {"name": "demo", "requires": {"r": ["4.3"]},
        "report": {"figures": [
            {"id": "native_a", "kind": "circle", "drawn_by": "tool", "fn": "plotA", "args": "obj",
             "axis": "sample", "position": "contrast", "legend": "a"},
            {"id": "native_b", "kind": "matrix", "drawn_by": "tool", "fn": "plotB", "args": "obj",
             "axis": "group", "position": "contrast", "legend": "b"},
            {"id": "nativecmp_c", "kind": "diff_matrix", "drawn_by": "tool", "fn": "plotC",
             "args": "m", "axis": "contrast", "position": "contrast", "legend": "c"}]}}
comp = SC.R_DRAW.replace("__NAME__", "demo") + SC.render_plan(SPEC)
ck("the companion no longer stops on an id that is not on the plan",
   "not on the plan" in comp and 'stop("no entry in the plan is called "' not in comp)
ck("and it reads the unit's axis from the context", ".fctx$axis" in comp)
rscript = shutil.which("Rscript")
if rscript:
    with tempfile.TemporaryDirectory() as td:
        script = (comp + '\n.fctx$axis <- "group"\n'
                  '.draw("native_gone")\n'
                  '.draw("native_a")\n'
                  '.draw("nativecmp_c")\n'
                  '.fctx$axis <- "contrast"\n'
                  '.draw("native_b")\n'
                  '.fctx$axis <- "margin"\n'
                  '.draw("native_b")\n'
                  '.draw_all("unit")\n'
                  'cat("reached the end\\n")\n')
        f = Path(td) / "probe.R"
        f.write_text(script, encoding="utf-8")
        p = subprocess.run([rscript, str(f)], capture_output=True, text=True, timeout=300, cwd=td)
        out = (p.stdout or "") + (p.stderr or "")
        ck("R runs through both skips to the end", p.returncode == 0 and "reached the end" in out,
           out[-600:])
        ck("the dropped id is named as not on the plan", "not on the plan" in out, out[-300:])
        ck("the sample-only entry is skipped for a group unit", "not for this unit" in out, out[-300:])
        # AN AXIS THE SCRIPT DOES NOT DRAW BY (harness ADR-0026, K-o): a contrast entry called
        # from a unit's script, or a unit entry from a contrast's, is skipped and named - the
        # maker had counted a pair scatter moved to the group axis while the run drew it per
        # contrast exactly as before, its draw site being in the compare script.
        ck("a contrast entry drawn from a unit's script is skipped and named",
           "nativecmp_c" in out and "drawn per contrast" in out, out[-500:])
        ck("a unit entry drawn from a contrast's script is skipped and named",
           "native_b is drawn per group; this unit is a contrast" in out, out[-500:])
        ck("a marginal pool draws nothing, and says so", "marginal" in out, out[-300:])
        ck("and nothing was drawn", not list(Path(td).glob("*.png")))
else:
    print("  skip  Rscript is not on this machine; the companion's text was checked")

print("\n" + ("a trimmed plan still runs" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
