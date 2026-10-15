"""Gates: the profile round-trips through JSON and every disabled op says why."""

from dino_autofocus.engine.gates import DeviceStatus, Gate, HardwareProfile, evaluate


def profile(**devices):
    return HardwareProfile("fake", devices={k: DeviceStatus(*v) for k, v in devices.items()},
                           objectives=["1-Plan Apo LmbdD20 4x"], camera_bit_depth=12)


def test_profile_round_trips(tmp_path):
    p = profile(camera=(True, True, "Kinetix_red"), z_drive=(True, False, "ZDrive"))
    p.confirmed["oil_objective_clean"] = "operator@example.test 2026-10-01"
    assert HardwareProfile.from_json(p.save(tmp_path / "hardware_profile.json").read_text()) == p


def test_disabled_ops_carry_every_reason():
    p = profile(camera=(True, True), xy_stage=(True, True), z_drive=(True, False))
    r = evaluate(p, (Gate("status", ("camera",)),
                     Gate("sample_map", ("camera", "xy_stage", "z_drive", "dia_lamp"), ("4x",)),
                     Gate("focus_100x", ("camera",), ("100x-Oil",), ("oil_loaded",))))
    assert r["status"].enabled and r["status"].reasons == []
    assert not r["sample_map"].enabled
    assert r["sample_map"].reasons == ["z_drive detected but its state did not read back",
                                       "dia_lamp not detected"]
    assert r["focus_100x"].reasons == ["objective 100x-Oil not on the nosepiece",
                                       "not confirmed by the operator: oil_loaded"]
