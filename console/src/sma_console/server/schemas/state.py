"""`GET /api/state` and `GET /api/permissions`, typed so the web side gets generated types.

The shapes follow `engine/runner.py` (`Runner.snapshot`, `_Op.public`, the one light payload,
`backend.Positions`). Every model allows extra keys, so a field the engine adds reaches the
browser before it is typed here; a field typed here with the wrong shape fails loudly.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class Positions(_Open):
    """Stage readback in um; None where the read failed, with the reason in `errors`."""

    x_um: float | None = None
    y_um: float | None = None
    z_um: float | None = None
    piezo_um: dict[str, float] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    t: float | None = None


class LampState(_Open):
    state: str = "unknown"  # "on" | "off" | "unknown"
    intensity: float | None = None


class AuraState(_Open):
    state: str = "unknown"
    lines: dict[str, float | None] = Field(default_factory=dict)  # line -> percent


class Lights(_Open):
    """The one light shape (light_changed, snapshot, records)."""

    dialamp: LampState = Field(default_factory=LampState)
    aura: AuraState = Field(default_factory=AuraState)
    verified: bool | None = None
    records: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class OpSummary(_Open):
    op_id: str
    op: str
    state: str
    origin: str = "human"
    user_id: str | None = None
    session_id: str | None = None
    proposal_id: str | None = None
    conversation_id: str | None = None
    confirmed_by: str | None = None
    confirmed_at: float | None = None
    record_prefix: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    why: str = ""
    last_progress: dict[str, Any] | None = None


class SessionRef(_Open):
    session_id: str | None = None
    started_at: float | None = None


class SampleRef(_Open):
    sample_id: str | None = None
    reserved: bool = False
    session_id: str | None = None


class StateGateRow(_Open):
    """One feature gate (T-028 `gates.gate_rows`): off rows come first. Named apart from
    `server/api/hardware.GateRow` so the OpenAPI keeps both names short."""

    op: str
    enabled: bool
    reasons: list[str] = Field(default_factory=list)
    requires: Any = None


GateRow = StateGateRow  # the old import name


class HardwareState(_Open):
    """`snapshot()["hardware"]`: the T-028 provider's block plus the runner's last_status.
    Without a provider the runner sends `gates: {}`, hence the dict."""

    profile: dict[str, Any] | None = None
    profile_path: str | None = None
    sha256: str | None = None
    previous: dict[str, Any] | None = None
    gates: list[StateGateRow] | dict[str, Any] = Field(default_factory=list)
    objective_options: list[dict[str, Any]] = Field(default_factory=list)
    last_status: dict[str, Any] | None = None
    error: str | None = None


class TrapOut(_Open):
    index: int
    on: bool
    x_um: float
    y_um: float
    z_um: float = 0.0
    power_pct: float | None = None


class TweezersState(_Open):
    """`snapshot()["tweezers"]` (engine/tweezers.py `state_of`); null when there are none."""

    kind: str
    n_traps: int
    bench: bool = True
    notes: dict[str, str] | None = None
    traps: list[TrapOut] = Field(default_factory=list)
    error: str | None = None


class PiezoPositionOut(_Open):
    x_um: float
    y_um: float
    z_um: float


class PiezoStateOut(_Open):
    """`snapshot()["piezo"]` (engine/piezo.py `piezo_state_of`): the piezo patterns may move;
    null on the stand (read only until M5)."""

    kind: str
    travel_um: dict[str, list[float]] = Field(default_factory=dict)
    bench: bool = True
    position: PiezoPositionOut | None = None
    error: str | None = None


class Snapshot(_Open):
    """The engine's current state."""

    positions: Positions | None = None
    lights: Lights | None = None
    owner: str | None = None  # op_id holding the core
    running: list[OpSummary] = Field(default_factory=list)
    proposals: list[OpSummary] = Field(default_factory=list)
    pending_confirms: list[dict[str, Any]] = Field(default_factory=list)
    awaiting_return: dict[str, Any] | None = None
    session: SessionRef | None = None
    sample: SampleRef | None = None
    last_shutdown_lights: dict[str, Any] | None = None
    tweezers: TweezersState | None = None
    piezo: PiezoStateOut | None = None
    unclean_shutdown: dict[str, Any] | None = None
    hardware: HardwareState | None = None
    stream: dict[str, Any] | None = None
    recent: list[OpSummary] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    permissions: dict[str, dict[str, Any]] = Field(default_factory=dict)  # engine table
    config: dict[str, Any] = Field(default_factory=dict)


class PermissionOut(BaseModel):
    """One entry of `GET /api/permissions`: may the asking person do this now, and if not,
    why (`reason`, shown before the click) and the refusal `code` when the server says no
    (login_required, locked, remote_view, role); None when the engine says no."""

    allowed: bool
    reason: str | None = None
    code: str | None = None
