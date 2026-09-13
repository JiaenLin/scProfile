"""`cores` and `cost` are measured, not trusted (harness ADR-0020, step 5).

Every run printed them as CHECKED BY NOBODY: two required declaration keys the scheduler sized
waves on, present-checked and true by nobody's account, since the day the tool was written. Now
every instance measures its own process tree's CPU beside its memory, the run fits a cores model
and a cost band per plugin from those points, and `capacity --cores` / `capacity --cost` hold the
declaration against the fit and write it back with `--declare` - the shape `measure` has for
memory. Nothing is pasted by hand.

Run: python tests/test_cores_and_cost_are_measured.py
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import _entry as E                                               # noqa: E402
from scprofile import kernels as K                                              # noqa: E402
from scprofile import cli                                                       # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def fake_proc(td, procs):
    """A reconstructed /proc: {pid: (ppid, utime_ticks, stime_ticks)}."""
    proc = Path(td) / "proc"
    for pid, (ppid, ut, st) in procs.items():
        d = proc / str(pid)
        d.mkdir(parents=True)
        # pid (comm) state ppid ... utime is field 14, stime field 15
        fields = ["S", str(ppid)] + ["0"] * 9 + [str(ut), str(st)] + ["0"] * 10
        (d / "stat").write_text(f"{pid} (worker) " + " ".join(fields) + "\n")
    return proc


print("the CPU of a process tree is read from /proc, self and every descendant")
with tempfile.TemporaryDirectory() as td:
    proc = fake_proc(td, {100: (1, 1000, 200), 101: (100, 3000, 500), 102: (101, 600, 0),
                          200: (1, 99999, 99999)})
    s = E._tree_cpu_s(100, proc=str(proc), tick=100)
    ck("utime and stime of 100, 101 and 102 summed, at 100 ticks a second, and 200 left out",
       s is not None and abs(s - (1000 + 200 + 3000 + 500 + 600) / 100.0) < 1e-6, str(s))
    ck("no /proc: None", E._tree_cpu_s(100, proc=str(Path(td) / "nowhere")) is None)

print("\nthe run fits a cores model and a cost band from its instances")
pts = [{"n_cells": 10000, "wall_s": 60.0, "cpu_s": 210.0, "cores_peak": 3.9},
       {"n_cells": 20000, "wall_s": 100.0, "cpu_s": 380.0, "cores_peak": 4.2},
       {"n_cells": 5000, "wall_s": 30.0, "cpu_s": 40.0}]
m = K.fit_cores_model(pts)
ck("the peak is the largest sampled peak", m and abs(m["peak"] - 4.2) < 1e-9, str(m))
ck("the mean is the median of cpu over wall", m and abs(m["mean"] - 3.5) < 1e-9, str(m))
ck("a point without a sampled peak still counts, by its mean", m and m["points"] == 3, str(m))
c = K.fit_cost_model(pts)
ck("seconds per 100k cells is the median over instances", c and abs(c["s_per_100k"] - 600.0) < 1e-6, str(c))
ck("and it lands in a band the tool defines once", c and c["band"] in K.COST_BANDS, str(c))
ck("the bands are ordered like the scheduler's cost order",
   list(K.COST_BANDS) == [k for k in K.Kernel.COST_ORDER if k in K.COST_BANDS][::-1]
   or set(K.COST_BANDS) <= set(K.Kernel.COST_ORDER), str(K.COST_BANDS))
ck("trivial is a few seconds, high is many minutes", K.cost_band(5.0) == "trivial" and K.cost_band(10_000.0) == "high",
   f"{K.cost_band(5.0)} {K.cost_band(10_000.0)}")

print("\ncapacity --cores and --cost are gates with a way out, like --memory")
PLUG = ('PLUGIN = {\n    "name": "k",\n    "cost": "low", "cores": 2,\n'
        '    "memory_gb_base": 1.0, "memory_gb_per_100k": 2.0,\n}\n')
with tempfile.TemporaryDirectory() as td:
    run = Path(td) / "run"
    run.mkdir()
    kfile = Path(td) / "k.py"
    kfile.write_text(PLUG)
    (run / "report.json").write_text(json.dumps({
        "kernels": {"k": {}},
        "cores_model": {"k": {"peak": 3.6, "mean": 2.9, "points": 4, "declared": 2}},
        "cost_model": {"k": {"s_per_100k": 600.0, "band": K.cost_band(600.0), "points": 4,
                             "declared": "low"}}}))

    def run_cli(*argv):
        o, e = io.StringIO(), io.StringIO()
        with redirect_stdout(o), redirect_stderr(e):
            try:
                rc = cli.main(list(argv))
            except SystemExit as ex:
                rc = ex.code
        return rc, o.getvalue() + e.getvalue()

    rc, out = run_cli("capacity", "--out", str(run), "--cores")
    ck("declared 2 against a measured peak of 3.6: the gate refuses", rc not in (0, None), f"rc={rc}\n{out[-400:]}")
    ck("and says what to declare", "cores" in out and "4" in out, out[-400:])
    rc, out = run_cli("capacity", "--out", str(run), "--cost")
    ck("declared low against a measured band above it: the gate refuses", rc not in (0, None), f"rc={rc}\n{out[-400:]}")
    ck("and names the band", K.cost_band(600.0) in out, out[-400:])

print("\n--declare writes the measured value into the plugin's own line, even beside other keys")
with tempfile.TemporaryDirectory() as td:
    kfile = Path(td) / "k.py"
    kfile.write_text(PLUG)
    K.write_declared_scalar(kfile, "cores", 4, note="measured in a run")
    K.write_declared_scalar(kfile, "cost", "medium")
    txt = kfile.read_text()
    ck("cores is 4 on the line it shared", '"cores": 4' in txt and '"cost": "medium"' in txt, txt)
    ck("and nothing else on that line changed", txt.count('"cost"') == 1 and '"memory_gb_base": 1.0' in txt, txt)
    ck("the note is beside it", "measured in a run" in txt, txt)

print("\n" + ("cores and cost are measured" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
