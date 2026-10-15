"""WP-G gate rules: the real gate list, arg rows, strict default, objective options, history."""

from __future__ import annotations

import json

from dino_autofocus.engine.gates import (
    GATES,
    NOT_SCANNED,
    UNGATED,
    DeviceStatus,
    HardwareProfile,
    ObjectiveRow,
    ProfileStore,
    check,
    diff,
    evaluate,
    gate_rows,
    objective_options,
)
from dino_autofocus.engine.guards import FREE_WD_UM
from dino_autofocus.engine.runner import PERMISSIONS

ALL = ("camera", "xy_stage", "z_drive", "dia_lamp", "aura", "nosepiece", "pfs")
LABELS = ["1-Plan Apo LmbdD20 4x", "4-Plan Apo 40x WI", "6-Plan Apo LmbdD0.13 100x Oil"]


def full(**over) -> HardwareProfile:
    devices = {r: DeviceStatus(True, True, r) for r in ALL}
    rows = [ObjectiveRow(0, LABELS[0], registry_key="4x", working_distance_um=20000.0),
            ObjectiveRow(3, LABELS[1], registry_key="40x-WI"),
            ObjectiveRow(5, LABELS[2], registry_key="100x-Oil", working_distance_um=130.0)]
    p = HardwareProfile("fake", devices=devices, objectives=list(LABELS), camera_bit_depth=12,
                        objective_rows=rows, objective=LABELS[0])
    for k, v in over.items():
        setattr(p, k, v)
    return p


def test_every_runner_operation_is_gated_or_listed_ungated():
    gated = {g.op for g in GATES}
    assert not gated & UNGATED
    assert set(PERMISSIONS) <= gated | UNGATED, set(PERMISSIONS) - gated - UNGATED


def test_without_a_profile_every_gate_is_off_but_stops_and_records_are_not():
    assert all(not r.enabled and r.reasons == [NOT_SCANNED] for r in evaluate(None).values())
    for op in ("lights_off", "abort", "hardware_scan", "hardware_confirm", "map_flag"):
        assert check(None, op) == (True, [])


def test_full_profile_opens_every_gate():
    assert all(r.enabled for r in evaluate(full()).values())


def test_unknown_operation_is_off_by_default():
    assert check(full(), "find_particle_z") == (False, ["no gate rule for 'find_particle_z'"])


def test_light_set_row_follows_the_mode():
    p = full()
    p.devices["aura"] = DeviceStatus(False, False)
    assert check(p, "light_set", {"mode": "brightfield"}) == (True, [])
    aura = check(p, "light_set", {"mode": "aura", "line": "GREEN"})
    assert aura == (False, ["aura not detected"])
    assert check(p, "light_set", {"mode": "off"}) == (True, [])
    ok, why = check(p, "light_set", {"mode": "strobe"})
    assert not ok and why == ["light_set: mode must be one of ['aura', 'brightfield', 'off']"]


def test_scan_4x_reasons_name_every_missing_piece():
    p = full(camera_bit_depth=None, objectives=[LABELS[2]])
    p.devices["pfs"] = DeviceStatus(True, False, "PFS")
    ok, why = check(p, "scan_4x")
    assert not ok
    assert why == ["pfs detected but its state did not read back",
                   "objective 4x not on the nosepiece",
                   "camera bit depth not read (it sets the saturation ceiling and auto exposure)"]


def test_loading_check_image_needs_camera_dialamp_and_4x():
    p = full()
    del p.devices["dia_lamp"]
    assert check(p, "loading_check_image") == (False, ["dia_lamp not detected"])


def test_gate_rows_put_disabled_first_and_carry_requirements():
    p = full()
    p.devices["xy_stage"] = DeviceStatus(False, False)
    rows = gate_rows(p)
    off = [r["op"] for r in rows if not r["enabled"]]
    assert rows[: len(off)] == [r for r in rows if not r["enabled"]]
    assert off == sorted(off) and "edge_trace" in off and "goto_xy" in off
    edge = next(r for r in rows if r["op"] == "edge_trace")
    assert edge["requires"] == {"devices": ["camera", "xy_stage", "dia_lamp"],
                                "objectives": ["4x"], "confirmed": [], "checks": [],
                                "arg": None}
    aura = next(r for r in rows if r["op"] == "light_set:aura")
    assert aura["requires"]["arg"] == {"mode": "aura"}
    json.dumps(rows)


def test_objective_options_say_why_a_position_is_not_selectable(monkeypatch):
    monkeypatch.delitem(FREE_WD_UM, "40x-WI")  # a lens without a value
    opts = {o["state"]: o for o in objective_options(full())}
    assert opts[0]["reasons"] == ["already on this objective"]
    assert opts[3]["reasons"] == ["working distance of 40x-WI not in the guards' lens table"]
    assert opts[5]["selectable"] and opts[5]["immersion"] is None  # rows built by hand here
    live = {o["state"]: o for o in objective_options(full(), current_label=LABELS[2])}
    assert live[0]["selectable"] and not live[5]["selectable"]


def test_objective_options_carry_the_gate_reasons():
    p = full()
    p.devices["pfs"] = DeviceStatus(False, False)
    assert all("pfs not detected" in o["reasons"] for o in objective_options(p))
    assert objective_options(None) == []


def test_store_keeps_history_and_diffs_configuration_only(tmp_path):
    store = ProfileStore(tmp_path / "hw")
    assert store.latest() is None and store.previous() is None
    first = store.save(full(positions={"x_um": 1.0}))
    assert first["previous"] is None
    second = full(positions={"x_um": 2.0}, lights={"DiaLamp": "1"})
    second.devices["pfs"] = DeviceStatus(False, False)
    saved = store.save(second)
    keys = [c["key"] for c in saved["previous"]["changed"]]
    assert keys == ["role.pfs"]  # positions and lights are state, not configuration
    assert saved["previous"]["sha256"] == first["sha256"]
    assert store.previous() == saved["previous"]  # survives a restart
    assert len(store.history()) == 2
    profile, path, sha = store.latest()
    assert profile == second and sha == saved["sha256"] and path == store.latest_path


def test_diff_ignores_property_values_but_not_property_metadata():
    before = {"device_list": [{"label": "Cam", "type": "CameraDevice", "properties": {
        "Exposure": {"value": "10", "read_only": False, "allowed": [], "limits": None}}}]}
    after = json.loads(json.dumps(before))
    after["device_list"][0]["properties"]["Exposure"]["value"] = "30"
    assert diff(before, after) == []
    after["device_list"][0]["properties"]["Exposure"]["read_only"] = True
    assert [c["key"] for c in diff(before, after)] == ["device.Cam.property.Exposure"]
