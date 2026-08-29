#!/usr/bin/env python3
"""PreToolUse hook: surface the development guideline when scProfile code is written.

Prose in a document is read once. This puts the same points in front of whoever is about to
write, every time, which is the only reliable moment for them to matter.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return 0
    if ev.get("tool_name") not in ("Write", "Edit", "NotebookEdit"):
        return 0
    p = str((ev.get("tool_input") or {}).get("file_path") or "")
    if not p or not p.startswith(str(ROOT)):
        return 0
    if p.endswith((".md", ".txt", ".json")):
        return 0
    g = ROOT / "DEVELOPMENT.md"
    if g.exists():
        print(g.read_text(encoding="utf-8"), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
