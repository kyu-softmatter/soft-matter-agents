"""Nothing that crosses to the console imports anything that stays with the engine, and the
reverse (soft-matter-agents card 077).

plan.md 15 moves the console out of this tree. What reads and shows crosses: the server, the
data layer that reads soft-matter-agents' files (`agents/`), the assistant that only proposes,
the server's login and audit (`auth/`), and their tests. What measures, moves or lights stays:
the engine, focus, synth, records, the live focus score, the flat files and their tests. The
lists were drawn on card 077 and accepted by manager-microscope-20261003-1 and
manager-console-office-20261017-1.

This walks the import graph, not names: every `import` and `from ... import`, at module level
or inside a function, relative imports resolved, plus a literal `importlib.import_module`
string. And one edge no static import shows: `server.api.include_area_routers` mounts every
module in the `server/api/` package, so each module there counts as imported by `server.api`.
A route that needs the engine cannot sit in that package without the crossing app reaching it.
"""

import ast
from pathlib import Path

TREE = Path(__file__).resolve().parents[1]  # microscope_agent/autofocus/
PKG = TREE / "src" / "dino_autofocus"
TESTS = TREE / "tests"

#: Packages of dino_autofocus that cross to the console. Everything else in it stays.
CROSSING_PACKAGES = ("dino_autofocus.server", "dino_autofocus.agents",
                     "dino_autofocus.assistant", "dino_autofocus.auth")
#: Test folders that cross with them. Every other test file stays.
CROSSING_TEST_DIRS = ("agents", "assistant", "auth", "server")
#: The package whose modules the crossing app mounts by scanning it.
SCANNED_ROUTER_PACKAGE = "dino_autofocus.server.api"


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(PKG.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


MODULES = {_module_name(p): p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts}


def _crosses(module: str) -> bool:
    return any(module == c or module.startswith(c + ".") for c in CROSSING_PACKAGES)


def _known(name: str) -> str | None:
    """The longest dino_autofocus module that `name` names, or None."""
    while name:
        if name in MODULES:
            return name
        name = name.rpartition(".")[0]
    return None


def _imports(path: Path, here: str | None) -> set[str]:
    """dino_autofocus modules `path` imports. `here` is its module name, or None for a test."""
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
            names = [target] + [f"{target}.{a.name}" for a in node.names]
        elif (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "import_module"
              and node.args and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)):
            names = [node.args[0].value]
        for name in names:
            if name.startswith("dino_autofocus") and (known := _known(name)) and known != here:
                found.add(known)
    if here == SCANNED_ROUTER_PACKAGE:
        found |= {m for m in MODULES if m.startswith(SCANNED_ROUTER_PACKAGE + ".")
                  and m.count(".") == SCANNED_ROUTER_PACKAGE.count(".") + 1}
    return found


def _test_crosses(path: Path) -> bool:
    rel = path.relative_to(TESTS).parts
    return len(rel) > 1 and rel[0] in CROSSING_TEST_DIRS


def _edges():
    for module, path in MODULES.items():
        yield path, _crosses(module), _imports(path, module)
    for path in sorted(TESTS.rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path, _test_crosses(path), _imports(path, None)


def _rel(path: Path) -> str:
    return path.relative_to(TREE).as_posix()


def test_the_lists_name_real_packages():
    for package in CROSSING_PACKAGES:
        assert package in MODULES, package
    for folder in CROSSING_TEST_DIRS:
        assert (TESTS / folder).is_dir(), folder
    assert any(not _crosses(m) for m in MODULES), "nothing stays"


def test_nothing_that_crosses_imports_anything_that_stays():
    bad = sorted(f"{_rel(path)} -> {target}" for path, crosses, targets in _edges() if crosses
                 for target in targets if not _crosses(target))
    assert not bad, bad


def test_nothing_that_stays_imports_anything_that_crosses():
    bad = sorted(f"{_rel(path)} -> {target}" for path, crosses, targets in _edges()
                 if not crosses for target in targets if _crosses(target))
    assert not bad, bad
