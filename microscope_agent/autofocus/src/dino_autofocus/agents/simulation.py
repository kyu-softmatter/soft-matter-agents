"""Simulation runs for the status screen (F6): progress, series, trajectory frames, zip.

Reads a soft-matter-agents `simulation_agent/runs/<run_id>/` folder, or one written by
`mock_sim`, and never writes it. The simulation code is not imported.

    config.json            the plan's parameters, backend, seed
    log.json               events; `progress` events carry the backend's state while it runs
    observables.json       what the run measured, left as it is
    trajectory_meta.json   frame count, stop outcome, and where the trajectory file is

Progress comes from one function, `read_progress`. Whether a running simulation writes its
log before it ends is still to be checked on the microscope PC (PLAN.md 10절); when nothing
says how far a run is, the state is "unknown".

Graph values are the numbers in the files. `read_series` reshapes them into columns and
curves and computes nothing.

Every trajectory reader returns the same `Frame`: positions, type ids, box and step. The 2D
(Canvas) and 3D (Three.js) viewers both draw it. Other per-particle fields are read only
when asked for by name.

`FileInfo`, `NotFoundError` and the soft-matter-agents root are the agent store's
(`agents.store`, `agents.sma_files`), so one `except NotFoundError` covers both.
"""

from __future__ import annotations

import json
import math
import os
import re
import zipfile
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np

from .sma_files import default_root
from .store import FileInfo, NotFoundError, StoreError

# Folders searched for a trajectory file the run folder does not hold, `os.pathsep`
# separated. The real place on the WSL side is to be found on the microscope PC.
TRAJECTORY_ROOTS_ENV = "DINO_AF_SIM_TRAJECTORY_ROOTS"

RECORD_FILES = ("config.json", "log.json", "observables.json", "trajectory_meta.json")
MAX_READ_BYTES = 20_000_000  # a record file over this is not opened

ProgressState = Literal["running", "complete", "fault", "aborted", "unknown"]
ProgressSource = Literal["log", "trajectory_meta", "none"]

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class SimulationError(StoreError):
    """Base for errors raised here. A missing run, file or frame is `NotFoundError`."""


class TrajectoryUnavailable(SimulationError):
    """The run has no trajectory this process can read; `reason` says why."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# -- progress ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunProgress:
    """How far a run is (F6.1).

    `steps_total` is the plan's step count (preflight frames x steps per frame, else the
    planned time over the timestep). `eta` assumes the steps-per-second rate seen so far
    holds. Times are ISO 8601 UTC strings; durations are seconds.
    """

    run_id: str
    state: ProgressState
    source: ProgressSource  # which file the numbers came from
    steps_taken: int | None
    steps_total: int | None
    fraction: float | None  # steps_taken / steps_total, 0..1
    frames_saved: int | None
    frames_expected: int | None
    simulated_time: float | None  # s, as the backend reported it
    started_at: str | None  # log t0_wall
    updated_at: str | None  # wall time of the last event read
    finished_at: str | None
    elapsed_s: float | None  # to finished_at, else to `now`
    remaining_s: float | None
    eta: str | None
    stopped_by: str | None = None
    failure: Any = None  # the backend's failure field, untouched

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunProgress:
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})


def read_progress(run_dir: str | os.PathLike[str], *, now: datetime | None = None) -> RunProgress:
    """The one place progress is read from. Missing or unreadable files give "unknown"."""
    d = Path(run_dir)
    now = now or datetime.now(UTC)
    log = _small_json(d / "log.json")
    meta = _small_json(d / "trajectory_meta.json")
    config = _small_json(d / "config.json")
    events = [e for e in log.get("events", []) if isinstance(e, dict)] if log else []

    preflight = next((e.get("report") for e in events if e.get("event") == "preflight"), None)
    preflight = preflight if isinstance(preflight, dict) else {}
    frames_expected = _int(preflight.get("frames_expected"))
    steps_total = _planned_steps(preflight, config)

    t0 = _parse_time(log.get("t0_wall"))
    finished = _parse_time(log.get("finished_at"))
    last_state: dict[str, Any] = {}
    last_t: float | None = None
    end_outcome: str | None = None
    stopped_by: str | None = None
    for e in events:
        st = e.get("state")
        if isinstance(st, dict) and "steps_taken" in st:
            last_state = st
            last_t = _float(e.get("t_mono"))
        if e.get("event") in ("complete", "abort"):
            # the monitor that fired says the outcome; a backend that ended by itself
            # leaves the monitor null and says it in its state
            mon = e.get("monitor") if isinstance(e.get("monitor"), dict) else {}
            st = st if isinstance(st, dict) else {}
            end_outcome = _str(mon.get("outcome")) or _str(st.get("state")) or e["event"]
            stopped_by = _str(mon.get("id"))

    last = _str(last_state.get("state"))
    source: ProgressSource = "log" if last_state or end_outcome else "none"
    state: ProgressState
    if end_outcome is not None:
        state = _end_state(end_outcome)
    elif last == "running":
        state = "running"
    elif last in ("complete", "fault"):
        state = _end_state(last)
    elif meta.get("stop_outcome") is not None:
        state, source = _end_state(str(meta["stop_outcome"])), "trajectory_meta"
    else:
        state = "unknown"

    steps = _int(last_state.get("steps_taken"))
    frames = _int(last_state.get("frames_saved"))
    sim_time = _float(last_state.get("simulated_time"))
    if steps is None and meta:  # a finished run whose log has no state
        steps, frames = _int(meta.get("steps_taken")), _int(meta.get("frames_saved"))
        sim_time = _float(meta.get("simulated_time"))
        if source == "none" and steps is not None:
            source = "trajectory_meta"
    stopped_by = stopped_by or _str(meta.get("stopped_by"))

    fraction = None
    if steps is not None and steps_total:
        fraction = min(max(steps / steps_total, 0.0), 1.0)
    elif _float(last_state.get("fraction_of_planned_steps")) is not None:
        fraction = _float(last_state.get("fraction_of_planned_steps"))

    updated = t0 + timedelta(seconds=last_t) if t0 and last_t is not None else None
    end = now if state == "running" else finished or updated
    elapsed = (end - t0).total_seconds() if t0 and end else None

    remaining = eta = None
    if state == "running" and steps and steps_total and last_t and updated:
        remaining = max(steps_total - steps, 0) * last_t / steps
        eta = updated + timedelta(seconds=remaining)
        remaining = max((eta - now).total_seconds(), 0.0)

    return RunProgress(
        run_id=d.name,
        state=state,
        source=source,
        steps_taken=steps,
        steps_total=steps_total,
        fraction=fraction,
        frames_saved=frames,
        frames_expected=frames_expected,
        simulated_time=sim_time,
        started_at=_iso(t0),
        updated_at=_iso(updated or finished),
        finished_at=_iso(finished),
        elapsed_s=elapsed,
        remaining_s=remaining,
        eta=_iso(eta),
        stopped_by=stopped_by,
        failure=last_state.get("failure"),
    )


def _planned_steps(preflight: dict[str, Any], config: dict[str, Any]) -> int | None:
    frames, per = _int(preflight.get("frames_expected")), _int(preflight.get("steps_per_frame"))
    if frames and per:
        return frames * per
    p = config.get("parameters_si")
    if isinstance(p, dict):
        total, dt = _float(p.get("total_simulated_time")), _float(p.get("integration_timestep"))
        if total and dt:
            return round(total / dt)
    return None


def _end_state(outcome: str) -> ProgressState:
    if outcome == "complete":
        return "complete"
    if outcome == "fault":
        return "fault"
    return "aborted"


# -- series -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Curve:
    """A curve found in observables.json. `path` is where, e.g. "psi6_curve.psi6_global".

    A "line" has one x per y. A "histogram" has bin edges in x, one more than its y.
    """

    path: str
    x_name: str | None
    x: list[float | None]
    y: list[float | None]
    kind: Literal["line", "histogram"] = "line"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunSeries:
    """What the graphs draw (F6.4), as read.

    `log` has one column per numeric field of the progress states, one row per progress
    event, plus `t_mono` (s since the log's t0). `observables` is the file whole; `curves`
    and `scalars` point into it so a graph does not have to know each observable's layout.
    """

    run_id: str
    log: dict[str, list[float | None]]
    observable: str | None
    curves: list[Curve]
    scalars: dict[str, float]
    observables: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "log": {k: list(v) for k, v in self.log.items()},
            "observable": self.observable,
            "curves": [c.to_dict() for c in self.curves],
            "scalars": dict(self.scalars),
            "observables": self.observables,
        }


def read_series(run_dir: str | os.PathLike[str]) -> RunSeries:
    d = Path(run_dir)
    log = _small_json(d / "log.json")
    rows: list[dict[str, Any]] = []
    for e in log.get("events", []) if log else []:
        if not isinstance(e, dict) or e.get("event") != "progress":
            continue
        if isinstance(e.get("state"), dict):
            rows.append({"t_mono": e.get("t_mono"), **e["state"]})
    names: list[str] = []
    for r in rows:
        names += [k for k, v in r.items() if _is_number(v) and k not in names]
    columns = {k: [r[k] if _is_number(r.get(k)) else None for r in rows] for k in names}

    obs: Any = None
    p = d / "observables.json"
    if p.is_file():
        obs = _small_json(p) or None
    curves: list[Curve] = []
    scalars: dict[str, float] = {}
    if isinstance(obs, dict):
        _walk(obs, "", curves, scalars)
    observable = _str(obs.get("observable")) if isinstance(obs, dict) else None
    return RunSeries(d.name, columns, observable, curves, scalars, obs)


_X_HINTS = ("time", "lag", "step", "center", "centre", "bin")


def _walk(v: Any, path: str, curves: list[Curve], scalars: dict[str, float]) -> None:
    if isinstance(v, dict):
        lists = {k: x for k, x in v.items() if _numeric_list(x)}
        used: set[str] = set()
        # a histogram: bin edges, and lists one shorter
        for ek in [k for k in lists if "edge" in k.lower()]:
            ys = [k for k in lists if k != ek and len(lists[k]) == len(lists[ek]) - 1]
            for k in ys:
                curves.append(Curve(_join(path, k), ek, list(lists[ek]), list(lists[k]),
                                    "histogram"))
            if ys:
                used |= {ek, *ys}
        # equal-length lists side by side: the first one named like an axis is x
        by_len: dict[int, list[str]] = {}
        for k in lists:
            if k not in used:
                by_len.setdefault(len(lists[k]), []).append(k)
        for keys in by_len.values():
            if len(keys) < 2:
                continue
            axes = [k for k in keys if any(h in k.lower() for h in _X_HINTS)]
            xk = axes[0] if axes else keys[0]
            for k in keys:
                if k != xk:
                    curves.append(Curve(_join(path, k), xk, list(lists[xk]), list(lists[k])))
            used |= set(keys)
        for k, x in v.items():
            if k not in used:
                _walk(x, _join(path, k), curves, scalars)
    elif isinstance(v, list):
        if v and all(isinstance(r, list) and len(r) == 2 and all(map(_is_number, r)) for r in v):
            curves.append(Curve(path, None, [r[0] for r in v], [r[1] for r in v]))
    elif _is_number(v) and path:
        scalars[path] = v


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _numeric_list(x: Any) -> bool:
    return isinstance(x, list) and len(x) > 0 and all(_is_number(i) or i is None for i in x)


# -- trajectory -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Frame:
    """One trajectory frame, the format both viewers draw.

    positions: (N, 3) float32, in `units`; a 2D run has z = 0.
    typeid: (N,) int32 index into `types`.
    box: [Lx, Ly, Lz, xy, xz, yz] as in GSD; a 2D run has Lz = 0.
    fields: per-particle arrays read only when asked for (e.g. "orientation").
    """

    index: int
    step: int | None
    positions: np.ndarray
    typeid: np.ndarray
    types: list[str]
    box: list[float]
    dimensions: int
    units: str = "m"
    fields: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return int(self.positions.shape[0])

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready. `positions` is flat [x0, y0, z0, x1, ...] for a Float32Array."""
        return {
            "index": self.index,
            "step": self.step,
            "n": self.n,
            "dimensions": self.dimensions,
            "units": self.units,
            "box": [float(b) for b in self.box],
            "types": list(self.types),
            "typeid": self.typeid.astype(int).tolist(),
            "positions": self.positions.astype(np.float32).reshape(-1).tolist(),
            "fields": {k: np.asarray(a).tolist() for k, a in self.fields.items()},
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Frame:
        return cls(
            index=d["index"],
            step=d.get("step"),
            positions=np.asarray(d["positions"], dtype=np.float32).reshape(-1, 3),
            typeid=np.asarray(d["typeid"], dtype=np.int32),
            types=list(d["types"]),
            box=list(d["box"]),
            dimensions=d["dimensions"],
            units=d.get("units", "m"),
            fields={k: np.asarray(v) for k, v in d.get("fields", {}).items()},
        )


class TrajectoryReader(Protocol):
    path: Path

    def __len__(self) -> int: ...

    def frame(self, i: int, fields: Sequence[str] = ()) -> Frame: ...

    def close(self) -> None: ...


class NpzTrajectory:
    """The mock's trajectory: one .npz with positions (F, N, 3), step (F,), typeid (N,),
    types (T,), box (6,), dimensions (), and optionally more (F, N, ...) arrays."""

    def __init__(self, path: str | os.PathLike[str], meta: dict[str, Any] | None = None) -> None:
        self.path = Path(path)
        with np.load(self.path, allow_pickle=False) as z:
            self._data = {k: z[k] for k in z.files}
        self._positions = self._data["positions"]

    def __len__(self) -> int:
        return int(self._positions.shape[0])

    def frame(self, i: int, fields: Sequence[str] = ()) -> Frame:
        i = _check_index(i, len(self))
        extra = {}
        for name in fields:
            a = self._data.get(name)
            if a is None or a.ndim < 2 or a.shape[0] != len(self) or name == "positions":
                raise NotFoundError(f"no per-particle field {name!r} in {self.path.name}")
            extra[name] = a[i]
        steps = self._data.get("step")
        return Frame(
            index=i,
            step=int(steps[i]) if steps is not None else None,
            positions=np.asarray(self._positions[i], dtype=np.float32),
            typeid=np.asarray(self._data["typeid"], dtype=np.int32),
            types=[str(t) for t in self._data["types"]],
            box=[float(b) for b in self._data["box"]],
            dimensions=int(self._data["dimensions"]),
            fields=extra,
        )

    def close(self) -> None:
        pass


class GsdTrajectory:
    """A HOOMD GSD file through the `gsd` package (the server dependency group).

    Imported only when a GSD trajectory is opened; where `gsd` is not installed (an
    environment without the server group), opening one raises TrajectoryUnavailable.
    Fields: "orientation", "velocity", "image",
    "charge", "diameter", "mass" and any other `particles` attribute.
    """

    def __init__(self, path: str | os.PathLike[str], meta: dict[str, Any] | None = None) -> None:
        try:
            import gsd.hoomd  # type: ignore[import-not-found]
        except ImportError as e:
            raise TrajectoryUnavailable("reading GSD needs the gsd package, not installed") from e
        self.path = Path(path)
        self._f = gsd.hoomd.open(str(self.path), "r")

    def __len__(self) -> int:
        return len(self._f)

    def frame(self, i: int, fields: Sequence[str] = ()) -> Frame:
        i = _check_index(i, len(self))
        snap = self._f[i]
        p, c = snap.particles, snap.configuration
        extra = {}
        for name in fields:
            a = getattr(p, name, None)
            if a is None or name in ("position", "typeid", "types"):
                raise NotFoundError(f"no per-particle field {name!r} in {self.path.name}")
            extra[name] = np.asarray(a)
        n = int(p.N)
        typeid = np.asarray(p.typeid if p.typeid is not None else np.zeros(n), dtype=np.int32)
        return Frame(
            index=i,
            step=int(c.step) if c.step is not None else None,
            positions=np.asarray(p.position, dtype=np.float32).reshape(n, 3),
            typeid=typeid,
            types=[str(t) for t in (p.types or ["A"])],
            box=[float(b) for b in c.box],
            dimensions=int(c.dimensions),
            fields=extra,
        )

    def close(self) -> None:
        self._f.close()


class TxtTrajectory:
    """The text trajectory of soft-matter-agents' HOOMD backends (`format: "txt"`).

    UNVERIFIED LAYOUT: no sample file has been checked yet (T-012; the samples are a user
    item). The layout is guessed from trajectory_meta.json, which gives the column names
    (step, particle, x, y[, z][, theta ...]), the frame count and the particle count: one row
    per particle per frame, whitespace or comma separated, `#` comments and a header line
    skipped, frames in order of step. Every guess is checked against those counts when the
    file is opened; any mismatch raises TrajectoryUnavailable saying the layout is unverified,
    so a wrong guess shows as "no trajectory", never as wrong frames.

    Opening scans the file once for where each frame starts (cached per file size and mtime),
    so reading a frame reads only its rows. Columns other than step, particle and x/y/z
    (e.g. "theta") are per-particle fields. The file has no types: every particle is "A".
    """

    verified = False

    def __init__(self, path: str | os.PathLike[str], meta: dict[str, Any] | None = None) -> None:
        self.path = Path(path)
        t = meta or {}
        cols = [c.get("name") for c in t.get("columns", []) if isinstance(c, dict)]
        if not cols or not all(isinstance(c, str) for c in cols):
            raise self._unverified("trajectory_meta.json lists no column names")
        missing = [c for c in ("step", "particle", "x", "y") if c not in cols]
        if missing:
            raise self._unverified(f"no {', '.join(missing)} column")
        self.columns: list[str] = cols
        box = t.get("box") if isinstance(t.get("box"), dict) else {}
        dims = _int(box.get("dimensions")) or (3 if "z" in cols else 2)
        length = _float(box.get("length_m")) or 0.0
        self.dimensions = 3 if dims == 3 else 2
        self.box = [length, length, length if self.dimensions == 3 else 0.0, 0.0, 0.0, 0.0]
        self._index = _txt_index(self.path, len(cols), cols.index("step"))
        if not self._index:
            raise self._unverified("no data rows")
        counts = {n for _, n in self._index}
        if len(counts) != 1:
            raise self._unverified(f"frames have different row counts {sorted(counts)[:5]}")
        self.n = counts.pop()
        frames, particles = _int(t.get("frames")), _int(t.get("particles"))
        if particles is not None and self.n != particles:
            raise self._unverified(f"{self.n} rows per frame, trajectory_meta says "
                                   f"{particles} particles")
        if frames is not None and len(self._index) != frames:
            raise self._unverified(f"{len(self._index)} frames, trajectory_meta says {frames}")

    def _unverified(self, why: str) -> TrajectoryUnavailable:
        return TrajectoryUnavailable(_unverified_txt(self.path, why))

    def __len__(self) -> int:
        return len(self._index)

    def frame(self, i: int, fields: Sequence[str] = ()) -> Frame:
        i = _check_index(i, len(self))
        col = {c: k for k, c in enumerate(self.columns)}
        plain = {"step", "particle", "x", "y", "z"}
        for name in fields:
            if name in plain or name not in col:
                raise NotFoundError(f"no per-particle field {name!r} in {self.path.name}")
        offset, count = self._index[i]
        rows: list[list[float]] = []
        with self.path.open("rb") as f:
            f.seek(offset)
            while len(rows) < count:
                line = f.readline()
                if not line:
                    break
                tokens = _txt_tokens(line)
                if tokens is not None:
                    rows.append([float(x) for x in tokens])
        a = np.asarray(rows, dtype=np.float64)
        if a.shape != (self.n, len(self.columns)):
            raise self._unverified(f"frame {i} changed while reading")
        a = a[np.argsort(a[:, col["particle"]], kind="stable")]
        pos = np.zeros((self.n, 3), dtype=np.float32)
        for k, axis in enumerate("xyz"):
            if axis in col:
                pos[:, k] = a[:, col[axis]]
        return Frame(
            index=i,
            step=int(a[0, col["step"]]),
            positions=pos,
            typeid=np.zeros(self.n, dtype=np.int32),
            types=["A"],
            box=list(self.box),
            dimensions=self.dimensions,
            fields={name: a[:, col[name]] for name in fields},
        )

    def close(self) -> None:
        pass


def _unverified_txt(path: Path, why: str) -> str:
    return f"{path.name}: unverified txt layout ({why}); no sample file has been checked yet"


def _txt_tokens(line: bytes) -> list[bytes] | None:
    """The values of a data row, or None for a blank, `#` comment or header line."""
    s = line.strip()
    if not s or s.startswith(b"#"):
        return None
    tokens = s.replace(b",", b" ").split()
    try:
        float(tokens[0])
    except ValueError:
        return None  # a header line of column names
    return tokens


_TXT_INDEX_CACHE: dict[tuple[str, int, int], list[tuple[int, int]]] = {}


def _txt_index(path: Path, ncols: int, step_col: int) -> list[tuple[int, int]]:
    """(byte offset, row count) of each frame, a frame being a run of rows with one step."""
    st = path.stat()
    key = (str(path.resolve()), st.st_size, st.st_mtime_ns)
    if key in _TXT_INDEX_CACHE:
        return _TXT_INDEX_CACHE[key]
    index: list[tuple[int, int]] = []
    step: bytes | None = None
    offset = 0
    with path.open("rb") as f:
        for lineno, line in enumerate(f, 1):
            tokens = _txt_tokens(line)
            if tokens is not None:
                if len(tokens) != ncols:
                    raise TrajectoryUnavailable(_unverified_txt(
                        path, f"line {lineno} has {len(tokens)} values, trajectory_meta names "
                              f"{ncols} columns"))
                if tokens[step_col] != step:
                    step = tokens[step_col]
                    index.append((offset, 0))
                index[-1] = (index[-1][0], index[-1][1] + 1)
            offset += len(line)
    if len(_TXT_INDEX_CACHE) > 16:
        _TXT_INDEX_CACHE.clear()
    _TXT_INDEX_CACHE[key] = index
    return index


READERS: dict[str, type] = {"npz": NpzTrajectory, "gsd": GsdTrajectory, "txt": TxtTrajectory}


def default_trajectory_roots() -> list[Path]:
    env = os.environ.get(TRAJECTORY_ROOTS_ENV, "")
    return [Path(p) for p in env.split(os.pathsep) if p]


def locate_trajectory(run_dir: str | os.PathLike[str],
                      roots: Iterable[str | os.PathLike[str]] = ()) -> tuple[str, Path]:
    """(format, path) of the run's trajectory, or TrajectoryUnavailable.

    The file named in trajectory_meta.json is looked for in the run folder, then in
    `<root>/<run_id>/` and `<root>/` for each root.
    """
    d = Path(run_dir)
    meta = _small_json(d / "trajectory_meta.json")
    t = meta.get("trajectory") if meta else None
    if not isinstance(t, dict) or not isinstance(t.get("file"), str):
        raise TrajectoryUnavailable("trajectory_meta.json names no trajectory file")
    if t.get("written") is False:
        raise TrajectoryUnavailable("the run wrote no trajectory")
    name = t["file"]
    if Path(name).name != name or name in (".", ".."):
        raise TrajectoryUnavailable(f"trajectory file name is not a plain name: {name!r}")
    fmt = str(t.get("format") or Path(name).suffix.lstrip(".")).lower()
    for base in [d, *(q for r in roots for q in (Path(r) / d.name, Path(r)))]:
        if (base / name).is_file():
            return fmt, base / name
    raise TrajectoryUnavailable(f"{name} is not in the run folder or a trajectory root")


def open_trajectory(run_dir: str | os.PathLike[str],
                    roots: Iterable[str | os.PathLike[str]] = ()) -> TrajectoryReader:
    fmt, path = locate_trajectory(run_dir, roots)
    reader = READERS.get(fmt)
    if reader is None:
        raise TrajectoryUnavailable(f"no reader for trajectory format {fmt!r}")
    meta = _small_json(Path(run_dir) / "trajectory_meta.json").get("trajectory")
    return reader(path, meta if isinstance(meta, dict) else None)


def _check_index(i: int, n: int) -> int:
    j = i + n if i < 0 else i
    if not 0 <= j < n:
        raise NotFoundError(f"frame {i} out of range, {n} frames")
    return j


# -- zip --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ZipEntry:
    """A file a run's zip holds. `optional` files (the trajectory) go in only when asked."""

    name: str  # path inside the zip, "<run_id>/<file>"
    size: int
    optional: bool
    source: Path

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "size": self.size, "optional": self.optional}


def zip_entries(run_dir: str | os.PathLike[str],
                roots: Iterable[str | os.PathLike[str]] = ()) -> list[ZipEntry]:
    """Every file of the run folder, and its trajectory if it lives elsewhere.

    The trajectory and any other file over `MAX_READ_BYTES` are optional.
    """
    d = Path(run_dir)
    out: list[ZipEntry] = []
    try:
        traj: Path | None = locate_trajectory(d, roots)[1]
    except TrajectoryUnavailable:
        traj = None
    for p in sorted(d.iterdir()):
        if p.is_file():
            size = p.stat().st_size
            big = p == traj or size > MAX_READ_BYTES or p.suffix in (".gsd", ".npz", ".txt")
            out.append(ZipEntry(f"{d.name}/{p.name}", size, big, p))
    if traj is not None and traj.parent != d:
        out.append(ZipEntry(f"{d.name}/{traj.name}", traj.stat().st_size, True, traj))
    return out


def iter_zip(entries: Iterable[ZipEntry], *, include_optional: bool | Iterable[str] = False,
             chunk_size: int = 1 << 20) -> Iterator[bytes]:
    """Stream a zip of `entries` without holding it in memory or writing it to disk.

    `include_optional` is True for all optional files, or the names to include (the name in
    the zip or the bare file name).
    """
    wanted = include_optional if isinstance(include_optional, bool) else set(include_optional)

    def included(e: ZipEntry) -> bool:
        if not e.optional or wanted is True:
            return True
        return bool(wanted) and (e.name in wanted or e.source.name in wanted)

    sink = _Sink()
    with zipfile.ZipFile(sink, "w", allowZip64=True) as zf:
        for e in entries:
            if not included(e):
                continue
            method = zipfile.ZIP_STORED if e.optional else zipfile.ZIP_DEFLATED
            info = zipfile.ZipInfo.from_file(e.source, arcname=e.name)
            info.compress_type = method
            with e.source.open("rb") as src, zf.open(info, "w", force_zip64=True) as dst:
                while chunk := src.read(chunk_size):
                    dst.write(chunk)
                    yield from sink.drain()
            yield from sink.drain()
    yield from sink.drain()


class _Sink:
    """A write-only, unseekable file for ZipFile; `drain` hands over what was written."""

    def __init__(self) -> None:
        self._parts: list[bytes] = []
        self._pos = 0

    def write(self, b: bytes) -> int:
        self._parts.append(bytes(b))
        self._pos += len(b)
        return len(b)

    def tell(self) -> int:
        return self._pos

    def flush(self) -> None:
        pass

    def drain(self) -> Iterator[bytes]:
        if self._parts:
            data, self._parts = b"".join(self._parts), []
            yield data


# -- runs folder ------------------------------------------------------------------------------


@dataclass(frozen=True)
class SimRunInfo:
    """A run in the list: enough to draw a row without opening its trajectory."""

    run_id: str
    qid: str | None
    backend: str | None
    progress: RunProgress
    files: list[FileInfo]
    trajectory: str | None  # "<format>:<file>" when readable here
    trajectory_unavailable: str | None  # why not, otherwise
    source: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["progress"] = self.progress.to_dict()
        d["files"] = [f.to_dict() for f in self.files]
        return d


class SimulationRuns:
    """The runs of one folder, soft-matter-agents or a mock's. Read only."""

    def __init__(self, runs_dir: str | os.PathLike[str] | None = None, *,
                 trajectory_roots: Iterable[str | os.PathLike[str]] | None = None,
                 source: str = "soft-matter-agents") -> None:
        self.runs_dir = Path(runs_dir) if runs_dir is not None else default_runs_dir()
        self.roots = (default_trajectory_roots() if trajectory_roots is None
                      else [Path(r) for r in trajectory_roots])
        self.source = source

    def __repr__(self) -> str:
        return f"SimulationRuns({str(self.runs_dir)!r}, source={self.source!r})"

    def run_dir(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not _RUN_ID_RE.match(run_id) or run_id in (".", ".."):
            raise NotFoundError(f"not a run id: {run_id!r}")
        d = self.runs_dir / run_id
        if not d.is_dir():
            raise NotFoundError(f"no simulation run {run_id} in {self.source}")
        return d

    def run_ids(self) -> list[str]:
        """Newest first by the log's start time, then by id."""
        if not self.runs_dir.is_dir():
            return []
        ids = [p.name for p in self.runs_dir.iterdir() if p.is_dir() and _RUN_ID_RE.match(p.name)]
        started = {i: _str(_small_json(self.runs_dir / i / "log.json").get("t0_wall")) or ""
                   for i in ids}
        return sorted(ids, key=lambda i: (started[i], i), reverse=True)

    def info(self, run_id: str, *, now: datetime | None = None) -> SimRunInfo:
        d = self.run_dir(run_id)
        config = _small_json(d / "config.json")
        files = [FileInfo(p.name, p.stat().st_size) for p in sorted(d.iterdir()) if p.is_file()]
        try:
            fmt, path = locate_trajectory(d, self.roots)
            traj, why = (f"{fmt}:{path.name}", None) if fmt in READERS else \
                (None, f"no reader for trajectory format {fmt!r}")
        except TrajectoryUnavailable as e:
            traj, why = None, e.reason
        return SimRunInfo(
            run_id=run_id,
            qid=_str(config.get("qid")),
            backend=_str(config.get("backend")),
            progress=read_progress(d, now=now),
            files=files,
            trajectory=traj,
            trajectory_unavailable=why,
            source=self.source,
        )

    def list_runs(self, *, now: datetime | None = None) -> list[SimRunInfo]:
        return [self.info(i, now=now) for i in self.run_ids()]

    def progress(self, run_id: str, *, now: datetime | None = None) -> RunProgress:
        return read_progress(self.run_dir(run_id), now=now)

    def series(self, run_id: str) -> RunSeries:
        return read_series(self.run_dir(run_id))

    def records(self, run_id: str) -> dict[str, Any]:
        """The record files, whole, for a detail view."""
        d = self.run_dir(run_id)
        return {n: _small_json(d / n) for n in RECORD_FILES if (d / n).is_file()}

    def trajectory(self, run_id: str) -> TrajectoryReader:
        return open_trajectory(self.run_dir(run_id), self.roots)

    def zip_entries(self, run_id: str) -> list[ZipEntry]:
        return zip_entries(self.run_dir(run_id), self.roots)

    def iter_zip(self, run_id: str, *, include_optional: bool | Iterable[str] = False,
                 chunk_size: int = 1 << 20) -> Iterator[bytes]:
        return iter_zip(self.zip_entries(run_id), include_optional=include_optional,
                        chunk_size=chunk_size)


def default_runs_dir() -> Path:
    return default_root() / "simulation_agent" / "runs"


# -- helpers ----------------------------------------------------------------------------------


def _small_json(p: Path) -> dict[str, Any]:
    """A record file's content, or {} when absent, too big, half written or not an object."""
    try:
        if not p.is_file() or p.stat().st_size > MAX_READ_BYTES:
            return {}
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _is_number(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


def _int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return None


def _float(v: Any) -> float | None:
    return float(v) if _is_number(v) else None


def _str(v: Any) -> str | None:
    return v if isinstance(v, str) else None


def _parse_time(v: Any) -> datetime | None:
    if not isinstance(v, str):
        return None
    try:
        t = datetime.fromisoformat(v)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _iso(t: datetime | None) -> str | None:
    return t.astimezone(UTC).isoformat() if t else None
