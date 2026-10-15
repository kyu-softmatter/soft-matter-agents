"""MockBackend: the Backend protocol (T-002 + T-015) over the virtual microscope (T-007).

The M1 default backend (PLAN.md 5). `MockWorld` is the hardware; this class is the driver
layer a real backend would be, with the bench's device names (ZDrive, XYStage, Nosepiece,
PFS, DiaLamp, Aura, camera Kinetix_red) so records look like the bench's.

- z is bench ZDrive um (up = toward the sample, 0 = retracted; PLAN v1.2), as in the world.
- Motion and light-on take the guard token (`require_token`); off never does. set_property
  goes through the shared allow-list (`check_set_property`).
- Reads go through the world's readback, so injected faults (`Faults`: Z/XY readback error,
  light dropout frames) reach the guards exactly as a misbehaving stand would. Change them
  with `inject_faults(...)`.
- Moves are instant by default. `move_time_scale` > 0 sleeps that fraction of the time the
  world says a real move takes. A move longer than `timeout_s` still happens (the stage keeps
  going) and then raises `TimeoutError`, like the Micro-Manager wait.
- The acquisition stream has no thread: frames are due every `interval_ms` from
  `start_stream`, and `next_frame` renders the newest due frame from the current state
  (older ones are dropped), waiting with the injected `sleep` until one is due.
- Values the mock invents (piezo position, Aura lines other than GREEN, stage travel) carry
  "unmeasured provisional" in `notes`.

numpy + scipy only (through mock_world); no torch, pymmcore or UI toolkit.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from ..backend import (
    AURA_LINES,
    PROVISIONAL,
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
    Readback,
    StageLimits,
    StreamActive,
    check_set_property,
    require_token,
)
from .mock_world import OBJECTIVES, Faults, MockWorld, SampleSpec

__all__ = ["CAMERA", "MockBackend"]

CAMERA = "Kinetix_red"  # the bench camera label (2026-09-30 run)
DIA_MAX = 2100  # DiaLamp intensity range of the Ti2 lamp, as in mock_world.Light
MEASURED_AURA_LINES = ("GREEN",)  # used on the bench 2026-09-30
#: mock choice, not a camera spec: interval_ms=None streams at the exposure, at most this fast
MIN_STREAM_INTERVAL_MS = 1000.0 / 30
#: unmeasured provisional: read-only piezo z seen on 2026-09-30, mock answers on this port
PIEZO_PORT, PIEZO_UM = "COM4", (0.0, 0.0, 9.94)


class MockBackend:
    kind = "mock"

    def __init__(self, world: MockWorld | None = None, *, seed: int = 0,
                 sample: SampleSpec | None = None, faults: Faults | None = None,
                 move_time_scale: float = 0.0,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.world = world or MockWorld(sample, faults, seed=seed)
        if world is not None and faults is not None:
            self.world.faults = faults
        self.move_time_scale = move_time_scale
        self.clock, self.sleep = clock, sleep
        self.is_open = False
        self.camera_props = {"PixelType": "16bit", "OnCameraCCDXSize": "2400",
                             "OnCameraCCDYSize": "2400"}
        self._config: ConfigRecord | None = None
        self._stream: dict | None = None  # {"t0", "interval_s", "last"}

    # -- faults
    def inject_faults(self, **kw: Any) -> Faults:
        """Replace fault fields (z_readback_error_um, xy_readback_error_um, dropout_frames,
        dropout_factor) for the following calls."""
        self.world.faults = replace(self.world.faults, **kw)
        return self.world.faults

    # -- life
    def open(self) -> BackendInfo:
        spec = json.dumps(self.world.to_dict()["sample"], sort_keys=True).encode()
        self._config = ConfigRecord(
            f"mock://seed={self.world.spec.seed}", hashlib.sha256(spec).hexdigest(), False,
            Readback.of("Core", "AutoShutter", 0, 0, notes={"mock": "no shutter logic"}),
            None, time.time(), notes={"source": "mock world, no configuration file"})
        self.is_open = True
        return self.info()

    def close(self) -> None:
        self.stop_stream()
        self.is_open = False

    def info(self) -> BackendInfo:
        w, o = self.world, self.world.objective
        lim = w.limits
        objs = [ObjectiveInfo(ob.position, ob.label, ob.magnification, ob.pixel_um,
                              ob.working_distance_um) for ob in OBJECTIVES]
        notes = {"stage_limits": PROVISIONAL, "camera.gain_e_per_adu": PROVISIONAL,
                 "objectives": "labels and parfocal offsets read on the bench only for "
                               f"4x and 100x Oil; others {PROVISIONAL}",
                 **{f"aura.{ln}": PROVISIONAL for ln in AURA_LINES
                    if ln not in MEASURED_AURA_LINES}}
        return BackendInfo("mock", self._config.path if self._config else "mock://",
                           CAMERA, w.camera.sensor, self._roi(), w.exposure_ms,
                           o.pixel_um * w.binning, o.label, None, w.camera.bit_depth, objs,
                           StageLimits(lim.x_um, lim.y_um, lim.z_um), notes, bench=False)

    def _roi(self) -> tuple[int, int, int, int]:
        h, wd = self.world.camera.sensor
        return self.world.roi or (0, 0, wd, h)

    # -- camera
    def _frame(self) -> Frame:
        w = self.world
        img = w.snap()
        x, y = w.read_xy()
        dz = (w.z_um - w.in_focus_z()) / w.objective.dof_um  # the true z, not the readback
        return Frame(img, time.time(), w.exposure_ms, x, y, w.read_z(), camera=CAMERA,
                     dz_truth_dof=float(dz))

    def snap(self) -> Frame:
        if self._stream is not None:
            raise StreamActive("stop the stream before snap()")
        return self._frame()

    def set_exposure(self, ms: float) -> float:
        self.world.set_exposure(ms)
        return self.world.exposure_ms

    def set_roi(self, size: int) -> tuple[int, int, int, int]:
        self.world.set_roi(None if int(size) == 0 else int(size))
        return self._roi()

    # -- stream
    def start_stream(self, interval_ms: float | None = None) -> None:
        ms = max(self.world.exposure_ms, MIN_STREAM_INTERVAL_MS) if interval_ms is None \
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
                s["last"] = due  # frames between the last one returned and `due` are dropped
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
        x, y = self.world.read_xy()
        return Positions(x, y, self.world.read_z())

    def _properties(self) -> dict[str, dict[str, PropertyInfo]]:
        """Every property the mock devices have: value, read-only, allowed values, limits."""
        w, lt = self.world, self.world.light
        labels = [o.label for o in OBJECTIVES]
        on_off = ["0", "1"]
        x, y = w.read_xy()
        aura = {"State": PropertyInfo(str(int(lt.aura_on)), False, on_off)}
        for ln in AURA_LINES:
            aura[ln] = PropertyInfo(str(int(lt.aura_lines.get(ln, False))), False, on_off)
            aura[f"{ln}_Intensity"] = PropertyInfo(str(lt.aura_permille.get(ln, 0)), False,
                                                   limits=(0.0, 1000.0))
        return {
            "Core": {"AutoShutter": PropertyInfo("0", False, on_off),
                     "Camera": PropertyInfo(CAMERA, True)},
            CAMERA: {"Exposure": PropertyInfo(f"{w.exposure_ms:.4f}", False,
                                              limits=(0.001, 10000.0)),
                     "Binning": PropertyInfo(str(w.binning), False, ["1", "2", "4", "8"]),
                     **{k: PropertyInfo(v, False) for k, v in self.camera_props.items()}},
            "ZDrive": {"Position": PropertyInfo(f"{w.read_z():.3f}", False,
                                                limits=w.limits.z_um)},
            "XYStage": {"X": PropertyInfo(f"{x:.3f}", True), "Y": PropertyInfo(f"{y:.3f}", True)},
            "Nosepiece": {"State": PropertyInfo(str(w.nosepiece), False,
                                                [str(o.position) for o in OBJECTIVES]),
                          "Label": PropertyInfo(w.objective.label, False, labels)},
            "PFS": {"FocusMaintenance": PropertyInfo("On" if w.pfs_enabled else "Off", False,
                                                     ["Off", "On"]),
                    "PFS in Range": PropertyInfo(w.pfs_in_range, True)},
            "DiaLamp": {"State": PropertyInfo(str(int(lt.dia_on)), False, on_off),
                        "Intensity": PropertyInfo(str(lt.dia_intensity), False,
                                                  limits=(0.0, float(DIA_MAX)))},
            "Aura": aura,
        }

    DEVICE_TYPES = {"Core": "CoreDevice", CAMERA: "CameraDevice", "ZDrive": "StageDevice",
                    "XYStage": "XYStageDevice", "Nosepiece": "StateDevice",
                    "PFS": "AutoFocusDevice", "DiaLamp": "ShutterDevice",
                    "Aura": "ShutterDevice"}

    def read_property(self, device: str, prop: str) -> str:
        try:
            return str(self._properties()[device][prop].value)
        except KeyError:
            raise ValueError(f"mock has no property {device}.{prop}") from None

    def nosepiece(self) -> str:
        return self.world.objective.label

    def pfs(self) -> PfsState:
        return PfsState(self.world.pfs_enabled, False, self.world.pfs_in_range)

    def light_state(self) -> dict[str, str]:
        lt = self.world.light
        return {"DiaLamp": str(int(lt.dia_on)), "Aura": str(int(lt.aura_on))}

    # -- discovery reads
    def describe_devices(self, include_properties: bool = True) -> list[DeviceInfo]:
        props = self._properties()
        return [DeviceInfo(label, kind, "mock", f"mock {kind} ({label})", True,
                           properties=props[label] if include_properties else {})
                for label, kind in self.DEVICE_TYPES.items()]

    def nosepiece_labels(self) -> list[NosepieceLabel]:
        return [NosepieceLabel(o.position, o.label, o.pixel_um) for o in OBJECTIVES]

    def piezo_read(self, port: str) -> PiezoReading:
        if not port:
            return PiezoReading("", False)
        if port != PIEZO_PORT:
            return PiezoReading(port, False, error=f"no piezo on {port} (mock: {PIEZO_PORT})")
        return PiezoReading(port, True, *PIEZO_UM)

    def config_record(self) -> ConfigRecord:
        return self._config or ConfigRecord("mock://", None, None, None,
                                            notes={"state": "not opened"})

    # -- writes
    def _rb(self, device: str, prop: str, wanted: Any, notes: dict | None = None) -> Readback:
        return Readback.of(device, prop, wanted, self.read_property(device, prop), notes)

    def set_property(self, device: str, prop: str, value: Any, *,
                     token: MotionToken | None = None) -> Readback:
        check_set_property(device, prop, token, camera=CAMERA)
        w, v = self.world, str(value)
        if device == "DiaLamp" and prop == "State":
            w.set_dialamp(bool(int(v)))
        elif device == "DiaLamp" and prop == "Intensity":
            if not 0 <= int(v) <= DIA_MAX:
                raise ValueError(f"DiaLamp intensity {v} outside 0..{DIA_MAX}")
            w.set_dialamp(w.light.dia_on, int(v))
        elif device == "Aura" and prop == "State":
            w.set_aura(bool(int(v)))
        elif device == "Aura" and prop in AURA_LINES:
            w.set_aura_line(prop, bool(int(v)))
        elif device == "Aura" and prop.endswith("_Intensity"):
            line = prop.removesuffix("_Intensity")
            w.set_aura_line(line, w.light.aura_lines.get(line, False), int(v))
        elif device == CAMERA and prop == "Exposure":
            w.set_exposure(float(v))
            return Readback.of(device, prop, f"{float(v):.4f}", self.read_property(device, prop))
        elif device == CAMERA and prop == "Binning":
            if v not in {"1", "2", "4", "8"}:
                raise ValueError(f"binning {v} not in 1, 2, 4, 8")
            w.binning = int(v)
        elif device == CAMERA:
            self.camera_props[prop] = v  # recorded; the mock image does not change
        else:
            raise ValueError(f"mock has no device {device!r}")  # demo names, allowed elsewhere
        notes = {"aura_line": PROVISIONAL} if device == "Aura" and _line(prop) not in \
            (None, *MEASURED_AURA_LINES) else None
        return self._rb(device, prop, v, notes)

    def lamp_on(self, *, token: MotionToken) -> list[Readback]:
        require_token(token)
        self.world.set_aura(False)
        r1 = self._rb("Aura", "State", 0)
        self.world.set_dialamp(True)
        return [r1, self._rb("DiaLamp", "State", 1)]

    def lamp_off(self) -> list[Readback]:
        self.world.set_dialamp(False)
        return [self._rb("DiaLamp", "State", 0)]

    def aura_line_on(self, line: str, percent: float, *, token: MotionToken) -> list[Readback]:
        """The 2026-09-30 order: DiaLamp State 0, <LINE>_Intensity (per-mille), <LINE> 1,
        Aura State 1. 1 % = per-mille 10."""
        require_token(token)
        ln = line.upper()
        if ln not in AURA_LINES:
            raise ValueError(f"Aura line {line!r} not in {AURA_LINES}")
        permille = int(round(float(percent) * 10))
        if not 0 <= permille <= 1000:
            raise ValueError(f"Aura percent {percent} outside 0..100")
        notes = None if ln in MEASURED_AURA_LINES else {"aura_line": PROVISIONAL}
        w = self.world
        w.set_dialamp(False)
        out = [self._rb("DiaLamp", "State", 0)]
        w.set_aura_line(ln, w.light.aura_lines.get(ln, False), permille)
        out.append(self._rb("Aura", f"{ln}_Intensity", permille, notes))
        w.set_aura_line(ln, True)
        out.append(self._rb("Aura", ln, 1, notes))
        w.set_aura(True)
        out.append(self._rb("Aura", "State", 1))
        return out

    def aura_off(self) -> list[Readback]:
        self.world.set_aura(False)
        return [self._rb("Aura", "State", 0)]

    def all_off(self) -> list[Readback]:
        self.world.all_off()
        return [self._rb("Aura", "State", 0), self._rb("DiaLamp", "State", 0)]

    # -- motion: engine.guards only
    def _wait(self, seconds: float, timeout_s: float | None, what: str) -> None:
        if self.move_time_scale > 0:
            self.sleep(seconds * self.move_time_scale)
        if timeout_s is not None and seconds > timeout_s:
            raise TimeoutError(f"{what} takes {seconds:.2f} s, over the {timeout_s} s wait "
                               "(the stage keeps moving)")

    def move_z(self, z_um: float, *, token: MotionToken) -> float:
        require_token(token)
        self._wait(self.world.move_z(float(z_um)), None, "ZDrive move")
        return self.world.read_z()

    def move_xy(self, x_um: float, y_um: float, *, token: MotionToken,
                timeout_s: float | None = None) -> tuple[float, float]:
        require_token(token)
        self._wait(self.world.move_xy(float(x_um), float(y_um)), timeout_s, "XY move")
        return self.world.read_xy()

    def move_xy_rel(self, dx_um: float, dy_um: float, *, token: MotionToken,
                    timeout_s: float | None = None) -> tuple[float, float]:
        require_token(token)
        x, y = self.world.read_xy()  # from the read, as the stand's relative move does
        return self.move_xy(x + float(dx_um), y + float(dy_um), token=token, timeout_s=timeout_s)

    def set_nosepiece(self, state: int, *, token: MotionToken) -> Readback:
        require_token(token)
        self.world.set_nosepiece(int(state))
        return self._rb("Nosepiece", "State", int(state))

    def pfs_off(self, *, token: MotionToken) -> Readback:
        require_token(token)
        self.world.pfs_disable()
        return self._rb("PFS", "FocusMaintenance", "Off")


def _line(prop: str) -> str | None:
    ln = prop.removesuffix("_Intensity")
    return ln if ln in AURA_LINES else None
