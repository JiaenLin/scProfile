#!/usr/bin/env python3
"""The host writes no cohort's run into a plugin (harness W047, GAP-C100; rule 1).

A COHORT'S MEASUREMENT LIVES IN THE COHORT'S RECORD; THE TOOL STATES THE METHOD'S PROPERTY. Three
places in the host wrote one cohort's run into the tool by contract, and no leak guard could see
them, because no generated term list holds a run directory's name or a run's counts:

  - `capacity --declare` wrote `# measured in <run directory>` beside each value it declared, so
    every plugin it touched carried the name of one cohort's run;
  - the scaffold stamped a sentence of one run's counts into every generated drawing companion,
    so every new plugin that draws through R was born carrying them;
  - the development contract asked for exactly that: "what it cost, in the code", with one
    cohort's counts as its examples.

Each is checked here the way it is used: the two commands through the real CLI, on a throwaway
plugin, the contract by reading it (no command reads the contract; people do).

THE CHECK IS A SHAPE, NOT A STRING. A run directory named the way the harness names runs, and a
comment that counts what a run produced, are refused whatever their values, so a different run or a
different count cannot pass where the old one failed.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scprofile import kernels as K                                          # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f"\n       {detail}"))
    if not cond:
        FAIL.append(name)


def cli(*argv, kernels):
    env = dict(os.environ, PYTHONPATH=str(ROOT), SCPROFILE_KERNELS=str(kernels))
    p = subprocess.run([sys.executable, "-m", "scprofile.cli", *argv], capture_output=True,
                       text=True, env=env, cwd=ROOT)
    return p.returncode, p.stdout + p.stderr


# A RUN KEY IN THE HARNESS'S SHAPE (stamp__tool-commit__stage__label), invented: no cohort ran it.
RUN_KEY = "20991231T235959Z__scprofile-0000000__04_profile__rerun"
RUN_KEY_SHAPE = re.compile(r"\d{8}T\d{6}Z__|__\d{2}_[a-z]+__")

# WHAT A RUN PRODUCED, COUNTED: a number (or a count word) next to what a run makes or spends.
_WORDS = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
          "fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|hundred")
RUN_COUNT = re.compile(r"\b(\d[\d,.]*|" + _WORDS + r")\s+(\w+\s+)?(units?|samples?|instances?|"
                       r"cells|plates|figures|panels|plots|seconds|minutes|hours|GB|MB)\b", re.I)

PLUGIN = (
    '"""A widget for the capacity declaration\'s test."""\n'
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

print("capacity --declare writes how a value was measured, never which run measured it")
with tempfile.TemporaryDirectory() as td:
    run = Path(td) / RUN_KEY
    run.mkdir()
    kernels = Path(td) / "kernels"
    kernels.mkdir()
    plug = kernels / "widget.py"
    plug.write_text(PLUGIN)
    (run / "report.json").write_text(json.dumps({
        "kernels": {"widget": {}},
        "memory_model": {"widget": {"base_gb": 2.0, "gb_per_100k": 4.0, "points": 3,
                                    "basis": ["the instance's own process tree (pss)"]}},
        "cores_model": {"widget": {"peak": 3.6, "mean": 2.9, "points": 4, "declared": 2}},
        "cost_model": {"widget": {"s_per_100k": 600.0, "band": K.cost_band(600.0), "points": 4,
                                  "declared": "low"}}}))
    for flag, wrote in (("--memory", '"memory_gb_base": 2.2'), ("--cores", '"cores": 3'),
                        ("--cost", f'"cost": "{K.cost_band(600.0)}"')):
        rc, out = cli("capacity", "--out", str(run), flag, "--declare", "widget", kernels=kernels)
        txt = plug.read_text()
        ck(f"{flag} --declare exits 0 and writes the value", rc == 0 and wrote in txt,
           f"rc={rc}\n{out[-300:]}\n{txt}")
        ck(f"{flag}: the plugin carries no run's name", RUN_KEY not in txt
           and not RUN_KEY_SHAPE.search(txt), txt[txt.find('"cost"'):][:240])
        ck(f"{flag}: and the run is named to the person running it, for the cohort's record",
           RUN_KEY in out, out[-300:])
    txt = plug.read_text()
    notes = [l for l in txt.splitlines() if "#" in l]
    ck("each declared line says how it was measured", notes
       and all("measured" in l and "run's instances" in l for l in notes), "\n".join(notes))
    ck("the plugin still loads, with what was declared",
       K.FileKernel(plug).executor.get("memory_gb_base") == 2.2, str(K.FileKernel(plug).executor))

print("\nthe scaffold writes no run's counts into a new plugin")


def comments(text):
    return [l for l in text.splitlines() if l.lstrip().startswith("#")]


with tempfile.TemporaryDirectory() as td:
    kernels = Path(td) / "kernels"
    kernels.mkdir()
    plug = kernels / "drawer.py"
    plug.write_text(PLUGIN.replace('"widget"', '"drawer"').replace(
        '"cost": "low", "cores": 2,', '"cost": "low", "cores": 2,\n    "requires": {"r": ["4.3"]},'))
    rc, out = cli("scaffold", "drawer", "--force", kernels=kernels)
    comp = kernels / "drawer.draw.R"
    ck("the drawing companion is generated through the CLI", rc == 0 and comp.is_file(),
       f"rc={rc}\n{out[-300:]}")
    hits = [l.strip() for l in comments(comp.read_text())
            if RUN_COUNT.search(l)] if comp.is_file() else ["(no companion)"]
    ck("and none of its comments counts what one run produced", not hits, "\n".join(hits))
    rc, out = cli("scaffold", "fresh", "--new", "--dir", str(Path(td) / "new"), kernels=kernels)
    made = sorted((Path(td) / "new").glob("*")) if (Path(td) / "new").is_dir() else []
    ck("a new plugin is written through the CLI", rc == 0 and made, f"rc={rc}\n{out[-300:]}")
    hits = [f"{p.name}: {l.strip()}" for p in made for l in comments(p.read_text())
            if RUN_COUNT.search(l)]
    ck("and none of its comments counts what one run produced", not hits, "\n".join(hits))

print("\nthe contract asks for the method's property, and sends a cohort's numbers to its record")
contract = (ROOT / "docs" / "DEVELOPMENT_CONTRACT.md").read_text(encoding="utf-8")
fix = contract[contract.find("**Two things a minimal fix always includes**"):]
fix = contract[contract.find("**Two things a minimal fix always includes**"):][:1600]
ck("the contract's minimal fix says where a cohort's measurement lives",
   "cohort's record" in fix, fix[:600])
ck("and asks for no run's counts in the code", not re.search(
    r"\d+ of \d+ units|\d+ figures|\d+(\.\d+)? against \d+|with the measurement", fix), fix[:600])

print("\n" + ("the host writes no run into a plugin" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
