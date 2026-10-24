"""Login, sign-up and account management over HTTP (T-105; docs/screens/login.md).

Mounted at `/api/auth`. The logic is T-018's (`sma_console.auth`) as the server holds it in
`AuthSeat`; this router only maps requests to it and its answers to HTTP. T-018 writes every
login, logout, lock, unlock, sign-up, approval, role change and control change to
`audit.jsonl`; nothing here logs a second time.

Access (app.py, server/api): `POST login | logout | lock | unlock | activity | signup` work
without a login (remote viewers log in too; sign-up itself is refused here from another PC);
login and unlock are attempt-limited (auth/throttle.py); every other route needs a live login,
and every other write also needs the microscope PC (loopback), an unlocked login and no
foreign Origin.
The admin routes check loopback again here, for reads too. Stops (abort, lights_off) never pass
through this router, so nothing here can block them.

An account is keyed by a plain login id, never an email (console card 009): sign-up, login and
the first-start step refuse anything else, the account routes name an account by its login, and
there is no route that deletes one -- accounts are switched off. An account an older console
recorded under an email is listed as needing a login id, and the administrator gives it one.

The session cookie (`dinoaf_session`) carries the T-018 login token: HttpOnly,
SameSite=Strict, path /, no Max-Age. dino's take-and-release control of the device is gone.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from ...auth import (
    Account,
    AccountError,
    Action,
    AuditKind,
    DuplicateAccountError,
    LoginInfo,
    LoginOutcome,
    NeedsLogin,
    PasswordPolicyError,
    PermissionDenied,
    SetupRequired,
    SetupState,
    TooManyAttempts,
    allows,
)
from . import (
    LOGIN_REQUIRED,
    SESSION_COOKIE,
    Auth,
    IsLocal,
    Login,
    LoginState,
    Refusal,
    logged_in_refusal,
    own_origin_refusal,
    remote_view,
)

router = APIRouter()

RoleName = Literal["admin", "operator", "viewer"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")  # sign-up has no role field, and nothing else


class SetupIn(_In):
    """The administrator's login comes from the settings, not from here. A blank name is the login."""

    password: str
    name: str | None = None


class SignupIn(_In):
    name: str
    login: str
    password: str


class LoginIn(_In):
    login: str
    password: str


class GiveLoginIn(_In):
    email: str  # in the body, never in a path: addresses do not belong in a URL that gets logged
    login: str


class UnlockIn(_In):
    password: str


class RoleIn(_In):
    role: RoleName


class PasswordIn(_In):
    password: str


class SetupOut(BaseModel):
    state: Literal["needs_admin", "ready"]
    #: the login the first administrator will have; only while the first start is still to do, and
    #: null when the settings name one that is not a plain id (the screen then says so)
    admin_login: str | None = None


class Me(BaseModel):
    user_id: str
    name: str
    role: RoleName
    locked: bool
    local: bool
    expires_at: float


class AccountOut(BaseModel):
    login: str
    name: str
    role: RoleName
    status: Literal["pending", "active", "disabled"]
    created_at: str
    approved_by: str | None
    approved_at: str | None


class SignupOut(BaseModel):
    status: Literal["pending"]


class NeedsLoginOut(BaseModel):
    """An account an older console recorded under an email: it cannot log in until it has a login."""

    email: str
    name: str
    role: RoleName
    status: Literal["pending", "active", "disabled"]
    created_at: str
    approved_by: str | None
    approved_at: str | None


# -- helpers ----------------------------------------------------------------------------


def _refuse(status: int, code: str, message: str) -> Refusal:
    return Refusal(status, code, message)


def _me(info: LoginInfo, local: bool) -> Me:
    return Me(user_id=info.user_id, name=info.name, role=str(info.role), locked=info.locked,
              local=local, expires_at=info.expires_at)


def _account(a: Account) -> AccountOut:
    return AccountOut(**a.public())


def _needs_login(n: NeedsLogin) -> NeedsLoginOut:
    return NeedsLoginOut(**n.public())


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict", path="/")


def _logged_in(me: LoginState, *, locked_ok: bool = False) -> LoginInfo:
    if why := logged_in_refusal(me, locked_ok=locked_ok):
        raise why.http()
    return me.info


def _admin_here(me: LoginState) -> LoginInfo:
    """A live, unlocked admin on the microscope PC (reads included)."""
    info = _logged_in(me)
    if not me.local:
        raise remote_view("remote view: accounts are managed on the microscope PC").http()
    if not allows(info.role, Action.MANAGE_USERS):
        raise _refuse(403, "role", f"role {info.role} may not manage accounts").http()
    return info


def _account_error(e: AccountError) -> Refusal:
    if isinstance(e, PermissionDenied):
        return _refuse(403, "role", str(e))
    if isinstance(e, DuplicateAccountError):
        return _refuse(409, "account_exists", str(e))
    if isinstance(e, SetupRequired):
        return _refuse(409, "setup_required", str(e))
    if str(e).startswith("no account for"):
        return _refuse(404, "no_account", str(e))
    if "reserved" in str(e):
        return _refuse(409, "login_reserved", str(e))
    if str(e).startswith("a login is a plain id") or "name" in str(e):
        return _refuse(422, "invalid", str(e))
    return _refuse(409, "account_state", str(e))


# -- first run --------------------------------------------------------------------------


@router.get("/setup", response_model=SetupOut)
def setup_state(auth: Auth) -> SetupOut:
    """Whether the first admin still has to be made, and under which login (a name, not a secret)."""
    if auth.accounts.setup_state() is SetupState.READY:
        return SetupOut(state="ready")
    try:
        return SetupOut(state="needs_admin", admin_login=auth.accounts.admin_login())
    except SetupRequired:
        return SetupOut(state="needs_admin")


@router.post("/setup/admin", response_model=Me)
def create_first_admin(body: SetupIn, request: Request, response: Response, auth: Auth,
                       local: IsLocal) -> Me:
    """First run only, on the microscope PC only: the first admin, under the login the settings
    name (`softmatter` by default) and the password typed here, then logged in."""
    if not local:
        raise remote_view("remote view: set up the administrator on the microscope PC").http()
    if why := own_origin_refusal(request):  # T-009d checks this too; kept here on purpose
        raise why.http()
    if auth.accounts.setup_state() is SetupState.READY:
        raise _refuse(409, "setup_done", "an admin account already exists").http()
    try:
        acc = auth.accounts.create_first_admin(body.name, body.password)
    except PasswordPolicyError as e:
        raise _refuse(422, "password_policy", str(e)).http() from e
    except AccountError as e:
        raise _account_error(e).http() from e
    result = auth.logins.login(acc.login, body.password)
    _set_cookie(response, result.token)
    return _me(result.info, local)


# -- sign-up and login ------------------------------------------------------------------


@router.post("/signup", response_model=SignupOut, status_code=201)
def signup(body: SignupIn, auth: Auth, local: IsLocal) -> SignupOut:
    """Name, login, password only. The account waits for an admin, who sets its role (D12).

    The login is a plain id; an email is refused. On the microscope PC only (user decision
    2026-10-02, audit S3; may be opened later). A login that already has an account gets the same
    answer as a new one and nothing changes (audit S1): the answer never tells a caller which
    logins are registered; the audit log records it for the admin."""
    if not local:
        raise remote_view("remote view: sign up on the microscope PC").http()
    try:
        auth.accounts.register(body.name, body.login, body.password)
    except PasswordPolicyError as e:
        raise _refuse(422, "password_policy", str(e)).http() from e
    except DuplicateAccountError:
        if auth.audit is not None:
            auth.audit.append(AuditKind.SIGNUP_EXISTING, body.login)
    except AccountError as e:
        raise _account_error(e).http() from e
    return SignupOut(status="pending")


def _client(request: Request) -> str | None:
    return request.client.host if request.client else None


def _too_many(message: str, retry_after_s: int) -> JSONResponse:
    return JSONResponse({"detail": {"code": "too_many_attempts", "message": message}},
                        status_code=429, headers={"X-DinoAF-Refusal": "too_many_attempts",
                                                  "Retry-After": str(retry_after_s)})


@router.post("/login", response_model=Me, responses={401: {}, 429: {}})
def login(body: LoginIn, request: Request, response: Response, auth: Auth, local: IsLocal):
    result = auth.logins.login(body.login, body.password, client=_client(request))
    if result.retry_after_s is not None:  # too many wrong passwords (audit S2)
        return _too_many(result.message, result.retry_after_s)
    if result.outcome is LoginOutcome.NOT_A_LOGIN:  # an email, say: no password was looked at
        raise _refuse(422, "not_a_login", result.message).http()
    if not result.ok:
        # code is the outcome: bad_credentials | pending_approval | disabled
        return JSONResponse(
            {"detail": {"code": str(result.outcome), "message": result.message}},
            status_code=401, headers={"X-DinoAF-Refusal": str(result.outcome)})
    _set_cookie(response, result.token)
    return _me(result.info, local)


@router.post("/logout", status_code=204)
def logout(response: Response, me: Login, auth: Auth) -> Response:
    """Ends the login. Fine without a login."""
    if me.token:
        auth.logins.logout(me.token)
    out = Response(status_code=204)
    out.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")
    return out


@router.post("/lock", status_code=204)
def lock(me: Login, auth: Auth) -> Response:
    _logged_in(me, locked_ok=True)
    auth.logins.lock(me.token)
    return Response(status_code=204)


@router.post("/unlock", response_model=Me, responses={429: {}})
def unlock(body: UnlockIn, request: Request, me: Login, auth: Auth):
    _logged_in(me, locked_ok=True)
    try:
        info = auth.logins.unlock(me.token, body.password, client=_client(request))
    except TooManyAttempts as e:  # audit S2
        return _too_many(str(e), e.retry_after_s)
    if info is None:
        raise _refuse(401, "bad_credentials", "Wrong password.").http()
    return _me(info, me.local)


@router.post("/activity", status_code=204)
def activity(me: Login, auth: Auth) -> Response:
    """Someone is working: keeps the idle lock from firing. A locked login stays locked."""
    _logged_in(me, locked_ok=True)
    auth.logins.touch(me.token)
    return Response(status_code=204)


@router.get("/me", response_model=Me, responses={401: {}})
def who_am_i(me: Login, auth: Auth) -> Me:
    if me.info is None:
        raise LOGIN_REQUIRED.http()
    return _me(me.info, me.local)


# -- accounts (admin, microscope PC) ----------------------------------------------------


@router.get("/accounts", response_model=list[AccountOut])
def accounts(me: Login, auth: Auth,
             status: Literal["pending", "active", "disabled"] | None = None) -> list[AccountOut]:
    _admin_here(me)
    return [_account(a) for a in auth.accounts.accounts()
            if status is None or str(a.status) == status]


@router.get("/accounts/needs-login", response_model=list[NeedsLoginOut])
def needs_login(me: Login, auth: Auth) -> list[NeedsLoginOut]:
    """Accounts an older console recorded under an email. None of them can log in yet."""
    _admin_here(me)
    return [_needs_login(n) for n in auth.accounts.needs_login()]


def _admin_change(me: LoginState, fn) -> AccountOut:
    info = _admin_here(me)
    try:
        return _account(fn(info.user_id))
    except AccountError as e:
        raise _account_error(e).http() from e


@router.post("/accounts/give-login", response_model=AccountOut)
def give_login(body: GiveLoginIn, me: Login, auth: Auth) -> AccountOut:
    """Give an email-keyed account a plain login. Nothing is guessed: the administrator names it.
    The audit line names both."""
    return _admin_change(me, lambda admin: auth.accounts.give_login(admin, body.email, body.login))


@router.post("/accounts/{login}/approve", response_model=AccountOut)
def approve(login: str, body: RoleIn, me: Login, auth: Auth) -> AccountOut:
    """The role is chosen here by the admin, and nowhere else (D12)."""
    return _admin_change(me, lambda admin: auth.accounts.approve(admin, login, body.role))


@router.post("/accounts/{login}/role", response_model=AccountOut)
def set_role(login: str, body: RoleIn, me: Login, auth: Auth) -> AccountOut:
    return _admin_change(me, lambda admin: auth.accounts.set_role(admin, login, body.role))


@router.post("/accounts/{login}/disable", response_model=AccountOut)
def disable(login: str, me: Login, auth: Auth) -> AccountOut:
    """Switch an account off. Accounts are never deleted: the audit log refers to them."""
    return _admin_change(me, lambda admin: auth.accounts.disable(admin, login))


@router.post("/accounts/{login}/enable", response_model=AccountOut)
def enable(login: str, me: Login, auth: Auth) -> AccountOut:
    return _admin_change(me, lambda admin: auth.accounts.enable(admin, login))


@router.post("/accounts/{login}/password", response_model=AccountOut)
def reset_password(login: str, body: PasswordIn, me: Login, auth: Auth) -> AccountOut:
    """The admin sets a new password; every login of that account ends."""
    def change(admin: str):
        acc = auth.accounts.reset_password(admin, login, body.password)
        auth.logins.end_user(acc.login, "password_reset")
        return acc
    try:
        return _admin_change(me, change)
    except PasswordPolicyError as e:
        raise _refuse(422, "password_policy", str(e)).http() from e
