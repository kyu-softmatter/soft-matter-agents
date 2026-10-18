import json

import numpy as np
import pytest

from dino_autofocus.assistant.tools import (
    REMOVED_IMAGE,
    TOOL_SPECS,
    ProposalBook,
    Sources,
    ToolSet,
    check_policy,
    strip_images,
    validate,
)

READ = {s.name for s in TOOL_SPECS if s.kind == "read"}
ACTION = {s.name for s in TOOL_SPECS if s.kind == "action"}


def test_every_action_tool_only_proposes():
    assert ACTION and all(n.startswith("propose_") for n in ACTION)
    assert not any(n.startswith("propose_") for n in READ)


def test_read_tool_runs_at_once():
    ts = ToolSet(Sources(snapshot=lambda: {"position": {"z_um": 2950.5}}))
    out = ts.call("get_hardware_state", {})
    assert out.kind == "read" and not out.is_error
    assert json.loads(out.content) == {"position": {"z_um": 2950.5}}


def test_unwired_sources_answer_from_marked_placeholders():
    ts = ToolSet()
    for name, inp in [
        ("get_hardware_state", {}),
        ("get_sample", {"sample_id": "s1"}),
        ("get_sample_map", {"sample_id": "s1"}),
        ("get_simulation_status", {"run_id": "r"}),
    ]:
        assert json.loads(ts.call(name, inp).content)["source"] == "fake"
    assert all(s.stub for s in TOOL_SPECS if s.name in {"get_sample", "list_simulations"})


def test_action_tool_returns_a_draft_and_calls_nothing():
    called = []
    ts = ToolSet(Sources(snapshot=lambda: called.append(1) or {}))
    out = ts.call(
        "propose_goto_xy",
        {"x_um": 100, "y_um": -5.5, "sample_id": "s1", "reason": "look at the edge"},
    )
    assert out.kind == "action" and not called
    assert out.draft["command"] == {
        "kind": "start",
        "op": "goto_xy",
        "args": {"x_um": 100, "y_um": -5.5, "sample_id": "s1"},
    }
    assert "x=100 um" in out.draft["summary"]
    lights = ts.call("propose_lights_off", {"reason": "done"}).draft["command"]
    assert lights["kind"] == "lights_off"


@pytest.mark.parametrize(
    "inp, needle",
    [
        ({"y_um": 1, "sample_id": "s", "reason": "r"}, "missing 'x_um'"),
        ({"x_um": "1", "y_um": 1, "sample_id": "s", "reason": "r"}, "'x_um' must be number"),
        ({"x_um": True, "y_um": 1, "sample_id": "s", "reason": "r"}, "'x_um' must be number"),
        ({"x_um": 1, "y_um": 1, "sample_id": "s", "reason": "r", "speed": 9}, "unknown field"),
    ],
)
def test_model_input_is_validated(inp, needle):
    out = ToolSet().call("propose_goto_xy", inp)
    assert out.is_error and needle in out.content and out.draft is None


def test_validate_limits():
    schema = TOOL_SPECS[[s.name for s in TOOL_SPECS].index("propose_scan_4x")].input_schema
    assert validate(schema, {"sample_id": "s", "reason": "r", "overlap": 0.95})
    assert not validate(schema, {"sample_id": "s", "reason": "r", "overlap": 0.15})
    assert validate(schema, []) == ["input must be an object"]


def test_unknown_tool_and_store_errors_are_tool_errors():
    class Store:
        def get_question(self, qid, version=None):
            raise KeyError(f"no question {qid}")

    ts = ToolSet(Sources(store=Store()))
    assert ts.call("rm_rf", {}).is_error
    out = ts.call("get_question", {"qid": "mic-20260101-001"})
    assert out.is_error and "no question" in out.content


def test_store_records_become_json():
    class Rec:
        def to_dict(self):
            return {"qid": "sim-20260923-001", "status": "open"}

    class Store:
        def list_questions(self, agent):
            return [Rec()]

    out = ToolSet(Sources(store=Store())).call("list_questions", {"agent": "simulation"})
    assert json.loads(out.content) == [{"qid": "sim-20260923-001", "status": "open"}]


def test_definitions_are_fixed_and_carry_only_api_fields():
    ts = ToolSet()
    a, b = ts.definitions(), ts.definitions()
    assert a == b and [d["name"] for d in a] == [s.name for s in TOOL_SPECS]
    assert all(set(d) == {"name", "description", "input_schema", "strict"} for d in a)
    assert all(d["strict"] is True for d in a)
    a[0]["name"] = "changed"
    a[-1]["input_schema"]["properties"].clear()
    assert ts.definitions() == b  # callers cannot change the cached list


def test_sent_schemas_are_strict_compatible_and_keep_limits_as_text():
    for d in ToolSet().definitions():
        s = d["input_schema"]
        assert s["additionalProperties"] is False
        for p in s["properties"].values():
            assert not {"minimum", "maximum", "exclusiveMinimum"} & set(p)
    scan = next(d for d in ToolSet().definitions() if d["name"] == "propose_scan_4x")
    assert (
        scan["input_schema"]["properties"]["overlap"]["description"] == "Must be >= 0 and <= 0.9."
    )
    # the full schema, limits included, is still what validates the model's input
    assert (
        ToolSet().call("propose_scan_4x", {"sample_id": "s", "reason": "r", "overlap": 2}).is_error
    )


def test_prompt_only_offers_no_read_tools():
    ts = ToolSet(policy="prompt_only")
    names = {d["name"] for d in ts.definitions()}
    assert names == ACTION
    out = ts.call("get_hardware_state", {})
    assert out.is_error and "data policy" in out.content


def test_images_policy_is_blocked():
    with pytest.raises(ValueError, match="blocked"):
        check_policy("images")
    with pytest.raises(ValueError):
        ToolSet(policy="everything")


def test_strip_images():
    value = {
        "frame": np.zeros((4, 4), np.uint16),
        "jpeg": b"\xff\xd8",
        "thumb": "data:image/png;base64,AAAA",
        "blocks": [{"type": "image", "source": {}}, {"type": "text", "text": "ok"}],
        "z_um": 2950.0,
        "row": np.zeros(3),  # a 1-D vector is data, not a picture
    }
    clean, n = strip_images(value)
    assert n == 4
    assert clean["frame"] == clean["jpeg"] == clean["thumb"] == REMOVED_IMAGE
    assert clean["blocks"] == [REMOVED_IMAGE, {"type": "text", "text": "ok"}]
    assert clean["z_um"] == 2950.0


def test_read_result_has_images_removed_and_counted():
    ts = ToolSet(Sources(snapshot=lambda: {"z_um": 1.0, "last_frame": b"\x00" * 64}))
    out = ts.call("get_hardware_state", {})
    assert out.images_removed == 1
    assert json.loads(out.content) == {"z_um": 1.0, "last_frame": REMOVED_IMAGE}


def test_long_results_are_cut_with_a_note():
    ts = ToolSet(Sources(snapshot=lambda: {"log": "x" * 50_000}))
    out = ts.call("get_hardware_state", {})
    assert out.truncated and out.content.endswith("characters in all]")


def test_expected_gate_comes_from_gate_code():
    seen = []

    def gates(op, args):
        seen.append((op, args))
        return False, ["no objective map for 100x"]

    cmd = {"kind": "start", "op": "focus_100x", "args": {"sample_id": "s"}}
    assert ToolSet(Sources(gates=gates)).expected_gate(cmd) == {
        "checked": True,
        "enabled": False,
        "reasons": ["no objective map for 100x"],
    }
    assert seen == [("focus_100x", {"sample_id": "s"})]
    assert ToolSet().expected_gate(cmd)["checked"] is False


def test_proposal_book_states():
    sent = []
    book = ProposalBook(lambda cmd: sent.append(cmd) or "op-7")
    p = book.add(
        conversation_id="c",
        tool="propose_lights_off",
        command={"kind": "lights_off", "op": "", "args": {}},
        summary="s",
        reason="r",
        expected_gate={},
    )
    assert p.status == "proposed" and not sent
    with pytest.raises(ValueError):
        book.confirm(p.proposal_id, by="")
    book.confirm(p.proposal_id, by="kyu", session_id="sess-1")
    assert p.status == "confirmed" and p.op_id == "op-7" and p.decided_by == "kyu"
    assert sent == [
        {
            "kind": "lights_off",
            "op": "",
            "args": {},
            "origin": "human",
            "proposal_id": p.proposal_id,
            "conversation_id": "c",
            "user_id": "kyu",
            "session_id": "sess-1",
        }
    ]
    with pytest.raises(ValueError, match="already confirmed"):
        book.reject(p.proposal_id, by="kyu")
    with pytest.raises(KeyError):
        book.get("prop-missing")
