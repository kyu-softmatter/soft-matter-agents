"""What the server assumes about the engine: command/event shapes and the runner interface.

Commands, events and their kind lists come from the engine (T-002, `engine/events.py`), the
runner's interface from `engine/runner.py` (T-011). The server needs a little more of the
runner than `runner.EngineAPI` names, so `EngineAPI` here extends it with those methods
(all of them `Runner` has).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ...engine.events import COMMAND_KINDS, EVENT_KINDS, ORIGINS, Command, Event
from ...engine.runner import EngineAPI as RunnerAPI

__all__ = [
    "COMMAND_KINDS", "EVENT_KINDS", "ORIGINS", "Command", "EngineAPI", "Event", "FrameSource",
    "MultiFrameSource",
]


class EngineAPI(RunnerAPI, Protocol):
    """The engine as the server sees it. The server decides nothing: it hands commands over
    and passes events on. Sinks may be called from any thread."""

    def check(self, ops: list[str] | None = None, context: dict | None = None) -> dict:
        """`{op: {allowed, reason}}` from the permission table and the engine state."""
        ...

    def set_local_viewers(self, count: int) -> None:
        """How many loopback browser connections are open (D14)."""
        ...

    def shutdown(self, reason: str) -> Any:
        """Lights off with readback first, then abort, finish records, record `reason`.
        Blocks until done."""
        ...


@runtime_checkable
class FrameSource(Protocol):
    """Optional: an engine that can hand over its newest camera frame. The frame bridge reads
    it when a `frame_ready` event arrives; `Runner.latest_frame` is one (T-011). `meta` is
    JSON-native (t, x_um, y_um, z_um, exposure_ms, bit_depth, frame_id, ...)."""

    def latest_frame(self) -> tuple[Any, dict[str, Any]] | None: ...  # (uint16 ndarray, meta)


@runtime_checkable
class MultiFrameSource(Protocol):
    """Optional, for more than one camera: the newest frame of each camera, keyed by the camera
    label (`meta["camera"]`). The bridge sends every camera whose frame changed; an engine
    without it is read through `latest_frame` as one camera."""

    def latest_frames(self) -> dict[str, tuple[Any, dict[str, Any]]]: ...
