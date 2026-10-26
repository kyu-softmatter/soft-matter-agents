"""The Experiments screens' server side (console card 014): show what is on disk, offer one run request.

The console reads plans, approvals and runs and says in words where each one stands. It starts nothing:
the one write route here, `POST /api/experiments/run`, answers "not built yet" and sends nothing until the
runtime has the part that receives it. Under the mock store everything is example data and says so.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from server_fakes import ADMIN, OPERATOR, OPERATOR2, VIEWER
from sma_fake_run import FakeSmaRun, sma_tree, tree_state

from sma_console.agents import MockStore, SmaFiles, experiments
from sma_console.agents.mock_store import MOCK_DATA
from sma_console.agents.sma_files import plan_hash, repository_root
from sma_console.server.api import REFUSAL_HEADER

REPO = repository_root()
PLANS, RUN, SAMPLE, MAP = ("/api/experiments/" + p for p in ("plans", "run", "sample", "sample-map"))
QID = "mic-20261026-001"
PLAN_ID = f"plan-{QID}-r1"
EXAMPLE = "example data"
DEFS = json.loads((REPO / "contracts" / "schemas" / "run_interface.schema.json").read_text(encoding="utf-8-sig"))["$defs"]
SIGNED_BY_CONSOLE = {"via": "console", "login": OPERATOR}


def tree_hash(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def refusal(r) -> tuple[int, str]:
    assert r.headers[REFUSAL_HEADER] == r.json()["detail"]["code"]
    return r.status_code, r.json()["detail"]["code"]


def settle(seat, **settings) -> None:
    folder = seat.accounts.config_dir
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "settings.json").write_text(json.dumps(settings), encoding="utf-8")


def fits_run_request(msg) -> bool:
    spec = DEFS["run_request"]
    return (isinstance(msg, dict) and set(msg) == set(spec["properties"]) and isinstance(msg["run"], str)
            and len(msg["run"]) == 64 and set(msg["run"]) <= set("0123456789abcdef"))


# -- a tree of our own: one question, its plan cards, the approvals and runs the tests put there --------


def plan_card(revision=1, status="VALIDATED", **over) -> dict:
    card = {"card": "plan", "schema_version": "0.1", "id": f"plan-{QID}-r{revision}", "qid": QID,
            "revision": revision, "created_at": "2026-10-26T09:00:00Z", "status": status,
            "actions": [{"id": "a1", "device": "optical_tweezers", "action": "on"}]}
    card.update(over)
    return card


def put_plan(root: Path, card: dict, version: int = 1) -> Path:
    name = f"plan_microscope_{QID}.json" if version == 1 else f"v{version}_plan_microscope_{QID}.json"
    p = root / "microscope_agent" / "questions" / QID / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(card), encoding="utf-8")
    return p


def approval_card(plan: dict, name="appr-1", **over) -> dict:
    card = {"card": "plan_approval", "schema_version": "0.1", "id": name, "qid": QID, "revision": 1,
            "created_at": "2026-10-26T10:00:00Z", "status": "APPROVED", "plan_id": plan["id"],
            "plan_revision": plan["revision"], "plan_hash": plan_hash(plan), "approved_by": "kyuhwan",
            "approved_at": "2026-10-26T10:00:00Z"}
    card.update(over)
    return card


def put_approval(root: Path, card: dict, *, bom: bool = False) -> tuple[Path, str]:
    """Returns the file and the sha256 of its raw bytes, which is what a run request names."""
    p = root / "microscope_runtime" / "approvals" / f"{card['id']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = (b"\xef\xbb\xbf" if bom else b"") + json.dumps(card, indent=2).encode()
    p.write_bytes(raw)
    return p, hashlib.sha256(raw).hexdigest()


def put_run(root: Path, run_id="run-20261026-001", *, plan_id=PLAN_ID, ended="completed", events=None,
            approval=None, refusal_text=None, sheet: str | None = None) -> Path:
    d = root / "microscope_runtime" / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    log = {"artifact": "run_log", "run_id": run_id, "plan_id": plan_id, "revision": 1,
           "approval": approval if approval is not None else {"id": None, "kind": None},
           "t0_wall": "2026-10-26T10:05:00.000+00:00", "backend": "hardware",
           "finished_at": "2026-10-26T10:30:00+00:00", "events": events or []}
    if ended is not None:
        log["ended"] = ended
    if refusal_text:
        log["refusal"] = refusal_text
    (d / "log.json").write_text(json.dumps(log), encoding="utf-8")
    if sheet is not None:
        (d / "manual_steps.md").write_text(sheet, encoding="utf-8")
    return d


def trap_apply(t=1.0):
    return {"t_mono": t, "event": "apply", "channel": "optical_tweezers", "action": "on",
            "params": {"commands": [["TRAP_ON", "t1"]]}}


OPEN_SHEET = ("# manual steps for run-20261026-001\n\n## s1 - optical_tweezers\n\n"
              "Switch the trapping laser on at the controller and confirm the bead is held.\n\n"
              "- opened: 2026-10-26T10:05:00Z\n- **not confirmed** - nothing on this lock group proceeded\n")
LOADING_SHEET = ("# manual steps for run-20261026-001\n\n## s1 - sample_loading\n\n"
                 "Check the loading: the sample is on the stage and the cover is closed.\n\n"
                 "- opened: 2026-10-26T10:05:00Z\n- confirmed: 2026-10-26T10:07:30Z by kyuhwan\n"
                 "- observed: sample loaded, no air bubble\n")


@pytest.fixture
def tree(tmp_path):
    root = sma_tree(tmp_path / "sma")
    (root / "microscope_runtime" / "approvals").mkdir(parents=True)
    return root


@pytest.fixture
def client(engine, make_client, tree):
    return lambda **kw: make_client(engine, agent_store=SmaFiles(tree, source="soft-matter-agents"), **kw)


def experiments_routes(c) -> set[tuple[str, str]]:
    """Every (method, path) the server mounts under /api/experiments, as its own description lists them."""
    return {(m.upper(), p) for p, ops in c.app.openapi()["paths"].items() if p.startswith("/api/experiments")
            for m in ops}


def plans_of(c) -> dict[str, dict]:
    r = c.get(PLANS)
    assert r.status_code == 200, r.text
    return {p["plan_id"]: p for p in r.json()["plans"]}


def runs_of(c) -> dict[str, dict]:
    return {r["run_id"]: r for r in c.get(PLANS).json()["runs"]}


# -- every plan on disk, with where it stands -------------------------------------------------------


def test_with_nothing_on_disk_there_is_nothing_listed_and_no_example_flag(client):
    got = client().get(PLANS).json()
    assert got["plans"] == [] and got["runs"] == []
    assert got["example"] is False and got["example_note"] is None
    assert "not saved" in got["drafts_note"] and "still to be designed" in got["drafts_note"]


def test_a_plan_no_one_has_validated_is_a_draft(client, tree):
    put_plan(tree, plan_card(status="PROPOSED"))
    p = plans_of(client())[PLAN_ID]
    assert p["state"] == "draft" and p["approval"] is None and p["run_offer"]["offered"] is False


def test_a_validated_plan_with_no_approval_waits_for_a_signature(client, tree):
    put_plan(tree, plan_card())
    p = plans_of(client())[PLAN_ID]
    assert p["state"] == "waiting_for_signature" and "signature" in p["state_words"].lower()
    assert p["revision"] == 1 and p["qid"] == QID and p["plan_hash"] == plan_hash(plan_card())
    assert "approved" in p["run_offer"]["why_not"].lower()


def test_a_covering_approval_makes_it_approved_and_is_named(client, tree):
    card = plan_card()
    put_plan(tree, card)
    put_approval(tree, approval_card(card))
    p = plans_of(client())[PLAN_ID]
    assert p["state"] == "approved" and p["void_approvals"] == []
    assert p["approval"]["id"] == "appr-1" and p["approval"]["approved_by"] == "kyuhwan"
    assert p["approval"]["signed_words"] == "signed by hand" and p["approval"]["signed_through"] is None


def test_an_approval_signed_through_the_console_says_so_and_who(client, tree):
    card = plan_card()
    put_plan(tree, card)
    put_approval(tree, approval_card(card, signed_through=SIGNED_BY_CONSOLE))
    a = plans_of(client())[PLAN_ID]["approval"]
    assert a["signed_through"] == SIGNED_BY_CONSOLE
    assert "through the console" in a["signed_words"] and OPERATOR in a["signed_words"]
    assert "runtime checks" in a["signed_words"]


def test_the_approvals_own_status_label_decides_nothing(client, tree):
    card = plan_card()
    put_plan(tree, card)
    put_approval(tree, approval_card(card, status="REVOKED"))
    assert plans_of(client())[PLAN_ID]["state"] == "approved"


def test_an_approval_for_a_plan_that_changed_is_listed_as_void_with_the_reason(client, tree):
    card = plan_card()
    put_plan(tree, card)
    put_approval(tree, approval_card(card))
    put_plan(tree, plan_card(actions=[]))  # same id and revision, different content
    p = plans_of(client())[PLAN_ID]
    assert p["state"] == "waiting_for_signature" and p["approval"] is None
    assert [v["name"] for v in p["void_approvals"]] == ["appr-1.json"]
    assert "changed" in p["void_approvals"][0]["why"]


def test_an_approval_with_no_plan_revision_is_void_and_says_which_field(client, tree):
    card = plan_card()
    put_plan(tree, card)
    bad = approval_card(card)
    del bad["plan_revision"]
    put_approval(tree, bad)
    p = plans_of(client())[PLAN_ID]
    assert p["state"] == "waiting_for_signature" and "plan_revision" in p["void_approvals"][0]["why"]


def test_an_approval_for_another_plan_is_not_listed_under_this_one(client, tree):
    card = plan_card()
    put_plan(tree, card)
    other = plan_card(revision=2)
    put_approval(tree, approval_card(other, name="appr-other"))
    p = plans_of(client())[PLAN_ID]
    assert p["state"] == "waiting_for_signature" and p["void_approvals"] == [] and p["approval"] is None


def test_every_version_of_a_question_has_its_plan_listed(client, tree):
    put_plan(tree, plan_card(revision=1), version=1)
    put_plan(tree, plan_card(revision=2), version=2)
    got = plans_of(client())
    assert set(got) == {f"plan-{QID}-r1", f"plan-{QID}-r2"}
    assert (got[f"plan-{QID}-r2"]["version"], got[f"plan-{QID}-r1"]["version"]) == (2, 1)


def test_a_run_that_is_going_makes_its_plan_running(client, tree):
    card = plan_card()
    put_plan(tree, card)
    put_approval(tree, approval_card(card))
    run = FakeSmaRun(tree, run_id="run-20261026-007", plan_id=PLAN_ID)
    try:
        c = client()
        p, r = plans_of(c)[PLAN_ID], runs_of(c)["run-20261026-007"]
        assert p["state"] == "running" and p["run_ids"] == ["run-20261026-007"]
        assert p["run_offer"]["offered"] is False and "running" in p["run_offer"]["why_not"].lower()
        assert r["state"] == "running" and r["how"] is None and r["plan_on_disk"] is True
    finally:
        run.end()


def test_a_run_that_ended_makes_its_plan_ended(client, tree):
    card = plan_card()
    put_plan(tree, card)
    put_approval(tree, approval_card(card))
    put_run(tree)
    p = plans_of(client())[PLAN_ID]
    assert p["state"] == "ended" and p["run_ids"] == ["run-20261026-001"]


def test_a_run_the_runtime_refused_is_not_a_run_that_happened(client, tree):
    """It stays in the plan's run list so the person can read why, and the plan stays approved."""
    card = plan_card()
    put_plan(tree, card)
    put_approval(tree, approval_card(card))
    put_run(tree, ended="refused", refusal_text="no plan_approval on disk names this revision")
    c = client()
    p, r = plans_of(c)[PLAN_ID], runs_of(c)["run-20261026-001"]
    assert p["state"] == "approved" and p["run_ids"] == ["run-20261026-001"]
    assert r["how"] == "refused" and "refus" in r["how_words"] and "no plan_approval" in r["refusal"]


# -- run rows -----------------------------------------------------------------------------------


@pytest.mark.parametrize("how", ["completed", "aborted_by_monitor", "stopped_from_outside", "failed", "refused"])
def test_a_run_row_says_how_it_ended_in_the_words_of_the_contract(client, tree, how):
    put_plan(tree, plan_card())
    put_run(tree, ended=how)
    r = runs_of(client())["run-20261026-001"]
    assert r["state"] == "ended" and r["how"] == how and r["how_words"] == experiments.ENDED_WORDS[how]
    assert r["finished_at"] == "2026-10-26T10:30:00+00:00" and r["started_at"] == "2026-10-26T10:05:00.000+00:00"


def test_a_run_row_counts_its_events(client, tree):
    put_run(tree, events=[{"event": "a"}, {"event": "b"}, {"event": "c"}])
    ev = runs_of(client())["run-20261026-001"]["events"]
    assert ev["count"] == 3 and "3" in ev["words"]


def test_a_run_whose_approval_file_says_it_was_signed_through_the_console_says_so(client, tree):
    put_run(tree, approval={"id": "appr-1", "kind": "plan_approval",
                            "file": {"path": "approvals/appr-1.json", "sha256": "ab" * 32,
                                     "signed_through": SIGNED_BY_CONSOLE}})
    a = runs_of(client())["run-20261026-001"]["approval"]
    assert a["id"] == "appr-1" and a["sha256"] == "ab" * 32 and a["signed_through"] == SIGNED_BY_CONSOLE
    assert "through the console" in a["signed_words"] and OPERATOR in a["signed_words"]


def test_a_run_whose_approval_file_has_no_mark_was_signed_by_hand(client, tree):
    put_run(tree, approval={"id": "appr-1", "kind": "plan_approval",
                            "file": {"path": "approvals/appr-1.json", "sha256": "cd" * 32}})
    assert runs_of(client())["run-20261026-001"]["approval"]["signed_words"] == "signed by hand"


def test_an_older_log_names_only_the_approval_id_and_says_how_signing_is_not_recorded(client, tree):
    put_run(tree, approval={"id": "appr-1", "kind": "plan_approval"})
    a = runs_of(client())["run-20261026-001"]["approval"]
    assert a["id"] == "appr-1" and a["sha256"] is None and a["signed_through"] is None
    assert "not in this run's record" in a["signed_words"]


def test_a_run_with_no_approval_named_has_no_approval_row(client, tree):
    put_run(tree)
    assert runs_of(client())["run-20261026-001"]["approval"] is None


def test_a_run_of_a_plan_that_is_not_on_disk_says_so(client, tree):
    put_run(tree, plan_id="plan-mic-20260101-009-r1")
    r = runs_of(client())["run-20261026-001"]
    assert r["plan_on_disk"] is False and r["plan_id"] == "plan-mic-20260101-009-r1"


def test_an_open_hand_step_sheet_shows_the_waiting_line_and_no_confirm_route(client, tree, engine):
    put_plan(tree, plan_card())
    put_run(tree, ended=None, sheet=OPEN_SHEET)
    r = runs_of(client())["run-20261026-001"]
    assert r["waiting_line"] == "Waiting for a step at the microscope. Confirm it there."
    (s,) = r["hand_steps"]
    assert s["confirmed"] is False and s["channel"] == "optical_tweezers" and "trapping laser" in s["instruction"]
    # the console offers no way to confirm: the only write route under experiments is the run request
    assert {(m, p) for m, p in experiments_routes(client()) if m != "GET"} == {("POST", RUN)}


def test_a_sheet_that_is_confirmed_leaves_no_waiting_line(client, tree):
    put_run(tree, sheet=LOADING_SHEET)
    r = runs_of(client())["run-20261026-001"]
    assert r["waiting_line"] is None and r["hand_steps"][0]["confirmed"] is True
    assert r["hand_steps"][0]["confirmed_by"] == "kyuhwan"


def test_a_run_with_no_sheet_has_no_steps_and_no_waiting_line(client, tree):
    put_run(tree)
    r = runs_of(client())["run-20261026-001"]
    assert r["hand_steps"] == [] and r["waiting_line"] is None


@pytest.mark.parametrize(("how", "note"), [
    ("stopped_from_outside", True), ("aborted_by_monitor", True), ("completed", False),
    ("failed", False), ("refused", False)])
def test_a_stop_on_a_run_that_had_traps_says_the_laser_is_assumed_on(client, tree, how, note):
    put_run(tree, ended=how, events=[trap_apply()])
    got = runs_of(client())["run-20261026-001"]["tweezers_note"]
    assert got == ("tweezers laser: software cannot switch it; assumed on until you confirm" if note else None)


def test_a_stop_on_a_run_with_no_traps_says_nothing_about_the_laser(client, tree):
    put_run(tree, ended="stopped_from_outside", events=[{"event": "apply", "channel": "aura", "params": {"commands": []}}])
    assert runs_of(client())["run-20261026-001"]["tweezers_note"] is None


# -- the Run button: when it is offered, and the one request it would send -----------------------------


@pytest.fixture
def approved(tree):
    card = plan_card()
    put_plan(tree, card)
    _, sha = put_approval(tree, approval_card(card))
    return sha


def offer(c) -> dict:
    return plans_of(c)[PLAN_ID]["run_offer"]


def test_the_person_at_the_microscope_is_offered_run_on_an_approved_plan(client, seat, approved):
    settle(seat, person_login=OPERATOR)
    o = offer(client(login=OPERATOR))
    assert o["offered"] is True and o["why_not"] is None
    assert o["approval_name"] == "appr-1.json" and o["approval_sha256"] == approved
    assert o["built"] is False and "not built yet" in o["message"].lower()


def test_the_approval_hash_is_of_the_files_raw_bytes_bom_and_all(client, seat, tree):
    settle(seat, person_login=OPERATOR)
    card = plan_card()
    put_plan(tree, card)
    path, sha = put_approval(tree, approval_card(card), bom=True)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert offer(client())["approval_sha256"] == sha
    assert sha != hashlib.sha256(path.read_bytes()[3:]).hexdigest()


@pytest.mark.parametrize("login", [OPERATOR2, ADMIN, VIEWER])
def test_anyone_but_the_named_login_is_offered_nothing(client, seat, approved, login):
    settle(seat, person_login=OPERATOR)
    o = offer(client(login=login))
    assert o["offered"] is False and "person" in o["why_not"].lower()


def test_with_no_person_login_named_nobody_is_offered_run(client, seat, approved):
    o = offer(client())
    assert o["offered"] is False and "not named" in o["why_not"]


def test_a_browser_on_another_computer_is_offered_nothing(client, seat, approved):
    settle(seat, person_login=OPERATOR)
    o = offer(client(remote=True))
    assert o["offered"] is False and "microscope computer" in o["why_not"]


def test_an_approved_plan_is_offered_for_every_plan_state_only_when_approved(client, seat, tree):
    settle(seat, person_login=OPERATOR)
    card = plan_card()
    put_plan(tree, card)
    assert offer(client())["offered"] is False  # waiting for a signature
    put_approval(tree, approval_card(card))
    assert offer(client())["offered"] is True
    put_run(tree)
    assert plans_of(client())[PLAN_ID]["state"] == "ended" and offer(client())["offered"] is False


def test_the_request_the_run_route_would_send_fits_the_schema_and_nothing_is_sent_or_written(
        client, seat, approved, tree):
    settle(seat, person_login=OPERATOR)
    before = tree_state(tree)
    r = client().post(RUN, json={"plan_id": PLAN_ID, "plan_revision": 1})
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["outcome"] == "not_built" and "not built yet" in got["message"].lower()
    assert got["would_send"] == {"run": approved} and fits_run_request(got["would_send"])
    assert tree_state(tree) == before


def test_the_run_route_refuses_in_order_login_remote_unnamed_other_missing_unapproved(client, seat, tree):
    card = plan_card()
    put_plan(tree, card)
    body = {"plan_id": PLAN_ID, "plan_revision": 1}
    assert refusal(client(login=None).post(RUN, json=body)) == (401, "login_required")
    settle(seat, person_login=OPERATOR)
    assert refusal(client(remote=True).post(RUN, json=body)) == (403, "remote_view")
    assert refusal(client(login=OPERATOR2).post(RUN, json=body)) == (403, "not_person")
    assert refusal(client().post(RUN, json={"plan_id": "plan-nope-r1", "plan_revision": 1})) == (404, "plan_not_found")
    assert refusal(client().post(RUN, json=body)) == (409, "not_approved")  # waiting for a signature
    settle(seat)
    assert refusal(client().post(RUN, json=body)) == (403, "person_not_named")


def test_the_run_route_takes_only_the_plan_and_its_revision(client, seat, approved):
    settle(seat, person_login=OPERATOR)
    for bad in ({"plan_id": PLAN_ID}, {"plan_id": PLAN_ID, "plan_revision": 1, "sha256": "ab" * 32},
                {"run": "ab" * 32}):
        assert client().post(RUN, json=bad).status_code == 422


def test_the_run_route_refuses_a_revision_that_is_not_the_one_on_disk(client, seat, approved):
    settle(seat, person_login=OPERATOR)
    assert refusal(client().post(RUN, json={"plan_id": PLAN_ID, "plan_revision": 2})) == (404, "plan_not_found")


# -- the example store ----------------------------------------------------------------------------------


@pytest.fixture
def mock_client(engine, make_client, tmp_path):
    return lambda **kw: make_client(engine, agent_store=MockStore(tmp_path / "practice"), **kw)


@pytest.mark.parametrize("path", [PLANS, SAMPLE, MAP])
def test_everything_from_the_mock_store_says_example_data_and_names_where_it_came_from(mock_client, path):
    got = mock_client().get(path).json()
    assert got["example"] is True
    assert EXAMPLE in got["example_note"] and "mock_data/SOURCE.md" in got["example_note"]


@pytest.mark.parametrize("path", [PLANS, SAMPLE, MAP])
def test_a_tree_store_is_not_example_data_even_when_it_is_a_copy_of_the_mock(client, tmp_path, engine, make_client, path):
    root = tmp_path / "copy"
    shutil.copytree(MOCK_DATA, root)
    got = make_client(engine, agent_store=SmaFiles(root, source="soft-matter-agents")).get(path).json()
    assert got["example"] is False and got["example_note"] is None


def test_the_mock_plan_is_approved_and_its_approval_is_named_and_the_other_plans_is_not_void(mock_client):
    plans = plans_of(mock_client())
    p = plans["plan-mic-20260925-002-r2"]
    assert p["state"] == "approved" and p["void_approvals"] == []
    assert p["approval"]["id"] == "appr-mic-20260925-002-r2" and p["approval"]["approved_by"] == "kyuhwan"


def test_the_mock_runs_are_read_from_the_runtime_layout_and_two_were_refused(mock_client):
    runs = runs_of(mock_client())
    assert set(runs) == {"run-20260924-003", "run-20261013-001", "run-20261013-004"}
    assert runs["run-20261013-001"]["how"] == "refused" and runs["run-20261013-001"]["refusal"]
    assert runs["run-20261013-004"]["how"] == "refused"
    assert runs["run-20260924-003"]["plan_on_disk"] is False and runs["run-20260924-003"]["plan_id"] is None


def test_the_refreshed_sample_has_its_runs_only_in_the_runtime_folder():
    assert (MOCK_DATA / "microscope_runtime" / "runs").is_dir()
    assert not (MOCK_DATA / "microscope_agent" / "runs").exists()


def test_the_mock_run_button_is_offered_to_the_person_and_still_sends_nothing(mock_client, seat):
    settle(seat, person_login=OPERATOR)
    c = mock_client()
    o = offer_for(c, "plan-mic-20260925-002-r2")
    assert o["offered"] is True and "example" in o["message"].lower()
    before = tree_hash(MOCK_DATA)
    r = c.post(RUN, json={"plan_id": "plan-mic-20260925-002-r2", "plan_revision": 2})
    assert r.status_code == 200 and r.json()["outcome"] == "not_built"
    assert fits_run_request(r.json()["would_send"])
    assert tree_hash(MOCK_DATA) == before


def offer_for(c, plan_id) -> dict:
    return plans_of(c)[plan_id]["run_offer"]


def test_no_console_action_changes_one_byte_of_the_mock_store(mock_client, seat, tmp_path):
    """A stop, a stop-all, a sign check, a draft and a run request, each from the person's own login."""
    settle(seat, person_login=OPERATOR)
    before = tree_hash(MOCK_DATA)
    c = mock_client()
    calls = [
        c.post(RUN, json={"plan_id": "plan-mic-20260925-002-r2", "plan_revision": 2}),
        c.post("/api/console/runs/stop", content=b""),
        c.post("/api/console/runs/microscope/run-20261013-001/stop", json={"reason": "test"}),
        c.post("/api/instruments/draft", json={"kind": "trap_steps"}),
        c.post("/api/console/sign-check", json={"qid": "mic-20260925-002", "plan_hash": "sha256:" + "0" * 64,
                                                  "password": "x"}),
        c.get(PLANS), c.get(SAMPLE), c.get(MAP),
    ]
    assert all(r.status_code < 500 for r in calls), [r.status_code for r in calls]
    assert tree_hash(MOCK_DATA) == before


def test_there_is_no_route_for_live_on_check_now_or_confirm_under_experiments(client):
    assert experiments_routes(client()) == {("GET", PLANS), ("POST", RUN), ("GET", SAMPLE), ("GET", MAP)}


# -- the sample and its map: "not yet" in words ---------------------------------------------------------


def test_there_is_no_sample_record_and_the_screen_does_not_invent_a_place_for_one(client):
    got = client().get(SAMPLE).json()
    assert got["record"] is None and got["loading_checks"] == []
    assert got["message"] == "No sample record yet: where a sample's record lives is still being designed."


def test_a_loading_check_done_at_the_microscope_is_shown_with_the_run_whose_sheet_holds_it(client, tree):
    put_run(tree, sheet=LOADING_SHEET)
    (c,) = client().get(SAMPLE).json()["loading_checks"]
    assert c["run_id"] == "run-20261026-001" and c["confirmed_by"] == "kyuhwan"
    assert c["confirmed_at"] == "2026-10-26T10:07:30Z"
    assert c["words"] == "done at the microscope, from run-20261026-001's hand-step sheet"


def test_a_step_that_is_not_a_loading_check_is_not_shown_as_one(client, tree):
    put_run(tree, sheet=OPEN_SHEET)
    assert client().get(SAMPLE).json()["loading_checks"] == []


def test_the_sample_map_is_four_parts_each_not_built_with_its_reason_and_draws_nothing(client):
    got = client().get(MAP).json()
    assert got["parts"] == experiments.SAMPLE_MAP_PARTS
    assert all(p["state"] == "not_built" and p["why"] for p in got["parts"])
    assert got["example_map"] is None and got["moves"] == [] and got["flags"] == [] and got["candidates"] == []
    assert "not built yet" in got["message"].lower()


def test_a_runs_events_never_become_candidates_or_moves_on_the_map(client, tree):
    put_run(tree, events=[{"event": "candidate", "x_um": 1, "y_um": 2}, {"event": "stage_move", "x_um": 3}])
    got = client().get(MAP).json()
    assert got["candidates"] == [] and got["moves"] == [] and got["flags"] == []


# -- what is never read ---------------------------------------------------------------------------------


def test_no_experiments_screen_reads_anything_under_the_librarians_folder(client, tree, monkeypatch):
    (tree / "librarian_agent" / "kb").mkdir(parents=True)
    (tree / "librarian_agent" / "kb" / "entry.json").write_text("{}", encoding="utf-8")
    (tree / "microscope_agent" / "envelope").mkdir(parents=True)
    (tree / "microscope_agent" / "envelope" / "snapshot.json").write_text("{}", encoding="utf-8")
    put_plan(tree, plan_card())
    opened: list[str] = []
    real_open = Path.open
    real_read_bytes = Path.read_bytes
    real_read_text = Path.read_text

    def spy_open(self, *a, **kw):
        opened.append(str(self))
        return real_open(self, *a, **kw)

    def spy_bytes(self, *a, **kw):
        opened.append(str(self))
        return real_read_bytes(self, *a, **kw)

    def spy_text(self, *a, **kw):
        opened.append(str(self))
        return real_read_text(self, *a, **kw)

    c = client()
    monkeypatch.setattr(Path, "open", spy_open)
    monkeypatch.setattr(Path, "read_bytes", spy_bytes)
    monkeypatch.setattr(Path, "read_text", spy_text)
    for path in (PLANS, SAMPLE, MAP):
        assert c.get(path).status_code == 200
    assert not [p for p in opened if "librarian_agent" in p or "snapshot.json" in p], opened


def test_the_experiments_code_names_no_librarian_or_snapshot_path():
    src = REPO / "console" / "src" / "sma_console"
    for p in (src / "agents" / "experiments.py", src / "server" / "api" / "experiments.py"):
        text = p.read_text(encoding="utf-8")
        assert "librarian_agent" not in text and "snapshot.json" not in text and "caller_id" not in text, p
