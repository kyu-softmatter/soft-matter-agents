"""Motion guards and the lights-off / single-owner scopes. Safety is decided here, in code.

Rules (docs/runs/2026-09-30_substrate-scan.md, scripts/change_objective.py, focus_100x.py):

- Z targets stay inside the sample window 2800-3200 um. Below it only `park_at` (descend
  only) goes, e.g. to the 0 um retract of an objective change.
- Upward moves (toward the sample) are refused unless the caller allows that much ascent
  (`move_to(z, allow_ascent_um=)`); sweeps are planned ascending and climb one step at a
  time. Descents are always allowed.
- A sweep's ceiling is min(3200, centre + 0.4 x free working distance): 130 um for the
  100x Oil. An objective with no known working distance gets no plan.
- If a sweep's peak is on its top plane it does not climb further (`at_top`); the
  operation asks the operator with `scope.ask("climb_past_top", ...)`.
- Every move is read back; off by more than the tolerance stops the operation
  (2026-09-30: commanded 3037.0, read 3036.0 -> stopped).
- Coming back from a retract, Z does not jump to its target. `approach` keeps the bench
  procedure: one move up to 2800 um (the bottom of the sample window), then steps of at
  most the objective's `approach_step_um` with readback, a rise check and the caller's
  clearance check at every step (soft-matter-agents task 026: a handed-over Z is a goal,
  not a destination).
- XY targets stay in the box (+1 mm). A move longer than the objective's `long_xy_um`
  in `OBJECTIVE_LIMITS` needs Z retracted to z_safe, confirmed by readback. The objective is read
  back from the nosepiece at each move; unreadable or not in the table means the
  strictest value (any move needs Z retracted). There is no per-operation override
  (director, PLAN section 5). At integration the table moves to soft-matter-agents
  `envelope/`.
- Values not yet measured on the stand are marked `PROVISIONAL` ("unmeasured
  provisional") here and in every motion record whose decision used them
  (docs/microscope-pc-checklist.md).
- Manual steps (oil loaded) are `scope.ask` -> `confirm` command -> `confirmed` event.
- The nosepiece turns only with Z retracted and PFS off and out of range.
- `operation()` switches Aura and DiaLamp off and reads them back on every exit path.
- One engine owns the backend at a time (`exclusive`).
- A model-graded value (`records.Graded`, grade "model") is refused as any guard input.
- The comparisons behind these refusals are the flat `microscope_agent/src/
  focus_step_rules.py` (D-01), asked at the moment of comparison (D-01b); this file keeps
  the limits, the backend calls, the records and the bench locks.
- `dry_run=True` records the motion and sends nothing.

Method names follow agentic_microscope's FocusAxis as the scripts call it (T-002 appendix),
so operations port from `scripts/` mechanically.
"""

from __future__ import annotations

import math
import queue
import re
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .._flat import load
from .backend import GUARD_TOKEN, Backend, BackendInfo, PfsState, Readback, is_bench
from .events import Event, EventSink, fan_out, null_sink
from .patterns import TRAP_RANGE_UM
from .records import Graded, OpRecord

#: The flat rules file, loaded by path as soft-matter-agents will hold it. Every limit is
#: passed in; a rule answers None (allowed) or the sentence of the refusal. Not delegated:
#: the approach loop (its next target comes from the readback, `approach_steps` plans from
#: the nominal) and the XY long-move rule (`needs_retract_before_xy` wants the lens kind of
#: D-04; today every lens is held to its table row).
_rules = load("focus_step_rules", "dino_autofocus.engine.focus_step_rules")

PROVISIONAL = "unmeasured provisional"

SAMPLE_Z_WINDOW_UM = (2800.0, 3200.0)  # measured window of the 2026-09-30 bench
RETRACT_Z_UM, RETURN_Z_UM = 0.0, 2800.0  # change_objective.py
WD_FRACTION = 0.4
#: free working distance per lens; add a lens only once known. 4x and 100x-Oil from the
#: 2026-09-30 run; 10x, 20x, 40x-WI, 60x-Oil are catalog values (librarian E3, read
#: 2026-10-02, docs/microscope-pc-checklist.md). 40x-WI 0.17 mm: set by the user 2026-10-02
#: (collar at 0.17; catalog range 0.16-0.20 mm, value at that collar not in the catalog).
FREE_WD_UM = {"4x": 20000.0, "10x": 4000.0, "20x": 800.0, "40x-WI": 170.0,
              "60x-Oil": 150.0, "100x-Oil": 130.0}
XY_BOX_MARGIN_UM = 1000.0

# unmeasured provisional (checklist Q20 / Q12); every use is marked in the record
Z_SAFE_UM = 0.0  # z_safe: full retract, for every lens
RETRACTED_MAX_Z_UM = Z_SAFE_UM + 1.0  # "Z retracted" for nosepiece turns and long XY moves
# F5 immersion-loading step-out: +Y by 15 mm (user, PLAN v1.3). Stage-level, not per lens.
ESCAPE_DY_UM: float = +15000.0

# SAFETY (T-029d): anything but the exact value "MEASURED" locks Z approach on the real
# stand. Unlocked by the user on 2026-10-02 ("2800 제한 해제") before Q13/Q20 and the stage
# limits were measured. Partial unlock: on the bench every upward move (sweeps included)
# stays under approach_ceiling_um, so only the 4x, 10x and 20x go above 2800 um
# (bench_ascent_refusal). mm-real's bench motion lock is separate. Read only by
# bench_approach_state(); no argument, environment variable or setting reaches it.
BENCH_APPROACH = "MEASURED"
BENCH_APPROACH_REASON = (
    "bench Z approach is locked until it is measured on the stand: checklist Q13 (a safe "
    "approach step from 0 to 2800 um), Q20 (how far Z must retract before XY moves) and the "
    "stage travel limits (T-029d)")


def bench_approach_state() -> str:
    """Fail-safe: "MEASURED" only for the exact value, else "LOCKED: <reason>"."""
    return "MEASURED" if BENCH_APPROACH == "MEASURED" else f"LOCKED: {BENCH_APPROACH_REASON}"


def bench_ascent_refusal(info: Any, lens_key: str | None, target_um: float) -> str | None:
    """Why an upward Z move to `target_um` with `lens_key` in place is refused, or None.
    Only on the bench (`is_bench(info)`). While BENCH_APPROACH is locked: refused above
    RETURN_Z_UM (2800) on every lens, and at any height on a lens other than the 4x.
    Unlocked (partial unlock, user 2026-10-02): refused above the lens's approach_ceiling_um,
    so a lens whose free WD does not cover the window (40x-WI, 60x-Oil, 100x-Oil, unknown)
    stays at or below 2800 for every upward move, sweeps and move_to included, not only
    approach(). Callers apply it to upward moves only; downward moves and retract() are never
    refused."""
    if not is_bench(info):
        return None
    if bench_approach_state() == "MEASURED":
        top = approach_ceiling_um(lens_key)
        if target_um > top:
            return (f"upward Z move to {target_um:.2f} um refused on the bench: above {top:.0f} um "
                    f"for {lens_key or 'an unreadable lens'}, whose free working distance does not "
                    f"cover the sample window (partial unlock, user 2026-10-02)")
        return None
    if target_um > RETURN_Z_UM:
        return (f"upward Z move to {target_um:.2f} um refused: above {RETURN_Z_UM:.0f} um on "
                f"the bench. {BENCH_APPROACH_REASON}")
    if lens_key != "4x":
        return (f"upward Z move on {lens_key or 'an unreadable lens'} refused on the bench "
                f"(only the 4x may climb, up to {RETURN_Z_UM:.0f} um). {BENCH_APPROACH_REASON}")
    return None
Z_TOL_UM = 0.25
XY_TOL_UM = 5.0


@dataclass(frozen=True)
class ObjectiveLimits:
    """One row of the per-objective guard table. Every value is unmeasured provisional."""

    long_xy_um: float  # an XY move longer than this needs Z retracted first
    approach_step_um: float  # largest Z step when climbing back above 2800 um


# The per-objective guard table (registry key -> row), unmeasured provisional; it moves to
# soft-matter-agents envelope/ at integration.
# long_xy_um: free WD >= 10 mm -> 10 mm (4x tile steps of 3.3 mm stay at sample Z, as on
#   2026-09-30; the F5 escape of 15-20 mm still retracts); otherwise min(field of view,
#   1 mm), field = 2400 px x the calibrated pixel (configs/ti2_*.yaml, catalogue WD).
# approach_step_um: 10 um for every lens to start, about WD/13 for the 100x Oil (checklist
#   Q13); to be confirmed on the bench before M4.
OBJECTIVE_LIMITS: dict[str, ObjectiveLimits] = {
    "4x": ObjectiveLimits(10000.0, 10.0),  # WD 20 mm
    "10x": ObjectiveLimits(1000.0, 10.0),  # WD 4 mm, field 1.56 mm
    "20x": ObjectiveLimits(777.0, 10.0),  # WD 0.8 mm, field 0.777 mm
    "40x-WI": ObjectiveLimits(390.0, 10.0),  # WD 0.17 mm, field 0.39 mm
    "60x-Oil": ObjectiveLimits(260.0, 10.0),  # WD 0.15 mm, field 0.26 mm
    "100x-Oil": ObjectiveLimits(156.0, 10.0),  # WD 0.13 mm, field 0.156 mm
}
# objective unreadable or not in the table: retract before any XY move, smallest Z step
STRICTEST = ObjectiveLimits(*_rules.strictest_for_unknown_lens(
    {k: (r.long_xy_um, r.approach_step_um) for k, r in OBJECTIVE_LIMITS.items()}))


UNKNOWN_OBJECTIVE = "unknown objective"  # FocusAxis key when the objective cannot be read


def approach_ceiling_um(key: str | None, window: tuple[float, float] = SAMPLE_Z_WINDOW_UM
                        ) -> float:
    """Highest target FocusAxis.approach() may climb to. The approach climbs without an
    image, so above RETURN_Z_UM only a lens whose known free working distance covers the
    whole window above it may go (the 4x, 10x and 20x). Every other lens, an unlisted key and an
    unreadable objective stop at RETURN_Z_UM (2800). Refused, never clamped (T-027b)."""
    return _rules.approach_ceiling(RETURN_Z_UM, window[1], FREE_WD_UM.get(key) if key else None)


def limits_for(label_or_key: str | None) -> tuple[ObjectiveLimits, str]:
    """(row, row name) for a nosepiece label or registry key; the strictest row if unknown."""
    if label_or_key is None:
        return STRICTEST, "strictest (objective unreadable)"
    key = label_or_key
    if key not in OBJECTIVE_LIMITS:
        try:
            key = registry_key(label_or_key)
        except GuardError:
            return STRICTEST, f"strictest ({label_or_key!r} has no magnification)"
    if key not in OBJECTIVE_LIMITS:
        return STRICTEST, f"strictest ({key} not in OBJECTIVE_LIMITS)"
    return OBJECTIVE_LIMITS[key], key


class GuardError(RuntimeError):
    """A guard refused; the operation stops."""


class OperationAborted(RuntimeError):
    """The operator (or an abort command) stopped the operation."""


def plain(v: Any, what: str) -> float:
    if isinstance(v, Graded):
        why = _rules.refuse_model_graded(v.grade, what, v.source)
        if why:
            raise GuardError(why)
        v = v.value
    f = float(v)
    if not math.isfinite(f):
        raise GuardError(f"{what}: {f} is not a finite number")
    return f


def registry_key(nosepiece_label: str) -> str:
    """'1-Plan Apo LmbdD20 4x' -> '4x'; '6-Plan Apo LmbdD0.13 100x Oil' -> '100x-Oil';
    '4-Apo LmbdS 40xC WI' -> '40x-WI'; 'Ti2 40x/1.25 water (...)' -> '40x-WI'.

    The magnification is digits then "x", followed by a letter (the "C" of 40xC) or a word
    boundary, and not part of a decimal such as LmbdD0.13."""
    m = re.search(r"(?<![\d.])(\d+)x(?=[A-Za-z]|\b)", nosepiece_label)
    if not m:
        raise GuardError(f"no magnification in objective label {nosepiece_label!r}")
    low = nosepiece_label.lower()
    suffix = "-Oil" if "oil" in low else "-WI" if (" wi" in low or "water" in low) else ""
    return f"{m.group(1)}x{suffix}"


# -- Z ------------------------------------------------------------------------------------
@dataclass
class SweepPlan:
    objective: str
    centre_um: float
    half_um: float
    step_um: float
    ceiling_um: float
    z_um: list[float]

    def describe(self) -> str:
        return (f"{self.objective}: {len(self.z_um)} planes {self.z_um[0]:.2f} -> "
                f"{self.z_um[-1]:.2f} um, step {self.step_um} (ascending), "
                f"ceiling {self.ceiling_um:.2f}")


@dataclass
class SweepPoint:
    z_um: float
    z_readback_um: float
    score: float | None
    diagnostics: dict = field(default_factory=dict)


@dataclass
class SweepResult:
    plan: SweepPlan
    points: list[SweepPoint]
    argmax_index: int | None
    peak_z_um: float | None  # the readback of the best plane, not the commanded z
    peak_interior: bool
    at_top: bool


def best_z_um(coarse: SweepResult, fine: SweepResult | None) -> tuple[float | None, str]:
    if fine is not None and fine.peak_interior:
        return fine.peak_z_um, "fine peak inside its span"
    if coarse.peak_interior:
        return coarse.peak_z_um, "coarse peak (no fine pass, or its peak on an end)"
    if coarse.at_top:
        return None, "peak at the top end: focus may be higher; the operator decides"
    if coarse.argmax_index is None:
        return None, "no scored planes"
    return None, "peak at the low end: focus is below the span; re-centre lower"


def _score(fn: Callable | None, frame: Any) -> tuple[float | None, dict]:
    r = frame if fn is None else fn(frame)
    if isinstance(r, Mapping):
        s = r.get("score", r.get("sharp"))
        return (None if s is None else float(s)), dict(r)
    if isinstance(r, tuple):
        return float(r[0]), dict(r[1])
    return float(r), {}


class FocusAxis:
    def __init__(self, backend: Backend, objective: str, *, allow_motion: bool = False,
                 dry_run: bool = False, sink: EventSink = null_sink, op_id: str = "",
                 window: tuple[float, float] = SAMPLE_Z_WINDOW_UM, tol_um: float = Z_TOL_UM,
                 sleep: Callable[[float], None] = time.sleep):
        self.b, self.allow_motion, self.dry_run = backend, allow_motion, dry_run
        if objective is None:
            self.key = UNKNOWN_OBJECTIVE  # strictest: no sweep plan, approach capped at 2800
        elif objective in FREE_WD_UM or objective in OBJECTIVE_LIMITS:
            self.key = objective
        else:
            self.key = registry_key(objective)
        self.emit, self.op_id, self.window = sink, op_id, window
        self.tol, self.sleep = tol_um, sleep
        self.motions: list[dict] = []
        self._z_dry: float | None = None

    @classmethod
    def from_backend(cls, backend: Backend, **kw: Any) -> FocusAxis:
        """The axis for the objective read back now; a read error or an unreadable label
        gives the unknown objective (strictest)."""
        try:
            label = backend.nosepiece()
            key: str | None = registry_key(label) if label else None
        except Exception:  # noqa: BLE001 - an unreadable objective is the strictest case
            key = None
        return cls(backend, key, **kw)

    def position_um(self) -> float:
        if self.dry_run and self._z_dry is not None:
            return self._z_dry
        p = self.b.positions()
        if p.z_um is None:
            raise GuardError(f"ZDrive unreadable: {p.errors.get('z', p.errors)}")
        return p.z_um

    def ceiling_um(self, centre_um: float) -> float:
        if self.key not in FREE_WD_UM:
            raise GuardError(f"no free working distance recorded for {self.key!r}")
        top = _rules.sweep_ceiling(centre_um, self.window[1], FREE_WD_UM[self.key], WD_FRACTION)
        if top is None:  # only a lens released from the rule (Q4) has none; this axis asks for none
            raise GuardError(f"no sweep ceiling for {self.key!r}")
        return top

    def plan(self, centre_um: float, half_um: float, step_um: float) -> SweepPlan:
        c, h, s = plain(centre_um, "centre"), plain(half_um, "half"), plain(step_um, "step")
        if s <= 0 or h < 0:
            raise GuardError(f"step {s} must be > 0 and half range {h} >= 0")
        top = self.ceiling_um(c)
        lo, hi = max(self.window[0], c - h), min(top, c + h)
        if lo > hi:
            raise GuardError(f"sweep {c - h:.2f}..{c + h:.2f} um is outside "
                             f"{self.window[0]:.0f}..{top:.2f} um")
        n = int(math.floor((hi - lo) / s + 1e-9)) + 1
        return SweepPlan(self.key, c, h, s, top, [round(lo + i * s, 4) for i in range(n)])

    def _check_bench_ascent(self, z: float) -> None:
        """T-029d: every Z move goes through _send, so this covers approach, move_to, the
        sweeps and any other caller. The lens is read back, not taken from the caller."""
        here = self.position_um()
        if z <= here or (z <= here + self.tol and z <= RETURN_Z_UM):
            return  # down, or flat within the readback tolerance at or below 2800: allowed
        # above 2800 every upward step is checked, however small: steps under the tolerance
        # would otherwise add up past the ceiling (e.g. a 0.2 um fine sweep on the 100x)
        try:
            info = self.b.info()
        except Exception:  # noqa: BLE001 - unreadable info: is_bench counts it as the bench
            info = None
        try:
            key: str | None = registry_key(self.b.nosepiece())
        except Exception:  # noqa: BLE001 - an unreadable lens is not the 4x
            key = None
        why = bench_ascent_refusal(info, key, z)
        if why:
            raise GuardError(why)

    def _send(self, z: float, how: str, basis: dict | None = None) -> float:
        if not self.dry_run:
            self._check_bench_ascent(z)
        if self.dry_run:
            read, sent = z, False
            self._z_dry = z
        else:
            if not self.allow_motion:
                raise GuardError("FocusAxis was made with allow_motion=False")
            read, sent = self.b.move_z(z, token=GUARD_TOKEN), True
        rec = {"axis": "z", "how": how, "target_um": z, "read_um": read, "sent": sent,
               "tol_um": self.tol, "basis": {"tol_um": PROVISIONAL, **(basis or {})}}
        self.motions.append(rec)
        self.emit(Event("motion", self.op_id, rec))
        why = _rules.readback_ok(z, read, self.tol, "ZDrive")
        if why:
            raise GuardError(why)
        return read

    def move_to(self, z_um: float, allow_ascent_um: float = 0.0) -> float:
        z, up = plain(z_um, "z target"), plain(allow_ascent_um, "allowed ascent")
        why = (_rules.inside_window(z, self.window)
               or _rules.may_move_up(self.position_um(), z, up, self.tol))
        if why:
            raise GuardError(why)
        return self._send(z, "move_to")

    def park_at(self, z_um: float) -> float:
        z = plain(z_um, "park z")
        why = _rules.park_only_descends(self.position_um(), z, self.tol, RETRACT_Z_UM,
                                        self.window[1])
        if why:
            raise GuardError(why)
        return self._send(z, "park_at")

    def retract(self) -> dict:
        """Z to z_safe (Z_SAFE_UM, 0 um; unmeasured provisional): away from the sample, so
        no clearance check. Read back within the Z tolerance (a mismatch raises GuardError
        with the commanded and read values). Already at z_safe: no move, the readback is
        still recorded. Returns {commanded_um, readback_um, verified, moved, from_um}."""
        here = self.position_um()
        basis = {"z_safe_um": PROVISIONAL}
        if here <= Z_SAFE_UM + self.tol:
            rec = {"axis": "z", "how": "retract", "target_um": Z_SAFE_UM, "read_um": here,
                   "sent": False, "why": "already at z_safe",
                   "basis": {"tol_um": PROVISIONAL, **basis}}
            self.motions.append(rec)
            self.emit(Event("motion", self.op_id, rec))
            return {"commanded_um": Z_SAFE_UM, "readback_um": here, "verified": True,
                    "moved": False, "from_um": here}
        read = self._send(Z_SAFE_UM, "retract", basis)
        return {"commanded_um": Z_SAFE_UM, "readback_um": read, "verified": True,
                "moved": True, "from_um": here}

    def require_pfs_quiet(self, disable: bool = True) -> PfsState:
        s = self.b.pfs()
        if s.enabled and disable and not self.dry_run:
            if not self.allow_motion:
                raise GuardError("PFS is on and FocusAxis was made with allow_motion=False")
            rb = self.b.pfs_off(token=GUARD_TOKEN)
            self.emit(Event("property_set", self.op_id, asdict(rb)))
            s = self.b.pfs()
        if s.enabled and not self.dry_run:
            raise GuardError(f"PFS still enabled: {s}")
        return s

    def sweep(self, plan: SweepPlan, grab: Callable[[], Any], score: Callable | None = None,
              settle_s: float = 0.0) -> SweepResult:
        self._check_plan(plan)
        first, here = plan.z_um[0], self.position_um()
        if here < self.window[0] - self.tol:
            raise GuardError(f"Z {here:.2f} um is below the sample window; bring it up first")
        if here > first:
            self.park_at(first)
        else:
            self.move_to(first, allow_ascent_um=first - here)
        pts: list[SweepPoint] = []
        for i, z in enumerate(plan.z_um):
            read = self._send_step(z, plan.step_um) if i else self.position_um()
            if self.dry_run:
                pts.append(SweepPoint(z, read, None))
                continue
            self.sleep(settle_s)
            s, diag = _score(score, grab())
            pts.append(SweepPoint(z, read, s, diag))
        ok = [i for i, p in enumerate(pts) if p.score is not None and math.isfinite(p.score)]
        k = max(ok, key=lambda i: pts[i].score) if ok else None
        return SweepResult(plan, pts, k, None if k is None else pts[k].z_readback_um,
                           k is not None and 0 < k < len(pts) - 1,
                           k is not None and k == len(pts) - 1 and len(pts) > 1)

    def _simulated(self) -> bool:
        """Not the real stand, by the one shared rule `backend.is_bench` (T-015b). A failed
        info() read is passed on as None, which is_bench counts as the bench."""
        try:
            info = self.b.info()
        except Exception:  # noqa: BLE001 - an unreadable backend counts as the bench
            info = None
        return not is_bench(info)

    def _check_plan(self, plan: SweepPlan) -> None:
        """A plan is re-checked here, so a hand-built one cannot pass the ceiling."""
        z = [plain(v, "plan z") for v in plan.z_um]
        if plan.objective != self.key:
            raise GuardError(f"plan is for {plan.objective!r}, this axis is {self.key!r}")
        if not z:
            raise GuardError("empty sweep plan")
        top = self.ceiling_um(plain(plan.centre_um, "plan centre"))
        why = (_rules.plan_inside(z, self.window[0], top)
               or _rules.ascending(z, plain(plan.step_um, "plan step")))
        if why:
            raise GuardError(why)

    def _send_step(self, z: float, step: float) -> float:
        return self.move_to(z, allow_ascent_um=step)

    def approach(self, target_um: float, step_um: float | None = None,
                 clearance: Callable[[float], bool] | None = None) -> float:
        """Climb to `target_um` by the bench procedure: from below 2800 um one move to 2800,
        then steps of at most the objective's `approach_step_um` (a smaller `step_um` may
        be asked for, never a larger one). After every move the readback must match and
        rise, and `clearance(z_read)` must return True, or the approach stops with
        GuardError. On the bench (`backend.is_bench`) `clearance` is
        required. Above the target it descends straight there."""
        z = plain(target_um, "approach target")
        if not self.window[0] <= z <= self.window[1]:
            raise GuardError(f"approach target {z:.2f} um is outside the window {self.window}")
        top = approach_ceiling_um(self.key, self.window)
        if z > top:
            wd = FREE_WD_UM.get(self.key)
            raise GuardError(
                f"approach target {z:.2f} um is above {top:.0f} um for {self.key}: its free "
                f"working distance ({'unknown' if wd is None else f'{wd:.0f} um'}) does not "
                f"cover the {self.window[1] - RETURN_Z_UM:.0f} um above {RETURN_Z_UM:.0f}; "
                f"approach to {RETURN_Z_UM:.0f} and find focus with a sweep")
        if clearance is None and not self.dry_run and not self._simulated():
            raise GuardError("approach on a bench backend needs a clearance check "
                             "(clearance=callable(z_read) -> bool)")
        row, name = limits_for(self.key)
        asked = None if step_um is None else plain(step_um, "approach step")
        step = _rules.approach_step_allowed(asked, row.approach_step_um, self.tol, name)
        if isinstance(step, str):
            raise GuardError(f"{step} ({PROVISIONAL})")
        basis = {"approach_step_um": f"OBJECTIVE_LIMITS[{name}].approach_step_um, {PROVISIONAL}"}
        here = self.position_um()
        if here >= z:
            return self.move_to(z)

        def check(read: float, before: float) -> float:
            why = _rules.rise_ok(before, read)
            if why:
                raise GuardError(why)
            if clearance is not None and not clearance(read):
                raise GuardError(f"clearance check stopped the approach at {read:.3f} um")
            return read

        if here < RETURN_Z_UM - self.tol:
            here = check(self._send(RETURN_Z_UM, "approach_to_window", basis), here)
        for _ in range(int(math.ceil((z - here) / step)) + 1):
            if here >= z - self.tol:
                return here
            here = check(self._send(min(z, here + step), "approach", basis), here)
        if here >= z - self.tol:
            return here
        raise GuardError(f"approach to {z:.2f} um did not arrive (Z reads {here:.2f} um)")


def rotate_nosepiece(backend: Backend, focus: FocusAxis, state: int) -> str:
    """Turn the nosepiece: only with Z retracted, PFS off and out of range. Returns the label."""
    z = focus.position_um()
    basis = {"z_um": z, "retracted_max_um": RETRACTED_MAX_Z_UM,
             "basis": {"retracted_max_um": PROVISIONAL}}
    if not _rules.retracted(z, RETRACTED_MAX_Z_UM):
        raise GuardError(f"Z {z:.2f} um is not retracted (<= {RETRACTED_MAX_Z_UM})")
    if not focus.allow_motion and not focus.dry_run:
        raise GuardError("FocusAxis was made with allow_motion=False")
    s = focus.require_pfs_quiet(disable=True)
    if not focus.dry_run:
        # the whole rule, on the state read back after the PFS was switched off: an unknown
        # PFS state refuses here (D-01b; before, only an enabled one did)
        why = _rules.nosepiece_turn_allowed(z, RETRACTED_MAX_Z_UM, s.enabled, s.in_range)
        if why:
            raise GuardError(why)
    if focus.dry_run:
        focus.emit(Event("motion", focus.op_id, {"axis": "nosepiece", "target": state,
                                                 "sent": False, **basis}))
        return backend.nosepiece()
    rb = backend.set_nosepiece(int(state), token=GUARD_TOKEN)
    focus.emit(Event("motion", focus.op_id, {"axis": "nosepiece", "target": state,
                                             "sent": True, "read": rb.read, **basis}))
    if not rb.verified:
        raise GuardError(f"Nosepiece reads {rb.read}, not {state}")
    return backend.nosepiece()


def step_out_target(backend: Backend, x_um: float, y_um: float) -> tuple[float, float, dict]:
    """(x, y, basis) of the F5 step-out from (x_um, y_um): +ESCAPE_DY_UM in Y. Refused when
    the backend reports no Y travel or the target is outside it. The move itself still goes
    through XYAxis.goto (box, Z retracted for a long move, readback)."""
    x, y = plain(x_um, "x"), plain(y_um, "y")
    target = y + ESCAPE_DY_UM
    try:
        limits = backend.info().stage_limits.y_um
    except Exception as exc:  # noqa: BLE001 - no limits read means no step-out
        raise GuardError(f"stage Y limit unreadable ({type(exc).__name__}: {exc}); "
                         "refusing the step-out") from None
    if limits is None:
        raise GuardError("the backend reports no stage Y limit; refusing the step-out")
    lo, hi = limits
    if not lo <= target <= hi:
        raise GuardError(f"step-out to y {target:.0f} um is outside the stage Y travel "
                         f"{lo:.0f}..{hi:.0f} um")
    basis = {"escape_dy_um": ESCAPE_DY_UM, "basis": {"escape_dy_um": PROVISIONAL},
             "stage_y_um": [lo, hi]}
    return x, target, basis


# -- XY -----------------------------------------------------------------------------------
@dataclass
class XYBox:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @classmethod
    def around(cls, centre: tuple[float, float], half_um: float,
               margin_um: float = XY_BOX_MARGIN_UM) -> XYBox:
        r = half_um + margin_um
        return cls(centre[0] - r, centre[0] + r, centre[1] - r, centre[1] + r)

    def contains(self, x: float, y: float) -> bool:
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max


class XYAxis:
    """XY moves inside the box, read back. The long-move threshold is `long_xy_um` in
    `OBJECTIVE_LIMITS` for the objective read back at each move; the motion record names
    the table row."""

    def __init__(self, backend: Backend, box: XYBox, *, allow_motion: bool = False,
                 dry_run: bool = False, sink: EventSink = null_sink, op_id: str = "",
                 timeout_s: float | None = None, tol_um: float = XY_TOL_UM):
        self.b, self.box, self.allow_motion, self.dry_run = backend, box, allow_motion, dry_run
        self.emit, self.op_id, self.timeout, self.tol = sink, op_id, timeout_s, tol_um
        self.motions: list[dict] = []

    def long_move_um(self) -> tuple[float, str]:
        """(threshold, table row) for the objective in place now, read back."""
        try:
            label = self.b.nosepiece()
        except Exception:  # noqa: BLE001 - unreadable objective: the strictest row
            label = None
        row, name = limits_for(label)
        return row.long_xy_um, name

    def goto_rel(self, dx_um: float, dy_um: float) -> tuple[float, float]:
        """Relative move (edge_trace steps): readback + delta becomes an absolute target and
        goes through `goto`, so the box, the long-move rule and the readback check apply.
        The backend's own move_xy_rel is never called from here."""
        dx, dy = plain(dx_um, "dx"), plain(dy_um, "dy")
        p = self.b.positions()
        if p.x_um is None or p.y_um is None:
            raise GuardError(f"position unreadable before a relative XY move: {p.errors}")
        return self.goto(p.x_um + dx, p.y_um + dy)

    def goto(self, x_um: float, y_um: float) -> tuple[float, float]:
        x, y = plain(x_um, "x target"), plain(y_um, "y target")
        why = _rules.inside_box(x, y, (self.box.x_min, self.box.x_max, self.box.y_min,
                                       self.box.y_max))
        if why:
            raise GuardError(why)
        p = self.b.positions()
        if p.x_um is None or p.y_um is None or p.z_um is None:
            raise GuardError(f"position unreadable before an XY move: {p.errors}")
        long_um, row = self.long_move_um()
        basis = {"long_move_um": f"OBJECTIVE_LIMITS[{row}].long_xy_um, {PROVISIONAL}",
                 "tol_um": PROVISIONAL,
                 "retracted_max_um": PROVISIONAL}
        # not `_rules.needs_retract_before_xy` until D-04 names the lens kind (Q4): today
        # every lens, dry or immersion, is held to its table row
        if math.hypot(x - p.x_um, y - p.y_um) > long_um and p.z_um > RETRACTED_MAX_Z_UM:
            raise GuardError(f"XY move over {long_um:.0f} um ({row}) needs Z retracted; "
                             f"Z reads {p.z_um:.2f} um")
        if self.dry_run:
            read, sent = (x, y), False
        else:
            if not self.allow_motion:
                raise GuardError("XYAxis was made with allow_motion=False")
            read = self.b.move_xy(x, y, token=GUARD_TOKEN, timeout_s=self.timeout)
            sent = True
        rec = {"axis": "xy", "target_um": [x, y], "read_um": list(read), "sent": sent,
               "z_um": p.z_um, "long_move_um": long_um, "tol_um": self.tol, "basis": basis}
        self.motions.append(rec)
        self.emit(Event("motion", self.op_id, rec))
        why = _rules.xy_readback_ok((x, y), read, self.tol)
        if why:
            raise GuardError(why)
        return read


TRAP_TOL_UM = 0.05  # PROVISIONAL: a trap's readback against its target


class TrapAxis:
    """Tweezer trap moves and on/off (card T-20261002-2205 stage 3): inside the provisional
    trap range (`patterns.TRAP_RANGE_UM`), read back, recorded as a `motion` event. Real
    tweezers (`info().bench` not exactly False) are refused while the stand's bench-motion
    lock is on (`bench_lock`: the backend's `notes["bench_motion"]`, "LOCKED: ..." on
    mm-real), and refused when that state cannot be read."""

    def __init__(self, tweezers: Any, *, bench_lock: str | None, sink: EventSink = null_sink,
                 op_id: str = "", tol_um: float = TRAP_TOL_UM, record: bool = True):
        self.t, self.lock, self.tol = tweezers, bench_lock, tol_um
        self.emit, self.op_id = sink, op_id
        #: False (pattern runs): no motion event and no list entry per move, only the counts
        self.record = record
        self.motions: list[dict] = []
        self.moves = 0
        self.max_off_um = 0.0

    def allowed(self) -> None:
        """Raises when these tweezers may not move now (none, unreadable, real and locked)."""
        self._allowed()

    def _allowed(self) -> None:
        if self.t is None:
            raise GuardError("no tweezers on this backend")
        try:
            real = self.t.info().bench is not False
        except Exception as exc:  # noqa: BLE001 - unreadable tweezers count as real ones
            raise GuardError(f"tweezers info unreadable ({type(exc).__name__}: {exc})") from exc
        if real and not (self.lock or "").startswith("UNLOCKED"):
            raise GuardError(f"real tweezers stay still while bench motion is locked "
                             f"({self.lock or 'lock state not reported'})")

    def move(self, index: int, x_um: float, y_um: float, z_um: float = 0.0) -> dict:
        self._allowed()
        target = {"x": plain(x_um, "trap x"), "y": plain(y_um, "trap y"),
                  "z": plain(z_um, "trap z")}
        for axis, v in target.items():
            lo, hi = TRAP_RANGE_UM[axis]
            if not lo <= v <= hi:
                raise GuardError(f"trap {index} {axis} {v:g} um is outside {lo:g}..{hi:g} um "
                                 f"({PROVISIONAL} trap range)")
        read = self.t.move_trap(int(index), target["x"], target["y"], target["z"],
                                token=GUARD_TOKEN)
        rec = {"axis": "trap", "trap": int(index), "sent": True,
               "target_um": [target["x"], target["y"], target["z"]],
               "read_um": [read.x_um, read.y_um, read.z_um], "tol_um": self.tol,
               "basis": {"range": f"patterns.TRAP_RANGE_UM, {PROVISIONAL}",
                         "tol_um": PROVISIONAL}}
        off = max(abs(r - t) for r, t in zip(rec["read_um"], rec["target_um"], strict=True))
        self.moves += 1
        self.max_off_um = max(self.max_off_um, off)
        if self.record:
            self.motions.append(rec)
            self.emit(Event("motion", self.op_id, rec))
        if off > self.tol:
            raise GuardError(f"trap {index} commanded {rec['target_um']}, read "
                             f"{rec['read_um']} um")
        return rec

    def set_on(self, index: int, on: bool) -> dict:
        self._allowed()
        read = self.t.set_trap(int(index), bool(on), token=GUARD_TOKEN)
        rec = {"axis": "trap", "trap": int(index), "sent": True, "on": bool(on),
               "read_on": read.on}
        self.motions.append(rec)
        self.emit(Event("motion", self.op_id, rec))
        if read.on is not bool(on):
            raise GuardError(f"trap {index} commanded {'on' if on else 'off'}, reads "
                             f"{'on' if read.on else 'off'}")
        return rec


PIEZO_TOL_UM = 0.05  # PROVISIONAL: a piezo axis's readback against its target


class PiezoAxis:
    """XYZ piezo moves for patterns (card T-20261002-2205 stage 4): inside the device's
    travel, read back. A real piezo (`info().bench` not exactly False) is always refused:
    piezo writes stay locked until M5 (operations-spec 9.2), whatever the bench-motion lock
    says. Per-move events are off by default (`record=False`): a pattern run reports progress
    and a summary instead of thousands of motion events."""

    def __init__(self, piezo: Any, *, sink: EventSink = null_sink, op_id: str = "",
                 tol_um: float = PIEZO_TOL_UM, record: bool = False):
        self.p, self.tol, self.record = piezo, tol_um, record
        self.emit, self.op_id = sink, op_id
        self.max_off_um = 0.0
        self.moves = 0

    def allowed(self) -> dict[str, tuple[float, float]]:
        """The travel per axis; raises when this piezo may not move."""
        if self.p is None:
            raise GuardError("no movable piezo on this setup (the stand's piezo is read only "
                             "until M5)")
        try:
            info = self.p.info()
        except Exception as exc:  # noqa: BLE001 - unreadable: treated as the real piezo
            raise GuardError(f"piezo info unreadable ({type(exc).__name__}: {exc})") from exc
        if info.bench is not False:
            raise GuardError("the real piezo is read only until M5 (operations-spec 9.2)")
        return dict(info.travel_um)

    def move(self, x_um: float, y_um: float, z_um: float) -> tuple[float, float, float]:
        travel = self.allowed()
        target = {"x": plain(x_um, "piezo x"), "y": plain(y_um, "piezo y"),
                  "z": plain(z_um, "piezo z")}
        for axis, v in target.items():
            lo, hi = travel[axis]
            if not lo <= v <= hi:
                raise GuardError(f"piezo {axis} {v:g} um is outside its travel {lo:g}..{hi:g} um")
        read = self.p.move(target["x"], target["y"], target["z"], token=GUARD_TOKEN)
        got = (read.x_um, read.y_um, read.z_um)
        off = max(abs(r - t) for r, t in zip(got, target.values(), strict=True))
        self.moves += 1
        self.max_off_um = max(self.max_off_um, off)
        if self.record:
            self.emit(Event("motion", self.op_id, {"axis": "piezo", "sent": True,
                                                  "target_um": list(target.values()),
                                                  "read_um": list(got), "tol_um": self.tol}))
        if off > self.tol:
            raise GuardError(f"piezo commanded {list(target.values())}, read {list(got)} um")
        return got


# -- scopes -------------------------------------------------------------------------------
_OWNER = threading.Lock()


@contextmanager
def exclusive(backend: Backend, sink: EventSink = null_sink) -> Iterator[BackendInfo]:
    """Open the backend as its only owner in this process; lights off and close on exit."""
    if not _OWNER.acquire(blocking=False):
        raise GuardError("another engine already owns the microscope")
    try:
        info = backend.open()
        try:
            yield info
        finally:
            sink(Event("light_changed", "", lights_off(backend)))
            backend.close()
    finally:
        _OWNER.release()


def lights_off(backend: Backend) -> dict:
    """Aura and DiaLamp off with readback. Never raises: the result says what happened."""
    try:
        rbs = backend.all_off()
        ok = bool(rbs) and all(r.verified for r in rbs)  # an empty readback proves nothing
        return {"readbacks": [asdict(r) for r in rbs], "verified": ok,
                "error": None}
    except Exception as exc:  # noqa: BLE001 - recorded, and the caller's own error goes on
        return {"readbacks": [], "verified": False, "error": f"{type(exc).__name__}: {exc}"}


def snapshot(backend: Backend) -> dict:
    out: dict = {}
    for key, read in (("positions", lambda: asdict(backend.positions())),
                      ("lights", backend.light_state), ("objective", backend.nosepiece)):
        try:
            out[key] = read()
        except Exception as exc:  # noqa: BLE001 - a state read must not stop the record
            out[key] = f"unreadable: {type(exc).__name__}: {exc}"
    return out


def check_lights(readbacks: list[Readback], emit: EventSink = null_sink,
                 op_id: str = "") -> list[Readback]:
    """Emit `light_changed` with the readbacks; raise GuardError if any does not verify or
    there is none (an empty readback proves nothing)."""
    emit(Event("light_changed", op_id, {"readbacks": [asdict(r) for r in readbacks]}))
    bad = [f"{r.device}.{r.prop} wanted {r.wanted}, read {r.read}" for r in readbacks
           if not r.verified]
    if not readbacks:
        bad = ["the backend returned no readback"]
    if bad:
        raise GuardError("light not verified: " + "; ".join(bad))
    return readbacks


def lamp_on(backend: Backend, emit: EventSink = null_sink, op_id: str = "") -> list[Readback]:
    """Transmitted lamp on with the guard token (D15), read back and recorded. For
    operations run by the runner, which owns the exit path that switches it off again."""
    return check_lights(backend.lamp_on(token=GUARD_TOKEN), emit, op_id)


def aura_line_on(backend: Backend, line: str, percent: float, emit: EventSink = null_sink,
                 op_id: str = "") -> list[Readback]:
    """One Aura line on at `percent` with the guard token, read back and recorded."""
    pct = plain(percent, "Aura percent")
    if not 0.0 < pct <= 100.0:
        raise GuardError(f"Aura percent {pct} is outside (0, 100]")
    return check_lights(backend.aura_line_on(str(line), pct, token=GUARD_TOKEN), emit, op_id)


@dataclass
class OpScope:
    """`answers` receives `confirm` Commands from whoever dispatches commands (the UI)."""

    op_id: str
    record: OpRecord
    emit: EventSink
    result: Any = None
    answers: queue.Queue = field(default_factory=queue.Queue)
    backend: Backend | None = None

    def lamp_on(self) -> list[Readback]:
        """Transmitted lamp on: the one legal way for an operation (D15). Off is the scope's
        exit path, or `backend.lamp_off()` / `all_off()`, which need no token."""
        return lamp_on(self._backend(), self.emit, self.op_id)

    def aura_line_on(self, line: str, percent: float) -> list[Readback]:
        """One Aura line on at `percent` (the backend converts to per-mille); lamp off first."""
        return aura_line_on(self._backend(), line, percent, self.emit, self.op_id)

    def _backend(self) -> Backend:
        if self.backend is None:
            raise GuardError("this scope has no backend (made outside operation())")
        return self.backend

    def lights(self, readbacks: list[Readback]) -> list[Readback]:
        """Record a light change; any readback that does not verify stops the operation."""
        return check_lights(readbacks, self.emit, self.op_id)

    def ask(self, key: str, text: str, timeout_s: float | None = None, **data: Any) -> bool:
        """A manual step: emit `confirm_required`, wait for the matching confirm, record it.
        No answer within `timeout_s` aborts the operation."""
        self.emit(Event("confirm_required", self.op_id, {"key": key, "text": text, **data}))
        while True:
            try:
                cmd = self.answers.get(timeout=timeout_s)
            except queue.Empty:
                raise OperationAborted(f"no answer to {key!r} within {timeout_s} s") from None
            if cmd.kind == "abort":
                raise OperationAborted(f"aborted while waiting for {key!r}")
            if cmd.kind == "confirm" and cmd.args.get("key") == key:
                ok = bool(cmd.args.get("ok"))
                self.emit(Event("confirmed", self.op_id, {"key": key, "ok": ok,
                                                          "origin": cmd.origin}))
                return ok


def _emit_safely(ev: Event, rec: OpRecord, sink: EventSink, error: str | None) -> str | None:
    """Emit to the record and the external sink; a failure in either is noted in `error`
    instead of replacing the operation's own exception."""
    for name, target in (("record writer", rec.sink), ("event sink", sink)):
        try:
            target(ev)
        except Exception as exc:  # noqa: BLE001 - the operation's own error comes first
            note = f"{name} failed on {ev.kind}: {type(exc).__name__}: {exc}"
            error = note if error is None else f"{error}; {note}"
    return error


@contextmanager
def operation(backend: Backend, parent: Path, op: str, sink: EventSink = null_sink,
              args: dict | None = None, prefix: str | None = None,
              user_id: str | None = None, session_id: str | None = None) -> Iterator[OpScope]:
    """One operation's record folder, events, and lights-off on every exit path.

    Enter it before switching any light on, and switch lights on only through
    `scope.lamp_on()` / `scope.aura_line_on(line, percent)`, which pass the guard token.
    Set `scope.result` inside the block; it lands in summary.json. `prefix` names the
    folder (`scan4x` keeps the 2026-09-30 `scan4x_<stamp>/` layout).

    `lights_off()` itself needs no ownership: a pre-emptive lights-off command may call it
    while another operation holds the backend (the runner aborts that operation)."""
    rec = OpRecord(parent, op, start_state=snapshot(backend), prefix=prefix,
                   user_id=user_id, session_id=session_id)
    scope = OpScope(rec.op_id, rec, fan_out(rec.sink, sink), backend=backend)
    scope.emit(Event("started", rec.op_id, {"op": op, "args": args or {}, "user_id": user_id,
                                            "session_id": session_id}))
    status, error = "finished", None
    try:
        yield scope
    except (OperationAborted, KeyboardInterrupt) as exc:
        status, error = "aborted", f"{type(exc).__name__}: {exc}"
        raise
    except BaseException as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"
        error = _emit_safely(Event("error", rec.op_id, {"error": error}), rec, sink, error)
        raise
    finally:
        lights = lights_off(backend)
        end = snapshot(backend)
        closing = [Event("light_changed", rec.op_id, lights)]
        if status != "error":
            data = {"error": error}
            if status == "finished":
                data["summary"] = scope.result  # the screens read finished.data.summary
            closing.append(Event(status, rec.op_id, data))
        for ev in closing:
            error = _emit_safely(ev, rec, sink, error)
        rec.finish(status, lights=lights, end_state=end, result=scope.result, error=error)
