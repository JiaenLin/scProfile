""""The upstream does not export it" and "the rule did not match it" were one sentence.

MEASURED, ON THE INSTALLED PACKAGE. The accounting once reported five declared plots as ones
CellChat does not export. Asked for membership in `getNamespaceExports` directly, with no rule in
the way, four of the five were there - `compareInteractions`, `identifyCommunicationPatterns`,
`rankNet`, `rankSimilarity` - and simply unmatched by the discovery pattern of the day; one,
`interaction_lr`, was genuinely gone. Four false alarms standing in front of one real defect is
worse than silence: the real one reads as more of the same.

So the two questions are separated. Discovery - what might be missing - can only ever be a
rule, because a package's naming is not a definition; the maker's extractor owns it now, and
its rule is behaviour (a body that reaches a device), not a prefix. Staleness - is what I
declared still there - is membership, and is exact. The plugin used to carry its own probe for
this (harness ADR-0016 step 4 deleted it with the rest of the plugin's inventory glue); the
host's accounting is where the two answers meet, and this is where they must stay apart.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scprofile import native as N                                         # noqa: E402

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


DECLARED = {"netVisual_bubble": {"use": "figures/native_bubble.png"},
            "rankNet": {"use": "figures/nativecmp_rankNet.png"},          # exported, unmatched
            "interaction_lr": {"use": "figures/nativecmp_interaction_lr.png"},  # gone
            "ggPalette": {"skip": "not_applicable", "evidence": "returns colours; draws nothing"}}
INVENTORY = ["netVisual_bubble", "ggPalette"]                                # what the rule saw
EVERY = ["netVisual_bubble", "ggPalette", "rankNet", "netVisual_circle"]     # what R exports

used, skipped, problems = N.account(INVENTORY, DECLARED, every=EVERY)
check("rankNet" in used, "a declared, exported function the rule missed is not counted as used")
check("interaction_lr" in dict(problems)
      and "does not export" in dict(problems)["interaction_lr"],
      f"the one genuinely absent function is not reported as stale: {problems}")
check("rankNet" not in dict(problems),
      f"an exported function the rule missed is reported as if the tool had lost it: {problems}")
check("ggPalette" in skipped, "a valid skip stopped being one when `every` was given")

# without the namespace, the sentence says it cannot tell
u2, s2, p2 = N.account(INVENTORY, DECLARED)
msgs = dict(p2)
check("rankNet" in msgs and "interaction_lr" in msgs,
      f"without the namespace both unmatched names must be raised: {p2}")
check(all("or the inventory's rule" in msgs[k] for k in ("rankNet", "interaction_lr")),
      f"without the namespace the sentence claims to know which it is: {p2}")
check("does not export this, so the entry is stale" not in msgs.get("rankNet", ""),
      "the old sentence - a claim the accounting cannot make - is back")

if fails:
    print("FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ok - an unmatched export and an absent one are two answers, and the accounting says which")
