"""T-009j: where operation records go. In the open experiment session they go into it (and
are committed with it); otherwise to <data root>/engine_records, outside git."""

from __future__ import annotations

import json
import queue
import time
from pathlib import Path

import numpy as np
import pytest

from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.backends.replay import ReplayBackend
from dino_autofocus.engine.events import Command, Event, queue_sink
from dino_autofocus.engine.runner import AllowAll, RunnerConfig
from dino_autofocus.records import ExperimentSession, FolderStore, RecordsConfig
from dino_autofocus.server import __main__ as launcher
from dino_autofocus.server.api import SessionSeat
from dino_autofocus.server.app import build_runner, session_records

USER = "otto@example.test"
T = 20.0


@pytest.fixture
def store(tmp_path):
    return FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                     data_root=tmp_path / "data"))


def lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def meta(op: str, session_id: str | None) -> dict:
    return {"op": op, "op_id": f"{op}_1", "origin": "human", "user_id": USER,
            "session_id": session_id, "proposal_id": None, "conversation_id": None,
            "confirmed_by": USER, "confirmed_at": 1.0, "record_prefix": None}


def test_op_in_the_open_session_is_recorded_in_it(store, tmp_path):
    session = ExperimentSession.open(store, USER, "20261001_1200_1")
    seat = SessionSeat()
    seat.set(session)
    rec = session_records(seat, tmp_path / "engine_records")(meta("hardware_scan",
                                                                  session.session_id))
    rec.event(Event("progress", "hardware_scan_1", {"i": 1}))
    rec.close({"state": "finished", "summary": {"ok": True}})
    got = lines(session.layout.operation_record("hardware_scan"))
    assert [x["event"] for x in got] == ["operation_started", "engine_event",
                                         "operation_finished"]
    assert got[1]["kind"] == "progress" and got[1]["data"] == {"i": 1}
    assert got[2]["summary"]["state"] == "finished"
    assert not (tmp_path / "engine_records").exists()  # nothing outside the session


def test_no_session_goes_to_the_engine_records_folder(store, tmp_path):
    rec = session_records(SessionSeat(), tmp_path / "engine_records")(meta("status", None))
    rec.event(Event("progress", "status_1", {"i": 1}))
    rec.close({"state": "finished"})
    folders = list((tmp_path / "engine_records").iterdir())
    assert len(folders) == 1 and (folders[0] / "log.jsonl").is_file()


def test_another_sessions_op_is_not_written_into_the_open_one(store, tmp_path):
    session = ExperimentSession.open(store, USER, "20261001_1200_1")
    seat = SessionSeat()
    seat.set(session)
    rec = session_records(seat, tmp_path / "engine_records")(meta("status", "other-session"))
    rec.close({"state": "finished"})
    assert not session.layout.operation_record("status").exists()
    assert (tmp_path / "engine_records").is_dir()


def test_session_closed_under_the_op_falls_back_to_the_folder(store, tmp_path):
    session = ExperimentSession.open(store, USER, "20261001_1200_1")
    seat = SessionSeat()
    seat.set(session)
    rec = session_records(seat, tmp_path / "engine_records")(meta("scan_4x", session.session_id))
    session.close(note="closed by the operator")
    rec.event(Event("progress", "scan_4x_1", {"i": 2}))  # must not raise into the engine
    rec.close({"state": "aborted"})
    folders = list((tmp_path / "engine_records").iterdir())
    assert len(folders) == 1
    assert rec.dir == str(folders[0])


def test_through_the_runner(store, tmp_path):
    """A real Runner with the server's record seat: an op run in the open session lands in
    the session's records/<op>.jsonl."""
    session = ExperimentSession.open(store, USER, "20261001_1200_1")
    seat = SessionSeat()
    seat.set(session)
    runner, _ = build_runner(MockBackend(seed=0), records_root=tmp_path / "records",
                             control=AllowAll(), config=RunnerConfig(position_interval_s=None),
                             records=session_records(seat, tmp_path / "engine_records"))
    events: queue.Queue = queue.Queue()
    runner.subscribe(queue_sink(events))
    runner.start()
    try:
        runner.set_experiment_session(session.session_id, time.time())
        op_id = runner.submit(Command("start", op="hardware_scan", args={"piezo_port": ""},
                                      user_id=USER, control_grant="g"))
        end = time.monotonic() + T
        while time.monotonic() < end:
            ev = events.get(timeout=T)
            if ev.op_id == op_id and ev.kind in ("finished", "error", "aborted"):
                break
        assert ev.kind == "finished", ev.data
    finally:
        runner.shutdown("test teardown", timeout=T)
        assert runner.wait_idle(T)
    got = lines(session.layout.operation_record("hardware_scan"))
    assert got[0]["event"] == "operation_started" and got[0]["op_id"] == op_id
    assert got[-1]["event"] == "operation_finished"
    assert not (tmp_path / "engine_records").exists()


# -- replay start-up ------------------------------------------------------------------------


def tiny_stack(folder: Path) -> Path:
    """The smallest source load_stacks reads: one find_particle field (3 planes, 8 x 8)."""
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / "find_particle_t_field00.npz"
    rng = np.random.default_rng(0)
    np.savez(p, stack=rng.random((3, 8, 8)).astype(np.float32),
             z_um=np.array([2990.0, 3000.0, 3010.0]), xy_um=np.array([0.0, 0.0]))
    return p


def test_replay_starts_on_a_source_and_uses_the_mock_root(tmp_path):
    source = tiny_stack(tmp_path / "stacks")
    b = launcher.build(launcher.parse_args([
        "--backend", "replay", "--replay-source", str(source),
        "--records-root", str(tmp_path / "records"), "--config-dir", str(tmp_path / "config"),
        "--web-dist", str(tmp_path / "no-web-dist")]))
    try:
        assert isinstance(b.backend, ReplayBackend) and b.name == "replay"
        assert b.backend.info().bench is False
        assert "hardware_scan" in b.engine.snapshot()["operations"]
    finally:
        b.close("test")
    assert launcher.record_roots(None, bench=False)[0].name.endswith("-mock")


def test_replay_needs_a_source(tmp_path):
    with pytest.raises(SystemExit, match="needs --replay-source"):
        launcher.open_backend("replay")
    with pytest.raises(SystemExit, match="'replay' cannot open on this PC"):
        launcher.open_backend("replay", replay_source=str(tmp_path / "missing"))
