"""Everything in this repository's documents that is rendered from its own declarations.

THERE IS NO SECOND REGISTRY - and there turned out to be four of them, not one. This module began
as `roadmap.py`, owning the Tier 0 table alone, and the same defect was then measured in the panel
layer: adding ONE panel kind meant four edits across two files, three of them tables keyed by the
same sixteen ids and one of them a count word in a skill's frontmatter. A second hand-maintained
catalogue is what proves one owner is needed rather than one exception.

Two of those four are gone at the source: `panels.OWNER` and `panels.SERVES` are derived from
`Kind` rather than written beside it. What is left here is the documents, which cannot derive
anything and must be written.

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

#: THE MARKER IS AN ADDRESS AND MUST NOT CARRY THE COMMAND. It did, and renaming the command from
#: `roadmap` to `generated` orphaned the block in the document it owned: the tool could no longer
#: find the region it was supposed to rewrite, so the one command that could have repaired the
#: file was the one thing that could not run. A generator whose own rename breaks its output is a
#: generator that cannot be maintained.
#:
#: So the address is stable and the instruction lives in the rendered body, where it is also more
#: likely to be read - a marker is invisible in every renderer a reader is likely to use.
FIX = "python -m scprofile.cli generated --write"
BEGIN = "<!-- BEGIN shipped -->"
END = "<!-- END shipped -->"
#: AND AN OLD ADDRESS STILL RESOLVES. Anything up to the first `-->` is the marker, so a block
#: written by the previous version is found, and rewriting normalises it.
_BEGIN_RX = r"<!-- BEGIN shipped\b[^>]*-->"

#: THROUGH TWENTY, because the first version stopped at twelve and the panel catalogue has
#: sixteen kinds - so the generated sentence read "16 network and per-unit panel kinds" while the
#: check that guards it looks for the WORD. A generator that silently falls back to a form its own
#: checker rejects writes a file that fails on the next run.
_COUNT_WORD = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
               "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
               "seventeen", "eighteen", "nineteen", "twenty")


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
             f"{'' if len(names) != 1 else 's'}. Generated from the kernel declarations by",
             f"`{FIX}` — a kernel is added by adding its file, never by editing this table.", "",
             "| kernel | answers | needs |", "|---|---|---|"]
    for n in names:
        spec = getattr(kernels[n], "spec", None) or {}
        lines.append(f"| `{n}` | {_cell(spec.get('summary'))} | {_cell(_needs(spec))} |")
    lines += ["", END]
    return "\n".join(lines)


def current(text):
    """The block as it stands in this document, or None when there is no block."""
    m = re.search(_BEGIN_RX + r".*?" + re.escape(END), text, re.S)
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


# ------------------------------------------------------------------------------------------------
# THE SKILL'S CATALOGUE. A frontmatter description is what an agent reads to decide whether a skill
# applies to the task in front of it, so a stale list there is worse than a stale README: it
# misinforms the reader who cannot check. This one carried a count word AND all sixteen kind ids by
# hand, and adding one kind reddened the suite on both.
#
# NOT MARKERS, ANCHORS. The description is a YAML block scalar, so an HTML comment written into it
# would become part of the description text - the tool would be corrupting the field it maintains.
# So the generated spans are located between literal phrases of the sentence they sit in, which
# also keeps the sentence readable to whoever edits the prose around them.
# ------------------------------------------------------------------------------------------------

SKILL = Path(".claude/skills/plugin-figures/SKILL.md")
_CAT_FROM = "Carries a PORTABLE CATALOGUE of "
_CAT_TO = " - each with what it establishes"
_RULES_TO = " rules paid for by real defects"


def _wrapped(text, column=0, width=97, indent="  "):
    """Wrapped as the file writes prose, allowing for the column the span STARTS at.

    `textwrap` measures from zero, and this span begins partway along an existing line - so
    wrapping it alone produced a first line running to about 150 characters in a file whose
    others stop near 97.

    `initial_indent`, NOT A PADDED STRING. Padding the text with spaces and slicing them back off
    afterwards deleted the first five panel ids from the skill's description: `drop_whitespace` is
    on by default, so textwrap removed the padding it had been given and the slice then took real
    characters. `initial_indent` is counted toward the width and is not dropped, which is the
    difference between modelling the column and corrupting the line.

    NEVER BREAK A WORD. This span begins at column 90 of a 97-column line, leaving seven
    characters, and textwrap's default is to split a word that cannot fit - so the count word came
    out as "seventee\\n  n network", which reads as a typo and fails the check that looks for the
    word. Overflowing the first line by one word is the right trade: the line is a few characters
    long and every word in it is a word.
    """
    import textwrap
    pad = " " * column
    lines = textwrap.wrap(text, width=width, initial_indent=pad,
                          break_long_words=False, break_on_hyphens=False)
    lines[0] = lines[0][column:]
    return ("\n" + indent).join(lines)


def _span(text, start_anchor, end_anchor):
    """(i, j) of what lies between two literal anchors, or None when either is absent/ambiguous."""
    if text.count(start_anchor) != 1 or text.count(end_anchor) != 1:
        return None
    i = text.index(start_anchor) + len(start_anchor)
    j = text.index(end_anchor, i)
    return (i, j) if j > i else None


def _word_before(text, anchor):
    """(i, j) of the single word immediately preceding a unique anchor.

    `plus ` occurs four times in this description and ` rules paid for by real defects` once, so
    the count is addressed from the end. An anchor that is not unique is not an address.
    """
    if text.count(anchor) != 1:
        return None
    j = text.index(anchor)
    i = j
    while i > 0 and not text[i - 1].isspace():
        i -= 1
    return (i, j)


def _catalogue(kinds, column=0):
    ids = ", ".join(k.id for k in kinds)
    return _wrapped(f"{_count(len(kinds))} network and per-unit panel kinds - {ids}", column)


def _skill_spans(text, panels):
    """[(i, j, wanted)] for every generated span in the skill, or None when one cannot be found."""
    cat = _span(text, _CAT_FROM, _CAT_TO)
    rules = _word_before(text, _RULES_TO)
    if cat is None or rules is None:
        return None
    column = cat[0] - (text.rfind("\n", 0, cat[0]) + 1)
    return [(cat[0], cat[1], _catalogue(panels.KINDS, column)),
            (rules[0], rules[1], _count(len(panels.RULES)))]


def _apply(text, spans):
    """Rewrite right-to-left, so an earlier span's new length cannot move a later one's offsets."""
    for i, j, wanted in sorted(spans, reverse=True):
        text = text[:i] + wanted + text[j:]
    return text


def blocks(root=None):
    """[(name, path, check(text) -> problem, rewrite(text) -> text)] for every generated region."""
    from . import panels
    base = Path(root or Path(__file__).resolve().parent.parent)
    ks = ships()

    def roadmap_check(text):
        return check(text, ks)

    def skill_check(text):
        spans = _skill_spans(text, panels)
        if spans is None:
            return (f"the catalogue sentence cannot be located: expected {_CAT_FROM!r} ... "
                    f"{_CAT_TO!r} and one {_RULES_TO!r}. Run `{FIX}` after repairing the prose")
        if any(text[i:j] != wanted for i, j, wanted in spans):
            return f"the panel catalogue is not what panels.py says. Run `{FIX}`"
        return ""

    def skill_rewrite(text):
        spans = _skill_spans(text, panels)
        if spans is None:
            raise ValueError("the catalogue sentence cannot be located in the skill")
        return _apply(text, spans)

    return [("ROADMAP.md shipped table", base / "ROADMAP.md", roadmap_check,
             lambda text: rewrite(text, ks)),
            ("the figures skill's panel catalogue", base / SKILL, skill_check, skill_rewrite)]
