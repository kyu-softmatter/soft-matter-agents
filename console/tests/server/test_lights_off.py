"""[Lights off] (console card 023 part 5): one press sends exactly `{"lights_off": true}` to the live-view host
and shows what the host answers, row by row, as the reply schema words it.

The host is a fake that records the raw bytes it was sent and answers with a reply the test chooses. The
examples and the refused replies are read from `contracts/schemas/run_interface.schema.json`, so the test
cannot drift from the schema it cites. Nothing is written into the tree, nothing is resent, and a press with
no host given sends nothing at all.
"""

from __future__ import annotations

import copy
import json
import socket
import threading

import pytest
from sma_fake_run import _Server
from test_instruments import tree, tree_hash  # noqa: F401 - the other screens' tree and its digest

from sma_console.agents import SmaFiles, sma_lights
from sma_console.agents.sma_files import repository_root

SCHEMA = json.loads((repository_root() / "contracts" / "schemas" / "run_interface.schema.json").read_text(encoding="utf-8"))
REPLY = SCHEMA["$defs"]["lights_off_reply"]
EXAMPLES: list[dict] = REPLY["examples"]
REFUSED_BY_SCHEMA: list[dict] = REPLY["x_refused"]
URL = "/api/instruments/lights-off"
LINE = b'{"lights_off": true}\n'


class FakeLightsHost:
    """Answers every line with `reply` (bytes, or None for silence). Records every raw request."""

    def __init__(self, reply: bytes | None = None) -> None:
        self.reply = reply
        self.requests: list[bytes] = []
        self.server = _Server(self._judge)
        self.server.start()

    def _judge(self, raw: bytes) -> bytes | None:
        self.requests.append(raw)
        return self.reply

    @property
    def spec(self) -> str:
        a = self.server.address()
        return f"{a['host']}:{a['port']}"

    @property
    def connections(self) -> int:
        return self.server.connections

    def close(self) -> None:
        self.server.close()


def said(doc: dict) -> bytes:
    return json.dumps(doc).encode() + b"\n"


@pytest.fixture
def host():
    made: list[FakeLightsHost] = []

    def make(reply=None) -> FakeLightsHost:
        h = FakeLightsHost(reply)
        made.append(h)
        return h

    yield make
    for h in made:
        h.close()


@pytest.fixture
def client(engine, make_client, tree):
    return lambda **kw: make_client(engine, agent_store=SmaFiles(tree, source="soft-matter-agents"), **kw)


def refusal(r):
    body = r.json()
    detail = body.get("detail", body)
    return r.status_code, detail.get("code") if isinstance(detail, dict) else None


# -- what is sent -------------------------------------------------------------------------------------


def test_a_press_sends_exactly_the_one_line_and_nothing_else(client, host):
    h = host(said(EXAMPLES[0]))
    r = client(live_host=h.spec).post(URL)
    assert r.status_code == 200
    assert h.requests == [LINE]
    assert h.connections == 1


def test_the_sent_line_is_valid_to_the_request_schema_and_the_schemas_refused_requests_are_not_sent(client, host):
    from sma_console.agents.schema_lite import Schemas

    schemas = Schemas(repository_root() / "contracts" / "schemas")
    assert schemas.validate_def(json.loads(LINE), "run_interface.schema.json", "#/$defs/lights_off_request") == []
    assert len(LINE) <= SCHEMA["$defs"]["lights_off_request"]["x_max_bytes"]
    for bad in SCHEMA["$defs"]["lights_off_request"]["x_refused"]:
        assert schemas.validate_def(bad, "run_interface.schema.json", "#/$defs/lights_off_request"), bad


@pytest.mark.parametrize("how", ["body", "query"])
def test_a_press_that_carries_anything_is_refused_and_sends_nothing(client, host, how):
    h = host(said(EXAMPLES[0]))
    c = client(live_host=h.spec)
    r = c.post(URL, json={"source": "Aura III"}) if how == "body" else c.post(URL + "?lights_on=1")
    assert refusal(r) == (400, "lights_off_takes_nothing")
    assert h.requests == [] and h.connections == 0


# -- what is shown: the schema's own examples -------------------------------------------------------


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["lights_off"] + str(i) for i, e in enumerate(EXAMPLES)])
def test_every_reply_the_schema_gives_as_an_example_is_shown_as_it_says(client, host, example):
    h = host(said(example))
    got = client(live_host=h.spec).post(URL).json()
    assert got["answer"] == example["lights_off"]
    assert got["run_id"] == example.get("run_id")
    if example["lights_off"] == "done":
        assert got["how"] == example["as"]
        assert got["sources"] == [{**s, "reason": s.get("reason")} for s in example["sources"]]  # verbatim, in order
    else:
        assert got["sources"] == [] and got["how"] is None
        assert got["reason"] == example["reason"]


def test_a_source_the_device_gave_no_read_back_for_is_shown_sent_and_never_off(client, host):
    doc = copy.deepcopy(EXAMPLES[0])
    got = client(live_host=host(said(doc)).spec).post(URL).json()
    by = {s["source"]: s for s in got["sources"]}
    assert by["DiaLamp"]["result"] == "sent" and by["DiaLamp"]["read_back"] is None
    assert by["optical tweezers"]["result"] == "not_turned_off" and by["optical tweezers"]["reason"]
    assert by["Aura III"]["result"] == "off" and by["Aura III"]["read_back"] == "0"


@pytest.mark.parametrize("bad", REFUSED_BY_SCHEMA, ids=[str(i) for i in range(len(REFUSED_BY_SCHEMA))])
def test_a_reply_the_schema_refuses_is_no_answer_and_none_of_it_is_shown(client, host, bad):
    h = host(said(bad))
    got = client(live_host=h.spec).post(URL).json()
    assert got["answer"] == "no_answer"
    assert got["sources"] == [] and got["run_id"] is None and got["how"] is None
    assert h.connections == 1  # never resent


@pytest.mark.parametrize("reply", [b"", b"\n", b"not json\n", b"[]\n", b"\xff\xfe\n", b"x" * 70000 + b"\n"],
                         ids=["closed", "blank", "text", "list", "bytes", "huge"])
def test_a_reply_that_is_not_one_json_object_is_no_answer(client, host, reply):
    h = host(reply)
    got = client(live_host=h.spec).post(URL).json()
    assert got["answer"] == "no_answer" and got["sources"] == []
    assert got["reason"]
    assert h.connections == 1


def test_a_host_that_never_answers_is_no_answer_after_the_wait_and_is_asked_once(client, host, monkeypatch):
    monkeypatch.setattr(sma_lights, "REPLY_TIMEOUT_S", 0.3)
    h = host(None)
    got = client(live_host=h.spec).post(URL).json()
    assert got["answer"] == "no_answer" and got["reason"]
    assert h.requests == [LINE] and h.connections == 1


def test_a_port_nothing_listens_on_is_no_answer(client):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    got = client(live_host=f"127.0.0.1:{port}").post(URL).json()
    assert got["answer"] == "no_answer" and got["reason"] and got["sources"] == []


def test_a_connection_that_fails_is_tried_once_and_not_again(client, monkeypatch):
    tries = []

    def refuse(*a, **k):
        tries.append(a)
        raise ConnectionRefusedError("nothing listens")

    monkeypatch.setattr(sma_lights.socket, "create_connection", refuse)
    got = client(live_host="127.0.0.1:9").post(URL).json()
    assert got["answer"] == "no_answer"
    assert len(tries) == 1


# -- which host -------------------------------------------------------------------------------------


def test_with_no_host_given_a_press_sends_nothing_and_is_no_host(client, host, tmp_path, monkeypatch):
    announced = host(said(EXAMPLES[0]))  # a host that IS running, announced where the live view looks by default
    f = tmp_path / "localappdata" / "soft-matter-agents" / "live_host.json"
    f.parent.mkdir(parents=True)
    a = announced.server.address()
    f.write_text(json.dumps({**a, "pid": 1, "started_at": "2026-10-29T10:00:00-07:00"}), encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("DINO_AF_SMA_LIVE_HOST_FILE", str(f))
    got = client().post(URL).json()
    assert got["answer"] == "no_host" and got["sources"] == [] and got["reason"]
    assert announced.requests == [] and announced.connections == 0


def test_a_host_file_given_on_the_command_line_is_followed(client, host, tmp_path):
    h = host(said(EXAMPLES[3]))
    f = tmp_path / "given.json"
    f.write_text(json.dumps({**h.server.address(), "pid": 1}), encoding="utf-8")
    got = client(live_host_file=f).post(URL).json()
    assert got["answer"] == "refused" and got["reason"] == EXAMPLES[3]["reason"]
    assert h.requests == [LINE]


def test_a_host_file_that_is_missing_or_unreadable_is_no_host_and_sends_nothing(client, tmp_path):
    f = tmp_path / "nowhere.json"
    got = client(live_host_file=f).post(URL).json()
    assert got["answer"] == "no_host" and got["reason"]
    f.write_text("{", encoding="utf-8")
    assert client(live_host_file=f).post(URL).json()["answer"] == "no_host"


def test_a_host_that_is_not_on_this_computer_is_never_connected_to(client):
    got = client(live_host="10.0.0.5:9000").post(URL).json()
    assert got["answer"] == "no_host"


# -- who may press ---------------------------------------------------------------------------------


def test_it_is_an_ordinary_write_and_not_a_stop_so_it_needs_the_login_a_stop_does_not(client, host):
    h = host(said(EXAMPLES[0]))
    r = client(live_host=h.spec, login=None).post(URL)
    assert refusal(r) == (401, "login_required")
    assert h.requests == [] and h.connections == 0


def test_a_viewer_logged_in_at_the_microscope_computer_may_press_too(client, host):
    from server_fakes import VIEWER

    h = host(said(EXAMPLES[0]))
    assert client(live_host=h.spec, login=VIEWER).post(URL).status_code == 200


def test_another_computer_is_refused_and_sends_nothing(client, host):
    h = host(said(EXAMPLES[0]))
    r = client(live_host=h.spec, remote=True).post(URL)
    assert r.status_code in (401, 403)
    assert h.requests == [] and h.connections == 0


def test_a_remote_viewer_the_server_lets_in_may_look_and_may_not_press(client, host):
    from server_fakes import VIEWER

    h = host(said(EXAMPLES[0]))  # the route's own refusal: the server's host filter is out of the way
    r = client(live_host=h.spec, remote=True, remote_view=True, login=VIEWER).post(URL)
    assert r.status_code == 403
    assert h.requests == [] and h.connections == 0


# -- what it never does ----------------------------------------------------------------------------


def test_a_press_writes_nothing_into_the_tree(client, host, tree):
    h = host(said(EXAMPLES[0]))
    before = tree_hash(tree)
    client(live_host=h.spec).post(URL)
    assert tree_hash(tree) == before


def test_two_presses_are_two_requests_and_the_second_waits_for_no_state(client, host):
    h = host(said(EXAMPLES[2]))
    c = client(live_host=h.spec)
    assert c.post(URL).json()["answer"] == "stop_sent"
    assert c.post(URL).json()["answer"] == "stop_sent"
    assert h.requests == [LINE, LINE]


def test_a_slow_host_does_not_hold_the_server_for_other_requests(client, host, monkeypatch):
    monkeypatch.setattr(sma_lights, "REPLY_TIMEOUT_S", 1.0)
    h = host(None)
    c = client(live_host=h.spec)
    done = threading.Event()
    t = threading.Thread(target=lambda: (c.post(URL), done.set()), daemon=True)
    t.start()
    assert c.get("/api/instruments/status").status_code == 200
    assert not done.is_set()  # the press is still waiting on the silent host, and the status answered
    t.join(5)
