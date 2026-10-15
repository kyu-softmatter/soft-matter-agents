"""`/api/patterns`: motion patterns for the piezo stage and the tweezer traps (T-20261002-2205).

A pattern is a design, not a run record: it is kept as one JSON file per pattern in the
settings folder (`app.state.patterns`, `<settings>/patterns/<id>.json`), shared by the mock
and the bench so a pattern made on the mock runs unchanged later. The shape and the checks are
`engine/patterns.py`. Nothing here moves hardware; running a pattern is a later operation.

Reads are for everyone who may read the API. Writes (POST save, POST .../delete, the app's one
write verb) go through the server-action
rule (`server_action_why`: login, loopback, operator or admin) and the CSRF origin check.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ...engine.patterns import PATTERN_ID, Pattern, PatternError, pattern_from_dict
from . import Login, Refusal, origin_refusal, server_action_why

router = APIRouter()


class TrackIO(BaseModel):
    #: "piezo" or "trap:N"
    target: str
    #: [t_s, x_um, y_um, z_um] per point; times start at 0 and go up
    points: list[list[float]]


class PatternIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""
    tracks: list[TrackIO] = Field(min_length=1)
    loop: bool = False
    notes: str = ""


class PatternOut(PatternIn):
    model_config = ConfigDict(extra="ignore")

    version: int
    id: str
    duration_s: float
    meta: dict[str, Any] = Field(default_factory=dict)


class PatternSummary(BaseModel):
    id: str
    name: str
    duration_s: float
    targets: list[str]
    updated_at: str | None = None


class PatternStore:
    """One JSON file per pattern; writes go to a temporary file and are swapped in."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self._lock = threading.Lock()

    def _path(self, pattern_id: str) -> Path:
        if not PATTERN_ID.match(pattern_id):
            raise PatternError("id: lower-case letters, digits, '-' and '_', at most 64")
        return self.root / f"{pattern_id}.json"

    def get(self, pattern_id: str) -> Pattern | None:
        p = self._path(pattern_id)
        if not p.is_file():
            return None
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            raise PatternError(f"{p.name} is not valid JSON: {e}") from e
        return pattern_from_dict(raw, pattern_id=pattern_id)

    def all(self) -> list[Pattern]:
        out = []
        if self.root.is_dir():
            for p in sorted(self.root.glob("*.json")):
                try:
                    got = self.get(p.stem)
                except PatternError:
                    continue  # a hand-edited file that no longer checks is skipped, not fatal
                if got is not None:
                    out.append(got)
        return out

    def put(self, pattern: Pattern) -> None:
        path = self._path(pattern.id)
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.root, prefix=f".{pattern.id}.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(pattern.to_dict(), f, indent=1)
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)  # never leave a half-written temporary file
                raise

    def delete(self, pattern_id: str) -> bool:
        path = self._path(pattern_id)
        with self._lock:
            if not path.is_file():
                return False
            path.unlink()
        return True


def _store(request: Request) -> PatternStore:
    store = getattr(request.app.state, "patterns", None)
    if store is None:
        raise Refusal(503, "no_patterns", "no pattern folder is configured on this server").http()
    return store


def _out(p: Pattern) -> PatternOut:
    return PatternOut(**p.to_dict(), duration_s=p.duration_s)


def _bad(e: PatternError) -> Refusal:
    return Refusal(422, "invalid_pattern", str(e))


def _write_check(request: Request, me, action: str) -> None:
    if why := server_action_why(me, action) or origin_refusal(request):
        raise why.http()


@router.get("", response_model=list[PatternSummary])
def list_patterns(request: Request) -> list[PatternSummary]:
    return [PatternSummary(id=p.id, name=p.name, duration_s=p.duration_s,
                           targets=[t.target for t in p.tracks],
                           updated_at=p.meta.get("updated_at"))
            for p in _store(request).all()]


@router.get("/{pattern_id}", response_model=PatternOut)
def get_pattern(pattern_id: str, request: Request) -> PatternOut:
    try:
        got = _store(request).get(pattern_id)
    except PatternError as e:
        raise _bad(e).http() from e
    if got is None:
        raise Refusal(404, "not_found", f"no pattern {pattern_id}").http()
    return _out(got)


@router.post("/{pattern_id}", response_model=PatternOut)
def save_pattern(pattern_id: str, body: PatternIn, request: Request, me: Login) -> PatternOut:
    """Create or replace. The server checks it (`engine/patterns.py`) and stamps the times."""
    _write_check(request, me, "pattern_save")
    store = _store(request)
    now = datetime.now(UTC).isoformat()
    try:
        old = store.get(pattern_id)
        raw = body.model_dump()
        raw["meta"] = {"created_at": old.meta.get("created_at", now) if old else now,
                       "updated_at": now, "by": me.info.user_id}
        pattern = pattern_from_dict(raw, pattern_id=pattern_id)
    except PatternError as e:
        raise _bad(e).http() from e
    store.put(pattern)
    return _out(pattern)


@router.post("/{pattern_id}/delete", status_code=204)
def delete_pattern(pattern_id: str, request: Request, me: Login) -> Response:
    _write_check(request, me, "pattern_delete")
    try:
        gone = _store(request).delete(pattern_id)
    except PatternError as e:
        raise _bad(e).http() from e
    if not gone:
        raise Refusal(404, "not_found", f"no pattern {pattern_id}").http()
    return Response(status_code=204)
