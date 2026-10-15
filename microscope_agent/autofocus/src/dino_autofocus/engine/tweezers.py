"""Optical tweezers: the interface the engine drives, and a mock (card T-20261002-2205 stage 3).

The real tweezers are run by the vendor software **Tweez300**, which stays running on the
microscope PC; the app sends it commands (Python API or TCP: `backends/tweez300.py`, not wired
until its command reference is in). Until then only `MockTweezers` exists.

Coordinates as in `engine/patterns.py`: a trap's x/y are um in the sample plane from the
centre of the camera field (x right, y down as on the image, orientation provisional); z is
the trap's focus offset. Moves and on/off are write calls and take the guards' token, so they
go through `guards.TrapAxis` only (ranges, bench lock), never straight from an operation.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, replace
from typing import Any, Protocol

import numpy as np

from .backend import require_token
from .patterns import TRAP_RANGE_UM


@dataclass(frozen=True)
class TrapState:
    index: int
    on: bool
    x_um: float
    y_um: float
    z_um: float = 0.0
    #: laser share in percent; None when the tweezers cannot report it (Tweez300: set by hand)
    power_pct: float | None = None


@dataclass(frozen=True)
class TweezersInfo:
    kind: str  # "mock" | "tweez300"
    n_traps: int
    #: False only for a simulation; anything else is treated as the real tweezers
    bench: bool = True
    notes: dict[str, str] | None = None


class Tweezers(Protocol):
    def info(self) -> TweezersInfo: ...
    def traps(self) -> list[TrapState]: ...
    def move_trap(self, index: int, x_um: float, y_um: float, z_um: float, *,
                  token: object) -> TrapState: ...
    def set_trap(self, index: int, on: bool, *, token: object) -> TrapState: ...
    def close(self) -> None: ...


def state_of(tweezers: Tweezers | None) -> dict[str, Any] | None:
    """The block the engine snapshot carries (`snapshot()["tweezers"]`); None: no tweezers."""
    if tweezers is None:
        return None
    try:
        info = asdict(tweezers.info())
    except Exception as exc:  # noqa: BLE001 - an unreadable device is a field, not a crash
        return {"kind": "unknown", "n_traps": 0, "bench": True, "notes": None, "traps": [],
                "error": f"{type(exc).__name__}: {exc}"}
    try:
        traps = [asdict(t) for t in tweezers.traps()]
    except Exception as exc:  # noqa: BLE001
        return {**info, "traps": [], "error": f"{type(exc).__name__}: {exc}"}
    return {**info, "traps": traps, "error": None}


class MockTweezers:
    """In-memory traps for the mock: moves land exactly, nothing is sent anywhere."""

    def __init__(self, n_traps: int = 4) -> None:
        self._lock = threading.Lock()
        self._traps = [TrapState(i, i == 0, 0.0 if i == 0 else 8.0 * i, 0.0, 0.0, 25.0)
                       for i in range(n_traps)]

    def info(self) -> TweezersInfo:
        return TweezersInfo("mock", len(self._traps), bench=False,
                            notes={"source": "mock tweezers, no Tweez300"})

    def traps(self) -> list[TrapState]:
        with self._lock:
            return list(self._traps)

    def _index(self, index: int) -> int:
        if not 0 <= int(index) < len(self._traps):
            raise ValueError(f"no trap {index} (traps 0..{len(self._traps) - 1})")
        return int(index)

    def move_trap(self, index: int, x_um: float, y_um: float, z_um: float, *,
                  token: object) -> TrapState:
        require_token(token)
        i = self._index(index)
        for axis, v in (("x", x_um), ("y", y_um), ("z", z_um)):
            lo, hi = TRAP_RANGE_UM[axis]
            if not lo <= v <= hi:  # the guards check first; the device refuses as well
                raise ValueError(f"trap {i} {axis} {v:g} um is outside {lo:g}..{hi:g} um")
        with self._lock:
            self._traps[i] = replace(self._traps[i], x_um=float(x_um), y_um=float(y_um),
                                     z_um=float(z_um))
            return self._traps[i]

    def set_trap(self, index: int, on: bool, *, token: object) -> TrapState:
        require_token(token)
        i = self._index(index)
        with self._lock:
            self._traps[i] = replace(self._traps[i], on=bool(on))
            return self._traps[i]

    def close(self) -> None:
        return None


def draw_traps(img: np.ndarray, traps: list[TrapState], pixel_um: float, *,
               peak: float, sigma_px: float = 6.0) -> np.ndarray:
    """A copy of `img` with a bright spot at each trap that is on (mock pictures only)."""
    out = img.astype(np.float32, copy=True)
    h, w = out.shape
    r = int(4 * sigma_px)
    for t in traps:
        if not t.on:
            continue
        cx, cy = w / 2 + t.x_um / pixel_um, h / 2 + t.y_um / pixel_um
        x0, x1 = max(int(cx) - r, 0), min(int(cx) + r + 1, w)
        y0, y1 = max(int(cy) - r, 0), min(int(cy) + r + 1, h)
        if x0 >= x1 or y0 >= y1:
            continue  # off the field
        gy = np.exp(-((np.arange(y0, y1) - cy) ** 2) / (2 * sigma_px**2))
        gx = np.exp(-((np.arange(x0, x1) - cx) ** 2) / (2 * sigma_px**2))
        out[y0:y1, x0:x1] += peak * np.outer(gy, gx)
    top = np.iinfo(img.dtype).max if np.issubdtype(img.dtype, np.integer) else None
    if top is not None:
        np.clip(out, 0, top, out=out)
    return out.astype(img.dtype)


#: a mock bead of about 1 um and a diffraction-limited laser spot, as gaussian sigmas in um
BEAD_SIGMA_UM = 0.45
SPOT_SIGMA_UM = 0.3
#: never smaller than this many camera pixels, so the mock traps stay visible after the live
#: view bins the frame at low magnification (a picture aid, not optics)
MIN_SIGMA_PX = 3.0


def mock_views(tweezers: Tweezers, *, laser_camera: str = "Kinetix_blue", piezo: Any = None):
    """`BackendStream.decorate` for the mock: the camera frame with a bead held in every trap
    that is on, plus a second camera (`laser_camera`) that sees only the trap laser spots, so
    the side-by-side and merged views show the traps over the sample. With a mock `piezo` the
    sample picture shifts by the piezo's XY offset from the middle of its travel (the traps,
    fixed to the optics, do not), so a pattern run is seen moving the sample."""
    dark: dict[tuple[int, ...], np.ndarray] = {}

    def shifted(img: np.ndarray, pixel_um: float) -> np.ndarray:
        if piezo is None:
            return img
        try:
            pos, travel = piezo.position(), piezo.info().travel_um
        except Exception:  # noqa: BLE001 - a picture aid only
            return img
        dx = (pos.x_um - sum(travel["x"]) / 2) / pixel_um
        dy = (pos.y_um - sum(travel["y"]) / 2) / pixel_um
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            return img
        return np.roll(img, (int(round(dy)), int(round(dx))), axis=(0, 1))

    def decorate(frame: Any) -> list[Any]:
        if frame.pixel_um is None or not frame.pixel_um > 0:
            return [frame]
        traps = tweezers.traps()
        img = shifted(frame.image, frame.pixel_um)
        # as bright as the brightest part of the sample, so the live view's display range
        # (0.5-99.5 percentile) keeps both visible
        bright = max(float(np.percentile(img[::8, ::8], 99.5)), 50.0)
        beads = draw_traps(img, traps, frame.pixel_um, peak=1.5 * bright,
                           sigma_px=max(MIN_SIGMA_PX, BEAD_SIGMA_UM / frame.pixel_um))
        if img.shape not in dark:
            # flat: the live view stretches its 0.5-99.5 percentile, which would blow noise up
            dark[img.shape] = np.full(img.shape, 100, dtype=img.dtype)
        spots = draw_traps(dark[img.shape], traps, frame.pixel_um, peak=3000.0,
                           sigma_px=max(MIN_SIGMA_PX, SPOT_SIGMA_UM / frame.pixel_um))
        # the sample camera last: `Runner.latest_frame()` (what edge_trace grabs from the
        # stream) is then always the sample, never the laser-only picture
        # the laser camera sees no sample: no focus truth on it
        return [replace(frame, image=spots, camera=laser_camera, dz_truth_dof=None),
                replace(frame, image=beads)]

    return decorate
