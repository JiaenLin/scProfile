"""Whether the next run will re-infer is said before the job, from the declaration and the
run it follows (harness ADR-0026, step 4 - the kill pass).

A comment inside the inference span, a keyed parameter's default, a legend: two of the three
cost eighteen units of inference and one costs nothing, and the maker said nothing about any of
them. A plugin that keeps a fitted object declares what keys it - the span of its source that
determines the object, and the config parameters in the key - and `scprofile cache --forecast`
reads the working tree against the tool commit the reference run recorded: HIT or MISS, with
the reason. Everything here is invented; a git repository is made for the purpose.

Run: python tests/test_the_cache_is_forecast_before_a_job.py
"""
import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import landscape as L                                            # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


PLUGIN = textwrap.dedent('''\
    PLUGIN = {
        "name": "demo",
        "version": "1.0.0",
        "cache": {"span": ["# --- RECIPE START ---", "# --- RECIPE END ---"],
                  "keyed_on": ["nboot", "trim"]},
        "config": {"nboot": {"type": "int", "default": 100, "help": "h"},
                   "trim": {"type": "float", "default": 0.1, "help": "h"},
                   "dots": {"type": "int", "default": 20, "help": "h"}},
        "report": {"figures": [{"id": "native_a", "legend": "a ring"}]},
    }

    R = """
    # --- RECIPE START ---
    fit <- infer(x, nboot = NBOOT, trim = TRIM)
    # --- RECIPE END ---
    draw(fit, title = "the ring")
    """
    ''')


def git(d, *args):
    return subprocess.run(["git", "-C", str(d), *args], capture_output=True, text=True, check=True)


with tempfile.TemporaryDirectory() as td:
    root = Path(td) / "tool"
    (root / "kernels").mkdir(parents=True)
    f = root / "kernels" / "demo.py"
    f.write_text(PLUGIN, encoding="utf-8")
    git(root, "init", "-q")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "one")
    commit = git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    run = Path(td) / "run"
    (run / "kernels" / "demo" / "U1").mkdir(parents=True)
    (run / "report.json").write_text(json.dumps({"tool_commit": commit}))
    (run / "kernels" / "demo" / "U1" / "in.json").write_text(json.dumps({"params": {}}))

    print("unchanged: a hit")
    fc = L.cache_forecast(root, "demo", run)
    ck("hit", fc["hit"] is True, str(fc))
    ck("against the run's own commit", fc.get("commit") == commit, str(fc))

    print("\na legend changed: still a hit")
    f.write_text(PLUGIN.replace('"legend": "a ring"', '"legend": "a ring, again"'), encoding="utf-8")
    fc = L.cache_forecast(root, "demo", run)
    ck("hit", fc["hit"] is True, str(fc))

    print("\na comment inside the span: a miss, and the reason names the span")
    f.write_text(PLUGIN.replace("fit <- infer(", "# a note\nfit <- infer("), encoding="utf-8")
    fc = L.cache_forecast(root, "demo", run)
    ck("miss", fc["hit"] is False, str(fc))
    ck("the reason", any("span" in r for r in fc["reasons"]), str(fc))

    print("\na keyed parameter's default changed: a miss, naming the parameter")
    f.write_text(PLUGIN.replace('"default": 100', '"default": 50'), encoding="utf-8")
    fc = L.cache_forecast(root, "demo", run)
    ck("miss", fc["hit"] is False, str(fc))
    ck("the reason names nboot and both values", any("nboot" in r and "100" in r and "50" in r
                                                      for r in fc["reasons"]), str(fc))

    print("\na parameter outside the key changed: a hit")
    f.write_text(PLUGIN.replace('"default": 20', '"default": 30'), encoding="utf-8")
    fc = L.cache_forecast(root, "demo", run)
    ck("hit", fc["hit"] is True, str(fc))

    print("\nthe run gave the parameter a value: that value is what is keyed")
    (run / "kernels" / "demo" / "U1" / "in.json").write_text(json.dumps({"params": {"nboot": 50}}))
    f.write_text(PLUGIN.replace('"default": 100', '"default": 50'), encoding="utf-8")
    fc = L.cache_forecast(root, "demo", run)
    ck("a default now equal to what the run was given is a hit", fc["hit"] is True, str(fc))

    print("\na plugin declaring no cache cannot be forecast, and says so")
    f.write_text(PLUGIN.replace('"cache": {"span"', '"cache_x": {"span"'), encoding="utf-8")
    fc = L.cache_forecast(root, "demo", run)
    ck("no forecast, with the reason", fc["hit"] is None and "declares no `cache`" in " ".join(fc["reasons"]), str(fc))

    print("\nthe command prints it")
    f.write_text(PLUGIN.replace("fit <- infer(", "# a note\nfit <- infer("), encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "scprofile.cli", "cache", "--out", str(run),
                        "--forecast", "--plugin", "demo", "--root", str(root)],
                       cwd=str(ROOT), capture_output=True, text=True)
    ck("MISS on the line, with the reason", p.returncode == 0 and "MISS" in p.stdout and "span" in p.stdout,
       p.stdout + p.stderr)

print("\nthe store keeps one object per span: a run with another span writes beside, not over")
# LAST WRITER WINS, TWICE IN ONE HOUR (harness ADR-0026, runs F and G): the store held one
# object per parameter key, a mutant span re-inferred and overwrote main's objects, and the next
# run of main - forecast HIT - paid twenty minutes re-inferring and overwrote them back. The
# host keys the unit's cache directory by the declared span, so versions of the inference
# coexist and the objects a run left cannot be overwritten by a run of another span; the
# forecast's HIT then means what it says, short of the cache being cleared.
with tempfile.TemporaryDirectory() as td:
    root = Path(td) / "tool"
    (root / "kernels").mkdir(parents=True)
    f = root / "kernels" / "demo.py"
    f.write_text(PLUGIN, encoding="utf-8")
    k1 = L.span_key(f, {"span": ["# --- RECIPE START ---", "# --- RECIPE END ---"]})
    ck("a key, ten hex characters", isinstance(k1, str) and len(k1) == 10
       and all(c in "0123456789abcdef" for c in k1), str(k1))
    f.write_text(PLUGIN.replace('"legend": "a ring"', '"legend": "a ring, again"'), encoding="utf-8")
    ck("a legend edit keeps the key",
       L.span_key(f, {"span": ["# --- RECIPE START ---", "# --- RECIPE END ---"]}) == k1)
    f.write_text(PLUGIN.replace("fit <- infer(", "# a note\nfit <- infer("), encoding="utf-8")
    k2 = L.span_key(f, {"span": ["# --- RECIPE START ---", "# --- RECIPE END ---"]})
    ck("an edit inside the span is another key", k2 != k1, f"{k1} {k2}")
    ck("no declaration, no key: the directory is the unit's, as before",
       L.span_key(f, None) is None and L.span_key(f, {}) is None)
    f.write_text(PLUGIN.replace("# --- RECIPE END ---", "# --- gone ---"), encoding="utf-8")
    ck("markers not both in the file: no key, said rather than guessed",
       L.span_key(f, {"span": ["# --- RECIPE START ---", "# --- RECIPE END ---"]}) is None)
src = (ROOT / "scprofile" / "cli.py").read_text(encoding="utf-8")
ck("the runner keys the unit's cache directory by it",
   "_L.span_key(" in src or "landscape.span_key(" in src or "span_key(" in src.split("cache_dir=")[1][:600]
   if "cache_dir=" in src else False)

print("\nthe HIT means what it says now")
with tempfile.TemporaryDirectory() as td:
    root = Path(td) / "tool"
    (root / "kernels").mkdir(parents=True)
    f = root / "kernels" / "demo.py"
    f.write_text(PLUGIN, encoding="utf-8")
    git(root, "init", "-q")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "one")
    commit = git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    run = Path(td) / "run"
    (run / "kernels" / "demo" / "U1").mkdir(parents=True)
    (run / "report.json").write_text(json.dumps({"tool_commit": commit}))
    (run / "kernels" / "demo" / "U1" / "in.json").write_text(json.dumps({"params": {}}))
    fc = L.cache_forecast(root, "demo", run)
    ck("a hit no longer hedges about a later run overwriting the objects",
       fc["hit"] is True and "overwrote" not in " ".join(fc["reasons"]), str(fc))
    ck("it names the one thing that still defeats it", "clear" in " ".join(fc["reasons"]), str(fc))

print("\nthe store's key changed since the run named: a MISS, once, said rather than met")
# THE FORECAST WOULD HAVE BEEN WRONG BY THIS VERY CHANGE: keying the store by span moves every
# existing object out of reach once, and a forecast reading only the plugin's span would say
# HIT while every unit re-inferred. The tool at the run's commit either keyed the store or did
# not; where it did not and the tree does, the objects are under the unkeyed path.
with tempfile.TemporaryDirectory() as td:
    root = Path(td) / "tool"
    (root / "kernels").mkdir(parents=True)
    (root / "scprofile").mkdir()
    f = root / "kernels" / "demo.py"
    f.write_text(PLUGIN, encoding="utf-8")
    (root / "scprofile" / "landscape.py").write_text("# the tool before the store was keyed\n")
    git(root, "init", "-q")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "one")
    commit = git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    (root / "scprofile" / "landscape.py").write_text("def span_key(plugin_path, decl):\n    pass\n")
    run = Path(td) / "run"
    (run / "kernels" / "demo" / "U1").mkdir(parents=True)
    (run / "report.json").write_text(json.dumps({"tool_commit": commit}))
    (run / "kernels" / "demo" / "U1" / "in.json").write_text(json.dumps({"params": {}}))
    fc = L.cache_forecast(root, "demo", run)
    ck("a miss, and the reason names the store's key", fc["hit"] is False
       and any("key" in r and "once" in r for r in fc["reasons"]), str(fc))
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "two")
    (run / "report.json").write_text(json.dumps({"tool_commit": git(root, "rev-parse", "--short", "HEAD").stdout.strip()}))
    fc = L.cache_forecast(root, "demo", run)
    ck("a run made after the keying: a hit again", fc["hit"] is True, str(fc))

print("\nthe declaration's shape is held")
from scprofile import declare as D                                              # noqa: E402


def errs(cache):
    spec = {"name": "demo", "api": 1, "version": "1.0.0", "state_version": 1, "summary": "s",
            "when_to_use": "w", "provides": ["x"], "requires": {"python": ">=3.10"},
            "config": {"nboot": {"type": "int", "default": 1, "help": "h"}},
            "cache": cache, "report": {"figures": []}}
    return [m for lvl, m in D.check(spec, "demo") if lvl == "ERROR" and "cache" in m]


ck("a span of two markers and keyed parameters the config declares pass",
   not errs({"span": ["# --- A ---", "# --- B ---"], "keyed_on": ["nboot"]}), str(errs({"span": ["# --- A ---", "# --- B ---"], "keyed_on": ["nboot"]})))
ck("one marker is refused", errs({"span": ["# --- A ---"], "keyed_on": []}))
ck("a keyed parameter the config lacks is refused, by name",
   any("trim" in m for m in errs({"span": ["# --- A ---", "# --- B ---"], "keyed_on": ["trim"]})))

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\nthe cache is forecast before a job")
