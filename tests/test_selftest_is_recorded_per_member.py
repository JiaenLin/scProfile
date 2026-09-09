"""Three plugins nobody asked about sank the one that was asked for.

REPRODUCED ON THE CLUSTER. `install liana --prefix ~/envs` resolved to scprofile-env-0242f5f3d1,
an environment seven plugins share. It ran seven selftests. liana PASSED. The command still
failed, and the job with it, because abundance hit a pertpy/statsmodels ImportError that is not
liana's to fix, and de and decoupler were SIGKILLed by the node. The environment liana had just
demonstrably run in was reported as not built, to a job that had asked about liana and nothing
else.

The property `install` was defending is CORRECT and this suite exists to keep it: an environment
shared by four plugins and proved by one is an environment three of them meet for the first time
inside a run. It was simply enforced in the wrong place - at install time, for everyone, all at
once - where the only verdict available is the worst member's.

So the verdict is recorded PER MEMBER beside the environment, and the refusal moved to the point
of use. What this suite pins down:

  - a member's selftest verdict is RECORDED, pass or fail, and the record says which environment
    it was proved against;
  - `install X` proves X and anyone with no standing record, and X alone decides whether the
    command failed;
  - `run` refuses a plugin whose own record is absent, stale or failed - by name, with the
    command that would prove it - and `plan` refuses it through `env_state`;
  - an environment with NO record for anyone is not refused. It predates the record or was built
    by hand, and refusing it would invalidate every installation on disk for a reason its owner
    did not cause. This is also what makes the change a NO-OP on a one-plugin tree, which is the
    shape the end-to-end run uses.
  - THE RECORD LIVES INSIDE THE ENVIRONMENT IT IS A CLAIM ABOUT, ON EVERY BUILD PATH. A proof
    stored anywhere else outlives `rm -rf <env>` and is then read as fresh against a rebuilt
    directory - the one failure the fingerprint exists to prevent, arriving by the one route the
    fingerprint cannot see. The last section names the two build paths and exercises both.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import planner, runner                                     # noqa: E402
from scprofile.kernels import discover                                    # noqa: E402

fails = []


def check(ok, msg, detail=""):
    if not ok:
        fails.append(msg + (f"   [{detail}]" if detail else ""))


#: A fake interpreter for the environment. It is a shell script rather than a python, because
#: nothing here is testing what a selftest computes - only what the host does with the verdict -
#: and a real environment for seven plugins is an hour of solving away. `FAIL_ON` names the
#: plugin whose selftest exits non-zero, which is how abundance's real ImportError is stood in for.
FAKE = """#!/bin/sh
case "$*" in
  *{fail_on}*) echo "ImportError: cannot import name 'something' from statsmodels" ; exit 1 ;;
  *) echo "fake interpreter: ok" ; exit 0 ;;
esac
"""


def fake_env(prefix, group, fail_on="__nothing__", route="conda", base=None):
    """A directory that looks exactly like a finished build of `group`, with no proofs in it.

    `route` is the BUILD PATH being stood in for, and the two differ in exactly one structural
    way that matters to anything in this file - whether `bin/python` points out of the prefix:

      conda  the interpreter is a real file in `bin/` (or a symlink to `bin/python3.11` lying
             beside it). Resolving it never leaves the environment.
      venv   `python -m venv` writes `bin/python` as a SYMLINK to the interpreter it was built
             FROM, which lives outside the environment entirely - a system python, a pyenv, a
             `module load`ed one. `runner.machine` chooses this route whenever no conda-family
             manager is on PATH, so it is what a laptop and a bare container get, not a corner.

    `base` lets two environments be built from ONE base interpreter, which is the normal case on
    a machine and the case where a record kept beside the base is shared between strangers.
    """
    p = Path(prefix) / group.name
    (p / "bin").mkdir(parents=True, exist_ok=True)
    if route == "venv":
        b = Path(base) if base else Path(prefix) / "base-python"
        (b / "bin").mkdir(parents=True, exist_ok=True)
        for exe in ("python", "Rscript"):
            f = b / "bin" / exe
            if not f.exists():
                f.write_text(FAKE.format(fail_on=fail_on))
                f.chmod(0o755)
            (p / "bin" / exe).symlink_to(f)
    else:
        for exe in ("python", "Rscript"):                # cellchat's interpreter is Rscript
            f = p / "bin" / exe
            f.write_text(FAKE.format(fail_on=fail_on))
            f.chmod(0o755)
    ks = discover()
    (p / ".scprofile_lock").write_text(runner.env_fingerprint(ks[group.members[0]], group),
                                       encoding="utf-8")
    return p


def groups():
    from scprofile import resolve as RS
    return list(RS.group_by_compatibility(list(discover().values())))


ks = discover()
shared = sorted([g for g in groups() if len(g.members) > 1], key=lambda g: -len(g.members))
alone = [g for g in groups() if len(g.members) == 1]

# WHAT THIS TREE CAN AND CANNOT SHOW, SAID OUT LOUD. The defect that started this file needs a
# SHARED environment - one member sinking another - so the sections below need a group with more
# than one member to reproduce anything. The end-to-end run is CELLCHAT-ONLY with the other eight
# plugins unplugged, and on that tree no such group exists: demanding one turned this suite red on
# the one tree the host actually ships, for the reason that the defect cannot happen there. That
# is a fixture requirement reported as a failure, which is the worst kind of red - it says nothing
# and it blocks everything.
#
# So a tree with nothing to share only has to say so. A tree with SEVERAL plugins and no shared
# group still fails: grouping is what makes the defect possible, and if it has silently stopped
# grouping, these sections are passing by not running.
check(bool(shared) or len(ks) < 2,
      f"this tree has {len(ks)} plugins and no shared environment at all, so nothing below "
      f"reproduces the defect - resolution has stopped grouping")
check(bool(alone), "no one-member environment in this tree, so the no-op cannot be proved")
if not shared:
    print("note: one-plugin tree - the shared-environment sections are not exercised here; the "
          "no-op section and the proof-location section below are.")


# --------------------------------------------------------------- the install that used to sink
if shared:
    g = shared[0]
    asked = "liana" if "liana" in g.members else [m for m in g.members if m != g.members[0]][0]
    other = "abundance" if "abundance" in g.members else g.members[0]
    if other == asked:
        other = [m for m in g.members if m != asked][0]
    with tempfile.TemporaryDirectory() as td:
        pref = Path(td)
        env = fake_env(pref, g, fail_on=other)
        said = []
        try:
            runner.install(ks[asked], pref, log=said.append)
            raised = ""
        except Exception as e:                                            # noqa: BLE001
            raised = str(e)
        txt = "\n".join(said)
        check(not raised,
              f"install {asked} still fails when {other}'s selftest does - which is the defect",
              raised[:200])
        check(f"recorded: {other} FAILED" in txt,
              f"{other}'s failure was not recorded per member", txt[-400:])
        check(f"recorded: {asked} ok" in txt,
              f"{asked}'s pass was not recorded per member", txt[-400:])
        check(runner.read_proof(env, other).get("verdict") == "failed",
              f"no proof record for {other} beside the environment",
              str(runner.read_proof(env, other)))
        check(runner.read_proof(env, asked).get("verdict") == "ok",
              f"no proof record for {asked} beside the environment",
              str(runner.read_proof(env, asked)))
        check(runner.read_proof(env, asked).get("fingerprint") == g.name,
              "the record does not say which environment it was proved against",
              str(runner.read_proof(env, asked)))
        check(other in txt and "run and plan time" in txt,
              "the install does not say where the failed member will be refused instead",
              txt[-400:])

        # A SECOND INSTALL DOES NOT PAY FOR THE FAILED MEMBER AGAIN. Re-proving a member whose
        # record already says it failed is the seven-selftest bill this change exists to stop -
        # and decoupler's is a 1800s timeout, every time.
        said2 = []
        runner.install(ks[asked], pref, log=said2.append)
        txt2 = "\n".join(said2)
        check(f"recorded: {other} FAILED already" in txt2,
              f"{other} is re-proved by an install asked about {asked}", txt2[-400:])
        check(f"recorded: {asked} ok" in txt2,
              "the member that was asked for is not re-proved, and drift is why it must be",
              txt2[-400:])

        # ---------------------------------------------------- the refusal, at the point of use
        inp = pref / "in.json"
        inp.write_text(json.dumps({"resources": {"cores": 1}}), encoding="utf-8")
        try:
            runner.run(ks[other], inp=inp, out_dir=pref / "out", prefix=pref,
                       log=lambda *_a, **_k: None)
            check(False, f"running {other} in an environment where its selftest FAILED was allowed")
        except RuntimeError as e:
            m = str(e)
            check(other in m, f"the refusal does not name {other}", m[:200])
            check("selftest FAILED" in m or "FAILED" in m,
                  "the refusal does not say what the record says", m[:200])
            check(f"scprofile install {other} --prefix {pref}" in m,
                  "the refusal does not carry the command that would prove it", m[:300])
            # AND IT DOES NOT QUOTE THE PLUGIN'S OWN ERROR. `feedback.diagnose` classifies
            # whatever `run` raises, and a recorded `ImportError` inside this text matches its
            # ENVIRONMENT signature - which is marked repairable, and the run loop repairs by
            # rebuilding the shared environment with --force. Hours of solving, triggered by a
            # refusal whose remedy is a one-minute selftest.
            from scprofile import feedback as FB
            check("ImportError" not in m,
                  "the refusal quotes the recorded failure, which another layer will read as a "
                  "broken environment and try to rebuild", m[:300])
            check(not FB.diagnose(other, RuntimeError(m), prefix=pref).repairable,
                  "an unproved plugin's refusal is diagnosed as a repairable environment, so the "
                  "run loop will --force rebuild an environment nothing is wrong with")
            # doctor and plan DO get the reason: nothing classifies their sentence.
            check("It said:" in runner.env_state(ks[other], pref)[1],
                  "the plan and doctor lost the one line that says what actually failed",
                  runner.env_state(ks[other], pref)[1])

        # and the member that WAS proved is not stopped by anything in this file
        try:
            runner.run(ks[asked], inp=inp, out_dir=pref / "out2", prefix=pref,
                       log=lambda *_a, **_k: None)
            stopped = ""
        except Exception as e:                                            # noqa: BLE001
            stopped = str(e)
        check("will not be run" not in stopped,
              f"{asked} was proved and the proof check stopped it anyway", stopped[:200])

        # ---------------------------------------------------------------- and the PLAN refuses
        # `plan` asks `env_state`, and treats exactly these three words as runnable. The word for
        # an unproved member is `missing` because the vocabulary is shared with `doctor` and
        # `planner.build_state`, and because it names the CHEAP repair.
        st, why, fix = runner.env_state(ks[other], pref)
        check(st not in ("installed", "override", "host"),
              f"plan would call {other} runnable in an environment nothing proved it in",
              f"{st}: {why}")
        check(other in why, "the plan's sentence does not name the plugin", why)
        check(fix.startswith(f"scprofile install {other}"),
              "the plan is not told the command that would prove it", fix)
        cli_src = (ROOT / "scprofile" / "cli.py").read_text(encoding="utf-8")
        check('state in ("installed", "override", "host")' in cli_src,
              "the plan no longer decides runnability from env_state's word, so this refusal may "
              "not reach it")
        d = planner.build_state(ks[other], st, prefix=pref)
        check(d and d.get("fixable"), "the plan cannot repair an unproved member", str(d))
        check(d and "--force" not in d.get("fix", ""),
              "the repair rebuilds a shared environment for everybody to re-prove one member",
              str(d))

        # ------------------------------------------------------------- absent, and stale, count
        third = [m for m in g.members if m not in (asked, other)]
        if third:
            t = third[0]
            (env / runner.PROOF_NAME.format(kernel=t)).unlink(missing_ok=True)
            stt, twhy, tfix = runner.proof_state(ks[t], pref)
            check(stt == "absent",
                  f"a member with no record among recorded ones is not called absent: {stt}", twhy)
            check(runner.env_state(ks[t], pref)[0] not in ("installed", "override", "host"),
                  f"{t} would be planned in an environment that has never been proved for it")
            check(tfix.startswith(f"scprofile install {t}"), "absent carries no fix", tfix)
        (env / runner.PROOF_NAME.format(kernel=asked)).write_text(
            "verdict=ok\nfingerprint=scprofile-env-0000000000\nwhen=2020-01-01T00:00:00Z\n")
        stale = runner.proof_state(ks[asked], pref)
        check(stale[0] == "stale",
              "a proof made against another environment still counts as proof", str(stale))
        check("scprofile-env-0000000000" in stale[1] and g.name in stale[1],
              "the stale sentence does not say proved-against-what and now-what", stale[1])


# ---------------------------------------- the proof lives WITH the environment, on BOTH routes
#
# THE BUILD PATHS EXERCISED HERE, NAMED: conda (bin/python is a real file, or a symlink to
# bin/python3.11 beside it - resolving it never leaves the prefix) and venv (`python -m venv`
# writes bin/python as a symlink to the interpreter it was built FROM, which lives outside the
# prefix entirely). `runner.machine` takes the venv route whenever no conda-family manager is on
# PATH, so it is what a laptop and a bare container get; `install` says so out loud when it does.
# A REAL `python -m venv` is also built at the end of this section, so the hand-built shape above
# is checked against the shape venv actually produces rather than against a belief about it.
#
# WHAT WENT WRONG. `proof_home` was `Path(exe).resolve().parent.parent`, which is the environment
# on the conda route and the BASE PYTHON'S PREFIX on the venv route. That inverts the safety
# property rather than weakening it, in whichever of two ways the machine picks for you:
#
#   - base prefix writable (pyenv, homebrew, a module on the cluster): the record is written
#     outside the environment, so it SURVIVES `rm -rf <env>`. The group name is content-addressed,
#     so a rebuild has the same fingerprint, and the record is read as a fresh proof of a directory
#     that has never been run in - the exact stale-proof-accepted-as-fresh failure the fingerprint
#     was added to prevent, arriving through the one path the fingerprint cannot see. That one
#     directory is also shared by every venv on the machine built from the same base python, so a
#     proof earned under one --prefix answers for a different --prefix.
#   - base prefix read-only (a system python): `record_proof` never raises, by design, so it
#     silently writes nothing at all. Every member stays `unrecorded`, `unrecorded` is deliberately
#     NOT in UNPROVED, and `run` and `plan` refuse nobody. The check is simply off.
#
# Both are checked below, and on ANY group this tree has - a shared one if there is one, the
# one-member group otherwise. WHERE the proof is stored has nothing to do with how many members
# share the environment, so this section is the part of the file that still runs, and still
# refuses to go green, on the CELLCHAT-ONLY tree the end-to-end run uses.
if shared or alone:
    g = (shared or alone)[0]
    one = g.members[0]
    print(f"proof-location section: exercising the conda and venv build paths on {g.name} "
          f"({len(g.members)} member(s): {', '.join(g.members)})")
    for route in ("conda", "venv"):
        with tempfile.TemporaryDirectory() as td:
            pref = Path(td)
            env = fake_env(pref, g, route=route)
            exe = Path(runner.interpreter(ks[one], pref)[0])
            home = runner.proof_home(ks[one], pref)

            # THE FIXTURE IS THE SHAPE IT CLAIMS TO BE. A venv case whose interpreter did not
            # actually point out of the prefix would pass everything below while testing nothing,
            # and this file would then certify a property it never exercised.
            escapes = exe.is_symlink() and not str(exe.resolve()).startswith(str(env.resolve()))
            check(escapes == (route == "venv"),
                  f"the {route} fixture is not the shape it stands in for: interpreter "
                  f"{'does' if escapes else 'does not'} resolve out of the environment", str(exe))

            check(home is not None and Path(home).resolve() == env.resolve(),
                  f"on the {route} route the proof is written OUTSIDE the environment it is a "
                  f"claim about", f"proof_home={home}  env={env}")
            wrote = runner.record_proof(ks[one], pref, verdict="ok")
            check(wrote is not None,
                  f"on the {route} route no proof could be written at all, so nothing is ever "
                  f"refused - a read-only base python is how this looks in the field")
            check(wrote is not None and Path(wrote).resolve().parent == env.resolve(),
                  f"on the {route} route the record did not land inside the environment",
                  str(wrote))
            check(runner.proof_state(ks[one], pref)[0] == "proved",
                  f"on the {route} route a record just written is not read back",
                  str(runner.proof_state(ks[one], pref)))

            # AND THE SELFTEST LOG TRAVELS WITH IT. `proof_state`'s sentence tells the reader both
            # files are "beside the environment"; they are only beside each other if one function
            # decides where. On the venv route the old expression sent the log to the base python
            # too, where a system python turns `open(logf, "w")` into a PermissionError and takes
            # down a selftest that had nothing wrong with it.
            runner.selftest(ks[one], prefix=pref, log=lambda *_a, **_k: None)
            check((env / f".scprofile_selftest_{one}.log").exists(),
                  f"on the {route} route the selftest log is not beside the environment, so the "
                  f"sentence `proof_state` prints is false", str(list(env.iterdir())[:8]))

            # THE RECORD DIES WITH THE ENVIRONMENT. This is the whole point of storing it inside:
            # delete the directory, build it again exactly as it was, and nothing may claim the
            # new one was ever proved. A record kept beside the base python survives this and is
            # read as `proved`, because a content-addressed group name rebuilds identical.
            import shutil as _sh
            _sh.rmtree(env)
            env = fake_env(pref, g, route=route)
            check(runner.read_proof(runner.proof_home(ks[one], pref), one) == {},
                  f"on the {route} route a proof outlived the environment it is about - the "
                  f"directory was deleted and rebuilt and the record is still there",
                  str(runner.read_proof(runner.proof_home(ks[one], pref), one)))
            check(runner.proof_state(ks[one], pref)[0] != "proved",
                  f"on the {route} route a rebuilt environment is reported as already proved",
                  str(runner.proof_state(ks[one], pref)))

    # TWO PREFIXES, ONE BASE PYTHON. The normal case on any machine: two `--prefix` locations
    # built by venv from the same interpreter. A record kept beside the base is one record for
    # both, so a proof earned in the first answers for the second, where nothing has ever run.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = root / "base-python"
        pa, pb = root / "a", root / "b"
        pa.mkdir(); pb.mkdir()
        ea = fake_env(pa, g, route="venv", base=base)
        eb = fake_env(pb, g, route="venv", base=base)
        check(runner.proof_home(ks[one], pa).resolve() != runner.proof_home(ks[one], pb).resolve(),
              "two environments built from one base python share a proof home, so a record "
              "written for either is read for both",
              f"{runner.proof_home(ks[one], pa)} vs {runner.proof_home(ks[one], pb)}")
        runner.record_proof(ks[one], pa, verdict="ok")
        check(runner.proof_state(ks[one], pa)[0] == "proved",
              "the prefix that was proved is not reported proved", str(runner.proof_state(ks[one], pa)))
        check(runner.proof_state(ks[one], pb)[0] != "proved",
              f"proving {one} under one --prefix reported it proved under a DIFFERENT one that "
              f"nothing has ever run it in", str(runner.proof_state(ks[one], pb)))

    # AND THE HAND-BUILT VENV SHAPE IS THE SHAPE VENV BUILDS. Everything above stands on the claim
    # that `python -m venv` symlinks its interpreter out of the prefix. That is checked here
    # against a real one rather than asserted. Where a platform copies the interpreter instead
    # (`--copies`, Windows), the escape does not happen and only the location claim is checked -
    # said out loud rather than silently skipped.
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        vp = Path(td) / "real-venv"
        try:
            subprocess.run([sys.executable, "-m", "venv", str(vp)], check=True,
                           capture_output=True, timeout=180)
            built = (vp / "bin" / "python").exists()
        except Exception as e:                                            # noqa: BLE001
            built = False
            print(f"note: no real venv could be built here ({type(e).__name__}), so the venv "
                  f"shape rests on the hand-built fixture alone")
        if built:
            rexe = vp / "bin" / "python"
            check(runner.env_home(rexe).resolve() == vp.resolve(),
                  "a REAL venv's interpreter does not resolve to the environment it belongs to",
                  f"env_home={runner.env_home(rexe)}  venv={vp}")
            if not str(rexe.resolve()).startswith(str(vp.resolve())):
                check(runner.env_home(rexe).resolve() != rexe.resolve().parent.parent,
                      "a REAL venv's proof home is still the base python's prefix",
                      f"{runner.env_home(rexe)} == {rexe.resolve().parent.parent}")
            else:
                print("note: this platform's venv copies its interpreter rather than symlinking "
                      "it, so the escape is exercised by the hand-built fixture only")


# ----------------------------------------------------------- the one-plugin tree is a no-op
#
# The end-to-end run is CELLCHAT-ONLY with every other plugin unplugged, so its group has one
# member. `velocity` and `scenic` are the one-member groups in this tree and stand in for it:
# with one member there is nothing a per-member record can add that the install did not already
# say, and nothing here may change what happens.
if alone:
    g1 = alone[0]
    only = g1.members[0]
    with tempfile.TemporaryDirectory() as td:
        pref = Path(td)
        env = fake_env(pref, g1)
        inp = pref / "in.json"
        inp.write_text(json.dumps({"resources": {"cores": 1}}), encoding="utf-8")

        # AN ENVIRONMENT WITH NO RECORD FOR ANYONE IS NOT REFUSED. Every environment built before
        # this record existed carries none, and the cluster's do. Absence of the whole record is
        # absence of evidence; absence of one record among several is evidence of absence.
        state, why, _fix = runner.env_state(ks[only], pref)
        check(state == "installed",
              f"a built one-member environment with no proof record is reported {state}", why)
        check(runner.proof_state(ks[only], pref)[0] == "unrecorded",
              "an environment carrying no records for anyone is not called unrecorded",
              str(runner.proof_state(ks[only], pref)))
        try:
            runner.run(ks[only], inp=inp, out_dir=pref / "out", prefix=pref,
                       log=lambda *_a, **_k: None)
            stopped = ""
        except Exception as e:                                            # noqa: BLE001
            stopped = str(e)
        check("will not be run" not in stopped,
              "a one-plugin tree's run is refused by a record that predates it - NOT a no-op",
              stopped[:200])

        # AND INSTALL BEHAVES AS IT ALWAYS DID: one member, so the member that was asked for is
        # the whole group, and its failure is still this command's failure.
        said = []
        runner.install(ks[only], pref, log=said.append)
        check(runner.read_proof(env, only).get("verdict") in ("ok", "none"),
              "the only member's verdict was not recorded", str(runner.read_proof(env, only)))
        for exe in ("python", "Rscript"):
            f = env / "bin" / exe
            f.write_text(FAKE.format(fail_on=only))
            f.chmod(0o755)
        try:
            runner.install(ks[only], pref, log=lambda *_a: None)
            check(runner.read_proof(env, only).get("verdict") == "none",
                  f"install {only} succeeded although its own selftest failed",
                  str(runner.read_proof(env, only)))
        except RuntimeError as e:
            check(only in str(e) and "asked about" in str(e),
                  "the refusal does not say that the member asked about is the one that failed",
                  str(e)[:200])


# ------------------------------------------------------------ the record is written once, by one
src = (ROOT / "scprofile" / "runner.py").read_text(encoding="utf-8")
check(src.count("record_proof(kernel, prefix, verdict=") >= 4,
      "not every verdict a selftest can reach is recorded")
check("record_proof" not in src.split("def install(")[1].split("def selftest(")[0],
      "install records verdicts of its own, so two functions can disagree about what happened")
check("REFUSAL" in src or "point of use" in src,
      "nothing in the runner records WHERE the refusal now happens")
# ONE DERIVATION FOR BOTH FILES. The proof and the selftest log were two copies of one expression,
# and a copy is where they drift apart again - which is how the record came to be written outside
# the environment on one build route and nowhere at all on the other.
check(src.count("env_home(exe)") >= 2,
      "the proof record and the selftest log no longer share one derivation of where the "
      "environment is, so they can be written to two different places again")

if fails:
    print("FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ok - a shared environment records a verdict per member, and refuses the plugin that was "
      "not proved rather than the one that was")
