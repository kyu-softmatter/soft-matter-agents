"""Accounts: plain login ids (test_auth_plain_logins.py has the id rules), register -> pending ->
approved with an admin-chosen role (D12), the first admin from the settings, the file holds no secret."""

import json
import re
from pathlib import Path

import pytest

from sma_console.auth import (
    AccountError,
    AccountStatus,
    AccountStore,
    DuplicateAccountError,
    LoginOutcome,
    PasswordPolicyError,
    PermissionDenied,
    Role,
    passwords,
)

REPO = Path(__file__).resolve().parents[2]


def test_registration_takes_name_login_password_and_starts_pending_viewer(store):
    acc = store.register("Kim Lee", "kim", "pass-word-1")
    assert acc.status is AccountStatus.PENDING and acc.role is Role.VIEWER
    assert acc.approved_by is None and acc.created_at
    with pytest.raises(TypeError):
        store.register("Kim", "kim2", "pass-word-1", role="admin")  # no role choice


def test_bad_name_or_password_stores_nothing(store):
    with pytest.raises(AccountError):
        store.register("   ", "kim", "pass-word-1")
    with pytest.raises(PasswordPolicyError):
        store.register("Kim", "kim", "short")
    assert store.accounts() == []


def test_pending_account_cannot_log_in_and_is_told_so(seeded, seed_password):
    assert seeded.authenticate("pat", seed_password).outcome is LoginOutcome.PENDING
    # a wrong password says nothing about the account's state
    assert seeded.authenticate("pat", "wrong-pass").outcome is \
        LoginOutcome.BAD_CREDENTIALS
    assert seeded.authenticate("nobody", seed_password).outcome is \
        LoginOutcome.BAD_CREDENTIALS


def test_admin_approves_and_sets_role(seeded, audit, seed_password):
    acc = seeded.approve("ada", "pat", "operator")
    assert acc.status is AccountStatus.ACTIVE and acc.role is Role.OPERATOR
    assert acc.approved_by == "ada" and acc.approved_at
    assert seeded.authenticate("pat", seed_password).ok
    entry = [e for e in audit.entries() if e["kind"] == "account_approved"][-1]
    assert entry["user_id"] == "ada" and entry["account"] == "pat"
    assert entry["approved_by"] == "ada" and entry["role"] == "operator"
    assert entry["created_at"] == acc.created_at
    with pytest.raises(AccountError):
        seeded.approve("ada", "pat", "admin")  # already approved


@pytest.mark.parametrize("who", ["otto", "vera", "pat",
                                 "nobody"])
def test_only_an_active_admin_approves(seeded, who):
    with pytest.raises(PermissionDenied):
        seeded.approve(who, "pat", "operator")


def test_creation_is_audited_with_its_time(store, audit):
    acc = store.register("Kim Lee", "kim", "pass-word-1")
    entry = next(e for e in audit.entries() if e["kind"] == "account_created")
    assert entry["user_id"] == "kim" and entry["created_at"] == acc.created_at
    assert entry["status"] == "pending" and entry["role"] == "viewer"


def test_last_admin_cannot_be_demoted_or_disabled(seeded):
    with pytest.raises(AccountError):
        seeded.set_role("ada", "ada", "viewer")
    with pytest.raises(AccountError):
        seeded.disable("ada", "ada")
    seeded.set_role("ada", "otto", "admin")
    assert seeded.set_role("otto", "ada", "viewer").role is Role.VIEWER


def test_disabled_account_cannot_log_in(seeded, seed_password):
    seeded.disable("ada", "vera")
    assert seeded.authenticate("vera", seed_password).outcome is \
        LoginOutcome.DISABLED


def test_disabled_account_is_enabled_with_its_role(seeded, audit, seed_password):
    seeded.disable("ada", "otto")
    acc = seeded.enable("ada", "otto")
    assert acc.status is AccountStatus.ACTIVE and acc.role is Role.OPERATOR
    assert seeded.authenticate("otto", seed_password).ok
    entry = [e for e in audit.entries() if e["kind"] == "account_enabled"][-1]
    assert (entry["user_id"], entry["account"]) == ("ada", "otto")
    with pytest.raises(AccountError):
        seeded.enable("ada", "otto")  # already active
    with pytest.raises(AccountError):
        seeded.enable("ada", "pat")  # pending: approve instead


def test_admin_resets_a_password_and_the_old_one_stops_working(seeded, audit, seed_password):
    seeded.reset_password("ada", "vera", "new-pass-word-1")
    assert not seeded.authenticate("vera", seed_password).ok
    assert seeded.authenticate("vera", "new-pass-word-1").ok
    entry = [e for e in audit.entries() if e["kind"] == "account_password_reset"][-1]
    assert (entry["user_id"], entry["account"]) == ("ada", "vera")
    assert not any("pass-word" in json.dumps(e) for e in audit.entries())
    with pytest.raises(PasswordPolicyError):
        seeded.reset_password("ada", "vera", "x")
    assert seeded.authenticate("vera", "new-pass-word-1").ok


@pytest.mark.parametrize("act", ["enable", "reset_password"])
def test_only_an_active_admin_enables_or_resets(seeded, act):
    seeded.disable("ada", "vera")
    args = ("new-pass-word-1",) if act == "reset_password" else ()
    with pytest.raises(PermissionDenied):
        getattr(seeded, act)("otto", "vera", *args)
    assert seeded.get("vera").status is AccountStatus.DISABLED


def test_file_round_trip_holds_hashes_only(seeded, tmp_path, seed_password):
    raw = (tmp_path / "config" / "accounts.json").read_text(encoding="utf-8")
    assert seed_password not in raw
    reopened = AccountStore(tmp_path / "config" / "accounts.json")
    assert [a.public() for a in reopened.accounts()] == [a.public() for a in seeded.accounts()]
    assert reopened.authenticate("otto", seed_password).ok
    assert "password_hash" not in reopened.get("otto").public()


def test_default_files_live_in_the_settings_folder_not_the_repo(isolated_config):
    store = AccountStore()
    assert store.path == isolated_config / "accounts.json"
    assert REPO not in store.path.parents


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")


def test_no_real_email_in_auth_code_or_tests():
    """Only example.test addresses may appear (the old-account tests need a few); no real address."""
    files = [*sorted((REPO / "src" / "sma_console" / "auth").rglob("*.py")),
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
    seeded.reset_password("ada", "vera", "old-pass-word-1")
    old = seeded.get("vera").password_hash
    monkeypatch.setattr(passwords, "SCRYPT_P", current_p)
    assert passwords.needs_rehash(old)
    assert not seeded.authenticate("vera", "wrong-pass-word").ok
    assert seeded.get("vera").password_hash == old  # a wrong password changes nothing
    assert seeded.authenticate("vera", "old-pass-word-1").ok
    new = seeded.get("vera").password_hash
    assert new != old and not passwords.needs_rehash(new)
    reloaded = AccountStore(seeded.path, audit=None)
    assert reloaded.get("vera").password_hash == new
    assert reloaded.authenticate("vera", "old-pass-word-1").ok
