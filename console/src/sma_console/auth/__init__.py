"""Login, roles and logs (X3, X4; docs/PLAN.md §5 "Users and login").

Imports nothing beyond the standard library, so the server and tests can use it without a UI or
web framework. The server routes are ``server/api/auth.py``. An account is keyed by a plain login
id, never an email (console card 009). dino's take-and-release control of the device is gone with
the engine it controlled (soft-matter-agents card 077).
"""

from .accounts import (
    LOGIN_PATTERN,
    Account,
    AccountError,
    AccountStore,
    DuplicateAccountError,
    LoginCheck,
    LoginOutcome,
    NeedsLogin,
    PermissionDenied,
    SetupRequired,
    SetupState,
    check_login,
)
from .audit import AuditFieldError, AuditKind, AuditLog
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
    "LOCAL_ONLY",
    "LOGIN_PATTERN",
    "DuplicateAccountError",
    "LoginCheck",
    "LoginInfo",
    "LoginOutcome",
    "LoginResult",
    "LoginSessions",
    "NeedsLogin",
    "PasswordPolicyError",
    "PermissionDenied",
    "Role",
    "SetupRequired",
    "SetupState",
    "allows",
    "check_login",
    "hash_password",
    "verify_password",
]
