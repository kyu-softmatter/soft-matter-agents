"""One run at a time on this computer, across processes (card 062).

A live view and a plan run would be two Micro-Manager cores on one
instrument, which never happens (plan.md 11-25 item 3). So every run --
operator.run and a live view alike -- holds this lock for its whole length,
and a run that cannot take it is refused, never queued.

THE MECHANISM IS AN OPERATING-SYSTEM FILE LOCK, and the reason is how it
fails. The lock is a byte-range lock on Windows (msvcrt.locking) and flock
elsewhere, on a file outside this tree. The operating system releases it
when the process holding it ends, however it ends. A lock made of a file's
mere existence, or of a pid written into it, outlives a crash and refuses
every later run until a person deletes it; this one cannot go stale. Both
kinds are per open handle, so a second RunLock in the same process is
refused as well, which is what the tests rely on.

Who holds it is written beside it, in `<lock>.holder.json`, for the refusal
message only. That file is advisory: the OS lock decides, and a holder file
left by a crash names a run that no longer holds anything.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


class RunLockHeld(RuntimeError):
    """Another run holds the lock. `.holder` is what it wrote about itself, if readable."""

    def __init__(self, holder: dict | None):
        self.holder = holder
        super().__init__("another run holds the run lock"
                         + (f": {json.dumps(holder, sort_keys=True)}" if holder else ""))


def default_path() -> Path:
    """%LOCALAPPDATA%\\soft-matter-agents\\run.lock, or ~/.soft-matter-agents/run.lock."""
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "soft-matter-agents" if base else Path.home() / ".soft-matter-agents"
    return root / "run.lock"


class RunLock:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_path()
        self._fh = None

    @property
    def holder_path(self) -> Path:
        return self.path.with_name(self.path.name + ".holder.json")

    @property
    def held(self) -> bool:
        return self._fh is not None

    def acquire(self, holder: dict) -> None:
        """Take the lock or raise RunLockHeld at once. Never waits."""
        if self._fh is not None:
            raise RuntimeError("this RunLock is already held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")
        try:
            if sys.platform == "win32":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            raise RunLockHeld(self.read_holder()) from None
        self._fh = fh
        info = {**holder, "pid": os.getpid()}
        tmp = self.holder_path.with_name(self.holder_path.name + ".tmp")
        tmp.write_text(json.dumps(info, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.holder_path)

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            self.holder_path.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            if sys.platform == "win32":
                import msvcrt
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None

    def read_holder(self) -> dict | None:
        try:
            return json.loads(self.holder_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
