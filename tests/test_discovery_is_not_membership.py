""""CellChat does not export it" and "my pattern did not match it" were one sentence.

MEASURED, ON THE INSTALLED PACKAGE. The accounting check reported five declared plots as ones
CellChat does not export. Asked for membership in `getNamespaceExports` directly, with no pattern
in the way:

    compareInteractions            EXPORTED
    identifyCommunicationPatterns  EXPORTED
    rankNet                        EXPORTED
    rankSimilarity                 EXPORTED
    interaction_lr                 absent

Four of the five are there and were simply unmatched - none of them begins with `netVisual`,
`netAnalysis`, `plot`, `show` or `StackedVln`, which is the whole discovery pattern. One is
genuinely gone.

WHY IT MATTERS MORE THAN FOUR NAMES. Four false alarms standing in front of one real defect is
worse than silence: the real one reads as more of the same. And a pattern that misses four
functions THIS PLUGIN ITSELF USES misses others nobody has declared, so the count of exported
plots the check reports is a floor and not a number.

So the two questions are separated. Discovery - what might be missing - can only ever be a
pattern, because a package's naming convention is not a definition. Staleness - is what I
declared still there - is membership, and is exact.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib.util as _iu                                              # noqa: E402

_sp = _iu.spec_from_file_location("cellchat_mod",
                                  Path(__file__).resolve().parent.parent / "kernels" / "cellchat.py")
CC = _iu.module_from_spec(_sp)
_sp.loader.exec_module(CC)

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


# the probe returns both sections
matched, every = CC._split_inventory(
    "MATCHED\nnetVisual_bubble\nplotGeneExpression\n"
    "ALL\nnetVisual_bubble\nplotGeneExpression\nrankNet\nggPalette\n")
check(matched == ["netVisual_bubble", "plotGeneExpression"], f"matched: {matched}")
check("rankNet" in every and "rankNet" not in matched,
      "the probe cannot tell an unmatched export from an absent one")

# and the R side asks for both
check("MATCHED" in CC._R_INVENTORY and "ALL" in CC._R_INVENTORY,
      "the R probe no longer returns every export, so membership cannot be asked")
check("getNamespaceExports" in CC._R_INVENTORY, "the probe stopped reading the namespace")

# the discovery pattern genuinely does not match the four that are exported
import re                                                                 # noqa: E402
pat = re.search(r'grep\("(\^\([^"]+\))"', CC._R_INVENTORY)
check(pat is not None, "the discovery pattern could not be read out of the probe")
if pat:
    rx = re.compile(pat.group(1))
    for name in ("compareInteractions", "identifyCommunicationPatterns",
                 "rankNet", "rankSimilarity"):
        check(not rx.match(name),
              f"{name} now matches the discovery pattern - if the pattern was widened, this "
              f"test's premise changed and its numbers need remeasuring")
    for name in ("netVisual_bubble", "netAnalysis_dot", "plotGeneExpression"):
        check(bool(rx.match(name)), f"the pattern stopped matching {name}")

if fails:
    print("FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ok - discovery is a pattern and staleness is membership, and the check no longer "
      "reports one as the other")
