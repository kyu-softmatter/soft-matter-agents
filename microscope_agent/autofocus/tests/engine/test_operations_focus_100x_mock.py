"""focus_100x through the engine runner on MockBackend (T-031)."""

import json

import pytest
import test_operations_scan_4x_mock as scan_mock
from test_operations_scan_4x_mock import mock, sample_for, start, yes

from dino_autofocus.engine.backends.mock_world import objective_at
from dino_autofocus.engine.events import Command
from dino_autofocus.engine.operations import focus_100x as F

engine = scan_mock.engine  # the runner fixture, shared with the scan_4x tests


def in_window_100x():
    return mock(z_um=2900.0, nosepiece=5)  # after objective_change: 100x Oil, Z in the window


def test_focus_100x_on_the_mock_climbs_only_after_a_yes(engine, tmp_path):
    b = in_window_100x()
    s = sample_for(tmp_path, b)
    truth = b.world.in_focus_z()
    r, sink = engine(b, s)
    # no 4x scan: the default centre 2930 sweeps 2890-2970, below the mock's ~2989 focus
    op = r.submit(start("focus_100x", sample_id=s.id, oil_loaded=True, exposure_ms=20.0))
    ask = sink.wait(op, "confirm_required", key="climb_past_top")
    assert ask.data["context"]["span_um"] == [2890.0, 2970.0]
    assert b.world.z_um == pytest.approx(2890.0)  # went back down before asking
    r.submit(yes(op, "climb_past_top"))
    end = sink.wait(op, "finished", "error", "aborted")
    assert end.kind == "finished", end.data
    res = end.data["summary"]
    assert res["peak_at"] == "interior"
    assert res["z_focus_um"] == pytest.approx(truth, abs=1.0)
    assert b.world.z_um == pytest.approx(res["z_parked_um"])
    assert max(p["z_um"] for p in res["coarse"]) <= 2970.0 + 52.0 + 1e-6  # guard ceiling
    d = sorted(s.dir.glob("focus100x_*"))[-1]
    summary = json.loads((d / "summary.json").read_text())
    assert summary["status"] == "finished" and b.light_state()["Aura"] == "0"


def test_centre_from_the_4x_plane_finds_focus_without_asking(engine, tmp_path):
    b = in_window_100x()
    s = sample_for(tmp_path, b)
    d = s.dir / "scan4x_20261001-120000"
    d.mkdir()
    x, y = b.world.x_um, b.world.y_um
    (d / "scan.json").write_text(json.dumps({"tiles": [
        {"x_um": x, "y_um": y, "z_focus_um": b.world.in_focus_z(x, y, objective_at(0))}]}))
    r, sink = engine(b, s)
    op = r.submit(start("focus_100x", sample_id=s.id, oil_loaded=True, exposure_ms=20.0))
    end = sink.wait(op, "finished", "error", "aborted")
    assert end.kind == "finished", end.data
    res = end.data["summary"]
    assert "4x plane" in res["centre_source"] and res["grades"]["centre_um"] == "computed"
    assert res["z_focus_um"] == pytest.approx(b.world.in_focus_z(), abs=1.0)
    assert not [e for e in sink.events if e.op_id == op and e.kind == "confirm_required"]


def test_no_oil_record_is_asked_and_no_ends_in_error(engine, tmp_path):
    b = in_window_100x()
    s = sample_for(tmp_path, b)
    r, sink = engine(b, s)
    op = r.submit(start("focus_100x", sample_id=s.id, centre_um=2985.0))
    sink.wait(op, "confirm_required", key="oil_applied")
    r.submit(Command("confirm", op_id=op, args={"key": "oil_applied", "ok": False},
                     user_id="op@example.test", session_id="20261001_1540_1"))
    end = sink.wait(op, "error", "finished", "aborted")
    assert end.kind == "error" and "no immersion oil" in end.data["message"]
    assert b.world.z_um == pytest.approx(2900.0) and b.light_state()["Aura"] == "0"


def test_wrong_lens_fails_preflight(engine, tmp_path):
    b = mock(z_um=2900.0, nosepiece=0)
    s = sample_for(tmp_path, b)
    r, sink = engine(b, s)
    op = r.submit(start("focus_100x", sample_id=s.id, oil_loaded=True))
    ev = sink.wait(op, "preflight_failed")
    assert any("100x Oil" in c["why"] for c in ev.data["checks"] if not c["ok"])


def test_plan_shows_ceiling_without_hardware(engine, tmp_path):
    b = in_window_100x()
    s = sample_for(tmp_path, b)
    r, _ = engine(b, s)
    p = r.plan(start("focus_100x", sample_id=s.id, centre_um=3180.0))["plan"]
    assert p["ceiling_um"] == 3200.0 and p["op"] == F.NAME
