"""The sample ops registered with the T-011 runner: permissions, preflight refusals, the
record-only ops, and the image check's light going off on the runner's exit path."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from dino_autofocus.engine import Command, Event
from dino_autofocus.engine.backend import Frame
from dino_autofocus.engine.operations.sample_ops import OPS, SampleSeat, install_sample_seat
from dino_autofocus.engine.runner import OPERATIONS, PERMISSIONS, AllowAll, Runner, RunnerConfig
from dino_autofocus.engine.sample import Sample, read_sample
from dino_autofocus.records import ExperimentSession, FolderStore, RecordsConfig

T = 5.0
USER = "operator@example.test"
SID = "20261001_1540_1"


class Collect:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._cond = threading.Condition()

    def __call__(self, ev: Event) -> None:
        with self._cond:
            self.events.append(ev)
            self._cond.notify_all()

    def wait(self, kind: str, op_id: str | None = None) -> Event:
        def find():
            return next((e for e in self.events
                         if e.kind == kind and (op_id is None or e.op_id == op_id)), None)

        with self._cond:
            assert self._cond.wait_for(lambda: find() is not None, T), (kind, op_id)
            return find()


@pytest.fixture
def world(tmp_path, fake):
    store = FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                      data_root=tmp_path / "data"))
    root = tmp_path / "samples"
    Sample(SID, root).dir.mkdir(parents=True)
    session = ExperimentSession.open(store, USER, SID)
    runner = Runner(fake, registry=OPERATIONS, control=AllowAll(),
                    config=RunnerConfig(position_interval_s=None))
    install_sample_seat(runner, SampleSeat(store, root, lambda sid: session
                                           if sid == session.session_id else None))
    sink = Collect()
    runner.subscribe(sink)
    runner.start()
    runner.set_experiment_session(session.session_id, time.time())
    yield runner, sink, store, root, session
    runner.shutdown("test teardown", timeout=T)
    assert runner.wait_idle(T)


def start(runner, session, op, **args) -> str:
    return runner.submit(Command("start", op=op, args=args, user_id=USER,
                                 session_id=session.session_id, control_grant="g-1"))


def test_every_sample_op_is_registered_with_a_permission():
    for op in OPS:
        assert OPERATIONS.get(op) is not None and op in PERMISSIONS
    assert not OPERATIONS.get("boundary_mark").exclusive
    assert OPERATIONS.get("loading_check_image").exclusive


def test_geometry_and_boundary_through_the_runner(world):
    runner, sink, store, root, session = world
    op_id = start(runner, session, "sample_geometry_set", sample_id=SID,
                  values={"sample_thickness_um": 80, "orientation": "upright"})
    done = sink.wait("finished", op_id)
    assert done.data["summary"]["loading"]["geometry"]["done"]
    for x in (1.0, 2.0):
        sink.wait("finished", start(runner, session, "boundary_mark", sample_id=SID,
                                    x_um=x, y_um=0.0))
    undo = start(runner, session, "boundary_undo", sample_id=SID)
    assert sink.wait("finished", undo).data["summary"]["boundary"] == [[1.0, 0.0]]
    assert sink.wait("map_changed", undo).data["n_points"] == 1
    assert read_sample(store, SID, root).boundary[0]["x_um"] == 1.0


def test_a_refusal_is_a_preflight_failure_and_writes_nothing(world):
    runner, sink, store, root, session = world
    op_id = start(runner, session, "sample_open", sample_id="20260930_1849_1")
    failed = sink.wait("preflight_failed", op_id)
    assert "one sample per session" in str(failed.data)
    op_id = start(runner, session, "sample_geometry_set", sample_id=SID,
                  values={"orientation": "sideways"})
    sink.wait("preflight_failed", op_id)
    assert read_sample(store, SID, root).n_events == 0


def test_the_image_check_lamp_goes_off_on_the_runners_exit(world, fake):
    runner, sink, store, root, session = world
    rng = np.random.default_rng(0)

    def snap():
        img = rng.normal(2700, 30, fake.shape)
        img[:, : fake.shape[1] // 2] -= 1500
        return Frame(img.clip(0, 4095).astype(np.uint16), time.time(), fake.exposure,
                     fake.x, fake.y, fake.z)

    fake.snap = snap
    op_id = start(runner, session, "loading_check_image", sample_id=SID)
    done = sink.wait("finished", op_id)
    assert done.data["summary"]["ok"] and done.data["summary"]["grade"] == "computed"
    assert fake.lights == {"DiaLamp": "0", "Aura": "0"}
    assert (Sample(SID, root).dir / done.data["summary"]["frame_ref"]).exists()
