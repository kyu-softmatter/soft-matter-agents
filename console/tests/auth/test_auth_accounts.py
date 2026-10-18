"""Accounts: email ids without case, one account per email, register -> pending -> approved
with an admin-chosen role (D12), first admin from configuration only, the file holds no secret."""

import json
import re
from pathlib import Path

import pytest

from dino_autofocus.auth import (
    AccountError,
    AccountStatus,
    AccountStore,
    DuplicateAccountError,
    LoginOutcome,
    PasswordPolicyError,
    PermissionDenied,
    Role,
    SetupRequired,
    SetupState,
    normalize_email,
    passwords,
)
from dino_autofocus.auth import config as auth_config

REPO = Path(__file__).resolve().parents[2]


def test_email_is_compared_without_case(store):
    store.register("Kim Lee", "  Kim.Lee@Example.TEST ", "pass-word-1")
    acc = store.get("kim.lee@example.test")
    assert acc is not None and acc.email == "kim.lee@example.test"
    assert store.get("KIM.LEE@EXAMPLE.TEST") == acc
    assert normalize_email("A@B.example.test") == "a@b.example.test"


@pytest.mark.parametrize("bad", ["", "no-at", "@example.test", "a@nodot", "a b@example.test",
                                 "a@@example.test"])
def test_not_an_email_is_refused(store, bad):
    with pytest.raises(AccountError):
        store.register("Someone", bad, "pass-word-1")


def test_duplicate_email_is_refused_whatever_the_case(store):
    store.register("Kim Lee", "kim@example.test", "pass-word-1")
    with pytest.raises(DuplicateAccountError):
        store.register("Other Kim", "KIM@example.test", "pass-word-2")
    assert len(store.accounts()) == 1


def test_registration_takes_name_email_password_and_starts_pending_viewer(store):
    acc = store.register("Kim Lee", "kim@example.test", "pass-word-1")
    assert acc.status is AccountStatus.PENDING and acc.role is Role.VIEWER
    assert acc.approved_by is None and acc.created_at
    with pytest.raises(TypeError):
        store.register("Kim", "kim2@example.test", "pass-word-1", role="admin")  # no role choice


def test_bad_name_or_password_stores_nothing(store):
    with pytest.raises(AccountError):
        store.register("   ", "kim@example.test", "pass-word-1")
    with pytest.raises(PasswordPolicyError):
        store.register("Kim", "kim@example.test", "short")
    assert store.accounts() == []


def test_pending_account_cannot_log_in_and_is_told_so(seeded, seed_password):
    assert seeded.authenticate("pat@example.test", seed_password).outcome is LoginOutcome.PENDING
    # a wrong password says nothing about the account's state
    assert seeded.authenticate("pat@example.test", "wrong-pass").outcome is \
        LoginOutcome.BAD_CREDENTIALS
    assert seeded.authenticate("nobody@example.test", seed_password).outcome is \
        LoginOutcome.BAD_CREDENTIALS


def test_admin_approves_and_sets_role(seeded, audit, seed_password):
    acc = seeded.approve("ADMIN@example.test", "pat@example.test", "operator")
    assert acc.status is AccountStatus.ACTIVE and acc.role is Role.OPERATOR
    assert acc.approved_by == "admin@example.test" and acc.approved_at
    assert seeded.authenticate("pat@example.test", seed_password).ok
    entry = [e for e in audit.entries() if e["kind"] == "account_approved"][-1]
    assert entry["user_id"] == "admin@example.test" and entry["account"] == "pat@example.test"
    assert entry["approved_by"] == "admin@example.test" and entry["role"] == "operator"
    assert entry["created_at"] == acc.created_at
    with pytest.raises(AccountError):
        seeded.approve("admin@example.test", "pat@example.test", "admin")  # already approved


@pytest.mark.parametrize("who", ["otto@example.test", "vera@example.test", "pat@example.test",
                                 "nobody@example.test"])
def test_only_an_active_admin_approves(seeded, who):
    with pytest.raises(PermissionDenied):
        seeded.approve(who, "pat@example.test", "operator")


def test_creation_is_audited_with_its_time(store, audit):
    acc = store.register("Kim Lee", "kim@example.test", "pass-word-1")
    entry = next(e for e in audit.entries() if e["kind"] == "account_created")
    assert entry["user_id"] == "kim@example.test" and entry["created_at"] == acc.created_at
    assert entry["status"] == "pending" and entry["role"] == "viewer"


def test_last_admin_cannot_be_demoted_or_disabled(seeded):
    with pytest.raises(AccountError):
        seeded.set_role("admin@example.test", "admin@example.test", "viewer")
    with pytest.raises(AccountError):
        seeded.disable("admin@example.test", "admin@example.test")
    seeded.set_role("admin@example.test", "otto@example.test", "admin")
    assert seeded.set_role("otto@example.test", "admin@example.test", "viewer").role is Role.VIEWER


def test_disabled_account_cannot_log_in(seeded, seed_password):
    seeded.disable("admin@example.test", "vera@example.test")
    assert seeded.authenticate("vera@example.test", seed_password).outcome is \
        LoginOutcome.DISABLED


def test_disabled_account_is_enabled_with_its_role(seeded, audit, seed_password):
    seeded.disable("admin@example.test", "otto@example.test")
    acc = seeded.enable("admin@example.test", "otto@example.test")
    assert acc.status is AccountStatus.ACTIVE and acc.role is Role.OPERATOR
    assert seeded.authenticate("otto@example.test", seed_password).ok
    entry = [e for e in audit.entries() if e["kind"] == "account_enabled"][-1]
    assert (entry["user_id"], entry["account"]) == ("admin@example.test", "otto@example.test")
    with pytest.raises(AccountError):
        seeded.enable("admin@example.test", "otto@example.test")  # already active
    with pytest.raises(AccountError):
        seeded.enable("admin@example.test", "pat@example.test")  # pending: approve instead


def test_admin_resets_a_password_and_the_old_one_stops_working(seeded, audit, seed_password):
    seeded.reset_password("admin@example.test", "vera@example.test", "new-pass-word-1")
    assert not seeded.authenticate("vera@example.test", seed_password).ok
    assert seeded.authenticate("vera@example.test", "new-pass-word-1").ok
    entry = [e for e in audit.entries() if e["kind"] == "account_password_reset"][-1]
    assert (entry["user_id"], entry["account"]) == ("admin@example.test", "vera@example.test")
    assert not any("pass-word" in json.dumps(e) for e in audit.entries())
    with pytest.raises(PasswordPolicyError):
        seeded.reset_password("admin@example.test", "vera@example.test", "x")
    assert seeded.authenticate("vera@example.test", "new-pass-word-1").ok


def test_delete_takes_pending_or_disabled_accounts_only(seeded, audit):
    with pytest.raises(AccountError):
        seeded.delete("admin@example.test", "vera@example.test")  # active: disable first
    seeded.delete("admin@example.test", "pat@example.test")  # a sign-up turned down
    seeded.disable("admin@example.test", "vera@example.test")
    seeded.delete("admin@example.test", "vera@example.test")
    assert seeded.get("pat@example.test") is None and seeded.get("vera@example.test") is None
    deleted = [e for e in audit.entries() if e["kind"] == "account_deleted"]
    assert [(e["account"], e["status"]) for e in deleted] == [
        ("pat@example.test", "pending"), ("vera@example.test", "disabled")]
    assert seeded.get("admin@example.test") is not None
    with pytest.raises(AccountError):
        seeded.delete("admin@example.test", "vera@example.test")  # gone


def test_an_admin_cannot_delete_themselves(seeded):
    seeded.set_role("admin@example.test", "otto@example.test", "admin")
    seeded.disable("otto@example.test", "admin@example.test")
    with pytest.raises(PermissionDenied):  # a disabled admin is no admin
        seeded.delete("admin@example.test", "admin@example.test")
    with pytest.raises(AccountError):
        seeded.delete("otto@example.test", "otto@example.test")


@pytest.mark.parametrize("act", ["enable", "reset_password", "delete"])
def test_only_an_active_admin_enables_resets_or_deletes(seeded, act):
    seeded.disable("admin@example.test", "vera@example.test")
    args = ("new-pass-word-1",) if act == "reset_password" else ()
    with pytest.raises(PermissionDenied):
        getattr(seeded, act)("otto@example.test", "vera@example.test", *args)
    assert seeded.get("vera@example.test").status is AccountStatus.DISABLED


def test_file_round_trip_holds_hashes_only(seeded, tmp_path, seed_password):
    raw = (tmp_path / "config" / "accounts.json").read_text(encoding="utf-8")
    assert seed_password not in raw
    reopened = AccountStore(tmp_path / "config" / "accounts.json")
    assert [a.public() for a in reopened.accounts()] == [a.public() for a in seeded.accounts()]
    assert reopened.authenticate("otto@example.test", seed_password).ok
    assert "password_hash" not in reopened.get("otto@example.test").public()


def test_default_files_live_in_the_settings_folder_not_the_repo(isolated_config):
    store = AccountStore()
    assert store.path == isolated_config / "accounts.json"
    assert REPO not in store.path.parents


# -- first admin: from configuration, never from code ------------------------------------------


def test_without_configured_admin_email_setup_is_required(store):
    assert store.setup_state() is SetupState.NEEDS_ADMIN_EMAIL
    with pytest.raises(SetupRequired):
        store.create_first_admin("First Admin", "pass-word-1")


def test_first_admin_from_environment_skips_approval(store, monkeypatch, audit):
    monkeypatch.setenv(auth_config.ADMIN_EMAIL_ENV, "Boss@Example.test")
    assert store.setup_state() is SetupState.NEEDS_ADMIN
    acc = store.create_first_admin("First Admin", "pass-word-1")
    assert acc.email == "boss@example.test" and acc.role is Role.ADMIN
    assert acc.status is AccountStatus.ACTIVE and store.setup_state() is SetupState.READY
    created = next(e for e in audit.entries() if e["kind"] == "account_created")
    assert created["via"] == "first_admin_setup"
    with pytest.raises(AccountError):
        store.create_first_admin("Second", "pass-word-2")


def test_first_admin_from_settings_file(store, isolated_config):
    isolated_config.mkdir(parents=True, exist_ok=True)
    (isolated_config / "settings.json").write_text(json.dumps({"admin_email": "lab@example.test"}))
    assert auth_config.admin_email() == "lab@example.test"
    with pytest.raises(AccountError):
        store.create_first_admin("Imposter", "pass-word-1", email="other@example.test")
    assert store.create_first_admin("Lab Admin", "pass-word-1").email == "lab@example.test"


def test_first_run_setup_may_supply_the_email(store):
    acc = store.create_first_admin("Lab Admin", "pass-word-1", email="lab@example.test")
    assert acc.role is Role.ADMIN


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")


def test_no_real_email_in_auth_code_or_tests():
    """Only example.test addresses may appear; the admin email lives in local settings."""
    files = [*sorted((REPO / "src" / "dino_autofocus" / "auth").rglob("*.py")),
             *sorted((REPO / "tests" / "auth").rglob("*.py")),
             *sorted((REPO / "tests" / "auth" / "fixtures").rglob("*.json"))]
    assert files
    found = {m.group(0) for f in files for m in _EMAIL.finditer(f.read_text(encoding="utf-8"))}
    assert found and all(e.lower().endswith("example.test") for e in found), found


def test_older_cheaper_hash_is_upgraded_at_the_next_login(seeded, seed_password, monkeypatch):
    """A p=1 hash answers faster than an unknown email's dummy check (audit S11): it must not
    stay on file once the password is known."""
    current_p = passwords.SCRYPT_P
    monkeypatch.setattr(passwords, "SCRYPT_P", 1)
    seeded.reset_password("admin@example.test", "vera@example.test", "old-pass-word-1")
    old = seeded.get("vera@example.test").password_hash
    monkeypatch.setattr(passwords, "SCRYPT_P", current_p)
    assert passwords.needs_rehash(old)
    assert not seeded.authenticate("vera@example.test", "wrong-pass-word").ok
    assert seeded.get("vera@example.test").password_hash == old  # a wrong password changes nothing
    assert seeded.authenticate("vera@example.test", "old-pass-word-1").ok
    new = seeded.get("vera@example.test").password_hash
    assert new != old and not passwords.needs_rehash(new)
    reloaded = AccountStore(seeded.path, audit=None)
    assert reloaded.get("vera@example.test").password_hash == new
    assert reloaded.authenticate("vera@example.test", "old-pass-word-1").ok
