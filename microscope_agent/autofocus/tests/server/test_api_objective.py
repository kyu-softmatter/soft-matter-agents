"""The objective area's read routes (T-104, docs/screens/objective.md section 1).

The plan comes from a real `Runner.plan()` over MockBackend (T-029's objective_change), so the
mapping is tested against the engine's own plan shape; state and lens rows come from a snapshot
shaped like `Runner.snapshot()`. Mock only: no hardware, no real login. Every runner is shut
down at the end of its test.
"""

from __future__ import annotations

from typing import Any

import pytest

from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.guards import FREE_WD_UM, PROVISIONAL
from dino_autofocus.engine.operations.objective_change import ObjectiveChange
from dino_autofocus.engine.runner import AllowAll, Registry, Runner, RunnerConfig
from dino_autofocus.server.api.objective import ceiling_for

T = 10.0
OBJECTIVES = [
    {"state": 0, "label": "1-Plan Apo LmbdD20 4x", "magnification": 4.0, "pixel_um": 1.625,
     "free_wd_um": 20000.0},
    {"state": 3, "label": "4-Plan Apo 40x WI", "magnification": 40.0, "pixel_um": 0.1625,
     "free_wd_um": None},
    {"state": 4, "label": "5-Plan Fluor 50x", "magnification": 50.0, "pixel_um": 0.13,
     "free_wd_um": None},
    {"state": 5, "label": "6-Plan Apo LmbdD0.13 100x Oil", "magnification": 100.0,
     "pixel_um": 0.065, "free_wd_um": 130.0},
]


def snapshot(**extra: Any) -> dict:
    snap = {
        "positions": {"x_um": 8026.0, "y_um": 571.6, "z_um": 3048.7},
        "running": [],
        "awaiting_return": None,
        "session": None,
        "backend_info": {"kind": "mock", "objectives": OBJECTIVES,
                         "stage_limits": {"y_um": [-50000.0, 50000.0]}},
        "hardware": {"last_status": {"op_id": "status_1", "t": 1759370000.0, "summary": {
            "nosepiece_label": "1-Plan Apo LmbdD20 4x", "nosepiece_state": 0,
            "pfs_enabled": False, "pfs_locked": False, "pfs_in_range": "Out of Range"}}},
    }
    snap.update(extra)
    return snap


@pytest.fixture
def make_engine(engine):
    """`make_engine(runner=None, **snapshot_overrides)`: the conftest FakeEngine with a
    Runner-shaped snapshot and, when given, a real Runner's plan()."""
    base = type(engine)

    class _ObjectiveEngine(base):
        def __init__(self, runner: Runner | None = None, **snap: Any) -> None:
            super().__init__()
            self._runner, self._snap = runner, snapshot(**snap)

        def snapshot(self) -> dict:
            return self._snap

        def plan(self, cmd):
            assert self._runner is not None, "this test gave no runner"
            return self._runner.plan(cmd)

    def make(runner: Runner | None = None, **snap: Any):
        return _ObjectiveEngine(runner, **snap)

    make.base = base
    return make


@pytest.fixture
def runner():
    reg = Registry()
    reg.register(ObjectiveChange)
    be = MockBackend(seed=1)
    be.open()
    r = Runner(be, registry=reg, control=AllowAll(), config=RunnerConfig(position_interval_s=None))
    r.start()
    yield r
    r.shutdown("test teardown", timeout=T)
    assert r.wait_idle(T)


# -- state ------------------------------------------------------------------------------


def test_state_reads_lens_pfs_and_encoder_z_from_the_snapshot(make_client, make_engine):
    c = make_client(make_engine())
    r = c.get("/api/objective/state")
    assert r.status_code == 200
    s = r.json()
    assert (s["nosepiece_state"], s["label"]) == (0, "1-Plan Apo LmbdD20 4x")
    assert s["pixel_um"] == 1.625 and s["z_um"] == 3048.7
    assert s["pfs"] == {"enabled": False, "locked": False, "in_range": "Out of Range"}
    assert s["awaiting_return"] is None and s["running"] is None


def test_state_shows_awaiting_return_and_a_running_change(make_client, make_engine):
    eng = make_engine(
        awaiting_return={"return_xy": [8026.0, 571.6], "since": 1759370100.0,
                         "objective_before": "1-Plan Apo LmbdD20 4x"},
        running=[{"op_id": "objective_change_3", "op": "objective_change", "state": "running"}])
    s = make_client(eng).get("/api/objective/state").json()
    assert s["awaiting_return"]["return_xy_um"] == [8026.0, 571.6]
    assert s["running"] == {"op_id": "objective_change_3", "op": "objective_change",
                            "step": None, "n_steps": None}


def test_state_without_a_status_run_leaves_the_lens_unknown(make_client, make_engine):
    s = make_client(make_engine(hardware={"last_status": None})).get(
        "/api/objective/state").json()
    assert s["nosepiece_state"] is None and s["label"] is None and s["read_at"] is None


# -- lens rows --------------------------------------------------------------------------


def test_lens_rows_give_the_reason_per_lens(make_client, make_engine, monkeypatch):
    monkeypatch.delitem(FREE_WD_UM, "40x-WI")  # a lens without a value
    rows = {r["nosepiece_state"]: r for r in make_client(make_engine()).get(
        "/api/objective/lenses").json()}
    assert rows[0]["disabled_reason"] == "already on that objective" and not rows[0]["selectable"]
    assert rows[3]["disabled_reason"] == "no working distance value"  # 40x WI
    assert rows[3]["immersion"] == "water"
    assert rows[4]["disabled_reason"] == "not in the lens table"  # 50x: no guards row
    assert rows[5]["selectable"] and rows[5]["disabled_reason"] is None
    assert rows[5]["immersion"] == "oil" and rows[5]["working_distance_um"] == 130.0


def test_lens_rows_prefer_the_engine_objective_options(make_client, make_engine):
    class WithOptions(type(make_engine())):
        def objective_options(self):
            return [{"nosepiece_state": 5, "label": "6-Plan Apo LmbdD0.13 100x Oil",
                     "registry_key": "100x-Oil", "magnification": 100.0, "immersion": "oil",
                     "working_distance_um": 130.0, "selectable": False,
                     "disabled_reason": "engine says no"}]

    rows = make_client(WithOptions()).get("/api/objective/lenses").json()
    assert [r["disabled_reason"] for r in rows] == ["engine says no"]


# -- plan (real Runner.plan, T-029) -----------------------------------------------------


def test_plan_maps_the_engine_plan_for_4x_to_100x(make_client, make_engine, runner):
    p = make_client(make_engine(runner)).get(
        "/api/objective/plan", params={"target_state": 5}).json()
    assert [s["step"] for s in p["steps"]] == [1, 2, 3, 4, 5, 6, 7]
    assert "Step out" in p["steps"][2]["name"]
    esc = p["escape"]
    assert esc["sign"] == "+Y" and esc["dy_um"] == 15000.0
    assert esc["mark"] == PROVISIONAL and esc["default"] is True  # oil lens
    assert p["immersion"] == "oil"
    assert p["approach_target_um"] == 2800.0 and p["approach_step_um"] == 10.0
    assert p["approach_step_mark"] == PROVISIONAL
    assert p["refusal"] is None


def test_plan_without_a_position_is_not_a_refusal(make_client, make_engine, runner):
    # the runner polled no position, so the engine says "checked at preflight"
    esc = make_client(make_engine(runner)).get(
        "/api/objective/plan", params={"target_state": 5}).json()["escape"]
    assert esc["allowed"] is True and esc["reason"] is None
    assert esc["note"] and esc["note"].startswith("checked at preflight")


def test_plan_passes_escape_false_and_marks_the_lens_refusal(make_client, make_engine, runner):
    c = make_client(make_engine(runner))
    p = c.get("/api/objective/plan", params={"target_state": 5, "escape": "false"}).json()
    assert "skipped" in p["steps"][2]["name"].lower() or 3 not in [s["step"] for s in p["steps"]]
    p0 = c.get("/api/objective/plan", params={"target_state": 0}).json()
    assert p0["refusal"] == "already on that objective"


def test_plan_without_an_engine_plan_is_503(make_client, make_engine):
    r = make_client(make_engine.base()).get("/api/objective/plan", params={"target_state": 5})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "no_plan"
    assert r.headers["X-DinoAF-Refusal"] == "no_plan"


# -- 100x defaults ----------------------------------------------------------------------


def test_100x_centre_is_not_set_without_a_4x_plane(make_client, make_engine):
    d = make_client(make_engine()).get("/api/objective/focus100x/defaults").json()
    assert d["z_4x_focus_um"] is None and d["centre_um"] is None and d["ceiling_um"] is None
    assert (d["half_um"], d["step_um"], d["exposure_ms"], d["metric"]) == (40.0, 2.0, 20.0, "peak")
    assert d["immersion_loaded_this_session"] is False


def test_100x_typed_centre_gets_its_ceiling(make_client, make_engine):
    d = make_client(make_engine()).get(
        "/api/objective/focus100x/defaults", params={"centre_um": 2988.7}).json()
    assert d["centre_um"] == 2988.7
    assert d["ceiling_um"] == pytest.approx(2988.7 + 0.4 * 130.0)
    assert ceiling_for(3190.0) == 3200.0  # never above the window top


def test_100x_centre_from_a_4x_plane_uses_the_lab_offset(make_client, make_engine):
    d = make_client(make_engine(focus={"z_4x_focus_um": 3048.7})).get(
        "/api/objective/focus100x/defaults").json()
    assert d["centre_um"] == pytest.approx(2988.7) and d["lab_offset_um"] == -60.0
    assert d["above_4x_focus"] is False


# -- access -----------------------------------------------------------------------------


def test_remote_viewers_read_the_area(make_client, make_engine):
    c = make_client(make_engine(), remote=True)
    assert c.get("/api/objective/state").status_code == 200
    assert c.get("/api/objective/lenses").status_code == 200


def test_reads_need_a_login(make_client, make_engine):
    r = make_client(make_engine(), login=None).get("/api/objective/state")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "login_required"


def test_loading_done_from_a_remote_origin_is_refused(make_client, make_engine):
    """Remote viewers may send abort (D13), never the load_immersion confirm."""
    eng = make_engine()
    c = make_client(eng, remote=True)
    r = c.post("/api/commands", json={"kind": "confirm", "op_id": "objective_change_1",
                                      "args": {"key": "load_immersion", "ok": True}})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "remote_view"
    assert r.headers["X-DinoAF-Refusal"] == "remote_view"
    assert eng.commands == []
    # the same viewer's abort still goes through
    assert c.post("/api/commands", json={"kind": "abort", "op_id": "objective_change_1"}
                  ).status_code == 200


def test_the_router_is_mounted_and_in_the_openapi(make_client, make_engine):
    spec = make_client(make_engine()).get("/openapi.json").json()
    for path in ("/api/objective/state", "/api/objective/lenses", "/api/objective/plan",
                 "/api/objective/focus100x/defaults"):
        assert set(spec["paths"][path]) == {"get"}, path
