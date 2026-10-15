"""FakeBackend: the Backend protocol in memory, shared by WP-B/WP-C tests.

Positions follow the commands; `z_readback_offset_um` makes ZDrive read back off by that
much; `all_off_raises` makes lights-off fail. `set_property` follows the shared allow-list
and light-on needs the guard token, like every backend. The stream has no thread: each
`next_frame()` while streaming is one new frame. `piezo_um` set = a piezo answers on any
port. `frame.z_um` is the commanded Z, so a test score can be
`lambda f: -abs(f.z_um - focus)`. Every call is appended to `calls`.
"""

from __future__ import annotations

import re
import time

import numpy as np

from dino_autofocus.engine.backend import (
    BackendInfo,
    ConfigRecord,
    DeviceInfo,
    Frame,
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

LABELS = ["1-Plan Apo LmbdD20 4x", "2-Plan Apo 10x", "3-Plan Apo 20x", "4-Plan Apo 40x WI",
          "5-Plan Apo 60x Oil", "6-Plan Apo LmbdD0.13 100x Oil"]


class FakeBackend:
    kind = "fake"

    def __init__(self, z_um: float = 2900.0, x_um: float = 8026.0, y_um: float = 571.6,
                 z_readback_offset_um: float = 0.0, pfs_enabled: bool = False,
                 pfs_in_range: str = "Out of Range", all_off_raises: bool = False,
                 shape: tuple[int, int] = (32, 32)):
        self.x, self.y, self.z, self.state = x_um, y_um, z_um, 0
        self.z_readback_offset_um = z_readback_offset_um
        self.all_off_raises, self.shape = all_off_raises, shape
        self.pfs_enabled, self.pfs_in_range = pfs_enabled, pfs_in_range
        self.lights = {"DiaLamp": "0", "Aura": "0"}
        self.stuck: set[str] = set()  # light devices whose State ignores writes
        self.props: dict[tuple[str, str], str] = {}
        self.exposure, self.is_open, self.calls = 10.0, False, []
        self.is_streaming, self.stream_frames = False, 0
        self.piezo_um: tuple[float, float, float] | None = None

    def _log(self, name: str, *args) -> None:
        self.calls.append((name, *args))

    def open(self) -> BackendInfo:
        self.is_open = True
        return self.info()

    def close(self) -> None:
        self.stop_stream()
        self.is_open = False
        self._log("close")

    def info(self) -> BackendInfo:
        objs = [ObjectiveInfo(i, lab, float(re.search(r"(\d+)x", lab).group(1)), None, None)
                for i, lab in enumerate(LABELS)]
        return BackendInfo("fake", "memory", "FakeCam", self.shape, (0, 0, *self.shape),
                           self.exposure, 1.625, LABELS[self.state], None, 12, objs,
                           StageLimits((-50000.0, 50000.0), (-35000.0, 35000.0),
                                       (0.0, 10000.0)), bench=False)

    def _frame(self) -> Frame:
        img = np.full(self.shape, 100, np.uint16)
        return Frame(img, time.time(), self.exposure, self.x, self.y, self.z)

    def snap(self) -> Frame:
        if self.is_streaming:
            raise StreamActive("stop the stream before snap()")
        return self._frame()

    def start_stream(self, interval_ms: float | None = None) -> None:
        self._log("start_stream", interval_ms)
        self.is_streaming = True

    def next_frame(self, timeout_s: float = 1.0) -> Frame | None:
        if not self.is_streaming:
            return None
        self.stream_frames += 1
        return self._frame()

    def stop_stream(self) -> None:
        if self.is_streaming:
            self._log("stop_stream")
        self.is_streaming = False

    def streaming(self) -> bool:
        return self.is_streaming

    def set_exposure(self, ms: float) -> float:
        self.exposure = float(ms)
        return self.exposure

    def set_roi(self, size: int) -> tuple[int, int, int, int]:
        return (0, 0, *self.shape)

    def positions(self) -> Positions:
        return Positions(self.x, self.y, self.z + self.z_readback_offset_um)

    def read_property(self, device: str, prop: str) -> str:
        return self.props.get((device, prop), "")

    def nosepiece(self) -> str:
        return LABELS[self.state]

    def pfs(self) -> PfsState:
        return PfsState(self.pfs_enabled, False, self.pfs_in_range)

    def light_state(self) -> dict[str, str]:
        return dict(self.lights)

    DEVICES = (("FakeCam", "CameraDevice"), ("ZDrive", "StageDevice"),
               ("XYStage", "XYStageDevice"), ("Nosepiece", "StateDevice"),
               ("PFS", "AutoFocusDevice"), ("DiaLamp", "ShutterDevice"),
               ("Aura", "ShutterDevice"))

    def describe_devices(self, include_properties: bool = True) -> list[DeviceInfo]:
        state = {"FakeCam": {"Exposure": str(self.exposure)}, "ZDrive": {"Position": str(self.z)},
                 "Nosepiece": {"State": str(self.state), "Label": LABELS[self.state]},
                 "DiaLamp": {"State": self.lights["DiaLamp"]},
                 "Aura": {"State": self.lights["Aura"]}}
        for (dev, prop), v in self.props.items():
            state.setdefault(dev, {})[prop] = v
        return [DeviceInfo(label, kind, "fake", f"fake {kind}", True,
                           properties={p: PropertyInfo(v) for p, v in state.get(label, {}).items()}
                           if include_properties else {})
                for label, kind in self.DEVICES]

    def nosepiece_labels(self) -> list[NosepieceLabel]:
        return [NosepieceLabel(o.state, o.label, 6.5 / o.magnification)
                for o in self.info().objectives]

    def piezo_read(self, port: str) -> PiezoReading:
        if not port:
            return PiezoReading("", False)
        if self.piezo_um is None:
            return PiezoReading(port, False, error=f"no piezo on {port}")
        return PiezoReading(port, True, *self.piezo_um)

    def config_record(self) -> ConfigRecord:
        return ConfigRecord("memory", None, False, Readback.of("Core", "AutoShutter", 0, 0))

    def set_property(self, device: str, prop: str, value, *, token=None) -> Readback:
        check_set_property(device, prop, token, camera="FakeCam")
        self._log("set_property", device, prop, str(value))
        self.props[(device, prop)] = str(value)
        return Readback.of(device, prop, value, value)

    def _light(self, dev: str, value: str) -> Readback:
        self._log("light", dev, value)
        if dev not in self.stuck:
            self.lights[dev] = value
        return Readback.of(dev, "State", value, self.lights[dev])

    def lamp_on(self, *, token):
        require_token(token)
        return [self._light("Aura", "0"), self._light("DiaLamp", "1")]

    def lamp_off(self):
        return [self._light("DiaLamp", "0")]

    def aura_line_on(self, line: str, percent: float, *, token):
        require_token(token)
        self.props[("Aura", f"{line.upper()}_Intensity")] = str(int(round(percent * 10)))
        return [self._light("DiaLamp", "0"), self._light("Aura", "1")]

    def aura_off(self):
        return [self._light("Aura", "0")]

    def all_off(self):
        if self.all_off_raises:
            raise OSError("light engine not answering")
        return [self._light("Aura", "0"), self._light("DiaLamp", "0")]

    def move_z(self, z_um: float, *, token) -> float:
        require_token(token)
        self._log("move_z", z_um)
        self.z = z_um
        return self.z + self.z_readback_offset_um

    def move_xy(self, x_um: float, y_um: float, *, token, timeout_s=None):
        require_token(token)
        self._log("move_xy", x_um, y_um)
        self.x, self.y = x_um, y_um
        return self.x, self.y

    def move_xy_rel(self, dx_um: float, dy_um: float, *, token, timeout_s=None):
        require_token(token)
        self._log("move_xy_rel", dx_um, dy_um)
        self.x, self.y = self.x + dx_um, self.y + dy_um
        return self.x, self.y

    def set_nosepiece(self, state: int, *, token) -> Readback:
        require_token(token)
        self._log("set_nosepiece", state)
        self.state = state
        return Readback.of("Nosepiece", "State", state, self.state)

    def pfs_off(self, *, token) -> Readback:
        require_token(token)
        self.pfs_enabled = False
        return Readback.of("PFS", "FocusMaintenance", "Off", "Off")
