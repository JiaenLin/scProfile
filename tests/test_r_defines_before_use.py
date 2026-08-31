"""An embedded R script must define a helper BEFORE it calls it. R does not hoist.

WHAT THIS COST: a phase clock was added to measure where a run spends its time, and `mark` was
defined next to the other helpers - far below its first call. Every unit of the run died on
`Error in mark("read the matrix") : could not find function "mark"`, after the host had already
written a 1.4 GB matrix for each of them. Python would have accepted the same arrangement, which
is exactly why this is easy to write and easy to miss.

Only helpers the script defines ITSELF are checked; anything from a library is out of scope.

AND A SECOND FAILURE THE ORDER CHECK CANNOT SEE: a helper CALLED HERE AND DEFINED NOWHERE HERE.
Checking order presumes the definition exists. A script written by copying its sibling inherits
the sibling's calls and not always its definitions - measured, a plot wrapper was called in one
embedded script and defined only in the other, and R halted the whole loop at the first call with
"could not find function". Half an analysis was drawn and the tally reported no failure, because
the process died before it printed one. A name defined in a SIBLING script of the same plugin and
not in this one is the signature of that copy, and is precise enough to check without guessing at
which names are library functions.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []
CHECKED = 0

for f in sorted((ROOT / "kernels").glob("*.py")):
    src = f.read_text()
    q3 = chr(34) * 3
    pat = r"(_R_[A-Z_]+)\s*=\s*r?(" + q3 + "|'''" + r")(.*?)\2"
    for m in re.finditer(pat, src, re.S):
        name, body = m.group(1), m.group(3)
        # `fn <- function(` at the start of a line is a definition this script owns
        defs = {d.group(1): d.start()
                for d in re.finditer(r"^([A-Za-z_.][\w.]*)\s*<-\s*function\s*\(", body, re.M)}
        if not defs:
            continue
        CHECKED += 1
        for fn, at in defs.items():
            # the first CALL that is not the definition itself
            first = None
            for c in re.finditer(r"(?<![\w.$])" + re.escape(fn) + r"\s*\(", body):
                if abs(c.start() - at) < 2:
                    continue
                if body[max(0, c.start() - 30):c.start()].rstrip().endswith("<-"):
                    continue
                first = c.start()
                break
            if first is not None and first < at:
                line = body[:first].count("\n") + 1
                dline = body[:at].count("\n") + 1
                FAILURES.append(
                    f"{f.name} / {name}: `{fn}` is called at line {line} and only defined at "
                    f"line {dline}. R does not hoist; this dies at run time.")

if CHECKED == 0:
    print("FAIL")
    print("  - no embedded R script defines a helper; this check proved nothing")
    raise SystemExit(1)

# ---------------------------------------------------------------------------------------------
# CALLED HERE, DEFINED ONLY IN A SIBLING. See the note at the top: this is the copy-paste failure
# the order check cannot see, because order presumes existence.
import re as _re2                                                          # noqa: E402

for _f in sorted(ROOT.glob("kernels/*.py")):
    _src = _f.read_text(encoding="utf-8")
    _scripts = dict(_re2.findall(r"^(_R_[A-Z_]+)\s*=\s*r?\"\"\"(.*?)\"\"\"",
                                 _src, _re2.S | _re2.M))
    if len(_scripts) < 2:
        continue
    _defs = {k: set(_re2.findall(r"^\s*\.?([A-Za-z_][A-Za-z0-9_.]*)\s*<-\s*function", v,
                                 _re2.M))
             for k, v in _scripts.items()}
    for _k, _body in _scripts.items():
        _elsewhere = set().union(*[v for j, v in _defs.items() if j != _k]) - _defs[_k]
        for _name in sorted(_elsewhere):
            if _re2.search(r"(?<![A-Za-z0-9_.])" + _re2.escape(_name) + r"\s*\(", _body):
                FAILURES.append(
                    f"{_f.name} / {_k}: calls {_name}() which is defined in a SIBLING embedded "
                    f"script and not in this one. R halts at the first call with 'could not find "
                    f"function', part-way through whatever loop it was in, and a tally printed "
                    f"after that point never runs - so the run reports no failure.")

if FAILURES:
    print("FAIL")
    for x in FAILURES:
        print("  -", x)
    raise SystemExit(1)
print(f"ok: {CHECKED} embedded R script(s); every helper is defined before it is called")
