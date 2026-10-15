"""F4 sample map, engine side (ops-spec 6, docs/screens/map.md sections 3 and 6, T-032 stage 2).

Operations (registered with the T-011 runner):

- `sample_map{sample_id, <scan_4x args>, exposure_ms=12, focus="per_tile", candidates=True}`:
  the scan_4x tile scan in brightfield (Aura off, DiaLamp on through the guarded helper), the
  mosaic (`engine.mosaic`), then classical particle candidates on the full-resolution tiles,
  written as `particle` events (status "candidate", source "classical_candidate", grade
  "computed"). Record `<sample>/sample_map_<stamp>/`; summary has `scan_box_um` and
  `allowed_box_um`. `focus="plane"` (reuse the last scan's focus plane) is refused until
  scan_4x's body takes a per-tile focus hook.
- `goto_xy{sample_id, x_um, y_um}`: click-move (ops-spec 6.3). Refused outside the latest
  scan's `allowed_box_um`. A move longer than the objective's long-move row with Z above the
  retracted height asks `retract_then_move`, switches PFS off (refused in preflight when PFS is
  unreadable), parks Z at `Z_SAFE_UM`, then moves XY through the
  guards; Z is left retracted (never raised again here). Lights are not touched.
- `map_flag{sample_id, x_um, y_um, name, note, replaces?}`, `map_flag_retire{sample_id,
  flag_id}`, `candidate_confirm{sample_id, candidate_id, note?}`, `candidate_reject{...}`:
  record-only (beside a hardware op). The engine assigns `flag_id`; confirm / reject add a
  `particle` event for the same id with `decides` and source `person_confirmed` /
  `person_rejected`, so nothing is overwritten (the fold keeps `history`). A note edit is a new
  flag with `replaces`, and the old one is retired with `replaced_by`.

Sample events go through the server's open ExperimentSession for this sample
(`runner.sample_seat`, T-027), then the legacy sample.json / map.json are regenerated
(`write_derived_views`) and `map_changed` is emitted. Writes need that open session.
"""

from __future__ import annotations

import json
import math
import threading
from pathlib import Path
from typing import Any, ClassVar

from ..guards import (
    RETRACTED_MAX_Z_UM,
    XY_BOX_MARGIN_UM,
    Z_SAFE_UM,
    FocusAxis,
    GuardError,
    OpScope,
    XYAxis,
    XYBox,
    lights_off,
    plain,
    registry_key,
)
from ..mosaic import CandidateParams, find_candidates, load_scan_tiles
from ..records import GRADE_COMPUTED
from ..runner import Aborted, Operation, register_operation
from ..sample import SAMPLES_ROOT, Sample, read_sample, write_derived_views
from . import scan_4x

SAMPLE_MAP, GOTO_XY = "sample_map", "goto_xy"
MAP_FLAG, MAP_FLAG_RETIRE = "map_flag", "map_flag_retire"
CANDIDATE_CONFIRM, CANDIDATE_REJECT = "candidate_confirm", "candidate_reject"
PREFIX = "sample_map"
BRIGHTFIELD_EXPOSURE_MS = 12.0  # 2026-09-30 brightfield 4x (10 ms: median 2766 ADU)
FOCUS_MODES = ("per_tile", "plane")
SOURCE_CONFIRMED, SOURCE_REJECTED = "person_confirmed", "person_rejected"
# record ops run beside each other (not exclusive). One lock covers reading the view (which
# reads the legacy sample.json), regenerating the derived views, and picking the next flag id
# with its write, so two ops at once neither read a half-written file nor share a flag id
_SAMPLE_LOCK = threading.RLock()


# -- the open session for a sample -------------------------------------------------------
class SampleRecorder:
    """Sample events through the open ExperimentSession, then the derived views and
    `map_changed`. One per operation run."""

    def __init__(self, seat: Any, session: Any, sample_id: str, emit: Any):
        self.seat, self.session, self.sample_id, self._emit = seat, session, sample_id, emit
        self.root = Path(seat.samples_root)

    @staticmethod
    def why_not(ctx: Any, sample_id: str | None) -> str | None:
        """Why sample events cannot be written for `sample_id` now, or None."""
        seat = getattr(ctx.runner, "sample_seat", None)
        if seat is None:
            return "the sample store is not installed on the engine"
        if not sample_id:
            return "needs a sample_id (or an open sample)"
        session = seat.session_for(ctx.session_id) if ctx.session_id else None
        if session is None or not getattr(session, "writable", False):
            return "needs an open experiment session for this sample"
        if session.info.sample_id != sample_id:
            return (f"the open experiment session is for sample {session.info.sample_id}, "
                    f"not {sample_id}")
        return None

    @classmethod
    def of(cls, ctx: Any, sample_id: str) -> SampleRecorder:
        why = cls.why_not(ctx, sample_id)
        if why:
            raise GuardError(why)
        seat = ctx.runner.sample_seat
        return cls(seat, seat.session_for(ctx.session_id), sample_id, ctx.emit)

    def event(self, kind: str, **payload: Any) -> Any:
        return self.session.sample_event(kind, **payload)

    def view(self) -> Any:
        with _SAMPLE_LOCK:
            return read_sample(self.seat.store, self.sample_id, self.root,
                               self.session.session_id)

    def changed(self, what: str, **data: Any) -> Any:
        with _SAMPLE_LOCK:
            view = self.view()
            write_derived_views(view, self.root, with_map=True)
        self._emit("map_changed", sample_id=self.sample_id, what=what, **data)
        return view


def _sample_id(ctx: Any) -> str | None:
    sid = ctx.args.get("sample_id")
    if sid:
        return str(sid)
    return ctx.runner.snapshot()["sample"]["sample_id"]


def _root(ctx: Any, default: Path) -> Path:
    seat = getattr(ctx.runner, "sample_seat", None)
    return Path(getattr(seat, "samples_root", None) or default)


def _check(name: str, why: str | None, read: Any = None) -> dict:
    return {"name": name, "ok": why is None, "want": name, "read": read, "why": why or ""}


def _only(args: dict, allowed: set[str]) -> None:
    extra = sorted(set(args) - allowed)
    if extra:
        raise ValueError(f"unknown arguments: {extra}")


# -- the latest scan box -----------------------------------------------------------------
def latest_scan_box(sample: Sample) -> dict | None:
    """`scan_box_um` / `allowed_box_um` (x0, x1, y0, y1) of the newest scan4x_* or sample_map_*
    folder, from its summary when present, else recomputed from scan.json as scan_4x plans it."""
    folders = sorted((p.parent for pat in ("scan4x_*/scan.json", f"{PREFIX}_*/scan.json")
                      for p in sample.dir.glob(pat)), key=lambda p: p.name.split("_", 1)[-1])
    for folder in reversed(folders):
        summary = folder / "summary.json"
        if summary.exists():
            res = json.loads(summary.read_text(encoding="utf-8")).get("result") or {}
            res = res.get("summary") or res  # the runner nests the op's summary
            if res.get("allowed_box_um"):
                return {"result_id": folder.name, "scan_box_um": res.get("scan_box_um"),
                        "allowed_box_um": res["allowed_box_um"]}
        rec = json.loads((folder / "scan.json").read_text(encoding="utf-8"))
        hole = rec.get("hole") or {}
        if hole.get("centre_um") and hole.get("diameter_mm"):
            c = (float(hole["centre_um"][0]), float(hole["centre_um"][1]))
            half = scan_4x.half_side_um(hole["diameter_mm"], float(rec.get("margin_um", 500.0)))
            box = XYBox.around(c, half, XY_BOX_MARGIN_UM)
            return {"result_id": folder.name, "scan_box_um": scan_4x.square_box_um(c, half),
                    "allowed_box_um": [box.x_min, box.x_max, box.y_min, box.y_max]}
    return None


# -- sample_map --------------------------------------------------------------------------
def parse_map_args(args: dict) -> tuple[scan_4x.ScanArgs, str, bool]:
    a = dict(args)
    a.pop("sample_id", None)
    focus = a.pop("focus", "per_tile")
    candidates = bool(a.pop("candidates", True))
    a.pop("light", None)  # brightfield is the point of this op; "aura" is scan_4x
    if focus not in FOCUS_MODES:
        raise ValueError(f"focus {focus!r} is not one of {FOCUS_MODES}")
    a.setdefault("exposure_ms", BRIGHTFIELD_EXPOSURE_MS)
    return scan_4x.parse(a), focus, candidates


def write_candidates(rec: SampleRecorder, folder: Path, m: Any, hole: dict | None,
                     op_id: str, params: CandidateParams) -> list[dict]:
    """Classical candidates on the record's tiles, one `particle` event each (engine ids)."""
    scan, tiles = load_scan_tiles(folder)
    z_of = {t["name"]: t.get("z_image_um") for t in scan.get("tiles", [])}
    found = find_candidates(tiles, m, params, hole=hole)
    out = []
    for k, c in enumerate(found, 1):
        pid = f"{op_id}-c{k:03d}"
        rec.event("particle", particle_id=pid, x_um=c["x_um"], y_um=c["y_um"],
                  z_um=z_of.get(c["tile"]), status="candidate", source=c["source"],
                  grade=GRADE_COMPUTED, score=c["score"], tile=c["tile"], result_id=folder.name,
                  method=c["method"]["detector"])
        out.append({"candidate_id": pid, **{k2: c[k2] for k2 in ("x_um", "y_um", "score")}})
    return out


@register_operation
class SampleMapOp(Operation):
    """Brightfield 4x mosaic with particle candidates. Motion (control + session)."""

    name = SAMPLE_MAP
    record_prefix = PREFIX
    snaps = True
    approaches = True
    samples_root: ClassVar[Path] = SAMPLES_ROOT

    def _sample(self) -> Sample:
        sid = _sample_id(self.ctx)
        if not sid:
            raise ValueError("sample_map needs a sample_id (or an open sample)")
        return Sample(sid, _root(self.ctx, self.samples_root))

    def plan(self) -> dict:
        try:
            a, focus, cands = parse_map_args(self.args)
            pl = scan_4x.plan(self._sample().load_info(), scan_4x.PLAN_SENSOR, a)
        except (TypeError, ValueError) as exc:
            return {"op": SAMPLE_MAP, "error": str(exc)}
        return {**pl, "op": SAMPLE_MAP, "light": "brightfield (Aura off, DiaLamp on)",
                "focus": focus, "candidates": cands}

    def preflight(self) -> list[dict]:
        try:
            _, focus, _ = parse_map_args(self.args)
            sample = self._sample()
        except (TypeError, ValueError) as exc:
            return [_check("args", str(exc))]
        checks = scan_4x._checks(scan_4x.preflight(self.ctx.backend, sample), SAMPLE_MAP)
        if focus == "plane":
            checks.append(_check("focus", "focus='plane' is not available yet (scan_4x needs a "
                                          "per-tile focus hook); use 'per_tile'"))
        checks.append(_check("sample_record", SampleRecorder.why_not(self.ctx, sample.id)))
        return checks

    def run(self) -> dict:
        ctx, b = self.ctx, self.ctx.backend
        a, _, want_candidates = parse_map_args(self.args)
        sample = self._sample()
        rec = SampleRecorder.of(ctx, sample.id)
        info = sample.load_info()
        pl = scan_4x.plan(info, b.info().sensor, a, b.positions().z_um)
        if a.dry_run:
            return {"dry_run": True, "plan": pl}
        folder = scan_4x.runner_folder(ctx, sample, PREFIX)
        host = scan_4x.Host.of_runner(ctx, folder)
        lamp = OpScope(ctx.op_id, None, lambda ev: ctx.emit(ev.kind, **ev.data), backend=b)
        host.light_on = lambda line, percent: lamp.lamp_on()  # brightfield, not an Aura line
        status = "error"
        try:
            result = scan_4x.run_body(b, sample, info, a, pl, host)
            status = "finished"
        except Aborted:
            status = "aborted"
            raise
        finally:
            scan_4x._legacy_end(folder, lights_off(b), b.positions().z_um, status,
                                "sample_map exit (all off); the runner's exit path follows")
        result.update(light="brightfield", focus="per_tile", result_id=folder.name)
        if want_candidates:
            cands = write_candidates(rec, folder, pl["M_px_per_um"], info.hole, ctx.op_id,
                                     CandidateParams(polarity="dark"))
            rec.changed("candidates", n=len(cands), result_id=folder.name)
            result["candidates"] = {"n": len(cands), "source": "classical_candidate",
                                    "grade": GRADE_COMPUTED}
        return result


# -- goto_xy -----------------------------------------------------------------------------
def goto_plan(x: float, y: float, here: Any, long_um: float, row: str) -> dict:
    d = math.hypot(x - here.x_um, y - here.y_um)
    large = d > long_um
    return {"op": GOTO_XY, "target_um": [x, y], "from_um": [here.x_um, here.y_um],
            "distance_um": round(d, 1), "large_move": large, "long_move_um": long_um,
            "long_move_row": row,
            "retract_needed": bool(large and here.z_um is not None
                                   and here.z_um > RETRACTED_MAX_Z_UM),
            "z_um": here.z_um, "z_safe_um": Z_SAFE_UM,
            "provisional": ["long_move_um", "z_safe_um", "retracted_max_um"]}


@register_operation
class GotoXyOp(Operation):
    """Click-move inside the latest scan box; Z is retracted first for a large move and left
    there. Motion (control + session)."""

    name = GOTO_XY
    samples_root: ClassVar[Path] = SAMPLES_ROOT

    def _target(self) -> tuple[float, float]:
        _only(self.args, {"sample_id", "x_um", "y_um"})
        return plain(self.args.get("x_um"), "x_um"), plain(self.args.get("y_um"), "y_um")

    def _box(self) -> dict | None:
        sid = _sample_id(self.ctx)
        return None if not sid else latest_scan_box(Sample(sid, _root(self.ctx, self.samples_root)))

    def plan(self) -> dict:
        try:
            x, y = self._target()
            b = self.ctx.backend
            here = b.positions()
            long_um, row = XYAxis(b, XYBox(-math.inf, math.inf, -math.inf, math.inf)).long_move_um()
            return goto_plan(x, y, here, long_um, row)
        except Exception as exc:  # noqa: BLE001 - plan-only call has no hardware behind it
            return {"op": GOTO_XY, "target_um": [self.args.get("x_um"), self.args.get("y_um")],
                    "note": f"distance needs the stage: {exc}"}

    def preflight(self) -> list[dict]:
        try:
            x, y = self._target()
        except (GuardError, TypeError, ValueError) as exc:
            return [_check("args", str(exc))]
        box = self._box()
        if box is None:
            return [_check("scan_box", "no scan of this sample yet: run scan_4x or sample_map")]
        b = self.ctx.backend
        bx = XYBox(*box["allowed_box_um"])
        inside = bx.contains(x, y)
        p = b.positions()
        readable = p.x_um is not None and p.y_um is not None and p.z_um is not None
        checks = [_check("scan_box", None if inside else
                         f"({x:.0f}, {y:.0f}) is outside the scanned area {box['allowed_box_um']}",
                         box["result_id"]),
                  _check("position", None if readable else f"position unreadable: {p.errors}")]
        if readable:
            long_um, row = XYAxis(b, bx).long_move_um()
            if goto_plan(x, y, p, long_um, row)["retract_needed"]:
                # the retract drives ZDrive: PFS must be readable to be switched off first
                try:
                    s = b.pfs()
                    read, why = {"enabled": s.enabled, "in_range": s.in_range}, None
                except Exception as exc:  # noqa: BLE001 - an unknown PFS state is not safe
                    read, why = None, f"PFS state unreadable ({type(exc).__name__}: {exc})"
                checks.append(_check("pfs", why, read))
        return checks

    def run(self) -> dict:
        ctx, b = self.ctx, self.ctx.backend
        x, y = self._target()
        box = XYBox(*self._box()["allowed_box_um"])
        xy = XYAxis(b, box, allow_motion=True, sink=lambda ev: ctx.emit(ev.kind, **ev.data),
                    op_id=ctx.op_id)
        long_um, row = xy.long_move_um()
        here = b.positions()
        pl = goto_plan(x, y, here, long_um, row)
        retracted, pfs = False, None
        if pl["retract_needed"]:
            ans = ctx.confirm("retract_then_move",
                              f"retract Z {here.z_um:.1f} -> {Z_SAFE_UM:g} um, then move to "
                              f"({x:.0f}, {y:.0f})",
                              context={"z_um": here.z_um, "z_safe_um": Z_SAFE_UM, "x_um": x,
                                       "y_um": y})
            if not ans.get("ok"):
                raise Aborted("the operator did not retract Z")
            ctx.progress("retract", z_um=here.z_um, z_safe_um=Z_SAFE_UM)
            focus = FocusAxis.from_backend(b, allow_motion=True,
                                           sink=lambda ev: ctx.emit(ev.kind, **ev.data),
                                           op_id=ctx.op_id, sleep=ctx.sleep)
            # PFS off before ZDrive moves (F5 order, change_objective, z_retract); raises if
            # it stays on
            before = b.pfs()  # require_pfs_quiet returns the state after switching off
            focus.require_pfs_quiet(disable=True)
            focus.park_at(Z_SAFE_UM)
            after = b.pfs()
            pfs = {"enabled_before": before.enabled, "enabled": after.enabled,
                   "in_range": after.in_range}
            retracted = True
        ctx.check()
        ctx.progress("move_xy", x_um=x, y_um=y)
        read = xy.goto(x, y)
        end = b.positions()
        return {"x_um": read[0], "y_um": read[1], "z_um": end.z_um, "retracted": retracted,
                "pfs": pfs,
                "distance_um": pl["distance_um"], "large_move": pl["large_move"],
                "allowed_box_um": [box.x_min, box.x_max, box.y_min, box.y_max],
                "z_left": "retracted" if retracted else "unchanged",
                "next": "refocus with a scan tile or focus_100x" if retracted else None}


# -- flags and candidate decisions (record-only) ------------------------------------------
class _MapRecordOp(Operation):
    exclusive = False  # record-only: runs beside a hardware op (T-011)
    motion = False
    allowed: ClassVar[set[str]] = set()

    def preflight(self) -> list[dict]:
        try:
            _only(self.args, self.allowed)
            self._validate()
        except (GuardError, TypeError, ValueError) as exc:
            return [_check("args", str(exc))]
        why = SampleRecorder.why_not(self.ctx, _sample_id(self.ctx))
        if why is None:
            why = self._state_problem(self._rec().view())
        return [_check("sample_record", why)]

    def _validate(self) -> None:
        return None

    def _state_problem(self, view: Any) -> str | None:
        """Why the sample's current state refuses this decision, or None."""
        return None

    def _rec(self) -> SampleRecorder:
        return SampleRecorder.of(self.ctx, _sample_id(self.ctx))


@register_operation
class MapFlagOp(_MapRecordOp):
    name = MAP_FLAG
    allowed: ClassVar[set[str]] = {"sample_id", "x_um", "y_um", "name", "note", "replaces"}

    def _validate(self) -> None:
        plain(self.args.get("x_um"), "x_um")
        plain(self.args.get("y_um"), "y_um")

    def _state_problem(self, view: Any) -> str | None:
        old = self.args.get("replaces")
        if old is not None and str(old) not in view.active_flags():
            return f"flag {old} is not an active flag of this sample"
        return None

    def run(self) -> dict:
        b, rec = self.ctx.backend, self._rec()
        old = self.args.get("replaces")
        try:
            objective = registry_key(b.nosepiece())
        except Exception:  # noqa: BLE001 - a flag without a readable lens is still a flag
            objective = None
        z = b.positions().z_um
        with _SAMPLE_LOCK:
            view = rec.view()
            if (why := self._state_problem(view)) is not None:
                raise GuardError(why)
            fid = f"F{len(view.flags) + 1:03d}"
            while fid in view.flags:
                fid = f"F{int(fid[1:]) + 1:03d}"
            payload = {"flag_id": fid, "name": str(self.args.get("name") or fid),
                       "note": str(self.args.get("note") or ""),
                       "x_um": plain(self.args["x_um"], "x_um"),
                       "y_um": plain(self.args["y_um"], "y_um"), "z_um": z,
                       "objective": objective, "replaces": None if old is None else str(old)}
            rec.event("flag_set", **payload)
            if old is not None:
                rec.event("flag_remove", flag_id=str(old), replaced_by=fid)
        rec.changed("flags", flag_id=fid)
        return {"flag": payload}


@register_operation
class MapFlagRetireOp(_MapRecordOp):
    name = MAP_FLAG_RETIRE
    allowed: ClassVar[set[str]] = {"sample_id", "flag_id"}

    def _state_problem(self, view: Any) -> str | None:
        fid = str(self.args.get("flag_id") or "")
        if fid not in view.active_flags():
            return f"flag {fid!r} is not an active flag of this sample"
        return None

    def run(self) -> dict:
        rec = self._rec()
        fid = str(self.args.get("flag_id") or "")
        if (why := self._state_problem(rec.view())) is not None:
            raise GuardError(why)
        rec.event("flag_remove", flag_id=fid)
        rec.changed("flags", flag_id=fid)
        return {"flag_id": fid, "retired": True}


class _CandidateDecision(_MapRecordOp):
    allowed: ClassVar[set[str]] = {"sample_id", "candidate_id", "note"}
    status: ClassVar[str] = ""
    source: ClassVar[str] = ""

    def _state_problem(self, view: Any) -> str | None:
        cid = str(self.args.get("candidate_id") or "")
        cand = view.candidates.get(cid)
        if cand is None or cand.get("status") != "candidate":
            return f"{cid!r} is not an undecided candidate of this sample"
        return None

    def run(self) -> dict:
        rec = self._rec()
        view = rec.view()
        cid = str(self.args.get("candidate_id") or "")
        if (why := self._state_problem(view)) is not None:
            raise GuardError(why)
        cand = view.candidates[cid]
        rec.event("particle", particle_id=cid, x_um=cand.get("x_um"), y_um=cand.get("y_um"),
                  z_um=cand.get("z_um"), status=self.status, source=self.source, decides=cid,
                  note=str(self.args.get("note") or ""))
        rec.changed("candidates", candidate_id=cid)
        return {"candidate_id": cid, "status": self.status, "source": self.source}


@register_operation
class CandidateConfirmOp(_CandidateDecision):
    name = CANDIDATE_CONFIRM
    status, source = "confirmed", SOURCE_CONFIRMED


@register_operation
class CandidateRejectOp(_CandidateDecision):
    name = CANDIDATE_REJECT
    status, source = "rejected", SOURCE_REJECTED

