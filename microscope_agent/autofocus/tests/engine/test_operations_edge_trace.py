"""edge_trace (operations-spec 8): the ported image functions, then whole traces on a simulated
stage with a 6 mm hole (after scripts/sim_edge_track.py) behind FakeBackend.

Time is simulated in the direct runs: the tracer's sleep advances a fake clock. The runner
tests at the end run in real time on short paths."""

from __future__ import annotations

import json
import time

import numpy as np
import pytest
from engine_fakes import FakeBackend

from dino_autofocus.engine.backend import Frame, Positions
from dino_autofocus.engine.guards import GuardError, OperationAborted
from dino_autofocus.engine.operations import edge_trace as et
from dino_autofocus.engine.sample import Sample, SampleMap

PX_UM, N = 16.0, 240  # 3.84 mm field, like the 4x on the full sensor at a coarser pixel
HOLE_C, HOLE_R = np.array([1200.0, -800.0]), 3000.0
# stage -> image content: mirrored in y like the bench, so calibration finds M = -M_TRUE
M_TRUE = np.array([[-1.0, 0.0], [0.0, 1.0]]) / PX_UM
M_CAL = -M_TRUE


def _texture(seed: int = 1, step_um: float = 20.0, half_um: float = 10000.0):
    rng = np.random.default_rng(seed)
    n = int(2 * half_um / step_um)
    f = np.fft.rfft2(rng.normal(size=(n, n)))
    ky = np.fft.fftfreq(n)[:, None]
    kx = np.fft.rfftfreq(n)[None, :]
    tex = np.fft.irfft2(f * np.exp(-((kx**2 + ky**2) / (2 * 0.03**2))), s=(n, n))
    return 40 * tex / tex.std(), step_um, half_um


TEX = _texture()


class HoleWorld(FakeBackend):
    """FakeBackend whose camera sees a bright 6 mm hole and texture fixed to the stage."""

    def __init__(self, xy, structure: bool = True, **kw):
        super().__init__(x_um=float(xy[0]), y_um=float(xy[1]), shape=(N, N), **kw)
        self.structure = structure
        self.rng = np.random.default_rng(0)
        self.snaps = 0

    def info(self):
        i = super().info()
        i.pixel_um = PX_UM
        return i

    def snap(self) -> Frame:
        self.snaps += 1
        if not self.structure:
            return super().snap()
        yy, xx = np.mgrid[0:N, 0:N].astype(float)
        dpx = np.stack([xx - (N - 1) / 2, yy - (N - 1) / 2], axis=-1)
        s = np.array([self.x, self.y]) + dpx @ np.linalg.inv(M_TRUE).T
        rel = s - HOLE_C
        inside = np.hypot(rel[..., 0], rel[..., 1]) < HOLE_R
        tex, step, half = TEX
        iy = np.clip(((s[..., 1] + half) / step).astype(int), 0, tex.shape[0] - 1)
        ix = np.clip(((s[..., 0] + half) / step).astype(int), 0, tex.shape[1] - 1)
        img = 200 + 300 * inside + tex[iy, ix] + self.rng.normal(0, 8, (N, N))
        return Frame(img.clip(0, 65535).astype(np.uint16), 0.0, self.exposure, self.x, self.y,
                     self.z)


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += max(s, 0.0)


START = HOLE_C + HOLE_R * np.array([np.cos(0.7), np.sin(0.7)]) + 400  # the edge in view


def _run(world, sample, args=None, *, confirm=lambda k, t: True, **kw):
    clock = Clock()
    events = []
    kw.setdefault("sleep", clock.sleep)
    out = et.run_edge_trace(world, sample, {"speed_um_s": 1000.0, **(args or {})},
                            events.append, confirm=confirm, clock=clock, wall=clock, **kw)
    return out, events


@pytest.fixture
def sample(tmp_path) -> Sample:
    s = Sample("20261001_1200_1", tmp_path)
    s.dir.mkdir()
    return s


# ---------------------------------------------------------------- pure functions
def test_kasa_and_robust_circle() -> None:
    a = np.linspace(0, 1.5 * np.pi, 40)
    pts = HOLE_C + HOLE_R * np.column_stack([np.cos(a), np.sin(a)])
    c, r = et.kasa_circle(pts)
    assert np.allclose(c, HOLE_C, atol=1e-6) and r == pytest.approx(HOLE_R)
    noisy = np.vstack([pts, HOLE_C + [[0, 0], [500, 500], [-800, 100]]])  # debris inside
    c, r, keep = et.robust_circle(noisy)
    assert np.allclose(c, HOLE_C, atol=1.0) and keep.sum() == 40
    assert et.arc_degrees(pts, HOLE_C) == pytest.approx(270, abs=0.1)
    c2 = et.fixed_radius_centre(pts[:10], HOLE_R, HOLE_C + 300)
    assert np.allclose(c2, HOLE_C, atol=1.0)


def test_hole_fit_needs_six_points() -> None:
    a = np.linspace(0, 2 * np.pi, 30, endpoint=False)
    pts = HOLE_C + HOLE_R * np.column_stack([np.cos(a), np.sin(a)])
    h = et.hole_fit(pts)
    assert h["diameter_mm"] == pytest.approx(6.0) and h["n_points"] == 30
    assert et.hole_fit(pts[:5]) is None


def test_phase_shift_recovers_a_shift() -> None:
    tex = et.gaussian(np.random.default_rng(3).normal(size=(128, 128)), 1.5)
    moved = np.roll(tex, (3, -5), axis=(0, 1))
    shift, sharp = et.phase_shift(tex, moved)
    assert np.allclose(shift, [-5, 3], atol=0.2) and sharp > et.CAL_MIN_PEAK


def test_find_edge_on_a_half_plane() -> None:
    img = np.full((150, 150), 200.0)
    img[:, 90:] = 500.0  # bright on the right; boundary at column 90
    img += np.random.default_rng(0).normal(0, 4, img.shape)
    e = et.find_edge(img)
    assert e is not None and abs(e["p"][0] - 90) < 2
    assert e["n"][0] > 0.9  # normal points dark -> bright
    assert et.find_edge(np.full((150, 150), 300.0)) is None


def test_small_regions_are_flipped() -> None:
    mask = np.zeros((40, 40), bool)
    mask[:, 20:] = True
    mask[5:8, 5:8] = True  # a 9-block speck on the dark side
    out = et.remove_small_regions(mask, 20)
    assert not out[5:8, 5:8].any() and out[:, 20:].all()


def test_pace_and_args() -> None:
    assert et.pace(400) == (400.0, 200.0)
    assert et.pace(5) == (10.0, 20.0)
    assert et.pace(1e9) == (1000.0, 200.0)
    with pytest.raises(ValueError, match="unknown"):
        et.EdgeTraceArgs.from_dict({"step_um": 50})
    with pytest.raises(ValueError, match="cal_um"):
        et.EdgeTraceArgs.from_dict({"cal_um": 500})
    with pytest.raises(ValueError, match="light"):
        et.EdgeTraceArgs.from_dict({"light": "aura"})
    assert "Z does not move" in et.plan({"speed_um_s": 400}, (1.0, 2.0))["text"]


def test_reference_calibration_is_the_bench_m() -> None:
    cal = et.calibration_of(np.array(et.REFERENCE_CAL_4X["M_px_per_um"]))
    assert cal["um_per_px"] == pytest.approx(1.6252, abs=1e-3)
    assert et.reference_calibration(None, "4x")["source"].startswith("2026-09-30")
    assert et.reference_calibration(None, "100x-Oil") is None
    own = {"objective": "4x", "M_px_per_um": M_CAL.tolist(), "angle_deg": 0.0}
    assert et.reference_calibration(own, "4x")["M_px_per_um"] == M_CAL.tolist()


# ---------------------------------------------------------------- preflight
def test_preflight_warns_off_4x_and_fails_on_unreadable_xy(monkeypatch) -> None:
    w = HoleWorld(START)
    w.state = 5
    checks = {c["name"]: c for c in et.preflight(w, {})}
    assert checks["objective"]["ok"] and "100x-Oil" in checks["objective"]["warning"]
    monkeypatch.setattr(w, "positions", lambda: Positions(None, None, 2900.0,
                                                          errors={"xy": "timeout"}))
    checks = {c["name"]: c for c in et.preflight(w, {})}
    assert not checks["xy_readable"]["ok"]


def test_preflight_failure_moves_nothing(sample, monkeypatch) -> None:
    w = HoleWorld(START)
    with pytest.raises(GuardError, match="args"):
        _run(w, sample, {"max_radius_um": -1})
    assert not [c for c in w.calls if c[0] in ("move_xy", "move_z", "light")]


# ---------------------------------------------------------------- whole traces
def test_full_trace_closes_the_loop_and_fits_the_hole(sample) -> None:
    w = HoleWorld(START)
    out, events = _run(w, sample, {"hole_diameter_mm": 6.0})
    assert out["why"] == et.FULL_LOOP
    hole = out["hole"]
    assert np.hypot(*(np.array(hole["centre_um"]) - HOLE_C)) < 60
    assert hole["diameter_mm"] == pytest.approx(6.0, rel=0.015)
    assert hole["arc_deg"] > 300 and hole["fitted_at"]
    assert hole["closed_loop"] is True and hole["trace_stop"] == et.FULL_LOOP
    assert out["calibration"]["um_per_px"] == pytest.approx(PX_UM, rel=0.03)
    assert np.allclose(out["calibration"]["M_px_per_um"], M_CAL, atol=0.004)

    info = json.loads(sample.sample_json.read_text(encoding="utf-8"))
    assert info["hole"]["fitted_at"] == hole["fitted_at"]
    assert info["stage_camera_calibration"]["objective"] == "4x"
    assert set(info["boundary_limits_um"]) == {"x", "y"}
    boundary = json.loads(sample.map_json.read_text(encoding="utf-8"))["boundary"]
    assert len(boundary) == out["n_points"] >= 30

    assert not [c for c in w.calls if c[0] == "move_z"]  # Z never moves
    assert ("light", "DiaLamp", "1") in w.calls  # brightfield during the trace
    assert w.lights == {"DiaLamp": "0", "Aura": "0"}  # and off on the way out
    steps = [c for c in w.calls if c[0] == "move_xy"]
    assert len(steps) == out["n_moves"]
    xy = np.array([c[1:] for c in steps])
    assert np.abs(np.diff(xy, axis=0)).max() <= 200.0 + 1e-6

    (folder,) = [p for p in sample.dir.iterdir() if p.name.startswith("edge_trace_")]
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "finished" and summary["lights_off"]["verified"]
    sub = [e.data["status"] for e in events if e.kind == "progress"]
    assert sub[0] == "track_start" and "cal_result" in sub and sub[-1] == "track_stop"
    assert "edge_point" in sub and "move" in sub
    assert [e for e in events if e.kind == "motion"]  # moves went through XYAxis


def test_keep_leaves_the_light_alone_until_the_exit_path(sample) -> None:
    w = HoleWorld(START)
    _run(w, sample, {"light": "keep", "max_path_um": 1000})
    assert not [c for c in w.calls if c[0] == "light" and c[2] == "1"]
    assert w.lights == {"DiaLamp": "0", "Aura": "0"}


def test_reference_calibration_skips_the_calibration_moves(sample) -> None:
    sample.save_info(sample.load_info())
    info = sample.load_info()
    info.stage_camera_calibration = {"objective": "4x", "M_px_per_um": M_CAL.tolist(),
                                     "angle_deg": 0.0, "source": "earlier trace"}
    sample.save_info(info)
    w = HoleWorld(START)
    out, events = _run(w, sample, {"calibrate": False, "max_path_um": 2000})
    moves = [e.data["data"]["why"] for e in events
             if e.kind == "progress" and e.data["status"] == "move"]
    assert moves and "calibration" not in moves
    assert out["calibration"]["source"] == "earlier trace"
    assert out["why"] == "travel or time limit"
    assert out["hole"]["closed_loop"] is False  # a partial arc is never a closed loop


def test_flat_image_stops_at_calibration_with_lights_off(sample) -> None:
    w = HoleWorld(START, structure=False)
    out, _ = _run(w, sample)
    assert "too little structure" in out["why"]
    assert out["hole"] is None and out["calibration"] is None
    assert w.lights == {"DiaLamp": "0", "Aura": "0"}


def test_radius_limit_stops_the_trace(sample) -> None:
    w = HoleWorld(START)
    out, _ = _run(w, sample, {"max_radius_um": 600})
    assert "from the start" in out["why"]
    x0, y0 = START
    assert np.hypot(w.x - x0, w.y - y0) < 600 + 200 + 1


def test_abort_mid_trace_ends_aborted_with_lights_off(sample) -> None:
    w = HoleWorld(START)
    n = {"checks": 0}

    def check() -> None:
        n["checks"] += 1
        if n["checks"] > 30:
            raise OperationAborted("operator pressed Stop")

    with pytest.raises(OperationAborted):
        _run(w, sample, check=check)
    (folder,) = [p for p in sample.dir.iterdir() if p.name.startswith("edge_trace_")]
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "aborted" and summary["lights_off"]["verified"]
    assert w.lights == {"DiaLamp": "0", "Aura": "0"}
    log = [json.loads(line) for line in (folder / "log.jsonl").read_text("utf-8").splitlines()]
    assert any(e["kind"] == "progress" and e["data"]["status"] == "track_stop"
               and e["data"]["data"]["why"] == "aborted" for e in log)


def test_speed_update_reaches_the_tracer(sample) -> None:
    w = HoleWorld(START)
    seen = []

    def on_tracer(tr) -> None:
        tr.set_speed(5000)  # the `+` key, clamped
        seen.append((tr.speed, tr.step))

    _run(w, sample, {"max_path_um": 1000}, on_tracer=on_tracer)
    assert seen == [(1000.0, 200.0)]
    assert {"speed_um_s"} == et.UPDATABLE and et.WATCHED


# ---------------------------------------------------------------- an earlier hole fit
def _with_previous_fit(sample: Sample) -> None:
    info = sample.load_info()
    info.hole = {"centre_um": [9361.1, 1272.2], "diameter_mm": 5.9919,
                 "fitted_at": "2026-09-30T18:49:00"}
    sample.save_info(info)
    sample.save_map(SampleMap(visits=[{"x": 1, "y": 2}], boundary=[[1.0, 2.0], [3.0, 4.0]]))


def test_keeping_the_previous_fit_moves_nothing(sample) -> None:
    _with_previous_fit(sample)
    w = HoleWorld(START)
    asked = []

    def confirm(key, text):
        asked.append((key, text))
        return False

    with pytest.raises(OperationAborted, match="kept the previous"):
        _run(w, sample, confirm=confirm)
    assert asked[0][0] == "replace_hole_fit" and "2026-09-30T18:49:00" in asked[0][1]
    assert not [c for c in w.calls if c[0] in ("move_xy", "light")]
    assert sample.load_map().boundary == [[1.0, 2.0], [3.0, 4.0]]
    assert not list(sample.dir.glob("*_before_rescan_*"))


def test_replacing_backs_up_and_clears_only_the_boundary(sample) -> None:
    _with_previous_fit(sample)
    w = HoleWorld(START)
    keys = []
    out, _ = _run(w, sample, {"max_path_um": 1500},
                  confirm=lambda k, t: keys.append(k) or True)
    assert keys == ["replace_hole_fit", "start_trace"]
    assert len(out["backups"]) == 2
    backup = json.loads((sample.dir / out["backups"][0]).read_text(encoding="utf-8"))
    assert backup["boundary"] == [[1.0, 2.0], [3.0, 4.0]]
    m = sample.load_map()
    assert [1.0, 2.0] not in m.boundary and m.visits == [{"x": 1, "y": 2}]


def test_declining_the_start_moves_nothing(sample) -> None:
    w = HoleWorld(START)
    with pytest.raises(OperationAborted, match="did not start"):
        _run(w, sample, confirm=lambda k, t: k != "start_trace")
    assert not [c for c in w.calls if c[0] in ("move_xy", "light")]


# ---------------------------------------------------------------- under the T-011 runner
class _Live:
    """A started T-011 runner over a HoleWorld, with the samples root in tmp_path."""

    def __init__(self, world, root, monkeypatch) -> None:
        from dino_autofocus.engine.runner import AllowAll, Runner, RunnerConfig, folder_records

        monkeypatch.setattr(et.EdgeTraceOp, "samples_root", root)
        self.r = Runner(world, control=AllowAll(), config=RunnerConfig(position_interval_s=None),
                        records=folder_records(lambda meta: root / "records"))
        self.events = []
        self.r.subscribe(self.events.append)
        self.r.start()
        self.r.set_experiment_session(SID, 1000.0)

    def cmd(self, kind, op_id="", op="", **args):
        from dino_autofocus.engine.events import Command

        return self.r.submit(Command(kind, op=op, op_id=op_id, args=args, user_id="u1",
                                     session_id=SID))

    def wait(self, pred, timeout=20.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            hit = next((e for e in list(self.events) if pred(e)), None)
            if hit is not None:
                return hit
            time.sleep(0.02)
        raise AssertionError(f"timed out; kinds {[e.kind for e in self.events][-12:]}")

    def close(self) -> None:
        self.r.shutdown("test teardown", timeout=5)
        assert self.r.wait_idle(5)


SID = "20261001_1200_1"


@pytest.fixture
def live(tmp_path, monkeypatch):
    made = []

    def build(world):
        (tmp_path / SID).mkdir(exist_ok=True)
        lv = _Live(world, tmp_path, monkeypatch)
        made.append(lv)
        return lv

    yield build
    for lv in made:
        lv.close()


def test_runner_edge_trace_confirm_update_and_finish(live, tmp_path) -> None:
    w = HoleWorld(START)
    lv = live(w)
    op_id = lv.cmd("start", op="edge_trace", sample_id=SID, max_path_um=1000,
                   speed_um_s=400)
    ask = lv.wait(lambda e: e.kind == "confirm_required" and e.op_id == op_id)
    assert ask.data["key"] == "start_trace"
    lv.cmd("confirm", op_id, key="start_trace", ok=True)
    lv.wait(lambda e: e.kind == "progress" and e.op_id == op_id
            and e.data["status"] == "cal_result")
    lv.cmd("update", op_id, speed_um_s=1000)
    end = lv.wait(lambda e: e.op_id == op_id and e.kind in ("finished", "aborted", "error"))
    assert end.kind == "finished", end.data
    assert end.data["summary"]["why"] == "travel or time limit"
    speeds = [e.data["data"] for e in lv.events if e.op_id == op_id and e.kind == "progress"
              and e.data["status"] == "track_speed"]
    assert speeds and speeds[-1]["speed_um_s"] == 1000.0
    info = json.loads((tmp_path / SID / "sample.json").read_text(encoding="utf-8"))
    assert info["stage_camera_calibration"]["objective"] == "4x"
    assert ("light", "DiaLamp", "1") in w.calls and w.lights["DiaLamp"] == "0"
    assert not [c for c in w.calls if c[0] == "move_z"]


def test_runner_declined_start_is_aborted_without_moving(live) -> None:
    w = HoleWorld(START)
    lv = live(w)
    op_id = lv.cmd("start", op="edge_trace", sample_id=SID)
    lv.wait(lambda e: e.kind == "confirm_required" and e.op_id == op_id)
    lv.cmd("confirm", op_id, key="start_trace", ok=False)
    end = lv.wait(lambda e: e.op_id == op_id and e.kind in ("finished", "aborted", "error"))
    assert end.kind == "aborted"
    assert not [c for c in w.calls if c[0] in ("move_xy", "light") and c[-1] != "0"]


def test_runner_abort_mid_trace_switches_off(live) -> None:
    w = HoleWorld(START)
    lv = live(w)
    op_id = lv.cmd("start", op="edge_trace", sample_id=SID, speed_um_s=50)
    lv.wait(lambda e: e.kind == "confirm_required" and e.op_id == op_id)
    lv.cmd("confirm", op_id, key="start_trace", ok=True)
    lv.wait(lambda e: e.kind == "progress" and e.op_id == op_id and e.data["status"] == "move")
    lv.cmd("abort", op_id)
    end = lv.wait(lambda e: e.op_id == op_id and e.kind in ("finished", "aborted", "error"))
    assert end.kind == "aborted"
    assert w.lights == {"DiaLamp": "0", "Aura": "0"}
    assert any(e.kind == "progress" and e.op_id == op_id and e.data["status"] == "track_stop"
               and e.data["data"]["why"] == "aborted" for e in lv.events)


def test_runner_refuses_without_a_sample(live) -> None:
    lv = live(HoleWorld(START))
    op_id = lv.cmd("start", op="edge_trace")
    fail = lv.wait(lambda e: e.op_id == op_id and e.kind == "preflight_failed")
    assert any(c["name"] == "sample" and not c["ok"] for c in fail.data["checks"])


def test_runner_bad_args_fail_preflight(live) -> None:
    lv = live(HoleWorld(START))
    op_id = lv.cmd("start", op="edge_trace", sample_id=SID, cal_um=500)
    fail = lv.wait(lambda e: e.op_id == op_id and e.kind == "preflight_failed")
    assert any(c["name"] == "args" and not c["ok"] for c in fail.data["checks"])


def test_runner_uses_the_installed_sample_root_and_needs_its_session(live, tmp_path) -> None:
    from types import SimpleNamespace

    other = tmp_path / "seat_root"
    (other / SID).mkdir(parents=True)
    lv = live(HoleWorld(START))
    lv.r.sample_seat = SimpleNamespace(samples_root=other, store=None,
                                       session_for=lambda session_id: None)
    op_id = lv.cmd("start", op="edge_trace", sample_id=SID)
    fail = lv.wait(lambda e: e.op_id == op_id and e.kind in ("preflight_ok", "preflight_failed"))
    assert fail.kind == "preflight_failed"
    checks = {c["name"]: c for c in fail.data["checks"]}
    assert checks["sample"]["ok"] and checks["sample"]["read"] == str(other / SID)
    assert not checks["sample_record"]["ok"]
    assert "open experiment session" in checks["sample_record"]["why"]


def test_runner_with_a_records_store_writes_sample_events(live, tmp_path) -> None:
    """With the server's sample seat and an open session, the boundary and the fit are sample
    events (boundary_clear on replace, boundary_point, hole_fit); map.json and sample.json are
    regenerated from them."""
    from dino_autofocus.engine.operations.sample_ops import SampleSeat, install_sample_seat
    from dino_autofocus.engine.sample import read_sample
    from dino_autofocus.records import ExperimentSession, FolderStore, RecordsConfig

    store = FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                      data_root=tmp_path / "data"))
    session = ExperimentSession.open(store, "u1", SID)
    session.sample_event("boundary_point", x_um=1.0, y_um=2.0)  # an earlier trace
    lv = live(HoleWorld(START))
    lv.r.set_experiment_session(session.session_id, 1000.0)
    install_sample_seat(lv.r, SampleSeat(store, tmp_path, session_for=lambda s: session))

    def cmd(kind, op_id="", op="", **args):
        from dino_autofocus.engine.events import Command

        return lv.r.submit(Command(kind, op=op, op_id=op_id, args=args, user_id="u1",
                                   session_id=session.session_id))

    op_id = cmd("start", op="edge_trace", sample_id=SID, max_path_um=2500, speed_um_s=1000)
    for key in ("replace_hole_fit", "start_trace"):
        ask = lv.wait(lambda e, key=key: e.kind == "confirm_required" and e.op_id == op_id
                      and e.data["key"] == key)
        cmd("confirm", op_id, key=ask.data["key"], ok=True)
    end = lv.wait(lambda e: e.op_id == op_id and e.kind in ("finished", "aborted", "error"))
    assert end.kind == "finished", end.data
    view = read_sample(store, SID, tmp_path, session.session_id)
    pts = [[p["x_um"], p["y_um"]] for p in view.boundary]
    assert [1.0, 2.0] not in pts and len(pts) == end.data["summary"]["n_points"] >= 6
    assert view.hole["closed_loop"] is False and view.hole["fitted_at"]
    assert view.hole["trace_stop"] == "travel or time limit"
    kinds = [json.loads(line)["kind"] for line in
             session.layout.sample_events.read_text(encoding="utf-8").splitlines()]
    assert kinds[:2] == ["boundary_point", "boundary_clear"] and kinds[-1] == "hole_fit"
    derived = json.loads((tmp_path / SID / "map.json").read_text(encoding="utf-8"))
    assert derived["boundary"] == pts  # map.json regenerated from the events
    info = json.loads((tmp_path / SID / "sample.json").read_text(encoding="utf-8"))
    assert info["hole"]["fitted_at"] == view.hole["fitted_at"]
    assert info["stage_camera_calibration"]["objective"] == "4x"  # kept as a sample.json key
    assert any(e.kind == "map_changed" and e.data["what"] == "hole" for e in lv.events)
