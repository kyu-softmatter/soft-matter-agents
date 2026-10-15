"""Live view from the console (soft-matter-agents card 062, agreed shapes of 2026-10-07):
`GET /api/console/live`, `POST /api/console/live/on` naming an approved list by sha256, and
"Live off" as the run's own stop. Against a stand-in host with the agreed rules."""

from __future__ import annotations

import json

import pytest
from server_fakes import OPERATOR, VIEWER
from sma_fake_run import FakeLiveHost, sma_tree, tree_state, write_live_list

from dino_autofocus.agents import SmaFiles, sma_live
from dino_autofocus.server.__main__ import parse_args
from dino_autofocus.server.api import REFUSAL_HEADER


def refusal(r) -> tuple[int, str]:
    assert r.headers[REFUSAL_HEADER] == r.json()["detail"]["code"]
    return r.status_code, r.json()["detail"]["code"]


@pytest.fixture
def root(tmp_path):
    return sma_tree(tmp_path / "sma")


@pytest.fixture
def addr_file(tmp_path):
    return tmp_path / "localappdata" / "soft-matter-agents" / "live_host.json"


@pytest.fixture
def host(root, addr_file):
    h = FakeLiveHost(root, addr_file)
    yield h
    h.close()


@pytest.fixture
def client(engine, make_client, root, addr_file):
    return lambda **kw: make_client(engine, agent_store=SmaFiles(root),
                                    live_host_file=addr_file, **kw)


# -- the module -------------------------------------------------------------------------------


def test_lists_are_files_marked_as_live_view_list_artifacts(root):
    sha = write_live_list(root)
    write_live_list(root, "appr-mic-x-r1.json", {"card": "plan_approval"})  # an approval
    write_live_list(root, "old.json", {"card": "live_view_list"})  # the pre-schema marker
    (got,) = sma_live.live_lists(root)
    assert got.name == "live-view-brightfield.json" and got.sha256 == sha
    assert got.data["camera"]["frame_ceiling"] == 3000


def test_host_address_from_file_or_flag(tmp_path, addr_file, host):
    addr, why = sma_live.host_address(addr_file)
    assert why is None and addr.host == "127.0.0.1"
    assert sma_live.host_address(tmp_path / "none.json")[1].startswith("the live-view host is not")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"host": "10.0.0.5", "port": 5000}), encoding="utf-8")
    assert "not 127.0.0.1" in sma_live.host_address(bad)[1]
    assert sma_live.parse_host("127.0.0.1:6123").port == 6123
    for v in ("localhost:6123", "127.0.0.1", "10.0.0.1:80", "127.0.0.1:x"):
        with pytest.raises(ValueError):
            sma_live.parse_host(v)


def test_live_on_sends_exactly_one_line(root, host, addr_file):
    sha = write_live_list(root)
    addr, _ = sma_live.host_address(addr_file)
    r = sma_live.live_on(addr, sha)
    assert r.outcome == "started" and r.run_id == "run-live-001"
    assert host.requests == [json.dumps({"live_on": sha}).encode() + b"\n"]
    with pytest.raises(ValueError):
        sma_live.live_on(addr, "not-a-sha")


def test_a_host_that_closes_without_a_reply_reads_as_refused(root, addr_file):
    h = FakeLiveHost(root, addr_file, silent=True)
    try:
        addr, _ = sma_live.host_address(addr_file)
        r = sma_live.live_on(addr, "a" * 64)
        assert r.outcome == "refused" and r.reason is None
    finally:
        h.close()


# -- the routes -------------------------------------------------------------------------------


def test_state_offers_the_approved_lists(client, root, host):
    sha = write_live_list(root)
    s = client().get("/api/console/live").json()
    assert s["available"] and s["why_not"] is None and s["host"].startswith("127.0.0.1:")
    assert [(x["name"], x["sha256"]) for x in s["lists"]] == [("live-view-brightfield.json", sha)]


def test_state_says_why_not(engine, make_client, client, root, addr_file):
    assert "--store sma" in make_client(engine).get("/api/console/live").json()["why_not"]
    write_live_list(root)
    s = client().get("/api/console/live").json()  # no host running
    assert not s["available"] and "not running" in s["why_not"]


def test_live_on_then_off_through_the_runs_stop(client, root, host, seat):
    sha = write_live_list(root)
    c = client()
    r = c.post("/api/console/live/on", json={"sha256": sha})
    assert r.status_code == 200, r.text
    assert r.json() == {"outcome": "started", "run_id": "run-live-001", "reason": None}
    run = host.runs[0]
    s = c.get(f"/api/console/runs/microscope/{run.run_id}/stream").json()
    assert s["state"] == "running" and s["can_stop"]
    again = c.post("/api/console/live/on", json={"sha256": sha}).json()
    assert again == {"outcome": "refused", "run_id": None, "reason": "a run holds the lock"}
    off = c.post(f"/api/console/runs/microscope/{run.run_id}/stop", json={"reason": "Live off"})
    assert off.json()["outcome"] == "begun"
    assert run.stops == [f"the dino console: Live off (by {OPERATOR})"]
    audit = [e for e in seat.audit.entries() if e.get("command") == "sma_live_on"]
    assert [a["outcome"] for a in audit] == ["started", "refused"]


def test_live_on_refusals(engine, make_client, client, root, host):
    sha = write_live_list(root)
    assert refusal(client().post("/api/console/live/on", json={"sha256": "b" * 64})) == \
        (409, "no_such_list")
    assert refusal(make_client(engine).post("/api/console/live/on", json={"sha256": sha})) == \
        (409, "not_sma")
    remote = client(remote=True, remote_view=True, login=OPERATOR)
    assert refusal(remote.post("/api/console/live/on", json={"sha256": sha})) == \
        (403, "remote_view")
    viewer = client(login=VIEWER)
    assert refusal(viewer.post("/api/console/live/on", json={"sha256": sha})) == (403, "role")
    assert refusal(client(login=None).post("/api/console/live/on", json={"sha256": sha})) == \
        (401, "login_required")
    assert host.requests == []  # none of those reached the host


def test_live_on_with_no_host(client, root):
    sha = write_live_list(root)
    r = client().post("/api/console/live/on", json={"sha256": sha})
    assert refusal(r) == (502, "live_host_not_running")


def test_permissions_answer_live_on(client, host):
    c = client()
    assert c.get("/api/permissions", params={"ops": "live_on"}).json()["live_on"]["allowed"]
    v = client(login=VIEWER)
    assert not v.get("/api/permissions", params={"ops": "live_on"}).json()["live_on"]["allowed"]


def test_switching_writes_nothing_in_the_tree_but_the_runs_own_files(client, root, host):
    sha = write_live_list(root)
    before = tree_state(root)
    c = client()
    c.get("/api/console/live")
    run_id = c.post("/api/console/live/on", json={"sha256": sha}).json()["run_id"]
    c.post(f"/api/console/runs/microscope/{run_id}/stop", json={})
    after = tree_state(root)
    new = set(after) - set(before)
    assert all(p.replace("\\", "/").startswith(f"microscope_agent/runs/{run_id}/") for p in new)
    assert {k: after[k] for k in before} == before


def test_flags(addr_file):
    a = parse_args(["--live-host-file", str(addr_file), "--live-host", "127.0.0.1:6000"])
    assert a.live_host_file == addr_file and a.live_host == "127.0.0.1:6000"
