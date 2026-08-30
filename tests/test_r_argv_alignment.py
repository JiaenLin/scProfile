"""The arguments Python passes to an embedded R script must line up with the ones R reads.

WHAT THIS COST: the cache directory was appended as the 11th argument and read in R as
`args[12]`. R returned nothing for it, the script fell back to the instance directory, and the
whole cross-run object cache did nothing - on a run where every log line looked normal, every
figure was correct, and eighteen units each paid for a full inference again. Nothing failed.

Off-by-one in a positional interface is invisible at runtime by construction, so it is checked
here: count what the caller appends, count the highest index the script reads, and require them
to agree.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []
CHECKED = 0

def _blocks(src):
    out = {}
    q3 = chr(34) * 3
    pat = r'(_R_[A-Z_]+)\s*=\s*r?(' + q3 + "|'''" + r')(.*?)\2'
    for m in re.finditer(pat, src, re.S):
        out[m.group(1)] = m.group(3)
    return out


for f in sorted((ROOT / "kernels").glob("*.py")):
    src = f.read_text()
    blocks = _blocks(src)
    # PAIR EACH CALLER WITH THE SCRIPT IT ACTUALLY WRITES. Taking the first R block that
    # mentions commandArgs paired the wrong two and reported a defect that was only the
    # pairing - a check that finds the wrong thing is worse than one that finds nothing.
    for m in re.finditer(r"\bargv\w*\s*=\s*\[", src):
        start = m.end() - 1
        depth, end = 0, start
        for j in range(start, len(src)):
            if src[j] == "[":
                depth += 1
            elif src[j] == "]":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        call = src[start + 1:end]
        depth, n_passed = 0, 1
        for ch in call:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                n_passed += 1
        n_passed -= 2          # the interpreter and the script path are not arguments
        if n_passed <= 0:
            continue
        before = src[max(0, m.start() - 1500):m.start()]
        hit = re.findall(r"write_text\((_R_[A-Z_]+)", before)
        if not hit:
            continue
        body = blocks.get(hit[-1])
        if not body or "commandArgs" not in body:
            continue
        CHECKED += 1
        idx = [int(x) for x in re.findall(r"\bargs\[(\d+)\]", body)]
        hi = max(idx) if idx else 0
        if hi > n_passed:
            FAILURES.append(
                f"{f.name} / {hit[-1]}: the caller appends {n_passed} argument(s) but the R "
                f"reads args[{hi}] - that index is always empty")
        missing = sorted(set(range(1, n_passed + 1)) - set(idx))
        if missing:
            FAILURES.append(
                f"{f.name} / {hit[-1]}: argument(s) {missing} are passed and never read")

if CHECKED == 0:
    print("FAIL")
    print("  - no embedded R script with positional arguments was found; this proved nothing")
    raise SystemExit(1)
if FAILURES:
    print("FAIL")
    for x in FAILURES:
        print("  -", x)
    raise SystemExit(1)
print(f"ok: {CHECKED} embedded script(s); every argument passed is read, and none is read "
      f"beyond what is passed")
