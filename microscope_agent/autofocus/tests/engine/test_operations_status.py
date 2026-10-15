"""status: read-only snapshot op (operations-spec 2) on FakeBackend."""

from __future__ import annotations

import json
import time

from engine_fakes import FakeBackend

from dino_autofocus.engine.backend import Positions
from dino_autofocus.engine.operations.status import read_status, run_status


def test_status_reads_every_field(fake: FakeBackend) -> None:
    fake.state = 5
    st = read_status(fake)
    assert st["nosepiece_label"] == "6-Plan Apo LmbdD0.13 100x Oil"
    assert st["nosepiece_state"] == 5
    assert st["z_um"] == 2900.0
    assert st["pfs_enabled"] is False and st["pfs_in_range"] == "Out of Range"
    assert st["lights"] == {"DiaLamp": "0", "Aura": "0"}
    assert st["bit_depth"] == 12 and st["ceiling_adu"] == 4095
    assert st["info"]["camera"] == "FakeCam"
    json.dumps(st)  # JSON-native


def test_failed_reads_are_fields_not_errors(fake: FakeBackend, monkeypatch) -> None:
    def broken():
        raise OSError("PFS not answering")

    monkeypatch.setattr(fake, "pfs", broken)
    monkeypatch.setattr(fake, "positions",
                        lambda: Positions(1.0, 2.0, None, errors={"z": "ZDrive timeout"}))
    st = read_status(fake)
    assert st["pfs_enabled"].startswith("unreadable: OSError")
    assert st["z_um"] is None
    assert st["positions"]["errors"] == {"z": "ZDrive timeout"}
    assert st["nosepiece_label"] == "1-Plan Apo LmbdD20 4x"  # the rest still reads


def test_status_without_record_emits_one_reading_and_writes_nothing(fake, tmp_path) -> None:
    events = []
    run_status(fake, tmp_path, events.append)
    assert [e.kind for e in events] == ["reading"]
    assert events[0].data["source"] == "status"
    assert list(tmp_path.iterdir()) == []
    assert not [c for c in fake.calls if c[0] in ("light", "move_z", "move_xy")]


def test_status_record_when_asked_keeps_lights_as_they_were(fake, tmp_path) -> None:
    fake.lights["DiaLamp"] = "1"  # brightfield set by a light_set before
    events = []
    st = run_status(fake, tmp_path, events.append, keep_record=True, user_id="u1")
    assert [e.kind for e in events] == ["started", "reading", "finished"]
    (folder,) = tmp_path.iterdir()
    assert folder.name.startswith("status_")
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "finished" and summary["user_id"] == "u1"
    assert summary["result"]["z_um"] == st["z_um"]
    assert summary["lights_off"]["switched_off"] is False
    assert fake.lights["DiaLamp"] == "1"  # nothing was switched
    assert not [c for c in fake.calls if c[0] == "light"]
    assert len((folder / "log.jsonl").read_text(encoding="utf-8").splitlines()) == 3


# ---------------------------------------------------------------- under the T-011 runner
def test_registered_ops_run_under_the_runner(fake: FakeBackend, tmp_path) -> None:
    import dino_autofocus.engine.operations.edge_trace  # noqa: F401 - registers
    import dino_autofocus.engine.operations.light_set  # noqa: F401
    from dino_autofocus.engine.events import Command
    from dino_autofocus.engine.runner import (
        OPERATIONS,
        AllowAll,
        Runner,
        RunnerConfig,
        folder_records,
    )

    assert {"status", "light_set", "edge_trace"} <= set(OPERATIONS.names())
    r = Runner(fake, control=AllowAll(), config=RunnerConfig(position_interval_s=None),
               records=folder_records(lambda meta: tmp_path / "records"))
    events = []
    r.subscribe(events.append)
    r.start()
    r.set_experiment_session("20261001_1200_1", 1000.0)
    try:
        ends = ("finished", "aborted", "error", "preflight_failed")

        def run(op: str, **args) -> str:
            op_id = r.submit(Command("start", op=op, args=args, user_id="u1",
                                     session_id="20261001_1200_1"))
            deadline = time.monotonic() + 10
            while not any(e.op_id == op_id and e.kind in ends for e in list(events)):
                assert time.monotonic() < deadline, [e.kind for e in events if e.op_id == op_id]
                time.sleep(0.01)
            assert r.wait_idle(10)
            return op_id

        lid = run("light_set", mode="brightfield")
        assert any(e.kind == "finished" and e.op_id == lid for e in events)
        assert fake.lights["DiaLamp"] == "1"  # keep_lights_on_finish
        sid = run("status")
        end = next(e for e in events if e.op_id == sid and e.kind == "finished")
        assert end.data["summary"]["status"]["nosepiece_label"] == "1-Plan Apo LmbdD20 4x"
        assert any(e.kind == "reading" and e.op_id == sid for e in events)
        assert fake.lights["DiaLamp"] == "1"  # a status after light_set keeps the light
        assert r.snapshot()["hardware"]["last_status"]["op_id"] == sid

        bad = run("light_set", mode="aura", line="VIOLET", percent=1)
        assert any(e.kind == "preflight_failed" and e.op_id == bad for e in events)
        fake.stuck.add("Aura")
        err = run("light_set", mode="aura", line="GREEN", percent=1)
        assert any(e.kind == "error" and e.op_id == err for e in events)
        assert fake.lights["DiaLamp"] == "0"  # the runner's exit path switched all off
    finally:
        r.shutdown("test teardown", timeout=5)
        assert r.wait_idle(5)
