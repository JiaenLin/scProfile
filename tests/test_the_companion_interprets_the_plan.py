#!/usr/bin/env python3
"""The generated companion carries the plan and draws from it (harness ADR-0016, step 4).

THE PLAN CARRIES THE CALL, AND THE COMPANION IS ITS INTERPRETER. `scaffold.render_plan(spec)`
writes every R-drawn entry of `report.figures` into the companion as data - the call, the file
expression, the items, the guard, the device and its size, the legend template - and two
functions beside it: `.draw(id, item, env)` draws one entry where a hand-written site stood,
evaluating the call, the file name and the legend's `{...}` placeholders in the CALLER's frame,
so a site inside a method loop sees the loop's own locals; `.draw_all(axis, env)` draws every
entry of an axis, binding `.item` over an entry's items. Nothing about the method is in the
companion, and nothing about any figure is left in the method.

Deterministic - the same declaration renders the same bytes - because the shipped companion is
checked byte for byte against what generates it. Run with R where R is installed.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import scaffold as SC                                      # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


SPEC = {"requires": {"r": ["base"]}, "report": {"figures": [
    {"id": "native_one", "drawn_by": "tool", "fn": "plot", "axis": "unit",
     "position": "appendix", "args": "seq_len(n)", "legend": "Counts for {n} populations."},
    # a guarded site: `when` is evaluated in the caller's frame and FALSE draws nothing
    {"id": "native_never", "drawn_by": "tool", "fn": "plot", "axis": "unit",
     "position": "appendix", "when": "n > 100", "args": "1", "legend": "Never drawn."},
    # one panel per item; NA and "" are dropped; the file stem is the entry's own expression
    {"id": "nativecmp_chord", "drawn_by": "tool", "fn": "plot", "axis": "contrast",
     "position": "contrast", "items": "shared", "at_most": 6,
     "file": 'paste0("chord__", .item)', "args": "1, main = .item",
     "legend": 'The {.item} pathway, "quoted".'},
    # the plugin's own R: a brace block on a side-effect device, sized by an expression
    {"id": "nativecmp_own", "drawn_by": "plugin", "axis": "contrast", "position": "conclusion",
     "at_most": 1, "device": "ndev", "w": "n * 100", "h": 300,
     "expr": "{\n x <- 1:3\n plot(x)\n }", "legend": "Own, {n} points."},
    # the host's emit path draws this one: not a site
    {"id": "F1_py", "drawn_by": "plugin", "axis": "unit", "position": "appendix",
     "shows": "result", "question": "q", "source": "s.csv"},
    # the tool writes this as a side effect of a call the method makes: not a site either
    {"id": "estimation", "drawn_by": "tool", "fn": "netClustering", "axis": "unit",
     "position": "appendix", "at_most": 2, "generated": False, "legend": "Not a panel."},
]}}

text = SC.render_plan(SPEC)
check(text == SC.render_plan(SPEC), "the rendered plan is not deterministic")
for fid in ("native_one", "native_never", "nativecmp_chord", "nativecmp_own"):
    check(f'.plan[["{fid}"]] <- list(' in text, f"{fid} is not in the rendered plan")
check('"F1_py"' not in text, "a panel the host's emit path writes was rendered as an R site")
check('"estimation"' not in text, "a file the tool writes as a side effect got a site")
check(".draw <- function(id, item = NULL, env = parent.frame())" in text,
      "the companion defines no `.draw`")
check(".draw_all <- function(axis, env = parent.frame())" in text,
      "the companion defines no `.draw_all`")
check('The {.item} pathway, \\"quoted\\".' in text,
      "a legend's double quotes are not escaped in the R string literal")
check("expr = quote({\n x <- 1:3\n plot(x)\n })" in text,
      "a brace block lost its lines on the way into the companion")
check("w = quote(n * 100)" in text and "h = quote(300)" in text,
      "a device size is not carried as an expression the draw evaluates")

companion = SC.R_DRAW.replace("__NAME__", "t") + text
rscript = shutil.which("Rscript")
if rscript:
    d = Path(tempfile.mkdtemp(prefix="plan-r-"))
    try:
        fig = d / "figures"
        fig.mkdir()
        body = f'''
figdir <- "{fig.as_posix()}"
n <- 3
shared <- c("A", NA, "", "B")
.figures(prefix = "native_", what = "test")
.draw("native_one")
.draw("native_never")
.figures(prefix = "nativecmp_", what = "test")
.draw_all("contrast")
.write_captions()
'''
        (d / "t.R").write_text(companion + body, encoding="utf-8")
        p = subprocess.run([rscript, str(d / "t.R")], capture_output=True, text=True,
                           timeout=300)
        check(p.returncode == 0, f"R exited {p.returncode}: {(p.stderr or '')[-600:]}")
        names = sorted(f.name for f in fig.glob("*.png"))
        check(names == ["native_one.png", "nativecmp_chord__A.png", "nativecmp_chord__B.png",
                        "nativecmp_own.png"],
              f"the plan drew {names}: expected one per entry, per item, none for the guarded "
              f"one, none for NA or empty items")
        caps = (fig / "captions.tsv").read_text(encoding="utf-8") if (fig / "captions.tsv").is_file() else ""
        check("Counts for 3 populations." in caps,
              f"a legend placeholder was not filled from the caller's frame: {caps!r}")
        check('The A pathway, "quoted".' in caps and 'The B pathway, "quoted".' in caps,
              f"`.item` did not reach the legend of a per-item entry: {caps!r}")
        check("Own, 3 points." in caps, f"the plugin's own site lost its legend: {caps!r}")
        check("\tplugin" in caps and "\ttool" in caps,
              f"the provenance did not travel from the entry to the caption: {caps!r}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
else:
    print("  (no Rscript here: the companion was rendered and not run)")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: the companion carries the plan and draws from it" + (" - run under R" if rscript else ""))
