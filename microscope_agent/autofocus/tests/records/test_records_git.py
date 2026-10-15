"""The git store: one branch, path-scoped commits, background auto-commit, no push."""

import subprocess
import sys
import threading

import pytest

from dino_autofocus.records import (
    AutoCommitter,
    ExperimentSession,
    GitFolderStore,
    MockLibrarian,
    RecordsConfig,
    sample_state,
)
from dino_autofocus.records import codeversion as codeversion_mod
from dino_autofocus.records import store as store_mod

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


@pytest.fixture
def cfg(tmp_path):
    return RecordsConfig(records_root=tmp_path / "records", data_root=tmp_path / "data",
                         max_tracked_bytes=1000)


@pytest.fixture
def store(cfg):
    return GitFolderStore(cfg)


def subcommand(cmd):
    """`git -C <dir> -c k=v ... <sub> ...` -> <sub>."""
    assert cmd[0] == "git"
    i = 1
    while cmd[i] in ("-C", "-c"):
        i += 2
    return cmd[i]


def files_in(repo, commit):
    return git(repo, "show", "--name-only", "--format=", commit).split()


def test_repo_is_created_on_main_with_no_remote(store, cfg):
    assert store.is_repo()
    ExperimentSession.open(store, USER, "s1")
    assert git(cfg.records_root, "branch", "--show-current").strip() == "main"
    assert git(cfg.records_root, "remote").strip() == ""


def test_open_commits_only_the_session_folder_as_the_user(store, cfg):
    root = cfg.records_root
    (root / "simulation" / "runs" / "r1").mkdir(parents=True)
    (root / "simulation" / "runs" / "r1" / "result.json").write_text("{}")  # another producer
    s = ExperimentSession.open(store, USER, "s1", user_name="Op Erator")
    rel = f"microscope/sessions/{s.session_id}"
    changed = files_in(root, "HEAD")
    assert changed and all(f.startswith(rel + "/") for f in changed)
    assert f"{rel}/session.json" in changed
    assert git(root, "log", "-1", "--format=%an <%ae>").strip() == f"Op Erator <{USER}>"
    assert "simulation/" in git(root, "status", "--porcelain")  # left alone, uncommitted


def test_auto_commit_runs_off_the_caller_thread(store, cfg):
    committer = AutoCommitter(store)
    s = ExperimentSession.open(store, USER, "s1", committer=committer)
    assert committer.flush(30)
    s.record("scan_4x", {"tile": "r0c0"})
    s.end_operation("scan_4x", {"tiles": 1})
    assert committer.flush(30)
    rel = f"microscope/sessions/{s.session_id}"
    # a queued commit takes whatever is on disk when it runs, so requests can coalesce;
    # here the open commit finished first, so there are exactly two
    assert len(store.log_paths(rel)) == 2
    assert not store.uncommitted(rel)
    assert "scan_4x finished" in git(cfg.records_root, "log", "-1", "--format=%s")
    committer.stop()


class SlowStore(GitFolderStore):
    def __init__(self, cfg, gate):
        super().__init__(cfg)
        self.gate = gate

    def commit(self, session_id, message, author):
        self.gate.wait(30)
        return super().commit(session_id, message, author)


def test_a_slow_commit_does_not_block_the_measurement(cfg):
    gate = threading.Event()
    store = SlowStore(cfg, gate)
    committer = AutoCommitter(store)
    s = ExperimentSession.open(store, USER, "s1", committer=committer)  # commit is queued
    for i in range(20):
        s.record("live", {"frame": i})  # returns while the worker waits on git
    s.end_operation("live")
    assert not committer.flush(0.2)  # still blocked on the gate
    gate.set()
    assert committer.flush(30)
    assert not store.uncommitted(f"microscope/sessions/{s.session_id}")
    committer.stop()


def test_failed_commit_is_logged_and_the_session_goes_on(store, cfg):
    seen = []
    committer = AutoCommitter(store, on_failure=seen.append)
    s = ExperimentSession.open(store, USER, "s1", committer=committer)
    assert committer.flush(30)
    lock = cfg.records_root / ".git" / "index.lock"
    lock.write_text("")  # another git process holds the index
    s.record("scan_4x", {"tile": "r0c0"})
    s.end_operation("scan_4x")
    assert committer.flush(30)
    assert len(committer.failures) == 1 and seen and "index.lock" in seen[0].error
    s.record("scan_4x", {"tile": "r0c1"})  # measurement continues
    lock.unlink()
    s.end_operation("scan_4x")
    assert committer.flush(30)
    rel = f"microscope/sessions/{s.session_id}"
    assert not store.uncommitted(rel)  # the next commit picked up what was left
    lines = git(cfg.records_root, "show", f"HEAD:{rel}/records/scan_4x.jsonl").splitlines()
    assert len(lines) == 4  # two tiles + two operation_finished lines
    committer.stop()


def test_sync_commit_failure_is_written_to_the_session_log(cfg):
    class Broken(GitFolderStore):
        def commit(self, session_id, message, author):
            raise store_mod.GitError("disk full")

    s = ExperimentSession.open(Broken(cfg), USER, "s1")
    s.end_operation("status")
    fails = [d for d in s.log_lines() if d["msg"] == "commit failed"]
    assert len(fails) == 2 and fails[0]["error"] == "disk full"


def test_two_sessions_on_one_sample_commit_without_conflict(store, cfg):
    committer = AutoCommitter(store)
    a = ExperimentSession.open(store, USER, "s1", committer=committer)
    b = ExperimentSession.open(store, "second@example.test", "s1", committer=committer)
    for i in range(3):  # interleaved, both "editing" the same sample
        a.sample_event("flag_set", flag_id=f"a{i}", name="from a")
        b.sample_event("flag_set", flag_id=f"b{i}", name="from b")
        a.end_operation("map")
        b.end_operation("map")
    a.close()
    b.close()
    assert committer.flush(60) and not committer.failures
    assert git(cfg.records_root, "status", "--porcelain", "--", "microscope").strip() == ""
    st = sample_state(store, "s1")
    assert set(st.flags) == {"a0", "a1", "a2", "b0", "b1", "b2"}
    assert sorted(st.sessions) == sorted([a.session_id, b.session_id])
    committer.stop()


def test_large_files_stay_out_of_git(store, cfg, tmp_path):
    s = ExperimentSession.open(store, USER, "s1")
    big = tmp_path / "stack.npy"
    big.write_bytes(b"z" * 5000)
    s.attach(big, kind="stack")
    s.end_operation("grab")
    tracked = git(cfg.records_root, "ls-files").split()
    assert f"microscope/sessions/{s.session_id}/manifest.json" in tracked
    assert not any(f.endswith("stack.npy") for f in tracked)
    assert (cfg.data_root / s.session_id / "stack.npy").is_file()


def test_nothing_in_the_package_pushes(cfg, tmp_path, monkeypatch):
    calls = []
    real = subprocess.run

    flags = []

    def spy(cmd, *a, **kw):
        calls.append(list(cmd))
        flags.append(kw.get("creationflags", 0))
        return real(cmd, *a, **kw)

    from dino_autofocus.records import session as session_mod

    monkeypatch.setattr(session_mod, "code_version", codeversion_mod.code_version)  # real one
    monkeypatch.setattr(store_mod.subprocess, "run", spy)
    monkeypatch.setattr(codeversion_mod.subprocess, "run", spy)
    store = GitFolderStore(cfg)
    committer = AutoCommitter(store)
    s = ExperimentSession.open(store, USER, "s1", committer=committer)
    s.sample_event("note", text="x")
    s.close()
    assert committer.flush(30)
    MockLibrarian(store).run_once()
    committer.stop()
    subcommands = {subcommand(c) for c in calls}
    assert subcommands <= {"init", "rev-parse", "status", "add", "diff", "commit", "log"}
    assert not subcommands & {"push", "fetch", "pull", "merge", "remote", "clone"}
    if sys.platform == "win32":  # no console window may flash on the desktop
        assert all(f & subprocess.CREATE_NO_WINDOW for f in flags), flags
