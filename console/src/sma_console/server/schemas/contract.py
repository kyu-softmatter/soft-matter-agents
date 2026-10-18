"""What the server assumes about the engine it shows: events out, a snapshot, no commands.

TEMPORARY (soft-matter-agents card 077). Until the cut, the event shape and the runner's
interface were imported from dino's engine (`engine/events.py`, `engine/runner.py`). The
console crosses to its own folder and the engine stays, so this module holds a copy of the
shapes the placeholder engine needs to answer status and events, and nothing more: no
`Command` type and no command kinds, because the console sends no command to any engine
(soft-matter-agents plan.md 15; the console commands nothing). It is replaced by the run
interface, `contracts/schemas/run_interface.schema.json`, on the console's first card after
the move. Nothing that stays with the engine imports it.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = ["EVENT_KINDS", "EngineAPI", "Event", "FrameSource", "MultiFrameSource"]

#: A copy of `engine/events.py`'s EVENT_KINDS at the cut, so the screens' event types stay
#: what they were. Event names only; no command is sent from here.
EVENT_KINDS = (
    "planned", "preflight_ok", "preflight_failed", "started", "progress", "frame_ready",
    "reading", "finished", "aborted", "error",
    "position", "light_changed", "property_set", "motion",
    "confirm_required", "confirmed",
    "proposed", "approved", "rejected", "refused", "updated",
    "map_changed", "sample_opened", "objective", "session_changed",
    "log",
)


@dataclass
class Event:
    """One event as the server passes it on. `user_id` / `session_id` are the operation's;
    None for engine-wide events such as `position`."""

    kind: str
    op_id: str = ""
    data: dict = field(default_factory=dict)
    t: float = field(default_factory=time.time)
    user_id: str | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind {self.kind!r}")

    def to_json(self) -> str:
        return json.dumps(asdict(self))


class EngineAPI(Protocol):
    """The engine as the server sees it: something that sends events and answers status.
    Sinks may be called from any thread."""

    def subscribe(self, sink: Callable[[Event], None]) -> Callable[[], None]:
        """Returns the unsubscribe."""
        ...

    def snapshot(self) -> dict:
        """JSON-native current state."""
        ...

    def check(self, ops: list[str] | None = None, context: dict | None = None) -> dict:
        """`{op: {allowed, reason}}`."""
        ...

    def set_local_viewers(self, count: int) -> None:
        """How many loopback browser connections are open (D14)."""
        ...

    def shutdown(self, reason: str) -> Any:
        """Stop, and record `reason`. Blocks until done."""
        ...


@runtime_checkable
class FrameSource(Protocol):
    """Optional: an engine that can hand over its newest camera frame. The frame bridge reads
    it when a `frame_ready` event arrives. `meta` is JSON-native."""

    def latest_frame(self) -> tuple[Any, dict[str, Any]] | None: ...  # (uint16 ndarray, meta)


@runtime_checkable
class MultiFrameSource(Protocol):
    """Optional, for more than one camera: the newest frame of each camera, keyed by the camera
    label (`meta["camera"]`)."""

    def latest_frames(self) -> dict[str, tuple[Any, dict[str, Any]]]: ...
