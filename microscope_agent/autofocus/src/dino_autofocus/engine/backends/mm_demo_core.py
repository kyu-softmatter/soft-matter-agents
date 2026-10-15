"""Micro-Manager demo devices for the mm-demo backend, without the Backend protocol (T-017).

`DemoDevices` loads pymmcore-plus's `MMConfig_demo.cfg` (simulated devices, no hardware) and
gives the mm-demo backend what it needs in bench terms. Measured on this PC (Micro-Manager
2.0.3 demo adapters, 2026-10-01; T-002 appendix 2):

* **Z**: the demo `Z` (DStage) takes -300..+300 um and refuses anything outside; its origin
  cannot be moved. Bench z (ZDrive um, sample window 2800-3200) maps to it through one
  `ZMap` offset. Everything outside this module sees bench z only. With the default offset
  (3000) the representable bench range is 2700-3300, so the bench retract height 0 is
  **not** reachable on the demo: `ZMap.to_demo` refuses it like any other out-of-range z.
* **XY**: the demo `XY` moves at its `Velocity` property, 10 mm/s by default, so a 50 mm
  move takes 5 s and hits the core's 5 s `waitForDevice` timeout. `open` raises the velocity
  and `move_xy` waits with its own deadline instead of the core timeout.
* **Light**: bench DiaLamp = demo `White Light Shutter`; bench Aura = demo `LED` (a state
  device whose labels stand for the lines) behind `LED Shutter`. `LED Shutter` has no
  `State` property, so it is driven with the shutter API only. The demo LED has no
  intensity; the Aura per-mille intensity is kept here and read back as an emulated
  property (`Intensity (emulated)`), so a record never claims a device read that did not
  happen. The White Light Shutter loads **open**: `open` switches all light off first.
* **Camera**: 2400 x 2400 16-bit like `scripts/mm_grab.py open_core(demo=True)`, in
  "Fluorescent Beads" mode, whose sharpness depends only on demo z (best at demo 0, symmetric,
  same frame for the same z). With the default offset the focus is at bench 3000.
* **Objective**: the demo nosepiece is called `Objective` (6 positions, like the Ti2). Its
  labels are mapped by position to the Ti2 labels the run records name.

Nothing here applies guards. The mm-demo backend calls these methods behind the engine's
motion token; this module only converts coordinates and reads back. pymmcore-plus is
imported inside functions, so importing this module needs no Micro-Manager.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from ..backend import check_set_property

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus

__all__ = [
    "AURA_LINES",
    "BENCH_OBJECTIVE_LABELS",
    "DemoDevices",
    "DemoReadback",
    "DemoUnavailable",
    "DemoZRangeError",
    "ObjectiveRead",
    "ZMap",
    "find_demo_config",
]

DEMO_CONFIG_NAME = "MMConfig_demo.cfg"

# demo device names
DEMO_Z = "Z"
DEMO_XY = "XY"
DEMO_NOSEPIECE = "Objective"
DEMO_LAMP = "White Light Shutter"  # bench DiaLamp
DEMO_LED = "LED"  # bench Aura line selector (state device)
DEMO_LED_SHUTTER = "LED Shutter"  # bench Aura master State; no State property

DEMO_Z_RANGE_UM = (-300.0, 300.0)
DEFAULT_Z_OFFSET_UM = 3000.0  # bench 3000 <-> demo 0, where the Beads frame is sharpest
DEFAULT_XY_VELOCITY = 100.0  # demo XY "Velocity" (mm/s); the demo default is 10
SENSOR_PX = 2400  # Kinetix22-sized, as scripts/mm_grab.py open_core(demo=True)
CAMERA_MODE = "Fluorescent Beads"

#: bench Aura line -> demo LED label. Only GREEN is used on the bench so far (2026-09-30 run);
#: the other line names are Lumencor's and are matched to the nearest demo wavelength.
#: NIR has no demo LED, so the demo refuses it.
AURA_LINES = {"UV": "385nm", "CYAN": "470nm", "GREEN": "550nm", "RED": "635nm"}

#: Ti2 nosepiece State -> Label from the run records (docs/runs/2026-09-30_substrate-scan.md,
#: docs/operations-spec.md). The other positions have not been read on the bench yet.
BENCH_OBJECTIVE_LABELS = {0: "1-Plan Apo LmbdD20 4x", 5: "6-Plan Apo LmbdD0.13 100x Oil"}


class DemoUnavailable(RuntimeError):
    """pymmcore-plus or its Micro-Manager demo adapters are not installed here."""


class DemoZRangeError(ValueError):
    """A bench z the demo Z cannot represent with the current offset."""


@dataclass(frozen=True)
class DemoReadback:
    """A write and what was read afterwards. Same fields as `engine.backend.Readback`, so the
    mm-demo backend converts with `Readback(**dataclasses.asdict(r))`."""

    device: str
    prop: str
    wanted: str
    read: str
    verified: bool
    t: float = field(default_factory=time.time)

    @classmethod
    def of(cls, device: str, prop: str, wanted: Any, read: Any) -> DemoReadback:
        return cls(device, prop, str(wanted), str(read), str(read) == str(wanted))


@dataclass(frozen=True)
class ZMap:
    """Bench z <-> demo z: `demo = bench - offset_um`. The one place the offset lives."""

    offset_um: float = DEFAULT_Z_OFFSET_UM
    demo_min_um: float = DEMO_Z_RANGE_UM[0]
    demo_max_um: float = DEMO_Z_RANGE_UM[1]

    @property
    def bench_range_um(self) -> tuple[float, float]:
        return self.demo_min_um + self.offset_um, self.demo_max_um + self.offset_um

    @property
    def bench_focus_um(self) -> float:
        """Bench z of the demo camera's best focus (demo 0)."""
        return self.offset_um

    def to_demo(self, bench_um: float) -> float:
        demo = float(bench_um) - self.offset_um
        if not (math.isfinite(demo) and self.demo_min_um <= demo <= self.demo_max_um):
            lo, hi = self.bench_range_um
            raise DemoZRangeError(
                f"bench z {bench_um} um is outside the demo Z range: bench {lo:g}-{hi:g} um "
                f"(demo {self.demo_min_um:g}..{self.demo_max_um:g}, offset {self.offset_um:g})")
        return demo

    def to_bench(self, demo_um: float) -> float:
        return float(demo_um) + self.offset_um


@dataclass(frozen=True)
class ObjectiveRead:
    state: int
    demo_label: str
    bench_label: str | None  # None where the Ti2 label at that position is not recorded


def find_demo_config() -> Path:
    """Path of `MMConfig_demo.cfg` in pymmcore-plus's Micro-Manager install."""
    try:
        from pymmcore_plus import find_micromanager
    except ImportError as e:
        raise DemoUnavailable(f"pymmcore-plus is not importable: {e}") from e
    mm_dir = find_micromanager()
    if not mm_dir:
        raise DemoUnavailable("no Micro-Manager install found (run `mmcore install`)")
    cfg = Path(mm_dir) / DEMO_CONFIG_NAME
    if not cfg.is_file():
        raise DemoUnavailable(f"{cfg} does not exist")
    return cfg


class DemoDevices:
    """One loaded demo core. Construct with `open`; `close` switches light off and unloads.

    Uses its own `CMMCorePlus()`, not the shared `CMMCorePlus.instance()`, so a test or a
    second backend cannot see half-configured devices.
    """

    def __init__(self, core: CMMCorePlus, config: Path, zmap: ZMap | None = None):
        self.core = core
        self.config = config
        self.zmap = zmap or ZMap()
        self._aura_permille: dict[str, int] = {}  # emulated per-line intensity
        self.opened_with: list[DemoReadback] = []  # the all_off done by `open`
        self._closed = False

    # -- life

    @classmethod
    def open(cls, *, exposure_ms: float = 10.0, roi: int = 0, zmap: ZMap | None = None,
             xy_velocity: float = DEFAULT_XY_VELOCITY) -> DemoDevices:
        config = find_demo_config()
        from pymmcore_plus import CMMCorePlus

        core = CMMCorePlus()
        try:
            core.setDeviceAdapterSearchPaths([str(config.parent)])
            core.loadSystemConfiguration(str(config))
            core.setAutoShutter(False)  # else every snap would open the lamp shutter
            core.waitForSystem()
            cam = core.getCameraDevice()
            core.setProperty(cam, "OnCameraCCDXSize", SENSOR_PX)
            core.setProperty(cam, "OnCameraCCDYSize", SENSOR_PX)
            core.setProperty(cam, "PixelType", "16bit")
            core.setProperty(cam, "Mode", CAMERA_MODE)
            core.setProperty(DEMO_XY, "Velocity", xy_velocity)
        except Exception as e:
            core.unloadAllDevices()
            raise DemoUnavailable(f"loading {config} failed: {e}") from e
        dev = cls(core, config, zmap)
        dev.set_exposure(exposure_ms)
        dev.set_roi(roi)
        dev.opened_with = dev.all_off()
        return dev

    def close(self) -> list[DemoReadback]:
        """Light off (read back), then unload. A second call does nothing and returns []."""
        if self._closed:
            return []
        self._closed = True
        try:
            return self.all_off()
        finally:
            self.core.unloadAllDevices()

    def __enter__(self) -> DemoDevices:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- camera

    def set_exposure(self, ms: float) -> float:
        self.core.setExposure(ms)
        return float(self.core.getExposure())

    def set_roi(self, size: int) -> tuple[int, int, int, int]:
        """Centred square ROI; 0 (or >= the sensor) = full sensor."""
        self.core.clearROI()
        w, h = self.core.getImageWidth(), self.core.getImageHeight()
        if 0 < size < min(w, h):
            self.core.setROI((w - size) // 2, (h - size) // 2, size, size)
        return tuple(self.core.getROI())

    def snap(self) -> np.ndarray:
        """One mono uint16 frame (H, W)."""
        img = self.core.snap()
        if img.ndim != 2 or img.dtype != np.uint16:
            raise RuntimeError(f"demo camera gave {img.shape} {img.dtype}, not 2-D uint16")
        return img

    # -- Z, bench coordinates

    def z_um(self) -> float:
        return self.zmap.to_bench(self.core.getPosition(DEMO_Z))

    def move_z(self, bench_um: float) -> float:
        """Move to bench z; returns the bench z read back. Out of range: refused, not moved."""
        demo = self.zmap.to_demo(bench_um)
        self.core.setPosition(DEMO_Z, demo)
        self.core.waitForDevice(DEMO_Z)
        return self.z_um()

    # -- XY

    def xy_um(self) -> tuple[float, float]:
        x, y = self.core.getXYPosition(DEMO_XY)
        return float(x), float(y)

    def move_xy(self, x_um: float, y_um: float, *,
                timeout_s: float | None = None) -> tuple[float, float]:
        """Move and wait up to `timeout_s` (default: twice the travel time at the set
        velocity, plus 2 s), not the core's fixed 5 s. Returns the position read back."""
        if timeout_s is None:
            x0, y0 = self.xy_um()
            mm = math.hypot(x_um - x0, y_um - y0) / 1000.0
            velocity = float(self.core.getProperty(DEMO_XY, "Velocity"))
            timeout_s = 2.0 * mm / max(velocity, 1e-6) + 2.0
        self.core.setXYPosition(DEMO_XY, x_um, y_um)
        deadline = time.monotonic() + timeout_s
        while self.core.deviceBusy(DEMO_XY):
            if time.monotonic() > deadline:
                self.core.stop(DEMO_XY)
                raise TimeoutError(f"XY move to ({x_um}, {y_um}) not done in {timeout_s:.1f} s")
            time.sleep(0.01)
        return self.xy_um()

    # -- objective

    def objective(self) -> ObjectiveRead:
        state = int(self.core.getProperty(DEMO_NOSEPIECE, "State"))
        return ObjectiveRead(state, self.core.getProperty(DEMO_NOSEPIECE, "Label"),
                             BENCH_OBJECTIVE_LABELS.get(state))

    def objectives(self) -> list[ObjectiveRead]:
        labels = self.core.getStateLabels(DEMO_NOSEPIECE)
        return [ObjectiveRead(i, lab, BENCH_OBJECTIVE_LABELS.get(i)) for i, lab in
                enumerate(labels)]

    def set_objective(self, state: int) -> DemoReadback:
        n = len(self.core.getStateLabels(DEMO_NOSEPIECE))
        if not 0 <= state < n:
            raise ValueError(f"nosepiece state {state} is not in 0..{n - 1}")
        return self._set_and_read(DEMO_NOSEPIECE, "State", state)

    # -- light, meaning-level, each step read back

    def lamp_on(self) -> list[DemoReadback]:
        """Transmitted lamp (bench DiaLamp). Aura off first, as the bench brightfield order."""
        return [*self.aura_off(), self._shutter(DEMO_LAMP, True)]

    def lamp_off(self) -> list[DemoReadback]:
        return [self._shutter(DEMO_LAMP, False)]

    def aura_line_on(self, line: str, percent: float) -> list[DemoReadback]:
        """Lamp off, then the line's intensity (per-mille, 1 % -> 10), the line, and the
        master shutter last: the order of `scripts/mm_grab.py aura_on`."""
        line = line.upper()
        if line not in AURA_LINES:
            raise ValueError(f"unknown Aura line {line!r}; known: {', '.join(AURA_LINES)}")
        if not 0.0 <= percent <= 100.0:
            raise ValueError(f"Aura percent {percent} is not in 0-100")
        permille = int(round(percent * 10))
        self._aura_permille[line] = permille
        return [*self.lamp_off(),
                DemoReadback.of(DEMO_LED, f"{line}_Intensity (emulated)", permille,
                                self._aura_permille[line]),
                self._set_and_read(DEMO_LED, "Label", AURA_LINES[line]),
                self._shutter(DEMO_LED_SHUTTER, True)]

    def aura_off(self) -> list[DemoReadback]:
        return [self._shutter(DEMO_LED_SHUTTER, False)]

    def all_off(self) -> list[DemoReadback]:
        return [*self.aura_off(), *self.lamp_off()]

    def light_state(self) -> dict[str, str]:
        """Bench names: DiaLamp and Aura are "1"/"0"; AuraLine is the bench line selected."""
        label = self.core.getProperty(DEMO_LED, "Label")
        line = next((k for k, v in AURA_LINES.items() if v == label), "")
        return {"DiaLamp": str(int(self.core.getShutterOpen(DEMO_LAMP))),
                "Aura": str(int(self.core.getShutterOpen(DEMO_LED_SHUTTER))),
                "AuraLine": line}

    # -- helpers

    def set_and_read(self, device: str, prop: str, value: Any, *,
                     token: object = None) -> DemoReadback:
        """Write one property and read it back, through the engine allow-list
        (`check_set_property` with this core's camera): motion devices are refused and
        light properties need the guard token."""
        check_set_property(device, prop, token, camera=self.core.getCameraDevice())
        return self._set_and_read(device, prop, value)

    def _set_and_read(self, device: str, prop: str, value: Any) -> DemoReadback:
        """Unchecked write and readback, for this module's own meaning-level methods."""
        self.core.setProperty(device, prop, value)
        self.core.waitForDevice(device)
        return DemoReadback.of(device, prop, value, self.core.getProperty(device, prop))

    def _shutter(self, device: str, open_: bool) -> DemoReadback:
        self.core.setShutterOpen(device, open_)
        self.core.waitForDevice(device)
        return DemoReadback.of(device, "open", int(open_), int(self.core.getShutterOpen(device)))
