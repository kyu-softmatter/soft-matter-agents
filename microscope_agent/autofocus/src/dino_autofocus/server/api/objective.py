"""The objective area's read routes (T-104; docs/screens/objective.md section 1).

Reads only. Rotating, "Loading done", resume, re-load and the 100x sweep are engine commands
through the common `POST /api/commands`, which refuses everything but `abort` from a remote
origin (`command_why`, D13), so "Loading done" can never come from another PC. Who may press
what is `GET /api/permissions`; this router computes no role, control, session or remote rule.

Everything shown comes from the engine: `snapshot()` (positions, the last `status` summary,
backend info, awaiting_return, running operations, pending confirms) and `plan(cmd)` for the
objective_change plan (T-029). Values that are not measured on the stand carry the engine's
"unmeasured provisional" mark.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ...engine import guards
from ...engine.events import Command
from ...engine.operations import objective_change as oc
from . import Engine, Refusal

router = APIRouter()

Immersion = Literal["dry", "oil", "water"]
OP = "objective_change"
LAB_OFFSET_UM = -60.0  # 100x focus below the 4x focus, 2026-09-30 run log; to be re-measured
LAB_OFFSET_MARK = "lab offset, to be re-measured"


# -- response models --------------------------------------------------------------------


class Pfs(BaseModel):
    enabled: Any = None
    locked: Any = None
    in_range: Any = None


class AwaitingReturn(BaseModel):
    since: Any = None
    return_xy_um: list[float] | None = None
    objective_before: str | None = None


class Running(BaseModel):
    op_id: str
    op: str
    step: int | None = None
    n_steps: int | None = None


class ObjectiveState(BaseModel):
    nosepiece_state: int | None
    label: str | None
    pixel_um: float | None
    z_um: float | None
    pfs: Pfs
    #: the session's immersion-loading record; None until the engine reports one
    immersion_loaded_this_session: dict | None = None
    awaiting_return: AwaitingReturn | None
    running: Running | None
    #: when the lens and PFS were last read (the last `status` run), or None
    read_at: float | None = None


class LensRow(BaseModel):
    nosepiece_state: int
    label: str
    registry_key: str | None
    magnification: float
    na: float | None = None
    immersion: Immersion
    working_distance_um: float | None
    selectable: bool
    disabled_reason: str | None


class PlanStep(BaseModel):
    step: int
    name: str
    target: str = ""


class Escape(BaseModel):
    allowed: bool
    #: the engine's refusal (guards.step_out_target), shown as is
    reason: str | None
    #: "checked at preflight: ..." when the plan could not decide yet
    note: str | None = None
    sign: Literal["+Y", "-Y"]
    dy_um: float | None
    mark: str
    default: bool


class ObjectivePlan(BaseModel):
    steps: list[PlanStep]
    escape: Escape
    immersion: Immersion
    approach_target_um: float
    approach_step_um: float | None
    approach_step_mark: str
    refusal: str | None


class Focus100xDefaults(BaseModel):
    z_4x_focus_um: float | None
    lab_offset_um: float
    lab_offset_mark: str = LAB_OFFSET_MARK
    centre_um: float | None
    half_um: float = 40.0
    step_um: float = 2.0
    fine_half_um: float = 3.0
    fine_step_um: float = 0.2
    exposure_ms: float = 20.0
    metric: Literal["peak", "vollath"] = "peak"
    ceiling_um: float | None
    above_4x_focus: bool
    immersion_loaded_this_session: bool


# -- helpers ----------------------------------------------------------------------------


def _snapshot(eng: Any) -> dict:
    try:
        return eng.snapshot() or {}
    except Exception:  # noqa: BLE001 - a screen read never fails on a missing snapshot
        return {}


def _status(snap: dict) -> dict:
    last = ((snap.get("hardware") or {}).get("last_status") or {})
    return last.get("summary") or {}


def _objectives(snap: dict) -> list[dict]:
    return list((snap.get("backend_info") or {}).get("objectives") or [])


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def _int(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _immersion(key: str | None) -> Immersion:
    return oc.immersion_of(key) or "dry"


def _key(label: str) -> str | None:
    try:
        return guards.registry_key(label)
    except guards.GuardError:
        return None


def _current_state(snap: dict) -> int | None:
    return _int(_status(snap).get("nosepiece_state"))


def _lens_rows(eng: Any, snap: dict) -> list[dict]:
    """The engine's lens options (T-028 `objective_options()`) when it has them. Until then,
    the same facts from the guards tables, with the same reason texts as the preflight."""
    options = getattr(eng, "objective_options", None)
    if callable(options):
        return list(options())
    current = _current_state(snap)
    rows = []
    for o in _objectives(snap):
        key = _key(o.get("label", ""))
        wd = guards.FREE_WD_UM.get(key or "")
        if o.get("state") == current:
            why = "already on that objective"
        elif key is None or key not in guards.OBJECTIVE_LIMITS:
            why = "not in the lens table"
        elif wd is None:
            why = "no working distance value"
        else:
            why = None
        rows.append({"nosepiece_state": o.get("state"), "label": o.get("label", ""),
                     "registry_key": key, "magnification": o.get("magnification") or 0.0,
                     "na": o.get("na"), "immersion": _immersion(key), "working_distance_um": wd,
                     "selectable": why is None, "disabled_reason": why})
    return rows


def _running(snap: dict) -> Running | None:
    for r in snap.get("running") or []:
        if r.get("op") in (OP, "focus_100x"):
            return Running(op_id=r.get("op_id", ""), op=r.get("op", ""),
                           step=_int(r.get("step")), n_steps=_int(r.get("n_steps")))
    return None


def _awaiting(snap: dict) -> AwaitingReturn | None:
    aw = snap.get("awaiting_return")
    if not aw:
        return None
    xy = aw.get("return_xy") or aw.get("return_xy_um")
    return AwaitingReturn(since=aw.get("since") or aw.get("t"),
                          return_xy_um=list(xy) if xy else None,
                          objective_before=aw.get("objective_before"))


def _immersion_record(snap: dict) -> dict | None:
    rec = (snap.get("session") or {}).get("immersion_loaded")
    return rec if isinstance(rec, dict) else None


def ceiling_for(centre_um: float) -> float:
    """focus_100x's sweep ceiling: min(window top, centre + 0.4 x the 100x Oil free WD)."""
    wd = guards.FREE_WD_UM["100x-Oil"]
    return min(guards.SAMPLE_Z_WINDOW_UM[1], centre_um + guards.WD_FRACTION * wd)


# -- routes -----------------------------------------------------------------------------


@router.get("/state", response_model=ObjectiveState)
def state(eng: Engine) -> ObjectiveState:
    snap = _snapshot(eng)
    st = _status(snap)
    current = _current_state(snap)
    label = st.get("nosepiece_label") if isinstance(st.get("nosepiece_label"), str) else None
    pixel = next((_num(o.get("pixel_um")) for o in _objectives(snap) if o.get("state") == current),
                 None)
    last = ((snap.get("hardware") or {}).get("last_status") or {})
    return ObjectiveState(
        nosepiece_state=current, label=label, pixel_um=pixel,
        z_um=_num((snap.get("positions") or {}).get("z_um")),
        pfs=Pfs(enabled=st.get("pfs_enabled"), locked=st.get("pfs_locked"),
                in_range=st.get("pfs_in_range")),
        immersion_loaded_this_session=_immersion_record(snap),
        awaiting_return=_awaiting(snap), running=_running(snap), read_at=_num(last.get("t")))


@router.get("/lenses", response_model=list[LensRow])
def lenses(eng: Engine) -> list[LensRow]:
    return [LensRow(**r) for r in _lens_rows(eng, _snapshot(eng))]


@router.get("/plan", response_model=ObjectivePlan)
def plan(eng: Engine, target_state: int = Query(...), escape: bool | None = Query(None)
         ) -> ObjectivePlan:
    plan_fn = getattr(eng, "plan", None)
    if not callable(plan_fn):
        raise Refusal(503, "no_plan", "this engine cannot plan without starting").http()
    args: dict[str, Any] = {"target_state": target_state}
    if escape is not None:
        args["escape"] = escape
    try:
        out = plan_fn(Command(kind="start", op=OP, args=args))
    except ValueError as e:  # engine.runner.CommandRefused is a ValueError
        raise Refusal(409, "plan_refused", str(getattr(e, "why", e))).http() from e
    p = out.get("plan", out)
    esc = p.get("escape") or {}
    allowed = esc.get("allowed")
    approach = p.get("approach") or {}
    rows = _lens_rows(eng, _snapshot(eng))
    lens = next((r for r in rows if r["nosepiece_state"] == target_state), None)
    dy = _num(esc.get("dy_um"))
    return ObjectivePlan(
        steps=[PlanStep(step=s["step"], name=s.get("text", "")) for s in p.get("steps") or []
               if s.get("runs", True)],
        escape=Escape(
            allowed=allowed is not False,
            reason=esc.get("reason") if allowed is False else None,
            note=esc.get("reason") if allowed is None else None,
            sign="-Y" if esc.get("sign") == "-" else "+Y",
            dy_um=None if dy is None else abs(dy),  # the sign is in `sign`
            mark=esc.get("mark") or guards.PROVISIONAL,
            default=bool(esc.get("default"))),
        immersion=_immersion(p.get("target_key")),
        approach_target_um=_num(approach.get("target_um")) or oc.RETURN_Z_UM,
        approach_step_um=_num(approach.get("step_um")),
        approach_step_mark=approach.get("mark") or guards.PROVISIONAL,
        refusal=lens["disabled_reason"] if lens else "not in the lens table")


@router.get("/focus100x/defaults", response_model=Focus100xDefaults)
def focus100x_defaults(eng: Engine, centre_um: float | None = Query(None)) -> Focus100xDefaults:
    snap = _snapshot(eng)
    # the 4x focus plane at this XY comes from the WP-C focus port; until then it is not set
    z4x = _num((snap.get("focus") or {}).get("z_4x_focus_um"))
    centre = centre_um if centre_um is not None else (None if z4x is None else z4x + LAB_OFFSET_UM)
    rec = _immersion_record(snap)
    return Focus100xDefaults(
        z_4x_focus_um=z4x, lab_offset_um=LAB_OFFSET_UM, centre_um=centre,
        ceiling_um=None if centre is None else ceiling_for(centre),
        above_4x_focus=centre is not None and z4x is not None and centre > z4x,
        immersion_loaded_this_session=bool(rec and rec.get("loaded")))
