"""The fake librarian reads closed sessions and writes only librarian/; it never merges."""

import hashlib
import subprocess

import pytest

from dino_autofocus.records import (
    ExperimentSession,
    FolderStore,
    GitFolderStore,
    MockLibrarian,
    RecordsConfig,
)

USER = "operator@example.test"


@pytest.fixture(autouse=True)
def fast_code_version(monkeypatch):
    """The code-version lookup is tested in test_records_session; here it would only add
    two slow git calls on this repository per opened session."""
    from dino_autofocus.records import session as session_mod
    from dino_autofocus.records.codeversion import CodeVersion

    monkeypatch.setattr(session_mod, "code_version",
                        lambda repo=None: CodeVersion("stub", "0" * 40, False))


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout


def tree_hash(folder):
    h = hashlib.sha256()
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(folder).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def cfg_for(tmp_path):
    return RecordsConfig(records_root=tmp_path / "records", data_root=tmp_path / "data")


def test_reflects_closed_sessions_into_librarian_only(tmp_path):
    cfg = cfg_for(tmp_path)
    store = GitFolderStore(cfg)
    a = ExperimentSession.open(store, USER, "s1")
    a.sample_event("flag_set", flag_id="f1", name="good area")
    a.close()
    b = ExperimentSession.open(store, "second@example.test", "s1")
    b.sample_event("flag_set", flag_id="f2", name="debris")
    b.close()
    still_open = ExperimentSession.open(store, USER, "s1")
    still_open.sample_event("flag_set", flag_id="f3", name="not yet")
    sessions = cfg.sessions_root
    before = tree_hash(sessions)
    head_before = store.head()

    run = MockLibrarian(store).run_once()
    assert sorted(run.reflected) == sorted([a.session_id, b.session_id])
    assert run.samples == ["s1"] and run.commit
    assert tree_hash(sessions) == before  # never writes a session folder
    changed = git(cfg.records_root, "show", "--name-only", "--format=", run.commit).split()
    assert changed and all(f.startswith("librarian/") for f in changed)
    assert git(cfg.records_root, "rev-parse", "HEAD~1").strip() == head_before  # no merge
    assert git(cfg.records_root, "branch", "--format=%(refname:short)").split() == ["main"]

    summary = MockLibrarian(store).read_sample("s1")
    assert set(summary["state"]["flags"]) == {"f1", "f2"}  # open session not reflected
    assert MockLibrarian(store).run_once().reflected == []  # already done


def test_skips_a_closed_session_that_is_not_committed(tmp_path):
    cfg = cfg_for(tmp_path)
    store = GitFolderStore(cfg)
    s = ExperimentSession.open(store, USER, "s1")
    s.close()
    (s.layout.records / "late.jsonl").write_text("{}\n")  # left uncommitted
    run = MockLibrarian(store).run_once()
    assert run.reflected == [] and s.session_id in run.skipped
    store.commit(s.session_id, "late file", s.author)
    assert MockLibrarian(store).run_once().reflected == [s.session_id]


def test_a_real_root_skips_sessions_not_recorded_on_the_bench(tmp_path):
    """T-106c: the rule the soft-matter-agents librarian applies, tested here first."""
    store = FolderStore(cfg_for(tmp_path))  # root "records": not a *-mock root
    mock = ExperimentSession.open(store, USER, "s1", backend_kind="mock", bench=False)
    mock.close()
    bench = ExperimentSession.open(store, USER, "s1", backend_kind="mm-real", bench=True)
    bench.close()
    older = ExperimentSession.open(store, USER, "s1")  # no flag: reflected, like before
    older.close()
    lib = MockLibrarian(store)
    assert lib.bench_only is True
    run = lib.run_once()
    assert sorted(run.reflected) == sorted([bench.session_id, older.session_id])
    assert "bench: false" in run.skipped[mock.session_id]
    assert MockLibrarian(store).run_once().reflected == []  # the skip is not a reflection


def test_a_mock_root_keeps_reflecting_its_simulated_sessions(tmp_path):
    cfg = RecordsConfig(records_root=tmp_path / "records-mock", data_root=tmp_path / "data-mock")
    store = FolderStore(cfg)
    s = ExperimentSession.open(store, USER, "s1", backend_kind="mock", bench=False)
    s.close()
    lib = MockLibrarian(store)
    assert lib.bench_only is False
    assert lib.run_once().reflected == [s.session_id]
    strict = MockLibrarian(FolderStore(cfg), bench_only=True)  # the flag wins over the name
    assert strict.run_once().reflected == [] and strict.bench_only is True


def test_works_on_the_folder_store_too(tmp_path):
    store = FolderStore(cfg_for(tmp_path))
    s = ExperimentSession.open(store, USER, "s1")
    s.sample_event("note", text="x")
    s.close()
    run = MockLibrarian(store).run_once()
    assert run.reflected == [s.session_id] and run.commit is None
    ledger = MockLibrarian(store).ledger.read_text().splitlines()
    assert len(ledger) == 1 and '"files_ok": true' in ledger[0]
