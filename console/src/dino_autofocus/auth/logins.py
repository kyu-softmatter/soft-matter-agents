"""Login sessions: token issue, idle lock, expiry, logout (X3).

A *login session* is one person logged in from one browser. It is not the experiment session
(T-019); the audit log's ``session_id`` is the experiment session.

* ``login`` checks the account and issues a random token. Only a hash of the token is kept.
  The cookie that carries it (HttpOnly, SameSite=Strict) is the server task's job.
* After ``idle_lock_s`` without ``touch`` the session **locks**: the person must give their
  password again (``unlock``). A lock stops nothing that is running; guards keep working and
  anyone may still stop the hardware (``control.authorize``).
* After ``max_age_s`` from login the session ends whatever the activity.
* The role is looked up from the account store on every read, so an admin's change applies at
  once, and a disabled account's sessions end.
* Wrong passwords on login and unlock are counted per account and per client
  (``throttle.AttemptLimiter``); past the limit both are refused before the password is checked.
* The password check (scrypt, about 1 s) never runs while this object's lock is held, so one
  slow check does not stall every other request.
"""

from __future__ import annotations

import hashlib
import math
import secrets
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from .accounts import AccountError, AccountStore, LoginOutcome, normalize_email
from .audit import AuditKind, AuditLog
from .roles import AccountStatus, Role
from .throttle import AttemptLimiter

IDLE_LOCK_S = 15 * 60
MAX_AGE_S = 12 * 3600


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LoginInfo:
    """What the rest of the app may know about a login session (no token in it)."""

    login_id: str  # not secret; names the session in control grants and logs
    user_id: str
    name: str
    role: Role
    locked: bool
    issued_at: float
    expires_at: float


def _minutes(seconds: int) -> str:
    m = max(1, math.ceil(seconds / 60))
    return f"{m} minute{'s' if m != 1 else ''}"


class TooManyAttempts(Exception):
    """Unlock refused before the password was checked (too many wrong ones)."""

    def __init__(self, retry_after_s: int):
        super().__init__(f"Too many wrong passwords. Try again in {_minutes(retry_after_s)}.")
        self.retry_after_s = retry_after_s


@dataclass(frozen=True)
class LoginResult:
    outcome: LoginOutcome
    token: str | None = None
    info: LoginInfo | None = None
    retry_after_s: int | None = None  # TOO_MANY only

    @property
    def ok(self) -> bool:
        return self.outcome is LoginOutcome.OK

    @property
    def message(self) -> str:
        return {
            LoginOutcome.OK: "Logged in.",
            LoginOutcome.BAD_CREDENTIALS: "Wrong email or password.",
            LoginOutcome.PENDING: "Your account is waiting for an administrator's approval.",
            LoginOutcome.DISABLED: "This account is disabled. Ask an administrator.",
            LoginOutcome.TOO_MANY: "Too many wrong passwords. Try again in "
                                   f"{_minutes(self.retry_after_s or 0)}.",
        }[self.outcome]


@dataclass
class _Session:
    login_id: str
    user_id: str
    issued_at: float
    last_activity: float
    locked: bool = False


class LoginSessions:
    def __init__(
        self,
        accounts: AccountStore,
        *,
        audit: AuditLog | None = None,
        idle_lock_s: float = IDLE_LOCK_S,
        max_age_s: float = MAX_AGE_S,
        clock: Callable[[], float] = time.time,
        limiter: AttemptLimiter | None = None,
    ) -> None:
        self._accounts = accounts
        self.limiter = limiter if limiter is not None else AttemptLimiter(clock=clock)
        self._audit = audit
        self.idle_lock_s = idle_lock_s
        self.max_age_s = max_age_s
        self._clock = clock
        self._lock = threading.RLock()
        self._sessions: dict[str, _Session] = {}  # key: sha256 of the token
        self._on_end: list[Callable[[str], None]] = []
        self._ended: list[str] = []  # login ids to announce once the lock is released

    def on_end(self, callback: Callable[[str], None]) -> None:
        """Call ``callback(login_id)`` when a session ends (logout, expiry, account off)."""
        self._on_end.append(callback)

    @contextmanager
    def _guard(self) -> Iterator[None]:
        # callbacks run after the lock is released, so one that takes its own lock (device
        # control) cannot deadlock with a thread that holds that lock and calls in here
        with self._lock:
            yield
            ended, self._ended = self._ended, []
        for login_id in ended:
            for callback in self._on_end:
                callback(login_id)

    def _log(self, kind: AuditKind, user_id: str | None, **fields) -> None:
        if self._audit is not None:
            self._audit.append(kind, user_id, **fields)

    # -- login / logout -----------------------------------------------------------------------

    def login(self, email: str, password: str, client: str | None = None) -> LoginResult:
        """``client``: the caller's address, for the per-client attempt limit."""
        try:
            user_id = normalize_email(email)
        except AccountError:
            user_id = None
        keys = self.limiter.keys(user_id or email, client)
        if (wait := self.limiter.retry_after(keys)) is not None:
            self._log(AuditKind.LOGIN_FAILED, user_id, reason=str(LoginOutcome.TOO_MANY),
                      client=client)
            return LoginResult(LoginOutcome.TOO_MANY, retry_after_s=wait)
        check = self._accounts.authenticate(email, password)
        if not check.ok:
            if check.outcome is LoginOutcome.BAD_CREDENTIALS:  # a right password is no guess
                for kind, _ in self.limiter.failed(keys):
                    self._log(AuditKind.LOGIN_FAILED, user_id, reason="lockout_started",
                              key=kind, client=client)
            self._log(AuditKind.LOGIN_FAILED, user_id, reason=str(check.outcome))
            return LoginResult(check.outcome)
        self.limiter.succeeded(user_id)
        now = self._clock()
        token = secrets.token_urlsafe(32)
        s = _Session(login_id=secrets.token_hex(8), user_id=check.account.email,
                     issued_at=now, last_activity=now)
        with self._guard():
            self._sessions[_hash(token)] = s
        self._log(AuditKind.LOGIN, s.user_id, login_id=s.login_id)
        return LoginResult(LoginOutcome.OK, token, self._info(s))

    def logout(self, token: str) -> bool:
        with self._guard():
            s = self._sessions.get(_hash(token))
            if s is None:
                return False
            self._end(_hash(token), s, "logout")
        return True

    def end_user(self, user_id: str, reason: str) -> int:
        """End every login of ``user_id`` (an admin reset its password). Returns how many."""
        with self._guard():
            mine = [(k, s) for k, s in self._sessions.items() if s.user_id == user_id]
            for key, s in mine:
                self._end(key, s, reason)
        return len(mine)

    def _end(self, key: str, s: _Session, reason: str) -> None:
        del self._sessions[key]
        self._log(AuditKind.LOGOUT, s.user_id, login_id=s.login_id, reason=reason)
        self._ended.append(s.login_id)

    # -- reading ------------------------------------------------------------------------------

    def _live(self, token: str) -> _Session | None:
        """The session for ``token`` after expiry and idle lock are applied, or None."""
        key = _hash(token)
        s = self._sessions.get(key)
        if s is None:
            return None
        now = self._clock()
        acc = self._accounts.get(s.user_id)
        if acc is None or acc.status is not AccountStatus.ACTIVE:
            self._end(key, s, "account_inactive")
            return None
        if now - s.issued_at >= self.max_age_s:
            self._end(key, s, "expired")
            return None
        if not s.locked and now - s.last_activity >= self.idle_lock_s:
            s.locked = True
            self._log(AuditKind.LOCKED, s.user_id, login_id=s.login_id, reason="idle")
        return s

    def _info(self, s: _Session) -> LoginInfo:
        acc = self._accounts.get(s.user_id)
        return LoginInfo(login_id=s.login_id, user_id=s.user_id, name=acc.name, role=acc.role,
                         locked=s.locked, issued_at=s.issued_at,
                         expires_at=s.issued_at + self.max_age_s)

    def get(self, token: str) -> LoginInfo | None:
        with self._guard():
            s = self._live(token)
            return None if s is None else self._info(s)

    def is_live(self, login_id: str) -> bool:
        """True while the session named ``login_id`` exists (locked counts as live)."""
        with self._guard():
            for key, s in list(self._sessions.items()):
                if s.login_id == login_id:
                    acc = self._accounts.get(s.user_id)
                    if (acc is None or acc.status is not AccountStatus.ACTIVE
                            or self._clock() - s.issued_at >= self.max_age_s):
                        self._end(key, s, "expired")
                        return False
                    return True
        return False

    # -- activity and lock --------------------------------------------------------------------

    def touch(self, token: str) -> LoginInfo | None:
        """Record user input. A locked session stays locked (unlock needs the password)."""
        with self._guard():
            s = self._live(token)
            if s is None:
                return None
            if not s.locked:
                s.last_activity = self._clock()
            return self._info(s)

    def lock(self, token: str) -> LoginInfo | None:
        with self._guard():
            s = self._live(token)
            if s is None:
                return None
            if not s.locked:
                s.locked = True
                self._log(AuditKind.LOCKED, s.user_id, login_id=s.login_id, reason="manual")
            return self._info(s)

    def unlock(self, token: str, password: str, client: str | None = None) -> LoginInfo | None:
        """Unlock with the account's password; None if the session is gone or it is wrong.
        Raises ``TooManyAttempts`` past the attempt limit (the password is not checked). The
        check runs outside the lock; the session is looked up again before it unlocks."""
        with self._guard():
            s = self._live(token)
            if s is None:
                return None
            if not s.locked:
                return self._info(s)
            user_id, login_id = s.user_id, s.login_id
        keys = self.limiter.keys(user_id, client)
        if (wait := self.limiter.retry_after(keys)) is not None:
            self._log(AuditKind.LOGIN_FAILED, user_id, login_id=login_id,
                      reason=str(LoginOutcome.TOO_MANY), client=client)
            raise TooManyAttempts(wait)
        ok = self._accounts.authenticate(user_id, password).ok  # scrypt, without the lock
        if not ok:
            for kind, _ in self.limiter.failed(keys):
                self._log(AuditKind.LOGIN_FAILED, user_id, login_id=login_id,
                          reason="lockout_started", key=kind, client=client)
            self._log(AuditKind.LOGIN_FAILED, user_id, login_id=login_id,
                      reason="unlock_bad_password")
            return None
        self.limiter.succeeded(user_id)
        with self._guard():
            s = self._live(token)
            if s is None or s.login_id != login_id:
                return None  # ended (logout, expiry, account off) during the check
            if s.locked:
                s.locked = False
                s.last_activity = self._clock()
                self._log(AuditKind.UNLOCKED, s.user_id, login_id=s.login_id)
            return self._info(s)
