"""What a run DELIVERED, as counts, so a later run cannot quietly deliver less.

THE TEST SUITE IS NOT A REGRESSION GUARD FOR THIS. Every suite can pass while a run produces
half the figures it produced yesterday: the suites check that the code is well-formed, and
capacity is a property of the OUTPUT. Both of the worst defects in this stage were of that
shape - four plot functions failing on every unit with no file, no log line and no non-zero
exit, and a rebuild that dropped 266 comparison figures and printed the same success line.
Neither would have failed a test, and neither did.

So a run records what it delivered, and any later run can be held against it. A DECREASE is
named. An increase is not a problem and is reported so the baseline can move deliberately.

Everything here is counted from the run directory itself. Nothing is remembered, declared or
inferred: if a figure is not on disk it is not counted, which is the only definition that cannot
drift from what a reader will actually find.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

#: The file each run carries. Beside the run card, because it is the same kind of fact.
NAME = "CAPACITY.json"

#: Counts where MORE is better, so a fall is a regression. Everything measured here is of that
#: kind; a count where less is better (failures) is stored negated so one rule covers both.
LOWER_IS_WORSE = ("units", "figures", "figures_native", "figures_compare", "tables",
                  "contrasts", "documents", "panel_plates", "claims", "plots_written",
                  "cache_hits")
#: Counts where MORE is worse.
HIGHER_IS_WORSE = ("plots_failed", "panel_gaps", "failed_units")


def measure(run_dir):
    """{name: count} for one run directory. Counted from disk, never from a manifest."""
    r = Path(run_dir)
    out = {}
    ker = r / "kernels"
    units, plugins = set(), set()
    if ker.is_dir():
        for p in ker.iterdir():
            if not p.is_dir():
                continue
            plugins.add(p.name)
            for u in p.iterdir():
                if u.is_dir() and (u / "out.json").is_file():
                    units.add(f"{p.name}/{u.name}")
    out["units"] = len(units)
    out["plugins"] = len(plugins)
    pngs = list(r.rglob("*.png"))
    out["figures"] = len(pngs)
    out["figures_native"] = sum(1 for f in pngs if f.name.startswith("native_"))
    out["figures_compare"] = sum(1 for f in pngs if f.name.startswith("nativecmp_"))
    out["tables"] = len(list(r.rglob("*.csv")))
    out["contrasts"] = sum(1 for p in ker.rglob("compare/*") if p.is_dir()) if ker.is_dir() else 0
    rep = r / "report"
    out["documents"] = len(list(rep.glob("*.html"))) if rep.is_dir() else 0

    # what the plugin's own script said it drew, which is the only place a SILENT failure shows
    w = f = 0
    for log in r.rglob("*_R.log"):
        for m in re.finditer(r"NATIVE PLOT TALLY:\s*(\d+) written,\s*(\d+) failed",
                             log.read_text(encoding="utf-8", errors="replace")):
            w += int(m.group(1))
            f += int(m.group(2))
    out["plots_written"], out["plots_failed"] = w, f
    out["cache_hits"] = sum(
        1 for log in r.rglob("*_R.log")
        if "inference skipped" in log.read_text(encoding="utf-8", errors="replace"))

    for page in (rep.glob("*_panel.html") if rep.is_dir() else []):
        t = page.read_text(encoding="utf-8", errors="replace")
        out["panel_plates"] = out.get("panel_plates", 0) + t.count("<img")
        out["panel_gaps"] = out.get("panel_gaps", 0) + t.count("no plate")
    out.setdefault("panel_plates", 0)
    out.setdefault("panel_gaps", 0)
    out["claims"] = sum(
        sum(1 for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()
            if '"kind": "claim"' in ln)
        for p in r.rglob("PAPER_CLAIMS*.jsonl"))
    try:
        card = json.loads((r / "RUN_CARD.json").read_text(encoding="utf-8"))
        out["failed_units"] = sum(1 for i in (card.get("instances") or [])
                                  if i.get("verdict") not in ("ok", None))
    except Exception:                                                     # noqa: BLE001
        out["failed_units"] = 0
    return out


def write(run_dir):
    """Record this run's capacity beside it. Returns the path."""
    r = Path(run_dir)
    p = r / NAME
    p.write_text(json.dumps({"run": r.name, "counts": measure(r)}, indent=1), encoding="utf-8")
    return p


def read(run_dir):
    """The recorded capacity of a run, measuring it if it was never recorded."""
    p = Path(run_dir) / NAME
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("counts") or {}
        except Exception:                                                 # noqa: BLE001
            pass
    return measure(run_dir)


#: The marker a run writes only when its job reached the end cleanly.
SEAL = "SEALED.txt"


def baseline(run):
    """The newest EARLIER SIBLING that finished, or None. What a regression is measured against.

    A PARTIAL RUN IS NOT A BASELINE. `read()` measures a directory when it holds no CAPACITY.json,
    which is right for a finished run written before that file existed and wrong for one that was
    killed: its counts are whatever it had managed to write. Measured live - a run cancelled
    mid-render became the comparison for the next run and produced a regression in a count it had
    never reached, which the agent was then asked to account for. An accounting of an artefact is
    worse than none, because somebody writes it down.

    Sealed only, earlier only, newest first. Run keys sort chronologically, which is what makes
    "earlier" answerable without reading a clock.
    """
    from . import review as RV
    here = Path(run)
    try:
        sibs = [d for d in RV.sibling_runs(here)
                if d.name < here.name and (d / SEAL).is_file()]
    except OSError:
        return None
    return max(sibs, key=lambda d: d.name) if sibs else None


def compare(now, before):
    """[(name, before, now, verdict)] - every count that moved, worst first.

    `verdict` is "REGRESSION", "gain" or "same". A regression is a fall in something where more
    is better, or a rise in failures. Nothing here decides what to do about it; naming it is the
    whole job, because the failure this guards against is one nobody noticed.
    """
    rows = []
    for k in sorted(set(now) | set(before)):
        a, b = before.get(k), now.get(k)
        if a is None or b is None or a == b:
            if a == b and a is not None:
                rows.append((k, a, b, "same"))
            continue
        if k in HIGHER_IS_WORSE:
            worse = b > a
        elif k in LOWER_IS_WORSE:
            worse = b < a
        else:
            worse = False
        rows.append((k, a, b, "REGRESSION" if worse else "gain"))
    rows.sort(key=lambda r: (r[3] != "REGRESSION", r[3] != "gain", r[0]))
    return rows


def regressions(now, before):
    """Just the regressions. Empty means this run delivered at least what the other did."""
    return [r for r in compare(now, before) if r[3] == "REGRESSION"]
