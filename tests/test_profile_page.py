"""The per-unit profile page is WRITTEN, and it does not duplicate the appendix.

A GREEN SUITE WHILE THE PAGE DID NOT EXIST. Every check of this feature passed - the declaration
validated, the figures were drawn, the ids matched - and no run ever produced the page, because
the code that writes it referred to a name bound ninety lines further down the same function.
A static scan sees that name bound in the function and says nothing; the call raised at run time
inside a caller that catches, so nothing said anything at all.

That is the shape this repository keeps meeting: a test that proves the parts are well-formed
while the OUTPUT is absent. So this test calls the reporter and looks for the file.

It also checks the second defect the same run exposed. The profile panels are drawn for every
unit, which brought the per-sample appendix back carrying exactly those panels - the page the
profile page replaces, rebuilt out of its own contents. A figure belongs on one page.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import report as R                                         # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


NAME = "demo"
SPEC = {"figures": [
    {"id": "P_rank", "shows": "result", "profile": True,
     "question": "what is active here?"},
    {"id": "X_detail", "shows": "result", "question": "everything else"},
]}

tmp = Path(tempfile.mkdtemp(prefix="scp_profile_"))
try:
    out = tmp / "run"
    figs = []
    for unit in ("armA", "s1", "s2"):
        d = out / "kernels" / NAME / unit / "figures"
        d.mkdir(parents=True)
        for fid in ("P_rank", "X_detail"):
            (d / f"{fid}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            figs.append({"id": fid, "unit": unit,
                         "path": f"kernels/{NAME}/{unit}/figures/{fid}.png",
                         "caption": f"[{unit}] {fid} drawn for this unit"})
    payload = {"kernel": NAME, "status": "ok", "figures": figs, "caveats": [], "absent": []}
    payload_all = {"unit_axis": {"armA": "group", "s1": "sample", "s2": "sample"},
                   "unit_members": {"armA": ["s1", "s2"]},
                   "design": {"s1": {"g": "a"}, "s2": {"g": "b"}}}
    R.write_kernel(out, NAME, payload, [], spec=SPEC, payload_all=payload_all)

    page = out / "report" / f"{NAME}_profile.html"
    check(page.is_file(), "the profile page was not written at all - the feature exists in the "
                          "declaration, the figures are drawn, and no run produces the page")
    if page.is_file():
        html = page.read_text(encoding="utf-8")
        # 1. every unit is on it, arms and samples alike
        for unit in ("armA", "s1", "s2"):
            check(unit in html, f"{unit} is missing from the profile page, so it describes some "
                                f"units and not others")
        # 2. only the declared profile figures
        check("P_rank" in html, "the declared profile figure is not on the profile page")
        check("X_detail" not in html,
              "a figure NOT declared as profile is on the profile page, so the page is the "
              "appendix again under a new name")
        # 3. it says what an arm is, because the geometry does not
        check("pooled" in html.lower(),
              "the page does not say that an arm is one fit on pooled cells and a sample is its "
              "own, so a reader takes the arm panel for the sum of the sample panels")

    # 4. the appendix does not carry what the profile page carries
    app = out / "report" / f"{NAME}_by_sample.html"
    if app.is_file():
        a = app.read_text(encoding="utf-8")
        check("P_rank" not in a,
              "the per-sample appendix repeats the profile panels, so the page the profile page "
              "replaces is rebuilt out of its own contents")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - the profile page exists, covers every unit, and does not duplicate the appendix")
