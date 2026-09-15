"""Every name a plugin's Python loads is bound: a parameter, a local, a module global, an import,
or a builtin (harness ADR-0026, K-s, found by run F).

A one-line change to a panel function named `Path`, which the module never imports; the
validator, the suites and the maker's status all passed, and eighteen units each spent five
minutes inferring before the NameError. Python's own compiler does not check names; this does
the pyflakes half that matters here - free names in function bodies against what the function,
its enclosing functions, the module and the builtins bind - and names the function and the line.
Comprehension and lambda scopes, `global`/`nonlocal`, and names bound by `with`, `for`,
`except`, `import` and assignment all count as bound.

Run: python tests/test_a_plugin_names_only_what_it_binds.py
"""
import ast
import builtins
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def _targets(node):
    """The names a target expression binds."""
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        return set().union(*(_targets(e) for e in node.elts))
    if isinstance(node, ast.Starred):
        return _targets(node.value)
    return set()


def _bound_in(body_nodes):
    """Names bound anywhere in a list of statements, not descending into nested functions or
    classes (their bindings are their own - a `from pathlib import Path` inside one function
    binds nothing for another)."""
    out = set()

    def stmt_names(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
            return                                  # its body is its own scope
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                out.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                out.update(_targets(t))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            out.update(_targets(node.target))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    out.update(_targets(item.optional_vars))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            out.update(node.names)
        # walrus targets anywhere in this statement's expressions
        for sub in ast.walk(node):
            if isinstance(sub, ast.NamedExpr):
                out.update(_targets(sub.target))
        for attr in ("body", "orelse", "finalbody", "handlers"):
            for child in getattr(node, attr, None) or []:
                stmt_names(child)

    for stmt in body_nodes:
        stmt_names(stmt)
    return out


def _params(args):
    out = set()
    for p in args.posonlyargs + args.args + args.kwonlyargs:
        out.add(p.arg)
    if args.vararg:
        out.add(args.vararg.arg)
    if args.kwarg:
        out.add(args.kwarg.arg)
    return out


def unbound_names(src):
    """[(function, line, name)] for every name loaded in a function body that nothing binds:
    a scope walk - a function's scope is its parameters and what its body binds over the
    enclosing scopes; a lambda's is its parameters; a comprehension's is its targets."""
    tree = ast.parse(src)
    module_bound = _bound_in(tree.body) | set(dir(builtins)) | {"__file__", "__name__", "__doc__"}
    out = []

    def visit(node, scope, fn_name):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inner = scope | _params(node.args) | _bound_in(node.body)
            for d in node.args.defaults + node.args.kw_defaults + node.decorator_list:
                if d is not None:
                    visit(d, scope, fn_name)
            for stmt in node.body:
                visit(stmt, inner, node.name)
            return
        if isinstance(node, ast.Lambda):
            inner = scope | _params(node.args)
            visit(node.body, inner, fn_name)
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            inner = set(scope)
            for gen in node.generators:
                visit(gen.iter, inner, fn_name)
                inner |= _targets(gen.target)
                for cond in gen.ifs:
                    visit(cond, inner, fn_name)
            for elt in ([node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]):
                visit(elt, inner, fn_name)
            return
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                visit(stmt, scope | {node.name}, fn_name)
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in scope and fn_name is not None:
                out.append((fn_name, node.lineno, node.id))
            return
        for child in ast.iter_child_nodes(node):
            visit(child, scope, fn_name)

    for stmt in tree.body:
        visit(stmt, module_bound, None)
    seen, uniq = set(), []
    for fn, ln, nm in out:
        if (ln, nm) not in seen:
            seen.add((ln, nm))
            uniq.append((fn, ln, nm))
    return uniq


print("the check itself")
ck("an unimported name in a function is named, with its line",
   unbound_names("def f(x):\n    return Path(x)\n") == [("f", 2, "Path")], str(unbound_names("def f(x):\n    return Path(x)\n")))
ck("an import, a parameter, a local, a loop variable and a builtin all bind",
   unbound_names("from pathlib import Path\nG = 1\ndef f(x):\n    y = 2\n    for i in x:\n        pass\n    return Path(x), y, i, G, len\n") == [])
ck("a nested function sees its enclosing scope; a comprehension binds its own",
   unbound_names("def f(x):\n    def g():\n        return x\n    return [k for k in x], g\n") == [])
ck("a nested function's parameter, a lambda's parameter and a default bind",
   unbound_names("def f(x):\n    def g(mat, n_run=2):\n        return mat, n_run\n    return sorted(x, key=lambda kv: kv[1]), g\n") == [],
   str(unbound_names("def f(x):\n    def g(mat, n_run=2):\n        return mat, n_run\n    return sorted(x, key=lambda kv: kv[1]), g\n")))
ck("an import inside one function binds nothing for another",
   unbound_names("def g():\n    from pathlib import Path\n    return Path\ndef f(x):\n    return Path(x)\n") == [("f", 5, "Path")],
   str(unbound_names("def g():\n    from pathlib import Path\n    return Path\ndef f(x):\n    return Path(x)\n")))
ck("an except name and a with name bind",
   unbound_names("def f(x):\n    try:\n        pass\n    except ValueError as e:\n        return e\n    with open(x) as fh:\n        return fh\n") == [])

print("\nevery shipped plugin names only what it binds")
from scprofile import kernels as K                                              # noqa: E402
n = 0
for name, k in sorted(K.discover().items()):
    src = Path(k.path).read_text(encoding="utf-8")
    bad = unbound_names(src)
    n += 1
    ck(f"{name}: no free name in any function", not bad,
       "; ".join(f"{fn}:{ln} {nm}" for fn, ln, nm in bad[:6]))
ck("at least one plugin was checked", n >= 1)

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\na plugin names only what it binds")
