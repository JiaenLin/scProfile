"""The shipped table, rendered from the declarations. THERE IS NO SECOND REGISTRY.

A KERNEL WAS ADMITTED BY TWO AUTHORITIES AND ONLY ONE OF THEM WAS THE CODE. `discover()` found a
new kernel the moment its file existed - no manifest, no import, no host edit, which is the whole
claim of the one-file plugin - and then the suite went red on ROADMAP.md, twice: once because the
Tier 0 table had no row for it, and once because a sentence above the table said "All nine". So
the real admission gate was a markdown table a newcomer had to be told about, and it failed in
both directions. Deleting a kernel left its row behind; adding one left the count behind.

The table is not decoration. A downstream project's index once recorded "scProfile ships
`cellcycle` and `velocity` only" and blocked a stage on a plugin that had been shipping for days.
A roadmap's *shipped* row is read as a statement of fact by people who will not open the source -
which is the argument for keeping the table, and the argument for not letting a human maintain it.

WHAT IS GENERATED AND WHAT IS NOT. This module renders only what the declarations know: which
kernels exist, what each answers, and what each must be given. It does not render the claim that
they meet the exit standard, or the date on which that was true, because it cannot check either -
a generator that emits a claim it cannot verify has laundered an assertion into a fact. Those
sentences stay in the prose outside the block, written and dated by whoever checked them.

THE `needs` COLUMN IS THE TOOL'S OWN VOCABULARY, not a paraphrase of it. `label`, `sample`,
`design` are the capability names the declaration uses and `--kernel` errors quote, so a reader
who has only ever seen the roadmap can still read a refusal. A prose column drifted: it said
pseudotime needs `cellcycle`, which names a peer - the one thing a declaration may never do - and
pseudotime does not read a phase call at all. Nine months of that sentence, and no check could
see it, because a paraphrase is not comparable to anything.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

#: The block a generator owns, and the exact command that rewrites it. Both markers carry the
#: command: whichever one a reader's eye lands on first tells them what not to hand-edit.
FIX = "python -m scprofile.cli roadmap --write"
BEGIN = f"<!-- BEGIN shipped: generated from the kernel declarations by `{FIX}` -->"
END = "<!-- END shipped -->"

_COUNT_WORD = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
               "ten", "eleven", "twelve")


def _count(n):
    """Twelve words, then digits. A count in prose reads as prose until it gets big."""
    return _COUNT_WORD[n] if n < len(_COUNT_WORD) else f"{n}"


def _needs(spec):
    """What this kernel must be given, in the vocabulary the host resolves.

    Three sources, because a kernel states its prerequisites in three places and each is there
    for a reason. `inject.required` is a capability the host resolves against the object.
    `needs.layers` is a literal layer the host does NOT resolve - velocity's spliced and unspliced
    counts come from the aligner and cannot be repaired later, so they are deliberately not an
    inject. `references` and an R interpreter are neither: they are what the BUILDER must fetch
    and install before the kernel can run at all, and a reader deciding whether to try a kernel
    wants to know that before they read anything else.
    """
    inj = (spec.get("inject") or {}).get("required") or []
    bits = [", ".join(f"`{c}`" for c in inj)] if inj else []
    layers = (spec.get("needs") or {}).get("layers") or []
    literal = [x for x in layers if not (str(x).startswith("{") and str(x).endswith("}"))]
    if literal:
        bits.append("layers " + ", ".join(f"`{x}`" for x in literal))
    if ((spec.get("requires") or {}).get("r")):
        bits.append("R")
    refs = spec.get("references") or {}
    if refs:
        bits.append(f"{len(refs)} reference file{'s' if len(refs) != 1 else ''}")
    return "; ".join(bits) or "—"


def _cell(text):
    """A markdown table cell. A pipe inside one silently invents a column."""
    return str(text or "").replace("|", "\\|").replace("\n", " ").strip()


def render(kernels):
    """The generated block, markers included, for this set of kernels."""
    names = sorted(kernels)
    lines = [BEGIN, "",
             f"{_count(len(names)).capitalize()} kernel{'s' if len(names) != 1 else ''} ship"
             f"{'' if len(names) != 1 else 's'}. This table is generated; a kernel is added by "
             f"adding its file.", "",
             "| kernel | answers | needs |", "|---|---|---|"]
    for n in names:
        spec = getattr(kernels[n], "spec", None) or {}
        lines.append(f"| `{n}` | {_cell(spec.get('summary'))} | {_cell(_needs(spec))} |")
    lines += ["", END]
    return "\n".join(lines)


def current(text):
    """The block as it stands in this document, or None when there is no block."""
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), text, re.S)
    return m.group(0) if m else None


def check(text, kernels):
    """"" when the document is what the declarations say, else what is wrong and the fix."""
    have, want = current(text), render(kernels)
    if have is None:
        return f"no generated block: {BEGIN!r} ... {END!r} is missing. Run `{FIX}`"
    if have != want:
        return f"the shipped table is not what the declarations say. Run `{FIX}`"
    return ""


def rewrite(text, kernels):
    """The document with its block brought up to date. Raises when there is no block to fill."""
    have = current(text)
    if have is None:
        raise ValueError(f"no {BEGIN!r} ... {END!r} block in this document")
    return text.replace(have, render(kernels), 1)


def path(root=None):
    return Path(root or Path(__file__).resolve().parent.parent) / "ROADMAP.md"


def ships():
    """What the REPOSITORY ships, with the site search path out of the way.

    `discover()` deliberately honours $SCPROFILE_KERNELS, because adding a method without forking
    is the whole point of that variable - and a plugin somebody else dropped in is not a plugin
    this repository ships. Rendered from `discover()` bare, the table would gain a row for a
    stranger's file on any machine with the variable set, and lose it again on any machine
    without: the document would then depend on the environment of whoever last ran the command.
    """
    from .kernels import discover
    keep = os.environ.pop("SCPROFILE_KERNELS", None)
    try:
        return discover()
    finally:
        if keep is not None:
            os.environ["SCPROFILE_KERNELS"] = keep
