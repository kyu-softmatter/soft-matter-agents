"""The FastAPI app: it shows. It passes the engine's events and snapshot on to the screens,
reads soft-matter-agents' files through the agent store, and decides nothing itself.

Since soft-matter-agents card 077 it sends no command to any engine: `/api/commands`, the
command messages on `/ws/events`, the assistant's engine hooks and the engine-backed area
routers (hardware, map, objective, patterns, sample, sessions) were retired with dino's
engine command path, and the only engine it is built with is the placeholder. The engine and
its records stay in `microscope_agent/autofocus/`; this module imports neither.

Access scope (PLAN.md 5, D13, D16; the rules live in `server/api/__init__.py`):
- The server listens on 127.0.0.1 only; `remote_view` opens it to other PCs for viewing.
- The Host header must be in an allow-list (loopback names, plus this PC's names and
  addresses under remote view), so a page that rebinds its own domain to 127.0.0.1 is refused.
- Every `/api/*` route and `/ws/*` needs a live login (the `dinoaf_session` cookie), except
  `GET /api/health`, `GET /api/auth/setup`, the login routes `POST /api/auth/{login, logout,
  lock, unlock, activity, signup}`, first-run `POST /api/auth/setup/admin` (from the microscope
  PC and this server's own page only), `POST /api/shutdown` from the microscope PC (the
  launcher has no login), and the stops `abort` / `lights_off` from the microscope PC.
- A write (any method other than GET/HEAD/OPTIONS, and command messages on `/ws/events`) is
  accepted only from the microscope PC itself, and only from a page served by this server or
  a dev server named with `dev_origins` (or a non-browser client), so a page in another tab,
  even one on another loopback port that carries the login cookie, cannot drive the stage.
  WebSocket handshakes get the same origin check.
- D13: a logged-in remote viewer may send `abort` and nothing else (`remote_abort`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import threading
from collections.abc import AsyncIterator, Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.openapi.utils import get_openapi
from pydantic.json_schema import models_json_schema
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ..agents import AgentStore, MockStore
from . import static, ws
from .api import (
    SERVER_ACTIONS,
    AuthSeat,
    Engine,
    Refusal,
    SessionSeat,
    command_refusal,
    include_area_routers,
    is_local,
    logged_in_refusal,
    login_state,
    normalize_origin,
    origin_refusal,
    own_origin_refusal,
    remote_view,
    server_action_why,
)
from .edge import EdgeMiddleware
from .schemas import (
    WS_MODELS,
    ApiError,
    EngineAPI,
    Health,
    PermissionOut,
    ShutdownAccepted,
    ShutdownIn,
    Snapshot,
)

log = logging.getLogger("dino_autofocus.server.app")

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
LOOPBACK_HOSTS = ("127.0.0.1", "localhost")
# the Abort of a run soft-matter-agents executes (plan.md 11-25): a stop, so it gets the stop
# rules (loopback always; a logged-in remote viewer when remote abort is on, D13)
SMA_STOP_PATH = re.compile(r"^/api/console/runs/[^/]+/[^/]+/stop$")
# "Stop all runs", for the lock screen and the logged-out screens (console card 004, the person
# at cee4f8c1): one write that stops every running followed microscope run. A stop, so the same
# rules as the line above. It is the only new thing reachable without a login, and only from
# the microscope PC; POST only, any other method is judged as an ordinary write.
STOP_ALL_PATH = "/api/console/runs/stop"
SHUTDOWN_PATH = "/api/shutdown"
OPEN_READS = frozenset({"/api/health", "/api/auth/setup"})  # setup: first-run state (T-105)
# reads a locked login still gets: the lock screen needs who is locked (T-105 `/me`)
LOCKED_OK_READS = frozenset({"/api/auth/me"})
# the one write that works with no login: making the first admin (T-105 handles 409 after)
SETUP_ADMIN_PATH = "/api/auth/setup/admin"
# remote viewers must be able to log in (PLAN.md 5); T-018 adds the routes in server/api/auth.py
AUTH_OPEN_PATHS = frozenset(
    f"/api/auth/{name}" for name in ("login", "logout", "lock", "unlock", "activity", "signup")
)


class EngineStopper:
    """Stops the engine once, from whichever exit path gets there first: `POST /api/shutdown`,
    a signal, the app's lifespan end, the launcher's `finally`, or `atexit`. A failed attempt
    does not count, so a later path tries again."""

    def __init__(self, engine: EngineAPI) -> None:
        self._engine = engine
        self._lock = threading.Lock()
        self.reason: str | None = None

    @property
    def done(self) -> bool:
        return self.reason is not None

    def __call__(self, reason: str) -> bool:
        """True if this call stopped the engine, False if it was already stopped."""
        with self._lock:
            if self.reason is not None:
                return False
            self._engine.shutdown(reason)
            self.reason = reason
            log.info("engine stopped (%s)", reason)
            return True

    def quietly(self, reason: str) -> None:
        """For exit hooks: never raise, log instead."""
        try:
            self(reason)
        except Exception:
            log.exception("engine shutdown (%s) failed", reason)


NO_COMMANDS = "the console sends no command to any engine (soft-matter-agents card 077)"


def _shutdown_refusal(request: Request) -> Refusal | None:
    """The launcher stops the server from this PC without a login; no D13 exception."""
    if not is_local(request):
        return remote_view("remote view: only the microscope PC may stop the server")
    return origin_refusal(request)


def _http_refusal(request: Request) -> Refusal | None:
    """The cookie check and the write rule for every `/api/*` request."""
    path = request.url.path
    if request.method in READ_METHODS:
        if path in OPEN_READS:
            return None
        return logged_in_refusal(login_state(request), locked_ok=path in LOCKED_OK_READS)
    if path == SETUP_ADMIN_PATH:
        if not is_local(request):
            return remote_view("remote view: first-run setup is done on the microscope PC")
        return own_origin_refusal(request)
    if path in AUTH_OPEN_PATHS:
        return origin_refusal(request)
    if path == SHUTDOWN_PATH:
        return _shutdown_refusal(request)
    if SMA_STOP_PATH.match(path) or (path == STOP_ALL_PATH and request.method == "POST"):
        return command_refusal(request, "abort")
    return command_refusal(request)  # any other write: loopback, logged in, unlocked


def _package_version() -> str:
    try:
        return version("sma-console")
    except PackageNotFoundError:
        return "0+unknown"


def create_app(
    engine: EngineAPI,
    *,
    agent_store: AgentStore | None = None,
    auth: AuthSeat | None = None,
    sessions: SessionSeat | None = None,
    remote_view: bool = False,
    remote_abort: bool = True,
    allowed_hosts: Sequence[str] = (),
    dev_origins: Sequence[str] = (),
    engine_name: str = "unknown",
    web_dist: Path | None = None,
    live_host_file: Path | None = None,
    live_host: str | None = None,
) -> FastAPI:
    """`agent_store` defaults to a `MockStore` (dev); `auth` to an `AuthSeat` with no accounts
    in a temporary folder (nobody can log in; the launcher passes `AuthSeat.from_config()`).
    `sessions` is the `SessionSeat` the assistant reads the open session from; nothing opens
    one here since the sessions router was retired (soft-matter-agents card 077).
    `allowed_hosts` adds Host header names beyond the loopback ones; under remote view the
    launcher passes this PC's host names and addresses. `dev_origins` names page origins
    besides this server's own that may write, e.g. the Vite dev server
    `http://localhost:5173` (T-010); none by default."""
    stopper = EngineStopper(engine)

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        app.state.sessions.clear()
        yield
        await asyncio.to_thread(stopper.quietly, "server stopping")

    app = FastAPI(title="dino-autofocus", version=_package_version(), lifespan=lifespan)
    app.state.engine = engine
    app.state.agent_store = agent_store if agent_store is not None else MockStore()
    # soft-matter-agents' live-view host (its card 062): an address file, or a fixed address
    app.state.live_host_file = live_host_file
    app.state.live_host = live_host
    app.state.auth = auth if auth is not None else AuthSeat.throwaway()
    app.state.sessions = sessions if sessions is not None else SessionSeat()
    app.state.remote_view = remote_view
    app.state.remote_abort = remote_abort
    app.state.dev_origins = frozenset(normalize_origin(o) for o in dev_origins)
    app.state.stop_engine = stopper
    app.state.request_exit = None  # set by the launcher: makes the server process exit

    @app.middleware("http")
    async def access(request: Request, call_next):
        if request.url.path.startswith("/api/") and (why := _http_refusal(request)):
            return why.response()
        return await call_next(request)

    # proxied requests, docs for this PC only, security headers (audit S5, S6, S8)
    app.add_middleware(EdgeMiddleware)
    # added last, so it runs first, for HTTP and WebSocket alike
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=[*LOOPBACK_HOSTS, *allowed_hosts], www_redirect=False)

    @app.get("/api/health", response_model=Health, tags=["server"])
    def health() -> Health:
        return Health(engine=engine_name, remote_view=remote_view, remote_abort=remote_abort)

    @app.get("/api/state", response_model=Snapshot, tags=["server"])
    def state(eng: Engine) -> Snapshot:
        """The engine's snapshot: positions, lights, running operations, session, sample..."""
        return Snapshot.model_validate(eng.snapshot())

    @app.get("/api/permissions", response_model=dict[str, PermissionOut], tags=["server"])
    def permissions(request: Request, ops: str = "") -> dict[str, PermissionOut]:
        """`?ops=a,b,c` -> may I do each now, and if not, why. The server's own actions
        (`SERVER_ACTIONS`: the session actions, `submit_question`, `live_on`) follow the
        T-018 permissions plus loopback. Every other name -- an engine operation, a stop, a
        map write -- is not allowed, code `no_commands`: the console sends no command to any
        engine (soft-matter-agents card 077), so no screen should offer one."""
        me = login_state(request)
        names = list(dict.fromkeys(n.strip() for n in ops.split(",") if n.strip()))
        out = {}
        for n in names:
            if n not in SERVER_ACTIONS:
                out[n] = PermissionOut(allowed=False, reason=NO_COMMANDS, code="no_commands")
            elif why := server_action_why(me, n):
                out[n] = PermissionOut(allowed=False, reason=why.message, code=why.code)
            else:
                out[n] = PermissionOut(allowed=True)
        return out

    @app.post(
        "/api/shutdown",
        response_model=ShutdownAccepted,
        responses={403: {"model": ApiError}, 500: {"model": ApiError}},
        tags=["server"],
    )
    def shutdown(body: ShutdownIn, request: Request, tasks: BackgroundTasks) -> ShutdownAccepted:
        """Stop the engine (lights off with readback, abort, finish records), then exit. The
        launcher calls this before any hard kill. Microscope PC only, no D13 exception."""
        if why := _shutdown_refusal(request):
            raise why.http()
        request_exit = app.state.request_exit
        try:
            stopped = stopper(body.reason)
        except Exception as e:
            log.exception("engine shutdown failed")
            if request_exit is not None:
                request_exit()  # exit anyway; the atexit hook tries the engine once more
            raise Refusal(500, "shutdown_failed", f"engine shutdown failed: {e}").http() from e
        if request_exit is not None:
            tasks.add_task(request_exit)  # after the response has gone out
        return ShutdownAccepted(reason=stopper.reason or body.reason, already=not stopped)

    include_area_routers(app)
    ws.install(app, engine, stopped=lambda: stopper.done)
    static.mount_web(app, web_dist)

    def openapi() -> dict:
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            # WebSocket messages are not routes; list them so the TS types cover them too
            _, defs = models_json_schema(
                [(m, "validation") for m in WS_MODELS],
                ref_template="#/components/schemas/{model}",
            )
            components = schema.setdefault("components", {}).setdefault("schemas", {})
            for name, s in defs.get("$defs", {}).items():
                components.setdefault(name, s)
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app
