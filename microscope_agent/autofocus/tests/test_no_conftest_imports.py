"""Guard (T-015e): no test module imports a conftest by name.

Several test directories have a conftest.py, and pytest puts each directory on sys.path, so
importing a conftest by name resolves to whichever one loaded first and breaks when
directories run in another order (T-015d, T-015e). Shared fakes live in uniquely named
modules instead (tests/engine/engine_fakes.py, tests/e2e/e2e_helpers.py,
tests/server/server_fakes.py). Docstrings and comments may mention conftest; only import
statements count.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def conftest_imports(root: Path = TESTS) -> list[str]:
    hits = []
    for p in sorted(root.rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                continue
            if any(n == "conftest" or n.endswith(".conftest") for n in names):
                hits.append(f"{p.relative_to(root)}:{node.lineno}")
    return hits


def test_no_test_module_imports_a_conftest():
    assert conftest_imports() == []


def test_the_guard_sees_both_import_forms(tmp_path):
    name = "conf" + "test"  # split so a plain git grep for the pattern stays empty
    (tmp_path / "a.py").write_text(f"from {name} import X\n", encoding="utf-8")
    (tmp_path / "b.py").write_text(f"import {name}\n", encoding="utf-8")
    (tmp_path / "c.py").write_text(f'"""from {name} import X is not an import"""\n',
                                   encoding="utf-8")
    assert conftest_imports(tmp_path) == ["a.py:1", "b.py:1"]
