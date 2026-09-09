"""Editing what a plugin SAYS must never cost an environment rebuild.

THE RISK THIS PINS. An environment here is content-addressed: the same requirements give the same
directory, an existing directory that matches is reused, and one install proves the selftest of
every plugin in the group. Nine plugins fold into three environments, and the velocity one alone
is a 1.5 GB build measured in tens of minutes on the cluster.

The writing layer touches every plugin's declaration - a `drawn_by` on every figure, a legend at
every draw site, a caption reworded. If any of that reached the address, a round of prose edits
would silently invalidate three cached environments and the next run would reinstall all of them.
Nothing would fail; the work would just take an hour longer for no reason, and it is exactly the
kind of cost nobody attributes to the change that caused it.

So the address covers the REQUIREMENTS and nothing else, and this says so in a way that fails if
someone widens the key.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scprofile import resolve as RS                                       # noqa: E402
from scprofile.kernels import discover                                    # noqa: E402

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


groups = RS.group_by_compatibility(list(discover().values()))
before = {g.name: sorted(g.members) for g in groups}

check(len(groups) >= 2, f"the resolver folded everything into {len(groups)} group(s); "
                        f"reuse is not being exercised at all")

# 1. THE KEY IS THE REQUIREMENTS. Named explicitly, so widening it is a deliberate act.
import inspect                                                            # noqa: E402
key = inspect.getsource(RS.Group.name.fget)
for word in ("caption", "drawn_by", "report", "figures", "summary", "question", "source"):
    check(word not in key,
          f"the environment address reads {word!r}: editing prose would rebuild an environment")
for word in ("self.python", "self.packages", "self.conda", "self.channels", "self.r"):
    check(word in key, f"the environment address no longer covers {word}")

# 2. AND THE SAME QUESTION ASKED OF THE REAL PLUGINS, because a key can be right and the value
#    fed to it wrong. Every figure's legend and provenance is rewritten in memory; the addresses
#    must not move.
for k in discover().values():
    rep = getattr(k, "report", None)
    if isinstance(rep, dict):
        for f in rep.get("figures") or []:
            if isinstance(f, dict):
                f["caption"] = "a completely different sentence about this panel"
                f["question"] = "a completely different question"
                f["drawn_by"] = "tool" if f.get("drawn_by") == "plugin" else "plugin"
    for attr in ("summary", "when_to_use"):
        if isinstance(getattr(k, attr, None), str):
            try:
                setattr(k, attr, "rewritten")
            except AttributeError:
                pass

after = {g.name: sorted(g.members)
         for g in RS.group_by_compatibility(list(discover().values()))}
check(before == after,
      f"rewriting every legend changed the environment plan:\n  before {before}\n  after  {after}")

if fails:
    print("FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"ok - {len(before)} environment(s) for {sum(len(v) for v in before.values())} plugins, "
      f"and no sentence in any of them is in the address")
