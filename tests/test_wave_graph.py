"""The capability graph, proved on plugin sets built for the purpose rather than on the nine.

WHAT THE SHIPPED SET PROVES ABOUT THIS MACHINERY IS ALMOST NOTHING, and that was invisible until
somebody counted. Nine plugins, five derived capabilities, and exactly ONE resolvable
plugin-to-plugin edge across the whole tree — `velocity -> pseudotime`, and it is optional.
`communication`, `activity`, `phase` and `ordering` are provided by six plugins and injected by
none. So `producer_edges`, `schedule` and `order_of_runs` — the mechanism the whole one-file
format is arranged around — were exercised by a single optional edge, and deleting one kernel
file emptied the graph and took the only proof with it.

The answer is NOT to invent a dependency between two shipped plugins so the graph looks busier.
`pseudotime` does not read a phase call; ROADMAP.md claimed it needed `cellcycle` for months, in
prose, naming a peer — the one thing a declaration may never do — and no check could see it
because a paraphrase is not comparable to anything. Writing that dependency into the declarations
to satisfy a test would put a false claim about the biology into the tool's own vocabulary.

So the mechanism is proved HERE, on sets built to have the shapes the shipped nine do not: a
required edge, a chain, a diamond, a plugin that provides what it injects, and a cycle. What the
shipped-set checks in test_portability.py assert is a different thing — facts about THIS
repository — and they stay there.

`producer_edges` was written for this. Its docstring says so: "getattr throughout: anything
presenting the kernel interface must work here, including a test stub. A graph function that only
accepts the concrete class cannot be tested apart from the plugin set it is meant to be
independent of." The affordance was built and never used.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile.kernels import producer_edges, schedule                    # noqa: E402
from scprofile.planner import order_of_runs                               # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


class Stub:
    """A plugin as the graph sees one: a name, what it provides, and what it injects.

    Deliberately NOT a `Kernel`. A stub that subclasses the concrete class proves the concrete
    class works and says nothing about the interface, which is what a third-party registry and a
    site plugin directory actually present.
    """

    def __init__(self, name, provides=(), required=(), optional=(), cost="medium", cores=1):
        self.name = name
        self.spec = {"provides": list(provides),
                     "inject": {"required": list(required), "optional": list(optional)}}
        self.needs_capabilities = list(required) + list(optional)
        self.needs_kernels = []
        self.executor = {"cost": cost, "cores": cores}
        self.per_unit = None
        self.also_cohort = None


def edges_of(*stubs):
    return producer_edges({s.name: s for s in stubs})


def waves_of(*stubs):
    """The plan's waves and the run's waves, as name lists. They must be the same waves."""
    ks = {s.name: s for s in stubs}
    plan = [sorted(w) for w in order_of_runs(sorted(ks), ks)]
    run = [sorted({i["plugin"] for i in w})
           for w in schedule(sorted(ks), ks, budget_cores=8, units=["u1"])]
    return plan, run


print("a REQUIRED edge is an edge, which the shipped set has never shown")
_p = Stub("producer", provides=["thing"])
_c = Stub("consumer", required=["thing"])
ck("the consumer depends on the producer", edges_of(_p, _c) == {"consumer": ["producer"]},
   str(edges_of(_p, _c)))
_plan, _run = waves_of(_p, _c)
ck("and the plan orders it second", _plan == [["producer"], ["consumer"]], str(_plan))
ck("and the run agrees with the plan", _plan == _run, f"plan {_plan} vs run {_run}")

print("\nan OPTIONAL edge is also an edge — the shipped set's only case")
_o = Stub("consumer", optional=["thing"])
ck("an optional input still orders the pair", edges_of(_p, _o) == {"consumer": ["producer"]},
   "an optional input that arrives after the plugin that wanted it is a missing one, quieter")

print("\na CHAIN is as many waves as it is long")
_a = Stub("a", provides=["x"])
_b = Stub("b", provides=["y"], required=["x"])
_c3 = Stub("c", required=["y"])
_plan, _run = waves_of(_a, _b, _c3)
ck("three links, three waves", _plan == [["a"], ["b"], ["c"]], str(_plan))
ck("and the run agrees", _plan == _run, f"plan {_plan} vs run {_run}")

print("\na DIAMOND waits for both providers, not the first one scheduled")
_l = Stub("left", provides=["cap"])
_r = Stub("right", provides=["cap"])
_d = Stub("down", required=["cap"])
ck("both providers are edges", edges_of(_l, _r, _d) == {"down": ["left", "right"]},
   str(edges_of(_l, _r, _d)))
_plan, _run = waves_of(_l, _r, _d)
ck("and the consumer is after both", _plan == [["left", "right"], ["down"]], str(_plan))
ck("and the run agrees", _plan == _run, f"plan {_plan} vs run {_run}")

print("\na plugin that INJECTS WHAT IT PROVIDES does not wait for itself")
# Not hypothetical: a plugin refining its own previous output is the obvious way to write one,
# and a self-edge is a deadlock that reads as a cycle in an unrelated part of the graph.
_self = Stub("solo", provides=["cap"], optional=["cap"])
ck("no self-edge", edges_of(_self) == {}, str(edges_of(_self)))
ck("and it schedules", waves_of(_self)[0] == [["solo"]], str(waves_of(_self)[0]))

print("\na REQUIRED capability nobody provides is not an ordering problem")
# It is a refusal, and it belongs to `unmet`/`available`. The graph's job is to say what waits on
# what; inventing an edge to a producer that does not exist would make the scheduler refuse work
# it could have run, in the name of a plugin that will be refused anyway.
_lonely = Stub("lonely", required=["nothing_provides_this"])
ck("no edge is invented", edges_of(_lonely) == {}, str(edges_of(_lonely)))
ck("and it is scheduled rather than dropped", waves_of(_lonely)[0] == [["lonely"]],
   str(waves_of(_lonely)[0]))

print("\na CYCLE is reported the same way by the plan and by the run")
# THE ONE SHAPE THE TWO BUILDERS DISAGREE ABOUT. `schedule` raises ValueError and
# `order_of_runs` appends the remainder and breaks, and the check that they agree runs only on
# the shipped set, which has no cycle. A user meeting this gets a plan that lists both plugins
# and a run that dies.
_x = Stub("x", provides=["p"], required=["q"])
_y = Stub("y", provides=["q"], required=["p"])
_ks = {"x": _x, "y": _y}
try:
    _plan_c = [sorted(w) for w in order_of_runs(sorted(_ks), _ks)]
    _plan_err = ""
except Exception as e:                                                    # noqa: BLE001
    _plan_c, _plan_err = None, f"{type(e).__name__}: {e}"
try:
    _run_c = [sorted({i["plugin"] for i in w})
              for w in schedule(sorted(_ks), _ks, budget_cores=8, units=["u1"])]
    _run_err = ""
except Exception as e:                                                    # noqa: BLE001
    _run_c, _run_err = None, f"{type(e).__name__}: {e}"
ck("the cycle is detected at all", _plan_c != [["x"], ["y"]] or _plan_err,
   "a cycle was ordered as if it were a chain")
ck("and the plan and the run do the same thing with it",
   bool(_plan_err) == bool(_run_err),
   f"plan {_plan_err or _plan_c} vs run {_run_err or _run_c}")

print("\n" + ("the graph holds, on shapes the shipped set does not have"
              if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
