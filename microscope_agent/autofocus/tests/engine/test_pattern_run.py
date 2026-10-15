"""`pattern_run` (card T-20261002-2205 stage 4): a saved pattern on the mock XYZ piezo and the mock
traps through the runner. Mock only: the stand's piezo stays read only and has no adapter."""

from __future__ import annotations

import threading
import time

import pytest

from dino_autofocus.engine import Command, Event
from dino_autofocus.engine.backend import GUARD_TOKEN, UnguardedMotion
from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.guards import GuardError, PiezoAxis
from dino_autofocus.engine.operations import pattern_run  # noqa: F401 - registers the op
from dino_autofocus.engine.patterns import pattern_from_dict
from dino_autofocus.engine.piezo import MockPiezo, PiezoInfo, piezo_state_of
from dino_autofocus.engine.runner import OPERATIONS, AllowAll, Runner, RunnerConfig
from dino_autofocus.engine.tweezers import MockTweezers

T = 10.0
USER, SESSION = "operator@example.test", "20261002-0900-operator"

SQUARE = {"id": "sq", "name": "Square", "tracks": [
    {"target": "piezo", "points": [[0, 0, 0, 0], [0.1, 5, 0, 1], [0.2, 5, 5, 2], [0.3, 0, 5, 1]]},
    {"target": "trap:1", "points": [[0, 0, 0, 0], [0.3, 10, -10, 0]]}]}


class Collect:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._cond = threading.Condition()

    def __call__(self, ev: Event) -> None:
        with self._cond:
            self.events.append(ev)
            self._cond.notify_all()

    def wait(self, kinds: tuple[str, ...], op_id: str) -> Event:
        def find():
            return next((e for e in self.events if e.kind in kinds and e.op_id == op_id), None)

        with self._cond:
            assert self._cond.wait_for(lambda: find() is not None, T), (kinds, op_id)
            return find()


@pytest.fixture
def make():
    made: list[Runner] = []

    def build(*, piezo=None, tweezers=None, patterns=None):
        backend = MockBackend(seed=1)
        backend.open()
        store = {p["id"]: pattern_from_dict(p) for p in (patterns or [SQUARE])}
        r = Runner(backend, registry=OPERATIONS, control=AllowAll(), tweezers=tweezers,
                   piezo=piezo, patterns=store.get,
                   config=RunnerConfig(position_interval_s=None))
        sink = Collect()
        r.subscribe(sink)
        r.start()
        r.set_experiment_session(SESSION, time.time())
        made.append(r)
        return r, sink

    yield build
    for r in made:
        r.shutdown("test teardown", timeout=T)
        assert r.wait_idle(T)


def start(r: Runner, args: dict) -> str:
    return r.submit(Command("start", op="pattern_run", args=args, user_id=USER,
                            session_id=SESSION, control_grant="g-1"))


class RealPiezo(MockPiezo):
    def info(self) -> PiezoInfo:
        return PiezoInfo("nanobench", dict(self.TRAVEL), bench=True)


# -- device and guard ------------------------------------------------------------------


def test_mock_piezo_needs_the_token_and_stays_in_travel():
    pz = MockPiezo()
    with pytest.raises(UnguardedMotion):
        pz.move(1, 1, 1, token=object())
    with pytest.raises(ValueError, match="travel"):
        pz.move(250, 1, 1, token=GUARD_TOKEN)
    assert piezo_state_of(pz)["position"] == {"x_um": 100.0, "y_um": 100.0, "z_um": 50.0}
    assert piezo_state_of(None) is None


def test_the_real_piezo_is_always_refused():
    pz = RealPiezo()
    with pytest.raises(GuardError, match="read only until M5"):
        PiezoAxis(pz).move(101, 100, 50)
    assert pz.position().x_um == 100.0
    with pytest.raises(GuardError, match="no movable piezo"):
        PiezoAxis(None).allowed()


# -- the operation -----------------------------------------------------------------------


def test_runs_the_piezo_and_a_trap_then_returns_the_piezo(make):
    pz, tw = MockPiezo(), MockTweezers()
    r, sink = make(piezo=pz, tweezers=tw)
    op = start(r, {"pattern_id": "sq", "repeats": 2, "rate_hz": 50})
    done = sink.wait(("finished", "error", "preflight_failed"), op)
    assert done.kind == "finished", done.data
    s = done.data["summary"]
    assert s["repeats"] == 2 and len(s["sha256"]) == 64
    assert s["piezo_start_um"] == s["piezo_returned_um"] == [100.0, 100.0, 50.0]
    assert s["piezo_moves"] >= 10 and s["trap_moves"] >= 10 and s["piezo_max_off_um"] == 0.0
    assert pz.position().x_um == 100.0  # back where it started
    assert (tw.traps()[1].x_um, tw.traps()[1].y_um) == (10.0, -10.0)  # the trap holds its end
    progress = [e for e in sink.events if e.kind == "progress" and e.op_id == op]
    assert progress and "positions" in progress[-1].data["data"]
    assert not any(e.kind == "motion" and e.op_id == op for e in sink.events)  # quiet moves


def test_an_abort_stops_at_once_without_the_return(make):
    slow = {"id": "slow", "name": "Slow", "tracks": [
        {"target": "piezo", "points": [[0, 0, 0, 0], [30, 20, 0, 0]]}]}
    pz = MockPiezo()
    r, sink = make(piezo=pz, patterns=[slow])
    op = start(r, {"pattern_id": "slow", "rate_hz": 20})
    sink.wait(("progress",), op)
    time.sleep(0.3)
    r.submit(Command("abort", op_id=op, user_id=USER))
    ended = sink.wait(("aborted", "finished", "error"), op)
    assert ended.kind == "aborted"
    x = pz.position().x_um
    assert x > 100.0  # it moved, and was left where the abort found it
    time.sleep(0.2)
    assert pz.position().x_um == x


def both(**kw):
    return {"piezo": MockPiezo(), "tweezers": MockTweezers(), **kw}


@pytest.mark.parametrize(("kw", "args", "says"), [
    ({}, {"pattern_id": "nope"}, "no pattern nope"),
    ({"tweezers": MockTweezers()}, {"pattern_id": "sq"}, "no movable piezo"),
    ({"piezo": MockPiezo()}, {"pattern_id": "sq"}, "no tweezers"),
    (both(piezo=RealPiezo()), {"pattern_id": "sq"}, "read only until M5"),
    (both(tweezers=MockTweezers(n_traps=1)), {"pattern_id": "sq"}, "no trap 1"),
    (both(), {"pattern_id": "sq", "repeats": 0}, "repeats"),
    (both(), {"pattern_id": "sq", "rate_hz": 500}, "rate"),
    (both(), {"pattern_id": "sq", "loops": 2}, "unknown"),
])
def test_preflight_refuses_before_anything_moves(make, kw, args, says):
    r, sink = make(**kw)
    failed = sink.wait(("preflight_failed", "finished", "error"), start(r, args))
    assert failed.kind == "preflight_failed" and says in str(failed.data)
    if "piezo" in kw:
        assert kw["piezo"].position().x_um == 100.0


def test_a_track_that_would_leave_the_piezo_travel_is_refused(make):
    pz = MockPiezo()
    with pz._lock:  # park it near the end of x travel
        pz._pos = type(pz._pos)(190.0, 100.0, 50.0)
    far = {"id": "far", "name": "Far", "tracks": [
        {"target": "piezo", "points": [[0, 0, 0, 0], [1, 20, 0, 0]]}]}
    r, sink = make(piezo=pz, patterns=[far])
    failed = sink.wait(("preflight_failed", "finished", "error"), start(r, {"pattern_id": "far"}))
    assert failed.kind == "preflight_failed" and "outside 0..200" in str(failed.data)
    assert pz.position().x_um == 190.0


def test_a_piezo_readback_mismatch_stops_the_run():
    class Drifty(MockPiezo):
        def move(self, x_um, y_um, z_um, *, token):
            got = super().move(x_um, y_um, z_um, token=token)
            return type(got)(got.x_um + 0.5, got.y_um, got.z_um)  # lands 0.5 um off

    with pytest.raises(GuardError, match="commanded"):
        PiezoAxis(Drifty()).move(101.0, 100.0, 50.0)


def test_bad_repeats_is_a_preflight_refusal_not_an_error(make):
    r, sink = make(piezo=MockPiezo(), tweezers=MockTweezers())
    failed = sink.wait(("preflight_failed", "finished", "error"),
                       start(r, {"pattern_id": "sq", "repeats": "two"}))
    assert failed.kind == "preflight_failed" and "repeats" in str(failed.data)


def test_mock_views_shift_the_sample_with_the_piezo_but_not_the_traps():
    import numpy as np

    from dino_autofocus.engine.backend import Frame
    from dino_autofocus.engine.tweezers import mock_views

    img = np.zeros((64, 64), np.uint16)
    img[10, 20] = 1000
    frame = Frame(img, 1.0, 10.0, camera="Kinetix_red", pixel_um=1.0)
    pz, tw = MockPiezo(), MockTweezers()
    pz.move(103.0, 102.0, 50.0, token=GUARD_TOKEN)  # +3 um x, +2 um y from the middle
    laser, sample = mock_views(tw, piezo=pz)(frame)
    assert sample.image[12, 23] >= 1000 and sample.image.shape == img.shape
    h, w = laser.image.shape
    assert laser.image[h // 2, w // 2] > 1000  # trap 0 still at the field centre
