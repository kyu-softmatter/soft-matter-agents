"""Who may command: D13 remote abort, and the Host header allow-list (DNS rebinding)."""

from __future__ import annotations

import json

import pytest
from starlette.websockets import WebSocketDisconnect

from dino_autofocus.server.schemas import SERVER_STAMPED


def test_remote_viewer_may_abort_only(engine, make_client):
    c = make_client(engine, remote=True, remote_view=True)
    assert c.post("/api/commands", json={"kind": "abort", "op_id": "op9"}).json() == \
        {"op_id": "op9"}
    for kind in ("start", "confirm", "lights_off"):
        r = c.post("/api/commands", json={"kind": kind, "op": "status"})
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "remote_view"
        assert "abort only" in r.json()["detail"]["message"]
    assert [x.kind for x in engine.commands] == ["abort"]


def test_remote_abort_can_be_switched_off(engine, make_client):
    c = make_client(engine, remote=True, remote_view=True, remote_abort=False)
    assert c.get("/api/health").json()["remote_abort"] is False
    assert c.post("/api/commands", json={"kind": "abort", "op_id": "op9"}).status_code == 403
    assert engine.commands == []


def test_remote_abort_over_websocket(engine, make_client):
    with make_client(engine, remote=True, remote_view=True) as c, \
            c.websocket_connect("/ws/events") as ws:
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "abort", "op_id": "a"}}))
        assert json.loads(ws.receive_text()) == {"type": "accepted", "op_id": "a"}
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "lights_off"}}))
        assert json.loads(ws.receive_text())["status"] == 403
    assert [x.kind for x in engine.commands] == ["abort"]


def test_foreign_page_may_not_abort_either(engine, make_client):
    c = make_client(engine)
    r = c.post("/api/commands", json={"kind": "abort"}, headers={"origin": "https://example.com"})
    assert r.status_code == 403


def test_host_allow_list(engine, make_client):
    """A page whose domain was rebound to 127.0.0.1 sends its own name as Host: refused,
    reads included, even though it is same-origin with itself and the socket is loopback."""
    c = make_client(engine)
    rebound = {"host": "evil.example:8765", "origin": "http://evil.example:8765"}
    assert c.get("/api/state", headers=rebound).status_code == 400
    assert c.post("/api/commands", json={"kind": "lights_off"}, headers=rebound).status_code \
        == 400
    assert c.get("/api/state", headers={"host": "localhost:8765"}).status_code == 200
    with pytest.raises(WebSocketDisconnect), \
            c.websocket_connect("/ws/events", headers=rebound) as ws:
        ws.receive_text()
    assert engine.commands == [] and engine.sinks == []


def test_extra_allowed_hosts_for_remote_view(engine, make_client):
    c = make_client(engine, remote=True, remote_view=True, allowed_hosts=["scope-pc"])
    assert c.get("/api/state", headers={"host": "scope-pc:8765"}).status_code == 200
    assert c.get("/api/state", headers={"host": "other-pc:8765"}).status_code == 400


@pytest.mark.parametrize("op", ["map_flag", "map_flag_retire", "candidate_confirm",
                                "candidate_reject"])
def test_map_writes_only_through_map_router(op, engine, make_client):
    """D16: the common endpoint must not bypass WRITE_MAP_FLAG in server/api/map.py."""
    c = make_client(engine)
    r = c.post("/api/commands", json={"kind": "start", "op": op})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "map_route"
    assert "/api/map" in r.json()["detail"]["message"]
    with c.websocket_connect("/ws/events") as ws:
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "start", "op": op}}))
        assert json.loads(ws.receive_text())["status"] == 403
    assert engine.commands == []


def refusal_code(r) -> str | None:
    return r.headers.get("X-DinoAF-Refusal")


def test_login_routes_open_to_remote_viewers(engine, make_client):
    """Exactly the six login routes skip the loopback rule: a logged-in remote viewer posting
    from this server's own page is not refused there at all (no 401 / 403, no refusal mark).
    What the route then answers is T-105's (404 before its router, 422 for an empty body), so
    it is not asserted. Any other write under /api/auth stays local only, and foreign pages
    are still refused. Logout goes last: after it, T-105's lock / unlock / activity would
    rightly answer 401 for the missing login."""
    c = make_client(engine, remote=True, remote_view=True)
    own = {"origin": f"http://{c.base_url.netloc.decode()}"}
    for name in ("login", "lock", "unlock", "activity", "signup", "logout"):
        r = c.post(f"/api/auth/{name}", json={}, headers=own)
        assert r.status_code not in (401, 403) and refusal_code(r) is None, (name, r.status_code)
    for path in ("/api/auth/users", "/api/auth/login/extra"):
        r = c.post(path, json={})
        assert (r.status_code, refusal_code(r)) == (403, "remote_view"), path
    foreign = c.post("/api/auth/login", json={}, headers={"origin": "https://example.com"})
    assert (foreign.status_code, refusal_code(foreign)) == (403, "foreign_origin")


# a plausible forged value per stamped field; the test fails if SERVER_STAMPED gains a field
# without one here
FORGED = {"origin": "assistant", "user_id": "admin@example.test", "session_id": "s9",
          "proposal_id": "p1", "conversation_id": "c1", "confirmed_by": "admin@example.test",
          "remote": False, "control_grant": "stolen", "t": 0.0}


def test_forged_values_cover_every_stamped_field():
    assert set(FORGED) == set(SERVER_STAMPED)


@pytest.mark.parametrize("field", SERVER_STAMPED)
def test_body_cannot_stamp_commands(field, engine, make_client):
    """A remote viewer cannot clear `remote` (D13), and nobody can hand in a control grant,
    an identity, a confirmation, a session or the assistant's provenance: those are the
    server's (T-011, T-013, T-018)."""
    value = FORGED[field]
    c = make_client(engine, remote=True, remote_view=True)
    r = c.post("/api/commands", json={"kind": "abort", "op_id": "a", field: value})
    assert r.status_code == 422
    with c.websocket_connect("/ws/events") as ws:
        ws.send_text(json.dumps({"type": "command",
                                 "command": {"kind": "abort", "op_id": "a", field: value}}))
        assert json.loads(ws.receive_text())["status"] == 422
    assert engine.commands == []


def test_server_marks_remote_commands(engine, make_client):
    make_client(engine, remote=True, remote_view=True).post(
        "/api/commands", json={"kind": "abort", "op_id": "a"})
    make_client(engine).post("/api/commands", json={"kind": "abort", "op_id": "b"})
    with make_client(engine, remote=True, remote_view=True) as c, \
            c.websocket_connect("/ws/events") as ws:
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "abort", "op_id": "c"}}))
        ws.receive_text()
    assert [(x.op_id, x.remote, x.control_grant, x.origin) for x in engine.commands] == \
        [("a", True, None, "human"), ("b", False, None, "human"), ("c", True, None, "human")]
