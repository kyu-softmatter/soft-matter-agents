"""Replay backend: saved z-stacks played back through the Backend protocol (T-034).

The source is anything `stacks.load_stacks` reads (T-005): in-memory `ZStack`s, synth
shards, or a sample folder's `find_particle_*`, `stack_*.npy` and `scan4x_*` tiles.

- **Z** is virtual: `move_z` (guard token) only changes the z that `snap()` looks up;
  `snap()` returns `ZStack.frame_at(z)`, the plane nearest the current z (edge plane and
  `last_hit.clamped` outside the stack). z is the stack's own coordinate (`notes["z_kind"]`):
  ZDrive um for bench stacks, but synth shards carry simulator or dz coordinates.
- **XY** is virtual too. Each stack sits at its recorded stage position (`x_um`/`y_um` or
  `xy_um` in its metadata); stacks without one are laid out on a virtual row
  `VIRTUAL_SPACING_UM` apart. An XY move sets the position; the stack nearest to it is the
  one replayed. With one stack the image never changes.
- **Lights, exposure, nosepiece, PFS** are virtual states read back exactly as written, with
  the same allow-list and token rules as every backend. They do not change the recorded
  frames (`notes["frames"]`).
- The acquisition stream has no thread: frames are due every interval from `start_stream`
  and `next_frame` returns the newest due one, with the injected clock and sleep.
- `info().bench` is False.

numpy only (through stacks); no torch, pymmcore or UI toolkit.
"""

from __future__ import annotations

import hashlib
import math
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from ..backend import (
    AURA_LINES,
    BackendInfo,
    ConfigRecord,
    DeviceInfo,
    Frame,
    MotionToken,
    NosepieceLabel,
    ObjectiveInfo,
    PfsState,
    PiezoReading,
    Positions,
    PropertyInfo,
    PropertyNotAllowed,
    Readback,
    StageLimits,
    StreamActive,
    check_set_property,
    require_token,
)
from .stacks import PlaneHit, ZStack, load_stacks

__all__ = ["CAMERA", "VIRTUAL_SPACING_UM", "ReplayBackend"]

CAMERA = "ReplayCam"
VIRTUAL_SPACING_UM = 1000.0  # stacks with no recorded XY, one per this step along x
MIN_STREAM_INTERVAL_MS = 1000.0 / 30  # interval_ms=None streams at the exposure, at most this fast
FRAMES_NOTE = "recorded frames: light, exposure and nosepiece do not change them"


def _xy_of(s: ZStack, i: int) -> tuple[tuple[float, float], bool]:
    m = s.meta
    if m.get("x_um") is not None and m.get("y_um") is not None:
        return (float(m["x_um"]), float(m["y_um"])), True
    xy = m.get("xy_um")
    if xy is not None and len(xy) >= 2 and None not in xy[:2]:
        return (float(xy[0]), float(xy[1])), True
    return (i * VIRTUAL_SPACING_UM, 0.0), False


class ReplayBackend:
    kind = "replay"

    def __init__(self, source, *, z_um: float | None = None, bit_depth: int = 16,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.stacks: list[ZStack] = load_stacks(source)
        if not self.stacks:
            raise FileNotFoundError(f"no z-stack in {source!r}")
        placed = [_xy_of(s, i) for i, s in enumerate(self.stacks)]
        self.stack_xy = [xy for xy, _ in placed]
        self.recorded_xy = [known for _, known in placed]
        self.bit_depth, self.clock, self.sleep = bit_depth, clock, sleep
        self.x, self.y = self.stack_xy[0]
        s0 = self.stacks[0]
        self.z = float(z_um) if z_um is not None else (
            s0.best_focus_um if s0.best_focus_um is not None else float(np.median(s0.z_um)))
        self.objectives = sorted({str(s.meta.get("objective") or "replay") for s in self.stacks})
        self.state = self.objectives.index(str(s0.meta.get("objective") or "replay"))
        self.exposure_ms = float(s0.meta.get("exposure_ms") or 10.0)
        self.roi_size = 0
        self.props: dict[tuple[str, str], str] = {("DiaLamp", "State"): "0",
                                                  ("DiaLamp", "Intensity"): "608",
                                                  ("Aura", "State"): "0"}
        for ln in AURA_LINES:
            self.props[("Aura", ln)] = "0"
            self.props[("Aura", f"{ln}_Intensity")] = "0"
        self.camera_props: dict[str, str] = {"Binning": "1", "PixelType": "16bit"}
        self.pfs_enabled = False
        self.is_open = False
        self.last_hit: PlaneHit | None = None
        self._stream: dict | None = None
        self._config: ConfigRecord | None = None

    # -- life
    def open(self) -> BackendInfo:
        h = hashlib.sha256()
        for s in self.stacks:
            h.update(np.ascontiguousarray(s.z_um).tobytes())
            h.update(repr(s.frames.shape).encode())
        paths = sorted({str(s.meta.get("path") or s.meta.get("source")) for s in self.stacks})
        self._config = ConfigRecord("; ".join(paths), h.hexdigest(), False, None, None,
                                    time.time(), {"source": "replay of saved z-stacks"})
        self.is_open = True
        return self.info()

    def close(self) -> None:
        self.stop_stream()
        self.is_open = False

    @property
    def stack(self) -> ZStack:
        """The stack nearest the virtual XY."""
        d = [math.hypot(x - self.x, y - self.y) for x, y in self.stack_xy]
        return self.stacks[int(np.argmin(d))]

    def info(self) -> BackendInfo:
        s = self.stack
        h, w = s.shape
        px = s.meta.get("pixel_um")
        notes = {"frames": FRAMES_NOTE, "z_kind": str(s.meta.get("z_kind", "unknown")),
                 "z_range_um": f"{s.z_range_um[0]:g}..{s.z_range_um[1]:g}",
                 "stacks": str(len(self.stacks)),
                 "xy": "recorded" if all(self.recorded_xy) else
                       f"virtual for stacks with no recorded XY, {VIRTUAL_SPACING_UM:g} um apart"}
        if px is None:
            notes["pixel_um"] = "not recorded with this stack (reported as 0)"
        return BackendInfo(
            "replay", self._config.path if self._config else "replay", CAMERA, (h, w),
            self._roi_box(), self.exposure_ms, float(px) if px is not None else 0.0,
            self.nosepiece(), None, self.bit_depth,
            [ObjectiveInfo(i, lab, 0.0, None, None) for i, lab in enumerate(self.objectives)],
            StageLimits(), notes, bench=False)

    def _roi_box(self) -> tuple[int, int, int, int]:
        h, w = self.stack.shape
        n = self.roi_size
        if 0 < n < min(h, w):
            return (w - n) // 2, (h - n) // 2, n, n
        return 0, 0, w, h

    # -- camera
    def _frame(self) -> Frame:
        hit = self.stack.frame_at(self.z)
        self.last_hit = hit
        x0, y0, rw, rh = self._roi_box()
        img = np.array(hit.frame[y0:y0 + rh, x0:x0 + rw])
        return Frame(img, time.time(), self.exposure_ms, self.x, self.y, self.z)

    def snap(self) -> Frame:
        if self._stream is not None:
            raise StreamActive("stop the stream before snap()")
        return self._frame()

    def set_exposure(self, ms: float) -> float:
        if not float(ms) > 0:
            raise ValueError(f"exposure must be > 0 ms, got {ms}")
        self.exposure_ms = float(ms)
        return self.exposure_ms

    def set_roi(self, size: int) -> tuple[int, int, int, int]:
        self.roi_size = max(0, int(size))
        return self._roi_box()

    # -- stream
    def start_stream(self, interval_ms: float | None = None) -> None:
        ms = max(self.exposure_ms, MIN_STREAM_INTERVAL_MS) if interval_ms is None \
            else float(interval_ms)
        if not ms > 0:
            raise ValueError(f"stream interval must be > 0 ms, got {ms}")
        self._stream = {"t0": self.clock(), "interval_s": ms / 1000.0, "last": -1}

    def next_frame(self, timeout_s: float = 1.0) -> Frame | None:
        s = self._stream
        if s is None:
            return None
        deadline = self.clock() + max(0.0, timeout_s)
        while True:
            now = self.clock()
            due = int(math.floor((now - s["t0"]) / s["interval_s"] + 1e-9))
            if due > s["last"]:
                s["last"] = due  # frames between the last returned and `due` are dropped
                return self._frame()
            wake = s["t0"] + (s["last"] + 1) * s["interval_s"]
            if wake > deadline:
                self.sleep(max(0.0, deadline - now))
                return None
            self.sleep(max(0.0, wake - now))

    def stop_stream(self) -> None:
        self._stream = None

    def streaming(self) -> bool:
        return self._stream is not None

    # -- reads
    def positions(self) -> Positions:
        return Positions(self.x, self.y, self.z)

    def _properties(self) -> dict[str, dict[str, PropertyInfo]]:
        on_off = ["0", "1"]
        dev: dict[str, dict[str, PropertyInfo]] = {"DiaLamp": {}, "Aura": {}}
        for (d, p), v in self.props.items():
            lim = (0.0, 1000.0) if p.endswith("_Intensity") else \
                (0.0, 2100.0) if p == "Intensity" else None
            dev[d][p] = PropertyInfo(v, False, [] if lim else on_off, lim)
        return {
            CAMERA: {"Exposure": PropertyInfo(f"{self.exposure_ms:.4f}", False),
                     **{k: PropertyInfo(v, False) for k, v in self.camera_props.items()}},
            "ZDrive": {"Position": PropertyInfo(f"{self.z:.3f}", False)},
            "XYStage": {"X": PropertyInfo(f"{self.x:.3f}", True),
                        "Y": PropertyInfo(f"{self.y:.3f}", True)},
            "Nosepiece": {"State": PropertyInfo(str(self.state), False,
                                                [str(i) for i in range(len(self.objectives))]),
                          "Label": PropertyInfo(self.nosepiece(), False, list(self.objectives))},
            "PFS": {"FocusMaintenance": PropertyInfo("On" if self.pfs_enabled else "Off", False),
                    "PFS in Range": PropertyInfo("Out of Range", True)},
            **dev,
        }

    DEVICE_TYPES = {CAMERA: "CameraDevice", "ZDrive": "StageDevice",
                    "XYStage": "XYStageDevice", "Nosepiece": "StateDevice",
                    "PFS": "AutoFocusDevice", "DiaLamp": "ShutterDevice",
                    "Aura": "ShutterDevice"}

    def read_property(self, device: str, prop: str) -> str:
        try:
            return str(self._properties()[device][prop].value)
        except KeyError:
            raise ValueError(f"replay has no property {device}.{prop}") from None

    def nosepiece(self) -> str:
        return self.objectives[self.state]

    def pfs(self) -> PfsState:
        return PfsState(self.pfs_enabled, False, "Out of Range")

    def light_state(self) -> dict[str, str]:
        return {"DiaLamp": self.props[("DiaLamp", "State")], "Aura": self.props[("Aura", "State")]}

    # -- discovery
    def describe_devices(self, include_properties: bool = True) -> list[DeviceInfo]:
        props = self._properties()
        return [DeviceInfo(label, kind, "replay", f"virtual {kind} over saved z-stacks", True,
                           properties=props[label] if include_properties else {})
                for label, kind in self.DEVICE_TYPES.items()]

    def nosepiece_labels(self) -> list[NosepieceLabel]:
        px = {str(s.meta.get("objective") or "replay"): s.meta.get("pixel_um")
              for s in self.stacks}
        return [NosepieceLabel(i, lab, None if px.get(lab) is None else float(px[lab]))
                for i, lab in enumerate(self.objectives)]

    def piezo_read(self, port: str) -> PiezoReading:
        return PiezoReading(port, False, error=f"no piezo on replay ({port})" if port else None)

    def config_record(self) -> ConfigRecord:
        return self._config or ConfigRecord("replay", None, None, None,
                                            notes={"state": "not opened"})

    # -- writes
    def _write(self, device: str, prop: str, value: Any) -> Readback:
        self.props[(device, prop)] = str(value)
        return Readback.of(device, prop, value, self.read_property(device, prop))

    def set_property(self, device: str, prop: str, value: Any, *,
                     token: MotionToken | None = None) -> Readback:
        check_set_property(device, prop, token, camera=CAMERA)
        if (device, prop) in self.props:
            return self._write(device, prop, value)
        if device == CAMERA:
            if prop == "Exposure":
                self.set_exposure(float(value))
                return Readback.of(device, prop, f"{float(value):.4f}",
                                   self.read_property(device, prop))
            self.camera_props[prop] = str(value)
            return Readback.of(device, prop, value, self.read_property(device, prop))
        raise PropertyNotAllowed(f"{device!r} is not a device on replay")

    def lamp_on(self, *, token: MotionToken) -> list[Readback]:
        require_token(token)
        return [self._write("Aura", "State", 0), self._write("DiaLamp", "State", 1)]

    def lamp_off(self) -> list[Readback]:
        return [self._write("DiaLamp", "State", 0)]

    def aura_line_on(self, line: str, percent: float, *, token: MotionToken) -> list[Readback]:
        require_token(token)
        ln = line.upper()
        if ln not in AURA_LINES:
            raise ValueError(f"Aura line {line!r} not in {AURA_LINES}")
        if not 0.0 <= float(percent) <= 100.0:
            raise ValueError(f"Aura percent {percent} is not in 0-100")
        return [self._write("DiaLamp", "State", 0),
                self._write("Aura", f"{ln}_Intensity", int(round(float(percent) * 10))),
                self._write("Aura", ln, 1), self._write("Aura", "State", 1)]

    def aura_off(self) -> list[Readback]:
        return [self._write("Aura", "State", 0)]

    def all_off(self) -> list[Readback]:
        return [*self.aura_off(), *self.lamp_off()]

    # -- motion: engine.guards only; virtual
    def move_z(self, z_um: float, *, token: MotionToken) -> float:
        require_token(token)
        z = float(z_um)
        if not math.isfinite(z):
            raise ValueError(f"z {z_um} is not a finite number")
        self.z = z
        return self.z

    def move_xy(self, x_um: float, y_um: float, *, token: MotionToken,
                timeout_s: float | None = None) -> tuple[float, float]:
        require_token(token)
        x, y = float(x_um), float(y_um)
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError(f"XY ({x_um}, {y_um}) is not finite")
        self.x, self.y = x, y
        return self.x, self.y

    def move_xy_rel(self, dx_um: float, dy_um: float, *, token: MotionToken,
                    timeout_s: float | None = None) -> tuple[float, float]:
        require_token(token)
        return self.move_xy(self.x + float(dx_um), self.y + float(dy_um), token=token)

    def set_nosepiece(self, state: int, *, token: MotionToken) -> Readback:
        require_token(token)
        if not 0 <= int(state) < len(self.objectives):
            raise ValueError(f"nosepiece state {state} is not in 0..{len(self.objectives) - 1}")
        self.state = int(state)
        return Readback.of("Nosepiece", "State", int(state), self.state)

    def pfs_off(self, *, token: MotionToken) -> Readback:
        require_token(token)
        self.pfs_enabled = False
        return Readback.of("PFS", "FocusMaintenance", "Off", "Off", notes={"pfs": "virtual"})
