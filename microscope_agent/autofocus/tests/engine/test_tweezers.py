"""Optical tweezers (card T-20261002-2205 stage 3): mock traps, the TrapAxis guard, the
trap_move / trap_set operations through the runner, and the mock live stream. Mock only:
nothing is sent to Tweez300."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from dino_autofocus.engine import Command, Event
from dino_autofocus.engine.backend import GUARD_TOKEN, UnguardedMotion
from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.guards import GuardError, TrapAxis
from dino_autofocus.engine.operations import trap  # noqa: F401 - registers the ops
from dino_autofocus.engine.runner import OPERATIONS, AllowAll, Runner, RunnerConfig
from dino_autofocus.engine.stream import BackendStream
from dino_autofocus.engine.tweezers import (
    MockTweezers,
    TweezersInfo,
    draw_traps,
    mock_views,
    state_of,
)

T = 5.0
USER, SESSION = "operator@example.test", "20261002-0900-operator"


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

    def build(tweezers, *, backend=None):
        backend = backend or MockBackend(seed=1)
        backend.open()
        r = Runner(backend, registry=OPERATIONS, control=AllowAll(), tweezers=tweezers,
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


def start(r: Runner, op: str, args: dict) -> str:
    return r.submit(Command("start", op=op, args=args, user_id=USER, session_id=SESSION,
                            control_grant="g-1"))


class RealTweezers(MockTweezers):
    """Stands in for Tweez300: reports bench=True."""

    def info(self) -> TweezersInfo:
        return TweezersInfo("tweez300", 4, bench=True)


# -- device and guard ------------------------------------------------------------------


def test_mock_traps_need_the_guards_token_and_stay_in_range():
    tw = MockTweezers()
    with pytest.raises(UnguardedMotion):
        tw.move_trap(0, 1.0, 1.0, 0.0, token=object())
    with pytest.raises(ValueError, match="outside"):
        tw.move_trap(0, 61.0, 0.0, 0.0, token=GUARD_TOKEN)
    with pytest.raises(ValueError, match="no trap"):
        tw.set_trap(9, True, token=GUARD_TOKEN)
    assert tw.move_trap(1, 2.0, -3.0, 0.5, token=GUARD_TOKEN).x_um == 2.0
    state = state_of(tw)
    assert state["kind"] == "mock" and state["bench"] is False and len(state["traps"]) == 4


def test_trap_axis_moves_reads_back_and_records():
    seen: list[Event] = []
    axis = TrapAxis(MockTweezers(), bench_lock=None, sink=seen.append, op_id="op1")
    rec = axis.move(0, 4.0, -2.0)
    assert rec["read_um"] == [4.0, -2.0, 0.0] and seen[-1].kind == "motion"
    assert axis.set_on(2, True)["read_on"] is True
    with pytest.raises(GuardError, match="outside"):
        axis.move(0, 0.0, -61.0)


@pytest.mark.parametrize("lock", [None, "LOCKED: bench motion locked (T-036)"])
def test_real_tweezers_stay_still_while_the_bench_lock_is_on(lock):
    tw = RealTweezers()
    with pytest.raises(GuardError, match="bench motion is locked"):
        TrapAxis(tw, bench_lock=lock).move(0, 1.0, 1.0)
    assert tw.traps()[0].x_um == 0.0


def test_no_tweezers_is_refused():
    with pytest.raises(GuardError, match="no tweezers"):
        TrapAxis(None, bench_lock=None).move(0, 0.0, 0.0)


# -- operations through the runner -----------------------------------------------------


def test_trap_move_and_set_run_on_the_mock(make):
    tw = MockTweezers()
    r, sink = make(tw)
    done = sink.wait(("finished", "error", "preflight_failed"),
                     start(r, "trap_move", {"trap": 1, "x_um": 5.5, "y_um": -4.0}))
    assert done.kind == "finished", done.data
    assert tw.traps()[1].x_um == 5.5 and tw.traps()[1].y_um == -4.0
    done = sink.wait(("finished", "error", "preflight_failed"),
                     start(r, "trap_set", {"trap": 1, "on": True}))
    assert done.kind == "finished" and tw.traps()[1].on is True
    snap = r.snapshot()["tweezers"]
    assert snap["traps"][1]["x_um"] == 5.5 and snap["traps"][1]["on"] is True


@pytest.mark.parametrize(("args", "says"), [
    ({"trap": 7, "x_um": 0, "y_um": 0}, "no such trap"),
    ({"trap": 0, "x_um": 80, "y_um": 0}, "outside"),
    ({"trap": 0, "x_um": 0, "y_um": 0, "speed": 3}, "unknown arguments"),
    ({"trap": 0, "x_um": 1.0}, "y_um is missing"),
])
def test_trap_move_preflight_refuses(make, args, says):
    tw = MockTweezers()
    r, sink = make(tw)
    failed = sink.wait(("preflight_failed", "finished", "error"), start(r, "trap_move", args))
    assert failed.kind == "preflight_failed" and says in str(failed.data)
    assert tw.traps()[0].x_um == 0.0


def test_without_tweezers_the_ops_refuse(make):
    r, sink = make(None)
    failed = sink.wait(("preflight_failed", "finished", "error"),
                       start(r, "trap_set", {"trap": 0, "on": False}))
    assert failed.kind == "preflight_failed" and "no tweezers" in str(failed.data)
    assert r.snapshot()["tweezers"] is None


# -- mock pictures and the live stream -------------------------------------------------


def test_draw_traps_puts_a_spot_where_the_trap_is():
    img = np.zeros((101, 101), np.uint16)
    traps = MockTweezers().traps()  # trap 0 on at the centre; others off
    out = draw_traps(img, traps, 0.5, peak=1000.0)
    assert np.unravel_index(out.argmax(), out.shape) == (50, 50) and out.max() > 900
    assert int(out[0, 0]) == 0


def test_mock_views_add_a_laser_camera():
    tw = MockTweezers()
    mock = MockBackend(seed=1)
    mock.open()
    frame = mock.snap()
    frame = type(frame)(**{**frame.__dict__, "pixel_um": 0.5})
    got = mock_views(tw)(frame)
    # the laser camera first, the sample camera last (what latest_frame() then holds)
    assert [f.camera for f in got] == ["Kinetix_blue", "Kinetix_red"]
    h, w = got[0].image.shape
    assert got[0].image[h // 2, w // 2] > 1000  # trap 0's laser spot at the field centre


def test_stream_publishes_until_paused_and_only_while_wanted():
    mock = MockBackend(seed=1)
    mock.open()
    mock.world.set_roi(200)  # small frames: fast enough for a test
    got: list = []
    watching = threading.Event()
    s = BackendStream.for_backend(mock, interval_s=0.05, pixel_um=lambda: 1.0,
                                  wanted=watching.is_set)
    s.attach(got.append)
    try:
        time.sleep(0.3)
        assert got == []  # nobody watches: nothing rendered
        assert s.running() and not s.live() and not mock.streaming()
        mock.snap()  # and an operation can snap for itself
        watching.set()
        deadline = time.time() + T
        while len(got) < 2 and time.time() < deadline:
            time.sleep(0.02)
        assert len(got) >= 2 and got[0].pixel_um == 1.0 and s.live()
        s.pause()
        assert not s.running() and not s.live()
        assert not mock.streaming()
        mock.snap()  # an operation may snap while the stream is paused
        n = len(got)
        time.sleep(0.3)
        assert len(got) == n
        s.resume()
        deadline = time.time() + T
        while len(got) == n and time.time() < deadline:
            time.sleep(0.02)
        assert len(got) > n
    finally:
        s.stop()
    assert not s.running() and not mock.streaming()


def test_the_stream_refuses_the_bench():
    class Bench:
        def info(self):
            return TweezersInfo("mm-real", 0)  # no `kind` in SIMULATED_KINDS: the bench

    with pytest.raises(ValueError, match="mock backend only"):
        BackendStream.for_backend(Bench())

    class Demo:
        def info(self):
            return type("Info", (), {"kind": "mm-demo", "bench": False})()

    with pytest.raises(ValueError, match="mock backend only"):
        BackendStream.for_backend(Demo())


def test_tweez300_is_not_wired_and_sends_nothing(monkeypatch):
    import socket

    from dino_autofocus.engine.backends.tweez300 import Tweez300NotWired, Tweez300Tweezers

    def no_socket(*a, **k):
        raise AssertionError("Tweez300 adapter opened a socket")

    monkeypatch.setattr(socket, "socket", no_socket)
    tw = Tweez300Tweezers("tcp", port=5000)
    assert tw.info().bench is True and "not wired" in tw.info().notes["state"]
    with pytest.raises(Tweez300NotWired):
        tw.traps()
    with pytest.raises(UnguardedMotion):
        tw.move_trap(0, 0.0, 0.0, 0.0, token=object())
    with pytest.raises(GuardError, match="bench motion is locked"):
        TrapAxis(tw, bench_lock="LOCKED: bench motion locked (T-036)").move(0, 0.0, 0.0)
    state = state_of(tw)
    assert state["kind"] == "tweez300" and state["traps"] == [] and "not wired" in state["error"]


def test_trap_ops_have_a_gate_row_that_asks_for_the_camera():
    from dino_autofocus.engine import gates

    for op in ("trap_move", "trap_set"):
        ok, why = gates.check(None, op, {})
        assert not ok and why == [gates.NOT_SCANNED]  # a row exists: not "no gate rule"
        row = next(g for g in gates.GATES if g.op == op)
        assert row.devices == ("camera",)


def test_with_the_mock_views_latest_frame_stays_the_sample_camera():
    mock = MockBackend(seed=1)
    mock.open()
    mock.world.set_roi(200)
    r = Runner(mock, registry=OPERATIONS)
    frame = mock.snap()
    frame = type(frame)(**{**frame.__dict__, "pixel_um": 0.5})
    for f in mock_views(MockTweezers())(frame):
        r.publish_frame(f)
    assert r.latest_frame()[1]["camera"] == "Kinetix_red"  # what edge_trace grabs
    assert sorted(r.latest_frames()) == ["Kinetix_blue", "Kinetix_red"]


def test_a_paused_stream_stays_off_when_a_viewer_arrives():
    mock = MockBackend(seed=1)
    mock.open()
    mock.world.set_roi(200)
    watching = threading.Event()
    s = BackendStream.for_backend(mock, interval_s=0.05, wanted=watching.is_set)
    s.attach(lambda f: None)
    try:
        assert s.running()  # unwatched but not paused: the runner pauses it for a snapping op
        s.pause()
        watching.set()  # someone opens the live view mid-operation
        time.sleep(0.3)
        assert not mock.streaming()
        mock.snap()  # the operation's snap still works
    finally:
        s.stop()
