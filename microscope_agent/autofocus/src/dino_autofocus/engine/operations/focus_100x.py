"""`focus_100x`: guarded 100x Oil focus search with ZDrive, particle light (operations-spec 7).

Port of `scripts/focus_100x.py`. The guards decide the motion: PFS off, every sweep ascends,
each move is read back, and the sweep ceiling is min(3200, centre + 0.4 x 130 um WD) from
`FocusAxis`. A coarse peak on the top end of the span is **not** climbed: Z goes back down to
the low end and the operator is asked (`climb_past_top`) whether to extend upward. A yes
re-sweeps from the low end in steps, up to one span higher but never past the guards'
ceiling (at most `MAX_EXTENSIONS` times). A peak on the low end is reported
("re-centre lower"); no fine pass follows either end.

Metric: `peak` (brightest 4 x 4-binned spot minus the binned median, for sparse particle
fields) by default, or `vollath`. Warnings (classical, not model): two separate maxima on the
coarse curve -> "check immersion oil"; clipped pixels -> "reduce exposure"; a first frame at
the dark level -> "signal at dark level".

Centre: `centre_um` if given; else the sample's 4x focus plane at the current XY plus the
4x -> 100x parfocal offset (about -60 um on 2026-09-30, unmeasured provisional); else 2930.
A centre above the 4x focus is asked first (`centre_above_4x`). No immersion loading recorded
this session (`oil_loaded` not True) is asked first (`oil_applied`).

Record `<sample>/focus100x_<stamp>/`: engine `log.jsonl` + `summary.json` with the script's
fields (coarse, fine, z_focus_um, why, z_parked_um, position) plus the run arguments, `sat`
per point, warnings and grades.

The step generation (arguments, centre, coarse / fine / extension spans, reading the coarse
peak, the warnings' rules) is the flat file `microscope_agent/src/focus_search.py` (the
soft-matter-agents layout, docs/integration-sma.md section 9), re-exported here. The guards
here (`FocusAxis`) still compute the ceiling, plan the Z list and check every move.
"""

from __future__ import annotations

import json
import queue
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from ..._flat import load
from ...bench_values import (
    DOUBLE_PEAK_PROMINENCE,
    FOCUS_ARG_DEFAULTS,
    FOCUS_LIGHT_DEFAULTS,
    MAX_SATURATED_FRACTION,
    PEAK_BIN_PX,
)
from ...bench_values import FOCUS_DARK_OFFSET_ADU as DARK_OFFSET_ADU
from ...bench_values import FOCUS_DEFAULT_CENTRE_UM as DEFAULT_CENTRE_UM
from ...bench_values import FOCUS_DEFAULT_EXPOSURE_MS as DEFAULT_EXPOSURE_MS
from ...bench_values import FOCUS_PARFOCAL_4X_TO_100X_UM as PARFOCAL_4X_TO_100X_UM
from ...bench_values import FOCUS_SIGNAL_MIN_ADU as SIGNAL_MIN_ADU
from ...focus.classical import (
    OIL_WARNING,
    double_peak,
    peak_brightness,
    vollath4,
)
from ..backend import Backend
from ..events import Event, EventSink, null_sink
from ..guards import (
    SAMPLE_Z_WINDOW_UM,
    FocusAxis,
    GuardError,
    SweepResult,
    bench_ascent_refusal,
    best_z_um,
    operation,
)
from ..records import GRADE_COMPUTED, GRADE_MEASURED
from ..runner import Operation, register_operation
from ..sample import SAMPLES_ROOT, Sample
from .scan_4x import Host, _checks, focus_plane_4x, runner_folder

load("focus_search", f"{__package__}._focus_search")
from ._focus_search import (  # noqa: E402, F401 - re-exported
    DARK_SIGNAL,
    INTERIOR,
    LOW_END,
    METRICS,
    REDUCE_EXPOSURE,
    TOP_END,
    centre_grade,
    coarse_span,
    extension_span,
    fine_span,
    peak_at,
    room_above,
)
from ._focus_search import FocusArgs as SearchArgs  # noqa: E402
from ._focus_search import at_dark_level as _at_dark_level  # noqa: E402
from ._focus_search import centre_from_plane as _centre_from_plane  # noqa: E402
from ._focus_search import parse as _parse  # noqa: E402
from ._focus_search import too_bright as _too_bright  # noqa: E402

__all__ = ["DARK_OFFSET_ADU", "DEFAULT_CENTRE_UM", "DEFAULT_EXPOSURE_MS",
           "PARFOCAL_4X_TO_100X_UM", "SIGNAL_MIN_ADU", "FocusArgs", "parse",
           "centre_from_plane", "at_dark_level", "too_bright", "run_focus_100x", "plan"]


MAX_EXTENSIONS = FOCUS_ARG_DEFAULTS["max_extensions"]  # this repository's default count


@dataclass(frozen=True)
class FocusArgs(SearchArgs):
    """The flat search's arguments plus the light this operation switches on before it
    (the flat search sets no light: in soft-matter-agents the plan does, D-03f)."""

    aura_line: str = FOCUS_LIGHT_DEFAULTS["aura_line"]
    aura_percent: float = FOCUS_LIGHT_DEFAULTS["aura_percent"]


# The flat search takes every bench number as an argument (D-02); these wrappers supply
# this repository's values from bench_values so the rest of the engine reads as before.
def parse(args: dict) -> FocusArgs:
    light = {k: args[k] for k in FOCUS_LIGHT_DEFAULTS if k in args}
    a = _parse({k: v for k, v in args.items() if k not in FOCUS_LIGHT_DEFAULTS},
               FOCUS_ARG_DEFAULTS)
    return FocusArgs(**asdict(a), **light)


def centre_from_plane(plane: dict | None) -> dict:
    return _centre_from_plane(plane, default_centre_um=DEFAULT_CENTRE_UM,
                              parfocal_offset_um=PARFOCAL_4X_TO_100X_UM)


def at_dark_level(first_max_adu: float) -> bool:
    return _at_dark_level(first_max_adu, dark_offset_adu=DARK_OFFSET_ADU,
                          signal_min_adu=SIGNAL_MIN_ADU)


def too_bright(saturated_fractions) -> bool:
    return _too_bright(saturated_fractions, MAX_SATURATED_FRACTION)

NAME = "focus_100x"
PREFIX = "focus100x"
OBJECTIVE_100X = "6-Plan Apo LmbdD0.13 100x Oil"
OBJECTIVE_KEY = "100x-Oil"
SETTLE_COARSE_S, SETTLE_FINE_S = 0.1, 0.15


def default_centre(sample: Sample | None, x_um: float | None, y_um: float | None) -> dict:
    """The suggested sweep centre and where it came from (computed, not model)."""
    p = None
    if sample is not None and x_um is not None and y_um is not None:
        p = focus_plane_4x(sample, x_um, y_um)
    return centre_from_plane(p)


def plan(args: dict | FocusArgs, centre: dict) -> dict:
    a = args if isinstance(args, FocusArgs) else parse(args)
    c = float(a.centre_um) if a.centre_um is not None else float(centre["centre_um"])
    coarse = FocusAxis(None, OBJECTIVE_KEY).plan(*coarse_span(c, a))
    return {"op": NAME, "centre_um": c,
            "centre_source": "argument" if a.centre_um is not None else centre["source"],
            "z_4x_um": centre.get("z_4x_um"), "coarse": coarse.describe(),
            "ceiling_um": coarse.ceiling_um,
            "fine": f"+-{a.fine_half_um:g} um @ {a.fine_step_um:g} around an interior coarse peak",
            "metric": a.metric, "exposure_ms": a.exposure_ms,
            "light": f"Aura {a.aura_line.upper()} {a.aura_percent:g} %"}


def preflight(backend: Backend) -> list[str]:
    try:
        label = backend.nosepiece()
    except Exception as exc:  # noqa: BLE001
        label = f"unreadable ({exc})"
    problems = [] if label == OBJECTIVE_100X else [
        f"nosepiece reads {label!r}, not {OBJECTIVE_100X!r}"]
    # T-029d second layer: the 100x sweeps climb with move_to, which the bench lock refuses
    try:
        info = backend.info()
    except Exception:  # noqa: BLE001 - is_bench counts an unreadable info as the bench
        info = None
    why = bench_ascent_refusal(info, "100x-Oil", SAMPLE_Z_WINDOW_UM[1])
    if why:
        problems.append(why)
    return problems


def run_focus_100x(backend: Backend, sample: Sample, args: dict, sink: EventSink = null_sink, *,
                   answers: queue.Queue | None = None, confirm_timeout_s: float | None = None,
                   user_id: str | None = None, session_id: str | None = None,
                   sleep: Callable[[float], None] = time.sleep) -> dict:
    """Run the search. Returns {"status", "record", "result"} (or preflight_failed)."""
    a = parse(args)
    problems = preflight(backend)
    pos = backend.positions()
    centre = default_centre(sample, pos.x_um, pos.y_um)
    try:
        pl = plan(a, centre)
    except GuardError as exc:
        problems.append(str(exc))
    if problems:
        sink(Event("preflight_failed", "", {"op": NAME, "reasons": problems}))
        return {"status": "preflight_failed", "reasons": problems, "record": None}
    sink(Event("planned", "", pl))
    sink(Event("preflight_ok", "", {"op": NAME}))

    was_streaming = backend.streaming()
    if was_streaming:
        backend.stop_stream()
    out: dict[str, Any] = {"status": "error", "record": None}
    try:
        with operation(backend, sample.dir, NAME, sink, args={**asdict(a), "sample_id": sample.id},
                       prefix=PREFIX, user_id=user_id, session_id=session_id) as scope:
            if answers is not None:
                scope.answers = answers
            out["record"] = str(scope.record.dir)
            host = Host.of_scope(scope, timeout_s=confirm_timeout_s, sleep=sleep,
                                 session_started=None)
            scope.result = run_body(backend, a, pl, host)
        out["status"] = "finished"
    finally:
        if was_streaming:
            backend.start_stream()
    out["result"] = json.loads((Path(out["record"]) / "summary.json").read_text())["result"]
    return out


def _points(sw: SweepResult) -> list[dict]:
    return [{"z_um": p.z_readback_um, "score": p.score, "vollath": p.diagnostics.get("vollath"),
             "mean": p.diagnostics.get("mean"), "max": p.diagnostics.get("max"),
             "sat": p.diagnostics.get("sat")} for p in sw.points]


def run_body(backend: Backend, a: FocusArgs, pl: dict, host: Host) -> dict:
    """The search itself, inside whatever exit path the host provides. Returns the result."""
    op, emit = host.op_id, host.emit
    centre = pl["centre_um"]
    if a.oil_loaded is not True and not host.ask(
            "oil_applied", "no immersion loading recorded this session; oil applied?", {}):
        raise GuardError("operator declined: no immersion oil")
    z4 = pl.get("z_4x_um")
    if z4 is not None and centre > z4 and not host.ask(
            "centre_above_4x", f"centre {centre:.1f} is above the 4x focus {z4:.1f}; 100x focus "
            "is usually 60-100 um below. Go on?", {"centre_um": centre, "z_4x_um": z4}):
        raise GuardError("operator declined: centre above the 4x focus")

    ceiling = backend.info().ceiling_adu
    backend.set_exposure(a.exposure_ms)
    axis = FocusAxis(backend, OBJECTIVE_KEY, allow_motion=True, sink=emit, op_id=op,
                     sleep=host.sleep)
    cur = {"pass": ""}

    def grab() -> np.ndarray:
        return backend.snap().image

    def score(f: np.ndarray) -> dict:
        v = vollath4(f)
        d = {"sharp": peak_brightness(f, PEAK_BIN_PX) if a.metric == "peak" else v, "vollath": v,
             "mean": float(f.mean()), "max": int(f.max()), "sat": float(np.mean(f >= ceiling))}
        emit(Event("progress", op, {"pass": cur["pass"], "z_um": axis.position_um(), **d}))
        return d

    axis.require_pfs_quiet(disable=True)
    light = [asdict(r) for r in host.light_on(a.aura_line, a.aura_percent)]

    warnings: list[str] = []
    first = grab()
    if at_dark_level(float(first.max())):
        warnings.append(DARK_SIGNAL)
        emit(Event("reading", op, {"warning": DARK_SIGNAL, "max_adu": int(first.max()),
                                   "dark_offset_adu": DARK_OFFSET_ADU}))

    cur["pass"] = "coarse"
    coarse = axis.sweep(axis.plan(*coarse_span(centre, a)), grab, score=score,
                        settle_s=SETTLE_COARSE_S)
    spans = [[coarse.plan.z_um[0], coarse.plan.z_um[-1]]]
    while coarse.at_top and len(spans) <= a.max_extensions:
        lo, hi = coarse.points[0].z_um, coarse.points[-1].z_um
        axis.move_to(lo)  # back down to the low end (the retract direction), as the script
        # the extension re-sweeps from the low end in steps, so Z never jumps upward
        nxt = axis.plan(*extension_span(lo, hi, a.step_um))
        if not room_above(nxt.z_um[-1], hi):  # the ceiling leaves nothing above
            emit(Event("reading", op, {"peak_at": "top_end", "ceiling_um": nxt.ceiling_um}))
            break
        if not host.ask("climb_past_top", f"peak at the top end of {lo:.1f}-{hi:.1f} um; "
                        f"extend upward to {nxt.z_um[-1]:.1f}?",
                        {"span_um": [lo, hi], "new_top_um": nxt.z_um[-1],
                         "ceiling_um": nxt.ceiling_um}):
            break
        host.check()
        coarse = axis.sweep(nxt, grab, score=score, settle_s=SETTLE_COARSE_S)
        spans.append([nxt.z_um[0], nxt.z_um[-1]])
    fine = None
    where = peak_at(coarse.at_top, coarse.argmax_index)
    if where == TOP_END:
        axis.move_to(coarse.points[0].z_um)
    elif where == LOW_END:
        emit(Event("reading", op, {"peak_at": LOW_END,
                                   "text": "focus is below the span; re-centre lower"}))
    else:
        cur["pass"] = "fine"
        fine = axis.sweep(axis.plan(*fine_span(coarse.peak_z_um, a)), grab,
                          score=score, settle_s=SETTLE_FINE_S)
    zf, why = best_z_um(coarse, fine)
    if double_peak([p.z_readback_um for p in coarse.points], [p.score for p in coarse.points],
                   DOUBLE_PEAK_PROMINENCE):
        warnings.append(OIL_WARNING)
    if too_bright(p.diagnostics.get("sat")
                  for p in coarse.points + (fine.points if fine else [])):
        warnings.append(REDUCE_EXPOSURE)
    parked = axis.park_at(zf) if zf is not None else None
    for w in warnings:
        emit(Event("reading", op, {"warning": w}))
    return {
        "args": asdict(a), "centre_um": centre, "centre_source": pl["centre_source"],
        "ceiling_um": pl["ceiling_um"], "light": light, "coarse_spans_um": spans,
        "coarse": _points(coarse), "fine": _points(fine) if fine else None,
        "z_focus_um": zf, "why": why, "peak_at": where, "z_parked_um": parked,
        "position": asdict(backend.positions()), "warnings": warnings,
        "grades": {"z_focus_um": GRADE_MEASURED if zf is not None else None,
                   "z_parked_um": GRADE_MEASURED, "score": GRADE_COMPUTED,
                   "centre_um": "argument" if a.centre_um is not None else centre_grade(pl)},
    }


# -- the engine runner (T-011) ------------------------------------------------------------


@register_operation
class Focus100x(Operation):
    """`start("focus_100x", {"sample_id": ..., <FocusArgs>})`. Motion class (control +
    session). `oil_loaded` should come from this session's `load_immersion` record; until
    the runner passes it, the operation asks."""

    name = NAME
    record_prefix = PREFIX
    snaps = True
    samples_root: ClassVar[Path] = SAMPLES_ROOT

    def _sample(self) -> Sample:
        sid = self.args.get("sample_id")
        if not sid:
            raise ValueError("focus_100x needs a sample_id")
        return Sample(str(sid), self.samples_root)

    def _args(self) -> FocusArgs:
        return parse({k: v for k, v in self.args.items() if k != "sample_id"})

    def plan(self) -> dict:
        try:  # no hardware here: the 4x plane is taken at the scan's hole centre
            sample, a = self._sample(), self._args()
            hole = sample.load_info().hole or {}
            xy = hole.get("centre_um") or (None, None)
            return plan(a, default_centre(sample, *xy))
        except (ValueError, GuardError) as exc:
            return {"op": NAME, "error": str(exc)}

    def preflight(self) -> list[dict]:
        try:
            self._args()
            self._sample()
        except ValueError as exc:
            return _checks([str(exc)], NAME)
        return _checks(preflight(self.ctx.backend), NAME)

    def run(self) -> dict:
        b, a, sample = self.ctx.backend, self._args(), self._sample()
        p = b.positions()
        pl = plan(a, default_centre(sample, p.x_um, p.y_um))
        host = Host.of_runner(self.ctx, runner_folder(self.ctx, sample, PREFIX))
        return run_body(b, a, pl, host)
