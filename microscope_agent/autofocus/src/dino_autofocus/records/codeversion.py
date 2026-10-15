"""Which version of this code ran a session: commit hash and whether the tree was dirty.

Read-only git calls on the *code* repository (``rev-parse``, ``status``). Never fails a
session: if git or the repository is missing, the fields are None and ``error`` says why.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .layout import NO_WINDOW

CODE_REPO = Path(__file__).resolve().parents[3]  # src/dino_autofocus/records -> repo root


@dataclass
class CodeVersion:
    repo: str
    commit: str | None
    dirty: bool | None   # uncommitted changes to tracked or untracked files
    error: str | None = None


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                         timeout=20, encoding="utf-8", errors="replace", **NO_WINDOW)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"git {args[0]} exited {out.returncode}")
    return out.stdout


def code_version(repo: Path | None = None) -> CodeVersion:
    r = Path(repo) if repo is not None else CODE_REPO
    try:
        commit = _git(r, "rev-parse", "HEAD").strip()
        dirty = bool(_git(r, "status", "--porcelain").strip())
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return CodeVersion(str(r), None, None, f"{type(exc).__name__}: {exc}")
    return CodeVersion(str(r), commit, dirty)
