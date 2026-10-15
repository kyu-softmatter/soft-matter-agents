"""focus_100x on FakeBackend with focus-dependent frames (T-031). MockBackend (T-021) replaces the
fake here when it lands."""

import json
import queue

import pytest
from test_operations_scan_4x import FocusFake, make_sample

from dino_autofocus.engine.events import Command
from dino_autofocus.engine.guards import GuardError
from dino_autofocus.engine.operations import focus_100x as F
from dino_autofocus.focus.classical import OIL_WARNING


def fake100(focus_z=2985.0, **kw):
    b = FocusFake(focus=lambda x, y: focus_z, dof_um=1.5, z_um=2880.0, **kw)
    b.state = 5  # 6-Plan Apo LmbdD0.13 100x Oil
    return b


def run(backend, sample, answers=(("oil_applied", True),), **args):
    q = queue.Queue()
    for key, ok in answers:
        q.put(Command("confirm", args={"key": key, "ok": ok}))
    events = []
    out = F.run_focus_100x(backend, sample, {"exposure_ms": 30.0, **args}, events.append,
                           answers=q, confirm_timeout_s=1.0, sleep=lambda s: None)
    return out, events


def summary(sample):
    d = sorted(sample.dir.glob("focus100x_*"))[-1]
    return json.loads((d / "summary.json").read_text())


def test_interior_peak_coarse_then_fine(tmp_path):
    b, s = fake100(2985.0), make_sample(tmp_path)
    out, ev = run(b, s, centre_um=2980.0)
    r = out["result"]
    assert out["status"] == "finished" and r["peak_at"] == "interior"
    assert r["z_focus_um"] == pytest.approx(2985.0, abs=0.3) and r["fine"]
    assert r["z_parked_um"] == pytest.approx(r["z_focus_um"])
    assert r["grades"]["z_focus_um"] == "measured" and r["centre_source"] == "argument"
    assert r["ceiling_um"] == pytest.approx(2980.0 + 52.0)
    assert r["args"]["metric"] == "peak" and all("sat" in p for p in r["coarse"])
    assert summary(s)["lights_off"]["verified"] and b.lights["Aura"] == "0"
    assert s.dir.glob("focus100x_*")


def test_top_end_peak_is_not_climbed_without_a_yes(tmp_path):
    b, s = fake100(3000.0), make_sample(tmp_path)  # above the default 2890-2970 span
    out, ev = run(b, s, answers=[("oil_applied", True), ("climb_past_top", False)])
    r = out["result"]
    assert r["peak_at"] == "top_end" and r["z_focus_um"] is None and r["z_parked_um"] is None
    assert b.z == pytest.approx(2890.0)  # back down to the low end, as the script
    ask = next(e.data for e in ev if e.kind == "confirm_required"
               and e.data["key"] == "climb_past_top")
    assert ask["span_um"] == [2890.0, 2970.0] and ask["new_top_um"] <= 2970.0 + 52.0
    assert max(c[1] for c in b.calls if c[0] == "move_z") <= 2970.0


def test_top_end_extension_after_a_yes_finds_the_focus(tmp_path):
    b, s = fake100(3000.0), make_sample(tmp_path)
    out, _ = run(b, s, answers=[("oil_applied", True), ("climb_past_top", True)])
    r = out["result"]
    assert r["peak_at"] == "interior" and r["z_focus_um"] == pytest.approx(3000.0, abs=0.3)
    assert r["coarse_spans_um"][1][0] == 2890.0  # the extension climbs from the low end
    zs = [c[1] for c in b.calls if c[0] == "move_z"]
    rises = [b2 - a2 for a2, b2 in zip(zs, zs[1:], strict=False) if b2 > a2]
    assert max(rises) <= 2.0 + 1e-6  # after the first plane: steps only, no upward jump
    assert max(zs) <= 2970.0 + 52.0


def test_low_end_peak_reports_and_does_not_park(tmp_path):
    b, s = fake100(2860.0), make_sample(tmp_path)
    out, ev = run(b, s)
    r = out["result"]
    assert r["peak_at"] == "low_end" and r["z_focus_um"] is None and r["fine"] is None
    assert any(e.kind == "reading" and e.data.get("peak_at") == "low_end" for e in ev)


def test_no_oil_record_asks_and_a_no_stops(tmp_path):
    b, s = fake100(), make_sample(tmp_path)
    with pytest.raises(GuardError, match="no immersion oil"):
        run(b, s, answers=[("oil_applied", False)])
    sm = summary(s)
    assert sm["status"] == "error" and sm["lights_off"]["verified"]
    assert not any(c[0] == "move_z" for c in b.calls)
    out, ev = run(fake100(), s, answers=(), oil_loaded=True, centre_um=2980.0)
    assert out["status"] == "finished"
    assert not any(e.kind == "confirm_required" for e in ev)


def test_wrong_lens_is_refused_in_preflight(tmp_path):
    b = fake100()
    b.state = 0
    out, ev = run(b, make_sample(tmp_path))
    assert out["status"] == "preflight_failed" and "100x Oil" in out["reasons"][0]
    assert not b.calls


def test_centre_from_the_4x_plane_and_above_it_is_asked(tmp_path):
    s = make_sample(tmp_path)
    d = s.dir / "scan4x_20261001-120000"
    d.mkdir()
    (d / "scan.json").write_text(json.dumps({"tiles": [
        {"x_um": 8026.0, "y_um": 571.6, "z_focus_um": 3045.0}]}))
    c = F.default_centre(s, 8026.0, 571.6)
    assert c["centre_um"] == pytest.approx(2985.0) and c["grade"] == "computed"
    assert "provisional" in c["source"]
    b = fake100(2985.0)
    out, _ = run(b, s)
    assert out["result"]["centre_um"] == pytest.approx(2985.0)
    assert out["result"]["grades"]["centre_um"] == "computed"
    with pytest.raises(GuardError, match="above the 4x focus"):
        run(fake100(), s, answers=[("oil_applied", True), ("centre_above_4x", False)],
            centre_um=3050.0)


def test_double_peak_warns_check_immersion_oil(tmp_path):
    b = fake100(2950.0, layers=((2996.0, 8000.0),))  # a false second focus, as with low oil
    out, _ = run(b, make_sample(tmp_path), centre_um=2970.0, half_um=40.0, metric="vollath")
    assert OIL_WARNING in out["result"]["warnings"]


def test_dark_and_saturated_warnings(tmp_path):
    s = make_sample(tmp_path)
    out, _ = run(fake100(), s, centre_um=2980.0, exposure_ms=0.01)
    assert F.DARK_SIGNAL in out["result"]["warnings"]
    out, _ = run(fake100(amp=400000.0), s, centre_um=2980.0)
    assert F.REDUCE_EXPOSURE in out["result"]["warnings"]


def test_plan_shows_the_guard_ceiling():
    p = F.plan({"centre_um": 3180.0}, F.default_centre(None, None, None))
    assert p["ceiling_um"] == 3200.0 and "ascending" in p["coarse"]
    with pytest.raises(ValueError):
        F.parse({"metric": "dino"})


def test_default_exposure_is_the_2026_09_30_20_ms():
    assert F.parse({}).exposure_ms == 20.0 == F.DEFAULT_EXPOSURE_MS
