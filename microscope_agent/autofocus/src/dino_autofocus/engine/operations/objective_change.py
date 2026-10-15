"""`objective_change`: rotate the nosepiece with the F5 immersion-loading step-out (T-029).

PLAN 2 F5 seven steps; operations-spec 4.2; screen contract T-104 (docs/screens/objective.md).
Port of `scripts/change_objective.py` (`--to N`, `--park`, `--return-only`), deleted in R-05.

Commands (names fixed by the screen contract):

- rotate: `start objective_change {target_state, escape, approach_target_um, approach_step_um}`
- loading done: `confirm {op_id, key: "load_immersion", ok: true}` (manual step, local only)
- resume after `awaiting_return`: `start objective_change {resume: true}` (steps 6-7)
- re-load immersion without rotating: `start objective_change {reload: true}` (no rotation)

Steps (F5), each with a `progress` event `step=1..7`; steps 2-6 carry
`{axis, commanded, readback, pfs_in_range, label_read}`, step 7 one event per approach move with
`step_index`:

1. record XY, Z, objective; switch the lights off (readback)
2. PFS off -> Z retract to 0 um -> PFS must read Out of Range
3. step out in +Y by `guards.ESCAPE_DY_UM` (only with Z retracted; `step_out_target`);
   sample event `objective_stepped_out`, written before the move (intent first)
4. rotate, read the label back; write the sample event `objective_changed`
   `{from_key, to_key, label}` to the open experiment session
5. the operator loads oil / water and presses "Loading done" (`manual_step`)
6. XY back to step 1's position (Z still retracted); `objective_stepped_back` once a fresh
   readback confirms the stage is back
7. Z from 0 um: one move to 2800 um, then steps of at most the lens's `approach_step_um`, with
   the readback and this operation's clearance check after every step (`FocusAxis.approach`)

From the step-out on, the operation's end state is `awaiting_return` with `return_xy`, until
step 6 has put XY back; an abort, an error or a "not done" answer in between leaves it so, and
the runner then refuses other motion until `{resume: true}` (ui-spec 7.5). No exit path raises
Z; the runner switches the lights off on every exit.

Values that are not measured on the stand come from the guards tables and are marked
"unmeasured provisional" (`guards.PROVISIONAL`) in the plan and the records.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from ..events import Event
from ..guards import (
    FREE_WD_UM,
    OBJECTIVE_LIMITS,
    PROVISIONAL,
    RETRACT_Z_UM,
    RETRACTED_MAX_Z_UM,
    RETURN_Z_UM,
    SAMPLE_Z_WINDOW_UM,
    XY_TOL_UM,
    Z_TOL_UM,
    FocusAxis,
    GuardError,
    XYAxis,
    XYBox,
    bench_approach_state,
    bench_ascent_refusal,
    check_lights,
    limits_for,
    registry_key,
    rotate_nosepiece,
    step_out_target,
)
from ..runner import Operation, register_operation
from ..sample import OBJECTIVE_CHANGED, STEPPED_BACK, STEPPED_OUT

NAME = "objective_change"
N_STEPS = 7
LOAD_KEY = "load_immersion"
#: nosepiece position -> lens key, from the `configs/ti2_*.yaml` headers ("nosepiece position N").
#: Only for `plan()`, which has no hardware; preflight checks it against the backend's labels.
NOSEPIECE_KEYS = {0: "4x", 1: "10x", 2: "20x", 3: "40x-WI", 4: "60x-Oil", 5: "100x-Oil"}
IMMERSION = {"-Oil": "oil", "-WI": "water"}
NO_WD_WHY = "free working distance not measured ({key}; guards.FREE_WD_UM)"


def immersion_of(key: str | None) -> str | None:
    """"oil", "water" or None (dry) from a lens key."""
    if not key:
        return None
    return next((v for k, v in IMMERSION.items() if key.endswith(k)), None)


def _dy_sign() -> str:
    dy = _escape_dy()
    return "+" if dy is not None and dy >= 0 else "-"


def _escape_dy() -> float | None:
    try:
        x, y, basis = step_out_target(_LimitsOnly((-math.inf, math.inf)), 0.0, 0.0)
    except GuardError:
        return None
    return y


class _LimitsOnly:
    """A stand-in backend for `step_out_target` in `plan()`: answers `info()` only."""

    def __init__(self, y_um):
        self._info = SimpleNamespace(stage_limits=SimpleNamespace(y_um=y_um))

    def info(self) -> Any:
        return self._info


def escape_plan(xy: tuple[float | None, float | None] | None, y_limits, default: bool) -> dict:
    """The plan's `escape` block (T-104): allowed / reason from `step_out_target` when the
    position and the stage Y limit are known; otherwise "checked at preflight"."""
    dy = _escape_dy()
    out = {"allowed": None, "reason": None, "sign": _dy_sign(), "dy_um": dy, "mark": PROVISIONAL,
           "default": default}
    missing = [what for what, v in (("position", xy and xy[1]), ("stage Y limit", y_limits))
               if v is None]
    if missing:
        out["reason"] = f"checked at preflight: {' and '.join(missing)} not known yet"
        return out
    try:
        _, y, _ = step_out_target(_LimitsOnly(tuple(y_limits)), xy[0] or 0.0, xy[1])
        out.update(allowed=True, target_y_um=y)
    except GuardError as e:
        out.update(allowed=False, reason=str(e))
    return out


def approach_cap_um(key: str | None) -> tuple[float, str]:
    """(highest Z this operation may approach to with lens `key`, why).

    Nothing here knows where the focus is, so guards' ceiling (focus centre + 0.4 x WD) cannot
    apply. Above 2800 um is allowed only for a lens whose free WD covers the whole sample
    window (today the 4x, 20 mm): wherever the sample sits in 2800-3200 um, the lens cannot
    reach the coverslip. Any other lens stops at 2800 um; focusing above is `focus_100x`'s job,
    under its ceiling.
    """
    lo, hi = SAMPLE_Z_WINDOW_UM
    wd = FREE_WD_UM.get(key or "")
    if wd is not None and wd >= hi - lo:
        return hi, f"{key}: free WD {wd:g} um covers the {lo:g}-{hi:g} um window"
    return RETURN_Z_UM, (f"{key or 'unknown lens'}: approach to {RETURN_Z_UM:g} um; focusing "
                         "above is focus_100x's job, under its ceiling")


def _check(name: str, ok: bool, want: Any = None, read: Any = None, why: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "want": want, "read": read, "why": why}


@register_operation
class ObjectiveChange(Operation):
    name = NAME
    approaches = True  # step 7 calls FocusAxis.approach() with `clearance()`

    # -- what kind of run this is
    @property
    def mode(self) -> str:
        a = self.args
        if a.get("resume"):
            return "resume"
        if a.get("reload"):
            return "reload"
        return "rotate"

    def returns_to_sample(self) -> bool:
        return self.mode == "resume"

    def _target_key(self) -> str | None:
        st = self.args.get("target_state")
        return NOSEPIECE_KEYS.get(int(st)) if isinstance(st, int | float) else None

    def _escape_default(self, key: str | None) -> bool:
        return immersion_of(key) is not None

    def _escape(self, key: str | None) -> bool:
        if self.mode == "resume":
            return False
        e = self.args.get("escape")
        return self._escape_default(key) if e is None else bool(e)

    def _approach_target(self) -> float:
        return float(self.args.get("approach_target_um", RETURN_Z_UM))

    # -- the clearance check handed to approach()
    def clearance(self) -> Callable[[float], bool]:
        """After every approach move: Z not past the asked target nor the lens's approach cap
        (`approach_cap_um`), the operation not aborted, and the nosepiece still reading the
        lens this approach is for."""
        target = self._approach_target()

        def clear(z_read: float) -> bool:
            if self.ctx.aborted:
                return False
            want = getattr(self, "_approach_label", None)
            try:
                key = registry_key(want) if want is not None else None
            except GuardError:
                key = None  # unreadable lens: the strict cap
            top = min(target, approach_cap_um(key)[0])
            if not RETRACT_Z_UM - Z_TOL_UM <= z_read <= top + Z_TOL_UM:
                return False
            return want is None or self.ctx.backend.nosepiece() == want

        return clear

    # -- plan: no hardware (Runner.plan)
    def plan(self) -> dict:
        snap = self._snapshot()
        key = self._target_key() if self.mode == "rotate" else None
        pos = snap.get("positions") or {}
        xy = (pos.get("x_um"), pos.get("y_um")) if pos else None
        info = snap.get("backend_info") or {}
        y_lim = (info.get("stage_limits") or {}).get("y_um")
        aw = snap.get("awaiting_return")
        row, row_name = limits_for(key) if key else (None, None)
        steps = self._step_texts(key)
        out: dict[str, Any] = {
            "mode": self.mode, "target_state": self.args.get("target_state"),
            "target_key": key, "immersion": immersion_of(key),
            "steps": steps, "n_steps": N_STEPS,
            "approach": {"from_um": RETRACT_Z_UM, "to_window_um": RETURN_Z_UM,
                         "target_um": self._approach_target(),
                         "step_um": self.args.get("approach_step_um")
                         or (row.approach_step_um if row else None),
                         "row": row_name, "mark": PROVISIONAL,
                         "cap_um": approach_cap_um(key)[0] if key else None,
                         "cap_why": approach_cap_um(key)[1] if key else None},
            "escape": escape_plan(xy, y_lim, self._escape_default(key)),
        }
        if self.mode == "resume":
            out["return_xy"] = (aw or {}).get("return_xy")
        return out

    def _snapshot(self) -> dict:
        try:
            return self.ctx.runner.snapshot()
        except Exception:  # noqa: BLE001 - a plan never fails on a missing snapshot
            return {}

    def _step_texts(self, key: str | None) -> list[dict]:
        esc = self._escape(key)
        dy = _escape_dy()
        texts = {
            1: "Record XY, Z and the objective; lights off",
            2: f"PFS off, Z -> {RETRACT_Z_UM:g} um, PFS must read Out of Range",
            3: (f"Step out: Y {dy:+.0f} um ({PROVISIONAL})" if esc and dy is not None
                else "Step out: skipped"),
            4: (f"Rotate to nosepiece {self.args.get('target_state')} ({key})"
                if self.mode == "rotate" else "Rotate: skipped (same objective)"),
            5: ("Load immersion, then press Loading done" if esc or immersion_of(key)
                else "Load immersion: none (dry objective)"),
            6: "XY back to the recorded position (Z still retracted)",
            7: f"Z approach from {RETRACT_Z_UM:g} um to {self._approach_target():g} um in steps",
        }
        run = {"rotate": range(1, 8), "reload": (1, 2, 3, 5, 6, 7), "resume": (6, 7)}[self.mode]
        return [{"step": s, "text": texts[s], "runs": s in run} for s in range(1, 8)]

    # -- preflight: reads only
    def preflight(self) -> list[dict]:
        a, b = self.args, self.ctx.backend
        checks: list[dict] = []
        modes = [m for m in ("resume", "reload") if a.get(m)]
        has_target = a.get("target_state") is not None
        if len(modes) > 1 or (modes and has_target) or (not modes and not has_target):
            checks.append(_check("mode", False, "one of target_state, reload, resume",
                                 {"modes": modes, "target_state": a.get("target_state")},
                                 "give exactly one of target_state, reload: true, resume: true"))
            return checks
        info = b.info()
        label = b.nosepiece()
        try:
            key_now = registry_key(label)
        except GuardError as e:
            key_now = None
            checks.append(_check("objective_now", False, "a readable lens", label, str(e)))
        if key_now is not None:
            checks.append(_check("objective_now", key_now in OBJECTIVE_LIMITS,
                                 "a lens in OBJECTIVE_LIMITS", key_now,
                                 "" if key_now in OBJECTIVE_LIMITS else
                                 f"{key_now} has no guards row"))
        p = b.positions()
        checks.append(_check("position", None not in (p.x_um, p.y_um, p.z_um), "x, y, z read",
                             [p.x_um, p.y_um, p.z_um], str(p.errors) if p.errors else ""))
        target_key = key_now
        if self.mode == "rotate":
            st = int(a["target_state"])
            by_state = {o.state: o for o in info.objectives}
            now_state = next((o.state for o in info.objectives if o.label == label), None)
            checks.append(_check("target_differs", st != now_state, f"not {now_state}", st,
                                 "already on that objective" if st == now_state else ""))
            tgt = by_state.get(st)
            if tgt is None:
                checks.append(_check("target_lens", False, "a nosepiece position with a lens",
                                     st, f"no objective at nosepiece position {st}"))
                return checks
            try:
                target_key = registry_key(tgt.label)
            except GuardError as e:
                checks.append(_check("target_lens", False, "a readable lens", tgt.label, str(e)))
                return checks
            if NOSEPIECE_KEYS.get(st) != target_key:
                checks.append(_check("target_lens", False, NOSEPIECE_KEYS.get(st), target_key,
                                     "the backend's lens at this position is not the one in "
                                     "configs/ti2_*.yaml"))
            ok = target_key in FREE_WD_UM and target_key in OBJECTIVE_LIMITS
            checks.append(_check("target_working_distance", ok, "a recorded free WD", target_key,
                                 "" if ok else NO_WD_WHY.format(key=target_key)))
        elif self.mode == "resume":
            aw = self._snapshot().get("awaiting_return") or {}
            ok = aw.get("op") == NAME and aw.get("return_xy") is not None
            checks.append(_check("awaiting_return", ok, "an objective_change away from the sample",
                                 aw.get("op_id"), "" if ok else "nothing to return to"))
            # the long-move rule would refuse the XY return anyway; say why up front
            okr = p.z_um is not None and p.z_um <= RETRACTED_MAX_Z_UM
            checks.append(_check("z_retracted", okr, f"<= {RETRACTED_MAX_Z_UM} um ({PROVISIONAL})",
                                 p.z_um, "" if okr else "Z must be retracted before the return"))
        if self._escape(target_key):
            try:
                _, ty, _ = step_out_target(b, p.x_um, p.y_um)
                checks.append(_check("step_out", True, "inside the stage Y travel", ty))
            except GuardError as e:
                checks.append(_check("step_out", False, "inside the stage Y travel",
                                     p.y_um, str(e)))
        zt = self._approach_target()
        # T-029d second layer: the approach after the turn climbs 0 -> zt on the target lens
        why = bench_ascent_refusal(info, target_key, zt)
        checks.append(_check("bench_approach", why is None, bench_approach_state(), zt,
                             why or ""))
        cap, cap_why = approach_cap_um(target_key)
        okz = SAMPLE_Z_WINDOW_UM[0] <= zt <= cap
        checks.append(_check("approach_target", okz, [SAMPLE_Z_WINDOW_UM[0], cap], zt,
                             "" if okz else (cap_why if zt > cap else
                                             "approach target below the sample Z window")))
        row, row_name = limits_for(target_key)
        step = a.get("approach_step_um")
        if step is not None:
            oks = Z_TOL_UM < float(step) <= row.approach_step_um
            checks.append(_check("approach_step", oks,
                                 f"{Z_TOL_UM} < step <= {row.approach_step_um} ({row_name}, "
                                 f"{PROVISIONAL})", step,
                                 "" if oks else "approach step outside the lens's row"))
        return checks

    # -- run
    def run(self) -> dict:
        ctx, b = self.ctx, self.ctx.backend
        sink = self._sink
        # 1. record the start
        p0 = b.positions()
        label0 = b.nosepiece()
        start = {"x_um": p0.x_um, "y_um": p0.y_um, "z_um": p0.z_um, "objective": label0,
                 "pfs": vars(b.pfs()).copy()}
        if self.mode == "resume":
            aw = self._snapshot().get("awaiting_return") or {}
            return_xy = list(aw["return_xy"])
            start["resumed_from"] = aw.get("op_id")
        else:
            return_xy = [p0.x_um, p0.y_um]
        summary: dict[str, Any] = {"mode": self.mode, "start": start, "return_xy": return_xy,
                                   "steps": []}
        if self.mode != "resume":
            # T-002 appendix 3 item 2: a light that does not read back off stops the operation
            check_lights(b.all_off(), sink, ctx.op_id)
            self._progress(1, "recorded", axis=None, commanded=None,
                           readback=[p0.x_um, p0.y_um, p0.z_um], pfs_in_range=start["pfs"]
                           ["in_range"], label_read=label0, summary=summary)
            ctx.check()
        z_axis = FocusAxis(b, label0, allow_motion=True, sink=sink, op_id=ctx.op_id,
                           sleep=ctx.sleep)
        target_key = registry_key(label0)
        escape = False
        if self.mode != "resume":
            # 2. PFS off, retract, PFS out of range
            z_axis.require_pfs_quiet(disable=True)
            z = z_axis.park_at(RETRACT_Z_UM) if z_axis.position_um() > RETRACT_Z_UM + Z_TOL_UM \
                else z_axis.position_um()
            pfs = b.pfs()
            self._progress(2, "retracted", axis="z", commanded=RETRACT_Z_UM, readback=z,
                           pfs_in_range=pfs.in_range, label_read=label0, summary=summary)
            if not pfs.out_of_range:
                raise GuardError(f"PFS reads {pfs.in_range!r} after retract; stopping with Z at "
                                 f"{z:.2f} um")
            ctx.check()
            if self.mode == "rotate":
                tgt = {o.state: o for o in b.info().objectives}[int(self.args["target_state"])]
                target_key = registry_key(tgt.label)
            escape = self._escape(target_key)
            # 3. step out
            if escape:
                x_t, y_t, basis = step_out_target(b, return_xy[0], return_xy[1])
                ctx.set_end_state(state="awaiting_return", return_xy=return_xy,
                                  objective_before=label0, step_out=basis)
                xy = self._xy_axis(return_xy, (x_t, y_t))
                # SAFETY (T-029c): the intent goes into the sample record before the move, so a
                # step-out that fails part-way still reads as away after a restart
                # (read_sample().awaiting_return). Only a confirmed return closes it.
                summary["stepped_out"] = self._sample_event(
                    STEPPED_OUT, return_xy=return_xy, step_out_xy=[x_t, y_t],
                    objective=registry_key(label0))
                read = xy.goto(x_t, y_t)
                self._progress(3, "stepped out", axis="xy", commanded=[x_t, y_t],
                               readback=list(read), pfs_in_range=b.pfs().in_range,
                               label_read=b.nosepiece(), summary=summary, basis=basis)
                ctx.check()
            # 4. rotate
            if self.mode == "rotate":
                ctx.set_end_state(state="awaiting_return", return_xy=return_xy,
                                  objective_before=label0)
                label = rotate_nosepiece(b, z_axis, int(self.args["target_state"]))
                self._progress(4, "rotated", axis="nosepiece",
                               commanded=int(self.args["target_state"]),
                               readback=label, pfs_in_range=b.pfs().in_range, label_read=label,
                               summary=summary)
                if registry_key(label) != target_key:
                    raise GuardError(f"nosepiece reads {label!r}, not the {target_key} lens")
                summary["sample_event"] = self._sample_event(
                    OBJECTIVE_CHANGED, from_key=registry_key(label0), to_key=target_key,
                    label=label)
                z_axis = FocusAxis(b, label, allow_motion=True, sink=sink, op_id=ctx.op_id,
                                   sleep=ctx.sleep)
                ctx.check()
            # 5. immersion loading
            immersion = immersion_of(target_key)
            if escape or immersion:
                ans = ctx.confirm(LOAD_KEY, f"Load {immersion or 'immersion'} on the "
                                            f"{target_key} objective, then press Loading done",
                                  options=("done",), kind="manual_step",
                                  context={"step": LOAD_KEY, "f5_step": 5,
                                           "immersion": immersion, "objective": target_key})
                self._progress(5, "loading done" if ans["ok"] else "loading not done",
                               axis=None, commanded=None, readback=ans.get("answer"),
                               pfs_in_range=None, label_read=b.nosepiece(), summary=summary)
                if not ans["ok"]:
                    summary["why"] = "loading not confirmed; the stage stays away"
                    return {**summary, "state": "awaiting_return", "return_xy": return_xy}
                ctx.check()
        # 6. XY back
        p = b.positions()
        if p.x_um is None or p.y_um is None:
            raise GuardError(f"position unreadable before the return: {p.errors}")
        if math.hypot(p.x_um - return_xy[0], p.y_um - return_xy[1]) > XY_TOL_UM:
            xy = self._xy_axis(return_xy, (p.x_um, p.y_um))
            read = xy.goto(*return_xy)
        else:
            read = (p.x_um, p.y_um)
        # the return counts only once a fresh readback puts the stage back at return_xy
        p = b.positions()
        if (p.x_um is None or p.y_um is None
                or math.hypot(p.x_um - return_xy[0], p.y_um - return_xy[1]) > XY_TOL_UM):
            raise GuardError(f"XY reads ({p.x_um}, {p.y_um}) after the return, not "
                             f"{return_xy} (tolerance {XY_TOL_UM} um); the stage stays away")
        read = (p.x_um, p.y_um)
        self._progress(6, "returned", axis="xy", commanded=return_xy, readback=list(read),
                       pfs_in_range=b.pfs().in_range, label_read=b.nosepiece(), summary=summary)
        ctx.set_end_state(state="returned")
        if escape or self.mode == "resume":  # closes the step-out in the sample record
            summary["stepped_back"] = self._sample_event(
                STEPPED_BACK, return_xy=return_xy, xy_um=list(read))
        ctx.check()
        # 7. stepwise approach
        label = b.nosepiece()
        z_axis = FocusAxis(b, label, allow_motion=True, sink=sink, op_id=ctx.op_id,
                           sleep=ctx.sleep)
        self._approach_label = label
        self._approach_n = 0
        z_end = z_axis.approach(self._approach_target(), self.args.get("approach_step_um"),
                                clearance=self.clearance())
        end = b.positions()
        summary["end"] = {"x_um": end.x_um, "y_um": end.y_um, "z_um": end.z_um,
                          "objective": b.nosepiece(), "pixel_um": b.info().pixel_um}
        summary["z_end_um"] = z_end
        summary["state"] = "done"
        return summary

    # -- helpers
    def _sink(self, ev: Event) -> None:
        """Guard events go out as they are; approach moves also as step-7 progress."""
        self.ctx.emit(ev.kind, **ev.data)
        d = ev.data
        if ev.kind == "motion" and d.get("axis") == "z" and str(d.get("how", "")).startswith(
                "approach"):
            self._approach_n = getattr(self, "_approach_n", 0) + 1
            self.ctx.progress("approaching", step=7, n_steps=N_STEPS,
                              step_index=self._approach_n, axis="z",
                              commanded=d.get("target_um"), readback=d.get("read_um"),
                              basis=d.get("basis"))

    def _sample_event(self, kind: str, **payload: Any) -> dict:
        """Write a sample event to the open experiment session (T-019) and say what happened.
        A missing seat or session, or a failed write, is logged and never stops the motion:
        the runner's own record of this operation is complete either way."""
        seat = getattr(self.ctx.runner, "sample_seat", None)
        sid = self.ctx.session_id
        session = seat.session_for(sid) if seat is not None and sid else None
        if session is None or not getattr(session, "writable", False):
            why = "no sample seat installed" if seat is None else "no open experiment session"
            self.ctx.log(f"{kind} not written: {why}", level="warning")
            return {"kind": kind, "written": False, "why": why, **payload}
        try:
            session.sample_event(kind, **payload)
        except Exception as e:  # noqa: BLE001 - a record failure must not strand the stage
            self.ctx.log(f"{kind} not written: {e}", level="warning")
            return {"kind": kind, "written": False, "why": str(e), **payload}
        return {"kind": kind, "written": True, **payload}

    def _xy_axis(self, a: tuple | list, b: tuple | list) -> XYAxis:
        """An axis whose box holds exactly the two points of this move, plus the tolerance.

        The sample's scan box does not apply here on purpose: the step-out leaves the sample
        by 15 mm. The box still refuses any other target, and XYAxis.goto keeps the
        long-move rule (Z retracted) and the readback check for both moves."""
        m = 2 * XY_TOL_UM
        box = XYBox(min(a[0], b[0]) - m, max(a[0], b[0]) + m, min(a[1], b[1]) - m,
                    max(a[1], b[1]) + m)
        return XYAxis(self.ctx.backend, box, allow_motion=True, sink=self._sink,
                      op_id=self.ctx.op_id)

    def _progress(self, step: int, status: str, *, summary: dict, **data: Any) -> None:
        summary["steps"].append({"step": step, "status": status, **data})
        self.ctx.progress(status, step=step, n_steps=N_STEPS, **data)

