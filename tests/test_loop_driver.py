"""The loop driver must at least IMPORT, and every station it names must exist.

This exists because it did not. `STATIONS` was edited to name a station defined further down the
file, so the module raised NameError at import - and it shipped, because the gate runs
`tests/test_*.py` and the loop driver is not one of them, while the check that was run against it
was `ast.parse`, which parses without executing and therefore cannot see an undefined name.

A driver that does not import reports nothing at all, which is the one failure mode a test loop
cannot afford: it looks like the loop was not run rather than like the loop failed.
"""
import importlib


def test_the_driver_imports():
    importlib.import_module("tests.loop_stations")


def test_every_named_station_is_callable():
    L = importlib.import_module("tests.loop_stations")
    for name, fn in L.STATIONS:
        assert callable(fn), f"station {name!r} is not callable"


def test_the_stations_are_in_order_and_unique():
    L = importlib.import_module("tests.loop_stations")
    names = [n for n, _ in L.STATIONS]
    assert len(set(names)) == len(names), "a station name is repeated"
    assert names[0].startswith("1 "), "the first station is not station 1"


def test_the_goal_stations_are_present():
    """The loop's goal is the eye scan and the manuscript; both must be in the chain."""
    L = importlib.import_module("tests.loop_stations")
    names = " ".join(n for n, _ in L.STATIONS)
    assert "eye" in names, "the eye station is not in the chain"
    assert "paper" in names, "the paper station is not in the chain"
    assert "outputs" in names, "the required-outputs station is not in the chain"


def test_required_outputs_names_the_manuscript():
    L = importlib.import_module("tests.loop_stations")
    paths = [p for p, _ in L.REQUIRED_OUTPUTS]
    assert "PAPER.md" in paths
    assert "report/paper.html" in paths


if __name__ == "__main__":
    import sys
    bad = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except Exception as e:
                bad += 1
                print(f"  FAIL {name}: {e}")
    sys.exit(1 if bad else 0)
