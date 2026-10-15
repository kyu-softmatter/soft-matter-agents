"""T-009g: the server's runner carries the T-028 hardware provider over the microscope's own
profile folder, the gates refuse through the server until a profile exists, and the provider
is on app.state.hardware for the assistant's `gates=`. Real Runner, MockBackend."""

from __future__ import annotations

import queue
import time

import pytest

from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.events import queue_sink
from dino_autofocus.engine.runner import OPERATIONS, RunnerConfig
from dino_autofocus.server.app import build_runner, hardware_root

T = 20.0


@pytest.fixture
def wired(tmp_path, seat, make_client):
    runner, hw = build_runner(MockBackend(seed=0), records_root=tmp_path / "records",
                              auth=seat, state_dir=tmp_path / "engine_state",
                              config=RunnerConfig(position_interval_s=None))
    events: queue.Queue = queue.Queue()
    runner.subscribe(queue_sink(events))
    runner.start()
    client = make_client(runner, control=True, hardware=hw)
    yield runner, hw, client, events
    runner.shutdown("test teardown", timeout=T)
    assert runner.wait_idle(T)


def wait_end(events: queue.Queue, op_id: str) -> object:
    end = time.monotonic() + T
    while time.monotonic() < end:
        ev = events.get(timeout=T)
        if ev.op_id == op_id and ev.kind in ("finished", "error", "aborted", "preflight_failed"):
            return ev
    raise AssertionError(f"{op_id} did not end")


def test_hardware_ops_registered_without_touching_operations(wired):
    runner, hw, client, _ = wired
    ops = client.get("/api/state").json()["operations"]
    assert {"hardware_scan", "hardware_confirm"} <= set(ops)
    assert set(OPERATIONS.names()) <= set(ops)  # everything else registered is there too
    assert OPERATIONS.get("hardware_scan") is None  # the shared registry is not changed
    assert client.app.state.hardware is hw


def test_gated_op_refused_through_the_server_until_a_profile_exists(wired):
    runner, hw, client, events = wired
    assert hw.check("scan_4x")[0] is False  # no profile: every gate is off
    runner.set_experiment_session("s-1", time.time())
    r = client.post("/api/commands", json={"kind": "start", "op": "scan_4x"})
    assert r.status_code == 200
    end = wait_end(events, r.json()["op_id"])
    assert end.kind == "preflight_failed"
    failed = [c for c in end.data["checks"] if not c["ok"]]
    assert any(c["name"] == "hardware_gate" for c in failed), failed


def test_scan_through_the_server_stores_the_profile_and_opens_the_gates(wired, tmp_path):
    runner, hw, client, events = wired
    r = client.post("/api/commands", json={"kind": "start", "op": "hardware_scan",
                                           "args": {"piezo_port": ""}})
    assert r.status_code == 200
    end = wait_end(events, r.json()["op_id"])
    assert end.kind == "finished", end.data
    stored = hardware_root(tmp_path / "records") / "hardware_profile.json"
    assert stored.is_file()  # the microscope's own folder, not a session's
    state = client.get("/api/state").json()["hardware"]
    assert state["profile_path"] == str(stored)
    assert state["profile"]["backend_kind"] == "mock"
    enabled, reasons = client.app.state.hardware.check("scan_4x")  # the assistant's gates
    assert (enabled, reasons) == (True, [])
