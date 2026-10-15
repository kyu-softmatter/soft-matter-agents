"""Login, roles, device control and logs (X3, X4; docs/PLAN.md 5절 "사용자와 로그인").

Imports nothing beyond the standard library, so the engine, the server and tests can use it
without a UI or web framework. The server routes (``server/api/auth.py``) and the login screen
are later tasks.
"""

from .accounts import (
    Account,
    AccountError,
    AccountStore,
    DuplicateAccountError,
    LoginCheck,
    LoginOutcome,
    PermissionDenied,
    SetupRequired,
    SetupState,
    normalize_email,
)
from .audit import AuditFieldError, AuditKind, AuditLog
from .control import ControlBusy, ControlError, ControlGrant, ControlHolder, Decision, DeviceControl
from .logins import LoginInfo, LoginResult, LoginSessions, TooManyAttempts
from .passwords import PasswordPolicyError, hash_password, verify_password
from .roles import LOCAL_ONLY, AccountStatus, Action, Role, allows
from .throttle import AttemptLimiter

__all__ = [
    "AttemptLimiter",
    "TooManyAttempts",
    "Account",
    "AccountError",
    "AccountStatus",
    "AccountStore",
    "Action",
    "AuditFieldError",
    "AuditKind",
    "AuditLog",
    "ControlBusy",
    "ControlError",
    "ControlGrant",
    "ControlHolder",
    "Decision",
    "LOCAL_ONLY",
    "DeviceControl",
    "DuplicateAccountError",
    "LoginCheck",
    "LoginInfo",
    "LoginOutcome",
    "LoginResult",
    "LoginSessions",
    "PasswordPolicyError",
    "PermissionDenied",
    "Role",
    "SetupRequired",
    "SetupState",
    "allows",
    "hash_password",
    "normalize_email",
    "verify_password",
]
