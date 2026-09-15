"""The run -> declare edge is a stage the maker reads, and the grammar of `produces` is held
(harness ADR-0026, step 4 - the kill pass).

EVERY RUN OF THE ARC PRINTED SEVEN `[declaration]` LINES PER UNIT - 260 a run - about `produces`
naming files the plugin does not register and missing one it does, and the maker's contract
stage read `done` over them: the drift was computed at the run, printed, stored in report.json,
and gated on by nothing. `scprofile capacity --out RUN --drift` reads the run's own diagnoses
back and exits non-zero on any; the maker's `declared` test stage runs it. And the plugin's
`produces` was written in a grammar no reader of it uses - `[optional] objects/x.rds` - which
the validator accepted; it refuses that now and says the form the readers read.

Run: python tests/test_what_the_plugin_did_against_what_it_said.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import declare as D                                              # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def drift(run):
    return subprocess.run([sys.executable, "-m", "scprofile.cli", "capacity", "--out", str(run),
                           "--drift"], cwd=str(ROOT), capture_output=True, text=True)


print("the run's declaration drift is read back, and gates")
with tempfile.TemporaryDirectory() as td:
    run = Path(td) / "run"
    run.mkdir()
    (run / "report.json").write_text(json.dumps({"diagnoses": [
        {"layer": "declaration", "why": "declares 'tables/x.csv' in `produces` and did not emit it.",
         "action": "fix `produces`"},
        {"layer": "declaration", "why": "declares 'tables/x.csv' in `produces` and did not emit it.",
         "action": "fix `produces`"},
        {"layer": "declaration", "why": "emitted 'tables/y.csv', which it does not declare in `produces`.",
         "action": "add it"},
        {"layer": "memory", "why": "peak above the declaration", "action": "raise it"}]}))
    p = drift(run)
    ck("non-zero with declaration drift", p.returncode != 0, p.stdout + p.stderr)
    ck("each distinct drift once, with how many units said it",
       "tables/x.csv" in p.stdout and "2 unit(s)" in p.stdout and "tables/y.csv" in p.stdout,
       p.stdout[:400])
    ck("a diagnosis of another layer is not counted here", "memory" not in p.stdout.lower()
       or "peak above" not in p.stdout, p.stdout[:400])
    (run / "report.json").write_text(json.dumps({"diagnoses": [
        {"layer": "memory", "why": "peak above the declaration", "action": "raise it"}]}))
    p = drift(run)
    ck("zero with none", p.returncode == 0 and "no declaration drift" in p.stdout, p.stdout + p.stderr)

print("\n`produces` is held to the grammar its readers read")


def errs(items):
    spec = {"name": "demo", "api": 1, "version": "1.0.0", "state_version": 1, "summary": "s",
            "when_to_use": "w", "provides": ["x"], "requires": {"python": ">=3.10"},
            "produces": items, "report": {"figures": []}}
    return [m for lvl, m in D.check(spec, "demo") if lvl == "ERROR" and "produces" in m]


ck("a table by name, an optional one, and a slot form pass",
   not errs(["edges.csv", "tables/edges.csv", "scores.csv?", "obs[phase]", "objects[fit.rds]?"]),
   str(errs(["edges.csv", "scores.csv?", "obs[phase]"])))
bad = errs(["[optional] objects/cellchat.rds"])
ck("a `[optional]` prefix is refused, and the `?` form named", bad and "?" in bad[0], str(bad))
bad = errs(["objects/fit.rds"])
ck("a path into a slot directory is refused, and the slot form named",
   bad and "objects[fit.rds]" in bad[0], str(bad))

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\nwhat the plugin did is read against what it said")
