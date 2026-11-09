"""An environment is built from its LOCK and named for it; a lock that no longer matches is refused.

THE DEFECT, MEASURED (harness ADR-0027, PBS 720377). The group seven plugins share could not be
built from `main`. Its requirement was fifteen RANGES; pip backtracked through pertpy's arviz 1.x
split until it stopped with `resolution-too-deep`; nothing recorded what those ranges had ever
resolved to; and the environment's name hashed the ranges. So a fresh prefix had nothing to build
from except a resolve that could not finish.

Measured on the workstation on 2026-11-09: a complete resolver (uv) solves the same ranges in
25 s - and its answer still cannot run abundance. pertpy 1.0.5 with statsmodels 0.15 does not
import; 1.0.5 asks scanpy 1.10 for a function only 1.11 has; numpyro 0.22 cannot initialise
scCODA. So the group is resolved ONCE, on purpose, with those facts applied as host constraints,
and the cluster applies the answer without resolving anything.

What this suite pins, every part of it failing on the code before the lock (f294c89):
  1. a current lock for this machine NAMES the environment: the name moves when a pin moves, and
     not when the lock's comments, header or line order do - nor when a range is re-locked to the
     same pins. An unlocked group keeps the name its ranges always gave it.
  2. a lock that no longer matches - a range moved, a member joined - is STALE, and a stale lock
     is refused before anything is built, naming what changed and the command that re-locks it.
     It is never bypassed by resolving the ranges instead.
  3. a lock for another platform changes nothing on this machine, and says so.
  4. through the real CLI: `scprofile lock` writes the lock from the resolver's answer; `install`
     applies it with `pip --no-deps`, checks every installed version against it, stamps the
     environment with the lock's name and leaves a receipt; an install whose result drifted from
     the lock is a FAILED build with no stamp.
  5. the shipped tree carries a CURRENT lock for its shared group, for linux, whose every pin meets
     every member's own range and the host's constraints.

Run: python tests/test_an_environment_is_built_from_its_lock.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import resolve as RS                                       # noqa: E402
from scprofile import runner                                              # noqa: E402
from scprofile.kernels import discover                                    # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


try:
    from scprofile import lock as LK                                      # noqa: E402
except ImportError:
    LK = None

SHIPPED_LOCKS = os.environ.pop("SCPROFILE_LOCKS", None)


def cli(*args, env=None):
    """The real CLI, in its own process, as a job runs it."""
    e = dict(os.environ, PYTHONPATH=str(ROOT))
    e.update(env or {})
    p = subprocess.run([sys.executable, "-m", "scprofile.cli", *args], capture_output=True,
                       text=True, env=e, cwd=str(ROOT), timeout=900)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class K:
    """A requirement, as the resolver reads one."""

    def __init__(self, name, python="", packages=None):
        self.name = name
        self.spec = {"requires": {"python": python, "packages": packages or {}}}


def pick(spec):
    """A version meeting a range - its floor, or 0 below a ceiling. Test data, not a resolver."""
    clauses = RS.parse(spec)
    exact = [w for op, w in clauses if op in ("==", "~=")]
    floors = [w for op, w in clauses if op in (">=", ">")]
    v = exact[0] if exact else (max(floors) if floors else (0,))
    s = ".".join(str(x) for x in v)
    return s if RS.satisfies(s, clauses) else s + ".1"


def _sh(path, body):
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def fakes(where):
    """A resolver, a package manager, pip, an interpreter and an Rscript, each recording its argv.

    Nothing here tests what a real resolver or a real manager computes; it tests what the HOST
    hands them and what it does with their answer, which is where the defect lived.
    """
    b = where / "bin"
    t = where / "templates"
    b.mkdir(parents=True)
    t.mkdir()
    _sh(b / "uv", 'if [ "$1" = "--version" ]; then echo "uv 0.0.0 (fake)"; exit 0; fi\n'
                  'printf "%s\\n" "$@" > "$FAKE_UV_ARGV"\n'
                  'out=""; prev=""\n'
                  'for a in "$@"; do [ "$prev" = "-o" ] && out="$a"; prev="$a"; done\n'
                  'cat "$FAKE_UV_OUT" > "$out"\n')
    _sh(b / "micromamba", 'echo "$*" >> "$FAKE_MGR_LOG"\n'
                          'case "$1" in\n'
                          '  create)\n'
                          '    p=""; prev=""\n'
                          '    for a in "$@"; do [ "$prev" = "-p" ] && p="$a"; prev="$a"; done\n'
                          '    mkdir -p "$p/bin"\n'
                          '    for x in python pip Rscript; do cp "$FAKE_TEMPLATES/$x" "$p/bin/$x"; '
                          'chmod +x "$p/bin/$x"; done\n'
                          '    exit 0 ;;\n'
                          '  list) echo "# fake conda list"; exit 0 ;;\n'
                          '  *) exit 0 ;;\n'
                          'esac\n')
    _sh(t / "pip", 'd=$(cd "$(dirname "$0")/.." && pwd)\n'
                   'echo "$*" >> "$FAKE_PIP_ARGV"\n'
                   'r=""; prev=""\n'
                   'for a in "$@"; do [ "$prev" = "-r" ] && r="$a"; prev="$a"; done\n'
                   'if [ -n "$r" ]; then\n'
                   '  if [ -n "$FAKE_PIP_DRIFT" ]; then\n'
                   '    sed "s/^$FAKE_PIP_DRIFT==.*/$FAKE_PIP_DRIFT==0.0.1/" "$r" >> '
                   '"$d/.fake_installed.txt"\n'
                   '  else cat "$r" >> "$d/.fake_installed.txt"; fi\n'
                   'fi\n'
                   'echo "pip==99.0" >> "$d/.fake_installed.txt"\n')
    _sh(t / "python", 'd=$(cd "$(dirname "$0")/.." && pwd)\n'
                      'case "$*" in\n'
                      '  *SCPROFILE_INSTALLED_VERSIONS*) cat "$d/.fake_installed.txt" '
                      '2>/dev/null; exit 0 ;;\n'
                      '  *) echo "fake interpreter: ok"; exit 0 ;;\n'
                      'esac\n')
    _sh(t / "Rscript", "exit 0\n")
    return b, t


# ======================================================================== 1. the lock names it
print("\na current lock for this machine names the environment")
LOCKS = Path(tempfile.mkdtemp())
os.environ["SCPROFILE_LOCKS"] = str(LOCKS)
pair = [K("a", ">=3.10,<3.13", {"numpy": ">=1.24,<2", "pandas": ">=2.0,<3"}),
        K("b", ">=3.10,<3.13", {"numpy": ">=1.24,<3"})]
PINS = {"numpy": "1.26.4", "pandas": "2.2.3", "tzdata": "2025.1"}


def group(ks):
    gs = RS.group_by_compatibility(ks)
    return gs[0] if len(gs) == 1 else None


def write_lock(members, platform, pins, requirement, resolver="uv test", written="2026-01-01",
               annot=""):
    body = "\n".join(f"{n}=={v}{annot}" for n, v in pins.items())
    p = LK.path_for(members, platform)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(LK.render(members, platform, "3.12", resolver, requirement, body,
                           written=written), encoding="utf-8")
    return p


g0 = group(pair)
ranges_name = g0.name if g0 else ""
ck("the two plugins share one environment", g0 is not None)
ck("unlocked, nothing is attached", getattr(g0, "lock", None) is None)

locked_name = ""
if LK is not None and g0 is not None:
    here = LK.machine_platform()
    req = LK.requirement_lines(g0)
    write_lock(["a", "b"], here, PINS, req)
    g1 = group(pair)
    ck("a current lock for this machine is attached to its group",
       getattr(g1, "lock", None) is not None, str(getattr(g1, "lock_state", None)))
    locked_name = g1.name
    ck("and the environment is named for the LOCK, not the ranges", locked_name != ranges_name,
       locked_name)

    write_lock(["a", "b"], here, dict(reversed(list(PINS.items()))), req, resolver="uv 9.9.9",
               written="2031-12-31", annot="    # via somebody")
    ck("rewriting the lock's comments, header and line order does not rename it",
       group(pair).name == locked_name, group(pair).name)

    write_lock(["a", "b"], here, dict(PINS, pandas="2.2.2"), req)
    ck("moving one pin renames it", group(pair).name not in (locked_name, ranges_name))
    write_lock(["a", "b"], here, PINS, req)

    print("\na lock that no longer matches is stale, and says what changed")
    moved = [K("a", ">=3.10,<3.13", {"numpy": ">=1.24,<2", "pandas": ">=2.0,<3"}),
             K("b", ">=3.10,<3.13", {"numpy": ">=1.25,<3"})]
    gm = group(moved)
    st = getattr(gm, "lock_state", ("",))
    ck("a moved range makes the lock stale", st[0] == "stale", str(st))
    ck("and the sentence names the range that moved", "numpy" in (st[1] if len(st) > 1 else ""),
       str(st))
    ck("and the fix is the command that re-locks it",
       (st[2] if len(st) > 2 else "").startswith("scprofile lock "), str(st))
    ck("a stale group is not named for the lock it no longer matches", gm.name != locked_name)
    write_lock(["a", "b"], here, PINS, LK.requirement_lines(gm))
    ck("re-locked to the same pins, it is the same environment - nothing to rebuild",
       group(moved).name == locked_name, group(moved).name)
    write_lock(["a", "b"], here, PINS, req)

    trio = pair + [K("c", ">=3.10,<3.13", {"pandas": ">=2.0,<3"})]
    gt = group(trio)
    st = getattr(gt, "lock_state", ("", ""))
    ck("a member joining makes it stale, and names who joined",
       st[0] == "stale" and "joined: c" in st[1], str(st))

    print("\na lock for another platform changes nothing here")
    other = "x86_64-manylinux_2_17" if here.endswith("apple-darwin") else "aarch64-apple-darwin"
    shutil.rmtree(LOCKS / here)
    write_lock(["a", "b"], other, PINS, req)
    go = group(pair)
    ck("this machine's environment keeps the name its ranges give it", go.name == ranges_name)
    ck("and says which platform the lock is for",
       go.lock_state[0] == "unlocked" and other in go.lock_state[1], str(go.lock_state))
    alone = [K("v", "==3.11", {"x": "==1"})]
    ck("a lock naming other plugins does not rename an unlocked one",
       group(alone).name == RS.Group("==3.11", {"x": "==1"}, ["v"]).name)
    shutil.rmtree(LOCKS / other)

    print("\na host constraint that cannot be read refuses the locked group and nothing else")
    write_lock(["a", "b"], here, PINS, req)
    (LOCKS / "constraints.txt").write_text("this is not a constraint\n", encoding="utf-8")
    lone = [K("v", "==3.9", {"x": "==1"})]           # an interpreter the pair excludes: alone
    try:
        gs = RS.group_by_compatibility(pair + lone)
        st = {tuple(g.members): g.lock_state for g in gs}
        ck("grouping still answers", len(gs) == 2, str(list(st)))
        ck("the locked group is refused, naming the file",
           st.get(("a", "b"), ("",))[0] == "stale" and "constraints" in st[("a", "b")][1],
           str(st.get(("a", "b"))))
        ck("and a group no lock names is untouched", st.get(("v",), ("",))[0] == "unlocked",
           str(st.get(("v",))))
    except Exception as e:                                                # noqa: BLE001
        ck("a malformed constraints file does not break grouping", False, repr(e))
    (LOCKS / "constraints.txt").unlink()
    shutil.rmtree(LOCKS / here)

    print("\nthe platform a lock is for")
    ck("a glibc 2.17 floor installs on a 2.28 machine",
       LK.accepts("x86_64-manylinux_2_17", "x86_64-manylinux_2_28")[0])
    ck("a 2.28 floor does not install on 2.17",
       not LK.accepts("x86_64-manylinux_2_28", "x86_64-manylinux_2_17")[0])
    ck("linux is not macOS", not LK.accepts("x86_64-manylinux_2_17", "aarch64-apple-darwin")[0])
    ck("nor another architecture",
       not LK.accepts("x86_64-manylinux_2_17", "aarch64-manylinux_2_28")[0])

    print("\na lock is exact or it is refused")
    for bad in ("numpy>=1.24\n", "numpy==1.26.4 ; python_version < '3.13'\n",
                "-e git+https://example.invalid/x\n"):
        try:
            LK.parse(bad)
            ck(f"{bad.strip()!r} is refused", False, "it was read as a lock")
        except ValueError:
            ck(f"{bad.strip()!r} is refused", True)

    print("\nthe builder hands pip the lock, not the ranges")
    write_lock(["a", "b"], here, PINS, req)
    sp = runner.build_spec(group(pair))
    ck("every pip item is an exact pin from the lock",
       sorted(sp["pip"]) == sorted(f"{n}=={v}" for n, v in PINS.items()), str(sp["pip"]))
    ck("and the interpreter is the lock's", sp["python"] == "3.12", str(sp["python"]))
    ck("an environment holding exactly the lock passes the check",
       LK.verify_installed({"numpy": "1.26.4"}, {"numpy": {"1.26.4"}}) == [])
    bad = LK.verify_installed({"numpy": "1.26.4", "pandas": "2.2.3"}, {"numpy": {"2.0.0"}})
    ck("a different version and a missing package are both named",
       len(bad) == 2 and "numpy" in bad[0] and "pandas" in bad[1], str(bad))
shutil.rmtree(LOCKS, ignore_errors=True)


# ============================================================ 2-4. the real CLI, end to end
print("\nthrough the real CLI: lock, dry run, install, drift, stale")
os.environ.pop("SCPROFILE_LOCKS", None)
ks = discover()
shared = max(RS.group_by_compatibility(list(ks.values())), key=lambda g: len(g.members))
asked = shared.members[0]
W = Path(tempfile.mkdtemp())
L2 = W / "locks"
L2.mkdir()
(L2 / "constraints.txt").write_text("# a host constraint, as the shipped file carries them\n"
                                    "statsmodels<0.15\n", encoding="utf-8")
bindir, templates = fakes(W)
canned = W / "compile.out"
canned.write_text("".join(f"{n}=={pick(s)}    # via -r requirements.in\n"
                          for n, s in sorted(shared.packages.items()))
                  + "statsmodels==0.14.6    # via -c constraints.txt\n", encoding="utf-8")
env = {"SCPROFILE_LOCKS": str(L2), "FAKE_UV_OUT": str(canned), "FAKE_UV_ARGV": str(W / "uv.argv"),
       "FAKE_MGR_LOG": str(W / "mgr.log"), "FAKE_PIP_ARGV": str(W / "pip.argv"),
       "FAKE_TEMPLATES": str(templates), "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
mach = LK.machine_platform() if LK is not None else ""
rc, out = cli("lock", asked, "--platform", mach or "x86_64-manylinux_2_17", "--uv",
              str(bindir / "uv"), env=env)
ck("`scprofile lock` is a command and it succeeds", rc == 0, out[-600:])
written = sorted(L2.glob("*/*.txt"))
ck("it writes one lock, filed by platform and named by the group's members",
   len(written) == 1 and written[0].name == "+".join(shared.members) + ".txt",
   str([p.relative_to(L2) for p in written]))
argv = (W / "uv.argv").read_text().split("\n") if (W / "uv.argv").exists() else []
ck("the resolver is asked for this platform and the group's interpreter",
   "--python-platform" in argv and "--python-version" in argv
   and argv[argv.index("--python-version") + 1] == RS.concrete_python(shared.python), str(argv))
ck("and is handed the host's constraints", "-c" in argv, str(argv))
lk = LK.parse(written[0].read_text(), path=written[0]) if (LK and written) else None
ck("the lock records its members, platform, interpreter and resolver",
   lk is not None and lk.members == shared.members and lk.platform == mach
   and lk.python == RS.concrete_python(shared.python) and lk.resolver == "uv 0.0.0",
   str(lk and (lk.members, lk.platform, lk.python, lk.resolver)))

if LK is not None:
    os.environ["SCPROFILE_LOCKS"] = str(L2)
    want_name = [g for g in RS.group_by_compatibility(list(discover().values()))
                 if asked in g.members][0].name
    os.environ.pop("SCPROFILE_LOCKS", None)
else:
    want_name = "<no lock module>"
rc, out = cli("install", asked, "--prefix", str(W / "dry"), "--dry-run", env=env)
ck("a dry run names the lock it would apply", rc == 0 and "lock: " in out and "locked" in out,
   out[-800:])
ck("and the environment it would build is named for the lock", want_name in out, want_name)
ck("and lists exact pins, no ranges",
   "numpy==" in out and not any(ln.strip().startswith("pip") and ">=" in ln
                                for ln in out.splitlines()), out[-800:])
rc, out = cli("doctor", "--prefix", str(W / "dry"), env=env)
ck("doctor says which environments are locked", "lock: " in out, out[-600:])

rc, out = cli("install", asked, "--prefix", str(W / "built"), env=env)
envdir = W / "built" / want_name
ck("a locked install builds", rc == 0, out[-1200:])
mgr = (W / "mgr.log").read_text() if (W / "mgr.log").exists() else ""
ck("the manager is asked for the lock's interpreter",
   f"python={RS.concrete_python(shared.python)}" in mgr, mgr[:300])
pipargs = (W / "pip.argv").read_text() if (W / "pip.argv").exists() else ""
ck("pip is told to resolve nothing (--no-deps) and given a file of pins",
   "--no-deps" in pipargs and " -r " in f" {pipargs} ", pipargs)
applied = envdir / ".scprofile_pip_lock.txt"
ck("the pins applied are exactly the lock's",
   applied.exists() and lk is not None
   and sorted(applied.read_text().split()) == sorted(f"{n}=={v}" for n, v in lk.pins.items()),
   str(applied))
stamp = envdir / ".scprofile_lock"
ck("the environment is stamped with the lock's name",
   stamp.exists() and stamp.read_text().strip() == want_name, str(stamp))
receipt = envdir / ".scprofile_resolved.txt"
ck("and leaves a receipt of what it holds", receipt.exists() and "numpy==" in receipt.read_text(),
   str(receipt))

rc, out = cli("install", asked, "--prefix", str(W / "drift"), env=dict(env, FAKE_PIP_DRIFT="numpy"))
ck("an install whose result drifted from the lock FAILS", rc != 0, out[-600:])
ck("and names the package and both versions", "numpy" in out and "0.0.1" in out, out[-600:])
ck("and writes no stamp", not (W / "drift" / want_name / ".scprofile_lock").exists())

# A MEMBER'S RANGE MOVES after the lock was written: a site copy of one member, one range
# raised, shadowing the shipped file. The lock is now stale, and the build must refuse BEFORE the
# manager is touched - the alternative is the resolve this lock was written to replace.
donor = next((ks[m] for m in shared.members if ks[m].path.is_file()
              and '"pandas": ">=2.0,<3"' in ks[m].path.read_text()), None)
ck("a member declaring pandas >=2.0,<3 exists to move", donor is not None)
if donor is not None:
    site = W / "site"
    site.mkdir()
    (site / donor.path.name).write_text(
        donor.path.read_text().replace('"pandas": ">=2.0,<3"', '"pandas": ">=2.1,<3"', 1))
    if (W / "mgr.log").exists():
        (W / "mgr.log").unlink()
    rc, out = cli("install", asked, "--prefix", str(W / "stale"),
                  env=dict(env, SCPROFILE_KERNELS=str(site)))
    ck("a stale lock is REFUSED", rc != 0, out[-600:])
    ck("naming the range that moved", "pandas" in out, out[-600:])
    ck("and the command that re-locks", "scprofile lock " in out, out[-600:])
    ck("and nothing was built - not resolved from ranges in its place",
       not list((W / "stale").glob("scprofile-env-*")) and not (W / "mgr.log").exists(),
       str(list((W / "stale").glob("*"))))
shutil.rmtree(W, ignore_errors=True)


# ============================================================== 5. the lock the tree ships
print("\nthe shipped tree carries a current lock for its shared group")
if SHIPPED_LOCKS is not None:
    os.environ["SCPROFILE_LOCKS"] = SHIPPED_LOCKS
shipped = LK.all_locks() if LK is not None else []
gs = RS.group_by_compatibility(list(discover().values()))
shared = max(gs, key=lambda g: len(g.members))
linux = [x for x in shipped if x.members == shared.members and "manylinux" in x.platform]
ck(f"a linux lock exists for {', '.join(shared.members)}", bool(linux),
   f"none among {[x.where() for x in shipped]}")
for x in linux:
    st = LK.state(shared, locks=shipped, machine=x.platform)
    ck(f"{x.where()} is CURRENT for today's requirement", st[0] == "locked", st[1])
    ck("it is a closure, not a copy of the direct requirements",
       len(x.pins) > len(shared.packages), f"{len(x.pins)} pins")
    for m in shared.members:
        own = RS.requirement(ks[m])["packages"]
        off = [f"{n}=={x.pins.get(LK.canon(n))} vs {s}" for n, s in sorted(own.items())
               if x.pins.get(LK.canon(n)) is None
               or not RS.satisfies(x.pins[LK.canon(n)], RS.parse(s))]
        ck(f"every pin meets {m}'s own ranges", not off, "; ".join(off))
    ck("and the host's constraints", LK.uncovered(x, shared) == [], str(LK.uncovered(x, shared)))
for x in shipped:
    use = [g for g in gs if g.members == x.members
           and LK.state(g, locks=shipped, machine=x.platform)[0] == "locked"]
    ck(f"{x.where()} is used by a current group, not left behind stale", bool(use),
       x.error or "its members or requirement no longer match any group")


print("\n" + ("an environment is built from its lock" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
