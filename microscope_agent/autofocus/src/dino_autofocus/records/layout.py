"""Where experiment-session records live, and small file helpers shared by the package.

PLAN.md v0.9 (D10, D11): the records store is a local git repository on the microscope PC,
never pushed. Each producer writes only its own folder; this app writes
``<records_root>/microscope/sessions/<session_id>/``. Large data stays outside git in
``<data_root>/<session_id>/`` and is listed in the session's ``manifest.json``.

The defaults are the microscope-PC paths. Everything takes a ``RecordsConfig`` so tests and
the desktop use a temporary folder instead.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_RECORDS_ROOT = Path(r"D:\AutoFocus\records")
DEFAULT_DATA_ROOT = Path(r"D:\AutoFocus\data")

#: Files larger than this go to the data folder, not into the session folder (git).
#: One full Kinetix frame (2400 x 2400 uint16) is 11.5 MB.
DEFAULT_MAX_TRACKED_BYTES = 5 * 1024 * 1024

SCHEMA = "dino-autofocus/experiment-session/1"

#: A records root whose folder name ends with this holds simulated sessions only (the server
#: names them so for every backend but mm-real, `server/__main__.py` `record_roots`); the mock
#: librarian uses it to tell a real root, where non-bench sessions are skipped, from a mock one.
MOCK_ROOT_SUFFIX = "-mock"

#: Extra subprocess.run arguments for every git call. The app runs under pythonw (no
#: console); on Windows a console child of a windowless parent would flash a window on the
#: user's desktop at every auto-commit.
NO_WINDOW: dict[str, Any] = (
    {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {})


@dataclass(frozen=True)
class RecordsConfig:
    records_root: Path = DEFAULT_RECORDS_ROOT
    data_root: Path = DEFAULT_DATA_ROOT
    sessions_subdir: str = "microscope/sessions"  # this app's own folder in the store
    max_tracked_bytes: int = DEFAULT_MAX_TRACKED_BYTES

    @property
    def sessions_root(self) -> Path:
        return Path(self.records_root) / self.sessions_subdir

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_root / check_id(session_id)

    def data_dir(self, session_id: str) -> Path:
        return Path(self.data_root) / check_id(session_id)


@dataclass(frozen=True)
class SessionLayout:
    """File names inside one session folder (`root`) and its data folder (`data`)."""

    root: Path
    data: Path

    @property
    def info(self) -> Path:
        return Path(self.root) / "session.json"

    @property
    def log(self) -> Path:
        return Path(self.root) / "log" / "session.jsonl"

    @property
    def records(self) -> Path:
        return Path(self.root) / "records"

    @property
    def sample_events(self) -> Path:
        return self.records / "sample_events.jsonl"

    @property
    def manual_steps(self) -> Path:
        return self.records / "manual_steps.jsonl"

    @property
    def manifest(self) -> Path:
        return Path(self.root) / "manifest.json"

    def operation_record(self, op: str) -> Path:
        return self.records / f"{check_name(op)}.jsonl"


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RESERVED = {"sample_events", "manual_steps"}


def check_id(value: str) -> str:
    """A session id is one path component: letters, digits, '.', '_', '-'."""
    if not isinstance(value, str) or not _ID.match(value) or value in {".", ".."}:
        raise ValueError(f"not a valid id: {value!r}")
    return value


def check_name(op: str) -> str:
    """Operation record names share the id rules and may not shadow the fixed record files."""
    check_id(op)
    if op in _RESERVED:
        raise ValueError(f"{op!r} is reserved for the session's own records")
    return op


def slug(text: str, limit: int = 24) -> str:
    """Folder-safe short form of a user id (an email): the local part, lower case."""
    local = text.strip().lower().split("@", 1)[0]
    s = re.sub(r"[^a-z0-9]+", "-", local).strip("-")
    return (s or "user")[:limit]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


_append_lock = threading.Lock()


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    """One JSON object per line, appended. Never rewrites earlier lines."""
    line = json.dumps(obj, ensure_ascii=False, default=str)
    if "\n" in line:
        raise ValueError("record does not serialise to a single line")
    path.parent.mkdir(parents=True, exist_ok=True)
    with _append_lock, open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()]
