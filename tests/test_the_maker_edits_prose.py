"""The maker edits a plugin's PROSE, records it, and refuses an edit that changes code.

FOUND BY THE LEAK GUARD (harness autodev W032, GAP-C79 and GAP-C80). A cohort's measured value
sat in a comment of cellchat's R script, and no verb of the maker could change it: `sch dev edit`
edits the declaration by span, `scprofile design --answer` edits the sites the design worksheet
names, and a comment is neither. The only way left was a hand edit, which the round's first rule
forbids - so by the rule of 2026-09-14 ("anything in a plugin that cannot be edited easily from
the maker is a suite or maker design defect") the defect was the maker's.

WHAT THIS HOLDS, each failing before `scprofile prose` existed:
  1. the verb exists on the real CLI;
  2. what is PROSE: a Python comment (inside the declaration too), a docstring, and a comment of an
     embedded R script; and what is CODE, refused with its line: Python's tokens, any other
     string, R's code and strings, a splice marker, the file's header lines;
  3. an edit is recorded like any other answer outside the declaration - in the plugin's maker
     record, its diff and digests and reason, the maker's version bump - and the record check
     and the replay admit it again by the same rule, so a record doctored to carry code fails;
  4. a plugin with no anchor - every held-out one - is refused, and so is an edit with no reason;
  5. on the shipped repository the verb runs through the CLI: a dry run of an R-comment edit of
     cellchat writes nothing, an edit of its R code and any edit of a held-out plugin are refused,
     and the shipped cellchat meets its record (`scprofile design cellchat` exits 0).
"""
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# EVERY `git` HERE IS ASKED ABOUT THE REPOSITORY IT NAMES (see test_the_maker_demands_the_design).
GITENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

FAILS = []


def ck(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"\n         {detail}"))
    if not ok:
        FAILS.append(name)


def cli(*args, cwd=ROOT):
    return subprocess.run([sys.executable, "-m", "scprofile.cli", *args], capture_output=True,
                          text=True, cwd=str(cwd), timeout=300)


print("1. the verb exists")
r = cli("prose", "--help")
ck("`scprofile prose` is a command of the real CLI", r.returncode == 0,
   (r.stdout + r.stderr)[-400:])
from scprofile import validate as V                                          # noqa: E402
HAVE = all(hasattr(V, f) for f in ("prose_refusals", "prose_answer", "after_edit_followers"))
ck("validate.prose_refusals, prose_answer and after_edit_followers exist", HAVE)
if not HAVE:
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1)

# A plugin as the format writes one: a declaration with a comment in it, docstrings, Python code,
# and an R script long enough for the suite's own rule to read as R (tests/subject.py).
R = ('\nlibrary(stats)\n'
     '# THE FIRST COMMENT, measured as 30.56 on somebody\'s cohort\n'
     'f <- function(a) {\n'
     '  b <- "#not a comment"   # a trailing comment\n'
     '  `odd # name` <- 2\n'
     '  a + 1\n'
     '}\n'
     '# __CAP__ is spliced below\n'
     + "# padding so the script is long enough to be read as one, as the suite reads it\n" * 3)
PLUG = ('"""The module\'s docstring."""\n'
        'PLUGIN = {\n'
        '    "api": 1,\n'
        '    # a comment inside the declaration, PBS 123456\n'
        '    "version": "0.1.0",\n'
        '}\n'
        '\n'
        f'_R_RUN = r"""{R}""".replace("__CAP__", "")\n'
        '\n'
        '\n'
        'def run(ctx):\n'
        '    """The function\'s docstring."""\n'
        '    x = "a plain string"  # a comment on code\n'
        '    return x\n')


def edit(old, new, text=PLUG):
    assert text.count(old) == 1, old
    return text.replace(old, new)


print("\n2. what is prose, and what is code")
prose = {
    "a comment on Python code": ("# a comment on code", "# a comment, reworded"),
    "a comment inside the declaration": ("PBS 123456", "a job"),
    "the module's docstring": ("The module's docstring.", "Reworded."),
    "a function's docstring": ("The function's docstring.", "Reworded, longer\n    and two lines."),
    "a whole-line R comment": ("measured as 30.56 on somebody's cohort", "measured on a cohort"),
    "a trailing R comment": ("# a trailing comment", "# reworded"),
    "an R comment line added": ("f <- function(a) {\n", "f <- function(a) {\n  # a new line\n"),
}
for what, (old, new) in prose.items():
    got = V.prose_refusals(PLUG, edit(old, new))
    ck(f"prose: {what}", got == [], got)
code = {
    "Python code": ("return x", "return x + ''"),
    "a plain string": ('"a plain string"', '"another string"'),
    "a string's quotes": ('"a plain string"', "'a plain string'"),
    "R code": ("a + 1", "a + 2"),
    "an R string holding a hash": ('"#not a comment"', '"#changed"'),
    "an R name holding a hash": ("`odd # name`", "`odd # other`"),
    "a splice marker in an R comment": ("# __CAP__ is spliced", "# __CUP__ is spliced"),
    "the declaration's value": ('"api": 1', '"api": 2'),
    "a header line (an encoding cookie)": ('"""The module', '# -*- coding: latin-1 -*-\n"""The module'),
}
for what, (old, new) in code.items():
    got = V.prose_refusals(PLUG, edit(old, new))
    ck(f"refused: {what}", bool(got) and all("line " in g for g in got), got)
got = V.prose_refusals(PLUG, edit("return x", "return x +"))
ck("refused: an edit that leaves a file that does not parse", bool(got), got)


class Stub:
    def __init__(self, path, name):
        self.path, self.name = Path(path), name


def repo(td, name, text, anchor=True):
    """`<td>/kernels/<name>.py` committed; DEVPOINTS names the commit as the plugin's anchor, as
    cellchat's is named (`rules.end_to_end.anchor`) - or names none."""
    (Path(td) / "kernels").mkdir()
    f = Path(td) / "kernels" / f"{name}.py"
    f.write_text(text, encoding="utf-8")
    g = ["git", "-C", str(td), "-c", "user.name=t", "-c", "user.email=t@t",
         "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", str(td)], check=True, capture_output=True, env=GITENV)
    subprocess.run(g + ["add", "-A"], check=True, capture_output=True, env=GITENV)
    subprocess.run(g + ["commit", "-q", "-m", "base"], check=True, capture_output=True, env=GITENV)
    sha = subprocess.run(["git", "-C", str(td), "rev-parse", "HEAD"], check=True,
                         capture_output=True, text=True, env=GITENV).stdout.strip()
    (Path(td) / "DEVPOINTS.yaml").write_text(
        "rules:\n  end_to_end:\n    names: [%s]\n" % name
        + (f"    anchor:\n      {name}: {sha}\n" if anchor else ""), encoding="utf-8")
    return Stub(f, name)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


print("\n3. an edit is recorded, and the record admits it again")
with tempfile.TemporaryDirectory() as td:
    k = repo(td, "demo", PLUG)
    quiet = []
    rc = V.prose_answer(k, [("measured as 30.56 on somebody's cohort", "measured on a cohort")],
                        "", root=td, log=quiet.append)
    ck("refused: an edit with no reason", rc == 1 and k.path.read_text() == PLUG, quiet)
    rc = V.prose_answer(k, [("a comment", "x")], "why", root=td, log=quiet.append)
    ck("refused: OLD that does not occur exactly once", rc == 1 and k.path.read_text() == PLUG,
       quiet[-1:])
    rc = V.prose_answer(k, [("a + 1", "a + 2")], "why", root=td, log=quiet.append)
    ck("refused through the verb: R code, and nothing is written",
       rc == 1 and k.path.read_text() == PLUG, quiet[-2:])
    log = []
    rc = V.prose_answer(k, [("measured as 30.56 on somebody's cohort", "measured on a cohort"),
                            ("PBS 123456", "a job")], "a cohort's value and a job id out",
                        root=td, log=log.append)
    after1 = k.path.read_text()
    ck("an R comment and a declaration comment, in one call", rc == 0
       and "30.56" not in after1 and "PBS 123456" not in after1, log)
    ck("the version is the maker's minor bump", '"version": "0.2.0"' in after1, after1[:200])
    rec = V._read_record(k)
    a = (rec.get("answers") or [{}])[-1]
    ck("recorded in the plugin's maker record, as prose, with its reason and digests",
       a.get("kind") == "prose" and a.get("why") == "a cohort's value and a job id out"
       and a.get("before") == V._sha(PLUG) and a.get("after") == V._sha(after1)
       and "30.56" in a.get("diff", ""), a)
    rc = V.prose_answer(k, [("# a comment on code", "# reworded")], "a second", root=td,
                        log=log.append)
    ok, said = V.design_record_check(k, root=td)
    ck("two answers: the record check walks both back to the anchor", rc == 0 and ok, said)
    shipped = k.path.read_text()
    copy = Path(td) / "base.py"
    copy.write_text(PLUG, encoding="utf-8")
    rc = V.design_replay(k, copy, log=quiet.append)
    ck("the replay rebuilds the shipped file from the base", rc == 0
       and copy.read_text() == shipped, quiet[-2:])
    # A RECORD IS A FILE ANYONE CAN EDIT: one doctored to carry code is refused by the same rule.
    import json
    raw = json.loads(V.design_record_path(k).read_text())
    k.path.write_text(shipped.replace("    return x\n", "    return x  # by hand\n"))
    ok, said = V.design_record_check(k, root=td)
    ck("an edit the record does not hold - even a comment - fails the record check", not ok, said)
    k.path.write_text(shipped)
    d = raw["answers"][-1]["diff"]
    raw["answers"][-1]["diff"] = d.replace("+    x = \"a plain string\"  # reworded",
                                           "+    x = \"another\"  # reworded")
    V.design_record_path(k).write_text(json.dumps(raw))
    k.path.write_text(shipped.replace('x = "a plain string"', 'x = "another"'))
    raw["answers"][-1]["after"] = V._sha(k.path.read_text())
    V.design_record_path(k).write_text(json.dumps(raw))
    ok, said = V.design_record_check(k, root=td)
    ck("a record doctored to carry a code change is refused", not ok and "prose" in said, said)

print("\n4. a plugin with no anchor is refused - every held-out one")
with tempfile.TemporaryDirectory() as td:
    k = repo(td, "held", PLUG, anchor=False)
    log = []
    rc = V.prose_answer(k, [("# a comment on code", "# x")], "why", root=td, log=log.append)
    ck("refused, and nothing is written", rc == 1 and k.path.read_text() == PLUG, log)
    ck("the refusal names the anchor", any("anchor" in x for x in log), log)

print("\n5. on the shipped repository, through the CLI")
fol = V.after_edit_followers(ROOT)
ck("the followers are the tool's declared `plan.after_edit`, in order",
   bool(fol) and fol[0][-2:] == ["validate", "{name}"]
   and any("test_portability.py" in " ".join(c) for c in fol), fol[:2])
cc = ROOT / "kernels" / "cellchat.py"
src = cc.read_text(encoding="utf-8")
spans = []
for t in tokenize.generate_tokens(io.StringIO(src).readline):
    if t.type == tokenize.STRING and "library(" in t.string and t.end[0] - t.start[0] > 20:
        spans.append((t.start[0], t.end[0]))
lines = src.split("\n")
inside = [i + 1 for a, b in spans for i in range(a, b - 1)]
r_comment = next((lines[i - 1].strip() for i in inside if lines[i - 1].strip().startswith("# ")
                  and len(lines[i - 1].strip()) > 30 and src.count(lines[i - 1].strip()) == 1),
                 None)
r_code = next((lines[i - 1].strip() for i in inside if "<-" in lines[i - 1]
               and not lines[i - 1].strip().startswith("#") and "#" not in lines[i - 1]
               and len(lines[i - 1].strip()) > 20 and src.count(lines[i - 1].strip()) == 1), None)
ck("cellchat carries an R script with a comment line and a code line to try", bool(r_comment)
   and bool(r_code), (spans, r_comment, r_code))
if r_comment and r_code:
    before = sha(cc)
    r = cli("prose", "cellchat", "--replace", r_comment, "# reworded by the test", "--why",
            "a dry run", "--dry")
    ck("a dry run of an R-comment edit of cellchat exits 0, shows the diff, writes nothing",
       r.returncode == 0 and "# reworded by the test" in r.stdout and sha(cc) == before,
       (r.stdout + r.stderr)[-600:])
    r = cli("prose", "cellchat", "--replace", r_code, r_code + " + 0", "--why", "code", "--dry")
    ck("an edit of cellchat's R code is refused, naming the line", r.returncode == 1
       and "line " in (r.stdout + r.stderr) and sha(cc) == before, (r.stdout + r.stderr)[-600:])
for held in ("abundance", "velocity"):
    hp = ROOT / "kernels" / f"{held}.py"
    if hp.is_file():
        before = sha(hp)
        r = cli("prose", held, "--replace", "#", "#", "--why", "any", "--dry")
        ck(f"held-out {held}: refused before anything is read, and untouched",
           r.returncode == 1 and "anchor" in (r.stdout + r.stderr) and sha(hp) == before,
           (r.stdout + r.stderr)[-400:])
r = cli("design", "cellchat")
ck("the shipped cellchat meets its record (`scprofile design cellchat` exits 0)",
   r.returncode == 0, (r.stdout + r.stderr)[-600:])

print(f"\n{len(FAILS)} failure(s)" + (": " + "; ".join(FAILS) if FAILS else ""))
sys.exit(1 if FAILS else 0)
