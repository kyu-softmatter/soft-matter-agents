"""The `sample` area router (F3, docs/screens/sample.md sections 3 and 4), mounted at /api/sample.

Read routes only, plus "Open folder". The five sample commands go through the common
`POST /api/commands`; the pre-click verdicts for them come from `/api/permissions`.

Every read goes through the engine's one sample view (`engine.sample.read_sample`, T-027),
which projects the T-019 fold; this module never opens sample files itself. The records store
and the samples root come from the sample seat the server installed on the engine
(`server.app.install_sample_seat`); the open experiment session from `app.state.sessions`.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from ...engine import sample as es
from ...records.layout import check_id
from . import Engine, IsLocal, LocalOnly, Refusal, Sessions, SessionSeat

router = APIRouter()

NO_STORE = Refusal(503, "no_sample_store", "the sample store is not installed on the engine")


# -- response models ----------------------------------------------------------------------------


class GeometryFieldOut(BaseModel):
    key: str
    label: str
    kind: Literal["number", "pair", "choice"]
    unit: str | None
    choices: list[str] | None
    default: float | list[float] | str | None
    safety: bool


class ValueSource(BaseModel):
    kind: Literal["entered", "default", "not_set"]
    by: str | None = None
    t: str | None = None


class GeometryValue(BaseModel):
    value: float | list[float] | str | None
    source: ValueSource


class Geometry(BaseModel):
    values: dict[str, GeometryValue]


class LastSession(BaseModel):
    session_id: str
    opened_at: str | None


class SampleSummary(BaseModel):
    sample_id: str
    created: str | None
    fitted_at: str | None
    closed_loop: bool
    objectives_used: list[str]
    last_session: LastSession | None
    awaiting_return: bool
    #: made by sample_new, no session yet
    reserved: bool


class Hole(BaseModel):
    centre_um: list[float] | None = None
    diameter_mm: float | None = None
    fit_rms_um: float | None = None
    n_points: int | None = None
    arc_deg: float | None = None
    fitted_at: str | None = None
    #: the engine's own words about the fit (hole_loop), e.g. "edge_trace: partial trace (...)"
    status: str | None = None


class Counts(BaseModel):
    #: flags not retired (SampleView.active_flags)
    flags: int
    #: candidates nobody has rejected (SampleView.open_candidates)
    candidates: int
    visits: int
    boundary_points: int


class SampleDetail(SampleSummary):
    dir: str
    hole: Hole | None
    counts: Counts


class StepState(BaseModel):
    done: bool
    by: str | None = None
    t: str | None = None


class ImageStep(StepState):
    ok: bool | None = None
    why: str | None = None
    result_ref: str | None = None


class LoadingState(BaseModel):
    session_id: str | None
    geometry: StepState
    person: StepState
    image: ImageStep
    confirmed: bool


class SampleAccess(BaseModel):
    #: local request and the folder exists (G9)
    can_open_folder: bool
    #: why sample_open / sample_new would be refused now: a session is open for another sample
    open_reason: str | None


# -- helpers ------------------------------------------------------------------------------------


def _seat(eng: Any) -> Any:
    seat = getattr(eng, "sample_seat", None)
    if seat is None:
        raise NO_STORE.http()
    return seat


def _open_session(sessions: SessionSeat) -> tuple[str | None, str | None]:
    """(session_id, sample_id) of the server's open experiment session, or (None, None)."""
    cur = sessions.current
    if cur is None or not getattr(cur, "writable", False):
        return None, None
    return cur.info.session_id, cur.info.sample_id


def _sample_id(sample_id: str) -> str:
    try:
        return check_id(sample_id)
    except ValueError:
        raise Refusal(404, "unknown_sample", f"no sample {sample_id!r}").http() from None


def _view(seat: Any, sample_id: str, sessions: SessionSeat) -> es.SampleView:
    session_id, open_for = _open_session(sessions)
    view = es.read_sample(seat.store, sample_id, Path(seat.samples_root),
                          session_id if open_for == sample_id else None)
    if not view.exists:
        raise Refusal(404, "unknown_sample", f"no sample {sample_id}").http()
    return view


def _folder_created(path: Path) -> str | None:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_ctime))
    except OSError:
        return None


def _summary(view: es.SampleView, samples_root: Path) -> SampleSummary:
    s = view.summary()
    created = s["created"] or _folder_created(samples_root / view.sample_id)
    return SampleSummary(**{**s, "created": created}, reserved=not view.sessions)


def _known_ids(seat: Any) -> list[str]:
    """Legacy sample folders and samples that have sessions: every sample the view can read."""
    ids: set[str] = set()
    root = Path(seat.samples_root)
    if root.is_dir():
        for p in root.iterdir():
            if p.is_dir() and not p.name.startswith(("_", ".")):
                ids.add(p.name)
    for info in seat.store.list_sessions():
        if info.get("sample_id"):
            ids.add(info["sample_id"])
    out = []
    for i in ids:
        try:
            out.append(check_id(i))
        except ValueError:
            continue
    return out


def _hole(view: es.SampleView) -> Hole | None:
    if view.hole is None:
        return None
    h = view.hole
    return Hole(centre_um=h.get("centre_um"), diameter_mm=h.get("diameter_mm"),
                fit_rms_um=h.get("fit_rms_um"), n_points=h.get("n_points"),
                arc_deg=h.get("arc_deg"), fitted_at=h.get("fitted_at"),
                status=view.hole_loop.get("why"))


def default_open_folder(path: Path) -> None:  # pragma: no cover - never run by the tests
    """Open Explorer on the microscope PC. Tests set `app.state.open_folder` to a recorder."""
    if sys.platform != "win32":
        raise OSError("Open folder is implemented for Windows only")
    os.startfile(str(path))  # type: ignore[attr-defined]


def _opener(request: Request) -> Callable[[Path], None]:
    return getattr(request.app.state, "open_folder", None) or default_open_folder


# -- routes (static paths before /{sample_id}) ----------------------------------------------------


@router.get("/list", response_model=list[SampleSummary])
def sample_list(eng: Engine, sessions: Sessions) -> list[SampleSummary]:
    """Every sample, newest first. A reserved sample (sample_new, no session yet) has its id,
    folder and created time from the folder."""
    seat = _seat(eng)
    session_id, open_for = _open_session(sessions)
    root = Path(seat.samples_root)
    out = []
    for sid in _known_ids(seat):
        view = es.read_sample(seat.store, sid, root, session_id if open_for == sid else None)
        if view.exists:
            out.append(_summary(view, root))
    return sorted(out, key=lambda s: s.created or "", reverse=True)


@router.get("/geometry-fields", response_model=list[GeometryFieldOut])
def geometry_fields() -> list[GeometryFieldOut]:
    """The provisional F3.1 field list (engine.sample.GEOMETRY_FIELDS); the screen renders it."""
    return [GeometryFieldOut(key=f.key, label=f.label, kind=f.kind, unit=f.unit,  # type: ignore[arg-type]
                             choices=list(f.choices) if f.choices else None,
                             default=list(f.default) if isinstance(f.default, tuple) else f.default,
                             safety=f.safety)
            for f in es.GEOMETRY_FIELDS]


@router.get("/access", response_model=SampleAccess)
def access(eng: Engine, sessions: Sessions, local: IsLocal,
           sample_id: str | None = None) -> SampleAccess:
    """Sample-specific facts before a click. Role, control, session and remote come from
    /api/permissions, not from here."""
    seat = _seat(eng)
    _, open_for = _open_session(sessions)
    folder_ok = False
    if sample_id:
        sid = _sample_id(sample_id)
        folder_ok = (Path(seat.samples_root) / sid).is_dir()
    open_reason = None
    if open_for is not None and open_for != sample_id:
        open_reason = (f"an experiment session is open for sample {open_for}; close it first "
                       "(one sample per session)")
    return SampleAccess(can_open_folder=local and folder_ok, open_reason=open_reason)


@router.get("/{sample_id}", response_model=SampleDetail)
def sample_detail(sample_id: str, eng: Engine, sessions: Sessions) -> SampleDetail:
    seat = _seat(eng)
    sid = _sample_id(sample_id)
    view = _view(seat, sid, sessions)
    root = Path(seat.samples_root)
    return SampleDetail(**_summary(view, root).model_dump(), dir=str(root / sid), hole=_hole(view),
                        counts=Counts(flags=len(view.active_flags()),
                                      candidates=len(view.open_candidates()),
                                      visits=len(view.visits), boundary_points=len(view.boundary)))


@router.get("/{sample_id}/geometry", response_model=Geometry)
def sample_geometry(sample_id: str, eng: Engine, sessions: Sessions) -> Geometry:
    view = _view(_seat(eng), _sample_id(sample_id), sessions)
    return Geometry(values=view.geometry)


@router.get("/{sample_id}/loading", response_model=LoadingState)
def sample_loading(sample_id: str, eng: Engine, sessions: Sessions) -> LoadingState:
    """The engine's loading state for this sample in the open session (none: all steps open)."""
    view = _view(_seat(eng), _sample_id(sample_id), sessions)
    return LoadingState.model_validate(view.loading)


@router.post("/{sample_id}/open-folder", status_code=204, dependencies=[LocalOnly],
             response_class=Response)
def open_folder(sample_id: str, request: Request, eng: Engine) -> Response:
    """Open the sample folder in Explorer on the microscope PC (G9: any logged-in local user;
    `LocalOnly` refuses a remote request with 403 remote_view). Not an engine op: it writes
    no record."""
    seat = _seat(eng)
    sid = _sample_id(sample_id)
    folder = Path(seat.samples_root) / sid
    if not folder.is_dir():
        raise Refusal(404, "no_folder", f"sample {sid} has no folder").http()
    try:
        _opener(request)(folder)
    except OSError as exc:
        raise Refusal(500, "open_failed", f"could not open the folder: {exc}").http() from exc
    return Response(status_code=204)
