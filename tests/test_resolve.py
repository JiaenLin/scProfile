"""Requirement resolution: which plugins can share an environment, and which provably cannot.

A wrongly SHARED environment runs a plugin against versions nobody tested it on, which returns a
plausible number rather than an error. A wrongly ISOLATED one costs disk. Those are not
comparable, so every case here checks which way the resolver errs.

Run: python tests/test_resolve.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import resolve as R                                              # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


class K:
    def __init__(self, name, python="", packages=None):
        self.name = name
        self.spec = {"requires": {"python": python, "packages": packages or {}}}


print("\nversion comparison")
for v, spec, want in ((("1.26.4"), ">=1.20", True), ("1.26.4", ">=1.27", False),
                      ("1.26.4", "==1.26.4", True), ("1.26.4", "==1.26.3", False),
                      ("1.10.4", ">=1.10,<1.11", True), ("1.11.0", ">=1.10,<1.11", False),
                      ("3.11", "==3.11", True), ("3.10", "==3.11", False),
                      ("1.26.4", "!=1.26.4", False), ("1.26.5", "!=1.26.4", True),
                      ("1.2.5", "~=1.2.3", True), ("1.3.0", "~=1.2.3", False)):
    got = R.satisfies(v, R.parse(spec))
    ck(f"{v} vs {spec} -> {want}", got is want, f"got {got}")

print("\ncompatibility is decided only when it is provable")
for a, b, want, why in (
        ("==1.26.4", "==1.26.4", True, "identical pins"),
        ("==1.26.4", "==1.23.5", False, "two different exact pins"),
        ("==1.26.4", ">=1.20", True, "a pin inside a range"),
        ("==1.26.4", ">=1.27", False, "a pin outside a range"),
        (">=1.10,<1.11", ">=1.11", False, "ranges that do not overlap"),
        (">=1.10,<1.11", ">=1.10.4", True, "ranges that do overlap"),
        (">=1.20", ">=1.25", True, "two open lower bounds"),
        ("==3.10", "==3.11", False, "two python minors")):
    got, msg = R.compatible(a, b)
    ck(f"{why}: {a} + {b} -> {'compatible' if want else 'not'}", got is want, f"{got} {msg}")
    if not want:
        ck("   and it says which versions clash", bool(msg))

print("\nan unparseable constraint is refused, not assumed compatible")
ok, why = R.compatible("==1.2.3", "not-a-version")
ck("refused", not ok, why)
ck("and says why", "unparseable" in why)

print("\nplugins wanting the same stack share ONE environment")
same = [K("a", "==3.11", {"numpy": "==1.26.4", "scanpy": "==1.10.4"}),
        K("b", "==3.11", {"numpy": "==1.26.4", "scanpy": "==1.10.4"}),
        K("c", "==3.11", {"numpy": "==1.26.4", "decoupler": "==1.8.0"})]
gs = R.group_by_compatibility(same)
ck("one environment for three plugins", len(gs) == 1, f"{len(gs)} groups")
ck("all three are members", gs[0].members == ["a", "b", "c"], str(gs[0].members))
ck("and its constraints are the union",
   set(gs[0].packages) == {"numpy", "scanpy", "decoupler"}, str(sorted(gs[0].packages)))

print("\na genuinely incompatible plugin is isolated, and told why")
mixed = same + [K("old", "==3.10", {"numpy": "==1.23.5", "dask": "==2023.5.0"})]
gs = R.group_by_compatibility(mixed)
ck("two environments", len(gs) == 2, f"{len(gs)}")
alone = [g for g in gs if g.members == ["old"]]
ck("the odd one out is alone", len(alone) == 1, str([g.members for g in gs]))
ck("and the reason names a package and two versions",
   bool(alone[0].why_alone) and ("python" in alone[0].why_alone
                                 or "numpy" in alone[0].why_alone),
   alone[0].why_alone)

print("\nisolation is per-conflict, not all-or-nothing")
gs = R.group_by_compatibility([
    K("x", "==3.11", {"numpy": "==1.26.4"}),
    K("y", "==3.11", {"numpy": "==1.26.4", "extra": "==1.0"}),
    K("z", "==3.10", {"numpy": "==1.23.5"}),
    K("w", "==3.10", {"numpy": "==1.23.5"})])
sizes = sorted(len(g.members) for g in gs)
ck("two groups of two, not four of one", sizes == [2, 2], str([g.members for g in gs]))

print("\nthe resolution is deterministic")
a1 = [(g.name, g.members) for g in R.group_by_compatibility(mixed)]
a2 = [(g.name, g.members) for g in R.group_by_compatibility(list(reversed(mixed)))]
ck("order of input does not change the answer", sorted(a1) == sorted(a2),
   f"{sorted(a1)} vs {sorted(a2)}")
ck("the name is content-addressed, not plugin-named",
   all(g.name.startswith("scprofile-env-") for g in R.group_by_compatibility(mixed)))
ck("and identical requirements give an identical name",
   R.group_by_compatibility([K("p", "==3.11", {"n": "==1"})])[0].name
   == R.group_by_compatibility([K("q", "==3.11", {"n": "==1"})])[0].name,
   "two plugins with the same requirement must land in the same environment")

print("\na plugin needing no environment is not grouped")
gs = R.group_by_compatibility([K("a", "==3.11", {"n": "==1"}),
                               type("N", (), {"name": "hostonly", "spec": {}})()])
ck("only the one that needs an env", sum(len(g.members) for g in gs) == 1, str(gs))

print("\na fully-pinned `env` is read as an exact requirement")
class Old:
    name = "legacy"
    spec = {"env": {"python": "3.11", "pip": ["numpy==1.26.4", "scanpy==1.10.4"]}}
req = R.requirement(Old())
ck("python becomes an exact constraint", req["python"] == "==3.11", str(req))
ck("pins become exact constraints", req["packages"]["numpy"] == "==1.26.4", str(req))
gs = R.group_by_compatibility([Old(), K("new", "==3.11", {"numpy": "==1.26.4"})])
ck("and it can share with a requirement-shaped plugin", len(gs) == 1,
   str([g.members for g in gs]))

print("\nmerged constraints are deduplicated, so the group NAME is stable")
dup = [K(n, "==3.11", {"numpy": "==1.26.4"}) for n in ("a", "b", "c", "d")]
g = R.group_by_compatibility(dup)[0]
ck("python appears once, not four times", g.python == "==3.11", g.python)
ck("and so does the package", g.packages["numpy"] == "==1.26.4", g.packages["numpy"])
two = R.group_by_compatibility(dup[:2])[0]
ck("two members and four members give the SAME environment name", g.name == two.name,
   "a redundant clause must not change where the environment is built")

print("\na directory plugin's lock.yml is read as its requirement")
import tempfile as _tf
with _tf.TemporaryDirectory() as d:
    d = Path(d) / "legacy"
    d.mkdir()
    (d / "kernel.yml").write_text("name: legacy\n")
    (d / "lock.yml").write_text(
        "name: x\nchannels:\n  - conda-forge\ndependencies:\n"
        "  - python=3.11\n  - pip\n  - pip:\n"
        "      - numpy==1.26.4\n      - scanpy==1.10.4\n")
    class Dir:
        name = "legacy"
        spec = {}
        path = d
    req = R.requirement(Dir())
    ck("the lock's python becomes an exact constraint", req["python"] == "==3.11", str(req))
    ck("and its pins become exact constraints",
       req["packages"] == {"numpy": "==1.26.4", "scanpy": "==1.10.4"}, str(req["packages"]))
    ck("so a locked plugin can share with a compatible requirement-shaped one",
       len(R.group_by_compatibility([Dir(), K("new", ">=3.11,<3.12",
                                              {"numpy": "==1.26.4"})])) == 1)

print("\nnot clashing is not the same as being compatible")
# An R plugin pinning r-base and 60 conda packages, naming NO python and NO pip package, clashes
# with nothing - so greedy first-fit put it in the python group with four python plugins. One
# 6 GB environment holding two language stacks, on the strength of an absence of evidence.
class Silent:
    name = "silent"
    spec = {"requires": {"conda": {"r-base": "4.3.3"}, "r": ["owner/repo@" + "a" * 40]}}
gs = R.group_by_compatibility([K("py", "==3.11", {"numpy": "==1.26.4"}), Silent()])
ck("a requirement with nothing in common is isolated", len(gs) == 2,
   str([g.members for g in gs]))
alone = [g for g in gs if g.members == ["silent"]]
ck("and told that the reason is silence, not a conflict",
   bool(alone) and "nothing in common" in alone[0].why_alone,
   str([g.why_alone for g in gs]))
ck("two plugins that both pin the interpreter still share",
   len(R.group_by_compatibility([K("a", ">=3.10,<3.13", {"x": "==1"}),
                                 K("b", "==3.11", {"y": "==2"})])) == 1,
   "overlapping on the interpreter is the ordinary case and the one that saves the disk")

print("\na requirement is five things, not two")
LOCK = ("name: x\nchannels:\n  - conda-forge\n  - bioconda\ndependencies:\n"
        "  - r-base=4.3.3\n  - petsc4py=3.20\n  - pip\n  - pip:\n      - numpy==1.26.4\n"
        "r:\n  - NMF==0.28\n  - owner/repo@" + "b" * 40 + "\n")
req = R.from_lock(LOCK)
ck("conda packages are read", req["conda"] == {"r-base": "4.3.3", "petsc4py": "3.20"},
   str(req["conda"]))
ck("channels are read", req["channels"] == ["conda-forge", "bioconda"], str(req["channels"]))
ck("r pins are read", len(req["r"]) == 2, str(req["r"]))
ck("pip pins are still read", req["packages"] == {"numpy": "==1.26.4"}, str(req["packages"]))
ck("and `pip` itself is not a conda package", "pip" not in req["conda"], str(req["conda"]))
onlyconda = R.from_lock("dependencies:\n  - r-base=4.3.3\n")
ck("a lock with no python and no pip is still a REQUIREMENT", onlyconda is not None,
   "reading only the pip section made such a plugin invisible to the resolver, and the "
   "builder then fell back to a private path nobody planned")

print("\nconda match-specs are not pip specifiers")
a = type("A", (), {"name": "a", "spec": {"requires": {"python": "==3.11",
                                                      "conda": {"petsc4py": "3.20"}}}})()
b = type("B", (), {"name": "b", "spec": {"requires": {"python": "==3.11",
                                                      "conda": {"petsc4py": "3.21"}}}})()
c = type("C", (), {"name": "c", "spec": {"requires": {"python": "==3.11",
                                                      "conda": {"petsc4py": "3.20"}}}})()
gs = R.group_by_compatibility([a, b])
ck("two different conda specs isolate", len(gs) == 2, str([g.members for g in gs]))
ck("and the reason names both", any("3.20" in (g.why_alone or "") and "3.21" in (g.why_alone or "")
                                    for g in gs), str([g.why_alone for g in gs]))
ck("identical conda specs share", len(R.group_by_compatibility([a, c])) == 1)
ck("the group NAME covers conda, so two groups cannot claim one directory",
   R.group_by_compatibility([a])[0].name != R.group_by_compatibility([b])[0].name)

print("\na constraint is not a version, and the builder needs a version")
ck("an exact pin is the answer", R.concrete_python(">=3.10,<3.13,==3.11") == "3.11")
ck("a range resolves to the highest candidate that satisfies it",
   R.concrete_python(">=3.10,<3.13") == "3.12", R.concrete_python(">=3.10,<3.13"))
ck("an unconstrained interpreter is None", R.concrete_python("") is None)
for bad in (">=4.0", "==3.11,<3.11"):
    try:
        R.concrete_python(bad)
        ck(f"{bad} raises rather than guessing", False, "it returned a version")
    except ValueError as e:
        ck(f"{bad} raises rather than guessing", True)

print("\nreport says what was decided and why")
lines = []
R.report(R.group_by_compatibility(mixed), log=lines.append)
txt = "\n".join(lines)
ck("it counts environments and plugins", "environment(s) will satisfy" in txt)
ck("it names who shares each", "shared by:" in txt)
ck("and why a lone plugin is alone", "ALONE because" in txt, txt)

print("\n" + ("resolution holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
