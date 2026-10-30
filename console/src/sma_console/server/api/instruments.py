"""The Instruments screens' server side (console card 012; plan.md 15, 15.1): show, draft and stop only.

Everything here is read from the runtime's files or composed on request, and **nothing is sent to an
instrument, written to a tree or saved**: the idle status file, the person's limits and the latest run's
events are read; a plan draft is built from what the person chose, checked against the schema read from
the tree, and returned. The console builds no stand-in for a runtime piece that does not exist yet
(check now, the idle status writer, latest frames).

The one connection it opens to the live-view host is [Lights off] (card 023 part 5): one line that can only ask
for less light, sent once to the address this server was started with, and the answer shown as the host gave it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from ...agents import StoreError, drafts, instruments, sma_lights
from ...agents.schema_lite import SchemaError, Schemas
from ...agents.sma_files import RootNotFoundError, repository_root
from . import AgentStoreDep, Login, Refusal, server_action_why

router = APIRouter()

VIEWER_DRAFT = "This login can only look: it cannot make a plan draft."
REMOTE_DRAFT = "Plan drafts are made at the microscope computer only. This browser is viewing from another computer."
RUN_REFUSES = ("The run will refuse this draft even when it is made and signed: the runtime cannot yet match this element "
               "to what software may command.")
AURA_REFUSED_LONGER = "The Aura stays refused longer than the lamp and the camera, until which light engine feeds which channel is settled."


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


class ChannelOut(BaseModel):
    channel: str
    opened: bool = Field(description="the run's last snapshot read this channel")
    detail: str | None = Field(default=None, description="why it is not opened, as the run recorded it")
    backend: str | None = None


class ChannelsOut(BaseModel):
    t_s: float | None = None
    t_wall: str | None = None
    label: str | None = None
    rows: list[ChannelOut] = []


class PathElementOut(BaseModel):
    key: str = Field(description="channel/name, unique in the list")
    name: str = Field(description="the element's name exactly as the read-back gives it")
    channel: str
    state: Literal["read_back", "sent", "not_open", "not_read"] = Field(description="exactly one: a position read back, only sent, the run did not open its channel, or no value could be read")
    value: str | None = Field(default=None, description="what was read, as text; for the blind laser the most dangerous state its commands allow")
    t_wall: str | None = Field(default=None, description="when `value` was read; None where nothing was read")
    reason: str | None = Field(default=None, description="why it is not open or not read, or what a sent state assumes")
    backend: str | None = Field(default=None, description="which backend answered; `mock` is the mock's own state")
    sent: str | None = Field(default=None, description="what was last sent to the channel, as compact text")
    sent_at: str | None = None
    control: Literal["hand", "draft"] | None = Field(default=None, description="moved by hand (no control), or drafted on this page; None for the laser")
    draft: Literal["aura", "dialamp"] | None = Field(default=None, description="the draft kind, where control is `draft`")


class OrderOut(BaseModel):
    state: Literal["none", "read", "not_in_snapshot", "not_understood"] = Field(
        default="none", description="the source has no order, an order, the file's reason for having none, or an order the shape refuses (never drawn in part)")
    data: dict[str, Any] | None = Field(default=None, description="the order exactly as the source wrote it and `light_path_order` in the idle status schema accepted it; None unless `read` or `not_in_snapshot`")
    problems: list[str] = Field(default=[], description="why it is not understood, from the schema's own refusals")


class PathOut(BaseModel):
    order: OrderOut = Field(default=OrderOut(), description="the order light travels, from the same source as the elements: the latest snapshot event, or the status file outside a run")
    source: Literal["run", "status_file", "last_snapshot", "none"] = Field(
        default="none", description="where the elements were read: the run's events, the runtime's status file, or the last run's last snapshot")
    run_id: str | None = None
    kind: str | None = None
    t_wall: str | None = Field(default=None, description="when the snapshot these elements come from was taken")
    written_at: str | None = Field(default=None, description="status file only: when it was written")
    ended_at: str | None = None
    ended_how: str | None = Field(default=None, description="the run's outcome, as the run's own text has it")
    detail: str | None = None
    elements: list[PathElementOut] = []


class LatestRunOut(BaseModel):
    state: Literal["ok", "no_run", "runs_not_found"]
    message: str | None = None
    run_id: str | None = None
    started_at: str | None = None
    running: bool = Field(default=False, description="the run's events file has no run_ended yet")
    ended_how: str | None = None
    ended_at: str | None = None
    plan_id: str | None = None
    frame_tap: bool = Field(default=False, description="running, with a loopback frame tap announced")
    channels: ChannelsOut | None = None
    path: PathOut = PathOut()
    events_seen: int = 0
    traps: list[SentTrapOut] = []
    trap_series: list[TrapPointOut] = []
    strength_last_sent: float | None = None
    piezo: list[PiezoPointOut] = []


class DraftIn(BaseModel):
    """What the person chose; nothing else is accepted."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["trap_steps", "aura", "dialamp", "camera_exposure", "piezo"]
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
    axis: Literal["x", "y", "z"] | None = None
    move: Literal["step", "sine"] | None = None
    target_um: float | None = None
    role: Literal["verify_mapping", "direction_finding", "approach", "return"] | None = None
    centre_um: float | None = None
    amplitude_um: float | None = None
    period_s: float | None = None
    cycles: int | None = None
    points_per_period: int | None = None
    start: Literal["centre", "minimum", "maximum"] | None = None
    return_um: float | None = None
    tolerance_um: float | None = None


class LightSourceOut(BaseModel):
    """One row of the host's reply, as the host gave it (`light_source_row`): the console adds and changes nothing."""

    source: str
    channel: str
    result: Literal["off", "sent", "not_turned_off"]
    read_back: str | None
    reason: str | None = None


class LightsOffOut(BaseModel):
    answer: Literal["done", "stop_sent", "refused", "no_answer", "no_host"] = Field(
        description="the host's own word, or the console's: no_host (nothing was sent) or no_answer (no acceptable reply)")
    how: Literal["own_run", "run_stop"] | None = None
    run_id: str | None = None
    reason: str | None = None
    sources: list[LightSourceOut] = []


class DraftOut(BaseModel):
    kind: str
    card: dict[str, Any]
    valid: bool = Field(description="the schema accepts it and every position and strength is inside the person's limits")
    problems: list[str] = Field(description="what plan.schema.json refuses, as its checker words it")
    range_problems: list[str] = Field(description="what the person's safety file refuses, in words")
    refused_today: list[str]
    saved: Literal[False] = False
    note: str


class PartIn(BaseModel):
    """One of the three parts software may command, as the person filled it in; nothing else is accepted."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["aura", "dialamp", "camera_exposure"]
    color: str | None = None
    power_mw: float | None = None
    state: Literal["on", "off"] | None = None
    intensity_percent: float | None = None
    exposure_ms: float | None = None


class SelectorIn(BaseModel):
    """A slot the person chose for a part moved by hand: a required state, which software never writes."""

    model_config = ConfigDict(extra="forbid")
    element: str
    value: str
    note: str | None = None


class ChangesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parts: list[PartIn] = []
    selectors: list[SelectorIn] = []


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


LIGHTS_OFF_TAKES_NOTHING = ("[Lights off] takes no body and no query: the request is the one line the console builds, "
                            "and nothing the browser sends reaches the host")


@router.post("/lights-off", response_model=LightsOffOut,
             responses={400: {"description": "the request carried a body or a query"},
                        401: {"description": "not logged in"}, 403: {"description": "another computer"}})
async def lights_off(request: Request, store: AgentStoreDep) -> LightsOffOut:
    """Ask the live-view host to turn the lights off: `{"lights_off": true}`, once, and show its answer row by row.

    It can only ask for less light, so it needs no password step and no confirmation. It is an ordinary write, not one
    of the stops: it needs the login any write needs and is refused from another computer. It takes nothing from the request. The host is the one this server was started with
    (`--live-host`, `--live-host-file`), never the live view's default file, and with none given **nothing is sent**.
    A reply the schema refuses is shown as no answer, and nothing is ever resent. It writes nothing."""
    if request.url.query or await request.body():
        raise Refusal(400, "lights_off_takes_nothing", LIGHTS_OFF_TAKES_NOTHING).http()
    state = request.app.state
    addr, why_not = sma_lights.host_to_ask(getattr(state, "live_host", None), getattr(state, "live_host_file", None))
    if addr is None:
        return LightsOffOut(answer="no_host", reason=why_not)
    r = await run_in_threadpool(sma_lights.lights_off, addr, _schemas(store))
    return LightsOffOut(answer=r.answer, how=r.how, run_id=r.run_id, reason=r.reason,  # type: ignore[arg-type]
                        sources=[LightSourceOut(**row) for row in r.sources])


def _draft_refusal(me: Any) -> Refusal | None:
    why = server_action_why(me, "draft_plan")
    if why is None:
        return None
    if why.code == "remote_view":
        return Refusal(403, "remote_view", REMOTE_DRAFT)
    if why.code == "role":
        return Refusal(403, "role", VIEWER_DRAFT)
    return why


SELECTOR_REFUSED = ("A required state is shown at the bench hand-over and set by your hand, then read and compared; "
                    "software never writes it.")


@router.post("/changes", response_model=DraftOut)
def changes(body: ChangesIn, store: AgentStoreDep, me: Login) -> DraftOut:
    """Collect the person's clicks into **one** plan draft and check it against plan.schema.json. Every part is refused
    before signing: no limit has been named for its quantity, and the safety file is not read. **It writes nothing: the draft is returned and saved nowhere.**"""
    if why := _draft_refusal(me):
        raise why.http()
    now = datetime.now(UTC)
    parts = [p.model_dump(exclude_none=True) for p in body.parts]
    try:
        card = drafts.changes_card(parts=parts, selectors=[s.model_dump(exclude_none=True) for s in body.selectors], now=now)
    except drafts.DraftError as e:
        raise Refusal(422, "invalid", str(e)).http() from e
    range_problems = drafts.part_refusals(parts)
    refused: list[str] = []
    if parts:
        refused += ["No limit has been named for these quantities yet, so they are refused before signing.", RUN_REFUSES]
    if any(p["kind"] == "aura" for p in parts):
        refused.append(AURA_REFUSED_LONGER)
    if body.selectors:
        refused.append(SELECTOR_REFUSED)
    try:
        problems = _schemas(store).validate(card, "plan.schema.json")
    except SchemaError as e:
        problems = [f"the draft cannot be checked against plan.schema.json: {e}"]
    return DraftOut(
        kind="changes", card=card, valid=not problems and not range_problems, problems=problems[:12],
        range_problems=range_problems, refused_today=refused,
        note="A draft is shown in full and saved nowhere. Where a console draft goes before the person signs it is still to be designed.")


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
        elif body.kind == "piezo":
            card = drafts.piezo_card(fields=body.model_dump(exclude_none=True), now=now)
            read = instruments.read_limits(_runtime(store))
            ranges = instruments.piezo_range(read.limits) if read.state == "present" else {}
            range_problems = drafts.piezo_range_problems(card, ranges)
            if read.state != "present":
                range_problems = ["There is no readable safety file in this tree, so no position can be checked."] + range_problems
            refused = ["The runtime checks every position against your safety file again before anything is sent."]
        else:
            card = drafts.part_card(part=body.kind, fields=body.model_dump(exclude_none=True), now=now)
            refused = ["No limit has been named for this quantity yet, so this draft is refused before it can be signed.", RUN_REFUSES]
            if body.kind == "aura":
                refused.append(AURA_REFUSED_LONGER)
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
