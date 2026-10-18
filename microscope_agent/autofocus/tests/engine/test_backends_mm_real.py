"""mm-real backend (T-033). No hardware here: the shared `BackendContract` runs the real code
on Micro-Manager's demo config (`DEMO_DEVICES`), skipped without the demo adapters, and
the bench light order runs on a stub core with the bench device names. Each test releases
the core it opened; nothing opens a window.

The T-036 bench motion lock is in tests/engine/test_backends_mm_real_lock.py, the T-036b
load-time preset check in tests/engine/test_backends_mm_real_cfg.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from dino_autofocus.engine.backend import (
    GUARD_TOKEN,
    CommandPathRetired,
)
from dino_autofocus.engine.backends import mm_real
from dino_autofocus.engine.backends.mm_real import (
    BENCH_CONFIG,
    DEMO_DEVICES,
    MmRealBackend,
    MmUnavailable,
    config_path,
)

T = GUARD_TOKEN  # tests stand in for engine.guards


#: the stock demo config turns its nosepiece at load, which mm-real refuses (T-036b)
DEMO_STARTUP_MOTION = "ConfigGroup,System,Startup,Objective,"


def safe_demo_text(cfg: Path) -> str:
    return "\n".join(line for line in cfg.read_text(encoding="utf-8").splitlines()
                     if not line.startswith(DEMO_STARTUP_MOTION)) + "\n"


def open_on_demo(**kw) -> MmRealBackend:
    """mm-real on a copy of the demo config without its load-time nosepiece setting. The
    copy is deleted once loaded (the backend loads its own private copy)."""
    from dino_autofocus.engine.backends.mm_demo_core import DemoUnavailable, find_demo_config

    try:
        cfg = find_demo_config()
        with tempfile.TemporaryDirectory(prefix="dino_af_test_") as tmp:
            safe = Path(tmp) / cfg.name
            safe.write_text(safe_demo_text(cfg), encoding="utf-8")
            b = MmRealBackend(safe, devices=DEMO_DEVICES, mm_dir=str(cfg.parent), **kw)
            b.open()
    except (DemoUnavailable, MmUnavailable) as e:
        pytest.skip(f"Micro-Manager demo adapters not available: {e}")
    return b


@pytest.fixture
def real():
    b = open_on_demo(roi=128)
    try:
        yield b
    finally:
        b.close()


# -- no hardware needed


def test_import_pulls_in_no_device_library():
    code = ("import sys, dino_autofocus.engine.backends.mm_real; "
            "bad = {'pymmcore', 'pymmcore_plus', 'torch', 'tkinter'} & set(sys.modules); "
            "assert not bad, bad")
    subprocess.run([sys.executable, "-c", code], check=True)


def test_config_path_argument_env_default_and_no_settings_file(monkeypatch, tmp_path):
    """The settings-folder lookup left with soft-matter-agents card 077: a settings.json
    naming a configuration is not read any more."""
    monkeypatch.delenv(mm_real.CONFIG_ENV, raising=False)
    monkeypatch.setenv("DINO_AF_CONFIG_DIR", str(tmp_path))
    assert config_path() == BENCH_CONFIG
    (tmp_path / "settings.json").write_text(json.dumps({"mm_config": "D:/cfg/a.cfg"}))
    assert config_path() == BENCH_CONFIG
    monkeypatch.setenv(mm_real.CONFIG_ENV, "D:/cfg/env.cfg")
    assert str(config_path()).replace(chr(92), "/") == "D:/cfg/env.cfg"
    assert config_path(tmp_path / "x.cfg") == tmp_path / "x.cfg"


def test_piezo_is_read_only_and_a_missing_link_is_a_field(monkeypatch, tmp_path):
    assert not any(hasattr(mm_real._PiezoReadOnly, n) for n in ("move_z", "_do",
                                                                 "ensure_user_level"))
    monkeypatch.setattr(mm_real._PiezoReadOnly, "LIBRARY", tmp_path / "none.dll")
    b = MmRealBackend(tmp_path / "x.cfg")
    r = b.piezo_read("COM4")
    assert not r.connected and "NanoBench" in r.error
    r0 = b.piezo_read("")
    assert r0.port == "" and not r0.connected and r0.error is None


class StubCore:
    """The few core calls the light and property paths make, with bench device names."""

    def __init__(self):
        self.props = {("DiaLamp", "State"): "0", ("Aura", "State"): "0",
                      **{("Aura", ln): "0" for ln in ("GREEN", "CYAN")},
                      **{("Aura", f"{ln}_Intensity"): "0" for ln in ("GREEN", "CYAN")}}
        self.writes: list[tuple[str, str, str]] = []

    def getLoadedDevices(self):
        return ["DiaLamp", "Aura", "Kinetix_red", "ZDrive", "XYStage", "Nosepiece", "PFS"]

    def getCameraDevice(self):
        return "Kinetix_red"

    def hasProperty(self, dev, prop):
        return (dev, prop) in self.props

    def getProperty(self, dev, prop):
        return self.props[(dev, prop)]

    def setProperty(self, dev, prop, value):
        self.writes.append((dev, prop, str(value)))
        self.props[(dev, prop)] = str(value)

    def waitForDevice(self, dev):
        pass


@pytest.fixture
def stub(tmp_path):
    b = MmRealBackend(tmp_path / "bench.cfg")
    b.core = StubCore()
    yield b
    b.core = None


class HubStubCore:
    """A bench hub and one peripheral; records every call so a hub query would show."""

    def __init__(self):
        self.calls: list[str] = []

    def __getattr__(self, name):
        answers = {
            "getLoadedDevices": lambda: ["Ti2-E__0", "ZDrive"],
            "getDevicePropertyNames": lambda label: [],
            "getDeviceType": lambda label: type("T", (), {"name": "HubDevice" if label ==
                                                         "Ti2-E__0" else "StageDevice"})(),
            "getDeviceLibrary": lambda label: "NikonTi2",
            "getDeviceDescription": lambda label: "",
            "getDeviceName": lambda label: label,
            "getParentLabel": lambda label: "" if label == "Ti2-E__0" else "Ti2-E__0",
            "getInstalledDevices": lambda label: ("ZDrive", "Nosepiece"),
        }
        if name not in answers:
            raise AttributeError(name)

        def call(*a):
            self.calls.append(name)
            return answers[name](*a)

        return call


def test_bench_scan_never_asks_a_hub_for_its_peripherals(tmp_path):
    """User, 2026-10-02: off on the stand until checked (READ_HUB_PERIPHERALS)."""
    assert mm_real.READ_HUB_PERIPHERALS is False
    b = MmRealBackend(tmp_path / "bench.cfg")
    b.core = HubStubCore()
    try:
        devs = {d.label: d for d in b.describe_devices(include_properties=False)}
    finally:
        calls, b.core = b.core.calls, None
    assert "getInstalledDevices" not in calls
    assert devs["Ti2-E__0"].installed is None
    assert (devs["ZDrive"].adapter, devs["ZDrive"].parent) == ("ZDrive", "Ti2-E__0")


# -- the real code on the demo config


#: card 077: every device write, and the core and its camera, refuse on mm-real
RETIRED_CALLS = [
    ("open", (), {}), ("set_exposure", (10.0,), {}), ("set_roi", (0,), {}),
    ("start_stream", (), {}), ("stop_stream", (), {}),
    ("set_property", ("DiaLamp", "State", 1), {"token": GUARD_TOKEN}),
    ("lamp_on", (), {"token": GUARD_TOKEN}), ("lamp_off", (), {}),
    ("aura_line_on", ("GREEN", 5.0), {"token": GUARD_TOKEN}), ("aura_off", (), {}),
    ("all_off", (), {}), ("move_z", (2950.0,), {"token": GUARD_TOKEN}),
    ("move_xy", (1.0, 2.0), {"token": GUARD_TOKEN}),
    ("move_xy_rel", (1.0, 2.0), {"token": GUARD_TOKEN}),
    ("set_nosepiece", (0,), {"token": GUARD_TOKEN}), ("pfs_off", (), {"token": GUARD_TOKEN}),
]


@pytest.mark.parametrize(("name", "args", "kwargs"), RETIRED_CALLS)
def test_every_write_and_the_core_refuse_on_mm_real(name, args, kwargs):
    b = MmRealBackend("absent.cfg")
    with pytest.raises(CommandPathRetired, match="plan.md 15, bc0f4848"):
        getattr(b, name)(*args, **kwargs)
    assert b.core is None  # nothing was opened
