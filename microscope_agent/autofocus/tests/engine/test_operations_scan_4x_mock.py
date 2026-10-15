"""scan_4x through the engine runner on MockBackend (T-031): registration, rule 12, confirm,
the record folder and the exit path. A 256 x 256 sensor and a 0.6 mm hole keep it fast."""

import json
import threading
import time

import pytest

from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.backends.mock_world import Camera, MockWorld, SampleSpec
from dino_autofocus.engine.events import Command, Event
from dino_autofocus.engine.mosaic import load_mosaic
from dino_autofocus.engine.operations import focus_100x as F
from dino_autofocus.engine.operations import scan_4x as S
from dino_autofocus.engine.runner import (
    OPERATIONS,
    PERMISSIONS,
    AllowAll,
    CommandRefused,
    DenyAll,
    Runner,
    RunnerConfig,
    folder_records,
)
from dino_autofocus.engine.sample import Sample, SampleInfo

T = 120.0
USER, SESSION = "op@example.test", "20261001_1540_1"
SESSION_START = time.mktime(time.strptime("2026-10-01T09:00:00", "%Y-%m-%dT%H:%M:%S"))
FULL = "back where the edge was first seen: full loop"
QUIET = RunnerConfig(position_interval_s=None)


class Collect:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._cond = threading.Condition()

    def __call__(self, ev: Event) -> None:
        with self._cond:
            self.events.append(ev)
            self._cond.notify_all()

    def wait(self, op_id: str, *kinds: str, key: str | None = None) -> Event:
        def find():
            return next((e for e in self.events if e.op_id == op_id and e.kind in kinds
                         and (key is None or e.data.get("key") == key)), None)

        with self._cond:
            assert self._cond.wait_for(lambda: find() is not None, T), \
                (kinds, [e.kind for e in self.events if e.op_id == op_id])
            return find()


def mock(hole_mm=0.6, z_um=None, nosepiece=0, faults=None):
    world = MockWorld(SampleSpec(seed=3, hole_diameter_mm=hole_mm),
                      camera=Camera(sensor=(256, 256)))
    if z_um is not None:
        world.z_um = z_um
    world.nosepiece = nosepiece
    b = MockBackend(world, faults=faults)
    b.open()
    return b


def sample_for(root, b, fitted="2026-10-01T10:00:00", stop=FULL):
    s = Sample.create(root)
    spec = b.world.spec
    s.save_info(SampleInfo(s.id, hole={"centre_um": list(spec.hole_centre_um),
                                       "diameter_mm": spec.hole_diameter_mm,
                                       "fitted_at": fitted, "trace_stop": stop,
                                       "arc_deg": 360.0}))
    return s


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(S.Scan4x, "samples_root", tmp_path)
    monkeypatch.setattr(F.Focus100x, "samples_root", tmp_path)
    made = []

    def build(b, sample, control=None, session=True):
        r = Runner(b, control=control or AllowAll(), config=QUIET,
                   records=folder_records(lambda meta: sample.dir))
        sink = Collect()
        r.subscribe(sink)
        r.start()
        if session:
            r.set_experiment_session(SESSION, SESSION_START)
        made.append(r)
        return r, sink

    yield build
    for r in made:
        r.shutdown("test teardown", timeout=30)


def start(op, **args):
    return Command("start", op=op, args=args, user_id=USER, session_id=SESSION)


def yes(op_id, key):
    return Command("confirm", op_id=op_id, args={"key": key, "ok": True}, user_id=USER,
                   session_id=SESSION)


def test_registered_as_motion():
    assert OPERATIONS.get("scan_4x") is S.Scan4x and OPERATIONS.get("focus_100x") is F.Focus100x
    assert PERMISSIONS["scan_4x"].action == "motion" and PERMISSIONS["scan_4x"].control
    assert PERMISSIONS["focus_100x"].session
    assert S.Scan4x.record_prefix == "scan4x" and S.Scan4x.snaps and S.Scan4x.approaches


def test_scan_through_the_runner_on_the_mock(engine, tmp_path):
    b = mock()
    s = sample_for(tmp_path, b)
    r, sink = engine(b, s)
    op = r.submit(start("scan_4x", sample_id=s.id, margin_um=0.0))
    sink.wait(op, "confirm_required", key="z_enter_window")  # the mock starts at 62.9 um
    r.submit(yes(op, "z_enter_window"))
    end = sink.wait(op, "finished", "error", "aborted")
    assert end.kind == "finished", end.data
    d = s.scans_4x()[-1]
    assert str(d) == end.data["record_dir"]
    rec = json.loads((d / "scan.json").read_text())
    assert len(rec["tiles"]) == 4  # 0.6 mm hole, 416 um field: 2 x 2
    for t in rec["tiles"]:
        truth = b.world.in_focus_z(t["x_um"], t["y_um"])
        assert t["z_focus_um"] == pytest.approx(truth, abs=3.0), t["focus_note"]
    assert load_mosaic(d)[1].n_tiles == 4  # engine.mosaic format
    summary = json.loads((d / "summary.json").read_text())
    assert summary["status"] == "finished" and summary["session_id"] == SESSION
    assert summary["lights_off"]["rule"] == "restore"
    assert b.light_state()["Aura"] == "0"  # the exit path turned off what the scan turned on
    res = end.data["summary"]
    assert res["scan_box_um"] and res["focus_plane"]["kind"] == "plane"
    zs = [e.data for e in sink.events if e.op_id == op and e.kind == "motion"
          and e.data.get("axis") == "z"]
    assert zs[0]["how"] == "approach_to_window" and zs[0]["target_um"] == 2800.0


def test_plan_needs_no_hardware(engine, tmp_path):
    b = mock()
    s = sample_for(tmp_path, b)
    r, _ = engine(b, s)
    p = r.plan(start("scan_4x", sample_id=s.id, margin_um=0.0))
    assert p["plan"]["fov_um"] == pytest.approx(2400 * 1.625)  # planned on the Kinetix22 size
    assert p["plan"]["grid_n"] == 1 and p["plan"]["first_sweep"].startswith("4x")


def test_partial_arc_is_refused_in_preflight(engine, tmp_path):
    b = mock()
    s = sample_for(tmp_path, b, stop="operator abort")
    r, sink = engine(b, s)
    op = r.submit(start("scan_4x", sample_id=s.id))
    ev = sink.wait(op, "preflight_failed")
    assert any("partial arc" in c["why"] for c in ev.data["checks"] if not c["ok"])
    sink.wait(op, "error")
    assert b.world.z_um == pytest.approx(62.9)


def test_rule_12_refuses_without_control_or_session(engine, tmp_path):
    b = mock()
    s = sample_for(tmp_path, b)
    r, _ = engine(b, s, control=DenyAll())
    with pytest.raises(CommandRefused):
        r.submit(start("scan_4x", sample_id=s.id))
    r2, _ = engine(b, s, session=False)
    with pytest.raises(CommandRefused):
        r2.submit(start("scan_4x", sample_id=s.id))


def test_abort_while_waiting_ends_aborted_and_dark(engine, tmp_path):
    b = mock()
    s = sample_for(tmp_path, b)
    r, sink = engine(b, s)
    op = r.submit(start("scan_4x", sample_id=s.id, margin_um=0.0))
    sink.wait(op, "confirm_required", key="z_enter_window")
    r.submit(Command("abort", op_id=op, user_id=USER, session_id=SESSION))
    sink.wait(op, "aborted")
    assert b.light_state()["Aura"] == "0" and b.light_state()["DiaLamp"] == "0"
    assert b.world.z_um == pytest.approx(62.9)


def test_light_dropout_fault_on_the_mock_is_filtered(engine, tmp_path):
    b = mock(hole_mm=0.3, z_um=2960.0)  # one tile, already in the window
    s = sample_for(tmp_path, b)
    b.inject_faults(dropout_frames=tuple(range(40, 52)), dropout_factor=0.77)
    r, sink = engine(b, s)
    op = r.submit(start("scan_4x", sample_id=s.id, margin_um=0.0, exposure_ms=500.0))
    end = sink.wait(op, "finished", "error", "aborted")
    assert end.kind == "finished", end.data
    t = end.data["summary"]["tiles"][0]
    assert t["dropout_z_um"], "the injected dropout frames were not flagged"
    truth = b.world.in_focus_z(t["x_um"], t["y_um"])
    assert t["z_focus_um"] == pytest.approx(truth, abs=3.0)


def test_scan_json_carries_the_light_readback_under_the_runner(engine, tmp_path):
    b = mock(hole_mm=0.3, z_um=2960.0)  # one tile, already in the window
    s = sample_for(tmp_path, b)
    r, sink = engine(b, s)
    op = r.submit(start("scan_4x", sample_id=s.id, margin_um=0.0, exposure_ms=500.0))
    end = sink.wait(op, "finished", "error", "aborted")
    assert end.kind == "finished", end.data
    d = s.scans_4x()[-1]
    rec = json.loads((d / "scan.json").read_text())
    assert rec["light_off"]["verified"] and rec["light_off"]["readbacks"]
    assert rec["status"] == "finished" and rec["z_end_um"] == pytest.approx(b.world.z_um)
    summary = json.loads((d / "summary.json").read_text())
    # scan_4x switched off first, so the runner's restore finds nothing to command: it reads
    # both lights off and records no readback of its own (verified None)
    lo = summary["lights_off"]
    assert lo["rule"] == "restore" and lo["aura"]["state"] == lo["dialamp"]["state"] == "off"


def test_abort_mid_scan_still_closes_scan_json(engine, tmp_path):
    b = mock(z_um=2960.0)
    s = sample_for(tmp_path, b)
    r, sink = engine(b, s)
    op = r.submit(start("scan_4x", sample_id=s.id, margin_um=0.0, exposure_ms=500.0))
    sink.wait(op, "frame_ready")  # the first tile is saved
    r.submit(Command("abort", op_id=op, user_id=USER, session_id=SESSION))
    sink.wait(op, "aborted")
    rec = json.loads((s.scans_4x()[-1] / "scan.json").read_text())
    assert rec["status"] == "aborted" and rec["light_off"]["verified"]
    assert 1 <= len(rec["tiles"]) < 4 and b.light_state()["Aura"] == "0"
