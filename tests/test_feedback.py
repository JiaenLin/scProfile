"""The downstream-to-upstream loop: a failure is routed to the layer that owns it.

A failure in a run has a cause in exactly one layer, and the layers have completely different
remedies. Reporting them all as "plugin X failed" makes the user read a traceback and guess -
which is what this replaces.

Run: python tests/test_feedback.py
"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import feedback as FB                                            # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


print("\nan environment failure is repairable, and says how")
for err in ("ModuleNotFoundError: No module named 'scvelo'",
            "ImportError: cannot import name 'x' from 'y'",
            "undefined symbol: _ZN5arrow",
            "ERROR: package version 1.2 is required, but you have 3.4"):
    d = FB.diagnose("velocity", err, prefix="/env")
    ck(f"{err[:34]!r} -> environment", d.layer == FB.ENVIRONMENT, d.layer)
    ck("   repairable", d.repairable)
    ck("   with a --force rebuild", "--force" in d.action, d.action)

print("\nan API failure belongs to the DECLARATION, and is not rebuilt")
for err in ("TypeError: score_genes() got multiple values for keyword argument 'ctrl_size'",
            "AttributeError: module 'scvelo' has no attribute 'moments'",
            "TypeError: run_ulm() got an unexpected keyword argument 'net'"):
    d = FB.diagnose("k", err)
    ck(f"{err[:34]!r} -> declaration", d.layer == FB.DECLARATION, d.layer)
    ck("   NOT auto-repaired", not d.repairable,
       "rebuilding cannot fix a call that is written wrong")
ck("and it says the selftest should have caught it",
   "selftest" in FB.diagnose("k", "got multiple values for keyword argument 'x'").why)

print("\nrunning out of resources is a METHOD outcome, not a defect")
for err, word in (("MemoryError", "memory"), ("Killed", "memory"),
                  ("TimeoutExpired: timed out after 900s", "timeout")):
    d = FB.diagnose("k", err)
    ck(f"{err[:20]!r} -> method", d.layer == FB.METHOD, d.layer)
    ck("   not repairable by rebuilding", not d.repairable)
ck("out of memory is described as not a defect",
   "Not a defect" in FB.diagnose("k", "MemoryError").why)

print("\na contract failure is the HOST's, not the plugin's or the user's")
d = FB.diagnose("k", "ContractError: out.json missing required field")
ck("-> host", d.layer == FB.HOST, d.layer)
ck("and says so plainly", "this host" in d.why)

print("\nan unknown failure is NOT guessed at")
d = FB.diagnose("k", "RuntimeError: something nobody has seen")
ck("the layer is not asserted", "not established" in d.why)
ck("and the evidence is carried", "nobody has seen" in d.evidence)
ck("not marked repairable", not d.repairable)

print("\ndeclaration drift is found by comparing what it DID with what it SAID")
class K:
    def __init__(self, produces):
        self.spec = {"produces": produces}

d = FB.declaration_drift(K(["obs[phase]", "tables/x.csv"]),
                         {"status": "ok", "obs": {"phase": "p"},
                          "tables": ["out/x.csv"]})
ck("a plugin that did what it said has no drift", not d, str(d))

d = FB.declaration_drift(K(["obs[phase]", "obsm[X_z]"]), {"status": "ok", "obs": {"phase": "p"}})
ck("a declared output that was not emitted is a defect", len(d) == 1, str(d))
ck("owned by the declaration layer", d[0].layer == FB.DECLARATION)
ck("and it says the next reader will believe it", "next reader" in d[0].why)

d = FB.declaration_drift(K(["obs[phase]"]),
                         {"status": "ok", "obs": {"phase": "p", "extra": "e"}})
ck("an undeclared output is a defect", len(d) == 1, str(d))
ck("and it says why that matters",
   "cannot_show" in d[0].why, "an undeclared output is covered by no limit")

d = FB.declaration_drift(K(["obs[phase]"]), {"status": "refused", "obs": {}})
ck("a REFUSAL is allowed to produce nothing", not d,
   "it said why it produced nothing; that is a result")

d = FB.declaration_drift(K([]), {"status": "ok", "obs": {"anything": "x"}})
ck("a plugin declaring no produces is not policed", not d)

print("\na rule the host states must be a rule the host checks")
# The contract says a sentinel - an annotator declining to call a cell type - stays in the object
# and leaves the STATISTICS. The host printed that as a guarantee in every plugin's caveats and
# could not deliver it: only the plugin knows what it groups by. The first plugin supplied from
# outside this repository then shipped a table whose worst-scoring population was `UNRESOLVED`,
# under a caveat saying sentinels were not treated as populations. Offer the mechanism, then
# CHECK - an unchecked rule holds until somebody writes a plugin.
import tempfile                                                                 # noqa: E402
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "tables").mkdir()
    (d / "tables" / "by_label.csv").write_text(
        "label,mean\nUNRESOLVED,-0.14\nFibroblast,0.31\n", encoding="utf-8")
    (d / "tables" / "clean.csv").write_text(
        "label,mean\nFibroblast,0.31\n", encoding="utf-8")
    pay = {"kernel": "k", "tables": ["tables/by_label.csv"]}
    got = FB.sentinel_as_population(d, pay, ("EXCLUDED", "UNRESOLVED"))
    ck("a sentinel used as a group is caught", len(got) == 1, str(got))
    ck("it is a DECLARATION defect - a maintainer changes the plugin",
       got and got[0].layer == FB.DECLARATION)
    ck("it names the sentinel and the file",
       got and "UNRESOLVED" in got[0].why and "by_label.csv" in got[0].why)
    ck("it names the mechanism rather than only the fault",
       got and "real_cells()" in got[0].why)
    ck("a clean table is not flagged",
       not FB.sentinel_as_population(d, {"kernel": "k", "tables": ["tables/clean.csv"]},
                                     ("UNRESOLVED",)))
    ck("no declared sentinels means nothing to check",
       not FB.sentinel_as_population(d, pay, ()))
    ck("a header matching a sentinel is not a group",
       not FB.sentinel_as_population(d, {"kernel": "k", "tables": ["tables/clean.csv"]},
                                     ("label",)))
    ck("a table the plugin declared and did not write is skipped, not raised",
       FB.sentinel_as_population(d, {"kernel": "k", "tables": ["tables/gone.csv"]},
                                 ("UNRESOLVED",)) == [])

from scprofile.plugin import Context                                            # noqa: E402
ck("the host offers the mechanism on Context", hasattr(Context, "real_cells"))
ck("and it is documented as the host answering once for every plugin",
   "every plugin" in (Context.real_cells.__doc__ or ""))

print("\nthe affordance four plugins misread is now gated, not merely documented")
# `ctx.populations()` returns (mask, groups). FOUR plugins destructured it as (populations,
# dropped) - which is what the NAME asks for and not what it gives - and the wrong reading is
# silent in the worst way: `len(pops)` is the cell count, so a refusal that should fire never
# does; `if dropped:` asks the truth value of an array and raises. Four occurrences of one
# mistake is a statement about the affordance.
from scprofile.plugin import Populations                                        # noqa: E402
_p = Populations([True, True, False], ["A", "B"], ["A", "B"], ["UNRESOLVED"])
_m, _g = _p
ck("it still unpacks as (mask, groups)", list(_m) == [True, True, False] and list(_g) == ["A", "B"])
ck("and now answers what the wrong readers wanted",
   _p.names == ["A", "B"] and _p.dropped == ["UNRESOLVED"], f"{_p.names} {_p.dropped}")
ck("mask and groups are also reachable by name",
   list(_p.mask) == list(_m) and list(_p.groups) == list(_g))

import tempfile as _tf2, types as _ty2                                          # noqa: E402
from scprofile import validate as _V                                            # noqa: E402
with _tf2.TemporaryDirectory() as _d2:
    _f2 = Path(_d2) / "badpop.py"
    _f2.write_text('PLUGIN = {"api": 1, "summary": "x", "cannot_show": ["y"]}\n'
                   'def run(ctx):\n    pops, dropped = ctx.populations()\n'
                   'def selftest(ctx):\n    pass\n')
    from scprofile.kernels import FileKernel as _FK                             # noqa: E402
    _fnd = _V.validate_plugin(_FK(_f2))
    ck("the wrong destructuring is an ERROR",
       any(x.level == "ERROR" and "populations()" in x.check for x in _fnd), str(_fnd))
    _f2.write_text('PLUGIN = {"api": 1, "summary": "x", "cannot_show": ["y"]}\n'
                   'def run(ctx):\n    mask, groups = ctx.populations()\n'
                   'def selftest(ctx):\n    pass\n')
    _fnd = _V.validate_plugin(_FK(_f2))
    ck("and the correct one is not",
       not any("populations()" in x.check for x in _fnd), str(_fnd))

print("\nthe loop is wired into the run, and a retry is never silent")
from scprofile import cli                                                       # noqa: E402
src = inspect.getsource(cli._run)
ck("a failure is diagnosed", "FB.diagnose(" in src)
ck("an environment failure triggers a rebuild", "REPAIRING" in src)
ck("it repairs each plugin at most once", "name not in repaired" in src)
ck("a recovery after rebuild is REPORTED as drift",
   "RECOVERED after rebuild" in src and "had DRIFTED" in src)
ck("a second failure is not blamed on the environment",
   "The environment is not the cause" in src)
ck("drift is checked on every success", "declaration_drift(" in src)
ck("and the sentinel rule with it", "sentinel_as_population(" in src)
ck("findings reach report.json", '"diagnoses"' in src)
ck("and which plugins were repaired", '"repaired"' in src)

print("\n" + ("the loop holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
