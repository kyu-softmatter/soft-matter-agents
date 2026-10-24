"""MockStore: the copied sample in `mock_data/`, plus the question requests written here.

The sample is a few cards and runs copied from soft-matter-agents (`mock_data/SOURCE.md`),
in the same layout, so it is read with the same `SmaFiles` reader. A question request is written
under `write_dir` (a temporary folder by default) as `console/requests/questions/<id>.json`, the
practice copy of the console's own folder. Nothing is written inside the package, and nothing
anywhere else; no goal card is ever made (console card 010).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .requests import FOLDER_PARTS as REQUEST_PARTS
from .requests import quantity_names
from .sma_files import RootNotFoundError, SmaFiles, long_path, repository_root
from .sma_run import RunStream
from .store import (
    Agent,
    Approval,
    InboxThread,
    NotFoundError,
    QuestionDetail,
    QuestionSummary,
    RunDetail,
    RunSummary,
)

PACKAGE_DIR = Path(__file__).resolve().parent
MOCK_DATA = PACKAGE_DIR / "mock_data"


class MockStore:
    """AgentStore over the sample in `mock_data/`, with question requests written to its own folder.

    Without a `write_dir`, the store makes a temporary one on the first write and owns it:
    `close()` (or leaving a `with MockStore() as store:` block) deletes it. A `write_dir`
    the caller gave is never deleted.
    """

    writable = True

    def __init__(self, write_dir: str | os.PathLike[str] | None = None, *,
                 data_dir: str | os.PathLike[str] | None = None):
        self.sample = SmaFiles(data_dir if data_dir is not None else MOCK_DATA, source="mock")
        self._write_dir = _checked_write_dir(write_dir) if write_dir is not None else None
        self._owns_write_dir = False

    def __repr__(self) -> str:
        return f"MockStore(write_dir={self._write_dir!r}, data_dir={str(self.sample.root)!r})"

    def __enter__(self) -> MockStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Delete the temporary write folder if this store made it. Safe to call twice;
        a later write makes a new one."""
        if self._owns_write_dir and self._write_dir is not None:
            shutil.rmtree(long_path(self._write_dir), ignore_errors=True)
            self._write_dir = None
            self._owns_write_dir = False

    @property
    def write_dir(self) -> Path:
        """Where question requests go. Made on first use when none was given."""
        if self._write_dir is None:
            self._write_dir = Path(tempfile.mkdtemp(prefix="dino-af-mock-store-"))
            self._owns_write_dir = True
        return self._write_dir

    # -- reading ---------------------------------------------------------------------------

    def list_questions(self, agent: Agent) -> list[QuestionSummary]:
        return self.sample.list_questions(agent)

    def get_question(self, qid: str, version: int | None = None) -> QuestionDetail:
        if self.sample.has_question(qid):
            return self.sample.get_question(qid, version)
        raise NotFoundError(f"no question {qid} in the mock store")

    def list_runs(self, agent: Agent) -> list[RunSummary]:
        return self.sample.list_runs(agent)

    def get_run(self, agent: Agent, run_id: str) -> RunDetail:
        return self.sample.get_run(agent, run_id)

    def run_stream(self, agent: Agent, run_id: str) -> RunStream:
        return self.sample.run_stream(agent, run_id)

    def list_inbox(self) -> list[InboxThread]:
        return self.sample.list_inbox()

    def list_approvals(self, agent: Agent) -> list[Approval]:
        return self.sample.list_approvals(agent)

    # -- question requests (console card 010) -----------------------------------------------------
    #
    # A request goes into the store's own write folder, in the layout soft-matter-agents' console
    # folder has, so this is the practice copy of `<root>/console/requests/questions/`. The shipped
    # sample is never written, and neither is the real tree.

    def request_write_folder(self) -> Path:
        return long_path(self.write_dir).joinpath(*REQUEST_PARTS)

    def request_folders(self) -> list[Path]:
        mine = [] if self._write_dir is None else [long_path(self._write_dir).joinpath(*REQUEST_PARTS)]
        return [*mine, self.sample.root.joinpath(*REQUEST_PARTS)]

    def approvals_target_present(self) -> bool:
        return True  # practice: there is nothing to look for, and nothing is written

    def registered_names(self) -> list[str]:
        try:
            return quantity_names(repository_root())
        except RootNotFoundError:
            return []


def _checked_write_dir(write_dir: str | os.PathLike[str]) -> Path:
    p = Path(write_dir).resolve()
    if p == PACKAGE_DIR or PACKAGE_DIR in p.parents:
        raise ValueError(f"the mock store does not write inside the package: {p}")
    return p
