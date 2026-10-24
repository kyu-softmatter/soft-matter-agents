"""T-105: the auth router over T-018, with fake accounts (plain logins) and a fake engine.
Mock only: no real login on this PC. Console card 009: logins are plain ids, never an email;
there is no delete route and no take-and-release control."""

from __future__ import annotations

import pytest

from sma_console.server.api import SESSION_COOKIE

ADMIN, OPERATOR, OPERATOR2, VIEWER = (
    "ada", "otto", "olga", "vera")
TEST_PASSWORD = "server-test-pass-1"  # conftest.TEST_PASSWORD: a test value only
OWN = {"origin": "http://127.0.0.1:8765"}  # the LoopbackClient base: this server's own page


def detail(r):
    return r.json()["detail"]


def audit_kinds(seat):
    return [e["kind"] for e in seat.audit.entries()]


# -- login, cookie, logout --------------------------------------------------------------


def test_login_sets_a_strict_httponly_cookie_and_me_answers(engine, make_client):
    c = make_client(engine, login=None)
    r = c.post("/api/auth/login", json={"login": "otto", "password": TEST_PASSWORD})
    assert r.status_code == 200
    me = r.json()
    assert (me["user_id"], me["role"], me["locked"], me["local"]) == (OPERATOR, "operator", False, True)
    assert "has_control" not in me
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    low = cookie.lower()
    assert "httponly" in low and "samesite=strict" in low and "path=/" in low
    assert "max-age" not in low and "expires" not in low  # dies with the browser
    token = cookie.split(";")[0].split("=", 1)[1]
    assert token not in r.text  # the token is never in a reply body
    assert c.get("/api/auth/me").json()["user_id"] == OPERATOR


@pytest.mark.parametrize(("login", "password", "code"), [
    (OPERATOR, "wrong-pass-1", "bad_credentials"),
    ("nobody", TEST_PASSWORD, "bad_credentials"),
])
def test_failed_login_says_why_and_sets_no_cookie(engine, make_client, login, password, code):
    c = make_client(engine, login=None)
    r = c.post("/api/auth/login", json={"login": login, "password": password})
    assert (r.status_code, detail(r)["code"]) == (401, code)
    assert "set-cookie" not in r.headers
    assert c.get("/api/auth/me").status_code == 401


def test_remote_viewer_logs_in_too(engine, make_client):
    c = make_client(engine, remote=True, login=None)
    r = c.post("/api/auth/login", json={"login": VIEWER, "password": TEST_PASSWORD})
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
    body = {"name": "Kim Lee", "login": "kim", "password": "kim-pass-12"}
    with_role = c.post("/api/auth/signup", json={**body, "role": "admin"})
    assert with_role.status_code == 422  # no role field: the admin picks it
    r = c.post("/api/auth/signup", json=body)
    assert (r.status_code, r.json()) == (201, {"status": "pending"})
    acc = seat.accounts.get("kim")
    assert (str(acc.status), str(acc.role)) == ("pending", "viewer")
    pending = c.post("/api/auth/login",
                     json={"login": "kim", "password": "kim-pass-12"})
    assert (pending.status_code, detail(pending)["code"]) == (401, "pending_approval")
    assert "approval" in detail(pending)["message"]
    before = seat.accounts.get("kim")
    dup = c.post("/api/auth/signup", json={**body, "name": "Someone Else",
                                           "login": "KIM"})
    assert (dup.status_code, dup.json()) == (201, {"status": "pending"})  # same as a new one
    assert seat.accounts.get("kim") == before  # and nothing changed
    assert audit_kinds(seat)[-1] == "signup_existing"
    short = c.post("/api/auth/signup", json={**body, "login": "k2", "password": "x"})
    assert (short.status_code, detail(short)["code"]) == (422, "password_policy")


def test_admin_approves_with_a_role_and_it_is_audited(engine, make_client, seat, log_in_as):
    seat.accounts.register("Kim Lee", "kim", "kim-pass-12")
    c = make_client(engine, login=ADMIN)
    listed = c.get("/api/auth/accounts", params={"status": "pending"}).json()
    assert [a["login"] for a in listed] == ["kim"]
    assert "password_hash" not in listed[0]
    r = c.post("/api/auth/accounts/kim/approve", json={"role": "operator"})
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["role"], r.json()["approved_by"]) == (
        "active", "operator", ADMIN)
    entry = [e for e in seat.audit.entries() if e["kind"] == "account_approved"][-1]
    assert (entry["user_id"], entry["account"], entry["role"]) == (
        ADMIN, "kim", "operator")
    again = c.post("/api/auth/accounts/kim/approve", json={"role": "admin"})
    assert again.status_code == 409


@pytest.mark.parametrize("who", [OPERATOR, VIEWER])
def test_non_admin_cannot_list_or_approve(engine, make_client, seat, who):
    seat.accounts.register("Kim Lee", "kim", "kim-pass-12")
    c = make_client(engine, login=who)
    assert detail(c.get("/api/auth/accounts"))["code"] == "role"
    r = c.post("/api/auth/accounts/kim/approve", json={"role": "operator"})
    assert (r.status_code, detail(r)["code"]) == (403, "role")
    assert str(seat.accounts.get("kim").status) == "pending"


def test_remote_admin_cannot_manage_accounts(engine, make_client, seat):
    seat.accounts.register("Kim Lee", "kim", "kim-pass-12")
    c = make_client(engine, remote=True, login=ADMIN)
    assert detail(c.get("/api/auth/accounts"))["code"] == "remote_view"
    r = c.post("/api/auth/accounts/kim/approve", json={"role": "operator"})
    assert (r.status_code, detail(r)["code"]) == (403, "remote_view")


def test_role_change_and_disable(engine, make_client, seat):
    c = make_client(engine, login=ADMIN)
    r = c.post(f"/api/auth/accounts/{VIEWER}/role", json={"role": "operator"})
    assert r.json()["role"] == "operator"
    assert c.post("/api/auth/accounts/nobody/disable").status_code == 404
    assert c.post(f"/api/auth/accounts/{VIEWER}/disable").json()["status"] == "disabled"
    bad = c.post(f"/api/auth/accounts/{VIEWER}/role", json={"role": "boss"})
    assert bad.status_code == 422


def test_enable_and_reset_password(engine, make_client, seat):
    viewer = make_client(engine, login=VIEWER)
    c = make_client(engine, login=ADMIN)
    assert c.post(f"/api/auth/accounts/{VIEWER}/enable").status_code == 409  # active already
    r = c.post(f"/api/auth/accounts/{VIEWER}/password", json={"password": "fresh-pass-word-1"})
    assert r.status_code == 200 and "password_hash" not in r.json()
    assert viewer.get("/api/auth/me").status_code == 401  # the old login ended
    assert make_client(engine).post("/api/auth/login", json={
        "login": VIEWER, "password": "fresh-pass-word-1"}).status_code == 200
    short = c.post(f"/api/auth/accounts/{VIEWER}/password", json={"password": "x"})
    assert (short.status_code, detail(short)["code"]) == (422, "password_policy")
    c.post(f"/api/auth/accounts/{VIEWER}/disable")
    assert c.post(f"/api/auth/accounts/{VIEWER}/enable").json()["status"] == "active"
    kinds = audit_kinds(seat)
    for k in ("account_password_reset", "account_enabled", "account_disabled"):
        assert k in kinds, k


@pytest.mark.parametrize("who", [OPERATOR, VIEWER])
def test_non_admin_cannot_enable_or_reset(engine, make_client, seat, who):
    seat.accounts.disable(ADMIN, OPERATOR2)
    c = make_client(engine, login=who)
    for path, body in (("enable", None), ("password", {"password": "fresh-pass-word-1"})):
        r = c.post(f"/api/auth/accounts/{OPERATOR2}/{path}", json=body)
        assert (r.status_code, detail(r)["code"]) == (403, "role"), path
    assert str(seat.accounts.get(OPERATOR2).status) == "disabled"


def test_remote_admin_cannot_enable_or_reset(engine, make_client, seat):
    seat.accounts.disable(ADMIN, OPERATOR2)
    c = make_client(engine, remote=True, login=ADMIN)
    for path, body in (("enable", None), ("password", {"password": "fresh-pass-word-1"})):
        r = c.post(f"/api/auth/accounts/{OPERATOR2}/{path}", json=body)
        assert r.status_code == 403, path
    assert seat.accounts.get(OPERATOR2) is not None


def test_signup_is_refused_from_another_pc(engine, make_client, seat):
    c = make_client(engine, remote=True, login=None)
    r = c.post("/api/auth/signup", json={"name": "Rem Ote", "login": "rem",
                                         "password": "rem-pass-123"})
    assert (r.status_code, detail(r)["code"]) == (403, "remote_view")
    assert seat.accounts.get("rem") is None


def test_too_many_wrong_passwords_lock_login_with_retry_after(engine, make_client, seat):
    c = make_client(engine, login=None)
    wrong = {"login": VIEWER, "password": "not-the-password"}
    codes = [c.post("/api/auth/login", json=wrong).status_code for _ in range(5)]
    assert codes == [401] * 5
    locked = c.post("/api/auth/login", json={"login": VIEWER, "password": TEST_PASSWORD})
    assert (locked.status_code, detail(locked)["code"]) == (429, "too_many_attempts")
    assert int(locked.headers["Retry-After"]) > 0 and "Try again" in detail(locked)["message"]
    other = c.post("/api/auth/login", json={"login": OPERATOR, "password": TEST_PASSWORD})
    assert other.status_code == 200  # another account from this client still logs in
    assert "too_many_attempts" in str([e for e in seat.audit.entries()
                                       if e["kind"] == "login_failed"])


def test_unknown_logins_are_limited_like_real_ones(engine, make_client):
    c = make_client(engine, login=None)
    wrong = {"login": "nobody", "password": "whatever-123"}
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


# -- no delete, no take-and-release control -----------------------------------------------


def test_there_is_no_delete_route_and_no_control_route(engine, make_client):
    c = make_client(engine, login=ADMIN)
    paths = c.get("/openapi.json").json()["paths"]
    assert not [p for p in paths if "delete" in p or "/control" in p], paths.keys()
    assert c.post(f"/api/auth/accounts/{VIEWER}/delete").status_code in (404, 405)
    for gone in ("acquire", "release", "revoke"):
        assert c.post(f"/api/auth/control/{gone}", json={"reason": "x"}).status_code in (404, 405), gone
    assert c.get("/api/auth/control").status_code in (404, 405)
    assert seat_has_account(c, VIEWER)  # nothing was deleted by asking


def seat_has_account(admin_client, login):
    return login in [a["login"] for a in admin_client.get("/api/auth/accounts").json()]


# -- stops are never blocked by login state ---------------------------------------------


def test_the_auth_routes_are_in_the_openapi_schema(engine, make_client):
    paths = make_client(engine).get("/openapi.json").json()["paths"]
    for p in ("/api/auth/login", "/api/auth/me", "/api/auth/signup",
              "/api/auth/accounts/{login}/approve", "/api/auth/accounts/{login}/enable",
              "/api/auth/accounts/{login}/password", "/api/auth/accounts/needs-login",
              "/api/auth/accounts/give-login"):
        assert p in paths, p


# -- first run (T-009d opens the paths; this router decides) ----------------------------


@pytest.fixture
def empty_seat(tmp_path):
    from sma_console.server.api import AuthSeat

    return AuthSeat.from_config(tmp_path / "fresh")


def test_first_run_makes_softmatter_with_the_typed_password(engine, make_client, empty_seat):
    c = make_client(engine, login=None, auth=empty_seat)
    assert c.get("/api/auth/setup").json() == {"state": "needs_admin", "admin_login": "softmatter"}
    r = c.post("/api/auth/setup/admin", json={"password": "admin-pass-1"}, headers=OWN)
    assert r.status_code == 200
    assert (r.json()["user_id"], r.json()["role"], r.json()["name"]) == ("softmatter", "admin", "softmatter")
    assert SESSION_COOKIE in r.headers["set-cookie"]
    assert "admin-pass-1" not in r.text
    assert c.get("/api/auth/me").json()["role"] == "admin"  # logged in by the setup
    assert c.get("/api/auth/setup").json() == {"state": "ready", "admin_login": None}
    again = c.post("/api/auth/setup/admin", json={"password": "admin-pass-2"}, headers=OWN)
    assert (again.status_code, detail(again)["code"]) == (409, "setup_done")
    created = [e for e in empty_seat.audit.entries() if e["kind"] == "account_created"]
    assert created[-1]["via"] == "first_admin_setup" and created[-1]["user_id"] == "softmatter"


def test_first_run_uses_the_login_in_the_settings(engine, make_client, empty_seat, tmp_path):
    import json as _json

    cfg = tmp_path / "fresh"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "settings.json").write_text(_json.dumps({"admin_login": "labadmin"}), encoding="utf-8")
    c = make_client(engine, login=None, auth=empty_seat)
    assert c.get("/api/auth/setup").json()["admin_login"] == "labadmin"
    r = c.post("/api/auth/setup/admin", json={"name": "Lab Admin", "password": "admin-pass-1"}, headers=OWN)
    assert (r.status_code, r.json()["user_id"], r.json()["name"]) == (200, "labadmin", "Lab Admin")


def test_first_run_refuses_a_settings_value_that_is_an_email(engine, make_client, empty_seat, tmp_path):
    import json as _json

    cfg = tmp_path / "fresh"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "settings.json").write_text(_json.dumps({"admin_login": "boss@example.test"}), encoding="utf-8")
    c = make_client(engine, login=None, auth=empty_seat)
    assert c.get("/api/auth/setup").json() == {"state": "needs_admin", "admin_login": None}
    r = c.post("/api/auth/setup/admin", json={"password": "admin-pass-1"}, headers=OWN)
    assert (r.status_code, detail(r)["code"]) == (409, "setup_required")
    assert "plain id" in detail(r)["message"]
    assert not empty_seat.accounts.has_admin()


def test_first_run_takes_no_login_from_the_request(engine, make_client, empty_seat):
    c = make_client(engine, login=None, auth=empty_seat)
    r = c.post("/api/auth/setup/admin", json={"password": "admin-pass-1", "login": "mine"}, headers=OWN)
    assert r.status_code == 422  # the administrator's login is the settings', not the caller's
    r = c.post("/api/auth/setup/admin", json={"password": "admin-pass-1", "email": "a@b.example.test"}, headers=OWN)
    assert r.status_code == 422
    assert not empty_seat.accounts.has_admin()


@pytest.mark.parametrize("typed", ["boss@example.test", "a@b", "kim lee", "", ".kim", "x" * 65])
def test_an_email_or_anything_not_a_plain_id_is_refused_at_registration_and_login(
        engine, make_client, seat, typed):
    c = make_client(engine, login=None)
    r = c.post("/api/auth/signup", json={"name": "Kim", "login": typed, "password": "kim-pass-12"})
    assert (r.status_code, detail(r)["code"]) == (422, "invalid")
    assert "plain id" in detail(r)["message"]
    r = c.post("/api/auth/login", json={"login": typed, "password": TEST_PASSWORD})
    assert (r.status_code, detail(r)["code"]) == (422, "not_a_login")
    assert "set-cookie" not in r.headers
    assert [a for a in seat.accounts.accounts() if a.login == typed] == []


def test_the_administrator_login_cannot_be_registered(engine, make_client, seat):
    c = make_client(engine, login=None)
    r = c.post("/api/auth/signup", json={"name": "Not Admin", "login": "softmatter", "password": "kim-pass-12"})
    assert (r.status_code, detail(r)["code"]) == (409, "login_reserved")
    assert seat.accounts.get("softmatter") is None


def test_email_keyed_accounts_are_listed_for_the_administrator_and_given_a_login(
        engine, make_client, seat):
    import json as _json

    old = {"email": "old.member@example.test", "name": "Old Member", "role": "operator", "status": "active",
           "password_hash": seat.accounts.get(VIEWER).password_hash, "created_at": "2026-10-01T00:00:00+00:00",
           "approved_by": None, "approved_at": None}
    path = seat.accounts.path
    data = _json.loads(path.read_text(encoding="utf-8"))
    data["accounts"].append(old)
    path.write_text(_json.dumps(data), encoding="utf-8")
    seat.accounts.__init__(path, audit=seat.audit)  # the store reads the file again
    admin = make_client(engine, login=ADMIN)
    listed = admin.get("/api/auth/accounts/needs-login").json()
    assert [n["email"] for n in listed] == ["old.member@example.test"]
    assert "password" not in str(listed)
    assert make_client(engine, login=None).post(
        "/api/auth/login", json={"login": "old.member@example.test", "password": TEST_PASSWORD}
    ).status_code == 422  # it cannot log in
    bad = admin.post("/api/auth/accounts/give-login", json={"email": "old.member@example.test", "login": "old@x.test"})
    assert (bad.status_code, detail(bad)["code"]) == (422, "invalid")
    r = admin.post("/api/auth/accounts/give-login", json={"email": "old.member@example.test", "login": "old.member"})
    assert r.status_code == 200 and r.json()["login"] == "old.member" and "email" not in r.json()
    assert admin.get("/api/auth/accounts/needs-login").json() == []
    line = [e for e in seat.audit.entries() if e["kind"] == "account_login_given"][-1]
    assert (line["user_id"], line["account"], line["former_email"]) == (ADMIN, "old.member", "old.member@example.test")
    missing = admin.post("/api/auth/accounts/give-login", json={"email": "ghost@example.test", "login": "ghost"})
    assert (missing.status_code, detail(missing)["code"]) == (404, "no_account")
    assert make_client(engine, login=None).post(
        "/api/auth/login", json={"login": "old.member", "password": TEST_PASSWORD}).status_code == 200


@pytest.mark.parametrize("who", [OPERATOR, VIEWER])
def test_only_an_administrator_here_sees_or_gives_logins(engine, make_client, who):
    c = make_client(engine, login=who)
    assert detail(c.get("/api/auth/accounts/needs-login"))["code"] == "role"
    r = c.post("/api/auth/accounts/give-login", json={"email": "a@b.example.test", "login": "ab"})
    assert (r.status_code, detail(r)["code"]) == (403, "role")
    remote = make_client(engine, remote=True, login=ADMIN)
    assert detail(remote.get("/api/auth/accounts/needs-login"))["code"] == "remote_view"


def test_no_password_in_any_auth_response(engine, make_client, seat):
    c = make_client(engine, login=ADMIN)
    texts = [c.get("/api/auth/me").text, c.get("/api/auth/accounts").text, c.get("/api/auth/accounts/needs-login").text,
             c.get("/api/auth/setup").text]
    r = c.post(f"/api/auth/accounts/{VIEWER}/password", json={"password": "fresh-pass-word-1"})
    texts.append(r.text)
    texts.append(make_client(engine, login=None).post(
        "/api/auth/login", json={"login": VIEWER, "password": "fresh-pass-word-1"}).text)
    for text in texts:
        assert "fresh-pass-word-1" not in text and TEST_PASSWORD not in text and "scrypt" not in text
    log = seat.audit.path.read_text(encoding="utf-8")
    assert "fresh-pass-word-1" not in log and TEST_PASSWORD not in log and "scrypt" not in log


def test_first_run_refuses_another_loopback_port_and_remote(engine, make_client, empty_seat):
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
