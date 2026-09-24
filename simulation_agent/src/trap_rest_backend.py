"""The trap backends with the fluid at rest, for `bd_overdamped_trapped`.

`bd_overdamped_trapped` is `bd_overdamped_trapped_uniform_flow` with the flow
removed, and its declaration names the same engine builder. So this module
adds no physics. It wraps the two trap backends -- `trap_hoomd_backend` for the
engine, `trap_backend` as the NumPy fallback -- and supplies the one parameter
an undriven plan does not carry: the flow speed, which is zero by declaration.

WHY A WRAPPER AND NOT A DEFAULT IN THE TRAP BACKENDS. Both list `flow_speed` as
required, and they are right to: for the driven configuration a missing speed
is a missing decision, and defaulting it to zero there would run a drag
calibration with no drag and finish green. The zero belongs to the undriven
configuration, so it lives in the undriven configuration's module.

AND WHY IT REFUSES A FLOW. An undriven plan that carries a `flow_speed` is a
plan contradicting its own configuration, and silently overwriting the speed
with zero would hide that. So a flow in the parameters is an error here.

The run log still names the builder that ran, `trap_hoomd_backend` or
`trap_backend`, because that is what integrated; the preflight report says in
addition that the flow was fixed at zero here.
"""

from __future__ import annotations

import math

import numpy as np

from . import trap_backend, trap_hoomd_backend


def at_rest(params: dict) -> dict:
    # Idempotent at zero, because the trap backends' apply() calls their own
    # preflight() with the parameters it was given -- which by then carry the
    # zero this function injected. The first version refused any flow_speed at
    # all and so refused its own output on the first run. What is refused is a
    # NONZERO flow: that is the plan contradicting its configuration.
    if float(params.get("flow_speed", 0.0)) != 0.0:
        raise ValueError(
            "bd_overdamped_trapped is undriven, but the plan carries flow_speed = "
            f"{params['flow_speed']!r}. A driven trap is bd_overdamped_trapped_uniform_flow."
        )
    out = dict(params)
    out["flow_speed"] = 0.0
    return out


def width(est) -> dict:
    """The registered observable: the per-axis in-plane width about the record mean.

    Read off the same post-startup record the trap estimator holds. For each of
    x and y: the standard deviation about the RECORD'S OWN mean (the estimator
    `trapped_position_distribution` registers), its ratio to equipartition's
    sqrt(k_B*T/k_t), the ratio corrected for the expected low bias of that
    subtraction, and the deviation in units of the record's own scatter. Plus
    the histogram in units of the predicted width against a unit Gaussian, and
    the excess kurtosis, which is the harmonicity check a bench trace can fail
    and this model cannot.
    """
    T = est.record_length
    bias = est.tau / T if T > 0 else float("nan")
    scatter = math.sqrt(est.tau / (2.0 * T)) if T > 0 else float("nan")
    edges = np.linspace(-5.0, 5.0, 41)
    centres = 0.5 * (edges[1:] + edges[:-1])
    gauss = [0.5 * (math.erf(b / math.sqrt(2)) - math.erf(a / math.sqrt(2))) for a, b in zip(edges[:-1], edges[1:])]
    axes = {}
    for name, i in (("x", 0), ("y", 1)):
        col = est.coords[:, i]
        s = float(col.std(ddof=1))
        z = (col - col.mean()) / est.sigma
        counts, _ = np.histogram(z, edges)
        ratio = s / est.sigma
        corrected = ratio / (1.0 - bias)
        axes[name] = {
            "width_si": s,
            "width_um": s * 1e6,
            "ratio_to_equipartition": ratio,
            "ratio_bias_corrected": corrected,
            "relative_deviation_bias_corrected": corrected - 1.0,
            "deviation_in_scatters": (corrected - 1.0) / scatter,
            "excess_kurtosis": float(((z - z.mean()) ** 4).mean() / (z.var() ** 2) - 3.0),
            "histogram": {"edges_in_predicted_widths": edges.tolist(), "counts": counts.tolist(),
                          "gaussian_expected_fraction": gauss},
        }
    worst = max(abs(a["relative_deviation_bias_corrected"]) for a in axes.values())
    return {
        "predicted_width_si": est.sigma,
        "predicted_width_um": est.sigma * 1e6,
        "frames_in_record": int(len(est.coords)),
        "record_length_si": T,
        "expected_relative_bias": -bias,
        "expected_relative_scatter": scatter,
        "axes": axes,
        "relative_deviation_of_width_from_equipartition": worst,
        "note": ("per-axis standard deviation about the record's own mean over the declared record, "
                 "after the start-up discard. The bias correction divides by (1 - tau_t/T), the expected "
                 "shortfall from subtracting that mean. The positions are instantaneous: a camera "
                 "frame averages over its exposure and would read narrower"),
    }


class _AtRest:
    def preflight(self, params: dict) -> dict:
        out = super().preflight(at_rest(params))
        out["flow"] = "zero by declaration: bd_overdamped_trapped is undriven (trap_rest_backend)"
        return out

    def apply(self, params: dict) -> dict:
        return super().apply(at_rest(params))

    def observables(self, params: dict) -> dict:
        """The width, not the drag offset: at zero flow the offset is zero and its
        relative deviation divides by it, which is how the first run of this
        configuration crashed after integrating correctly."""
        est = self.estimator()
        steps = max(1, self.steps_taken)
        name = trap_hoomd_backend.NAME if isinstance(self, trap_hoomd_backend.TrapHoomdBackend) else trap_backend.NAME
        return {
            "window_parameter": "record_length",
            "window_si": est.record_length,
            "trapped_position_distribution": width(est),
            "relaxation_time": est.relaxation_time(),
            "transverse": est.transverse(),
            "cost": {
                "integration_wall_s": self.integration_wall_s,
                "steps": self.steps_taken,
                "wall_s_per_step": (self.integration_wall_s / steps) if self.integration_wall_s else None,
                "frames_saved": len(self.frames),
                "n_particles": trap_backend.N_PARTICLES,
                "backend": name,
                "note": "measured on the integration loop alone, one bead, fluid at rest",
            },
        }


class TrapRestHoomdBackend(_AtRest, trap_hoomd_backend.TrapHoomdBackend):
    """The engine build, fluid at rest."""


class TrapRestBackend(_AtRest, trap_backend.TrapBackend):
    """The NumPy fallback, fluid at rest."""
