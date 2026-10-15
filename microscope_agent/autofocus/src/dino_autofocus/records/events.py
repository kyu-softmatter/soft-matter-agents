"""Sample state as append-only events, folded into the current state on read.

Every session appends to its own ``records/sample_events.jsonl``; nothing is ever rewritten.
The state of a sample is the fold of all events for that sample across all sessions, sorted
by ``(t, session_id, seq)``. Two sessions that touched the same sample therefore never edit
the same line or file, and folding their events gives the same state whatever order the
files are read in (PLAN.md v0.9, F7).

Event kinds (payload fields in brackets):

* ``hole_fit`` [centre_um (x, y), diameter_mm, rms_um, ...]: the latest fit wins.
* ``boundary_point`` [x_um, y_um]: hole-edge points, kept in order.
* ``boundary_clear`` []: drops the boundary points recorded before it.
* ``field_visit`` [x_um, y_um, objective, ...]: a field that was looked at.
* ``flag_set`` [flag_id, name, note, x_um, y_um, objective]: create or replace a flag.
* ``flag_remove`` [flag_id]: the flag stays, with ``retired: True`` (the map shows retired
  flags on a toggle, ui-spec 7.4). Every flag entry has ``history``: one ``{kind, by, at}``
  per event, in order; a later ``flag_set`` brings it back with ``retired: False``.
* ``particle`` [particle_id, x_um, y_um, z_um, status]: status "candidate" (found by image
  processing), "confirmed" or "rejected" (a person checked it); the latest event per id
  wins, and ``history`` keeps every step as ``{kind, by, at, status}``.
* ``note`` [text]

Unknown kinds are kept (``SampleState.other``) so newer writers do not break older readers.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .layout import check_id, now_iso

KINDS = ("hole_fit", "boundary_point", "boundary_clear", "field_visit", "flag_set",
         "flag_remove", "particle", "note")


@dataclass
class SampleEvent:
    kind: str
    sample_id: str
    session_id: str
    user_id: str
    seq: int                       # order within one session's file
    t: str = field(default_factory=now_iso)
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SampleEvent:
        return cls(kind=d["kind"], sample_id=d["sample_id"], session_id=d["session_id"],
                   user_id=d.get("user_id", ""), seq=int(d["seq"]), t=d["t"],
                   payload=dict(d.get("payload") or {}))

    @property
    def order(self) -> tuple[datetime, str, int]:
        # parsed, so a DST change in the offset does not reorder events
        t = datetime.fromisoformat(self.t)
        return (t if t.tzinfo else t.astimezone(), self.session_id, self.seq)


def make_event(kind: str, sample_id: str, session_id: str, user_id: str, seq: int,
               t: str | None = None, **payload: Any) -> SampleEvent:
    if not kind:
        raise ValueError("event kind is empty")
    check_id(sample_id)
    if kind in ("flag_set", "flag_remove") and "flag_id" not in payload:
        raise ValueError(f"{kind} needs a flag_id")
    if kind == "particle" and "particle_id" not in payload:
        raise ValueError("particle needs a particle_id")
    return SampleEvent(kind=kind, sample_id=sample_id, session_id=session_id, user_id=user_id,
                       seq=seq, t=t or now_iso(), payload=payload)


@dataclass
class SampleState:
    sample_id: str
    hole: dict[str, Any] | None = None
    boundary: list[dict[str, Any]] = field(default_factory=list)
    visits: list[dict[str, Any]] = field(default_factory=list)
    flags: dict[str, dict[str, Any]] = field(default_factory=dict)
    particles: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: list[dict[str, Any]] = field(default_factory=list)
    other: list[dict[str, Any]] = field(default_factory=list)
    sessions: list[str] = field(default_factory=list)   # sessions that touched it, in order
    n_events: int = 0
    updated: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stamp(e: SampleEvent) -> dict[str, Any]:
    # seq is monotonic within one session's file and orders events in the same second
    # (t has one-second resolution: a boundary mark and its undo can share a timestamp)
    return {**e.payload, "t": e.t, "session_id": e.session_id, "user_id": e.user_id,
            "seq": e.seq}


def _history(prev: dict[str, Any] | None, e: SampleEvent, **extra: Any) -> list[dict]:
    return [*((prev or {}).get("history") or []),
            {"kind": e.kind, "by": e.user_id, "at": e.t, **extra}]


def fold(events: Iterable[SampleEvent], sample_id: str) -> SampleState:
    """Current state of `sample_id` from events of any sessions, in any order.

    A `flag_remove` for a flag_id no `flag_set` made leaves a retired stub
    (`{"flag_id", "retired": True, "history"}`) rather than being dropped."""
    st = SampleState(sample_id=sample_id)
    mine = sorted((e for e in events if e.sample_id == sample_id), key=lambda e: e.order)
    for e in mine:
        st.n_events += 1
        st.updated = e.t
        if e.session_id not in st.sessions:
            st.sessions.append(e.session_id)
        rec = _stamp(e)
        if e.kind == "hole_fit":
            st.hole = rec
        elif e.kind == "boundary_point":
            st.boundary.append(rec)
        elif e.kind == "boundary_clear":
            st.boundary.clear()
        elif e.kind == "field_visit":
            st.visits.append(rec)
        elif e.kind == "flag_set":
            fid = str(e.payload["flag_id"])
            prev = st.flags.get(fid)
            st.flags[fid] = {**rec, "retired": False, "history": _history(prev, e)}
        elif e.kind == "flag_remove":
            fid = str(e.payload["flag_id"])
            prev = st.flags.get(fid) or {"flag_id": fid}
            st.flags[fid] = {**prev, "retired": True, "history": _history(prev, e)}
        elif e.kind == "particle":
            pid = str(e.payload["particle_id"])
            prev = st.particles.get(pid)
            st.particles[pid] = {**rec, "history": _history(prev, e,
                                                           status=e.payload.get("status"))}
        elif e.kind == "note":
            st.notes.append(rec)
        else:
            st.other.append({"kind": e.kind, **rec})
    return st
