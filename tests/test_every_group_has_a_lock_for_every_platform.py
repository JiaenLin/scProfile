"""Every plugin group the tool declares has a lock for every platform it declares, and the lock is the group's.

THE SET IS READ, NEVER LISTED HERE. `lock.pairs()` (scprofile/lock.py) is the one place that
defines it: the groups `resolve.group_by_compatibility` forms from each plugin's `requires`, times
the platforms in `setup/locks/platforms.txt`. A new group or a new platform is walked by this test
with no line added to it. (Before autodev W058 the platforms were stated nowhere, two of the three
groups had never been locked, and on the cluster `install` resolved their ranges at install time.)

For each pair it asks three things, each its own judge, so each fails for its own reason:
  EXISTS  a lock at `setup/locks/<platform>/<members>.txt`;
  FRESH   its recorded inputs are the group's declaration TODAY - the members, the platform, the
          requirement lines and their digest - and its pins meet them (`lock.state` reads the
          pair `locked` from that lock alone);
  PINS    every exact pin a member declares - an `==` in its `requires.packages`, and
          `wraps.version` for `wraps.tool` (autodev W055's source stage) - is the version the
          lock holds.
And in reverse: every shipped lock belongs to a pair of the set (none is left behind for a group or
a platform that is gone).

Then it proves its own judges bite, on copies and never on the tree: a removed lock fails EXISTS
only, a range moved after the lock fails FRESH only, a `wraps.version` moved off the lock fails
PINS only, and a platform added to the declaration fails EXISTS for every group and nothing else.

Run: python tests/test_every_group_has_a_lock_for_every_platform.py
"""
import copy
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for var in ("SCPROFILE_LOCKS", "SCPROFILE_ISOLATE", "SCPROFILE_KERNELS"):
    os.environ.pop(var, None)

from scprofile import lock as LK                                          # noqa: E402
from scprofile import resolve as RS                                       # noqa: E402
from scprofile.kernels import discover                                    # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + ("" if cond or not detail else f"  -- {detail}"))
    if not cond:
        FAIL.append(name)


def declared_pins(k):
    """[(where, package, version)]: every exact version a plugin declares."""
    out = []
    for n, s in sorted(((RS.requirement(k) or {}).get("packages") or {}).items()):
        for c in str(s).split(","):
            c = c.strip()
            if c.startswith("==") and not c.startswith("==="):
                out.append(("requires", n, c[2:].strip()))
    w = k.spec.get("wraps") if isinstance(k.spec.get("wraps"), dict) else {}
    if w.get("tool") and w.get("version") is not None:
        out.append(("wraps.version", str(w["tool"]), str(w["version"])))
    return out


def same_version(a, b):
    try:
        return RS.satisfies(a, RS.parse(f"=={b}"))
    except ValueError:
        return str(a) == str(b)


def walk(kernels):
    """{(members, platform): {"EXISTS": [...], "FRESH": [...], "PINS": [...]}}, plus orphans."""
    found = LK.all_locks()
    out, keys = {}, set()
    for g, plat in LK.pairs(kernels):
        key = ("+".join(g.members), plat)
        keys.add(key)
        probs = {"EXISTS": [], "FRESH": [], "PINS": []}
        path = LK.path_for(g.members, plat)
        lk = next((x for x in found if x.path is not None and x.path.resolve() == path.resolve()),
                  None)
        if lk is None:
            probs["EXISTS"].append(f"no lock at {LK._rel(path)}: `{LK.lock_command(g, plat)}`")
            out[key] = probs
            continue
        st, got, why, fix = LK.state(g, locks=[lk], machine=plat)
        if lk.platform != plat:
            probs["FRESH"].append(f"{lk.where()} records platform {lk.platform!r}, not {plat}")
        if st != "locked" or got is None:
            probs["FRESH"].append(f"{st}: {why}  Fix: {fix}")
        held = {LK.canon(n) for n in g.packages}
        for m in g.members:
            for where, pkg, ver in declared_pins(kernels[m]):
                have = lk.pins.get(LK.canon(pkg))
                if have is None:
                    if where == "wraps.version" and LK.canon(pkg) not in held:
                        continue     # not a pip package of the group: an R tool is pinned by its remote
                    probs["PINS"].append(f"{m} declares {pkg}=={ver} ({where}); {lk.where()} "
                                         f"pins no {pkg}")
                elif not same_version(have, ver):
                    probs["PINS"].append(f"{m} declares {pkg}=={ver} ({where}); {lk.where()} "
                                         f"holds {pkg}=={have}")
        out[key] = probs
    orphans = [lk.where() for lk in found if ("+".join(lk.members), lk.platform) not in keys]
    return out, orphans


def failing(result):
    """{(pair, judge)} that have a problem."""
    return {(key, j) for key, probs in result.items() for j, v in probs.items() if v}


KS = discover()

# ====================================================================== 1. the tree as it ships
print("\nthe set, read from the one place that defines it")
plats = LK.declared_platforms()
SET = LK.pairs(KS)
ck("the tool declares at least one platform (setup/locks/platforms.txt)", bool(plats), str(plats))
ck("the set is every group times every declared platform",
   len(SET) == len(RS.group_by_compatibility(list(KS.values()), isolate=())) * len(plats),
   f"{len(SET)} pairs")
ck("every plugin that declares an environment is in exactly one group of the set",
   sorted(m for g, p in SET if p == plats[0] for m in g.members)
   == sorted(n for n, k in KS.items() if RS.requirement(k) is not None))
for g, p in SET:
    print(f"      {'+'.join(g.members)}  x  {p}")

print("\neach pair: its lock EXISTS, is FRESH against today's declaration, and holds every exact PIN")
SHIPPED, ORPHANS = walk(KS)
for (members, plat), probs in sorted(SHIPPED.items()):
    for judge in ("EXISTS", "FRESH", "PINS"):
        ck(f"{judge:<6} {members} on {plat}", not probs[judge], "; ".join(probs[judge][:3]))
ck("no shipped lock is left behind for a group or platform outside the set", not ORPHANS,
   "; ".join(ORPHANS))
n_pins = sum(len(declared_pins(KS[m])) for g, p in SET for m in g.members)
ck("the PINS judge had pins to read (an empty walk proves nothing)", n_pins > 0, str(n_pins))

# =============================================================== 2. each judge fails on its own
print("\neach judge fails for its own reason, and only that judge (on copies, never the tree)")
TMP = Path(tempfile.mkdtemp(prefix="w058-walk-"))
try:
    COPY = TMP / "locks"
    shutil.copytree(LK.lock_dir(), COPY, symlinks=True)
    os.environ["SCPROFILE_LOCKS"] = str(COPY)
    base = failing(walk(KS)[0])
    ck("the copy reads as the tree does", base == failing(SHIPPED), str(base))

    def victim(name):
        return next(((g, p) for g, p in LK.pairs(KS) if name in g.members), (None, None))

    def mutated(name, edit):
        ks = dict(KS)
        k = copy.copy(KS[name])
        k.spec = copy.deepcopy(KS[name].spec)
        edit(k.spec)
        ks[name] = k
        return ks

    # (a) a lock REMOVED: EXISTS fails for that pair, and nothing else moves.
    g, p = victim("scenic")
    key = ("+".join(g.members), p)
    gone = LK.path_for(g.members, p)
    held = gone.read_bytes()
    gone.unlink()
    got = failing(walk(KS)[0]) - base
    ck("a removed lock fails EXISTS for its pair and nothing else", got == {(key, "EXISTS")},
       str(sorted(got)))
    gone.write_bytes(held)

    # (b) a lock made STALE: one of the group's ranges moves after the lock was written.
    def widen(spec):
        spec["requires"]["packages"]["anndata"] = ">=0.9,<0.12"
    got = failing(walk(mutated("scenic", widen))[0]) - base
    ck("a range moved after the lock fails FRESH for its pair and nothing else",
       got == {(key, "FRESH")}, str(sorted(got)))
    msg = walk(mutated("scenic", widen))[0][key]["FRESH"]
    ck("and the reason names the range that moved", any("anndata" in x for x in msg), str(msg))

    # (c) a PIN moved off its lock: `wraps.version` is not part of the requirement, so the lock
    # stays fresh - only the pin judge can see it.
    g2, p2 = victim("velocity")
    key2 = ("+".join(g2.members), p2)
    v0 = KS["velocity"].spec["wraps"]["version"]

    def move(spec):
        spec["wraps"]["version"] = "0.0.1"
    got = failing(walk(mutated("velocity", move))[0]) - base
    ck("a wraps.version moved off its lock fails PINS for its pair and nothing else",
       got == {(key2, "PINS")}, str(sorted(got)))
    msg = walk(mutated("velocity", move))[0][key2]["PINS"]
    ck("and names both versions", any("0.0.1" in x and v0 in x for x in msg), str(msg))

    # (d) a PLATFORM added to the declaration: the set grows with no line added to this test.
    (COPY / LK.PLATFORMS_NAME).write_text(
        (COPY / LK.PLATFORMS_NAME).read_text(encoding="utf-8") + "aarch64-apple-darwin\n",
        encoding="utf-8")
    grown, _ = walk(KS)
    new = {k for k in grown if k[1] == "aarch64-apple-darwin"}
    ck("a declared platform adds one pair per group", len(new) == len(SET) // len(plats),
       str(sorted(new)))
    ck("and fails EXISTS for each of them, nothing else",
       failing(grown) - base == {(k, "EXISTS") for k in new}, str(sorted(failing(grown) - base)))

    # (e) the site's isolation list is not the tool's declaration: the set does not move with it.
    (COPY / LK.PLATFORMS_NAME).write_text(
        (ROOT / "setup" / "locks" / LK.PLATFORMS_NAME).read_text(encoding="utf-8"),
        encoding="utf-8")
    os.environ["SCPROFILE_ISOLATE"] = "abundance"
    ck("a site's isolation list leaves the set as declared",
       sorted(("+".join(g.members), p) for g, p in LK.pairs(KS))
       == sorted(("+".join(g.members), p) for g, p in SET))
    os.environ.pop("SCPROFILE_ISOLATE", None)
finally:
    os.environ.pop("SCPROFILE_LOCKS", None)
    os.environ.pop("SCPROFILE_ISOLATE", None)
    shutil.rmtree(TMP, ignore_errors=True)       # a copied tree; rmtree removes links, never follows

print("\n" + ("every group has a current lock for every declared platform" if not FAIL
              else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
