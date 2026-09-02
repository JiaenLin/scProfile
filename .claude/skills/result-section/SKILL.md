---
name: result-section
description: Turn a run's composed findings into a result section that reads as a research article, without inventing anything
---

# Writing the result section

> **Where this lives.** `scProfile/.claude/skills/result-section/SKILL.md`, version-controlled and
> pushed. Symlink it into `~/.claude/skills/` so it loads in every project, not only inside this
> repository.

Every rule here was paid for on a real manuscript. Each is stated with what it cost.

## The input already exists — do not go looking for numbers

**Every run writes a composed section** at `kernels/<plugin>/PAPER.<plugin>.md`, built from that
run's own tables, with one subsection per comparison the design supports and every number naming
the file it came from. **Start there. Do not compute anything yourself.**

*What this replaces: numbers were read off tables by hand, into a scratch script, and typed into
prose. Nothing about that document was reproducible, and a fresh run produced no document at
all — the tool's own rule about scratch probes, broken on the manuscript itself.*

**If a number is not in the composed section or a run table, it does not go in the article.** Not
because it is wrong — because a reader cannot open it.

## Pick a template first

A result section's shape depends on what was measured. A communication network, a
differential-expression table and a trajectory are described differently, claim different things
and carry different caveats — and a writer handed only the rules below writes the same paragraph
for all three. That is what made the first sections read as reports on a run: correct, general,
and about nothing in particular.

**`templates/` holds one file per method family.** Read the one whose family matches the plugin
the run used, then come back here — the template carries the METHOD (what it infers, what it
supports, what it does not, the order to write in, the caveats with their citations, sentence
patterns), and this file carries the RULES that hold whatever was measured.

- `templates/cell-cell-communication.md` — ligand–receptor inference between populations

**If no template matches, write from the rules and then add one.** `templates/README.md` says what
a template must contain. The next person will meet the same method, and a template written once
is the difference between their section and yours being comparable.

## What you are adding

You are adding **reading**: what the measurements are about, in the language of the field, in the
order the design gives. **Write it as a research article, not as a report on a run.**

### You may state findings, and you may state hypotheses

*Standing instruction from the PI, 2026-08-31, replacing an earlier prohibition on "conclusions
the run does not support" — that clause is why every section read as measurement with no reading
of it, and why the manuscript sounded like a QC document.*

Say what the result IS, in the field's own words. Name the biology. Where a pattern suggests a
mechanism, say so. A hypothesis is a legitimate part of a results section and its absence is not
caution, it is a section that stops before the interesting part.

**The one thing required of a hypothesis is that it is legible as one.** The project's evidence
rule permits interpretation and asks that it be labelled: a reader must be able to tell a measured
number from a reading of it. "X is higher in the treated arm" and "this is consistent with Y"
are both allowed; writing the second in the grammar of the first is not. That is a rule about
GRAMMAR, not about permission - it costs a clause, and it is what lets everything else be said
freely.

**Numbers and tests are still the run's.** Interpretation is yours; arithmetic is not. Do not
introduce a figure the run did not produce or a statistic it did not compute - see the next two
sections, which are permissions rather than restrictions.

### Never downgrade or reject a finding

State all of them. A result that looks surprising, or that a caveat bears on, is still a result.

*Cost: a whole manuscript was written defensively — every section led with what could not be
concluded, and the biology was never actually said. It reported which pathways led each contrast
and never said what they were.*

### Never invent a statistic, and never switch one off

Use the wrapped tool's own test and name it. If the tool ships none, say the difference is
descriptive — do not substitute one.

*Cost, and this is the one to remember: a tool's between-arm test was DISABLED by a parameter,
and the section then reported "nothing here is tested between arms" as though that were a
property of the method. The tool had offered two ways past an error and the one that removed the
test was taken. Check what the run actually ran before writing that something cannot be done.*

## Before anything: get the brief, and LOOK AT THE FIGURES

**This is the first step and it is mechanised, because it is the one most easily skipped.**

    scprofile write  --out <run> [--plugin <p>]

That writes `kernels/<plugin>/WRITING_BRIEF.md`: the contrasts in reading order with their
reference arms, every figure with the number the paper gives it, what the run recorded against
itself, and which template this method declares. Every entry names the file it came from.

**Then open every figure the brief lists, and record what you saw:**

    scprofile review --out <run> --plugin <p> --figure <path> --note "what you saw"

A note is refused if it is too short to be a look, or copied from another figure. The record is
bound to the image's sha256, so a redrawn figure loses its review and comes back onto the list.

**If the run is on a cluster and you are not**, you cannot open anything until the images are
on your side. The run writes the set as a transfer list — `kernels/<plugin>/FIGURES.txt`, one
run-relative path per line — so it moves in one operation:

    rsync -a --files-from=<the list> <host>:<run>/ <a local directory>/

Open them from the local copy; record the looks **against the run directory**, because the ledger
lives with the run. `scprofile agenda --out <run>` prints the exact command for this run's mode.

**This step parallelises, and a large figure set should be split across agents.** Ask the tool
for the shards rather than dividing the list yourself — an invented split silently leaves figures
unreviewed:

    scprofile review --out <run> --plugin <p> --shards 4 --shard 1   # one agent's list

Each agent opens its own shard and records its own looks into the same run; the ledger is
append-only and locked per write.

Why this is a step and not a suggestion: **every figure defect found in this project was found
by opening the image while the suite was green.** An encoding that contradicted its legend. A
ranking that hid the thing the panel existed to show. Labels driven off the axes by a fix for
labels. A table shows none of these, and nothing fails.

*Cost: 672 figures in one run, two of them ever opened, and a manuscript written from the tables
beneath them. The writing was fluent and described panels nobody had seen.*

**You are the agent that runs this tool.** `docs/AGENT_CONTRACT.md` says which half of the work
is yours: the tool measures, and you read, look, and write. Neither substitutes for the other.

## The architecture of the document

**This order is the same for every plugin.** What changes between plugins is what fills each
part, and that comes from the plugin's own declaration - never from this file, which is why the
same skill writes a communication paper and a differential-expression one.

1. **The overview.** What each group is and how they differ in total, in prose, with the
   design-wide panels beside it. A reader meets the groups before any machinery.
2. **The reference profile.** The control group described in its own right, at every level the
   plugin declares, with no comparison in it. A difference means nothing until the thing it is a
   difference *from* has been described.
3. **One section per crossed comparison**, each walking the plugin's levels coarsest first.
4. **One section per marginal comparison** - a factor's effect pooled over the other. These come
   AFTER the crossed ones because a marginal is an average over strata and is unreadable until
   the strata have been seen.
5. **The interactions.** One factor's response conditioned on the other, at the same levels.
   This is the deepest claim the design supports and it belongs last.
6. **Limitations.** One paragraph, under 200 words, ranked by what actually threatens the
   conclusions.
7. **Supporting material.** Composition tables, what could not be compared, settings, the full
   caveat list.

**Nothing that is machinery opens the document.** A composition table, a QC statement or a
settings block at the top tells a reader what was checked before telling them what was found -
they arrive at a number with nothing to attach it to. All of it is real and all of it belongs
after the argument, where a reader who wants to check something can find it.

### Levels: how a comparison is walked

A plugin declares an ordered list of **levels** - the granularities its method resolves, coarsest
first. Every comparison section walks the same list in the same order, so the document has one
shape whatever the plugin is:

| plugin kind | coarse | middle | fine |
|---|---|---|---|
| cell-cell communication | which cell types talk | which programmes | which ligand-receptor pairs |
| differential expression | which cell types respond | which programmes | which genes |

The host asks the plugin for the list and for which panels answer each level. **Do not write the
level names into the prose from memory** - a section that names "ligand-receptor pairs" when the
plugin is measuring something else is the failure this arrangement exists to prevent.

### Section headings name the comparison, not the finding

> `Differential <subject> between <treated arm> and <reference arm>`
>
> where `<subject>` is what the plugin declares it measures and the two arm names are the
> UNITS the run recorded for that contrast.

**This supersedes the older rule that a heading should be a finding.** That rule was written when
the result was one section, and it is wrong once there is a section per comparison: a heading
that changes with the result makes the document's structure depend on its outcome, so two runs
of the same design produce differently-shaped papers and nothing can be cross-referenced. The
finding goes in the section's first sentence, where it belongs and where it can be as specific
as the data allows.

**The arm names come from the units, never from the factor levels.** In a crossed design two
contrasts can both read "level A against level B" at the level of FACTORS while comparing
different objects - the same factor contrast taken within each level of the other factor. The
levels are identical in both; only the units differ. The run records the units; use them.

### When two scales disagree, say which one carries the claim

A total and the same total per observation are two readings of one result, and they can rank the
groups differently. **Report both, then state which one the claim is made on and why** - in one
sentence, in the text, not left to the reader.

The rule that settles it is not a preference: **if the groups differ in size, the per-observation
scale is what a claim about behaviour is made on, and the absolute scale is what a claim about
total burden is made on.** Say which of the two you are making.

> *Arm A carries more in total than arm B (1,193 against 871), but arm A is the larger sample:
> per 1,000 observations the two are close (38.7 against 36.5), so the difference in the total
> is a difference in how much was sampled rather than in how much each observation does.*

*Cost: the same four arms ranked one way on the total and another per 1,000 cells, with both
panels on the page and no sentence saying which to read. A reader could take either and reach
opposite conclusions about whether diet or age dominates.*

### The limitations paragraph

One paragraph, **under 200 words**, at the end of the text. It is a **ranking of the run's own
recorded caveats**, not new prose: the run collects them, this selects the few that actually
threaten the conclusions and states them plainly. A different cohort produces different
limitations with nobody editing text.

Rank by what would change a conclusion if a reader disagreed with it. A confound the design
cannot separate outranks a preparation caveat, which outranks a threshold. The full list stays in
the supporting material - the paragraph is what a reader meets at the end of the argument.

## The shape of the section

**A finding opens each section, in its first sentence.** "Aged hearts signal more, and the
increase is broad", not "the age comparison was performed". A reader moving through the document
should meet the result immediately under each heading.

*This was previously written as a rule about HEADINGS - "titles are findings" - and it is
superseded by the architecture above, for one reason: with a section per comparison, a heading
that states the result makes the document's shape depend on its outcome. Two runs of the same
design then produce papers that cannot be laid side by side. The requirement did not disappear,
it moved one line down, where it can be more specific than a heading ever allowed.*

**Use the comparison labels the run enumerates, verbatim and in order.** They are the panel's
section names too, so a reader moving between the documents lands in the same place.

*Cost: the panel's sections came from the design; the section's headings came from whoever wrote
it. The two agreed on nothing but the run they came from.*

**State the reference of every contrast.** Everything is measured against a control, the run
records which and why, and a difference reported without it is unreadable.

**Explain, do not warn.** Where something has a cause, give the cause.

> not: *a statement on one scale alone is an artefact of the denominator*
> but: *PECAM1 is lower in the treated arm in absolute terms and higher as a share of its arm's
> total, because that arm's total is less than half the reference's*

*Cost: captions and prose were written as cautions about what the figures did not establish. The
same facts, stated as what the figure shows, are usable.*

**Say a design fact once.** Aliasing, differential filtering, a confound — state it in the
methods or a single line, and then get on with the analysis. It is not a caption and not a
reason to hedge every sentence.

*Cost: one aliasing statement appeared nine times, including at the head of every affected panel,
where it read as though the comparison had been withheld. It had not been.*

## Where the tool cannot answer, say so once and leave it open

Some questions have no panel and no test — an interaction needs four fitted objects where a
differential takes two. Name the question, give the arithmetic if there is any, say plainly that
the tool provides no test for it, and **do not manufacture one**.

## When a choice is unsettled, report both

A parameter that changes the result and has no recorded reason is not resolved by picking one.
Run it both ways, report both, and name both run keys.

*Cost: one contrast in a six-contrast design REVERSED DIRECTION between two settings of a single
parameter. Choosing silently would have hidden that entirely.*

## Before you hand it over

- [ ] Every number traceable to a named file in the run
- [ ] Every claim recorded with `paper --claim ... --cites ...` — the ledger refuses a citation
      to a figure the run does not contain, which is the check that matters
- [ ] The figures in the section are the figures in the panel
- [ ] The reference arm of every contrast is stated
- [ ] The tool's own statistic reported wherever a finding is stated
- [ ] Carried into the run with `--section`, not left beside it

**A section that lives outside the run is a draft**, however good it reads. It has no run key,
its citations resolve to nothing, and it disappears with the session that produced it.
