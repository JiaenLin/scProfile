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

print("\nthe MAKER produces a plugin the tool accepts, on the first generation")
# THE PLUGIN IS WRITTEN ONCE AND SHIPS PREBUILT, so what the maker emits decides what the builder
# and planner get to read for the life of that plugin. A skeleton that starts with gaps is a
# skeleton whose gaps are inherited: eight of the nine plugins here declared no memory rate, and
# the allocator guessed for all eight.
import ast as _ast                                                             # noqa: E402
from scprofile.onefile import render as _render                                # noqa: E402
_src = _render("mymethod", "what it gives you", "mytool")
_ast.parse(_src)
_ns = {}
exec(compile(_src, "generated", "exec"), _ns)                                  # noqa: S102
_P = _ns.get("PLUGIN") or {}
ck("the generated plugin is valid Python", bool(_P))
ck("and passes the declaration check with no ERROR",
   not [m for lv, m in declare.check(_P, "mymethod") if lv == "ERROR"],
   str(declare.check(_P, "mymethod")))
ck("and no WARN either - it starts declaration-complete",
   not declare.check(_P, "mymethod"), str(declare.check(_P, "mymethod")))
for _f in ("api", "summary", "cannot_show", "inject", "produces", "requires",
           "cores", "memory_gb_per_100k"):
    ck(f"the skeleton declares {_f}", _f in _P)
ck("run and selftest are both present", callable(_ns.get("run")) and callable(_ns.get("selftest")))
# and they REFUSE rather than returning nothing, so an unfinished plugin cannot look like one
# that ran and found no result
for _fn in ("run", "selftest"):
    try:
        _ns[_fn](None)
        ck(f"{_fn} refuses until it is written", False, "it returned instead of raising")
    except NotImplementedError:
        ck(f"{_fn} refuses until it is written", True)
    except Exception as _e:                                                    # noqa: BLE001
        ck(f"{_fn} refuses until it is written", False, f"raised {type(_e).__name__}")

print("\nthe roadmap's SHIPPED table is checked against what actually ships")
# A COUNT IN A DOCUMENT IS READ AS A FACT BY PEOPLE WHO WILL NOT OPEN THE SOURCE, and this one
# travelled: `ROADMAP.md` listed two shipped kernels for as long as it took to build the other
# seven, and a downstream project's index copied "ships `cellcycle` and `velocity` only" and
# blocked a stage on a plugin that had been shipping for days.
#
# So the list is MEASURED rather than maintained. Both directions: a plugin that ships and is
# not listed understates the tool, and a name listed that does not ship promises what is not
# there - and the second is the one somebody plans work around.
import re as _re2                                                               # noqa: E402
from scprofile.kernels import discover as _disc                                 # noqa: E402

_rmp = Path(__file__).resolve().parents[1] / "ROADMAP.md"
try:
    _rm = _rmp.read_text(encoding="utf-8")
except OSError as _e:
    ck("ROADMAP.md is readable", False, str(_e))
    _rm = ""
_t0 = _rm.split("## Tier 0", 1)[-1].split("## Tier 1", 1)[0]
_listed = set(_re2.findall(r"^\| `([a-z_0-9]+)` \|", _t0, _re2.M))
_ships = set(_disc())
ck("every shipped plugin is in the roadmap's Tier 0",
   not (_ships - _listed), f"ships and unlisted: {sorted(_ships - _listed)}")
ck("and nothing is listed as shipped that does not ship",
   not (_listed - _ships), f"listed and absent: {sorted(_listed - _ships)}")
# AND THE PROSE COUNT BESIDE IT. "All nine" and a table of eight is the same defect one line up.
_words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
_claim = _re2.search(r"\*\*All ([a-z]+),", _t0)
ck("the count claimed in prose matches the table",
   bool(_claim) and _words.get(_claim.group(1)) == len(_listed),
   f"prose says {_claim.group(1) if _claim else '?'}, table has {len(_listed)}")

print("\nthe keys a report block may carry are stated once, not twice")
# THE CHECKER DEMANDED A KEY AND THEN WARNED THAT THE KEY WAS UNKNOWN. The allowed-key set was a
# literal inside the unknown-key check, written before `unit_metrics` existed and never updated
# when it became a REQUIREMENT of every per-unit plugin - so three shipped plugins carried a
# permanent warning saying the reporter ignores a key the reporter uses. Two statements of one
# fact, drifting, in the same function.
import ast as _ast                                                              # noqa: E402
import inspect as _insp                                                         # noqa: E402

_read = {n.args[0].value
         for n in _ast.walk(_ast.parse(_insp.getsource(declare._check_report)))
         if isinstance(n, _ast.Call)
         and getattr(n.func, "attr", "") == "get"
         and getattr(n.func.value, "id", "") == "block"
         and n.args and isinstance(n.args[0], _ast.Constant)}
ck("every key the checker reads is a key it allows",
   _read <= set(declare.REPORT_KEYS), str(sorted(_read - set(declare.REPORT_KEYS))))
# AND THE OTHER DIRECTION: a key allowed and never read is a setting that does nothing.
_elsewhere = _insp.getsource(declare)
ck("and every key it allows is read somewhere",
   all(f'"{k}"' in _elsewhere for k in declare.REPORT_KEYS),
   str([k for k in declare.REPORT_KEYS if f'"{k}"' not in _elsewhere]))

_ok = {"name": "x", "summary": "s", "cannot_show": ["a"], "api": 1, "per_unit": "sample",
       "executor": {"memory_gb_per_100k": 1},
       "report": {"figures": [{"id": "f", "question": "q?", "shows": "diagnostic",
                               "source": "t.csv"}],
                  "unit_metrics": [{"id": "m", "question": "q?"}]}}
ck("a per-unit plugin declaring what it is required to declare gets no warning",
   declare.check(_ok) == [], str(declare.check(_ok)))
ck("and a key that really is unknown is still reported",
   any("unknown" in m for _l, m in
       declare.check({**_ok, "report": {**_ok["report"], "nonsense": 1}})))

print("\na plugin cannot declare more panels than a page will carry")
# THE PLAN AND THE RUN AGREE BY CONSTRUCTION, extended to the report. A cohort plugin's page is
# its own figures PLUS the per-arm panels the host adds, and only the second half was ever
# bounded. One shipped plugin declares 9 and renders exactly 12 - the standard's cap, with zero
# headroom - and the only way its maintainer could have learned that was to run the job.
from scprofile.report import BY_ARM_PANEL_CAP as _CAP                           # noqa: E402
from scprofile.standard import MAX_FIGURES as _MAXF                             # noqa: E402

_budget = _MAXF - _CAP


def _figs(n):
    return [{"id": f"f{i}", "question": "q?", "shows": "diagnostic", "source": f"t{i}.csv"}
            for i in range(n)]


_base = {"name": "x", "summary": "s", "cannot_show": ["a"], "api": 1,
         "executor": {"memory_gb_per_100k": 1}}
ck("a cohort plugin at the budget is accepted",
   not errs({**_base, "report": {"figures": _figs(_budget)}}), str(_budget))
ck("and one panel over it is refused BEFORE the job",
   any("budget" in m or "at most" in m
       for m in errs({**_base, "report": {"figures": _figs(_budget + 1)}})),
   str(errs({**_base, "report": {"figures": _figs(_budget + 1)}})))
# A PER-UNIT PLUGIN'S PANELS GO TO THE APPENDIX, which is exempt from the page cap by design -
# per-sample panels ARE repeats and there are many, which is why they were moved off the page a
# reader reads. Holding them to the cohort budget would refuse them for being what they are.
ck("a per-unit plugin is not held to the cohort page budget",
   not errs({**_base, "per_unit": "sample",
             "report": {"figures": _figs(_budget + 4),
                        "unit_metrics": [{"id": "m", "question": "q?"}]}}))
# ONE STATEMENT OF EACH NUMBER. The budget is arithmetic over two constants owned by the two
# modules that enforce them; restating either here is the defect this file already caught once.
import inspect as _i2                                                           # noqa: E402
_dsrc = _i2.getsource(declare)
ck("the page cap is imported, not restated", f"= {_MAXF}" not in _dsrc.split("MAX_FIGURES")[0][-40:])
ck("and so is the host's panel allowance", "BY_ARM_PANEL_CAP" in _dsrc)

print("\n" + ("the declaration holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
