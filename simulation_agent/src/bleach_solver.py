"""What a bleach run should read, from the diffusion equation and with the run's own camera.

For non-interacting beads, the expected bright fraction obeys the diffusion
equation exactly, so the mean of many curves is a closed problem. This
module solves it and then reads the solution the way the run reads its
beads:

- the bleach is applied as the run applies it, a multiplicative kick
  `exp(-k*dt)` inside the disc at each engine sample, followed by free
  diffusion for dt;
- each frame is the mean over the same discrete samples the run averages;
- w is the half-contrast radius of the first post-bleach frame's profile,
  binned exactly as `estimator_bleach.Bleacher` bins it;
- the fit is `estimator_bleach.estimate` itself.

So the D this predicts carries the same finite-bleach, finite-frame and
finite-box effects the run carries, and a run is compared against it rather
than against Stokes-Einstein. That is the comparison that tests the
integrator (task 025, Stage 2 a, and the manager's condition 4).

**The one approximation**, stated. The run's box is a periodic square of
side L. Here it is a disc of equal area, with a zero-flux edge at
`L/sqrt(pi)`. The plateau, one minus the bleached amount over the box area,
is the same by construction, and
the shapes differ only once the refill reaches the box edge, near
`(L/2)^2/(4D)` (25 tau at L = 10 w), well past the record. Lengths are in units of w, and
times in units of tau = w^2/(4D).
"""

from __future__ import annotations

import math

import numpy as np
from scipy.linalg import solve_banded

from . import estimator_bleach

DR = 0.01
D_DIMLESS = 0.25


def _grid(box_over_w: float):
    r_max = box_over_w / math.sqrt(math.pi)
    n = int(round(r_max / DR))
    r_c = (np.arange(n) + 0.5) * DR
    r_f = np.arange(n + 1) * DR
    area = r_c * DR
    return n, r_c, r_f, area


def _matrix(n, r_f, area, dt):
    up = D_DIMLESS * r_f[1:] / (area * DR)
    lo = D_DIMLESS * r_f[:-1] / (area * DR)
    up[-1] = 0.0                      # zero flux at the equal-area edge
    ab = np.zeros((3, n))
    ab[0, 1:] = -dt * up[:-1]
    ab[2, :-1] = -dt * lo[1:]
    ab[1] = 1.0 + dt * (up + lo)
    return ab


def predict(*, box_over_w: float, k_tau: float, bleach_tau: float, frame_tau: float,
            window_tau: float, dt_tau: float, n_pre: int = 10, substeps: int = 8,
            profile_bins: int = 40, profile_rmax: float = 3.0) -> dict:
    """Expected curve and the registered fit to it, all in units of w and tau."""
    n, r_c, r_f, area = _grid(box_over_w)
    inside = r_c < 1.0
    roi_area = float(np.sum(area[inside]))
    h = dt_tau / substeps
    ab = _matrix(n, r_f, area, h)

    def diffuse(b):
        for _ in range(substeps):
            b = solve_banded((1, 1), ab, b)
        return b

    per_frame = int(round(frame_tau / dt_tau))
    per_bleach = int(round(bleach_tau / dt_tau))
    post_frames = int(math.floor(window_tau / frame_tau + 1e-9))
    kick = math.exp(-k_tau * dt_tau)

    b = np.ones(n)
    for _ in range(per_bleach):
        b = np.where(inside, b * kick, b)
        b = diffuse(b)
    # Dark material is conserved once the bleach ends, so the long-time
    # plateau is fixed now: 1 - (dark amount) / (box area).
    plateau = 1.0 - float(np.sum((1.0 - b) * area) / np.sum(area))
    F, first_profile = [], None
    for f in range(post_frames):
        acc, prof = 0.0, np.zeros(n)
        for _ in range(per_frame):
            acc += float(np.sum(b[inside] * area[inside]) / roi_area)
            if f == 0:
                prof += b
            b = diffuse(b)
        F.append(acc / per_frame)
        if f == 0:
            first_profile = prof / per_frame
    F = np.array(F)
    # bin the first frame's profile as the Bleacher bins bead counts
    edges = np.linspace(0.0, profile_rmax, profile_bins + 1)
    r_mid = 0.5 * (edges[1:] + edges[:-1])
    binned = np.empty(profile_bins)
    for i in range(profile_bins):
        m = (r_c >= edges[i]) & (r_c < edges[i + 1])
        binned[i] = float(np.sum(first_profile[m] * area[m]) / np.sum(area[m]))
    w_meas = estimator_bleach.half_contrast_radius(r_mid, binned)
    t = (np.arange(post_frames) + 0.5) * frame_tau
    est = estimator_bleach.estimate(t, F, w_meas, 1.0, bleach_tau, frame_tau, window_tau)
    D_ratio = est["D"] / D_DIMLESS if est.get("D") is not None else None
    return {
        "D_fit_over_D": D_ratio,
        "w_measured_over_w": w_meas,
        "tau_fit_over_tau": est.get("tau"),
        "mobile_fraction": est.get("mobile_fraction"),
        "reported": est.get("reported"),
        "refusal": est.get("refusal"),
        "dip": float(1.0 - F[0]),
        "plateau_expected": plateau,
        "t_over_tau": [float(x) for x in t],
        "F": [float(x) for x in F],
        "approximation": "periodic square replaced by the equal-area disc with a zero-flux edge",
    }


def predict_si(params: dict) -> dict:
    """The same prediction from a run's SI parameters."""
    from . import physics                                  # noqa: PLC0415
    D = physics.stokes_einstein(params["temperature"], params["viscosity"], params["bead_diameter"])
    w = params["bleach_radius"]
    tau = w * w / (4.0 * D)
    out = predict(box_over_w=params["box_length"] / w, k_tau=params["bleach_rate"] * tau,
                  bleach_tau=params["bleach_duration"] / tau, frame_tau=params["frame_interval"] / tau,
                  window_tau=params["max_recovery_time"] / tau, dt_tau=params["integration_timestep"] / tau,
                  n_pre=int(round(params["pre_bleach_frames"])))
    out["tau_s"] = tau
    out["D_stokes_einstein_m2_per_s"] = D
    return out
