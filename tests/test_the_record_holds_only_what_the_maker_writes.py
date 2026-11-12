"""A design record holds only what the maker writes, each field in the form it writes it (a reason
only as text), and an older record is rewritten through the maker, with a trace the check reads.

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

AND, FOUND BY THE BATCH'S VERIFICATION (W047 fix round), each failing on `945549f`:
  7. `--rewrite-record` is refused, nothing written: over a copy that is not the declaration its
     answer made (the verifier's reproduction: it exited 0 and wrote a record identical to a
     clean one), with no `--why`, and over a hand-edited plugin; and no other verb drops a copy;
  8. what it writes carries a trace the check validates - the tool's version, the commit, the
     reason, each dropped copy's digest - so a trace forged in any field, or removed, fails;
  9. a value planted in any field the maker writes (`n`, a prose answer's `sites`, a statement
     no file of the chain has, `version`, `diff`, ...) is refused by name, not only a new key.
AND, FOUND BY THE BATCH'S LEAN RE-CHECK (W047 last fix), each failing on `95ed6bd`:
 10. the record is read as the file, not as a lenient parse of it: a repeated key (before an
     answer's `n`, the record's `plugin`, a statement's `how`, the trace's `commit`), a second
     document, trailing space, a byte-order mark, a NaN or Infinity literal, a byte that is not
     UTF-8, a character the writer escapes written raw, a merge-conflict marker - each is refused
     by name by `design`, by `check` and by every verb that writes (`--answer`, `prose`,
     `--confirm`, `--rewrite-record`, `--replay-into`), nothing written; and text in place of the
     version of the file de's first answer was made on is refused by name.
Held to their form and no further, and so the limits of these checks: a reason (`why`) is the
author's words, held only to being text - a value written into one passes, and is read as any
text of the repository is; a trace's `commit` can be any commit the repository holds whose
VERSION reads the stated version; and the digits of that one version literal, in de's record
only, pass.
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
    WHY = "a rewrite in a test of this suite"
    rc, out = cli("design", "de", "--rewrite-record", "--why", WHY)
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
    trace = new.get("rewrites") or [{}]
    ck("and the record says it was rewritten: one entry, the tool's version, the commit it ran "
       "on, the reason, each dropped copy's digest",
       len(new.get("rewrites") or []) == 1 and trace[0].get("commit") == git("rev-parse", "HEAD")
       and trace[0].get("why") == WHY and trace[0].get("version") == (
           ROOT / "VERSION").read_text(encoding="utf-8").strip()
       and trace[0].get("dropped") == {str(n): V._sha(c) for n, c in copies.items()},
       new.get("rewrites"))
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
    rc, out = cli("design", "de", "--rewrite-record", "--why", WHY)
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
    rc, out = cli("design", "cellchat", "--rewrite-record", "--why", WHY)
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

    print("\n7. `--rewrite-record` is refused, nothing written (the batch's verification, F1)")
    # THE VERIFIER'S REPRODUCTION: the record an older maker wrote, a value put into a copy. It
    # exited 0, said the copy was NOT the declaration, and wrote a record identical to a clean one.
    P = "planted: 3 of 7 units, a synthetic count"
    tampered = json.loads(old_text)
    tampered["answers"][0]["after_declaration"] += f"# {P}\n"
    REC.write_text(json.dumps(tampered, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    t0 = REC.read_bytes()
    rc, out = cli("design", "de", "--rewrite-record", "--why", WHY)
    ck("a copy that is not the declaration its answer made: refused, naming the answer, nothing "
       "written", rc == 1 and "answer 1's copy of the declaration is NOT the declaration" in out
       and "nothing written" in out and REC.read_bytes() == t0, out[-500:])
    REC.write_text(old_text, encoding="utf-8")
    rc, out = cli("design", "de", "--rewrite-record")
    ck("with no reason: refused, naming --why, nothing written", rc == 1 and "--why" in out
       and REC.read_text(encoding="utf-8") == old_text, out[-300:])
    # THE SAME FACT BY ANOTHER VERB (ATTACKS 21): a confirmation writes the record too, and every
    # copy went with whichever verb wrote next, with no trace. Only the rewrite drops one now.
    line = V._scan(SHIPPED.decode("utf-8"))[1][0]["line"]
    rc, out = cli("design", "de", "--confirm", str(line), "--why", "a confirmation in a test")
    kept = json.loads(REC.read_text(encoding="utf-8"))
    ck("a confirmation over the record an older maker wrote keeps both copies, for the check to "
       "refuse", {a["n"]: a.get("after_declaration") for a in kept["answers"]
                  if "after_declaration" in a} == copies, out[-300:])
    # THE CHECK IS THE VERB'S (the verifier's mutant "the rewrite skips its check" was green):
    # over a hand-edited plugin, a record already in the form is refused, not "already written".
    DE.write_bytes(SHIPPED + b"# a hand edit\n")
    for label, rec_text in (("a record already in the form", before.decode("utf-8")),
                            ("the record an older maker wrote", old_text)):
        REC.write_text(rec_text, encoding="utf-8")
        rc, out = cli("design", "de", "--rewrite-record", "--why", WHY)
        ck(f"over a hand-edited plugin, {label}: refused by its check, nothing written",
           rc == 1 and "does not pass its check" in out
           and REC.read_text(encoding="utf-8") == rec_text
           and DE.read_bytes() == SHIPPED + b"# a hand edit\n", out[-300:])
    DE.write_bytes(SHIPPED)
    REC.write_bytes(before)

    def planted(cases, rec_path, name, base_bytes):
        for where, edit, says in cases:
            r = json.loads(base_bytes)
            try:
                edit(r)
            except (KeyError, IndexError, TypeError, AttributeError) as e:
                ck(f"{where}: (planted)", False, f"the record has no such field here: {e!r}")
                continue
            rec_path.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            rc, out = cli("design", name)
            ck(f"{where}: refused by name", rc == 1 and says in out, out[-400:])
        rec_path.write_bytes(base_bytes)

    print("\n8. the trace is validated wherever the record is read: forged, or removed, it fails")
    head_c = git("rev-parse", "HEAD")

    def tr(r):
        return r["rewrites"][0]
    planted((
        ("the trace removed", lambda r: r.pop("rewrites"),
         "no rewrite in the record says it dropped it"),
        ("one dropped copy taken out of it", lambda r: tr(r)["dropped"].pop("2"),
         "answer 2 was recorded before W035's fix round 1"),
        ("a dropped copy's digest forged", lambda r: tr(r)["dropped"].__setitem__(
            "1", "0123456789abcdef"), "the trace is not of this record"),
        ("its `version` forged", lambda r: tr(r).__setitem__("version", "9.9.9"),
         "rewrite 1's `version`"),
        ("its `commit`, a whole id git does not hold", lambda r: tr(r).__setitem__(
            "commit", "1" * 40), "cannot be read"),
        ("its `commit` abbreviated", lambda r: tr(r).__setitem__("commit", head_c[:7]),
         "not a commit id"),
        ("its `why` emptied", lambda r: tr(r).__setitem__("why", " "),
         "rewrite 1's `why` is not a reason"),
        ("a made-on answer named as dropped", lambda r: tr(r)["dropped"].__setitem__(
            "3", "0123456789abcdef"), "which is no answer recorded before"),
        ("a key of its own", lambda r: tr(r).__setitem__("note", P), "never writes"),
        ("one of its keys removed", lambda r: tr(r).pop("version"), "lacks ['version']"),
        ("doubled", lambda r: r["rewrites"].append(dict(tr(r))), "more than one rewrite"),
    ), REC, "de", before)

    print("\n9. a value in a field the maker writes, in a form it never writes, is refused by name")
    sts = json.loads(before)["statements"]
    conf = next(d for d, s in sorted(sts.items()) if s["how"] == "confirmed")
    ans2 = next(d for d, s in sorted(sts.items()) if s["how"] == "answer 2")

    def in_diff(i, fn):
        return lambda r: r["answers"][i].__setitem__("diff", fn(r["answers"][i]["diff"]))
    planted((
        ("the record's `plugin`", lambda r: r.__setitem__("plugin", f"de, {P}"), "`plugin`"),
        ("an older answer's `n`", lambda r: r["answers"][0].__setitem__("n", f"1, {P}"), "`n`"),
        ("the made-on answer's `n`, a number", lambda r: r["answers"][2].__setitem__("n", 37),
         "`n`"),
        ("a design answer's `kind`", lambda r: r["answers"][1].__setitem__("kind", P), "`kind`"),
        ("an answer's `why` emptied", lambda r: r["answers"][1].__setitem__("why", ""), "`why`"),
        ("a prose answer's `sites`", lambda r: r["answers"][2].__setitem__("sites", [P]),
         "`sites`"),
        ("a design answer's `sites`, out of the admission's order",
         lambda r: r["answers"][1]["sites"].reverse(), "`sites`"),
        ("an older answer's `version`", lambda r: r["answers"][0].__setitem__("version", "3.7.0"),
         "`version`"),
        ("the made-on answer's `version`",
         lambda r: r["answers"][2].__setitem__("version", "3.7.0"), "`version`"),
        ("an older diff's header", in_diff(0, lambda d: d.replace(
            "--- a/kernels/de.py", f"--- a/kernels/de.py {P}", 1)), "`diff`"),
        ("a made-on diff's header", in_diff(2, lambda d: d.replace(
            "+++ b/kernels/de.py", f"+++ b/kernels/de.py {P}", 1)), "`diff`"),
        ("a hunk's tail", in_diff(0, lambda d: d.replace(" @@\n", f" @@ {P}\n", 1)), "`diff`"),
        ("a hunk's counts", in_diff(2, lambda d: re.sub(
            r"(@@ -\d+(?:,\d+)? \+\d+),\d+ @@", r"\g<1>,37 @@", d, count=1)), "`diff`"),
        ("a row the maker never writes", in_diff(2, lambda d: d + f"\\ {P}\n"), "`diff`"),
        ("a statement no file of the chain has", lambda r: r["statements"].__setitem__(
            "0" * 16, {"site": "statement:1", "how": "confirmed", "why": P}),
         "no statement the worksheet names"),
        ("a statement's `site`", lambda r: r["statements"][conf].__setitem__(
            "site", "statement:37"), "`site`"),
        ("a statement's `how`", lambda r: r["statements"][conf].__setitem__("how", P), "`how`"),
        ("an answered statement's `why`, not its answer's", lambda r: r["statements"][
            ans2].__setitem__("why", P), "`why`"),
        ("a confirmation's `why` emptied", lambda r: r["statements"][conf].__setitem__(
            "why", " "), "`why`"),
    ), REC, "de", before)
    rc2, out2 = cli("check")
    ck("(and with the record as written, check's design-record row is green)",
       record_row(out2).startswith("GREEN"), record_row(out2))
    # THE VERIFIER'S THREE, ON cellchat's RECORD: each passed `design cellchat`, and the rewrite
    # said the record was already as the maker writes it.
    CC = clone / "kernels" / "cellchat.design.json"
    planted((
        ("cellchat: a value in a prose answer's `sites`",
         lambda r: r["answers"][0].__setitem__("sites", [P]), "`sites`"),
        ("cellchat: a value in `n`", lambda r: r["answers"][0].__setitem__("n", f"1, {P}"), "`n`"),
        ("cellchat: a statement keyed by a digest no line has", lambda r: r["statements"]
         .__setitem__("0" * 16, {"site": "x", "how": P, "why": "y"}),
         "no statement the worksheet names"),
    ), CC, "cellchat", cc)

    print("\n10. the record is read as the file the maker writes, never as a lenient parse of it")
    # THE BATCH'S LEAN RE-CHECK (W047 last fix, R1; ATTACKS 38): a JSON parse keeps the last of a
    # repeated key, and the check read only the parse. A text written before answer 1's own `n`
    # passed `design` and `check`; `--rewrite-record` then erased it with a trace that dropped
    # nothing, and `--confirm` with none - and `--confirm` over a record that did not parse wrote
    # a stub with no answers, exit 0. Each form below is refused by name by the stage, by `check`
    # and by every verb that writes, and nothing is written.
    text = before.decode("utf-8")

    def first(key, value):
        """`text` with `"key": value,` written once more, before the first line of `key`."""
        m = re.search(rf'\n( *)"{key}": ', text)
        return (text[:m.start()] + f'\n{m.group(1)}"{key}": {json.dumps(value)},'
                + text[m.start():]).encode("utf-8")
    forms = [
        ("a repeated key before answer 1's `n`", first("n", P), "repeats the key 'n'"),
        ("a repeated key before the record's `plugin`", first("plugin", P),
         "repeats the key 'plugin'"),
        ("a repeated key before a statement's `how`", first("how", P), "repeats the key 'how'"),
        ("a repeated key before the trace's `commit`", first("commit", P),
         "repeats the key 'commit'"),
        ("a second document after the record", before + json.dumps({"plugin": P}).encode(),
         "content after the document"),
        ("trailing space after the record", before + b" \n", "byte for byte"),
        ("a byte-order mark", b"\xef\xbb\xbf" + before, "byte-order mark"),
        ("a NaN literal", before.replace(b'"n": 1,', b'"n": NaN,', 1), "the literal NaN"),
        ("an Infinity literal", before.replace(b'"n": 1,', b'"n": Infinity,', 1),
         "the literal Infinity"),
        ("a byte that is not UTF-8", before.replace(b'"why": "', b'"why": "\xff', 1),
         "is not UTF-8"),
        ("a character the writer escapes, written raw", before.replace(
            b'"why": "', '"why": "\u00e9'.encode("utf-8"), 1), "byte for byte"),
        ("a merge-conflict marker", b"<<<<<<< HEAD\n" + before, "does not parse"),
    ]
    ck("(each form is planted: a JSON parse reads the first four as the record itself)",
       all(f != before for _w, f, _s in forms)
       and all(json.loads(f) == json.loads(before) for _w, f, _s in forms[:4]))
    sl = V._scan(SHIPPED.decode("utf-8"))[1][0]["line"]
    comment = next(x for x in SHIPPED.decode("utf-8").splitlines()
                   if x.strip().startswith("# ") and SHIPPED.decode("utf-8").count(x) == 1)
    proposal, target = td / "proposal.py", td / "replay.py"
    proposal.write_bytes(SHIPPED)
    verbs = [
        ("design de", ("design", "de")),
        ("check", ("check",)),
        ("--answer", ("design", "de", "--answer", str(proposal), "--why", WHY)),
        ("prose", ("prose", "de", "--replace", comment, comment + " (a test edit)", "--why", WHY)),
        ("--confirm", ("design", "de", "--confirm", str(sl), "--why", WHY)),
        ("--rewrite-record", ("design", "de", "--rewrite-record", "--why", WHY)),
        ("--replay-into", ("design", "de", "--replay-into", str(target))),
    ]
    for where, form, says in forms:
        for label, args in verbs:
            REC.write_bytes(form)
            target.write_bytes(SHIPPED)
            rc, out = cli(*args)
            unwritten = (REC.read_bytes() == form and DE.read_bytes() == SHIPPED
                         and target.read_bytes() == SHIPPED)
            green = label == "check" and record_row(out).startswith("GREEN")
            ck(f"{where}: `{label}` refuses it by name, nothing written",
               rc != 0 and says in out and unwritten and not green, out[-400:])
    REC.write_bytes(before)
    DE.write_bytes(SHIPPED)
    # A COPY PUT BACK IS KEPT FOR THE CHECK, NEVER TIDIED BY A VERB: the mutant "any verb drops a
    # copy again" was caught only by a confirmation over the record an older maker wrote, which
    # `--confirm` now refuses before it writes. Here the copy put back is the true declaration and
    # the trace stands, so a verb that dropped it would pass its own check and erase it.
    r = json.loads(before)
    r["answers"][0]["after_declaration"] = copies[1]
    put_back = (json.dumps(r, indent=1, sort_keys=True) + "\n").encode("utf-8")
    REC.write_bytes(put_back)
    rc, out = cli("design", "de", "--confirm", str(sl), "--why", WHY)
    ck("a copy put back after its rewrite: `--confirm` refuses it by name and keeps it, nothing "
       "written", rc == 1 and "after_declaration" in out and REC.read_bytes() == put_back,
       out[-400:])
    REC.write_bytes(before)

    # R2: ONE LITERAL PINNED BY NOTHING BUT ITS FORM. de's first answer was recorded before W035's
    # fix round 1: the file it was made on is rebuilt only from that answer's diff, and the
    # admission sets a version aside, so text in place of that file's version, with the answer's
    # `before` and `diff` re-made by the check's own helpers, passed. Every file rebuilt for an
    # answer now declares N.N.N; the digits of that one literal stay free (the stated limit).
    TAMPER = (
        "import json, sys\n"
        "from scprofile.kernels import discover\n"
        "from scprofile import validate as V\n"
        "f = {}; ok, w = V.design_record_check(discover()['de'], files=f); assert ok, w\n"
        "prev, made = f[1]; ln, old = V._version_node(prev); L = prev.split('\\n')\n"
        "L[ln - 1] = L[ln - 1].replace(json.dumps(old), json.dumps(sys.argv[1]), 1)\n"
        "p2 = '\\n'.join(L); r = json.loads(open('kernels/de.design.json').read())\n"
        "r['answers'][0]['before'] = V._sha(p2)\n"
        "r['answers'][0]['diff'] = V._maker_diff(p2, made, 'de.py', None)\n"
        "open('kernels/de.design.json', 'w').write(json.dumps(r, indent=1, sort_keys=True) + '\\n')\n")
    for value, refused in ((P, True), ("not a version", True), ("9.9.9", False)):
        REC.write_bytes(before)
        t = subprocess.run([sys.executable, "-c", TAMPER, value], cwd=str(clone), env=ENV,
                           capture_output=True, text=True, timeout=600)
        rc, out = cli("design", "de")
        rc2, out2 = cli("check")
        if refused:
            ck(f"the version of the file answer 1 was made on, {value!r}: refused by name by "
               f"`design de` and `check`", t.returncode == 0 and rc == 1
               and "answer 1 was made on declares the version" in out
               and not record_row(out2).startswith("GREEN"), (t.stderr + out)[-400:])
        else:
            ck("(the stated limit: other digits there, N.N.N, pass - that one literal, in de's "
               "record only)", t.returncode == 0 and rc == 0
               and record_row(out2).startswith("GREEN"), (t.stderr + out)[-400:])
    REC.write_bytes(before)
finally:
    shutil.rmtree(td, ignore_errors=True)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    raise SystemExit(1)
print("a design record is read as the file the maker writes, each field in the form it writes it (a "
      "reason only as text), and an older one is rewritten through it, with a trace")
