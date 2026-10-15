"""What the engine needs from a microscope: the Backend protocol and its plain records.

Implementations live in `engine/backends/` (mock, replay, mm-demo, mm-real). Rules every
implementation follows:

- z is always in bench coordinates (ZDrive um, increasing = toward the sample, sample
  window 2800-3200). A device with another origin (the Micro-Manager demo Z) offsets
  inside the backend; guards and records never see its own numbers.
- Every write returns a `Readback`: what was wanted, what was read afterwards, verified.
- Light is set through meaning-level methods, not property writes, so a device with no
  `State` property (the demo LED shutter) is covered. Aura percent is converted to the
  device's per-mille inside the backend (1 % -> GREEN_Intensity 10).
- A position read that fails is a field (`Positions.errors`), never an exception: a
  missing stage must not stop the camera.
- The backend does not judge safety. Motion methods take the guards' `MotionToken` and
  call `require_token` first, so only `engine.guards` can move the stage or focus. Light
  methods that switch on or change intensity take it too (PLAN D15); switching off never does.
- `set_property` is an allow-list (`check_set_property`): motion devices are always refused,
  light properties need the token, a short list of camera properties needs none, and
  everything else is refused. Every backend calls it before writing.
- Markings such as "unmeasured provisional" or a demo substitution go into `notes`, never
  into device or property names.
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import numpy as np


@dataclass
class Readback:
    device: str
    prop: str
    wanted: str
    read: str
    verified: bool
    t: float = field(default_factory=time.time)
    notes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def of(cls, device: str, prop: str, wanted: Any, read: Any,
           notes: dict[str, str] | None = None) -> Readback:
        return cls(device, prop, str(wanted), str(read), str(read) == str(wanted),
                   notes=dict(notes or {}))


@dataclass
class Positions:
    """Stage readback in um; None where the read failed, with the reason in `errors`."""

    x_um: float | None = None
    y_um: float | None = None
    z_um: float | None = None
    piezo_um: dict[str, float] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    t: float = field(default_factory=time.time)


@dataclass
class PfsState:
    enabled: bool | None
    locked: bool | None
    in_range: str | None  # the device's own text, e.g. "In Range" / "Out of Range"

    @property
    def out_of_range(self) -> bool:
        return self.in_range is not None and "out" in self.in_range.lower()


@dataclass
class ObjectiveInfo:
    state: int  # nosepiece position
    label: str  # e.g. "6-Plan Apo LmbdD0.13 100x Oil"
    magnification: float
    pixel_um: float | None  # camera pixel in the sample plane
    free_wd_um: float | None  # None until measured; guards then plan no sweep for it


@dataclass
class StageLimits:
    """Travel the backend reports or was configured with, um. None = not known yet."""

    x_um: tuple[float, float] | None = None
    y_um: tuple[float, float] | None = None
    z_um: tuple[float, float] | None = None


@dataclass
class BackendInfo:
    kind: str  # "mock" | "replay" | "mm-demo" | "mm-real"
    config: str
    camera: str
    sensor: tuple[int, int]
    roi: tuple[int, int, int, int]
    exposure_ms: float
    pixel_um: float
    objective: str
    intermediate_mag: str | None
    bit_depth: int
    objectives: list[ObjectiveInfo] = field(default_factory=list)
    stage_limits: StageLimits = field(default_factory=StageLimits)
    notes: dict[str, str] = field(default_factory=dict)  # e.g. {"aura.CYAN": PROVISIONAL}
    #: Fail safe (T-015b): True unless a simulated backend says False. On the bench, guards
    #: and the runner require a clearance callback for `FocusAxis.approach()`. Read it
    #: through `is_bench`, never directly.
    bench: bool = True

    @property
    def ceiling_adu(self) -> int:
        return 2**self.bit_depth - 1  # 4095 for the Kinetix 100 MHz 12-bit readout

    def to_dict(self) -> dict:
        return {**asdict(self), "ceiling_adu": self.ceiling_adu}


@dataclass
class Frame:
    """A mono uint16 image. Positions are read when the frame is popped (`t_read`), which
    during motion can differ from the exposure by the buffer latency."""

    image: np.ndarray
    t_read: float
    exposure_ms: float
    x_um: float | None = None
    y_um: float | None = None
    z_um: float | None = None
    #: the camera device label (e.g. "Kinetix_red"); None when the backend does not say
    camera: str | None = None
    #: one image pixel in the sample plane, um (binning included); None when not known
    pixel_um: float | None = None
    #: mock only: the true dz = stage - best focus in depths of field (the live view's gauge
    #: shows it as "mock truth"); None from every real backend
    dz_truth_dof: float | None = None

    def meta(self) -> dict:
        return {"t_read": self.t_read, "exposure_ms": self.exposure_ms, "x_um": self.x_um,
                "y_um": self.y_um, "z_um": self.z_um, "shape": list(self.image.shape),
                "camera": self.camera, "pixel_um": self.pixel_um}


# ---------------------------------------------------------------- discovery reads (F2)
# Shapes follow `hardware_profile.json` in docs/operations-spec.md 5. Discovery writes
# nothing, moves nothing and switches nothing on; a read that fails is a field.


@dataclass
class PropertyInfo:
    value: str | None  # None when the read failed (`read_ok` False, reason in `error`)
    read_only: bool | None = None
    allowed: list[str] = field(default_factory=list)  # empty = free value
    limits: tuple[float, float] | None = None
    read_ok: bool = True
    error: str | None = None


@dataclass
class DeviceInfo:
    """A loaded device. `read_back`: its state can be read. `write_verified` stays None until
    a write was read back, which discovery never does (soft-matter-agents preflight names)."""

    label: str
    type: str  # Micro-Manager DeviceType name: "CameraDevice", "XYStageDevice", ...
    library: str
    description: str
    read_back: bool
    write_verified: bool | None = None
    properties: dict[str, PropertyInfo] = field(default_factory=dict)
    #: how the config loads it (what a `.cfg` needs to load it again): the adapter's device
    #: name, the parent hub label, the pre-init property values. None/empty = not reported
    adapter: str | None = None
    parent: str | None = None
    preinit: dict[str, str] = field(default_factory=dict)
    #: hubs only: the peripheral device names the hub reports as installed (its own
    #: detection, loaded or not); None = not a hub or not read
    installed: list[str] | None = None


def read_wiring(core: Any, label: str, type_name: str, *,
                hub_peripherals: bool = True) -> dict[str, Any]:
    """`DeviceInfo` wiring fields from a Micro-Manager core: reads only. Each read that fails
    leaves its field unreported instead of failing the description. The adapter, parent and
    pre-init reads use the core's own state; `hub_peripherals` adds `getInstalledDevices` on a
    hub, which asks the hub's adapter (its DetectInstalledDevices) and may query hardware."""
    out: dict[str, Any] = {}
    unreported = contextlib.suppress(Exception)  # a failed read is an unreported field
    with unreported:
        out["adapter"] = str(core.getDeviceName(label)) or None
    with unreported:
        out["parent"] = str(core.getParentLabel(label)) or None
    pre: dict[str, str] = {}
    with unreported:
        for name in core.getDevicePropertyNames(label):
            if core.isPropertyPreInit(label, name):
                pre[str(name)] = str(core.getProperty(label, name))
    out["preinit"] = pre
    if hub_peripherals and type_name == "HubDevice":
        with unreported:
            out["installed"] = [str(n) for n in core.getInstalledDevices(label)]
    return out


@dataclass
class NosepieceLabel:
    state: int
    label: str
    pixel_um: float | None  # from the backend's pixel-size table; None if it has none


@dataclass
class PiezoReading:
    """Read-only piezo position. Not opening (`port` "") or failing to open is a field."""

    port: str
    connected: bool
    x_um: float | None = None
    y_um: float | None = None
    z_um: float | None = None
    error: str | None = None
    t: float = field(default_factory=time.time)


@dataclass
class ConfigRecord:
    """What loading the configuration did at `open()`.

    `changed_during_load`: the file's sha256 differed before and after the load.
    `autoshutter`: AutoShutter 0 written at open and read back. `startup_preset`: the
    group/preset the load applied (Micro-Manager System/Startup), None if there is none.
    """

    path: str
    sha256: str | None
    changed_during_load: bool | None
    autoshutter: Readback | None
    startup_preset: str | None = None
    t_loaded: float | None = None
    notes: dict[str, str] = field(default_factory=dict)


class StreamActive(RuntimeError):
    """`snap()` while the acquisition stream runs. The engine pauses the stream first (T-011)."""


class MotionToken:
    """Held by `engine.guards`. A motion or light-on call without it is refused by the backend."""

    __slots__ = ()


GUARD_TOKEN = MotionToken()  # used outside engine/guards.py (and test fakes) = review failure

PROVISIONAL = "unmeasured provisional"  # the `notes` value for numbers not yet measured


class UnguardedMotion(RuntimeError):
    pass


class PropertyNotAllowed(ValueError):
    """`set_property` on a device/property outside the allow-list."""


def require_token(token: object) -> None:
    if token is not GUARD_TOKEN:
        raise UnguardedMotion("motion and light-on must go through engine.guards "
                              "(FocusAxis / XYAxis / lights)")


#: the only kinds that may report bench=False ("fake" is the tests' FakeBackend)
SIMULATED_KINDS = frozenset({"mock", "replay", "mm-demo", "fake"})


def is_bench(info: Any) -> bool:
    """Is this the real stand? The one rule guards and the runner share (T-015b, T-027).

    False only when `info` is readable, its `kind` is in `SIMULATED_KINDS` and its `bench`
    is exactly False. Everything else is the bench: no info (a failed `info()` read),
    an unreadable field, a missing `bench`, any other kind, or any other `bench` value.
    Any error while deciding (e.g. an unhashable `kind`) also means the bench (T-015c).
    """
    if info is None:
        return True
    try:
        kind, bench = info.kind, getattr(info, "bench", True)
        simulated = kind in SIMULATED_KINDS and bench is False
    except Exception:  # noqa: BLE001 - any error means the strict side
        return True
    return not simulated


# ---------------------------------------------------------------- set_property allow-list
# One place for every backend (T-015). Bench names first, then the Micro-Manager demo names.

#: Always refused by set_property, token or not: motion goes only through the guarded
#: methods. "Core" is listed because its Focus / XYStage properties would re-route motion.
MOTION_DEVICES = frozenset({
    "ZDrive", "XYStage", "Nosepiece", "PFS", "PFSOffset",  # bench (Ti2)
    "Z", "XY", "Objective", "Autofocus", "Core",  # demo
})

#: Aura lines as read off the Aura III 5-NII-WA on 2026-10-02 (docs/runs/
#: 2026-10-02_bench-properties.json). Only GREEN has been switched on at the bench
#: (2026-09-30); the rest are named but their use is unmeasured provisional.
AURA_LINES = ("UV", "CYAN", "GREEN", "RED", "NIR")

#: Token required (PLAN D15). Bench: Aura line on/off, line intensity (per-mille), master
#: State; DiaLamp State and Intensity. Demo: White Light Shutter (DiaLamp) and the LED line
#: selector; LED Shutter (Aura master) has no writable property and is switched by the light
#: methods.
LIGHT_PROPERTIES = frozenset(
    {("Aura", line) for line in AURA_LINES}
    | {("Aura", f"{line}_Intensity") for line in AURA_LINES}
    | {("Aura", "State"), ("DiaLamp", "State"), ("DiaLamp", "Intensity")}
    | {("White Light Shutter", "State"), ("LED", "Label"), ("LED", "State")}
)

#: No token, on the backend's own camera device only (`BackendInfo.camera`): what the
#: scripts set today. Prefer `set_exposure` / `set_roi` where they exist. Kinetix readout:
#: `ReadoutRate`'s allowed values depend on `Port` (2026-10-02: Port "Dynamic Range" ->
#: only "100MHz 16bit"), so the two are listed together; set Port first.
CAMERA_PROPERTIES = frozenset({"Exposure", "Binning", "PixelType",
                               "OnCameraCCDXSize", "OnCameraCCDYSize", "Port", "ReadoutRate"})


def check_set_property(device: str, prop: str, token: object, *, camera: str) -> None:
    """Raise unless `set_property(device, prop, ..., token=token)` is allowed.

    `camera` is the backend's camera device label. Motion devices raise `UnguardedMotion`
    always; light properties raise it without the guard token; anything not listed raises
    `PropertyNotAllowed` naming the allow-list.
    """
    if device in MOTION_DEVICES:
        raise UnguardedMotion(f"set_property on {device!r} would move hardware; "
                              "use the guarded motion methods")
    if (device, prop) in LIGHT_PROPERTIES:
        require_token(token)
        return
    if device == camera and prop in CAMERA_PROPERTIES:
        return
    lights = ", ".join(f"{d}.{p}" for d, p in sorted(LIGHT_PROPERTIES))
    cams = ", ".join(f"{camera}.{p}" for p in sorted(CAMERA_PROPERTIES))
    raise PropertyNotAllowed(f"set_property {device}.{prop} is not on the allow-list. "
                             f"Light (token required): {lights}. Camera: {cams}")


@runtime_checkable
class Backend(Protocol):
    # -- life
    def open(self) -> BackendInfo: ...
    def close(self) -> None: ...
    def info(self) -> BackendInfo: ...

    # -- camera
    def snap(self) -> Frame: ...
    def set_exposure(self, ms: float) -> float: ...  # returns the exposure read back
    def set_roi(self, size: int) -> tuple[int, int, int, int]: ...  # 0 = full sensor

    # -- reads
    def positions(self) -> Positions: ...
    def read_property(self, device: str, prop: str) -> str: ...
    def nosepiece(self) -> str: ...  # label, e.g. "1-Plan Apo LmbdD20 4x"
    def pfs(self) -> PfsState: ...
    def light_state(self) -> dict[str, str]: ...  # e.g. {"DiaLamp": "0", "Aura": "0"}

    # -- discovery reads (F2, hardware_scan): write nothing, move nothing, switch nothing on
    def describe_devices(self, include_properties: bool = True) -> list[DeviceInfo]: ...
    def nosepiece_labels(self) -> list[NosepieceLabel]: ...  # every state, not only the current
    def piezo_read(self, port: str) -> PiezoReading: ...  # "" = do not open the port
    def config_record(self) -> ConfigRecord: ...

    # -- acquisition stream, owned by the engine (T-011). Frames carry the same meta as
    # snap(). snap() while streaming raises StreamActive. next_frame returns the newest
    # frame not yet returned (older ones are dropped), or None after timeout_s.
    def start_stream(self, interval_ms: float | None = None) -> None: ...  # None = camera rate
    def next_frame(self, timeout_s: float = 1.0) -> Frame | None: ...
    def stop_stream(self) -> None: ...  # no-op when not streaming
    def streaming(self) -> bool: ...

    # -- writes, each returning what it read back. set_property: check_set_property first
    def set_property(self, device: str, prop: str, value: Any, *,
                     token: MotionToken | None = None) -> Readback: ...
    # light on / intensity: token required (D15). Off: no token, it is a stop
    def lamp_on(self, *, token: MotionToken) -> list[Readback]: ...  # DiaLamp
    def lamp_off(self) -> list[Readback]: ...
    def aura_line_on(self, line: str, percent: float, *,
                     token: MotionToken) -> list[Readback]: ...  # lamp off first
    def aura_off(self) -> list[Readback]: ...
    def all_off(self) -> list[Readback]: ...  # Aura and DiaLamp

    # -- motion: engine.guards only
    def move_z(self, z_um: float, *, token: MotionToken) -> float: ...  # returns z read back
    def move_xy(self, x_um: float, y_um: float, *, token: MotionToken,
                timeout_s: float | None = None) -> tuple[float, float]: ...
    # relative to the current XY read (edge_trace steps); same guards as move_xy. Returns
    # the XY read back after the move
    def move_xy_rel(self, dx_um: float, dy_um: float, *, token: MotionToken,
                    timeout_s: float | None = None) -> tuple[float, float]: ...
    def set_nosepiece(self, state: int, *, token: MotionToken) -> Readback: ...
    def pfs_off(self, *, token: MotionToken) -> Readback: ...
