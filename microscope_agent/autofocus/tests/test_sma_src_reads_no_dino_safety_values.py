"""soft-matter-agents' own microscope code never reaches dino's guards or patterns.

The librarian ruled dino's guard windows, retract heights, pattern ranges and focus distances
the envelope's (soft-matter-agents card 075; `safety_rows` in its store source
`src_dino_autofocus_numbers_95eee95`). In soft-matter-agents a limit binds only from
`microscope_agent/envelope/safety.json`, which the person writes, so its agent code must not
pick one up from this tree. This test reads every Python file under that repository's
`microscope_agent/src/` and fails on any import of `dino_autofocus`'s guards or patterns
modules, and on any string that names those files, which is how a by-path load would reach
them.
"""

import ast
from pathlib import Path

TREE = Path(__file__).resolve().parents[1]  # microscope_agent/autofocus/
SMA_SRC = TREE.parents[1] / "microscope_agent" / "src"

#: dino's modules that hold the safety rows: the engine's guards and the patterns.
FORBIDDEN_MODULES = ("dino_autofocus.engine.guards", "dino_autofocus.engine.patterns",
                     "dino_autofocus.engine.operations.pattern_run",
                     "dino_autofocus.server.api.patterns")
FORBIDDEN_FILES = ("guards.py", "patterns.py", "pattern_run.py")


def _hits(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
        out += [f"imports {n}" for n in names
                if any(n == m or n.startswith(m + ".") for m in FORBIDDEN_MODULES)]
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value.replace("\\", "/")
            if "autofocus" in text and any(f in text for f in FORBIDDEN_FILES):
                out.append(f"names {node.value!r}")
    return [f"{path.relative_to(SMA_SRC).as_posix()}:{h}" for h in out]


def test_sma_microscope_src_imports_no_dino_guard_or_pattern():
    files = sorted(SMA_SRC.rglob("*.py"))
    assert files, f"nothing to check under {SMA_SRC}"
    hits = [h for p in files if "__pycache__" not in p.parts for h in _hits(p)]
    assert not hits, hits
