"""Load the flat files in `microscope_agent/src/` (docs/integration-sma.md section 9).

Those files are laid out as they will sit in soft-matter-agents: flat, no package, siblings
loaded by path under `_mic_<stem>`. This module loads them under the same names and
registers each one again under its old `dino_autofocus` dotted name, so both import styles
get one module object (one `Verdict` enum, one `FrameStats` class).

A wheel carries the files in `dino_autofocus/_microscope_agent_src/` (pyproject
force-include); a source checkout or editable install reads them from the repository.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_PACKAGE = Path(__file__).resolve().parent
DIRS = (_PACKAGE / "_microscope_agent_src", _PACKAGE.parents[1] / "microscope_agent" / "src")


def src_dir() -> Path:
    for d in DIRS:
        if (d / "focus_classical.py").is_file():
            return d
    raise ImportError(f"microscope_agent/src not found in {[str(d) for d in DIRS]}")


def load(stem: str, alias: str) -> ModuleType:
    """`microscope_agent/src/<stem>.py` as `_mic_<stem>`, also registered as `alias`."""
    name = f"_mic_{stem}"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, src_dir() / f"{stem}.py")
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {stem}.py from {src_dir()}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    sys.modules[alias] = module
    return module
