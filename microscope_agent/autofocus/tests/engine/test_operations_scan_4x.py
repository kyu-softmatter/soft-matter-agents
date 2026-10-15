"""scan_4x on FakeBackend with focus-dependent frames (T-031). MockBackend (T-021) replaces the
fake here when it lands."""

import json
import queue

import numpy as np
import pytest
from engine_fakes import FakeBackend
from scipy import ndimage

from dino_autofocus.engine.events import Command
from dino_autofocus.engine.guards import GuardError, OperationAborted
from dino_autofocus.engine.mosaic import load_mosaic, mosaic_from_scan
from dino_autofocus.engine.operations import scan_4x as S
from dino_autofocus.engine.sample import Sample, SampleInfo

FITTED = "2026-10-01T10:00:00"
SESSION = "2026-10-01T09:00:00"


class FocusFake(FakeBackend):
    """Frames of fixed spots blurred by |z - focus(x, y)|; brightness follows the exposure.

    `dropout_z`: a frame snapped there is 23 % dimmer and sharp, like the 2026-09-30 Aura
    dropout that read 2.7x sharper than its neighbours."""

    def __init__(self, focus=lambda x, y: 2993.0, amp=8000.0, dof_um=5.0, layers=(),
                 dropout_z=None, **kw):
        kw.setdefault("shape", (96, 96))
        kw.setdefault("z_um", 2950.0)
        super().__init__(**kw)
        self.focus, self.amp, self.dof, self.layers = focus, amp, dof_um, layers
        self.dropout_z, self.snaps = dropout_z, 0
        rng = np.random.default_rng(7)
        self.spots = np.zeros(self.shape)
        ys, xs = rng.integers(6, self.shape[0] - 6, (2, 40))
        self.spots[ys, xs] = 1.0

    def info(self):
        info = super().info()
        info.bit_depth = 12
        return info

    def _render(self, z_focus, amp, sharp=False):
        sigma = 0.8 if sharp else 0.8 + abs(self.z - z_focus) / self.dof
        # the blur keeps the photons (the frame mean does not change with z), the peak falls
        return ndimage.gaussian_filter(self.spots, sigma) * amp * self.exposure / 30.0

    def _frame(self):
        self.snaps += 1
        f = self.focus(self.x, self.y)
        drop = self.dropout_z is not None and abs(self.z - self.dropout_z) < 0.5
        img = 100 + self._render(f, self.amp, sharp=drop)
        for z_l, amp_l in self.layers:
            img = img + self._render(z_l, amp_l)
        if drop:
            img = 100 + (img - 100) * 0.77 - 0.23 * 100
        f0 = super()._frame()
        f0.image = np.clip(img, 0, 4095).astype(np.uint16)
        return f0


FULL_LOOP = "back where the edge was first seen: full loop"  # edge_trace's stop reason


def make_sample(root, diameter_mm=0.2, fitted_at=FITTED, cal=None,
                trace_stop=FULL_LOOP, arc_deg=360.0):
    s = Sample.create(root)
    s.save_info(SampleInfo(s.id, hole={"centre_um": [8000.0, 600.0], "diameter_mm": diameter_mm,
                                       "fitted_at": fitted_at, "trace_stop": trace_stop,
                                       "arc_deg": arc_deg},
                           stage_camera_calibration=cal))
    return s


def run(backend, sample, answers=(), **args):
    q = queue.Queue()
    for key, ok in answers:
        q.put(Command("confirm", args={"key": key, "ok": ok}))
    events = []
    out = S.run_scan_4x(backend, sample, {"exposure_ms": 30.0, "margin_um": 10.0, **args},
                        events.append, answers=q, session_started=SESSION,
                        confirm_timeout_s=1.0, sleep=lambda s: None)
    return out, events


def test_grid_serpentine_and_the_2026_09_30_vector():
    tiles, pitch, n = S.grid((0.0, 0.0), 6.1438 * 500 + 500, 2400 * 1.6252, 0.15)
    assert n == 2 and pitch == pytest.approx(3315.4, abs=0.1)  # operations-spec 3, 2) plan
    assert [(r, c) for _, _, r, c in tiles] == [(0, 0), (0, 1), (1, 1), (1, 0)]
    _, _, n3 = S.grid((0.0, 0.0), 300.0, 156.0, 0.15)
    assert n3 == 5


def test_plan_needs_a_hole_and_reports_boxes(tmp_path):
    s = make_sample(tmp_path)
    p = S.plan(s.load_info(), (96, 96), {"margin_um": 10.0}, z_now_um=3012.0)
    assert p["grid_n"] == 2 and p["z_guess_um"] == 3012.0
    assert p["scan_box_um"] == [7890.0, 8110.0, 490.0, 710.0]
    assert p["allowed_box_um"] == [6890.0, 9110.0, -510.0, 1710.0]
    assert p["calibration"] == "2026-09-30 4x calibration"
    low = S.plan(s.load_info(), (96, 96), {"margin_um": 10.0}, z_now_um=62.9)
    assert low["z_guess_um"] == 2960.0
    with pytest.raises(ValueError, match="hole not fitted"):
        S.plan(SampleInfo("x"), (96, 96), {})
    with pytest.raises(ValueError, match="unknown"):
        S.parse({"marg": 1})


def test_preflight_refuses_wrong_lens_and_no_hole(tmp_path):
    b = FocusFake()
    b.state = 5
    s = make_sample(tmp_path)
    assert any("not '1-Plan Apo" in r for r in S.preflight(b, s))
    out, ev = run(b, s)
    assert out["status"] == "preflight_failed" and out["record"] is None
    assert ev[-1].kind == "preflight_failed" and not b.calls  # nothing moved or switched
    assert S.preflight(FocusFake(), Sample("nope", tmp_path)) == [
        f"no sample.json in {tmp_path / 'nope'}"]


@pytest.mark.parametrize("stop, arc, ok", [
    (FULL_LOOP, 120.0, True),  # the tracer said full loop
    ("operator abort", 140.0, False),  # partial arc: refuse
    ("aborted or failed", None, False),
    (None, 355.0, True),  # 2026-09-30 live_focus fits carry only arc_deg
    (None, 200.0, False),
])
def test_hole_fit_must_be_a_closed_loop(tmp_path, stop, arc, ok):
    s = make_sample(tmp_path, trace_stop=stop, arc_deg=arc)
    reasons = S.preflight(FocusFake(), s)
    assert (reasons == []) is ok
    if not ok:
        assert "partial arc" in reasons[0] and "re-trace a full loop" in reasons[0]


def test_dry_run_plans_only(tmp_path):
    b, s = FocusFake(), make_sample(tmp_path)
    out, ev = run(b, s, dry_run=True)
    assert out["dry_run"] and out["record"] is None and not s.scans_4x()
    assert [e.kind for e in ev] == ["planned", "finished"] and not b.calls


def test_scan_focuses_every_tile_and_writes_the_record(tmp_path):
    b = FocusFake(focus=lambda x, y: 2990.0 + 0.1 * (x - 8000.0))
    s = make_sample(tmp_path)
    out, ev = run(b, s)
    assert out["status"] == "finished"
    d = s.scans_4x()[-1]
    assert d.name.startswith("scan4x_")
    rec = json.loads((d / "scan.json").read_text())
    assert [t["name"] for t in rec["tiles"]] == ["tile_r0c0", "tile_r0c1", "tile_r1c1",
                                                 "tile_r1c0"]
    for t in rec["tiles"]:
        assert t["z_focus_um"] == pytest.approx(b.focus(t["x_um"], t["y_um"]), abs=2.5)
        assert t["grades"]["z_focus_um"] == "measured" and len(t["block_z_um"]) == 36
        assert (d / f"{t['name']}.npy").exists()
    assert rec["light_off"]["verified"] and rec["status"] == "finished"
    assert b.lights == {"DiaLamp": "0", "Aura": "0"}
    summary = json.loads((d / "summary.json").read_text())
    assert summary["status"] == "finished"
    res = summary["result"]
    assert res["scan_box_um"] == [7890.0, 8110.0, 490.0, 710.0]
    assert res["focus_plane"]["slope_x_um_per_mm"] == pytest.approx(100.0, abs=20.0)
    mosaic, meta = load_mosaic(d)  # the engine.mosaic format the map screen reads (T-032)
    assert meta.orientation == "stage" and meta.n_tiles == 4 and meta.objective == "4x"
    assert meta.M_px_per_um == [list(r) for r in S.DEFAULT_M_PX_PER_UM]
    assert meta.calibration_source == "2026-09-30 4x calibration"
    assert mosaic.shape == tuple(meta.shape) and {t["name"] for t in meta.tiles} == {
        t["name"] for t in rec["tiles"]}
    kinds = {e.kind for e in ev}
    assert {"planned", "started", "motion", "progress", "frame_ready", "reading",
            "light_changed", "finished"} <= kinds
    sweeps = [e.data for e in ev if e.kind == "motion" and e.data.get("axis") == "z"]
    assert all(m["sent"] for m in sweeps)


def test_light_dropout_frame_does_not_pick_the_focus(tmp_path):
    b = FocusFake(focus=lambda x, y: 2993.0, dropout_z=2996.0)
    s = make_sample(tmp_path, diameter_mm=0.1)  # one tile
    run(b, s)
    t = json.loads((s.scans_4x()[-1] / "scan.json").read_text())["tiles"][0]
    assert t["dropout_z_um"] == [2996.0]
    assert "without light-dropout" in t["focus_note"]
    assert t["grades"]["z_focus_um"] == "computed"
    assert t["z_focus_um"] == pytest.approx(2993.0, abs=1.5)


def test_mosaic_matches_engine_mosaic_from_the_scan_folder(tmp_path):
    b, s = FocusFake(), make_sample(tmp_path)
    run(b, s)
    d = s.scans_4x()[-1]
    mosaic, meta = load_mosaic(d)
    again, meta2 = mosaic_from_scan(d, meta.M_px_per_um, save=False)  # T-032's own builder
    assert np.array_equal(mosaic, again)
    assert {k: v for k, v in meta.to_dict().items() if k != "calibration_source"} == {
        k: v for k, v in meta2.to_dict().items() if k != "calibration_source"}


def test_stale_hole_fit_is_asked_and_can_be_declined(tmp_path):
    b, s = FocusFake(), make_sample(tmp_path, fitted_at="2026-09-30T18:49:00")
    with pytest.raises(GuardError, match="declined"):
        run(b, s, answers=[("hole_fit_stale", False)])
    d = s.scans_4x()[-1] if s.scans_4x() else next(s.dir.glob("scan4x_*"))
    summary = json.loads((d / "summary.json").read_text())
    assert summary["status"] == "error" and summary["lights_off"]["verified"]
    assert not any(c[0] == "move_z" for c in b.calls)


def test_z_below_the_window_asks_then_approaches(tmp_path):
    b, s = FocusFake(z_um=62.9), make_sample(tmp_path, diameter_mm=0.1)
    out, ev = run(b, s, answers=[("z_enter_window", True)])
    assert out["status"] == "finished"
    zs = [c[1] for c in b.calls if c[0] == "move_z"]
    assert zs[0] == 2800.0  # one move to the window bottom, then steps (approach)
    assert all(b2 - a2 <= 10.0 + 1e-9 for a2, b2 in zip(zs[1:4], zs[2:5], strict=False))
    confirms = [e for e in ev if e.kind == "confirm_required"]
    assert confirms[0].data["key"] == "z_enter_window"


def test_abort_while_asking_switches_off(tmp_path):
    b, s = FocusFake(z_um=62.9), make_sample(tmp_path)
    q = queue.Queue()
    q.put(Command("abort"))
    with pytest.raises(OperationAborted):
        S.run_scan_4x(b, s, {"exposure_ms": 30.0, "margin_um": 10.0}, answers=q,
                      session_started=SESSION, sleep=lambda s: None)
    summary = json.loads((next(s.dir.glob("scan4x_*")) / "summary.json").read_text())
    assert summary["status"] == "aborted" and summary["lights_off"]["verified"]


def test_auto_exposure_aims_at_half_the_ceiling(tmp_path):
    b, s = FocusFake(amp=2000.0), make_sample(tmp_path, diameter_mm=0.1)
    out, ev = run(b, s, exposure_ms=None)
    auto = next(e.data for e in ev if e.kind == "reading" and "auto_exposure_ms" in e.data)
    assert auto["auto_exposure_ms"] > 30.0  # a dim field: longer exposure
    assert 0.5 * 4095 / 1.4 < auto["p999_adu"] < 0.5 * 4095 / 0.7  # stopped within 0.7-1.4
    assert out["result"]["exposure_ms"] == auto["auto_exposure_ms"]


def test_stream_is_paused_and_restored(tmp_path):
    b, s = FocusFake(), make_sample(tmp_path, diameter_mm=0.1)
    b.start_stream()
    out, _ = run(b, s)
    assert out["status"] == "finished" and b.streaming()
    assert ("stop_stream",) in b.calls


def test_focus_plane_4x_from_the_last_scan(tmp_path):
    s = make_sample(tmp_path)
    d = s.dir / "scan4x_20261001-120000"
    d.mkdir()
    tiles = [{"x_um": x, "y_um": y, "z_focus_um": 3000.0 + 0.002 * x - 0.004 * y}
             for x, y in ((0, 0), (1000, 0), (0, 1000), (1000, 1000))]
    tiles.append({"x_um": 500, "y_um": 500, "z_focus_um": None})
    (d / "scan.json").write_text(json.dumps({"tiles": tiles}))
    p = S.focus_plane_4x(s, 500.0, 250.0)
    assert p["z_um"] == pytest.approx(3000.0 + 1.0 - 1.0)
    assert p["plane"]["kind"] == "plane" and p["grade"] == "computed"
    assert S.focus_plane_4x(Sample("none", tmp_path), 0, 0) is None
    flat = S.fit_plane([(0.0, 0.0, 3001.0), (10.0, 0.0, 3003.0)])
    assert flat["kind"].startswith("flat") and S.plane_z(flat, 99.0, 99.0) == 3002.0
