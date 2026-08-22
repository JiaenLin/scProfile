# Designing a run plan

A run plan answers one question for every plugin the build knows about: **should this run on this
project, at what depth, and if not, why not.**

It is a document before it is a command. A plan that says "7 plugins will run" is not a plan; a
plan that says *why the other two will not, in terms a reader can check against the data*, is.

---

## 0. Two axes, and the plan must not confuse them

Every plugin gets **two** answers, and they are about different things:

| axis | question | example |
|---|---|---|
| **verdict** | what would this do **on this project**? | RUN (full) over 10 samples |
| **readiness** | what stands between **this installation** and running it? | its wrapper is not written yet |

**A plugin that is not built here is not a limitation of the user's data.** Collapsing the two
cost exactly that: a plan on a healthy ten-sample project reported seven of nine plugins BLOCKED,
in the same column and the same word as *"your spliced counts are missing"*, because their
wrappers had not been written in that checkout. A user installing the tool and running the planner
would conclude their dataset could not be analysed — when every one of those plugins would run on
it.

So the plan leads with the verdict, because that is the question the user asked, and reports
readiness beside it as work to be done — most of it by `plan --build`. The headline says both:

```
ON THIS PROJECT:       7 of 9 plugin(s) would run.
IN THIS INSTALLATION:  2 ready now, 7 need building first.
```

---

## 1. The four verdicts, and why there must be four

Every plugin gets exactly one:

| verdict | means | who decides |
|---|---|---|
| **RUN** | the data is there and the design supports it | the plan, with a capacity level (§3) |
| **SKIP** | the **design** genuinely cannot support it | the plan, and it must cite a design fact |
| **BLOCKED** | the **data** is absent and cannot be produced from what exists | the plan, and it must name every place it looked |
| **UNRESOLVED** | the scan **could not determine** whether the data is there | nobody — this is a defect in the plan |

Three of these are answers. The fourth is an admission, and it is the whole point of having four.

> **UNRESOLVED IS NEVER A SKIP.** A plugin must never be dropped because the scan failed, timed
> out, could not read a directory, could not parse a manifest, or did not know where to look. That
> is a fact about the scan, not about the project — and a plan that turns it into a skip has
> converted its own limitation into a property of somebody's experiment, which is
> indistinguishable downstream from the experiment genuinely lacking the data.

**A plan containing any UNRESOLVED is not a plan.** It is a list of things to go and find out. The
audit (§5) fails it, and it must be resolved — by searching harder, by being told where to look
(`--search`), or by a human recording that the data does not exist — into one of the other three.

### The difference between SKIP and BLOCKED, stated positively

**SKIP** requires a positive statement about the experiment:

> *"`de` is skipped: `diet` has one level (`HFD`) across all 10 samples, so no diet contrast
> exists."*

**BLOCKED** requires a positive statement about the search:

> *"`velocity` is blocked: no spliced/unspliced layers in the object, and no velocyto `.loom`,
> mtx triplet or layered `.h5ad` under the 4 directories harvested from `uns` provenance or the 1
> given with `--search`. Each is listed. These come from the aligner and cannot be derived later."*

Neither may be phrased as an absence of information. "No design table found" is not a design fact;
it is a missing input, and the verdict is BLOCKED, not SKIP.

---

## 2. Knowing what is actually available

The plan's first job is to know the project's data **exhaustively**, because everything downstream
inherits its blind spots.

**Read the object completely.** Every `obs` column, every `obsm` key, every `layer`, every `uns`
record — not the ones a plugin asked about. A plan that only looks for what it expects cannot
report what is there.

**Follow the provenance chain.** Upstream tools record where they came from. Harvest every
recognised tool record in `uns` and every string in it that resolves to a directory, and search
those for inputs that are not in the object at all — aligner output being the usual case. Report
the number of leads found and searched, and **the count of directories searched must appear in the
plan**, because "searched 0 directories" and "searched 6 and found nothing" are different verdicts
wearing the same words.

**Report what was found AND what was looked for.** A scan that reports only hits cannot be audited.

**Never infer from a name.** Not a sample's, not a file's, not a column's. Pattern-matching a
naming convention bakes one project into a tool that every other project then works around, and it
fails silently on the first project that names things differently. Detect by *content*, report the
evidence, and let a flag override.

**If a search cannot complete, say UNRESOLVED.** A directory that could not be read, an object that
could not be opened backed, a provenance record whose shape is unrecognised — each is an
UNRESOLVED, not an absence.

**And a search has limits, so it must report whether it hit them.** Depth caps, visit budgets and
unreadable directories all end a walk early, and a walk that ended early returns the same empty
list as one that finished. Measured: STARsolo delivers its velocyto matrices at
`<sample>_Solo.out/Velocyto/filtered/`, **depth 9** below a project root, beside `__STARtmp`
directories holding thousands of entries. A search capped at depth 8 with an 8,000-directory
budget could not reach it and reported the aligner output as absent — the exact failure this
section exists to prevent, committed by the tool that documents it. The budget must be large
enough for real aligner output, the noise directories must be pruned so the budget reaches the
candidates, and **the searcher must expose whether it stopped early** so the caller can answer
UNRESOLVED instead of BLOCKED.

---

## 3. Capacity: run it at the depth the project can support

A plugin that runs is not automatically running *well*. Each has a ladder, and the plan states
which rung it is on **and why not the one above** — otherwise a degraded run is indistinguishable
from a full one in the report.

The general form:

| rung | condition |
|---|---|
| **full** | every optional input present; the richest contrast the design permits |
| **reduced** | runs, but an optional input is missing or a contrast is unavailable |
| **minimal** | the required inputs only; the result answers a narrower question than the plugin can |

Three rules govern the ladder:

1. **Take the highest rung the data and design support.** Not the safest one. A design with two
   crossed factors and replication in every cell supports an interaction term; testing only main
   effects there discards the study's primary question.
2. **A plugin declaring `per_unit` fans out over every unit it has.** Pooling is a different
   question — an inference pooled over a cohort describes the average of its conditions and may
   describe none of them. If no unit key exists, it runs pooled **with that caveat recorded**; it
   is not skipped.
3. **Every rung below full is a caveat in the result**, naming the input that would raise it.

---

## 4. What legitimately justifies a SKIP — and it is very little

**The default answer is RUN.** A skip means the design cannot phrase the question *at all*, and
there are only two ways that happens:

- **A factor has one level.** There is no contrast; the question cannot be written down.
- **No level has two samples in it.** A differential test over singletons has no within-group
  variance to estimate, so the number it returns is not an estimate of anything.

**Everything else runs, with a caveat.** In particular, none of these is a skip:

| situation | what the plan does |
|---|---|
| one arm of several is a singleton | RUN, and say which arm contributes no within-group variance |
| two factors are confounded, wholly or partly | RUN, and say the effect is real while its *attribution* is ambiguous |
| the groups are unbalanced | RUN, and report the sizes |
| no two factors are crossed | RUN at main effects, and say the interaction is not estimable |
| an upstream `constraint_on_use` applies | RUN, and reproduce the constraint — a claim it forbids is refused by the *plugin*, not withheld by the plan |

This line is drawn deliberately, and the alternative was measured. A planner that skips on every
imperfection tells a user with a real, slightly imbalanced experiment that their data cannot be
analysed. That is both wrong and the opposite of what they installed the tool for: **a confound
weakens an attribution, it does not make a number unworthy of being computed.**

---

## 4a. The plan prescribes, it does not merely permit

A verdict of RUN is not a plan. For every plugin that runs, the plan states:

- **the settings** — which label column, which layer, which embedding, how many cores, which
  reference set. A plan that says *"run liana"* leaves the user to work out every flag, and a
  plugin run with a default it should not have used produces a result nobody can distinguish from
  a correct one;
- **the contrast, at the richest the design permits** — an interaction where two factors are
  crossed with replication in every cell, because that is usually the question the study was
  designed to ask; main effects otherwise, and it says which;
- **the units** — a `per_unit` plugin is told the key and every unit it will fan out over;
- **the order** — waves derived from `needs_kernels`, so a plugin that reads another's output runs
  after it. A plan that lists both without saying so leaves the ordering to be discovered from a
  failure.

---

## 4b. Readiness is repaired, never reported as a refusal

If a plugin is not built in this installation, **that is the plan's problem to solve, not the
user's problem to be told about.** The plan still gives it a full verdict against the project —
"on your data this would run at full, over 10 samples, testing the age×diet interaction" — and
lists the preparation separately, marked by who does it:

```
PREPARATION: 7 plugin(s) are not ready in this installation.
None of this is a limitation of your project.
  [auto] liana        scprofile install liana --prefix <dir>
  [ you] scenic       scprofile scaffold scenic
```

`--build` then performs every `[auto]` step and **troubleshoots what fails**: no conda on PATH, a
selftest that failed after a clean resolve, a package that tried to build from source, a full
disk, a network that could not be reached — each has a different remedy, and printing a traceback
leaves the user to work out which one they hit.

---

## 5. The audit

The plan is checked before it is believed, by rules that do not repeat the plan's own reasoning.

| check | fails when |
|---|---|
| **completeness** | any known plugin is missing from the plan, or appears twice |
| **no unresolved** | any plugin is UNRESOLVED |
| **skips are justified** | a SKIP cites no design fact, or cites one contradicted by the design table |
| **blocks name a search** | a BLOCKED does not say where it looked, or says it looked in zero places |
| **capacity is argued** | a RUN below full does not name the input that would raise it |
| **capacity is not left on the table** | an input is present that would support a higher rung than the plan chose |
| **evidence is re-derivable** | a claim about the object disagrees with the object when checked independently |
| **the design is used** | a design table is present and no design-aware plugin uses it |
| **order is sound** | a plugin runs before something it declares it needs |
| **nothing vanished** | the plugins in the plan plus the skipped plus the blocked equals every plugin known |

The audit reports what it checked, not only what it found. **An audit that prints nothing when it
passes cannot be told from an audit that did not run.**

---

## 6. Stability

The same project must produce the same plan.

- **Deterministic.** No dependence on iteration order, wall-clock, or filesystem order. Sort
  everything.
- **Explain every choice inline.** Detected or declared, and the evidence — those carry different
  weight when a result is questioned later.
- **Re-planning after a run must reach the same verdicts** for anything that has not changed.
- **A plan is dated and records the tool version and the object's identity.** A plan is only ever
  correct as of a moment; the artifact it describes can move underneath it.

---

## 7. What this is not allowed to assume

No organism. No assay. No column name. No design shape — not 2×2, not paired, not time-course. No
minimum sample count. No particular upstream tool.

The plan asks the *object* and the *design table* what they are and reports the evidence. Anything
a plan must know that it cannot discover is a flag, with a default that is announced rather than
silent.

A project with one sample, no design table and no spliced counts should get a **short, correct,
honest plan** — not an error, and not a plan that quietly pretends the missing pieces are absent
on purpose.
