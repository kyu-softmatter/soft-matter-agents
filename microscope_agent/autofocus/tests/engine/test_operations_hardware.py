"""hardware_scan / hardware_confirm (WP-G) on FakeBackend and MockBackend, alone and through
the runner. The scan only reads; failed reads are fields; confirmations carry the operator."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from dino_autofocus.engine import Command, Event
from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.gates import NOT_SCANNED, ProfileStore
from dino_autofocus.engine.operations.hardware_scan import (
    CONFIRM,
    SCAN,
    assign_roles,
    register_hardware,
    scan,
)
from dino_autofocus.engine.runner import AllowAll, Registry, Runner, RunnerConfig, folder_records

T = 5.0
USER = "op@example.test"
#: everything that writes, moves or switches; a scan must call none of them
WRITES = frozenset({"set_property", "lamp_on", "lamp_off", "aura_line_on", "aura_off",
                    "all_off", "move_z", "move_xy", "move_xy_rel", "set_nosepiece", "pfs_off",
                    "set_exposure", "set_roi", "snap", "start_stream", "stop_stream"})


class ReadOnly:
    """Wraps a backend and records every call. While `armed`, a write, motion or light call
    raises; disarm before the runner's shutdown, which switches off by design."""

    def __init__(self, backend):
        self._b, self.calls, self.armed = backend, [], True

    def __getattr__(self, name):
        attr = getattr(self._b, name)
        if not callable(attr):
            return attr

        def call(*a, **k):
            self.calls.append(name)
            if self.armed and name in WRITES:
                raise AssertionError(f"hardware_scan called {name}")
            return attr(*a, **k)

        return call


class Collect:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._cond = threading.Condition()

    def __call__(self, ev: Event) -> None:
        with self._cond:
            self.events.append(ev)
            self._cond.notify_all()

    def wait(self, kinds: tuple[str, ...], op_id: str) -> Event:
        def find():
            return next((e for e in self.events if e.kind in kinds and e.op_id == op_id), None)

        with self._cond:
            assert self._cond.wait_for(lambda: find() is not None, T), [e.kind for e in self.events]
            return find()

    def of(self, kind: str, op_id: str) -> list[Event]:
        return [e for e in self.events if e.kind == kind and e.op_id == op_id]


def test_scan_reads_every_section_of_the_fake(fake) -> None:
    p = scan(ReadOnly(fake), piezo_port="", host="bench-pc")
    assert p.backend_kind == fake.info().kind and p.host == "bench-pc"
    assert {r for r, d in p.devices.items() if d.present and d.readable} == {
        "camera", "xy_stage", "z_drive", "nosepiece", "pfs", "dia_lamp", "aura"}
    assert "piezo" not in p.devices  # "" skips the port
    assert p.camera["bit_depth"] == 12 and p.camera["ceiling_adu"] == 4095
    assert p.config["autoshutter_verified"] is True
    rows = {r.state: r for r in p.objective_rows}
    assert rows[0].registry_key == "4x" and rows[0].immersion == "dry"
    assert rows[5].registry_key == "100x-Oil" and rows[5].immersion == "oil"
    assert rows[5].working_distance_um == 130.0 and rows[5].wd_source == "guards.FREE_WD_UM"
    assert p.objective == "1-Plan Apo LmbdD20 4x"
    assert all(d.write_verified is None for d in p.device_list)
    assert p.bench is False  # a simulated kind with bench False (backend.is_bench)
    assert p.errors == {}
    json.loads(p.to_json())


def test_scan_of_the_mock_backend_opens_every_gate() -> None:
    from dino_autofocus.engine.gates import evaluate

    b = MockBackend()
    b.open()
    try:
        p = scan(ReadOnly(b), piezo_port="")
    finally:
        b.close()
    assert p.backend_kind == "mock" and p.bench is False
    assert {k: r.reasons for k, r in evaluate(p).items() if not r.enabled} == {}
    assert next(r for r in p.objective_rows if r.state == 1).wd_source == "backend"


def test_an_unreadable_info_is_the_bench(fake, monkeypatch) -> None:
    monkeypatch.setattr(fake, "info", lambda: (_ for _ in ()).throw(OSError("no core")))
    p = scan(fake, piezo_port="")
    assert p.bench is True and p.backend_kind == "unknown" and "info" in p.errors
    assert p.camera == {} and p.camera_bit_depth is None


def test_a_failed_read_is_a_field_and_the_rest_still_reads(fake, monkeypatch) -> None:
    def broken(**_):
        raise OSError("core not answering")

    monkeypatch.setattr(fake, "describe_devices", broken)
    monkeypatch.setattr(fake, "pfs", lambda: (_ for _ in ()).throw(TimeoutError("PFS")))
    p = scan(fake, piezo_port="")
    assert p.errors["devices"] == "OSError: core not answering"
    assert p.errors["pfs"].startswith("TimeoutError")
    assert p.devices == {} and p.pfs == {}
    assert p.camera["bit_depth"] == 12 and len(p.objective_rows) == 6


def test_piezo_port_is_read_when_given(fake) -> None:
    p = scan(fake, piezo_port="COM4")
    assert p.piezo["port"] == "COM4"
    assert p.devices["piezo"].present == p.piezo["connected"]


def test_roles_fall_back_to_a_unique_device_type() -> None:
    from dino_autofocus.engine.backend import DeviceInfo

    devs = [DeviceInfo("Cam1", "CameraDevice", "x", "", True),
            DeviceInfo("Stage9", "XYStageDevice", "x", "", False),
            DeviceInfo("White Light Shutter", "ShutterDevice", "x", "", True)]
    roles = assign_roles(devs, camera=None)
    assert {r: d.label for r, d in roles.items()} == {
        "camera": "Cam1", "xy_stage": "Stage9", "dia_lamp": "White Light Shutter"}


# -- through the runner ---------------------------------------------------------------------


@pytest.fixture
def engine(fake, tmp_path):
    made = []

    def build(backend=None):
        reg = Registry()
        store = ProfileStore(tmp_path / "hardware")
        hw = register_hardware(reg, store)
        r = Runner(backend or fake, registry=reg, control=AllowAll(), hardware=hw,
                   config=RunnerConfig(position_interval_s=None),
                   records=folder_records(lambda meta: tmp_path / "records"))
        made.append(r)
        sink = Collect()
        r.subscribe(sink)
        r.start()
        return r, sink, store, hw

    yield build
    for r in made:
        r.shutdown("test teardown", timeout=T)
        assert r.wait_idle(T)


def start(op: str, user: str | None = USER, **args) -> Command:
    return Command("start", op=op, args=args, user_id=user)


def test_scan_through_the_runner_fills_the_snapshot_and_reads_only(engine, fake) -> None:
    guarded = ReadOnly(fake)
    r, sink, store, _ = engine(guarded)
    before = r.snapshot()["hardware"]
    assert before["profile"] is None
    assert all(not g["enabled"] and g["reasons"] == [NOT_SCANNED] for g in before["gates"])
    op_id = r.submit(start(SCAN, include_properties=True, piezo_port=""))
    end = sink.wait(("finished", "error", "aborted"), op_id)
    assert end.kind == "finished", end.data
    assert end.data["summary"]["sha256"] == store.latest()[2]
    assert "scan_4x" in end.data["summary"]["gates_enabled"]
    sources = {e.data["source"] for e in sink.of("reading", op_id)}
    assert {"hardware_scan.camera", "hardware_scan.objective_rows"} <= sources
    hw = r.snapshot()["hardware"]
    assert hw["profile"]["backend_kind"] == fake.info().kind
    assert hw["profile_path"] == str(store.latest_path) and hw["previous"] is None
    assert all(g["enabled"] for g in hw["gates"]) and "last_status" in hw
    assert {o["state"] for o in hw["objective_options"]} == set(range(6))
    assert not WRITES & set(guarded.calls)
    guarded.armed = False  # the teardown shutdown switches everything off, as it should
    summary = json.loads((Path(end.data["record_dir"]) / "summary.json").read_text("utf-8"))
    assert summary["status"] == "finished"
    assert summary["result"]["summary"]["profile"]["backend_kind"] == fake.info().kind


def test_lights_found_on_are_left_on_with_a_warning(engine, fake) -> None:
    fake.lights["DiaLamp"] = "1"
    r, sink, _, _ = engine()
    op_id = r.submit(start(SCAN, piezo_port=""))
    assert sink.wait(("finished", "error"), op_id).kind == "finished"
    warnings = [e.data["text"] for e in sink.of("log", op_id) if e.data.get("level") == "warning"]
    assert any("DiaLamp" in w and "switches nothing" in w for w in warnings)
    assert fake.lights["DiaLamp"] == "1"


def test_bad_scan_arguments_stop_in_preflight(engine) -> None:
    r, sink, store, _ = engine()
    op_id = r.submit(start(SCAN, include_properties="yes", speed=3))
    failed = sink.wait(("preflight_failed",), op_id)
    bad = {c["name"] for c in failed.data["checks"] if not c["ok"]}
    assert bad == {"args", "include_properties"}
    assert store.latest() is None


def test_confirm_needs_a_profile_and_an_operator(engine) -> None:
    r, sink, _, _ = engine()
    op_id = r.submit(start(CONFIRM, items={"dialamp_intensity": 608}))
    names = {c["name"] for c in sink.wait(("preflight_failed",), op_id).data["checks"]
             if not c["ok"]}
    assert names == {"profile"}
    scan_id = r.submit(start(SCAN, piezo_port=""))
    sink.wait(("finished",), scan_id)
    anon = r.submit(start(CONFIRM, user=None, items={"dialamp_intensity": 608}))
    names = {c["name"] for c in sink.wait(("preflight_failed",), anon).data["checks"]
             if not c["ok"]}
    assert names == {"operator"}
    junk = r.submit(start(CONFIRM, items={"": 1, "ring": [1, 2]}))
    why = next(c["why"] for c in sink.wait(("preflight_failed",), junk).data["checks"]
               if c["name"] == "items")
    assert "item name ''" in why and "ring: value must be" in why


def test_confirmed_items_carry_who_and_when_and_survive_a_rescan(engine) -> None:
    r, sink, store, hw = engine()
    sink.wait(("finished",), r.submit(start(SCAN, piezo_port="")))
    op_id = r.submit(start(CONFIRM, items={"dialamp_intensity": 608,
                                           "condenser_turret": "3-"}))
    end = sink.wait(("finished", "error"), op_id)
    assert end.kind == "finished", end.data
    item = store.latest()[0].confirmed["dialamp_intensity"]
    assert item["value"] == 608 and item["by"] == USER and item["at"]
    changed = [c["key"] for c in store.previous()["changed"]]
    assert changed == ["confirmed.condenser_turret", "confirmed.dialamp_intensity"]
    sink.wait(("finished",), r.submit(start(SCAN, piezo_port="")))
    assert store.latest()[0].confirmed["condenser_turret"]["value"] == "3-"
    gone = r.submit(start(CONFIRM, items={"condenser_turret": None}))
    assert sink.wait(("finished",), gone).data["summary"]["withdrawn"] == ["condenser_turret"]
    assert set(store.latest()[0].confirmed) == {"dialamp_intensity"}
    assert len(store.history()) == 4
    assert hw.check("scan_4x") == (True, [])
