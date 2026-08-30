# The development contract

Three rules for every change to this tool. They are not style preferences; each one exists
because breaking it has already cost something measurable, named below.

---

## 1. Every fix lands in this repository, as mechanism or as plugin content

There is no third place. A fix is one of exactly two things:

- **A mechanism** — it belongs in `scprofile/`, knows nothing about any particular method or
  project, and would work the same for a plugin nobody has written yet.
- **Plugin content** — it belongs in `kernels/<plugin>.py`, and it is allowed to know everything
  about the tool it wraps and nothing about the host.

**A fix that lives anywhere else is not a fix.** A script in a scratch directory, a command typed
into a terminal, a file edited on a cluster: these change one run and no other. The next run has
the defect back and nobody knows why.

The test: **delete the output, run the tool from a clean checkout, and see whether the fix is
still there.**

### Which of the two is it?

Ask what the change knows about. If it names a method, a database, a function of some wrapped
package, an assay or a species, it is plugin content. If it would read identically for a plugin
that has not been written yet, it is mechanism.

Where a fix seems to need both, it is two changes: the host gains a general capability, the
plugin uses it. `ctx.cache()` is the host saying *here is somewhere that outlives a run*;
`cellchat` deciding to keep a fitted object there is the plugin's business, and the host never
learns what an RDS is.

---

## 2. No regression in what the tool delivers

**The suites do not check this and cannot.** They check that the code is well-formed. Capacity is
a property of the OUTPUT, and every suite can pass while a run produces half of what it produced
yesterday.

Both of the worst defects in this stage were exactly that shape:

- Four plot functions failed on every unit of a whole run — **no file, no log line, no non-zero
  exit**. Found by counting figure kinds against the declaration, days later.
- A rebuild dropped **266 comparison figures**, recorded nothing in their place, and printed the
  same success line.

Neither failed a test. Neither would.

So every run records what it delivered, in `CAPACITY.json`, and says at the end whether it
delivered less than the run before it:

```
scprofile capacity --out <run>              what it delivered, against the previous run
scprofile capacity --out <run> --against <other> --strict
```

Counted from disk, never from a manifest: if a figure is not there it is not counted, which is
the only definition that cannot drift from what a reader will find.

**A regression is not automatically wrong** — removing a panel deliberately is a regression by
this measure and may be right. What is forbidden is one nobody noticed.

---

## 3. The smallest change that fixes the defect

Find the surgical version. Rewriting around a defect hides what it was, and the next person
inherits a larger thing with the same bug somewhere inside it.

In order of preference:

1. **Change the one line that is wrong.** The cache reuse did nothing because an argument was
   read at index 12 and passed at index 11. The fix is one character. Everything else that was
   tempting — restructuring the argument passing, moving to a JSON parameter file — would have
   hidden it.
2. **Change the one place the wrong value comes from.** Six call sites each wrote *if a design
   was passed, read it*, so all six degraded identically. The fix is one function they all call,
   not six edits.
3. **Add the missing mechanism**, only when 1 and 2 genuinely cannot hold the fix.

**Two things a minimal fix always includes**, and they are not optional extras:

- **A check that fails on the defect.** Written so that reintroducing the bug fails it —
  demonstrate that, do not assume it. A check that was never seen to fail proves nothing.
- **What it cost, in the code.** One or two sentences at the fix, with the measurement: *"11 of
  18 units", "266 figures", "57.5 against 23.3"*. A comment that says what the code does is
  worth little; one that says what happened without it survives the next person's judgement
  about whether the guard is needed.

### What a minimal fix is not

It is not leaving the rest of the defect in place. If one call site is wrong and five others have
the same shape, the minimal fix is the shared function — not the one line, and not a rewrite of
all six.

---

## The order

1. Reproduce it, and measure the cost.
2. Find the smallest change (rule 3).
3. Land it as mechanism or plugin content (rule 1).
4. Write the check, and see it fail on the defect.
5. Run the suites, and the capacity guard (rule 2).
