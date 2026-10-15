"""`objective_change` (T-029): the F5 seven steps on the runner over MockBackend.

Every runner a test builds is shut down by the `make` fixture, so no thread outlives a test.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from dino_autofocus.engine import Command, Event
from dino_autofocus.engine.backend import GUARD_TOKEN, Readback
from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.guards import FREE_WD_UM, PROVISIONAL, GuardError
from dino_autofocus.engine.operations.objective_change import (
    LOAD_KEY,
    NAME,
    ObjectiveChange,
    approach_cap_um,
    escape_plan,
    immersion_of,
    step_out_target,
)
from dino_autofocus.engine.runner import AllowAll, Registry, Runner, RunnerConfig
from dino_autofocus.engine.sample import OBJECTIVE_CHANGED, STEPPED_BACK, STEPPED_OUT

T = 10.0
USER, SESSION = "op@example.test", "20261001_1540_1"
REG = Registry()
REG.register(ObjectiveChange)
HOLE = (8026.0, 571.6)


class Collect:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._cond = threading.Condition()

    def __call__(self, ev: Event) -> None:
        with self._cond:
            self.events.append(ev)
            self._cond.notify_all()

    def wait(self, kind: str, op_id: str) -> Event:
        def find():
            return next((e for e in self.events if e.kind == kind and e.op_id == op_id), None)

        with self._cond:
            assert self._cond.wait_for(lambda: find() is not None, T), (kind, self.kinds(op_id))
            return find()

    def kinds(self, op_id: str) -> list[str]:
        return [e.kind for e in self.events if e.op_id == op_id]

    def of(self, kind: str, op_id: str) -> list[Event]:
        return [e for e in self.events if e.kind == kind and e.op_id == op_id]


def start(**args) -> Command:
    return Command("start", op=NAME, args=args, user_id=USER, session_id=SESSION)


def confirm(op_id: str, ok: bool = True) -> Command:
    return Command("confirm", op_id=op_id, user_id=USER, session_id=SESSION,
                   args={"key": LOAD_KEY, "ok": ok, "answer": "done" if ok else "not done"})


@pytest.fixture
def make():
    made: list[Runner] = []

    def build(nosepiece: int = 0, z_um: float = 3048.7, xy=HOLE):
        be = MockBackend(seed=1)
        w = be.world
        w.set_nosepiece(nosepiece)
        w.move_xy(*xy)
        w.move_z(z_um)
        be.open()
        r = Runner(be, registry=REG, control=AllowAll(),
                   config=RunnerConfig(position_interval_s=None))
        made.append(r)
        sink = Collect()
        r.subscribe(sink)
        r.start()
        r.set_experiment_session(SESSION, 1000.0)
        return r, sink, be

    yield build
    for r in made:
        r.shutdown("test teardown", timeout=T)
        assert r.wait_idle(T)


def steps_seen(sink: Collect, op_id: str) -> list[int]:
    return [e.data["step"] for e in sink.of("progress", op_id)]


# ---------------------------------------------------------------- the full rotation


def test_4x_to_100x_runs_the_seven_steps_and_waits_for_loading(make):
    r, sink, be = make()
    w = be.world
    be.lamp_on(token=GUARD_TOKEN)
    op_id = r.submit(start(target_state=5))
    req = sink.wait("confirm_required", op_id)
    assert req.data["kind"] == "manual_step" and req.data["context"]["immersion"] == "oil"
    # while waiting: Z retracted, stepped out +15 mm in Y, 100x in place, lights off
    assert w.z_um == pytest.approx(0.0)
    assert (w.x_um, w.y_um) == pytest.approx((HOLE[0], HOLE[1] + 15000.0))
    assert w.objective.key == "100x-Oil"
    assert not w.light.dia_on and not w.light.aura_on
    assert steps_seen(sink, op_id) == [1, 2, 3, 4]
    r.submit(confirm(op_id))
    fin = sink.wait("finished", op_id)
    s = fin.data["summary"]
    assert s["state"] == "done" and s["mode"] == "rotate"
    assert fin.data["end_state"]["state"] == "returned"
    assert (w.x_um, w.y_um) == pytest.approx(HOLE)
    assert w.z_um == pytest.approx(2800.0) and s["z_end_um"] == pytest.approx(2800.0)
    assert fin.data["manual_steps"][0]["step"] == LOAD_KEY
    assert r.snapshot()["awaiting_return"] is None


def test_progress_carries_the_contract_fields(make):
    r, sink, _ = make()
    op_id = r.submit(start(target_state=5))
    sink.wait("confirm_required", op_id)
    r.submit(confirm(op_id))
    sink.wait("finished", op_id)
    prog = sink.of("progress", op_id)
    for e in prog:
        if e.data["step"] in (2, 3, 4, 6):
            assert {"axis", "commanded", "readback", "pfs_in_range", "label_read"} <= set(
                e.data["data"]), e.data
    by_step = {e.data["step"]: e.data["data"] for e in prog if e.data["step"] != 7}
    assert by_step[2]["pfs_in_range"] == "Out of Range" and by_step[2]["commanded"] == 0.0
    assert by_step[3]["commanded"][1] == pytest.approx(HOLE[1] + 15000.0)
    assert by_step[4]["label_read"] == "6-Plan Apo LmbdD0.13 100x Oil"
    one = [e.data["data"] for e in prog if e.data["step"] == 7]
    assert [(a["step_index"], a["commanded"]) for a in one] == [(1, 2800.0)]  # 100x: cap 2800


def test_4x_approach_climbs_in_steps_with_step_index(make):
    r, sink, _ = make(nosepiece=5, z_um=2989.4)
    op_id = r.submit(start(target_state=0, approach_target_um=2850.0))
    sink.wait("finished", op_id)
    approach = [e.data["data"] for e in sink.of("progress", op_id) if e.data["step"] == 7]
    assert [a["step_index"] for a in approach] == list(range(1, len(approach) + 1))
    z = [a["commanded"] for a in approach]
    assert z[0] == 2800.0 and z[-1] == pytest.approx(2850.0)  # one move to the window, then
    assert all(0 < b - a <= 10.0 + 1e-9 for a, b in zip(z[1:], z[2:], strict=False))
    assert len(z) == 6  # 2800, 2810, ... 2850: never a jump to the target


def test_step_out_basis_and_approach_step_are_marked_provisional(make):
    r, sink, _ = make()
    op_id = r.submit(start(target_state=5))
    sink.wait("confirm_required", op_id)
    r.submit(confirm(op_id))
    sink.wait("finished", op_id)
    motions = sink.of("motion", op_id)
    assert any(PROVISIONAL in str(m.data.get("basis")) for m in motions if m.data["axis"] == "z"
               and str(m.data.get("how")).startswith("approach"))
    step3 = next(e for e in sink.of("progress", op_id) if e.data["step"] == 3)
    assert step3.data["data"]["basis"]["basis"]["escape_dy_um"] == PROVISIONAL


# ---------------------------------------------------------------- interruptions


def test_abort_while_loading_leaves_awaiting_return_and_resume_brings_it_back(make):
    r, sink, be = make()
    w = be.world
    op_id = r.submit(start(target_state=5))
    sink.wait("confirm_required", op_id)
    r.submit(Command("abort", op_id=op_id, user_id=USER, session_id=SESSION))
    ab = sink.wait("aborted", op_id)
    assert ab.data["end_state"]["state"] == "awaiting_return"
    aw = r.snapshot()["awaiting_return"]
    assert aw["return_xy"] == pytest.approx(list(HOLE)) and aw["op"] == NAME
    assert w.z_um == pytest.approx(0.0)  # no exit path raises Z
    # any other motion is refused until the return
    other = r.submit(start(target_state=0))
    failed = sink.wait("preflight_failed", other)
    assert failed.data["checks"][0]["name"] == "awaiting_return"
    back = r.submit(start(resume=True))
    fin = sink.wait("finished", back)
    assert steps_seen(sink, back)[:1] == [6] and set(steps_seen(sink, back)) == {6, 7}
    assert (w.x_um, w.y_um) == pytest.approx(HOLE) and w.z_um == pytest.approx(2800.0)
    assert fin.data["summary"]["start"]["resumed_from"] == op_id
    assert r.snapshot()["awaiting_return"] is None


def test_loading_not_done_finishes_away_from_the_sample(make):
    r, sink, be = make()
    op_id = r.submit(start(target_state=5))
    sink.wait("confirm_required", op_id)
    r.submit(confirm(op_id, ok=False))
    fin = sink.wait("finished", op_id)
    assert fin.data["end_state"]["state"] == "awaiting_return"
    assert r.snapshot()["awaiting_return"]["return_xy"] == pytest.approx(list(HOLE))
    assert be.world.z_um == pytest.approx(0.0)


def test_z_readback_error_stops_at_the_retract_and_nothing_moves_in_xy(make):
    r, sink, be = make()
    be.inject_faults(z_readback_error_um=-1.0)  # commanded 0, reads -1
    op_id = r.submit(start(target_state=5))
    err = sink.wait("error", op_id)
    assert "ZDrive" in err.data["message"] or "commanded" in err.data["message"]
    assert (be.world.x_um, be.world.y_um) == pytest.approx(HOLE)
    assert be.world.objective.key == "4x"
    assert r.snapshot()["awaiting_return"] is None  # still at the sample: no return needed


# ---------------------------------------------------------------- other modes


def test_100x_to_4x_dry_target_skips_step_out_and_loading(make):
    r, sink, be = make(nosepiece=5, z_um=2989.4)
    op_id = r.submit(start(target_state=0))
    fin = sink.wait("finished", op_id)
    assert "confirm_required" not in sink.kinds(op_id)
    assert steps_seen(sink, op_id)[:5] == [1, 2, 4, 6, 7]
    assert be.world.objective.key == "4x" and be.world.z_um == pytest.approx(2800.0)
    assert (be.world.x_um, be.world.y_um) == pytest.approx(HOLE)
    assert fin.data["summary"]["state"] == "done"


def test_reload_steps_out_and_back_without_rotating(make):
    r, sink, be = make(nosepiece=5, z_um=2989.4)
    op_id = r.submit(start(reload=True))
    sink.wait("confirm_required", op_id)
    assert be.world.y_um == pytest.approx(HOLE[1] + 15000.0)
    r.submit(confirm(op_id))
    fin = sink.wait("finished", op_id)
    assert 4 not in steps_seen(sink, op_id)
    assert be.world.objective.key == "100x-Oil" and fin.data["summary"]["mode"] == "reload"


# ---------------------------------------------------------------- preflight refusals


@pytest.mark.parametrize("args, check", [
    ({"target_state": 0}, "target_differs"),  # already on 4x
    ({"target_state": 9}, "target_lens"),
    ({}, "mode"),
    ({"target_state": 5, "resume": True}, "mode"),
    ({"target_state": 5, "approach_step_um": 20.0}, "approach_step"),
    ({"target_state": 5, "approach_target_um": 3300.0}, "approach_target"),
    ({"target_state": 5, "approach_target_um": 3200.0}, "approach_target"),  # 100x WD 130 um
    ({"target_state": 5, "approach_target_um": 2801.0}, "approach_target"),
    ({"resume": True}, "awaiting_return"),
])
def test_preflight_refusals(make, args, check):
    r, sink, be = make()
    op_id = r.submit(start(**args))
    failed = sink.wait("preflight_failed", op_id)
    bad = [c["name"] for c in failed.data["checks"] if not c["ok"]]
    assert any(n.startswith(check) for n in bad), failed.data["checks"]
    assert be.world.z_um == pytest.approx(3048.7)  # nothing moved


@pytest.mark.parametrize("state, key", [(1, "10x"), (3, "40x-WI")])
def test_preflight_refuses_a_lens_without_a_working_distance(make, monkeypatch, state, key):
    monkeypatch.delitem(FREE_WD_UM, key)
    r, sink, be = make()
    failed = sink.wait("preflight_failed", r.submit(start(target_state=state)))
    bad = [c["name"] for c in failed.data["checks"] if not c["ok"]]
    assert any(n.startswith("target") for n in bad), failed.data["checks"]
    assert be.world.z_um == pytest.approx(3048.7)  # nothing moved


def test_step_out_past_the_stage_y_limit_is_refused(make):
    r, sink, be = make(xy=(HOLE[0], 30000.0))  # +15 mm passes the 37.5 mm mock travel
    op_id = r.submit(start(target_state=5))
    failed = sink.wait("preflight_failed", op_id)
    step = next(c for c in failed.data["checks"] if c["name"] == "step_out")
    assert not step["ok"] and "outside the stage Y travel" in step["why"]


# ---------------------------------------------------------------- plan and clearance


def test_plan_has_the_screen_shape_without_hardware(make):
    r, _, _ = make()
    p = r.plan(start(target_state=5))["plan"]
    esc = p["escape"]
    assert set(esc) >= {"allowed", "reason", "sign", "dy_um", "mark", "default"}
    assert esc["sign"] == "+" and esc["dy_um"] == pytest.approx(15000.0)
    assert esc["mark"] == PROVISIONAL and esc["default"] is True
    assert p["immersion"] == "oil" and [s["step"] for s in p["steps"]] == list(range(1, 8))
    assert p["approach"]["step_um"] == 10.0 and p["approach"]["mark"] == PROVISIONAL
    dry = r.plan(start(target_state=0))["plan"]["escape"]
    assert dry["default"] is False


def test_escape_plan_reads_the_refusal_from_step_out_target():
    ok = escape_plan((HOLE[0], HOLE[1]), (-37500.0, 37500.0), True)
    assert ok["allowed"] is True and ok["target_y_um"] == pytest.approx(HOLE[1] + 15000.0)
    no = escape_plan((HOLE[0], 30000.0), (-37500.0, 37500.0), True)
    assert no["allowed"] is False and "outside the stage Y travel" in no["reason"]
    unknown = escape_plan(None, None, True)
    assert unknown["allowed"] is None and unknown["reason"].startswith("checked at preflight")


def test_step_out_target_refuses_without_y_travel():
    be = SimpleNamespace(info=lambda: SimpleNamespace(stage_limits=SimpleNamespace(y_um=None)))
    with pytest.raises(GuardError, match="no stage Y limit"):
        step_out_target(be, 0.0, 0.0)


def test_clearance_is_always_a_real_check():
    assert ObjectiveChange.approaches is True
    labels = ["1-Plan Apo LmbdD20 4x"]
    ctx = SimpleNamespace(aborted=False, args={"approach_target_um": 2850.0},
                          backend=SimpleNamespace(nosepiece=lambda: labels[0]))
    op = ObjectiveChange(ctx)
    op._approach_label = labels[0]
    clear = op.clearance()
    assert clear is not None
    assert clear(2800.0) and clear(2850.0)
    assert not clear(2851.0)  # past the asked target
    labels[0] = "6-Plan Apo LmbdD0.13 100x Oil"
    assert not clear(2810.0)  # the lens changed under the approach
    labels[0] = "1-Plan Apo LmbdD20 4x"
    ctx.aborted = True
    assert not clear(2810.0)


def test_100x_clearance_caps_at_2800_whatever_the_target():
    label = "6-Plan Apo LmbdD0.13 100x Oil"
    ctx = SimpleNamespace(aborted=False, args={"approach_target_um": 3200.0},
                          backend=SimpleNamespace(nosepiece=lambda: label))
    op = ObjectiveChange(ctx)
    op._approach_label = label
    clear = op.clearance()
    assert clear(2800.0) and not clear(2810.0)
    assert approach_cap_um("100x-Oil")[0] == 2800.0 and approach_cap_um("4x")[0] == 3200.0
    assert approach_cap_um(None)[0] == 2800.0  # unknown lens: the strict cap


def test_unverified_lights_off_stops_before_any_motion(make):
    r, sink, be = make()
    be.all_off = lambda: [Readback.of("DiaLamp", "State", 0, 1)]  # lamp still reads on
    op_id = r.submit(start(target_state=5))
    err = sink.wait("error", op_id)
    assert "light not verified" in err.data["message"]
    assert be.world.z_um == pytest.approx(3048.7) and be.world.objective.key == "4x"


def test_immersion_kinds():
    assert immersion_of("100x-Oil") == "oil" and immersion_of("40x-WI") == "water"
    assert immersion_of("4x") is None and immersion_of(None) is None


# ---------------------------------------------------------------- sample events


class FakeSession:
    writable = True

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def sample_event(self, kind: str, **payload) -> None:
        self.events.append((kind, payload))


def test_rotation_writes_objective_changed_to_the_open_session(make):
    r, sink, _ = make()
    session = FakeSession()
    r.sample_seat = SimpleNamespace(session_for=lambda sid: session if sid == SESSION else None)
    op_id = r.submit(start(target_state=5))
    sink.wait("confirm_required", op_id)
    r.submit(confirm(op_id))
    fin = sink.wait("finished", op_id)
    kinds = [k for k, _ in session.events]
    assert kinds == [STEPPED_OUT, OBJECTIVE_CHANGED, STEPPED_BACK]  # away, rotated, back
    assert session.events[1][1] == {
        "from_key": "4x", "to_key": "100x-Oil", "label": "6-Plan Apo LmbdD0.13 100x Oil"}
    out = session.events[0][1]
    assert out["return_xy"] == pytest.approx(list(HOLE))
    assert out["step_out_xy"][1] == pytest.approx(HOLE[1] + 15000.0)
    s = fin.data["summary"]
    assert s["sample_event"]["written"] and s["stepped_out"]["written"]
    assert s["stepped_back"]["written"]


def test_abort_away_leaves_the_step_out_open_until_resume_closes_it(make):
    r, sink, _ = make()
    session = FakeSession()
    r.sample_seat = SimpleNamespace(session_for=lambda sid: session)
    op_id = r.submit(start(target_state=5))
    sink.wait("confirm_required", op_id)
    r.submit(Command("abort", op_id=op_id, user_id=USER, session_id=SESSION))
    sink.wait("aborted", op_id)
    assert [k for k, _ in session.events] == [STEPPED_OUT, OBJECTIVE_CHANGED]  # still away
    sink.wait("finished", r.submit(start(resume=True)))
    assert [k for k, _ in session.events][-1] == STEPPED_BACK


def test_dry_change_writes_no_step_events(make):
    r, sink, _ = make(nosepiece=5, z_um=2989.4)
    session = FakeSession()
    r.sample_seat = SimpleNamespace(session_for=lambda sid: session)
    sink.wait("finished", r.submit(start(target_state=0)))
    assert [k for k, _ in session.events] == [OBJECTIVE_CHANGED]


def test_no_session_logs_and_still_completes(make):
    r, sink, be = make(nosepiece=5, z_um=2989.4)
    op_id = r.submit(start(target_state=0))
    fin = sink.wait("finished", op_id)
    ev = fin.data["summary"]["sample_event"]
    assert ev["written"] is False and ev["why"] == "no sample seat installed"
    assert any("objective_changed not written" in e.data.get("text", "")
               for e in sink.of("log", op_id))
    assert be.world.objective.key == "4x"


def test_unmeasured_working_distance_reason(make, monkeypatch):
    monkeypatch.delitem(FREE_WD_UM, "10x")
    r, sink, _ = make()
    failed = sink.wait("preflight_failed", r.submit(start(target_state=1)))
    wd = next(c for c in failed.data["checks"] if c["name"] == "target_working_distance")
    assert wd["why"].startswith("free working distance not measured")


# ---------------------------------------------------------------- T-029c: intent first


SAMPLE_ID = "20261002_0900_1"


@pytest.fixture
def records(tmp_path):
    """A real T-019 records store and an open session, as the sample seat hands them out."""
    from dino_autofocus.records import ExperimentSession, FolderStore, RecordsConfig

    store = FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                      data_root=tmp_path / "data"))
    session = ExperimentSession.open(store, USER, SAMPLE_ID)
    yield store, session, tmp_path / "samples"
    if session.writable:
        session.close()


def away(records) -> bool:
    from dino_autofocus.engine.sample import read_sample

    store, _, root = records
    return read_sample(store, SAMPLE_ID, root).awaiting_return


def seat(r, records) -> None:
    r.sample_seat = SimpleNamespace(session_for=lambda sid: records[1])


def test_a_step_out_that_fails_part_way_still_reads_as_away(make, records):
    r, sink, be = make()
    seat(r, records)
    real = be.move_xy

    def stalls(x, y, *, token, timeout_s=None):
        if y > HOLE[1] + 1000:  # the step-out: the stage gets half way, then the wait fails
            be.world.move_xy(x, (y + be.world.y_um) / 2)
            raise TimeoutError("XY move did not finish")
        return real(x, y, token=token, timeout_s=timeout_s)

    be.move_xy = stalls
    op_id = r.submit(start(target_state=5))
    sink.wait("error", op_id)
    assert be.world.y_um > HOLE[1] + 1000  # off the sample
    assert away(records) is True  # written before the move
    assert r.snapshot()["awaiting_return"]["return_xy"] == pytest.approx(list(HOLE))


def test_a_full_change_ends_with_the_sample_not_away(make, records):
    r, sink, _ = make()
    seat(r, records)
    op_id = r.submit(start(target_state=5))
    sink.wait("confirm_required", op_id)
    assert away(records) is True  # stepped out, waiting for oil
    r.submit(confirm(op_id))
    sink.wait("finished", op_id)
    assert away(records) is False


def test_stepped_back_needs_a_confirmed_readback(make, records):
    r, sink, be = make()
    seat(r, records)
    op_id = r.submit(start(target_state=5))
    sink.wait("confirm_required", op_id)
    r.submit(Command("abort", op_id=op_id, user_id=USER, session_id=SESSION))
    sink.wait("aborted", op_id)
    be.inject_faults(xy_readback_error_um=(20.0, 0.0))  # the stage reads 20 um off
    back = r.submit(start(resume=True))
    sink.wait("error", back)
    assert away(records) is True  # no stepped_back without a confirmed return
    kinds = [e.kind for e in records[1].events()]
    assert kinds.count(STEPPED_OUT) == 1 and STEPPED_BACK not in kinds
