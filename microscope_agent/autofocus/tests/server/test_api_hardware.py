"""`/api/hardware` (T-101): read-only views of the engine's hardware state, on a fake engine.

The fake hardware block follows T-028 (55d88c2, `operations/hardware_scan.HardwareState`):
`{profile: asdict(HardwareProfile), profile_path, sha256, previous, gates: gate_rows(...),
objective_options}` plus the runner's `last_status`. It is written out by hand because T-028
is not on main yet; swap it for `HardwareState` output when it is.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

VIEWER = "vera@example.test"  # the seeded viewer in conftest.py
SHA = "ab" * 32


def t028_profile(**over: Any) -> dict[str, Any]:
    """`asdict(engine.gates.HardwareProfile)` as T-028 writes it."""
    p = {
        "backend_kind": "mock",
        "detected_at": "2026-10-02T09:00:00",
        "devices": {
            "camera": {"present": True, "readable": True, "label": "Kinetix_red", "note": ""},
            "xy_stage": {"present": True, "readable": False, "label": "XYStage", "note": ""},
            "piezo": {"present": False, "readable": False, "label": "", "note": "port skipped"},
        },
        "objectives": ["1-Plan Apo LmbdD20 4x", "6-Plan Apo LmbdD0.13 100x Oil"],
        "camera_bit_depth": 12,
        "confirmed": {"DiaLamp intensity": {"value": "608/2100", "by": "otto", "at": "09:01"}},
        "host": "MICROSCOPE",
        "bench": False,
        "objective": "1-Plan Apo LmbdD20 4x",
        "config": {"path": "C:/mm/demo.cfg", "sha256": "cd" * 32, "changed_during_load": False},
        "device_list": [
            {
                "label": "Kinetix_red",
                "type": "CameraDevice",
                "library": "DemoCamera",
                "description": "",
                "role": "camera",
                "read_back": True,
                "write_verified": None,
                "properties": {"Binning": {"value": "1", "read_only": False}},
            },
            {
                "label": "XYStage",
                "type": "XYStageDevice",
                "library": "DemoCamera",
                "description": "",
                "role": "xy_stage",
                "read_back": False,
                "write_verified": None,
                "properties": {},
            },
        ],
        "objective_rows": [
            {
                "state": 0,
                "label": "1-Plan Apo LmbdD20 4x",
                "pixel_um": 1.625,
                "magnification": 4,
                "registry_key": "4x",
                "working_distance_um": 20000,
                "wd_source": "guards",
                "immersion": "dry",
                "na": None,
            },
            {
                "state": 5,
                "label": "6-Plan Apo LmbdD0.13 100x Oil",
                "pixel_um": 0.065,
                "magnification": 100,
                "registry_key": "100x-Oil",
                "working_distance_um": 130,
                "wd_source": "guards",
                "immersion": "oil",
                "na": None,
            },
        ],
        "camera": {
            "name": "Kinetix_red",
            "sensor": [2400, 2400],
            "roi": [0, 0, 2400, 2400],
            "bit_depth": 12,
            "ceiling_adu": 4095,
        },
        "piezo": {
            "port": "",
            "connected": False,
            "x_um": None,
            "y_um": None,
            "z_um": None,
            "error": None,
        },
        "positions": {},
        "pfs": {},
        "lights": {},
        "stage_limits": {},
        "notes": {"stage_limits": "unmeasured provisional"},
        "errors": {},
    }
    p.update(over)
    return p


def t028_gates() -> list[dict[str, Any]]:
    """`engine.gates.gate_rows(profile)` as T-028 returns it: a list, off rows first."""

    def req(devices=(), objectives=(), confirmed=(), checks=(), arg=None):
        return {
            "devices": list(devices),
            "objectives": list(objectives),
            "confirmed": list(confirmed),
            "checks": list(checks),
            "arg": arg,
        }

    return [
        {
            "op": "sample_map",
            "enabled": False,
            "reasons": ["xy_stage detected but its state did not read back"],
            "requires": req(
                ("camera", "xy_stage", "z_drive", "dia_lamp"), ("4x",), checks=("camera_bit_depth",)
            ),
        },
        {
            "op": "light_set:aura",
            "enabled": True,
            "reasons": [],
            "requires": req(("aura",), arg={"mode": "aura"}),
        },
        {
            "op": "light_set:brightfield",
            "enabled": False,
            "reasons": ["dia_lamp not detected"],
            "requires": req(("dia_lamp",), arg={"mode": "brightfield"}),
        },
        {
            "op": "light_set:off",
            "enabled": True,
            "reasons": [],
            "requires": req(arg={"mode": "off"}),
        },
        {"op": "status", "enabled": True, "reasons": [], "requires": req(("camera",))},
    ]


def t028_block(**over: Any) -> dict[str, Any]:
    block = {
        "profile": t028_profile(),
        "profile_path": "D:/AutoFocus/hardware/hardware_profile.json",
        "sha256": SHA,
        "previous": {
            "sha256": "ef" * 32,
            "detected_at": "2026-10-01T18:00:00",
            "changed": [{"key": "device.XYStage.read_back", "before": True, "after": False}],
        },
        "gates": t028_gates(),
        "objective_options": [],
        "last_status": None,
    }
    block.update(over)
    return block


@pytest.fixture
def with_hardware(engine):
    """`with_hardware(block)`: conftest's FakeEngine, whose snapshot carries the hardware
    block `snapshot()["hardware"]`."""

    def make(block: dict[str, Any]):
        plain = engine.snapshot
        engine.snapshot = lambda: {**plain(), "hardware": block}
        return engine

    return make


@pytest.fixture
def hw_engine(with_hardware):
    return with_hardware(t028_block())


def test_router_is_mounted_read_only(make_client, hw_engine):
    """Read only, but for saving a drafted cfg file (never the hardware)."""
    c = make_client(hw_engine)
    paths = c.get("/openapi.json").json()["paths"]
    mine = {p: m for p, m in paths.items() if p.startswith("/api/hardware")}
    assert set(mine) == {
        "/api/hardware/profile",
        "/api/hardware/gates",
        "/api/hardware/gates/{op}",
        "/api/hardware/status",
        "/api/hardware/config",
        "/api/hardware/config/match",
        "/api/hardware/config/draft",
    }
    assert {p: set(m) for p, m in mine.items() if set(m) != {"get"}} == \
        {"/api/hardware/config/draft": {"get", "post"}}
    assert c.post("/api/hardware/profile", json={}).status_code == 405


def test_profile_is_null_before_the_first_scan(make_client, with_hardware):
    block = {
        "profile": None,
        "profile_path": None,
        "sha256": None,
        "previous": None,
        "gates": [],
        "objective_options": [],
        "last_status": None,
    }
    r = make_client(with_hardware(block)).get("/api/hardware/profile")
    assert r.status_code == 200
    assert r.json() == {
        "profile": None,
        "path": None,
        "sha256": None,
        "previous": None,
        "error": None,
    }


def test_profile_without_a_hardware_block(make_client, engine):
    """An engine that reports no hardware block at all reads as "never scanned"."""
    c = make_client(engine)
    assert c.get("/api/hardware/profile").json()["profile"] is None
    assert c.get("/api/hardware/gates").json() == []
    assert c.get("/api/hardware/status").json() is None


def test_runner_default_block_reads_as_never_scanned(make_client, with_hardware):
    """The runner's own default before `hardware=` is wired: gates is an empty dict."""
    c = make_client(
        with_hardware({"profile": None, "profile_path": None, "gates": {}, "last_status": None})
    )
    assert c.get("/api/hardware/profile").json()["profile"] is None
    assert c.get("/api/hardware/gates").json() == []


def test_t028_profile_is_reshaped_for_the_screen(make_client, hw_engine):
    body = make_client(hw_engine).get("/api/hardware/profile").json()
    p = body["profile"]
    assert body["path"].endswith("hardware_profile.json")
    assert body["sha256"] == SHA  # the engine's hash of the file, not recomputed here
    assert p["backend_kind"] == "mock" and "backend" not in p
    assert p["host"] == "MICROSCOPE" and p["bench"] is False
    assert p["objective"] == "1-Plan Apo LmbdD20 4x"
    assert p["config"]["path"] == "C:/mm/demo.cfg"
    # device_list rows, then the roles no loaded device fills (piezo: a problem row)
    assert [d["label"] for d in p["devices"]] == ["Kinetix_red", "XYStage", "piezo"]
    xy = p["devices"][1]
    assert xy["type"] == "XYStageDevice" and xy["present"] is True and xy["read_back"] is False
    assert "properties" not in xy
    assert p["devices"][2] == {
        "label": "piezo",
        "role": "piezo",
        "type": None,
        "library": None,
        "description": None,
        "present": False,
        "read_back": False,
        "write_verified": None,
        "note": "port skipped",
    }
    oil = p["objectives"][1]
    assert oil["registry_key"] == "100x-Oil" and oil["working_distance_um"] == 130
    assert oil["immersion"] == "oil" and oil["na"] is None
    assert p["camera"]["sensor"] == [2400, 2400] and p["camera"]["ceiling_adu"] == 4095
    assert p["piezo"]["port"] == "" and p["piezo"]["connected"] is False
    assert p["human_confirmed"]["DiaLamp intensity"] == {
        "value": "608/2100",
        "by": "otto",
        "at": "09:01",
    }
    assert p["notes"] == {"stage_limits": "unmeasured provisional"}


def test_previous_profile_diff_comes_from_the_engine(make_client, hw_engine):
    prev = make_client(hw_engine).get("/api/hardware/profile").json()["previous"]
    assert prev["sha256"] == "ef" * 32
    assert prev["changed"] == [{"key": "device.XYStage.read_back", "before": True, "after": False}]


def test_skeleton_profile_still_reads(make_client, with_hardware):
    """A T-002 skeleton profile (main before T-028): roles only, labels only, who/when only."""
    skeleton = {
        "backend_kind": "mock",
        "detected_at": "2026-10-01T18:00:00",
        "devices": {
            "camera": {"present": True, "readable": True, "label": "Kinetix_red", "note": ""}
        },
        "objectives": ["1-Plan Apo LmbdD20 4x"],
        "camera_bit_depth": 12,
        "confirmed": {"DiaLamp intensity": "otto 18:05"},
    }
    eng = with_hardware(
        {"profile": skeleton, "profile_path": None, "gates": {}, "last_status": None}
    )
    p = make_client(eng).get("/api/hardware/profile").json()["profile"]
    assert p["devices"][0]["label"] == "Kinetix_red" and p["devices"][0]["read_back"] is True
    assert p["objectives"][0]["label"] == "1-Plan Apo LmbdD20 4x"
    assert p["camera"]["bit_depth"] == 12
    assert p["human_confirmed"]["DiaLamp intensity"] == {
        "value": "not reported",
        "by": "otto 18:05",
        "at": None,
    }


def test_gates_off_first_with_reasons_and_requirements(make_client, hw_engine):
    rows = make_client(hw_engine).get("/api/hardware/gates").json()
    assert [r["op"] for r in rows] == [
        "light_set:brightfield",
        "sample_map",
        "light_set:aura",
        "light_set:off",
        "status",
    ]
    sample_map = rows[1]
    assert sample_map["reasons"] == ["xy_stage detected but its state did not read back"]
    assert sample_map["requires"] == {
        "devices": ["camera", "xy_stage", "z_drive", "dia_lamp"],
        "objectives": ["4x"],
        "confirmed": [],
        "checks": ["camera_bit_depth"],
        "arg": None,
    }


def test_light_set_rows_are_per_mode(make_client, hw_engine):
    c = make_client(hw_engine)
    bf = c.get("/api/hardware/gates/light_set:brightfield").json()
    assert bf["enabled"] is False and bf["reasons"] == ["dia_lamp not detected"]
    assert bf["requires"]["arg"] == {"mode": "brightfield"}
    assert c.get("/api/hardware/gates/light_set:aura").json()["enabled"] is True
    assert c.get("/api/hardware/gates/light_set").status_code == 404  # only per-mode rows


def test_a_gate_without_a_plain_yes_is_off(make_client, with_hardware):
    gates = [{"op": "scan_4x", "reasons": []}, {"op": "status", "enabled": "yes"}]
    rows = make_client(with_hardware(t028_block(gates=gates))).get("/api/hardware/gates").json()
    assert all(r["enabled"] is False for r in rows)


def test_unknown_gate_is_404_with_a_refusal_code(make_client, hw_engine):
    r = make_client(hw_engine).get("/api/hardware/gates/no_such_op")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "unknown_gate"
    assert r.headers["X-DinoAF-Refusal"] == "unknown_gate"


def test_status_is_the_last_result(make_client, with_hardware):
    last = {
        "op_id": "op7",
        "t": 1759340000.0,
        "summary": {
            "nosepiece_label": "1-Plan Apo LmbdD20 4x",
            "z_um": 3012.5,
            "pfs_in_range": "Out of Range",
        },
    }
    body = (
        make_client(with_hardware(t028_block(last_status=last))).get("/api/hardware/status").json()
    )
    assert body == {"op_id": "op7", "t": 1759340000.0, "user_id": None, "summary": last["summary"]}


def test_engine_hardware_error_is_reported(make_client, with_hardware):
    eng = with_hardware(
        {"profile": None, "gates": [], "last_status": None, "error": "profile file unreadable"}
    )
    body = make_client(eng).get("/api/hardware/profile").json()
    assert body["error"] == "profile file unreadable"


def test_a_remote_viewer_reads(make_client, hw_engine):
    c = make_client(hw_engine, remote=True, login=VIEWER)
    for path in ("/api/hardware/profile", "/api/hardware/gates", "/api/hardware/status"):
        assert c.get(path).status_code == 200, path


def test_reads_need_a_login(make_client, hw_engine):
    r = make_client(hw_engine, login=None).get("/api/hardware/profile")
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "login_required"


def test_router_never_writes_to_the_engine(make_client, hw_engine):
    c = make_client(hw_engine)
    for path in (
        "/api/hardware/profile",
        "/api/hardware/gates",
        "/api/hardware/gates/status",
        "/api/hardware/status",
    ):
        c.get(path)
    assert hw_engine.commands == []


# -- /config: the Micro-Manager cfg's device tree -------------------------------------------

MINI_CFG = """\
Property,Core,Initialize,0
Device,Ti2-E__0,NikonTi2,Ti2-E__0
Device,ZDrive,NikonTi2,ZDrive
Parent,ZDrive,Ti2-E__0
Property,Core,Initialize,1
Property,Core,Focus,ZDrive
"""


@pytest.fixture
def no_server_or_repo_cfg(monkeypatch, tmp_path):
    """Only the scanned cfg is listed: mm-real's choice and the repo folder point nowhere."""
    from dino_autofocus.engine.backends import mm_real
    from dino_autofocus.server.api import hardware

    monkeypatch.setattr(mm_real, "config_path", lambda override=None: tmp_path / "absent.cfg")
    monkeypatch.setattr(hardware, "REPO_MM_CONFIGS", tmp_path / "no-repo-configs")


def scanned_cfg_block(path) -> dict[str, Any]:
    return t028_block(profile=t028_profile(config={"path": str(path), "sha256": "cd" * 32}))


def test_config_defaults_to_the_cfg_the_scan_loaded(make_client, with_hardware, tmp_path,
                                                     no_server_or_repo_cfg):
    cfg = tmp_path / "bench.cfg"
    cfg.write_text(MINI_CFG, encoding="utf-8")
    r = make_client(with_hardware(scanned_cfg_block(cfg))).get("/api/hardware/config")
    assert r.status_code == 200
    body = r.json()
    assert (body["path"], body["source"], body["error"]) == (str(cfg), "scanned", None)
    assert [c["source"] for c in body["available"]] == ["scanned"]
    assert len(body["sha256"]) == 64
    z = next(d for d in body["devices"] if d["label"] == "ZDrive")
    assert (z["parent"], z["link"], z["roles"]) == ("Ti2-E__0", "parent", ["Focus"])


def test_config_lists_the_repo_cfgs_and_picks_one_by_path(make_client, hw_engine):
    c = make_client(hw_engine)
    body = c.get("/api/hardware/config").json()
    repo = [a for a in body["available"] if a["source"] == "repo"]
    assert {a["name"] for a in repo} >= {"DMD_dualcam_LUNF.cfg", "single_cam_red_noDMD_nocom10.cfg"}
    dual = next(a for a in repo if a["name"] == "DMD_dualcam_LUNF.cfg")
    picked = c.get("/api/hardware/config", params={"path": dual["path"]}).json()
    assert picked["path"] == dual["path"]
    assert any(d["label"] == "CSUW1-Hub" and d["parent"] == "COM10" for d in picked["devices"])


def test_config_reads_only_listed_files(make_client, hw_engine, tmp_path):
    secret = tmp_path / "other.cfg"
    secret.write_text(MINI_CFG, encoding="utf-8")
    r = make_client(hw_engine).get("/api/hardware/config", params={"path": str(secret)})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "unknown_config"


def test_config_says_when_no_file_is_found(make_client, with_hardware, no_server_or_repo_cfg):
    body = make_client(with_hardware(t028_block())).get("/api/hardware/config").json()
    assert body["path"] is None and body["devices"] == []
    assert body["error"] == "no Micro-Manager config found"


def test_config_is_open_to_a_remote_viewer(make_client, hw_engine):
    r = make_client(hw_engine, remote=True, login=VIEWER).get("/api/hardware/config")
    assert r.status_code == 200


def test_config_prefers_a_byte_identical_copy_of_a_scanned_cfg_not_on_this_machine(
        make_client, with_hardware):
    """The bench scan loaded C:/agentic_microscope/...; this desktop has the repo copy."""
    import hashlib

    from dino_autofocus.server.api.hardware import REPO_MM_CONFIGS

    single = REPO_MM_CONFIGS / "single_cam_red_noDMD_nocom10.cfg"
    sha = hashlib.sha256(single.read_bytes()).hexdigest()
    block = t028_block(profile=t028_profile(config={
        "path": "C:/no-such-bench-folder/single_cam_red_noDMD_nocom10.cfg", "sha256": sha}))
    body = make_client(with_hardware(block)).get("/api/hardware/config").json()
    assert (body["source"], body["sha256"]) == ("scanned-copy", sha)
    assert body["path"] == str(single)
    assert [c["source"] for c in body["available"]].count("scanned-copy") == 1


# -- /config/match and /config/draft: find or make a cfg from the scan ---------------------

TREE_CFG = MINI_CFG + "Property,Core,Camera,Cam\n"
WIRED_ROWS = [
    {"label": "Ti2-E__0", "type": "HubDevice", "library": "NikonTi2", "description": "",
     "role": None, "read_back": True, "write_verified": None, "properties": {},
     "adapter": "Ti2-E__0", "parent": None, "preinit": {}, "installed": ["ZDrive", "Nosepiece"]},
    {"label": "ZDrive", "type": "StageDevice", "library": "NikonTi2", "description": "",
     "role": "z_drive", "read_back": True, "write_verified": None, "properties": {},
     "adapter": "ZDrive", "parent": "Ti2-E__0", "preinit": {}, "installed": None},
    {"label": "Core", "type": "CoreDevice", "library": "", "description": "", "role": None,
     "read_back": True, "write_verified": None, "properties": {}},
]


@pytest.fixture
def wired_engine(with_hardware, tmp_path, no_server_or_repo_cfg):
    """A scan of Ti2-E__0 + ZDrive that loaded `scanned.cfg` (which also declares nothing more)."""
    cfg = tmp_path / "scanned.cfg"
    cfg.write_text(MINI_CFG, encoding="utf-8")
    profile = t028_profile(device_list=WIRED_ROWS, objective_rows=[],
                           config={"path": str(cfg), "sha256": "cd" * 32})
    return with_hardware(t028_block(profile=profile))


def test_match_ranks_the_listed_cfgs_against_the_scan(make_client, wired_engine, tmp_path):
    body = make_client(wired_engine).get("/api/hardware/config/match").json()
    assert body["error"] is None and body["detected_at"] == "2026-10-02T09:00:00"
    best = body["rows"][0]
    assert (best["name"], best["exact"], best["score"]) == ("scanned.cfg", True, 1.0)
    assert best["matched"] == ["Ti2-E__0", "ZDrive"]


def test_match_before_a_scan_says_so(make_client, with_hardware):
    body = make_client(with_hardware({"profile": None})).get("/api/hardware/config/match").json()
    assert body["rows"] == [] and "not scanned" in body["error"]


def test_draft_is_built_from_the_scan_and_passes_the_load_check(make_client, wired_engine):
    r = make_client(wired_engine).get("/api/hardware/config/draft")
    assert r.status_code == 200
    d = r.json()
    assert d["devices"] == 2 and d["base"]["name"] == "scanned.cfg"
    assert "Device,ZDrive,NikonTi2,ZDrive" in d["text"]
    assert "Parent,ZDrive,Ti2-E__0" in d["text"]
    assert "Property,Core,Focus,ZDrive" in d["text"]
    assert d["hub_found"] == ["Ti2-E__0: Nosepiece"]
    assert d["load_check"] is None
    assert d["suggested_name"] == "from-scan-202610020900"


def test_draft_before_a_scan_is_refused(make_client, with_hardware):
    r = make_client(with_hardware({"profile": None})).get("/api/hardware/config/draft")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_scanned"


def test_save_writes_a_new_file_that_is_then_listed(make_client, wired_engine, seat):
    c = make_client(wired_engine)
    r = c.post("/api/hardware/config/draft", json={"name": "bench-from-scan"})
    assert r.status_code == 201, r.text
    saved = r.json()
    path = Path(saved["path"])
    assert path.name == "bench-from-scan.cfg" and path.parent.name == "micromanager"
    assert path.parent.parent == Path(seat.accounts.path).parent  # the settings folder
    assert "Device,ZDrive,NikonTi2,ZDrive" in path.read_text(encoding="utf-8")
    listed = c.get("/api/hardware/config").json()["available"]
    assert {"path": str(path), "name": "bench-from-scan.cfg", "source": "saved"} in listed
    # never replaced
    again = c.post("/api/hardware/config/draft", json={"name": "bench-from-scan.cfg"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "exists"


@pytest.mark.parametrize("name", ["", "../escape", "a/b", "con fig", ".hidden", "x" * 81])
def test_save_refuses_a_bad_file_name(make_client, wired_engine, name):
    r = make_client(wired_engine).post("/api/hardware/config/draft", json={"name": name})
    assert r.status_code == 422


def test_save_is_for_the_local_operator_only(make_client, wired_engine):
    viewer = make_client(wired_engine, login=VIEWER).post(
        "/api/hardware/config/draft", json={"name": "x"})
    assert viewer.status_code == 403 and viewer.json()["detail"]["code"] == "role"
    remote = make_client(wired_engine, remote=True).post(
        "/api/hardware/config/draft", json={"name": "x"})
    assert remote.status_code == 403 and remote.json()["detail"]["code"] == "remote_view"
    foreign = make_client(wired_engine).post(
        "/api/hardware/config/draft", json={"name": "x"}, headers={"Origin": "http://evil.test"})
    assert foreign.status_code == 403 and foreign.json()["detail"]["code"] == "foreign_origin"


def test_a_scan_only_draft_uses_no_base(make_client, wired_engine):
    d = make_client(wired_engine).get("/api/hardware/config/draft",
                                      params={"no_base": "true"}).json()
    assert d["base"] is None and d["from_base"] == []
    assert "Device,ZDrive,NikonTi2,ZDrive" in d["text"]  # the scan reported the adapter
