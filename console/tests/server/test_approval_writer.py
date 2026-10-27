"""The approval writer (console card 013): the one place the console writes into `microscope_runtime/`.

It is part of the person's guard, built on the person's word (Q-20261024-office-01, `b4f340ee`). Every
refusal is checked by listing the whole test tree before and after, and the repository's own
`microscope_runtime/approvals/` is compared by listing and by hashes once the module's tests are over.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from server_fakes import ADMIN, OPERATOR, OPERATOR2, TEST_PASSWORD, VIEWER
from test_signing import (  # noqa: F401 - fixtures and helpers shared with card 011's tests
    CHECK,
    EXAMPLE_PLAN,
    QID,
    REPO,
    body,
    place_login_file,
    refusal,
    settle,
    sma_client,
    sma_root,
    tree_hash,
    with_folder,
)

from sma_console.agents import MockStore
from sma_console.agents.mock_store import MOCK_DATA
from sma_console.agents.schema_lite import Schemas
from sma_console.agents.sma_files import plan_hash
from sma_console.auth import TooManyAttempts
from sma_console.signing import approval_writer as aw
from sma_console.signing.approval_writer import SigningRefused, write_approval

REPO_APPROVALS = REPO / "microscope_runtime" / "approvals"
SCHEMAS = Schemas(REPO / "contracts" / "schemas")
PLAN = json.loads(EXAMPLE_PLAN.read_text(encoding="utf-8"))
FILE_NAME = f"appr-{QID}-r{PLAN['revision']}.json"


@pytest.fixture(scope="module", autouse=True)
def the_repositorys_own_approvals_are_never_touched():
    before = tree_hash(REPO_APPROVALS)
    yield
    assert tree_hash(REPO_APPROVALS) == before  # same listing, same bytes


@pytest.fixture
def ready(sma_client, seat, sma_root, with_folder):
    """A real tree with the folder and the person's login file in place, the person named."""
    settle(seat, person_login=OPERATOR)
    place_login_file(sma_root, OPERATOR)
    return sma_root


def refused_and_untouched(client, root: Path, code: tuple[int, str], **over) -> None:
    before = tree_hash(root)
    r = client.post(CHECK, json=body(**over))
    assert (r.status_code, r.json()["detail"]["code"]) == code, r.text
    assert tree_hash(root) == before


# -- who may sign ------------------------------------------------------------------------------------


def test_another_login_is_refused_and_nothing_is_written(sma_client, ready):
    for other in (OPERATOR2, ADMIN, VIEWER):
        before = tree_hash(ready)
        r = sma_client(login=other).post(CHECK, json=body())
        assert r.status_code == 403, other
        assert tree_hash(ready) == before


def test_with_no_person_login_set_nothing_is_written(sma_client, seat, ready):
    settle(seat)
    refused_and_untouched(sma_client(), ready, (403, "person_not_named"))


@pytest.mark.parametrize("name", ["otto@example.test", "../otto", "", "o" * 65])
def test_a_person_login_that_is_not_a_plain_id_signs_nothing(sma_client, seat, ready, name):
    settle(seat, person_login=name)
    refused_and_untouched(sma_client(), ready, (403, "person_not_named"))


def test_the_module_itself_refuses_a_session_login_that_is_not_the_persons(ready):
    for session in (None, "", "someone-else", "x@y.test"):
        with pytest.raises(SigningRefused) as e:
            call(ready, session_login=session)
        assert e.value.code == "not_person"
    assert approvals_listing(ready) == {}


def test_the_module_refuses_when_the_person_is_named_by_something_that_is_not_a_plain_id(ready):
    for name in ("../otto", "otto@example.test", "", "-otto"):
        with pytest.raises(SigningRefused) as e:
            call(ready, session_login=name, person_login=name)
        assert e.value.code == "person_not_named"
    assert approvals_listing(ready) == {}


# -- practice ----------------------------------------------------------------------------------------


def test_under_the_mock_store_nothing_is_written_and_the_module_refuses_practice(
        engine, make_client, seat, tmp_path):
    settle(seat, person_login=OPERATOR)
    sample, practice = tree_hash(MOCK_DATA), tmp_path / "practice"
    plan = json.loads((MOCK_DATA / "microscope_agent/questions/mic-20260925-002/"
                       "plan_microscope_mic-20260925-002.json").read_text("utf-8"))
    r = make_client(engine, agent_store=MockStore(practice)).post(
        CHECK, json={"qid": "mic-20260925-002", "plan_hash": plan_hash(plan), "password": TEST_PASSWORD})
    assert r.json()["outcome"] == "practice_signed" and r.json()["file_name"] is None
    assert tree_hash(MOCK_DATA) == sample
    assert not practice.exists() or not any(practice.rglob("*.json"))
    with pytest.raises(SigningRefused) as e:  # and the module will not write for a practice store at all
        call(tmp_path, practice=True)
    assert e.value.code == "practice"


def test_a_practice_login_that_is_not_the_persons_is_refused_even_under_the_mock_store(
        engine, make_client, seat, tmp_path):
    settle(seat, person_login=OPERATOR)
    r = make_client(engine, agent_store=MockStore(tmp_path / "p"), login=OPERATOR2).post(
        CHECK, json={"qid": "mic-20260925-002", "plan_hash": "sha256:" + "0" * 64, "password": TEST_PASSWORD})
    assert r.status_code == 403


# -- the password ------------------------------------------------------------------------------------


def test_a_wrong_password_writes_nothing(sma_client, ready):
    refused_and_untouched(sma_client(), ready, (401, "bad_credentials"), password="not-the-password")


def test_a_throttled_login_writes_nothing_even_with_the_right_password(sma_client, ready):
    c = sma_client()
    for _ in range(5):
        assert c.post(CHECK, json=body(password="wrong-pass-123")).status_code == 401
    refused_and_untouched(c, ready, (429, "too_many_attempts"))


def test_the_module_lets_the_throttle_through_and_writes_nothing(ready):
    def throttled() -> bool:
        raise TooManyAttempts(30)

    with pytest.raises(TooManyAttempts):
        call(ready, check_password=throttled)
    assert approvals_listing(ready) == {}


def test_the_password_is_asked_once_and_after_the_plan_and_folder_are_known(ready, tmp_path):
    asked = []
    with pytest.raises(SigningRefused):
        call(ready, shown="sha256:" + "0" * 64, check_password=lambda: asked.append(1) or True)
    with pytest.raises(SigningRefused):
        call(tmp_path, check_password=lambda: asked.append(1) or True)  # a tree with no folder
    assert asked == []
    call(ready, check_password=lambda: asked.append(1) or True)
    assert asked == [1]


# -- the plan ----------------------------------------------------------------------------------------


def test_a_changed_plan_is_refused_by_its_fingerprint(sma_client, ready):
    refused_and_untouched(sma_client(), ready, (409, "plan_changed"), plan_hash="sha256:" + "0" * 64)


def test_a_plan_edited_on_disk_after_the_screen_showed_it_is_refused(sma_client, ready):
    shown = body()["plan_hash"]
    path = ready / "microscope_agent" / "questions" / QID / EXAMPLE_PLAN.name
    edited = {**PLAN, "revision": PLAN["revision"] + 1}
    path.write_text(json.dumps(edited), encoding="utf-8")
    r = sma_client().post(CHECK, json=body(plan_hash=shown))
    assert refusal(r) == (409, "plan_changed")
    assert r.json()["detail"]["message"] == "The plan changed; review it again."
    assert approvals_listing(ready) == {}


def test_a_plan_card_of_another_question_is_refused(ready):
    with pytest.raises(SigningRefused) as e:
        call(ready, qid="mic-20990101-001")
    assert e.value.code == "plan_changed"
    with pytest.raises(SigningRefused) as e:
        call(ready, plan_card=None)
    assert e.value.code == "plan_changed"


def test_a_plan_the_schema_cannot_take_is_refused_before_writing(ready):
    odd = {**PLAN, "qid": "mic-bad"}
    with pytest.raises(SigningRefused) as e:
        call(ready, plan_card=odd, qid="mic-bad", shown=plan_hash(odd))
    assert e.value.code == "approval_invalid"
    assert approvals_listing(ready) == {}


# -- the folder --------------------------------------------------------------------------------------


def test_a_tree_without_the_approvals_folder_is_refused_and_none_is_made(sma_client, seat, sma_root):
    settle(seat, person_login=OPERATOR)
    place_login_file(sma_root, OPERATOR)
    (sma_root / "microscope_agent" / "approvals").mkdir(parents=True, exist_ok=True)  # the old place
    before = tree_hash(sma_root)
    r = sma_client().post(CHECK, json=body())
    assert refusal(r) == (409, "no_approvals_folder")
    assert "Your approvals folder is not there" in r.json()["detail"]["message"]
    assert tree_hash(sma_root) == before
    assert not (sma_root / "microscope_runtime" / "approvals").exists()
    assert list((sma_root / "microscope_agent" / "approvals").iterdir()) == []


# -- the person's own login file ---------------------------------------------------------------------


def test_a_missing_login_file_is_refused_in_words(sma_client, ready):
    (ready / "microscope_runtime" / "envelope" / "console_login.json").unlink()
    r = sma_client().post(CHECK, json=body())
    assert refusal(r) == (409, "login_file_missing")
    assert "your own login file, placed by hand beside the safety policy, is missing" in r.json()["detail"]["message"].lower()
    assert approvals_listing(ready) == {}


@pytest.mark.parametrize("text", [
    "not json at all",
    json.dumps({"artifact": "console_login", "schema_version": "0.1", "login": OPERATOR}),  # no written_by
    json.dumps({"artifact": "console_login", "schema_version": "0.1", "login": OPERATOR,
                "written_by": "x", "written_at": "2026-10-26", "extra": 1}),
    json.dumps({"artifact": "console_login", "schema_version": "0.1", "login": "otto@example.test",
                "written_by": "x", "written_at": "2026-10-26"}),
    "[]",
])
def test_an_invalid_login_file_is_refused_in_words(sma_client, ready, text):
    (ready / "microscope_runtime" / "envelope" / "console_login.json").write_text(text, encoding="utf-8")
    r = sma_client().post(CHECK, json=body())
    assert refusal(r) == (409, "login_file_invalid")
    assert "is not valid" in r.json()["detail"]["message"]
    assert approvals_listing(ready) == {}


def test_a_login_file_that_names_another_login_is_refused_in_words(sma_client, ready):
    place_login_file(ready, "someone-else")
    r = sma_client().post(CHECK, json=body())
    assert refusal(r) == (409, "login_file_other_login")
    assert "names another login" in r.json()["detail"]["message"]
    assert approvals_listing(ready) == {}


def test_the_login_is_compared_byte_for_byte(sma_client, ready):
    place_login_file(ready, OPERATOR.upper() if OPERATOR.upper() != OPERATOR else OPERATOR + "x")
    r = sma_client().post(CHECK, json=body())
    assert refusal(r) == (409, "login_file_other_login")


def test_the_console_never_writes_the_login_file(sma_client, ready):
    path = ready / "microscope_runtime" / "envelope" / "console_login.json"
    before = path.read_bytes()
    assert sma_client().post(CHECK, json=body()).status_code == 200
    assert path.read_bytes() == before


# -- an approval that is already there ---------------------------------------------------------------


def test_an_existing_approval_of_that_name_is_never_replaced(sma_client, ready, with_folder):
    existing = with_folder / FILE_NAME
    existing.write_bytes(b"the person's earlier approval\n")
    before = tree_hash(ready)
    r = sma_client().post(CHECK, json=body())
    assert refusal(r) == (409, "already_approved")
    assert tree_hash(ready) == before and existing.read_bytes() == b"the person's earlier approval\n"


def test_signing_twice_writes_once_and_the_second_is_refused(sma_client, ready, with_folder):
    c = sma_client()
    assert c.post(CHECK, json=body()).status_code == 200
    first = (with_folder / FILE_NAME).read_bytes()
    assert refusal(c.post(CHECK, json=body())) == (409, "already_approved")
    assert (with_folder / FILE_NAME).read_bytes() == first


def test_the_module_does_not_replace_a_file_that_appears_while_it_is_writing(ready, monkeypatch):
    folder = aw.approvals_folder(ready)
    real = os.link

    def racing(src, dst):
        Path(dst).write_bytes(b"someone else got there first\n")  # after the exists-check, before the link
        return real(src, dst)

    monkeypatch.setattr(aw.os, "link", racing)
    with pytest.raises(SigningRefused) as e:
        call(ready)
    assert e.value.code == "already_approved"
    assert (folder / FILE_NAME).read_bytes() == b"someone else got there first\n"
    assert [p.name for p in folder.iterdir()] == [FILE_NAME]  # and the temporary file is gone


# -- what is written ---------------------------------------------------------------------------------


def test_a_signing_writes_exactly_one_schema_valid_file_carrying_the_mark(sma_client, seat, ready, with_folder):
    before = tree_hash(ready)
    r = sma_client().post(CHECK, json=body())
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["outcome"] == "written" and out["file_name"] == FILE_NAME
    assert out["message"] == aw.WRITTEN_MESSAGE
    assert "reads it from disk now" in out["message"] and "Commit it yourself" in out["message"]
    after = tree_hash(ready)
    added = sorted(set(after) - set(before))
    assert added == [f"microscope_runtime/approvals/{FILE_NAME}"]
    assert {k: v for k, v in after.items() if k in before} == before  # nothing else moved
    assert [p.name for p in with_folder.iterdir()] == [FILE_NAME]
    doc = json.loads((with_folder / FILE_NAME).read_text(encoding="utf-8"))
    assert SCHEMAS.validate(doc, "plan_approval.schema.json") == []
    assert doc["signed_through"] == {"via": "console", "login": OPERATOR}
    assert doc["approved_by"] == OPERATOR and doc["plan_id"] == PLAN["id"]
    assert doc["plan_revision"] == PLAN["revision"] and doc["plan_hash"] == plan_hash(PLAN)
    assert set(doc) == {"card", "schema_version", "id", "qid", "thread", "round", "revision", "author",
                        "created_at", "status", "plan_id", "plan_revision", "plan_hash", "approved_by",
                        "approved_at", "numbers", "degraded", "signed_through"}
    assert not (ready / "microscope_agent" / "approvals").exists()  # the old place stays untouched


def test_approved_at_is_utc_now(ready):
    moment = datetime(2026, 10, 26, 12, 30, 45, tzinfo=UTC)
    got = call(ready, now=lambda: moment)
    assert got.approved_at == "2026-10-26T12:30:45Z"
    doc = json.loads(got.path.read_text(encoding="utf-8"))
    assert doc["approved_at"] == "2026-10-26T12:30:45Z" and doc["created_at"] == doc["approved_at"]


def test_approved_at_is_converted_to_utc_from_another_zone(ready):
    from datetime import timedelta, timezone
    local = datetime(2026, 10, 26, 5, 30, 45, tzinfo=timezone(timedelta(hours=-7)))  # the bench's own clock
    got = call(ready, now=lambda: local)
    assert got.approved_at == "2026-10-26T12:30:45Z"


def test_the_temporary_file_is_whole_hidden_and_does_not_end_in_json(ready, monkeypatch):
    folder = aw.approvals_folder(ready)
    seen: list[tuple[str, list[str], int]] = []
    real = os.link

    def watching(src, dst):
        seen.append((Path(src).name, [p.name for p in folder.glob("*.json")], Path(src).stat().st_size))
        return real(src, dst)

    monkeypatch.setattr(aw.os, "link", watching)
    got = call(ready)
    (tmp_name, json_names, size), = seen
    assert not tmp_name.endswith(".json")  # the runtime reads every *.json in the folder
    assert json_names == []  # at that moment the runtime would have found nothing to read
    assert size == got.path.stat().st_size > 0  # and the temporary file was already whole
    assert [p.name for p in folder.iterdir()] == [FILE_NAME]


def test_no_password_appears_in_the_file_the_response_or_the_audit_log(sma_client, seat, ready, with_folder):
    secret = "very-secret-pass-77"
    r1 = sma_client().post(CHECK, json=body(password=secret))
    r2 = sma_client().post(CHECK, json=body())
    hashed = seat.accounts.get(OPERATOR).password_hash
    texts = [r1.text, r2.text, (with_folder / FILE_NAME).read_text(encoding="utf-8"),
             seat.audit.path.read_text(encoding="utf-8")]
    for text in texts:
        assert secret not in text and TEST_PASSWORD not in text and hashed not in text and "scrypt" not in text


def test_the_audit_line_names_who_what_and_which_file(sma_client, seat, ready):
    sma_client().post(CHECK, json=body())
    line = [e for e in seat.audit.entries() if e["kind"] == "approval_written"][-1]
    assert line["user_id"] == OPERATOR and line["qid"] == QID and line["plan_id"] == PLAN["id"]
    assert line["plan_revision"] == PLAN["revision"] and line["plan_hash"] == plan_hash(PLAN)
    assert line["file_name"] == FILE_NAME
    assert not any(k in line for k in ("password", "token"))


def test_a_refusal_leaves_no_approval_written_line(sma_client, seat, ready):
    sma_client().post(CHECK, json=body(password="wrong-pass-123"))
    assert not [e for e in seat.audit.entries() if e["kind"] == "approval_written"]


# -- helpers -----------------------------------------------------------------------------------------


def approvals_listing(root: Path) -> dict[str, str]:
    return tree_hash(root / "microscope_runtime" / "approvals") if (root / "microscope_runtime" / "approvals").exists() else {}


def call(tree: Path, *, session_login: str | None = OPERATOR, person_login: str | None = OPERATOR,
         practice: bool = False, qid: str = QID, shown: str | None = None, plan_card="default",
         check_password=lambda: True, now=aw._now):
    card = PLAN if plan_card == "default" else plan_card
    return write_approval(
        tree=tree, practice=practice, session_login=session_login, person_login=person_login, qid=qid,
        shown_plan_hash=shown if shown is not None else (plan_hash(card) if card is not None else "x"),
        plan_card=card, check_password=check_password, now=now)
