"""Reading the object, and working out what it is without being told.

THE POINT OF THIS MODULE IS THAT THE TOOL IS EASY TO RUN. A user should be able to point it at an
h5ad and get a correct answer, not spend twenty minutes discovering that their label column is
called something this tool did not guess.

So everything is DETECTED, and every detection is PRINTED and RECORDED with the evidence for it.
Detection that happens silently is a guess the user cannot audit; detection that is reported is a
default they can override in one flag.

NOTHING HERE MAY ASSUME THIS PROJECT'S DATASET. No column name, no organism, no assay, no design
shape and no cell type is hardcoded. The upstream tools let the user name their own columns, so a
host that keys on `cell_type` works on exactly one cohort.
"""
from __future__ import annotations

import re
from . import manifest

#: Labels an annotator uses to say "no call". Not cell types, and never treated as populations.
#: These are the ones scAnno writes, and they are a DEFAULT, not a definition - `--sentinels`
#: replaces them outright, and `--sentinels ""` says this annotation has none. A tool that only
#: knows one annotator's sentinels treats another's as a cell population, which is the same
#: failure as not knowing about sentinels at all.
DEFAULT_SENTINELS = ("EXCLUDED", "UNRESOLVED")

#: Candidate names for each role, most specific first. A HINT for detection, never a requirement:
#: whatever is found is reported, and `--label-key` overrides it outright.
CANDIDATES = {
    "label": ["cell_type", "celltype", "cell_type_forced", "annotation", "labels",
              "scanno_path_scope", "scanno_cell_type", "leiden"],
    "compartment": ["cell_compartment", "compartment", "lineage", "scAnno_L1_scope", "L1"],
    "sample": ["sample", "sample_id", "library", "donor", "orig.ident", "batch"],
    "batch": ["batch", "sample", "library", "chemistry"],
    "counts_layer": ["counts", "raw", "raw_counts", "spliced"],
    # LOG-NORMALISED VALUES ARE NOT ALWAYS IN A LAYER CALLED `lognorm`. That is what this tool
    # family writes; Seurat's converters write `data`, Bioconductor's write `logcounts`, and a
    # great many objects carry them in X with no layer at all. The host hard-coded the string, so
    # every plugin declaring `layers: {lognorm}` - liana, cellchat, decoupler - reported an unmet
    # prerequisite on an object that had the values under another name.
    "lognorm_layer": ["lognorm", "logcounts", "log1p", "data", "normalized", "norm"],
    # OBSM, and detected like everything else rather than picked inline. This was chosen by a
    # `next((e for e in ('X_scanvi','X_umap','X_pca') if e in A.obsm), None)` buried in the run
    # loop - the only key in the whole tool selected silently, with no evidence line, and headed
    # by one particular integration tool's output name. A user whose object carries both an
    # `X_scanvi` and the embedding they actually meant got scanvi and was never told.
    # THIS IS THE REPRESENTATION TO COMPUTE ON, and the order is right for that: an integrated
    # space before an uncorrected one, because a neighbour graph built on the uncorrected space
    # has the batch in it. It is NOT the thing to draw on - see `pick_layout` below, and
    # CAPABILITIES["embedding"], which has always read "a cell embedding to compute neighbours
    # on". `X_umap` and `X_pca` remain at the end as the last resort for a graph.
    "embedding": ["X_scanvi", "X_scvi", "X_harmony", "X_integrated", "X_pca_harmony",
                  "X_umap", "X_pca"],
}

#: Which pool each role is looked for in. Anything not named here is an `obs` column.
#: This was `role == "counts_layer"` inline, so a second layer role searched obs and found
#: nothing - silently, because "not found" is a legitimate answer for an optional key.
_LAYER_ROLES = ("counts_layer", "lognorm_layer")
_OBSM_ROLES = ("embedding", "layout")

#: Genes present in essentially every mammalian dataset, used only to tell CASING apart.
#: Not a marker panel and not biology - purely a test of whether symbols are Xxxx or XXXX.
_CASING_PROBES = ("ACTB", "GAPDH", "MALAT1", "RPL13A", "PTPRC", "EEF1A1")


class Refuse(Exception):
    """Continuing would produce a number that looks right and is not."""


def detect_keys(obs_columns, layers=(), obsm=(), overrides=None):
    """Best guess for each role, with the evidence. Returns {role: (name|None, why)}.

    An override is recorded as such, so the report can distinguish "the user said so" from "the
    tool guessed" - those carry different weight when a result is questioned later.
    """
    over = {k: v for k, v in (overrides or {}).items() if v}
    cols = list(obs_columns)
    out = {}
    for role, cands in CANDIDATES.items():
        pool = (list(layers) if role in _LAYER_ROLES
                else list(obsm) if role in _OBSM_ROLES else cols)
        if role in over:
            name = over[role]
            if name not in pool:
                raise Refuse(
                    f"--{role.replace('_', '-')}-key {name!r} is not present. "
                    f"{'layers' if role == 'counts_layer' else 'obs'} offers: "
                    + ", ".join(map(repr, pool[:20]))
                    + (" ..." if len(pool) > 20 else ""))
            out[role] = (name, "given on the command line")
            continue
        hit = next((c for c in cands if c in pool), None)
        out[role] = (hit, f"detected: the first of {cands[:3]}... present" if hit
                     else "not found among the usual names")

    # LAYOUT IS RESOLVED BY RULE, NOT BY A CANDIDATE LIST, and therefore after the loop: it
    # depends on which representation was chosen, because the layout worth drawing on is the one
    # derived FROM that representation. A candidate list could not express that and would go on
    # naming product names in a fixed order, which is the shape of the defect it replaces.
    emb = (out.get("embedding") or (None, ""))[0]
    try:
        out["layout"] = pick_layout(obsm, embedding=emb, override=over.get("layout"))
    except Refuse:
        raise
    except Exception as exc:                                              # noqa: BLE001
        out["layout"] = (None, f"could not be resolved: {type(exc).__name__}: {exc}")
    return out


#: Algorithms whose output is a LAYOUT - two coordinates made to be looked at. Ordered by how
#: commonly they are the thing a reader has already seen. scvelo's own default is `umap` and its
#: documented preference is umap, tsne, pca; nothing here contradicts a tool's own default, it
#: only makes the choice visible.
LAYOUT_PREFERENCE = ["X_umap", "X_tsne", "X_draw_graph_fa", "X_fa2", "X_phate", "X_densmap",
                     "X_diffmap"]

#: How wide a thing has to be to be a layout. Exactly two: a figure has two axes.
LAYOUT_WIDTH = 2


def _widths(obsm):
    """`{name: n_columns}` from either a mapping or a bare sequence of names.

    A SEQUENCE MEANS THE WIDTHS ARE UNKNOWN, not that they are two. `detect_keys` was given a
    list of obsm KEYS and nothing else, so it could not tell a 30-dimensional latent from a
    2-dimensional layout - and it chose `X_scanvi` as the thing to draw on, on an object that
    also carried `X_umap_scanvi`. Every caller that can pass widths should.
    """
    if isinstance(obsm, dict):
        return {str(k): (int(v) if isinstance(v, int) else
                         int(v[1]) if isinstance(v, (tuple, list)) and len(v) > 1 else None)
                for k, v in obsm.items()}
    return {str(k): None for k in obsm}


def pick_layout(obsm, embedding=None, override=None):
    """The 2-D layout to DRAW on. Returns (name|None, why).

    A REPRESENTATION IS NOT A LAYOUT, and conflating them is what this function exists to stop.
    `embedding` is documented in CAPABILITIES as "a cell embedding to compute neighbours on" - a
    30- or 50-dimensional space where distances are meaningful and the axes are not. A layout is
    two coordinates produced to be looked at.

    The distinction is not pedantic for a variational latent. The dimensions of a scVI or scANVI
    latent are exchangeable and carry no variance ordering, unlike principal components: taking
    the first two gives two arbitrary coordinates of a roughly isotropic Gaussian, which draws as
    a featureless ball whatever structure the data has. Theis's own DRVI line of work exists
    because standard VAE latents are entangled, and disentangling them is a research problem
    rather than a property one can assume.

    The rule, in order, and it is a RULE rather than a list of product names:

      1. THE LAYOUT DERIVED FROM THE CHOSEN REPRESENTATION. `X_umap_<name>` beside `X_<name>` is
         a widespread convention for exactly this - a UMAP computed FROM that representation -
         and it is the only candidate guaranteed to describe the same manifold the neighbours
         were computed on.
      2. A named layout algorithm's output, at two columns.
      3. The only two-column key present, if there is exactly one. Unambiguous by arithmetic.
      4. Nothing. A plugin that needs to draw then refuses and names what to compute, which is a
         better answer than a picture of the wrong space.
    """
    w = _widths(obsm)
    two = [k for k, n in w.items() if n == LAYOUT_WIDTH]
    unknown = [k for k, n in w.items() if n is None]

    if override:
        if override not in w:
            raise Refuse(f"--layout {override!r} is not in obsm. Present: "
                         + ", ".join(sorted(w)[:20]) + (" ..." if len(w) > 20 else ""))
        n = w[override]
        if n is not None and n != LAYOUT_WIDTH:
            raise Refuse(f"--layout {override!r} has {n} columns. A layout is drawn on two axes; "
                         f"a wider one is a representation, and its first two columns are not a "
                         f"picture of it.")
        return override, "given on the command line"

    if embedding:
        stem = embedding[2:] if embedding.startswith("X_") else embedding
        derived = f"X_umap_{stem}"
        if derived in w and w[derived] in (LAYOUT_WIDTH, None):
            return derived, (f"the layout derived from the representation ({embedding}): a UMAP "
                             f"of that same space, so both describe one manifold")

    for cand in LAYOUT_PREFERENCE:
        if w.get(cand) == LAYOUT_WIDTH:
            return cand, f"first of {LAYOUT_PREFERENCE[:3]}... present, at two columns"

    if len(two) == 1:
        return two[0], "the only two-column entry in obsm"
    if two:
        return sorted(two)[0], (f"first of the {len(two)} two-column entries in obsm "
                                f"({', '.join(sorted(two)[:4])}) - name one with --layout")
    if unknown and not two:
        for cand in LAYOUT_PREFERENCE:
            if cand in w:
                return cand, (f"first of {LAYOUT_PREFERENCE[:3]}... present; its width was not "
                              f"supplied, so it is assumed to be a layout by its name")
    return None, ("no two-column entry in obsm. A layout has to be computed - for an integrated "
                  "representation that is `sc.pp.neighbors(adata, use_rep=<representation>)` "
                  "then `sc.tl.umap(adata)` - and drawing on the first two columns of a wider "
                  "space would be a picture of two arbitrary coordinates.")

def detect_organism(var_names, declared=None):
    """`mouse` / `human` / None, from gene-symbol CASING. Returns (organism, why).

    A heuristic and labelled as one. Human symbols are upper case (`ACTB`), mouse title case
    (`Actb`); an object indexed by Ensembl IDs matches neither and returns None rather than a
    coin-flip. `--organism` overrides and is recorded as declared.
    """
    if declared:
        return declared.lower(), "declared on the command line"
    names = [str(v) for v in var_names[:5000]]
    if not names:
        return None, "the object has no var_names"
    if sum(1 for n in names if re.match(r"^ENS[A-Z]*G\d+", n)) > len(names) * 0.5:
        return None, ("var_names look like Ensembl IDs, which carry no species casing. "
                      "Pass --organism, or re-index the object by symbol.")
    up = {n.upper() for n in names}
    probes = [p for p in _CASING_PROBES if p in up]
    if not probes:
        return None, "none of the casing probe genes are present; pass --organism"
    exact_upper = sum(1 for p in probes if p in names)
    exact_title = sum(1 for p in probes if p.capitalize() in names)
    if exact_upper > exact_title:
        return "human", f"{exact_upper}/{len(probes)} probe genes are UPPER CASE ({probes[:3]})"
    if exact_title > exact_upper:
        return "mouse", f"{exact_title}/{len(probes)} probe genes are Title Case ({probes[:3]})"
    return None, f"casing is ambiguous over {probes[:3]}; pass --organism"


def detect_assay(adata, declared=None):
    """`cell` / `nucleus` / None, and why. This changes the CAVEATS, never the code path.

    It matters more than it looks. On nuclei the unspliced fraction is high BY CONSTRUCTION, so a
    velocity model built for a cytoplasmic spliced pool is being applied to data that inverts its
    assumption; and mitochondrial percent measures cytoplasmic carry-over rather than
    mitochondrial transcription. A kernel that does not know which it has cannot caveat itself.
    """
    if declared:
        return declared.lower(), "declared on the command line"
    for key in ("scqc", "scanno", "scanno_embed", "scintegrate"):
        u = adata.uns.get(key)
        if isinstance(u, dict):
            for k, v in u.items():
                if "assay" in str(k).lower():
                    s = str(v).lower()
                    if "nuc" in s or s in ("sn", "snrna"):
                        return "nucleus", f"uns[{key!r}][{k!r}] = {v!r}"
                    if "cell" in s or s in ("sc", "scrna"):
                        return "cell", f"uns[{key!r}][{k!r}] = {v!r}"
    if "spliced" in adata.layers and "unspliced" in adata.layers:
        import numpy as np
        s, u = adata.layers["spliced"], adata.layers["unspliced"]
        ss = float(s[:2000].sum()) if s.shape[0] > 2000 else float(s.sum())
        uu = float(u[:2000].sum()) if u.shape[0] > 2000 else float(u.sum())
        if ss + uu > 0:
            frac = uu / (ss + uu)
            if frac > 0.5:
                return "nucleus", (f"unspliced is {100 * frac:.0f}% of counts, which is the "
                                   f"nuclear pattern (cells are typically 10-30%)")
            return "cell", f"unspliced is {100 * frac:.0f}% of counts"
    return None, ("could not be determined. Pass --assay cell|nucleus - it does not change what "
                  "is computed, but it changes what each kernel is allowed to claim.")


def sentinel_mask(labels, sentinels=DEFAULT_SENTINELS):
    """(is_real, {sentinel: count}). Sentinels stay in the object; they leave the STATISTICS."""
    import numpy as np
    lab = np.asarray([str(x) for x in labels])
    sent = tuple(s for s in (sentinels or ()) if s)
    found = {s: int((lab == s).sum()) for s in sent if (lab == s).any()}
    is_real = ~np.isin(lab, sent) if sent else np.ones(len(lab), dtype=bool)
    return is_real, found


#: A ROLE the host detects, mapped to the CAPABILITY a plugin injects. They are two vocabularies
#: on purpose - a role is about this object ("which layer holds log-normalised values here"), a
#: capability is about the plugin's need ("give me log-normalised values") - and everywhere they
#: differ is a place the host can resolve a role and then fail to satisfy the capability it
#: answers. Only two differ, and both did: `in.json` carried `counts_layer` and `lognorm_layer`
#: and nothing named `counts` or `lognorm`, so `ctx.counts()` returned None on an object with a
#: counts layer, `ctx.X` fell back to `.X` without saying so, and any plugin declaring
#: `inject.required: ["lognorm"]` was refused a capability the object plainly had.
ROLE_CAPABILITY = {"counts_layer": "counts", "lognorm_layer": "lognorm"}

#: EVERY ROLE THE HOST RESOLVES, which is not the same as every role with a candidate list.
#: `layout` is resolved by a rule that depends on the chosen representation, so it has no entry in
#: CANDIDATES - and anything iterating CANDIDATES to enumerate roles silently omits it. That is
#: how a capability can be declared, resolved, handed to plugins, and still be missing from the
#: one check that asserts every capability has a bridge.
ROLES = tuple(CANDIDATES) + ("layout",)


def capability_keys(detected):
    """The key map handed to a plugin: every detected role, plus its capability name.

    `detected` is either {role: (name, why)} as `detect_keys` returns it, or {role: name}.
    Roles whose name is empty are dropped - a key present and null reads as a key that was looked
    for and found, which is the opposite of what it means.

    Kept HERE rather than at each call site, because it WAS at each call site: two of the three
    aliased, and the third was the one that wrote `in.json`.
    """
    flat = {}
    for role, v in (detected or {}).items():
        name = v[0] if isinstance(v, (tuple, list)) else v
        if name:
            flat[role] = name
    for role, cap in ROLE_CAPABILITY.items():
        if flat.get(role):
            flat.setdefault(cap, flat[role])
    return flat


def read_constraint(adata):
    """The upstream constraint on use, if the object carries one. Absence is a FINDING.

    scIntegrate writes what its chosen embedding may and may not carry, computed from the design.
    The abundance kernel needs it: a factor nested in the batch key is not identifiable, and a
    differential-abundance test will return small confident p-values for it regardless.

    Returns (text, source). Source is "" when there is none, and the caller must say so rather
    than proceeding as though the design had been checked.
    """
    # ANY upstream block that declares one, not one named tool. This read
    # `uns['scintegrate']['constraint_on_use']` and nothing else, so the whole mechanism - the
    # thing that stops an unidentifiable factor being tested - was silent for every object not
    # produced by one particular toolchain. A SAFETY feature that fires only for its author's
    # pipeline is worse than none, because its absence reads exactly like "no constraint applies".
    #
    # The KEY is the contract, not the writer's name: an upstream tool declares
    # `constraint_on_use` and any host can read it. Sorted so two writers give a stable answer,
    # and both are reported rather than one silently winning.
    found = []
    for key in sorted(adata.uns):
        block = adata.uns[key]
        if isinstance(block, dict) and block.get("constraint_on_use"):
            found.append((str(block["constraint_on_use"]), f"uns[{key!r}]['constraint_on_use']"))
    top = adata.uns.get("constraint_on_use")
    if top:
        found.append((str(top), "uns['constraint_on_use']"))
    if not found:
        return "", ""
    if len(found) == 1:
        return found[0]
    # TWO CONSTRAINTS ARE BOTH BINDING. Picking one would silently drop a restriction somebody
    # wrote down deliberately.
    return ("\n\n".join(t for t, _ in found),
            " + ".join(src for _, src in found))


# THE PROHIBITION IS ONE SENTENCE, and it ends at the first sentence break or newline. Reading a
# whole paragraph instead reached past the prohibition into the REMEDY that follows it - "for
# that, use the uncorrected X_pca ... Differential expression on per-sample counts is unaffected"
# - and returned `sample` as a bound factor from a clause that exists to say what is still
# ALLOWED. A rule that reports the permission as a prohibition is worse than no rule: it is the
# kind of false positive that gets the whole check switched off.
_SENTENCE_END = re.compile(r"\.\s|\n")


def constraint_binds(constraint, factors):
    """Which of these design factors does the constraint FORBID a claim across?

    A constraint is prose written by an upstream tool, and the one thing in it that can be
    matched reliably is a factor name, because both sides name the same column of the same
    design table. So the rule is deliberately narrow: a factor is BOUND when it is named inside
    the prohibition - the text from a `must NOT` to the end of its paragraph - and by nothing
    else. The permission half is not parsed at all; a constraint exists for its prohibition.

    Matching is on word boundaries. Twice already a substring match has fired on prose - a
    plugin named `de` inside the word "declared" - and a factor called `age` sits inside
    "average", "damage" and "usage".

    Returns a sorted list; empty is the honest answer for a constraint about an axis this
    cohort does not vary, and it must not be read as "no constraint applies".
    """
    txt = str(constraint or "")
    if "must NOT" not in txt:
        return []
    windows = []
    for m in re.finditer(r"must NOT", txt):
        rest = txt[m.start():]
        end = _SENTENCE_END.search(rest)
        windows.append(rest[:end.start()] if end else rest)
    hay = " ".join(windows)
    return sorted({f for f in (factors or [])
                   if re.search(rf"\b{re.escape(str(f))}\b", hay)})


#: Above this many levels a factor is an identifier, not an arm, and a per-arm panel of it is a
#: per-sample panel wearing the wrong label.
ARM_LEVEL_CAP = 12
#: Below this many cells an arm's quantiles describe the handful of cells that landed in it.
ARM_MIN_CELLS = 20


def by_arm(adata, columns, design, sample_key, factors, *, cap=ARM_LEVEL_CAP):
    """Every per-cell column a plugin produced, summarised ACROSS THE DESIGN. Description only.

    THE DESIGN IS MISSING FROM EVERY PAGE THAT DOES NOT TEST IT. Measured on a 2x2 cohort: of
    nine plugins, the two that test the design reported across it and the other seven reported
    per population and per cell and never once split a result by the factor the study exists to
    ask about. Two of the seven DECLARED `design_aware` - "reports per arm without testing
    across the design" - and between them had fourteen panels, none of them about an arm. The
    first form of this defect was a flag nobody set; this is a flag nobody honoured, and only a
    check that looks at the OUTPUT rather than the declaration can tell them apart.

    So the host does it, once, for every plugin - a plugin gets its per-arm view by writing a
    per-cell column, which it already does, and writes no code for it. That also fixes it for a
    plugin written next year.

    NUMBERS ARE DESCRIBED, NEVER TESTED. Quantiles and counts, no p-value and no effect size:
    the moment this computed a test it would be doing inference the plugin declared, the design
    was audited for, and the upstream constraint may forbid outright. A categorical column is
    summarised as its per-arm composition, which is the same description of a different scale.

    Returns {column: {factor: {...}}}, empty for anything it cannot honestly summarise.
    """
    import numpy as np
    import pandas as pd

    if not (columns and design and sample_key) or sample_key not in adata.obs:
        return {}
    samp = adata.obs[sample_key].astype(str)

    # TWO FACTORS WITH THE SAME PARTITION ARE ONE SPLIT, AND THE PAGE SAYS SO. Drawing both
    # presents one division of the samples twice, and a reader with two panels showing the same
    # difference under two names has, on the page, two pieces of evidence. Measured on the
    # cohort this was found on: `age` and `chemistry` are aliased one-to-one over all ten
    # libraries, so every per-arm panel appeared once as biology and once as a reagent lot.
    #
    # The alias is NAMED rather than dropped silently - which of two aliased factors is the
    # cause is exactly what the data cannot say, and hiding one would imply the other was
    # chosen.
    partitions, keep, alias = {}, [], {}
    for fac in sorted(factors or []):
        # THE GROUPING OF SAMPLES, NOT ITS LABELS. Keying on (sample, level) pairs made two
        # factors that split the samples identically look different because one calls its arms
        # `young`/`aged` and the other `v3`/`v4` - which is precisely the pair this exists to
        # catch, since an aliased confounder almost never shares the vocabulary of the factor it
        # is aliased with.
        by_level = {}
        for k, r in design.items():
            by_level.setdefault(str(r.get(fac, "")), set()).add(k)
        key = frozenset(frozenset(v) for v in by_level.values())
        if key in partitions:
            alias.setdefault(partitions[key], []).append(fac)
        else:
            partitions[key] = fac
            keep.append(fac)
    factors = keep

    out = {}
    for col in sorted(set(columns)):
        if col not in adata.obs:
            continue
        v = adata.obs[col]
        numeric = pd.api.types.is_numeric_dtype(v) and not pd.api.types.is_bool_dtype(v)
        levels_of_col = None
        if not numeric:
            levels_of_col = sorted({str(x) for x in v.dropna().unique()})
            if len(levels_of_col) > cap:
                continue                       # an identifier, not a readout
        per_factor = {}
        for fac in sorted(factors or []):
            arm = samp.map({k: str(r.get(fac, "")) for k, r in design.items()})
            keep = arm.notna() & (arm.astype(str) != "")
            levels = sorted({str(x) for x in arm[keep].unique()})
            if not (2 <= len(levels) <= cap):
                continue
            rows = []
            for lv in levels:
                m = keep & (arm.astype(str) == lv)
                n = int(m.sum())
                if n < ARM_MIN_CELLS:
                    continue
                if numeric:
                    x = pd.to_numeric(v[m], errors="coerce").to_numpy(dtype=float)
                    x = x[np.isfinite(x)]
                    if x.size < ARM_MIN_CELLS:
                        continue
                    q1, med, q3 = (float(q) for q in np.quantile(x, [0.25, 0.5, 0.75]))
                    rows.append({"level": lv, "n": int(x.size), "median": med,
                                 "q1": q1, "q3": q3,
                                 "min": float(x.min()), "max": float(x.max())})
                else:
                    c = v[m].astype(str).value_counts()
                    rows.append({"level": lv, "n": n,
                                 "share": {str(k): round(int(x) / n, 6)
                                           for k, x in c.items()}})
            if len(rows) >= 2:
                per_factor[fac] = {"kind": "numeric" if numeric else "categorical",
                                   "arms": rows,
                                   "aliased_with": sorted(alias.get(fac, [])),
                                   "categories": levels_of_col}
        if per_factor:
            out[col] = per_factor
    return out


#: Below this many cells with both columns finite, a correlation describes the overlap and not
#: the cohort.
CONCORDANCE_MIN_CELLS = 200


def concordance(adata, produced_by, *, min_cells=CONCORDANCE_MIN_CELLS):
    """Every per-cell number one plugin produced, against every one ANOTHER plugin produced.

    A DIAGNOSTIC IS USELESS ON THE PAGE OF THE PLUGIN THAT COMPUTED IT. One plugin's summary
    reads "cell-cycle phase per cell, and the check that a trajectory is not a cell-cycle axis";
    the trajectory is on a different plugin's page, and nothing connected the two, so the check
    was computed, reported, and never applied to the claim it exists to bound. Exactly the shape
    of the upstream constraint reaching an index and none of the pages.

    Two things a trajectory report is asked for and could not otherwise have:

      * a second ordering to agree with. "When the expected topology is unknown, trajectories
        and downstream hypotheses should be confirmed by multiple trajectory inference methods"
        - Heumos et al., Nat Rev Genet 2023, doi:10.1038/s41576-023-00586-w. Two plugins that
          each produce an ordering are two methods, and the host is the only thing that holds
          both.
      * the cell-cycle check, which is a correlation between an ordering and a phase score and
        is arithmetic the moment both columns are in one object.

    Spearman, because an ordering is a rank and the relation between two orderings is monotone
    long before it is linear. CROSS-PLUGIN ONLY: two columns from one plugin are that plugin's
    own business and it can draw them together itself.

    Reports rho and n for every pair. It does not threshold, star or interpret - which
    correlation matters is a question about the biology.
    """
    import numpy as np
    import pandas as pd

    cols = []
    for owner, names in sorted((produced_by or {}).items()):
        for c in sorted(set(names or [])):
            if c in adata.obs and pd.api.types.is_numeric_dtype(adata.obs[c]) \
                    and not pd.api.types.is_bool_dtype(adata.obs[c]):
                cols.append((owner, c))
    out = {}
    for i, (o1, c1) in enumerate(cols):
        for o2, c2 in cols[i + 1:]:
            if o1 == o2:
                continue
            x = pd.to_numeric(adata.obs[c1], errors="coerce")
            y = pd.to_numeric(adata.obs[c2], errors="coerce")
            m = np.isfinite(x) & np.isfinite(y)
            n = int(m.sum())
            if n < min_cells:
                continue
            xr, yr = x[m].rank(), y[m].rank()
            if xr.std(ddof=0) == 0 or yr.std(ddof=0) == 0:
                continue
            rho = float(np.corrcoef(xr, yr)[0, 1])
            if rho != rho:
                continue
            rec = {"rho": round(rho, 4), "n": n,
                   "a": {"plugin": o1, "column": c1}, "b": {"plugin": o2, "column": c2}}
            out.setdefault(o1, []).append(rec)
            out.setdefault(o2, []).append(rec)
    for k in out:
        out[k].sort(key=lambda r: -abs(r["rho"]))
    return out


def describe(adata, keys, organism, assay, constraint_src):
    """The provenance block: what was found, and whether it was told or guessed."""
    return {
        "n_obs": int(adata.n_obs), "n_vars": int(adata.n_vars),
        "keys": {r: (v[0] or "") for r, v in keys.items()},
        "keys_why": {r: v[1] for r, v in keys.items()},
        "organism": organism[0] or "", "organism_why": organism[1],
        "assay": assay[0] or "", "assay_why": assay[1],
        "layers": manifest.layer_names(adata),
        "obsm": sorted(str(k) for k in adata.obsm),
        # Whatever upstream tools recorded themselves, not a list of one project's three. A
        # provenance block is any uns entry that is a mapping - naming the three this project
        # happens to use made every other pipeline's object look like it had no provenance.
        "upstream": sorted(str(k) for k, v in adata.uns.items() if isinstance(v, dict)),
        "constraint_source": constraint_src or "ABSENT",
    }


def read_design(path, samples=None, sample_col=None):
    """The design table: a CSV keyed on the sample column. Returns (table, key, factors).

    The factors a study is ABOUT are usually not in an annotated object - it carries the
    annotation, not the animal metadata - so they arrive as a table keyed on the sample.

    A sample present in the object with no row is REFUSED BY NAME. Nothing is derived by
    pattern-matching a sample name: that bakes one project's naming into a tool every other
    project then has to work around, and it fails silently on the first project that names things
    differently.

    Standard library only. A design table a reader cannot open without this package installed is
    a design table nobody can check.
    """
    import csv
    import os

    if not os.path.exists(path):
        raise Refuse(f"no design table at {path}")
    with open(path, newline="", encoding="utf-8") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(fh, dialect=dialect))
    if not rows:
        raise Refuse(f"{path} has no rows")

    cols = list(rows[0])
    key = sample_col or next(
        (c for c in cols if c.lower() in ("sample", "sample_id", "library", "batch", "donor")),
        None)
    if key is None:
        raise Refuse(f"{path}: no sample column found among {cols}. Pass --design-sample-col.")

    table = {str(r[key]): {c: r[c] for c in cols if c != key} for r in rows}
    factors = [c for c in cols if c != key]

    if samples:
        missing = [s for s in samples if s not in table]
        if missing:
            raise Refuse(
                f"{len(missing)} sample(s) in the object have no row in {path}: "
                f"{missing[:8]}{' ...' if len(missing) > 8 else ''}. "
                f"The table has {len(table)}: {sorted(table)[:8]}. "
                f"Nothing is inferred from a sample name.")
    return table, key, factors
