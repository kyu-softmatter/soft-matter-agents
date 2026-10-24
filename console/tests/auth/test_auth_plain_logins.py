"""Plain login ids, never an email (console card 009).

A console-signed approval carries the login as `signed_through.login`, which the plan approval
schema holds to a plain id: a committed approval is published, and an email in it would publish an
address. So an account is keyed by that id, and an email is refused where a login is typed.
"""

import importlib.util
import json
import re
from pathlib import Path

import pytest

from sma_console.auth import AccountStore, AuditKind, AuditLog, LoginSessions
from sma_console.auth import accounts as accounts_mod
from sma_console.auth import config as auth_config
from sma_console.auth.accounts import AccountError, DuplicateAccountError, LoginOutcome, PermissionDenied

REPO = Path(__file__).resolve().parents[3]
SCHEMA = REPO / "contracts" / "schemas" / "plan_approval.schema.json"
PW = "pass-word-1"


def _settings(config_dir: Path, **values) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "settings.json").write_text(json.dumps(values), encoding="utf-8")


# -- the pattern -------------------------------------------------------------------------------


def test_the_pattern_is_the_approval_schemas_own():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    pattern = schema["properties"]["signed_through"]["properties"]["login"]["pattern"]
    assert accounts_mod.LOGIN_PATTERN == pattern


@pytest.mark.parametrize("login", ["softmatter", "ada", "a", "A1", "kim.lee", "kim-lee", "kim_lee", "a" * 64])
def test_plain_ids_are_logins(login):
    assert accounts_mod.check_login(login) == login


@pytest.mark.parametrize("bad", [
    "kim@example.test", "a@b", "", " ", " kim", "kim ", "kim lee", ".kim", "-kim", "_kim", "a" * 65,
    "kim\n", "kim\n\n", "kiño", "١٢", "kim/lee", None, 7,
])
def test_anything_else_is_refused(bad):
    with pytest.raises(AccountError):
        accounts_mod.check_login(bad)


def test_the_refusal_says_why_in_plain_words():
    with pytest.raises(AccountError, match="plain id") as e:
        accounts_mod.check_login("kim@example.test")
    assert "email" in str(e.value)


def test_a_login_keeps_its_case(store):
    """The runtime compares the login byte for byte, so it is stored exactly as typed."""
    store.register("Kim Lee", "Kim.Lee", PW)
    assert store.get("Kim.Lee").login == "Kim.Lee"
    assert store.get("kim.lee") is None


def test_a_login_that_differs_only_by_case_is_refused(store):
    store.register("Kim Lee", "kim", PW)
    with pytest.raises(DuplicateAccountError):
        store.register("Other Kim", "KIM", PW)


# -- an email is refused at registration, login and first start ----------------------------------


def test_registration_refuses_an_email(store):
    with pytest.raises(AccountError, match="plain id"):
        store.register("Kim Lee", "kim@example.test", PW)
    assert store.accounts() == []


def test_login_refuses_an_email_before_any_password_is_checked(seeded, logins, seed_password):
    result = logins.login("ada@example.test", seed_password)
    assert result.outcome is LoginOutcome.NOT_A_LOGIN and not result.ok and result.token is None
    assert "plain id" in result.message and "email" in result.message
    assert seeded.authenticate("ada@example.test", seed_password).outcome is LoginOutcome.NOT_A_LOGIN


def test_first_start_refuses_a_configured_email(store, isolated_config):
    _settings(isolated_config, admin_login="boss@example.test")
    with pytest.raises(AccountError, match="plain id"):
        store.create_first_admin("Boss", PW)
    assert store.accounts() == []


def test_an_old_admin_email_setting_and_environment_are_not_read(store, isolated_config, monkeypatch):
    _settings(isolated_config, admin_email="lab@example.test")
    monkeypatch.setenv("DINO_AF_ADMIN_EMAIL", "boss@example.test")
    assert not hasattr(auth_config, "admin_email")
    assert store.create_first_admin("Admin", PW).login == "softmatter"


# -- the first administrator's login -------------------------------------------------------------


def test_admin_login_defaults_to_softmatter(isolated_config):
    assert auth_config.DEFAULT_ADMIN_LOGIN == "softmatter"
    assert auth_config.admin_login(isolated_config) == "softmatter"


def test_a_settings_value_overrides_it(isolated_config):
    _settings(isolated_config, admin_login="labadmin")
    assert auth_config.admin_login(isolated_config) == "labadmin"


def test_a_blank_settings_value_falls_back_to_the_default(isolated_config):
    _settings(isolated_config, admin_login="  ")
    assert auth_config.admin_login(isolated_config) == "softmatter"


def test_first_start_creates_that_account_with_the_typed_password(store, audit):
    assert store.setup_state() is accounts_mod.SetupState.NEEDS_ADMIN
    acc = store.create_first_admin("", PW)
    assert acc.login == "softmatter" and acc.name == "softmatter"
    assert acc.role.value == "admin" and acc.status.value == "active"
    assert store.setup_state() is accounts_mod.SetupState.READY
    assert store.authenticate("softmatter", PW).ok
    created = next(e for e in audit.entries() if e["kind"] == "account_created")
    assert created["user_id"] == "softmatter" and created["via"] == "first_admin_setup"
    with pytest.raises(AccountError):
        store.create_first_admin("Second", "pass-word-2")


def test_first_start_uses_the_settings_login(store, isolated_config):
    _settings(isolated_config, admin_login="labadmin")
    assert store.create_first_admin("Lab Admin", PW).login == "labadmin"


def test_no_credential_ships_in_code_or_settings():
    """The default login is a name, not a secret; config.py has no password name or default."""
    import ast

    tree = ast.parse((REPO / "console" / "src" / "sma_console" / "auth" / "config.py").read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.arg)) and hasattr(n, "name")}
    names |= {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
    assert not [n for n in names if "pass" in n.lower() or "secret" in n.lower() or "credential" in n.lower()]
    strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and len(n.value) < 40}
    assert not [s for s in strings if "pass" in s.lower() and " " not in s]


def test_the_admin_login_cannot_be_registered_by_someone_else(store):
    with pytest.raises(AccountError, match="reserved"):
        store.register("Not the admin", "softmatter", PW)
    assert store.accounts() == []


# -- an account keyed by email from before ---------------------------------------------------------


def _legacy_file(path: Path, *, admin_active=True) -> list[dict]:
    rows = [
        {"email": "ada@example.test", "name": "Ada Admin", "role": "admin",
         "status": "active" if admin_active else "disabled", "password_hash": "scrypt$old-admin-hash",
         "created_at": "2026-10-01T00:00:00+00:00", "approved_by": None, "approved_at": None},
        {"email": "otto@example.test", "name": "Otto Operator", "role": "operator", "status": "active",
         "password_hash": "scrypt$old-otto-hash", "created_at": "2026-10-02T00:00:00+00:00",
         "approved_by": "ada@example.test", "approved_at": "2026-10-02T01:00:00+00:00"},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "accounts": rows}, indent=2), encoding="utf-8")
    return rows


def test_an_email_keyed_account_loads_as_needs_a_login_id(tmp_path, audit):
    path = tmp_path / "config" / "accounts.json"
    _legacy_file(path)
    store = AccountStore(path, audit=audit)
    assert store.accounts() == []
    needing = store.needs_login()
    assert [n.email for n in needing] == ["ada@example.test", "otto@example.test"]
    assert needing[1].name == "Otto Operator" and needing[1].role.value == "operator"
    assert "password_hash" not in needing[1].public() and needing[1].public()["email"] == "otto@example.test"


def test_it_cannot_log_in_and_is_not_lost(tmp_path, audit):
    path = tmp_path / "config" / "accounts.json"
    rows = _legacy_file(path)
    store = AccountStore(path, audit=audit)
    sessions = LoginSessions(store, audit=audit)
    for who in ("ada@example.test", "ada", "otto"):
        assert not sessions.login(who, PW).ok
    # another account is added and the file saved: the old records are written back as they were
    store.register("Kim Lee", "kim", PW)
    saved = json.loads(path.read_text(encoding="utf-8"))["accounts"]
    assert [r for r in saved if "email" in r] == rows
    assert [r["login"] for r in saved if "login" in r] == ["kim"]
    assert [n.email for n in AccountStore(path).needs_login()] == ["ada@example.test", "otto@example.test"]


def test_when_the_only_admin_is_email_keyed_first_start_appears_and_the_old_record_stays(tmp_path, audit):
    path = tmp_path / "config" / "accounts.json"
    rows = _legacy_file(path)
    store = AccountStore(path, audit=audit)
    assert not store.has_admin()
    assert store.setup_state() is accounts_mod.SetupState.NEEDS_ADMIN
    store.create_first_admin("Admin", PW)
    saved = json.loads(path.read_text(encoding="utf-8"))["accounts"]
    assert [r for r in saved if "email" in r] == rows
    assert [r["login"] for r in saved if "login" in r] == ["softmatter"]


def test_the_administrator_gives_it_a_plain_login_and_the_audit_names_both(tmp_path, audit):
    path = tmp_path / "config" / "accounts.json"
    _legacy_file(path)
    store = AccountStore(path, audit=audit)
    store.create_first_admin("Admin", PW)
    acc = store.give_login("softmatter", "otto@example.test", "otto")
    assert acc.login == "otto" and acc.role.value == "operator" and acc.status.value == "active"
    assert acc.name == "Otto Operator" and acc.approved_by == "ada@example.test"
    assert [n.email for n in store.needs_login()] == ["ada@example.test"]
    line = next(e for e in audit.entries() if e["kind"] == "account_login_given")
    assert line["user_id"] == "softmatter" and line["account"] == "otto" and line["former_email"] == "otto@example.test"
    # the password the person had is the one the account keeps
    store2 = AccountStore(path)
    assert store2.get("otto").password_hash == "scrypt$old-otto-hash"
    assert store2.get("otto").public().get("former_email") is None
    assert [n.email for n in store2.needs_login()] == ["ada@example.test"]


def test_giving_a_login_is_for_an_active_admin_and_a_plain_free_id(tmp_path, audit):
    path = tmp_path / "config" / "accounts.json"
    _legacy_file(path)
    store = AccountStore(path, audit=audit)
    store.create_first_admin("Admin", PW)
    store.register("Kim", "kim", PW)
    with pytest.raises(PermissionDenied):
        store.give_login("kim", "otto@example.test", "otto")  # pending, not an admin
    with pytest.raises(AccountError, match="plain id"):
        store.give_login("softmatter", "otto@example.test", "otto@example.test")
    with pytest.raises(DuplicateAccountError):
        store.give_login("softmatter", "otto@example.test", "kim")
    with pytest.raises(DuplicateAccountError):
        store.give_login("softmatter", "otto@example.test", "KIM")
    with pytest.raises(AccountError, match="no account"):
        store.give_login("softmatter", "nobody@example.test", "nobody")
    assert len(store.needs_login()) == 2


def test_an_unreadable_row_is_an_error_not_a_silent_drop(tmp_path):
    path = tmp_path / "config" / "accounts.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": 1, "accounts": [{"name": "No key"}]}), encoding="utf-8")
    with pytest.raises(AccountError):
        AccountStore(path)


# -- accounts are switched off, never deleted -----------------------------------------------------


def test_there_is_no_delete(seeded):
    assert not hasattr(AccountStore, "delete")
    assert "ACCOUNT_DELETED" not in AuditKind.__members__
    assert seeded.get("vera").status.value == "active"
    seeded.disable("ada", "vera")
    assert seeded.get("vera") is not None and seeded.get("vera").status.value == "disabled"


# -- the take-and-release control is gone ---------------------------------------------------------


def test_the_control_module_is_gone():
    assert importlib.util.find_spec("sma_console.auth.control") is None
    import sma_console.auth as auth

    for name in ("DeviceControl", "ControlBusy", "ControlError", "ControlGrant", "ControlHolder", "Decision"):
        assert not hasattr(auth, name), name
    assert not any(k.startswith("CONTROL_") for k in AuditKind.__members__)


# -- no password anywhere it should not be ----------------------------------------------------------


def test_no_password_in_the_audit_log_or_the_public_account(tmp_path, audit):
    path = tmp_path / "config" / "accounts.json"
    _legacy_file(path)
    store = AccountStore(path, audit=audit)
    sessions = LoginSessions(store, audit=audit)
    secret = "very-secret-pass-1"
    store.create_first_admin("Admin", secret)
    store.register("Kim", "kim", secret + "-k")
    sessions.login("softmatter", secret)
    sessions.login("softmatter", "wrong-pass-word")
    store.approve("softmatter", "kim", "operator")
    store.reset_password("softmatter", "kim", secret + "-new")
    store.give_login("softmatter", "otto@example.test", "otto")
    log = Path(audit.path).read_text(encoding="utf-8")
    for word in (secret, secret + "-k", secret + "-new", "wrong-pass-word", "scrypt$"):
        assert word not in log
    for acc in store.accounts():
        assert "password" not in json.dumps(acc.public())
    for n in store.needs_login():
        assert "password" not in json.dumps(n.public())
    assert not re.search(r"password_hash", log)
