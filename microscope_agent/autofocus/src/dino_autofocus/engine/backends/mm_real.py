"""mm-real backend: the Backend protocol (T-002 + T-015) on the bench Ti2 / Kinetix / Aura.

Ported from `scripts/mm_grab.py` (`open_core`, `set_and_read`, `aura_on/off`, `positions`,
`PiezoReader.read`) and `scripts/change_objective.py` (`state`), both deleted in R-05 (in git
history). pymmcore-plus is imported
only when the backend opens; the piezo DLL only when the piezo is read.

- **Config**: `config_path()` = the argument, else `DINO_AF_MM_CONFIG`, else `"mm_config"`
  in the settings folder's settings.json (`auth.config.config_dir`), else `BENCH_CONFIG`.
  Loading applies the file's System/Startup preset (`LappMainBranch1 State 1`); AutoShutter
  goes off straight after, as mm_grab does, else every snap would switch the light on. Both
  facts are in `config_record()`. **Before loading (T-036b)** the `.cfg` text is parsed and
  the load is refused (`UnsafeConfig`, naming every device.property) if the Startup or
  Shutdown preset or a post-init `Property` line sets a motion device; then a private copy of
  exactly the checked bytes is loaded. What loading sets is in `config_record().notes`.
  Motion devices are the fixed names, the labels the cfg assigns as Core Focus / XYStage /
  AutoFocus, and this backend's `DeviceNames`; a Core role that differs from `DeviceNames`
  is refused too (T-036d).
- **Bench-flagged**: `info().bench` is True, so the guards and the runner require a
  clearance callback for `FocusAxis.approach()` on this backend.
- **Device names** come from one `DeviceNames` (bench by default). `DEMO_DEVICES` points the
  same code at Micro-Manager's demo config, which is how the tests run it on a desktop: no
  Aura, no PFS, the lamp is "White Light Shutter".
- Motion and light-on take the guard token; off never does; `set_property` goes through
  `check_set_property` with the camera label. Z is ZDrive um as the stand reports it: the
  bench coordinates *are* the stand's, no offset.
- **Piezo: read only.** `piezo_read(port)` opens the NanoBench session, reads the three
  measured positions and closes. No position command, no security-level change: piezo moves
  are out of scope (operations-spec 9.2, M5).
- Failed reads are fields (`Positions.errors`, `PropertyInfo.read_ok`, `PiezoReading.error`).
- **SAFETY, bench motion is locked (T-036).** `BENCH_MOTION` ships as "LOCKED". While it is
  anything but "UNLOCKED", every motion method (`move_z`, `move_xy`, `move_xy_rel`,
  `set_nosepiece`) raises `BenchMotionLocked` before touching the core, so nothing that
  guards' `move_to` / `park_at` / `approach` / `sweep` or `rotate_nosepiece` reaches can move
  the stand. Reads, frames, streams, light on/off (D15) and PFS off stay allowed. Only a
  reviewed commit that edits the constant lifts it: no argument, environment variable,
  config file or setting is read for it. Lifting waits for T-027 (approach refuses without
  clearance on bench) and the T-011 bench check, with the manager's and director's sign-off.

Nothing here has run on the stand: what only the microscope PC can confirm is listed in
`USER_CHECKS` (and `info().notes["user_check"]`).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..backend import (
    AURA_LINES,
    MOTION_DEVICES,
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
    PropertyNotAllowed,
    Readback,
    StageLimits,
    StreamActive,
    check_set_property,
    read_wiring,
    require_token,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus

__all__ = ["BENCH_CONFIG", "BENCH_DEVICES", "BENCH_MOTION", "DEMO_DEVICES", "USER_CHECKS",
           "BenchMotionLocked", "DeviceNames", "LoadSetting", "MmRealBackend", "MmUnavailable",
           "UnsafeConfig", "check_load_settings", "config_path", "load_time_settings"]

#: SAFETY (T-036): ships "LOCKED". Lifted only by a reviewed commit that edits this line,
#: after T-027 and the T-011 bench check are on main. Nothing else may set or override it.
BENCH_MOTION = "LOCKED"
MOTION_LOCK_REASON = "bench motion locked until clearance guards land (T-027, T-011)"

#: Off on the stand (user, 2026-10-02): `hardware_scan` does not ask the bench hubs
#: (Ti2-E__0, NIDAQHub) for their installed peripherals until that query is checked on the
#: microscope PC (USER_CHECKS). Only a reviewed edit of this line turns it on.
READ_HUB_PERIPHERALS = False

BENCH_CONFIG = Path(r"C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg")
CONFIG_ENV = "DINO_AF_MM_CONFIG"
SETTINGS_KEY = "mm_config"
MEASURED_AURA_LINES = ("GREEN",)  # 2026-09-30 bench run
#: lens facts by nosepiece State, docs/runs/2026-09-30_substrate-scan.yaml; others unknown
BENCH_PIXEL_UM = {0: 1.625, 5: 0.065}
#: states 1-4 are catalog values (guards.FREE_WD_UM, 2026-10-02)
BENCH_FREE_WD_UM = {0: 20000.0, 1: 4000.0, 2: 800.0, 3: 170.0, 4: 150.0, 5: 130.0}
DEFAULT_XY_TIMEOUT_S = 30.0  # unmeasured provisional: a full-travel XY move on the Ti2

#: what only the microscope PC can confirm (review request "user check needed"; checklist)
USER_CHECKS = (
    "config path and Micro-Manager install (adapter search path) on the microscope PC",
    "Core AutoFocus device is the PFS, so enable/isContinuousFocus* address it",
    "PFS off by enableContinuousFocus(False) reads back as disabled",
    "Aura State 0 switches every line off (checklist Q10)",
    "XYStage readback after a move vs the command (checklist Q11)",
    "XY wait: DEFAULT_XY_TIMEOUT_S covers the longest move",
    "Kinetix Port that gave 2026-09-30's ReadoutRate 100MHz 12bit (2026-10-02 shows 16bit only)",
    "opening the NanoBench session for a read changes nothing (checklist Q19)",
    "stage travel limits (StageLimits are None until read)",
    "before READ_HUB_PERIPHERALS goes on: hub getInstalledDevices (Ti2-E__0, NIDAQHub) only reads",
)


class MmUnavailable(RuntimeError):
    """pymmcore-plus, the Micro-Manager install or the config is missing, or loading failed."""


class BenchMotionLocked(RuntimeError):
    """A motion call on mm-real while `BENCH_MOTION` is locked (T-036)."""


def _motion_state() -> str:
    """Fail-safe: anything but exactly "UNLOCKED" is locked. The one read of BENCH_MOTION."""
    return "UNLOCKED" if BENCH_MOTION == "UNLOCKED" else f"LOCKED: {MOTION_LOCK_REASON}"


def _require_motion_unlocked(what: str) -> None:
    if _motion_state() != "UNLOCKED":
        raise BenchMotionLocked(f"{what}: {MOTION_LOCK_REASON}")


# ---------------------------------------------------------------- load-time settings (T-036b)
#: presets Micro-Manager applies by itself: System/Startup right after loading; System/Shutdown
#: is checked too in case the core applies it when it unloads
LOAD_TIME_PRESETS = (("System", "Startup"), ("System", "Shutdown"))
#: Core is in MOTION_DEVICES against run-time re-routing (Core.Focus / XYStage); at load its
#: lines only assign roles, so they are recorded, not refused
LOAD_CHECK_DEVICES = MOTION_DEVICES - {"Core"}


class UnsafeConfig(RuntimeError):
    """The config would set a motion device while loading (T-036b). Nothing was loaded."""


@dataclass(frozen=True)
class LoadSetting:
    where: str  # "ConfigGroup System/Startup" or "post-init Property"
    device: str
    prop: str
    value: str

    def text(self) -> str:
        return f"{self.where}: {self.device}.{self.prop}={self.value}"


def load_time_settings(cfg_text: str) -> list[LoadSetting]:
    """What loading this `.cfg` sets by itself: the `Property` lines after
    `Property,Core,Initialize,1` and every setting of the `LOAD_TIME_PRESETS`. Pre-init
    `Property` lines (ports, hubs) are needed to load a device and set nothing on it."""
    out, initialized = [], False
    for raw in cfg_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if parts[0] == "Property" and len(parts) >= 3:
            value = ",".join(parts[3:])
            if parts[1] == "Core" and parts[2] == "Initialize":
                initialized = value == "1"
            elif initialized:
                out.append(LoadSetting("post-init Property", parts[1], parts[2], value))
        elif parts[0] == "ConfigGroup" and len(parts) >= 5 and \
                (parts[1], parts[2]) in LOAD_TIME_PRESETS:
            out.append(LoadSetting(f"ConfigGroup {parts[1]}/{parts[2]}", parts[3], parts[4],
                                   ",".join(parts[5:])))
    return out


#: Core role properties a cfg sets at load, and the `DeviceNames` field each must match
CORE_ROLES = {"Focus": "z", "XYStage": "xy", "AutoFocus": "pfs"}


def check_load_settings(settings: list[LoadSetting], name: str,
                        devices: DeviceNames | None = None) -> None:
    """Refuse a config that sets any motion device while loading, naming every one.

    Motion devices (T-036d: a bench cfg may name its stage otherwise) are
    `LOAD_CHECK_DEVICES`, the labels the cfg's own Core role lines assign (Core.Focus /
    XYStage / AutoFocus) and, given `devices`, the labels this backend drives as Z, XY,
    nosepiece and PFS. With `devices`, a Core role that names another label than the backend
    drives is refused too: the guards would read one device while the core moves another.
    """
    roles = {s.prop: s.value for s in settings
             if s.device == "Core" and s.prop in CORE_ROLES and s.value}
    motion = set(LOAD_CHECK_DEVICES) | set(roles.values())
    if devices is not None:
        motion |= set(devices.motion_labels())
    motion.discard("Core")
    bad: dict[str, list[str]] = {}
    for s in settings:
        if s.device in motion:
            bad.setdefault(s.where, []).append(f"{s.device}.{s.prop}")
    problems = [f"{', '.join(v)} in {w}" for w, v in bad.items()]
    if devices is not None:
        for prop, label in roles.items():
            field = CORE_ROLES[prop]
            want = getattr(devices, field)
            if want != label:
                problems.append(f"role mismatch: Core.{prop} is {label!r} but this backend "
                                f"drives {want!r} as {field}")
    if problems:
        raise UnsafeConfig(f"{name} would move the stand while loading, or moves a device "
                           f"the guards do not read: {'; '.join(problems)}. Fix the config "
                           "(or DeviceNames); motion goes only through the guards")


@dataclass(frozen=True)
class DeviceNames:
    """Micro-Manager labels of the devices the protocol talks to. None = not on this config."""

    z: str = "ZDrive"
    xy: str = "XYStage"
    nosepiece: str = "Nosepiece"
    pfs: str | None = "PFS"
    dialamp: str = "DiaLamp"
    aura: str | None = "Aura"
    intermediate_mag: str | None = "IntermediateMagnification"

    def motion_labels(self) -> tuple[str, ...]:
        """The labels that move the stand: Z, XY, nosepiece and PFS (when present)."""
        return tuple(d for d in (self.z, self.xy, self.nosepiece, self.pfs) if d)


BENCH_DEVICES = DeviceNames()
#: Micro-Manager's MMConfig_demo.cfg, for desktop tests of this code only
DEMO_DEVICES = DeviceNames(z="Z", xy="XY", nosepiece="Objective", pfs=None,
                           dialamp="White Light Shutter", aura=None, intermediate_mag=None)


def config_path(override: str | os.PathLike[str] | None = None) -> Path:
    if override is not None:
        return Path(override)
    env = os.environ.get(CONFIG_ENV, "").strip()
    if env:
        return Path(env)
    from ...auth.config import SETTINGS_FILE, config_dir

    try:
        settings = json.loads((config_dir() / SETTINGS_FILE).read_text(encoding="utf-8"))
        if settings.get(SETTINGS_KEY):
            return Path(settings[SETTINGS_KEY])
    except (OSError, ValueError):
        pass
    return BENCH_CONFIG


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _magnification(label: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)\s*[xX]\b", label)
    return float(m.group(1)) if m else 0.0


class MmRealBackend:
    kind = "mm-real"

    def __init__(self, config: str | os.PathLike[str] | None = None, *,
                 devices: DeviceNames = BENCH_DEVICES, mm_dir: str | None = None,
                 exposure_ms: float = 10.0, roi: int = 0):
        self.config = config_path(config)
        self.devices, self.mm_dir = devices, mm_dir
        self._exposure_ms, self._roi = exposure_ms, roi
        self.core: CMMCorePlus | None = None
        self._config: ConfigRecord | None = None
        self._sensor: tuple[int, int] = (0, 0)
        self._streaming = False

    # -- life
    def open(self) -> BackendInfo:
        if self.core is not None:
            return self.info()
        if not self.config.is_file():
            raise MmUnavailable(f"config {self.config} does not exist")
        # T-036b: check what loading would set before anything loads, then load a private
        # copy of exactly the checked bytes, so a file changed in between cannot slip past
        data = self.config.read_bytes()
        settings = load_time_settings(data.decode("utf-8", errors="replace"))
        check_load_settings(settings, self.config.name, self.devices)
        try:
            from pymmcore_plus import CMMCorePlus, find_micromanager
        except ImportError as e:
            raise MmUnavailable(f"pymmcore-plus is not importable: {e}") from e
        mm_dir = self.mm_dir or find_micromanager()
        if not mm_dir:
            raise MmUnavailable("no Micro-Manager install found")
        checked = hashlib.sha256(data).hexdigest()
        core = CMMCorePlus()  # its own core: nothing else sees half-loaded devices
        with tempfile.TemporaryDirectory(prefix="dino_af_cfg_") as tmp:
            copy = Path(tmp) / self.config.name
            copy.write_bytes(data)
            try:
                core.setDeviceAdapterSearchPaths([str(mm_dir)])
                core.loadSystemConfiguration(str(copy))
                core.setAutoShutter(False)  # as loaded, every snap would switch the light on
                core.waitForSystem()
            except Exception as e:
                core.unloadAllDevices()
                raise MmUnavailable(f"loading {self.config} failed: {e}") from e
        after = _sha256(self.config)
        self.core = core
        startup = "System/Startup" if "System" in core.getAvailableConfigGroups() and \
            "Startup" in core.getAvailableConfigs("System") else None
        self._config = ConfigRecord(
            str(self.config), checked, None if after is None else after != checked,
            Readback.of("Core", "AutoShutter", 0, int(core.getAutoShutter())), startup,
            time.time(), {"mm_dir": str(mm_dir),
                          "loaded": "a private copy of the checked bytes (T-036b)",
                          "load_settings": "; ".join(s.text() for s in settings) or "none"})
        core.setExposure(self._exposure_ms)
        core.clearROI()
        self._sensor = (int(core.getImageWidth()), int(core.getImageHeight()))
        self.set_roi(self._roi)
        return self.info()

    def close(self) -> None:
        """Stream off, then unload. Lights are the guards' (`exclusive` switches them off
        before close); a second call does nothing."""
        if self.core is None:
            return
        self.stop_stream()
        core, self.core = self.core, None
        core.unloadAllDevices()

    def __enter__(self) -> MmRealBackend:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _c(self) -> CMMCorePlus:
        if self.core is None:
            raise RuntimeError("mm-real backend is not open")
        return self.core

    def _has(self, device: str | None) -> bool:
        return device is not None and device in self._c().getLoadedDevices()

    def _prop(self, device: str | None, *names: str) -> str | None:
        """First of `names` the device has; None if neither (a record must not stop a run)."""
        if not self._has(device):
            return None
        for name in names:
            if self._c().hasProperty(device, name):
                return str(self._c().getProperty(device, name))
        return None

    def info(self) -> BackendInfo:
        core, d = self._c(), self.devices
        notes = {"bench_motion": _motion_state(),
                 "user_check": "; ".join(USER_CHECKS),
                 "stage_limits": "not read: user check needed",
                 "xy_timeout_s": f"{DEFAULT_XY_TIMEOUT_S:g}, {PROVISIONAL}",
                 **{f"aura.{ln}": PROVISIONAL for ln in AURA_LINES
                    if ln not in MEASURED_AURA_LINES}}
        if d != BENCH_DEVICES:
            notes["devices"] = f"not the bench names: {d}"
        return BackendInfo(
            self.kind, str(self.config), core.getCameraDevice(), self._sensor,
            tuple(int(v) for v in core.getROI()), float(core.getExposure()),
            float(core.getPixelSizeUm()), self.nosepiece(),
            self._prop(d.intermediate_mag, "Label", "State"), int(core.getImageBitDepth()),
            [ObjectiveInfo(i, lab, _magnification(lab), BENCH_PIXEL_UM.get(i),
                           BENCH_FREE_WD_UM.get(i)) for i, lab in self._labels()],
            StageLimits(), notes, bench=True)

    # -- camera
    def _frame(self, img) -> Frame:
        p = self.positions()
        return Frame(img, time.time(), float(self._c().getExposure()), p.x_um, p.y_um, p.z_um,
                     camera=self._c().getCameraDevice() or None)

    def snap(self) -> Frame:
        if self._streaming:
            raise StreamActive("stop the stream before snap()")
        img = self._c().snap()
        if img.ndim != 2:
            raise RuntimeError(f"camera gave a {img.shape} image, not 2-D mono")
        return self._frame(img)

    def set_exposure(self, ms: float) -> float:
        self._c().setExposure(float(ms))
        return float(self._c().getExposure())

    def set_roi(self, size: int) -> tuple[int, int, int, int]:
        """Centred square ROI; 0 (or >= the sensor) = full sensor."""
        core = self._c()
        core.clearROI()
        w, h = self._sensor
        if 0 < size < min(w, h):
            core.setROI((w - size) // 2, (h - size) // 2, size, size)
        return tuple(int(v) for v in core.getROI())

    # -- stream (engine-owned, T-011)
    def start_stream(self, interval_ms: float | None = None) -> None:
        if self._streaming:
            return
        self._c().startContinuousSequenceAcquisition(float(interval_ms or 0.0))
        self._streaming = True

    def next_frame(self, timeout_s: float = 1.0) -> Frame | None:
        if not self._streaming:
            return None
        core = self._c()
        deadline = time.monotonic() + timeout_s
        while core.getRemainingImageCount() == 0:
            if time.monotonic() > deadline:
                return None
            time.sleep(0.002)
        img = core.getLastImage()  # the newest; older ones are dropped
        core.clearCircularBuffer()
        return self._frame(img)

    def stop_stream(self) -> None:
        if self._streaming and self.core is not None:
            self.core.stopSequenceAcquisition()
        self._streaming = False

    def streaming(self) -> bool:
        return self._streaming

    # -- reads
    def positions(self) -> Positions:
        core, p = self._c(), Positions()
        try:
            x, y = core.getXYPosition(self.devices.xy)
            p.x_um, p.y_um = float(x), float(y)
        except Exception as e:  # a missing stage must not stop the camera
            p.errors["xy"] = f"{type(e).__name__}: {e}"
        try:
            p.z_um = float(core.getPosition(self.devices.z))
        except Exception as e:
            p.errors["z"] = f"{type(e).__name__}: {e}"
        return p

    def read_property(self, device: str, prop: str) -> str:
        return str(self._c().getProperty(device, prop))

    def _nosepiece_state(self) -> int:
        return int(self._c().getProperty(self.devices.nosepiece, "State"))

    def _labels(self) -> list[tuple[int, str]]:
        return list(enumerate(self._c().getStateLabels(self.devices.nosepiece)))

    def nosepiece(self) -> str:
        return str(self._c().getProperty(self.devices.nosepiece, "Label"))

    def pfs(self) -> PfsState:
        """change_objective.state: Core continuous focus enabled / locked, `PFS in Range`."""
        core = self._c()
        if not self._has(self.devices.pfs):
            return PfsState(None, None, None)
        out: list[Any] = []
        for fn in (core.isContinuousFocusEnabled, core.isContinuousFocusLocked):
            try:
                out.append(bool(fn()))
            except Exception:  # unreadable stays None; the guards treat None as not quiet
                out.append(None)
        return PfsState(*out, self._prop(self.devices.pfs, "PFS in Range"))

    def light_state(self) -> dict[str, str]:
        out = {"DiaLamp": self._prop(self.devices.dialamp, "State") or "unreadable"}
        if self.devices.aura is not None:
            out["Aura"] = self._prop(self.devices.aura, "State") or "unreadable"
        return out

    # -- discovery: reads only
    def describe_devices(self, include_properties: bool = True) -> list[DeviceInfo]:
        core = self._c()
        out = []
        for label in core.getLoadedDevices():
            props = {n: self._property_info(label, n) for n in core.getDevicePropertyNames(label)}
            dtype = core.getDeviceType(label)
            tname = getattr(dtype, "name", str(dtype))
            out.append(DeviceInfo(label, tname,
                                  str(core.getDeviceLibrary(label)),
                                  str(core.getDeviceDescription(label)),
                                  all(p.read_ok for p in props.values()),
                                  properties=props if include_properties else {},
                                  **read_wiring(core, label, tname,
                                                hub_peripherals=READ_HUB_PERIPHERALS)))
        return out

    def _property_info(self, label: str, name: str) -> PropertyInfo:
        core = self._c()
        try:
            limits = ((float(core.getPropertyLowerLimit(label, name)),
                       float(core.getPropertyUpperLimit(label, name)))
                      if core.hasPropertyLimits(label, name) else None)
            return PropertyInfo(str(core.getProperty(label, name)),
                                bool(core.isPropertyReadOnly(label, name)),
                                [str(v) for v in core.getAllowedPropertyValues(label, name)],
                                limits)
        except Exception as e:  # a failed read is a field
            return PropertyInfo(None, read_ok=False, error=f"{type(e).__name__}: {e}")

    def nosepiece_labels(self) -> list[NosepieceLabel]:
        here, px = self._nosepiece_state(), float(self._c().getPixelSizeUm())
        return [NosepieceLabel(i, lab, BENCH_PIXEL_UM.get(i, px if i == here else None))
                for i, lab in self._labels()]

    def piezo_read(self, port: str) -> PiezoReading:
        if not port:
            return PiezoReading("", False)
        try:
            with _PiezoReadOnly(port) as pz:
                xyz = pz.read()
        except Exception as e:  # DLL missing, port held by the NanoBench program, ...
            return PiezoReading(port, False, error=f"{type(e).__name__}: {e}")
        return PiezoReading(port, True, xyz.get("x"), xyz.get("y"), xyz.get("z"))

    def config_record(self) -> ConfigRecord:
        self._c()
        assert self._config is not None  # open() sets it
        return self._config

    # -- writes
    def _set_and_read(self, device: str, prop: str, value: Any,
                      notes: dict[str, str] | None = None) -> Readback:
        core = self._c()
        core.setProperty(device, prop, value)
        core.waitForDevice(device)
        return Readback.of(device, prop, value, core.getProperty(device, prop), notes)

    def set_property(self, device: str, prop: str, value: Any, *,
                     token: MotionToken | None = None) -> Readback:
        check_set_property(device, prop, token, camera=self._c().getCameraDevice())
        if not self._has(device):
            raise PropertyNotAllowed(f"{device!r} is not loaded from {self.config.name}")
        line = prop.removesuffix("_Intensity")
        notes = {"aura_line": PROVISIONAL} if device == self.devices.aura and \
            line in AURA_LINES and line not in MEASURED_AURA_LINES else None
        return self._set_and_read(device, prop, value, notes)

    def lamp_on(self, *, token: MotionToken) -> list[Readback]:
        """Transmitted lamp: Aura off first, then DiaLamp State 1."""
        require_token(token)
        return [*self.aura_off(), self._set_and_read(self.devices.dialamp, "State", 1)]

    def lamp_off(self) -> list[Readback]:
        return [self._set_and_read(self.devices.dialamp, "State", 0)]

    def aura_line_on(self, line: str, percent: float, *, token: MotionToken) -> list[Readback]:
        """mm_grab.aura_on: DiaLamp off, then <LINE>_Intensity (per-mille, 1 % -> 10), the
        line, and the master State last."""
        require_token(token)
        aura = self.devices.aura
        if aura is None or not self._has(aura):
            raise PropertyNotAllowed(f"no Aura device on {self.config.name}")
        ln = line.upper()
        if ln not in AURA_LINES:
            raise ValueError(f"Aura line {line!r} not in {AURA_LINES}")
        if not 0.0 <= float(percent) <= 100.0:
            raise ValueError(f"Aura percent {percent} is not in 0-100")
        notes = None if ln in MEASURED_AURA_LINES else {"aura_line": PROVISIONAL}
        return [*self.lamp_off(),
                self._set_and_read(aura, f"{ln}_Intensity", int(round(float(percent) * 10)),
                                   notes),
                self._set_and_read(aura, ln, 1, notes),
                self._set_and_read(aura, "State", 1)]

    def aura_off(self) -> list[Readback]:
        aura = self.devices.aura
        if aura is None or not self._has(aura):
            return []
        return [self._set_and_read(aura, "State", 0)]

    def all_off(self) -> list[Readback]:
        return [*self.aura_off(), *self.lamp_off()]

    # -- motion: engine.guards only, and locked while BENCH_MOTION is (T-036)
    def move_z(self, z_um: float, *, token: MotionToken) -> float:
        _require_motion_unlocked("move_z")
        require_token(token)
        z = float(z_um)
        if not math.isfinite(z):
            raise ValueError(f"z {z_um} is not a finite number")
        core = self._c()
        core.setPosition(self.devices.z, z)
        core.waitForDevice(self.devices.z)
        return float(core.getPosition(self.devices.z))

    def move_xy(self, x_um: float, y_um: float, *, token: MotionToken,
                timeout_s: float | None = None) -> tuple[float, float]:
        """Move and wait up to `timeout_s` (default `DEFAULT_XY_TIMEOUT_S`), not the core's
        fixed wait. On timeout the stage is stopped and TimeoutError raised."""
        _require_motion_unlocked("move_xy")
        require_token(token)
        x, y = float(x_um), float(y_um)
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError(f"XY ({x_um}, {y_um}) is not finite")
        core, dev = self._c(), self.devices.xy
        core.setXYPosition(dev, x, y)
        wait = DEFAULT_XY_TIMEOUT_S if timeout_s is None else float(timeout_s)
        deadline = time.monotonic() + wait
        while core.deviceBusy(dev):
            if time.monotonic() > deadline:
                core.stop(dev)
                raise TimeoutError(f"XY move to ({x}, {y}) not done in {wait:.1f} s")
            time.sleep(0.01)
        rx, ry = core.getXYPosition(dev)
        return float(rx), float(ry)

    def move_xy_rel(self, dx_um: float, dy_um: float, *, token: MotionToken,
                    timeout_s: float | None = None) -> tuple[float, float]:
        _require_motion_unlocked("move_xy_rel")
        require_token(token)
        x, y = self._c().getXYPosition(self.devices.xy)  # from the read
        return self.move_xy(float(x) + float(dx_um), float(y) + float(dy_um), token=token,
                            timeout_s=timeout_s)

    def set_nosepiece(self, state: int, *, token: MotionToken) -> Readback:
        _require_motion_unlocked("set_nosepiece")
        require_token(token)
        n = len(self._labels())
        if not 0 <= int(state) < n:
            raise ValueError(f"nosepiece state {state} is not in 0..{n - 1}")
        return self._set_and_read(self.devices.nosepiece, "State", int(state))

    def pfs_off(self, *, token: MotionToken) -> Readback:
        """Continuous focus off on the Core's autofocus device (the PFS: user check needed)."""
        require_token(token)
        core = self._c()
        if not self._has(self.devices.pfs):
            return Readback.of("PFS", "FocusMaintenance", "Off", "Off",
                               notes={"pfs": f"no PFS on {self.config.name}"})
        core.enableContinuousFocus(False)
        core.waitForDevice(self.devices.pfs)
        return Readback.of(self.devices.pfs, "ContinuousFocus", "Off",
                           "On" if core.isContinuousFocusEnabled() else "Off")


class _PiezoReadOnly:
    """The NanoBench 6000 link of `scripts/mm_grab.py::PiezoReader` (deleted in R-05), reads only.

    `read()` sends `stage.position.measured.get <channel>` for channels 1/2/3 (x/y/z, the
    controller's labelling) and converts picometres to um. There is no write method and no
    security-level call.

    The deleted reader also moved the piezo, and for that raised the controller to its "User"
    security level. It read that access code at run time from the vendor's own
    `C:\\Program Files (x86)\\NanoBench 6000\\data\\config.ini` (section SecurityLevels, key
    User) and never stored or logged it; no code value is in the repository (public-release
    audit K4). Anything that needs the level again reads it the same way.
    """

    LIBRARY = Path(r"C:\Program Files (x86)\NanoBench 6000\data\controller_interface64.dll")
    CHANNELS = {"x": 1, "y": 2, "z": 3}

    def __init__(self, address: str):
        import ctypes

        if not self.LIBRARY.is_file():
            raise OSError(f"no NanoBench library at {self.LIBRARY}")
        self._ct = ctypes
        lib = ctypes.cdll.LoadLibrary(str(self.LIBRARY))
        lib.Init.restype = ctypes.c_void_p
        lib.Uninit.argtypes = [ctypes.c_void_p]
        lib.OpenSession.restype = ctypes.c_int
        lib.OpenSession.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.CloseSession.argtypes = [ctypes.c_void_p]
        lib.DoCommand.restype = ctypes.c_int
        lib.DoCommand.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        for name in ("GetAllResultNames", "GetAllResults"):
            getattr(lib, name).restype = ctypes.c_int
            getattr(lib, name).argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self._lib, self._h = lib, lib.Init(None)
        if not lib.OpenSession(self._h, address.encode()):
            lib.Uninit(self._h)
            raise OSError(f"piezo controller did not open on {address} "
                          "(is the NanoBench program holding the port?)")

    def __enter__(self) -> _PiezoReadOnly:
        return self

    def __exit__(self, *exc: object) -> None:
        try:
            self._lib.CloseSession(self._h)
        finally:
            self._lib.Uninit(self._h)

    def _string(self, getter) -> str:
        probe = self._ct.create_string_buffer(2)
        size = getter(self._h, probe, 1) + 1
        buf = self._ct.create_string_buffer(max(size, 2))
        getter(self._h, buf, size)
        return buf.value.decode("utf-8", errors="replace")

    def read(self) -> dict[str, float]:
        out = {}
        for axis, ch in self.CHANNELS.items():
            if self._lib.DoCommand(self._h, f"stage.position.measured.get {ch}".encode()) <= 0:
                continue
            names = self._string(self._lib.GetAllResultNames).splitlines()
            values = dict(zip(names, self._string(self._lib.GetAllResults).splitlines(),
                              strict=False))
            if "value" in values:
                out[axis] = round(float(values["value"]) * 1e-6, 4)
        return out
