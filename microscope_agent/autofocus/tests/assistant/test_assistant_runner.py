import json
import subprocess
import sys

import pytest

from dino_autofocus.assistant import Assistant, AssistantConfig, Sources, connection_status
from dino_autofocus.assistant.providers.anthropic import credentials
from dino_autofocus.assistant.providers.fake import FakeProvider
from dino_autofocus.assistant.records import RecordLog
from dino_autofocus.assistant.runner import SYSTEM_PROMPT
from dino_autofocus.assistant.tools import REMOVED_IMAGE, ConfirmRefused


class FakeEngine:
    """The EngineAPI shape T-009 assumes: submit, subscribe, snapshot."""

    def __init__(self, refuse=False):
        self.submitted = []
        self.snapshots = 0
        self.refuse = refuse

    def submit(self, cmd):
        if self.refuse:
            raise RuntimeError("preflight_failed: Z window")
        self.submitted.append(cmd)
        return f"op-{len(self.submitted)}"

    def subscribe(self, sink):
        return lambda: None

    def snapshot(self):
        self.snapshots += 1
        return {"position": {"x_um": 10.0, "y_um": 20.0, "z_um": 2950.0}, "running": None}


def fake_allows(role, action, *, local=False):
    """The T-018 `auth.roles.allows` rules for the actions used here."""
    if action in {"operate", "write_map_flag"} and not local:
        return False
    rank = {"viewer": 0, "operator": 1, "admin": 2}
    need = {"operate": 1, "write_map_flag": 1, "stop": 0}
    return rank[role] >= need[action]


def tool_use(tool, **inp):
    return {"type": "tool_use", "name": tool, "input": inp}


def text(s):
    return {"type": "text", "text": s}


def make(script, engine=None, **cfg):
    engine = engine or FakeEngine()
    provider = FakeProvider(script)
    a = Assistant(
        AssistantConfig(**cfg),
        provider=provider,
        sources=Sources(snapshot=engine.snapshot),
        submit=engine.submit,
        allows=fake_allows,
        records=RecordLog(),
    )
    return a, provider, engine


def last_tool_results(request):
    return [b for b in request.messages[-1]["content"] if b["type"] == "tool_result"]


def test_read_tool_runs_and_its_text_goes_back():
    a, provider, engine = make(
        [
            [text("Checking. "), tool_use("get_hardware_state")],
            [text("Z is 2950 um.")],
        ]
    )
    events = []
    ans = a.ask("Where is the stage?", on_event=events.append)
    assert ans.text == "Checking. Z is 2950 um." and ans.stop_reason == "end_turn"
    assert engine.snapshots == 1 and engine.submitted == []
    (res,) = last_tool_results(provider.requests[1])
    assert json.loads(res["content"])["position"]["z_um"] == 2950.0
    kinds = [e["type"] for e in events]
    assert kinds[0] == "text" and "tool_call" in kinds and kinds[-1] == "done"
    assert ans.grade == "model"


def test_action_tool_makes_a_proposal_and_runs_nothing():
    a, provider, engine = make(
        [
            [
                tool_use(
                    "propose_goto_xy",
                    x_um=1200.0,
                    y_um=-300.0,
                    sample_id="s1",
                    reason="the edge is there",
                )
            ],
            [text("I proposed the move; please confirm it.")],
        ]
    )
    ans = a.ask("Go to the edge", user_id="kyu", session_id="sess-1")
    assert engine.submitted == []  # no hardware call before a person confirms
    (p,) = ans.proposals
    assert p["status"] == "proposed" and p["origin"] == "assistant"
    assert p["conversation_id"] == ans.conversation_id
    assert p["command"] == {
        "kind": "start",
        "op": "goto_xy",
        "args": {"x_um": 1200.0, "y_um": -300.0, "sample_id": "s1"},
    }
    assert p["reason"] == "the edge is there" and p["expected_gate"]["checked"] is False
    (res,) = last_tool_results(provider.requests[1])
    body = json.loads(res["content"])
    assert body["status"] == "proposed" and "Not executed" in body["note"]
    rec = a.records.entries("proposal")[0]
    assert rec["args"]["x_um"] == {
        "value": 1200.0,
        "grade": "model",
        "source": f"assistant:{p['proposal_id']}",
    }
    assert rec["user_id"] == "kyu" and rec["session_id"] == "sess-1"


def test_confirm_sends_the_command_with_its_origin():
    a, _, engine = make([[tool_use("propose_lights_off", reason="finished")], [text("ok")]])
    pid = a.ask("lights off please").proposals[0]["proposal_id"]
    done = a.confirm(pid, by="kyu", session_id="sess-2")
    assert done["status"] == "confirmed" and done["op_id"] == "op-1"
    (cmd,) = engine.submitted
    # a stop card sends the person's own stop; the engine takes no stop from an assistant
    assert cmd["kind"] == "lights_off" and cmd["origin"] == "human"
    assert cmd["proposal_id"] == pid and cmd["user_id"] == "kyu"
    assert cmd["session_id"] == "sess-2"
    (rec,) = a.records.entries("proposal_confirmed")
    assert rec["op_id"] == "op-1" and rec["user_id"] == "kyu"
    with pytest.raises(ValueError):
        a.confirm(pid, by="kyu")  # once only
    assert len(engine.submitted) == 1


def test_reject_is_recorded_and_never_reaches_the_engine():
    a, _, engine = make(
        [[tool_use("propose_scan_4x", sample_id="s1", reason="map it")], [text("proposed")]]
    )
    pid = a.ask("scan").proposals[0]["proposal_id"]
    # T-013c: clearing a card needs the permission confirming it would (operate, local)
    for role, local in [("viewer", True), ("operator", False), (None, True)]:
        with pytest.raises(PermissionError):
            a.reject(pid, by="someone", role=role, local=local)
    assert len(a.records.entries("reject_refused")) == 3
    assert a.proposals.get(pid).status == "proposed"
    out = a.reject(pid, by="kyu", note="not now", role="operator", local=True)
    assert out["status"] == "rejected" and out["note"] == "not now"
    (rec,) = a.records.entries("proposal_rejected")
    assert rec["proposal_id"] == pid and rec["user_id"] == "kyu"
    assert rec["permission"] == "operate"
    with pytest.raises(ValueError):
        a.confirm(pid, by="kyu")
    assert engine.submitted == []


def test_engine_refusal_keeps_the_card_proposed():
    a, _, engine = make(
        [[tool_use("propose_focus_100x", sample_id="s", reason="r")], [text("x")]],
        engine=FakeEngine(refuse=True),
    )
    pid = a.ask("focus").proposals[0]["proposal_id"]
    with pytest.raises(ConfirmRefused, match="Z window"):
        a.confirm(pid, by="kyu", role="operator", local=True)
    p = a.proposals.get(pid)
    assert p.status == "proposed" and "Z window" in p.note and p.decided_by is None
    assert "Z window" in a.records.entries("proposal_failed")[0]["note"]


def test_no_engine_means_no_confirmation():
    a = Assistant(
        provider=FakeProvider([[tool_use("propose_lights_off", reason="r")], [text("x")]]),
        records=RecordLog(),
    )
    pid = a.ask("off").proposals[0]["proposal_id"]
    with pytest.raises(RuntimeError, match="no engine"):
        a.confirm(pid, by="kyu")


def test_system_prompt_and_tools_are_the_same_on_every_call():
    a, provider, _ = make(
        [
            [tool_use("get_hardware_state")],
            [text("one")],
            [tool_use("list_simulations")],
            [text("two")],
        ]
    )
    a.ask("first", context={"area": "live"})
    a.ask("second", context={"area": "simulation", "run_id": "run-1"})
    reqs = provider.requests
    assert len(reqs) == 4
    assert all(r.system == SYSTEM_PROMPT for r in reqs)
    assert all(r.tools == reqs[0].tools for r in reqs)
    assert all(r.model == "claude-opus-5-5" for r in reqs)
    # the screen context travels in the user message, not in the cached prefix
    assert "run-1" not in reqs[3].system and "run-1" in json.dumps(reqs[3].messages)


def test_screen_context_is_short_text_only():
    a, provider, _ = make([[text("ok")]])
    a.ask("what is selected?", context={"area": "map", "sample_id": "s1", "region": [1, 2, 3, 4]})
    first = provider.requests[0].messages[0]["content"][0]["text"]
    assert first.startswith("<screen_context>") and '"sample_id": "s1"' in first
    for bad in [{"img": "data:image/png;base64,AA"}, {"blob": "x" * 500}, {"f": b"raw"}]:
        with pytest.raises(ValueError):
            a.ask("q", context=bad)
    with pytest.raises(ValueError):
        a.ask("   ")


def test_one_conversation_across_screens():
    a, provider, _ = make([[text("first answer")], [text("second answer")]])
    cid = a.ask("from the live screen", context={"area": "live"}).conversation_id
    ans = a.ask("from the map screen", context={"area": "map"}, conversation_id=cid)
    assert ans.conversation_id == cid
    msgs = provider.requests[1].messages
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    hist = a.conversation(cid)
    assert len(hist["messages"]) == 4 and hist["usage"]["output_tokens"] > 0
    assert a.ask("new").conversation_id != cid


def test_usage_is_shown_and_recorded_per_answer():
    a, _, _ = make([[tool_use("get_hardware_state")], [text("done")]])
    events = []
    ans = a.ask("q", on_event=events.append)
    turns = a.records.entries("model_turn")
    assert len(turns) == 2
    total = sum(t["usage"]["input_tokens"] for t in turns)
    assert ans.usage["input_tokens"] == total > 0
    (rec,) = a.records.entries("answer")
    assert rec["usage"] == ans.usage and rec["grade"] == "model"
    assert sum(e["type"] == "usage" for e in events) == 2


def test_images_in_tool_results_are_removed_and_recorded():
    provider = FakeProvider([[tool_use("get_hardware_state")], [text("ok")]])
    a = Assistant(
        provider=provider,
        records=RecordLog(),
        sources=Sources(snapshot=lambda: {"z_um": 2950.0, "frame": b"\x00\x01" * 100}),
    )
    a.ask("show me")
    (res,) = last_tool_results(provider.requests[1])
    assert json.loads(res["content"]) == {"z_um": 2950.0, "frame": REMOVED_IMAGE}
    (rec,) = a.records.entries("tool_call")
    assert rec["images_removed"] == 1


def test_prompt_only_sends_no_read_tools_and_refuses_them():
    a, provider, engine = make(
        [[tool_use("get_hardware_state")], [text("cannot")]], data_policy="prompt_only"
    )
    a.ask("where is the stage?")
    names = {t["name"] for t in provider.requests[0].tools}
    assert "get_hardware_state" not in names and "propose_lights_off" in names
    (res,) = last_tool_results(provider.requests[1])
    assert res["is_error"] and "data policy" in res["content"]
    assert engine.snapshots == 0


def test_cut_off_turn_runs_no_tools():
    a, provider, engine = make(
        [
            {"content": [tool_use("propose_goto_xy", x_um=1.0)], "stop_reason": "max_tokens"},
        ]
    )
    ans = a.ask("move")
    assert ans.stop_reason == "max_tokens" and ans.proposals == [] and ans.tool_calls == []
    msgs = a.conversation(ans.conversation_id)["messages"]
    assert msgs[-1]["content"][0]["is_error"] is True  # every tool_use is answered
    assert a.proposals.list() == []


def test_loop_stops_after_max_steps():
    a, provider, _ = make([[tool_use("get_hardware_state")]] * 5, max_steps=3)
    ans = a.ask("loop")
    assert ans.stop_reason == "max_steps" and len(provider.requests) == 3


def test_provider_failure_is_recorded():
    class Broken:
        name = "broken"

        def turn(self, request, on_text):
            raise ConnectionError("offline")

    a = Assistant(provider=Broken(), records=RecordLog())
    with pytest.raises(ConnectionError):
        a.ask("q")
    assert "offline" in a.records.entries("error")[0]["error"]


def test_default_fake_answers_without_a_script():
    a = Assistant(records=RecordLog())
    ans = a.ask("hello")
    assert ans.provider == "fake" and "No model is connected" in ans.text


def test_records_go_to_a_file(tmp_path):
    seen = []
    a = Assistant(
        AssistantConfig(records_dir=tmp_path),
        provider=FakeProvider([[tool_use("propose_lights_off", reason="r")], [text("x")]]),
        submit=lambda cmd: "op-9",
    )
    a.records._sinks.append(seen.append)
    pid = a.ask("off", user_id="kyu").proposals[0]["proposal_id"]
    a.confirm(pid, by="kyu")
    lines = [json.loads(s) for s in (tmp_path / "assistant.jsonl").read_text("utf-8").splitlines()]
    kinds = [r["kind"] for r in lines]
    assert kinds == [
        "question",
        "model_turn",
        "proposal",
        "tool_call",
        "model_turn",
        "answer",
        "proposal_confirmed",
    ]
    assert len(seen) == len(lines)
    assert a.records.entries("answer", conversation_id=lines[0]["conversation_id"])


# --------------------------------------------------------------------------- config, status


def test_config_from_env():
    c = AssistantConfig.from_env({"DINO_AF_ASSISTANT_DATA": "prompt_only"})
    assert c.provider == "fake" and c.data_policy == "prompt_only" and c.model == "claude-opus-5-5"
    with pytest.raises(ValueError, match="blocked"):
        AssistantConfig.from_env({"DINO_AF_ASSISTANT_DATA": "images"})
    with pytest.raises(ValueError):
        AssistantConfig(provider="openai")


def test_status_fake():
    s = connection_status(AssistantConfig())
    assert s == {"provider": "fake", "connected": False, "data_stage": "text"}
    s = connection_status(AssistantConfig(data_policy="prompt_only"))
    assert s["data_stage"] == "prompt_only"


def test_status_without_credentials_is_not_connected(tmp_path):
    s = connection_status(AssistantConfig(provider="anthropic"), env={}, home=tmp_path)
    assert s == {"provider": "anthropic", "connected": False, "data_stage": "text"}
    ok, why = credentials({}, home=tmp_path)
    assert not ok and "no API key" in why


def test_status_never_shows_the_key(tmp_path):
    env = {"ANTHROPIC_API_KEY": "test-key-not-real-123"}
    ok, why = credentials(env, home=tmp_path)
    assert ok and why == "environment"
    s = connection_status(AssistantConfig(provider="anthropic"), env=env)
    assert "test-key-not-real-123" not in json.dumps(s)


def test_import_loads_neither_anthropic_nor_torch():
    code = (
        "import sys\n"
        "import dino_autofocus.assistant, dino_autofocus.assistant.providers.anthropic\n"
        "from dino_autofocus.assistant import Assistant\n"
        "Assistant().ask('hi')\n"
        "bad = {'anthropic', 'torch'} & set(sys.modules)\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


# --------------------------------------------------------------------------- loop conditions
# (PLAN.md 5절 D6: the conditions under which the loop is ours rather than the Tool Runner)


def test_refusal_runs_no_tools():
    a, provider, engine = make(
        [
            {
                "content": [tool_use("propose_lights_off", reason="r")],
                "stop_reason": "refusal",
            }
        ]
    )
    ans = a.ask("q")
    assert ans.stop_reason == "refusal" and ans.proposals == [] and len(provider.requests) == 1
    assert a.proposals.list() == [] and engine.submitted == []


def test_several_tool_calls_answer_in_one_user_message():
    a, provider, engine = make(
        [
            [
                tool_use("get_hardware_state"),
                tool_use("get_sample", sample_id=7),  # wrong type: fails validation
                tool_use("propose_lights_off", reason="r"),
            ],
            [text("done")],
        ]
    )
    ans = a.ask("q")
    msgs = provider.requests[1].messages
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    results = msgs[-1]["content"]
    assert [b["type"] for b in results] == ["tool_result"] * 3
    ids = [b["id"] for b in provider.requests[1].messages[1]["content"]]
    assert [b["tool_use_id"] for b in results] == ids
    assert [b.get("is_error", False) for b in results] == [False, True, False]
    assert engine.snapshots == 1 and len(ans.proposals) == 1


def test_history_is_append_only_and_keeps_thinking_blocks():
    thinking = {"type": "thinking", "thinking": "", "signature": "sig-abc"}
    turn1 = [dict(thinking), text("Looking. "), tool_use("get_hardware_state")]
    a, provider, _ = make([turn1, [text("Z is 2950.")], [text("again")]])
    cid = a.ask("q1").conversation_id
    a.ask("q2", conversation_id=cid)
    first, second, third = provider.requests
    sent_back = second.messages[1]["content"]
    assert sent_back[0] == thinking and sent_back[1] == text("Looking. ")
    # every later request starts with every earlier one, unchanged
    assert second.messages[: len(first.messages)] == first.messages
    assert third.messages[: len(second.messages)] == second.messages


def test_system_prompt_and_tools_are_byte_stable():
    def sent_bytes():
        a, provider, _ = make([[tool_use("get_hardware_state")], [text("x")]])
        a.ask("q", context={"area": "live", "t": 1.5})
        return [
            json.dumps([r.system, r.tools], ensure_ascii=False).encode() for r in provider.requests
        ]

    one, two = sent_bytes(), sent_bytes()
    assert len(set(one + two)) == 1  # same bytes across calls and across instances
    assert "datetime" not in SYSTEM_PROMPT and "{" not in SYSTEM_PROMPT


def test_any_source_failure_still_answers_every_tool_use():
    class BrokenStore:
        def list_inbox(self):
            raise RuntimeError("share offline")

    def broken_gates(op, args):
        raise TypeError("bad profile")

    provider = FakeProvider(
        [
            [
                tool_use("get_hardware_state"),
                tool_use("list_inbox"),
                tool_use("propose_lights_off", reason="r"),
            ],
            [text("done")],
            [text("still fine")],
        ]
    )
    a = Assistant(
        provider=provider,
        records=RecordLog(),
        sources=Sources(store=BrokenStore(), gates=broken_gates),
    )
    ans = a.ask("q")
    results = provider.requests[1].messages[-1]["content"]
    assert [b.get("is_error", False) for b in results] == [False, True, False]
    assert "share offline" in results[1]["content"]
    assert ans.proposals[0]["expected_gate"]["checked"] is False
    assert "gate check failed" in ans.proposals[0]["expected_gate"]["reasons"][0]
    a.ask("next", conversation_id=ans.conversation_id)  # the history is still valid
    roles = [m["role"] for m in provider.requests[2].messages]
    assert roles == ["user", "assistant", "user", "assistant", "user"]


def test_thinking_block_is_resent_byte_identical():
    thinking = {"type": "thinking", "thinking": "", "signature": "EqQBCkYIBxgCKkB=="}
    a, provider, _ = make([[thinking, tool_use("get_hardware_state")], [text("ok")]])
    a.ask("q")
    sent = provider.requests[1].messages[1]["content"][0]
    assert json.dumps(sent, sort_keys=False).encode() == json.dumps(thinking).encode()


def test_tool_definitions_are_byte_stable_across_toolsets():
    from dino_autofocus.assistant.tools import ToolSet

    one = json.dumps(ToolSet().definitions()).encode()
    two = json.dumps(ToolSet(Sources(snapshot=lambda: {})).definitions()).encode()
    assert one == two


# --------------------------------------------------------------------------- D16, rule 12


def flag_proposal(a):
    ans = a.ask(
        "flag it",
        context={"area": "map"},
    )
    return ans.proposals[0]["proposal_id"]


def flag_assistant():
    return make(
        [
            [
                tool_use(
                    "propose_map_flag",
                    sample_id="s1",
                    x_um=5.0,
                    y_um=6.0,
                    name="dust",
                    reason="looks like dust",
                )
            ],
            [text("proposed")],
        ]
    )


@pytest.mark.parametrize(
    "role, local", [("viewer", True), ("viewer", False), ("operator", False), (None, True)]
)
def test_map_flag_proposal_needs_write_map_flag(role, local):
    a, _, engine = flag_assistant()
    pid = flag_proposal(a)
    assert a.proposals.get(pid).command["op"] == "map_flag"
    with pytest.raises(PermissionError):
        a.confirm(pid, by="someone", role=role, local=local)
    assert engine.submitted == [] and a.proposals.get(pid).status == "proposed"
    (rec,) = a.records.entries("confirm_refused")
    assert rec["permission"] == "write_map_flag" and rec["role"] == role


def test_map_flag_proposal_confirmed_by_the_local_operator():
    a, _, engine = flag_assistant()
    pid = flag_proposal(a)
    out = a.confirm(pid, by="kyu", role="operator", local=True)
    assert out["status"] == "confirmed" and engine.submitted[0]["op"] == "map_flag"
    assert a.records.entries("proposal_confirmed")[0]["permission"] == "write_map_flag"


@pytest.mark.parametrize(
    "op", ["map_flag", "map_flag_retire", "candidate_confirm", "candidate_reject"]
)
def test_every_map_write_needs_write_map_flag(op):
    from dino_autofocus.assistant.tools import ProposalBook, required_permission

    cmd = {"kind": "start", "op": op, "args": {}}
    assert required_permission(cmd) == "write_map_flag"
    seen = []

    def allows(role, perm, *, local=False):
        seen.append(perm)
        return False

    book = ProposalBook(lambda c: "op-1", allows=allows)
    p = book.add(
        conversation_id="c", tool="t", command=cmd, summary="s", reason="r", expected_gate={}
    )
    with pytest.raises(PermissionError):
        book.confirm(p.proposal_id, by="kyu", role="operator", local=True)
    assert seen == ["write_map_flag"] and p.status == "proposed"


def test_motion_needs_operate_and_stops_need_nothing():
    a, _, engine = make(
        [
            [
                tool_use("propose_goto_xy", x_um=1.0, y_um=2.0, sample_id="s", reason="r"),
                tool_use("propose_lights_off", reason="r"),
            ],
            [text("x")],
        ]
    )
    move, off = (p["proposal_id"] for p in a.ask("q").proposals)
    with pytest.raises(PermissionError):
        a.confirm(move, by="v", role="viewer", local=True)
    with pytest.raises(PermissionError):
        a.confirm(move, by="op", role="operator", local=False)  # remote: read only
    a.confirm(off, by="anyone", role=None, local=False)  # rule 12: stops always pass
    a.confirm(move, by="op", role="operator", local=True)
    assert [c["kind"] for c in engine.submitted] == ["lights_off", "start"]


def test_without_a_permission_check_only_stops_confirm():
    engine = FakeEngine()
    a = Assistant(
        provider=FakeProvider(
            [
                [
                    tool_use("propose_scan_4x", sample_id="s", reason="r"),
                    tool_use("propose_lights_off", reason="r"),
                ],
                [text("x")],
            ]
        ),
        submit=engine.submit,
        records=RecordLog(),
    )
    scan, off = (p["proposal_id"] for p in a.ask("q").proposals)
    with pytest.raises(PermissionError, match="no permission check"):
        a.confirm(scan, by="kyu", role="admin", local=True)
    a.confirm(off, by="kyu")
    assert [c["kind"] for c in engine.submitted] == ["lights_off"]
