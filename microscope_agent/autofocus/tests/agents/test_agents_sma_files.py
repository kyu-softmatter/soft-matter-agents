"""SmaFiles reads and never writes. Format checks run on a read-only copy of mock_data;
the real soft-matter-agents checkout is read when it is present, else skipped."""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from dino_autofocus.agents import NotFoundError, ReadOnlyStoreError, SmaFiles
from dino_autofocus.agents.mock_store import MOCK_DATA
from dino_autofocus.agents.sma_files import (
    ROOT_ENV,
    default_root,
    guess_kind,
    long_path,
    split_version,
)


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    root = long_path(root)
    return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in root.rglob("*")}


def read_everything(s: SmaFiles) -> int:
    n = 0
    for agent in ("microscope", "simulation"):
        for q in s.list_questions(agent):
            for v in q.versions:
                s.get_question(q.qid, v)
                n += 1
        for r in s.list_runs(agent):
            s.get_run(agent, r.run_id)
            n += 1
        n += len(s.list_approvals(agent))
    n += len(s.list_inbox())
    return n


def test_version_prefix():
    assert split_version("v3_goal.json") == (3, "goal.json")
    assert split_version("v12_axis_x_a1.json") == (12, "axis_x_a1.json")
    assert split_version("goal.json") == (1, "goal.json")
    assert split_version("vx_goal.json") == (1, "vx_goal.json")


def test_kind_from_file_name():
    assert guess_kind("axis_bd_pairwise_a7.json") == "axis"
    assert guess_kind("plan_simulation_sim-20260923-001.json") == "plan"
    assert guess_kind("refusal_s4_sim-20260923-001.json") == "refusal"
    assert guess_kind("synthesis.json") == "synthesis"
    assert guess_kind("configs.json") == "configs"


def test_root_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(ROOT_ENV, str(tmp_path))
    assert default_root() == tmp_path
    assert SmaFiles().root == tmp_path
    monkeypatch.delenv(ROOT_ENV)
    assert default_root() == Path(r"D:\codes\github\soft-matter-agents")


@pytest.fixture
def readonly_copy(tmp_path):
    root = tmp_path / "sma"
    shutil.copytree(long_path(MOCK_DATA), root)
    files = [p for p in long_path(root).rglob("*") if p.is_file()]
    for p in files:
        os.chmod(p, stat.S_IREAD)
    yield root
    for p in files:
        os.chmod(p, stat.S_IREAD | stat.S_IWRITE)


def test_reads_a_read_only_copy_and_changes_nothing(readonly_copy):
    before = snapshot(readonly_copy)
    s = SmaFiles(readonly_copy)
    assert s.available()
    assert read_everything(s) > 5
    with pytest.raises(ReadOnlyStoreError):
        s.submit_question("q", "microscope")
    assert snapshot(readonly_copy) == before


def test_same_reading_as_the_mock_store(readonly_copy):
    s = SmaFiles(readonly_copy)
    d = s.get_question("sim-20260923-001")
    assert d.summary.source == "soft-matter-agents"
    assert (d.version, d.goal.name, d.summary.versions) == (3, "v3_goal.json", [1, 2, 3])


def test_odd_files_are_listed_not_fatal(tmp_path):
    q = tmp_path / "microscope_agent" / "questions" / "mic-20260101-001"
    q.mkdir(parents=True)
    (q / "goal.json").write_text('{"card": "goal", "status": "DRAFT", '
                                 '"created_at": "2026-01-01T00:00:00Z"}', encoding="utf-8")
    (q / "v2_goal.json").write_text("{ not json", encoding="utf-8")
    (q / "failures.jsonl").write_text("{}\n", encoding="utf-8")
    (q / "picture.png").write_bytes(b"\x89PNG")
    (q / "goal.json.tmp").write_text("{}", encoding="utf-8")
    (tmp_path / "microscope_agent" / "questions" / "notes").mkdir()
    run = tmp_path / "microscope_agent" / "runs" / "run-x"
    run.mkdir(parents=True)
    (run / "log.json").write_text("{ cut off", encoding="utf-8")

    s = SmaFiles(tmp_path)
    (summary,) = s.list_questions("microscope")
    assert summary.versions == [1, 2]
    v1 = s.get_question(summary.qid, 1)
    assert v1.goal.status == "DRAFT"
    assert sorted(f.name for f in v1.files) == ["failures.jsonl", "picture.png"]
    v2 = s.get_question(summary.qid, 2)
    assert v2.goal is None and [f.name for f in v2.files] == ["v2_goal.json"]
    (run,) = s.list_runs("microscope")
    assert run.status is None and run.created_at is None
    assert s.get_run("microscope", "run-x").not_opened == ["log.json"]
    assert s.list_questions("simulation") == [] and s.list_inbox() == []


def test_missing_root_is_empty_not_an_error(tmp_path):
    s = SmaFiles(tmp_path / "nowhere")
    assert not s.available()
    assert s.list_questions("microscope") == [] and s.list_runs("simulation") == []
    assert s.list_inbox() == []
    with pytest.raises(NotFoundError):
        s.get_question("mic-20260101-001")


def test_importing_pulls_in_no_heavy_or_ui_module():
    heavy = "{'torch', 'pymmcore', 'pymmcore_plus', 'tkinter', 'PySide6'}"
    code = (f"import sys, dino_autofocus.agents; bad = {heavy} & set(sys.modules); "
            "assert not bad, bad")
    subprocess.run([sys.executable, "-c", code], check=True)


REAL = SmaFiles()


@pytest.mark.skipif(not REAL.available(), reason=f"no soft-matter-agents at {REAL.root}")
def test_real_checkout_is_read_and_left_unchanged():
    watched = [REAL.root / f"{a}_agent" / sub for a in ("microscope", "simulation")
               for sub in ("questions", "runs", "inbox")] + [REAL.root / "bridge" / "threads"]
    watched = [w for w in watched if w.is_dir()]
    before = {str(w): snapshot(w) for w in watched}

    for agent in ("microscope", "simulation"):
        qs = REAL.list_questions(agent)
        assert qs and all(q.source == "soft-matter-agents" for q in qs)
        for q in qs:
            d = REAL.get_question(q.qid)
            assert d.version == q.latest_version
        runs = REAL.list_runs(agent)
        assert runs
        for r in runs[:5]:
            assert REAL.get_run(agent, r.run_id).files
    assert REAL.list_inbox()
    with pytest.raises(ReadOnlyStoreError):
        REAL.submit_question("q", "simulation")

    assert {str(w): snapshot(w) for w in watched} == before


def everything(s: SmaFiles) -> list:
    """Every record the store gives, as plain data, for comparing two stores."""
    out = []
    for agent in ("microscope", "simulation"):
        for q in s.list_questions(agent):
            out += [q.to_dict()] + [s.get_question(q.qid, v).to_dict() for v in q.versions]
        for r in s.list_runs(agent):
            out += [r.to_dict(), s.get_run(agent, r.run_id).to_dict()]
    return out + [t.to_dict() for t in s.list_inbox()]


def test_a_copy_past_max_path_reads_the_same(tmp_path):
    deep = tmp_path / ("d" * 60) / ("e" * 60) / ("f" * 60)
    shutil.copytree(long_path(MOCK_DATA), long_path(deep))
    longest = max(len(str(deep / p.relative_to(long_path(deep))))
                  for p in long_path(deep).rglob("*"))
    assert longest > 260  # past MAX_PATH, where is_file() goes False without long paths
    shallow = everything(SmaFiles(MOCK_DATA))
    assert everything(SmaFiles(deep)) == shallow
    assert len(shallow) > 10


def test_mock_store_writes_and_reads_past_max_path(tmp_path):
    from dino_autofocus.agents import MockStore

    deep = tmp_path / ("w" * 100) / ("x" * 100)
    store = MockStore(deep)
    s = store.submit_question("deep question", "microscope")
    assert store.list_questions("microscope")[0] == s
    assert store.get_question(s.qid).goal.data["question"] == "deep question"


def test_entries_that_cannot_be_stated_are_reported(tmp_path, monkeypatch):
    shutil.copytree(long_path(MOCK_DATA), tmp_path / "sma")
    root = tmp_path / "sma"
    q = root / "simulation_agent/questions/sim-20260923-001"
    (q / "v3_hidden_card.json").write_text("{}", encoding="utf-8")
    (q / "hidden_notes.md").write_text("# x", encoding="utf-8")
    inbox = root / "microscope_agent/inbox/thr-tracer-diffusivity-001"
    (inbox / "r3_hidden_ask.md").write_text("x", encoding="utf-8")

    # What a path past MAX_PATH does without long paths: listed by iterdir, but stat and
    # open fail, so is_file() and is_dir() are both False
    real_stat, real_open = Path.stat, Path.open

    def unseen(p):
        return "hidden" in p.name or (p.name == "commands.json" and "run-20260924-003" in str(p))

    def fake_stat(self, *a, **k):
        if unseen(self):
            raise FileNotFoundError(2, "The system cannot find the path specified", str(self))
        return real_stat(self, *a, **k)

    def fake_open(self, *a, **k):
        if unseen(self):
            raise FileNotFoundError(2, "The system cannot find the path specified", str(self))
        return real_open(self, *a, **k)

    monkeypatch.setattr(Path, "stat", fake_stat)
    monkeypatch.setattr(Path, "open", fake_open)
    s = SmaFiles(root)

    v3 = s.get_question("sim-20260923-001")
    assert ("v3_hidden_card.json", None) in {(f.name, f.size) for f in v3.files}
    v1 = s.get_question("sim-20260923-001", 1)
    assert ("hidden_notes.md", None) in {(f.name, f.size) for f in v1.files}

    d = s.get_run("microscope", "run-20260924-003")
    assert d.not_opened == ["commands.json"] and "commands.json" not in d.records
    assert ("commands.json", None) in {(f.name, f.size) for f in d.files}

    (t,) = s.list_inbox()
    hidden = [m for m in t.messages if m.name == "r3_hidden_ask.md"]
    assert len(hidden) == 1 and hidden[0].text is None and hidden[0].round == 3


def test_any_version_prefix_and_the_highest_is_latest(tmp_path):
    q = tmp_path / "simulation_agent" / "questions" / "sim-20260101-001"
    q.mkdir(parents=True)

    def card(name, kind, status, when):
        (q / name).write_text(f'{{"card": "{kind}", "status": "{status}", '
                              f'"created_at": "2026-01-{when:02d}T00:00:00Z"}}', encoding="utf-8")

    card("goal.json", "goal", "DRAFT", 1)
    card("v4_goal.json", "goal", "DRAFT", 4)
    card("v4_axis_x_a1.json", "axis", "VALIDATED", 4)
    card("v5_axis_x_a1.json", "axis", "VALIDATED", 5)
    card("v5_plan_simulation_sim-20260101-001.json", "plan", "VALIDATED", 6)
    card("v10_goal.json", "goal", "APPROVED", 10)
    card("v9_refusal_s4.json", "refusal", "REFUSED", 9)

    s = SmaFiles(tmp_path)
    (summary,) = s.list_questions("simulation")
    assert summary.versions == [1, 4, 5, 9, 10]  # numeric, not text, order: v10 after v9
    assert summary.latest_version == 10 and summary.status == "APPROVED"
    assert summary.updated_at == "2026-01-10T00:00:00Z"
    assert s.get_question(summary.qid).goal.name == "v10_goal.json"
    v5 = s.get_question(summary.qid, 5)
    assert (v5.goal, v5.plan.name) == (None, "v5_plan_simulation_sim-20260101-001.json")
    assert [c.name for c in v5.axes] == ["v5_axis_x_a1.json"]
    assert s.get_question(summary.qid, 9).refusal.status == "REFUSED"
    for missing in (2, 3, 11):
        with pytest.raises(NotFoundError):
            s.get_question(summary.qid, missing)


def test_summary_fields_for_the_console_list(tmp_path):
    s = SmaFiles(MOCK_DATA)
    by_qid = {q.qid: q for a in ("microscope", "simulation") for q in s.list_questions(a)}
    sim = by_qid["sim-20260923-001"]
    assert (sim.purpose, sim.intent, sim.observable_name) == (
        "characterize", "explore", "structural_relaxation_time")
    plan_only = by_qid["mic-20260925-002"]
    assert (plan_only.purpose, plan_only.intent, plan_only.observable_name) == (
        "verify", "confirm", None)  # a plan names no observable

    run = tmp_path / "microscope_agent" / "runs" / "run-20260101-001"
    run.mkdir(parents=True)
    (run / "log.json").write_text('{"approval": {"id": "a1", "kind": "plan_approval"}}',
                                  encoding="utf-8")
    other = tmp_path / "simulation_agent" / "runs" / "run-20260101-002"
    other.mkdir(parents=True)
    (other / "config.json").write_text('{"approval": {"id": null, "kind": null}}',
                                       encoding="utf-8")
    t = SmaFiles(tmp_path)
    assert t.list_runs("microscope")[0].approval_kind == "plan_approval"
    assert t.list_runs("simulation")[0].approval_kind is None
    assert {r.approval_kind for a in ("microscope", "simulation") for r in s.list_runs(a)} == {None}
