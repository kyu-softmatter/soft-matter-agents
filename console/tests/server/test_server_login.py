"""T-009b: the login cookie on every route, the refusal marks, GET /api/permissions and D14
viewer counts. Accounts are seeded fakes (plain logins)."""

from __future__ import annotations

import json

import pytest

from sma_console.server.api import SESSION_COOKIE

OTTO, OLGA, VERA, ADA = ("otto", "olga", "vera",
                         "ada")
DEV_ORIGIN = {"origin": "http://localhost:5173"}  # another loopback origin (a dev server)
OWN_ORIGIN = {"origin": "http://127.0.0.1:8765"}  # the page this server served
#: writes that replaced the retired commands route as probes (soft-matter-agents card 077):
#: one behind the origin rule only, one behind the full write rule (loopback, login, unlocked)
OPEN_WRITE = "/api/auth/activity"
WRITE = "/api/auth/accounts/give-login"


def detail(r):
    return r.json()["detail"]


# -- the director's test: no cookie, nothing beyond the login routes ----------------------


def test_cookieless_loopback_page_gets_nothing_but_login(engine, make_client):
    """Another loopback origin (not listed as a dev origin) with no cookie reads nothing, opens
    no socket and writes nothing (T-009c). The login routes and health stay open to this
    server's own page. The no-login stops from this PC went with the commands route (card
    077); a run's stop keeps that rule, tested in test_api_console_sma_run.py."""
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
    r = c.post(OPEN_WRITE, json={}, headers=DEV_ORIGIN)
    assert (r.status_code, detail(r)["code"]) == (403, "foreign_origin")
    assert detail(c.put("/api/anything", json={}, headers=DEV_ORIGIN))["code"] == "foreign_origin"
    assert detail(c.post("/api/auth/login", json={}, headers=DEV_ORIGIN))["code"] == \
        "foreign_origin"
    # what stays open: the login routes, health
    # open path: whatever T-105's handler answers (404 before it exists), never a login refusal
    login = c.post("/api/auth/login", json={}, headers=OWN_ORIGIN)
    assert login.status_code not in (401, 403, 423)
    assert c.get("/api/health").status_code == 200


def test_bad_or_ended_cookie_counts_as_no_login(engine, make_client, seat):
    c = make_client(engine, login=None)
    c.cookies.set(SESSION_COOKIE, "not-a-token")
    assert detail(c.get("/api/state"))["code"] == "login_required"
    d = make_client(engine)
    seat.logins.logout(d.login_token)
    assert detail(d.get("/api/state"))["code"] == "login_required"


def test_locked_login_reads_and_writes_nothing(engine, make_client, seat):
    c = make_client(engine)
    seat.logins.lock(c.login_token)
    r = c.get("/api/state")
    assert (r.status_code, detail(r)["code"]) == (423, "locked")
    assert c.post(WRITE, json={}).status_code == 423
    with c.websocket_connect("/ws/events") as ws:  # admitted, lock state only (T-009c)
        assert ws.lock == {"type": "lock", "locked": True}


# -- refusal marks --------------------------------------------------------------------------


def test_only_the_remote_refusal_carries_remote_view(engine, make_client):
    remote = make_client(engine, remote=True, remote_view=True)
    r = remote.post(WRITE, json={})
    assert (r.status_code, detail(r)["code"], r.headers["X-DinoAF-Refusal"]) == \
        (403, "remote_view", "remote_view")
    assert detail(remote.put("/api/anything", json={}))["code"] == "remote_view"

    local = make_client(engine)
    marks = {
        "foreign_origin": local.post(WRITE, json={}, headers={"origin": "https://example.com"}),
    }
    viewer = make_client(engine, login=VERA)
    marks["role"] = viewer.post("/api/console/questions",
                                json={"text": "q", "target": "microscope"})
    for code, r in marks.items():
        assert (r.status_code, detail(r)["code"], r.headers["X-DinoAF-Refusal"]) == \
            (403, code, code)


# -- GET /api/permissions -------------------------------------------------------------------


OPS = "status,busy_op,boundary_mark,map_flag,abort,lights_off,session_open,submit_question"


ENGINE_NAMES = ("status", "busy_op", "boundary_mark", "map_flag", "abort", "lights_off")


def _no_commands(got, names=ENGINE_NAMES):
    """Card 077: an engine operation, a stop or a map write is never allowed here."""
    for op in names:
        assert (got[op]["allowed"], got[op]["code"]) == (False, "no_commands"), op


def test_permissions_for_a_logged_in_operator(engine, make_client):
    got = make_client(engine).get(f"/api/permissions?ops={OPS}").json()
    _no_commands(got)
    assert got["session_open"]["allowed"] and got["submit_question"]["allowed"]
    assert engine.checks == []  # the engine is not asked: there is nothing to send it


def test_permissions_for_a_local_viewer(engine, make_client):
    got = make_client(engine, login=VERA).get(f"/api/permissions?ops={OPS}").json()
    for op in ("session_open", "submit_question"):
        assert (got[op]["allowed"], got[op]["code"]) == (False, "role"), op
    _no_commands(got)


def test_permissions_for_a_remote_viewer(engine, make_client):
    got = make_client(engine, remote=True, remote_view=True, login=VERA).get(
        f"/api/permissions?ops={OPS}").json()
    for op in ("session_open", "submit_question"):
        assert (got[op]["allowed"], got[op]["code"]) == (False, "remote_view"), op
    _no_commands(got)


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
