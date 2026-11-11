"""The declaration is one statement, alone on its lines, and every gate reads it as the host does.

FOUND BY W013's FINAL RE-CHECK (its verifier, at b39ca4a). The design record's check folded and
swapped the declaration's WHOLE LINES while its literal check read only the `PLUGIN` assignment's
value, so a statement on the declaration's first line (`x(); PLUGIN = {`) or its last (`}; <code>`)
ran on every import of the plugin and was compared nowhere: a payload on de's closing brace doubled
every fold change de wrote, on both fixture shapes, with the design stage, the suite, `scprofile
check` and the ladder's `agree` all green (GAP-C72). The host kept the LAST top-level `PLUGIN =`
and the check read the FIRST, so a second binding appended to the file left the design stage
reading "not design-aware" - exit 0, the job's first step - over a plugin it no longer described;
and a key `ast.literal_eval` rejects with TypeError crashed discovery with a traceback (GAP-C73).
And `scprofile check` never ran the record's check at all, so every forged record of the re-check
left it green (GAP-C74).

WHAT THIS HOLDS, each failing at b39ca4a, every attack run through the real commands - `scprofile
design de` (the maker's stage, and the stage-4 job's first step) and `scprofile check` - on a clone
of this repository carrying this tree's code:
  1. code on the declaration's first or last line is refused by name, the payload included;
  2. `PLUGIN` bound twice, in any syntax and at any depth the import runs, is refused by name, so
     the host and the check read one statement;
  3. whatever the reader meets - a key `literal_eval` rejects, a value that is not a dict, a file
     that does not parse or is not UTF-8 - is a named owe, never a traceback;
  4. `scprofile check` is red, naming de, on every one of them and on every forged record;
and still: the record's attacks of the re-check (D1) stay refused, the maker's verb may edit the
declaration after the answers (D4), and a comment after the closing brace is not code.

The verifier's driver is the source of the attacks (W013's final re-check, `attack_scripts/
attacks.py`, kept in the coordinator's scratch); each is restated here as an edit of the shipped
plugin, so the suite needs nothing outside the repository.
"""
import json
import os
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

SHIPPED = (ROOT / "kernels" / "de.py").read_text(encoding="utf-8")
RECORD = (ROOT / "kernels" / "de.design.json").read_text(encoding="utf-8")
ANCHOR = V._spent_commit(ROOT, "de")
_g = subprocess.run(["git", "-C", str(ROOT), "show", f"{ANCHOR}:kernels/de.py"],
                    capture_output=True, text=True, env=GITENV)
BASE = _g.stdout if _g.returncode == 0 else None
if BASE is None:
    ck("(the blind-record commit can be read here)", False, _g.stderr[-300:])
    print(f"\n{len(FAILS)} FAILED")
    raise SystemExit(1)

#: The verifier's out-of-site edit: the gene filter doubled (in no site the worksheet names).
FILTER = 'keep = sub.sum(axis=0) >= C["min_counts"]'
FILTER2 = 'keep = sub.sum(axis=0) >= 2 * C["min_counts"]'
#: The payload the re-check put on de's closing brace: every log2FoldChange doubled at import.
PAYLOAD = ('_pd = __import__("importlib.util").util.find_spec("pydeseq2") and __import__('
           '"pydeseq2.ds", fromlist=["ds"]); _pd and setattr(_pd.DeseqStats, "summary", '
           '(lambda f: lambda s, *a, **k: (f(s, *a, **k), s.results_df.__setitem__('
           '"log2FoldChange", 2 * s.results_df["log2FoldChange"]))[0])(_pd.DeseqStats.summary))')


def span(text):
    """(first, last) line of the declaration as the plugin ships it - found by its text, so this
    suite runs on a tree whose reader is older than this one."""
    lines = text.split("\n")
    a = lines.index("PLUGIN = {") + 1
    b = next(i for i in range(a, len(lines)) if lines[i] == "}") + 1
    return a, b


def on_line(text, n, new):
    lines = text.split("\n")
    lines[n - 1] = new
    return "\n".join(lines)


def swap(old, new):
    def edit(text):
        assert old in text, old
        return text.replace(old, new, 1)
    return edit


def chain_before(shipped, record, root=ROOT):
    """`[the file the last answer made, its file before, ..., answer 1's before]` (`chain`)."""
    c = chain(shipped, record, root)
    return [c[-1][1]] + [before for before, _made in reversed(c)]


def chain(shipped, record, root=ROOT):
    """`[(file before, file made)]` of every answer, in the record's order, rebuilt as the record
    check rebuilds them, from what the record and git hold.

    AN ANSWER MADE ON A COMMITTED FILE (`made_on`, every answer since W035's fix round 1) keeps
    no text and no copy of the declaration: its file before is read from git at that commit, and
    the file it made is that file with its diff applied, each written row read back by its digest
    from the file that follows it. AN OLDER ANSWER (de's two from W013) is undone by its diff
    from the file that follows it, its recorded declaration set back first only where that file
    is not its own - the check's own order. Every file is held to the digest the record states,
    so a rebuild that went wrong stops here rather than feeding an attack below a wrong file
    (W047: this read the last answer's declaration copy, which a made-on answer does not keep,
    and failed with a KeyError once de's prose was answered)."""
    out, cur = [], shipped
    for ans in reversed(record["answers"]):
        if ans.get("made_on"):
            prev, how = V._git_show(root, ans["made_on"], "kernels/de.py")
            assert prev is not None, how
            made = V._apply_unified(prev, ans["diff"],
                                    written=V._written(cur, prev, ans.get("version")))
        else:
            made = cur
            if V._sha(cur) != ans["after"] and ans.get("after_declaration"):
                made = V._swap_declaration(cur, ans["after_declaration"])
            prev = V._apply_unified(made, V._reverse_diff(ans["diff"]))
        assert V._sha(made) == ans["after"] and V._sha(prev) == ans["before"], ans.get("n")
        out.append((prev, made))
        cur = prev
    return out[::-1]


def forge_commit(repo, text, rel="kernels/de.py"):
    """A commit of `repo` whose `rel` is `text`, made with git's plumbing - no checkout, no hook,
    an index of its own - and reachable from nothing: the commit a forger's record names."""
    env = dict(GITENV, GIT_INDEX_FILE=str(Path(tempfile.mkdtemp(prefix="w047-forge-")) / "i"))

    def git(*a, inp=None):
        return subprocess.run(["git", "-C", str(repo), "-c", "user.name=f", "-c",
                               "user.email=f@f", *a], input=inp, capture_output=True,
                              check=True, env=env).stdout.decode("utf-8").strip()
    blob = git("hash-object", "-w", "--stdin", inp=text.encode("utf-8"))
    git("read-tree", "HEAD")
    git("update-index", "--cacheinfo", f"100644,{blob},{rel}")
    return git("commit-tree", git("write-tree"), "-m", "forged")


def doctored(repo):
    """D1a: the out-of-site edit pushed under answer 1, every digest recomputed - AND THE FORGER
    WRITES HISTORY TOO: every answer made on a committed file is re-made on a commit, in `repo`,
    of its doctored file (W047). Without that, a made-on answer's own link to git refused the
    forgery first, and the anchor - what this attack is for - was never reached. Every file of
    the forged chain is checked here to be the one its forged digests name, so the only thing
    left that can refuse it is the blind-record commit."""
    forged, last = json.loads(RECORD), None
    for (before, made), ans in zip(chain(SHIPPED, json.loads(RECORD)), forged["answers"]):
        assert FILTER in before and FILTER in made, ans.get("n")
        cur, nxt = before.replace(FILTER, FILTER2, 1), made.replace(FILTER, FILTER2, 1)
        assert last is None or cur == last, ans.get("n")     # each answer meets the one before
        if ans.get("made_on"):
            ans["made_on"] = forge_commit(repo, cur)
            again = V._apply_unified(cur, ans["diff"],
                                     written=V._written(nxt, cur, ans.get("version")))
        else:
            again = V._apply_unified(cur, ans["diff"])
        assert again == nxt, ans.get("n")
        ans["before"], ans["after"] = V._sha(cur), V._sha(nxt)
        ans.pop("after_declaration", None)    # each file is its answer's own: no copy is read
        last = nxt
    return last, json.dumps(forged, indent=1, sort_keys=True) + "\n"


EMPTY = json.dumps({"plugin": "de", "answers": [], "statements": {}})
A, B = span(SHIPPED)

# (tag, what, de.py as text or bytes, the record (None: deleted), what the refusal must say)
ATTACKS = [
    # D1a is made below, once the clone it writes its forged commits into exists
    ("D1b", "an empty record over the blind plugin, hand-edited outside every site",
     BASE.replace(FILTER, FILTER2, 1), EMPTY, "blind-record commit"),
    ("D1b2", "the record deleted over the same hand edit", BASE.replace(FILTER, FILTER2, 1), None,
     "blind-record commit"),
    ("D2a", "run-time code inside the dict",
     swap('    "api": 1,\n', '    "api": (print("HIDDEN RUN-TIME CODE RAN") or 1),\n')(SHIPPED),
     RECORD, "not a pure literal"),
    ("D2b", "run-time code on the declaration's closing line: `}; <code>`",
     on_line(SHIPPED, B, '}; print("HIDDEN RUN-TIME CODE RAN")'), RECORD,
     "code follows the declaration on its last line"),
    ("D2b-payload", "the re-check's payload on the closing line (every fold change doubled)",
     on_line(SHIPPED, B, "}; " + PAYLOAD), RECORD, "code follows the declaration on its last line"),
    ("D2c", "run-time code on the declaration's first line: `<code>; PLUGIN = {`",
     on_line(SHIPPED, A, 'print("HIDDEN RUN-TIME CODE RAN"); PLUGIN = {'), RECORD,
     "code precedes the declaration on its first line"),
    ("D3a", "a declaration that is not a literal", swap('    "api": 1,\n',
                                                        '    "api": int("1"),\n')(SHIPPED),
     RECORD, "not a pure literal"),
    ("D3b", "a file that does not parse", swap('    "api": 1,\n', '    "api": 1,,\n')(SHIPPED),
     RECORD, "does not parse"),
    ("D3c", "a second binding at the end of the file (the host read the last)",
     SHIPPED + "\nPLUGIN = dict(PLUGIN)\n", RECORD, "bound 2 times"),
    ("D3d", "a second binding on the declaration's closing line",
     on_line(SHIPPED, B, "}; PLUGIN = dict(PLUGIN)"), RECORD, "bound 2 times"),
    ("D3e", "a key `literal_eval` rejects with TypeError",
     swap('    "api": 1,\n', '    "api": 1, ["x"]: 1,\n')(SHIPPED), RECORD,
     "not a literal the host can read (TypeError"),
    ("V-block", "a second binding inside a block the import runs",
     SHIPPED + "\nif True:\n    PLUGIN = {**PLUGIN}\n", RECORD, "bound 2 times"),
    ("V-global", "a function rebinding the module's PLUGIN through `global`",
     SHIPPED + "\ndef _again():\n    global PLUGIN\n    PLUGIN = {}\n", RECORD, "bound"),
    ("V-annotation", "a walrus in a function's annotation, evaluated where the `def` stands",
     SHIPPED + "\ndef _again(x: (PLUGIN := {})):\n    return x\n", RECORD, "bound 2 times"),
    ("V-augmented", "`PLUGIN |= {...}` after the declaration",
     SHIPPED + '\nPLUGIN |= {"api": 1}\n', RECORD, "bound 2 times"),
    ("V-import", "an import bound to the name", SHIPPED + "\nimport json as PLUGIN\n", RECORD,
     "bound 2 times"),
    ("V-annotated", "the declaration written as an annotated assignment",
     on_line(SHIPPED, A, "PLUGIN: dict = {"), RECORD, "not declared by `PLUGIN = {...}`"),
    ("V-chained", "the declaration assigning another name with it",
     on_line(SHIPPED, A, "PLUGIN = OTHER = {"), RECORD, "assigns other names"),
    ("V-list", "a declaration that is not a dict",
     V._swap_declaration(SHIPPED, "PLUGIN = [1]\n") if hasattr(V, "_swap_declaration")
     else SHIPPED, RECORD, "not a dict"),
    ("V-needs", "a `needs` the host cannot read by role",
     swap('    "api": 1,\n', '    "api": 1, "needs": ["obs"],\n')(SHIPPED), RECORD,
     "not a mapping"),
    ("V-deep", "a literal nested past what the parser takes",
     swap('    "api": 1,\n', '    "api": ' + "[" * 300 + "1" + "]" * 300 + ",\n")(SHIPPED),
     RECORD, "does not parse"),
    ("V-nul", "a NUL byte in a comment", swap("PLUGIN = {\n", "PLUGIN = {  # \x00\n")(SHIPPED),
     RECORD, "does not parse"),
    ("V-bytes", "a byte that is not UTF-8, in a comment",
     SHIPPED.replace("PLUGIN = {\n", "PLUGIN = {  # \udcff\n", 1)
     .encode("utf-8", "surrogateescape"),
     RECORD, "UTF-8"),
    ("V-mutation", "the declaration changed after it, by a statement outside it",
     SHIPPED + '\nPLUGIN["inject"] = {}\n', RECORD, "outside its declaration"),
]

print("0. a clone of this repository, carrying this tree's code")
td = Path(tempfile.mkdtemp(prefix="w032-decl-"))
clone = td / "clone"
subprocess.run(["git", "clone", "-q", "--no-local", str(ROOT), str(clone)], check=True,
               capture_output=True, env=GITENV)
for d in ("scprofile", "kernels", "setup"):
    shutil.copytree(ROOT / d, clone / d, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
shutil.copyfile(ROOT / "DEVPOINTS.yaml", clone / "DEVPOINTS.yaml")
# the clone's own commit gate, so `check` judges the plugin and not a fresh clone's hook setting
subprocess.run(["git", "-C", str(clone), "config", "core.hooksPath", "setup/githooks"],
               check=True, capture_output=True, env=GITENV)
ENV = dict(GITENV, PYTHONPATH=str(clone))
DE, REC = clone / "kernels" / "de.py", clone / "kernels" / "de.design.json"
ATTACKS.insert(0, ("D1a", "a record rewritten to start from a doctored answer-1 `before`, its "
                          "made-on answers re-made on forged commits", *doctored(clone),
                   "blind-record commit"))
ROW = "every shipped plugin's declaration loads, and its design record accounts"


def put(text, record):
    DE.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    if record is None:
        REC.unlink(missing_ok=True)
    else:
        REC.write_text(record, encoding="utf-8")


def cli(*args):
    r = subprocess.run([sys.executable, "-m", "scprofile.cli", *args], cwd=str(clone), env=ENV,
                       capture_output=True, text=True, timeout=600)
    return r.returncode, r.stdout + r.stderr


def record_row(out):
    """(state, line) of `check`'s design-record row, or (None, why) when it has none."""
    line = next((l for l in out.splitlines() if ROW in l), None)
    if line is None:
        return None, "`scprofile check` has no design-record row"
    return ("GREEN" if line.strip().startswith("GREEN") else "RED"), line.strip()


try:
    put(SHIPPED, RECORD)
    rc, out = cli("design", "de")
    ck("(the shipped plugin: the design stage exits 0)", rc == 0, out[-600:])
    rc, out = cli("check")
    state, line = record_row(out)
    ck("(the shipped plugin: check's design-record row is green)", state == "GREEN", line)

    for tag, what, text, record, says in ATTACKS:
        print(f"\n{tag}: {what}")
        put(text, record)
        rc, out = cli("design", "de")
        ck(f"{tag}: `scprofile design de` owes, by name ({says!r})",
           rc == 1 and says in out and "Traceback" not in out, out[-700:])
        rc, out = cli("check")
        state, line = record_row(out)
        ck(f"{tag}: `scprofile check` is red on the design record, naming de",
           rc != 0 and state == "RED" and "de:" in line and says in line
           and "Traceback" not in out, line if state else out[-500:])
        put(SHIPPED, RECORD)

    print("\nthe host reads the declaration the check reads, and says why when it cannot")
    from scprofile import kernels as K
    for tag, what, text, record, says in ATTACKS:
        if not tag.startswith(("D2", "D3", "V-")) or tag == "V-mutation":
            continue
        put(text, record)
        try:
            fk = K.FileKernel(DE)
            err = getattr(fk, "declaration_error", None)
            ok_ = bool(err) and says in err and not (fk.spec or {}).get("inject")
        except Exception as e:                                            # noqa: BLE001
            ok_, err = False, f"{type(e).__name__}: {e}"
        ck(f"{tag}: the host lists it with no declaration and the reason", ok_, err)
        put(SHIPPED, RECORD)
    put(SHIPPED + "\nPLUGIN = dict(PLUGIN)\n", RECORD)
    rc, out = cli("validate", "de")
    ck("a plugin bound twice: `scprofile validate de` names the declaration first",
       rc != 0 and "its declaration does not load" in out and "bound 2 times" in out, out[-500:])
    put(SHIPPED, RECORD)

    print("\nan answer cannot leave a second binding: `global PLUGIN` inside a site")
    # The admission counts the names a statement BINDS, and `global` binds none - so an answer
    # adding it strictly inside a fit site was admitted, and would rebind the module's
    # declaration whenever the plugin ran.
    from scprofile.kernels import FileKernel as _FK
    with tempfile.TemporaryDirectory() as t2:
        kd = Path(t2) / "kernels"
        kd.mkdir()
        shutil.copyfile(ROOT / "kernels" / "de.py", kd / "de.py")
        shutil.copyfile(ROOT / "kernels" / "de.design.json", kd / "de.design.json")
        fits, _st, _c = V._scan(SHIPPED)
        lines = SHIPPED.split("\n")
        prop_text = None
        for f in fits:
            for a, b in f["spans"]:
                if b <= a:
                    continue
                ind = lines[a][:len(lines[a]) - len(lines[a].lstrip())]
                cand = "\n".join(lines[:a] + [ind + "global PLUGIN"] + lines[a:])
                try:
                    compile(cand, "de.py", "exec")
                except SyntaxError:
                    continue
                prop_text = cand
                break
            if prop_text:
                break
        ck("(a line strictly inside a fit site takes a `global PLUGIN`)", prop_text is not None)
        if prop_text:
            prop = Path(t2) / "global.py"
            prop.write_text(prop_text, encoding="utf-8")
            log = []
            rc = V.design_answer(_FK(kd / "de.py"), prop, "x", log=log.append, root=ROOT)
            ck("such an answer is refused, naming the declaration",
               rc == 1 and "declaration" in " ".join(log)
               and (kd / "de.py").read_text(encoding="utf-8") == SHIPPED, log[-2:])

    print("\nD1c: the first answer cannot be made over a hand edit")
    texts = chain_before(SHIPPED, json.loads(RECORD))
    put(BASE.replace(FILTER, FILTER2, 1), EMPTY)
    prop = td / "answer1.py"
    prop.write_text(V._swap_declaration(texts[-2], V._declaration_text(BASE))
                    .replace(FILTER, FILTER2, 1), encoding="utf-8")
    rc, out = cli("design", "de", "--answer", str(prop), "--why", "x")
    ck("D1c: `--answer` refuses it, naming the blind-record commit, and leaves de.py as it was",
       rc == 1 and "refused" in out and "blind-record commit" in out
       and DE.read_text(encoding="utf-8") == BASE.replace(FILTER, FILTER2, 1), out[-500:])
    put(SHIPPED, RECORD)

    print("\nwhat is not code passes: the verb's edit of the declaration (D4), and a comment")
    import re
    verb = re.sub(r'("summary": "[^"]*)"', r'\1, by population"', SHIPPED, count=1)
    verb = re.sub(r'("version": ")(\d+)\.(\d+)\.(\d+)"',
                  lambda m: f'{m.group(1)}{m.group(2)}.{int(m.group(3)) + 1}.0"', verb, count=1)
    for tag, text in (("D4", verb), ("comment", on_line(SHIPPED, B, "}  # the declaration ends"))):
        put(text, RECORD)
        rc, out = cli("design", "de")
        rc2, out2 = cli("check")
        state, line = record_row(out2)
        ck(f"{tag}: the design stage exits 0 and check's design-record row is green",
           rc == 0 and state == "GREEN", (out[-300:], line))
        put(SHIPPED, RECORD)
finally:
    shutil.rmtree(td, ignore_errors=True)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    raise SystemExit(1)
print("the declaration is one statement alone on its lines, and every gate reads it as the host "
      "does")
