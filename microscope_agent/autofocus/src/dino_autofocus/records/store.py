"""Records stores: where session folders live and how they are committed.

``RecordsStore`` is the interface the session code uses. Two implementations:

* ``FolderStore`` -- folders only, no git. For tests and machines without a records repo.
* ``GitFolderStore`` -- the D11 layout: one local git repository, one branch (``main``), and
  each commit names only this session's folder as its pathspec, so it can never pick up
  another producer's files (``simulation/``, ``librarian/``). Authors come from the logged-in
  user via ``git -c user.name -c user.email``; the global git config is never touched.
  There is no push anywhere in this package (D10): the repository has no remote of ours.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .layout import NO_WINDOW, RecordsConfig, check_id, read_json, slug


@dataclass(frozen=True)
class Author:
    name: str
    email: str

    @classmethod
    def from_user(cls, user_id: str, name: str = "") -> Author:
        """Account ids are emails (PLAN D9); anything else gets a local placeholder address."""
        email = user_id if "@" in user_id else f"{slug(user_id)}@localhost"
        return cls(name=name or user_id, email=email)


@dataclass
class CommitResult:
    session_id: str
    committed: bool
    commit: str | None = None
    reason: str = ""      # why nothing was committed, or the git error


class RecordsStore(Protocol):
    config: RecordsConfig

    def open_session(self, session_id: str) -> Path:
        """Create the session's folder (fails if it exists) and return it."""
        ...

    def commit(self, session_id: str, message: str, author: Author) -> CommitResult: ...

    def close_session(self, session_id: str) -> None:
        """Called after session.json says closed; a store may seal the folder."""
        ...

    def list_sessions(self) -> list[dict]:
        """``session.json`` of every session folder, oldest first."""
        ...


class FolderStore:
    """Session folders on disk, no version control: ``commit`` records nothing."""

    def __init__(self, config: RecordsConfig):
        self.config = config

    def open_session(self, session_id: str) -> Path:
        d = self.config.session_dir(session_id)
        d.parent.mkdir(parents=True, exist_ok=True)
        d.mkdir()  # FileExistsError if taken: ids are never reused
        return d

    def commit(self, session_id: str, message: str, author: Author) -> CommitResult:
        check_id(session_id)
        return CommitResult(session_id, committed=False, reason="folder store: no git")

    def close_session(self, session_id: str) -> None:
        check_id(session_id)

    def commit_path(self, rel: str, message: str, author: Author, label: str = ""
                    ) -> CommitResult:
        return CommitResult(label or rel, committed=False, reason="folder store: no git")

    def list_sessions(self) -> list[dict]:
        root = self.config.sessions_root
        if not root.is_dir():
            return []
        infos = [read_json(p) for p in root.glob("*/session.json")]
        return sorted(infos, key=lambda i: (i.get("started_at", ""), i["session_id"]))


class GitError(RuntimeError):
    pass


class GitFolderStore(FolderStore):
    """One local repository, one branch, commits limited to the session's own folder."""

    def __init__(self, config: RecordsConfig, init: bool = True, git: str = "git",
                 timeout_s: float = 60.0):
        super().__init__(config)
        self.git_exe = git
        self.timeout_s = timeout_s
        self.root = Path(config.records_root)
        if init:
            self.ensure_repo()

    # -- git plumbing
    def _git(self, *args: str, author: Author | None = None, check: bool = True
             ) -> subprocess.CompletedProcess:
        cmd = [self.git_exe, "-C", str(self.root)]
        if author is not None:
            cmd += ["-c", f"user.name={author.name}", "-c", f"user.email={author.email}"]
        cmd += list(args)
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_s,
                             encoding="utf-8", errors="replace", **NO_WINDOW)
        if check and out.returncode != 0:
            raise GitError(f"git {' '.join(args)}: {(out.stderr or out.stdout).strip()}")
        return out

    def is_repo(self) -> bool:
        if not (self.root / ".git").exists():
            return False
        return self._git("rev-parse", "--is-inside-work-tree", check=False).returncode == 0

    def ensure_repo(self) -> None:
        """Create the records repository on first use (branch ``main``, no remote)."""
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.is_repo():
            self._git("init", "--quiet", "--initial-branch=main")

    def _rel(self, session_id: str) -> str:
        d = self.config.session_dir(session_id)
        return d.relative_to(self.root).as_posix()

    def head(self) -> str | None:
        out = self._git("rev-parse", "--verify", "--quiet", "HEAD", check=False)
        return out.stdout.strip() or None

    # -- RecordsStore
    def commit(self, session_id: str, message: str, author: Author) -> CommitResult:
        """Stage and commit only ``microscope/sessions/<session_id>/``. Raises GitError."""
        return self.commit_path(self._rel(session_id), message, author, label=session_id)

    def commit_path(self, rel: str, message: str, author: Author, label: str = ""
                    ) -> CommitResult:
        """Commit everything under `rel` (repo-relative folder) and nothing else."""
        if not (self.root / rel).is_dir():
            raise GitError(f"no folder {rel}")
        self._git("add", "--all", "--", rel)
        staged = self._git("diff", "--cached", "--quiet", "--", rel, check=False)
        if staged.returncode == 0:
            return CommitResult(label or rel, committed=False, reason="nothing to commit")
        self._git("commit", "--quiet", "-m", message, "--", rel, author=author)
        return CommitResult(label or rel, committed=True, commit=self.head())

    def uncommitted(self, path: str) -> bool:
        """True if anything under `path` (relative to the repo) differs from HEAD."""
        return bool(self._git("status", "--porcelain", "--", path).stdout.strip())

    def log_paths(self, path: str) -> list[str]:
        """Commit hashes touching `path`, newest first: the per-session history."""
        out = self._git("log", "--format=%H", "--", path, check=False)
        return out.stdout.split()
