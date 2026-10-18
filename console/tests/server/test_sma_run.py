"""agents/sma_run.py: reading a followed soft-matter-agents run's events.jsonl, its stop channel
and its frame tap (plan.md 11-25), against a stand-in with the same rules (sma_fake_run)."""

from __future__ import annotations

import json
import socket

import numpy as np
import pytest
from sma_fake_run import FakeSmaRun, sma_tree, tree_state

from dino_autofocus.agents import SmaFiles, sma_run


@pytest.fixture
def root(tmp_path):
    return sma_tree(tmp_path / "sma")


@pytest.fixture
def run(root):
    r = FakeSmaRun(root)
    yield r
    r.end()


# -- the events file ------------------------------------------------------------------------


def test_stream_reads_started_events_and_end(run):
    run.record(event="dispatch", element="LightPath")
    st = sma_run.read_stream(run.folder)
    assert st.run_id == run.run_id and st.plan_id.startswith("plan_microscope")
    assert st.running and st.ended_how is None
    assert st.stop_channel is not None and st.frame_tap is not None
    assert [e["event"] for e in st.events] == ["dispatch"]
    run.end("aborted_by_monitor")
    st = sma_run.read_stream(run.folder)
    assert not st.running and st.ended_how == "aborted_by_monitor"
    assert st.events[-1]["event"] == "run_ended"


def test_a_line_being_written_waits_and_a_bad_line_is_counted():
    head = {"event": "run_started", "run_id": "r1", "stop_channel": None}
    raw = (json.dumps(head) + "\n" + "not json\n" + '{"event": "a"}\n' + '{"event": "b"').encode()
    st = sma_run.parse_stream(raw, "r1")
    assert [e["event"] for e in st.events] == ["a"]
    assert st.partial_tail and st.bad_lines == 1


def test_not_followed(tmp_path):
    with pytest.raises(sma_run.NotFollowedError):
        sma_run.read_stream(tmp_path)
    (tmp_path / "events.jsonl").write_text('{"event": "dispatch"}\n', encoding="utf-8")
    with pytest.raises(sma_run.NotFollowedError):
        sma_run.read_stream(tmp_path)


@pytest.mark.parametrize("value", [
    {"host": "0.0.0.0", "port": 5000}, {"host": "10.0.0.2", "port": 5000},
    {"host": "localhost", "port": 5000}, {"host": "127.0.0.1", "port": 0},
    {"host": "127.0.0.1", "port": "5000"}, {"host": "127.0.0.1", "port": True}, None, "x",
])
def test_an_address_read_from_a_file_must_be_loopback(value):
    assert sma_run.Address.parse(value) is None


def test_store_lists_a_followed_run_by_its_stream(root, run):
    store = SmaFiles(root)
    (summary,) = store.list_runs("microscope")
    assert summary.run_id == run.run_id and summary.status == "running"
    assert summary.qid == "mic-20261005-001" and summary.created_at == "2026-10-05T10:00:00-07:00"
    run.end("stopped_from_outside")
    assert store.list_runs("microscope")[0].status == "stopped_from_outside"
    assert store.run_stream("microscope", run.run_id).ended_how == "stopped_from_outside"


def test_a_finished_followed_run_keeps_its_outcome_once_log_json_exists(root, run):
    """log.json of a followed run has no outcome field (card 063 step 4, 2026-10-07): the
    list reads run_ended's how from events.jsonl instead of showing nothing."""
    run.end("stopped_from_outside")
    (run.folder / "log.json").write_text(json.dumps(
        {"run_id": run.run_id, "plan_id": None, "t0_wall": "2026-10-07T22:34:24Z",
         "events": [{"event": "abort_end"}], "finished_at": "2026-10-07T22:34:42Z"}),
        encoding="utf-8")
    (summary,) = SmaFiles(root).list_runs("microscope")
    assert summary.status == "stopped_from_outside"
    assert summary.finished_at == "2026-10-07T22:34:42Z"


# -- the stop channel -----------------------------------------------------------------------


def test_stop_is_one_line_with_exact_keys(run):
    st = sma_run.read_stream(run.folder)
    result = sma_run.send_stop(st, "Abort pressed (by otto)")
    assert result.outcome == "begun"
    assert run.stops == ["the dino console: Abort pressed (by otto)"] and run.refused == []
    events = [e["event"] for e in sma_run.read_stream(run.folder).events]
    assert events[:2] == ["stop_requested", "abort_begin"]


def test_stop_line_fits_1024_bytes_whatever_the_reason():
    line = sma_run.stop_line("run-1", "é" * 5000)
    assert len(line) <= sma_run.STOP_MAX_BYTES and line.endswith(b"\n")
    assert line.count(b"\n") == 1
    msg = json.loads(line)
    assert set(msg) == {"stop", "reason"} and msg["stop"] == "run-1"
    # line breaks in a typed reason do not make a second line
    assert json.loads(sma_run.stop_line("run-1", "a\nb\r\nc"))["reason"].endswith("a b c")


def test_a_refused_stop_is_reported_as_refused(run):
    st = sma_run.read_stream(run.folder)
    other = sma_run.RunStream(**{**st.__dict__, "run_id": "someone-else"})
    result = sma_run.send_stop(other, "x")
    assert result.outcome == "refused" and run.stops == []
    assert run.refused and "not this run" in run.refused[0]


def test_slow_abort_is_no_answer_not_refused(root):
    r = FakeSmaRun(root, stop_reply_delay_s=0.6)
    try:
        st = sma_run.read_stream(r.folder)
        assert sma_run.send_stop(st, "x", reply_timeout_s=0.2).outcome == "no_answer"
    finally:
        r.end()


def test_ended_or_unreachable(run):
    st = sma_run.read_stream(run.folder)
    run.end()
    with pytest.raises(sma_run.UnreachableError):
        sma_run.send_stop(st, "x")  # the stream read before the end: the socket is gone
    with pytest.raises(sma_run.RunEndedError):
        sma_run.send_stop(sma_run.read_stream(run.folder), "x")


# -- the frame tap --------------------------------------------------------------------------


def test_frame_tap_no_frame_then_a_frame(run):
    st = sma_run.read_stream(run.folder)
    assert sma_run.latest_frame(st) is None
    img = (np.arange(64 * 48, dtype=np.uint16) % 4096).reshape(48, 64)
    run.put(img, {"ImageNumber": 7, "camera": "Andor"}, 12.5)
    got = sma_run.latest_frame(st)
    assert got.shape == [48, 64] and got.dtype == "uint16" and got.t_mono == 12.5
    assert got.metadata["ImageNumber"] == 7
    np.testing.assert_array_equal(got.pixels, img)
    assert run.refused == []


def test_no_tap_announced(root):
    r = FakeSmaRun(root, run_id="run-notap", tap=False)
    try:
        with pytest.raises(sma_run.NotFollowedError):
            sma_run.latest_frame(sma_run.read_stream(r.folder))
    finally:
        r.end()


def test_reading_and_stopping_write_nothing_in_the_tree(root, run):
    """The console's side: no file appears, and only the run itself appends to its events."""
    before = tree_state(root)
    store = SmaFiles(root)
    store.list_runs("microscope")
    st = store.run_stream("microscope", run.run_id)
    sma_run.latest_frame(st)
    sma_run.send_stop(st, "x")
    after = tree_state(root)
    assert set(after) == set(before)
    changed = {k for k in before if before[k] != after[k]}
    assert changed <= {str(run.folder.relative_to(root) / "events.jsonl")}


def test_nothing_connects_to_a_stop_channel_unless_asked(root, run):
    """OD-30: reading the stream, the frame, and a viewer going away send no stop."""
    store = SmaFiles(root)
    for _ in range(3):
        st = store.run_stream("microscope", run.run_id)
        sma_run.latest_frame(st)
    assert run.stop_server.connections == 0 and run.stops == []


def test_send_stop_connects_only_to_the_announced_loopback_port(run, monkeypatch):
    seen = []
    real = socket.create_connection

    def spy(addr, *a, **kw):
        seen.append(addr)
        return real(addr, *a, **kw)

    monkeypatch.setattr(socket, "create_connection", spy)
    st = sma_run.read_stream(run.folder)
    sma_run.send_stop(st, "x")
    assert seen == [("127.0.0.1", st.stop_channel.port)]
