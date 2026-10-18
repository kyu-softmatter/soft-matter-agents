"""Claude through the Anthropic Python SDK (Messages API, streamed).

Runs only when the server is configured with `provider=anthropic` and has credentials. The
key stays on the server: the SDK reads `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` or an
`ant auth login` profile, and nothing here returns or logs it.

The `anthropic` package is not a dependency yet (it arrives with the pyproject change after
T-009), so it is imported only inside `_client()`. Not exercised against the live API: the
tests drive `turn()` with a stand-in client.

Request shape, per call:
- the system prompt as one text block with a cache breakpoint, after the tool list, which is
  the same list in the same order on every call; tools render before system, so one
  breakpoint caches both. Top-level `cache_control` caches the conversation so far.
- `output_config.effort` always set; no `thinking` field, so the model's default (adaptive on
  Opus 5.5) stands and nothing disables it.
- `tool_choice` auto, `strict` on every tool (from `ToolSpec.definition`), and
  `eager_input_streaming`: inputs are validated in `tools.validate` before anything runs.
- the content blocks come back as dicts and go into the history unchanged, thinking blocks
  included (append-only history).
- refusal fallback (`fallbacks="default"`), on by default.
The loop around it (tool calls, proposals) is `assistant.runner`'s, shared with the fake.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import USAGE_KEYS, ProviderUnavailable, TextSink, TurnRequest, TurnResult

FALLBACK_BETA = "server-side-fallback-2026-07-01"
JSON_RETRIES = 2  # a tool input the SDK cannot parse at all: re-issue the turn this often

_WIF_VARS = (
    "ANTHROPIC_FEDERATION_RULE_ID",
    "ANTHROPIC_ORGANIZATION_ID",
    "ANTHROPIC_SERVICE_ACCOUNT_ID",
)


def package_available() -> bool:
    return importlib.util.find_spec("anthropic") is not None


def credentials(env: Mapping[str, str] | None = None, home: Path | None = None) -> tuple[bool, str]:
    """Whether the SDK would find credentials, and where. Never the credential itself."""
    env = os.environ if env is None else env
    if env.get("ANTHROPIC_API_KEY") or env.get("ANTHROPIC_AUTH_TOKEN"):
        return True, "environment"
    if env.get("ANTHROPIC_PROFILE"):
        return True, "named profile"
    if all(env.get(k) for k in _WIF_VARS) and (
        env.get("ANTHROPIC_IDENTITY_TOKEN_FILE") or env.get("ANTHROPIC_IDENTITY_TOKEN")
    ):
        return True, "workload identity"
    profiles = (home or Path.home()) / ".config" / "anthropic"
    if profiles.is_dir() and any(profiles.iterdir()):
        return True, "ant auth login profile"
    return False, "no API key or `ant auth login` profile on this server"


def connection(env: Mapping[str, str] | None = None, home: Path | None = None) -> tuple[bool, str]:
    if not package_available():
        return False, "anthropic package not installed"
    return credentials(env, home)


def _usage(u: Any) -> dict:
    return {k: int(getattr(u, k, 0) or 0) for k in USAGE_KEYS}


def _block(b: Any) -> dict:
    return b.to_dict() if hasattr(b, "to_dict") else dict(b)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client: Any = None, *, fallbacks: bool = True):
        self._client_obj = client
        self.fallbacks = fallbacks

    def _client(self) -> Any:
        if self._client_obj is None:
            ok, why = connection()
            if not ok:
                raise ProviderUnavailable(why)
            import anthropic

            self._client_obj = anthropic.Anthropic()
        return self._client_obj

    def request_kwargs(self, request: TurnRequest) -> dict:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": [
                {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
            ],
            "tools": [{**t, "eager_input_streaming": True} for t in request.tools],
            # never "any"/"tool" (a 400 on claude-opus-5-5); the system prompt says when to
            # call tools and `strict` keeps the arguments schema-valid
            "tool_choice": {"type": "auto"},
            "messages": request.messages,
            "output_config": {"effort": request.effort},
            "cache_control": {"type": "ephemeral"},
        }
        if self.fallbacks:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    def turn(self, request: TurnRequest, on_text: TextSink) -> TurnResult:
        client = self._client()
        kwargs = self.request_kwargs(request)
        failures = 0
        while True:
            try:
                with client.beta.messages.stream(**kwargs) as stream:
                    for event in stream:
                        if event.type == "text":
                            on_text(event.text)
                    message = stream.get_final_message()
                break
            except ValueError:
                # tool-input JSON the SDK could not parse; there is no tool_use id to answer,
                # so the turn is sent again. API errors are not ValueError and propagate.
                failures += 1
                if failures > JSON_RETRIES:
                    raise
        return TurnResult(
            content=[_block(b) for b in message.content],
            stop_reason=message.stop_reason,
            usage=_usage(message.usage),
        )
