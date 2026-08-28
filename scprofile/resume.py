"""What a run directory ALREADY HOLDS, and what is therefore left to do.

RERUNNING WHAT IS ALREADY DONE IS NOT A NEUTRAL COST. It is the cost that decides whether a
fix gets checked against real data or against a fixture: a change to a figure does not need the
inference recomputed, but if the only way to see the figure is a full run, the figure gets
checked on synthetic data or not at all. That is a correctness problem wearing a performance
problem's clothes.

THE STATES ARE THE MANIFEST'S, NOT NEW ONES. `manifest.py` already defines what a unit
directory means and this module must not invent a second vocabulary for the same files:

    out.json absent, nothing staged   never started
    out.json absent, inputs staged    STARTED AND DIED - the one state that must be redone
    out.json present, no entries      ran and found nothing. THAT IS A RESULT.
    out.json present, with entries    produced these things

The third row is the one a resume gets wrong. "Empty" reads like "failed" and it is not: a unit
where the method ran correctly and returned nothing is finished, and re-running it produces the
same nothing at full price. A resume that retries empty units silently converts a negative
result into an unstable one, because the next run may differ for unrelated reasons and nobody
will know which run the emptiness came from.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Ordered by how much work they imply is outstanding, most finished first.
DONE = "done"
EMPTY = "empty"
STALE = "stale"
DIED = "died"
ABSENT = "absent"

#: States that need no recomputation. `EMPTY` is here deliberately - see the module docstring.
FINISHED = (DONE, EMPTY)


def unit_dir(out, plugin, unit=None):
    """Where one instance writes - the same expression the runner uses, in one place."""
    return Path(out) / "kernels" / str(plugin) / (str(unit) if unit else "")


def state(d, want_version=None):
    """(state, why, n_entries) for one instance directory. Reads, never runs anything.

    `want_version` is the plugin version the CALLER is about to run. When it is given and does
    not match what the unit recorded, the unit is STALE and must be redone however complete it
    looks. THIS IS THE PROPERTY THAT MAKES A RESUME SAFE TO USE. Without it a resume across a
    plugin change silently produces one run directory holding units from two different versions
    of the code - each internally consistent, the set of them describing nothing, and no field
    anywhere saying so. It is the same failure as a run key naming a commit the run did not use,
    which this project has already paid for.
    """
    d = Path(d)
    oj = d / "out.json"
    if not oj.exists():
        if not d.exists():
            return ABSENT, "no directory - this instance has never been staged", 0
        # STAGED BUT UNFINISHED. The host writes the kernel's inputs before launching it, so
        # inputs without an out.json is the signature of a kernel that started and did not
        # return - killed, crashed, or still running. It is the one state that must be redone.
        staged = [p.name for p in d.iterdir() if p.name != "out.json"]
        if staged:
            return DIED, (f"inputs were staged ({len(staged)} file(s)) but no out.json was "
                          f"written - the kernel started and did not return"), 0
        return ABSENT, "directory exists but is empty", 0
    try:
        payload = json.loads(oj.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # UNREADABLE IS NOT FINISHED. A truncated out.json is what a kill during the write
        # leaves behind, and treating it as done would skip the unit forever.
        return DIED, f"out.json is present but unreadable ({exc}) - treat as unfinished", 0
    n = sum(len(payload.get(k) or []) for k in ("figures", "tables", "objects")
            if isinstance(payload.get(k), list))
    got = payload.get("version")
    if want_version is not None and got is not None and str(got) != str(want_version):
        return STALE, (f"produced by plugin version {got!r}, and {want_version!r} is what would "
                       f"run now - a resume that kept this would mix two versions in one run "
                       f"directory"), n
    if n == 0:
        return EMPTY, ("ran and produced nothing. THAT IS A RESULT, not a failure - re-running "
                       "it costs the same and answers the same"), 0
    return DONE, f"produced {n} artifact(s)", n


def survey(out, instances, versions=None):
    """One row per instance: (plugin, unit, state, why, n). Order is the caller's.

    `versions` maps plugin name -> the version about to run, so staleness can be detected.

    `instances` is any iterable of (plugin, unit) or of mappings carrying `plugin` and `unit` -
    a plan's instance list passes straight in.
    """
    rows = []
    for inst in instances:
        if isinstance(inst, dict):
            plugin, unit = inst.get("plugin"), inst.get("unit")
        else:
            plugin, unit = (list(inst) + [None])[:2]
        want = (versions or {}).get(plugin)
        st, why, n = state(unit_dir(out, plugin, unit), want_version=want)
        rows.append((plugin, unit, st, why, n))
    return rows


def discover(out):
    """Every instance a run directory already holds, without needing a plan to ask about.

    So `status` can be pointed at a directory alone. A resume that can only describe a run it
    can re-plan is useless in the case that matters most - the object moved, the plan cannot be
    rebuilt, and the question is precisely what survived.
    """
    root = Path(out) / "kernels"
    if not root.is_dir():
        return []
    found = []
    for pdir in sorted(p for p in root.iterdir() if p.is_dir()):
        subs = sorted(c for c in pdir.iterdir() if c.is_dir() and c.name != "figures"
                      and c.name != "tables")
        # A COHORT PLUGIN WRITES AT THE PLUGIN LEVEL and a per-unit plugin writes one level
        # down. Which it is, is visible from the files rather than declared here.
        if (pdir / "out.json").exists():
            found.append((pdir.name, None))
        for c in subs:
            if (c / "out.json").exists() or any(c.iterdir()):
                found.append((pdir.name, c.name))
    return found


def outstanding(rows):
    """The instances a resume would actually run, in the order given."""
    return [(p, u) for p, u, st, _w, _n in rows if st not in FINISHED]


def summarise(rows):
    """{state: count} - for a one-line report."""
    out = {}
    for _p, _u, st, _w, _n in rows:
        out[st] = out.get(st, 0) + 1
    return out
