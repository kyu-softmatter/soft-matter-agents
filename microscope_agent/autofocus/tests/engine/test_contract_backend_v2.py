"""Backend contract v2 (T-015): set_property allow-list, light tokens, notes, discovery
reads, relative XY and the acquisition stream.

`BackendContract` holds the checks every backend must pass. It is not collected on its own
(no `Test` prefix); a backend's test file subclasses it and provides a `backend` fixture
(an opened backend, closed after the test). Other backends reuse it with

    from test_contract_backend_v2 import BackendContract

    class TestMockBackendContract(BackendContract):
        @pytest.fixture
        def backend(self): ...

The light property used for the token check defaults to the bench DiaLamp; a backend with
other device names sets `light_write` (device, prop, value). The value switches light off.
`xy_tol_um` is the XY readback tolerance of the relative-move check (raise it for a backend
with injected readback error). `bench` is what `is_bench(info())` must say (True for
mm-real). The fixture must leave no stream running (close() stops it).

T-015b: `BackendInfo.bench` defaults to True and `is_bench` is the one rule; the tests at
the end enumerate every backend class so a new one cannot opt out of the bench by omission.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest
from engine_fakes import FakeBackend

from dino_autofocus.engine.backend import (
    CAMERA_PROPERTIES,
    GUARD_TOKEN,
    LIGHT_PROPERTIES,
    MOTION_DEVICES,
    PROVISIONAL,
    Backend,
    ConfigRecord,
    DeviceInfo,
    Frame,
    NosepieceLabel,
    PiezoReading,
    PropertyInfo,
    PropertyNotAllowed,
    Readback,
    StreamActive,
    UnguardedMotion,
    check_set_property,
    is_bench,
)


def _where(b: Backend) -> tuple:
    p = b.positions()
    return p.x_um, p.y_um, p.z_um, b.nosepiece()


class BackendContract:
    light_write: tuple[str, str, object] = ("DiaLamp", "State", 0)
    unlisted_write: tuple[str, str, object] = ("LightPath", "State", "4-L100")
    xy_tol_um: float = 0.01
    bench: bool = False  # what is_bench(info()) must say; mm-real sets True

    def test_meets_the_protocol(self, backend):
        assert isinstance(backend, Backend)

    def test_is_bench_says_what_this_backend_is(self, backend):
        assert is_bench(backend.info()) is self.bench

    @pytest.mark.parametrize("device", sorted(MOTION_DEVICES))
    def test_set_property_refuses_motion_devices_even_with_the_token(self, backend, device):
        before = _where(backend)
        for prop in ("State", "Position", "Focus"):
            with pytest.raises(UnguardedMotion):
                backend.set_property(device, prop, 1, token=GUARD_TOKEN)
            with pytest.raises(UnguardedMotion):
                backend.set_property(device, prop, 1)
        assert _where(backend) == before

    def test_light_property_needs_the_token(self, backend):
        device, prop, value = self.light_write
        before = backend.light_state()
        with pytest.raises(UnguardedMotion):
            backend.set_property(device, prop, value)
        assert backend.light_state() == before
        rec = backend.set_property(device, prop, value, token=GUARD_TOKEN)
        assert isinstance(rec, Readback) and rec.device == device and rec.prop == prop

    def test_listed_camera_property_needs_no_token(self, backend):
        info = backend.info()
        rec = backend.set_property(info.camera, "Exposure", info.exposure_ms)
        assert isinstance(rec, Readback)

    def test_unlisted_property_is_refused_with_the_allow_list(self, backend):
        device, prop, value = self.unlisted_write
        with pytest.raises(PropertyNotAllowed, match="allow-list"):
            backend.set_property(device, prop, value, token=GUARD_TOKEN)
        cam = backend.info().camera
        with pytest.raises(PropertyNotAllowed):  # camera names only on the camera device
            backend.set_property("Not" + cam, "Exposure", 10)

    def test_light_on_needs_the_token_and_off_never_does(self, backend):
        before = backend.light_state()
        with pytest.raises(UnguardedMotion):
            backend.lamp_on(token=None)
        with pytest.raises(UnguardedMotion):
            backend.aura_line_on("GREEN", 1.0, token=None)
        assert backend.light_state() == before
        assert backend.lamp_on(token=GUARD_TOKEN)
        for off in (backend.lamp_off, backend.aura_off, backend.all_off):
            assert all(isinstance(r, Readback) for r in off())

    def test_info_and_readbacks_carry_json_safe_notes(self, backend):
        info = backend.info()
        assert isinstance(info.notes, dict)
        json.dumps(info.to_dict())
        for r in backend.all_off():
            assert isinstance(r.notes, dict)
            json.dumps(asdict(r))

    # -- discovery reads
    def test_discovery_reads_change_nothing_and_are_json_safe(self, backend):
        before = (_where(backend), backend.light_state())
        devices = backend.describe_devices()
        labels = backend.nosepiece_labels()
        cfg = backend.config_record()
        piezo = backend.piezo_read("")
        assert (_where(backend), backend.light_state()) == before
        json.dumps([asdict(d) for d in devices] + [asdict(n) for n in labels]
                   + [asdict(cfg), asdict(piezo)])
        assert devices and all(isinstance(d, DeviceInfo) for d in devices)
        assert all(d.write_verified is None for d in devices)  # discovery never writes
        assert backend.info().camera in {d.label for d in devices}
        assert all(isinstance(p, PropertyInfo) for d in devices for p in d.properties.values())
        assert all(not d.properties for d in backend.describe_devices(include_properties=False))
        assert isinstance(cfg, ConfigRecord)

    def test_nosepiece_labels_cover_every_state_and_the_current_one(self, backend):
        labels = backend.nosepiece_labels()
        assert all(isinstance(n, NosepieceLabel) for n in labels)
        assert len({n.state for n in labels}) == len(labels)
        assert backend.nosepiece() in {n.label for n in labels}

    def test_piezo_not_opened_is_a_field(self, backend):
        r = backend.piezo_read("")
        assert isinstance(r, PiezoReading) and r.port == "" and not r.connected

    # -- relative XY
    def test_move_xy_rel_needs_the_token_and_moves_by_the_step(self, backend):
        p0 = backend.positions()
        with pytest.raises(UnguardedMotion):
            backend.move_xy_rel(10.0, -5.0, token=None)
        assert backend.positions().x_um == p0.x_um
        x, y = backend.move_xy_rel(10.0, -5.0, token=GUARD_TOKEN)
        p1 = backend.positions()
        assert (x, y) == pytest.approx((p1.x_um, p1.y_um), abs=self.xy_tol_um)
        assert (p1.x_um - p0.x_um, p1.y_um - p0.y_um) == pytest.approx((10.0, -5.0),
                                                                     abs=self.xy_tol_um)

    # -- stream
    def test_stream_frames_have_snap_meta_and_block_snap(self, backend):
        keys = set(backend.snap().meta())
        assert not backend.streaming()
        backend.start_stream()
        try:
            assert backend.streaming()
            f = backend.next_frame(timeout_s=5.0)
            assert isinstance(f, Frame) and set(f.meta()) == keys
            assert f.image.dtype.name == "uint16"
            with pytest.raises(StreamActive):
                backend.snap()
        finally:
            backend.stop_stream()
        assert not backend.streaming()
        backend.stop_stream()  # second stop is a no-op
        assert backend.next_frame(timeout_s=0.01) is None
        assert isinstance(backend.snap(), Frame)

    def test_close_stops_the_stream(self, backend):
        backend.start_stream()
        backend.close()
        assert not backend.streaming()


class TestFakeBackendContract(BackendContract):
    @pytest.fixture
    def backend(self):
        b = FakeBackend()
        b.open()
        yield b
        b.close()


def test_allow_list_groups_do_not_overlap():
    assert not {d for d, _ in LIGHT_PROPERTIES} & MOTION_DEVICES
    assert {"ZDrive", "XYStage", "Nosepiece", "PFS"} <= MOTION_DEVICES
    assert ("Aura", "GREEN_Intensity") in LIGHT_PROPERTIES
    assert {"Exposure", "PixelType"} <= CAMERA_PROPERTIES


def test_check_set_property_cases():
    check_set_property("Cam", "Exposure", None, camera="Cam")
    check_set_property("DiaLamp", "Intensity", GUARD_TOKEN, camera="Cam")
    with pytest.raises(UnguardedMotion):
        check_set_property("DiaLamp", "Intensity", None, camera="Cam")
    with pytest.raises(UnguardedMotion):
        check_set_property("Core", "Focus", GUARD_TOKEN, camera="Cam")
    with pytest.raises(PropertyNotAllowed):
        check_set_property("Cam", "Gain", None, camera="Cam")


def test_bench_aura_lines_and_kinetix_readout_2026_10_02():
    """The Aura III has UV CYAN GREEN RED NIR and no VIOLET; Kinetix Port and ReadoutRate
    are listed together (ReadoutRate's values depend on Port)."""
    for line in ("UV", "CYAN", "GREEN", "RED", "NIR"):
        check_set_property("Aura", line, GUARD_TOKEN, camera="Cam")
        check_set_property("Aura", f"{line}_Intensity", GUARD_TOKEN, camera="Cam")
    with pytest.raises(PropertyNotAllowed):
        check_set_property("Aura", "VIOLET", GUARD_TOKEN, camera="Cam")
    check_set_property("Cam", "Port", None, camera="Cam")
    check_set_property("Cam", "ReadoutRate", None, camera="Cam")


def test_refused_writes_never_reach_the_fake_device():
    b = FakeBackend()
    for args in (("ZDrive", "Position", 3000), ("DiaLamp", "State", 1), ("Foo", "Bar", 1)):
        with pytest.raises((UnguardedMotion, PropertyNotAllowed)):
            b.set_property(*args)
    assert not b.props and not b.calls


def test_fake_piezo_and_stream_details():
    b = FakeBackend()
    assert b.piezo_read("COM4").error == "no piezo on COM4"
    b.piezo_um = (1.0, 2.0, 9.94)
    r = b.piezo_read("COM4")
    assert r.connected and r.z_um == 9.94
    b.start_stream(interval_ms=100)
    frames = [b.next_frame() for _ in range(3)]
    b.close()
    assert b.stream_frames == 3 and all(f is not None for f in frames)
    assert ("start_stream", 100) in b.calls and ("stop_stream",) in b.calls


def test_notes_round_trip_and_default_empty():
    r = Readback.of("Aura", "CYAN", 1, 1, notes={"line": PROVISIONAL})
    assert r.verified and r.notes == {"line": PROVISIONAL}
    assert Readback.of("Aura", "State", 0, 0).notes == {}
    assert Readback(**json.loads(json.dumps(asdict(r)))) == r


# -- T-015b: the bench is the default


NON_BENCH_CLASSES = {"MockBackend": "mock", "MmDemoBackend": "mm-demo",
                     "ReplayBackend": "replay", "FakeBackend": "fake"}


class _Info:
    """A stand-in BackendInfo with only the fields given."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class _BadHash:
    def __hash__(self):
        raise RuntimeError("no hash")


class _Unreadable:
    @property
    def kind(self):
        raise OSError("device gone")


def test_bench_field_defaults_to_true():
    from dino_autofocus.engine.backend import BackendInfo

    info = BackendInfo("anything", "c", "cam", (1, 1), (0, 0, 1, 1), 1.0, 1.0, "o", None, 12)
    assert info.bench is True and is_bench(info)


@pytest.mark.parametrize("info, bench", [
    (None, True),  # info() could not be read
    (_Unreadable(), True),  # a field read fails
    (_Info(kind="mock"), True),  # no bench field
    (_Info(kind="mock", bench=None), True),  # not exactly False
    (_Info(kind="mock", bench=0), True),
    (_Info(kind="mm-real", bench=False), True),  # not a simulated kind
    (_Info(kind=["mock"], bench=False), True),  # unhashable kind (T-015c)
    (_Info(kind=_BadHash(), bench=False), True),  # hashing the kind raises
    (_Info(kind="new-backend", bench=False), True),
    (_Info(kind="mm-real", bench=True), True),
    (_Info(kind="mock", bench=True), True),
    (_Info(kind="mock", bench=False), False),  # the only way out
    (_Info(kind="replay", bench=False), False),
    (_Info(kind="mm-demo", bench=False), False),
    (_Info(kind="fake", bench=False), False),
])
def test_is_bench_branches(info, bench):
    assert is_bench(info) is bench


def _backend_classes() -> dict[str, type]:
    """Every class in engine/backends/* that has the Backend protocol's methods."""
    import importlib
    import inspect
    import pkgutil

    import dino_autofocus.engine.backends as pkg

    names = [n for n, v in vars(Backend).items() if callable(v) and not n.startswith("_")]
    found = {}
    for m in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"{pkg.__name__}.{m.name}")
        for name, cls in inspect.getmembers(mod, inspect.isclass):
            if cls.__module__ == mod.__name__ and all(hasattr(cls, n) for n in names):
                found[name] = cls
    found["FakeBackend"] = FakeBackend
    return found


def test_every_backend_outside_the_list_is_bench():
    classes = _backend_classes()
    assert {"MockBackend", "MmDemoBackend", "MmRealBackend", "FakeBackend"} <= set(classes)
    for name, cls in classes.items():
        kind = getattr(cls, "kind", None)
        if name in NON_BENCH_CLASSES:
            assert kind == NON_BENCH_CLASSES[name], (name, kind)
            continue
        # even claiming bench=False, a class not on the list is the bench
        assert kind not in NON_BENCH_CLASSES.values(), f"{name} reuses a simulated kind {kind!r}"
        assert is_bench(_Info(kind=kind, bench=False)), name


def test_listed_backends_report_not_bench():
    from dino_autofocus.engine.backends.mock import MockBackend

    assert not is_bench(MockBackend(seed=0).info())
    assert not is_bench(FakeBackend().info())
