"""Backends for `bd_overdamped` when the observable is `bleach_recovery_diffusivity`.

There are two classes behind the same four calls (preflight / apply / read /
abort), and both run the same physics:

- `BleachHoomdBackend`: the engine, HOOMD's Brownian integrator in reduced
  units, the same unit system `hoomd_backend` uses (sigma = bead diameter,
  energy k_B T, time sigma^2/D).
- `BleachMockBackend`: the first-class mock, which integrates the same free
  overdamped motion in SI with NumPy. **It applies the bleach label and
  returns the same observables.** The operator falls back to it when the
  engine is missing, and to nothing else. `mock_backend.MockBackend` is free
  diffusion with no bleach, and under this plan's id it would finish green
  having measured nothing the plan asked for.

**What the engine is asked to do is only to move the beads.** The beads do
not interact, so the bleach is a label on a trajectory and not a force on it.
`estimator_bleach.Bleacher` applies the label and samples the camera, and
both backends feed it xy positions at every engine step. z is integrated by
the engine (the configuration is three-dimensional) and is dropped. The
column bleach makes the depth-projected signal independent of z, so a
periodic z of the chamber depth stands in for the chamber. The walls are not
modelled; at 100 nm in a chamber tens of micrometres deep they hinder a
negligible share of the depth.

**Labels follow particle TAGS, never array positions.** HOOMD sorts its
particle arrays in memory for locality, so the row a bead occupies changes
during a run. A dark label kept by row index therefore drifts onto other
beads. The first scratch run on 2026-09-30 did exactly that: half the beads
read as permanently dark and the fitted tau came out 2.6x too long. Positions
are scattered into tag order before the Bleacher sees them, and
`python -m src.check_bleach_backend` asserts that a reordering of rows
cannot move a label, and carries the index-based reader as a control that must
fail the same assertion.

**Independent curves, not one long run.** Each curve starts from fresh
uniform positions. That is an exact equilibrium draw for non-interacting
beads, so no equilibration is needed and the curves are independent by
construction. `record_length` is a declared count of curve periods, so a
smoke run (which shortens `record_length`) runs fewer curves and not shorter
ones.

No policy lives here. The operator owns limits and stopping, the envelope
owns ceilings, and the estimator's refusals are the registered estimator's.
"""

from __future__ import annotations

import math
import threading
import time

import numpy as np

from . import estimator_bleach, mock_backend, physics

DIMENSIONS = 3
SUBMITTED, RUNNING, COMPLETE, ABORTED, FAILED = (
    mock_backend.SUBMITTED, mock_backend.RUNNING, mock_backend.COMPLETE,
    mock_backend.ABORTED, mock_backend.FAILED,
)
TERMINAL = mock_backend.TERMINAL

REQUIRED = (
    "temperature", "viscosity", "bead_diameter", "bleach_radius", "box_length", "chamber_depth",
    "n_particles", "integration_timestep", "frame_interval", "bleach_duration", "bleach_rate",
    "max_recovery_time", "pre_bleach_frames", "record_length", "curve_period",
)

UM = 1e-6


def _whole(span: float, step: float) -> bool:
    m = span / step
    return abs(m - round(m)) < 1e-6 and round(m) >= 1


def preflight_report(name: str, params: dict, seed: int) -> dict:
    missing = [k for k in REQUIRED if k not in params]
    if missing:
        return {"backend": name, "missing_parameters": missing, "steps_per_frame": None,
                "save_interval_divides_step": False, "seed": seed}
    dt = params["integration_timestep"]
    fi, tb, T = params["frame_interval"], params["bleach_duration"], params["max_recovery_time"]
    n_pre = int(round(params["pre_bleach_frames"]))
    per_curve_time = n_pre * fi + tb + math.floor(T / fi + 1e-9) * fi
    divides = _whole(fi, dt) and _whole(tb, dt)
    n_curves = int(math.floor(params["record_length"] / params["curve_period"] + 1e-9))
    D = physics.stokes_einstein(params["temperature"], params["viscosity"], params["bead_diameter"])
    return {
        "backend": name,
        "missing_parameters": [],
        # The operator's name for "a sampled instant falls on a step". Here
        # every engine step is sampled, and what must divide is the frame
        # interval and the bleach duration.
        "steps_per_frame": int(round(fi / dt)),
        "save_interval_divides_step": divides,
        "curve_fits_its_period": per_curve_time <= params["curve_period"] + 1e-12,
        "simulated_time_per_curve_s": per_curve_time,
        "curves_expected": n_curves,
        "steps_per_curve": int(round(per_curve_time / dt)),
        "diffusivity_si": D,
        "seed": seed,
    }


def rows_in_tag_order(tag, position, n: int) -> np.ndarray:
    """xy of every particle, indexed by TAG. HOOMD's rows move (module
    docstring); a label kept by row would follow whichever bead sits there."""
    xy = np.empty((n, 2))
    xy[np.asarray(tag)] = np.asarray(position)[:, :2]
    return xy


class _BleachBackend:
    """The run loop both backends share; subclasses supply the motion."""

    NAME = "bleach_backend"
    DIMENSIONS = DIMENSIONS

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)
        self.params: dict | None = None
        self.frames: list = []          # nothing is stored; see the module docstring
        self.frame_times: list = []
        self.simulated_time = 0.0
        self.steps_taken = 0
        self.curves_done = 0
        self.curve_results: list[dict] = []
        self.curve_F: list[np.ndarray] = []
        self.curve_t: np.ndarray | None = None
        self.max_step = 0.0
        self.integration_wall_s = 0.0
        self.readout_wall_s = 0.0
        self.state = None
        self.failure: str | None = None
        self.handle: str | None = None
        self.aborted: str | None = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # -- interface ---------------------------------------------------------

    def preflight(self, params: dict) -> dict:
        report = preflight_report(self.NAME, params, self.seed)
        report.update(self._engine_report())
        return report

    def apply(self, params: dict) -> dict:
        if self._worker is not None:
            raise RuntimeError("this backend has already been given a run")
        report = self.preflight(params)
        if report["missing_parameters"]:
            raise ValueError(f"missing {report['missing_parameters']}")
        if not report["curve_fits_its_period"]:
            raise ValueError("pre-bleach frames + bleach + record exceed the declared curve period")
        self.params = dict(params)
        self.state = SUBMITTED
        self.handle = f"{self.NAME}:{self.seed}:{id(self):x}"
        self._worker = threading.Thread(target=self._run, name=self.handle, daemon=True)
        submitted = self.state
        self._worker.start()
        return {"handle": self.handle, "state": submitted}

    def read(self) -> dict:
        with self._lock:
            if self.state is None:
                return {"state": None, "initialised": False}
            period = float(self.params["curve_period"])
            return {
                "state": self.state,
                "initialised": True,
                "handle": self.handle,
                "steps_taken": self.steps_taken,
                "simulated_time": self.simulated_time,
                # The declared record completed: whole curves times the curve
                # period. A count of curves expressed in the record's unit,
                # derived from an integer and not accumulated.
                "record_time_completed": self.curves_done * period,
                "curves_completed": self.curves_done,
                "frames_saved": self.curves_done,
                "max_single_step_displacement": self.max_step,
                "integration_wall_s": self.integration_wall_s,
                "frame_readout_wall_s": self.readout_wall_s,
                "failure": self.failure,
            }

    def abort(self, reason: str) -> dict:
        self.aborted = reason
        self._stop.set()
        if self._worker is not None and threading.current_thread() is not self._worker:
            self._worker.join(timeout=60)
        with self._lock:
            if self.state not in TERMINAL:
                self.state = ABORTED
            return {"aborted": True, "reason": reason, "state": self.state,
                    "steps_taken": self.steps_taken}

    # -- the run -------------------------------------------------------------

    def _run(self) -> None:
        try:
            p = self.params
            report = preflight_report(self.NAME, p, self.seed)
            n_curves = report["curves_expected"]
            w = p["bleach_radius"] / UM
            box = p["box_length"] / UM
            N = int(round(p["n_particles"]))
            dt = p["integration_timestep"]
            self._start(p)
            with self._lock:
                self.state = RUNNING
            for c in range(n_curves):
                if self._stop.is_set():
                    with self._lock:
                        self.state = ABORTED
                    return
                rng = np.random.default_rng([self.seed, c])
                bl = estimator_bleach.Bleacher(
                    w_nominal=w, box=box, k=p["bleach_rate"], bleach_duration=p["bleach_duration"],
                    frame_interval=p["frame_interval"], max_recovery_time=p["max_recovery_time"],
                    n_pre=int(round(p["pre_bleach_frames"])), sample_dt=dt, rng=rng)
                self._place(rng, N, box, p["chamber_depth"] / UM)
                prev = None
                steps = 0
                while not bl.done:
                    t0 = time.perf_counter()
                    xy = self._xy_um()
                    if prev is not None:
                        d = xy - prev
                        d -= box * np.round(d / box)
                        step_max = float(np.abs(d).max()) * UM
                        if step_max > self.max_step:
                            self.max_step = step_max
                    prev = xy
                    bl.feed(xy)
                    t1 = time.perf_counter()
                    self._advance()
                    t2 = time.perf_counter()
                    self.readout_wall_s += t1 - t0
                    self.integration_wall_s += t2 - t1
                    steps += 1
                curve = bl.curve()
                est = estimator_bleach.estimate(
                    curve["t"], curve["F"], curve["w_measured"], w, p["bleach_duration"],
                    p["frame_interval"], p["max_recovery_time"])
                est["dip"] = float(1.0 - curve["F"][0]) if len(curve["F"]) else None
                est["beads_in_disc_pre_bleach"] = curve["pre_mean_count"]
                est["dark_count"] = curve["dark_count"]
                with self._lock:
                    self.curve_results.append(est)
                    self.curve_F.append(curve["F"])
                    self.curve_t = curve["t"]
                    self.steps_taken += steps
                    # integer steps times dt, never a running sum (CLAUDE.md, S6)
                    self.simulated_time = self.steps_taken * dt
                    self.curves_done = c + 1
            with self._lock:
                self.state = COMPLETE
        except Exception as exc:                       # noqa: BLE001
            with self._lock:
                self.failure = f"{type(exc).__name__}: {exc}"
                self.state = FAILED

    # -- observables -----------------------------------------------------------

    def observables(self, params: dict) -> dict:
        """What the run read, per curve and summarised over curves. D in
        m^2/s, radii in m, times in s."""
        with self._lock:
            res = list(self.curve_results)
            Fs = [f for f in self.curve_F]
            t = self.curve_t
        rep = [r for r in res if r.get("reported")]
        D = np.array([r["D"] for r in rep]) * UM**2
        summary = {
            "n_curves": len(res),
            "n_reported": len(rep),
            "refusals": {},
            "beads_in_disc_mean": float(np.mean([r["beads_in_disc_pre_bleach"] for r in res])) if res else None,
        }
        for r in res:
            if not r.get("reported"):
                key = r.get("refusal", "unknown")
                summary["refusals"][key] = summary["refusals"].get(key, 0) + 1
        if len(D):
            summary.update({
                "D_mean": float(D.mean()),
                "D_sem": float(D.std(ddof=1) / math.sqrt(len(D))) if len(D) > 1 else None,
                "D_sd_one_curve": float(D.std(ddof=1)) if len(D) > 1 else None,
                "D_median": float(np.median(D)),
                "D_p05": float(np.percentile(D, 5)),
                "D_p16": float(np.percentile(D, 16)),
                "D_p84": float(np.percentile(D, 84)),
                "D_p95": float(np.percentile(D, 95)),
                "log10_D_sd_one_curve": float(np.log10(D).std(ddof=1)) if len(D) > 1 else None,
                "w_measured_mean": float(np.mean([r["w_measured"] for r in rep])) * UM,
                "mobile_fraction_mean": float(np.mean([r["mobile_fraction"] for r in rep])),
                "tau_mean": float(np.mean([r["tau"] for r in rep])),
            })
        bounds = [r for r in res if not r.get("reported") and r.get("D") is not None]
        if bounds:
            summary["one_sided_bounds"] = {
                "count": len(bounds),
                "D_median_of_bounds": float(np.median([r["D"] for r in bounds])) * UM**2,
                "side": sorted({r.get("bound_side") for r in bounds}),
            }
        mean_curve = None
        if Fs and t is not None:
            M = np.vstack(Fs)
            mean_curve = {"t_s": [float(x) for x in t], "F_mean": [float(x) for x in M.mean(axis=0)],
                          "F_sem": [float(x) for x in M.std(axis=0, ddof=1) / math.sqrt(len(Fs))] if len(Fs) > 1 else None}
        return {
            "observable": "bleach_recovery_diffusivity",
            "estimator": "estimator_bleach.estimate, the registered steps (contracts/observables.json)",
            "camera": "exposure equals the frame interval (an integrating camera); background 0 and "
                      "reference ratio 1 are identities in the engine and are applied",
            "summary": summary,
            "per_curve": [{k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items()})
                           for k, v in r.items()} for r in res],
            "mean_curve": mean_curve,
            "units": {"per_curve": "lengths um, times s, D um^2/s", "summary": "SI"},
        }

    # -- motion (subclasses) ----------------------------------------------------

    def _engine_report(self) -> dict:
        return {}

    def _start(self, p: dict) -> None:
        raise NotImplementedError

    def _place(self, rng, N: int, box_um: float, depth_um: float) -> None:
        raise NotImplementedError

    def _xy_um(self) -> np.ndarray:
        raise NotImplementedError

    def _advance(self) -> None:
        raise NotImplementedError


class BleachMockBackend(_BleachBackend):
    """Free overdamped motion in SI with NumPy: the exact Gaussian step, no
    potential, so no timestep error. z is not integrated, because nothing
    reads it. The column geometry makes it irrelevant, and the engine
    integrates it only because the configuration is three-dimensional."""

    NAME = "bleach_mock_backend"

    def _start(self, p: dict) -> None:
        self._D_um2 = physics.stokes_einstein(p["temperature"], p["viscosity"], p["bead_diameter"]) / UM**2
        self._dt = p["integration_timestep"]
        self._box = p["box_length"] / UM

    def _place(self, rng, N, box_um, depth_um):
        self._rng = rng
        self._xy = rng.uniform(-box_um / 2, box_um / 2, (N, 2))

    def _xy_um(self):
        return self._xy

    def _advance(self):
        s = math.sqrt(2.0 * self._D_um2 * self._dt)
        self._xy = self._xy + self._rng.normal(0.0, s, self._xy.shape)
        self._xy -= self._box * np.round(self._xy / self._box)


class BleachHoomdBackend(_BleachBackend):
    """HOOMD's Brownian integrator, kT* = gamma* = 1, sigma = bead diameter."""

    NAME = "bleach_hoomd_backend"

    def __init__(self, seed: int = 0, engine=None, device=None) -> None:
        from . import hoomd_backend                       # noqa: PLC0415
        super().__init__(seed)
        self._hb = hoomd_backend
        self.engine = engine if engine is not None else hoomd_backend._import_hoomd()
        self.device = device

    def _engine_report(self) -> dict:
        return {"engine_build": self._hb.engine_build(self.engine)}

    def _start(self, p: dict) -> None:
        hoomd = self.engine
        self.units = self._hb.Reduced(p["temperature"], p["viscosity"], p["bead_diameter"])
        self._sigma_um = p["bead_diameter"] / UM
        box_r = p["box_length"] / p["bead_diameter"]
        depth_r = p["chamber_depth"] / p["bead_diameter"]
        N = int(round(p["n_particles"]))
        sim = hoomd.Simulation(device=self.device or hoomd.device.CPU(), seed=self.seed % 65536)
        snap = hoomd.Snapshot()
        if snap.communicator.rank == 0:
            snap.configuration.box = [box_r, box_r, depth_r, 0, 0, 0]
            snap.particles.N = N
            snap.particles.types = ["tracer"]
            snap.particles.position[:] = 0.0
        sim.create_state_from_snapshot(snap)
        brownian = hoomd.md.methods.Brownian(filter=hoomd.filter.All(), kT=1.0)
        brownian.gamma["tracer"] = 1.0
        # No pair potential: bd_overdamped declares non-interacting tracers.
        sim.operations.integrator = hoomd.md.Integrator(
            dt=self.units.time_in(p["integration_timestep"]), methods=[brownian])
        self._sim = sim
        self._N = N
        self._box_r = box_r
        self._depth_r = depth_r

    def _place(self, rng, N, box_um, depth_um):
        pos = rng.uniform(-0.5, 0.5, (N, 3)) * np.array([self._box_r, self._box_r, self._depth_r])
        with self._sim.state.cpu_local_snapshot as s:
            tags = np.asarray(s.particles.tag)
            s.particles.position[:] = pos[tags]
            s.particles.image[:] = 0

    def _xy_um(self):
        with self._sim.state.cpu_local_snapshot as s:
            xy = rows_in_tag_order(s.particles.tag, s.particles.position, self._N)
        return xy * self._sigma_um

    def _advance(self):
        self._sim.run(1)
