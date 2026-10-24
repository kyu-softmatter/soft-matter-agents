"""Local accounts: register, approve, authenticate (X3, D9, D12).

* The account id is a **plain login id, never an email** (console card 009): letters, digits,
  dot, underscore and hyphen, at most 64, starting with a letter or digit -- the pattern of
  ``signed_through.login`` in ``plan_approval.schema.json`` (``LOGIN_PATTERN``). A console-signed
  approval carries the login, a committed approval is published, and an email in it would publish
  an address. The runtime compares the login byte for byte, so it is stored exactly as typed; two
  logins that differ only by case are not both allowed, so one cannot pass for the other.
* Registration takes only a name, a login and a password. A new account is ``pending`` with role
  ``viewer``; an admin approves it and sets the role at the same time. The user never picks their
  own role. A pending account cannot log in; ``authenticate`` says it is pending (only after the
  right password, so the answer does not reveal which logins exist).
* The **first admin** is created by ``create_first_admin`` and skips approval. Its login is
  ``admin_login`` in the settings file, ``softmatter`` when the key is absent
  (``config.admin_login``); the person types its password at the first start. No password ships.
* The file (``accounts.json`` in the settings folder outside the repository) holds password
  hashes only. Writes go to a temporary file and are swapped in, so a crash never leaves
  half a file.
* An account recorded by an older console is keyed by an email. It is **not guessed into an id**:
  it loads as "needs a login id" (``needs_login``), cannot log in, and is written back to the
  file exactly as it was. The administrator gives it a plain login (``give_login``), which writes
  an audit line naming both.
* Accounts are **switched off, never deleted**: the audit log refers to them.

Creation, approval (with the approving admin and the role), role changes, disable, enable,
password reset and giving a login go to the audit log when one is given.
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field, replace
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

FILE_VERSION = 2
#: older files, keyed by email, are still read (as accounts that need a login id)
READABLE_VERSIONS = (1, 2)
MAX_NAME_LENGTH = 100

#: ``signed_through.login`` in contracts/schemas/plan_approval.schema.json, character for character
LOGIN_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
_LOGIN = re.compile(LOGIN_PATTERN)


class AccountError(ValueError):
    """A registration or admin request that cannot be done (the message says why)."""


class DuplicateAccountError(AccountError):
    pass


class PermissionDenied(AccountError):
    pass


class SetupRequired(AccountError):
    """The settings name no usable administrator login: fix ``admin_login`` there."""


def check_login(login: object) -> str:
    """The login itself if it is a plain id; otherwise ``AccountError`` saying why. Nothing is
    trimmed, lower-cased or otherwise changed: the runtime compares the login byte for byte."""
    if not isinstance(login, str) or _LOGIN.fullmatch(login) is None:
        raise AccountError(
            "a login is a plain id: letters, digits, dot, underscore or hyphen, starting with a "
            "letter or digit, at most 64 characters. It is not an email address."
        )
    return login


@dataclass(frozen=True)
class Account:
    login: str
    name: str
    role: Role
    status: AccountStatus
    password_hash: str
    created_at: str
    approved_by: str | None = None
    approved_at: str | None = None
    #: set when an administrator gave an email-keyed account its login (kept so nothing is lost)
    former_email: str | None = None

    def public(self) -> dict[str, Any]:
        """Everything but the password hash and the old email (for the user list and the API)."""
        d = asdict(self)
        del d["password_hash"]
        del d["former_email"]
        d["role"] = str(self.role)
        d["status"] = str(self.status)
        return d


@dataclass(frozen=True)
class NeedsLogin:
    """An account recorded under an email by an older console. It has no login id yet."""

    email: str
    name: str
    role: Role
    status: AccountStatus
    created_at: str
    approved_by: str | None
    approved_at: str | None
    #: the record exactly as the file held it, written back unchanged
    raw: dict[str, Any] = field(repr=False, compare=False)

    def public(self) -> dict[str, Any]:
        return {"email": self.email, "name": self.name, "role": str(self.role),
                "status": str(self.status), "created_at": self.created_at,
                "approved_by": self.approved_by, "approved_at": self.approved_at}


class LoginOutcome(StrEnum):
    OK = "ok"
    BAD_CREDENTIALS = "bad_credentials"
    PENDING = "pending_approval"
    DISABLED = "disabled"
    #: refused before the password was checked: too many wrong ones (auth/throttle.py)
    TOO_MANY = "too_many_attempts"
    #: what was typed is not a plain login id (an email, say); the password is not checked
    NOT_A_LOGIN = "not_a_login"


@dataclass(frozen=True)
class LoginCheck:
    outcome: LoginOutcome
    account: Account | None = None

    @property
    def ok(self) -> bool:
        return self.outcome is LoginOutcome.OK


class SetupState(StrEnum):
    #: no admin account yet: the first-start step makes it, with a password typed there
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


def _email_key(email: object) -> str:
    return email.strip().casefold() if isinstance(email, str) else ""


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
        self._accounts: dict[str, Account] = {}
        self._needs_login: list[NeedsLogin] = []
        self._load()

    # -- file ---------------------------------------------------------------------------------

    def _load(self) -> None:
        if not self.path.is_file():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("version") not in READABLE_VERSIONS:
            raise AccountError(f"{self.path}: unknown file version {data.get('version')!r}")
        for raw in data["accounts"]:
            try:
                if "login" in raw:
                    acc = Account(**{**raw, "role": Role(raw["role"]),
                                     "status": AccountStatus(raw["status"])})
                    self._accounts[acc.login] = acc
                elif "email" in raw:
                    self._needs_login.append(NeedsLogin(
                        email=raw["email"], name=raw["name"], role=Role(raw["role"]),
                        status=AccountStatus(raw["status"]), created_at=raw["created_at"],
                        approved_by=raw.get("approved_by"), approved_at=raw.get("approved_at"),
                        raw=dict(raw)))
                else:
                    raise KeyError("login")
            except (KeyError, TypeError, ValueError) as e:
                raise AccountError(f"{self.path}: an account record cannot be read ({e!r})") from e

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, Any]] = [
            {**asdict(a), "role": str(a.role), "status": str(a.status)}
            for a in self._accounts.values()]
        rows.extend(n.raw for n in self._needs_login)  # as they were: never guessed, never lost
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps({"version": FILE_VERSION, "accounts": rows}, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self.path)

    def _log(self, kind: AuditKind, user_id: str | None, **fields: Any) -> None:
        if self._audit is not None:
            self._audit.append(kind, user_id, **fields)

    # -- reading ------------------------------------------------------------------------------

    def get(self, login: str) -> Account | None:
        """The account with exactly this login, or None."""
        return self._accounts.get(login) if isinstance(login, str) else None

    def accounts(self) -> list[Account]:
        return sorted(self._accounts.values(), key=lambda a: a.created_at)

    def needs_login(self) -> list[NeedsLogin]:
        """Accounts recorded under an email, waiting for an administrator to give them a login."""
        return list(self._needs_login)

    def pending(self) -> list[Account]:
        return [a for a in self.accounts() if a.status is AccountStatus.PENDING]

    def has_admin(self) -> bool:
        return any(a.role is Role.ADMIN and a.status is AccountStatus.ACTIVE
                   for a in self._accounts.values())

    def setup_state(self) -> SetupState:
        return SetupState.READY if self.has_admin() else SetupState.NEEDS_ADMIN

    def admin_login(self) -> str:
        """The login the first administrator will have, or ``SetupRequired`` when the settings
        name something that is not a plain id."""
        configured = config.admin_login(self._config_dir)
        try:
            return check_login(configured)
        except AccountError as e:
            raise SetupRequired(
                f"'admin_login' in {self._config_dir / config.SETTINGS_FILE} is not usable: {e}"
            ) from e

    # -- creating -----------------------------------------------------------------------------

    def _taken(self, login: str) -> bool:
        low = login.casefold()
        return any(k.casefold() == low for k in self._accounts)

    def _add(self, name: str, login: str, password: str, role: Role, status: AccountStatus,
             approved_by: str | None, via: str) -> Account:
        name = _clean_name(name)
        key = check_login(login)
        password_hash = hash_password(password)  # policy check before anything is stored
        with self._lock:
            if self._taken(key):
                raise DuplicateAccountError(f"an account already exists for {key}")
            now = self._clock().isoformat()
            acc = Account(login=key, name=name, role=role, status=status,
                          password_hash=password_hash, created_at=now,
                          approved_by=approved_by,
                          approved_at=now if approved_by is not None else None)
            self._accounts[key] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_CREATED, key, created_at=acc.created_at, name=acc.name,
                  role=str(acc.role), status=str(acc.status), via=via)
        return acc

    def register(self, name: str, login: str, password: str) -> Account:
        """Self-registration: name, login, password only. Starts pending, role viewer."""
        key = check_login(login)
        if key.casefold() == str(config.admin_login(self._config_dir)).casefold():
            raise AccountError("that login is reserved for the administrator")
        return self._add(name, key, password, DEFAULT_ROLE, AccountStatus.PENDING,
                         approved_by=None, via="register")

    def create_first_admin(self, name: str | None, password: str) -> Account:
        """Make the first admin, without approval, under ``admin_login`` from the settings
        (``softmatter`` by default) and the password given here. A blank name becomes the login."""
        if self.has_admin():
            raise AccountError("an admin account already exists")
        login = self.admin_login()
        shown = name if isinstance(name, str) and name.strip() else login
        return self._add(shown, login, password, Role.ADMIN, AccountStatus.ACTIVE,
                         approved_by=None, via="first_admin_setup")

    # -- admin actions ------------------------------------------------------------------------

    def _require_admin(self, admin_login: str) -> Account:
        admin = self.get(admin_login)
        if (admin is None or admin.status is not AccountStatus.ACTIVE
                or not allows(admin.role, Action.MANAGE_USERS)):
            raise PermissionDenied("only an active admin may manage users")
        return admin

    def _target(self, login: str) -> Account:
        acc = self.get(login)
        if acc is None:
            raise AccountError(f"no account for {login!r}")
        return acc

    def approve(self, admin_login: str, login: str, role: Role | str) -> Account:
        """Approve a pending account and set its role (the admin decides it, D12)."""
        role = Role(role)
        with self._lock:
            admin = self._require_admin(admin_login)
            acc = self._target(login)
            if acc.status is not AccountStatus.PENDING:
                raise AccountError(f"{acc.login} is not waiting for approval ({acc.status})")
            acc = replace(acc, role=role, status=AccountStatus.ACTIVE, approved_by=admin.login,
                          approved_at=self._clock().isoformat())
            self._accounts[acc.login] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_APPROVED, admin.login, account=acc.login, role=str(role),
                  approved_by=admin.login, approved_at=acc.approved_at,
                  created_at=acc.created_at)
        return acc

    def _would_leave_no_admin(self, acc: Account) -> bool:
        others = [a for a in self._accounts.values() if a.login != acc.login
                  and a.role is Role.ADMIN and a.status is AccountStatus.ACTIVE]
        return acc.role is Role.ADMIN and not others

    def set_role(self, admin_login: str, login: str, role: Role | str) -> Account:
        role = Role(role)
        with self._lock:
            admin = self._require_admin(admin_login)
            acc = self._target(login)
            if acc.status is not AccountStatus.ACTIVE:
                raise AccountError(f"{acc.login} is {acc.status}; approve it to set a role")
            if role is not Role.ADMIN and self._would_leave_no_admin(acc):
                raise AccountError("this is the last admin; make another admin first")
            old = acc.role
            acc = replace(acc, role=role)
            self._accounts[acc.login] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_ROLE_CHANGED, admin.login, account=acc.login,
                  old_role=str(old), role=str(role))
        return acc

    def disable(self, admin_login: str, login: str) -> Account:
        """Switch an account off. It stays in the file because the audit log names it."""
        with self._lock:
            admin = self._require_admin(admin_login)
            acc = self._target(login)
            if self._would_leave_no_admin(acc):
                raise AccountError("this is the last admin; make another admin first")
            acc = replace(acc, status=AccountStatus.DISABLED)
            self._accounts[acc.login] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_DISABLED, admin.login, account=acc.login)
        return acc

    def enable(self, admin_login: str, login: str) -> Account:
        """Switch a disabled account back on with the role it had."""
        with self._lock:
            admin = self._require_admin(admin_login)
            acc = self._target(login)
            if acc.status is not AccountStatus.DISABLED:
                raise AccountError(f"{acc.login} is not disabled ({acc.status})")
            acc = replace(acc, status=AccountStatus.ACTIVE)
            self._accounts[acc.login] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_ENABLED, admin.login, account=acc.login, role=str(acc.role))
        return acc

    def reset_password(self, admin_login: str, login: str, password: str) -> Account:
        """The admin sets a new password (policy-checked). The caller ends the old logins."""
        password_hash = hash_password(password)  # policy check before anything is stored
        with self._lock:
            admin = self._require_admin(admin_login)
            acc = self._target(login)
            acc = replace(acc, password_hash=password_hash)
            self._accounts[acc.login] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_PASSWORD_RESET, admin.login, account=acc.login)
        return acc

    def give_login(self, admin_login: str, email: str, login: str) -> Account:
        """Give an email-keyed account from an older console a plain login id.

        The account keeps its name, role, status, password and history; the email moves into
        ``former_email`` and the audit line names both, so nothing is lost."""
        with self._lock:
            admin = self._require_admin(admin_login)
            old = next((n for n in self._needs_login if _email_key(n.email) == _email_key(email)),
                       None)
            if old is None:
                raise AccountError(f"no account for {email!r}")
            key = check_login(login)
            if self._taken(key):
                raise DuplicateAccountError(f"an account already exists for {key}")
            acc = Account(login=key, name=old.name, role=old.role, status=old.status,
                          password_hash=old.raw["password_hash"], created_at=old.created_at,
                          approved_by=old.approved_by, approved_at=old.approved_at,
                          former_email=old.email)
            self._needs_login = [n for n in self._needs_login if n is not old]
            self._accounts[key] = acc
            self._save()
        self._log(AuditKind.ACCOUNT_LOGIN_GIVEN, admin.login, account=acc.login,
                  former_email=old.email, role=str(acc.role), status=str(acc.status))
        return acc

    # -- login --------------------------------------------------------------------------------

    def _rehash(self, acc: Account, password: str) -> Account:
        try:
            password_hash = hash_password(password)
        except PasswordPolicyError:
            return acc  # an older, weaker policy: keep the old hash rather than refuse the login
        with self._lock:
            current = self._accounts.get(acc.login)
            if current is None or current.password_hash != acc.password_hash:
                return current or acc  # changed or removed meanwhile: leave it
            acc = replace(current, password_hash=password_hash)
            self._accounts[acc.login] = acc
            self._save()
        return acc

    def authenticate(self, login: str, password: str) -> LoginCheck:
        """Check a login. Pending and disabled are reported only after the right password."""
        try:
            check_login(login)
        except AccountError:
            return LoginCheck(LoginOutcome.NOT_A_LOGIN)  # not an id: nothing to check a password on
        acc = self.get(login)
        if acc is None:
            dummy_verify(password)  # same cost as a real check: no hint which logins exist
            return LoginCheck(LoginOutcome.BAD_CREDENTIALS)
        if not verify_password(password, acc.password_hash):
            return LoginCheck(LoginOutcome.BAD_CREDENTIALS)
        if needs_rehash(acc.password_hash):
            # An older, cheaper hash answers faster than an unknown login's dummy check, which
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

        Each entry has ``name``, ``login``, ``role`` and optionally ``status`` (default
        active). All get the same given password; the seed file holds no passwords.
        """
        out = []
        for e in entries:
            status = AccountStatus(e.get("status", AccountStatus.ACTIVE))
            approved_by = "seed" if status is not AccountStatus.PENDING else None
            out.append(self._add(e["name"], e["login"], password, Role(e["role"]), status,
                                 approved_by=approved_by, via="seed"))
        return out
