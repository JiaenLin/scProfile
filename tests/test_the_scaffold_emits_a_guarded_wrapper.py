"""A plugin that draws through R is GIVEN the wrapper that honours its ceilings.

`sch dev convert placement` requires a plugin's draw wrappers to refuse past the declared ceiling,
because the host cannot reach into another interpreter's graphics device. A requirement the tool
makes and does not satisfy is a requirement every author meets by hand: while this was
hand-written, one plugin carried three copies of the same helper, one per embedded script, and
nothing checked any of them.

THE RULE IS READ FROM THIS REPOSITORY'S OWN DECLARATION, not restated here. `DEVPOINTS.yaml` says
what the drawing code must name and what leaving a wrapper looks like; if that declaration changes
this test follows it, which is the only way the generated wrapper and the check that demands it
cannot drift apart.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import scaffold as S                                       # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


text = (ROOT / "DEVPOINTS.yaml").read_text(encoding="utf-8")
m = re.search(r"enforced_by:\s*\n\s*token:\s*(\S+)\s*\n\s*returns:\s*(\S+)", text)
check(m is not None, "DEVPOINTS.yaml declares no `enforced_by`, so nothing says what a wrapper "
                     "must read; the check that demands it cannot be satisfied on purpose")

if m:
    token, returns = m.group(1), m.group(2)
    body = S.R_DRAW

    # THE SAME SHAPE THE MAKER LOOKS FOR: a conditional naming the token that leaves.
    guards = [l.strip() for l in body.splitlines()
              if l.strip().startswith("if") and token in l.strip() and returns in l.strip()]
    check(len(guards) >= 1,
          f"the generated wrapper has {len(guards)} guard(s) naming {token!r} and returning, so "
          f"nothing in it refuses past a declared ceiling")

    def body_of(fn):
        mm = re.search(rf"^{fn} <- function\([^)]*\)\s*\{{\n(.*?)\n\}}", body, re.S | re.M)
        return mm.group(1) if mm else None

    # EVERY PUBLIC WRAPPER REFUSES BEFORE IT DRAWS - directly, or through the one it hands the
    # expression to. THE FIRST VERSION DEMANDED THE GUARD BE EACH WRAPPER'S FIRST STATEMENT,
    # which is a demand that the guard be WRITTEN TWICE: `npng` and `ndev` differ in one line,
    # and the moment they were factored onto a single guarded body this check failed the
    # correct arrangement and would have passed the duplicated one. A check that rewards
    # copying mechanism, inside the file that exists to stop mechanism being copied.
    for fn in ("npng", "ndev"):
        b = body_of(fn)
        check(b is not None, f"the generated wrapper defines no {fn}")
        if not b:
            continue
        first = next((l.strip() for l in b.splitlines() if l.strip()), "")
        if first.startswith("if") and token in first:
            continue
        hop = re.match(r"([.\w]+)\s*\(", first)
        inner = body_of(hop.group(1)) if hop else None
        check(inner is not None,
              f"{fn}'s first statement is {first[:60]!r} - neither the ceiling guard nor a call "
              f"to another wrapper defined here")
        if inner:
            lines = [l.strip() for l in inner.splitlines() if l.strip()]
            gi = next((i for i, l in enumerate(lines)
                       if l.startswith("if") and token in l and returns in l), -1)
            di = next((i for i, l in enumerate(lines) if "grDevices::png(" in l), len(lines))
            check(gi >= 0, f"{fn} delegates to `{hop.group(1)}`, which never names {token!r}")
            check(gi < di, f"{fn} delegates to `{hop.group(1)}`, which opens the device before "
                           f"it consults the ceiling - the panel is computed either way")

    # THE LEGEND SLOT SURVIVES. The maker finds it by one language-neutral rule - the parameter
    # whose default is the empty string - so a generated wrapper that dropped it would produce a
    # plugin whose every draw site reports as having nowhere to put a legend.
    check(len(re.findall(r'legend = ""', body)) >= 3,
          "the generated wrapper has no parameter defaulting to the empty string, so the maker "
          "can find no legend slot in it")

    # ONE DEFINITION, NOT ONE PER SCRIPT. The hand-written version was copied three times.
    check(body.count(".at_ceiling <- function") == 1,
          "the generated wrapper defines the guard more than once")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: the scaffold emits a wrapper that already satisfies the check the maker makes")
