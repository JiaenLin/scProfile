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

print("\na singular design is a METHOD outcome and is named as one")
# PBS 677677: `~ a + b + c + d` on a cohort where one technical factor took one value for every
# sample in one arm of a biological factor and another value for the rest. pydeseq2's IRLS inverted the model matrix and
# raised `numpy.linalg.LinAlgError: Singular matrix`, which the loop could only report as "no
# known failure signature matched". True, and it tells a user nothing about their experiment.
d = FB.diagnose("de", "numpy.linalg.LinAlgError: Singular matrix")
ck("-> method", d.layer == FB.METHOD, d.layer)
ck("not repairable by rebuilding", not d.repairable)
ck("it says the terms are collinear", "collinear" in d.why)
ck("and that it is the DESIGN, not the data", "design table" in d.why)

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

print("\na tool that moved mid-run is neither the plugin nor its environment")
# Measured on PBS 683096: six instances refused because the tool directory moved mid-run, and
# every one was classified `[method] ... the plugin is the place to start`. The plugin was
# untouched. A diagnosis that names the wrong layer is worse than none, because it is acted on.
_d = FB.diagnose("cellchat",
                "cellchat[S1]: THE TOOL CHANGED WHILE THIS RUN WAS IN PROGRESS "
                "(kernels/cellchat.py, scprofile/plugin.py)")
_layer = _d.get("layer") if isinstance(_d, dict) else getattr(_d, "layer", None)
_rep = _d.get("repairable") if isinstance(_d, dict) else getattr(_d, "repairable", None)
_why = str(_d.get("why") if isinstance(_d, dict) else getattr(_d, "why", ""))
ck("it is classified as a HOST failure", _layer == FB.HOST, str(_layer))
ck("and not as the method's", _layer != FB.METHOD)
ck("it is NOT auto-repairable - rebuilding an environment fixes nothing here", _rep is False)
ck("and it says outright not to debug the plugin",
   "not debug" in _why.lower() or "NOT a fault in the plugin" in _why, _why[:80])
ck("and names the remedy: finish or kill the run before updating",
   "before updating" in _why, _why[:80])

print("\na declaration that under-sizes what the run cost is a defect the run can prove")
# THE ONE FAILURE THAT PRODUCES NO EVIDENCE. A kernel killed by the OOM killer at its largest
# step leaves no traceback, so nothing downstream can classify it - which is why this is caught
# from a run that SUCCEEDED, using what it measured, before the next one is sized to die.
# The numbers are real: 14.374 GB reported by the process, 42.7 GB billed by the scheduler.


class _Kern:
    name = "k"
    spec = {}
    executor = {"memory_gb_base": 8.0, "memory_gb_per_100k": 6.0}


_both = {"n_cells": 100_713, "peak_rss_gb": 14.374, "cgroup_peak_gb": 42.7}
ck("two measurements of one cost: the LARGER is taken",
   FB.peak_measurement(_both)[0] == 42.7, str(FB.peak_measurement(_both)))
ck("and it says which one that was", "scheduler" in FB.peak_measurement(_both)[1],
   FB.peak_measurement(_both)[1])
ck("a floor on its own is still usable", FB.peak_measurement({"peak_rss_gb": 3.0})[0] == 3.0)
ck("and no measurement at all is not a zero", FB.peak_measurement({})[0] is None)

_d = FB.memory_drift(_Kern, {"measured": _both})
ck("the under-declaration is diagnosed", len(_d) == 1, str(_d))
ck("against the DECLARATION, not the method or the environment",
   _d and _d[0].layer == FB.DECLARATION, str(_d[0].layer) if _d else "")
ck("it is not auto-repairable - the host must not silently correct a declaration",
   _d and _d[0].repairable is False)
ck("it names the fields to change", _d and "memory_gb_base" in _d[0].action, str(_d[0].action))
ck("and says why a kill leaves nothing to diagnose",
   _d and "no traceback" in _d[0].why, str(_d[0].why)[:80])

ck("a declaration that covers the cost is silent",
   FB.memory_drift(type("K2", (_Kern,), {"executor": {"memory_gb_base": 60.0,
                                                      "memory_gb_per_100k": 0.0}}),
                   {"measured": _both}) == [])
ck("and so is a run that measured nothing", FB.memory_drift(_Kern, {"measured": {}}) == [])
ck("no declared model at all is reported as one to WRITE, not one that is wrong",
   len(FB.memory_drift(type("K3", (_Kern,), {"executor": {}}), {"measured": _both})) == 1)
# A THRESHOLD THAT FIRES ON NOISE IS ONE A MAINTAINER LEARNS TO SCROLL PAST.
_near = {"n_cells": 100_000, "peak_rss_gb": 14.0 * FB.MEMORY_DRIFT_RATIO * 0.99}
ck("a small overshoot is noise and is not reported",
   FB.memory_drift(_Kern, {"measured": _near}) == [], str(FB.memory_drift(_Kern, {"measured": _near})))


print("\na job-wide counter is never charged to one instance")
# THE SECOND HALF OF THE SAME DEFECT. Fixing the cgroup PATH made the number right - 45.0 GB
# against PBS's own 42.7 GB for the job - and it was still attributed to each of ten concurrent
# instances, so all ten reported 45.0 GB over inputs of 7,374 to 11,985 cells and the advice was
# to raise a 3.8 GB declaration elevenfold. An even split puts the true figure near 4.5 GB, which
# is 1.18x the declaration: it was right all along.
class _K:
    name = "p"
    executor = {"memory_gb_base": 3.8, "memory_gb_per_100k": 0.0}


_pl = {"measured": {"n_cells": 11985, "cgroup_peak_gb": 45.0, "peak_rss_gb": 4.1}}
_shared = FB.memory_drift(_K(), _pl, concurrent=10)
_alone = FB.memory_drift(_K(), _pl, concurrent=1)
ck("with several instances in one job it is not a declaration defect",
   len(_shared) == 1 and _shared[0].layer == FB.HOST, str([d.layer for d in _shared]))
ck("and it says so in the words that stop the wrong fix",
   "must not be raised to it" in _shared[0].why, _shared[0].why[:90])
ck("it names the per-instance bound an even split implies",
   "4.5 GB" in _shared[0].why, _shared[0].why[-120:])
ck("with ONE instance the counter is exact and the declaration IS checked",
   len(_alone) == 1 and _alone[0].layer == FB.DECLARATION,
   str([d.layer for d in _alone]))
ck("the floor measurement is never suppressed - only the job-wide one",
   FB.memory_drift(_K(), {"measured": {"n_cells": 11985, "peak_rss_gb": 45.0}},
                   concurrent=10)[0].layer == FB.DECLARATION,
   "the process's own floor belongs to the process, however many share the job")

from pathlib import Path as _Path                                            # noqa: E402
_src_cli = (_Path(__file__).resolve().parents[1] / "scprofile" / "cli.py").read_text()
ck("and the FITTED model refuses the same input",
   "_unattributable" in _src_cli and "was NOT fitted" in _src_cli,
   "identical peaks at differing sizes fit a horizontal line through one number")
ck("detected from the data, not plumbed through the scheduler",
   "round(_gb, 6) for _sz, _gb in _pts" in _src_cli,
   "so the check cannot fall out of step with how waves are scheduled")


print("\nthe memory counter is the JOB'S cgroup, never the machine's")
# RECONSTRUCTED FROM THE RUN THAT BROKE IT: a 1 TB node, a batch job in an unnamespaced
# cgroup v2, ten concurrent instances. The old code read /sys/fs/cgroup/memory.peak by absolute
# path - the ROOT - and reported 1000.7 GB ten times, identical, for instances of 7,374 to 11,985
# cells. PBS billed the whole job 42.7 GB. The declaration it then told the maintainer to raise
# was 3.5-3.8 GB and correct.
import tempfile as _tf                                                          # noqa: E402
from pathlib import Path as _P                                                  # noqa: E402
from scprofile import _entry as _E                                              # noqa: E402


def _tree(proc_text, files, total=1007.4):
    """A fake /sys/fs/cgroup + /proc/self/cgroup. Returns what _cgroup_peak_gb makes of it."""
    d = _P(_tf.mkdtemp())
    (d / "proc").write_text(proc_text)
    for rel, gb in files.items():
        f = d / "cg" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(str(int(gb * 1024 ** 3)))
    (d / "cg").mkdir(exist_ok=True)
    return _E._cgroup_peak_gb(root=d / "cg", procfile=d / "proc", total=total)


_job = _tree("0::/pbspro.service/jobs/698875\n",
             {"pbspro.service/jobs/698875/memory.peak": 42.7})
ck("a job-scoped cgroup v2 peak is read", _job is not None and abs(_job - 42.7) < 0.01, str(_job))

_root = _tree("0::/\n", {"memory.peak": 1000.7})
ck("THE ROOT CGROUP IS NOT READ - this is the 1000.7 GB, and it must not come back",
   _root is None, str(_root))

_nodewide = _tree("0::/pbspro.service/jobs/698875\n",
                  {"pbspro.service/jobs/698875/memory.peak": 1000.7})
ck("and a job-scoped value indistinguishable from the whole machine is refused too",
   _nodewide is None, f"{_nodewide} - a counter that might be the node is not evidence")

_v1 = _tree("7:memory:/pbspro/698875\n",
            {"memory/pbspro/698875/memory.max_usage_in_bytes": 12.5})
ck("cgroup v1 still works, at its own controller path", _v1 is not None and abs(_v1 - 12.5) < 0.01,
   str(_v1))

_v1root = _tree("7:memory:/\n", {"memory/memory.max_usage_in_bytes": 1000.7})
ck("and v1's root is refused by the same rule", _v1root is None, str(_v1root))

ck("no /proc at all is None, not a crash and not a zero",
   _E._cgroup_peak_gb(root="/nonexistent-cg", procfile="/nonexistent-proc") is None)

_plausible = _tree("0::/pbspro.service/jobs/1\n",
                   {"pbspro.service/jobs/1/memory.peak": 900.0}, total=1007.4)
ck("a large but sub-machine reading is still believed - the guard is not a cap",
   _plausible is not None and abs(_plausible - 900.0) < 0.01, str(_plausible))


print("\n" + ("the loop holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
