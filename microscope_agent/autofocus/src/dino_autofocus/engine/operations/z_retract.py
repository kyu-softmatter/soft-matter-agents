"""`z_retract{}`: ZDrive to z_safe (0 um), the first engine motion on the stand (T-039).

Runbook step 2a (docs/runbooks/first-bench-motion.md): away from the sample, the safest
direction, so it tests the lock lift, the readback and the records before any XY move.

- Moves through `FocusAxis.retract()` (engine/guards.py): descend only, read back within the
  guards' Z tolerance; a mismatch fails the operation with the commanded and read values.
  Already at z_safe: succeeds with no move and records the readback.
- PFS first, as the F5 order, scripts/change_objective.py and objective_change do: driving
  ZDrive while PFS is engaged fights the focus lock (PFS was on in the 2026-09-30 session).
  Preflight refuses an unreadable PFS; the run switches PFS off (`require_pfs_quiet`,
  disable only, never enable) before the move and records the PFS state after it.
- Refuses only what every motion refuses: the T-036 lock (mm-real reports
  `notes["bench_motion"]` as "LOCKED: ..." and its move_z raises as well) and rule 12
  (control plus an open session; the runner's permission table, motion class by default).
  No clearance callback is needed: it moves away from the sample.
- `motion = False` in the runner's sense: it is not refused while a sample awaits return,
  since retracting is always the safe move.
- Lights: nothing is switched; the runner's exit path keeps its own rule (T-011e).
"""

from __future__ import annotations

from ..events import Event
from ..guards import Z_SAFE_UM, FocusAxis
from ..runner import Operation, register_operation

NAME = "z_retract"


def lock_state(backend) -> str | None:
    """The backend's reported bench-motion lock ("LOCKED: ..." / "UNLOCKED"), or None if it
    reports none (simulated backends)."""
    try:
        notes = backend.info().notes or {}
    except Exception as exc:  # noqa: BLE001 - an unreadable info reads as locked
        return f"LOCKED: backend info unreadable ({type(exc).__name__}: {exc})"
    state = notes.get("bench_motion")
    return None if state is None else str(state)


def preflight_checks(backend, args: dict) -> list[dict]:
    checks = []

    def check(name: str, ok: bool, want: str, read, why: str = "") -> None:
        checks.append({"name": name, "ok": ok, "want": want, "read": read, "why": why})

    extra = sorted(args)
    check("args", not extra, "no arguments", extra, f"unknown arguments: {extra}" if extra else "")
    state = lock_state(backend)
    locked = state is not None and not state.startswith("UNLOCKED")
    check("bench_motion", not locked, "UNLOCKED or not reported", state,
          f"bench motion is locked ({state})" if locked else "")
    try:
        z = backend.positions().z_um
    except Exception as exc:  # noqa: BLE001
        z, err = None, f"{type(exc).__name__}: {exc}"
    else:
        err = "ZDrive position unreadable" if z is None else ""
    check("z_drive", z is not None, "a readable ZDrive position", z, err)
    try:
        pfs = backend.pfs()
        read, err = {"enabled": pfs.enabled, "in_range": pfs.in_range}, ""
    except Exception as exc:  # noqa: BLE001 - an unknown PFS state is not safe to drive
        read, err = None, f"PFS state unreadable ({type(exc).__name__}: {exc})"
    check("pfs", read is not None, "a readable PFS state (switched off before the move)",
          read, err)
    return checks


@register_operation
class ZRetract(Operation):
    """`start("z_retract", {})`. Motion class for rule 12 (control + open session)."""

    name = NAME
    motion = False  # always allowed, also while a sample awaits return

    def plan(self) -> dict:
        return {"op": NAME, "text": f"ZDrive to {Z_SAFE_UM:g} um (z_safe, unmeasured "
                                    "provisional), away from the sample. Nothing else moves."}

    def preflight(self) -> list[dict]:
        return preflight_checks(self.ctx.backend, dict(self.args))

    def run(self) -> dict:
        ctx = self.ctx

        def emit(ev: Event) -> None:
            ctx.emit(ev.kind, **ev.data)

        axis = FocusAxis(ctx.backend, None, allow_motion=True, sink=emit, op_id=ctx.op_id)
        before = ctx.backend.pfs()  # as found, before anything is switched
        axis.require_pfs_quiet(disable=True)  # PFS off first; raises if it stays on
        result = axis.retract()  # a readback mismatch raises GuardError
        after = ctx.backend.pfs()
        return {"op": NAME, **result,
                "pfs": {"enabled_before": before.enabled, "in_range_before": before.in_range,
                        "enabled": after.enabled, "in_range": after.in_range}}
