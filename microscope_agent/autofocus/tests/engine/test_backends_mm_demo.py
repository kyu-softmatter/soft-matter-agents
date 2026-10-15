"""mm-demo backend: the Backend protocol on Micro-Manager's demo devices (T-023).

`TestMmDemoContract` runs T-015's `BackendContract` on mm-demo. The T-002 checks of
tests/engine/test_contract.py run here on both FakeBackend and mm-demo. mm-demo cases skip
without the demo adapters. Each test opens its own core and closes it; no test opens a
window.
"""

import json
import subprocess
import sys

import numpy as np
import pytest
from test_contract_backend_v2 import BackendContract

from dino_autofocus.engine.backend import (
    GUARD_TOKEN,
    PROVISIONAL,
    Backend,
    PropertyNotAllowed,
    UnguardedMotion,
)
from dino_autofocus.engine.backends.mm_demo import MmDemoBackend
from dino_autofocus.engine.backends.mm_demo_core import DemoUnavailable, DemoZRangeError

T = GUARD_TOKEN  # tests stand in for engine.guards


def open_demo(**kw) -> MmDemoBackend:
    b = MmDemoBackend(**kw)
    try:
        b.open()
    except DemoUnavailable as e:
        pytest.skip(f"Micro-Manager demo adapters not available: {e}")
    return b


@pytest.fixture
def demo():
    b = open_demo(roi=256)
    try:
        yield b
    finally:
        b.close()


class TestMmDemoContract(BackendContract):
    light_write = ("White Light Shutter", "State", 0)

    @pytest.fixture
    def backend(self, demo):
        return demo


@pytest.fixture(params=["fake", "mm-demo"])
def backend(request):
    return request.getfixturevalue("fake" if request.param == "fake" else "demo")


# -- the T-002 contract, parametrised


def test_meets_protocol_and_info_is_json(backend):
    assert isinstance(backend, Backend)
    json.dumps(backend.info().to_dict())
    assert backend.info().ceiling_adu >= 4095


def test_refuses_unguarded_motion(backend):
    for call in (lambda: backend.move_z(3000.0, token=None),
                 lambda: backend.move_xy(0.0, 0.0, token=None),
                 lambda: backend.set_nosepiece(0, token=None),
                 lambda: backend.pfs_off(token=None)):
        with pytest.raises(UnguardedMotion):
            call()


def test_light_read_back_and_off(backend):
    assert all(r.verified for r in backend.aura_line_on("GREEN", 1, token=T))
    assert backend.light_state()["Aura"] == "1"
    assert all(r.verified for r in backend.all_off())
    assert backend.light_state()["Aura"] == "0" and backend.light_state()["DiaLamp"] == "0"


def test_guarded_z_reads_back_in_bench_coordinates(backend):
    assert backend.move_z(2950.0, token=T) == pytest.approx(2950.0)
    assert backend.positions().z_um == pytest.approx(2950.0)
    f = backend.snap()
    assert f.image.dtype == np.uint16 and f.image.ndim == 2
    assert f.z_um == pytest.approx(2950.0)


# -- mm-demo only


def test_import_does_not_load_pymmcore():
    code = ("import sys, dino_autofocus.engine.backends.mm_demo; "
            "sys.exit('pymmcore_plus' in sys.modules or 'pymmcore' in sys.modules)")
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_info(demo):
    info = demo.info()
    assert info.kind == "mm-demo" and info.bit_depth == 16
    assert info.sensor == (2400, 2400) and info.roi[2:] == (256, 256)
    assert info.stage_limits.z_um == (0.0, 3300.0)
    by_state = {o.state: o for o in info.objectives}
    assert len(by_state) == 6
    assert by_state[0].label == "1-Plan Apo LmbdD20 4x" and by_state[0].magnification == 4
    assert by_state[5].free_wd_um == 130.0 and by_state[5].pixel_um == 0.065
    assert [by_state[s].free_wd_um for s in (1, 2, 3, 4)] == [4000.0, 800.0, 170.0, 150.0]
    assert "simulated" in info.notes["z_below_range"] and "simulated" in info.notes["pfs"]
    assert info.notes["aura.CYAN"] == PROVISIONAL and "aura.GREEN" not in info.notes
    assert json.loads(demo.read_property("mm-demo", "notes")) == info.notes


def test_retract_zone_parks_at_demo_floor_and_reads_commanded(demo):
    demo.move_z(2900.0, token=T)
    assert demo.pfs().in_range == "In Range"
    assert demo.read_property("mm-demo", "demo_retract") == ""
    assert demo.move_z(0.0, token=T) == 0.0  # the full retract
    assert demo.positions().z_um == 0.0
    assert demo.dev.core.getPosition("Z") == pytest.approx(-300.0)  # physically at bench 2700
    sub = json.loads(demo.read_property("mm-demo", "demo_retract"))
    assert sub["kind"] == "demo_retract" and sub["commanded_um"] == 0.0
    assert sub["physical_bench_um"] == pytest.approx(2700.0)
    assert sub["physical_demo_um"] == pytest.approx(-300.0)
    assert demo.pfs().out_of_range


def test_simulated_z_ends_when_the_demo_stage_moves_off_the_floor(demo):
    demo.move_z(0.0, token=T)
    demo.dev.core.setPosition("Z", -250.0)  # moved behind the backend's back
    demo.dev.core.waitForDevice("Z")
    assert demo.positions().z_um == pytest.approx(2750.0)


def test_approach_steps_from_retract(demo):
    demo.move_z(0.0, token=T)
    n0 = len(demo.substitutions)
    for z in np.arange(100.0, 2801.0, 100.0):  # FocusAxis.approach-like climb
        assert demo.move_z(float(z), token=T) == pytest.approx(z)
    assert len(demo.substitutions) - n0 == 26  # 100 .. 2600 were in the zone; 2700, 2800 real
    assert demo.dev.core.getPosition("Z") == pytest.approx(-200.0)
    assert demo.read_property("mm-demo", "demo_retract") == ""
    assert not demo.pfs().out_of_range


@pytest.mark.parametrize("bad", [-0.1, 3300.1, float("nan")])
def test_z_outside_demo_refused_without_moving(demo, bad):
    demo.move_z(3010.0, token=T)
    with pytest.raises(DemoZRangeError):
        demo.move_z(bad, token=T)
    assert demo.positions().z_um == pytest.approx(3010.0)


def test_no_demo_z_number_leaves_the_backend(demo):
    demo.move_z(2950.0, token=T)
    assert float(demo.read_property("Z", "Position")) == pytest.approx(2950.0)
    z = next(d for d in demo.describe_devices() if d.label == "Z")
    assert float(z.properties["Position"].value) == pytest.approx(2950.0)
    assert "bench um" in z.description


def test_nosepiece_turn_from_retract(demo):
    demo.move_z(0.0, token=T)
    assert demo.pfs().out_of_range and demo.pfs_off(token=T).verified
    rb = demo.set_nosepiece(5, token=T)
    assert rb.verified and demo.nosepiece() == "6-Plan Apo LmbdD0.13 100x Oil"
    assert demo.info().pixel_um == 0.065
    labels = {n.state: n for n in demo.nosepiece_labels()}
    assert labels[0].label == "1-Plan Apo LmbdD20 4x" and labels[0].pixel_um == 1.625


def test_light_through_demo_names_only(demo):
    assert demo.set_property("LED", "Label", "470nm", token=T).verified
    for dev, prop in (("Aura", "State"), ("DiaLamp", "State")):  # bench names: not devices here
        with pytest.raises(PropertyNotAllowed, match="not a device on mm-demo"):
            demo.set_property(dev, prop, 0, token=T)


@pytest.mark.parametrize("dev, prop", [("Camera", "SimulateCrash"), ("Camera", "Gain"),
                                       ("LED Shutter", "State Device"), ("Dichroic", "State")])
def test_set_property_outside_allow_list_refused(demo, dev, prop):
    with pytest.raises(PropertyNotAllowed, match="allow-list"):
        demo.set_property(dev, prop, 1, token=T)


def test_provisional_aura_line_in_notes_not_names(demo):
    recs = demo.aura_line_on("CYAN", 2.0, token=T)
    assert all(r.verified for r in recs)
    assert all("provisional" not in r.device + r.prop for r in recs)
    label = next(r for r in recs if r.prop == "Label")
    assert label.notes == {"line": PROVISIONAL, "bench_line": "CYAN"}
    assert demo.substitutions[-1]["kind"] == "aura_line"
    n = len(demo.substitutions)
    assert all(not r.notes for r in demo.aura_line_on("GREEN", 1.0, token=T))
    assert len(demo.substitutions) == n  # GREEN is bench-confirmed


def test_config_record(demo):
    cfg = demo.config_record()
    assert cfg.path.endswith("MMConfig_demo.cfg") and len(cfg.sha256) == 64
    assert cfg.changed_during_load is False
    assert cfg.autoshutter.verified and cfg.startup_preset == "System/Startup"


def test_close_is_idempotent_and_dark():
    b = open_demo(roi=64)
    try:
        b.lamp_on(token=T)
        b.start_stream()
    finally:
        b.close()
    b.close()
    assert b.dev is None and not b.streaming()
