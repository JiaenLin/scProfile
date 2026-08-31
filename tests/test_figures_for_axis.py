"""Which unit axes get per-unit figures is a RUN setting, and it never changes what is computed.

WHY. A run that draws every panel for every unit spends most of itself drawing. Measured on a
cohort of eighteen units, ten of them single samples: the per-sample panels were 340 of the
run's figures and about half its wall clock, and they answer a different question from the group
panels - they are the consistency check, not the result.

THE DANGEROUS WAY TO FIX THAT is to delete the code that draws them, which takes the capability
away from every other project and cannot be undone per run. The safe way is a setting whose
DEFAULT IS EVERY AXIS, so a run that says nothing behaves exactly as before.

THE PROPERTY THAT MATTERS MOST is the last one checked here: the setting must gate DRAWING and
nothing else. If it ever gates the inference or the tables, a per-unit panel built on those
numbers loses its data and the run reports a smaller result rather than a faster one - and that
is a silent change of finding, not a change of speed.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile.plugin import Context                                      # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


def ctx(axis, want=None):
    return Context(None, keys={}, out="/tmp", unit="u", unit_axis=axis, figures_for=want)


# 1. the default is unchanged behaviour
check(ctx("sample").draw_figures, "with no setting a sample unit is not drawn - the default "
                                  "must be every axis, or this becomes a silent deletion")
check(ctx("group").draw_figures, "with no setting a group unit is not drawn")
check(ctx("").draw_figures, "a unit whose axis the resolver did not name is not drawn")

# 2. the setting selects
check(not ctx("sample", ["group"]).draw_figures, "figures_for=group still draws sample units")
check(ctx("group", ["group"]).draw_figures, "figures_for=group does not draw group units")
check(ctx("sample", ["group", "sample"]).draw_figures, "naming both axes drops one")

# 3. NOTHING HERE KNOWS WHAT AN AXIS IS CALLED. The resolver names them; this compares strings.
check(ctx("banana", ["banana"]).draw_figures,
      "the axis vocabulary is hard-coded somewhere instead of compared against what the "
      "resolver actually named")

# 4. it travels to the kernel's own interpreter
man = (ROOT / "scprofile" / "manifest.py").read_text()
ent = (ROOT / "scprofile" / "_entry.py").read_text()
cli = (ROOT / "scprofile" / "cli.py").read_text()
check('"figures_for"' in man and '"unit_axis"' in man,
      "in.json does not carry the setting, so a kernel in another interpreter cannot see it")
check("figures_for=inp.get" in ent and "unit_axis=inp.get" in ent,
      "the kernel entry point does not read them back out of in.json")
check("--figures-for" in cli, "there is no way to ask for this on the command line")

# 5. THE PLUGIN GATES DRAWING AND NOTHING ELSE. Checked on the embedded R: the guard must sit
#    inside the two plot wrappers, and must NOT appear around anything that writes a table or
#    runs the inference.
ck = (ROOT / "kernels" / "cellchat.py").read_text()
check("ctx.draw_figures" in ck, "the plugin never asks whether figures are wanted")
check("draw_figs <- " in ck, "the embedded R never parses the flag")
check(ck.count("if (!draw_figs) return(invisible(NULL))") == 2,
      f"expected the guard in exactly the two plot wrappers, found "
      f"{ck.count('if (!draw_figs) return(invisible(NULL))')}")
run_block = ck[ck.index("_R_RUN"):]
run_block = run_block[:run_block.index("_R_COMPARE")] if "_R_COMPARE" in run_block else run_block
for line in run_block.splitlines():
    if "draw_figs" in line and "write.csv" in line:
        FAILURES.append(f"the drawing flag gates a table write, which changes the RESULT and "
                        f"not the run time: {line.strip()[:90]}")
# the inference call itself must not be behind it
for m in re.finditer(r"if \(!?draw_figs\)([^\n]*)", run_block):
    if any(w in m.group(1) for w in ("computeCommunProb", "netAnalysis", "write")):
        FAILURES.append(f"the drawing flag gates computation: {m.group(0)[:90]}")

# 6. IT MUST REACH THE PLUGIN'S OWN PANELS, NOT ONLY THE WRAPPED TOOL'S. The first version
#    gated the R plots and nothing else, so ten Python-drawn panels per sample unit were still
#    written, the per-sample page was still built, and the run reported a saving it had not made.
#    Every shipped plugin emits through `emit_figure`, so that is where the setting belongs.
pl = (ROOT / "scprofile" / "plugin.py").read_text()
blk = pl[pl.index("def emit_figure("):]
blk = blk[:blk.index("\n    def ", 1)]
# CHECKED AS BEHAVIOUR, NOT AS SPELLING. The first version of this matched the literal text of
# the guard and broke the moment the guard learned about profile figures - a check that fails
# when its subject gains a capability is testing the source, not the property.
if "self.draws(" not in blk:
    FAILURES.append("emit_figure does not consult the per-figure decision, so a plugin's own "
                    "panels are drawn whatever the run asked for - the half-fix that leaves the "
                    "per-sample page standing")
elif blk.index("self.draws(") > blk.index('"figures" / f"{name}.png"'):
    FAILURES.append("the guard sits after the file path is built, so the check happens too late "
                    "to skip the work")

# 7. A PROFILE FIGURE IS DRAWN ON EVERY AXIS. The supplementary page describing what is active in
#    each unit is made of a few declared panels, and switching the full set off for an axis must
#    not switch those off too - a page with holes in it is worse than no page.
c = Context(None, keys={}, out="/tmp", unit="u", unit_axis="sample", figures_for=["group"],
            profile_figures=["P_keep"])
check(not c.draw_figures, "the fixture is wrong: this unit's full set should be off")
check(c.draws("P_keep"), "a declared profile figure is dropped on an excluded axis, so the "
                         "profile page would have holes in it")
check(not c.draws("X_other"), "a figure that is NOT in the profile set is drawn anyway, so the "
                              "setting saves nothing")
c2 = Context(None, keys={}, out="/tmp", unit="u", unit_axis="group", figures_for=["group"],
             profile_figures=["P_keep"])
check(c2.draws("X_other"), "an included axis stopped drawing its ordinary figures")

# 8. THE PROFILE PAGE IS DERIVED FROM THE DECLARATION, not from a list of figure names. A page
#    built from names the host knows is a page that only works for the plugin it was written for.
rep = (ROOT / "scprofile" / "report.py").read_text()
check('f.get("profile")' in rep,
      "the profile page is not built from the plugins' own `profile` declarations")
for bad in ("F8_pathway_rank", "F4_network", "F6_signaling_roles"):
    if bad in rep:
        FAILURES.append(f"report.py names the figure {bad!r}, which belongs to one plugin - the "
                        f"profile page must be built from what plugins DECLARE")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - default draws everything, the setting selects an axis, and it gates only drawing")
