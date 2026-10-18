"""MockStore: the copied sample in `mock_data/`, plus the questions submitted here.

The sample is a few cards and runs copied from soft-matter-agents (`mock_data/SOURCE.md`),
in the same layout, so it is read with the same `SmaFiles` reader. `submit_question` writes a
draft goal card under `write_dir` (a temporary folder by default) in that layout as well, and
reads it back from there. Nothing is written inside the package, and nothing anywhere else.

A submitted card follows `goal.schema.json` in shape only. It carries
`"origin": "dino-autofocus mock"` and is not validated, so it cannot pass for a seat's card.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .sma_files import SmaFiles, long_path
from .sma_run import RunStream
from .store import (
    QID_PREFIX,
    Agent,
    Approval,
    InboxThread,
    NotFoundError,
    QuestionDetail,
    QuestionSummary,
    RunDetail,
    RunSummary,
    StoreError,
    check_agent,
)

PACKAGE_DIR = Path(__file__).resolve().parent
MOCK_DATA = PACKAGE_DIR / "mock_data"
ORIGIN = "dino-autofocus mock"

# goal.schema.json "purpose"; a missing purpose is the person's to give, so none is guessed
PURPOSES = ("screen", "characterize", "compare", "verify", "troubleshoot", "feed")
FIRST_MOCK_NUMBER = 901  # mock qids run mic-YYYYMMDD-901.. so they do not look like a seat's


class MockStore:
    """AgentStore over the sample in `mock_data/` and the questions submitted to it.

    Without a `write_dir`, the store makes a temporary one on the first submit and owns it:
    `close()` (or leaving a `with MockStore() as store:` block) deletes it. A `write_dir`
    the caller gave is never deleted.
    """

    writable = True

    def __init__(self, write_dir: str | os.PathLike[str] | None = None, *,
                 data_dir: str | os.PathLike[str] | None = None,
                 clock: Callable[[], datetime] | None = None):
        self.sample = SmaFiles(data_dir if data_dir is not None else MOCK_DATA, source="mock")
        self._write_dir = _checked_write_dir(write_dir) if write_dir is not None else None
        self._owns_write_dir = False
        self._clock = clock or (lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"MockStore(write_dir={self._write_dir!r}, data_dir={str(self.sample.root)!r})"

    def __enter__(self) -> MockStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Delete the temporary write folder if this store made it. Safe to call twice;
        a later submit makes a new one."""
        if self._owns_write_dir and self._write_dir is not None:
            shutil.rmtree(long_path(self._write_dir), ignore_errors=True)
            self._write_dir = None
            self._owns_write_dir = False

    @property
    def write_dir(self) -> Path:
        """Where submitted questions go. Made on first use when none was given."""
        if self._write_dir is None:
            self._write_dir = Path(tempfile.mkdtemp(prefix="dino-af-mock-store-"))
            self._owns_write_dir = True
        return self._write_dir

    def _submitted(self) -> SmaFiles | None:
        if self._write_dir is None or not long_path(self._write_dir).is_dir():
            return None
        return SmaFiles(self._write_dir, source="mock-submitted")

    def _stores(self) -> list[SmaFiles]:
        sub = self._submitted()
        return [self.sample] if sub is None else [sub, self.sample]

    # -- reading ---------------------------------------------------------------------------

    def list_questions(self, agent: Agent) -> list[QuestionSummary]:
        out = [q for s in self._stores() for q in s.list_questions(agent)]
        return sorted(out, key=lambda s: s.qid, reverse=True)

    def get_question(self, qid: str, version: int | None = None) -> QuestionDetail:
        for s in self._stores():
            if s.has_question(qid):
                return s.get_question(qid, version)
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

    # -- writing ---------------------------------------------------------------------------

    def submit_question(self, text: str, target: Agent, *, purpose: str | None = None,
                        observable: str | None = None) -> QuestionSummary:
        """Write a DRAFT goal card for `target` and return its summary.

        The text is kept verbatim, as the seats keep a person's question in
        `constraint_notes[0]`. Purpose and observable are recorded only when given.
        """
        target = check_agent(target)
        if not text or not text.strip():
            raise ValueError("a question needs text")
        if purpose is not None and purpose not in PURPOSES:
            raise ValueError(f"purpose must be one of {PURPOSES}, got {purpose!r}")

        now = self._clock().astimezone(UTC)
        questions = long_path(self.write_dir) / f"{target}_agent" / "questions"
        questions.mkdir(parents=True, exist_ok=True)
        qid, qdir = self._new_question_dir(questions, QID_PREFIX[target], now)

        card: dict[str, object] = {
            "card": "goal",
            "schema_version": "0.1",
            "id": f"goal-{qid}-r1",
            "qid": qid,
            "thread": f"solo-{qid}",
            "round": 0,
            "revision": 1,
            "author": "human",
            "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "DRAFT",
            "requested_by": "human",
            "question": text,
        }
        if purpose is not None:
            card["purpose"] = purpose
        if observable:
            card["observable"] = {"name": observable}
        card.update({
            "numbers": [],
            "degraded": [],
            "constraint_notes": [text],
            "origin": ORIGIN,
            "origin_note": "Written by the dino-autofocus mock store from the console. "
                           "Not a seat's card and not validated against goal.schema.json.",
        })
        tmp = qdir / "goal.json.tmp"
        tmp.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(qdir / "goal.json")
        return self.get_question(qid).summary

    def _new_question_dir(self, questions: Path, prefix: str, now: datetime) -> tuple[str, Path]:
        day = now.strftime("%Y%m%d")
        for n in range(FIRST_MOCK_NUMBER, 1000):
            qid = f"{prefix}-{day}-{n:03d}"
            if self.sample.has_question(qid):
                continue
            qdir = questions / qid
            try:
                qdir.mkdir()
            except FileExistsError:
                continue
            return qid, qdir
        raise StoreError(f"no free mock question number left for {prefix}-{day}")


def _checked_write_dir(write_dir: str | os.PathLike[str]) -> Path:
    p = Path(write_dir).resolve()
    if p == PACKAGE_DIR or PACKAGE_DIR in p.parents:
        raise ValueError(f"the mock store does not write inside the package: {p}")
    return p
