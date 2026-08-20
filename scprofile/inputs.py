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

#: Labels an annotator uses to say "no call". Not cell types, and never treated as populations.
#: These are scAnno's declared sentinels; overridable for an annotation that uses others.
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
}

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
        pool = list(layers) if role == "counts_layer" else cols
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
    return out


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


def read_constraint(adata):
    """The upstream constraint on use, if the object carries one. Absence is a FINDING.

    scIntegrate writes what its chosen embedding may and may not carry, computed from the design.
    The abundance kernel needs it: a factor nested in the batch key is not identifiable, and a
    differential-abundance test will return small confident p-values for it regardless.

    Returns (text, source). Source is "" when there is none, and the caller must say so rather
    than proceeding as though the design had been checked.
    """
    u = adata.uns.get("scintegrate")
    if isinstance(u, dict):
        c = u.get("constraint_on_use")
        if c:
            return str(c), "uns['scintegrate']['constraint_on_use']"
    return "", ""


def describe(adata, keys, organism, assay, constraint_src):
    """The provenance block: what was found, and whether it was told or guessed."""
    return {
        "n_obs": int(adata.n_obs), "n_vars": int(adata.n_vars),
        "keys": {r: (v[0] or "") for r, v in keys.items()},
        "keys_why": {r: v[1] for r, v in keys.items()},
        "organism": organism[0] or "", "organism_why": organism[1],
        "assay": assay[0] or "", "assay_why": assay[1],
        "layers": sorted(str(k) for k in adata.layers if k is not None),
        "obsm": sorted(str(k) for k in adata.obsm),
        "upstream": sorted(k for k in ("scqc", "scanno_embed", "scintegrate") if k in adata.uns),
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
