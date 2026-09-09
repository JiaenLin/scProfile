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

AND A PHASE IS NOT AN INSTANCE. The four rows above describe an INSTANCE - one plugin over one
unit, planned, scheduled and resumable. A plugin also has phases that take no unit at all: the
reporter re-launches `compare(ctx)` under `kernels/<plugin>/compare/`, once per arm pair and
once over every arm. `discover` walked into that directory, found it non-empty and reported it
as an instance - so a run in which EVERY instance succeeded and the reporting worked reported
`1 died`, and `check --out` answered "every instance finished" with FALSE and "1 outstanding".
The states above were being applied to a directory they were never about. `phase_of` below is
where the two are told apart, and it is told apart at the level `discover` actually enumerates.
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

#: The subdirectory of a plugin's output that holds a PHASE of the run rather than an INSTANCE
#: of it. The reporter re-launches the plugin's `compare(ctx)` in here, once per arm pair and
#: once over every crossed arm; none of those launches is a unit. Named here rather than in the
#: reporter because two sides have to agree on the word - the side that creates the directory
#: and the side that has to not mistake it for work left undone.
COMPARE_DIRNAME = "compare"

#: What a phase writes at the level `discover` enumerates, so a phase directory can SAY what it
#: is instead of being recognised only by its name. A directory written before this file existed
#: is still recognised - see `phase_of`.
PHASE_RECORD = "phase.json"

#: Directories under a plugin that hold the plugin's own cohort output, not one instance's.
_PLUGIN_OUTPUT_DIRS = ("figures", "tables")


def phase_of(d):
    """The phase this directory records, or None when it is an instance directory.

    DECIDED ON THE DIRECTORY'S OWN NAME, AT THE LEVEL `discover` ACTUALLY ENUMERATES. The first
    guard proposed for this tested whether the PARENT directory was named `compare` and read a
    manifest to confirm it, and reproducing it showed it could never fire: `discover` walks
    exactly two levels - `kernels/<plugin>/<child>` - so the row it produces for the reporter's
    phase IS `kernels/<plugin>/compare`. That directory's parent is the PLUGIN name, and it holds
    neither `in.json` nor `out.json`, because both are written one level deeper under
    `compare/<label>/`. A guard keyed on either of those facts is a guard written against a
    directory shape that never occurs. The reproduction is the FIRST assertion in
    `tests/test_the_compare_phase_is_recorded.py` for exactly that reason.

    THE NAME ALONE IS NOT ENOUGH EITHER, because a unit may legitimately be called `compare` -
    nothing stops a sample being named that, and hiding a real instance would be the same defect
    facing the other way. An instance directory is staged with its own `in.json` and finishes
    with its own `out.json`; a phase directory has neither AT THIS LEVEL. So: a directory is a
    phase when it carries the phase record, or when it is named for a phase and carries no
    manifest of its own.
    """
    d = Path(d)
    rec = d / PHASE_RECORD
    if rec.is_file():
        try:
            got = (json.loads(rec.read_text(encoding="utf-8")) or {}).get("phase")
        except (OSError, ValueError):
            got = None
        return str(got) if got else d.name
    if (d.name == COMPARE_DIRNAME
            and not (d / "in.json").exists() and not (d / "out.json").exists()):
        return COMPARE_DIRNAME
    return None


def phases(out):
    """[(plugin, phase, record)] - every phase a run directory holds and what it recorded.

    KEPT APART FROM `discover`, DELIBERATELY. These are launches of a plugin that took no unit:
    they are not in the plan, a resume does not iterate them, and a survey must not count them.
    They are still executions the run paid for, so they belong in the run's execution record -
    the reporter renders them into its schedule table from here, and `record["cardinality"]`
    says how many launches the phase declared, ran, reused and skipped.

    A phase directory written before the record existed comes back with an empty record rather
    than being dropped: "this ran and left no receipt" is the thing worth being able to see.
    """
    root = Path(out) / "kernels"
    if not root.is_dir():
        return []
    rows = []
    for pdir in sorted(p for p in root.iterdir() if p.is_dir()):
        for c in sorted(x for x in pdir.iterdir() if x.is_dir()):
            ph = phase_of(c)
            if not ph:
                continue
            rec, f = {}, c / PHASE_RECORD
            if f.is_file():
                try:
                    rec = json.loads(f.read_text(encoding="utf-8")) or {}
                except (OSError, ValueError):
                    rec = {}
            rows.append((pdir.name, ph, rec))
    return rows


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

    INSTANCES ONLY. What this returns is fed to `survey`, `outstanding`, `licence` and the
    landscape, every one of which reasons about work a resume could finish. A plugin's PHASE
    directories are excluded here and enumerated by `phases` instead; see `phase_of`.
    """
    root = Path(out) / "kernels"
    if not root.is_dir():
        return []
    found = []
    for pdir in sorted(p for p in root.iterdir() if p.is_dir()):
        subs = sorted(c for c in pdir.iterdir() if c.is_dir()
                      and c.name not in _PLUGIN_OUTPUT_DIRS
                      # A PHASE IS NOT AN INSTANCE, and this is the line where that has to be
                      # said. `any(c.iterdir())` below accepts ANY non-empty subdirectory, and
                      # the reporter's compare phase creates one - so a run whose every instance
                      # SUCCEEDED reported `1 died` because the reporting had worked. The state
                      # was real; the row it was attached to was not an instance at all.
                      and not phase_of(c))
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
