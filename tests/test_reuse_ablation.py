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


# ============================================================================================
# A HOST CHANGE MUST INVALIDATE REUSE, and for a long time it did not.
#
# The key covered the PLUGIN's version and nothing about the code that writes an instance. So
# when the host gained a drawing audit every panel was supposed to carry, the next run adopted
# fourteen of fifteen instances from before it existed, the audit never ran, and the station
# reading it reported "no panel carries an audit" on a tool that had just grown one. Nothing was
# broken except that reuse was too permissive, and nothing said so.
# ============================================================================================
print("\na change to the HOST invalidates a cached result")
from scprofile import landscape as _LS                                          # noqa: E402

_base = {"plugin": "p", "version": "1.0", "unit": "u", "input": "/x.h5ad",
         "input_size": 10, "input_mtime": 1, "params": {}, "keys": {}, "host": "aaaaaaaaaaaa"}
_same = dict(_base)
_newhost = dict(_base, host="bbbbbbbbbbbb")
_noneho = dict(_base, host=None)
check("the same instance under the same host reuses",
      _LS.reuse_key(_base) == _LS.reuse_key(_same))
check("a different host version is a DIFFERENT result",
      _LS.reuse_key(_base) != _LS.reuse_key(_newhost),
      "a host change that alters what an instance records must not be adopted over")
check("and an instance written before the host was recorded does not match a current one",
      _LS.reuse_key(_noneho) != _LS.reuse_key(_base))
check("the host version is scoped to the modules that WRITE an instance",
      set(_LS.HOST_MODULES) == {"_entry.py", "plugin.py", "manifest.py"},
      "folding in the reporter or the CLI would invalidate every cached result on every commit")
check("and it is stable when nothing changes",
      _LS.host_version() == _LS.host_version())
