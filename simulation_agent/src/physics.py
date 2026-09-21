"""The two facts both backends need, in one place so they cannot disagree.

Neither of these is the estimator and neither is policy. `stokes_einstein` is
the relation an overdamped backend needs to turn a bath and a particle into a
diffusivity, and both the mock and the engine need it -- the mock to set its
noise amplitude, the engine to set a drag and to derive its own time unit. One
copy each would be one formula in two places (11-11), and the copy that drifts
is never the one anyone is looking at.

**A constant is not policy.** Reading `k_B` out of the registry does not put an
envelope in a backend (4.6.5); it keeps the number from being retyped, which is
what D7 says about every other number here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

_UNITS = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "units.json").read_text())
K_B = float(_UNITS["constants"]["k_B"]["value"])


def stokes_einstein(temperature: float, viscosity: float, diameter: float) -> float:
    """Translational diffusivity of a sphere, in SI.

    **A backend derives this rather than being handed it.** The plan carries a
    `diffusivity`, and that number is what the run is checked against -- so
    feeding it in as an input would make the success criterion compare the run
    against a value the run was given. What goes in is the bath and the
    particle; what comes out is a diffusivity that can disagree.
    """
    return K_B * temperature / (3.0 * np.pi * viscosity * diameter)
