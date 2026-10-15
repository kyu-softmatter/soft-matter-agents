"""Fake librarian for tests and demos (PLAN.md v0.9, F7.3).

The real librarian agent belongs to soft-matter-agents and is not part of this app. This
stand-in shows the same flow on the local records store:

* it reads ``closed`` sessions under ``microscope/sessions/`` and **never writes there**;
* it writes only ``librarian/``: ``reflected.jsonl`` (which session was taken in, when, from
  which commit) and ``samples/<sample_id>.json`` (the folded sample state);
* with a git store it commits only ``librarian/``. It never merges and never pushes.

A closed session whose folder still has uncommitted changes (its close commit failed) is
skipped until it is committed, because the real librarian reads what is in git.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .events import SampleEvent, fold
from .layout import (
    MOCK_ROOT_SUFFIX,
    append_jsonl,
    now_iso,
    read_json,
    read_jsonl,
    write_json_atomic,
)
from .manifest import Manifest, verify
from .store import Author, FolderStore, GitFolderStore

LIBRARIAN = Author("mock-librarian", "mock-librarian@example.test")


@dataclass
class LibrarianRun:
    reflected: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)   # session id -> reason
    samples: list[str] = field(default_factory=list)
    commit: str | None = None


class MockLibrarian:
    """`bench_only` (T-106c): skip closed sessions whose ``session.json`` says
    ``bench: false`` (a mock or simulated backend), the rule the soft-matter-agents librarian
    applies to the real records root. None: decided by the root's name, a ``*-mock`` root
    (``layout.MOCK_ROOT_SUFFIX``, the server's naming for every backend but mm-real) keeps
    reflecting its simulated sessions; any other root is treated as the real one."""

    def __init__(self, store: FolderStore, author: Author = LIBRARIAN, *,
                 bench_only: bool | None = None):
        self.store = store
        self.author = author
        self.dir = Path(store.config.records_root) / "librarian"
        root_name = Path(store.config.records_root).name
        self.bench_only = (not root_name.endswith(MOCK_ROOT_SUFFIX) if bench_only is None
                           else bool(bench_only))

    @property
    def ledger(self) -> Path:
        return self.dir / "reflected.jsonl"

    def reflected_ids(self) -> set[str]:
        return {d["session_id"] for d in read_jsonl(self.ledger)}

    def run_once(self) -> LibrarianRun:
        run = LibrarianRun()
        done = self.reflected_ids()
        touched: set[str] = set()
        for info in self.store.list_sessions():
            sid = info["session_id"]
            if info.get("status") != "closed" or sid in done:
                continue
            if self.bench_only and info.get("bench") is False:
                run.skipped[sid] = "not recorded on the bench (session.json bench: false)"
                continue
            sdir = self.store.config.session_dir(sid)
            source = None
            if isinstance(self.store, GitFolderStore):
                rel = sdir.relative_to(self.store.root).as_posix()
                if self.store.uncommitted(rel):
                    run.skipped[sid] = "closed but not fully committed"
                    continue
                hist = self.store.log_paths(rel)
                source = hist[0] if hist else None
            m = Manifest(sdir / "manifest.json")
            files_ok = all(verify(e, sdir, self.store.config.data_root) for e in m.entries)
            n_events = len(read_jsonl(sdir / "records" / "sample_events.jsonl"))
            append_jsonl(self.ledger, {
                "session_id": sid, "sample_id": info["sample_id"], "user_id": info["user_id"],
                "closed_at": info.get("closed_at"), "reflected_at": now_iso(),
                "source_commit": source, "n_sample_events": n_events,
                "n_files": len(m.entries), "files_ok": files_ok})
            run.reflected.append(sid)
            touched.add(info["sample_id"])
        for sample_id in sorted(touched):
            write_json_atomic(self.dir / "samples" / f"{sample_id}.json",
                              self.sample_summary(sample_id))
            run.samples.append(sample_id)
        if run.reflected:
            res = self.store.commit_path("librarian", f"librarian: reflect {len(run.reflected)} "
                                         f"session(s)", self.author, label="librarian")
            run.commit = res.commit
        return run

    def sample_summary(self, sample_id: str) -> dict[str, Any]:
        """Sample state from the reflected (closed) sessions only."""
        ids = {d["session_id"] for d in read_jsonl(self.ledger) if d["sample_id"] == sample_id}
        events: list[SampleEvent] = []
        for sid in sorted(ids):
            path = self.store.config.session_dir(sid) / "records" / "sample_events.jsonl"
            events += [SampleEvent.from_dict(d) for d in read_jsonl(path)]
        return {"sample_id": sample_id, "from_sessions": sorted(ids), "written_at": now_iso(),
                "state": fold(events, sample_id).as_dict()}

    def read_sample(self, sample_id: str) -> dict[str, Any]:
        return read_json(self.dir / "samples" / f"{sample_id}.json")
