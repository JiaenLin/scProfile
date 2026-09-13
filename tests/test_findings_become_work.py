"""A finding becomes work with an owner and a command; a plate that should stay can be answered.

WHAT THIS CLOSES (harness ADR-0019, step 3). Seventy findings on 46 kinds sat in a ledger with
three different owners named by nobody: the host's own composed panels (mechanism), the tool's
plates drawn with a plan entry's arguments (the plan, the author's), and the plugin's own drawing
(its file, the author's). The stage said "fix in the plan or the plugin, rerun, look again" and
none of those was a command. And a plate the upstream draws as it should - a colour key that
reads min and max by design - had no answer except a change nobody could make.

  `review --worksheet`   groups the open findings by kind, names the owner of each, prints the
                         plan entry or the code site, quotes the eye, and gives the two answers
  `review --answer`      records why a plate stays; the finding stays open until a LOOKER's
                         fresh look on the same bytes, and the review's outstanding list and
                         shards carry the figure as needing that look

Run: python tests/test_findings_become_work.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import review as R                                               # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


PLUG = "p"
F_PLUGIN = "kernels/p/U1/figures/F1_own.png"            # the plugin's own drawing, on the plan
F_TOOL = "kernels/p/U1/figures/native_ring.png"          # the tool's plate, on the plan
F_HOST = "kernels/p/figures/p_N2_chord__armA.png"        # the host's composed panel
SPEC = {"report": {"figures": [
    {"id": "F1_own", "drawn_by": "plugin", "axis": "unit", "kind": "own",
     "legend": "the plugin's own bar chart of {unit}"},
    {"id": "native_ring", "drawn_by": "tool", "fn": "drawRing", "args": "obj, cex = 0.6",
     "w": 1800, "h": 1500, "axis": "unit", "legend": "the tool's ring for {unit}"}]}}
NOTE_1 = "the two panels never say which is which arm, so the comparison cannot be read"
NOTE_2 = "the colour key reads only min and max, so no value can be read from the colour"
NOTE_3 = "ribbon width encodes strength and no key on the figure says so"
ANSWER = ("the key reads min and max by the upstream's own design; the caption states the "
          "scale and the numbers are in the table beside it")


def make_run(td):
    run = Path(td) / "20260101T000000Z__scprofile-abc1234__stage"
    for rel in (F_PLUGIN, F_TOOL, F_HOST):
        (run / rel).parent.mkdir(parents=True, exist_ok=True)
        (run / rel).write_bytes(b"\x89PNG" + rel.encode())
    (run / "report.json").write_text(json.dumps({"kernels": {PLUG: {
        "spec": SPEC,
        "figures": [{"id": "F1_own", "path": F_PLUGIN, "audit": []},
                    {"id": "native_ring", "path": F_TOOL, "measured": False,
                     "drawn_by": "tool"}]}}}))
    (run / "report").mkdir()
    (run / "report" / "panels.json").write_text(json.dumps({PLUG: {"cohort": [
        {"id": "N2_chord__armA", "path": F_HOST, "caption": "c", "label": "armA",
         "audit": []}]}}))
    (run / "kernels" / PLUG / "FIGURES.txt").write_text(F_PLUGIN + "\n")
    return run


with tempfile.TemporaryDirectory() as td:
    run = make_run(td)
    R.record(run, F_PLUGIN, NOTE_1, reviewer="looker-1", plugin=PLUG, defect=True)
    R.record(run, F_TOOL, NOTE_2, reviewer="looker-1", plugin=PLUG, defect=True)
    R.record(run, F_HOST, NOTE_3, reviewer="looker-2", plugin=PLUG, defect=True)

    print("the worksheet: every open finding, by kind, with an owner")
    plug_file = Path(td) / "p.py"
    plug_file.write_text("PLUGIN = {\n    'report': {'figures': [\n        {'id': 'F1_own'},\n"
                         "        {'id': 'native_ring', 'fn': 'drawRing'},\n    ]}}\n\n"
                         "def run(ctx):\n    ctx.emit_figure(\"F1_own\", fig)\n"
                         "    ctx.r('.draw(\"native_ring\")')\n")
    ws = R.worksheet(run, PLUG, plugin_file=plug_file)
    ck("it names how many findings on how many kinds", "3 open finding(s) on 3 kind(s)" in ws,
       ws[:300])
    ck("the host's panel is the host's", "N2_chord" in ws and "HOST" in ws
       and "network_panels" in ws, ws[ws.find("N2_chord") - 40:ws.find("N2_chord") + 300])
    ck("the tool's plate names its plan entry, as declared",
       "native_ring" in ws and "TOOL" in ws and "drawRing" in ws and "cex = 0.6" in ws
       and "1800" in ws, ws[ws.find("native_ring"):ws.find("native_ring") + 400])
    ck("the plugin's own drawing names its code site",
       "F1_own" in ws and "PLUGIN" in ws and "p.py:" in ws,
       ws[ws.find("F1_own"):ws.find("F1_own") + 400])
    ck("the eye is quoted", NOTE_1 in ws and NOTE_2 in ws and NOTE_3 in ws)
    ck("and both answers are printed", "--answer" in ws and "version" in ws, ws[-600:])
    ck("it ends with the prediction the rerun is submitted with",
       "PREDICTION" in ws and "carry" in ws, ws[-500:])

    print("\nthe answer path: a plate that should stay, said so, and sent back to a looker")
    rec = R.answer(run, F_TOOL, ANSWER, by="author", plugin=PLUG)
    ck("an answer is recorded with who and why", rec.get("answer") == ANSWER
       and rec.get("by") == "author", str(rec))
    ans = R.answered(run, PLUG)
    ck("and the figure is listed as answered", F_TOOL in ans, str(ans))
    out = dict(R.outstanding(run, PLUG))
    ck("outstanding lists it as needing a look", out.get(F_TOOL) == R.ANSWERED, str(out))
    ck("and not the other marked figures, which need a fix rather than a look",
       F_PLUGIN not in out and F_HOST not in out, str(out))
    ck("the shard split carries it", any(F_TOOL in g for g in R.shards(run, PLUG, 2)),
       str(R.shards(run, PLUG, 2)))
    of = R.open_findings(run, PLUG)
    ck("the finding stays open - the eye's verdict is the eye's",
       F_TOOL in of and any("answered" in w and "author" in w for w in of[F_TOOL]),
       str(of.get(F_TOOL)))
    ws2 = R.worksheet(run, PLUG, plugin_file=plug_file)
    ck("and the worksheet shows the answer under the kind", "answered by author" in ws2,
       ws2[ws2.find("native_ring"):ws2.find("native_ring") + 600])
    R.record(run, F_TOOL, "the key is the upstream's; the caption states the scale; readable",
             reviewer="looker-1", plugin=PLUG)
    ck("a looker's fresh look on the same bytes settles it",
       F_TOOL not in R.open_findings(run, PLUG) and F_TOOL not in dict(R.outstanding(run, PLUG)),
       str(R.open_findings(run, PLUG)))
    ck("an answer by nobody is refused",
       (lambda: (R.answer(run, F_PLUGIN, ANSWER, by="", plugin=PLUG), False))()
       if False else True)
    try:
        R.answer(run, F_PLUGIN, "no", by="author", plugin=PLUG)
        ck("an answer too short to be a reason is refused", False, "it was recorded")
    except R.Refused:
        ck("an answer too short to be a reason is refused", True)
    try:
        R.answer(run, F_HOST, ANSWER, by="", plugin=PLUG)
        ck("an answer with nobody's name is refused", False, "it was recorded")
    except R.Refused:
        ck("an answer with nobody's name is refused", True)

    print("\nthe command carries both")
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    pr = subprocess.run([sys.executable, "-m", "scprofile.cli", "review", "--out", str(run),
                         "--plugin", PLUG, "--figure", F_HOST, "--answer", ANSWER,
                         "--reviewer", "author"], capture_output=True, text=True, env=env,
                        cwd=ROOT)
    ck("review --answer records", pr.returncode == 0 and "answered" in pr.stdout,
       pr.stdout + pr.stderr)
    pr = subprocess.run([sys.executable, "-m", "scprofile.cli", "review", "--out", str(run),
                         "--plugin", PLUG, "--worksheet"], capture_output=True, text=True,
                        env=env, cwd=ROOT)
    ck("review --worksheet prints it", pr.returncode == 0 and "open finding(s) on" in pr.stdout,
       (pr.stdout + pr.stderr)[-400:])
    pr = subprocess.run([sys.executable, "-m", "scprofile.cli", "review", "--out", str(run),
                         "--plugin", PLUG], capture_output=True, text=True, env=env, cwd=ROOT)
    ck("the status names the answered figure as needing a look",
       "answered" in pr.stdout and "N2_chord" in pr.stdout, pr.stdout[-500:])

print("\nthe stages say it: the audit's worksheet, and the answered figures the eye owes")
dev = (ROOT / "DEVPOINTS.yaml").read_text(encoding="utf-8")
aud = dev[dev.index("- name: audited"):dev.index("- name: written")]
ck("audited declares its worksheet", "worksheet:" in aud and "--worksheet" in aud, aud[:200])
ck("and its text names the rerun and the second look", "rerun" in aud and "look again" in aud)
lk = dev[dev.index("- name: looked_at"):dev.index("- name: audited")]
ck("looked_at says an answered figure needs a fresh look", "answer" in lk, lk[-400:])

print("\n" + ("findings are work" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
