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
import pathlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import cli, inputs, refs                                         # noqa: E402
from scprofile.kernels import discover                                          # noqa: E402

FAIL = []


def _refused(fn):
    """True if the call raises DeclarationError — a check that must still refuse."""
    try:
        fn()
    except Exception as e:                                                # noqa: BLE001
        return type(e).__name__ == "DeclarationError"
    return False


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

print("\nwhat the tool REASONS about is not what a user may DECLARE")
# `--organism` had its `choices` removed because argparse refused the flag before the tool could
# refuse the analysis - a user of any other species could not even say what they had. `--assay`
# was left with `choices=[None, "cell", "nucleus"]`: the same defect, one flag over.
_cli_src = (Path(__file__).resolve().parents[1] / "scprofile" / "cli.py").read_text()
ck("--assay does not restrict what can be declared",
   'choices=[None, "cell", "nucleus"]' not in _cli_src)
ck("--organism does not either", 'choices=[None, "mouse", "human"]' not in _cli_src)
ck("but an unrecognised assay is REPORTED, so the caveats that will not fire are named",
   _cli_src.count("is not an assay this tool reasons about") >= 2,
   "the plan and the run must both say it")
_val = (Path(__file__).resolve().parents[1] / "scprofile" / "validate.py").read_text()
ck("and validate does not warn on every unlisted organism, only on a likely typo",
   "get_close_matches" in _val)

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

print("\nthe reporter knows what a panel is FOR and no panel by name")
# A REPORTER THAT KNEW THE IDS WOULD BE WRONG ABOUT EVERY PLUGIN IT HAD NOT BEEN TOLD ABOUT -
# the defect `_who_produces` in kernels.py was written to record, arriving in a third domain.
# The vocabulary is three words; everything else about a panel comes from the plugin's own
# declaration, so a tenth plugin with panels nobody has seen is laid out as well as the nine.
from scprofile import declare as _dc, report as _rp                            # noqa: E402
from scprofile.kernels import discover as _disc                                # noqa: E402

_HOST = {q.name: q.read_text() for q in
         (Path(__file__).resolve().parents[1] / "scprofile").glob("*.py")}
_ids = sorted({str(f.get("id")) for k in _disc().values()
               for f in _dc.report_figures(k.spec) if f.get("id")})
ck("some plugin declares panels at all, or this check proves nothing", bool(_ids), str(_ids))
_leak = [(m, i) for m, s in _HOST.items() for i in _ids if i in s]
ck("no host module names a figure id", not _leak, str(_leak[:4]))
ck("the vocabulary is closed and generic",
   _dc.SHOWS == ("diagnostic", "result", "comparison"), str(_dc.SHOWS))
_gsrc = inspect.getsource(_rp._figure_section) + str(_rp._GROUPS)
# ON A WORD BOUNDARY. `de` is a shipped plugin's name and a syllable in half of English, so a
# substring test fails on the word "declared" and reports a leak that is not one - a guard that
# cries wolf is a guard somebody deletes.
_named = [n for n in _disc() if re.search(rf"\b{re.escape(n)}\b", _gsrc)]
ck("and the reporter's own text names no plugin", not _named, str(_named))

print("\na plugin that declares no report block is still reported")
# THE DECLARATION MUST BE WORTH ADDING, NOT COMPULSORY. A format that refuses a plugin for not
# having it yet is a format nobody adopts - and every plugin written before this existed is such
# a plugin, including any a user wrote against $SCPROFILE_KERNELS.
_none = _rp._figure_section([{"id": "x", "path": "kernels/k/figures/x.png", "caption": "c"}],
                            None)
ck("its emitted panels are still rendered", "x.png" in _none)
ck("and the page says why it cannot say more", "declares no" in _none)
ck("nothing is claimed missing", "NOT PRODUCED" not in _none)
_empty = _rp._figure_section([], None)
ck("a plugin that drew nothing and declared nothing renders nothing", _empty == "")

print("\na declared panel that was not drawn is stated, never a gap")
_spec = {"figures": [
    {"id": "must", "shows": "diagnostic", "question": "q1", "source": "s", "required": True},
    {"id": "may", "shows": "result", "question": "q2", "source": "s", "required": False,
     "when_absent": "the data could not support it"}]}
_out = _rp._figure_section([], _spec)
ck("a required panel that is absent is a DEFECT on the page", "NOT PRODUCED" in _out)
# THE TWO ABSENCES MUST NOT LOOK ALIKE. A required panel missing is a defect in the run; an
# optional one missing is a property of the data, and the page says which with a different class
# and the plugin's own sentence. Asserted on the classes, because splitting the HTML on an id
# that is never printed compared the wrong half and passed for the wrong reason.
ck("an optional one carries the plugin's own reason and is NOT a defect",
   "the data could not support it" in _out
   and _out.count("class=\"bad\"") == 1 and _out.count("class=\"warn\"") == 1,
   f'bad={_out.count(chr(34).join(["class=", "bad", ""]))}')
ck("both questions are printed whether or not the panel exists",
   "q1" in _out and "q2" in _out)
_drawn = _rp._figure_section(
    [{"id": "undeclared", "path": "kernels/k/figures/u.png", "caption": ""}], _spec)
ck("a panel drawn and not declared is still shown", "u.png" in _drawn)
ck("...and named as undeclared", "not declared" in _drawn.lower())

print("\nthe run -> declare edge holds a plugin to its own report block")
from scprofile import feedback as _fb                                          # noqa: E402


class _K:
    def __init__(self, spec):
        self.spec = spec


ck("no block means nothing to drift from",
   _fb.figure_drift(_K({}), {"figures": []}) == [])
_d = _fb.figure_drift(_K({"report": _spec}), {"figures": [{"id": "may"}]})
ck("a required panel not drawn is a finding", any("must" in d.why for d in _d), str(_d))
ck("an optional one not drawn is not", not any("'may'" in d.why for d in _d), str(_d))
_d2 = _fb.figure_drift(_K({"report": _spec}),
                       {"figures": [{"id": "must"}, {"id": "may"}, {"id": "surprise"}]})
ck("a panel drawn and not declared is a finding", any("surprise" in d.why for d in _d2), str(_d2))
ck("a refusal is allowed to draw nothing",
   _fb.figure_drift(_K({"report": _spec}), {"status": "refused", "figures": []}) == [])

print("\nthe id survives the round trip a real run makes")
# THE JOIN IS THE WHOLE MECHANISM, and it was severed at serialisation. `manifest._figure` builds
# a fresh mapping from a fixed key list written before `report.figures` existed, so nine panels
# emitted with their ids arrived at the host as nine `null`s - and the drift check that exists to
# catch exactly that reported clean, because it was reading ids that were no longer there.
# Measured on PBS 688878. A check whose input has been silently emptied is worse than no check.
import json as _json                                                           # noqa: E402
import tempfile as _tf                                                         # noqa: E402
from scprofile import manifest as _mf                                          # noqa: E402

with _tf.TemporaryDirectory() as _d:
    _o = Path(_d)
    (_o / "figures").mkdir()
    for _n in ("declared", "bare"):
        (_o / "figures" / f"{_n}.png").write_bytes(b"x")
    _pl = _mf.write_output(
        _o, kernel="k", status="ok", headline="h", caveats=["c"],
        figures=[{"id": "declared", "path": _o / "figures" / "declared.png", "caption": "c"},
                 _o / "figures" / "bare.png"])
    _back = _json.loads((_o / "out.json").read_text())
    _ids = [f.get("id") for f in _back["figures"]]
    ck("a declared id survives into out.json", _ids[0] == "declared", str(_ids))
    ck("and the one-line form gets the file's stem, so both forms join up",
       _ids[1] == "bare", str(_ids))

    # END TO END, because both halves passed on their own and the pair did not.
    _spec2 = {"figures": [{"id": "declared", "shows": "result", "question": "q",
                           "source": "s", "required": True},
                          {"id": "never_drawn", "shows": "diagnostic", "question": "q2",
                           "source": "s", "required": True}]}
    _f = _fb.figure_drift(_K({"report": _spec2}), _back)
    ck("a panel that WAS drawn is not reported missing",
       not any("'declared'" in x.why for x in _f), str([x.why[:50] for x in _f]))
    ck("...and one that was not IS", any("never_drawn" in x.why for x in _f),
       str([x.why[:50] for x in _f]))

print("\na partial run drew a page and is checked like any other")
# `partial` is the ordinary status of a method that fitted on a subset or scored below its own
# threshold - most real runs - and it was exempted from the figure check by a guard copied from
# `declaration_drift`, where it belongs. The first real run of this check was silent for that
# reason on top of the one above.
ck("a partial run is held to its declaration",
   len(_fb.figure_drift(_K({"report": _spec}), {"status": "partial", "figures": []})) > 0)
ck("a refusal is still exempt",
   _fb.figure_drift(_K({"report": _spec}), {"status": "refused", "figures": []}) == [])

print("\na representation and a layout are two roles, resolved by rule and not by product name")
# THE DEFECT THIS REPLACES: `embedding` was used for both, so a 30-column scANVI latent was
# handed to a plugin to DRAW on. The rule below must work for a toolchain nobody here has heard
# of, which is why it derives the layout from the chosen representation rather than listing keys.
_pl = inputs.pick_layout

_int = {"X_pca": 50, "X_someintegrator": 30, "X_umap_someintegrator": 2, "X_umap": 2}
_got, _why = _pl(_int, embedding="X_someintegrator")
ck("the layout DERIVED from the representation wins, whatever the tool is called",
   _got == "X_umap_someintegrator", f"{_got} - {_why}")
ck("...and the reason says so, without naming a product", "derived from the representation" in _why)
ck("a plain object falls back to its only conventional layout",
   _pl({"X_pca": 50, "X_umap": 2}, embedding="X_pca")[0] == "X_umap")
ck("a 2-column key under a name nobody knows is still found",
   _pl({"X_zzz": 2}, embedding=None)[0] == "X_zzz")
ck("a representation alone yields NONE, not its first two columns",
   _pl({"X_pca": 50}, embedding="X_pca")[0] is None)
ck("...and the reason names what to compute",
   "sc.tl.umap" in _pl({"X_pca": 50}, embedding="X_pca")[1])
try:
    _pl({"X_pca": 50}, override="X_pca")
    ck("a wide key named with --layout is REFUSED", False, "it was accepted")
except inputs.Refuse as e:
    ck("a wide key named with --layout is REFUSED", "50 columns" in str(e), str(e)[:60])
ck("no host module hard-codes a layout key of one toolchain",
   not any(re.search(r"X_umap_[a-z]+", s) for n, s in _HOST.items() if n != "inputs.py"),
   "a derived-layout key is spelled out somewhere it should be derived")
_lay_src = inspect.getsource(inputs.pick_layout)
ck("and the rule itself names no integration tool",
   not any(w in _lay_src for w in ("scanvi", "scvi", "harmony", "bbknn")),
   "the rule names a specific integrator")

print("\nthe palette does not silently repeat itself")
from scprofile import figure as _fg                                            # noqa: E402

ck("more hues than Okabe-Ito alone", len(_fg.CATEGORY_COLOURS) > len(_fg.OKABE_ITO))
_many = [f"pop{i:02d}" for i in range(14)]
ck("fourteen categories get fourteen colours",
   len(set(_fg.palette(_many).values())) == 14, str(len(set(_fg.palette(_many).values()))))
ck("no collision at fourteen", _fg.palette_collisions(_many) == [])
_too_many = [f"pop{i:02d}" for i in range(len(_fg.CATEGORY_COLOURS) + 3)]
_cl = _fg.palette_collisions(_too_many)
ck("past the palette's end the collisions are ANSWERABLE, not silent", len(_cl) == 3, str(_cl))
ck("...and each names the labels that share the hue",
   all(len(labs) == 2 for _c, labs in _cl), str(_cl))

print("\nan axis label is a convention of this tool, not of each plugin")
# FOUR PLUGINS DREW ON A LAYOUT AND WROTE FOUR AXIS LABELS. Three printed the obsm key verbatim -
# `umap_scanvi 1` - and the fourth carried a private splitter, so the correction that turned
# `SCANVI 1` into `UMAP 1 (of scanvi)` reached one of the four and none of the others. A
# convention implemented per plugin is a convention that drifts.
_KSRC = {q.name: q.read_text() for q in
         (Path(__file__).resolve().parents[1] / "kernels").glob("*.py")}
_own = sorted(n for n, s in _KSRC.items()
              if re.search(r'set_[xy]label\(\s*f["\']\{[A-Za-z_]+\}\s*[12]', s))
ck("no plugin spells its own basis axis label", not _own, str(_own))
# CODE, NOT PROSE. `de` explains in a comment that it never calls `ctx.layout()` because it has
# nothing per-cell to place - and a substring test read that sentence as a call, which is the same
# false positive the plugin-name check hit on the word "declared". A guard that fires on a comment
# saying the right thing is a guard somebody deletes.
def _code(s):
    return "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))


_draws = [n for n, s in _KSRC.items() if "ctx.layout()" in _code(s)]
ck("some plugin draws on a layout, or this check proves nothing", bool(_draws), str(_draws))
ck("the ones that draw on a layout use the shared label",
   all("basis_label" in _KSRC[n] for n in _draws),
   str([n for n in _draws if "basis_label" not in _KSRC[n]]))
ck("and the splitter lives in figure.py, not in a plugin",
   not any("def split_basis" in s or "def _split_basis" in s for s in _KSRC.values()),
   "a plugin carries its own splitter")
ck("it knows a multi-word algorithm from a provenance",
   _fg.split_basis("draw_graph_fa") == ("draw_graph_fa", "")
   and _fg.split_basis("X_umap_anything") == ("umap", "anything"),
   str(_fg.split_basis("draw_graph_fa")))
ck("and an unrecognised basis is printed whole rather than guessed at",
   _fg.split_basis("X_somebodyelses") == ("somebodyelses", ""))

print("\nhierarchical labels are shortened by one rule, and the rule keeps them unambiguous")
# A THIRD CONVENTION THAT HAD DRIFTED PER PLUGIN. Annotation labels are PATHS, and a
# communication panel's categories are pairs of them - sixty characters before a real name is
# reached. Rotated ninety degrees they took three quarters of two shipped panels' height and, on
# one, the colourbar was drawn through the label text.
_sl = _fg.short_labels
_g = _sl(["A/one -> B/two", "C/three -> B/two"])
ck("a pair of paths is shortened on BOTH sides",
   _g["A/one -> B/two"] == "one -> two", str(_g))
ck("a flat label is left alone", _sl(["alpha", "beta"], pair=None)["alpha"] == "alpha")
_c = _sl(["A/x", "B/x", "A/y"], pair=None)
ck("two labels that would collide BOTH keep another segment",
   _c["A/x"] == "A/x" and _c["B/x"] == "B/x", str(_c))
ck("...while one that would not is still shortened", _c["A/y"] == "y", str(_c))
ck("it returns a MAPPING, so the full path can stay in the source table",
   isinstance(_sl(["A/b"]), dict))
ck("a label with no separator survives", _sl(["plain"], pair=None)["plain"] == "plain")
ck("it terminates on a label that cannot be made unique",
   _sl(["same", "same"], pair=None)["same"] == "same")
_users = [n for n, s in _KSRC.items() if "set_xticklabels" in _code(s) and "rotation=90" in _code(s)]
ck("some plugin rotates category labels, or this check proves nothing", bool(_users), str(_users))
ck("every plugin that rotates them shortens them through the shared rule",
   all("short_labels" in _KSRC[n] for n in _users),
   str([n for n in _users if "short_labels" not in _KSRC[n]]))

# ---------------------------------------------------------------------------------------------
# A REQUIREMENT IS STATED ONCE, AND EVERY DECISION READS THE PLACE IT IS STATED.
#
# `inject.required` is what the runner enforces; `needs_*` is what six DECISIONS read. The two
# drifted apart in the one direction nothing can see: `needs_design` and `needs_obsm` were unset
# on every shipped plugin, so six conditions took their False branch on every run of every
# cohort. Nothing refused, no contrast was ever planned, and the constraint check exempted the
# one plugin whose headline that constraint forbids. At a call site an unset flag and an unmet
# condition are the same three characters.
# ---------------------------------------------------------------------------------------------
from scprofile import declare as _DECL, feedback as _FB, planner as _PL         # noqa: E402
from scprofile import kernels as _KN                                            # noqa: E402
from scprofile.kernels import producer_edges as _pe                             # noqa: E402

_K = discover()

print("\na requirement is stated once, and no decision reads a flag nobody sets")
_dead = _FB.dead_predicates(_K)
ck("no kernel predicate is falsy for every installed plugin",
   not _dead, str([a for a, _ in _dead]))
ck("every exemption from that check carries a written reason",
   all(str(v).strip() for v in _FB.PREDICATE_EXEMPT.values()),
   str([k for k, v in _FB.PREDICATE_EXEMPT.items() if not str(v).strip()]))
ck("needs_design is DERIVED from inject, not declared beside it",
   all(k.needs_design == ("design" in k.injects_required or bool(k.spec.get("needs_design")))
       for k in _K.values())
   and any(k.needs_design for k in _K.values()),
   "a kernel injecting `design` must report needs_design")
_dk = next((k for k in _K.values() if k.requires_role("design")), None)
_probs = _KN.unmet(_dk, obs=(), obsm=(), layers=(), available=_K, ran=set(),
                   has_design=False, keys={}, organism=None, var=(), derived=()) if _dk else []
ck("a kernel requiring a design reports that lack ONCE, not once per statement of it",
   len([x for x in _probs if "design" in str(x).lower()]) == 1,
   str([x for x in _probs if "design" in str(x).lower()]))

print("\na plugin names a capability, never a peer")
_named = {n: [c for c in (k.spec.get("needs_kernels") or [])] for n, k in _K.items()}
ck("no plugin declares another plugin by name",
   not any(_named.values()), str({n: v for n, v in _named.items() if v}))
_unprov = _FB.unprovidable_capabilities(_K)
ck("every capability a plugin asks for has an installed provider",
   not _unprov, str([a for a, _ in _unprov]))
ck("the wave graph has at least one edge, or it is not a graph",
   bool(_pe(_K)), "producer_edges resolved nothing across the installed set")
# TWO WAVE BUILDERS, ONE GRAPH. `schedule` orders the run and `order_of_runs` orders the plan,
# and until both were made to call one edge function they read different things: the run put a
# consumer in the same wave as its producer while the plan put it in the next one. The first fix
# to either is what proves two implementations of one graph drift.
_runw = [sorted({i["plugin"] for i in w})
         for w in _KN.schedule(sorted(_K), _K, budget_cores=8, units=["u1", "u2"])]
_planw = [sorted(w) for w in _PL.order_of_runs(sorted(_K), _K)]
ck("the run's waves and the plan's waves are the same waves", _runw == _planw,
   f"run {_runw} vs plan {_planw}")
ck("and a consumer is in a later wave than its producer",
   all(any(p in _runw[i - 1] for i in range(1, len(_runw)) if c in _runw[i])
       for c, ps in _pe(_K).items() for p in ps),
   str(_pe(_K)))

print("\nthe plan and the run make the same decisions, by calling the same function")
_facts = {"has_design": True, "crossed_pairs": [["f1", "f2"]], "testable": ["f1", "f2"]}
ck("decisions_for is what the planner records",
   "decisions_for(" in inspect.getsource(_PL.settings_for),
   "the planner must not compute a decision inline")
_clisrc = inspect.getsource(cli)
ck("decisions_for is what the run delivers",
   "_PL.decisions_for(" in _clisrc,
   "the run path must call the same function the plan calls")
ck("the run merges those decisions into the params the plugin is handed",
   "params=_params_for(name)" in _clisrc)
ck("user --params override a planned decision, and the run says which it used",
   "OVERRIDES the plan" in _clisrc)
ck("a design-testing plugin is planned a contrast on any crossed design",
   all(_PL.decisions_for(k, _facts).get("contrast", {}).get("kind") == "interaction"
       for k in _K.values() if k.needs_design),
   "a crossed pair with replication must yield an interaction, whatever the factors are called")
# THE DECISION MUST BE DELIVERABLE. The plan printed a contrast, the run delivered it, and both
# plugins refused the whole run three hours into a queue with "no such parameter ['contrast']" —
# because a config key is a knob the USER sets and an injected capability is something the HOST
# hands the plugin, and they arrive in one dict that was validated as though it were all config.
ck("every decision the plan makes is one the plugin declared it can be given",
   all(set(_PL.decisions_for(k, _facts)) <= (set(k.injects_required) | set(k.injects_optional))
       for k in _K.values()),
   str({n: sorted(set(_PL.decisions_for(k, _facts))
                  - set(k.injects_required) - set(k.injects_optional))
        for n, k in _K.items() if _PL.decisions_for(k, _facts)}))
ck("and the config resolver actually delivers it rather than dropping it",
   all(_DECL.resolve_config(k.spec, _PL.decisions_for(k, _facts), n).get("contrast")
       == _PL.decisions_for(k, _facts).get("contrast")
       for n, k in _K.items() if _PL.decisions_for(k, _facts)),
   "an injected capability that passes the check and is then dropped from the resolved "
   "mapping never reaches the plugin, and nothing says so")
ck("a genuine typo in --params is still refused",
   _refused(lambda: _DECL.resolve_config(_K["de"].spec, {"nonsense": 1}, "de")))
ck("and main effects where nothing is crossed",
   all(_PL.decisions_for(k, {"has_design": True, "crossed_pairs": [],
                             "testable": ["f1"]}).get("contrast", {}).get("kind")
       == "main effects" for k in _K.values() if k.needs_design))

print("\nan upstream constraint reaches the page whose claim it bounds")
_c = ("It may carry clustering. It must NOT carry an abundance claim across f1, f2 - for that, "
      "use the uncorrected representation and say so. Per-sample counts are unaffected.")
ck("the factors a constraint binds are read from the prohibition, not the whole text",
   inputs.constraint_binds(_c, ["f1", "f2", "f3", "sample"]) == ["f1", "f2"],
   str(inputs.constraint_binds(_c, ["f1", "f2", "f3", "sample"])))
ck("a factor named only in the remedy is not reported as bound",
   "sample" not in inputs.constraint_binds(_c, ["sample"]))
ck("matching is on word boundaries",
   inputs.constraint_binds("it must NOT average over usage", ["age", "use"]) == [])
ck("no prohibition binds nothing",
   inputs.constraint_binds("this object carries no prohibition", ["f1"]) == [])
from scprofile import report as _RP                                             # noqa: E402
ck("a bound page renders the constraint",
   bool(_RP._constraint_block(_c, ["f1"])))
ck("an unbound page does not",
   not _RP._constraint_block(_c, []))
ck("the binding is decided by the host and carried in the payload",
   '"constraint_binds"' in _clisrc and "constraint_binds" in inspect.getsource(_RP.write_all),
   "the reporter must not re-derive it from a live declaration")
ck("the constraint defect asks what a plugin TESTS, not what container it reads",
   "needs_obsm" not in inspect.getsource(cli).split("design defects")[1][:4000],
   "a claim is bounded by the factor it crosses")

# ---------------------------------------------------------------------------------------------
# A PER-UNIT PLUGIN MUST PUT ITS UNITS ON ONE AXIS.
#
# It runs separately on every unit, and its page is that many single-unit reports in sequence.
# Every panel is true; the question a cohort study asks - do the units agree? - is answered
# nowhere, because the numbers never share an axis. Measured on a ten-animal cohort: one
# plugin's per-unit count ran 8,194 to 38,895 across ten animals of one tissue, in ten separate
# figures, and a reader taking the first unit's strongest result as a finding had nothing on the
# page to warn them.
# ---------------------------------------------------------------------------------------------
print("\na per-unit plugin puts its units on one axis")
_pu = {n: k for n, k in _K.items() if k.per_unit}
ck("some plugin runs per unit, or this section proves nothing", bool(_pu))
for _n, _k in sorted(_pu.items()):
    _ums = (_k.report_spec or {}).get("unit_metrics") or []
    ck(f"{_n} declares what makes its units comparable", bool(_ums))
    ck(f"{_n}'s metrics each carry a question",
       all(str(m.get("id") or "").strip() and str(m.get("question") or "").strip()
           for m in _ums), str(_ums))
    _src = _KSRC.get(f"{_n}.py", "")
    _missing = [str(m.get("id")) for m in _ums
                if f'ctx.metric("{m.get("id")}"' not in _src
                and f"ctx.metric('{m.get('id')}'" not in _src]
    ck(f"{_n} records every metric it declares", not _missing, str(_missing))
ck("the declaration check REFUSES a per-unit plugin that declares none",
   any(lvl == "ERROR" and "unit_metrics" in msg
       for lvl, msg in _DECL.check({**next(iter(_pu.values())).spec,
                                    "report": {"figures": [], "unit_metrics": []}})),
   "a per-unit plugin with no unit_metrics must be an ERROR, not a WARN")

print("\nthe host draws that comparison, so no plugin writes its own version of it")
_units = [{"unit": f"u{i}", "metrics": {"m": v}} for i, v in enumerate([8194, 17957, 38895])]
_html = _RP._across_units(_units, [{"id": "m", "question": "how many?"}])
ck("it renders from the units alone, with no plotting library",
   "<svg" in _html and "matplotlib" not in inspect.getsource(_RP))
ck("it states the range rather than judging it",
   "4.75x" in _html and "too" not in _html.lower().split("across units")[1][:400])
ck("it names the extremes so a reader can go to the unit",
   "u0" in _html and "u2" in _html)
ck("a per-unit plugin that recorded nothing is NAMED as uncomparable, not omitted",
   "cannot be put on one axis" in _RP._across_units([{"unit": "a"}, {"unit": "b"}], []))
ck("one unit is not a comparison",
   "cannot be put on one axis" in _RP._across_units([{"unit": "a", "metrics": {"m": 1}}], []))
ck("counts are not rendered in scientific notation",
   _RP._num(38895) == "38,895" and "e+" not in _RP._num(23543.5))
ck("the comparison is placed BEFORE the per-unit panels",
   inspect.getsource(_RP.write_kernel).index("_across_units")
   < inspect.getsource(_RP.write_kernel).index("_figure_section"))

print("\nthe run is held to what it declared, in both directions")
_kk = next(iter(_pu.values()))
ck("a declared metric that never arrives is a finding",
   any("recorded it for no unit" in d.why
       for d in _FB.metric_drift(_kk, {"status": "ok", "units": [{"metrics": {}}]})))
ck("a metric nobody declared is a finding",
   any("does not declare" in d.why
       for d in _FB.metric_drift(_kk, {"status": "ok",
                                       "units": [{"metrics": {"invented": 1.0}}]})))
ck("a refusal produced nothing by design and is exempt",
   not _FB.metric_drift(_kk, {"status": "refused", "units": []}))
ck("a metric recorded by a plugin that declares none is STILL a finding",
   bool(_FB.metric_drift(_K["de"], {"status": "ok", "metrics": {"stray": 1.0}})),
   "returning early on an empty declaration lets a plugin record what nothing renders")
ck("and a plugin that records none and declares none is clean",
   not _FB.metric_drift(_K["de"], {"status": "ok"}))
ck("a count reported across independently corrected families names the scope",
   "corrected WITHIN" in _KSRC["de.py"] and "_bh_across_families" in _KSRC["de.py"],
   "Apply multiple-testing correction jointly across the whole comparison family, not "
   "separately per cell type, when the cell types are tested in one design")
_bhsrc = ""
for _node in __import__("ast").parse(_KSRC["de.py"]).body:
    if getattr(_node, "name", "") == "_bh_across_families":
        _bhsrc = __import__("ast").get_source_segment(_KSRC["de.py"], _node) or ""
ck("the joint correction is applied to raw p-values, never to an adjusted column",
   'res["pvalue"]' in _bhsrc and '"padj"' not in _bhsrc,
   "correcting an adjusted column twice is a smaller number with no interpretation")
ck("a PARTIAL run wrote a page and is NOT exempt",
   bool(_FB.metric_drift(_kk, {"status": "partial", "units": [{"metrics": {}}]})))

# ---------------------------------------------------------------------------------------------
# THE DESIGN REACHES THE PAGES THAT DID NOT TEST IT.
#
# Of nine plugins on the cohort this was found on, the two that TEST the design reported across
# it and the other seven reported per population and per cell, never once splitting a result by
# the factor the study exists to ask about. Two of the seven DECLARED `design_aware` - "reports
# per arm without testing across the design" - and between them had fourteen panels, none about
# an arm. A flag nobody sets and a flag nobody honours fail the same way and only a check
# against the OUTPUT tells them apart.
# ---------------------------------------------------------------------------------------------
print("\nthe design reaches the pages that did not test it")


class _Obj:
    def __init__(self, obs):
        self.obs = obs


def _fake_obs():
    import numpy as np, pandas as pd
    n, r = 900, __import__("numpy").random.RandomState(0)
    return pd.DataFrame({"sample": [f"S{i % 6}" for i in range(n)],
                         "score": r.normal(size=n),
                         "phase": r.choice(["G1", "S", "G2M"], n),
                         "barcode": [f"b{i}" for i in range(n)],
                         "tiny": r.normal(size=n)})


_des = {f"S{i}": {"f1": "a" if i < 3 else "b", "f2": "x" if i % 2 else "y"} for i in range(6)}
_ba = inputs.by_arm(_Obj(_fake_obs()), ["score", "phase", "barcode"], _des, "sample", ["f1", "f2"])
ck("a numeric per-cell column is summarised per arm",
   _ba.get("score", {}).get("f1", {}).get("kind") == "numeric")
ck("with quantiles, not a mean and an error bar over cells",
   set(_ba["score"]["f1"]["arms"][0]) >= {"median", "q1", "q3", "min", "max", "n"})
ck("a categorical column is summarised as its composition",
   _ba.get("phase", {}).get("f1", {}).get("kind") == "categorical"
   and "share" in _ba["phase"]["f1"]["arms"][0])
ck("shares sum to one",
   abs(sum(_ba["phase"]["f1"]["arms"][0]["share"].values()) - 1.0) < 1e-6)
ck("an identifier column is not mistaken for a readout", "barcode" not in _ba)
ck("it works on factor names it has never seen", set(_ba["score"]) == {"f1", "f2"})
ck("a factor with one arm is not a comparison",
   not inputs.by_arm(_Obj(_fake_obs()), ["score"],
                     {f"S{i}": {"f1": "only"} for i in range(6)}, "sample", ["f1"]))
ck("an arm below the cell floor is dropped rather than quantiled",
   inputs.ARM_MIN_CELLS >= 20)
ck("no design, no section", not inputs.by_arm(_Obj(_fake_obs()), ["score"], {}, "sample", ["f1"]))

# TWO FACTORS WITH THE SAME PARTITION ARE ONE SPLIT. Drawing both shows one division of the
# samples twice, and a reader with two panels showing the same difference under two names has,
# on the page, two pieces of evidence. Keying the partition on (sample, level) PAIRS missed it
# entirely, because an aliased confounder almost never shares the vocabulary of the factor it is
# aliased with — a reagent version aliased with an age arm calls its levels v3/v4, not young/old.
_ali_des = {f"S{i}": {"bio": "y" if i < 3 else "o",
                      "reagent": "v3" if i < 3 else "v4",
                      "crossed": "a" if i % 2 else "b"} for i in range(6)}
_ali = inputs.by_arm(_Obj(_fake_obs()), ["score"], _ali_des, "sample",
                     ["bio", "reagent", "crossed"])
ck("an aliased pair is drawn once, not twice", sorted(_ali["score"]) == ["bio", "crossed"],
   str(sorted(_ali.get("score", {}))))
ck("and the alias is NAMED, never silently dropped",
   _ali["score"]["bio"]["aliased_with"] == ["reagent"])
ck("a genuinely crossed factor keeps its own panel",
   _ali["score"]["crossed"]["aliased_with"] == [])
ck("the page says which of the two the difference belongs to cannot be known",
   "not something this data can say" in _RP._by_arm_block(_ali, aware=False))
ck("it detects the alias across different level VOCABULARIES",
   "by_level" in pathlib.Path(inputs.__file__).read_text(),
   "keying on (sample, level) pairs cannot see young/aged aliased with v3/v4")

_html = _RP._by_arm_block(_ba, aware=False)
ck("the page says outright that it is a description and not a test",
   "not a test" in _html and "unit of replication is the sample" in _html)
ck("it draws with no plotting library", "<svg" in _html)
ck("it uses the shared palette rather than a second copy of it",
   "from .figure import CATEGORY_COLOURS" in pathlib.Path(
       Path(_RP.__file__)).read_text())
ck("a plugin claiming design_aware with nothing to split is NAMED on its page",
   "produced no per-cell column" in _RP._by_arm_block({}, aware=True))
ck("a plugin making no such claim gets no empty section",
   _RP._by_arm_block({}, aware=False) == "")
ck("the declaration REFUSES design_aware with no per-cell column",
   any(lvl == "ERROR" and "design_aware" in msg for lvl, msg in _DECL.check(
       {**_K["cellcycle"].spec, "design_aware": True, "produces": ["tables/x.csv"]})))
ck("the section is placed before the per-population panels",
   inspect.getsource(_RP.write_kernel).index("_by_arm_block")
   < inspect.getsource(_RP.write_kernel).index("_figure_section"))
# A PAGE IS BOUND BY THE FACTORS IT ACTUALLY SHOWS — a union of what it TESTS and what its
# per-arm section DISPLAYS. Widening the set of bound plugins while still computing the factors
# as an intersection with contrast terms gave every newly-included plugin an empty list, because
# a plugin that does not test the design has no terms to intersect: four pages went on showing
# results across the design with no constraint on them, and the binding looked considered.
ck("a page is bound by what it SHOWS as well as by what it TESTS",
   "_shown | _terms" in _clisrc,
   "intersecting only with contrast terms empties the bound for every plugin that does not test")
ck("the factors shown come from the per-arm section itself",
   "_by_arm.get(_n)" in _clisrc)
ck("and a plugin the constraint does not touch is not listed",
   "if _hit:" in _clisrc, "an empty list must not be recorded as a considered binding")

# ---------------------------------------------------------------------------------------------
# A DIAGNOSTIC IS USELESS ON THE PAGE OF THE PLUGIN THAT COMPUTED IT.
#
# One plugin's own summary reads "the check that a trajectory is not a cell-cycle axis". The
# trajectory is on a different plugin's page, and nothing connected the two — so the check was
# computed, reported, and never applied to the claim it exists to bound. The same shape as an
# upstream constraint that reaches an index and none of the pages a reader quotes from.
# ---------------------------------------------------------------------------------------------
print("\na diagnostic reaches the page carrying the claim it bounds")
import numpy as _np, pandas as _pd                                              # noqa: E402
_n = 3000
_r = _np.random.RandomState(0)
_t = _np.linspace(0, 1, _n)


class _Ord:
    obs = _pd.DataFrame({"ordering": _t,
                         "phase_score": _t * 0.8 + _r.normal(0, 0.3, _n),
                         "other_ordering": _t + _r.normal(0, 0.05, _n),
                         "unrelated": _r.normal(size=_n),
                         "flat": _np.ones(_n)})


_c = inputs.concordance(_Ord(), {"p1": ["ordering"], "p2": ["phase_score", "flat"],
                                 "p3": ["other_ordering", "unrelated"]})
ck("a plugin's number is compared with another plugin's", bool(_c.get("p1")))
ck("two orderings that agree are found",
   any(abs(x["rho"]) > 0.9 for x in _c["p1"]), str(_c.get("p1")))
ck("an ordering tracking a phase score is found",
   any(0.4 < abs(x["rho"]) < 0.9 for x in _c["p1"]))
ck("an unrelated column is reported too, not filtered away",
   any(abs(x["rho"]) < 0.1 for x in _c["p1"]),
   "silently dropping weak pairs would make the strong ones look selected")
ck("a constant column has no rank correlation and is skipped",
   not any("flat" in (x["a"]["column"], x["b"]["column"]) for x in _c.get("p1", [])))
ck("two columns from ONE plugin are that plugin's own business",
   not any(x["a"]["plugin"] == x["b"]["plugin"] for v in _c.values() for x in v))
ck("strongest first", [abs(x["rho"]) for x in _c["p1"]]
   == sorted((abs(x["rho"]) for x in _c["p1"]), reverse=True))
ck("too few overlapping cells is not a correlation",
   inputs.CONCORDANCE_MIN_CELLS >= 200)
_hb = _RP._concordance_block("p1", _c["p1"])
ck("the pair appears on the page of BOTH plugins",
   "p3" in _hb and "p1" in _RP._concordance_block("p3", _c["p3"]))
ck("the page names the other plugin, not just the column", "from " in _hb)
ck("it is not thresholded or starred",
   "*" not in _hb and "significant" not in _hb.lower())
ck("no pairs, no section", _RP._concordance_block("p1", []) == "")

# ---------------------------------------------------------------------------------------------
# A PLUGIN CANNOT CALL AN API THAT DOES NOT EXIST.
#
# `ctx.figure.SINGLE()` is a TypeError: SINGLE is a WIDTH IN INCHES, not a factory, and every
# shipped plugin writes `plt.subplots(figsize=(F.SINGLE, ...))`. Nothing static caught it —
# a fixture written against a misremembered API validated cleanly and would have failed inside
# the job, at the one step a pre-flight exists to make unnecessary.
# ---------------------------------------------------------------------------------------------
print("\na plugin cannot call an API that does not exist")
import ast as _ast                                                              # noqa: E402
from scprofile import figure as _FIG                                            # noqa: E402
from scprofile.plugin import Context as _Ctx                                    # noqa: E402

_SMOKE = {q.name: q.read_text() for q in
          (Path(__file__).resolve().parents[1] / "tests" / "smoke").glob("*.py")
          if not q.name.startswith("_")}
_ALLSRC = dict(_KSRC)
_ALLSRC.update({f"smoke/{k}": v for k, v in _SMOKE.items()})

# THE CLASS PLUS WHAT __init__ BINDS. `dir(Context)` lists methods and properties and none of
# the instance attributes — `ctx.log`, `ctx.headline`, `ctx.status` — so a check built on it
# alone reports every plugin in the tree as calling APIs that do not exist. A guard whose first
# run is all false positives is a guard that gets deleted.
_ctx_api = {n for n in dir(_Ctx) if not n.startswith("__")}
for _nd in _ast.walk(_ast.parse(pathlib.Path(_Ctx.__module__.replace(".", "/") + ".py").read_text()
                                if False else
                                (Path(__file__).resolve().parents[1] / "scprofile"
                                 / "plugin.py").read_text())):
    if isinstance(_nd, _ast.Assign):
        for _t in _nd.targets:
            for _sub in ([_t] if not isinstance(_t, _ast.Tuple) else _t.elts):
                if isinstance(_sub, _ast.Attribute) and isinstance(_sub.value, _ast.Name) \
                        and _sub.value.id == "self":
                    _ctx_api.add(_sub.attr)
_fig_api = {n for n in dir(_FIG) if not n.startswith("_")}
_bad_ctx, _bad_fig, _bad_call = [], [], []
for _name, _src in sorted(_ALLSRC.items()):
    try:
        _tree = _ast.parse(_src)
    except SyntaxError as e:
        _bad_ctx.append(f"{_name}: does not parse ({e})")
        continue
    for _nd in _ast.walk(_tree):
        if not isinstance(_nd, _ast.Attribute):
            continue
        _v = _nd.value
        # ctx.<attr>
        if isinstance(_v, _ast.Name) and _v.id == "ctx" and _nd.attr not in _ctx_api:
            _bad_ctx.append(f"{_name}: ctx.{_nd.attr}")
        # ctx.figure.<attr>  /  F.<attr> where F = ctx.figure
        if isinstance(_v, _ast.Attribute) and getattr(_v, "attr", "") == "figure" \
                and isinstance(getattr(_v, "value", None), _ast.Name) \
                and _v.value.id == "ctx" and _nd.attr not in _fig_api:
            _bad_fig.append(f"{_name}: ctx.figure.{_nd.attr}")
    # a non-callable used as a call: ctx.figure.SINGLE() and friends
    for _nd in _ast.walk(_tree):
        if isinstance(_nd, _ast.Call) and isinstance(_nd.func, _ast.Attribute):
            _f = _nd.func
            _base = _f.value
            _is_fig = (isinstance(_base, _ast.Attribute) and _base.attr == "figure") or \
                      (isinstance(_base, _ast.Name) and _base.id == "F")
            if _is_fig and _f.attr in _fig_api and not callable(getattr(_FIG, _f.attr, None)):
                _bad_call.append(f"{_name}: {_f.attr}() — it is a "
                                 f"{type(getattr(_FIG, _f.attr)).__name__}, not a function")

ck("every ctx.<attr> a plugin uses exists on Context", not _bad_ctx, str(_bad_ctx[:4]))
ck("every ctx.figure.<attr> exists in figure.py", not _bad_fig, str(_bad_fig[:4]))
ck("and nothing calls a figure CONSTANT as if it were a factory", not _bad_call,
   str(_bad_call[:4]))
ck("the check covers the test fixtures too, which is where it was found",
   any(k.startswith("smoke/") for k in _ALLSRC), str(sorted(_ALLSRC)[:3]))

# ---------------------------------------------------------------------------------------------
# WHAT THE FIRST REAL RUN OF THE CONTRAST FOUND.
#
# Two failures, both invisible for as long as the plan's decision never reached the run:
#
#   de       LinAlgError: Singular matrix. Every MAIN EFFECT is rank-tested by `_identifiable`
#            and the interaction was appended without being asked, so a population with an empty
#            cell of the a-by-b table killed the whole plugin instead of dropping one term.
#   velocity IORegistryError, from ONE unreadable file among 569 candidates found by a search
#            over 21,408 directories. A candidate that cannot be opened is a candidate that does
#            not match; only the h5py probe was guarded and the read beneath it was not.
# ---------------------------------------------------------------------------------------------
print("\nthe first real run of the contrast, and what it found")
import numpy as _np2, pandas as _pd2                                            # noqa: E402

_desrc = _KSRC["de.py"]
_ie = None
for _nd in _ast.parse(_desrc).body:
    if getattr(_nd, "name", "") == "_interaction_estimable":
        _ns2 = {}
        exec(compile(_ast.Module([_nd], []), "<x>", "exec"), {"__builtins__": __builtins__}, _ns2)
        _ie = _ns2["_interaction_estimable"]
ck("the interaction gets the same rank test the main effects get", _ie is not None,
   "an interaction appended without being asked is the Singular matrix this prevents")
if _ie:
    _full = _pd2.DataFrame({"a": list("yyyyoooo"), "b": list("cchhcchh")})
    _gap = _pd2.DataFrame({"a": list("yyoo"), "b": list("cccH")})
    _one = _pd2.DataFrame({"a": list("yyyy"), "b": list("chch")})
    ck("a replicated 2x2 is estimable", _ie(_full, "a", "b", _np2, _pd2) is True)
    ck("an empty cell of the two-way table is NOT", _ie(_gap, "a", "b", _np2, _pd2) is False)
    ck("a factor with one level here is NOT", _ie(_one, "a", "b", _np2, _pd2) is False)
    ck("a full 3x2 is estimable, so the test is not just a 2x2 rule",
       _ie(_pd2.DataFrame({"a": list("yyoomm"), "b": list("chchch")}), "a", "b", _np2, _pd2) is True)
ck("the run asks before it adds", "_interaction_estimable(sub_obs" in _desrc)
# AN INTERACTION IN THE MODEL AND NOT IN THE OUTPUT. The results loop iterates the MAIN EFFECTS,
# so `age:diet` entered the design, moved every coefficient in it, and produced no row. The
# study's primary readout was fitted and never reported, and the caveat said it had been ADDED -
# true, and read as though it had been tested. Measured on the real table of run 693758: terms
# were `age` and `diet`, and nothing else.
ck("an interaction that is added is also CONTRASTED",
   "if pop in interacted:" in _desrc and "DeseqStats(dds, contrast=vec" in _desrc,
   "adding a term to the formula is not testing it")
ck("the contrast column is taken from the design matrix the fit built",
   'dds.obsm.get("design_matrix")' in _desrc,
   "reconstructing what formulaic would have named it guesses at another library's internals")
ck("an interaction spread over several columns is NAMED, not silently skipped",
   "not_interacted.setdefault" in _desrc,
   "a factor with three levels spreads its interaction over columns an F-test would combine")
ck("and a population that cannot fit it is NAMED, not silently main-effects-only",
   "not_interacted" in _desrc and "WAS NOT TESTED" in _desrc.upper())

from scprofile import sources as _SRC                                           # noqa: E402
_srcsrc = pathlib.Path(_SRC.__file__).read_text()
ck("an unreadable candidate is skipped rather than raised",
   "skipped, not matched" in _srcsrc)
ck("the guard covers every source kind, not only the one that failed",
   _srcsrc.count("skipped, not matched") >= 3, "loom, h5ad and mtx all open foreign files")


class _Boom:
    kind, path = "h5ad", Path("/nonexistent/boom.h5ad")


_said = []
try:
    _SRC.attach.__globals__["load"]
    _orig_load = _SRC.load
    _SRC.load = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("unreadable"))
    try:
        _SRC.attach(type("A", (), {"n_obs": 0, "n_vars": 0, "obs_names": [], "var_names": [],
                                   "obs": _pd2.DataFrame()})(),
                    [_Boom()], log=_said.append)
        _raised = False
    except RuntimeError:
        _raised = True
    except Exception:
        _raised = False          # any other failure is the stub, not the guard
    finally:
        _SRC.load = _orig_load
except Exception:
    _raised = None
ck("a raising candidate does not propagate out of the search", _raised is not True,
   "one unopenable file among hundreds must not end a plugin")

print("\n" + ("nothing here assumes one dataset" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
