"""Turn many plugins' environment REQUIREMENTS into as few environments as will satisfy them.

THE LAYERING THIS FIXES

A plugin used to declare a private, fully-pinned environment - `env: {python, pip: [16 exact
pins]}` - and the builder built one per plugin. That put a resolution decision inside the plugin,
where it cannot be made: a plugin cannot know what else is installed, so every plugin assumed it
was alone and got its own 1.5 GB copy of the same stack. Three of the shipped plugins wanted
numpy 1.26 / pandas 2.2 / scanpy 1.10. That is one environment, built three times.

The layers, corrected:

    PLUGIN     declares what it NEEDS - constraints, not a lock. "scanpy >=1.10,<1.11".
    BUILDER    RESOLVES those needs: which plugins can share an environment, which cannot, and
               WHY - naming the package and the two constraints that clash.
    PLANNER    uses what was resolved, and never asks a plugin about installation.

A plugin declaring a requirement is stating a fact about itself that stays true anywhere. A
plugin declaring a lock is answering a question that belongs to the machine it lands on.

WHEN IN DOUBT, ISOLATE. A wrongly shared environment is a plugin running against versions it was
never tested on, which is the failure that returns a plausible number rather than an error. A
wrongly isolated one costs disk. Those are not comparable, so anything this module cannot prove
compatible gets its own environment and says so.
"""
from __future__ import annotations

import hashlib
import re

#: A constraint is a comma-joined list of `<op><version>` clauses, as pip writes them.
_CLAUSE = re.compile(r"^\s*(==|!=|>=|<=|>|<|~=)?\s*([0-9][0-9A-Za-z.\-+*]*)\s*$")
_OPS = ("==", "!=", ">=", "<=", ">", "<", "~=")


def _ver(s):
    """A comparable version tuple. Non-numeric trailing parts sort before numeric ones.

    Deliberately small: this compares release segments, which is what pins in this project use.
    It is not a full PEP 440 implementation, and where it cannot decide it says so rather than
    guessing - see `compatible`.
    """
    out = []
    for part in str(s).split("."):
        m = re.match(r"^(\d+)", part)
        out.append(int(m.group(1)) if m else -1)
    return tuple(out)


def _pad(a, b):
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)), b + (0,) * (n - len(b))


def parse(spec):
    """`">=1.10,<1.11"` -> [("&gt;=", (1,10)), ("&lt;", (1,11))]. Raises on anything unparseable."""
    out = []
    for raw in str(spec or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        op = next((o for o in _OPS if raw.startswith(o)), "==")
        rest = raw[len(op):] if raw.startswith(op) else raw
        m = _CLAUSE.match(rest)
        if not m:
            raise ValueError(f"cannot parse version constraint {raw!r}")
        out.append((op, _ver(m.group(2))))
    return out


def satisfies(version, clauses):
    """Does a concrete version satisfy every clause?"""
    v = _ver(version)
    for op, w in clauses:
        a, b = _pad(v, w)
        if op == "==" and a != b:
            return False
        if op == "!=" and a == b:
            return False
        if op == ">=" and a < b:
            return False
        if op == "<=" and a > b:
            return False
        if op == ">" and a <= b:
            return False
        if op == "<" and a >= b:
            return False
        if op == "~=":
            # ~=1.2.3 means >=1.2.3, ==1.2.*
            if a < b:
                return False
            if len(w) >= 2 and a[:len(w) - 1] != b[:len(w) - 1]:
                return False
    return True


def compatible(spec_a, spec_b):
    """(bool, why). Can one version satisfy both constraints?

    Returns False ONLY when the two are provably disjoint. Where this cannot decide - an operator
    combination it does not model - it returns True and the caller falls back on the exactness
    check below, because a resolver that guesses "incompatible" fragments environments and one
    that guesses "compatible" installs a plugin against versions nobody tested.
    """
    try:
        A, B = parse(spec_a), parse(spec_b)
    except ValueError as e:
        return False, f"unparseable constraint ({e})"

    # Two exact pins on the same package are the common, decidable case.
    ea = [w for op, w in A if op == "=="]
    eb = [w for op, w in B if op == "=="]
    for x in ea:
        for y in eb:
            a, b = _pad(x, y)
            if a != b:
                return False, (f"pinned to {'.'.join(map(str, x))} and "
                               f"{'.'.join(map(str, y))}")
    # An exact pin against a range is decidable too.
    for pins, other, side in ((ea, B, spec_b), (eb, A, spec_a)):
        for x in pins:
            if not satisfies(".".join(map(str, x)), other):
                return False, (f"{'.'.join(map(str, x))} does not satisfy {side!r}")
    # Two ranges: the lower bound of one at or above the upper bound of the other. STRICTNESS
    # MATTERS and ignoring it missed the commonest real case: `>=1.10,<1.11` against `>=1.11` are
    # disjoint, because `<1.11` excludes 1.11 exactly - and a bounds check that only tested
    # `lo > hi` called them compatible and would have merged two environments that cannot both
    # be satisfied.
    def bounds(cl):
        los = [(w, op == ">") for op, w in cl if op in (">=", ">")]
        his = [(w, op == "<") for op, w in cl if op in ("<=", "<")]
        lo = max(los, key=lambda x: x[0]) if los else None
        hi = min(his, key=lambda x: x[0]) if his else None
        return lo, hi
    la, ha = bounds(A)
    lb, hb = bounds(B)
    for lo, hi, s1, s2 in ((la, hb, spec_a, spec_b), (lb, ha, spec_b, spec_a)):
        if lo is not None and hi is not None:
            x, y = _pad(lo[0], hi[0])
            if x > y or (x == y and (lo[1] or hi[1])):
                return False, f"{s1!r} and {s2!r} do not overlap"
    return True, ""


class Group:
    """One environment, and every plugin that will share it."""

    def __init__(self, python, packages, members, why_alone=""):
        self.python = python
        self.packages = dict(packages)          # {name: constraint}
        self.members = sorted(members)
        #: Empty when this group holds more than one plugin. When a plugin is alone, this says
        #: WHICH package and WHICH two constraints forced it - never just "incompatible".
        self.why_alone = why_alone

    @property
    def name(self):
        """A content-addressed name, so the same requirements give the same environment.

        Named for its CONTENT and not for a plugin: an environment named `scprofile-velocity`
        that three plugins share is a lie the moment the second one joins, and the first plugin
        to be removed takes its name with it.
        """
        key = repr((self.python, sorted(self.packages.items())))
        return "scprofile-env-" + hashlib.sha256(key.encode()).hexdigest()[:10]

    def as_dict(self):
        return {"name": self.name, "python": self.python, "packages": self.packages,
                "members": self.members, "why_alone": self.why_alone}

    def __repr__(self):
        return f"<Group {self.name} python={self.python} {len(self.members)} member(s)>"


def requirement(kernel):
    """A plugin's declared environment requirement, or None if it needs no environment."""
    spec = getattr(kernel, "spec", {}) or {}
    req = spec.get("requires")
    if req:
        return {"python": str(req.get("python") or ""),
                "packages": dict(req.get("packages") or {})}
    # A FULLY-PINNED ENVIRONMENT IS STILL A REQUIREMENT - the strictest possible one. Both older
    # shapes are read as exact constraints, so nothing that worked stops working and every plugin
    # takes part in resolution whichever shape it uses.
    #
    # A pinned plugin will usually end up alone, and that is the honest outcome: `==1.26.4` says
    # only that version works, and a resolver has no business softening a claim the plugin made.
    # Loosening it is the MAINTAINER'S decision, and `validate` suggests it.
    env = spec.get("env")
    if env:
        return {"python": f"=={env.get('python')}" if env.get("python") else "",
                "packages": _exact(env.get("pip") or [])}

    lock = getattr(kernel, "path", None)
    lock = (lock / "lock.yml") if lock is not None and lock.is_dir() else None
    if lock is None or not lock.exists():
        return None
    py, pins, in_pip = "", [], False
    for raw in lock.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s in ("pip:", "- pip:"):
            in_pip = True
            continue
        if s.startswith("- python="):
            py = "==" + s.split("=", 1)[1].strip()
        elif in_pip and s.startswith("- "):
            pins.append(s[2:].strip())
    return {"python": py, "packages": _exact(pins)} if (py or pins) else None


def _exact(pins):
    """`["numpy==1.26.4", ...]` -> `{"numpy": "==1.26.4"}`. Anything not pinned is skipped."""
    out = {}
    for pin in pins:
        if "==" in pin:
            n, v = pin.split("==", 1)
            out[n.strip()] = f"=={v.strip().split()[0]}"
    return out


def group_by_compatibility(kernels, log=None):
    """Resolve every requirement into as few environments as will satisfy them all.

    Greedy and ORDER-INDEPENDENT: kernels are considered in sorted order, and a plugin joins the
    first group it is provably compatible with. Deterministic, because a resolver that gives a
    different answer on a different day gives a different environment on a different day.
    """
    say = log or (lambda *_a: None)
    groups = []
    for k in sorted(kernels, key=lambda x: x.name):
        req = requirement(k)
        if req is None:
            continue
        placed = None
        blockers = []
        for g in groups:
            ok, why = _fits(g, req)
            if ok:
                placed = g
                break
            blockers.append(f"{g.members[0]}: {why}")
        if placed is None:
            g = Group(req["python"], req["packages"], [k.name],
                      why_alone=("; ".join(blockers[:2]) if blockers else ""))
            groups.append(g)
            say(f"  {k.name}: new environment"
                + (f" - cannot share ({blockers[0]})" if blockers else ""))
        else:
            _merge(placed, req)
            placed.members = sorted(placed.members + [k.name])
            placed.why_alone = ""
            say(f"  {k.name}: shares with {', '.join(n for n in placed.members if n != k.name)}")
    return groups


def _fits(group, req):
    """Can this requirement join this group? (bool, why not)."""
    if req["python"] and group.python:
        ok, why = compatible(group.python, req["python"])
        if not ok:
            return False, f"python {why}"
    for name, spec in sorted(req["packages"].items()):
        if name in group.packages:
            ok, why = compatible(group.packages[name], spec)
            if not ok:
                return False, f"{name} {why}"
    return True, ""


def _join(existing, incoming):
    """Every clause from both, each kept once, in a stable order.

    Deduplicated because four plugins pinning the same python produced
    `>=3.10,<3.13,==3.11,==3.11,==3.11` - correct, and unreadable, and it changes the group's
    content-addressed NAME with each redundant member, so the same set of plugins could land in
    two differently-named directories depending on how many of them repeated a clause.
    """
    seen, out = set(), []
    for clause in [c.strip() for c in f"{existing},{incoming}".split(",") if c.strip()]:
        if clause not in seen:
            seen.add(clause)
            out.append(clause)
    return ",".join(out)


def _merge(group, req):
    """Tighten a group's constraints with a new member's. Never loosens."""
    if req["python"]:
        group.python = _join(group.python, req["python"]) if group.python else req["python"]
    for name, spec in req["packages"].items():
        group.packages[name] = (_join(group.packages[name], spec)
                                if name in group.packages else spec)


def report(groups, log=print):
    """What the builder decided, and why. Printed because a shared environment is a decision."""
    log(f"\n{len(groups)} environment(s) will satisfy "
        f"{sum(len(g.members) for g in groups)} plugin(s):")
    for g in sorted(groups, key=lambda x: (-len(x.members), x.name)):
        log(f"  {g.name}  python {g.python or 'unconstrained'}  "
            f"{len(g.packages)} package(s)")
        log(f"      shared by: {', '.join(g.members)}")
        if len(g.members) == 1 and g.why_alone:
            log(f"      ALONE because {g.why_alone}")
