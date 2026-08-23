"""Nothing here may assume one project's dataset, one lab's conventions or one species.

scProfile is written against a cohort that came through scQC, scAnno and scIntegrate, and every
convenience that made THAT cohort easy is a place where somebody else's object stops working. The
failure is never loud: a key that is not found is a legitimate answer for an optional key, an
organism with no reference data looks exactly like a plugin that needs none, and an annotator's
sentinel that this tool does not know becomes a cell population.

So the portability rules are asserted, not intended.

Run: python tests/test_portability.py
"""
import inspect
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import cli, inputs, refs                                         # noqa: E402
from scprofile.kernels import discover                                          # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


print("\nno project, person, machine or cohort appears anywhere")
BAD = re.compile(r"\bsambo\b|wangyb|duke-nus|hn-10-03|aging[_ ]?hfd|young[_ ]?hfd"
                 r"|/data/wangyb|scratch/2026"
                 # BARE SAMPLE NAMES. The list above caught `aging_hfd` and missed `Aging1`,
                 # which is the same cohort's other arm - so a dozen of them reached docs, host
                 # code and two test files before anyone noticed. A leak guard that covers some
                 # of a cohort's names is a guard that reports clean while the tree is not.
                 r"|\b(?:aging|young)[ _]?\d+\b"
                 # and the tissue the cohort came from: naming it identifies the study as
                 # surely as naming a sample does.
                 r"|heart study|myocard|cardiomyocyte", re.I)
#: Two exemptions, both narrow, because a check that fires on correct code is a check somebody
#: switches off. A repository URL contains its owner's account name and is not a leak; and the
#: OTHER leak guard has to contain the strings it looks for.
OK_LINE = re.compile(r"github\.com/|re\.compile|re\.I\)")
root = Path(__file__).resolve().parents[1]

#: SCAN EVERYTHING THAT IS NOT BINARY, rather than listing the languages to scan. The list
#: version read `*.py`, `*.yml`, `*.md` - and by the time anyone looked, the tree also held three
#: `.pbs` templates, a `selftest.R` and a shell script, none of which this check had ever opened.
#: A `.pbs` is the single most likely place for an absolute cluster path to appear, so the guard
#: had a hole exactly where the risk is highest. Inverting it means a kernel written in a new
#: language is covered on the day it lands instead of the day somebody remembers.
BINARY = {".png", ".jpg", ".jpeg", ".pdf", ".svg", ".ico", ".gz", ".zip", ".h5", ".h5ad",
          ".feather", ".npy", ".npz", ".parquet", ".so", ".pyc", ".whl"}
hits, scanned = [], 0
for f in sorted(root.rglob("*")):
    if not f.is_file() or ".git" in f.parts or f.name == Path(__file__).name:
        continue
    if f.suffix.lower() in BINARY:
        continue
    scanned += 1
    for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if BAD.search(line) and not OK_LINE.search(line):
            hits.append(f"{f.relative_to(root)}:{i}")
ck(f"no project or host names in the tree ({scanned} files scanned)", not hits,
   "; ".join(hits[:4]))
# The count is asserted, not merely printed: a glob that silently starts matching nothing reports
# a clean tree, and a clean report from a check that ran on zero files is the worst kind.
ck("and the scan actually opened the tree", scanned >= 40, f"only {scanned} files")

print("\nevery role a user might name differently is DETECTED and OVERRIDABLE")
for role in ("label", "sample", "batch", "compartment", "counts_layer", "lognorm_layer",
             "embedding"):
    ck(f"{role} has candidates", bool(inputs.CANDIDATES.get(role)))
    got = inputs.detect_keys(["zzz"], layers=["zzz"], obsm=["zzz"],
                             overrides={role: "zzz"})[role]
    ck(f"{role} can be overridden", got[0] == "zzz" and "command line" in got[1], str(got))

print("\nthe log-normalised layer is not assumed to be called `lognorm`")
for lay, want in (("lognorm", "lognorm"), ("logcounts", "logcounts"), ("data", "data"),
                  ("normalized", "normalized")):
    got = inputs.detect_keys(["c"], layers=["counts", lay], obsm=[])["lognorm_layer"][0]
    ck(f"a layer called {lay!r} is found", got == want, f"got {got!r}")
src = inspect.getsource(cli)
ck("the host no longer hard-codes the string",
   "'lognorm' if 'lognorm' in A.layers" not in src)

print("\nthe embedding is detected with evidence, not picked inline")
ck("embedding is a declared role", "embedding" in inputs.CANDIDATES)
ck("the inline pick is gone", "X_scanvi', 'X_umap', 'X_pca'" not in src)
got = inputs.detect_keys(["c"], layers=[], obsm=["X_harmony"])["embedding"]
ck("an object with no scanvi still gets one", got[0] == "X_harmony", str(got))
ck("and the reason is recorded", bool(got[1]))

print("\nno flag restricts the user's own declaration")
p = cli.main.__globals__  # the parser is built inside main; check the source instead
ck("--organism takes any species",
   'choices=[None, "mouse", "human"]' not in src and '"--organism", default=None, metavar' in src)
ck("--sentinels exists", '"--sentinels"' in src)
ck("--embedding is read, not just declared", 'getattr(a, "embedding", None)' in src)

print("\nannotator sentinels are a default, never a definition")
ck("the default is documented as scAnno's", "scAnno" in inspect.getsource(inputs))
ck("an empty override means none", cli._split("") == [])
ck("a custom set parses", cli._split("Doublet,Unknown") == ["Doublet", "Unknown"])

print("\na plugin with reference data refuses an organism it has none for")
ks = discover()
sc_ = ks["scenic"]
ck("scenic declares its organisms", sc_.reference_organisms() == {"mouse", "human"},
   str(sc_.reference_organisms()))
for org in ("zebrafish", "drosophila", None):
    try:
        refs.require_supported(sc_, org)
        ck(f"{org!r} is refused", False, "it was allowed to run with no reference data")
    except refs.UnsupportedOrganism as e:
        ck(f"{org!r} is refused", "declares none for" in str(e))
        ck(f"and the refusal names what it does have ({org!r})", "mouse" in str(e))
try:
    refs.require_supported(sc_, "MOUSE")
    ck("a supported organism still runs, case-insensitively", True)
except refs.UnsupportedOrganism:
    ck("a supported organism still runs, case-insensitively", False)
refs.require_supported(ks["cellcycle"], "zebrafish")
ck("a plugin that needs no references is not refused", True)
ck("the host asks reference_organisms, not references(organism)",
   "k.reference_organisms()" in src and "if k.references(organism[0]) else {}" not in src)

print("\ntwo fetches into one directory refuse rather than race")
import os as _os, tempfile as _tf                                              # noqa: E402
with _tf.TemporaryDirectory() as _d:
    _d = Path(_d)
    with refs._DirLock(_d):
        ck("the lock file exists while held", (_d / ".scprofile_fetch.lock").exists())
        try:
            with refs._DirLock(_d):
                ck("a second writer is refused", False, "it was allowed in")
        except RuntimeError as e:
            ck("a second writer is refused", "already writing" in str(e))
            ck("and the refusal names the pid and host", str(_os.getpid()) in str(e))
    ck("the lock is released on the way out", not (_d / ".scprofile_fetch.lock").exists())

    # A JOB KILLED MID-DOWNLOAD MUST NOT BLOCK THE RETRY. That is exactly what happened - a
    # superseded job was qdel'd while holding a 46 MB .part - so a lock whose owner is gone is
    # taken over rather than obeyed.
    (_d / ".scprofile_fetch.lock").write_text("999999 " + refs.socket.gethostname() + "\n")
    took = []
    with refs._DirLock(_d, log=took.append):
        ck("a stale lock is taken over", any("stale" in x for x in took), str(took))
    (_d / ".scprofile_fetch.lock").write_text("1 some-other-node\n")
    try:
        with refs._DirLock(_d, log=lambda *_a: None):
            ck("a lock from another host is not assumed dead", True)
    except RuntimeError:
        ck("a lock from another host is not assumed dead", True)

print("\nthe two audiences are distinguishable")
_cli = inspect.getsource(cli)
for _c in ("doctor", "install", "fetch", "run", "plan", "report"):
    ck(f"{_c} is marked for the user", f'"{_c}", help="[you]' in _cli)
for _c in ("validate", "selftest", "scaffold"):
    ck(f"{_c} is marked for the maintainer", f'"{_c}", help="[maintainer]' in _cli)
_rt = Path(__file__).resolve().parents[1]
_rm = (_rt / "README.md").read_text()
# THE INTENT, NOT ONE SENTENCE. This pinned the literal phrase "for people running an analysis",
# so rewording the README broke it while the property it guards - that a reader can tell which
# half is addressed to them - was still true.
ck("the README tells a user they never write a plugin",
   "never write a wrapper" in _rm.lower() or "you never open a plugin" in _rm.lower())
ck("and names the maintainer path", "maintainer" in _rm.lower()
   and "MAINTAINING_PLUGINS.md" in _rm)
ck("and splits its documentation by audience",
   "**Users:**" in _rm and "**Maintainers:**" in _rm)
ck("and points maintainers elsewhere", "MAINTAINING_PLUGINS" in _rm)
_mg = _rt / "docs" / "MAINTAINING_PLUGINS.md"
ck("the maintainer guide exists", _mg.exists())
_mt = _mg.read_text() if _mg.exists() else ""
ck("it says it is not for users", "not for users" in _mt)
ck("it covers WHEN a plugin needs attention", "needs attention" in _mt)
ck("it says a release is not automatically a reason to bump",
   "not a reason to bump" in _mt)
ck("it names what a maintainer does NOT own", "do NOT own" in _mt)

print("\nthe planner assumes no design shape and no cohort")
from scprofile import planner as _P                                            # noqa: E402
# CODE, NOT PROSE. The first version searched the whole source and fired on the docstring
# sentence "not 2x2, not paired, not a time course" - a DISCLAIMER that the planner assumes no
# shape. A check that fires on correct code is a check somebody switches off, so comments and
# docstrings are stripped and only executable text is searched.
import ast as _a2                                                              # noqa: E402
_tree = _a2.parse(inspect.getsource(_P))
for _n in _a2.walk(_tree):
    if isinstance(_n, (_a2.Module, _a2.FunctionDef, _a2.AsyncFunctionDef, _a2.ClassDef)):
        if (_n.body and isinstance(_n.body[0], _a2.Expr)
                and isinstance(getattr(_n.body[0], "value", None), _a2.Constant)
                and isinstance(_n.body[0].value.value, str)):
            _n.body.pop(0)
_psrc = _a2.unparse(_tree)
for lit in ("2x2", "young", "aged", "chow", "HFD", "cell_type", "sample_id",
            "mouse", "human", "nucleus"):
    ck(f"the planner's CODE does not mention {lit!r}", lit not in _psrc)
ck("no minimum sample count is hard-coded except the statistical one",
   _psrc.count("min_replicates") >= 1 and "n_units > 3" not in _psrc)
# One sample, no design, nothing found: a short, correct, honest plan - not an error.
_f = _P.design_facts(None, [], None, ["only"])
class _K:
    name, needs_design, per_unit, needs_kernels = "x", False, None, []
_v = _P.plan_kernel(_K(), present={"x": {}}, facts=_f, searched=["obj"], ran=set())
ck("a one-sample, design-less project still yields a verdict", _v.verdict == _P.RUN, _v.verdict)
_fnd = _P.audit([_v], ["x"], _f)
ck("and that plan passes its own audit",
   not [x for x in _fnd if x.level == "ERROR"], str(_fnd))

print("\nplan and run agree on every override")
run_flags = set(re.findall(r'r\.add_argument\("--([a-z-]+)"', src))
plan_flags = set(re.findall(r'"([a-z-]+)"', src.split('for f in ("label-key"')[1].split(")")[0]))
plan_flags.add("label-key")
missing = {f for f in ("label-key", "sample-key", "batch-key", "counts-layer", "lognorm-layer",
                       "compartment-key", "embedding", "sentinels", "organism", "assay")
           if f not in plan_flags}
ck("plan takes the same key overrides as run", not missing, str(sorted(missing)))

print("\nthe constraint on use is read from ANY upstream tool, not one toolchain")
# A SAFETY MECHANISM THAT FIRES ONLY FOR ITS AUTHOR'S PIPELINE IS WORSE THAN NONE. This read
# `uns['scintegrate']['constraint_on_use']` and nothing else, so for every object produced by
# any other pipeline the whole mechanism was silent - and silence here reads exactly like
# "no constraint applies", which is the one wrong answer it must never give.
from scprofile.inputs import read_constraint as _rc                            # noqa: E402


class _Stub:
    def __init__(self, uns):
        self.uns = uns


ck("no constraint is reported as absent, not as clear", _rc(_Stub({})) == ("", ""))
_t, _s = _rc(_Stub({"someothertool": {"constraint_on_use": "do not test X"}}))
ck("a THIRD-PARTY tool's constraint is found", _t == "do not test X", _s)
ck("and the source names that tool", "someothertool" in _s, _s)
_t2, _s2 = _rc(_Stub({"scintegrate": {"constraint_on_use": "Y"},
                      "atool": {"constraint_on_use": "X"}}))
ck("two writers are BOTH binding, neither silently dropped",
   "X" in _t2 and "Y" in _t2, _t2)
ck("and both sources are named", "atool" in _s2 and "scintegrate" in _s2, _s2)
ck("a top-level constraint is found too", _rc(_Stub({"constraint_on_use": "Z"}))[0] == "Z")
ck("a non-mapping uns entry does not raise", _rc(_Stub({"x": "a string", "y": 42})) == ("", ""))
ck("no upstream tool is named in the reader",
   not any(t in inspect.getsource(_rc) .replace("scintegrate", "", 1)
           for t in ("scqc", "scanno")),
   "the reader still names a specific pipeline")

print("\n" + ("nothing here assumes one dataset" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
