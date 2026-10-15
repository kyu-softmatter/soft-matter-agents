"""Load the focus core from soft-matter-agents' originals before any test module is collected.

The flat tests under `microscope_agent/tests/` load their siblings by path and reuse a name
already in `sys.modules`. The focus core is not beside them any more (soft-matter-agents card
073), so it is loaded here, through the package's one resolver, `dino_autofocus._flat`.

In `pytest_sessionstart` and not at import: `tests/conftest.py` asks for one BLAS thread
before numpy is imported, and the core imports numpy. The same ask is repeated here for a run
that names only `microscope_agent/tests`, where that file is not loaded.
"""

import os


def pytest_sessionstart(session):
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    from dino_autofocus import _flat

    _flat.load_core()
