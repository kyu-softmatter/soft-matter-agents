"""Engine operations (WP-C, WP-H, WP-I). Importing this package registers every operation with
the runner's registry (`engine.runner.OPERATIONS`), because each module registers its classes
with `@register_operation` when it is imported.

The server imports `engine.operations.sample_ops`, which runs this file first, so a running
server knows every operation without listing them itself. A new operation module is added to
`MODULES` below; tests/engine/test_operations_package.py fails if one is missing.

Importing an operation module only defines and registers classes: no backend, no hardware,
no file is touched until the runner starts an operation.
"""

from __future__ import annotations

from importlib import import_module

MODULES = (
    "status",
    "light_set",
    "edge_trace",
    "scan_4x",
    "focus_100x",
    "objective_change",
    "z_retract",
    "trap",
    "pattern_run",
    "hardware_scan",  # defines the hardware ops; the server registers them (register_hardware)
    "sample_ops",
    "sample_map",
)

for _name in MODULES:
    import_module(f"{__name__}.{_name}")
del _name
