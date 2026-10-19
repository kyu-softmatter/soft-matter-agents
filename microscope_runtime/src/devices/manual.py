"""The channel for devices a person operates (4.6.6 rule 2).

Some of this instrument has no programming interface at all -- the camera
splitter is set by hand and its position cannot be read -- and some of it can
be commanded but not verified. Both come here. Pretending a half-automated
system is fully automated does not make the log optimistic, it makes the whole
log false (P2, P9).

So this module drives nothing. It issues an instruction sheet and waits for a
human confirmation, and while a sheet is open the orchestrator sends no
automatic command to that lock group. That is lockout/tagout in software: a
person closes the sheet, never a timeout (2.1 rule 5).
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

_LOCK = threading.Lock()
_OPEN: dict[str, dict] = {}
_HISTORY: list[dict] = []


class ConfirmationRequired(RuntimeError):
    """Raised instead of returning success. There is no silent manual step."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def preflight(channel: dict | None = None) -> dict:
    """Always unverified, and says so rather than guessing at a state."""
    channel = channel or {}
    return {
        "channel": channel.get("id", "manual"),
        "ready": True,
        "read_back": False,
        "automatable": channel.get("automatable", "none"),
        "backend": "manual",
        "note": "state is whatever a person last set; it is not read back and not assumed",
    }


def apply(params: dict) -> dict:
    """Open an instruction sheet. This never completes the step by itself.

    The caller gets a sheet id and an exception. A manual step that returned
    success would be a step nobody performed.
    """
    sheet_id = params.get("sheet_id") or f"sheet-{len(_HISTORY) + len(_OPEN) + 1:03d}"
    record = {
        "sheet_id": sheet_id,
        "opened_at": _now(),
        "instruction": params.get("instruction", ""),
        "channel": params.get("channel", ""),
        "element": params.get("element"),
        "requested_state": {k: v for k, v in params.items()
                            if k not in {"sheet_id", "instruction", "channel", "element"}},
    }
    if not record["instruction"]:
        raise ConfirmationRequired(
            f"sheet {sheet_id}: a manual step needs an instruction a person can actually follow"
        )
    with _LOCK:
        _OPEN[sheet_id] = record
    raise ConfirmationRequired(
        f"sheet {sheet_id} is open on {record['channel']}: {record['instruction']}. "
        "Nothing proceeds on this lock group until a person confirms"
    )


def confirm(sheet_id: str, confirmed_by: str, observed: str = "") -> dict:
    """A person says they did it, and who they are goes into the record.

    `observed` is what they saw, not what they were asked to set. Where a
    selector decides whether light arrives at all, those are two different
    questions and only the second one is evidence.
    """
    with _LOCK:
        record = _OPEN.pop(sheet_id, None)
    if record is None:
        raise ConfirmationRequired(f"no open sheet {sheet_id!r}")
    record.update({"confirmed_at": _now(), "confirmed_by": confirmed_by, "observed": observed})
    _HISTORY.append(record)
    return record


def open_sheets() -> list[dict]:
    with _LOCK:
        return list(_OPEN.values())


def read() -> dict:
    """What is outstanding. There is no device state to report."""
    with _LOCK:
        return {"open_sheets": list(_OPEN), "completed": len(_HISTORY), "backend": "manual"}


def abort() -> dict:
    """Abort closes nothing here -- a person is holding this device.

    Cancelling the sheet would tell the log the step is over while someone still
    has their hands in the instrument. The sheet stays open, and the abort says
    that it did.
    """
    with _LOCK:
        outstanding = list(_OPEN)
    return {
        "aborted": True,
        "backend": "manual",
        "sheets_left_open": outstanding,
        "note": "a manual sheet is not cancelled by an abort; the person closes it",
    }


def render(run_id: str) -> str:
    """The sheet as a person reads it -- runs/<run_id>/manual_steps.md (4.6.6-2)."""
    lines = [f"# manual steps for {run_id}", ""]
    for record in _HISTORY + list(_OPEN.values()):
        head = f"## {record['sheet_id']} - {record['channel']}"
        if record.get("element"):
            head += f" / {record['element']}"
        lines += [head, "", record["instruction"], "", f"- opened: {record['opened_at']}"]
        if "confirmed_by" in record:
            lines += [
                f"- confirmed: {record['confirmed_at']} by {record['confirmed_by']}",
                f"- observed: {record['observed'] or '(nothing recorded)'}",
            ]
        else:
            lines.append("- **not confirmed** - nothing on this lock group proceeded")
        lines.append("")
    return "\n".join(lines)
