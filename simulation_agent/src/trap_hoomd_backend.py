"""The trap configuration on HOOMD: one sphere, a harmonic trap, uniform flow.

For `bd_overdamped_trapped_uniform_flow`, the engine build of what
`trap_backend` integrates in NumPy. It subclasses that backend and replaces
only the integration, so the four-call interface, the five states, `read`,
`abort`, the estimator and `observables` are ONE implementation on both
engines. Whatever differs between a mock run and an engine run of the same
plan is then the engine and nothing else -- the working definition of
reproducibility in 4.6.5, and the reason the mock came first (it passed a
smoke run and a 200-seed ensemble before this file existed).

**How the trap is built, because HOOMD has no harmonic external potential.**
`hoomd.md.external.field` offers Electric, Magnetic and Periodic, none of them
a spring to a point. So the trap is a HARMONIC BOND, `U = k/2 (r - r0)^2` with
`r0 = 0`, between the bead and a second particle -- the tether -- that sits at
the trap centre and is left out of the integration method's filter, so it
never moves. The force is then computed by the engine in C++, which is what
makes this an engine run rather than NumPy physics driven through HOOMD's
integrator. Measured before this file was written: a bead started exactly on
the tether, where `r0/r` is 0/0, steps to a finite position, and the tether's
largest coordinate after 62000 steps is 0.0.

**The flow is `md.force.Constant`, gamma*v along +x, on the bead only.** In
the overdamped limit a uniform flow and a constant force gamma*v are the same
update, as `trap_backend` says; here gamma* = 1, so the force in reduced units
IS the reduced speed.

**Units, converted here and nowhere else (5.7 rule 4).** `hoomd_backend.Reduced`
is reused rather than restated, so length is the bead diameter, energy k_B*T
and time d^2/D, with kT* = gamma* = 1. The trap stiffness is an energy over a
length squared, so k* = k_t * d^2 / (k_B*T); the speed goes through
`speed_in`. Positions come back through the same object's `length`. The
scheme is HOOMD's Brownian method, which is Euler-Maruyama -- the scheme A1's
bounds were written for, and the one the mock integrates.
"""

from __future__ import annotations

import math
import time

import numpy as np

from . import hoomd_backend, physics
from .mock_backend import ABORTED, COMPLETE, FAILED, RUNNING
from .trap_backend import DIMENSIONS, N_PARTICLES, REQUIRED, TrapBackend

NAME = "trap_hoomd_backend"
BEAD, TETHER = "bead", "tether"


def to_engine(params: dict) -> dict:
    """The plan's SI parameters in the engine's reduced units."""
    u = hoomd_backend.Reduced(params["temperature"], params["viscosity"], params["bead_diameter"])
    k_star = float(params["trap_stiffness"]) * u.length ** 2 / u.energy
    v_star = u.speed_in(params["flow_speed"])
    return {
        "box_length": u.length_in(params["box_length"]),
        "integration_timestep": u.time_in(params["integration_timestep"]),
        "trap_stiffness": k_star,
        "flow_force": v_star,                 # gamma* = 1, so F* = gamma* * v* = v*
        "kT": 1.0,
        "gamma": 1.0,
        "relaxation_time": 1.0 / k_star,      # gamma*/k*
        "predicted_offset": v_star / k_star,
        "units": u.describe(),
    }


class TrapHoomdBackend(TrapBackend):
    """The same run as TrapBackend, integrated by HOOMD's Brownian method."""

    NAME = NAME

    def __init__(self, seed: int = 0, engine=None, device=None) -> None:
        super().__init__(seed=seed)
        # Raises EngineMissing at construction, before the operator has opened
        # a run directory, so a machine without HOOMD falls back instead of
        # recording a run that never started (hoomd_backend's reasoning).
        self.engine = engine if engine is not None else hoomd_backend._import_hoomd()
        self.device = device
        self.units: hoomd_backend.Reduced | None = None

    def preflight(self, params: dict) -> dict:
        out = super().preflight(params)
        out["backend"] = NAME
        out["engine_build"] = {"engine": "hoomd", "version": self.engine.version.version,
                               "gpu": bool(self.engine.version.gpu_enabled),
                               "precision": list(self.engine.version.floating_point_precision),
                               "scheme": "hoomd.md.methods.Brownian (Euler-Maruyama)",
                               "trap": "hoomd.md.bond.Harmonic to a tether left out of the integration filter",
                               "flow": "hoomd.md.force.Constant on the bead"}
        if not out["missing_parameters"]:
            out["engine_parameters"] = to_engine(params)
        return out

    def _integrate(self) -> None:
        try:
            p = self.params
            pre = self.preflight(p)
            e = pre["engine_parameters"]
            per_frame, frames = int(pre["steps_per_frame"]), int(pre["frames_expected"])
            dt_si = float(p["integration_timestep"])
            self.units = hoomd_backend.Reduced(p["temperature"], p["viscosity"], p["bead_diameter"])
            sim = self._start_engine(e)
            with self._lock:
                self.steps_planned = per_frame * frames
                self.frames = [self._bead(sim, e["box_length"])]
                self.frame_times = [0.0]
                self.state = RUNNING
            last_step = 0.0
            started = time.perf_counter()
            for _ in range(frames):
                if self._stop.is_set():
                    with self._lock:
                        self.state = ABORTED
                    return
                # The frame's last step is taken alone between two snapshots,
                # so the largest single-step displacement -- what the divergence
                # criterion watches -- is measured once per frame. Same steps in
                # the same order; one extra snapshot per frame.
                if per_frame > 1:
                    sim.run(per_frame - 1)
                    before = self._bead(sim, e["box_length"])
                else:
                    before = self.frames[-1]
                sim.run(1)
                x = self._bead(sim, e["box_length"])
                last_step = max(last_step, float(np.abs(x - before).max()))
                with self._lock:
                    self.position = x
                    self.steps_taken += per_frame
                    self.simulated_time = self.steps_taken * dt_si      # derived, never accumulated
                    self.frames.append(x)
                    self.frame_times.append(self.simulated_time)
                    self.largest_single_step = last_step
            tether = np.asarray(sim.state.get_snapshot().particles.position[1], dtype=float)
            with self._lock:
                self.integration_wall_s = time.perf_counter() - started
                self.tether_drift_reduced = float(np.abs(tether).max())
                self.state = COMPLETE
        except Exception as exc:                       # noqa: BLE001
            with self._lock:
                self.failure = f"{type(exc).__name__}: {exc}"
                self.state = FAILED

    def _start_engine(self, e: dict):
        hoomd = self.engine
        sim = hoomd.Simulation(device=self.device or hoomd.device.CPU(), seed=self.seed)
        L = float(e["box_length"])
        snap = hoomd.Snapshot()
        if snap.communicator.rank == 0:
            snap.configuration.box = [L, L, L, 0.0, 0.0, 0.0]
            snap.particles.N = 2
            snap.particles.types = [BEAD, TETHER]
            snap.particles.typeid[:] = [0, 1]
            snap.particles.position[:] = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]   # the bead starts at the centre
            snap.bonds.N = 1
            snap.bonds.types = ["trap"]
            snap.bonds.typeid[:] = [0]
            snap.bonds.group[:] = [[0, 1]]
        sim.create_state_from_snapshot(snap)
        trap = hoomd.md.bond.Harmonic()
        trap.params["trap"] = dict(k=e["trap_stiffness"], r0=0.0)
        flow = hoomd.md.force.Constant(filter=hoomd.filter.Type([BEAD]))
        flow.constant_force[BEAD] = (e["flow_force"], 0.0, 0.0)
        flow.constant_force[TETHER] = (0.0, 0.0, 0.0)
        brownian = hoomd.md.methods.Brownian(filter=hoomd.filter.Type([BEAD]), kT=e["kT"],
                                             default_gamma=e["gamma"])
        sim.operations.integrator = hoomd.md.Integrator(dt=e["integration_timestep"],
                                                        methods=[brownian], forces=[trap, flow])
        return sim

    def _bead(self, sim, box_reduced: float) -> np.ndarray:
        """The bead's unwrapped position in SI metres, as (1, 3)."""
        snap = sim.state.get_snapshot()
        pos = np.asarray(snap.particles.position[0], dtype=float)
        img = np.asarray(snap.particles.image[0], dtype=float)
        return ((pos + img * box_reduced) * self.units.length).reshape(N_PARTICLES, DIMENSIONS)

    def observables(self, params: dict) -> dict:
        out = super().observables(params)
        out["cost"]["backend"] = NAME
        out["cost"]["note"] = ("measured on the integration loop alone, HOOMD on the CPU, one bead and one "
                               "tether. It calibrates THIS backend at N=1 and replaces neither the NumPy mock's "
                               "figure nor a many-particle HOOMD figure")
        out["engine"] = {"tether_drift_reduced": getattr(self, "tether_drift_reduced", None),
                         "note": "the tether's largest coordinate at the end, in bead diameters; it is outside "
                                 "the integration filter and must read exactly zero",
                         "units": self.units.describe() if self.units else None}
        return out
