"""Shared fixtures.

Everything here is sized for speed: small fields of view, few planes, coarse
grids.  The point of these tests is to pin down physics invariants and catch
regressions, not to produce publication-quality PSFs, and a suite nobody waits
for is a suite nobody runs.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dino_autofocus.synth.optics.psf import PSFEngine
from dino_autofocus.synth.optics.system import SampleStack, preset

# psf-autofocus pytest.ini, scoped to this directory; the first filter wins
WARNING_FILTERS = (
    "ignore:.*labelling density.*:RuntimeWarning",
    "ignore:.*wrap-free.*:RuntimeWarning",
    "error::RuntimeWarning",
)


def pytest_collection_modifyitems(items):
    here = Path(__file__).parent
    for item in items:
        if here in item.path.parents:
            for f in WARNING_FILTERS:
                item.add_marker(pytest.mark.filterwarnings(f))


@pytest.fixture(scope="session")
def rng():
    return np.random.default_rng(12345)


@pytest.fixture(scope="session")
def sys_20x():
    return preset("20x_air")


@pytest.fixture(scope="session")
def sys_matched():
    """60x oil with the sample index equal to the immersion: symmetric PSF."""
    base = preset("60x_oil")
    return base.evolve(stack=SampleStack(
        n_sample=base.objective.n_immersion,
        n_glass=base.stack.n_glass,
        n_immersion=base.objective.n_immersion,
        n_glass_design=base.stack.n_glass_design,
        n_immersion_design=base.stack.n_immersion_design,
    ))


@pytest.fixture(scope="session")
def eng_20x(sys_20x):
    return PSFEngine(sys_20x, fov_px=48, pad=2, workers=1, cache_size=8)


@pytest.fixture(scope="session")
def eng_matched(sys_matched):
    return PSFEngine(sys_matched, fov_px=48, pad=2, workers=1, cache_size=8)
