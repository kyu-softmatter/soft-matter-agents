"""Who may write: the Host header allow-list (DNS rebinding) and the login routes. And that no
command reaches any engine from this server (soft-matter-agents card 077): `/api/commands` and
the command messages on `/ws/events` are gone. The remote-abort rules (D13) still hold for the
stop of a run soft-matter-agents executes; test_api_console_sma_run.py tests them there."""

from __future__ import annotations

import json

import pytest
from starlette.websockets import WebSocketDisconnect


def test_commands_are_gone(engine, make_client):
    """The command route answers as an unknown route, and a message on /ws/events is refused
    as a command this server does not take, from the microscope PC and remote alike."""
    r = make_client(engine).post("/api/commands", json={"kind": "abort", "op_id": "op9"})
    assert r.status_code in (404, 405), r.status_code
    remote = make_client(engine, remote=True, remote_view=True)
    r = remote.post("/api/commands", json={"kind": "abort", "op_id": "op9"})
    assert r.json()["detail"]["code"] == "remote_view"  # every remote write, before routing
    with make_client(engine) as c, c.websocket_connect("/ws/events") as ws:
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "abort"}}))
        reply = json.loads(ws.receive_text())
        assert (reply["status"], reply["code"]) == (405, "no_commands")


def test_host_allow_list(engine, make_client):
    """A page whose domain was rebound to 127.0.0.1 sends its own name as Host: refused,
    reads included, even though it is same-origin with itself and the socket is loopback."""
    c = make_client(engine)
    rebound = {"host": "evil.example:8765", "origin": "http://evil.example:8765"}
    assert c.get("/api/state", headers=rebound).status_code == 400
    assert c.post("/api/shutdown", json={}, headers=rebound).status_code == 400
    assert c.get("/api/state", headers={"host": "localhost:8765"}).status_code == 200
    with pytest.raises(WebSocketDisconnect), \
            c.websocket_connect("/ws/events", headers=rebound) as ws:
        ws.receive_text()
    assert engine.shutdowns == [] and engine.sinks == []


def test_extra_allowed_hosts_for_remote_view(engine, make_client):
    c = make_client(engine, remote=True, remote_view=True, allowed_hosts=["scope-pc"])
    assert c.get("/api/state", headers={"host": "scope-pc:8765"}).status_code == 200
    assert c.get("/api/state", headers={"host": "other-pc:8765"}).status_code == 400


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
