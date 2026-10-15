"""Find the Micro-Manager `.cfg` that matches what a `hardware_scan` found, or draft a new one.

Both work on the scan's device rows (`HardwareProfile.device_list` as dicts) and parsed cfg
files (`mm_config_tree.CfgTree`). Nothing here touches hardware or writes a file.

- `match_configs` ranks cfg files by how many scanned devices they declare with the same
  label and adapter library (and adapter name, when the scan reports it).
- `draft_cfg` writes a `.cfg` text from the scan: Device, pre-init Property, Parent, Core
  role and Label lines. What the scan does not report (adapter names in profiles from before
  2026-10-02, state labels, Core roles) is taken from a base cfg, usually the best match.
  Peripherals a hub reports as installed but no config loads are added commented out.
  The draft carries no post-init device settings, no config groups and no Startup preset,
  so loading it sets nothing on a motion device (mm_real T-036b); `check_draft` runs that
  same check on the text.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .mm_config_tree import CfgDevice, CfgTree, parse_cfg

#: scan role -> the Core property that names its device
SCAN_ROLE_TO_CORE = {"camera": "Camera", "z_drive": "Focus", "xy_stage": "XYStage",
                     "pfs": "AutoFocus"}
#: device types loaded first: ports before the hubs that open them, hubs before peripherals
LOAD_FIRST = ("SerialDevice", "HubDevice")


def scanned_devices(device_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The scan's loadable devices: every row but the Core."""
    return [d for d in device_list
            if isinstance(d, dict) and d.get("label") and d.get("type") != "CoreDevice"
            and d.get("label") != "Core"]


@dataclass
class ConfigMatch:
    matched: list[str] = field(default_factory=list)  # same label, library (and adapter)
    differs: list[str] = field(default_factory=list)  # same label, other library/adapter
    missing: list[str] = field(default_factory=list)  # in the cfg, not in the scan
    extra: list[str] = field(default_factory=list)  # in the scan, not in the cfg
    score: float = 0.0  # matched / every label in either
    exact: bool = False


def match_config(rows: list[dict[str, Any]], tree: CfgTree) -> ConfigMatch:
    scan = {d["label"]: d for d in scanned_devices(rows)}
    cfg = {d.label: d for d in tree.devices}
    m = ConfigMatch()
    for label in sorted(set(scan) & set(cfg)):
        s, c = scan[label], cfg[label]
        same = (s.get("library") or "") == c.library and \
            (not s.get("adapter") or s["adapter"] == c.adapter)
        (m.matched if same else m.differs).append(label)
    m.missing = sorted(set(cfg) - set(scan))
    m.extra = sorted(set(scan) - set(cfg))
    union = len(set(scan) | set(cfg))
    m.score = round(len(m.matched) / union, 4) if union else 0.0
    m.exact = bool(union) and not (m.differs or m.missing or m.extra)
    return m


@dataclass
class Draft:
    text: str
    devices: int = 0
    from_base: list[str] = field(default_factory=list)  # what was taken from the base cfg
    unknown_adapter: list[str] = field(default_factory=list)  # left commented out
    hub_found: list[str] = field(default_factory=list)  # "hub: name", added commented out
    warnings: list[str] = field(default_factory=list)


def _order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rank = {t: i for i, t in enumerate(LOAD_FIRST)}
    return sorted(rows, key=lambda d: rank.get(str(d.get("type")), len(LOAD_FIRST)))


def _line(*parts: Any) -> str:
    return ",".join(str(p) for p in parts)


def draft_cfg(rows: list[dict[str, Any]], base: CfgTree | None = None, *,
              base_name: str | None = None, scan_labels: dict[str, dict[str, str]] | None = None,
              header: list[str] | None = None) -> Draft:
    """The `.cfg` text for the scanned devices. `scan_labels`: state labels the scan read
    (nosepiece objectives), used where the base has none. `header`: comment lines on top."""
    devs = _order(scanned_devices(rows))
    base_dev: dict[str, CfgDevice] = {d.label: d for d in (base.devices if base else [])}
    from_base: set[str] = set()
    unknown: list[str] = []
    hub_found: list[str] = []
    out = [f"# {h}" for h in (header or [])]
    out += ["# Review before loading. Not included: config groups and presets, pixel size",
            "# calibrations, focus direction, delays, post-init settings.", "",
            "# Reset", _line("Property", "Core", "Initialize", 0), "", "# Devices"]
    loaded: list[str] = []
    for d in devs:
        label, lib = d["label"], d.get("library") or ""
        b = base_dev.get(label)
        adapter = d.get("adapter") or (b.adapter if b and b.library == lib else None)
        if not d.get("adapter") and adapter:
            from_base.add(f"{label}: adapter")
        if not adapter or not lib:
            unknown.append(label)
            out.append(f"# {_line('Device', label, lib or '?', '?')}"
                       "  <- adapter name not reported; fill in and uncomment")
            continue
        loaded.append(label)
        out.append(_line("Device", label, lib, adapter))
    installed_lines: list[str] = []
    for hub in devs:
        names = hub.get("installed")
        if not names:
            continue
        here = {d.get("adapter") for d in devs if d.get("parent") == hub["label"]}
        here |= {base_dev[x].adapter for x in loaded
                 if x in base_dev and base_dev[x].parent == hub["label"]}
        for name in names:
            if name in here:
                continue
            hub_found.append(f"{hub['label']}: {name}")
            installed_lines.append(f"# {_line('Device', name, hub.get('library') or '?', name)}"
                                   f"  <- reported installed by {hub['label']}, not loaded")
    if installed_lines:
        out += ["", "# Peripherals the hubs report but no config loaded (uncomment to add)"]
        out += installed_lines

    out += ["", "# Pre-init settings for devices"]
    for label in loaded:
        d = next(x for x in devs if x["label"] == label)
        pre = d.get("preinit") or {}
        if not pre and label in base_dev and base_dev[label].preinit:
            pre = base_dev[label].preinit
            from_base.add(f"{label}: pre-init settings")
        out += [_line("Property", label, k, v) for k, v in pre.items()]

    out += ["", "# Hub (parent) references"]
    for label in loaded:
        d = next(x for x in devs if x["label"] == label)
        parent = d.get("parent")
        b = base_dev.get(label)
        if not parent and b is not None and b.link == "parent":
            parent = b.parent
            from_base.add(f"{label}: parent")
        if parent and parent in loaded:
            out.append(_line("Parent", label, parent))
        elif parent:
            out.append(f"# {_line('Parent', label, parent)}  <- {parent} is not loaded")

    out += ["", "# Initialize", _line("Property", "Core", "Initialize", 1), "", "# Roles"]
    roles: dict[str, str] = {}
    for label in loaded:
        for prop in (base_dev[label].roles if label in base_dev else []):
            roles.setdefault(prop, label)
            from_base.add(f"{label}: Core {prop}")
    for d in devs:
        prop = SCAN_ROLE_TO_CORE.get(str(d.get("role")))
        if prop and d["label"] in loaded:
            roles.setdefault(prop, d["label"])
    out += [_line("Property", "Core", prop, label) for prop, label in roles.items()]

    out += ["", "# Labels"]
    for label in loaded:
        labels = base_dev[label].state_labels if label in base_dev else {}
        if labels:
            from_base.add(f"{label}: state labels")
        else:
            labels = (scan_labels or {}).get(label, {})
        out += [_line("Label", label, s, name) for s, name in labels.items()]

    draft = Draft(text="\n".join(out) + "\n", devices=len(loaded), unknown_adapter=unknown,
                  hub_found=hub_found, from_base=sorted(from_base))
    if from_base and base_name:
        draft.warnings.append(f"details missing from the scan were taken from {base_name}")
    draft.warnings += parse_cfg(draft.text).warnings
    return draft


def check_draft(text: str, name: str) -> str | None:
    """None when mm-real would load this text, else why not (T-036b/d load checks, bench
    device names)."""
    from .backends.mm_real import (
        BENCH_DEVICES,
        UnsafeConfig,
        check_load_settings,
        load_time_settings,
    )

    try:
        check_load_settings(load_time_settings(text), name, BENCH_DEVICES)
    except UnsafeConfig as e:
        return str(e)
    return None


def draft_header(profile: dict[str, Any], base_name: str | None) -> list[str]:
    cfg = profile.get("config") if isinstance(profile.get("config"), dict) else {}
    return [
        f"Drafted by dino-autofocus on {time.strftime('%Y-%m-%dT%H:%M:%S')} from the hardware "
        f"scan of {profile.get('detected_at', '?')}",
        f"backend {profile.get('backend_kind', '?')}, host {profile.get('host') or '?'}, "
        f"scanned config {cfg.get('path') or '?'}",
        f"base for details the scan did not report: {base_name or 'none'}",
    ]
