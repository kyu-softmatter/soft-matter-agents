"""Audit log: append only, fields, no secrets, thread safe. App log: daily files, pruning."""

import inspect
import json
import logging
import subprocess
import sys
import threading
from datetime import date

import pytest

from dino_autofocus.auth import AuditFieldError, AuditKind, AuditLog, applog


def test_every_line_has_time_kind_user_and_session(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl", session_id_provider=lambda: "2026-10-01-a-1")
    log.append(AuditKind.COMMAND_PROPOSED, "otto@example.test", command="move_z", origin="ui")
    log.append(AuditKind.LOGIN, None, session_id="explicit")
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    for row in rows:
        assert {"ts", "kind", "user_id", "session_id"} <= row.keys()
    assert rows[0]["session_id"] == "2026-10-01-a-1" and rows[0]["command"] == "move_z"
    assert rows[1]["session_id"] == "explicit" and rows[1]["user_id"] is None


def test_without_a_session_the_field_is_null(tmp_path):
    row = AuditLog(tmp_path / "a.jsonl").append("logout", "otto@example.test")
    assert "session_id" in row and row["session_id"] is None


def test_appends_never_rewrite(tmp_path):
    path = tmp_path / "audit.jsonl"
    AuditLog(path).append("login", "otto@example.test")
    first = path.read_bytes()
    AuditLog(path).append("logout", "otto@example.test")
    assert path.read_bytes().startswith(first)
    public = {n for n, _ in inspect.getmembers(AuditLog, inspect.isfunction)
              if not n.startswith("_")}
    assert public == {"append", "entries"}  # no edit or delete API


@pytest.mark.parametrize("field", ["password", "new_password", "token", "control_token", "ts"])
def test_secrets_and_reserved_names_are_refused(tmp_path, field):
    with pytest.raises(AuditFieldError):
        AuditLog(tmp_path / "a.jsonl").append("login", "otto@example.test", **{field: "x"})


def test_unknown_kind_is_refused(tmp_path):
    with pytest.raises(ValueError):
        AuditLog(tmp_path / "a.jsonl").append("made_up", None)


def test_threads_do_not_interleave_lines(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")

    def worker(i):
        for j in range(25):
            log.append("assistant_message", f"u{i}@example.test", text="x" * 500, n=j)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rows = list(log.entries())
    assert len(rows) == 200 and all(len(r["text"]) == 500 for r in rows)


def test_app_log_writes_one_file_per_day_and_prunes(tmp_path):
    day = [date(2026, 10, 1)]
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "app-2026-08-01.log").write_text("two months")
    (logs / "app-2026-08-31.log").write_text("31 days")
    (logs / "app-2026-09-01.log").write_text("30 days")
    (logs / "notes.txt").write_text("not ours")
    handler = applog.setup(logs, retention_days=30, today=lambda: day[0])
    try:
        assert sorted(p.name for p in logs.iterdir()) == ["app-2026-09-01.log", "notes.txt"]
        logger = logging.getLogger("dino_autofocus.server")
        logger.info("first day")
        day[0] = date(2026, 10, 2)
        logger.warning("second day")
        assert "first day" in (logs / "app-2026-10-01.log").read_text(encoding="utf-8")
        assert "second day" in (logs / "app-2026-10-02.log").read_text(encoding="utf-8")
        day[0] = date(2026, 11, 1)
        logger.info("a month later")
        assert not (logs / "app-2026-10-01.log").exists()
        assert (logs / "app-2026-10-02.log").exists() and (logs / "notes.txt").exists()
    finally:
        logging.getLogger(applog.LOGGER_NAME).removeHandler(handler)
        handler.close()


def test_default_app_log_folder_is_under_the_settings_folder(isolated_config):
    assert applog.log_dir() == isolated_config / "logs"


def test_import_pulls_in_no_heavy_or_ui_packages():
    code = ("import sys, dino_autofocus.auth; "
            "bad = [m for m in ('torch', 'pymmcore', 'pymmcore_plus', 'fastapi', 'starlette', "
            "'PySide6', 'PyQt6', 'anthropic', 'numpy') if m in sys.modules]; print(bad)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def test_kinds_for_commands_and_questions_exist(tmp_path):
    for kind in ("command_proposed", "command_confirmed", "command_executed", "command_rejected",
                 "question_submitted", "assistant_message"):
        assert AuditKind(kind)
    row = AuditLog(tmp_path / "a.jsonl").append(AuditKind.QUESTION_SUBMITTED, "otto@example.test",
                                               area="console", text="Is the 100x lens in?")
    assert row["kind"] == "question_submitted" and row["area"] == "console"
