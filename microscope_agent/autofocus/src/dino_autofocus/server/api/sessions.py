"""`/api/sessions`: experiment sessions (PLAN.md F7), contract `docs/screens/sessions.md`.

Reads are for everyone who may read the API. Writes (open, close, continue) go through the one
permission rule for server actions (`server_action_why`: login, loopback, T-018 role) and the
CSRF origin check; this module adds only the sessions area's own rules (one open session, one
sample per session, the session's owner, closed sessions), as plain refusals that are never
`remote_view`.

The records store is `app.state.records`, the T-019 `RecordsStore` the server was created with.
Commits go to the app's one `AutoCommitter`, `app.state.committer` (T-009e: the launcher passes
it, the lifespan flushes and stops it), so a handler never waits on git; without one, a
session commits in the request thread. The code version is read once per app (G4).

The open session object lives in `app.state.sessions` (`SessionSeat`), so the engine's sample
operations write through the same object and share its seq counter; the engine hears about
every change through `set_experiment_session`.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...engine.backend import is_bench
from ...engine.operations.sample_ops import ensure_sample_created
from ...records import (
    AutoCommitter,
    ExperimentSession,
    SessionClosedError,
    code_version,
)
from ...records import open_session as find_open_session
from ...records.layout import check_id, read_jsonl
from . import Engine, Login, Refusal, Sessions, origin_refusal, server_action_why

router = APIRouter()

LOG_TAIL_MAX = 1000


# -- response shapes (docs/screens/sessions.md section 2) ----------------------------------


class SessionSummaryOut(BaseModel):
    session_id: str
    user_id: str
    user_name: str = ""
    sample_id: str
    status: Literal["open", "closed"]
    started_at: str
    closed_at: str | None = None
    continues: str | None = None
    reflected: bool | None = Field(None, description="None: no librarian ledger to tell")


class CodeOut(BaseModel):
    repo: str = ""
    commit: str | None = None
    dirty: bool | None = None
    error: str | None = None


class SessionHardwareProfileOut(BaseModel):
    path: str
    sha256: str


class RecordFileOut(BaseModel):
    name: str
    lines: int


class ManifestOut(BaseModel):
    files: int
    bytes: int
    by_where: dict[str, int]
    entries: list[dict[str, Any]]


class SessionDetailOut(SessionSummaryOut):
    """`session.json` as recorded (code version and hardware hash are never recomputed)."""

    code: CodeOut
    hardware_profile: SessionHardwareProfileOut | None = None
    sma_run_id: str | None = None
    #: what the session ran on (T-106b); `bench` is True only on the real stand
    backend_kind: str | None = None
    bench: bool | None = None
    close_note: str = ""
    log_tail: list[dict[str, Any]]
    records: list[RecordFileOut]
    manifest: ManifestOut


class OpenIn(BaseModel):
    sample_id: str | None = Field(None, description="must match the engine's current sample")


class CloseIn(BaseModel):
    note: str = ""


# -- app-level helpers ----------------------------------------------------------------------

_app_lock = threading.Lock()


def _store(request: Request) -> Any:
    """`app.state.records`, the T-019 store `create_app(records=...)` was given."""
    store = getattr(request.app.state, "records", None)
    if store is None:
        raise Refusal(503, "no_records", "no records store is configured on this server").http()
    return store


def _committer(request: Request) -> AutoCommitter | None:
    """`app.state.committer` (T-009e), or None: then sessions commit in the request thread."""
    return getattr(request.app.state, "committer", None)


def _code(request: Request) -> Any:
    with _app_lock:
        cv = getattr(request.app.state, "records_code_version", None)
        if cv is None:
            cv = code_version()
            request.app.state.records_code_version = cv
        return cv


def _snapshot(eng: Any) -> dict[str, Any]:
    try:
        return eng.snapshot() or {}
    except Exception:  # noqa: BLE001 - a read problem here must not hide the sessions list
        return {}


def _backend(eng: Any) -> tuple[str | None, bool | None]:
    """(backend kind, bench) from the engine's snapshot, by the engine's own bench rule
    (`is_bench`, fail-safe); (None, None) when the engine reports no backend info."""
    info = _snapshot(eng).get("backend_info")
    if not isinstance(info, dict) or not info.get("kind"):
        return None, None
    return str(info["kind"]), is_bench(SimpleNamespace(**info))


def _current_sample(eng: Any) -> str | None:
    return ((_snapshot(eng).get("sample") or {}).get("sample_id")) or None


def _profile_path(eng: Any) -> Path | None:
    p = (_snapshot(eng).get("hardware") or {}).get("profile_path")
    return Path(p) if p and Path(p).is_file() else None


def _tell_engine(eng: Any, session: ExperimentSession | None) -> None:
    set_session = getattr(eng, "set_experiment_session", None)
    if set_session is None:
        return
    if session is None:
        set_session(None)
    else:
        set_session(session.session_id,
                    datetime.fromisoformat(session.info.started_at).timestamp())


def _reflected(store: Any) -> set[str] | None:
    ledger = Path(store.config.records_root) / "librarian" / "reflected.jsonl"
    if not ledger.is_file():
        return None
    return {d.get("session_id") for d in read_jsonl(ledger)}


def _summary(info: dict[str, Any], reflected: set[str] | None) -> SessionSummaryOut:
    return SessionSummaryOut(
        session_id=info["session_id"], user_id=info.get("user_id", ""),
        user_name=info.get("user_name", ""), sample_id=info.get("sample_id", ""),
        status=info.get("status", "open"), started_at=info.get("started_at", ""),
        closed_at=info.get("closed_at"), continues=info.get("continues"),
        reflected=None if reflected is None else info["session_id"] in reflected)


def _detail(store: Any, s: ExperimentSession, log_tail: int) -> SessionDetailOut:
    from dataclasses import asdict

    info = asdict(s.info)
    m = s.manifest()
    by_where: dict[str, int] = {}
    for e in m.entries:
        by_where[e.where] = by_where.get(e.where, 0) + 1
    lines = s.log_lines()
    return SessionDetailOut(
        **_summary(info, _reflected(store)).model_dump(),
        code=CodeOut(**{k: info["code"].get(k) for k in ("repo", "commit", "dirty", "error")
                        if k in info["code"]}),
        hardware_profile=info.get("hardware_profile"), sma_run_id=info.get("sma_run_id"),
        backend_kind=info.get("backend_kind"), bench=info.get("bench"),
        close_note=info.get("close_note", ""),
        log_tail=lines[-log_tail:] if log_tail > 0 else [],
        records=[RecordFileOut(**r) for r in s.record_files()],
        manifest=ManifestOut(files=len(m.entries), bytes=sum(e.size for e in m.entries),
                             by_where=by_where, entries=[asdict(e) for e in m.entries]))


def _load(store: Any, session_id: str, seat: Any) -> ExperimentSession:
    try:
        check_id(session_id)
    except ValueError:
        raise Refusal(404, "not_found", f"No experiment session {session_id}").http() from None
    current = seat.session_for(session_id)
    if current is not None:
        return current
    if not (store.config.session_dir(session_id) / "session.json").is_file():
        raise Refusal(404, "not_found", f"No experiment session {session_id}").http()
    return ExperimentSession.load(store, session_id)


def _may(request: Request, me: Any, action: str) -> None:
    why = server_action_why(me, action) or origin_refusal(request)
    if why is not None:
        raise why.http()


def _no_open_session(store: Any) -> None:
    open_ = find_open_session(store)
    if open_ is not None:
        raise Refusal(409, "session_open",
                      f"{open_['session_id']} is open; close it first").http()


def _open(request: Request, eng: Any, me: Any, seat: Any, store: Any, sample_id: str,
          continues: str | None) -> ExperimentSession:
    try:
        kind, bench = _backend(eng)
        s = ExperimentSession.open(store, me.info.user_id, sample_id, user_name=me.info.name,
                                   hardware_profile=_profile_path(eng), continues=continues,
                                   code=_code(request), committer=_committer(request),
                                   backend_kind=kind, bench=bench)
    except ValueError as exc:
        raise Refusal(422, "bad_sample", str(exc)).http() from None
    seat.set(s)
    _tell_engine(eng, s)
    ensure_sample_created(s, store)  # T-027: first event for a sample's first session
    return s


# -- routes ---------------------------------------------------------------------------------


@router.get("", response_model=list[SessionSummaryOut])
def list_sessions(request: Request, user: str | None = None, sample: str | None = None,
                  status: Literal["open", "closed"] | None = None) -> list[SessionSummaryOut]:
    """Every experiment session, oldest first, optionally filtered."""
    store = _store(request)
    reflected = _reflected(store)
    return [_summary(i, reflected) for i in store.list_sessions()
            if (not user or i.get("user_id") == user)
            and (not sample or i.get("sample_id") == sample)
            and (not status or i.get("status") == status)]


@router.get("/current", response_model=SessionSummaryOut | None)
def current_session(request: Request) -> SessionSummaryOut | None:
    """The open experiment session, or null."""
    store = _store(request)
    info = find_open_session(store)
    return None if info is None else _summary(info, _reflected(store))


@router.get("/{session_id}", response_model=SessionDetailOut)
def session_detail(request: Request, session_id: str, seat: Sessions,
                   log_tail: int = 200) -> SessionDetailOut:
    store = _store(request)
    s = _load(store, session_id, seat)
    return _detail(store, s, max(0, min(log_tail, LOG_TAIL_MAX)))


@router.post("", status_code=201, response_model=SessionDetailOut)
def open_session(request: Request, eng: Engine, me: Login, seat: Sessions,
                 body: OpenIn | None = None) -> SessionDetailOut:
    """Open a session for the engine's current sample (one sample per session)."""
    _may(request, me, "session_open")
    store = _store(request)
    _no_open_session(store)
    current = _current_sample(eng)
    if current is None:
        raise Refusal(409, "no_sample", "Open or create a sample first").http()
    if body is not None and body.sample_id and body.sample_id != current:
        raise Refusal(409, "other_sample",
                      f"The current sample is {current}; open {body.sample_id} first").http()
    return _detail(store, _open(request, eng, me, seat, store, current, None), 200)


@router.post("/{session_id}/close", response_model=SessionDetailOut)
def close_session(request: Request, session_id: str, eng: Engine, me: Login, seat: Sessions,
                  body: CloseIn | None = None) -> SessionDetailOut:
    _may(request, me, "session_close")
    store = _store(request)
    s = _load(store, session_id, seat)
    if not s.writable:
        raise Refusal(409, "closed", f"Session {session_id} is closed (read-only)").http()
    if me.info.role != "admin" and s.info.user_id != me.info.user_id:
        raise Refusal(403, "not_owner",
                      f"Only {s.info.user_id} or an admin can close this session").http()
    if s.committer is None:
        s.committer = _committer(request)
    try:
        s.close(note=body.note if body else "")
    except SessionClosedError:
        raise Refusal(409, "closed", f"Session {session_id} is closed (read-only)").http() \
            from None
    if seat.session_for(session_id) is not None:
        seat.clear()
    if ((_snapshot(eng).get("session") or {}).get("session_id")) == session_id:
        _tell_engine(eng, None)
    return _detail(store, s, 200)


@router.post("/{session_id}/continue", status_code=201, response_model=SessionDetailOut)
def continue_session(request: Request, session_id: str, eng: Engine, me: Login,
                     seat: Sessions) -> SessionDetailOut:
    """A new session on the same sample as `session_id` (F7.4): the sample is picked again
    (nothing moves) and a session opens for it with `continues` set."""
    _may(request, me, "session_continue")
    store = _store(request)
    prev = _load(store, session_id, seat)
    _no_open_session(store)
    pick = getattr(eng, "set_current_sample", None)
    if pick is not None:
        pick(prev.info.sample_id, reserved=True)
    return _detail(store, _open(request, eng, me, seat, store, prev.info.sample_id, session_id),
                   200)
