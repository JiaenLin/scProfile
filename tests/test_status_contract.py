#!/usr/bin/env python3
"""What a run leaves behind, written by the tool: STATUS.json first as partial, last with the
outcome; RUNNING replaced by SEALED or FAILED; the commit read from .git by file; a refusal that
is a record with its fix; state_version declared by every shipped plugin.

Stdlib only. Run as a script; exit 1 on any failure.
"""
from __future__ import annotations

import io
import json
import re
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

fails = []


def ck(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f"   {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


from scprofile import status as ST  # noqa: E402

print("status writers")
with tempfile.TemporaryDirectory() as td:
    out = Path(td) / "run"
    ST.begin(out, "run", version="0.0.0", state_version=1, sees=[], cannot_show={})
    rec = json.loads((out / "STATUS.json").read_text())
    ck("run: partial first, RUNNING.txt standing", rec["status"] == "partial" and (out / "RUNNING.txt").exists())
    ck("commit read by file, or None", rec["commit"] is None or re.fullmatch(r"[0-9a-f]{40}", rec["commit"]) is not None)
    (out / "report.json").write_text("{}")
    rec = ST.finish(out, "run", status="ok", headline="done", exit_code=0, expected=["report.json", "RUN_CARD.json"])
    ck("a missing expected product is failed, named", rec["status"] == "failed" and rec["missing"] == ["RUN_CARD.json"]
       and (out / "FAILED.txt").exists())
    (out / "RUN_CARD.json").write_text("{}")
    rec = ST.finish(out, "run", status="ok", headline="done", exit_code=0, expected=["report.json", "RUN_CARD.json"])
    ck("every product present seals", rec["status"] == "ok" and (out / "SEALED.txt").exists()
       and not (out / "FAILED.txt").exists() and not (out / "RUNNING.txt").exists())
    ck("the seal names the commit as the job script does", "tool=" in (out / "SEALED.txt").read_text())
    ST.refuse("unknown kernel", fix="name one of the discovered kernels")
    rec = ST.finish(out, "run", status="refused", headline="refused", exit_code=2)
    ck("refused carries the recorded reason and fix", rec["refusal"]["reason"] == "unknown kernel"
       and rec["refusal"]["fix"] == "name one of the discovered kernels" and (out / "FAILED.txt").exists())
    ST.begin(out, "review", version="0", state_version=1, sees=[], cannot_show={})
    ST.finish(out, "review", status="ok", headline="looked", exit_code=0)
    ck("another command seals under its own name and leaves the run's record alone",
       (out / "SEALED.review.txt").exists() and (out / "FAILED.txt").exists()
       and json.loads((out / "STATUS.json").read_text())["status"] == "refused")
    ck("status files are not products", all(not p["path"].startswith(("STATUS", "SEALED", "FAILED")) for p in rec["products"]))

print("\nthrough the CLI: a host refusal is a status, not only a line")
from scprofile import cli  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    out = Path(td) / "r"
    o, e = io.StringIO(), io.StringIO()
    with redirect_stdout(o), redirect_stderr(e):
        try:
            rc = cli.main(["run", "--h5ad", str(Path(td) / "nonexistent.h5ad"), "--out", str(out),
                           "--kernel", "no_such_kernel", "--prefix", str(Path(td) / "env")])
        except SystemExit as ex:
            rc = ex.code
    st = out / "STATUS.json"
    ck("exit 2", rc == 2, e.getvalue()[-300:])
    ck("STATUS.json refused with a fix; FAILED.txt", st.exists() and json.loads(st.read_text())["status"] == "refused"
       and json.loads(st.read_text())["refusal"]["fix"] and (out / "FAILED.txt").exists(), e.getvalue()[-300:])
    ck("no traceback", "Traceback" not in o.getvalue() + e.getvalue())

print("\nevery shipped plugin declares state_version")
for f in sorted((ROOT / "kernels").glob("*.py")):
    src = f.read_text(encoding="utf-8")
    ck(f"{f.name} declares an integer state_version", re.search(r'"state_version":\s*\d+,', src) is not None)

print("")

# A READING COMMAND ASKED OF A SEALED RUN. The seal makes every file read-only, including the
# stamps this contract wrote when the run was made - and the next `capacity --promised` asked of
# the run died in `begin`, rewriting STATUS.capacity.json, before doing any of its own reading.
# Two of the maker's six run-side stages were answered "PermissionError" on the sealed reference.
# A sealed run is a run the contract should be able to READ; the stamp is not rewritten and the
# command says so on stderr, once.
print("a sealed run can still be read")
with tempfile.TemporaryDirectory() as td:
    out = Path(td) / "sealed"
    (out / "kernels").mkdir(parents=True)
    for name in ("STATUS.capacity.json", "SEALED.capacity.txt"):
        (out / name).write_text("{}", encoding="utf-8")
        (out / name).chmod(0o400)
    from scprofile import cli
    buf_out, buf_err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            rc = cli.main(["capacity", "--out", str(out), "--promised"])
    except PermissionError as e:
        rc = f"raised {e}"
    ck("capacity --promised on a sealed run returns its own verdict", rc == 0, str(rc))
    ck("and says the stamp was not rewritten", "sealed" in buf_err.getvalue().lower(), buf_err.getvalue()[-200:])
    ck("and the sealed stamp is untouched", (out / "STATUS.capacity.json").read_text() == "{}")
    for name in ("STATUS.capacity.json", "SEALED.capacity.txt"):
        (out / name).chmod(0o600)

if fails:
    print(f"FAIL: {len(fails)}")
    raise SystemExit(1)
print("\nthe commit of an exported tree is read from HEAD.txt")
# A TREE EXPORTED WITH `git archive` HAS NO .git. The cluster's cellchat-only tree is one, and
# every seal it wrote read `commit=unidentified` while the run key beside it named the commit.
# The export convention writes the short hash to HEAD.txt at the tree's root; that is the second
# place the commit lives, and the only one an export has.
with tempfile.TemporaryDirectory() as td:
    tree = Path(td)
    (tree / "HEAD.txt").write_text("344993d\n", encoding="utf-8")
    ck("HEAD.txt answers where .git is absent", ST.commit(tree) == "344993d",
       repr(ST.commit(tree)))
    (tree / "HEAD.txt").unlink()
    ck("neither .git nor HEAD.txt is None, not a crash", ST.commit(tree) is None)
    ck("the tool's own tree still answers from .git", ST.commit() is not None
       and re.fullmatch(r"[0-9a-f]{7,40}", str(ST.commit())) is not None, repr(ST.commit()))

if fails:
    print(f"\nFAILED: {fails}")
    sys.exit(1)
print("PASS: the status contract holds")
