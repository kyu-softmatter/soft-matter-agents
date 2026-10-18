"""engine.operations: importing the package registers every operation with the runner, and an
import touches nothing. The console's server no longer imports it (soft-matter-agents card
077), so the server-side checks that stood here went with the cut."""

from __future__ import annotations

import json
import pkgutil
import subprocess
import sys

import dino_autofocus.engine.operations as ops
from dino_autofocus.engine.runner import OPERATIONS

# operations-spec op names (sections 1-8, ui-spec light_set) and the sample ops (T-027)
SPEC_OPS = {"status", "scan_4x", "objective_change", "focus_100x", "edge_trace", "light_set",
            "z_retract",  # T-039
            "sample_map", "goto_xy", "map_flag", "map_flag_retire", "candidate_confirm",
            "candidate_reject"}
SAMPLE_OPS = {"sample_open", "sample_new", "sample_geometry_set", "loading_confirm_person",
              "loading_check_image", "boundary_mark", "boundary_undo", "boundary_reset"}
# in the spec, not registered by the import: hardware_scan's module is imported (MODULES); the
# server registers its ops with register_hardware (T-028 / T-009g)
PENDING = {"hardware_scan": "server register_hardware"}


def test_every_module_in_the_package_is_imported() -> None:
    found = {m.name for m in pkgutil.iter_modules(ops.__path__) if not m.name.startswith("_")}
    assert found == set(ops.MODULES), "add the new module to engine/operations MODULES"


def test_every_operation_is_registered() -> None:
    names = set(OPERATIONS.names())
    assert names >= SPEC_OPS | SAMPLE_OPS
    assert "lights_off" not in names  # a command kind, built into the runner
    assert not (set(PENDING) & SPEC_OPS)


def test_importing_the_package_alone_registers_them_and_touches_nothing(tmp_path) -> None:
    """A fresh interpreter that imports only engine.operations sees every operation; the
    import writes no file."""
    code = ("import json; import dino_autofocus.engine.operations; "
            "from dino_autofocus.engine.runner import OPERATIONS; "
            "print(json.dumps(OPERATIONS.names()))")
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True,
                         text=True, timeout=300, check=True)
    names = set(json.loads(out.stdout.strip().splitlines()[-1]))
    assert names >= SPEC_OPS | SAMPLE_OPS
    assert list(tmp_path.iterdir()) == []
