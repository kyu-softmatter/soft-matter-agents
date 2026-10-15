"""The device list and hub tree a Micro-Manager `.cfg` declares, read from its text only.

Nothing here opens a core or touches hardware: the hardware screen draws this list and joins
it with the last `hardware_scan` (which devices loaded, which read back) to show connection
state per device.

What a device depends on, in the order it is taken:
- `parent`: a `Parent,<device>,<hub>` line (Ti2 peripherals under `Ti2-E__0`).
- `port`: a pre-init `Property,<device>,Port,<label>` naming a device the cfg loads, i.e. a
  SerialManager port (`CSUW1-Hub` on `COM10`).
- `inferred`: no line says so, but the device's adapter library has exactly one hub device
  (adapter name ends in "Hub") and the device is not that hub. The CSU-W1 peripherals have no
  `Parent` lines yet still need `CSUW1-Hub`. Marked so the screen can say it is a guess.
A `Connection`/`Port` value that names no loaded device (Lumencor's `COM3`) stays a detail.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

#: Core properties that assign a role to a device label
CORE_ROLE_PROPS = ("Camera", "Shutter", "Focus", "XYStage", "AutoFocus", "SLM", "Galvo")
#: pre-init properties that name the port a device talks through
PORT_PROPS = ("Port", "Connection")


@dataclass
class CfgDevice:
    label: str
    library: str
    adapter: str
    parent: str | None = None
    link: str | None = None  # "parent" | "port" | "inferred" | None (top level)
    port: str | None = None  # Port/Connection value, also when it names no loaded device
    roles: list[str] = field(default_factory=list)  # Core roles, e.g. ["Camera"]
    state_labels: dict[str, str] = field(default_factory=dict)  # state -> label
    preinit: dict[str, str] = field(default_factory=dict)  # pre-init Property lines
    line: int = 0  # 1-based line of its Device line


@dataclass
class CfgTree:
    devices: list[CfgDevice]
    startup: list[str] = field(default_factory=list)  # System/Startup settings, "dev.prop=value"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fields(line: str) -> list[str]:
    return [p.strip() for p in line.split(",")]


def parse_cfg(text: str) -> CfgTree:
    """Parse the `.cfg` text. Unknown lines are skipped; problems become `warnings`."""
    devices: dict[str, CfgDevice] = {}
    parents: dict[str, str] = {}
    roles: dict[str, list[str]] = {}
    labels: dict[str, dict[str, str]] = {}
    preinit: dict[str, dict[str, str]] = {}
    startup: list[str] = []
    warnings: list[str] = []
    initialized = False
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = _fields(line)
        kind = f[0]
        if kind == "Device" and len(f) >= 4:
            if f[1] in devices:
                warnings.append(f"line {n}: device {f[1]!r} declared twice")
            devices[f[1]] = CfgDevice(label=f[1], library=f[2], adapter=",".join(f[3:]), line=n)
        elif kind == "Parent" and len(f) >= 3:
            parents[f[1]] = f[2]
        elif kind == "Label" and len(f) >= 4:
            labels.setdefault(f[1], {})[f[2]] = ",".join(f[3:])
        elif kind == "Property" and len(f) >= 3:
            value = ",".join(f[3:])
            if f[1] == "Core":
                if f[2] == "Initialize":
                    initialized = value == "1"
                elif f[2] in CORE_ROLE_PROPS and value:
                    roles.setdefault(value, []).append(f[2])
            elif not initialized:
                preinit.setdefault(f[1], {})[f[2]] = value
        elif kind == "ConfigGroup" and len(f) >= 5 and (f[1], f[2]) == ("System", "Startup"):
            startup.append(f"{f[3]}.{f[4]}={','.join(f[5:])}")

    for d in devices.values():
        d.roles = roles.get(d.label, [])
        d.state_labels = dict(sorted(labels.get(d.label, {}).items(),
                                     key=lambda kv: (len(kv[0]), kv[0])))
        d.preinit = preinit.get(d.label, {})
        d.port = next((d.preinit[p] for p in PORT_PROPS if d.preinit.get(p)), None)
        hub = parents.get(d.label)
        if hub:
            d.parent, d.link = hub, "parent"
            if hub not in devices:
                warnings.append(f"{d.label}: parent {hub!r} is not a device in this file")
        elif d.port and d.port in devices:
            d.parent, d.link = d.port, "port"

    hubs: dict[str, list[str]] = {}
    for d in devices.values():
        if d.adapter.replace(" ", "").lower().endswith("hub"):
            hubs.setdefault(d.library, []).append(d.label)
    for d in devices.values():
        lib_hubs = hubs.get(d.library, [])
        if d.parent is None and len(lib_hubs) == 1 and lib_hubs[0] != d.label:
            d.parent, d.link = lib_hubs[0], "inferred"

    for label in (set(parents) | set(labels) | set(preinit)) - set(devices) - {"Core"}:
        warnings.append(f"{label!r} has settings but no Device line")
    _break_cycles(devices, warnings)
    return CfgTree(devices=list(devices.values()), startup=startup, warnings=sorted(warnings))


def _break_cycles(devices: dict[str, CfgDevice], warnings: list[str]) -> None:
    """A parent loop would hide its devices from any tree: lift the first one to the top."""
    for d in devices.values():
        seen, cur = {d.label}, d.parent
        while cur is not None and cur in devices:
            if cur in seen:
                warnings.append(f"{d.label}: parent loop through {cur!r}; shown at the top level")
                d.parent, d.link = None, None
                break
            seen.add(cur)
            cur = devices[cur].parent


def read_cfg(path: Path) -> tuple[CfgTree, str]:
    """Parse the file at `path`; returns the tree and the file's sha256."""
    data = path.read_bytes()
    return parse_cfg(data.decode("utf-8", errors="replace")), hashlib.sha256(data).hexdigest()
