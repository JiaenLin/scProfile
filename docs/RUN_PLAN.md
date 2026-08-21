# Designing a run plan

A run plan answers one question for every plugin the build knows about: **should this run on this
project, at what depth, and if not, why not.**

It is a document before it is a command. A plan that says "7 plugins will run" is not a plan; a
plan that says *why the other two will not, in terms a reader can check against the data*, is.

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

## 4. What legitimately justifies a SKIP

Only a statement about the experiment. In practice:

- **A factor has one level.** No contrast exists on it.
- **No replication within the groups being compared.** A differential test with n=1 per arm
  produces a p-value and no evidence; the plan must say which arms and their sizes.
- **The contrast is not identifiable.** It is nested inside, or perfectly confounded with, a factor
  the upstream constraint says the object cannot support. Where an upstream tool has written a
  `constraint_on_use`, the plan reads it and honours it.
- **The unit of analysis does not exist.** A between-sample comparison on a one-sample project.

Each of these is checkable against the design table and the object, and the plan must show the
numbers, not the conclusion. **"It probably will not work" is not a design fact.**

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
