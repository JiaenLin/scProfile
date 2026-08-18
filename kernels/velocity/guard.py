#!/usr/bin/env python3
"""velocity's own guard: is this dataset one where velocity would MEAN what the report says?

Modelled on the agent harness's PreToolUse hook. It runs in the HOST, before the environment is
resolved and before anything is spent, reads what the host knows about the dataset on stdin, and
either allows with a note or DENIES with a reason. Exit 0 allows; non-zero denies.

A guard is not a prerequisite check. `unmet()` already refuses when the spliced layer is absent -
that is structural, and no amount of willingness makes it runnable. A guard is about
INTERPRETABILITY: the run would succeed, produce numbers, and those numbers would not support the
sentence a reader will write under them.

Its escape hatch is `--allow velocity`, and every use is appended to guard_overrides.jsonl with
the reason. A gate with no escape gets switched off; a gate whose escapes are all recorded does
not.
"""
from __future__ import annotations

import json
import sys


def main():
    ctx = json.load(sys.stdin)
    d = ctx.get("describe") or {}
    assay = (d.get("assay") or "").lower()
    organism = (d.get("organism") or "").lower()
    notes, deny = [], []

    if not assay:
        deny.append(
            "The assay is not declared or detected, and velocity says different things about\n"
            "nuclei and whole cells. On nuclei the unspliced fraction is high BY CONSTRUCTION,\n"
            "so every caveat this kernel writes depends on knowing which you have.\n"
            "  Fix: pass --assay nucleus or --assay cell. It changes no computation.")
    elif assay == "nucleus":
        notes.append(
            "single-NUCLEUS velocity: validated directionally against matched cells "
            "(r 0.94-0.99, Sci Rep 2024), but the pseudotime output rests on more than the "
            "arrows do")

    if not organism:
        notes.append("organism unknown; nothing here depends on it, but the report will say so")

    if deny:
        print("\n".join(deny))
        return 1
    print(" | ".join(notes) if notes else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
