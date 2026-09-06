"""Makes this directory a REGULAR package, and that is load-bearing rather than tidy.

`test_loop_driver.py` does `importlib.import_module("tests.loop_stations")`. Without this file,
`tests` is a namespace package, and Python resolves namespace packages last: the import machinery
records a directory without `__init__.py` as a portion and KEEPS SCANNING, so any regular
top-level `tests` package installed anywhere on the path wins - even one that appears later than
this repository's own root.

That is not hypothetical. In the environment this tool runs in on the cluster, a dependency ships
`site-packages/tests/__init__.py`, so `tests.loop_stations` resolved into that package and raised
ModuleNotFoundError while the file sat one directory away. The suite reported four failures that
had nothing to do with the code, and it did so ONLY in that environment - the same commit is
green wherever no package happens to have claimed the name. Found on 2026-09-06 by running the
suite through `sch dev check` on the cluster rather than on a workstation.

An empty file would have the same effect. This one explains itself so that nobody deletes it for
being empty.
"""
