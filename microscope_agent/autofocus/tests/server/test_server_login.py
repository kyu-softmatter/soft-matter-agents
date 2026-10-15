"""T-009b: the login cookie on every route, the refusal marks, the server-held control grant,
GET /api/permissions and D14 viewer counts. Accounts are seeded fakes (example.test)."""

from __future__ import annotations

import json

import pytest

from dino_autofocus.server.api import SESSION_COOKIE

OTTO, OLGA, VERA, ADA = ("otto@example.test", "olga@example.test", "vera@example.test",
                         "admin@example.test")
DEV_ORIGIN = {"origin": "http://localhost:5173"}  # another loopback origin (a dev server)
OWN_ORIGIN = {"origin": "http://127.0.0.1:8765"}  # the page this server served


def detail(r):
    return r.json()["detail"]


# -- the director's test: no cookie, nothing beyond the login routes ----------------------


def test_cookieless_loopback_page_gets_nothing_but_login_and_stops(engine, make_client):
    """Another loopback origin (not listed as a dev origin) with no cookie reads nothing, opens
    no socket and writes nothing, stops included (T-009c). From this PC without a browser
    Origin (the launcher, a script) the stops still work with no login; the login routes and
    health stay open to this server's own page."""
    c = make_client(engine, login=None)
    for path in ("/api/state", "/api/permissions?ops=status", "/api/anything"):
        r = c.get(path, headers=DEV_ORIGIN)
        assert r.status_code == 401 and detail(r)["code"] == "login_required", path
        assert r.headers["X-DinoAF-Refusal"] == "login_required"
    for path in ("/ws/events", "/ws/frames"):
        with c.websocket_connect(path, headers=DEV_ORIGIN) as ws:
            msg = json.loads(ws.receive_text())
            assert (msg["type"], msg["status"], msg["code"]) == ("error", 403, "foreign_origin")
    assert engine.sinks == []  # no events were subscribed
    for body in ({"kind": "start", "op": "status"}, {"kind": "abort"}, {"kind": "lights_off"}):
        r = c.post("/api/commands", json=body, headers=DEV_ORIGIN)
        assert (r.status_code, detail(r)["code"]) == (403, "foreign_origin"), body
    assert detail(c.put("/api/anything", json={}, headers=DEV_ORIGIN))["code"] == "foreign_origin"
    assert detail(c.post("/api/auth/login", json={}, headers=DEV_ORIGIN))["code"] == \
        "foreign_origin"
    # what stays open: the stops from this PC (PLAN.md 5), the login routes, health
    for kind in ("abort", "lights_off"):
        assert c.post("/api/commands", json={"kind": kind}).status_code == 200, kind
    # open path: whatever T-105's handler answers (404 before it exists), never a login refusal
    login = c.post("/api/auth/login", json={}, headers=OWN_ORIGIN)
    assert login.status_code not in (401, 403, 423)
    assert c.get("/api/health").status_code == 200
    assert [(x.kind, x.user_id) for x in engine.commands] == [("abort", None),
                                                               ("lights_off", None)]


def test_bad_or_ended_cookie_counts_as_no_login(engine, make_client, seat):
    c = make_client(engine, login=None)
    c.cookies.set(SESSION_COOKIE, "not-a-token")
    assert detail(c.get("/api/state"))["code"] == "login_required"
    d = make_client(engine)
    seat.logins.logout(d.login_token)
    assert detail(d.get("/api/state"))["code"] == "login_required"


def test_locked_login_reads_nothing_but_may_stop(engine, make_client, seat):
    c = make_client(engine)
    seat.logins.lock(c.login_token)
    r = c.get("/api/state")
    assert (r.status_code, detail(r)["code"]) == (423, "locked")
    assert c.post("/api/commands", json={"kind": "start", "op": "status"}).status_code == 423
    assert c.post("/api/commands", json={"kind": "abort"}).status_code == 200
    with c.websocket_connect("/ws/events") as ws:  # admitted, lock state only (T-009c)
        assert ws.lock == {"type": "lock", "locked": True}


# -- refusal marks --------------------------------------------------------------------------


def test_only_the_remote_refusal_carries_remote_view(engine, make_client):
    remote = make_client(engine, remote=True, remote_view=True)
    r = remote.post("/api/commands", json={"kind": "start", "op": "status"})
    assert (r.status_code, detail(r)["code"], r.headers["X-DinoAF-Refusal"]) == \
        (403, "remote_view", "remote_view")
    assert detail(remote.put("/api/anything", json={}))["code"] == "remote_view"

    local = make_client(engine)
    marks = {
        "map_route": local.post("/api/commands", json={"kind": "start", "op": "map_flag"}),
        "foreign_origin": local.post("/api/commands", json={"kind": "abort"},
                                     headers={"origin": "https://example.com"}),
    }
    viewer = make_client(engine, login=VERA)
    marks["role"] = viewer.post("/api/commands", json={"kind": "start", "op": "boundary_mark"})
    for code, r in marks.items():
        assert (r.status_code, detail(r)["code"], r.headers["X-DinoAF-Refusal"]) == \
            (403, code, code)
    assert engine.commands == []


def test_remote_abort_needs_a_logged_in_viewer(engine, make_client):
    anonymous = make_client(engine, remote=True, remote_view=True, login=None)
    r = anonymous.post("/api/commands", json={"kind": "abort", "op_id": "a"})
    assert (r.status_code, detail(r)["code"]) == (401, "login_required")
    viewer = make_client(engine, remote=True, remote_view=True, login=VERA)
    assert viewer.post("/api/commands", json={"kind": "abort", "op_id": "a"}).status_code == 200
    assert [(x.kind, x.remote, x.user_id) for x in engine.commands] == [("abort", True, VERA)]


# -- who, and with which grant --------------------------------------------------------------


def test_commands_carry_the_user_and_the_server_held_grant(engine, make_client, seat):
    holder = make_client(engine, control=True)
    holder.post("/api/commands", json={"kind": "start", "op": "status"})
    other = make_client(engine, login=OLGA)
    other.post("/api/commands", json={"kind": "start", "op": "status"})
    (mine, theirs) = engine.commands
    assert mine.user_id == OTTO and mine.control_grant
    assert theirs.user_id == OLGA and theirs.control_grant is None
    # the grant is the live one from T-018, and it never reaches the browser
    assert seat.control.check(mine.control_grant).user_id == OTTO
    for r in (holder.get("/api/state"), holder.get("/api/permissions?ops=status")):
        assert mine.control_grant not in r.text


def test_grant_ends_with_release_revoke_and_logout(engine, make_client, seat):
    c = make_client(engine, control=True)
    info = seat.login(c.login_token)
    assert seat.has_control(info)
    seat.release(c.login_token)
    assert seat.grant_for(info) is None
    seat.acquire(c.login_token, local=True)
    admin = make_client(engine, login=ADA)
    seat.control.revoke(admin.login_token, "test")
    assert seat.grant_for(info) is None
    seat.acquire(c.login_token, local=True)
    seat.logins.logout(c.login_token)
    assert seat.grant_for(info) is None and seat.control.holder() is None


def test_websocket_commands_are_stamped_too(engine, make_client):
    c = make_client(engine, control=True)
    with c.websocket_connect("/ws/events") as ws:
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "start", "op": "status"}}))
        assert json.loads(ws.receive_text())["type"] == "accepted"
    (cmd,) = engine.commands
    assert (cmd.user_id, cmd.remote, bool(cmd.control_grant)) == (OTTO, False, True)


# -- GET /api/permissions -------------------------------------------------------------------


OPS = "status,busy_op,boundary_mark,map_flag,abort,lights_off,session_open,submit_question"


def test_permissions_for_the_control_holder(engine, make_client):
    got = make_client(engine, control=True).get(f"/api/permissions?ops={OPS}").json()
    assert {op: e["allowed"] for op, e in got.items()} == {
        "status": True, "busy_op": False, "boundary_mark": True, "map_flag": True,
        "abort": True, "lights_off": True, "session_open": True, "submit_question": True}
    assert got["busy_op"]["reason"].startswith("busy") and got["busy_op"]["code"] is None
    ops, ctx = engine.checks[-1]
    assert "session_open" not in ops and ctx["user_id"] == OTTO and ctx["control_grant"]


def test_permissions_without_control_take_the_engines_reason(engine, make_client):
    got = make_client(engine).get(f"/api/permissions?ops={OPS}").json()
    assert got["status"] == {"allowed": False, "reason": "does not hold equipment control",
                             "code": None}
    assert got["abort"]["allowed"] and got["session_open"]["allowed"]


def test_permissions_for_a_local_viewer(engine, make_client):
    got = make_client(engine, login=VERA).get(f"/api/permissions?ops={OPS}").json()
    for op in ("boundary_mark", "map_flag", "session_open", "submit_question"):
        assert (got[op]["allowed"], got[op]["code"]) == (False, "role"), op
    assert got["abort"]["allowed"]


def test_permissions_for_a_remote_viewer(engine, make_client):
    got = make_client(engine, remote=True, remote_view=True, login=VERA).get(
        f"/api/permissions?ops={OPS}").json()
    assert got["abort"] == {"allowed": True, "reason": None, "code": None}
    for op in ("status", "lights_off", "map_flag", "session_open", "submit_question"):
        assert (got[op]["allowed"], got[op]["code"]) == (False, "remote_view"), op


@pytest.mark.parametrize("login", [None])
def test_permissions_need_a_login(login, engine, make_client):
    r = make_client(engine, login=login).get("/api/permissions?ops=abort")
    assert r.status_code == 401


# -- D14 --------------------------------------------------------------------------------


def test_local_event_viewers_are_reported(engine, make_client):
    local = make_client(engine)
    remote = make_client(engine, remote=True, remote_view=True, login=VERA)
    with local.websocket_connect("/ws/events"), remote.websocket_connect("/ws/events"):
        pass
    with local.websocket_connect("/ws/events"), local.websocket_connect("/ws/events"):
        pass
    # the remote viewer is never counted; two local tabs count two
    assert engine.viewers == [1, 0, 1, 2, 1, 0]
