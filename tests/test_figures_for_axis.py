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
import re as _re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import subject                                                            # noqa: E402

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
ck = subject.source("cellchat", "that its figures declare the axis they are drawn for")
check("ctx.draw_figures" in ck, "the plugin never asks whether figures are wanted")
check("draw_figs <- " in ck, "the embedded R never parses the flag")
# MATCHED ON THE PROPERTY, NOT THE SPELLING - for the third time in this file's history. The
# literal was checked twice before and broke twice when the guard gained a capability; what
# matters is that BOTH plot wrappers consult the flag and that both allow the profile exception.
# SCOPED TO THE GUARD ITSELF, not to a return statement. Counting `return(invisible(NULL))`
# across the whole file caught every other helper that returns early - a check that breaks when
# an unrelated helper is added is measuring the wrong thing, for the fourth time in this file.
# MATCHED ON THE PROPERTY IN THE SCRIPT THAT RUNS - for the fourth time in this file's history,
# and this time because the wrapper MOVED. It lives in a generated companion prepended to every
# embedded script, so the per-unit script no longer spells the guard inside `npng` at all: it
# declares WHAT IS VISIBLE, once, and the generated wrapper asks before it opens a device. Both
# halves are still required and neither is a literal any more.
_run = dict(subject.r_as_run("cellchat", "that its figures declare the axis they are drawn for"))
_per_unit = _run.get("_R_RUN", "")
_vis = _re.search(r"visible\s*=\s*function\s*\([^)]*\)\s*(.+)", _per_unit)
check(_vis is not None,
      "the per-unit script declares no visibility rule, so the drawing flag reaches no panel")
if _vis:
    _rule = _vis.group(1)
    check("draw_figs" in _rule,
          "the per-unit visibility rule does not consult the drawing flag at all")
    check("profile_plots" in _rule,
          "the visibility rule has no profile exception, so the profile page loses the units "
          "whose full figure set the run switched off - a page with holes in exactly what it "
          "describes")
# AND THE WRAPPER ASKS BEFORE IT DRAWS. A rule nothing consults is a comment, which is the
# defect one directory over that this whole mechanism exists to stop.
_asks = _re.search(r"\$visible\(", _per_unit)
check(_asks is not None,
      "no draw wrapper consults the declared visibility rule, so the flag governs nothing")
if _asks:
    _dev = _per_unit.index("grDevices::png(")
    check(_asks.start() < _dev,
          "the wrapper consults the visibility rule after it opens the device, so the work the "
          "flag exists to skip has already been done")
run_block = _per_unit
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

# 9. THE TWO HALVES OF THE PROFILE DECLARATION MUST AGREE. The plugin marks FUNCTIONS in its
#    declaration, for the host to build the page from, and names PLOTS for its own R guard. A
#    name in one that no longer resolves to the other produces a page with holes in it and no
#    error anywhere - so the link is checked, through the same inversion the captions use.
sys.path.insert(0, str(ROOT))
from scprofile import native as _NAT                                      # noqa: E402
from scprofile.kernels import discover                                    # noqa: E402

for _n, _k in sorted(discover().items()):
    _sp = getattr(_k, "spec", None) or {}
    _decl = _sp.get("native_plots") or {}
    _marked = {fn for fn, rec in _decl.items() if (rec or {}).get("profile")}
    # READ FROM THE SOURCE, not by importing: a plugin runs in its own interpreter and may not
    # import in the host's - which is the whole reason the declaration is data rather than code.
    _plots = ()
    _src = Path(getattr(_k, "path", "") or "")
    if _src.is_file():
        _m = re.search(r"_PROFILE_PLOTS\s*=\s*\(([^)]*)\)", _src.read_text(encoding="utf-8"))
        if _m:
            _plots = tuple(x.strip().strip('"\'') for x in _m.group(1).split(",") if x.strip())
    if not (_marked or _plots):
        continue
    check(bool(_marked) and bool(_plots),
          f"{_n} declares one half of the profile set and not the other "
          f"(functions: {sorted(_marked)}, plots: {list(_plots)})")
    for _pl in _plots:
        _fn = _NAT.function_for(_decl, f"native_{_pl}.png")
        check(_fn in _marked,
              f"{_n}: the profile plot {_pl!r} resolves to {_fn!r}, which is not marked "
              f"`profile` in native_plots - the guard and the page disagree about what the "
              f"profile is")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - default draws everything, the setting selects an axis, and it gates only drawing")
