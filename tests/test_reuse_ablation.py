"""Ablation over the reuse decision. The cases live in `scprofile.selfcheck`.

ONE IMPLEMENTATION, TWO CALLERS: the suite runs them here, and `scprofile check --deep` runs
them on an installation where a test file may not be present. A copy in each place is two
copies that drift.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import selfcheck                                            # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"   {detail}" if detail and not cond
                                                      else ""))
    if not cond:
        FAILED.append(name)


print("reuse behaves correctly under ablation")
rows = selfcheck.reuse_ablation()
for title, expect, got, ok, detail in rows:
    check(title, ok, f"expected {expect}, got {got} — {detail}")
check("the ablation covered every failure mode it claims", len(rows) >= 8, str(len(rows)))

ok_hl, why_hl = selfcheck.adoption_is_a_hardlink()
check("adoption shares the inode rather than copying", ok_hl, why_hl)

print("\n" + ("reuse holds" if not FAILED else f"{len(FAILED)} FAILED: {FAILED}"))
sys.exit(1 if FAILED else 0)
