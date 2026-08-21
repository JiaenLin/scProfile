# Reference data: where every byte comes from

A **reference** here is any data a plugin consults that did not come from your object. A motif
ranking, a ligand–receptor database, a regulatory prior, a gene set. They decide answers as much
as the algorithm does — two runs of the same method against two versions of the same database
disagree, and neither one is wrong.

This document is the register: what each plugin uses, who published it, under what terms, how it
is pinned, and whether anything checks it. It exists because **only one plugin's references are
visible to the tool**, and the rest are no less real for being invisible.

---

## The three tiers, and why the difference matters

| tier | pinned by | fetched by | verified by | appears in the report |
|---|---|---|---|---|
| **declared** | `references.yml`, with a `sha256` and a `size` | `scprofile fetch` | `validate --deep`, and again by `resolve()` before every run | yes, by name and digest |
| **bundled** | the package version in `lock.yml` | the environment build | nothing | no |
| **runtime** | nothing | the plugin, over the network, while it runs | nothing | no |

**Declared** is the only tier where a result can be traced to the exact bytes that produced it.

**Bundled** is genuinely pinned — a package version fixes the database inside it — but the pin is
*incidental*: it was chosen for the software, and the database came along. Nothing records which
version of the database produced a given result, and upgrading the package to fix a bug silently
changes the answers.

**Runtime** is the one to be uneasy about. The data is not pinned, the source can change under
you, and the fetch needs outbound network from a compute node that may not have any.

---

## Declared references

### `scenic` — cisTarget motif rankings

**Source:** `https://resources.aertslab.org/cistarget/` — the Aerts lab's own distribution, the
authors of SCENIC.
**Terms:** distributed for research use. The underlying motif collection (`v10nr_clust`) is
derived from JASPAR, HOCOMOCO, SwissRegulon and others; see the vendor's site for the full
provenance of the collection itself.
**Cite:** Aibar *et al.*, *Nature Methods* 2017 (SCENIC); Van de Sande *et al.*, *Nature
Protocols* 2020 (pySCENIC).

Full declaration, with URLs, digests and sizes: [`kernels/scenic/references.yml`](../kernels/scenic/references.yml).

| entry | organism | what it is | why the run needs it |
|---|---|---|---|
| `mm10_rankings_10kb` / `hg38_rankings_10kb` | mouse / human | genes × motifs ranking, 10 kb up and down of the full transcript | the `ctx` step ranks each co-expression module against these; without them nothing is pruned |
| `mm10_motif2tf` / `hg38_motif2tf` | mouse / human | motif → gene mapping for `v10nr_clust` | turns an enriched motif back into the TF that binds it |
| `mm_tfs` / `hs_tfs` | mouse / human | the TF list | GRNBoost2 restricts its regulators to these |

**Why these are declared and not bundled:** pySCENIC's second and third steps are a *lookup*, not
inference. Without the rankings, `ctx` prunes nothing, every co-expression module survives, and
the regulons are GRNBoost2's raw output wearing a regulon's name — **a full result file, and
wrong**. That failure has no symptom, which is why these are checksummed rather than merely
present.

**Digest provenance.** The vendor publishes no checksums. Every `sha256` in `references.yml` was
computed by `fetch` from a completed download, printed, and pasted in **by hand on a workstation**
— the machine that downloads is not the machine that authors. Every `size` was arrived at twice
and independently: the vendor's `Content-Length` from a HEAD request, and the bytes on disk
afterwards.

> An entry with no `sha256` is an honest gap, and `validate` will keep refusing the plugin until
> one is declared. That is the correct state. A digest invented for a file this project has never
> downloaded would be worse than none, because everything downstream would then verify against it
> and pass.

---

## Bundled references — real, pinned, and invisible to this tool

### `cellchat` — CellChatDB

`CellChatDB.human` and `CellChatDB.mouse` are R data objects **inside the CellChat package**.
They are pinned by the git commit in [`kernels/cellchat/lock.yml`](../kernels/cellchat/lock.yml)
(`jinworks/CellChat@75253cd…`, DESCRIPTION version 2.2.0.9001), which was chosen for the
*software* — the database is pinned as a side effect.

**Source:** <https://github.com/jinworks/CellChat> · **Cite:** Jin *et al.*, *Nature
Communications* 2021.

This plugin's own `cannot_show` already warns that *"its database is its own… disagreement is a
finding about the databases as much as about the cells"*. What is missing is the version: nothing
in a result records which CellChatDB produced it.

### `liana` — the consensus resources

`consensus` (human) and `mouseconsensus` ship inside the wheel, pinned by `liana==1.4.0` in
[`kernels/liana/lock.yml`](../kernels/liana/lock.yml). They are assembled from OmniPath.

**Source:** <https://github.com/saezlab/liana-py> · **Cite:** Dimitrov *et al.*, *Nature
Communications* 2022 (LIANA); Türei *et al.*, *Molecular Systems Biology* 2021 (OmniPath).

The plugin's selftest loads both offline and measures their symbol casing, because *"the default
resource is HUMAN, and a human resource on non-human symbols does not error; it returns a small
plausible table"* is in its `cannot_show`. Loading them offline is also what proves the plugin can
run in a batch job at all.

---

## Runtime references — not pinned by anything

### `decoupler` — CollecTRI and PROGENy

`decoupler` obtains its priors **over the network while it runs**, from OmniPath. Nothing pins
them, nothing checksums them, and the fetch needs outbound HTTPS from a compute node.

**Source:** <https://github.com/saezlab/decoupler-py> · **Cite:** Badia-i-Mompel *et al.*,
*Bioinformatics Advances* 2022 (decoupler); Müller-Dott *et al.*, *Nucleic Acids Research* 2023
(CollecTRI); Schubert *et al.*, *Nature Communications* 2018 (PROGENy).

**This is an open design problem, not a documented decision.** The plugin is `status: planned`, so
nothing runs today — but before it does, its priors should move to the *declared* tier: pinned to
a release, fetched by `scprofile fetch`, checksummed, and named in the report. A prior downloaded
at run time makes a result unreproducible in the one way nobody checks, because the run succeeds.

---

## Plugins that use no reference data

`velocity`, `pseudotime`, `abundance` and `de` consult nothing external — every number comes from
your object. `cellcycle` carries the Tirosh *et al.* (*Science*, 2016) cell-cycle gene sets **as a
literal in its own source**, which is a reference of a fourth kind: versioned by this repository's
git history, small enough to read, and printed in the plugin's caveats along with how many of its
genes matched your object.

---

## Adding a reference, or an organism

1. Add an entry to that plugin's `references.yml`: a unique name, `organism`, `url`, and a `note`
   saying what it is. Leave `sha256` and `size` out if you do not have them.
2. Run `scprofile fetch <plugin> --to <dir> --organism <name>`. It reports the total and checks
   the free space before downloading anything, then prints the `sha256` and `size` of every file
   that declared none.
3. Paste those lines into `references.yml` **on a workstation**, and commit. Never let the
   downloading machine edit the file — a reference declaration edited by whichever host happened
   to run a fetch is a declaration with no single origin.
4. `scprofile validate <plugin> --references <dir> --organism <name> --deep` must be clean.

**A plugin that declares references for some organisms and not others refuses the rest.**
`reference_organisms()` is the set it can serve; anything outside it is a refusal naming what it
does have, because an organism with no declared reference data used to look exactly like a plugin
that needed none — and the plugin ran with nothing.
