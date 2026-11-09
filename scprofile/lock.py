"""The resolved versions of one environment group, recorded once and applied without resolving.

WHAT THIS FIXES, MEASURED (harness ADR-0027, PBS 720377)

The seven plugins that share one environment declare RANGES - `pertpy >=0.9,<2`, `numpy >=1.24,<2`,
fifteen of them merged - and nothing recorded what those ranges had ever resolved to. The
environment's name hashed the ranges, so a fresh prefix had nothing to build from except a resolve,
and the resolve pip attempted on the cluster did not finish: `resolution-too-deep`, backtracking
through pertpy's arviz 1.x split. The group could not be installed from `main` at all.

Two facts, both measured on 2026-11-09, decide the shape of the answer:

  - THE RANGES DO RESOLVE. A complete resolver (uv) solves them in 25 s: pertpy 1.1 to 1.4 need
    arviz >= 1.2, whose arviz-base needs numpy >= 2, while four members cap numpy below 2, and
    pertpy 1.5 needs Python 3.13 - so the group can only hold pertpy 1.0.x, and pip walked every
    arviz 1.x release before it could learn that.
  - THE SOLUTION STILL DOES NOT RUN. Resolved from the ranges alone, abundance cannot start: pertpy
    1.0.5 with statsmodels 0.15 raises ImportError, 1.0.5 asks scanpy 1.10 for a function only 1.11
    has, and numpyro 0.22 cannot initialise scCODA's model. Metadata cannot know any of that. It
    is host knowledge, kept in `constraints.txt` beside the locks, with the measurement behind
    each line.

So a group is resolved ONCE, on purpose, by `scprofile lock`, with those constraints applied, and
the answer - every package of the closure at one exact version, for one platform and one Python -
is recorded here. `scprofile install` applies it with `pip install --no-deps`, which resolves
nothing, and then checks that the environment holds exactly what the lock says.

THE LAYERING IS UNCHANGED. A plugin still declares what it NEEDS; this module records what those
needs RESOLVED TO on one platform, which is the machine's question and not the plugin's. No plugin
file names a version it did not choose, and editing a plugin's range is still the only way to
change what it asks for - after which its lock no longer matches, and `install` says so rather
than quietly resolving the ranges again.

WHAT A LOCK IS KEYED BY, AND WHY EACH PART

  members     the plugins it was resolved for. A plugin belongs to one group at a time, so a lock
              that names a member of this group and does not match it is evidence of a change.
  platform    wheels differ per platform and per glibc. A lock resolved for linux says nothing true
              about macOS, so it is applied only where `accepts` says the machine can install it.
  requirement every merged range, the interpreter range and the constraints, as canonical lines,
              with a digest. A lock whose recorded requirement differs from today's is STALE, and a
              stale lock is refused - by name, with what changed - never bypassed.

The environment's NAME is a digest of the pins themselves (see `resolve.Group.name`), so it moves
when a version moves and not when a comment, a date or the order of lines does.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

#: Where the shipped locks live, relative to the checkout. Beside the installer's job scripts in
#: `setup/`, because a lock is installation data: what `install` builds, not what a plugin is.
LOCK_DIRNAME = Path("setup") / "locks"
CONSTRAINTS_NAME = "constraints.txt"
ENV_VAR = "SCPROFILE_LOCKS"

HEADER = ("# scProfile environment lock: every package of one group, at one exact version, for "
          "one platform.\n"
          "# Written by `scprofile lock`. Change a plugin's `requires`, or constraints.txt, and "
          "re-run it; never edit this file.\n")

_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?==([^\s;#]+)$")
_REQ = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")
#: One clause of a specifier: an operator and a version, nothing else.
_CLAUSE = re.compile(r"^(===|==|!=|>=|<=|~=|>|<)\s*[0-9A-Za-z][0-9A-Za-z.*+!_-]*$")


def lock_dir():
    """The directory locks are read from and written to.

    `$SCPROFILE_LOCKS` REPLACES the shipped one rather than adding to it, because the reason to set
    it is to control exactly which locks apply - a site with kernels of its own, or a test.
    """
    over = os.environ.get(ENV_VAR)
    if over:
        return Path(over).expanduser()
    return Path(__file__).resolve().parent.parent / LOCK_DIRNAME


def canon(name):
    """A package name as the index compares it (PEP 503): `PyYAML`, `pyyaml` and `py_yaml` agree."""
    return re.sub(r"[-_.]+", "-", str(name)).lower()


def canon_spec(spec):
    """A specifier with its clauses deduplicated and sorted, so their ORDER is not a change."""
    return ",".join(sorted({c.strip() for c in str(spec or "").split(",") if c.strip()}))


# ---------------------------------------------------------------------------------- the platform

def machine_platform():
    """This machine, in the resolver's vocabulary (`uv pip compile --python-platform`).

    A linux machine is named by its glibc, because a wheel's tag names the oldest glibc it runs on
    and a lock resolved for a newer one can name wheels this machine cannot load.
    """
    import platform as _pf
    import sys
    arch = _pf.machine().lower()
    arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(arch, arch)
    if sys.platform.startswith("linux"):
        ver = ""
        try:
            got = os.confstr("CS_GNU_LIBC_VERSION") or ""       # "glibc 2.28"
            ver = got.split()[-1] if got.startswith("glibc") else ""
        except (AttributeError, ValueError, OSError):
            ver = ""
        if not ver:
            lib, v = _pf.libc_ver()
            ver = v if lib == "glibc" else ""
        m = re.match(r"^(\d+)\.(\d+)", ver or "")
        if m:
            return f"{arch}-manylinux_{m.group(1)}_{m.group(2)}"
        return f"{arch}-unknown-linux-musl"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    if sys.platform.startswith("win"):
        return f"{arch}-pc-windows-msvc"
    return f"{arch}-{sys.platform}"


def _parts(tag):
    """(arch, os, glibc floor or None) for a platform tag; None when the tag is not understood."""
    t = str(tag or "").strip().lower()
    m = re.match(r"^([a-z0-9_]+)-manylinux_(\d+)_(\d+)$", t)
    if m:
        return m.group(1), "linux", (int(m.group(2)), int(m.group(3)))
    m = re.match(r"^([a-z0-9_]+)-manylinux2014$", t)
    if m:
        return m.group(1), "linux", (2, 17)
    m = re.match(r"^([a-z0-9_]+)-unknown-linux-gnu$", t)
    if m:
        return m.group(1), "linux", (2, 17)
    m = re.match(r"^([a-z0-9_]+)-apple-darwin$", t)
    if m:
        return m.group(1), "darwin", None
    return None


def accepts(lock_platform, machine=None):
    """(bool, why). Can a machine install the wheels a lock for `lock_platform` names?

    A glibc floor is a FLOOR: a lock resolved for manylinux_2_17 installs on a 2.28 machine, and
    not the other way round. Anything this cannot parse matches only itself, exactly.
    """
    mine = machine or machine_platform()
    a, b = _parts(lock_platform), _parts(mine)
    if a is None or b is None:
        same = str(lock_platform).strip().lower() == str(mine).strip().lower()
        return same, ("" if same else f"{lock_platform} is not {mine}")
    if a[0] != b[0] or a[1] != b[1]:
        return False, f"{lock_platform} is for {a[1]} {a[0]}; this machine is {b[1]} {b[0]}"
    if a[2] and b[2] and b[2] < a[2]:
        return False, (f"{lock_platform} needs glibc {a[2][0]}.{a[2][1]}; this machine has "
                       f"{b[2][0]}.{b[2][1]}")
    return True, ""


# ------------------------------------------------------------------------------- the requirement

def read_constraints(dirpath=None):
    """The host's constraint lines, canonical and sorted. Comments and blank lines are not lines."""
    f = Path(dirpath or lock_dir()) / CONSTRAINTS_NAME
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = _REQ.match(line)
        clauses = [c.strip() for c in (m.group(3) if m else "").split(",") if c.strip()]
        if not m or not clauses or not all(_CLAUSE.match(c) for c in clauses):
            raise ValueError(f"{f}: {raw!r} is not a constraint (`name<spec>`, e.g. `pkg<2`)")
        out.append(f"{canon(m.group(1))}{canon_spec(m.group(3))}")
    return sorted(set(out))


def requirement_lines(group, constraints=None):
    """What a lock for this group is resolved FROM, one canonical line per fact.

    The interpreter's range, every merged package range, and every host constraint. Clause order
    and name spelling are normalised away, because neither changes what a resolver is asked.
    """
    cons = read_constraints() if constraints is None else list(constraints)
    lines = [f"python {canon_spec(getattr(group, 'python', ''))}"]
    for n, s in sorted((getattr(group, "packages", {}) or {}).items(), key=lambda kv: canon(kv[0])):
        lines.append(f"requires {canon(n)} {canon_spec(s)}")
    lines += [f"constraint {c}" for c in sorted(cons)]
    return lines


def requirement_digest(lines):
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:12]


# ------------------------------------------------------------------------------------- the lock

class Lock:
    """One lock file, read. `pins` is {canonical name: version}; nothing in it is a range."""

    def __init__(self, path=None, members=(), platform="", python="", resolver="", written="",
                 digest="", requirement=(), pins=None, error=""):
        self.path = Path(path) if path else None
        self.members = sorted(members)
        self.platform = platform
        self.python = python
        self.resolver = resolver
        self.written = written
        self.digest = digest
        self.requirement = list(requirement)
        self.pins = dict(pins or {})
        #: Non-empty when the file could not be read as a lock. It still names its members by its
        #: file name, so a broken lock is a refusal for exactly the group it was written for.
        self.error = error

    @property
    def identity(self):
        """A digest of the pins alone, in canonical order: what is BUILT, never how it is written."""
        body = "\n".join(f"{n}=={v}" for n, v in sorted(self.pins.items()))
        return hashlib.sha256(body.encode()).hexdigest()[:12]

    def where(self):
        """The lock's path, relative to the checkout when it lives in one."""
        if self.path is None:
            return "(unsaved lock)"
        try:
            return str(self.path.resolve().relative_to(Path(__file__).resolve().parent.parent))
        except (ValueError, OSError):
            return str(self.path)

    def __repr__(self):
        return f"<Lock {'+'.join(self.members)} {self.platform} {len(self.pins)} pins>"


def parse(text, path=None):
    """A lock's text, read strictly. Anything that is not a comment or `name==version` RAISES.

    A lock with one range in it is a lock that resolves at install time - the thing it exists to
    stop - so a range, a URL or an option line is refused rather than passed to pip.
    """
    head, pins, req = {}, {}, []
    for n, raw in enumerate(str(text).splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            m = re.match(r"^#\s*([a-z-]+):\s*(.*)$", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                if key == "requirement":
                    req.append(val)
                else:
                    head.setdefault(key, val)
            continue
        body = line.split(" #", 1)[0].strip()
        m = _PIN.match(body)
        if not m:
            raise ValueError(f"{path or 'lock'}:{n}: {raw.strip()!r} is not an exact pin "
                             f"(`name==version`). A lock that carries a range resolves at "
                             f"install time, which is the thing it exists to prevent.")
        name = canon(m.group(1))
        if name in pins and pins[name] != m.group(3):
            raise ValueError(f"{path or 'lock'}:{n}: {name} is pinned twice ({pins[name]} and "
                             f"{m.group(3)})")
        pins[name] = m.group(3)
    return Lock(path=path, members=head.get("members", "").split(), platform=head.get("platform", ""),
                python=head.get("python", ""), resolver=head.get("resolver", ""),
                written=head.get("written", ""), digest=head.get("requirement-digest", ""),
                requirement=req, pins=pins)


def render(members, platform, python, resolver, requirement, body, written=None):
    """The text of a lock: the header that keys it, then the resolver's pins, verbatim."""
    when = written or time.strftime("%Y-%m-%d", time.gmtime())
    lines = [HEADER.rstrip("\n"),
             f"# members: {' '.join(sorted(members))}",
             f"# platform: {platform}",
             f"# python: {python}",
             f"# resolver: {resolver}",
             f"# written: {when}",
             f"# requirement-digest: {requirement_digest(requirement)}"]
    lines += [f"# requirement: {r}" for r in requirement]
    out = "\n".join(lines) + "\n"
    kept = [ln.rstrip() for ln in str(body).splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    return out + "\n".join(kept) + "\n"


def path_for(members, platform, dirpath=None):
    """`<locks>/<platform>/<member>+<member>.txt`: the file names the group it belongs to."""
    return Path(dirpath or lock_dir()) / str(platform) / ("+".join(sorted(members)) + ".txt")


def all_locks(dirpath=None):
    """Every lock under the directory. An unreadable one is returned carrying its error."""
    root = Path(dirpath or lock_dir())
    out = []
    if not root.is_dir():
        return out
    for f in sorted(root.glob("*/*.txt")):
        try:
            lk = parse(f.read_text(encoding="utf-8"), path=f)
        except (OSError, ValueError) as e:
            lk = Lock(path=f, members=f.stem.split("+"), platform=f.parent.name, error=str(e))
        if not lk.members:
            lk.members = f.stem.split("+")
        if not lk.platform:
            lk.platform = f.parent.name
        out.append(lk)
    return out


# ----------------------------------------------------------------------------- does it apply here

def _satisfies(version, spec):
    """Whether a pinned version meets a range, where this host can decide it; True otherwise."""
    from . import resolve as RS
    try:
        return RS.satisfies(version, RS.parse(spec))
    except ValueError:
        return True


def uncovered(lk, group, constraints=None):
    """What a lock fails to pin, or pins outside a range it was resolved from. [] when sound."""
    bad = []
    for n, s in sorted((getattr(group, "packages", {}) or {}).items()):
        v = lk.pins.get(canon(n))
        if v is None:
            bad.append(f"{n} is required and not pinned")
        elif not _satisfies(v, s):
            bad.append(f"{n}=={v} does not satisfy {s}")
    for c in (read_constraints() if constraints is None else constraints):
        m = _REQ.match(c)
        v = lk.pins.get(canon(m.group(1))) if m else None
        if v is not None and m.group(3) and not _satisfies(v, m.group(3)):
            bad.append(f"{m.group(1)}=={v} breaks the host constraint {c}")
    if lk.python and getattr(group, "python", "") and not _satisfies(lk.python, group.python):
        bad.append(f"python {lk.python} does not satisfy {group.python}")
    return bad


def _why_stale(lk, group, want_lines):
    if lk.error:
        return f"{lk.where()} cannot be read as a lock: {lk.error}"
    mine = sorted(group.members)
    if lk.members != mine:
        add = sorted(set(mine) - set(lk.members))
        gone = sorted(set(lk.members) - set(mine))
        return (f"{lk.where()} was resolved for {', '.join(lk.members)}; this environment's "
                f"members are now {', '.join(mine)}"
                + (f" (joined: {', '.join(add)})" if add else "")
                + (f" (left: {', '.join(gone)})" if gone else ""))
    was = set(lk.requirement)
    now = set(want_lines)
    if lk.digest != requirement_digest(want_lines) or was != now:
        changed = ([f"now {x}" for x in sorted(now - was)]
                   + [f"was {x}" for x in sorted(was - now)])
        return (f"{lk.where()} was resolved from a different requirement"
                + (f": {'; '.join(changed[:6])}" if changed else
                   f" (recorded digest {lk.digest or 'none'})"))
    bad = uncovered(lk, group)
    return f"{lk.where()} does not satisfy its own requirement: {'; '.join(bad[:6])}"


def state(group, locks=None, machine=None):
    """(status, lock or None, sentence, fix) for one group on one machine.

        locked    a lock for exactly these members, for a platform this machine can install,
                  resolved from today's requirement and satisfying it. The build applies it.
        stale     a lock for this platform names a member of this group and does not match it.
                  The build REFUSES, because the alternative is resolving the ranges, which is
                  what the lock was written to stop.
        unlocked  no lock for this platform names any member. The build resolves the ranges as it
                  always did, and says that nothing records what they resolved to.
    """
    mach = machine or machine_platform()
    found = all_locks() if locks is None else list(locks)
    mine = set(getattr(group, "members", []) or [])
    first = sorted(mine)[0] if mine else "<plugin>"
    fix = f"scprofile lock {first} --platform {mach}"
    if not any(set(lk.members) & mine for lk in found):
        # NEVER LOCKED, decided before anything else is read: a group no lock names builds from
        # its ranges as it always did, and nothing about the lock directory can stop that.
        return ("unlocked", None,
                "UNLOCKED: never locked, so the build resolves the ranges at install time and only "
                "the receipt it leaves records what they resolved to", fix)
    here = [lk for lk in found if accepts(lk.platform, mach)[0]]
    try:
        want = requirement_lines(group)
        good = [lk for lk in here
                if not lk.error and set(lk.members) == mine
                and lk.digest == requirement_digest(want) and set(lk.requirement) == set(want)
                and not uncovered(lk, group)]
    except ValueError as e:
        # A HOST CONSTRAINT THAT CANNOT BE READ is a lock that cannot be checked, for exactly the
        # groups a lock names. Refused there, by name; grouping and every other group go on.
        return ("stale", None, f"the host constraints cannot be read, so no lock can be checked: "
                               f"{e}", f"correct {lock_dir() / CONSTRAINTS_NAME}")
    if good:
        # THE MOST SPECIFIC FLOOR WINS: a machine that can take a 2.28 lock and a 2.17 one gets
        # the one resolved closest to it.
        good.sort(key=lambda lk: ((_parts(lk.platform) or ("", "", (0, 0)))[2] or (0, 0)),
                  reverse=True)
        lk = good[0]
        return ("locked", lk,
                f"{lk.where()} ({len(lk.pins)} packages, {lk.platform}, python {lk.python}, "
                f"{lk.resolver or 'resolver unrecorded'}, {lk.written or 'undated'})", "")
    named = [lk for lk in here if set(lk.members) & mine]
    if named:
        named.sort(key=lambda lk: (set(lk.members) != mine, str(lk.path)))
        lk = named[0]
        return ("stale", None,
                _why_stale(lk, group, want) + ". A lock that no longer matches is not applied, "
                "and resolving the ranges in its place is what it exists to prevent",
                f"scprofile lock {first} --platform {lk.platform}")
    other = sorted({lk.platform for lk in found if set(lk.members) & mine})
    return ("unlocked", None,
            f"UNLOCKED on this machine ({mach}): locks exist for {', '.join(other)} only, so "
            f"this build resolves the ranges at install time", fix)


def attach(groups, machine=None):
    """Give every group its lock state, and its lock where one applies. Reads the directory once."""
    try:
        found = all_locks()
    except OSError:
        found = []
    for g in groups:
        st, lk, why, fix = state(g, locks=found, machine=machine)
        g.lock = lk
        g.lock_state = (st, why, fix)
    return groups


def verify_installed(pins, installed):
    """What an environment holds that its lock does not say. [] when every pin is there, exactly.

    `installed` is {canonical name: set of versions}. Two versions of one distribution is a
    defect of its own - two dist-info directories, one shadowing the other - and is named.
    """
    bad = []
    for n, v in sorted(pins.items()):
        got = installed.get(canon(n)) or set()
        if not got:
            bad.append(f"{n}: pinned {v}, not installed")
        elif v not in got:
            bad.append(f"{n}: pinned {v}, installed {', '.join(sorted(got))}")
        elif len(got) > 1:
            bad.append(f"{n}: pinned {v}, and {len(got)} versions are installed "
                       f"({', '.join(sorted(got))})")
    return bad


# -------------------------------------------------------------------------------- writing a lock

def compile_lock(group, *, platform, python, uv, log=print, timeout=1800):
    """Resolve a group's ranges ONCE, with uv, under the host's constraints, and write the lock.

    uv and not pip, for the measured reason in the module docstring: pip could not finish this
    resolve and uv takes 25 s. The resolver runs on the machine that WRITES the lock, which is the
    workstation; the machine that builds applies its answer and never resolves.

    It runs in an empty directory, with `--no-config`, and is handed relative file names, so
    nothing about the machine that wrote a lock - a config file, a path - ends up in it.
    """
    root = lock_dir()
    cons = read_constraints(root)
    want = requirement_lines(group, cons)
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        (tdp / "requirements.in").write_text(
            "".join(f"{n}{s}\n" for n, s in sorted(group.packages.items())), encoding="utf-8")
        argv = [str(uv), "pip", "compile", "requirements.in", "--python-platform", str(platform),
                "--python-version", str(python), "--no-header", "--annotation-style", "line",
                "--no-config", "-o", "lock.out"]
        if cons:
            (tdp / CONSTRAINTS_NAME).write_text("".join(c + "\n" for c in cons), encoding="utf-8")
            argv += ["-c", CONSTRAINTS_NAME]
        log(f"  resolving {len(group.packages)} range(s) for {platform}, python {python}"
            + (f", under {len(cons)} host constraint(s)" if cons else ""))
        r = subprocess.run(argv, cwd=td, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0 or not (tdp / "lock.out").exists():
            tail = "\n".join(((r.stderr or "") + (r.stdout or "")).strip().splitlines()[-25:])
            raise RuntimeError(f"uv could not resolve this group for {platform}, python "
                               f"{python}:\n{tail}")
        body = (tdp / "lock.out").read_text(encoding="utf-8")
    try:
        v = subprocess.run([str(uv), "--version"], capture_output=True, text=True, timeout=60)
        resolver = (v.stdout or "").strip().split("(")[0].strip() or "uv"
    except (OSError, subprocess.SubprocessError):
        resolver = "uv"
    text = render(group.members, platform, python, resolver, want, body)
    out = path_for(group.members, platform, root)
    lk = parse(text, path=out)
    bad = uncovered(lk, group, cons)
    if bad:
        raise RuntimeError("the resolver's answer does not satisfy the group it was asked about, "
                           "so it is not written: " + "; ".join(bad[:8]))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return lk


def prune(platform, groups):
    """Remove locks for `platform` that no current group can use and none can be stale against.

    A lock is SUPERSEDED when every member it names now sits in a group that has its own current
    lock. Until then it is kept, because it is what makes a member that left it refuse to build
    from ranges instead of quietly doing so.
    """
    found = all_locks()
    held = {}
    for g in groups:
        st, lk, _w, _f = state(g, locks=found, machine=platform)
        if st == "locked" and lk is not None:
            for m in g.members:
                held[m] = lk.path
    gone = []
    for lk in found:
        if lk.platform != platform or lk.path in set(held.values()):
            continue
        if lk.members and all(m in held for m in lk.members):
            lk.path.unlink()
            gone.append(lk.path)
    return gone
