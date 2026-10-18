"""The assistant's HTTP routes (server/api/assistant.py) on the real app, with a fake engine,
the fake provider and seeded fake accounts (example.test only, a test-only password).

Since soft-matter-agents card 077 no proposal reaches an engine: none is held there, a
confirmation is refused as `not_connected` and leaves the card proposed, and a rejection is
the assistant's own. The fake engine has no `submit`, so a route that tried would fail."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dino_autofocus.agents import MockStore
from dino_autofocus.assistant import AssistantConfig
from dino_autofocus.assistant.providers.fake import FakeProvider
from dino_autofocus.auth import config as auth_config
from dino_autofocus.server import create_app
from dino_autofocus.server.api import SESSION_COOKIE, AuthSeat
from dino_autofocus.server.api.assistant import build_assistant
from dino_autofocus.server.schemas import Event

LOCAL = ("127.0.0.1", 50000)
REMOTE = ("192.168.1.20", 50000)
TEST_PASSWORD = "assistant-test-pass-1"  # a test value for the seeded fake accounts
OTTO, VERA = "otto@example.test", "vera@example.test"
USERS = [
    {"name": "Otto Operator", "email": OTTO, "role": "operator"},
    {"name": "Vera Viewer", "email": VERA, "role": "viewer"},
]


class FakeEngine:
    """Events and a snapshot, and `check` as the card's gate. No `submit`: the console sends
    no command to any engine (card 077)."""

    def __init__(self) -> None:
        self.sinks: list[Callable[[Event], None]] = []

    def subscribe(self, sink):
        self.sinks.append(sink)
        return lambda: self.sinks.remove(sink)

    def snapshot(self) -> dict[str, Any]:
        return {"positions": {"x_um": 1.0, "y_um": 2.0, "z_um": 2950.0}, "running": []}

    def check(self, ops=None, context=None) -> dict:
        return {
            op: {
                "allowed": op != "focus_100x",
                "reason": "no 100x objective" if op == "focus_100x" else None,
            }
            for op in ops or []
        }

    def shutdown(self, reason: str) -> None:
        pass

    def set_local_viewers(self, count: int) -> None:
        pass


def tool_use(tool, **inp):
    return {"type": "tool_use", "name": tool, "input": inp}


def text(s):
    return {"type": "text", "text": s}


@pytest.fixture(autouse=True)
def isolated_auth_config(tmp_path, monkeypatch):
    monkeypatch.setenv(auth_config.CONFIG_DIR_ENV, str(tmp_path / "config"))
    monkeypatch.delenv(auth_config.ADMIN_EMAIL_ENV, raising=False)
    for name in ("DINO_AF_ASSISTANT_PROVIDER", "DINO_AF_ASSISTANT_DATA"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="module")
def agent_store(tmp_path_factory):
    return MockStore(tmp_path_factory.mktemp("agent-store"))


@pytest.fixture
def seat(tmp_path) -> AuthSeat:
    s = AuthSeat.from_config(tmp_path / "auth")
    s.accounts.seed(USERS, TEST_PASSWORD)
    return s


@pytest.fixture
def setup(tmp_path, seat, agent_store):
    """`setup(script, login=OTTO, remote=False, control=True)` -> (client, engine, app)."""

    def make(script=(), *, login=OTTO, remote=False, control=True, **cfg):
        engine = FakeEngine()
        app = create_app(
            engine,
            engine_name="fake",
            auth=seat,
            agent_store=agent_store,
            web_dist=tmp_path / "no-web-dist",
            remote_view=remote,
        )
        app.state.assistant = build_assistant(app.state, AssistantConfig(**cfg))
        app.state.assistant.provider = FakeProvider(list(script))
        client = TestClient(
            app, base_url="http://127.0.0.1:8765", client=REMOTE if remote else LOCAL
        )
        if login:
            result = seat.logins.login(login, TEST_PASSWORD)
            assert result.ok, result.message
            client.cookies.set(SESSION_COOKIE, result.token)
            if control and not remote and login != VERA:  # a viewer cannot take control
                seat.acquire(result.token, local=True)
        return client, engine, app

    return make


def ask(client, question="q", **body):
    r = client.post("/api/assistant/ask", json={"question": question, **body})
    lines = [json.loads(s) for s in r.text.splitlines() if s] if r.status_code == 200 else []
    return r, lines


def proposal_id(lines):
    return next(e["proposal"]["proposal_id"] for e in lines if e["type"] == "proposal")


# -- status ---------------------------------------------------------------------------


def test_status_is_exactly_three_names(setup):
    client, _, _ = setup()
    r = client.get("/api/assistant/status")
    assert r.status_code == 200
    assert r.json() == {"provider": "fake", "connected": False, "data_stage": "text"}
    client, _, _ = setup(control=False, data_policy="prompt_only")
    assert client.get("/api/assistant/status").json()["data_stage"] == "prompt_only"


def test_status_is_readable_remotely_but_not_without_login(setup):
    remote, _, _ = setup(remote=True)
    assert remote.get("/api/assistant/status").status_code == 200
    anon, _, _ = setup(login=None)
    assert anon.get("/api/assistant/status").status_code == 401


# -- ask -------------------------------------------------------------------------------


def test_ask_streams_ndjson_and_no_engine_holds_the_proposal(setup):
    client, engine, _ = setup(
        [
            [text("Checking. "), tool_use("get_hardware_state")],
            [tool_use("propose_goto_xy", x_um=10.0, y_um=20.0, sample_id="s1", reason="edge")],
            [text("Proposed; please confirm.")],
        ]
    )
    r, lines = ask(client, "go to the edge", context={"area": "map", "sample_id": "s1"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    types = [e["type"] for e in lines]
    assert types[0] == "start" and types[-1] == "done"
    assert {"text", "tool_call", "tool_result", "proposal", "usage"} <= set(types)
    cid = lines[0]["conversation_id"]
    done = lines[-1]["answer"]
    assert done["conversation_id"] == cid and done["text"].endswith("please confirm.")
    prop = next(e["proposal"] for e in lines if e["type"] == "proposal")
    assert prop["status"] == "proposed" and prop["engine_op_id"] is None
    assert prop["expected_gate"] == {"checked": True, "enabled": True, "reasons": []}
    assert not hasattr(engine, "submit")  # nothing could have been held or run


def test_ask_needs_submit_question_on_the_microscope_pc(setup):
    viewer, _, _ = setup([[text("x")]], login=VERA)
    r, _ = ask(viewer)
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "role")
    remote, _, _ = setup([[text("x")]], remote=True)
    r, _ = ask(remote)
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "remote_view")
    anon, _, _ = setup([[text("x")]], login=None)
    assert ask(anon)[0].status_code == 401


def test_ask_rejects_bad_input(setup):
    client, _, _ = setup([[text("x")]])
    assert ask(client, "  ")[0].status_code == 422
    r, _ = ask(client, context={"thumb": "data:image/png;base64,AAAA"})
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "invalid")
    r, _ = ask(client, conversation_id="conv-made-up")
    assert (r.status_code, r.json()["detail"]["code"]) == (404, "not_found")
    assert client.post("/api/assistant/ask", json={"question": "q", "x": 1}).status_code == 422


def test_provider_failure_ends_the_stream_with_one_error(setup):
    client, _, app = setup()

    class Broken:
        name = "broken"

        def turn(self, request, on_text):
            raise ConnectionError("offline")

    app.state.assistant.provider = Broken()
    r, lines = ask(client)
    assert r.status_code == 200
    assert [e["type"] for e in lines] == ["start", "error"] and "offline" in lines[1]["error"]


def test_one_conversation_across_screens(setup):
    client, _, _ = setup([[text("first")], [text("second")]])
    _, lines = ask(client, "from live", context={"area": "live"})
    cid = lines[0]["conversation_id"]
    _, lines = ask(client, "from map", context={"area": "map"}, conversation_id=cid)
    assert lines[0]["conversation_id"] == cid
    r = client.get(f"/api/assistant/conversations/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user", "assistant"]
    assert body["usage"]["output_tokens"] > 0
    assert client.get("/api/assistant/conversations/nope").status_code == 404


# -- decisions ---------------------------------------------------------------------------


def test_confirm_is_refused_as_not_connected(setup):
    """Card 077: nothing can carry out a confirmation here, so it is refused and the card
    stays proposed; the operator's control grant never reaches the browser."""
    client, _, app = setup(
        [[tool_use("propose_scan_4x", sample_id="s1", reason="map")], [text("ok")]]
    )
    _, lines = ask(client)
    pid = proposal_id(lines)
    r = client.post(f"/api/assistant/proposals/{pid}/confirm")
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "not_connected")
    assert "control_grant" not in r.text
    assert app.state.assistant.proposals.get(pid).status == "proposed"


def test_viewer_and_remote_cannot_confirm(setup, seat):
    client, engine, app = setup(
        [[tool_use("propose_goto_xy", x_um=1.0, y_um=2.0, sample_id="s", reason="r")], [text("x")]]
    )
    _, lines = ask(client)
    pid = proposal_id(lines)
    viewer = TestClient(app, base_url="http://127.0.0.1:8765", client=LOCAL)
    viewer.cookies.set(SESSION_COOKIE, seat.logins.login(VERA, TEST_PASSWORD).token)
    r = viewer.post(f"/api/assistant/proposals/{pid}/confirm")
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "role")
    remote = TestClient(app, base_url="http://127.0.0.1:8765", client=REMOTE)
    remote.cookies.set(SESSION_COOKIE, seat.logins.login(OTTO, TEST_PASSWORD).token)
    r = remote.post(f"/api/assistant/proposals/{pid}/confirm")
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "remote_view")
    assert app.state.assistant.proposals.get(pid).status == "proposed"


def test_map_flag_card_follows_d16(setup, seat):
    script = [
        [
            tool_use(
                "propose_map_flag", sample_id="s1", x_um=5.0, y_um=6.0, name="dust", reason="dust"
            )
        ],
        [text("x")],
    ]
    client, engine, app = setup(script)
    _, lines = ask(client)
    pid = proposal_id(lines)
    viewer = TestClient(app, base_url="http://127.0.0.1:8765", client=LOCAL)
    viewer.cookies.set(SESSION_COOKIE, seat.logins.login(VERA, TEST_PASSWORD).token)
    r = viewer.post(f"/api/assistant/proposals/{pid}/confirm")
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "role")
    r = client.post(f"/api/assistant/proposals/{pid}/confirm")
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "not_connected")


def test_lights_off_card_is_not_connected_either(setup):
    """A stop card too: no engine takes its stop from here (card 077)."""
    client, _, app = setup(
        [[tool_use("propose_lights_off", reason="done")], [text("x")]], control=False
    )
    _, lines = ask(client)
    pid = proposal_id(lines)
    r = client.post(f"/api/assistant/proposals/{pid}/confirm")
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "not_connected")
    assert app.state.assistant.proposals.get(pid).status == "proposed"


def test_reject_is_the_assistants_own_and_confirm_keeps_the_card(setup):
    script = [
        [
            tool_use("propose_scan_4x", sample_id="a", reason="r"),
            tool_use("propose_scan_4x", sample_id="b", reason="r"),
        ],
        [text("x")],
    ]
    client, engine, app = setup(script)
    _, lines = ask(client)
    first, second = [e["proposal"]["proposal_id"] for e in lines if e["type"] == "proposal"]
    r = client.post(f"/api/assistant/proposals/{first}/reject", json={"note": "not now"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    r = client.post(f"/api/assistant/proposals/{second}/confirm")
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "not_connected")
    assert app.state.assistant.proposals.get(second).status == "proposed"
    assert client.post("/api/assistant/proposals/nope/confirm").status_code == 404
    assert client.post("/api/assistant/proposals/nope/reject").status_code == 404


def test_questions_proposals_and_decisions_reach_the_audit_log(setup, seat):
    client, _, _ = setup([[tool_use("propose_lights_off", reason="r")], [text("x")]])
    _, lines = ask(client, "lights off?")
    client.post(f"/api/assistant/proposals/{proposal_id(lines)}/confirm")
    rows = [r for r in seat.audit.entries() if r.get("source") == "assistant"]
    kinds = [r["kind"] for r in rows]
    assert kinds == [  # no command_confirmed: confirming is refused here (card 077)
        "question_submitted",
        "command_proposed",
        "assistant_message",
    ]
    assert all(r["user_id"] == OTTO for r in rows)
    assert rows[0]["question"] == "lights off?"


def test_openapi_lists_the_routes():
    from dino_autofocus.server import create_app as make_app

    app = make_app(FakeEngine(), engine_name="fake")
    spec = app.openapi()
    paths = spec["paths"]
    for p in (
        "/api/assistant/status",
        "/api/assistant/ask",
        "/api/assistant/conversations/{conversation_id}",
        "/api/assistant/proposals/{proposal_id}/confirm",
        "/api/assistant/proposals/{proposal_id}/reject",
    ):
        assert p in paths, p
    assert (
        "application/x-ndjson" in paths["/api/assistant/ask"]["post"]["responses"]["200"]["content"]
    )
    assert set(spec["components"]["schemas"]["AssistantStatus"]["properties"]) == {
        "provider",
        "connected",
        "data_stage",
    }


def test_a_proposal_the_engine_would_refuse_shows_its_gate_and_is_not_connected(setup):
    """No engine holds a proposal (card 077), so it is not `failed` for want of a hold; the
    card's gate still says what the engine's check says, and a confirmation is refused."""
    client, _, _ = setup(
        [[tool_use("propose_focus_100x", sample_id="s", reason="r")], [text("x")]]
    )
    _, lines = ask(client)
    prop = next(e["proposal"] for e in lines if e["type"] == "proposal")
    assert prop["status"] == "proposed" and prop["engine_op_id"] is None
    assert prop["expected_gate"]["enabled"] is False  # the engine's check said no
    r = client.post(f"/api/assistant/proposals/{prop['proposal_id']}/confirm")
    assert r.status_code == 409


def test_server_import_does_not_load_the_sdk():
    import subprocess
    import sys

    code = (
        "import sys\n"
        "import dino_autofocus.server, dino_autofocus.server.api.assistant\n"
        "assert 'anthropic' not in sys.modules\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_card_gate_comes_from_the_hardware_provider_when_there_is_one(setup):
    class Hardware:
        def __init__(self):
            self.asked = []

        def check(self, op, args=None):
            self.asked.append((op, dict(args or {})))
            return False, ["no 4x objective in the hardware profile"]

    client, _, app = setup([[tool_use("propose_scan_4x", sample_id="s1", reason="r")], [text("x")]])
    hw = app.state.hardware = Hardware()
    app.state.assistant = build_assistant(app.state, AssistantConfig())
    app.state.assistant.provider = FakeProvider(
        [[tool_use("propose_scan_4x", sample_id="s1", reason="r")], [text("x")]]
    )
    _, lines = ask(client)
    prop = next(e["proposal"] for e in lines if e["type"] == "proposal")
    assert prop["expected_gate"] == {
        "checked": True,
        "enabled": False,
        "reasons": ["no 4x objective in the hardware profile"],
    }
    assert hw.asked == [("scan_4x", {"sample_id": "s1"})]


# -- T-013c: rejecting needs the same permission as confirming ---------------------------


def _client_for(app, seat, email, where=LOCAL):
    c = TestClient(app, base_url="http://127.0.0.1:8765", client=where)
    c.cookies.set(SESSION_COOKIE, seat.logins.login(email, TEST_PASSWORD).token)
    return c


@pytest.mark.parametrize(
    "tool, inp",
    [
        ("propose_goto_xy", {"x_um": 1.0, "y_um": 2.0, "sample_id": "s"}),
        ("propose_map_flag", {"sample_id": "s", "x_um": 1.0, "y_um": 2.0, "name": "n"}),
    ],
)
def test_viewer_and_remote_cannot_reject(setup, seat, tool, inp):
    client, engine, app = setup([[tool_use(tool, reason="r", **inp)], [text("x")]])
    _, lines = ask(client)
    pid = proposal_id(lines)
    r = _client_for(app, seat, VERA).post(f"/api/assistant/proposals/{pid}/reject")
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "role")
    assert r.headers["X-DinoAF-Refusal"] == "role"
    r = _client_for(app, seat, OTTO, REMOTE).post(f"/api/assistant/proposals/{pid}/reject")
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "remote_view")
    assert app.state.assistant.proposals.get(pid).status == "proposed"
    r = client.post(f"/api/assistant/proposals/{pid}/reject", json={"note": "no"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"


def test_a_stop_card_may_be_cleared_by_anyone_allowed_to_stop(setup, seat):
    client, _, app = setup(
        [[tool_use("propose_lights_off", reason="r")], [text("x")]], control=False
    )
    _, lines = ask(client)
    pid = proposal_id(lines)
    r = _client_for(app, seat, VERA).post(f"/api/assistant/proposals/{pid}/reject")
    assert r.status_code == 200 and r.json()["decided_by"] == VERA
