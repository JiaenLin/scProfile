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

THE LAUNCH SITES (autodev W065, builder 2). The channels hold only for a process whose environment
comes from `env_for_kernel`, and at 0870714 the selftest's did not. So the test also walks every
process start in scprofile/, read from the syntax tree: each must take its `env=` from
`env_for_kernel`, or be named in `manifest.HOST_ONLY_LAUNCHES` with what it runs. It then plants a
launch in a copy, and removes each routed site's routing in a copy, and each must fail by its site.
A launch that names no share gets `manifest.UNALLOCATED_CORES` on every channel, never the caller's.

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
# -------------------------------------------------------------------------------------------------
# THE WALK OF THE LAUNCH SITES (autodev W065, builder 2). The channels above are set by ONE
# function, `manifest.env_for_kernel`, and that holds only for a process whose environment comes
# from it. At 0870714 the selftest launch took `with_env_bin(exe)` alone, so a selftest on a node
# read the node's count: the fixture's defect by another route. This reads the package's syntax
# tree and runs none of it. Every call that can start a process, in every module of scprofile/,
# must take its `env=` from `env_for_kernel` (directly, through a local name assigned from it, or
# through a function whose return is built from it), or be named in `manifest.HOST_ONLY_LAUNCHES`
# with what it runs and why no plugin code and no plugin environment's interpreter runs there. A
# new launch site fails here by file, line and function, whatever it runs, until it is routed or
# named; a name in that registry that starts no process fails too.
import ast       # noqa: E402
import shutil    # noqa: E402

ROOT_ = Path(__file__).resolve().parent.parent
#: Every call that can start a process, by the module that provides it.
STARTS = {
    "subprocess": {"run", "Popen", "call", "check_call", "check_output", "getoutput",
                   "getstatusoutput"},
    "os": ({"system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp"}
           | {p + s for p in ("exec", "spawn") for s in ("l", "le", "lp", "lpe", "v", "ve", "vp",
                                                         "vpe")}),
    "multiprocessing": {"Process", "Pool"},
    "multiprocessing.pool": {"Pool"},
    "concurrent.futures": {"ProcessPoolExecutor"},
    "asyncio": {"create_subprocess_exec", "create_subprocess_shell"},
    "pty": {"spawn", "fork"},
}


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    return ".".join([node.id] + parts[::-1]) if isinstance(node, ast.Name) else None


def _calls(node):
    """The name of every function called in `node`'s tree (the last part of a dotted name)."""
    return {(n.func.id if isinstance(n.func, ast.Name) else n.func.attr)
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))}


def _built_from(expr, scopes, routes):
    """Is `expr` built by a call to one of `routes`, itself or through a name assigned from one?"""
    if routes & _calls(expr):
        return True
    names = {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)}
    for scope in scopes:
        for n in ast.walk(scope):
            tgts = (n.targets if isinstance(n, ast.Assign) else
                    [n.target] if isinstance(n, ast.AnnAssign) and n.value is not None else [])
            if any(isinstance(t, ast.Name) and t.id in names for t in tgts) \
                    and routes & _calls(n.value):
                return True
    return False


def _routes(trees):
    """`env_for_kernel`, and every function whose return is built from it (to a fixed point)."""
    routes = {"env_for_kernel"}
    while True:
        more = {fn.name for t in trees.values() for fn in ast.walk(t)
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                and fn.name not in routes
                and any(isinstance(r, ast.Return) and r.value is not None
                        and _built_from(r.value, [fn], routes) for r in ast.walk(fn))}
        if not more:
            return routes
        routes |= more


class _Sites(ast.NodeVisitor):
    """Every process start in one module: (file:function, line, what, its env= or None, scopes)."""

    def __init__(self, rel, tree):
        self.rel, self.tree, self.stack, self.found = rel, tree, [], []
        self.mods, self.names = {}, {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    top = a.name.split(".")[0]
                    self.mods[a.asname or top] = a.name if a.asname else top
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                for a in n.names:
                    self.names[a.asname or a.name] = (n.module, a.name)
                    self.mods.setdefault(a.asname or a.name, f"{n.module}.{a.name}")

    def _start(self, call):
        f = call.func
        if isinstance(f, ast.Name):
            if f.id not in self.names:
                return None
            mod, attr = self.names[f.id]
        else:
            d = _dotted(f)
            if not d or d.split(".")[0] not in self.mods:
                return None
            head, rest = d.split(".", 1)
            mod, _, attr = (self.mods[head] + "." + rest).rpartition(".")
        return f"{mod}.{attr}" if attr in STARTS.get(mod, ()) else None

    def _scope(self, node):
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scope

    def visit_Call(self, node):
        what = self._start(node)
        if what:
            fns = [s for s in self.stack if not isinstance(s, ast.ClassDef)] or [self.tree]
            env = next((k.value for k in node.keywords if k.arg == "env"), None)
            where = ".".join(s.name for s in self.stack) or "<module>"
            self.found.append((f"{self.rel}:{where}", node.lineno, what, env, fns))
        self.generic_visit(node)


def _registry(root):
    """`HOST_ONLY_LAUNCHES` as `root`'s manifest.py writes it, read from its tree, not imported."""
    tree = ast.parse((Path(root) / "scprofile" / "manifest.py").read_text(encoding="utf-8"))
    for n in tree.body:
        tgts = n.targets if isinstance(n, ast.Assign) else [n.target] \
            if isinstance(n, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == "HOST_ONLY_LAUNCHES" for t in tgts):
            return ast.literal_eval(n.value)
    return {}


def judge(root):
    """Every process start under `root`/scprofile, its state, the registry, and what fails."""
    root = Path(root)
    trees = {p.relative_to(root).as_posix(): ast.parse(p.read_text(encoding="utf-8"))
             for p in sorted((root / "scprofile").rglob("*.py"))}
    routes, reg, rows, bad = _routes(trees), _registry(root), [], []
    for rel, tree in trees.items():
        v = _Sites(rel, tree)
        v.visit(tree)
        for key, line, what, env, fns in v.found:
            if env is not None and _built_from(env, fns, routes):
                state = "routed"
                if key in reg:
                    bad.append(f"{key} (line {line}) takes env_for_kernel and is ALSO named "
                               f"host-only: one of the two is stale")
            elif key in reg:
                state = "host-only"
            else:
                state = "UNROUTED"
                bad.append(f"{key} (line {line}): {what} starts a process whose environment does "
                           f"not come from manifest.env_for_kernel, and the site is not named in "
                           f"manifest.HOST_ONLY_LAUNCHES")
            rows.append((key, line, what, state))
    for key in sorted(set(reg) - {r[0] for r in rows}):
        bad.append(f"{key}: named in manifest.HOST_ONLY_LAUNCHES, and no process is started there")
    return rows, reg, bad


rows, reg, bad = judge(ROOT_)
print(f"\nevery launch site in scprofile/ ({len(rows)} process start(s), read from the syntax tree)")
for key, line, what, state in rows:
    print(f"  {state:9s} {key} line {line}: {what}")
ck("the walk sees the run's launch and the selftest's (it is walking something)",
   {"scprofile/runner.py:run", "scprofile/runner.py:selftest"} <= {r[0] for r in rows})
ck("every process start takes its environment from manifest.env_for_kernel, or is named host-only",
   not bad, "\n      " + "\n      ".join(bad))
ck("every host-only launch says what it runs and why no plugin code runs there",
   all(isinstance(w, str) and len(w) >= 40 for w in reg.values()), reg)

def _unroute(root, key):
    """In the copy at `root`, every start at `key` made to take `with_env_bin(exe)` alone: its
    `env=` value replaced at the syntax tree's own positions. Returns how many were replaced."""
    rel = key.split(":", 1)[0]
    p = Path(root) / rel
    raw = p.read_bytes()
    tree = ast.parse(raw)
    v = _Sites(rel, tree)
    v.visit(tree)
    envs = [env for k, _ln, _w, env, _f in v.found if k == key and env is not None]
    starts = [0]
    for ln in raw.splitlines(keepends=True):
        starts.append(starts[-1] + len(ln))
    for env in sorted(envs, key=lambda n: (n.lineno, n.col_offset), reverse=True):
        i = starts[env.lineno - 1] + env.col_offset
        j = starts[env.end_lineno - 1] + env.end_col_offset
        raw = raw[:i] + b"with_env_bin(exe)" + raw[j:]
    p.write_bytes(raw)
    return len(envs)


#: THE WALK ON ITSELF, in a copy of the package: a launch planted with `with_env_bin(exe)` alone
#: (the selftest's route at 0870714), then EVERY routed site's routing removed, one at a time.
PLANT = ('\n\ndef _planted_launch(exe):\n    import subprocess\n    from .runner import with_env_bin\n'
         '    return subprocess.run([str(exe), "-c", "pass"], env=with_env_bin(exe))\n')
routed = sorted({k for k, _ln, _w, s in rows if s == "routed"})
with tempfile.TemporaryDirectory() as d:
    cp = Path(d)
    shutil.copytree(ROOT_ / "scprofile", cp / "scprofile", symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    f = cp / "scprofile" / "compat.py"
    clean = f.read_bytes()
    f.write_bytes(clean + PLANT.encode("utf-8"))
    bad1 = judge(cp)[2]
    f.write_bytes(clean)
    print(f"    planted in a copy: scprofile/compat.py:_planted_launch -> the walk names "
          + ", ".join(x.split(" (line")[0] for x in bad1))
    ck("a launch planted with `with_env_bin(exe)` alone (the selftest's route at 0870714) fails, "
       "by its site", len(bad1) == 1 and bad1[0].startswith("scprofile/compat.py:_planted_launch "),
       bad1)
    for key in routed:
        p = cp / key.split(":", 1)[0]
        kept = p.read_bytes()
        n = _unroute(cp, key)
        badk = judge(cp)[2]
        p.write_bytes(kept)
        print(f"    routing removed in a copy: {key} ({n} start(s)) -> the walk names "
              + ", ".join(x.split(" (line")[0] for x in badk))
        ck(f"{key}: its routing removed in a copy fails, naming it and nothing else",
           n >= 1 and len(badk) == n and all(x.startswith(key + " ") for x in badk), badk)
ck("the selftest's launch is among the routed sites the walk proves on itself",
   "scprofile/runner.py:selftest" in routed, routed)

# A LAUNCH WITH NO SHARE OF ITS OWN (a selftest, a probe, a guard, an install step) gets the STATED
# allocation on every channel, never what its caller exports. At 0870714 a call naming no share
# left the channels alone - inherited - which is how a selftest would read a node's count.
_one = getattr(manifest, "UNALLOCATED_CORES", None)
_saved = {v: os.environ.get(v) for v in manifest._THREAD_VARS}
try:
    for v in manifest._THREAD_VARS:
        os.environ[v] = str(MANY)
    untouched = manifest.env_for_kernel()
finally:
    for v, old in _saved.items():
        if old is None:
            os.environ.pop(v, None)
        else:
            os.environ[v] = old
ck(f"a launch that names no share gets the stated {_one} on every channel, not the {MANY} its "
   f"caller exports", _one is not None
   and all(untouched.get(v) == str(_one) for v in manifest._THREAD_VARS),
   {v: untouched.get(v) for v in manifest._THREAD_VARS})

print(f"\n{len(FAIL)} failure(s)" if FAIL else "\nall checks passed")
sys.exit(1 if FAIL else 0)
