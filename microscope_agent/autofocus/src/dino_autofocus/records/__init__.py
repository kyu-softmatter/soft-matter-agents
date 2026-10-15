"""Experiment sessions and the local records store (PLAN.md F7, D10, D11).

One experiment session is one folder under ``microscope/sessions/`` of a local git
repository on the microscope PC. Commits name only that folder; nothing is pushed. Sample
state is append-only events folded on read. Standard library only (git via subprocess).
"""

from .codeversion import CodeVersion, code_version
from .committer import AutoCommitter, CommitFailure
from .events import KINDS, SampleEvent, SampleState, fold
from .layout import RecordsConfig
from .librarian_mock import LibrarianRun, MockLibrarian
from .manifest import Manifest, ManifestEntry, sha256_file
from .session import (
    ExperimentSession,
    SessionClosedError,
    SessionInfo,
    open_session,
    open_session_started_at,
    sample_state,
    sessions_of_sample,
)
from .store import Author, CommitResult, FolderStore, GitError, GitFolderStore, RecordsStore

__all__ = [
    "KINDS",
    "Author",
    "AutoCommitter",
    "CodeVersion",
    "CommitFailure",
    "CommitResult",
    "ExperimentSession",
    "FolderStore",
    "GitError",
    "GitFolderStore",
    "LibrarianRun",
    "Manifest",
    "ManifestEntry",
    "MockLibrarian",
    "RecordsConfig",
    "RecordsStore",
    "SampleEvent",
    "SampleState",
    "SessionClosedError",
    "SessionInfo",
    "code_version",
    "fold",
    "open_session",
    "open_session_started_at",
    "sample_state",
    "sessions_of_sample",
    "sha256_file",
]
