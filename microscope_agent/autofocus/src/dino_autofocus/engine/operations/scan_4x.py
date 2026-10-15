"""`scan_4x`: tile the hole at 4x, autofocus each tile, keep the in-focus frames (ops-spec 3).

Port of `scripts/scan_4x.py` onto the engine. What guards it:

- Z: `FocusAxis` for the 4x (free WD 20 mm, so the 2800-3200 window binds). Sweeps ascend and
  every move is read back. Coming into the window from below (9/30: Z at 62.9 um) is asked
  first (`z_enter_window`) and done by `approach`, never a jump.
- XY: `XYAxis` inside the scan box + 1 mm, each move read back. Tile steps (~3.3 mm) stay at
  sample Z because the 4x row of the per-objective table allows them; longer moves need Z
  retracted (guards).
- Light: Aura line on through the scope's guarded helper (D15), only inside `operation()`,
  whose exit path switches everything off with readback.
- Nosepiece: read only; preflight refuses unless it is the 4x.

Tile order is serpentine (rows alternate direction), as on 2026-09-30 (`grid`, with
`fit_plane` / `plane_z`, is the flat file `microscope_agent/src/map_tiles.py`, the
soft-matter-agents layout, docs/integration-sma.md section 9). Per tile: coarse
sweep (first tile +-160 um @ 10, later +-50 @ 6; a failed later tile widens once to the
first-tile span), a fine sweep +-12 @ 2 around an interior coarse peak, the 2 % light-dropout
filter, a parabola per 6 x 6 block, then park at the focus and save the frame.

Record `<sample>/scan4x_<stamp>/` (prefix kept for `plot_scan.py` and the launcher):
engine `log.jsonl` + `summary.json`, the legacy `scan.json` (same fields as the script),
`tile_r<r>c<c>.npy`, and `mosaic.npy` + `mosaic.json` written by `engine.mosaic` (T-032), the
one format the map screen reads (stage orientation from `M_px_per_um`, overlaps averaged).

Grades: a tile's `z_focus_um` is the encoder readback of the best plane ("measured"), or a
parabola vertex when the dropout filter re-fits the fine pass ("computed"); block z and the
focus plane are "computed". No model value is used.

`focus_plane_4x(sample, x, y)` gives the 4x focus plane of the sample's last scan at an XY:
the default centre for `focus_100x`.
"""

from __future__ import annotations

import json
import math
import queue
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from ..._flat import load
from ...bench_values import (
    CALIBRATION_4X_SOURCE,
    DROPOUT_TOLERANCE,
)
from ...bench_values import M_PX_PER_UM_4X as DEFAULT_M_PX_PER_UM
from ...bench_values import SCAN_BLOCKS_PER_SIDE as BLOCKS
from ...bench_values import UM_PER_PX_4X as DEFAULT_UM_PER_PX
from ...focus.classical import (
    block_scores,
    dropout_mask,
    parabola_peak,
    vollath4,
)
from ..backend import Backend
from ..events import Event, EventSink, null_sink
from ..guards import (
    SAMPLE_Z_WINDOW_UM,
    XY_BOX_MARGIN_UM,
    FocusAxis,
    GuardError,
    OpScope,
    SweepResult,
    XYAxis,
    XYBox,
    best_z_um,
    lights_off,
    operation,
)
from ..mosaic import Tile, build_mosaic, save_mosaic
from ..records import GRADE_COMPUTED, GRADE_MEASURED
from ..runner import Aborted, Operation, register_operation
from ..sample import SAMPLES_ROOT, Sample, SampleInfo

load("map_tiles", f"{__package__}._map_tiles")
from ._map_tiles import (  # noqa: E402, F401 - re-exported
    camera_calibration,
    fit_plane,
    grid,
    half_side_um,
    plane_z,
    square_box_um,
    tile_list,
)

try:  # T-027 puts the closed-loop rule next to fitted_at
    from ..sample import hole_loop
except ImportError:  # until T-027 merges: the same rule and result shape
    FULL_LOOP_ARC_DEG, FULL_LOOP_STOP = 330.0, "full loop"

    def hole_loop(hole: dict | None) -> dict:
        if not hole:
            return {"closed": False, "why": "no hole fit", "fitted_at": None,
                    "trace_stop": None, "arc_deg": None}
        stop, arc = hole.get("trace_stop"), hole.get("arc_deg")
        try:
            arc_f = None if arc is None else float(arc)
        except (TypeError, ValueError):
            arc_f = None
        if stop is not None and FULL_LOOP_STOP in str(stop):
            closed, why = True, f"trace stopped on a full loop ({stop})"
        elif stop is not None:
            closed, why = False, f"partial trace: {stop}"
        elif arc_f is not None and arc_f >= FULL_LOOP_ARC_DEG:
            closed, why = True, f"arc {arc_f:.0f} deg >= {FULL_LOOP_ARC_DEG:.0f} deg"
        else:
            closed = False
            why = ("no arc recorded" if arc_f is None
                   else f"arc {arc_f:.0f} deg < {FULL_LOOP_ARC_DEG:.0f} deg")
        return {"closed": closed, "why": why, "fitted_at": hole.get("fitted_at"),
                "trace_stop": stop, "arc_deg": arc_f}

NAME = "scan_4x"
PREFIX = "scan4x"
OBJECTIVE_4X = "1-Plan Apo LmbdD20 4x"
OBJECTIVE_KEY = "4x"
DEFAULT_Z_GUESS_UM = 2960.0
COARSE_STEP_FIRST_UM, COARSE_STEP_UM = 10.0, 6.0
FINE_HALF_UM, FINE_STEP_UM = 12.0, 2.0
SETTLE_COARSE_S, SETTLE_FINE_S, XY_SETTLE_S = 0.1, 0.2, 0.2
# auto exposure (scan_4x.py): p99.9 at half the ceiling, factor clipped 0.25-4, done at 0.7-1.4
AUTO_TARGET, AUTO_ROUNDS, AUTO_START_MS, AUTO_MS = 0.5, 6, 30.0, (1.0, 2000.0)
PLAN_SENSOR = (2400, 2400)  # Kinetix22: the runner plans with no hardware behind it


@dataclass(frozen=True)
class ScanArgs:
    margin_um: float = 500.0
    overlap: float = 0.15
    exposure_ms: float | None = None  # None: auto exposure
    aura_line: str = "GREEN"
    aura_percent: float = 1.0
    z_guess_um: float | None = None  # None: current Z if in the window, else 2960
    first_half_um: float = 160.0
    tile_half_um: float = 50.0
    dry_run: bool = False


def parse(args: dict) -> ScanArgs:
    known = set(ScanArgs.__dataclass_fields__)
    extra = sorted(set(args) - known - {"sample_id"})
    if extra:
        raise ValueError(f"unknown scan_4x arguments: {extra}")
    a = ScanArgs(**{k: v for k, v in args.items() if k in known})
    for name in ("margin_um", "first_half_um", "tile_half_um", "aura_percent"):
        v = float(getattr(a, name))
        if not math.isfinite(v) or v < 0:
            raise ValueError(f"{name} {v} must be a finite number >= 0")
    if not 0 <= a.overlap < 1:
        raise ValueError(f"overlap {a.overlap} must be in [0, 1)")
    if a.exposure_ms is not None and not 0 < float(a.exposure_ms) <= AUTO_MS[1]:
        raise ValueError(f"exposure_ms {a.exposure_ms} must be in (0, {AUTO_MS[1]:g}]")
    return a


def calibration(info: SampleInfo) -> tuple[float, list[list[float]], str]:
    """(um_per_px, M_px_per_um, source) from the sample's stage_camera_calibration."""
    return camera_calibration(info.stage_camera_calibration,
                              default_um_per_px=DEFAULT_UM_PER_PX,
                              default_m_px_per_um=DEFAULT_M_PX_PER_UM,
                              default_source=CALIBRATION_4X_SOURCE)


def plan(info: SampleInfo, sensor: tuple[int, int], args: dict | ScanArgs,
         z_now_um: float | None = None) -> dict:
    """Everything the scan will do, computed without hardware (the `planned` event)."""
    a = args if isinstance(args, ScanArgs) else parse(args)
    hole = info.hole
    if not hole or hole.get("centre_um") is None or hole.get("diameter_mm") is None:
        raise ValueError("hole not fitted: run edge_trace")
    centre = (float(hole["centre_um"][0]), float(hole["centre_um"][1]))
    half = half_side_um(hole["diameter_mm"], a.margin_um)
    um_px, m, cal_src = calibration(info)
    fov = min(sensor) * um_px
    tiles, pitch, n = grid(centre, half, fov, a.overlap)
    box = XYBox.around(centre, half, XY_BOX_MARGIN_UM)
    z_guess = _z_guess(a, z_now_um)
    first = FocusAxis(None, OBJECTIVE_KEY).plan(z_guess, a.first_half_um, COARSE_STEP_FIRST_UM)
    return {
        "op": NAME, "centre_um": list(centre), "half_side_um": half, "um_per_px": um_px,
        "M_px_per_um": m, "calibration": cal_src, "fov_um": fov, "pitch_um": pitch,
        "grid_n": n, "tiles": tile_list(tiles),
        "scan_box_um": square_box_um(centre, half),
        "allowed_box_um": [box.x_min, box.x_max, box.y_min, box.y_max],
        "z_guess_um": z_guess, "first_sweep": first.describe(),
        "later_sweeps": (f"+-{a.tile_half_um:g} um @ {COARSE_STEP_UM:g}, fine +-{FINE_HALF_UM:g} "
                         f"@ {FINE_STEP_UM:g} around an interior coarse peak; a failed tile "
                         f"widens once to +-{a.first_half_um:g} @ {COARSE_STEP_FIRST_UM:g}"),
        "light": f"Aura {a.aura_line.upper()} {a.aura_percent:g} %",
        "exposure_ms": a.exposure_ms if a.exposure_ms is not None else "auto",
    }


def preflight(backend: Backend, sample: Sample) -> list[str]:
    """Reasons the scan cannot start (empty list: it can). Reads only."""
    problems = []
    if not sample.sample_json.exists():
        return [f"no sample.json in {sample.dir}"]
    info = sample.load_info()
    if not info.hole or info.hole.get("centre_um") is None:
        problems.append("hole not fitted: run edge_trace")
    elif not (loop := hole_loop(info.hole))["closed"]:
        problems.append(f"hole trace is a partial arc ({loop['why']}): re-trace a full loop")
    try:
        label = backend.nosepiece()
    except Exception as exc:  # noqa: BLE001 - unreadable is a reason, not a crash
        label = f"unreadable ({exc})"
    if label != OBJECTIVE_4X:
        problems.append(f"nosepiece reads {label!r}, not {OBJECTIVE_4X!r}")
    try:
        bits = backend.info().bit_depth
        if not 8 <= bits <= 16:
            problems.append(f"camera bit depth {bits} is not 8-16")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"camera info unreadable: {exc}")
    return problems


def _z_guess(a: ScanArgs, z_now: float | None) -> float:
    if a.z_guess_um is not None:
        return float(a.z_guess_um)
    lo, hi = SAMPLE_Z_WINDOW_UM
    return float(z_now) if z_now is not None and lo <= z_now <= hi else DEFAULT_Z_GUESS_UM


def _hole_fit_is_current(hole: dict, session_started: str | None) -> bool:
    fitted = hole.get("fitted_at")
    if not fitted:
        return False
    return session_started is None or str(fitted) >= str(session_started)  # ISO strings


def _save_mosaic(out: Path, tiles: list[dict], frames: dict[str, np.ndarray],
                 m: list[list[float]], calibration_source: str) -> None:
    """mosaic.npy + mosaic.json in the one format the map screen reads (engine.mosaic, T-032)."""
    mosaic, meta = build_mosaic([Tile(t["name"], t["x_um"], t["y_um"], frames[t["name"]])
                                 for t in tiles], m, objective=OBJECTIVE_KEY,
                                calibration_source=calibration_source)
    save_mosaic(out, mosaic, meta)


def focus_plane_4x(sample: Sample, x_um: float, y_um: float) -> dict | None:
    """The 4x focus plane of the sample's last scan, evaluated at (x, y). None without a scan
    or without a focused tile. Computed from measured tile z; not a model value."""
    scans = sample.scans_4x()
    if not scans:
        return None
    rec = json.loads((scans[-1] / "scan.json").read_text(encoding="utf-8"))
    pts = [(t["x_um"], t["y_um"], t["z_focus_um"]) for t in rec.get("tiles", [])
           if t.get("z_focus_um") is not None]
    plane = fit_plane(pts)
    if plane is None:
        return None
    return {"z_um": plane_z(plane, x_um, y_um), "at_um": [x_um, y_um], "plane": plane,
            "scan": scans[-1].name, "grade": GRADE_COMPUTED}


@dataclass
class Host:
    """What an operation body needs from whoever runs it: `run_*` below (guards.operation)
    or the engine runner (`OpContext`). `emit` takes Events with `op_id` set; `ask` returns
    the operator's yes/no; `light_on` is the guarded Aura helper (D15); `sleep` and `check`
    are where an abort lands."""

    op_id: str
    folder: Path
    emit: EventSink
    ask: Callable[[str, str, dict], bool]
    light_on: Callable[[str, float], list]
    sleep: Callable[[float], None]
    check: Callable[[], None] = lambda: None
    session_started: str | None = None  # ISO local time of the experiment session start

    @classmethod
    def of_scope(cls, scope: OpScope, *, timeout_s: float | None,
                 sleep: Callable[[float], None], session_started: str | None) -> Host:
        return cls(scope.op_id, Path(scope.record.dir), scope.emit,
                   lambda key, text, data: scope.ask(key, text, timeout_s, **data),
                   scope.aura_line_on, sleep, session_started=session_started)

    @classmethod
    def of_runner(cls, ctx: Any, folder: Path) -> Host:
        """`ctx` is the runner's OpContext. Light-on goes through an OpScope bound to the
        runner's backend, the one place that holds the guard token; its events go to ctx."""

        def emit(ev: Event) -> None:
            ctx.emit(ev.kind, **ev.data)

        lights = OpScope(ctx.op_id, None, emit, backend=ctx.backend)  # record is the runner's
        started = ctx.session_started_at
        return cls(ctx.op_id, folder, emit,
                   lambda key, text, data: bool(ctx.confirm(key, text, context=data).get("ok")),
                   lights.aura_line_on, ctx.sleep, ctx.check,
                   None if started is None
                   else time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)))


def runner_folder(ctx: Any, sample: Sample, prefix: str) -> Path:
    """The runner's record folder when it keeps one (folder_records), else a new
    `<sample>/<prefix>_<stamp>/` for the operation's own files."""
    if ctx.record_dir is not None:
        return ctx.record_dir
    base, n = sample.dir / f"{prefix}_{time.strftime('%Y%m%d-%H%M%S')}", 1
    path = base
    while path.exists():
        n += 1
        path = Path(f"{base}_{n}")
    path.mkdir(parents=True)
    return path


def run_scan_4x(backend: Backend, sample: Sample, args: dict, sink: EventSink = null_sink, *,
                answers: queue.Queue | None = None, session_started: str | None = None,
                confirm_timeout_s: float | None = None, user_id: str | None = None,
                session_id: str | None = None,
                sleep: Callable[[float], None] = time.sleep) -> dict:
    """Run the scan. Returns {"status", "record", "result"}; a guard refusal or abort is
    raised after the record is complete. Dry run: the plan only, no folder, nothing moves."""
    a = parse(args)
    problems = preflight(backend, sample)
    if problems:
        sink(Event("preflight_failed", "", {"op": NAME, "reasons": problems}))
        return {"status": "preflight_failed", "reasons": problems, "record": None}
    info = sample.load_info()
    z_now = backend.positions().z_um
    pl = plan(info, backend.info().sensor, a, z_now)
    sink(Event("planned", "", pl))
    if a.dry_run:
        sink(Event("finished", "", {"dry_run": True}))
        return {"status": "finished", "dry_run": True, "plan": pl, "record": None}
    sink(Event("preflight_ok", "", {"op": NAME}))

    was_streaming = backend.streaming()
    if was_streaming:
        backend.stop_stream()  # this operation snaps (T-011 decision)
    out: dict[str, Any] = {"status": "error", "record": None}
    try:
        with operation(backend, sample.dir, NAME, sink, args={**asdict(a), "sample_id": sample.id},
                       prefix=PREFIX, user_id=user_id, session_id=session_id) as scope:
            if answers is not None:
                scope.answers = answers
            out["record"] = str(scope.record.dir)
            host = Host.of_scope(scope, timeout_s=confirm_timeout_s, sleep=sleep,
                                 session_started=session_started)
            scope.result = run_body(backend, sample, info, a, pl, host)
        out["status"] = "finished"
    finally:
        if out["record"]:
            _close_legacy(Path(out["record"]))
        if was_streaming:
            backend.start_stream()
    out["result"] = json.loads((Path(out["record"]) / "summary.json").read_text())["result"]
    return out


def run_body(backend: Backend, sample: Sample, info: SampleInfo, a: ScanArgs, pl: dict,
             host: Host) -> dict:
    """The scan itself, inside whatever exit path the host provides. Returns the result."""
    op, emit, out, sleep = host.op_id, host.emit, host.folder, host.sleep
    hole = info.hole or {}
    if not _hole_fit_is_current(hole, host.session_started) and not host.ask(
            "hole_fit_stale", f"hole fit is from {hole.get('fitted_at')}; scan anyway "
            "(re-trace in brightfield recommended)?", {"fitted_at": hole.get("fitted_at")}):
        raise GuardError("operator declined: hole fit not from this session")
    binfo = backend.info()
    ceiling = binfo.ceiling_adu
    axis = FocusAxis(backend, OBJECTIVE_KEY, allow_motion=True, sink=emit, op_id=op, sleep=sleep)
    box = XYBox(*pl["allowed_box_um"])
    xy = XYAxis(backend, box, allow_motion=True, sink=emit, op_id=op)
    backend.set_exposure(a.exposure_ms or AUTO_START_MS)
    backend.set_roi(0)
    um_px, m = pl["um_per_px"], pl["M_px_per_um"]
    rec: dict[str, Any] = {
        "sample": sample.id, "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "header": binfo.to_dict(), "objective": backend.nosepiece(), "um_per_px": um_px,
        "fov_um": pl["fov_um"], "pitch_um": pl["pitch_um"], "grid_n": pl["grid_n"],
        "hole": hole, "margin_um": a.margin_um,
        "coordinates": "x/y = XYStage readback at the tile centre; z = ZDrive (um)",
        "camera_ceiling_adu": ceiling, "tiles": []}

    def save() -> None:
        (out / "scan.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")

    cur = {"tile": "", "pass": ""}

    def grab() -> np.ndarray:
        return backend.snap().image

    def score(frame: np.ndarray) -> dict:
        d = {"sharp": vollath4(frame), "blocks": block_scores(frame, BLOCKS),
             "mean": float(frame.mean()), "p999": float(np.percentile(frame, 99.9)),
             "saturated_frac": float(np.mean(frame >= ceiling))}
        emit(Event("progress", op, {"tile": cur["tile"], "pass": cur["pass"],
                                    "z_um": axis.position_um(), "sharp": d["sharp"],
                                    "mean": d["mean"], "sat": d["saturated_frac"]}))
        return d

    def goto(x: float, y: float) -> tuple[float, float]:
        read = xy.goto(x, y)
        sleep(XY_SETTLE_S)
        return read

    def sweep_pair(z_centre: float, half: float, step: float
                   ) -> tuple[SweepResult, SweepResult | None]:
        cur["pass"] = "coarse"
        coarse = axis.sweep(axis.plan(z_centre, half, step), grab, score=score,
                            settle_s=SETTLE_COARSE_S)
        fine = None
        if coarse.peak_interior:
            cur["pass"] = "fine"
            fine = axis.sweep(axis.plan(coarse.peak_z_um, FINE_HALF_UM, FINE_STEP_UM), grab,
                              score=score, settle_s=SETTLE_FINE_S)
        return coarse, fine

    axis.require_pfs_quiet(disable=True)
    z_guess = pl["z_guess_um"]
    here = axis.position_um()
    lo, hi = SAMPLE_Z_WINDOW_UM
    if here < lo - axis.tol:
        if not host.ask("z_enter_window", f"ZDrive {here:.1f} -> {z_guess:.1f} um "
                        "(approach in steps)?", {"z_um": here, "target_um": z_guess}):
            raise GuardError("operator declined the Z approach into the sample window")
        axis.approach(min(z_guess, hi))
    rec["light"] = [asdict(r) for r in host.light_on(a.aura_line, a.aura_percent)]
    tiles = pl["tiles"]
    goto(tiles[0]["x_um"], tiles[0]["y_um"])
    if a.exposure_ms is None:
        z0 = min(z_guess, hi)
        axis.move_to(z0, allow_ascent_um=max(0.0, z0 - axis.position_um()) + 0.5)
        p = 0.0
        for _ in range(AUTO_ROUNDS):
            p = float(np.percentile(grab(), 99.9))
            f = float(np.clip(AUTO_TARGET * ceiling / max(p, 1.0), 0.25, 4.0))
            if 0.7 < f < 1.4:
                break
            backend.set_exposure(float(np.clip(backend.info().exposure_ms * f, *AUTO_MS)))
        emit(Event("reading", op, {"auto_exposure_ms": backend.info().exposure_ms,
                                   "p999_adu": p}))
    rec["exposure_ms"] = backend.info().exposure_ms
    save()

    frames: dict[str, np.ndarray] = {}
    z_ref, first = z_guess, True
    for k, t in enumerate(tiles):
        host.check()
        t0 = time.monotonic()
        name = t["name"]
        cur["tile"] = name
        emit(Event("progress", op, {"tile": name, "k": k, "n": len(tiles)}))
        xr, yr = goto(t["x_um"], t["y_um"])
        hr = a.first_half_um if first else a.tile_half_um
        coarse, fine = sweep_pair(z_ref, hr, COARSE_STEP_FIRST_UM if first else COARSE_STEP_UM)
        zf, why = best_z_um(coarse, fine)
        if zf is None and not first:  # widen once before giving up on the tile
            coarse, fine = sweep_pair(z_ref, a.first_half_um, COARSE_STEP_FIRST_UM)
            zf, why = best_z_um(coarse, fine)
        grade = GRADE_MEASURED
        pts_all = coarse.points + (fine.points if fine else [])
        keep = dropout_mask([p.diagnostics["mean"] for p in pts_all], DROPOUT_TOLERANCE)
        pts = [p for p, ok in zip(pts_all, keep, strict=True) if ok]
        dropped = [round(p.z_readback_um, 2) for p, ok in zip(pts_all, keep, strict=True)
                   if not ok]
        if dropped and fine is not None:
            fp = [p for p in fine.points if p in pts]
            zc = parabola_peak([p.z_readback_um for p in fp],
                               [p.score for p in fp]) if len(fp) >= 3 else None
            if zc is not None:
                zf, why, grade = zc, f"fine pass without light-dropout frames at {dropped}", \
                    GRADE_COMPUTED
        zs = [p.z_readback_um for p in pts]
        bz = [parabola_peak(zs, [p.diagnostics["blocks"][b] for p in pts]) if len(pts) >= 3
              else None for b in range(BLOCKS * BLOCKS)]
        z_img = zf if zf is not None else z_ref
        z_landed = axis.park_at(min(z_img, hi))
        img = grab()
        frames[name] = img
        np.save(out / f"{name}.npy", img)
        emit(Event("frame_ready", op, {"tile": name, "file": f"{name}.npy",
                                       "shape": list(img.shape), "z_um": z_landed}))
        tile = {"name": name, "row": t["row"], "col": t["col"], "x_cmd_um": t["x_um"],
                "y_cmd_um": t["y_um"], "x_um": round(xr, 2), "y_um": round(yr, 2),
                "z_focus_um": None if zf is None else round(zf, 3), "focus_note": why,
                "z_image_um": round(z_landed, 3),
                "block_z_um": [None if v is None else round(v, 2) for v in bz],
                "blocks_per_side": BLOCKS, "dropout_z_um": dropped,
                "curve": [{"z": round(p.z_readback_um, 3), "sharp": round(p.score, 5),
                           "mean": round(p.diagnostics["mean"], 1),
                           "sat": p.diagnostics["saturated_frac"]} for p in pts_all],
                "frame_mean": float(img.mean()), "frame_max": int(img.max()),
                "seconds": round(time.monotonic() - t0, 1),
                "grades": {"z_focus_um": grade if zf is not None else None,
                           "z_image_um": GRADE_MEASURED, "block_z_um": GRADE_COMPUTED,
                           "x_um": GRADE_MEASURED, "y_um": GRADE_MEASURED}}
        rec["tiles"].append(tile)
        save()
        emit(Event("reading", op, {k2: tile[k2] for k2 in
                                   ("name", "x_um", "y_um", "z_focus_um", "focus_note",
                                    "z_image_um", "dropout_z_um")}))
        if zf is not None:
            z_ref, first = zf, False

    _save_mosaic(out, rec["tiles"], frames, m, pl["calibration"])
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save()
    plane = fit_plane([(t["x_um"], t["y_um"], t["z_focus_um"]) for t in rec["tiles"]
                       if t["z_focus_um"] is not None])
    result = {k2: rec[k2] for k2 in ("um_per_px", "fov_um", "pitch_um", "grid_n", "hole",
                                     "margin_um", "exposure_ms", "camera_ceiling_adu",
                                     "tiles", "light")}
    result.update(scan_box_um=pl["scan_box_um"], allowed_box_um=pl["allowed_box_um"],
                  M_px_per_um=m, calibration=pl["calibration"], focus_plane=plane,
                  mosaic={"file": "mosaic.npy", "meta": "mosaic.json"}, legacy="scan.json",
                  folder=str(out))
    return result


def _close_legacy(folder: Path) -> None:
    """Add the exit path's lights-off and end Z to scan.json, as the script's `finally` did."""
    summary = folder / "summary.json"
    if not summary.exists():
        return
    s = json.loads(summary.read_text(encoding="utf-8"))
    end = s.get("end_state") or {}
    pos = end.get("positions") if isinstance(end, dict) else None
    _legacy_end(folder, s.get("lights_off"), pos.get("z_um") if isinstance(pos, dict) else None,
                s.get("status"), "operation() exit path")


def _legacy_end(folder: Path, light_off: dict | None, z_end_um: float | None, status: str | None,
                by: str) -> None:
    """End fields of the legacy scan.json: light_off readback, z_end_um, status."""
    scan = folder / "scan.json"
    if not scan.exists():  # stopped before the first save: no legacy record to close
        return
    rec = json.loads(scan.read_text(encoding="utf-8"))
    rec["light_off"] = None if light_off is None else {**light_off, "by": by}
    rec["z_end_um"], rec["status"] = z_end_um, status
    scan.write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")


# -- the engine runner (T-011) ------------------------------------------------------------


def _checks(reasons: list[str], name: str = NAME) -> list[dict]:
    if not reasons:
        return [{"name": name, "ok": True, "want": "ready", "read": "ready", "why": ""}]
    return [{"name": name, "ok": False, "want": "ready", "read": r, "why": r} for r in reasons]


@register_operation
class Scan4x(Operation):
    """`start("scan_4x", {"sample_id": ..., <ScanArgs>})`. Motion class (control + session).
    `approaches`: a scan that starts below the Z window climbs with `approach`; on the bench
    the runner refuses it until a clearance check is given (T-011b)."""

    name = NAME
    record_prefix = PREFIX
    snaps = True
    approaches = True
    samples_root: ClassVar[Path] = SAMPLES_ROOT

    def _sample(self) -> Sample:
        sid = self.args.get("sample_id")
        if not sid:
            raise ValueError("scan_4x needs a sample_id")
        return Sample(str(sid), self.samples_root)

    def _args(self) -> ScanArgs:
        return parse({k: v for k, v in self.args.items() if k != "sample_id"})

    def plan(self) -> dict:
        try:
            return plan(self._sample().load_info(), PLAN_SENSOR, self._args())
        except ValueError as exc:
            return {"op": NAME, "error": str(exc)}

    def preflight(self) -> list[dict]:
        try:
            self._args()
            sample = self._sample()
        except ValueError as exc:
            return _checks([str(exc)])
        return _checks(preflight(self.ctx.backend, sample))

    def run(self) -> dict:
        b, a, sample = self.ctx.backend, self._args(), self._sample()
        info = sample.load_info()
        pl = plan(info, b.info().sensor, a, b.positions().z_um)
        if a.dry_run:
            return {"dry_run": True, "plan": pl}
        folder = runner_folder(self.ctx, sample, PREFIX)
        status = "error"
        try:
            result = run_body(b, sample, info, a, pl, Host.of_runner(self.ctx, folder))
            status = "finished"
            return result
        except Aborted:
            status = "aborted"
            raise
        finally:
            # scan.json carries the light readback like summary.json: switch off here (no
            # token needed) and record it; the runner's exit path follows and finds it off
            _legacy_end(folder, lights_off(b), b.positions().z_um, status,
                        "scan_4x exit (all off); the runner's exit path follows")
