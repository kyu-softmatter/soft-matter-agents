"""Model providers: one model turn in, content blocks out.

The conversation loop, tool dispatch and proposal gate live in `assistant.runner`, so the fake
provider exercises exactly the path the real one takes. A provider only sends one request
and returns the assistant's content blocks as plain dicts (the Messages API shapes), the stop
reason and the token usage.

`fake` is the default and needs nothing. `anthropic` imports the SDK inside its functions, so
importing this package never loads it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

PROVIDERS = ("fake", "anthropic")

TextSink = Callable[[str], None]


class ProviderUnavailable(RuntimeError):
    """The provider cannot run here: no package, or no credentials."""


@dataclass(frozen=True)
class TurnRequest:
    model: str
    system: str  # the same text on every call: it is the cached prefix
    tools: list[dict]  # likewise, in the same order
    messages: list[dict]
    max_tokens: int = 16000
    effort: str = "medium"


@dataclass
class TurnResult:
    content: list[dict]
    stop_reason: str
    usage: dict = field(default_factory=dict)


class Provider(Protocol):
    name: str

    def turn(self, request: TurnRequest, on_text: TextSink) -> TurnResult: ...


USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def add_usage(total: dict, more: dict) -> dict:
    for k in USAGE_KEYS:
        total[k] = int(total.get(k) or 0) + int(more.get(k) or 0)
    return total


def make_provider(name: str) -> Provider:
    if name == "fake":
        from .fake import FakeProvider

        return FakeProvider()
    if name == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider()
    raise ValueError(f"provider must be one of {PROVIDERS}, got {name!r}")
