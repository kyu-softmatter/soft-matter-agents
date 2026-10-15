"""focus.sma_event: a verdict becomes a soft-matter-agents run-log event with no E6 grade,
no command fields, and the encoder z as the only z."""

import json
import os
from pathlib import Path

import pytest

from dino_autofocus.focus import FrameStats, Verdict, from_reading, from_sweep
from dino_autofocus.focus.sma_event import EVENT, to_run_log_event


def _stats(score: float) -> FrameStats:
    return FrameStats(metric="tenengrad", score=score, mean=500.0, median=480.0, p999=900.0,
                      max=1200, saturated_fraction=0.0)


class Reading:
    score, sigma, n_used, tiles, sign_known = 2.5, 0.5, 3, [0, 1, 2], True


def _sweep():
    z = [3000.0, 3002.0, 3004.0, 3006.0, 3008.0]
    return from_sweep(z, [_stats(s) for s in (1.0, 3.0, 5.0, 3.0, 1.0)])


def test_sweep_verdict_event_carries_encoder_z_and_e1_e4_grades():
    v = _sweep()
    assert v.verdict is Verdict.IN_FOCUS
    ev = to_run_log_event(v, 12.5)
    assert json.loads(json.dumps(ev, allow_nan=False)) == ev
    assert (ev["event"], ev["choice"], ev["time_base"]) == (EVENT, "in_focus", "software")
    assert ev["z"] == {"value": 3004.0, "unit": "um", "grade": "E1", "read_from": "z_drive"}
    assert {e["grade"] for e in ev["evidence"]} <= {"E1", "E4"}
    assert ev["signals"] == []


def test_model_numbers_go_to_signals_without_a_grade():
    ev = to_run_log_event(from_reading(Reading(), z_um=3010.0, frame_index=7), 3.0)
    assert ev["choice"] == "step_down"
    assert {s["name"] for s in ev["signals"]} == {"dz", "sigma", "n_used"}
    assert all("grade" not in s for s in ev["signals"])
    assert "E6" not in json.dumps(ev)
    assert ev["z"]["value"] == 3010.0  # the frame's readback, not the model's dz


def test_no_command_fields_and_bad_time_rejected():
    ev = to_run_log_event(_sweep(), 0.0)
    assert not {"params", "channel", "action", "from", "verification", "deletion"} & set(ev)
    with pytest.raises(ValueError):
        to_run_log_event(_sweep(), float("nan"))
    with pytest.raises(ValueError):
        to_run_log_event(_sweep(), 1.0, time_base="wall")


def _sma_root() -> Path:
    return Path(os.environ.get("DINO_AF_SMA_ROOT", r"D:\codes\github\soft-matter-agents"))


def test_event_fits_the_sma_run_log_event_schema_when_present():
    schema_dir = _sma_root() / "contracts" / "schemas"
    if not (schema_dir / "run_log.schema.json").is_file():
        pytest.skip("soft-matter-agents checkout not found")
    event = json.loads((schema_dir / "run_log.schema.json").read_text(encoding="utf-8"))
    event = event["$defs"]["event"]
    grades = json.loads((schema_dir / "common.schema.json").read_text(encoding="utf-8"))
    grades = set(grades["$defs"]["grade"]["enum"])
    ev = to_run_log_event(_sweep(), 1.0)
    assert set(event["required"]) <= set(ev)
    assert ev["time_base"] in event["properties"]["time_base"]["enum"]
    assert event.get("additionalProperties", True) is not False
    for e in [*ev["evidence"], ev["z"]]:
        assert e["grade"] in grades and e["grade"] != "E6"
