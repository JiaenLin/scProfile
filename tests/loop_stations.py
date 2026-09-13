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
        # WHAT THIS STATION DID NOT MEASURE, COUNTED FROM DISK. The audit runs where the host
        # writes a panel - `emit_figure` - and a panel the wrapped tool draws in its own
        # interpreter never passes through it: no audit, no manifest record, and the reporter
        # globs it off disk later. Measured on the run this was written against: about four
        # panels in five, and the station's silence on them read as clean. A station that
        # measured a fifth of the panels and said "none with a drawing issue" was the
        # found-nothing-versus-looked-and-found-nothing defect at the largest scale in the tool.
        #
        # Disk against manifest, as station 4 does: the manifest is the tool's account of
        # itself, and the pngs are what a reader will find.
        unmeasured = _unmeasured(r, audited)
        # AND WHICH OF THEM ANYTHING RECORDED (ADR-0016 step 4f). A panel the plan's companion
        # drew carries a manifest record marked `measured: False`; one the reporter drew for
        # its own pages carries none. Both are unmeasured; only the first is accounted for.
        recorded = {str(f.get("path") or "") for f in figs if f.get("measured") is False}
        n_rec = sum(1 for x in unmeasured if x in recorded)
        um = (f"; {len(unmeasured)} drawn and NOT measured by any machine ({n_rec} recorded by "
              f"the plugin's companion as drawn outside the host's emit path, "
              f"{len(unmeasured) - n_rec} recorded by nothing - the eye is their only check)"
              if unmeasured else "")
        hits = [(f.get("id"), a) for f in audited for a in (f.get("audit") or [])]
        by = Counter(a.get("code") for _i, a in hits)
        # WHAT THE HOST MENDED BEFORE IT MEASURED (harness ADR-0018). The audit repairs the
        # classes it can where the artists are still live and records the residue; a clean run
        # that needed forty repairs is a different fact from one that needed none, and a residue
        # means nothing without what was tried.
        reps = [(f.get("id"), rp) for f in audited for rp in (f.get("repairs") or [])]
        n_rep_panels = len({i for i, _r in reps})
        mended = (f"the host repaired {len(reps)} on {n_rep_panels} panel(s)"
                  if reps else "the host repaired nothing")
        if hits:
            tried = {}
            for i, rp in reps:
                tried.setdefault(i, set()).add(str(rp.get("code")))
            named = "; ".join(f"{i}: {a.get('code')}"
                              + (f" (tried: {', '.join(sorted(tried[i]))})" if i in tried
                                 else "")
                              for i, a in hits[:4])
            return BLOCKED, (f"{r.name}: {len(hits)} drawing issue(s) remain across "
                             f"{len({i for i, _a in hits})} panel(s) after {mended} — "
                             + " · ".join(f"{n} {k}" for k, n in by.items()) + um
                             + drew_nothing), \
                (f"FIX THESE, they are what the host's repertoire does not answer: {named}. "
                 f"A class that is general belongs in the repertoire (scprofile/figure.py); "
                 f"one that is this panel's belongs in the plan or the plugin")
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
                      f"issue; {mended}{extra}{um}{drew_nothing}"), ""
    return BLOCKED, "no figures in any run", "run something that draws"


def _unmeasured(run, audited):
    """Raster panels on disk that no manifest record with an audit names. Run-relative paths."""
    from scprofile import review as RV
    RASTER = (".png", ".jpg", ".jpeg")
    on_disk = {f for f in RV.figures(run) if f.lower().endswith(RASTER)}
    measured = {str(f.get("path") or "") for f in audited}
    return sorted(on_disk - measured)


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


def _scan(r):
    """(the scan set of one run, the figures of it with a recorded look) - run-relative paths.

    ONE SET, `review.scan_set`, per plugin and unioned: what the paper numbers plus one instance
    of every other kind (harness ADR-0017). The ledgers are per plugin; a figure path inside a
    ledger is relative to the RUN root wherever it was written, which is what makes the union
    meaningful without rewriting anything.
    """
    from scprofile import review as RV
    want = set()
    for p in plugins_in(r):
        want |= set(RV.scan_set(r, p))
    done = set()
    for led in [r / RV.LEDGER] + [r / "kernels" / p / RV.LEDGER for p in plugins_in(r)]:
        done |= {row["figure"] for row in _lines(led)}
    return want, want & done, done


def station_eye(runs):
    """7. Are the pictures right? A ledger entry per figure in the scan set.

    TWO THINGS THIS GOT WRONG ON ITS FIRST RUN, both of which made the worklist wrong rather
    than merely long: it scanned the PDF and the PNG of one panel as two instances, and it
    picked the run with the most gaps, which is the oldest. Raster only; the newest run. And a
    third, found when a cold agent was to be driven through it (ADR-0017): it asked for a set
    of its own - every kind's largest and smallest, by a definition of a kind that was its own
    too - while the review command split the paper's list; the set is `review.scan_set` now,
    read by every caller alike.
    """
    from scprofile import review as RV
    # Newest by run key, which begins with a UTC stamp - so sorting the names sorts by time.
    for r in sorted(runs, key=lambda p: p.name, reverse=True):
        want, seen, done = _scan(r)
        if not want:
            continue
        allf = len([f for f in RV.figures(r) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
        kinds = {RV.kind_of(f) for f in want}
        # KINDS AND INSTANCES ARE DIFFERENT NUMBERS AND BOTH BELONG ON THE LINE: a look at any
        # instance of a kind is evidence about the drawing code even when it is not the
        # instance asked for, and reporting zero for it is how a gate gets ignored.
        seen_kinds = {RV.kind_of(f) for f in done} & kinds
        todo = sorted(want - seen)
        break
    else:
        return BLOCKED, "no figures in any run", "run something that draws"
    head = (f"{r.name}: {len(seen_kinds)}/{len(kinds)} kind(s) have a recorded look, "
            f"{len(seen)}/{len(want)} of the named scan set ({allf} figures in the run)")
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
        plugs = plugins_in(r)
        cmd = (f"scprofile review --out {r} --plugin {plugs[0] if plugs else '<plugin>'} "
               f"--shards {max(1, -(-len(todo) // 25))}")
        return BLOCKED, head, \
            (f"OPEN THESE AND RECORD WHAT YOU SEE (the whole list, split for several agents: "
             f"{cmd}):\n      " + "\n      ".join(_lines_out)
             + (f"\n      ... and {len(todo) - 8} more" if len(todo) > 8 else "")
             + ("\n      (a look at another instance of a kind counts toward the KIND, not "
                "toward the named instance)" if seen_kinds else ""))
    return PASS, head, ""


def station_paper(runs):
    """8. Does any of it support a claim? Per plugin, as the reporter writes it.

    THE NEWEST RUN, LIKE THE EYE STATION - and for the same reason it took a fix there: a
    finished loop on an old run made the station green while the run the current code produced
    had no claim written from it at all.

    PER PLUGIN (harness ADR-0017). The claims ledger and the rendered section are one plugin's,
    under `kernels/<plugin>/` and `report/<plugin>_paper.html`; this read the run-level ledger
    and looked for `report/paper.html`, so a run carrying 24 composed claims and a rendered
    page per plugin read "no claim written from the newest run", and the station could never
    pass on any run the reporter had made.
    """
    from scprofile import paper as PA
    newest = sorted(runs, key=lambda p: p.name, reverse=True)
    for r in newest:
        if not (r / "report.json").exists():
            continue
        plugs = plugins_in(r)
        if not plugs:
            continue
        n_claims, n_withdrawn, gaps = 0, 0, []
        for p in plugs:
            rows = PA.status(r, p)
            if not rows:
                gaps.append((f"{p}: no claim written",
                             f"scprofile paper --out {r} --plugin {p} --brief"))
                continue
            n_claims += len(rows)
            n_withdrawn += sum(1 for _c, st, _n, _t in rows if st == PA.WITHDRAWN)
            out = PA.outstanding(r, p)
            if out:
                gaps.append((f"{p}: {len(out)} claim(s) undefended or stale",
                             f"scprofile paper --out {r} --plugin {p} --round {out[0][0]} "
                             f"--verdict standing|narrowed|withdrawn --why '...'"))
                continue
            if not (r / "report" / PA.page_name(p)).is_file():
                gaps.append((f"{p}: claims defended, section not rendered into the run",
                             f"scprofile paper --out {r} --plugin {p} --render"))
        if gaps:
            return BLOCKED, f"{r.name}: " + "; ".join(g for g, _c in gaps), gaps[0][1]
        return PASS, (f"{r.name}: {n_claims} claim(s) over {len(plugs)} plugin(s), "
                      f"{n_withdrawn} withdrawn, section(s) rendered"), \
            ("" if n_withdrawn else "no claim was ever withdrawn — that is also what a loop "
                                    "looks like when nobody pushed")
    return BLOCKED, "no run to write from", "run something first"


#: THE DELIVERABLES A FINISHED RUN MUST CARRY, by path relative to the run directory. A run that
#: is missing any of these has not produced its outputs, whatever else it wrote - and a loop that
#: reports a round as going well while the manuscript does not exist is describing the half of
#: the work that is easy. Named rather than counted, so the message says WHICH one is absent.
REQUIRED_OUTPUTS = (
    ("report.json", "the machine-readable record every station reads"),
    ("report/index.html", "the assembled report"),
)

#: AND PER PLUGIN, because a run mounts several methods and each owes its own result. Each is
#: a template of a RUN-RELATIVE path: the ledger and the section live in the plugin's own
#: directory (`kernels.plugin_out`), the rendered page beside the plugin's other pages in the
#: run's report directory (`paper.page_name`). The page was resolved under `kernels/<plugin>/`
#: before harness ADR-0017, where the reporter never writes it, so the station named it missing
#: on every run that had it.
REQUIRED_PER_PLUGIN = (
    ("kernels/{plugin}/FIGURE_REVIEW.jsonl", "the ledger of what was actually looked at"),
    ("kernels/{plugin}/PAPER.{plugin}.md", "this plugin's result section, written from its figures"),
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
            rel = tmpl.format(plugin=plug)
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
    """The scan set of the newest run that drew anything, and what has been looked at.

    Computed here as well as in the station so the GOAL can be printed as a count on every
    blocked round, including rounds blocked earlier than station 7 - the distance to the goal
    does not depend on which station happens to be in the way.
    """
    for r in sorted(runs, key=lambda p: p.name, reverse=True):
        want, seen, _done = _scan(r)
        if want:
            return want, seen
    return set(), set()


def _eye_total(runs):
    return len(_eye_set(runs)[0])


def _eye_done(runs):
    return len(_eye_set(runs)[1])


def select(stations, want):
    """The stations `--station` names: by number ("6b", "7") or by word ("eye", "paper")."""
    if not want:
        return list(stations)
    keys = [w.strip().lower() for w in str(want).split(",") if w.strip()]
    out = []
    for name, fn in stations:
        num, _, word = name.partition(" ")
        if any(k == num.lower() or k == word.lower() for k in keys):
            out.append((name, fn))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # ONE RUN, OR A DIRECTORY OF THEM. `--runs` is the loop as a project runs it - every run,
    # oldest to newest, so a station can clear a commit rather than a run. `--run` is the same
    # stations asked of ONE run, which is how the plugin maker asks them: `sch dev convert status
    # --run RUNDIR` declares each of the run-side stations as a test-phase stage whose command is
    # this script, so the loop is implemented once and read by two callers.
    ap.add_argument("--runs", type=Path, help="a directory holding run directories")
    ap.add_argument("--run", type=Path, help="one run directory")
    ap.add_argument("--round", type=int, default=0, help="which round this is, for the record")
    ap.add_argument("--station", default="",
                    help="only these stations, by number or word: '6b', '7,8', 'eye'")
    ap.add_argument("--json", action="store_true",
                    help="one JSON object - state, detail and next per station - for an agent "
                         "rather than the prose")
    a = ap.parse_args(argv)
    if bool(a.runs) == bool(a.run):
        ap.error("pass exactly one of --runs (a directory of runs) or --run (one run)")
    if a.run:
        runs = [a.run] if (a.run / "report.json").is_file() else []
        where = a.run
    else:
        runs = _runs(a.runs)
        where = a.runs
    if not runs:
        print(f"no run directory with a report.json at {where}", file=sys.stderr)
        return 2
    stations = select(STATIONS, a.station)
    if not stations:
        print(f"--station {a.station!r} names no station; the stations are "
              + ", ".join(n for n, _ in STATIONS), file=sys.stderr)
        return 2
    if not a.json:
        print(f"THE TEST LOOP — round {a.round or '?'} — {len(runs)} run(s) under {where}\n")
    first_blocked = None
    record = {}
    for name, fn in stations:
        try:
            state, detail, nxt = fn(runs)
        except Exception as e:                                            # noqa: BLE001
            state, detail, nxt = BLOCKED, f"station raised: {e}", ""
        record[name] = {"state": state, "detail": detail, "next": nxt}
        if not a.json:
            mark = "  ok  " if state == PASS else "BLOCKED"
            print(f"{mark}  {name:<12} {detail}")
            # ONE STATION ASKED: the help under it is one line, so the verdict stays within the
            # tail the maker keeps. The whole list is the round's, printed when the round is.
            if a.station and nxt:
                nxt = nxt.splitlines()[0]
            if nxt and state != PASS:
                print(f"          -> {nxt}")
            elif nxt:
                print(f"          note: {nxt}")
        if state != PASS and first_blocked is None:
            first_blocked = name
    if a.json:
        # THE SAME FACTS THE PROSE CARRIES, and nothing the prose does not. An agent reading
        # this gets the first blocked station, the count that is the goal, and the one next
        # command per station - which is what the prose was printing for a person.
        print(json.dumps({
            "runs": [r.name for r in runs],
            "stations": record,
            "first_blocked": first_blocked,
            "eye": {"done": _eye_done(runs), "total": _eye_total(runs)},
            "missing_outputs": [{"path": p, "why": w} for p, w in
                                missing_outputs(sorted(runs, key=lambda p: p.name)[-1])],
        }, indent=1))
        return 1 if first_blocked else 0
    # ONE STATION ASKED IS ONE STATION ANSWERED. `--station 6b` is the maker asking a question
    # whose answer it keeps as the command's tail; the round's goal restatement and its
    # missing-outputs block belong to the whole round and, printed after the station, they were
    # the tail - the station's own line, with the 43 issues and the 765 unmeasured panels it
    # named on the sealed reference, had scrolled off the top.
    if a.station:
        return 1 if first_blocked else 0
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
