"""T-032 stage 2 through the T-011 runner: flags and candidate decisions as sample events,
goto_xy (box, retract, guarded move) on FakeBackend, and a brightfield sample_map on
MockBackend with candidates written as particle events. A real records store (FolderStore)
and an open experiment session sit behind the runner's sample seat, as the server installs
them."""

from __future__ import annotations

import json
import threading
import time

import pytest
from engine_fakes import FakeBackend

from dino_autofocus.engine.events import Command, Event
from dino_autofocus.engine.mosaic import load_mosaic
from dino_autofocus.engine.operations import sample_map as SM
from dino_autofocus.engine.operations.sample_ops import SampleSeat, install_sample_seat
from dino_autofocus.engine.runner import (
    OPERATIONS,
    PERMISSIONS,
    AllowAll,
    Runner,
    RunnerConfig,
    folder_records,
)
from dino_autofocus.engine.sample import Sample, SampleInfo, read_sample
from dino_autofocus.records import ExperimentSession, FolderStore, RecordsConfig

USER = "operator@example.test"
SID = "20261002_0900_1"
T = 120.0
QUIET = RunnerConfig(position_interval_s=None)
ENDS = ("finished", "aborted", "error", "preflight_failed")


class Collect:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._cond = threading.Condition()

    def __call__(self, ev: Event) -> None:
        with self._cond:
            self.events.append(ev)
            self._cond.notify_all()

    def wait(self, op_id: str, *kinds: str, key: str | None = None) -> Event:
        def find():
            return next((e for e in self.events if e.op_id == op_id and e.kind in kinds
                         and (key is None or e.data.get("key") == key)), None)

        with self._cond:
            assert self._cond.wait_for(lambda: find() is not None, T), \
                (kinds, [e.kind for e in self.events if e.op_id == op_id])
            return find()


class Engine:
    """A runner over `backend` with the records store, an open session for SID and the seat."""

    def __init__(self, backend, tmp_path, session: bool = True):
        self.root = tmp_path / "samples"
        self.sample = Sample(SID, self.root)
        self.sample.dir.mkdir(parents=True, exist_ok=True)
        self.store = FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                               data_root=tmp_path / "data"))
        self.session = ExperimentSession.open(self.store, USER, SID) if session else None
        self.r = Runner(backend, control=AllowAll(), config=QUIET,
                        records=folder_records(lambda meta: self.sample.dir))
        self.sink = Collect()
        self.r.subscribe(self.sink)
        self.r.start()
        sid = self.session.session_id if self.session else None
        if sid:
            self.r.set_experiment_session(sid, time.time() - 3600)
        install_sample_seat(self.r, SampleSeat(
            self.store, self.root,
            session_for=lambda s: self.session if self.session and s == sid else None))

    @property
    def session_id(self) -> str | None:
        return self.session.session_id if self.session else None

    def start(self, op: str, **args) -> str:
        return self.r.submit(Command("start", op=op, args={"sample_id": SID, **args},
                                     user_id=USER, session_id=self.session_id))

    def answer(self, op_id: str, key: str, ok: bool = True) -> None:
        self.r.submit(Command("confirm", op_id=op_id, args={"key": key, "ok": ok},
                              user_id=USER, session_id=self.session_id))

    def end(self, op_id: str) -> Event:
        return self.sink.wait(op_id, *ENDS)

    def run(self, op: str, **args) -> Event:
        return self.end(self.start(op, **args))

    def view(self):
        return read_sample(self.store, SID, self.root, self.session_id)

    def close(self) -> None:
        self.r.shutdown("test teardown", timeout=30)


@pytest.fixture
def engine(tmp_path):
    made = []

    def build(backend=None, **kw) -> Engine:
        e = Engine(backend or FakeBackend(), tmp_path, **kw)
        made.append(e)
        return e

    yield build
    for e in made:
        e.close()


def checks_of(ev: Event) -> dict:
    return {c["name"]: c for c in ev.data["checks"]}


def test_registered_with_their_permission_classes() -> None:
    for name in (SM.SAMPLE_MAP, SM.GOTO_XY, SM.MAP_FLAG, SM.MAP_FLAG_RETIRE,
                 SM.CANDIDATE_CONFIRM, SM.CANDIDATE_REJECT):
        assert OPERATIONS.get(name) is not None, name
    assert PERMISSIONS["sample_map"].action == PERMISSIONS["goto_xy"].action == "motion"
    assert PERMISSIONS["map_flag"].action == "record"
    assert not OPERATIONS.get("map_flag").exclusive and OPERATIONS.get("sample_map").snaps


# ---------------------------------------------------------------- flags
def test_flags_get_engine_ids_edits_replace_and_retire_keeps_history(engine) -> None:
    e = engine()
    first = e.run("map_flag", x_um=8100.0, y_um=600.0, name="crystal", note="")
    assert first.kind == "finished", first.data
    f1 = first.data["summary"]["flag"]
    assert f1["flag_id"] == "F001" and f1["objective"] == "4x" and f1["z_um"] == 2900.0
    assert e.run("map_flag", x_um=8200.0, y_um=650.0, name="bubble").data["summary"][
        "flag"]["flag_id"] == "F002"
    edit = e.run("map_flag", x_um=8100.0, y_um=600.0, name="crystal", note="large",
                 replaces="F001")
    assert edit.data["summary"]["flag"] == {**edit.data["summary"]["flag"], "flag_id": "F003",
                                            "replaces": "F001"}
    assert e.run("map_flag_retire", flag_id="F002").kind == "finished"
    v = e.view()
    assert set(v.active_flags()) == {"F003"}
    assert v.flags["F001"]["retired"] and v.flags["F002"]["retired"]
    assert [h["kind"] for h in v.flags["F001"]["history"]] == ["flag_set", "flag_remove"]
    assert any(ev.kind == "map_changed" and ev.data["what"] == "flags" for ev in e.sink.events)


def test_flag_refusals_happen_in_preflight(engine) -> None:
    e = engine()
    bad = e.run("map_flag_retire", flag_id="F404")
    assert bad.kind == "preflight_failed" and "not an active flag" in \
        checks_of(bad)["sample_record"]["why"]
    assert e.run("map_flag", x_um="here", y_um=1.0).kind == "preflight_failed"
    assert e.run("map_flag", x_um=1.0, y_um=1.0, colour="red").kind == "preflight_failed"
    assert e.run("map_flag", x_um=1.0, y_um=1.0, replaces="F404").kind == "preflight_failed"
    assert e.view().flags == {}


def test_record_ops_need_the_open_session_of_the_sample(engine) -> None:
    e = engine(session=False)
    with pytest.raises(ValueError):  # rule 12: the runner refuses without a session
        e.start("map_flag", x_um=1.0, y_um=1.0)


# ---------------------------------------------------------------- candidates
def test_confirm_and_reject_add_decisions_without_overwriting(engine) -> None:
    e = engine()
    for k, (x, y) in enumerate([(8000.0, 500.0), (8100.0, 520.0)], 1):
        e.session.sample_event("particle", particle_id=f"m1-c{k:03d}", x_um=x, y_um=y, z_um=2950.0,
                               status="candidate", source="classical_candidate", score=9.0)
    assert e.run("candidate_confirm", candidate_id="m1-c001", note="round").kind == "finished"
    assert e.run("candidate_reject", candidate_id="m1-c002").kind == "finished"
    v = e.view()
    assert set(v.confirmed_particles) == {"m1-c001"} and v.open_candidates() == {}
    rej = v.candidates["m1-c002"]
    assert rej["status"] == "rejected" and rej["source"] == "person_rejected"
    assert rej["decides"] == "m1-c002"
    assert [h["status"] for h in rej["history"]] == ["candidate", "rejected"]
    again = e.run("candidate_confirm", candidate_id="m1-c002")
    assert again.kind == "preflight_failed"  # decided already: not an undecided candidate
    assert e.run("candidate_reject", candidate_id="nope").kind == "preflight_failed"


# ---------------------------------------------------------------- goto_xy
def scan_box(sample: Sample, diameter_mm: float = 6.0) -> None:
    d = sample.dir / "scan4x_20261002-100000"
    d.mkdir()
    (d / "scan.json").write_text(json.dumps({
        "hole": {"centre_um": [8026.0, 571.6], "diameter_mm": diameter_mm},
        "margin_um": 500.0, "tiles": []}), encoding="utf-8")


def test_goto_xy_small_move_stays_at_z(engine) -> None:
    fake = FakeBackend()
    e = engine(fake)
    scan_box(e.sample)
    end = e.run("goto_xy", x_um=8526.0, y_um=571.6)
    assert end.kind == "finished", end.data
    s = end.data["summary"]
    assert (s["x_um"], s["y_um"]) == (8526.0, 571.6) and not s["retracted"]
    assert s["allowed_box_um"] == [8026.0 - 4500, 8026.0 + 4500, 571.6 - 4500, 571.6 + 4500]
    assert not [c for c in fake.calls if c[0] == "move_z"]
    assert not [c for c in fake.calls if c[0] == "light"]
    assert any(ev.kind == "motion" and ev.data["axis"] == "xy" for ev in e.sink.events)


def test_goto_xy_large_move_retracts_after_a_yes(engine) -> None:
    fake = FakeBackend()
    fake.state = 5  # 100x Oil: a 500 um move is long
    e = engine(fake)
    scan_box(e.sample)
    op = e.start("goto_xy", x_um=8526.0, y_um=571.6)
    ask = e.sink.wait(op, "confirm_required")
    assert ask.data["key"] == "retract_then_move"
    assert ask.data["context"]["z_um"] == 2900.0 and ask.data["context"]["z_safe_um"] == 0.0
    planned = e.sink.wait(op, "planned").data["plan"]
    assert planned["large_move"] and planned["retract_needed"] and planned["distance_um"] == 500.0
    e.answer(op, "retract_then_move")
    end = e.end(op)
    assert end.kind == "finished", end.data
    assert end.data["summary"]["retracted"] and end.data["summary"]["z_um"] == 0.0
    moves = [c[0] for c in fake.calls if c[0] in ("move_z", "move_xy")]
    assert moves == ["move_z", "move_xy"]  # Z down first, never back up
    steps = [ev.data["status"] for ev in e.sink.events if ev.op_id == op and ev.kind == "progress"]
    assert steps == ["retract", "move_xy"]


def test_goto_xy_declined_retract_moves_nothing(engine) -> None:
    fake = FakeBackend()
    fake.state = 5
    e = engine(fake)
    scan_box(e.sample)
    op = e.start("goto_xy", x_um=8526.0, y_um=571.6)
    e.sink.wait(op, "confirm_required")
    e.answer(op, "retract_then_move", ok=False)
    assert e.end(op).kind == "aborted"
    assert not [c for c in fake.calls if c[0] in ("move_z", "move_xy")]


def test_goto_xy_refuses_outside_the_scan_box_and_without_a_scan(engine) -> None:
    fake = FakeBackend()
    e = engine(fake)
    no_scan = e.run("goto_xy", x_um=8026.0, y_um=571.6)
    assert no_scan.kind == "preflight_failed" and "no scan" in checks_of(no_scan)["scan_box"]["why"]
    scan_box(e.sample)
    out = e.run("goto_xy", x_um=8026.0 + 5000, y_um=571.6)
    assert out.kind == "preflight_failed"
    assert "outside the scanned area" in checks_of(out)["scan_box"]["why"]
    assert not [c for c in fake.calls if c[0] in ("move_z", "move_xy")]


def test_latest_scan_box_prefers_the_summary(tmp_path) -> None:
    s = Sample(SID, tmp_path)
    s.dir.mkdir()
    scan_box(s)
    newer = s.dir / "sample_map_20261002-110000"
    newer.mkdir()
    (newer / "scan.json").write_text(json.dumps({"tiles": []}), encoding="utf-8")
    (newer / "summary.json").write_text(json.dumps({"result": {"summary": {
        "scan_box_um": [0, 1, 0, 1], "allowed_box_um": [-1, 2, -1, 2]}}}), encoding="utf-8")
    box = SM.latest_scan_box(s)
    assert box["result_id"] == newer.name and box["allowed_box_um"] == [-1, 2, -1, 2]


# ---------------------------------------------------------------- sample_map
def test_sample_map_argument_rules() -> None:
    a, focus, cands = SM.parse_map_args({"sample_id": SID, "margin_um": 0.0})
    assert a.exposure_ms == SM.BRIGHTFIELD_EXPOSURE_MS and focus == "per_tile" and cands
    with pytest.raises(ValueError, match="focus"):
        SM.parse_map_args({"focus": "auto"})


def test_sample_map_plane_focus_is_refused_for_now(engine) -> None:
    e = engine()
    end = e.run("sample_map", focus="plane")
    assert end.kind == "preflight_failed"
    assert "per-tile focus hook" in checks_of(end)["focus"]["why"]


def mock_backend():
    from dino_autofocus.engine.backends.mock import MockBackend
    from dino_autofocus.engine.backends.mock_world import Camera, MockWorld, SampleSpec

    world = MockWorld(SampleSpec(seed=3, hole_diameter_mm=0.3), camera=Camera(sensor=(256, 256)))
    world.z_um = 2960.0  # already in the window: no approach confirm
    world.nosepiece = 0
    b = MockBackend(world)
    b.open()
    return b


def test_sample_map_on_the_mock_writes_mosaic_and_candidate_events(engine) -> None:
    b = mock_backend()
    e = engine(b)
    spec = b.world.spec
    e.sample.save_info(SampleInfo(SID, hole={
        "centre_um": list(spec.hole_centre_um), "diameter_mm": spec.hole_diameter_mm,
        "fitted_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "trace_stop": "full loop",
        "closed_loop": True, "arc_deg": 360.0}))
    op = e.start("sample_map", margin_um=0.0)
    end = e.end(op)
    assert end.kind == "finished", end.data
    s = end.data["summary"]
    assert s["light"] == "brightfield" and s["scan_box_um"] and s["allowed_box_um"]
    folder = e.sample.dir / s["result_id"]
    assert folder.name.startswith("sample_map_") and str(folder) == end.data["record_dir"]
    assert load_mosaic(folder)[1].orientation == "stage"
    rec = json.loads((folder / "scan.json").read_text(encoding="utf-8"))
    assert any(r["device"] == "DiaLamp" and r["read"] == "1" for r in rec["light"])
    assert rec["light_off"]["verified"]
    assert b.light_state()["DiaLamp"] == "0" and b.light_state()["Aura"] == "0"
    v = e.view()
    mine = {k: c for k, c in v.candidates.items() if k.startswith(op)}
    assert len(mine) == s["candidates"]["n"] >= 1  # seed 3: the mock shows two
    for c in mine.values():
        assert c["status"] == "candidate" and c["source"] == "classical_candidate"
        assert c["grade"] == "computed" and c["result_id"] == folder.name
    assert any(ev.kind == "map_changed" and ev.data["what"] == "candidates"
               for ev in e.sink.events if ev.op_id == op)


def test_goto_xy_switches_pfs_off_before_the_retract(engine, monkeypatch) -> None:
    fake = FakeBackend(pfs_enabled=True)
    fake.state = 5  # 100x Oil: a 500 um move needs the retract
    real_off = fake.pfs_off

    def pfs_off(*, token):
        fake.calls.append(("pfs_off",))
        return real_off(token=token)

    monkeypatch.setattr(fake, "pfs_off", pfs_off)
    e = engine(fake)
    scan_box(e.sample)
    op = e.start("goto_xy", x_um=8526.0, y_um=571.6)
    e.sink.wait(op, "confirm_required")
    e.answer(op, "retract_then_move")
    end = e.end(op)
    assert end.kind == "finished", end.data
    order = [c[0] for c in fake.calls if c[0] in ("pfs_off", "move_z", "move_xy")]
    assert order == ["pfs_off", "move_z", "move_xy"]
    assert end.data["summary"]["pfs"] == {"enabled_before": True, "enabled": False,
                                          "in_range": "Out of Range"}


def test_goto_xy_refuses_a_retract_when_pfs_is_unreadable(engine, monkeypatch) -> None:
    fake = FakeBackend()
    fake.state = 5

    def broken():
        raise OSError("PFS not answering")

    monkeypatch.setattr(fake, "pfs", broken)
    e = engine(fake)
    scan_box(e.sample)
    end = e.run("goto_xy", x_um=8526.0, y_um=571.6)
    assert end.kind == "preflight_failed"
    assert "PFS state unreadable" in checks_of(end)["pfs"]["why"]
    assert not [c for c in fake.calls if c[0] in ("move_z", "move_xy")]
    fake.state = 0  # at 4x the same 500 um move needs no retract, so PFS is not asked
    assert e.run("goto_xy", x_um=8526.0, y_um=571.6).kind == "finished"


def test_flags_submitted_together_get_different_ids(engine) -> None:
    e = engine()
    ops = [e.start("map_flag", x_um=8000.0 + k, y_um=500.0, name=f"f{k}") for k in range(6)]
    ends = [e.end(op) for op in ops]
    assert all(end.kind == "finished" for end in ends), [end.data for end in ends]
    ids = [end.data["summary"]["flag"]["flag_id"] for end in ends]
    assert len(set(ids)) == 6 and set(e.view().active_flags()) == set(ids)
