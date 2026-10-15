"""The M1 safety properties on the mock, each on a fresh bench (conftest `bench`):

- lights off on every non-normal end: abort, lights_off pre-emption, a stage fault, the
  local viewer leaving (D14), the session closing, shutdown;
- motion and light refused without the control grant or without an open session (rule 12),
  and the backend itself refusing motion that skips the guards;
- remote clients may abort and nothing else (D13).

The trace runs used here are the real edge_trace code on MockBackend, stopped early.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from e2e_helpers import OFF, OPERATOR

from dino_autofocus.auth import Action
from dino_autofocus.engine.backend import UnguardedMotion
from dino_autofocus.engine.backends.mock_world import SampleSpec
from dino_autofocus.engine.runner import CommandRefused

SPEC = SampleSpec()
TRACE = {"speed_um_s": 1000.0, "hole_diameter_mm": SPEC.hole_diameter_mm}


def at_the_edge(bench) -> None:
    """The operator's hands: joystick to the chamber edge, focus knob to the 4x focus."""
    world = bench.backend.world
    r = SPEC.hole_diameter_mm * 500 + 300
    world.move_xy(SPEC.hole_centre_um[0] + r * math.cos(0.7),
                  SPEC.hole_centre_um[1] + r * math.sin(0.7))
    world.move_z(world.in_focus_z())
    bench.backend.set_roi(1200)


def lamp_is_on(op_id):
    def pred(e) -> bool:
        return (e.kind == "light_changed" and e.op_id == op_id
                and any(r["device"] == "DiaLamp" and str(r["read"]) == "1"
                        for r in e.data.get("records") or e.data.get("readbacks", [])))
    return pred


def tracing(bench) -> str:
    """An edge_trace that is running with the lamp on."""
    at_the_edge(bench)
    op_id = bench.start("edge_trace", TRACE)
    bench.wait_for("confirm_required", op_id)
    bench.answer(op_id, "start_trace")
    bench.wait(lamp_is_on(op_id))
    assert bench.lights()["DiaLamp"] == "1"
    return op_id


def summary_of(end) -> dict:
    """The runner's record of the operation that ended with `end`."""
    return json.loads((Path(end.data["record_dir"]) / "summary.json").read_text(encoding="utf-8"))


def ended_all_off(bench, end, state: str) -> None:
    assert end.kind == state, end.data
    assert bench.lights() == OFF
    lights = end.data["end_state"]["lights"]
    assert lights["rule"] == "all_off" and lights["verified"], lights
    s = summary_of(end)
    assert s["status"] == state and (s["user_id"], s["session_id"]) == (
        OPERATOR, bench.session.session_id)


# -- lights off on every non-normal end ------------------------------------------------------

def test_abort_mid_trace_switches_everything_off(bench):
    bench.ready()
    op_id = tracing(bench)
    bench.submit("abort", op_id=op_id, grant=None)
    end = bench.wait_end(op_id)
    ended_all_off(bench, end, "aborted")
    # the runner's one edge_trace record agrees, and the trace's own last word in its log is
    # the abort (the registered EdgeTraceOp runs inside the runner's record; T-032b, manager)
    folder = Path(end.data["record_dir"])
    assert [p.parent for p in bench.sample.dir.glob("edge_trace_*/summary.json")] == [folder]
    rec = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert rec["status"] == "aborted" and rec["lights_off"]["verified"]
    log = [json.loads(line) for line in
           (folder / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    trace = [e["data"] for e in log
             if e["kind"] == "progress" and e["data"].get("op") == "edge_trace"]
    assert trace[-1]["status"] == "track_stop" and trace[-1]["data"]["why"] == "aborted"
    assert all(t["status"] != "track_start" for t in trace[1:])  # a start comes first, if any


def test_lights_off_preempts_a_running_trace(bench):
    bench.ready()
    op_id = tracing(bench)
    stop = bench.submit("lights_off", grant=None, user=None)  # anyone, no grant, no login
    ended_all_off(bench, bench.wait_end(op_id), "aborted")
    off = bench.wait_end(stop)
    assert off.kind == "finished" and off.data["summary"]["verified"]


def test_a_stage_readback_fault_ends_in_error_with_lights_off(bench):
    bench.ready()
    at_the_edge(bench)
    bench.backend.inject_faults(xy_readback_error_um=(40.0, 0.0))  # the stage lies by 40 um
    end = bench.run("edge_trace", TRACE)
    ended_all_off(bench, end, "error")
    assert "GuardError" in end.data["message"] and "XY" in end.data["message"]


def test_the_watched_trace_stops_when_the_local_viewer_leaves(bench):
    bench.ready()  # local_gone_abort_s is 0.3 s on this bench
    op_id = tracing(bench)
    bench.runner.set_local_viewers(0)
    ended_all_off(bench, bench.wait_end(op_id), "aborted")


def test_closing_the_session_mid_trace_stops_it(bench):
    bench.ready()
    op_id = tracing(bench)
    bench.runner.set_experiment_session(None)
    ended_all_off(bench, bench.wait_end(op_id), "aborted")


def test_shutdown_switches_off_a_light_left_on(bench):
    bench.ready()
    assert bench.run("light_set", {"mode": "aura", "line": "GREEN", "percent": 5}).kind == \
        "finished"
    assert bench.lights()["Aura"] == "1"  # light_set keeps its light
    rec = bench.runner.shutdown("operator closes the app")
    assert bench.lights() == OFF
    assert json.dumps(rec)  # the shutdown record is JSON


# -- rule 12: control and session ------------------------------------------------------------

def test_motion_and_light_need_the_operators_grant(bench):
    bench.ready()
    at_the_edge(bench)
    for op, args in (("edge_trace", TRACE), ("light_set", {"mode": "brightfield"})):
        with pytest.raises(CommandRefused, match="equipment control"):
            bench.start(op, args, grant=None)
        with pytest.raises(CommandRefused, match="equipment control"):
            bench.start(op, args, grant="made-up-token")
        with pytest.raises(CommandRefused, match="equipment control"):  # not Olga's grant
            bench.start(op, args, user="olga@example.test")
    bench.control.release(bench.login_token)
    with pytest.raises(CommandRefused, match="equipment control"):  # given back: gone
        bench.start("edge_trace", TRACE)
    assert bench.lights() == OFF
    assert not [e for e in bench.events if e.kind == "motion"]


def test_motion_and_light_need_an_open_session(bench):
    bench.take_control()
    for op, args in (("edge_trace", TRACE), ("light_set", {"mode": "brightfield"})):
        with pytest.raises(CommandRefused, match="no open experiment session"):
            bench.start(op, args)
    assert bench.run("status").kind == "finished"  # reading needs no session
    bench.open_session()
    with pytest.raises(CommandRefused, match="is not the open session"):
        bench.start("light_set", {"mode": "brightfield"}, session_id="20260101-0000-other-1")


def test_the_backend_refuses_motion_that_skips_the_guards(bench):
    b = bench.backend
    p = b.positions()
    for fake_token in (None, object(), bench.control_token, "GUARD_TOKEN"):
        with pytest.raises(UnguardedMotion):
            b.move_xy(p.x_um + 100, p.y_um, token=fake_token)
        with pytest.raises(UnguardedMotion):
            b.move_z(p.z_um + 10, token=fake_token)
        with pytest.raises(UnguardedMotion):
            b.lamp_on(token=fake_token)
    assert b.positions().x_um == pytest.approx(p.x_um) and bench.lights() == OFF


# -- D13: remote clients abort and nothing else ------------------------------------------------

def test_a_remote_client_may_abort_and_nothing_else(bench):
    bench.ready()
    at_the_edge(bench)
    for kind, op in (("start", "status"), ("start", "light_set"), ("lights_off", "")):
        with pytest.raises(CommandRefused, match="abort only"):
            bench.submit(kind, op, args={"mode": "brightfield"} if op == "light_set" else {},
                         remote=True)
    op_id = bench.start("edge_trace", TRACE)
    bench.wait_for("confirm_required", op_id)
    with pytest.raises(CommandRefused, match="abort only"):
        bench.answer(op_id, "start_trace", remote=True)
    bench.submit("abort", op_id=op_id, remote=True, user=None, grant=None)
    end = bench.wait_end(op_id)
    assert end.kind == "aborted" and bench.lights() == OFF
    assert any(e.kind == "log" and e.data.get("rule") == "D13" for e in bench.events)


def test_the_server_side_check_lets_anyone_stop_but_only_local_operators_operate(bench):
    bench.take_control()
    c, login, grant = bench.control, bench.login_token, bench.control_token
    assert c.authorize(Action.STOP, None, local=False).allowed  # no login, remote
    assert c.authorize(Action.OPERATE, login, grant, local=True).allowed
    assert not c.authorize(Action.OPERATE, login, grant, local=False).allowed
    assert not c.authorize(Action.OPERATE, login, None, local=True).allowed
    viewer = bench.login("vera@example.test")
    assert not c.authorize(Action.OPERATE, viewer, grant, local=True).allowed


# -- the bench itself ------------------------------------------------------------------------

def test_a_wait_that_never_matches_fails_fast_and_says_what_it_waited_for(bench):
    bench.take_control()
    assert bench.run("status").kind == "finished"
    with pytest.raises(AssertionError) as err:
        bench.wait(lambda e: False, timeout=0.2, what="an event that never comes")
    msg = str(err.value)
    assert "an event that never comes" in msg and "Last events" in msg and "finished:" in msg
