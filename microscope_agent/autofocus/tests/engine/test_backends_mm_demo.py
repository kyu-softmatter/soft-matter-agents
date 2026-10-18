"""mm-demo backend: the Backend protocol on Micro-Manager's demo devices (T-023).

`TestMmDemoContract` runs T-015's `BackendContract` on mm-demo. The T-002 checks of
tests/engine/test_contract.py run here on both FakeBackend and mm-demo. mm-demo cases skip
without the demo adapters. Each test opens its own core and closes it; no test opens a
window.
"""

import json
import subprocess
import sys

import numpy as np
import pytest

from dino_autofocus.engine.backend import (
    GUARD_TOKEN,
    Backend,
    CommandPathRetired,
    UnguardedMotion,
)
from dino_autofocus.engine.backends.mm_demo import MmDemoBackend

T = GUARD_TOKEN  # tests stand in for engine.guards


@pytest.fixture(params=["fake"])
def backend(request):
    """The T-002 contract below, on the fake backend. mm-demo was the second case until card
    077 retired its core: its open refuses, so it has no case here any more."""
    return request.getfixturevalue(request.param)







# -- the T-002 contract, parametrised


# -- mm-demo only


def test_import_does_not_load_pymmcore():
    code = ("import sys, dino_autofocus.engine.backends.mm_demo; "
            "sys.exit('pymmcore_plus' in sys.modules or 'pymmcore' in sys.modules)")
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


#: card 077: every device write, and the demo core and its camera, refuse on mm-demo
RETIRED_CALLS = [
    ("open", (), {}), ("set_exposure", (10.0,), {}), ("set_roi", (0,), {}),
    ("start_stream", (), {}), ("stop_stream", (), {}),
    ("set_property", ("DiaLamp", "State", 1), {"token": GUARD_TOKEN}),
    ("lamp_on", (), {"token": GUARD_TOKEN}), ("lamp_off", (), {}),
    ("aura_line_on", ("GREEN", 5.0), {"token": GUARD_TOKEN}), ("aura_off", (), {}),
    ("all_off", (), {}), ("move_z", (2950.0,), {"token": GUARD_TOKEN}),
    ("move_xy", (1.0, 2.0), {"token": GUARD_TOKEN}),
    ("move_xy_rel", (1.0, 2.0), {"token": GUARD_TOKEN}),
    ("set_nosepiece", (0,), {"token": GUARD_TOKEN}), ("pfs_off", (), {"token": GUARD_TOKEN}),
]


@pytest.mark.parametrize(("name", "args", "kwargs"), RETIRED_CALLS)
def test_every_write_and_the_core_refuse_on_mm_demo(name, args, kwargs):
    b = MmDemoBackend()
    with pytest.raises(CommandPathRetired, match="plan.md 15, bc0f4848"):
        getattr(b, name)(*args, **kwargs)
    assert b.dev is None  # no demo core was opened


# -- the T-002 contract, on the fake backend (mm-demo's cases retired, card 077)


def test_meets_protocol_and_info_is_json(backend):
    assert isinstance(backend, Backend)
    json.dumps(backend.info().to_dict())
    assert backend.info().ceiling_adu >= 4095


def test_refuses_unguarded_motion(backend):
    for call in (lambda: backend.move_z(3000.0, token=None),
                 lambda: backend.move_xy(0.0, 0.0, token=None),
                 lambda: backend.set_nosepiece(0, token=None),
                 lambda: backend.pfs_off(token=None)):
        with pytest.raises(UnguardedMotion):
            call()


def test_light_read_back_and_off(backend):
    assert all(r.verified for r in backend.aura_line_on("GREEN", 1, token=T))
    assert backend.light_state()["Aura"] == "1"
    assert all(r.verified for r in backend.all_off())
    assert backend.light_state()["Aura"] == "0" and backend.light_state()["DiaLamp"] == "0"


def test_guarded_z_reads_back_in_bench_coordinates(backend):
    assert backend.move_z(2950.0, token=T) == pytest.approx(2950.0)
    assert backend.positions().z_um == pytest.approx(2950.0)
    f = backend.snap()
    assert f.image.dtype == np.uint16 and f.image.ndim == 2
    assert f.z_um == pytest.approx(2950.0)
