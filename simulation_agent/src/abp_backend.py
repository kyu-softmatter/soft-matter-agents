"""The active backend: interacting active Brownian particles in two dimensions, on HOOMD.

Same four-call interface as `hoomd_backend` and `mock_backend` (4.6.5) --
`preflight / apply / read / abort`, a handle that returns before the run
ends, the same five states -- and the same first responsibility: units. Cards
are in SI (D7); the engine works in reduced units derived from the plan's own
bath and particle, and the conversion lives here and nowhere else:

    length  sigma   = bead_diameter
    energy  epsilon = k_B * T
    time    tau     = sigma^2 / D_T,  D_T = k_B*T / (3*pi*eta*d)

so kT* = 1 and gamma* = 1 as for `bd_overdamped`. What the active model adds
enters as three more reduced numbers, each derived from a plan condition:

    D_R*      = rotational_diffusivity * tau
    v0*       = peclet_number_steric * D_R*           (v0 = Pe * d * D_R, the steric convention)
    eps_wca*  = wca_epsilon / (k_B * T)

**Rotation is the integrator's, not an updater's.** HOOMD's Brownian method
diffuses the orientation with D_r = kT/gamma_r, so gamma_r = 1/D_R* gives the
declared D_R exactly: measured on 2026-09-23 as a spread of 0.638 rad against
the expected 0.632 over two persistence-time-tenths. The alternative --
`Active.create_diffusion_updater` -- adds its own noise ON TOP of the
integrator's unless gamma_r is made huge, and the first trial did exactly
that and measured 1.4 rad. One source of rotational noise, and the integrator
is it.

**Particles start on a square lattice**, not at random: at the plan's packing
fractions a random placement overlaps, and a WCA overlap is a force of
hundreds of kT per sigma that the first step turns into a particle leaving
the box. Orientations start uniformly random in the plane.

**The active force is the self-propulsion.** F* = gamma* v0* = v0* along the
particle's orientation; `Active.active_force` is the body-frame vector and
the orientation quaternion rotates it. Torque zero.

**Two dimensions.** The box has L_z = 0, which is how HOOMD 4+ declares a 2D
system (the `dimensions` attribute is read-only and inferred). Frames are
kept as (N, 3) with z = 0 so `trajectory.write` is unchanged; the estimator
reads the first two columns. Orientations are kept per frame as angles, for
the persistence time, and are not written to the GSD file yet (the writer
holds positions only; raising that is a separate change).

**It holds no policy.** The step, the box, the record and the windows are the
plan's; whether the run may proceed is the operator's. Reporting a stiffness
that the step cannot resolve is A1's job before the run and the divergence
monitor's during it, not this file's.

**Measured before it was written down.** The trials that fixed the rotation
scheme and the lattice also timed the engine: about 3.5e6 particle-steps per
second at a thousand particles and phi = 0.1 on this workstation's CPU,
against A5's assumed 1e7 -- same decade, a factor three slower. And at
dt* = 1e-3 with Pe 30 a thousand-particle run blew up after 1700 steps at a
pair distance of 0.9 sigma, where the WCA stiffness is some forty times the
value at the minimum; at dt* = 1e-4 it did not. The plan's step is 1.8e-5
tau. That is the A1 caveat -- activity drives overlaps deeper than the
minimum -- seen once in the engine.
"""

from __future__ import annotations

import threading

import numpy as np

from . import estimator_abp
from . import hoomd_backend
from . import physics

NAME = "abp_backend"
# The physics this backend builds is two-dimensional: the box it creates has
# L_z = 0, which is how HOOMD declares a 2D system, and the estimator is told
# so explicitly rather than reading a module constant of its own.
DIMENSIONS = 2

SUBMITTED, RUNNING, COMPLETE, ABORTED, FAILED = hoomd_backend.SUBMITTED, hoomd_backend.RUNNING, hoomd_backend.COMPLETE, hoomd_backend.ABORTED, hoomd_backend.FAILED
TERMINAL = hoomd_backend.TERMINAL

REQUIRED = (
    "box_length", "packing_fraction", "bead_diameter", "temperature", "viscosity",
    "rotational_diffusivity", "peclet_number_steric", "wca_epsilon",
    "integration_timestep", "save_interval", "total_simulated_time",
    "max_lag_time", "fit_lag_range_lower_bound",
)

WCA_CUTOFF = 2.0 ** (1.0 / 6.0)
NLIST_BUFFER = 0.4


def particle_count(params: dict) -> int:
    """N from the held packing fraction and the arm's box: phi = N*pi*d^2/(4*L^2)."""
    d, L, phi = float(params["bead_diameter"]), float(params["box_length"]), float(params["packing_fraction"])
    return int(round(4.0 * phi * L * L / (np.pi * d * d)))


def to_engine(params: dict) -> dict:
    units = hoomd_backend.Reduced(params["temperature"], params["viscosity"], params["bead_diameter"])
    d_r = float(params["rotational_diffusivity"]) * units.time
    v0 = float(params["peclet_number_steric"]) * d_r                      # Pe = v0/(d*D_R); sigma = d = 1
    return {
        "n_particles": particle_count(params),
        "box_length": units.length_in(params["box_length"]),
        "integration_timestep": units.time_in(params["integration_timestep"]),
        "save_interval": units.time_in(params["save_interval"]),
        "total_simulated_time": units.time_in(params["total_simulated_time"]),
        "kT": 1.0,
        "gamma": 1.0,
        "gamma_r": 1.0 / d_r,
        "rotational_diffusivity": d_r,
        "self_propulsion_speed": v0,
        "active_force": v0,                                                # gamma* = 1
        "wca_epsilon": float(params["wca_epsilon"]) / units.energy,
        "wca_sigma": 1.0,
        "wca_r_cut": WCA_CUTOFF,
        "dimensions": DIMENSIONS,
    }


def preflight_report(params: dict, seed: int) -> dict:
    missing = [k for k in REQUIRED if k not in params]
    if missing:
        return {"backend": NAME, "missing_parameters": missing, "steps_per_frame": None,
                "frames_expected": None, "save_interval_divides_step": False, "seed": seed}
    steps_per_frame = round(params["save_interval"] / params["integration_timestep"])
    units = hoomd_backend.Reduced(params["temperature"], params["viscosity"], params["bead_diameter"])
    engine = to_engine(params)
    return {
        "backend": NAME,
        "missing_parameters": [],
        "steps_per_frame": steps_per_frame,
        "frames_expected": round(params["total_simulated_time"] / params["save_interval"]),
        "save_interval_divides_step": abs(steps_per_frame * params["integration_timestep"] - params["save_interval"]) < 1e-12,
        "diffusivity_si": units.diffusivity,
        "n_particles": engine["n_particles"],
        "self_propulsion_speed_si": engine["self_propulsion_speed"] * units.length / units.time,
        "persistence_length_si": engine["self_propulsion_speed"] / engine["rotational_diffusivity"] * units.length,
        "seed": seed,
        "reduced_units": units.describe(),
        "engine_parameters": engine,
        "note": (
            "N is derived from the packing fraction and the box, so the plan's compare arms differ "
            "in box_length alone. D_T is derived from the bath by Stokes-Einstein, as for bd_overdamped; "
            "the plan's translational_diffusivity condition is the same relation rounded and is not "
            "handed to the engine. D_R and v0 are the plan's, through the steric Peclet number."
        ),
    }


class AbpBackend:
    NAME = NAME

    def __init__(self, seed: int = 0, engine=None, device=None) -> None:
        self.seed = int(seed)
        self.engine = engine if engine is not None else hoomd_backend._import_hoomd()
        self.device = device
        self.params: dict | None = None
        self.units: hoomd_backend.Reduced | None = None
        self.frames: list[np.ndarray] = []
        self.orientations: list[np.ndarray] = []
        self.frame_times: list[float] = []
        self.simulated_time = 0.0
        self.steps_taken = 0
        self.aborted: str | None = None
        self.state = None
        self.failure: str | None = None
        self.handle: str | None = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # -- the fixed interface ------------------------------------------------ #

    def preflight(self, params: dict) -> dict:
        report = preflight_report(params, self.seed)
        report["engine_build"] = hoomd_backend.engine_build(self.engine)
        return report

    def apply(self, params: dict) -> dict:
        if self._worker is not None:
            raise RuntimeError("this backend has already been given a run")
        report = self.preflight(params)
        if report["missing_parameters"]:
            raise ValueError(f"missing {report['missing_parameters']}")
        self.params = dict(params)
        self.units = hoomd_backend.Reduced(params["temperature"], params["viscosity"], params["bead_diameter"])
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
            last = self.frames[-1] - self.frames[-2] if len(self.frames) > 1 else np.zeros(1)
            return {
                "state": self.state, "initialised": True, "handle": self.handle,
                "steps_taken": self.steps_taken, "simulated_time": self.simulated_time,
                "frames_saved": len(self.frames),
                "max_single_step_displacement": float(np.abs(last).max()),
                "max_absolute_coordinate": float(np.abs(self.frames[-1]).max()) if self.frames else 0.0,
                "failure": self.failure,
            }

    def abort(self, reason: str) -> dict:
        self.aborted = reason
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=30)
        with self._lock:
            if self.state not in TERMINAL:
                self.state = ABORTED
            return {"aborted": True, "reason": reason, "state": self.state, "steps_taken": self.steps_taken}

    # -- the run -------------------------------------------------------------- #

    def _integrate(self) -> None:
        try:
            report = self.preflight(self.params)
            per_frame = int(report["steps_per_frame"]); frames = int(report["frames_expected"])
            p = report["engine_parameters"]; dt_si = float(self.params["integration_timestep"])
            sim = self._start_engine(p)
            with self._lock:
                pos, theta = self._snapshot(sim, p["box_length"])
                self.frames, self.orientations, self.frame_times = [pos], [theta], [0.0]
                self.state = RUNNING
            for _ in range(frames):
                if self._stop.is_set():
                    with self._lock:
                        self.state = ABORTED
                    return
                sim.run(per_frame)
                pos, theta = self._snapshot(sim, p["box_length"])
                with self._lock:
                    self.steps_taken += per_frame
                    self.simulated_time = self.steps_taken * dt_si       # derived, never accumulated
                    self.frames.append(pos); self.orientations.append(theta)
                    self.frame_times.append(self.simulated_time)
            with self._lock:
                self.state = COMPLETE
        except Exception as exc:                                          # noqa: BLE001
            with self._lock:
                self.failure = f"{type(exc).__name__}: {exc}"
                self.state = FAILED

    def _start_engine(self, p: dict):
        hoomd = self.engine
        device = self.device or hoomd.device.CPU()
        sim = hoomd.Simulation(device=device, seed=self.seed)
        n, L = int(p["n_particles"]), float(p["box_length"])
        snapshot = hoomd.Snapshot()
        if snapshot.communicator.rank == 0:
            snapshot.configuration.box = [L, L, 0.0, 0.0, 0.0, 0.0]          # L_z = 0 declares 2D
            snapshot.particles.N = n
            snapshot.particles.types = ["active"]
            m = int(np.ceil(np.sqrt(n)))
            xs = (np.arange(m) + 0.5) * L / m - L / 2
            lattice = np.array([[x, y, 0.0] for x in xs for y in xs])[:n]
            snapshot.particles.position[:] = lattice
            rng = np.random.default_rng(self.seed)
            theta = rng.uniform(0.0, 2.0 * np.pi, n)
            quat = np.zeros((n, 4)); quat[:, 0] = np.cos(theta / 2); quat[:, 3] = np.sin(theta / 2)
            snapshot.particles.orientation[:] = quat
            snapshot.particles.moment_inertia[:] = [0.0, 0.0, 1.0]
        sim.create_state_from_snapshot(snapshot)

        nlist = hoomd.md.nlist.Cell(buffer=NLIST_BUFFER)
        wca = hoomd.md.pair.LJ(nlist=nlist, default_r_cut=p["wca_r_cut"], mode="shift")
        wca.params[("active", "active")] = {"sigma": p["wca_sigma"], "epsilon": p["wca_epsilon"]}
        active = hoomd.md.force.Active(filter=hoomd.filter.All())
        active.active_force["active"] = (p["active_force"], 0.0, 0.0)
        active.active_torque["active"] = (0.0, 0.0, 0.0)
        brownian = hoomd.md.methods.Brownian(
            filter=hoomd.filter.All(), kT=p["kT"], default_gamma=p["gamma"],
            default_gamma_r=(p["gamma_r"], p["gamma_r"], p["gamma_r"]),
        )
        sim.operations.integrator = hoomd.md.Integrator(
            dt=p["integration_timestep"], methods=[brownian], forces=[wca, active],
            integrate_rotational_dof=True,
        )
        return sim

    def _snapshot(self, sim, box_reduced: float) -> tuple[np.ndarray, np.ndarray]:
        """Unwrapped positions in SI metres as (N, 3) with z = 0, and in-plane angles."""
        snap = sim.state.get_snapshot()
        position = np.asarray(snap.particles.position, dtype=float)
        image = np.asarray(snap.particles.image, dtype=float)
        unwrapped = position + image * np.array([box_reduced, box_reduced, 0.0])
        unwrapped[:, 2] = 0.0
        quat = np.asarray(snap.particles.orientation, dtype=float)
        theta = 2.0 * np.arctan2(quat[:, 3], quat[:, 0])
        return unwrapped * self.units.length, theta

    # -- estimation, delegated ------------------------------------------------ #

    def estimator(self) -> estimator_abp.ActiveEstimator:
        return estimator_abp.ActiveEstimator(self.frame_times, self.frames, self.orientations, dimensions=DIMENSIONS)

    def _lower(self) -> float:
        return float(self.params["fit_lag_range_lower_bound"])

    def mean_squared_displacement(self, max_lag_time: float, tracers=None):
        return self.estimator().mean_squared_displacement(max_lag_time, tracers=tracers)

    def fit_diffusivity(self, max_lag_time: float) -> dict:
        """The operator's name for the fitted number; here it is the EFFECTIVE
        translational diffusivity over lags above the plan's lower bound, and
        the dict says so in `quantity`."""
        return self.estimator().fit_effective_diffusivity(self._lower(), max_lag_time)

    def block_uncertainty(self, max_lag_time: float) -> dict:
        return self.estimator().block_uncertainty(self._lower(), max_lag_time)

    def window_halves(self, max_lag_time: float) -> dict:
        return self.estimator().window_halves(self._lower(), max_lag_time)

    def active_observables(self, max_lag_time: float) -> dict:
        """The rest of the registered family, for the run's observables.json."""
        est = self.estimator()
        return {
            "msd_loglog_slope": est.loglog_slope(max_lag_time),
            "orientation_autocorrelation": est.orientation_autocorrelation(max_lag_time),
            "persistence_time": est.fit_persistence_time(max_lag_time),
        }
