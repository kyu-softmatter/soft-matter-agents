"""Login, sign-up, approval and device control over HTTP (T-105; docs/screens/login.md).

Mounted at `/api/auth`. The logic is T-018's (`dino_autofocus.auth`) as the server holds it in
`AuthSeat`; this router only maps requests to it and its answers to HTTP. T-018 writes every
login, logout, lock, unlock, sign-up, approval, role change and control change to
`audit.jsonl`; nothing here logs a second time.

Access (app.py, server/api): `POST login | logout | lock | unlock | activity | signup` work
without a login (remote viewers log in too; sign-up itself is refused here from another PC);
login and unlock are attempt-limited (auth/throttle.py); every other route needs a live login,
and every other write also needs the microscope PC (loopback), an unlocked login and no
foreign Origin.
The admin routes and device control check loopback again here, for reads too. Stops (abort,
lights_off) never pass through this router, so nothing here can block them.

The session cookie (`dinoaf_session`) carries the T-018 login token: HttpOnly,
SameSite=Strict, path /, no Max-Age. The device-control token stays in `AuthSeat`; the browser
only sees `has_control`.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ...auth import (
    Account,
    AccountError,
    Action,
    AuditKind,
    ControlBusy,
    ControlError,
    DuplicateAccountError,
    LoginInfo,
    PasswordPolicyError,
    PermissionDenied,
    SetupRequired,
    SetupState,
    TooManyAttempts,
    allows,
    normalize_email,
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
    name: str
    password: str
    email: str | None = None


class SignupIn(_In):
    name: str
    email: str
    password: str


class LoginIn(_In):
    email: str
    password: str


class UnlockIn(_In):
    password: str


class RoleIn(_In):
    role: RoleName


class PasswordIn(_In):
    password: str


class RevokeIn(_In):
    reason: str = Field(min_length=1)


class SetupOut(BaseModel):
    state: Literal["needs_admin_email", "needs_admin", "ready"]


class Me(BaseModel):
    user_id: str
    name: str
    role: RoleName
    locked: bool
    has_control: bool
    local: bool
    expires_at: float


class AccountOut(BaseModel):
    email: str
    name: str
    role: RoleName
    status: Literal["pending", "active", "disabled"]
    created_at: str
    approved_by: str | None
    approved_at: str | None


class SignupOut(BaseModel):
    status: Literal["pending"]


class HolderOut(BaseModel):
    user_id: str
    name: str
    since: float


class ControlOut(BaseModel):
    holder: HolderOut | None


class RevokeOut(BaseModel):
    previous_holder: HolderOut | None


# -- helpers ----------------------------------------------------------------------------


def _refuse(status: int, code: str, message: str) -> Refusal:
    return Refusal(status, code, message)


def _me(auth, info: LoginInfo, local: bool) -> Me:
    return Me(user_id=info.user_id, name=info.name, role=str(info.role), locked=info.locked,
              has_control=auth.has_control(info), local=local, expires_at=info.expires_at)


def _account(a: Account) -> AccountOut:
    return AccountOut(**a.public())


def _holder(auth, h) -> HolderOut | None:
    if h is None:
        return None
    acc = auth.accounts.get(h.user_id)
    return HolderOut(user_id=h.user_id, name=acc.name if acc else h.user_id, since=h.acquired_at)


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
    if str(e).startswith("not an email") or "name" in str(e):
        return _refuse(422, "invalid", str(e))
    return _refuse(409, "account_state", str(e))


# -- first run --------------------------------------------------------------------------


@router.get("/setup", response_model=SetupOut)
def setup_state(auth: Auth) -> SetupOut:
    """Whether the first admin still has to be made. Never says which email is configured."""
    return SetupOut(state=str(auth.accounts.setup_state()))


@router.post("/setup/admin", response_model=Me)
def create_first_admin(body: SetupIn, request: Request, response: Response, auth: Auth,
                       local: IsLocal) -> Me:
    """First run only, on the microscope PC only: the first admin, then logged in."""
    if not local:
        raise remote_view("remote view: set up the administrator on the microscope PC").http()
    if why := own_origin_refusal(request):  # T-009d checks this too; kept here on purpose
        raise why.http()
    if auth.accounts.setup_state() is SetupState.READY:
        raise _refuse(409, "setup_done", "an admin account already exists").http()
    try:
        acc = auth.accounts.create_first_admin(body.name, body.password, email=body.email)
    except PasswordPolicyError as e:
        raise _refuse(422, "password_policy", str(e)).http() from e
    except AccountError as e:
        raise _account_error(e).http() from e
    result = auth.logins.login(acc.email, body.password)
    _set_cookie(response, result.token)
    return _me(auth, result.info, local)


# -- sign-up and login ------------------------------------------------------------------


@router.post("/signup", response_model=SignupOut, status_code=201)
def signup(body: SignupIn, auth: Auth, local: IsLocal) -> SignupOut:
    """Name, email, password only. The account waits for an admin, who sets its role (D12).

    On the microscope PC only (user decision 2026-10-02, audit S3; may be opened later). An
    email that already has an account gets the same answer as a new one and nothing changes
    (audit S1): the answer never tells a caller which emails are registered; the audit log
    records it for the admin."""
    if not local:
        raise remote_view("remote view: sign up on the microscope PC").http()
    try:
        auth.accounts.register(body.name, body.email, body.password)
    except PasswordPolicyError as e:
        raise _refuse(422, "password_policy", str(e)).http() from e
    except DuplicateAccountError:
        if auth.audit is not None:
            auth.audit.append(AuditKind.SIGNUP_EXISTING, normalize_email(body.email))
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
    result = auth.logins.login(body.email, body.password, client=_client(request))
    if result.retry_after_s is not None:  # too many wrong passwords (audit S2)
        return _too_many(result.message, result.retry_after_s)
    if not result.ok:
        # code is the outcome: bad_credentials | pending_approval | disabled
        return JSONResponse(
            {"detail": {"code": str(result.outcome), "message": result.message}},
            status_code=401, headers={"X-DinoAF-Refusal": str(result.outcome)})
    _set_cookie(response, result.token)
    return _me(auth, result.info, local)


@router.post("/logout", status_code=204)
def logout(response: Response, me: Login, auth: Auth) -> Response:
    """Ends the login (and frees device control if it held it). Fine without a login."""
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
    return _me(auth, info, me.local)


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
    return _me(auth, me.info, me.local)


# -- accounts (admin, microscope PC) ----------------------------------------------------


@router.get("/accounts", response_model=list[AccountOut])
def accounts(me: Login, auth: Auth,
             status: Literal["pending", "active", "disabled"] | None = None) -> list[AccountOut]:
    _admin_here(me)
    return [_account(a) for a in auth.accounts.accounts()
            if status is None or str(a.status) == status]


def _admin_change(me: LoginState, fn) -> AccountOut:
    info = _admin_here(me)
    try:
        return _account(fn(info.user_id))
    except AccountError as e:
        raise _account_error(e).http() from e


@router.post("/accounts/{email}/approve", response_model=AccountOut)
def approve(email: str, body: RoleIn, me: Login, auth: Auth) -> AccountOut:
    """The role is chosen here by the admin, and nowhere else (D12)."""
    return _admin_change(me, lambda admin: auth.accounts.approve(admin, email, body.role))


@router.post("/accounts/{email}/role", response_model=AccountOut)
def set_role(email: str, body: RoleIn, me: Login, auth: Auth) -> AccountOut:
    return _admin_change(me, lambda admin: auth.accounts.set_role(admin, email, body.role))


@router.post("/accounts/{email}/disable", response_model=AccountOut)
def disable(email: str, me: Login, auth: Auth) -> AccountOut:
    return _admin_change(me, lambda admin: auth.accounts.disable(admin, email))


@router.post("/accounts/{email}/enable", response_model=AccountOut)
def enable(email: str, me: Login, auth: Auth) -> AccountOut:
    return _admin_change(me, lambda admin: auth.accounts.enable(admin, email))


@router.post("/accounts/{email}/password", response_model=AccountOut)
def reset_password(email: str, body: PasswordIn, me: Login, auth: Auth) -> AccountOut:
    """The admin sets a new password; every login of that account ends."""
    def change(admin: str):
        acc = auth.accounts.reset_password(admin, email, body.password)
        auth.logins.end_user(acc.email, "password_reset")
        return acc
    try:
        return _admin_change(me, change)
    except PasswordPolicyError as e:
        raise _refuse(422, "password_policy", str(e)).http() from e


@router.post("/accounts/{email}/delete", response_model=AccountOut)
def delete(email: str, me: Login, auth: Auth) -> AccountOut:
    """Pending or disabled accounts only; the audit log keeps the history."""
    return _admin_change(me, lambda admin: auth.accounts.delete(admin, email))


# -- device control ---------------------------------------------------------------------


@router.get("/control", response_model=ControlOut)
def control(me: Login, auth: Auth) -> ControlOut:
    _logged_in(me)
    return ControlOut(holder=_holder(auth, auth.control.holder()))


@router.post("/control/acquire", response_model=ControlOut, responses={409: {}})
def acquire(me: Login, auth: Auth):
    _logged_in(me)
    try:
        h = auth.acquire(me.token, local=me.local)
    except ControlBusy as e:
        holder = _holder(auth, auth.control.holder())
        return JSONResponse(
            {"detail": {"code": "control_busy", "message": str(e)},
             "holder": holder.model_dump() if holder else None},
            status_code=409, headers={"X-DinoAF-Refusal": "control_busy"})
    except ControlError as e:
        if not me.local:
            raise remote_view(str(e)).http() from e
        raise _refuse(403, "control", str(e)).http() from e
    return ControlOut(holder=_holder(auth, h))


@router.post("/control/release", status_code=204)
def release(me: Login, auth: Auth) -> Response:
    _logged_in(me)
    try:
        auth.release(me.token)
    except ControlError as e:
        raise _refuse(409, "not_holder", str(e)).http() from e
    return Response(status_code=204)


@router.post("/control/revoke", response_model=RevokeOut)
def revoke(body: RevokeIn, me: Login, auth: Auth) -> RevokeOut:
    _admin_here(me)
    try:
        h = auth.control.revoke(me.token, body.reason)
    except ControlError as e:
        raise _refuse(403, "role", str(e)).http() from e
    return RevokeOut(previous_holder=_holder(auth, h))
