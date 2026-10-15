"""Commands into the engine and events out of it: plain dataclasses that survive JSON.

The engine never knows who listens. A sink is any `Callable[[Event], None]`; a UI passes a
function that hands the event to its own loop, a test passes `list.append`, and
`queue_sink` wraps a `queue.Queue` for a reader on another thread. Payloads go in `data`
and must be JSON-native (str, int, float, bool, None, list, dict), so the same objects can
later cross a process boundary unchanged.
"""

from __future__ import annotations

import json
import queue
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

# lights_off pre-empts: the runner aborts the running operation and switches all off.
# update changes a running operation's declared args; approve / reject decide a proposal.
COMMAND_KINDS = ("start", "abort", "confirm", "lights_off", "update", "approve", "reject")
ORIGINS = ("human", "assistant")  # an assistant command is a proposal until a human confirms
CONFIRM_KINDS = ("question", "manual_step")  # manual_step: F5 "Loading done", recorded as such

EVENT_KINDS = (
    # operation life cycle
    "planned", "preflight_ok", "preflight_failed", "started", "progress", "frame_ready",
    "reading", "finished", "aborted", "error",
    # hardware
    "position", "light_changed", "property_set", "motion",
    # the operator has to answer before the operation goes on (oil loaded, climb past a
    # peak); "confirmed" records the answer as an operator-graded entry
    "confirm_required", "confirmed",
    # commands: an assistant proposal and its decision, a refused command, an update
    "proposed", "approved", "rejected", "refused", "updated",
    # state the screens follow (screen contracts, T-100..T-106)
    "map_changed", "sample_opened", "objective", "session_changed",
    "log",
)


def _check(kind: str, allowed: tuple[str, ...], what: str) -> None:
    if kind not in allowed:
        raise ValueError(f"unknown {what} kind {kind!r}; expected one of {allowed}")


@dataclass
class Command:
    """`start` names an operation in `op` with its `args`; `abort`, `confirm` and `update`
    name the running operation by `op_id`. A confirm answers a `confirm_required` event:
    `args` holds `{"key": <that event's data["key"]>, "ok": bool}` (or `"answer"`). `update`
    carries the args to change; `approve` / `reject` name a proposal by `op_id`.

    An assistant `start` with `confirmed_by` was confirmed by that person on the proposal
    card (T-013) and runs; without it the engine holds it as a proposal. `remote` marks a
    command from a non-loopback client: the engine takes only `abort` from one (D13).
    `control_grant` is attached by the server from the operator's control (T-018), never
    taken from the browser; the engine ignores token-like fields inside `args`."""

    kind: str
    op: str = ""
    op_id: str = ""
    args: dict = field(default_factory=dict)
    origin: str = "human"
    user_id: str | None = None  # who sent it; None until login exists (T-018)
    session_id: str | None = None  # experiment session id (T-019); None outside one
    proposal_id: str | None = None  # assistant proposals (T-013)
    conversation_id: str | None = None
    confirmed_by: str | None = None
    remote: bool = False
    control_grant: str | None = None
    t: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        _check(self.kind, COMMAND_KINDS, "command")
        _check(self.origin, ORIGINS, "origin")

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> Command:
        return cls(**json.loads(s))


@dataclass
class Event:
    """`user_id` / `session_id` are the operation's (rule 12); None for engine-wide events
    such as the periodic `position`."""

    kind: str
    op_id: str = ""
    data: dict = field(default_factory=dict)
    t: float = field(default_factory=time.time)
    user_id: str | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        _check(self.kind, EVENT_KINDS, "event")

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> Event:
        return cls(**json.loads(s))


EventSink = Callable[[Event], None]


def queue_sink(q: queue.Queue) -> EventSink:
    return q.put


def fan_out(*sinks: EventSink) -> EventSink:
    """One sink that feeds several (e.g. the UI and the operation's log.jsonl)."""

    def emit(ev: Event) -> None:
        for s in sinks:
            s(ev)

    return emit


def null_sink(_ev: Event) -> None:
    return None
