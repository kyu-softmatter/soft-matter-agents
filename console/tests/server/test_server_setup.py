"""T-009d: first-run setup is reachable with no login, and its one write only from this PC
and this server's own page. The handlers are T-105's; until they exist the open paths 404,
and the assertions only say "the middleware let it through" (no 401 / 403 / 423)."""

from __future__ import annotations

import pytest

OWN = {"origin": "http://127.0.0.1:8765"}  # the LoopbackClient's base: this server's page
PASSED = lambda r: r.status_code not in (401, 403, 423)  # noqa: E731


def test_setup_state_is_readable_without_login(engine, make_client):
    c = make_client(engine, login=None)
    assert PASSED(c.get("/api/auth/setup"))
    assert c.get("/api/auth/setup/anything").status_code == 401  # exactly that path


def test_setup_admin_from_own_page_passes(engine, make_client):
    c = make_client(engine, login=None)
    assert PASSED(c.post("/api/auth/setup/admin", json={}, headers=OWN))


@pytest.mark.parametrize("headers", [
    {},  # no Origin: a script or another program on this PC
    {"origin": "http://127.0.0.1:9999"},  # another loopback port: same site, not this server
    {"origin": "http://localhost:5173"},  # even the dev server: not for this write
    {"origin": "http://localhost:8765"},  # same port, other host name: not this origin
    {"origin": "https://127.0.0.1:8765"},  # same host and port, other scheme
    {"origin": "http://127.0.0.1"},  # port left out
    {"origin": "https://example.com"},
], ids=["no-origin", "other-loopback-port", "dev-server", "localhost-not-127", "https",
        "no-port", "foreign-site"])
def test_setup_admin_refused_unless_own_origin(headers, engine, make_client):
    c = make_client(engine, login=None)
    r = c.post("/api/auth/setup/admin", json={}, headers=headers)
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "foreign_origin")
    assert r.headers["X-DinoAF-Refusal"] == "foreign_origin"


def test_setup_admin_is_for_the_microscope_pc_only(engine, make_client):
    c = make_client(engine, remote=True, remote_view=True, login=None,
                    allowed_hosts=["scope-pc"])
    own_remote = {"host": "scope-pc:8765", "origin": "http://scope-pc:8765"}
    r = c.post("/api/auth/setup/admin", json={}, headers=own_remote)
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "remote_view")


def test_setup_subpaths_stay_closed(engine, make_client):
    c = make_client(engine, login=None)
    assert c.post("/api/auth/setup/admin/x", json={}, headers=OWN).status_code == 401
    assert c.post("/api/auth/setup", json={}, headers=OWN).status_code == 401


def test_me_answers_a_locked_login(engine, make_client, seat):
    """The lock screen asks who is locked; every other read stays 423 while locked."""
    assert make_client(engine, login=None).get("/api/auth/me").status_code == 401
    c = make_client(engine)
    seat.logins.lock(c.login_token)
    assert PASSED(c.get("/api/auth/me"))
    assert c.get("/api/state").status_code == 423
    assert c.get("/api/auth/me/anything").status_code == 423
