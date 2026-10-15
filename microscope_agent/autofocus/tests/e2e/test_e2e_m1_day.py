"""One scripted M1 day on the mock (PLAN 8 M1: F1-F5 without hardware), step by step.

The steps run in file order on one shared `day` bench (conftest) and go through the T-011
runner with `Command`s, as the server will send them; T-009's server is the last step. A step
whose operation has not landed skips with its task number. When it lands, `pending(...)`
turns into a skip saying the step is still to be written here (a T-035 follow-up), so
nothing passes by accident.
"""

from __future__ import annotations

import json
import math

import pytest
from e2e_helpers import OFF, OPERATOR, after, need, read_jsonl

from dino_autofocus.auth import ControlBusy, ControlError
from dino_autofocus.engine.backends.mock_world import SampleSpec
from dino_autofocus.engine.runner import CommandRefused
from dino_autofocus.engine.sample import read_sample
from dino_autofocus.records import GitFolderStore, SessionClosedError, open_session, sample_state

SPEC = SampleSpec()  # the sample MockBackend(seed=0) holds: 6.144 mm hole at (8026, 571.6)
#: the camera ROI for the day's frames: a 1200 px field keeps the trace near 20 s and each
#: rendered frame at a quarter of the full sensor's memory (T-035b); the full 2400 px sensor
#: works too (the trace then takes about 100 s)
TRACE_ROI_PX = 1200


def pending(module: str, task: str) -> None:
    need(module, task)
    pytest.skip(f"{task} is on main; this step of the day is still to be written (T-035)")


def view(day):
    """What the sample, map and sessions screens read (T-027 `read_sample`)."""
    return read_sample(day.store, day.sample.id, day.samples_root, day.open_session_id)


def at_the_edge(day) -> None:
    """The operator's hands: joystick to the chamber edge, focus knob to the 4x focus."""
    world = day.backend.world
    r = SPEC.hole_diameter_mm * 500 + 300
    world.move_xy(SPEC.hole_centre_um[0] + r * math.cos(0.7),
                  SPEC.hole_centre_um[1] + r * math.sin(0.7))
    world.move_z(world.in_focus_z())


def summaries(day) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(day.sample.dir.glob("*/summary.json"))]


# -- morning: who is at the microscope ------------------------------------------------------

def test_01_operator_logs_in(day):
    assert not day.logins.login(OPERATOR, "not-the-password").ok
    day.login_token = day.login(OPERATOR)
    assert day.logins.get(day.login_token).role == "operator"
    day.done.add("login")


def test_02_nothing_runs_until_the_operator_holds_control(day):
    after(day, "login")
    with pytest.raises(CommandRefused, match="equipment control"):
        day.start("status", grant=None)
    with pytest.raises(ControlError):  # remote viewing never takes control
        day.control.acquire(day.login_token, local=False)
    with pytest.raises(ControlError):  # a viewer cannot operate
        day.control.acquire(day.login("vera@example.test"), local=True)

    day.control_token = day.control.acquire(day.login_token, local=True).token
    assert day.control.holder().user_id == OPERATOR
    with pytest.raises(ControlBusy):  # one operator at a time
        day.control.acquire(day.login("olga@example.test"), local=True)
    with pytest.raises(CommandRefused, match="equipment control"):  # not Olga's grant
        day.start("status", user="olga@example.test")
    day.runner.set_local_viewers(1)  # the operator's own browser on the microscope PC
    day.done.add("control")


def test_03_status_before_the_session(day):
    after(day, "control")
    end = day.run("status")
    assert end.kind == "finished", end.data
    st = end.data["summary"]["status"]
    assert st["nosepiece_label"].endswith("4x") and st["lights"] == OFF
    with pytest.raises(CommandRefused, match="no open experiment session"):
        day.start("light_set", {"mode": "brightfield"})  # light needs a session (D15)
    day.done.add("status_before")


def test_04_operator_picks_a_sample_and_opens_a_session(day):
    after(day, "control")
    s = day.open_session()  # sample_new through the runner, then the session for it
    assert open_session(day.store)["session_id"] == s.session_id
    info = json.loads((s.layout.root / "session.json").read_text(encoding="utf-8"))
    assert (info["user_id"], info["sample_id"], info["status"]) == (
        OPERATOR, day.sample.id, "open")
    assert day.sample.dir.is_dir()
    assert day.runner.snapshot()["sample"]["sample_id"] == day.sample.id
    assert view(day).created is not None  # sample_created, the sample's first event
    day.done.add("session")


# -- F2: what hardware is there ---------------------------------------------------------------

def test_05_f2_hardware_scan_and_gates(day):
    after(day, "session")
    pending("dino_autofocus.engine.operations.hardware_scan", "T-028")


# -- F3: the sample goes on -------------------------------------------------------------------

#: the operator's entries on the sample screen (docs/screens/sample.md section 2)
GEOMETRY = {"sample_size_mm": list(SPEC.size_mm), "chamber_shape": "hole",
            "hole_diameter_mm": SPEC.hole_diameter_mm,
            "coverslip_thickness_um": SPEC.coverslip_um,
            "sample_thickness_um": 1000.0,  # the slide; the mock does not model it
            "orientation": "upright"}


def test_06_f3_sample_geometry_is_entered(day):
    after(day, "session")
    with pytest.raises(CommandRefused, match="equipment control"):
        day.start("sample_geometry_set", {"sample_id": day.sample.id, "values": GEOMETRY},
                  grant=None)
    bad = day.run("sample_geometry_set", {"sample_id": day.sample.id,
                                          "values": {"orientation": "sideways"}})
    assert bad.kind == "error" and bad.data["where"] == "preflight"  # refused, nothing written
    end = day.run("sample_geometry_set", {"sample_id": day.sample.id, "values": GEOMETRY})
    assert end.kind == "finished", end.data
    g = view(day).geometry
    assert {k: g[k]["value"] for k in GEOMETRY} == GEOMETRY
    assert all(g[k]["source"]["kind"] == "entered" and g[k]["source"]["by"] == OPERATOR
               for k in GEOMETRY)
    assert view(day).loading["geometry"]["done"] and not view(day).loading["confirmed"]
    day.done.add("geometry")


def test_07_f3_loading_is_confirmed_by_the_person_and_the_image(day):
    after(day, "geometry")
    at_the_edge(day)  # the image check needs structure in view: the chamber edge, in focus
    day.backend.set_roi(TRACE_ROI_PX)  # the edge is in a 1200 px field too; a quarter the memory
    end = day.run("loading_confirm_person", {"sample_id": day.sample.id})
    assert end.kind == "finished", end.data
    end = day.run("loading_check_image", {"sample_id": day.sample.id})
    assert end.kind == "finished", end.data
    assert end.data["summary"]["ok"], end.data["summary"]
    assert day.lights() == OFF  # the lamp for the frame is off again
    loading = view(day).loading
    assert loading["person"]["done"] and loading["image"]["ok"] and loading["confirmed"]
    assert loading["person"]["by"] == OPERATOR
    assert (day.sample.dir / end.data["summary"]["frame_ref"]).is_file()
    day.done.add("loaded")


# -- F4: find the hole, map the sample ---------------------------------------------------------

def test_08_f4_edge_trace_fits_the_hole(day):
    after(day, "loaded")
    b = day.backend
    assert b.nosepiece().endswith("4x")
    at_the_edge(day)
    b.set_roi(TRACE_ROI_PX)
    z_before = b.positions().z_um

    # a whole loop: about 20 s alone, a few minutes when the desktop is loaded
    end = day.run("edge_trace", {"speed_um_s": 1000.0,
                                 "hole_diameter_mm": SPEC.hole_diameter_mm}, timeout=300)
    b.set_roi(0)
    assert end.kind == "finished", end.data
    asked = [e.data["key"] for e in day.events
             if e.kind == "confirmed" and e.op_id == end.op_id]
    assert asked == ["start_trace"]  # a fresh sample: no earlier fit to replace
    out = end.data["summary"]
    assert out["why"] == "back where the edge was first seen: full loop"
    hole = out["hole"]
    assert math.dist(hole["centre_um"], SPEC.hole_centre_um) < 30
    assert hole["diameter_mm"] == pytest.approx(SPEC.hole_diameter_mm, rel=0.02)
    assert b.positions().z_um == pytest.approx(z_before)  # Z never moved
    assert day.lights() == OFF and end.data["end_state"]["lights"]["rule"] == "restore"
    assert [e for e in day.events if e.kind == "motion" and e.op_id == end.op_id]
    day.trace = out
    day.done.add("edge_trace")


def test_09_the_trace_lands_in_the_sample_record(day):
    """The edge_trace op wrote every traced point (`boundary_point`) and the fit (`hole_fit`)
    as sample events through the open session itself (T-032 stage 2); map.json is the view
    regenerated from them. The sample view must give back the traced hole and loop."""
    after(day, "edge_trace")
    s, hole = day.session, day.trace["hole"]
    points = [list(p) for p in day.sample.load_map().boundary]  # derived from the events
    assert len(points) == day.trace["n_points"]
    kinds = [e.kind for e in s.events()]
    assert kinds.count("boundary_point") == len(points) and kinds.count("hole_fit") == 1

    v = view(day)
    assert [[p["x_um"], p["y_um"]] for p in v.boundary] == points
    assert v.hole["centre_um"] == hole["centre_um"]
    assert v.hole["diameter_mm"] == hole["diameter_mm"]
    assert v.hole_loop["closed"]
    assert v.sessions == [s.session_id]
    st = sample_state(day.store, day.sample.id)
    assert len(st.boundary) == len(points) and st.sessions == [s.session_id]
    assert all(e.user_id == OPERATOR and e.session_id == s.session_id for e in s.events())
    day.done.add("fold")


def test_10_f4_scan_4x(day):
    after(day, "fold")
    pending("dino_autofocus.engine.operations.scan_4x", "T-031")


def test_11_f4_sample_map(day):
    after(day, "fold")
    pending("dino_autofocus.engine.operations.sample_map", "T-032")


def test_12_f4_flag_and_goto_xy(day):
    after(day, "fold")
    pending("dino_autofocus.engine.operations.sample_map", "T-032")


# -- F5: 4x -> 100x Oil and focus -------------------------------------------------------------

def test_13_f5_objective_change_to_100x_oil(day):
    after(day, "fold")
    pending("dino_autofocus.engine.operations.objective_change", "T-029")


def test_14_f5_focus_100x(day):
    after(day, "fold")
    pending("dino_autofocus.engine.operations.focus_100x", "T-031")


# -- evening: lights, records, close ------------------------------------------------------------

def test_15_light_set_stays_through_status_then_lights_off(day):
    after(day, "session")
    end = day.run("light_set", {"mode": "brightfield"})
    assert end.kind == "finished" and end.data["end_state"]["lights"]["rule"] == "keep"
    assert day.lights()["DiaLamp"] == "1"
    assert day.run("status").kind == "finished"
    assert day.lights()["DiaLamp"] == "1"  # a status does not switch the light set before
    stop = day.submit("lights_off", grant=None)  # the stop needs no control grant
    end = day.wait_end(stop)
    assert end.kind == "finished" and end.data["summary"]["verified"]
    assert day.lights() == OFF
    day.done.add("lights")


def test_16_every_record_carries_the_user_and_the_session(day):
    after(day, "lights", "fold")
    sid = day.session.session_id
    recs = summaries(day)
    ops = [r["op"] for r in recs]
    # boundary points come from edge_trace itself now (T-032 stage 2), not boundary_mark runs
    assert {"edge_trace", "light_set", "status", "lights_off", "sample_geometry_set",
            "loading_confirm_person", "loading_check_image"} <= set(ops)
    for r in recs:  # every runner record
        assert r["user_id"] == OPERATOR, r["op_id"]
        assert r["session_id"] == sid, r["op_id"]
    lay = day.session.layout
    for path in (lay.log, lay.sample_events, lay.manual_steps):
        for line in read_jsonl(path):
            assert (line["user_id"], line["session_id"]) == (OPERATOR, sid), path.name
    for ev in day.events:  # what every screen heard
        if ev.op_id and ev.kind in ("started", "finished"):
            assert ev.user_id == OPERATOR, (ev.kind, ev.op_id)
    day.done.add("records")


def test_17_the_day_closes(day):
    after(day, "session")
    s = day.session
    day.runner.set_experiment_session(None)  # closing is a stop: lights off
    with pytest.raises(CommandRefused, match="no open experiment session"):
        day.start("light_set", {"mode": "brightfield"}, session_id=s.session_id)
    day.control.release(day.login_token)
    assert day.control.holder() is None
    with pytest.raises(CommandRefused, match="equipment control"):
        day.start("status")
    s.close("end of the M1 mock day")
    with pytest.raises(SessionClosedError):
        s.log("after close")
    assert open_session(day.store) is None
    assert day.logins.logout(day.login_token)
    assert day.lights() == OFF

    released = [e for e in day.audit.entries() if e["kind"] == "control_released"]
    assert released[-1]["user_id"] == OPERATOR
    assert released[-1]["session_id"] == s.session_id  # stamped while the session was open
    if isinstance(day.store, GitFolderStore):  # the records repository holds the day
        log = day.store._git("log", "--format=%ae %s").stdout.splitlines()
        assert log and all(line.startswith(OPERATOR) for line in log)
        assert not day.store.uncommitted(day.store._rel(s.session_id))
    day.done.add("closed")


def test_18_the_same_day_through_the_server(day):
    pending("dino_autofocus.server.app", "T-009")


def test_19_stand_ins_in_use_are_the_unregistered_ones(day):
    """The suite says which merged operations still run through a conftest stand-in."""
    from dino_autofocus.engine.runner import OPERATIONS

    assert set(day.stand_ins) == {n for n in ("status", "light_set", "edge_trace")
                                  if OPERATIONS.get(n) is None}
