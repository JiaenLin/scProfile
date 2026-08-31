"""What a run DECLINED TO COMPARE, recorded by the run rather than remembered by a person.

WHY THIS EXISTS. Analyses remove things. A comparison restricts itself to the elements both sides
have; a four-way comparison restricts harder still; a minimum-size floor drops an element before
it is ever scored. Every one of those is defensible and every one is invisible in the result: a
panel drawn on nine populations and a panel drawn on eleven look identical, and the number under
each is quoted the same way.

The failure is never the removal. It is that the removal is described rather than NAMED - "the
populations the arms did not share" reads as a technicality, and "Immune/Lymphoid, 542 cells in
one arm, absent from another, therefore not in the interaction" reads as what it is. A reader
given the first cannot ask the question the second invites.

So a removal is a RECORD the run writes, in a declared format, with the elements named. Three
properties make it worth having rather than a comment somebody keeps up to date:

  NAMES, OR IT IS REFUSED. A row with no element is not a record of a removal, it is a count of
  one, and a count cannot be argued with. `check` rejects it.

  THE HOST COMPUTES WHETHER IT IS DIFFERENTIAL, rather than trusting whoever wrote the row. An
  element missing from every arm at one level of a factor and from none at the other is aligned
  with that factor - which turns a technical omission into an apparent biological difference, and
  is the one thing about a removal that cannot be judged by the person making it.

  IT IS REPORTED ONCE, where it belongs, and travels into the written section automatically. A
  removal nobody reads is the same as one nobody recorded.

Nothing here knows what an element is. A population, a gene, a pathway, a sample - the format is
`what was removed`, `where it was absent`, `where it was present`, `why`, and the design does the
rest.
"""

from __future__ import annotations

import csv
import glob
import os
from pathlib import Path

#: The columns a removal record carries. `element` is the only one that cannot be empty.
COLUMNS = ("scope", "element_kind", "element", "absent_from", "present_in", "reason")

#: The file a plugin writes, wherever it writes one. The host looks for it beside a comparison's
#: figures and beside a unit's tables, because those are the two places a removal is decided.
NAME = "removals.csv"


class Unnamed(Exception):
    """A removal was recorded without naming what it removed."""


def write(path, rows):
    """Write removal records. Refuses a row that does not name what it removed."""
    rows = [dict(r) for r in (rows or [])]
    check(rows)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    return p


def check(rows):
    """Raise `Unnamed` unless every row names an element. The whole point of the record.

    A count of what was dropped cannot be argued with; a list can. This is the one rule the
    format enforces rather than merely documents.
    """
    bad = [i for i, r in enumerate(rows or [], 1) if not str((r or {}).get("element", "")).strip()]
    if bad:
        raise Unnamed(
            f"{len(bad)} removal record(s) do not name what was removed (rows {bad[:5]}). "
            f"A removal described by its category - 'the ones not shared', 'the small ones' - "
            f"cannot be checked by a reader or argued with by a reviewer. Name them.")
    return True


def read(run, plugin):
    """Every removal this run recorded for one plugin, from wherever it was written."""
    base = Path(run) / "kernels" / str(plugin)
    out = []
    for f in sorted(glob.glob(str(base / "**" / NAME), recursive=True)):
        try:
            with open(f, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    r["_from"] = os.path.relpath(f, Path(run))
                    out.append(r)
        except (OSError, ValueError):
            continue
    return out


def _levels(design, arm_members, arm):
    """{factor: level} for one arm: its own design row, or the one its members share."""
    des = dict(design or {})
    if arm in des:
        return {k: str(v) for k, v in (des[arm] or {}).items()}
    mem = [str(x) for x in ((arm_members or {}).get(arm) or ())]
    out = {}
    for f in {k for m in mem for k in (des.get(m) or {})}:
        lv = {str((des.get(m) or {}).get(f, "")) for m in mem}
        lv.discard("")
        if len(lv) == 1:
            out[f] = next(iter(lv))
    return out


def differential(rows, design, arm_members=None):
    """[(element, factor, level)] - removals that line up with one side of a design factor.

    RULE ONE'S THIRD QUESTION, COMPUTED HERE RATHER THAN ASKED OF THE CALLER. An element absent
    from every arm at one level of a factor and present at the other has had a technical property
    converted into an apparent biological difference, and no downstream analysis can undo it. It
    is also the one thing about a removal that the person making it is worst placed to judge.
    """
    out = []
    for r in (rows or []):
        el = str(r.get("element", "")).strip()
        gone = [x for x in str(r.get("absent_from", "")).split("|") if x.strip()]
        have = [x for x in str(r.get("present_in", "")).split("|") if x.strip()]
        if not (el and gone and have):
            continue
        lv_gone = [_levels(design, arm_members, a) for a in gone]
        lv_have = [_levels(design, arm_members, a) for a in have]
        for f in {k for d in lv_gone + lv_have for k in d}:
            g = {d.get(f) for d in lv_gone if d.get(f)}
            h = {d.get(f) for d in lv_have if d.get(f)}
            # absent from exactly one level, and present at none of the arms carrying it
            if len(g) == 1 and h and not (g & h):
                out.append((el, f, next(iter(g))))
    return sorted(set(out))


def summarise(rows, design=None, arm_members=None):
    """(n_elements, [names], [(element, factor, level)]) - what to print, once."""
    names = sorted({str(r.get("element", "")).strip()
                    for r in (rows or []) if str(r.get("element", "")).strip()})
    return len(names), names, differential(rows, design, arm_members)
