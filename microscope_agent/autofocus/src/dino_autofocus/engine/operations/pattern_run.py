"""`pattern_run{pattern_id, repeats?, rate_hz?, return_to_start?}`: run a saved motion pattern on
the XYZ piezo and the tweezer traps (card T-20261002-2205 stage 4).

- The pattern is read from the server's pattern folder (`Runner.patterns`, `engine/patterns.py`)
  when the operation starts; the plan and the summary carry its sha256, so the record says
  exactly what ran.
- Every tick (`rate_hz`, default 20, at most 50) every track's position at that time is sent:
  piezo targets are the start position plus the track's offsets, through `guards.PiezoAxis`;
  trap targets are field positions, through `guards.TrapAxis`. Both read back. Per-move events
  are off; progress every 0.5 s carries the pattern time and where every target is, so the live
  view's overlay can follow the run.
- Time runs `repeats` times over the pattern (default 1, at most 100; at most 2 h in all). At the
  end the last points are sent, then the piezo goes back to where it started
  (`return_to_start`, default true). An abort stops at once: nothing more moves, not even the
  return.
- No ramp yet: the first tick goes straight to the track's first point and each repeat jumps
  from the end back to the start. Fine for the mock piezo; a ramp or a step limit is needed
  before any real piezo (M5).
- Refused by preflight, before anything moves: a missing pattern, a piezo track without a piezo
  that may move (the stand's piezo is read only until M5), a trap track without tweezers or with
  a trap the tweezers do not have, real tweezers while the bench-motion lock is on, and a piezo
  track that would leave the piezo's travel from where it is now.
- Motion class for rule 12 (the operator's control and an open experiment session). Not
  `snaps`: the live stream keeps running, so the run is seen.
"""

from __future__ import annotations

import hashlib
import json
import time

from ..guards import PiezoAxis, TrapAxis
from ..patterns import MAX_DURATION_S
from ..runner import Operation, register_operation
from .z_retract import lock_state

NAME = "pattern_run"
KEYS = {"pattern_id", "repeats", "rate_hz", "return_to_start"}
MAX_REPEATS = 100
MAX_RATE_HZ = 50.0
MAX_TOTAL_S = 2 * MAX_DURATION_S
PROGRESS_EVERY_S = 0.5


def _sha(pattern) -> str:
    return hashlib.sha256(json.dumps(pattern.to_dict(), sort_keys=True).encode()).hexdigest()


@register_operation
class PatternRun(Operation):
    """`start("pattern_run", {"pattern_id": "helix-1", "repeats": 2})`."""

    name = NAME

    # -- arguments ----------------------------------------------------------------------------

    def _pattern(self):
        source = getattr(self.ctx.runner, "patterns", None)
        if source is None:
            return None, "no pattern folder on this server"
        pid = self.args.get("pattern_id")
        if not isinstance(pid, str) or not pid:
            return None, "pattern_id is missing"
        try:
            got = source(pid)
        except Exception as exc:  # noqa: BLE001 - a bad file is a refusal, not a crash
            return None, f"pattern {pid} cannot be read: {exc}"
        return (got, None) if got is not None else (None, f"no pattern {pid}")

    def _repeats(self) -> int:
        try:
            return int(self.args.get("repeats", 1))
        except (TypeError, ValueError):
            return 1  # preflight refuses it; plan() only needs a number to describe

    def _rate(self) -> float:
        try:
            return float(self.args.get("rate_hz", 20.0))
        except (TypeError, ValueError):
            return 20.0

    def plan(self) -> dict:
        pattern, why = self._pattern()
        if pattern is None:
            return {"op": NAME, "text": f"Run pattern {self.args.get('pattern_id')!r}: {why}."}
        targets = ", ".join(t.target for t in pattern.tracks)
        return {"op": NAME, "pattern_id": pattern.id, "sha256": _sha(pattern),
                "duration_s": pattern.duration_s, "repeats": self._repeats(),
                "text": f"Run pattern {pattern.name} ({targets}) for "
                        f"{pattern.duration_s * self._repeats():.1f} s. The piezo goes back to "
                        "its start position at the end; an abort stops at once."}

    def preflight(self) -> list[dict]:
        args, checks = dict(self.args), []

        def check(name: str, ok: bool, want: str, read, why: str = "") -> None:
            checks.append({"name": name, "ok": ok, "want": want, "read": read, "why": why})

        extra = sorted(set(args) - KEYS)
        check("args", not extra, f"only {sorted(KEYS)}", extra,
              f"unknown arguments: {extra}" if extra else "")
        pattern, why = self._pattern()
        self._checked = pattern  # run() uses this very copy, not a later save of the file
        check("pattern", pattern is not None, "a saved pattern", args.get("pattern_id"), why or "")
        rep = args.get("repeats", 1)
        ok = isinstance(rep, int) and not isinstance(rep, bool) and 1 <= rep <= MAX_REPEATS
        check("repeats", ok, f"1..{MAX_REPEATS}", rep, "" if ok else "repeats out of range")
        rate = args.get("rate_hz", 20.0)
        ok = (isinstance(rate, int | float) and not isinstance(rate, bool)
              and 1.0 <= rate <= MAX_RATE_HZ)
        check("rate_hz", ok, f"1..{MAX_RATE_HZ:g} Hz", rate, "" if ok else "rate out of range")
        rts = args.get("return_to_start", True)
        check("return_to_start", isinstance(rts, bool), "true or false", rts,
              "" if isinstance(rts, bool) else "return_to_start must be true/false")
        if pattern is None or not ok or not isinstance(rep, int):
            return checks
        total = pattern.duration_s * rep
        check("duration", total <= MAX_TOTAL_S, f"at most {MAX_TOTAL_S:g} s in all", total,
              "" if total <= MAX_TOTAL_S else "the run would last too long")
        for track in pattern.tracks:
            if track.target == "piezo":
                self._check_piezo(track, check)
            else:
                self._check_trap(track, check)
        return checks

    def _check_piezo(self, track, check) -> None:
        axis = PiezoAxis(self.ctx.piezo)
        try:
            travel = axis.allowed()
            start = self.ctx.piezo.position()
        except Exception as exc:  # noqa: BLE001 - GuardError or an unreadable device
            check("piezo", False, "a piezo that may move", None, str(exc))
            return
        bad = []
        for name, base in (("x", start.x_um), ("y", start.y_um), ("z", start.z_um)):
            lo, hi = travel[name]
            vals = [base + getattr(p, f"{name}_um") for p in track.points]
            if min(vals) < lo or max(vals) > hi:
                bad.append(f"{name} {min(vals):.2f}..{max(vals):.2f} um outside {lo:g}..{hi:g}")
        check("piezo", not bad, "the track inside the piezo travel from where it is now",
              {"start_um": [start.x_um, start.y_um, start.z_um]}, "; ".join(bad))

    def _check_trap(self, track, check) -> None:
        tw = self.ctx.tweezers
        index = int(track.target.split(":")[1])
        try:
            TrapAxis(tw, bench_lock=lock_state(self.ctx.backend)).allowed()
            n = tw.info().n_traps
        except Exception as exc:  # noqa: BLE001 - GuardError or an unreadable device
            check(track.target, False, "tweezers that may move", None, str(exc))
            return
        check(track.target, index < n, f"a trap 0..{n - 1}", index,
              "" if index < n else f"the tweezers have no trap {index}")

    # -- run ------------------------------------------------------------------------------------

    def run(self) -> dict:
        ctx = self.ctx
        pattern = getattr(self, "_checked", None) or self._pattern()[0]
        repeats, rate = self._repeats(), self._rate()
        back = bool(self.args.get("return_to_start", True))
        piezo_track = next((t for t in pattern.tracks if t.target == "piezo"), None)
        traps = [t for t in pattern.tracks if t.target != "piezo"]
        piezo = PiezoAxis(ctx.piezo) if piezo_track else None
        trap_axis = (TrapAxis(ctx.tweezers, bench_lock=lock_state(ctx.backend), record=False)
                     if traps else None)
        start = ctx.piezo.position() if piezo_track else None
        d = pattern.duration_s
        total = d * repeats

        def send(t_pat: float) -> dict:
            where = {}
            if piezo_track is not None:
                p = piezo_track.at(t_pat)
                got = piezo.move(start.x_um + p.x_um, start.y_um + p.y_um, start.z_um + p.z_um)
                where["piezo"] = [round(v, 3) for v in got]
            for tr in traps:
                p = tr.at(t_pat)
                trap_axis.move(int(tr.target.split(":")[1]), p.x_um, p.y_um, p.z_um)
                where[tr.target] = [round(p.x_um, 3), round(p.y_um, 3), round(p.z_um, 3)]
            return where

        t0 = time.monotonic()
        last_report = -1.0
        ticks = 0
        while True:
            elapsed = time.monotonic() - t0
            done = elapsed >= total
            t_pat = d if done else (elapsed % d if d > 0 else 0.0)
            where = send(t_pat)
            ticks += 1
            if done or elapsed - last_report >= PROGRESS_EVERY_S:
                last_report = elapsed
                ctx.progress("running", step=min(int(elapsed / d) + 1, repeats) if d else 1,
                             n_steps=repeats, t_s=round(t_pat, 3),
                             elapsed_s=round(min(elapsed, total), 3), of_s=round(total, 3),
                             pattern_id=pattern.id, positions=where)
            if done:
                break
            ctx.sleep(1.0 / rate)  # an abort raises here: nothing more is sent
        returned = None
        if piezo_track is not None and back:
            returned = [round(v, 3) for v in piezo.move(start.x_um, start.y_um, start.z_um)]
        return {"op": NAME, "pattern_id": pattern.id, "sha256": _sha(pattern),
                "duration_s": d, "repeats": repeats, "ticks": ticks, "rate_hz": rate,
                "piezo_start_um": None if start is None else [start.x_um, start.y_um, start.z_um],
                "piezo_returned_um": returned,
                "piezo_moves": piezo.moves if piezo else 0,
                "piezo_max_off_um": piezo.max_off_um if piezo else None,
                "trap_moves": trap_axis.moves if trap_axis else 0,
                "trap_max_off_um": trap_axis.max_off_um if trap_axis else None}
