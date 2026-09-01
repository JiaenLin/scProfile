"""A name bound only inside a branch is not read outside it.

TWICE IN THIS FILE NOW. `report.write_kernel` is long and its sections are guarded - a profile
page is written only where there are profile panels, an arms page only where there are arms - so
a local bound inside one of those guards does not exist on the runs that skip it. Reading it a
few hundred lines further down is an UnboundLocalError that fires on the ORDINARY case: the run
where the optional thing was absent.

  * a report block was written to `d`, which was bound ninety lines later;
  * the figure-panel link read `_pd`, bound inside the branch that writes the profile page.

Both raised only where the guarded section had not run, and both were caught by a test that
happened to exercise that path rather than by anything looking for the shape.

The check is deliberately narrow, because the general version is a type checker: a name is
flagged only when EVERY binding of it sits inside a conditional body and it is read at the
function's own statement level, outside any conditional. That is exactly the two failures above
and it does not fire on the ordinary "assign in both arms of an if/else" pattern.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []


def _branchy(fn):
    """{name: bound_only_inside_a_branch} and the names read at the function's own level."""
    top_binds, deep_binds, top_reads = set(), set(), set()

    def walk(node, depth):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Name):
                if isinstance(child.ctx, ast.Store):
                    (deep_binds if depth else top_binds).add(child.id)
                elif isinstance(child.ctx, ast.Load) and depth == 0:
                    top_reads.add(child.id)
            inner = depth + 1 if isinstance(child, (ast.If, ast.For, ast.While,
                                                    ast.Try, ast.With)) else depth
            walk(child, inner)

    walk(fn, 0)
    return (deep_binds - top_binds) & top_reads


for path in sorted((ROOT / "scprofile").glob("*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = {a.arg for a in node.args.args + node.args.kwonlyargs}
        args |= {node.args.vararg.arg} if node.args.vararg else set()
        args |= {node.args.kwarg.arg} if node.args.kwarg else set()
        for nm in sorted(_branchy(node) - args):
            FAILURES.append(
                f"{path.name} / {node.name}(): '{nm}' is bound only inside a conditional and "
                f"read outside it - the run that skips that branch raises UnboundLocalError")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - no local escapes the branch that binds it")
