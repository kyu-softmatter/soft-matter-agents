"""Sample ops over the T-019 records store: one sample per session, events as the truth,
legacy sample.json / map.json derived (T-027)."""

import json
import time

import numpy as np
import pytest

from dino_autofocus.engine.backend import Frame
from dino_autofocus.engine.operations.sample_ops import (
    SampleContext,
    ensure_sample_created,
    run_sample_op,
    structure_check,
)
from dino_autofocus.engine.sample import Sample, read_sample
from dino_autofocus.records import ExperimentSession, FolderStore, RecordsConfig

USER = "operator@example.test"
LEGACY = "20260930_1849_1"


@pytest.fixture
def store(tmp_path):
    return FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                     data_root=tmp_path / "data"))


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "samples"
    s = Sample(LEGACY, r)
    s.dir.mkdir(parents=True)
    s.sample_json.write_text(json.dumps({  # a 2026-09-30 sample: no events, legacy only
        "sample_id": LEGACY, "created": "2026-09-30T18:49:00",
        "hole": {"centre_um": [8026.0, 571.6], "diameter_mm": 6.1438, "arc_deg": 352.0,
                 "fitted_at": "2026-09-30T19:57:19"}}))
    s.map_json.write_text(json.dumps({"visits": [], "boundary": [[1.0, 2.0], [3.0, 4.0]]}))
    return r


def ctx_for(store, root, session=None):
    return SampleContext(store, root, session, USER)


def run(op, ctx, sink=None, backend=None, **args):
    seen = [] if sink is None else sink
    out = run_sample_op(op, ctx, args, seen.append, backend)
    return out, seen


def edge_frame(fake, rng=None):
    rng = rng or np.random.default_rng(0)
    img = rng.normal(2700, 30, fake.shape)
    img[:, : fake.shape[1] // 2] -= 1500  # the hole edge in brightfield
    return Frame(img.clip(0, 4095).astype(np.uint16), time.time(), fake.exposure,
                 fake.x, fake.y, fake.z)


def test_sample_new_reserves_only_and_refuses_with_a_session_open(store, root):
    out, ev = run("sample_new", ctx_for(store, root))
    sid = out["summary"]["sample_id"]
    assert out["status"] == "finished" and (root / sid).is_dir()
    assert ev[-1].kind == "finished" and ev[-1].data["summary"]["sample_id"] == sid
    assert read_sample(store, sid, root).n_events == 0  # no event until a session opens
    s = ExperimentSession.open(store, USER, sid)
    out, ev = run("sample_new", ctx_for(store, root, s))
    assert out["status"] == "refused" and ev[-1].kind == "preflight_failed"
    assert "one sample per session" in out["why"]


def test_the_first_session_writes_sample_created_once(store, root):
    sid = run("sample_new", ctx_for(store, root))[0]["summary"]["sample_id"]
    s = ExperimentSession.open(store, USER, sid)
    assert ensure_sample_created(s, store) and not ensure_sample_created(s, store)
    assert read_sample(store, sid, root).created is not None


def test_sample_open_reads_a_legacy_sample_and_keeps_one_sample_per_session(store, root):
    out, _ = run("sample_open", ctx_for(store, root), sample_id=LEGACY)
    assert out["status"] == "finished"
    summary = out["summary"]
    assert summary["fitted_at"] == "2026-09-30T19:57:19" and summary["closed_loop"]
    assert summary["created"] == "2026-09-30T18:49:00"
    assert run("sample_open", ctx_for(store, root), sample_id="20990101_0000_1")[0][
        "status"] == "refused"
    other = ExperimentSession.open(store, USER, "20261001_1540_1")
    assert run("sample_open", ctx_for(store, root, other), sample_id=LEGACY)[0][
        "status"] == "refused"
    same = ExperimentSession.open(store, USER, LEGACY)
    assert run("sample_open", ctx_for(store, root, same), sample_id=LEGACY)[0][
        "status"] == "finished"


def test_geometry_needs_the_session_and_valid_values(store, root):
    assert run("sample_geometry_set", ctx_for(store, root), sample_id=LEGACY,
               values={"orientation": "upright"})[0]["status"] == "refused"
    s = ExperimentSession.open(store, USER, LEGACY)
    ctx = ctx_for(store, root, s)
    bad, _ = run("sample_geometry_set", ctx, sample_id=LEGACY, values={"orientation": "sideways"})
    assert bad["status"] == "refused" and "not one of" in bad["why"]
    assert read_sample(store, LEGACY, root).n_events == 0  # a refusal writes nothing
    out, _ = run("sample_geometry_set", ctx, sample_id=LEGACY,
                 values={"sample_thickness_um": 80, "orientation": "flipped"})
    geo = out["summary"]["geometry"]
    assert geo["orientation"]["source"] == {"kind": "entered", "by": USER,
                                            "t": geo["orientation"]["source"]["t"]}
    assert out["summary"]["loading"]["geometry"]["done"]
    derived = json.loads(Sample(LEGACY, root).sample_json.read_text())
    assert derived["geometry"]["sample_thickness_um"] == 80.0
    assert derived["hole"]["arc_deg"] == 352.0  # the legacy hole is kept


def test_loading_is_confirmed_by_person_and_image(store, root, fake):
    s = ExperimentSession.open(store, USER, LEGACY)
    ctx = ctx_for(store, root, s)
    run("sample_geometry_set", ctx, sample_id=LEGACY,
        values={"sample_thickness_um": 80, "orientation": "upright"})
    run("loading_confirm_person", ctx, sample_id=LEGACY)
    fake.snap = lambda: edge_frame(fake)
    out, ev = run("loading_check_image", ctx, backend=fake, sample_id=LEGACY)
    r = out["summary"]
    assert r["ok"] and r["grade"] == "computed" and r["metric"] == "structure_ratio"
    assert r["loading"]["confirmed"]
    assert (Sample(LEGACY, root).dir / r["frame_ref"]).exists()
    assert fake.lights == {"DiaLamp": "0", "Aura": "0"}  # light off after the check
    assert [e.kind for e in ev if e.kind == "light_changed"] == ["light_changed"] * 2
    assert ev[-1].kind == "finished" and ev[-1].data["summary"]["ok"]
    # a new session for the same sample starts unconfirmed
    s.close()
    s2 = ExperimentSession.open(store, USER, LEGACY)
    assert not read_sample(store, LEGACY, root, s2.session_id).loading["confirmed"]


def test_image_check_refuses_off_4x_and_reports_a_flat_field(store, root, fake):
    s = ExperimentSession.open(store, USER, LEGACY)
    ctx = ctx_for(store, root, s)
    fake.state = 5  # 100x Oil in place
    out, ev = run("loading_check_image", ctx, backend=fake, sample_id=LEGACY)
    assert out["status"] == "refused" and "4x" in out["why"]
    assert not any(c[0] == "light" for c in fake.calls)  # refused before any light
    fake.state = 0
    out, _ = run("loading_check_image", ctx, backend=fake, sample_id=LEGACY)  # flat frame
    assert not out["summary"]["ok"] and out["summary"]["why"]
    assert read_sample(store, LEGACY, root, s.session_id).loading["image"]["ok"] is False


def test_structure_check_tells_an_edge_from_flat_dark_and_clipped_frames(fake):
    rng = np.random.default_rng(1)
    assert structure_check(edge_frame(fake, rng).image, 4095)["ok"]
    assert "flat field" in structure_check(rng.normal(2700, 30, (64, 64)), 4095)["why"]
    assert "range" in structure_check(np.full((64, 64), 102.0), 4095)["why"]
    clipped = edge_frame(fake, rng).image.copy()
    clipped[:8] = 4095
    assert "clipped" in structure_check(clipped, 4095)["why"]


def test_boundary_mark_undo_reset_in_the_same_second(store, root):
    s = ExperimentSession.open(store, USER, LEGACY)
    ctx = ctx_for(store, root, s)
    for x in (10.0, 20.0, 30.0):
        run("boundary_mark", ctx, sample_id=LEGACY, x_um=x, y_um=0.0)
    out, _ = run("boundary_undo", ctx, sample_id=LEGACY)
    assert out["summary"]["boundary"] == [[10.0, 0.0], [20.0, 0.0]]
    run("boundary_mark", ctx, sample_id=LEGACY, x_um=40.0, y_um=0.0)
    m = json.loads(Sample(LEGACY, root).map_json.read_text())
    assert m["boundary"] == [[10.0, 0.0], [20.0, 0.0], [40.0, 0.0]]  # derived from events
    out, _ = run("boundary_reset", ctx, sample_id=LEGACY)
    assert out["summary"]["n_points"] == 0
    assert run("boundary_undo", ctx, sample_id=LEGACY)[0]["status"] == "refused"
    run("boundary_mark", ctx, sample_id=LEGACY, x_um=50.0, y_um=0.0)
    run("boundary_undo", ctx, sample_id=LEGACY)
    run("boundary_undo", ctx, sample_id=LEGACY)  # refused: nothing left, nothing written
    assert read_sample(store, LEGACY, root).boundary == []


def test_a_geometry_op_does_not_wipe_a_legacy_map(store, root):
    s = ExperimentSession.open(store, USER, LEGACY)
    run("sample_geometry_set", ctx_for(store, root, s), sample_id=LEGACY,
        values={"orientation": "upright"})
    assert json.loads(Sample(LEGACY, root).map_json.read_text())["boundary"] == [[1.0, 2.0],
                                                                               [3.0, 4.0]]


def test_boundary_points_refuse_model_numbers_and_need_a_session(store, root):
    from dino_autofocus.engine.records import model_value

    assert run("boundary_mark", ctx_for(store, root), sample_id=LEGACY, x_um=1.0, y_um=2.0)[
        0]["status"] == "refused"
    s = ExperimentSession.open(store, USER, LEGACY)
    out, _ = run("boundary_mark", ctx_for(store, root, s), sample_id=LEGACY,
                 x_um=model_value(1.0, "head"), y_um=2.0)
    assert out["status"] == "refused" and "model output" in out["why"]
    with pytest.raises(ValueError, match="unknown sample op"):
        run_sample_op("sample_delete", ctx_for(store, root))



def test_objective_changes_project_into_objectives_used_and_sample_json(store, root):
    from dino_autofocus.engine.sample import OBJECTIVE_CHANGED, write_derived_views

    json_path = Sample(LEGACY, root).sample_json
    legacy = json.loads(json_path.read_text())
    json_path.write_text(json.dumps({**legacy, "objectives_used": ["4x"]}))
    s = ExperimentSession.open(store, USER, LEGACY)
    s.sample_event(OBJECTIVE_CHANGED, from_key="4x", to_key="100x-Oil",
                   label="6-Plan Apo LmbdD0.13 100x Oil")
    s.sample_event(OBJECTIVE_CHANGED, from_key="100x-Oil", to_key="4x",
                   label="1-Plan Apo LmbdD20 4x")
    s.sample_event(OBJECTIVE_CHANGED, from_key="4x", to_key="60x-Oil",
                   label="5-Plan Apo LmbdD 60x Oil")
    view = read_sample(store, LEGACY, root)
    assert view.objectives_used == ["4x", "100x-Oil", "60x-Oil"]  # ordered, unique
    assert view.summary()["objectives_used"] == ["4x", "100x-Oil", "60x-Oil"]
    write_derived_views(view, root)
    assert json.loads(json_path.read_text())["objectives_used"] == ["4x", "100x-Oil", "60x-Oil"]



def test_a_removed_flag_is_kept_retired_with_its_history(store, root):
    s = ExperimentSession.open(store, USER, LEGACY)
    s.sample_event("flag_set", flag_id="f1", name="good area", x_um=1.0, y_um=2.0)
    s.sample_event("flag_set", flag_id="f2", name="debris", x_um=3.0, y_um=4.0)
    s.sample_event("flag_remove", flag_id="f2")
    view = read_sample(store, LEGACY, root)
    assert set(view.flags) == {"f1", "f2"}  # remove, then list: f2 is still there
    f2 = view.flags["f2"]
    assert f2["retired"] and f2["name"] == "debris"
    assert [h["kind"] for h in f2["history"]] == ["flag_set", "flag_remove"]
    assert all(h["by"] == USER and h["at"] for h in f2["history"])
    assert set(view.active_flags()) == {"f1"}
    s.sample_event("flag_set", flag_id="f2", name="debris after all", x_um=3.0, y_um=4.0)
    again = read_sample(store, LEGACY, root).flags["f2"]
    assert not again["retired"] and len(again["history"]) == 3


def test_confirm_then_reject_keeps_both_in_the_candidate_history(store, root):
    s = ExperimentSession.open(store, USER, LEGACY)
    s.sample_event("particle", particle_id="p1", status="candidate", x_um=1.0, y_um=1.0)
    s.sample_event("particle", particle_id="p1", status="confirmed", x_um=1.0, y_um=1.0)
    other = "second@example.test"
    s.info.user_id = other  # a second person rejects it in the same session
    s.sample_event("particle", particle_id="p1", status="rejected", x_um=1.0, y_um=1.0)
    view = read_sample(store, LEGACY, root)
    p1 = view.candidates["p1"]
    assert p1["status"] == "rejected" and "p1" not in view.open_candidates()
    assert [(h["status"], h["by"]) for h in p1["history"]] == [
        ("candidate", USER), ("confirmed", USER), ("rejected", other)]
    assert all(h["at"] for h in p1["history"])
