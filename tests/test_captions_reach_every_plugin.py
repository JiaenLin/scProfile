"""The host owns the legend format, so the host must be able to HAND a plugin a writer for it.

THE DEFECT, MEASURED ON A SEALED RUN. 711 panels carried 69 written legends and 642 carried none,
and the reason was structural. `scprofile/captions.py` had four read sites in the host and no
writer in production: its own `write` was dead code, and the only thing in the repository that
produced a `captions.tsv` was R embedded inside ONE plugin, which had copied the format into three
of its own scripts. So the format was host-owned in name and plugin-implemented in fact, and the
second plugin that embedded R would have had to re-derive it by reading somebody else's
`write.table` call - three times, without knowing which of the three was current.

WHAT THIS SUITE PINS.

  1. `write` produces exactly what the host's own reader parses, byte for byte - unquoted,
     tab-separated, LF, one line per panel.
  2. The R writer the host ships produces THE SAME BYTES for the same inputs. Not "the same
     shape": the same file. A specification that is checked by eye is a specification that
     drifts, and this one had already drifted into three copies.
  3. The R draw wrapper is one definition and does the whole draw site - device, expression,
     close, legend - so the next plugin takes the wrapper rather than re-inventing the parts of
     it that the copies had each got wrong differently.
  4. It reaches a plugin WITHOUT the plugin importing the host, through the channel that already
     carries the host's figure context into every plugin's `in.json`.
  5. And the reader is read with the quoting the file is written with, which it was not: one
     unbalanced double quote in a caption silently ate every legend after it.
  6. A legend is filed beside the PANEL. The wrapper appended every row to the directory that was
     opened, so a run drawing one panel per unit into per-unit subdirectories pooled every legend
     into one file - and the reader, keying on basename, served one unit another unit's sentence.

A NOTE ON WHY THE FIXTURES LOOK THE WAY THEY DO. Check 5 was first written with the quote in the
MIDDLE of a caption, and it pinned nothing: csv enters quoted mode only when a field BEGINS with a
double quote, so that fixture parsed identically under QUOTE_MINIMAL and QUOTE_NONE and the whole
suite still passed with the fix reverted. Both fixtures now open with the quote. A test that
cannot fail is worse than no test, because it is counted.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import captions as C                                       # noqa: E402
from scprofile import figure_context as FC                                # noqa: E402
from scprofile import manifest as MF                                      # noqa: E402

FAILURES = []


def ck(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


#: THE INPUTS ARE THE ONES THAT BREAK A FORMAT, not three tidy sentences. Each row here is a shape
#: that has cost this project something: whitespace that would split a row in two, a term in
#: quotes, an accented word, and a non-breaking space - which is what arrives the moment anybody
#: pastes a phrase into a caption, and which R's `\s` does not fold unless it is told to.
ROWS = [
    {"file": "native_matrix.png",
     "caption": "Rows are senders and columns are receivers; colour is the summed weight.",
     "drawn_by": "tool"},
    {"file": "figures/native_flow.png",
     "caption": "  A legend written   with a\ttab, a\nnewline and doubled  spaces.  ",
     "drawn_by": "plugin"},
    {"file": "native_scale.png",
     "caption": "Accented prose — naïve, coöperate, façade — and an em dash for good measure.",
     "drawn_by": "plugin"},
    {"file": "native_totals.png",
     # THE NON-BREAKING SPACES ARE WRITTEN AS ESCAPES so they can be seen. They are
     # why the R writer needs PCRE's (*UCP): without it R folds ASCII whitespace
     # only while Python's str.split() folds every Unicode space, and the two
     # writers stop producing the same bytes for a caption somebody pasted into.
     "caption": "A\u00a0non-breaking\u00a0space\u00a0between\u00a0every\u00a0word\u00a0here.",
     "drawn_by": "tool"},
    {"file": "native_roles.png",
     # THE QUOTE IS AT THE FRONT OF THE FIELD, AND THAT IS THE WHOLE FIXTURE. csv enters quoted
     # mode only when a field BEGINS with a double quote, so a caption reading `The "reference"
     # arm ...` parses IDENTICALLY under QUOTE_MINIMAL and QUOTE_NONE - same rows, same captions,
     # same drawn_by - and pins nothing at all. This row starts with one, which is what makes the
     # reader's quoting keyword load-bearing: revert it and the marks are eaten.
     "caption": '"reference" arm subtracted, so a "positive" cell means the second arm here.',
     "drawn_by": "tool"},
]


print("the writer produces what the host's own reader parses")
tmp = Path(tempfile.mkdtemp(prefix="scp_captions_"))
try:
    figdir = tmp / "py" / "figures"
    p = C.write(figdir / C.NAME, ROWS)
    raw = p.read_bytes()
    ck("the file is UTF-8 and ends every row with LF alone",
       b"\r" not in raw and raw.endswith(b"\n"), repr(raw[:60]))
    lines = raw.decode("utf-8").split("\n")[:-1]
    ck("the header is the declared column list",
       lines[0] == "\t".join(C.COLUMNS), lines[0])
    ck("one line per legend, however the caption was wrapped",
       len(lines) == len(ROWS) + 1, f"{len(lines)} line(s) for {len(ROWS)} legend(s)")
    ck("and nothing is quoted, because nothing needs to be",
       all(l.count("\t") == len(C.COLUMNS) - 1 for l in lines),
       "a field carrying a tab would shift every column after it")
    got = C.read(figdir)
    # THE ROUND TRIP IS THE POINT. Four host read sites parse this file and none of them had a
    # writer to be checked against; a format nobody can write is a format nobody can test.
    ck("every legend comes back", len(got) == len(ROWS), f"{len(got)} of {len(ROWS)}")
    ck("keyed on the figure's basename, whatever the writer was handed",
       "native_flow.png" in got, str(sorted(got)[:3]))
    ck("a caption that contained a tab and a newline survives as one legend",
       got.get("native_flow.png", {}).get("caption", "").startswith("A legend written with a tab"),
       repr(got.get("native_flow.png", {}).get("caption", ""))[:90])
    ck("who drew it survives too",
       {k: v["drawn_by"] for k, v in got.items()}.get("native_scale.png") == "plugin")

    # THE DEFECT THIS FOUND. The file is written unquoted and was READ with csv's default
    # QUOTE_MINIMAL, so a field that merely STARTS with a double quote was treated as quoted.
    # A legend quoting a term lost its quote marks; a legend with an ODD number of them swallowed
    # the rest of the file into its own caption, and the surplus-field guard could not see it
    # because there was no surplus. Every legend after the first was gone, and the page rendered
    # exactly as a page with no legends does.
    ck("a legend that quotes a term keeps its quotation marks",
       '"reference"' in got.get("native_roles.png", {}).get("caption", ""),
       repr(got.get("native_roles.png", {}).get("caption", ""))[:90])
    odd = tmp / "odd"
    odd.mkdir()
    # THE UNBALANCED QUOTE OPENS THE FIELD. Mid-field it is an ordinary character to csv and this
    # fixture would parse the same way under either quoting - two rows, both drawn_by intact -
    # which is exactly how the first version of this check came to pass against the unfixed
    # reader. At the front it opens a quoted field that never closes, and QUOTE_MINIMAL swallows
    # the remaining line: 1 row, drawn_by=None, b.png gone.
    (odd / C.NAME).write_text(
        "\t".join(C.COLUMNS) + "\n"
        + "a.png\t\"Cross-talk is the tool's own word, and this quote is unbalanced\ttool\n"
        + "b.png\tA perfectly ordinary legend that says what the panel shows\tplugin\n",
        encoding="utf-8")
    back = C.read(odd)
    ck("one unbalanced quote does not swallow the legends after it",
       "b.png" in back, f"read {sorted(back)} - the rows after the unbalanced quote were lost")

    print("\nthe R writer the host ships produces THE SAME BYTES")
    rscript = shutil.which("Rscript")
    if not rscript:
        # NOT A DEFECT, AND NOT A PASS EITHER - said in the same words the rest of this tree
        # uses for a subject that is not installed. The host runs without R; this half of the
        # suite runs wherever R does.
        print("  not checked here - no Rscript on this machine, so the two writers were not "
              "compared. The Python half above still ran.")
    else:
        rdir = tmp / "r" / "figures"
        src = tmp / "captions_writer.R"
        src.write_text(C.r_source(), encoding="utf-8")

        def _u(s):
            """One field as the bytes it is, so nothing about R string literals is being tested."""
            b = str(s).encode("utf-8")
            return "u(c(" + ",".join(f"0x{x:02x}" for x in b) + "))"

        drv = ["u <- function(b) { s <- rawToChar(as.raw(b)); Encoding(s) <- \"UTF-8\"; s }",
               f"source({json.dumps(str(src))})",
               f"scp_captions_open({json.dumps(str(rdir))})"]
        for r in ROWS:
            drv.append(f"scp_legend({_u(r['file'])}, {_u(r['caption'])}, {_u(r['drawn_by'])})")
        dpath = tmp / "drive.R"
        dpath.write_text("\n".join(drv) + "\n", encoding="utf-8")
        run = subprocess.run([rscript, "--vanilla", str(dpath)],
                             capture_output=True, text=True, timeout=300)
        ck("the R writer runs", run.returncode == 0, (run.stderr or run.stdout)[-400:])
        r_raw = (rdir / C.NAME).read_bytes() if (rdir / C.NAME).is_file() else b""
        # BYTE FOR BYTE, NOT ROW FOR ROW. Two writers that agree after parsing can still disagree
        # on line endings, on encoding, and on which whitespace counts as whitespace - and the
        # host reader hides all three, so a comparison made after reading proves nothing about
        # the file a plugin actually leaves on disk.
        ck("the two writers produce the same file, byte for byte", r_raw == raw,
           f"python {len(raw)}B, R {len(r_raw)}B; first difference at "
           + str(next((i for i, (x, y) in enumerate(zip(raw, r_raw)) if x != y),
                          min(len(raw), len(r_raw)))))
        ck("and the host reads the R writer's file identically",
           C.read(rdir) == got, "the same rows must come back from either writer")

        print("\nthe draw wrapper is the whole draw site, not only the format")
        cap = subprocess.run([rscript, "--vanilla", "-e", "cat(capabilities('png'))"],
                             capture_output=True, text=True, timeout=120).stdout.strip()
        if cap.upper() != "TRUE":
            print("  not checked here - this R has no png device, so the draw wrapper was not "
                  "exercised. The writer half above still ran.")
        else:
            ddir = tmp / "drawn"
            drw = [f"source({json.dumps(str(src))})",
                   f"scp_captions_open({json.dumps(str(ddir))})",
                   # a panel that draws, with a real legend
                   f"scp_draw(file.path({json.dumps(str(ddir))}, 'native_ok.png'), plot(1:10),"
                   f" legend = 'A panel that drew, with a legend long enough to be one.',"
                   f" render = 'force')",
                   # a panel whose plotting expression dies
                   f"scp_draw(file.path({json.dumps(str(ddir))}, 'native_dead.png'),"
                   f" stop('the tool refused'),"
                   f" legend = 'A legend for a panel that never got drawn at all.')",
                   # a panel whose legend is a label rather than a legend
                   f"scp_draw(file.path({json.dumps(str(ddir))}, 'native_label.png'),"
                   f" plot(1:3), legend = 'interaction flow', render = 'force')",
                   # a panel claiming a provenance that is not one of the two
                   f"scp_draw(file.path({json.dumps(str(ddir))}, 'native_who.png'),"
                   f" plot(1:3), legend = 'A legend long enough to count as a real legend.',"
                   f" drawn_by = 'somebody', render = 'force')",
                   "scp_draw_tally()"]
            dp2 = tmp / "draw.R"
            dp2.write_text("\n".join(drw) + "\n", encoding="utf-8")
            r2 = subprocess.run([rscript, "--vanilla", str(dp2)],
                                capture_output=True, text=True, timeout=300)
            ck("the draw wrapper runs", r2.returncode == 0, (r2.stderr or r2.stdout)[-400:])
            legends = C.read(ddir)
            ck("a panel that drew gets its legend", "native_ok.png" in legends,
               str(sorted(legends)))
            ck("and the file it drew is on disk and not empty",
               (ddir / "native_ok.png").is_file() and (ddir / "native_ok.png").stat().st_size > 0)
            # ONE FAILING PLOT COSTS ITS OWN FILE. The device creates the PNG when it OPENS, so a
            # plot that died leaves a zero-byte image behind - which the host would place on a
            # page, and a reader would meet as a broken image with a legend underneath it.
            ck("a panel whose expression died leaves no file",
               not (ddir / "native_dead.png").exists())
            ck("and no legend for a panel that does not exist",
               "native_dead.png" not in legends, str(sorted(legends)))
            # A LABEL IN THE PLACE A DESCRIPTION GOES READS AS THE DESCRIPTION. The panel is
            # kept - it is already drawn and it is worth showing - and the page says, in the
            # reader's own words, that nobody wrote a legend for it.
            ck("a four-word label is refused, and the panel is still drawn",
               (ddir / "native_label.png").is_file() and "native_label.png" not in legends)
            ck("and the refusal is said out loud", "REFUSED" in (r2.stdout + r2.stderr),
               "a legend dropped in silence is indistinguishable from one never written")
            ck("a provenance outside the two valid answers is refused",
               "native_who.png" not in legends,
               "a panel claiming an unknown origin would be reported as though it were known")

            print("\nand the legend is filed beside the PANEL, not beside the open() call")
            # THE DEFECT THIS FOUND, and the section above is structurally unable to see it: it
            # only ever draws into the one directory it opened. `scp_draw` called `scp_legend`
            # with no `dir`, so every row fell back to scp_captions$dir. Open once and draw a
            # panel per unit into its own subdirectory - the normal shape for this host - and all
            # of them landed in ONE shared file. The host's reader searches one level up, finds
            # it, and `setdefault` keys on the BASENAME, so two units that both draw `roles.png`
            # collide and the second is served the first one's sentence. MEASURED with real
            # Rscript before the fix:
            #     unitA -> "Unit A: senders on the x axis, ..."
            #     unitB -> "Unit A: senders on the x axis, ..."   <- unitB got unitA's legend
            # That is a caption asserting a provenance it cannot know, which this module's own
            # header calls WORSE than no caption at all.
            udir = tmp / "units"
            uleg = {"unitA": "Unit A: senders on the x axis and receivers on the y axis.",
                    "unitB": "Unit B: a different unit, and a legend that is only its own."}
            drw2 = [f"source({json.dumps(str(src))})",
                    f"scp_captions_open({json.dumps(str(udir))})"]
            for _u_name, _u_txt in uleg.items():
                drw2.append(
                    f"scp_draw(file.path({json.dumps(str(udir / _u_name))}, 'roles.png'),"
                    f" plot(1:10), legend = {json.dumps(_u_txt)}, render = 'force')")
            # AND A PANEL DRAWN OUTSIDE THE OPENED TREE ALTOGETHER, which did not borrow a
            # neighbour's legend - it lost its own. The row was filed where the reader never
            # looks, and read() came back {} for a panel whose legend had been written.
            outside = tmp / "outside"
            _o_txt = "Drawn outside the opened directory, and still carrying its own legend."
            drw2.append(
                f"scp_draw(file.path({json.dumps(str(outside))}, 'roles.png'), plot(1:10),"
                f" legend = {json.dumps(_o_txt)}, render = 'force')")
            dp3 = tmp / "units.R"
            dp3.write_text("\n".join(drw2) + "\n", encoding="utf-8")
            r3 = subprocess.run([rscript, "--vanilla", str(dp3)],
                                capture_output=True, text=True, timeout=300)
            ck("the per-unit draw runs", r3.returncode == 0, (r3.stderr or r3.stdout)[-400:])
            per = {u: C.read(udir / u) for u in uleg}
            ck("two units that both draw roles.png each get their OWN legend",
               all(per[u].get("roles.png", {}).get("caption") == t for u, t in uleg.items()),
               "; ".join(f"{u} -> {per[u].get('roles.png', {}).get('caption')!r}" for u in uleg))
            ck("the row is written in the unit's own directory, beside the panel",
               all((udir / u / C.NAME).is_file() for u in uleg),
               f"{sorted(p.name for p in udir.rglob('*'))}")
            # THE OPENED DIRECTORY IS NOT WHERE THESE ROWS GO. Header only: a shared file with
            # rows in it is the bug, and it renders as a page rather than as an error.
            ck("and not pooled into the directory that was opened", C.read(udir) == {},
               f"{C.read(udir)} - one shared file is what let one unit read another's legend")
            ck("a panel drawn outside the opened tree keeps its legend rather than losing it",
               C.read(outside).get("roles.png", {}).get("caption") == _o_txt,
               f"read {C.read(outside)}")

            # ONE DIRECTORY, TWO SPELLINGS, ONE FILE - a hazard that filing beside the panel
            # CREATES rather than one it inherits. The per-directory file is now started by the
            # first legend that lands there, so "which directories has this process already
            # started" is consulted for every panel; and a directory truncates when it looks new.
            # Keyed on the raw string, "." and the absolute path of the same directory are two
            # directories. MEASURED with the key unnormalised: the bare-name draw truncated the
            # file and the absolute draw's legend was gone - two panels on disk and one legend.
            same = tmp / "same"
            (same / "figs").mkdir(parents=True)
            spell = [f"source({json.dumps(str(src))})",
                     f"scp_captions_open({json.dumps(str(same / 'figs'))})",
                     f"scp_draw({json.dumps(str(same / 'figs' / 'abs.png'))}, plot(1:10),"
                     f" legend = 'The first panel, whose path was spelled absolutely.',"
                     f" render = 'force')",
                     f"setwd({json.dumps(str(same / 'figs'))})",
                     "scp_draw('bare.png', plot(1:10),"
                     " legend = 'The second panel, spelled as a bare file name instead.',"
                     " render = 'force')"]
            dp4 = tmp / "spelling.R"
            dp4.write_text("\n".join(spell) + "\n", encoding="utf-8")
            r4 = subprocess.run([rscript, "--vanilla", str(dp4)],
                                capture_output=True, text=True, timeout=300)
            ck("the two-spelling draw runs", r4.returncode == 0, (r4.stderr or r4.stdout)[-400:])
            spelled = C.read(same / "figs")
            ck("one directory spelled two ways does not truncate away its own first legend",
               sorted(spelled) == ["abs.png", "bare.png"],
               f"read {sorted(spelled)} for 2 panels - the second spelling started the file again")

            # AND AN EXPLICIT open() ON A DIRECTORY THIS PROCESS HAS ALREADY STARTED MUST
            # TRUNCATE IT. Three branches decide whether the file is started again, and each is a
            # different defect when it is wrong: a directory this process has never seen truncates
            # (or a second run appends to the first run's rows); a directory already started does
            # NOT (or a run filing legends beside its panels erases the rows it wrote a moment
            # ago); and an explicit `open` on an already-started directory truncates AGAIN,
            # because `open` is how a script says "these are THIS run's legends". Two of the three
            # were pinned above and the third was only ASSERTED, by the comment on
            # `scp_captions_open` - and a re-verifier deleted the two lines that drop the
            # directory from the started set with this whole suite still green.
            #
            # MEASURED with real Rscript, in ONE process, opening the same directory twice and
            # drawing roles.png after each open:
            #     with the setdiff:      1 row  - the reader serves "CURRENT: ..."
            #     with the setdiff cut:  2 rows - the reader serves "STALE: ..."
            # which is precisely the failure `scp_captions_ensure`'s own comment names: `read`
            # keys on the basename with `setdefault`, so it keeps the FIRST row for a file name
            # and serves the superseded legend forever. The panel on disk is this run's and the
            # sentence under it is the last run's - a caption asserting something it cannot know,
            # on a page that renders exactly as a correct one does.
            redir = tmp / "reopen"
            _stale = "STALE: the draft legend, written on this script's first pass."
            _fresh = "CURRENT: the corrected legend, written after the panel was redrawn."
            reo = [f"source({json.dumps(str(src))})",
                   f"scp_captions_open({json.dumps(str(redir))})",
                   f"scp_draw(file.path({json.dumps(str(redir))}, 'roles.png'), plot(1:10),"
                   f" legend = {json.dumps(_stale)}, render = 'force')",
                   # THE SECOND OPEN IS THE WHOLE FIXTURE, and it must be in the SAME process:
                   # the started set lives in `scp_captions`, so two Rscript invocations would
                   # start from an empty set and pass whatever the branch does.
                   f"scp_captions_open({json.dumps(str(redir))})",
                   f"scp_draw(file.path({json.dumps(str(redir))}, 'roles.png'), plot(1:10),"
                   f" legend = {json.dumps(_fresh)}, render = 'force')"]
            dp5 = tmp / "reopen.R"
            dp5.write_text("\n".join(reo) + "\n", encoding="utf-8")
            r5 = subprocess.run([rscript, "--vanilla", str(dp5)],
                                capture_output=True, text=True, timeout=300)
            ck("the reopened-directory draw runs", r5.returncode == 0,
               (r5.stderr or r5.stdout)[-400:])
            _txt = ((redir / C.NAME).read_text(encoding="utf-8")
                    if (redir / C.NAME).is_file() else "")
            # THE ROWS ARE COUNTED ON DISK, not through the reader, because the reader HIDES this
            # defect by design: two rows for one panel come back as one legend either way, and
            # only which of the two it is says whether the file was truncated.
            _rows = [l for l in _txt.split("\n")[1:] if l]
            ck("an explicit open on an already-started directory truncates it, once, again",
               len(_rows) == 1,
               f"{len(_rows)} row(s) on disk for one panel - this run appended to the previous "
               "run's rows instead of starting the file")
            ck("so a redrawn panel is served this run's legend and not the superseded draft",
               C.read(redir).get("roles.png", {}).get("caption") == _fresh,
               f"served {C.read(redir).get('roles.png', {}).get('caption')!r} - the reader keeps "
               "the FIRST row for a file name")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nthe R is generated from the host's constants, not written beside them")
rsrc = C.r_source()
ck("no placeholder survived the substitution", "@CAPTIONS" not in rsrc,
   rsrc[rsrc.find("@CAPTIONS"):][:40])
ck("the file name comes from the host", f'"{C.NAME}"' in rsrc)
ck("the columns come from the host", all(f'"{c}"' in rsrc for c in C.COLUMNS))
ck("the two provenances come from the host", all(f'"{b}"' in rsrc for b in C.DRAWN_BY))
ck("and the word bar comes from the host", f"<- {C.MIN_LEGEND_WORDS}" in rsrc)
# ONE DEFINITION, WHICH IS THE WHOLE POINT. The three copies inside one plugin are what this
# replaces; a host that shipped two ways to write a row would have started the same drift again.
ck("exactly one function writes a row", rsrc.count("scp_caption_line <- function") == 1)
ck("exactly one function opens the file", rsrc.count("scp_captions_open <- function") == 1)
ck("exactly one draw wrapper", rsrc.count("scp_draw <- function") == 1)
# AND IT IS COUNTABLE. Every name here is the host's, so how many panels a plugin put through the
# host's wrapper is `grep -c 'scp_draw('` over that plugin - a number a maker can take - rather
# than an argument about which of a plugin's local helpers is a copy of which.
import re as _re                                                          # noqa: E402

_defs = _re.findall(r"^([A-Za-z_.][\w.]*)\s*<-\s*function\s*\(", rsrc, _re.M)
ck("everything the host defines is named from the host",
   bool(_defs) and all(d.startswith("scp_") for d in _defs), str(_defs))
ck("and nothing is defined twice", len(_defs) == len(set(_defs)), str(_defs))
_call = _re.compile(r"(?<![\w.])scp_draw\s*\(")
ck("the call-site count is a grep",
   len(_call.findall("scp_draw(a, plot(1))\nscp_draw(b, plot(2))")) == 2)
# THE HOST NEVER CALLS ITS OWN WRAPPER, so a plugin's count is its panels and does not start at
# one. The preamble is sourced, not run.
ck("and the preamble is not itself a call site", not _call.search(rsrc),
   "every plugin's panel count would be off by the host's own calls")
# THE DEVICE IS THE WRAPPER'S JOB, or the caller writes the half that the copies each got wrong.
for _bit, _why in (("dev.cur()", "the wrapper must close the device it opened, by number"),
                   ("dev.list()", "and only if it is still open"),
                   ("unlink(path)", "a failed panel must not be left on disk"),
                   ("render", "one wrapper with an argument, not two that can be half-copied")):
    ck(f"the wrapper carries {_bit}", _bit in rsrc, _why)

print("\nand it reaches a plugin without the plugin importing the host")
# THE EXISTING CHANNEL, NOT A SECOND ONE. `figure_context` is the block the host already computes
# once and puts in every plugin's in.json; the writer rides in it rather than inventing a route.
empty = FC.build()
ck("the block is built even when the host knows no labels", bool(empty),
   "a run with no label totals must still hand over the writer")
ck("and it carries the writer", (empty.get("captions") or {}).get("r_source", "") == rsrc)
ck("with the format beside it, for a plugin that writes its own",
   (empty.get("captions") or {}).get("columns") == list(C.COLUMNS))
with tempfile.TemporaryDirectory() as td:
    inj = Path(td) / "in.json"
    MF.write_input(inj, h5ad=str(Path(td) / "x.h5ad"), out_dir=Path(td), keys={},
                   figure_context=FC.build(labels=["one", "two"], unit="u"))
    pay = json.loads(inj.read_text(encoding="utf-8"))
    ck("in.json carries it verbatim",
       pay.get("figure_context", {}).get("captions", {}).get("r_source") == rsrc,
       "a plugin reads its in.json and nothing else")
    from scprofile.plugin import Context                                  # noqa: E402
    _c = Context(None, keys={}, out=td, figure_context=pay["figure_context"])
    ck("and a plugin reaches it through the context it is handed",
       (_c.figure_context.get("captions") or {}).get("r_source") == rsrc)

    # THE WORD BAR IS ONE NUMBER, AND THIS IS THE THIRD PARTY THAT APPLIES IT. `MIN_LEGEND_WORDS`
    # is documented as being applied by `check`, by `Context.emit_figure` and by the generated R;
    # `emit_figure` in fact carried its own hardcoded `5`, so the docstring was a claim nothing
    # held up and raising the bar in one place would have moved two of the three. Pinned by
    # MOVING the constant rather than by grepping for a digit: a copy of the number cannot follow
    # it, so this fails the moment the literal comes back.
    import matplotlib                                                     # noqa: E402
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt                                      # noqa: E402

    def _emit_words(n, bar):
        """Emit one panel whose legend is `n` words, with the host's bar set to `bar`."""
        was = C.MIN_LEGEND_WORDS
        C.MIN_LEGEND_WORDS = bar
        try:
            c = Context(None, keys={}, out=td, figure_context=pay["figure_context"])
            f = _plt.figure()
            c.emit_figure(f"bar_{n}_{bar}", f, caption=" ".join(["word"] * n))
            return f"bar_{n}_{bar}" in c.unlegended
        finally:
            C.MIN_LEGEND_WORDS = was
            _plt.close("all")

    ck("a legend under the host's bar is reported unlegended when a plugin emits it",
       _emit_words(C.MIN_LEGEND_WORDS - 1, C.MIN_LEGEND_WORDS),
       "a label passed here would be refused silently at the far end instead")
    ck("and emit_figure reads the bar from the host rather than keeping its own copy",
       _emit_words(C.MIN_LEGEND_WORDS + 2, C.MIN_LEGEND_WORDS + 4),
       f"a legend of {C.MIN_LEGEND_WORDS + 2} words passed a bar of "
       f"{C.MIN_LEGEND_WORDS + 4}: the number is hardcoded here, so the docstring on "
       "MIN_LEGEND_WORDS names a party that does not apply it")

# NOTHING HERE MAY ASSUME ONE TOOL. The writer is the host's, so it must be usable by a plugin
# wrapping something with no interactions, no populations and no arms.
_low = rsrc.lower()
for _word in ("cell" + "chat", "path" + "way", "lig" + "and", "sender", "receiver"):
    ck(f"the R names nothing method-specific ({_word[:4]}...)", _word not in _low)

if FAILURES:
    print("\nFAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("\nok - one legend format, two writers that agree byte for byte, and a plugin can have "
      "either without importing the host")
