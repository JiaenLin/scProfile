"""The reporter re-launches the plugin, and that was a SECOND EXECUTION PHASE nobody recorded.

`run` prints "18 instances in 1 wave" and that is the run phase. Building the report then invoked
the same plugins again - once per arm pair and, on a design crossing more than two arms, once more
over all of them - through `report._native_compare`. Those launches had:

    no in.json      the spec went to a NamedTemporaryFile, so nothing on disk said what the
                    phase had been handed
    no out.json     so it re-executed unconditionally on every report build: a plain run, a
                    --resume, and every `scprofile report` rebuild alike
    no schedule row "How this ran" answered the question with the run phase only
    no core share   the env came from `with_env_bin` alone, NOT `manifest.env_for_kernel`, so
                    the six thread caps were absent - and absent means INHERITED. A job script
                    exporting OMP_NUM_THREADS=$NCPUS handed 64 to every launch.
    no timeout      3600 was a literal in two places and 300 in a third, and `--timeout` could
                    lower none of them because the parameter chain did not exist
    no cardinality  the number of launches was stated nowhere, and the gate on the across-arms
                    one was a bare `len(_cross) > 2`

AND THE PHANTOM. `resume.discover` accepts ANY non-empty subdirectory of a plugin as an instance,
and this phase creates one. So a run in which every instance SUCCEEDED reported `1 died` - because
the reporting had worked - and that verdict travelled: `scprofile status`, `check --out` answering
"every instance finished" with FALSE and "1 outstanding", and every `landscape.scan` that reached
the run through `--reuse-from`.

THE FIRST SECTION BELOW IS A REPRODUCTION, AND IT IS FIRST ON PURPOSE. A guard was proposed for
the phantom that keyed on the PARENT directory being named `compare` and confirmed itself with a
manifest read. It could never fire. `discover` walks exactly two levels, so the row it produces
IS `kernels/<plugin>/compare`: that directory's own name is `compare`, its parent is the PLUGIN
name, and it holds neither `in.json` nor `out.json` because both are written one level deeper.
The reproduction pins that shape so the guard cannot drift back onto a directory shape that never
occurs.
"""
import contextlib
import inspect
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scprofile import kernels as _K                                       # noqa: E402
from scprofile import report as _RP                                       # noqa: E402
from scprofile import resume as _RS                                       # noqa: E402
from scprofile import runner as _RN                                       # noqa: E402

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


def _tree(root, plugin="cellchat", units=("ctrl", "treated"),
          phase_labels=("diet", "_across_arms")):
    """A run directory shaped exactly as the reporter leaves one: units, and a compare phase."""
    k = Path(root) / "kernels" / plugin
    for u in units:
        (k / u).mkdir(parents=True, exist_ok=True)
        (k / u / "in.json").write_text("{}", encoding="utf-8")
        (k / u / "out.json").write_text(json.dumps({"figures": [f"{u}.png"]}), encoding="utf-8")
    for lab in phase_labels:
        (k / _RS.COMPARE_DIRNAME / lab / "figures").mkdir(parents=True, exist_ok=True)
        (k / _RS.COMPARE_DIRNAME / lab / "figures" / "nativecmp_x.png").write_bytes(b"")
    return k


# ---------------------------------------------------------------------------------------------
# 1. THE REPRODUCTION. What `discover` actually enumerates, before anything is asserted about
#    the guard that has to work at that level.
# ---------------------------------------------------------------------------------------------
d1 = Path(tempfile.mkdtemp())
k1 = _tree(d1)
phase_dir = k1 / _RS.COMPARE_DIRNAME

# The level `discover` walks is kernels/<plugin>/<child>. Reconstructed here rather than assumed,
# because everything below depends on it.
children = sorted(c.name for c in k1.iterdir() if c.is_dir())
check(children == ["compare", "ctrl", "treated"],
      f"the children of kernels/<plugin> are {children} - the phase directory is meant to sit "
      f"beside the units, at the level discover enumerates")
check(phase_dir.is_dir() and phase_dir.name == _RS.COMPARE_DIRNAME,
      "the directory discover reaches is the phase directory itself, and its OWN name is the "
      "phase name")
check(phase_dir.parent.name == "cellchat",
      f"the phase directory's parent is {phase_dir.parent.name!r} - the PLUGIN name, not "
      f"'compare'. A guard keyed on the parent's name could never fire here.")
check(not (phase_dir / "in.json").exists() and not (phase_dir / "out.json").exists(),
      "the phase directory holds neither manifest - both are written one level deeper, under "
      "compare/<label>/ - so a guard that confirms itself with a manifest read at this level "
      "falls through and never fires")
check(any((phase_dir / lab / "figures").is_dir() for lab in ("diet", "_across_arms")),
      "the manifests and figures live one level DOWN, which is the level discover does not reach")
# and the rule that was there before the guard accepts it, which is the whole defect
check((phase_dir / "out.json").exists() or any(phase_dir.iterdir()),
      "the pre-guard rule - out.json OR any non-empty directory - accepted the phase directory; "
      "if it no longer does, this test's premise has changed")
check(_RS.state(phase_dir)[0] == _RS.DIED,
      f"a phase directory read as an INSTANCE is {_RS.state(phase_dir)[0]}, and it was `died` - "
      f"the states are the manifest's and this directory is not a manifest's")

# ---------------------------------------------------------------------------------------------
# 2. THE PHANTOM IS GONE, and a successful run says so.
# ---------------------------------------------------------------------------------------------
found = _RS.discover(d1)
check(("cellchat", "compare") not in found,
      f"discover still reports the compare PHASE as an instance: {found}")
check(sorted(found) == [("cellchat", "ctrl"), ("cellchat", "treated")],
      f"discover should report the two units and nothing else; got {found}")
counts = _RS.summarise(_RS.survey(d1, found))
check(counts == {"done": 2},
      f"a fully successful run surveys as {counts} - it reported 1 died among its successes "
      f"because the REPORTING had worked")
check(_RS.outstanding(_RS.survey(d1, found)) == [],
      "nothing is outstanding on a run where every instance finished")
check(all(st in _RS.FINISHED for _p, _u, st, _w, _n in _RS.survey(d1, _RS.discover(d1))),
      "`check --out` asks exactly this and answered FALSE with '1 outstanding'")

# ---------------------------------------------------------------------------------------------
# 3. A UNIT MAY LEGITIMATELY BE CALLED `compare`, and hiding a real instance is the same defect
#    facing the other way. An instance directory has its own manifests; a phase directory has not.
# ---------------------------------------------------------------------------------------------
d2 = Path(tempfile.mkdtemp())
_tree(d2, plugin="cellchat")
ku = Path(d2) / "kernels" / "othertool" / "compare"
ku.mkdir(parents=True)
(ku / "in.json").write_text("{}", encoding="utf-8")
(ku / "out.json").write_text(json.dumps({"figures": ["a.png"]}), encoding="utf-8")
check(("othertool", "compare") in _RS.discover(d2),
      "a UNIT named `compare` - staged with its own in.json and out.json - is an instance and "
      "must survive the guard")
check(_RS.phase_of(ku) is None, "an instance directory is not a phase, whatever it is named")
check(_RS.phase_of(Path(d2) / "kernels" / "cellchat" / "compare") == _RS.COMPARE_DIRNAME,
      "a phase directory is a phase")

# ---------------------------------------------------------------------------------------------
# 4. NOT SILENTLY DROPPED - enumerated as what it is.
# ---------------------------------------------------------------------------------------------
ph = _RS.phases(d1)
check([(p, k) for p, k, _r in ph] == [("cellchat", "compare")],
      f"resume.phases should name the phase the run holds; got {ph}")

# ---------------------------------------------------------------------------------------------
# 5. THE CORE SHARE. The env came from `with_env_bin` alone, so the six thread caps were absent -
#    and absent means inherited from whatever the job script exported.
# ---------------------------------------------------------------------------------------------
_saved = os.environ.get("OMP_NUM_THREADS")
os.environ["OMP_NUM_THREADS"] = "64"                      # what a PBS script exports for itself
try:
    fake_exe = Path(tempfile.mkdtemp()) / "bin" / "python"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.write_text("", encoding="utf-8")
    old_way = _RN.with_env_bin(str(fake_exe))
    check(old_way.get("OMP_NUM_THREADS") == "64",
          "the premise: `with_env_bin` alone does not touch the thread caps, so the child "
          "inherited the job's 64. If this changed, remeasure this test.")
    new_way = _RP._phase_env(str(fake_exe), inp="/tmp/x/in.json", cores=4)
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        check(new_way.get(var) == "4",
              f"{var} is {new_way.get(var)!r} for a compare launch allocated 4 cores")
    check(new_way.get("SCPROFILE_IN") == "/tmp/x/in.json",
          "a launch's env names ITS OWN manifest - one env object was built once and reused for "
          "all three launches, and one variable cannot name three files")
    check(str(fake_exe.parent.resolve()) in new_way.get("PATH", "").split(os.pathsep),
          "the plugin's own bin is still first on PATH - that is why with_env_bin was there")
    probe = _RP._phase_env(str(fake_exe), cores=4)
    check(probe.get("OMP_NUM_THREADS") == "4",
          "the --phases probe LOADS the plugin, so the caps matter there too")
    check("SCPROFILE_IN" not in probe,
          "the probe reads no manifest; an empty SCPROFILE_IN would be a path that is not a file, "
          "which is a worse answer than the variable being absent")
finally:
    if _saved is None:
        os.environ.pop("OMP_NUM_THREADS", None)
    else:
        os.environ["OMP_NUM_THREADS"] = _saved

# ---------------------------------------------------------------------------------------------
# 6. THE PARAMETER CHAIN THAT CARRIES `--timeout`, which did not exist.
#
#    EVERYTHING IN THIS SECTION IS A PREMISE AND NONE OF IT IS A TEST OF THE CHAIN. It asks
#    `inspect.signature` whether the parameters EXIST and greps the source for two spellings -
#    so it is satisfied by a `write_all` that reads the run's limits and then forwards `None`,
#    by a `write_kernel` that accepts them and drops them, and by an `_arm_content` that passes
#    `timeout=None, cores=None` in so many words. All three were tried as mutations and all
#    three left this section green, because the only thing this file EXECUTED was
#    `_native_compare` and `_compare_launch`, both called below with the limits handed to them
#    directly. A signature is not a wire.
#
#    Section 10 drives `write_all` itself and reads what arrives at the far end. This section
#    stays because a broken signature should fail HERE, with a one-line reason, rather than as a
#    TypeError inside a page build.
# ---------------------------------------------------------------------------------------------
src = Path(_RP.__file__).read_text(encoding="utf-8")
check("timeout=3600" not in src,
      "a 3600s ceiling nobody asked for, that no --timeout could lower, is still hardcoded in "
      "report.py")
for fn in (_RP.write_kernel, _RP._arm_content, _RP._native_compare):
    params = inspect.signature(fn).parameters
    check("timeout" in params and "cores" in params,
          f"{fn.__name__} does not carry the run's timeout and core budget")
check("payload.get(\"timeout\")" in src and "payload.get(\"cores\")" in src,
      "write_all must read the run's own limits from report.json - not from the command line, "
      "because a rebuild months later must run the phase under the limits of the RUN")
check(_RP._PROBE_TIMEOUT == 300,
      "the probe's own limit is named rather than a literal; if it moved, say so here")

# ---------------------------------------------------------------------------------------------
# 7. ONE LAUNCH, WITH THE RECORD THAT PROVES IT HAPPENED - and does not happen twice.
# ---------------------------------------------------------------------------------------------
d3 = Path(tempfile.mkdtemp())
k3 = _tree(d3, plugin="cellchat", phase_labels=())
entry = d3 / "fake_entry.py"
# THE STAND-IN PLUGIN. It records that it was launched, what environment it was launched in, and
# it can be told to be SLOW - `PHASES_SLEEP` in the probe, `FAKE_SLEEP` in the launch itself.
# The sleeps are not decoration: a timeout is only real if the process is actually killed by it,
# and a limit asserted only against the RECORD is satisfied by a launch that ran under a
# different one. It records itself BEFORE it sleeps and draws AFTER, so a killed launch has the
# unmistakable signature of one that started and never finished.
entry.write_text(
    "import json, os, sys, time\n"
    "from pathlib import Path\n"
    "if sys.argv[1] == '--phases':\n"
    "    time.sleep(float(os.environ.get('PHASES_SLEEP', '0')))\n"
    "    print('run compare'); raise SystemExit(0)\n"
    "spec = json.loads(Path(sys.argv[3]).read_text())\n"
    "log = Path(os.environ['LAUNCH_LOG'])\n"
    "log.write_text(str(int(log.read_text() or 0) + 1))\n"
    "Path(os.environ['ENV_LOG']).write_text(json.dumps(\n"
    "    {k: os.environ.get(k) for k in ('OMP_NUM_THREADS', 'SCPROFILE_IN')}))\n"
    "time.sleep(float(os.environ.get('FAKE_SLEEP', '0')))\n"
    "out = Path(spec['out_dir']); (out / 'figures').mkdir(parents=True, exist_ok=True)\n"
    "(out / 'figures' / 'nativecmp_x.png').write_bytes(b'')\n"
    "raise SystemExit(int(os.environ.get('FAKE_EXIT', '0')))\n",
    encoding="utf-8")
launch_log = d3 / "launches.txt"
launch_log.write_text("0", encoding="utf-8")
env_log = d3 / "env.json"
os.environ["LAUNCH_LOG"], os.environ["ENV_LOG"] = str(launch_log), str(env_log)

cdir = k3 / _RS.COMPARE_DIRNAME / "diet"
spec = {"pair": "diet", "units": {"ctrl": str(k3 / "ctrl"), "treated": str(k3 / "treated")},
        "out_dir": str(cdir)}
kw = dict(exe=sys.executable, entry=entry, plugin_file=d3 / "cellchat.py", cdir=cdir,
          kernel="cellchat", version="1.2.3", kind="arm_pair", label="diet",
          cores=6, timeout=1800, log=lambda *_a: None)
rec = _RP._compare_launch(spec=dict(spec), **kw)

check((cdir / "in.json").is_file(),
      "the spec went to a NamedTemporaryFile, so nothing on disk said what the phase was handed")
check(json.loads((cdir / "in.json").read_text())["pair"] == "diet",
      "the launch's in.json is the spec it was actually given")
check((cdir / "out.json").is_file(), "a launch with no out.json is a launch that re-runs forever")
check(rec["status"] == "ok" and rec["exit"] == 0, f"the launch did not succeed: {rec}")
check(rec["cores"] == 6 and rec["timeout"] == 1800,
      f"the record must state the share and the limit this launch ran under; got {rec}")
check(isinstance(rec["seconds"], float), "no duration was recorded")
check(rec["figures"] == ["nativecmp_x.png"], f"the record does not name what it drew: {rec}")
check(rec["kernel"] == "cellchat" and rec["version"] == "1.2.3",
      "a record with no plugin version cannot be told apart from one produced by other code")
seen = json.loads(env_log.read_text())
check(seen["OMP_NUM_THREADS"] == "6",
      f"the CHILD saw OMP_NUM_THREADS={seen['OMP_NUM_THREADS']!r}; the share is only real if the "
      f"process that runs BLAS gets it")
check(seen["SCPROFILE_IN"] == str(cdir / "in.json"),
      "the child finds its manifest the same way every other phase does")
check(launch_log.read_text() == "1", "the plugin should have been launched exactly once")

again = _RP._compare_launch(spec=dict(spec), **kw)
check(again.get("reused") is True and launch_log.read_text() == "1",
      "the phase re-executed on EVERY report build - a plain run, a --resume and every rebuild "
      "alike - because nothing on disk could say it had already run")

# and a unit recomputed underneath it is not skipped: the spec carries paths, not numbers
(k3 / "ctrl" / "out.json").write_text(json.dumps({"figures": ["ctrl.png", "extra.png"]}),
                                      encoding="utf-8")
third = _RP._compare_launch(spec=dict(spec), **kw)
check(not third.get("reused") and launch_log.read_text() == "2",
      "a side recomputed between two builds leaves the spec byte-identical; skipping on the spec "
      "alone would place the last build's figures over this build's units")

# the digest must not change with how the run directory was SPELLED: `run` and `scprofile
# report` can address the same directory differently, and a digest that moved with the spelling
# would make the skip fire on neither
_dig_a = _RP._phase_inputs_digest({"units": {"u": str(k3 / "ctrl")}, "out_dir": str(cdir)},
                                  [k3 / "ctrl"])
_dig_b = _RP._phase_inputs_digest(
    {"units": {"u": os.path.join(str(k3), ".", "ctrl")}, "out_dir": os.path.join(str(cdir), ".")},
    [k3 / "ctrl"])
check(_dig_a == _dig_b,
      "two spellings of one directory gave two digests, so the launch would be redone on every "
      "rebuild that typed the path differently")

# a record whose figures have been deleted is not a reason to skip: the reuse exists so the
# panels can be PLACED without re-drawing them
(cdir / "figures" / "nativecmp_x.png").unlink()
fourth = _RP._compare_launch(spec=dict(spec), **kw)
check(not fourth.get("reused") and launch_log.read_text() == "3",
      "a launch was reused although the figures it recorded are gone - the page would lose the "
      "panels and cite nothing")

# A NEW PLUGIN VERSION IS A NEW ANSWER TO THE SAME QUESTION, and reusing across one is how a
# report comes to show figures the installed plugin cannot produce. The version is in the record
# and in the reuse gate; only the gate was ever exercised for the digest, so a mutation that
# dropped `version` from the comparison left the version RECORDED, correctly, on a launch that
# had not been re-run. Recorded and enforced are different claims and this asserts the second.
fifth = _RP._compare_launch(spec=dict(spec), **dict(kw, version="9.9.9"))
check(not fifth.get("reused") and launch_log.read_text() == "4",
      f"a launch recorded under plugin version 1.2.3 was REUSED for version 9.9.9; the page "
      f"would carry panels the installed plugin never drew: {fifth}")
check(fifth["version"] == "9.9.9",
      f"the re-run recorded the old version, so the next build reuses it again: {fifth}")
sixth = _RP._compare_launch(spec=dict(spec), **dict(kw, version="9.9.9"))
check(sixth.get("reused") is True and launch_log.read_text() == "4",
      "and the SAME version still reuses - a gate that re-runs unconditionally is the defect "
      "this file opened with, arriving through the version instead of the digest")

# THE TIMEOUT IS THE PROCESS'S, NOT THE RECORD'S. `out.json` states the limit the launch ran
# under, and asserting only that leaves the two free to disagree - a launch running to 3600s
# while its record says 1800 is a LYING RECORD, and the run's document would then be evidence
# for a limit that was never applied. So this one is measured on a child that will not finish
# in time: the limit is real if, and only if, the process dies.
os.environ["FAKE_SLEEP"] = "4"
slow_dir = k3 / _RS.COMPARE_DIRNAME / "slow"
_before = launch_log.read_text()
try:
    slow = _RP._compare_launch(spec=dict(spec, out_dir=str(slow_dir)),
                               **dict(kw, cdir=slow_dir, label="slow", timeout=1))
finally:
    os.environ.pop("FAKE_SLEEP", None)
check(launch_log.read_text() != _before,
      "the slow child never started, so nothing here measures a timeout")
check(slow["status"] == "failed" and slow["exit"] is None,
      f"a child sleeping 4s under `timeout=1` finished normally, so the limit the record names "
      f"is not the limit the process ran under: {slow}")
check("timed out" in str(slow.get("error") or "").lower()
      or "timeout" in str(slow.get("error") or "").lower(),
      f"the launch failed but not by the clock, so this measures something else: {slow}")
check(slow["timeout"] == 1 and slow["seconds"] < 3,
      f"the record must name the limit that killed it, and the duration must be that limit and "
      f"not the child's own: {slow}")
check(slow["figures"] == [],
      "the child draws AFTER it sleeps; figures here would mean it was never interrupted")

# a failed launch is recorded as one, and is retried rather than reused
os.environ["FAKE_EXIT"] = "3"
bad_dir = k3 / _RS.COMPARE_DIRNAME / "fails"
bad = _RP._compare_launch(spec=dict(spec, out_dir=str(bad_dir)), **dict(kw, cdir=bad_dir,
                                                                       label="fails"))
check(bad["status"] == "failed" and bad["exit"] == 3, f"a refusal must arrive as one: {bad}")
retry = _RP._compare_launch(spec=dict(spec, out_dir=str(bad_dir)), **dict(kw, cdir=bad_dir,
                                                                         label="fails"))
check(not retry.get("reused"), "a FAILED launch must be retried, never reused")
os.environ.pop("FAKE_EXIT", None)

# and none of the records it wrote turned the phase back into an instance
check(("cellchat", "compare") not in _RS.discover(d3),
      f"writing the records re-created the phantom: {_RS.discover(d3)}")

# ---------------------------------------------------------------------------------------------
# 8. THE WHOLE PHASE, AND THE CARDINALITY IT NOW STATES.
# ---------------------------------------------------------------------------------------------
d4 = Path(tempfile.mkdtemp())
k4 = _tree(d4, plugin="cellchat", units=("ctrl", "hi"), phase_labels=())
(k4 / "cellchat.py").write_text("# a plugin\n", encoding="utf-8")
shutil.copy(entry, d4 / "fake_entry.py")
launch_log.write_text("0", encoding="utf-8")


class _FakeKernel:
    spec = {"version": "1.2.3"}
    name = "cellchat"


_old_disc, _old_entry, _old_interp = _K.discover, _K.SHARED_ENTRY, _RN.interpreter
_K.discover = lambda *a, **k: {"cellchat": _FakeKernel()}
_K.SHARED_ENTRY = d4 / "fake_entry.py"
_RN.interpreter = lambda *a, **k: (sys.executable, "the test's own interpreter")
try:
    design = {"s1": {"diet": "ctrl"}, "s2": {"diet": "hi"}}
    units = [{"unit": "ctrl", "dir": "kernels/cellchat/ctrl"},
             {"unit": "hi", "dir": "kernels/cellchat/hi"}]
    from scprofile.compare_panel import arm_pairs                          # noqa: E402
    drawn = _RP._native_compare("cellchat", {}, {"ctrl": [], "hi": []}, design,
                                arm_pairs(design), d4, units,
                                declared={}, timeout=900, cores=8)
finally:
    _K.discover, _K.SHARED_ENTRY, _RN.interpreter = _old_disc, _old_entry, _old_interp

prec = k4 / _RS.COMPARE_DIRNAME / _RS.PHASE_RECORD
check(prec.is_file(), "the phase writes no record of itself, so its cardinality is stated nowhere")
if prec.is_file():
    rec4 = json.loads(prec.read_text())
    card = rec4.get("cardinality") or {}
    check(card.get("launched") == 1 and card.get("ran") == 1,
          f"one arm pair, one launch: {card}")
    check(card.get("not_launched") == 1 and "more than two arms" in rec4.get("across_arms_gate",
                                                                            ""),
          f"the across-arms gate was a bare `len(_cross) > 2` and appeared in no document of the "
          f"run; it must say what it is and why it did not fire: {rec4.get('across_arms_gate')!r}")
    check([L["cores"] for L in rec4["launches"]] == [8]
          and [L["timeout"] for L in rec4["launches"]] == [900],
          f"the phase must run under the RUN's budget and limit: {rec4['launches']}")
    check(rec4.get("is_instance") is False,
          "the record says what the directory is, so a resume does not have to guess from a name")
check(launch_log.read_text() == "1",
      f"one launchable pair should be one launch; the log says {launch_log.read_text()}")
check(("cellchat", "compare") not in _RS.discover(d4),
      f"a real phase run re-created the phantom: {_RS.discover(d4)}")

# ---------------------------------------------------------------------------------------------
# 9. AND IT HAS A ROW IN "How this ran", which described the run phase only.
# ---------------------------------------------------------------------------------------------
block = _RP._schedule_block(
    {"schedule": [[{"plugin": "cellchat", "unit": "ctrl", "cores": 8, "seconds": 12.0,
                    "outcome": "ok"}]], "cores": 8, "timeout": 900},
    phases=_RS.phases(d4))
check("compare" in block and "SECOND execution phase" in block,
      "the schedule table still answers 'how this ran' with the run phase alone")
check(block.count("<tr>") >= 4,
      f"one header, one instance, one launch and one not-launched row were expected; the table "
      f"has {block.count('<tr>')} rows")


def _fake_run_tree(root, units=("ctrl", "hi"), table=False):
    """A run directory `write_all` and `_native_compare` can both be pointed at."""
    k = Path(root) / "kernels" / "cellchat"
    rows = []
    for u in units:
        (k / u).mkdir(parents=True, exist_ok=True)
        (k / u / "in.json").write_text("{}", encoding="utf-8")
        (k / u / "out.json").write_text(json.dumps({"figures": []}), encoding="utf-8")
        if table:
            # The edge table `unit_network` names. `_arm_content` reads it and returns EMPTY
            # without two of them - and an empty return never reaches `_native_compare`, so a
            # drive missing this file would pass section 10 by never testing anything.
            (k / u / "net.csv").write_text("source,target,prob\nA,B,1.0\nB,C,2.0\n",
                                           encoding="utf-8")
        rows.append({"unit": u, "dir": f"kernels/cellchat/{u}", "metrics": {}})
    (k / "cellchat.py").write_text("# a plugin\n", encoding="utf-8")
    shutil.copy(entry, Path(root) / "fake_entry.py")
    launch_log.write_text("0", encoding="utf-8")
    env_log.write_text("{}", encoding="utf-8")
    return k, rows


@contextlib.contextmanager
def _plugin_machinery(root):
    """The plugin discovery, entry point and interpreter, all pointed at the stand-in above."""
    _o = (_K.discover, _K.SHARED_ENTRY, _RN.interpreter)
    _K.discover = lambda *a, **k: {"cellchat": _FakeKernel()}
    _K.SHARED_ENTRY = Path(root) / "fake_entry.py"
    _RN.interpreter = lambda *a, **k: (sys.executable, "the test's own interpreter")
    try:
        yield
    finally:
        _K.discover, _K.SHARED_ENTRY, _RN.interpreter = _o


_DESIGN = {"s1": {"diet": "ctrl"}, "s2": {"diet": "hi"}}
_UNITS = [{"unit": "ctrl", "dir": "kernels/cellchat/ctrl"},
          {"unit": "hi", "dir": "kernels/cellchat/hi"}]


def _drive_native(root, *, timeout, cores, design=None, units=None):
    """(drawn, everything it printed) - the phase run for real, quietly."""
    from scprofile.compare_panel import arm_pairs as _pairs                # noqa: E402

    dsg = _DESIGN if design is None else design
    uni = _UNITS if units is None else units
    buf = io.StringIO()
    with _plugin_machinery(root), contextlib.redirect_stdout(buf):
        drawn = _RP._native_compare("cellchat", {}, {u["unit"]: [] for u in uni}, dsg,
                                    _pairs(dsg), root, uni,
                                    declared={}, timeout=timeout, cores=cores)
    return drawn, buf.getvalue()


# ---------------------------------------------------------------------------------------------
# 10. THE CHAIN, DRIVEN FROM THE TOP. Section 6 asks whether the parameters exist; this asks
#     what actually arrives, by calling the function a report build calls - `write_all` - with a
#     payload that declares `timeout: 900, cores: 8` the way `report.json` does, and reading the
#     limits off the far end of the chain in three places: the arguments `_native_compare` was
#     handed, the launch records the phase wrote, and THE ENVIRONMENT THE CHILD PROCESS SAW.
#
#     Nothing between those ends is stubbed. `_native_compare` is wrapped rather than replaced,
#     so one drive proves both that the numbers travelled and that they were applied - and a
#     forward that is dropped anywhere along `write_all -> write_kernel -> _arm_content ->
#     _native_compare -> _compare_launch -> _phase_env` fails here at the point it was dropped.
#
#     THE FAILURE THIS CATCHES IS `cores=None`, and it is worse than a smaller share: the six
#     thread caps are set by `manifest.env_for_kernel` under `if cores:`, so None sets NONE of
#     them and the child inherits the job script's `OMP_NUM_THREADS`. A dropped forward is not a
#     degraded core share, it is the total absence of one, which is the state this whole file
#     exists to close.
# ---------------------------------------------------------------------------------------------
d5 = Path(tempfile.mkdtemp())
k5, rows5 = _fake_run_tree(d5, table=True)
payload5 = {
    # The two keys `run` writes and `write_all` reads back. A rebuild months later runs the
    # phase under the limits of the RUN, so they come from here and not from a command line.
    "timeout": 900, "cores": 8,
    "design": _DESIGN,
    "report_spec": {"cellchat": {"unit_network": {"table": "net.csv", "source": "source",
                                                  "target": "target", "weight": "prob"}}},
    "kernels": {"cellchat": {"status": "ok", "per_unit": True, "units": rows5,
                             "spec": {"native_plots": {}}}},
    "cannot_show": {}, "summaries": {}, "merged": {},
}

_seen_kw = {}
_real_native = _RP._native_compare


def _recording_native(*a, **kw):
    """Record what the chain delivered, then run the real phase with it."""
    _seen_kw.update(kw)
    return _real_native(*a, **kw)


_noise = io.StringIO()
try:
    _RP._native_compare = _recording_native
    with _plugin_machinery(d5), contextlib.redirect_stdout(_noise):
        _RP.write_all(d5, payload5)
finally:
    _RP._native_compare = _real_native

check(bool(_seen_kw),
      "`write_all` never reached the compare phase at all, so this section measures nothing - "
      "the payload below it no longer satisfies `_arm_content` (two units, an edge table each, "
      "a `unit_network` declaration and a design)")
check(_seen_kw.get("timeout") == 900,
      f"the run declared `timeout: 900` and the phase was handed {_seen_kw.get('timeout')!r}; "
      f"the forward is dropped somewhere in write_all -> write_kernel -> _arm_content")
check(_seen_kw.get("cores") == 8,
      f"the run declared `cores: 8` and the phase was handed {_seen_kw.get('cores')!r}. None is "
      f"not a small share - env_for_kernel sets the six thread caps only `if cores:`, so None "
      f"sets none of them and the child inherits the node's count")
_rec5 = k5 / _RS.COMPARE_DIRNAME / _RS.PHASE_RECORD
check(_rec5.is_file(), "a page built by write_all wrote no phase record")
if _rec5.is_file():
    _L5 = json.loads(_rec5.read_text()).get("launches") or []
    check([L.get("cores") for L in _L5] == [8] and [L.get("timeout") for L in _L5] == [900],
          f"the launches a real page build made do not carry the run's limits: {_L5}")
_env5 = json.loads(env_log.read_text())
check(_env5.get("OMP_NUM_THREADS") == "8",
      f"the CHILD a page build launched saw OMP_NUM_THREADS={_env5.get('OMP_NUM_THREADS')!r}. "
      f"This is the end of the chain and the only place the share is real: BLAS sizes its pool "
      f"at import, before any plugin code runs")
check(_env5.get("SCPROFILE_IN"),
      "the child a page build launched was given no manifest to read")
check(launch_log.read_text() == "1",
      f"one arm pair through a whole page build should be one launch; the log says "
      f"{launch_log.read_text()}")
check("NO core share" not in _noise.getvalue(),
      "a run that declared its core budget was warned it had none")

# ---------------------------------------------------------------------------------------------
# 11. THE PROBE IS A LAUNCH TOO, and its limit is `min(_PROBE_TIMEOUT, --timeout)`. Both halves
#     of that `min` are load-bearing and each fails silently on its own, so each gets its own
#     slow child rather than an assertion about the constant: a probe allowed to outlive the
#     limit the run declared is a limit the run does not actually have, and a probe allowed to
#     outlive 300s is an import hanging a report build with no ceiling of its own.
# ---------------------------------------------------------------------------------------------
d6 = Path(tempfile.mkdtemp())
k6, _ = _fake_run_tree(d6)
os.environ["PHASES_SLEEP"] = "4"                 # an import that will not finish in one second
try:
    _drawn6, _ = _drive_native(d6, timeout=1, cores=8)
finally:
    os.environ.pop("PHASES_SLEEP", None)
check(_drawn6 == [] and launch_log.read_text() == "0",
      f"a run declaring `--timeout 1` let its probe run to the probe's own 300s and then went "
      f"on to launch the phase; the run's limit must lower this one: {_drawn6}")
check(not (k6 / _RS.COMPARE_DIRNAME / _RS.PHASE_RECORD).exists(),
      "a probe that never answered produced a phase record, so the phase is documented as "
      "having run")

launch_log.write_text("0", encoding="utf-8")
_saved_probe = _RP._PROBE_TIMEOUT
os.environ["PHASES_SLEEP"] = "4"
try:
    # The other half of the `min`, measured the same way with the roles swapped: the run's limit
    # is now the LARGER of the two, and the probe must still be bounded by its own.
    _RP._PROBE_TIMEOUT = 1
    _drawn7, _ = _drive_native(d6, timeout=900, cores=8)
finally:
    _RP._PROBE_TIMEOUT = _saved_probe
    os.environ.pop("PHASES_SLEEP", None)
check(_drawn7 == [] and launch_log.read_text() == "0",
      f"the probe took the RUN's limit instead of the smaller of the two, so a long-running run "
      f"has no ceiling on a plugin import at all: {_drawn7}")

# ---------------------------------------------------------------------------------------------
# 12. AND WHEN A LIMIT IS MISSING, THE PHASE SAYS SO - BOTH OF THEM. `timeout=None` was announced
#     and `cores=None` was not, and that asymmetry ran the wrong way: a missing timeout removes a
#     ceiling, while a missing core share removes THE CAPS THEMSELVES and silently restores the
#     inherited-thread-count defect this file was opened for. `cli` records `"cores": budget` on
#     every run so a live run cannot get here; a `scprofile report` rebuild from an older
#     report.json can, and that is exactly the case with nobody watching the queue.
# ---------------------------------------------------------------------------------------------
d8 = Path(tempfile.mkdtemp())
k8, _ = _fake_run_tree(d8)
_saved = os.environ.get("OMP_NUM_THREADS")
os.environ["OMP_NUM_THREADS"] = "64"                      # what a PBS script exports for itself
try:
    _drawn8, _said8 = _drive_native(d8, timeout=900, cores=None)
    _env8 = json.loads(env_log.read_text())
finally:
    if _saved is None:
        os.environ.pop("OMP_NUM_THREADS", None)
    else:
        os.environ["OMP_NUM_THREADS"] = _saved
check(_env8.get("OMP_NUM_THREADS") == "64",
      f"the premise, and the reason the sentence is needed: with no core share the six caps are "
      f"unset and the child INHERITED the job's 64, got {_env8.get('OMP_NUM_THREADS')!r}. If "
      f"this changed, env_for_kernel now has a default and this section should be remeasured")
check("NO core share" in _said8,
      f"a rebuild running the phase with NO core share said nothing about it, so the page's "
      f"figures were drawn on an oversubscribed node and no document of the run says so. The "
      f"missing timeout is announced; this one printed: {_said8!r}")
check("NO timeout" not in _said8,
      "a run that declared `--timeout 900` was told it had no limit")
_rec8 = k8 / _RS.COMPARE_DIRNAME / _RS.PHASE_RECORD
check(_rec8.is_file(), "a phase run with no core share wrote no record, so nothing below is read")
if _rec8.is_file():
    check([L.get("cores") for L in (json.loads(_rec8.read_text()).get("launches") or [])]
          == [None],
          "the record must state the share the launch ACTUALLY ran under, including when there "
          "was none - a record naming a share nobody applied is worse than no record")

# ---------------------------------------------------------------------------------------------
# 13. THE SECOND LAUNCH SITE. This phase has TWO calls to `_compare_launch` - one per arm pair and
#     one over every crossed arm - and every design used above has exactly two arms, so the
#     across-arms gate never fired and its call site was never executed by this file at all. A
#     mutation putting `cores=None, timeout=None` on it survived the whole battery: the arm-pair
#     site was covered, the across-arms site was reached only on a design nobody here built.
#
#     THREE LEVELS OF ONE FACTOR is the cheapest design that fires it - `len(_cross) > 2` - and
#     it also makes the gate's own sentence say the opposite thing from section 8, where it did
#     not fire. Both launch kinds are asserted from one record, by kind, so a limit dropped at
#     either site fails here naming which.
# ---------------------------------------------------------------------------------------------
d10 = Path(tempfile.mkdtemp())
k10, _ = _fake_run_tree(d10, units=("ctrl", "mid", "hi"))
_design10 = {"s1": {"diet": "ctrl"}, "s2": {"diet": "mid"}, "s3": {"diet": "hi"}}
_units10 = [{"unit": u, "dir": f"kernels/cellchat/{u}"} for u in ("ctrl", "mid", "hi")]
_drawn10, _ = _drive_native(d10, timeout=900, cores=8, design=_design10, units=_units10)
_rec10 = k10 / _RS.COMPARE_DIRNAME / _RS.PHASE_RECORD
check(_rec10.is_file(), "a three-arm design produced no phase record")
if _rec10.is_file():
    _r10 = json.loads(_rec10.read_text())
    _L10 = _r10.get("launches") or []
    _kinds = sorted(L.get("kind") for L in _L10)
    check("across_arms" in _kinds,
          f"the across-arms launch did not fire on a design crossing three arms, so this section "
          f"measures nothing and the second launch site is still unexecuted: {_kinds}")
    check([L.get("cores") for L in _L10] == [8] * len(_L10)
          and [L.get("timeout") for L in _L10] == [900] * len(_L10),
          f"a launch site is carrying its own limits rather than the run's: "
          f"{[(L.get('kind'), L.get('cores'), L.get('timeout')) for L in _L10]}")
    check((_r10.get("cardinality") or {}).get("not_launched") == 0,
          f"nothing should be unlaunchable on three arms of one factor: {_r10.get('cardinality')}")
    check("more than two arms" in (_r10.get("across_arms_gate") or ""),
          f"the gate must state its rule whether or not it fired: "
          f"{_r10.get('across_arms_gate')!r}")
    # THE RECORD IS CHECKED AGAINST THE PLUGIN'S OWN COUNT, not against itself. The cardinality
    # is a claim about how many times a process started, and the only witness to that is the
    # process.
    check(launch_log.read_text() == str(len(_L10)) == str((_r10.get("cardinality") or {}).get(
              "launched")),
          f"the record claims {len(_L10)} launch(es) and a cardinality of "
          f"{(_r10.get('cardinality') or {}).get('launched')}; the plugin was started "
          f"{launch_log.read_text()} time(s)")

d9 = Path(tempfile.mkdtemp())
_fake_run_tree(d9)
_drawn9, _said9 = _drive_native(d9, timeout=None, cores=8)
check("NO timeout" in _said9,
      f"the missing-timeout sentence is gone; a phase running unbounded must say so, and it is "
      f"the sentence the core-share one was modelled on: {_said9!r}")
check("NO core share" not in _said9,
      "a run that declared `cores: 8` was told it had no share")

for _d in (d1, d2, d3, d4, d5, d6, d8, d9, d10):
    shutil.rmtree(_d, ignore_errors=True)

if fails:
    print("FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ok - the compare phase writes its manifest, its record and its cardinality, is DRIVEN "
      "from write_all under the run's own core share and timeout all the way into the child's "
      "environment at BOTH launch sites, is killed by that timeout rather than merely recording "
      "it, bounds its probe by both limits, re-runs on a version bump, announces either limit "
      "when it is missing, does not re-execute on every report build, and is no longer surveyed "
      "as an instance that died")
