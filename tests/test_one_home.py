"""The repository is the only home, and the documents describe the code that is here.

Two failures this catches, both of which happened:

  MATERIAL WITH NO HOME. Manuscript drafts and every panel-rendering harness were written to a
  scratchpad while `DEVELOPMENT.md` said to ship it in the tool. None survived the session, so
  the one reusable thing - a way to redraw a panel from a finished run - was rebuilt from memory
  a dozen times and never committed.

  DOCUMENTS THAT DRIFTED FROM THE CODE. A skill described six rules and thirteen panel kinds
  when there were eleven and fifteen. A reference table listed a directory no run has ever
  written. Every one of those reads exactly like a correct document.

Run: python tests/test_one_home.py
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scprofile import panels as P, paper as PA                                  # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


CLI = (ROOT / "scprofile" / "cli.py").read_text(encoding="utf-8")
REF = (ROOT / "docs" / "REFERENCE.md").read_text(encoding="utf-8")

print("every command exists in both the CLI and the reference")
cmds = set(re.findall(r'add_parser\("([a-z_]+)"', CLI))
doc = set(re.findall(r"\| `scprofile ([a-z_]+)`", REF))
ck("every registered command is documented", cmds <= doc, str(sorted(cmds - doc)))
ck("and every documented command is registered", doc <= cmds, str(sorted(doc - cmds)))

# AN INDEPENDENT COUNT, KEPT ON PURPOSE NOW THAT THE SENTENCE IS GENERATED. These read like
# duplicates of the generated-block check in test_declaration.py and they are not: that one asks
# whether the document holds what the renderer produces, which is satisfied whenever both are
# wrong together. This one enumerates from `panels.py` and looks each id up in the file, so it
# checks the RENDERER as well as the document - and it earned its keep immediately, catching a
# wrap that silently dropped the first five ids from the description while still reading as a
# complete sentence. Do not delete it as redundant with the generator; it is the generator's
# only cross-check.
print("\nthe counts the documents claim are the counts the code has")
SKILL = ROOT / ".claude" / "skills" / "plugin-figures" / "SKILL.md"
# THE TOOL'S OWN WORD LIST, not a second one. This was a literal dict covering 6 and 11-17, so a
# seventeenth panel kind passed and an eighteenth would have failed with "?" - a check whose reach
# was set by whoever last widened it by hand. The count in the document is rendered from
# `generated._count`; asking the same function what to look for is what makes this a check of the
# document rather than a check of two hand-maintained tables agreeing.
from scprofile.generated import _count as _word                           # noqa: E402
if SKILL.is_file():
    head = SKILL.read_text(encoding="utf-8").split("---")[1]
    ck("the skill's panel-kind count is right",
       _word(len(P.KINDS)) in head, f"{len(P.KINDS)} kinds")
    ck("the skill's rule count is right",
       f"{_word(len(P.RULES))} rules" in head, f"{len(P.RULES)} rules")
    ck("every registered kind is named in the skill",
       all(k.id in head for k in P.KINDS),
       str([k.id for k in P.KINDS if k.id not in head]))
else:
    ck("the figures skill lives in this repository", False, str(SKILL))

print("\nevery test in a suite is a test the suite runs")
# EIGHT TESTS HAD NEVER EXECUTED. A file ending in `if __name__ == "__main__":` collects its tests
# from `globals()` at the moment that block runs - so a test function defined BELOW it is not yet
# defined, is not collected, and is silently not run. Two files had drifted that way, and four of
# the eight were the ratchet tests added the same morning, reported green on a run that never
# called them. A test that does not run is worse than a missing test: the count says it is covered.
import ast as _ast_om                                                           # noqa: E402
_dead = []
for _f in sorted((ROOT / "tests").glob("test_*.py")):
    _t = _ast_om.parse(_f.read_text(encoding="utf-8"))
    _main = next((n.lineno for n in _t.body if isinstance(n, _ast_om.If)
                  and _ast_om.unparse(n.test) == "__name__ == '__main__'"), None)
    if _main is None:
        continue
    _dead += [f"{_f.name}:{n.name}" for n in _t.body if isinstance(n, _ast_om.FunctionDef)
              and n.name.startswith("test_") and n.lineno > _main]
ck("no test is defined below the runner that collects it", not _dead, str(_dead[:6]))
# AND NO CODE AT ALL BELOW A MODULE-LEVEL `sys.exit`, which is the same defect in a second shape.
# The check above looks for test FUNCTIONS under `if __name__ == "__main__"`. Hours after writing
# it I appended a check to this very file below its own `sys.exit(...)`, where it was unreachable,
# and only noticed because I tried to prove it could fail. A guard that catches one spelling of a
# defect teaches you the defect is handled.
_after = []
for _f in sorted((ROOT / "tests").glob("test_*.py")):
    _t = _ast_om.parse(_f.read_text(encoding="utf-8"))
    _exit = next((n.lineno for n in _t.body if isinstance(n, _ast_om.Expr)
                  and isinstance(n.value, _ast_om.Call)
                  and _ast_om.unparse(n.value.func) in ("sys.exit", "exit")), None)
    if _exit is None:
        continue
    _live = [n for n in _t.body if n.lineno > _exit
             and not (isinstance(n, _ast_om.If)
                      and _ast_om.unparse(n.test) == "__name__ == '__main__'")]
    if _live:
        _after.append(f"{_f.name}: {len(_live)} statement(s) after sys.exit on line {_exit}")
ck("and no statement sits below a module-level sys.exit", not _after, str(_after[:4]))

print("\nevery path a document points at exists")
missing = []
for d in sorted((ROOT / "docs").glob("*.md")) + [ROOT / "README.md", ROOT / "DEVELOPMENT.md"]:
    body = d.read_text(encoding="utf-8")
    for m in re.findall(r"`((?:docs/|tests/|scprofile/|kernels/)[\w./-]+)`", body):
        if not (ROOT / m).exists() and not m.endswith("/"):
            missing.append(f"{d.name} -> {m}")
ck("no document points at a file that is not here", not missing, "; ".join(missing[:6]))

print("\nthe guideline's enforced list matches what the hook actually denies")
DEV = (ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")
HOOK = (ROOT / ".claude" / "hooks" / "dev_guideline.py").read_text(encoding="utf-8")
ck("the hook denies scratchpad material and the guideline says so",
   "_is_scratch" in HOOK and "scratchpad" in DEV.lower())
ck("the hook denies ad-hoc heredocs and the guideline says so",
   "heredoc" in HOOK and "heredoc" in DEV.lower())
ck("the guideline names the repository as the only home",
   "ONLY HOME" in DEV.upper())
ck("and the script it points people to is committed",
   (ROOT / "tests" / "preview_panels.py").is_file())
# THE COMMIT RULES FIRE ON THE REPOSITORY, NOT ON THE SESSION. A session rooted elsewhere made
# commits here past every rule, because the only trigger was a PreToolUse hook keyed to the
# session's root. The commit half now runs as a git hook under a committed hooks path, and the
# three parties that name that path read it from one module.
from scprofile import gate as _GATE
_pc = ROOT / _GATE.HOOKS_PATH / _GATE.PRE_COMMIT
ck("the commit gate is a committed git hook", _pc.is_file() and os.access(_pc, os.X_OK),
   str(_pc))
ck("and it runs the commit half of the guideline, not a copy of it",
   "--pre-commit" in _pc.read_text(encoding="utf-8") and "def pre_commit" in HOOK)
ck("the session hook refuses a commit while the gate is not installed",
   "installed(ROOT)" in HOOK and "install_command()" in HOOK)
# THE GATE IS THE ONE RUNNER. The commit half looped over tests/test_*.py itself, without the
# PYTHONPATH the runner sets, and the first real run refused on seven suites the runner passes.
ck("and the commit gate runs `tests/run_all.py`, not a copy of it",
   "run_all.py" in HOOK.split("def pre_commit")[1])
ck("the guideline says how to install it", _GATE.install_command() in DEV)

print("\nthe paper test is wired end to end, not only defined")
ck("the chain names it after review", re.search(r"review\s*(->|→)\s*(PAPER|paper)", REF)
   is not None)
ck("its limits are in the tool and in a document",
   len(PA.NARROW) >= 6 and (ROOT / "docs" / "PAPER_TEST.md").is_file())
ck("the written result is a run output, not a scratch file",
   "PAPER.md" in REF or "PAPER_CLAIMS" in REF)
ck("and the command can render it", "--render" in CLI and hasattr(PA, "render"))

print("\nthe documents a maintainer reads describe the code that is here")
# AGE IS NOT WRONGNESS - a document 180 commits old can be perfectly correct - so this checks
# for CONCRETE ABSENCES, each one found by asking what changed and which document should have
# said so. Four were missing at once: the domain chain ended at REPORT with no paper step; the
# reporting boundary described a two-way routing that had become three-way; and neither document
# a plugin author reads mentioned `unit_network`, the single declaration that earns a plugin
# twelve host-drawn panels.
_ARCH = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
_REP = (ROOT / "docs" / "REPORTING.md").read_text(encoding="utf-8")
ck("the domain chain includes the paper step", "PAPER" in _ARCH)
ck("the reporting boundary knows panels route three ways",
   "by_arm" in _REP or "arms page" in _REP)
for _f in ("docs/PLUGIN_DESIGN.md", "docs/MAINTAINING_PLUGINS.md"):
    _t = (ROOT / _f).read_text(encoding="utf-8")
    ck(f"{Path(_f).name} documents unit_network", "unit_network" in _t)
    ck(f"{Path(_f).name} documents what weight_scale decides", "weight_scale" in _t)

print("\nthe test loop is part of development, not a document beside it")
_DEV = (ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")
ck("the guideline carries the loop", "THE LOOP IS HOW THIS TOOL IS TESTED" in _DEV)
ck("and names its stations", all(w in _DEV for w in ("adopt", "drawing", "eye", "paper")))
ck("and the rule that makes it converge",
   "before fixing anything" in _DEV and "from the eye to a measurement" in _DEV)
ck("the driver it points at is committed", (ROOT / "tests" / "loop_stations.py").is_file())
ck("and the design document exists", (ROOT / "docs" / "TEST_LOOP.md").is_file())

print("\nnothing in the package writes outside a run directory")
# A MODULE THAT WRITES TO /tmp HAS INVENTED A THIRD PLACE. Every path this tool writes is
# derived from the run directory it was given.
bad = []
for f in sorted((ROOT / "scprofile").glob("*.py")):
    src = f.read_text(encoding="utf-8")
    for m in re.findall(r'["\'](/tmp/[^"\']*)["\']', src):
        bad.append(f"{f.name}: {m}")
ck("no module hard-codes a temp path", not bad, "; ".join(bad[:4]))

print("\n" + ("one home, and the documents match the code" if not FAIL
              else f"{len(FAIL)} FAILED: {FAIL}"))
print("\na citation into the source is an anchor somebody can find")
# A LINE NUMBER IS NOT AN ANCHOR. The figures skill cited `velocity.py:1624` for a comment about
# plotting imports and `velocity.py:1359` for a UMAP computation; both line numbers still resolved,
# because the file is long enough, and both pointed at unrelated code. Existence proves nothing
# here - the failure is drift, and only a quoted phrase can be checked.
#
# So a citation names a file and a string to search for, and this asserts the string is there.
import re as _re_cite                                                           # noqa: E402
_cites = []
for _doc in sorted((ROOT / ".claude" / "skills").rglob("*.md")) + sorted((ROOT / "docs").glob("*.md")):
    for _m in _re_cite.finditer(r"\(`([\w/]+\.(?:py|R))`, search `([^`]+)`\)", _doc.read_text(encoding="utf-8")):
        _f, _needle = ROOT / _m.group(1), _m.group(2)
        if not _f.is_file():
            _cites.append(f"{_doc.name}: no such file {_m.group(1)}")
        elif _needle not in _f.read_text(encoding="utf-8"):
            _cites.append(f"{_doc.name}: {_m.group(1)} does not contain {_needle!r}")
ck("every searchable citation finds its text", not _cites, str(_cites[:4]))


sys.exit(1 if FAIL else 0)
