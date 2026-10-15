"""The core install stays small: `[project].dependencies` is numpy + scipy, and every package
soft-matter-agents may take (engine, focus, records, agents, auth, assistant) imports with the
extras and the server group absent (docs/integration-sma.md P1)."""

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = {"numpy", "scipy"}
CORE_PACKAGES = ("engine", "focus", "records", "agents", "auth", "assistant")
# modules of the ml / hw / synth / plot extras and the server group
NOT_IN_CORE = ("torch", "torchvision", "sklearn", "joblib", "skimage", "yaml", "matplotlib",
               "pymmcore", "pymmcore_plus", "pydantic", "fastapi", "starlette", "uvicorn",
               "PIL", "anthropic", "gsd")


def _name(req: str) -> str:
    for sep in "<>=!~[; ":
        req = req.split(sep)[0]
    return req.strip().lower()


def test_core_dependencies_are_numpy_and_scipy_only():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert {_name(r) for r in project["dependencies"]} == CORE


def test_core_packages_import_without_extras():
    code = f"""
import importlib, importlib.abc, pkgutil, sys

class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in {NOT_IN_CORE!r}:
            raise ModuleNotFoundError(f"No module named {{name!r}} (blocked: not core)")
        return None

sys.meta_path.insert(0, Block())
for pkg in {CORE_PACKAGES!r}:
    mod = importlib.import_module("dino_autofocus." + pkg)
    for info in pkgutil.walk_packages(mod.__path__, mod.__name__ + "."):
        importlib.import_module(info.name)
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=300)
    assert out.returncode == 0, out.stderr
