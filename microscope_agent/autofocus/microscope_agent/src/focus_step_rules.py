# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/src/focus_step_rules.py
# body-sha256: 68adadc8094da4406f00230528cc138f7680beb58f71a59d101035ab09264540
"""The step rules of the focus drive, the XY stage and the PFS as pure functions (D-01).

These are the comparisons dino-autofocus's engine guards make
before and after every move, with every limit as an argument and no number of its own:
the Z window, the retract and return heights, the readback tolerances, the per-lens free
working distances, long-move thresholds and approach steps all come from the caller. In
this repository the guards hold them (unmeasured provisional); in soft-matter-agents the
envelope the person writes and the plan the person approves hold them, and the operator or
the orchestrator calls these functions at the moment of comparison.

A rule returns ``None`` when the move is allowed and a sentence saying why when it is not;
nothing here moves anything, reads anything or holds state. Ambiguity refuses: an unknown
PFS state, an unknown lens and a model-graded number are all refusals, never defaults.

The rules, as the bench runs them (the 2026-09-30 substrate-scan run note; PLAN section 5):

- Z targets stay inside the sample window; below it only a park (descend only) may go.
- A move up is refused unless the caller allows that much ascent; sweeps are planned
  ascending in steps of at most the plan step and climb one step at a time.
- Every move is read back; off by more than the tolerance stops the operation.
- Coming back from a retract, Z does not jump to the target: one move to the window's
  return height, then steps of at most the lens's approach step, each one read back,
  rising, and passing the caller's clearance check.
- A sweep's ceiling is the window top or centre + fraction x free working distance,
  whichever is lower; a lens released from the immersion rule (Q4: dry lenses) has no lens
  ceiling and the window top binds; a lens with no known working distance gets no plan.
- An XY move longer than the lens's long-move threshold needs Z retracted first, unless the
  lens is released from that rule (dry); an unknown lens gets the strictest row.
- The nosepiece turns only with Z retracted, the PFS off and out of range.
- A model-graded value drives no motion.

Flat file in the soft-matter-agents layout (integration-sma.md section 9): stdlib only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

EPS = 1e-6  # float slack on step and ceiling comparisons; not a tolerance of any device

GRADE_MODEL = "model"


def _num(v: object, what: str) -> float:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what}: {v!r} is not a number") from exc
    if not math.isfinite(f):
        raise ValueError(f"{what}: {f} is not a finite number")
    return f


# -- values ------------------------------------------------------------------------------------

def refuse_model_graded(grade: str | None, what: str, source: str | None = None) -> str | None:
    """A number a model produced may not drive motion (soft-matter-agents: E6 enters nothing)."""
    if grade == GRADE_MODEL:
        return f"{what}: a model output cannot drive motion" + (f" ({source})" if source else "")
    return None


def strictest_for_unknown_lens(rows: Mapping[str, tuple[float, float]]) -> tuple[float, float]:
    """The row an unreadable or unlisted lens gets: any XY move needs Z retracted
    (threshold 0) and the smallest approach step in the table. `rows`: key -> (long_xy_um,
    approach_step_um). An empty table has no strictest row."""
    if not rows:
        raise ValueError("no lens rows: nothing to be strict about")
    return 0.0, min(_num(step, f"{k} approach step") for k, (_, step) in rows.items())


# -- Z ----------------------------------------------------------------------------------------

def inside_window(z_um: float, window: tuple[float, float]) -> str | None:
    z, lo, hi = _num(z_um, "z"), _num(window[0], "window low"), _num(window[1], "window high")
    if not lo <= z <= hi:
        return f"z {z:.2f} um is outside the window {lo:.0f}..{hi:.0f} um"
    return None


def readback_ok(commanded_um: float, read_um: float, tol_um: float, axis: str = "Z") -> str | None:
    """A move is verified only by its readback, within the caller's tolerance."""
    c, r, t = _num(commanded_um, "commanded"), _num(read_um, "read"), _num(tol_um, "tolerance")
    if abs(r - c) > t:
        return f"{axis} commanded {c:.3f}, read {r:.3f} um (tolerance {t} um)"
    return None


def may_move_up(here_um: float, target_um: float, allowed_ascent_um: float,
                tol_um: float) -> str | None:
    """`move_to`: descents are always allowed; a rise needs the caller's permission for that
    much ascent (the readback tolerance absorbs a flat move)."""
    here, z = _num(here_um, "here"), _num(target_um, "target")
    up, t = _num(allowed_ascent_um, "allowed ascent"), _num(tol_um, "tolerance")
    rise = z - here
    if rise > up + t:
        return f"move up by {rise:.2f} um; only {up:.2f} um allowed"
    return None


def park_only_descends(here_um: float, target_um: float, tol_um: float, retract_um: float,
                       window_top_um: float) -> str | None:
    """`park_at`: between the retract height and the window top, and never upward."""
    here, z, t = _num(here_um, "here"), _num(target_um, "park z"), _num(tol_um, "tolerance")
    lo, hi = _num(retract_um, "retract"), _num(window_top_um, "window top")
    if z < lo or z > hi:
        return f"park z {z:.2f} um outside {lo:g}..{hi:g} um"
    if z > here + t:
        return "park_at only descends"
    return None


def ascending(z_um: Sequence[float], step_um: float) -> str | None:
    """A sweep plan climbs one step at a time: strictly increasing, no gap over the step."""
    z = [_num(v, "plan z") for v in z_um]
    s = _num(step_um, "plan step")
    if not z:
        return "empty sweep plan"
    if s <= 0:
        return f"plan step {s} must be > 0"
    for a, b in zip(z, z[1:], strict=False):
        if not 0 < b - a <= s + EPS:
            return f"plan z is not ascending in steps of at most {s} um ({a} -> {b})"
    return None


def plan_inside(z_um: Sequence[float], window_low_um: float, ceiling_um: float) -> str | None:
    """The whole plan lies between the window floor and the lens ceiling."""
    z = [_num(v, "plan z") for v in z_um]
    if not z:
        return "empty sweep plan"
    lo, top = _num(window_low_um, "window low"), _num(ceiling_um, "ceiling")
    if z[0] < lo or z[-1] > top + EPS:
        return f"plan {z[0]:.2f}..{z[-1]:.2f} um leaves {lo:.0f}..{top:.2f} um"
    return None


def sweep_ceiling(centre_um: float, window_top_um: float, free_wd_um: float | None,
                  wd_fraction: float, *, released: bool = False) -> float | None:
    """Highest Z a sweep around `centre_um` may reach. `released` (Q4: a dry lens the person
    released from the immersion rule): no lens ceiling, the window top binds -- returned as
    None so the caller sees that no lens number took part. Otherwise min(window top, centre +
    fraction x free working distance); a lens with no known working distance gets no plan."""
    if released:
        return None
    if free_wd_um is None:
        raise ValueError("no free working distance recorded for this lens: no sweep plan")
    c, top = _num(centre_um, "centre"), _num(window_top_um, "window top")
    wd, f = _num(free_wd_um, "free working distance"), _num(wd_fraction, "wd fraction")
    return min(top, c + f * wd)


def approach_ceiling(return_um: float, window_top_um: float,
                     free_wd_um: float | None) -> float:
    """Highest target an image-less approach may climb to: the window top only for a lens
    whose free working distance covers the whole window above the return height; every
    other lens, and an unknown one, stops at the return height (refused, never clamped)."""
    ret, top = _num(return_um, "return height"), _num(window_top_um, "window top")
    if free_wd_um is None:
        return ret
    return top if _num(free_wd_um, "free working distance") >= top - ret else ret


def approach_step_allowed(asked_um: float | None, row_step_um: float, tol_um: float,
                          row_name: str = "the lens row") -> float | str:
    """The step an approach may use: the lens row's step, or a smaller one the caller asks
    for, and always more than the readback tolerance. Returns the step or the refusal."""
    step, t = _num(row_step_um, "row approach step"), _num(tol_um, "tolerance")
    if asked_um is not None:
        asked = _num(asked_um, "approach step")
        if asked > step:
            return f"approach step {asked} um is larger than {row_name}'s {step} um"
        step = asked
    if step <= t:
        return f"approach step {step} um must exceed the readback tolerance {t} um"
    return step


def approach_steps(here_um: float, target_um: float, step_um: float, return_um: float,
                   tol_um: float) -> list[float]:
    """The Z targets of the bench approach, in order: from below the return height one move
    to it, then steps of at most `step_um` up to the target. Above the target: straight
    down to it (one move). Already there (within the tolerance): nothing."""
    here, z = _num(here_um, "here"), _num(target_um, "target")
    s, ret, t = _num(step_um, "step"), _num(return_um, "return height"), _num(tol_um, "tolerance")
    if s <= 0:
        raise ValueError(f"step {s} must be > 0")
    if here >= z:
        return [] if here - z <= t else [z]
    out: list[float] = []
    if here < ret - t and ret <= z:
        out.append(ret)
        here = ret
    while here < z - t:
        here = min(z, here + s)
        out.append(here)
    return out


def rise_ok(before_um: float, read_um: float) -> str | None:
    """After an approach step Z must have risen; a readback at or below the last one stops."""
    b, r = _num(before_um, "before"), _num(read_um, "read")
    if r <= b:
        return f"Z did not rise: read {r:.3f} um after {b:.3f} um"
    return None


def retracted(z_um: float, retracted_max_um: float) -> bool:
    """Z counts as retracted at or below the caller's retracted height."""
    return _num(z_um, "z") <= _num(retracted_max_um, "retracted max")


# -- PFS ---------------------------------------------------------------------------------------

def pfs_quiet(enabled: bool | None) -> str | None:
    """The focus servo must be off before Z moves; an unknown state is not off."""
    if enabled is None:
        return "PFS state unknown: not treated as off"
    if enabled:
        return "PFS is enabled"
    return None


def pfs_out_of_range(in_range_text: str | None) -> bool:
    """The device's own range text says it lost the surface (needed before a turret turn)."""
    return in_range_text is not None and "out" in in_range_text.lower()


def nosepiece_turn_allowed(z_um: float, retracted_max_um: float, pfs_enabled: bool | None,
                           pfs_in_range_text: str | None) -> str | None:
    """The turret turns only with Z retracted, the PFS off and out of range."""
    z, top = _num(z_um, "z"), _num(retracted_max_um, "retracted max")
    if z > top:
        return f"Z {z:.2f} um is not retracted (<= {top:g})"
    why = pfs_quiet(pfs_enabled)
    if why:
        return why
    if not pfs_out_of_range(pfs_in_range_text):
        return f"PFS reads {pfs_in_range_text!r} after retract; refusing to rotate"
    return None


# -- XY ----------------------------------------------------------------------------------------

def inside_box(x_um: float, y_um: float, box: tuple[float, float, float, float]) -> str | None:
    """`box` = (x_min, x_max, y_min, y_max)."""
    x, y = _num(x_um, "x"), _num(y_um, "y")
    x0, x1, y0, y1 = (_num(v, "box") for v in box)
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return f"XY ({x:.0f}, {y:.0f}) is outside the box {box}"
    return None


def xy_readback_ok(commanded: tuple[float, float], read: tuple[float, float],
                   tol_um: float) -> str | None:
    cx, cy = _num(commanded[0], "x"), _num(commanded[1], "y")
    rx, ry = _num(read[0], "read x"), _num(read[1], "read y")
    if math.hypot(rx - cx, ry - cy) > _num(tol_um, "tolerance"):
        return f"XY commanded ({cx:.1f}, {cy:.1f}), read ({rx:.1f}, {ry:.1f}) um"
    return None


def needs_retract_before_xy(distance_um: float, long_xy_um: float, z_um: float,
                            retracted_max_um: float, *, immersion: bool | None) -> str | None:
    """A move longer than the lens's long-move threshold with Z up is refused -- for an
    immersion lens, and for a lens whose kind is unknown (None: ambiguity refuses). A dry
    lens released from the rule (Q4) moves at sample height."""
    d, long_um = _num(distance_um, "distance"), _num(long_xy_um, "long move threshold")
    z, top = _num(z_um, "z"), _num(retracted_max_um, "retracted max")
    if immersion is False:
        return None
    if d > long_um and z > top:
        who = "an immersion lens" if immersion else "a lens of unknown kind"
        return (f"XY move of {d:.0f} um exceeds {long_um:.0f} um on {who} and needs Z "
                f"retracted; Z reads {z:.2f} um")
    return None
