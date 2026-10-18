"""Login sessions: tokens, pending notice, idle lock and unlock, expiry, role changes apply."""

from dino_autofocus.auth import LoginOutcome, Role


def test_login_issues_a_token_and_logout_ends_it(logins, seed_password, audit):
    r = logins.login("Otto@Example.test", seed_password)
    assert r.ok and r.token and r.info.user_id == "otto@example.test"
    assert r.info.role is Role.OPERATOR and not r.info.locked
    assert logins.get(r.token).login_id == r.info.login_id
    assert logins.logout(r.token) and logins.get(r.token) is None
    kinds = [e["kind"] for e in audit.entries()]
    assert "login" in kinds and "logout" in kinds
    assert all(r.token not in str(e) for e in audit.entries())


def test_failures_say_why_without_a_token(logins, seed_password, audit):
    bad = logins.login("otto@example.test", "wrong-pass")
    assert bad.outcome is LoginOutcome.BAD_CREDENTIALS and bad.token is None
    pending = logins.login("pat@example.test", seed_password)
    assert pending.outcome is LoginOutcome.PENDING and pending.token is None
    assert "approval" in pending.message
    failed = [e for e in audit.entries() if e["kind"] == "login_failed"]
    assert [e["reason"] for e in failed] == ["bad_credentials", "pending_approval"]


def test_idle_session_locks_and_unlocks_with_the_password(logins, login, clock, seed_password):
    token = login("otto@example.test")
    clock.advance(599)
    assert not logins.touch(token).locked  # input resets the idle timer
    clock.advance(599)
    assert not logins.get(token).locked
    clock.advance(1)
    assert logins.get(token).locked
    assert logins.touch(token).locked  # input on a locked screen does not unlock it
    assert logins.unlock(token, "wrong-pass") is None and logins.get(token).locked
    assert not logins.unlock(token, seed_password).locked


def test_manual_lock(logins, login):
    token = login("vera@example.test")
    assert logins.lock(token).locked


def test_session_expires_after_max_age_and_ends_listeners(logins, login, clock):
    ended = []
    logins.on_end(ended.append)
    token = login("otto@example.test")
    login_id = logins.get(token).login_id
    clock.advance(3600)
    assert logins.get(token) is None and ended == [login_id]


def test_role_change_applies_at_once_and_disabling_ends_the_session(logins, login, seeded):
    token = login("vera@example.test")
    seeded.set_role("admin@example.test", "vera@example.test", "operator")
    assert logins.get(token).role is Role.OPERATOR
    seeded.disable("admin@example.test", "vera@example.test")
    assert logins.get(token) is None


def test_unknown_token(logins):
    assert logins.get("not-a-token") is None and not logins.logout("not-a-token")


def test_end_user_ends_every_login_of_that_account_only(logins, login, audit):
    a, b, other = login("vera@example.test"), login("vera@example.test"), login("otto@example.test")
    assert logins.end_user("vera@example.test", "password_reset") == 2
    assert logins.get(a) is None and logins.get(b) is None
    assert logins.get(other) is not None
    reasons = [e["reason"] for e in audit.entries() if e["kind"] == "logout"]
    assert reasons.count("password_reset") == 2


def test_deleting_an_account_ends_its_login(logins, login, seeded):
    token = login("vera@example.test")
    seeded.disable("admin@example.test", "vera@example.test")
    seeded.delete("admin@example.test", "vera@example.test")
    assert logins.get(token) is None



def test_wrong_passwords_lock_the_account_and_a_right_one_clears_its_count(seeded, audit, clock,
                                                                         seed_password):
    from dino_autofocus.auth import AttemptLimiter, LoginSessions

    logins = LoginSessions(seeded, audit=audit, clock=clock,
                           limiter=AttemptLimiter(account_limit=3, client_limit=10,
                                                  window_s=60, lockout_s=120, clock=clock))
    for _ in range(2):
        assert logins.login("vera@example.test", "bad-pass-123", client="10.0.0.9").outcome \
            is LoginOutcome.BAD_CREDENTIALS
    assert logins.login("vera@example.test", seed_password, client="10.0.0.9").ok  # clears it
    for _ in range(3):
        logins.login("vera@example.test", "bad-pass-123", client="10.0.0.9")
    locked = logins.login("vera@example.test", seed_password, client="10.0.0.9")
    assert locked.outcome is LoginOutcome.TOO_MANY and 0 < locked.retry_after_s <= 120
    assert any(e.get("reason") == "lockout_started" for e in audit.entries())
    clock.t += 121
    assert logins.login("vera@example.test", seed_password, client="10.0.0.9").ok


def test_the_client_limit_covers_many_accounts(seeded, audit, clock, seed_password):
    from dino_autofocus.auth import AttemptLimiter, LoginSessions

    logins = LoginSessions(seeded, audit=audit, clock=clock,
                           limiter=AttemptLimiter(account_limit=10, client_limit=3,
                                                  window_s=60, lockout_s=60, clock=clock))
    for who in ("a@example.test", "b@example.test", "c@example.test"):
        logins.login(who, "guess-guess-1", client="10.0.0.7")
    assert logins.login("otto@example.test", seed_password, client="10.0.0.7").outcome \
        is LoginOutcome.TOO_MANY
    assert logins.login("otto@example.test", seed_password, client="10.0.0.8").ok


def test_pending_or_disabled_with_the_right_password_is_no_guess(seeded, audit, clock,
                                                                seed_password):
    from dino_autofocus.auth import AttemptLimiter, LoginSessions

    logins = LoginSessions(seeded, audit=audit, clock=clock,
                           limiter=AttemptLimiter(account_limit=2, clock=clock))
    for _ in range(4):
        assert logins.login("pat@example.test", seed_password).outcome is LoginOutcome.PENDING


def test_unlock_checks_the_password_outside_the_lock(logins, login, seeded, seed_password):
    import threading as th

    other = login("otto@example.test")
    token = login("vera@example.test")
    logins.lock(token)
    entered, release = th.Event(), th.Event()
    real = seeded.authenticate

    def slow(email, password):
        entered.set()
        release.wait(5)
        return real(email, password)

    seeded.authenticate = slow
    t = th.Thread(target=lambda: logins.unlock(token, seed_password))
    t.start()
    try:
        assert entered.wait(5)
        done = th.Event()
        th.Thread(target=lambda: (logins.get(other), done.set())).start()
        assert done.wait(1.0)  # another request is not stuck behind the slow check
    finally:
        release.set()
        t.join(5)
        seeded.authenticate = real
    assert logins.get(token).locked is False


def test_unlock_of_a_session_that_ended_during_the_check_does_nothing(logins, login, seeded,
                                                                     seed_password):
    token = login("vera@example.test")
    logins.lock(token)
    real = seeded.authenticate

    def logout_meanwhile(email, password):
        logins.logout(token)
        return real(email, password)

    seeded.authenticate = logout_meanwhile
    try:
        assert logins.unlock(token, seed_password) is None
    finally:
        seeded.authenticate = real



def test_the_limiter_drops_stale_keys_and_caps_their_length():
    from dino_autofocus.auth import throttle

    t = [0.0]
    lim = throttle.AttemptLimiter(window_s=10, lockout_s=10, clock=lambda: t[0])
    assert lim.keys("x" * 1000, None) == [("account", "x" * throttle.MAX_KEY)]
    for i in range(throttle.PRUNE_AT + 1):
        lim.failed([("account", f"guess{i}@example.test")])
    t[0] = 100.0  # every count is stale now
    lim.failed([("account", "last@example.test")])
    assert len(lim._counts) == 1
