"""F2 gates: which operations are enabled, decided in code from the hardware profile.

A `HardwareProfile` (written by `operations/hardware_scan.py`, WP-G) says what was detected
and what a person confirmed (`hardware_profile.json`, operations-spec 5). Each `Gate` names the
device roles, objectives, profile checks and operator confirmations an operation needs.
`evaluate` returns, per gate, whether it is enabled and every reason it is not, so the UI can
show a disabled feature with its reasons (F2.2). Neither a model nor a UI dialog opens a gate.

Device roles are backend-neutral: camera, xy_stage, z_drive, dia_lamp, aura, nosepiece, pfs,
piezo. `ROLE_LABELS` maps the bench and Micro-Manager demo device labels onto them.

Rules:
- A gate checks what the hardware *is*, not what one run needs: the sample's hole fit, this
  session's oil loading or the target objective are the operation's preflight.
- Stops (`abort`, `lights_off`) are never gated: switching off must always be possible (PLAN 5).
  Operations that need no hardware state (records, sample choice, the scan itself) are listed in
  `UNGATED`. Any other operation with no gate row is disabled, the strict default.
- With no profile yet, every gated operation is disabled with the reason `NOT_SCANNED`.
- A gate row may apply to one argument value (`Gate.arg`, e.g. `light_set` mode):
  `check(profile, op, args)` picks the row; `evaluate` reports every row under its `key`
  (`light_set:aura`).

`ProfileStore` keeps the latest profile, every version in `history/`, and the diff of each
version against the one before (configuration only: positions, lights, PFS state and property
values are state, not configuration). Where the store lives is the caller's choice.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .guards import FREE_WD_UM, GuardError, registry_key

ROLES = ("camera", "xy_stage", "z_drive", "dia_lamp", "aura", "nosepiece", "pfs", "piezo")

#: role -> device labels: bench (Ti2, mm-real BENCH_DEVICES) first, then the demo config
ROLE_LABELS: dict[str, tuple[str, ...]] = {
    "z_drive": ("ZDrive", "Z"),
    "xy_stage": ("XYStage", "XY"),
    "nosepiece": ("Nosepiece", "Objective"),
    "pfs": ("PFS",),
    "dia_lamp": ("DiaLamp", "White Light Shutter"),
    "aura": ("Aura", "LED Shutter"),
}
#: role -> Micro-Manager device type, used when no label above matches and the type is unique
ROLE_TYPES = {"camera": "CameraDevice", "xy_stage": "XYStageDevice", "pfs": "AutoFocusDevice"}

NOT_SCANNED = "hardware not scanned yet: run hardware_scan"


@dataclass
class DeviceStatus:
    present: bool
    readable: bool  # a read of its state succeeded and was checked
    label: str = ""  # the backend's own device name, e.g. "Kinetix_red", "ZDrive"
    note: str = ""


@dataclass
class DeviceRow:
    """One loaded device (operations-spec 5 `devices[]`). `write_verified` stays None: the scan
    never writes. `properties` is `{name: {value, read_only, allowed, limits, read_ok, error}}`."""

    label: str
    type: str
    library: str
    description: str = ""
    role: str | None = None
    read_back: bool = False
    write_verified: bool | None = None
    properties: dict[str, dict] = field(default_factory=dict)
    #: `backend.DeviceInfo` wiring: what a `.cfg` needs to load it again (profiles written
    #: before 2026-10-02 lack these and read back with the defaults)
    adapter: str | None = None
    parent: str | None = None
    preinit: dict[str, str] = field(default_factory=dict)
    installed: list[str] | None = None


@dataclass
class ObjectiveRow:
    """One nosepiece position. `working_distance_um` is the backend's objective info, else the
    guards' lens table (`guards.FREE_WD_UM`); `wd_source` says which. No backend reports NA
    yet, so `na` stays None ("not set")."""

    state: int
    label: str
    pixel_um: float | None = None
    magnification: float | None = None
    registry_key: str | None = None
    working_distance_um: float | None = None
    wd_source: str | None = None
    immersion: str | None = None  # "dry" | "oil" | "water"
    na: float | None = None


@dataclass
class HardwareProfile:
    backend_kind: str
    detected_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    devices: dict[str, DeviceStatus] = field(default_factory=dict)  # role -> status
    objectives: list[str] = field(default_factory=list)  # nosepiece labels
    camera_bit_depth: int | None = None
    #: item -> {"value", "by", "at"} (`hardware_confirm`); the operator's word, not a detection
    confirmed: dict[str, Any] = field(default_factory=dict)
    host: str = ""
    bench: bool = True  # backend.is_bench(info): the real stand, the strict default
    objective: str | None = None  # nosepiece label at detection time
    config: dict = field(default_factory=dict)  # path, sha256, changed_during_load, ...
    device_list: list[DeviceRow] = field(default_factory=list)
    objective_rows: list[ObjectiveRow] = field(default_factory=list)
    camera: dict = field(default_factory=dict)  # name, sensor, roi, bit_depth, ceiling_adu, ...
    piezo: dict = field(default_factory=dict)  # port, connected, x_um, y_um, z_um, error
    positions: dict = field(default_factory=dict)
    pfs: dict = field(default_factory=dict)
    lights: dict = field(default_factory=dict)
    stage_limits: dict = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)  # backend notes, e.g. provisional
    errors: dict[str, str] = field(default_factory=dict)  # section -> why its read failed

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1)

    @classmethod
    def from_json(cls, s: str) -> HardwareProfile:
        d = json.loads(s)
        d["devices"] = {k: DeviceStatus(**v) for k, v in d.get("devices", {}).items()}
        d["device_list"] = [DeviceRow(**r) for r in d.get("device_list", [])]
        d["objective_rows"] = [ObjectiveRow(**r) for r in d.get("objective_rows", [])]
        return cls(**d)

    def save(self, path: Path) -> Path:
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    def objective_keys(self) -> set[str]:
        keys = set()
        for label in self.objectives:
            try:
                keys.add(registry_key(label))
            except GuardError:
                continue
        return keys


def immersion_of(key: str | None) -> str | None:
    if key is None:
        return None
    return "oil" if key.endswith("-Oil") else "water" if key.endswith("-WI") else "dry"


def working_distance(key: str | None,
                     from_backend: float | None) -> tuple[float | None, str | None]:
    """(free working distance um, where it came from); (None, None) when nobody knows it."""
    if from_backend is not None:
        return float(from_backend), "backend"
    if key is not None and key in FREE_WD_UM:
        return FREE_WD_UM[key], "guards.FREE_WD_UM"
    return None, None


# -- gates ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Gate:
    op: str
    devices: tuple[str, ...] = ()
    objectives: tuple[str, ...] = ()  # registry keys, e.g. "4x", "100x-Oil"
    confirmed: tuple[str, ...] = ()  # operator confirmations the profile must hold
    checks: tuple[str, ...] = ()  # names in CHECKS, e.g. "camera_bit_depth"
    arg: tuple[str, str] | None = None  # (argument, value): this row is for that value

    @property
    def key(self) -> str:
        return self.op if self.arg is None else f"{self.op}:{self.arg[1]}"

    def requires(self) -> dict:
        return {"devices": list(self.devices), "objectives": list(self.objectives),
                "confirmed": list(self.confirmed), "checks": list(self.checks),
                "arg": None if self.arg is None else {self.arg[0]: self.arg[1]}}


@dataclass
class GateResult:
    op: str
    enabled: bool
    reasons: list[str]


def _bit_depth(p: HardwareProfile) -> str | None:
    if p.camera_bit_depth:
        return None
    return "camera bit depth not read (it sets the saturation ceiling and auto exposure)"


#: profile checks a gate can name; each returns why it fails, or None
CHECKS = {"camera_bit_depth": _bit_depth}

# operations-spec 5 gate table, T-027 loading_check_image, D15 light_set. The run-time parts of
# that table (the sample's hole, this session's oil record, the target lens's working
# distance) are the operations' preflight, not gates.
GATES: tuple[Gate, ...] = (
    Gate("status"),  # reads what exists; a missing device is a field, not a stop
    Gate("light_set", ("dia_lamp",), arg=("mode", "brightfield")),
    Gate("light_set", ("aura",), arg=("mode", "aura")),
    Gate("light_set", arg=("mode", "off")),
    Gate("edge_trace", ("camera", "xy_stage", "dia_lamp"), ("4x",)),
    Gate("scan_4x", ("camera", "xy_stage", "z_drive", "pfs", "aura"), ("4x",),
         checks=("camera_bit_depth",)),
    Gate("sample_map", ("camera", "xy_stage", "z_drive", "pfs", "dia_lamp"), ("4x",),
         checks=("camera_bit_depth",)),
    Gate("goto_xy", ("xy_stage", "z_drive", "nosepiece")),
    Gate("objective_change", ("nosepiece", "z_drive", "pfs", "xy_stage")),
    Gate("focus_100x", ("camera", "z_drive", "pfs", "aura", "nosepiece"), ("100x-Oil",),
         checks=("camera_bit_depth",)),
    Gate("loading_check_image", ("camera", "dia_lamp"), ("4x",)),
    # optical tweezers (card T-20261002-2205): the profile has no tweezers role yet (the scan
    # does not detect Tweez300), so the gate asks for the camera that shows the trap; whether
    # there are tweezers at all is the operation's preflight
    Gate("trap_move", ("camera",)),
    Gate("trap_set", ("camera",)),
    Gate("pattern_run", ("camera",)),  # which targets exist is the operation's preflight
)

#: never gated: stops, the scan that makes the profile, and operations on records only
UNGATED = frozenset({
    "abort", "lights_off", "hardware_scan", "hardware_confirm",
    "sample_open", "sample_new", "sample_geometry_set", "loading_confirm_person",
    "boundary_mark", "boundary_undo", "boundary_reset", "map_flag", "map_flag_retire",
    "candidate_confirm", "candidate_reject", "score_tare", "score_tare_clear", "frame_save",
})


def _reasons(profile: HardwareProfile | None, g: Gate) -> list[str]:
    if profile is None:
        return [NOT_SCANNED]
    keys = profile.objective_keys()
    why = []
    for role in g.devices:
        d = profile.devices.get(role)
        if d is None or not d.present:
            why.append(f"{role} not detected")
        elif not d.readable:
            why.append(f"{role} detected but its state did not read back")
    why += [f"objective {k} not on the nosepiece" for k in g.objectives if k not in keys]
    why += [r for c in g.checks if (r := CHECKS[c](profile))]
    why += [f"not confirmed by the operator: {c}" for c in g.confirmed
            if c not in profile.confirmed]
    return why


def evaluate(profile: HardwareProfile | None,
             gates: tuple[Gate, ...] = GATES) -> dict[str, GateResult]:
    """Every gate row, keyed by `Gate.key`. `profile=None`: nothing scanned, all disabled."""
    return {g.key: GateResult(g.key, not (why := _reasons(profile, g)), why) for g in gates}


def check(profile: HardwareProfile | None, op: str, args: dict | None = None,
          gates: tuple[Gate, ...] = GATES) -> tuple[bool, list[str]]:
    """(enabled, reasons) for one command. The row whose `arg` matches `args` wins over the
    op's plain row; an op with no row is enabled only if it is in `UNGATED`."""
    if op in UNGATED:
        return True, []
    args = args or {}
    rows = [g for g in gates if g.op == op]
    if not rows:
        return False, [f"no gate rule for {op!r}"]
    picked = ([g for g in rows if g.arg is not None and args.get(g.arg[0]) == g.arg[1]]
              or [g for g in rows if g.arg is None])
    if not picked:
        name = rows[0].arg[0]
        values = sorted(g.arg[1] for g in rows)
        return False, [f"{op}: {name} must be one of {values}"]
    why = _reasons(profile, picked[0])
    return not why, why


def gate_rows(profile: HardwareProfile | None,
              gates: tuple[Gate, ...] = GATES) -> list[dict]:
    """The screen's GateRow list (docs/screens/hardware.md 1): disabled rows first, then by key."""
    res = evaluate(profile, gates)
    rows = [{"op": g.key, "enabled": res[g.key].enabled, "reasons": res[g.key].reasons,
             "requires": g.requires()} for g in gates]
    return sorted(rows, key=lambda r: (r["enabled"], r["op"]))


def objective_options(profile: HardwareProfile | None, current_label: str | None = None,
                      gates: tuple[Gate, ...] = GATES) -> list[dict]:
    """Per nosepiece position: label, whether `objective_change` may go there now, and why not
    (T-104). Unselectable: the current objective, a lens whose working distance is not in the
    guards' lens table (operations-spec 4.2: 40x WI is refused; a backend's catalogue value is
    shown but does not count, the guards decide), and any reason of the `objective_change` gate.
    `current_label` defaults to the objective read at detection; the screen passes the live one."""
    if profile is None:
        return []
    _, gate_why = check(profile, "objective_change", gates=gates)
    current = current_label if current_label is not None else profile.objective
    out = []
    for row in profile.objective_rows:
        why = list(gate_why)
        if current is not None and row.label == current:
            why.append("already on this objective")
        if row.registry_key is None:
            why.append(f"no magnification in the label {row.label!r}")
        elif row.registry_key not in FREE_WD_UM:
            why.append(f"working distance of {row.registry_key} not in the guards' lens table")
        out.append({"state": row.state, "label": row.label, "registry_key": row.registry_key,
                    "immersion": row.immersion, "working_distance_um": row.working_distance_um,
                    "selectable": not why, "reasons": why})
    return out


# -- profile history -----------------------------------------------------------------------

#: top-level fields that are state, not configuration: left out of the diff
STATE_KEYS = frozenset({"detected_at", "positions", "lights", "pfs", "errors", "objective"})
MAX_CHANGES = 200


def _flat(profile: dict) -> dict[str, Any]:
    """Dotted keys for the diff: devices by label, objectives by state, piezo by connection,
    property metadata without the value (a property value is state)."""
    out: dict[str, Any] = {}
    for k, v in profile.items():
        if k in STATE_KEYS:
            continue
        if k == "devices":
            for role, st in v.items():
                out[f"role.{role}"] = st
        elif k == "device_list":
            for d in v:
                base = f"device.{d['label']}"
                for name, x in d.items():
                    if name == "properties":
                        for prop, meta in x.items():
                            out[f"{base}.property.{prop}"] = {
                                m: meta.get(m) for m in ("read_only", "allowed", "limits")}
                    elif name != "label":
                        out[f"{base}.{name}"] = x
        elif k == "objective_rows":
            for r in v:
                for name, x in r.items():
                    if name != "state":
                        out[f"objective.{r['state']}.{name}"] = x
        elif k == "piezo":
            out["piezo.port"], out["piezo.connected"] = v.get("port"), v.get("connected")
        elif isinstance(v, dict):
            for name, x in v.items():
                out[f"{k}.{name}"] = x
        else:
            out[k] = v
    return out


def diff(before: dict | None, after: dict) -> list[dict]:
    """Configuration changes `before -> after` as `{key, before, after}`, sorted by key."""
    if before is None:
        return []
    a, b = _flat(before), _flat(after)
    changes = [{"key": k, "before": a.get(k), "after": b.get(k)}
               for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    return changes[:MAX_CHANGES]


class ProfileStore:
    """`<root>/hardware_profile.json` (latest), `<root>/history/hardware_profile_<stamp>.json`
    (every version, never rewritten) and `<root>/hardware_profile.previous.json` (the latest
    version's diff against the one before). `save` returns where it went, its sha256 and that
    diff. One lock per store: a scan and a confirm do not interleave."""

    LATEST = "hardware_profile.json"

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.lock = threading.RLock()

    @property
    def latest_path(self) -> Path:
        return self.root / self.LATEST

    def latest(self) -> tuple[HardwareProfile, Path, str] | None:
        p = self.latest_path
        if not p.exists():
            return None
        data = p.read_bytes()
        return (HardwareProfile.from_json(data.decode("utf-8")), p,
                hashlib.sha256(data).hexdigest())

    def history(self) -> list[Path]:
        return sorted((self.root / "history").glob("hardware_profile_*.json"))

    def save(self, profile: HardwareProfile) -> dict:
        with self.lock:
            prev = self.latest()
            data = profile.to_json().encode("utf-8")
            hist = self.root / "history"
            hist.mkdir(parents=True, exist_ok=True)
            base = f"hardware_profile_{time.strftime('%Y%m%d-%H%M%S')}"
            path, n = hist / f"{base}.json", 1
            while path.exists():  # two saves in one second
                n += 1
                path = hist / f"{base}_{n}.json"
            path.write_bytes(data)
            tmp = self.latest_path.with_name(self.LATEST + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(self.latest_path)
            previous = None
            if prev is not None:
                previous = {"sha256": prev[2], "detected_at": prev[0].detected_at,
                            "changed": diff(asdict(prev[0]), asdict(profile))}
            self.previous_path.write_text(json.dumps(previous, indent=1), encoding="utf-8")
            return {"profile_path": str(self.latest_path), "version_path": str(path),
                    "sha256": hashlib.sha256(data).hexdigest(), "previous": previous}

    @property
    def previous_path(self) -> Path:
        return self.root / "hardware_profile.previous.json"

    def previous(self) -> dict | None:
        """The latest version's diff against the one before it (None for the first version)."""
        p = self.previous_path
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
