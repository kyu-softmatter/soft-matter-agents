"""Operation records: every operation leaves `<parent>/<prefix or op>_<stamp>/` with two files
(and may add its own, e.g. scan_4x keeps writing the old-format scan.json there).

- `log.jsonl`: every event of the operation, one `Event.to_json()` per line, as emitted.
- `summary.json`: op, op_id, status, start and end state, the lights-off readback (always
  present: `finish` cannot be called without it), the result, the error if any, and
  `user_id` / `session_id` (who ran it, in which experiment session; null when absent,
  PLAN rule 12).

Grades (field name `grade`, shared with focus/verdict.py, T-003). A number in a record says
where it came from: `measured` (encoder z, readback, pixel statistics), `computed`
(deterministic from measured values: classical sharpness, a parabola vertex) or `model`
(DINO, Claude). Model values are wrapped in `Graded(value, "model", source)` wherever they
are stored; `engine.guards` refuses a model-graded value as a motion input. Who asked for
something (an operator click, an assistant proposal) is `origin`, not a grade.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any

from .events import Event

GRADE_MEASURED = "measured"
GRADE_COMPUTED = "computed"
GRADE_MODEL = "model"
GRADES = (GRADE_MEASURED, GRADE_COMPUTED, GRADE_MODEL)

STATUSES = ("finished", "aborted", "error")


@dataclass
class Graded:
    value: Any
    grade: str
    source: str = ""

    def __post_init__(self) -> None:
        if self.grade not in GRADES:
            raise ValueError(f"grade {self.grade!r} not in {GRADES}")


def model_value(value: Any, source: str) -> Graded:
    """Wrap a model output, e.g. `model_value(-1.3, "dinov2_vits14_L1 head dz_dof")`."""
    return Graded(value, GRADE_MODEL, source)


def to_jsonable(o: Any) -> Any:
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


def stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


class OpRecord:
    """Folder, event log and summary of one operation. `sink` is an EventSink."""

    def __init__(self, parent: Path, op: str, when: str | None = None,
                 start_state: dict | None = None, prefix: str | None = None,
                 user_id: str | None = None, session_id: str | None = None):
        parent.mkdir(parents=True, exist_ok=True)
        base, n = f"{prefix or op}_{when or stamp()}", 1
        name = base
        while (parent / name).exists():  # two runs in one second
            n += 1
            name = f"{base}_{n}"
        self.dir, self.op, self.op_id = parent / name, op, name
        self.dir.mkdir()
        self.started = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.start_state = start_state
        self.user_id, self.session_id = user_id, session_id
        self.n_events = 0
        self._log = (self.dir / "log.jsonl").open("w", encoding="utf-8")

    def sink(self, ev: Event) -> None:
        if self._log.closed:
            return
        self._log.write(ev.to_json() + "\n")
        self._log.flush()
        self.n_events += 1

    def finish(self, status: str, *, lights: dict, end_state: dict | None = None,
               result: Any = None, error: str | None = None) -> Path:
        if status not in STATUSES:
            raise ValueError(f"status {status!r} not in {STATUSES}")
        summary = {
            "op": self.op, "op_id": self.op_id, "status": status,
            "user_id": self.user_id, "session_id": self.session_id,
            "started": self.started, "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "start_state": self.start_state, "end_state": end_state,
            "lights_off": lights, "result": result, "error": error,
            "n_events": self.n_events,
        }
        path = self.dir / "summary.json"
        path.write_text(json.dumps(summary, indent=1, default=to_jsonable), encoding="utf-8")
        self._log.close()
        return path
