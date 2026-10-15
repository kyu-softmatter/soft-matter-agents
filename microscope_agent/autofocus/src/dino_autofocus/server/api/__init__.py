"""Registration point for the area routers (console, hardware, sample, map, objective, ...),
and the access rules and dependencies they share.

An area adds one module here, `server/api/<area>.py`, holding a module-level
`router = fastapi.APIRouter()`. It is found on start-up and mounted at `/api/<area>` with the
tag `<area>`; this file is not edited per area. Modules whose names start with `_` are skipped.

Dependencies for handlers (`Annotated`, so `def handler(eng: Engine, me: Login): ...`):
- `Engine`: the engine. `AgentStoreDep`: the agent store (F1). `Auth`: the `AuthSeat`.
- `Sessions`: the `SessionSeat` holding the open ExperimentSession (T-019, T-106).
- `Login`: who is asking (`LoginState`: login token or None, `LoginInfo` or None, `local`).
- `IsLocal`: whether the request comes from the microscope PC itself (loopback socket).
- `LocalOnly`: refuse unless the request may write from here (loopback, a live unlocked
  login, not from a foreign page). Area writes that move nothing but must stay local use it.

Access (PLAN.md 5, D13, D16; manager's T-009b contract), one place for REST and WebSocket:
- Without a live login only these work: `GET /api/health` and `/api/auth/setup`, the login
  routes, first-run `POST /api/auth/setup/admin` (loopback, own page only), `POST
  /api/shutdown` (loopback), and the stops `abort` / `lights_off` from loopback. Everything
  else under `/api/*` and `/ws/*` is 401 `login_required`; a locked login gets 423 `locked`
  except for stops and the login routes.
- A remote viewer reads, and may send `abort` (logged in, D13) and nothing else: 403
  `remote_view`, the one code that switches the web client to read-only.
- Refusals carry `detail = {code, message}` and the header `X-DinoAF-Refusal: <code>`.
- Writes and WebSocket handshakes from a browser are accepted only from this server's own
  origin or a `--dev-origin` (403 `foreign_origin`), see `origin_refusal`.
"""

from __future__ import annotations

import importlib
import ipaddress
import pkgutil
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.requests import HTTPConnection

from ...agents import AgentStore
from ...auth import (
    AccountStore,
    Action,
    AuditLog,
    ControlHolder,
    DeviceControl,
    LoginInfo,
    LoginSessions,
    allows,
)
from ...engine.runner import permission
from ..schemas import EngineAPI

SESSION_COOKIE = "dinoaf_session"  # the T-018 login token; set by server/api/auth.py (T-105)
REFUSAL_HEADER = "X-DinoAF-Refusal"
STOPS = frozenset({"abort", "lights_off"})
# D16: map writes go only through server/api/map.py, which checks WRITE_MAP_FLAG
MAP_WRITE_OPS = frozenset({"map_flag", "map_flag_retire", "candidate_confirm", "candidate_reject"})
# actions the server decides itself (not engine operations), for /api/permissions
SESSION_ACTIONS = frozenset({"session_open", "session_close", "session_continue"})
# live_on: switch on soft-matter-agents' live view (its card 062); an operator action, local
SERVER_ACTIONS = SESSION_ACTIONS | {"submit_question", "live_on"}


# -- refusals ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Refusal:
    status: int
    code: str
    message: str

    def body(self) -> dict[str, Any]:
        return {"detail": {"code": self.code, "message": self.message}}

    def headers(self) -> dict[str, str]:
        return {REFUSAL_HEADER: self.code}

    def http(self) -> HTTPException:
        return HTTPException(self.status, detail=self.body()["detail"], headers=self.headers())

    def response(self) -> JSONResponse:
        return JSONResponse(self.body(), status_code=self.status, headers=self.headers())


def remote_view(message: str) -> Refusal:
    return Refusal(403, "remote_view", message)


LOGIN_REQUIRED = Refusal(401, "login_required", "log in first")
LOCKED = Refusal(423, "locked", "the screen is locked; unlock it first")


# -- the login seat ---------------------------------------------------------------------


class AuthSeat:
    """T-018's accounts, login sessions and device control, as the server holds them.

    The control token never reaches the browser: `acquire` keeps it here and `grant_for`
    hands it to the engine Command. Route code (T-105) calls `acquire` / `release` on the
    seat, not on `control`, so the seat knows the grant; a revoke, logout or expiry is seen
    through `control.holder()` and ends the grant here too."""

    def __init__(self, accounts: AccountStore, logins: LoginSessions, control: DeviceControl,
                 audit: AuditLog | None = None) -> None:
        self.accounts, self.logins, self.control, self.audit = accounts, logins, control, audit
        self._grants: dict[str, str] = {}  # login_id -> control token
        self._lock = threading.Lock()

    @classmethod
    def from_config(cls, config_dir: str | Path | None = None) -> AuthSeat:
        """The real files in the local config folder (accounts.json, audit.jsonl)."""
        from ...auth import config

        d = config.config_dir(config_dir)
        audit = AuditLog(d / config.AUDIT_FILE)
        accounts = AccountStore(audit=audit, config_dir=d)
        logins = LoginSessions(accounts, audit=audit)
        return cls(accounts, logins, DeviceControl(logins, audit=audit), audit)

    @classmethod
    def throwaway(cls) -> AuthSeat:
        """No accounts, under a fresh temporary path: nobody can log in until one is created.
        The default for `create_app` so tests and tools never touch the real config folder.
        The stores create the folder only when they first write."""
        return cls.from_config(Path(tempfile.gettempdir()) / f"dinoaf-auth-{uuid.uuid4().hex}")

    def login(self, token: str | None) -> LoginInfo | None:
        return self.logins.get(token) if token else None

    def acquire(self, login_token: str, *, local: bool) -> ControlHolder:
        g = self.control.acquire(login_token, local=local)
        with self._lock:
            self._grants[g.login_id] = g.token
        return ControlHolder(g.user_id, g.login_id, g.acquired_at)

    def release(self, login_token: str) -> None:
        info = self.logins.get(login_token)
        self.control.release(login_token)
        if info is not None:
            with self._lock:
                self._grants.pop(info.login_id, None)

    def grant_for(self, info: LoginInfo | None) -> str | None:
        """The control token this login holds right now, or None."""
        if info is None:
            return None
        holder = self.control.holder()
        with self._lock:
            if holder is None or holder.login_id != info.login_id:
                self._grants.pop(info.login_id, None)
                return None
            return self._grants.get(info.login_id)

    def has_control(self, info: LoginInfo | None) -> bool:
        return self.grant_for(info) is not None


class SessionSeat:
    """The server's open ExperimentSession (T-019), one object for every writer so they share
    its seq counter. The sessions router (T-106) calls `set` on open / continue and `clear`
    on close (and tells the engine through `set_experiment_session`); the engine's sample
    seat reads it through `session_for`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current: Any = None

    def set(self, session: Any) -> None:
        with self._lock:
            self.current = session

    def clear(self) -> None:
        with self._lock:
            self.current = None

    def session_for(self, session_id: str | None) -> Any:
        with self._lock:
            cur = self.current
        if cur is None or session_id is None or cur.info.session_id != session_id:
            return None
        return cur


@dataclass(frozen=True)
class LoginState:
    token: str | None
    info: LoginInfo | None
    local: bool

    @property
    def user_id(self) -> str | None:
        return self.info.user_id if self.info else None


# -- the rules --------------------------------------------------------------------------


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def is_local(conn: HTTPConnection) -> bool:
    return is_loopback_host(conn.client.host if conn.client else None)


def login_state(conn: HTTPConnection) -> LoginState:
    token = conn.cookies.get(SESSION_COOKIE)
    return LoginState(token, conn.app.state.auth.login(token), is_local(conn))


def normalize_origin(value: str) -> str:
    """`scheme://host:port` in lower case, for comparing origins. Raises ValueError for
    anything that is not a plain http(s) origin (a path, `null`, no host)."""
    o = urlsplit(value.strip())
    if o.scheme not in ("http", "https") or not o.netloc or o.path not in ("", "/") \
            or o.query or o.fragment:
        raise ValueError(f"not an http(s) origin: {value!r}")
    return f"{o.scheme}://{o.netloc}".lower()


def own_origin(conn: HTTPConnection) -> str:
    """This server's origin as the browser sees it: the request's scheme and Host header."""
    scheme = {"ws": "http", "wss": "https"}.get(conn.url.scheme, conn.url.scheme)
    return f"{scheme}://{conn.headers.get('host', '')}".lower()


def origin_refusal(conn: HTTPConnection, *, required: bool = False) -> Refusal | None:
    """A browser page may write (and open a WebSocket) only if it was served by this server,
    or by a dev server named with `--dev-origin` (T-009c). The comparison is exact: scheme,
    host and port, so a page on another loopback port of this PC is refused even though
    SameSite lets it carry the login cookie, and `localhost` is not `127.0.0.1`.
    Non-browser clients send no Origin and pass, unless `required` (first-run setup)."""
    origin = conn.headers.get("origin")
    if origin is None and not required:
        return None
    if origin is not None:
        try:
            value = normalize_origin(origin)
        except ValueError:
            value = None
        if value is not None and (value == own_origin(conn)
                                  or value in getattr(conn.app.state, "dev_origins", ())):
            return None
    return Refusal(403, "foreign_origin",
                   f"not accepted from a page served by {origin or 'nothing (no Origin)'}; "
                   f"only this server's own page")


def own_origin_refusal(conn: HTTPConnection) -> Refusal | None:
    """First-run setup (T-009d): the same rule, and an Origin is required."""
    return origin_refusal(conn, required=True)


def logged_in_refusal(me: LoginState, *, locked_ok: bool = False) -> Refusal | None:
    if me.info is None:
        return LOGIN_REQUIRED
    if me.info.locked and not locked_ok:
        return LOCKED
    return None


def command_why(me: LoginState, kind: str | None, op: str = "", *,
                remote_abort: bool = True) -> Refusal | None:
    """Why this person may not send a command of `kind` (and `op` for `start`), from login,
    loopback, D13 and D16, or None. The engine adds control, session and state (T-011).
    `kind=None` means "some write whose kind is unknown" and gets no stop exception."""
    if kind == "start" and op in MAP_WRITE_OPS:
        return Refusal(403, "map_route", f"{op!r} goes through /api/map, not /api/commands (D16)")
    stop = kind in STOPS
    if not me.local:
        if kind != "abort":
            allowed = "abort only" if remote_abort else "nothing"
            return remote_view(f"remote view: commands are accepted only on the microscope PC "
                               f"(remote viewers may send {allowed})")
        if not remote_abort:
            return remote_view("remote view: remote abort is switched off")
        return logged_in_refusal(me, locked_ok=True)  # D13 assumes a logged-in viewer
    if stop:
        return None  # loopback stops: always, with or without a login (PLAN.md 5)
    if why := logged_in_refusal(me):
        return why
    if kind == "start" and permission(op).operator and not allows(
            me.info.role, Action.OPERATE, local=True):
        return Refusal(403, "role", f"role {me.info.role} may not run {op}")
    return None


def command_refusal(conn: HTTPConnection, kind: str | None = None, op: str = "") -> Refusal | None:
    """The origin first (a foreign page learns nothing about the login), then the rules."""
    remote_abort = getattr(conn.app.state, "remote_abort", True)
    return (origin_refusal(conn)
            or command_why(login_state(conn), kind, op, remote_abort=remote_abort))


def server_action_why(me: LoginState, action: str) -> Refusal | None:
    """The T-018 named permission plus loopback for a non-engine action (session_open,
    session_close, session_continue, submit_question) or a map write (D16, WRITE_MAP_FLAG;
    the engine's `check()` still has its say on those)."""
    if why := logged_in_refusal(me):
        return why
    need = (Action.SUBMIT_QUESTION if action == "submit_question"
            else Action.WRITE_MAP_FLAG if action in MAP_WRITE_OPS else Action.OPERATE)
    if not me.local:
        return remote_view(f"remote view: {action} is allowed on the microscope PC only")
    if not allows(me.info.role, need, local=True):
        return Refusal(403, "role", f"role {me.info.role} may not {action}")
    return None


# -- dependencies -----------------------------------------------------------------------


def get_engine(request: Request) -> EngineAPI:
    return request.app.state.engine


def get_agent_store(request: Request) -> AgentStore:
    return request.app.state.agent_store


def get_auth(request: Request) -> AuthSeat:
    return request.app.state.auth


def get_sessions(request: Request) -> SessionSeat:
    return request.app.state.sessions


def local_only(request: Request) -> None:
    if why := command_refusal(request):
        raise why.http()


Engine = Annotated[EngineAPI, Depends(get_engine)]
AgentStoreDep = Annotated[AgentStore, Depends(get_agent_store)]
Auth = Annotated[AuthSeat, Depends(get_auth)]
Sessions = Annotated[SessionSeat, Depends(get_sessions)]
Login = Annotated[LoginState, Depends(login_state)]
IsLocal = Annotated[bool, Depends(is_local)]
LocalOnly = Depends(local_only)  # router- or route-level: dependencies=[LocalOnly]


def include_area_routers(app: FastAPI, package: str = __name__) -> list[str]:
    """Mount every area router found in `package`; returns the area names, sorted."""
    pkg = importlib.import_module(package)
    areas = []
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        if info.name.startswith("_") or info.ispkg:
            continue
        module = importlib.import_module(f"{package}.{info.name}")
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            raise TypeError(f"{module.__name__} has no module-level `router = APIRouter()`")
        app.include_router(router, prefix=f"/api/{info.name}", tags=[info.name])
        areas.append(info.name)
    return areas
