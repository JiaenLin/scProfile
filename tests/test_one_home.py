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

print("\nthe counts the documents claim are the counts the code has")
SKILL = ROOT / ".claude" / "skills" / "plugin-figures" / "SKILL.md"
WORDS = {6: "six", 11: "eleven", 13: "thirteen", 15: "fifteen", 12: "twelve", 14: "fourteen"}
if SKILL.is_file():
    head = SKILL.read_text(encoding="utf-8").split("---")[1]
    ck("the skill's panel-kind count is right",
       WORDS.get(len(P.KINDS), "?") in head, f"{len(P.KINDS)} kinds")
    ck("the skill's rule count is right",
       f"{WORDS.get(len(P.RULES), '?')} rules" in head, f"{len(P.RULES)} rules")
    ck("every registered kind is named in the skill",
       all(k.id in head for k in P.KINDS),
       str([k.id for k in P.KINDS if k.id not in head]))
else:
    ck("the figures skill lives in this repository", False, str(SKILL))

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
sys.exit(1 if FAIL else 0)
