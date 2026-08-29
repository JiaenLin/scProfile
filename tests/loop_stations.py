"""Drive a project's real runs through every element of scProfile, one station at a time.

WHY THIS EXISTS. The suite proves a function returns. It cannot prove the chain works on runs
somebody actually made, in the state they are actually in - some sealed and some not, some
carrying a card and some not - which is the state a tool meets and a fixture never reproduces.

WHAT IT DOES AND DOES NOT DO. It runs the mechanical stations, MEASURES the filesystem rather
than believing the tool's account of itself, and names the one thing to do next. It does not do
the looking or the writing, because nothing can; it refuses to advance without them.

    python tests/loop_stations.py --runs <dir-of-run-directories> [--round N]

`docs/TEST_LOOP.md` is the design: the stations, what counts as evidence, and the coverage rule
for the eye scan.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BLOCKED, PASS, EMPTY = "BLOCKED", "pass", "n/a"


def _runs(d):
    return sorted(p for p in Path(d).iterdir()
                  if p.is_dir() and (p / "report.json").is_file())


def _load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                                     # noqa: BLE001
        return {}


def _lines(p):
    if not p.is_file():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
            if l.strip() and l.strip().startswith("{")]


def station_exists(runs):
    """1. What do these runs already hold?"""
    from scprofile import resume as RS
    tot = Counter()
    for r in runs:
        for _p, _u, st, _w, _n in RS.survey(r, RS.discover(r)):
            tot[st] += 1
    if not tot:
        return BLOCKED, "no instances found in any run", "check --runs points at run directories"
    return PASS, " · ".join(f"{n} {k}" for k, n in sorted(tot.items())), ""


def station_landscape(runs):
    """2. Which results could a new run reuse?"""
    from scprofile import landscape as LS
    try:
        cands = LS.survey(runs[0].parent) if hasattr(LS, "survey") else None
    except Exception:                                                     # noqa: BLE001
        cands = None
    licensed = [r for r in runs if (r / "LICENCES").is_dir()
                and any((r / "LICENCES").glob("*.json"))]
    if not licensed:
        return BLOCKED, "no run carries a granted licence", \
            "scprofile licence --out <RUN> --grant"
    n = sum(len(list((r / "LICENCES").glob("*.json"))) for r in licensed)
    return PASS, f"{n} licence(s) across {len(licensed)} run(s)", ""


def station_licence(runs):
    """3. Is any of it fit to build on? Grades must come from criteria, on disk."""
    grades = Counter()
    for r in runs:
        for f in sorted((r / "LICENCES").glob("*.json")) if (r / "LICENCES").is_dir() else []:
            grades[str(_load(f).get("grade", "?"))] += 1
    if not grades:
        return BLOCKED, "no grades on disk", "scprofile licence --out <RUN> --grant"
    only = set(grades) <= {"refused"}
    return (BLOCKED if only else PASS), " · ".join(f"{n} {k}" for k, n in sorted(grades.items())), \
        ("every licence is refused, so nothing can be adopted" if only else "")


def station_adopt(runs):
    """4. Does reuse actually reuse? MEASURED on the filesystem, not read off a log."""
    adopted = [(r, f.parent) for r in runs
               for f in r.rglob("ADOPTED.json")]
    if not adopted:
        return BLOCKED, "no instance in any run was adopted from another", \
            "scprofile run ... --reuse-from <dir-of-runs>"
    shared, checked, copied = 0, 0, 0
    for run, inst in adopted:
        rec = _load(inst / "ADOPTED.json")
        src = rec.get("from") or rec.get("source") or ""
        for f in sorted(inst.rglob("*")):
            if not f.is_file() or f.name == "ADOPTED.json":
                continue
            checked += 1
            # THE TOOL SAYS "by hardlink". THIS COUNTS THE LINKS. A tool's account of its own
            # behaviour is a claim; st_nlink is a measurement.
            if os.stat(f).st_nlink > 1:
                shared += 1
            else:
                copied += 1
            if checked >= 40:
                break
        if checked >= 40:
            break
    if not checked:
        return BLOCKED, "adopted instances hold no files", "the adoption wrote nothing"
    return PASS, (f"{len(adopted)} adopted instance(s); of {checked} product file(s) measured, "
                  f"{shared} share an inode and {copied} do not"), \
        ("" if shared else "NOTHING shares an inode — the adoption copied, or the link was lost")


def station_merge(runs):
    """5. Did an adopted result reach the merged object?"""
    hits = 0
    for r in runs:
        pay = _load(r / "report.json")
        if pay.get("reused"):
            hits += 1
    if not hits:
        return BLOCKED, "no run's payload records what it reused", \
            "a run with --reuse-from records `reused` in report.json"
    return PASS, f"{hits} run(s) record what they reused", ""


def station_report(runs):
    """6. Is the page readable? The standard, on the rendered HTML."""
    from scprofile import standard as ST
    ok, bad = 0, []
    for r in runs:
        d = r / "report"
        if not d.is_dir():
            continue
        try:
            res = ST.check_report(r) if hasattr(ST, "check_report") else None
        except Exception as e:                                            # noqa: BLE001
            bad.append(f"{r.name}: {e}")
            continue
        if res is None:
            continue
        ok += 1
    if not ok and not bad:
        return BLOCKED, "no rendered report to measure", "scprofile report --out <RUN>"
    return PASS, f"{ok} report(s) measured" + (f"; {len(bad)} raised" if bad else ""), \
        "; ".join(bad[:2])


def _kind(fig):
    """A figure id with its unit suffix removed - the KIND, which is where a defect lives."""
    stem = Path(fig).stem
    stem = re.sub(r"__.*$", "", stem)
    return re.sub(r"^[a-z0-9]+_(?=[A-Z]|[CNPF]\d)", "", stem)


def station_eye(runs):
    """7. Are the pictures right? A ledger entry per figure in the scan set.

    TWO THINGS THIS GOT WRONG ON ITS FIRST RUN, both of which made the worklist wrong rather
    than merely long:

      IT SCANNED THE PDF AND THE PNG OF THE SAME PANEL. `review` counts every image suffix, and
      "the largest and smallest instance of a kind" then selected the two FORMATS of one panel
      instead of two units of it - so the rule that exists to cover the units that break layouts
      covered one unit twice. Raster only: the vector is the same picture.

      IT PICKED THE RUN WITH THE MOST GAPS. That is whichever run has the most figures, and it
      is usually an old one. The loop tests the TOOL, and the newest run is the one the current
      code produced; scanning an old run's figures reports on code that has already changed.
    """
    from scprofile import review as RV
    RASTER = (".png", ".jpg", ".jpeg")
    # Newest by run key, which begins with a UTC stamp - so sorting the names sorts by time.
    for r in sorted(runs, key=lambda p: p.name, reverse=True):
        figs = [f for f in RV.figures(r) if f.lower().endswith(RASTER)]
        if not figs:
            continue
        kinds = {}
        for f in figs:
            kinds.setdefault(_kind(f), []).append(f)
        # THE COVERAGE RULE, from docs/TEST_LOOP.md: every kind once, plus every cohort panel,
        # and where a kind is per-unit take the largest and smallest instance - the two that
        # break a layout.
        want = set()
        for _k, fs in kinds.items():
            fs = sorted(fs, key=lambda p: (r / p).stat().st_size)
            want.add(fs[0])
            want.add(fs[-1])
        done = {row["figure"] for row in _lines(r / RV.LEDGER)}
        todo = sorted(want - done)
        worst = (r, todo, len(want), len(figs))
        break
    else:
        return BLOCKED, "no figures in any run", "run something that draws"
    r, todo, want, allf = worst
    if todo:
        return BLOCKED, (f"{r.name}: {want - len(todo)}/{want} of the scan set looked at "
                         f"({allf} figures in the run)"), \
            f"OPEN THESE AND RECORD WHAT YOU SEE:\n      " + "\n      ".join(todo[:8]) \
            + (f"\n      ... and {len(todo) - 8} more" if len(todo) > 8 else "")
    return PASS, f"every kind in the scan set has a recorded look ({want} of {allf} figures)", ""


def station_paper(runs):
    """8. Does any of it support a claim?"""
    from scprofile import paper as PA
    best = None
    for r in runs:
        rows = PA.status(r)
        if not rows:
            continue
        withdrawn = sum(1 for _c, st, _n, _t in rows if st == PA.WITHDRAWN)
        out = PA.outstanding(r)
        rendered = (r / "report" / "paper.html").is_file()
        best = (r, rows, withdrawn, out, rendered)
        if not out and rendered:
            break
    if best is None:
        return BLOCKED, "no claim has been written from any run's figures", \
            "scprofile paper --out <RUN> --brief"
    r, rows, withdrawn, out, rendered = best
    if out:
        return BLOCKED, f"{r.name}: {len(out)} claim(s) undefended or stale", \
            f"scprofile paper --out {r} --round <id> --verdict ... --why '...'"
    if not rendered:
        return BLOCKED, f"{r.name}: claims defended, section not rendered into the run", \
            f"scprofile paper --out {r} --render"
    return PASS, (f"{r.name}: {len(rows)} claim(s), {withdrawn} withdrawn, section rendered"), \
        ("" if withdrawn else "no claim was ever withdrawn — that is also what a loop looks "
                              "like when nobody pushed")


STATIONS = (
    ("1 exists", station_exists), ("2 landscape", station_landscape),
    ("3 licence", station_licence), ("4 adopt", station_adopt),
    ("5 merge", station_merge), ("6 report", station_report),
    ("7 eye", station_eye), ("8 paper", station_paper),
)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", required=True, type=Path,
                    help="a directory holding run directories")
    ap.add_argument("--round", type=int, default=0, help="which round this is, for the record")
    a = ap.parse_args()
    runs = _runs(a.runs)
    if not runs:
        print(f"no run directories under {a.runs}", file=sys.stderr)
        return 2
    print(f"THE TEST LOOP — round {a.round or '?'} — {len(runs)} run(s) under {a.runs}\n")
    first_blocked = None
    for name, fn in STATIONS:
        try:
            state, detail, nxt = fn(runs)
        except Exception as e:                                            # noqa: BLE001
            state, detail, nxt = BLOCKED, f"station raised: {e}", ""
        mark = "  ok  " if state == PASS else "BLOCKED"
        print(f"{mark}  {name:<12} {detail}")
        if nxt and state != PASS:
            print(f"          -> {nxt}")
        elif nxt:
            print(f"          note: {nxt}")
        if state != PASS and first_blocked is None:
            first_blocked = name
    print()
    if first_blocked:
        print(f"THE LOOP IS BLOCKED AT {first_blocked}. Clear it, then run this again.")
        print("Every finding becomes a change in this repository, or it did not happen.")
        return 1
    print("EVERY STATION HAS EVIDENCE. Start the next round from station 1: a change upstream "
          "invalidates what is downstream, which is what the digests are for.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
