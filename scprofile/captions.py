"""A figure's legend, written by whatever drew it, rather than derived from its filename.

WHY THIS EXISTS. The host names a panel by inverting the plugin's declaration - which file came
from which function - and that is enough to say where a figure came from. It is not remotely
enough to say what the figure SHOWS. With no better source the caption became the filename with
its underscores removed:

    "interaction flow  age response by diet, drawn by the tool itself."

That is a filename. It does not say what the axes are, what the dashed line means, what the colour
encodes, that the panel is a difference of two differences, or that no test applies to it. And the
caption is what travels into the written section, so everything a title says is lost the moment a
reader meets the panel anywhere else.

WORSE, THE FALLBACK ASSERTS A PROVENANCE IT CANNOT KNOW. "Drawn by the tool itself" is false for a
panel the PLUGIN drew from the tool's numbers - a second scale, a derived matrix - and the
distinction between those two is exactly what the upstream-plot accounting exists to protect. A
caption that gets it wrong undoes that accounting at the last step.

So whatever draws a figure writes its legend, next to it, in this format. The host prefers it and
keeps the filename fallback for anything undescribed, so nothing regresses for a plugin that has
not been changed.

Nothing here knows what a figure shows. It knows that a legend must exist, must not be empty, and
must say truthfully who drew it.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

#: The file a plugin writes beside the figures it just drew.
NAME = "captions.tsv"

#: `file` is the figure's basename; `caption` is its legend; `drawn_by` is who drew it.
COLUMNS = ("file", "caption", "drawn_by")

#: WHO DREW A PANEL, and the two answers are not interchangeable. `tool` is the wrapped tool's own
#: plotting function, unmodified. `plugin` is this plugin drawing the tool's NUMBERS itself -
#: a second scale, a derived matrix, an annotation layer - which is a different claim about
#: provenance and must not be reported as the tool's own encoding.
DRAWN_BY = ("tool", "plugin")


class BadCaption(Exception):
    """A legend is missing, empty, or claims a provenance that is not one of the two."""


def check(rows):
    """Raise unless every row has a file, a non-trivial legend, and a valid provenance."""
    bad = []
    for i, r in enumerate(rows or [], 1):
        f = str((r or {}).get("file", "")).strip()
        c = " ".join(str((r or {}).get("caption", "")).split())
        by = str((r or {}).get("drawn_by", "")).strip()
        if not f:
            bad.append(f"row {i}: no file")
        elif len(c.split()) < 5:
            bad.append(f"{f}: a legend of {len(c.split())} word(s) is a label, not a legend")
        elif by not in DRAWN_BY:
            bad.append(f"{f}: drawn_by={by!r}, expected one of {DRAWN_BY}")
    if bad:
        raise BadCaption("; ".join(bad[:6]))
    return True


def write(path, rows):
    """Write the legends for one directory of figures. Refuses a row that fails `check`.

    THE PLUGIN-SIDE FILE IS NOT WRITTEN HERE. A wrapped tool draws in its own interpreter and
    writes `captions.tsv` beside its figures, so this writer serves the host and anything
    running in Python - which is why the same invariant has to be enforced again at READ time,
    below, rather than trusted to whoever wrote the file.
    """
    rows = [dict(r) for r in (rows or [])]
    check(rows)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(COLUMNS), delimiter="\t")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    return p


def read(directory):
    """{figure basename: {caption, drawn_by}} for one directory, or `{}`.

    Looked for beside the figures AND one level up, because a plugin may write its figures into a
    `figures/` subdirectory and its tables beside it, and neither placement should be the one that
    silently loses the legends.
    """
    d = Path(directory)
    out, malformed = {}, []
    for cand in (d / NAME, d.parent / NAME):
        if not cand.is_file():
            continue
        try:
            with open(cand, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh, delimiter="\t"):
                    # A ROW WITH EXTRA FIELDS IS A CORRUPTED ROW, NOT A ROW TO GUESS AT. The
                    # file is tab-separated and a writer that does not quote turns one caption
                    # containing a tab into a row whose columns are all shifted. `DictReader`
                    # parks the surplus under the key `None`, which is the only signal that
                    # happens - and dropping such a row silently is how a figure comes to carry
                    # a neighbouring figure's legend.
                    if r.get(None):
                        malformed.append(str(r.get("file", "?")))
                        continue
                    f = os.path.basename(str(r.get("file", "")).strip())
                    cap = " ".join(str(r.get("caption", "")).split())
                    if f and cap:
                        out.setdefault(f, {"caption": cap,
                                           "drawn_by": str(r.get("drawn_by", "")).strip()})
        except (OSError, ValueError):
            continue
    if malformed:
        # SAY IT, DO NOT ONLY SKIP IT. A legend file that lost rows renders as a page whose
        # figures fall back to their filenames, which is indistinguishable from a plugin that
        # never wrote legends at all.
        print(f"  {len(malformed)} malformed legend row(s) in {d}: {', '.join(malformed[:4])}")
    return out


def provenance(drawn_by, function=""):
    """The sentence naming who drew a panel, or "" when nothing is known.

    THE DEFAULT SAYS NOTHING RATHER THAN GUESSING. A caption that asserts the wrong provenance is
    worse than one that omits it: the first is checked and believed, the second is noticed.
    """
    by = str(drawn_by or "").strip()
    fn = str(function or "").strip()
    if by == "tool":
        return f"Drawn by the tool's own {fn}()." if fn else "Drawn by the wrapped tool."
    if by == "plugin":
        return (f"Drawn by this plugin from {fn}()'s own numbers, not by {fn}() itself."
                if fn else "Drawn by this plugin from the tool's own numbers.")
    return ""
