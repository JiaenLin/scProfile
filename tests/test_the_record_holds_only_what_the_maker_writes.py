"""A design record holds only what the maker writes, and an older record is rewritten through it.

FOUND BY W047 (a reader's pass for one cohort's values, run 2). de's two W013 answers each kept a
copy of the declaration they left (`after_declaration`), and with it one cohort's description
that de.py itself no longer carried once its prose was answered. No verb could drop the copies:
a record changes form only when a verb writes it. And the record check read a copy only where a
declaration edit had followed an older last answer - which de's record never had - so a copy
re-worded, dropped, or replaced by a declaration nobody declared that carried a planted count
all passed the check (ATTACKS 13), as would any key nothing reads. The check also honoured
`git replace` (ATTACKS 22, found by W035's last re-check): a local ref under the anchor and
every `made_on` let a code line no answer admits pass. And the anchor could be an abbreviation.

WHAT THIS HOLDS, each through the real CLI on a clone of this repository carrying this tree's
code, and each failing on the head before it (`4d5e90f`):
  1. a record carrying a copy of a declaration is refused, naming the key and the verb;
  2. `scprofile design de --rewrite-record` writes it without: the plugin untouched, each dropped
     copy shown to be the declaration of the file its answer made, as rebuilt from git and the
     record, byte for byte; the stage and `check` green after; a second run writes nothing; no
     copy and no word of the cohort description left in the record;
  3. a copy, or any key the maker never writes - in an answer, a statement or the record - is
     refused by name, whatever it carries;
  4. the same verb on cellchat's record, already in the form, writes nothing;
  5. replace refs under the anchor and the made-on answer, with a code line smuggled into the
     plugin and every digest re-made, are refused: the check reads the objects the ids name;
  6. an anchor DEVPOINTS names by an abbreviation is refused.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# EVERY `git` HERE IS ASKED ABOUT THE REPOSITORY IT NAMES: the commit gate runs this suite under
# git's pre-commit hook, which exports GIT_INDEX_FILE=.git/index (relative).
GITENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

FAILS = []


def ck(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name
          + ("" if ok else f"\n         {str(detail)[:700]}"))
    if not ok:
        FAILS.append(name)


from scprofile import validate as V                                          # noqa: E402

#: The head before this rule, whose de.design.json an older maker wrote: two answers with a copy
#: of the declaration each, and answer 3 made on a committed file.
OLDER = "4d5e90fc55c1683b7924b6ee0cfc85b30b9a75d5"
#: The words of the one cohort description the copies carried, by their shape only: a sample
#: count with its unit, and a cell count in thousands - no cohort's value is written here.
COHORT_SHAPES = re.compile(r"\b\d+-sample\b|~\d+k cells")

td = Path(tempfile.mkdtemp(prefix="w047-record-"))
clone = td / "clone"
try:
    subprocess.run(["git", "clone", "-q", "--no-local", str(ROOT), str(clone)], check=True,
                   capture_output=True, env=GITENV)
    for d in ("scprofile", "kernels", "setup"):
        shutil.copytree(ROOT / d, clone / d, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(ROOT / "DEVPOINTS.yaml", clone / "DEVPOINTS.yaml")
    ENV = dict(GITENV, PYTHONPATH=str(clone))
    DE, REC = clone / "kernels" / "de.py", clone / "kernels" / "de.design.json"
    SHIPPED, CURRENT = DE.read_bytes(), REC.read_text(encoding="utf-8")

    def cli(*args):
        r = subprocess.run([sys.executable, "-m", "scprofile.cli", *args], cwd=str(clone),
                           env=ENV, capture_output=True, text=True, timeout=600)
        return r.returncode, r.stdout + r.stderr

    def git(*args, inp=None, env=None):
        return subprocess.run(["git", "-C", str(clone), "-c", "user.name=t", "-c",
                               "user.email=t@t", *args], input=inp, capture_output=True,
                              check=True, env=env or GITENV).stdout.decode("utf-8").strip()

    def show(commit):
        """`git show <commit>:kernels/de.py` in the clone, as git gives it - replace refs and all,
        and not stripped: a digest is of the file to its last byte."""
        return subprocess.run(["git", "-C", str(clone), "show", f"{commit}:kernels/de.py"],
                              capture_output=True, check=True, env=GITENV).stdout.decode("utf-8")

    def record_row(out):
        line = next((x for x in out.splitlines()
                     if "every shipped plugin's declaration loads, and its design record "
                        "accounts" in x), "")
        return line.strip()

    g = subprocess.run(["git", "-C", str(ROOT), "show", f"{OLDER}:kernels/de.design.json"],
                       capture_output=True, text=True, env=GITENV)
    ck("(the record an older maker wrote can be read from git)", g.returncode == 0,
       g.stderr[-300:])
    old_text = g.stdout
    old = json.loads(old_text) if g.returncode == 0 else {"answers": []}
    copies = {a["n"]: a["after_declaration"] for a in old["answers"] if "after_declaration" in a}
    ck("(it keeps a copy of the declaration in each of its two older answers)",
       sorted(copies) == [1, 2] and all(COHORT_SHAPES.search(c) for c in copies.values()),
       sorted(copies))

    print("1. a record that keeps a copy of a declaration is refused, naming the key")
    REC.write_text(old_text, encoding="utf-8")
    rc, out = cli("design", "de")
    ck("`scprofile design de` owes, naming `after_declaration` and the verb that drops it",
       rc == 1 and "after_declaration" in out and "--rewrite-record" in out, out[-500:])

    print("\n2. `--rewrite-record` writes it without, and proves what it dropped")
    rc, out = cli("design", "de", "--rewrite-record")
    ck("exit 0", rc == 0, out[-600:])
    ck("each dropped copy is the declaration of the file its answer made, rebuilt from git and "
       "the record, byte for byte",
       all(f"answer {n}: its copy of the declaration dropped - the file it made, rebuilt from "
           f"git and the record, carries that declaration byte for byte" in out
           for n in (1, 2)), out[-800:])
    new = json.loads(REC.read_text(encoding="utf-8"))
    ck("the record keeps no copy, and no word of the cohort description",
       "after_declaration" not in REC.read_text(encoding="utf-8")
       and not COHORT_SHAPES.search(REC.read_text(encoding="utf-8")))
    ck("and every digest, diff and reason it held, unchanged",
       [{k: v for k, v in a.items() if k != "after_declaration"} for a in old["answers"]]
       == new["answers"] and old["statements"] == new["statements"])
    ck("de.py is not touched", DE.read_bytes() == SHIPPED)
    # INDEPENDENTLY OF THE VERB'S OWN WORDS: answer 2 made the file committed at 9cbe9c6, and
    # that file's declaration is the copy answer 2 kept.
    a2 = V._git_show(clone, "9cbe9c62dfbad797d66d8645136e1ae9269e2f32", "kernels/de.py")[0]
    ck("(git's own file for answer 2 carries the copy it kept, and has its recorded digest)",
       a2 is not None and V._sha(a2) == old["answers"][1]["after"]
       and V._declaration_text(a2) == copies.get(2))
    rc, out = cli("design", "de")
    rc2, out2 = cli("check")
    ck("the design stage exits 0 and check's design-record row is green", rc == 0
       and record_row(out2).startswith("GREEN"), (out[-300:], record_row(out2)))
    before = REC.read_bytes()
    rc, out = cli("design", "de", "--rewrite-record")
    ck("a second run writes nothing", rc == 0 and "nothing written" in out
       and REC.read_bytes() == before, out[-300:])

    print("\n3. a copy, or any key the maker never writes, is refused by name")
    planted = 'PLUGIN = {"api": 1, "note": "planted: 3 of 7 units, a synthetic count"}\n'
    for where, edit in (
            ("a copy nobody declared, in answer 1",
             lambda r: r["answers"][0].__setitem__("after_declaration", planted)),
            ("a copy, in the made-on answer",
             lambda r: r["answers"][-1].__setitem__("after_declaration", planted)),
            ("a key of its own, in an answer",
             lambda r: r["answers"][1].__setitem__("note", "measured on one run: 3 of 7, synthetic")),
            ("a key of its own, in a statement",
             lambda r: next(iter(r["statements"].values())).__setitem__("note", "3 of 7, synthetic")),
            ("a key of its own, in the record",
             lambda r: r.__setitem__("note", "3 of 7, synthetic"))):
        r = json.loads(before)
        edit(r)
        REC.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        rc, out = cli("design", "de")
        rc2, out2 = cli("check")
        ck(f"{where}: the stage owes and check is red, naming the key",
           rc == 1 and "never writes" in out and record_row(out2).startswith("RED")
           and "never writes" in record_row(out2), (out[-300:], record_row(out2)))
    REC.write_bytes(before)

    print("\n4. the same route on cellchat's record, already in the form")
    cc = (clone / "kernels" / "cellchat.design.json").read_bytes()
    rc, out = cli("design", "cellchat", "--rewrite-record")
    ck("writes nothing, and says so", rc == 0 and "nothing written" in out
       and (clone / "kernels" / "cellchat.design.json").read_bytes() == cc, out[-300:])

    print("\n5. replace refs under the anchor and the made-on answer (ATTACKS 22)")
    X = "\n_W047_SMUGGLED = 1  # a code line no answer admits\n"
    anchor = V._spent_commit(clone, "de")
    rec = json.loads(before)
    made_on = [a["made_on"] for a in rec["answers"] if a.get("made_on")]
    idx = str(td / "index")
    for c in [anchor] + made_on:
        blob = git("hash-object", "-w", "--stdin",
                   inp=(show(c) + X).encode("utf-8"))
        env = dict(GITENV, GIT_INDEX_FILE=idx)
        git("read-tree", c, env=env)
        git("update-index", "--cacheinfo", f"100644,{blob},kernels/de.py", env=env)
        git("replace", "-f", c, git("commit-tree", git("write-tree", env=env), "-m", "forged",
                                    env=env))
    shipped = SHIPPED.decode("utf-8") + X
    follows = shipped
    for a in reversed(rec["answers"]):
        if a.get("made_on"):
            prev = show(a["made_on"])                                    # through the refs
            made = V._apply_unified(prev, a["diff"],
                                    written=V._written(follows, prev, a["version"]))
        else:
            made = follows
            prev = V._apply_unified(made, V._reverse_diff(a["diff"]))
        a["before"], a["after"] = V._sha(prev), V._sha(made)
        follows = prev
    DE.write_text(shipped, encoding="utf-8")
    REC.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ck("(through the replace refs, the forged files carry the line)",
       all(show(c).endswith(X) for c in [anchor] + made_on))
    rc, out = cli("design", "de")
    ck("the plugin carrying the smuggled line is refused: the check reads the object its id "
       "names, not the replacement", rc == 1 and "the file at its commit is not the file it "
       "records it was made on" in out and "_W047_SMUGGLED" in DE.read_text(encoding="utf-8"),
       out[-400:])
    for c in [anchor] + made_on:
        git("replace", "-d", c)
    rc, out = cli("design", "de")
    ck("(and with the refs deleted, the same files are refused as well)", rc == 1, out[-300:])
    DE.write_bytes(SHIPPED)
    REC.write_bytes(before)

    print("\n6. the anchor is a commit id, all its digits")
    dp = (clone / "DEVPOINTS.yaml").read_text(encoding="utf-8")
    ck("(DEVPOINTS names de's anchor by its whole hash)", f"de: {anchor}" in dp)
    (clone / "DEVPOINTS.yaml").write_text(dp.replace(f"de: {anchor}", f"de: {anchor[:7]}", 1),
                                          encoding="utf-8")
    rc, out = cli("design", "de")
    ck("an abbreviated anchor is refused, by name", rc == 1 and "not a commit id" in out,
       out[-300:])
    (clone / "DEVPOINTS.yaml").write_text(dp, encoding="utf-8")
    rc, out = cli("design", "de")
    ck("(and the whole hash passes again)", rc == 0, out[-300:])
finally:
    shutil.rmtree(td, ignore_errors=True)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    raise SystemExit(1)
print("a design record holds only what the maker writes, and an older one is rewritten through it")
