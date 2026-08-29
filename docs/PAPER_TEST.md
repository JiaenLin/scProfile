# The paper test

**Write the result from your figures. Then defend it. Whatever does not survive was a bad figure
or a missing one.**

That is the whole idea. This page says where it sits, how to run it, and — at the end — what it
does not yet do, because it is narrower than it should be.

---

## Where it sits

```
run  →  report  →  standard  →  review  →  PAPER  →  licence / promote
        draw the   measure     look at    write the  build on it
        figures    the page    them       result
```

Each step asks a narrower question than the next:

| step | question |
|---|---|
| `standard` | Is the page readable? Are there too many figures, too many words? |
| `review` | Did anybody actually open the images? |
| **`paper`** | **Do these figures support the thing you want to say?** |

The first two can pass on a figure set that supports nothing. The third is the one a reader will
put to you, so it is better to put it to yourself first.

**Run it before you promote a run or reuse its results.** A figure set nobody has written a
result from has not been tested, only rendered.

---

## How to run it

**1. Write a claim.** One sentence you would put in a paper, and the figures you read it off.

```bash
scprofile paper --out RUNDIR \
  --claim "The share of X rises in arm A and falls in arm B, by about nine points each way" \
  --cites kernels/p/figures/F4.png,kernels/p/figures/C5.png
```

A claim too short to be checkable is refused, and so is a claim citing nothing. "Diet matters"
is not a claim. Say what is higher than what, where, and by how much.

**2. Put it to a reviewer, and record what happened.**

```bash
scprofile paper --out RUNDIR --round <claim-id> \
  --verdict standing|narrowed|withdrawn \
  --why "what was put to it, and what happened"
```

Three outcomes, and the third is the one that teaches you something:

- **standing** — it held up.
- **narrowed** — it survived in smaller form. Record the smaller form as a new claim.
- **withdrawn** — it was wrong. Something in the figure set was misleading you; find it.

**3. Look at the ledger.**

```bash
scprofile paper --out RUNDIR            # every claim, its state, how many rounds
scprofile paper --out RUNDIR --strict   # non-zero while any claim is undefended or stale
```

---

## The one property that makes this a test and not a checklist

**A claim is tied to the figures it was read off.** Redraw one of them and the claim goes
**stale** — it has to be defended again, whatever verdict it had. A statement about a picture
cannot outlive the picture.

This is the same mechanism as the figure-review ledger, for the same reason: anything that can
be satisfied once and then quietly drift is not a check.

---

## What makes a round worth running

- **Write the claim, not a description of the panel.** "Figure 3 shows the comparison" cannot be
  wrong, so it tests nothing.
- **Check every number against its own denominator first.** Most claims that die, die here.
- **Review against real standards.** What would a specialist in this field demand? An imagined
  reviewer only knows what you already know.
- **Run more than one round.** The first finds the obvious. The later ones find the claims that
  survived because you believed them.
- **Do not hunt for one dramatic failure.** The job is every claim the set cannot support,
  including the dull ones. A round that confirms most claims and kills one is a normal round.

**If every claim stands unchanged, that is a result you should be suspicious of**, and the tool
says so: it usually means nobody pushed.

---

## What it caught the first time it was run

Four rounds on one figure set. Each round removed a claim, and each removal was a figure defect:

| round | the claim | what it turned out to be |
|---|---|---|
| 1 | a factor changed the total | the groups' totals, four-fold apart |
| 2 | a switch between two families | half of it was a self-interacting pair acting as an abundance readout |
| 3 | one named element led the effect | the ranking flipped on a second scale — and the "control" led the other one |
| 4 | — | the effect survives; what carries it does not |

Three of the four produced a code change. Those changes are rules R7–R11 in
[`FIGURE_STANDARD.md`](FIGURE_STANDARD.md).

---

## What this test does NOT do yet

**It is too narrow, and these are the specific ways.** They are listed in the tool as well
(`scprofile.paper.NARROW`), printed every time the command runs, so nobody can use the test as
though it had no limits.

1. **Only the Results section.** A paper is also methods, discussion, and figure legends. None
   of those is exercised.
2. **Only claims that cite a figure.** A claim resting on a table, or on a number in the text,
   is invisible to the ledger.
3. **The reviewer is unspecified.** The tool records *that* a round happened and what it
   decided. It says nothing about who is competent to hold one, and a project with no reviewer
   available has no test.
4. **Missing figures are found only indirectly.** A gap shows up when somebody tries to write
   the claim that needs it — so the test sees exactly as far as the writer's imagination, and no
   further. This is the deepest limitation.
5. **It does not ask whether a figure can be understood.** A correct claim read off an
   unreadable panel passes.
6. **There is no negative control.** The loop has never been run against a figure set known to
   be sound, so how often it kills a *true* claim is unmeasured.
7. **Rounds are counted, not scored.** Nothing says when enough review has happened.
8. **One design shape, one method, so far.** Single-factor, three-factor, no-design, time-course
   and nested designs are untested.

**The next version should fix 3 and 4 first.** Without a defined reviewer the loop depends on
who happens to be available; without a way to surface missing figures directly, it only ever
finds the gaps somebody already suspected.
