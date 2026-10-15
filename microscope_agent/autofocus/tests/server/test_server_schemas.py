from __future__ import annotations

import dataclasses
import typing

import pytest
from pydantic import ValidationError

from dino_autofocus.engine import events
from dino_autofocus.server.schemas import (
    SERVER_STAMPED,
    CommandIn,
    CommandKind,
    EventKind,
    EventOut,
    Snapshot,
)


def test_literals_follow_engine_kind_lists():
    assert typing.get_args(CommandKind) == events.COMMAND_KINDS
    assert typing.get_args(EventKind) == events.EVENT_KINDS


def test_models_wrap_engine_dataclasses():
    """Fails when the engine gains or loses a field the wire models do not follow."""
    command_fields = {f.name for f in dataclasses.fields(events.Command)}
    assert set(CommandIn.model_fields) == command_fields - set(SERVER_STAMPED)
    assert set(SERVER_STAMPED) <= command_fields
    assert set(EventOut.model_fields) == {f.name for f in dataclasses.fields(events.Event)}


def test_command_to_engine():
    cmd = CommandIn(kind="confirm", op_id="op3", args={"key": "oil", "ok": True}).to_engine(
        remote=False, user_id="op@example.test", session_id="s1", control_grant="g1")
    assert isinstance(cmd, events.Command)
    stamped = (cmd.origin, cmd.user_id, cmd.session_id, cmd.remote, cmd.control_grant)
    assert stamped == ("human", "op@example.test", "s1", False, "g1")
    assert (cmd.proposal_id, cmd.conversation_id, cmd.confirmed_by) == (None, None, None)
    assert cmd.t > 0
    assert events.Command.from_json(cmd.to_json()) == cmd
    assert CommandIn(kind="abort").to_engine(remote=True).remote is True


@pytest.mark.parametrize("field", SERVER_STAMPED)
def test_body_cannot_set_server_stamped_fields(field):
    """remote, control_grant, user_id, session_id and the assistant provenance come from the
    server, never from the browser: a body that carries one is refused, not half-applied."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CommandIn.model_validate({"kind": "abort", field: "x"})


def test_event_from_engine():
    out = EventOut.from_engine(events.Event(kind="position", data={"z_um": 3000.0}))
    assert (out.kind, out.data) == ("position", {"z_um": 3000.0})
    assert (out.user_id, out.session_id) == (None, None)
    ev = events.Event(kind="finished", op_id="scan_4x_1", user_id="op@example.test",
                      session_id="s1")
    out = EventOut.from_engine(ev)
    assert (out.user_id, out.session_id) == ("op@example.test", "s1")


def test_unknown_kinds_refused():
    with pytest.raises(ValidationError):
        CommandIn(kind="move_z")
    with pytest.raises(ValidationError):
        EventOut(kind="teleported", t=0.0)


def test_snapshot_types_the_runners_shape():
    """A snapshot shaped like `Runner.snapshot()` (engine/runner.py) validates, and keys the
    model does not know yet still reach the browser."""
    op = {"op_id": "scan_4x_1", "op": "scan_4x", "state": "running", "origin": "human",
          "user_id": "otto@example.test", "session_id": "s1", "proposal_id": None,
          "conversation_id": None, "confirmed_by": "otto@example.test", "confirmed_at": 1.0,
          "record_prefix": "scan4x", "args": {}, "why": "", "last_progress": {"i": 3}}
    raw = {
        "positions": {"x_um": 1.0, "y_um": None, "z_um": 3000.0, "piezo_um": {},
                      "errors": {"y": "timeout"}, "t": 2.0},
        "lights": {"dialamp": {"state": "on", "intensity": 30.0},
                   "aura": {"state": "off", "lines": {}}, "verified": True, "records": []},
        "owner": "scan_4x_1", "running": [op], "proposals": [], "pending_confirms": [],
        "awaiting_return": None, "session": {"session_id": "s1", "started_at": 1.0},
        "sample": {"sample_id": "20261001_1200_1", "reserved": False, "session_id": "s1"},
        "last_shutdown_lights": None, "unclean_shutdown": None,
        "hardware": {"profile": None, "profile_path": None, "gates": {}, "last_status": None},
        "stream": {"running": False}, "recent": [], "operations": ["scan_4x"],
        "permissions": {"scan_4x": {"action": "motion", "control": True, "session": True,
                                    "operator": False}},
        "config": {"position_interval_s": 0.5}, "added_later": {"x": 1},
    }
    snap = Snapshot.model_validate(raw)
    assert snap.running[0].op == "scan_4x" and snap.lights.dialamp.state == "on"
    assert snap.positions.errors == {"y": "timeout"}
    assert snap.model_dump()["added_later"] == {"x": 1}
