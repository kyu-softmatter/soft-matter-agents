"""Experiment sessions: one measurement run, one folder, open -> closed.

An *experiment session* is one run at the microscope (PLAN.md F7), not a Claude session.

    store = GitFolderStore(RecordsConfig(records_root=..., data_root=...))
    committer = AutoCommitter(store)
    s = ExperimentSession.open(store, user_id="op@example.test", sample_id="20260930_1849_1",
                               committer=committer)
    s.log("live view started")
    s.sample_event("flag_set", flag_id="f1", name="good area", x_um=8026.0, y_um=571.6)
    s.record("scan_4x", {"tile": "r0c0", "z_focus_um": 3048.9})
    s.end_operation("scan_4x", {"tiles": 4})          # queues an auto-commit
    s.close()                                          # read-only from here on

Folder (``RecordsConfig.session_dir``)::

    session.json              user, sample, status, start/close, code version, hardware hash
    log/session.jsonl         the session log
    records/<op>.jsonl        per-operation records (engine record format: T-002)
    records/manual_steps.jsonl
    records/sample_events.jsonl
    files/                    attached files up to the size limit
    manifest.json             every attached file: where, size, sha256

Every line written carries the session id and the user id (PLAN.md design rule 12). Writes
are refused once the session is closed. A commit that fails is logged; the session goes on.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .codeversion import CodeVersion, code_version
from .events import SampleEvent, SampleState, fold, make_event
from .layout import (
    SCHEMA,
    SessionLayout,
    append_jsonl,
    check_id,
    now_iso,
    read_json,
    read_jsonl,
    slug,
    write_json_atomic,
)
from .manifest import Manifest, ManifestEntry, place_file, sha256_file
from .store import Author, RecordsStore

log = logging.getLogger("dino_autofocus.records")

Status = Literal["open", "closed"]


class SessionClosedError(RuntimeError):
    """A write to a closed (read-only) experiment session."""


@dataclass
class SessionInfo:
    """Contents of ``session.json``."""

    session_id: str
    user_id: str                       # account id = email (T-018); a plain string here
    sample_id: str
    started_at: str
    status: Status = "open"
    closed_at: str | None = None
    user_name: str = ""
    code: dict[str, Any] = field(default_factory=dict)        # CodeVersion
    hardware_profile: dict[str, Any] | None = None             # {path, sha256}
    continues: str | None = None       # previous session of the same sample (F7.4)
    sma_run_id: str | None = None      # soft-matter-agents runs/<run_id>/, set at integration
    #: T-106b: the engine backend this session ran on (`BackendInfo.kind`) and whether it was
    #: the real stand (`engine.backend.is_bench`). None: not recorded (older sessions, or an
    #: engine with no backend info); only an exact True counts as the bench downstream.
    backend_kind: str | None = None
    bench: bool | None = None
    close_note: str = ""
    schema: str = SCHEMA

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SessionInfo:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


def new_session_id(sessions_root: Path, user_id: str, now: datetime | None = None) -> str:
    """``<YYYYMMDD-HHMM>-<user>-<n>``, the first n that is not taken yet."""
    stem = f"{(now or datetime.now()):%Y%m%d-%H%M}-{slug(user_id)}"
    n = 1
    while (Path(sessions_root) / f"{stem}-{n}").exists():
        n += 1
    return f"{stem}-{n}"


class ExperimentSession:
    def __init__(self, store: RecordsStore, info: SessionInfo,
                 committer: Any | None = None):
        self.store = store
        self.info = info
        self.committer = committer   # AutoCommitter, or None: commit in the caller's thread
        cfg = store.config
        self.layout = SessionLayout(cfg.session_dir(info.session_id),
                                    cfg.data_dir(info.session_id))
        self.author = Author.from_user(info.user_id, info.user_name)
        self._seq = len(read_jsonl(self.layout.sample_events))
        self._lock = threading.Lock()

    # -- lifecycle
    @classmethod
    def open(cls, store: RecordsStore, user_id: str, sample_id: str, *, user_name: str = "",
             hardware_profile: str | Path | None = None, continues: str | None = None,
             code_repo: str | Path | None = None, code: CodeVersion | None = None,
             committer: Any | None = None,
             now: Callable[[], datetime] | None = None,
             backend_kind: str | None = None, bench: bool | None = None) -> ExperimentSession:
        """Create the folder and ``session.json`` and make the first commit. `backend_kind`
        and `bench` say what the session ran on (T-106b); the export and the librarian read
        them, and a missing or non-True `bench` never counts as the real stand."""
        if not user_id:
            raise ValueError("an experiment session needs a logged-in user")
        check_id(sample_id)
        cfg = store.config
        while True:
            sid = new_session_id(cfg.sessions_root, user_id, now() if now else None)
            try:
                store.open_session(sid)
                break
            except FileExistsError:  # another session took the id in between
                continue
        hw = None
        if hardware_profile is not None:
            p = Path(hardware_profile)
            hw = {"path": str(p), "sha256": sha256_file(p)}
        # `code`: read once at server start-up instead of two git calls per open (G4)
        cv = code if code is not None else code_version(
            Path(code_repo) if code_repo is not None else None)
        info = SessionInfo(session_id=sid, user_id=user_id, sample_id=sample_id,
                           started_at=now_iso(), user_name=user_name, code=asdict(cv),
                           hardware_profile=hw, continues=continues,
                           backend_kind=backend_kind,
                           bench=None if bench is None else bool(bench))
        s = cls(store, info, committer)
        s.layout.records.mkdir(parents=True, exist_ok=True)
        s.layout.log.parent.mkdir(parents=True, exist_ok=True)
        s._write_info()
        Manifest(s.layout.manifest).save()
        s.log("session opened", sample_id=sample_id, continues=continues,
              code_commit=cv.commit, code_dirty=cv.dirty, backend_kind=backend_kind,
              bench=info.bench)
        s._commit("open session")
        return s

    @classmethod
    def load(cls, store: RecordsStore, session_id: str,
             committer: Any | None = None) -> ExperimentSession:
        """Open an earlier session to read it (closed) or carry on with it (still open)."""
        info = SessionInfo.from_dict(read_json(store.config.session_dir(session_id)
                                               / "session.json"))
        return cls(store, info, committer)

    @classmethod
    def continue_from(cls, store: RecordsStore, previous_id: str, user_id: str,
                      **kw: Any) -> ExperimentSession:
        """New session on the same sample as `previous_id` (F7.4)."""
        prev = cls.load(store, previous_id)
        return cls.open(store, user_id, prev.info.sample_id, continues=previous_id, **kw)

    def close(self, note: str = "") -> None:
        """Mark closed and commit. Afterwards every write raises ``SessionClosedError``."""
        with self._lock:
            self._check_writable()
            self._log_line("session closed", "info", {"note": note})
            self.info.status = "closed"
            self.info.closed_at = now_iso()
            self.info.close_note = note
            self._write_info()
        self.store.close_session(self.info.session_id)
        self._commit("close session")

    @property
    def writable(self) -> bool:
        return self.info.status == "open"

    @property
    def session_id(self) -> str:
        return self.info.session_id

    # -- writes
    def log(self, msg: str, level: str = "info", **fields: Any) -> None:
        with self._lock:
            self._check_writable()
            self._log_line(msg, level, fields)

    def record(self, op: str, obj: dict[str, Any]) -> None:
        """Append one line to ``records/<op>.jsonl``."""
        with self._lock:
            self._check_writable()
            append_jsonl(self.layout.operation_record(op), self._stamp(obj))

    def end_operation(self, op: str, summary: dict[str, Any] | None = None) -> None:
        """Close an operation's record and queue an auto-commit."""
        self.record(op, {"event": "operation_finished", "summary": summary or {}})
        self.log(f"{op} finished")
        self._commit(f"{op} finished")

    def manual_step(self, name: str, **fields: Any) -> None:
        """A step a person did (oil loaded, sample moved by hand, ...)."""
        with self._lock:
            self._check_writable()
            append_jsonl(self.layout.manual_steps, self._stamp({"step": name, **fields}))

    def sample_event(self, kind: str, **payload: Any) -> SampleEvent:
        with self._lock:
            self._check_writable()
            e = make_event(kind, self.info.sample_id, self.session_id, self.info.user_id,
                           self._seq, **payload)
            append_jsonl(self.layout.sample_events, e.as_dict())
            self._seq += 1
            return e

    def attach(self, src: str | Path, name: str | None = None, kind: str = "",
               move: bool = False) -> ManifestEntry:
        """Copy (or move) a file in: small ones into ``files/``, large ones to the data
        folder outside git. Either way the manifest gets its size and sha256."""
        with self._lock:
            self._check_writable()
            name = check_id(name or Path(src).name)
            m = Manifest(self.layout.manifest)
            if name in m.names():
                raise FileExistsError(f"{name} already attached")
            cfg = self.store.config
            e = place_file(Path(src), name, self.layout.root, cfg.data_root, self.session_id,
                           cfg.max_tracked_bytes, move=move, kind=kind)
            m.entries.append(e)
            m.save()
            self._log_line("file attached", "info", {"name": name, "where": e.where,
                                                     "size": e.size, "sha256": e.sha256})
            return e

    # -- reads
    def events(self) -> list[SampleEvent]:
        return [SampleEvent.from_dict(d) for d in read_jsonl(self.layout.sample_events)]

    def log_lines(self) -> list[dict[str, Any]]:
        return read_jsonl(self.layout.log)

    def record_files(self) -> list[dict[str, Any]]:
        """Every ``records/*.jsonl`` with its line count, by name (for the session detail view)."""
        out = []
        for p in sorted(self.layout.records.glob("*.jsonl")):
            with open(p, encoding="utf-8") as f:
                out.append({"name": p.name, "lines": sum(1 for line in f if line.strip())})
        return out

    def manifest(self) -> Manifest:
        return Manifest(self.layout.manifest)

    # -- internals
    def _check_writable(self) -> None:
        if not self.writable:
            raise SessionClosedError(f"session {self.session_id} is closed (read-only)")

    def _stamp(self, obj: dict[str, Any]) -> dict[str, Any]:
        return {"t": now_iso(), "session_id": self.session_id, "user_id": self.info.user_id,
                **obj}

    def _log_line(self, msg: str, level: str, fields: dict[str, Any]) -> None:
        append_jsonl(self.layout.log, self._stamp({"level": level, "msg": msg, **fields}))

    def _write_info(self) -> None:
        write_json_atomic(self.layout.info, asdict(self.info))

    def _commit(self, message: str) -> None:
        msg = f"{self.session_id}: {message}"
        if self.committer is not None:
            self.committer.submit(self.session_id, msg, self.author)
            return
        try:
            self.store.commit(self.session_id, msg, self.author)
        except Exception as exc:  # noqa: BLE001 - recording must not stop the measurement
            log.warning("records commit failed for %s: %s", self.session_id, exc)
            if self.writable:
                with self._lock:
                    self._log_line("commit failed", "warning", {"message": message,
                                                                "error": str(exc)})


def sessions_of_sample(store: RecordsStore, sample_id: str) -> list[dict[str, Any]]:
    return [i for i in store.list_sessions() if i.get("sample_id") == sample_id]


def sample_state(store: RecordsStore, sample_id: str) -> SampleState:
    """Fold the sample's events from every session that touched it, open or closed."""
    events: list[SampleEvent] = []
    for info in sessions_of_sample(store, sample_id):
        path = store.config.session_dir(info["session_id"]) / "records" / "sample_events.jsonl"
        events += [SampleEvent.from_dict(d) for d in read_jsonl(path)]
    return fold(events, sample_id)


def open_session(store: RecordsStore) -> dict[str, Any] | None:
    """``session.json`` of the open experiment session, or None when none is open.

    One operator drives the instrument at a time, so normally at most one is open. If an
    earlier run crashed and left another open, the most recently started one counts.
    """
    infos = [i for i in store.list_sessions() if i.get("status") == "open"]
    if not infos:
        return None
    return max(infos, key=lambda i: datetime.fromisoformat(i["started_at"]))


def open_session_started_at(store: RecordsStore) -> datetime | None:
    """Start time of the open experiment session (None when none is open).

    The engine compares a hole fit's time with this for the re-trace-every-session rule
    (docs/runs/2026-09-30_substrate-scan.md: the hole moved 1.5 mm between fits).
    """
    info = open_session(store)
    return None if info is None else datetime.fromisoformat(info["started_at"])
