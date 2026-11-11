"""The maker asks a design-aware plugin for the design, and its fixture can tell the answers apart.

FOUND BY A BLIND TEST OF THE MAKER (docs/MIGRATIONS.md 1, `de` at f5175ea). The plugin chose a
contrast's reference by sort order and could not be handed a covariate, and the maker read every
build stage of it done over both: no stage asked a design-aware plugin how it orders a factor or
what it adjusts for. And the ladder's value axis - the fixture's shape b, whose control sorts
last, built to catch exactly that (harness ADR-0027) - was handed `--control <factor>=ctrl`, shape
a's literal, on both shapes: shape b has no such level, so a plugin that took the declared control
and one that sorted could not be told apart there, and the fixture's covariate column was dropped
by `--factor` without a word.

WHAT THIS HOLDS, each failing on f5175ea:
  1. the fixture command hands each shape ITS OWN control (`{control}`) and declares the fixture's
     covariate, in the plan and in the run;
  2. the kernel point declares a BUILD stage `design` whose command is the maker's check;
  3. the check names each site where a design-aware plugin builds a model or takes a contrast,
     owes until the plugin asks the host for its frame and its order and declares `covariates`,
     and has nothing to say to a plugin that is not design-aware;
  4. the shipped `de` answers it.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# EVERY `git` HERE IS ASKED ABOUT THE REPOSITORY IT NAMES: the commit gate runs this suite under
# git's pre-commit hook, which exports GIT_INDEX_FILE=.git/index (relative), so a git run here in
# another repository would read - or write - an index that is not its own.
import os                                                                    # noqa: E402
GITENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

FAILS = []


def ck(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"\n         {detail}"))
    if not ok:
        FAILS.append(name)


print("1. the fixture hands each shape its own control, and its covariate")
# READ AS TEXT, as every suite here reads DEVPOINTS: the host depends on numpy and pandas only.
dev = (ROOT / "DEVPOINTS.yaml").read_text(encoding="utf-8")
fixture = dev[dev.index("\nfixture:"):dev.index("\nbaseline_dir:")]
code = "\n".join(l.split("#", 1)[0] for l in fixture.splitlines())
ck("plan and run are told the shape's control, not a literal",
   code.count('"--control", "{role_condition}={control}"') == 2, code[-900:])
ck("both declare the fixture's covariate",
   code.count('"--covariate", "{role_covariate}"') == 2, code[-900:])
ck("no fixture command names a level of either shape",
   "=ctrl" not in code and "=untreated" not in code)


print("\n2. the kernel point declares the design stage, a build stage with a command")
stages = dev[dev.index("      stages:"):]
names = [l.split("- name:", 1)[1].strip() for l in stages.splitlines() if "- name:" in l]
ck("a stage named design exists", "design" in names, names)
blk = stages[stages.index("- name: design"):] if "design" in names else ""
blk = blk[:blk.index("- name:", 5)] if "- name:" in blk[5:] else blk
ck("it is a build stage", "phase: build" in blk, blk[:200])
ck("its command is the maker's check",
   'command: ["{python}", "-m", "scprofile.cli", "design", "{name}"]' in blk, blk[:600])
ck("it says how to finish it", "model_frame" in blk and "ctx.levels" in blk)
ck("after the contract, before the judgement",
   "design" in names and names.index("contract") < names.index("design") < names.index("judgement"),
   names)


print("\n3. the check names the sites, and owes until the host's model is taken")
from scprofile import validate as V                                          # noqa: E402

FITS = '''
PLUGIN = {"inject": {"required": ["design"], "optional": ["contrast"%s]}}

def run(ctx):
    import somelib
    terms = ctx.params["contrast"]["terms"]
%s
    fit = somelib.Model(data=obs, design="~ " + " + ".join(terms))
    for term in terms:
%s
        res = fit.compare(contrast=[term, levels[-1], levels[0]])
'''
OWN = ('    obs = ctx.design_frame()', '        levels = sorted(obs[term].unique())')
HOST = ('    obs, covs = ctx.model_frame(ctx.design_frame(), terms)',
        '        levels = ctx.levels(term, obs[term])')


class Stub:
    def __init__(self, path, spec):
        self.path, self.spec, self.name = str(path), spec, Path(path).stem


def rooted(fn, *a, **kw):
    """`fn(..., root=ROOT)` where it takes the repository's root - the anchor of a design record
    is read there (W013 fix-up 5) - and as it was called before, where it does not."""
    import inspect
    if "root" in inspect.signature(fn).parameters:
        kw["root"] = ROOT
    return fn(*a, **kw)


def anchored(td, name, text):
    """`<td>/kernels/<name>.py`, committed in a repository of its own whose DEVPOINTS names that
    commit as the plugin's blind record: an answer needs an anchor, as de's does (fix-up 5)."""
    kdir = Path(td) / "kernels"
    kdir.mkdir()
    f = kdir / f"{name}.py"
    f.write_text(text, encoding="utf-8")
    g = ["git", "-C", str(td), "-c", "user.name=t", "-c", "user.email=t@t",
         "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", str(td)], check=True, capture_output=True, env=GITENV)
    subprocess.run(g + ["add", f"kernels/{name}.py"], check=True, capture_output=True,
                   env=GITENV)
    subprocess.run(g + ["commit", "-q", "-m", "blind"], check=True, capture_output=True,
                   env=GITENV)
    sha = subprocess.run(["git", "-C", str(td), "rev-parse", "HEAD"], check=True,
                         capture_output=True, text=True, env=GITENV).stdout.strip()
    (Path(td) / "DEVPOINTS.yaml").write_text(
        f"rules:\n  held_out:\n    spent:\n      {name}: {sha}\n", encoding="utf-8")
    return f


if not hasattr(V, "design_sites"):
    ck("validate.design_sites exists", False, "no design_sites in scprofile/validate.py")
else:
    with tempfile.TemporaryDirectory() as td:
        own = Path(td) / "own.py"
        own.write_text(FITS % ("", OWN[0], OWN[1]), encoding="utf-8")
        d = V.design_sites(Stub(own, {"inject": {"required": ["design"],
                                                 "optional": ["contrast"]}}))
        ck("a plugin ordering its own levels is design-aware and owes", d["design_aware"]
           and d["owes"], d)
        ck("each site is named with its line",
           [(ln, nm) for ln, nm, _k in d["sites"]] == [(8, "Model"), (11, "compare")], d["sites"])
        ck("and what is owed: the frame, the order, the covariates",
           [m for m, _w in d["missing"]] == ["model_frame", "levels", "covariates"], d["missing"])
        host = Path(td) / "host.py"
        host.write_text(FITS % (', "covariates"', HOST[0], HOST[1]), encoding="utf-8")
        d = V.design_sites(Stub(host, {"inject": {"required": ["design"],
                                                  "optional": ["contrast", "covariates"]}}))
        ck("one that takes the host's frame and order and declares covariates owes nothing",
           d["design_aware"] and not d["owes"] and len(d["sites"]) == 2, d)
        plain = Path(td) / "plain.py"
        plain.write_text("PLUGIN = {}\n\ndef run(ctx):\n    f(formula='x')\n", encoding="utf-8")
        d = V.design_sites(Stub(plain, {"inject": {"required": ["counts"]}}))
        ck("one that is not design-aware has nothing to answer",
           not d["design_aware"] and not d["owes"] and not d["sites"], d)


print("\n4. the shipped de answers the worksheet")
r = subprocess.run([sys.executable, "-m", "scprofile.cli", "design", "de"], capture_output=True,
                   text=True, cwd=str(ROOT), timeout=120)
ck("scprofile design de exits 0", r.returncode == 0, (r.stdout + r.stderr)[-800:])


print("\n5. every STATEMENT of what was contrasted or modelled is a site, answered through the "
      "worksheet and recorded (GAP-C47)")
# FOUND BY W013's VERIFIER: de's runtime caveat said an interaction was "not contrasted" beside
# the row contrasting it, and the sentence was changed with no verb and no worksheet naming the
# site. A plugin's sentence about the design is a claim about the host's decision.
STATED = '''
PLUGIN = {"version": "1.0.0", "inject": {"required": ["design"], "optional": ["contrast", "covariates"]}}

def run(ctx):
    import somelib
    terms = ctx.params["contrast"]["terms"]
    obs, covs = ctx.model_frame(ctx.design_frame(), terms)
    for term in terms:
        levels = ctx.levels(term, obs[term])
        res = somelib.compare(contrast=[term, levels[-1], levels[0]])
    ctx.caveat("the cells of every sample were summed before testing")
    if terms:
        ctx.caveat("THE INTERACTION IS IN THE MODEL AND IS NOT CONTRASTED here")
'''


class Stub2(Stub):
    pass


import json                                                                  # noqa: E402
with tempfile.TemporaryDirectory() as td0:
    f0 = Path(td0) / "stated.py"
    f0.write_text(STATED, encoding="utf-8")
    d0 = V.design_sites(Stub2(f0, {"inject": {"required": ["design"],
                                              "optional": ["contrast", "covariates"]}}))
    st0 = d0.get("statements") or []
    ck("the sentence about the model is named as a statement site, the other is not",
       [x["line"] for x in st0] == [13], [(x["line"], x.get("text")) for x in st0])
    ck("and it is owed until it is answered", d0["owes"]
       and [m for m, _w in d0["missing"]] == ["statement:13"], d0["missing"])
if not hasattr(V, "design_answer"):
    ck("validate.design_answer, design_confirm and design_replay exist", False,
       "no answer mechanism in scprofile/validate.py")
else:
    with tempfile.TemporaryDirectory() as td:
        f = anchored(td, "stated", STATED)
        k = Stub2(f, {"inject": {"required": ["design"], "optional": ["contrast", "covariates"]}})
        base = f.read_text(encoding="utf-8")
        ck("a confirmation needs a reason", V.design_confirm(k, 13, "", log=lambda *a: None) == 1)
        ck("confirmed true, by the digest of its syntax, it is answered",
           V.design_confirm(k, 13, "checked against the host", log=lambda *a: None) == 0
           and not V.design_sites(k)["owes"])
        rec = json.loads(V.design_record_path(k).read_text(encoding="utf-8"))
        ck("the confirmation is in the worksheet's own record", any(
            v.get("how") == "confirmed" and v.get("site") == "statement:13"
            for v in rec["statements"].values()), rec)
        f.write_text(base.replace("NOT CONTRASTED here", "not contrasted at all"), "utf-8")
        ck("a sentence changed after it was confirmed owes again", V.design_sites(k)["owes"])
        f.write_text(base, encoding="utf-8")
        V.design_record_path(k).unlink()
        outside = Path(td) / "outside.py"
        outside.write_text(base.replace('"version": "1.0.0", ', '"version": "1.0.0", "x": 1, '),
                           encoding="utf-8")
        lines = []
        ck("an answer changing a line no site names is refused, by line",
           V.design_answer(k, outside, "why", log=lines.append) == 1
           and f.read_text(encoding="utf-8") == base
           and any("line(s) 2" in x and "hand edit" in x for x in lines), lines)
        fixed = Path(td) / "fixed.py"
        fixed.write_text(base.replace(
            '        ctx.caveat("THE INTERACTION IS IN THE MODEL AND IS NOT CONTRASTED here")',
            '        # the interaction is contrasted, as its own row\n'
            '        ctx.caveat("THE INTERACTION IS IN THE MODEL AND IS CONTRASTED, as its own row")'),
            encoding="utf-8")
        ck("an answer at the statement is applied, and the version is the maker's to raise",
           V.design_answer(k, fixed, "it is contrasted", log=lambda *a: None) == 0
           and "IS CONTRASTED, as its own row" in f.read_text(encoding="utf-8")
           and '"version": "1.1.0"' in f.read_text(encoding="utf-8"))
        ck("and the statement it answered is answered", not V.design_sites(k)["owes"])
        rec = json.loads(V.design_record_path(k).read_text(encoding="utf-8"))
        ans = rec["answers"][0] if rec["answers"] else {}
        # the diff names every line by its digest, the lines it wrote too (W035 fix round 2)
        ck("the record carries the diff, the reason and the sites",
           ans.get("sites") == ["statement:13"] and ans.get("why") == "it is contrasted"
           and "+" + V.REDACTED + V._sha("        # the interaction is contrasted, as its own row\n")
           in ans.get("diff", "") and "the interaction is contrasted" not in ans.get("diff", ""),
           ans)
        copy = Path(td) / "copy.py"
        copy.write_text(base, encoding="utf-8")
        ck("replayed onto the file it was made against, the record rebuilds the plugin exactly",
           V.design_replay(k, copy, log=lambda *a: None) == 0
           and copy.read_text(encoding="utf-8") == f.read_text(encoding="utf-8"))
        copy.write_text(base + "\n", encoding="utf-8")
        ck("and refuses a file it was not made against",
           V.design_replay(k, copy, log=lambda *a: None) == 1)


print("\n6. the shipped de: every statement answered, and its record replays")
from scprofile.kernels import discover                                      # noqa: E402
_de = discover()["de"]
ck("the worksheet keeps its own record beside the plugin", hasattr(V, "design_record_path")
   and V.design_record_path(_de).is_file())
if hasattr(V, "design_record_path"):
    d = V.design_sites(_de)
    ck("the worksheet names de's statements, and every one is answered",
       len(d.get("statements") or []) >= 10
       and all(x.get("answered") for x in d["statements"]), [
           (x["line"], bool(x.get("answered"))) for x in d.get("statements") or []])
    rec = json.loads(V.design_record_path(_de).read_text(encoding="utf-8")) \
        if V.design_record_path(_de).is_file() else {"answers": []}
    ck("its record holds the answers that changed it, each with a reason and a diff",
       len(rec["answers"]) >= 2 and all(a.get("why") and a.get("diff") for a in rec["answers"]),
       len(rec["answers"]))
    # OUTSIDE THE DECLARATION (fix-up 5): the declaration is the maker's verb's to edit after an
    # answer, and a whole-file comparison failed exactly that; the record's self-check below
    # covers the rest.
    _ship = (ROOT / "kernels" / "de.py").read_text(encoding="utf-8")
    _last = rec["answers"][-1] if rec["answers"] else {}
    _swap = getattr(V, "_swap_declaration", None)
    ck("the last answer made the file that ships, outside its declaration", bool(_last)
       and _last["after"] == V._sha(_swap(_ship, _last.get("after_declaration", ""))
                                    if _swap and _last.get("after_declaration") else _ship))
    _chk = getattr(V, "design_record_check", None)
    ck("the record undoes from the shipped file, and every answer is admitted again at the "
       "sites it records", _chk is not None and _chk(_de)[0], _chk(_de) if _chk else None)


print("\n7. an answer cannot carry a hand edit: narrow fit sites, insertions strictly inside, "
      "the record re-checked on replay (W013 fix-up 2)")
# THE VERIFIER'S THREE PROBES, run against a copy of the shipped plugin. A fit site spanned its
# whole loop or function - 334 of run()'s 532 lines and all of selftest - so a doubled filter
# threshold and a zeroed selftest gate were recorded as a design answer; an insertion just after
# the loop was accepted naming no site; and the replay trusted any diff whose digests matched.
import shutil                                                                 # noqa: E402
if not hasattr(V, "design_answer"):
    ck("the answer mechanism exists", False, "no design_answer")
else:
    with tempfile.TemporaryDirectory() as td:
        de_copy = Path(td) / "de.py"
        shutil.copyfile(ROOT / "kernels" / "de.py", de_copy)
        shutil.copyfile(V.design_record_path(_de), Path(td) / "de.design.json")
        kd = Stub(de_copy, _de.spec)
        shipped = de_copy.read_text(encoding="utf-8")

        def refused(name, edit):
            prop = Path(td) / f"{name}.py"
            prop.write_text(edit(shipped), encoding="utf-8")
            out = []
            rc = rooted(V.design_answer, kd, prop, "x", log=out.append)
            return rc == 1 and de_copy.read_text(encoding="utf-8") == shipped, out

        ok_, out = refused("threshold", lambda t: t.replace(
            'keep = sub.sum(axis=0) >= C["min_counts"]',
            'keep = sub.sum(axis=0) >= 2 * C["min_counts"]', 1))
        ck("a filter threshold three lines from a fit call is not a fit site: refused",
           ok_ and any("hand edit" in x for x in out), out)
        ok_, out = refused("gate", lambda t: t.replace("assert found >= 15, (",
                                                      "assert found >= 0, (", 1))
        ck("a selftest's gate is not a fit site: refused", ok_, out)
        anchor = ('        ctx.log(f"  {pop}: {int(m.sum())} pseudobulk samples, '
                  '{int(keep.sum()):,} genes tested")\n')
        ck("(the probe's anchor is in the shipped plugin)", anchor in shipped)
        ok_, out = refused("edge", lambda t: t.replace(anchor, anchor + "    out = out[:1]\n", 1))
        ck("an insertion just after a site's last line is refused", ok_, out)
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "stated.py"
        f.write_text(STATED, encoding="utf-8")
        k = Stub2(f, {"inject": {"required": ["design"], "optional": ["contrast", "covariates"]}})
        before = STATED
        after = STATED.replace('"version": "1.0.0", ', '"version": "1.0.0", "x": 1, ')
        import difflib
        tampered = {"plugin": "stated", "statements": {}, "answers": [{
            "n": 1, "why": "x", "sites": ["fit:10"], "version": "1.0.0",
            "before": V._sha(before), "after": V._sha(after),
            "diff": "".join(difflib.unified_diff(before.splitlines(keepends=True),
                                                 after.splitlines(keepends=True), "a", "b"))}]}
        V.design_record_path(k).write_text(json.dumps(tampered), encoding="utf-8")
        copy = Path(td) / "copy.py"
        copy.write_text(before, encoding="utf-8")
        out = []
        ck("a record whose diff changes a line outside every site does not replay",
           V.design_replay(k, copy, log=out.append) == 1
           and copy.read_text(encoding="utf-8") == before, out)


print("\n8. one line model; design arguments only, two hops; no added binding (W013 fix-up 3)")
# THE VERIFIER'S ROUTES AT af0f560, against a copy of the shipped plugin. Eleven form feeds (or
# line separators) in an admitted comment shifted every later index of the diff against the `ast`
# line numbers its sites are counted in; a fit site's names came from every argument, so the
# configuration, the gene mask, `refit_cooks` and `alpha` were all answerable; and a statement
# added beside a site line rode in with it. And the other way: two design answers two hops from
# the call - the terms a formula is built from, the column an interaction is picked by - were
# refused.
if hasattr(V, "design_answer"):
    with tempfile.TemporaryDirectory() as td:
        de_copy = Path(td) / "de.py"
        shutil.copyfile(ROOT / "kernels" / "de.py", de_copy)
        shutil.copyfile(V.design_record_path(_de), Path(td) / "de.design.json")
        kd = Stub(de_copy, _de.spec)
        shipped = de_copy.read_text(encoding="utf-8")

        def verdict(name, edit):
            prop = Path(td) / f"{name}.py"
            with open(prop, "w", encoding="utf-8", newline="") as fh:
                fh.write(edit(shipped))
            out = []
            rc = rooted(V.design_answer, kd, prop, "x", log=out.append)
            admitted = rc == 0
            de_copy.write_text(shipped, encoding="utf-8")         # each probe on the shipped file
            shutil.copyfile(V.design_record_path(_de), V.design_record_path(kd))  # and its record
            return admitted, " ".join(out)

        def swap(old, new):
            def edit(t):
                assert old in t, old
                return t.replace(old, new, 1)
            return edit

        CONFIG = "    C = ctx.config\n"
        for ch, what in (("\x0c", "form feeds"), ("\u2028", "line separators")):
            ok_, out = verdict("lb", swap(CONFIG, "    C = ctx.config  # " + ch * 11 + "\n"))
            ck(f"eleven {what} in a comment are refused, by name", not ok_
               and "U+" in out, out[-300:])
        ok_, out = verdict("cr", lambda t: t.replace("\n", "\r\n"))
        ck("carriage returns are refused, by name", not ok_ and "carriage return" in out,
           out[-200:])
        _lm = getattr(V, "_lines", None)
        ck("one line model: a line is what `ast` counts", _lm is not None
           and _lm("a\x0cb\nc\u2028d\n") == ["a\x0cb\n", "c\u2028d\n"])
        for name, edit in (
                ("config", swap(CONFIG, '    C = dict(ctx.config, min_counts=2 * '
                                        'ctx.config["min_counts"])\n')),
                ("mask", swap("counts_df = pd.DataFrame(np.rint(sub[:, keep]).astype(int),",
                              'counts_df = pd.DataFrame(np.rint(sub[:, keep & (sub.sum(axis=0) '
                              '>= 2 * C["min_counts"])]).astype(int),')),
                ("refit", swap("refit_cooks=True, min_replicates",
                               "refit_cooks=False, min_replicates")),
                ("alpha", swap('                            alpha=C["alpha"],\n',
                               '                            alpha=0.5,\n')),
                ("added", swap("terms, subset=pop)\n",
                               "terms, subset=pop)  # the host's frame\n"
                               "        C = dict(C, alpha=0.5)\n"))):
            ok_, out = verdict(name, edit)
            ck(f"not a design answer, refused: {name}", not ok_, out[-300:])
        for name, edit in (
                ("terms", swap("use, aliased = _identifiable(ctx, sub_obs, terms)",
                               "use, aliased = _identifiable(ctx, sub_obs, terms + covs)")),
                ("hits", swap('hits = [c for c in cols if ":" in c and a_ in c and b_ in c]',
                              'hits = [c for c in cols if ":" in c and f"{a_}[" in c '
                              'and f"{b_}[" in c]'))):
            ok_, out = verdict(name, edit)
            ck(f"a design answer two hops from the call is admitted: {name}", ok_, out[-300:])
        ck("the depth is stated", getattr(V, "DESIGN_DEPTH", None) == 2
           and "metadata" in getattr(V, "DESIGN_ARGUMENTS", ()))


print("\n9. the record verifies itself wherever it is read (W013 fix-up 4)")
# THE VERIFIER'S ROUTE AT 190fcf4: a hand edit in no site (the cut of the hit counts) with an
# entry appended to the record claiming a site, with the right digests, passed the suite, the
# check, `scprofile design` and the maker's status - only `--replay-into`, whose starting file is
# not in the repository, refused it. And a hand edit with no entry at all read `ok` here.
if hasattr(V, "design_answer"):
    import difflib
    CUT = 'sig = tested & (pa < C["alpha"])'
    with tempfile.TemporaryDirectory() as td:
        de_copy = Path(td) / "de.py"
        shutil.copyfile(ROOT / "kernels" / "de.py", de_copy)
        shutil.copyfile(V.design_record_path(_de), Path(td) / "de.design.json")
        kd = Stub(de_copy, _de.spec)
        shipped = de_copy.read_text(encoding="utf-8")
        _check = getattr(V, "design_record_check", None)
        check = (lambda k: rooted(_check, k)) if _check else None
        ck("(the shipped copy and its record agree)", check is not None and check(kd)[0],
           check(kd) if check else None)
        ck("(the probe's line is in the shipped plugin)", CUT in shipped)
        edited = shipped.replace(CUT, 'sig = tested & (pa < 0.5)', 1)
        de_copy.write_text(edited, encoding="utf-8")
        d = rooted(V.design_sites, kd)
        ck("a hand edit with no record entry: the design stage owes",
           d["owes"] and any(m == "record" for m, _w in d["missing"]), d["missing"][-1:])
        rec = json.loads(V.design_record_path(kd).read_text(encoding="utf-8"))
        rec["answers"].append({
            "n": len(rec["answers"]) + 1, "why": "x", "sites": ["fit:1406"],
            "version": rec["answers"][-1]["version"], "before": V._sha(shipped),
            "after": V._sha(edited),
            "diff": "".join(difflib.unified_diff(V._lines(shipped), V._lines(edited), "a", "b")),
            "after_declaration": rec["answers"][-1].get("after_declaration", "")})
        V.design_record_path(kd).write_text(json.dumps(rec), encoding="utf-8")
        d = rooted(V.design_sites, kd)
        ck("the same edit with a forged entry claiming a site: the design stage owes",
           d["owes"] and any(m == "record" for m, _w in d["missing"]), d["missing"][-1:])
        ck("and the check names the entry as not admissible",
           check is not None and not check(kd)[0] and "not admissible" in check(kd)[1],
           check(kd) if check else None)
        de_copy.write_text(shipped, encoding="utf-8")
        shutil.copyfile(V.design_record_path(_de), Path(td) / "de.design.json")
        de_copy.write_text(shipped.replace(
            '"summary": "which genes change, per cell type, across the design"',
            '"summary": "which genes change, per cell type, across the design, per population"', 1),
            encoding="utf-8")
        ck("a change to the declaration alone - the verb's to make - still meets the record",
           check is not None and check(kd)[0] and not rooted(V.design_sites, kd)["owes"],
           check(kd) if check else None)


print("\n10. the record's chain is anchored at the blind-record commit; the declaration is a pure "
      "literal (W013 fix-up 5)")
# THE VERIFIER'S ROUTES AT e63104c: a hand edit outside every site (the up-count cut), with the
# record rewritten so its chain ends on a doctored answer-1 `before`, passed `scprofile design`,
# the suite and `scprofile check`; an empty record returned ok, so a hand edit before the first
# answer would become its base; run-time code inside `PLUGIN = {...}` passed; a declaration that
# does not load read "not design-aware".
if hasattr(V, "design_answer"):
    import difflib
    UP = '"n_up": int((sig & (lfc > 0)).sum())'
    UP2 = '"n_up": int((sig & (lfc > 1)).sum())'

    def sites_of(k):
        return rooted(V.design_sites, k)

    def check_of(k):
        fn = getattr(V, "design_record_check", None)
        return None if fn is None else rooted(fn, k)

    def chain(shipped, record, root=ROOT):
        """`[(file before, file made)]` of every answer, in order, rebuilt as the record check
        rebuilds them, from what the record and git hold (W047): an answer made on a committed
        file read from git at its `made_on`, its written rows resolved by digest from the file
        that follows it; an older one undone by its diff, its recorded declaration set back first
        only where that file is not its own. Each file is held to the digest the record states.
        This read the last answer's copy of the declaration, which a made-on answer does not
        keep, and failed with a KeyError once de's prose was answered."""
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
        """A commit of `repo` whose `rel` is `text`, made with git's plumbing (no checkout, no
        hook, an index of its own) and reachable from nothing: the commit a forger names."""
        env = dict(GITENV, GIT_INDEX_FILE=str(Path(tempfile.mkdtemp(prefix="w047-")) / "i"))

        def git(*a, inp=None):
            return subprocess.run(["git", "-C", str(repo), "-c", "user.name=f", "-c",
                                   "user.email=f@f", *a], input=inp, capture_output=True,
                                  check=True, env=env).stdout.decode("utf-8").strip()
        blob = git("hash-object", "-w", "--stdin", inp=text.encode("utf-8"))
        git("read-tree", "HEAD")
        git("update-index", "--cacheinfo", f"100644,{blob},{rel}")
        return git("commit-tree", git("write-tree"), "-m", "forged")

    shipped = (ROOT / "kernels" / "de.py").read_text(encoding="utf-8")
    record = json.loads(V.design_record_path(_de).read_text(encoding="utf-8"))
    pairs = chain(shipped, record)
    texts = [pairs[-1][1]] + [before for before, _made in reversed(pairs)]
    with tempfile.TemporaryDirectory() as td:
        de_copy = Path(td) / "de.py"
        kd = Stub(de_copy, _de.spec)
        rp = V.design_record_path(kd)
        # 1. THE DOCTORED BASE: the hand edit pushed under answer 1, every digest recomputed, AND
        # HISTORY WRITTEN TOO (W047): each answer made on a committed file is re-made on a commit
        # of its doctored file, in a clone, so its own link to git cannot refuse the forgery
        # first and the anchor is the only thing left that can. Every forged file is checked here
        # to be the one its forged digests name.
        repo = Path(td) / "repo"
        subprocess.run(["git", "clone", "-q", "--no-local", str(ROOT), str(repo)], check=True,
                       capture_output=True, env=GITENV)
        shutil.copyfile(ROOT / "DEVPOINTS.yaml", repo / "DEVPOINTS.yaml")
        forged, last = json.loads(json.dumps(record)), None
        for (before, made), ans in zip(pairs, forged["answers"]):
            assert UP in before and UP in made, ans.get("n")
            cur, nxt = before.replace(UP, UP2, 1), made.replace(UP, UP2, 1)
            assert last is None or cur == last, ans.get("n")
            if ans.get("made_on"):
                ans["made_on"] = forge_commit(repo, cur)
                again = V._apply_unified(cur, ans["diff"],
                                         written=V._written(nxt, cur, ans.get("version")))
            else:
                again = V._apply_unified(cur, ans["diff"])
            assert again == nxt, ans.get("n")
            ans["before"], ans["after"] = V._sha(cur), V._sha(nxt)
            ans.pop("after_declaration", None)    # each file is its answer's own
            last = nxt
        (repo / "kernels" / "de.py").write_text(last, encoding="utf-8")
        (repo / "kernels" / "de.design.json").write_text(json.dumps(forged), encoding="utf-8")
        kf = Stub(repo / "kernels" / "de.py", _de.spec)
        r = V.design_record_check(kf, root=repo)
        ck("a record rewritten to start from a doctored base, its made-on answers re-made on "
           "forged commits, does not meet the blind-record commit",
           not r[0] and "blind-record commit" in r[1], r)
        ck("and the design stage owes", V.design_sites(kf, root=repo)["owes"])
        # 2. AN EMPTY RECORD AND A HAND EDIT: the plugin as it was blind, edited outside the sites
        # (read with git here, so the check is what is tested, at any commit)
        g = subprocess.run(["git", "-C", str(ROOT), "show", "f5175ea:kernels/de.py"],
                           capture_output=True, text=True, env=GITENV)
        base_text = g.stdout if g.returncode == 0 else None
        ck("(the blind-record commit can be read here)", base_text is not None, g.stderr[-200:])
        if base_text is not None:
            ck("(the probe's line is in the plugin as it was blind)", UP in base_text)
            empty = json.dumps({"plugin": "de", "answers": [], "statements": {}})
            de_copy.write_text(base_text.replace(UP, UP2, 1), encoding="utf-8")
            rp.write_text(empty, encoding="utf-8")
            r = check_of(kd)
            ck("with no answer yet, a hand edit before the first answer fails, against the "
               "blind-record commit", r is not None and not r[0], r)
            de_copy.write_text(base_text, encoding="utf-8")
            r = check_of(kd)
            ck("(and the plugin as it was blind, unedited, passes)", r is not None and r[0], r)
            # THE FIRST ANSWER: answer 1 as recorded, handed in whole over the plugin as it was
            # blind, is admitted; the same answer over the hand-edited plugin is refused, so a hand
            # edit made before the first answer does not become the record's base.
            first = Path(td) / "first.py"
            first.write_text(V._swap_declaration(texts[-2], V._declaration_text(base_text)),
                             encoding="utf-8")
            out = []
            rc = rooted(V.design_answer, kd, first, "x", log=out.append)
            ck("(answer 1, handed in over the plugin as it was blind, is admitted)", rc == 0, out)
            de_copy.write_text(base_text.replace(UP, UP2, 1), encoding="utf-8")
            rp.write_text(empty, encoding="utf-8")
            first.write_text(first.read_text(encoding="utf-8").replace(UP, UP2, 1),
                             encoding="utf-8")
            out = []
            rc = rooted(V.design_answer, kd, first, "x", log=out.append)
            ck("the same answer over a hand-edited plugin is refused, naming the blind-record "
               "commit", rc == 1 and "blind-record commit" in " ".join(out)
               and de_copy.read_text(encoding="utf-8") == base_text.replace(UP, UP2, 1), out)
        # 3. RUN-TIME CODE INSIDE THE DECLARATION
        de_copy.write_text(shipped.replace(
            '    "api": 1,\n', '    "api": (globals().__setitem__("PVALUE_BINS", 5), 1)[1],\n', 1),
            encoding="utf-8")
        rp.write_text(json.dumps(record), encoding="utf-8")
        r = check_of(kd)
        ck("a declaration that is not a pure literal fails the record's check",
           r is not None and not r[0] and "literal" in r[1], r)
        d = sites_of(kd)
        ck("and the design stage owes, naming the declaration", d["owes"]
           and any(m == "declaration" for m, _w in d["missing"]), d["missing"][:2])
        # 4. A DECLARATION THE HOST CANNOT LOAD IS NOT "NOT DESIGN-AWARE"
        from scprofile.kernels import FileKernel
        kernels_dir = Path(td) / "kernels"
        kernels_dir.mkdir()
        bad = kernels_dir / "de.py"
        bad.write_text(de_copy.read_text(encoding="utf-8"), encoding="utf-8")
        fk = FileKernel(bad)
        d = V.design_sites(fk)
        ck("a plugin whose declaration does not load: the design stage owes",
           d["owes"] and not fk.spec.get("inject"), (fk.spec.get("inject"), d["missing"][:1]))
        # 5. THE MAKER'S VERB EDITS THE DECLARATION AFTER THE ANSWERS: it still meets the record
        # (a value and the version changed, as `sch dev edit --set summary=...` changes them)
        import re
        verb = re.sub(r'("summary": "[^"]*)"', r'\1, by population"', shipped, count=1)
        verb = re.sub(r'("version": ")(\d+)\.(\d+)\.(\d+)"',
                      lambda m: f'{m.group(1)}{m.group(2)}.{int(m.group(3)) + 1}.0"', verb, count=1)
        ck("(the edit is to the declaration, and only to it)", verb != shipped
           and V._swap_declaration(verb, V._declaration_text(shipped)) == shipped)
        de_copy.write_text(verb, encoding="utf-8")
        rp.write_text(json.dumps(record), encoding="utf-8")
        d = sites_of(kd)
        ck("a verb's edit of the declaration after the answers still meets the record",
           not d["owes"], d["missing"][:2])

print("\n11. the base is read where there is no git; where the history is not there, it is not "
      "established (W013 fix-up 5)")
# THE CLUSTER'S COMPUTE NODES HAVE NO `git` (harness ADR-0027), and the stage-4 job's first step
# is `scprofile design de` on the tool's checkout, under `set -e`: there the base is read from the
# checkout's own object store. A checkout that does not hold the blind-record commit - shallow, or
# no repository at all - cannot establish the base, and the check fails rather than passing.
if not hasattr(V, "_git_show"):
    ck("the record's base can be read where there is no git (validate._git_show)", False,
       "no reader of the blind-record commit in scprofile/validate.py")
else:
    import shutil
    anchor = V._spent_commit(ROOT, "de")
    want = subprocess.run(["git", "-C", str(ROOT), "show", f"{anchor}:kernels/de.py"],
                          capture_output=True, text=True, env=GITENV).stdout
    ck("(DEVPOINTS names de's blind-record commit, and git gives its plugin)",
       bool(anchor) and "PLUGIN = {" in want, anchor)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clone, shallow, plain = td / "clone", td / "shallow", td / "plain"
        subprocess.run(["git", "clone", "-q", "--no-local", str(ROOT), str(clone)], check=True,
                       capture_output=True, env=GITENV)
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{ROOT}", str(shallow)],
                       check=True, capture_output=True, env=GITENV)
        subprocess.run(["git", "-C", str(clone), "worktree", "add", "-q", "--detach",
                        str(td / "linked")], check=True, capture_output=True, env=GITENV)
        # each holds the plugin, its record and DEVPOINTS as they stand here
        for d in (clone, shallow, plain):
            (d / "kernels").mkdir(parents=True, exist_ok=True)
            for rel in ("DEVPOINTS.yaml", "kernels/de.py", "kernels/de.design.json"):
                shutil.copyfile(ROOT / rel, d / rel)
        nogit = td / "bin-without-git"
        nogit.mkdir()
        path0 = os.environ.get("PATH", "")
        os.environ["PATH"] = str(nogit)
        try:
            here = V._git_show(ROOT, anchor, "kernels/de.py")
            fresh = V._git_show(clone, anchor, "kernels/de.py")
            short = V._git_show(clone, anchor[:7], "kernels/de.py")
            linked = V._git_show(td / "linked", anchor, "kernels/de.py")
            gone = V._git_show(shallow, anchor, "kernels/de.py")
            node = V.design_record_check(Stub(clone / "kernels" / "de.py", _de.spec), root=clone)
            cut = V.design_record_check(Stub(shallow / "kernels" / "de.py", _de.spec),
                                        root=shallow)
            bare = V.design_record_check(Stub(plain / "kernels" / "de.py", _de.spec), root=plain)
            cli = subprocess.run([sys.executable, "-m", "scprofile.cli", "design", "de"],
                                 cwd=str(clone), capture_output=True, text=True, timeout=300,
                                 env=dict(GITENV, PATH=str(nogit), PYTHONPATH=str(clone)))
        finally:
            os.environ["PATH"] = path0
        ck("with no git, this repository's object store gives the plugin at the blind-record "
           "commit, byte for byte", here[0] == want and "object store" in here[1], here[1])
        ck("and so does a fresh clone's - one pack, its deltas", fresh[0] == want, fresh[1])
        ck("by an abbreviated name too", short[0] == want, short[1])
        ck("and a linked worktree's, through its `.git` file", linked[0] == want, linked[1])
        ck("a shallow clone, which lacks the commit, cannot give it", gone[0] is None, gone[1])
        ck("with no git, the design record's check passes on a checkout that has the history",
           node[0], node)
        # WHICHEVER READ OF THE HISTORY COMES FIRST FAILS IT (W047): the anchor, or - once an
        # answer is made on a committed file - the file that answer was made on. A shallow clone
        # at a later head lacks both; a directory that is no repository has neither.
        closed = ("base cannot be established", "the file it was made on cannot be read")
        ck("on a shallow checkout: the history it needs is not there, and it fails",
           not cut[0] and any(s in cut[1] for s in closed), cut)
        ck("in a directory that is no repository: the same", not bare[0]
           and any(s in bare[1] for s in closed), bare)
        ck("the job's first step, `scprofile design de`, on a checkout, with no git on PATH: "
           "exit 0", cli.returncode == 0, (cli.stdout + cli.stderr)[-600:])

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    raise SystemExit(1)
print("the maker demands the design, and the fixture can tell the answers apart")
