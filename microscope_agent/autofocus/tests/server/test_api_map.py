"""The map router (T-102, docs/screens/map.md): reads from the T-027 sample view and the legacy
samples root, the mosaic PNG, and the D16 writes. Fake engine and fake accounts only: no login
with real control, no hardware, no browser."""

from __future__ import annotations

import io
import shutil
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from server_fakes import OPERATOR, VIEWER, FakeEngine

from dino_autofocus.engine.operations.sample_ops import SampleSeat
from dino_autofocus.records import FolderStore, RecordsConfig
from dino_autofocus.records.session import ExperimentSession
from dino_autofocus.server.api import MAP_WRITE_OPS, REFUSAL_HEADER

FIXTURE = Path(__file__).parent / "fixtures" / "map" / "samples"
SAMPLE = "20260930_1849_1"
MAP_RESULT = "sample_map_20260930-200100"
SCAN_RESULT = "scan4x_20260930-195700"
FIT_AT = "2026-09-30T19:57:00"


class MapEngine(FakeEngine):
    """FakeEngine plus the T-027 sample seat and the engine's session rule for record ops."""

    def __init__(self, seat: SampleSeat, session: dict | None) -> None:
        super().__init__()
        self.sample_seat = seat
        self.session = session

    def snapshot(self) -> dict:
        return {**super().snapshot(), "session": self.session,
                "sample": {"sample_id": SAMPLE,
                           "session_id": (self.session or {}).get("session_id")}}

    def submit(self, cmd):
        # runner._MARK: record ops need an open experiment session (checked by the engine)
        if cmd.op in MAP_WRITE_OPS and cmd.session_id is None:
            raise ValueError(f"{cmd.op}: open an experiment session first")
        return super().submit(cmd)


def epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).astimezone().timestamp()


@pytest.fixture
def world(tmp_path):
    root = tmp_path / "samples"
    shutil.copytree(FIXTURE, root)
    d = root / SAMPLE / MAP_RESULT
    # rows run from y0 (row 0) to y1; brighter towards +y so the flip is visible
    mosaic = np.tile(np.arange(1, 9, dtype=np.uint16)[:, None] * 100, (1, 12))
    mosaic[0, 0] = 0  # an empty cell
    np.save(d / "mosaic.npy", mosaic)

    records = FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                        data_root=tmp_path / "data"))
    s = ExperimentSession.open(records, user_id=OPERATOR, sample_id=SAMPLE, code_repo=tmp_path)
    s.sample_event("hole_fit", centre_um=[8026.0, 571.6], diameter_mm=6.1438, fit_rms_um=42.5,
                   n_points=49, arc_deg=352.0, fitted_at=FIT_AT, closed_loop=True)
    s.sample_event("boundary_point", x_um=8833.4, y_um=-2354.1)
    s.sample_event("boundary_point", x_um=11097.0, y_um=571.6)
    s.sample_event("field_visit", x_um=8026.0, y_um=571.6, objective="4x", fov_um=3900.0,
                   verdict="in_focus")
    s.sample_event("geometry_set", values={"hole_diameter_mm": 6.0})
    s.sample_event("flag_set", flag_id="f1", name="good field", note="dense", x_um=8164.7,
                   y_um=523.4, objective="4x", z_um=2988.45)
    s.sample_event("flag_set", flag_id="f0", name="old", x_um=7000.0, y_um=0.0)
    s.sample_event("flag_remove", flag_id="f0")
    s.sample_event("particle", particle_id="c1", x_um=7811.0, y_um=1529.0, status="candidate",
                   score=0.7, result_id=MAP_RESULT)
    s.sample_event("particle", particle_id="c2", x_um=8100.0, y_um=600.0, status="confirmed")
    s.sample_event("particle", particle_id="c3", x_um=9000.0, y_um=900.0, status="rejected")
    session = {"session_id": s.session_id, "started_at": epoch("2026-09-30T19:30:00")}
    engine = MapEngine(SampleSeat(records, root), session)
    return SimpleNamespace(engine=engine, root=root, session=s, records=records)


def open_session(client, world) -> None:
    client.app.state.sessions.set(SimpleNamespace(info=SimpleNamespace(session_id=world.session.session_id)))


# -- reads ------------------------------------------------------------------------------


def test_map_state_from_the_sample_view(world, make_client):
    got = make_client(world.engine).get(f"/api/map/{SAMPLE}")
    assert got.status_code == 200
    m = got.json()
    assert m["sample_id"] == SAMPLE
    assert [(p["x_um"], p["y_um"]) for p in m["boundary"]] == [(8833.4, -2354.1), (11097.0, 571.6)]
    h = m["hole"]
    assert h["centre_um"] == [8026.0, 571.6] and h["diameter_mm"] == 6.1438
    assert h["fit_rms_um"] == 42.5 and h["n_points"] == 49 and h["arc_deg"] == 352.0
    assert h["fitted_at"] == pytest.approx(epoch(FIT_AT))
    assert h["closed_loop"] is True
    assert m["expected_diameter_mm"] == 6.0
    assert m["visits"] == [{"x_um": 8026.0, "y_um": 571.6, "w_um": 3900.0, "h_um": 3900.0,
                            "verdict": "in_focus", "source": None}]
    # the latest result (sample_map, 20:01) carries its own boxes
    assert m["allowed_box_um"] == {"x0": 3554.0, "x1": 12498.0, "y0": -3900.0, "y1": 5043.0}
    assert m["session_started_at"] == pytest.approx(epoch("2026-09-30T19:30:00"))


def test_results_newest_first_with_boxes(world, make_client):
    got = make_client(world.engine).get(f"/api/map/{SAMPLE}/results").json()
    assert [(r["result_id"], r["kind"], r["has_mosaic"]) for r in got] == [
        (MAP_RESULT, "sample_map", True), (SCAN_RESULT, "scan_4x", False)]
    scan = got[1]
    # derived from the scan's hole and margin: half = 6.1438 * 500 + 500
    half = 6.1438 * 500 + 500
    assert scan["scan_box_um"]["x0"] == pytest.approx(8026.0 - half)
    assert scan["allowed_box_um"]["y1"] == pytest.approx(571.6 + half + 1000)
    assert scan["n_tiles"] == 2 and scan["grid_n"] == 2
    assert scan["started"] == pytest.approx(epoch("2026-09-30T19:57:30"))


def test_result_detail_tiles_and_mosaic_extent(world, make_client):
    c = make_client(world.engine)
    scan = c.get(f"/api/map/{SAMPLE}/results/{SCAN_RESULT}").json()
    assert [t["name"] for t in scan["tiles"]] == ["r0c0", "r0c1"]
    assert scan["tiles"][0]["block_z_um"] == [3050.1, None]
    assert scan["tiles"][1]["z_focus_um"] is None
    assert scan["mosaic"] is None and scan["fov_um"] == 3901.0
    smap = c.get(f"/api/map/{SAMPLE}/results/{MAP_RESULT}").json()
    assert smap["mosaic"] == {"x0": 4418.0, "x1": 11634.0, "y0": -3036.0, "y1": 4180.0,
                              "um_per_px": 13.0, "bin": 8}


def test_mosaic_png_is_stage_up_and_grey(world, make_client):
    got = make_client(world.engine).get(f"/api/map/{SAMPLE}/results/{MAP_RESULT}/mosaic.png")
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/png"
    img = np.asarray(Image.open(io.BytesIO(got.content)))
    assert img.dtype == np.uint8 and img.shape == (8, 12)
    # +y up: the last mosaic row (y1, brightest) is the top PNG row; M is not applied again
    assert img[0].mean() > img[-1, 1:].mean()
    assert img[-1, 0] == 0  # the empty cell at (y0, x0) stays black, bottom left
    assert img[0, 0] == 255


def test_mosaic_downscaled_to_max_px(world, make_client, tmp_path):
    big = np.ones((300, 500), dtype=np.uint16)
    np.save(world.root / SAMPLE / MAP_RESULT / "mosaic.npy", big)
    url = f"/api/map/{SAMPLE}/results/{MAP_RESULT}/mosaic.png?max_px=100"
    got = make_client(world.engine).get(url)
    assert max(Image.open(io.BytesIO(got.content)).size) <= 100


def test_mosaic_refusals(world, make_client):
    c = make_client(world.engine)
    none = c.get(f"/api/map/{SAMPLE}/results/{SCAN_RESULT}/mosaic.png")
    assert none.status_code == 404 and none.json()["detail"]["code"] == "no_mosaic"
    meta = world.root / SAMPLE / MAP_RESULT / "mosaic.json"
    meta.write_text('{"x0": 0, "x1": 1, "y0": 0, "y1": 1, "um_per_px": 1, "bin": 1}',
                    encoding="utf-8")
    unsure = c.get(f"/api/map/{SAMPLE}/results/{MAP_RESULT}/mosaic.png")
    assert unsure.status_code == 409
    assert unsure.json()["detail"]["code"] == "mosaic_orientation"
    assert unsure.headers[REFUSAL_HEADER] == "mosaic_orientation"


def test_flags_and_candidates(world, make_client):
    c = make_client(world.engine)
    flags = c.get(f"/api/map/{SAMPLE}/flags").json()
    assert [(f["flag_id"], f["name"], f["z_um"]) for f in flags] == [("f1", "good field", 2988.45)]
    assert flags[0]["t"] is not None and flags[0]["retired_at"] is None
    cands = c.get(f"/api/map/{SAMPLE}/candidates").json()
    assert {x["candidate_id"]: x["source"] for x in cands} == {
        "c1": "classical_candidate", "c2": "person_confirmed"}
    assert next(x for x in cands if x["candidate_id"] == "c2")["by"] == OPERATOR
    every = c.get(f"/api/map/{SAMPLE}/candidates?include_rejected=true").json()
    assert {x["candidate_id"]: x["source"] for x in every}["c3"] == "person_rejected"


def test_retired_flag_is_not_in_play_but_kept_with_its_history(world, make_client):
    """T-027c: the fold keeps a retired flag; the default list uses active_flags()."""
    c = make_client(world.engine)
    assert "f0" not in {f["flag_id"] for f in c.get(f"/api/map/{SAMPLE}/flags").json()}
    every = {f["flag_id"]: f for f in c.get(f"/api/map/{SAMPLE}/flags?include_retired=true").json()}
    f0, f1 = every["f0"], every["f1"]
    assert f0["retired"] is True and f0["retired_by"] == OPERATOR
    assert f0["retired_at"] is not None and (f0["x_um"], f0["y_um"]) == (7000.0, 0.0)
    assert [h["kind"] for h in f0["history"]] == ["flag_set", "flag_remove"]
    assert f1["retired"] is False and f1["retired_at"] is None and f1["retired_by"] is None


def test_decided_candidates_carry_who_and_when(world, make_client):
    """T-027c: open_candidates() leaves out rejected ones; decisions come from history."""
    c = make_client(world.engine)
    shown = {x["candidate_id"]: x for x in c.get(f"/api/map/{SAMPLE}/candidates").json()}
    assert "c3" not in shown
    assert shown["c1"]["by"] is None and shown["c1"]["decided_at"] is None
    assert shown["c2"]["by"] == OPERATOR and shown["c2"]["decided_at"] is not None
    assert shown["c2"]["history"][-1]["status"] == "confirmed"
    every = {x["candidate_id"]: x
             for x in c.get(f"/api/map/{SAMPLE}/candidates?include_rejected=true").json()}
    assert every["c3"]["by"] == OPERATOR and every["c3"]["decided_at"] is not None


def test_unknown_sample_bad_ids_and_no_store(world, make_client):
    c = make_client(world.engine)
    assert c.get("/api/map/20990101_0000_1").status_code == 404
    assert c.get(f"/api/map/{SAMPLE}/results/bad%20id").status_code == 404
    assert c.get(f"/api/map/{SAMPLE}/results/not_a_result").status_code == 404
    bare = make_client(FakeEngine()).get(f"/api/map/{SAMPLE}")
    assert bare.status_code == 503 and bare.json()["detail"]["code"] == "no_records"


def test_reads_are_open_to_viewers_and_remote_viewers(world, make_client):
    assert make_client(world.engine, login=VIEWER).get(f"/api/map/{SAMPLE}").status_code == 200
    remote = make_client(world.engine, remote=True, login=VIEWER)
    assert remote.get(f"/api/map/{SAMPLE}/flags").status_code == 200
    assert make_client(world.engine, login=None).get(f"/api/map/{SAMPLE}").status_code == 401


# -- D16 writes -------------------------------------------------------------------------

WRITES = [
    ("map_flag", f"/api/map/{SAMPLE}/flags", {"x_um": 1.0, "y_um": 2.0, "name": "edge"}),
    ("map_flag_retire", f"/api/map/{SAMPLE}/flags/f1/retire", {}),
    ("candidate_confirm", f"/api/map/{SAMPLE}/candidates/c1/confirm", {}),
    ("candidate_reject", f"/api/map/{SAMPLE}/candidates/c1/reject", {}),
]


@pytest.mark.parametrize("op,path,body", WRITES)
def test_d16_viewer_is_refused_by_role_not_remote_view(world, make_client, op, path, body):
    c = make_client(world.engine, login=VIEWER)
    open_session(c, world)
    got = c.post(path, json=body)
    assert got.status_code == 403
    assert got.json()["detail"]["code"] == "role"  # not remote_view: the screen stays live
    assert got.headers[REFUSAL_HEADER] == "role"
    assert world.engine.commands == []


@pytest.mark.parametrize("op,path,body", WRITES)
def test_d16_remote_operator_is_refused(world, make_client, op, path, body):
    c = make_client(world.engine, remote=True, login=OPERATOR)
    got = c.post(path, json=body)
    assert got.status_code == 403 and got.json()["detail"]["code"] == "remote_view"
    assert world.engine.commands == []


@pytest.mark.parametrize("op,path,body", WRITES)
def test_d16_needs_an_open_experiment_session(world, make_client, op, path, body):
    got = make_client(world.engine, login=OPERATOR).post(path, json=body)
    assert got.status_code == 400 and got.json()["detail"]["code"] == "refused"
    assert "experiment session" in got.json()["detail"]["message"]
    assert world.engine.commands == []


@pytest.mark.parametrize("op,path,body", WRITES)
def test_d16_local_operator_with_a_session_submits_the_engine_command(world, make_client, op,
                                                                       path, body):
    c = make_client(world.engine, login=OPERATOR, control=True)
    open_session(c, world)
    got = c.post(path, json=body)
    assert got.status_code == 200, got.text
    assert got.json()["op_id"]
    cmd = world.engine.commands[-1]
    assert (cmd.kind, cmd.op, cmd.origin) == ("start", op, "human")
    assert cmd.args["sample_id"] == SAMPLE
    assert cmd.user_id == OPERATOR and cmd.session_id == world.session.session_id
    assert cmd.control_grant is not None and cmd.remote is False


def test_flag_args_and_validation(world, make_client):
    c = make_client(world.engine, login=OPERATOR)
    open_session(c, world)
    c.post(f"/api/map/{SAMPLE}/flags", json={"x_um": 1.0, "y_um": 2.0, "name": "edge",
                                             "note": "denser", "replaces": "f1"})
    assert world.engine.commands[-1].args == {"sample_id": SAMPLE, "x_um": 1.0, "y_um": 2.0,
                                              "name": "edge", "note": "denser", "replaces": "f1"}
    empty = c.post(f"/api/map/{SAMPLE}/flags", json={"x_um": 1, "y_um": 2, "name": ""})
    assert empty.status_code == 422
    assert c.post(f"/api/map/{SAMPLE}/candidates/c1/confirm",
                  json={"note": "checked at 100x"}).status_code == 200
    assert world.engine.commands[-1].args["note"] == "checked at 100x"


def test_common_endpoint_refuses_the_map_writes(world, make_client):
    c = make_client(world.engine, login=OPERATOR, control=True)
    for op in sorted(MAP_WRITE_OPS):
        got = c.post("/api/commands", json={"kind": "start", "op": op, "args": {}})
        assert got.status_code == 403 and got.json()["detail"]["code"] == "map_route"


def test_routes_are_in_the_openapi(world, make_client):
    paths = make_client(world.engine).get("/openapi.json").json()["paths"]
    for p in ("/api/map/{sample_id}", "/api/map/{sample_id}/results/{result_id}/mosaic.png",
              "/api/map/{sample_id}/flags/{flag_id}/retire"):
        assert p in paths
