"""A run must record what it delivered, and a fall must be named a regression.

THE SUITES CANNOT CATCH THIS CLASS. Every one of them passes while a run produces half the
figures it produced yesterday: they check that the code is well-formed, and capacity is a
property of the OUTPUT. Both of the worst defects in this stage were exactly that shape - four
plot functions failing on every unit with no file, no log line and no non-zero exit, and a
rebuild that dropped 266 comparison figures and printed the same success line. Neither failed a
test, and neither was noticed at the time.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import capacity as C                                       # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


def _fake(root, *, units=2, figs=10, failed=0, plates=4, gaps=1):
    root.mkdir(parents=True, exist_ok=True)
    (root / "report").mkdir(exist_ok=True)
    for i in range(units):
        d = root / "kernels" / "kk" / f"u{i}"
        (d / "figures").mkdir(parents=True, exist_ok=True)
        (d / "out.json").write_text("{}")
        (d / "cellchat_R.log").write_text(
            f"NATIVE PLOT TALLY: {figs // units} written, {failed} failed\n"
            + ("reusing the saved CellChat object; inference skipped\n" if i == 0 else ""))
        for j in range(figs // units):
            (d / "figures" / f"native_x{j}.png").write_bytes(b"\x89PNG")
    (root / "report" / "kk_panel.html").write_text(
        "<img>" * plates + "no plate" * gaps)
    return root


with tempfile.TemporaryDirectory() as td:
    base = Path(td) / "runs"
    a = _fake(base / "20260101T000000Z__run", units=2, figs=10, failed=0)
    m = C.measure(a)
    check(m["units"] == 2, f"units miscounted: {m['units']}")
    check(m["figures"] == 10, f"figures miscounted: {m['figures']}")
    check(m["plots_written"] == 10, f"tally not read: {m['plots_written']}")
    check(m["cache_hits"] == 1, f"cache hits not read: {m['cache_hits']}")
    check(m["panel_plates"] == 4 and m["panel_gaps"] == 1,
          f"panel not read: {m['panel_plates']}/{m['panel_gaps']}")
    C.write(a)
    check((a / C.NAME).is_file(), "capacity was not recorded beside the run")

    # A RUN THAT DELIVERS LESS IS A REGRESSION, and one that fails plots is too.
    b = _fake(base / "20260102T000000Z__run", units=2, figs=4, failed=3)
    reg = {r[0] for r in C.regressions(C.measure(b), C.read(a))}
    check("figures" in reg, f"a fall in figures was not called a regression: {sorted(reg)}")
    check("plots_failed" in reg, f"a rise in failures was not called a regression: {sorted(reg)}")

    # A RUN THAT DELIVERS MORE IS NOT.
    c = _fake(base / "20260103T000000Z__run", units=3, figs=30, failed=0)
    check(not C.regressions(C.measure(c), C.read(a)),
          f"delivering more was called a regression: {C.regressions(C.measure(c), C.read(a))}")
    gains = {r[0] for r in C.compare(C.measure(c), C.read(a)) if r[3] == "gain"}
    check("figures" in gains, "an increase was not reported as a gain")

# and the run path must record it without being asked
cli = (ROOT / "scprofile" / "cli.py").read_text()
check(cli.count("_record_capacity(") >= 3,
      "capacity is not recorded by both `run` and `report`")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ok: a run records what it delivered; a fall in output or a rise in plot failures is "
      "named a regression, an increase is not")
