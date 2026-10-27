"""The idle status file (card 085): what the last run saw, written when it ends.

`.runtime_status/idle_status.json`, validated by contracts/schemas/idle_status.schema.json. It is
built from the ending run's OWN log and nothing else: a channel the run did not open is absent, every
value carries the time it was read, and a read that did not happen is `not_read` with no value --
never the last one. The file is replaced whole by a rename, so a reader sees the old file or the new
one. It is never committed (.gitignore holds `.runtime_status/`).

Nothing here reads or sends to a device. A failure of any kind is the caller's to record; the run
that wrote it has already ended as it would have.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATUS_NAME = "idle_status.json"
RUN_ID = re.compile(r"^run-[0-9]{8}-[0-9]{3}$")
KINDS = ("plan", "live_view", "check_now", "preparatory")


def _wall(t0_wall: str, t_mono: float) -> str:
    """The wall time of a log offset: the run's t0 plus the offset."""
    t0 = datetime.fromisoformat(t0_wall)
    if t0.tzinfo is None:
        t0 = t0.replace(tzinfo=timezone.utc)
    return (t0 + timedelta(seconds=float(t_mono))).isoformat(timespec="milliseconds")


def _plain(value):
    return json.loads(json.dumps(value, default=str))


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _last_sent(events: list[dict], cid: str):
    """What this run last sent a channel that cannot be read back, or None if it sent nothing."""
    for e in reversed(events):
        if e.get("event") == "apply" and e.get("channel") == cid and isinstance(e.get("params"), dict):
            return _plain(e["params"])
    return None


def _reading(o, events: list[dict], cid: str, state, t_mono: float):
    """One channel's reading from one state in the log, or None when the run did not open it."""
    channel = o.channels.get(cid)
    out = {"channel": cid, "name": cid}
    if isinstance(state, dict) and state.get("not_open"):
        return None
    if not isinstance(state, dict) or state.get("not_read") or state.get("error"):
        out.update(how="not_read", t_wall=None, value=None)
        return out
    out["t_wall"] = _wall(o.clock.t0_wall, t_mono)
    if channel is not None and channel.read_back is False:
        out.update(how="not_readable", value=_last_sent(events, cid))
    else:
        out.update(how="read_back", value=_plain(state))
    return out


def _preflight(o, events: list[dict]):
    """This run's preflight rows as the log has them, the latest row of each channel, with when."""
    rows: dict[str, dict] = {}
    last = None
    for e in events:
        if e.get("event") == "preflight":
            rows.pop(e["channel"], None)
            rows[e["channel"]] = {"channel": e["channel"], "named_as": _plain(e.get("named_as") or []),
                                  "verified": bool(e.get("verified")), "state": _plain(e.get("state"))}
            last = e
    if not rows:
        return None
    return {"t_wall": _wall(o.clock.t0_wall, last["t_mono"]), "rows": list(rows.values())}


def _snapshot(o, events: list[dict]):
    """The last `snapshot` event, only the channels this run opened."""
    for e in reversed(events):
        if e.get("event") != "snapshot":
            continue
        channels = []
        for cid, state in (e.get("states") or {}).items():
            if cid not in o._preflight_state:
                continue
            row = _reading(o, events, cid, state, e["t_mono"])
            if row is not None:
                channels.append(row)
        if channels:
            return {"t_wall": _wall(o.clock.t0_wall, e["t_mono"]), "channels": channels}
        return None
    return None


def _check_now(o, events: list[dict], listed: dict):
    """The check-now section: one entry per listed channel, in the list's order, from this run's events."""
    entries = []
    for cid in listed["channels"]:
        mine = [e for e in events if e.get("channel") == cid]
        opened = any(e["event"] == "check_now_open" for e in mine)
        closed = (any(e["event"] == "check_now_close" for e in mine)
                  and not any(e["event"] == "check_now_step_failed" and e.get("step") == "close" for e in mine)
                  ) if opened else None
        failure = next((e for e in mine if e["event"] == "check_now_step_failed"
                        and e.get("step") in ("preflight", "open", "read")), None)
        read = next((e for e in mine if e["event"] == "check_now_read"), None)
        error = None
        if read is not None and not read.get("not_read"):
            row = _reading(o, events, cid, read.get("state"), read["t_mono"])
        else:
            row = {"channel": cid, "name": cid, "how": "not_read", "t_wall": None, "value": None}
            if read is not None:
                error = read.get("why")
            elif failure is not None:
                error = f"{failure['step']} failed: {failure.get('error')}"
        close_failure = next((e for e in mine if e["event"] == "check_now_step_failed"
                              and e.get("step") == "close"), None)
        if close_failure is not None and error is None:
            error = f"close failed: {close_failure.get('error')}"
        row.update(opened=opened, closed=closed)
        if error:
            row["error"] = str(error)
        entries.append(row)
    return {"run_id": listed["run_id"], "t_wall": _wall(o.clock.t0_wall, listed["t_mono"]),
            "list": {"path": listed["path"], "sha256": listed["sha256"]}, "channels": entries}


def build(o, run_id: str, kind: str, how: str, ended_at: str, check_now: dict | None = None) -> dict:
    """The status document for the run `o` is ending. `check_now` is the list the run was given, or None."""
    if not RUN_ID.match(str(run_id)):
        raise ValueError(f"run id {run_id!r} is not one the status file can name (run-YYYYMMDD-NNN)")
    if kind not in KINDS:
        raise ValueError(f"run kind {kind!r} is not one of {KINDS}")
    with o._log_lock:
        events = list(o.log)
    registry_path = o.registry_source
    registry_file = Path(registry_path)
    if not registry_file.is_absolute():
        registry_file = _repo() / registry_path
    doc = {
        "artifact": "idle_status", "schema_version": "0.1",
        "written_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "written_by_run": run_id,
        "last_run": {"run_id": run_id, "kind": kind, "ended_at": ended_at, "outcome": str(how) or "unknown",
                     "preflight": _preflight(o, events), "last_snapshot": _snapshot(o, events)},
        "check_now": None if check_now is None else _check_now(o, events, check_now),
        "ownership": {"status": "not_built"},
        "registry": {"path": str(registry_path).replace("\\", "/"), "sha256": _file_sha(registry_file)},
    }
    return doc


def _repo() -> Path:
    return Path(__file__).resolve().parents[2]


def _replace(src, dst, attempts: int = 50, pause_s: float = 0.005) -> None:
    """os.replace, trying again for a moment when Windows refuses because a reader has the old file open."""
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(pause_s)


def write(folder, doc: dict) -> Path:
    """Replace `<folder>/idle_status.json` whole: a temp file in the same folder, then a rename over it."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / STATUS_NAME
    fd, tmp = tempfile.mkstemp(prefix=".idle_status.", suffix=".tmp", dir=str(folder))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(doc, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _replace(tmp, final)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return final
