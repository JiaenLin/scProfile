"""A job template asks for what it needs and leaves the QUEUE to the site that runs it.

A QUEUE IS A SITE'S NAME FOR A PLACE ON ITS OWN SCHEDULER. Every template in `setup/` named one
(`#PBS -q <queue>`), so the template only worked where a queue of that name existed, and the name
was this site's string in a tool that runs anywhere. On another site `qsub` refuses an unknown
queue; on this one the name chose the place for the submitter, and a reader took it for a
requirement of the tool.

WHAT THE TEMPLATE STATES IS THE REQUEST - cores, memory, walltime - because that is the tool's to
know. Which queue serves that request is the site's: named at submission with `qsub -q <queue>`
(the one whose `resources_max` covers the request: `qstat -Q -f <queue>`), or decided by the
server's default (often a routing queue that places a job by what it asks for).

HOW QSUB READS A TEMPLATE, and so how this reads it: every `#PBS` line before the first line
that is neither blank nor a comment is a directive; a directive after that line is ignored. A
queue named there is the queue a submission without `-q` gets. qsub cannot run on a workstation,
so this reads the block exactly as it does, and then asks bash, the template's other reader, to
parse the whole file.
"""
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = sorted((ROOT / "setup").glob("*.pbs"))
FAILURES = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" - {detail}" if not cond and detail else ""))
    if not cond:
        FAILURES.append(name)


def directives(text: str) -> list:
    """The directive block as qsub reads it: (line number, option tokens) of every `#PBS` line
    before the first executable line. A comment or a blank line does not end the block; the
    interpreter line is a comment like any other."""
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if s.startswith("#PBS"):
            out.append((n, shlex.split(s[len("#PBS"):], comments=False)))
            continue
        if not s or s.startswith("#"):
            continue
        break
    return out


def queue_of(block: list):
    """The queue a submission WITHOUT `-q` gets from the directives: None means the site's."""
    q = None
    for _, toks in block:
        for i, t in enumerate(toks):
            if t == "-q" and i + 1 < len(toks):
                q = toks[i + 1]
            elif t.startswith("-q") and len(t) > 2:
                q = t[2:]
    return q


def requests(block: list) -> set:
    """The resources the directives request, by name (`ncpus`, `mem`, `walltime`, ...)."""
    names = set()
    for _, toks in block:
        for i, t in enumerate(toks):
            if t == "-l" and i + 1 < len(toks):
                for part in re.split(r"[:,]", toks[i + 1]):
                    if "=" in part:
                        names.add(part.split("=", 1)[0].strip())
    return names


print("\nthe reader itself: a queue it would miss is a queue it would pass")
_named = "#!/bin/bash\n#PBS -N x\n# a comment does not end the block\n#PBS -q aqueue\n#PBS -l select=1:ncpus=2:mem=4gb\n"
_late = "#!/bin/bash\n#PBS -l walltime=01:00:00\necho start\n#PBS -q aqueue\n"
ck("a queue named in the block is read", queue_of(directives(_named)) == "aqueue")
ck("a queue written as one token is read", queue_of(directives("#PBS -qaqueue\n")) == "aqueue")
ck("a `#PBS` line after the first command is not a directive, as in qsub",
   queue_of(directives(_late)) is None and requests(directives(_late)) == {"walltime"})
ck("the request is read as named resources", requests(directives(_named)) >= {"ncpus", "mem"})

print(f"\nevery job template in setup/ ({len(TEMPLATES)}) leaves the queue to the site")
ck("the templates were found", len(TEMPLATES) >= 5, f"{len(TEMPLATES)} found")
for t in TEMPLATES:
    text = t.read_text(encoding="utf-8")
    block = directives(text)
    rel = t.relative_to(ROOT).as_posix()
    q = queue_of(block)
    ck(f"{rel} names no queue in its directives", q is None,
       f"`-q {q}` at line {next(n for n, toks in block if any(x.startswith('-q') for x in toks))}"
       if q else "")
    got = requests(block)
    ck(f"{rel} still states its request (ncpus, mem, walltime)",
       {"ncpus", "mem", "walltime"} <= got, f"requests {sorted(got)}")
    ck(f"{rel} says how the queue is given (`qsub -q <queue>`)", "qsub -q <queue>" in text)
    if shutil.which("bash"):
        r = subprocess.run(["bash", "-n", str(t)], capture_output=True, text=True)
        ck(f"{rel} parses as bash", r.returncode == 0, r.stderr.strip()[:200])

if FAILURES:
    print(f"\nFAIL: {len(FAILURES)} check(s)")
    sys.exit(1)
print("\nok: every job template states its request and leaves the queue to the site")
