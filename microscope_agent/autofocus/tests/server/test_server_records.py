"""T-009e: the records store on app.state, crash-left sessions closed at start-up, and the
AutoCommitter flushed and stopped at shutdown (after the engine)."""

from __future__ import annotations

import pytest

from dino_autofocus.records import ExperimentSession, FolderStore, RecordsConfig
from dino_autofocus.server.app import INTERRUPTED_NOTE

USER = "otto@example.test"
SAMPLE = "20261001_1200_1"


@pytest.fixture
def records(tmp_path):
    return FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                     data_root=tmp_path / "data"))


class Order:
    """One list both fakes write to, so the test sees what came first."""

    def __init__(self) -> None:
        self.seen: list[str] = []


class FakeCommitter:
    def __init__(self, order: Order) -> None:
        self.order = order

    def submit(self, session_id, message, author) -> None:
        self.order.seen.append(f"commit {message}")

    def flush(self, timeout_s=None) -> bool:
        self.order.seen.append("flush")
        return True

    def stop(self, timeout_s=None) -> None:
        self.order.seen.append("stop")


def test_records_store_on_app_state(engine, make_client, records):
    assert make_client(engine, records=records).app.state.records is records
    assert make_client(engine).app.state.records is None


def test_open_session_left_by_a_crash_is_closed_at_start_up(engine, make_client, records):
    left = ExperimentSession.open(records, USER, SAMPLE)
    done = ExperimentSession.open(records, USER, SAMPLE)
    done.close(note="finished normally")
    told = []
    engine.set_experiment_session = lambda *a, **kw: told.append(a)
    c = make_client(engine, records=records)
    assert ExperimentSession.load(records, left.session_id).writable  # not before start-up
    with c:
        info = ExperimentSession.load(records, left.session_id).info
        assert (info.status, info.close_note) == ("closed", INTERRUPTED_NOTE)
        assert c.app.state.interrupted_sessions == [left.session_id]
        assert c.app.state.sessions.current is None  # the Sessions holder starts empty
        assert told == []  # never handed to the runner
        # a session closed before is left as it was
        assert ExperimentSession.load(records, done.session_id).info.close_note == \
            "finished normally"


def test_one_bad_session_does_not_stop_start_up(engine, make_client, records, monkeypatch):
    first = ExperimentSession.open(records, USER, SAMPLE)
    second = ExperimentSession.open(records, USER, SAMPLE)
    real_load = ExperimentSession.load

    def load(store, sid, committer=None):
        if sid == first.session_id:
            raise OSError("session.json unreadable")
        return real_load(store, sid, committer=committer)

    monkeypatch.setattr(ExperimentSession, "load", staticmethod(load))
    with make_client(engine, records=records) as c:
        assert c.app.state.interrupted_sessions == [second.session_id]


def test_committer_flushed_and_stopped_after_the_engine(engine, make_client, records):
    order = Order()
    real_shutdown = engine.shutdown

    def shutdown(reason):
        order.seen.append("engine")
        real_shutdown(reason)

    engine.shutdown = shutdown
    with make_client(engine, records=records, committer=FakeCommitter(order)):
        assert order.seen == []
    assert order.seen == ["engine", "flush", "stop"]


def test_crash_close_commits_through_the_committer(engine, make_client, records):
    ExperimentSession.open(records, USER, SAMPLE)
    order = Order()
    with make_client(engine, records=records, committer=FakeCommitter(order)):
        (commit,) = order.seen
        assert commit.startswith("commit ") and commit.endswith(": close session")
