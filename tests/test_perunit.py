"""Ten defects an adversarial review found after the wave rewrite. One test each.

Nine of the ten live on the PER-UNIT path, and none of them could fire with the kernels in the
tree today: the three `per_unit: sample` plugins are `status: planned` and `run` skips anything
not built. That is exactly the argument for testing them here rather than waiting - the first
built per-unit plugin, in-tree or supplied through $SCPROFILE_KERNELS, meets all nine at once,
and every one of them fails by delivering a document that looks complete.

Run: python tests/test_perunit.py
"""
import inspect
import pathlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import cli, merge, report                                        # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(name)


def _payloads():
    """Three units of one plugin, the third having failed to produce its array output."""
    out = []
    for u in ("s1", "s2", "s3"):
        out.append({
            "kernel": "liana", "unit": u, "dir": f"kernels/liana/{u}",
            "status": "ok", "headline": f"{u}: 812 interactions", "version": "0.1",
            "obs": {"ccc_score": "obs/score.csv"},
            "obsm": {"X_ccc": "arrays/ccc.npy"},
            "tables": ["out/ccc_edges.csv"],
            "figures": [{"path": "figs/dot.png", "vector": "figs/dot.pdf",
                         "source": "figs/dot.csv", "caption": "dotplot"}],
            "caveats": [f"{u} caveat"],
        })
    return out


print("\nper-unit payloads survive folding")
f = merge.fold_payloads(_payloads())
ck("one entry per plugin", set(f) == {"liana"})
ck("every unit is kept", [u["unit"] for u in f["liana"]["units"]] == ["s1", "s2", "s3"],
   f"got {[u['unit'] for u in f['liana']['units']]}")
ck("every unit's figures are kept", len(f["liana"]["figures"]) == 3)
ck("every unit's caveats are kept", len(f["liana"]["caveats"]) == 3)
ck("the headline says it is per unit", "3 unit(s)" in f["liana"]["headline"])

print("\nfigure paths resolve from report/")
paths = [x["path"] for x in f["liana"]["figures"]]
ck("path carries the unit segment", all("/s" in p and p.startswith("kernels/liana/") for p in paths),
   str(paths))
ck("vector and source too",
   all(x["vector"].startswith("kernels/liana/s") and x["source"].startswith("kernels/liana/s")
       for x in f["liana"]["figures"]))
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    report.write_kernel(d, "liana", f["liana"], [], "")
    html = (d / "report" / "liana.html").read_text()
    ck("rendered src includes the unit", 'src="../kernels/liana/s1/figs/dot.png"' in html,
       "hrefs still guess ../kernels/<name>/")
    ck("no unit-less kernel href survives", '"../kernels/liana/figs' not in html)
    ck("the page has a per-unit section", "Per unit" in html and "s3" in html)

print("\ntable names are the ones actually delivered")
ck("unit-suffixed", sorted(f["liana"]["tables"]) ==
   ["tables/liana_ccc_edges__s1.csv", "tables/liana_ccc_edges__s2.csv",
    "tables/liana_ccc_edges__s3.csv"], str(f["liana"]["tables"]))
ck("copy_tables and link_objects share one rule",
   "delivered_name" in inspect.getsource(merge.copy_tables)
   and "delivered_name" in inspect.getsource(merge.link_objects))
ck("a side-car object is unit-suffixed",
   merge.delivered_name({"kernel": "scenic", "unit": "s2"}, "scenic.loom") == "scenic__s2.loom")

print("\nthe report says what the merge did, not what the plugin declared")
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    report.write_kernel(d, "liana", f["liana"], [], "", merged={"obs": ["ccc_score"], "obsm": []})
    html = (d / "report" / "liana.html").read_text()
    ck("a dropped obsm is not called merged", "NOT in the object" in html)
    ck("the merged obs still is", html.count("merged into the object by barcode") >= 1)

print("\na plugin that ran on some units and failed on others")
pay = {"ran": ["liana"], "skipped": [{"kernel": "liana", "unit": "s3", "why": ["boom"]},
                                     {"kernel": "liana", "unit": "s2", "why": ["bang"]}],
       "kernels": f, "cannot_show": {"liana": []}, "summaries": {}, "describe": {},
       "status": {"liana": "built"}}
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    report.write_index(d, pay)
    idx = (d / "report" / "index.html").read_text()
    ck("the index does not call it a plain success", "unit(s) failed" in idx)
    ck("it names the units that are missing", "s3" in idx and "s2" in idx)
    ck("it says those cells are NaN", "NaN" in idx)
ck("every reason is kept, not the last one",
   "accumulate" in inspect.getsource(report.write_index).lower()
   or "setdefault" in inspect.getsource(report.write_index))

print("\nthe README counts plugins, not instances")
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "report").mkdir()
    (d / "report" / "index.html").write_text("i")
    (d / "report" / "liana.html").write_text("k")
    cli._write_readme(d, dict(pay, version="0.1", input="x.h5ad", object=str(d / "o.h5ad")))
    md = (d / "README.md").read_text()
    ck("one plugin ran, none failed outright", "**1** plugin(s) ran, **0** did not" in md,
       md.splitlines()[2] if len(md.splitlines()) > 2 else md[:120])
    ck("the partial run is named as such", "not on every unit" in md and "s3" in md)
    ck("the layout section sees report/", "report/" in md)
    n = int(md.split("- ")[2].split(" files")[0])
    ck("the file count includes README.md itself", n == 3, f"counted {n} of 3")

print("\na run that produced nothing must still be able to say so")
# THE REGRESSION THAT PROMPTED THIS. `objects/` was created unconditionally, and it was the only
# thing that created the run's output directory at all. Making it conditional on something having
# merged - so that a run in which every plugin refused stops writing a multi-gigabyte copy of its
# input under a name that says it was profiled - killed `report.json` with FileNotFoundError on
# exactly the run whose report matters most. A fix that only works on the happy path is worse
# than the bug: the wasteful object was at least accompanied by an explanation.
import ast as _ast
import textwrap as _tw
_src = _tw.dedent(inspect.getsource(cli._run))
_fn = _ast.parse(_src).body[0]
_top = [n for n in _fn.body
        if isinstance(n, _ast.Expr) and isinstance(n.value, _ast.Call)
        and isinstance(n.value.func, _ast.Attribute) and n.value.func.attr == "mkdir"
        and getattr(n.value.func.value, "id", "") == "out"]
ck("the output directory is created by the function, not by one of its branches", bool(_top),
   "every writer below assumes it exists; a conditional mkdir makes that true only sometimes")

# A PLUGIN THAT RAN AND REFUSED STILL GETS A MERGE ENTRY - {'obs': [], 'obsm': [], 'layers': []} -
# and that dict is truthy. Testing `if merged_slots:` therefore answered "did anything attempt a
# merge", not "did anything land", and PBS 676944 wrote 3.21 GB on the strength of it: velocity
# recovered from a broken environment, refused for want of spliced counts, and the run announced
# an object it had contributed nothing to. The emptiness has to be looked INTO.
_empty_entry = {"velocity": {"obs": [], "obsm": [], "layers": []}}
_landed = {"velocity": {"obs": ["velocity_length"], "obsm": [], "layers": []}}
ck("a merge entry that merged nothing is not evidence of an object",
   not any(v for got in _empty_entry.values() for v in got.values()))
ck("and one that merged something is", any(v for got in _landed.values() for v in got.values()))
ck("the writer tests what LANDED, not that a merge was attempted",
   "merged_anything" in _src and "if merged_slots:" not in _src,
   "a refusal produces an entry describing nothing, and the entry is truthy")

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    empty = dict(pay, version="0.1", input="x.h5ad", object=None, ran=[], kernels={})
    report.write_index(d, empty)
    idx = (d / "report" / "index.html").read_text()
    ck("the report says no object was written rather than rendering None",
       "No object was written" in idx and ">None<" not in idx, idx[:200])
    cli._write_readme(d, empty)
    ck("the README still renders with no object", (d / "README.md").exists())

print("\nan adversarial review's eight findings")
class _Obs(dict):
    @property
    def columns(self):
        return list(self)
class _AD:
    def __init__(self, n=6):
        self.obs_names = _Idx([f"c{i}" for i in range(n)])
        self.obs, self.obsm, self.layers = _Obs(), {}, {}
        self.n_obs = n
class _Idx(list):
    is_unique = True
    def astype(self, _):
        return self
    def intersection(self, other):
        return _Idx([x for x in self if x in set(other)])

# merge_one must be ALL-OR-NOTHING: a refusal must leave the object untouched.
import types                                                                   # noqa: E402
_read_obs, _read_arr = merge._read_obs_column, merge._read_array
class _S(dict):
    def __init__(self, d):
        super().__init__(d)
        self.index = _Idx(list(d))
    def reindex(self, bc):
        return types.SimpleNamespace(values=[self.get(b) for b in bc])
merge._read_obs_column = lambda p: _S({"c0": 1.0, "c1": 2.0})
merge._read_array = lambda p: types.SimpleNamespace(shape=(2, 3))
A_ = _AD()
try:
    merge.merge_one(A_, ".", {"kernel": "P", "unit": "s1",
                              "obs": {"score": "o.csv"}, "obsm": {"X_p": "a.npy"}})
    ck("a mismatched array is refused", False, "it was accepted")
except merge.MergeError as e:
    ck("a mismatched array is refused", True)
    ck("and NOTHING was written to the object first", list(A_.obs) == [], str(list(A_.obs)))
    ck("the refusal names the per-unit cause", "ran per unit" in str(e))

# a single SURVIVING unit must not be routed through merge_one
seen = {}
merge.merge_one = lambda *a_, **k_: seen.setdefault("called", True)
try:
    merge.merge_many(_AD(), [(".", {"kernel": "P", "unit": "s4", "obs": {"score": "o.csv"}})])
except Exception:                                                              # noqa: BLE001
    pass
ck("one surviving unit does NOT take the merge_one shortcut", "called" not in seen)
merge.merge_one, merge._read_obs_column, merge._read_array = (
    merge.__dict__["merge_one"], _read_obs, _read_arr)

# a basename collision is refused rather than resolved by luck
with tempfile.TemporaryDirectory() as _d:
    _d = Path(_d)
    for _r in ("a/edges.csv", "b/edges.csv"):
        (_d / _r).parent.mkdir(parents=True, exist_ok=True)
        (_d / _r).write_text(_r)
    try:
        merge.copy_tables(_d, {"kernel": "P", "unit": None,
                               "tables": ["a/edges.csv", "b/edges.csv"]}, _d / "out")
        ck("two tables with one basename are refused", False, "one silently replaced the other")
    except merge.MergeError as e:
        ck("two tables with one basename are refused", "both deliver as" in str(e))
        ck("and nothing was delivered before the refusal",
           not (_d / "out").exists() or not list((_d / "out").iterdir()))

# a plugin whose units failed is PARTIAL everywhere
fp = merge.fold_payloads(_payloads()[:2], failed={"liana": ["s3", "s4"]})
ck("status is partial when units failed", fp["liana"]["status"] == "partial",
   fp["liana"]["status"])
ck("the failed units are named", fp["liana"]["failed_units"] == ["s3", "s4"])
ck("the headline says so", "FAILED" in fp["liana"]["headline"])
ck("a caveat says the cells are NaN", "NaN" in (fp["liana"]["caveats"] or [""])[0])
pv = merge.provenance(fp, {}, {}, merged={})
ck("uns carries the failed units", pv["kernels"]["liana"]["failed_units"] == ["s3", "s4"])
ck("uns does not say ok", pv["kernels"]["liana"]["status"] == "partial")

# the schedule table shows each instance's OWN time
sched = {"schedule": [[{"plugin": "liana", "unit": "s1", "cores": 1, "seconds": 100.0},
                       {"plugin": "liana", "unit": "s2", "cores": 1, "seconds": 100.0},
                       {"plugin": "liana", "unit": "s3", "cores": 1}]],
         "seconds": {"liana": [100.0, 100.0]}, "cores": 4}
blk = report._schedule_block(sched)
ck("a unit row shows its own seconds, not the plugin's total",
   blk.count("100s") == 2 and "200s" not in blk, blk[-400:])
ck("a unit that never ran says so", "did not run" in blk)

print("\nsingle-instance plugins are unchanged in shape")
one = merge.fold_payloads([{"kernel": "cellcycle", "unit": None, "dir": "kernels/cellcycle",
                            "status": "ok", "headline": "h", "obs": {"phase": "o.csv"},
                            "tables": ["t.csv"], "figures": [{"path": "f.png"}]}])
ck("no per-unit section", not one["cellcycle"]["per_unit"])
ck("headline is the plugin's own", one["cellcycle"]["headline"] == "h")
ck("path is still run-relative", one["cellcycle"]["figures"][0]["path"] == "kernels/cellcycle/f.png")

print("\nthe builders report their own state honestly")
import io as _io, contextlib as _ctx, argparse as _ap                          # noqa: E402
_buf = _io.StringIO()
with _ctx.redirect_stdout(_buf):
    cli._doctor(_ap.Namespace(prefix=None, references=None, organism=None))
_doc = _buf.getvalue()
for _n in ("de", "decoupler", "abundance", "liana", "scenic", "cellchat", "pseudotime"):
    _line = next((l for l in _doc.splitlines() if f" {_n} " in l or f" {_n}  " in l), "")
    ck(f"doctor does not call {_n} ok", not _line.strip().startswith("ok"), _line.strip()[:90])
# EVERY PLUGIN IS NOW BUILT, so there is no unbuilt one to observe. The RULE still has to hold,
# so it is tested against the branch rather than against the tree - a test that needed an unbuilt
# plugin to exist would have to keep one unbuilt forever to keep passing.
_dsrc = inspect.getsource(cli._doctor)
ck("doctor still has the unbuilt branch", '"TODO"' in _dsrc and "planned" in _dsrc)
ck("and it keys on status, not on a name", 'k.status == "built"' in _dsrc)
ck("no plugin in this tree is unbuilt", "TODO" not in _doc,
   "which is the goal state, not a reason to delete the rule")
# AND NO PLUGIN IN THIS TREE RUNS IN THE HOST INTERPRETER ANY MORE, which is the same shape of
# problem one line up: `cellcycle` was the built host-interpreter plugin this asserted against,
# and it now declares a requirement and shares the others' environment. The RULE - a plugin that
# needs no environment is ready, not missing - is tested against the branch and against a kernel
# that declares it, so keeping one plugin unpinned forever is not the price of keeping the check.
ck("doctor still has the host-interpreter branch", '"host"' in _dsrc or "host" in _dsrc)
from scprofile import runner as _rn                                            # noqa: E402
import types as _ty                                                            # noqa: E402
_hostk = _ty.SimpleNamespace(name="hostish", needs_env=False, language="python",
                             path=Path("/nowhere/hostish.py"))
ck("a plugin needing no environment reads as host, not missing",
   _rn.env_state(_hostk, prefix=None)[0] == "host", str(_rn.env_state(_hostk, prefix=None)))
ck("doctor can say how many are unbuilt", "DECLARED BUT NOT BUILT" in _dsrc)

from scprofile import refs as _refs                                            # noqa: E402
from scprofile.kernels import discover as _disc                                # noqa: E402
_ks = _disc()
_out = []
_refs.fetch(_ks["cellcycle"], "/tmp/__noref", log=_out.append, dry_run=True)
ck("a plugin with no references is not called 'all present'",
   any("declares no reference data" in x for x in _out), "; ".join(_out))
ck("and does not claim anything is present",
   not any("present" in x for x in _out), "; ".join(_out))

_src = inspect.getsource(cli)
ck("every per-plugin label is flushed before its work",
   'print(f"{name}:")' not in _src and 'print(f"{n}:")' not in _src)

print("\nthe live defects")
ck("--dry-run reaches refs.fetch", "dry_run=" in inspect.getsource(cli._fetch))
ck("--kernel a,a is deduplicated", cli._split("a,b,a") == ["a", "b"])
src = inspect.getsource(cli._run)
ck("the budget is redivided over what launches",
   "_budget([i for i, _k, _c in staged], budget)" in src)

# PLAN AND RUN MUST ANSWER THE SAME QUESTION ABOUT THE SAME MACHINE. `plan` hard-coded
# `--cores 8` while `run` defaulted to the scheduler's allocation, so on PBS 679143 the plan
# printed `scenic[Aging1](8c)` and the run did `scenic[Aging1](16c)`. The plan is what a person
# reads BEFORE committing a job; one that understates the budget understates every share in it.
_parser = cli._parser() if hasattr(cli, "_parser") else None
_plansrc = inspect.getsource(cli._plan)
ck("plan resolves its budget the way run does",
   "_default_cores()" in _plansrc, "plan never calls _default_cores()")
_cli_src = pathlib.Path(cli.__file__).read_text()
ck("neither subcommand hard-codes a core budget",
   'add_argument("--cores", type=int, default=8)' not in _cli_src)
ck("both --cores default to the allocation",
   _cli_src.count('add_argument("--cores", type=int, default=None') == 2,
   f'{_cli_src.count(chr(39))}: found {_cli_src.count("--cores")} --cores definitions')
# The CALL SITE, not the def - which sits above _budget in the same function and would make this
# pass by matching the wrong occurrence. A check that passes for its own reasons is the failure
# mode three defects in this morning's harness already had.
ck("in.json is written AFTER the budget, not with the rest of preparation",
   src.index("_budget([i for i") < src.index("prepared = [(inst, _write_in("))
ck("every filter that can refuse runs before the budget",
   all(src.index(x) < src.index("_budget([i for i") for x in
       ("guard refused:", "cannot read this object even re-encoded")))
ck("per_unit with no unit key is announced", "per_unit and no unit key" in src.replace("\n", " ")
   or "declare per_unit" in src)
ck("the README is written after the report", src.index("report.write_all") < src.index("_write_readme(out"))

print("\nevery file that names a module imports it")
import ast as _ast                                                             # noqa: E402
# ROOTED AT THE FILE, NOT AT THE WORKING DIRECTORY. `Path("scprofile").rglob(...)` returns
# NOTHING when the suite is run from anywhere else, and this check then passes having opened zero
# files - which is the failure `test_portability` guards its own scan against and this one did
# not. It was never noticed because nothing had run the suites from outside the repository root
# until the job script started doing it.
_ROOT = Path(__file__).resolve().parents[1]
_bad, _scanned = [], 0
for _f in list((_ROOT / "scprofile").rglob("*.py")) + list((_ROOT / "tests").rglob("*.py")) \
        + list((_ROOT / "kernels").rglob("*.py")):
    _scanned += 1
    src = _f.read_text()
    tree = _ast.parse(src)

    # PER SCOPE, NOT PER FILE. The first version collected every import anywhere in the file, so a
    # module imported inside one function and used inside ANOTHER passed - which is exactly how
    # `manifest.layer_names` reached `_plan`, a function that does not import it, and died with a
    # NameError on a 3.2 GB object after the read. A check that cannot see scope cannot catch the
    # bug it was written for.
    def _binds(node, *, deep):
        out = set()
        stack = list(getattr(node, "body", []))
        while stack:
            n = stack.pop()
            if isinstance(n, _ast.Import):
                out |= {(a.asname or a.name).split(".")[0] for a in n.names}
            elif isinstance(n, _ast.ImportFrom):
                out |= {(a.asname or a.name) for a in n.names}
            elif isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                out.add(n.name)
                if deep:
                    stack.extend(n.body)
                continue
            elif isinstance(n, _ast.Name) and isinstance(n.ctx, _ast.Store):
                out.add(n.id)
            elif isinstance(n, _ast.arg):
                out.add(n.arg)
            stack.extend(_ast.iter_child_nodes(n))
        return out

    # LEXICAL, so a nested def sees its ENCLOSING function's imports. Walking every FunctionDef
    # against module scope alone reported `_stage()` - defined inside `_run`, which imports what
    # it uses - as three defects. A guard that fires on correct code is a guard somebody deletes,
    # and this one had just been written to catch a real bug.
    _mod_level = _binds(tree, deep=False)
    _scopes = []

    def _walk_scopes(node, visible):
        _scopes.append((node, visible))
        for child in _ast.iter_child_nodes(node):
            _descend(child, visible)

    def _descend(node, visible):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            inner = visible | _binds(node, deep=True) | {
                a.arg for a in node.args.args + node.args.kwonlyargs}
            _walk_scopes(node, inner)
        else:
            for child in _ast.iter_child_nodes(node):
                _descend(child, visible)

    _walk_scopes(tree, _mod_level)
    bound = _mod_level
    # ATTRIBUTE ACCESS IN THE AST, not a substring. A substring search matched the word
    # "manifest." in a docstring and "the report." in a comment, and a check that fires on correct
    # code is a check somebody switches off.
    _MODS = ("manifest", "merge", "report", "runner", "refs", "compat", "inputs", "figure",
             "planner", "provenance", "scaffold")
    for _scope, _visible in _scopes:
        # A nested def sees its enclosing function's imports, so attribute accesses inside one are
        # not attributed to this scope.
        _inner = {id(x) for f2 in _ast.walk(_scope)
                  if isinstance(f2, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and f2 is not _scope
                  for x in _ast.walk(f2)}
        used = {n.value.id for n in _ast.walk(_scope)
                if isinstance(n, _ast.Attribute) and isinstance(n.value, _ast.Name)
                and id(n) not in _inner}
        _where = getattr(_scope, "name", "<module>")
        for mod in _MODS:
            if mod in used and mod not in _visible:
                _bad.append(f"{_f}:{_where}() uses {mod}. without importing it")
ck("no file uses a module it did not import", not _bad, "; ".join(_bad[:3]))
# THE COUNT IS ASSERTED, NOT ASSUMED. This scan passed vacuously from any directory but the
# repository root, and a clean report from a check that opened zero files is the worst kind.
ck("and the scan actually opened the tree", _scanned >= 30, f"only {_scanned} files")

print("\nlayer_names knows what list(adata.layers) does not")
from scprofile import manifest                                                 # noqa: E402
class _L(dict):
    pass
class _Fake:
    layers = _L({None: "X", "counts": 1, "spliced": 2})
ck("the None alias for X is not a layer", manifest.layer_names(_Fake()) == ["counts", "spliced"],
   str(manifest.layer_names(_Fake())))
ck("an object with no layers gives []", manifest.layer_names(object()) == [])
_hostsrc = list((_ROOT / "scprofile").glob("*.py"))
ck("and the host was actually opened to check it", len(_hostsrc) >= 10, str(len(_hostsrc)))
ck("nothing iterates layers raw any more",
   not any("in A.layers if k" in f.read_text() or "in adata.layers if k" in f.read_text()
           for f in _hostsrc))

print("\nthe smoke fixture is not a shipped plugin")
from scprofile.kernels import discover                                         # noqa: E402
import os as _os
_os.environ.pop("SCPROFILE_KERNELS", None)
ck("perunit is absent from the default set", "perunit" not in discover(),
   "a fixture that computes nothing must never be discoverable as a method")
_os.environ["SCPROFILE_KERNELS"] = str(Path(__file__).resolve().parent / "smoke")
ck("it IS discoverable when a site asks for it", "perunit" in discover())
_os.environ.pop("SCPROFILE_KERNELS", None)

print("\nthe budget divides once, however many times it is applied")
from scprofile.kernels import _budget                                          # noqa: E402
w = [{"plugin": "velocity", "unit": None, "cores": 8},
     {"plugin": "cellcycle", "unit": None, "cores": 1}] + \
    [{"plugin": "perunit", "unit": f"S{i}", "cores": 1} for i in range(1, 5)]
_budget(w, 4)
first = [i["cores"] for i in w]
_budget(w, 4)
ck("re-budgeting an unfiltered wave changes nothing", [i["cores"] for i in w] == first,
   f"{first} became {[i['cores'] for i in w]}")
# DECLARED, CAPPED AT THE BUDGET - not a proportional share of it. This expected 2, which is
# `int(8 * 4 / 15)`: the old rule divided the budget across the whole wave as though all six
# instances ran at once. They do not; CorePool admits what fits. The old rule is why a plugin
# declaring 16 cores ran on one.
ck("velocity gets what it declared, capped at the budget", first[0] == 4, str(first))
live = [i for i in w if i["plugin"] != "perunit"]
_budget(live, 4)
ck("filtering the wave does not change what a survivor was allocated",
   [i["cores"] for i in live] == [4, 1], str([i["cores"] for i in live]))
w2 = [{"plugin": "a", "unit": None, "cores": 2}, {"plugin": "b", "unit": None, "cores": 1}]
_budget(w2, 8)
ck("an under-subscribed wave is left alone", [i["cores"] for i in w2] == [2, 1])

print("\nand the wave does not START more instances than the budget holds")
# EXECUTION.md §4 has stated `min(budget / smallest declared cores, ready)` since it was written,
# and the runner started EVERY instance of a wave at once. The two are not the same thing: the
# budget divides the share each instance is TOLD it has, and every one of 35 correctly told
# `cores: 1` still runs on a node asked for 8. On the shipped set - nine plugins, three of them
# per_unit, ten samples - that is 35 subprocesses each opening a 3 GB object.
from scprofile.kernels import concurrency                                      # noqa: E402
big = [{"plugin": "velocity", "unit": None, "cores": 8, "declared": 8}] + \
      [{"plugin": "scenic", "unit": f"S{i}", "cores": 1, "declared": 4} for i in range(10)] + \
      [{"plugin": "cellcycle", "unit": None, "cores": 1, "declared": 1}]
_budget(big, 8)
ck("every instance is told a share it can use", all(i["cores"] >= 1 for i in big))
ck("velocity is given the 8 it declared, not a share of them",
   big[0]["cores"] == 8, str(big[0]))
# ONE, because velocity declared the whole allocation and got it. The old rule flattened all
# twelve to a single core and started eight of them; this runs the 8-core instance on 8 cores and
# admits the others as it releases them. Same cores busy, but the plugin that declared 8 gets 8.
ck("but they do not all start at once", concurrency(big, 8) == 1,
   f"{concurrency(big, 8)} of {len(big)} would start on an 8-core allocation")
ck("a wave smaller than the budget starts whole", concurrency(w2, 8) == 2, str(concurrency(w2, 8)))
ck("one instance declaring more than the budget runs alone",
   concurrency([{"plugin": "x", "cores": 8, "declared": 16}], 8) == 1)
ck("an empty wave does not divide by zero", concurrency([], 8) == 1)

print("\na plugin whose output vocabulary is INFERRED also gets one cohort fit")
# SCENIC discovers its regulon set per fit, so two units' AUC columns are not the same quantity.
# Measured on ten samples: 37-111 regulons, Jaccard 0.17 between two of them. The cohort fit is
# the one comparable vocabulary; the per-unit fits are the only independent check on it, so it is
# an EXTRA instance and never a replacement.
import types as _types                                                        # noqa: E402
from scprofile.kernels import schedule as _schedule                           # noqa: E402


def _fake(name, per_unit=None, cohort=False):
    return _types.SimpleNamespace(
        name=name, needs_kernels=[], per_unit=per_unit,
        also_cohort={"why": "vocabulary is inferred per fit"} if cohort else None,
        executor={"cost": "medium", "cores": 2, "memory_gb_per_100k": None})


_units = ["s1", "s2", "s3"]
_ks = {"scenicish": _fake("scenicish", "sample", cohort=True),
       "lianaish": _fake("lianaish", "sample"),
       "wholeish": _fake("wholeish")}
_w = _schedule(list(_ks), _ks, budget_cores=8, units=_units)[0]
_by = {}
for i in _w:
    _by.setdefault(i["plugin"], []).append(i["unit"])
ck("the inferred-vocabulary plugin gets every unit AND a cohort fit",
   sorted(x or "COHORT" for x in _by["scenicish"]) == ["COHORT", "s1", "s2", "s3"],
   str(_by["scenicish"]))
ck("a fixed-vocabulary per-unit plugin gets NO extra cohort fit",
   sorted(_by["lianaish"]) == ["s1", "s2", "s3"], str(_by["lianaish"]))
ck("a whole-cohort plugin is unaffected", _by["wholeish"] == [None], str(_by["wholeish"]))
ck("the declaration carries its reason",
   "inferred" in (_ks["scenicish"].also_cohort or {}).get("why", ""))
ck("and a plugin that declares nothing has no cohort scope",
   _ks["lianaish"].also_cohort is None)

print("\nand the pool never holds more cores than the allocation, under real threads")
# The headline is an integer; the POOL is what schedules. This is the property that actually
# protects the node, and no integer can express it for a wave of mixed core counts.
import threading as _th                                                        # noqa: E402
from scprofile.kernels import CorePool                                         # noqa: E402
_pool, _held, _peak, _lk = CorePool(8), 0, 0, _th.Lock()


def _work(n):
    global _held, _peak
    got = _pool.acquire(n)
    with _lk:
        _held += got
        _peak = max(_peak, _held)
    _th.Event().wait(0.01)
    with _lk:
        _held -= got
    _pool.release(got)


_ts = [_th.Thread(target=_work, args=(c,)) for c in ([8] + [4] * 10 + [1] * 5)]
for _t in _ts:
    _t.start()
for _t in _ts:
    _t.join()
ck(f"peak residency never exceeded the budget (peak {_peak})", _peak <= 8, f"peak {_peak}")
ck("and every permit came back", _pool.free == 8, f"{_pool.free} free of 8")
ck("an instance wanting more than the budget is capped, not deadlocked",
   CorePool(8).acquire(64) == 8)

print("\nand the pool admits on MEMORY as well as cores — the dimension that kills jobs")
# PBS 677891 died at 260 GB against a 200 GB request while each of its ten instances correctly
# held one core. The core budget was satisfied throughout and could not have prevented it:
# cores bound how fast a wave runs, memory bounds whether it runs at all.
from scprofile.kernels import ResourcePool, demand, UNDECLARED_GB_PER_100K   # noqa: E402
_rp = ResourcePool(cores=50, memory_gb=200)
_h = {"c": 0.0, "m": 0.0}
_pk = {"c": 0.0, "m": 0.0}
_l2 = _th.Lock()


def _work2(need):
    g = _rp.acquire(need)
    with _l2:
        _h["c"] += g["cores"]; _h["m"] += g["memory_gb"]
        _pk["c"] = max(_pk["c"], _h["c"]); _pk["m"] = max(_pk["m"], _h["m"])
    _th.Event().wait(0.01)
    with _l2:
        _h["c"] -= g["cores"]; _h["m"] -= g["memory_gb"]
    _rp.release(g)


# scenic-shaped: cheap in cores, expensive in memory. Cores alone would admit all ten.
_t2 = [_th.Thread(target=_work2, args=({"cores": 4, "memory_gb": 40, "gpus": 0},))
       for _ in range(10)]
for _t in _t2:
    _t.start()
for _t in _t2:
    _t.join()
ck(f"peak memory within the allocation (peak {_pk['m']:.0f} GB)", _pk["m"] <= 200, str(_pk))
ck("and MEMORY was the binding constraint, not cores",
   _pk["c"] < 40, f"cores peaked at {_pk['c']:.0f}; cores alone would have admitted all ten")
ck("every permit came back in every dimension",
   _rp.free["cores"] == 50 and _rp.free["memory_gb"] == 200, str(_rp.free))
_big = ResourcePool(cores=8, memory_gb=16)
_g = _big.acquire({"cores": 64, "memory_gb": 999, "gpus": 0})
ck("an instance larger than the whole allocation runs alone, in every dimension",
   _g["cores"] == 8 and _g["memory_gb"] == 16, str(_g))
_big.release(_g)

print("\nand memory is charged against the cells the instance actually touches")
_km = _types.SimpleNamespace(executor={"cores": 8, "memory_gb_per_100k": 12, "gpus": 0})
_whole = demand({"cores": 8}, _km, 100_713)
_unit = demand({"cores": 8}, _km, 13_824)
ck("a cohort instance is charged more than a per-unit one",
   _whole["memory_gb"] > _unit["memory_gb"] * 6,
   f"{_whole['memory_gb']:.1f} vs {_unit['memory_gb']:.1f} GB")
_kn = _types.SimpleNamespace(executor={"cores": 4, "memory_gb_per_100k": None, "gpus": 0})
_d = demand({"cores": 4}, _kn, 100_000)
ck("an UNDECLARED rate is assumed, never read as zero",
   _d["memory_gb"] >= UNDECLARED_GB_PER_100K and _d["memory_assumed"] is True, str(_d))
ck("and the assumption is flagged so it can be printed",
   _d["memory_assumed"] is True)
# THE DOCUMENT MUST STATE THE RULE THE CODE IMPLEMENTS. This pinned the literal
# "budget / smallest_declared_cores", which was the proportional rule replaced on 2026-08-22;
# leaving it would have kept EXECUTION.md describing an allocator that no longer exists, and
# this check green for saying so.
_ex = (_ROOT / "docs" / "EXECUTION.md").read_text()
ck("the document states admission is by cores", "Admission is by CORES, not by count" in _ex)
ck("and names what implements it", "CorePool" in _ex)
ck("and the replaced rule is recorded as replaced, not deleted",
   "declared x budget / sum(declared)" in _ex)

print("\nthe uns payload is writable, checked before write_h5ad")
prov = merge.provenance(f, {"n_obs": 10, "compartment": None}, {"liana": ["x"]},
                        merged={"liana": {"obs": ["ccc_score"], "obsm": [],
                                          "dropped": ["obsm[X_ccc]"]}})
ck("a per-unit plugin's units are strings", prov["kernels"]["liana"]["units"] == ["s1", "s2", "s3"])
ck("a None in describe is normalised, not refused", prov["input"]["compartment"] == "")
ck("produced_obsm reports the merge, not the declaration",
   prov["kernels"]["liana"]["produced_obsm"] == [] and
   prov["kernels"]["liana"]["not_merged"] == ["obsm[X_ccc]"])
one_p = merge.provenance(one, {}, {})
ck("a plugin with no units gets [], never [None]", one_p["kernels"]["cellcycle"]["units"] == [],
   str(one_p["kernels"]["cellcycle"]["units"]))
try:
    merge._uns_safe({"k": ["a", None]})
    ck("a None inside a list is refused", False, "it was accepted")
except merge.MergeError as e:
    ck("a None inside a list is refused", "None" in str(e))

print("\nbarcodes must be unique before any reindex")
ck("there is a precondition", hasattr(merge, "_require_unique_barcodes"))
try:
    class _A:
        class _N:
            is_unique = False

            @staticmethod
            def astype(_):
                return ["a", "a", "b"]
        obs_names = _N()
    merge._require_unique_barcodes(_A())
    ck("it raises", False, "no error on duplicate barcodes")
except merge.MergeError as e:
    ck("it raises MergeError naming the cause", "not unique" in str(e))
except Exception as e:                                                   # noqa: BLE001
    ck("it raises MergeError", False, type(e).__name__)

print("\n" + ("all per-unit checks passed" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
