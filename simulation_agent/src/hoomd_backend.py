"""The HOOMD backend -- the same interface, a different engine, and units.

`mock_backend` is a first-class backend and therefore the specification (4.6.5):
this file matches its shapes rather than a reading of what they should be. The
seam is already there -- `operator.run()` takes `backend=` -- so **nothing in
the operator changes** when a run comes here instead.

**What is verified and what is not, said plainly.** Everything that does not
touch the engine is exercised with no engine present: the parameter mapping,
the unit system in both directions, the state machine, the frame record, and
the estimator wiring. The ~20 lines that call HOOMD were **not executed
anywhere until 2026-09-22** -- HOOMD is conda-forge only and, until that
morning, no interpreter on this machine had it -- so they were written against
HOOMD-blue's documented API and the first real run was where they got checked.
That was `010`'s arrangement and not a shortcut: a machine with the validator
and the mock does all of M2's verification (9.2 rule 4). They have run since:
fourteen `log.json` files under `runs/` say `hoomd_backend` (counted on
2026-09-23, plus `-hoomd-s1`, which ran the engine under a mock label), and
the ten-seed sweep reproduces Stokes-Einstein to 0.04 per cent in the mean. How the engine gets onto another machine is `_import_hoomd()`'s
business below, and **which build answered** is `engine_build()`'s, recorded
in every run's preflight report.

**Units are this file's first responsibility** (5.7 rule 4, D7). Cards are
authoritative in physical units and the engine works in its own, so the
conversion lives at this boundary and nowhere else -- a plan does not become
invalid when the engine changes. The system is derived from the plan's own
parameters and recalled from nothing:

    length  sigma = bead_diameter
    energy  epsilon = k_B * T
    time    tau = sigma^2 / D,  D = k_B*T / (3*pi*eta*d)

which makes `kT* = 1`, `D* = 1` and therefore `gamma* = kT*/D* = 1`. Those
three being one is not a convenience: it is the statement that the engine is
given the bath and the particle and not the answer. The diffusivity that comes
back out is then a number the inputs did not hand it -- as far as an overdamped
free tracer allows, which 5.3 says is not far, and that is the configuration's
property rather than this file's.

**The estimator is not here.** `estimator.py` holds the fit the vocabulary
declares and both backends delegate to it, because two copies of one estimator
are two estimators and the weighting is the part that was measured into the
contract. By the time a trajectory reaches that module the difference between
this backend and the mock is gone, which is what makes the two comparable at
all.

**It holds no policy.** No limit, no judgement about whether a run may proceed,
no stopping itself. The envelope and the operator own all of that.

**And nothing here came from another repository.** 10.3: an integrator setting
recalled from elsewhere is `operator_recall:` E5 at best and has no place in a
module. Every number below is derived from the plan's parameters in this file,
in the open.
"""

from __future__ import annotations

import glob
import json
import os
import platform
import sys
import threading

import numpy as np

from . import estimator as estimator_module
from . import physics

NAME = "hoomd_backend"
DIMENSIONS = estimator_module.DIMENSIONS

# The same five states and the same terminal set as the mock, because the
# operator compares against these by name. SUBMITTED is the one that earns its
# place here rather than there: locally the mock is running before the first
# poll, and a queued engine job really can sit submitted for minutes.
SUBMITTED, RUNNING, COMPLETE, ABORTED, FAILED = (
    "submitted", "running", "complete", "aborted", "failed",
)
TERMINAL = (COMPLETE, ABORTED, FAILED)

REQUIRED = (
    "n_particles",
    "integration_timestep",
    "save_interval",
    "total_simulated_time",
    "box_length",
    "temperature",
    "viscosity",
    "bead_diameter",
)


class EngineMissing(RuntimeError):
    """HOOMD is not importable here.

    Raised at construction and not at `apply()`, so a run that cannot happen
    fails before the operator has recorded a gate, derived commands and opened
    a run directory. A backend that accepted a plan and then discovered it had
    no engine would leave a run record for a run that never started.
    """


# --------------------------------------------------------------------------- #
# units -- pure, and testable without an engine
# --------------------------------------------------------------------------- #


class Reduced:
    """The engine's unit system, derived from the plan's own parameters.

    Held as an object rather than a pair of functions because the conversion
    has to be the SAME one in both directions: a run converted in by one rule
    and out by another produces a trajectory in no unit system at all, and the
    error is a constant factor that looks like physics.
    """

    def __init__(self, temperature: float, viscosity: float, bead_diameter: float) -> None:
        self.diffusivity = physics.stokes_einstein(temperature, viscosity, bead_diameter)
        self.length = float(bead_diameter)                       # sigma
        self.energy = physics.K_B * float(temperature)           # epsilon = kT
        self.time = self.length ** 2 / self.diffusivity          # tau = sigma^2 / D

    def time_in(self, seconds: float) -> float:
        return float(seconds) / self.time

    def time_out(self, reduced: float) -> float:
        return float(reduced) * self.time

    def length_in(self, metres: float) -> float:
        return float(metres) / self.length

    def speed_in(self, metres_per_second: float) -> float:
        """A speed in SI -> the engine's. sigma/tau, with tau = sigma^2/D."""
        return float(metres_per_second) * self.time / self.length

    def rate_in(self, per_second: float) -> float:
        """A rate in SI -> the engine's. A rotational diffusivity is 1/time."""
        return float(per_second) * self.time

    def length_out(self, reduced) -> "np.ndarray | float":
        return np.asarray(reduced) * self.length if isinstance(reduced, np.ndarray) else float(reduced) * self.length

    def describe(self) -> dict:
        """What the conversion was, for the run record.

        A trajectory in reduced units with no record of the system it was
        reduced by cannot be read back, and the numbers here are derived from
        three plan parameters -- so this is the one place where a mistake in
        them is visible to a person rather than only to the physics.
        """
        return {
            "length_si": self.length,
            "energy_si": self.energy,
            "time_si": self.time,
            "diffusivity_si": self.diffusivity,
            "kT_reduced": 1.0,
            "gamma_reduced": 1.0,
            "note": (
                "sigma = bead_diameter, epsilon = k_B*T, tau = sigma^2/D with D from "
                "Stokes-Einstein. kT and gamma are then both 1, which is the statement that "
                "the engine is given the bath and the particle rather than the diffusivity"
            ),
        }


def to_engine(params: dict) -> dict:
    """Plan parameters in SI -> the engine's numbers. Pure and testable."""
    units = Reduced(params["temperature"], params["viscosity"], params["bead_diameter"])
    return {
        "n_particles": int(params["n_particles"]),
        "box_length": units.length_in(params["box_length"]),
        "integration_timestep": units.time_in(params["integration_timestep"]),
        "save_interval": units.time_in(params["save_interval"]),
        "total_simulated_time": units.time_in(params["total_simulated_time"]),
        "kT": 1.0,
        "gamma": 1.0,
        "diameter": 1.0,
        # The configuration's declared dimensionality (capabilities/
        # simulation.json `dimensions.n`), carried into the engine record so a
        # run says which `d` its diffusivity was divided by. 3 is a FALLBACK
        # and not a default in disguise: it is what every plan in this tree
        # predating the field meant, all of them bd_overdamped, and the
        # preflight report prints it so a wrong one is visible rather than
        # silent. The active path overrides it below.
        "dimensions": int(params.get("dimensions", 3)),
        **_active_to_engine(params, units),
    }


# --- the active configurations ------------------------------------------- #
#
# `abp_free` declares hoomd_backend as its executed_by, so the active path
# belongs in this file and not beside it. It is ADDITIVE: a plan carrying
# neither `self_propulsion_speed` nor `rotational_diffusivity` takes exactly
# the path it took before, so every bd_overdamped card regenerates unchanged.
#
# What makes a run active is the PLAN, not a flag: the two parameters are the
# model, and a plan that has them is a plan for a model that has them.

ACTIVE_KEYS = ("self_propulsion_speed", "rotational_diffusivity")


def is_active(params: dict) -> bool:
    """Whether this plan describes a self-propelled particle."""
    return all(k in params and params[k] is not None for k in ACTIVE_KEYS)


def _active_to_engine(params: dict, units: "Reduced") -> dict:
    """The active parameters in engine units, or nothing at all.

    `active_force` and not `active_speed`: HOOMD's md.force.Active applies a
    FORCE, and the overdamped velocity it produces is force/gamma. gamma is 1
    in this unit system, so the two are numerically equal here -- and writing
    the multiplication out is what keeps that an arithmetic fact rather than a
    coincidence somebody later reads as an identity.
    """
    if not is_active(params):
        return {}
    v0 = units.speed_in(params["self_propulsion_speed"])
    return {
        "active_speed": v0,
        "active_force": v0 * 1.0,
        "rotational_diffusion": units.rate_in(params["rotational_diffusivity"]),
        "dimensions": 2,
    }


def preflight_report(params: dict, seed: int) -> dict:
    """The same report the mock gives, for the same fields.

    Shared shape and not shared code: the two backends answer this about
    themselves, and the one number that differs -- what the engine would
    actually be handed -- is the reason this exists separately. Pure: it
    touches no engine, so it is checkable with HOOMD absent, which is most of
    what `010` step 3 asks for.
    """
    missing = [k for k in REQUIRED if k not in params]
    if missing:
        return {
            "backend": NAME,
            "missing_parameters": missing,
            "steps_per_frame": None,
            "frames_expected": None,
            "save_interval_divides_step": False,
            "diffusivity_si": None,
            "seed": seed,
        }
    steps_per_frame = round(params["save_interval"] / params["integration_timestep"])
    units = Reduced(params["temperature"], params["viscosity"], params["bead_diameter"])
    return {
        "backend": NAME,
        "missing_parameters": [],
        "steps_per_frame": steps_per_frame,
        "frames_expected": round(params["total_simulated_time"] / params["save_interval"]),
        # The same tolerance the mock applies, and against the same quantity: a
        # save interval that is not a whole number of steps puts a frame
        # between steps and the lag axis is then wrong by a fraction of a step.
        "save_interval_divides_step": (
            abs(steps_per_frame * params["integration_timestep"] - params["save_interval"]) < 1e-12
        ),
        "diffusivity_si": units.diffusivity,
        "seed": seed,
        "reduced_units": units.describe(),
        "engine_parameters": to_engine(params),
    }


def _plain(value):
    """JSON-safe or None. A build field is a record, not an object graph."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def engine_build(engine) -> dict:
    """Which build of the engine answered, for the run record.

    Read off the module (`hoomd.version`) and off the environment that
    installed it (`<sys.prefix>/conda-meta/hoomd-*.json`, which every
    conda-family tool writes for each package it links: channel, build
    string, platform and the archive's sha256). The two are different claims.
    The first says what the code was compiled with -- CPU or GPU, MPI or not,
    single or double precision -- and the second says where the bytes came
    from. A run record that names neither can say `hoomd_backend` and no
    more, and the librarian's log already holds one case of two current
    builds answering the same question differently; "which build" is a field
    here for the same reason it became one there.

    Every field degrades to None rather than raising. A double injected as
    `engine` has no `version`; an engine built from source has no conda-meta
    entry. Absent is recorded as absent, not filled in (P1).
    """
    v = getattr(engine, "version", None)

    def read(name):
        return _plain(getattr(v, name, None)) if v is not None else None

    flags = read("compile_flags")
    conda = None
    for path in sorted(glob.glob(f"{sys.prefix}/conda-meta/hoomd-*.json")):
        try:
            with open(path) as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            continue
        conda = {k: _plain(meta.get(k)) for k in ("fn", "version", "build", "channel", "subdir", "sha256")}
    return {
        "engine": "hoomd",
        "version": read("version"),
        "gpu_enabled": read("gpu_enabled"),
        "mpi_enabled": read("mpi_enabled"),
        "gpu_platform": read("gpu_platform") or None,
        "compile_flags": flags.strip() if isinstance(flags, str) else flags,
        "floating_point_precision": read("floating_point_precision"),
        "conda_package": conda,
        "python": sys.version.split()[0],
        "interpreter": os.path.abspath(sys.executable),
        "platform": f"{platform.system()}-{platform.machine()}",
    }


# --------------------------------------------------------------------------- #
# the backend
# --------------------------------------------------------------------------- #


class HoomdBackend:
    """Overdamped Brownian dynamics in HOOMD, behind the four-call interface.

    `engine` is the module this drives, defaulting to `hoomd`. It is injectable
    for one reason and it is not to fake a run: the state machine, the unit
    conversion, the frame record and the estimator wiring are this file's and
    are checkable with no engine present, and were for four days before one
    was; the engine calls have run since 2026-09-22. A double exercises the
    wiring and says nothing about the physics -- which is the distinction 4.6.5
    draws when it calls the mock a first-class backend and this kind of thing
    not one.
    """

    NAME = NAME

    def __init__(self, seed: int = 0, engine=None, device=None) -> None:
        self.seed = int(seed)
        self.engine = engine if engine is not None else _import_hoomd()
        self.device = device
        self.params: dict | None = None
        self.units: Reduced | None = None
        self.frames: list[np.ndarray] = []
        self.frame_times: list[float] = []
        self.simulated_time = 0.0
        self.steps_taken = 0
        self.aborted: str | None = None
        self.state = None
        self.failure: str | None = None
        self.handle: str | None = None
        self._sim = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # -- the fixed interface ------------------------------------------------

    def preflight(self, params: dict) -> dict:
        report = preflight_report(params, self.seed)
        # Beside `engine_parameters`, so the record holds what the engine was
        # handed and what the engine was, in one place. The preflight event
        # is where the operator already puts this report, so log.json carries
        # it with no change to run_log.schema.json.
        report["engine_build"] = engine_build(self.engine)
        return report

    def apply(self, params: dict) -> dict:
        """Submit and return a handle. **Does not block until it finishes.**

        Same contract as the mock's, and here the reason is literal rather than
        anticipatory: an engine run is the multi-hour case that made the rule.
        """
        if self._worker is not None:
            raise RuntimeError("this backend has already been given a run")
        report = self.preflight(params)
        if report["missing_parameters"]:
            raise ValueError(f"missing {report['missing_parameters']}")

        self.params = dict(params)
        self.units = Reduced(params["temperature"], params["viscosity"], params["bead_diameter"])
        self.state = SUBMITTED
        self.handle = f"{NAME}:{self.seed}:{id(self):x}"
        self._worker = threading.Thread(target=self._integrate, name=self.handle, daemon=True)
        submitted_as = self.state
        self._worker.start()
        return {"handle": self.handle, "state": submitted_as}

    def read(self) -> dict:
        """Poll. The monitor's input, with no judgement attached."""
        with self._lock:
            if self.state is None:
                return {"state": None, "initialised": False}
            last = self.frames[-1] - self.frames[-2] if len(self.frames) > 1 else np.zeros(1)
            return {
                "state": self.state,
                "initialised": True,
                "handle": self.handle,
                "steps_taken": self.steps_taken,
                "simulated_time": self.simulated_time,
                "frames_saved": len(self.frames),
                "max_single_step_displacement": float(np.abs(last).max()),
                "max_absolute_coordinate": (
                    float(np.abs(self.frames[-1]).max()) if self.frames else 0.0
                ),
                "failure": self.failure,
            }

    def abort(self, reason: str) -> dict:
        """Interrupt and WAIT. The trajectory is read after this returns, and
        reading it while the worker is still appending reports a record nobody
        ran."""
        self.aborted = reason
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=30)
        with self._lock:
            if self.state not in TERMINAL:
                self.state = ABORTED
            return {
                "aborted": True,
                "reason": reason,
                "state": self.state,
                "steps_taken": self.steps_taken,
            }

    # -- the run ------------------------------------------------------------

    def _integrate(self) -> None:
        """Chunk the run, pull a frame back after each chunk, convert, record.

        The loop is this file's and the three calls inside it are the engine's.
        Stopping is checked between chunks and not judged here: the operator
        sets the flag on a comparison the plan declared (4.6.5).
        """
        try:
            report = self.preflight(self.params)
            per_frame = int(report["steps_per_frame"])
            frames = int(report["frames_expected"])
            engine_params = report["engine_parameters"]
            dt_si = float(self.params["integration_timestep"])

            sim = self._start_engine(engine_params)
            with self._lock:
                self._sim = sim
                self.frames = [self._snapshot_positions(sim, engine_params["box_length"])]
                self.frame_times = [0.0]
                self.state = RUNNING

            for _ in range(frames):
                if self._stop.is_set():
                    with self._lock:
                        self.state = ABORTED
                    return
                sim.run(per_frame)
                positions = self._snapshot_positions(sim, engine_params["box_length"])
                with self._lock:
                    self.steps_taken += per_frame
                    # Derived from the integer step count and never accumulated.
                    # Summing dt ten thousand times landed 2e-13 below a 20 s
                    # planned end and the completion criterion was then false on
                    # a run that finished exactly as planned; the sign of that
                    # drift is not predictable from dt alone.
                    self.simulated_time = self.steps_taken * dt_si
                    self.frames.append(positions)
                    self.frame_times.append(self.simulated_time)
            with self._lock:
                self.state = COMPLETE
        except Exception as exc:                       # noqa: BLE001
            with self._lock:
                self.failure = f"{type(exc).__name__}: {exc}"
                self.state = FAILED

    # -- the engine, and the only part of this file HOOMD has ever seen ----- #
    #
    # Written against HOOMD-blue's documented API and NOT EXECUTED until
    # 2026-09-22, when the first real runs checked it: `run-20260922-hoomd-s1`,
    # which recorded itself as a mock run, and `-s1b`, which did not (014).
    # The label "not yet executed" stood here for four days and was the honest
    # one. Everything above and below was exercised from the start.

    def _start_engine(self, p: dict):
        """Build and start a Brownian-dynamics simulation in reduced units."""
        if "active_force" in p:
            return self._start_engine_active(p)
        hoomd = self.engine
        device = self.device or hoomd.device.CPU()
        sim = hoomd.Simulation(device=device, seed=self.seed)

        snapshot = hoomd.Snapshot()
        if snapshot.communicator.rank == 0:
            snapshot.configuration.box = [p["box_length"]] * 3 + [0, 0, 0]
            snapshot.particles.N = p["n_particles"]
            snapshot.particles.types = ["tracer"]
            rng = np.random.default_rng(self.seed)
            snapshot.particles.position[:] = rng.uniform(
                -p["box_length"] / 2, p["box_length"] / 2, size=(p["n_particles"], DIMENSIONS)
            )
        sim.create_state_from_snapshot(snapshot)

        # Brownian and not Langevin: the overdamped limit is the model the
        # capability table declares, and an integrator with inertia is a
        # different physical model -- which this agent does not get to change
        # (4.2). gamma is set per type and is 1 by the unit system above.
        brownian = hoomd.md.methods.Brownian(filter=hoomd.filter.All(), kT=p["kT"])
        brownian.gamma["tracer"] = p["gamma"]
        integrator = hoomd.md.Integrator(dt=p["integration_timestep"], methods=[brownian])
        # No pair potential: `bd_overdamped` declares non-interacting tracers,
        # and adding one here would change the model without changing the card
        # that says which model ran.
        sim.operations.integrator = integrator
        return sim

    def _start_engine_active(self, p: dict):
        """A free active Brownian particle in two dimensions (`abp_free`).

        Three things differ from the passive build and each is the model and
        not a setting.

        **Two dimensions.** The configuration declares 2D, so the box is flat
        and the orientation lives in the plane. It is not a smaller version of
        the 3D run: the closed form carries (d-1) in the rotational term, so a
        3D box would give a different MSD under the same numbers.

        **The propulsion is a FORCE here and a SPEED in the plan.** HOOMD's
        `md.force.Active` applies a force; the overdamped velocity it produces
        is force/gamma, and gamma is 1 in this unit system. `to_engine` does
        that multiplication explicitly so the equality stays arithmetic. This
        is also where the person's ruling of 2026-09-23 lands: the plan
        declares a fixed SPEED, and for a free particle a fixed force along
        the orientation produces exactly that -- the two coincide with nothing
        to push against, and separate the moment there is.

        **Rotational diffusion is an updater, not an integrator method.**
        `integrate_rotational_dof` stays off: the orientation is not evolved by
        a torque, it is diffused directly at D_R by
        `md.update.ActiveRotationalDiffusion`. Turning both on would drive the
        orientation twice.
        """
        hoomd = self.engine
        device = self.device or hoomd.device.CPU()
        sim = hoomd.Simulation(device=device, seed=self.seed)
        box = p["box_length"]

        snapshot = hoomd.Snapshot()
        if snapshot.communicator.rank == 0:
            snapshot.configuration.box = [box, box, 0, 0, 0, 0]
            snapshot.particles.N = p["n_particles"]
            snapshot.particles.types = ["tracer"]
            rng = np.random.default_rng(self.seed)
            start = np.zeros((p["n_particles"], 3))
            start[:, :2] = rng.uniform(-box / 2, box / 2, size=(p["n_particles"], 2))
            snapshot.particles.position[:] = start
            # A uniform in-plane orientation, as a rotation about z. Starting
            # every particle pointing the same way would put a coherent drift
            # in the first persistence time and the MSD would carry it.
            theta = rng.uniform(0.0, 2.0 * np.pi, p["n_particles"])
            quaternion = np.zeros((p["n_particles"], 4))
            quaternion[:, 0] = np.cos(theta / 2.0)
            quaternion[:, 3] = np.sin(theta / 2.0)
            snapshot.particles.orientation[:] = quaternion
            snapshot.particles.moment_inertia[:] = np.tile([0.0, 0.0, 1.0], (p["n_particles"], 1))
        sim.create_state_from_snapshot(snapshot)

        brownian = hoomd.md.methods.Brownian(filter=hoomd.filter.All(), kT=p["kT"])
        brownian.gamma["tracer"] = p["gamma"]
        brownian.gamma_r["tracer"] = [1.0, 1.0, 1.0]
        active = hoomd.md.force.Active(filter=hoomd.filter.All())
        active.active_force["tracer"] = (p["active_force"], 0.0, 0.0)
        integrator = hoomd.md.Integrator(
            dt=p["integration_timestep"], methods=[brownian], forces=[active],
            integrate_rotational_dof=False,
        )
        sim.operations.integrator = integrator
        sim.operations.updaters.append(
            hoomd.md.update.ActiveRotationalDiffusion(
                trigger=1, active_force=active,
                rotational_diffusion=p["rotational_diffusion"],
            )
        )
        # No pair potential: `abp_free` declares one particle with no
        # interaction, no wall and no obstacle, and adding one here would
        # change the model without changing the card that says which ran.
        return sim

    def _snapshot_positions(self, sim, box_reduced: float) -> np.ndarray:
        """Unwrapped positions, in SI metres.

        **Unwrapped, via the image flags.** A wrapped coordinate makes a tracer
        that crossed the boundary look like it jumped a box width, and the MSD
        then reports that jump as physics -- the artefact A3's image bound
        exists to keep out rather than to hide in the estimator. HOOMD stores
        the wrapped position and an integer image count per particle, so the
        unwrapped position is `position + image * L`, and this is the only
        place that knows it.
        """
        snap = sim.state.get_snapshot()
        position = np.asarray(snap.particles.position, dtype=float)
        image = np.asarray(snap.particles.image, dtype=float)
        # PER AXIS, and not one scalar. The box has three edge lengths and
        # `box_reduced` is only their common value when it is a cube. That was
        # true of every run this file had ever made -- bd_overdamped is a cubic
        # 3D box -- and it is false the moment a two-dimensional configuration
        # arrives, where Lz is 0.
        #
        # It is not a tidy-up. HOOMD keeps incrementing the z IMAGE FLAG in a
        # flat box even though z never moves and Lz is zero: measured on
        # 2026-09-23, image[2] = 2001 with z identically 0. Multiplied by the
        # scalar 4000 that put 40 metres of displacement on an axis the model
        # does not have, and the mean squared displacement came out 1e11 times
        # the closed form. Reading the edge lengths off the box makes Lz = 0
        # cancel it with no special case for two dimensions.
        edges = np.asarray(snap.configuration.box[:3], dtype=float)
        unwrapped_reduced = position + image * edges
        return unwrapped_reduced * self.units.length

    # -- trajectory output --------------------------------------------------
    #
    # Delegated, exactly as the mock delegates. By this point the frames are
    # SI metres and seconds and nothing downstream can tell which engine made
    # them, which is what lets two runs be compared at all.

    def estimator(self) -> estimator_module.Estimator:
        # The dimensionality is the configuration's and is never assumed here:
        # `D = slope/(2d)` with d = 3 on a two-dimensional run returns two
        # thirds of the true diffusivity, plausibly and with nothing failing.
        return estimator_module.Estimator(
            self.frame_times, self.frames, to_engine(self.params)["dimensions"]
        )

    def mean_squared_displacement(self, max_lag_time: float,
                                  tracers: "np.ndarray | None" = None) -> list[tuple[float, float]]:
        return self.estimator().mean_squared_displacement(max_lag_time, tracers=tracers)

    def fit_diffusivity(self, max_lag_time: float) -> dict:
        return self.estimator().fit_diffusivity(max_lag_time)

    def block_uncertainty(self, max_lag_time: float) -> dict:
        """The honest error bar, and not the fit's own.

        `006` measured the fit's quoted standard error at about 36 times too
        small for this configuration, because the fit treats a hundred MSD
        points as independent when every lag comes from the same trajectories.
        The first result card's error bar rests on the block estimate. An
        engine backend that returned the fit's error instead would quietly
        restore the defect the card was built to avoid -- so this delegates to
        the same estimator rather than offering an engine-flavoured
        alternative.
        """
        return self.estimator().block_uncertainty(max_lag_time)

    def window_halves(self, max_lag_time: float) -> dict:
        return self.estimator().window_halves(max_lag_time)


def _import_hoomd():
    """Import the engine, or say how to get one, once and early.

    HOOMD is not on PyPI -- it ships through conda-forge -- so `uv sync` gets
    the pipeline and not the engine, deliberately (9.2 rule 4: a machine with
    the validator and the mock does all of M2's verification). A missing engine
    is therefore an ordinary state of this repository and not a broken install,
    and it gets a sentence rather than a traceback.

    Since 2026-09-22 the engine is also the DEFAULT backend (018), so on a
    fresh machine this message is the first thing the operator says. It used
    to end "install HOOMD outside this repository", which named no file, no
    command and no version; the install lines now come from `engine_check`,
    the one module that reads the pin, so this message and that report cannot
    disagree about what to type.
    """
    try:
        import hoomd                                   # noqa: PLC0415
    except ImportError as exc:
        from . import engine_check                     # noqa: PLC0415  (only on the failure path)
        try:
            lines = engine_check.install_lines(engine_check.read_pin())
        except (OSError, LookupError) as pin_exc:      # the spec is missing or unreadable
            lines = [f"(the pixi table could not be read: {pin_exc})"]
        raise EngineMissing(
            f"hoomd is not importable in this interpreter ({exc}). HOOMD-blue is not on PyPI, "
            "so `uv sync` never installs it and no PyPI dependency list can name it; it ships through "
            f"conda-forge for {', '.join(engine_check.PLATFORMS)} and not win-64. The environment "
            "that holds it together with the pipeline's own dependencies is pyproject.toml's "
            "[tool.pixi] `sim` environment, locked in pixi.lock:\n    "
            + "\n    ".join(lines)
            + "\n`python3 -m src.engine_check` says what this interpreter has. The pipeline runs "
            "without the engine by being handed mock_backend explicitly (4.6.5)."
        ) from exc
    return hoomd
