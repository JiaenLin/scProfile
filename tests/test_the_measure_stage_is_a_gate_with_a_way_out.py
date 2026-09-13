"""`measure` is a gate with a way out: measured in any run, declared by one command, never by hand.

WHAT THIS REPLACES (harness ADR-0018). `capacity --memory` printed a fitted model "ready to paste"
and exited 0 whenever a model existed; the two numbers reached the declaration by somebody
pasting them, or did not. So a plugin could be measured on every run and declared from a guess
forever, and the stage read "answered" about a declaration nothing had compared. Now:

  - it exits 0 only when the plugin declares BOTH terms at or above the fit - under-declaration
    is the direction that kills a job, and it is what the exit code refuses;
  - `--declare <plugin>` writes the fit plus its headroom into the plugin's own file, reloads the
    declaration and refuses - restoring the file - if the values did not take. This is the
    repository's own tool editing its own artefact, as `scaffold --force` already regenerates the
    companion; the maker runs it as the stage's `apply:`.

Run: python tests/test_the_measure_stage_is_a_gate_with_a_way_out.py
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


PLUGIN = (
    '"""A widget for the memory gate\'s test."""\n'
    'PLUGIN = {\n'
    '    "name": "widget",\n'
    '    "api": 1,\n'
    '    "version": "0.1.0",\n'
    '    "summary": "a widget",\n'
    '\n'
    '    "cost": "low", "cores": 2,\n'
    '\n'
    '    "report": {"figures": []},\n'
    '}\n'
    '\n'
    '\n'
    'def run(ctx):\n'
    '    return None\n'
)

BASIS = ["the instance's own process tree (pss)"]


def model(name, base, rate, points=3):
    return {"memory_model": {name: {"base_gb": base, "gb_per_100k": rate, "points": points,
                                    "basis": BASIS}}}


def capacity(run, kernels, *extra):
    env = dict(os.environ, PYTHONPATH=str(ROOT), SCPROFILE_KERNELS=str(kernels))
    p = subprocess.run([sys.executable, "-m", "scprofile.cli", "capacity", "--out", str(run),
                        "--memory", *extra], capture_output=True, text=True, env=env, cwd=ROOT)
    return p.returncode, (p.stdout + p.stderr)


with tempfile.TemporaryDirectory() as td:
    run = Path(td) / "run"
    run.mkdir()
    kernels = Path(td) / "kernels"
    kernels.mkdir()
    plug = kernels / "widget.py"
    plug.write_text(PLUGIN)

    print("no model, no answer")
    (run / "report.json").write_text(json.dumps({}))
    rc, out = capacity(run, kernels)
    ck("a run that fitted nothing is refused, and the words say why",
       rc != 0 and "records no memory model" in out, out[-200:])

    print("\na model the declaration lags is a gate, not a printout")
    (run / "report.json").write_text(json.dumps(model("widget", 2.0, 4.0)))
    rc, out = capacity(run, kernels)
    ck("undeclared terms exit non-zero", rc != 0, f"rc {rc}")
    ck("and the way out is printed", "--declare widget" in out, out[-300:])
    ck("with the headroom the declaration will carry", "2.2" in out and "4.4" in out,
       out[-300:])

    print("\n--declare writes the fit into the plugin's own file, verified by reloading it")
    before = plug.read_text()
    rc, out = capacity(run, kernels, "--declare", "widget")
    after = plug.read_text()
    ck("the command exits 0 once the declaration is at the fit", rc == 0, out[-300:])
    ck("both terms are in the file",
       '"memory_gb_base": 2.2' in after and '"memory_gb_per_100k": 4.4' in after,
       after[after.find('"cost"'):][:160])
    ck("and the rest of the file is what it was",
       len(after.splitlines()) - len(before.splitlines()) <= 3
       and after.startswith(before[:before.find('"cost"')])
       and after.endswith(before[before.find('"report"'):]),
       f"{len(before.splitlines())} -> {len(after.splitlines())} lines")
    from scprofile import kernels as K
    ck("the host reads the terms back from the declaration",
       K.FileKernel(plug).executor.get("memory_gb_base") == 2.2
       and K.FileKernel(plug).executor.get("memory_gb_per_100k") == 4.4,
       str(K.FileKernel(plug).executor))
    rc, out = capacity(run, kernels)
    ck("and the gate is now answered without --declare", rc == 0, out[-200:])

    print("\na later measurement re-declares; a file the tool cannot anchor in is left alone")
    (run / "report.json").write_text(json.dumps(model("widget", 3.0, 1.0, 4)))
    rc, out = capacity(run, kernels)
    ck("a base now below the fit owes again, whatever the rate does", rc != 0, out[-200:])
    rc, out = capacity(run, kernels, "--declare", "widget")
    ck("re-declaring replaces both terms with the new fit",
       rc == 0 and '"memory_gb_base": 3.3' in plug.read_text()
       and '"memory_gb_per_100k": 1.1' in plug.read_text(), plug.read_text()[-400:])
    ck("and there is still exactly one line carrying them",
       plug.read_text().count('"memory_gb_base"') == 1, plug.read_text()[-400:])
    odd = kernels / "oddity.py"
    odd.write_text('PLUGIN = {"name": "oddity", "api": 1, "version": "0.1.0", "summary": "s",\n'
                   '          "report": {"figures": []}}\n\n\ndef run(ctx):\n    return None\n')
    (run / "report.json").write_text(json.dumps(model("oddity", 1.0, 1.0, 2)))
    was = odd.read_text()
    rc, out = capacity(run, kernels, "--declare", "oddity")
    ck("a plugin with no `cores` line to anchor on is refused",
       rc != 0 and "cores" in out, out[-300:])
    ck("and its file is byte-identical", odd.read_text() == was)
    rc, out = capacity(run, kernels, "--declare", "nobody")
    ck("a plugin the tree does not hold is refused by name", rc != 0 and "nobody" in out,
       out[-200:])

print("\n" + ("the gate holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
