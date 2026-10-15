"""Lights off on every way out: POST /api/shutdown, signals, lifespan end, atexit."""

from __future__ import annotations

import atexit
import json
import signal
import threading

from dino_autofocus.server.__main__ import PlaceholderEngine, install_exit_hooks
from dino_autofocus.server.app import EngineStopper


def test_shutdown_route_stops_engine_then_exits(engine, make_client):
    c = make_client(engine)
    exits = []
    c.app.state.request_exit = lambda: exits.append(True)
    r = c.post("/api/shutdown", json={"reason": "launcher closing"})
    assert r.status_code == 200
    assert r.json() == {"reason": "launcher closing", "already": False}
    assert engine.shutdowns == ["launcher closing"]
    assert exits == [True]

    again = c.post("/api/shutdown", json={})
    assert again.json() == {"reason": "launcher closing", "already": True}
    assert engine.shutdowns == ["launcher closing"]  # stopped once

    assert c.post("/api/commands", json={"kind": "lights_off"}).status_code == 503
    with c.websocket_connect("/ws/events") as ws:
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "abort"}}))
        assert json.loads(ws.receive_text())["status"] == 503
    assert engine.commands == []


def test_shutdown_is_local_only_even_under_d13(engine, make_client):
    c = make_client(engine, remote=True, remote_view=True, remote_abort=True)
    r = c.post("/api/shutdown", json={})
    assert r.status_code == 403
    local = make_client(engine)
    foreign = local.post("/api/shutdown", json={}, headers={"origin": "https://example.com"})
    assert foreign.status_code == 403
    assert engine.shutdowns == []


def test_failed_shutdown_still_exits_and_can_be_retried(engine, make_client):
    c = make_client(engine)
    exits = []
    c.app.state.request_exit = lambda: exits.append(True)
    engine.fail_shutdown = True
    r = c.post("/api/shutdown", json={"reason": "launcher closing"})
    assert r.status_code == 500
    assert r.json()["detail"]["code"] == "shutdown_failed"
    assert "readback timed out" in r.json()["detail"]["message"]
    assert exits == [True]
    c.app.state.stop_engine.quietly("process exit")  # what the atexit hook does
    assert engine.shutdowns == ["process exit"]


def test_lifespan_end_stops_engine(engine, make_client):
    with make_client(engine) as c:
        assert c.get("/api/health").status_code == 200
        assert engine.shutdowns == []
    assert engine.shutdowns == ["server stopping"]


class DummyServer:
    """The two things install_exit_hooks touches on a uvicorn.Server."""

    def __init__(self) -> None:
        self.should_exit = False
        self.trapped: list[int] = []

    def handle_exit(self, sig, frame) -> None:
        self.trapped.append(sig)
        self.should_exit = True


def test_signal_and_atexit_hooks(engine, make_client):
    app = make_client(engine).app
    server = DummyServer()
    hook = install_exit_hooks(app, server)
    try:
        app.state.request_exit()
        assert server.should_exit
        server.handle_exit(signal.SIGINT, None)
        assert server.trapped == [signal.SIGINT]  # uvicorn's own handling still runs
        for t in threading.enumerate():
            if t.name == "engine-stop":
                t.join(5)
        assert engine.shutdowns == ["signal SIGINT"]
        hook()  # atexit later: already stopped, nothing more
        assert engine.shutdowns == ["signal SIGINT"]
    finally:
        atexit.unregister(hook)


def test_stopper_runs_engine_shutdown_once_across_threads(engine):
    stop = EngineStopper(engine)
    threads = [threading.Thread(target=stop.quietly, args=(f"t{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(engine.shutdowns) == 1 and stop.done


def test_placeholder_shutdown_reports_lights_off():
    eng = PlaceholderEngine(shape=(60, 80))
    seen = []
    unsubscribe = eng.subscribe(seen.append)
    try:
        eng.shutdown("test")
    finally:
        unsubscribe()
    lights = [e for e in seen if e.kind == "light_changed"]
    assert lights and lights[-1].data["dialamp"]["state"] == "off"
    assert lights[-1].data["aura"]["state"] == "off"
