"""Simulation status (PLAN.md 2절 F6): runs, progress, series, trajectory frames, zip.

Every route is a GET, so a remote viewer can follow a run too (the shared access rules in
`server/api/__init__.py` still ask for a login). The data layer is `agents.simulation`; this
module only turns it into HTTP.

Which runs: `app.state.simulation_runs` when the launcher sets one (a `SimulationRuns`, or a
`MockSimulations`). Otherwise the agent store decides: the soft-matter-agents files
(`SmaFiles`) mean their `simulation_agent/runs/`, and anything else (the default `MockStore`)
means the mock runs of `agents.mock_sim`, written to a temporary folder that goes with the app.
The mock runs move forward with the clock; they are synced on each read, so no thread runs.

Progress is pushed as server-sent events on `/runs/{run_id}/progress/stream`: one `progress`
event when it changes, until the run ends, the client goes or `limit` events were sent.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import weakref
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...agents import SmaFiles
from ...agents.mock_sim import MockSimulation, make_mock_runs
from ...agents.simulation import (
    NotFoundError,
    SimulationRuns,
    TrajectoryUnavailable,
)
from ..schemas import ApiError
from . import Refusal

router = APIRouter()

STREAM_INTERVAL_S = 1.0


# -- wire models ---------------------------------------------------------------------------
# Field for field the to_dict() of agents.simulation; the web types follow these.


class ProgressOut(BaseModel):
    run_id: str
    state: Literal["running", "complete", "fault", "aborted", "unknown"]
    source: Literal["log", "trajectory_meta", "none"]
    steps_taken: int | None
    steps_total: int | None
    fraction: float | None
    frames_saved: int | None
    frames_expected: int | None
    simulated_time: float | None
    started_at: str | None
    updated_at: str | None
    finished_at: str | None
    elapsed_s: float | None
    remaining_s: float | None
    eta: str | None
    stopped_by: str | None = None
    failure: Any = None


class FileInfoOut(BaseModel):
    name: str
    size: int


class RunInfoOut(BaseModel):
    run_id: str
    qid: str | None
    backend: str | None
    progress: ProgressOut
    files: list[FileInfoOut]
    trajectory: str | None  # "<format>:<file>" when this server can read it
    trajectory_unavailable: str | None
    source: str


class CurveOut(BaseModel):
    path: str
    x_name: str | None
    x: list[float | None]
    y: list[float | None]
    kind: Literal["line", "histogram"] = "line"


class SeriesOut(BaseModel):
    run_id: str
    log: dict[str, list[float | None]]
    observable: str | None
    curves: list[CurveOut]
    scalars: dict[str, float]
    observables: Any  # observables.json as it is


class FrameOut(BaseModel):
    """The frame both viewers draw (web/src/features/simulation/frame.ts FrameJson)."""

    index: int
    step: int | None
    n: int
    dimensions: int
    units: str
    box: list[float]
    types: list[str]
    typeid: list[int]
    positions: list[float]  # flat x, y, z per particle
    fields: dict[str, Any]


class ZipEntryOut(BaseModel):
    name: str
    size: int
    optional: bool


# -- the runs ----------------------------------------------------------------------------


class MockSimulations:
    """The mock runs for a server without soft-matter-agents files: `make_mock_runs` in a
    temporary folder that is deleted with this object. `runs` syncs them to the clock first."""

    def __init__(self, write_dir: str | Path | None = None) -> None:
        if write_dir is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="dinoaf-mock-sim-")
            write_dir = self._tmp.name
            self._finalizer = weakref.finalize(self, self._tmp.cleanup)
        self.sims: list[MockSimulation] = make_mock_runs(write_dir)
        self._runs = SimulationRuns(write_dir, trajectory_roots=[], source="mock")
        self._lock = threading.Lock()

    @property
    def runs(self) -> SimulationRuns:
        with self._lock:
            for s in self.sims:
                s.sync()
        return self._runs

    def close(self) -> None:
        if getattr(self, "_finalizer", None) is not None:
            self._finalizer()


def _runs_for(app: Any) -> SimulationRuns | MockSimulations:
    held = getattr(app.state, "simulation_runs", None)
    if held is None:
        store = getattr(app.state, "agent_store", None)
        if isinstance(store, SmaFiles):
            held = SimulationRuns(store.root / "simulation_agent" / "runs")
        else:
            held = MockSimulations()
        app.state.simulation_runs = held
    return held


_pick_lock = threading.Lock()


def get_runs(request: Request) -> SimulationRuns:
    with _pick_lock:
        held = _runs_for(request.app)
    return held.runs if isinstance(held, MockSimulations) else held


Runs = Annotated[SimulationRuns, Depends(get_runs)]


def _not_found(e: Exception) -> Exception:
    return Refusal(404, "not_found", str(e)).http()


NOT_FOUND = {404: {"model": ApiError}}


# -- routes ------------------------------------------------------------------------------


@router.get("/runs", response_model=list[RunInfoOut])
def list_runs(runs: Runs) -> list[dict[str, Any]]:
    """Every run, newest first, with its progress and whether its trajectory can be read."""
    return [r.to_dict() for r in runs.list_runs()]


@router.get("/runs/{run_id}", response_model=RunInfoOut, responses=NOT_FOUND)
def get_run(run_id: str, runs: Runs) -> dict[str, Any]:
    try:
        return runs.info(run_id).to_dict()
    except NotFoundError as e:
        raise _not_found(e) from e


@router.get("/runs/{run_id}/progress", response_model=ProgressOut, responses=NOT_FOUND)
def get_progress(run_id: str, runs: Runs) -> dict[str, Any]:
    """F6.1. State "unknown" when the run's files do not say how far it is."""
    try:
        return runs.progress(run_id).to_dict()
    except NotFoundError as e:
        raise _not_found(e) from e


@router.get(
    "/runs/{run_id}/progress/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}, **NOT_FOUND},
)
async def stream_progress(request: Request, run_id: str,
                          limit: Annotated[int | None, Query(ge=1)] = None) -> StreamingResponse:
    """Server-sent events: `event: progress` with a ProgressOut whenever it changes, until the
    run is no longer running, the client disconnects, or `limit` events were sent."""
    app = request.app

    def read() -> dict[str, Any]:
        with _pick_lock:
            held = _runs_for(app)
        runs = held.runs if isinstance(held, MockSimulations) else held
        return runs.progress(run_id).to_dict()

    try:
        first = await asyncio.to_thread(read)
    except NotFoundError as e:
        raise _not_found(e) from e

    async def events() -> AsyncIterator[str]:
        sent, last, p = 0, None, first
        while True:
            body = json.dumps(p)
            if body != last:
                yield f"event: progress\ndata: {body}\n\n"
                sent, last = sent + 1, body
            if p["state"] != "running" or (limit is not None and sent >= limit):
                return
            await asyncio.sleep(STREAM_INTERVAL_S)
            if await request.is_disconnected():
                return
            try:
                p = await asyncio.to_thread(read)
            except NotFoundError:
                return

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store"})


@router.get("/runs/{run_id}/series", response_model=SeriesOut, responses=NOT_FOUND)
def get_series(run_id: str, runs: Runs) -> dict[str, Any]:
    """F6.4. The log's progress columns and observables.json, values as read."""
    try:
        return runs.series(run_id).to_dict()
    except NotFoundError as e:
        raise _not_found(e) from e


@router.get("/runs/{run_id}/frames/{index}", response_model=FrameOut, responses=NOT_FOUND)
def get_frame(run_id: str, index: int, runs: Runs, fields: str = "") -> dict[str, Any]:
    """F6.3. One trajectory frame; `index` may be negative (-1 is the newest).
    `?fields=a,b` adds per-particle fields. 404 `trajectory_unavailable` says why there is none."""
    names = [f.strip() for f in fields.split(",") if f.strip()]
    try:
        reader = runs.trajectory(run_id)
    except NotFoundError as e:
        raise _not_found(e) from e
    except TrajectoryUnavailable as e:
        raise Refusal(404, "trajectory_unavailable", e.reason).http() from e
    try:
        return reader.frame(index, names).to_dict()
    except NotFoundError as e:
        raise _not_found(e) from e
    finally:
        reader.close()


@router.get("/runs/{run_id}/zip/entries", response_model=list[ZipEntryOut], responses=NOT_FOUND)
def get_zip_entries(run_id: str, runs: Runs) -> list[dict[str, Any]]:
    """What the zip holds; `optional` files (the trajectory) go in only with `?trajectory=1`."""
    try:
        return [e.to_dict() for e in runs.zip_entries(run_id)]
    except NotFoundError as e:
        raise _not_found(e) from e


@router.get(
    "/runs/{run_id}/zip",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/zip": {}}}, **NOT_FOUND},
)
def get_zip(run_id: str, runs: Runs, trajectory: bool = False) -> StreamingResponse:
    """F6.2. The run folder as a zip, streamed; the originals are only read."""
    try:
        chunks: Iterator[bytes] = runs.iter_zip(run_id, include_optional=trajectory)
    except NotFoundError as e:
        raise _not_found(e) from e
    return StreamingResponse(
        chunks,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.zip"',
                 "Cache-Control": "no-store"},
    )
