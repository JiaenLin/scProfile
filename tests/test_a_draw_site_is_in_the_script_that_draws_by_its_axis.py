"""An entry's `axis` is one the script holding its draw site draws by, said before any job
(harness ADR-0026, the open items: the static half of K-o).

RUN A MOVED A PAIR SCATTER TO THE GROUP AXIS AND NOTHING MOVED: the plan counted it per arm,
every local gate was green, and the run drew it per contrast as before - its `.draw("id")` site
is in the compare script, which draws by contrast whatever the entry says. The companion now
refuses such a site at run time (K-o); this is the reading before the run. The plugin's Python
says which R string each phase launches (`ctx.rscript(_R_RUN, ...)` inside `run(ctx)`,
`_R_COMPARE` and `_R_COHORT` inside `compare(ctx)`), the R strings say where each `.draw` site
is, and the tool's own convention says which axes each phase draws by: `unit`, `sample`, `group`
per unit; `contrast`, `interaction`, `cohort` per comparison. The validator refuses the
mismatch by name and the maker's first follower prints it.

Run: python tests/test_a_draw_site_is_in_the_script_that_draws_by_its_axis.py
"""
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import declare as D                                              # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


SRC = textwrap.dedent('''\
    PLUGIN = {"name": "demo", "report": {"figures": [
        {"id": "native_ring", "axis": "sample", "legend": "a"},
        {"id": "nativecmp_pair", "axis": "contrast", "legend": "b"},
        {"id": "nativecmp_flow", "axis": "interaction", "legend": "c"},
        {"id": "estimation", "generated": False, "legend": "d"},
        {"id": "host_panel", "axis": "cohort", "legend": "e"},
    ]}}
    _R_DB = """
    library(CellChat)
    db <- 1
    """
    _R_RUN = """
    library(CellChat)
    x <- 1
    .draw("native_ring")
    """
    _R_COMPARE = """
    library(CellChat)
    y <- 2
    .draw("nativecmp_pair")
    """
    _R_CAP = """
    cap <- 1
    """
    _R_COHORT = """
    library(CellChat)
    z <- 3
    __R_CAP__
    .draw('nativecmp_flow')
    """.replace("__R_CAP__", _R_CAP)
    def run(ctx):
        ctx.rscript(_R_DB, [])
        ctx.rscript(_R_RUN, [])
    def compare(ctx):
        ctx.rscript(_R_COHORT, [])
        ctx.rscript(_R_COMPARE, [])
    ''')


def findings(src):
    import ast
    spec = ast.literal_eval(ast.parse(src).body[0].value)
    return D.draw_site_phase(src, spec)


print("the phases, the sites, and the axes they draw by")
ck("a plan whose every site is in the script of its axis passes", findings(SRC) == [],
   str(findings(SRC)))
moved = SRC.replace('"id": "nativecmp_pair", "axis": "contrast"', '"id": "nativecmp_pair", "axis": "group"')
f = findings(moved)
ck("a compare-script site under a unit axis is an ERROR, by id, script and phase",
   len(f) == 1 and f[0][0] == "ERROR" and "nativecmp_pair" in f[0][1] and "_R_COMPARE" in f[0][1]
   and "compare(ctx)" in f[0][1] and "group" in f[0][1], str(f))
moved = SRC.replace('"id": "native_ring", "axis": "sample"', '"id": "native_ring", "axis": "contrast"')
f = findings(moved)
ck("a unit-script site under a contrast axis is an ERROR",
   len(f) == 1 and "native_ring" in f[0][1] and "_R_RUN" in f[0][1] and "run(ctx)" in f[0][1], str(f))
moved = SRC.replace('"id": "nativecmp_flow", "axis": "interaction"', '"id": "nativecmp_flow", "axis": "unit"')
f = findings(moved)
ck("the cohort script is the compare phase too, a single-quoted site is found, and a literal "
   "under `.replace(...)` (how cellchat splices its shared cap) is still read",
   len(f) == 1 and "nativecmp_flow" in f[0][1] and "_R_COHORT" in f[0][1], str(f))
ck("an entry with no site says nothing here", not [x for x in findings(SRC) if "estimation" in x[1]])
ck("an entry whose site is in no launched script says nothing",
   findings(SRC.replace('.draw("native_ring")', "")) == [])
ck("the reading is by id, not by prefix", findings(SRC.replace('.draw("native_ring")',
   '.draw("native_ring_extra")')) == [])
src_no_phase = SRC.replace("def run(ctx):", "def run_(ctx):")
ck("a script launched by no phase cannot contradict an axis", findings(src_no_phase) == [])

print("\nthe validator reads it for a one-file plugin, so the maker's first follower prints it")
src = (ROOT / "scprofile" / "validate.py").read_text(encoding="utf-8")
ck("validate_plugin calls it with the source", "declare.draw_site_phase(src, spec)" in src
   or "draw_site_phase(src, spec)" in src)

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\na draw site is in the script that draws by its axis")
