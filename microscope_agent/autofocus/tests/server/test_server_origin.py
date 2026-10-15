"""T-009c (SAFETY): only this server's own origin, plus `--dev-origin`s, may write or open a
WebSocket; and a locked microscope-PC page keeps its event socket (D14) but sees no data."""

from __future__ import annotations

import json

import pytest

from dino_autofocus.server import ws as ws_module
from dino_autofocus.server.api import SESSION_COOKIE

OWN = "http://127.0.0.1:8765"  # the LoopbackClient's base: the page this server served
DEV = "http://localhost:5173"
START = {"kind": "start", "op": "status"}
TEST_PASSWORD = "server-test-pass-1"  # conftest's seeded test password (a test value)


def code(r):
    return r.json()["detail"]["code"] if r.status_code >= 400 else None


@pytest.fixture(autouse=True)
def quick_lock_poll(monkeypatch):
    monkeypatch.setattr(ws_module, "LOCK_POLL_S", 0.05)


# -- (c) REST ---------------------------------------------------------------------------


@pytest.mark.parametrize("origin", [
    "http://127.0.0.1:9999",  # another loopback port: same site, so it carries the cookie
    "http://localhost:8765",  # same port, other host name
    "https://127.0.0.1:8765",  # other scheme
    DEV,  # a dev server not named with --dev-origin
    "null",  # a sandboxed frame or a file
    "https://example.com",
])
def test_other_pages_holding_the_cookie_cannot_command(origin, engine, make_client):
    """The director's case: the operator holds control and is logged in; a page served on
    another loopback port sends the cookie along (SameSite ignores ports). Refused."""
    c = make_client(engine, control=True)
    assert c.cookies.get(SESSION_COOKIE)
    for body in (START, {"kind": "abort"}, {"kind": "lights_off"}):
        r = c.post("/api/commands", json=body, headers={"origin": origin})
        assert (r.status_code, code(r)) == (403, "foreign_origin"), (origin, body)
    assert code(c.put("/api/anything", json={}, headers={"origin": origin})) == "foreign_origin"
    assert engine.commands == []


def test_own_page_and_no_origin_may_command(engine, make_client):
    c = make_client(engine, control=True)
    assert c.post("/api/commands", json=START, headers={"origin": OWN}).status_code == 200
    assert c.post("/api/commands", json=START).status_code == 200  # no browser: no Origin
    assert [x.control_grant is not None for x in engine.commands] == [True, True]


def test_listed_dev_origin_may_command(engine, make_client):
    c = make_client(engine, control=True, dev_origins=[DEV + "/"])
    assert c.post("/api/commands", json=START, headers={"origin": DEV}).status_code == 200
    other = c.post("/api/commands", json=START, headers={"origin": "http://localhost:5174"})
    assert code(other) == "foreign_origin"


def test_bad_dev_origin_is_refused_at_start(engine, make_client):
    for bad in ("localhost:5173", "http://localhost:5173/app", "ftp://x"):
        with pytest.raises(ValueError):
            make_client(engine, dev_origins=[bad])


def test_setup_admin_uses_the_same_rule(engine, make_client):
    c = make_client(engine, login=None, dev_origins=[DEV])
    passed = c.post("/api/auth/setup/admin", json={}, headers={"origin": DEV})
    assert passed.status_code not in (401, 403, 423)  # a listed dev origin may (T-009d)
    assert code(c.post("/api/auth/setup/admin", json={})) == "foreign_origin"  # Origin needed


# -- (a) WebSocket handshake --------------------------------------------------------------


@pytest.mark.parametrize("path", ["/ws/events", "/ws/frames"])
@pytest.mark.parametrize("origin", ["http://127.0.0.1:9999", "https://example.com", DEV])
def test_websocket_from_another_page_is_refused(path, origin, frame_engine, make_client):
    c = make_client(frame_engine)
    with c.websocket_connect(path, headers={"origin": origin}, raw=True) as ws:
        msg = json.loads(ws.receive_text())
        assert (msg["type"], msg["status"], msg["code"]) == ("error", 403, "foreign_origin")
    assert frame_engine.sinks == [] and frame_engine.viewers == []


def test_websocket_from_own_or_listed_page(engine, make_client):
    for c, origin in ((make_client(engine), OWN),
                      (make_client(engine, dev_origins=[DEV]), DEV)):
        with c.websocket_connect("/ws/events", headers={"origin": origin}) as ws:
            assert ws.lock == {"type": "lock", "locked": False}


# -- (b) locked sockets and D14 -----------------------------------------------------------


def recv(ws) -> dict:
    return json.loads(ws.receive_text())


def wait_sinks(engine, n):
    import time

    end = time.monotonic() + 5
    while len(engine.sinks) != n:
        assert time.monotonic() < end, "subscription did not happen"
        time.sleep(0.01)


def test_locked_page_counts_and_reloads_without_tripping_d14(engine, make_client, seat):
    c = make_client(engine)
    seat.logins.lock(c.login_token)
    for _ in range(2):  # open, reload
        with c.websocket_connect("/ws/events") as ws:
            assert ws.lock == {"type": "lock", "locked": True}
    assert engine.viewers == [1, 0, 1, 0]  # counted each time: D14 sees the page come back


def test_locked_socket_gets_no_payload_until_unlock(engine, make_client, seat):
    c = make_client(engine)
    seat.logins.lock(c.login_token)
    with c.websocket_connect("/ws/events") as ws:
        assert ws.lock["locked"] is True
        wait_sinks(engine, 1)
        engine.emit("position", z_um=1.0)  # while locked: dropped
        seat.logins.unlock(c.login_token, TEST_PASSWORD)
        assert recv(ws) == {"type": "lock", "locked": False}
        engine.emit("position", z_um=2.0)
        assert recv(ws)["event"]["data"] == {"z_um": 2.0}  # the locked-time event never came


def test_open_socket_stops_events_when_its_login_locks(engine, make_client, seat):
    c = make_client(engine)
    with c.websocket_connect("/ws/events") as ws:
        assert ws.lock["locked"] is False
        wait_sinks(engine, 1)
        engine.emit("position", z_um=1.0)
        assert recv(ws)["event"]["data"] == {"z_um": 1.0}
        seat.logins.lock(c.login_token)
        engine.emit("position", z_um=2.0)
        assert recv(ws) == {"type": "lock", "locked": True}
        # stops still work and their replies still come while locked
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "abort", "op_id": "a"}}))
        assert recv(ws) == {"type": "accepted", "op_id": "a"}
        seat.logins.unlock(c.login_token, TEST_PASSWORD)
        assert recv(ws) == {"type": "lock", "locked": False}
        engine.emit("position", z_um=3.0)
        assert recv(ws)["event"]["data"] == {"z_um": 3.0}
    assert [x.kind for x in engine.commands] == ["abort"]


def test_socket_closes_when_its_login_ends(engine, make_client, seat):
    c = make_client(engine)
    with c.websocket_connect("/ws/events") as ws:
        seat.logins.logout(c.login_token)
        msg = recv(ws)
        assert (msg["type"], msg["status"], msg["code"]) == ("error", 401, "login_required")


def test_remote_locked_socket_is_refused_and_never_counts(engine, make_client, seat):
    c = make_client(engine, remote=True, remote_view=True)
    seat.logins.lock(c.login_token)
    with c.websocket_connect("/ws/events") as ws:
        msg = recv(ws)
        assert (msg["status"], msg["code"]) == (423, "locked")
    assert engine.viewers == []
