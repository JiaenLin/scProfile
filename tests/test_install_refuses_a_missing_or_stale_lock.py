"""`install` builds a pair of the set from its lock alone, and refuses a missing or stale lock by name.

Through the real CLI, `scprofile install ... --dry-run --platform TAG` (the building machine of
that platform, asked from here), for every pair `lock.pairs()` defines:
  1. RIGHT: the dry run reads the pair `locked`, and every pip line it would hand the installer is
     exactly one of the lock's pins - as many lines as pins, each `name==version`, nothing a
     resolver would have to choose.
  2. A MISSING LOCK on a declared platform is REFUSED (exit 1, nothing built), naming the group's
     members, the platform and the exact command that writes the lock. Before autodev W058 this
     read `unlocked` and the build resolved the group's ranges at install time.
  3. A STALE LOCK - the site's own case: `$SCPROFILE_ISOLATE=abundance` makes groups the shipped
     lock was not written for - is REFUSED, naming the members, the platform, who left, and a
     command that carries the site's list. Without the list, `scprofile lock cellchat` would
     re-lock the seven-member group and leave this one stale.
  4. Outside the set, nothing changed: a platform the tool does not declare builds from ranges,
     as before, and says UNLOCKED. `--platform` without `--dry-run` is refused.

Run: python tests/test_install_refuses_a_missing_or_stale_lock.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for var in ("SCPROFILE_LOCKS", "SCPROFILE_ISOLATE", "SCPROFILE_KERNELS"):
    os.environ.pop(var, None)

from scprofile import lock as LK                                          # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + ("" if cond or not detail else f"  -- {detail}"))
    if not cond:
        FAIL.append(name)


def cli(*args, env=None):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    e.update(env or {})
    r = subprocess.run([sys.executable, "-m", "scprofile.cli", *args], cwd=str(ROOT), env=e,
                       capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


TMP = Path(tempfile.mkdtemp(prefix="w058-install-"))
PFX = TMP / "prefix"
PFX.mkdir()
try:
    SET = LK.pairs()
    ck("the set has pairs to ask about", bool(SET), str(SET))

    # ========================================================== 1. each pair, from its lock alone
    print("\neach pair's dry run resolves from its lock alone")
    for g, plat in SET:
        first = g.members[0]
        rc, out = cli("install", first, "--prefix", str(PFX), "--dry-run", "--platform", plat)
        lk = next((x for x in LK.all_locks() if x.path == LK.path_for(g.members, plat)), None)
        tag = f"{'+'.join(g.members)} on {plat}"
        ck(f"{tag}: exit 0 and `lock: locked`", rc == 0 and "lock: locked" in out, out[-500:])
        pip = re.findall(r"^\s+pip\s+(\S+)\s*$", out, re.M)
        want = sorted(f"{n}=={v}" for n, v in (lk.pins.items() if lk else []))
        ck(f"{tag}: the pip lines are exactly the lock's {len(want)} pins",
           lk is not None and sorted(pip) == want,
           f"{len(pip)} lines; differ: {sorted(set(pip) ^ set(want))[:4]}")
        ck(f"{tag}: and the requirement says so", "(locked, exact)" in out, out[-300:])
    ck("nothing was built by a dry run", not any(PFX.iterdir()), str(list(PFX.iterdir())))

    # ================================================== 2. a missing lock is refused, by name
    print("\na pair with no lock is refused, naming the group, the platform and the command")
    COPY = TMP / "locks"
    shutil.copytree(LK.lock_dir(), COPY, symlinks=True)
    g, plat = next((x for x in SET if x[0].members == ["scenic"]), SET[-1])
    (COPY / plat / ("+".join(g.members) + ".txt")).unlink()
    rc, out = cli("install", g.members[0], "--prefix", str(PFX), "--dry-run", "--platform", plat,
                  env={"SCPROFILE_LOCKS": str(COPY)})
    cmd = f"SCPROFILE_LOCKS={COPY} scprofile lock {g.members[0]} --platform {plat}"
    ck("REFUSED, exit 1", rc == 1 and "REFUSED" in out and "NO LOCK" in out, out[-500:])
    ck("naming the group", f"the group {', '.join(g.members)} (" in out, out[-500:])
    ck("naming the platform", f"on {plat}, a platform this tool declares" in out, out[-500:])
    ck("and the exact command that writes the lock, lock directory included", cmd in out,
       out[-500:])
    ck("and nothing was built", not any(PFX.iterdir()), str(list(PFX.iterdir())))
    rc, out = cli("install", g.members[0], "--prefix", str(PFX), "--dry-run",
                  "--platform", "x86_64-manylinux_2_28", env={"SCPROFILE_LOCKS": str(COPY)})
    ck("a newer glibc installs the declared floor, so it is refused for the declared tag",
       rc == 1 and f"--platform {plat}" in out, out[-400:])

    # ======================================= 3. a stale lock: the site isolates a member
    print("\na lock made stale by the site's isolation list is refused, with the list in the command")
    site = {"SCPROFILE_ISOLATE": "abundance"}
    main = max(SET, key=lambda x: len(x[0].members))[0]
    six = [m for m in main.members if m != "abundance"]
    rc, out = cli("install", six[0], "--prefix", str(PFX), "--dry-run",
                  "--platform", "x86_64-manylinux_2_17", env=site)
    ck("REFUSED as STALE, exit 1", rc == 1 and "STALE" in out, out[-600:])
    ck("naming the group the site formed", f"the group {', '.join(six)} (" in out, out[-600:])
    ck("naming the platform and who left",
       "on x86_64-manylinux_2_17, " in out and "left: abundance" in out, out[-600:])
    ck("and a command that carries the site's list",
       f"SCPROFILE_ISOLATE=abundance scprofile lock {six[0]} --platform x86_64-manylinux_2_17"
       in out, out[-600:])
    rc, out = cli("install", "abundance", "--prefix", str(PFX), "--dry-run",
                  "--platform", "x86_64-manylinux_2_17", env=site)
    ck("the isolated member is refused too, by its own name",
       rc == 1 and "the group abundance (" in out
       and "SCPROFILE_ISOLATE=abundance scprofile lock abundance" in out, out[-500:])

    # ============================================================== 4. outside the set
    print("\noutside the set nothing changed")
    outside = "aarch64-apple-darwin"
    if outside in LK.declared_platforms():
        outside = "x86_64-apple-darwin"
    rc, out = cli("install", "scenic", "--prefix", str(PFX), "--dry-run", "--platform", outside)
    ck(f"{outside}, not declared: builds from ranges as before, saying UNLOCKED",
       rc == 0 and "lock: unlocked" in out and "(ranges, resolved at install time)" in out,
       out[-400:])
    rc, out = cli("install", "scenic", "--prefix", str(PFX), "--platform", "x86_64-manylinux_2_17")
    ck("--platform without --dry-run is refused (exit 2), and nothing is built",
       rc == 2 and "--dry-run" in out and not any(PFX.iterdir()), out[-300:])
finally:
    shutil.rmtree(TMP, ignore_errors=True)       # a copied tree; rmtree removes links, never follows

print("\n" + ("install builds the set from its locks and refuses a missing or stale one by name"
              if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
