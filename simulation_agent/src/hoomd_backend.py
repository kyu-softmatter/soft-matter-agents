"""The HOOMD backend -- the same interface, a different engine, and units.

`mock_backend` is a first-class backend and therefore the specification (4.6.5):
this file matches its shapes rather than a reading of what they should be. The
seam is already there -- `operator.run()` takes `backend=` -- so **nothing in
the operator changes** when a run comes here instead.

**What is verified and what is not, said plainly.** Everything that does not
touch the engine is exercised today: the parameter mapping, the unit system in
both directions, the state machine, the frame record, and the estimator wiring.
The ~20 lines that call HOOMD are **not executed anywhere yet** -- HOOMD is
conda-forge only and this machine's conda does not run -- so they are written
against HOOMD-blue v4's documented API and the first real run is where they get
checked. That is `010`'s arrangement and not a shortcut: a machine with the
validator and the mock does all of M2's verification (9.2 rule 4).

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


# --------------------------------------------------------------------------- #
# the backend
# --------------------------------------------------------------------------- #


class HoomdBackend:
    """Overdamped Brownian dynamics in HOOMD, behind the four-call interface.

    `engine` is the module this drives, defaulting to `hoomd`. It is injectable
    for one reason and it is not to fake a run: the state machine, the unit
    conversion, the frame record and the estimator wiring are this file's and
    are checkable today, while the engine calls are not. A double exercises the
    wiring and says nothing about the physics -- which is the distinction 4.6.5
    draws when it calls the mock a first-class backend and this kind of thing
    not one.
    """

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
        return preflight_report(params, self.seed)

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
    # NOT YET EXECUTED. Written against HOOMD-blue v4's documented API; the
    # first real run is where it is checked, and until then this comment is the
    # honest label. Everything above and below is exercised today.

    def _start_engine(self, p: dict):
        """Build and start a Brownian-dynamics simulation in reduced units."""
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
        unwrapped_reduced = position + image * box_reduced
        return unwrapped_reduced * self.units.length

    # -- trajectory output --------------------------------------------------
    #
    # Delegated, exactly as the mock delegates. By this point the frames are
    # SI metres and seconds and nothing downstream can tell which engine made
    # them, which is what lets two runs be compared at all.

    def estimator(self) -> estimator_module.Estimator:
        return estimator_module.Estimator(self.frame_times, self.frames)

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
    """Import the engine, or say why there is none, once and early.

    HOOMD is not on PyPI -- it ships through conda-forge -- so `uv sync` gets
    the pipeline and not the engine, deliberately (9.2 rule 4: a machine with
    the validator and the mock does all of M2's verification). A missing engine
    is therefore an ordinary state of this repository and not a broken install,
    and it gets a sentence rather than a traceback.
    """
    try:
        import hoomd                                   # noqa: PLC0415
    except ImportError as exc:
        raise EngineMissing(
            "hoomd is not importable here. It is conda-forge only and is not in "
            "pyproject.toml on purpose, so `uv sync` never installs it: 9.2 rule 4 puts all of "
            "M2's verification on the validator and mock_backend, and this backend is the part "
            "that waits for a machine with the engine. Run with mock_backend, or install HOOMD "
            f"outside this repository. ({exc})"
        ) from exc
    return hoomd
