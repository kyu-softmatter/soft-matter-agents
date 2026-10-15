"""mm-demo backend: the engine's Backend protocol on Micro-Manager's demo devices (T-023).

Built on `mm_demo_core.DemoDevices`, which owns the core and the bench <-> demo Z offset.
Everything here is in bench coordinates (PLAN.md 5절). Demo-only rules, each stated in
`info().notes`:

* **Below-range zone.** The demo Z reaches bench 2700-3300 only (offset 3000), but the bench
  retracts to 0 and `FocusAxis.approach` climbs back in steps. A bench z in [0, 2700) parks
  the demo stage at bench 2700 and reads back the commanded z: that readback is
  **simulated**, so the guard's retract and step checks pass without proving anything about
  a real ZDrive. Each such move is logged in `substitutions` as a `demo_retract`
  {commanded_um, physical_bench_um, physical_demo_um}; `read_property("mm-demo",
  "demo_retract")` gives the one in force. z < 0 or > 3300 is refused.
* **PFS.** The demo has none. `pfs()` is simulated: never enabled, "Out of Range" while z is
  in the below-range zone, "In Range" otherwise, so `rotate_nosepiece` can be exercised.
* **Aura lines.** Only GREEN is bench-confirmed; the others map to the nearest demo LED
  wavelength and their readbacks carry `notes["line"] = PROVISIONAL`.
* **Control token** (PLAN.md D15). Motion and switching light on take the guards' token;
  switching off takes none. `set_property` goes through `check_set_property` with the demo
  camera label; light is written under the demo names (White Light Shutter, LED).
* **Discovery** shows the demo `Z` position in bench um, so no demo number leaves the
  backend. There is no piezo.

pymmcore-plus is imported only when the backend opens.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..backend import (
    AURA_LINES,
    PROVISIONAL,
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
    PropertyNotAllowed,
    Readback,
    StageLimits,
    StreamActive,
    check_set_property,
    read_wiring,
    require_token,
)
from .mm_demo_core import (
    AURA_LINES as DEMO_AURA_LABELS,
)
from .mm_demo_core import (
    DEMO_LED,
    DEMO_Z,
    DemoDevices,
    DemoReadback,
    DemoZRangeError,
    ObjectiveRead,
    ZMap,
    find_demo_config,
)

__all__ = ["PSEUDO_DEVICE", "MmDemoBackend"]

PSEUDO_DEVICE = "mm-demo"  # read_property(PSEUDO_DEVICE, ...) answers the demo notes
BENCH_RETRACT_UM = 0.0  # lowest bench z accepted: the full retract
MEASURED_AURA_LINES = ("GREEN",)  # 2026-09-30 bench run
#: bench lens facts by nosepiece State, from docs/runs/2026-09-30_substrate-scan.yaml
BENCH_PIXEL_UM = {0: 1.625, 5: 0.065}
#: states 1-4 are catalog values (guards.FREE_WD_UM, 2026-10-02)
BENCH_FREE_WD_UM = {0: 20000.0, 1: 4000.0, 2: 800.0, 3: 170.0, 4: 150.0, 5: 130.0}


def _readbacks(recs: list[DemoReadback]) -> list[Readback]:
    return [Readback(**asdict(r)) for r in recs]


def _magnification(label: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)\s*[xX]\b", label)
    return float(m.group(1)) if m else 0.0  # 0 = not in the label (demo "Objective-2")


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


class MmDemoBackend:
    kind = "mm-demo"

    def __init__(self, *, exposure_ms: float = 10.0, roi: int = 0,
                 z_offset_um: float | None = None):
        self._exposure_ms, self._roi = exposure_ms, roi
        self.zmap = ZMap() if z_offset_um is None else ZMap(offset_um=z_offset_um)
        self.dev: DemoDevices | None = None
        self.substitutions: list[dict[str, Any]] = []
        self._below_z: float | None = None  # commanded z while in the below-range zone
        self._config: ConfigRecord | None = None
        self._streaming = False

    # -- life

    def open(self) -> BackendInfo:
        if self.dev is None:
            cfg = find_demo_config()
            before = _sha256(cfg)
            self.dev = DemoDevices.open(exposure_ms=self._exposure_ms, roi=self._roi,
                                        zmap=self.zmap)
            after = _sha256(cfg)
            core = self.dev.core
            self._config = ConfigRecord(
                str(cfg), after, None if before is None or after is None else before != after,
                Readback.of("Core", "AutoShutter", 0, int(core.getAutoShutter())),
                "System/Startup" if "Startup" in core.getAvailableConfigs("System") else None,
                time.time(), {"config": "Micro-Manager demo devices, no hardware"})
        return self.info()

    def close(self) -> None:
        if self.dev is not None:
            self.stop_stream()
            dev, self.dev = self.dev, None
            dev.close()

    def __enter__(self) -> MmDemoBackend:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _d(self) -> DemoDevices:
        if self.dev is None:
            raise RuntimeError("mm-demo backend is not open")
        return self.dev

    def info(self) -> BackendInfo:
        d = self._d()
        core, cam = d.core, d.core.getCameraDevice()
        now = d.objective()
        return BackendInfo(
            kind=self.kind, config=str(d.config), camera=cam,
            sensor=(int(core.getProperty(cam, "OnCameraCCDXSize")),
                    int(core.getProperty(cam, "OnCameraCCDYSize"))),
            roi=tuple(core.getROI()), exposure_ms=float(core.getExposure()),
            pixel_um=BENCH_PIXEL_UM.get(now.state, float(core.getPixelSizeUm())),
            objective=self._label(now), intermediate_mag=None,
            bit_depth=int(core.getProperty(cam, "BitDepth")),
            objectives=[self._objective_info(o) for o in d.objectives()],
            stage_limits=StageLimits(None, None, (BENCH_RETRACT_UM, self.zmap.bench_range_um[1])),
            notes=self.notes(), bench=False,
        )

    def notes(self) -> dict[str, str]:
        lo, hi = self.zmap.bench_range_um
        return {
            "z_offset_um": f"{self.zmap.offset_um:g} (demo z = bench z - offset)",
            "z_below_range": (f"bench z {BENCH_RETRACT_UM:g}-{lo:g} um parks the demo stage at "
                              f"{lo:g}; readback in that zone is simulated (demo_retract)"),
            "z_reachable_um": f"{lo:g}-{hi:g}",
            "pfs": "simulated: the demo has no PFS",
            "piezo": "none on the demo",
            **{f"aura.{line}": PROVISIONAL for line in AURA_LINES
               if line not in MEASURED_AURA_LINES},
            "objectives": (f"Ti2 labels known for states {sorted(BENCH_PIXEL_UM)}; "
                           "other positions show the demo label"),
        }

    # -- camera

    def snap(self) -> Frame:
        if self._streaming:
            raise StreamActive("stop the stream before snap()")
        d = self._d()
        return self._frame(d.snap(), float(d.core.getExposure()))

    def set_exposure(self, ms: float) -> float:
        return self._d().set_exposure(ms)

    def set_roi(self, size: int) -> tuple[int, int, int, int]:
        return self._d().set_roi(size)

    # -- stream

    def start_stream(self, interval_ms: float | None = None) -> None:
        core = self._d().core
        if self._streaming:
            return
        core.startContinuousSequenceAcquisition(float(interval_ms or 0.0))
        self._streaming = True

    def next_frame(self, timeout_s: float = 1.0) -> Frame | None:
        if not self._streaming:
            return None
        core = self._d().core
        deadline = time.monotonic() + timeout_s
        while core.getRemainingImageCount() == 0:
            if time.monotonic() > deadline:
                return None
            time.sleep(0.002)
        img = core.getLastImage()  # the newest; older ones are dropped
        core.clearCircularBuffer()
        return self._frame(img, float(core.getExposure()))

    def stop_stream(self) -> None:
        if self._streaming and self.dev is not None:
            self.dev.core.stopSequenceAcquisition()
        self._streaming = False

    def streaming(self) -> bool:
        return self._streaming

    # -- reads

    def positions(self) -> Positions:
        d, p = self._d(), Positions()
        try:
            p.x_um, p.y_um = d.xy_um()
        except Exception as e:  # a failed read is a field, not an exception
            p.errors["xy"] = str(e)
        try:
            p.z_um = self._z_read()
        except Exception as e:
            p.errors["z"] = str(e)
        return p

    def read_property(self, device: str, prop: str) -> str:
        if device == PSEUDO_DEVICE:
            if prop == "notes":
                return json.dumps(self.notes())
            if prop == "demo_retract":  # the substitution in force now, "" if none
                last = next((s for s in reversed(self.substitutions)
                             if s["kind"] == "demo_retract"), None)
                return json.dumps(last) if self._below_z is not None and last else ""
            raise KeyError(f"{PSEUDO_DEVICE} has no property {prop!r}")
        if device == DEMO_Z and prop == "Position":
            return f"{self._z_read():.4f}"  # bench um: no demo number leaves the backend
        return str(self._d().core.getProperty(device, prop))

    def nosepiece(self) -> str:
        return self._label(self._d().objective())

    def pfs(self) -> PfsState:
        return PfsState(False, False, "Out of Range" if self._below_z is not None else "In Range")

    def light_state(self) -> dict[str, str]:
        return self._d().light_state()

    # -- discovery: reads only

    def describe_devices(self, include_properties: bool = True) -> list[DeviceInfo]:
        core = self._d().core
        out = []
        for label in core.getLoadedDevices():
            dtype = core.getDeviceType(label)
            desc = str(core.getDeviceDescription(label))
            if label == DEMO_Z:
                desc += f" (Position in bench um: demo + {self.zmap.offset_um:g})"
            props = {}
            if include_properties:
                for name in core.getDevicePropertyNames(label):
                    props[name] = self._property_info(label, name)
            tname = getattr(dtype, "name", str(dtype))
            out.append(DeviceInfo(label, tname,
                                  str(core.getDeviceLibrary(label)), desc, True,
                                  properties=props, **read_wiring(core, label, tname)))
        return out

    def nosepiece_labels(self) -> list[NosepieceLabel]:
        return [NosepieceLabel(o.state, self._label(o), BENCH_PIXEL_UM.get(o.state))
                for o in self._d().objectives()]

    def piezo_read(self, port: str) -> PiezoReading:
        return PiezoReading(port, False, error=f"no piezo on mm-demo ({port})" if port else None)

    def config_record(self) -> ConfigRecord:
        self._d()
        if self._config is None:  # open() always sets it
            raise RuntimeError("mm-demo backend has no config record")
        return self._config

    # -- writes

    def set_property(self, device: str, prop: str, value: Any, *,
                     token: object = None) -> Readback:
        core = self._d().core
        check_set_property(device, prop, token, camera=core.getCameraDevice())
        if device not in core.getLoadedDevices():  # e.g. the bench names Aura, DiaLamp
            raise PropertyNotAllowed(f"{device!r} is not a device on mm-demo; light is written "
                                     "as White Light Shutter.State or LED.Label/State")
        return Readback(**asdict(self._d().set_and_read(device, prop, value, token=token)))

    def lamp_on(self, *, token: object = None) -> list[Readback]:
        require_token(token)
        return _readbacks(self._d().lamp_on())

    def lamp_off(self) -> list[Readback]:
        return _readbacks(self._d().lamp_off())

    def aura_line_on(self, line: str, percent: float, *,
                     token: object = None) -> list[Readback]:
        require_token(token)
        line = line.upper()
        recs = _readbacks(self._d().aura_line_on(line, percent))
        if line not in MEASURED_AURA_LINES:
            for r in recs:
                if r.device == DEMO_LED and r.prop == "Label":
                    r.notes.update(line=PROVISIONAL, bench_line=line)
            self.substitutions.append({"kind": "aura_line", "line": line,
                                       "demo_label": DEMO_AURA_LABELS[line],
                                       "status": PROVISIONAL, "t": time.time()})
        return recs

    def aura_off(self) -> list[Readback]:
        return _readbacks(self._d().aura_off())

    def all_off(self) -> list[Readback]:
        return _readbacks(self._d().all_off())

    # -- motion: engine.guards only

    def move_z(self, z_um: float, *, token: object) -> float:
        require_token(token)
        d = self._d()
        z = float(z_um)
        lo, hi = self.zmap.bench_range_um
        if not (math.isfinite(z) and BENCH_RETRACT_UM <= z <= hi):
            raise DemoZRangeError(f"bench z {z_um} um is outside {BENCH_RETRACT_UM:g}-{hi:g} um "
                                  "on the demo")
        if z >= lo:
            self._below_z = None
            return d.move_z(z)
        physical = d.move_z(lo)
        self.substitutions.append({"kind": "demo_retract", "commanded_um": z,
                                   "physical_bench_um": physical,
                                   "physical_demo_um": d.core.getPosition(DEMO_Z),
                                   "t": time.time()})
        if abs(physical - lo) > 0.01:  # the park itself failed: report what was read
            self._below_z = None
            return physical
        self._below_z = z
        return z

    def move_xy(self, x_um: float, y_um: float, *, token: object,
                timeout_s: float | None = None) -> tuple[float, float]:
        require_token(token)
        return self._d().move_xy(x_um, y_um, timeout_s=timeout_s)

    def move_xy_rel(self, dx_um: float, dy_um: float, *, token: object,
                    timeout_s: float | None = None) -> tuple[float, float]:
        require_token(token)
        x, y = self._d().xy_um()
        return self._d().move_xy(x + float(dx_um), y + float(dy_um), timeout_s=timeout_s)

    def set_nosepiece(self, state: int, *, token: object) -> Readback:
        require_token(token)
        return Readback(**asdict(self._d().set_objective(state)))

    def pfs_off(self, *, token: object) -> Readback:
        require_token(token)
        return Readback.of("PFS", "FocusMaintenance", "Off", "Off",
                           notes={"pfs": "simulated: the demo has no PFS"})

    # -- helpers

    def _frame(self, img, exposure_ms: float) -> Frame:
        p = self.positions()
        return Frame(img, time.time(), exposure_ms, p.x_um, p.y_um, p.z_um,
                     camera=self._d().core.getCameraDevice() or None)

    def _z_read(self) -> float:
        """The simulated z only while the demo stage still sits at the zone floor; if it
        moved off (anything but this backend moved it), the physical z."""
        z = self._d().z_um()
        if self._below_z is not None and abs(z - self.zmap.bench_range_um[0]) <= 0.01:
            return self._below_z
        return z

    def _property_info(self, label: str, name: str) -> PropertyInfo:
        core = self._d().core
        try:
            value = str(core.getProperty(label, name))
            if label == DEMO_Z and name == "Position":
                value = f"{self._z_read():.4f}"
            limits = ((float(core.getPropertyLowerLimit(label, name)),
                       float(core.getPropertyUpperLimit(label, name)))
                      if core.hasPropertyLimits(label, name) else None)
            return PropertyInfo(value, bool(core.isPropertyReadOnly(label, name)),
                                [str(v) for v in core.getAllowedPropertyValues(label, name)],
                                limits)
        except Exception as e:  # a failed read is a field
            return PropertyInfo(None, read_ok=False, error=f"{type(e).__name__}: {e}")

    @staticmethod
    def _label(o: ObjectiveRead) -> str:
        return o.bench_label or o.demo_label

    def _objective_info(self, o: ObjectiveRead) -> ObjectiveInfo:
        return ObjectiveInfo(o.state, self._label(o), _magnification(self._label(o)),
                             BENCH_PIXEL_UM.get(o.state), BENCH_FREE_WD_UM.get(o.state))
