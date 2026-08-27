---
name: plugin-figures
description: Design, declare, draw and verify the figures of a scProfile plugin that wraps an external analysis tool - from what the tool actually computes to a page that passes `scprofile standard`. Use whenever you are adding, rebuilding or fixing a plugin's panels, writing `PLUGIN["report"]["figures"]`, calling `ctx.emit_figure`, or a page has failed count/captions/arms/identifiers/repeats. MANDATORY - WHICH figures the page carries is the USER'S choice, upstream panels and ones you invent alike: enumerate candidates from the tool's source and ask, never pick for them. NEVER read an encoding off a rendered image, a screenshot or the tool's own prose; read the function definition. Most wrapped tools ship no plots you would use, so the always-required catalogue is the RETURN CONTRACT - scale, range, whether the value is relative, and what the tool returns when it knows nothing. Also covers the figure budget, absence-is-not-zero, self-scaling that hides a finding, the unit of observation, and the seven caption fields.
---

# Plugin figures — upstream source to a page that passes

Written 2026-08-27. Every constant here was read from `scprofile/figure.py`, `standard.py`,
`declare.py`, `report.py` and `plugin.py` in this repository, not remembered. Every incident
attached to a rule is **one instance**; read each as *the shape this failure takes* and expect it
in a different costume. The instances came from wrapping tools of two shapes and both are covered
throughout: a tool that ships a large catalogue of its own published plots, and a tool that ships
a scoring function, a fitted model, a table, or a value per observation and a label — and no
plotting code you would use. **The second shape is the common one here**, so read anything phrased
as an upstream panel as conditional on the tool having one.

The order below is the order the work happens: establish the encoding → choose which figures →
declare → draw → look → disclose → budget → verify.

## How to read the CHECKs

Every rule below ends in a question with a yes/no answer. Three standing rules about them:

- **A threshold you set yourself is written down before the render that tests it**, with its
  value and why — the ink floor, the correlation bound, the scaling tolerance, the agreement
  tolerance. A threshold chosen after seeing the measurement is the measurement wearing a check's
  clothes. It goes in the plugin file, beside the panel it governs.
- **A failed check has three outcomes and never a fourth**: fix the panel; drop the panel and
  declare it `required: False` with a `when_absent` naming the failure; or `ctx.refuse(what, why)`
  for the whole plugin. Shipping the panel with the failure described in its caption is not one of
  them — that is the text a 32-word cap truncates first.
- **Record what you measured, not how many attempts it took.** A round count is bookkeeping
  nobody can falsify.

## Rule zero — THE ENCODING COMES FROM THE SOURCE, NEVER FROM A PICTURE OF IT

> **A rendered figure tells you what the tool drew once. Only the function definition tells you
> what it draws.**

You may not reproduce an upstream encoding until you have read the function that produces it, the
arguments the example passes, and the defaults that apply to the ones it does not. A screenshot, a
paper figure, a blog post and the tool's own prose are all inadmissible as the source of an
encoding.

**One instance.** A wrapper defaulted to `layout="circle"`. Every example chunk commented
`# Hierarchy plot` passed only `vertex.receiver` and in fact drew a circle plot — the argument is
a formal of the wrapper and is silently swallowed, no error. A second argument was dead code,
overwritten inside the body. Nothing rendered would have shown either.

**This is mechanical, not moral.** `emit_figure` calls `fig.savefig` (`plugin.py:632`): it takes a
matplotlib figure and nothing else, and there is no route by which a PNG written by R's grDevices
or by a CLI's `--plot` flag becomes a figure on the page. You are **reimplementing** the encoding
in matplotlib from the tables the tool returns, never capturing it — and a picture is not a
specification of something you have to rebuild. A plugin wrapping an R package redraws all eight
of its figure families in matplotlib from R-returned tables.

**Where the source is.** `scprofile doctor --prefix <dir>` prints, per plugin, the state of its
environment and the interpreter it resolved to (`runner.env_state`). The wrapped package sits
under that prefix — `<prefix>/…/lib/R/library/<Tool>/R/` for an R tool,
`<prefix>/…/lib/python3.*/site-packages/<tool>/` for a Python one. Read it **there**, in the
version the plugin pins, not in whatever is installed on your machine. For an R S3 generic, resolve
the method first (`getS3method`, `getAnywhere("fn.default")`): the generic's body is one
`UseMethod` line, so grepping it reports every formal as unread.

**When the tool publishes few figures or none**, rule zero still binds and points elsewhere: the
encoding you must read from source is the **return contract**, catalogued in Step 1a. You are then
the author of the encoding, with nothing upstream to inherit blame, and every check in Steps 5–8
applies unchanged.

**That is the normal case, not the awkward one, and this document is not a retrospective about a
tool with a big plot catalogue.** Across the 51 shipped figures, **not one calls an upstream
plotting function.** `velocity` used to call one and says in-line why it stopped: the call "proved
the tool's plotting imports and nothing about the code that actually draws" (`velocity.py:1624`). A
catalogue of upstream plots tells you what somebody else chose to show; the return contract is what
your panels are made of either way. So **Step 1a is required of every plugin, and Step 1b only of a
plugin whose upstream publishes plots.**

## Step 1 — Catalogue what the tool RETURNS, and what it plots, before designing anything

**Where both catalogues live: in the plugin file.** `PLUGIN["upstream"]` — `docs`, `read`,
`defaults_changed`, `not_used`, `gotchas` — with the return-contract table and the per-call table
in the module docstring beside them. A plugin is **one file**, `kernels/<name>.py`;
`docs/MAINTAINING_PLUGINS.md` states it
("What you own. One file… there is no second file to keep in step") and `kernels/decoupler.py`
says why the record moved in: *"In the directory shape this was a separate `UPSTREAM.md` that had
to be kept in step with the wrapper; here it is in the file it describes, which is the only place
it cannot drift from."* `declare.check` already ERRORs on a plugin that `wraps` a tool and records
no `upstream.docs` (`declare.py:466`), so this is the field the host is looking for. `scprofile
scaffold`'s `UPSTREAM.md` template is written into `Path(kernel.path)` and therefore only lands
for the directory-kernel shape, which no shipped plugin uses.

**1a — the return contract. Required of every plugin, whether or not the tool draws anything.**
You are reimplementing in matplotlib from what the tool hands back, so what it hands back is the
material every panel is made of. One row per field the plugin reads — a column, an `obs`/`var`
key, an `obsm` array, an attribute of a fitted estimator, all of them.

| column | why |
|---|---|
| field | the name as it appears in the returned object, and where it lives |
| what one element is | the entity one element describes — an observation, a pair, a feature, a group, a unit. This is Step 8 field (3), and it is decided here rather than at caption time |
| units and scale | raw, count, log, rank, probability, rescaled. **Never leave the scale implicit** |
| theoretical range | what the quantity CAN take, not what this run took. An axis, a colour scale and the null panel of Step 8 are all drawn against the first |
| relative or absolute | is the value computable from one entity, or does it depend on the set present — a min-max rescale, a rank, a share, a normalisation over whatever is in the object? **A relative value cannot be put on a shared axis across arms, subsets or runs**, and this column is what says so before a panel does it anyway |
| depends on which choice | the parameter that fixes the value — an origin, a root, a reference level, a baseline, a k, a threshold. A quantity that moves when a parameter moves is a property of the run and the parameter goes on the panel |
| degenerate values | the sentinel for *not computed*, *not assigned*, *not converged*, and whether it is distinguishable from a measured value. Feeds Step 6 |
| assigned without computing | every branch returning a value the tool did not measure — an empty-input guard, an exception handler, a constant fallback. Feeds C16 |

**CHECK (A0):** is there a row for every field the plugin reads, each with its scale, its
theoretical range, an answer to *relative or absolute*, and its sentinel named? Is the count of
fields read but not catalogued zero? A blank scale column is not a catalogued field, and "the
numbers the tool returns" is the name of the category rather than the catalogue.

*One instance, from this repository, and the tool draws nothing you could have looked at.*
`pseudotime` records that the wrapped tool's own commitment score "is MIN-MAX NORMALISED to [0, 1]
over the cells present, so a dataset in which every cell is evenly split still returns a score
spanning the full range" — a *relative* value, which on a shared axis across arms would have drawn
a difference between them out of a constant. It is not used; a raw entropy against its `log2(k)`
ceiling is drawn instead, absolute and judgeable without knowing the rest of the dataset. Nothing
in the returned array shows the difference. It came out of reading the function.

**1b — enumerate and count the upstream plot calls**, when the tool has any. Cheap, and it is
**half** of what Step 2's list is built from — the other half is the coverage enumeration over your
own output table, which Step 2 says comes first. Every plot call across every document the tool
publishes, with a count and the document list. Grep the docs, notebooks, vignettes and tests for
the tool's plotting namespace and count. The denominator is a **count**, not a verification.

**CHECK (A1):** does the catalogue state **N calls across M documents**? *One instance:*
121 plot calls across 11 documents. Without the denominator you design around the two or three
usages you read first and meet the fourth pattern after the API is fixed. The other end of the
range is M = 0 — a tool with no plot call anywhere — and the catalogue says so in one line rather
than not existing. **M = 0 does not shorten Step 1**; it moves the whole weight onto 1a, and 1c
below then resolves the functions that COMPUTE the fields, by the same six columns.

**1c — resolve and verify**, over the calls behind the figures the user chose in Step 2, and — when
there were no upstream plot calls to choose from — over the functions that COMPUTE the 1a fields.
No others. Verifying 121 calls to build four panels is the wrong spend; not knowing the denominator
when you present the list is how you present four of twelve as though they were all of them.

| column | why |
|---|---|
| call | the plot call as the example writes it, or the computing call as your plugin writes it |
| defined at | file and line, **as of the pinned version**. A name you cannot resolve is not catalogued |
| args passed | every argument the example, or your plugin, passes |
| args read | is each formal's value **reachable at the point of use** — not shadowed, not overwritten by a sibling, not swallowed by `...`? Trace it to the call it reaches |
| effective defaults | the value applying to each argument NOT passed. Look it up, do not infer it |
| return contract | returns an object the caller draws, or draws as a side effect and returns nothing |

**CHECK (A2/A3/A4):** every name resolved (ratio 1.00)? every passed argument's value reachable —
count of passed-but-unread rows 0? zero unrecorded return contracts? A name-appearance test is not
enough: the dead argument in rule zero's instance appears in its body, on the line that overwrites
it.

**CHECK (A5) — the version stamp.** Does the catalogue name the tool's **version and commit, and
the date read**, and does the pinned version equal the installed one? Every `defined at` is a
`path:line` *as of that commit*, and a departure declared under Step 8(7) departs from a named
version, not from "upstream". On any upstream version change, re-resolve every row before trusting
the figures again — a re-render that still runs is not evidence, because a changed default renders
silently.

**Reimplement the consequential quantities.** Not every plotted number — a count you also emit as
a table is derived twice already. Reimplement every quantity the tool **computes** rather than
counts, every quantity a headline or a ranked order is read off, and anything feeding an area or a
colour scale. Derive it a second time by a route sharing no code with the upstream call, over
**all** real items.

**CHECK (A6/F25):** is the verification script's import set disjoint from the module under test?
all items, not a spot check? are `n_items` and `max_deviation` recorded — **against a tolerance
declared before the comparison was run**, and does disagreement abort the build? For a float
quantity state the tolerance (one instance agreed to 3e-15); for a set-valued result the tolerance
is **exact identity of the names**, not equality of counts. And does the catalogue record which
quantities you judged consequential **and which you did not**? That judgement is unmechanised, so
it must at least be visible. *One instance:* reimplementation found the upstream centrality routine
singular whenever ≥2 nodes are absent from a sub-network; its `tryCatch` substituted a row of
zeros indistinguishable from a measured zero, in 60 of 68 real cases, all finite and plausible.

## Step 2 — ASK THE USER WHICH FIGURES. IT IS NOT YOUR CHOICE.

Which figures the page carries is a scientific decision belonging to whoever asked for the plugin —
whether the candidates are the upstream tool's own plot calls or panels only you will draw. Do not
select for them, and do not select implicitly by building the ones that are easy.

**Two cases, one exchange.**

- *The tool publishes more panels than a page can hold.* Enumerate them from the 1b count.
- *The tool publishes few or none* — a scoring function, a fitted model, an estimator returning a
  value per observation and a label. Then the candidates are **the 1a fields, one row each**, the
  levels of Step 2b, and the checks the method's assumptions require; the enumeration is **yours**,
  which makes asking more important rather than less, because nothing upstream constrains what you
  would have drawn. This is the case for most plugins here, not the exception.

*The columns below are the rule. The rows are one tool's, and row 4 is what the second case looks
like — yours will name different things.*

```
#   candidate                  documented in      encodes                          our data supports
1   <tool>::plot_network       vignette 1, 3, 7   per-pair strength, arc = count    yes
2   <tool>::role_scores        vignette 2         centrality, 2 channels            NO - singular in 60/68, see A6
3   (ours) assumption check    none - we draw it  drawn vs. modelled dispersion     yes
4   (ours) per-unit spread     none - ours        the 1a field per entity, by unit  yes
```

Then ask, in one message: **which of these should the plugin carry, and which is the result as
opposed to a check on the method?** Say what a page can hold (Step 3) so the choice is made
against the real budget, and say which entries you would refuse to draw and why. Then wait.

**CHECK:** does the record contain a message enumerating **at least as many candidates as the page
can hold**, and a reply choosing among them? An empty or pre-filtered enumeration is not a passed
check — show the ones you would refuse and why rather than omitting them. If you built panels
before that exchange, you chose.

**And enumerate by COVERAGE of your own output before you enumerate by what is published.** An
enumeration assembled from a catalogue of upstream plots is ordered by what those plots look like,
and the striking ones cluster at the coarse end. List every entity level and grouping column your
own result table can address — the pairing, the group, the individual feature, the constituent
identifiers, any annotation class — and check each has a candidate. A level with no candidate is
not a level nobody wants; it is a level nobody looked at.

*One instance.* An output table addressed four levels: pair-of-groups, group (68 values),
individual feature (255 values), and constituent identifier. Sixteen panels were built and all but
one sat at the coarsest two. The finest level — nearly four times as many values as the level above
it, and the level at which an experimental follow-up is actually designed — had no representation,
and the most-published panel type of that whole method family was never offered as a choice. The
enumeration had been built by visual distinctiveness and nothing checked it against the table.

- **C2b** For every column of your primary output table that names an entity or a grouping — the
  levels are 1a's *what one element is*, plus every grouping the design table names — can you
  point to a candidate figure that puts it on an axis, a facet, or a colour channel? If any column
  has none, the enumeration is unfinished — extend it before asking, and if you still would not
  draw that level, put it in the list with the reason so the choice is theirs.
- **C2c** Does the offer name at least one candidate you considered and would leave out, with the
  reason? A choice can only range over what was shown. Presenting a filtered list and then treating
  the reply as full coverage converts your omission into their decision, which is worse than the
  omission — a gap is visible, a laundered gap looks settled.

## Step 2b — THE GROUP-LEVEL COMPARISON IS THE MAIN FIGURE. THE UNIT-LEVEL VIEW IS SUPPLEMENTARY.

> **A figure that shows one state of the world compares nothing, however well it is drawn.**

Three levels the word "unit" can mean, and they are not interchangeable:

| | what it is | what it can carry |
|---|---|---|
| **one unit** | a single sample, animal, donor, run | that unit, and nothing else |
| **pooled cohort** | every unit analysed together as one | a description of the cohort, and **no contrast** |
| **group / arm** | levels of a design factor compared, with the **unit** as the unit of replication | a contrast |

The pooled cohort is the one that gets miscounted. It looks like the whole dataset and it is
often beautiful, so it is easy to file as the main result — but pooling is what *removes* the
contrast, and a pooled panel answers no question about the design.

**So: for every figure family, the group-level version is what goes on the page. The pooled or
per-unit version goes to the supplementary set, and only if it answers something the group-level
version cannot.** Aggregate per unit FIRST, then compare across units; never pool observations
across units and compare the pools.

*One instance, and it is the coordinator's error rather than a builder's.* A builder produced four
panels of one figure family: a faithful single-sample reproduction of the published encoding, a
coverage panel, **and two group-level arm comparisons**. The coordinator put the reproduction and
the coverage panel on the review page and left both comparisons off — selecting what illustrated
the METHOD over what answered the QUESTION. The scientist's first response was that the figure
showed one sample and no comparison. Nothing in the process had asked.

- **C2d** For every figure family on the page, is there a version whose panels are levels of a
  design factor, with the unit as the unit of replication? If the only version is pooled or
  single-unit, it is not finished — build the group-level one or state why the family cannot have
  one (see the exempt cases below).
- **C2e** Can a reader determine the unit from the figure ALONE — a stated n per arm, a panel
  title, an axis label? Cover the caption and look. A figure whose unit a reader cannot determine
  is the modal published failure of this kind: in one survey of 39 papers using a widely-used
  method, **23% never stated their unit at all**, the same size as every other category but one.
- **C2g** Does any single unit dominate an arm? Compute each unit's share of its arm — of the
  quantity the panel sums, or, where the panel sums nothing, of the observations it draws and of
  the entities it finds — and print the largest. A per-observation value with no arm total still
  has this failure: the arm's distribution is whichever unit contributed most of the marks.
  *One instance:* one animal of five carried **48% of its arm's entire signal**
  and had 595 significant edges against 84-145 for the other four - it was the deepest library in
  the cohort, so "the arm" was substantially "that animal". A comparison in which one unit is half
  of one side is not a comparison between groups, and no summary panel shows it.
- **C2h** Print what a restriction COSTS. Restricting to entities detected in every unit of both
  arms is the right move (see D21) and it is not free: in one set it removed **79.2% of all
  observations** and 23 of 68 features. A restriction whose cost is not stated reads as though the
  full data supported the result.
- **C2f** For every supplementary figure, name the question it answers that the main figure does
  not. If you cannot, delete it — a supplementary figure nobody needs is a figure a reader still
  has to read.

**Families that legitimately have no group-level version**, and the test is that their subject is
not the biology:

- a **rank- or parameter-selection curve** — its subject is a choice you made;
- a **demonstration of a defect** in the upstream encoding — its subject is the method, and it is
  most honest drawn on whatever data shows the defect most plainly;
- a **manifold or clustering of the pooled result** where the entities being embedded are features
  rather than units — an arm-split version would embed two manifolds that cannot be compared
  coordinate-wise;
- a **coverage panel** whose whole job is to show what a window leaves out.

Mark these deliberately rather than by omission. A family exempted because nobody wanted to
rebuild it is not exempt, it is unfinished.

**A group-level version you must NOT build:** one whose arms differ in whether an entity is
present at all. If a population, feature or category is absent from one arm because it fell below
a per-unit floor, an arm comparison of it compares PRESENCE and will read as the strongest effect
on the panel. Restrict to entities detected in every unit of both arms, name what the restriction
removed, and say what the restricted set leaves. See Step 6, D21.

## Step 3 — Declare, and the budget arithmetic

`PLUGIN["report"]["figures"]`, a list of mappings, checked by `declare._check_report`. ERROR stops
the builder; WARN does not.

| key | required | wrong → | rule |
|---|---|---|---|
| `id` | **yes** | ERROR | non-empty, unique. What the reporter positions and `emit_figure` is called with — **the entire join** between declaration and drawn panel |
| `question` | **yes** | ERROR | non-empty. The panel's `<h3>`; first `HEADING_LEAD_WORDS = 14` words visible, remainder behind `<details>` |
| `shows` | **yes** | ERROR | exactly one of `diagnostic`, `result`, `comparison`. **This and nothing else orders the page**, diagnostics first: a result under a failed check is a number, not an answer |
| `source` | **yes** | ERROR | non-empty string. **Checked for non-emptiness only — never cross-checked against the file `emit_figure(source=...)` links.** Two different `source`s can exist and only the emitted one becomes the page's link |
| `required` | no (default `True`) | — | `False` makes an un-emitted panel a property of the data rather than a defect |
| `when_absent` | when `required: False` | WARN | the reason printed in place of the panel |

**`comparison` is not "compares the arms."** That is the `arms` caption criterion, which any
`shows` value can satisfy. `declare.py:105` defines it as *"the same question answered a second
way. Needs another plugin, so it is the one kind of panel that can be absent because something
ELSE did not run"* — so it belongs with a `reads_with` naming that plugin, and is normally
`required: False` with a `when_absent`. **Zero of the 51 shipped figures use it.** If you reach for
it, check you do not mean `result`.

Block level: no `report` block → WARN, and the page becomes an undifferentiated list in emission
order. `report` not a mapping, or `figures` not a list → ERROR; empty list → WARN. Keys outside
`("figures", "reads_with", "unit_metrics")` → WARN. `reads_with` naming this plugin → ERROR. A
figure declared while `requires.packages` is non-empty and lacks `matplotlib` → ERROR
(`declare.py:458`) — `ctx.plot()` imports it in this plugin's own interpreter. **A plugin that
declares no `requires.packages` at all is not caught**, which is exactly what a new one-file
plugin looks like.

```
MAX_FIGURES      = 12    # standard.py - <figure> elements a page may carry
BY_ARM_PANEL_CAP =  3    # report.py   - reserved for the host's own per-arm panels
budget           =  9    # declared figures, for a plugin that is NOT per_unit
```

`len(figures) > MAX_FIGURES − BY_ARM_PANEL_CAP` is an ERROR at declaration time. Three things the
check does **not** do, all of which still fail the page:

1. **`per_unit` plugins are skipped by the budget check entirely** (`not spec.get("per_unit")`),
   and *skipped by the budget* is not *exempt from the standard*. Only a figure emitted **with** a
   `unit` tag routes to the appendix (`report.py:1000`); a per-unit plugin's cohort-level panels
   stay on the main page and are held to `count ≤ 12`. The host adds one `<figure>` per comparable
   `unit_metric` you declare (`report.py:497`) plus one across-design panel, so **your cohort
   budget is `12 − len(report["unit_metrics"]) − 1`, counted by you, because nothing counts it.**
   Step 9's three appendix conditions must also hold or the appendix is judged as a page and fails
   `repeats` on the spot. And a `per_unit` plugin declaring no `report.unit_metrics` is an ERROR
   (`declare.py:316`).
2. It counts **declared** figures. The `count` criterion counts rendered `<figure>` elements,
   which also includes emitted-but-undeclared panels and host-drawn blocks.
3. What the host actually spends on a cohort page today is **1**, not 3: `_by_arm_block` collects
   every (column × factor) pair into one `<figure>` of inline SVG strips, and nothing in
   `report.py` reads `BY_ARM_PANEL_CAP` — it is a reserve, not a measurement. `declare.py:222`
   still carries the note that one shipped plugin declares 9 and renders exactly 12 with **zero**
   headroom; that was measured under the older host, which wrapped each pair in its own `<figure>`.
   Trust neither number about your own page — measure it.

**CHECK:** `scprofile validate <name>` clean on the report block? within budget for your plugin's
shape? every `required: False` figure carrying a `when_absent`? Across the 51 shipped figures the
correspondence is exact — 23 optional with 23 `when_absent`, 28 required with none.

## Step 4 — Draw. What the emit point does, and what it does not.

```python
plt = ctx.plot()                      # matplotlib.use("Agg") + the RC block. CALL THIS FIRST.
fig, ax = plt.subplots(figsize=(ctx.figure.SINGLE, 2.4))
...
ctx.figure.rasterize_points(ax)       # dots become an image; text and axes stay vector
ctx.emit_figure("F1_coverage", fig, caption="...", source=df)
```

`ctx.emit_figure(name, fig, *, caption="", source=None, close=True)` — `plugin.py:632` — writes
`figures/<name>.png` and `.pdf`; **reads DPI from rcParams**, so 400 after `ctx.plot()` and 200
otherwise; applies `figure.fit_column(fig)` **inside a bare `try/except: pass`**; saves with
`bbox_inches="tight"`, which is *why* `fit_column` is needed, since tight bbox ADDS everything
outside the axes to the canvas rather than fitting it in; writes `source` to
`figures/<name>.csv` if it has `.to_csv`, else records the path given; appends
`{"id", "path", "vector", "source", "caption"}`; **closes the figure**; returns the PNG `Path`.

It does **not** apply the RC block. Without `ctx.plot()` you get 200 dpi and matplotlib's Type-3
fonts — `pdf.fonttype = 42` is the non-negotiable one, and its absence is discovered at
resubmission. `fit_column` is best-effort at both call sites: **a figure that will not measure
ships over-wide, silently.**

| `ctx` | use it for |
|---|---|
| `figure.SINGLE` / `DOUBLE` | `85/25.4` and `174/25.4` — **inches**, for `figsize=`. Passing 85 asks for an 85-inch canvas |
| `figure.palette(labels)` | `{label: colour}` keyed on the **sorted** labels, so two panels over different subsets agree. `PALETTE_LIMIT = 16` hues, cycles silently above that |
| `figure.palette_collisions(labels)` | `[(colour, [labels])]`. Call it; if non-empty, say so on the panel or label points directly |
| `figure.rasterize_points(ax)` | every collection rasterised, text stays live. This is about file size, **not** overplotting |
| `figure.fit_column(fig)` | snaps to the nearer of `SINGLE`/`DOUBLE`, ≤10 passes, never below `MIN_PAGE_SHARE = 0.7` of declared; returns the width in mm. Safe to call yourself — it exits when the figure already measures its column and never grows one |
| `figure.legend_outside(...)` | **a size legend must pass `markerscale=1.0`**, or the key says something false about every dot |
| `figure.split_basis` / `basis_label` / `short_labels` | `umap_scanvi` → `"UMAP 1  (of scanvi)"`; shortest unambiguous tails, returned as a mapping so the full path still goes in the source table |
| `figure.save(...)` | returns a manifest entry and **does not register the figure with ctx**. Use `emit_figure`. |
| `fixture(n_cells, n_genes, *, genes, labels, seed)` | `plugin.py:703` — the host's synthetic AnnData, `counts` and `lognorm` layers already built. **Every absence and scaling fixture in Steps 6–7 starts here.** Hand-rolled ones have been too small for the tool's own coverage check, missing the label column, and on the wrong scale |
| `layout()` / `layout_key()` | the two-column layout to draw on, or `None`. **There is no fallback to the first two columns of something wider** |

**Colour is never the only channel carrying the claim.** Nothing in `standard.py` looks at colour,
so a panel of hard-coded reds and greens passes every mechanised check here. Categories come from
`figure.palette` (Okabe-Ito + Tol, both designed for colour-vision deficiency) or from a scheme you
can name and cite. `figure.py:88` states that together they give *"twelve hues that stay separable,
which is about where hue stops working as an identifier at all"* — **four below `PALETTE_LIMIT =
16`**, and `palette_collisions` catches identical hues only, never two a deuteranope cannot
separate. Continuous channels use a perceptually uniform map, or a diverging map centred on the
value that means *no difference*; rainbow and jet invent edges.
**CHECK:** above twelve categories, is every mark direct-labelled or the panel split? Rendered
through a deuteranopia simulation and through greyscale, is every distinction the caption claims
still readable? A distinction surviving only in colour needs position, shape, hatch or a label.

**A diverging scale must be centred AND symmetric. Centring alone is not enough.** The usual
constructor — `TwoSlopeNorm(vmin=data_min, vcenter=neutral, vmax=data_max)` — pins the neutral
value to the middle of the *bar* and then gives each half whatever slope its own side of the data
demands. Whenever the data is skewed, the two halves carry different units-per-millimetre, so two
marks equidistant from the neutral colour mean different magnitudes and the picture invites exactly
the comparison it cannot support. Set the limit from `max(|min|, |max|)` in both directions
instead. The cost is that the weaker side's ramp is not fully used, and that is the honest
rendering of a one-sided contrast, not a defect to tune away — say in the caption what fraction of
it the data reaches. This applies to every signed quantity a plugin draws: a log fold change, a
Δ-abundance, a z-score, an enrichment, a residual, a velocity component.
**ONE INSTANCE.** A signed contrast drawn with `TwoSlopeNorm(vmin=lo, vcenter=0, vmax=hi)` ran two
factors from the same data through the same code. One was −19.90 to +19.81 and distorted by
1.005×; the other was −22.50 to +14.63 and distorted by **1.538×**. The bug was invisible on the
first panel and wrong by half on the second, and both panels rendered without warning and looked
equally plausible. The ticks compounded it: derived as `[lo, lo/2, 0, hi/2, hi]`, they sat
asymmetrically on the bar and left both ends unlabelled, so the key confirmed the distortion
rather than exposing it.
**CHECK:** for every diverging scale, does `abs(vmin) == abs(vmax)`? Are the tick values symmetric
about the neutral value, and is the neutral value itself one of them? Would a reader measuring two
marks equidistant from neutral, one each side, be right that they are equal in magnitude?

**Determinism.** A layout, a chord order, a jitter or a tie-break that varies between runs makes
the same data draw a different picture, and a reader diffing this report against the last one sees
motion that means nothing. **CHECK:** is a seed recorded on the panel or in its source CSV, is
there a total order on ties, and does the category order come from a sorted list rather than
encounter order?

`ctx.refuse(what, why)` sets `status = "refused"` and **returns** — you must return after it. It
is the only status that switches off `feedback.figure_drift`; `partial` is still held to the
declaration. Do not emit a figure named `<pluginname>_across_design`: the host writes its own
across-design panel to that exact path at **report** time, after your run, so it silently replaces
your image and duplicates a basename on the page.

## Step 5 — Render it, OPEN it, iterate. Then turn what you saw into a measurement.

**A drawing defect does not look like a defect. It looks like a finding.** An arrowhead reserving
8× too much space reads as *an edge to somewhere else*; a band painted over a label column turns
`Pecam1` into `Pecam` and `Cd74` into `d74`, which are valid names of other genes; a reach estimate
taken off a control polygon reads as *a quarter of the manifold is empty*. That is why you open the
PNG at every round, not only at the end. **A figure whose first render is its shipped render has
not been reviewed.** The eight measurements below are failures earlier rounds already found,
mechanised so they cannot come back — a floor, not a ceiling, and the ninth failure will be found
the way these eight were. **None of them is mechanised in scProfile**; there is no chokepoint
asserting them, and `standard.check_page` never opens a PNG.

**THE MEASUREMENTS DO NOT REPLACE LOOKING, AND EVERY REDRAW IS RE-SCANNED BY EYE.** The eight
rows below are failures already found, mechanised so they cannot return. They are a floor. No set
of assertions covers what a person sees in one glance — that a panel is three-fifths empty, that
two categories are the same colour to a reader, that a caption and its marks disagree, that the
thing is simply ugly. So: **after every change that alters a rendered figure, open the image and
look at it again.** Not the code that made it, not a grep of the output, not the assertions
re-run — the image. If the figures are being rebuilt by an agent, the re-scan is done by an agent
*looking at the PNG*, and its report names what it saw and where.

*One instance, and it is the reviewer's rather than the builder's.* A page of figures was rebuilt
and verified with `grep` against the generated HTML: every check passed. Three panel titles were
rendering `&mdash;` and `&times;` as literal text, because titles pass through `html.escape` and an
entity written there survives as characters. `grep` for the entity found it present and reported
success — the check and the defect agreed with each other. It was found only when somebody looked
at the page. **A code check confirms what you thought to ask; looking is how you find what you did
not.**

- **C21** For every figure changed since the last review, is there a record of somebody opening the
  rendered image afterwards and reporting what they saw? Re-running the assertions is not that
  record. If the answer is no for any changed panel, the review is not finished.
- **C22** Was the artefact a reader will actually see the one that was looked at? A downscaled,
  recompressed or palette-quantised web copy is a different image from the print original, and a
  quantisation that breaks a diverging scale or blurs 5 pt type is invisible in the original and
  invisible to every assertion. Look at both.

**Iterate on a fixture, not on the cohort.** Layout, labels, glyphs, paths, aspect and size are
properties of the *drawing*: build a reduced input with the same shape and the same degeneracies —
`ctx.fixture` plus the specific absences, ties and extremes of the real data, or
`tests/make_fixture.py`, which writes a synthetic object carrying labels, annotator sentinels,
several samples and an integrated embedding. Cache anything expensive to the plugin's own output
and redraw from the cached table. Then render once at full scale and **re-run all eight
measurements on that file**, because the ones that fail at scale are the ones a small input cannot
show: tight-bbox growth from long real labels, palette collisions past sixteen real categories, and
ink and occlusion at real n.

**Run them in two places, because `emit_figure` changes the figure and then closes it.** Before
emitting: call `ctx.figure.fit_column(fig)` yourself, then `fig.canvas.draw()`, and measure against
`fig.canvas.get_renderer()` — the figure you measure is then the figure that ships. After emitting:
measure *size* and *ink* on the written PNG. Nothing here can be run on a closed figure.

Rows 1–4 and 8 fire on every panel. Rows 5–7 fire only when the panel builds geometry by
arithmetic instead of letting the library place it.

| assert | yes/no check | one instance |
|---|---|---|
| **size** | read pixel dims and DPI back off the written PNG, convert to mm, `abs(measured − declared)/declared < 0.01`; and read `figure.figsize`, `figure.dpi` and `savefig.dpi` back out of `rcParams` immediately before the save | panels saved at 148 / 187 / 246 / 354 mm while declaring 85 or 174 — from tight bbox, and separately from a style module re-applying an rcParam after `ctx.plot()` and doubling every measured size at once |
| **no crop, no overpaint** | every artist's bbox (legends included) contained in the figure bbox; for every text artist, overlap count against patches drawn later in z-order is 0 | the label truncations above. Separately, a legend below the axes cropped away by the tight bbox |
| **glyphs** (any non-ASCII text) | query the resolved font's cmap for every codepoint of every string; zero missing | chosen symbols rendered as tofu |
| **wrapping** | joining the stripped wrapped lines with single spaces reproduces the input exactly, and every fragment is in the input token set | a long identifier split at a line break into two nonsense words |
| **constructed paths** (you assemble a vertex/code list) | the code sequence parses as a complete grammar and `len(vertices)` matches the arity the codes imply; sample the curve at ≥100 points and match the axis limits to the **sampled** extent, not the control polygon | a cubic whose final CURVE4 was overwritten with CLOSEPOLY, after which the vertex array is read out of phase and ribbons fly off on tangents |
| **geometric reservations** (an element reserves space by arithmetic — arrowhead, offset gap, label pad) | render one element with known endpoints, measure the gap in **data** coordinates, equal to the intended reservation ± 1 px | a head-length reservation 8× too large |
| **aspect** (a channel is area, or a size key claims a diameter) | axes aspect equal **and** a rendered size key measures 1.000 ± 0.01 width/height in pixels | size keys drawn as ellipses |
| **ink** | rasterise, 4×4 grid over the axes, no contiguous quadrant below your stated ink threshold unless declared empty | the empty quarter above — found by eye, mechanisable by this |

## Step 5b — A CHANNEL THAT IS DRAWN BUT CANNOT BE DECODED

> **Encoding a quantity is not the same as making it readable. If a reader cannot recover a value
> from the channel, the channel is decoration that looks like evidence.**

An independent scan of one rebuilt set of 23 figures found this in **at least 15 of them**, in six
disguises. It was by far the most common defect, and every instance had passed code review:

| disguise | what it looks like |
|---|---|
| a ramp not orderable by eye | a rainbow applied to a sequential quantity: not monotonic in lightness, so two marks cannot be ranked |
| a size channel with no key | area encodes something and nothing says what, or the legend's range is smaller than the eye can separate |
| a plotted track with **no axis at all** | a marginal bar, density or secondary track with no ticks and no numbers |
| an axis that exists **once** | a grid of twelve panels labelled only under the leftmost column; a reader maps position across a thousand pixels |
| an **undeclared** non-linear ramp | ticks at equal pixel spacing for unequal intervals, so two marks 1.6x apart in magnitude carry identical intensity — and its sibling figure uses a linear ramp, so the pair cannot be read as a pair |
| a stack the caption asks you to count | *"count the units"* over marks that overlap into one blob |

The fix is not more caption. It is either **make the channel decodable** — a key with a real range,
an axis with ticks, a lightness-ordered ramp, jitter or a beeswarm so marks can be counted — or
**stop drawing it**, because a channel a reader cannot decode is one they will decode wrongly.

- **C23** For every visual channel in the panel (position, length, area, colour value, colour hue,
  opacity, texture), name the quantity it encodes and point at the key, axis or tick scale a reader
  recovers a value from. Any channel without one is either keyed or removed.
- **C23b (a floor makes a channel AFFINE, and affine is not proportional)** A size or width
  channel drawn as `floor + k * f(value)` is not proportional to the value, and a key drawn only
  at large values will not reveal it — the key confirms the mapping over the range where the
  intercept is negligible and says nothing about the range where it dominates. Do not write
  "proportional", "= count" or "area = X" over an affine map. State the mapping including its
  intercept, and draw a key at the SMALLEST value actually plotted, not just at round large ones:
  two keys a decade apart that come out nearly the same size make the floor self-evident and need
  no prose. Note also which end the floor is at — an additive offset on a RADIUS inflates every
  disc, not only the small ones, so a footnote saying "the smallest are drawn slightly larger than
  proportional" misdescribes the mechanism as a clamp when it is a shift.
  **ONE INSTANCE.** A network panel declared "node area = significant L-R pairs (in + out)" and
  drew keys at 100 / 500 / 2,000 whose measured areas were 1 : 1.69 : 3.41 — a 20x value rendered
  at 3.4x the ink, the 100 disc carrying 5.9x and the middle 500 disc 1.99x the area proportionality
  gives them, because radius was `rmin + (rmax - rmin) * sqrt(v / vmax)`. Its edge widths were
  affine too: over a 466x range in the data the drawn ink spanned 10.3x. The page carried a
  footnote about the floor and it described a clamp on the small end, which is not what the code
  did. The floor itself was right to exist — without it a small-but-present entity draws the same
  as an absent one, which is a worse error — so the repair is the declaration and the key, not the
  floor.
  **CHECK:** for every size, width, area or opacity channel, write down the actual mapping from
  value to ink including any intercept, clamp or `min()`. Is the word on the page true of THAT
  mapping? Does the key include the smallest value the panel actually draws? Measure two keys a
  decade apart in the rendered file: is their ink ratio the ratio the caption claims?
- **C23c (a parameter can be honoured in one function and defeated by a default in another)** When
  a plugin offers a CHOICE about how to treat missing entities — impute a zero, drop them, carry
  them as NaN — that choice is usually applied in two places: where the per-unit tables are BUILT
  and where they are SUMMARISED. Thread it through one and leave the other on its default and the
  panel reports the option it was GIVEN rather than the one it APPLIED. Nothing errors, both
  functions are correct in isolation, and the figure is a lie about its own arithmetic. This is
  worst for the CONTROL panel — the one whose entire job is to show whether the choice matters —
  because it then shows that it does not, which is the most reassuring possible way to be wrong.
  Make the combination impossible rather than correcting the call site: a summariser asked to drop
  missing values, handed data with no missing values, and holding entities known to be absent
  somewhere, should REFUSE.
  **ONE INSTANCE.** A cohort panel titled "absent = left out of its own mean" was byte-identical in
  every numeric column to its sibling titled "absent = 0", because the unit tables had been built
  once with the zero rule and reused for both — so `nanmean` had no NaN to skip. Applying the rule
  for real changed 8 of 13 entities, by up to **10x** (an entity present in 1 of 10 units), and
  reordered the top five. The repair then broke a SECOND rule silently: the summariser had been
  setting its `n_units` to the per-entity present count, so `n_present == n_units` for every row
  and the label rule that attaches `(k/N)` to any dot whose n is not the full n stopped firing
  everywhere. Two rules had disagreed about what N meant.
  **CHECK:** for every option your plugin exposes about missing or excluded entities, list every
  function that reads it, and confirm each is passed the same value on the same call path. Does the
  panel drawn under option A differ NUMERICALLY from the one under option B? If they are identical,
  prove that is the data's doing and not the plumbing's. And after changing how absence is counted,
  re-check every derived count that shares the denominator.

- **C23d (provenance is a channel, and an undeclared one must be LOUD)** A panel that does not say
  what it was drawn from reads as though it were drawn from everything: the reader supplies the
  cohort the picture never claimed. This is not a caption problem — a qualification that lives only
  in a caption does not travel with the image into a slide, a grant or a referee's PDF. Put the
  unit, the n, and the denominator ON THE FACE. And make the DEFAULT loud: a drawing function whose
  `provenance` argument is omitted should print "PROVENANCE NOT DECLARED" on the panel rather than
  print nothing, because a red line is a defect somebody fixes and a blank corner is a defect
  nobody can see. Escalate when n = 1: a single-unit panel drawn in the idiom of a cohort panel is
  the one case where the reader's default assumption is wrong and nothing on the page contradicts
  it. Any plugin that can be run on one object and on many has this failure available to it — a
  trajectory fitted on one sample, a doublet rate from one library, a motif enrichment from one
  peak set, a spatial neighbourhood from one section.
  **ONE INSTANCE.** Six delivered panels of one family were each a SINGLE animal and not one
  carried a sample name, an n, a group, or the word "unit". The selecting function printed the name
  to stdout and nowhere else. The animal was the one separately measured to carry ~48% of its arm's
  signal, so the panels a reader would take as the cohort's structure were closest to that one
  animal's. The same panels drew 9 sectors where the study has 13, with nothing saying the other
  four were removed by the method's per-object cell floor rather than being biologically absent.
  **CHECK:** does every panel name its unit(s) and its n ON THE FACE, not only in the caption? If a
  panel shows fewer entities than the study has, does it say how many are missing and why? Run the
  drawing function with provenance omitted — does the rendered panel say so, or does it just look
  finished?

- **C23e (a legibility guard set below the legibility floor is not a guard)** Panels that shrink a
  label to fit a mark - a node number inside a disc, a count inside a bar, a value inside a cell -
  usually carry a threshold below which the label is placed elsewhere instead. That threshold is
  the whole mechanism, and it is easy to set it to whatever happened to look acceptable on the
  developer's screen rather than to the size type is actually readable at in print. Set it to the
  journal floor, around 5 pt, and let the label move out. A panel that draws the label anyway, one
  tenth of a point above its own threshold, has told the reader it is labelled and then refused to
  be read - which is the failure the threshold exists to prevent, passing its own check.
  **ONE INSTANCE.** A network figure's threshold was 3.6 pt against a ~5 pt floor. Its 104 in-mark
  numbers measured 3.611 to 4.000 pt at full double-column width - every one below the floor, the
  smallest clearing the guard by 0.011 pt - and the reverse-contrast two-digit ones on dark fills
  did not resolve as numbers at 1:1. Raising the threshold to 5.0 moved all 104 outside their
  marks, where they set at 5.4 pt in black on white and every one became readable. The code
  carried a comment saying "a number too small to read is worse than no number"; the constant
  beneath it permitted exactly that.
  **CHECK:** what is the smallest type size your panel actually writes, measured from the rendered
  file rather than from the requested size? Is any label placed by a size threshold set below 5 pt?

- **C23f (extracting text from a file is not looking at it)** A check that reads strings out of a
  rendered artifact answers a question about the file format, not about the page. It will miss
  anything the renderer drew as glyphs rather than text, anything composed at draw time, and -
  most often - anything present in a form the extractor was not written to expect. When such a
  check disagrees with what the panel shows, the panel wins.
  **ONE INSTANCE.** A reviewer counted standalone digit strings in a PDF's text operators and
  reported that two of thirteen marks were unlabelled, on a panel whose caption promised all
  thirteen. Opening the figure and magnifying the region showed both labels present - the drawing
  code moves a number that will not fit inside a mark INTO that mark's adjacent text, so the digits
  were there, inside longer strings the extractor's word-boundary pattern never matched. A second
  extractor written to settle it returned zero of thirteen for every file, having failed on font
  subsetting - so the tooling was wrong twice in the same direction while the figure was right.
  The claim was withdrawn and nothing was changed, which was the correct outcome.
  **CHECK:** before acting on a defect found by parsing a rendered file, did you open the file and
  see it? If the parse and the picture disagree, have you established which one is broken?

- **C23g (never name a channel by its hue in the legend)** "The amber bar means...", "red =
  higher", "the green cells are..." - each identifies a mark by a property roughly 8% of male
  readers cannot perceive, so the one reader who most needs the legend cannot use it to FIND the
  mark. The swatch printed beside the text does not rescue it, because the reader must first know
  which swatch the sentence is about. Name POSITION, SHAPE or ORDER instead: "the bar in the column
  right of the labels", "the open circles", "the upper of each pair". The hue can still carry the
  distinction; it just cannot be how the words point at it. This is separate from whether the
  palette is colour-vision-safe - a perfectly safe palette still fails if the prose says "amber".
  **ONE INSTANCE.** A legend read "amber bar: entity absent from at least one WHOLE group". Under a
  deuteranopia simulation of the delivered PNG - rendered and then LOOKED AT, not merely computed -
  that bar is olive. Every other channel on the same figure survived, because each had a text
  fallback: the group strip was coded by letters, the category swatches sat under written names,
  and the sequential ramp kept its lightness ordering. The one thing that failed was a sentence.
  **CHECK:** search the legend and footnotes for colour words. For each, is the mark identifiable
  without that word? Render a deuteranopia and a protanopia simulation, OPEN IT AND LOOK: is the
  colour the sentence names still recognisable as that colour?

- **C23h (a bottom-anchored block that grows upward needs a measuring guard, not vigilance)** Any
  text block pinned to the bottom of a figure and laid out upward - a footnote, a caveat, a legend
  column - moves toward the panels every time a sentence is added to it. The text still renders and
  the file still saves, so nothing objects; the only symptom is type struck through other type, and
  the only check that finds it is looking at the rendered image. That makes it a defect you will
  reintroduce, because the whole point of these blocks is that they get edited. Measure instead:
  compute the lowest INK of every axes - `get_tightbbox`, not `get_position`, because the axes box
  sits above its own tick labels and axis title - and refuse to draw a block that would cross it.
  Report the overlap in millimetres so the message says how much to cut.
  **ONE INSTANCE, twice in one session by the same author.** Adding a derivation to a footnote
  pushed it through a colourbar's axis label; the text was shortened, and a later edit pushed the
  same block through a panel's tick labels and x-axis title, 1.62 mm of overlap. Both were caught
  only by opening the PNG afterwards. A guard was then written, and it fired on the long text and
  passed on the original - which is the property that matters, because a guard that fires on
  correct behaviour gets switched off. The lasting fix was not shorter prose: it was moving the
  derived sentence into the caption file, where a reader can also copy it.
  **CHECK:** does the layout compute the lowest ink of the panels and refuse to overlap it, or does
  it rely on whoever edits the prose next remembering to look? Add a sentence and re-render: does
  anything object?

- **C23i (two correct numbers that read as a typo of each other are a defect of the page)** A
  panel usually quotes several counts, and two of them will sooner or later be counts of DIFFERENT
  things that land close together - a universe and a subset, a raw total and a filtered one, items
  and item-pairs. When they also happen to be near-anagrams, a reader's first conclusion is that
  one is a slip, and their second is to distrust the rest of the numbers. The fix is not to change
  either number: it is to name what each is a count OF, in the same breath, wherever both appear.
  Name the denominator on every count you print, and say when two denominators differ.
  **ONE INSTANCE.** A figure's header read "109 of 225 combinations" and a note beneath it "12 rows
  out of 255". Both were exactly right - 225 is (item x pair) combinations inside the drawn window,
  255 is the distinct items in the whole cohort, and 109 + 116 = 225 checks - but the reviewer's
  first move, and mine, was to treat 255 as a transposition of 225 and go looking for the bug. The
  repair was six words: "of the 255 distinct L-R pairs in the cohort (a different denominator from
  the 225 combinations counted above)". This is the mirror of the failure where two true facts are
  fused into one false sentence: here two true facts stay separate and still mislead.
  **CHECK:** list every count printed on the panel with what it counts and over what universe. Do
  any two differ by a digit swap or a factor a reader could mistake for a slip? Does the page say,
  at the point of use, which denominator each belongs to?

- **C23j (a layout constant derived from OPTIONAL content belongs to the row, not the panel)** In a
  multi-panel figure, some panels carry an optional line - a "not observed here" note, a warning, a
  per-panel n - and some do not. Compute a padding, a height or an offset from whether THAT panel
  has it and sibling panels drift apart: two titles of the same role, side by side, land a full
  line out of register. Take the value over the whole ROW instead - the maximum any panel needs -
  and give it to every panel, or reserve the optional line unconditionally and draw it empty.
  The reason this survives review is that it is CONDITIONAL: whenever every panel happens to carry
  the optional content, the figure is correct, so it looks fine on the example the author had open.
  **ONE INSTANCE.** `pad=9 if absent else 3` on a panel title. Of four figures from one function,
  two were perfectly aligned and two had their titles 17 px apart - a full line - with the shorter
  panel's title sitting level with its neighbour's SUBTITLE. The two correct ones were correct by
  luck: both their panels happened to have the note. Replacing it with a row-wide `title_pad`
  computed once took all four to a measured 0 px offset. Any per-panel figure has this available
  to it - a trajectory per lineage, a QC histogram per sample, a domain map per section.
  **CHECK:** list every layout constant your panel loop computes from per-panel content. For each,
  would two panels in the same row get different values? Render a case where ONE panel has the
  optional content and the others do not - do the shared elements still line up?

- **C24** Is every continuous ramp monotonic in lightness, so the encoding survives being printed
  in grey and survives a colour-vision deficiency? Convert the rendered panel to greyscale and
  look: can you still order two marks?
- **C25** If a caption asks the reader to count, can they? Render at the shipped size and count
  the marks yourself in the densest region.
- **C26** Across every panel of a multi-panel figure, does each axis a reader needs appear on the
  panel they are reading, or only once for the set?

**And one that crosses figures.** In the same set, four figures used *the same thirteen colours
assigned to different entities* — the hue that meant one cell type in three figures meant a
different one in the fourth, with nothing on either figure warning of it. A palette is a claim
about identity, and identity has to hold across the set, not within one panel.

- **C27** Does every categorical palette in the set map the same colour to the same entity in
  every figure? Put the legends side by side and check. If two figures cannot share a palette,
  say so on both.

## Step 6 — ABSENCE IS NOT ZERO

This appeared **five times in one session, in five figures, by five agents who never spoke to each
other**, each in a different costume:

- a population absent from an entire arm drawn as a dot at the origin — reads as *measured, and
  silent*, not *never seen*;
- a category absent from an arm entering a difference as 0, and therefore ranking as the largest
  change on the page;
- a row-scaled heatmap giving a category seen in 2 of 10 samples the same full-intensity tile as
  one seen in all 10;
- the upstream tool assigning `p = 0` by a fallback branch wherever one arm is empty, so the
  on/off cases — the ones a reader most wants — are never tested and score maximally significant;
- invisible `1e-10` self-links inserted for nodes with no surviving link, to satisfy a drawing
  library, force-enabling a rescale that made arc length encode nothing.

Its sixth costume is **occlusion**: at 100k marks the last-drawn arm covers the first, and draw
order, which encodes nothing, decides what a reader sees. *Drawn but invisible* is
indistinguishable from *absent*.

**How to find your own costume**, because the five above are the ones one session happened to draw
and yours will not look like them. Take 1a's *degenerate values* column and ask, for each sentinel,
which legitimately measured value it collides with: zero, the origin, the first category, the
minimum of a scale, the start of an ordering, an even split across k outcomes. **A tool whose
output is constrained — probabilities summing to one, shares summing to 100%, a rescale to [0, 1] —
has no value left with which to say *unknown*, so it says something else and the something else is
always a state a reader can believe.**
*One instance, from this repository:* `pseudotime` records that "fate probabilities sum to one by
construction, so a cell with no clear fate is reported as evenly split rather than as unknown". An
even split is a real, meaningful, drawable state; it is also what the tool returns when it knows
nothing, and the two are the same number.

The fix is one shape every time: **draw absence distinctly** (hollow, hatched, a labelled gutter,
"not drawn"), **name what is absent in words on the figure**, and never let absence share an
encoding with a measured value — a zero where zero is the collision, and whatever else your 1a
sentinels collide with where it is not.

- **C13** Fixture: category X absent from an arm, category Y present at exactly 0. Render. Do the
  marks differ in at least one of {RGBA, hatch, position, glyph}? Does the text layer name X? If
  the marks are pixel-identical anywhere, fail. **Run the same fixture once per sentinel in 1a** —
  an entity carrying the *not assigned* value against one measured at the value that sentinel
  collides with — and answer the same question.
- **C14** For the top-k of any ranked difference, print n per arm. Is the count of top-k items
  with zero observations in an arm, outside a separately-labelled on/off gutter, 0?
- **C15** For each row- or column-scaled tile, is support printed? Take the two most
  similar-looking rows: do their true totals differ by less than the tolerance you declared?
- **C16** Enumerate, **by reading the upstream source**, every branch assigning a statistic without
  running the test — empty-input guards, exception handlers, hard-coded returns. One fixture each.
  Is the count of unflagged fallback values in every shipped table 0? None of them sorted into a
  "most significant" list?
- **C17** Does the record count and identity set handed to the renderer equal the source table's?
  Where a library forces padding, is the channel it compromises disabled, or declared
  non-quantitative in the figure's own text?
- **C18 (occlusion)** At real n, is the drawing density-aware — binned, hexbinned, contoured, or
  split into per-arm small multiples — and is the number of marks drawn printed on the panel? Swap
  the categorical draw order and re-render: does any claim in the caption change?
- **C19 (the ragged denominator)** An aggregate over units divides by the number of units, and
  an entity observable in only some of them gets the same divisor as one observable in all. The
  entities this understates are exactly the ones a floor already removed, so the two defects
  compound silently and in the same direction. For every aggregate you draw across units, is the
  divisor the number of units in which the entity could be observed, or the number of units? If
  you keep the whole-cohort divisor deliberately, is the per-entity denominator drawn or printed?
  *One instance.* A cohort mean divided by ten everywhere. An entity scorable in four units of ten
  was drawn at **40% of its scored mean, a factor of 2.50**, and nothing on the panel said so -
  while the same entity's absences were already aligned with a design factor.
- **C20 (marks outside the axes)** A point drawn beyond the axis limit is clipped, and clipping is
  silent. Render, then count the marks inside the axes and compare that to the number of records
  handed to the renderer - the same identity check as C17, applied to geometry rather than to
  padding. Are they equal? *One instance:* an axis limit taken from the largest MEAN while
  per-unit points were drawn over it clipped **20 of 368 points (5.4%)**, including every one of
  a panel's nine - so that panel showed two summary bars and not a single unit, with nothing
  saying so. Prefer the full domain of a bounded quantity over a data-derived limit.
- **D21 (per-unit thresholds)** A method run once per unit applies its own floors once per unit,
  so an entity near a floor is exposed to it as many times as there are units — and pooling would
  have exposed it once. That makes the floor a REMOVAL whose incidence must be computed per level
  of each design factor, never per unit. For every entity absent from a unit's result, can you say
  whether it was absent because it fell below one of the method's own floors in that unit? And can
  you state each floor's removal rate per level of every design factor? If the answer exists only
  per unit, you have not checked: folding N per-unit reports into a range is exactly the operation
  that destroys the alignment.
  *One instance.* A wrapped tool dropped a group's edges when that group had fewer than ten cells
  in the object being scored. The plugin ran once per unit, correctly reported the floor on each
  unit's own page, and the host folded ten such reports into "1-3 groups per unit". Crossed against
  the design instead: across 13 groups and 10 units, **not one group was absent from a unit while
  having 10 or more cells in it — zero exceptions**, and the three smallest groups were removed
  from 100% of one level of a factor and 0% of the other. Every absence was a threshold crossing on
  a small group, and three figures had already drawn those absences as a finding about the design.
  A floor converts a QUANTITATIVE difference in abundance into a BINARY presence, and the result
  cannot distinguish the two afterwards.
- **D22** For every declared filtering step, does a fixture exist that makes it fire and name the
  dropped item? *One instance:* a documented neighbour-mask step whose mask was never applied, so
  the dropped list was structurally always empty and the page printed "none dropped" — believed
  most strongly where it was least true.

The shipped plugins do this well. `de` separates *not tested* from *tested and null*, and its own
record is exact about the distinction: a NaN adjusted p-value has three causes, and *"the first two
mean the gene was NOT TESTED. Counting `padj < alpha` silently files all three under 'not
significant', which is the one reading that is wrong for two of them"* — the third, independent
filtering, **was** tested and had its adjusted p-value withheld, and the panel colours it as
tested. Its never-tested rows sort first so a row cap can never drop them (`de.py:1104`).

## Step 7 — A PANEL SCALED TO ITS OWN DATA HIDES ITS OWN FINDING

Found in six of seven plugins before the rebuild, and again during it. The upstream comparison
example passed the union of row names to two heatmap calls, each normalising to its own maximum,
with nothing on the published figure saying so; measured on real data, rows that look identical
differ by up to **1.9×** in true total.

**Make shared scaling the default of every multi-panel function, and independent scaling an
explicit argument that also draws its own disclosure — the code raises rather than drawing
undisclosed independent scales.** API design beats testing here.

- **D18** Call the function with defaults on two panels with known different maxima: identical
  limits, one colourbar? Does requesting independent scaling without a disclosure string raise? On
  real data, pick the row that looks equal across panels — is the ratio of its true totals below
  the tolerance you declared?
- **D19** Evaluate any monotone transform driving a channel over `[min, max]` of the real data:
  finite and strictly monotone everywhere, no value from a substitution branch? Correlate drawn
  lengths against true values — Spearman must be 1.0 **and** Pearson must clear the bound you
  declared; if only Spearman holds, the channel encodes rank and must be **labelled** rank. *One
  instance:* a bar track computed as `-1/log(rowSum)`, undefined at a total of 1, with a synthetic
  ramp substituted between 1.1× and 1.5× the largest real bar.
- **D20** Map the real values through your size function: how many fall below the smallest
  labelled legend break? Over 10% and the channel fails — re-map (log, quantile) or drop it. *One
  instance:* 56 of 68 items below the smallest break, across four orders of magnitude.

Precedent in this repo, both directions. `decoupler._fig_map`: *"ONE SCALE ACROSS THE GRID, AND ONE
COLOURBAR ... each panel still prints its OWN 98th percentile so the magnitude it lost to the
shared scale is on the panel rather than gone."* Unfixed but disclosed: `scenic
F5_activity_on_layout` runs each panel from its own minimum to its own 99th percentile, so a
regulon varying from 0.0100 to 0.0104 gets the full viridis range across that span; `velocity
F2_stream` normalises line width to the panel's own maximum speed and its caption never says so,
while its sibling `F3_grid` discloses the analogous normalisation.

## Step 8 — What travels ON the figure

Seven fields, never in a methods paragraph. A field that does not apply says so as an explicit
count — **`"0 of 68 dropped"`, never blank.**

1. **coverage drawn**, as a fraction of total mass, with the denominator's source file
2. **what is dropped, by name** — named, not counted
3. **unit of observation, and n per group**
4. **the scale statement**, wherever a panel is normalised
5. **the direction of a difference**, named in at least two different encodings
6. **known technical confounds**, with magnitude and the reason they bias the statistic
7. **departures from the upstream encoding**, each with its reason and the version departed from.
   When there is no upstream encoding, the field is not blank and not inapplicable: it reads
   `no upstream encoding; every channel is ours`, which is the stronger claim, because it says the
   choices under C23 were made here and are answerable here

**Budget them, because the caption cap is 45 visible words and the host spends about 8 of them.**
`_panel` prints `Figure N.`, an optional unit code and `vector (PDF) · source data` around your
text, and `_split_caption` cuts your text at `CAPTION_LEAD_WORDS = 32`. Seven fields do not fit in
32 words, so allocate them: **on the panel** — (3) unit and n, (4) the scale statement, and (1)'s
fraction where it is axis text; **in the visible 32-word lead** — (5) the direction, (1)'s coverage
with its denominator, and the literal arm vocabulary the `arms` criterion looks for; **in the
caption remainder, behind `<details>`** — (2), (6) and (7). The remainder is charged to `hidden`
(cap 2500 for the whole page: at nine panels that is ~250 words each, with the page's own
disclosures still to pay for), never to `captions`. A field that will not fit as prose becomes a
number on the panel, never a blank.

**Field 6 applies to panels whose `shows` is `result` or `comparison`.** Name the confound you
**checked** and its magnitude — *"6.6× library-depth span, inflates the statistic because …"*.
`none known` is not a permitted value: if you checked none, the field reads `not checked`.

**CHECK (F27/D21):** every applicable field present and non-empty on every panel, and every
inapplicable one carrying an explicit count or `not checked`? Diff your mark spec against the Step
1 catalogue — is the count of differences not listed under (7) zero? **With no upstream plot call
to diff against, the diff is against 1a**: is every channel drawn from a field the catalogue names,
and does each obey that field's *units and scale* and *relative or absolute* rows — nothing
relative on an axis shared across arms, nothing ranked drawn as a length, nothing whose value
depends on a parameter drawn without that parameter on the panel? *One instance of (1) and (6):*
`"31 of 79 ordered pairs = 71% of total strength"`, and a 6.6× library-depth span stated with the
reason it inflates the statistic. *Of (7):* area- rather than diameter-proportional dots, because
the upstream linear size makes area go as the square of the count and contradicts its own legend.

**E23 — the unit of observation is the claim.** Name what one row of the table handed to the test
is, and assert `n_rows_per_group == n_independent_units_per_group`. If n_rows exceeds n_units — a
product, a square, a per-cell expansion — re-run the contrast at the unit level and **report the
number of conclusions that change**. *One instance:* the upstream significance test treats N×N
population pairs as replicates and pools the animals away first; re-run with the animal as the
unit, the verdict changed on **40 of 68** pathways and every top offender had signal in 1 of 10
animals. What went on the figure: the pair-level test is not underpowered, it is measuring the
wrong thing, and its apparent power is manufactured by the pooling step.

**E24.** When the correct test is underpowered, print the attainable floor and draw a
**description**; never substitute the better-powered wrong test. **CHECK:** does the p-floor appear
in the figure's text, and if reported p-values sit at it, is the panel labelled descriptive and
carrying no significance claim? *One instance:* n = 5 vs 5 cannot reach below p = 0.008 — stated
rather than implied.

**A null result is a result, and it has a shape.** When the honest panel is flat, draw the flatness
at the scale a real effect would have occupied: the effect size with its interval, an axis spanning
the range that *would* have mattered rather than the range observed, and **the smallest effect this
design could have detected**, printed on the panel — only that last number lets a reader separate
*no effect* from *no power*. Every way of making a flat panel interesting is a defect already named
here: rescaling to the observed range is Step 7, cropping to the responders is a coverage failure
under (1), swapping magnitude for rank is D19, dropping the null rows is Step 6.
**CHECK:** is the detectable floor on the panel, and is the axis range justified by something other
than the data drawn on it?

**Grounds for NOT drawing a panel**, decided before you build it and recorded with which ground
applies: (a) the quantity is not interpretable in this assay, and drawing it well does not rescue
it; (b) the channel separates nothing — D20 with no re-map that fixes it; (c) the only available
test is the wrong one (E23/E24) — draw a description, or nothing; (d) the upstream routine is
defective on this data, so reproducing its picture faithfully would ship fabricated values (A6's
60 of 68) — take the measurement back to the user under Step 2; (e) the panel duplicates another
panel's claim. Not drawing is `ctx.refuse(what, why)` for the plugin, or `required: False` with a
`when_absent` naming the ground, for one panel. **Silence is neither**: `figure_drift` reports it
and the page carries a `div.bad` charged to `prose`.

**Some results are tables, and the figure is a summary of one.** When the deliverable is a ranked
list, ship the table as the result and let the panel index it — then the panel owes (1), (2) and a
link to the full table via `emit_figure(source=...)`. **No number may appear only in the figure**,
and a figure that is a picture of a table with no rows removed and no ordering added is a table
drawn badly.

**F26 — a structural count with no N is not a count.** Every count in a caption or report comes
from a script looping over **all** inputs and printing `(value, N, per_input_min, per_input_max)`.
*One instance:* "9 populations, 49 pathways" propagated into four task briefs from one sample of
ten; over all ten it was 13 and 68, per-sample ranges 8–13 and 27–52. **In a fan-out this rule is
about the brief, not the figure**: a structural fact that will appear in more than one brief —
population count, arm sizes, the unit of observation — is measured over all inputs *before* the
first brief is written and travels as `(value, N, min, max)`, because a per-agent check cannot
catch a fact that was wrong when it was handed out. The converse also holds: a defect five
independent agents each produced is a property of the data shape, not of an agent, so put Step 6 in
every brief and expect to find it in every panel.

**F27 — a bound the figure states, its own shipped numbers must satisfy.** A caption that prints
a floor, a ceiling, a resolution or an attainable minimum has made an assertion the panel's own
data can falsify. Check it mechanically: for every stated bound, scan the figure's source table
for a value on the wrong side of it.

*Two instances, both in one set, both shipped.* A panel printed *"6 vs 4 units cannot reach below
p = 0.0095"* while all ten of its highlighted hits sat at **p = 0.004762**; at the printed floor,
multiple-testing correction over its own 161 tests gives q = 0.153 and **nothing on the panel
crosses its own significance threshold at all** — the figure disproves its own headline in its own
footnote. A sibling asserted a floor of 0.0079 and its table attained **0.0075**. In both cases the
bound was the exact rank-test minimum and the number came from a normal approximation, so whatever
test ran was not the test named.

This is the most self-inflicted defect in this document, and the most quotable: **a figure that
states a bound and then violates it has done the reviewer's work for them, and lost.**

- **C28** For every bound printed on the figure - an attainable minimum, a resolution, a detection
  floor, a range - is there a value in the figure's own source table on the wrong side of it? One
  pass over the table per stated bound. If the answer is yes, either the bound is wrong or the
  method is not the one named; find out which before shipping, because a reader who checks will.

## Step 9 — Render the page and run the standard

```bash
scprofile validate <name>                                    # declaration: ERRORs stop the builder
python tests/make_fixture.py $W/fixture.h5ad                 # the iteration loop
scprofile run --h5ad $W/fixture.h5ad --out $W/results \
    --kernel <name> --design tests/smoke/design.csv --cores 4
scprofile standard --out $W/results                          # the ten criteria, on the HTML written
```

`--h5ad` and `--out` are required. **Pass `--design`**: without a design table the host *exempts*
`arms` outright (`report.py:893`), so a page that would fail it passes. A plugin not yet in
`kernels/` is discovered through `SCPROFILE_KERNELS=<dir>`; `tests/smoke/run_smoke.sh` chains the
whole sequence. The full-scale run on real data is the **last** round, not every round — it is what
`count`, `identifiers` and `repeats` need real labels for.

`standard.check_page` measures the rendered HTML and the CSVs it links. **It never opens a PNG** —
only its filename. The eight a figure can fail (the last row is three of them, sharing a
mechanism):

| criterion | rule | how a figure fails it |
|---|---|---|
| **count** | `<figure>` elements ≤ **12** | your panels + undeclared panels + host blocks. The declaration budget does not bound this |
| **repeats** | no PNG **basename** twice — the directory is stripped | ten units' `umap.png` at ten paths are ten identical ids. This is what the appendix exists to remove |
| **captions** | each visible figcaption ≤ **45** words (`<details>` charged to `hidden`) | `_panel` splits at `CAPTION_LEAD_WORDS = 32` and adds `"Figure N."`, an optional unit code and `vector (PDF) · source data` — about 8 words, so headroom is roughly 5 |
| **arms** | one **visible caption lead** must match the arm vocabulary | say it literally: *by arm*, *across the design*, *per arm*, *between arms*, *arm(s) of the design*, *split by design*, *by design level*, *per design level*, *grouped by design* — in the visible 32-word lead. A page describing its design comparison in any other words fails even when the figure genuinely compares arms |
| **identifiers** | accessions matched over captions **and** over every `href="../*.csv"`: header line and first column of the first `SOURCE_ROWS = 200` rows. Passes if absent, or if the page text **anywhere, disclosures included**, matches `unmapped\|no gene symbol\|accession` | attaching a `source` puts its **labels** under this criterion. Accessions are never dropped; the page must say how many labels are unmapped. Put it in the visible text anyway — the criterion is looser than the reader is |
| **prose / caveats / hidden** | **900** visible non-caption words / **800** inside `div.warn` / **2500** inside `<details>` | each `question` lead is an `<h3>` and is prose; a `required: True` panel not drawn renders `div.bad` and is charged to **prose**, an optional one's `when_absent` renders `div.warn` and is charged to **caveats**. Folding into `<details>` is accounting, not escape |

`overview` and `contradiction` are host-supplied and a figure cannot fail them. `contradiction` is
the only criterion not measurable from the page — every string in the payload's `contradictions`
must appear in the **visible** page, disclosures stripped; `ctx.contradiction(claim)` records into
both `contradictions` and `caveats`, and `recorded=None` reports `n/a`, never `ok`.

**Exemptions.** Declared in the page's own HTML as `data-standard-exempt="<criterion>"`, the
element's own text up to the next `<` being the reason; an exemption with no reason is refused.
**A plugin cannot declare one** — every caption is escaped on the way to the page. Today exactly
one exists: the host exempts `arms` when the payload carries no design table at all — attached to
the design being absent, not to `by_arm` being empty, because an earlier version exempted runs
whose design was perfect.

**The appendix** (`<name>_by_sample.html`) is skipped from the standard entirely — no figure cap,
no caption cap — but only when all three hold: the filename ends `_by_sample`, the parent plugin
page exists, and **the parent page's HTML contains the appendix filename**. Fail any one and it is
judged as a page, where per-unit panels fail `repeats` immediately. Moving figures out of sight
requires leaving a door to them in plain view; nothing is deleted.

**Drift, after the run.** `feedback.figure_drift` compares the declaration against the payload:
declared-required-not-emitted tells you to emit it or set `required: False` with a `when_absent`;
emitted-not-declared tells you to declare it. Only `refused` suppresses it. `metric_drift` is the
twin for `report.unit_metrics` against `ctx.metric(name, value)`.

## Archetypes worth copying, from the 51 shipped figures

Every plugin opens with **3–5** diagnostics before its first result. Read the entity names as
placeholders: "population" below is whatever your 1a *what one element is* column groups by, and
every one of these archetypes was drawn in matplotlib from a returned table rather than reproduced
from an upstream plot.

| archetype | plugins | the thing that makes it work |
|---|---|---|
| per-population power strip | 7 | count on a log axis beside what that count bought, same axis and sort order, exclusion threshold drawn, populations below it in a second colour, Spearman ρ of size against result-count |
| attrition funnel | 5 | stages drawn against the full reference set in grey so the grey *is* the loss; count and % on each bar; the delta in the wedge between bars; the source table naming which step lost each item |
| manifold panel | 3 | **`required: False`**, never computes its own layout, and every `when_absent` refuses the "first two columns of a wider representation" substitute in the same words. `velocity`'s two field panels are the deliberate exception — `required: True`, and they compute a UMAP when the object has none (`velocity.py:1359`) |
| model-fit diagnostic | 6 | the check made on the **derived quantity the answer is read off**, not a generic convergence statistic |
| threshold-margin panel | 4 | the quantity the call was made on, threshold drawn, numbered and named on the panel; filled = called, hollow = measured-and-not-called |
| population × population matrix | 4 | same order on both axes, diagonal outlined and called out, silent pairs in flat grey **off** the colour scale rather than at its bottom |
| technical-confound check | 4 | bin by a library property, plot the call against it, print the rank correlation **on the figure**, state that any slope means part of the result is the library |
| redundancy check | 3 | are two high-scoring things two findings, or one measurement twice |

Two things to know before copying. **`shows` is the ordering key and the figure number is not** —
`velocity` declares F1, F4, F9, F5, F8, F2, F3, F6, F7 and says in-line why: the ids were
retrofitted onto panels it already drew. And **`cellchat` and `liana` never draw a single mark per
cell or per replicate unit**, while the quantity deciding both results is per-cell sparsity:
`cellchat`'s own `cannot_show` states it and nothing on either page shows it. `abundance` is the
honest form of the same shape — one point per **sample**, n visible, the comment over its report
block saying outright that *"a composition is a table of shares per sample, and the only honest
picture of one is the samples themselves."*

## What is mechanised, and what is you

| enforced by the tool | where |
|---|---|
| declaration keys, `shows` vocabulary, `source` non-empty, `matplotlib` declared when any package is | `declare._check_report`, via `scprofile validate` |
| the cohort figure budget | `declare._check_report`, importing `MAX_FIGURES` and `BY_ARM_PANEL_CAP` from the modules that own them — **skipped entirely for `per_unit` plugins** |
| column width, DPI, Type-42 fonts, PNG + PDF + CSV together | `ctx.plot()` and `ctx.emit_figure` → `figure.fit_column` — **best-effort; both call sites swallow every exception** |
| declared-but-not-drawn, drawn-but-not-declared | `feedback.figure_drift`, after every run |
| the ten page criteria, on the HTML actually written | `standard.check_page` / `check_report`, via `scprofile standard --out` |

Everything else here is you. Not mechanised anywhere: **the return contract catalogue (A0)** —
`declare.check` asserts only that `upstream.docs` is a non-empty string (`declare.py:466`), and
nothing in the host ever looks at what the wrapped tool returns, so a plugin that catalogued no
field at all validates clean; the rendered pixels (Step 5, all eight rows,
and `check_page` never opens one); colour, contrast and colour-vision safety; determinism; absence
as an *encoding* — a host-side gate that refuses the removal of observations does not reach an
encoding, or a zero in arithmetic; self-scaling (Step 7); the unit of observation; the seven
caption fields; and the fact that the declaration's `source` string and `emit_figure(source=...)`
are unrelated, only the second becoming the page link and only the second being scanned by
`identifiers`. Two that no check can reach at all: deciding *which* quantities are consequential
enough to reimplement, and knowing a derived element is combinatorial when its row count happens
to match.

## Troubleshooting

| symptom | cause |
|---|---|
| `count` fails at 12 or 13 with 9 declared | emitted-but-undeclared panels, or a per-unit merge putting unit figures on the cohort page. Check the "Drawn, and not declared" section |
| `repeats` fails | two panels share a PNG **basename** after the directory is stripped — a per-unit plugin whose figures did not route to the appendix, or a name colliding with `<name>_across_design` |
| `arms` fails and the figure clearly compares arms | the caption lacks the literal `ARM_HINT` vocabulary in its visible 32-word lead — or the run had no `--design`, in which case it did not fail, it was exempted |
| `identifiers` fails and no caption has an accession | the linked source CSV's header or first column does |
| a caption ends in `...` | past `CAPTION_LEAD_WORDS = 32`; the remainder is behind `<details>` and charged to `hidden` |
| PDF opens with uneditable text | `ctx.plot()` was not called, so `pdf.fonttype = 42` was never applied |
| panel wider than the column it declared | `fit_column` raised and was swallowed, a style module re-applied an rcParam after `ctx.plot()`, or the panel is mostly tick label and hit `MIN_PAGE_SHARE = 0.7`. Measure the written file |
| two labels the same colour | more than `PALETTE_LIMIT = 16` categories; `palette` cycles without raising. Call `palette_collisions` — and note it separates identical hues only |
| a required panel missing and the page silent | never emitted and never refused. `figure_drift` reports it after the run; `partial` does not excuse it, only `refused` does |
| the panel you drew is not the panel on the page | you emitted `<pluginname>_across_design`; the host overwrites that path at report time |
