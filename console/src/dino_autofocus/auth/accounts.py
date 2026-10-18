"""Local accounts: register, approve, authenticate (X3, D9, D12).

* The account id is the **email the account was created with**, compared without case
  (``normalize_email``). One account per email.
* Registration takes only a name, an email and a password. A new account is ``pending`` with
  role ``viewer``; an admin approves it and sets the role at the same time. The user never
  picks their own role. A pending account cannot log in; ``authenticate`` says it is pending
  (only after the right password, so the answer does not reveal which emails exist).
* The **first admin** comes from the configured admin email (``config.admin_email``) through
  ``create_first_admin`` and skips approval. The email itself is never in code or git.
* The file (``accounts.json`` in the settings folder outside the repository) holds password
  hashes only. Writes go to a temporary file and are swapped in, so a crash never leaves
  half a file.

Creation, approval (with the approving admin and the role), role changes, disable, enable,
password reset and delete go to the audit log when one is given.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import config
from .audit import AuditKind, AuditLog
from .passwords import (
    PasswordPolicyError,
    dummy_verify,
    hash_password,
    needs_rehash,
    verify_password,
)
from .roles import DEFAULT_ROLE, AccountStatus, Action, Role, allows

FILE_VERSION = 1
MAX_NAME_LENGTH = 100


class AccountError(ValueError):
    """A registration or admin request that cannot be done (the message says why)."""


class DuplicateAccountError(AccountError):
    pass


class PermissionDenied(AccountError):
    pass


class SetupRequired(AccountError):
    """No admin email is configured yet: the first-run setup step must supply it."""


def normalize_email(email: str) -> str:
    """Trim and lower-case; reject what is plainly not an address. The result is the id."""
    if not isinstance(email, str):
        raise AccountError("email must be a string")
    value = email.strip().lower()
    local, at, domain = value.partition("@")
    if not at or not local or "." not in domain or "@" in domain or any(c.isspace() for c in value):
        raise AccountError(f"not an email address: {email!r}")
    return value


@dataclass(frozen=True)
class Account:
    email: str
    name: str
    role: Role
    status: AccountStatus
    password_hash: str
    created_at: str
    approved_by: str | None = None
    approved_at: str | None = None

    def public(self) -> dict[str, Any]:
        """Everything but the password hash (for the user list and the API)."""
        d = asdict(self)
        del d["password_hash"]
        d["role"] = str(self.role)
        d["status"] = str(self.status)
        return d


class LoginOutcome(StrEnum):
    OK = "ok"
    BAD_CREDENTIALS = "bad_credentials"
    PENDING = "pending_approval"
    DISABLED = "disabled"
    #: refused before the password was checked: too many wrong ones (auth/throttle.py)
    TOO_MANY = "too_many_attempts"


@dataclass(frozen=True)
class LoginCheck:
    outcome: LoginOutcome
    account: Account | None = None

    @property
    def ok(self) -> bool:
        return self.outcome is LoginOutcome.OK


class SetupState(StrEnum):
    #: no admin account and no configured admin email: ask for it in the first-run step
    NEEDS_ADMIN_EMAIL = "needs_admin_email"
    #: the admin email is configured but its account does not exist yet (needs a password)
    NEEDS_ADMIN = "needs_admin"
    READY = "ready"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _clean_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise AccountError("name is required")
    name = " ".join(name.split())
    if len(name) > MAX_NAME_LENGTH:
        raise AccountError(f"name is longer than {MAX_NAME_LENGTH} characters")
    return name


class AccountStore:
    def __init__(
        self,
        path: str | os.PathLike[str] | None = None,
        *,
        audit: AuditLog | None = None,
        config_dir: str | os.PathLike[str] | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._config_dir = config.config_dir(config_dir)
        self.path = Path(path) if path is not None else self._config_dir / config.ACCOUNTS_FILE
        self._audit = audit
        self._clock = clock
        self._lock = threading.RLock()
        self._accounts: dict[str, Account] = self._load()

    # -- file ---------------------------------------------------------------------------------

    def _load(self) -> dict[str, Account]:
        if not self.path.is_file():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("version") != FILE_VERSION:
            raise AccountError(f"{self.path}: unknown file version {data.get('version')!r}")
        out = {}
        for raw in data["accounts"]:
            acc = Account(**{**raw, "role": Role(raw["role"]),
                             "status": AccountStatus(raw["status"])})
            out[acc.email] = acc
        return out

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{**asdict(a), "role": str(a.role), "status": str(a.status)}
                for a in self._accounts.values()]
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps({"version": FILE_VERSION, "accounts": rows}, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self.path)

    def _log(self, kind: AuditKind, user_id: str | None, **fields: Any) -> None:
        if self._audit is not None:
            self._audit.append(kind, user_id, **fields)

    # -- reading ------------------------------------------------------------------------------

    def get(self, email: str) -> Account | None:
        try:
            key = normalize_email(email)
        except AccountError:
            return None
        return self._accounts.get(key)

    def accounts(self) -> list[Account]:
        return sorted(self._accounts.values(), key=lambda a: a.created_at)

    def pending(self) -> list[Account]:
        return [a for a in self.accounts() if a.status is AccountStatus.PENDING]

    def has_admin(self) -> bool:
        return any(a.role is Role.ADMIN and a.status is AccountStatus.ACTIVE
                   for a in self._accounts.values())

    def setup_state(self) -> SetupState:
        if self.has_admin():
            return SetupState.READY
        if config.admin_email(self._config_dir) is None:
            return SetupState.NEEDS_ADMIN_EMAIL
        return SetupState.NEEDS_ADMIN

    # -- creating -----------------------------------------------------------------------------

    def _add(self, name: str, email: str, password: str, role: Role, status: AccountStatus,
             approved_by: str | None, via: str) -> Account:
        name = _clean_name(name)
        key = normalize_email(email)
        password_hash = hash_password(password)  # policy check before anything is stored
        with self._lock:
            if key in self._accounts:
                raise DuplicateAccountError(f"an account already exists for {key}")
            now = self._clock().isoformat()
            acc = Account(email=key, name=name, role=role, status=status,
                          password_hash=password_hash, created_at=now,
                          approved_by=approved_by,
                          approved_at=now if approved_by is not None else None)
            self._accounts[key] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_CREATED, key, created_at=acc.created_at, name=acc.name,
                  role=str(acc.role), status=str(acc.status), via=via)
        return acc

    def register(self, name: str, email: str, password: str) -> Account:
        """Self-registration: name, email, password only. Starts pending, role viewer."""
        return self._add(name, email, password, DEFAULT_ROLE, AccountStatus.PENDING,
                         approved_by=None, via="register")

    def create_first_admin(self, name: str, password: str, email: str | None = None) -> Account:
        """Make the first admin from the configured admin email, without approval.

        ``email`` is for the first-run setup step when nothing is configured; when an admin
        email is configured, a different ``email`` is refused.
        """
        if self.has_admin():
            raise AccountError("an admin account already exists")
        configured = config.admin_email(self._config_dir)
        if configured is None and email is None:
            raise SetupRequired(
                f"no admin email configured: set {config.ADMIN_EMAIL_ENV} or "
                f"'admin_email' in {self._config_dir / config.SETTINGS_FILE}"
            )
        target = normalize_email(email if email is not None else configured)
        if configured is not None and target != normalize_email(configured):
            raise AccountError("the first admin must use the configured admin email")
        return self._add(name, target, password, Role.ADMIN, AccountStatus.ACTIVE,
                         approved_by=None, via="first_admin_setup")

    # -- admin actions ------------------------------------------------------------------------

    def _require_admin(self, admin_email: str) -> Account:
        admin = self.get(admin_email)
        if (admin is None or admin.status is not AccountStatus.ACTIVE
                or not allows(admin.role, Action.MANAGE_USERS)):
            raise PermissionDenied("only an active admin may manage users")
        return admin

    def _target(self, email: str) -> Account:
        acc = self.get(email)
        if acc is None:
            raise AccountError(f"no account for {email!r}")
        return acc

    def approve(self, admin_email: str, email: str, role: Role | str) -> Account:
        """Approve a pending account and set its role (the admin decides it, D12)."""
        role = Role(role)
        with self._lock:
            admin = self._require_admin(admin_email)
            acc = self._target(email)
            if acc.status is not AccountStatus.PENDING:
                raise AccountError(f"{acc.email} is not waiting for approval ({acc.status})")
            acc = replace(acc, role=role, status=AccountStatus.ACTIVE, approved_by=admin.email,
                          approved_at=self._clock().isoformat())
            self._accounts[acc.email] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_APPROVED, admin.email, account=acc.email, role=str(role),
                  approved_by=admin.email, approved_at=acc.approved_at,
                  created_at=acc.created_at)
        return acc

    def _would_leave_no_admin(self, acc: Account) -> bool:
        others = [a for a in self._accounts.values() if a.email != acc.email
                  and a.role is Role.ADMIN and a.status is AccountStatus.ACTIVE]
        return acc.role is Role.ADMIN and not others

    def set_role(self, admin_email: str, email: str, role: Role | str) -> Account:
        role = Role(role)
        with self._lock:
            admin = self._require_admin(admin_email)
            acc = self._target(email)
            if acc.status is not AccountStatus.ACTIVE:
                raise AccountError(f"{acc.email} is {acc.status}; approve it to set a role")
            if role is not Role.ADMIN and self._would_leave_no_admin(acc):
                raise AccountError("this is the last admin; make another admin first")
            old = acc.role
            acc = replace(acc, role=role)
            self._accounts[acc.email] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_ROLE_CHANGED, admin.email, account=acc.email,
                  old_role=str(old), role=str(role))
        return acc

    def disable(self, admin_email: str, email: str) -> Account:
        """Switch an account off. It stays in the file because the audit log names it."""
        with self._lock:
            admin = self._require_admin(admin_email)
            acc = self._target(email)
            if self._would_leave_no_admin(acc):
                raise AccountError("this is the last admin; make another admin first")
            acc = replace(acc, status=AccountStatus.DISABLED)
            self._accounts[acc.email] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_DISABLED, admin.email, account=acc.email)
        return acc

    def enable(self, admin_email: str, email: str) -> Account:
        """Switch a disabled account back on with the role it had."""
        with self._lock:
            admin = self._require_admin(admin_email)
            acc = self._target(email)
            if acc.status is not AccountStatus.DISABLED:
                raise AccountError(f"{acc.email} is not disabled ({acc.status})")
            acc = replace(acc, status=AccountStatus.ACTIVE)
            self._accounts[acc.email] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_ENABLED, admin.email, account=acc.email, role=str(acc.role))
        return acc

    def reset_password(self, admin_email: str, email: str, password: str) -> Account:
        """The admin sets a new password (policy-checked). The caller ends the old logins."""
        password_hash = hash_password(password)  # policy check before anything is stored
        with self._lock:
            admin = self._require_admin(admin_email)
            acc = self._target(email)
            acc = replace(acc, password_hash=password_hash)
            self._accounts[acc.email] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_PASSWORD_RESET, admin.email, account=acc.email)
        return acc

    def delete(self, admin_email: str, email: str) -> Account:
        """Remove a pending or disabled account from the file. The audit log keeps its history;
        an active account is disabled first, so a delete is always a second, separate step."""
        with self._lock:
            admin = self._require_admin(admin_email)
            acc = self._target(email)
            if acc.email == admin.email:
                raise AccountError("an admin cannot delete their own account")
            if acc.status is AccountStatus.ACTIVE:
                raise AccountError(f"{acc.email} is active; disable it before deleting")
            del self._accounts[acc.email]
            self._save()
        self._log(AuditKind.ACCOUNT_DELETED, admin.email, account=acc.email, name=acc.name,
                  role=str(acc.role), status=str(acc.status), created_at=acc.created_at)
        return acc

    # -- login --------------------------------------------------------------------------------

    def _rehash(self, acc: Account, password: str) -> Account:
        try:
            password_hash = hash_password(password)
        except PasswordPolicyError:
            return acc  # an older, weaker policy: keep the old hash rather than refuse the login
        with self._lock:
            current = self._accounts.get(acc.email)
            if current is None or current.password_hash != acc.password_hash:
                return current or acc  # changed or removed meanwhile: leave it
            acc = replace(current, password_hash=password_hash)
            self._accounts[acc.email] = acc
            self._save()
        return acc

    def authenticate(self, email: str, password: str) -> LoginCheck:
        """Check a login. Pending and disabled are reported only after the right password."""
        acc = self.get(email)
        if acc is None:
            dummy_verify(password)  # same cost as a real check: no hint which emails exist
            return LoginCheck(LoginOutcome.BAD_CREDENTIALS)
        if not verify_password(password, acc.password_hash):
            return LoginCheck(LoginOutcome.BAD_CREDENTIALS)
        if needs_rehash(acc.password_hash):
            # An older, cheaper hash answers faster than an unknown email's dummy check, which
            # would tell that the account exists; upgrade it now that the password is known.
            acc = self._rehash(acc, password)
        if acc.status is AccountStatus.PENDING:
            return LoginCheck(LoginOutcome.PENDING, acc)
        if acc.status is AccountStatus.DISABLED:
            return LoginCheck(LoginOutcome.DISABLED, acc)
        return LoginCheck(LoginOutcome.OK, acc)

    # -- mock users ---------------------------------------------------------------------------

    def seed(self, entries: Iterable[Mapping[str, str]], password: str) -> list[Account]:
        """Add fake users for development and tests (``tests/auth/fixtures/users.json``).

        Each entry has ``name``, ``email``, ``role`` and optionally ``status`` (default
        active). All get the same given password; the seed file holds no passwords.
        """
        out = []
        for e in entries:
            status = AccountStatus(e.get("status", AccountStatus.ACTIVE))
            approved_by = "seed" if status is not AccountStatus.PENDING else None
            out.append(self._add(e["name"], e["email"], password, Role(e["role"]), status,
                                 approved_by=approved_by, via="seed"))
        return out
