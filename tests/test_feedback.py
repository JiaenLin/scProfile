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
ck("findings reach report.json", '"diagnoses"' in src)
ck("and which plugins were repaired", '"repaired"' in src)

print("\n" + ("the loop holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
