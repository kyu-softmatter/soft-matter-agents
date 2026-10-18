"""D-00, the safety baseline (docs/integration-sma-workplan.md section 3.1): the facts every later
merge item stands on, pinned in one place so that a lock flip, a widened allow-list or a new
position-write call site becomes a failing test instead of a diff somebody has to notice.

Lock values at the time of writing, with where they live:

- ``engine/backends/mm_real.py:88``  ``BENCH_MOTION = "LOCKED"`` (T-036; only the user flips it)
- ``engine/guards.py:84``            ``BENCH_APPROACH = "MEASURED"``
  (the partial unlock of 2026-10-02, by the user)
- ``engine/guards.py:61-62``         ``SAMPLE_Z_WINDOW_UM = (2800, 3200)``, retract 0, return 2800
- ``engine/guards.py:68``            ``FREE_WD_UM`` -> ``approach_ceiling_um``: 4x, 10x and 20x may
  climb to 3200 um; 40x-WI, 60x-Oil, 100x-Oil, an unknown or unreadable lens stop at 2800 um

The behaviour behind each fact is tested beside its code (``test_backends_mm_real_lock.py``,
``test_operations_bench_approach.py``, ``test_tweezers.py``, ``test_mock_bench_safety.py``,
moved from ``e2e/test_e2e_safety.py`` by soft-matter-agents card 077); this
module asserts the baseline itself and one thing nothing else does: the inventory of direct
Micro-Manager write calls in the tree.

Since soft-matter-agents card 077 (plan.md 15 at bc0f4848) the inventory is EMPTY, in the
package and in scripts: dino's engine command path is retired, so no module here moves,
lights, sets a property or a camera setting, starts a stream or loads a configuration
through a Micro-Manager core. Card 077 is the D-05 this docstring used to name ("dropping
the bench motion path once soft-matter-agents owns it"), and it rewrote this test to assert
absence. Every write method of the mm-real, mm-demo and replay backends, and the open of the
two that would open a core, is a single raise of ``CommandPathRetired``. ``BENCH_MOTION``
still ships "LOCKED", with nothing left behind it.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from dino_autofocus.engine import guards
from dino_autofocus.engine.backend import GUARD_TOKEN, SIMULATED_KINDS, is_bench
from dino_autofocus.engine.backends import mm_real
from dino_autofocus.engine.backends.tweez300 import Tweez300NotWired, Tweez300Tweezers
from dino_autofocus.engine.guards import GuardError, PiezoAxis, approach_ceiling_um
from dino_autofocus.engine.piezo import PiezoInfo, PiezoState
from dino_autofocus.engine.stream import BackendStream

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "dino_autofocus"
SCRIPTS = ROOT / "scripts"

# Every MMCore call that moves something or can (the same family soft-matter-agents refuses by
# name in its device wrapper), and since card 077 every other device write too: a property, a
# shutter, a camera setting, a sequence, loading a configuration. As an attribute call, so a
# word inside a string does not count. MMCore's `home` is left out: `Path.home()` is the same
# spelling and nothing here homes a stage.
WRITE_CALL = re.compile(
    r"\.(setPosition|setXYPosition|setRelativePosition|setRelativeXYPosition|setOrigin\w*"
    r"|setState|setStateLabel|setConfig|enableContinuousFocus|setAutoFocusOffset"
    r"|fullFocus|incrementalFocus"
    r"|setProperty|setShutterOpen|setAutoShutter|setExposure|setROI|clearROI"
    r"|startContinuousSequenceAcquisition|startSequenceAcquisition|stopSequenceAcquisition"
    r"|loadSystemConfiguration|setDeviceAdapterSearchPaths)\("
)

# -- the two locks --------------------------------------------------------------------------


def test_bench_motion_ships_locked():
    assert mm_real.BENCH_MOTION == "LOCKED"
    assert mm_real._motion_state().startswith("LOCKED: ")


def test_bench_approach_is_the_partial_unlock_with_per_lens_ceilings():
    assert guards.BENCH_APPROACH == "MEASURED"
    assert guards.SAMPLE_Z_WINDOW_UM == (2800.0, 3200.0)
    assert (guards.RETRACT_Z_UM, guards.RETURN_Z_UM) == (0.0, 2800.0)
    for lens in ("4x", "10x", "20x"):
        assert approach_ceiling_um(lens) == 3200.0, lens
    for lens in ("40x-WI", "60x-Oil", "100x-Oil", guards.UNKNOWN_OBJECTIVE, "no such lens", None):
        assert approach_ceiling_um(lens) == 2800.0, lens


# -- the bench decision fails safe ----------------------------------------------------------


@pytest.mark.parametrize(
    ("info", "bench"),
    [
        (None, True),
        (SimpleNamespace(kind="mock", bench=False), False),
        (SimpleNamespace(kind="mm-demo", bench=False), False),
        (SimpleNamespace(kind="replay", bench=False), False),
        (SimpleNamespace(kind="mm-real", bench=False), True),  # the kind decides, not the flag
        (SimpleNamespace(kind="mock", bench=True), True),
        (SimpleNamespace(kind="mock", bench=None), True),
        (SimpleNamespace(kind="mock"), True),  # no flag at all: the bench
        (SimpleNamespace(kind=["mock"], bench=False), True),  # unhashable kind: the bench
    ],
)
def test_is_bench_fails_safe(info, bench):
    assert is_bench(info) is bench


def test_the_simulated_kinds_are_the_four_known_ones():
    assert {"mock", "replay", "mm-demo", "fake"} == SIMULATED_KINDS


# -- the device paths that must refuse today -------------------------------------------------


def test_tweez300_refuses_every_call_and_counts_as_the_bench():
    tw = Tweez300Tweezers()
    assert tw.info().bench is True
    assert tw.info().n_traps == 0
    with pytest.raises(Tweez300NotWired):
        tw.traps()
    with pytest.raises(Tweez300NotWired):
        tw.move_trap(0, 0.0, 0.0, 0.0, token=GUARD_TOKEN)
    with pytest.raises(Tweez300NotWired):
        tw.set_trap(0, True, token=GUARD_TOKEN)


class _Piezo:
    def __init__(self, bench):
        self._info = PiezoInfo(kind="fake", travel_um={"x": (0.0, 1.0), "y": (0.0, 1.0),
                                                       "z": (0.0, 1.0)}, bench=bench)

    def info(self):
        return self._info

    def position(self):
        return PiezoState(0.0, 0.0, 0.0)

    def move(self, x_um, y_um, z_um, *, token):  # pragma: no cover - never reached on the bench
        return PiezoState(x_um, y_um, z_um)


def test_piezo_axis_refuses_anything_but_a_simulated_piezo():
    with pytest.raises(GuardError):
        PiezoAxis(_Piezo(bench=True)).allowed()
    with pytest.raises(GuardError):
        PiezoAxis(_Piezo(bench=None)).allowed()
    with pytest.raises(GuardError):
        PiezoAxis(None).allowed()
    assert PiezoAxis(_Piezo(bench=False)).allowed() == {"x": (0.0, 1.0), "y": (0.0, 1.0),
                                                         "z": (0.0, 1.0)}


def test_the_live_stream_is_for_the_mock_only():
    refused = (
        SimpleNamespace(kind="mm-real", bench=True),
        SimpleNamespace(kind="mm-demo", bench=False),
        SimpleNamespace(kind="replay", bench=False),
        SimpleNamespace(kind="mock", bench=True),
    )
    for info in refused:
        with pytest.raises(ValueError):
            BackendStream.for_backend(SimpleNamespace(info=lambda info=info: info))
    mock = SimpleNamespace(info=lambda: SimpleNamespace(kind="mock", bench=False))
    stream = BackendStream.for_backend(mock)
    assert isinstance(stream, BackendStream)


# -- the inventory of direct MMCore write calls -----------------------------------------------


def _call_sites(folder: Path) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted(folder.rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("#"):
                continue
            for m in WRITE_CALL.finditer(line):
                found.setdefault(path.relative_to(ROOT).as_posix(), set()).add(m.group(1))
    return found


# R-05 deleted the legacy bench scripts (scan_4x, edge_track, find_particle_z and eight more;
# in git history), so scripts/ holds no direct MMCore write at all; a new one fails here
# (OD-35, user 2026-10-06).
SCRIPTS_BUCKET: dict[str, set[str]] = {}

#: the Backend protocol's writes, as card 077 retired them on the three backends
RETIRED_WRITES = {"set_property", "lamp_on", "lamp_off", "aura_line_on", "aura_off", "all_off",
                  "move_z", "move_xy", "move_xy_rel", "set_nosepiece", "pfs_off"}
#: and on the two that would open a Micro-Manager core, the core itself and its camera
RETIRED_CORE = {"open", "set_exposure", "set_roi", "start_stream", "stop_stream"}
RETIRED = {"mm_real.py": ("MmRealBackend", RETIRED_WRITES | RETIRED_CORE),
           "mm_demo.py": ("MmDemoBackend", RETIRED_WRITES | RETIRED_CORE),
           "replay.py": ("ReplayBackend", RETIRED_WRITES)}


def test_no_direct_write_call_is_left_in_the_package():
    assert _call_sites(SRC) == {}


def test_direct_write_calls_in_scripts_are_exactly_the_legacy_bucket():
    assert _call_sites(SCRIPTS) == SCRIPTS_BUCKET


def test_every_retired_method_only_raises_the_refusal():
    """Card 077: each write (and each core open) on the three backends is one statement,
    `raise CommandPathRetired(...)`, after at most a docstring: nothing is sent first."""
    import ast

    for filename, (cls_name, methods) in RETIRED.items():
        tree = ast.parse((SRC / "engine" / "backends" / filename).read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
        found = {}
        for node in cls.body:
            if isinstance(node, ast.FunctionDef) and node.name in methods:
                body = [s for s in node.body
                        if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
                found[node.name] = body
        assert set(found) == methods, (filename, methods - set(found))
        for name, body in found.items():
            ok = (len(body) == 1 and isinstance(body[0], ast.Raise)
                  and isinstance(body[0].exc, ast.Call)
                  and getattr(body[0].exc.func, "id", None) == "CommandPathRetired")
            assert ok, f"{filename} {cls_name}.{name} does more than refuse"


def test_the_retired_backends_refuse_when_called():
    from dino_autofocus.engine.backend import CommandPathRetired
    from dino_autofocus.engine.backends.mm_demo import MmDemoBackend
    from dino_autofocus.engine.backends.mm_demo_core import DemoDevices

    for backend in (mm_real.MmRealBackend("absent.cfg"), MmDemoBackend()):
        for call in (backend.open, backend.all_off, backend.lamp_off,
                     lambda b=backend: b.move_z(1.0, token=GUARD_TOKEN),
                     lambda b=backend: b.set_exposure(10.0)):
            with pytest.raises(CommandPathRetired, match="plan.md 15, bc0f4848"):
                call()
    with pytest.raises(CommandPathRetired):
        DemoDevices.open()


# -- the executable spec of the exit rules stays with the engine tests (C-02) ----------------


def test_the_e2e_safety_spec_is_present_and_whole():
    # moved from tests/e2e/test_e2e_safety.py with every one of these tests (card 077)
    spec = ROOT / "tests" / "engine" / "test_mock_bench_safety.py"
    text = spec.read_text(encoding="utf-8")
    for name in (
        "test_abort_mid_trace_switches_everything_off",
        "test_lights_off_preempts_a_running_trace",
        "test_the_watched_trace_stops_when_the_local_viewer_leaves",
        "test_shutdown_switches_off_a_light_left_on",
        "test_the_backend_refuses_motion_that_skips_the_guards",
        "test_a_remote_client_may_abort_and_nothing_else",
    ):
        assert f"def {name}(" in text, name
