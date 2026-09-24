"""The estimator for `trapped_particle_drag_offset`, and the checks that ride on one trace.

`estimator.py` is `tracer_diffusivity`'s and reads an MSD slope; that reading
throws away exactly what this observable is. The registered estimator here is
the one `contracts/observables.json` declares for the id, and it is written
once so a second backend delegates to it rather than growing its own:

    Track the particle centre over a declared record length under steady flow
    and report the mean displacement from the DECLARED trap centre, resolved
    along the flow direction.

**The declared centre, not the measured mean.** That single word is the whole
difference from `trapped_position_distribution`, whose estimator takes the
mean position as the centre and subtracts it. The two are complements read
off one trace, so this module computes the mean relative to the origin the
backend placed the trap at, and never re-centres.

Three further readings ride on the same frames. None of them is the
observable; each is a check on the model the run is supposed to be:

* **equipartition** -- the per-axis variance against k_B*T/k_t, a second
  route to the stiffness that does not go through the drag at all;
* **the relaxation time** -- the decay of the along-flow autocorrelation
  against gamma/k_t, which is the timescale every axis card was written in;
* **the transverse means** -- y and z, which the flow does not drive and
  which must sit at the centre within their own error.

**Euler-Maruyama leaves the two routes to the stiffness unequal, and the
difference is predicted, not a defect.** For the discrete update
x' = x + (-x/tau + v)*dt + sqrt(2*D*dt)*xi the stationary MEAN is v*tau
exactly, at any stable timestep, because the drift is linear. The stationary
VARIANCE is D*tau/(1 - dt/(2*tau)), so equipartition reads the stiffness low
by a fraction dt/(2*tau). The drag route is therefore unbiased by the
integrator and the equipartition route is not, and both numbers are reported
beside the bias the scheme predicts so a reader can tell the two apart.
"""

from __future__ import annotations

import math

import numpy as np

from . import physics


def _stokes_drag(viscosity: float, bead_diameter: float) -> float:
    """gamma = 3*pi*eta*d, the translational drag coefficient, in kg/s."""
    return 3.0 * math.pi * viscosity * bead_diameter


class TrapEstimator:
    """Readings off the post-startup record of one trapped particle."""

    def __init__(self, frame_times: list, frames: list, params: dict) -> None:
        self.params = dict(params)
        times = np.asarray(frame_times, dtype=float)
        coords = np.asarray([np.asarray(f, dtype=float).reshape(-1, 3)[0] for f in frames])
        startup = float(params["startup_discard"])
        keep = times >= startup - 1e-12
        self.times = times[keep]
        self.coords = coords[keep]           # shape (n_frames, 3), metres, trap centre at origin

        T = float(params["temperature"])
        eta = float(params["viscosity"])
        d = float(params["bead_diameter"])
        self.k_t = float(params["trap_stiffness"])
        self.v = float(params["flow_speed"])
        self.dt = float(params["integration_timestep"])
        self.save = float(params["save_interval"])
        self.gamma = _stokes_drag(eta, d)
        self.kT = physics.K_B * T
        self.D = self.kT / self.gamma
        self.tau = self.gamma / self.k_t
        self.sigma = math.sqrt(self.kT / self.k_t)

    # -- the registered observable ----------------------------------------

    @property
    def record_length(self) -> float:
        return float(self.times[-1] - self.times[0]) if len(self.times) > 1 else 0.0

    def drag_offset(self) -> dict:
        """Mean along-flow displacement from the DECLARED centre, with a block error.

        Blocks are ten declared relaxation times long, so neighbouring block
        means are independent to about e^-10. The block count is DERIVED from
        the declared model rather than tuned on the data, which is what keeps
        the error bar from being chosen after seeing the answer.
        """
        x = self.coords[:, 0]
        mean = float(x.mean())
        block_frames = max(1, int(round(10.0 * self.tau / self.save)))
        n_blocks = len(x) // block_frames
        if n_blocks >= 2:
            blocks = x[: n_blocks * block_frames].reshape(n_blocks, block_frames).mean(axis=1)
            se_block = float(blocks.std(ddof=1) / math.sqrt(n_blocks))
        else:
            se_block = float("nan")
        predicted = self.gamma * self.v / self.k_t
        se_ou = self.sigma * math.sqrt(2.0 * self.tau / self.record_length) if self.record_length > 0 else float("nan")
        return {
            "value_si": mean,
            "unit_si": "m",
            "value_um": mean * 1e6,
            "standard_error_block_si": se_block,
            "standard_error_ou_predicted_si": se_ou,
            "block_count": n_blocks,
            "block_length_s": block_frames * self.save,
            "record_length_s": self.record_length,
            "frames_used": int(len(x)),
            "predicted_si": predicted,
            "relative_deviation_from_predicted": (mean - predicted) / predicted,
            "deviation_in_block_standard_errors": (mean - predicted) / se_block if se_block and not math.isnan(se_block) else None,
            "note": (
                "the mean of x over the record after startup_discard, relative to the trap centre "
                "the backend placed at the origin. `predicted_si` is gamma*v/k_t from the declared "
                "inputs, and it is exact for the Euler-Maruyama update at any stable timestep -- "
                "so any deviation here is statistics, not integration error. Two error bars: the "
                "block estimate is read off this trace; the OU one is sigma*sqrt(2*tau/T) from the "
                "declared model, and the question's central claim is that they agree."
            ),
        }

    def recovered_stiffness(self) -> dict:
        """k_t two ways: through the drag, and through equipartition."""
        off = self.drag_offset()
        k_drag = self.gamma * self.v / off["value_si"] if off["value_si"] else float("nan")
        rel_se = abs(off["standard_error_block_si"] / off["value_si"]) if off["value_si"] else float("nan")
        var_x = float(self.coords[:, 0].var(ddof=1))
        k_equip = self.kT / var_x if var_x > 0 else float("nan")
        em_bias = -self.dt / (2.0 * self.tau)
        # For a stationary Gaussian process with C(t) = sigma^2 exp(-|t|/tau),
        # Var(mean) = (1/T) * integral C = 2*sigma^2*tau/T and
        # Var(sample variance) = (2/T) * integral C^2 = 2*sigma^4*tau/T. So both
        # routes carry the same factor sqrt(2*tau/T), and the drag route alone
        # divides it by the offset in thermal widths.
        base = math.sqrt(2.0 * self.tau / self.record_length) if self.record_length > 0 else float("nan")
        offset_in_sigma = abs(off["value_si"]) / self.sigma if self.sigma else float("nan")
        return {
            "declared_si": self.k_t,
            "unit_si": "N/m",
            "from_drag_si": k_drag,
            "from_drag_ratio": k_drag / self.k_t,
            "from_drag_relative_standard_error": rel_se,
            "from_drag_relative_standard_error_ou_predicted": base / offset_in_sigma if offset_in_sigma else None,
            "from_equipartition_si": k_equip,
            "from_equipartition_ratio": k_equip / self.k_t,
            "from_equipartition_relative_standard_error_ou_predicted": base,
            "euler_maruyama_predicted_equipartition_bias": em_bias,
            "offset_in_thermal_widths": offset_in_sigma,
            "drag_route_advantage_predicted": offset_in_sigma,
            "note": (
                "the drag route is gamma*v/<x>; the equipartition route is k_B*T/var(x). BOTH CARRY "
                "THE SAME STATISTICAL FACTOR sqrt(2*tau/T), and the drag route alone divides it by "
                "the offset in thermal widths -- so at equal record length DRAG BEATS EQUIPARTITION "
                "BY EXACTLY THAT FACTOR, and driving harder improves only the drag route. That is the "
                "reason drag calibration exists as a method, measured here rather than asserted. The "
                "equipartition route also carries Euler-Maruyama's dt/(2*tau) bias, given beside it; "
                "at a smoke-run record the bias is far inside the statistical error, so a deviation "
                "of order ten per cent there is statistics and not the integrator. THE "
                "RECOVERED-OVER-DECLARED RATIO IS NOT EVIDENCE ABOUT ANY TRAP: gamma and k_t both "
                "went in and the estimator inverts the equation the integrator solved "
                "(output_independent_of_input false). What it tests is the integrator and this "
                "estimator, and the relative standard error is the number the question is about."
            ),
        }

    # -- checks on the model, not the observable ---------------------------

    def relaxation_time(self) -> dict:
        """The along-flow autocorrelation's decay time, against gamma/k_t."""
        x = self.coords[:, 0] - self.coords[:, 0].mean()
        c0 = float(np.dot(x, x) / len(x))
        max_lag = max(2, int(round(2.0 * self.tau / self.save)))
        lags, logc = [], []
        for k in range(1, min(max_lag, len(x) - 1) + 1):
            c = float(np.dot(x[:-k], x[k:]) / (len(x) - k)) / c0
            if c <= math.exp(-2.0):
                break
            lags.append(k * self.save)
            logc.append(math.log(c))
        if len(lags) >= 2:
            slope = float(np.polyfit(lags, logc, 1)[0])
            tau_fit = -1.0 / slope if slope < 0 else float("nan")
        else:
            tau_fit = float("nan")
        return {
            "declared_si": self.tau,
            "fitted_si": tau_fit,
            "ratio": tau_fit / self.tau if tau_fit == tau_fit else None,
            "lags_used": len(lags),
            "note": (
                "log C(lag) fitted over lags where C > e^-2, up to two declared relaxation times. "
                "gamma/k_t is the timescale every axis card for this configuration is written in, so "
                "a mismatch here would unseat A1, A2, A4 and A7 at once."
            ),
        }

    def transverse(self) -> dict:
        """y and z, which the flow does not drive."""
        out = {}
        for axis, i in (("y", 1), ("z", 2)):
            col = self.coords[:, i]
            se = self.sigma * math.sqrt(2.0 * self.tau / self.record_length) if self.record_length > 0 else float("nan")
            out[axis] = {
                "mean_si": float(col.mean()),
                "mean_in_ou_standard_errors": float(col.mean() / se) if se else None,
                "variance_ratio_to_equipartition": float(col.var(ddof=1) / (self.kT / self.k_t)),
            }
        out["note"] = ("undriven axes: the mean must sit at the declared centre within its own error, "
                       "and the variance at k_B*T/k_t up to the same Euler-Maruyama bias as x")
        return out
