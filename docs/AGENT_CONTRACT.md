# scProfile is run by an agent, end to end, and the agent is responsible for all of it
# except the measuring

This document exists because the division of labour in this tool is not obvious from the code,
and an agent that does not know it will do the wrong half — usually by writing prose the tool
should not contain, or by describing figures it never opened.

## There are two parties, and neither of them is a person

**The tool measures. The agent does everything else, end to end.**

The agent installs, plans, submits the job, watches it, opens every figure, records what it saw,
writes the result, carries it back into a run, and defends its claims. **There is no step inside
scProfile that waits for a human.** Any task that reads like a person's job — looking at the
pictures above all — is the agent's job.

**Human review is outside this tool.** It happens on the artifacts a run leaves behind, when it
is asked for. Nothing in scProfile schedules it, gates on it, or holds a run open for it, and no
command is marked for a human operator. The tool used to mark its analysis commands `[you]`,
which read as a person at a terminal and quietly left those steps to nobody: in this project's
whole history, 120 figure looks and `run --section` used ZERO times. The steps existed and the
phase never ran.

## The division

| The TOOL is responsible for | The AGENT is responsible for |
|---|---|
| fitting, and every number | deciding what the numbers mean |
| every figure, and its legend | **opening the figures** and recording what was seen |
| the evidence, gathered into one brief | the manuscript written from that brief |
| refusing what it cannot support | stating findings, and labelling hypotheses as hypotheses |
| recording what it declined to compare | saying so in the text, once |

Neither half is optional and neither substitutes for the other. A tool that writes produces
formulaic prose that cannot narrow to a focus; an agent that writes without the tool produces
numbers with no file behind them.

## Why the tool does not write

It used to. Headings were built from f-strings, the limitations paragraph was ranked and joined,
and a sentence was emitted whenever two scales diverged past a threshold. All of it was
traceable, reproducible, and not writing: it could not decide what mattered, synthesise across
levels, or narrow — which is the one thing the writing guidance asks for, since a section that
reports every pathway equally reports none.

So the generated section is a **placeholder that stands between the run sealing and the agent
writing**, and the rendered page says so in a banner the exit standard fails on. It is not a
fallback for a run nobody writes up, because every run is written up: the agent that ran it is
the author. `scprofile write` exists to hand that agent the evidence.

## Run the cycle to the end — there is no point at which you stop and ask

`scprofile agenda` lists six tasks and every one of them is unblocked by the one above it and by
nothing else. **There is no approval step inside this tool.** A cycle that halts after the
compute leaves a run with figures nobody opened and a section nobody wrote, which is the state
the agenda exists to get a run out of, not a state to report back from.

Finish it: submit, watch, collect, open every figure the brief lists (fan it out), write the
result, carry it back in with `--section`, record the claims. Then say what the result is.

Human review happens outside this tool, on the finished artifacts.

## The failure path is part of the cycle

A run that regressed, or lost a unit, **still seals, still writes a report, and still says most
of its tasks are done.** `scprofile agenda` reads the run's own records and surfaces two things
before the writing step, because both were walked past once:

- **A capacity regression is not automatically a breakage.** Deliberately removing a duplicated
  figure lowers the figure count and the guard reports it, correctly. The guard cannot know which
  it is; you can. Say which, in the run log, before writing anything up.
- **One failed unit downgrades every other unit's verdict.** A single instance failing produces a
  run-level diagnosis that marks all instances suspect, and the suspect count then reads as that
  many broken units. Read which unit actually failed; the rest of the run may be sound.

Two ordering rules follow, both paid for:

- **Settle the figure set before writing the section.** The paper numbers figures in order, so
  adding or removing one renumbers every citation after it — and a section written against the
  old set cites the wrong plates while reading perfectly.
- **Fix the figures before looking at them.** A review is bound to the image, so redrawing
  destroys it. A sweep taken before a fix round is a sweep thrown away.

**You should never have to remember what comes next.** Two commands answer it:

    scprofile next  --out <run>          # the single next action, with its command
    scprofile agenda --out <run>         # the whole cycle and the state of each step

`watch --wait` prints the next action itself the moment a job seals or fails, so the handoff
happens without being asked for — a watcher that reports a seal and then stops leaves the agent
at a dead end at exactly the moment the next step becomes available, and an agent at a dead end
goes and does something else.

And one thing about watching a job: **do not hand-roll the poll loop.**

    scprofile watch --out <run>          # what state is it in, right now
    scprofile watch --out <run> --wait   # block until sealed or failed

The run records its own job id in `RUNNING.txt` before it does any work, so nothing has to be
passed in. The reason this is a command and not three lines of shell: **the seal lags the queue.** A finished job leaves `qstat`
before its trap's write to a network filesystem is visible, so "job gone and no `SEALED.txt`" is
not a failure until you have re-checked. `FAILED.txt` is the marker that means failure.

## One run produces all of its output

**A run is a unit.** Its objects, its figures and its documents all come from ONE tool version,
and the run key names that version. Nothing else is a run.

So when the tool changes, **run the pipeline** — do not rebuild a part of an existing run. The
object cache makes this cheap: an edit that does not touch the inference span reuses every
fitted object, and a full run costs about the same as rebuilding the documents alone.

`scprofile report` exists to rebuild documents from `report.json`, and it is for a run whose
DOCUMENTS were lost or whose reporter was itself the thing being repaired — not for skipping a
run because the change looked small. Used casually it produces a directory whose figures came
from one commit and whose prose came from another, under a single run key that names only one of
them. That is not a faster run; it is an artifact nobody can trace, and it reads exactly like a
correct one.

*Cost: a partial rebuild pointed at the wrong run directory, produced a report, exited zero, and
the paper it was supposed to change looked unchanged - which was then investigated as a defect in
the tool. The tool was fine. The shortcut was not.*

## The writing phase, in order

    scprofile write   --out <run> [--plugin <p>]     # the brief: evidence, figures, template
    scprofile review  --out <run> --figure <f> --note "..."   # ONE PER FIGURE, before writing
    ...write...                                       # against .claude/skills/result-section
    scprofile run     --section <file>                # carry it back into the run

### Under a scheduler, the figures are not where you are

**PBS-HPC mode.** The run directory is on the cluster filesystem; whatever you open images with
is usually on another machine. "Open the figures" is then not an instruction you can follow, and
an agent in that position either writes a throwaway parser over the brief's markdown — the
in-house script this tool exists to make unnecessary — or writes about panels it never saw.

So the run writes the figure set as a **transfer list**: `kernels/<plugin>/FIGURES.txt`, one
run-relative path per line, in the order the paper numbers them. Any tool that reads a file of
paths takes it as it stands.

    rsync -a --files-from=<the list> <host>:<run>/ <a local directory>/
    # no rsync: tar -C <run> -T <run>/kernels/<plugin>/FIGURES.txt -czf figures.tgz

Bring the whole set across in **one** transfer, open every one from the local copy, and then
record each look **against the run directory on the cluster** — not against the copy. The ledger
lives with the run and binds a note to the sha256 of the image the run holds.

`scprofile agenda --out <run>` prints this with the paths filled in, for the mode the run is in.
The host names the list, the run root and the direction; it does not know your hostname or where
you keep files, and does not guess.

### The looking parallelises — let the tool cut the shards

Opening every panel is the slowest step in the cycle and the one most often skipped, and those
are the same fact: a task nobody can finish in one sitting gets a glance and a summary instead.
It is also the only step that parallelises without argument — the panels are independent, nothing
is computed, and the record is append-only. **So fan it out across several agents.**

    scprofile review --out <run> --plugin <p> --shards 4            # all four, to dispatch
    scprofile review --out <run> --plugin <p> --shards 4 --shard 1  # one agent's list

**Start with coverage, not volume.** A run draws one kind many times — a circle plot per unit,
a role heatmap per contrast — and a defect in a kind is present in every instance of it. Reading
in path order spends the whole budget inside the first few kinds: on one cohort here, 93 looks
covered 31 kinds and left 50 never opened at all.

    scprofile review --out <run> --plugin <p> --per-kind 2 --shards 4   # every kind, twice

Sweep everything afterwards. Before a fix round, the per-kind sweep is the only one worth doing:
a review dies when its image changes, so a full sweep before a redraw is thrown away.

**Do not divide the list yourself.** An invented split is how one figure gets two reviews and
another gets none — and the second is invisible, because the ledger simply goes on reporting it
as outstanding. The tool's split is disjoint, covers exactly what is still outstanding, and keeps
each unit's figures in one shard, because a differential panel means little without the arm
networks beside it.

Each agent opens its own shard and records its own looks against the same run. The ledger is
append-only and locked per write, so they may record at the same time. `scprofile agenda` says
how many shards the outstanding count is worth and stays quiet below the floor, where splitting
costs more than it saves.

**Step two is a step, not advice.** Every figure defect ever found in this project was found by
opening the image while the test suite was green: an encoding that contradicted its legend, a
ranking that hid the thing the panel was drawn for, labels driven off the axes by a fix for
labels. None of them is visible in a table, and none of them failed anything.

The review ledger binds a look to the image's **sha256**, so redrawing a figure destroys its
review and returns it to the outstanding list. `scprofile review --strict` exits non-zero while
anything is outstanding, which is what a gate reads.

## What an agent must not do

- **Write a number that is not in the run.** If it came from a scratch script, it is not a
  result; put the computation in the tool or leave the number out.
- **Describe a figure it has not opened.** The brief marks which are outstanding.
- **Invent a statistic, or soften one the method reports.** The wrapped method's own test is the
  statistic. Where it provides none — a difference of two differences has none — say so plainly
  and report the magnitude.
- **Downgrade a finding because it is inconvenient.** State it, with what it rests on.
- **Leave the section outside the run.** A section with no run key has citations that resolve to
  nothing and disappears with the session that produced it.

## Where the guidance lives

`.claude/skills/result-section/SKILL.md` is the general writing skill — the document's
architecture, the levels, headings, the two-scale rule, the limitations cap — and applies to
every plugin. Each plugin **declares** the template it writes with (`report.writing_template`),
which supplies what is specific to its method. The host never maps a plugin name to a template:
that is the one place where adding a second method quietly stops working.
