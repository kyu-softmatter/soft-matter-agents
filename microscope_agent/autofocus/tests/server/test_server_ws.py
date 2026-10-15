from __future__ import annotations

import json
import time

import numpy as np


def wait_for(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > end:
            raise AssertionError("condition not met in time")
        time.sleep(0.01)


def test_events_stream_and_unsubscribe(engine, make_client):
    with make_client(engine) as c, c.websocket_connect("/ws/events") as ws:
        wait_for(lambda: len(engine.sinks) == 1)
        engine.emit("position", x_um=1.5, y_um=2.5, z_um=3001.0)
        engine.emit("finished", "op7", ok=True)
        first = json.loads(ws.receive_text())
        assert first["type"] == "event"
        assert first["event"]["kind"] == "position"
        assert first["event"]["data"] == {"x_um": 1.5, "y_um": 2.5, "z_um": 3001.0}
        second = json.loads(ws.receive_text())
        assert (second["event"]["kind"], second["event"]["op_id"]) == ("finished", "op7")
    wait_for(lambda: engine.sinks == [])


def test_ws_command_local(engine, make_client):
    with make_client(engine) as c, c.websocket_connect("/ws/events") as ws:
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "lights_off"}}))
        assert json.loads(ws.receive_text()) == {"type": "accepted", "op_id": "op1"}
        ws.send_text("not json")
        bad = json.loads(ws.receive_text())
        assert (bad["type"], bad["status"]) == ("error", 422)
        ws.send_text(json.dumps({"type": "command",
                                 "command": {"kind": "start", "op": "unknown_op"}}))
        assert json.loads(ws.receive_text())["status"] == 400
    assert [x.kind for x in engine.commands] == ["lights_off"]


def test_ws_remote_gets_events_but_cannot_command(engine, make_client):
    with make_client(engine, remote=True, remote_view=True) as c, \
            c.websocket_connect("/ws/events") as ws:
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "lights_off"}}))
        refused = json.loads(ws.receive_text())
        assert (refused["type"], refused["status"]) == ("error", 403)
        wait_for(lambda: len(engine.sinks) == 1)
        engine.emit("light_changed", aura="off")
        assert json.loads(ws.receive_text())["event"]["kind"] == "light_changed"
    assert engine.commands == []


def test_ws_command_refused_from_foreign_page(engine, make_client):
    with make_client(engine) as c, \
            c.websocket_connect("/ws/events", headers={"origin": "https://example.com"}) as ws:
        ws.send_text(json.dumps({"type": "command", "command": {"kind": "lights_off"}}))
        assert json.loads(ws.receive_text())["status"] == 403
    assert engine.commands == []


def test_frames_end_to_end(frame_engine, make_client):
    frame_engine.frame = (np.full((1200, 1600), 1000, np.uint16), {"t": 12.5, "z_um": 3000.0})
    with make_client(frame_engine) as c, c.websocket_connect("/ws/frames") as ws:
        wait_for(lambda: len(frame_engine.sinks) == 1)
        frame_engine.emit("frame_ready")
        meta = json.loads(ws.receive_text())
        jpeg = ws.receive_bytes()
        assert meta["type"] == "frame"
        assert (meta["width"], meta["height"], meta["binning"]) == (800, 600, 2)
        assert meta["meta"] == {"t": 12.5, "z_um": 3000.0}
        assert meta["t"] == 12.5
        assert meta["jpeg_bytes"] == len(jpeg)
        assert jpeg[:2] == b"\xff\xd8"
    wait_for(lambda: frame_engine.sinks == [])  # nobody watching: bridge unsubscribed


def test_frames_without_frame_source(engine, make_client):
    with make_client(engine) as c, c.websocket_connect("/ws/frames") as ws:
        msg = json.loads(ws.receive_text())
        assert (msg["type"], msg["status"]) == ("error", 501)
