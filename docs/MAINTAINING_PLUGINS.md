# Maintaining a plugin

**This page is for plugin maintainers. It is not for users.**

A user installs scProfile, points it at an object, and runs `plan` and `run`. They never open a
plugin, never edit one, and never write a wrapper. If a user is reading this page to get their
analysis to work, something upstream of them has failed.

A **plugin maintainer** owns one plugin for as long as it exists. The plugin is written once; the
world it wraps is not.

---

## What you own

One file. `kernels/<name>.py` — the declaration, the environment, the references, the limits, the
upstream record, `run(ctx)`, `selftest(ctx)` and, where the dataset can make the result mean
something it does not, `guard(g)`. Everything about that plugin is in it, which is what makes
ownership possible: there is no second file to keep in step.

**Module scope must be importable by the host.** Keep every third-party import inside a function,
as every shipped plugin does. The host executes your module in its own interpreter for anything
that must happen before your environment is resolved — `guard(g)` is that case today — and the
host's interpreter has none of your pins.

You own it against a moving target. The wrapped tool releases, renames a keyword, changes a
default, moves a result key, drops a python version. **None of that reaches the user as a bug in
their data if you are doing this job**, and all of it does if you are not.

### You also own what the host would otherwise have to guess

Your plugin is written once and ships prebuilt. The builder and the planner run again on every
machine and every project, so a field you leave out is not neutral — it becomes an assumption made
later, elsewhere, about a method you wrote and they did not.

| declare | or the host will | and the cost |
|---|---|---|
| `memory_gb_base`, `memory_gb_per_100k` | assume a conservative rate, and print that it is guessing | over-provisioned waves, or a killed job if the guess is low |
| `references` with a `tier` | see no reference at all | the plan cannot warn, the report cannot name what decided the answer |
| `per_unit` / `also_cohort` | run one pooled fit | an answer describing the average of the conditions, which may describe none of them |
| `gpus` | assume none | |
| `report.figures` | lay out whatever you emitted, in emission order | nothing says what a panel is for, and an absent panel is indistinguishable from one nobody wanted |

**Measure the memory, do not estimate it.** Every run fits both terms from your plugin's own
instances and prints them ready to paste. The estimate this project's most expensive plugin
carried was wrong in *both* terms against its first real measurement. A per-unit plugin gives one
point per unit for nothing, which is exactly what separates a baseline from a slope; a plugin that
runs once per cohort gives one point, which cannot — the fit says so and charges the whole peak to
the rate, the direction that over-provisions rather than under-requests.

**Declare a reference you cannot verify.** `bundled` (inside a package, pinned by its version) and
`runtime` (fetched while the tool runs) exist so the tool can *name* them. Declaring them costs you
nothing and buys a user the one warning that matters on a cluster: this method will reach the
network from a compute node.

---

## When a plugin needs attention

| signal | what it means | what to do |
|---|---|---|
| a user's `selftest` fails on a new machine | the constraints do not resolve there, or resolve to something that no longer works | reproduce, then fix the requirement — not the selftest |
| the wrapped tool releases | the pin is now behind; it is not automatically wrong | read the changelog against `upstream.defaults_changed`, then decide |
| `validate` warns | the declaration has drifted from what the code does | fix the declaration |
| a run reports a caveat you did not write | the host added it — a sentinel count, an excluded NaN row | nothing; that is the contract working |
| a new organism is asked for | `references.yml` covers species you declared and no others | add the entries, fetch, record the digests |

**A release is not a reason to bump.** A pin is a claim that *these versions were seen to work
together*. Upgrading replaces a tested claim with an untested one, and the selftest is what turns
it back into a tested one. Bump when there is a reason — a fix you need, a security issue, a
python version going out of support — and prove it.

---

## Updating

1. **Change the constraint.** In `PLUGIN["requires"]` — `python`, `packages`, and where the tool
   needs them `conda`, `channels` and `r`. Constraints, not pins, wherever the tool genuinely
   tolerates a range: a pin says only *that* version works, and claiming it where it is untrue
   forces an environment nobody can share.
2. **Run the selftest against it.** On a machine that matters, not only on yours. This is the
   whole check: it runs the real call and asserts the schema, not an import.

   **Your plugin may not be alone in there.** The builder resolves every plugin's requirement
   together, so tightening yours can move you out of a shared environment and into your own — and
   `install` proves the environment for *every* member, so a change of yours can surface as
   somebody else's selftest failing. That is the mechanism working: it is the failure that would
   otherwise have happened inside a user's run. `scprofile install <name> --prefix <dir>
   --dry-run` shows which environment you land in and who is in it, without building anything.
3. **Read the changelog against your `upstream` record.** Every entry in `defaults_changed` is a
   claim about the old version. A default that was wrong may now be right, or the reverse, and
   the record must say what is true of the version you pinned.
4. **Update `upstream.read`** to the date you read the documentation. That field exists so a
   later maintainer knows how stale the reading is, not to prove diligence.
5. **Check `cannot_show` still holds.** A new version can change what a method can support.
6. **Note it in the plugin's docstring** if the result changes. A user comparing two runs across
   a bump needs to know the difference is the tool and not their data.

---

## The rules a plugin must keep

These are enforced — by `validate`, by the contract tests, or by the compiler — because each was
broken once.

**Never name a user's vocabulary.** No column, no layer, no organism, no sample, in `run()`.
Those arrive as `ctx.keys[...]` and `ctx.organism`. A plugin that writes `adata.obs["cell_type"]`
works on exactly one project.

> `ctx.keys.get("lognorm")` is a **role** and is correct. `adata.layers["lognorm"]` is a **name**
> and is not. Reading back a key the wrapped library itself just wrote — `obsm["ulm_estimate"]` —
> is that library's API surface and is fine.

**Never use `os.cpu_count()`.** `ctx.cores` is the allocated share. Four plugins each reading the
machine start four times the node's worth of threads.

**Group with `ctx.populations()`, never with the raw label column.** It returns
`(mask, groups)` with the annotator's sentinels already out of the grouping, and it adds the
caveat saying how many were set aside — so you cannot mask correctly and then forget to say it.
Two of the first two plugins that grouped by `ctx.obs("label")` reported `UNRESOLVED` as a
population, and in a results table that reads exactly like a cell type that scored badly. The
per-cell result still covers every cell; only the grouping excludes them.

> **It is not `(populations, dropped)`, and `validate` refuses that reading by name.** Five
> plugins in this repository destructured it that way, which is not five mistakes but one bad
> affordance: `len(pops)` then returns the cell count, so a refusal that should fire never does
> and a headline claims a hundred thousand populations, while `if dropped:` asks the truth value
> of an array and raises. If those are the two things you want, they are on the object —
> `p = ctx.populations()`, then `p.names` and `p.dropped`.

**Refuse rather than return something empty.** `ctx.refuse(what, why)` is a result the host
records. A plugin that returns an empty answer produces a result-shaped hole nobody can tell from
a real negative.

**Declare every limit.** `cannot_show` is printed with the numbers. A result whose limits were
never written down reads exactly as authoritative as one whose limits were thought about.

**Say when an output is conditional.** `produces` may end an entry with `?` — `"obs[latent_time]?"`
— for something only some modes produce, and may glob a name chosen at run time —
`"obsm[velocity_*]"`. Without the `?` the declaration has two ways to be wrong and no way to be
right: leave the entry out and every run that produces it reports an undeclared output, put it in
and every run that does not reports a broken promise. Drift that fires on correct behaviour is
drift a maintainer learns to scroll past.

**The selftest asserts shapes, columns and finiteness — never a biological answer.** The fixture
is synthetic; there is no correct answer to check against, and a selftest that asserted one would
be testing its fixture.

---

## What you do NOT own

The contract. Reading `in.json`, resolving keys, subsetting to a unit, keeping annotator sentinels
as cells, excluding cells with NaN in a computed embedding, honouring the core share, writing
`out.json` — all of that is `scprofile/_entry.py`, shipped once and shared by every plugin.

If you find yourself writing any of it, stop: either the host is missing something and that is a
host bug, or you are about to reintroduce one of the bugs that lived in the wrappers this replaced.

---

## Checking your work

```
scprofile validate <name>                          # the declaration
scprofile install <name> --prefix <dir> --dry-run  # which environment, shared with whom
scprofile install <name> --prefix <dir>            # builds it, and runs every member's selftest
python tests/test_contract.py                      # the rules above
```

`install` is the builder and it ends in a selftest deliberately: **an environment nothing proved
is one that fails inside somebody's run.** It runs *every* member's, not only yours — an
environment shared by four and proved by one is an environment three of them meet for the first
time in a stranger's cohort.

## `report.unit_network` — the one declaration that buys figures

A plugin that writes a per-unit table of relationships between populations declares where it is
and what its columns mean, and the HOST then draws the panels. **No host code names a method**;
what a plugin declares is exactly what it gets.

```python
"unit_network": {"table": "tables/edges.csv", "source": "source", "target": "target",
                 "weight": "score", "weight_scale": "per_object",
                 "group": "pathway", "member": "interaction"}
```

| declared | what it earns |
|---|---|
| `table`, `source`, `target`, `weight` (required) | the sender-by-receiver matrix, the ring, the chord and the role scatter per arm; the difference matrix and the role shift per contrast; the interaction where the design supports one |
| `+ group` | the flow ranking and the group-by-population role heatmap per arm; the paired flow comparison per contrast |
| `+ group` and `member` | the decomposition of one group into its members |

`weight_scale` is `per_object` (the default) or `absolute`, and it decides what a comparison
between two units is allowed to claim. Where a method computes its weight over the elements
present — the usual case — two units' values are on two scales, and every between-arm panel is
drawn on each arm's own SHARE with both totals printed. **The host cannot tell which it is from
the numbers.** Declaring it wrongly does not fail; it produces a comparison that looks right.

An unrecognised key here is an **ERROR**, not a warning: a misspelt column name removes panels
in silence, and a plugin that has lost three looks exactly like one that declared less.
