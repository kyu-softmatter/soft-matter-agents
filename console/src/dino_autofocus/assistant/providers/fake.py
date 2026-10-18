"""A scripted provider: no network, no cost.

Give it a script of turns; each turn is a list of content blocks (`{"type": "text", ...}`,
`{"type": "tool_use", "name": ..., "input": ...}`) or a dict `{"content": [...],
"stop_reason": ...}` to force a stop reason. Tool-use ids are filled in. When the script runs
out it answers in text that no model is connected. Every request is kept, so tests can check
what would have been sent (the same system prompt and tool list on every call).
"""

from __future__ import annotations

import copy
import itertools
import json

from . import TextSink, TurnRequest, TurnResult


def _estimate(obj: object) -> int:
    return max(1, len(json.dumps(obj, ensure_ascii=False, default=str)) // 4)


def _last_question(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m["role"] != "user" or isinstance(m["content"], str):
            continue
        texts = [b["text"] for b in m["content"] if b.get("type") == "text"]
        if texts:
            return texts[-1]
    return ""


class FakeProvider:
    name = "fake"

    def __init__(self, script: list | None = None):
        self._script = list(script or [])
        self._ids = itertools.count(1)
        self.requests: list[TurnRequest] = []

    def turn(self, request: TurnRequest, on_text: TextSink) -> TurnResult:
        self.requests.append(copy.deepcopy(request))
        if self._script:
            step = self._script.pop(0)
        else:
            q = _last_question(request.messages)
            step = [
                {
                    "type": "text",
                    "text": f"[fake provider] No model is connected. You asked: {q[:200]}",
                }
            ]
        if isinstance(step, dict):
            blocks, stop = step["content"], step.get("stop_reason")
        else:
            blocks, stop = step, None
        content = []
        for b in copy.deepcopy(blocks):
            if b["type"] == "tool_use":
                b.setdefault("id", f"toolu_fake_{next(self._ids)}")
            if b["type"] == "text":
                on_text(b["text"])
            content.append(b)
        if stop is None:
            stop = "tool_use" if any(b["type"] == "tool_use" for b in content) else "end_turn"
        usage = {
            "input_tokens": _estimate([request.system, request.tools, request.messages]),
            "output_tokens": _estimate(content),
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        return TurnResult(content=content, stop_reason=stop, usage=usage)
