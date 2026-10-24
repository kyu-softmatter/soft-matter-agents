"""The sign dialog's server side (console card 011, plan.md 6.1, 15.1): it checks and writes nothing.

The part that writes an approval into `microscope_runtime/approvals/` is part of the person's guard and
is built only on the person's word (Q-20261024-office-01, not answered). So these tests hold the
console to the other half: who may see Sign, the fingerprint the dialog shows, the password check with
its throttle, and that **nothing is written anywhere**.
"""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from server_fakes import ADMIN, OPERATOR, OPERATOR2, TEST_PASSWORD, VIEWER

from sma_console.agents import MockStore, SmaFiles
from sma_console.agents.mock_store import MOCK_DATA
from sma_console.agents.sma_files import plan_hash, repository_root
from sma_console.server.api import REFUSAL_HEADER

REPO = repository_root()
EXAMPLE_PLAN = REPO / "contracts" / "examples" / "plan_microscope_mic-20260917-001.json"
EXAMPLE_APPROVAL = REPO / "contracts" / "examples" / "plan_approval.json"
QID = "mic-20260917-001"
STATE = "/api/console/signing"
CHECK = "/api/console/sign-check"
NOT_BUILT = "Signing is not built yet: the part that writes your approval waits for your OK."


def refusal(r) -> tuple[int, str]:
    assert r.headers[REFUSAL_HEADER] == r.json()["detail"]["code"]
    return r.status_code, r.json()["detail"]["code"]


def tree_hash(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def card_sha_of_validator() -> object:
    """`card_sha` exactly as contracts/validate.py has it, taken from that file's own source."""
    tree = ast.parse((REPO / "contracts" / "validate.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "card_sha")
    fn.decorator_list = []
    ns: dict = {"hashlib": hashlib, "json": json}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "validate.py", "exec"), ns)  # noqa: S102
    return ns["card_sha"]


@pytest.fixture
def sma_root(tmp_path):
    """The sample as a soft-matter-agents tree, plus the example plan as a question of its own."""
    root = tmp_path / "sma"
    shutil.copytree(MOCK_DATA, root)
    shutil.rmtree(root / "console")
    q = root / "microscope_agent" / "questions" / QID
    q.mkdir(parents=True)
    shutil.copy(EXAMPLE_PLAN, q / EXAMPLE_PLAN.name)
    return root


def settle(seat, **settings) -> None:
    folder = seat.accounts.config_dir
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "settings.json").write_text(json.dumps(settings), encoding="utf-8")


@pytest.fixture
def sma_client(engine, make_client, sma_root):
    return lambda **kw: make_client(engine, agent_store=SmaFiles(sma_root, source="soft-matter-agents"), **kw)


@pytest.fixture
def with_folder(sma_root):
    (sma_root / "microscope_runtime" / "approvals").mkdir(parents=True)
    return sma_root / "microscope_runtime" / "approvals"


def body(**over):
    return {"qid": QID, "plan_hash": plan_hash(json.loads(EXAMPLE_PLAN.read_text("utf-8"))),
            "password": TEST_PASSWORD, **over}


# -- the fingerprint ---------------------------------------------------------------------------------


def test_the_fingerprint_is_card_sha_of_the_example_plan_and_its_approvals_plan_hash():
    plan = json.loads(EXAMPLE_PLAN.read_text(encoding="utf-8"))
    approval = json.loads(EXAMPLE_APPROVAL.read_text(encoding="utf-8"))
    assert plan["status"] == "APPROVED"  # status moves along the machine and is not in the hash
    assert plan_hash(plan) == card_sha_of_validator()(plan) == approval["plan_hash"]
    assert plan_hash({**plan, "status": "PROPOSED"}) == approval["plan_hash"]
    assert plan_hash({**plan, "revision": 2}) != approval["plan_hash"]


def test_the_question_detail_carries_that_fingerprint_in_full(sma_client):
    d = sma_client().get(f"/api/console/questions/{QID}").json()
    approval = json.loads(EXAMPLE_APPROVAL.read_text(encoding="utf-8"))
    assert d["plan_hash"] == approval["plan_hash"] and len(d["plan_hash"]) == len("sha256:") + 64


# -- who sees Sign ----------------------------------------------------------------------------------


def test_with_no_person_login_nobody_may_sign(sma_client, seat):
    for login in (OPERATOR, ADMIN, VIEWER):
        got = sma_client(login=login).get(STATE).json()
        assert got["person_named"] is False and got["is_person"] is False, login


def test_only_the_named_login_is_the_person(sma_client, seat):
    settle(seat, person_login=OPERATOR)
    assert sma_client(login=OPERATOR).get(STATE).json()["is_person"] is True
    for other in (OPERATOR2, ADMIN, VIEWER):
        got = sma_client(login=other).get(STATE).json()
        assert got["person_named"] is True and got["is_person"] is False, other


def test_a_person_login_that_is_not_a_plain_id_names_nobody(sma_client, seat):
    settle(seat, person_login="otto@example.test")
    got = sma_client(login=OPERATOR).get(STATE).json()
    assert got == {**got, "person_named": False, "is_person": False}


def test_the_state_needs_a_login(sma_client):
    assert sma_client(login=None).get(STATE).status_code == 401


def test_the_state_says_whether_the_approvals_folder_is_there(sma_client, seat, sma_root, with_folder):
    settle(seat, person_login=OPERATOR)
    assert sma_client().get(STATE).json()["approvals_folder"] is True
    shutil.rmtree(with_folder)
    assert sma_client().get(STATE).json()["approvals_folder"] is False


def test_under_the_mock_store_it_is_practice_and_needs_no_folder(engine, make_client, seat, tmp_path):
    settle(seat, person_login=OPERATOR)
    got = make_client(engine, agent_store=MockStore(tmp_path / "p")).get(STATE).json()
    assert got["practice"] is True and got["approvals_folder"] is True and got["is_person"] is True


def test_the_old_place_is_not_a_place_to_sign(sma_client, seat, sma_root):
    settle(seat, person_login=OPERATOR)
    (sma_root / "microscope_agent" / "approvals").mkdir(parents=True, exist_ok=True)
    assert sma_client().get(STATE).json()["approvals_folder"] is False


# -- the check ---------------------------------------------------------------------------------------


def test_sign_answers_that_it_is_not_built_and_writes_nothing(sma_client, seat, sma_root, with_folder):
    settle(seat, person_login=OPERATOR)
    before_tree, before_repo = tree_hash(sma_root), tree_hash(REPO / "console" / "src")
    r = sma_client().post(CHECK, json=body())
    assert r.status_code == 200, r.text
    assert r.json() == {"outcome": "not_built", "message": NOT_BUILT}
    assert tree_hash(sma_root) == before_tree and list(with_folder.iterdir()) == []
    assert tree_hash(REPO / "console" / "src") == before_repo


def test_under_the_mock_store_a_practice_login_is_shown_as_signed_and_nothing_is_written(
        engine, make_client, seat, tmp_path):
    settle(seat, person_login=OPERATOR)
    store = MockStore(tmp_path / "practice")
    sample = tree_hash(MOCK_DATA)
    r = make_client(engine, agent_store=store).post(CHECK, json={
        "qid": "mic-20260925-002",
        "plan_hash": plan_hash(json.loads((MOCK_DATA / "microscope_agent/questions/mic-20260925-002/"
                                          "plan_microscope_mic-20260925-002.json").read_text("utf-8"))),
        "password": TEST_PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "practice_signed" and "Nothing was written" in r.json()["message"]
    assert tree_hash(MOCK_DATA) == sample
    assert not (tmp_path / "practice").exists() or list((tmp_path / "practice").rglob("*.json")) == []


def test_a_wrong_password_is_refused_and_counted(sma_client, seat, with_folder):
    settle(seat, person_login=OPERATOR)
    c = sma_client()
    r = c.post(CHECK, json=body(password="not-the-password"))
    assert refusal(r) == (401, "bad_credentials")
    assert "not-the-password" not in r.text
    assert list(with_folder.iterdir()) == []


def test_too_many_wrong_passwords_are_throttled_and_a_right_one_waits(sma_client, seat, with_folder):
    settle(seat, person_login=OPERATOR)
    c = sma_client()
    codes = [c.post(CHECK, json=body(password="wrong-pass-123")).status_code for _ in range(5)]
    assert codes == [401] * 5
    locked = c.post(CHECK, json=body())  # the right password, but the account is locked for a while
    assert refusal(locked) == (429, "too_many_attempts")
    assert int(locked.headers["Retry-After"]) > 0
    assert list(with_folder.iterdir()) == []


def test_only_the_person_may_check(sma_client, seat, with_folder):
    settle(seat, person_login=OPERATOR)
    for other in (OPERATOR2, ADMIN, VIEWER):
        r = sma_client(login=other).post(CHECK, json=body())
        assert r.status_code == 403, other
        assert refusal(r)[1] in ("not_person", "role")
    settle(seat)  # nobody named
    r = sma_client().post(CHECK, json=body())
    assert refusal(r) == (403, "person_not_named")


def test_a_missing_approvals_folder_means_nothing_can_be_signed_and_no_other_place_is_offered(
        sma_client, seat, sma_root):
    settle(seat, person_login=OPERATOR)
    (sma_root / "microscope_agent" / "approvals").mkdir(parents=True, exist_ok=True)  # the old place
    before = tree_hash(sma_root)
    r = sma_client().post(CHECK, json=body())
    assert refusal(r) == (409, "no_approvals_folder")
    message = r.json()["detail"]["message"]
    assert "microscope_runtime/approvals/" in message and "microscope_agent" not in message
    assert tree_hash(sma_root) == before
    assert not (sma_root / "microscope_runtime").exists()  # not even made


def test_a_missing_folder_is_said_before_the_password_is_looked_at(sma_client, seat):
    settle(seat, person_login=OPERATOR)
    c = sma_client()
    codes = [c.post(CHECK, json=body(password="wrong-pass-123")).status_code for _ in range(7)]
    assert codes == [409] * 7  # it never counted a wrong password: no password was asked of anyone


def test_the_plan_must_be_the_one_whose_fingerprint_is_shown(sma_client, seat, with_folder):
    settle(seat, person_login=OPERATOR)
    c = sma_client()
    assert refusal(c.post(CHECK, json=body(plan_hash="sha256:" + "0" * 64))) == (409, "plan_changed")
    assert refusal(c.post(CHECK, json=body(qid="mic-20990101-001"))) == (404, "not_found")
    assert refusal(c.post(CHECK, json=body(qid="mic-20260925-001", plan_hash="sha256:" + "0" * 64)))[0] in (404, 409)
    assert list(with_folder.iterdir()) == []


@pytest.mark.parametrize("extra", [{"login": "otto"}, {"approved_by": "otto"}, {"path": "x"}])
def test_the_request_takes_no_other_field(sma_client, seat, with_folder, extra):
    settle(seat, person_login=OPERATOR)
    assert sma_client().post(CHECK, json={**body(), **extra}).status_code == 422


def test_a_remote_browser_and_a_locked_login_cannot_check(sma_client, seat, with_folder):
    settle(seat, person_login=OPERATOR)
    assert sma_client(remote=True).post(CHECK, json=body()).status_code == 403
    assert sma_client(login=None).post(CHECK, json=body()).status_code == 401
    c = sma_client()
    seat.logins.lock(c.login_token)
    assert c.post(CHECK, json=body()).status_code == 423


def test_no_password_and_no_hash_of_one_in_any_response_or_log_line(sma_client, seat, with_folder):
    settle(seat, person_login=OPERATOR)
    c = sma_client()
    secret = "very-secret-pass-77"
    texts = [c.post(CHECK, json=body(password=secret)).text, c.post(CHECK, json=body()).text, c.get(STATE).text]
    hashed = seat.accounts.get(OPERATOR).password_hash
    for text in texts:
        assert secret not in text and TEST_PASSWORD not in text and hashed not in text and "scrypt" not in text
    log = seat.audit.path.read_text(encoding="utf-8")
    assert secret not in log and TEST_PASSWORD not in log and hashed not in log and "scrypt" not in log
    kinds = [e["kind"] for e in seat.audit.entries()]
    assert "login_failed" in kinds and "sign_checked" in kinds
    line = [e for e in seat.audit.entries() if e["kind"] == "sign_checked"][-1]
    assert line["user_id"] == OPERATOR and line["qid"] == QID and line["outcome"] == "not_built"
