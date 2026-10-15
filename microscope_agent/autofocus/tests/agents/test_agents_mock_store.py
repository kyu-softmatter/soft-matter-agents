"""MockStore: every method over the copied sample, version choice, round trips, and that
submitting writes in the write folder and nowhere else."""

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dino_autofocus.agents import (
    AgentStore,
    InboxThread,
    MockStore,
    NotFoundError,
    QuestionDetail,
    QuestionSummary,
    RunDetail,
    RunSummary,
    SmaFiles,
    open_store,
)
from dino_autofocus.agents.mock_store import MOCK_DATA, ORIGIN, PACKAGE_DIR
from dino_autofocus.agents.sma_files import long_path

SIM_Q = "sim-20260923-001"
DATA = long_path(MOCK_DATA)  # the tests' own reads survive a deep checkout too
PACKAGE = long_path(PACKAGE_DIR)


def fixed_clock():
    return datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path):
    return MockStore(tmp_path / "written", clock=fixed_clock)


def tree(root: Path) -> dict[str, str]:
    root = long_path(root)
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def roundtrip(obj):
    return type(obj).from_dict(json.loads(json.dumps(obj.to_dict())))


def test_is_an_agent_store(store):
    assert isinstance(store, AgentStore)
    assert isinstance(SmaFiles(MOCK_DATA), AgentStore)


def test_lists_questions_of_each_seat_newest_first(store):
    mic = store.list_questions("microscope")
    sim = store.list_questions("simulation")
    assert [q.qid for q in mic] == ["mic-20260925-002", "mic-20260925-001"]
    assert [q.qid for q in sim] == [SIM_Q]
    assert all(q.source == "mock" for q in mic + sim)
    assert all(q.agent == "microscope" for q in mic)
    with pytest.raises(ValueError):
        store.list_questions("librarian")


def test_summary_lifts_status_times_and_title(store):
    (q,) = store.list_questions("simulation")
    assert q.versions == [1, 2, 3] and q.latest_version == 3
    assert q.status == "VALIDATED"  # the v3 plan is the newest card
    assert q.created_at == "2026-09-23T16:30:00Z"  # the first goal
    assert q.updated_at == "2026-09-24T14:55:00Z"  # the v3 plan
    assert q.title == "structural relaxation from a random initial configuration"
    by_qid = {x.qid: x for x in store.list_questions("microscope")}
    assert by_qid["mic-20260925-001"].title == "well_occupancy"
    assert by_qid["mic-20260925-002"].title == "verify · bead_held"  # a plan, no goal


def test_latest_version_is_the_default(store):
    d = store.get_question(SIM_Q)
    assert d.version == 3
    assert d.goal.name == "v3_goal.json" and d.goal.version == 3
    assert [c.name for c in d.axes] == ["v3_axis_bd_pairwise_a7.json"]
    assert d.plan.name == "v3_plan_simulation_sim-20260923-001.json"
    assert d.synthesis.kind == "synthesis"
    assert d.refusal is None and d.refusals == []
    assert d.summary.versions == [1, 2, 3]


def test_older_versions_hold_only_their_own_files(store):
    v1 = store.get_question(SIM_Q, version=1)
    assert v1.goal.name == "goal.json"
    assert v1.refusal.name == "refusal_s4_sim-20260923-001.json"
    assert v1.refusal.status == "REFUSED"
    assert [x.name for x in v1.documents] == ["question_simulation_sim-20260923-001.md"]
    v2 = store.get_question(SIM_Q, version=2)
    assert v2.goal.name == "v2_goal.json"
    assert v2.plan is None and v2.refusals == []  # the v1 refusal does not carry forward
    with pytest.raises(NotFoundError):
        store.get_question(SIM_Q, version=4)


def test_card_content_is_kept_whole(store):
    d = store.get_question(SIM_Q)
    on_disk = json.loads((DATA / "simulation_agent/questions" / SIM_Q / "v3_goal.json")
                         .read_text(encoding="utf-8"))
    assert d.goal.data == on_disk
    assert d.goal.data["numbers"] == on_disk["numbers"]  # grades pass through untouched
    other = store.get_question("mic-20260925-001")
    assert [c.kind for c in other.others] == ["analysis_method_declared"]


def test_unknown_questions_raise(store):
    for qid in ("sim-20990101-001", "mic-20260925-999", "not-a-qid", "../etc"):
        with pytest.raises(NotFoundError):
            store.get_question(qid)


def test_runs(store):
    (mic,) = store.list_runs("microscope")
    assert mic.run_id == "run-20260924-003"
    assert mic.status.startswith("stopped:")  # the outcome of its run_end event
    assert mic.created_at == "2026-09-24T19:06:52.466+00:00"
    assert mic.qid is None and mic.plan_id is None  # this run had no plan
    d = store.get_run("microscope", mic.run_id)
    assert set(d.records) == {"commands.json", "log.json"}
    assert isinstance(d.records["commands.json"], list)

    (sim,) = store.list_runs("simulation")
    assert sim.qid == SIM_Q and sim.status == "complete"
    d = store.get_run("simulation", sim.run_id)
    assert set(d.records) == {"config.json", "log.json", "observables.json",
                              "trajectory_meta.json"}
    assert {f.name for f in d.files} == set(d.records)
    for bad in ("run-20990101-001", "../runs", ".."):
        with pytest.raises(NotFoundError):
            store.get_run("simulation", bad)


def test_large_records_are_listed_not_opened(tmp_path):
    shutil.copytree(DATA, tmp_path / "data")
    s = SmaFiles(tmp_path / "data", max_read_bytes=5000)
    d = s.get_run("simulation", "run-20260924-001-smoke-g2k2")
    assert d.not_opened == ["log.json"]  # 9 KB, over the 5 KB limit
    assert "log.json" not in d.records
    assert "log.json" in {f.name for f in d.files}


def test_inbox(store):
    (t,) = store.list_inbox()
    assert t.thread == "thr-tracer-diffusivity-001"
    assert t.agent == "microscope"
    assert (t.state, t.turn, t.round) == ("open", "microscope_agent", 2)
    assert [(m.round, m.kind) for m in t.messages] == [(1, "ask_experiment"),
                                                       (2, "ask_experiment")]
    assert all(m.text and m.card is None for m in t.messages)


def test_everything_survives_a_json_round_trip(store):
    store.submit_question("Is the bead stuck?", "microscope")
    objs = []
    for agent in ("microscope", "simulation"):
        for q in store.list_questions(agent):
            objs.append(q)
            for v in q.versions:
                objs.append(store.get_question(q.qid, v))
        for r in store.list_runs(agent):
            objs += [r, store.get_run(agent, r.run_id)]
    objs += store.list_inbox()
    kinds = {type(o) for o in objs}
    assert kinds == {QuestionSummary, QuestionDetail, RunSummary, RunDetail, InboxThread}
    for o in objs:
        assert roundtrip(o) == o


def test_submit_writes_a_marked_draft_and_lists_it_first(store):
    text = "How fast do 2 um beads diffuse 10 um above the coverslip?\nSecond line."
    s = store.submit_question(text, "microscope", purpose="characterize",
                              observable="tracer_diffusivity")
    assert s.qid == "mic-20261001-901"
    assert (s.status, s.source, s.versions) == ("DRAFT", "mock-submitted", [1])
    assert s.title == text.splitlines()[0]
    assert store.list_questions("microscope")[0] == s
    goal = store.get_question(s.qid).goal
    assert goal.data["origin"] == ORIGIN
    assert goal.data["question"] == text and goal.data["constraint_notes"] == [text]
    assert goal.data["purpose"] == "characterize"
    assert goal.data["observable"] == {"name": "tracer_diffusivity"}
    assert goal.data["qid"] == s.qid and goal.data["author"] == "human"
    assert re.fullmatch(r"^(mic|sim)-[0-9]{8}-[0-9]{3}$", s.qid)
    s2 = store.submit_question("another", "microscope")
    assert s2.qid == "mic-20261001-902"
    assert "purpose" not in store.get_question(s2.qid).goal.data  # not guessed
    s3 = store.submit_question("for the other seat", "simulation")
    assert s3.qid == "sim-20261001-901" and s3.agent == "simulation"


def test_submit_refuses_bad_input(store):
    with pytest.raises(ValueError):
        store.submit_question("   ", "microscope")
    with pytest.raises(ValueError):
        store.submit_question("q", "bridge")
    with pytest.raises(ValueError):
        store.submit_question("q", "microscope", purpose="find out")


def test_submit_writes_only_in_the_write_folder(tmp_path):
    before_sample = tree(MOCK_DATA)
    before_package = tree(PACKAGE)
    write_dir = tmp_path / "written"
    store = MockStore(write_dir, clock=fixed_clock)
    store.submit_question("q one", "microscope")
    store.submit_question("q two", "simulation")
    assert tree(MOCK_DATA) == before_sample
    assert {k for k in tree(PACKAGE) if "__pycache__" not in k} == \
        {k for k in before_package if "__pycache__" not in k}
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")
                  if p.is_file()) == [
        "written/microscope_agent/questions/mic-20261001-901/goal.json",
        "written/simulation_agent/questions/sim-20261001-901/goal.json",
    ]


def test_write_folder_may_not_be_inside_the_package():
    with pytest.raises(ValueError):
        MockStore(MOCK_DATA)
    with pytest.raises(ValueError):
        MockStore(PACKAGE_DIR / "somewhere")


def test_default_write_folder_is_a_temporary_one():
    with MockStore(clock=fixed_clock) as store:
        assert store.list_questions("microscope")  # reading makes no folder
        assert store._write_dir is None
        store.submit_question("q", "microscope")
        made = store.write_dir
        assert PACKAGE_DIR not in made.parents
        assert (made / "microscope_agent/questions/mic-20261001-901/goal.json").is_file()
    assert not made.exists()  # leaving the block deleted the folder the store made


def test_close_deletes_only_a_folder_the_store_made(tmp_path):
    store = MockStore(clock=fixed_clock)
    store.submit_question("q", "microscope")
    made = store.write_dir
    store.close()
    store.close()  # twice is fine
    assert not made.exists()
    assert store.list_questions("microscope")[0].source == "mock"  # the sample is still read
    again = store.submit_question("q", "microscope")  # a new temporary folder
    assert again.qid == "mic-20261001-901" and store.write_dir != made
    store.close()

    given = tmp_path / "given"
    with MockStore(given, clock=fixed_clock) as mine:
        mine.submit_question("q", "simulation")
    mine.close()
    assert (given / "simulation_agent/questions/sim-20261001-901/goal.json").is_file()


def test_writable_flag():
    assert MockStore.writable is True and SmaFiles.writable is False
    assert MockStore().writable and not SmaFiles(MOCK_DATA).writable


def test_sample_is_small_and_says_where_it_came_from():
    files = [p for p in DATA.rglob("*") if p.is_file()]
    assert sum(p.stat().st_size for p in files) < 200_000
    source = (DATA / "SOURCE.md").read_text(encoding="utf-8")
    assert re.search(r"\b[0-9a-f]{40}\b", source)


def test_open_store(tmp_path):
    assert isinstance(open_store("mock", tmp_path), MockStore)
    s = open_store("sma", tmp_path)
    assert isinstance(s, SmaFiles) and s.root == tmp_path
    with pytest.raises(ValueError):
        open_store("http")
