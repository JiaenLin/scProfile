"""A figure's legend is written by whatever drew it, and says truthfully who that was.

THE DEFECT. The host names a panel by inverting the plugin's declaration - which file came from
which function - and with nothing better used the FILENAME as the caption:

    "interaction flow  age response by diet, drawn by the tool itself."

That is a filename. It says nothing about the axes, the colour, the dashed line, or that the panel
is a difference of two differences with no test attached. And the caption is what travels into the
written section, so everything the title says is lost the moment a reader meets the panel anywhere
else.

AND THE LAST CLAUSE WAS FALSE. "Drawn by the tool itself" is wrong for a panel the PLUGIN drew
from the tool's numbers - a second scale, a derived matrix - and that distinction is exactly what
the upstream-plot accounting exists to protect. A caption asserting it wrongly undoes that
accounting at the last step, where nobody checks.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import captions as C                                       # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


# 1. the format refuses what is not a legend
for bad, why in ((
        [{"file": "a.png", "caption": "flow age diet", "drawn_by": "tool"}],
        "a three-word label was accepted as a legend"), (
        [{"file": "a.png", "caption": "a legend long enough to say something real", "drawn_by": "x"}],
        "a provenance outside the two valid answers was accepted"), (
        [{"file": "", "caption": "a legend long enough to say something real", "drawn_by": "tool"}],
        "a row with no file was accepted")):
    try:
        C.check(bad)
        FAILURES.append(why)
    except C.BadCaption:
        pass

# 2. provenance is stated truthfully, or not at all
check("netVisual_heatmap()" in C.provenance("tool", "netVisual_heatmap"),
      "a tool-drawn panel does not name the function that drew it")
check("not by rankNet() itself" in C.provenance("plugin", "rankNet"),
      "a plugin-drawn panel is not distinguished from one the tool drew")
check(C.provenance("", "x") == "",
      "an unknown provenance is GUESSED rather than omitted - a caption that asserts the wrong "
      "origin is worse than one that omits it, because the first is believed")

# 3. THE HOST PREFERS A WRITTEN LEGEND - CHECKED BY CALLING IT, not by finding the call in the
#    source. The first version of this looked for `_CAP.read(` in report.py and passed happily
#    with the branch that uses it disabled, which is the failure mode it was written to prevent.
import shutil                                                             # noqa: E402
import tempfile                                                           # noqa: E402

from scprofile import report as RPT                                       # noqa: E402

_tmp = Path(tempfile.mkdtemp(prefix="scp_legend_"))
try:
    fd = _tmp / "run" / "kernels" / "p" / "compare" / "c" / "figures"
    fd.mkdir(parents=True)
    (fd / "nativecmp_thing_a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (fd / "nativecmp_thing_b.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    C.write(fd / C.NAME, [{"file": "nativecmp_thing_a.png",
                           "caption": "A real legend saying what this panel shows and how.",
                           "drawn_by": "plugin"}])
    decl = {"someFn": {"use": "figures/nativecmp_thing_<x>.png"}}
    got = RPT._native_panels(fd, "lab", decl, _tmp / "run", "lo", "hi")
    caps = {r[0]: (" ".join(r[2]) if isinstance(r[2], (list, tuple)) else str(r[2])) for r in got}
    a = next((v for k, v in caps.items() if k.endswith("thing_a")), "")
    b = next((v for k, v in caps.items() if k.endswith("thing_b")), "")
    check("A real legend saying what this panel shows" in a,
          f"the written legend did not reach the caption; got {a[:90]!r}")
    check("not by someFn() itself" in a,
          f"a plugin-drawn panel is reported as the tool's own work; got {a[:120]!r}")
    check("thing b" in b,
          f"a panel with NO written legend lost its fallback, so an undescribed plugin regresses; "
          f"got {b[:90]!r}")
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

# 4. the plugin writes them, for every panel it draws itself
ck = (ROOT / "kernels" / "cellchat.py").read_text()
check(ck.count(".write_captions()") >= 1, "the plugin never writes its legends")
check(ck.count(".legend(basename(path)") >= 6,
      f"only {ck.count('.legend(basename(path)')} of the plot wrappers record a legend")

# EVERY PANEL THE PLUGIN DRAWS ITSELF MUST SAY SO. `by = \"plugin\"` is the claim that this is
# the tool's NUMBERS and not its encoding; a panel we drew that omits it is reported as the
# tool's own work.
# Four panel families are drawn by the plugin from the tool's numbers today: the per-observation
# bars, the interaction scatter on each scale, and the interaction matrix. The raw bars are
# correctly NOT among them - they are the tool's own function, unmodified - which is the
# distinction this count exists to keep.
own = len(re.findall(r'by = "plugin"', ck))
check(own >= 4, f"only {own} plugin-drawn panel family(ies) declare themselves as such; a panel "
                f"we drew that omits it is reported to a reader as the tool's own work")

# and a diverging panel must key its colours - the defect that shipped three times
for must in ("RED means", "BLUE means", "WHITE means"):
    check(must in ck, f"an interaction legend does not say what {must.split()[0]} means")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - legends are written where panels are drawn, and provenance is not guessed")
