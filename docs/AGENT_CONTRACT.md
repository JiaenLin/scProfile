# scProfile is run by an agent, and the agent is responsible for these parts

This document exists because the division of labour in this tool is not obvious from the code,
and an agent that does not know it will do the wrong half — usually by writing prose the tool
should not contain, or by describing figures it never opened.

## The division

**The tool measures. The agent reads, looks, and writes.**

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

So the generated section is a **fallback for a run nobody writes up**, and it says so. The real
result comes from an agent, and `scprofile write` exists to hand that agent the evidence.

## The writing phase, in order

    scprofile write   --out <run> [--plugin <p>]     # the brief: evidence, figures, template
    scprofile review  --out <run> --figure <f> --note "..."   # ONE PER FIGURE, before writing
    ...write...                                       # against .claude/skills/result-section
    scprofile run     --section <file>                # carry it back into the run

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
