"""A plugin takes its allocation, not the machine (autodev W065, GAP-C133).

The cluster's first dev-suite run: inside a job allowed 8 cores, on a node with 256, de's
`DeseqStats` passed no worker count, pydeseq2 0.5.2 took `multiprocessing.cpu_count()` - the
node's - and joblib started a loky worker for each, until the node's open-file table was full. The
host set six thread-pool variables then; Python's own count was not among them, nor joblib's.

THE CLASS: every channel by which a library in a plugin's process decides how many workers or
threads to start is set by the host from the share, before the plugin's code runs. THE ONE PLACE:
`manifest._THREAD_VARS`, which `env_for_kernel` sets. THIS TEST walks that tuple: a probe plugin
(a fixture of this test, not a shipped plugin) is launched as the host launches one - the
plugin's interpreter, the shared entry point, the environment `runner.run` builds from the share
in the plugin's own in.json - with a share of 2, from a parent that exports 16 on every channel
(a job script exporting its node's count; and on Python 3.13, a machine whose `os.cpu_count()`
reads 16). The probe prints what each channel reads in its own process; every one must be 2. A
channel added to the tuple is tested here with no new test. Python's count is also read the way
pydeseq2 reads it (`multiprocessing.cpu_count()`), and joblib's and numba's the way those
libraries read them, where they are importable. Nothing is started: the probe only reads.

Run: python tests/test_a_plugin_takes_its_allocation.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import manifest, runner                                          # noqa: E402
from scprofile.kernels import SHARED_ENTRY                                      # noqa: E402

FAIL = []
SHARE, MANY = 2, 16


def ck(name, cond, detail=""):
    print(("  ok    " if cond else "  FAIL  ") + name + ("" if cond else f"  [{detail}]"))
    if not cond:
        FAIL.append(name)


#: The probe: what each channel reads in the plugin's own process, at its module scope - which the
#: entry point executes after its own imports and before the plugin's `run`.
PROBE = r'''
import json, multiprocessing, os
from scprofile import manifest
seen = {"env": {v: os.environ.get(v) for v in manifest._THREAD_VARS},
        "os.cpu_count()": os.cpu_count(), "multiprocessing.cpu_count()": multiprocessing.cpu_count()}
try:
    import joblib
    seen["joblib.cpu_count()"] = joblib.cpu_count()
except ImportError:
    pass
try:
    import numba
    seen["numba.config.NUMBA_NUM_THREADS"] = numba.config.NUMBA_NUM_THREADS
except ImportError:
    pass
print("W065-PROBE " + json.dumps(seen))

def run(ctx):
    pass
'''

#: What reads a channel inside the process, beside the variable itself. These are read whether or
#: not the host's tuple names their channel - they are what the libraries consult - so a channel
#: the host forgets fails here, as Python's own count did at W058's head.
READERS = {"PYTHON_CPU_COUNT": ("os.cpu_count()", "multiprocessing.cpu_count()"),
           "LOKY_MAX_CPU_COUNT": ("joblib.cpu_count()",),
           "NUMBA_NUM_THREADS": ("numba.config.NUMBA_NUM_THREADS",)}


def launch(td):
    probe = td / "w065_probe.py"
    probe.write_text(PROBE, encoding="utf-8")
    inp = td / "in.json"
    manifest.write_input(inp, h5ad=td / "x.h5ad", out_dir=td / "out", keys={"label": "l"},
                         resources={"cores": SHARE})
    # THE SHARE AS runner.run READS IT: from the manifest just written, into env_for_kernel.
    cores = (json.loads(inp.read_text(encoding="utf-8")).get("resources") or {}).get("cores")
    parent = sorted(set(manifest._THREAD_VARS) | set(READERS))
    saved = {v: os.environ.get(v) for v in parent}
    try:
        for v in parent:
            os.environ[v] = str(MANY)
        env = runner.with_env_bin(sys.executable, manifest.env_for_kernel(inp, cores=cores))
    finally:
        for v, old in saved.items():
            if old is None:
                os.environ.pop(v, None)
            else:
                os.environ[v] = old
    r = subprocess.run([sys.executable, str(SHARED_ENTRY), "--phases", str(probe)], env=env,
                       cwd=str(td), capture_output=True, text=True, timeout=300)
    line = [ln for ln in r.stdout.splitlines() if ln.startswith("W065-PROBE ")]
    return r, (json.loads(line[-1].split(" ", 1)[1]) if line else None)


print(f"\na plugin takes its share ({SHARE}), not the {MANY} its parent reports, on every channel")
with tempfile.TemporaryDirectory() as d:
    r, seen = launch(Path(d))
ck("the probe ran through the shared entry point and printed its readings", seen is not None,
   f"exit {r.returncode}: {(r.stderr or r.stdout)[-400:]}")
seen = seen or {"env": {}}
for var in manifest._THREAD_VARS:
    got = seen["env"].get(var)
    ck(f"{var} reads {SHARE} in the plugin's process", got == str(SHARE), f"it reads {got!r}")
    for reader in READERS.get(var, ()):
        if reader in seen:
            ck(f"  and {reader} reads {SHARE}", seen[reader] == SHARE, f"it reads {seen[reader]!r}")
        else:
            print(f"  --    {reader}: not importable in this interpreter, so not read here")
for var in sorted(set(READERS) - set(manifest._THREAD_VARS)):
    print(f"  --    {var}: NOT in the host's tuple; what reads it, read all the same")
    for reader in READERS[var]:
        if reader in seen:
            ck(f"  {reader} reads {SHARE}", seen[reader] == SHARE, f"it reads {seen[reader]!r}")
untouched = manifest.env_for_kernel(Path("in.json"))
ck("a launch that names no share sets no channel (the caller's environment is left alone)",
   all(untouched.get(v) == os.environ.get(v) for v in manifest._THREAD_VARS))

print(f"\n{len(FAIL)} failure(s)" if FAIL else "\nall checks passed")
sys.exit(1 if FAIL else 0)
