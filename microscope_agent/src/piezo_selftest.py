"""Card 035's refusal tests for the piezo backend, each one watched failing.

    python src/piezo_selftest.py            the tests, against the mock link
    python src/piezo_selftest.py --mutate   each guard switched off in turn: its
                                            test must FAIL, or the test tests nothing
    python src/piezo_selftest.py --sim      the vendor simulator, in a child process

A test that has never been seen to fail is a test nobody knows tests anything,
so `--mutate` is not an extra: it is how each test below earns its place. It
replaces one guard in the loaded module with a version that does not guard,
runs every test, and requires that the guard's own tests go red. A mutation
under which its test still passes is reported as a defect in the test.

Nothing here touches hardware. The mock is in-process; `--sim` opens only the
vendor library's simulator address, which the backend refuses to widen.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import contextlib                                                # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
import subprocess                                                # noqa: E402
import tempfile                                                  # noqa: E402
from pathlib import Path                                         # noqa: E402

MODULE_PATH = Path(_HERE) / "devices" / "python_serial.py"


def load():
    spec = importlib.util.spec_from_file_location("_piezo_under_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)                                 # type: ignore[union-attr]
    return mod


def envelope(tmp: Path, limits: dict[str, tuple[float, float]] | None) -> Path:
    """A throwaway safety file in the envelope's shape, outside the tree."""
    doc = {"targets": [{"target": "bench", "limits": {}}]}
    for axis, (lo, hi) in (limits or {}).items():
        doc["targets"][0]["limits"][f"piezo_{axis}_position_min"] = {"value": lo, "unit": "um"}
        doc["targets"][0]["limits"][f"piezo_{axis}_position_max"] = {"value": hi, "unit": "um"}
    path = tmp / f"safety_{len(list(tmp.iterdir()))}.json"
    path.write_text(json.dumps(doc))
    return path


FULL = {"x": (0.0, 600.0), "y": (0.0, 600.0), "z": (0.0, 600.0)}


def setup(mod, tmp, limits=FULL, start=None, link=None):
    mod.reset()
    mod._ENVELOPE = envelope(tmp, limits)
    mod._HOLDER.link = link or mod.MockLink(start_um=start)
    mod._FOUND_LEVEL = None
    return mod._HOLDER.link


def refused(mod, params) -> str | None:
    try:
        mod.apply(params)
    except mod.PiezoRefused as exc:
        return str(exc)
    return None


def moves(link):
    return [c for c in link.commands if c[0] == "move"]


# --------------------------------------------------------------------------- #
# the tests: each returns None on pass, or what went wrong
# --------------------------------------------------------------------------- #


def t_absent_limit(mod, tmp):
    link = setup(mod, tmp, limits={"y": (0, 600), "z": (0, 600)})
    why = refused(mod, {"targets_um": {"x": 10}})
    if not why or "piezo_x_position_min" not in why:
        return f"an axis with no limit was not refused (got {why!r})"
    if moves(link):
        return "a command reached the controller on an axis with no limit"


def t_inverted_limit(mod, tmp):
    link = setup(mod, tmp, limits={**FULL, "x": (600, 0)})
    why = refused(mod, {"targets_um": {"x": 10}})
    if not why or "floor is above the ceiling" not in why:
        return f"an inverted limit was not refused (got {why!r})"
    if moves(link):
        return "a command reached the controller under an inverted limit"


def t_start_outside(mod, tmp):
    link = setup(mod, tmp, start={"x": -50.0})
    why = refused(mod, {"targets_um": {"x": 10}})
    if not why or "start" not in why:
        return f"a start outside the limit was not refused (got {why!r})"
    if moves(link):
        return "the backend moved an out-of-range axis instead of refusing"


def t_target_outside(mod, tmp):
    link = setup(mod, tmp)
    why = refused(mod, {"targets_um": {"x": 700}})
    if not why or "target" not in why:
        return f"a target outside the limit was not refused (got {why!r})"
    if moves(link):
        return "a command reached the controller with a target out of range"


def t_one_bad_axis_refuses_the_whole(mod, tmp):
    link = setup(mod, tmp)
    if not refused(mod, {"targets_um": {"x": 10, "y": 900}}):
        return "a request with one target out of range was not refused"
    if moves(link):
        return "part of a refused request went out -- it must fail whole, never halfway"


def t_waveform(mod, tmp):
    link = setup(mod, tmp)
    why = refused(mod, {"waveform": {"channel": 1}, "targets_um": {"x": 10}})
    if not why or "waveform generator" not in why:
        return f"the waveform generator was not refused (got {why!r})"
    if moves(link):
        return "a waveform request still moved the stage"


def t_z_needs_the_persons_step(mod, tmp):
    link = setup(mod, tmp, start={"z": 100.0})
    if not refused(mod, {"targets_um": {"z": 101}}):
        return "piezo Z moved with no direction-finding step from the person"
    if not refused(mod, {"targets_um": {"z": 105},
                         "z_direction_finding": {"step_um": 1, "by": "the person"}}):
        return "piezo Z moved further than the person's step"
    if moves(link):
        return "a refused Z request reached the controller"


def t_lock_restored_on_success(mod, tmp):
    link = setup(mod, tmp)
    out = mod.apply({"targets_um": {"x": 10}})
    if link.security_level() != link.BASE_LEVEL:
        return f"the controller was left at {link.security_level()!r} after a move"
    if not moves(link) or out["read_um"]["x"] != 10:
        return "the permitted move did not happen, so the test proves nothing"


def t_lock_restored_on_exception(mod, tmp):
    class Breaks(mod.MockLink):
        def move_absolute(self, channel, target_um):
            super().move_absolute(channel, target_um)
            raise OSError("the link broke mid-move")
    link = setup(mod, tmp, link=Breaks())
    try:
        mod.apply({"targets_um": {"x": 10}})
    except OSError:
        pass
    else:
        return "the injected failure did not surface"
    if link.security_level() != link.BASE_LEVEL:
        return f"an exception left the controller at {link.security_level()!r}"


def t_lock_restored_on_abort(mod, tmp):
    # Read the level AT THE MOMENT abort() returns, while the unlock is still in
    # force. Checking after apply() unwinds would see the `finally` restore and
    # pass whether or not abort restores anything -- which is exactly what the
    # first version of this test did, and `--mutate` is what showed it.
    class AbortsMidMove(mod.MockLink):
        seen = None

        def move_absolute(self, channel, target_um):
            super().move_absolute(channel, target_um)
            mod.abort()
            AbortsMidMove.seen = self.level
            raise RuntimeError("aborted mid-move")
    link = setup(mod, tmp, link=AbortsMidMove())
    with contextlib.suppress(RuntimeError):
        mod.apply({"targets_um": {"x": 10}})
    if AbortsMidMove.seen != link.BASE_LEVEL:
        return f"abort() returned with the controller still at {AbortsMidMove.seen!r}"
    if link.security_level() != link.BASE_LEVEL:
        return f"an abort left the controller at {link.security_level()!r}"
    if not refused(mod, {"targets_um": {"x": 20}}):
        return "after abort the backend accepted a command"


def t_unknown_level_changes_nothing(mod, tmp):
    class Strange(mod.MockLink):
        def restorable(self, base):
            return False
    link = setup(mod, tmp, link=Strange())
    why = refused(mod, {"targets_um": {"x": 10}})
    if not why or "does not know how to restore" not in why:
        return f"an unrestorable level was not refused (got {why!r})"
    if [c for c in link.commands if c[0] == "security"]:
        return "the security level was changed while refusing"


TESTS = [t_absent_limit, t_inverted_limit, t_start_outside, t_target_outside,
         t_one_bad_axis_refuses_the_whole, t_waveform, t_z_needs_the_persons_step,
         t_lock_restored_on_success, t_lock_restored_on_exception, t_lock_restored_on_abort,
         t_unknown_level_changes_nothing]


# --------------------------------------------------------------------------- #
# mutations: each switches one guard off; the named tests must then fail
# --------------------------------------------------------------------------- #


def _no_restore(mod):
    @contextlib.contextmanager
    def unlocked(link, level="user"):
        link.set_security_level(level)
        yield link.security_level()
    mod.unlocked = unlocked


def _no_restorable_check(mod):
    original = mod.unlocked

    @contextlib.contextmanager
    def unlocked(link, level="user"):
        base = link.security_level()
        link.set_security_level(level)
        try:
            yield base
        finally:
            link.set_security_level(base)
    mod.unlocked = unlocked
    return original


MUTATIONS = {
    "axis_refusal off": (lambda m: setattr(m, "axis_refusal", lambda *a, **k: None),
                         ["t_absent_limit", "t_inverted_limit"]),
    "position_refusal off": (lambda m: setattr(m, "position_refusal", lambda *a, **k: None),
                             ["t_start_outside", "t_target_outside",
                              "t_one_bad_axis_refuses_the_whole"]),
    "waveform_refusal off": (lambda m: setattr(m, "waveform_refusal", lambda *a, **k: None),
                             ["t_waveform"]),
    "z_refusals off": (lambda m: setattr(m, "z_refusals", lambda *a, **k: []),
                       ["t_z_needs_the_persons_step"]),
    "lock not restored": (_no_restore, ["t_lock_restored_on_success",
                                        "t_lock_restored_on_exception"]),
    "abort does not restore": (lambda m: setattr(m, "_FOUND_LEVEL", None) or
                               setattr(m, "abort", _abort_without_restore(m)),
                               ["t_lock_restored_on_abort"]),
    "restorable check off": (_no_restorable_check, ["t_unknown_level_changes_nothing"]),
}


def _abort_without_restore(mod):
    def abort():
        mod._ABORTED = True
        return {"aborted": True}
    return abort


def run(mod, tmp) -> dict[str, str | None]:
    out = {}
    for test in TESTS:
        try:
            out[test.__name__] = test(mod, tmp)
        except Exception as exc:                                  # a crash is a failure
            out[test.__name__] = f"crashed: {type(exc).__name__}: {exc}"
    return out


def main(argv: list[str]) -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        if "--sim" in argv:
            return sim()
        results = run(load(), tmp)
        failed = {k: v for k, v in results.items() if v}
        for name, why in results.items():
            print(f"{'FAIL' if why else 'pass'}  {name}" + (f"  -- {why}" if why else ""))
        if "--mutate" not in argv:
            return 1 if failed else 0
        if failed:
            print("the unmutated tests do not all pass; mutation results would mean nothing")
            return 1
        bad = 0
        for label, (mutate, expected) in MUTATIONS.items():
            mod = load()
            mutate(mod)
            got = run(mod, tmp)
            went_red = [n for n in expected if got.get(n)]
            silent = [n for n in expected if not got.get(n)]
            print(f"mutation {label!r}: watched failing {went_red}"
                  + (f"; STILL PASSING {silent} -- that test does not test its guard" if silent else ""))
            bad += bool(silent)
        return 1 if bad else 0


SIM_CHILD = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("p", sys.argv[1])
p = importlib.util.module_from_spec(spec); sys.modules["p"] = p; spec.loader.exec_module(p)
out = {}
try:
    p.DllLink("COM4")
    out["real_address"] = "NOT REFUSED"
except p.PiezoRefused as exc:
    out["real_address"] = "refused before loading the library: " + str(exc)[:80]
link = p.open_link("dll", address="sim:/NPC6330")
out["security"] = link.security_level()
try:
    out["position_um"] = {a: link.read_position(c) for a, c in p.AXIS_CHANNEL.items()}
except p.PiezoRefused as exc:
    out["position_um"] = "no answer: " + str(exc)
out["learn_levels"] = link.learn_levels()
# One move through every refusal, against the person's envelope/safety.json as
# it stands. The simulator answers zero to everything, so the read-back is 0
# and the difference is reported rather than judged -- which is the point.
res = p.apply({"targets_um": {"x": 10}})
out["apply"] = {k: res[k] for k in ("applied", "read_um", "difference_um",
                                     "verified", "security_level_after")}
try:
    p.apply({"targets_um": {"x": 700}})
    out["target_700"] = "NOT REFUSED"
except p.PiezoRefused as exc:
    out["target_700"] = "refused: " + str(exc)[:70]
p.close_link()
print(json.dumps(out))
"""


def sim() -> int:
    """The simulator in a child process: a library fault cannot take this one down."""
    proc = subprocess.run([sys.executable, "-c", SIM_CHILD, str(MODULE_PATH)],
                          capture_output=True, text=True, timeout=60)
    print(proc.stdout.strip() or "(no output)")
    if proc.returncode:
        print(proc.stderr.strip()[-2000:])
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
