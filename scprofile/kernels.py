"""Finding kernels, reading what they declare, and checking prerequisites BEFORE spending.

A kernel is a directory, not a python class. That is what lets one be written in R, and what stops
the host from importing anything a kernel pins.

    kernels/<name>/
        kernel.yml       what it needs, what it produces, what it cannot show
        lock.yml         the environment, captured from a working install
        references.yml   URL + sha256 + size, organism-keyed  (optional)
        run.py | run.R   the entry point
        selftest.py      proves the env works before a run is spent on it

STDLIB ONLY, including the YAML reading. `kernel.yml` is deliberately a flat, simple subset -
scalars, lists and one level of mapping - so the host needs no yaml dependency to discover what a
kernel wants. A host that could not enumerate its kernels without pyyaml installed would fail at
exactly the moment a user is trying to work out why nothing runs.
"""
from __future__ import annotations

from pathlib import Path

#: Where kernels live, relative to the package. Overridable so a site can add its own.
KERNEL_DIRNAME = "kernels"

#: The shared entrypoint, as a PATH rather than a module name. A one-file plugin is run by its own
#: interpreter, in its own pinned environment, where the host is not installed - so it cannot be
#: reached as `-m scprofile._entry`. `_entry.py` puts the host on sys.path itself.
SHARED_ENTRY = Path(__file__).resolve().parent / "_entry.py"


def _mini_yaml(text):
    """A deliberately small YAML subset: `key: value`, `key:` + `  - item`, and `#` comments.

    Not a YAML parser and does not pretend to be. It reads the files THIS project ships, and
    refuses anything it does not understand rather than guessing - a config silently
    mis-parsed is worse than one that will not load.
    """
    out, key = {}, None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith(("  - ", "- ")):
            item = line.split("- ", 1)[1].strip()
            if key is None:
                raise ValueError(f"list item with no key: {raw!r}")
            # `key:` with nothing after it stores None, which is not the same as absent - so
            # setdefault would keep the None and the isinstance check below would reject a
            # perfectly ordinary list. Promote it here.
            if out.get(key) is None:
                out[key] = []
            if not isinstance(out[key], list):
                raise ValueError(f"{key!r} has both a value and list items")
            out[key].append(_scalar(item))
            continue
        if line.startswith("  ") and ":" in line and not line.strip().startswith("- "):
            # ONE level of nested mapping, for `wraps:` and `executor:`. Deliberately one: a
            # parser that accepts arbitrary depth is a YAML parser, and this is not one. Anything
            # deeper still raises rather than being guessed at, because a config silently
            # mis-parsed is worse than one that will not load.
            if key is None:
                raise ValueError(f"indented mapping with no key: {raw!r}")
            if out.get(key) is None:
                out[key] = {}
            if not isinstance(out[key], dict):
                raise ValueError(f"{key!r} has both a value and nested keys")
            k2, _, v2 = line.strip().partition(":")
            out[key][k2.strip()] = _scalar(v2.strip()) if v2.strip() else None
            continue
        if line.startswith(" "):
            raise ValueError(f"unsupported indentation: {raw!r}")
        if ":" not in line:
            raise ValueError(f"not a key: {raw!r}")
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        out[key] = _scalar(val) if val else None
    return out


def _scalar(v):
    v = v.strip().strip('"').strip("'")
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lower() in ("null", "none", ""):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


class Kernel:
    """One kernel directory, and what it declares about itself."""

    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name
        f = self.path / "kernel.yml"
        if not f.exists():
            raise FileNotFoundError(f"{self.path} has no kernel.yml; it is not a kernel")
        self.spec = _mini_yaml(f.read_text(encoding="utf-8"))

    def _list(self, key):
        v = self.spec.get(key)
        if v is None:
            return []
        return list(v) if isinstance(v, list) else [v]

    # ---- what it declares ------------------------------------------------------------------
    @property
    def summary(self):
        return self.spec.get("summary") or ""

    @property
    def language(self):
        return (self.spec.get("language") or "python").lower()

    @property
    def entry(self):
        return self.spec.get("entry") or ("run.R" if self.language == "r" else "run.py")

    # ---- how it is LAUNCHED ----------------------------------------------------------------
    #
    # A plugin's SHAPE decides how its interpreter is invoked, so the shape answers - not the
    # runner. The runner asks a kernel for its argv and knows nothing about directories, files
    # or the shared entrypoint; a shape added later answers for itself and the runner is
    # untouched.
    def argv(self, exe, inp):
        """The command that runs this plugin. The directory shape has its own `main()`."""
        return [str(exe), str(self.path / self.entry), str(inp)]

    @property
    def has_selftest(self):
        return bool(self._selftest_file())

    def _selftest_file(self):
        for n in ("selftest.py", "selftest.R"):
            if (self.path / n).exists():
                return self.path / n
        return None

    def selftest_argv(self, exe):
        """The command that runs this plugin's selftest, or None if it ships none."""
        st = self._selftest_file()
        return [str(exe), str(st)] if st else None

    @property
    def injects_required(self):
        """The capabilities the host must supply or it will not call `run()`.

        Read here so every consumer asks the kernel rather than reaching into `spec` - the
        planner needs it as much as the entrypoint does, and reaching in is how one of them
        came to be written without it.
        """
        inj = self.spec.get("inject") or {}
        return list(inj.get("required") or []) if isinstance(inj, dict) else []

    @property
    def needs_obs(self):
        return self._list("needs_obs")

    @property
    def needs_obsm(self):
        return self._list("needs_obsm")

    @property
    def needs_layers(self):
        return self._list("needs_layers")

    @property
    def sees(self):
        """What was SHOWN to this plugin - the honest list of inputs it reads.

        Distinct from `needs_*`, which is what it REFUSES without: a plugin may read a layer it
        can also do without, and the plan still has to tell the user that it will touch it.

        Exposed here because it was declared in manifests and reachable from no code at all -
        `getattr(kernel, "sees", None)` returned None for every plugin, so the plan reported that
        cellcycle, which scores from a lognorm layer, consumed nothing.
        """
        return self._list("sees")

    @property
    def status(self):
        """`built` or `planned`. A planned plugin is a DECLARATION with no implementation.

        It exists so `plan` can answer, against a real dataset, which of the whole roadmap is
        runnable and what each would need — before any of it is written. A roadmap in prose says
        what is intended; a manifest says what it would require, and can be checked.
        """
        return self.spec.get("status", "built")

    @property
    def executor(self):
        """Scheduling hints: cost, cores, memory. Advisory — the executor plugin decides.

        A plugin that declares nothing is read PESSIMISTICALLY: medium cost, one core. An
        undeclared plugin is then under-served rather than allowed to swamp the node, which is the
        safe direction for a default nobody thought about.
        """
        e = self.spec.get("executor")
        e = dict(e) if isinstance(e, dict) else {}
        return {"cost": e.get("cost", "medium"),
                "cores": int(e.get("cores", 1) or 1),
                "memory_gb_per_100k": e.get("memory_gb_per_100k")}

    #: cost -> sort key. Longest pole first: a wave's wall-clock is its slowest member, and
    #: starting that member last adds its whole duration to the total.
    COST_ORDER = {"high": 0, "medium": 1, "low": 2, "trivial": 3}

    @property
    def per_unit(self):
        """The design unit this plugin is run once per, or None for once over the cohort.

        `per_unit: sample` is a CORRECTNESS declaration before it is a speed one. A communication
        or network inference pooled over a cohort describes the average of the conditions, which
        may describe neither — and the between-condition question needs one result per unit to
        compare. That it is also embarrassingly parallel is a consequence, not the reason.
        """
        return self.spec.get("per_unit")

    @property
    def design_aware(self):
        """True if it reports per arm without testing across the design.

        Distinct from `needs_design`, which REFUSES without one. A design-aware plugin runs fine on
        a cohort with no design and simply reports less.
        """
        return bool(self.spec.get("design_aware"))

    @property
    def can_source_layers(self):
        """This kernel can FETCH a missing layer from files beside the object.

        Velocity needs spliced/unspliced, which come from the aligner and are absent from almost
        every object that has been through QC and annotation - while the files are usually still
        on disk. A kernel that declares this is not blocked by the host's prerequisite check; it
        gets to run its own search and refuse with a report of everywhere it looked, which is
        strictly more useful than "layers absent".
        """
        return bool(self.spec.get("can_source_layers"))

    @property
    def needs_kernels(self):
        return self._list("needs_kernels")

    @property
    def needs_design(self):
        return bool(self.spec.get("needs_design"))

    @property
    def produces(self):
        return self._list("produces")

    def declared_slots(self):
        """`produces` parsed into {slot: {name}}, e.g. obs[phase] -> {"obs": {"phase"}}.

        The harness lets a skill declare `allowed-tools` and then HOLDS IT TO THAT. Here the same
        idea: `produces` stops being a comment and becomes the set the host checks a kernel's
        actual output against. A kernel that quietly starts writing a second obs column is a
        kernel whose documentation, report section and provenance have all silently gone stale.

        A TRAILING `?` marks an output only some runs produce, and is stripped here - see
        `optional_produces`.
        """
        out = {}
        for item in self.produces:
            s = str(item).strip().rstrip("?")
            if "[" in s and s.endswith("]"):
                slot, _, rest = s.partition("[")
                out.setdefault(slot.strip(), set()).add(rest[:-1].strip())
            else:
                out.setdefault("tables", set()).add(s)
        return out

    def optional_produces(self):
        """The `produces` entries marked `?`: declared, and NOT a promise for every run.

        A method with a mode produces different things in each - velocity writes `obs[latent_time]`
        only in `dynamical` mode - and until this existed the declaration had two ways to be
        wrong and no way to be right. Leave it out and every dynamical run reports an undeclared
        output; put it in and every ordinary run reports a broken promise. Drift that fires on
        correct behaviour is drift a maintainer learns to scroll past, which costs the check.

        `?` says: this is mine, its ABSENCE is not drift, and its presence is declared.
        """
        return {str(x).strip().rstrip("?") for x in self.produces if str(x).strip().endswith("?")}

    @property
    def cannot_show(self):
        """What this kernel's own result does NOT establish. Printed under its section."""
        return self._list("cannot_show")

    @property
    def when_to_use(self):
        """One line saying WHEN this kernel is the right thing to run.

        Taken from the agent-harness convention where every skill carries a description whose job
        is to let a router decide RELEVANCE without loading the skill. `doctor` prints it, and
        `applicable()` turns it into a per-dataset answer rather than a general one: a user should
        be told that velocity is irrelevant to their object because it has no unspliced layer, not
        merely that it is not installed.
        """
        return self.spec.get("when_to_use") or self.summary

    @property
    def guard(self):
        """A `guard.py` this kernel ships, or None.

        The harness pattern is a PreToolUse hook: it inspects the intended action, DENIES it, and
        names the remedy - and its escape hatch is logged rather than absent, because a gate with
        no escape gets switched off and a gate whose escapes are recorded does not.

        A kernel guard runs in the HOST, before the environment is resolved or the kernel is
        launched, and answers one question: is this dataset one where my output would mean what my
        report says it means?
        """
        g = self.path / "guard.py"
        return g if g.exists() else None

    @property
    def has_guard(self):
        return self.guard is not None

    def guard_argv(self, exe):
        """The command that asks this kernel's guard, or None if it ships none.

        THE SHAPE ANSWERS HOW IT IS LAUNCHED, exactly as `argv` and `selftest_argv` do - and this
        one did not exist, so `guard_verdict` reached for `kernel.path / "guard.py"` directly. For
        a ONE-FILE plugin that path is inside a file and can never exist, which means converting a
        guarded plugin to the shape this host prefers SILENTLY DROPPED ITS GUARD: no error, no
        line in the log, and the first dataset the guard existed to refuse would have been
        analysed and reported.
        """
        g = self.guard
        return [str(exe), str(g)] if g else None

    @property
    def needs_env(self):
        """False for a kernel that runs in the host's own interpreter (e.g. cheap ones)."""
        return self.spec.get("needs_env", True)

    def references(self, organism=None):
        """{name: {url, sha256, size, organism}} for this kernel, filtered by organism."""
        # DECLARED IN THE PLUGIN FIRST. A one-file plugin carries its references in PLUGIN, and
        # this read only `references.yml` - so a one-file plugin's references were INVISIBLE:
        # `reference_organisms()` came back empty, `require_supported` passed, and scenic would
        # have run with no cisTarget rankings at all. Nothing is pruned then, every co-expression
        # module survives, and the regulons are raw correlation wearing a regulon's name. A full
        # result file, and wrong - which is the exact failure that plugin's own docstring names.
        inline = (self.spec or {}).get("references")
        if isinstance(inline, dict) and inline:
            out = {k: dict(v) for k, v in inline.items() if isinstance(v, dict)}
            if organism:
                out = {k: v for k, v in out.items()
                       if not v.get("organism")
                       or str(v["organism"]).lower() == str(organism).lower()}
            return out

        f = self.path / "references.yml"
        if not f.exists():
            return {}
        flat = _mini_yaml(f.read_text(encoding="utf-8"))
        out, cur = {}, None
        for k, v in flat.items():
            # Two shapes, because `_mini_yaml` gained one level of nesting after this was written
            # and silently stopped producing the older one. The regression was invisible: a
            # references.yml that parsed to NOTHING gave a plugin zero declared references, and
            # `resolve()` then found nothing missing and passed. A plugin would have run with no
            # reference data at all and reported success.
            if isinstance(v, dict):
                out[k] = dict(v)
                cur = None
            elif v is None:
                cur = k
                out[cur] = {}
            elif cur:
                out[cur][k] = v
        if organism:
            out = {k: v for k, v in out.items()
                   if not v.get("organism") or str(v["organism"]).lower() == organism.lower()}
        return out

    def reference_organisms(self):
        """Every organism this plugin declares reference data for. Empty if it needs none.

        The set matters because an organism ABSENT from it is not "a plugin that needs no
        references" - it is a plugin whose references nobody has declared for that species, and
        the two were indistinguishable. `references(organism)` filters by organism and returns {},
        the host read that as "nothing required" and skipped the check, and the plugin ran with no
        reference data at all. For scenic that means cisTarget prunes nothing and the regulons are
        raw co-expression wearing a regulon's name: a full result file, and wrong.
        """
        out = set()
        for spec in self.references(None).values():
            o = spec.get("organism")
            if o:
                out.add(str(o).lower())
        return out

    def __repr__(self):
        return f"<Kernel {self.name}>"


class FileKernel(Kernel):
    """A plugin that is ONE FILE: a PLUGIN dict and a run(ctx). Nothing else is required.

    The declaration is read WITHOUT importing the module, so discovery never executes plugin code
    and never needs the plugin's own environment - a plugin pinned to numpy 1.23 must still be
    listable by a host running numpy 2.
    """

    def __init__(self, path):
        import ast
        self.path = path
        self.name = path.stem
        self.spec = {}
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            return
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    getattr(tgt, "id", "") == "PLUGIN" for tgt in node.targets):
                try:
                    self.spec = ast.literal_eval(node.value)
                except ValueError:
                    self.spec = {}
        # `needs` is one mapping here rather than four keys, because a plugin author should write
        # what it needs in one place. Flattened to the names the rest of the host already uses.
        needs = self.spec.get("needs") or {}
        for role in ("obs", "obsm", "layers", "kernels"):
            if needs.get(role):
                self.spec[f"needs_{role}"] = needs[role]
        if needs.get("design"):
            self.spec["needs_design"] = True
        # EITHER SHAPE MEANS IT NEEDS AN ENVIRONMENT. This read `env` alone, so the moment a
        # plugin moved to the resolvable `requires` shape the host decided it needed no
        # environment at all and reported it as running in the host interpreter - a plugin
        # pinned to numpy 1.26 declared ready on a host running numpy 2.
        self.spec.setdefault("needs_env",
                             bool(self.spec.get("env") or self.spec.get("requires")))
        self.spec.setdefault("language", "python")
        self.spec.setdefault("status", "built" if self.spec else "planned")
        self.spec.setdefault("executor", {"cost": self.spec.get("cost", "medium"),
                                          "cores": self.spec.get("cores", 1)})

    @property
    def entry(self):
        """The file itself. The host runs it through scprofile._entry, never directly."""
        return self.path

    # THE SHARED ENTRYPOINT IS THE WHOLE POINT OF THIS SHAPE. A one-file plugin is a PLUGIN dict
    # and a `run(ctx)`; it has no `main()`, no argument parsing and no manifest handling, because
    # `_entry.py` does all of that once for every plugin that will ever exist. Handing the file
    # straight to an interpreter therefore does not fail - it DEFINES two names, exits 0 and
    # writes nothing, which the host can only report as a missing out.json. That is what happened
    # to the first third-party plugin to reach a real run.
    #
    # `_entry.py` is invoked BY PATH rather than as `-m scprofile._entry`, because the
    # interpreter running it is the PLUGIN'S, in the plugin's own pinned environment, where the
    # host is not installed and must not have to be. `_entry.py` puts the host on its own
    # sys.path as its first act.
    def argv(self, exe, inp):
        return [str(exe), str(SHARED_ENTRY), str(self.path), str(inp)]

    @property
    def has_selftest(self):
        """Read from the SOURCE, not from a neighbouring file - there is no neighbouring file.

        `selftest` used to be looked for at `kernel.path / "selftest.py"`. For this shape
        `kernel.path` is the plugin itself, so that test could never be true and every one-file
        plugin was reported as shipping no selftest - by name, in a list headed `not considered`,
        which reads exactly like a plugin that was checked.
        """
        try:
            return "def selftest(" in self.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False

    def selftest_argv(self, exe):
        return [str(exe), str(SHARED_ENTRY), "--selftest", str(self.path)] if self.has_selftest \
            else None

    @property
    def guard(self):
        """There is no neighbouring `guard.py`; a one-file plugin's guard is a `guard(g)` in it."""
        return self.path if self.has_guard else None

    @property
    def has_guard(self):
        try:
            return "def guard(" in self.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False

    def guard_argv(self, exe):
        """Run through the shared entrypoint, in the HOST's interpreter.

        The host's, deliberately: a guard runs BEFORE the environment is resolved, and one of the
        things it can say is that resolving it is not worth doing. `_entry.py` imports the plugin
        module and calls `guard(g)` - which is why module scope in a plugin must stay importable
        by the host, with every third-party import inside a function.
        """
        return [str(exe), str(SHARED_ENTRY), "--guard", str(self.path)] if self.has_guard else None


def discover(root=None):
    """Every kernel that ships with the host, plus any under $SCPROFILE_KERNELS."""
    import os
    roots = []
    r = Path(root) if root else Path(__file__).resolve().parent.parent / KERNEL_DIRNAME
    roots.append(r)
    extra = os.environ.get("SCPROFILE_KERNELS")
    if extra:
        roots += [Path(p) for p in extra.split(os.pathsep) if p]
    found, shadowed = {}, []
    for base in roots:
        if not base.is_dir():
            continue
        # A PLUGIN IS ONE FILE. `kernels/myplugin.py` carrying a PLUGIN dict and a run(ctx) is
        # the whole installation - see scprofile/plugin.py. The six-file directory shape below
        # still loads, because nothing that worked should stop working; but it is the old shape,
        # and a plugin host whose plugins take six files to declare is an assembly kit.
        for f in sorted(base.glob("*.py")):
            if f.name.startswith("_"):
                continue
            k = FileKernel(f)
            if k.name in found:
                shadowed.append((k.name, str(found[k.name].path), str(f)))
            found[k.name] = k
        for d in sorted(base.iterdir()):
            if d.is_dir() and (d / "kernel.yml").exists():
                if d.name in found:
                    # A site kernel overriding a shipped one is legitimate and is the reason
                    # $SCPROFILE_KERNELS exists. Doing it SILENTLY is not: a run would use code
                    # from a directory nobody mentioned. Recorded, and doctor prints it.
                    shadowed.append((d.name, str(found[d.name].path), str(d)))
                found[d.name] = Kernel(d)
    discover.shadowed = shadowed
    return found


#: Populated by the last `discover()`: [(name, shadowed_path, winning_path)].
discover.shadowed = []


def order(names, available):
    """Kernels sorted so a prerequisite runs before what needs it. Refuses a cycle by name."""
    todo, done, out = list(names), set(), []
    guard = 0
    while todo:
        guard += 1
        if guard > len(names) * len(names) + 10:
            raise ValueError(f"cannot order {names}: a needs_kernels cycle among {todo}")
        n = todo.pop(0)
        k = available.get(n)
        pend = [d for d in (k.needs_kernels if k else []) if d in names and d not in done]
        if pend:
            todo.append(n)
            continue
        out.append(n)
        done.add(n)
    return out


def schedule(names, available, *, budget_cores=1, units=None):
    """The run plan: waves of plugin instances, cost-ordered, with a core share for each.

    A WAVE IS NOT A BARRIER UNLESS THE GRAPH SAYS SO. Waves are computed from `needs_kernels`, so
    a plugin waits only on what it actually depends on — not on whatever else happened to be
    scheduled beside it. `pseudotime` waits on `cellcycle` and must not wait on `scenic`.

    Returns [[instance, ...], ...] where an instance is
    {"plugin": name, "unit": <value or None>, "cores": int}.
    """
    remaining, done, waves = list(names), set(), []
    guard = 0
    while remaining:
        guard += 1
        if guard > len(names) + 2:
            raise ValueError(f"cannot schedule {remaining}: a needs_kernels cycle")
        ready = [n for n in remaining
                 if all(d in done or d not in names
                        for d in (available[n].needs_kernels if n in available else []))]
        if not ready:
            raise ValueError(f"cannot schedule {remaining}: a needs_kernels cycle")

        # longest pole first, then by declared cores, then by name so a plan is reproducible
        ready.sort(key=lambda n: (Kernel.COST_ORDER.get(available[n].executor["cost"], 1),
                                  -available[n].executor["cores"], n))
        wave = []
        for n in ready:
            k = available[n]
            us = list(units or []) if k.per_unit else [None]
            for u in (us or [None]):
                wave.append({"plugin": n, "unit": u, "cores": k.executor["cores"]})
        waves.append(_budget(wave, budget_cores))
        done.update(ready)
        remaining = [n for n in remaining if n not in done]
    return waves


def _budget(wave, budget):
    """Divide the core budget across a wave's instances. No instance gets more than the budget.

    A plugin reading `os.cpu_count()` inside itself is a bug: it reports the NODE, not its share,
    and four concurrent plugins each doing it start four times the node's cores in threads. The
    share is passed in `in.json` and the plugin is required to use it.

    IDEMPOTENT, and it has to be, because it is applied twice: once when the plan is computed and
    again over the instances that survive a wave's filters. Scaling the ALREADY-SCALED number the
    second time compounded - a six-instance wave in which nothing was filtered out went from a
    planned velocity(2c) to a run velocity(1c), so the fix for over-division became an
    under-division whenever the filters removed nothing. Every division is from `declared`.
    """
    if not wave:
        return wave
    for i in wave:
        i.setdefault("declared", i["cores"])
    want = sum(i["declared"] for i in wave)
    for i in wave:
        i["cores"] = (i["declared"] if want <= budget
                      else max(1, min(budget, int(i["declared"] * budget / want))))
    return wave


def concurrency(instances, budget):
    """How many instances of a wave may run AT ONCE. `min(budget / smallest declared, ready)`.

    `docs/EXECUTION.md` §4 has stated this rule since it was written, and nothing implemented it:
    the runner started every instance of a wave at once, however many there were. `_budget` divides
    the CORE SHARE each instance is told to use, which is a different thing from how many of them
    exist - so a wave that is larger than the budget was scaled to one core each and then all
    launched together.

    Measured on the shipped set, ten samples and an eight-core allocation: nine plugins, three of
    them `per_unit`, is 35 instances. Thirty-five subprocesses, each opening a 3 GB object, on a
    node that was asked for eight cores. Every one of them is correctly told `cores: 1` and the
    node still runs thirty-five of them, which is the oversubscription the share exists to prevent
    wearing the other hat - and the memory failure it causes looks like the plugin's fault.

    The SMALLEST DECLARED, not the smallest scaled: a wave of cheap plugins should fill the budget,
    and scaling has already flattened everything to 1 by the time it is oversubscribed. A plugin
    declaring more than the whole budget runs alone, at the budget, rather than being refused.
    """
    if not instances:
        return 1
    smallest = max(1, min(int(i.get("declared", i.get("cores", 1)) or 1) for i in instances))
    return max(1, min(len(instances), int(budget) // smallest))


def resolve_keys(items, keys):
    """Substitute `{label}`, `{counts}` and the rest through the key map.

    The plugin format REQUIRES a plugin to name keys rather than columns — a plugin naming a real
    column has bound itself to one project. So every consumer of `needs` must resolve them, and
    this one did not: it checked for a column literally called `{label}`, which no object has.

    Every correctly-written plugin therefore failed its own prerequisite check, and the failure
    read as a property of the dataset rather than of the resolver.

    An unresolvable key is returned UNCHANGED so it surfaces as a missing capability naming the
    key, rather than being silently dropped.
    """
    out = []
    for it in items:
        s = str(it)
        for k, v in (keys or {}).items():
            if v:
                s = s.replace("{" + k + "}", str(v))
        out.append(s)
    return out


def unmet(kernel, *, obs=(), obsm=(), layers=(), ran=(), has_design=False, keys=None,
          organism=None, var=(), derived=()):
    """Everything `kernel` needs and does not have. One line per problem, each with its FIX.

    Checked before the kernel is launched. A prerequisite discovered inside a kernel is a
    prerequisite discovered after the environment was resolved and the object was read.
    """
    from . import declare as _D
    problems = []
    # REQUIRED CAPABILITIES, which the host resolves and the plugin therefore never checks. The
    # entrypoint refuses without them; until this existed, nothing upstream of the run knew - so
    # the plan said RUN and the refusal arrived an hour later, in a queue.
    for cap in (kernel.injects_required or []):
        if _D.available(cap, keys=keys, obs=obs, obsm=obsm, layers=layers, var=var,
                        has_design=has_design, organism=organism, derived=derived):
            continue
        why = (_D.CAPABILITIES.get(cap) or {}).get("why", "the host cannot resolve it here")
        how = (_D.CAPABILITIES.get(cap) or {}).get("resolve", "data")
        fix = {"data": f"name it with a --{cap}-key style flag, or run whatever writes it",
               "design": "pass --design",
               "derived": f"run a plugin that provides {cap!r} first"}.get(how, "")
        problems.append(f"capability {cap!r} is not available: {why}.  Fix: {fix}.")
    for c in resolve_keys(kernel.needs_obs, keys):
        if c not in obs:
            who = _who_produces(f"obs[{c}]")
            problems.append(f"obs[{c!r}] is absent." + (f"  Fix: run --kernel {who} first." if who
                                                        else "  It must be on the input object."))
    for c in resolve_keys(kernel.needs_obsm, keys):
        if c not in obsm:
            problems.append(f"obsm[{c!r}] is absent.  Fix: pass --embedding to name the one to "
                            f"use, or run the integration step that writes it.")
    for c in resolve_keys(kernel.needs_layers, keys):
        if c not in layers and kernel.can_source_layers:
            continue          # the kernel searches for it and reports what it found
        if c not in layers:
            problems.append(
                f"layers[{c!r}] is absent.  Fix: this kernel cannot run on this dataset. "
                f"{'Spliced/unspliced counts come from the aligner and cannot be derived later.' if c in ('spliced', 'unspliced') else ''}")
    for d in kernel.needs_kernels:
        if d not in ran:
            problems.append(f"kernel {d!r} has not been run.  Fix: --kernel {d} first, or "
                            f"--kernel {d},{kernel.name}.")
    if kernel.needs_design and not has_design:
        problems.append("no --design was given.  Fix: pass a CSV keyed on the sample column. "
                        "Without it there is no contrast to test.")
    return problems


def undeclared(kernel, payload):
    """What a kernel WROTE that it never declared it produces.

    Not fatal - a kernel may legitimately gain an output before its declaration is updated, and
    refusing the run would punish the user for the author's oversight. But it is reported at every
    level: on the console, in the kernel's report page, and in the provenance. An undeclared output
    is one that no `cannot_show` covers and no documentation mentions.
    """
    import fnmatch
    want = kernel.declared_slots()
    extra = []
    for slot in ("obs", "obsm", "layers", "objects"):
        pats = want.get(slot, set())
        for name in sorted((payload.get(slot) or {}).keys()):
            # Glob, because some outputs are named after a runtime choice. velocity writes
            # `obsm[velocity_<basis>]` and the basis is whichever embedding the object turned out
            # to carry - so `velocity_*` is the honest declaration and enumerating every possible
            # embedding name would be a declaration that goes stale the first time somebody adds
            # one. A pattern still HOLDS the kernel to a shape; it just does not pretend to know
            # the suffix in advance.
            if not any(fnmatch.fnmatchcase(name, pat) for pat in pats):
                extra.append(f"{slot}[{name}]")
    return extra


def guard_verdict(kernel, *, describe, constraint, params, log=print):
    """Run a kernel's own guard, if it ships one. Returns (allow, reason, escape_flag).

    The guard is given what the host knows about the dataset and answers whether this kernel's
    output would MEAN what its report says. It is not a prerequisite check - those are structural
    and live in `unmet()`. A guard is about interpretability: an abundance test on a design whose
    factor is nested in the batch key runs perfectly and returns p-values for a contrast that is
    not identifiable.
    """
    import json
    import subprocess
    import sys
    argv = (kernel.guard_argv(sys.executable) if hasattr(kernel, "guard_argv")
            else ([sys.executable, str(kernel.guard)] if getattr(kernel, "guard", None) else None))
    if not argv:
        return True, "", ""
    payload = json.dumps({"describe": describe, "constraint": constraint,
                          "params": dict(params or {})})
    r = subprocess.run(argv, input=payload, capture_output=True, text=True)
    if r.returncode == 0:
        return True, (r.stdout or "").strip(), ""
    reason = (r.stdout or "") + (r.stderr or "")
    return False, reason.strip(), f"--allow {kernel.name}"


def log_escape(path, kernel_name, reason, who=""):
    """Append a guard override to the escape log. The harness's lesson, verbatim:

    a gate with no escape gets switched off; a gate whose escapes are all recorded does not.
    """
    import datetime
    import json
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "when": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "kernel": kernel_name, "overridden_reason": reason, "by": who}) + "\n")
    return p


#: Which kernel writes which cell-level column, so an unmet prerequisite can name its own fix
#: instead of leaving the user to work out where `phase` was supposed to come from.
_PRODUCERS = {
    "obs[phase]": "cellcycle",
    "obs[S_score]": "cellcycle",
    "obs[G2M_score]": "cellcycle",
    "obs[pseudotime]": "pseudotime",
    "obs[velocity_confidence]": "velocity",
    "obs[velocity_pseudotime]": "velocity",
}


def _who_produces(slot):
    return _PRODUCERS.get(slot)
