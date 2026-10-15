"""The server's engine seams with the real runner (T-011): sample seat (T-027) and the typed
snapshot. The runner is not started, so nothing touches a backend."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dino_autofocus.engine.operations.sample_ops import OPS, SampleSeat
from dino_autofocus.engine.runner import Runner, RunnerConfig
from dino_autofocus.records import FolderStore, RecordsConfig


@pytest.fixture
def runner():
    return Runner(object(), config=RunnerConfig(position_interval_s=None))


@pytest.fixture
def records(tmp_path):
    return FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                     data_root=tmp_path / "data"))


def test_sample_ops_registered_and_seat_installed(runner, records, make_client, tmp_path):
    c = make_client(runner, records=records, samples_root=tmp_path / "samples")
    seat = runner.sample_seat
    assert isinstance(seat, SampleSeat)
    assert seat.store is records and seat.samples_root == tmp_path / "samples"
    state = c.get("/api/state")
    assert state.status_code == 200  # the real runner's snapshot fits the typed model
    assert set(OPS) <= set(state.json()["operations"])
    assert set(OPS) <= set(state.json()["permissions"])


def test_one_session_object_for_every_writer(runner, records, make_client):
    c = make_client(runner, records=records)
    session = SimpleNamespace(info=SimpleNamespace(session_id="s-1"))
    assert runner.sample_seat.session_for("s-1") is None  # nothing open yet
    c.app.state.sessions.set(session)
    assert runner.sample_seat.session_for("s-1") is session
    assert runner.sample_seat.session_for("s-2") is None
    c.app.state.sessions.clear()
    assert runner.sample_seat.session_for("s-1") is None


def test_no_records_no_seat(runner, make_client):
    make_client(runner)
    assert not hasattr(runner, "sample_seat")


def test_permissions_ask_the_real_runner(runner, records, make_client):
    got = make_client(runner, records=records, control=True).get(
        "/api/permissions?ops=sample_open,abort").json()
    assert got["abort"]["allowed"] is True
    assert got["sample_open"] == {"allowed": False, "reason": "the engine is not running",
                                  "code": None}
