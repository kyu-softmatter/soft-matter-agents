"""The Gaussian double well on HOOMD: an ensemble of independent walkers in two dimensions.

For `bd_overdamped_gaussian_double_well_2d`. The potential, the reduced units
and the estimator are `double_well`'s, shared with the NumPy reference, so
whatever differs between the two runs of one point is the engine and nothing
else (4.6.5).

**The engine form.** HOOMD 7.2 CPU, a 2-D box, `hoomd.md.methods.Brownian`
(Euler-Maruyama) with kT* = gamma* = 1, and the two wells as an
`hoomd.md.force.Custom`. The walkers carry no pair force, so they need no
spacing: every walker sits in the same two wells and one run is an ensemble of
independent single-particle records. The box only has to be wide enough that
no walker wraps, and it is 60 w_1 plus the separation, against a well that is
zero beyond a few widths.

**Positions are read back sorted by tag.** The CPU local snapshot is not in tag
order, and reading it unsorted scrambles walkers between frames -- a
1000-walker run read widths 200 times too large before that was fixed (the
manager's scratch, 2026-09-24). The force needs no sorting: it is computed per
local index from the same local index's position.
"""

from __future__ import annotations

import math
import threading
import time

import numpy as np

from . import double_well as dw
from . import hoomd_backend
from .mock_backend import ABORTED, COMPLETE, FAILED, RUNNING, SUBMITTED, TERMINAL

NAME = "double_well_hoomd_backend"
DIMENSIONS = 2

# The plan's parameters, in SI. `walkers` is the ensemble size: independent
# single-bead records in one engine run, not interacting particles.
REQUIRED = (
    "integration_timestep", "save_interval", "record_length", "startup_discard",
    "temperature", "viscosity", "bead_diameter",
    "trap_stiffness_1", "trap_stiffness_2", "trap_width_1", "trap_width_2", "barrier_target",
    "walkers", "milestone_core_fraction", "box_length",
)


def to_reduced(p: dict) -> dict:
    """SI -> reduced: length w_1, energy kT, time w_1^2/D. Converted here and nowhere else."""
    kT = dw.K_B * float(p["temperature"])
    w1, w2 = float(p["trap_width_1"]), float(p["trap_width_2"])
    sc = dw.si_scales(float(p["temperature"]), float(p["viscosity"]), float(p["bead_diameter"]), w1)
    eps1 = float(p["trap_stiffness_1"]) * w1 ** 2 / kT
    # `depth_difference`, in kT, lowers well 2 below what its stiffness gives. It is how
    # the plan states an asymmetry: one kT at 250 kT deep is a 0.4 per cent stiffness
    # trim, which no explore-mode stiffness can write and no calibration resolves, so
    # the bench makes it by watching the occupancy and the plan names the kT.
    eps2 = float(p["trap_stiffness_2"]) * w2 ** 2 / kT - float(p.get("depth_difference", 0.0))
    # The separation is SOLVED from the barrier, never taken from the plan: the barrier
    # moves by kT per few nm near merging, so a separation written to one figure would
    # be a different experiment. Kept in full precision here and reported, in SI.
    d = dw.separation_for_barrier(eps1, eps2, float(p["barrier_target"]), w2 / w1)
    return {
        "eps1": eps1, "eps2": eps2,
        "trap_stiffness_2_effective": eps2 * kT / w2 ** 2,
        "w2": w2 / w1, "d": d, "separation_si": d * w1,
        "dt": float(p["integration_timestep"]) / sc["time_s"],
        "scales": sc,
    }


def estimate_si(x_si: np.ndarray, frame_interval_s: float, core_fraction: float,
                split_si: float = 0.0) -> dict:
    """The estimator as the experiment applies it, on the projected record in SI.

    Cores sit around the two histogram peaks of the record ITSELF -- one each side of
    `split_si`, the midpoint between the trap centres -- with radius `core_fraction`
    of the peak spacing. Near merging the minima sit far inside the trap centres
    (+-0.67 w against +-1.08 w at the stiff point), so cores on the centres would
    miss the wells; the peaks are what a bench histogram shows. Returns per-record
    estimates and the peaks used.
    """
    x = np.asarray(x_si, dtype=float)
    pooled = x.ravel()
    h, e = np.histogram(pooled, bins=400)
    mid = 0.5 * (e[1:] + e[:-1])
    left, right = mid < split_si, mid >= split_si
    c1 = float(mid[left][np.argmax(h[left])])
    c2 = float(mid[right][np.argmax(h[right])])
    R = core_fraction * (c2 - c1)
    est = dw.estimate(x, frame_interval_s, c1, c2, R)
    return {"peaks_si": [c1, c2], "core_radius_si": R, "records": est if isinstance(est, list) else [est]}


def _wells_force_class(hoomd, wells: dw.Wells):
    class GaussianWells(hoomd.md.force.Custom):
        def set_forces(self, timestep):
            with self._state.cpu_local_snapshot as snap, self.cpu_local_force_arrays as arrays:
                p = snap.particles.position
                fx, fy = wells.force(p[:, 0], p[:, 1])
                arrays.force[:, 0] = fx
                arrays.force[:, 1] = fy
                arrays.force[:, 2] = 0.0
                arrays.potential_energy[:] = wells.energy(p[:, 0], p[:, 1])
    return GaussianWells()


def integrate_hoomd(wells: dw.Wells, walkers: int, t_total: float, dt: float, save_every: int,
                    burn_in: float, seed: int, engine=None,
                    tracker: dw.DiskTracker | None = None) -> tuple[np.ndarray, dict]:
    """HOOMD in reduced units. Returns (x(t) as (frames, walkers) sorted by tag, timing).

    Same start as `double_well.integrate_numpy`: even tags at centre 1, odd at centre 2.
    """
    hoomd = engine if engine is not None else hoomd_backend._import_hoomd()
    sim = hoomd.Simulation(device=hoomd.device.CPU(), seed=int(seed) % 65536)
    L = 60.0 * max(wells.w1, wells.w2) + wells.d
    snap = hoomd.Snapshot()
    snap.configuration.box = [L, L, 0.0, 0.0, 0.0, 0.0]
    snap.particles.N = walkers
    snap.particles.types = ["walker"]
    pos = np.zeros((walkers, 3))
    pos[:, 0] = np.where(np.arange(walkers) % 2 == 0, wells.c1, wells.c2)
    snap.particles.position[:] = pos
    sim.create_state_from_snapshot(snap)
    brownian = hoomd.md.methods.Brownian(filter=hoomd.filter.All(), kT=1.0, default_gamma=1.0)
    sim.operations.integrator = hoomd.md.Integrator(dt=dt, methods=[brownian],
                                                    forces=[_wells_force_class(hoomd, wells)])
    t0 = time.perf_counter()
    burn_steps = int(round(burn_in / dt))
    if burn_steps:
        sim.run(burn_steps)
    n_frames = int(round(t_total / dt)) // save_every + 1
    out = np.empty((n_frames, walkers))
    stepping = readout = 0.0

    def read():
        with sim.state.cpu_local_snapshot as s:
            order = np.argsort(s.particles.tag)
            x = np.array(s.particles.position[order, 0], dtype=float)
            img = np.array(s.particles.image[order, 0], dtype=float)
        return x + img * L

    t1 = time.perf_counter()
    out[0] = read()
    readout += time.perf_counter() - t1
    def step_tracked(n):
        for _ in range(n):
            sim.run(1)
            with sim.state.cpu_local_snapshot as s:
                order = np.argsort(s.particles.tag)
                p = np.array(s.particles.position[order, :2], dtype=float)
            tracker.update(p[:, 0], p[:, 1])

    for f in range(1, n_frames):
        a = time.perf_counter()
        if tracker is None:
            sim.run(save_every)
        else:
            step_tracked(save_every)
        b = time.perf_counter()
        out[f] = read()
        stepping += b - a; readout += time.perf_counter() - b
    timing = {"wall_s": time.perf_counter() - t0, "stepping_s": stepping, "readout_s": readout,
              "walker_steps": walkers * (burn_steps + (n_frames - 1) * save_every), "frames": n_frames,
              "engine": {"hoomd": hoomd.version.version, "gpu": bool(hoomd.version.gpu_enabled),
                         "scheme": "hoomd.md.methods.Brownian (Euler-Maruyama)",
                         "wells": "hoomd.md.force.Custom"}}
    return out, timing


def _build(hoomd, wells: dw.Wells, walkers: int, dt: float, seed: int):
    """The engine state: a 2-D box, walkers split between the two centres, Brownian + wells."""
    sim = hoomd.Simulation(device=hoomd.device.CPU(), seed=int(seed) % 65536)
    L = 60.0 * max(wells.w1, wells.w2) + wells.d
    snap = hoomd.Snapshot()
    snap.configuration.box = [L, L, 0.0, 0.0, 0.0, 0.0]
    snap.particles.N = walkers
    snap.particles.types = ["walker"]
    pos = np.zeros((walkers, 3))
    pos[:, 0] = np.where(np.arange(walkers) % 2 == 0, wells.c1, wells.c2)
    snap.particles.position[:] = pos
    sim.create_state_from_snapshot(snap)
    brownian = hoomd.md.methods.Brownian(filter=hoomd.filter.All(), kT=1.0, default_gamma=1.0)
    sim.operations.integrator = hoomd.md.Integrator(dt=dt, methods=[brownian],
                                                    forces=[_wells_force_class(hoomd, wells)])
    return sim, L


class DoubleWellHoomdBackend:
    """The operator's four calls for `bd_overdamped_gaussian_double_well_2d`, on HOOMD.

    Frames are (walkers, 2) in SI metres, x along the joining line with the midpoint
    between the traps at 0 and trap 1 at negative x. The start-up discard is part of
    the record the operator writes -- every frame from t = 0 -- and the estimator
    drops it, so what was discarded stays on disk.
    """

    NAME = NAME
    DIMENSIONS = DIMENSIONS

    def __init__(self, seed: int = 0, engine=None) -> None:
        # EngineMissing at construction, before the operator opens a run directory.
        self.engine = engine if engine is not None else hoomd_backend._import_hoomd()
        self.seed = seed
        self.params: dict | None = None
        self.frames: list[np.ndarray] = []
        self.frame_times: list[float] = []
        self.steps_taken = 0
        self.steps_planned: int | None = None
        self.simulated_time = 0.0
        self.state = None
        self.failure: str | None = None
        self.handle: str | None = None
        self.stepping_wall_s = self.frame_readout_wall_s = self.loop_wall_s = None
        self.integration_wall_s = None
        self.largest_single_step: float | None = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    @property
    def N_PARTICLES(self) -> int:           # noqa: N802 -- the operator reads this name
        return int(self.params["walkers"]) if self.params else 0

    def engine_build(self) -> dict:
        v = self.engine.version
        return {"engine": "hoomd", "version": v.version, "gpu": bool(v.gpu_enabled),
                "precision": list(v.floating_point_precision),
                "scheme": "hoomd.md.methods.Brownian (Euler-Maruyama)", "dimensions": 2,
                "wells": "hoomd.md.force.Custom, two additive Gaussians",
                "readout": "local snapshot sorted by tag"}

    def preflight(self, params: dict) -> dict:
        missing = [k for k in REQUIRED if k not in params]
        out = {"backend": NAME, "engine_build": self.engine_build(), "missing_parameters": missing,
               "seed": self.seed}
        if missing:
            out.update(steps_per_frame=None, frames_expected=None, save_interval_divides_step=False)
            return out
        dt, save = float(params["integration_timestep"]), float(params["save_interval"])
        per_frame = round(save / dt)
        total = float(params["startup_discard"]) + float(params["record_length"])
        r = to_reduced(params)
        W = dw.Wells(r["eps1"], r["eps2"], r["d"], 1.0, r["w2"])
        L = W.landscape()
        out.update(
            steps_per_frame=per_frame, frames_expected=round(total / save),
            total_simulated_time_si=total,
            save_interval_divides_step=abs(per_frame * dt - save) < 1e-12 * max(1.0, save),
            n_particles=int(params["walkers"]),
            reduced_units={"length_si": r["scales"]["length_m"], "energy_si": r["scales"]["energy_J"],
                           "time_si": r["scales"]["time_s"],
                           "note": "length trap_width_1, energy k_B*T, time trap_width_1^2/D"},
            engine_parameters={"eps1_kT": r["eps1"], "eps2_kT": r["eps2"], "w2_over_w1": r["w2"],
                               "trap_stiffness_2_effective_N_per_m": r["trap_stiffness_2_effective"],
                               "d_over_w1": r["d"], "separation_m_solved_from_barrier": r["separation_si"],
                               "dt_reduced": r["dt"],
                               "dt_times_eps1": r["dt"] * r["eps1"]},
            landscape_computed={k: (v * r["scales"]["length_m"] if k.startswith("x") else v)
                                for k, v in L.items()},
            box_edge_reduced=60.0 * max(1.0, r["w2"]) + r["d"],
        )
        return out

    def apply(self, params: dict) -> dict:
        if self._worker is not None:
            raise RuntimeError("this backend has already been given a run")
        pre = self.preflight(params)
        if pre["missing_parameters"]:
            raise ValueError(f"missing {pre['missing_parameters']}")
        self.params = dict(params)
        self.state = SUBMITTED
        self.handle = f"{NAME}:{self.seed}:{id(self):x}"
        self._worker = threading.Thread(target=self._integrate, name=self.handle, daemon=True)
        self._worker.start()
        return {"handle": self.handle, "state": SUBMITTED}

    def _integrate(self) -> None:
        try:
            p = self.params
            pre = self.preflight(p)
            per_frame, frames = int(pre["steps_per_frame"]), int(pre["frames_expected"])
            r = to_reduced(p)
            wells = dw.Wells(r["eps1"], r["eps2"], r["d"], 1.0, r["w2"])
            sim, box = _build(self.engine, wells, int(p["walkers"]), r["dt"], self.seed)
            w1 = r["scales"]["length_m"]
            dt_si = float(p["integration_timestep"])

            def read():
                with sim.state.cpu_local_snapshot as s:
                    order = np.argsort(s.particles.tag)
                    xy = np.array(s.particles.position[order, :2], dtype=float)
                    img = np.array(s.particles.image[order, :2], dtype=float)
                return (xy + img * box) * w1

            with self._lock:
                self.steps_planned = per_frame * frames
                self.frames = [read()]
                self.frame_times = [0.0]
                self.state = RUNNING
            stepping = readout = 0.0
            largest = 0.0
            started = time.perf_counter()
            for _ in range(frames):
                if self._stop.is_set():
                    with self._lock:
                        self.state = ABORTED
                    return
                # the frame's last step alone, so the largest single-step displacement is measured
                if per_frame > 1:
                    t0 = time.perf_counter(); sim.run(per_frame - 1); t1 = time.perf_counter()
                    before = read(); stepping += t1 - t0; readout += time.perf_counter() - t1
                else:
                    before = self.frames[-1]
                t0 = time.perf_counter(); sim.run(1); t1 = time.perf_counter()
                x = read(); stepping += t1 - t0; readout += time.perf_counter() - t1
                largest = max(largest, float(np.abs(x - before).max()))
                with self._lock:
                    self.steps_taken += per_frame
                    self.simulated_time = self.steps_taken * dt_si     # derived, never accumulated
                    self.frames.append(x)
                    self.frame_times.append(self.simulated_time)
                    self.largest_single_step = largest
                    self.stepping_wall_s, self.frame_readout_wall_s = stepping, readout
            with self._lock:
                self.loop_wall_s = time.perf_counter() - started
                self.integration_wall_s = self.stepping_wall_s
                self.state = COMPLETE
        except Exception as exc:                       # noqa: BLE001
            with self._lock:
                self.failure = f"{type(exc).__name__}: {exc}"
                self.state = FAILED

    def read(self) -> dict:
        with self._lock:
            if self.state is None:
                return {"state": None, "initialised": False}
            last = self.frames[-1] if self.frames else np.zeros((1, 2))
            return {
                "state": self.state, "initialised": True, "handle": self.handle,
                "steps_taken": self.steps_taken, "simulated_time": self.simulated_time,
                "frames_saved": len(self.frames),
                "fraction_of_planned_steps": (self.steps_taken / self.steps_planned
                                              if self.steps_planned else 0.0),
                "max_single_step_displacement": float(self.largest_single_step or 0.0),
                "integration_wall_s": self.stepping_wall_s,
                "frame_readout_wall_s": self.frame_readout_wall_s,
                "frame_write_wall_s": None,
                "max_absolute_coordinate": float(np.abs(last).max()),
                "failure": self.failure,
            }

    def abort(self, reason: str) -> dict:
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=30)
        with self._lock:
            if self.state not in TERMINAL:
                self.state = ABORTED
            return {"aborted": True, "reason": reason, "state": self.state, "steps_taken": self.steps_taken}

    def observables(self, params: dict) -> dict:
        """The four registered observables, per record and over the ensemble, after the discard."""
        with self._lock:
            times = np.array(self.frame_times)
            frames = np.array(self.frames)                     # (frames, walkers, 2)
        keep = times >= float(params["startup_discard"]) - 1e-12 * max(1.0, float(params["startup_discard"]))
        x = frames[keep, :, 0]
        fi = float(params["save_interval"])
        e = estimate_si(x, fi, float(params["milestone_core_fraction"]))
        recs = [q for q in e["records"] if q is not None]

        def summary(key):
            v = np.array([q[key] for q in recs], dtype=float)
            v = v[np.isfinite(v)]
            if not len(v):
                return {"n_records": 0}
            return {"mean": float(v.mean()), "sd_over_records": float(v.std(ddof=1)) if len(v) > 1 else None,
                    "se_of_mean": float(v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 1 else None,
                    "p05": float(np.percentile(v, 5)), "p50": float(np.percentile(v, 50)),
                    "p95": float(np.percentile(v, 95)), "n_records": int(len(v))}

        r = to_reduced(params)
        L = dw.Wells(r["eps1"], r["eps2"], r["d"], 1.0, r["w2"]).landscape()
        steps = max(1, self.steps_taken)
        return {
            "window_parameter": "record_length",
            "window_si": float(params["record_length"]),
            "definition": {"projection": "x, the coordinate along the line joining the traps",
                           "cores": "around the two histogram peaks of the pooled record, one each side of "
                                    "the midpoint between the traps",
                           "core_radius_fraction_of_peak_spacing": float(params["milestone_core_fraction"]),
                           "frame_interval_s": fi,
                           "rate": "per ordered pair: transitions out of the origin well over the time "
                                   "assigned to the origin well (the registered estimator); the hop "
                                   "frequency is all transitions over the assigned record",
                           "residence": "mean completed dwell; the first and last dwell of a record are cut"},
            "peaks_si": e["peaks_si"], "core_radius_si": e["core_radius_si"],
            "well_occupancy": summary("occupancy_1"),
            "interwell_transition_rate": {"well_1_to_2": summary("rate_12"), "well_2_to_1": summary("rate_21"),
                                          "hop_frequency_both_directions": summary("rate"),
                                          "transitions_per_record": summary("transitions")},
            "well_residence_time": {"well_1": summary("residence_1"), "well_2": summary("residence_2")},
            "interwell_barrier_height": {
                "projected_free_energy_kT": dw._hist_barrier(x.ravel(), e["peaks_si"][0], e["peaks_si"][1], 120),
                "potential_computed_kT": None if L["merged"] else L["barrier_from_deeper"],
                "note": "the first is read off the pooled projected histogram and includes the transverse "
                        "entropy; the second is the potential's saddle minus the deeper minimum, computed"},
            "fraction_below_saddle": None if L["merged"] else float((x < L["x_saddle"] * r["scales"]["length_m"]).mean()),
            "cost": {"integration_wall_s": self.integration_wall_s, "steps": self.steps_taken,
                     "wall_s_per_step": (self.integration_wall_s / steps) if self.integration_wall_s else None,
                     "frame_readout_wall_s": self.frame_readout_wall_s, "frames_saved": len(frames),
                     "loop_wall_s": self.loop_wall_s, "n_particles": int(params["walkers"]), "backend": NAME},
        }
