"""Data layer of the agent console (F1): questions, runs and inbox of the two seats.

`MockStore` is the default: a copied sample plus the questions submitted to it.
`SmaFiles` reads the soft-matter-agents files and never writes them (PLAN.md 6.9).
No UI, torch or hardware import happens here.
"""

from __future__ import annotations

import os
from typing import Literal

from . import sma_live, sma_run
from .mock_store import MockStore
from .sma_files import SmaFiles
from .store import (
    AGENTS,
    Agent,
    AgentStore,
    Approval,
    Card,
    Document,
    FileInfo,
    InboxMessage,
    InboxThread,
    NotFoundError,
    QuestionDetail,
    QuestionSummary,
    ReadOnlyStoreError,
    RunDetail,
    RunSummary,
    StoreError,
)

__all__ = [
    "AGENTS",
    "Agent",
    "AgentStore",
    "Approval",
    "Card",
    "Document",
    "FileInfo",
    "InboxMessage",
    "InboxThread",
    "MockStore",
    "NotFoundError",
    "QuestionDetail",
    "QuestionSummary",
    "ReadOnlyStoreError",
    "RunDetail",
    "RunSummary",
    "SmaFiles",
    "StoreError",
    "open_store",
    "sma_live",
    "sma_run",
]


def open_store(kind: Literal["mock", "sma"] = "mock",
               path: str | os.PathLike[str] | None = None) -> AgentStore:
    """`mock`: path is the write folder (temporary if None). `sma`: path is the
    soft-matter-agents root ($DINO_AF_SMA_ROOT or the desktop checkout if None)."""
    if kind == "mock":
        return MockStore(path)
    if kind == "sma":
        return SmaFiles(path)
    raise ValueError(f"store kind must be 'mock' or 'sma', got {kind!r}")
