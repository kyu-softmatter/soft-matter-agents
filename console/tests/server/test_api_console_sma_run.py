"""The console's routes for a run soft-matter-agents executes (plan.md 11-25): follow its
events, show its latest frame, and Abort it on its loopback stop channel. The Abort has the
stop rules (loopback always; remote viewer when remote abort is on, D13)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from server_fakes import OPERATOR, VIEWER
from sma_fake_run import FakeSmaRun, sma_tree, tree_state

from dino_autofocus.agents import SmaFiles
from dino_autofocus.agents.mock_store import MOCK_DATA
from dino_autofocus.server.api import REFUSAL_HEADER

MIC_RUN = "run-20260924-003"  # the mock sample's microscope run: not followed


def refusal(r) -> tuple[int, str]:
    assert r.headers[REFUSAL_HEADER] == r.json()["detail"]["code"]
    return r.status_code, r.json()["detail"]["code"]


@pytest.fixture
def root(tmp_path):
    return sma_tree(tmp_path / "sma")


@pytest.fixture
def run(root):
    r = FakeSmaRun(root)
    yield r
    r.end()


@pytest.fixture
def client(engine, make_client, root):
    return lambda **kw: make_client(engine, agent_store=SmaFiles(root), **kw)


def base(run) -> str:
    return f"/api/console/runs/microscope/{run.run_id}"


def test_stream_running_then_since_then_ended(client, run):
    c = client()
    run.record(event="dispatch", element="Shutter")
    s = c.get(f"{base(run)}/stream").json()
    assert s["followed"] and s["state"] == "running" and s["can_stop"] and s["frame_tap"]
    assert s["stop_unavailable"] is None and s["total"] == 1
    assert [e["event"] for e in s["events"]] == ["dispatch"]
    run.record(event="readback", element="Shutter")
    s2 = c.get(f"{base(run)}/stream", params={"since": s["total"]}).json()
    assert [e["event"] for e in s2["events"]] == ["readback"] and s2["total"] == 2
    run.end("completed")
    s3 = c.get(f"{base(run)}/stream").json()
    assert s3["state"] == "ended" and s3["ended_how"] == "completed"
    assert not s3["can_stop"] and "has ended" in s3["stop_unavailable"] and not s3["frame_tap"]


def test_a_run_not_followed_says_why_it_cannot_be_stopped(engine, make_client):
    c = make_client(engine, agent_store=SmaFiles(MOCK_DATA))
    s = c.get(f"/api/console/runs/microscope/{MIC_RUN}/stream").json()
    assert s["state"] == "not_followed" and not s["can_stop"]
    assert "operator terminal" in s["stop_unavailable"]
    r = c.post(f"/api/console/runs/microscope/{MIC_RUN}/stop", json={"reason": "x"})
    assert refusal(r) == (409, "not_followed")
    assert c.get("/api/console/runs/microscope/nope/stream").status_code == 404


def test_mock_store_reads_streams_too(engine, make_client):
    s = make_client(engine).get(f"/api/console/runs/microscope/{MIC_RUN}/stream").json()
    assert s["state"] == "not_followed"


def test_local_operator_aborts_and_it_is_audited(client, run, seat):
    c = client()
    r = c.post(f"{base(run)}/stop", json={"reason": "wrong well"})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "begun"
    assert run.stops == [f"the dino console: wrong well (by {OPERATOR})"]
    audit = [e for e in seat.audit.entries() if e.get("command") == "sma_stop"]
    assert audit and audit[-1]["run_id"] == run.run_id and audit[-1]["outcome"] == "begun"


def test_loopback_stop_works_without_a_login(client, run):
    r = client(login=None).post(f"{base(run)}/stop", json={})
    assert r.status_code == 200 and r.json()["outcome"] == "begun"
    assert run.stops == ["the dino console: Abort pressed (by the microscope PC)"]


def test_remote_viewer_may_abort_when_remote_abort_is_on(client, run):
    c = client(remote=True, remote_view=True, login=VIEWER)
    r = c.post(f"{base(run)}/stop", json={"reason": "smoke"})
    assert r.status_code == 200 and r.json()["outcome"] == "begun"


def test_remote_abort_off_or_logged_out_is_refused(client, run):
    off = client(remote=True, remote_view=True, login=VIEWER, remote_abort=False)
    assert refusal(off.post(f"{base(run)}/stop", json={})) == (403, "remote_view")
    anon = client(remote=True, remote_view=True, login=None)
    assert refusal(anon.post(f"{base(run)}/stop", json={})) == (401, "login_required")
    assert run.stops == [] and run.stop_server.connections == 0


def test_stop_after_the_end_and_simulation(client, run):
    c = client()
    run.end("aborted_by_monitor")
    assert refusal(c.post(f"{base(run)}/stop", json={})) == (409, "run_ended")
    r = c.post("/api/console/runs/simulation/anything/stop", json={})
    assert refusal(r) == (409, "not_followed")


def test_frame_none_then_jpeg(client, run):
    c = client()
    assert c.get(f"{base(run)}/frame").status_code == 204
    run.put((np.arange(300 * 200, dtype=np.uint16) % 1000).reshape(200, 300), {"camera": "c1"}, 3.0)
    r = c.get(f"{base(run)}/frame")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"
    head = json.loads(r.headers["X-DinoAF-Frame"])
    assert head["shape"] == [200, 300] and head["t_mono"] == 3.0


def test_frame_after_end_is_refused(client, run):
    c = client()
    run.end()
    assert refusal(c.get(f"{base(run)}/frame")) == (409, "run_ended")


def test_viewing_sends_no_stop_and_writes_nothing(client, run, root):
    """OD-30 and the one-way rule: polling and frames, then the viewer leaves; no stop, and
    no file in the soft-matter-agents tree changes."""
    before = tree_state(root)
    c = client()
    for _ in range(3):
        c.get(f"{base(run)}/stream")
        c.get(f"{base(run)}/frame")
    c.close()
    assert run.stop_server.connections == 0
    assert tree_state(root) == before
