#!/usr/bin/env python3
"""The host launches a plugin's embedded R: companion first, then the body (ADR-0016, step 4b).

THE GLUE WAS THE PLUGIN'S AND IT WAS GENERAL. Writing the figure context as a TSV for R, reading
the generated companion beside the plugin, prepending it to the script, choosing the interpreter,
running it, keeping the whole log and surfacing every FAILED line: six functions in one plugin,
each of them true of every plugin that draws through R and none of them about CellChat. They
are `ctx.rscript` and `ctx.write_figure_context` now, on both contexts, and a plugin's launch is
one call with the arguments its script reads.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile.plugin import CompareContext                              # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


d = Path(tempfile.mkdtemp(prefix="rscript-"))
lines = []
try:
    ctx = CompareContext(pair="a__b", units={}, out=d, figure_ceiling={"native_x": 3},
                         figure_context={"stamp": "unit U, n = 5", "colours": {"A": "#112233"}},
                         r_companion='cat("companion loaded\\n")\n', log=lines.append)
    fc = ctx.write_figure_context()
    check(str(fc).endswith("figure_context.tsv"), f"no figure context written: {fc!r}")
    text = Path(fc).read_text(encoding="utf-8") if fc else ""
    check("ceiling:native_x\t3" in text and "colour:A\t#112233" in text
          and "stamp\tunit U, n = 5" in text,
          f"the figure context does not carry the stamp, the colours and the ceilings: {text!r}")
    rscript = shutil.which("Rscript")
    if rscript:
        p = ctx.rscript('args <- commandArgs(trailingOnly = TRUE)\n'
                        'cat("got", length(args), "argument(s)\\n")\n'
                        'cat("native plot x FAILED: on purpose\\n")\n'
                        'writeLines(args[1], file.path(args[2], "echo.txt"))\n',
                        [str(fc), str(d)], name="probe")
        check(p.returncode == 0, f"R exited {p.returncode}: {(p.stderr or '')[-400:]}")
        check((d / "probe.R").read_text(encoding="utf-8").startswith('cat("companion loaded'),
              "the script the host wrote does not begin with the companion")
        check((d / "echo.txt").is_file() and str(fc) in (d / "echo.txt").read_text(),
              "the arguments did not reach the script")
        log = (d / "probe.log").read_text(encoding="utf-8") if (d / "probe.log").is_file() else ""
        check("companion loaded" in log and "got 2 argument(s)" in log,
              f"the whole R output is not kept beside the outputs: {log!r}")
        check(any("FAILED: on purpose" in x for x in lines),
              f"a FAILED line in R's output was not surfaced through the log: {lines}")
        check(any("1 failure(s)" in x for x in lines), f"the failure count is not logged: {lines}")
    else:
        print("  (no Rscript here: the launch was not exercised)")
finally:
    shutil.rmtree(d, ignore_errors=True)

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: the host writes the figure context, prepends the companion, runs R and keeps the log")
