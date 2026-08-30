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


def test_required_outputs_names_the_manuscript_per_plugin():
    """One manuscript per plugin, so the requirement is per plugin too."""
    L = importlib.import_module("tests.loop_stations")
    run_level = [p for p, _ in L.REQUIRED_OUTPUTS]
    per_plug = [p for p, _ in L.REQUIRED_PER_PLUGIN]
    assert "report/index.html" in run_level
    assert any("PAPER." in p for p in per_plug), per_plug
    assert any("_paper.html" in p for p in per_plug), per_plug
    assert "FIGURE_REVIEW.jsonl" in per_plug


def test_a_plugin_missing_its_section_is_named():
    """A run whose report assembled but whose cellchat section was never written is unfinished,
    and the message must say WHICH result is missing rather than that something is."""
    import tempfile
    from pathlib import Path

    L = importlib.import_module("tests.loop_stations")
    with tempfile.TemporaryDirectory() as td:
        run = Path(td) / "20260101T000000Z__scprofile-a__s"
        (run / "report").mkdir(parents=True)
        (run / "report.json").write_text("{}")
        (run / "report" / "index.html").write_text("<p>")
        figs = run / "kernels" / "cellchat" / "figures"
        figs.mkdir(parents=True)
        (figs / "F1.png").write_bytes(b"x")
        gone = dict(L.missing_outputs(run))
        assert any("cellchat" in p for p in gone), gone
        assert any(p.endswith("PAPER.cellchat.md") for p in gone), gone


def test_findings_are_carried_across_runs():
    """A redraw destroys the review. It must not also destroy what was written.

    Built as a real pair of run directories, because the thing under test is reading one run's
    ledger while scanning another.
    """
    import json
    import tempfile
    from pathlib import Path

    L = importlib.import_module("tests.loop_stations")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        old = root / "20260101T000000Z__scprofile-aaaaaaa__stage"
        new = root / "20260102T000000Z__scprofile-bbbbbbb__stage"
        for d in (old, new):
            (d / "kernels" / "k" / "figures").mkdir(parents=True)
            (d / "kernels" / "k" / "figures" / "F1.png").write_bytes(b"x")
        rel = "kernels/k/figures/F1.png"
        (old / "FIGURE_REVIEW.jsonl").write_text(
            json.dumps({"figure": rel, "note": "the legend covers the third bar"}) + "\n")

        got = L.carried_findings([old, new], new)
        assert rel in got, "nothing was carried from the earlier run"
        assert "legend covers" in got[rel][0], f"the wrong note was carried: {got[rel]}"
        assert got[rel][1] == old.name, "the carried finding does not name the run it came from"

        # and a run must not carry from ITSELF, which would make a look look done
        assert L.carried_findings([old], old) == {}, "a run carried its own ledger forward"


def test_the_newest_earlier_finding_wins():
    import json
    import tempfile
    from pathlib import Path

    L = importlib.import_module("tests.loop_stations")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rel = "kernels/k/figures/F1.png"
        runs = []
        for stamp, note in (("20260101T000000Z", "older finding"),
                            ("20260102T000000Z", "newer finding")):
            d = root / f"{stamp}__scprofile-x__stage"
            (d / "kernels" / "k" / "figures").mkdir(parents=True)
            (d / "FIGURE_REVIEW.jsonl").write_text(
                json.dumps({"figure": rel, "note": note}) + "\n")
            runs.append(d)
        cur = root / "20260103T000000Z__scprofile-y__stage"
        cur.mkdir()
        got = L.carried_findings(runs + [cur], cur)
        assert got[rel][0] == "newer finding", f"an older finding won: {got[rel]}"


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
