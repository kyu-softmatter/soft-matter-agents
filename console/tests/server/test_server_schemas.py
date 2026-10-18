from __future__ import annotations

import dataclasses
import typing

import pytest
from pydantic import ValidationError

from sma_console.server import schemas
from sma_console.server.schemas import EventKind, EventOut, Snapshot, contract


def test_literals_follow_the_contract_kind_list():
    assert typing.get_args(EventKind) == contract.EVENT_KINDS


def test_event_model_wraps_the_contract_dataclass():
    """Fails when the console's event copy gains or loses a field the wire model does not."""
    assert set(EventOut.model_fields) == {f.name for f in dataclasses.fields(contract.Event)}


def test_no_command_model_is_left():
    """Card 077: the console sends no command to any engine, so no command shape remains."""
    gone = ("Command", "CommandIn", "CommandAccepted", "CommandKind", "COMMAND_KINDS",
            "WsCommand", "WsAccepted", "SERVER_STAMPED")
    assert not [name for name in gone if hasattr(schemas, name) or hasattr(contract, name)]


def test_event_from_engine():
    out = EventOut.from_engine(contract.Event(kind="position", data={"z_um": 3000.0}))
    assert (out.kind, out.data) == ("position", {"z_um": 3000.0})
    assert (out.user_id, out.session_id) == (None, None)
    ev = contract.Event(kind="finished", op_id="scan_4x_1", user_id="op@example.test",
                        session_id="s1")
    out = EventOut.from_engine(ev)
    assert (out.user_id, out.session_id) == ("op@example.test", "s1")


def test_unknown_kinds_refused():
    with pytest.raises(ValidationError):
        EventOut(kind="teleported", t=0.0)
    with pytest.raises(ValueError):
        contract.Event(kind="teleported")


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
