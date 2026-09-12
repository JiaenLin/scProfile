"""WHICH PLUGIN A TEST IS ABOUT, and what to do when that plugin is not installed.

MEASURED BEFORE IT WAS FIXED, and the measurement corrected the diagnosis. Deleting each shipped
kernel in turn and counting red suites gave: abundance 0, pseudotime 1, de and liana 2, scenic and
velocity 3, cellcycle and decoupler 4 - and cellchat EIGHTEEN of sixty-six. Eight of those opened
with `(ROOT / "kernels" / "cellchat.py").read_text()`, which reads like the coupling to remove.

IT IS NOT. Those suites check things like `saveRDS(cc, rds_tmp)` being guarded by a cache flag,
and `rows$stratum_role == "against"` selecting a stratum by its declared role rather than by
position. Those are assertions about ONE plugin's R implementation, and generalising them over
"every plugin that embeds R" would be worse than the name: the second R wrapper will have a
different cache and a different frame, both perfectly correct, and would fail checks written
against somebody else's internals.

So the name stays and the CRASH goes. A suite whose subject is absent was raising
FileNotFoundError - which reads in a summary exactly like the plugin being broken, and which is
what made one deleted file look like eighteen defects. "This plugin is not installed here" and
"this plugin is wrong" are different findings, and only the second is a defect. The same
distinction, learned separately in `sch dev` as applicable-versus-unavailable, and the same
reason: an exit code that means two things is read as neither.

WHAT IS SHARED IS THE DETECTOR, not the subject. `r_scripts()` is one implementation of "find the
R a plugin embeds", used by the lint suites that legitimately run over every plugin.
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NotInstalled(Exception):
    """The plugin a test is about is not in this repository. NOT A DEFECT, and not an error.

    Raised rather than returned so a per-test runner can tell it from a failure. The runners in
    these files caught AssertionError only, so a missing plugin file escaped as FileNotFoundError
    and took the whole suite with it - including the tests in the same file that never needed the
    plugin at all. One deleted kernel read as eighteen broken suites largely this way.
    """


def spec(name, about):
    """The plugin's PLUGIN declaration, or raise NotInstalled."""
    import importlib.util
    f = ROOT / "kernels" / f"{name}.py"
    if not f.is_file():
        raise NotInstalled(f"`{name}` is not installed here, so {about} is not checked")
    sp = importlib.util.spec_from_file_location(name, f)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m.PLUGIN


def kernel(name, about, registry=None):
    """One discovered kernel, or raise NotInstalled. `discover()[name]` raises KeyError.

    A KeyError reads in a summary as a bug in the discovery code. It is not: the plugin this test
    is about is not in this checkout, which is a fact and not a fault.
    """
    if registry is None:
        from scprofile.kernels import discover
        registry = discover()
    if name not in registry:
        raise NotInstalled(f"`{name}` is not installed here, so {about} is not checked")
    return registry[name]


def source(name, about):
    """The plugin's Python source, or print why this suite has nothing to do and EXIT ZERO.

    `about` completes "this suite checks ...", so the skip line says what is not being checked
    rather than only which file is missing. A skip nobody can read is a pass.
    """
    f = ROOT / "kernels" / f"{name}.py"
    try:
        return f.read_text(encoding="utf-8")
    except OSError:
        print(f"skipped - `{name}` is not installed in this repository, so {about} is not "
              f"checked here. Not a defect: this suite is about that plugin's own "
              f"implementation, and it runs again wherever the plugin does")
        sys.exit(0)


def companions(name):
    """[(filename, text)] for the GENERATED R a plugin keeps beside itself.

    NAMED FOR ITS PLUGIN. Nine one-file kernels share one `kernels/` directory, so a companion
    is `kernels/<name>.draw.R` and never a bare `draw.R` that would answer for all nine.
    """
    out = []
    for f in sorted((ROOT / "kernels").glob(f"{name}.*.R")):
        try:
            out.append((f.name, f.read_text(encoding="utf-8")))
        except OSError:
            continue
    return out


def r_as_run(name, about):
    """[(attribute, script)] for every embedded R script, WITH the generated protocol prepended.

    THE TEXT THAT RUNS, WHICH IS NOT THE TEXT IN THE PYTHON FILE. A plugin that draws through R
    is handed a generated companion - the ceilings, the colour map, the caption file and both
    draw wrappers - prepended to each of its embedded scripts, so ONE definition serves all of
    them. Three suites here grepped the Python constant alone and went red the day that
    consolidation happened: each was asserting a property of the running script and reading half
    of it. Reading half of a script is how a check comes to be measuring the spelling.
    """
    pre = "".join(t for _f, t in companions(name))
    # WHICH SCRIPTS ACTUALLY GET IT, read from the plugin rather than assumed. Not every embedded
    # script draws: a probe that reads a database and writes a table is handed no wrapper, and
    # prepending one here would let a suite check a script assembled in a way that never happens.
    py = source(name, about)
    out = []
    for who, attr, rsrc in r_scripts():
        if who != name:
            continue
        # PREPENDED BY THE PLUGIN (`_draw_r() + _R_RUN`) OR BY THE HOST (`ctx.rscript(_R_RUN,
        # ...)`, harness ADR-0016 step 4): either way the script that runs begins with the
        # companion, and a suite reading the constant alone reads half of it.
        prepended = bool(re.search(r"\+\s*" + re.escape(attr) + r"\b", py)
                         or re.search(re.escape(attr) + r"\s*\+", py)
                         or re.search(r"\.rscript\(\s*" + re.escape(attr) + r"\b", py))
        out.append((attr, (pre if prepended else "") + rsrc))
    if not out:
        print(f"skipped - `{name}` holds no embedded R here, so {about} is not checked")
        sys.exit(0)
    return out


def _modules():
    """[(name, module)] for every kernel file that imports. Unimportable ones are skipped.

    A plugin whose module scope raises is a real defect and it is `test_declaration.py`'s to
    report; a subject-selection helper that raised here would turn one broken plugin into every
    suite failing with the same unrelated traceback.
    """
    out = []
    for f in sorted((ROOT / "kernels").glob("*.py")):
        sp = importlib.util.spec_from_file_location(f.stem, f)
        m = importlib.util.module_from_spec(sp)
        try:
            sp.loader.exec_module(m)
        except Exception:                                             # noqa: BLE001
            continue
        out.append((f.stem, m))
    return out


def r_scripts():
    """[(plugin, attribute, r_source)] for every R string a shipped plugin holds.

    A plugin's R is a string in a Python file, so nothing about it is checked by importing it.
    The three conditions together are what tells an R script from a docstring that mentions R.
    """
    out = []
    for name, m in _modules():
        for attr in dir(m):
            v = getattr(m, attr)
            if not isinstance(v, str) or len(v) < 200:
                continue
            if "library(" in v and ("<-" in v or "function(" in v):
                out.append((name, attr, v))
    return out


def nothing_found(marker, what):
    """A detector found nothing. Is the tree empty, or has the detector stopped matching?

    ("absent", sentence) or ("broken", sentence). FIVE SUITES ASSERTED THE SECOND AND PRINTED IT
    AS THE FIRST: "no plugin declares provides_evidence; this check proved nothing", "no plugin
    uses ctx.cache", "no plot call was found in any plugin", "no embedded R script with positional
    arguments", "no R script located in any plugin; the detector is not looking correctly". Every
    one of them fired when a single plugin was removed, and every one reported it as a fault in
    the checking rather than as a repository with nothing of that kind in it.

    The guards are right to exist - a check that silently proves nothing is worse than no check.
    They were wrong that a vacuous run has only one cause. `marker` is the crude, independent
    question: does the raw text of any kernel contain this at all? Deliberately cruder than the
    detector it audits, because a second signal sharing the first's conditions fails in the same
    direction and confirms nothing.
    """
    present = [f.stem for f in sorted((ROOT / "kernels").glob("*.py"))
               if marker in f.read_text(encoding="utf-8", errors="ignore")]
    if present:
        return ("broken", f"{', '.join(present)} contain {marker!r} and the detector found "
                          f"nothing, so it has stopped matching and every check below is "
                          f"vacuously green")
    return ("absent", f"no plugin here {what}, so there is nothing for this to check. Not a "
                      f"defect - it runs again the day one arrives")


def any_kernel_embeds_r():
    """A SECOND, INDEPENDENT SIGNAL, so "found nothing" can be told from "looked wrongly".

    `r_scripts()` needs a string over 200 characters holding `library(` and either `<-` or
    `function(` - three conditions, any of which a real script could one day miss. When it returns
    nothing, the guard that says so cannot tell a repository with no R plugin from a detector that
    has stopped matching, and it asserted the second: "the detector is not looking correctly",
    printed on a tree whose only R plugin had simply been removed.

    This asks the cruder question - does any kernel file contain `library(` at all - and the two
    answers together are decisive. Crude on purpose: a signal that shared the real detector's
    conditions would fail in the same direction and confirm nothing.
    """
    return any("library(" in f.read_text(encoding="utf-8", errors="ignore")
               for f in (ROOT / "kernels").glob("*.py"))
