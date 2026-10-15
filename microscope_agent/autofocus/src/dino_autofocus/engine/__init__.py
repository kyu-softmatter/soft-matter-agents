"""UI-independent engine: backend protocol, commands/events, guards, gates, records, samples.

Importing this package pulls in no UI toolkit, torch or pymmcore (checked by
tests/engine/test_contract.py); backends import their device libraries where they are used.
"""

from .backend import Backend, BackendInfo, Frame, PfsState, Positions, Readback
from .events import COMMAND_KINDS, EVENT_KINDS, Command, Event, EventSink, fan_out, queue_sink
from .guards import (
    PROVISIONAL,
    FocusAxis,
    GuardError,
    OperationAborted,
    XYAxis,
    XYBox,
    exclusive,
    lights_off,
    operation,
)
from .records import Graded, OpRecord, model_value
from .sample import Sample, SampleGeometry, SampleInfo

__all__ = [
    "COMMAND_KINDS", "EVENT_KINDS", "PROVISIONAL", "Backend", "BackendInfo", "Command",
    "Event", "EventSink", "FocusAxis", "Frame", "Graded", "GuardError", "OpRecord",
    "OperationAborted", "PfsState", "Positions", "Readback", "Sample", "SampleGeometry",
    "SampleInfo", "XYAxis", "XYBox", "exclusive",
    "fan_out", "lights_off", "model_value", "operation", "queue_sink",
]
