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


def station_drawing(runs):
    """6b. What a machine can see in the panels, before anyone spends an eye on them.

    THE STATION THAT MAKES THE LOOP CONVERGE. The eye station is the slowest by far and it was
    being spent on defects a measurement can make: text over text, a label clipped by the canvas,
    a size channel with no key. Those are now recorded by `emit_figure` on every panel of every
    run, so this station reads them and the eye is spent on the eight kinds of defect that have
    no mechanical form.
    """
    newest = sorted(runs, key=lambda p: p.name, reverse=True)
    # WHICH BUILD IS BEING JUDGED, SAID OUT LOUD. This station walks back to the newest run that
    # actually drew something, and it used to do that silently - so when a run was skipped for a
    # missing environment, the station reported an OLDER COMMIT'S defects under the heading of
    # the current round. The findings were real; the build they belonged to was not the one
    # under test, and nothing on the line said so.
    #
    # Walking back is still right - an empty run is not evidence that the previous defects are
    # fixed - but it is now labelled, and a run that drew nothing is named as the reason.
    skipped = []
    for r in newest:
        pay = _load(r / "report.json")
        figs = [f for pl in (pay.get("kernels") or {}).values()
                for f in (pl.get("figures") or [])]
        if not figs:
            skipped.append(r.name)
            continue
        drew_nothing = ""
        if skipped:
            drew_nothing = (f" — NOTE: this is not the newest run. "
                            f"{len(skipped)} newer run(s) drew no panels at all, starting with "
                            f"{skipped[0]}, so they prove nothing about the defects below")
        audited = [f for f in figs if "audit" in f]
        if not audited:
            return BLOCKED, (f"{r.name}: no panel carries a drawing audit — this run predates "
                             f"it{drew_nothing}"), \
                "re-run so every figure is measured as it is written"
        hits = [(f.get("id"), a) for f in audited for a in (f.get("audit") or [])]
        by = Counter(a.get("code") for _i, a in hits)
        if hits:
            named = "; ".join(f"{i}: {a.get('code')}" for i, a in hits[:4])
            return BLOCKED, (f"{r.name}: {len(hits)} drawing issue(s) across "
                             f"{len({i for i, _a in hits})} panel(s) — "
                             + " · ".join(f"{n} {k}" for k, n in by.items()) + drew_nothing), \
                f"FIX THESE FIRST, they need no eye: {named}"
        # A CLEAN RUN IS NOT A CLEAN BUILD. The same commit drew the same panels from the same
        # data twice and produced five text collisions once and none the next time - neither run
        # adopted anything, so both drew afresh. A mechanical defect that comes and goes is
        # still a defect, and a station that passes on whichever run happened to be clean would
        # sign off a build that ships the collision to whoever runs it next.
        #
        # So the station clears a COMMIT, not a run: every run of this same tool version is
        # read, and any panel that showed an issue in any of them holds the station open. A
        # build that has genuinely fixed the defect clears it in every run it has, and one that
        # has not is caught by the run where it appeared.
        commit = _commit_of(r)
        siblings = [q for q in newest if q is not r and _commit_of(q) == commit] if commit else []
        prior = []
        for q in siblings:
            qp = _load(q / "report.json")
            for pl in (qp.get("kernels") or {}).values():
                for f in (pl.get("figures") or []):
                    for a in (f.get("audit") or []):
                        prior.append((q.name, f.get("id"), a.get("code")))
        if prior:
            named = "; ".join(f"{i} ({c}) in {rn}" for rn, i, c in prior[:4])
            return BLOCKED, (f"{r.name} is clean, but {len(prior)} drawing issue(s) appeared in "
                             f"{len({rn for rn, _i, _c in prior})} other run(s) of the SAME "
                             f"commit {commit} — the defect is intermittent, not gone"), \
                (f"an intermittent defect is cleared by a build, not by a run: {named}. "
                 f"Fix it, or show it cannot occur")
        extra = f", and in {len(siblings)} other run(s) of the same commit" if siblings else ""
        return PASS, (f"{r.name}: {len(audited)} panel(s) measured, none with a drawing "
                      f"issue{extra}{drew_nothing}"), ""
    return BLOCKED, "no figures in any run", "run something that draws"


def _commit_of(run):
    """The tool version a run was drawn by, taken from its own directory name.

    Read from the run key rather than from a file inside the run: the key is fixed when the
    directory is created and nothing rewrites it, whereas the version stamp beside the code was
    untracked and went stale often enough to mislabel a run with the commit before its own.
    """
    for part in run.name.split("__"):
        if part.startswith("scprofile-"):
            return part.split("-", 1)[1]
    return ""


def _kind(fig):
    """A figure id with its unit suffix removed - the KIND, which is where a defect lives."""
    stem = Path(fig).stem
    stem = re.sub(r"__.*$", "", stem)
    return re.sub(r"^[a-z0-9]+_(?=[A-Z]|[CNPF]\d)", "", stem)


def carried_findings(runs, current):
    """What was last SEEN on each figure path, in earlier runs of this project.

    A review is bound to its image's sha256, which is right - a redrawn panel has not been looked
    at. But a change in the HOST redraws every panel of every plugin, so one line in `figure.py`
    costs every recorded look, and the eye station went 0 -> 3 -> 5 -> 8 -> 0 across five rounds
    while real defects were being found. The discipline of scanning a whole set on one build works
    around that; it does not remove it.

    So the looks are not carried - they are gone, correctly - but the FINDINGS are. A re-scan
    starts from what was last written about that panel rather than from nothing, which is the
    difference between re-reading 84 panels and re-checking 84 known findings.

    Returns {relpath: (note, run_name)}, newest first, for paths not reviewed in `current`.
    """
    out = {}
    for r in sorted(runs, key=lambda p: p.name, reverse=True):
        if r == current:
            continue
        leds = [r / "FIGURE_REVIEW.jsonl"] + [r / "kernels" / _p / "FIGURE_REVIEW.jsonl"
                                              for _p in plugins_in(r)]
        for led in [x for x in leds if x.is_file()]:
          for row in _lines(led):
            rel, note = row.get("figure"), str(row.get("note", "")).strip()
            if rel and note and rel not in out:
                out[rel] = (note, r.name)
    return out


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
        # THE LEDGERS ARE PER PLUGIN NOW, so the scan set is checked against their union. A
        # figure path inside a ledger is relative to the RUN root wherever it was written, which
        # is what makes the union meaningful without rewriting anything.
        done = set()
        for _led in [r / RV.LEDGER] + [r / "kernels" / _p / RV.LEDGER for _p in plugins_in(r)]:
            done |= {row["figure"] for row in _lines(_led)}
        todo = sorted(want - done)
        # KINDS AND INSTANCES ARE DIFFERENT NUMBERS AND BOTH BELONG ON THE LINE. The first
        # version reported only the named instances, so three real looks at a kind's MIDDLE
        # instance scored 0/45 - the coverage rule is about KINDS, and a look at any instance of
        # one is evidence about the drawing code even when it is not the instance asked for.
        # Reporting zero progress for work that was done is how a gate gets ignored.
        seen_kinds = {_kind(f) for f in done}
        worst = (r, todo, len(want), len(figs), len(kinds), len(seen_kinds & set(kinds)))
        break
    else:
        return BLOCKED, "no figures in any run", "run something that draws"
    r, todo, want, allf, nk, seenk = worst
    head = (f"{r.name}: {seenk}/{nk} kind(s) have a recorded look, "
            f"{want - len(todo)}/{want} of the named scan set ({allf} figures in the run)")
    if todo:
        # WHAT WAS LAST SEEN ON THIS PANEL, beside the name of the panel to open. A redraw
        # correctly destroys the review; it should not also destroy the knowledge.
        _carried = carried_findings(runs, r)
        _lines_out = []
        for _f in todo[:8]:
            _lines_out.append(_f)
            _prev = _carried.get(_f)
            if _prev:
                _lines_out.append(f"    last seen ({_prev[1][:24]}): {_prev[0][:150]}")
        return BLOCKED, head, \
            f"OPEN THESE AND RECORD WHAT YOU SEE:\n      " + "\n      ".join(_lines_out) \
            + (f"\n      ... and {len(todo) - 8} more" if len(todo) > 8 else "") \
            + ("\n      (a look at another instance of a kind counts toward the KIND, not "
               "toward the named largest and smallest, which are the two that break layouts)"
               if seenk else "")
    return PASS, head, ""


def station_paper(runs):
    """8. Does any of it support a claim?"""
    from scprofile import paper as PA
    # THE NEWEST RUN, LIKE THE EYE STATION - and for the same reason it took a fix there. This
    # scanned every run and stopped at the first COMPLETE one, so a finished loop on an old run
    # made the station green while the run the current code produced had no claim written from
    # it at all. A loop that reports on a run two commits back is testing code that has changed.
    best = None
    for r in sorted(runs, key=lambda p: p.name, reverse=True):
        rows = PA.status(r)
        if not rows and best is not None:
            continue
        withdrawn = sum(1 for _c, st, _n, _t in rows if st == PA.WITHDRAWN)
        out = PA.outstanding(r)
        rendered = (r / "report" / "paper.html").is_file()
        best = (r, rows, withdrawn, out, rendered)
        break
    if best is None:
        return BLOCKED, "no run to write from", "run something first"
    if not best[1]:
        # NAME THE RUN. "no claim in any run" was the message even when older runs had plenty -
        # what is true is that the NEWEST one has none, and the difference is the whole point of
        # testing the run the current code produced.
        return BLOCKED, f"{best[0].name}: no claim written from the newest run", \
            f"scprofile paper --out {best[0]} --brief"
    r, rows, withdrawn, out, rendered = best
    if not rows:
        return BLOCKED, f"{r.name}: no claim written from the newest run", \
            f"scprofile paper --out {r} --brief"
    if out:
        return BLOCKED, f"{r.name}: {len(out)} claim(s) undefended or stale", \
            f"scprofile paper --out {r} --round <id> --verdict ... --why '...'"
    if not rendered:
        return BLOCKED, f"{r.name}: claims defended, section not rendered into the run", \
            f"scprofile paper --out {r} --render"
    return PASS, (f"{r.name}: {len(rows)} claim(s), {withdrawn} withdrawn, section rendered"), \
        ("" if withdrawn else "no claim was ever withdrawn — that is also what a loop looks "
                              "like when nobody pushed")


#: THE DELIVERABLES A FINISHED RUN MUST CARRY, by path relative to the run directory. A run that
#: is missing any of these has not produced its outputs, whatever else it wrote - and a loop that
#: reports a round as going well while the manuscript does not exist is describing the half of
#: the work that is easy. Named rather than counted, so the message says WHICH one is absent.
REQUIRED_OUTPUTS = (
    ("report.json", "the machine-readable record every station reads"),
    ("report/index.html", "the assembled report"),
)

#: AND PER PLUGIN, because a run mounts several methods and each owes its own result. These are
#: resolved under `kernels/<plugin>/` - see `kernels.plugin_out`.
REQUIRED_PER_PLUGIN = (
    ("FIGURE_REVIEW.jsonl", "the ledger of what was actually looked at"),
    ("PAPER.{plugin}.md", "this plugin's result section, written from its figures"),
    ("report/{plugin}_paper.html", "its manuscript and figure panel, rendered"),
)


def plugins_in(run):
    """The plugins that actually produced something in this run."""
    d = run / "kernels"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir()
                  if p.is_dir() and any(p.rglob("*.png")))


def missing_outputs(run):
    """Which required deliverables this run does not have. Empty means it is complete.

    Run-level first, then EVERY PLUGIN'S own three. A run whose report assembled but whose
    cellchat section was never written is not finished, and saying so per plugin is the only way
    a reader learns WHICH result is missing rather than that something is.
    """
    gone = [(p, why) for p, why in REQUIRED_OUTPUTS if not (run / p).exists()]
    for plug in plugins_in(run):
        for tmpl, why in REQUIRED_PER_PLUGIN:
            rel = f"kernels/{plug}/" + tmpl.format(plugin=plug)
            if not (run / rel).exists():
                gone.append((rel, why))
    return gone


def station_outputs(runs):
    """9. Did the newest run produce every output a finished run must carry?

    LAST, AND IT GATES. Everything before it can be green while the run holds no manuscript at
    all - which is exactly the state a round was reported as progress in. The paper is not a
    flourish on top of the profiling layer, it is the thing the figures are for, so a run without
    one is unfinished in the same way a run without a report would be.
    """
    newest = sorted(runs, key=lambda p: p.name, reverse=True)
    for r in newest:
        if not (r / "report.json").exists():
            continue
        gone = missing_outputs(r)
        if gone:
            return BLOCKED, (f"{r.name}: {len(gone)} required output(s) missing — "
                             + ", ".join(p for p, _ in gone)), \
                ("PRODUCE THESE; a run without them is not finished:\n      "
                 + "\n      ".join(f"{p} — {why}" for p, why in gone))
        return PASS, f"{r.name}: every required output present ({len(REQUIRED_OUTPUTS)})", ""
    return BLOCKED, "no run has a report.json", "run something"



STATIONS = (
    ("1 exists", station_exists), ("2 landscape", station_landscape),
    ("3 licence", station_licence), ("4 adopt", station_adopt),
    ("5 merge", station_merge), ("6 report", station_report),
    ("6b drawing", station_drawing),
    ("7 eye", station_eye), ("8 paper", station_paper),
    ("9 outputs", station_outputs),
)




def _eye_set(runs):
    """The named scan set of the newest run that drew anything, and what has been looked at.

    Computed here as well as in the station so the GOAL can be printed as a count on every
    blocked round, including rounds blocked earlier than station 7 - the distance to the goal
    does not depend on which station happens to be in the way.
    """
    from scprofile import review as RV
    RASTER = (".png", ".jpg", ".jpeg")
    for r in sorted(runs, key=lambda p: p.name, reverse=True):
        figs = [f for f in RV.figures(r) if f.lower().endswith(RASTER)]
        if not figs:
            continue
        kinds = {}
        for f in figs:
            kinds.setdefault(_kind(f), []).append(f)
        want = set()
        for _k, fs in kinds.items():
            fs = sorted(fs, key=lambda p: (r / p).stat().st_size)
            want.add(fs[0])
            want.add(fs[-1])
        done = {row["figure"] for row in _lines(r / RV.LEDGER)}
        return want, want & done
    return set(), set()


def _eye_total(runs):
    return len(_eye_set(runs)[0])


def _eye_done(runs):
    return len(_eye_set(runs)[1])


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
        # THE GOAL, RESTATED ON EVERY BLOCKED RUN, BECAUSE THE LOOP HAS BEEN ABANDONED SHORT OF
        # IT. The stations before 7 are mechanical and they all go green long before the tool is
        # any good - which reads like an achievement and is not one. A round that clears every
        # machine check and looks at six panels of eighty-four has tested almost nothing: every
        # figure defect this tool has ever had was found by opening the image while the suite
        # was green.
        #
        # So the distance to the goal is printed on its own line, in the same words every time,
        # and it is a COUNT rather than a state. "BLOCKED at 7" invites a status report; "6 of
        # 84 looked at" does not.
        print()
        print(f"    THE GOAL OF THIS LOOP IS STATION 7 AT {_eye_total(runs)}/{_eye_total(runs)}, "
              f"THEN STATION 8.")
        print(f"    Reached so far: {_eye_done(runs)}/{_eye_total(runs)} panels looked at and "
              f"recorded.")
        print("    Nothing before station 7 is the goal. Clearing the machine checks is the "
              "cheap half")
        print("    and it goes green while the pictures are still wrong. DO NOT STOP HERE, AND "
              "DO NOT")
        print("    REPORT THIS AS PROGRESS: an unfinished scan is an untested tool.")
        # AND THE DELIVERABLES, NAMED, ON EVERY BLOCKED ROUND. Station 9 checks them, but a
        # round blocked at station 2 never reaches station 9 - and "the manuscript does not
        # exist" is not a fact that should wait its turn behind a licence check.
        newest = sorted(runs, key=lambda p: p.name, reverse=True)
        for _r in newest:
            if (_r / "report.json").exists():
                _gone = missing_outputs(_r)
                if _gone:
                    print()
                    print(f"    REQUIRED OUTPUTS STILL MISSING from {_r.name}:")
                    for _p, _why in _gone:
                        print(f"      {_p:24s} {_why}")
                    print("    No round is finished while any of these is absent.")
                break
        return 1
    print("EVERY STATION HAS EVIDENCE. Start the next round from station 1: a change upstream "
          "invalidates what is downstream, which is what the digests are for.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
