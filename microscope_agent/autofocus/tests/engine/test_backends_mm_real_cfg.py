"""SAFETY (T-036b): mm-real refuses a config that would move the stand while loading.

Small synthetic `.cfg` files (tmp_path) for the parser and the refusal, which happen before
pymmcore-plus is imported; the stock demo config (refused: its Startup turns the nosepiece)
and a cleaned copy (opens, records what loading set) skip without the demo adapters.
"""

from __future__ import annotations

import pytest
from test_backends_mm_real import DEMO_STARTUP_MOTION, open_on_demo

from dino_autofocus.engine.backends.mm_real import (
    BENCH_DEVICES,
    DEMO_DEVICES,
    DeviceNames,
    LoadSetting,
    MmRealBackend,
    UnsafeConfig,
    check_load_settings,
    load_time_settings,
)

HEAD = """# synthetic bench-like config
Property,Core,Initialize,0
Device,ZDrive,NikonTi2,ZDrive
Device,XYStage,NikonTi2,XYStage
Device,Nosepiece,NikonTi2,Nosepiece
Device,LappMainBranch1,NikonTi2,LappMainBranch1
Device,DiaLamp,NikonTi2,DiaLamp
Property,XYStage,Port,COM3
Property,Core,Initialize,1
Property,Core,Focus,ZDrive
Property,Core,AutoShutter,1
"""
CLEAN = HEAD + """ConfigGroup,System,Startup,LappMainBranch1,State,1
ConfigGroup,System,Startup,DiaLamp,State,0
ConfigGroup,System,Startup,Core,Shutter,DiaLamp
ConfigGroup,Objective,100x,Nosepiece,State,5
"""
MOVES = HEAD + """ConfigGroup,System,Startup,LappMainBranch1,State,1
ConfigGroup,System,Startup,ZDrive,Position,3000
ConfigGroup,System,Startup,Nosepiece,State,5
Property,XYStage,Velocity,10
"""


def write(tmp_path, text: str, name: str = "bench.cfg"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_parser_finds_post_init_properties_and_the_load_time_presets():
    got = load_time_settings(MOVES)
    assert LoadSetting("ConfigGroup System/Startup", "ZDrive", "Position", "3000") in got
    assert LoadSetting("post-init Property", "XYStage", "Velocity", "10") in got
    assert LoadSetting("post-init Property", "Core", "Focus", "ZDrive") in got
    assert not any(s.prop == "Port" for s in got)  # pre-init: needed to load, sets nothing
    assert not any(s.where.endswith("Objective/100x") for s in load_time_settings(CLEAN))


def test_clean_config_passes_light_path_shutters_and_core_roles():
    check_load_settings(load_time_settings(CLEAN), "bench.cfg")


def test_refusal_names_every_motion_setting_and_where():
    with pytest.raises(UnsafeConfig) as e:
        check_load_settings(load_time_settings(MOVES), "bench.cfg")
    msg = str(e.value)
    assert "ZDrive.Position, Nosepiece.State in ConfigGroup System/Startup" in msg
    assert "XYStage.Velocity in post-init Property" in msg
    assert "LappMainBranch1" not in msg and "bench.cfg" in msg


def test_shutdown_preset_is_checked_too():
    with pytest.raises(UnsafeConfig, match=r"PFS.FocusMaintenance in ConfigGroup System/Shutdown"):
        check_load_settings(load_time_settings(
            HEAD + "ConfigGroup,System,Shutdown,PFS,FocusMaintenance,On\n"), "x.cfg")


def test_open_refuses_before_loading_anything(tmp_path, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_pymmcore(name, *a, **k):
        if name.startswith("pymmcore"):
            raise AssertionError("pymmcore imported before the config check")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_pymmcore)
    b = MmRealBackend(write(tmp_path, MOVES))
    with pytest.raises(UnsafeConfig, match="ZDrive.Position"):
        b.open()
    assert b.core is None


def test_the_stock_demo_config_is_refused():
    from dino_autofocus.engine.backends.mm_demo_core import DemoUnavailable, find_demo_config

    try:
        cfg = find_demo_config()
    except DemoUnavailable as e:
        pytest.skip(f"Micro-Manager demo adapters not available: {e}")
    b = MmRealBackend(cfg, devices=DEMO_DEVICES, mm_dir=str(cfg.parent))
    with pytest.raises(UnsafeConfig, match=r"Objective.Label in ConfigGroup System/Startup"):
        b.open()
    assert b.core is None
    assert DEMO_STARTUP_MOTION in cfg.read_text(encoding="utf-8")


def test_a_clean_copy_opens_and_records_what_loading_set():
    b = open_on_demo(roi=64)
    try:
        notes = b.config_record().notes
        assert "ConfigGroup System/Startup: Camera.BitDepth=16" in notes["load_settings"]
        assert "Objective" not in notes["load_settings"]
        assert "private copy" in notes["loaded"]
        assert b.config_record().changed_during_load is False
    finally:
        b.close()


# -- T-036d: motion devices under other labels

RENAMED = """Property,Core,Initialize,0
Device,TIZDrive,NikonTi2,ZDrive
Device,TIXYStage,NikonTi2,XYStage
Property,Core,Initialize,1
"""


def test_a_renamed_stage_is_refused_by_the_configured_label():
    text = RENAMED + "ConfigGroup,System,Startup,TIZDrive,Position,3000\n"
    check_load_settings(load_time_settings(text), "x.cfg")  # fixed names alone miss it
    with pytest.raises(UnsafeConfig, match=r"TIZDrive.Position in ConfigGroup System/Startup"):
        check_load_settings(load_time_settings(text), "x.cfg",
                            DeviceNames(z="TIZDrive", xy="TIXYStage"))


def test_a_renamed_stage_is_refused_by_the_cfgs_own_core_role():
    text = (RENAMED + "Property,Core,Focus,TIZDrive\n"
            "ConfigGroup,System,Startup,TIZDrive,Position,3000\n")
    with pytest.raises(UnsafeConfig) as e:
        check_load_settings(load_time_settings(text), "x.cfg")  # no DeviceNames at all
    assert "TIZDrive.Position in ConfigGroup System/Startup" in str(e.value)
    with pytest.raises(UnsafeConfig) as e:
        check_load_settings(load_time_settings(text), "x.cfg", BENCH_DEVICES)
    msg = str(e.value)
    assert "TIZDrive.Position in ConfigGroup System/Startup" in msg
    assert "role mismatch: Core.Focus is 'TIZDrive' but this backend drives 'ZDrive' as z" in msg


def test_a_role_mismatch_alone_is_refused_and_matching_roles_pass():
    text = RENAMED + "Property,Core,Focus,TIZDrive\nProperty,Core,XYStage,TIXYStage\n"
    with pytest.raises(UnsafeConfig) as e:
        check_load_settings(load_time_settings(text), "x.cfg", BENCH_DEVICES)
    assert "Core.Focus is 'TIZDrive'" in str(e.value)
    assert "Core.XYStage is 'TIXYStage'" in str(e.value)
    check_load_settings(load_time_settings(text), "x.cfg",
                        DeviceNames(z="TIZDrive", xy="TIXYStage"))
    with pytest.raises(UnsafeConfig, match=r"Core.AutoFocus is 'PFS' but this backend drives None"):
        check_load_settings(load_time_settings(HEAD + "Property,Core,AutoFocus,PFS\n"), "x.cfg",
                            DeviceNames(pfs=None))


def test_open_uses_the_backends_device_names(tmp_path):
    text = RENAMED + "ConfigGroup,System,Startup,TIZDrive,Position,3000\n"
    b = MmRealBackend(write(tmp_path, text), devices=DeviceNames(z="TIZDrive", xy="TIXYStage"))
    with pytest.raises(UnsafeConfig, match="TIZDrive.Position"):
        b.open()
    assert b.core is None
