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

## The shape of the section

**Titles are findings, not activities.** "Aged hearts signal more, and the increase is broad",
not "Age comparison". A reader should be able to read only the headings and know the result.

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
