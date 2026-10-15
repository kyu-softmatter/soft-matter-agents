"""T-105: the auth router over T-018, with fake accounts (example.test) and a fake engine.
Mock only: no real login, no real control on this PC."""

from __future__ import annotations

import pytest

from dino_autofocus.auth import config as auth_config
from dino_autofocus.server.api import SESSION_COOKIE

ADMIN, OPERATOR, OPERATOR2, VIEWER = (
    "admin@example.test", "otto@example.test", "olga@example.test", "vera@example.test")
TEST_PASSWORD = "server-test-pass-1"  # conftest.TEST_PASSWORD: a test value only
OWN = {"origin": "http://127.0.0.1:8765"}  # the LoopbackClient base: this server's own page


def detail(r):
    return r.json()["detail"]


def audit_kinds(seat):
    return [e["kind"] for e in seat.audit.entries()]


# -- login, cookie, logout --------------------------------------------------------------


def test_login_sets_a_strict_httponly_cookie_and_me_answers(engine, make_client):
    c = make_client(engine, login=None)
    r = c.post("/api/auth/login", json={"email": "Otto@Example.TEST", "password": TEST_PASSWORD})
    assert r.status_code == 200
    me = r.json()
    assert (me["user_id"], me["role"], me["locked"], me["has_control"], me["local"]) == (
        OPERATOR, "operator", False, False, True)
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    low = cookie.lower()
    assert "httponly" in low and "samesite=strict" in low and "path=/" in low
    assert "max-age" not in low and "expires" not in low  # dies with the browser
    token = cookie.split(";")[0].split("=", 1)[1]
    assert token not in r.text  # the token is never in a reply body
    assert c.get("/api/auth/me").json()["user_id"] == OPERATOR


@pytest.mark.parametrize(("email", "password", "code"), [
    (OPERATOR, "wrong-pass-1", "bad_credentials"),
    ("nobody@example.test", TEST_PASSWORD, "bad_credentials"),
])
def test_failed_login_says_why_and_sets_no_cookie(engine, make_client, email, password, code):
    c = make_client(engine, login=None)
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert (r.status_code, detail(r)["code"]) == (401, code)
    assert "set-cookie" not in r.headers
    assert c.get("/api/auth/me").status_code == 401


def test_remote_viewer_logs_in_too(engine, make_client):
    c = make_client(engine, remote=True, login=None)
    r = c.post("/api/auth/login", json={"email": VIEWER, "password": TEST_PASSWORD})
    assert r.status_code == 200 and r.json()["local"] is False


def test_logout_clears_the_cookie_and_ends_the_login(engine, make_client, seat):
    c = make_client(engine)
    token = c.login_token
    r = c.post("/api/auth/logout")
    assert r.status_code == 204
    assert f'{SESSION_COOKIE}=""' in r.headers["set-cookie"] or "max-age=0" in r.headers[
        "set-cookie"].lower()
    assert seat.logins.get(token) is None
    assert "logout" in audit_kinds(seat)


# -- sign-up and approval (D12) ---------------------------------------------------------


def test_signup_takes_name_email_password_only_and_waits_for_approval(engine, make_client, seat):
    c = make_client(engine, login=None)
    body = {"name": "Kim Lee", "email": "kim@example.test", "password": "kim-pass-12"}
    with_role = c.post("/api/auth/signup", json={**body, "role": "admin"})
    assert with_role.status_code == 422  # no role field: the admin picks it
    r = c.post("/api/auth/signup", json=body)
    assert (r.status_code, r.json()) == (201, {"status": "pending"})
    acc = seat.accounts.get("kim@example.test")
    assert (str(acc.status), str(acc.role)) == ("pending", "viewer")
    pending = c.post("/api/auth/login",
                     json={"email": "kim@example.test", "password": "kim-pass-12"})
    assert (pending.status_code, detail(pending)["code"]) == (401, "pending_approval")
    assert "approval" in detail(pending)["message"]
    before = seat.accounts.get("kim@example.test")
    dup = c.post("/api/auth/signup", json={**body, "name": "Someone Else",
                                           "email": "KIM@example.test"})
    assert (dup.status_code, dup.json()) == (201, {"status": "pending"})  # same as a new one
    assert seat.accounts.get("kim@example.test") == before  # and nothing changed
    assert audit_kinds(seat)[-1] == "signup_existing"
    short = c.post("/api/auth/signup", json={**body, "email": "k2@example.test", "password": "x"})
    assert (short.status_code, detail(short)["code"]) == (422, "password_policy")


def test_admin_approves_with_a_role_and_it_is_audited(engine, make_client, seat, log_in_as):
    seat.accounts.register("Kim Lee", "kim@example.test", "kim-pass-12")
    c = make_client(engine, login=ADMIN)
    listed = c.get("/api/auth/accounts", params={"status": "pending"}).json()
    assert [a["email"] for a in listed] == ["kim@example.test"]
    assert "password_hash" not in listed[0]
    r = c.post("/api/auth/accounts/kim@example.test/approve", json={"role": "operator"})
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["role"], r.json()["approved_by"]) == (
        "active", "operator", ADMIN)
    entry = [e for e in seat.audit.entries() if e["kind"] == "account_approved"][-1]
    assert (entry["user_id"], entry["account"], entry["role"]) == (
        ADMIN, "kim@example.test", "operator")
    again = c.post("/api/auth/accounts/kim@example.test/approve", json={"role": "admin"})
    assert again.status_code == 409


@pytest.mark.parametrize("who", [OPERATOR, VIEWER])
def test_non_admin_cannot_list_or_approve(engine, make_client, seat, who):
    seat.accounts.register("Kim Lee", "kim@example.test", "kim-pass-12")
    c = make_client(engine, login=who)
    assert detail(c.get("/api/auth/accounts"))["code"] == "role"
    r = c.post("/api/auth/accounts/kim@example.test/approve", json={"role": "operator"})
    assert (r.status_code, detail(r)["code"]) == (403, "role")
    assert str(seat.accounts.get("kim@example.test").status) == "pending"


def test_remote_admin_cannot_manage_accounts(engine, make_client, seat):
    seat.accounts.register("Kim Lee", "kim@example.test", "kim-pass-12")
    c = make_client(engine, remote=True, login=ADMIN)
    assert detail(c.get("/api/auth/accounts"))["code"] == "remote_view"
    r = c.post("/api/auth/accounts/kim@example.test/approve", json={"role": "operator"})
    assert (r.status_code, detail(r)["code"]) == (403, "remote_view")


def test_role_change_and_disable(engine, make_client, seat):
    c = make_client(engine, login=ADMIN)
    r = c.post(f"/api/auth/accounts/{VIEWER}/role", json={"role": "operator"})
    assert r.json()["role"] == "operator"
    assert c.post("/api/auth/accounts/nobody@example.test/disable").status_code == 404
    assert c.post(f"/api/auth/accounts/{VIEWER}/disable").json()["status"] == "disabled"
    bad = c.post(f"/api/auth/accounts/{VIEWER}/role", json={"role": "boss"})
    assert bad.status_code == 422


def test_enable_reset_password_and_delete(engine, make_client, seat):
    viewer = make_client(engine, login=VIEWER)
    c = make_client(engine, login=ADMIN)
    assert c.post(f"/api/auth/accounts/{VIEWER}/enable").status_code == 409  # active already
    r = c.post(f"/api/auth/accounts/{VIEWER}/password", json={"password": "fresh-pass-word-1"})
    assert r.status_code == 200 and "password_hash" not in r.json()
    assert viewer.get("/api/auth/me").status_code == 401  # the old login ended
    assert make_client(engine).post("/api/auth/login", json={
        "email": VIEWER, "password": "fresh-pass-word-1"}).status_code == 200
    short = c.post(f"/api/auth/accounts/{VIEWER}/password", json={"password": "x"})
    assert (short.status_code, detail(short)["code"]) == (422, "password_policy")
    assert c.post(f"/api/auth/accounts/{VIEWER}/delete").status_code == 409  # disable first
    c.post(f"/api/auth/accounts/{VIEWER}/disable")
    assert c.post(f"/api/auth/accounts/{VIEWER}/enable").json()["status"] == "active"
    c.post(f"/api/auth/accounts/{VIEWER}/disable")
    assert c.post(f"/api/auth/accounts/{VIEWER}/delete").json()["email"] == VIEWER
    assert seat.accounts.get(VIEWER) is None
    assert c.post(f"/api/auth/accounts/{VIEWER}/delete").status_code == 404
    kinds = audit_kinds(seat)
    for k in ("account_password_reset", "account_enabled", "account_deleted"):
        assert k in kinds, k


@pytest.mark.parametrize("who", [OPERATOR, VIEWER])
def test_non_admin_cannot_enable_reset_or_delete(engine, make_client, seat, who):
    seat.accounts.disable(ADMIN, OPERATOR2)
    c = make_client(engine, login=who)
    for path, body in (("enable", None), ("password", {"password": "fresh-pass-word-1"}),
                       ("delete", None)):
        r = c.post(f"/api/auth/accounts/{OPERATOR2}/{path}", json=body)
        assert (r.status_code, detail(r)["code"]) == (403, "role"), path
    assert str(seat.accounts.get(OPERATOR2).status) == "disabled"


def test_remote_admin_cannot_enable_reset_or_delete(engine, make_client, seat):
    seat.accounts.disable(ADMIN, OPERATOR2)
    c = make_client(engine, remote=True, login=ADMIN)
    for path, body in (("enable", None), ("password", {"password": "fresh-pass-word-1"}),
                       ("delete", None)):
        r = c.post(f"/api/auth/accounts/{OPERATOR2}/{path}", json=body)
        assert r.status_code == 403, path
    assert seat.accounts.get(OPERATOR2) is not None


def test_signup_is_refused_from_another_pc(engine, make_client, seat):
    c = make_client(engine, remote=True, login=None)
    r = c.post("/api/auth/signup", json={"name": "Rem Ote", "email": "rem@example.test",
                                         "password": "rem-pass-123"})
    assert (r.status_code, detail(r)["code"]) == (403, "remote_view")
    assert seat.accounts.get("rem@example.test") is None


def test_too_many_wrong_passwords_lock_login_with_retry_after(engine, make_client, seat):
    c = make_client(engine, login=None)
    wrong = {"email": VIEWER, "password": "not-the-password"}
    codes = [c.post("/api/auth/login", json=wrong).status_code for _ in range(5)]
    assert codes == [401] * 5
    locked = c.post("/api/auth/login", json={"email": VIEWER, "password": TEST_PASSWORD})
    assert (locked.status_code, detail(locked)["code"]) == (429, "too_many_attempts")
    assert int(locked.headers["Retry-After"]) > 0 and "Try again" in detail(locked)["message"]
    other = c.post("/api/auth/login", json={"email": OPERATOR, "password": TEST_PASSWORD})
    assert other.status_code == 200  # another account from this client still logs in
    assert "too_many_attempts" in str([e for e in seat.audit.entries()
                                       if e["kind"] == "login_failed"])


def test_unknown_emails_are_limited_like_real_ones(engine, make_client):
    c = make_client(engine, login=None)
    wrong = {"email": "nobody@example.test", "password": "whatever-123"}
    codes = [c.post("/api/auth/login", json=wrong).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]  # a lockout says nothing about who has an account


def test_too_many_wrong_unlock_passwords_answer_429(engine, make_client, seat):
    c = make_client(engine)
    assert c.post("/api/auth/lock").status_code == 204
    for _ in range(5):
        assert c.post("/api/auth/unlock", json={"password": "wrong-pass-99"}).status_code == 401
    r = c.post("/api/auth/unlock", json={"password": TEST_PASSWORD})
    assert (r.status_code, detail(r)["code"]) == (429, "too_many_attempts")
    assert c.get("/api/auth/me").json()["locked"] is True


# -- lock, unlock, activity -------------------------------------------------------------


def test_lock_and_unlock_with_the_password(engine, make_client, seat):
    c = make_client(engine)
    assert c.post("/api/auth/lock").status_code == 204
    assert seat.logins.get(c.login_token).locked
    assert c.get("/api/state").status_code == 423
    bad = c.post("/api/auth/unlock", json={"password": "wrong-pass-1"})
    assert (bad.status_code, detail(bad)["code"]) == (401, "bad_credentials")
    ok = c.post("/api/auth/unlock", json={"password": TEST_PASSWORD})
    assert ok.status_code == 200 and ok.json()["locked"] is False
    assert {"locked", "unlocked"} <= set(audit_kinds(seat))


def test_activity_keeps_the_idle_lock_away(engine, make_client, seat):
    clock = [1_800_000_000.0]
    seat.logins._clock = lambda: clock[0]
    c = make_client(engine)
    clock[0] += seat.logins.idle_lock_s - 1
    assert c.post("/api/auth/activity").status_code == 204
    clock[0] += seat.logins.idle_lock_s - 1
    assert not seat.logins.get(c.login_token).locked  # without activity this would lock
    clock[0] += 1
    assert seat.logins.get(c.login_token).locked
    assert c.post("/api/auth/activity").status_code == 204  # allowed, but does not unlock
    assert seat.logins.get(c.login_token).locked


def test_activity_and_lock_need_a_login(engine, make_client):
    c = make_client(engine, login=None)
    assert c.post("/api/auth/activity").status_code == 401
    assert c.post("/api/auth/lock").status_code == 401


# -- device control ---------------------------------------------------------------------


def test_one_holder_take_and_release(engine, make_client, seat, log_in_as):
    otto = make_client(engine, login=OPERATOR)
    olga = make_client(engine, login=OPERATOR2)
    assert otto.get("/api/auth/control").json() == {"holder": None}
    r = otto.post("/api/auth/control/acquire")
    assert r.status_code == 200 and r.json()["holder"]["user_id"] == OPERATOR
    assert r.json()["holder"]["name"] == "Otto Operator"
    assert "token" not in r.text
    assert otto.get("/api/auth/me").json()["has_control"] is True
    busy = olga.post("/api/auth/control/acquire")
    assert (busy.status_code, detail(busy)["code"]) == (409, "control_busy")
    assert busy.json()["holder"]["user_id"] == OPERATOR
    assert olga.post("/api/auth/control/release").status_code == 409
    assert otto.post("/api/auth/control/release").status_code == 204
    assert olga.post("/api/auth/control/acquire").status_code == 200
    assert {"control_acquired", "control_released"} <= set(audit_kinds(seat))


def test_viewer_and_remote_operator_cannot_take_control(engine, make_client):
    viewer = make_client(engine, login=VIEWER)
    assert detail(viewer.post("/api/auth/control/acquire"))["code"] == "control"
    remote = make_client(engine, remote=True, login=OPERATOR)
    assert detail(remote.post("/api/auth/control/acquire"))["code"] == "remote_view"


def test_admin_force_releases(engine, make_client, seat):
    otto = make_client(engine, login=OPERATOR, control=True)
    admin = make_client(engine, login=ADMIN)
    assert otto.post("/api/auth/control/revoke", json={"reason": "mine"}).status_code == 403
    r = admin.post("/api/auth/control/revoke", json={"reason": "otto left the room"})
    assert r.status_code == 200 and r.json()["previous_holder"]["user_id"] == OPERATOR
    assert admin.get("/api/auth/control").json() == {"holder": None}
    assert otto.get("/api/auth/me").json()["has_control"] is False
    assert "control_revoked" in audit_kinds(seat)


def test_logout_frees_control(engine, make_client):
    otto = make_client(engine, login=OPERATOR, control=True)
    olga = make_client(engine, login=OPERATOR2)
    otto.post("/api/auth/logout")
    assert olga.get("/api/auth/control").json() == {"holder": None}


# -- stops are never blocked by login state ---------------------------------------------


def test_abort_while_locked_and_without_control(engine, make_client, seat):
    c = make_client(engine, login=OPERATOR)  # no control
    c.post("/api/auth/lock")
    for kind in ("abort", "lights_off"):
        assert c.post("/api/commands", json={"kind": kind}).status_code == 200, kind
    nobody = make_client(engine, login=None)
    assert nobody.post("/api/commands", json={"kind": "abort"}).status_code == 200
    assert [x.kind for x in engine.commands] == ["abort", "lights_off", "abort"]


def test_the_auth_routes_are_in_the_openapi_schema(engine, make_client):
    paths = make_client(engine).get("/openapi.json").json()["paths"]
    for p in ("/api/auth/login", "/api/auth/me", "/api/auth/signup", "/api/auth/control/acquire",
              "/api/auth/accounts/{email}/approve", "/api/auth/accounts/{email}/enable",
              "/api/auth/accounts/{email}/password", "/api/auth/accounts/{email}/delete"):
        assert p in paths, p


# -- first run (T-009d opens the paths; this router decides) ----------------------------


@pytest.fixture
def empty_seat(tmp_path):
    from dino_autofocus.server.api import AuthSeat

    return AuthSeat.from_config(tmp_path / "fresh")


def test_first_run_from_the_configured_email(engine, make_client, empty_seat, monkeypatch):
    monkeypatch.setenv(auth_config.ADMIN_EMAIL_ENV, "lab-admin@example.test")
    c = make_client(engine, login=None, auth=empty_seat)
    assert c.get("/api/auth/setup").json() == {"state": "needs_admin"}
    assert "example.test" not in c.get("/api/auth/setup").text  # the email is never sent
    r = c.post("/api/auth/setup/admin", json={"name": "Lab Admin", "password": "admin-pass-1"},
               headers=OWN)
    assert r.status_code == 200
    assert (r.json()["user_id"], r.json()["role"]) == ("lab-admin@example.test", "admin")
    assert SESSION_COOKIE in r.headers["set-cookie"]
    assert c.get("/api/auth/me").json()["role"] == "admin"  # logged in by the setup
    assert c.get("/api/auth/setup").json() == {"state": "ready"}
    again = c.post("/api/auth/setup/admin", json={"name": "X", "password": "admin-pass-2"},
                   headers=OWN)
    assert (again.status_code, detail(again)["code"]) == (409, "setup_done")
    created = [e for e in empty_seat.audit.entries() if e["kind"] == "account_created"]
    assert created[-1]["via"] == "first_admin_setup"


def test_first_run_without_configured_email_takes_one(engine, make_client, empty_seat):
    c = make_client(engine, login=None, auth=empty_seat)
    assert c.get("/api/auth/setup").json() == {"state": "needs_admin_email"}
    missing = c.post("/api/auth/setup/admin", json={"name": "A", "password": "admin-pass-1"},
                     headers=OWN)
    assert (missing.status_code, detail(missing)["code"]) == (409, "setup_required")
    r = c.post("/api/auth/setup/admin",
               json={"name": "A", "password": "admin-pass-1", "email": "first@example.test"},
               headers=OWN)
    assert r.status_code == 200 and r.json()["user_id"] == "first@example.test"


def test_first_run_refuses_another_loopback_port_and_remote(engine, make_client, empty_seat,
                                                            monkeypatch):
    monkeypatch.setenv(auth_config.ADMIN_EMAIL_ENV, "lab-admin@example.test")
    c = make_client(engine, login=None, auth=empty_seat)
    body = {"name": "Lab Admin", "password": "admin-pass-1"}
    other_port = c.post("/api/auth/setup/admin", json=body,
                        headers={"origin": "http://127.0.0.1:9999"})
    assert (other_port.status_code, detail(other_port)["code"]) == (403, "foreign_origin")
    remote = make_client(engine, remote=True, remote_view=True, login=None, auth=empty_seat,
                         allowed_hosts=["scope-pc"])
    r = remote.post("/api/auth/setup/admin", json=body,
                    headers={"host": "scope-pc:8765", "origin": "http://scope-pc:8765"})
    assert (r.status_code, detail(r)["code"]) == (403, "remote_view")
    assert not empty_seat.accounts.has_admin()


def test_locked_login_reads_me_for_the_lock_screen(engine, make_client, seat):
    c = make_client(engine)
    c.post("/api/auth/lock")
    me = c.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["locked"] is True
    assert me.json()["name"] == "Otto Operator"
