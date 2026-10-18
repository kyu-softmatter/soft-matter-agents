"""Shared wire models. These are the one place the API contract is written down: FastAPI turns
them into OpenAPI and the web shell generates its TypeScript types from that.

Each model wraps a dataclass of `contract.py`; `kind` is a Literal built from its kind list
and `data` stays a dict. Area routers (`server/api/<area>.py`) type their own payloads.

No command model is here (soft-matter-agents card 077): the console sends no command to any
engine, so `CommandIn`, `CommandAccepted`, `WsCommand` and `WsAccepted` went with
`/api/commands` and the command messages on `/ws/events`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .contract import EVENT_KINDS, Event

EventKind = Literal[EVENT_KINDS]  # type: ignore[valid-type]


class EventOut(BaseModel):
    """`user_id` / `session_id` are the operation's (rule 12); None for engine-wide events."""

    kind: EventKind
    op_id: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    t: float
    user_id: str | None = None
    session_id: str | None = None

    @classmethod
    def from_engine(cls, ev: Event) -> EventOut:
        return cls(kind=ev.kind, op_id=ev.op_id, data=ev.data, t=ev.t, user_id=ev.user_id,
                   session_id=ev.session_id)


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    engine: str
    remote_view: bool
    remote_abort: bool  # D13: a remote viewer may send abort, and nothing else


class RefusalDetail(BaseModel):
    """Why the server said no. `code` is also in the `X-DinoAF-Refusal` header. Codes:
    login_required (401), locked (423), remote_view (403; the web client turns read-only
    on this one only), foreign_origin, map_route, role (403), refused (400, the engine said
    no), shutting_down (503), shutdown_failed (500)."""

    code: str
    message: str


class ApiError(BaseModel):
    detail: RefusalDetail


class ShutdownIn(BaseModel):
    reason: str = "api"


class ShutdownAccepted(BaseModel):
    """The engine has stopped (abort, lights off with readback, records finished); the server
    exits next. `already` is true when another exit path had stopped the engine first."""

    reason: str
    already: bool


# --- WebSocket messages (not REST routes; added to the OpenAPI components by app.py) ---


class WsEvent(BaseModel):
    """`/ws/events`, server -> client."""

    type: Literal["event"] = "event"
    event: EventOut


class WsError(BaseModel):
    """`/ws/*`, server -> client: a refused or malformed message. `status` and `code` follow
    the REST refusals (401 login_required, 423 locked, 403 remote_view and others, 400
    refused by the engine, 422 bad message, 503 shutting_down). A 401/423 on connect is
    followed by a close."""

    type: Literal["error"] = "error"
    status: int
    detail: str
    code: str | None = None


class WsLock(BaseModel):
    """`/ws/events`, server -> client: the login's lock state, sent once on connect and on
    every change. While `locked`, no `event` messages are sent (command replies still are,
    since stops are allowed); after unlock the client reloads `/api/state` (T-009c, D14)."""

    type: Literal["lock"] = "lock"
    locked: bool


class FocusDz(BaseModel):
    """The live -10..+10 gauge's reading (engine/live_dz.py): dz = stage - best focus in depths
    of field, 0 = in focus. Display only."""

    #: null: nothing readable in view (`note` says why)
    dz_dof: float | None = None
    #: the reading's one-sigma spread, DoF; null for the mock's truth
    sigma_dof: float | None = None
    #: "mock_truth" (the mock world's own z, not a measurement) or "model" (a DINO head)
    source: Literal["mock_truth", "model"]
    note: str = ""
    #: false when |dz| is within sigma: the side of focus is not known
    sign_known: bool = False


class WsFrame(BaseModel):
    """`/ws/frames`, server -> client. Always sent as a text message immediately followed by
    one binary message holding the JPEG (`jpeg_bytes` long). Pixel values were mapped
    linearly from `display_min..display_max` (raw counts) to 0..255."""

    type: Literal["frame"] = "frame"
    seq: int
    t: float
    width: int
    height: int
    binning: int
    source_width: int
    source_height: int
    display_min: float
    display_max: float
    jpeg_bytes: int
    #: the camera label (e.g. "Kinetix_blue"); null when the engine names none. With two
    #: cameras both arrive on the same socket, told apart by this field.
    camera: str | None = None
    #: always null since soft-matter-agents card 077: a focus score is a measurement, and the
    #: console measures nothing. It was computed here from the binned frame; it stays with the
    #: engine side, and a frame statistic for a run comes from the runtime by a later card
    focus_score: float | None = None
    focus_metric: str | None = None
    #: the signed gauge reading of this frame (`meta.focus_dz` from the engine); null when the
    #: engine has none (no head loaded and no mock truth)
    focus_dz: FocusDz | None = None
    #: how `t` was taken. "software": the host clock when the frame was popped from the camera
    #: buffer. Two cameras' frames are paired by arrival, not by a hardware trigger, so a merged
    #: or side-by-side view is display only: no timing, correlation or coincidence analysis may
    #: be read off it (soft-matter-agents plan.md 4.6.9: physics never from a software timestamp;
    #: simultaneous capture is a hardware-triggered plan there).
    time_base: Literal["software"] = "software"
    meta: dict[str, Any] = Field(default_factory=dict)


WS_MODELS: tuple[type[BaseModel], ...] = (WsEvent, WsError, WsLock, WsFrame)
