"""What a run leaves behind so that a reader who did not watch it can tell four states apart:
ok, partial, refused, failed — from the filesystem alone, written by the TOOL.

    STATUS.json   written FIRST as `partial`, rewritten LAST with the outcome and the products
    RUNNING.txt   at start; replaced at exit by SEALED.txt (exit 0 and every expected product
                  present) or FAILED.txt (anything else, naming what is missing)

`run` owns the run directory and writes the bare names. Every other command that takes --out
writes beside its own output under the command's name — STATUS.report.json, SEALED.review.txt —
so `review` cannot overwrite the run's own record. `setup/dev_cycle.pbs` writes a seal too; it is
the second witness, and until now it was the only one, so a run launched any other way was
unsealed. The commit is read from .git by FILE: compute nodes have no git binary. Stdlib only;
the same shape as the status contract shared with the tools this one is orchestrated beside.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path

CONTRACT = "1.0"
STATUSES = ("ok", "partial", "refused", "failed")
ROOT = Path(__file__).resolve().parents[1]
LAST_REFUSAL: dict = {}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def commit() -> str | None:
    git = ROOT / ".git"
    try:
        if git.is_file():
            git = Path(git.read_text().split(":", 1)[1].strip())
        head = (git / "HEAD").read_text().strip()
        if head.startswith("ref:"):
            ref = head.split(None, 1)[1]
            f = git / ref
            if f.exists():
                return f.read_text().strip()
            packed = git / "packed-refs"
            if packed.exists():
                for ln in packed.read_text().splitlines():
                    if ln.endswith(" " + ref):
                        return ln.split()[0]
            return None
        return head
    except OSError:
        return None


def job() -> dict:
    for var, name in (("PBS_JOBID", "pbs"), ("SLURM_JOB_ID", "slurm")):
        if os.environ.get(var):
            return {"scheduler": name, "id": os.environ[var], "host": socket.gethostname()}
    return {"scheduler": None, "id": None, "host": socket.gethostname()}


def refuse(reason: str, fix: str = "") -> int:
    """Record the reason and the fix for the status file; the caller prints what it always did."""
    LAST_REFUSAL.clear()
    LAST_REFUSAL.update({"reason": reason, "fix": fix})
    return 2


def _names(cmd: str) -> tuple:
    if cmd == "run":
        return "STATUS.json", "RUNNING.txt", "SEALED.txt", "FAILED.txt"
    return f"STATUS.{cmd}.json", f"RUNNING.{cmd}.txt", f"SEALED.{cmd}.txt", f"FAILED.{cmd}.txt"


def _rel(path: Path, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def products_of(out: Path) -> list:
    res = []
    if not out.is_dir():
        return res
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.suffix in (".json", ".csv", ".tsv", ".html", ".h5ad", ".md", ".jsonl") \
                and not p.name.startswith(("STATUS", "RUNNING", "SEALED", "FAILED")) \
                and "cache" not in p.relative_to(out).parts:
            res.append({"path": _rel(p, out), "bytes": p.stat().st_size})
            if len(res) >= 2000:
                break
    return res


def begin(out: Path, cmd: str, *, version: str, state_version: int, sees: list, cannot_show: dict | list,
          argv: list | None = None) -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    st, run, _, _ = _names(cmd)
    rec = {"contract": CONTRACT, "tool": "scprofile", "command": cmd, "version": version,
           "commit": commit(), "state_version": state_version, "status": "partial",
           "headline": "started", "started": _now(), "finished": None, "job": job(),
           "python": sys.version.split()[0], "argv": list(argv if argv is not None else sys.argv),
           "products": [], "absent": [], "refusal": None, "sees": list(sees), "escapes": [],
           "cannot_show": cannot_show, "wrapped_versions": {}}
    (out / st).write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8")
    (out / run).write_text(f"started={rec['started']}\njobid={rec['job']['id'] or 'none'}\n"
                           f"host={rec['job']['host']}\ncommit={rec['commit'] or 'unidentified'}\n"
                           f"command={cmd}\n", encoding="utf-8")
    return out / st


def finish(out: Path, cmd: str, *, status: str, headline: str, exit_code: int,
           refusal: dict | None = None, expected: list | None = None,
           escapes: list | None = None, wrapped_versions: dict | None = None) -> dict:
    if status not in STATUSES:
        raise ValueError(f"status {status!r} is not one of {STATUSES}")
    out = Path(out)
    st, run, sealed_n, failed_n = _names(cmd)
    p = out / st
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rec = {"contract": CONTRACT, "tool": "scprofile", "command": cmd, "started": None, "job": job()}
    products = products_of(out)
    present = {x["path"] for x in products if x["bytes"] > 0}
    missing = [e for e in (expected or []) if e not in present]
    if status == "ok" and missing:
        status = "failed"
        headline = f"{headline}; missing products: {', '.join(missing)}"
    if status == "refused":
        refusal = dict(refusal or LAST_REFUSAL or {})
        refusal.setdefault("reason", headline)
        refusal.setdefault("fix", "the refusal names what to change; read the line above it")
    rec.update({"status": status, "headline": headline, "finished": _now(), "exit": exit_code,
                "products": products, "missing": missing,
                "refusal": refusal if status == "refused" else None,
                "escapes": list(escapes if escapes is not None else rec.get("escapes") or []),
                "wrapped_versions": dict(wrapped_versions or rec.get("wrapped_versions") or {})})
    p.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8")
    sealed = status == "ok" and exit_code == 0 and not missing
    seal = out / (sealed_n if sealed else failed_n)
    lines = [f"exit={exit_code}", f"status={status}", f"command={cmd}",
             f"jobid={(rec.get('job') or {}).get('id') or 'none'}",
             f"commit={rec.get('commit') or 'unidentified'}", f"tool={rec.get('commit') or 'unidentified'}",
             f"started={rec.get('started')}", f"finished={rec['finished']}", f"host={socket.gethostname()}",
             "products=" + " ".join(x["path"] for x in products[:60])]
    if missing:
        lines.append("missing=" + " ".join(missing))
    seal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    other = out / (failed_n if sealed else sealed_n)
    if other.exists():
        other.unlink()
    if (out / run).exists():
        (out / run).unlink()
    return rec
