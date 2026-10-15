"""`z_retract` through the T-011 runner: moves to z_safe with readback, a no-op at z_safe,
refused while the bench motion lock is on and without control or session (T-039)."""

from __future__ import annotations

import threading
import time

import pytest

from dino_autofocus.engine import Command, Event
from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.operations import z_retract  # noqa: F401 - registers the op
from dino_autofocus.engine.runner import (
    OPERATIONS,
    AllowAll,
    CommandRefused,
    DenyAll,
    Runner,
    RunnerConfig,
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

    def build(backend, *, control=None, session: str | None = SESSION):
        r = Runner(backend, registry=OPERATIONS, control=control or AllowAll(),
                   config=RunnerConfig(position_interval_s=None))
        sink = Collect()
        r.subscribe(sink)
        r.start()
        if session:
            r.set_experiment_session(session, time.time())
        made.append(r)
        return r, sink

    yield build
    for r in made:
        r.shutdown("test teardown", timeout=T)
        assert r.wait_idle(T)


def start(r: Runner) -> str:
    return r.submit(Command("start", op="z_retract", user_id=USER, session_id=SESSION,
                            control_grant="g-1"))


def bench(fake, notes=None):
    real = fake.info

    def info():
        i = real()
        i.bench = True  # a bench-flagged FakeBackend (T-015b)
        i.notes = {**(i.notes or {}), **(notes or {})}
        return i
    fake.info = info
    return fake


def test_moves_to_z_safe_and_verifies_on_a_bench_flagged_fake(make, fake):
    r, sink = make(bench(fake, {"bench_motion": "UNLOCKED"}))
    fake.z = 2950.0
    done = sink.wait(("finished", "error"), start(r))
    assert done.kind == "finished"
    s = done.data["summary"]
    assert (s["commanded_um"], s["readback_um"], s["verified"], s["moved"]) == (0.0, 0.0,
                                                                              True, True)
    assert s["from_um"] == 2950.0 and fake.z == 0.0
    assert [c for c in fake.calls if c[0] == "move_z"] == [("move_z", 0.0)]


def test_moves_to_z_safe_on_the_mock_backend(make):
    mock = MockBackend(seed=1)
    mock.open()
    r, sink = make(mock)
    done = sink.wait(("finished", "error"), start(r))
    assert done.kind == "finished", done.data
    assert done.data["summary"]["readback_um"] == pytest.approx(0.0, abs=0.25)
    assert mock.positions().z_um == pytest.approx(0.0, abs=0.25)


def test_already_at_z_safe_is_a_no_op_success(make, fake):
    fake.z = 0.0
    r, sink = make(bench(fake))
    done = sink.wait(("finished", "error"), start(r))
    assert done.kind == "finished" and done.data["summary"]["moved"] is False
    assert done.data["summary"]["readback_um"] == 0.0
    assert not any(c[0] == "move_z" for c in fake.calls)


def test_refused_while_the_bench_motion_lock_is_on(make, fake):
    r, sink = make(bench(fake, {"bench_motion": "LOCKED: bench motion locked (T-036)"}))
    op_id = start(r)
    failed = sink.wait(("preflight_failed", "finished", "error"), op_id)
    assert failed.kind == "preflight_failed" and "locked" in str(failed.data)
    assert fake.z == 2900.0 and not any(c[0] == "move_z" for c in fake.calls)


@pytest.mark.parametrize("why", ["no control", "no session"])
def test_refused_without_control_or_session(make, fake, why):
    if why == "no control":
        r, _ = make(fake, control=DenyAll())
    else:
        r, _ = make(fake, session=None)
    with pytest.raises(CommandRefused):
        start(r)
    assert not any(c[0] == "move_z" for c in fake.calls)


def test_a_readback_mismatch_fails_with_commanded_and_read(make, fake):
    fake.z_readback_offset_um = 1.5  # ZDrive reads 1.5 um off what it was sent
    r, sink = make(bench(fake))
    done = sink.wait(("finished", "error"), start(r))
    assert done.kind == "error"
    text = str(done.data)
    assert "commanded 0.000" in text and "read 1.500" in text



def test_pfs_is_switched_off_before_the_z_move(make, fake):
    fake.z, fake.pfs_enabled, fake.pfs_in_range = 2950.0, True, "In Range"
    real_off = fake.pfs_off

    def pfs_off(*, token):
        fake.calls.append(("pfs_off",))
        rb = real_off(token=token)
        fake.pfs_in_range = "Out of Range"
        return rb
    fake.pfs_off = pfs_off
    r, sink = make(bench(fake))
    done = sink.wait(("finished", "error"), start(r))
    assert done.kind == "finished", done.data
    order = [c[0] for c in fake.calls if c[0] in ("pfs_off", "move_z")]
    assert order == ["pfs_off", "move_z"]
    assert done.data["summary"]["pfs"] == {  # as found, then after the move
        "enabled_before": True, "in_range_before": "In Range",
        "enabled": False, "in_range": "Out of Range"}
    assert not fake.pfs_enabled


def test_an_unreadable_pfs_refuses_before_any_move(make, fake):
    def broken():
        raise OSError("PFS not answering")
    fake.pfs = broken
    r, sink = make(bench(fake))
    failed = sink.wait(("preflight_failed", "finished", "error"), start(r))
    assert failed.kind == "preflight_failed" and "PFS state unreadable" in str(failed.data)
    assert not any(c[0] == "move_z" for c in fake.calls)
