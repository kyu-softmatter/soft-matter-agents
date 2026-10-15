"""Load the flat files: dino's own in `microscope_agent/src/`, and the focus core from
soft-matter-agents' `microscope_agent/src/` (docs/integration-sma.md section 9).

Those files are flat, no package, siblings loaded by path under `_mic_<stem>`. This module
loads them under the same names and registers each one again under its old
`dino_autofocus` dotted name, so both import styles get one module object (one `Verdict`
enum, one `FrameStats` class).

The focus core -- `focus_classical`, `focus_verdict` and `focus_search` -- is no longer
mirrored here (soft-matter-agents card 073). This tree was imported into soft-matter-agents
at `microscope_agent/autofocus/`, whose `microscope_agent/src/` holds the originals, and
`path_of` is the one place that reaches across to them. That fixed in-repo path holds while
this tree sits at `microscope_agent/autofocus/`. Before loading any of dino's own flat
files, `load` loads the core from there, so a flat file's own sibling lookup by name finds
the originals already in `sys.modules`; no copy sits beside them for it to find instead.

A wheel carries dino's own flat files in `dino_autofocus/_microscope_agent_src/` (pyproject
force-include) and not the core, so only a checkout inside soft-matter-agents can load the
core.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_PACKAGE = Path(__file__).resolve().parent
DIRS = (_PACKAGE / "_microscope_agent_src", _PACKAGE.parents[1] / "microscope_agent" / "src")
#: The focus core, held by soft-matter-agents, in load order (each needs the ones before it).
CORE = ("focus_classical", "focus_verdict", "focus_search")
#: soft-matter-agents' `microscope_agent/src/`: this package is
#: `microscope_agent/autofocus/src/dino_autofocus/`.
ORIGINALS = _PACKAGE.parents[2] / "src"


def src_dir() -> Path:
    """The directory of dino's own flat files."""
    for d in DIRS:
        if (d / "focus_verdict_model.py").is_file():
            return d
    raise ImportError(f"microscope_agent/src not found in {[str(d) for d in DIRS]}")


def path_of(stem: str) -> Path:
    """Where the flat file `<stem>.py` is read from: a core stem from soft-matter-agents'
    originals, every other stem from dino's own directory."""
    if stem in CORE:
        return ORIGINALS / f"{stem}.py"
    return src_dir() / f"{stem}.py"


def _exec(stem: str) -> ModuleType:
    name = f"_mic_{stem}"
    module = sys.modules.get(name)
    if module is not None:
        return module
    path = path_of(stem)
    if not path.is_file():
        raise ImportError(f"{stem}.py not found at {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {stem}.py from {path.parent}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def load_core() -> None:
    """Load the focus core from the originals, so every later sibling lookup reuses them."""
    for stem in CORE:
        _exec(stem)


def load(stem: str, alias: str) -> ModuleType:
    """The flat file `<stem>.py` as `_mic_<stem>`, also registered as `alias`."""
    load_core()
    module = _exec(stem)
    sys.modules[alias] = module
    return module
