"""The assistant's record: every question, model turn, tool call, proposal and human decision.

One JSON object per line in `assistant.jsonl`, appended and never rewritten. Each line has
`t`, `kind`, `conversation_id`, and the logged-in `user_id` and experiment `session_id` when the
server knows them (PLAN.md 6절 12항). Anything Claude wrote (answer text, proposed arguments)
is marked `"grade": "model"`, the same word `engine.records` uses, so it is never read back as
a measurement. Token usage is written with every model turn and summed for every answer.

Without a folder the log keeps its lines in memory (tests, and a server started without a
records root). Extra sinks receive every line too; the audit log (WP-M) attaches here.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

GRADE_MODEL = "model"  # engine.records.GRADE_MODEL; repeated so this package imports alone

RECORD_KINDS = (
    "question",  # the person's prompt and screen context
    "model_turn",  # one provider call: content blocks, stop reason, usage
    "tool_call",  # a read tool ran, or an action tool was turned into a proposal
    "proposal",  # a proposal card was created (nothing ran)
    "proposal_confirmed",  # a person confirmed it; the command went to the engine
    "proposal_rejected",  # a person rejected it
    "confirm_refused",  # a confirmation without the permission (role, loopback; D16)
    "reject_refused",  # a rejection without that same permission (T-013c)
    "proposal_failed",  # confirmed, but the engine refused the submission
    "answer",  # the end of one question: text, stop reason, summed usage
    "error",  # the provider failed
)

FILE_NAME = "assistant.jsonl"

RecordSink = Callable[[dict], None]


class RecordLog:
    def __init__(self, folder: str | Path | None = None, *, sinks: list[RecordSink] = ()):
        self.path = None if folder is None else Path(folder) / FILE_NAME
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._memory: list[dict] = []
        self._sinks = list(sinks)
        self._lock = threading.Lock()

    def write(self, kind: str, **fields: Any) -> dict:
        if kind not in RECORD_KINDS:
            raise ValueError(f"unknown record kind {kind!r}; expected one of {RECORD_KINDS}")
        entry = {"t": time.time(), "kind": kind, **fields}
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._lock:
            if self.path is None:
                self._memory.append(json.loads(line))
            else:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            for sink in self._sinks:
                sink(entry)
        return entry

    def entries(self, kind: str | None = None, conversation_id: str | None = None) -> list[dict]:
        with self._lock:
            if self.path is None:
                rows = list(self._memory)
            elif self.path.exists():
                rows = [json.loads(s) for s in self.path.read_text("utf-8").splitlines() if s]
            else:
                rows = []
        return [
            r
            for r in rows
            if (kind is None or r["kind"] == kind)
            and (conversation_id is None or r.get("conversation_id") == conversation_id)
        ]


def model_graded(value: Any, source: str) -> dict:
    """The JSON form of `engine.records.Graded(value, "model", source)`."""
    return {"value": value, "grade": GRADE_MODEL, "source": source}
