"""A vector copy is written for the figures a result is written from, and not for the rest.

The PDF beside each PNG is not redundant - the report offers it as a "vector (PDF)" download, and
a reader preparing a manuscript wants it. It was being written for EVERY panel. Measured on one
cohort: 360 files for 180 diagnostic plates, ten per unit across eighteen units, in two formats,
and the composed section cites none of them.

Which kinds those are is not the host's to know. The plugin already says, by placing a kind
`appendix` - the same declaration that keeps it out of the paper's numbering - so this reads that
map rather than introducing a second one that can disagree with it.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile.plugin import _wants_vector                                # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


PLACED = {"diag": "appendix", "diag_keep": "contrast", "head": "overview"}

# THE FIXTURE CARRIES BOTH SIDES. A test whose every panel is withheld passes for a writer that
# never writes a vector at all.
check(_wants_vector(PLACED, "head_totals") is True,
      "a figure the paper is written from lost its vector copy")
check(_wants_vector(PLACED, "diag_permutation") is False,
      "an `appendix` kind still got a vector copy - the 180 files this exists to stop")
check(_wants_vector(PLACED, "diag_keep_this") is True,
      "the longer prefix did not win, so a family cannot be withheld with one member kept")

# UNDECLARED MEANS YES. A plugin that places nothing keeps every vector copy it had before this
# existed; a reduction nobody asked for is a regression.
check(_wants_vector({}, "anything") is True,
      "a plugin that declares no positions lost its vector copies")
check(_wants_vector(None, "anything") is True,
      "a missing declaration was read as `appendix`")

# THE NAME IS MATCHED, NOT THE PATH IT SITS IN.
check(_wants_vector(PLACED, "figures/diag_permutation") is False,
      "a path in front of the id defeated the match")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: the vector copy follows the paper, and an undeclared plugin keeps all of them")
