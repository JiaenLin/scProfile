"""The plugin declaration: the contract the builder and the maintainer both depend on.

Every check here is a way a declaration can be wrong that would otherwise be found by a user, in
a run, as a traceback. The declaration is read from source and never imported, so these run on an
interpreter with no scientific stack at all - which is also how discovery works on a cluster.

Run: python tests/test_declaration.py
"""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import declare                                                   # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def errs(spec):
    return [m for lvl, m in declare.check(spec) if lvl == "ERROR"]


GOOD = {"api": 1, "summary": "x", "cannot_show": ["y"],
        "inject": {"required": ["counts"], "optional": ["design"]},
        "provides": ["activity"],
        "config": {"n": {"type": "int", "default": 1, "help": "h"}}}

print("\na sound declaration passes")
ck("no errors", not errs(GOOD), str(errs(GOOD)))

print("\nthe contract version is a refusal, not a crash")
ck("a future api is an ERROR", errs({**GOOD, "api": 99}))
ck("and it says both versions",
   any("99" in m and str(declare.API) in m for m in errs({**GOOD, "api": 99})))
ck("a missing api is only a warning",
   not errs({k: v for k, v in GOOD.items() if k != "api"}))

print("\ncapabilities are checked against what the host can resolve")
ck("an unknown injected capability is refused", errs({**GOOD, "inject": {"required": ["wat"]}}))
ck("the refusal lists what IS known",
   any("counts" in m for m in errs({**GOOD, "inject": {"required": ["wat"]}})))
ck("providing a data capability is refused",
   errs({**GOOD, "provides": ["counts"]}),
   "a plugin cannot provide what the host reads from the object")
ck("providing a derived capability is fine", not errs({**GOOD, "provides": ["ordering"]}))
ck("every known capability explains itself",
   all(c.get("why") for c in declare.CAPABILITIES.values()))
ck("and says where the host resolves it",
   all(c.get("resolve") in ("data", "design", "derived")
       for c in declare.CAPABILITIES.values()))

print("\na declaration without limits is refused")
ck("no cannot_show is an ERROR", errs({k: v for k, v in GOOD.items() if k != "cannot_show"}))
ck("no summary is an ERROR", errs({k: v for k, v in GOOD.items() if k != "summary"}))

print("\nan environment must pin the interpreter")
ck("env without python is an ERROR", errs({**GOOD, "env": {"pip": ["x==1"]}}))
ck("an inexact pin is a warning, not a refusal",
   not errs({**GOOD, "env": {"python": "3.11", "pip": ["x>=1"]}}))
ck("and it is warned about",
   any("lower bound" in m for lvl, m in declare.check({**GOOD, "env": {"python": "3.11",
                                                                      "pip": ["x>=1"]}})))

print("\nwrapping a tool means recording having read its documentation")
ck("wraps with no upstream.docs is an ERROR",
   errs({**GOOD, "wraps": {"tool": "t"}}))
ck("with docs it passes",
   not errs({**GOOD, "wraps": {"tool": "t"}, "upstream": {"docs": "http://x"}}))

print("\nevery problem is reported, not just the first")
many = {"api": 99, "provides": ["counts"], "inject": {"required": ["wat"]}}
ck("several errors come back together", len(errs(many)) >= 4, str(len(errs(many))))

print("\nconfig is defaulted, typed and range-checked BEFORE a run")
ck("defaults are applied", declare.resolve_config(GOOD, {}) == {"n": 1})
ck("a given value wins", declare.resolve_config(GOOD, {"n": 5}) == {"n": 5})
ck("a string is coerced to the declared type", declare.resolve_config(GOOD, {"n": "7"}) == {"n": 7})
for bad, why in (({"nope": 1}, "an unknown parameter"),
                 ({"n": "abc"}, "a value of the wrong type")):
    try:
        declare.resolve_config(GOOD, bad)
        ck(f"{why} is refused", False, "it was accepted")
    except declare.DeclarationError:
        ck(f"{why} is refused", True)
RANGED = {**GOOD, "config": {"n": {"type": "int", "default": 5, "min": 1, "max": 10, "help": "h"}}}
for val in (0, 11):
    try:
        declare.resolve_config(RANGED, {"n": val})
        ck(f"n={val} is refused", False, "it was accepted")
    except declare.DeclarationError as e:
        ck(f"n={val} is refused", "declared" in str(e))
ck("a config key with no help is warned about",
   any("no help" in m for lvl, m in declare.check(
       {**GOOD, "config": {"n": {"type": "int", "default": 1}}})))

print("\nthe shipped plugin holds to all of it")
pp = Path(__file__).resolve().parents[1] / "kernels" / "decoupler.py"
spec = importlib.util.spec_from_file_location("dcp", pp)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
P = mod.PLUGIN
ck("it declares an api", P.get("api") == declare.API)
ck("its declaration is clean", not errs(P), str(errs(P)))
ck("it injects capabilities, required and optional",
   set(P["inject"]) == {"required", "optional"})
ck("it provides a capability", P["provides"] == ["activity"])
# THE POINT OF INJECTION: the host checks, so the plugin does not.
src = pp.read_text()
run_src = src[src.index("def run("):src.index("def selftest(")]
ck("run() contains no prerequisite checking",
   "if not ctx.organism" not in run_src and "if not ctx.keys" not in run_src, "it still checks")
ck("run() reads config without validating it",
   "ctx.config[" in run_src and "raise" not in run_src)

print("\nthe CONTRACT'S own dependency is declared, not assumed")
# `_entry.py` reads the object with `anndata.read_h5ad` BEFORE a plugin is called, so a python
# plugin whose environment has no anndata cannot run at all - and the failure arrives as "this
# kernel's interpreter cannot read the object", which reads as a problem with the OBJECT.
# Measured on PBS 677677: ten instances of scenic reported exactly that, and the cause was
# `No module named 'anndata'`. Two more plugins - abundance and de - had the same gap and worked
# only because they SHARE an environment with plugins that name it, which is accidental.
ck("the entrypoint reads with anndata, not scanpy",
   "import anndata as ad" in (Path(__file__).resolve().parents[1]
                              / "scprofile" / "_entry.py").read_text())
_bad = declare.check({"api": 1, "summary": "x", "cannot_show": ["y"],
                      "requires": {"python": ">=3.10", "packages": {"numpy": ">=1"}}})
ck("a python requirement with no anndata is an ERROR",
   any(l == "ERROR" and "anndata" in m for l, m in _bad), str(_bad))
_ok = declare.check({"api": 1, "summary": "x", "cannot_show": ["y"],
                     "requires": {"python": ">=3.10",
                                  "packages": {"numpy": ">=1", "anndata": ">=0.10,<0.12"}}})
ck("and with it, it is not", not any("anndata" in m for _l, m in _ok), str(_ok))
_r = declare.check({"api": 1, "summary": "x", "cannot_show": ["y"],
                    "requires": {"conda": {"r-base": "4.3"}, "r": ["a/b==1"]}})
ck("a requirement that brings no python packages is not asked for it",
   not any("anndata" in m for _l, m in _r), str(_r))
from scprofile.kernels import discover as _disc                                 # noqa: E402
for _n, _k in sorted(_disc().items()):
    if (_k.spec.get("requires") or {}).get("packages"):
        ck(f"{_n} declares it", "anndata" in _k.spec["requires"]["packages"])

print("\n" + ("the declaration holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
