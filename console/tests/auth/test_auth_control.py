"""Device control: one holder, release and admin revoke, roles, and stop always accepted."""

import pytest

from dino_autofocus.auth import Action, ControlBusy, ControlError, Role, allows


def test_one_operator_at_a_time(control, login):
    otto, olga = login("otto@example.test"), login("olga@example.test")
    grant = control.acquire(otto, local=True)
    assert control.acquire(otto, local=True) == grant  # asking again keeps the same grant
    with pytest.raises(ControlBusy) as e:
        control.acquire(olga, local=True)
    assert e.value.holder == "otto@example.test"
    assert control.holder().user_id == "otto@example.test"
    assert control.check(grant.token) == grant
    control.release(otto)
    assert control.holder() is None
    with pytest.raises(ControlError):
        control.check(grant.token)
    assert control.acquire(olga, local=True).user_id == "olga@example.test"


def test_only_the_holder_releases(control, login):
    otto, olga = login("otto@example.test"), login("olga@example.test")
    control.acquire(otto, local=True)
    with pytest.raises(ControlError):
        control.release(olga)


def test_viewer_cannot_take_control_and_admin_can(control, login):
    with pytest.raises(ControlError):
        control.acquire(login("vera@example.test"), local=True)
    assert control.acquire(login("admin@example.test"), local=True).user_id == "admin@example.test"


def test_admin_revokes_and_operator_cannot(control, login, audit):
    otto, olga, admin = (login(e) for e in
                         ("otto@example.test", "olga@example.test", "admin@example.test"))
    grant = control.acquire(otto, local=True)
    with pytest.raises(ControlError):
        control.revoke(olga, "want it")
    held = control.revoke(admin, "otto left the room")
    assert held.user_id == "otto@example.test" and control.holder() is None
    with pytest.raises(ControlError):
        control.check(grant.token)
    entry = [e for e in audit.entries() if e["kind"] == "control_revoked"][-1]
    assert entry["user_id"] == "admin@example.test" and entry["holder"] == "otto@example.test"
    assert entry["reason"] == "otto left the room"


def test_logout_and_expiry_free_control(control, logins, login, clock):
    otto = login("otto@example.test")
    control.acquire(otto, local=True)
    logins.logout(otto)
    assert control.holder() is None
    olga = login("olga@example.test")
    control.acquire(olga, local=True)
    clock.advance(3600)
    assert control.holder() is None


def test_locked_screen_keeps_control_but_cannot_command(control, logins, login, clock):
    otto = login("otto@example.test")
    grant = control.acquire(otto, local=True)
    clock.advance(600)
    assert logins.get(otto).locked
    assert control.check(grant.token) == grant  # running work keeps its control
    d = control.authorize(Action.OPERATE, otto, grant.token, local=True)
    assert not d.allowed and "locked" in d.reason
    with pytest.raises(ControlError):
        control.acquire(otto, local=True)


def test_operate_needs_login_role_and_own_control_token(control, login):
    otto, olga, vera = (login(e) for e in
                        ("otto@example.test", "olga@example.test", "vera@example.test"))
    assert not control.authorize(Action.OPERATE, None, local=True).allowed
    assert not control.authorize(Action.OPERATE, otto, local=True).allowed  # no control token
    grant = control.acquire(otto, local=True)

    def operate(who, token=grant.token, local=True):
        return control.authorize(Action.OPERATE, who, token, local=local).allowed

    assert operate(otto)
    assert not operate(otto, local=False)  # remote: read only, even for the holder
    assert not operate(olga)  # someone else's token
    assert not operate(vera)  # viewer
    assert not operate(otto, token="forged")


def test_control_is_taken_on_the_microscope_pc_only(control, login):
    with pytest.raises(ControlError, match="microscope PC"):
        control.acquire(login("otto@example.test"))


# -- D16: questions and map flags: operator, on the microscope PC -------------------------------


@pytest.mark.parametrize("action", [Action.SUBMIT_QUESTION, Action.WRITE_MAP_FLAG])
def test_viewer_refused_remote_operator_refused_local_operator_allowed(control, login, action):
    vera, otto, admin = (login(e) for e in
                         ("vera@example.test", "otto@example.test", "admin@example.test"))
    assert not control.authorize(action, vera, local=True).allowed
    assert not control.authorize(action, vera).allowed
    remote = control.authorize(action, otto)
    assert not remote.allowed and "microscope PC" in remote.reason
    assert control.authorize(action, otto, local=True).allowed  # no device control needed
    assert control.authorize(action, admin, local=True).allowed
    assert not control.authorize(action, None, local=True).allowed


@pytest.mark.parametrize("action", [Action.SUBMIT_QUESTION, Action.WRITE_MAP_FLAG,
                                    Action.OPERATE])
def test_local_only_actions_in_roles(action):
    assert not allows(Role.OPERATOR, action)
    assert allows(Role.OPERATOR, action, local=True)
    assert not allows(Role.VIEWER, action, local=True)


def test_stop_is_accepted_remotely_too(control, login):
    assert control.authorize(Action.STOP, login("vera@example.test"), local=False).allowed


@pytest.mark.parametrize("who", [None, "vera@example.test", "olga@example.test"])
def test_stop_is_always_accepted(control, logins, login, clock, who):
    otto = login("otto@example.test")
    control.acquire(otto, local=True)
    token = login(who) if who else None
    clock.advance(600)  # every screen is locked now
    if token:
        assert logins.get(token).locked
    d = control.authorize(Action.STOP, token)
    assert d.allowed and d.user_id == who


def test_view_and_manage(control, login):
    vera, admin = login("vera@example.test"), login("admin@example.test")
    assert control.authorize(Action.VIEW, vera).allowed
    assert not control.authorize(Action.VIEW, None).allowed  # remote viewing needs a login too
    assert not control.authorize(Action.MANAGE_USERS, vera).allowed
    assert control.authorize(Action.MANAGE_USERS, admin).allowed
