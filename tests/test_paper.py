"""The paper test's own ledger: can a claim be recorded, defended, and invalidated by a redraw?

Every check here is a way the mechanism could become a formality. The one that matters most is
the last: a claim is bound to the figures it was read off, so redrawing one of them must take
the claim back to undefended. Without that property this is a checklist, and a checklist is
satisfied by reading it.

Run: python tests/test_paper.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import paper as PA                                               # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def refuses(fn, *a, **k):
    try:
        fn(*a, **k)
        return False
    except PA.Refused:
        return True


root = Path(tempfile.mkdtemp())
figs = root / "kernels" / "k" / "figures"
figs.mkdir(parents=True)
(figs / "a.png").write_text("A")
(figs / "b.png").write_text("B")
A, B = "kernels/k/figures/a.png", "kernels/k/figures/b.png"
GOOD = "The share of one pathway rises in one arm and falls in the other, by about nine points"

print("an empty ledger says so, rather than passing")
ck("no claims reads as NOT RUN, not as clean", "NO CLAIMS RECORDED" in PA.summarise(root))
ck("and nothing is outstanding only because nothing exists", PA.outstanding(root) == [])

print("\na claim must be checkable and must cite something")
ck("a claim too short to be checkable is refused", refuses(PA.claim, root, "diet matters", [A]))
ck("a claim citing no figure is refused", refuses(PA.claim, root, GOOD, []))
ck("a claim citing a figure not in the run is refused",
   refuses(PA.claim, root, GOOD, ["kernels/k/figures/nope.png"]))
rec = PA.claim(root, GOOD, [A, B], author="t")
ck("a real claim records the digest of every figure it cites",
   len(rec["cites"]) == 2 and all(len(v) == 64 for v in rec["cites"].values()))

print("\nand it starts UNDEFENDED, which is the state that has to be visible")
cid = rec["id"]
ck("a new claim is unreviewed", PA.status(root)[0][1] == PA.UNREVIEWED)
ck("and appears in the outstanding set", [c for c, _ in PA.outstanding(root)] == [cid])

print("\na round has to say what happened")
ck("an unknown verdict is refused", refuses(PA.review, root, cid, "fine", "a real reason here"))
ck("a verdict with no reasoning is refused",
   refuses(PA.review, root, cid, PA.STANDING, "ok"))
ck("a round against an unrecorded claim is refused",
   refuses(PA.review, root, "0" * 12, PA.STANDING, "checked against its own denominator"))
PA.review(root, cid, PA.STANDING, "checked against its own denominator and it held", reviewer="r")
ck("a defended claim leaves the outstanding set", not PA.outstanding(root))
ck("and its state is the verdict", PA.status(root)[0][1] == PA.STANDING)

print("\nthe later verdict wins, because a claim can die on the second round")
PA.review(root, cid, PA.WITHDRAWN, "the ranking was not stable on a second scale")
ck("the newest verdict is the claim's state", PA.status(root)[0][1] == PA.WITHDRAWN)
ck("and the round count is kept", PA.status(root)[0][2] == 2)

print("\nTHE PROPERTY THAT MAKES IT A GATE: a redraw invalidates the claim")
# A claim is a statement ABOUT A PICTURE. Change the picture and the statement has not merely
# aged - the thing it described is gone, and it has to be defended again. Same mechanism as the
# figure-review ledger, for the same reason.
(figs / A.split("/")[-1]).write_text("A CHANGED")
ck("redrawing a cited figure takes the claim to STALE", PA.status(root)[0][1] == PA.STALE)
ck("even though it had a verdict", PA.status(root)[0][2] == 2)
ck("and it is outstanding again", [c for c, _ in PA.outstanding(root)] == [cid])

print("\nand a loop that only ever confirms is named as one")
root2 = Path(tempfile.mkdtemp())
f2 = root2 / "figures"
f2.mkdir(parents=True)
(f2 / "x.png").write_text("X")
r2 = PA.claim(root2, GOOD, ["figures/x.png"])
PA.review(root2, r2["id"], PA.STANDING, "put to a reviewer and it held up")
ck("all-standing is flagged rather than reported as success",
   "EVERY CLAIM SURVIVED UNCHANGED" in PA.summarise(root2))

print("\nthe limits are stated in the tool, not only in the docs")
ck("the narrow list is non-empty and specific", len(PA.NARROW) >= 6)
ck("every gap is a sentence, not a word", all(len(g.split()) >= 8 for g in PA.NARROW))
_doc = (Path(__file__).resolve().parents[1] / "docs" / "PAPER_TEST.md")
ck("and there is a document to point at", _doc.is_file(), str(_doc))

print("\n" + ("the paper test holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)


def test_a_plugin_section_never_touches_the_run_root():
    """One manuscript per plugin means its ledger, draft and page live under the plugin.

    Threading a `plugin` argument through by hand left three `_append` call sites unthreaded, so
    a claim was written to the RUN ROOT ledger while `review` read the plugin's - and the review
    then refused a claim that had just been recorded. The failure was silent until an end-to-end
    call, because each function worked and only their pairing was wrong.
    """
    import tempfile
    from pathlib import Path

    from scprofile import paper as P

    d = Path(tempfile.mkdtemp())
    figs = d / "kernels" / "cellchat" / "figures"
    figs.mkdir(parents=True)
    (figs / "F1.png").write_bytes(b"x" * 100)

    rec = P.claim(d, "A claim long enough to be checkable about the figure it cites.",
                  ["kernels/cellchat/figures/F1.png"], plugin="cellchat")
    P.review(d, rec["id"], "standing", "a reviewer put it and it held", plugin="cellchat")
    P.write_draft(d, " ".join(["w"] * 400), plugin="cellchat")

    plug = d / "kernels" / "cellchat"
    assert (plug / "PAPER_CLAIMS.cellchat.jsonl").is_file(), "the claim did not reach the plugin"
    assert (plug / "PAPER.cellchat.md").is_file(), "the draft did not reach the plugin"
    assert not (d / "PAPER_CLAIMS.jsonl").exists(), (
        "a per-plugin claim was written to the run root, where its own review cannot find it")
    assert not (d / "PAPER.md").exists(), "a per-plugin draft was written to the run root"

    rows = P.status(d, "cellchat")
    assert rows and rows[0][1] != P.UNREVIEWED, "the review did not attach to the claim"


def test_the_rendered_page_actually_shows_its_figures():
    """A figure panel with no figures is the one thing it must not be.

    The href was hard-coded as "../" + path, correct while every page sat in `<run>/report/`. A
    plugin's page sits three levels down, so every `<img>` pointed at nothing and the section
    rendered with its claims, its verdicts and no figures at all - and the page still looked
    plausible, because the prose and the claims table were there.
    """
    import os
    import re
    import tempfile
    from pathlib import Path

    from scprofile import paper as P

    d = Path(tempfile.mkdtemp())
    figs = d / "kernels" / "cellchat" / "figures"
    figs.mkdir(parents=True)
    (figs / "F1.png").write_bytes(b"x" * 100)
    rec = P.claim(d, "A claim long enough to be checkable about the figure it cites here.",
                  ["kernels/cellchat/figures/F1.png"], plugin="cellchat")
    P.review(d, rec["id"], "standing", "a reviewer put it and it held", plugin="cellchat")
    P.write_draft(d, " ".join(["w"] * 400), plugin="cellchat")
    page = P.render(d, plugin="cellchat")

    srcs = re.findall(r'<img src="([^"]+)"', page.read_text())
    assert srcs, "the page cites a figure and embeds none"
    for s in srcs:
        target = os.path.normpath(os.path.join(page.parent, s))
        assert os.path.isfile(target), f"<img src={s!r}> resolves to nothing from {page.parent}"
