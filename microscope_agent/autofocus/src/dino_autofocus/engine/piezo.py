"""The XYZ piezo stage as the engine drives it for patterns (card T-20261002-2205 stage 4).

On the stand the piezo is READ ONLY until M5 (`mm_real.piezo_read`; operations-spec 9.2): no
position command exists for it, and nothing here adds one. Only `MockPiezo` moves, for the
mock. Writes take the guards' token and go through `guards.PiezoAxis` only.

Positions are the piezo's own axes in um (0..travel); a pattern's piezo track is offsets from
where the piezo is when the run starts (`engine/patterns.py`).
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .backend import require_token


@dataclass(frozen=True)
class PiezoState:
    x_um: float
    y_um: float
    z_um: float


@dataclass(frozen=True)
class PiezoInfo:
    kind: str  # "mock"
    #: travel per axis, um: (low, high)
    travel_um: dict[str, tuple[float, float]]
    #: False only for a simulation; anything else is treated as the real piezo
    bench: bool = True


class Piezo(Protocol):
    def info(self) -> PiezoInfo: ...
    def position(self) -> PiezoState: ...
    def move(self, x_um: float, y_um: float, z_um: float, *, token: object) -> PiezoState: ...


def piezo_state_of(piezo: Piezo | None) -> dict[str, Any] | None:
    """The block the engine snapshot carries (`snapshot()["piezo"]`); None: no piezo to move."""
    if piezo is None:
        return None
    try:
        info = asdict(piezo.info())
    except Exception as exc:  # noqa: BLE001
        return {"kind": "unknown", "travel_um": {}, "bench": True, "position": None,
                "error": f"{type(exc).__name__}: {exc}"}
    try:
        pos = asdict(piezo.position())
    except Exception as exc:  # noqa: BLE001
        return {**info, "position": None, "error": f"{type(exc).__name__}: {exc}"}
    return {**info, "position": pos, "error": None}


class MockPiezo:
    """An in-memory XYZ piezo: travel 0..200 um in x and y, 0..100 um in z, starting at the
    middle; moves land exactly."""

    TRAVEL = {"x": (0.0, 200.0), "y": (0.0, 200.0), "z": (0.0, 100.0)}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pos = PiezoState(100.0, 100.0, 50.0)

    def info(self) -> PiezoInfo:
        return PiezoInfo("mock", dict(self.TRAVEL), bench=False)

    def position(self) -> PiezoState:
        with self._lock:
            return self._pos

    def move(self, x_um: float, y_um: float, z_um: float, *, token: object) -> PiezoState:
        require_token(token)
        for axis, v in (("x", x_um), ("y", y_um), ("z", z_um)):
            lo, hi = self.TRAVEL[axis]
            if not lo <= v <= hi:  # the guards check first; the device refuses as well
                raise ValueError(f"piezo {axis} {v:g} um is outside its travel {lo:g}..{hi:g} um")
        with self._lock:
            self._pos = PiezoState(float(x_um), float(y_um), float(z_um))
            return self._pos
