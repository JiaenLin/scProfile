"""A plugin declaration may not contain the same key twice.

Adding a `provides_evidence` block to a plugin, I wrote a second `"report": {...}` into the same
dict literal. Python keeps the last occurrence, so the block was silently discarded and every
need resolved as unavailable - a declaration that looked complete in the file and was absent at
run time. Nothing failed; the coverage was simply zero.

A duplicate key is invisible to the eye in a long declaration and invisible to `validate`, which
inspects the dict AFTER Python has already collapsed it. It is only visible in the source, which
is what this reads.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dupes(path):
    tree = ast.parse(path.read_text())
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        seen = {}
        for k in node.keys:
            if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
                continue
            if k.value in seen:
                bad.append((k.value, seen[k.value], k.lineno))
            seen[k.value] = k.lineno
    return bad


def test_no_shipped_plugin_declares_a_key_twice():
    bad = {}
    for f in sorted((ROOT / "kernels").glob("*.py")):
        d = _dupes(f)
        if d:
            bad[f.name] = d
    assert not bad, (
        "a dict literal repeats a key; Python keeps the LAST and the earlier one is silently "
        f"discarded: {bad}")


def test_no_host_module_declares_a_key_twice():
    bad = {}
    for f in sorted((ROOT / "scprofile").glob("*.py")):
        d = _dupes(f)
        if d:
            bad[f.name] = d
    assert not bad, f"duplicate dict keys in the host: {bad}"


def test_the_detector_finds_a_duplicate_it_is_given():
    """The check must be able to fail, or it is decoration."""
    import tempfile

    p = Path(tempfile.mkdtemp()) / "x.py"
    p.write_text('PLUGIN = {"report": {"a": 1}, "name": "x", "report": {"b": 2}}\n')
    found = _dupes(p)
    assert found and found[0][0] == "report", found


if __name__ == "__main__":
    import sys
    bad = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except AssertionError as e:
                bad += 1
                print(f"  FAIL {name}: {str(e)[:200]}")
    sys.exit(1 if bad else 0)
