"""A run says whether it finished, and cannot say so falsely.

A directory of outputs looks the same whether the job walked to the end or was killed at hour
eleven of a twelve-hour walltime, and the difference is not recoverable afterwards. Anything
reading these directories later - a reuse layer deciding what to adopt, a loop station deciding
whether a defect is real - is otherwise reading partial runs as complete ones.

These are structural checks on the job template. They do not run a scheduler; what they defend
is the ordering, which is where this went wrong: a trap installed after the work covers only the
exit it was already going to reach, which is the one case that needed no trap.
"""
from pathlib import Path

PBS = Path(__file__).resolve().parents[1] / "setup" / "dev_cycle.pbs"


def _src():
    return PBS.read_text()


def test_the_template_seals_at_all():
    s = _src()
    assert "SEALED.txt" in s, "a completed run writes nothing to say it completed"
    assert "FAILED.txt" in s, "a run that stops early writes nothing to say it stopped"


def test_the_trap_is_registered_before_the_work():
    """The ordering IS the mechanism."""
    s = _src()
    trap = s.index("trap _seal EXIT")
    work = s.index('case "${PHASE}" in')
    assert trap < work, (
        "the seal trap is registered after the work begins, so it covers only a clean exit - "
        "the ways a job ends without reaching its last line are the ones it exists for")


def test_a_kill_is_recorded_rather_than_silent():
    s = _src()
    assert "TERM" in s, "a walltime kill sends SIGTERM; without a handler nothing is written"


def test_a_seal_needs_more_than_an_exit_status():
    """`$?` alone sealed a job that had failed, so it is not trusted alone."""
    s = _src()
    assert "_DONE" in s, "nothing records that the script reached its last line"
    seal = s.index("_seal() {")
    done = s.rindex("_DONE=1")
    assert done > seal, "the completion flag is set before the work it is meant to attest"
    assert s.index('[ -n "$_DONE" ]', seal) > seal, (
        "the trap does not consult the completion flag, so it seals on exit status alone")


def test_the_two_disagree_only_in_the_safe_direction():
    """A false FAILED costs a re-run; a false SEALED corrupts everything downstream."""
    s = _src()
    i = s.index('[ -n "$_DONE" ] || _rc=')
    line = s[i:s.index("\n", i)]
    assert "99" in line, (
        "reaching the end is not required for a zero status to seal; an unfinished run with a "
        "zero status would be sealed as complete")


def test_every_documented_variable_is_actually_threaded():
    """A `-v` variable the header documents must reach the command, or it is silently dropped.

    `LABEL=cell_type_forced` was accepted on the qsub line and never passed on, so a run asked
    for a forced annotation column and profiled the default one, with nothing in its output
    saying so. A variable that is documented and unused is worse than one that is absent: the
    absent one fails loudly at the shell.
    """
    import re
    src = _src()
    head = src[:src.index('case "${PHASE}" in')]
    body = src[src.index('case "${PHASE}" in'):]
    documented = set(re.findall(r"^# `([A-Z][A-Z0-9_]{2,})[=`]", head, re.M))
    documented |= set(re.findall(r"^#\s+`([A-Z][A-Z0-9_]{2,})=", head, re.M))
    missing = sorted(v for v in documented if v not in body)
    assert not missing, (
        "documented in the header and never used in the body, so it is accepted and dropped: "
        f"{missing}")


def test_the_label_option_reaches_both_plan_and_run():
    """The plan and the run must be given the SAME object description.

    COUNTING OCCURRENCES IS NOT ENOUGH, and this test learned that the hard way: it asserted
    `count("--label-key") >= 2` and passed with three occurrences, ALL of them on `plan`
    invocations and none on `cli run`. A run then profiled the default annotation column while
    every check said the option was threaded. A check that can be satisfied without the thing
    it is checking for is worse than no check.

    So each invocation is found by name and inspected for the flag.
    """
    import re
    src = _src()
    for sub in ("plan", "run"):
        calls = re.findall(r"scprofile\.cli " + sub + r"\b(.*?)(?:\|\||\n\n)", src, re.S)
        assert calls, f"no `scprofile.cli {sub}` invocation found in the template"
        assert all("--label-key" in c for c in calls), (
            f"a `cli {sub}` invocation does not pass --label-key, so plan and run would be "
            f"given different object descriptions: {len(calls)} call(s) checked")


if __name__ == "__main__":
    import sys
    bad = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except AssertionError as e:
                bad += 1
                print(f"  FAIL {name}: {e}")
    sys.exit(1 if bad else 0)
