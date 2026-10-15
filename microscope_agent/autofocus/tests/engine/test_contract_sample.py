"""Sample folders round-trip old and new keys; records carry user and session ids."""

import json
import time

from dino_autofocus.engine import Sample, SampleGeometry, SampleInfo, operation
from dino_autofocus.engine.sample import SampleMap


def test_sample_json_round_trip_keeps_unknown_keys(tmp_path):
    s = Sample("20260930_1849_1", tmp_path)
    s.dir.mkdir()
    s.sample_json.write_text(json.dumps({
        "sample_id": s.id, "from_the_future": [1, 2],
        "hole": {"centre_um": [8026.0, 571.6], "diameter_mm": 6.1438,
                 "fitted_at": "2026-09-30T19:57:19"}}))
    info = s.load_info()
    assert info.hole["fitted_at"] == "2026-09-30T19:57:19"
    assert info.extra == {"from_the_future": [1, 2]}
    info.geometry = SampleGeometry(hole_diameter_mm=6.0, orientation="inverted")
    s.save_info(info)
    again = s.load_info()
    assert again.geometry == info.geometry and again.extra == info.extra
    assert SampleInfo.from_dict(again.to_dict()) == again
    s.save_map(SampleMap(visits=[{"x": 1.0, "y": 2.0}], boundary=[[1.0, 2.0]]))
    assert s.load_map().boundary == [[1.0, 2.0]]


def test_new_sample_ids_count_up_within_a_minute(tmp_path):
    now = time.strptime("2026-10-01 15:40", "%Y-%m-%d %H:%M")
    a, b = Sample.create(tmp_path, now), Sample.create(tmp_path, now)
    assert (a.id, b.id) == ("20261001_1540_1", "20261001_1540_2")
    assert Sample(a.id, tmp_path).load_info().sample_id == a.id  # no sample.json yet


def test_operation_records_name_the_user_and_session(fake, tmp_path):
    s = Sample.create(tmp_path)
    user = "operator@example.test"
    with operation(fake, s.dir, "status", user_id=user, session_id="exp-1") as op:
        pass
    summary = json.loads((s.dir / op.op_id / "summary.json").read_text())
    assert (summary["user_id"], summary["session_id"]) == (user, "exp-1")
    with operation(fake, s.dir, "status") as op2:
        pass
    summary = json.loads((s.dir / op2.op_id / "summary.json").read_text())
    assert summary["user_id"] is None and summary["session_id"] is None
