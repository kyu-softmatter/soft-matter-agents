"""The Instruments screens' server side (console card 012): show, draft and stop only.

The idle status file, the person's limits and the latest run's events are read; a plan draft is composed and
checked against plan.schema.json read from the tree. Nothing is sent to an instrument, no draft is saved, and
no stand-in is built for a runtime piece that does not exist yet.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from server_fakes import OPERATOR, VIEWER

from sma_console.agents import MockStore, SmaFiles, drafts, instruments
from sma_console.agents.mock_store import MOCK_DATA
from sma_console.agents.schema_lite import Schemas
from sma_console.agents.sma_files import repository_root

REPO = repository_root()
STATUS, LIMITS, LATEST, DRAFT = (f"/api/instruments/{p}" for p in ("status", "limits", "latest-run", "draft"))
NOW = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)
SHA = "a" * 64


def tree_hash(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def reading(channel, name, how="read_back", value="x", t="2026-10-24T11:00:00Z"):
    if how == "not_read":
        return {"channel": channel, "name": name, "how": how, "t_wall": None, "value": None}
    return {"channel": channel, "name": name, "how": how, "t_wall": t, "value": value}


def idle(**over):
    doc = {
        "artifact": "idle_status", "schema_version": "0.1", "written_at": "2026-10-24T11:05:00Z",
        "written_by_run": "run-20261024-001",
        "last_run": {
            "run_id": "run-20261024-001", "kind": "plan", "ended_at": "2026-10-24T11:05:00Z", "outcome": "completed",
            "preflight": None,
            "last_snapshot": {"t_wall": "2026-10-24T11:04:00Z", "channels": [
                reading("aura", "Aura III LED", "read_back", "off"),
                reading("tweez", "Tweez 300 trap strength", "not_readable", 0.02),
                reading("piezo", "Piezo stage", "not_read")]},
        },
        "check_now": None, "ownership": {"status": "not_built"},
        "registry": {"path": "contracts/registry.json", "sha256": SHA},
    }
    doc.update(over)
    return doc


def log_with(events, run="run-20261024-001"):
    return {"artifact": "run_log", "run_id": run, "t0_wall": "2026-10-24T11:00:00.000+00:00", "backend": "hardware", "events": events}


def apply(t, commands):
    return {"t_mono": t, "event": "apply", "channel": "optical_tweezers", "action": "x", "params": {"commands": commands}}


def snapshot(t, x, y, z, label="before"):
    return {"t_mono": t, "event": "snapshot", "label": label,
            "states": {"piezo_stage": {"position_um": {"x": x, "y": y, "z": z}, "backend": "python_serial"},
                       "camera_red": {"error": "not opened"}}}


@pytest.fixture
def tree(tmp_path):
    """The sample as a soft-matter-agents tree with the repository's schemas and a safety file of its own
    values, so a test can tell that a range is read and not remembered."""
    root = tmp_path / "sma"
    shutil.copytree(MOCK_DATA, root)
    shutil.rmtree(root / "console")
    shutil.copytree(REPO / "contracts" / "schemas", root / "contracts" / "schemas")
    (root / "microscope_runtime" / "envelope").mkdir(parents=True)
    safety = json.loads((REPO / "microscope_runtime" / "envelope" / "safety.json").read_text(encoding="utf-8-sig"))
    for t in safety["targets"]:
        lim = t["limits"]
        if "piezo_x_position_min" in lim:
            lim["piezo_x_position_min"]["value"], lim["piezo_x_position_max"]["value"] = 11, 555
            lim["piezo_y_position_min"]["value"], lim["piezo_y_position_max"]["value"] = 12, 556
            lim["piezo_z_position_min"]["value"], lim["piezo_z_position_max"]["value"] = 13, 557
        if "tweezers_trap_position_100x_min" in lim:
            lim["tweezers_trap_position_100x_min"]["value"], lim["tweezers_trap_position_100x_max"]["value"] = -4, 4
    (root / "microscope_runtime" / "envelope" / "safety.json").write_text(json.dumps(safety), encoding="utf-8")
    return root


def write_status(root, doc):
    d = root / "microscope_runtime" / ".runtime_status"
    d.mkdir(parents=True, exist_ok=True)
    (d / "idle_status.json").write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture
def client(engine, make_client, tree):
    return lambda **kw: make_client(engine, agent_store=SmaFiles(tree, source="soft-matter-agents"), **kw)


# -- status ------------------------------------------------------------------------------------------


def test_a_missing_status_file_is_no_status_yet_not_nothing_connected(client, tree):
    r = client().get(STATUS)
    assert r.status_code == 200 and r.json() == {"state": "none", "data": None, "problems": []}


def test_a_status_file_is_read_as_data_exactly(client, tree):
    write_status(tree, idle())
    got = client().get(STATUS).json()
    assert got["state"] == "present" and got["data"] == idle()
    chans = got["data"]["last_run"]["last_snapshot"]["channels"]
    assert [c["how"] for c in chans] == ["read_back", "not_readable", "not_read"]
    assert chans[2]["value"] is None and chans[2]["t_wall"] is None  # a reading not taken is unknown, not zero


def test_a_status_file_its_schema_refuses_is_not_shown_as_a_status(client, tree):
    bad = idle()
    bad["last_run"]["last_snapshot"]["channels"][0]["how"] = "guessed"
    write_status(tree, bad)
    got = client().get(STATUS).json()
    assert got["state"] == "invalid" and got["data"] is None and got["problems"]


def test_a_not_read_channel_with_a_value_is_refused_by_the_schema(client, tree):
    bad = idle()
    bad["last_run"]["last_snapshot"]["channels"][2]["value"] = 5
    write_status(tree, bad)
    assert client().get(STATUS).json()["state"] == "invalid"


def test_a_status_file_that_is_not_json_is_unreadable_not_none(client, tree):
    d = tree / "microscope_runtime" / ".runtime_status"
    d.mkdir(parents=True)
    (d / "idle_status.json").write_text("{not json", encoding="utf-8")
    got = client().get(STATUS).json()
    assert got["state"] == "unreadable" and got["data"] is None


def test_without_the_schema_in_the_tree_a_status_is_not_shown(client, tree):
    write_status(tree, idle())
    shutil.rmtree(tree / "contracts" / "schemas")
    assert client().get(STATUS).json()["state"] == "invalid"


def test_the_mock_store_has_no_status_and_no_stand_in(engine, make_client, tmp_path):
    got = make_client(engine, agent_store=MockStore(tmp_path / "p")).get(STATUS).json()
    assert got["state"] == "none" and got["data"] is None


def test_the_status_route_needs_a_login(client):
    assert client(login=None).get(STATUS).status_code == 401


# -- the person's limits -----------------------------------------------------------------------------


def test_the_piezo_range_is_read_from_the_safety_file(client, tree):
    got = client().get(LIMITS).json()
    assert got["state"] == "present" and got["policy_version"]
    p = got["piezo"]
    assert (p["x"]["min"]["value"], p["x"]["max"]["value"]) == (11, 555)
    assert (p["y"]["min"]["value"], p["y"]["max"]["value"]) == (12, 556)
    assert (p["z"]["min"]["value"], p["z"]["max"]["value"]) == (13, 557)
    assert p["x"]["min"]["unit"] == "um"


def test_the_range_follows_the_file_when_the_file_changes(client, tree):
    path = tree / "microscope_runtime" / "envelope" / "safety.json"
    doc = json.loads(path.read_text("utf-8"))
    for t in doc["targets"]:
        if "piezo_z_position_max" in t["limits"]:
            t["limits"]["piezo_z_position_max"]["value"] = 321
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert client().get(LIMITS).json()["piezo"]["z"]["max"]["value"] == 321


def test_no_range_is_written_into_the_console_code():
    """The piezo range and the tweezers ranges are read from the person's file. The shipped real values do not
    appear as constants in the server's or the web's source for these screens."""
    real = json.loads((REPO / "microscope_runtime" / "envelope" / "safety.json").read_text("utf-8-sig"))
    values = {str(spec["value"]) for t in real["targets"] for n, spec in t["limits"].items()
              if n.startswith(("piezo_", "tweezers_trap_position")) and isinstance(spec.get("value"), (int, float))}
    src = REPO / "console"
    files = [src / "src/sma_console/agents/instruments.py", src / "src/sma_console/server/api/instruments.py",
             src / "src/sma_console/agents/drafts.py"]
    files += sorted((src / "web/src/features/instruments").glob("*.tsx"))
    for f in files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for v in ("600", "67"):  # the person's range, 0 to 600 um, and the 60x tweezers range, +-67 um
            if v in values:
                assert f" {v} um" not in text and f"±{v}" not in text and f"= {v}" not in text, (f.name, v)


def test_a_limit_the_file_does_not_hold_is_missing_not_defaulted(client, tree):
    path = tree / "microscope_runtime" / "envelope" / "safety.json"
    doc = json.loads(path.read_text("utf-8"))
    for t in doc["targets"]:
        for k in [k for k in t["limits"] if k.startswith("piezo_z_position")]:
            del t["limits"][k]
    path.write_text(json.dumps(doc), encoding="utf-8")
    got = client().get(LIMITS).json()
    assert got["state"] in ("present", "invalid")
    if got["state"] == "present":
        assert got["piezo"]["z"] is None and got["piezo"]["x"] is not None


def test_no_safety_file_reads_as_none(client, tree):
    (tree / "microscope_runtime" / "envelope" / "safety.json").unlink()
    got = client().get(LIMITS).json()
    assert got["state"] == "none" and got["piezo"] == {}


def test_the_tweezers_ranges_are_read_too(client, tree):
    t = client().get(LIMITS).json()["tweezers"]
    assert t["positions"]["100x"]["min"]["value"] == -4 and t["positions"]["100x"]["max"]["value"] == 4
    assert t["step_max"]["value"] > 0 and t["strength"]["max"]["value"] <= 1


# -- the latest run's events -------------------------------------------------------------------------


def write_run(root, name, log, layout="microscope_agent"):
    d = root / layout / "runs" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "log.json").write_text(json.dumps(log), encoding="utf-8")


def test_traps_and_strength_come_from_what_the_run_sent(client, tree):
    write_run(tree, "run-20261024-001", log_with([
        apply(1.0, [["SIMPLE_TRAP_CREATE", "trap_1"], ["TRAP_POSITION", "trap_1", 0.0, 0.0], ["TRAP_STRENGTH", "trap_1", 0.3]]),
        apply(2.0, [["TRAP_ON", "trap_1"]]),
        apply(5.0, [["TRAP_POSITION", "trap_1", 1.0, 0.0]]),
        apply(6.0, [["SIMPLE_TRAP_CREATE", "trap_2"], ["TRAP_POSITION", "trap_2", 6.0, 2.0], ["TRAP_STRENGTH", "trap_2", 0.4], ["TRAP_ON", "trap_2"]]),
    ]))
    got = client().get(LATEST).json()
    assert got["state"] == "ok" and got["run_id"] == "run-20261024-001"
    by = {t["trap"]: t for t in got["traps"]}
    assert (by["trap_1"]["x_um"], by["trap_1"]["y_um"], by["trap_1"]["strength"], by["trap_1"]["on"]) == (1.0, 0.0, 0.3, True)
    assert (by["trap_2"]["x_um"], by["trap_2"]["y_um"], by["trap_2"]["strength"]) == (6.0, 2.0, 0.4)
    assert got["strength_last_sent"] == 0.4
    assert [(p["t_s"], p["trap"], p["x_um"]) for p in got["trap_series"]] == [(1.0, "trap_1", 0.0), (5.0, "trap_1", 1.0), (6.0, "trap_2", 6.0)]


def test_a_trap_switched_off_reads_off_and_nothing_is_invented(client, tree):
    write_run(tree, "run-20261024-001", log_with([apply(1.0, [["TRAP_POSITION", "trap_1", 0, 0], ["TRAP_STRENGTH", "trap_1", 1]]),
                                                  apply(2.0, [["TRAP_ON", "trap_1"]]), apply(3.0, [["TRAP_OFF", "trap_1"]])]))
    t = client().get(LATEST).json()["traps"][0]
    assert t["on"] is False


def test_a_run_that_sent_nothing_to_the_tweezers_shows_no_trap(client, tree):
    write_run(tree, "run-20261024-001", log_with([snapshot(1.0, 1, 2, 3)]))
    got = client().get(LATEST).json()
    assert got["state"] == "ok" and got["traps"] == [] and got["strength_last_sent"] is None and got["trap_series"] == []


def test_nothing_is_carried_forward_from_an_older_run(client, tree):
    write_run(tree, "run-20261023-001", log_with([apply(1.0, [["TRAP_POSITION", "trap_1", 9, 9], ["TRAP_STRENGTH", "trap_1", 0.9]])], "run-20261023-001"))
    write_run(tree, "run-20261024-001", log_with([snapshot(1.0, 1, 2, 3)]))
    got = client().get(LATEST).json()
    assert got["run_id"] == "run-20261024-001" and got["traps"] == [] and got["strength_last_sent"] is None


def test_the_piezo_points_come_from_snapshots_with_their_times(client, tree):
    write_run(tree, "run-20261024-001", log_with([snapshot(0.5, 10.0, 20.0, 30.0, "before"), snapshot(9.5, 11.0, 21.0, 31.0, "after"),
                                                  {"t_mono": 5, "event": "snapshot", "label": "x", "states": {"piezo_stage": {"error": "no"}}}]))
    p = client().get(LATEST).json()["piezo"]
    assert [(q["t_s"], q["x_um"], q["y_um"], q["z_um"], q["label"]) for q in p] == [(0.5, 10.0, 20.0, 30.0, "before"), (9.5, 11.0, 21.0, 31.0, "after")]
    assert p[0]["t_wall"] == "2026-10-24T11:00:00.500Z"


def test_the_runs_folder_missing_is_its_own_answer(engine, make_client, tmp_path):
    root = tmp_path / "bare"
    (root / "microscope_agent").mkdir(parents=True)
    got = make_client(engine, agent_store=SmaFiles(root, source="soft-matter-agents")).get(LATEST).json()
    assert got["state"] == "runs_not_found" and got["message"]


def test_no_run_at_all_is_no_run(engine, make_client, tmp_path):
    root = tmp_path / "bare"
    (root / "microscope_agent" / "runs").mkdir(parents=True)
    got = make_client(engine, agent_store=SmaFiles(root, source="soft-matter-agents")).get(LATEST).json()
    assert got["state"] == "no_run" and got["traps"] == []


# -- the drafts --------------------------------------------------------------------------------------


def post(c, **body):
    return c.post(DRAFT, json=body)


def test_a_trap_pattern_draft_is_an_ordinary_plan_card_the_schema_accepts(client, tree):
    r = post(client(), kind="trap_steps", pattern="line", objective="100x", n=3, spacing_um=1.0, strength=0.3)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["valid"] is True and d["problems"] == [] and d["range_problems"] == [] and d["saved"] is False
    assert Schemas(REPO / "contracts" / "schemas").validate(d["card"], "plan.schema.json") == []
    xs = [s["x_um"] for s in d["card"]["trap_steps"]["steps"] if s["kind"] == "create"]
    assert xs == [-1.0, 0.0, 1.0]
    kinds = [s["kind"] for s in d["card"]["trap_steps"]["steps"]]
    assert kinds == ["create", "on"] * 3 + ["hold_for_person"]
    assert [a["id"] for a in d["card"]["actions"]] == [s["id"] for s in d["card"]["trap_steps"]["steps"]]
    assert "goal_id" not in d["card"] and d["card"]["card"] == "plan" and d["card"]["status"] == "DRAFT"


@pytest.mark.parametrize("pattern", ["line", "circle", "grid"])
def test_every_pattern_validates(client, tree, pattern):
    d = post(client(), kind="trap_steps", pattern=pattern, objective="100x", n=4, spacing_um=1.0, strength=0.5).json()
    assert d["problems"] == [], d["problems"]


def test_positions_outside_the_persons_range_are_refused_from_the_file(client, tree):
    d = post(client(), kind="trap_steps", pattern="line", objective="100x", n=3, spacing_um=5.0, strength=0.3).json()
    assert d["valid"] is False and d["problems"] == []  # a good card, outside this person's limits (-4 to 4 here)
    assert any("outside -4 to 4 um" in p and "your safety file" in p for p in d["range_problems"])


def test_a_strength_outside_the_files_range_is_refused(client, tree):
    path = tree / "microscope_runtime" / "envelope" / "safety.json"
    doc = json.loads(path.read_text("utf-8"))
    for t in doc["targets"]:
        if "tweezers_trap_strength_max" in t["limits"]:
            t["limits"]["tweezers_trap_strength_max"]["value"] = 0.2
    path.write_text(json.dumps(doc), encoding="utf-8")
    d = post(client(), kind="trap_steps", pattern="line", objective="100x", n=1, spacing_um=1.0, strength=0.3).json()
    assert any("strength 0.3 is outside" in p for p in d["range_problems"])


def test_a_missing_range_refuses_every_position(client, tree):
    path = tree / "microscope_runtime" / "envelope" / "safety.json"
    doc = json.loads(path.read_text("utf-8"))
    for t in doc["targets"]:
        for k in [k for k in t["limits"] if k.startswith("tweezers_trap_position_60x")]:
            del t["limits"][k]
    path.write_text(json.dumps(doc), encoding="utf-8")
    d = post(client(), kind="trap_steps", pattern="line", objective="60x", n=1, spacing_um=1.0, strength=0.3).json()
    assert d["valid"] is False and any("no trap position range for 60x" in p for p in d["range_problems"])


def test_count_and_flicker_are_said_to_be_refused_until_a_limit_exists(client, tree):
    d = post(client(), kind="trap_steps", pattern="line", objective="100x", n=2, spacing_um=1.0, strength=0.3).json()
    text = " ".join(d["refused_today"])
    assert "Trap count" in text and "Flicker rate" in text and "until" in text


def test_the_three_part_drafts_are_composed_checked_and_refused_with_the_schemas_own_words(client, tree):
    cases = [
        dict(kind="aura", color="blue", power_mw=0.5),
        dict(kind="dialamp", state="on", intensity_percent=12),
        dict(kind="camera_exposure", exposure_ms=30),
    ]
    for body in cases:
        d = post(client(), **body).json()
        assert d["valid"] is False and d["saved"] is False
        assert d["problems"] and any("goal_id" in p or "observable" in p for p in d["problems"]), d["problems"]
        assert d["card"]["actions"][0]["device"] in ("Aura", "DiaLamp", "Kinetix_red")
        assert any("limit" in r for r in d["refused_today"])


def test_only_the_three_parts_are_offered_and_nothing_else_is_accepted(client, tree):
    for body in ({"kind": "filter_turret", "color": "x"}, {"kind": "objective"}, {"kind": "laser_combiner"},
                 {"kind": "trap_steps", "pattern": "spiral"}, {"kind": "trap_steps", "objective": "4x"},
                 {"kind": "aura", "color": "blue", "power_mw": 1, "extra": 1}):
        assert post(client(), **body).status_code == 422, body


@pytest.mark.parametrize("body", [
    dict(kind="aura", power_mw=1), dict(kind="aura", color="blue", power_mw=-1), dict(kind="dialamp", state="dim", intensity_percent=1),
    dict(kind="dialamp", state="on", intensity_percent=101), dict(kind="camera_exposure", exposure_ms=0),
    dict(kind="trap_steps", n=0), dict(kind="trap_steps", n=1000), dict(kind="trap_steps", strength=1.5),
    dict(kind="trap_steps", spacing_um=0),
])
def test_a_bad_choice_is_refused_in_words(client, tree, body):
    r = post(client(), **body)
    assert r.status_code == 422 and r.json()["detail"]


def test_no_draft_is_written_anywhere(client, tree, seat):
    before_tree, before_repo = tree_hash(tree), tree_hash(REPO / "console" / "src")
    c = client()
    for body in (dict(kind="trap_steps"), dict(kind="aura", color="blue", power_mw=1), dict(kind="dialamp", state="on", intensity_percent=5),
                 dict(kind="camera_exposure", exposure_ms=10)):
        assert post(c, **body).status_code == 200
    assert tree_hash(tree) == before_tree and tree_hash(REPO / "console" / "src") == before_repo


def test_under_the_mock_store_a_draft_is_made_and_nothing_is_written(engine, make_client, tmp_path):
    store = MockStore(tmp_path / "practice")
    sample = tree_hash(MOCK_DATA)
    d = make_client(engine, agent_store=store).post(DRAFT, json={"kind": "trap_steps", "n": 1}).json()
    assert d["saved"] is False and d["problems"] == [] and d["valid"] is False  # no safety file: nothing can be checked
    assert any("no readable safety file" in p for p in d["range_problems"])
    assert tree_hash(MOCK_DATA) == sample and not (tmp_path / "practice").exists()


def test_who_may_draft_is_the_servers_present_rule_said_in_words(client, tree):
    r = post(client(login=VIEWER), kind="trap_steps")
    assert r.status_code == 403 and "only look" in r.json()["detail"]["message"]
    r = post(client(remote=True), kind="trap_steps")
    assert r.status_code == 403
    assert post(client(login=None), kind="trap_steps").status_code == 401


def test_the_draft_route_and_the_others_send_nothing_to_an_instrument(client, tree):
    """Every route on this router is a read or a composition: there is no command kind, no run request, no stop."""
    from sma_console.server.api import instruments as mod

    paths = sorted((r.path, sorted(r.methods)) for r in mod.router.routes)
    assert paths == [("/draft", ["POST"]), ("/latest-run", ["GET"]), ("/limits", ["GET"]), ("/status", ["GET"])]


def test_the_pattern_points_are_what_a_person_would_draw():
    assert drafts.pattern_points("line", 3, 5) == [(-5.0, 0.0), (0.0, 0.0), (5.0, 0.0)]
    assert drafts.pattern_points("line", 1, 5) == [(0.0, 0.0)]
    c = drafts.pattern_points("circle", 4, 2 ** 0.5)
    assert sorted(round(abs(x) + abs(y), 3) for x, y in c) == [1.0, 1.0, 1.0, 1.0]
    g = drafts.pattern_points("grid", 4, 2)
    assert sorted(g) == [(-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)]


# -- card 015: following a run, the connection state, the piezo operation draft -------------------------

from sma_fake_run import FakeSmaRun, sma_tree, tree_state  # noqa: E402


def ev(run, t, **fields):
    run._line({"t_mono": t, "time_base": "software", **fields})


def snap(run, t, states, label="before"):
    ev(run, t, event="snapshot", label=label, states=states)


@pytest.fixture
def runs(tree):
    sma_tree(tree)
    made = []

    def make(run_id, **kw):
        r = FakeSmaRun(tree, run_id=run_id, **kw)
        made.append(r)
        return r

    yield make
    for r in made:
        r.end()


def test_the_screens_follow_the_newest_run_that_is_running_not_the_newest_run(client, tree, runs):
    running = runs("run-20261025-001")
    ended = runs("run-20261026-001")
    ended.end()
    got = client().get(LATEST).json()
    assert got["run_id"] == running.run_id and got["running"] is True and got["ended_how"] is None


def test_with_none_running_the_newest_run_is_shown_as_ended_with_how_and_when(client, tree, runs):
    old = runs("run-20261025-001")
    old.end("aborted_by_monitor")
    new = runs("run-20261026-001")
    snap(new, 1.0, {"piezo_stage": {"position_um": {"x": 1, "y": 2, "z": 3}, "backend": "mock"}})
    new.end("completed")
    got = client().get(LATEST).json()
    assert got["run_id"] == new.run_id and got["running"] is False and got["ended_how"] == "completed"
    assert got["ended_at"] is not None and got["frame_tap"] is False
    assert [(p["x_um"], p["y_um"], p["z_um"]) for p in got["piezo"]] == [(1.0, 2.0, 3.0)]


def test_a_running_runs_events_are_read_as_they_grow(client, tree, runs):
    run = runs("run-20261026-001")
    c = client()
    assert c.get(LATEST).json()["piezo"] == []
    snap(run, 1.0, {"piezo_stage": {"position_um": {"x": 10, "y": 20, "z": 30}, "backend": "mock"}})
    first = c.get(LATEST).json()
    snap(run, 2.0, {"piezo_stage": {"position_um": {"x": 11, "y": 21, "z": 31}, "backend": "mock"}}, "after")
    second = c.get(LATEST).json()
    assert len(first["piezo"]) == 1 and len(second["piezo"]) == 2 and second["running"] is True
    assert second["frame_tap"] is True and second["events_seen"] > first["events_seen"]


def test_a_run_with_no_frame_tap_says_so(client, tree, runs):
    runs("run-20261026-001", tap=False)
    got = client().get(LATEST).json()
    assert got["running"] is True and got["frame_tap"] is False


def test_trap_commands_in_a_running_runs_events_are_sent_not_read_back(client, tree, runs):
    run = runs("run-20261026-001")
    ev(run, 1.0, event="apply", channel="optical_tweezers", action="x",
       params={"commands": [["TRAP_POSITION", "trap_1", 2.0, 3.0], ["TRAP_STRENGTH", "trap_1", 0.4], ["TRAP_ON", "trap_1"]]})
    got = client().get(LATEST).json()
    assert got["traps"] == [{"trap": "trap_1", "x_um": 2.0, "y_um": 3.0, "strength": 0.4, "on": True}]
    assert got["strength_last_sent"] == 0.4


def test_the_connection_state_is_read_from_the_runs_last_snapshot(client, tree, runs):
    run = runs("run-20261026-001")
    snap(run, 1.0, {"stand_ti2e": {"error": "old"}}, "before")
    snap(run, 2.0, {"piezo_stage": {"position_um": {"x": 1, "y": 2, "z": 3}, "backend": "python_serial"},
                    "camera_red": {"error": "not opened"}, "camera_blue": {"error": "not opened"}}, "after")
    ch = client().get(LATEST).json()["channels"]
    assert ch["label"] == "after" and ch["t_s"] == 2.0
    assert {r["channel"]: (r["opened"], r["detail"], r["backend"]) for r in ch["rows"]} == {
        "piezo_stage": (True, None, "python_serial"), "camera_red": (False, "not opened", None),
        "camera_blue": (False, "not opened", None)}


def test_a_run_with_no_snapshot_has_no_connection_state(client, tree, runs):
    runs("run-20261026-001")
    ch = client().get(LATEST).json()["channels"]
    assert ch["rows"] == [] and ch["t_wall"] is None


def test_following_a_run_writes_nothing_starts_nothing_and_stops_nothing(client, tree, runs):
    run = runs("run-20261026-001")
    snap(run, 1.0, {"piezo_stage": {"position_um": {"x": 1, "y": 2, "z": 3}, "backend": "mock"}})
    before = tree_state(tree)
    c = client()
    for path in (STATUS, LIMITS, LATEST):
        assert c.get(path).status_code == 200
    assert post(c, kind="piezo", axis="x", move="step", target_um=100, tolerance_um=1).status_code == 200
    assert tree_state(tree) == before and run.stops == [] and run.refused == []


def test_a_run_not_followed_falls_back_to_its_log(client, tree):
    write_run(tree, "run-20261024-001", log_with([snapshot(1.0, 1, 2, 3)]))
    got = client().get(LATEST).json()
    assert got["running"] is False and got["frame_tap"] is False and len(got["piezo"]) == 1


# the piezo operation draft ---------------------------------------------------------------------------


def piezo_body(**over):
    return {"kind": "piezo", "axis": "x", "move": "step", "target_um": 100, "tolerance_um": 1, **over}


def test_a_piezo_step_is_an_ordinary_operation_plan_the_schema_accepts(client, tree):
    d = post(client(), **piezo_body(return_um=50)).json()
    assert d["valid"] is True and d["problems"] == [] and d["range_problems"] == [] and d["saved"] is False
    assert Schemas(REPO / "contracts" / "schemas").validate(d["card"], "plan.schema.json") == []
    op = d["card"]["operation"]
    assert op["device"] == "piezo_stage" and op["read_back"] == "before_and_after_each_move"
    assert [(m["axis"], m["kind"], m["target_um"], m["role"]) for m in op["moves"]] == [
        ("x", "step", 100, "verify_mapping"), ("x", "step", 50, "return")]
    assert [a["id"] for a in d["card"]["actions"]] == [m["id"] for m in op["moves"]]
    assert d["card"]["targets"][0]["value"] == 1 and "goal_id" not in d["card"]


def test_a_piezo_sine_comes_with_the_approach_step_to_where_it_starts(client, tree):
    body = piezo_body(axis="y", move="sine", centre_um=100, amplitude_um=5, period_s=10, cycles=2,
                      points_per_period=16, start="minimum")
    del body["target_um"]
    d = post(client(), **body).json()
    assert d["problems"] == [] and d["range_problems"] == []
    moves = d["card"]["operation"]["moves"]
    assert [(m["kind"], m.get("role")) for m in moves] == [("step", "approach"), ("sine", None)]
    assert moves[0]["target_um"] == 95 and moves[1]["host_timed"] is True
    assert [m["id"] for m in moves] == ["approach_y", "sine_y"]
    assert [a["id"] for a in d["card"]["actions"]] == ["approach_y", "sine_y"]


def test_a_step_on_z_may_only_find_a_direction_or_return(client, tree):
    assert post(client(), **piezo_body(axis="z", role="direction_finding")).json()["problems"] == []
    r = post(client(), **piezo_body(axis="z"))
    assert r.status_code == 422 and "direction_finding" in r.json()["detail"]["message"]


def test_a_sine_on_z_is_refused(client, tree):
    body = piezo_body(axis="z", move="sine", centre_um=100, amplitude_um=5, period_s=10, cycles=1, points_per_period=8)
    r = post(client(), **body)
    assert r.status_code == 422 and "x or y only" in r.json()["detail"]["message"]


@pytest.mark.parametrize("tol", [None, 0, -1])
def test_the_readback_tolerance_is_the_persons_and_never_defaulted(client, tree, tol):
    body = piezo_body()
    del body["tolerance_um"]
    if tol is not None:
        body["tolerance_um"] = tol
    r = post(client(), **body)
    assert r.status_code == 422 and "tolerance" in r.json()["detail"]["message"]


def test_a_position_outside_the_persons_piezo_range_is_refused_from_the_file(client, tree):
    d = post(client(), **piezo_body(target_um=9999)).json()
    assert d["valid"] is False and any("11 to 555" in p for p in d["range_problems"]), d["range_problems"]
    assert post(client(), **piezo_body(target_um=12)).json()["range_problems"] == []


def test_a_sine_is_checked_at_both_ends_of_its_swing(client, tree):
    body = piezo_body(move="sine", centre_um=550, amplitude_um=10, period_s=10, cycles=1, points_per_period=8)
    del body["target_um"]
    d = post(client(), **body).json()
    assert any("560" in p for p in d["range_problems"]), d["range_problems"]


def test_a_missing_piezo_range_refuses_every_position(client, tree):
    path = tree / "microscope_runtime" / "envelope" / "safety.json"
    safety = json.loads(path.read_text(encoding="utf-8"))
    for t in safety["targets"]:
        for k in [k for k in t["limits"] if k.startswith("piezo_x_position")]:
            del t["limits"][k]
    path.write_text(json.dumps(safety), encoding="utf-8")
    d = post(client(), **piezo_body()).json()
    assert d["valid"] is False and any("no piezo range for x" in p for p in d["range_problems"])


def test_a_piezo_draft_saves_nothing(client, tree):
    before = tree_hash(tree)
    assert post(client(), **piezo_body()).status_code == 200
    assert tree_hash(tree) == before


@pytest.mark.parametrize("body", [dict(axis="w"), dict(move="spin"), dict(role="whenever"), dict(start="middle")])
def test_a_bad_piezo_choice_is_refused(client, tree, body):
    assert post(client(), **piezo_body(**body)).status_code == 422


# the live optical path (card 015) -----------------------------------------------------------------------


def stand(devices, backend="mock"):
    return {"state": devices, "aborted": False, "backend": backend}


def test_each_path_element_comes_with_what_the_run_read_back_and_when(client, tree, runs):
    run = runs("run-20261026-001")
    snap(run, 1.0, {"stand_ti2e": stand({"FilterTurret1": {"State": "2", "Label": "DAPI"}, "LightPath": {"State": "1"}}),
                    "confocal_csuw1": stand({"CSUW1-Dichroic": {"State": "3"}}),
                    "widefield_source_b": stand({"DiaLamp": {"State": "1", "Intensity": "12"}})})
    rows = {r["device"]: r for r in client().get(LATEST).json()["path"]}
    assert rows["FilterTurret1"]["props"] == {"State": "2", "Label": "DAPI"}
    assert rows["DiaLamp"]["props"] == {"State": "1", "Intensity": "12"}
    assert rows["CSUW1-Dichroic"]["props"] == {"State": "3"}
    assert rows["LightPath"]["t_wall"].startswith("2026-10-05T17:00:01") and rows["LightPath"]["t_s"] == 1.0
    assert {r["backend"] for r in rows.values()} == {"mock"}


def test_a_device_no_snapshot_reported_is_absent_and_nothing_is_filled_in(client, tree, runs):
    run = runs("run-20261026-001")
    snap(run, 1.0, {"stand_ti2e": stand({"FilterTurret1": {"State": "2"}})})
    got = client().get(LATEST).json()["path"]
    assert [r["device"] for r in got] == ["FilterTurret1"]


def test_the_latest_read_of_a_device_replaces_the_earlier_one_and_keeps_its_own_time(client, tree, runs):
    run = runs("run-20261026-001")
    snap(run, 1.0, {"stand_ti2e": stand({"FilterTurret1": {"State": "1"}, "FilterTurret2": {"State": "5"}})})
    snap(run, 4.0, {"stand_ti2e": stand({"FilterTurret1": {"State": "2"}})}, "after")
    rows = {r["device"]: r for r in client().get(LATEST).json()["path"]}
    assert rows["FilterTurret1"]["props"] == {"State": "2"} and rows["FilterTurret1"]["t_s"] == 4.0
    assert rows["FilterTurret2"]["props"] == {"State": "5"} and rows["FilterTurret2"]["t_s"] == 1.0


def test_a_channel_that_could_not_be_read_reports_no_device(client, tree, runs):
    run = runs("run-20261026-001")
    snap(run, 1.0, {"stand_ti2e": {"error": "no Micro-Manager configuration is loaded"}})
    assert client().get(LATEST).json()["path"] == []


def test_the_instruments_own_backend_is_carried_so_the_screen_can_say_whose_state_it_is(client, tree, runs):
    run = runs("run-20261026-001")
    snap(run, 1.0, {"stand_ti2e": stand({"FilterTurret1": {"State": "1"}}, backend="micromanager")})
    assert client().get(LATEST).json()["path"][0]["backend"] == "micromanager"


def test_an_ended_runs_last_path_is_kept(client, tree, runs):
    run = runs("run-20261026-001")
    snap(run, 1.0, {"stand_ti2e": stand({"LightPath": {"State": "1"}})})
    run.end()
    got = client().get(LATEST).json()
    assert got["running"] is False and [r["device"] for r in got["path"]] == ["LightPath"]


def test_no_run_has_no_path(engine, make_client, tmp_path):
    root = tmp_path / "bare"
    (root / "microscope_agent" / "runs").mkdir(parents=True)
    got = make_client(engine, agent_store=SmaFiles(root, source="soft-matter-agents")).get(LATEST).json()
    assert got["path"] == []
