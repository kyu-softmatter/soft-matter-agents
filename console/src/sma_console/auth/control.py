"""Device control: one operator at a time may move the hardware (X3, design rule 12).

* ``acquire`` gives the logged-in operator (or admin) a **control token**. While someone holds
  it, everyone else only watches. ``release`` gives it back; an admin may ``revoke`` it. A
  holder's logout or expiry frees it; a locked screen does not (running work goes on).
* The engine checks a command's control token with ``check`` (T-011 injects it as its control
  check). It is a separate thing from the engine's ``MotionToken``, which only the guards hold.
* Control is taken on the microscope PC only (``local``); remote viewing is read only.
* ``authorize`` is the one decision the server makes per request, given whether the request is
  local (loopback). **STOP (abort, lights_off) is always allowed**: without control, without a
  login, while the login is locked, and from a remote view.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from .audit import AuditKind, AuditLog
from .logins import LoginInfo, LoginSessions
from .roles import LOCAL_ONLY, Action, allows


class ControlError(PermissionError):
    """Control cannot be taken, given back or used (the message says why)."""


class ControlBusy(ControlError):
    def __init__(self, holder: str) -> None:
        super().__init__(f"device control is held by {holder}")
        self.holder = holder


@dataclass(frozen=True)
class ControlGrant:
    token: str
    user_id: str
    login_id: str
    acquired_at: float


@dataclass(frozen=True)
class ControlHolder:
    """Who holds control, for the status bar (no token in it)."""

    user_id: str
    login_id: str
    acquired_at: float


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    user_id: str | None = None


class DeviceControl:
    def __init__(
        self,
        logins: LoginSessions,
        *,
        audit: AuditLog | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._logins = logins
        self._audit = audit
        self._clock = clock
        self._lock = threading.RLock()
        self._grant: ControlGrant | None = None
        logins.on_end(self._login_ended)

    def _log(self, kind: AuditKind, user_id: str | None, **fields) -> None:
        if self._audit is not None:
            self._audit.append(kind, user_id, **fields)

    def _active_login(self, login_token: str) -> LoginInfo:
        info = self._logins.get(login_token)
        if info is None:
            raise ControlError("not logged in")
        if info.locked:
            raise ControlError("the screen is locked; unlock it first")
        return info

    def _current(self) -> ControlGrant | None:
        """The grant, dropped if its login session has ended."""
        g = self._grant
        if g is not None and not self._logins.is_live(g.login_id):
            # is_live has ended the session, and _login_ended has already dropped and logged
            # the grant; this is only a safety net
            self._grant = None
            return None
        return g

    def _login_ended(self, login_id: str) -> None:
        with self._lock:
            g = self._grant
            if g is not None and g.login_id == login_id:
                self._grant = None
                self._log(AuditKind.CONTROL_RELEASED, g.user_id, login_id=login_id,
                          reason="login_ended")

    # -- taking and giving back ---------------------------------------------------------------

    def acquire(self, login_token: str, *, local: bool = False) -> ControlGrant:
        """Take control. Only from the microscope PC (``local``), as operator or admin."""
        info = self._active_login(login_token)
        if not local:
            raise ControlError("device control is taken on the microscope PC only")
        if not allows(info.role, Action.OPERATE, local=True):
            raise ControlError(f"role {info.role} cannot operate the hardware")
        with self._lock:
            g = self._current()
            if g is not None:
                if g.login_id == info.login_id:
                    return g
                raise ControlBusy(g.user_id)
            g = ControlGrant(token=secrets.token_urlsafe(32), user_id=info.user_id,
                             login_id=info.login_id, acquired_at=self._clock())
            self._grant = g
        self._log(AuditKind.CONTROL_ACQUIRED, info.user_id, login_id=info.login_id)
        return g

    def release(self, login_token: str) -> None:
        info = self._logins.get(login_token)
        if info is None:
            raise ControlError("not logged in")
        with self._lock:
            g = self._current()
            if g is None or g.login_id != info.login_id:
                raise ControlError("you do not hold device control")
            self._grant = None
        self._log(AuditKind.CONTROL_RELEASED, info.user_id, login_id=info.login_id,
                  reason="released")

    def revoke(self, admin_login_token: str, reason: str) -> ControlHolder | None:
        """Admin takes control away from its holder. Returns who held it, or None."""
        info = self._active_login(admin_login_token)
        if not allows(info.role, Action.MANAGE_USERS):
            raise ControlError("only an admin may revoke device control")
        with self._lock:
            g = self._current()
            self._grant = None
        if g is None:
            return None
        self._log(AuditKind.CONTROL_REVOKED, info.user_id, holder=g.user_id,
                  holder_login_id=g.login_id, reason=reason)
        return ControlHolder(g.user_id, g.login_id, g.acquired_at)

    # -- reading ------------------------------------------------------------------------------

    def holder(self) -> ControlHolder | None:
        with self._lock:
            g = self._current()
        return None if g is None else ControlHolder(g.user_id, g.login_id, g.acquired_at)

    def check(self, control_token: str | None) -> ControlGrant:
        """The engine's check: the token is the live grant. Raises ``ControlError`` if not."""
        with self._lock:
            g = self._current()
        if (g is None or not isinstance(control_token, str)
                or not secrets.compare_digest(g.token, control_token)):
            raise ControlError("no valid device control token")
        return g

    def authorize(
        self,
        action: Action | str,
        login_token: str | None,
        control_token: str | None = None,
        *,
        local: bool = False,
    ) -> Decision:
        """May this request do ``action``? STOP is always yes.

        ``local`` is the server's loopback check of the request; local-only actions (hardware
        commands, questions, map flags) are refused without it (``roles.LOCAL_ONLY``).
        """
        action = Action(action)
        info = self._logins.get(login_token) if login_token else None
        user_id = info.user_id if info is not None else None
        if action is Action.STOP:
            return Decision(True, "stop is always accepted", user_id)
        if info is None:
            return Decision(False, "not logged in")
        if info.locked:
            return Decision(False, "the screen is locked", user_id)
        if action in LOCAL_ONLY and not local:
            return Decision(False, f"{action} is allowed on the microscope PC only", user_id)
        if not allows(info.role, action, local=local):
            return Decision(False, f"role {info.role} may not {action}", user_id)
        if action is Action.OPERATE:
            try:
                g = self.check(control_token)
            except ControlError as e:
                return Decision(False, str(e), user_id)
            if g.login_id != info.login_id:
                return Decision(False, "device control belongs to another login", user_id)
        return Decision(True, "ok", user_id)
