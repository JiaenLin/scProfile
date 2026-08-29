"""Self-checks that build a real situation and assert the tool responds correctly.

A CHECK THAT READS SOURCE PROVES THE CODE IS PRESENT. It does not prove the code is right.
`scprofile check` mostly greps: it can tell you an adopt path exists and not whether adopting
the wrong thing is refused. The functions here build actual run directories - out.json,
figures, tables, a card, a licence - and put the same question to the tool that a run puts.

They live in the package rather than in the test suite because both need them: the suite runs
them as a test, and `scprofile check --deep` runs them on an installation, where a test file
may not be present.

REUSE IS A HARDLINK. An adopted result becomes part of a later run byte for byte, so a wrong
YES carries a bad result forward with a trail that makes it look verified. Testing the happy
path proves almost nothing; what must be tested is that every way of being wrong is caught.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path


def _make_run(base, obj, name, *, unit="U1", figures=("FA", "FB"), version="1.0",
              card_verdict="ok", write_out=True, licence=True):
    from . import licence as LC

    d = base / name / "kernels" / "k" / unit
    (d / "figures").mkdir(parents=True)
    (d / "tables").mkdir()
    (d / "tables" / "t.csv").write_text("a,b\n1,2\n")
    for f in figures:
        (d / "figures" / f"{f}.png").write_text(f)
    (d / "in.json").write_text(json.dumps({"h5ad": str(obj), "params": {}, "keys": {}}))
    if write_out:
        (d / "out.json").write_text(json.dumps({
            "version": version, "kernel": "k", "status": "ok",
            "figures": [{"id": f, "path": f"figures/{f}.png"} for f in figures],
            "tables": ["tables/t.csv"]}))
    if card_verdict:
        (base / name / "RUN_CARD.json").write_text(json.dumps({
            "card": 1, "run": name, "verdict": card_verdict,
            "instances": [{"plugin": "k", "unit": unit, "verdict": card_verdict,
                           "reasons": [], "artifacts": 2, "state": "done"}]}))
    if licence:
        LC.grant(base / name, "k", unit, declared=["tables/t.csv"],
                 required_figures=["FA"], declared_version=version)
    return base / name


def reuse_ablation():
    """[(title, expected, got, ok, detail)] - one row per way reuse can be wrong."""
    from . import landscape as LS

    base = Path(tempfile.mkdtemp())
    try:
        obj = base / "obj.h5ad"
        obj.write_text("x" * 500)

        def ask(unit="U1", version="1.0"):
            want = LS.wanted("k", unit, version=version, h5ad=obj, params={}, keys={})
            return LS.match(want, LS.scan(base))

        rows = []

        def case(title, expect, got):
            st, src, why = got
            rows.append((title, expect, st, st == expect,
                         (src or {}).get("run", "") if st == LS.REUSABLE
                         else (why or [""])[0][:70]))

        _make_run(base, obj, "r1_good")
        case("a complete, licensed, card-ok result is reused", LS.REUSABLE, ask())

        shutil.rmtree(base / "r1_good")
        _make_run(base, obj, "r2_missing_req", figures=("FB",))
        case("a missing REQUIRED figure is refused", LS.CHANGED, ask())

        shutil.rmtree(base / "r2_missing_req")
        r = _make_run(base, obj, "r3_tampered")
        (r / "kernels" / "k" / "U1" / "tables" / "t.csv").write_text("a,b\n9,9\n")
        case("a product changed after licensing voids it", LS.CHANGED, ask())

        shutil.rmtree(base / "r3_tampered")
        _make_run(base, obj, "r4_suspect", card_verdict="suspect")
        case("a run that calls its own result suspect is refused", LS.CHANGED, ask())

        shutil.rmtree(base / "r4_suspect")
        _make_run(base, obj, "r5_died", write_out=False, licence=False)
        case("a kernel that never wrote out.json is refused", LS.CHANGED, ask())

        shutil.rmtree(base / "r5_died")
        _make_run(base, obj, "r6_old_version", version="1.0")
        case("a newer plugin version is refused", LS.CHANGED, ask(version="2.0"))

        case("a unit nobody ran is absent", LS.ABSENT, ask(unit="U9"))

        _make_run(base, obj, "r7_bad_newer", card_verdict="suspect")
        _make_run(base, obj, "r8_good_older")
        case("a good older run is found behind a suspect newer one", LS.REUSABLE, ask())
        return rows
    finally:
        shutil.rmtree(base, ignore_errors=True)


def adoption_is_a_hardlink():
    """(ok, detail) - adopting a licensed instance shares the inode rather than copying."""
    import os

    from . import licence as LC

    base = Path(tempfile.mkdtemp())
    try:
        obj = base / "obj.h5ad"
        obj.write_text("x" * 500)
        src = _make_run(base, obj, "src")
        lic = LC.read(src, "k", "U1")
        if not lic or lic.get("grade") not in LC.ADOPTABLE:
            return False, f"no adoptable licence to test with (grade {(lic or {}).get('grade')})"
        dest = base / "dest"
        n, how, why = LC.adopt(lic, dest, min_grade=LC.PROVISIONAL)
        if not n:
            return False, "; ".join(why) or "adoption refused"
        a = src / "kernels" / "k" / "U1" / "tables" / "t.csv"
        b = dest / "kernels" / "k" / "U1" / "tables" / "t.csv"
        same = os.stat(a).st_ino == os.stat(b).st_ino
        return (same and how == "hardlink"), f"{n} file(s) by {how}, same inode {same}"
    finally:
        shutil.rmtree(base, ignore_errors=True)
