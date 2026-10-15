"""Loading a specific instrument from YAML."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

yaml = pytest.importorskip("yaml")

from dino_autofocus.synth.optics.config import describe, load_system, save_system, system_from_dict
from dino_autofocus.synth.optics.system import preset
from dino_autofocus.synth.sim.scene import RandomisationConfig, draw_system

CONFIGS = Path(__file__).parents[2] / "configs"


def test_template_loads_and_roundtrips(tmp_path):
    s = load_system(CONFIGS / "lab_template.yaml")
    assert s.objective.na == pytest.approx(1.30)
    assert s.objective.n_immersion == pytest.approx(1.406)
    out = tmp_path / "rt.yaml"
    save_system(s, out)
    assert load_system(out).to_dict() == s.to_dict()


def test_base_preset_is_inherited_field_by_field():
    """A file should only have to state what differs from the preset."""
    base = preset("60x_oil")
    s = system_from_dict({"base": "60x_oil", "objective": {"na": 1.2}})
    assert s.objective.na == pytest.approx(1.2)
    assert s.objective.magnification == base.objective.magnification
    assert s.camera.pixel_size == base.camera.pixel_size
    assert s.illumination.wavelength == base.illumination.wavelength


def test_unknown_fields_are_rejected_loudly():
    """A typo in an instrument file must not be silently ignored -- it would
    mean generating a dataset for the wrong microscope."""
    with pytest.raises(ValueError, match="unknown field"):
        system_from_dict({"base": "60x_oil", "objective": {"numerical_aperture": 1.2}})
    with pytest.raises(ValueError, match="unknown top-level"):
        system_from_dict({"base": "60x_oil", "objectiv": {}})


def test_invalid_physics_is_rejected():
    with pytest.raises(ValueError, match="n_immersion"):
        system_from_dict({"objective": {"na": 1.4, "magnification": 60,
                                        "n_immersion": 1.0}})


def test_describe_warns_about_index_matching():
    s = system_from_dict({"base": "60x_oil", "stack": {"n_sample": 1.518}})
    text = describe(s)
    assert "no depth-induced spherical aberration" in text
    assert "sign information" in text


def test_describe_warns_about_coverglass_error():
    s = system_from_dict({"base": "60x_oil", "stack": {"t_glass": 178.0}})
    assert "from design" in describe(s)


def test_locked_optics_keeps_the_instrument_fixed(rng):
    """Jittering NA and wavelength is right for a model that must work on any
    microscope, and wrong when the instrument is known."""
    custom = load_system(CONFIGS / "lab_template.yaml")
    cfg = RandomisationConfig(custom_system=custom, lock_optics=True)
    for _ in range(6):
        s, ab = draw_system(rng, cfg)
        assert s.objective.na == pytest.approx(custom.objective.na)
        assert s.illumination.wavelength == pytest.approx(custom.illumination.wavelength)
        assert s.stack.n_sample == pytest.approx(custom.stack.n_sample)
        # but the photon budget and aberrations still vary session to session
        assert s.illumination.photons_per_emitter > 0
    assert len(ab) > 0


def test_unlocked_optics_jitters_around_the_instrument(rng):
    custom = load_system(CONFIGS / "lab_template.yaml")
    cfg = RandomisationConfig(custom_system=custom, lock_optics=False)
    nas = [draw_system(rng, cfg)[0].objective.na for _ in range(12)]
    assert len(set(np.round(nas, 6))) > 1
    assert all(n <= custom.objective.na + 1e-9 for n in nas)
