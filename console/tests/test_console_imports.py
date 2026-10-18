"""Nothing under console/ reaches outside it (card 001, after soft-matter-agents card 077).

The cut's own walk, `microscope_agent/autofocus/tests/test_console_cut_imports.py`, resolves an
import to the longest module it knows and drops the rest. Here that would hide the very failure
this test is for: a module that imported the engine side and finds it gone. So a
`dino_autofocus` import that names no module under `console/src/` is reported, not dropped.

Every `import` and `from ... import`, at module level or inside a function, with relative imports
resolved, plus a literal `importlib.import_module` string. One edge no static import shows:
`server.api.include_area_routers` mounts every module in the `server/api/` package.
"""

import ast
import importlib.util
from pathlib import Path

TREE = Path(__file__).resolve().parents[1]  # console/
PKG = TREE / "src" / "dino_autofocus"
TESTS = TREE / "tests"

#: The only subpackages of dino_autofocus that live under console/.
PACKAGES = {"server", "agents", "assistant", "auth"}
SCANNED_ROUTER_PACKAGE = "dino_autofocus.server.api"


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(PKG.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


MODULES = {_module_name(p): p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts}


def _dino_names(path: Path, here: str | None) -> set[str]:
    """Every `dino_autofocus` name `path` imports, resolved but not looked up."""
    is_package = path.name == "__init__.py"
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if here is None:
                    continue  # a test's relative import stays inside the tests
                base = here.split(".") if is_package else here.split(".")[:-1]
                base = base[: len(base) - node.level + 1] if node.level > 1 else base
                target = ".".join(base + ([node.module] if node.module else []))
            else:
                target = node.module or ""
            # the module itself must exist; `target.name` may be a module or an attribute
            names = [target]
        elif (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "import_module"
              and node.args and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)):
            names = [node.args[0].value]
        found |= {n for n in names if n == "dino_autofocus" or n.startswith("dino_autofocus.")}
    return found


def _files():
    for module, path in MODULES.items():
        yield path, module
    for path in sorted(TESTS.rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path, None


def _rel(path: Path) -> str:
    return path.relative_to(TREE).as_posix()


def test_only_the_four_packages_are_here():
    here = {m.split(".")[1] for m in MODULES if m.count(".") >= 1}
    assert here == PACKAGES, sorted(here ^ PACKAGES)
    for folder in sorted(p.name for p in TESTS.iterdir() if p.is_dir() and p.name != "__pycache__"):
        assert folder in PACKAGES, folder


def test_every_dino_autofocus_import_names_a_module_under_console_src():
    unresolved = sorted(f"{_rel(path)} -> {name}" for path, here in _files()
                        for name in _dino_names(path, here) if name not in MODULES)
    assert not unresolved, unresolved


def test_the_router_package_scan_finds_modules_that_exist():
    scanned = sorted(m for m in MODULES if m.startswith(SCANNED_ROUTER_PACKAGE + ".")
                     and m.count(".") == SCANNED_ROUTER_PACKAGE.count(".") + 1)
    assert scanned, "server/api/ holds no modules to mount"


def test_the_environment_cannot_open_a_microscope_core():
    """No torch and no Micro-Manager binding in this environment (card 001)."""
    for name in ("pymmcore", "pymmcore_plus", "torch", "torchvision"):
        assert importlib.util.find_spec(name) is None, name
