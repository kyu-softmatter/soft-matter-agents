"""`hardware_scan{include_properties, piezo_port}` and `hardware_confirm{items}` (F2, WP-G).

`hardware_scan` (operations-spec 5) reads what is connected and writes `hardware_profile.json`:
the configuration record, every loaded device with its type, library and properties, the
objectives, the camera, positions, PFS, lights and the piezo. **It reads only**: nothing moves,
nothing is switched on or off, no property is written. A read that fails becomes an entry in
`profile.errors`, never a stop, so one missing device never hides the rest. Lights found on are
logged as a warning and left as they are.

`hardware_confirm{items: {name: value}}` records what a person checked on the stand (DiaLamp
intensity 608/2100, CondenserTurret, the 40x WI correction ring). Each item becomes
`{value, by, at}` with the operator's user id; a `None` value withdraws the item. It writes a
new profile version and moves nothing. Confirmations are carried into the next scan, with the
diff showing what changed since they were made.

Both keep every version in the `ProfileStore` history with a diff against the previous one.
Who may run them (rule 12) is the runner's `PERMISSIONS`: scan needs the control grant and no
session; confirm needs a logged-in local operator and no session.

Wiring (server, once): `hw = register_hardware(OPERATIONS, ProfileStore(root))`, then
`Runner(..., hardware=hw)`. `hw()` is the snapshot block `{profile, profile_path, sha256,
previous, gates, objective_options}` (the runner adds `last_status`); `hw.check(op, args)` is
the `(enabled, reasons)` the assistant tools and a preflight can ask for.
"""

from __future__ import annotations

import math
import socket
import time
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from ..backend import Backend, DeviceInfo, NosepieceLabel, is_bench
from ..gates import (
    GATES,
    ROLE_LABELS,
    ROLE_TYPES,
    DeviceRow,
    DeviceStatus,
    Gate,
    HardwareProfile,
    ObjectiveRow,
    ProfileStore,
    check,
    gate_rows,
    immersion_of,
    objective_options,
    working_distance,
)
from ..guards import GuardError, registry_key
from ..runner import Operation, Registry

SCAN, CONFIRM = "hardware_scan", "hardware_confirm"
DEFAULT_PIEZO_PORT = "COM4"  # live_focus --piezo; "" skips the piezo (operations-spec Q19)
MAX_ITEM_NAME = 64
MAX_ITEM_TEXT = 500


def _try(errors: dict[str, str], section: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a failed read is a field, not a stop
        errors[section] = f"{type(exc).__name__}: {exc}"
        return None


def assign_roles(devices: list[DeviceInfo], camera: str | None) -> dict[str, DeviceInfo]:
    """role -> device: the backend's own camera label, then the known labels, then a device
    type that occurs once."""
    by_label = {d.label: d for d in devices}
    roles: dict[str, DeviceInfo] = {}
    if camera and camera in by_label:
        roles["camera"] = by_label[camera]
    for role, labels in ROLE_LABELS.items():
        hit = next((by_label[x] for x in labels if x in by_label), None)
        if hit is not None:
            roles[role] = hit
    for role, kind in ROLE_TYPES.items():
        if role in roles:
            continue
        same = [d for d in devices if d.type == kind]
        if len(same) == 1:
            roles[role] = same[0]
    return roles


def _objective_rows(backend: Backend, info: Any, errors: dict[str, str]) -> list[ObjectiveRow]:
    known = {o.state: o for o in (getattr(info, "objectives", None) or [])}
    labels = _try(errors, "nosepiece_labels", backend.nosepiece_labels)
    if labels is None:  # fall back to the objectives the backend info carries
        labels = [NosepieceLabel(o.state, o.label, o.pixel_um) for o in known.values()]
    rows = []
    for nl in sorted(labels, key=lambda n: n.state):
        o = known.get(nl.state)
        try:
            key = registry_key(nl.label)
        except GuardError:
            key = None
        wd, src = working_distance(key, o.free_wd_um if o else None)
        rows.append(ObjectiveRow(
            state=nl.state, label=nl.label,
            pixel_um=nl.pixel_um if nl.pixel_um is not None else (o.pixel_um if o else None),
            magnification=o.magnification if o else None, registry_key=key,
            working_distance_um=wd, wd_source=src, immersion=immersion_of(key)))
    return rows


def scan(backend: Backend, *, include_properties: bool = True,
         piezo_port: str = DEFAULT_PIEZO_PORT, host: str | None = None,
         confirmed: dict | None = None) -> HardwareProfile:
    """Read everything operations-spec 5 lists into a profile. Reads only."""
    errors: dict[str, str] = {}
    info = _try(errors, "info", backend.info)
    devices = _try(errors, "devices",
                   lambda: backend.describe_devices(include_properties=include_properties)) or []
    roles = assign_roles(devices, getattr(info, "camera", None))
    role_of = {d.label: r for r, d in roles.items()}
    config = _try(errors, "config", backend.config_record)
    piezo = _try(errors, "piezo", lambda: backend.piezo_read(piezo_port))
    pos = _try(errors, "positions", backend.positions)
    pfs = _try(errors, "pfs", backend.pfs)
    lights = _try(errors, "lights", backend.light_state)
    objective = _try(errors, "nosepiece", backend.nosepiece)
    rows = _objective_rows(backend, info, errors)

    status = {r: DeviceStatus(True, bool(d.read_back), d.label) for r, d in roles.items()}
    if piezo is not None and piezo.port:
        status["piezo"] = DeviceStatus(piezo.connected, piezo.connected and piezo.error is None,
                                       piezo.port, piezo.error or "")
    pixel_type = None
    cam = roles.get("camera")
    if cam is not None and "PixelType" in cam.properties:
        pixel_type = cam.properties["PixelType"].value
    camera = {}
    if info is not None:
        camera = {"name": info.camera, "sensor": list(info.sensor), "roi": list(info.roi),
                  "bit_depth": info.bit_depth, "ceiling_adu": info.ceiling_adu,
                  "pixel_type": pixel_type, "exposure_ms": info.exposure_ms}
    cfg = {}
    if config is not None:
        cfg = {"path": config.path, "sha256": config.sha256,
               "changed_during_load": config.changed_during_load,
               "autoshutter_verified": None if config.autoshutter is None
               else config.autoshutter.verified,
               "startup_preset_applied": config.startup_preset,
               "t_loaded": config.t_loaded, "notes": dict(config.notes)}
    return HardwareProfile(
        backend_kind=getattr(info, "kind", "unknown"),
        devices=status,
        objectives=[r.label for r in rows],
        camera_bit_depth=getattr(info, "bit_depth", None),
        confirmed=dict(confirmed or {}),
        host=host if host is not None else socket.gethostname(),
        bench=is_bench(info),  # the shared rule: no info or unknown kind = the bench
        objective=objective if isinstance(objective, str) else None,
        config=cfg,
        device_list=[DeviceRow(d.label, d.type, d.library, d.description, role_of.get(d.label),
                               bool(d.read_back), d.write_verified,
                               {k: asdict(p) for k, p in d.properties.items()},
                               adapter=getattr(d, "adapter", None),
                               parent=getattr(d, "parent", None),
                               preinit=dict(getattr(d, "preinit", None) or {}),
                               installed=getattr(d, "installed", None))
                     for d in devices],
        objective_rows=rows,
        camera=camera,
        piezo=asdict(piezo) if piezo is not None else {},
        positions=asdict(pos) if pos is not None else {},
        pfs={} if pfs is None else {"enabled": pfs.enabled, "locked": pfs.locked,
                                    "in_range": pfs.in_range},
        lights=dict(lights or {}),
        stage_limits=asdict(info.stage_limits) if info is not None else {},
        notes=dict(getattr(info, "notes", {}) or {}),
        errors=errors,
    )


def lights_on(lights: dict) -> list[str]:
    """Light devices whose State reads anything but 0 / off."""
    return [k for k, v in lights.items() if str(v).strip().lower() not in ("0", "off", "")]


class HardwareState:
    """The runner's `hardware=` provider and the gate check, over one `ProfileStore`."""

    def __init__(self, store: ProfileStore, gates: tuple[Gate, ...] = GATES):
        self.store, self.gates = store, gates

    def profile(self) -> HardwareProfile | None:
        got = self.store.latest()
        return None if got is None else got[0]

    def check(self, op: str, args: dict | None = None) -> tuple[bool, list[str]]:
        return check(self.profile(), op, args, self.gates)

    def __call__(self) -> dict:
        got = self.store.latest()
        profile, path, sha = got if got is not None else (None, None, None)
        return {"profile": None if profile is None else asdict(profile),
                "profile_path": None if path is None else str(path), "sha256": sha,
                "previous": self.store.previous() if got is not None else None,
                "gates": gate_rows(profile, self.gates),
                "objective_options": objective_options(profile, gates=self.gates)}


def _scan_op(state: HardwareState) -> type[Operation]:
    class HardwareScan(Operation):
        name = SCAN
        motion = False  # reads only: allowed while a sample awaits return

        def _port(self) -> str:
            return str(self.args.get("piezo_port", DEFAULT_PIEZO_PORT))

        def plan(self) -> dict:
            port = self._port()
            return {"text": "Reads devices, properties, objectives, camera, positions, PFS, "
                            "lights, piezo. Nothing moves or turns on.",
                    "include_properties": bool(self.args.get("include_properties", True)),
                    "piezo_port": port, "piezo": "skipped" if not port else f"read on {port}"}

        def preflight(self) -> list[dict]:
            extra = sorted(set(self.args) - {"include_properties", "piezo_port"})
            checks = [{"name": "args", "ok": not extra, "want": "include_properties, piezo_port",
                       "read": extra, "why": f"unknown hardware_scan arguments: {extra}"}]
            ip = self.args.get("include_properties", True)
            checks.append({"name": "include_properties", "ok": isinstance(ip, bool),
                           "want": "true or false", "read": ip,
                           "why": "include_properties must be true or false"})
            port = self.args.get("piezo_port", DEFAULT_PIEZO_PORT)
            checks.append({"name": "piezo_port", "ok": isinstance(port, str), "want": "a port",
                           "read": port, "why": "piezo_port must be text (\"\" skips it)"})
            return checks

        def run(self) -> dict:
            with state.store.lock:
                prev = state.store.latest()
                profile = scan(self.ctx.backend,
                               include_properties=bool(self.args.get("include_properties", True)),
                               piezo_port=self._port(),
                               confirmed=prev[0].confirmed if prev else None)
                for section in ("config", "camera", "objective_rows", "piezo", "pfs", "lights"):
                    value = getattr(profile, section)
                    self.ctx.emit("reading", source=f"hardware_scan.{section}",
                                  value=[asdict(r) for r in value]
                                  if section == "objective_rows" else value)
                for name, why in profile.errors.items():
                    self.ctx.log(f"{name} unreadable: {why}", level="warning")
                on = lights_on(profile.lights)
                if on:
                    self.ctx.log(f"lights on during detection: {', '.join(on)} (left as they "
                                 "are; hardware_scan switches nothing)", level="warning")
                saved = state.store.save(profile)
            enabled = [r["op"] for r in gate_rows(profile, state.gates) if r["enabled"]]
            return {"profile": asdict(profile), **saved, "gates_enabled": enabled,
                    "errors": profile.errors}

    return HardwareScan


def _confirm_op(state: HardwareState) -> type[Operation]:
    class HardwareConfirm(Operation):
        name = CONFIRM
        exclusive = False  # record-only: runs beside a running operation
        motion = False

        def _items(self) -> Any:
            return self.args.get("items")

        def plan(self) -> dict:
            items = self._items() if isinstance(self._items(), dict) else {}
            return {"text": "Records operator-confirmed hardware items. Nothing moves.",
                    "items": sorted(items)}

        def preflight(self) -> list[dict]:
            items, bad = self._items(), []
            if not isinstance(items, dict) or not items:
                bad.append("items must be a non-empty {name: value} object")
            else:
                for k, v in items.items():
                    if not isinstance(k, str) or not k.strip() or len(k) > MAX_ITEM_NAME:
                        bad.append(f"item name {k!r} must be 1-{MAX_ITEM_NAME} characters")
                    if v is not None and not isinstance(v, (str, int, float, bool)):
                        bad.append(f"{k}: value must be text, a number, true/false or null")
                    elif isinstance(v, float) and not math.isfinite(v):
                        bad.append(f"{k}: {v} is not a finite number")
                    elif isinstance(v, str) and len(v) > MAX_ITEM_TEXT:
                        bad.append(f"{k}: value longer than {MAX_ITEM_TEXT} characters")
            extra = sorted(set(self.args) - {"items"})
            if extra:
                bad.append(f"unknown hardware_confirm arguments: {extra}")
            return [
                {"name": "items", "ok": not bad, "want": "{name: value}", "read": items,
                 "why": "; ".join(bad)},
                {"name": "operator", "ok": bool(self.ctx.user_id), "want": "a logged-in operator",
                 "read": self.ctx.user_id, "why": "a confirmation needs who made it"},
                {"name": "profile", "ok": state.store.latest() is not None,
                 "want": "a hardware profile", "read": None,
                 "why": "no hardware profile yet: run hardware_scan first"},
            ]

        def run(self) -> dict:
            at = time.strftime("%Y-%m-%dT%H:%M:%S")
            with state.store.lock:
                got = state.store.latest()
                if got is None:  # removed between preflight and run
                    raise RuntimeError("no hardware profile yet: run hardware_scan first")
                profile = got[0]
                done, withdrawn = {}, []
                for k, v in self._items().items():
                    if v is None:
                        if profile.confirmed.pop(k, None) is not None:
                            withdrawn.append(k)
                        continue
                    profile.confirmed[k] = done[k] = {"value": v, "by": self.ctx.user_id,
                                                      "at": at}
                saved = state.store.save(profile)
            self.ctx.emit("reading", source="hardware_confirm", value={
                "confirmed": done, "withdrawn": withdrawn})
            return {"confirmed": done, "withdrawn": withdrawn, **saved}

    return HardwareConfirm


def register_hardware(registry: Registry, store: ProfileStore,
                      gates: tuple[Gate, ...] = GATES) -> HardwareState:
    """Register both operations, bound to `store`, and return the snapshot provider."""
    state = HardwareState(store, gates)
    registry.register(_scan_op(state))
    registry.register(_confirm_op(state))
    return state
