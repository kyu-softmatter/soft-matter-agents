"""Load an imaging system from a YAML file.

The presets in :mod:`dino_autofocus.synth.optics.system` cover common objectives, but a real
microscope is never exactly one of them: the tube lens, the coverglass, the
camera and the emission filter all differ, and those differences move best
focus by micrometres (see :class:`dino_autofocus.synth.sim.render.FocalShift`).  A dataset
generated for a specific instrument therefore has to start from that
instrument's numbers.

Only the fields that matter need to be given; everything else falls back to the
named preset, or to the dataclass defaults if no preset is named.  What matters
most, in rough order:

1. ``objective.na`` and ``objective.magnification`` -- set resolution, depth of
   field and the sampling ratio.
2. ``camera.pixel_size`` -- with the magnification, sets the sample-plane pixel
   and hence whether the PSF is sampled at all.
3. ``stack.n_sample`` against ``objective.n_immersion`` -- sets the
   depth-dependent focal shift and the spherical aberration that makes the sign
   of defocus recoverable.
4. ``stack.t_glass`` against ``t_glass_design`` -- a constant focus offset, and
   a large one: at 60x a 8 um error moves best focus by about 8 um.
5. ``illumination.wavelength`` -- the emission band actually reaching the camera.
"""
from __future__ import annotations

from dataclasses import asdict, fields
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .system import (Camera, Illumination, ImagingSystem, Objective,
                     SampleStack, preset)

_SECTIONS = {"objective": Objective, "camera": Camera,
             "stack": SampleStack, "illumination": Illumination}


def _build(cls, defaults: Dict[str, Any], overrides: Dict[str, Any], where: str):
    known = {f.name for f in fields(cls)}
    unknown = set(overrides) - known
    if unknown:
        raise ValueError(
            f"{where}: unknown field(s) {sorted(unknown)}; "
            f"valid fields are {sorted(known)}")
    return cls(**{**defaults, **overrides})


def system_from_dict(spec: Dict[str, Any]) -> ImagingSystem:
    """Build an :class:`ImagingSystem` from a nested dict.

    ``base`` names a preset to inherit from; any section given overrides it
    field by field, so a file need only state what differs from the preset.
    """
    spec = dict(spec or {})
    base_name = spec.pop("base", None)
    name = spec.pop("name", base_name or "custom")
    base = preset(base_name) if base_name else None

    parts = {}
    for section, cls in _SECTIONS.items():
        defaults = asdict(getattr(base, section)) if base is not None else {}
        parts[section] = _build(cls, defaults, dict(spec.pop(section, {}) or {}),
                                f"section '{section}'")
    if spec:
        raise ValueError(
            f"unknown top-level key(s) {sorted(spec)}; expected any of "
            f"'name', 'base', {sorted(_SECTIONS)}")

    return ImagingSystem(objective=parts["objective"], camera=parts["camera"],
                         stack=parts["stack"], illumination=parts["illumination"],
                         name=str(name))


def load_system(path: str | Path) -> ImagingSystem:
    """Read a system from YAML and report what it implies for sampling."""
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    return system_from_dict(data.get("system", data))


def save_system(system: ImagingSystem, path: str | Path) -> None:
    payload = {"system": {"name": system.name,
                          **{k: asdict(getattr(system, k)) for k in _SECTIONS}}}
    Path(path).write_text(yaml.safe_dump(payload, sort_keys=False))


def describe(system: ImagingSystem) -> str:
    """Human-readable sampling summary, with the warnings that matter."""
    d = system.describe()
    lines = [
        f"{system.name}:",
        f"  NA {d['na']:.3f}, {d['magnification']:g}x, "
        f"immersion n = {system.stack.n_immersion:.3f}",
        f"  sample-plane pixel   {d['pixel_size_sample_um'] * 1000:7.1f} nm",
        f"  Abbe resolution      {d['abbe_resolution_um'] * 1000:7.1f} nm",
        f"  depth of field       {d['depth_of_field_um'] * 1000:7.1f} nm",
        f"  Nyquist pixel        {d['nyquist_pixel_um'] * 1000:7.1f} nm",
        f"  sampling ratio       {d['sampling_ratio']:7.2f} "
        f"({'undersampled' if d['sampling_ratio'] > 1 else 'oversampled'})",
        f"  PSF oversampling     {d['oversampling']:7d}x",
    ]
    if d["sampling_ratio"] > 2.0:
        lines.append("  NOTE: the camera undersamples the PSF by more than 2x. That is "
                     "a real property of this instrument, not a simulation flaw, but "
                     "it caps how well any method can localise focus.")
    if abs(system.stack.n_sample - system.stack.n_immersion) < 1e-6:
        lines.append("  NOTE: sample and immersion indices are equal, so there is no "
                     "depth-induced spherical aberration -- and therefore no "
                     "single-frame sign information. Use a two-plane policy or add "
                     "deliberate astigmatism.")
    if abs(system.stack.t_glass - system.stack.t_glass_design) > 1e-6:
        lines.append(f"  NOTE: coverglass is {system.stack.t_glass - system.stack.t_glass_design:+.1f} um "
                     "from design, which shifts best focus by micrometres.")
    return "\n".join(lines)
