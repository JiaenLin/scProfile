---
name: figure-rebuild-process
description: How to run a large figure rebuild with many agents - the orchestration, not the drawing. Use when rebuilding or auditing a whole set of figures for a plugin or a paper, when you have more figures than one person can review, or when a figure set has been rejected and you need to find out why. Covers the panels to run (build, referee, professor, verify-by-looking, compare-against-each-other, compare-against-published, fix, sweep), what each one finds that the others cannot, the empirical yield of repeated looking, and the coordinator failures that no per-figure check can catch. For designing an individual figure, use `plugin-figures` instead.
---

# Running a figure rebuild with many agents

Written 2026-08-27, from one rebuild: 8 figure families, ~60 rendered figures, ~200 agents, and a
set that went through 23 plates before anyone noticed a whole level of the data was missing.

`plugin-figures` says how to design one figure. This says how to run the operation, and it exists
because **the expensive failures in that rebuild were not in any figure. They were in the
coordination.**

## The three coordinator failures, and they cost the most

Every one of these passed every per-figure check, because none of them lives in a figure.

**1. The enumeration was built from what looks impressive.** Sixteen panels covered two of the
four entity levels the output table addressed. The finest level - four times as many values as the
level above it, and the level at which a follow-up experiment is designed - had no representation,
and the most-published figure type of that whole method family was never offered as a choice.

- **P1** Before offering anything, list every entity level and grouping column the output table can
  address, and name a candidate figure for each. A level with no candidate is not a level nobody
  wants; it is a level nobody looked at.

**2. The builders produced the right figures and the coordinator selected the wrong ones.** Agents
built group-level arm comparisons; the coordinator put the pooled and single-unit panels on the
page and left the comparisons off. Three times, at three different levels: a missing entity level,
missing comparison panels, and **nine group-level figures already on disk that were never shown.**

- **P2** After every build round, list everything the builders produced and diff it against what
  you published. Anything built and not shown needs a stated reason. The bias is systematic and it
  runs one way: toward what illustrates the METHOD and away from what answers the QUESTION.

**3. A structural fact was measured once, on one input, and propagated into four briefs.** "9
populations, 49 pathways" was one sample of ten; across all ten it was 13 and 68, with per-sample
ranges of 8-13 and 27-52.

- **P3** A structural fact that will appear in more than one brief is measured over ALL inputs
  before the first brief is written, and travels as `(value, N, min, max)`. A per-agent check
  cannot catch a fact that was already wrong when it was handed out.

## The panels, and what each finds that the others cannot

Running one review panel finds one class of defect. These are not redundant.

| panel | one agent per | finds what nothing else finds |
|---|---|---|
| **build** | figure family | the figure |
| **referee** | figure | craft defects: collisions, clipping, illegibility, undecodable channels |
| **professor** | figure | whether there is any science, and whether it is already known |
| **verify-by-looking** | batch of claims | that some reported defects are FALSE - claims that had already been reported upward as fact |
| **compare-against-each-other** | pair or group | cross-figure contradictions; a figure can be internally perfect and contradict its neighbour |
| **compare-against-published** | figure family | where the real standard sits, which is often LOWER than what you built |
| **fix** | figure family | whether a defect is real - a fixer that checks first sometimes finds nothing there |
| **sweep** | pass over everything | what a first look misses, which is a different kind of thing (below) |

**The verify panel earns its place by refuting.** In this rebuild it overturned findings that had
already been reported to the scientist as fact, including one from the coordinator's own looking.
A review panel with no refutation step launders its own errors upward.

- **P4** Does every claim that reached a decision get re-tested by an agent that did not produce
  it, by opening the artefact? A claim that was only ever produced, never tested, is a rumour.

## Compare figures against each other. This is the panel people skip.

A per-figure review cannot find:

- the same colour meaning different entities in different figures (four figures used the same
  thirteen colours for different cell types);
- a fix applied to one member of a family and not its siblings (a colour-vision palette fix, and a
  disclosure about a singular matrix, each applied to exactly one of two sibling figures);
- one figure stating that the set contains no X while another draws an X;
- a figure inverting its own convention **between its own panels** - one panel keyed a factor blue
  and its neighbour keyed it orange, three rows apart.

- **P5** Build a palette table: colour, and what it means in every figure that uses it. Every row
  where a colour means two things is a defect. Do the same for absence glyphs.
- **P6** For every family, diff the disclosures between siblings. A caveat present on one and
  absent on the other is a defect in the one that lacks it.

## One vocabulary for absence, across the whole set

Absence appeared in this rebuild in eight costumes across different figures: hatched columns,
hollow rims, open circles, dashed lines, grey tiles, white tiles, outlined swatches,
double-daggers. A reader who learned one figure could not read the next.

One figure worked out the right answer and nothing else used it. **Fill answers "is there a
value"; rim answers "is the denominator whole".** Four states, named the same way everywhere:

    value present, scored in all units
    value present, partial denominator - the mean divides by the full n anyway, so it is an UNDER-READ
    measured absence - scored everywhere, no value for this comparison
    never tested - below the method's own floor before scoring

The last two matter most: they look identical in most figures, and reading the second as evidence
of silence is reading a threshold as biology.

- **P7** Is one absence vocabulary used identically in every figure of the set, with the same four
  words in every legend? Where a geometry cannot carry a rim, map the same four states onto that
  geometry's own channels and use the same words.

## How much does repeated looking buy?

Measured, rather than asserted. Sweep 1 over a rebuilt set found a defect in most figures. Later
sweeps, each told what earlier ones had found and asked for what they missed, kept finding things -
and the late findings were a **different kind** of thing:

- early sweeps find collisions, clipping, illegibility - what is wrong with the marks;
- late sweeps find captions describing marks the figure does not draw, numbers on a figure that
  contradict other numbers on the same figure, a title claiming what the panels do not show, tick
  values unevenly spaced for even intervals, units that change between panels, and what a reader
  sees who reads only the graphic and none of the text.

- **P8** Run sweeps until a sweep yields nothing new, and record the yield per sweep. A set still
  producing findings at sweep six needs rebuilding, not fixing. Falling yield is the only evidence
  that a set is finished; "we reviewed it" is not.
- **P9** Push each sweep past what is known by handing it the running list of found defects and
  asking only for what those missed. A sweep that re-finds sweep one's defects has cost you a
  sweep.

## What a first look misses, in order of how late it is found

This ordering is the most transferable thing here. Look for these FIRST next time.

1. **A caption describing a mark the figure does not draw**, or omitting one it does. Found late
   every time, because reading the caption and reading the figure are different acts and reviewers
   do one of them.
2. **A number on the figure contradicting another number on the same figure.** Requires reading
   every number and holding them together.
3. **A stated bound violated by the figure's own source table.** One panel printed a floor its own
   data crossed; at the printed floor nothing on it reached significance at all.
4. **The picture asserting what the caption denies.** A panel visibly sparse next to one visibly
   dense, with the confound quantified in 5 pt grey underneath. A reader takes the image.
5. **A channel drawn with no key.** Found in most of one set, and still being found at sweep four,
   because a missing key is an absence and absences are what eyes skip.

## Coordinator discipline

- **P10** Check by looking, never by grep. A page rebuild was verified with `grep` against the
  generated HTML and every check passed while three titles rendered entity codes as literal text -
  the grep found the entity present and reported success. **The check and the defect agreed with
  each other.** A code check confirms what you thought to ask.
- **P11** Look at the artefact a reader will actually see. A downscaled or recompressed copy is a
  different image; one encoding pass silently collapsed a thirteen-colour categorical palette into
  three confusable pairs, lost an experimental arm to grey, and posterised colour bars into bands -
  **manufacturing contour thresholds that were not in the data**. It passed every numeric check.
- **P12** One standalone script per figure, each writing its own artefact and its own source table.
  A family that renders from a shared driver cannot be regenerated, re-checked or fixed one figure
  at a time, and every fix then risks its siblings.
- **P13** When an agent dies mid-task, its output is usually on disk. Read the directory before
  relaunching, and hand the successor what its predecessor already did - including the defect it
  had just reported and not yet fixed.
- **P14** An agent that checks a reported defect before fixing it sometimes finds nothing there. In
  this rebuild one did, three ways, and closed the defect CLASS instead - removing the default that
  made the omission silent. **Instruct fixers to verify first; a phantom fix costs more than a
  missed one.**

- **P16 (parallel fixers must not share an output directory, or an input module)** Fan-out is
  right for FINDING defects, because the angles are independent. It is a trap for FIXING them,
  because the fixes are not: two agents repairing two different defects in one shared helper each
  re-render into their own directory, and every file produced is a mixture of one agent's fix and
  the other's un-fixed state. Nothing is corrupt, every agent reports honestly, and the set is
  incoherent anyway. Give each fixer either its own module or its own turn, and re-render the whole
  set ONCE from the final source before anybody looks at it.
  **ONE INSTANCE.** Four fixers worked in parallel on one figure directory. Their reports were
  accurate and their code changes were all correct and all landed. But a checker opening the file
  one of them had signed off as final found text struck through by a key arrow and a declaration
  reading "3.13 to 3.13 is 1.0x in value and 1.0x in width" - a degenerate case a SIBLING agent had
  already hardened the shared helper against, forty-one minutes after that PNG was written. Two
  agents also reported the same file at different byte sizes because a third rewrote it between
  their reads, and one cited two paths as "before" that were byte-identical to the "after".
  **CHECK:** does every rendered file in the set post-date the last edit to every module that draws
  it? Compare mtimes and say the number. If any figure is older than its own source, it is not a
  figure of that source and no observation about it - defect or clean bill - is about the code you
  now have.

- **P17 (a stale artifact reads exactly like a current one)** There is no visual difference between
  a figure rendered from the fixed source and one rendered from the source before the fix, so a
  reviewer cannot tell them apart and will report defects that are already repaired. Quarantine
  superseded output directories by RENAMING them, not by remembering which is current: a reviewer
  pointed at a directory reads what is in it.
  **ONE INSTANCE.** A review round confirmed 18 defects; 2 of the 18 had been fixed before the
  round began, and were reported because the brief named a directory that had since been superseded.
  The reviewers were not wrong about what was on the page - the page was just not the current one.
  **CHECK:** does the brief name exactly one directory per figure family, and is every other
  directory renamed so that reading it is impossible by accident?

  **ONE INSTANCE, and it is the coordinator's own.** Having written this rule, the coordinator then
  named two directories as "the CURRENT ones" in two successive briefs. Both were stale by the time
  the second brief was written: another agent had edited the shared module an hour after those
  renders, so the figures the reviewers were sent to were not figures of the code anybody now had.
  The error was found only because a MANUSCRIPT agent, told to cite what it had opened, cited a
  third directory the coordinator had never heard of - which was the genuinely current one. Naming
  a directory as current is a claim with a shelf life measured in minutes on an active tree, and
  the coordinator is the last person who will notice it has expired, because they are the one who
  remembers deciding it. Do not name a directory as current from memory. Recompute it - newest
  render whose mtime beats every module that draws it - at the moment you write the brief.

- **P18 (consolidate to one directory per family, and delete the question)** The remedy for the
  above is not better bookkeeping, it is fewer directories. An iterating rebuild accumulates output
  directories the way a shell accumulates history, and every one of them is a trap for the next
  reader, who has no way to tell a superseded render from a current one by looking - they are all
  plausible figures. Render once from final source into ONE directory per family, name it
  unambiguously, and move every other directory out of the tree.
  **ONE INSTANCE.** One figure family had accumulated 21 output directories - `r1`-`r8`, `alias1`-
  `alias6`, `baseline`, `final`, `pal`, `pfix`-`pfix4`. `final` was among the oldest, 8 hours
  behind source. The two most recent were unknown to the coordinator. Consolidating left one
  directory, two figures, zero stale.
  **CHECK:** how many directories hold a render of this family? If the answer is more than one, you
  are relying on somebody remembering which, and that has already failed here.

- **P19 (scope the freshness check to a figure's OWN producer)** The check in P16 is only as good as
  its notion of "the source". Taking the newest mtime over every module in a directory marks every
  figure stale the moment any one module is touched, so the check cries wolf, and a check that
  fires on correct behaviour gets ignored - which costs you the one time it was right. Match each
  figure to the script that actually draws it and compare against that.
  **ONE INSTANCE.** Run over one directory, the coarse check reported **60 of 62** figures stale.
  Matching each figure to its own producer gave **26 of 52** - the coarse version over-reported by
  2.3x, and a reviewer handed the first number would reasonably have concluded the whole directory
  was worthless and stopped looking.
  **CHECK:** does your freshness check name, for each figure, the specific file it compared against?
  If it reports a single source mtime for a whole directory, it is answering a different question.

- **P20 (two true facts fuse into one false sentence, and the join is invisible)** The dangerous
  error in an annotated figure is not a wrong number - a wrong number is usually checkable against
  the panel. It is two correct numbers joined by a clause that was never computed: each half
  survives inspection, the sentence reads fluently, and only someone who knows what the identifiers
  MEAN can see that they belong to different objects. Build such sentences from the same variables
  that draw the marks, and derive each clause separately even when that makes the sentence longer.
  **ONE INSTANCE.** A headline panel printed "One animal, X, carries ~48% of the chow arm's signal
  - it is the deepest library (1949 edges against 297)". X was the cohort's deepest library and an
  animal of the OTHER arm; the animal carrying ~48% of the named arm was a different one entirely.
  Both halves were true of somebody. The name came from an argmax over the whole cohort while the
  share was a hard-coded literal about one arm, and nothing connected them. It survived every
  numeric check because no number in it was wrong.
  **CHECK:** for every sentence on a panel that joins an identifier to a quantity, was the
  identifier computed from the same subset the quantity describes? Are any percentages in the
  annotation literals rather than derived? Print the sentence's inputs and read them side by side.

- **P21 (a shared vocabulary is shared only where it is IMPORTED)** Deciding the canonical words
  for a rebuild is the easy half; the hard half is that every figure has to fetch them from one
  place. Write the canon into a module, let each figure keep its own wording, and you have the
  divergence you started with PLUS a file asserting it is gone - which is worse, because the next
  reader checks the module and stops. Marks may legitimately differ by figure type (a heatmap cell
  has no rim to dot, a ring node has no column to hatch); the WORDS are the transferable part and
  must come from the shared module by import, not by copying.
  **ONE INSTANCE.** A rebuild produced a good four-state absence vocabulary in a module whose own
  docstring said "identical in every figure of this set; do not paraphrase them per figure". Four
  of roughly twelve figure modules imported it. The rest each carried their own phrasing for the
  same states - one sheet said "population present, zero in this row" for what the canon calls a
  measured absence and "not reported by any animal in that arm" for what it calls never tested -
  so a reader who learned the terms on one page did not meet them on the next. The module that
  ORIGINATED the vocabulary was itself among the non-importers.
  **CHECK:** grep for the module that defines your shared vocabulary - how many figure modules
  import it, out of how many exist? For each that does not, is that because the concept does not
  arise there, or because it was paraphrased?

- **P22 (adopt a set-wide convention by CONVERTING one figure at a time, and look at each)** The
  temptation with a set-wide change is to apply it everywhere in one pass. Do not: a convention
  interacts with each figure's own layout, so the change that fits one panel overflows the next,
  and a single sweep produces a set where some figures are better, some are broken, and the diff
  is too large to tell which is which. Convert one, render it, LOOK at it, and only then take the
  next. The rendered result is the only evidence that the convention actually fits.
  **ONE INSTANCE.** Substituting canonical wording into one sheet's key lengthened two lines. On
  that sheet they fitted; on a different figure the same class of edit had already pushed a
  bottom-anchored footer block through a panel's axis labels, twice. Neither outcome was
  predictable from the source - both were visible immediately in the render.
  **CHECK:** after converting each figure to the shared convention, did you re-open the rendered
  file and look at the region you changed? Can you name what the change cost in layout?

- **P23 (when two sentences on a page disagree, find out which is TRUE - deleting one is not
  resolving it)** Two statements about the same entities that give different reasons for the same
  absence is a signal that somebody does not know which reason is right. The repair is to go to the
  data and find out. Deleting the sentence you like less removes the CONTRADICTION and leaves the
  ERROR, now unopposed and looking settled - and you will delete the true one about half the time.
  **ONE INSTANCE, and it is the coordinator's own.** A panel carried a provenance line saying
  entities were omitted because "this unit did not have" them, and a second line calling the same
  entities "NO SURVIVING LINK". I noticed the collision, judged the second line authoritative
  because it came from the drawing function, and rewrote the first to agree with it - deleting the
  clause that named the method's detection floor. The data said the opposite: all five named
  entities appeared in no edge at all in that unit, having fallen below the floor before anything
  could be scored. So the panel went from contradicting itself to asserting the wrong one of two
  states, on the unit with the MOST floor-driven omissions in the whole cohort, while its sibling
  panels kept the floor sentence - which invited a reader to infer this unit's omissions had some
  other cause. One measurement against the source table would have settled it in a minute.
  **CHECK:** for every contradiction you resolve, what measurement decided which side was right?
  If the answer is "the one in the more authoritative-looking code", you have not measured. And
  after resolving, does the surviving sentence still say everything the deleted one said that was
  TRUE?

- **P24 (a bucket named for one of the states it contains asserts that state)** Code that groups
  entities by a computed condition - `total <= 0`, `count == 0`, `not in index` - often merges
  states the vocabulary keeps apart, because the condition is equally true of all of them. The
  grouping is fine; the LABEL is where it goes wrong, because a label has to say something and
  whatever it says will be read as true of every member. Either split the bucket by passing in the
  information that distinguishes the states, or name it so it asserts NEITHER.
  **ONE INSTANCE.** `total_in <= 0` collected both entities the method never scored and entities it
  scored and found silent, and the note read "NO SURVIVING LINK" - which asserts the second of the
  two. On the panel that exposed it, all five members were the first. The drawing function reserved
  a separate correctly-named note for the genuine "lost to the cutoff" case, but that list was
  empty on this panel, so the contrasting line that would have taught the reader the narrow sense
  never rendered. Repair: the caller now passes which entities were never tested, the note splits
  into two canonical states, and where the caller passes nothing the note asserts neither.
  **CHECK:** for every group your code forms by a threshold or a missing-key test, list the
  distinct real-world states its members can be in. Does the label hold for ALL of them? If the
  distinguishing information lives in the caller, is it being passed?

- **P25 (freshness by mtime does not tell you a figure can still be BUILT)** Comparing a rendered
  file's mtime against its source answers "is this older than the code?" and nothing else. A figure
  can be newer than every module that draws it and still be unreproducible, because the producer
  raises the moment you run it - a helper it calls was renamed, a shared module was rewritten under
  it, an entry point was refactored and its standalone caller left behind. That figure is not a
  figure of the code you have; it is an artefact of a version that no longer exists, and nobody
  finds out until someone tries to change it. Before trusting any freshness audit, RUN each
  producer. Two more traps found the same way: a figure's producer is its entry point AND every
  module that entry point imports, so matching by filename alone misses the module that actually
  draws it; and the entry point may not be the live one.
  **ONE INSTANCE.** A per-producer freshness check reported one figure FRESH. Its named script
  raised `AttributeError` on the first call - it used an API removed in a refactor. Its actual
  drawing module was nine hours NEWER than the figure, which the check never compared against
  because it matched on filename. The live entry point then raised too, on a different missing
  function. Enumerating what that module needed from its shared dependency: 13 attributes, of which
  three existed in NEITHER of the two candidate modules. The family could not be regenerated at
  all, and the figure on disk had been read and reviewed several times as though it could.
  **CHECK:** for each delivered figure, did you EXECUTE its producer this session and see it write
  the file? If not, "fresh" means only that a timestamp is in the right order.

- **P26 (one shared module, or none - three API generations is the worst outcome)** A shared module
  succeeds only if every caller tracks it. Rewrite it while some callers keep the old surface and
  you get several generations live at once: callers importing different modules for the same
  concept, the same state under different constant names, and functions that exist in one and not
  the other. This is strictly worse than each figure having its own copy, because now a reader -
  and the next agent - believes there is one canon and checks only it.
  **ONE INSTANCE.** A rebuild finished with TWO modules implementing one four-state vocabulary.
  They named the same state differently (`MEASURED` in one, `ABSENT` in the other); five figure
  modules imported one and a sixth imported the other; and one caller had been written against a
  THIRD generation that called that state `NEVER` and provided helpers neither survivor has. So one
  of the four states had three spellings across three generations of the module whose entire
  purpose was to stop exactly that.
  **CHECK:** how many modules in the tree define your shared vocabulary? If more than one, which is
  canonical, and does every caller import THAT one? Do the constants have identical names in all of
  them?

## What to expect at the end

In this rebuild, of 23 plates: **19 were about the method, not the biology.** Four presented a
biological contrast; two of those were self-nullifying by design; the remaining two both failed
under a control that arrived after they were built.

That is not a failure of the rebuild. It is what the set was built to be, and saying so plainly is
worth more than four confident panels that do not survive their own denominator. Expect a
methodological result, and expect the honest biological yield to be small.

- **P15** Before publishing, sort every figure into "about the method" and "about the subject", and
  state the counts. If nobody has done that sort, the set has not been understood.
