"""`trap_move{trap, x_um, y_um, z_um?}` and `trap_set{trap, on}`: optical tweezer traps (card
T-20261002-2205 stage 3).

- Positions as in `engine/patterns.py`: um in the sample plane from the centre of the camera
  field (x right, y down as on the image, orientation provisional); z is the trap's focus
  offset. The provisional trap range is checked in preflight and again by `guards.TrapAxis`,
  which reads the move back and records it as a `motion` event.
- Motion class for rule 12 (the operator's control and an open experiment session), like
  every stage move. Real tweezers (Tweez300) stay still while the stand's bench-motion lock is
  on; only the mock tweezers move today.
- Not `snaps`: the live stream keeps running, so the trap is seen moving.
"""

from __future__ import annotations

from ..events import Event
from ..guards import TrapAxis
from ..patterns import TRAP_RANGE_UM
from ..runner import Operation, register_operation
from .z_retract import lock_state


def _checks(ctx, args: dict, keys: dict[str, type]) -> list[dict]:
    checks = []

    def check(name: str, ok: bool, want: str, read, why: str = "") -> None:
        checks.append({"name": name, "ok": ok, "want": want, "read": read, "why": why})

    extra = sorted(set(args) - set(keys))
    check("args", not extra, f"only {sorted(keys)}", extra,
          f"unknown arguments: {extra}" if extra else "")
    tw = ctx.tweezers
    check("tweezers", tw is not None, "tweezers on this setup", None if tw is None else "present",
          "" if tw is not None else "no tweezers on this setup")
    n = 0
    if tw is not None:
        try:
            n = tw.info().n_traps
        except Exception as exc:  # noqa: BLE001
            check("tweezers_info", False, "readable tweezers", None, f"{type(exc).__name__}: {exc}")
    trap = args.get("trap")
    ok = isinstance(trap, int) and not isinstance(trap, bool) and 0 <= trap < max(n, 1)
    check("trap", ok, f"a trap number 0..{max(n - 1, 0)}", trap, "" if ok else "no such trap")
    for axis in ("x", "y", "z"):
        key = f"{axis}_um"
        if key not in keys:
            continue
        if axis != "z" and key not in args:  # z is optional (0); x and y are not
            check(key, False, "a number", None, f"{key} is missing")
            continue
        v = args.get(key, 0.0)
        lo, hi = TRAP_RANGE_UM[axis]
        good = isinstance(v, int | float) and not isinstance(v, bool) and lo <= v <= hi
        check(key, good, f"{lo:g}..{hi:g} um (provisional trap range)", v,
              "" if good else f"{key} {v!r} is outside {lo:g}..{hi:g} um or not a number")
    return checks


class _TrapOp(Operation):
    def _axis(self) -> TrapAxis:
        ctx = self.ctx

        def emit(ev: Event) -> None:
            ctx.emit(ev.kind, **ev.data)

        return TrapAxis(ctx.tweezers, bench_lock=lock_state(ctx.backend), sink=emit,
                        op_id=ctx.op_id)


@register_operation
class TrapMove(_TrapOp):
    """`start("trap_move", {"trap": 0, "x_um": 3.0, "y_um": -2.0, "z_um": 0.0})`."""

    name = "trap_move"
    KEYS = {"trap": int, "x_um": float, "y_um": float, "z_um": float}

    def plan(self) -> dict:
        a = self.args
        return {"op": self.name, "text": f"Trap {a.get('trap')} to x {a.get('x_um')}, "
                                         f"y {a.get('y_um')}, z {a.get('z_um', 0.0)} um "
                                         "(from the field centre). Nothing else moves."}

    def preflight(self) -> list[dict]:
        return _checks(self.ctx, dict(self.args), self.KEYS)

    def run(self) -> dict:
        a = self.args
        rec = self._axis().move(a["trap"], a["x_um"], a["y_um"], a.get("z_um", 0.0))
        return {"op": self.name, **rec}


@register_operation
class TrapSet(_TrapOp):
    """`start("trap_set", {"trap": 0, "on": true})`."""

    name = "trap_set"
    KEYS = {"trap": int, "on": bool}

    def plan(self) -> dict:
        a = self.args
        return {"op": self.name, "text": f"Trap {a.get('trap')} {'on' if a.get('on') else 'off'}."}

    def preflight(self) -> list[dict]:
        checks = _checks(self.ctx, dict(self.args), self.KEYS)
        on = self.args.get("on")
        checks.append({"name": "on", "ok": isinstance(on, bool), "want": "true or false",
                       "read": on, "why": "" if isinstance(on, bool) else "on must be true/false"})
        return checks

    def run(self) -> dict:
        rec = self._axis().set_on(self.args["trap"], self.args["on"])
        return {"op": self.name, **rec}
