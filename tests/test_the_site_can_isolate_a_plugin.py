"""A site can build one plugin alone, so one member's failed solve does not block the others.

The resolver groups plugins on their declarations, and a declaration cannot show a solve that
fails: seven plugins resolved into one environment whose pip stage died on one member's
dependency closure, and no member installed (harness B1-015). `$SCPROFILE_ISOLATE` names what
the site has measured: each listed plugin gets its own environment, no other plugin joins it,
and the rest share without it. With the variable unset nothing changes.

Asked twice: of the resolver, on plugins built for it, and of the real `install --dry-run` on
the shipped set, with an empty lock directory so the answer does not depend on which platform
the shipped locks are for.

Run: python tests/test_the_site_can_isolate_a_plugin.py
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scprofile import resolve as R                                              # noqa: E402

VAR = "SCPROFILE_ISOLATE"
FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


class K:
    def __init__(self, name, packages):
        self.name = name
        self.spec = {"requires": {"python": ">=3.10,<3.13", "packages": packages}}


def groups(ks, isolate=None):
    keep = os.environ.pop(VAR, None)
    try:
        if isolate is not None:
            os.environ[VAR] = isolate
        return {tuple(g.members): g for g in R.group_by_compatibility(ks)}
    finally:
        os.environ.pop(VAR, None)
        if keep is not None:
            os.environ[VAR] = keep


print("the resolver: a listed plugin is alone, and nobody joins it")
SET = [K("p", {"numpy": ">=1.24", "solver_heavy": ">=1.0"}),
       K("q", {"numpy": ">=1.24"}), K("r", {"numpy": ">=1.24"})]
g0 = groups(SET)
ck("unset: the three share one environment", list(g0) == [("p", "q", "r")], str(list(g0)))
g1 = groups(SET, "p")
ck("listed: p is alone, q and r share without it",
   sorted(g1) == [("p",), ("q", "r")], str(sorted(g1)))
ck("and the reason is the site, by name",
   "isolated by the site" in getattr(g1.get(("p",)), "why_alone", ""),
   getattr(g1.get(("p",)), "why_alone", "no group"))
ck("and the others' environment no longer carries p's package",
   "solver_heavy" not in getattr(g1.get(("q", "r")), "packages", {"solver_heavy": 1}))
g2 = groups(SET, " q, r ")
ck("a list of two, with spaces: three environments, none shared",
   sorted(g2) == [("p",), ("q",), ("r",)], str(sorted(g2)))


print("\nthe real install --dry-run, on the shipped set")
from scprofile.kernels import discover                                         # noqa: E402

_keep = os.environ.pop("SCPROFILE_KERNELS", None)
try:
    _shared = [g for g in R.group_by_compatibility(list(discover().values()))
               if len(g.members) > 1]
finally:
    if _keep is not None:
        os.environ["SCPROFILE_KERNELS"] = _keep


def dry(name, isolate=None):
    with tempfile.TemporaryDirectory() as t:
        env = {k: v for k, v in os.environ.items() if k not in (VAR, "SCPROFILE_KERNELS")}
        env.update(PYTHONPATH=str(ROOT), SCPROFILE_LOCKS=str(Path(t) / "no-locks"))
        if isolate is not None:
            env[VAR] = isolate
        r = subprocess.run([sys.executable, "-m", "scprofile.cli", "install", name, "--prefix",
                            str(Path(t) / "envs"), "--dry-run"], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, timeout=300)
        return r.returncode, (r.stdout or "") + (r.stderr or "")


def shared_by(out):
    m = re.search(r"shared by: ([^\n(]+)", out)
    return [x.strip() for x in m.group(1).split(",")] if m else []


if not _shared:
    print("  (no two shipped plugins share an environment here, so there is nothing to split; "
          "the resolver's half above is the test)")
else:
    grp = max(_shared, key=lambda g: len(g.members))
    first, other = grp.members[0], grp.members[-1]
    rc, out = dry(other)
    ck(f"unset: {other}'s environment includes {first}", rc == 0 and first in shared_by(out),
       out[-400:])
    rc, out = dry(other, first)
    ck(f"{VAR}={first}: {other}'s environment no longer includes it",
       rc == 0 and shared_by(out) and first not in shared_by(out), out[-400:])
    rc, out = dry(first, first)
    ck(f"and {first} is built alone, the site named as the reason",
       rc == 0 and shared_by(out) == [first] and "isolated by the site" in out, out[-400:])

print("\n" + ("a site can isolate a plugin" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
