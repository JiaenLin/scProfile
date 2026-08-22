# The plugin design, and what it borrows

A plugin is written once and lives against a moving world. Two very different people have to be
able to trust it: the **builder**, which must make it runnable on a machine nobody has seen, and
the **maintainer**, who must change it years later without knowing what else depends on it.

This is what the shape has to earn.

---

## Borrowed from Cordis, and what was left behind

scProfile's host is inspired by [Cordis](https://github.com/cordiverse/cordis), the framework
behind DeepSeek Harness, whose organising claim is *everything is a plugin*. Four of its ideas
carry over almost unchanged, and the rest deliberately do not.

> The primary Cordis documentation was not reachable when this was written, so what follows is
> the model as understood from its published API surface, not a quotation of its docs. Where this
> design departs, it says so.

**Taken: injection.** A Cordis plugin declares `inject: ['database']` and the framework only
activates it when that service exists — the plugin never checks. scProfile does the same with
**capabilities**: a plugin declares what it must be given, and the host does not call it
otherwise. A plugin that begins `if not ctx.organism: refuse(...)` is doing the host's job, and
doing it once per plugin means doing it differently once per plugin.

**Taken: required versus optional.** Cordis separates injections that gate activation from ones
that are merely used if present. That distinction is the difference between *this plugin cannot
run* and *this plugin will do less*, and both belong in the declaration rather than in an `if`.

**Taken: capabilities, not names.** A Cordis plugin injects `database`, not `sqlite-plugin`.
scProfile plugins `provide` and `inject` **capabilities** — `ordering`, `communication`,
`activity` — so a plugin that needs an ordering does not care which plugin produced it, and a
better one can replace it without every consumer being edited.

**Taken: effects and disposal.** In Cordis everything a plugin registers is tied to its scope and
is undone when the scope closes. Here that is `ctx.effect()`: a dask client, a temp directory, an
R session, released whether the plugin returns, refuses or raises.

**Left behind: the event bus, reactive config, nested loading.** Those serve a long-lived
service host. This host runs batch analyses in subprocesses that exit. Importing that machinery
would be borrowing the shape of a solution to a problem this tool does not have.

---

## The declaration

```python
PLUGIN = {
    "api": 1,                      # the contract this plugin was written against
    "summary": "...",
    "inject": {
        "required": ["counts", "label"],     # the host will not call run() without these
        "optional": ["design", "embedding"], # used if present; the plugin does less without
    },
    "provides": ["activity"],                # capabilities, so consumers need not name plugins
    "config": {                              # typed, defaulted, validated BEFORE run()
        "min_cells": {"type": "int", "default": 10, "min": 1,
                      "help": "populations smaller than this are not scored"},
    },
    "env": {...}, "references": {...}, "upstream": {...}, "cannot_show": [...],
}
```

**`api` is the compatibility mechanism.** A host that understands api 1 and meets a plugin
declaring api 2 refuses it by name rather than calling it and failing somewhere inside. Without
it, the only way to discover a contract change is a crash in a stranger's run.

**`inject` replaces prerequisite checking inside plugins.** The host resolves each capability
against the object and the design, and either calls `run()` with everything present or reports
precisely which capability was missing — to the *planner*, which turns it into a verdict a user
can act on.

> **One function answers that question, for both.** `declare.available()` is asked by the
> entrypoint before `run()` and by the planner before a queue slot is spent, so the plan and the
> run cannot disagree about what a plugin will be given. It was implemented at run time only:
> the entrypoint refused correctly, the planner did not know `inject` existed, and a plugin
> requiring an organism was planned `RUN` against an object that had none — discovered an hour
> later, in a queue.

**`config` is validated before anything runs.** A bad `--params` should fail in the second the
plan is drawn, not an hour into a queue.

---

## What the host guarantees

Everything below happens for every plugin, in `_entry.py`, and none of it is a plugin's business:

- keys resolved, so **no plugin ever writes a column name**;
- the object subset to this plugin's unit;
- annotator sentinels kept as cells and counted;
- cells with NaN in a computed embedding excluded and reported;
- the **allocated** core share, never the machine's;
- required capabilities present, or `run()` is not called;
- config defaulted and type-checked;
- effects disposed, on every exit path;
- outputs written and `out.json` sealed.

Every wrapper bug in this project's history lived somewhere in that list.

---

## Why this is robust for the builder

The builder needs to answer *can this run here* without executing analysis. It reads the
declaration — never imports the plugin — so a plugin pinned to numpy 1.23 is still listable by a
host on numpy 2. `env` says what to build, `references` what to fetch, `selftest` how to prove it,
`api` whether to attempt any of it at all.

## Why this is robust for the maintainer

Everything about one plugin is in one file, so there is no second file to keep in step. The
declaration is *checked* rather than trusted: `validate` reports a drift between what the plugin
says and what it does. And the contract is not copied into the plugin, so a fix to the host's
handling of sentinels or NaN rows reaches every plugin — including ones the maintainer never
looked at.
