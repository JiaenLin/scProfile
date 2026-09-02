"""The plugin declaration: the contract the builder and the maintainer both depend on.

Every check here is a way a declaration can be wrong that would otherwise be found by a user, in
a run, as a traceback. The declaration is read from source and never imported, so these run on an
interpreter with no scientific stack at all - which is also how discovery works on a cluster.

Run: python tests/test_declaration.py
"""
import importlib.util
import re
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
# THE INTENT IS "run() DOES NOT RAISE", AND THAT IS AN AST QUESTION, NOT A SPELLING ONE.
# This was `"raise" not in run_src` - a substring search over the function's whole source,
# COMMENTS INCLUDED. A comment explaining a bug that had been fixed used the word "raised" and
# failed the check, which is a gate firing on correct behaviour: the kind that gets switched off
# rather than obeyed. `ast` asks what the code does and is blind to what the prose says about it.
import ast as _ast_run                                                        # noqa: E402
_run_tree = _ast_run.parse(run_src)
_raises = [n for n in _ast_run.walk(_run_tree) if isinstance(n, _ast_run.Raise)]
ck("run() reads config without validating it",
   "ctx.config[" in run_src and not _raises,
   f"{len(_raises)} raise statement(s) at line(s) "
   f"{[n.lineno for n in _raises[:4]]} within run()")

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

print("\nevery declared version constraint is a constraint pip will accept")
# A SPECIFIER THAT DOES NOT PARSE IS NOT A PIN, and it does not announce itself as one: the
# builder passes it through, pip rejects the whole install, and the message names pip's parser
# rather than the plugin that wrote it. Ceilings with no floor are legitimate and must stay so -
# a ceiling is what you declare when you have MEASURED which version breaks and have measured no
# floor, and turning that into "declare both or neither" would push people into inventing floors.
try:
    from packaging.specifiers import SpecifierSet as _Spec
except ImportError:
    _Spec = None
ck("the specifier parser is available to check with", _Spec is not None,
   "install `packaging` or this check proves nothing")
if _Spec is not None:
    _unparseable = []
    _seen = 0
    for _n, _k in sorted(_disc().items()):
        for _pkg, _spec in ((_k.spec.get("requires") or {}).get("packages") or {}).items():
            _seen += 1
            try:
                _Spec(str(_spec))
            except Exception as _e:
                _unparseable.append(f"{_n}:{_pkg}={_spec!r} ({_e})")
    ck(f"all {_seen} package constraint(s) across every plugin parse", not _unparseable,
       "; ".join(_unparseable))
    ck("and the check actually read some", _seen >= 20, f"only {_seen}")
    ck("a ceiling with no floor is accepted, because that is what a measured break looks like",
       bool(_Spec("<0.4")))
    def _rejects(text):
        try:
            _Spec(text)
        except Exception:
            return True
        return False

    ck("and genuine nonsense is still caught, so the check above can fail",
       _rejects("=<0.4") and _rejects("not-a-version") and not _rejects(">=1,<2"))

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
# WHAT THE ROADMAP DOCUMENTS IS WHAT THE REPOSITORY SHIPS - NOT WHAT IS ON THE SEARCH PATH.
#
# `discover()` deliberately includes $SCPROFILE_KERNELS, because adding a method without forking
# is the whole point of that variable. Measuring "what ships" through it counts somebody else's
# plugin as ours, so this check failed on the feature working: the batch job points
# $SCPROFILE_KERNELS at `tests/smoke/plugins`, whose `silhouette` exists precisely to prove that
# a plugin dropped in from OUTSIDE the repository loads. It was read as a tenth shipped method
# and failed this suite in EVERY job, while passing on any machine with the variable unset -
# which is how it went unnoticed: the workstation said green and the cluster said red about the
# same commit.
import os as _os3                                                               # noqa: E402


def _repo_ships():
    """What the REPOSITORY ships, measured with the site search path out of the way."""
    _keep = _os3.environ.pop("SCPROFILE_KERNELS", None)
    try:
        return set(_disc())
    finally:
        if _keep is not None:
            _os3.environ["SCPROFILE_KERNELS"] = _keep


_ships = _repo_ships()
# AND THE CHECK IS FALSIFIABLE ON ANY MACHINE, not only on one where the variable happens to be
# set. Point it at the smoke plugins deliberately and measure again: the shipped set must not
# move, and `discover()` must still SEE the site plugin - otherwise this "fix" would have been
# to break the feature rather than to stop miscounting it.
_smoke = Path(__file__).resolve().parent / "smoke" / "plugins"
if _smoke.is_dir():
    _prev = _os3.environ.get("SCPROFILE_KERNELS")
    _os3.environ["SCPROFILE_KERNELS"] = str(_smoke)
    try:
        ck("a plugin on $SCPROFILE_KERNELS is not counted as one the repository ships",
           _repo_ships() == _ships, f"the shipped set moved: {sorted(_repo_ships() ^ _ships)}")
        ck("and discover() still finds it, so the search path still works",
           bool(set(_disc()) - _ships), "nothing extra was discovered from the site directory")
    finally:
        if _prev is None:
            _os3.environ.pop("SCPROFILE_KERNELS", None)
        else:
            _os3.environ["SCPROFILE_KERNELS"] = _prev
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
import pathlib as _pathlib                                                      # noqa: E402
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

# THE GUARD ABOVE COMPARED TWO STATEMENTS INSIDE ONE MODULE AND MISSED THE ONE THAT DRIFTED.
# Both of its directions read `declare`; the consumer that had gone out of step was the
# REPORTER, in report.py, which read `unit_network` while the checker warned - on the only two
# plugins using it - that "the reporter ignores them". A guard that watches the checker watch
# itself will pass every time the checker is self-consistent and wrong.
#
# So the scan is now over the WHOLE PACKAGE, for the one accessor every consumer goes through.
_pkg = _pathlib.Path(declare.__file__).parent
_srcs = {f.name: f.read_text(encoding="utf-8") for f in sorted(_pkg.glob("*.py"))}
_consumed = {}
for _fn, _src in _srcs.items():
    for _n in _ast.walk(_ast.parse(_src)):
        if (isinstance(_n, _ast.Call)
                and getattr(_n.func, "attr", getattr(_n.func, "id", "")) == "report_get"
                and len(_n.args) >= 2 and isinstance(_n.args[1], _ast.Constant)):
            _consumed.setdefault(_n.args[1].value, set()).add(_fn)

ck("every report key a CONSUMER reads is a key the checker allows",
   set(_consumed) <= set(declare.REPORT_KEYS),
   str(sorted((k, sorted(v)) for k, v in _consumed.items()
              if k not in set(declare.REPORT_KEYS))))
ck("the reporter is one of those consumers, so the scan covers the module that drifted",
   any("report.py" in v for v in _consumed.values()),
   "no report_get call in report.py — the accessor was bypassed")
ck("`unit_network`, the key this guard was widened for, is read through the accessor",
   "report.py" in _consumed.get("unit_network", set()),
   str(sorted(_consumed.get("unit_network", ()))))

# AND THE BACK DOOR IS CLOSED. An accessor nobody is obliged to use is a convention, and a
# convention is what the last two versions of this guard were. A consumer reaching into the
# block directly can read a key the checker has never heard of, which is exactly the defect.
#
# BY THE SHAPE, NOT BY THE WORD `spec`. The first version of this check grepped for `spec.get(`
# and named ten modules, because `spec` in this package is also a reference spec, a plugin
# declaration and a resolved requirement - a gate red on eight correct modules, which is the
# same failure as the reference-tier gate two fixes ago and would have been switched off just
# as fast. What identifies a read of the REPORT BLOCK is the receiver (`spec` or `block`, the
# two names the block travels under) together with a key this module governs. `p.get("figures")`
# in report.py reads the PAYLOAD's emitted figures and is untouched by any of this.
def _receiver(node):
    """The name a `.get` is called on, seeing through `(spec or {})`."""
    v = node.func.value
    if isinstance(v, _ast.BoolOp) and v.values:
        v = v.values[0]
    return getattr(v, "id", "")

_direct = []
for _fn, _src in _srcs.items():
    if _fn == "declare.py":            # the checker reads the block; that is its job
        continue
    for _n in _ast.walk(_ast.parse(_src)):
        if (isinstance(_n, _ast.Call) and getattr(_n.func, "attr", "") == "get"
                and _receiver(_n) in ("spec", "block")
                and _n.args and isinstance(_n.args[0], _ast.Constant)
                and _n.args[0].value in set(declare.REPORT_KEYS)):
            _direct.append(f"{_fn}:{_n.lineno} {_n.args[0].value}")
ck("no module reads a plugin's report block around the accessor",
   not _direct, f"{sorted(_direct)} reach into the block directly")

# EVERY CHECK MUST BE ABLE TO FAIL. An unlisted key must raise at the call, not warn later.
try:
    declare.report_get({"nope": 1}, "nope")
    _raised = False
except KeyError:
    _raised = True
ck("report_get REFUSES a key that is not declared", _raised,
   "an undeclared key was read without complaint, which is how the drift starts")

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

# THE HOST OPENS THE OBJECT; A PLUGIN ONLY EVER SEES THE COPY IT IS HANDED. `compat` exists so an
# older plugin can still read that copy - nothing performs the same service for the host, so a host
# floor BELOW a plugin floor is a tool that refuses, at the first step, an object its own plugins
# were declared able to process. The two are declared in different files, so nothing but this
# connects them. It drifted exactly that way and was found on a real run: every kernel said
# `anndata >=0.10,<0.12` and the host extra said a bare `anndata>=0.10`, and the install that
# satisfied both could not open the object at all.
_root = Path(__file__).resolve().parents[1]


def _floor(spec):
    m = re.search(r">=\s*([0-9]+(?:\.[0-9]+)*)", spec or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


_host = None
for _line in (_root / "pyproject.toml").read_text().splitlines():
    if _line.startswith("run = "):
        _m = re.search(r'"anndata([^"]*)"', _line)
        if _m:
            _host = _floor(_m.group(1))
_worst, _who = None, None
for _f in sorted((_root / "kernels").glob("*.py")):
    _m = re.search(r'"anndata"\s*:\s*"([^"]+)"', _f.read_text())
    if not _m:
        continue
    _fl = _floor(_m.group(1))
    if _fl and (_worst is None or _fl > _worst):
        _worst, _who = _fl, _f.name
ck("the host declares an anndata floor at all", _host is not None)
ck("the host's anndata floor is not below any plugin's",
   bool(_host and _worst and _host >= _worst),
   f"host >={_host}, {_who} >={_worst} - the host reads the object BEFORE any plugin does")

print("\na reference is checked against the tier it declares")
# THE CHECKER DEMANDED A URL AND A DIGEST FROM A DATABASE THAT SHIPS INSIDE AN R PACKAGE.
# `validate_references` was written when every reference was a file this tool downloads, and it
# never learned about the tiers `refs.status()` has honoured since they were added. The result
# was 12 ERRORs across three of the nine shipped plugins - on SIX OF THE SIX references in the
# tree, every one of them correctly declared - each reported as "a defect that would produce a
# plausible wrong answer". A gate red on everything correct teaches its reader to skip it, and
# this project has written that lesson down twice already.
from scprofile import refs as _refs, validate as _V                             # noqa: E402


class _K:
    """The two attributes `validate_references` touches, and nothing else."""

    name = "t"
    path = Path("/nonexistent")

    def __init__(self, refs):
        self._refs = refs

    def references(self, organism=None):
        return self._refs


def _lv(refs, level):
    return [f.check for f in _V.validate_references(_K(refs)) if f.level == level]


_FETCH_OK = {"r": {"tier": "fetch", "url": "https://x/y.gz", "sha256": "a" * 64, "size": "1 GB"}}
ck("a downloadable reference with its url and digest passes", not _lv(_FETCH_OK, "ERROR"),
   str(_lv(_FETCH_OK, "ERROR")))
ck("and one missing its digest is STILL an error — the check that mattered still fires",
   len(_lv({"r": {**_FETCH_OK["r"], "sha256": ""}}, "ERROR")) == 1)
ck("and a truncated digest is still caught",
   len(_lv({"r": {**_FETCH_OK["r"], "sha256": "abc"}}, "ERROR")) == 1)

_BUNDLED = {"r": {"tier": "bundled", "package": "CellChat", "source": "https://github.com/x"}}
ck("a bundled reference is not asked for a url or a digest it cannot have",
   not _lv(_BUNDLED, "ERROR"), str(_lv(_BUNDLED, "ERROR")))
ck("but one naming no package IS an error — nothing would pin it at all",
   len(_lv({"r": {"tier": "bundled"}}, "ERROR")) == 1)

_RUNTIME = {"r": {"tier": "runtime", "source": "OmniPath"}}
ck("a run-time reference is not asked for a digest nothing can compute",
   not _lv(_RUNTIME, "ERROR"), str(_lv(_RUNTIME, "ERROR")))
ck("and it WARNS that the compute node needs the network, which is the real hazard",
   any("run time" in c for c in _lv(_RUNTIME, "WARN")), str(_lv(_RUNTIME, "WARN")))
ck("a misspelt tier is an error, not silently treated as a download",
   len(_lv({"r": {"tier": "bundeld", "package": "p"}}, "ERROR")) >= 1)

ck("the tier vocabulary is stated once, not restated by the checker",
   'TIERS = (' in (Path(_refs.__file__)).read_text(encoding="utf-8")
   and "_R.TIERS" in Path(_V.__file__).read_text(encoding="utf-8"),
   "validate carries its own copy of the tier list")
ck("and the checker defaults a missing tier exactly as the status reader does",
   _refs.tier_of({}) == _refs.DEFAULT_TIER == "fetch")

# EVERY SHIPPED PLUGIN, NOT A FIXTURE. The convenient fixture hides the bug it was built to
# catch: nothing in this suite read the kernels the tool actually ships, so twelve errors on
# three of them survived a green run of everything here.
print("\nevery shipped plugin validates")
from scprofile.kernels import discover                                          # noqa: E402

for _n, _k in sorted(discover().items()):
    _f = _V.validate_plugin(_k) + _V.validate_references(_k)
    _bad = [x.check for x in _f if x.level == "ERROR"]
    ck(f"{_n} declares itself without error", not _bad, "; ".join(_bad))

print("\n" + ("the declaration holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
