"""A directory at the top of a run that the run did not write is not the run's (harness
ADR-0026, the open items; found by scanning the cold agent's path on the run for review).

THE FIXTURE GATE'S SCRATCH SITS INSIDE THE RUN DIRECTORY - the job writes only there, by its own
rule - and three readers swept the whole directory: `review.figures` (station 7, the shards, the
scan set, `--adopt`) would have handed a cold looker two synthetic cohorts' plates beside the
real ones; `capacity.measure` would have read a hundred-odd figures and tables gained against
the reference; the run's own product record listed the scratch, and the next job emitted from
that reference expected it. A denylist of names would have caught these three and missed the
next (`incoming`, `replay`, whatever a later job adds). The run's own trees are declared ONCE
(`manifest.OWN_TREES`: kernels, report, tables, objects, and the files at the top), and every
reader that walks a run walks those.

Run: python tests/test_a_foreign_directory_is_not_the_runs.py
"""
import json
import os
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


def seed(d):
    """A run with its own trees, and every foreign directory a job has ever put beside them."""
    own = {
        "kernels/demo/U1/out.json": json.dumps({"kernel": "demo", "status": "ok", "figures": {}}),
        "kernels/demo/U1/figures/native_a.png": "p", "kernels/demo/U1/tables/t.csv": "a\n1\n",
        "kernels/demo/U1/demo_R.log": "NATIVE PLOT TALLY: 3 written, 0 failed\ninference skipped\n",
        "kernels/demo/compare/c1/out.json": json.dumps({"kernel": "demo", "status": "ok"}),
        "kernels/demo/compare/c1/figures/nativecmp_b.png": "p",
        "kernels/demo/PAPER_CLAIMS.demo.jsonl": '{"kind": "claim"}\n',
        "report/index.html": "<html>", "report/figures/x.png": "p", "report/panels.json": "{}",
        "tables/demo_t__U1.csv": "a\n1\n", "objects/o.h5ad": "h",
        "report.json": "{}", "RUN_CARD.json": "{}", "README.md": "#", "STATUS.json": "{}",
    }
    foreign = {
        "fixture/run_a/run/kernels/demo/U1/out.json": json.dumps({"kernel": "demo"}),
        "fixture/run_a/run/kernels/demo/U1/figures/native_z.png": "p",
        "fixture/run_a/run/kernels/demo/U1/tables/z.csv": "a\n",
        "fixture/run_a/run/kernels/demo/U1/demo_R.log": "NATIVE PLOT TALLY: 9 written, 9 failed\ninference skipped\n",
        "fixture/run_a/run/kernels/demo/PAPER_CLAIMS.demo.jsonl": '{"kind": "claim"}\n',
        "fixture/run_a/run/report/figures/y.png": "p", "fixture/fixture_a.h5ad": "h",
        "logs/pbs.log": "l", "logs/l.png": "p", "cache/mpl/c.png": "p", "cache/c.csv": "a\n",
        "incoming/kernels/demo/U1/figures/i.png": "p", "replay/kernels/demo/U1/figures/r.png": "p",
        "somewhere_new/deep/n.png": "p", "somewhere_new/n.csv": "a\n",
    }
    for rel, body in {**own, **foreign}.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return own, foreign


print("the run's own trees are declared once")
from scprofile import manifest as M                                             # noqa: E402

ck("kernels, report, tables, objects", tuple(M.OWN_TREES) == ("kernels", "report", "tables", "objects"),
   str(M.OWN_TREES))
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    own, foreign = seed(d)
    files = {str(p.relative_to(d)) for p in M.own_files(d)}
    ck("every file of the run's own is listed", set(own) <= files, str(set(own) - files))
    ck("no file of a foreign directory is", not (set(foreign) & files), str(set(foreign) & files))
    ck("a top-level file is the run's", "README.md" in files and "STATUS.json" in files)
    ck("is_own reads a relative path", M.is_own("kernels/demo/U1/out.json") and M.is_own("report.json")
       and not M.is_own("fixture/run_a/run/kernels/demo/U1/out.json") and not M.is_own("logs/pbs.log")
       and not M.is_own("somewhere_new/n.csv"))

    print("\nevery reader that walks a run walks those")
    from scprofile import review as RV, capacity as C, status as ST
    figs = RV.figures(d)
    ck("review.figures: the run's plates, none from a foreign directory",
       figs == ["kernels/demo/U1/figures/native_a.png", "kernels/demo/compare/c1/figures/nativecmp_b.png"]
       or sorted(figs) == sorted(["kernels/demo/U1/figures/native_a.png", "kernels/demo/compare/c1/figures/nativecmp_b.png"]),
       str(figs))
    m = C.measure(d)
    ck("capacity.measure: figures, tables, plots written, cache hits and claims counted on the run's own trees",
       m["figures"] == 3 and m["tables"] == 2 and m["plots_written"] == 3 and m["plots_failed"] == 0
       and m["cache_hits"] == 1 and m["claims"] == 1, str({k: m[k] for k in ("figures", "tables", "plots_written", "plots_failed", "cache_hits", "claims")}))
    prods = {p["path"] for p in ST.products_of(d)}
    ck("the run's own product record names no foreign file",
       not any(p.startswith(("fixture/", "logs/", "cache/", "incoming/", "replay/", "somewhere_new/")) for p in prods)
       and "kernels/demo/U1/out.json" in prods and "report/index.html" in prods, str(sorted(prods))[:400])
    src = (ROOT / "scprofile" / "cli.py").read_text(encoding="utf-8")
    _rd = src[src.index("def _write_readme("):]
    _rd = _rd[:_rd.index("\ndef ")] if "\ndef " in _rd else _rd
    ck("the README's enumeration walks the run's own files, imported where it runs",
       "from .manifest import own_files" in _rd and "files = own_files(out)" in _rd)
    ls = (ROOT / "tests" / "loop_stations.py").read_text(encoding="utf-8")
    ck("the loop's adopt station walks the run's own files", "own_files(" in ls)

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\na foreign directory is not the run's")
