"""`engine.mm_config_tree`: the device list and hub tree of a Micro-Manager `.cfg`, text only."""

from __future__ import annotations

from pathlib import Path

import pytest

from dino_autofocus.engine.mm_config_tree import parse_cfg, read_cfg

REPO_CFGS = Path(__file__).resolve().parents[2] / "configs" / "micromanager"

CFG = """\
# Reset
Property,Core,Initialize,0
Device,COM10,SerialManager,COM10
Device,Ti2-E__0,NikonTi2,Ti2-E__0
Device,ZDrive,NikonTi2,ZDrive
Device,Nosepiece,NikonTi2,Nosepiece
Device,Kinetix_red,PVCAM,Camera-2
Device,LightEngine,Lumencor,LightEngine
Device,CSUW1-Hub,CSUW1,CSUW1-Hub
Device,CSUW1-Port,CSUW1,CSUW1-Port
Property,LightEngine,Connection,COM3
Property,CSUW1-Hub,Port,COM10
Property,COM10,BaudRate,115200
Parent,ZDrive,Ti2-E__0
Parent,Nosepiece,Ti2-E__0
Property,Core,Initialize,1
Property,Core,Camera,Kinetix_red
Property,Core,Focus,ZDrive
Property,ZDrive,Speed,3
Label,Nosepiece,1,2-Plan Apo 10x
Label,Nosepiece,0,1-Plan Apo 4x
ConfigGroup,System,Startup,CSUW1-Port,State,1
"""


def by_label(text: str) -> dict:
    return {d.label: d for d in parse_cfg(text).devices}


def test_devices_in_file_order_with_library_and_adapter():
    tree = parse_cfg(CFG)
    assert [d.label for d in tree.devices][:3] == ["COM10", "Ti2-E__0", "ZDrive"]
    cam = by_label(CFG)["Kinetix_red"]
    assert (cam.library, cam.adapter, cam.roles) == ("PVCAM", "Camera-2", ["Camera"])
    assert cam.parent is None


def test_parent_port_and_inferred_links():
    d = by_label(CFG)
    assert (d["ZDrive"].parent, d["ZDrive"].link) == ("Ti2-E__0", "parent")
    assert (d["CSUW1-Hub"].parent, d["CSUW1-Hub"].link) == ("COM10", "port")
    # no Parent line, but the CSUW1 library has one hub
    assert (d["CSUW1-Port"].parent, d["CSUW1-Port"].link) == ("CSUW1-Hub", "inferred")
    # a Connection that names no loaded device stays a detail
    assert (d["LightEngine"].port, d["LightEngine"].parent) == ("COM3", None)


def test_preinit_only_before_initialize_and_labels_in_state_order():
    d = by_label(CFG)
    assert d["COM10"].preinit == {"BaudRate": "115200"}
    assert "Speed" not in d["ZDrive"].preinit  # post-init line, not a pre-init setting
    assert d["ZDrive"].roles == ["Focus"]
    assert list(d["Nosepiece"].state_labels.items()) == [
        ("0", "1-Plan Apo 4x"), ("1", "2-Plan Apo 10x")]
    assert parse_cfg(CFG).startup == ["CSUW1-Port.State=1"]


def test_warnings_for_unknown_parent_duplicates_and_loops():
    text = "\n".join([
        "Device,A,Lib,A", "Device,B,Lib,B", "Device,B,Lib,B", "Device,C,Lib,C",
        "Parent,A,B", "Parent,B,A", "Parent,C,Nowhere", "Property,Ghost,Port,COM1",
    ])
    tree = parse_cfg(text)
    w = " | ".join(tree.warnings)
    assert "declared twice" in w and "'Nowhere' is not a device" in w
    assert "'Ghost' has settings" in w
    assert "parent loop" in w
    # the loop is broken: at least one of A/B is at the top, so the tree shows both
    assert any(d.parent is None for d in tree.devices if d.label in {"A", "B"})


@pytest.mark.parametrize("name", ["DMD_dualcam_LUNF.cfg", "single_cam_red_noDMD_nocom10.cfg"])
def test_repo_configs_parse_without_warnings(name):
    tree, sha = read_cfg(REPO_CFGS / name)
    assert len(sha) == 64 and tree.warnings == []
    d = {x.label: x for x in tree.devices}
    assert d["ZDrive"].parent == "Ti2-E__0"
    assert d["LUNF-Blanking"].parent == "NIDAQHub"
    assert d["Kinetix_red"].roles == ["Camera"]


def test_dualcam_csu_w1_hangs_under_its_hub_on_com10():
    tree, _ = read_cfg(REPO_CFGS / "DMD_dualcam_LUNF.cfg")
    d = {x.label: x for x in tree.devices}
    assert d["CSUW1-Hub"].parent == "COM10"
    under_hub = sorted(x.label for x in tree.devices if x.parent == "CSUW1-Hub")
    assert under_hub == sorted(["CSUW1-Filter_Red", "CSUW1-Filter_Blue", "CSUW1-Dichroic",
                                "CSUW1-Shutter", "CSUW1-Bright", "CSUW1-Port"])
