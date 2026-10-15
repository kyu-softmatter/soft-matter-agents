"""records.export: a closed session becomes console.* files under its SMA run id, with the
user's 2026-10-02 answers (chosen or random person ids, free text scanned and kept, the
assistant conversation left local). Only example.test addresses; everything in tmp_path."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dino_autofocus.records import CodeVersion, ExperimentSession, FolderStore, RecordsConfig
from dino_autofocus.records.export import (
    EXPORT_FILE,
    ExportRefused,
    assign_person_ids,
    export_session,
    load_people,
)
from dino_autofocus.records.redact import RUNS_FILE, Pseudonyms, RedactionRefused

ADA = "ada.lovelace@example.test"
RUN = "run-20261002-001"
NOW = lambda: datetime(2026, 10, 2, 21, 0, tzinfo=UTC)  # noqa: E731


def _session(tmp_path: Path, *, close: bool = True, run_id: str | None = RUN,
             bench: bool | None = True):
    store = FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                      data_root=tmp_path / "data", max_tracked_bytes=1000))
    code = CodeVersion("D:/code/dino-autofocus", "abc123", False)
    s = ExperimentSession.open(store, ADA, "20260930_1849_1", user_name="Ada Lovelace",
                               code=code, now=lambda: datetime(2026, 10, 2, 14, 30),
                               backend_kind=None if bench is None else "mm-real", bench=bench)
    s.info.sma_run_id = run_id
    s.manual_step("oil loaded", note="oil looked clean")
    s.record("focus_100x", {"event": "operation_started", "op_id": "op-1",
                            "confirmed_by": ADA})
    if close:
        s.close(note="good focus at the second field")
    return s, _find_session_dir(tmp_path, s.session_id)


def _find_session_dir(tmp_path: Path, sid: str) -> Path:
    return next(p.parent for p in (tmp_path / "records").rglob("session.json")
                if json.loads(p.read_text(encoding="utf-8"))["session_id"] == sid)


@pytest.fixture
def people(tmp_path):
    path = tmp_path / "settings" / "people.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"persons": [
        {"person_id": "ada", "email": ADA, "name": "Ada Lovelace"}]}), encoding="utf-8")
    return Pseudonyms.from_dict(load_people(path))


def test_export_writes_console_files_under_the_run_id(tmp_path, people):
    s, folder = _session(tmp_path)
    out = export_session(folder, people, tmp_path / "staging", now=NOW)
    assert out.folder == tmp_path / "staging" / RUN and out.run_id == RUN
    names = sorted(p.name for p in out.folder.iterdir())
    assert EXPORT_FILE in names and "console.session.json" in names
    assert all(RUNS_FILE.match(n) for n in names)
    text = "".join((out.folder / n).read_text(encoding="utf-8") for n in names)
    assert "example.test" not in text and "Ada Lovelace" not in text
    assert "oil looked clean" in text and "good focus at the second field" in text  # Q2
    summary = json.loads((out.folder / EXPORT_FILE).read_text(encoding="utf-8"))
    assert summary["run_id"] == RUN and summary["exported_at"] == "2026-10-02T21:00:00+00:00"
    for name, digest in summary["files"].items():
        data = (out.folder / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest


def test_the_assistant_conversation_stays_local(tmp_path, people):
    s, folder = _session(tmp_path)
    (folder / "assistant.jsonl").write_text(
        json.dumps({"user_id": ADA, "question": "ask Ada Lovelace"}) + "\n", encoding="utf-8")
    out = export_session(folder, people, tmp_path / "staging")
    assert out.kept_local == ["assistant.jsonl"]
    assert not list(out.folder.glob("*assistant*"))


def test_refusals_write_nothing(tmp_path, people):
    s, folder = _session(tmp_path, close=False)
    with pytest.raises(ExportRefused, match="closed"):
        export_session(folder, people, tmp_path / "staging")
    s2, folder2 = _session(tmp_path / "b", run_id=None)
    with pytest.raises(ExportRefused, match="sma_run_id"):
        export_session(folder2, people, tmp_path / "staging")
    with pytest.raises(ExportRefused, match="folder name"):
        export_session(folder2, people, tmp_path / "staging", run_id="../x")
    with pytest.raises(RedactionRefused):  # nobody mapped
        export_session(folder2, Pseudonyms(()), tmp_path / "staging", run_id=RUN)
    assert not (tmp_path / "staging").exists()


def test_a_mock_session_is_not_exported(tmp_path, people):
    s, folder = _session(tmp_path, bench=False)
    with pytest.raises(ExportRefused, match="real microscope"):
        export_session(folder, people, tmp_path / "staging")


def test_a_session_that_does_not_say_bench_is_not_exported(tmp_path, people):
    """R-03: only an exact True counts; an older session with no flag is refused, not guessed."""
    s, folder = _session(tmp_path, bench=None)
    info = json.loads((folder / "session.json").read_text(encoding="utf-8"))
    assert info["bench"] is None
    with pytest.raises(ExportRefused, match="bench is not True"):
        export_session(folder, people, tmp_path / "staging")
    assert not (tmp_path / "staging").exists()


def test_run_id_has_the_soft_matter_agents_runs_shape(tmp_path, people):
    """R-03: that repository's validator admits runs/[a-z0-9-]+/ only."""
    s, folder = _session(tmp_path, run_id=None)
    for bad in ("Run_1", "run.20261003", "run-20261003-001/x", "RUN-1", "-" * 70):
        with pytest.raises(ExportRefused, match="runs/ folder name"):
            export_session(folder, people, tmp_path / "staging", run_id=bad)
    assert not (tmp_path / "staging").exists()
    out = export_session(folder, people, tmp_path / "staging", run_id="run-20261003-001", now=NOW)
    assert out.run_id == "run-20261003-001"


def test_run_id_rule_agrees_with_the_soft_matter_agents_validator():
    """Read the runs/ path rule from that repository's validator when a checkout is here."""
    import os
    import re

    from dino_autofocus.records.export import RUN_ID

    root = Path(os.environ.get("DINO_AF_SMA_ROOT", r"D:\codes\github\soft-matter-agents"))
    validate = root / "contracts" / "validate.py"
    if not validate.is_file():
        pytest.skip("no soft-matter-agents checkout to compare with")
    text = validate.read_text(encoding="utf-8")
    m = re.search(r"_agent/runs/(\[[^\]]+\]\+)/", text)
    assert m, "the runs/ rule moved in contracts/validate.py; update RUN_ID and this test"
    sma = re.compile(rf"^{m.group(1)}$")
    for name in ("run-20261003-001", "a", "x-y-z", "0123456789abcdef"):
        assert RUN_ID.match(name) and sma.match(name), name
    for name in ("Run-1", "run_1", "run.1", "run 1"):
        assert not RUN_ID.match(name) and not sma.match(name), name


def test_console_files_never_read_as_a_card(tmp_path, people):
    """R-03: no console.* document carries a top-level card or artifact key, which that
    repository's validator would read as a card to validate."""
    s, folder = _session(tmp_path)
    out = export_session(folder, people, tmp_path / "staging", now=NOW)
    for p in out.folder.iterdir():
        docs = ([json.loads(p.read_text(encoding="utf-8"))] if p.suffix == ".json" else
                [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line])
        for d in docs:
            assert not ({"card", "artifact"} & set(d)), p.name
    # and a record that did would stop the export before anything is written
    s2, folder2 = _session(tmp_path, run_id="run-20261003-002")
    rec = folder2 / "records" / "focus_100x.jsonl"
    rec.write_text(rec.read_text(encoding="utf-8") + json.dumps({"card": "plan", "user_id": ADA})
                   + "\n", encoding="utf-8")
    with pytest.raises(ExportRefused, match="card"):
        export_session(folder2, people, tmp_path / "staging2", now=NOW)
    assert not (tmp_path / "staging2").exists()


def test_an_export_never_overwrites(tmp_path, people):
    s, folder = _session(tmp_path)
    export_session(folder, people, tmp_path / "staging")
    with pytest.raises(ExportRefused, match="never overwrites"):
        export_session(folder, people, tmp_path / "staging")


def test_assign_person_ids_keeps_chosen_ids_and_adds_random_ones(tmp_path):
    path = tmp_path / "people.json"
    path.write_text(json.dumps({"persons": [{"person_id": "ada", "email": ADA}]}),
                    encoding="utf-8")
    tokens = iter(["aaaaaa", "aaaaaa", "bbbbbb"])
    m = assign_person_ids(path, [ADA, "BOB@example.test", "carol@example.test"],
                          token=lambda: next(tokens))
    assert m.person_ids == {"ada", "p-aaaaaa", "p-bbbbbb"}  # a taken id is drawn again
    saved = load_people(path)["persons"]
    assert [p["person_id"] for p in saved] == ["ada", "p-aaaaaa", "p-bbbbbb"]
    before = path.read_bytes()
    assign_person_ids(path, [ADA, "bob@example.test"])  # nothing new: file untouched
    assert path.read_bytes() == before


def test_people_file_missing_means_empty(tmp_path):
    assert load_people(tmp_path / "none.json") == {"persons": [], "hosts": {}}
