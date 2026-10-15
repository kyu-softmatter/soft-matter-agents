"""`edge_trace`: follow the chamber edge with XY moves only and fit the hole (operations-spec 8).

Port of `scripts/edge_track.py` (`EdgeTracker` and its image functions) and the `t` tracking
of `scripts/live_focus.py`, both deleted in R-05 (in git history); this is the engine version.

What it does, in order:

1. preflight: XY readable, a camera pixel size, the objective (4x recommended; another lens
   is a warning, calibration is stored per lens), the arguments in range.
2. a sample with a hole fit or boundary asks `replace_hole_fit`; yes backs up `map.json` and
   `sample.json` as `*_before_rescan_<stamp>.json` and clears the boundary only (visits stay).
3. `start_trace` asks the operator: XY moves only, within `max_radius_um` of here.
4. inside the record scope: brightfield on (unless `light="keep"`), then calibration: +x and
   back, +y and back by `cal_um`, image shift by phase correlation -> M (px per um), checked
   against the camera pixel (0.7-1.4) and the reference calibration's handedness and angle.
   `calibrate=False` uses the reference instead (the sample's own for this lens, else the
   2026-09-30 4x bench M).
5. tracking: find the edge nearest the field centre, map it to the stage with
   `stage + inv(M) @ (centre - p)`, step along it (at most 200 um, no faster than
   `speed_um_s`), steer by the fitted chamber circle once it is trustworthy. Every
   `point_every_um` of travel an edge point goes to the sample boundary.
6. stops on: more than `max_radius_um` from the start, path or time limit, the edge lost,
   a full loop, abort, an error. Z never moves.
7. the hole is fitted to all boundary points (`robust_circle`) and written to sample.json with
   `fitted_at`, `trace_stop`, `closed_loop` (True only when the trace came round to where it
   first saw the edge), `boundary_limits_um` and `stage_camera_calibration`. A diameter more than
   20 % off `hole_diameter_mm` is a warning in the result.
8. every exit path switches the lights off (DiaLamp too, unlike live_focus: 9/30 problem 4).

Image vectors are (x, y) = (column, row) in full-resolution pixels; stage vectors are (x, y)
in um as the XY stage reports them (Ti2; piezo offsets are not added yet).

The image functions (`find_edge`, the circle fits, `hole_fit`) are the flat file
`microscope_agent/src/map_edge.py`, and `calibration_of` is `map_geometry.py` (the
soft-matter-agents layout, docs/integration-sma.md section 9; numpy only); they are
re-exported here.

Seams for the pieces that are not on main yet, each one argument of `run_edge_trace`:
- `grab`: the acquisition stream (T-011 / T-015 `start_stream` / `next_frame`). The default
  uses `next_frame` while the backend streams, else `snap`.
- `move_rel`: an XY relative move through the guards. The default is `XYAxis.goto_rel`
  (T-002-4: box, long-move rule and readback apply).
- `on_point`: boundary points. The default appends to `map.json` through `engine.sample`;
  T-027's `boundary_mark` replaces it.
- `confirm`, `check`, `sleep`, `clock`: the runner's `ctx.confirm`, abort check, abortable
  sleep and time.

`UPDATABLE` names the one argument the runner's `update` command may change mid-run
(`speed_um_s`, the `+` / `-` keys). `WATCHED` marks it operator-watched (D14).
"""

from __future__ import annotations

import math
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import numpy as np

from ..._flat import load
from ..backend import Backend, StreamActive
from ..events import Event, EventSink, null_sink
from ..guards import (
    GuardError,
    OperationAborted,
    OpScope,
    XYAxis,
    XYBox,
    operation,
    registry_key,
)
from ..records import stamp
from ..runner import Aborted, OpContext, Operation, register_operation
from ..sample import SAMPLES_ROOT, Sample
from .light_set import LightRequest, scope_for, switch
from .sample_map import SampleRecorder

load("map_edge", f"{__package__}._map_edge")
load("map_geometry", f"{__package__}._map_geometry")
from ._map_edge import (  # noqa: E402, F401 - re-exported
    arc_degrees,
    block_mean,
    find_edge,
    fixed_radius_centre,
    gaussian,
    hole_fit,
    kasa_circle,
    otsu,
    phase_shift,
    remove_small_regions,
    robust_circle,
)
from ._map_geometry import calibration_of  # noqa: E402, F401 - re-exported

NAME = "edge_trace"
WATCHED = True  # D14: abort when every local viewer is gone
UPDATABLE = frozenset({"speed_um_s"})
RECOMMENDED_OBJECTIVE = "4x"

MAX_SPEED_UM_S, MIN_SPEED_UM_S = 1000.0, 10.0
MAX_STEP_UM, MIN_STEP_UM = 200.0, 20.0
MIN_BLOB_UM = 500.0  # regions smaller than (500 um)^2 are debris or bubbles
CAL_MIN_PEAK = 8.0  # phase-correlation peak sharpness below this: too little structure
CAL_SCALE_RANGE = (0.7, 1.4)  # measured um/px over the camera pixel
CAL_MAX_ANGLE_DIFF_DEG = 10.0  # against the reference calibration
DIAMETER_WARN_FRACTION = 0.2
FULL_LOOP = "back where the edge was first seen: full loop"

# docs/runs/2026-09-30_substrate-scan.yaml calibration_4x: the image is mirrored vs the stage
REFERENCE_CAL_4X = {
    "objective": "4x", "um_per_px": 1.62524, "angle_deg": 0.117,
    "M_px_per_um": [[0.61602, 0.00236], [0.00126, -0.61456]],
    "source": "2026-09-30 bench, docs/runs/2026-09-30_substrate-scan.yaml",
}


# ---------------------------------------------------------------- arguments
@dataclass
class EdgeTraceArgs:
    hole_diameter_mm: float | None = None
    speed_um_s: float = 100.0
    exposure_ms: float | None = None
    light: str = "brightfield"  # "brightfield" | "keep" (the light already set stays)
    calibrate: bool = True
    cal_um: float = 200.0
    point_every_um: float = 250.0
    max_radius_um: float = 7000.0
    max_path_um: float = 25000.0
    max_time_s: float = 360.0
    min_radius_um: float = 1000.0

    @classmethod
    def from_dict(cls, d: dict) -> EdgeTraceArgs:
        known = {f.name for f in fields(cls)}
        extra = sorted(set(d) - known)
        if extra:
            raise ValueError(f"unknown edge_trace arguments: {extra}")
        a = cls(**d)
        if a.light not in ("brightfield", "keep"):
            raise ValueError(f"light {a.light!r} is not 'brightfield' or 'keep'")
        for name in ("speed_um_s", "cal_um", "point_every_um", "max_radius_um", "max_path_um",
                     "max_time_s", "min_radius_um"):
            v = getattr(a, name)
            if not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise ValueError(f"{name} must be a positive number, got {v!r}")
        if a.cal_um > MAX_STEP_UM:
            raise ValueError(f"cal_um {a.cal_um} exceeds the {MAX_STEP_UM:g} um step limit")
        for name in ("hole_diameter_mm", "exposure_ms"):
            v = getattr(a, name)
            if v is not None and (not isinstance(v, (int, float)) or not math.isfinite(v)
                                  or v <= 0):
                raise ValueError(f"{name} must be a positive number or null, got {v!r}")
        return a


def pace(speed_um_s: float) -> tuple[float, float]:
    """(speed, step): speed clamped to 10-1000 um/s, step = 0.5 s of it, 20-200 um."""
    speed = float(min(max(speed_um_s, MIN_SPEED_UM_S), MAX_SPEED_UM_S))
    return speed, float(min(max(speed * 0.5, MIN_STEP_UM), MAX_STEP_UM))


# ---------------------------------------------------------------- the routine
class EdgeTracer:
    """The tracking loop, with the hardware behind plain callables.

    `grab(not_before)` returns an image taken after the wall time `not_before`; `move_rel(d)`
    moves the stage by d um (guarded) and returns the position read back; `xy()` reads the
    stage. `log(dict)` gets the script's event dicts (`event` = track_start, cal, cal_result,
    move, edge_point, track_speed, track_stop). `check()` raises on abort; `sleep` and
    `clock` are the runner's abortable sleep and a monotonic clock."""

    def __init__(self, *, grab: Callable[[float], np.ndarray],
                 move_rel: Callable[[np.ndarray], Any], xy: Callable[[], np.ndarray],
                 pixel_um: float, exposure_ms: float,
                 args: EdgeTraceArgs, log: Callable[[dict], None],
                 on_point: Callable[[float, float], None] | None = None,
                 reference: dict | None = None, check: Callable[[], None] = lambda: None,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic,
                 wall: Callable[[], float] = time.time):
        self.grab, self.move_rel, self.xy = grab, move_rel, xy
        self.px, self.args = float(pixel_um), args
        self.settle_s = 2 * exposure_ms / 1000 + 0.08
        self.log, self.on_point, self.reference = log, on_point, reference
        self.check, self.sleep, self.clock, self.wall = check, sleep, clock, wall
        self.expect_r = None if not args.hole_diameter_mm else args.hole_diameter_mm * 500.0
        self.speed, self.step = pace(args.speed_um_s)
        self.M: np.ndarray | None = None
        self.calibration: dict | None = None
        self.circle_info: dict | None = None
        self.status, self.why = "starting", None
        self.path_um, self.n_moves, self.points = 0.0, 0, []
        self._ready_at, self._ready_wall = 0.0, 0.0

    def set_speed(self, speed_um_s: float) -> None:
        """Change pace while running; the step grows with it (0.5 s per step) up to 200 um."""
        self.speed, self.step = pace(speed_um_s)
        self.log({"event": "track_speed", "speed_um_s": self.speed, "step_um": self.step})

    # -- plumbing
    def _stop(self, why: str) -> str:
        self.why, self.status = why, f"stopped: {why}"
        self.log({"event": "track_stop", "why": why})
        return why

    def _frame(self) -> np.ndarray:
        wait = self._ready_at - self.clock()
        if wait > 0:
            self.sleep(wait)
        self.check()
        return self.grab(self._ready_wall)

    def _wait(self, s: float) -> None:
        self._ready_at = max(self._ready_at, self.clock() + s)
        self._ready_wall = max(self._ready_wall, self.wall() + s)

    def _move(self, d_um: np.ndarray, why: str) -> None:
        self.check()
        d_um = np.asarray(d_um, float)
        n = float(np.linalg.norm(d_um))
        limit = self.args.cal_um if why == "calibration" else self.step
        if n > limit + 1e-6:
            d_um = d_um * (limit / n)
        at = self.move_rel(d_um)
        self.n_moves += 1
        self._ready_at = self.clock() + self.settle_s
        self._ready_wall = self.wall() + self.settle_s
        self.log({"event": "move", "why": why, "d_um": [round(float(v), 2) for v in d_um],
                  "at_um": [round(float(v), 2) for v in at]})

    def _circle(self, hist: list[np.ndarray]) -> tuple[np.ndarray, float] | None:
        """The chamber circle to steer by, or None while it isn't trustworthy yet.

        With a known diameter the radius is held at it until the arc reaches 60 degrees. The
        circle is used only if the points sit on it (rms < 60 um) and its radius is plausible:
        a wrong circle would reject the true edge, which is worse than having none."""
        if len(hist) < 6:
            return None
        hb = np.array(hist[-300:])
        if np.ptp(hb, axis=0).max() < 800:
            return None
        c, r, keep = robust_circle(hb)
        hb = hb[keep]
        r_exp = self.expect_r
        if r_exp is not None and (arc_degrees(hb, c) < 60 or abs(r - r_exp) > 0.2 * r_exp):
            mean = hb.mean(axis=0)
            toward = (c - mean) / max(np.linalg.norm(c - mean), 1e-9)  # curvature side
            c = fixed_radius_centre(hb, r_exp, mean + r_exp * toward)
            r = r_exp
        rms = float(np.sqrt(np.mean((np.hypot(*(hb - c).T) - r) ** 2)))
        plausible = (r >= self.args.min_radius_um
                     and (r_exp is None or abs(r - r_exp) < 0.3 * r_exp))
        self.circle_info = {"centre": c.tolist(), "r": r, "rms": rms, "n": len(hb)}
        return (c, r) if rms < 60 and plausible else None

    # -- calibration
    def _check_against_reference(self, cal: dict) -> str | None:
        ref = self.reference
        if not ref:
            return None
        Mr = np.asarray(ref["M_px_per_um"], float)
        if np.sign(np.linalg.det(Mr)) != np.sign(np.linalg.det(np.asarray(cal["M_px_per_um"]))):
            return "calibration is mirrored the other way from the reference"
        diff = (cal["angle_deg"] - float(ref.get("angle_deg", calibration_of(Mr)["angle_deg"]))
                + 180) % 360 - 180
        if abs(diff) > CAL_MAX_ANGLE_DIFF_DEG:
            return (f"calibration angle {cal['angle_deg']:.1f} deg is {diff:+.1f} deg off the "
                    f"reference")
        return None

    def _calibrate(self, frame: np.ndarray) -> tuple[np.ndarray | None, np.ndarray]:
        if not self.args.calibrate:
            if not self.reference:
                self._stop("calibrate=false needs a reference calibration for this objective")
                return None, frame
            M = np.asarray(self.reference["M_px_per_um"], float)
            cal = calibration_of(M)
            self.log({"event": "cal_result", **cal, "source": self.reference.get("source")})
        else:
            self.status, b, cols = "calibrating", 4, []
            for axis in (0, 1):
                ref = block_mean(frame, b)
                d = np.zeros(2)
                d[axis] = self.args.cal_um
                self._move(d, "calibration")
                frame = self._frame()
                shift, sharp = phase_shift(ref, block_mean(frame, b))
                cols.append(shift * b / self.args.cal_um)
                self.log({"event": "cal", "axis": "xy"[axis], "shift_px": (shift * b).tolist(),
                          "peak": sharp})
                self._move(-d, "calibration")
                frame = self._frame()
                if sharp < CAL_MIN_PEAK:
                    self._stop("calibration: image has too little structure to measure a shift")
                    return None, frame
            M = np.column_stack(cols)
            if abs(np.linalg.det(M)) < 1e-12:
                self._stop("calibration: the image did not move with the stage")
                return None, frame
            cal = calibration_of(M)
            self.log({"event": "cal_result", **cal, "source": "measured"})
        lo, hi = CAL_SCALE_RANGE
        if not lo < cal["um_per_px"] / self.px < hi:
            self._stop(f"calibration gives {cal['um_per_px']:.3f} um/px against "
                       f"{self.px:.3f} expected")
            return None, frame
        bad = self._check_against_reference(cal) if self.args.calibrate else None
        if bad:
            self._stop(bad)
            return None, frame
        self.M, self.calibration = M, {**cal, "source": "measured" if self.args.calibrate
                                       else self.reference.get("source")}
        return M, frame

    # -- the routine itself
    def run(self) -> str:
        """Calibrate, then follow the edge until a stop condition. Returns why it stopped."""
        frame = self._frame()
        start = np.asarray(self.xy(), float)
        self.log({"event": "track_start", "start_um": start.tolist(), "pixel_um": self.px})
        M, frame = self._calibrate(frame)
        if M is None:
            return self.why
        Minv = np.linalg.inv(M)
        self.status = "tracking"
        a = self.args
        t0, since_point, lost = self.clock(), a.point_every_um, 0
        prev_t = prev_n = last_dir = loop_start = None
        last_move, sense = -math.inf, 0.0
        hist: list[np.ndarray] = []
        min_blob_px = MIN_BLOB_UM / self.px
        while True:
            here = np.asarray(self.xy(), float)
            centre = np.array([(frame.shape[1] - 1) / 2, (frame.shape[0] - 1) / 2])
            circ = self._circle(hist)
            e = find_edge(frame, prefer_n=prev_n, min_blob_px=min_blob_px)
            edge_stage = None if e is None else here + Minv @ (centre - e["p"])
            if (e is not None and circ is not None
                    and abs(np.linalg.norm(edge_stage - circ[0]) - circ[1]) > 200):
                e, edge_stage = None, None  # a boundary, but not on the chamber's circle
            if np.linalg.norm(here - start) > a.max_radius_um:
                return self._stop(f"more than {a.max_radius_um / 1000:g} mm from the start")
            if self.path_um > a.max_path_um or self.clock() - t0 > a.max_time_s:
                return self._stop("travel or time limit")
            if e is None:
                lost += 1
                limit = max(10, int(2000 / self.step)) if circ is not None else 3
                if lost > limit:
                    return self._stop(f"edge not found in {limit} frames"
                                      + (" (coasted along the fitted circle)" if circ else ""))
                self.status = (f"coasting on fitted circle ({lost}/{limit})" if circ
                               else f"edge lost ({lost}/{limit})")
                if circ is None:  # nothing to steer by yet: wait for a better frame
                    self._wait(0.15)
                    frame = self._frame()
                    continue
            else:
                lost = 0
                prev_n = e["n"]
                hist.append(edge_stage)
                if since_point >= a.point_every_um:
                    since_point = 0.0
                    pt = [float(edge_stage[0]), float(edge_stage[1])]
                    self.points.append(pt)
                    if self.on_point:
                        self.on_point(*pt)
                    self.log({"event": "edge_point", "um": pt, "contrast": e["contrast"]})
                if loop_start is None:
                    loop_start = edge_stage
                elif (self.path_um > 3000
                      and np.linalg.norm(edge_stage - loop_start) < 3 * self.step):
                    return self._stop(FULL_LOOP)
            wait = self.step / self.speed - (self.clock() - last_move)
            if wait > 0:
                self._wait(wait)
                frame = self._frame()
                continue
            if circ is not None:
                c0, r0 = circ
                rvec = (edge_stage if e is not None else here) - c0
                rhat = rvec / max(np.linalg.norm(rvec), 1e-9)
                tan = np.array([-rhat[1], rhat[0]])  # counter-clockwise
                if sense == 0.0:
                    sense = 1.0 if last_dir is None or tan @ last_dir >= 0 else -1.0
                if e is not None:
                    # along the circle, plus the image's centring (radial part only)
                    corr = Minv @ (0.5 * (centre - e["p"]))
                    d = sense * tan * self.step + (corr @ rhat) * rhat
                else:  # coast: field centre onto the circle, one step further round
                    ang = sense * self.step / r0
                    rot = np.array([[math.cos(ang), -math.sin(ang)],
                                    [math.sin(ang), math.cos(ang)]])
                    d = c0 + r0 * (rot @ rhat) - here
            else:
                n = e["n"]
                t = np.array([-n[1], n[0]])
                if prev_t is not None and t @ prev_t < 0:
                    t = -t  # keep going the same way round
                if last_dir is not None and (Minv @ -t) @ last_dir < 0:
                    t = -t  # ...and never reverse the stage's direction of travel
                prev_t = t
                # image content moves opposite to the view; 0.5 x pulls the edge to the centre
                d = Minv @ (0.5 * (centre - e["p"]) - t * (self.step / self.px))
            if e is not None:
                self.status = (f"tracking {self.speed:.0f} um/s  path {self.path_um / 1000:.2f}"
                               f" mm  contrast {e['contrast']:.0f}"
                               + (f"  circle d {2 * circ[1] / 1000:.2f} mm" if circ else ""))
            self._move(d, "track" if e is not None else "coast")
            last_move = self.clock()
            moved = min(float(np.linalg.norm(d)), self.step)
            last_dir = d / max(np.linalg.norm(d), 1e-9)
            self.path_um += moved
            since_point += moved
            frame = self._frame()


# ---------------------------------------------------------------- the operation
def reference_calibration(info_cal: dict | None, objective: str) -> dict | None:
    """The sample's calibration for this lens, else the 2026-09-30 bench M for the 4x."""
    if info_cal and info_cal.get("objective") == objective and info_cal.get("M_px_per_um"):
        return {**info_cal, "source": info_cal.get("source") or "sample calibration"}
    if objective == RECOMMENDED_OBJECTIVE:
        return dict(REFERENCE_CAL_4X)
    return None


def plan(args: dict, start_um: tuple[float, float] | None = None) -> dict:
    a = EdgeTraceArgs.from_dict(args)
    speed, step = pace(a.speed_um_s)
    return {
        "op": NAME, "start_um": None if start_um is None else list(start_um),
        "max_radius_um": a.max_radius_um, "max_path_um": a.max_path_um,
        "max_time_s": a.max_time_s, "speed_um_s": speed, "step_um": step,
        "calibration": ([f"+x {a.cal_um:g} um and back", f"+y {a.cal_um:g} um and back"]
                        if a.calibrate else ["reference calibration, no moves"]),
        "text": (f"Trace the edge: XY moves only, steps up to {step:g} um at {speed:g} um/s, "
                 f"within {a.max_radius_um / 1000:g} mm of the start. Z does not move."),
    }


def preflight(backend: Backend, args: dict) -> list[dict]:
    """Checks as `{name, ok, want, read, why}`; a warning is ok with a `warning` text."""
    checks: list[dict] = []
    try:
        EdgeTraceArgs.from_dict(args)
        checks.append({"name": "args", "ok": True, "want": "valid", "read": "valid", "why": ""})
    except (TypeError, ValueError) as exc:
        checks.append({"name": "args", "ok": False, "want": "valid", "read": str(exc),
                       "why": str(exc)})
    p = backend.positions()
    xy_ok = p.x_um is not None and p.y_um is not None
    checks.append({"name": "xy_readable", "ok": xy_ok, "want": "x and y read",
                   "read": [p.x_um, p.y_um], "why": "" if xy_ok else f"unreadable: {p.errors}"})
    info = backend.info()
    px_ok = bool(info.pixel_um and info.pixel_um > 0)
    checks.append({"name": "pixel_um", "ok": px_ok, "want": "> 0", "read": info.pixel_um,
                   "why": "" if px_ok else "no camera pixel size for the calibration check"})
    try:
        key = registry_key(backend.nosepiece())
    except Exception as exc:  # noqa: BLE001 - unreadable lens is a warning; calibration says
        key = f"unreadable: {exc}"
    c = {"name": "objective", "ok": True, "want": RECOMMENDED_OBJECTIVE, "read": key, "why": ""}
    if key != RECOMMENDED_OBJECTIVE:
        c["warning"] = (f"edge_trace is meant for the {RECOMMENDED_OBJECTIVE}; calibration is "
                        f"stored for {key!r}")
    checks.append(c)
    return checks


def _backup(sample: Sample, when: str) -> list[str]:
    """Copy map.json and sample.json aside before a re-trace replaces the fit."""
    saved = []
    for src, name in ((sample.map_json, f"map_before_rescan_{when}.json"),
                      (sample.sample_json, f"sample_before_rescan_{when}.json")):
        if src.exists():
            shutil.copy2(src, sample.dir / name)
            saved.append(name)
    return saved


class LegacyWriter:
    """Boundary and hole fit straight into map.json / sample.json: the T-002 lifecycle and an
    engine with no records store (no sample seat)."""

    def __init__(self, sample: Sample):
        self.sample = sample

    def has_fit(self) -> tuple[bool, str | None]:
        hole = self.sample.load_info().hole
        return bool(self.sample.load_map().boundary or hole), (hole or {}).get("fitted_at")

    def clear(self) -> None:
        m = self.sample.load_map()
        m.boundary = []
        self.sample.save_map(m)

    def point(self, x: float, y: float) -> None:
        m = self.sample.load_map()
        m.boundary.append([round(x, 1), round(y, 1)])
        self.sample.save_map(m)

    def boundary(self) -> list[list[float]]:
        return [list(p) for p in self.sample.load_map().boundary]

    def hole(self, fit: dict, limits: dict) -> None:
        info = self.sample.load_info()
        info.hole, info.boundary_limits_um = fit, limits
        self.sample.save_info(info)

    def calibration(self, cal: dict) -> None:
        info = self.sample.load_info()
        info.stage_camera_calibration = cal
        self.sample.save_info(info)


class EventWriter(LegacyWriter):
    """Boundary and hole fit as sample events through the open session (T-027 fold kinds
    `boundary_clear`, `boundary_point`, `hole_fit`); map.json / sample.json are regenerated from
    the view (`write_derived_views`) and `map_changed` goes out. The calibration has no event
    kind: it stays a sample.json key, which the derived views keep."""

    def __init__(self, sample: Sample, recorder: Any):
        super().__init__(sample)
        self.rec = recorder

    def has_fit(self) -> tuple[bool, str | None]:
        view = self.rec.view()
        return bool(view.boundary or view.hole), (view.hole or {}).get("fitted_at")

    def clear(self) -> None:
        self.rec.event("boundary_clear")
        self.rec.changed("boundary", n_points=0)

    def point(self, x: float, y: float) -> None:
        self.rec.event("boundary_point", x_um=round(x, 1), y_um=round(y, 1))
        self.rec.changed("boundary", n_points=len(self.rec.view().boundary))

    def boundary(self) -> list[list[float]]:
        return [[float(p["x_um"]), float(p["y_um"])] for p in self.rec.view().boundary]

    def hole(self, fit: dict, limits: dict) -> None:
        self.rec.event("hole_fit", **fit)
        self.rec.changed("hole", fitted_at=fit.get("fitted_at"))


def _default_grab(backend: Backend) -> Callable[[float], np.ndarray]:
    """A frame taken after `not_before` (wall time): the stream while it runs, else snap."""

    def grab(not_before: float) -> np.ndarray:
        streaming = getattr(backend, "streaming", None)
        if callable(streaming) and streaming():
            for _ in range(50):
                f = backend.next_frame(timeout_s=2.0)
                if f is not None and f.t_read >= not_before:
                    return f.image
            raise GuardError("no fresh frame from the acquisition stream")
        return backend.snap().image

    return grab


def prepare(sample: Sample, a: EdgeTraceArgs, confirm: Callable[[str, str], bool],
            writer: LegacyWriter | None = None) -> list[str]:
    """The two confirmations before anything moves; returns the backups made.

    A sample with a hole fit or boundary asks `replace_hole_fit` (yes: back up and clear the
    boundary only), then `start_trace`. A no raises OperationAborted."""
    writer = writer or LegacyWriter(sample)
    backups: list[str] = []
    has, fitted = writer.has_fit()
    if has:
        when = fitted or "an earlier trace"
        if not confirm("replace_hole_fit", f"replace the hole fit from {when}? (backed up)"):
            raise OperationAborted("the operator kept the previous hole fit")
        backups = _backup(sample, stamp())
        writer.clear()
    if not confirm("start_trace", f"trace the edge: XY moves only, within "
                                  f"{a.max_radius_um / 1000:g} mm of here"):
        raise OperationAborted("the operator did not start the trace")
    return backups


def _is_abort(exc: BaseException) -> bool:
    """OperationAborted (T-002 lifecycle), the runner's Aborted, or Ctrl+C."""
    return isinstance(exc, (OperationAborted, KeyboardInterrupt)) or type(exc).__name__ == "Aborted"


def trace(backend: Backend, sample: Sample, a: EdgeTraceArgs, scope: OpScope, *,
          warnings: list[str], check: Callable[[], None] = lambda: None,
          sleep: Callable[[float], None] = time.sleep,
          clock: Callable[[], float] = time.monotonic, wall: Callable[[], float] = time.time,
          grab: Callable[[float], np.ndarray] | None = None,
          move_rel: Callable[[np.ndarray], Any] | None = None,
          on_point: Callable[[float, float], None] | None = None,
          on_tracer: Callable[[EdgeTracer], None] | None = None,
          writer: LegacyWriter | None = None) -> dict:
    """The trace itself, inside a scope the caller owns (the record and the exit-path lights
    are the caller's: `operation()` or the runner). Returns the result dict. `writer` stores
    the boundary and the fit (default LegacyWriter: the sample's files)."""
    writer = writer or LegacyWriter(sample)
    def log(d: dict) -> None:
        ev = dict(d)
        name = ev.pop("event")
        scope.emit(Event("progress", scope.op_id, {"op": NAME, "status": name, "data": ev}))

    for w in warnings:
        scope.emit(Event("log", scope.op_id, {"level": "warning", "text": w}))
    if a.light == "brightfield":
        switch(backend, scope, LightRequest("brightfield"))
    if a.exposure_ms is not None:
        backend.set_exposure(a.exposure_ms)
    binfo = backend.info()
    try:
        objective = registry_key(backend.nosepiece())
    except GuardError:
        objective = "unknown"
    start = _xy(backend)
    axis = XYAxis(backend, XYBox.around(start, a.max_radius_um), allow_motion=True,
                  sink=scope.emit, op_id=scope.op_id)
    tracer = EdgeTracer(
        grab=grab or _default_grab(backend),
        move_rel=move_rel or (lambda d: axis.goto_rel(float(d[0]), float(d[1]))),
        xy=lambda: np.array(_xy(backend)), pixel_um=binfo.pixel_um,
        exposure_ms=binfo.exposure_ms, args=a, log=log,
        on_point=on_point or writer.point,
        reference=reference_calibration(sample.load_info().stage_camera_calibration, objective),
        check=check, sleep=sleep, clock=clock, wall=wall)
    if on_tracer:
        on_tracer(tracer)
    result: dict[str, Any] = {"warnings": warnings, "objective": objective,
                              "start_um": list(start)}
    scope.result = result
    try:
        result["why"] = tracer.run()
    except BaseException as exc:
        tracer.log({"event": "track_stop",
                    "why": "aborted" if _is_abort(exc) else f"error: {exc}"})
        raise
    finally:
        result.update(_finish(writer, tracer, objective, a, warnings))
    return result


def run_edge_trace(backend: Backend, sample: Sample, args: dict, sink: EventSink = null_sink, *,
                   confirm: Callable[[str, str], bool],
                   user_id: str | None = None, session_id: str | None = None,
                   **seams: Any) -> dict:
    """Run edge_trace on the T-002 lifecycle (record in `<sample>/edge_trace_<stamp>/`).

    `confirm(key, text)` answers `replace_hole_fit` and `start_trace`; a no raises
    OperationAborted before anything moves. `seams` are `trace`'s keyword arguments
    (check, sleep, clock, wall, grab, move_rel, on_point, on_tracer). Preflight failures
    raise GuardError before any record."""
    checks = preflight(backend, args)
    failed = [c for c in checks if not c["ok"]]
    if failed:
        raise GuardError("preflight failed: " + "; ".join(f"{c['name']}: {c['why']}"
                                                          for c in failed))
    a = EdgeTraceArgs.from_dict(args)
    backups = prepare(sample, a, confirm)
    with operation(backend, sample.dir, NAME, sink, args=dict(args), user_id=user_id,
                   session_id=session_id) as scope:
        result = trace(backend, sample, a, scope,
                       warnings=[c["warning"] for c in checks if c.get("warning")], **seams)
        result["backups"] = backups
    return result


def _xy(backend: Backend) -> tuple[float, float]:
    p = backend.positions()
    if p.x_um is None or p.y_um is None:
        raise GuardError(f"XY unreadable: {p.errors}")
    return p.x_um, p.y_um


def _finish(writer: LegacyWriter, tracer: EdgeTracer, objective: str, a: EdgeTraceArgs,
            warnings: list[str]) -> dict:
    """Store the calibration and the hole fit (over every boundary point); also on abort and
    error, where `trace_stop` and `closed_loop` say the arc is partial."""
    out: dict[str, Any] = {"path_um": round(tracer.path_um, 1), "n_moves": tracer.n_moves,
                           "n_points": len(tracer.points), "calibration": None, "hole": None}
    if tracer.calibration is not None:
        cal = {**tracer.calibration, "objective": objective,
               "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        writer.calibration(cal)
        out["calibration"] = cal
    pts = np.asarray(writer.boundary(), float)
    hole = hole_fit(pts) if len(pts) else None
    if hole is not None:
        hole["fitted_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        hole["trace_stop"] = tracer.why or "aborted or failed"  # a partial arc says so
        hole["closed_loop"] = tracer.why == FULL_LOOP  # stable flag for sample.hole_loop()
        writer.hole(hole, {"x": [float(pts[:, 0].min()), float(pts[:, 0].max())],
                           "y": [float(pts[:, 1].min()), float(pts[:, 1].max())]})
        out["hole"] = hole
        if a.hole_diameter_mm:
            off = abs(hole["diameter_mm"] - a.hole_diameter_mm) / a.hole_diameter_mm
            if off > DIAMETER_WARN_FRACTION:
                warnings.append(f"fitted diameter {hole['diameter_mm']:.3f} mm is "
                                f"{100 * off:.0f} % off the expected {a.hole_diameter_mm:g} mm")
    out["warnings"] = warnings
    return out


def _runner_grab(ctx: OpContext) -> Callable[[float], np.ndarray]:
    """Frames under the runner: the engine's stream when it runs (its newest published frame
    taken after `not_before`), else a snap."""

    # `live()` (engine/stream.py): frames are coming now; a stream without it streams while
    # it runs
    live = getattr(ctx.stream, "live", ctx.stream.running)

    def grab(not_before: float) -> np.ndarray:
        for _ in range(400):
            if live():
                latest = ctx.runner.latest_frame()
                if latest is not None and latest[1].get("t_read", 0.0) >= not_before:
                    return latest[0]
            else:
                try:
                    return ctx.backend.snap().image
                except StreamActive:  # the stream is stopping or starting: look again
                    pass
            ctx.sleep(0.025)
        raise GuardError("no fresh frame from the acquisition stream or a snap in 10 s")

    return grab


@register_operation
class EdgeTraceOp(Operation):
    """`start("edge_trace", {...})` on the open sample (or `sample_id` in the args).

    Operator-watched (D14); `update{speed_um_s}` changes the pace mid-run. A declined
    confirmation ends it aborted before anything moves. Sample folders live under the
    runner's installed `sample_seat.samples_root` (T-027), else `samples_root`."""

    name = NAME
    watched = WATCHED
    updatable = UPDATABLE
    samples_root = SAMPLES_ROOT

    def __init__(self, ctx: OpContext):
        super().__init__(ctx)
        self._tracer: EdgeTracer | None = None
        self._checks: list[dict] = []

    def _trace_args(self) -> dict:
        return {k: v for k, v in self.args.items() if k != "sample_id"}

    def _root(self) -> Path:
        seat = getattr(self.ctx.runner, "sample_seat", None)
        return Path(getattr(seat, "samples_root", None) or self.samples_root)

    def _sample_id(self) -> str | None:
        return self.args.get("sample_id") or self.ctx.runner.snapshot()["sample"]["sample_id"]

    def plan(self) -> dict:
        try:
            return plan(self._trace_args())
        except (TypeError, ValueError) as exc:  # preflight reports it as a failed check
            return {"op": NAME, "text": f"invalid arguments: {exc}"}

    def _writer(self, sample: Sample) -> LegacyWriter:
        """Sample events when the server installed the records store; the legacy files when
        the engine runs without one (development, tests)."""
        if getattr(self.ctx.runner, "sample_seat", None) is None:
            return LegacyWriter(sample)
        return EventWriter(sample, SampleRecorder.of(self.ctx, sample.id))

    def preflight(self) -> list[dict]:
        sid = self._sample_id()
        folder = None if not sid else self._root() / sid
        ok = folder is not None and folder.is_dir()
        self._checks = [{"name": "sample", "ok": ok, "want": "an open sample folder",
                         "read": None if folder is None else str(folder),
                         "why": "" if ok else "open a sample first (sample_open)"}]
        if getattr(self.ctx.runner, "sample_seat", None) is not None:
            why = SampleRecorder.why_not(self.ctx, sid)
            self._checks.append({"name": "sample_record", "ok": why is None,
                                 "want": "the open session of this sample", "read": sid,
                                 "why": why or ""})
        self._checks += preflight(self.ctx.backend, self._trace_args())
        return self._checks

    def run(self) -> dict:
        ctx = self.ctx
        sample = Sample(self._sample_id(), self._root())
        a = EdgeTraceArgs.from_dict(self._trace_args())
        writer = self._writer(sample)
        try:
            backups = prepare(sample, a, lambda key, text: bool(ctx.confirm(key, text)["ok"]),
                              writer)
        except OperationAborted as exc:
            raise Aborted(str(exc)) from None
        result = trace(ctx.backend, sample, a, scope_for(ctx),
                       warnings=[c["warning"] for c in self._checks if c.get("warning")],
                       check=ctx.check, sleep=ctx.sleep, grab=_runner_grab(ctx),
                       on_tracer=self._set_tracer, writer=writer)
        result["backups"] = backups
        return result

    def _set_tracer(self, tracer: EdgeTracer) -> None:
        self._tracer = tracer

    def update(self, args: dict) -> None:
        super().update(args)
        if self._tracer is not None and "speed_um_s" in args:
            self._tracer.set_speed(float(args["speed_um_s"]))
