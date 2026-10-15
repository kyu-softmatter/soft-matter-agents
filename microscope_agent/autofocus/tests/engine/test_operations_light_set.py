"""light_set: meaning-level light switching with readback (ui-spec 4.3, D15) on FakeBackend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine_fakes import FakeBackend

from dino_autofocus.engine.operations.light_set import parse, plan, run_light_set


@pytest.mark.parametrize("args, why", [
    ({"mode": "strobe"}, "mode"),
    ({}, "mode"),
    ({"mode": "aura", "line": "VIOLET", "percent": 1}, "line"),  # not on the Aura
    ({"mode": "aura", "line": "GREEN"}, "percent"),
    ({"mode": "aura", "line": "GREEN", "percent": 0}, "percent"),
    ({"mode": "aura", "line": "GREEN", "percent": 101}, "percent"),
    ({"mode": "aura", "line": "GREEN", "percent": float("nan")}, "percent"),
    ({"mode": "brightfield", "percent": 5}, "takes no"),
    ({"mode": "off", "device": "XYStage"}, "unknown"),
])
def test_allow_list_refuses(args, why) -> None:
    with pytest.raises(ValueError, match=why):
        parse(args)


def test_refused_args_switch_nothing_and_write_nothing(fake: FakeBackend, tmp_path) -> None:
    with pytest.raises(ValueError):
        run_light_set(fake, tmp_path, {"mode": "aura", "line": "VIOLET", "percent": 1})
    assert fake.calls == [] and list(tmp_path.iterdir()) == []


def test_plan_text_touches_no_backend() -> None:
    assert plan({"mode": "aura", "line": "green", "percent": 1})["text"].startswith(
        "DiaLamp off, Aura GREEN at 1 %")


def test_brightfield_stays_on_after_finish(fake: FakeBackend, tmp_path) -> None:
    events = []
    out = run_light_set(fake, tmp_path, {"mode": "brightfield"}, events.append)
    assert out["status"] == "finished"
    assert fake.lights == {"DiaLamp": "1", "Aura": "0"}
    assert [e.kind for e in events] == ["started", "light_changed", "light_changed", "finished"]
    assert fake.calls[:2] == [("light", "Aura", "0"), ("light", "DiaLamp", "1")]
    summary = json.loads((Path(out["record"]) / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "finished"
    assert summary["lights_off"]["switched_off"] is False
    assert summary["result"]["verified"] is True


def test_aura_line_percent_goes_per_mille(fake: FakeBackend, tmp_path) -> None:
    run_light_set(fake, tmp_path, {"mode": "aura", "line": "GREEN", "percent": 1})
    assert fake.props[("Aura", "GREEN_Intensity")] == "10"
    assert fake.lights == {"DiaLamp": "0", "Aura": "1"}


def test_off_mode(fake: FakeBackend, tmp_path) -> None:
    fake.lights = {"DiaLamp": "1", "Aura": "0"}
    assert run_light_set(fake, tmp_path, {"mode": "off"})["status"] == "finished"
    assert fake.lights == {"DiaLamp": "0", "Aura": "0"}


def test_unverified_readback_switches_off_and_errors(fake: FakeBackend, tmp_path) -> None:
    fake.stuck.add("DiaLamp")  # DiaLamp State ignores the write
    events = []
    out = run_light_set(fake, tmp_path, {"mode": "brightfield"}, events.append)
    assert out["status"] == "error" and "DiaLamp.State wanted 1" in out["error"]
    assert fake.calls[-2:] == [("light", "Aura", "0"), ("light", "DiaLamp", "0")]  # all_off
    assert "error" in [e.kind for e in events]
    assert events[-1].kind == "light_changed" and events[-1].data["switched_off"] is True


def test_backend_failure_still_switches_off(fake: FakeBackend, tmp_path, monkeypatch) -> None:
    def boom(*_a):
        raise OSError("light engine not answering")

    monkeypatch.setattr(fake, "all_off", boom)
    with pytest.raises(OSError):
        run_light_set(fake, tmp_path, {"mode": "off"})
    (folder,) = tmp_path.iterdir()
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "error" and summary["lights_off"]["switched_off"] is True
    assert summary["lights_off"]["verified"] is False  # the switch-off failed too: said so
    assert "light engine not answering" in summary["lights_off"]["error"]

