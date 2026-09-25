"""The pairwise backend: 2D overdamped Brownian dynamics with a repulsive
Yukawa pair potential, in NumPy, in SI throughout (`bd_pairwise`).

Same four-call interface as `mock_backend`, `hoomd_backend` and the others
(4.6.5) -- `preflight / apply / read / abort`, a handle that returns before
the run ends, the same five states. This is the FIRST-CLASS MOCK for the
configuration: the pipeline is verified on it before the engine attaches
(`pairwise_hoomd_backend`, not yet written). Its own file, not a branch in
`hoomd_backend.apply`, because three seats edit that file today.

    u(r)  = U0 (a/r) exp(-kappa (r - a)),  U0 = gamma k_B T,  kappa = kappa_a / a
    F(r)  = U0 a exp(-kappa (r - a)) (1/r^2 + kappa/r)   along r-hat, repulsive
    dx    = (D0 / k_B T) F dt + sqrt(2 D0 dt) xi,       D0 = k_B T / (3 pi eta d)

The box is Lx = rows_x * lattice_constant by Ly = rows_y * (sqrt(3)/2) *
lattice_constant, periodic, so a defect-free triangular lattice at the
plan's lattice constant fits it (A3's precondition); rows_y must be even.
The plan's `box_length` is Lx and preflight refuses if the two disagree.
Positions start uniformly at random. Frames are kept UNWRAPPED (task 021)
as (N, 2) arrays in metres; forces use the minimum image on folded copies.
Pairs inside the cutoff come from a periodic k-d tree (scipy), so the work
scales with the interacting pairs; adequate for the smoke run at 900
particles, and the engine is for the sweep.

The pair cutoff is where u/kT falls to one thousandth, capped at half the
shorter box edge, and is reported in preflight. At kappa a = 1 that is many
spacings: the potential is long-ranged there and the cutoff says so rather
than hiding it.

It holds no policy: step, box, record, windows are the plan's; whether the
run may proceed is the operator's.
"""

from __future__ import annotations

import math
import threading
import time

import numpy as np

from . import estimator_psi6, physics
from .mock_backend import SUBMITTED, RUNNING, COMPLETE, ABORTED, FAILED, TERMINAL

NAME = "pairwise_backend"
DIMENSIONS = 2
REQUIRED = ("n_particles", "rows_x", "rows_y", "lattice_constant", "gamma", "kappa_a", "mean_spacing",
            "temperature", "viscosity", "bead_diameter", "integration_timestep", "save_interval",
            "total_simulated_time", "box_length")
CUTOFF_U_OVER_KT = 1e-3


def geometry(params: dict) -> dict:
    a_lat = float(params["lattice_constant"])
    lx = int(round(params["rows_x"])) * a_lat
    ly = int(round(params["rows_y"])) * (math.sqrt(3) / 2) * a_lat
    kT = physics.K_B * float(params["temperature"])
    d0 = physics.stokes_einstein(params["temperature"], params["viscosity"], params["bead_diameter"])
    a = float(params["mean_spacing"])
    u0 = float(params["gamma"]) * kT
    kappa = float(params["kappa_a"]) / a
    # u(r)/kT = gamma (a/r) exp(-kappa (r-a)) = 1e-3, solved by bisection on [a, 100 a]
    lo, hi = a, 100 * a
    f = lambda r: float(params["gamma"]) * (a / r) * math.exp(-kappa * (r - a)) - CUTOFF_U_OVER_KT
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        (lo, hi) = (mid, hi) if f(mid) > 0 else (lo, mid)
    r_cut = min(hi, 0.5 * min(lx, ly))
    return {"lx": lx, "ly": ly, "kT": kT, "d0": d0, "u0": u0, "kappa": kappa, "a": a, "r_cut": r_cut,
            "r_cut_over_spacing": r_cut / a, "cutoff_capped_by_box": hi > 0.5 * min(lx, ly)}


def preflight_report(params: dict, seed: int) -> dict:
    missing = [k for k in REQUIRED if k not in params]
    if missing:
        return {"backend": NAME, "missing_parameters": missing, "steps_per_frame": None,
                "frames_expected": None, "save_interval_divides_step": False, "seed": seed}
    g = geometry(params)
    steps_per_frame = round(params["save_interval"] / params["integration_timestep"])
    report = {
        "backend": NAME, "missing_parameters": [],
        "steps_per_frame": steps_per_frame,
        "frames_expected": round(params["total_simulated_time"] / params["save_interval"]),
        "save_interval_divides_step": abs(steps_per_frame * params["integration_timestep"] - params["save_interval"]) < 1e-12,
        "seed": seed, "dimensions": DIMENSIONS,
        "box_si": {"lx": g["lx"], "ly": g["ly"]},
        "box_length_matches_rows": abs(g["lx"] - float(params["box_length"])) <= 1e-9 * max(1.0, g["lx"]),
        "rows_y_even": int(round(params["rows_y"])) % 2 == 0,
        "n_particles_matches_rows": int(params["n_particles"]) == int(round(params["rows_x"])) * int(round(params["rows_y"])),
        "diffusivity_si": g["d0"], "contact_energy_si": g["u0"], "kappa_si": g["kappa"],
        "cutoff_si": g["r_cut"], "cutoff_over_spacing": g["r_cut_over_spacing"], "cutoff_capped_by_box": g["cutoff_capped_by_box"],
        "engine_build": {"engine": NAME, "version": "numpy " + np.__version__},
        "note": ("SI throughout, no reduced units. Positions unwrapped; psi6 folds them at read time. "
                 "All pairs evaluated with the minimum image: adequate for a smoke run, not for the sweep"),
    }
    if not report["box_length_matches_rows"]:
        report["missing_parameters"] = ["box_length (does not equal rows_x * lattice_constant)"]
    if not report["rows_y_even"]:
        report["missing_parameters"].append("rows_y (must be even for a periodic triangular lattice)")
    if not report["n_particles_matches_rows"]:
        report["missing_parameters"].append("n_particles (must equal rows_x * rows_y)")
    return report


class PairwiseBackend:
    NAME = NAME
    DIMENSIONS = DIMENSIONS

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.params: dict | None = None
        self.frames: list[np.ndarray] = []
        self.frame_times: list[float] = []
        self.simulated_time = 0.0
        self.steps_taken = 0
        self.last_step_displacement = 0.0
        self.max_step_displacement = 0.0
        self.state = None
        self.handle = None
        self.failure = None
        self.aborted = None
        self.integration_wall_s = 0.0
        self.frame_readout_wall_s = 0.0
        self._geom: dict | None = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def preflight(self, params: dict) -> dict:
        return preflight_report(params, self.seed)

    def apply(self, params: dict) -> dict:
        if self._worker is not None:
            raise RuntimeError("this backend has already been given a run")
        report = self.preflight(params)
        if report["missing_parameters"]:
            raise ValueError(f"missing {report['missing_parameters']}")
        self.params = dict(params)
        self._geom = geometry(params)
        self.N_PARTICLES = int(params["n_particles"])
        self.state = SUBMITTED
        self.handle = f"{NAME}:{self.seed}:{id(self):x}"
        self._worker = threading.Thread(target=self._integrate, name=self.handle, daemon=True)
        submitted_as = self.state
        self._worker.start()
        return {"handle": self.handle, "state": submitted_as}

    def read(self) -> dict:
        with self._lock:
            if self.state is None:
                return {"state": None, "initialised": False}
            return {
                "state": self.state, "initialised": True, "handle": self.handle,
                "steps_taken": self.steps_taken, "simulated_time": self.simulated_time,
                "frames_saved": len(self.frames),
                "max_single_step_displacement": float(self.last_step_displacement),
                "max_absolute_coordinate": float(np.abs(self.frames[-1]).max()) if self.frames else 0.0,
                "failure": self.failure,
                "integration_wall_s": self.integration_wall_s,
                "frame_readout_wall_s": self.frame_readout_wall_s,
            }

    def abort(self, reason: str) -> dict:
        self.aborted = reason
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=60)
        with self._lock:
            if self.state not in TERMINAL:
                self.state = ABORTED
            return {"aborted": True, "reason": reason, "state": self.state, "steps_taken": self.steps_taken}

    # -- the run ------------------------------------------------------------

    def _forces(self, pos: np.ndarray) -> np.ndarray:
        """Pair forces within the cutoff, minimum image, via a periodic k-d tree.

        scipy's cKDTree takes `boxsize` and returns every pair closer than the
        cutoff under the periodic metric, so the work is proportional to the
        number of interacting pairs rather than to N^2. Positions are folded
        into [0, L) for the tree only; the integrator keeps them unwrapped.
        """
        from scipy.spatial import cKDTree

        g = self._geom
        box = np.array([g["lx"], g["ly"]])
        folded = np.mod(pos, box)
        folded = np.where(folded >= box, 0.0, folded)          # a fold can land exactly on L
        pairs = cKDTree(folded, boxsize=box).query_pairs(g["r_cut"], output_type="ndarray")
        forces = np.zeros_like(pos)
        if len(pairs) == 0:
            return forces
        i, j = pairs[:, 0], pairs[:, 1]
        d = folded[i] - folded[j]
        d -= box * np.round(d / box)
        r = np.sqrt((d ** 2).sum(-1))
        mag = g["u0"] * g["a"] * np.exp(-g["kappa"] * (r - g["a"])) * (1.0 / r ** 2 + g["kappa"] / r)
        f = (mag / r)[:, None] * d                               # on i, away from j
        np.add.at(forces, i, f)
        np.add.at(forces, j, -f)
        return forces

    def _integrate(self) -> None:
        try:
            p, g = self.params, self._geom
            dt = float(p["integration_timestep"])
            per_frame = round(p["save_interval"] / dt)
            frames = round(p["total_simulated_time"] / p["save_interval"])
            n = int(p["n_particles"])
            box = np.array([g["lx"], g["ly"]])
            pos = self.rng.uniform(0.0, 1.0, size=(n, 2)) * box
            mobility_dt = g["d0"] / g["kT"] * dt
            noise = math.sqrt(2.0 * g["d0"] * dt)
            with self._lock:
                self.frames = [pos.copy()]
                self.frame_times = [0.0]
                self.state = RUNNING
            for _ in range(frames):
                if self._stop.is_set():
                    with self._lock:
                        self.state = ABORTED
                    return
                t0 = time.perf_counter()
                for _ in range(per_frame):
                    step = mobility_dt * self._forces(pos) + noise * self.rng.standard_normal((n, 2))
                    pos = pos + step
                self.integration_wall_s += time.perf_counter() - t0
                t1 = time.perf_counter()
                last = float(np.sqrt((step ** 2).sum(-1)).max())
                snapshot = pos.copy()
                self.frame_readout_wall_s += time.perf_counter() - t1
                with self._lock:
                    self.steps_taken += per_frame
                    self.simulated_time = self.steps_taken * dt      # derived from the integer count, never summed
                    self.frames.append(snapshot)
                    self.frame_times.append(self.simulated_time)
                    self.last_step_displacement = last
                    self.max_step_displacement = max(self.max_step_displacement, last)
                    if not np.all(np.isfinite(pos)):
                        self.state = FAILED
                        self.failure = "non-finite position"
                        return
            with self._lock:
                self.state = COMPLETE
        except Exception as exc:  # the record must say why, not die silently
            with self._lock:
                self.state = FAILED
                self.failure = f"{type(exc).__name__}: {exc}"

    # -- what the run read ----------------------------------------------------

    def observables(self, params: dict) -> dict:
        g = self._geom
        box = np.array([g["lx"], g["ly"]])
        local, glob = estimator_psi6.psi6_curve(self.frames, box)
        reading = estimator_psi6.relaxation_time(np.asarray(self.frame_times), local,
                                                 float(params["relaxation_fit_window"]), float(params["plateau_fraction"]))
        return {
            "window_parameter": "relaxation_fit_window",
            "window_si": float(params["relaxation_fit_window"]),
            "plateau_fraction": float(params["plateau_fraction"]),
            "psi6_definition": "mean over particles of |psi6_j|, Voronoi neighbours from a Delaunay triangulation of folded positions with periodic images",
            "psi6_curve": {"time_si": [float(t) for t in self.frame_times], "psi6_local_mean": local.tolist(), "psi6_global": glob.tolist()},
            "relaxation": reading,
            "box_si": {"lx": g["lx"], "ly": g["ly"]},
            "cutoff_si": g["r_cut"],
            "positions_convention": "unwrapped in the trajectory; folded into the box for psi6",
            "max_single_step_displacement_si": float(self.max_step_displacement),
        }
