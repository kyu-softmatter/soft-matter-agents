"""The `map` area (PLAN.md F4): reads for the sample map screen and its D16 record writes.

Contract: docs/screens/map.md. The server reads; it never moves anything. Motion and scans go
through `POST /api/commands` like every other engine command; this router only adds

- reads of the sample view (T-027 `read_sample` over `records.events.fold`, the one fold) and
  of the scan results in the legacy samples root, including the mosaic as a PNG;
- the four D16 writes (flag write / retire, candidate confirm / reject). `/api/commands` refuses
  them (`map_route`), so the check lives here: `server_action_why` (WRITE_MAP_FLAG, loopback,
  login) first, then the engine's own check (control, open experiment session) on submit.

Area rule kept here: the scan box of a result (`allowed_box_um` = box + 1 mm) when the scan
record does not carry it yet (docs/screens/map.md G6). Everything else (role, control, session,
remote) comes from the shared rules in `server/api/__init__.py` and the engine.
"""

from __future__ import annotations

import io
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ...engine.sample import SampleView, read_sample
from ..schemas import ApiError, CommandAccepted
from ..schemas.common import CommandIn
from . import MAP_WRITE_OPS, Auth, Engine, Login, Refusal, Sessions, server_action_why

router = APIRouter()

XY_BOX_MARGIN_UM = 1000.0  # scan box + 1 mm: the click-move limit (operations-spec 3, 6.3)
MOSAIC_MAX_PX = 2048
MOSAIC_PERCENTILES = (0.5, 99.8)  # scripts/plot_scan.py
RESULT_PREFIXES = {"scan4x_": "scan_4x", "sample_map_": "sample_map"}
_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

REFUSALS = {400: {"model": ApiError}, 401: {"model": ApiError}, 403: {"model": ApiError},
            404: {"model": ApiError}, 409: {"model": ApiError}, 423: {"model": ApiError},
            503: {"model": ApiError}}


# -- response models (docs/screens/map.md section 2) ------------------------------------


class Box(BaseModel):
    x0: float
    x1: float
    y0: float
    y1: float


class BoundaryPoint(BaseModel):
    x_um: float
    y_um: float
    t: float | None = None


class HoleFit(BaseModel):
    centre_um: tuple[float, float]
    diameter_mm: float
    fit_rms_um: float | None = None
    n_points: int | None = None
    arc_deg: float | None = None
    fitted_at: float | None = None  # epoch seconds
    closed_loop: bool = False  # T-027 hole_loop: a partial trace cannot be scanned
    loop_why: str = ""


class Visit(BaseModel):
    x_um: float
    y_um: float
    w_um: float
    h_um: float
    verdict: str | None = None
    source: str | None = None


class MapState(BaseModel):
    sample_id: str
    boundary: list[BoundaryPoint]
    hole: HoleFit | None
    expected_diameter_mm: float | None
    visits: list[Visit]
    scan_box_um: Box | None
    allowed_box_um: Box | None
    session_started_at: float | None  # the open experiment session's start, epoch seconds


class ResultSummary(BaseModel):
    result_id: str
    kind: str  # scan_4x | sample_map
    started: float | None
    finished: float | None
    light: str | None
    n_tiles: int
    grid_n: int
    has_mosaic: bool
    scan_box_um: Box | None
    allowed_box_um: Box | None


class Tile(BaseModel):
    name: str
    row: int
    col: int
    x_um: float
    y_um: float
    z_focus_um: float | None  # classical focus at the encoder read-back, not a model value
    focus_note: str = ""
    block_z_um: list[float | None] = Field(default_factory=list)
    blocks_per_side: int = 6
    dropout_z_um: list[float] = Field(default_factory=list)


class MosaicExtent(Box):
    um_per_px: float
    bin: int


class ResultDetail(ResultSummary):
    tiles: list[Tile]
    fov_um: float | None
    um_per_px: float | None
    mosaic: MosaicExtent | None


class HistoryEntry(BaseModel):
    """One step of a flag or candidate, from the fold (T-027c): who, when, what."""

    kind: str  # flag_set | flag_remove | particle
    by: str | None = None
    at: float | None = None  # epoch seconds
    status: str | None = None  # particle steps: candidate | confirmed | rejected


class Flag(BaseModel):
    flag_id: str
    name: str
    note: str = ""
    t: float | None
    objective: str | None = None
    x_um: float
    y_um: float
    z_um: float | None = None  # ZDrive read-back when the flag was set
    replaces: str | None = None
    retired: bool = False
    retired_at: float | None = None
    retired_by: str | None = None
    history: list[HistoryEntry] = Field(default_factory=list)


class Candidate(BaseModel):
    candidate_id: str
    x_um: float
    y_um: float
    source: str  # classical_candidate | person_confirmed | person_rejected
    score: float | None = None
    result_id: str | None = None
    decides: str | None = None
    t: float | None
    by: str | None = None  # who decided (confirmed / rejected), from history
    decided_at: float | None = None
    history: list[HistoryEntry] = Field(default_factory=list)


class FlagIn(BaseModel):
    x_um: float
    y_um: float
    name: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=500)
    replaces: str | None = None  # a note edit is a new flag that replaces the old one


class DecisionIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


# -- the one reader ---------------------------------------------------------------------


def _refuse(status: int, code: str, message: str) -> HTTPException:
    return Refusal(status, code, message).http()


def _check_id(value: str, what: str) -> str:
    if not _ID.match(value) or value in (".", ".."):
        raise _refuse(404, "not_found", f"no {what} {value!r}")
    return value


def _seat(eng: Any) -> Any:
    seat = getattr(eng, "sample_seat", None)
    if seat is None:
        raise _refuse(503, "no_records", "the sample store is not installed on the engine")
    return seat


def sample_view(eng: Any, sample_id: str) -> tuple[SampleView, Path]:
    """The one place this router reads sample state: T-027's projection of the fold, plus the
    legacy root where the scan results live. A storage change is a change here only."""
    seat = _seat(eng)
    sid = _check_id(sample_id, "sample")
    session_id = ((_snapshot(eng).get("session") or {}).get("session_id"))
    view = read_sample(seat.store, sid, Path(seat.samples_root), session_id=session_id)
    if not view.exists:
        raise _refuse(404, "not_found", f"no sample {sid!r}")
    return view, Path(seat.samples_root) / sid


def _snapshot(eng: Any) -> dict[str, Any]:
    try:
        snap = eng.snapshot()
    except Exception:  # an engine that cannot answer is not a reason to hide the map
        return {}
    return snap if isinstance(snap, dict) else {}


# -- small converters -------------------------------------------------------------------


def _epoch(t: Any) -> float | None:
    if t is None:
        return None
    if isinstance(t, (int, float)):
        return float(t)
    try:
        d = datetime.fromisoformat(str(t))
    except ValueError:
        return None
    return (d if d.tzinfo else d.astimezone()).timestamp()


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _box(d: Any) -> Box | None:
    if isinstance(d, dict) and all(_num(d.get(k)) is not None for k in ("x0", "x1", "y0", "y1")):
        return Box(**{k: float(d[k]) for k in ("x0", "x1", "y0", "y1")})
    return None


def _hole(h: dict[str, Any] | None, loop: dict[str, Any]) -> HoleFit | None:
    if not h or _num(h.get("diameter_mm")) is None:
        return None
    c = h.get("centre_um") or h.get("centre") or (None, None)
    cx, cy = (_num(c[0]), _num(c[1])) if len(c) == 2 else (None, None)
    if cx is None or cy is None:
        return None
    n = _num(h.get("n_points"))
    return HoleFit(centre_um=(cx, cy), diameter_mm=float(h["diameter_mm"]),
                   fit_rms_um=_num(h.get("fit_rms_um", h.get("rms_um"))),
                   n_points=None if n is None else int(n), arc_deg=_num(h.get("arc_deg")),
                   fitted_at=_epoch(h.get("fitted_at")), closed_loop=bool(loop.get("closed")),
                   loop_why=str(loop.get("why") or ""))


def _visit(v: dict[str, Any]) -> Visit | None:
    x, y = _num(v.get("x_um")), _num(v.get("y_um"))
    if x is None or y is None:
        return None
    w = _num(v.get("w_um")) or _num(v.get("fov_um")) or 0.0
    h = _num(v.get("h_um")) or w
    verdict, source = v.get("verdict"), v.get("source")
    return Visit(x_um=x, y_um=y, w_um=w, h_um=h,
                 verdict=verdict if isinstance(verdict, str) else None,
                 source=source if isinstance(source, str) else None)


def _history(rec: dict[str, Any]) -> list[HistoryEntry]:
    out = []
    for h in rec.get("history") or []:
        if isinstance(h, dict):
            st = h.get("status")
            out.append(HistoryEntry(kind=str(h.get("kind") or ""), by=h.get("by"),
                                    at=_epoch(h.get("at")),
                                    status=st if isinstance(st, str) else None))
    return out


def _last(hist: list[HistoryEntry], kind: str, status: str | None = None) -> HistoryEntry | None:
    return next((h for h in reversed(hist)
                 if h.kind == kind and (status is None or h.status == status)), None)


def _flag(fid: str, f: dict[str, Any]) -> Flag | None:
    x, y = _num(f.get("x_um")), _num(f.get("y_um"))
    if x is None or y is None:
        return None
    hist = _history(f)
    retired = bool(f.get("retired"))
    gone = _last(hist, "flag_remove") if retired else None
    return Flag(flag_id=fid, name=str(f.get("name") or fid), note=str(f.get("note") or ""),
                t=_epoch(f.get("t")), objective=f.get("objective"), x_um=x, y_um=y,
                z_um=_num(f.get("z_um")), replaces=f.get("replaces"), retired=retired,
                retired_at=gone.at if gone else None, retired_by=gone.by if gone else None,
                history=hist)


_SOURCE = {"candidate": "classical_candidate", "confirmed": "person_confirmed",
           "rejected": "person_rejected"}


def _candidate(pid: str, p: dict[str, Any]) -> Candidate | None:
    x, y = _num(p.get("x_um")), _num(p.get("y_um"))
    if x is None or y is None:
        return None
    status = str(p.get("status") or "candidate")
    source = _SOURCE.get(status, "classical_candidate")
    hist = _history(p)
    decided = None if source == "classical_candidate" else _last(hist, "particle", status)
    return Candidate(candidate_id=pid, x_um=x, y_um=y, source=source, score=_num(p.get("score")),
                     result_id=p.get("result_id"), decides=p.get("decides"), t=_epoch(p.get("t")),
                     by=decided.by if decided else None,
                     decided_at=decided.at if decided else None, history=hist)


# -- scan results in the legacy root ----------------------------------------------------


def _result_kind(name: str) -> str | None:
    return next((k for p, k in RESULT_PREFIXES.items() if name.startswith(p)), None)


def _result_record(d: Path) -> dict[str, Any]:
    for name in ("summary.json", "scan.json"):
        p = d / name
        if p.is_file():
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(rec, dict):
                return rec
    return {}


def _boxes(rec: dict[str, Any]) -> tuple[Box | None, Box | None]:
    """The record's own boxes when it has them; else from the hole and margin the scan used
    (operations-spec 3절 2항: half = diameter_mm * 500 + margin_um, guard box + 1 mm)."""
    scan, allowed = _box(rec.get("scan_box_um")), _box(rec.get("allowed_box_um"))
    if scan is not None and allowed is not None:
        return scan, allowed
    hole = rec.get("hole") or {}
    c, dia = hole.get("centre_um"), _num(hole.get("diameter_mm"))
    if not c or len(c) != 2 or dia is None or _num(c[0]) is None or _num(c[1]) is None:
        return scan, allowed
    half = dia * 500.0 + (_num(rec.get("margin_um")) or 500.0)
    cx, cy = float(c[0]), float(c[1])
    scan = scan or Box(x0=cx - half, x1=cx + half, y0=cy - half, y1=cy + half)
    h2 = half + XY_BOX_MARGIN_UM
    allowed = allowed or Box(x0=cx - h2, x1=cx + h2, y0=cy - h2, y1=cy + h2)
    return scan, allowed


def _mosaic_meta(d: Path) -> dict[str, Any] | None:
    meta, npy = d / "mosaic.json", d / "mosaic.npy"
    if not (meta.is_file() and npy.is_file()):
        return None
    try:
        m = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return m if isinstance(m, dict) else None


def _summary(d: Path, rec: dict[str, Any]) -> ResultSummary:
    scan, allowed = _boxes(rec)
    tiles = rec.get("tiles") or []
    grid_n = rec.get("grid_n")
    return ResultSummary(
        result_id=d.name, kind=_result_kind(d.name) or "scan_4x",
        started=_epoch(rec.get("started")), finished=_epoch(rec.get("finished")),
        light=rec.get("light") if isinstance(rec.get("light"), str) else None,
        n_tiles=len(tiles) if isinstance(tiles, list) else 0,
        grid_n=int(grid_n) if isinstance(grid_n, (int, float)) else 0,
        has_mosaic=_mosaic_meta(d) is not None, scan_box_um=scan, allowed_box_um=allowed)


def _stamp(d: Path) -> str:
    return next((d.name[len(p):] for p in RESULT_PREFIXES if d.name.startswith(p)), d.name)


def _results(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir() and _result_kind(p.name)]
    return sorted(dirs, key=_stamp, reverse=True)  # newest first, scan_4x and sample_map mixed


def _result_dir(root: Path, result_id: str) -> Path:
    rid = _check_id(result_id, "result")
    d = root / rid
    if _result_kind(rid) is None or not d.is_dir():
        raise _refuse(404, "not_found", f"no result {rid!r}")
    return d


def _tile(t: dict[str, Any]) -> Tile | None:
    x, y = _num(t.get("x_um")), _num(t.get("y_um"))
    if x is None or y is None:
        return None
    dropouts = (_num(z) for z in t.get("dropout_z_um") or [])
    return Tile(name=str(t.get("name") or ""), row=int(t.get("row") or 0),
                col=int(t.get("col") or 0), x_um=x, y_um=y, z_focus_um=_num(t.get("z_focus_um")),
                focus_note=str(t.get("focus_note") or ""),
                block_z_um=[_num(b) for b in t.get("block_z_um") or []],
                blocks_per_side=int(t.get("blocks_per_side") or 6),
                dropout_z_um=[f for f in dropouts if f is not None])


def _extent(m: dict[str, Any] | None) -> MosaicExtent | None:
    if m is None or _box(m) is None or _num(m.get("um_per_px")) is None:
        return None
    return MosaicExtent(**_box(m).model_dump(), um_per_px=float(m["um_per_px"]),
                        bin=int(_num(m.get("bin")) or 1))


def mosaic_png(mosaic: np.ndarray, max_px: int = MOSAIC_MAX_PX) -> bytes:
    """An 8-bit grey PNG with +x to the right and +y up. `mosaic.npy` is assembled as in
    plot_scan.py: tiles already flipped by the sign of M, row 0 = y0. So only the row order is
    reversed here; M is not applied a second time (docs/screens/map.md section 2)."""
    from PIL import Image

    a = np.asarray(mosaic, dtype=np.float64)
    if a.ndim != 2 or a.size == 0:
        raise ValueError("mosaic is not a 2-D image")
    step = max(1, math.ceil(max(a.shape) / max(1, max_px)))
    a = a[::step, ::step]
    filled = a[a > 0]
    lo, hi = (np.percentile(filled, MOSAIC_PERCENTILES) if filled.size else (0.0, 1.0))
    if hi <= lo:
        hi = lo + 1.0
    img = np.clip((a - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
    img[a <= 0] = 0  # empty mosaic cells stay black
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(np.flipud(img))).save(buf, format="PNG")
    return buf.getvalue()


# -- read routes (everyone who may read: the shared access rules apply) ------------------


@router.get("/{sample_id}", response_model=MapState, responses=REFUSALS)
def map_state(sample_id: str, eng: Engine) -> MapState:
    view, root = sample_view(eng, sample_id)
    latest = next(iter(_results(root)), None)
    scan, allowed = _boxes(_result_record(latest)) if latest else (None, None)
    started = (_snapshot(eng).get("session") or {}).get("started_at")
    return MapState(
        sample_id=view.sample_id,
        boundary=[BoundaryPoint(x_um=float(p["x_um"]), y_um=float(p["y_um"]), t=_epoch(p.get("t")))
                  for p in view.boundary
                  if _num(p.get("x_um")) is not None and _num(p.get("y_um")) is not None],
        hole=_hole(view.hole, view.hole_loop),
        expected_diameter_mm=_num((view.geometry.get("hole_diameter_mm") or {}).get("value")),
        visits=[v for v in (_visit(x) for x in view.visits) if v is not None],
        scan_box_um=scan, allowed_box_um=allowed, session_started_at=_epoch(started))


@router.get("/{sample_id}/results", response_model=list[ResultSummary], responses=REFUSALS)
def results(sample_id: str, eng: Engine) -> list[ResultSummary]:
    _, root = sample_view(eng, sample_id)
    return [_summary(d, _result_record(d)) for d in _results(root)]


@router.get("/{sample_id}/results/{result_id}", response_model=ResultDetail, responses=REFUSALS)
def result(sample_id: str, result_id: str, eng: Engine) -> ResultDetail:
    _, root = sample_view(eng, sample_id)
    d = _result_dir(root, result_id)
    rec = _result_record(d)
    tiles = [t for t in (_tile(x) for x in rec.get("tiles") or [] if isinstance(x, dict)) if t]
    return ResultDetail(**_summary(d, rec).model_dump(), tiles=tiles,
                        fov_um=_num(rec.get("fov_um")), um_per_px=_num(rec.get("um_per_px")),
                        mosaic=_extent(_mosaic_meta(d)))


@router.get("/{sample_id}/results/{result_id}/mosaic.png", responses={
    200: {"content": {"image/png": {}}}, **REFUSALS})
def mosaic(sample_id: str, result_id: str, eng: Engine,
           max_px: int = Query(MOSAIC_MAX_PX, ge=64, le=8192)) -> Response:
    _, root = sample_view(eng, sample_id)
    d = _result_dir(root, result_id)
    meta = _mosaic_meta(d)
    if meta is None:
        raise _refuse(404, "no_mosaic", f"{result_id} has no mosaic")
    if meta.get("orientation") != "stage":
        # without it the server cannot tell whether the tiles were already flipped by M
        raise _refuse(409, "mosaic_orientation",
                      "mosaic.json does not say orientation 'stage'; not guessing the flip")
    try:
        png = mosaic_png(np.load(d / "mosaic.npy", allow_pickle=False), max_px)
    except (OSError, ValueError) as e:
        raise _refuse(409, "mosaic_unreadable", f"mosaic.npy: {e}") from e
    return Response(png, media_type="image/png")


@router.get("/{sample_id}/flags", response_model=list[Flag], responses=REFUSALS)
def flags(sample_id: str, eng: Engine, include_retired: bool = False) -> list[Flag]:
    view, _ = sample_view(eng, sample_id)
    shown = view.flags if include_retired else view.active_flags()  # T-027c: what is in play
    return [f for f in (_flag(k, v) for k, v in shown.items()) if f is not None]


@router.get("/{sample_id}/candidates", response_model=list[Candidate], responses=REFUSALS)
def candidates(sample_id: str, eng: Engine, include_rejected: bool = False) -> list[Candidate]:
    view, _ = sample_view(eng, sample_id)
    # T-027c: open_candidates() leaves out rejected ones; confirmed particles are drawn filled
    shown = {**(view.candidates if include_rejected else view.open_candidates()),
             **view.confirmed_particles}
    return [c for c in (_candidate(k, v) for k, v in shown.items()) if c is not None]


# -- D16 writes: local operator, then the engine (control, open session) ----------------


def _submit(op: str, args: dict[str, Any], eng: Any, me: Any, seat: Any,
            sessions: Any) -> CommandAccepted:
    assert op in MAP_WRITE_OPS
    if why := server_action_why(me, op):
        raise why.http()
    session = getattr(sessions, "current", None)
    session_id = session.info.session_id if session is not None else None
    cmd = CommandIn(kind="start", op=op, args=args)
    try:
        op_id = eng.submit(cmd.to_engine(remote=not me.local, user_id=me.user_id,
                                         session_id=session_id,
                                         control_grant=seat.grant_for(me.info)))
    except ValueError as e:  # runner.CommandRefused: no session, no control, ...
        raise _refuse(400, "refused", str(e)) from e
    return CommandAccepted(op_id=op_id)


@router.post("/{sample_id}/flags", response_model=CommandAccepted, responses=REFUSALS)
def add_flag(sample_id: str, body: FlagIn, eng: Engine, me: Login, seat: Auth,
             sessions: Sessions) -> CommandAccepted:
    sid = _check_id(sample_id, "sample")
    args = {"sample_id": sid, "x_um": body.x_um, "y_um": body.y_um, "name": body.name,
            "note": body.note, "replaces": body.replaces}
    return _submit("map_flag", args, eng, me, seat, sessions)


@router.post("/{sample_id}/flags/{flag_id}/retire", response_model=CommandAccepted,
             responses=REFUSALS)
def retire_flag(sample_id: str, flag_id: str, eng: Engine, me: Login,
                seat: Auth, sessions: Sessions) -> CommandAccepted:
    args = {"sample_id": _check_id(sample_id, "sample"), "flag_id": _check_id(flag_id, "flag")}
    return _submit("map_flag_retire", args, eng, me, seat, sessions)


@router.post("/{sample_id}/candidates/{candidate_id}/confirm", response_model=CommandAccepted,
             responses=REFUSALS)
def confirm_candidate(sample_id: str, candidate_id: str, eng: Engine,
                      me: Login, seat: Auth, sessions: Sessions,
                      body: DecisionIn | None = None) -> CommandAccepted:
    args = {"sample_id": _check_id(sample_id, "sample"),
            "candidate_id": _check_id(candidate_id, "candidate"),
            "note": body.note if body else None}
    return _submit("candidate_confirm", args, eng, me, seat, sessions)


@router.post("/{sample_id}/candidates/{candidate_id}/reject", response_model=CommandAccepted,
             responses=REFUSALS)
def reject_candidate(sample_id: str, candidate_id: str, eng: Engine,
                     me: Login, seat: Auth, sessions: Sessions,
                     body: DecisionIn | None = None) -> CommandAccepted:
    args = {"sample_id": _check_id(sample_id, "sample"),
            "candidate_id": _check_id(candidate_id, "candidate"),
            "note": body.note if body else None}
    return _submit("candidate_reject", args, eng, me, seat, sessions)
