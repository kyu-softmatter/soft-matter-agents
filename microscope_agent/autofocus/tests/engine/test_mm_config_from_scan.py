"""`engine.mm_config_from_scan`: rank cfg files against a scan, draft a cfg from a scan."""

from __future__ import annotations

import json
from pathlib import Path

from dino_autofocus.engine.mm_config_from_scan import (
    check_draft,
    draft_cfg,
    match_config,
)
from dino_autofocus.engine.mm_config_tree import parse_cfg, read_cfg

REPO = Path(__file__).resolve().parents[2]
CFGS = REPO / "configs" / "micromanager"
BENCH_READ = REPO / "docs" / "runs" / "2026-10-02_bench-properties.json"


def bench_rows() -> list[dict]:
    """The 2026-10-02 bench `describe_devices` (no adapter/parent/pre-init: older read)."""
    data = json.loads(BENCH_READ.read_text(encoding="utf-8"))
    return [{k: v for k, v in d.items() if k != "properties"} for d in data["devices"]]


def row(label, type_, library, **over):
    return {"label": label, "type": type_, "library": library, "description": "",
            "role": None, "read_back": True, "write_verified": None, **over}


def test_the_bench_scan_matches_the_bench_cfg_exactly_and_the_dualcam_partly():
    rows = bench_rows()
    single = match_config(rows, read_cfg(CFGS / "single_cam_red_noDMD_nocom10.cfg")[0])
    assert (single.exact, single.score, single.missing, single.extra) == (True, 1.0, [], [])
    dual = match_config(rows, read_cfg(CFGS / "DMD_dualcam_LUNF.cfg")[0])
    assert not dual.exact and dual.extra == []
    assert set(dual.missing) == {"COM10", "CSUW1-Hub", "CSUW1-Filter_Red", "CSUW1-Filter_Blue",
                                 "CSUW1-Dichroic", "CSUW1-Shutter", "CSUW1-Bright",
                                 "CSUW1-Port", "Kinetix_blue", "MightexPolygon1000"}
    assert dual.score < single.score


def test_a_different_adapter_counts_as_differs_not_matched():
    tree = parse_cfg("Device,Cam,PVCAM,Camera-1\n")
    m = match_config([row("Cam", "CameraDevice", "PVCAM", adapter="Camera-2")], tree)
    assert (m.matched, m.differs, m.exact) == ([], ["Cam"], False)


def test_draft_from_an_old_scan_takes_adapters_and_parents_from_the_base():
    base = read_cfg(CFGS / "single_cam_red_noDMD_nocom10.cfg")[0]
    d = draft_cfg(bench_rows(), base, base_name="single_cam")
    assert d.devices == 20 and d.unknown_adapter == []
    assert "Device,Kinetix_red,PVCAM,Camera-2" in d.text
    assert "Parent,ZDrive,Ti2-E__0" in d.text
    assert "Property,Core,Camera,Kinetix_red" in d.text
    assert "Label,Nosepiece,0,1-Plan Apo LmbdD20 4x" in d.text
    assert "Kinetix_red: adapter" in d.from_base
    # the draft parses to the same devices and hub tree as its base
    redo = {x.label: (x.library, x.adapter, x.parent) for x in parse_cfg(d.text).devices}
    want = {x.label: (x.library, x.adapter, x.parent) for x in base.devices}
    assert redo == want


def test_draft_without_a_base_leaves_unknown_adapters_commented_out():
    d = draft_cfg(bench_rows(), None)
    assert d.devices == 0 and len(d.unknown_adapter) == 20
    assert "# Device,ZDrive,NikonTi2,?" in d.text
    assert parse_cfg(d.text).devices == []


def test_draft_uses_the_scans_own_wiring_and_lists_hub_peripherals_not_loaded():
    rows = [
        row("COM1", "SerialDevice", "SerialManager", adapter="COM1", preinit={"BaudRate": "9600"}),
        row("Hub", "HubDevice", "Lib", adapter="LibHub", installed=["StageA", "NewThing"]),
        row("Stage", "StageDevice", "Lib", adapter="StageA", parent="Hub", role="z_drive",
            preinit={"Port": "COM1"}),
        row("Core", "CoreDevice", ""),
    ]
    d = draft_cfg(rows, None)
    lines = d.text.splitlines()
    devices = [ln for ln in lines if ln.startswith("Device,")]
    assert devices == ["Device,COM1,SerialManager,COM1", "Device,Hub,Lib,LibHub",
                       "Device,Stage,Lib,StageA"]  # ports, then hubs, then the rest
    assert "Property,COM1,BaudRate,9600" in lines and "Parent,Stage,Hub" in lines
    assert "Property,Core,Focus,Stage" in lines
    assert d.hub_found == ["Hub: NewThing"]
    assert any(ln.startswith("# Device,NewThing,Lib,NewThing") for ln in lines)
    # pre-init lines come before Initialize 1, so loading sets nothing after init
    assert lines.index("Property,Stage,Port,COM1") < lines.index("Property,Core,Initialize,1")


def test_the_draft_passes_mm_reals_load_check_and_a_bad_one_does_not():
    base = read_cfg(CFGS / "single_cam_red_noDMD_nocom10.cfg")[0]
    d = draft_cfg(bench_rows(), base, base_name="single_cam")
    assert check_draft(d.text, "draft") is None
    unsafe = d.text + "Property,ZDrive,Position,100\n"  # post-init setting on a motion device
    assert "would move the stand" in check_draft(unsafe, "draft")


class FakeCore:
    """The Micro-Manager core calls `read_wiring` makes; `fail` names calls that raise."""

    def __init__(self, fail=()):
        self.fail = set(fail)

    def _maybe(self, name):
        if name in self.fail:
            raise RuntimeError(name)

    def getDeviceName(self, label):
        self._maybe("getDeviceName")
        return {"Hub": "LibHub", "Stage": "StageA"}[label]

    def getParentLabel(self, label):
        self._maybe("getParentLabel")
        return "" if label == "Hub" else "Hub"

    def getDevicePropertyNames(self, label):
        return ["Port", "Speed"]

    def isPropertyPreInit(self, label, name):
        return name == "Port"

    def getProperty(self, label, name):
        return "COM1"

    def getInstalledDevices(self, label):
        self._maybe("getInstalledDevices")
        return ("StageA", "NewThing")


def test_read_wiring_reads_adapter_parent_preinit_and_hub_peripherals():
    from dino_autofocus.engine.backend import read_wiring

    assert read_wiring(FakeCore(), "Hub", "HubDevice") == {
        "adapter": "LibHub", "parent": None, "preinit": {"Port": "COM1"},
        "installed": ["StageA", "NewThing"]}
    stage = read_wiring(FakeCore(), "Stage", "StageDevice")
    assert stage["parent"] == "Hub" and "installed" not in stage


def test_read_wiring_leaves_a_failed_read_unreported():
    from dino_autofocus.engine.backend import read_wiring

    out = read_wiring(FakeCore(fail={"getDeviceName", "getInstalledDevices"}), "Hub", "HubDevice")
    assert "adapter" not in out and "installed" not in out and out["preinit"] == {"Port": "COM1"}


def test_profiles_round_trip_the_wiring_and_old_profiles_still_load():
    from dino_autofocus.engine.gates import DeviceRow, HardwareProfile

    p = HardwareProfile(backend_kind="mm-real", device_list=[
        DeviceRow("Stage", "StageDevice", "Lib", adapter="StageA", parent="Hub",
                  preinit={"Port": "COM1"})])
    back = HardwareProfile.from_json(p.to_json()).device_list[0]
    assert (back.adapter, back.parent, back.preinit, back.installed) == \
        ("StageA", "Hub", {"Port": "COM1"}, None)
    old = json.loads(p.to_json())
    for k in ("adapter", "parent", "preinit", "installed"):
        del old["device_list"][0][k]  # a profile written before 2026-10-02
    assert HardwareProfile.from_json(json.dumps(old)).device_list[0].adapter is None


def test_read_wiring_skips_the_hub_query_when_asked():
    from dino_autofocus.engine.backend import read_wiring

    core = FakeCore(fail={"getInstalledDevices"})  # would raise if called
    out = read_wiring(core, "Hub", "HubDevice", hub_peripherals=False)
    assert "installed" not in out and out["adapter"] == "LibHub"
