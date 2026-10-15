"""Background auto-commit: git work on its own thread so the instrument loop never waits.

``submit`` only puts a request on a queue and returns. The worker thread commits requests
one at a time (git's index lock allows no more). A failed commit is logged and kept in
``failures``; it never raises into the caller, so a measurement goes on when git does not.
The next successful commit of the same folder picks up whatever was left uncommitted.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass

from .layout import now_iso
from .store import Author, CommitResult, RecordsStore

log = logging.getLogger("dino_autofocus.records")


@dataclass
class CommitRequest:
    session_id: str
    message: str
    author: Author
    t: str


@dataclass
class CommitFailure:
    request: CommitRequest
    error: str
    t: str


class AutoCommitter:
    def __init__(self, store: RecordsStore,
                 on_failure: Callable[[CommitFailure], None] | None = None,
                 keep: int = 200):
        self.store = store
        self.on_failure = on_failure
        self.keep = keep
        self.results: list[CommitResult] = []
        self.failures: list[CommitFailure] = []
        self._q: queue.Queue[CommitRequest | None] = queue.Queue()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="records-autocommit",
                                        daemon=True)
        self._thread.start()

    def submit(self, session_id: str, message: str, author: Author) -> None:
        """Queue a commit and return at once. Never raises for a git problem."""
        if not self._thread.is_alive():
            self._fail(CommitRequest(session_id, message, author, now_iso()),
                       "auto-commit worker is not running")
            return
        self._q.put(CommitRequest(session_id, message, author, now_iso()))

    def flush(self, timeout_s: float | None = None) -> bool:
        """Wait until every queued request is done; False on timeout."""
        done = threading.Event()

        def waiter() -> None:
            self._q.join()
            done.set()

        threading.Thread(target=waiter, daemon=True).start()
        return done.wait(timeout_s)

    def stop(self, timeout_s: float | None = 30.0) -> None:
        """Finish what is queued, then end the worker."""
        if self._thread.is_alive():
            self._q.put(None)
            self._thread.join(timeout_s)

    def _fail(self, req: CommitRequest, error: str) -> None:
        f = CommitFailure(req, error, now_iso())
        with self._lock:
            self.failures = (self.failures + [f])[-self.keep:]
        log.warning("records commit failed for %s (%s): %s", req.session_id, req.message, error)
        if self.on_failure is not None:
            try:
                self.on_failure(f)
            except Exception:  # noqa: BLE001 - a broken callback must not stop the worker
                log.exception("records commit failure callback raised")

    def _run(self) -> None:
        while True:
            req = self._q.get()
            try:
                if req is None:
                    return
                try:
                    res = self.store.commit(req.session_id, req.message, req.author)
                except Exception as exc:  # noqa: BLE001 - any git problem is a logged failure
                    self._fail(req, f"{type(exc).__name__}: {exc}")
                else:
                    with self._lock:
                        self.results = (self.results + [res])[-self.keep:]
            finally:
                self._q.task_done()
