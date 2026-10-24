"""The Instruments screens' server side (console card 012; plan.md 15, 15.1): show, draft and stop only.

Everything here is read from the runtime's files or composed on request, and **nothing is sent to an
instrument, written to a tree or saved**: the idle status file, the person's limits and the latest run's
events are read; a plan draft is built from what the person chose, checked against the schema read from
the tree, and returned. The console builds no stand-in for a runtime piece that does not exist yet
(check now, the idle status writer, latest frames), and opens no connection to the live-view host.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ...agents import StoreError, drafts, instruments
from ...agents.schema_lite import SchemaError, Schemas
from ...agents.sma_files import RootNotFoundError, repository_root
from . import AgentStoreDep, Login, Refusal, server_action_why

router = APIRouter()

VIEWER_DRAFT = "This login can only look: it cannot make a plan draft."
REMOTE_DRAFT = "Plan drafts are made at the microscope computer only. This browser is viewing from another computer."


class StatusOut(BaseModel):
    state: Literal["none", "present", "invalid", "unreadable"]
    data: dict[str, Any] | None = Field(default=None, description="the idle status file, as the runtime wrote it and its schema accepted it")
    problems: list[str] = []


class LimitsOut(BaseModel):
    state: Literal["none", "present", "invalid", "unreadable"]
    policy_version: str | None = None
    written_by: str | None = None
    written_at: str | None = None
    piezo: dict[str, dict[str, Any] | None] = Field(default_factory=dict, description="axis -> {min, max} each {value, unit}; None when the file holds no limit")
    tweezers: dict[str, Any] = Field(default_factory=dict)
    problems: list[str] = []


class SentTrapOut(BaseModel):
    trap: str
    x_um: float | None
    y_um: float | None
    strength: float | None
    on: bool | None


class TrapPointOut(BaseModel):
    t_s: float | None
    trap: str
    x_um: float | None
    y_um: float | None


class PiezoPointOut(BaseModel):
    t_s: float | None
    t_wall: str | None
    x_um: float | None
    y_um: float | None
    z_um: float | None
    label: str | None = None


class LatestRunOut(BaseModel):
    state: Literal["ok", "no_run", "runs_not_found"]
    message: str | None = None
    run_id: str | None = None
    started_at: str | None = None
    traps: list[SentTrapOut] = []
    trap_series: list[TrapPointOut] = []
    strength_last_sent: float | None = None
    piezo: list[PiezoPointOut] = []


class DraftIn(BaseModel):
    """What the person chose; nothing else is accepted."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["trap_steps", "aura", "dialamp", "camera_exposure"]
    pattern: Literal["line", "circle", "grid"] | None = None
    objective: Literal["40x", "60x", "100x"] | None = None
    n: int | None = None
    spacing_um: float | None = None
    strength: float | None = None
    color: str | None = None
    power_mw: float | None = None
    state: Literal["on", "off"] | None = None
    intensity_percent: float | None = None
    exposure_ms: float | None = None


class DraftOut(BaseModel):
    kind: str
    card: dict[str, Any]
    valid: bool = Field(description="the schema accepts it and every position and strength is inside the person's limits")
    problems: list[str] = Field(description="what plan.schema.json refuses, as its checker words it")
    range_problems: list[str] = Field(description="what the person's safety file refuses, in words")
    refused_today: list[str]
    saved: Literal[False] = False
    note: str


def _runtime(store: Any):
    fn = getattr(store, "runtime_root", None)
    return fn() if fn is not None else None


def _schemas(store: Any) -> Schemas:
    root = _runtime(store)
    if root is None:
        try:
            root = repository_root()
        except RootNotFoundError:
            root = None
    return Schemas(root / "contracts" / "schemas" if root is not None else "contracts/schemas")


@router.get("/status", response_model=StatusOut)
def status(store: AgentStoreDep) -> StatusOut:
    """The idle status file the runtime writes, as data. Absent: "no status yet", not "nothing connected"."""
    r = instruments.read_idle_status(_runtime(store))
    return StatusOut(state=r.state, data=r.data, problems=r.problems)  # type: ignore[arg-type]


@router.get("/limits", response_model=LimitsOut)
def limits(store: AgentStoreDep) -> LimitsOut:
    """The person's own limits the screens show: the piezo range and the tweezers ranges, from the safety
    file. Never written into code; a limit the file lacks is None."""
    r = instruments.read_limits(_runtime(store))
    if r.state != "present":
        return LimitsOut(state=r.state, problems=r.problems)  # type: ignore[arg-type]
    return LimitsOut(state="present", policy_version=r.policy_version, written_by=r.written_by, written_at=r.written_at,
                     piezo=instruments.piezo_range(r.limits), tweezers=instruments.tweezers_ranges(r.limits))


@router.get("/latest-run", response_model=LatestRunOut)
def latest_run(store: AgentStoreDep) -> LatestRunOut:
    """What the newest microscope run's events say about the tweezers (sent) and the piezo stage (read back)."""
    try:
        return LatestRunOut(**instruments.latest_run_readings(store))
    except StoreError as e:
        raise Refusal(500, "store_error", str(e)).http() from e


def _draft_refusal(me: Any) -> Refusal | None:
    why = server_action_why(me, "draft_plan")
    if why is None:
        return None
    if why.code == "remote_view":
        return Refusal(403, "remote_view", REMOTE_DRAFT)
    if why.code == "role":
        return Refusal(403, "role", VIEWER_DRAFT)
    return why


@router.post("/draft", response_model=DraftOut)
def draft(body: DraftIn, store: AgentStoreDep, me: Login) -> DraftOut:
    """Build a plan draft from the person's choice and check it against plan.schema.json. **It writes nothing:
    the draft is returned and saved nowhere.** Where a console draft goes before signing is still to be designed."""
    if why := _draft_refusal(me):
        raise why.http()
    now = datetime.now(UTC)
    range_problems: list[str] = []
    try:
        if body.kind == "trap_steps":
            card = drafts.trap_steps_card(
                pattern=body.pattern or "line", objective=body.objective or "100x", n=body.n if body.n is not None else 3,
                spacing_um=body.spacing_um if body.spacing_um is not None else 5.0,
                strength=body.strength if body.strength is not None else 0.3, now=now)
            read = instruments.read_limits(_runtime(store))
            ranges = instruments.tweezers_ranges(read.limits) if read.state == "present" else {"positions": {}, "strength": None}
            range_problems = drafts.trap_range_problems(card, ranges)
            if read.state != "present":
                range_problems = ["There is no readable safety file in this tree, so no position or strength can be checked."] + range_problems
            refused = ["Trap count: your safety file has no limit for it yet, so it is refused until you write one.",
                       "Flicker rate: none is sent, and it is refused until a limit exists."]
        else:
            card = drafts.part_card(part=body.kind, fields=body.model_dump(exclude_none=True), now=now)
            refused = ["Refused until you write a limit: your safety file has none for this part yet."]
    except drafts.DraftError as e:
        raise Refusal(422, "invalid", str(e)).http() from e
    try:
        problems = _schemas(store).validate(card, "plan.schema.json")
    except SchemaError as e:
        problems = [f"the draft cannot be checked against plan.schema.json: {e}"]
    return DraftOut(
        kind=body.kind, card=card, valid=not problems and not range_problems, problems=problems[:12],
        range_problems=range_problems, refused_today=refused,
        note="A draft is shown in full and saved nowhere. Where a console draft goes before the person signs it is still to be designed.")
