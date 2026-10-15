"""Records pseudonymisation before export to a public runs/ folder (docs/records-privacy.md).

Only example.test addresses and made-up names. Every session is built in tmp_path."""

import hashlib
import json
from datetime import datetime

import pytest

from dino_autofocus.records import CodeVersion, ExperimentSession, FolderStore, RecordsConfig
from dino_autofocus.records.redact import (
    RUNS_FILE,
    Person,
    Pseudonyms,
    RedactionRefused,
    flat_name,
    redact,
    redact_record,
    redact_session,
    scan,
)

ADA = "ada.lovelace@example.test"
BOB = "bob@example.test"
PEOPLE = {
    "persons": [
        {"person_id": "p-ada", "email": ADA, "name": "Ada Lovelace", "aliases": ["Countess"]},
        {"person_id": "p-bob", "email": BOB, "name": "Bob Builder"},
    ],
    "hosts": {"LAB-SCOPE-01": "microscope-pc"},
}


@pytest.fixture
def people():
    return Pseudonyms.from_dict(PEOPLE)


def _tree_hash(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


@pytest.fixture
def session(tmp_path):
    store = FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                      data_root=tmp_path / "data", max_tracked_bytes=1000))
    profile = tmp_path / "hardware_profile.json"
    profile.write_text("{}", encoding="utf-8")
    code = CodeVersion(r"C:\Users\Ada Lovelace\code\dino-autofocus", "abc123", False)
    s = ExperimentSession.open(store, ADA, "20260930_1849_1", user_name="Ada Lovelace",
                               hardware_profile=profile, code=code,
                               now=lambda: datetime(2026, 10, 2, 14, 30))
    s.log("live view started", path=r"C:\Users\Ada Lovelace\AppData\Local\dino-autofocus")
    s.sample_event("flag_set", flag_id="f1", name="good area", x_um=1.0, y_um=2.0)
    s.manual_step("oil loaded", note="Countess loaded the oil, BOB BUILDER watched")
    s.record("focus_100x", {"event": "operation_started", "op_id": "op-1",
                            "confirmed_by": ADA, "origin": "assistant"})
    s.record("focus_100x", {"event": "engine_event", "kind": "confirmed",
                            "data": {"key": "climb_past_top", "ok": True, "by": BOB}})
    s.record("focus_100x", {"event": "engine_event", "kind": "approved",
                            "data": {"by": "assistant", "host": "LAB-SCOPE-01"}})
    note = tmp_path / "note.txt"
    note.write_text("free text", encoding="utf-8")
    s.attach(note, kind="note")
    s.close(note=f"done; data copied to /mnt/c/Users/ada/Desktop; next {s.session_id}")
    return s


# -- a whole session ---------------------------------------------------------------------


def test_session_export_has_no_personal_information(session, people):
    root = session.layout.root
    before = _tree_hash(root)
    out = redact_session(root, people)
    assert _tree_hash(root) == before  # the local records are not touched

    assert session.session_id == "20261002-1430-ada-lovelace-1"
    assert out.session_id == session.session_id
    assert out.export_id == "20261002-1430-p-ada-1"
    text = "\n".join(out.files.values())
    for gone in ("@", "Ada Lovelace", "ada-lovelace", "Bob Builder", "BOB BUILDER", "Countess",
                 "Users", "LAB-SCOPE-01"):
        assert gone.lower() not in text.lower(), gone
    assert out.left_out == ["files/note.txt"]  # not JSON: not copied

    info = json.loads(out.files["session.json"])
    assert info["user_id"] == "p-ada"
    assert "user_name" not in info
    assert info["session_id"] == out.export_id
    assert info["code"]["repo"] == r"~\code\dino-autofocus"
    assert info["close_note"] == f"done; data copied to /mnt/c/~/Desktop; next {out.export_id}"

    lines = [json.loads(s) for s in out.files["records/focus_100x.jsonl"].splitlines()]
    assert {ln["user_id"] for ln in lines} == {"p-ada"}
    assert lines[0]["confirmed_by"] == "p-ada"
    assert lines[1]["data"]["by"] == "p-bob"
    assert lines[2]["data"] == {"by": "assistant", "host": "microscope-pc"}
    steps = json.loads(out.files["records/manual_steps.jsonl"])
    assert steps["note"] == "p-ada loaded the oil, p-bob watched"
    event = json.loads(out.files["records/sample_events.jsonl"])
    assert (event["user_id"], event["session_id"]) == ("p-ada", out.export_id)


def test_flat_names_fit_the_runs_folder(session, people):
    flat = redact_session(session.layout.root, people).flat_files()
    assert set(flat) == {"console.session.json", "console.manifest.json",
                         "console.log.session.jsonl", "console.records.focus_100x.jsonl",
                         "console.records.manual_steps.jsonl",
                         "console.records.sample_events.jsonl"}
    assert all(RUNS_FILE.match(n) for n in flat)


def test_an_unmapped_account_refuses_the_whole_session(session):
    only_bob = Pseudonyms((Person("p-bob", BOB, "Bob Builder"),))
    with pytest.raises(RedactionRefused) as e:
        redact_session(session.layout.root, only_bob)
    kinds = {f.kind for f in e.value.findings}
    assert {"email", "unmapped_person", "session_user"} <= kinds
    assert "lovelace" not in str(e.value).lower()  # the refusal names places, not values
    assert "@" not in str(e.value)


def test_a_session_folder_needs_session_json(tmp_path, people):
    with pytest.raises(FileNotFoundError):
        redact_session(tmp_path, people)


# -- single records ----------------------------------------------------------------------


def test_emails_are_mapped_in_any_case_and_inside_text(people):
    out = redact_record({"user_id": "Ada.Lovelace@EXAMPLE.test",
                         "msg": f"asked {BOB} to check"}, people)
    assert out == {"user_id": "p-ada", "msg": "asked p-bob to check"}


@pytest.mark.parametrize("address", ["carol@example.test", "carol\uff20example.test"])
def test_any_other_email_refuses(people, address):
    with pytest.raises(RedactionRefused) as e:
        redact_record({"note": f"ping {address}"}, people)
    assert [f.kind for f in e.value.findings] == ["email"]
    assert "carol" not in str(e.value)


def test_a_person_field_needs_a_person_id_or_an_actor(people):
    assert redact_record({"by": "engine", "user_id": None, "holder": ["p-bob"]}, people)
    with pytest.raises(RedactionRefused) as e:
        redact_record({"events": [{"by": "carol"}]}, people)
    assert [(f.where, f.kind) for f in e.value.findings] == [("events[0].by", "unmapped_person")]


@pytest.mark.parametrize(("raw", "want"), [
    (r"C:\Users\Ada Lovelace\AppData\x.json", r"~\AppData\x.json"),
    ("C:/Users/ada/x.json", "~/x.json"),
    (r"saved to D:\Documents and Settings\bob\f", r"saved to ~\f"),
    ("/home/ada/data", "~/data"),
    ("/Users/ada", "~"),
    ("/mnt/c/Users/ada/x", "/mnt/c/~/x"),
])
def test_home_folders_become_tilde(people, raw, want):
    assert scan(raw, people)[0].kind == "home_path"
    assert redact(raw, people) == want
    assert scan(want, people) == []


def test_names_and_aliases_are_whole_words(people):
    out = redact_record({"note": "ada  lovelace and the countess; Adamant Bobby Builders"},
                        people)
    assert out["note"] == "p-ada and the p-ada; Adamant Bobby Builders"


def test_keys_are_redacted_and_scanned_too():
    p = Pseudonyms((Person("p-ada", ADA),))  # no name mapped: nothing replaces it
    assert redact_record({"Ada Lovelace": 1}, p) == {"Ada Lovelace": 1}
    named = Pseudonyms.from_dict(PEOPLE)
    out = redact_record({"flags": {ADA: {"by": ADA}}}, named)
    assert out == {"flags": {"p-ada": {"by": "p-ada"}}}
    found = scan({"flags": {"x@example.test": 1}}, named)
    assert [(f.where, f.kind) for f in found] == [("flags.<key>", "key:email")]


def test_session_ids_are_renamed_or_refused(people):
    assert redact("20261002-1430-bob-12: open session", people) == \
        "20261002-1430-p-bob-12: open session"
    assert redact("20261002-1430-p-bob-12", people) == "20261002-1430-p-bob-12"
    with pytest.raises(RedactionRefused) as e:
        redact_record({"continues": "20261001-0900-carol-1"}, people)
    assert [f.kind for f in e.value.findings] == ["session_user"]


def test_dropped_keys_and_hosts(people):
    out = redact_record({"user_name": "Ada Lovelace", "login_id": "abc", "host": "OTHER-PC",
                         "msg": "ran on lab-scope-01"}, people)
    assert out == {"msg": "ran on microscope-pc"}


def test_mapping_validation():
    with pytest.raises(ValueError):
        Person("Ada", ADA)  # person ids are lower case
    with pytest.raises(ValueError):
        Person("p-ada", "not an email")
    with pytest.raises(ValueError):
        Pseudonyms((Person("p-ada", ADA), Person("p-ada", BOB)))
    with pytest.raises(ValueError):
        Pseudonyms((Person("p-ada", ADA), Person("p-two", ADA.upper())))
    with pytest.raises(ValueError):
        Pseudonyms((Person("engine", ADA),))
    with pytest.raises(ValueError):
        Pseudonyms((Person("p-ada", ADA),), hosts={"LAB-SCOPE-01": "Lab PC"})


def test_flat_name_refuses_what_runs_does_not_hold():
    assert flat_name("records/scan_4x.jsonl") == "console.records.scan_4x.jsonl"
    with pytest.raises(ValueError):
        flat_name("records/a b.jsonl")
