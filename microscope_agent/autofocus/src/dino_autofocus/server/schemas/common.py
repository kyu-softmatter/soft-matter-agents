"""Shared wire models. These are the one place the API contract is written down: FastAPI turns
them into OpenAPI and the web shell generates its TypeScript types from that.

Each model wraps an engine dataclass; `kind` is a Literal built from the engine's kind list
and `data` stays a dict. Area routers (`server/api/<area>.py`) type their own payloads.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contract import COMMAND_KINDS, EVENT_KINDS, Command, Event

CommandKind = Literal[COMMAND_KINDS]  # type: ignore[valid-type]
EventKind = Literal[EVENT_KINDS]  # type: ignore[valid-type]

# Command fields the browser does not send: the server sets them from the request and its
# own state. Who (user_id, from the login cookie, T-018), where (remote: a non-loopback
# client, D13), with what right (control_grant, from the operator's control, T-018), in which
# experiment session (session_id, the one the server opened, T-019), and the assistant's
# provenance (origin, proposal_id, conversation_id, confirmed_by: set only by the assistant
# routes, T-013, from the proposal card; this endpoint is the human path). t is when the
# server received it.
SERVER_STAMPED = ("origin", "user_id", "session_id", "proposal_id", "conversation_id",
                  "confirmed_by", "remote", "control_grant", "t")


class CommandIn(BaseModel):
    """A command for the engine, as the browser sends it. `start` names an operation in `op`
    with its `args`; `abort`, `confirm` and `update` name the running operation by `op_id`;
    `approve` / `reject` name a proposal by `op_id`; `lights_off` pre-empts anything. Any
    other field is refused (422): the server sets the rest (see SERVER_STAMPED)."""

    model_config = ConfigDict(extra="forbid")

    kind: CommandKind
    op: str = ""
    op_id: str = ""
    args: dict[str, Any] = Field(default_factory=dict)

    def to_engine(
        self, *, remote: bool, user_id: str | None = None, session_id: str | None = None,
        control_grant: str | None = None,
    ) -> Command:
        """The caller (server) passes what it knows about the request; until login and
        sessions are wired in (T-009b) user_id, session_id and control_grant stay None."""
        return Command(kind=self.kind, op=self.op, op_id=self.op_id, args=dict(self.args),
                       origin="human", user_id=user_id, session_id=session_id,
                       remote=remote, control_grant=control_grant, t=time.time())


class CommandAccepted(BaseModel):
    op_id: str


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


class WsCommand(BaseModel):
    """`/ws/events`, client -> server. Accepted only from the microscope PC (loopback)."""

    type: Literal["command"] = "command"
    command: CommandIn


class WsAccepted(BaseModel):
    """`/ws/events`, server -> client: reply to a `WsCommand`."""

    type: Literal["accepted"] = "accepted"
    op_id: str


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
    #: a live focus score of this frame (`focus_metric`, scale invariant), computed on the
    #: binned frame sent here, so it follows the focus but is not a sweep score; null when
    #: it could not be computed
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


WS_MODELS: tuple[type[BaseModel], ...] = (WsEvent, WsCommand, WsAccepted, WsError, WsLock,
                                          WsFrame)
