"""Sensor model, checked the way a camera is actually characterised."""
from __future__ import annotations

import numpy as np
import pytest

from dino_autofocus.synth.optics.system import Camera
from dino_autofocus.synth.sim.camera import Sensor, auto_exposure


@pytest.fixture
def flat_cam():
    """No fixed-pattern noise, so the calibration tests isolate shot and read."""
    return Camera(prnu=0.0, hot_pixel_rate=0.0)


def test_photon_transfer_curve_recovers_gain(flat_cam, rng):
    """The photon-transfer slope of variance against mean is 1/gain when gain
    is in electrons per ADU -- not gain itself, which is easy to misremember."""
    s = Sensor(flat_cam, (256, 256), rng)
    means, variances = [], []
    for flux in (50, 200, 1000, 5000, 20000):
        a = s.expose(np.full((256, 256), float(flux)), 0.05).astype(np.float64)
        means.append(a.mean() - flat_cam.offset)
        variances.append(a.var())
    means, variances = np.array(means), np.array(variances)
    ok = means < 0.7 * flat_cam.full_well / flat_cam.gain
    slope = np.polyfit(means[ok], variances[ok], 1)[0]
    assert slope == pytest.approx(1.0 / flat_cam.gain, rel=0.1)


def test_dark_frame_recovers_read_noise(flat_cam, rng):
    s = Sensor(flat_cam, (256, 256), rng)
    dark = s.expose(np.zeros((256, 256)), 1e-3).astype(np.float64)
    assert dark.std() * flat_cam.gain == pytest.approx(flat_cam.read_noise, rel=0.15)
    assert dark.mean() == pytest.approx(flat_cam.offset, abs=1.0)


def test_saturation_clips_at_the_well_not_the_adc(flat_cam, rng):
    s = Sensor(flat_cam, (32, 32), rng)
    photons = np.zeros((32, 32)); photons[16, 16] = 1e9
    out = s.expose(photons, 0.05)
    assert out[16, 16] == pytest.approx(flat_cam.full_well / flat_cam.gain, rel=0.02)
    assert out[16, 16] < flat_cam.adu_max


def test_emccd_excess_noise_factor(rng):
    """A multiplication register doubles the variance-to-mean ratio: the
    familiar sqrt(2) excess-noise factor."""
    cam = Camera(em_gain=100.0, read_noise=50.0, prnu=0.0,
                 hot_pixel_rate=0.0, full_well=1e9)
    s = Sensor(cam, (256, 256), rng)
    e = s.expose(np.full((256, 256), 200.0), 0.05, return_electrons=True) / cam.em_gain
    assert e.var() / e.mean() == pytest.approx(2.0, rel=0.2)


def test_quantum_efficiency_scales_the_signal(rng):
    a = Sensor(Camera(qe=0.8, prnu=0.0, hot_pixel_rate=0.0, read_noise=0.0),
               (128, 128), rng)
    b = Sensor(Camera(qe=0.4, prnu=0.0, hot_pixel_rate=0.0, read_noise=0.0),
               (128, 128), rng)
    flux = np.full((128, 128), 5000.0)
    ea = a.expose(flux, 0.02, return_electrons=True).mean()
    eb = b.expose(flux, 0.02, return_electrons=True).mean()
    assert ea / eb == pytest.approx(2.0, rel=0.05)


def test_fixed_pattern_is_fixed_across_exposures(rng):
    cam = Camera(prnu=0.05, read_noise=0.0, dark_current=0.0)
    s = Sensor(cam, (64, 64), rng)
    flux = np.full((64, 64), 40000.0)
    a = s.expose(flux, 0.05, return_electrons=True)
    b = s.expose(flux, 0.05, return_electrons=True)
    # the pattern correlates the two frames far more than shot noise alone would
    assert np.corrcoef(a.ravel(), b.ravel())[0, 1] > 0.3


def test_auto_exposure_hits_the_requested_fill(rng):
    cam = Camera(prnu=0.0, hot_pixel_rate=0.0)
    flux = np.full((64, 64), 1e5)
    t = auto_exposure(flux, cam, target_fill=0.5)
    electrons = 1e5 * t * cam.qe
    assert electrons == pytest.approx(0.5 * cam.full_well, rel=0.05)


def test_snr_and_saturation_diagnostics(rng):
    cam = Camera(prnu=0.0, hot_pixel_rate=0.0)
    s = Sensor(cam, (64, 64), rng)
    bright = np.full((64, 64), 1e5)
    dim = np.full((64, 64), 10.0)
    assert s.snr(bright, 0.01) > s.snr(dim, 0.01)
    assert s.clipped_in_well(bright, 1.0) > 0.99
    assert s.clipped_in_well(dim, 1e-3) == 0.0
