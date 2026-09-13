"""The eye comes before the pen: a look carries a verdict, the audit reads it, the pen waits.

THE INCONSISTENCY THIS CLOSES (harness ADR-0018). The loop's own rule is look -> fix -> rebuild ->
look again -> write, and the contract says "settle the figure set before writing the section".
The mechanism's order was look -> write: a note was prose no machine could count, `audited` read
only the machine's findings and came before the eye, the agenda's write task opened the moment
every look was RECORDED whatever the looks said, and a claim could cite a plate its own looker had
condemned an hour earlier. Blind 0004 did exactly that, and the reviewer withdrew or narrowed 32
of 33 claims.

So: `review --defect` marks a look that says the panel must change; `review.defects` and
`review.open_findings` read those beside the machine's residue; `audited` owes while either
exists or the scan set is unlooked; the agenda's write task and `paper --claim` refuse a figure
with an open finding, quoting it; the brief marks it. Checked on real files with real digests.

Run: python tests/test_the_eye_comes_before_the_pen.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import agenda as AG                                              # noqa: E402
from scprofile import brief as B                                                # noqa: E402
from scprofile import compose as C                                              # noqa: E402
from scprofile import paper as PA                                               # noqa: E402
from scprofile import review as R                                               # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def refuses(fn, *a, **k):
    try:
        fn(*a, **k)
        return ""
    except (PA.Refused, R.Refused) as e:
        return str(e) or "refused"


F1, F2, F3 = ("kernels/p/U1/figures/F1_a.png", "kernels/p/U1/figures/F2_b.png",
              "kernels/p/U1/figures/F3_c.png")
GOOD = "The share of one pathway rises in one arm and falls in the other, by about nine points"
NOTE_BAD = "the two panels never say which is which arm, so the comparison cannot be read"
NOTE_OK = "two arms side by side, each labelled, the scale shared and numbered"


def make_run(td, residue_on=("F2_b",)):
    run = Path(td) / "20260101T000000Z__scprofile-abc1234__stage"
    figs = run / "kernels" / "p" / "U1" / "figures"
    figs.mkdir(parents=True)
    for f in ("F1_a", "F2_b", "F3_c"):
        (figs / f"{f}.png").write_bytes(b"\x89PNG" + f.encode())
    recs = [{"id": f, "path": f"kernels/p/U1/figures/{f}.png",
             "audit": ([{"code": "text_overlap", "detail": "'4000' over '25' — 92% of the "
                                                            "smaller, at (776,80)px"}]
                       if f in residue_on else []),
             **({"repairs": [{"code": "axis_offset", "what": "the bottom spine moved"}]}
                if f in residue_on else {})}
            for f in ("F1_a", "F2_b", "F3_c")]
    (run / "report.json").write_text(json.dumps({"kernels": {"p": {"figures": recs}}}))
    (run / "kernels" / "p" / "FIGURES.txt").write_text(F1 + "\n")
    return run


with tempfile.TemporaryDirectory() as td:
    run = make_run(td)

    print("a look carries a verdict, and the verdict is bound to the image")
    rec = R.record(run, F1, NOTE_BAD, reviewer="looker-1", plugin="p", defect=True)
    ck("a defect look is recorded as one", rec.get("defect") is True, str(rec))
    d = R.defects(run, "p")
    ck("and listed with the looker's words", [x[0] for x in d] == [F1] and NOTE_BAD in d[0][1],
       str(d))
    plain = R.record(run, F3, NOTE_OK, reviewer="looker-1", plugin="p")
    ck("a look without the flag describes and condemns nothing",
       "defect" not in plain and [x[0] for x in R.defects(run, "p")] == [F1], str(plain))
    R.record(run, F1, NOTE_OK, reviewer="looker-2", plugin="p")
    ck("a later clean look on the same bytes supersedes the defect", R.defects(run, "p") == [],
       str(R.defects(run, "p")))
    R.record(run, F1, NOTE_BAD, reviewer="looker-2", plugin="p", defect=True)
    (run / F1).write_bytes(b"\x89PNG redrawn")
    ck("and a redraw clears it - the look was of an image that no longer exists",
       R.defects(run, "p") == [], str(R.defects(run, "p")))
    R.record(run, F1, NOTE_BAD, reviewer="looker-2", plugin="p", defect=True)

    print("\nthe open findings are the machine's residue and the eye's defects, together")
    of = R.open_findings(run, "p")
    ck("both figures are named", set(of) == {F1, F2}, str(sorted(of)))
    ck("the machine's finding carries its code and where",
       any("text_overlap" in w and "4000" in w for w in of.get(F2, [])), str(of.get(F2)))
    ck("the eye's carries the looker and the words",
       any("looker-2" in w and NOTE_BAD in w for w in of.get(F1, [])), str(of.get(F1)))
    ck("a clean figure carries none", F3 not in of)

    print("\nthe pen waits: a claim cannot rest on a plate the run's own record calls wrong")
    why = refuses(PA.claim, run, GOOD, [F1], author="w", plugin="p")
    ck("a claim citing an eye-marked plate is refused", bool(why), "it was recorded")
    ck("and the refusal quotes the finding", NOTE_BAD in why, why)
    why2 = refuses(PA.claim, run, GOOD, [F3, F2], author="w", plugin="p")
    ck("a claim citing a plate with machine residue is refused too, naming the code",
       "text_overlap" in why2, why2)
    ok = PA.claim(run, GOOD, [F3], author="w", plugin="p")
    ck("a claim on a clean plate is recorded", bool(ok.get("id")))
    head, cmd = PA.next_step(run, "p")
    ck("the next step names the open findings before anything about writing",
       "open finding" in head and "2" in head and "review" in cmd, f"{head} | {cmd}")

    print("\nthe agenda's write task is blocked while a finding is open, and names it")
    C.figure_index = lambda run, plugin, spec=None, design=None: {F1: 1, F2: 2}
    tasks = {t["id"]: t for t in AG.tasks(run, "p", how=AG.LOCAL)}
    ck("write is BLOCKED although every figure of the scan set has a look",
       tasks["write"]["state"] == AG.BLOCKED, str(tasks["write"]["state"]))
    ck("and the reason names the figures and says fix, rerun, look again",
       "F1_a" in tasks["write"]["why"] and "F2_b" in tasks["write"]["why"]
       and "look again" in tasks["write"]["why"], tasks["write"]["why"])
    ck("the look task tells the looker how to mark a defect", "--defect" in tasks["look"]["do"],
       tasks["look"]["do"])

    print("\nthe brief marks every figure with an open finding")
    C.findings = lambda run, plugin, spec: {"age": {"ratio": 2.0, "reference": "y",
                                                    "against": "a", "ratio_per_cell": 1.5,
                                                    "n_significant": 3, "n_tested": 4}}
    C._controls = lambda run: {"age": "y"}
    C._order = lambda f, design, controls=None: ["age"]
    p = B.write_brief(run, "p", spec={"report": {"subject": "widgets"}}, design={})
    txt = Path(p).read_text(encoding="utf-8") if p else ""
    line2 = [l for l in txt.splitlines() if "F2_b" in l]
    ck("the figure with residue is marked", bool(line2) and "open finding" in line2[0],
       str(line2))
    line1 = [l for l in txt.splitlines() if "F1_a" in l and "Figure" in l]
    ck("and so is the eye-marked one, with the words",
       bool(line1) and "open finding" in line1[0] and "which arm" in line1[0], str(line1))

    print("\nwhen the findings clear, the pen opens")
    R.record(run, F1, NOTE_OK, reviewer="looker-3", plugin="p")
    run2 = make_run(Path(td) / "second", residue_on=())
    for f in (F1, F2, F3):
        R.record(run2, f, NOTE_OK + " " + f[-8:], reviewer="looker-3", plugin="p")
    ck("no residue and no defect: nothing is open", R.open_findings(run2, "p") == {},
       str(R.open_findings(run2, "p")))
    tasks2 = {t["id"]: t for t in AG.tasks(run2, "p", how=AG.LOCAL)}
    ck("and the write task is pending", tasks2["write"]["state"] == AG.PENDING,
       str(tasks2["write"]))

    print("\nthe command carries the flag, and the status prints what is open")
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    pr = subprocess.run([sys.executable, "-m", "scprofile.cli", "review", "--out", str(run2),
                         "--plugin", "p", "--figure", F2, "--note", NOTE_BAD, "--reviewer",
                         "l", "--defect"], capture_output=True, text=True, env=env, cwd=ROOT)
    ck("review --defect records", pr.returncode == 0 and "recorded" in pr.stdout,
       pr.stdout + pr.stderr)
    ck("and the record says defect", R.read_ledger(run2, "p")[F2].get("defect") is True)
    pr = subprocess.run([sys.executable, "-m", "scprofile.cli", "review", "--out", str(run2),
                         "--plugin", "p"], capture_output=True, text=True, env=env, cwd=ROOT)
    ck("the status names the open finding", "open finding" in pr.stdout and "F2_b" in pr.stdout,
       pr.stdout[-400:])

print("\nthe stage order says the same: the eye, then the audit that reads it, then the pen")
dev = (ROOT / "DEVPOINTS.yaml").read_text(encoding="utf-8")
ck("looked_at is declared before audited",
   dev.index("- name: looked_at") < dev.index("- name: audited"))
ck("and audited before written", dev.index("- name: audited") < dev.index("- name: written"))
ck("looked_at says how a defect is marked", "--defect" in dev[dev.index("- name: looked_at"):
                                                              dev.index("- name: audited")])

print("\n" + ("the eye comes first" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
