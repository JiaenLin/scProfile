"""Every field the host's monitor writes is declared as the run's execution record (autodev W065).

THE CLASS: out.json's `measured` is written by the host's monitor (`_entry.py`, `ctx.measured`):
the time, the CPU, the memory and the processes of the instance's own execution, which move
between two runs of the same input. Every one of them is declared in DEVPOINTS.yaml's
`fixture.execution_record`, so `agree` and the baseline report it and never judge it - except
`n_cells`, a count of the data, which stays judged. The declaration named four fields as the
monitor had them at W019; the monitor then added the process tree's peak, its sample count, the
job's cgroup peak and the peak process count, which only Linux's /proc gives, and on the cluster's
first dev-suite run `agree` judged two of them (abundance: `samples` 41 against 42). THIS TEST
reads the monitor's own dict from its source, every key in every branch, and holds each against
the declaration with the suite's matching (a glob is `product::key`; `*` stays inside one path
segment of the product and matches any run in the key) - so a field the monitor adds is declared
or this fails.

Run: python tests/test_the_record_covers_the_monitor.py
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAIL = []
DATA = {"n_cells"}          # a count of the data the instance ran on: judged, never excused


def ck(name, cond, detail=""):
    print(("  ok    " if cond else "  FAIL  ") + name + ("" if cond else f"  [{detail}]"))
    if not cond:
        FAIL.append(name)


def monitor_keys():
    """Every string key of the dict the entry point assigns to `ctx.measured`, every branch."""
    tree = ast.parse((ROOT / "scprofile" / "_entry.py").read_text(encoding="utf-8"))
    keys, sites = set(), 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Attribute) and t.attr == "measured"
                and isinstance(t.value, ast.Name) and t.value.id == "ctx" for t in node.targets):
            sites += 1
            for d in ast.walk(node.value):
                if isinstance(d, ast.Dict):
                    keys |= {k.value for k in d.keys
                             if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return keys, sites


def declared_globs():
    """The `fixture.execution_record` list, read as the YAML lists it: one quoted glob a line."""
    lines = (ROOT / "DEVPOINTS.yaml").read_text(encoding="utf-8").splitlines()
    out, on = [], False
    for ln in lines:
        if re.match(r"^  execution_record:\s*$", ln):
            on = True
            continue
        if on:
            m = re.match(r'^    - "([^"]+)"\s*$', ln)
            if m:
                out.append(m.group(1))
            elif ln.strip() and not ln.lstrip().startswith("#"):
                break
    return out


def excused(globs, product, key):
    for g in globs:
        if g.count("::") != 1:
            continue
        gp, gk = g.split("::")
        pp = "^" + "[^/]*".join(map(re.escape, gp.split("*"))) + "$"
        kp = "^" + ".*".join(map(re.escape, gk.split("*"))) + "$"
        if re.match(pp, product) and re.match(kp, key):
            return g
    return None


keys, sites = monitor_keys()
globs = declared_globs()
print("\nthe host monitor's fields are the run's declared execution record; the data count is not")
ck("the monitor's dict is found in _entry.py (one `ctx.measured = {...}`)", sites == 1 and keys,
   f"{sites} assignment(s), {len(keys)} key(s)")
ck("DEVPOINTS.yaml declares an execution record", bool(globs))
product = "run/kernels/abundance/out.json"
for k in sorted(keys - DATA):
    g = excused(globs, product, f"measured.{k}")
    ck(f"measured.{k} is declared" + (f" (by {g!r})" if g else ""), g is not None,
       "the monitor writes it and no glob of fixture.execution_record matches it")
for k in sorted(keys & DATA):
    g = excused(globs, product, f"measured.{k}")
    ck(f"measured.{k}, a count of the data, is NOT excused", g is None, f"excused by {g!r}")

print(f"\n{len(FAIL)} failure(s)" if FAIL else "\nall checks passed")
sys.exit(1 if FAIL else 0)
