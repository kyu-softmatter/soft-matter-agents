"""The focus core is read from soft-matter-agents' originals, and no copy sits beside it.

`dino_autofocus._flat.path_of` is the one place that reaches from this tree, imported at
`microscope_agent/autofocus/`, to soft-matter-agents' `microscope_agent/src/`
(soft-matter-agents card 073). These tests pin that: the three core stems resolve to the
originals, every other stem to dino's own directory, the modules every importer shares are
the originals, and dino's directory holds no copy that a sibling lookup could find instead.
"""

import sys
from pathlib import Path

from dino_autofocus import _flat

TREE = Path(__file__).resolve().parents[1]  # microscope_agent/autofocus/
SMA = TREE.parents[1]  # the soft-matter-agents checkout this tree was imported into
ORIGINALS = SMA / "microscope_agent" / "src"
DINO_FLAT = TREE / "microscope_agent"


def test_the_tree_sits_where_the_resolver_expects():
    assert TREE.parent.name == "microscope_agent" and TREE.name == "autofocus"
    assert (SMA / "contracts" / "validate.py").is_file()


def test_core_stems_resolve_to_the_originals():
    assert _flat.ORIGINALS.resolve() == ORIGINALS.resolve()
    for stem in _flat.CORE:
        path = _flat.path_of(stem)
        assert path.resolve() == (ORIGINALS / f"{stem}.py").resolve(), stem
        assert path.is_file(), path


#: The core's three tests, held by soft-matter-agents beside the originals.
CORE_TESTS = ("test_focus_core.py", "test_focus_contract.py", "test_focus_search.py")


def test_no_copy_of_the_core_or_its_tests_sits_in_dinos_tree():
    copies = [DINO_FLAT / "src" / f"{stem}.py" for stem in _flat.CORE]
    copies += [DINO_FLAT / "tests" / name for name in CORE_TESTS]
    assert not [p for p in copies if p.exists()]
    assert all((SMA / "microscope_agent" / "tests" / name).is_file() for name in CORE_TESTS)


def test_other_stems_resolve_to_dinos_own_directory():
    for stem in ("focus_verdict_model", "focus_run_log", "focus_step_rules", "map_geometry"):
        path = _flat.path_of(stem)
        assert path.parent.resolve() == (DINO_FLAT / "src").resolve(), stem
        assert path.is_file(), path


def test_every_importer_shares_the_originals():
    from dino_autofocus import focus

    model, run_log = focus.verdict_model, focus.sma_event
    assert focus.classical is sys.modules["_mic_focus_classical"]
    assert focus.verdict is sys.modules["_mic_focus_verdict"]
    for stem in _flat.CORE:
        module = sys.modules[f"_mic_{stem}"]
        assert Path(module.__file__).resolve() == (ORIGINALS / f"{stem}.py").resolve(), stem
    assert model._verdict is sys.modules["_mic_focus_verdict"]
    assert run_log._verdict is sys.modules["_mic_focus_verdict"]
