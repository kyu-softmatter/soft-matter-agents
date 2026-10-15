"""The Anthropic provider driven by a stand-in client: no package, no network."""

import pytest

from dino_autofocus.assistant import Assistant
from dino_autofocus.assistant.providers import TurnRequest
from dino_autofocus.assistant.providers.anthropic import FALLBACK_BETA, AnthropicProvider
from dino_autofocus.assistant.records import RecordLog
from dino_autofocus.assistant.runner import SYSTEM_PROMPT


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


class Stream:
    def __init__(self, message, texts, fail=False):
        self.message, self.texts, self.fail = message, texts, fail

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        if self.fail:
            raise ValueError("unparseable tool input")
        for t in self.texts:
            yield Obj(type="text", text=t)

    def get_final_message(self):
        return self.message


class Client:
    def __init__(self, turns, fail_first=0):
        self.turns = list(turns)
        self.calls = []
        self.fail_first = fail_first
        self.beta = Obj(messages=Obj(stream=self.stream))

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_first:
            self.fail_first -= 1
            return Stream(None, [], fail=True)
        content, stop = self.turns.pop(0)
        usage = Obj(
            input_tokens=1200,
            output_tokens=40,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=1100,
        )
        texts = [b.text for b in content if b.type == "text"]
        return Stream(Obj(content=content, stop_reason=stop, usage=usage), texts)


def request(**kw):
    base = dict(
        model="claude-opus-5-5",
        system=SYSTEM_PROMPT,
        tools=[{"name": "t", "description": "d", "input_schema": {"type": "object"}}],
        messages=[{"role": "user", "content": "hi"}],
    )
    return TurnRequest(**{**base, **kw})


def test_request_shape():
    kw = AnthropicProvider(client=object()).request_kwargs(request(effort="high"))
    assert kw["model"] == "claude-opus-5-5"
    assert kw["system"] == [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
    ]
    assert kw["tools"][0]["eager_input_streaming"] is True
    assert kw["output_config"] == {"effort": "high"}
    assert kw["cache_control"] == {"type": "ephemeral"}
    assert kw["betas"] == [FALLBACK_BETA] and kw["fallbacks"] == "default"
    assert "thinking" not in kw
    no_fb = AnthropicProvider(client=object(), fallbacks=False).request_kwargs(request())
    assert "fallbacks" not in no_fb and "betas" not in no_fb


def test_turn_streams_text_and_returns_dicts():
    client = Client([([Obj(type="text", text="Hello")], "end_turn")])
    seen = []
    out = AnthropicProvider(client=client).turn(request(), seen.append)
    assert seen == ["Hello"]
    assert out.content == [{"type": "text", "text": "Hello"}]
    assert out.stop_reason == "end_turn"
    assert out.usage["cache_read_input_tokens"] == 1100


def test_unparseable_tool_input_is_retried_then_raised():
    client = Client([([Obj(type="text", text="ok")], "end_turn")], fail_first=1)
    assert AnthropicProvider(client=client).turn(request(), lambda t: None).content
    assert len(client.calls) == 2
    with pytest.raises(ValueError):
        AnthropicProvider(client=Client([], fail_first=5)).turn(request(), lambda t: None)


def test_same_proposal_gate_with_the_real_provider_shape():
    sent = []
    client = Client(
        [
            (
                [
                    Obj(
                        type="tool_use",
                        id="toolu_1",
                        name="propose_lights_off",
                        input={"reason": "done"},
                    )
                ],
                "tool_use",
            ),
            ([Obj(type="text", text="Proposed.")], "end_turn"),
        ]
    )
    a = Assistant(
        provider=AnthropicProvider(client=client), submit=sent.append, records=RecordLog()
    )
    ans = a.ask("lights off")
    assert sent == [] and ans.proposals[0]["status"] == "proposed"
    second = client.calls[1]
    assert second["tools"] == client.calls[0]["tools"]
    assert second["system"] == client.calls[0]["system"]
    assert second["messages"][-1]["content"][0]["tool_use_id"] == "toolu_1"
    assert ans.usage["input_tokens"] == 2400


def test_no_forced_tool_choice_and_strict_tools():
    a = Assistant(provider=AnthropicProvider(client=object()), records=RecordLog())
    kw = a.provider.request_kwargs(request(tools=a.tools.definitions(), effort=a.config.effort))
    assert kw["tool_choice"] == {"type": "auto"}
    assert all(t["strict"] is True and t["eager_input_streaming"] is True for t in kw["tools"])
    assert kw["output_config"] == {"effort": "medium"}  # set explicitly, never left to default


def test_thinking_blocks_go_back_unchanged_and_prefix_bytes_stay_put():
    import json

    think = Obj(type="thinking", thinking="", signature="sig-1")
    client = Client(
        [
            (
                [think, Obj(type="tool_use", id="toolu_9", name="get_hardware_state", input={})],
                "tool_use",
            ),
            ([Obj(type="text", text="2950 um")], "end_turn"),
        ]
    )
    a = Assistant(provider=AnthropicProvider(client=client), records=RecordLog())
    a.ask("where?")
    first, second = client.calls
    assert second["messages"][1]["content"][0] == {
        "type": "thinking",
        "thinking": "",
        "signature": "sig-1",
    }
    assert second["messages"][: len(first["messages"])] == first["messages"]
    for key in ("system", "tools", "tool_choice", "output_config"):
        assert json.dumps(first[key]).encode() == json.dumps(second[key]).encode()


def test_request_kwargs_bytes_do_not_depend_on_question_or_context():
    import json

    from dino_autofocus.assistant.tools import ToolSet

    p = AnthropicProvider(client=object())
    a = p.request_kwargs(
        request(
            tools=ToolSet().definitions(), messages=[{"role": "user", "content": "where is z?"}]
        )
    )
    b = p.request_kwargs(
        request(
            tools=ToolSet().definitions(),
            messages=[
                {"role": "user", "content": [{"type": "text", "text": "<screen_context>{}"}]}
            ],
        )
    )
    for key in ("system", "tools"):
        assert json.dumps(a[key]).encode() == json.dumps(b[key]).encode()
