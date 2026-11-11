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

W035's FIX ROUND 1 (the verifier's findings), each failing on 849698a, through the real CLI on a
local clone of this repository:
  6. a verb writes what it admits: `--as-version` is N.N.N or refused, for `prose` and for
     `design --answer`, and nothing is written; a design answer is made on a committed file too;
  7. a record keeps no text an edit took out and no copy of the declaration, and a declaration
     edit between two answers - `sch dev edit`'s - keeps the chain the record check walks;
  8. a sentence saying what was measured on a sample, with a number, is refused by `validate` on
     a plugin the maker owns (`sample_values`), and the shipped cellchat states none.
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
     '# THE FIRST COMMENT, measured as 12.34 on somebody\'s cohort\n'
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
        '    # a comment inside the declaration, a job 123456\n'
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
    "a comment inside the declaration": ("a job 123456", "a job"),
    "the module's docstring": ("The module's docstring.", "Reworded."),
    "a function's docstring": ("The function's docstring.", "Reworded, longer\n    and two lines."),
    "a whole-line R comment": ("measured as 12.34 on somebody's cohort", "measured on a cohort"),
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
    rc = V.prose_answer(k, [("measured as 12.34 on somebody's cohort", "measured on a cohort")],
                        "", root=td, log=quiet.append)
    ck("refused: an edit with no reason", rc == 1 and k.path.read_text() == PLUG, quiet)
    rc = V.prose_answer(k, [("a comment", "x")], "why", root=td, log=quiet.append)
    ck("refused: OLD that does not occur exactly once", rc == 1 and k.path.read_text() == PLUG,
       quiet[-1:])
    rc = V.prose_answer(k, [("a + 1", "a + 2")], "why", root=td, log=quiet.append)
    ck("refused through the verb: R code, and nothing is written",
       rc == 1 and k.path.read_text() == PLUG, quiet[-2:])
    log = []
    rc = V.prose_answer(k, [("measured as 12.34 on somebody's cohort", "measured on a cohort"),
                            ("a job 123456", "a job")], "a cohort's value and a job id out",
                        root=td, log=log.append)
    after1 = k.path.read_text()
    ck("an R comment and a declaration comment, in one call", rc == 0
       and "12.34" not in after1 and "a job 123456" not in after1, log)
    rtext = V.design_record_path(k).read_text()
    ck("the record carries no text the edit removed (a removed leak does not move into it)",
       "12.34" not in rtext and "123456" not in rtext, rtext[:300])
    ck("the version is the maker's minor bump", '"version": "0.2.0"' in after1, after1[:200])
    rec = V._read_record(k)
    a = (rec.get("answers") or [{}])[-1]
    ck("recorded in the plugin's maker record, as prose, with its reason and digests",
       a.get("kind") == "prose" and a.get("why") == "a cohort's value and a job id out"
       and a.get("before") == V._sha(PLUG) and a.get("after") == V._sha(after1)
       and "+# THE FIRST COMMENT, measured on a cohort" in a.get("diff", "")
       and len(a.get("made_on") or "") == 40, a)
    rc = V.prose_answer(k, [("# a comment on code", "# reworded")], "a second", root=td,
                        log=log.append)
    ck("refused: an answer on a file that differs from its commit", rc == 1, log[-1:])
    g = ["git", "-C", str(td), "-c", "user.name=t", "-c", "user.email=t@t",
         "-c", "commit.gpgsign=false"]
    subprocess.run(g + ["add", "-A"], check=True, capture_output=True, env=GITENV)
    subprocess.run(g + ["commit", "-q", "-m", "answer 1"], check=True, capture_output=True,
                   env=GITENV)
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


# W035's FIX ROUND 1: THE VERIFIER'S THREE FINDINGS, each through the real CLI on a local clone of
# this repository (its history included: the anchor, and the commits a record names), so the
# shipped files stay as they are.
G = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
     "-c", "core.hooksPath=/dev/null"]


def clone_here(td):
    """A clone of this repository at its HEAD, with this tree's code copied over the clone's, so
    the code under test is the code here."""
    import shutil
    dst = Path(td) / "repo"
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                          text=True, env=GITENV).stdout.strip()
    r = subprocess.run(["git", "clone", "-q", "--no-checkout", str(ROOT), str(dst)],
                       capture_output=True, text=True, env=GITENV)
    if r.returncode or not head:
        return None
    subprocess.run(["git", "-C", str(dst), "checkout", "-q", head], capture_output=True,
                   env=GITENV)
    for p in (ROOT / "scprofile").glob("*.py"):
        shutil.copyfile(p, dst / "scprofile" / p.name)
    return dst


def kernels_changed(dst):
    return subprocess.run(["git", "-C", str(dst), "status", "--porcelain", "--", "kernels"],
                          capture_output=True, text=True, env=GITENV).stdout.strip()


def commit_all(dst, msg):
    subprocess.run(["git", "-C", str(dst), *G, "add", "-A", "kernels"], capture_output=True,
                   env=GITENV)
    subprocess.run(["git", "-C", str(dst), *G, "commit", "-q", "-m", msg], capture_output=True,
                   env=GITENV)


def said(r):
    return (r.stdout + r.stderr)[-500:]


print("\n6. a verb writes what it admits: a version is a version (fix round 1, the verifier's A8)")
# `--as-version '0.43.1", "status": "planned'` exited 0, wrote a new key into cellchat's
# declaration and turned it from built to planned: the prose rule had been asked of the file
# before the version was spliced in, and `design --answer` spliced the same way.
SPLICE = '9.9.9", "status": "planned'
with tempfile.TemporaryDirectory() as td:
    dst = clone_here(td)
    ck("(a local clone of this repository, for the real CLI)", dst is not None)
    if dst is not None:
        csrc = (dst / "kernels" / "cellchat.py").read_text(encoding="utf-8")
        j = csrc.index('"""')
        old, new = csrc[j:j + 12], csrc[j:j + 12] + " (reworded)"
        r = cli("prose", "cellchat", "--replace", old, new, "--why", "t", "--as-version", SPLICE,
                "--no-follow", cwd=dst)
        ck("prose: a version spliced with a key is refused, and nothing is written",
           r.returncode == 1 and not kernels_changed(dst) and "version" in said(r), said(r))
        r = cli("prose", "cellchat", "--replace", old, new, "--why", "t", "--as-version",
                "banana", "--no-follow", cwd=dst)
        ck("prose: a version that is not N.N.N is refused, and nothing is written",
           r.returncode == 1 and not kernels_changed(dst), said(r))
        r = cli("prose", "cellchat", "--replace", old, new, "--why", "t", "--as-version", "9.9.9",
                "--dry", cwd=dst)
        ck("prose: a version of that form is admitted (a dry run writes nothing)",
           r.returncode == 0 and '+    "version": "9.9.9",' in r.stdout
           and not kernels_changed(dst), said(r))
        # design --answer: one of de's statements answered, with the same splice
        import re
        desrc = (dst / "kernels" / "de.py").read_text(encoding="utf-8")
        dl = desrc.split("\n")
        prop = None
        for x in V._scan(desrc)[1]:
            for ln in range(x["line"], x["span"][1] + 1):
                m = re.search(r'"([A-Za-z][^"\\]{8,})"', dl[ln - 1])
                if not m:
                    continue
                cand = list(dl)
                cand[ln - 1] = dl[ln - 1][:m.start(1)] + "Note: " + dl[ln - 1][m.start(1):]
                _o, sites, refused, _n = V._admit(desrc, "\n".join(cand))
                if sites and not refused:
                    prop = "\n".join(cand)
                    break
            if prop:
                break
        ck("(de has a statement an answer can change)", prop is not None)
        if prop is not None:
            pf = Path(td) / "answer.py"
            pf.write_text(prop, encoding="utf-8")
            r = cli("design", "de", "--answer", str(pf), "--why", "t", "--as-version", SPLICE,
                    cwd=dst)
            ck("design --answer: a version spliced with a key is refused, and nothing is written",
               r.returncode == 1 and not kernels_changed(dst), said(r))
            r = cli("design", "de", "--answer", str(pf), "--why", "a word added", cwd=dst)
            drec = (dst / "kernels" / "de.design.json").read_text(encoding="utf-8")
            import json
            last = (json.loads(drec).get("answers") or [{}])[-1]
            ck("design --answer: an answer is made on a committed file and recorded by the lines "
               "it wrote, with no copy of the declaration", r.returncode == 0
               and len(last.get("made_on") or "") == 40 and "after_declaration" not in last
               and V.REDACTED in last.get("diff", "") if hasattr(V, "REDACTED") else False,
               (said(r), sorted(last)))
            r = cli("design", "de", cwd=dst)
            ck("and de's record, two older answers and this one, meets the plugin "
               "(`scprofile design de` exits 0)", r.returncode == 0, said(r))

print("\n7. a record keeps no text an edit took out, and no copy of the declaration (fix round 1)")
# Each answer kept the whole declaration it left (`after_declaration`, ~125,000 characters for
# cellchat), so a comment taken out of the declaration by a second answer stayed in the first
# one's copy, and the record check said ok. And a declaration edit between two answers - the
# maker's own verb, `sch dev edit` - broke the chain the check walks.
with tempfile.TemporaryDirectory() as td:
    dst = clone_here(td)
    if dst is not None:
        cc = dst / "kernels" / "cellchat.py"
        src = cc.read_text(encoding="utf-8")
        a_, b_ = V._declaration(src)
        coms = [t.string for t in tokenize.generate_tokens(io.StringIO(src).readline)
                if t.type == tokenize.COMMENT and a_ <= t.start[0] <= b_ and len(t.string) > 40
                and src.count(t.string) == 1]
        ck("(cellchat's declaration carries comments to take out)", len(coms) >= 2, len(coms))
        if len(coms) >= 2:
            r = cli("prose", "cellchat", "--replace", coms[0], "# reworded by the test", "--why",
                    "a declaration comment out", "--no-follow", cwd=dst)
            rec = (dst / "kernels" / "cellchat.design.json").read_text(encoding="utf-8")
            ck("a prose answer takes a comment out of the declaration", r.returncode == 0, said(r))
            ck("the record keeps no copy of the comment it took out",
               coms[0].lstrip("# ").strip() not in rec)
            ck("the record keeps no copy of the declaration", "after_declaration" not in rec)
            # A DECLARATION EDIT, as `sch dev edit` makes one: a value changed and the version
            # raised, committed - then a second prose answer.
            commit_all(dst, "answer")
            import ast as _ast
            src = cc.read_text(encoding="utf-8")
            node = V._version_node(src)
            decl = next(n for n in _ast.parse(src).body if isinstance(n, _ast.Assign)
                        and getattr(n.targets[0], "id", "") == "PLUGIN").value
            sv = next(v for k_, v in zip(decl.keys, decl.values)
                      if isinstance(k_, _ast.Constant) and k_.value == "summary")
            seg = _ast.get_source_segment(src, sv)
            src = src.replace(seg, '"a summary the test wrote"', 1)
            src = src.replace(f'"version": "{node[1]}"', '"version": "9.0.0"', 1)
            cc.write_text(src, encoding="utf-8")
            commit_all(dst, "a declaration edit")
            r = cli("design", "cellchat", cwd=dst)
            ck("a declaration edit after an answer meets the record", r.returncode == 0, said(r))
            r = cli("prose", "cellchat", "--replace", coms[1], "# reworded again", "--why",
                    "a second comment out", "--no-follow", cwd=dst)
            ck("a second prose answer, after the declaration edit", r.returncode == 0, said(r))
            r = cli("design", "cellchat", cwd=dst)
            ck("the chain holds across the declaration edit (`scprofile design cellchat` exits 0)",
               r.returncode == 0, said(r))
            rec = (dst / "kernels" / "cellchat.design.json").read_text(encoding="utf-8")
            ck("and the record keeps neither the declaration's old value nor either comment",
               _ast.literal_eval(seg) not in rec and coms[1].lstrip("# ").strip() not in rec
               and coms[0].lstrip("# ").strip() not in rec)

print("\n8. a value measured on a sample is the sample's: no plugin the maker owns states one "
      "(fix round 1)")
# cellchat's caveat quoted two shares measured on one sample of a real cohort - numbers no
# generated term list holds, since a list holds names and levels - and its record copied them.
HAVE8 = hasattr(V, "sample_values")
ck("validate.sample_values exists", HAVE8)
if HAVE8:
    for s, want in (("Measured on one sample of a real cohort, X fell from 41.0% to 12.5%.", True),
                    ("Observed across two donors: a 3.1x enrichment.", True),
                    ("measured on 3 samples, the median was 0.42.", True),
                    ("The 41.0% above is MEASURED from the shipped database.", False),
                    ("The size of that is measured on this run rather than quoted.", False)):
        in_string, in_comment = (bool(V.sample_values(f"x = {s!r}\n")),
                                 bool(V.sample_values(f"# {s}\n")))
        ck(f"{'found' if want else 'not found'}, in a string and in a comment: {s[:60]}",
           in_string == want and in_comment == want, (in_string, in_comment))
r = cli("validate", "cellchat")
ck("`scprofile validate cellchat` passes, naming no value measured on a sample",
   r.returncode == 0 and "measured on a sample" not in r.stdout, r.stdout[-600:])

print(f"\n{len(FAILS)} failure(s)" + (": " + "; ".join(FAILS) if FAILS else ""))
sys.exit(1 if FAILS else 0)
