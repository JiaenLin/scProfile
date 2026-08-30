"""The written section must land where the plugin's other pages are, and be linked from them.

`page_name` gives the file the name `<plugin>_paper.html` for a stated reason: so it sorts beside
`<plugin>.html`, `<plugin>_by_arm.html` and `<plugin>_by_sample.html`. The directory defeated the
name - the page was written to `<run>/kernels/<plugin>/report/`, where none of those three is - so
the run index could not link it and a reader following the report would never meet the section
written off its own panels.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import kernels as K, paper as PA                           # noqa: E402

FAILURES = []
out = Path("/tmp/_wherever")

want = K.run_report(out)
got = PA._report_dir(out, "someplugin")
if Path(got) != Path(want):
    FAILURES.append(f"the section renders to {got}, not to {want} where its siblings are")

name = PA.page_name("someplugin")
if name != "someplugin_paper.html":
    FAILURES.append(f"unexpected page name {name!r}")

# the SOURCES stay with the method, which is a different question and must not have moved
root = PA._root(out, "someplugin")
if Path(root) == Path(out):
    FAILURES.append("the section's sources moved to the run root; they belong with the plugin")

# and the plugin page must be able to link it
src = (ROOT / "scprofile" / "report.py").read_text()
if "_paper.html" not in src:
    FAILURES.append("report.py never links the written section, so nothing leads a reader to it")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ok: the section renders beside its sibling pages, keeps its sources with the plugin, "
      "and is linked from the plugin page")
