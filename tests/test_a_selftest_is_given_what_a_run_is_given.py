"""A plugin's selftest is handed what a run is handed, and the host's fixture needs nothing the
host's own interpreter lacks.

Found by the third blind conversion (harness docs/blind/0003-deseq2.md), the first plugin written
on the figure plan by a cold agent: its selftest could not draw through the generated companion,
because `_entry.selftest` built its Context without `r_companion` while `main` and `_compare`
both load it - so `.draw` was undefined in the one place a plugin proves its own call. And
`ctx.fixture()` imported scanpy to log-normalise 200 cells, so on an interpreter with anndata
and numpy but no scanpy every plugin's selftest failed before the plugin ran. The agent worked
around both inside the plugin; neither belongs there.
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import _entry as E                                        # noqa: E402
from scprofile.plugin import Context                                     # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


print("the selftest's context carries the generated companion")
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    (d / "probe.py").write_text(
        'PLUGIN = {"api": 1, "state_version": 1, "summary": "x", "cannot_show": ["y"]}\n'
        'def run(ctx):\n'
        '    pass\n'
        'def selftest(ctx):\n'
        '    assert ".draw <- function" in ctx.r_companion, "no companion on the context"\n',
        encoding="utf-8")
    (d / "probe.draw.R").write_text(".draw <- function(id, item = NULL) NULL\n", encoding="utf-8")
    got, why = None, ""
    try:
        got = E.selftest(str(d / "probe.py"), log=lambda *a, **k: None)
    except AssertionError as e:
        why = str(e)
    check(got is True, f"selftest did not pass: {why or got!r}")

print("the fixture is built without scanpy")
try:
    import anndata                                                        # noqa: F401
except ImportError:
    # A TEST WHOSE SUBJECT IS ABSENT IS NOT A TEST THAT FAILED: the fixture is anndata's, and
    # this interpreter has none. `tests/run_all.py --python <one that has it>` runs this half.
    print("  skip: anndata is not installed here")
    anndata = None
_had = sys.modules.get("scanpy", "absent")
if anndata is None:
    _had = None
if _had is not None:
    sys.modules["scanpy"] = None                   # import scanpy -> ModuleNotFoundError
try:
    with tempfile.TemporaryDirectory() as td:
        if _had is None:
            raise StopIteration
        ctx = Context(None, keys={}, out=td, cores=1, log=lambda *a, **k: None)
        err = ""
        try:
            A = ctx.fixture(n_cells=40, n_genes=30)
        except ImportError as e:
            A, err = None, str(e)
        check(A is not None, f"fixture() needs an import the host does not require: {err}")
        if A is not None:
            X = np.asarray(A.layers["counts"], dtype="float64")
            lib = X.sum(axis=1, keepdims=True)
            want = np.log1p(X / np.where(lib == 0, 1, lib) * 1e4)
            check(np.allclose(np.asarray(A.layers["lognorm"], dtype="float64"), want, atol=1e-5),
                  "the lognorm layer is not counts scaled to ten thousand per cell, log1p")
            check("label" in A.obs and A.obs["label"].nunique() == 2, "the fixture lost its labels")
except StopIteration:
    pass
finally:
    if _had == "absent":
        del sys.modules["scanpy"]
    elif _had is not None:
        sys.modules["scanpy"] = _had

if FAILURES:
    print("FAIL")
    for x in FAILURES:
        print("  -", x)
    raise SystemExit(1)
print("ok: the selftest draws through the companion a run draws through, and the fixture is the "
      "host's own arithmetic")
