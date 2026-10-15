"""The audit log ``audit.jsonl``: who did what and when (X4).

One JSON object per line, **append only**. There is no API that edits or deletes a line.
Every line carries ``ts`` (UTC ISO 8601), ``kind``, ``user_id`` (account email, or null) and
``session_id`` (experiment session id, or null; T-019 supplies it through
``session_id_provider``), then the event's own fields.

Secrets never go in: a field whose name contains ``password`` or ``token`` is refused.
Writes are serialised by a lock, so threads may share one ``AuditLog``.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import config


class AuditKind(StrEnum):
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    ACCOUNT_CREATED = "account_created"
    #: a sign-up for an email that already has an account; answered like a new one (S1)
    SIGNUP_EXISTING = "signup_existing"
    ACCOUNT_APPROVED = "account_approved"
    ACCOUNT_ROLE_CHANGED = "account_role_changed"
    ACCOUNT_DISABLED = "account_disabled"
    ACCOUNT_ENABLED = "account_enabled"
    ACCOUNT_PASSWORD_RESET = "account_password_reset"
    ACCOUNT_DELETED = "account_deleted"
    CONTROL_ACQUIRED = "control_acquired"
    CONTROL_RELEASED = "control_released"
    CONTROL_REVOKED = "control_revoked"
    COMMAND_PROPOSED = "command_proposed"
    COMMAND_CONFIRMED = "command_confirmed"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_REJECTED = "command_rejected"
    #: a question put to the assistant (console F1.1 submit or a prompt box; D16)
    QUESTION_SUBMITTED = "question_submitted"
    ASSISTANT_MESSAGE = "assistant_message"


RESERVED = ("ts", "kind", "user_id", "session_id")
_FORBIDDEN = ("password", "token")


class AuditFieldError(ValueError):
    """An audit field would overwrite a reserved key or hold a secret."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuditLog:
    def __init__(
        self,
        path: str | os.PathLike[str] | None = None,
        *,
        session_id_provider: Callable[[], str | None] | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.path = Path(path) if path is not None else config.config_dir() / config.AUDIT_FILE
        self._session_id_provider = session_id_provider
        self._clock = clock
        self._lock = threading.Lock()

    def append(
        self,
        kind: AuditKind | str,
        user_id: str | None,
        *,
        session_id: str | None = None,
        **fields: Any,
    ) -> dict[str, Any]:
        """Write one line and return it. ``session_id`` defaults to the provider's value."""
        for name in fields:
            if name in RESERVED:
                raise AuditFieldError(f"{name!r} is set by the audit log itself")
            if any(word in name.lower() for word in _FORBIDDEN):
                raise AuditFieldError(f"{name!r} looks like a secret; it is not logged")
        if session_id is None and self._session_id_provider is not None:
            session_id = self._session_id_provider()
        entry = {
            "ts": self._clock().isoformat(),
            "kind": str(AuditKind(kind)),
            "user_id": user_id,
            "session_id": session_id,
            **fields,
        }
        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8", newline="\n") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        return entry

    def entries(self) -> Iterator[Mapping[str, Any]]:
        """Read the log back in order (for the log view). Read only."""
        if not self.path.is_file():
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
